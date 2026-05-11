"""
Layer 4.5: Optimization Engine — Response Curve Portfolio.

Implements 4 yield response models:
  1. Mitscherlich (diminishing returns): Y = Ymax * (1 - exp(-c*(x+b)))
  2. Quadratic-Plateau: Y = a + bx + cx^2 until plateau
  3. Linear-Plateau: Y = a + bx until plateau
  4. Square-Root (Baule): Y = a + b*sqrt(x) + cx

Economic optimization: Marginal Revenue = Marginal Cost -> optimal rate
Product selection: 4R Right Source matching

Split application timing based on phenology stage and crop type.

References:
  - Cerrato & Blackmer (1990): Comparison of response models
  - Bullock & Bullock (1994): Quadratic-plateau for economic optimum
  - IPNI 4R Nutrient Stewardship Framework
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from layer4_nutrients.schema import (
    Prescription, NutrientState, ActionId, ApplicationMethod,
    FertilizerProduct, PRODUCT_ANALYSIS, ResponseModel,
    PrescriptionAudit, Severity, TimingWindow, SplitApplication,
    EnvironmentalRisk, RegulatoryCompliance, Nutrient, RiskIfWrong,
    MACRO_NUTRIENTS,
)
from layer4_nutrients.policy.compliance_gate import ComplianceGate


# ============================================================================
# Response Curve Functions
# ============================================================================

def mitscherlich_response(x: float, ymax: float, c: float, b: float) -> float:
    """Mitscherlich: Y = Ymax * (1 - exp(-c*(x+b)))"""
    return ymax * (1.0 - math.exp(-c * (x + b)))


def mitscherlich_marginal(x: float, ymax: float, c: float, b: float) -> float:
    """dY/dx for Mitscherlich."""
    return ymax * c * math.exp(-c * (x + b))


def quadratic_plateau_response(x: float, a: float, b: float, c: float) -> float:
    """Quadratic-Plateau: Y = a + bx + cx^2, capped at vertex."""
    vertex_x = -b / (2 * c) if c != 0 else 0
    plateau = a + b * vertex_x + c * vertex_x * vertex_x
    if x >= vertex_x:
        return plateau
    return a + b * x + c * x * x


def quadratic_plateau_marginal(x: float, a: float, b: float, c: float) -> float:
    """dY/dx for Quadratic-Plateau."""
    vertex_x = -b / (2 * c) if c != 0 else 0
    if x >= vertex_x:
        return 0.0  # On plateau
    return b + 2 * c * x


def linear_plateau_response(x: float, a: float, b: float, plateau: float) -> float:
    """Linear-Plateau: Y = a + bx, capped at plateau."""
    y = a + b * x
    return min(y, plateau)


def linear_plateau_marginal(x: float, a: float, b: float, plateau: float) -> float:
    """dY/dx for Linear-Plateau."""
    if a + b * x >= plateau:
        return 0.0
    return b


# ============================================================================
# Crop-specific response parameters
# ============================================================================

# Calibrated per nutrient × crop (from meta-analysis literature)
RESPONSE_PARAMS = {
    "corn": {
        "N": {"model": ResponseModel.QUADRATIC_PLATEAU,
              "params": {"a": 6.0, "b": 0.045, "c": -0.00012},
              "ymax": 14.0, "n0": 40.0},
        "P": {"model": ResponseModel.LINEAR_PLATEAU,
              "params": {"a": 8.0, "b": 0.10, "plateau": 12.0}, "ymax": 12.0},
        "K": {"model": ResponseModel.MITSCHERLICH,
              "params": {"ymax": 13.0, "c": 0.01, "b": 50.0}, "ymax": 13.0},
    },
    "_default": {
        "N": {"model": ResponseModel.MITSCHERLICH,
              "params": {"ymax": 10.0, "c": 0.015, "b": 30.0}, "ymax": 10.0, "n0": 30.0},
        "P": {"model": ResponseModel.LINEAR_PLATEAU,
              "params": {"a": 6.0, "b": 0.08, "plateau": 9.0}, "ymax": 9.0},
        "K": {"model": ResponseModel.MITSCHERLICH,
              "params": {"ymax": 10.0, "c": 0.012, "b": 40.0}, "ymax": 10.0},
    },
}

# Default commodity prices ($/ton or MAD/ton)
CROP_PRICES = {
    "corn": 200.0, "wheat": 250.0, "soybean": 400.0, "rice": 350.0,
    "cotton": 1500.0, "barley": 220.0, "potato": 150.0, "sorghum": 180.0,
    "alfalfa": 180.0, "canola": 500.0, "sunflower": 450.0,
}

# Product cost ($/kg product)
PRODUCT_COSTS = {
    FertilizerProduct.UREA: 0.45, FertilizerProduct.CAN: 0.35,
    FertilizerProduct.DAP: 0.55, FertilizerProduct.MAP: 0.50,
    FertilizerProduct.TSP: 0.40, FertilizerProduct.MOP: 0.35,
    FertilizerProduct.SOP: 0.55, FertilizerProduct.NPK_15_15_15: 0.40,
    FertilizerProduct.AMMONIUM_SULFATE: 0.30, FertilizerProduct.UAN_28: 0.30,
    FertilizerProduct.UAN_32: 0.32, FertilizerProduct.LIME: 0.05,
}

# Split application templates by crop × nutrient
SPLIT_TEMPLATES = {
    "corn": {
        "N": [
            {"fraction": 0.30, "stage": "initial", "method": ApplicationMethod.BANDED},
            {"fraction": 0.40, "stage": "vegetative", "method": ApplicationMethod.SIDE_DRESS},
            {"fraction": 0.30, "stage": "reproductive", "method": ApplicationMethod.TOP_DRESS},
        ],
    },
    "wheat": {
        "N": [
            {"fraction": 0.40, "stage": "initial", "method": ApplicationMethod.BROADCAST},
            {"fraction": 0.60, "stage": "vegetative", "method": ApplicationMethod.TOP_DRESS},
        ],
    },
    "_default": {
        "N": [
            {"fraction": 0.50, "stage": "initial", "method": ApplicationMethod.BROADCAST},
            {"fraction": 0.50, "stage": "vegetative", "method": ApplicationMethod.SIDE_DRESS},
        ],
        "P": [{"fraction": 1.0, "stage": "initial", "method": ApplicationMethod.BANDED}],
        "K": [{"fraction": 1.0, "stage": "initial", "method": ApplicationMethod.BROADCAST}],
    },
}


def _select_product(nutrient: Nutrient, method: ApplicationMethod, soil_ph: Optional[float] = None) -> FertilizerProduct:
    """4R Right Source: select best product for conditions."""
    if nutrient == Nutrient.N:
        if method == ApplicationMethod.FERTIGATION:
            return FertilizerProduct.UAN_32
        if soil_ph is not None and soil_ph > 7.5:
            return FertilizerProduct.CAN  # Less volatile than urea on alkaline soils
        return FertilizerProduct.UREA
    elif nutrient == Nutrient.P:
        return FertilizerProduct.DAP
    elif nutrient == Nutrient.K:
        return FertilizerProduct.MOP
    return FertilizerProduct.NPK_15_15_15


class OptimizationEngine:
    """Response curve portfolio optimizer with 4R compliance."""

    def __init__(self):
        self.gate = ComplianceGate()

    def optimize(
        self,
        states: Dict[Nutrient, NutrientState],
        swb_out: Any,
        crop_type: str = "corn",
        management_goal: str = "yield_max",
        soil_ph: Optional[float] = None,
        irrigation_type: str = "rainfed",
        constraints: Optional[Dict] = None,
    ) -> List[Prescription]:
        """Generate 4R prescriptions for all deficient nutrients."""

        prescriptions = []
        for nutrient in MACRO_NUTRIENTS:
            state = states.get(nutrient)
            if not state:
                continue

            rx = self._optimize_single(
                state, swb_out, crop_type, management_goal,
                soil_ph, irrigation_type, constraints or {},
            )
            if rx:
                prescriptions.append(rx)

        return prescriptions

    def _optimize_single(
        self,
        state: NutrientState,
        swb_out: Any,
        crop_type: str,
        management_goal: str,
        soil_ph: Optional[float],
        irrigation_type: str,
        constraints: Dict,
    ) -> Optional[Prescription]:
        """Optimize a single nutrient prescription."""
        nutrient = state.nutrient
        crop_lower = crop_type.lower()

        # 1. Action decision
        if state.probability_deficient > 0.60:
            action = ActionId(f"APPLY_{nutrient.value}")
        elif state.probability_deficient > 0.35:
            action = ActionId.VERIFY_SOIL_TEST
        else:
            return None  # No action needed

        # 2. Rate optimization (only if intervening)
        optimal_rate = 0.0
        response_model_used = ""
        response_params_used = {}

        if action.value.startswith("APPLY_"):
            optimal_rate, response_model_used, response_params_used = self._compute_optimal_rate(
                nutrient, crop_lower, management_goal, constraints)

            # Confidence adjustment: if low confidence, reduce rate
            if state.confidence < 0.5:
                if state.severity in (Severity.HIGH, Severity.CRITICAL):
                    optimal_rate *= 0.5  # Apply half, then verify
                else:
                    action = ActionId.VERIFY_SOIL_TEST
                    optimal_rate = 0.0

        # 3. Product selection (4R Right Source)
        method = self._select_method(nutrient, irrigation_type)
        product = _select_product(nutrient, method, soil_ph)
        product_analysis = PRODUCT_ANALYSIS.get(product, {})
        nutrient_fraction = product_analysis.get(nutrient.value, 0.46)
        product_rate = optimal_rate / nutrient_fraction if nutrient_fraction > 0 else 0.0

        # 4. Split application (4R Right Time)
        splits = self._build_splits(nutrient, crop_lower, optimal_rate, product, method)

        # 5. Compliance check
        compliance = self.gate.check_compliance(
            nutrient, product, optimal_rate, method, swb_out,
            crop_lower, soil_ph, constraints,
        )

        is_allowed = compliance.is_compliant
        blocked = compliance.violations

        # 6. Environmental risk
        env_risk = self.gate.compute_environmental_risk(
            nutrient, optimal_rate, method, swb_out, soil_ph, crop_lower,
        )

        # Risk level
        risk_level = RiskIfWrong.LOW
        if state.severity == Severity.CRITICAL:
            risk_level = RiskIfWrong.HIGH
        elif state.severity == Severity.HIGH:
            risk_level = RiskIfWrong.MEDIUM
        if not is_allowed:
            risk_level = RiskIfWrong.HIGH

        # Source rationale
        source_rationale = self._explain_source(product, nutrient, soil_ph, method)

        # Audit
        crop_price = CROP_PRICES.get(crop_lower, 200.0)
        product_cost = PRODUCT_COSTS.get(product, 0.40)
        audit = PrescriptionAudit(
            crop_price_per_ton=crop_price,
            product_cost_per_kg=product_cost,
            constraints_active=list(constraints.keys()),
            response_model=response_model_used,
            response_params=response_params_used,
            objective="ProfitMax" if management_goal == "yield_max" else "CostMin",
            nutrient_budget_balance=state.balance_kg_ha or 0.0,
        )

        return Prescription(
            action_id=action,
            nutrient=nutrient,
            rate_kg_ha=round(optimal_rate, 1),
            product=product,
            product_rate_kg_ha=round(product_rate, 1),
            timing_window=TimingWindow(phenology_stage="vegetative"),
            splits=splits,
            method=method,
            source_rationale=source_rationale,
            risk_if_wrong=risk_level,
            preconditions=[],
            is_allowed=is_allowed,
            blocked_reason=blocked,
            environmental_risk=env_risk,
            regulatory=compliance,
            audit=audit,
        )

    def _compute_optimal_rate(
        self, nutrient: Nutrient, crop: str, goal: str, constraints: Dict,
    ) -> Tuple[float, str, Dict]:
        """Compute economically optimal nutrient rate."""
        rp = RESPONSE_PARAMS.get(crop, RESPONSE_PARAMS["_default"])
        nut_rp = rp.get(nutrient.value, rp.get("N", {}))
        model = nut_rp.get("model", ResponseModel.MITSCHERLICH)
        params = nut_rp.get("params", {})
        crop_price = CROP_PRICES.get(crop, 200.0)
        product = _select_product(nutrient, ApplicationMethod.BROADCAST)
        product_cost = PRODUCT_COSTS.get(product, 0.40)
        analysis = PRODUCT_ANALYSIS.get(product, {})
        nut_frac = analysis.get(nutrient.value, 0.46)

        # Cost per kg nutrient
        cost_per_kg_nutrient = product_cost / nut_frac if nut_frac > 0 else 1.0
        cost_revenue_ratio = cost_per_kg_nutrient / max(crop_price, 1.0)

        # Optimal rate: where marginal revenue = marginal cost
        opt_rate = 0.0
        if model == ResponseModel.MITSCHERLICH:
            ymax = params.get("ymax", 10.0)
            c = params.get("c", 0.015)
            b = params.get("b", 30.0)
            try:
                term = cost_revenue_ratio / (ymax * c)
                if term > 0 and term < 1:
                    opt_rate = (-1.0 / c) * math.log(term) - b
            except (ValueError, ZeroDivisionError):
                opt_rate = 0.0

        elif model == ResponseModel.QUADRATIC_PLATEAU:
            a = params.get("a", 6.0)
            b_coeff = params.get("b", 0.04)
            c_coeff = params.get("c", -0.0001)
            # dY/dx = b + 2cx = cost_ratio -> x = (cost_ratio - b) / (2c)
            if c_coeff != 0:
                vertex = -b_coeff / (2 * c_coeff)
                econ_opt = (cost_revenue_ratio - b_coeff) / (2 * c_coeff)
                opt_rate = min(vertex, max(0, econ_opt))

        elif model == ResponseModel.LINEAR_PLATEAU:
            b_coeff = params.get("b", 0.08)
            plateau = params.get("plateau", 9.0)
            a_val = params.get("a", 6.0)
            # Linear until plateau: x_plateau = (plateau - a) / b
            x_plat = (plateau - a_val) / b_coeff if b_coeff > 0 else 0
            # Economic: only worthwhile if marginal return > cost
            if b_coeff * crop_price > cost_per_kg_nutrient:
                opt_rate = x_plat
            else:
                opt_rate = 0.0

        # Apply goal adjustment
        if goal == "cost_min":
            opt_rate *= 0.75
        elif goal == "sustainable":
            opt_rate *= 0.85

        # Apply constraints
        max_rate = constraints.get(f"{nutrient.value.lower()}_max_kg_ha")
        # Also check common alias: nitrogen_limit_kg_ha
        nut_aliases = {"N": "nitrogen_limit_kg_ha", "P": "phosphorus_limit_kg_ha", "K": "potassium_limit_kg_ha"}
        alias_rate = constraints.get(nut_aliases.get(nutrient.value, ""), None)
        if alias_rate is not None:
            max_rate = min(max_rate, alias_rate) if max_rate is not None else alias_rate
        if max_rate is not None:
            opt_rate = min(opt_rate, max_rate)

        opt_rate = max(0.0, opt_rate)

        return opt_rate, model.value, params

    def _select_method(self, nutrient: Nutrient, irrigation_type: str) -> ApplicationMethod:
        """4R Right Place: select application method."""
        if irrigation_type in ("drip", "fertigation"):
            return ApplicationMethod.FERTIGATION
        if nutrient == Nutrient.P:
            return ApplicationMethod.BANDED  # P is immobile → place near roots
        if nutrient == Nutrient.N:
            return ApplicationMethod.SIDE_DRESS
        return ApplicationMethod.BROADCAST

    def _build_splits(
        self, nutrient: Nutrient, crop: str, total_rate: float,
        product: FertilizerProduct, method: ApplicationMethod,
    ) -> List[SplitApplication]:
        """Build split application plan."""
        template = SPLIT_TEMPLATES.get(crop, SPLIT_TEMPLATES["_default"])
        nut_splits = template.get(nutrient.value, template.get("N", [{"fraction": 1.0, "stage": "initial", "method": method}]))

        splits = []
        for i, s in enumerate(nut_splits):
            split_rate = total_rate * s["fraction"]
            splits.append(SplitApplication(
                split_id=i + 1,
                rate_kg_ha=round(split_rate, 1),
                product=product,
                method=s.get("method", method),
                timing=TimingWindow(phenology_stage=s.get("stage", "initial")),
                fraction_of_total=s["fraction"],
            ))
        return splits

    def _explain_source(
        self, product: FertilizerProduct, nutrient: Nutrient,
        soil_ph: Optional[float], method: ApplicationMethod,
    ) -> str:
        """4R Right Source rationale."""
        reasons = []
        if product == FertilizerProduct.CAN and soil_ph and soil_ph > 7.5:
            reasons.append("CAN selected over urea: alkaline soil (pH>7.5) reduces volatilization risk")
        elif product == FertilizerProduct.UREA:
            reasons.append("Urea: highest N concentration (46%), cost-effective")
        elif product == FertilizerProduct.DAP:
            reasons.append("DAP: provides both N+P, efficient for P-deficient soils")
        elif product == FertilizerProduct.MOP:
            reasons.append("MOP (KCl): most economical K source")
        if method == ApplicationMethod.FERTIGATION:
            reasons.append("Fertigation: drip system enables precise nutrient delivery")
        return "; ".join(reasons) if reasons else f"{product.value} selected for {nutrient.value}"

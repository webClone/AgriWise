"""
Layer 4.2: Crop Demand & Uptake Engine — Multi-crop science.

Computes N/P/K demand curves for 11 crops using published nutrient
removal rates and phenology-aware uptake patterns.

Science:
  - Nutrient removal: IPNI (2014) crop nutrient removal database
  - Uptake curves: Ciampitti & Vyn (2012) for corn N, adapted for others
  - Yield targets: attainable × management goal factor
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Mapping
import math

from layer4_nutrients.schema import CropDemandOutput
from crop_database import get_crop, CROP_REGISTRY


# ============================================================================
# Nutrient Removal Rates & Attainable Yields
# Now sourced from centralized crop_database (209+ crops)
# ============================================================================

def _get_removal_rates(crop_type: str) -> Dict[str, float]:
    """Get N/P/K removal rates (kg/ton product) from centralized registry."""
    spec = get_crop(crop_type)
    return {"N": spec.removal_n, "P": spec.removal_p, "K": spec.removal_k}


def _get_attainable_yield(crop_type: str) -> float:
    """Get attainable yield (t/ha) from centralized registry."""
    return get_crop(crop_type).attainable_yield_t_ha


# Management goal → yield fraction
GOAL_YIELD_FACTOR = {
    "yield_max": 1.0,
    "cost_min": 0.85,
    "sustainable": 0.80,
}

# Uptake fraction by stage end (cumulative)
# Based on Ciampitti & Vyn (2012) for corn, adapted for other crops
UPTAKE_CURVES = {
    "corn": {
        "initial":      {"N": 0.02, "P": 0.05, "K": 0.02},
        "vegetative":   {"N": 0.55, "P": 0.45, "K": 0.65},
        "reproductive": {"N": 0.90, "P": 0.85, "K": 1.00},
        "maturity":     {"N": 1.00, "P": 1.00, "K": 1.00},
        "senescence":   {"N": 1.00, "P": 1.00, "K": 1.00},
    },
    "wheat": {
        "initial":      {"N": 0.03, "P": 0.05, "K": 0.03},
        "vegetative":   {"N": 0.60, "P": 0.50, "K": 0.70},
        "reproductive": {"N": 0.92, "P": 0.88, "K": 1.00},
        "maturity":     {"N": 1.00, "P": 1.00, "K": 1.00},
        "senescence":   {"N": 1.00, "P": 1.00, "K": 1.00},
    },
    # Default for unlisted crops
    "_default": {
        "initial":      {"N": 0.03, "P": 0.05, "K": 0.03},
        "vegetative":   {"N": 0.55, "P": 0.45, "K": 0.60},
        "reproductive": {"N": 0.90, "P": 0.85, "K": 0.95},
        "maturity":     {"N": 1.00, "P": 1.00, "K": 1.00},
        "senescence":   {"N": 1.00, "P": 1.00, "K": 1.00},
    },
}


class CropDemandUptakeEngine:
    """Computes N/P/K demand curves and critical windows."""

    def compute_demand(
        self,
        crop_type: str,
        stages: List[str],
        management_goal: str = "yield_max",
        yield_override: Optional[float] = None,
    ) -> CropDemandOutput:
        """Compute nutrient demand from crop type + phenology stages."""

        crop_lower = crop_type.lower()
        n_days = len(stages)

        # 1. Yield target
        attainable = _get_attainable_yield(crop_type)
        goal_factor = GOAL_YIELD_FACTOR.get(management_goal, 1.0)
        yield_target = yield_override if yield_override else attainable * goal_factor

        # 2. Total demand
        removal = _get_removal_rates(crop_type)
        total_demand = {
            nut: round(rate * yield_target, 1)
            for nut, rate in removal.items()
        }

        # 3. Uptake curves
        curve = UPTAKE_CURVES.get(crop_lower, UPTAKE_CURVES["_default"])
        cumulative = {"N": [], "P": [], "K": []}

        for day_idx in range(n_days):
            stage = stages[day_idx].lower() if day_idx < len(stages) else "maturity"
            stage_frac = curve.get(stage, curve.get("vegetative", {}))

            for nut in ["N", "P", "K"]:
                frac = stage_frac.get(nut, 0.5)
                cum_kg = frac * total_demand.get(nut, 0)
                cumulative[nut].append(round(cum_kg, 2))

        # Enforce monotonicity
        for nut in ["N", "P", "K"]:
            for i in range(1, len(cumulative[nut])):
                cumulative[nut][i] = max(cumulative[nut][i], cumulative[nut][i-1])

        # 4. Daily uptake (derivative)
        daily_uptake = {"N": [], "P": [], "K": []}
        for nut in ["N", "P", "K"]:
            prev = 0.0
            for val in cumulative[nut]:
                daily_uptake[nut].append(round(max(0, val - prev), 3))
                prev = val

        # 5. Peak daily demand
        peak_daily = {}
        for nut in ["N", "P", "K"]:
            peak_daily[nut] = max(daily_uptake[nut]) if daily_uptake[nut] else 0.0

        # 6. Critical windows (top 20% uptake days)
        critical_windows = []
        for nut in ["N", "P", "K"]:
            if not daily_uptake[nut]:
                continue
            threshold = peak_daily[nut] * 0.5
            window_start = None
            for i, du in enumerate(daily_uptake[nut]):
                if du >= threshold and window_start is None:
                    window_start = i
                elif du < threshold and window_start is not None:
                    stage_at_start = stages[window_start].lower() if window_start < len(stages) else "unknown"
                    stage_at_end = stages[min(i, len(stages)-1)].lower() if i < len(stages) else "unknown"
                    critical_windows.append({
                        "nutrient": nut,
                        "stage": f"{stage_at_start}-{stage_at_end}",
                        "day_start": window_start,
                        "day_end": i,
                        "demand_pct": round(
                            sum(daily_uptake[nut][window_start:i]) / max(1, total_demand.get(nut, 1)) * 100, 1
                        ),
                    })
                    window_start = None

        return CropDemandOutput(
            crop_type=crop_lower,
            yield_target_t_ha=round(yield_target, 1),
            total_demand=total_demand,
            cumulative_uptake=cumulative,
            critical_windows=critical_windows,
            peak_daily_demand=peak_daily,
        )

    def compute_posterior_demand(
        self,
        *,
        stages: List[str],
        semantic_lineage: Mapping[str, Any],
        management_goal: str = "yield_max",
    ) -> CropDemandOutput:
        """Marginalize crop demand over canonical crop/stage hypotheses.

        This path deliberately avoids ``get_crop('unknown')`` because the
        registry's compatibility fallback is wheat.  Group-only and unknown
        identity are represented as mixtures with explicit variance.
        """
        def normalise(raw: Any) -> Dict[str, float]:
            if not isinstance(raw, Mapping):
                return {}
            values: Dict[str, float] = {}
            for key, value in raw.items():
                try:
                    probability = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(probability) and probability > 0.0:
                    values[str(key).lower()] = probability
            total = sum(values.values())
            return ({key: value / total for key, value in values.items()}
                    if total > 0.0 else {})

        crop_mix = normalise(semantic_lineage.get("crop_mixture"))
        species_allowed = bool(semantic_lineage.get("species_specific_allowed"))
        crop_resolution = str(semantic_lineage.get("crop_resolution") or "unknown")
        selected_crop = str(semantic_lineage.get("selected_crop") or "").lower()
        if species_allowed and selected_crop and not crop_mix:
            crop_mix = {selected_crop: 1.0}
        elif not species_allowed and crop_resolution == "group_only":
            expanded: Dict[str, float] = {}
            for group, weight in crop_mix.items():
                matches = [
                    code for code, spec in CROP_REGISTRY.items()
                    if str(spec.architecture).lower() == group
                ]
                for code in matches:
                    expanded[code] = expanded.get(code, 0.0) + weight / max(1, len(matches))
            crop_mix = normalise(expanded)
        if not crop_mix:
            representatives: Dict[str, str] = {}
            for code, spec in CROP_REGISTRY.items():
                representatives.setdefault(str(spec.architecture).lower(), code)
            crop_mix = normalise({code: 1.0 for code in representatives.values()})

        stage_mix = normalise(semantic_lineage.get("stage_posterior"))
        stage_allowed = bool(semantic_lineage.get("stage_specific_allowed"))
        selected_stage = str(semantic_lineage.get("phenology_stage") or "").lower()
        if stage_allowed and selected_stage and not stage_mix:
            stage_mix = {selected_stage: 1.0}
        if not stage_mix:
            stage_mix = {
                "initial": 0.20, "vegetative": 0.30,
                "reproductive": 0.30, "maturity": 0.20,
            }

        # A stage hypothesis is repeated over the requested horizon.  It is a
        # scenario branch, never a newly inferred stage.
        horizon = max(1, len(stages))
        components = []
        component_weights: Dict[str, float] = {}
        for crop_code, crop_weight in crop_mix.items():
            if crop_code not in CROP_REGISTRY:
                continue
            for stage, stage_weight in stage_mix.items():
                weight = crop_weight * stage_weight
                result = self.compute_demand(
                    crop_type=crop_code,
                    stages=[stage] * horizon,
                    management_goal=management_goal,
                )
                key = f"{crop_code}:{stage}"
                components.append((weight, result))
                component_weights[key] = weight
        if not components:
            raise ValueError("no compatible crop hypotheses for nutrient demand")

        total_weight = sum(weight for weight, _ in components) or 1.0
        component_weights = {
            key: value / total_weight for key, value in component_weights.items()
        }
        nutrients = ("N", "P", "K")
        means: Dict[str, float] = {}
        variances: Dict[str, float] = {}
        bounds: Dict[str, tuple] = {}
        cumulative = {nut: [0.0] * horizon for nut in nutrients}
        peaks = {nut: 0.0 for nut in nutrients}
        yield_mean = 0.0
        for weight, result in components:
            w = weight / total_weight
            yield_mean += w * result.yield_target_t_ha
            for nutrient in nutrients:
                values = [item.total_demand[nutrient] for _, item in components]
                means[nutrient] = sum(
                    (item_weight / total_weight) * item.total_demand[nutrient]
                    for item_weight, item in components
                )
                for day in range(horizon):
                    cumulative[nutrient][day] += w * result.cumulative_uptake[nutrient][day]
                peaks[nutrient] += w * result.peak_daily_demand[nutrient]
                bounds[nutrient] = (min(values), max(values))
        for nutrient in nutrients:
            variances[nutrient] = sum(
                (weight / total_weight)
                * (result.total_demand[nutrient] - means[nutrient]) ** 2
                for weight, result in components
            )

        evidence_class = (
            "species_stage_posterior" if species_allowed and stage_allowed
            else "group_stage_mixture" if crop_resolution == "group_only"
            else "generic_bounded_mixture"
        )
        return CropDemandOutput(
            crop_type=(selected_crop if species_allowed else crop_resolution),
            yield_target_t_ha=round(yield_mean, 2),
            total_demand={key: round(value, 2) for key, value in means.items()},
            cumulative_uptake={
                key: [round(value, 2) for value in values]
                for key, values in cumulative.items()
            },
            critical_windows=[],
            peak_daily_demand={key: round(value, 3) for key, value in peaks.items()},
            demand_variance={key: round(value, 3) for key, value in variances.items()},
            demand_bounds={
                key: (round(value[0], 2), round(value[1], 2))
                for key, value in bounds.items()
            },
            crop_stage_evidence_class=evidence_class,
            crop_posterior_hash=str(semantic_lineage.get("crop_posterior_hash") or ""),
            phenology_posterior_hash=str(semantic_lineage.get("phenology_posterior_hash") or ""),
            hypothesis_weights=component_weights,
            production_eligible=species_allowed and stage_allowed,
        )

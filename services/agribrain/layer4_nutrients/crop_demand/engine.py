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

from typing import Any, Dict, List, Optional

from layer4_nutrients.schema import CropDemandOutput


# ============================================================================
# Nutrient Removal Rates (kg nutrient per ton grain/product)
# Source: IPNI, FAO, regional calibration
# ============================================================================

REMOVAL_RATES = {
    #              N      P2O5→P    K2O→K
    "corn":     {"N": 15.0, "P": 3.5, "K": 4.0},
    "wheat":    {"N": 22.0, "P": 4.0, "K": 5.0},
    "soybean":  {"N": 55.0, "P": 5.5, "K": 14.0},  # High N from fixation
    "rice":     {"N": 14.0, "P": 2.8, "K": 3.0},
    "cotton":   {"N": 50.0, "P": 10.0, "K": 15.0},  # Per ton lint
    "barley":   {"N": 18.0, "P": 3.5, "K": 5.0},
    "potato":   {"N": 3.5,  "P": 0.5, "K": 5.5},    # Per ton tuber
    "sorghum":  {"N": 16.0, "P": 3.0, "K": 3.5},
    "alfalfa":  {"N": 27.0, "P": 2.5, "K": 22.0},   # Per ton DM
    "canola":   {"N": 35.0, "P": 6.0, "K": 8.0},
    "sunflower": {"N": 30.0, "P": 7.0, "K": 12.0},
}

# Attainable yield (t/ha) by crop under good conditions
ATTAINABLE_YIELD = {
    "corn": 12.0, "wheat": 7.0, "soybean": 4.0, "rice": 8.0,
    "cotton": 1.5, "barley": 6.0, "potato": 40.0, "sorghum": 8.0,
    "alfalfa": 12.0, "canola": 3.5, "sunflower": 3.0,
}

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
        attainable = ATTAINABLE_YIELD.get(crop_lower, 8.0)
        goal_factor = GOAL_YIELD_FACTOR.get(management_goal, 1.0)
        yield_target = yield_override if yield_override else attainable * goal_factor

        # 2. Total demand
        removal = REMOVAL_RATES.get(crop_lower, REMOVAL_RATES["corn"])
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

"""
AgriBrain V53 Crop-Stage-Aware Dynamic Resolution Policy Selector.

Determines the finest defensible spatial resolution dynamically per Sentinel-2
scene acquisition based on plot geometry, crop growth stage, and quality gates.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


class CropStageAwareSelector:
    """
    AgriBrain V53/V54/V55 Crop-Stage-Aware Dynamic Resolution Policy Selector.
    
    Uses V52 stage-level baseline stability profiles to dynamically promote
    or downgrade spatial enhancement resolutions depending on current scene conditions.
    Supports external validation hooks registry.
    """
    
    def __init__(self):
        self.registered_hooks = {
            "drone_orthomosaic": {"registered": True, "data_available": False, "validation_passed": False},
            "gnss_boundary": {"registered": True, "data_available": False, "validation_passed": False},
            "rtk_field_boundary": {"registered": True, "data_available": False, "validation_passed": False}
        }

    def check_external_confidence_boost(self) -> bool:
        """
        Gates confidence boost strictly. Only allowed if hook is registered,
        data is present, and validation passes.
        """
        boost_allowed = False
        for name, hook in self.registered_hooks.items():
            if hook.get("registered") and hook.get("data_available") and hook.get("validation_passed"):
                boost_allowed = True
                break
        return boost_allowed

    # V52 stage-level baseline stability profiles (mode resolution and stability rate)
    STABILITY_PROFILES = {
        "v50b_oued_souf_10ha": {
            "peak_growth": {"mode_resolution_m": 5, "stability_rate_pct": 100.0},
            "senescence": {"mode_resolution_m": 5, "stability_rate_pct": 100.0},
            "harvest_fallow": {"mode_resolution_m": 10, "stability_rate_pct": 60.0} # unstable 5m at 40%
        },
        "v50b_timimoun_20ha": {
            "peak_growth": {"mode_resolution_m": 3, "stability_rate_pct": 100.0},
            "senescence": {"mode_resolution_m": 3, "stability_rate_pct": 90.0},
            "harvest_fallow": {"mode_resolution_m": 3, "stability_rate_pct": 60.0} # unstable 3m/5m
        },
        "v50b_boufarik_30ha": {
            "peak_growth": {"mode_resolution_m": 5, "stability_rate_pct": 100.0},
            "senescence": {"mode_resolution_m": 5, "stability_rate_pct": 80.0},
            "harvest_fallow": {"mode_resolution_m": 10, "stability_rate_pct": 100.0}
        }
    }

    @staticmethod
    def current_quality_gates_pass(m: Dict[str, float]) -> bool:
        """
        Enforces standard production quality gates.
        """
        if not m:
            return False
        return (
            m.get("global_gain_pct", 0.0) >= 3.0
            and m.get("local_high_confidence_gain_pct", 0.0) >= 5.0
            and m.get("critical_zone_degradation_pct", 0.0) >= -5.0
            and m.get("fallback_fraction", 1.0) < 0.70
            and m.get("mean_uncertainty", 1.0) <= 0.15
            and m.get("coverage_pct", 0.0) >= 70.0
        )

    @staticmethod
    def exceptional_quality_gates_pass(m: Dict[str, float]) -> bool:
        """
        Enforces stricter exceptional quality gates for unstable crop stages.
        """
        if not m:
            return False
        return (
            m.get("global_gain_pct", 0.0) >= 5.0
            and m.get("local_high_confidence_gain_pct", 0.0) >= 7.5
            and m.get("critical_zone_degradation_pct", 0.0) >= -3.0
            and m.get("fallback_fraction", 1.0) < 0.50
            and m.get("mean_uncertainty", 1.0) <= 0.10
        )

    @staticmethod
    def one_meter_certified_pass(crop_stage: str, geometry_mode: str, m: Dict[str, float], m1m_stability_rate: float) -> bool:
        """
        Enforces strict V54 conditional 1m certification gates.
        """
        if not m:
            return False
            
        # 1. Crop stage is peak_growth or strong senescence, not harvest/fallow
        if crop_stage not in {"peak_growth", "senescence"}:
            return False
            
        # 2. Geometry mode is compatible: pivot_prior or rectangular_parcel
        if geometry_mode not in {"pivot_prior", "rectangular_parcel"}:
            return False
            
        # 3. Global gain vs strongest temporal baseline >= 5%
        # 4. Local high-confidence gain >= 8%
        # 5. Critical zone degradation >= -2%
        # 6. Mean uncertainty <= 0.08
        # 7. Fallback fraction < 35%
        # 8. Valid in-plot coverage >= 85%
        # 9. 1m stability rate over recent/Monte Carlo runs >= 80%
        return (
            m.get("global_gain_pct", 0.0) >= 5.0
            and m.get("local_high_confidence_gain_pct", 0.0) >= 8.0
            and m.get("critical_zone_degradation_pct", 0.0) >= -2.0
            and m.get("mean_uncertainty", 1.0) <= 0.08
            and m.get("fallback_fraction", 1.0) < 0.35
            and m.get("coverage_pct", 0.0) >= 85.0
            and m1m_stability_rate >= 80.0
        )

    def select_resolution(
        self,
        plot_id: str,
        crop_stage: str,
        current_metrics_by_res: Dict[int, Dict[str, float]],
        allow_conditional_1m_certified_export: bool = False,
        geometry_mode: str = "generic_polygon",
        m1m_stability_rate: float = 0.0
    ) -> Tuple[int, str]:
        """
        Dynamically selects the best resolution (1m, 2m, 3m, 5m, 10m) based on
        stage-level stability and current scene conditions.
        """
        # 1. Check conditional 1m certification gate if enabled
        if allow_conditional_1m_certified_export:
            metrics_1m = current_metrics_by_res.get(1)
            if metrics_1m and self.one_meter_certified_pass(crop_stage, geometry_mode, metrics_1m, m1m_stability_rate):
                return 1, "certified_conditional_one_meter_promotion_passed_gates"

        # Default fallback floor
        selected_res = 10
        reason = "default_temporal_fallback_floor"

        profile = self.STABILITY_PROFILES.get(plot_id)
        if not profile:
            return selected_res, "unknown_plot_id"

        stage_profile = profile.get(crop_stage)
        if not stage_profile:
            return selected_res, "unknown_crop_stage"

        stage_mode_res = stage_profile["mode_resolution_m"]
        stability_rate = stage_profile["stability_rate_pct"]

        # Enforce the crop-stage-aware active policy
        if stability_rate >= 80.0:
            # Stage mode resolution has a stable stage-level baseline
            if stage_mode_res == 10:
                selected_res = 10
                reason = "stage_stable_fallback_floor"
            else:
                metrics = current_metrics_by_res.get(stage_mode_res)
                if self.current_quality_gates_pass(metrics):
                    selected_res = stage_mode_res
                    reason = f"stage_stable_resolution_passed_gates_{stage_mode_res}m"
                else:
                    selected_res = 10
                    reason = f"stage_stable_resolution_failed_gates_fallback_{stage_mode_res}m_to_10m"
        else:
            # Unstable stage, allow promotion only if exceptional gates pass
            promoted = False
            # Check resolutions from finest to coarsest
            for r in [2, 3, 5]:
                metrics = current_metrics_by_res.get(r)
                if self.exceptional_quality_gates_pass(metrics):
                    selected_res = r
                    reason = f"stage_unstable_exceptional_promotion_passed_gates_{r}m"
                    promoted = True
                    break
            if not promoted:
                selected_res = 10
                reason = "stage_unstable_failed_exceptional_gates_fallback_to_10m"

        return selected_res, reason

"""
AgriBrain V56 Ground Truth Scoring Engine.

Implements the Source Authority Hierarchy and resolves conflicts across multi-source evidence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from ground_truth.schemas import GroundTruthEvidence


class SourceAuthorityScorer:
    """
    Scorer that evaluates and ranks sources according to domain precedence,
    resolving conflicting claims about spatial detail, crop stage, and water/stress.
    """

    SPATIAL_HIERARCHY = [
        "drone_orthomosaic",
        "rtk_field_boundary",
        "gnss_boundary",
        "ip_camera",
        "farmer_photo",
        "satellite_microzone"
    ]

    CROP_STAGE_HIERARCHY = [
        "farmer_input",
        "ip_camera",
        "farmer_photo",
        "satellite_phenology"
    ]

    WATER_STRESS_HIERARCHY = [
        "iot_sensor",
        "farmer_input",
        "satellite_ndmi_proxy",
        "farmer_photo"
    ]

    @classmethod
    def resolve_spatial_resolution(
        cls, 
        evidences: List[GroundTruthEvidence], 
        satellite_res: float,
        registry_decision: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Determines the authoritative spatial resolution from multi-source evidence.
        """
        three_cm_allowed = True
        one_meter_allowed = True

        if registry_decision:
            cert_decision = registry_decision.get("certification_decision", {})
            three_cm_allowed = cert_decision.get("three_cm_external_layer_allowed", True)
            one_meter_allowed = cert_decision.get("one_meter_advisory_certified", True)

        best_ev = None
        best_rank = len(cls.SPATIAL_HIERARCHY)

        for ev in evidences:
            if ev.source_type in cls.SPATIAL_HIERARCHY:
                # If drone is not allowed or failed QA, skip it
                if ev.source_type == "drone_orthomosaic":
                    if not three_cm_allowed:
                        continue
                    if ev.resolution_m is None or ev.resolution_m > 0.03:
                        continue
                    if ev.payload_ref and "rmse_" in ev.payload_ref:
                        try:
                            rmse = float(ev.payload_ref.split("rmse_")[1])
                            if rmse > 0.20:
                                continue
                        except Exception:
                            pass

                rank = cls.SPATIAL_HIERARCHY.index(ev.source_type)
                if rank < best_rank:
                    best_rank = rank
                    best_ev = ev

        if best_ev and best_ev.resolution_m is not None:
            return {
                "resolution_m": best_ev.resolution_m,
                "resolution_origin": best_ev.resolution_origin or "external_ground_truth",
                "resolution_role": best_ev.resolution_role or "validation_anchor",
                "source": best_ev.source_type,
                "state_update_allowed": best_ev.state_update_allowed
            }

        # If 1m satellite resolution is not certified, degrade it to 10m fallback floor
        if satellite_res == 1.0 and not one_meter_allowed:
            satellite_res = 10.0

        # Fallback to satellite derived
        return {
            "resolution_m": satellite_res,
            "resolution_origin": "satellite_derived",
            "resolution_role": "certified_advisory_visual_layer" if satellite_res == 1.0 else "production_state",
            "source": "satellite_microzone",
            "state_update_allowed": False if satellite_res in {1.0, 0.03} else True
        }

    @classmethod
    def resolve_crop_stage(cls, evidences: List[GroundTruthEvidence], satellite_stage: str) -> str:
        """
        Determines the authoritative crop stage from multi-source evidence.
        """
        best_ev = None
        best_rank = len(cls.CROP_STAGE_HIERARCHY)

        for ev in evidences:
            if "crop_stage" in ev.validation_targets and ev.source_type in cls.CROP_STAGE_HIERARCHY:
                rank = cls.CROP_STAGE_HIERARCHY.index(ev.source_type)
                if rank < best_rank:
                    best_rank = rank
                    best_ev = ev

        if best_ev and best_ev.payload_ref:
            # We assume crop stage is stored in payload_ref or validation payload
            return best_ev.payload_ref
        
        return satellite_stage

    @classmethod
    def evaluate_water_stress_consistency(
        cls, 
        evidences: List[GroundTruthEvidence], 
        satellite_claims_stress: bool
    ) -> Dict[str, Any]:
        """
        Validates if satellite-derived water stress claims are consistent with ground truth.
        For example: if claims_water_stress but soil moisture sensors indicate high moisture,
        reduces confidence or blocks the zone.
        """
        anomaly_detected = False
        block_zone = False
        message = "Consistent"

        # IoT soil moisture is the primary authority
        iot_evs = [ev for ev in evidences if ev.source_type == "iot_sensor" and "water_stress" in ev.validation_targets]
        
        if iot_evs and satellite_claims_stress:
            # If any moisture sensor claims HIGH moisture (e.g. payload_ref == "high_moisture")
            for ev in iot_evs:
                if ev.payload_ref == "high_moisture":
                    anomaly_detected = True
                    block_zone = True
                    message = "Conflict: Satellite claims water stress, but IoT soil moisture is high."
                    break

        return {
            "anomaly_detected": anomaly_detected,
            "block_zone": block_zone,
            "message": message
        }

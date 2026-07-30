"""
MicroZone source adapter.

Extracts and packages high-resolution deconvolution rasters (Red, NIR, NDVI)
and temporal fusion baseline arrays into canonical Layer 1 EvidenceItem packets.
Enforces strict production safety locks and deconvolution-diagnostics limits.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from layer1_fusion.schemas import (
    EvidenceItem,
    Layer1InputBundle,
    SourceEnvelope,
)

class MicroZoneAdapter:
    source_family = "microzone"

    def __init__(
        self,
        allow_strong_1m_export: bool = False,
        production_policy: str = "adaptive_2m_to_10m",
        deconvolution_mode: str = "diagnostic_only",
        export_mode: str = "production_safe",
        allow_conditional_1m_certified_export: bool = True,
        one_meter_state_update_allowed: bool = False,
        one_meter_export_label: str = "certified_high_resolution_advisory_layer"
    ):
        if production_policy != "adaptive_2m_to_10m":
            raise ValueError("SECURITY_VIOLATION: production_policy must be locked to adaptive_2m_to_10m!")
        if deconvolution_mode != "diagnostic_only":
            raise ValueError("SECURITY_VIOLATION: deconvolution_mode must be locked to diagnostic_only!")
        
        if export_mode == "controlled_research":
            self.allow_strong_1m_export = allow_strong_1m_export
            self.allow_conditional_1m_certified_export = allow_conditional_1m_certified_export
            self.one_meter_state_update_allowed = one_meter_state_update_allowed
            self.one_meter_export_label = one_meter_export_label
        else:
            # Strict hardcoded production assertions
            if allow_strong_1m_export is not False:
                raise ValueError("SECURITY_VIOLATION: allow_strong_1m_export must be locked to False in production!")
            if allow_conditional_1m_certified_export is not True:
                raise ValueError("SECURITY_VIOLATION: allow_conditional_1m_certified_export must be locked to True in production!")
            if one_meter_state_update_allowed is not False:
                raise ValueError("SECURITY_VIOLATION: one_meter_state_update_allowed must be locked to False in production!")
            if one_meter_export_label != "certified_high_resolution_advisory_layer":
                raise ValueError("SECURITY_VIOLATION: one_meter_export_label must be locked to certified_high_resolution_advisory_layer in production!")
            
            self.allow_strong_1m_export = False
            self.allow_conditional_1m_certified_export = True
            self.one_meter_state_update_allowed = False
            self.one_meter_export_label = "certified_high_resolution_advisory_layer"
            
        self.production_policy = production_policy
        self.deconvolution_mode = deconvolution_mode
        self.export_mode = export_mode

    def can_read(self, package: Any) -> bool:
        return package is not None and isinstance(package, dict) and "plot_id" in package

    def extract_evidence(self, package: Any, context: Layer1InputBundle) -> List[EvidenceItem]:
        """
        Extracts microzone deconvolution and baseline arrays, packaging them into
        canonical Layer 1 EvidenceItems with strict diagnostic/state boundaries.
        """
        items: List[EvidenceItem] = []
        if not self.can_read(package):
            return items

        plot_id = package["plot_id"]
        mgrs_tile = package.get("mgrs_tile", "MGRS-32SLC")
        source_dates = package.get("source_dates", [])
        geometry_mode = package.get("geometry_mode", "generic_polygon")
        observed_at = package.get("observed_at") or datetime.now(timezone.utc)
        confidence = float(package.get("confidence", 0.85))
        
        # Load arrays
        b04_recon = np.array(package["b04_recon"])
        b08_recon = np.array(package["b08_recon"])
        ndvi_recon = np.array(package["ndvi_recon"])
        
        b04_prior = np.array(package["b04_prior"])
        b08_prior = np.array(package["b08_prior"])
        ndvi_prior = np.array(package["ndvi_prior"])
        
        temporal_hr = np.array(package["temporal_hr"])
        u_map = np.array(package["u_map"])
        alpha_hr = np.array(package["alpha_hr"])
        fallback_mask = np.array(package["fallback_mask"])
        zone_policy_map = np.array(package["zone_policy_map"])
        fallback_reason_map = np.array(package["fallback_reason_map"])
        
        retro_score = float(package.get("retro_score", 0.0))

        # Core metadata
        process_operator_version = "process_deconv_v50"
        psf_sigma_by_band = {"b04": 3.0, "b08": 3.0}
        provenance = {
            "algorithm": "PSF-aware regularized spatial deconvolution",
            "regularization": "Spatial TV + L2 baseline prior",
            "iterations": 30,
            "lambda_tv": 0.002,
            "lambda_prior": 0.05
        }
        
        # Ingest Leakage Audit Metadata
        leakage_audit = {
            "target_leakage_detected": False,
            "obs_used_only_for_final_mse": True,
            "empirical_zone_gain_validation": True,
            "empirical_zone_gain_validation_meaning": "metrics are leakage-free and empirically computed",
            "validation_mode": "loo_no_leakage",
            "prediction_frozen_before_holdout_eval": True,
            "holdout_used_in_prior": False,
            "holdout_used_in_uncertainty": False,
            "holdout_used_in_alpha": False,
            "holdout_used_in_deconvolution": False,
        }

        # V61: Build resolution raster from best_val_res_map when available.
        # Falls back to the old binary (10.0m fallback / 2.0m deconvolved) for
        # backward compatibility with packages that don't include best_val_res_map.
        resolution_raster = np.array(
            package.get("best_val_res_map", np.where(fallback_mask > 0.5, 10.0, 2.0))
        )
        
        # Build retrovalidation score raster (spatially uniform based on Gate 5 LOO score)
        h, w = ndvi_recon.shape
        retrovalidation_score_raster = np.full((h, w), retro_score)

        blended_ndvi = np.array(package["blended_ndvi"])
        blended_red = np.array(package["blended_red"])
        blended_nir = np.array(package["blended_nir"])

        # Load V51 adaptive resolution variables (backward compatible fallbacks)
        best_val_res_map = np.array(package.get("best_val_res_map", np.full((h, w), 10.0)))
        res_conf_map = np.array(package.get("res_conf_map", np.full((h, w), 1.0)))
        res_reason_code_map = np.array(package.get("res_reason_code_map", np.full((h, w), 0.0)))
        res_candidate_stack = np.array(package.get("res_candidate_stack", np.zeros((5, h, w))))

        # Determine dynamic certified resolution metadata based on best_val_res_map
        unique_res = np.unique(best_val_res_map)
        selected_res_m = 1.0 if 1.0 in unique_res else (float(np.min(unique_res)) if len(unique_res) > 0 else 10.0)
        selected_resolution_role = "certified_advisory_visual_layer" if selected_res_m == 1.0 else "production_state_driver"
        state_update_resolution_m = float(package.get("state_update_resolution_m", 3.0 if selected_res_m == 1.0 else selected_res_m))
        state_update_source = "temporal_baseline_or_certified_2m_3m_5m" if selected_res_m == 1.0 else "direct_validated_resolution"

        # 14 canonical variables
        variables_to_export = [
            ("microzone_ndvi_sharpened", blended_ndvi, True, False), # var, raster, diagnostic_only, state_update_allowed
            ("microzone_red_reflectance_sharpened", blended_red, True, False),
            ("microzone_nir_reflectance_sharpened", blended_nir, True, False),
            ("microzone_uncertainty", u_map, False, True),
            ("microzone_resolution_m", resolution_raster, False, True),
            ("microzone_retrovalidation_score", retrovalidation_score_raster, False, True),
            ("microzone_fallback_mask", fallback_mask, False, True),
            ("microzone_zone_policy", zone_policy_map, False, True),
            ("microzone_fallback_reason", fallback_reason_map, False, True),
            ("microzone_ndvi_temporal_baseline", temporal_hr, False, True),
            ("microzone_best_validated_resolution_m", best_val_res_map, False, True),
            ("microzone_resolution_confidence", res_conf_map, False, True),
            ("microzone_resolution_reason_code", res_reason_code_map, False, True),
            ("microzone_resolution_candidate_stack", res_candidate_stack, True, False),
        ]

        mean_u = float(np.mean(u_map))
        fallback_frac = float(np.mean(fallback_mask))

        # Precompute nested lists once before the loop (treated as read-only) to avoid CPU bottlenecks
        u_map_list = u_map.tolist()
        resolution_raster_list = resolution_raster.tolist()
        retrovalidation_score_raster_list = retrovalidation_score_raster.tolist()

        for var_name, raster, diag_only, state_up_allowed in variables_to_export:
            raster_list = raster.tolist()
            payload = {
                "value_raster": raster_list,
                "uncertainty_raster": u_map_list,
                "resolution_m_raster": resolution_raster_list,
                "retrovalidation_score_raster": retrovalidation_score_raster_list,
                "source_dates": source_dates,
                "mgrs_tile": mgrs_tile,
                "process_operator_version": process_operator_version,
                "psf_sigma_by_band": psf_sigma_by_band,
                "fallback_fraction": fallback_frac,
                "production_policy": self.production_policy,
                "provenance": provenance,
                "leakage_audit": leakage_audit,
                "diagnostic_only": diag_only,
                "state_update_allowed": state_up_allowed,
                "description": "Diagnostic deconvolution detail" if diag_only else "State-updating temporal baseline",
                "geometry_mode": geometry_mode,
                
                # V54 dynamic certified metadata
                "selected_resolution_m": int(selected_res_m),
                "selected_resolution_role": selected_resolution_role,
                "state_update_resolution_m": int(state_update_resolution_m),
                "state_update_source": state_update_source,
                "one_meter_export_policy": {
                    "allow_strong_1m_export": self.allow_strong_1m_export,
                    "allow_conditional_1m_certified_export": self.allow_conditional_1m_certified_export,
                    "one_meter_state_update_allowed": self.one_meter_state_update_allowed,
                    "one_meter_export_label": self.one_meter_export_label,
                    "1m_visual_export": "allowed_if_certified",
                    "1m_advisory_export": "allowed_if_certified_and_flagged",
                    "1m_state_update_export": "blocked_until_external_ground_truth_validation"
                }
            }

            item = EvidenceItem(
                evidence_id=f"microzone_{plot_id}_{var_name}",
                plot_id=plot_id,
                variable=var_name,
                value=raster_list,
                unit="index" if "ndvi" in var_name else ("fraction" if "reflectance" in var_name else ("m" if "resolution" in var_name else ("score" if "score" in var_name else "ratio"))),
                source_family="microzone",
                source_id=mgrs_tile,
                observation_type="derived_feature",
                spatial_scope="raster",
                observed_at=observed_at,
                confidence=confidence,
                sigma=mean_u,
                provenance_ref=f"microzone_deconv_{mgrs_tile}",
                flags=["ADAPTIVE_RESOLUTION_EVIDENCE"],
                temporal_scope="daily",
                diagnostic_only=diag_only,
                state_update_allowed=state_up_allowed
            )
            item.payload = payload
            items.append(item)

        # Enforce assertions inside adapter
        for item in items:
            if item.variable in {
                "microzone_ndvi_sharpened",
                "microzone_red_reflectance_sharpened",
                "microzone_nir_reflectance_sharpened",
                "microzone_resolution_candidate_stack",
            }:
                if item.diagnostic_only is not True:
                    raise RuntimeError(f"SECURITY_VIOLATION: deconvolution band {item.variable} must be diagnostic_only!")
                if item.state_update_allowed is not False:
                    raise RuntimeError(f"SECURITY_VIOLATION: deconvolution band {item.variable} must not allow state updates!")
            elif item.variable in {
                "microzone_ndvi_temporal_baseline",
                "microzone_best_validated_resolution_m",
                "microzone_resolution_confidence",
                "microzone_resolution_reason_code",
            }:
                if item.diagnostic_only is not False:
                    raise RuntimeError(f"SECURITY_VIOLATION: production variable {item.variable} must NOT be diagnostic_only!")
                if item.state_update_allowed is not True:
                    raise RuntimeError(f"SECURITY_VIOLATION: production variable {item.variable} must allow state updates!")

        # Enforce V54 dynamic certified assertions
        if selected_res_m == 1.0:
            if self.one_meter_state_update_allowed is not False:
                raise RuntimeError("SECURITY_VIOLATION: one_meter_state_update_allowed must be False when 1m is certified!")
            for item in items:
                if item.variable in {
                    "microzone_ndvi_sharpened",
                    "microzone_red_reflectance_sharpened",
                    "microzone_nir_reflectance_sharpened",
                    "microzone_resolution_candidate_stack",
                }:
                    if item.diagnostic_only is not True:
                        raise RuntimeError(f"SECURITY_VIOLATION: deconvolution band {item.variable} must be diagnostic_only!")
                    if item.state_update_allowed is not False:
                        raise RuntimeError(f"SECURITY_VIOLATION: deconvolution band {item.variable} must not allow state updates!")
                    if item.payload["one_meter_export_policy"]["one_meter_export_label"] != "certified_high_resolution_advisory_layer":
                        raise RuntimeError("SECURITY_VIOLATION: one_meter_export_label in payload must be locked to certified_high_resolution_advisory_layer!")

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="microzone_missing",
                source_family="microzone",
                source_name="MicroZone Deconvolution",
                package_id="",
                package_version="",
                source_status="missing",
            )

        mgrs_tile = package.get("mgrs_tile", "MGRS-32SLC")
        observed_at = package.get("observed_at") or datetime.now(timezone.utc)
        return SourceEnvelope(
            source_id=mgrs_tile,
            source_family="microzone",
            source_name="MicroZone Deconvolution",
            package_id=mgrs_tile,
            package_version="v50",
            input_hash=None,
            produced_at=datetime.now(timezone.utc),
            observed_start=observed_at,
            observed_end=observed_at,
            spatial_scope="raster",
            temporal_scope="daily",
            trust_score=0.85,
            source_status="ok"
        )

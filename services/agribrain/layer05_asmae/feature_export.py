# -*- coding: utf-8 -*-
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional

# ── Per-feature derivation metadata ───────────────────────────────────────────
# Each state variable has a known derivation chain and expected weight when
# derived from proxy composites instead of a real Layer 05 EnKF run.
# confidence = quality of the derivation (0–1)
# weight     = how much downstream formulas should trust this feature (0–1)
#              weight=0 when a feature is unavailable.
_FEATURE_PROXY_META: Dict[str, Dict[str, Any]] = {
    # Strongly correlated to NDVI → reasonable proxy
    "vigor":                   {"source": "ndvi_proxy",   "confidence": 0.55, "weight": 0.55},
    "lai":                     {"source": "ndvi_proxy",   "confidence": 0.50, "weight": 0.50},
    # Red-edge / chlorophyll index required — moderate proxy quality
    "chlorophyll":             {"source": "reip_proxy",   "confidence": 0.35, "weight": 0.35},
    # NDMI required — reasonable proxy when NDMI exists
    "canopy_water":            {"source": "ndmi_proxy",   "confidence": 0.45, "weight": 0.45},
    # Thermal required — not derivable from optical composites
    "root_zone_water":         {"source": "sar_proxy",    "confidence": 0.30, "weight": 0.30},
    "surface_wetness_event":   {"source": "sar_proxy",    "confidence": 0.30, "weight": 0.30},
    # BSI / bare soil index
    "structure":               {"source": "ndvi_proxy",   "confidence": 0.40, "weight": 0.40},
    "bare_soil_fraction":      {"source": "bsi_proxy",    "confidence": 0.38, "weight": 0.38},
    # Very low quality from proxies
    "salinity_stress":         {"source": "unknown_proxy","confidence": 0.20, "weight": 0.20},
    "thermal_stress":          {"source": "unknown_proxy","confidence": 0.15, "weight": 0.15},
    "biotic_confounder_risk":  {"source": "unknown_proxy","confidence": 0.15, "weight": 0.15},
    "phenology_progress":      {"source": "ndvi_proxy",   "confidence": 0.40, "weight": 0.40},
    "stress_memory":           {"source": "unknown_proxy","confidence": 0.18, "weight": 0.18},
    # Diagnostic features
    "confidence":              {"source": "derived",      "confidence": 0.60, "weight": 0.60},
    "uncertainty":             {"source": "derived",      "confidence": 0.60, "weight": 0.60},
    "bma_disagreement":        {"source": "derived",      "confidence": 0.50, "weight": 0.50},
    "cross_layer_conflict":    {"source": "derived",      "confidence": 0.45, "weight": 0.45},
    "retrovalidation_score":   {"source": "derived",      "confidence": 0.55, "weight": 0.55},
    "archive_support":         {"source": "derived",      "confidence": 0.55, "weight": 0.55},
    "ml_support":              {"source": "derived",      "confidence": 0.50, "weight": 0.50},
    "causal_support":          {"source": "derived",      "confidence": 0.40, "weight": 0.40},
    "radiometric_support":     {"source": "derived",      "confidence": 0.50, "weight": 0.50},
    "enkf_support":            {"source": "derived",      "confidence": 0.55, "weight": 0.55},
}

_REAL_ENKF_WEIGHT = 0.90
_REAL_ENKF_CONFIDENCE = 0.90

_STATE_FEATURES = {
    "vigor",
    "lai",
    "chlorophyll",
    "canopy_water",
    "root_zone_water",
    "surface_wetness_event",
    "structure",
    "bare_soil_fraction",
    "salinity_stress",
    "thermal_stress",
    "biotic_confounder_risk",
    "phenology_progress",
    "stress_memory",
}

_PRIOR_ONLY_WITHOUT_STATE_LEDGER = {
    "salinity_stress",
    "thermal_stress",
    "biotic_confounder_risk",
    "phenology_progress",
    "stress_memory",
}


def build_state_support_ledger(update_reports: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build state truth exclusively from explicit accepted/excluded update reports."""
    ledger: Dict[str, Dict[str, Any]] = {
        state: {
            "state": state,
            "support_status": "prior_constrained",
            "observation_relationship": "none",
            "source_feature_ids": [],
            "accepted_update_count": 0,
            "direct_observation_count": 0,
            "indirect_observation_count": 0,
            "proxy_observation_count": 0,
            "field_approval_eligible": False,
            "spatial_support": "microzone_grid",
            "authority_ceiling": "DIAGNOSTIC",
            "block_reasons": ["no_accepted_state_update"],
            "accepted_updates": [],
            "excluded_updates": [],
        }
        for state in sorted(_STATE_FEATURES)
    }

    for report in update_reports or []:
        if not isinstance(report, dict):
            continue
        target_states = [state for state in report.get("target_states", []) if state in ledger]
        if not target_states:
            continue

        accepted = report.get("update_applied") is True
        source_reality = str(report.get("source_reality", "unknown") or "unknown")
        real_provider = bool(report.get("real_provider_product", False))
        real_source = real_provider and source_reality in {
            "real_raster", "real_provider_raster", "provider_observation",
        }
        reported_kind = str(report.get("evidence_kind", "unknown"))
        if accepted and real_source and reported_kind == "direct_observation":
            evidence_kind = "direct_observation"
        elif accepted and real_source and reported_kind == "indirect_observation":
            evidence_kind = "indirect_observation"
        elif accepted:
            evidence_kind = "proxy_observation"
        else:
            evidence_kind = "excluded"

        for state in target_states:
            entry = ledger[state]
            if not accepted:
                entry["excluded_updates"].append({
                    "scene_id": report.get("scene_id"),
                    "timestamp": report.get("timestamp"),
                    "observation_feature": report.get("obs_name"),
                    "update_mode": report.get("mode"),
                    "exclusion_reason": report.get("failure_reason", "update_not_applied"),
                })
                continue

            update_record = {
                "scene_id": report.get("scene_id"),
                "timestamp": report.get("timestamp"),
                "observation_feature": report.get("obs_name"),
                "sensor": report.get("sensor"),
                "update_mode": report.get("mode"),
                "evidence_kind": evidence_kind,
                "source_reality": source_reality,
                "innovation": report.get("innovation_mean"),
                "observation_noise_sigma": report.get("sigma_obs"),
                "valid_pixel_count": report.get("n_pixels", 0),
                "kalman_gain": report.get("kalman_gain_summary"),
                "prior_variance": (report.get("prior_variance") or {}).get(state),
                "posterior_variance": (report.get("posterior_variance") or {}).get(state),
                "information_gain": (report.get("information_gain") or {}).get(state),
                "information_gain_fraction": (report.get("information_gain_fraction") or {}).get(state),
            }
            entry["accepted_updates"].append(update_record)
            entry["accepted_update_count"] += 1
            count_key = {
                "direct_observation": "direct_observation_count",
                "indirect_observation": "indirect_observation_count",
                "proxy_observation": "proxy_observation_count",
            }[evidence_kind]
            entry[count_key] += 1

    for entry in ledger.values():
        if entry["direct_observation_count"] > 0:
            entry["support_status"] = "assimilated"
            entry["observation_relationship"] = "direct"
            entry["field_approval_eligible"] = True
        elif entry["indirect_observation_count"] > 0:
            entry["support_status"] = "assimilated"
            entry["observation_relationship"] = "indirect"
        elif entry["proxy_observation_count"] > 0:
            entry["support_status"] = "assimilated"
            entry["observation_relationship"] = "proxy"
        if entry["accepted_update_count"] > 0:
            entry["block_reasons"] = []
        entry["source_feature_ids"] = sorted({
            str(update["observation_feature"])
            for update in entry["accepted_updates"]
            if update.get("observation_feature")
        })
    return ledger


def export_asmae_feature_pack(output: Any) -> Dict[str, Any]:
    """
    Creates a canonical ASMAEFeaturePack from the ASMAEOutput.

    BC.10.13 P3 — per-feature truth:
    Every feature now carries its own status, source, confidence, and weight
    instead of sharing a single binary real/proxy_derived classification.
    Downstream consumers must check weight > 0 before using any feature.
    """
    raster_maps = getattr(output, "raster_maps", {}) or {}
    uncertainty_maps = getattr(output, "uncertainty_maps", {}) or {}
    confidence_maps = getattr(output, "confidence_maps", {}) or {}
    retrovalidation_maps = getattr(output, "retrovalidation_maps", {}) or {}
    bma_maps = getattr(output, "bma_maps", {}) or {}
    diagnostics = getattr(output, "diagnostics", {}) or {}
    grid_spec = getattr(output, "grid_spec", {}) or {}
    ev_state = getattr(output, "asmae_evidence_state", {}) or {}

    real_ev = ev_state.get("real_asmae_evidence", False)
    state_support_ledger = diagnostics.get("state_support_ledger", {}) or {}

    # Helper to extract 2-D list from multiple possible key names
    def get_grid(maps, *keys) -> Optional[list]:
        for k in keys:
            if k in maps and maps[k] is not None:
                return maps[k]
        return None

    # ── State variables ────────────────────────────────────────────────────────
    state_vigor          = get_grid(raster_maps, "vigor",                  "ASMAE_VIGOR")
    state_lai            = get_grid(raster_maps, "lai",                    "ASMAE_LAI")
    state_chlorophyll    = get_grid(raster_maps, "chlorophyll",            "ASMAE_CHLOROPHYLL")
    state_canopy_water   = get_grid(raster_maps, "canopy_water",           "ASMAE_CANOPY_WATER")
    state_root_zone_water= get_grid(raster_maps, "root_zone_water",        "ASMAE_ROOT_ZONE_WATER")
    state_surface_wetness= get_grid(raster_maps, "surface_wetness_event",  "ASMAE_SURFACE_WETNESS_EVENT")
    state_structure      = get_grid(raster_maps, "structure",              "ASMAE_STRUCTURE")
    state_bare_soil      = get_grid(raster_maps, "bare_soil_fraction",     "ASMAE_BARE_SOIL_FRACTION")
    state_salinity       = get_grid(raster_maps, "salinity_stress",        "ASMAE_SALINITY_STRESS")
    state_thermal        = get_grid(raster_maps, "thermal_stress",         "ASMAE_THERMAL_STRESS")
    state_biotic         = get_grid(raster_maps, "biotic_confounder_risk", "ASMAE_BIOTIC_CONFOUNDER_RISK")
    state_phenology      = get_grid(raster_maps, "phenology_progress",     "ASMAE_PHENOLOGY_PROGRESS")
    state_stress_memory  = get_grid(raster_maps, "stress_memory",          "ASMAE_STRESS_MEMORY")

    # ── Diagnostic support maps ────────────────────────────────────────────────
    diag_confidence   = get_grid(confidence_maps,      "ASMAE_CONFIDENCE",            "confidence")
    diag_uncertainty  = get_grid(uncertainty_maps,     "ASMAE_UNCERTAINTY",           "uncertainty")
    diag_bma          = get_grid(bma_maps,             "ASMAE_BMA_DISAGREEMENT",      "bma_disagreement")
    diag_cross_layer  = get_grid(raster_maps,          "cross_layer_conflict",        "ASMAE_CROSS_LAYER_CONFLICT")
    diag_retro        = get_grid(retrovalidation_maps, "ASMAE_RETROVALIDATION_SCORE", "retro_score")
    diag_archive      = get_grid(confidence_maps,      "ASMAE_ARCHIVE_SUPPORT",       "archive_support")
    diag_ml           = get_grid(bma_maps,             "ASMAE_ML_AGREEMENT",          "ml_support")
    diag_causal       = get_grid(raster_maps,          "causal_support",              "ASMAE_CAUSAL_SUPPORT")
    diag_radiometric  = get_grid(retrovalidation_maps, "ASMAE_RADIOMETRIC_SUPPORT",   "radiometric_support")
    diag_enkf         = get_grid(retrovalidation_maps, "ASMAE_ENKF_SUPPORT",          "enkf_support")

    # ── Resolution masks ───────────────────────────────────────────────────────
    res_eff  = (get_grid(diagnostics, "effective_resolution_map")
                or get_grid(raster_maps, "effective_resolution", "COMPOSITE_EFFECTIVE_RESOLUTION"))
    res_1m   = get_grid(diagnostics, "one_meter_advisory_mask")
    res_2_5m = get_grid(diagnostics, "model_assisted_2_5m_mask")
    res_5m   = get_grid(diagnostics, "generalized_5m_mask")

    # ── Grid shape ─────────────────────────────────────────────────────────────
    H = grid_spec.get("height", len(state_vigor) if state_vigor else 0)
    W = grid_spec.get("width",  len(state_vigor[0]) if (state_vigor and len(state_vigor) > 0) else 0)

    # ── Authority pack ─────────────────────────────────────────────────────────
    authority_pack = {
        "source_reality":               ev_state.get("source_reality", "raster_composite_proxy"),
        "scene_stack_mode":             ev_state.get("scene_stack_mode", "unavailable"),
        "real_asmae_evidence":          real_ev,
        "composite_advisory_allowed":   ev_state.get("composite_advisory_allowed", False),
        "current_1m_approval_allowed":  ev_state.get("current_1m_approval_allowed", False),
        "state_update_allowed":         ev_state.get("state_update_allowed", False),
    }

    feature_formula_versions = diagnostics.get("feature_formula_versions", {})

    # ── BC.10.13 P3 — per-feature truth ───────────────────────────────────────
    def check_per_feature_status(grid_val, feature_name: str) -> Dict[str, Any]:
        """
        Returns a per-feature status dict:
          status     : "real" | "proxy_derived" | "unavailable"
          source     : where the value came from
          confidence : derivation quality (0–1); 0.0 when unavailable
          weight     : downstream formula weight (0–1); 0.0 when unavailable
        """
        formula_ver = {}
        feat_to_band = {
            "vigor": "NDVI",
            "canopy_water": "NDMI",
            "structure": "NDWI",
            "bare_soil_fraction": "BSI",
            "chlorophyll": "REIP"
        }
        mapped_band = feat_to_band.get(feature_name)
        if mapped_band and mapped_band in feature_formula_versions:
            formula_ver[mapped_band] = feature_formula_versions[mapped_band]

        if grid_val is None:
            return {
                "status": "unavailable",
                "source": None,
                "confidence": 0.0,
                "weight": 0.0,
                "source_kind": "unavailable",
                "usable_for_field_approval": False,
                "usable_for_advisory": False,
                "usable_for_visual_only": False,
                "feature_formula_versions": {},
            }

        is_state_var = feature_name in _STATE_FEATURES
        if is_state_var:
            state_support = state_support_ledger.get(feature_name, {})
            accepted_count = int(state_support.get("accepted_update_count", 0) or 0)
            direct_count = int(state_support.get("direct_observation_count", 0) or 0)
            indirect_count = int(state_support.get("indirect_observation_count", 0) or 0)
            proxy_count = int(state_support.get("proxy_observation_count", 0) or 0)
            if accepted_count == 0:
                return {
                    "status": "prior_constrained",
                    "source": "layer05_process_model",
                    "confidence": 0.0,
                    "weight": 0.0,
                    "source_kind": "process_model_only",
                    "usable_for_field_approval": False,
                    "usable_for_advisory": False,
                    "usable_for_visual_only": True,
                    "direct_observation_count": 0,
                    "indirect_observation_count": 0,
                    "proxy_observation_count": 0,
                    "prior_only": True,
                    "authority_block_reason": "no_accepted_state_update",
                    "state_support": state_support,
                    "feature_formula_versions": formula_ver,
                }
            if direct_count > 0 and real_ev:
                status = "real"
                source = "layer05_enkf_direct"
                source_kind = "layer05_assimilated"
                confidence = _REAL_ENKF_CONFIDENCE
                weight = _REAL_ENKF_WEIGHT
                field_approval = bool(state_support.get("field_approval_eligible", False))
            elif indirect_count > 0 and real_ev:
                status = "real"
                source = "layer05_enkf_indirect"
                source_kind = "layer05_assimilated_indirect"
                confidence = 0.65
                weight = 0.60
                field_approval = False
            else:
                meta = _FEATURE_PROXY_META.get(feature_name, {
                    "source": "proxy_observation", "confidence": 0.25, "weight": 0.25,
                })
                status = "proxy_derived"
                source = meta["source"]
                source_kind = "layer05_proxy_assimilated"
                confidence = meta["confidence"]
                weight = meta["weight"]
                field_approval = False
            return {
                "status": status,
                "source": source,
                "confidence": confidence,
                "weight": weight,
                "source_kind": source_kind,
                "usable_for_field_approval": field_approval,
                "usable_for_advisory": True,
                "usable_for_visual_only": True,
                "direct_observation_count": direct_count,
                "indirect_observation_count": indirect_count,
                "proxy_observation_count": proxy_count,
                "prior_only": False,
                "state_support": state_support,
                "feature_formula_versions": formula_ver,
            }

        if real_ev:
            if feature_name == "retrovalidation_score":
                source_kind = "real_retrovalidation_support"
            elif feature_name == "archive_support":
                source_kind = "real_archive_support"
            elif feature_name == "ml_support":
                source_kind = "ml_shadow"
            else:
                source_kind = "real_observation"
            return {
                "status": "real",
                "source": "layer05_diagnostic",
                "confidence": _REAL_ENKF_CONFIDENCE,
                "weight": _REAL_ENKF_WEIGHT,
                "source_kind": source_kind,
                "usable_for_field_approval": False,
                "usable_for_advisory": True,
                "usable_for_visual_only": True,
                "direct_observation_count": 0,
                "proxy_observation_count": 0,
                "prior_only": False,
                "feature_formula_versions": formula_ver,
            }

        # Proxy-derived: use per-feature metadata
        meta = _FEATURE_PROXY_META.get(feature_name, {
            "source": "unknown_proxy",
            "confidence": 0.25,
            "weight": 0.25,
        })
        src = meta["source"]

        if feature_name in _PRIOR_ONLY_WITHOUT_STATE_LEDGER or src == "unknown_proxy":
            return {
                "status": "unavailable",
                "source": None,
                "confidence": 0.0,
                "weight": 0.0,
                "source_kind": "unavailable",
                "usable_for_field_approval": False,
                "usable_for_advisory": False,
                "usable_for_visual_only": False,
                "direct_observation_count": 0,
                "proxy_observation_count": 0,
                "prior_only": True,
                "drop_reason": "required_evidence_family_missing",
                "feature_formula_versions": formula_ver,
            }
        
        if feature_name == "retrovalidation_score":
            source_kind = "proxy_reconstruction_stability"
        elif feature_name == "archive_support":
            source_kind = "proxy_observation_support"
        elif feature_name == "ml_support":
            source_kind = "proxy_texture_stability"
        elif feature_name == "bma_disagreement":
            source_kind = "proxy_stack_disagreement"
        elif src == "ndvi_proxy" or src == "reip_proxy" or src == "bsi_proxy":
            source_kind = "proxy_from_ndvi"
        elif src == "ndmi_proxy":
            source_kind = "proxy_from_ndmi"
        elif src == "sar_proxy":
            source_kind = "proxy_from_sar"
        elif src == "weather":
            source_kind = "weather_derived"
        elif src == "ml_shadow":
            source_kind = "ml_shadow"
        else:
            source_kind = "proxy_from_ndvi"

        if source_kind == "ml_shadow" or meta.get("confidence", 0.0) <= 0.20:
            usable_for_advisory = False
            usable_for_visual_only = True
        else:
            usable_for_advisory = True
            usable_for_visual_only = True

        return {
            "status": "proxy_derived",
            "source": src,
            "confidence": meta["confidence"],
            "weight": meta["weight"],
            "source_kind": source_kind,
            "usable_for_field_approval": False,
            "usable_for_advisory": usable_for_advisory,
            "usable_for_visual_only": usable_for_visual_only,
            "direct_observation_count": 0,
            "proxy_observation_count": 1,
            "prior_only": False,
            "feature_formula_versions": formula_ver,
        }

    status_pack = {
        "vigor":                 check_per_feature_status(state_vigor,           "vigor"),
        "lai":                   check_per_feature_status(state_lai,             "lai"),
        "chlorophyll":           check_per_feature_status(state_chlorophyll,     "chlorophyll"),
        "canopy_water":          check_per_feature_status(state_canopy_water,    "canopy_water"),
        "root_zone_water":       check_per_feature_status(state_root_zone_water, "root_zone_water"),
        "surface_wetness_event": check_per_feature_status(state_surface_wetness, "surface_wetness_event"),
        "structure":             check_per_feature_status(state_structure,        "structure"),
        "bare_soil_fraction":    check_per_feature_status(state_bare_soil,       "bare_soil_fraction"),
        "salinity_stress":       check_per_feature_status(state_salinity,        "salinity_stress"),
        "thermal_stress":        check_per_feature_status(state_thermal,         "thermal_stress"),
        "biotic_confounder_risk":check_per_feature_status(state_biotic,          "biotic_confounder_risk"),
        "phenology_progress":    check_per_feature_status(state_phenology,       "phenology_progress"),
        "stress_memory":         check_per_feature_status(state_stress_memory,   "stress_memory"),
        "confidence":            check_per_feature_status(diag_confidence,       "confidence"),
        "uncertainty":           check_per_feature_status(diag_uncertainty,      "uncertainty"),
        "bma_disagreement":      check_per_feature_status(diag_bma,              "bma_disagreement"),
        "cross_layer_conflict":  check_per_feature_status(diag_cross_layer,      "cross_layer_conflict"),
        "retrovalidation_score": check_per_feature_status(diag_retro,            "retrovalidation_score"),
        "archive_support":       check_per_feature_status(diag_archive,          "archive_support"),
        "ml_support":            check_per_feature_status(diag_ml,               "ml_support"),
        "causal_support":        check_per_feature_status(diag_causal,           "causal_support"),
        "radiometric_support":   check_per_feature_status(diag_radiometric,      "radiometric_support"),
        "enkf_support":          check_per_feature_status(diag_enkf,             "enkf_support"),
    }

    # ── Canonical ASMAEFeaturePack ─────────────────────────────────────────────
    return {
        "state": {
            "vigor":                 state_vigor,
            "lai":                   state_lai,
            "chlorophyll":           state_chlorophyll,
            "canopy_water":          state_canopy_water,
            "root_zone_water":       state_root_zone_water,
            "surface_wetness_event": state_surface_wetness,
            "structure":             state_structure,
            "bare_soil_fraction":    state_bare_soil,
            "salinity_stress":       state_salinity,
            "thermal_stress":        state_thermal,
            "biotic_confounder_risk":state_biotic,
            "phenology_progress":    state_phenology,
            "stress_memory":         state_stress_memory,
        },
        "diagnostics": {
            "confidence":          diag_confidence,
            "uncertainty":         diag_uncertainty,
            "bma_disagreement":    diag_bma,
            "cross_layer_conflict":diag_cross_layer,
            "retrovalidation_score":diag_retro,
            "archive_support":     diag_archive,
            "ml_support":          diag_ml,
            "causal_support":      diag_causal,
            "radiometric_support": diag_radiometric,
            "enkf_support":        diag_enkf,
        },
        "resolution": {
            "effective_resolution":      res_eff,
            "one_meter_mask":            res_1m,
            "model_assisted_2_5m_mask":  res_2_5m,
            "generalized_5m_mask":       res_5m,
        },
        "authority":       authority_pack,
        "state_support_ledger": state_support_ledger,
        "feature_status":  status_pack,   # now a per-feature dict, not a flat string
        "grid_spec": {
            "height":             H,
            "width":              W,
            "crs":                grid_spec.get("crs", "EPSG:4326"),
            "transform":          grid_spec.get("transform", None),
            "bounds":             grid_spec.get("bounds", None),
            "native_resolution_m":grid_spec.get("resolution_m", 10.0),
        },
    }

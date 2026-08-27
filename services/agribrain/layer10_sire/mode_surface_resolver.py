from typing import List, Dict, Any, Optional
from services.agribrain.layer10_sire.schema import SurfaceArtifact, SurfaceType

def trust_badges_for_surface(surface: Any, default_badges: Optional[List[str]] = None, threshold: float = 0.90) -> List[str]:
    """
    Authoritative resolver for surface trust badges.
    Strictly prevents 'Direct observation' unless all criteria are satisfied.
    """
    if surface is None:
        return ["Unverified grounding"]
        
    gc = getattr(surface, "grounding_class", None) or "UNIFORM"
    prov = getattr(surface, "provenance", {}) or {}
    if not isinstance(prov, dict):
        prov = {}
        
    real_prod = prov.get("real_provider_product", False)
    prod_usable = prov.get("production_usable", False)
    diag_only = prov.get("diagnostic_only", False)
    obs_ratio = getattr(surface, "observed_ratio", 0.0) or 0.0
    source_reality = str(prov.get("source_reality", "")).lower()

    if source_reality == "provider_temporal_composite_raster":
        return ["Provider temporal composite"]
    
    # Check if all conditions for direct observation are met
    if (
        gc == "RASTER_GROUNDED"
        and real_prod is True
        and prod_usable is True
        and diag_only is False
        and obs_ratio >= threshold
    ):
        return ["Direct observation"]
        
    if default_badges and "Direct observation" in default_badges:
        return ["Unverified grounding"]
        
    if default_badges:
        return default_badges
        
    # Derive fallback badges
    st = getattr(surface, "semantic_type", getattr(surface, "type", ""))
    if hasattr(st, "value"):
        st = st.value
    st = str(st)
    
    if st == "EXPERIMENTAL_VISUAL_CANOPY":
        return ["experimental"]
    if st == "ASMAE_VISUAL_FUSION_CANOPY":
        return ["Visual Fusion"]
    if st == "COMPOSITE_ADVISORY_CANOPY":
        return ["Composite Advisory"]
    if st == "CANOPY_ASMAE_VIGOR":
        return ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
    if prov.get("source_class") == "asmae_diagnostic" or prov.get("source_reality") == "raster_composite_proxy":
        return ["ASMAE diagnostic", "not direct observation"]
    if gc in ("UNIFORM", "BROADCAST"):
        return ["plot-level estimate"]
    if gc == "PROXY_SPATIAL":
        return ["scouting hint"]
        
    return ["Unverified grounding"]

def resolve_mode_surface_plan(
    surfaces: List[SurfaceArtifact],
    engines: Optional[List[Any]] = None,
    source_policy: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Authoritatively resolve the best available surface/model source for each map mode.
    Implements the Canonical Mode Fallback Matrix.
    """
    # Filter surfaces by source_policy
    if source_policy == "satellite":
        surfaces = [
            s for s in surfaces 
            if "ASMAE" not in (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)) 
            and "EXPERIMENTAL" not in (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type))
        ]
    elif source_policy == "experimental":
        surfaces = [
            s for s in surfaces 
            if "ASMAE" not in (s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type))
        ]

    surface_map = {}
    for s in surfaces:
        st_val = s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)
        surface_map[st_val] = s

    # Parse engines status
    engine_status = {}
    if engines:
        for eng in engines:
            eng_id = getattr(eng, "id", getattr(eng, "engine_id", None)) or eng.get("id") if isinstance(eng, dict) else None
            eng_status = getattr(eng, "status", None) or eng.get("status") if isinstance(eng, dict) else None
            if eng_id and eng_status:
                engine_status[str(eng_id).upper()] = str(eng_status).upper()

    def is_spatial(s: Optional[SurfaceArtifact]) -> bool:
        if not s:
            return False
        vals = getattr(s, "values", None)
        if vals and isinstance(vals, (list, tuple)) and len(vals) > 0:
            first_row = vals[0]
            if isinstance(first_row, (list, tuple)) and len(first_row) > 0:
                return True
        gc = getattr(s, "grounding_class", "UNIFORM") or "UNIFORM"
        if gc not in ["UNIFORM", "BROADCAST"]:
            return True
        return False

    plan = {}
    prefer_asmae = source_policy in ("asmae_diagnostic", "hybrid")

    # Get composite surfaces
    s_comp = surface_map.get("COMPOSITE_ADVISORY_CANOPY")
    s_comp_veg = surface_map.get("COMPOSITE_VEG_ATTENTION")
    s_comp_water = surface_map.get("COMPOSITE_WATER_SUPPORT")
    s_comp_nut = surface_map.get("COMPOSITE_NUTRIENT_SUPPORT")
    s_comp_sal = surface_map.get("COMPOSITE_SALINITY_STRESS")
    s_comp_risk = surface_map.get("COMPOSITE_RISK_DIAGNOSTIC")
    s_comp_conf = surface_map.get("COMPOSITE_CONFIDENCE")
    s_comp_res = surface_map.get("COMPOSITE_EFFECTIVE_RESOLUTION")

    # 1. Canopy Mode
    canopy_plan = {
        "selected_surface_type": None,
        "source_class": "unavailable",
        "spatial": False,
        "fallback_rank": 0,
        "reason": "No canopy data available",
        "trust_badges": ["no data"]
    }
    s_clean = surface_map.get("NDVI_CLEAN")
    s_alias = surface_map.get("CANOPY_ASMAE_VIGOR")
    s_fusion = surface_map.get("ASMAE_VISUAL_FUSION_CANOPY")
    s_exp = surface_map.get("EXPERIMENTAL_VISUAL_CANOPY")
    
    if source_policy == "hybrid":
        if s_fusion and is_spatial(s_fusion):
            canopy_plan = {
                "selected_surface_type": "ASMAE_VISUAL_FUSION_CANOPY",
                "source_class": "asmae",
                "spatial": True,
                "fallback_rank": 1.05,
                "reason": "Using ASMAE Visual Fusion Canopy per policy",
                "trust_badges": ["Visual Fusion", "hybrid canopy"]
            }
        elif s_comp and is_spatial(s_comp):
            canopy_plan = {
                "selected_surface_type": "COMPOSITE_ADVISORY_CANOPY",
                "source_class": "asmae",
                "spatial": True,
                "fallback_rank": 1.08,
                "reason": "Using Composite Advisory Canopy per policy",
                "trust_badges": ["Composite Advisory"]
            }
        elif s_exp and is_spatial(s_exp):
            canopy_plan = {
                "selected_surface_type": "EXPERIMENTAL_VISUAL_CANOPY",
                "source_class": "experimental",
                "spatial": True,
                "fallback_rank": 1.15,
                "reason": "Using Experimental Visual Canopy",
                "trust_badges": ["experimental"]
            }
        elif s_clean and is_spatial(s_clean):
            canopy_plan = {
                "selected_surface_type": "NDVI_CLEAN",
                "source_class": "canonical",
                "spatial": True,
                "fallback_rank": 1,
                "reason": "Canonical NDVI clean surface is available as spatial raster",
                "trust_badges": trust_badges_for_surface(s_clean, ["Direct observation"])
            }
    elif prefer_asmae:
        if s_alias and is_spatial(s_alias):
            canopy_plan = {
                "selected_surface_type": "CANOPY_ASMAE_VIGOR",
                "source_class": "asmae",
                "spatial": True,
                "fallback_rank": 1.0,
                "reason": "Using ASMAE Vigor diagnostic raster per policy",
                "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"],
                "candidate_metadata": {
                    "evidence_class": "posterior_state",
                    "accepted_updates": getattr(s_alias, "provenance", {}).get("accepted_update_count", 1) if isinstance(getattr(s_alias, "provenance", None), dict) else 1,
                    "uncertainty_valid": True,
                }
            }
        elif s_fusion and is_spatial(s_fusion):
            canopy_plan = {
                "selected_surface_type": "ASMAE_VISUAL_FUSION_CANOPY",
                "source_class": "asmae",
                "spatial": True,
                "fallback_rank": 1.05,
                "reason": "Using ASMAE Visual Fusion Canopy per policy",
                "trust_badges": ["Visual Fusion"]
            }
        elif s_comp and is_spatial(s_comp):
            canopy_plan = {
                "selected_surface_type": "COMPOSITE_ADVISORY_CANOPY",
                "source_class": "asmae",
                "spatial": True,
                "fallback_rank": 1.08,
                "reason": "Using Composite Advisory Canopy per policy",
                "trust_badges": ["Composite Advisory"]
            }
        elif s_clean and is_spatial(s_clean):
            canopy_plan = {
                "selected_surface_type": "NDVI_CLEAN",
                "source_class": "canonical",
                "spatial": True,
                "fallback_rank": 1.1,
                "reason": "Canonical NDVI clean surface is available as spatial raster",
                "trust_badges": trust_badges_for_surface(s_clean, ["Direct observation"])
            }
    elif s_clean and is_spatial(s_clean):
        canopy_plan = {
            "selected_surface_type": "NDVI_CLEAN",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 1,
            "reason": "Canonical NDVI clean surface is available as spatial raster",
            "trust_badges": trust_badges_for_surface(s_clean, ["Direct observation"])
        }
    elif not prefer_asmae and s_alias and is_spatial(s_alias):
        canopy_plan = {
            "selected_surface_type": "CANOPY_ASMAE_VIGOR",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 2,
            "reason": "NDVI_CLEAN missing; using ASMAE_VIGOR diagnostic raster",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif s_clean:  # uniform
        canopy_plan = {
            "selected_surface_type": "NDVI_CLEAN",
            "source_class": "canonical",
            "spatial": False,
            "fallback_rank": 3,
            "reason": "Canonical NDVI clean is uniform plot-level only",
            "trust_badges": ["plot-wide average"]
        }
    elif engine_status.get("L2") == "COMPLETED":
        canopy_plan = {
            "selected_surface_type": None,
            "source_class": "engine_model",
            "spatial": False,
            "fallback_rank": 4,
            "reason": "L2 completed; showing plot-level crop vigor estimate",
            "trust_badges": ["crop vigor estimate"]
        }
    plan["canopy"] = canopy_plan

    # 2. Vegetation Attention Mode
    veg_att_plan = {
        "selected_surface_type": None,
        "source_class": "unavailable",
        "spatial": False,
        "fallback_rank": 0,
        "reason": "No vegetation attention data available",
        "trust_badges": ["no data"]
    }
    s_dev = surface_map.get("NDVI_DEVIATION")
    s_base = surface_map.get("BASELINE_ANOMALY")
    # V92.4-BC.2: Canonical ASMAE veg attention aliases (preferred over raw ASMAE surfaces)
    s_veg_attn_diag = surface_map.get("VEG_ATTENTION_ASMAE_DIAGNOSTIC")
    s_veg_conflict = surface_map.get("VEG_ATTENTION_ASMAE_CONFLICT")
    s_veg_disagree = surface_map.get("VEG_ATTENTION_ASMAE_DISAGREEMENT")
    # Raw ASMAE surfaces (fallback only)
    s_bma = surface_map.get("ASMAE_BMA_DISAGREEMENT")
    s_conflict = surface_map.get("ASMAE_CROSS_LAYER_CONFLICT")
    s_vigor = surface_map.get("ASMAE_VIGOR")

    asmae_candidates = [
        ("VEG_ATTENTION_ASMAE_DIAGNOSTIC", s_veg_attn_diag, "Using ASMAE diagnostic vegetation attention composite (conflict + disagreement + uncertainty)"),
        ("VEG_ATTENTION_ASMAE_CONFLICT", s_veg_conflict, "Using ASMAE cross-layer conflict attention alias"),
        ("VEG_ATTENTION_ASMAE_DISAGREEMENT", s_veg_disagree, "Using ASMAE BMA disagreement attention alias"),
        ("ASMAE_BMA_DISAGREEMENT", s_bma, "Using raw ASMAE BMA disagreement diagnostic overlay"),
        ("ASMAE_CROSS_LAYER_CONFLICT", s_conflict, "Using raw ASMAE cross-layer conflict diagnostic overlay"),
        ("ASMAE_VIGOR", s_vigor, "Using ASMAE vigor deviation from field mean"),
        ("COMPOSITE_VEG_ATTENTION", s_comp_veg, "Using Composite Vegetation Attention"),
    ]

    selected = None
    if prefer_asmae:
        for name, s_obj, reason_text in asmae_candidates:
            if s_obj and is_spatial(s_obj):
                selected = (name, s_obj, reason_text)
                break

    if selected:
        veg_att_plan = {
            "selected_surface_type": selected[0],
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.1,
            "reason": selected[2],
            "trust_badges": ["ASMAE diagnostic", "attention mask", "not prescription driver"]
        }
    elif s_dev and is_spatial(s_dev):
        veg_att_plan = {
            "selected_surface_type": "NDVI_DEVIATION",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 1,
            "reason": "Canonical NDVI deviation surface is available",
            "trust_badges": trust_badges_for_surface(s_dev, ["Direct observation"])
        }
    elif s_base and is_spatial(s_base):
        veg_att_plan = {
            "selected_surface_type": "BASELINE_ANOMALY",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 1.5,
            "reason": "Canonical baseline anomaly is available",
            "trust_badges": trust_badges_for_surface(s_base, ["Direct observation"])
        }
    else:
        for name, s_obj, reason_text in asmae_candidates:
            if s_obj and is_spatial(s_obj):
                selected = (name, s_obj, reason_text)
                break
        if selected:
            veg_att_plan = {
                "selected_surface_type": selected[0],
                "source_class": "asmae",
                "spatial": True,
                "fallback_rank": 3,
                "reason": selected[2],
                "trust_badges": ["ASMAE diagnostic", "attention mask"]
            }
        elif engine_status.get("L2") == "COMPLETED":
            veg_att_plan = {
                "selected_surface_type": None,
                "source_class": "engine_model",
                "spatial": False,
                "fallback_rank": 5,
                "reason": "L2 completed; showing plot-level vegetation anomaly summary",
                "trust_badges": ["anomaly summary"]
            }
    plan["veg_attention"] = veg_att_plan

    # 3. Water Stress Mode
    water_plan = {
        "selected_surface_type": None,
        "source_class": "unavailable",
        "spatial": False,
        "fallback_rank": 0,
        "reason": "No water stress data available",
        "trust_badges": ["no data"]
    }
    s_water = surface_map.get("WATER_STRESS_PROB")
    s_canopy_water = surface_map.get("WATER_ASMAE_CANOPY_WATER")
    s_root_water = surface_map.get("WATER_ASMAE_ROOT_ZONE_WATER")

    if prefer_asmae and s_canopy_water and is_spatial(s_canopy_water):
        water_plan = {
            "selected_surface_type": "WATER_ASMAE_CANOPY_WATER",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.1,
            "reason": "Using ASMAE canopy-water diagnostic per policy",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif prefer_asmae and s_root_water and is_spatial(s_root_water):
        water_plan = {
            "selected_surface_type": "WATER_ASMAE_ROOT_ZONE_WATER",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.2,
            "reason": "Using ASMAE root-zone water estimate per policy",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif prefer_asmae and s_comp_water and is_spatial(s_comp_water):
        water_plan = {
            "selected_surface_type": "COMPOSITE_WATER_SUPPORT",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.08,
            "reason": "Using Composite Water Support per policy",
            "trust_badges": ["Composite Water"]
        }
    elif s_water and is_spatial(s_water):
        water_plan = {
            "selected_surface_type": "WATER_STRESS_PROB",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 1,
            "reason": "Canonical water stress probability raster available",
            "trust_badges": trust_badges_for_surface(s_water, ["Direct observation"])
        }
    elif not prefer_asmae and s_canopy_water and is_spatial(s_canopy_water):
        water_plan = {
            "selected_surface_type": "WATER_ASMAE_CANOPY_WATER",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 2,
            "reason": "WATER_STRESS_PROB missing; using ASMAE canopy-water diagnostic",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif not prefer_asmae and s_root_water and is_spatial(s_root_water):
        water_plan = {
            "selected_surface_type": "WATER_ASMAE_ROOT_ZONE_WATER",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 2.5,
            "reason": "WATER_STRESS_PROB missing; using ASMAE root-zone water estimate",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif s_water:
        water_plan = {
            "selected_surface_type": "WATER_STRESS_PROB",
            "source_class": "canonical",
            "spatial": False,
            "fallback_rank": 3,
            "reason": "Canonical water stress is uniform plot-level only",
            "trust_badges": ["plot-wide average"]
        }
    elif engine_status.get("L3") == "COMPLETED":
        water_plan = {
            "selected_surface_type": None,
            "source_class": "engine_model",
            "spatial": False,
            "fallback_rank": 4,
            "reason": "L3 completed; showing soil moisture water-balance model",
            "trust_badges": ["water deficit model"]
        }
    plan["water_stress"] = water_plan

    # 4. Nutrient Risk Mode
    nut_plan = {
        "selected_surface_type": None,
        "source_class": "unavailable",
        "spatial": False,
        "fallback_rank": 0,
        "reason": "No nutrient risk data available",
        "trust_badges": ["no data"]
    }
    s_nut = surface_map.get("NUTRIENT_STRESS_PROB")
    s_chlo = surface_map.get("NUTRIENT_ASMAE_CHLOROPHYLL_PROXY")

    if prefer_asmae and s_chlo and is_spatial(s_chlo):
        nut_plan = {
            "selected_surface_type": "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.1,
            "reason": "Using ASMAE chlorophyll proxy per policy",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif prefer_asmae and s_comp_nut and is_spatial(s_comp_nut):
        nut_plan = {
            "selected_surface_type": "COMPOSITE_NUTRIENT_SUPPORT",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.08,
            "reason": "Using Composite Nutrient Support per policy",
            "trust_badges": ["Composite Nutrient"]
        }
    elif s_nut and is_spatial(s_nut):
        nut_plan = {
            "selected_surface_type": "NUTRIENT_STRESS_PROB",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 1,
            "reason": "Canonical nutrient stress probability raster available",
            "trust_badges": trust_badges_for_surface(s_nut, ["Direct observation"])
        }
    elif not prefer_asmae and s_chlo and is_spatial(s_chlo):
        nut_plan = {
            "selected_surface_type": "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 2,
            "reason": "NUTRIENT_STRESS_PROB missing; using ASMAE chlorophyll proxy",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif s_nut:
        nut_plan = {
            "selected_surface_type": "NUTRIENT_STRESS_PROB",
            "source_class": "canonical",
            "spatial": False,
            "fallback_rank": 3,
            "reason": "Canonical nutrient stress is uniform plot-level only",
            "trust_badges": ["plot-wide average"]
        }
    elif engine_status.get("L4") == "COMPLETED":
        nut_plan = {
            "selected_surface_type": None,
            "source_class": "engine_model",
            "spatial": False,
            "fallback_rank": 4,
            "reason": "L4 completed; showing plot-level nutrient diagnosis summary",
            "trust_badges": ["nutrient model"]
        }
    plan["nutrient_risk"] = nut_plan

    # 5. Salinity Mode
    sal_plan = {
        "selected_surface_type": None,
        "source_class": "unavailable",
        "spatial": False,
        "fallback_rank": 0,
        "reason": "No salinity data available",
        "trust_badges": ["no data"]
    }
    s_sal = surface_map.get("SALINITY_STRESS")
    s_asal = surface_map.get("SALINITY_ASMAE_STRESS")

    if prefer_asmae and s_asal and is_spatial(s_asal):
        sal_plan = {
            "selected_surface_type": "SALINITY_ASMAE_STRESS",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.1,
            "reason": "Using ASMAE salinity diagnostic raster per policy",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif prefer_asmae and s_comp_sal and is_spatial(s_comp_sal):
        sal_plan = {
            "selected_surface_type": "COMPOSITE_SALINITY_STRESS",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.08,
            "reason": "Using Composite Salinity Stress per policy",
            "trust_badges": ["Composite Salinity"]
        }
    elif s_sal and is_spatial(s_sal):
        sal_plan = {
            "selected_surface_type": "SALINITY_STRESS",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 1,
            "reason": "Canonical salinity stress raster available",
            "trust_badges": trust_badges_for_surface(s_sal, ["Direct observation"])
        }
    elif not prefer_asmae and s_asal and is_spatial(s_asal):
        sal_plan = {
            "selected_surface_type": "SALINITY_ASMAE_STRESS",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 2,
            "reason": "SALINITY_STRESS missing; using ASMAE salinity diagnostic raster",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif s_sal:
        sal_plan = {
            "selected_surface_type": "SALINITY_STRESS",
            "source_class": "canonical",
            "spatial": False,
            "fallback_rank": 3,
            "reason": "Canonical salinity stress is uniform plot-level only",
            "trust_badges": ["plot-wide average"]
        }
    elif engine_status.get("L4") == "COMPLETED":
        sal_plan = {
            "selected_surface_type": None,
            "source_class": "engine_model",
            "spatial": False,
            "fallback_rank": 4,
            "reason": "L4 completed; showing plot-level salinity estimate",
            "trust_badges": ["salinity model"]
        }
    plan["salinity"] = sal_plan

    # 6. Risk Mode
    risk_plan = {
        "selected_surface_type": None,
        "source_class": "unavailable",
        "spatial": False,
        "fallback_rank": 0,
        "reason": "No risk data available",
        "trust_badges": ["no data"]
    }
    s_risk = surface_map.get("COMPOSITE_RISK")
    s_arisk = surface_map.get("RISK_ASMAE_DIAGNOSTIC")

    if prefer_asmae and s_arisk and is_spatial(s_arisk):
        risk_plan = {
            "selected_surface_type": "RISK_ASMAE_DIAGNOSTIC",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.1,
            "reason": "Using ASMAE diagnostic risk composite per policy",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif prefer_asmae and s_comp_risk and is_spatial(s_comp_risk):
        risk_plan = {
            "selected_surface_type": "COMPOSITE_RISK_DIAGNOSTIC",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.08,
            "reason": "Using Composite Risk Diagnostic per policy",
            "trust_badges": ["Composite Risk"]
        }
    elif s_risk and is_spatial(s_risk):
        risk_plan = {
            "selected_surface_type": "COMPOSITE_RISK",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 1,
            "reason": "Canonical composite risk heatmap available",
            "trust_badges": trust_badges_for_surface(s_risk, ["Direct observation"])
        }
    elif not prefer_asmae and s_arisk and is_spatial(s_arisk):
        risk_plan = {
            "selected_surface_type": "RISK_ASMAE_DIAGNOSTIC",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 2,
            "reason": "COMPOSITE_RISK missing; using ASMAE diagnostic risk composite",
            "trust_badges": ["ASMAE diagnostic", "not direct observation", "not prescription driver"]
        }
    elif engine_status.get("L5") == "COMPLETED":
        risk_plan = {
            "selected_surface_type": None,
            "source_class": "engine_model",
            "spatial": False,
            "fallback_rank": 3,
            "reason": "L5 completed; showing plot-level composite risk summary",
            "trust_badges": ["risk summary"]
        }
    plan["composite_risk"] = risk_plan

    # 7. Confidence Mode
    conf_plan = {
        "selected_surface_type": None,
        "source_class": "unavailable",
        "spatial": False,
        "fallback_rank": 0,
        "reason": "No confidence data available",
        "trust_badges": ["no data"]
    }
    s_rel = surface_map.get("DATA_RELIABILITY")
    s_conf = surface_map.get("DATA_CONFIDENCE")
    s_sigma = surface_map.get("UNCERTAINTY_SIGMA")
    s_aconf = surface_map.get("ASMAE_POSTERIOR_CONCENTRATION")

    if prefer_asmae and s_aconf and is_spatial(s_aconf):
        conf_plan = {
            "selected_surface_type": "ASMAE_POSTERIOR_CONCENTRATION",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.1,
            "reason": "Using canonical ASMAE posterior concentration per policy",
            "trust_badges": ["ASMAE diagnostic", "not direct observation"]
        }
    elif prefer_asmae and s_comp_conf and is_spatial(s_comp_conf):
        conf_plan = {
            "selected_surface_type": "COMPOSITE_CONFIDENCE",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.08,
            "reason": "Using Composite Confidence per policy",
            "trust_badges": ["Composite Confidence"]
        }
    elif s_rel and is_spatial(s_rel):
        conf_plan = {
            "selected_surface_type": "DATA_RELIABILITY",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 1,
            "reason": "Canonical data reliability surface is available",
            "trust_badges": trust_badges_for_surface(s_rel, ["Direct observation"])
        }
    elif s_conf and is_spatial(s_conf):
        conf_plan = {
            "selected_surface_type": "DATA_CONFIDENCE",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 1.5,
            "reason": "Canonical data confidence surface is available",
            "trust_badges": trust_badges_for_surface(s_conf, ["Direct observation"])
        }
    elif s_sigma and is_spatial(s_sigma):
        conf_plan = {
            "selected_surface_type": "UNCERTAINTY_SIGMA",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 2,
            "reason": "Inverting UNCERTAINTY_SIGMA for reliability",
            "trust_badges": trust_badges_for_surface(s_sigma, ["Direct observation", "inverted"])
        }
    elif not prefer_asmae and s_aconf and is_spatial(s_aconf):
        conf_plan = {
            "selected_surface_type": "ASMAE_POSTERIOR_CONCENTRATION",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 3,
            "reason": "Using canonical ASMAE posterior concentration",
            "trust_badges": ["ASMAE diagnostic", "not direct observation"]
        }
    elif engine_status.get("L2") == "COMPLETED":
        conf_plan = {
            "selected_surface_type": None,
            "source_class": "engine_model",
            "spatial": False,
            "fallback_rank": 4,
            "reason": "L2 completed; showing plot-level readiness score",
            "trust_badges": ["readiness score"]
        }
    plan["uncertainty"] = conf_plan

    # 8. Resolution Mode
    res_plan = {
        "selected_surface_type": None,
        "source_class": "unavailable",
        "spatial": False,
        "fallback_rank": 0,
        "reason": "No resolution coverage available",
        "trust_badges": ["no data"]
    }
    s_res = surface_map.get("RESOLUTION_COVERAGE")
    s_ares = surface_map.get("RESOLUTION_ASMAE_EFFECTIVE")

    if prefer_asmae and s_ares and is_spatial(s_ares):
        res_plan = {
            "selected_surface_type": "RESOLUTION_ASMAE_EFFECTIVE",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.1,
            "reason": "Using ASMAE effective resolution per policy",
            "trust_badges": ["ASMAE diagnostic", "not direct observation"]
        }
    elif prefer_asmae and s_comp_res and is_spatial(s_comp_res):
        res_plan = {
            "selected_surface_type": "COMPOSITE_EFFECTIVE_RESOLUTION",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 1.08,
            "reason": "Using Composite Effective Resolution per policy",
            "trust_badges": ["Composite Resolution"]
        }
    elif s_res and is_spatial(s_res):
        res_plan = {
            "selected_surface_type": "RESOLUTION_COVERAGE",
            "source_class": "canonical",
            "spatial": True,
            "fallback_rank": 1,
            "reason": "Canonical resolution coverage map available",
            "trust_badges": trust_badges_for_surface(s_res, ["Direct observation"])
        }
    elif not prefer_asmae and s_ares and is_spatial(s_ares):
        res_plan = {
            "selected_surface_type": "RESOLUTION_ASMAE_EFFECTIVE",
            "source_class": "asmae",
            "spatial": True,
            "fallback_rank": 2,
            "reason": "RESOLUTION_COVERAGE missing; using ASMAE effective resolution",
            "trust_badges": ["ASMAE diagnostic", "not direct observation"]
        }
    elif engine_status.get("L1") or engine_status.get("L2"):
        res_plan = {
            "selected_surface_type": None,
            "source_class": "engine_model",
            "spatial": False,
            "fallback_rank": 3,
            "reason": "Showing native sensor observation resolution metadata",
            "trust_badges": ["sensor metadata"]
        }
    plan["resolution_coverage"] = res_plan

    return plan

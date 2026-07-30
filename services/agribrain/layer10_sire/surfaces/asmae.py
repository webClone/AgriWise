"""
ASMAE Surface Generator (V82)
==============================

Generates ASMAE state and diagnostic surfaces for Layer 10 map visualization.
Enforces truthfulness-first UI gating, standard warning wordings, display trust tiers,
and blocks fake full-field broadcasts for state layers.
"""

from typing import List, Optional, Dict, Any
import numpy as np

from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId, GroundingClass,
    ASMAE_STATE_SURFACES, ASMAE_DIAGNOSTIC_SURFACES,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData

def get_standard_variable_name(stype: SurfaceType, meta_var: Optional[str] = None) -> str:
    v = (meta_var or "").lower()
    s = stype.value.lower()
    if "vigor" in v or "vigor" in s or "ndvi" in v or "ndvi" in s:
        return "vigor"
    if "water" in v or "water" in s or "canopy_water" in v or "canopy_water" in s:
        return "canopy_water"
    if "salinity" in v or "salinity" in s:
        return "salinity_stress"
    if "biotic" in v or "biotic" in s or "confounder" in v or "confounder" in s:
        return "biotic_confounder"
    return v or s


def get_surface_display_policy(
    confidence: float,
    uncertainty: float,
    resolution_m: float,
    bma_status: Optional[str],
    cross_layer_conflict: float,
    is_certified_v90: bool = False,
) -> Dict[str, Any]:
    """Determine UI display trust tier, desaturation level, alpha, and warning codes."""
    warning_codes = []

    if resolution_m <= 1.0 and not is_certified_v90:
        warning_codes.append("resolution_1m_blocked")

    if cross_layer_conflict > 0.45:
        warning_codes.append("cross_layer_conflict")

    if confidence < 0.60:
        warning_codes.append("low_confidence")

    if uncertainty > 0.40:
        warning_codes.append("high_uncertainty")

    if bma_status != "success":
        warning_codes.append("bma_not_success")

    # If no major warnings, check for mild warnings for provisional tier
    if not warning_codes:
        if (0.60 <= confidence <= 0.80) or (0.30 <= uncertainty <= 0.40):
            warning_codes.append("mild_warning")

    # Determine display trust tier based on the highest severity warning
    if "resolution_1m_blocked" in warning_codes:
        tier = "visual_only"
        desat = 0.8
        alpha = 0.8
    elif "cross_layer_conflict" in warning_codes:
        tier = "conflict"
        desat = 0.5
        alpha = 0.9
    elif "low_confidence" in warning_codes or "high_uncertainty" in warning_codes:
        tier = "diagnostic"
        desat = 1.0
        alpha = 0.7
    elif "bma_not_success" in warning_codes:
        tier = "diagnostic"
        desat = 0.8
        alpha = 0.8
    elif "mild_warning" in warning_codes:
        tier = "provisional"
        desat = 0.3
        alpha = 1.0
    else:
        tier = "trusted"
        desat = 0.0
        alpha = 1.0

    requires_warning = len(warning_codes) > 0

    return {
        "display_trust_tier": tier,
        "desaturation_level": desat,
        "alpha_multiplier": alpha,
        "requires_user_warning": requires_warning,
        "warning_codes": warning_codes,
    }


def generate_asmae_surfaces(
    inp: Layer10Input,
    H: int,
    W: int,
    l1_data: Optional[L1SpatialData] = None,
) -> List[SurfaceArtifact]:
    """Generate all registered ASMAE state and diagnostic surfaces."""
    from rollout.rollout_policy import should_render_l10_asmae
    if not should_render_l10_asmae(inp.plot_id):
        return []

    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)

    # P0-1 Check if any ASMAE input exists in raster_maps, raster_metadata, or last_values
    has_asmae_input = any(
        str(k).lower().startswith("asmae_")
        for k in (
            list(l1_data.raster_maps.keys())
            + list(l1_data.raster_metadata.keys())
            + list(l1_data.last_values.keys())
        )
    )

    if not has_asmae_input:
        return []

    surfaces = []

    # Combine state and diagnostic surfaces to process
    all_asmae_types = list(ASMAE_STATE_SURFACES) + list(ASMAE_DIAGNOSTIC_SURFACES)

    # Palette mappings
    palettes = {
        SurfaceType.ASMAE_VIGOR: PaletteId.VIGOR_GREEN,
        SurfaceType.ASMAE_LAI: PaletteId.VIGOR_GREEN,
        SurfaceType.ASMAE_CHLOROPHYLL: PaletteId.VIGOR_GREEN,
        SurfaceType.ASMAE_CANOPY_WATER: PaletteId.YIELD_BLUE,
        SurfaceType.ASMAE_ROOT_ZONE_WATER: PaletteId.YIELD_BLUE,
        SurfaceType.ASMAE_SURFACE_WETNESS_EVENT: PaletteId.YIELD_BLUE,
        SurfaceType.ASMAE_STRUCTURE: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_BARE_SOIL: PaletteId.CARBON_BROWN,
        SurfaceType.ASMAE_SALINITY_STRESS: PaletteId.SALINITY_TEAL,
        SurfaceType.ASMAE_THERMAL_STRESS: PaletteId.THERMAL_ORANGE,
        SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: PaletteId.STRESS_RED,
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_CONFIDENCE: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_UNCERTAINTY: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_RETROVALIDATION_SCORE: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_BMA_DISAGREEMENT: PaletteId.RISK_HEAT,
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: PaletteId.RISK_HEAT,
        SurfaceType.ASMAE_EXPORT_ELIGIBILITY: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_1M_ADVISORY_MASK: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_5M_GENERALIZED_MASK: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION_MAP: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_ML_AGREEMENT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_ARCHIVE_SUPPORT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_ENKF_SUPPORT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_RADIOMETRIC_SUPPORT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_VISUAL_FUSION_CANOPY: PaletteId.VIGOR_GREEN,
        SurfaceType.COMPOSITE_ADVISORY_CANOPY: PaletteId.VIGOR_GREEN,
        SurfaceType.COMPOSITE_VEG_ATTENTION: PaletteId.VIGOR_GREEN,
        SurfaceType.COMPOSITE_WATER_SUPPORT: PaletteId.YIELD_BLUE,
        SurfaceType.COMPOSITE_NUTRIENT_SUPPORT: PaletteId.VIGOR_GREEN,
        SurfaceType.COMPOSITE_SALINITY_STRESS: PaletteId.SALINITY_TEAL,
        SurfaceType.COMPOSITE_RISK_DIAGNOSTIC: PaletteId.RISK_HEAT,
        SurfaceType.COMPOSITE_CONFIDENCE: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_EFFECTIVE_RESOLUTION: PaletteId.RAW_GRAYSCALE,
        SurfaceType.COMPOSITE_UNCERTAINTY: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_BMA_DISAGREEMENT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_ARCHIVE_SUPPORT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_RETRO_SCORE: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_ML_SUPPORT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_TEXTURE_DETAIL: PaletteId.RAW_GRAYSCALE,
        SurfaceType.EXPERIMENTAL_TEXTURE_SUPPORT_MASK: PaletteId.RAW_GRAYSCALE,
    }

    # Unit mappings
    units = {
        SurfaceType.ASMAE_VIGOR: "fraction",
        SurfaceType.ASMAE_LAI: "index",
        SurfaceType.ASMAE_CHLOROPHYLL: "index",
        SurfaceType.ASMAE_CANOPY_WATER: "fraction",
        SurfaceType.ASMAE_ROOT_ZONE_WATER: "fraction",
        SurfaceType.ASMAE_SURFACE_WETNESS_EVENT: "fraction",
        SurfaceType.ASMAE_STRUCTURE: "fraction",
        SurfaceType.ASMAE_BARE_SOIL: "fraction",
        SurfaceType.ASMAE_SALINITY_STRESS: "fraction",
        SurfaceType.ASMAE_THERMAL_STRESS: "fraction",
        SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: "fraction",
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: "meters",
        SurfaceType.ASMAE_CONFIDENCE: "fraction",
        SurfaceType.ASMAE_UNCERTAINTY: "fraction",
        SurfaceType.ASMAE_RETROVALIDATION_SCORE: "fraction",
        SurfaceType.ASMAE_BMA_DISAGREEMENT: "fraction",
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: "fraction",
        SurfaceType.ASMAE_EXPORT_ELIGIBILITY: "bool",
        SurfaceType.ASMAE_1M_ADVISORY_MASK: "fraction",
        SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK: "fraction",
        SurfaceType.ASMAE_5M_GENERALIZED_MASK: "fraction",
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION_MAP: "meters",
        SurfaceType.ASMAE_ML_AGREEMENT: "fraction",
        SurfaceType.ASMAE_ARCHIVE_SUPPORT: "fraction",
        SurfaceType.ASMAE_ENKF_SUPPORT: "fraction",
        SurfaceType.ASMAE_RADIOMETRIC_SUPPORT: "fraction",
        SurfaceType.ASMAE_VISUAL_FUSION_CANOPY: "fraction",
        SurfaceType.COMPOSITE_ADVISORY_CANOPY: "fraction",
        SurfaceType.COMPOSITE_VEG_ATTENTION: "fraction",
        SurfaceType.COMPOSITE_WATER_SUPPORT: "fraction",
        SurfaceType.COMPOSITE_NUTRIENT_SUPPORT: "fraction",
        SurfaceType.COMPOSITE_SALINITY_STRESS: "fraction",
        SurfaceType.COMPOSITE_RISK_DIAGNOSTIC: "fraction",
        SurfaceType.COMPOSITE_CONFIDENCE: "fraction",
        SurfaceType.COMPOSITE_EFFECTIVE_RESOLUTION: "meters",
        SurfaceType.COMPOSITE_UNCERTAINTY: "fraction",
        SurfaceType.COMPOSITE_BMA_DISAGREEMENT: "fraction",
        SurfaceType.COMPOSITE_ARCHIVE_SUPPORT: "fraction",
        SurfaceType.COMPOSITE_RETRO_SCORE: "fraction",
        SurfaceType.COMPOSITE_ML_SUPPORT: "fraction",
        SurfaceType.COMPOSITE_TEXTURE_DETAIL: "fraction",
        SurfaceType.EXPERIMENTAL_TEXTURE_SUPPORT_MASK: "fraction",
    }

    render_ranges = {
        SurfaceType.ASMAE_LAI: (0.0, 8.0),
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: (0.03, 10.0),
    }

    for stype in all_asmae_types:
        var_name = stype.value.lower()
        
        # Look up metadata case-insensitively
        meta = {}
        for key in [var_name, var_name.upper(), var_name.lower(), stype.value]:
            if key in l1_data.raster_metadata:
                meta = l1_data.raster_metadata[key]
                break

        # Check for grid in raster_maps
        grid = None
        has_real_grid = False
        
        # Map variables to their actual raster keys in L1 raster_maps
        l1_grid_keys = [var_name, var_name.upper(), var_name.lower(), stype.value]
        # Standardize state aliases
        if stype == SurfaceType.ASMAE_BARE_SOIL:
            l1_grid_keys.extend(["asmae_bare_soil_fraction", "asmae_bare_soil", "bare_soil_fraction"])

        for key in l1_grid_keys:
            if key in l1_data.raster_maps:
                grid = l1_data.raster_maps[key]
                has_real_grid = True
                break

        # Fallback to metadata / scalar last_values
        scalar_val = None
        for key in [var_name, var_name.upper(), var_name.lower(), stype.value]:
            if key in l1_data.last_values:
                scalar_val = l1_data.last_values[key]
                break

        # P0-2 Presence Gating: Only generate if has_real_grid, has_scalar, or has_metadata
        has_grid_presence = has_real_grid
        has_scalar_presence = scalar_val is not None
        has_metadata_presence = bool(meta)

        if not (has_grid_presence or has_scalar_presence or has_metadata_presence):
            continue

        is_state_surface = stype in ASMAE_STATE_SURFACES

        if is_state_surface and not has_real_grid:
            # Rule: do not broadcast scalar fallback for state surfaces
            grid = [[None] * W for _ in range(H)]
            has_spatial_grid_flag = False
            generated_from = "metadata_fallback"
            diagnostic_only = True
            state_update_allowed = False
            visual_only = True
        else:
            has_spatial_grid_flag = True
            generated_from = "raster_maps" if has_real_grid else "metadata_fallback"
            
            if not has_real_grid:
                # Allowed to broadcast diagnostic/metadata surfaces
                val = scalar_val if scalar_val is not None else (10.0 if stype == SurfaceType.ASMAE_EFFECTIVE_RESOLUTION else 0.0)
                grid = [[val] * W for _ in range(H)]
            
            diagnostic_only = meta.get("diagnostic_only", True)
            state_update_allowed = meta.get("state_update_allowed", False)
            visual_only = False

        # Extract parameters
        confidence = float(meta.get("confidence", 0.5))
        uncertainty = float(meta.get("uncertainty", 0.1))
        resolution_m = float(meta.get("resolution_m", 10.0))
        asmae_channel = meta.get("asmae_channel", "diagnostic")
        source_basis = meta.get("source_basis", "asmae")
        c_hash = meta.get("content_hash")
        a_hash = meta.get("artifact_instance_hash")
        retro_status = meta.get("retro_status")
        retro_score = float(meta.get("retro_mean_score", meta.get("retrovalidation_score", 0.0)))
        bma_status = meta.get("bma_status")
        bma_disagreement = float(meta.get("bma_disagreement", 0.0))
        cross_layer_conflict = float(meta.get("cross_layer_conflict", 0.0))

        # Scene stack and validation parameters
        # V92.4-BC: No safe defaults. Missing proof must propagate as None
        # so asmae_surface_spatially_eligible() rejects correctly.
        scene_stack_mode = meta.get("scene_stack_mode") or meta.get("scene_stack_status_mode")
        degraded_mean_only = meta.get("degraded_mean_only", scene_stack_mode == "degraded_mean_only") if scene_stack_mode else False
        no_scenes = meta.get("no_scenes", scene_stack_mode == "no_scenes") if scene_stack_mode else False
        mean_only = meta.get("mean_only", False)
        operator_locked = meta.get("operator_locked")
        graph_locked = meta.get("graph_locked")
        radiometric_mode = meta.get("radiometric_mode")
        enkf_mode = meta.get("enkf_mode")

        # Enforce visual-only limits for 1m overlays, checking resolver for V90
        is_certified_v90 = False
        resolved_result = None
        if resolution_m <= 1.0:
            cert_id = meta.get("certification_id")
            cert_src = meta.get("certification_source")
            cert_status = meta.get("certification_status")
            
            # Map variable
            v90_var = get_standard_variable_name(stype, meta.get("variable"))
            
            # Get geometry hash and crop season
            geom_hash = ""
            if hasattr(inp, "field_tensor"):
                geom_hash = getattr(inp.field_tensor, "geometry_hash", "")
                if not geom_hash and hasattr(inp.field_tensor, "_context_package"):
                    geom_hash = getattr(inp.field_tensor._context_package, "geometry_hash", "")
            if not geom_hash:
                geom_hash = getattr(inp, "geometry_hash", "")
                
            crop_season_id = getattr(inp, "crop_season_id", "")
            if not crop_season_id and hasattr(inp, "field_tensor"):
                crop_season_id = getattr(inp.field_tensor, "crop_season_id", "")
                if not crop_season_id and hasattr(inp.field_tensor, "_context_package"):
                    crop_season_id = getattr(inp.field_tensor._context_package, "crop_season_id", "")
            if not crop_season_id:
                crop_season_id = meta.get("crop_season_id", "")

            source_hashes = {
                "layer0_output_hash": meta.get("layer0_output_hash", ""),
                "asmae_content_hash": meta.get("asmae_content_hash", ""),
                "asmae_artifact_instance_hash": meta.get("asmae_artifact_instance_hash", ""),
                "memory_content_hash": meta.get("memory_content_hash", ""),
                "report_verified_evidence_hash": meta.get("report_verified_evidence_hash", ""),
            }

            # Call V90 resolver
            from certification.v90_resolver import verify_v90_certification_record
            resolved_result = verify_v90_certification_record(
                certification_id=cert_id,
                plot_id=inp.plot_id,
                variable=v90_var,
                time_window=(meta.get("time_window_start"), meta.get("time_window_end")),
                geometry_hash=geom_hash,
                crop_season_id=crop_season_id,
                source_hashes=source_hashes
            )
            
            if cert_src == "v90" and cert_status == "certified" and cert_id and resolved_result.approved:
                is_certified_v90 = True
                
            if is_certified_v90:
                visual_only = False
                diagnostic_only = True
                state_update_allowed = False  # force-blocked!
                asmae_channel = "certified_inferred_detail"
                certification_status = "certified_inferred_detail"
            else:
                visual_only = True
                diagnostic_only = True
                state_update_allowed = False
                asmae_channel = "visual"
                certification_status = "uncertified_1m"

        # Apply display trust policy
        policy = get_surface_display_policy(
            confidence=confidence,
            uncertainty=uncertainty,
            resolution_m=resolution_m,
            bma_status=bma_status,
            cross_layer_conflict=cross_layer_conflict,
            is_certified_v90=is_certified_v90
        )

        # P0-4 Certified observation basis calculation
        native_basis = meta.get("native_observation_resolution_m", 10.0)
        certified_basis_m = meta.get("certified_basis_m", native_basis)

        # P1-1 Non-empty warning wording logic
        warning_wording = ""
        if policy["requires_user_warning"] or resolution_m <= 1.0:
            wordings = []
            if "resolution_1m_blocked" in policy["warning_codes"]:
                wordings.append("Experimental visual detail — not a direct 1m satellite observation.")
            if "cross_layer_conflict" in policy["warning_codes"]:
                wordings.append("ASMAE conflicts with other evidence sources.")
            if "low_confidence" in policy["warning_codes"]:
                wordings.append("Low-confidence ASMAE surface. Use as diagnostic context.")
            if "high_uncertainty" in policy["warning_codes"]:
                wordings.append("High uncertainty. Interpret boundaries cautiously.")
            if "bma_not_success" in policy["warning_codes"]:
                wordings.append("Model agreement was insufficient; this layer is diagnostic.")
            if "mild_warning" in policy["warning_codes"]:
                wordings.append("Provisional ASMAE evidence with mild warnings.")
            
            if wordings:
                warning_wording = " ".join(wordings)
            else:
                warning_wording = "ASMAE quality warning."

        # In both cases, append the warning: "Certified inferred high-resolution detail; not a direct 1m satellite observation."
        if resolution_m <= 1.0:
            msg = "Certified inferred high-resolution detail; not a direct 1m satellite observation."
            if warning_wording:
                warning_wording += " " + msg
            else:
                warning_wording = msg

        # Determine real_asmae_evidence and source_reality
        real_ev = getattr(l1_data, "real_asmae_evidence", False)
        src_real = "raster_composite_proxy"
        if real_ev:
            src_real = "real_raster"
            if l1_data.asmae_evidence_state:
                src_real = l1_data.asmae_evidence_state.get("source_reality", "real_raster")
        elif l1_data.asmae_evidence_state:
            src_real = l1_data.asmae_evidence_state.get("source_reality", "raster_composite_proxy")

        creator_mapping = {
            SurfaceType.ASMAE_VIGOR: "ASMAE_ENKF",
            SurfaceType.ASMAE_LAI: "ASMAE_ENKF",
            SurfaceType.ASMAE_CHLOROPHYLL: "ASMAE_ENKF",
            SurfaceType.ASMAE_CANOPY_WATER: "ASMAE_ENKF",
            SurfaceType.ASMAE_ROOT_ZONE_WATER: "ASMAE_ENKF",
            SurfaceType.ASMAE_SURFACE_WETNESS_EVENT: "ASMAE_ENKF",
            SurfaceType.ASMAE_STRUCTURE: "ASMAE_ENKF",
            SurfaceType.ASMAE_BARE_SOIL: "ASMAE_ENKF",
            SurfaceType.ASMAE_SALINITY_STRESS: "ASMAE_ENKF",
            SurfaceType.ASMAE_THERMAL_STRESS: "ASMAE_ENKF",
            SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: "ASMAE_ENKF",
            SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: "ASMAE_ENKF",
            SurfaceType.ASMAE_CONFIDENCE: "ASMAE_BMA",
            SurfaceType.ASMAE_UNCERTAINTY: "ASMAE_BMA",
            SurfaceType.ASMAE_RETROVALIDATION_SCORE: "ASMAE_RETROVALIDATION",
            SurfaceType.ASMAE_BMA_DISAGREEMENT: "ASMAE_BMA",
            SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: "ASMAE_ML",
            SurfaceType.ASMAE_EXPORT_ELIGIBILITY: "ASMAE_ENKF",
            SurfaceType.ASMAE_1M_ADVISORY_MASK: "ASMAE_ENKF",
            SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK: "ASMAE_ENKF",
            SurfaceType.ASMAE_5M_GENERALIZED_MASK: "ASMAE_ENKF",
            SurfaceType.ASMAE_EFFECTIVE_RESOLUTION_MAP: "ASMAE_ENKF",
            SurfaceType.ASMAE_ML_AGREEMENT: "ASMAE_ML",
            SurfaceType.ASMAE_ARCHIVE_SUPPORT: "ASMAE_ARCHIVE",
            SurfaceType.ASMAE_ENKF_SUPPORT: "ASMAE_ENKF",
            SurfaceType.ASMAE_RADIOMETRIC_SUPPORT: "ASMAE_RADIOMETRIC",
            SurfaceType.ASMAE_VISUAL_FUSION_CANOPY: "ASMAE_VISUAL_FUSION",
        }

        feature_mapping = {
            SurfaceType.ASMAE_VIGOR: "asmae_vigor",
            SurfaceType.ASMAE_LAI: "asmae_lai",
            SurfaceType.ASMAE_CHLOROPHYLL: "asmae_chlorophyll",
            SurfaceType.ASMAE_CANOPY_WATER: "asmae_canopy_water",
            SurfaceType.ASMAE_ROOT_ZONE_WATER: "asmae_root_zone_water",
            SurfaceType.ASMAE_SURFACE_WETNESS_EVENT: "asmae_surface_wetness_event",
            SurfaceType.ASMAE_STRUCTURE: "asmae_structure",
            SurfaceType.ASMAE_BARE_SOIL: "asmae_bare_soil",
            SurfaceType.ASMAE_SALINITY_STRESS: "asmae_salinity_stress",
            SurfaceType.ASMAE_THERMAL_STRESS: "asmae_thermal_stress",
            SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: "asmae_biotic_confounder_risk",
            SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: "asmae_effective_resolution",
            SurfaceType.ASMAE_CONFIDENCE: "asmae_confidence",
            SurfaceType.ASMAE_UNCERTAINTY: "asmae_uncertainty",
            SurfaceType.ASMAE_RETROVALIDATION_SCORE: "retrovalidation_score",
            SurfaceType.ASMAE_BMA_DISAGREEMENT: "bma_disagreement",
            SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: "cross_layer_conflict",
            SurfaceType.ASMAE_EXPORT_ELIGIBILITY: "asmae_export_eligibility",
            SurfaceType.ASMAE_1M_ADVISORY_MASK: "asmae_1m_advisory_mask",
            SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK: "asmae_2_5m_model_assisted_mask",
            SurfaceType.ASMAE_5M_GENERALIZED_MASK: "asmae_5m_generalized_mask",
            SurfaceType.ASMAE_EFFECTIVE_RESOLUTION_MAP: "asmae_effective_resolution_map",
            SurfaceType.ASMAE_ML_AGREEMENT: "ml_agreement",
            SurfaceType.ASMAE_ARCHIVE_SUPPORT: "archive_support",
            SurfaceType.ASMAE_ENKF_SUPPORT: "enkf_support",
            SurfaceType.ASMAE_RADIOMETRIC_SUPPORT: "radiometric_support",
            SurfaceType.ASMAE_VISUAL_FUSION_CANOPY: "visual_fusion_canopy",
        }

        provenance = {
            "real_asmae_evidence": real_ev,
            "source_reality": src_real,
            "creator": creator_mapping.get(stype, "ASMAE_ENKF"),
            "asmae_feature": feature_mapping.get(stype, stype.value.lower()),
            "used_bma": True,
            "used_archive": True,
            "used_retrovalidation": True,
            "has_spatial_grid": has_spatial_grid_flag,
            "grid_inheritance_allowed": True,
            "surface_generated_from": generated_from,
            "surface_type": stype.value,
            "render_mode": f"RenderMode.{stype.value}",
            "asmae_channel": asmae_channel,
            "resolution_m": resolution_m,
            "effective_resolution_m": meta.get("effective_resolution_m", resolution_m),
            "native_observation_resolution_m": native_basis,
            "certified_basis_m": certified_basis_m,
            "source_basis": source_basis,
            "confidence": confidence,
            "uncertainty": uncertainty,
            "retro_status": retro_status,
            "retrovalidation_score": retro_score,
            "bma_status": bma_status,
            "bma_disagreement": bma_disagreement,
            "cross_layer_conflict": cross_layer_conflict,
            "state_update_allowed": state_update_allowed,
            "enkf_mode": enkf_mode,
            "radiometric_mode": radiometric_mode,
            "operator_locked": operator_locked,
            "graph_locked": graph_locked,
            "scene_stack_mode": scene_stack_mode,
            "degraded_mean_only": degraded_mean_only,
            "no_scenes": no_scenes,
            "mean_only": mean_only,
            "operator_bundle_hash": meta.get("operator_bundle_hash"),
            "has_enkf_proxy_fallback": meta.get("has_enkf_proxy_fallback", False),
            "full_enkf_credit_allowed": meta.get("full_enkf_credit_allowed", False),
            "full_radiometric_credit_allowed": meta.get("full_radiometric_credit_allowed", False),
            "diagnostic_only": diagnostic_only,
            "visual_only": visual_only,
            "content_hash": c_hash,
            "artifact_instance_hash": a_hash,
            "warning_codes": policy["warning_codes"],
            "display_trust_tier": policy["display_trust_tier"],
            "desaturation_level": policy["desaturation_level"],
            "alpha_multiplier": policy["alpha_multiplier"],
            "requires_user_warning": policy["requires_user_warning"],
            "warning_wording": warning_wording,
        }

        # The advisory mask is an inter-stage control artifact, not just a
        # renderable raster.  Bind it to the exact ASMAE snapshot, authority
        # decision and grid that produced it so a later stage can fail closed
        # instead of consuming a stale, proxy-derived or resampled mask.
        if stype == SurfaceType.ASMAE_1M_ADVISORY_MASK:
            evidence_state = dict(getattr(l1_data, "asmae_evidence_state", {}) or {})
            allowed_outputs = evidence_state.get("allowed_outputs") or []
            source_plot_id = meta.get("source_plot_id") or inp.plot_id
            source_schema_version = meta.get("source_schema_version")
            authority = evidence_state.get("authority")
            current_1m_allowed = bool(evidence_state.get("current_1m_approval_allowed", False))
            output_allowed = (
                "ASMAE_1M_ADVISORY_MASK" in allowed_outputs
                if allowed_outputs
                else current_1m_allowed
            )
            non_proxy = bool(
                real_ev
                and evidence_state.get("real_asmae_evidence", False)
                and src_real not in ("raster_composite_proxy", "proxy", "synthetic", "unknown", "missing")
                and "proxy" not in str(src_real).lower()
            )
            provenance["candidate_mask_proof"] = {
                "contract_version": "asmae_candidate_mask_v1",
                "source_schema_version": source_schema_version,
                "plot_id": str(source_plot_id or ""),
                "source_output_content_hash": c_hash,
                "source_artifact_instance_hash": a_hash,
                "source_generated_at": meta.get("source_generated_at"),
                "grid_shape": [H, W],
                "surface_grid_ref": f"{H}x{W}",
                "generated_from_current_raster": bool(has_real_grid and generated_from == "raster_maps"),
                "source_reality": src_real,
                "real_asmae_evidence": bool(real_ev and evidence_state.get("real_asmae_evidence", False)),
                "non_proxy": non_proxy,
                "authority": authority,
                "current_1m_authority_allowed": current_1m_allowed,
                "output_allowed": bool(output_allowed),
                "diagnostic_only": bool(diagnostic_only),
                "state_update_allowed": False,
            }

        # Inject explicit display-only and certification metadata
        if resolution_m <= 1.0:
            if resolved_result:
                provenance["certification_reason_codes"] = resolved_result.reason_codes
            if is_certified_v90:
                provenance["certification_status"] = "certified_inferred_detail"
                provenance["certification_source"] = "v90"
                provenance["certification_id"] = meta.get("certification_id")
                provenance["display_certified"] = True
                provenance["reporting_certified"] = True
                provenance["state_update_allowed"] = False
                provenance["layer1_state_evidence_allowed"] = False
                provenance["training_label_allowed"] = False
                provenance["prescription_driver_allowed"] = False
                provenance["not_direct_observation"] = True
            else:
                provenance["certification_status"] = "uncertified_1m"
                provenance["display_certified"] = False
                provenance["reporting_certified"] = False
                provenance["state_update_allowed"] = False
                provenance["layer1_state_evidence_allowed"] = False
                provenance["training_label_allowed"] = False
                provenance["prescription_driver_allowed"] = False
                provenance["not_direct_observation"] = True

        # Styling/wording overrides for visual_only 1m resolution or certified
        if resolution_m <= 1.0:
            if is_certified_v90:
                provenance["user_facing_badge"] = "Certified Inferred Detail"
                provenance["user_facing_warning"] = "Certified inferred detail; not a direct 1m observation"
                provenance["expert_tooltip"] = "Certified inferred detail from ASMAE deconvolution; display only"
                provenance["pixel_inspector_label"] = "Certified inferred detail; state update blocked"
                provenance["warning_wording"] = "Certified inferred high-resolution detail; not a direct 1m satellite observation."
            else:
                provenance["user_facing_badge"] = "Experimental visual detail"
                provenance["user_facing_warning"] = "Not a direct 1m satellite observation"
                provenance["expert_tooltip"] = "Inferred visual detail from ASMAE deconvolution / assimilation"
                provenance["pixel_inspector_label"] = "Visual-only; state update blocked"
                provenance["warning_wording"] = "Experimental visual detail — not a direct 1m satellite observation."

        # Grounding class
        flat_vals = [v for row in grid for v in row if v is not None]
        if not has_spatial_grid_flag:
            grounding = GroundingClass.UNIFORM.value
        elif len(set(flat_vals)) > 1:
            grounding = GroundingClass.RASTER_GROUNDED.value
        else:
            grounding = GroundingClass.UNIFORM.value

        if grounding == GroundingClass.UNIFORM.value:
            provenance["scope"] = "plot_level"
            provenance["constant_allowed"] = True

        surfaces.append(SurfaceArtifact(
            surface_id=f"{stype.value}_{inp.plot_id}",
            semantic_type=stype,
            grid_ref=f"{H}x{W}",
            values=grid,
            units=units[stype],
            native_resolution_m=resolution_m,
            render_range=render_ranges.get(stype, (0.0, 1.0)),
            palette_id=palettes[stype],
            source_layers=["L1"],
            provenance=provenance,
            grounding_class=grounding,
        ))

    return surfaces


def asmae_surface_visual_eligible(surface: SurfaceArtifact) -> tuple[bool, str]:
    """Check if ASMAE surface is eligible for any visual display (card, badge, tint, or overlay).
    
    V92.4-BC.2: Soft visual gate. Only blocks when the surface genuinely has no
    renderable information at all. Passed surfaces may still be plot-level cards,
    metadata badges, or uniform tints — they are not necessarily pixel overlays.
    """
    if surface is None:
        return False, "surface_is_none"
    
    prov = surface.provenance or {}
    
    # No values at all — nothing to show
    vals = surface.values
    if not vals:
        return False, "no_values"
    
    # Check for at least one 2D array with finite values
    is_2d = isinstance(vals, list) and len(vals) > 0 and isinstance(vals[0], list)
    if not is_2d:
        return False, "no_2d_values"
    
    finite_count = sum(
        1 for row in vals for v in row
        if v is not None and isinstance(v, (int, float)) and not (isinstance(v, float) and (v != v))  # NaN check
    )
    if finite_count == 0:
        return False, "no_finite_values"
    
    return True, "visual_eligible"


def asmae_surface_pixel_visual_eligible(surface: SurfaceArtifact, output_grid_spec: Optional[dict] = None) -> tuple[bool, str]:
    """Check if ASMAE surface can render as a spatial pixel overlay (not just card/badge).
    
    V92.4-BC.2: Requires spatial grid and non-uniform grounding. Does NOT check
    authority gates (operator lock, radiometric mode, EnKF credit). Those are for
    state updates, prescriptions, and certification only.
    
    Surfaces that fail this check but pass visual_eligible can still appear as
    plot-level uniform tints or metadata cards.
    """
    # Must first pass basic visual eligibility
    visual_ok, visual_reason = asmae_surface_visual_eligible(surface)
    if not visual_ok:
        return False, visual_reason
    
    prov = surface.provenance or {}
    
    # Grounding class check — UNIFORM/BROADCAST cannot be pixel overlays
    gc = getattr(surface, "grounding_class", "UNIFORM") or "UNIFORM"
    if gc in ["UNIFORM", "BROADCAST"]:
        return False, "grounding_class_non_spatial"
    
    # Hard rejections for degraded states — no real spatial variation
    if prov.get("degraded_mean_only") is True:
        return False, "degraded_mean_only"
    if prov.get("no_scenes") is True:
        return False, "no_scenes"
    if prov.get("mean_only") is True:
        return False, "mean_only"
    
    # Require explicit spatial grid proof
    if prov.get("has_spatial_grid") is not True:
        return False, "no_spatial_grid"
    
    # Check grid_spec/bounds exist if surface has grid_spec attribute
    grid_spec = getattr(surface, "grid_spec", None)
    if not grid_spec:
        if not output_grid_spec:
            return False, "missing_grid_spec"
        # Check values shape matches output_grid_spec height and width
        vals = surface.values
        vals_h = len(vals) if vals else 0
        vals_w = len(vals[0]) if vals_h > 0 and isinstance(vals[0], list) else 0
        tgt_h = output_grid_spec.get("height", 0)
        tgt_w = output_grid_spec.get("width", 0)
        if vals_h != tgt_h or vals_w != tgt_w:
            if prov.get("grid_inheritance_allowed") is not True:
                return False, "grid_spec_shape_mismatch"
        if prov.get("grid_inheritance_allowed") is not True:
            return False, "grid_spec_not_provenanced"
        grid_spec = output_grid_spec
        
    if not grid_spec or not isinstance(grid_spec, dict):
        return False, "invalid_grid_spec"
        
    bounds = grid_spec.get("bounds")
    width = grid_spec.get("width")
    height = grid_spec.get("height")
    
    if not bounds or not isinstance(bounds, (list, tuple)) or len(bounds) < 4:
        return False, "missing_grid_spec_bounds"
    if not width or not isinstance(width, int) or width <= 0:
        return False, "missing_grid_spec_width"
    if not height or not isinstance(height, int) or height <= 0:
        return False, "missing_grid_spec_height"
    
    return True, "overlay_eligible"


def asmae_surface_spatially_eligible(surface: SurfaceArtifact) -> tuple[bool, str]:
    """Check if ASMAE surface is authority-eligible for state updates, prescriptions, and certification.
    
    V92.4-BC: Fail closed. Missing provenance fields are NOT defaulted to safe-looking
    values. Every check requires explicit proof to be present and correct.
    
    V92.4-BC.2: This is the AUTHORITY gate. Surfaces that fail this check can still
    render as diagnostic pixel overlays (if pixel_visual_eligible) or plot-level cards
    (if visual_eligible). Only state_update_allowed, prescription_driver_allowed,
    training_label_allowed, and certification depend on this gate.
    """
    prov = surface.provenance or {}
    
    # Grounding class check — UNIFORM/BROADCAST are never spatial
    gc = getattr(surface, "grounding_class", "UNIFORM") or "UNIFORM"
    if gc in ["UNIFORM", "BROADCAST"]:
        return False, "grounding_class_non_spatial"
    
    # Hard rejections for degraded states
    if prov.get("degraded_mean_only") is True:
        return False, "degraded_mean_only"
    if prov.get("no_scenes") is True:
        return False, "no_scenes"
    if prov.get("mean_only") is True:
        return False, "mean_only"
    
    # V92.4: Fail closed — require explicit spatial grid proof
    if prov.get("has_spatial_grid") is not True:
        return False, "no_spatial_grid"
    
    # V92.4: Fail closed — require scene stack to be real raster
    scene_stack_mode = prov.get("scene_stack_mode")
    if scene_stack_mode != "real_raster":
        return False, f"scene_stack_not_real_raster:{scene_stack_mode}"
    
    # V92.4: Fail closed — require operator and graph locks
    if prov.get("operator_locked") is not True:
        return False, "operator_not_locked"
    if prov.get("graph_locked") is not True:
        return False, "graph_not_locked"
    
    # V92.4-BC: Require exact ht_per_pixel radiometric mode — no boolean True
    radiometric_mode = prov.get("radiometric_mode")
    if radiometric_mode != "ht_per_pixel":
        return False, f"radiometric_not_ht_per_pixel:{radiometric_mode}"
    
    # V92.4-BC: Require full radiometric credit
    if prov.get("full_radiometric_credit_allowed") is not True:
        return False, "radiometric_credit_not_allowed"
    
    # V92.4-BC: Require exact ht_per_pixel EnKF mode — no boolean True
    enkf_mode = prov.get("enkf_mode")
    if enkf_mode != "ht_per_pixel":
        return False, f"enkf_not_ht_per_pixel:{enkf_mode}"
    
    # V92.4-BC: Require full EnKF credit
    if prov.get("full_enkf_credit_allowed") is not True:
        return False, "enkf_credit_not_allowed"
    
    # V92.4: Fail closed — reject proxy fallback
    if prov.get("has_enkf_proxy_fallback") is True:
        return False, "enkf_proxy_fallback"
    
    return True, "eligible"


def generate_asmae_aliases(
    H: int,
    W: int,
    surfaces: List[SurfaceArtifact],
    inp: Layer10Input,
    grid_spec_dict: Optional[dict] = None
) -> List[SurfaceArtifact]:
    """Generate canonical alias/proxy surfaces from ASMAE surfaces to bridge them to map modes.
    
    V92.4-BC.2: Uses three-tier eligibility:
      - visual_eligible: can be shown somewhere (card, badge, tint)
      - pixel_visual_eligible: can render as spatial pixel overlay
      - authority_eligible: can influence state/prescription/certification
    
    Aliases are generated when pixel_visual_eligible=True, even if authority_eligible=False.
    Authority-ineligible aliases get diagnostic_only=True and state_update_allowed=False.
    """
    aliases = []
    
    # Helper to find a surface by semantic type
    def find_surf(stype: SurfaceType) -> Optional[SurfaceArtifact]:
        return next((s for s in surfaces if s.semantic_type == stype), None)

    # Alias mapping rules
    ASMAE_ALIAS_RULES = {
        SurfaceType.ASMAE_VIGOR: {
            "alias": SurfaceType.CANOPY_ASMAE_VIGOR,
            "mode": "canopy",
            "requires_spatial": True,
            "trust_label": "ASMAE vigor diagnostic",
            "warning": "ASMAE vigor diagnostic - not direct observation - not prescription driver",
            "confounder_warnings": [],
        },
        SurfaceType.ASMAE_CANOPY_WATER: {
            "alias": SurfaceType.WATER_ASMAE_CANOPY_WATER,
            "mode": "water",
            "requires_spatial": True,
            "trust_label": "ASMAE canopy water diagnostic",
            "warning": "Canopy water diagnostic, not confirmed water stress - not prescription driver",
            "confounder_warnings": [],
        },
        SurfaceType.ASMAE_ROOT_ZONE_WATER: {
            "alias": SurfaceType.WATER_ASMAE_ROOT_ZONE_WATER,
            "mode": "water",
            "requires_spatial": True,
            "trust_label": "ASMAE root-zone water estimate",
            "warning": "Root-zone water estimate, not confirmed water stress - not prescription driver",
            "confounder_warnings": [],
        },
        SurfaceType.ASMAE_CHLOROPHYLL: {
            "alias": SurfaceType.NUTRIENT_ASMAE_CHLOROPHYLL_PROXY,
            "mode": "nutrients",
            "requires_spatial": True,
            "trust_label": "ASMAE chlorophyll proxy",
            "warning": "Nutrient proxy from ASMAE chlorophyll - diagnostic only - confounded by water, salinity, disease, growth stage",
            "confounder_warnings": [
                "chlorophyll_proxy_not_confirmed_nutrient_stress",
                "confounded_by_water",
                "confounded_by_salinity",
                "confounded_by_biotic_stress",
                "confounded_by_crop_stage",
            ],
        },
        SurfaceType.ASMAE_SALINITY_STRESS: {
            "alias": SurfaceType.SALINITY_ASMAE_STRESS,
            "mode": "salinity",
            "requires_spatial": True,
            "trust_label": "ASMAE diagnostic salinity estimate",
            "warning": "ASMAE diagnostic salinity estimate - not direct observation - not prescription driver",
            "confounder_warnings": [],
        },
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: {
            "alias": SurfaceType.RESOLUTION_ASMAE_EFFECTIVE,
            "mode": "resolution",
            "requires_spatial": False,
            "trust_label": "ASMAE effective resolution",
            "warning": "ASMAE effective resolution diagnostic",
            "confounder_warnings": [],
        },
        # V92.4-BC.2: Veg attention separate aliases
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: {
            "alias": SurfaceType.VEG_ATTENTION_ASMAE_CONFLICT,
            "mode": "veg_attention",
            "requires_spatial": True,
            "trust_label": "ASMAE cross-layer conflict diagnostic",
            "warning": "ASMAE cross-layer conflict — diagnostic attention mask",
            "confounder_warnings": [],
        },
        SurfaceType.ASMAE_BMA_DISAGREEMENT: {
            "alias": SurfaceType.VEG_ATTENTION_ASMAE_DISAGREEMENT,
            "mode": "veg_attention",
            "requires_spatial": True,
            "trust_label": "ASMAE BMA disagreement diagnostic",
            "warning": "ASMAE model disagreement — diagnostic attention mask",
            "confounder_warnings": [],
        },
    }

    for src_type, rules in ASMAE_ALIAS_RULES.items():
        src_surf = find_surf(src_type)
        if not src_surf:
            continue
        
        # V92.4-BC.2: Three-tier eligibility
        visual_ok, visual_reason = asmae_surface_visual_eligible(src_surf)
        pixel_ok, pixel_reason = asmae_surface_pixel_visual_eligible(src_surf, output_grid_spec=grid_spec_dict)
        authority_ok, authority_reason = asmae_surface_spatially_eligible(src_surf)
        
        # If spatial display is required, need at least pixel_visual_eligible
        if rules["requires_spatial"] and not pixel_ok:
            continue
        
        # If not spatial but not visually eligible at all, skip
        if not rules["requires_spatial"] and not visual_ok:
            continue
            
        prov = dict(src_surf.provenance or {})
        prov.update({
            "alias_of": src_type.value,
            "map_mode": rules["mode"],
            "source_class": "asmae_diagnostic",
            "diagnostic_only": True,
            "not_direct_observation": True,
            "prescription_driver_allowed": False,
            "state_update_allowed": False,
            "visual_only": False,
            "warning_wording": rules["warning"],
            # V92.4-BC.2: Full three-tier eligibility provenance
            "card_or_badge_eligible": visual_ok,
            "visual_eligibility_reason": visual_reason,
            "overlay_eligible": pixel_ok,
            "pixel_visual_reason": pixel_reason,
            "authority_eligible": authority_ok,
            "authority_block_reason": authority_reason if not authority_ok else None,
            "display_level": "asmae_diagnostic",
            "authority_level": "scout" if not authority_ok else "decision_support",
            "trust_badges": [
                "ASMAE diagnostic",
                "not direct observation",
                "not prescription driver",
            ],
        })
        
        # V92.4-BC.2: Confounder warnings for nutrient/chlorophyll proxy
        if rules.get("confounder_warnings"):
            prov["confounder_warnings"] = rules["confounder_warnings"]
        
        aliases.append(SurfaceArtifact(
            surface_id=f"{rules['alias'].value}_{inp.plot_id}",
            semantic_type=rules["alias"],
            grid_ref=src_surf.grid_ref,
            values=src_surf.values,
            units=src_surf.units,
            native_resolution_m=src_surf.native_resolution_m,
            render_range=src_surf.render_range,
            palette_id=src_surf.palette_id,
            source_layers=src_surf.source_layers,
            provenance=prov,
            grounding_class=src_surf.grounding_class,
            grid_spec=grid_spec_dict,
        ))

    # ── V92.4-BC.2: VEG_ATTENTION_ASMAE_DIAGNOSTIC composite ──────────
    # Combines cross-layer conflict and BMA disagreement into a single
    # attention mask for farmer mode. Expert mode uses the separate aliases.
    veg_attn_ingredients = {
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: 0.45,
        SurfaceType.ASMAE_BMA_DISAGREEMENT: 0.35,
        SurfaceType.ASMAE_UNCERTAINTY: 0.20,
    }
    
    active_veg_ingredients = {}
    excluded_veg_ingredients = []
    for st, w in veg_attn_ingredients.items():
        s = find_surf(st)
        if s:
            pixel_ok, pixel_reason = asmae_surface_pixel_visual_eligible(s, output_grid_spec=grid_spec_dict)
            if pixel_ok:
                active_veg_ingredients[st] = (s, w)
            else:
                excluded_veg_ingredients.append({"surface": st.value, "reason": pixel_reason})
    
    if active_veg_ingredients:
        veg_attn_grid = [[None] * W for _ in range(H)]
        has_veg_val = False
        
        for r in range(H):
            for c in range(W):
                val_sum = 0.0
                weight_sum = 0.0
                for s, w in active_veg_ingredients.values():
                    v = s.values[r][c]
                    if v is not None:
                        val_sum += v * w
                        weight_sum += w
                
                if weight_sum > 0:
                    veg_attn_grid[r][c] = round(val_sum / weight_sum, 4)
                    has_veg_val = True
        
        if has_veg_val:
            res_m = next(iter(active_veg_ingredients.values()))[0].native_resolution_m
            
            aliases.append(SurfaceArtifact(
                surface_id=f"VEG_ATTENTION_ASMAE_DIAGNOSTIC_{inp.plot_id}",
                semantic_type=SurfaceType.VEG_ATTENTION_ASMAE_DIAGNOSTIC,
                grid_ref=f"{H}x{W}",
                values=veg_attn_grid,
                units="score",
                native_resolution_m=res_m,
                render_range=(0.0, 1.0),
                palette_id=PaletteId.RISK_HEAT,
                source_layers=["L1"],
                provenance={
                    "alias_of": "ASMAE_VEG_ATTENTION_COMPOSITE",
                    "map_mode": "veg_attention",
                    "source_class": "asmae_diagnostic",
                    "diagnostic_only": True,
                    "not_direct_observation": True,
                    "prescription_driver_allowed": False,
                    "state_update_allowed": False,
                    "visual_only": False,
                    "has_spatial_grid": True,
                    "card_or_badge_eligible": True,
                    "overlay_eligible": True,
                    "authority_eligible": False,
                    "authority_block_reason": "diagnostic_composite",
                    "display_level": "asmae_diagnostic",
                    "authority_level": "scout",
                    "trust_badges": ["ASMAE diagnostic", "attention composite", "not prescription driver"],
                    "veg_attn_ingredients": [st.value for st in active_veg_ingredients.keys()],
                    "veg_attn_weights": {st.value: w for st, (_, w) in active_veg_ingredients.items()},
                    "excluded_ingredients": excluded_veg_ingredients,
                    "composite_method": "weighted_attention: 0.45 conflict + 0.35 disagreement + 0.20 uncertainty",
                    "warning_wording": "ASMAE diagnostic vegetation attention composite — not prescription driver.",
                },
                grounding_class=GroundingClass.RASTER_GROUNDED.value,
                grid_spec=grid_spec_dict,
            ))

    # ── RISK_ASMAE_DIAGNOSTIC: ASMAE diagnostic risk composite ────────
    risk_ingredients = {
        SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: 0.3,
        SurfaceType.ASMAE_THERMAL_STRESS: 0.2,
        SurfaceType.ASMAE_SALINITY_STRESS: 0.2,
        SurfaceType.ASMAE_BMA_DISAGREEMENT: 0.15,
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: 0.15,
    }
    
    # V92.4-BC.2: Gate each risk ingredient on pixel_visual eligibility (not authority)
    active_ingredients = {}
    excluded_ingredients = []
    for st, w in risk_ingredients.items():
        s = find_surf(st)
        if s:
            elig, elig_reason = asmae_surface_pixel_visual_eligible(s, output_grid_spec=grid_spec_dict)
            if elig:
                active_ingredients[st] = (s, w)
            else:
                excluded_ingredients.append({"surface": st.value, "reason": elig_reason})
            
    if active_ingredients:
        composite_grid = [[0.0] * W for _ in range(H)]
        has_val = False
        
        conf_surf = find_surf(SurfaceType.ASMAE_CONFIDENCE)
        retro_surf = find_surf(SurfaceType.ASMAE_RETROVALIDATION_SCORE)
        
        for r in range(H):
            for c in range(W):
                val_sum = 0.0
                weight_sum = 0.0
                for s, w in active_ingredients.values():
                    v = s.values[r][c]
                    if v is not None:
                        val_sum += v * w
                        weight_sum += w
                        
                if weight_sum > 0:
                    base_risk = val_sum / weight_sum
                    
                    # Apply trust weighting
                    conf_weight = conf_surf.values[r][c] if (conf_surf and conf_surf.values[r][c] is not None) else 0.8
                    retro_weight = retro_surf.values[r][c] if (retro_surf and retro_surf.values[r][c] is not None) else 0.85
                    
                    composite_grid[r][c] = round(base_risk * conf_weight * retro_weight, 4)
                    has_val = True
                else:
                    composite_grid[r][c] = None
                    
        if has_val:
            res_m = next(iter(active_ingredients.values()))[0].native_resolution_m
            
            # V92.4-BC.2: Risk authority is diagnostic_only unless every primary ingredient is authority-eligible
            risk_authority_ok = all(
                asmae_surface_spatially_eligible(s)[0]
                for s, _ in active_ingredients.values()
            )
            
            aliases.append(SurfaceArtifact(
                surface_id=f"RISK_ASMAE_DIAGNOSTIC_{inp.plot_id}",
                semantic_type=SurfaceType.RISK_ASMAE_DIAGNOSTIC,
                grid_ref=f"{H}x{W}",
                values=composite_grid,
                units="score",
                native_resolution_m=res_m,
                render_range=(0.0, 1.0),
                palette_id=PaletteId.RISK_HEAT,
                source_layers=["L1"],
                provenance={
                    "alias_of": "ASMAE_RISK_COMPOSITE",
                    "map_mode": "composite_risk",
                    "source_class": "asmae_diagnostic",
                    "diagnostic_only": True,
                    "not_direct_observation": True,
                    "prescription_driver_allowed": False,
                    "state_update_allowed": False,
                    "visual_only": False,
                    "has_spatial_grid": True,
                    "card_or_badge_eligible": True,
                    "overlay_eligible": True,
                    "authority_eligible": risk_authority_ok,
                    "authority_block_reason": "diagnostic_composite" if not risk_authority_ok else None,
                    "display_level": "asmae_diagnostic",
                    "authority_level": "decision_support" if risk_authority_ok else "scout",
                    "trust_badges": ["ASMAE diagnostic", "not prescription driver"],
                    "risk_ingredients": [st.value for st in active_ingredients.keys()],
                    "excluded_ingredients": excluded_ingredients,
                    "composite_method": "weighted_diagnostic",
                    "warning_wording": "ASMAE diagnostic risk composite — not prescription driver.",
                },
                grounding_class=GroundingClass.RASTER_GROUNDED.value,
                grid_spec=grid_spec_dict,
            ))

    # ── CONFIDENCE_ASMAE ──────────────────────────────────────────────
    # V92.4-BC.2: Uses pixel_visual eligibility (not authority) for confidence
    conf_surf = find_surf(SurfaceType.ASMAE_CONFIDENCE)
    conf_pixel_ok = False
    if conf_surf:
        conf_pixel_ok, conf_pixel_reason = asmae_surface_pixel_visual_eligible(conf_surf, output_grid_spec=grid_spec_dict)
        if not conf_pixel_ok:
            # Check if visually eligible for plot-level card
            conf_visual_ok, _ = asmae_surface_visual_eligible(conf_surf)
            if not conf_visual_ok:
                conf_surf = None
    
    if conf_surf and conf_pixel_ok:
        conf_authority_ok, conf_authority_reason = asmae_surface_spatially_eligible(conf_surf)
        aliases.append(SurfaceArtifact(
            surface_id=f"CONFIDENCE_ASMAE_{inp.plot_id}",
            semantic_type=SurfaceType.CONFIDENCE_ASMAE,
            grid_ref=conf_surf.grid_ref,
            values=conf_surf.values,
            units=conf_surf.units,
            native_resolution_m=conf_surf.native_resolution_m,
            render_range=conf_surf.render_range,
            palette_id=PaletteId.UNCERTAINTY_GRAY,
            source_layers=conf_surf.source_layers,
            provenance={
                "alias_of": "ASMAE_CONFIDENCE",
                "map_mode": "uncertainty",
                "source_class": "asmae_diagnostic",
                "diagnostic_only": True,
                "not_direct_observation": True,
                "prescription_driver_allowed": False,
                "state_update_allowed": False,
                "visual_only": False,
                "has_spatial_grid": True,
                "card_or_badge_eligible": True,
                "overlay_eligible": True,
                "authority_eligible": conf_authority_ok,
                "authority_block_reason": conf_authority_reason if not conf_authority_ok else None,
                "display_level": "asmae_diagnostic",
                "authority_level": "scout",
                "trust_badges": ["ASMAE diagnostic", "not direct observation"],
                "warning_wording": "ASMAE diagnostic confidence.",
            },
            grounding_class=conf_surf.grounding_class,
            grid_spec=grid_spec_dict,
        ))
    elif not conf_surf or not conf_pixel_ok:
        # Fallback to inverted ASMAE_UNCERTAINTY
        unc_surf = find_surf(SurfaceType.ASMAE_UNCERTAINTY)
        if unc_surf:
            unc_pixel_ok, unc_pixel_reason = asmae_surface_pixel_visual_eligible(unc_surf, output_grid_spec=grid_spec_dict)
            if not unc_pixel_ok:
                unc_surf = None
        if unc_surf:
            unc_authority_ok, unc_authority_reason = asmae_surface_spatially_eligible(unc_surf)
            inverted_grid = [[None if v is None else round(1.0 - v, 4) for v in row] for row in unc_surf.values]
            aliases.append(SurfaceArtifact(
                surface_id=f"CONFIDENCE_ASMAE_{inp.plot_id}",
                semantic_type=SurfaceType.CONFIDENCE_ASMAE,
                grid_ref=unc_surf.grid_ref,
                values=inverted_grid,
                units="score",
                native_resolution_m=unc_surf.native_resolution_m,
                render_range=(0.0, 1.0),
                palette_id=PaletteId.UNCERTAINTY_GRAY,
                source_layers=unc_surf.source_layers,
                provenance={
                    "alias_of": "ASMAE_UNCERTAINTY",
                    "map_mode": "uncertainty",
                    "source_class": "asmae_diagnostic",
                    "diagnostic_only": True,
                    "not_direct_observation": True,
                    "prescription_driver_allowed": False,
                    "state_update_allowed": False,
                    "visual_only": False,
                    "has_spatial_grid": True,
                    "inverted": True,
                    "card_or_badge_eligible": True,
                    "overlay_eligible": True,
                    "authority_eligible": unc_authority_ok,
                    "authority_block_reason": unc_authority_reason if not unc_authority_ok else None,
                    "display_level": "asmae_diagnostic",
                    "authority_level": "scout",
                    "trust_badges": ["ASMAE diagnostic", "inverted uncertainty", "not direct observation"],
                    "warning_wording": "ASMAE diagnostic confidence derived from uncertainty.",
                },
                grounding_class=unc_surf.grounding_class,
                grid_spec=grid_spec_dict,
            ))

    return aliases


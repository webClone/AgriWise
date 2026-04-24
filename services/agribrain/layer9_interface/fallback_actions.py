from typing import Dict, Any

def get_fallback_guidance(surface_type: str, state: str, has_plot_data: bool) -> Dict[str, Any]:
    """
    Computes the deterministic fallback action guidance given a surface type and its state.
    state: "localized", "field_wide", "none", "no_data", "low_confidence", "unknown"
    has_plot_data: boolean indicating if plot-level fallback metrics exist
    """
    
    # Case A: Localized zones exist
    if state == "localized":
        return None
        
    # Case B: Spatial uniform (field-wide or none)
    if state in ["field_wide", "none"]:
        if "WATER" in surface_type or "MOISTURE" in surface_type:
            why = "Moisture conditions appear broadly uniform across the plot"
            next_step = "Use whole-field irrigation judgment rather than zone targeting"
        elif "NUTRIENT" in surface_type:
            why = "Nutrient risk appears broadly uniform"
            next_step = "Prefer field-wide sampling or uniform management review rather than variable-rate action"
        elif "RISK" in surface_type:
            why = "Composite risk is uniform across the field"
            next_step = "Prioritize whole-field inspection and verify the main driver"
        elif "UNCERTAINTY" in surface_type or "RELIABILITY" in surface_type:
            why = "Confidence signal is uniform"
            next_step = "Interpret all plot recommendations with the same trust level across the field"
        else: # VEGETATION / CANOPY
            why = "Vegetation and canopy signal is spatially valid but broadly uniform across the plot"
            next_step = "Inspect the field as a whole and verify expected phenology-related growth"

        return {
            "action_mode": "field_wide",
            "recommended_next_step": next_step,
            "why": why,
            "confidence": 0.85,
            "data_basis": "spatial_uniform_surface"
        }
        
    # Case C/D: Map is invalid (no_data, low_confidence, unknown)
    if has_plot_data:
        # Case C: Plot level only
        if "WATER" in surface_type or "MOISTURE" in surface_type:
            why = "Plot-level water indicators are available, but spatial map is invalid."
            next_step = "Use whole-field irrigation review rather than intra-field zoning."
        elif "VEG" in surface_type or "NDVI" in surface_type or "CANOPY" in surface_type:
            why = "Plot-level vegetation evidence exists, but no trustworthy spatial anomaly map is available for this period."
            next_step = "Use whole-field trend interpretation, not spatial targeting."
        else:
            why = f"Plot-level data exists for {surface_type}, but no trustworthy spatial surface is available."
            next_step = "Use trend-based whole-field judgment or provide additional field evidence."
            
        return {
            "action_mode": "plot_level_only",
            "recommended_next_step": next_step,
            "why": why,
            "confidence": 0.65,
            "data_basis": "plot_stats_only"
        }
    else:
        # Case D: True No Data
        return {
            "action_mode": "insufficient_data",
            "recommended_next_step": "Wait for the next valid satellite pass or add field evidence such as a photo, sensor reading, or drone image.",
            "why": "No usable spatial or plot-level evidence is available for this mode.",
            "confidence": 0.1,
            "data_basis": "none"
        }

def build_fallback_guidance_map(zone_state_by_surface: Dict[str, str], has_plot_data: bool) -> Dict[str, Dict[str, Any]]:
    """
    Builds a dictionary of fallback guidance objects keyed by surface type.
    """
    guidance_map = {}
    
    # We always ensure the primary types are mapped even if missing from zone_state_by_surface
    core_surfaces = [
        "NDVI_CLEAN", "NDVI_DEVIATION", "BASELINE_ANOMALY",
        "WATER_STRESS_PROB", "NUTRIENT_STRESS_PROB", "COMPOSITE_RISK",
        "UNCERTAINTY_SIGMA", "DATA_RELIABILITY"
    ]
    
    for stype in core_surfaces:
        state = zone_state_by_surface.get(stype, "no_data")
        guidance = get_fallback_guidance(stype, state, has_plot_data)
        if guidance:
            guidance_map[stype] = guidance
            
    # Add any dynamic surfaces found in the dictionary
    for stype, state in zone_state_by_surface.items():
        if stype not in guidance_map:
            guidance = get_fallback_guidance(stype, state, has_plot_data)
            if guidance:
                guidance_map[stype] = guidance
                
    return guidance_map

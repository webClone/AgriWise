"""
Geo Context Diagnostics.

Summarizes provider status, feature coverage, proxy warnings,
and hard prohibition status.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.geo_context.dem.schemas import DEMContext
from layer0.geo_context.landcover.schemas import LandCoverContext
from layer0.geo_context.wapor.schemas import WaPORContext


def build_geo_diagnostics(
    dem: Optional[DEMContext] = None,
    landcover: Optional[LandCoverContext] = None,
    wapor: Optional[WaPORContext] = None,
    validation_evidence: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build diagnostics summary for the geo context package."""
    diag: Dict[str, Any] = {}

    # Provider status
    diag["providers"] = {
        "dem": {
            "available": dem is not None,
            "source": dem.source if dem else "unavailable",
            "quality": dem.qa.quality_class.value if dem else "unavailable",
            "flags": dem.qa.flags if dem else [],
        },
        "worldcover": {
            "available": landcover is not None and landcover.worldcover is not None,
            "quality": "good" if landcover and landcover.worldcover else "unavailable",
        },
        "dynamic_world": {
            "available": landcover is not None and landcover.dynamic_world is not None,
        },
        "wapor": {
            "available": wapor is not None and wapor.wapor_available,
            "level": wapor.wapor_level if wapor and wapor.wapor_available else None,
            "flags": wapor.flags if wapor else [],
        },
    }

    # Feature coverage
    diag["features"] = {
        "terrain_features_computed": dem is not None,
        "terrain_derivatives_reliable": dem.qa.terrain_derivatives_reliable if dem else False,
        "landcover_fractions_computed": landcover is not None and landcover.worldcover is not None,
        "contamination_analyzed": landcover is not None and landcover.contamination is not None,
        "wapor_indicators_computed": wapor is not None and wapor.wapor_available,
    }

    # Proxy warnings (Revision 3)
    diag["proxy_warnings"] = []
    if dem is not None:
        diag["proxy_warnings"].append("TWI_PROXY_NOT_HYDROLOGICAL_MODEL")
        if dem.flow_accumulation_proxy is None:
            diag["proxy_warnings"].append("FLOW_ACCUMULATION_NOT_COMPUTED_V1")

    # Validation evidence summary
    if validation_evidence:
        conflicts = [e for e in validation_evidence if e["status"] == "conflict"]
        diag["validation_summary"] = {
            "rules_evaluated": len(validation_evidence),
            "conflicts": len(conflicts),
            "conflict_rules": [e["rule"] for e in conflicts],
        }

    # Hard prohibitions — always report (gate-level)
    diag["geo_context_not_used_for_kalman"] = True
    diag["hard_prohibitions"] = {
        "no_direct_kalman_updates": True,
        "dem_not_soil_moisture_truth": True,
        "landcover_not_crop_health": True,
        "wapor_not_plot_truth": True,
        "dynamic_world_not_crop_health": True,
        "sensor_placement_not_state_update": True,
    }

    return diag

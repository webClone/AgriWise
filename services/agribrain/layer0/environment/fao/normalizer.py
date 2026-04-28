"""
FAO/HWSD Normalizer.

Converts raw HWSD data to FAOSoilContext.
V1: accepts pre-fetched/mocked input.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.fao.schemas import FAOSoilContext


def normalize_fao_response(
    raw_data: Dict[str, Any],
    dataset_version: str = "v2.0",
    access_method: str = "mocked_fixture",
) -> FAOSoilContext:
    """Convert raw HWSD/FAO response dict to FAOSoilContext."""
    return FAOSoilContext(
        soil_mapping_unit=str(raw_data.get("soil_mapping_unit", "")),
        dominant_soil_type=str(raw_data.get("dominant_soil_type", "")),
        secondary_soil_type=str(raw_data.get("secondary_soil_type", "")),
        ipcc_soil_group=str(raw_data.get("ipcc_soil_group", "")),
        topsoil_texture=str(raw_data.get("topsoil_texture", "")),
        subsoil_texture=str(raw_data.get("subsoil_texture", "")),
        soil_depth_class=str(raw_data.get("soil_depth_class", "")),
        salinity_risk=str(raw_data.get("salinity_risk", "unknown")),
        sodicity_risk=str(raw_data.get("sodicity_risk", "unknown")),
        calcareous_lime_risk=str(raw_data.get("calcareous_lime_risk", "unknown")),
        gypsum_risk=str(raw_data.get("gypsum_risk", "unknown")),
        drainage_limitation=str(raw_data.get("drainage_limitation", "unknown")),
        agro_ecological_flags=list(raw_data.get("agro_ecological_flags", [])),
        resolution_m=1000.0,
        dataset_name="HWSD",
        dataset_version=dataset_version,
        access_method=access_method,
    )

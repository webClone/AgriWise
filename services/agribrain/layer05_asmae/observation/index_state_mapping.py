"""
V72: Central index-to-state mapping registry.

Maps each spectral index / SAR feature to:
  - Target agronomic states it updates
  - Forbidden states it must NOT update
  - Observation noise model parameters
  - Crop-stage modifier behavior
  - Confidence contribution

Hard rules (user-approved, non-negotiable):
  - SAR must NOT directly update chlorophyll or vigor
  - NDRE must NOT update water state
  - Root-zone water changes slower than surface wetness
  - Each observation update declares observed feature, target states,
    forbidden states, noise model, crop-stage modifier, confidence contribution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from ..config import (
    IDX_BARE_SOIL,
    IDX_BIOTIC,
    IDX_CANOPY_WATER,
    IDX_CHLOROPHYLL,
    IDX_LAI,
    IDX_PHENOLOGY,
    IDX_ROOT_ZONE_WATER,
    IDX_SALINITY,
    IDX_STRESS_MEMORY,
    IDX_STRUCTURE,
    IDX_SURFACE_WETNESS,
    IDX_THERMAL,
    IDX_VIGOR,
)


@dataclass(frozen=True)
class IndexStateMapping:
    """Mapping from a single observation index to agronomic states.

    Attributes:
        index_name: Name of the observation (e.g. "ndvi", "sar_vh").
        sensor: Source sensor ("S2", "S1", "S5P", "EXTERNAL").
        target_state_indices: State indices this observation updates.
        forbidden_state_indices: State indices this observation must NOT update.
        base_noise_sigma: Base observation noise standard deviation.
        noise_floor: Minimum noise (prevents over-confident updates).
        crop_stage_noise_multiplier: Extra noise during specific phenology stages.
        confidence_contribution: How much this observation contributes to confidence.
        description: Human-readable description.
    """
    index_name: str
    sensor: str
    target_state_indices: Tuple[int, ...]
    forbidden_state_indices: Tuple[int, ...] = ()
    base_noise_sigma: float = 0.05
    noise_floor: float = 0.02
    crop_stage_noise_multiplier: Dict[str, float] = field(default_factory=dict)
    confidence_contribution: float = 0.5
    description: str = ""


# ── REGISTRY ────────────────────────────────────────────────────────────────

INDEX_STATE_REGISTRY: Dict[str, IndexStateMapping] = {}


def _register(m: IndexStateMapping) -> None:
    INDEX_STATE_REGISTRY[m.index_name] = m


# ── Optical indices (Sentinel-2) ────────────────────────────────────────────

_register(IndexStateMapping(
    index_name="ndvi",
    sensor="S2",
    target_state_indices=(IDX_VIGOR, IDX_LAI),
    forbidden_state_indices=(IDX_ROOT_ZONE_WATER, IDX_SURFACE_WETNESS, IDX_STRUCTURE),
    base_noise_sigma=0.04,
    noise_floor=0.02,
    crop_stage_noise_multiplier={"bare_soil": 1.5, "senescence": 1.3},
    confidence_contribution=0.7,
    description="Vigor and LAI from normalized difference vegetation index",
))

_register(IndexStateMapping(
    index_name="evi",
    sensor="S2",
    target_state_indices=(IDX_VIGOR,),
    forbidden_state_indices=(IDX_ROOT_ZONE_WATER, IDX_SURFACE_WETNESS, IDX_STRUCTURE),
    base_noise_sigma=0.04,
    noise_floor=0.02,
    crop_stage_noise_multiplier={"dense_canopy": 0.8},
    confidence_contribution=0.6,
    description="Vigor from enhanced vegetation index (better in dense canopy)",
))

_register(IndexStateMapping(
    index_name="savi",
    sensor="S2",
    target_state_indices=(IDX_VIGOR, IDX_BARE_SOIL),
    forbidden_state_indices=(IDX_ROOT_ZONE_WATER, IDX_SURFACE_WETNESS),
    base_noise_sigma=0.05,
    noise_floor=0.02,
    crop_stage_noise_multiplier={"early_veg": 0.9},
    confidence_contribution=0.5,
    description="Early vegetation and bare soil from soil-adjusted VI",
))

_register(IndexStateMapping(
    index_name="ndre",
    sensor="S2",
    target_state_indices=(IDX_CHLOROPHYLL,),
    forbidden_state_indices=(
        IDX_CANOPY_WATER, IDX_ROOT_ZONE_WATER, IDX_SURFACE_WETNESS, IDX_STRUCTURE,
    ),
    base_noise_sigma=0.05,
    noise_floor=0.02,
    crop_stage_noise_multiplier={"bare_soil": 2.0, "senescence": 1.5},
    confidence_contribution=0.6,
    description="Chlorophyll from normalized difference red-edge",
))

_register(IndexStateMapping(
    index_name="reip",
    sensor="S2",
    target_state_indices=(IDX_CHLOROPHYLL,),
    forbidden_state_indices=(
        IDX_CANOPY_WATER, IDX_ROOT_ZONE_WATER, IDX_SURFACE_WETNESS,
    ),
    base_noise_sigma=0.06,
    noise_floor=0.03,
    confidence_contribution=0.5,
    description="Chlorophyll from red-edge inflection point",
))

_register(IndexStateMapping(
    index_name="ndmi",
    sensor="S2",
    target_state_indices=(IDX_CANOPY_WATER,),
    forbidden_state_indices=(IDX_CHLOROPHYLL, IDX_STRUCTURE),
    base_noise_sigma=0.05,
    noise_floor=0.02,
    confidence_contribution=0.6,
    description="Canopy water content from normalized difference moisture index",
))

_register(IndexStateMapping(
    index_name="ndwi",
    sensor="S2",
    target_state_indices=(IDX_SURFACE_WETNESS,),
    forbidden_state_indices=(IDX_CHLOROPHYLL, IDX_VIGOR),
    base_noise_sigma=0.06,
    noise_floor=0.03,
    crop_stage_noise_multiplier={"dry_season": 0.8},
    confidence_contribution=0.4,
    description="Surface wetness event from NDWI (decays quickly)",
))

_register(IndexStateMapping(
    index_name="bsi",
    sensor="S2",
    target_state_indices=(IDX_BARE_SOIL,),
    forbidden_state_indices=(IDX_VIGOR, IDX_LAI, IDX_CHLOROPHYLL),
    base_noise_sigma=0.06,
    noise_floor=0.03,
    confidence_contribution=0.4,
    description="Bare soil fraction (salinity confounder)",
))

_register(IndexStateMapping(
    index_name="nbr",
    sensor="S2",
    target_state_indices=(IDX_VIGOR, IDX_BARE_SOIL),
    forbidden_state_indices=(IDX_CHLOROPHYLL, IDX_ROOT_ZONE_WATER),
    base_noise_sigma=0.07,
    noise_floor=0.03,
    confidence_contribution=0.3,
    description="Disturbance/harvest residue from NBR",
))

# ── SAR indices (Sentinel-1) ───────────────────────────────────────────────

_register(IndexStateMapping(
    index_name="sar_vv",
    sensor="S1",
    target_state_indices=(IDX_SURFACE_WETNESS, IDX_ROOT_ZONE_WATER),
    forbidden_state_indices=(
        IDX_VIGOR, IDX_CHLOROPHYLL, IDX_LAI, IDX_PHENOLOGY,
    ),
    base_noise_sigma=0.08,
    noise_floor=0.04,
    confidence_contribution=0.4,
    description="Surface roughness/wetness from SAR VV backscatter",
))

_register(IndexStateMapping(
    index_name="sar_vh",
    sensor="S1",
    target_state_indices=(IDX_STRUCTURE,),
    forbidden_state_indices=(
        IDX_VIGOR, IDX_CHLOROPHYLL, IDX_LAI, IDX_PHENOLOGY,
    ),
    base_noise_sigma=0.08,
    noise_floor=0.04,
    confidence_contribution=0.4,
    description="Vegetation structure/volume from SAR VH backscatter",
))

_register(IndexStateMapping(
    index_name="sar_ratio",
    sensor="S1",
    target_state_indices=(IDX_STRUCTURE, IDX_SURFACE_WETNESS),
    forbidden_state_indices=(
        IDX_VIGOR, IDX_CHLOROPHYLL, IDX_LAI, IDX_PHENOLOGY,
    ),
    base_noise_sigma=0.09,
    noise_floor=0.04,
    confidence_contribution=0.3,
    description="Structure-moisture coupling from VV/VH ratio",
))

_register(IndexStateMapping(
    index_name="delta_sar",
    sensor="S1",
    target_state_indices=(IDX_SURFACE_WETNESS, IDX_BARE_SOIL),
    forbidden_state_indices=(IDX_VIGOR, IDX_CHLOROPHYLL, IDX_LAI),
    base_noise_sigma=0.10,
    noise_floor=0.05,
    confidence_contribution=0.3,
    description="Change detection: harvest, tillage, flooding from ΔSAR",
))


# ── MESIA In-Situ Terrestrial RF Features (Monograph §146 / P-08) ────────────

_register(IndexStateMapping(
    index_name="mesia_root_zone_water",
    sensor="MESIA",
    target_state_indices=(IDX_ROOT_ZONE_WATER,),
    forbidden_state_indices=(
        IDX_VIGOR, IDX_CHLOROPHYLL, IDX_LAI, IDX_PHENOLOGY, IDX_STRUCTURE,
    ),
    base_noise_sigma=0.03,
    noise_floor=0.015,
    confidence_contribution=0.85,
    description="Sub-surface volumetric water content from MESIA in-situ RF tomography",
))

_register(IndexStateMapping(
    index_name="mesia_canopy_water",
    sensor="MESIA",
    target_state_indices=(IDX_CANOPY_WATER,),
    forbidden_state_indices=(
        IDX_ROOT_ZONE_WATER, IDX_CHLOROPHYLL, IDX_PHENOLOGY,
    ),
    base_noise_sigma=0.04,
    noise_floor=0.02,
    confidence_contribution=0.80,
    description="Canopy water content from MESIA terrestrial multi-frequency link attenuation",
))

_register(IndexStateMapping(
    index_name="mesia_surface_wetness",
    sensor="MESIA",
    target_state_indices=(IDX_SURFACE_WETNESS,),
    forbidden_state_indices=(
        IDX_VIGOR, IDX_CHLOROPHYLL, IDX_LAI, IDX_PHENOLOGY,
    ),
    base_noise_sigma=0.04,
    noise_floor=0.02,
    confidence_contribution=0.75,
    description="Surface wetness event detection from MESIA multipath ground-bounce",
))

_register(IndexStateMapping(
    index_name="mesia_gnssr_in_situ_vwc",
    sensor="MESIA",
    target_state_indices=(IDX_ROOT_ZONE_WATER,),
    forbidden_state_indices=(
        IDX_VIGOR, IDX_CHLOROPHYLL, IDX_LAI, IDX_PHENOLOGY, IDX_STRUCTURE,
    ),
    base_noise_sigma=0.03,
    noise_floor=0.015,
    confidence_contribution=0.85,
    description="Volumetric soil water content from in-situ GNSS-R multipath SNR interferometry",
))

_register(IndexStateMapping(
    index_name="mesia_cellular_canopy_water",
    sensor="MESIA",
    target_state_indices=(IDX_CANOPY_WATER,),
    forbidden_state_indices=(
        IDX_ROOT_ZONE_WATER, IDX_CHLOROPHYLL, IDX_PHENOLOGY, IDX_VIGOR, IDX_LAI,
    ),
    base_noise_sigma=0.04,
    noise_floor=0.02,
    confidence_contribution=0.80,
    description="Canopy water content from public 4G/5G base station forward-scatter radar",
))

_register(IndexStateMapping(
    index_name="mesia_dvb_deep_soil_water",
    sensor="MESIA",
    target_state_indices=(IDX_ROOT_ZONE_WATER,),
    forbidden_state_indices=(
        IDX_VIGOR, IDX_CHLOROPHYLL, IDX_LAI, IDX_PHENOLOGY, IDX_STRUCTURE,
    ),
    base_noise_sigma=0.04,
    noise_floor=0.02,
    confidence_contribution=0.80,
    description="Deep root-zone soil water content (30-100cm) from terrestrial DVB-T2 UHF broadcast",
))

_register(IndexStateMapping(
    index_name="mesia_spaceborne_gnssr_vwc",
    sensor="MESIA",
    target_state_indices=(IDX_ROOT_ZONE_WATER,),
    forbidden_state_indices=(
        IDX_VIGOR, IDX_CHLOROPHYLL, IDX_LAI, IDX_PHENOLOGY, IDX_STRUCTURE,
    ),
    base_noise_sigma=0.04,
    noise_floor=0.02,
    confidence_contribution=0.75,
    description="100% pure remote soil moisture from NASA CYGNSS / Spire spaceborne GNSS-R",
))

_register(IndexStateMapping(
    index_name="mesia_cml_humidity",
    sensor="MESIA",
    target_state_indices=(IDX_SURFACE_WETNESS,),
    forbidden_state_indices=(
        IDX_VIGOR, IDX_CHLOROPHYLL, IDX_LAI, IDX_PHENOLOGY,
    ),
    base_noise_sigma=0.05,
    noise_floor=0.025,
    confidence_contribution=0.70,
    description="Near-surface humidity & rain from Commercial Microwave Link (CML) telecom backhaul",
))

_register(IndexStateMapping(
    index_name="mesia_wifi_csi_canopy_foliar",
    sensor="MESIA",
    target_state_indices=(IDX_CANOPY_WATER,),
    forbidden_state_indices=(
        IDX_ROOT_ZONE_WATER, IDX_CHLOROPHYLL, IDX_PHENOLOGY, IDX_VIGOR, IDX_LAI, IDX_STRUCTURE,
    ),
    base_noise_sigma=0.035,
    noise_floor=0.018,
    confidence_contribution=0.82,
    description="Foliar canopy water & perimeter mass scattering from 802.11bf Wi-Fi CSI OFDM subcarriers",
))



# ── Accessors ───────────────────────────────────────────────────────────────

def get_mapping(index_name: str) -> Optional[IndexStateMapping]:
    """Get the mapping for a given index name."""
    return INDEX_STATE_REGISTRY.get(index_name)


def get_mappings_for_sensor(sensor: str) -> List[IndexStateMapping]:
    """Get all mappings for a given sensor."""
    return [m for m in INDEX_STATE_REGISTRY.values() if m.sensor == sensor]


def validate_forbidden_state_update(
    index_name: str, state_index: int,
) -> bool:
    """Check if updating state_index from index_name is forbidden.

    Returns True if the update is FORBIDDEN (should be blocked).
    """
    mapping = get_mapping(index_name)
    if mapping is None:
        return False
    return state_index in mapping.forbidden_state_indices


def get_all_index_names() -> List[str]:
    """Return all registered index names."""
    return list(INDEX_STATE_REGISTRY.keys())

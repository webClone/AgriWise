"""Scientific Contracts — State Schema Versions & Order.

Isolated from world_model and layer packages.
"""

from __future__ import annotations

STATE_SCHEMA_VERSION = "asmae_state_v1_13"
STATE_SUPPORT_LEDGER_SCHEMA_VERSION = "state_support_record_v2"
STATE_STATUS_CONTRACT_VERSION = "state_status_v1"
SCIENTIFIC_CONTRACTS_VERSION = "scientific_contracts_v1"
LAYER10_PUBLICATION_SCHEMA_VERSION = "l10_pub_v2_r5"

STATE_ORDER = (
    "vigor", "lai", "chlorophyll", "canopy_water", "root_zone_water",
    "surface_wetness_event", "structure", "bare_soil_fraction",
    "salinity_stress", "thermal_stress", "biotic_confounder_risk",
    "phenology_progress", "stress_memory",
)

# External layers historically used several display and raster names for the
# same scientific state.  All support-ledger lookups must pass through this
# resolver so authority cannot fall back to run-level evidence merely because
# a producer used a compatibility name.
STATE_KEY_ALIASES = {
    "bare_soil": "bare_soil_fraction",
    "bare_soil_fraction": "bare_soil_fraction",
    "canopy_water": "canopy_water",
    "chlorophyll": "chlorophyll",
    "lai": "lai",
    "root_zone_water": "root_zone_water",
    "surface_wetness_event": "surface_wetness_event",
    "structure": "structure",
    "vigor": "vigor",
    "salinity_stress": "salinity_stress",
    "salinity": "salinity_stress",
    "thermal_stress": "thermal_stress",
    "thermal": "thermal_stress",
    "biotic_confounder_risk": "biotic_confounder_risk",
    "biotic_risk": "biotic_confounder_risk",
    "phenology_progress": "phenology_progress",
    "phenology": "phenology_progress",
    "stress_memory": "stress_memory",
}


# Explicit surface type and alias to canonical state mapping.
# Eliminates substring collisions (e.g. CANOPY vs CANOPY_WATER).
SURFACE_TO_CANONICAL_STATE: dict[str, str] = {
    "ASMAE_VIGOR": "vigor",
    "CANOPY_ASMAE_VIGOR": "vigor",
    "ASMAE_LAI": "lai",
    "ASMAE_CHLOROPHYLL": "chlorophyll",
    "NUTRIENT_ASMAE_CHLOROPHYLL_PROXY": "chlorophyll",
    "ASMAE_CANOPY_WATER": "canopy_water",
    "WATER_ASMAE_CANOPY_WATER": "canopy_water",
    "ASMAE_ROOT_ZONE_WATER": "root_zone_water",
    "WATER_ASMAE_ROOT_ZONE_WATER": "root_zone_water",
    "ASMAE_SURFACE_WETNESS_EVENT": "surface_wetness_event",
    "ASMAE_STRUCTURE": "structure",
    "ASMAE_BARE_SOIL": "bare_soil_fraction",
    "ASMAE_BARE_SOIL_FRACTION": "bare_soil_fraction",
    "ASMAE_SALINITY_STRESS": "salinity_stress",
    "SALINITY_ASMAE_STRESS": "salinity_stress",
    "ASMAE_THERMAL_STRESS": "thermal_stress",
    "ASMAE_BIOTIC_CONFOUNDER_RISK": "biotic_confounder_risk",
    "ASMAE_PHENOLOGY_PROGRESS": "phenology_progress",
    "ASMAE_STRESS_MEMORY": "stress_memory",
}


def canonical_state_key(value: str | None) -> str:
    """Return the canonical 13-state ledger key for a surface/feature alias."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    if upper in SURFACE_TO_CANONICAL_STATE:
        return SURFACE_TO_CANONICAL_STATE[upper]
    key = raw.lower()
    if key.startswith("asmae_"):
        key = key[6:]
    return STATE_KEY_ALIASES.get(key, key)


# Canonical 13-state catalog mapping product identities, units, ranges, uncertainty, and authority ceilings
CANONICAL_13_STATE_CATALOG: dict[str, dict[str, Any]] = {
    "vigor": {
        "state": "vigor",
        "surface_type": "ASMAE_VIGOR",
        "semantic_name": "Canopy photosynthetic activity",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "PRESCRIPTION_ELIGIBLE",
        "identifiability_class": "INDIRECTLY_CONSTRAINED",
    },
    "lai": {
        "state": "lai",
        "surface_type": "ASMAE_LAI",
        "semantic_name": "Leaf area index",
        "units": "index",
        "render_range": (0.0, 8.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "DIAGNOSTIC",
        "identifiability_class": "PARTIALLY_IDENTIFIED",
    },
    "chlorophyll": {
        "state": "chlorophyll",
        "surface_type": "ASMAE_CHLOROPHYLL",
        "semantic_name": "Foliar chlorophyll content",
        "units": "ug/cm2",
        "render_range": (0.0, 80.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "DIAGNOSTIC",
        "identifiability_class": "PARTIALLY_IDENTIFIED",
    },
    "canopy_water": {
        "state": "canopy_water",
        "surface_type": "ASMAE_CANOPY_WATER",
        "semantic_name": "Canopy water content",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "DIAGNOSTIC",
        "identifiability_class": "INDIRECTLY_CONSTRAINED",
    },
    "root_zone_water": {
        "state": "root_zone_water",
        "surface_type": "ASMAE_ROOT_ZONE_WATER",
        "semantic_name": "Root-zone soil moisture",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "DIAGNOSTIC",
        "identifiability_class": "INDIRECTLY_CONSTRAINED",
    },
    "surface_wetness_event": {
        "state": "surface_wetness_event",
        "surface_type": "ASMAE_SURFACE_WETNESS_EVENT",
        "semantic_name": "Event-based surface water",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "DIAGNOSTIC",
        "identifiability_class": "INDIRECTLY_CONSTRAINED",
    },
    "structure": {
        "state": "structure",
        "surface_type": "ASMAE_STRUCTURE",
        "semantic_name": "Canopy/biomass structure",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "DIAGNOSTIC",
        "identifiability_class": "INDIRECTLY_CONSTRAINED",
    },
    "bare_soil_fraction": {
        "state": "bare_soil_fraction",
        "surface_type": "ASMAE_BARE_SOIL",
        "semantic_name": "Exposed soil fraction",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "PRESCRIPTION_ELIGIBLE",
        "identifiability_class": "INDIRECTLY_CONSTRAINED",
    },
    "salinity_stress": {
        "state": "salinity_stress",
        "surface_type": "ASMAE_SALINITY_STRESS",
        "semantic_name": "Salinity-induced stress",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "MONITORING_ONLY",
        "identifiability_class": "HYPOTHESIS_ONLY",
    },
    "thermal_stress": {
        "state": "thermal_stress",
        "surface_type": "ASMAE_THERMAL_STRESS",
        "semantic_name": "Thermal stress",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "DIAGNOSTIC",
        "identifiability_class": "INDIRECTLY_CONSTRAINED",
    },
    "biotic_confounder_risk": {
        "state": "biotic_confounder_risk",
        "surface_type": "ASMAE_BIOTIC_CONFOUNDER_RISK",
        "semantic_name": "Biotic pressure confounding risk",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "MONITORING_ONLY",
        "identifiability_class": "HYPOTHESIS_ONLY",
    },
    "phenology_progress": {
        "state": "phenology_progress",
        "surface_type": "ASMAE_PHENOLOGY_PROGRESS",
        "semantic_name": "Phenological stage progress",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "DIAGNOSTIC",
        "identifiability_class": "PARTIALLY_IDENTIFIED",
    },
    "stress_memory": {
        "state": "stress_memory",
        "surface_type": "ASMAE_STRESS_MEMORY",
        "semantic_name": "EWMA stress accumulator",
        "units": "fraction",
        "render_range": (0.0, 1.0),
        "uncertainty_association": "posterior_uncertainty",
        "authority_ceiling": "VISUALIZATION",
        "identifiability_class": "NOT_IDENTIFIED",
    },
}

CANONICAL_STATE_TO_SURFACE: dict[str, str] = {
    k: str(v["surface_type"]) for k, v in CANONICAL_13_STATE_CATALOG.items()
}


def get_state_catalog_entry(state_or_surface: str | None) -> dict[str, Any]:
    """Return the canonical 13-state catalog specification for a state or surface name."""
    if not state_or_surface:
        return {}
    key = canonical_state_key(state_or_surface)
    return dict(CANONICAL_13_STATE_CATALOG.get(key, {}))



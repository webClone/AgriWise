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


def canonical_state_key(value: str | None) -> str:
    """Return the canonical 13-state ledger key for a surface/feature alias."""
    key = str(value or "").strip().lower()
    if key.startswith("asmae_"):
        key = key[6:]
    return STATE_KEY_ALIASES.get(key, key)

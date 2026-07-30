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

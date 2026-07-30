# Approved validation sources from external systems
APPROVED_EXTERNAL_VALIDATION_SOURCES = {
    "agronomist_observation", "soil_lab", "calibrated_sensor", 
    "farmer_observation", "field_scout", "drone_image", 
    "farmer_photo", "harvest_record", "insurance_inspection"
}

# Variable mapping keys
VAR_VIGOR = "vigor"
VAR_NDVI = "ndvi"
VAR_CANOPY_WATER = "canopy_water"
VAR_SALINITY_STRESS = "salinity_stress"
VAR_BIOTIC_CONFOUNDER = "biotic_confounder"

# Radiometric tolerances (mean delta allowed between upscaled 1m and coarse satellite/BMA)
RADIOMETRIC_TOLERANCE_BY_VARIABLE = {
    VAR_VIGOR: 0.15,
    VAR_NDVI: 0.15,
    VAR_CANOPY_WATER: 0.20,
    VAR_SALINITY_STRESS: 0.18,
    VAR_BIOTIC_CONFOUNDER: 0.30,
}
DEFAULT_RADIOMETRIC_TOLERANCE = 0.25

# Contradiction tolerances (new manual validation delta allowed before revoking)
CONTRADICTION_TOLERANCE_BY_VARIABLE = {
    VAR_VIGOR: 0.25,
    VAR_NDVI: 0.25,
    VAR_CANOPY_WATER: 0.25,
    VAR_SALINITY_STRESS: 0.20,
    VAR_BIOTIC_CONFOUNDER: 0.30,
}
DEFAULT_CONTRADICTION_TOLERANCE = 0.50

# Minimum eligibility requirements
MIN_TOTAL_TELEMETRY_ITEMS = 10
MIN_VALID_SCENES = 5
MIN_EXTERNAL_VALIDATION_EVENTS = 3
MIN_DISTINCT_VALIDATION_DATES = 2
MIN_DISTINCT_VALIDATION_SOURCES = 2
MIN_SPATIAL_HOLDOUT_CELLS = 3
MIN_TEMPORAL_SEPARATION_HOURS = 24

# Retrovalidation score threshold
MIN_RETRO_SCORE = 0.85

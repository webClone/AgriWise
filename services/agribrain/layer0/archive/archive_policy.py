"""
Sentinel Archive Policy for AgriBrain.
Implements the core boundaries and version tags for V90.7.
"""

# Hard policy boundaries
ARCHIVE_CAN_CREATE_GROUND_TRUTH = False
ARCHIVE_CAN_CERTIFY_1M_ALONE = False
ARCHIVE_CAN_CREATE_TRAINING_LABEL = False
ARCHIVE_CAN_TRIGGER_PRESCRIPTION = False
ARCHIVE_CAN_UPDATE_LAYER1_STATE_DIRECTLY = False

# Version tags to avoid silent cache reuse on policy updates
ARCHIVE_POLICY_VERSION = "v90_7_archive_policy_v1"
QUALITY_POLICY_VERSION = "v90_7_quality_policy_v1"
HARMONIZATION_POLICY_VERSION = "v90_7_harmonization_policy_v1"
OPERATOR_POLICY_VERSION = "v90_7_operator_policy_v1"
RETROVALIDATION_POLICY_VERSION = "v90_7_retrovalidation_policy_v1"

ARCHIVE_MODES = {
    "quick_monitoring": {
        "lookback_days": 180,
        "purpose": "fast current monitoring",
    },
    "seasonal": {
        "lookback": "current_crop_season",
        "purpose": "crop-season state context",
    },
    "historical_1y": {
        "lookback_years": 1,
        "purpose": "short-term historical calibration and validation",
    },
    "historical_3y": {
        "lookback_years": 3,
        "purpose": "plot behavior calibration",
    },
    "historical_5y": {
        "lookback_years": 5,
        "purpose": "retrovalidation and BMA scoring",
    },
    "historical_full": {
        "start_policy": "sentinel_archive_start",
        "purpose": "long-term historical baseline and certification support",
    },
}

PILOT_BUDGETS = {
    "offline_fixture": {
        "cold_seconds_per_plot_year": 5.0,
        "warm_seconds_per_plot_year": 0.5,
        "storage_mb_per_plot_year_warning": 50,
    },
    "live_metadata_only": {
        "cold_seconds_per_plot_year": 30.0,
        "warm_seconds_per_plot_year": 2.0,
        "storage_mb_per_plot_year_warning": 5,
    },
    "live_raster_pilot": {
        "cold_seconds_per_plot_year": 180.0,
        "warm_seconds_per_plot_year": 5.0,
        "storage_mb_per_plot_year_warning": 250,
    },
}


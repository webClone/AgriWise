"""
Layer 1 Evidence Validation.

Validates evidence items before admission to the ledger.
Quarantines invalid evidence with structured reasons.

Checks:
  - ID, plot_id, variable non-empty
  - Source family, observation type, spatial scope canonical
  - Unit canonical (if provided)
  - Confidence/reliability bounds [0, 1]
  - Forecast source consistency
  - Provenance ref present
  - NaN/Inf in numeric values
  - Physical value bounds for known variables
"""

from __future__ import annotations

import math
from typing import List

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real

from .schemas import (
    CANONICAL_UNITS,
    EvidenceItem,
    QuarantinedEvidence,
    SOURCE_FAMILIES,
    SPATIAL_SCOPES,
    OBSERVATION_TYPES,
    DATA_STATUSES,
    DATA_STATUS_CEILING,
)


def validate_evidence(item: EvidenceItem) -> List[str]:
    """Validate a single evidence item. Returns list of violation messages."""
    violations: List[str] = []

    if not item.evidence_id:
        violations.append("EMPTY_EVIDENCE_ID")
    if not item.plot_id:
        violations.append("EMPTY_PLOT_ID")
    if not item.variable:
        violations.append("EMPTY_VARIABLE")
    if item.source_family not in SOURCE_FAMILIES:
        violations.append(f"INVALID_SOURCE_FAMILY:{item.source_family}")
    if item.observation_type not in OBSERVATION_TYPES:
        violations.append(f"INVALID_OBSERVATION_TYPE:{item.observation_type}")
    if item.spatial_scope not in SPATIAL_SCOPES:
        violations.append(f"INVALID_SPATIAL_SCOPE:{item.spatial_scope}")

    # Unit validation: if provided, must be canonical
    if item.unit is not None and item.unit not in CANONICAL_UNITS:
        violations.append(f"NON_CANONICAL_UNIT:{item.unit}")

    # Confidence and reliability bounds: strictly finite real and non-boolean
    fin_conf = finite_real(item.confidence)
    if fin_conf is None or not (0.0 <= fin_conf <= 1.0):
        violations.append(f"CONFIDENCE_OUT_OF_BOUNDS:{item.confidence}")
    fin_rel = finite_real(item.reliability)
    if fin_rel is None or not (0.0 <= fin_rel <= 1.0):
        violations.append(f"RELIABILITY_OUT_OF_BOUNDS:{item.reliability}")

    # Check data_status is set and valid
    status = getattr(item, "data_status", None)
    if status is None:
        violations.append("MISSING_DATA_STATUS")
        status = "unknown"

    if status not in DATA_STATUSES:
        violations.append(f"INVALID_DATA_STATUS:{status}")
    else:
        # Confidence ceilings (using centralized DATA_STATUS_CEILING)
        if status in DATA_STATUS_CEILING and item.confidence > DATA_STATUS_CEILING[status]:
            violations.append(f"{status.upper()}_CONFIDENCE_EXCEEDS_CEILING:{item.confidence}")

        # Behavioral rules
        if status in ("simulated", "reconstruction"):
            if not item.diagnostic_only or item.state_update_allowed:
                violations.append("SIMULATED_DATA_MUST_BE_DIAGNOSTIC_AND_NOT_STATE_UPDATE")
        elif status == "unavailable":
            if not item.diagnostic_only or item.state_update_allowed:
                violations.append("UNAVAILABLE_DATA_MUST_BE_DIAGNOSTIC")
        elif status == "fallback":
            if not item.diagnostic_only or item.state_update_allowed:
                violations.append("FALLBACK_DATA_MUST_BE_DIAGNOSTIC_AND_NOT_STATE_UPDATE")
        elif status == "assimilated":
            if item.observation_type == "measurement":
                violations.append("ASSIMILATED_DATA_CANNOT_BE_MEASUREMENT")

        # Contradiction checks V92.4-BC.10.5
        if item.source_reality == "raster_composite_proxy" and status == "observed":
            violations.append("PROXY_SOURCE_CANNOT_BE_OBSERVED")

        if item.production_usable is False and item.state_update_allowed:
            violations.append("NON_PRODUCTION_EVIDENCE_CANNOT_UPDATE_STATE")

        if (item.confidence == 0.0 or item.reliability == 0.0) and item.state_update_allowed:
            violations.append("ZERO_CONFIDENCE_OR_RELIABILITY_CANNOT_UPDATE_STATE")

        if (
            item.real_provider_product is False
            and not item.diagnostic_only
            and item.truth_class != "provider_plot_timeseries"
        ):
            violations.append("NON_PROVIDER_PRODUCT_MUST_BE_DIAGNOSTIC")

        if item.truth_class in {
            "fallback_default",
            "experimental_visual_detail",
            "raster_composite_proxy",
            "estimated_model",
        } and item.state_update_allowed:
            violations.append("LOW_TRUTH_CLASS_CANNOT_UPDATE_STATE")

    # Forecast must not claim to be observation
    if item.observation_type == "forecast" and item.source_family not in ("weather_forecast", "history"):
        violations.append("FORECAST_FROM_NON_FORECAST_SOURCE")

    # Provenance ref should be present
    if not item.provenance_ref:
        violations.append("MISSING_PROVENANCE_REF")

    # Physical value bounds and numeric qualification for known variables
    _BOUNDS = {
        "ndvi": (-1.0, 1.0), "ndmi": (-1.0, 1.0), "ndre": (-1.0, 1.0),
        "evi": (-1.0, 1.0), "bsi": (-1.0, 1.0),
        "soil_moisture_vwc": (0.0, 0.65), "vegetation_fraction": (0.0, 1.0),
        "bare_soil_fraction": (0.0, 1.0), "canopy_cover": (0.0, 1.0),
        # Weather physical boundaries
        "weather_temp_mean": (-50.0, 60.0),
        "weather_temp_max": (-50.0, 60.0),
        "weather_temp_min": (-50.0, 60.0),
        "weather_precipitation_mm": (0.0, 500.0),
        "weather_vpd_kpa": (0.0, 15.0),
        "temp_max": (-50.0, 60.0),
        "temp_min": (-50.0, 60.0),
        "precipitation": (0.0, 500.0),
        "et0": (0.0, 50.0),
        # Sensor probe physical boundaries
        "ec": (0.0, 20.0),
        "soil_temperature": (-40.0, 60.0),
    }

    _QUANTITATIVE_VARIABLES = frozenset({
        "soil_clay_pct", "soil_sand_pct", "soil_silt_pct",
        "soil_organic_carbon", "soil_ph", "soil_cec",
        "soil_bulk_density", "elevation", "slope", "aspect",
        "wapor_et", "wapor_aet", "wapor",
        "soil_moisture", "soil_moisture_vwc",
    })

    NUMERIC_UNITS = {
        "degC", "fraction", "percent", "mm", "mm_day", "m_s", "kPa",
        "dS_m", "pH", "kg_ha", "W_m2", "umol_m2_s", "dBm", "dB",
        "m2", "m", "cm", "L", "L_min", "deg", "min", "bar", "V",
        "mm_h", "ratio", "score", "index", "count", "linear_power", "db",
    }

    is_quantitative = (
        item.variable in _BOUNDS
        or item.variable in _QUANTITATIVE_VARIABLES
        or (item.unit is not None and item.unit in NUMERIC_UNITS)
        or (
            item.observation_type in ("measurement", "model_estimate", "state_estimate", "derived_feature")
            and item.unit not in ("bool", "class")
            and item.variable not in ("crop_stage", "variety", "texture_class", "soil_texture_class", "landcover", "land_use", "cropland")
        )
    )

    if is_quantitative:
        if isinstance(item.value, bool):
            violations.append(f"BOOLEAN_VALUE_DISALLOWED:{item.variable}={item.value}")
        else:
            val = finite_real(item.value)
            if val is None:
                violations.append(f"NON_FINITE_OR_MALFORMED_VALUE:{item.variable}={item.value!r}")
            elif item.variable in _BOUNDS:
                lo, hi = _BOUNDS[item.variable]
                if val < lo or val > hi:
                    violations.append(
                        f"VALUE_OUT_OF_BOUNDS:{item.variable}={val:.4f} not in [{lo},{hi}]"
                    )
    else:
        # General non-finite check for other numeric items
        if isinstance(item.value, bool):
            if item.observation_type in ("measurement", "model_estimate", "derived_feature", "state_estimate"):
                violations.append(f"BOOLEAN_VALUE_DISALLOWED:{item.variable}={item.value}")
        elif isinstance(item.value, float) and (math.isnan(item.value) or math.isinf(item.value)):
            violations.append(f"NAN_INF_VALUE:{item.value}")

    return violations


def quarantine_evidence(
    item: EvidenceItem, violations: List[str]
) -> QuarantinedEvidence:
    """Create a quarantine record for invalid evidence."""
    severity = "blocking" if len(violations) >= 3 else (
        "error" if len(violations) >= 1 else "warning"
    )
    return QuarantinedEvidence(
        evidence_id=item.evidence_id,
        reason_codes=violations,
        original_source_family=item.source_family,
        variable=item.variable,
        severity=severity,
        can_override=False,
        original_value=item.value,
        original_unit=item.unit,
    )

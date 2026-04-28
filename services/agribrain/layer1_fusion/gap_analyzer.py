"""
Layer 1 Gap Analyzer.

Detects missing evidence sources and computes gap severity.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Set

from .schemas import EvidenceGap, EvidenceItem, GAP_TYPES


# Gap detection rules
_GAP_RULES = [
    {
        "type": "NO_RECENT_SENTINEL2",
        "requires_source": "sentinel2",
        "severity": "warning",
        "affected": ["ndvi_context", "vegetation_trend", "chlorophyll_proxy"],
        "action": "Wait for next S2 overpass or check cloud status",
    },
    {
        "type": "NO_RECENT_SENTINEL1",
        "requires_source": "sentinel1",
        "severity": "info",
        "affected": ["sar_wetness_proxy", "flood_detection"],
        "action": "SAR data may have 6-12 day revisit gap",
    },
    {
        "type": "NO_SENSOR_FOR_ROOT_ZONE",
        "requires_source": "sensor",
        "requires_variable_contains": "moisture",
        "severity": "warning",
        "affected": ["soil_moisture_vwc", "irrigation_response"],
        "action": "Deploy soil moisture sensor or use SAR proxy",
    },
    {
        "type": "NO_RAIN_GAUGE",
        "requires_source": "sensor",
        "requires_variable_contains": "rain",
        "severity": "info",
        "affected": ["precipitation_ground_truth"],
        "action": "Relying on weather model precipitation only",
    },
    {
        "type": "NO_IRRIGATION_FLOW_SENSOR",
        "requires_source": "sensor",
        "requires_variable_contains": "irrigation",
        "severity": "info",
        "affected": ["irrigation_volume", "water_balance"],
        "action": "Relying on user-declared irrigation events only",
    },
    {
        "type": "NO_CROP_STAGE_DECLARED",
        "requires_source": "user_event",
        "requires_variable_contains": "planting",
        "severity": "info",
        "affected": ["phenology_context", "gdd_tracking"],
        "action": "User should declare planting date",
    },
    {
        "type": "NO_VALID_WEATHER_FORECAST",
        "requires_source": "weather_forecast",
        "severity": "warning",
        "affected": ["forecast_precip", "forecast_et0", "risk_windows"],
        "action": "Check weather provider availability",
    },
    {
        "type": "NO_GEO_CONTEXT",
        "requires_source": "geo_context",
        "severity": "warning",
        "affected": ["elevation", "slope", "landcover", "trust_modifiers"],
        "action": "Geo context engine may have failed",
    },
    {
        "type": "NO_LANDCOVER_VALIDITY",
        "requires_source": "geo_context",
        "requires_variable_contains": "landcover",
        "severity": "info",
        "affected": ["plot_validity", "contamination_risk"],
        "action": "Landcover data may be unavailable",
    },
    {
        "type": "NO_WAPOR_CONTEXT",
        "requires_source": "geo_context",
        "requires_variable_contains": "wapor",
        "severity": "info",
        "affected": ["et_context"],
        "action": "WaPOR coverage may be limited",
    },
    {
        "type": "NO_USER_MANAGEMENT_EVENTS",
        "requires_source": "user_event",
        "severity": "info",
        "affected": ["operational_context", "irrigation_events", "fertilizer_events"],
        "action": "User should log management actions",
    },
]


def detect_gaps(evidence: List[EvidenceItem]) -> List[EvidenceGap]:
    """Detect gaps in evidence coverage.

    Checks which source families and key variables are present.
    Reports missing sources as structured gaps.
    """
    gaps: List[EvidenceGap] = []

    # Build presence maps
    sources_present: Set[str] = {e.source_family for e in evidence}
    variables_present: Set[str] = {e.variable for e in evidence}

    for rule in _GAP_RULES:
        source = rule["requires_source"]
        var_contains = rule.get("requires_variable_contains")

        is_missing = False

        if source not in sources_present:
            is_missing = True
        elif var_contains:
            # Source is present, but the specific variable is missing
            has_var = any(var_contains in v for v in variables_present)
            if not has_var:
                is_missing = True

        if is_missing:
            gid = hashlib.sha256(rule["type"].encode()).hexdigest()[:10]
            gaps.append(EvidenceGap(
                gap_id=f"gap_{gid}",
                gap_type=rule["type"],
                severity=rule["severity"],
                affected_features=rule["affected"],
                suggested_action=rule["action"],
            ))

    return gaps

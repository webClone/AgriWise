"""
Layer 1 Gap Analyzer.

Detects missing evidence sources and computes gap severity.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional
from common.time_utils import ensure_utc

from .schemas import EvidenceGap, EvidenceItem, GAP_TYPES, SourceEnvelope


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
        "type": "NO_SIF_DATA",
        "requires_source": "sentinel5p",
        "severity": "info",
        "affected": ["photosynthetic_efficiency", "sif_stress_detection"],
        "action": "No TROPOMI SIF data — photosynthetic shutdown detection unavailable",
    },
    {
        "type": "NO_EO_EMBEDDING",
        "requires_source": "eo_foundation",
        "severity": "info",
        "affected": ["anomaly_embedding", "spectral_intelligence"],
        "action": "No EO Foundation Model embedding — advanced spectral anomaly detection unavailable",
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


def detect_gaps(
    evidence: List[EvidenceItem],
    source_envelopes: Optional[List[SourceEnvelope]] = None,
    reference_time: Optional[datetime] = None,
) -> List[EvidenceGap]:
    """Detect gaps in evidence coverage.

    Checks which source families and key variables are present and usable.
    Reports missing, unavailable, or stale sources as structured gaps.
    """
    gaps: List[EvidenceGap] = []

    # Build presence and usability maps
    sources_present: Set[str] = set()
    sources_unavailable: Set[str] = set()
    latest_observation_times: Dict[str, datetime] = {}
    variables_present: Set[str] = set()

    # First analyze envelopes to identify families that have NO usable envelopes
    envelope_unusable_families: Set[str] = set()
    if source_envelopes:
        family_envelopes: Dict[str, List[SourceEnvelope]] = {}
        for env in source_envelopes:
            family_envelopes.setdefault(env.source_family, []).append(env)
        for fam, envs in family_envelopes.items():
            has_usable = any(env.source_status in ("ok", "degraded") for env in envs)
            if not has_usable:
                envelope_unusable_families.add(fam)

    for e in evidence:
        variables_present.add(e.variable)
        if e.data_status == "unavailable" or e.diagnostic_only or e.source_family in envelope_unusable_families:
            sources_unavailable.add(e.source_family)
        else:
            sources_present.add(e.source_family)

        if e.observed_at:
            obs_utc = ensure_utc(e.observed_at)
            prev_utc = ensure_utc(latest_observation_times.get(e.source_family))
            if prev_utc is None or obs_utc > prev_utc:
                latest_observation_times[e.source_family] = obs_utc

    # Integrate source envelopes health status
    if source_envelopes:
        for env in source_envelopes:
            if env.source_status in ("unusable", "missing", "stale", "conflicted"):
                sources_unavailable.add(env.source_family)
            elif env.source_status in ("ok", "degraded") and env.source_family not in envelope_unusable_families:
                sources_present.add(env.source_family)

    # Core gap rules
    for rule in _GAP_RULES:
        source = rule["requires_source"]
        var_contains = rule.get("requires_variable_contains")

        is_missing = False
        is_unavailable = False

        if source not in sources_present:
            is_missing = True
            if source in sources_unavailable:
                is_unavailable = True
        elif var_contains:
            has_var = any(var_contains in v for v in variables_present)
            if not has_var:
                is_missing = True

        if is_missing:
            # Change severity or description based on health status
            severity = rule["severity"]
            action = rule["action"]
            if is_unavailable:
                severity = "blocking" if rule["severity"] == "warning" else rule["severity"]
                action = f"{action} (Source is present but marked as UNAVAILABLE or degraded)"
            
            gid = hashlib.sha256(rule["type"].encode()).hexdigest()[:10]
            gaps.append(EvidenceGap(
                gap_id=f"gap_{gid}",
                gap_type=rule["type"],
                severity=severity,
                affected_features=rule["affected"],
                data_improvement_hint=action,
            ))

    # Staleness checks (temporal gaps) using deterministic reference_time
    if reference_time:
        staleness_thresholds = {
            "sentinel2": timedelta(days=12),
            "sentinel1": timedelta(days=10),
            "weather_forecast": timedelta(days=2),
        }
        for family, threshold in staleness_thresholds.items():
            if family in sources_present and family in latest_observation_times:
                last_obs = latest_observation_times[family]
                age = reference_time - last_obs
                if age > threshold:
                    gid = hashlib.sha256(f"STALE_{family.upper()}".encode()).hexdigest()[:10]
                    gaps.append(EvidenceGap(
                        gap_id=f"gap_{gid}",
                        gap_type=f"STALE_{family.upper()}_DATA",
                        severity="warning",
                        affected_features=[f"{family}_context", "staleness_warning"],
                        data_improvement_hint=f"Latest {family} observation is {age.days} days old (exceeds threshold of {threshold.days} days). Wait for next overpass/update.",
                    ))

    return gaps

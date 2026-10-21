"""Canonical admission contract for plot-scoped temporal provider evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union


ADMITTED_SOURCE_REALITIES = {
    "provider_daily_statistical_aggregate",
    "provider_catalog_scene_observation",
    "provider_scene_observation",
    "provider_temporal_observation",
    "real_provider_raster",
    "provider_observation",
    "real_raster",
}


try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real


class TimingRole(str, Enum):
    """Canonical temporal role distinguishing realized evidence from forward scenarios."""
    MEASUREMENT = "measurement"
    PRIOR = "prior"
    FORECAST = "forecast"
    MANAGEMENT_SCENARIO = "management_scenario"

    @classmethod
    def from_value(cls, val: Any) -> "TimingRole":
        if isinstance(val, cls):
            return val
        s = str(val or "").strip().lower()
        if s in ("forecast", "weather_forecast", "prediction", "projection"):
            return cls.FORECAST
        if s in ("prior", "climatology", "baseline"):
            return cls.PRIOR
        if s in ("scenario", "management_scenario", "plan", "management_plan", "prescription_plan", "intervention"):
            return cls.MANAGEMENT_SCENARIO
        return cls.MEASUREMENT


def _parse_utc_datetime(val: Any) -> Optional[datetime]:
    """Parse string or datetime into UTC timezone-aware datetime."""
    if val is None or val is False or val is True:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None or val.utcoffset() is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned:
            return None
        cleaned = cleaned.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None or dt.utcoffset() is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            try:
                dt = datetime.strptime(cleaned[:10], "%Y-%m-%d")
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                return None
    return None


@dataclass(frozen=True)
class TemporalTiming:
    """Typed bitemporal timing metadata for evidence admission and replay."""
    role: TimingRole
    valid_time: datetime
    available_at: datetime
    valid_end: Optional[datetime] = None
    issued_at: Optional[datetime] = None
    revision_id: Optional[str] = None
    provider_id: Optional[str] = None
    is_forecast: bool = False

    def validate_cutoff(self, cutoff: datetime) -> Tuple[bool, Optional[str]]:
        """Validate whether this evidence was legally available and valid as of *cutoff*."""
        cutoff_dt = _parse_utc_datetime(cutoff)
        if cutoff_dt is None:
            return False, "invalid_cutoff_timestamp"

        if self.role == TimingRole.MEASUREMENT:
            # Physical causality: a measurement cannot be available before it was physically observed
            if self.available_at < self.valid_time:
                return False, "causality_violation_availability_precedes_observation"
            if self.valid_time > cutoff_dt:
                return False, "observation_time_postdates_cutoff"
            if self.available_at > cutoff_dt:
                return False, "availability_time_postdates_cutoff"
            return True, None

        if self.role == TimingRole.FORECAST:
            issuance = self.issued_at or self.available_at
            if issuance > cutoff_dt:
                return False, "forecast_issued_after_cutoff"
            # Prospective scenario validity: earlier-issued forecasts remain eligible as scenarios
            return True, None

        if self.role == TimingRole.PRIOR:
            if self.available_at > cutoff_dt:
                return False, "prior_available_after_cutoff"
            return True, None

        if self.role == TimingRole.MANAGEMENT_SCENARIO:
            issuance = self.issued_at or self.available_at
            if issuance > cutoff_dt:
                return False, "scenario_issued_after_cutoff"
            return True, None

        return False, "unrecognized_timing_role"


def extract_temporal_timing(record: Dict[str, Any]) -> Optional[TemporalTiming]:
    """Safely extract TemporalTiming from a record dictionary."""
    if not isinstance(record, dict):
        return None

    # 1. Resolve role
    raw_role = (
        record.get("timing_role")
        or record.get("role")
        or record.get("truth_class")
        or record.get("event_type")
        or record.get("data_status")
    )
    is_forecast_flag = record.get("is_forecast") is True or "forecast" in str(raw_role or "").lower()
    role = TimingRole.from_value("forecast" if is_forecast_flag else raw_role)

    # 2. Resolve valid/observation time
    valid_raw = (
        record.get("observation_time")
        or record.get("timestamp")
        or record.get("observed_at")
        or record.get("valid_time")
        or record.get("effective_at")
        or record.get("date")
        or record.get("scene_time")
    )
    valid_dt = _parse_utc_datetime(valid_raw)
    if valid_dt is None:
        return None

    # 3. Resolve availability time
    avail_raw = (
        record.get("available_at")
        or record.get("committed_at")
        or record.get("recorded_at")
        or record.get("known_at")
        or record.get("created_at")
        or record.get("ingested_at")
    )
    avail_dt = _parse_utc_datetime(avail_raw)
    if avail_dt is None:
        # If availability is not explicitly provided on a legacy record, fallback to valid_dt
        avail_dt = valid_dt

    # 4. Resolve issued_at if any
    issued_raw = record.get("issued_at") or record.get("published_at") or record.get("generated_at")
    issued_dt = _parse_utc_datetime(issued_raw)

    valid_end_dt = _parse_utc_datetime(record.get("valid_end") or record.get("end_date"))

    return TemporalTiming(
        role=role,
        valid_time=valid_dt,
        available_at=avail_dt,
        valid_end=valid_end_dt,
        issued_at=issued_dt,
        revision_id=str(record.get("revision_id") or record.get("revision") or ""),
        provider_id=str(record.get("provider_product_id") or record.get("provider_id") or ""),
        is_forecast=is_forecast_flag,
    )


def _has_numeric(record: Dict[str, Any], keys: Tuple[str, ...]) -> bool:
    return any(
        finite_real(record.get(key)) is not None
        for key in keys
    )


def is_admitted_temporal_record(
    record: Dict[str, Any],
    *,
    value_keys: Tuple[str, ...] = (
        "ndvi", "ndvi_mean", "evi", "evi_mean", "ndmi", "ndmi_mean",
        "vv", "vv_db", "vv_db_mean", "vh", "vh_db", "vh_db_mean",
        "vv_vh_ratio", "rvi", "rvi_mean",
    ),
    cutoff: Optional[Union[datetime, str]] = None,
    allowed_roles: Optional[Iterable[TimingRole]] = None,
) -> bool:
    """Default-deny scientific admission shared by all temporal consumers."""
    if not isinstance(record, dict):
        return False
    source_reality = record.get("source_reality")
    is_daily_aggregate = source_reality == "provider_daily_statistical_aggregate"
    identity = (
        record.get("provider_product_id")
        or record.get("scene_id")
        or record.get("observation_id")
        or (record.get("request_hash") if is_daily_aggregate else None)
    )
    quality = str(record.get("quality_class", "")).lower()
    base_admitted = (
        source_reality in ADMITTED_SOURCE_REALITIES
        and bool(identity)
        and bool(record.get("content_hash"))
        and _has_numeric(record, value_keys)
        and record.get("usable") is True
        and quality in {"good", "acceptable", "clear", "valid"}
        and record.get("production_usable") is True
        and (is_daily_aggregate or record.get("real_provider_product") is True)
        and record.get("diagnostic_only") is False
        and (
            not is_daily_aggregate
            or (
                record.get("quality_admitted") is True
                and bool(record.get("geometry_hash"))
                and isinstance(record.get("valid_pixel_count"), int)
                and record.get("valid_pixel_count") > 0
            )
        )
    )
    if not base_admitted:
        return False

    if cutoff is not None:
        cutoff_dt = _parse_utc_datetime(cutoff)
        if cutoff_dt is None:
            return False
        timing = extract_temporal_timing(record)
        if timing is None:
            return False
        if allowed_roles is not None and timing.role not in allowed_roles:
            return False
        valid, _ = timing.validate_cutoff(cutoff_dt)
        if not valid:
            return False

    return True


def build_temporal_admission_ledger(
    records: Iterable[Dict[str, Any]],
    *,
    value_keys: Tuple[str, ...] = (
        "ndvi", "ndvi_mean", "evi", "evi_mean", "ndmi", "ndmi_mean",
        "vv", "vv_db", "vv_db_mean", "vh", "vh_db", "vh_db_mean",
        "vv_vh_ratio", "rvi", "rvi_mean",
    ),
    cutoff: Optional[Union[datetime, str]] = None,
    allowed_roles: Optional[Iterable[TimingRole]] = None,
) -> Dict[str, Any]:
    """Return admitted/rejected records plus explicit health counters and cutoff audit."""
    items = list(records)
    cutoff_dt = _parse_utc_datetime(cutoff) if cutoff is not None else None

    admitted: List[Dict[str, Any]] = []
    admitted_measurements: List[Dict[str, Any]] = []
    admitted_scenarios: List[Dict[str, Any]] = []
    excluded_revisions: List[Dict[str, Any]] = []
    quarantined_future_leakage: int = 0
    quarantined_causality_violations: int = 0

    for item in items:
        timing = extract_temporal_timing(item)
        admit = is_admitted_temporal_record(
            item,
            value_keys=value_keys,
            cutoff=cutoff_dt,
            allowed_roles=allowed_roles,
        )
        if admit:
            admitted.append(item)
            if timing and timing.role == TimingRole.MEASUREMENT:
                admitted_measurements.append(item)
            elif timing and timing.role in (TimingRole.FORECAST, TimingRole.MANAGEMENT_SCENARIO):
                admitted_scenarios.append(item)
        else:
            reason = "quality_or_numeric_admission_failed"
            if cutoff_dt is not None and timing is not None:
                valid, timing_reason = timing.validate_cutoff(cutoff_dt)
                if not valid:
                    reason = timing_reason or "temporal_cutoff_violation"
                    if "postdates" in reason or "after_cutoff" in reason:
                        quarantined_future_leakage += 1
                    elif "causality" in reason:
                        quarantined_causality_violations += 1
            excluded_revisions.append({
                "record_id": str(
                    item.get("provider_product_id")
                    or item.get("scene_id")
                    or item.get("observation_id")
                    or item.get("request_hash")
                    or ""
                ),
                "reason": reason,
                "role": timing.role.value if timing else "unknown",
                "valid_time": timing.valid_time.isoformat() if timing else None,
                "available_at": timing.available_at.isoformat() if timing else None,
            })

    return {
        "contract_version": "temporal_evidence_admission_v1",
        "timing_contract_version": "temporal_timing_contract_v1",
        "decision_cutoff": cutoff_dt.isoformat() if cutoff_dt else None,
        "transport_received": bool(items),
        "input_count": len(items),
        "quality_admitted_count": len(admitted),
        "rejected_count": len(items) - len(admitted),
        "state_eligible": bool(admitted),
        "scientifically_healthy": bool(admitted),
        "admitted_records": admitted,
        "admitted_measurements_count": len(admitted_measurements),
        "admitted_scenarios_count": len(admitted_scenarios),
        "excluded_revisions": excluded_revisions,
        "quarantined_future_leakage_count": quarantined_future_leakage,
        "quarantined_causality_violations_count": quarantined_causality_violations,
    }

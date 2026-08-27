"""Immutable scientific identity for one plot crop cycle."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Tuple

from .plot_namespace import PlotNamespace, _coerce_namespace, namespace_payload


CROP_CYCLE_CONTEXT_CONTRACT_VERSION = "canonical_crop_cycle_context_v2"
_ADMINISTRATIVE_STATUS_ROLE = "workflow_only_not_phenology_evidence"
_DECLARATION_AUTHORITIES = frozenset({
    "UNKNOWN",
    "REGISTRY_DECLARED",
    "USER_CONFIRMED",
    "FARMER_CONFIRMED",
    "OFFICIAL_PARCEL_LABEL",
    "AGRONOMIST_CONFIRMED",
})
_PLANT_DATE_STATUSES = frozenset({
    "confirmed",
    "estimated",
    "interval",
    "unknown",
})


def _json_number_normalized(value: Any) -> Any:
    """Match JavaScript JSON's representation of integral IEEE-754 values."""
    if isinstance(value, Mapping):
        return {
            str(key): _json_number_normalized(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_number_normalized(item) for item in value]
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_number_normalized(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _content_hash(value: Mapping[str, Any]) -> str:
    payload = {
        key: item for key, item in value.items() if key != "content_hash"
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _normalized_text(value: Any, *, upper: bool = False) -> str:
    result = str(value or "").strip()
    return result.upper() if upper else result


def _normalized_crop(value: Any) -> str:
    return (
        _normalized_text(value).lower().replace("-", "_").replace(" ", "_")
        or "unknown"
    )


def _normalized_iso(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(
                str(value).strip().replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError(f"Invalid crop-cycle date: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True, kw_only=True)
class CanonicalCropCycleContextV2:
    """Frozen crop-cycle record; administrative status is never phenology."""

    plot_namespace: PlotNamespace
    crop_cycle_id: str
    geometry_version: str
    effective_at: str
    declared_crop_code: str = "unknown"
    declared_crop_authority: str = "UNKNOWN"
    declared_crop_at: Optional[str] = None
    declared_crop_source: str = "unknown"
    variety: Optional[str] = None
    irrigation_type: str = "unknown"
    plant_date_status: str = "unknown"
    plant_date_source: str = "unknown"
    plant_date_confidence: Optional[float] = None
    plant_date_nominal: Optional[str] = None
    plant_date_range_start: Optional[str] = None
    plant_date_range_end: Optional[str] = None
    expected_harvest_date: Optional[str] = None
    actual_harvest_date: Optional[str] = None
    administrative_status: str = "UNKNOWN"
    management_event_refs: Tuple[str, ...] = ()
    contract_version: str = field(
        default=CROP_CYCLE_CONTEXT_CONTRACT_VERSION, init=False
    )
    content_hash: str = field(default="", init=False)

    def __post_init__(self) -> None:
        namespace = _coerce_namespace(self.plot_namespace)
        crop_cycle_id = _normalized_text(self.crop_cycle_id)
        geometry_version = _normalized_text(self.geometry_version)
        effective_at = _normalized_iso(self.effective_at)
        authority = _normalized_text(
            self.declared_crop_authority, upper=True
        ) or "UNKNOWN"
        declared_crop_at = _normalized_iso(self.declared_crop_at)
        declared_crop_source = (
            _normalized_text(self.declared_crop_source).lower() or "unknown"
        )
        if not crop_cycle_id:
            raise ValueError("crop_cycle_id is required")
        if not geometry_version:
            raise ValueError("geometry_version is required")
        if effective_at is None:
            raise ValueError("effective_at is required")
        if authority not in _DECLARATION_AUTHORITIES:
            raise ValueError(
                f"Unsupported declared_crop_authority: {authority}"
            )

        plant_date_status = (
            _normalized_text(self.plant_date_status).lower() or "unknown"
        )
        if plant_date_status not in _PLANT_DATE_STATUSES:
            raise ValueError(
                f"Unsupported plant_date_status: {plant_date_status}"
            )

        confidence = self.plant_date_confidence
        if confidence is not None:
            confidence = float(confidence)
            if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                raise ValueError("plant_date_confidence must be within [0, 1]")

        nominal = _normalized_iso(self.plant_date_nominal)
        range_start = _normalized_iso(self.plant_date_range_start)
        range_end = _normalized_iso(self.plant_date_range_end)
        if range_start and range_end and range_start > range_end:
            raise ValueError("plant_date_range_start must not exceed range_end")
        if nominal is not None:
            range_start = range_start or nominal
            range_end = range_end or nominal
        if plant_date_status in {"confirmed", "estimated"} and nominal is None:
            raise ValueError(
                f"plant_date_nominal is required for {plant_date_status} status"
            )
        if plant_date_status == "interval" and not (range_start and range_end):
            raise ValueError(
                "plant_date_range_start and range_end are required for interval status"
            )
        if plant_date_status == "unknown" and any(
            value is not None for value in (nominal, range_start, range_end)
        ):
            raise ValueError("unknown plant_date_status cannot carry dates")
        management_refs = tuple(sorted({
            _normalized_text(item)
            for item in self.management_event_refs
            if _normalized_text(item)
        }))

        object.__setattr__(self, "plot_namespace", namespace)
        object.__setattr__(self, "crop_cycle_id", crop_cycle_id)
        object.__setattr__(self, "geometry_version", geometry_version)
        object.__setattr__(self, "effective_at", effective_at)
        object.__setattr__(
            self, "declared_crop_code", _normalized_crop(self.declared_crop_code)
        )
        object.__setattr__(self, "declared_crop_authority", authority)
        object.__setattr__(self, "declared_crop_at", declared_crop_at)
        object.__setattr__(
            self, "declared_crop_source", declared_crop_source
        )
        object.__setattr__(
            self, "variety", _normalized_text(self.variety) or None
        )
        object.__setattr__(
            self, "irrigation_type",
            _normalized_text(self.irrigation_type).lower() or "unknown",
        )
        object.__setattr__(self, "plant_date_status", plant_date_status)
        object.__setattr__(
            self, "plant_date_source",
            _normalized_text(self.plant_date_source).lower() or "unknown",
        )
        object.__setattr__(self, "plant_date_confidence", confidence)
        object.__setattr__(self, "plant_date_nominal", nominal)
        object.__setattr__(self, "plant_date_range_start", range_start)
        object.__setattr__(self, "plant_date_range_end", range_end)
        object.__setattr__(
            self, "expected_harvest_date",
            _normalized_iso(self.expected_harvest_date),
        )
        object.__setattr__(
            self, "actual_harvest_date",
            _normalized_iso(self.actual_harvest_date),
        )
        object.__setattr__(
            self, "administrative_status",
            _normalized_text(self.administrative_status, upper=True) or "UNKNOWN",
        )
        object.__setattr__(self, "management_event_refs", management_refs)
        object.__setattr__(self, "content_hash", _content_hash(self.to_dict(False)))

    def to_dict(self, include_hash: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contract_version": self.contract_version,
            "plot_namespace": namespace_payload(self.plot_namespace),
            "crop_cycle_id": self.crop_cycle_id,
            "geometry_version": self.geometry_version,
            "effective_at": self.effective_at,
            "declared_crop_code": self.declared_crop_code,
            "declared_crop_authority": self.declared_crop_authority,
            "declared_crop_at": self.declared_crop_at,
            "declared_crop_source": self.declared_crop_source,
            "variety": self.variety,
            "irrigation_type": self.irrigation_type,
            # Layer 2 consumes these explicit names.  The duplicate
            # ``planting_date`` spelling is a hash-bound compatibility alias,
            # not a separately mutable value.
            "plant_date": self.plant_date_nominal,
            "planting_date": self.plant_date_nominal,
            "plant_date_status": self.plant_date_status,
            "plant_date_source": self.plant_date_source,
            "plant_date_confidence": self.plant_date_confidence,
            "plant_date_min": self.plant_date_range_start,
            "plant_date_max": self.plant_date_range_end,
            "harvest_dates": {
                "expected": self.expected_harvest_date,
                "actual": self.actual_harvest_date,
            },
            "administrative_status": self.administrative_status,
            "administrative_status_role": _ADMINISTRATIVE_STATUS_ROLE,
            "management_event_refs": list(self.management_event_refs),
            "phenology_from_administrative_status_allowed": False,
        }
        if include_hash:
            payload["content_hash"] = self.content_hash
        return payload

    @classmethod
    def from_mapping(
        cls, raw: Mapping[str, Any], *, verify_hash: bool = True
    ) -> "CanonicalCropCycleContextV2":
        if not isinstance(raw, Mapping):
            raise ValueError("crop_cycle_context must be a mapping")
        if str(raw.get("contract_version") or "") != (
            CROP_CYCLE_CONTEXT_CONTRACT_VERSION
        ):
            raise ValueError("Unsupported crop_cycle_context contract_version")
        if raw.get("phenology_from_administrative_status_allowed") is True:
            raise ValueError("administrative status cannot authorize phenology")
        if any(key in raw for key in ("stage", "phenology_stage", "crop_stage")):
            raise ValueError("crop_cycle_context cannot transport phenology stage")
        plant_date = raw.get("plant_date")
        harvest_dates = raw.get("harvest_dates")
        legacy_plant_date = plant_date if isinstance(plant_date, Mapping) else {}
        canonical_plant_date = (
            None if isinstance(plant_date, Mapping) else plant_date
        )
        planting_date_alias = raw.get("planting_date")
        if (
            canonical_plant_date not in (None, "")
            and planting_date_alias not in (None, "")
            and _normalized_iso(canonical_plant_date)
            != _normalized_iso(planting_date_alias)
        ):
            raise ValueError("plant_date and planting_date aliases disagree")
        if not isinstance(harvest_dates, Mapping):
            harvest_dates = {}
        management_refs = raw.get("management_event_refs") or ()
        if not isinstance(management_refs, (list, tuple)):
            raise ValueError("management_event_refs must be a list")
        value = cls(
            plot_namespace=_coerce_namespace(raw.get("plot_namespace") or {}),
            crop_cycle_id=str(raw.get("crop_cycle_id") or ""),
            geometry_version=str(raw.get("geometry_version") or ""),
            effective_at=str(raw.get("effective_at") or ""),
            declared_crop_code=str(raw.get("declared_crop_code") or "unknown"),
            declared_crop_authority=str(
                raw.get("declared_crop_authority") or "UNKNOWN"
            ),
            declared_crop_at=raw.get("declared_crop_at"),
            declared_crop_source=str(
                raw.get("declared_crop_source") or "unknown"
            ),
            variety=raw.get("variety"),
            irrigation_type=str(raw.get("irrigation_type") or "unknown"),
            plant_date_status=str(
                raw.get("plant_date_status")
                or legacy_plant_date.get("status")
                or "unknown"
            ),
            plant_date_source=str(
                raw.get("plant_date_source")
                or legacy_plant_date.get("source")
                or "unknown"
            ),
            plant_date_confidence=(
                raw.get("plant_date_confidence")
                if "plant_date_confidence" in raw
                else legacy_plant_date.get("confidence")
            ),
            plant_date_nominal=(
                canonical_plant_date
                or planting_date_alias
                or legacy_plant_date.get("nominal")
            ),
            plant_date_range_start=(
                raw.get("plant_date_min")
                or legacy_plant_date.get("range_start")
            ),
            plant_date_range_end=(
                raw.get("plant_date_max")
                or legacy_plant_date.get("range_end")
            ),
            expected_harvest_date=harvest_dates.get("expected"),
            actual_harvest_date=harvest_dates.get("actual"),
            administrative_status=str(raw.get("administrative_status") or "UNKNOWN"),
            management_event_refs=tuple(management_refs),
        )
        supplied_hash = _normalized_text(raw.get("content_hash"))
        if verify_hash and (
            not supplied_hash
            or not hmac.compare_digest(supplied_hash, value.content_hash)
        ):
            raise ValueError("crop_cycle_context content_hash is invalid")
        return value

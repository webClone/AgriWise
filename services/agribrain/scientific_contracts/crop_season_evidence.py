"""Crop-season archive sufficiency and active-acquisition contracts.

The archive receipt is deliberately an *as-of* product.  A source record with
an observation time after ``as_of`` is recorded as excluded and cannot affect
counts, coverage, or sufficiency.  Processing duplicates are collapsed by
physical-acquisition identity before any coverage metric is calculated.

The acquisition planner is diagnostic.  Its default information-gain values
are transparent heuristics and are labelled ``estimated``; they may only be
labelled ``calibrated`` when an explicit calibration receipt is supplied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from services.agribrain.common.plot_namespace import PlotNamespace


CROP_SEASON_EVIDENCE_RECEIPT_VERSION = "crop-season-evidence-receipt-v1"
CROP_ACTIVE_ACQUISITION_PLAN_VERSION = "crop-active-acquisition-plan-v1"
_CROP_LEDGER_HASH = re.compile(r"^CROPLEDGERV2-[0-9a-f]{64}$")


def _namespace(value: Any) -> PlotNamespace:
    if isinstance(value, PlotNamespace):
        candidate = value
    elif isinstance(value, Mapping):
        candidate = PlotNamespace(
            tenant_id=str(value.get("tenant_id") or "").strip(),
            farm_id=str(value.get("farm_id") or "").strip(),
            plot_id=str(value.get("plot_id") or "").strip(),
        )
    else:
        candidate = PlotNamespace(
            tenant_id=str(getattr(value, "tenant_id", "") or "").strip(),
            farm_id=str(getattr(value, "farm_id", "") or "").strip(),
            plot_id=str(getattr(value, "plot_id", "") or "").strip(),
        )
    if not candidate.is_valid():
        raise ValueError("A complete PlotNamespace is required")
    return PlotNamespace(*candidate.to_tuple())


def _namespace_dict(value: PlotNamespace) -> Dict[str, str]:
    return {
        "tenant_id": value.tenant_id.strip(),
        "farm_id": value.farm_id.strip(),
        "plot_id": value.plot_id.strip(),
    }


def _canonical(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Scientific contracts cannot contain non-finite values")
        return 0.0 if value == 0.0 else value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [_canonical(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _canonical(value.to_dict())
    if hasattr(value, "item") and callable(value.item):
        return _canonical(value.item())
    raise ValueError(f"Unsupported scientific-contract type: {type(value).__name__}")


def _content_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parse_time(value: Any, *, required: bool = False) -> Optional[datetime]:
    if value in (None, ""):
        if required:
            raise ValueError("A valid timestamp is required")
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    else:
        raw = str(value).strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.strptime(raw[:10], "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(f"Invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any) -> str:
    parsed = _parse_time(value, required=True)
    assert parsed is not None
    if parsed.microsecond:
        return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _date_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).date().isoformat()


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _first(value: Any, names: Sequence[str], default: Any = None) -> Any:
    for name in names:
        candidate = _field(value, name, None)
        if candidate not in (None, ""):
            return candidate
    return default


def _tuple_text(values: Iterable[Any]) -> Tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _fraction(value: Any, *, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return max(0.0, min(1.0, parsed))


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _source_family(record: Any) -> str:
    raw = " ".join(
        str(_field(record, key, "") or "")
        for key in ("source_family", "mission", "sensor", "source", "provider")
    ).lower().replace("-", "").replace("_", "")
    if any(token in raw for token in ("sentinel2", "s2", "optical")):
        return "sentinel2"
    if any(token in raw for token in ("sentinel1", "s1", "sar", "radar")):
        return "sentinel1"
    if "photo" in raw:
        return "field_photo"
    if any(token in raw for token in ("survey", "fieldobservation", "agronomist")):
        return "field_observation"
    return str(_field(record, "source_family", "unknown") or "unknown").strip().lower()


def _observation_id(record: Any, index: int) -> str:
    value = _first(record, ("observation_id", "scene_id", "id", "source_id"))
    if value not in (None, ""):
        return str(value).strip()
    # A deterministic fallback is audit-only and never creates physical identity.
    sensing = _first(record, ("sensing_time", "datetime", "date"), "missing-time")
    family = _source_family(record)
    return f"unidentified:{family}:{sensing}:{index}"


def _physical_key(record: Any, family: str, observation_id: str) -> str:
    key = str(_field(record, "physical_acquisition_key", "") or "").strip()
    if key:
        return key
    # Explicitly different field observations may use their observation identity;
    # EO records without a physical key are not independent crop evidence.
    if family in {"field_photo", "field_observation"} and not observation_id.startswith(
        "unidentified:"
    ):
        return f"{family}:{observation_id}"
    return ""


def _contains_red_edge(record: Any) -> bool:
    feature_names = set()
    for container_name in (
        "spectral_summary",
        "feature_families",
        "features",
        "indices",
    ):
        container = _field(record, container_name, {})
        if isinstance(container, Mapping):
            feature_names.update(str(key).lower() for key in container)
        elif isinstance(container, (tuple, list, set, frozenset)):
            feature_names.update(str(item).lower() for item in container)
    feature_names.update(
        str(key).lower()
        for key in (record.keys() if isinstance(record, Mapping) else ())
    )
    return any(
        token in name
        for name in feature_names
        for token in ("ndre", "cired", "ci_red", "mtci", "red_edge", "b05", "b06", "b07", "b8a")
    )


def _quality_rank(record: Any, observation_id: str) -> Tuple[float, float, int, str]:
    valid = _fraction(_field(record, "valid_fraction", 0.0))
    cloud_raw = _field(record, "cloud_fraction", None)
    cloud = _fraction(cloud_raw, default=1.0) if cloud_raw is not None else 1.0
    # min() chooses this tuple: highest valid support, least cloud, red edge, ID.
    return (-valid, cloud, 0 if _contains_red_edge(record) else 1, observation_id)


@dataclass(frozen=True, kw_only=True)
class CropSeasonEvidenceReceiptV1:
    namespace: PlotNamespace
    as_of: str
    source_evidence_ledger_hash: str
    crop_cycle_id: Optional[str]
    plant_date_status: str
    season_window_status: str
    candidate_season_start_min: str
    candidate_season_start_max: str
    candidate_season_end_min: str
    candidate_season_end_max: str
    retrieval_window_start: str
    retrieval_window_end: str
    independent_observation_ids: Tuple[str, ...]
    independent_physical_acquisition_keys: Tuple[str, ...]
    independent_s2_observation_ids: Tuple[str, ...]
    independent_s1_observation_ids: Tuple[str, ...]
    field_observation_ids: Tuple[str, ...]
    duplicate_observation_ids: Tuple[str, ...]
    excluded_future_observation_ids: Tuple[str, ...]
    excluded_outside_window_observation_ids: Tuple[str, ...]
    rejected_observation_ids: Tuple[str, ...]
    excluded_future_weather_dates: Tuple[str, ...]
    weather_dates: Tuple[str, ...]
    weather_available_day_count: int
    weather_expected_day_count: int
    weather_completeness: float
    independent_acquisition_count: int
    optical_acquisition_count: int
    sar_acquisition_count: int
    field_observation_count: int
    red_edge_acquisition_count: int
    sensor_families: Tuple[str, ...]
    temporal_span_days: int
    temporal_coverage: float
    biological_phase_coverage: Tuple[Tuple[str, float], ...]
    archive_completeness: float
    model_domain_compatible: bool
    phenology_sufficient: bool
    species_sufficient: bool
    sufficiency_status: str
    sufficiency_reasons: Tuple[str, ...]
    management_event_refs: Tuple[str, ...] = ()
    previous_cycle_crop_posterior_hash: Optional[str] = None
    geometry_change_refs: Tuple[str, ...] = ()
    backtest_safe: bool = True
    completeness_method: str = "bounded-season-coverage-v1-diagnostic"
    contract_version: str = CROP_SEASON_EVIDENCE_RECEIPT_VERSION
    content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "namespace", _namespace(self.namespace))
        object.__setattr__(self, "as_of", _iso(self.as_of))
        ledger_hash = str(self.source_evidence_ledger_hash or "").strip()
        if not _CROP_LEDGER_HASH.fullmatch(ledger_hash):
            raise ValueError(
                "source_evidence_ledger_hash must identify a verified CropEvidenceLedgerV2"
            )
        object.__setattr__(self, "source_evidence_ledger_hash", ledger_hash)
        for name in (
            "candidate_season_start_min",
            "candidate_season_start_max",
            "candidate_season_end_min",
            "candidate_season_end_max",
            "retrieval_window_start",
            "retrieval_window_end",
        ):
            object.__setattr__(self, name, _iso(getattr(self, name)))
        for name in (
            "independent_observation_ids",
            "independent_physical_acquisition_keys",
            "independent_s2_observation_ids",
            "independent_s1_observation_ids",
            "field_observation_ids",
            "duplicate_observation_ids",
            "excluded_future_observation_ids",
            "excluded_outside_window_observation_ids",
            "rejected_observation_ids",
            "excluded_future_weather_dates",
            "weather_dates",
            "sensor_families",
            "sufficiency_reasons",
            "management_event_refs",
            "geometry_change_refs",
        ):
            object.__setattr__(self, name, _tuple_text(getattr(self, name)))
        phase_rows = tuple(
            sorted(
                (
                    str(name).strip().lower(),
                    _fraction(value),
                )
                for name, value in self.biological_phase_coverage
            )
        )
        if tuple(name for name, _ in phase_rows) != ("early", "late", "mid"):
            raise ValueError("Biological phase coverage must contain early/mid/late")
        object.__setattr__(self, "biological_phase_coverage", phase_rows)
        for name in ("weather_completeness", "temporal_coverage", "archive_completeness"):
            raw = float(getattr(self, name))
            if not math.isfinite(raw) or not 0.0 <= raw <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
            object.__setattr__(self, name, raw)
        for name in (
            "weather_available_day_count",
            "weather_expected_day_count",
            "independent_acquisition_count",
            "optical_acquisition_count",
            "sar_acquisition_count",
            "field_observation_count",
            "red_edge_acquisition_count",
            "temporal_span_days",
        ):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} cannot be negative")
            object.__setattr__(self, name, int(getattr(self, name)))
        if not self.backtest_safe:
            raise ValueError("Crop season evidence receipts must fail closed on future data")
        expected = _content_hash(self._payload_without_hash())
        if self.content_hash and str(self.content_hash).lower() != expected:
            raise ValueError("Crop season evidence receipt content_hash mismatch")
        object.__setattr__(self, "content_hash", expected)

    @property
    def receipt_id(self) -> str:
        return "CROP-SEASON-EVIDENCE-" + self.content_hash[:24]

    @property
    def phase_coverage(self) -> Dict[str, float]:
        return dict(self.biological_phase_coverage)

    def _payload_without_hash(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "namespace": _namespace_dict(self.namespace),
            "as_of": self.as_of,
            "source_evidence_ledger_hash": self.source_evidence_ledger_hash,
            "crop_cycle_id": self.crop_cycle_id,
            "plant_date_status": self.plant_date_status,
            "season_window_status": self.season_window_status,
            "candidate_season_start_min": self.candidate_season_start_min,
            "candidate_season_start_max": self.candidate_season_start_max,
            "candidate_season_end_min": self.candidate_season_end_min,
            "candidate_season_end_max": self.candidate_season_end_max,
            "retrieval_window_start": self.retrieval_window_start,
            "retrieval_window_end": self.retrieval_window_end,
            "independent_observation_ids": list(self.independent_observation_ids),
            "independent_physical_acquisition_keys": list(
                self.independent_physical_acquisition_keys
            ),
            "independent_s2_observation_ids": list(self.independent_s2_observation_ids),
            "independent_s1_observation_ids": list(self.independent_s1_observation_ids),
            "field_observation_ids": list(self.field_observation_ids),
            "duplicate_observation_ids": list(self.duplicate_observation_ids),
            "excluded_future_observation_ids": list(
                self.excluded_future_observation_ids
            ),
            "excluded_outside_window_observation_ids": list(
                self.excluded_outside_window_observation_ids
            ),
            "rejected_observation_ids": list(self.rejected_observation_ids),
            "excluded_future_weather_dates": list(self.excluded_future_weather_dates),
            "weather_dates": list(self.weather_dates),
            "weather_available_day_count": self.weather_available_day_count,
            "weather_expected_day_count": self.weather_expected_day_count,
            "weather_completeness": self.weather_completeness,
            "independent_acquisition_count": self.independent_acquisition_count,
            "optical_acquisition_count": self.optical_acquisition_count,
            "sar_acquisition_count": self.sar_acquisition_count,
            "field_observation_count": self.field_observation_count,
            "red_edge_acquisition_count": self.red_edge_acquisition_count,
            "sensor_families": list(self.sensor_families),
            "temporal_span_days": self.temporal_span_days,
            "temporal_coverage": self.temporal_coverage,
            "biological_phase_coverage": dict(self.biological_phase_coverage),
            "archive_completeness": self.archive_completeness,
            "model_domain_compatible": bool(self.model_domain_compatible),
            "phenology_sufficient": bool(self.phenology_sufficient),
            "species_sufficient": bool(self.species_sufficient),
            "sufficiency_status": self.sufficiency_status,
            "sufficiency_reasons": list(self.sufficiency_reasons),
            "management_event_refs": list(self.management_event_refs),
            "previous_cycle_crop_posterior_hash": self.previous_cycle_crop_posterior_hash,
            "geometry_change_refs": list(self.geometry_change_refs),
            "backtest_safe": bool(self.backtest_safe),
            "completeness_method": self.completeness_method,
        }

    def to_dict(self) -> Dict[str, Any]:
        result = self._payload_without_hash()
        result.update({"receipt_id": self.receipt_id, "content_hash": self.content_hash})
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CropSeasonEvidenceReceiptV1":
        if not isinstance(value, Mapping):
            raise ValueError("Crop season evidence receipt must be an object")
        phase = value.get("biological_phase_coverage") or {}
        receipt = cls(
            namespace=_namespace(value.get("namespace") or {}),
            as_of=str(value.get("as_of") or ""),
            source_evidence_ledger_hash=str(
                value.get("source_evidence_ledger_hash") or ""
            ),
            crop_cycle_id=value.get("crop_cycle_id"),
            plant_date_status=str(value.get("plant_date_status") or "unknown"),
            season_window_status=str(value.get("season_window_status") or "latent_unanchored"),
            candidate_season_start_min=str(value.get("candidate_season_start_min") or ""),
            candidate_season_start_max=str(value.get("candidate_season_start_max") or ""),
            candidate_season_end_min=str(value.get("candidate_season_end_min") or ""),
            candidate_season_end_max=str(value.get("candidate_season_end_max") or ""),
            retrieval_window_start=str(value.get("retrieval_window_start") or ""),
            retrieval_window_end=str(value.get("retrieval_window_end") or ""),
            independent_observation_ids=tuple(value.get("independent_observation_ids") or ()),
            independent_physical_acquisition_keys=tuple(value.get("independent_physical_acquisition_keys") or ()),
            independent_s2_observation_ids=tuple(value.get("independent_s2_observation_ids") or ()),
            independent_s1_observation_ids=tuple(value.get("independent_s1_observation_ids") or ()),
            field_observation_ids=tuple(value.get("field_observation_ids") or ()),
            duplicate_observation_ids=tuple(value.get("duplicate_observation_ids") or ()),
            excluded_future_observation_ids=tuple(value.get("excluded_future_observation_ids") or ()),
            excluded_outside_window_observation_ids=tuple(value.get("excluded_outside_window_observation_ids") or ()),
            rejected_observation_ids=tuple(value.get("rejected_observation_ids") or ()),
            excluded_future_weather_dates=tuple(value.get("excluded_future_weather_dates") or ()),
            weather_dates=tuple(value.get("weather_dates") or ()),
            weather_available_day_count=int(value.get("weather_available_day_count") or 0),
            weather_expected_day_count=int(value.get("weather_expected_day_count") or 0),
            weather_completeness=float(value.get("weather_completeness") or 0.0),
            independent_acquisition_count=int(value.get("independent_acquisition_count") or 0),
            optical_acquisition_count=int(value.get("optical_acquisition_count") or 0),
            sar_acquisition_count=int(value.get("sar_acquisition_count") or 0),
            field_observation_count=int(value.get("field_observation_count") or 0),
            red_edge_acquisition_count=int(value.get("red_edge_acquisition_count") or 0),
            sensor_families=tuple(value.get("sensor_families") or ()),
            temporal_span_days=int(value.get("temporal_span_days") or 0),
            temporal_coverage=float(value.get("temporal_coverage") or 0.0),
            biological_phase_coverage=tuple(
                phase.items() if isinstance(phase, Mapping) else phase
            ),
            archive_completeness=float(value.get("archive_completeness") or 0.0),
            model_domain_compatible=value.get("model_domain_compatible") is True,
            phenology_sufficient=value.get("phenology_sufficient") is True,
            species_sufficient=value.get("species_sufficient") is True,
            sufficiency_status=str(value.get("sufficiency_status") or "insufficient"),
            sufficiency_reasons=tuple(value.get("sufficiency_reasons") or ()),
            management_event_refs=tuple(value.get("management_event_refs") or ()),
            previous_cycle_crop_posterior_hash=value.get("previous_cycle_crop_posterior_hash"),
            geometry_change_refs=tuple(value.get("geometry_change_refs") or ()),
            backtest_safe=value.get("backtest_safe") is True,
            completeness_method=str(value.get("completeness_method") or "bounded-season-coverage-v1-diagnostic"),
            contract_version=str(value.get("contract_version") or CROP_SEASON_EVIDENCE_RECEIPT_VERSION),
            content_hash=str(value.get("content_hash") or ""),
        )
        supplied_id = str(value.get("receipt_id") or "")
        if supplied_id and supplied_id != receipt.receipt_id:
            raise ValueError("Crop season evidence receipt_id mismatch")
        return receipt


def _cycle_window(
    context: Any,
    as_of: datetime,
    *,
    historical_window_days: int,
    preplant_baseline_days: int,
) -> Dict[str, Any]:
    status = str(_field(context, "plant_date_status", "unknown") or "unknown").lower()
    nominal = _first(context, ("plant_date_nominal", "plant_date"))
    range_start = _first(context, ("plant_date_range_start", "plant_date_min"))
    range_end = _first(context, ("plant_date_range_end", "plant_date_max"))
    nominal_dt = _parse_time(nominal)
    start_dt = _parse_time(range_start) or nominal_dt
    end_dt = _parse_time(range_end) or nominal_dt

    # A plant-date statement made after the inference date cannot anchor a
    # historical replay.  The date itself may be historical, but its source
    # effective time still matters.
    context_effective = _parse_time(_field(context, "effective_at", None))
    if context_effective is not None and context_effective > as_of:
        status = "unknown"
        nominal_dt = start_dt = end_dt = None

    if status == "confirmed" and nominal_dt is not None and nominal_dt <= as_of:
        start_min = start_max = nominal_dt
        window_status = "confirmed_anchor"
    elif status in {"interval", "estimated"} and start_dt and end_dt:
        start_min, start_max = sorted((start_dt, end_dt))
        if start_min > as_of:
            start_min = start_max = None
            status = "unknown"
            window_status = "latent_unanchored"
        else:
            start_max = min(start_max, as_of)
            window_status = "bounded_interval_anchor"
    else:
        start_min = start_max = None
        window_status = "latent_unanchored"

    if start_min is None or start_max is None:
        start_min = as_of - timedelta(days=max(1, int(historical_window_days)))
        start_max = as_of
        status = "unknown"

    actual_harvest = _parse_time(
        _first(context, ("actual_harvest_date", "actual_harvest"))
    )
    expected_harvest = _parse_time(
        _first(context, ("expected_harvest_date", "expected_harvest"))
    )
    known_end = next(
        (
            candidate
            for candidate in (actual_harvest, expected_harvest)
            if candidate is not None and candidate <= as_of
        ),
        as_of,
    )
    end_min = end_max = min(known_end, as_of)
    retrieval_start = start_min - timedelta(days=max(0, int(preplant_baseline_days)))
    return {
        "plant_date_status": status,
        "season_window_status": window_status,
        "start_min": start_min,
        "start_max": start_max,
        "end_min": end_min,
        "end_max": end_max,
        "retrieval_start": retrieval_start,
        "retrieval_end": as_of,
    }


def build_crop_season_evidence_receipt(
    *,
    namespace: Any,
    observations: Sequence[Any],
    source_evidence_ledger_hash: str,
    weather_records: Sequence[Any] = (),
    crop_cycle_context: Any = None,
    as_of: Any,
    historical_window_days: int = 365,
    preplant_baseline_days: int = 14,
    model_domain_compatible: bool = False,
) -> CropSeasonEvidenceReceiptV1:
    """Build a deterministic, future-safe crop archive sufficiency receipt."""

    as_of_dt = _parse_time(as_of, required=True)
    assert as_of_dt is not None
    context = crop_cycle_context or {}
    window = _cycle_window(
        context,
        as_of_dt,
        historical_window_days=historical_window_days,
        preplant_baseline_days=preplant_baseline_days,
    )
    lower = window["retrieval_start"]
    upper = window["retrieval_end"]

    eligible_by_key: Dict[str, list[Tuple[Any, str, datetime, str]]] = {}
    future_ids: list[str] = []
    outside_ids: list[str] = []
    rejected_ids: list[str] = []

    for index, record in enumerate(observations or ()):
        obs_id = _observation_id(record, index)
        sensing = _parse_time(_first(record, ("sensing_time", "datetime", "date")))
        if sensing is None:
            rejected_ids.append(obs_id)
            continue
        if sensing > as_of_dt:
            future_ids.append(obs_id)
            continue
        if sensing < lower or sensing > upper:
            outside_ids.append(obs_id)
            continue
        family = _source_family(record)
        physical_key = _physical_key(record, family, obs_id)
        direct = _field(record, "direct_observation", True) is not False
        independent = _field(record, "independent_evidence", True) is not False
        observed = _field(record, "is_observed", True) is not False
        admission = str(_field(record, "admission_status", "admitted") or "").lower()
        admitted = admission in {
            "admitted",
            "accepted",
            "production_usable",
            "diagnostic_usable",
            "included",
        }
        if not (physical_key and direct and independent and observed and admitted):
            rejected_ids.append(obs_id)
            continue
        eligible_by_key.setdefault(physical_key, []).append(
            (record, obs_id, sensing, family)
        )

    chosen: list[Tuple[Any, str, datetime, str, str]] = []
    duplicate_ids: list[str] = []
    for physical_key in sorted(eligible_by_key):
        cluster = sorted(
            eligible_by_key[physical_key],
            key=lambda row: _quality_rank(row[0], row[1]),
        )
        selected = cluster[0]
        chosen.append((*selected, physical_key))
        duplicate_ids.extend(row[1] for row in cluster[1:])
    chosen.sort(key=lambda row: (row[2], row[4], row[1]))

    independent_ids = [row[1] for row in chosen]
    physical_keys = [row[4] for row in chosen]
    s2_ids = [row[1] for row in chosen if row[3] == "sentinel2"]
    s1_ids = [row[1] for row in chosen if row[3] == "sentinel1"]
    field_ids = [
        row[1]
        for row in chosen
        if row[3] in {"field_photo", "field_observation"}
    ]
    red_edge_ids = [
        row[1]
        for row in chosen
        if row[3] == "sentinel2" and _contains_red_edge(row[0])
    ]
    sensor_families = _tuple_text(row[3] for row in chosen)

    expected_days = max(1, (upper.date() - lower.date()).days + 1)
    if chosen:
        temporal_span_days = (chosen[-1][2].date() - chosen[0][2].date()).days + 1
    else:
        temporal_span_days = 0
    temporal_coverage = min(1.0, temporal_span_days / expected_days)

    phase_hits = {"early": 0, "mid": 0, "late": 0}
    for _, _, sensing, _, _ in chosen:
        offset = max(0, (sensing.date() - lower.date()).days)
        fraction = min(0.999999, offset / expected_days)
        phase = "early" if fraction < 1 / 3 else ("mid" if fraction < 2 / 3 else "late")
        phase_hits[phase] += 1
    phase_coverage = tuple(
        (phase, 1.0 if phase_hits[phase] > 0 else 0.0)
        for phase in ("early", "mid", "late")
    )
    phase_fraction = sum(value for _, value in phase_coverage) / 3.0

    weather_by_date: Dict[str, Any] = {}
    future_weather_dates: list[str] = []
    for record in weather_records or ():
        moment = _parse_time(_first(record, ("sensing_time", "datetime", "date")))
        if moment is None:
            continue
        date_key = _date_iso(moment)
        if moment > as_of_dt:
            future_weather_dates.append(date_key)
            continue
        if moment < lower or moment > upper:
            continue
        temperature_available = any(
            _finite(_field(record, key, None)) is not None
            for key in ("tmean", "temp_mean", "temp_min", "temp_max", "temperature")
        )
        if temperature_available:
            # Multiple providers on one day still represent one forcing day.
            weather_by_date.setdefault(date_key, record)
    weather_days = len(weather_by_date)
    weather_completeness = min(1.0, weather_days / expected_days)

    modality_fraction = min(1.0, len({row[3] for row in chosen if row[3] in {"sentinel1", "sentinel2"}}) / 2.0)
    archive_completeness = max(
        0.0,
        min(
            1.0,
            0.35 * temporal_coverage
            + 0.30 * phase_fraction
            + 0.25 * weather_completeness
            + 0.10 * modality_fraction,
        ),
    )

    anchor_known = window["season_window_status"] != "latent_unanchored"
    phenology_sufficient = (
        anchor_known
        and len(chosen) >= 4
        and phase_fraction >= (2.0 / 3.0)
        and weather_completeness >= 0.8
    )
    species_sufficient = (
        len(chosen) >= 6
        and len(s2_ids) >= 4
        and len(s1_ids) >= 1
        and len(red_edge_ids) >= 2
        and phase_fraction >= 1.0
        and bool(model_domain_compatible)
    )
    reasons: list[str] = []
    if not anchor_known:
        reasons.append("planting_date_or_season_boundary_unknown")
    if len(chosen) < 4:
        reasons.append("insufficient_independent_acquisitions")
    if phase_fraction < 2.0 / 3.0:
        reasons.append("insufficient_biological_phase_coverage")
    if weather_completeness < 0.8:
        reasons.append("incomplete_daily_weather_forcing")
    if len(s2_ids) < 4:
        reasons.append("insufficient_independent_optical_acquisitions")
    if not s1_ids:
        reasons.append("sar_season_evidence_missing")
    if len(red_edge_ids) < 2:
        reasons.append("red_edge_transition_evidence_missing")
    if not model_domain_compatible:
        reasons.append("crop_model_domain_not_validated")
    status = (
        "full_season_sufficient"
        if phenology_sufficient and species_sufficient
        else "phenology_sufficient"
        if phenology_sufficient
        else "insufficient"
    )

    return CropSeasonEvidenceReceiptV1(
        namespace=_namespace(namespace),
        as_of=_iso(as_of_dt),
        source_evidence_ledger_hash=source_evidence_ledger_hash,
        crop_cycle_id=(
            str(_field(context, "crop_cycle_id", "") or "").strip() or None
        ),
        plant_date_status=window["plant_date_status"],
        season_window_status=window["season_window_status"],
        candidate_season_start_min=_iso(window["start_min"]),
        candidate_season_start_max=_iso(window["start_max"]),
        candidate_season_end_min=_iso(window["end_min"]),
        candidate_season_end_max=_iso(window["end_max"]),
        retrieval_window_start=_iso(lower),
        retrieval_window_end=_iso(upper),
        independent_observation_ids=tuple(independent_ids),
        independent_physical_acquisition_keys=tuple(physical_keys),
        independent_s2_observation_ids=tuple(s2_ids),
        independent_s1_observation_ids=tuple(s1_ids),
        field_observation_ids=tuple(field_ids),
        duplicate_observation_ids=tuple(duplicate_ids),
        excluded_future_observation_ids=tuple(future_ids),
        excluded_outside_window_observation_ids=tuple(outside_ids),
        rejected_observation_ids=tuple(rejected_ids),
        excluded_future_weather_dates=tuple(future_weather_dates),
        weather_dates=tuple(weather_by_date),
        weather_available_day_count=weather_days,
        weather_expected_day_count=expected_days,
        weather_completeness=weather_completeness,
        independent_acquisition_count=len(chosen),
        optical_acquisition_count=len(s2_ids),
        sar_acquisition_count=len(s1_ids),
        field_observation_count=len(field_ids),
        red_edge_acquisition_count=len(red_edge_ids),
        sensor_families=sensor_families,
        temporal_span_days=temporal_span_days,
        temporal_coverage=temporal_coverage,
        biological_phase_coverage=phase_coverage,
        archive_completeness=archive_completeness,
        model_domain_compatible=bool(model_domain_compatible),
        phenology_sufficient=phenology_sufficient,
        species_sufficient=species_sufficient,
        sufficiency_status=status,
        sufficiency_reasons=tuple(reasons),
        management_event_refs=tuple(
            _first(context, ("management_event_refs", "management_refs"), ()) or ()
        ),
        previous_cycle_crop_posterior_hash=_field(
            context, "previous_cycle_crop_posterior_hash", None
        ),
        geometry_change_refs=tuple(_field(context, "geometry_change_refs", ()) or ()),
        backtest_safe=True,
    )


@dataclass(frozen=True, kw_only=True)
class CropAcquisitionActionV1:
    action_type: str
    priority: int
    expected_information_gain: Optional[float]
    information_gain_status: str
    cost_class: str
    latency_class: str
    availability_start: Optional[str]
    availability_end: Optional[str]
    cloud_probability: Optional[float]
    reason: str
    expected_evidence_authority: str
    calibration_receipt_id: Optional[str] = None

    def __post_init__(self) -> None:
        if int(self.priority) < 1:
            raise ValueError("Acquisition action priority must be positive")
        object.__setattr__(self, "priority", int(self.priority))
        status = str(self.information_gain_status or "estimated").lower()
        if status not in {"estimated", "calibrated", "unavailable"}:
            raise ValueError("Invalid information_gain_status")
        if status == "calibrated" and not self.calibration_receipt_id:
            raise ValueError("Calibrated EIG requires a calibration receipt")
        if status != "calibrated" and self.calibration_receipt_id:
            raise ValueError("EIG calibration receipt requires calibrated status")
        object.__setattr__(self, "information_gain_status", status)
        if self.expected_information_gain is not None:
            gain = float(self.expected_information_gain)
            if not math.isfinite(gain) or gain < 0.0:
                raise ValueError("Expected information gain must be finite and non-negative")
            object.__setattr__(self, "expected_information_gain", gain)
        if self.cloud_probability is not None:
            object.__setattr__(
                self, "cloud_probability", _fraction(self.cloud_probability)
            )
        for name in ("availability_start", "availability_end"):
            raw = getattr(self, name)
            object.__setattr__(self, name, _iso(raw) if raw else None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "priority": self.priority,
            "expected_information_gain": self.expected_information_gain,
            "information_gain_status": self.information_gain_status,
            "information_gain_unit": "nats",
            "cost_class": self.cost_class,
            "latency_class": self.latency_class,
            "availability_start": self.availability_start,
            "availability_end": self.availability_end,
            "cloud_probability": self.cloud_probability,
            "reason": self.reason,
            "expected_evidence_authority": self.expected_evidence_authority,
            "calibration_receipt_id": self.calibration_receipt_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CropAcquisitionActionV1":
        return cls(
            action_type=str(value.get("action_type") or ""),
            priority=int(value.get("priority") or 0),
            expected_information_gain=(
                float(value["expected_information_gain"])
                if value.get("expected_information_gain") is not None
                else None
            ),
            information_gain_status=str(value.get("information_gain_status") or "estimated"),
            cost_class=str(value.get("cost_class") or "unknown"),
            latency_class=str(value.get("latency_class") or "unknown"),
            availability_start=value.get("availability_start"),
            availability_end=value.get("availability_end"),
            cloud_probability=value.get("cloud_probability"),
            reason=str(value.get("reason") or ""),
            expected_evidence_authority=str(value.get("expected_evidence_authority") or "diagnostic"),
            calibration_receipt_id=value.get("calibration_receipt_id"),
        )


@dataclass(frozen=True, kw_only=True)
class CropActiveAcquisitionPlanV1:
    namespace: PlotNamespace
    crop_cycle_id: Optional[str]
    valid_time: str
    evidence_receipt_hash: str
    crop_posterior_hash: Optional[str]
    phenology_posterior_hash: Optional[str]
    current_posterior_entropy: Optional[float]
    entropy_status: str
    candidate_hypotheses: Tuple[Tuple[str, float], ...]
    actions: Tuple[CropAcquisitionActionV1, ...]
    planner_authority: str = "diagnostic_estimated_utility"
    contract_version: str = CROP_ACTIVE_ACQUISITION_PLAN_VERSION
    content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "namespace", _namespace(self.namespace))
        object.__setattr__(self, "valid_time", _iso(self.valid_time))
        entropy_status = str(self.entropy_status or "estimated").lower()
        if entropy_status not in {"estimated", "calibrated", "unavailable"}:
            raise ValueError("Invalid entropy_status")
        object.__setattr__(self, "entropy_status", entropy_status)
        if self.current_posterior_entropy is not None:
            entropy = float(self.current_posterior_entropy)
            if not math.isfinite(entropy) or entropy < 0.0:
                raise ValueError("Posterior entropy must be finite and non-negative")
            object.__setattr__(self, "current_posterior_entropy", entropy)
        hypotheses = tuple(
            sorted(
                (
                    (str(name).strip(), float(probability))
                    for name, probability in self.candidate_hypotheses
                    if str(name).strip() and _finite(probability) is not None
                ),
                key=lambda row: (-row[1], row[0]),
            )
        )
        if any(probability < 0.0 or probability > 1.0 for _, probability in hypotheses):
            raise ValueError("Candidate hypothesis probabilities must be in [0, 1]")
        object.__setattr__(self, "candidate_hypotheses", hypotheses)
        actions = tuple(sorted(self.actions, key=lambda item: (item.priority, item.action_type)))
        if tuple(range(1, len(actions) + 1)) != tuple(item.priority for item in actions):
            raise ValueError("Acquisition action priorities must be contiguous")
        object.__setattr__(self, "actions", actions)
        expected = _content_hash(self._payload_without_hash())
        if self.content_hash and str(self.content_hash).lower() != expected:
            raise ValueError("Crop acquisition plan content_hash mismatch")
        object.__setattr__(self, "content_hash", expected)

    @property
    def plan_id(self) -> str:
        return "CROP-ACQUISITION-" + self.content_hash[:24]

    def _payload_without_hash(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "namespace": _namespace_dict(self.namespace),
            "crop_cycle_id": self.crop_cycle_id,
            "valid_time": self.valid_time,
            "evidence_receipt_hash": self.evidence_receipt_hash,
            "crop_posterior_hash": self.crop_posterior_hash,
            "phenology_posterior_hash": self.phenology_posterior_hash,
            "current_posterior_entropy": self.current_posterior_entropy,
            "entropy_status": self.entropy_status,
            "candidate_hypotheses": [
                {"hypothesis": name, "probability": probability}
                for name, probability in self.candidate_hypotheses
            ],
            "actions": [action.to_dict() for action in self.actions],
            "planner_authority": self.planner_authority,
        }

    def to_dict(self) -> Dict[str, Any]:
        result = self._payload_without_hash()
        result.update({"plan_id": self.plan_id, "content_hash": self.content_hash})
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CropActiveAcquisitionPlanV1":
        hypotheses = value.get("candidate_hypotheses") or ()
        plan = cls(
            namespace=_namespace(value.get("namespace") or {}),
            crop_cycle_id=value.get("crop_cycle_id"),
            valid_time=str(value.get("valid_time") or ""),
            evidence_receipt_hash=str(value.get("evidence_receipt_hash") or ""),
            crop_posterior_hash=value.get("crop_posterior_hash"),
            phenology_posterior_hash=value.get("phenology_posterior_hash"),
            current_posterior_entropy=(
                float(value["current_posterior_entropy"])
                if value.get("current_posterior_entropy") is not None
                else None
            ),
            entropy_status=str(value.get("entropy_status") or "estimated"),
            candidate_hypotheses=tuple(
                (
                    str(item.get("hypothesis") or ""),
                    float(item.get("probability") or 0.0),
                )
                if isinstance(item, Mapping)
                else (str(item[0]), float(item[1]))
                for item in hypotheses
            ),
            actions=tuple(
                CropAcquisitionActionV1.from_dict(item)
                for item in (value.get("actions") or ())
            ),
            planner_authority=str(value.get("planner_authority") or "diagnostic_estimated_utility"),
            contract_version=str(value.get("contract_version") or CROP_ACTIVE_ACQUISITION_PLAN_VERSION),
            content_hash=str(value.get("content_hash") or ""),
        )
        supplied_id = str(value.get("plan_id") or "")
        if supplied_id and supplied_id != plan.plan_id:
            raise ValueError("Crop acquisition plan_id mismatch")
        return plan


def _posterior_hypotheses(crop_posterior: Any) -> Tuple[Tuple[str, float], ...]:
    if not crop_posterior:
        return ()
    candidates = _first(
        crop_posterior,
        ("l3_species_posterior", "species_posterior", "species_ranking"),
        {},
    )
    rows: list[Tuple[str, float]] = []
    if isinstance(candidates, Mapping):
        rows = [
            (str(name), float(probability))
            for name, probability in candidates.items()
            if _finite(probability) is not None and float(probability) >= 0.0
        ]
    elif isinstance(candidates, (tuple, list)):
        for item in candidates:
            if isinstance(item, Mapping):
                name = _first(item, ("crop", "code", "name", "hypothesis"))
                probability = _first(item, ("probability", "share", "score"))
                if name and _finite(probability) is not None:
                    rows.append((str(name), max(0.0, float(probability))))
    total = sum(probability for _, probability in rows)
    if total <= 0.0:
        return ()
    return tuple(
        sorted(
            ((name, probability / total) for name, probability in rows),
            key=lambda row: (-row[1], row[0]),
        )[:5]
    )


def _opportunity_type(value: Any) -> str:
    raw = str(
        _first(value, ("action_type", "source_family", "mission", "sensor"), "")
        or ""
    ).lower().replace("-", "").replace("_", "")
    if any(token in raw for token in ("sentinel2", "s2", "rededge")):
        return "sentinel2_red_edge"
    if any(token in raw for token in ("sentinel1", "s1", "sar")):
        return "sentinel1_observation"
    return raw


def _best_opportunity(
    opportunities: Sequence[Any], action_type: str, as_of: datetime
) -> Optional[Dict[str, Any]]:
    candidates: list[Dict[str, Any]] = []
    for item in opportunities or ():
        if _opportunity_type(item) != action_type:
            continue
        if _field(item, "available", True) is False:
            continue
        start = _parse_time(_first(item, ("availability_start", "start", "time")))
        end = _parse_time(_first(item, ("availability_end", "end"))) or start
        if start is None or end is None or end < as_of:
            continue
        candidates.append(
            {
                "start": max(start, as_of),
                "end": end,
                "cloud": (
                    _fraction(_field(item, "cloud_probability", None), default=1.0)
                    if _field(item, "cloud_probability", None) is not None
                    else None
                ),
            }
        )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            item["cloud"] if item["cloud"] is not None else 1.0,
            item["start"],
            item["end"],
        ),
    )


def build_crop_active_acquisition_plan(
    *,
    receipt: CropSeasonEvidenceReceiptV1 | Mapping[str, Any],
    crop_posterior: Any = None,
    phenology_posterior: Any = None,
    opportunities: Sequence[Any] = (),
    eig_calibration_receipt_id: Optional[str] = None,
) -> CropActiveAcquisitionPlanV1:
    """Recommend missing evidence without upgrading estimated utility to fact."""

    if isinstance(receipt, Mapping):
        receipt = CropSeasonEvidenceReceiptV1.from_dict(receipt)
    if not isinstance(receipt, CropSeasonEvidenceReceiptV1):
        raise ValueError("A CropSeasonEvidenceReceiptV1 is required")

    hypotheses = _posterior_hypotheses(crop_posterior)
    entropy = (
        -sum(probability * math.log(probability) for _, probability in hypotheses if probability > 0.0)
        if hypotheses
        else None
    )
    posterior_calibration_id = _field(crop_posterior, "calibration_receipt_id", None)
    posterior_calibrated = (
        _field(crop_posterior, "calibrated", False) is True
        and bool(posterior_calibration_id)
    )
    entropy_status = (
        "calibrated" if entropy is not None and posterior_calibrated
        else "estimated" if entropy is not None
        else "unavailable"
    )
    eig_status = "calibrated" if eig_calibration_receipt_id else "estimated"
    as_of = _parse_time(receipt.as_of, required=True)
    assert as_of is not None

    selected_level = str(
        _first(crop_posterior, ("deepest_publishable_level", "selected_level"), "unknown")
        or "unknown"
    ).lower()
    unknown_probability = _finite(_field(crop_posterior, "unknown_probability", None))
    species_supported = (
        receipt.species_sufficient
        and selected_level in {"l3", "species", "l3_species"}
        and posterior_calibrated
        and (unknown_probability is None or unknown_probability < 0.25)
    )
    stage = str(
        _first(phenology_posterior, ("most_likely_stage", "current_stage"), "UNKNOWN")
        or "UNKNOWN"
    ).upper()
    stage_confidence = _finite(_field(phenology_posterior, "stage_confidence", 0.0)) or 0.0
    phenology_supported = receipt.phenology_sufficient and stage != "UNKNOWN" and stage_confidence >= 0.6

    proposals: list[Dict[str, Any]] = []
    if receipt.archive_completeness < 0.75:
        proposals.append({
            "action_type": "archive_retrieval",
            "eig": 0.22,
            "cost": "low",
            "latency": "hours_to_days",
            "reason": "Season archive completeness is below the diagnostic target; retrieve independent historical S2/S1 scenes and weather without crossing the as-of boundary.",
            "authority": "direct_observation_diagnostic",
            "opportunity": None,
        })
    if receipt.plant_date_status == "unknown":
        proposals.append({
            "action_type": "confirm_planting_date_range",
            "eig": 0.30,
            "cost": "low",
            "latency": "user_dependent",
            "reason": "The season boundary is latent; request an approximate planting-date range separately from crop identity confirmation.",
            "authority": "farmer_confirmed_context",
            "opportunity": None,
        })
    if receipt.red_edge_acquisition_count < 2 or receipt.optical_acquisition_count < 4:
        opportunity = _best_opportunity(opportunities, "sentinel2_red_edge", as_of)
        cloud = opportunity["cloud"] if opportunity else None
        proposals.append({
            "action_type": "sentinel2_red_edge",
            "eig": max(0.03, 0.27 * (1.0 - (cloud if cloud is not None else 0.5))),
            "cost": "low",
            "latency": "next_available_pass",
            "reason": "Independent red-edge transition support is insufficient; select the lowest-cloud available S2 opportunity.",
            "authority": "direct_observation_diagnostic",
            "opportunity": opportunity,
        })
    if receipt.sar_acquisition_count < 1:
        opportunity = _best_opportunity(opportunities, "sentinel1_observation", as_of)
        proposals.append({
            "action_type": "sentinel1_observation",
            "eig": 0.12,
            "cost": "low",
            "latency": "next_available_pass",
            "reason": "No independent SAR acquisition covers this season; request S1 structure evidence that is less sensitive to clouds.",
            "authority": "direct_observation_diagnostic",
            "opportunity": opportunity,
        })
    if not species_supported:
        proposals.append({
            "action_type": "field_photo",
            "eig": 0.34,
            "cost": "medium",
            "latency": "user_dependent",
            "reason": "Species-level support is not calibrated and sufficient; request a geotagged field photo rather than forcing a species label.",
            "authority": "field_observation_pending_review",
            "opportunity": None,
        })
    if not phenology_supported and receipt.archive_completeness >= 0.75:
        proposals.append({
            "action_type": "wait_for_transition_window",
            "eig": 0.10,
            "cost": "none",
            "latency": "phenology_dependent",
            "reason": "Current stage support is weak; wait for a discriminative transition window unless field evidence is available sooner.",
            "authority": "diagnostic_only",
            "opportunity": None,
        })

    # Highest estimated scientific utility first.  This ranking itself is
    # diagnostic unless the EIG calibration receipt is present.
    proposals.sort(key=lambda item: (-float(item["eig"]), item["action_type"]))
    actions = tuple(
        CropAcquisitionActionV1(
            action_type=item["action_type"],
            priority=index + 1,
            expected_information_gain=float(item["eig"]),
            information_gain_status=eig_status,
            cost_class=item["cost"],
            latency_class=item["latency"],
            availability_start=(
                _iso(item["opportunity"]["start"]) if item["opportunity"] else None
            ),
            availability_end=(
                _iso(item["opportunity"]["end"]) if item["opportunity"] else None
            ),
            cloud_probability=(
                item["opportunity"]["cloud"] if item["opportunity"] else None
            ),
            reason=item["reason"],
            expected_evidence_authority=item["authority"],
            calibration_receipt_id=eig_calibration_receipt_id,
        )
        for index, item in enumerate(proposals)
    )

    return CropActiveAcquisitionPlanV1(
        namespace=receipt.namespace,
        crop_cycle_id=receipt.crop_cycle_id,
        valid_time=receipt.as_of,
        evidence_receipt_hash=receipt.content_hash,
        crop_posterior_hash=_field(crop_posterior, "content_hash", None),
        phenology_posterior_hash=_field(phenology_posterior, "content_hash", None),
        current_posterior_entropy=entropy,
        entropy_status=entropy_status,
        candidate_hypotheses=hypotheses,
        actions=actions,
        planner_authority=(
            "diagnostic_calibrated_utility"
            if eig_calibration_receipt_id
            else "diagnostic_estimated_utility"
        ),
    )


__all__ = [
    "CROP_SEASON_EVIDENCE_RECEIPT_VERSION",
    "CROP_ACTIVE_ACQUISITION_PLAN_VERSION",
    "CropSeasonEvidenceReceiptV1",
    "CropAcquisitionActionV1",
    "CropActiveAcquisitionPlanV1",
    "build_crop_season_evidence_receipt",
    "build_crop_active_acquisition_plan",
]

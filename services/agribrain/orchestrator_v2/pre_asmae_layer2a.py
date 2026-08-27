"""Pre-ASMAE crop/phenology authority helpers.

This module closes two orchestration seams without owning orchestration order:

* build a Layer-2A input from the *selected* observations in a verified
  ``CropEvidenceLedgerV2``; and
* publish/read crop and phenology events through the canonical worldline using
  the complete authenticated ``PlotNamespace``.

The main runner deliberately remains the owner of when these helpers execute.
No generic Layer-1 temporal row is admitted as crop evidence here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, time, timezone
import hashlib
import json
import math
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from services.agribrain.common.plot_namespace import (
    PlotNamespace,
    namespace_payload,
)
from services.agribrain.layer2_veg_int.features.ledger_crop_features import (
    ledger_rows_for_observations,
)
from services.agribrain.scientific_contracts.crop_cycle_segmentation import (
    CropCycleSegmentationReceiptV1,
    build_crop_cycle_segmentation_receipt,
)
from services.agribrain.scientific_contracts.crop_model_input import (
    normalize_verified_crop_evidence_ledger,
)
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    WorldlineEventProposal,
)


PRE_ASMAE_LAYER2A_CONTRACT_VERSION = "pre-asmae-layer2a-v1"
CROP_POSTERIOR_EVENT_TYPE = "CROP_POSTERIOR"
PHENOLOGY_POSTERIOR_EVENT_TYPE = "PHENOLOGY_POSTERIOR"

_WEATHER_ALIASES: Dict[str, Tuple[str, ...]] = {
    "rain": ("rain", "rainfall", "precipitation", "precipitation_mm"),
    "tmean": ("tmean", "temp_mean", "temperature", "temperature_mean"),
    "temp_min": ("temp_min", "tmin", "temperature_min"),
    "temp_max": ("temp_max", "tmax", "temperature_max"),
    "et0": ("et0", "eto", "reference_et"),
}


@dataclass(frozen=True)
class CanonicalCropPosteriorRecord:
    """A crop posterior transported with its canonical event identity.

    The event envelope is deliberately kept separate from the scientific
    posterior so callers cannot accidentally include mutable storage metadata
    in a posterior content hash or feed it back as temporal evidence.
    """

    posterior: Dict[str, Any]
    worldline_event_id: str
    event_sequence: int
    effective_at: str
    observation_or_valid_time: str


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
        default=str,
    )


def _content_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _parse_timestamp(value: Any, *, end_of_day: bool = False) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp is required")
    if len(text) == 10:
        parsed_date = datetime.strptime(text, "%Y-%m-%d").date()
        parsed = datetime.combine(
            parsed_date,
            time.max if end_of_day else time.min,
            tzinfo=timezone.utc,
        )
    else:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _date_key(value: Any) -> str:
    return _parse_timestamp(value).date().isoformat()


def _require_namespace(namespace: Any) -> PlotNamespace:
    if not isinstance(namespace, PlotNamespace) or not namespace.is_valid():
        raise ValueError("complete authenticated PlotNamespace is required")
    for label, value in (
        ("tenant_id", namespace.tenant_id),
        ("farm_id", namespace.farm_id),
        ("plot_id", namespace.plot_id),
    ):
        text = str(value).strip()
        if text in {".", ".."} or any(char in text for char in ("/", "\\", "\x00")):
            raise ValueError(f"unsafe PlotNamespace {label}")
    return namespace


def _cycle_hypothesis_id(inputs: Any, crop_config: Mapping[str, Any]) -> str:
    posterior = crop_config.get("crop_posterior")
    posterior = posterior if isinstance(posterior, Mapping) else {}
    cycle_context = getattr(inputs, "crop_cycle_context", None)
    if hasattr(cycle_context, "to_dict"):
        cycle_context = cycle_context.to_dict()
    cycle_context = cycle_context if isinstance(cycle_context, Mapping) else {}
    for source in (posterior, cycle_context, crop_config):
        for key in (
            "crop_cycle_identity",
            "crop_cycle_id",
            "crop_season_id",
            "cycle_id",
            "season_id",
        ):
            value = str(source.get(key) or "").strip()
            if value:
                return value
    return "unresolved-cycle"


def _weather_index(
    records: Sequence[Mapping[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """Build deterministic date-keyed meteorological forcing only.

    Spectral/index fields are intentionally absent from the allow-list, so a
    generic temporal record cannot become additional crop evidence through
    this join.
    """
    candidates: Dict[str, list[Tuple[str, Dict[str, float]]]] = {}
    for raw in records or ():
        if not isinstance(raw, Mapping):
            continue
        stamp = raw.get("date") or raw.get("timestamp") or raw.get("sensing_time")
        if not stamp:
            continue
        values: Dict[str, float] = {}
        for target, aliases in _WEATHER_ALIASES.items():
            selected = next(
                (_finite(raw.get(alias)) for alias in aliases if _finite(raw.get(alias)) is not None),
                None,
            )
            if selected is not None:
                values[target] = selected
        if values:
            candidates.setdefault(_date_key(stamp), []).append(
                (_canonical_json(values), values)
            )
    return {
        day: dict(sorted(items, key=lambda item: item[0])[-1][1])
        for day, items in candidates.items()
    }


@dataclass(frozen=True)
class PreASMAELayer2AInputBundle:
    """Immutable references plus a deterministic, JSON-safe input receipt."""

    inputs: Any
    tensor: Any
    segmentation: CropCycleSegmentationReceiptV1
    selected_observation_ids: Tuple[str, ...]
    input_receipt: Mapping[str, Any]


@dataclass(frozen=True)
class PreASMAELayer2AResult:
    bundle: PreASMAELayer2AInputBundle
    output: Any
    asmae_context: Mapping[str, Any]


def build_pre_asmae_layer2a_input(
    inputs: Any,
    layer1_tensor: Any,
    *,
    weather_records: Sequence[Mapping[str, Any]] = (),
) -> PreASMAELayer2AInputBundle:
    """Create a current-cycle Layer-2A input from ledger representatives only.

    The function fails closed on namespace/hash/as-of mismatches.  It clones
    both frozen orchestrator input and the Layer-1 tensor, and never mutates the
    caller's objects.
    """
    namespace = _require_namespace(getattr(inputs, "plot_namespace", None))
    crop_config = getattr(inputs, "crop_config", None)
    crop_config = dict(crop_config) if isinstance(crop_config, Mapping) else {}
    ledger_payload = crop_config.get("crop_evidence_ledger")
    if not isinstance(ledger_payload, Mapping):
        raise ValueError("pre-ASMAE Layer-2A requires CropEvidenceLedgerV2")
    ledger = normalize_verified_crop_evidence_ledger(ledger_payload)
    if ledger.plot_namespace != namespace:
        raise ValueError("pre-ASMAE Layer-2A ledger namespace mismatch")
    declared_ledger_hash = str(
        crop_config.get("crop_evidence_ledger_hash") or ""
    ).strip()
    if declared_ledger_hash != ledger.ledger_hash:
        raise ValueError("pre-ASMAE Layer-2A ledger identity mismatch")

    segmentation = build_crop_cycle_segmentation_receipt(
        ledger,
        crop_cycle_hypothesis_id=_cycle_hypothesis_id(inputs, crop_config),
    )
    posterior = crop_config.get("crop_posterior")
    posterior = posterior if isinstance(posterior, Mapping) else {}
    embedded = posterior.get("crop_cycle_segmentation_receipt")
    embedded = embedded if isinstance(embedded, Mapping) else {}
    expected_segmentation_hash = str(
        posterior.get("crop_cycle_segmentation_receipt_hash")
        or embedded.get("content_hash")
        or ""
    ).strip()
    if (
        expected_segmentation_hash
        and expected_segmentation_hash != segmentation.content_hash
    ):
        raise ValueError("pre-ASMAE Layer-2A segmentation identity mismatch")

    selected_ids = tuple(segmentation.current_observation_ids)
    rows = ledger_rows_for_observations(ledger, selected_ids)
    date_range = getattr(inputs, "date_range", None)
    date_range = date_range if isinstance(date_range, Mapping) else {}
    as_of_text = str(date_range.get("end") or "").strip()
    if not as_of_text:
        raise ValueError("pre-ASMAE Layer-2A requires an explicit as-of date")
    as_of = _parse_timestamp(as_of_text, end_of_day=True)
    forcing_by_day = _weather_index(weather_records)

    selected_rows: list[Dict[str, Any]] = []
    for source_row in rows:
        sensing_time = str(
            source_row.get("timestamp") or source_row.get("date") or ""
        ).strip()
        if _parse_timestamp(sensing_time) > as_of:
            raise ValueError("pre-ASMAE Layer-2A selection contains future evidence")
        row = {
            key: value
            for key, value in source_row.items()
            if not str(key).startswith("_")
        }
        row["sensing_time"] = sensing_time
        row["date"] = _date_key(sensing_time)
        row.update(forcing_by_day.get(row["date"], {}))
        if row.get("gdd_accumulated") is not None:
            row["gdd"] = row["gdd_accumulated"]
        ndvi = next(
            (
                _finite(row.get(key))
                for key in ("ndvi_mean", "ndvi", "ndvi_clean")
                if _finite(row.get(key)) is not None
            ),
            None,
        )
        row["is_observed"] = ndvi is not None
        reliability = _finite(row.get("reading_reliability"))
        row["uncertainty"] = (
            max(0.02, min(1.0, 1.0 - reliability))
            if reliability is not None else 0.1
        )
        row["crop_evidence_role"] = "selected_physical_representative"
        selected_rows.append(row)

    selected_rows.sort(
        key=lambda row: (row["sensing_time"], row["observation_hash"])
    )
    if tuple(row["observation_id"] for row in selected_rows) != selected_ids:
        raise ValueError("pre-ASMAE Layer-2A observation ordering mismatch")
    used_forcing = {
        day: forcing_by_day[day]
        for day in sorted({row["date"] for row in selected_rows})
        if day in forcing_by_day
    }

    receipt_without_hash: Dict[str, Any] = {
        "contract_version": PRE_ASMAE_LAYER2A_CONTRACT_VERSION,
        "plot_namespace": namespace_payload(namespace),
        "source_crop_evidence_ledger_hash": ledger.ledger_hash,
        "crop_cycle_segmentation_receipt_hash": segmentation.content_hash,
        "crop_cycle_hypothesis_id": segmentation.primary_hypothesis_id,
        "selected_observation_ids": list(selected_ids),
        "selected_physical_acquisition_keys": [
            row["physical_acquisition_key"] for row in selected_rows
        ],
        "selected_rows_hash": _content_hash(selected_rows),
        "as_of": as_of.isoformat(),
        "weather_forcing_hash": _content_hash(used_forcing),
        "generic_plot_timeseries_consumed_as_crop_evidence": False,
    }
    input_receipt = {
        **receipt_without_hash,
        "content_hash": _content_hash(receipt_without_hash),
    }
    prepared_crop_config = {
        **crop_config,
        "crop_cycle_segmentation_receipt": segmentation.to_dict(),
        "crop_cycle_segmentation_receipt_hash": segmentation.content_hash,
        "pre_asmae_layer2a_input_receipt": input_receipt,
    }
    prepared_inputs = replace(inputs, crop_config=prepared_crop_config)
    prepared_tensor = replace(
        layer1_tensor,
        run_id=(
            "pre-asmae-layer2a-"
            + input_receipt["content_hash"][:24]
        ),
        time_index=[row["date"] for row in selected_rows],
        plot_timeseries=selected_rows,
        # Spatial products retain a different time axis. Layer-2A is temporal
        # crop/phenology only, so exposing them here would be a false join.
        zone_stats={},
    )
    return PreASMAELayer2AInputBundle(
        inputs=prepared_inputs,
        tensor=prepared_tensor,
        segmentation=segmentation,
        selected_observation_ids=selected_ids,
        input_receipt=input_receipt,
    )


def run_pre_asmae_layer2a(
    bundle: PreASMAELayer2AInputBundle,
    *,
    layer2_runner: Optional[Callable[[Any, Any], Any]] = None,
) -> PreASMAELayer2AResult:
    """Execute Layer-2A and expose only canonical crop-season context to ASMAE."""
    if layer2_runner is None:
        from services.agribrain.layer2_veg_int.runner import run_layer2_veg

        layer2_runner = run_layer2_veg
    output = layer2_runner(bundle.inputs, bundle.tensor)
    phenology = getattr(output, "phenology", None)
    canonical_phenology = getattr(phenology, "canonical_posterior", None)
    canonical_phenology = (
        dict(canonical_phenology)
        if isinstance(canonical_phenology, Mapping) else None
    )
    phenology_hash = (
        str(canonical_phenology.get("content_hash") or "").strip()
        if canonical_phenology else ""
    )
    season_receipt = getattr(output, "crop_season_evidence_receipt", None)
    season_receipt = dict(season_receipt) if isinstance(season_receipt, Mapping) else None
    if season_receipt is not None and str(
        season_receipt.get("source_evidence_ledger_hash") or ""
    ) != str(bundle.input_receipt["source_crop_evidence_ledger_hash"]):
        raise ValueError("pre-ASMAE Layer-2A season receipt ledger mismatch")
    acquisition_plan = getattr(output, "crop_active_acquisition_plan", None)
    acquisition_plan = (
        dict(acquisition_plan)
        if isinstance(acquisition_plan, Mapping) else None
    )
    context: Dict[str, Any] = {
        "pre_asmae_layer2a_status": (
            "available" if canonical_phenology and phenology_hash else "unavailable"
        ),
        "pre_asmae_layer2a_input_receipt": dict(bundle.input_receipt),
        "pre_asmae_layer2a_input_receipt_hash": bundle.input_receipt["content_hash"],
        "phenology_posterior": canonical_phenology,
        "phenology_posterior_hash": phenology_hash or None,
        "crop_season_evidence_receipt": season_receipt,
        "crop_season_evidence_receipt_hash": (
            season_receipt.get("content_hash") if season_receipt else None
        ),
        "crop_active_acquisition_plan": acquisition_plan,
        "crop_active_acquisition_plan_hash": (
            acquisition_plan.get("content_hash") if acquisition_plan else None
        ),
        "layer2a_run_id": str(getattr(output, "run_id", "") or ""),
    }
    return PreASMAELayer2AResult(
        bundle=bundle,
        output=output,
        asmae_context=context,
    )


def _validate_scientific_namespace(
    value: Mapping[str, Any], namespace: PlotNamespace,
) -> None:
    plot_id = str(value.get("plot_id") or "").strip()
    if plot_id and plot_id != namespace.plot_id:
        raise ValueError("worldline scientific payload plot namespace mismatch")
    for key in ("plot_namespace", "namespace"):
        declared = value.get(key)
        if isinstance(declared, Mapping) and dict(declared) != namespace_payload(namespace):
            raise ValueError("worldline scientific payload namespace mismatch")


def _worldline_coordinates(namespace: PlotNamespace) -> Dict[str, str]:
    namespace = _require_namespace(namespace)
    # CanonicalWorldlineService has three storage coordinates. Mapping the
    # authenticated tenant/farm/plot triple one-to-one removes the legacy
    # shared "default" partition.
    return {
        "tenant_id": namespace.tenant_id,
        "namespace": namespace.farm_id,
        "plot_id": namespace.plot_id,
    }


def _commit_scientific_event(
    service: CanonicalWorldlineService,
    *,
    plot_namespace: PlotNamespace,
    event_type: str,
    payload_key: str,
    scientific_payload: Mapping[str, Any],
    geometry_version: str,
    evidence_set_hash: str,
    model_version: str,
    authority_ref: str,
    effective_at: Any,
    observation_or_valid_time: Any,
    parent_event_ids: Sequence[Any] = (),
    envelope: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    namespace = _require_namespace(plot_namespace)
    scientific = dict(scientific_payload)
    _validate_scientific_namespace(scientific, namespace)
    required = {
        "geometry_version": str(geometry_version or "").strip(),
        "evidence_set_hash": str(evidence_set_hash or "").strip(),
        "model_version": str(model_version or "").strip(),
        "authority_ref": str(authority_ref or "").strip(),
        "effective_at": str(effective_at or "").strip(),
        "observation_or_valid_time": str(observation_or_valid_time or "").strip(),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise ValueError(
            "canonical crop/phenology proposal missing " + ",".join(missing)
        )
    payload = {
        "plot_namespace": namespace_payload(namespace),
        payload_key: scientific,
        **dict(envelope or {}),
    }
    proposal = WorldlineEventProposal(
        event_type=event_type,
        payload=payload,
        parent_event_ids=tuple(parent_event_ids),
        geometry_version=required["geometry_version"],
        evidence_set_hash=required["evidence_set_hash"],
        model_version=required["model_version"],
        authority_ref=required["authority_ref"],
        observation_or_valid_time=required["observation_or_valid_time"],
    )
    return service.commit_proposal(
        **_worldline_coordinates(namespace),
        proposal=proposal,
        effective_at=effective_at,
    )


def commit_crop_posterior_worldline(
    service: CanonicalWorldlineService,
    *,
    plot_namespace: PlotNamespace,
    crop_posterior: Mapping[str, Any],
    geometry_version: str,
    effective_at: Any,
    observation_or_valid_time: Any,
    parent_event_ids: Sequence[Any] = (),
    parent_orchestrator_run_id: Optional[str] = None,
    pass_name: str = "PRE_ASMAE",
) -> Dict[str, Any]:
    posterior = dict(crop_posterior)
    evidence_hash = str(
        posterior.get("crop_evidence_ledger_hash")
        or posterior.get("content_hash")
        or ""
    )
    engine_evidence = posterior.get("engine_evidence")
    engine_evidence = engine_evidence if isinstance(engine_evidence, Mapping) else {}
    return _commit_scientific_event(
        service,
        plot_namespace=plot_namespace,
        event_type=CROP_POSTERIOR_EVENT_TYPE,
        payload_key="crop_posterior",
        scientific_payload=posterior,
        geometry_version=geometry_version,
        evidence_set_hash=evidence_hash,
        model_version=str(
            engine_evidence.get("engine_version")
            or posterior.get("contract_version")
            or "crop-posterior-v1"
        ),
        authority_ref=str(posterior.get("authority") or "unavailable"),
        effective_at=effective_at,
        observation_or_valid_time=observation_or_valid_time,
        parent_event_ids=parent_event_ids,
        envelope={
            "parent_orchestrator_run_id": parent_orchestrator_run_id,
            "pass": pass_name,
        },
    )


def commit_phenology_posterior_worldline(
    service: CanonicalWorldlineService,
    *,
    plot_namespace: PlotNamespace,
    phenology_posterior: Mapping[str, Any],
    geometry_version: str,
    effective_at: Any,
    observation_or_valid_time: Any,
    parent_event_ids: Sequence[Any] = (),
    parent_orchestrator_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    posterior = dict(phenology_posterior)
    return _commit_scientific_event(
        service,
        plot_namespace=plot_namespace,
        event_type=PHENOLOGY_POSTERIOR_EVENT_TYPE,
        payload_key="phenology_posterior",
        scientific_payload=posterior,
        geometry_version=geometry_version,
        evidence_set_hash=str(
            posterior.get("evidence_ledger_hash")
            or posterior.get("content_hash")
            or ""
        ),
        model_version=str(
            posterior.get("contract_version")
            or posterior.get("calibration_status")
            or "phenology-posterior-v1"
        ),
        authority_ref=str(
            posterior.get("stage_authority")
            or posterior.get("authority")
            or "unavailable"
        ),
        effective_at=effective_at,
        observation_or_valid_time=observation_or_valid_time,
        parent_event_ids=parent_event_ids,
        envelope={"parent_orchestrator_run_id": parent_orchestrator_run_id},
    )


def load_latest_crop_phenology_event(
    service: CanonicalWorldlineService,
    *,
    plot_namespace: PlotNamespace,
    event_type: str,
) -> Optional[Dict[str, Any]]:
    """Read the latest typed event and verify its complete namespace binding."""
    if event_type not in {CROP_POSTERIOR_EVENT_TYPE, PHENOLOGY_POSTERIOR_EVENT_TYPE}:
        raise ValueError("unsupported crop/phenology worldline event type")
    namespace = _require_namespace(plot_namespace)
    coordinates = _worldline_coordinates(namespace)
    head = service.load_head(**coordinates)
    event_id = str((head.get("latest_by_type") or {}).get(event_type) or "").strip()
    if not event_id:
        return None
    event = service.load_event(event_id=event_id, **coordinates)
    if not event:
        raise ValueError("canonical crop/phenology head references a missing event")
    if (
        event.get("tenant_id") != namespace.tenant_id
        or event.get("namespace") != namespace.farm_id
        or event.get("plot_id") != namespace.plot_id
    ):
        raise ValueError("canonical crop/phenology event namespace mismatch")
    payload = event.get("payload")
    payload = payload if isinstance(payload, Mapping) else {}
    if payload.get("plot_namespace") != namespace_payload(namespace):
        raise ValueError("canonical crop/phenology payload namespace mismatch")
    return dict(event)


def load_latest_crop_posterior(
    service: CanonicalWorldlineService,
    *,
    plot_namespace: PlotNamespace,
) -> Optional[Dict[str, Any]]:
    record = load_latest_crop_posterior_record(
        service,
        plot_namespace=plot_namespace,
    )
    return dict(record.posterior) if record is not None else None


def load_latest_crop_posterior_record(
    service: CanonicalWorldlineService,
    *,
    plot_namespace: PlotNamespace,
) -> Optional[CanonicalCropPosteriorRecord]:
    """Load one verified event and keep its identity bound to its posterior."""
    event = load_latest_crop_phenology_event(
        service,
        plot_namespace=plot_namespace,
        event_type=CROP_POSTERIOR_EVENT_TYPE,
    )
    if event is None:
        return None
    payload = event.get("payload") or {}
    posterior = payload.get("crop_posterior")
    if not isinstance(posterior, Mapping):
        raise ValueError("canonical crop-posterior event has no scientific payload")
    event_id = str(event.get("event_id") or "").strip()
    if not event_id:
        raise ValueError("canonical crop-posterior event has no event identity")
    return CanonicalCropPosteriorRecord(
        posterior=dict(posterior),
        worldline_event_id=event_id,
        event_sequence=int(event.get("sequence") or 0),
        effective_at=str(event.get("effective_at") or ""),
        observation_or_valid_time=str(
            event.get("observation_or_valid_time") or ""
        ),
    )


def load_latest_phenology_posterior(
    service: CanonicalWorldlineService,
    *,
    plot_namespace: PlotNamespace,
) -> Optional[Dict[str, Any]]:
    event = load_latest_crop_phenology_event(
        service,
        plot_namespace=plot_namespace,
        event_type=PHENOLOGY_POSTERIOR_EVENT_TYPE,
    )
    if event is None:
        return None
    payload = event.get("payload") or {}
    posterior = payload.get("phenology_posterior")
    return dict(posterior) if isinstance(posterior, Mapping) else None


__all__ = [
    "PRE_ASMAE_LAYER2A_CONTRACT_VERSION",
    "CROP_POSTERIOR_EVENT_TYPE",
    "PHENOLOGY_POSTERIOR_EVENT_TYPE",
    "CanonicalCropPosteriorRecord",
    "PreASMAELayer2AInputBundle",
    "PreASMAELayer2AResult",
    "build_pre_asmae_layer2a_input",
    "run_pre_asmae_layer2a",
    "commit_crop_posterior_worldline",
    "commit_phenology_posterior_worldline",
    "load_latest_crop_phenology_event",
    "load_latest_crop_posterior",
    "load_latest_crop_posterior_record",
    "load_latest_phenology_posterior",
]

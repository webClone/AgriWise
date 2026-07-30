"""Atomic evidence classification and executable capability planning for ASMAE.

The Layer 0 boundary is a graph, not a flat list: source-package wrappers own
packets, scene products, Kalman observations and process forcings.  This module
flattens that graph into content-bound atomic nodes, classifies each node, and
then builds the only Layer 0/temporal/composite inputs that ASMAE is allowed to
execute.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import dataclass, field, is_dataclass, fields
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

EVIDENCE_CAPABILITY_CONTRACT_VERSION = "evidence_capability_contract_v4_executable_mapping"


class EvidenceCapability(str, Enum):
    SPATIAL_PROVIDER_SCENE = "spatial_provider_scene"
    TEMPORAL_PLOT_OBSERVATION = "temporal_plot_observation"
    COMPOSITE_RASTER = "composite_raster"
    UNKNOWN_OR_INVALID = "unknown_or_invalid"


_DIRECT_SIGNAL_KEYS = {
    "ndvi": ("ndvi", "ndvi_mean", "NDVI", "ndvi_clean", "ndvi_interpolated"),
    "evi": ("evi", "evi_mean", "EVI"),
    "ndmi": ("ndmi", "ndmi_mean", "NDMI"),
    "ndre": ("ndre", "ndre_mean", "NDRE"),
    "reip": ("reip", "reip_mean", "REIP"),
    "vv": ("vv", "vv_db", "vv_db_mean", "sar_vv", "VV"),
    "vh": ("vh", "vh_db", "vh_db_mean", "sar_vh", "VH"),
}
_PROCESS_SIGNAL_KEYS = {
    "temp_max": ("temp_max", "temp_max_c", "temperature_max", "temperature_2m_max"),
    "temp_min": ("temp_min", "temp_min_c", "temperature_min", "temperature_2m_min"),
    "temp_mean": ("temp_mean", "temp_mean_c", "temperature_mean", "temperature_2m"),
    "precipitation": ("precipitation", "precipitation_mm", "rainfall", "rainfall_mm"),
    "et0": ("et0", "et0_mm", "evapotranspiration"),
    "humidity": ("humidity", "humidity_mean_pct", "relative_humidity"),
    "soil_moisture": ("soil_moisture", "soil_moisture_pct", "volumetric_water_content"),
    "soil_ec": ("ec", "soil_ec", "soil_ec_ds_m"),
}
_ALL_SIGNAL_KEYS = {**_DIRECT_SIGNAL_KEYS, **_PROCESS_SIGNAL_KEYS}
_CHILD_COLLECTION_KEYS = (
    "packets", "scenes", "observations", "records", "timeseries",
    "kalman_observations", "process_forcing", "process_forcings",
)


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _public(obj: Any) -> Dict[str, Any]:
    """Return public fields and understand raw manifest object wrappers."""
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        value = dict(obj)
        if value.get("__asmae_manifest_type__") == "object_v1" and isinstance(value.get("fields"), Mapping):
            return dict(value["fields"])
        return value
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: getattr(obj, f.name) for f in fields(obj) if not f.name.startswith("_")}
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not str(k).startswith("_")}
    return {}


def _mapping(value: Any) -> Dict[str, Any]:
    return _public(value)


def _merged_public(obj: Any) -> Dict[str, Any]:
    """Expose packet payload and scene metadata without losing the envelope."""
    base = _public(obj)
    merged = dict(base)
    for key in ("metadata", "scene_metadata"):
        nested = _mapping(base.get(key))
        for name, value in nested.items():
            merged.setdefault(name, value)
    payload = _mapping(base.get("payload"))
    for name, value in payload.items():
        merged.setdefault(name, value)
    grid_spec = _mapping(payload.get("grid_spec") or base.get("grid_spec"))
    for name in ("crs", "transform", "width", "height", "bounds"):
        if name in grid_spec:
            merged.setdefault(name, grid_spec[name])
    if merged.get("acquisition_time") is None:
        merged["acquisition_time"] = (
            merged.get("acquisition_datetime") or merged.get("acquired_at")
            or merged.get("timestamp") or merged.get("date")
        )
    if merged.get("scene_id") is None and _obs_type(merged) in ("raster", "spatial_scene", "raster_scene"):
        merged["scene_id"] = merged.get("packet_id")
    if merged.get("band_arrays") is None:
        merged["band_arrays"] = merged.get("bands") or payload.get("bands")
    if merged.get("band_refs") is None:
        merged["band_refs"] = merged.get("local_cache_refs") or payload.get("band_refs")
    if merged.get("mask_refs") is None:
        merged["mask_refs"] = payload.get("mask_refs") or payload.get("masks")
    return merged


def _obs_type(d: Mapping[str, Any]) -> str:
    value = _enum_value(d.get("obs_type") or d.get("observation_type") or "")
    text = str(value).lower()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
        return number if number == number and abs(number) < 1e308 else None
    except (TypeError, ValueError):
        return None


def _has_raster_geometry(d: Mapping[str, Any]) -> bool:
    transform = d.get("transform")
    try:
        values = list(transform)
        valid_transform = len(values) == 6 and any(abs(float(v)) > 0.0 for v in values)
        return valid_transform and int(d.get("width") or 0) > 0 and int(d.get("height") or 0) > 0
    except (TypeError, ValueError):
        return False


def _has_time(d: Mapping[str, Any]) -> bool:
    return bool(
        d.get("acquisition_time") or d.get("acquisition_datetime")
        or d.get("acquired_at") or d.get("timestamp") or d.get("date")
    )


def _has_band_evidence(d: Mapping[str, Any]) -> bool:
    return bool(
        d.get("band_refs") or d.get("band_arrays") or d.get("bands")
        or d.get("local_cache_refs")
    )


def _has_provider_receipt(d: Mapping[str, Any]) -> bool:
    provenance = _mapping(d.get("provenance"))
    qa = _mapping(d.get("qa"))
    quality = _mapping(d.get("quality"))
    return bool(
        provenance.get("asmae_scene_metadata") or provenance.get("provider_receipt")
        or d.get("provider_product_id") or d.get("process_request_hash")
        or d.get("provider_response_hash") or d.get("qa_score") is not None
        or d.get("valid_fraction") is not None or qa.get("valid_pixel_fraction") is not None
        or quality.get("valid_fraction") is not None
    )


def _extract_scalar_signals(d: Mapping[str, Any]) -> Dict[str, float]:
    payload = _mapping(d.get("payload"))
    result: Dict[str, float] = {}
    for canonical, aliases in _ALL_SIGNAL_KEYS.items():
        for alias in aliases:
            raw = d.get(alias) if d.get(alias) is not None else payload.get(alias)
            value = _finite(raw)
            if value is not None:
                result[canonical] = value
                break
    return result


def _direct_signals(signals: Mapping[str, float]) -> Dict[str, float]:
    return {key: float(value) for key, value in signals.items() if key in _DIRECT_SIGNAL_KEYS}


def _conditioned_states(signals: Mapping[str, float], direct: bool) -> Tuple[str, ...]:
    states: List[str] = []
    if direct:
        if "ndvi" in signals or "evi" in signals:
            states.extend(("vigor", "lai", "phenology_progress"))
        if "ndre" in signals or "reip" in signals:
            states.append("chlorophyll")
        if "ndmi" in signals:
            states.append("canopy_water")
        if "vv" in signals or "vh" in signals:
            states.append("structure")
    else:
        if any(key in signals for key in ("temp_max", "temp_min", "temp_mean", "humidity")):
            states.append("thermal_stress")
        if any(key in signals for key in ("precipitation", "et0", "soil_moisture")):
            states.append("root_zone_water")
        if "soil_ec" in signals:
            states.append("salinity_stress")
    return tuple(dict.fromkeys(states))


def _source_reality(d: Mapping[str, Any], family: str) -> str:
    metadata = _mapping(d.get("metadata"))
    return str(
        d.get("source_reality") or metadata.get("source_reality")
        or _mapping(d.get("provenance")).get("source_reality") or family
    ).lower()


def _intended_capability(d: Mapping[str, Any], family: str) -> EvidenceCapability:
    obs_type = _obs_type(d)
    family_lower = str(family).lower()
    if obs_type in ("raster", "spatial_scene", "raster_scene") or _has_raster_geometry(d):
        return EvidenceCapability.SPATIAL_PROVIDER_SCENE
    if "composite" in _source_reality(d, family) or "composite" in str(d.get("contract_type") or "").lower():
        return EvidenceCapability.COMPOSITE_RASTER
    if obs_type in ("point_ts", "point_timeseries", "tabular", "temporal", "daily_aggregate") or _has_time(d):
        return EvidenceCapability.TEMPORAL_PLOT_OBSERVATION
    if any(token in family_lower for token in ("sentinel1", "sentinel2", "_s1", "_s2")):
        return EvidenceCapability.SPATIAL_PROVIDER_SCENE
    return EvidenceCapability.UNKNOWN_OR_INVALID


def classify_package(pkg: Any, source_family: str) -> Tuple[EvidenceCapability, List[str], Dict[str, float]]:
    d = _merged_public(pkg)
    reasons: List[str] = []
    intended = _intended_capability(d, source_family)
    signals = _extract_scalar_signals(d)
    reality = _source_reality(d, source_family)
    contract_type = str(d.get("contract_type") or "").lower()

    if intended == EvidenceCapability.COMPOSITE_RASTER or "composite_raster" in contract_type:
        return EvidenceCapability.COMPOSITE_RASTER, [], signals

    if intended == EvidenceCapability.SPATIAL_PROVIDER_SCENE:
        if not _has_raster_geometry(d):
            reasons.append("missing_raster_geometry")
        if not (d.get("scene_id") or d.get("content_hash") or d.get("packet_id")):
            reasons.append("missing_scene_id")
        if not d.get("crs"):
            reasons.append("missing_crs")
        if not _has_time(d):
            reasons.append("missing_acquisition_time")
        if not (_has_band_evidence(d) or _has_provider_receipt(d)):
            reasons.append("missing_band_or_provider_receipt")
        if any(token in reality for token in ("proxy", "synthetic", "simulated")):
            reasons.append("non_provider_spatial_reality")
        if d.get("diagnostic_only") or d.get("spatial_visualization_unavailable") or d.get("data_status") == "unusable":
            reasons.append("diagnostic_only_package_not_spatial_provider_scene")
        if reasons:
            return EvidenceCapability.UNKNOWN_OR_INVALID, reasons, signals
        return EvidenceCapability.SPATIAL_PROVIDER_SCENE, [], signals

    if intended == EvidenceCapability.TEMPORAL_PLOT_OBSERVATION:
        if not _has_time(d):
            reasons.append("missing_acquisition_time")
        if not signals:
            reasons.append("no_scalar_signals_found")
        if reasons:
            return EvidenceCapability.UNKNOWN_OR_INVALID, reasons, {}
        return EvidenceCapability.TEMPORAL_PLOT_OBSERVATION, [], signals

    return EvidenceCapability.UNKNOWN_OR_INVALID, ["insufficient_fields_for_any_capability"], signals


def _sensor_for(d: Mapping[str, Any], family: str) -> Optional[str]:
    source = str(_enum_value(d.get("sensor") or d.get("source") or family)).lower()
    if any(token in source for token in ("sentinel2", "sentinel-2", "s2_")) or source == "s2":
        return "S2"
    if any(token in source for token in ("sentinel1", "sentinel-1", "s1_")) or source == "s1":
        return "S1"
    bands = {str(key).upper() for key in _mapping(d.get("band_arrays") or d.get("band_refs") or d.get("bands")).keys()}
    if {"B04", "B08"}.issubset(bands):
        return "S2"
    if bands.intersection({"VV", "VH"}):
        return "S1"
    return None


def _stable_node_hash(value: Any, family: str, path: Sequence[str], parent_id: Optional[str]) -> str:
    """Canonical path-independent scientific observation content hash."""
    d = _merged_public(value)
    canon_id = (
        d.get("packet_id")
        or d.get("observation_id")
        or d.get("provider_product_id")
        or d.get("scene_id")
        or d.get("content_hash")
    )
    acq_time = d.get("timestamp") or d.get("date") or d.get("acquisition_time") or d.get("time")
    sensor = _sensor_for(d, family)
    signals = _extract_scalar_signals(d)
    
    if canon_id or acq_time:
        canon_obj = {
            "canon_id": str(canon_id or ""),
            "acq_time": str(acq_time or ""),
            "sensor": str(sensor or ""),
            "signals": {k: float(v) for k, v in sorted(signals.items()) if v is not None},
        }
        return hashlib.sha256(json.dumps(canon_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    try:
        from .job_manifest import scientific_value_hash
        return scientific_value_hash({"value": value})
    except Exception:
        payload = json.dumps(_merged_public(value), sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _looks_like_atomic_scene(value: Any) -> bool:
    d = _merged_public(value)
    return _has_raster_geometry(d) and (_has_band_evidence(d) or _has_provider_receipt(d))


def _iter_atomic_values(
    value: Any,
    family: str,
    path: Tuple[str, ...],
    parent_id: Optional[str],
) -> Iterable[Tuple[Any, Tuple[str, ...], Optional[str]]]:
    if value is None:
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _iter_atomic_values(item, family, path + (str(index),), parent_id)
        return

    d = _public(value)
    if not d:
        yield value, path, parent_id
        return

    current_id = str(
        d.get("package_id") or d.get("scene_id") or d.get("packet_id")
        or d.get("content_hash") or parent_id or ""
    ) or None
    emitted_children = False
    for key in _CHILD_COLLECTION_KEYS:
        children = d.get(key)
        if not isinstance(children, (list, tuple)) or not children:
            continue
        emitted_children = True
        for index, child in enumerate(children):
            yield from _iter_atomic_values(
                child, family, path + (key, str(index)), current_id
            )

    # Scene packages often also own a one-row scalar packet.  Emit both the
    # scene package and that temporal packet; wrapper-only envelopes are not
    # misclassified as evidence.
    if _looks_like_atomic_scene(value) or not emitted_children:
        yield value, path, parent_id


@dataclass(frozen=True)
class EvidenceNode:
    evidence_node_id: str
    capability: EvidenceCapability
    intended_capability: EvidenceCapability
    source_family: str
    source_reality: str
    sensor: Optional[str]
    accepted: bool
    rejection_reasons: Tuple[str, ...]
    content_hash: str
    signals: Tuple[Tuple[str, float], ...]
    states_supported: Tuple[str, ...]
    parent_node_id: Optional[str]
    node_path: Tuple[str, ...]
    direct_observation: bool
    raw_value: Any = field(repr=False, compare=False)

    @property
    def signal_map(self) -> Dict[str, float]:
        return dict(self.signals)

    def public_record(self) -> Dict[str, Any]:
        return {
            "evidence_node_id": self.evidence_node_id,
            "capability": self.capability.value,
            "intended_capability": self.intended_capability.value,
            "source_family": self.source_family,
            "source_reality": self.source_reality,
            "sensor": self.sensor,
            "accepted": self.accepted,
            "rejection_reasons": list(self.rejection_reasons),
            "content_hash": self.content_hash,
            "signals": dict(self.signals),
            "states_supported": list(self.states_supported),
            "parent_node_id": self.parent_node_id,
            "node_path": list(self.node_path),
            "direct_observation": self.direct_observation,
        }


@dataclass(frozen=True)
class CapabilityPlan:
    spatial_scenes: Tuple[EvidenceNode, ...] = ()
    temporal_observations: Tuple[EvidenceNode, ...] = ()
    composite_rasters: Tuple[EvidenceNode, ...] = ()
    archive_posteriors: Tuple[EvidenceNode, ...] = ()
    context_priors: Tuple[EvidenceNode, ...] = ()
    rejected_nodes: Tuple[EvidenceNode, ...] = ()
    contract_version: str = EVIDENCE_CAPABILITY_CONTRACT_VERSION

    @property
    def spatial_scene_count(self) -> int:
        return len(self.spatial_scenes)

    @property
    def temporal_observation_count(self) -> int:
        return len(self.temporal_observations)

    @property
    def capability_summary(self) -> Dict[str, Any]:
        rejected_spatial = sum(
            node.intended_capability == EvidenceCapability.SPATIAL_PROVIDER_SCENE
            for node in self.rejected_nodes
        )
        rejected_temporal = sum(
            node.intended_capability == EvidenceCapability.TEMPORAL_PLOT_OBSERVATION
            for node in self.rejected_nodes
        )
        return {
            "contract_version": self.contract_version,
            "capability_plan_hash": self.plan_hash(),
            "spatial_scene_capability": {
                "status": "available" if self.spatial_scenes else "unavailable",
                "accepted_count": len(self.spatial_scenes),
                "rejected_count": rejected_spatial,
            },
            "temporal_capability": {
                "status": "available" if self.temporal_observations else "unavailable",
                "accepted_count": len(self.temporal_observations),
                "rejected_count": rejected_temporal,
                "direct_observation_count": sum(node.direct_observation for node in self.temporal_observations),
                "process_forcing_count": sum(not node.direct_observation for node in self.temporal_observations),
            },
            "composite_raster_capability": {
                "status": "available" if self.composite_rasters else "unavailable",
                "accepted_count": len(self.composite_rasters),
            },
            "unknown_quarantined": len(self.rejected_nodes),
        }

    def plan_hash(self) -> str:
        records = sorted(
            f"{node.evidence_node_id}:{node.content_hash}:{node.capability.value}"
            for node in (
                self.spatial_scenes + self.temporal_observations
                + self.composite_rasters + self.rejected_nodes
            )
        )
        encoded = json.dumps(
            {"contract": self.contract_version, "nodes": records},
            sort_keys=True, separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()[:24]

    def public_records(self) -> List[Dict[str, Any]]:
        return [
            node.public_record() for node in (
                self.spatial_scenes + self.temporal_observations
                + self.composite_rasters + self.rejected_nodes
            )
        ]

    def execution_layer0_packages(self) -> Dict[str, List[Any]]:
        packages: Dict[str, List[Any]] = {
            "asmae_sentinel2_real": [],
            "asmae_sentinel1_real": [],
        }
        seen: set[str] = set()
        for node in self.spatial_scenes:
            if node.content_hash in seen:
                continue
            seen.add(node.content_hash)
            key = "asmae_sentinel1_real" if node.sensor == "S1" else "asmae_sentinel2_real"
            packages[key].append(copy.deepcopy(node.raw_value))
        return packages

    def execution_plot_timeseries(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for node in self.temporal_observations:
            if not node.direct_observation or node.content_hash in seen:
                continue
            seen.add(node.content_hash)
            d = _merged_public(node.raw_value)
            row: Dict[str, Any] = {
                "timestamp": d.get("acquisition_time") or d.get("timestamp") or d.get("date"),
                "source": str(_enum_value(d.get("source") or node.source_family)),
                "content_hash": node.content_hash,
                "evidence_node_id": node.evidence_node_id,
                "quality": d.get("quality") or d.get("qa_score") or d.get("valid_fraction"),
                "uncertainty": d.get("uncertainty"),
                "data_status": str(_enum_value(d.get("data_status") or "observed")),
            }
            row.update(_direct_signals(node.signal_map))
            rows.append(row)
        rows.sort(key=lambda row: str(row.get("timestamp") or ""))
        return rows

    def execution_raster_composites(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for node in self.composite_rasters:
            result[node.source_family] = copy.deepcopy(node.raw_value)
        return result


def _make_node(
    raw: Any,
    family: str,
    path: Tuple[str, ...],
    parent_id: Optional[str],
) -> EvidenceNode:
    d = _merged_public(raw)
    capability, reasons, signals = classify_package(raw, family)
    intended = _intended_capability(d, family)
    content_hash = _stable_node_hash(raw, family, path, parent_id)
    base_id = str(
        d.get("scene_id") or d.get("packet_id") or d.get("content_hash")
        or d.get("observation_id") or f"{family}:{'/'.join(path)}"
    )
    node_id = f"{base_id}:{content_hash[:8]}"
    direct = bool(_direct_signals(signals)) and str(_enum_value(d.get("data_status") or "observed")).lower() == "observed"
    return EvidenceNode(
        evidence_node_id=node_id,
        capability=capability,
        intended_capability=intended,
        source_family=str(family),
        source_reality=_source_reality(d, family),
        sensor=_sensor_for(d, family),
        accepted=capability != EvidenceCapability.UNKNOWN_OR_INVALID,
        rejection_reasons=tuple(reasons),
        content_hash=content_hash,
        signals=tuple(sorted((key, float(value)) for key, value in signals.items())),
        states_supported=_conditioned_states(signals, direct),
        parent_node_id=parent_id,
        node_path=path,
        direct_observation=direct,
        raw_value=raw,
    )


def build_capability_plan(
    layer0_source_packages: Dict[str, Any],
    raster_composites: Optional[Dict[str, Any]] = None,
    plot_timeseries: Optional[Any] = None,
) -> CapabilityPlan:
    spatial: List[EvidenceNode] = []
    temporal: List[EvidenceNode] = []
    composites: List[EvidenceNode] = []
    rejected: List[EvidenceNode] = []

    for family, raw_packages in dict(layer0_source_packages or {}).items():
        for raw, path, parent_id in _iter_atomic_values(
            raw_packages, str(family), (str(family),), None
        ):
            node = _make_node(raw, str(family), path, parent_id)
            if node.capability == EvidenceCapability.SPATIAL_PROVIDER_SCENE:
                spatial.append(node)
            elif node.capability == EvidenceCapability.TEMPORAL_PLOT_OBSERVATION:
                temporal.append(node)
            elif node.capability == EvidenceCapability.COMPOSITE_RASTER:
                composites.append(node)
            else:
                rejected.append(node)

    if plot_timeseries:
        for raw, path, parent_id in _iter_atomic_values(
            plot_timeseries, "plot_timeseries", ("plot_timeseries",), None
        ):
            node = _make_node(raw, "plot_timeseries", path, parent_id)
            if node.capability == EvidenceCapability.TEMPORAL_PLOT_OBSERVATION:
                temporal.append(node)
            else:
                rejected.append(node)

    for key, composite in dict(raster_composites or {}).items():
        if composite is None:
            continue
        content_hash = _stable_node_hash(composite, str(key), ("raster_composites", str(key)), None)
        composites.append(EvidenceNode(
            evidence_node_id=f"composite:{key}:{content_hash[:8]}",
            capability=EvidenceCapability.COMPOSITE_RASTER,
            intended_capability=EvidenceCapability.COMPOSITE_RASTER,
            source_family=str(key),
            source_reality="provider_temporal_composite_raster",
            sensor=None,
            accepted=True,
            rejection_reasons=(),
            content_hash=content_hash,
            signals=(),
            states_supported=(),
            parent_node_id=None,
            node_path=("raster_composites", str(key)),
            direct_observation=False,
            raw_value=composite,
        ))

    # Atomic content identity, rather than wrapper position, performs dedupe.
    def unique(nodes: List[EvidenceNode]) -> Tuple[EvidenceNode, ...]:
        by_hash: Dict[str, EvidenceNode] = {}
        for node in nodes:
            by_hash.setdefault(node.content_hash, node)
        return tuple(by_hash[key] for key in sorted(by_hash))

    plan = CapabilityPlan(
        spatial_scenes=unique(spatial),
        temporal_observations=unique(temporal),
        composite_rasters=unique(composites),
        rejected_nodes=unique(rejected),
    )
    logger.info(
        "CapabilityPlan %s: %d spatial | %d temporal | %d composite | %d quarantined",
        plan.plan_hash(), len(plan.spatial_scenes), len(plan.temporal_observations),
        len(plan.composite_rasters), len(plan.rejected_nodes),
    )
    return plan


def prepare_capability_execution_context(context: Mapping[str, Any]) -> Tuple[Dict[str, Any], CapabilityPlan]:
    """Freeze evidence first, then construct the exact executable ASMAE inputs."""
    base = dict(context or {})
    if base.get("_capability_plan_prepared") is True:
        # The manifest already binds the original atomic-node ledger and the
        # normalized execution inputs in its context hash.  Reclassify the
        # execution inputs for runtime validation, but do not replace the
        # original plan hash with a second-generation normalized-plan hash.
        plan = build_capability_plan(
            dict(base.get("layer0_source_packages") or {}),
            dict(base.get("raster_composites") or {}),
            base.get("plot_timeseries") or [],
        )
        return base, plan
    plan = build_capability_plan(
        dict(base.get("layer0_source_packages") or {}),
        dict(base.get("raster_composites") or {}),
        base.get("plot_timeseries") or [],
    )
    prepared = dict(base)
    prepared["layer0_source_packages"] = plan.execution_layer0_packages()
    prepared["plot_timeseries"] = plan.execution_plot_timeseries()
    prepared["raster_composites"] = plan.execution_raster_composites()
    prepared["evidence_capability_contract_version"] = plan.contract_version
    prepared["capability_plan_hash"] = plan.plan_hash()
    prepared["capability_plan_summary"] = plan.capability_summary
    prepared["capability_plan_nodes"] = plan.public_records()
    prepared["_capability_plan_prepared"] = True
    return prepared, plan

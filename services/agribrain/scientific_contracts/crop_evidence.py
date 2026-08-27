"""Immutable scientific contracts for crop observations and evidence ledgers.

The contracts deliberately separate a physical acquisition from provider
processing products.  Hashes cover the complete plot namespace, QA/support,
feature measurements, and processing lineage using deterministic JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
import json
import math
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from services.agribrain.common.plot_namespace import PlotNamespace

from .exceptions import ContractViolation


CROP_OBSERVATION_CONTRACT_VERSION = "canonical_crop_observation_v2"
CROP_EVIDENCE_LEDGER_CONTRACT_VERSION = "crop_evidence_ledger_v2"


_FEATURE_SOURCE_BANDS: Dict[str, Tuple[str, ...]] = {
    "ndvi": ("B04", "B08"),
    "evi": ("B02", "B04", "B08"),
    "ndre": ("B05", "B8A"),
    "cired": ("B05", "B8A"),
    "ndmi": ("B08", "B11"),
    "lswi": ("B08", "B11"),
    "psri": ("B02", "B04", "B06"),
    "mtci": ("B04", "B05", "B06"),
    "red_edge_slope_1": ("B04", "B05"),
    "red_edge_slope_2": ("B05", "B06"),
    "red_edge_slope_3": ("B06", "B07"),
    "vv_vh_ratio": ("VV", "VH"),
    "vv_minus_vh_db": ("VV", "VH"),
    "rvi": ("VV", "VH"),
    "cross_pol_fraction": ("VV", "VH"),
}


def _namespace(value: Any) -> PlotNamespace:
    if isinstance(value, PlotNamespace):
        candidate = value
    elif isinstance(value, Mapping):
        candidate = PlotNamespace(
            tenant_id=str(value.get("tenant_id") or "").strip(),
            farm_id=str(value.get("farm_id") or "").strip(),
            plot_id=str(value.get("plot_id") or "").strip(),
        )
    elif all(hasattr(value, name) for name in ("tenant_id", "farm_id", "plot_id")):
        candidate = PlotNamespace(
            tenant_id=str(getattr(value, "tenant_id") or "").strip(),
            farm_id=str(getattr(value, "farm_id") or "").strip(),
            plot_id=str(getattr(value, "plot_id") or "").strip(),
        )
    else:
        raise ContractViolation("crop_evidence_requires_full_plot_namespace")
    if not candidate.is_valid():
        raise ContractViolation("crop_evidence_requires_full_plot_namespace")
    return PlotNamespace(*candidate.to_tuple())


def _namespace_dict(value: PlotNamespace) -> Dict[str, str]:
    return {
        "tenant_id": value.tenant_id.strip(),
        "farm_id": value.farm_id.strip(),
        "plot_id": value.plot_id.strip(),
    }


def _canonical_data(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractViolation("crop_evidence_contains_nonfinite_float")
        return 0.0 if value == 0.0 else value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_data(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_data(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [_canonical_data(item) for item in value]
        return sorted(normalized, key=_canonical_json)
    if isinstance(value, datetime):
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "item") and callable(value.item):
        return _canonical_data(value.item())
    if hasattr(value, "tolist") and callable(value.tolist):
        return _canonical_data(value.tolist())
    raise ContractViolation(
        f"crop_evidence_contains_unsupported_type:{type(value).__name__}"
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical_data(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    )


def _hash(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest}"


def _normalized_time(value: Any, *, required: bool = False) -> Optional[str]:
    if value in (None, ""):
        if required:
            raise ContractViolation("crop_observation_sensing_time_required")
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractViolation("invalid_crop_observation_time") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _fraction(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ContractViolation(f"invalid_crop_qa_fraction:{name}")
    try:
        parsed = float(value or 0.0)
    except (TypeError, ValueError) as exc:
        raise ContractViolation(f"invalid_crop_qa_fraction:{name}") from exc
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise ContractViolation(f"invalid_crop_qa_fraction:{name}")
    return parsed


def _optional_fraction(value: Any, name: str) -> Optional[float]:
    if value in (None, ""):
        return None
    return _fraction(value, name)


@dataclass(frozen=True)
class CropFeatureContributionV2:
    feature_name: str
    statistic: str
    value: float
    valid_pixel_count: int
    support_hash: str
    source_bands: Tuple[str, ...] = ()
    contribution_role: str = "observed_model_input_candidate"

    def __post_init__(self) -> None:
        if not self.feature_name.strip() or not self.statistic.strip():
            raise ContractViolation("crop_feature_name_and_statistic_required")
        if not math.isfinite(float(self.value)):
            raise ContractViolation("crop_feature_value_nonfinite")
        if int(self.valid_pixel_count) <= 0:
            raise ContractViolation("crop_feature_requires_positive_valid_support")
        if not self.support_hash.strip():
            raise ContractViolation("crop_feature_support_hash_required")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "statistic": self.statistic,
            "value": float(self.value),
            "valid_pixel_count": int(self.valid_pixel_count),
            "support_hash": self.support_hash,
            "source_bands": list(self.source_bands),
            "contribution_role": self.contribution_role,
        }


@dataclass(frozen=True)
class CropObservationQAV2:
    admitted: bool
    quality_class: str
    rejection_reasons: Tuple[str, ...]
    valid_pixel_count: int
    field_pixel_count: int
    valid_fraction: float
    cloud_fraction: Optional[float]
    shadow_fraction: Optional[float]
    snow_fraction: Optional[float]
    nodata_fraction: float
    reading_reliability: float
    support_hash: str
    support_definition: str
    grid_identity_hash: str

    def __post_init__(self) -> None:
        if int(self.valid_pixel_count) < 0 or int(self.field_pixel_count) < 0:
            raise ContractViolation("crop_qa_pixel_count_negative")
        if int(self.valid_pixel_count) > int(self.field_pixel_count):
            raise ContractViolation("crop_qa_valid_pixels_exceed_field_pixels")
        for name in ("valid_fraction", "nodata_fraction", "reading_reliability"):
            _fraction(getattr(self, name), name)
        for name in ("cloud_fraction", "shadow_fraction", "snow_fraction"):
            if getattr(self, name) is not None:
                _fraction(getattr(self, name), name)
        if not self.support_hash.strip() or not self.grid_identity_hash.strip():
            raise ContractViolation("crop_qa_support_identity_required")
        if not self.support_definition.strip():
            raise ContractViolation("crop_qa_support_definition_required")
        if self.admitted and self.rejection_reasons:
            raise ContractViolation("admitted_crop_observation_has_rejection_reasons")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "admitted": self.admitted,
            "quality_class": self.quality_class,
            "rejection_reasons": list(self.rejection_reasons),
            "valid_pixel_count": self.valid_pixel_count,
            "field_pixel_count": self.field_pixel_count,
            "valid_fraction": self.valid_fraction,
            "cloud_fraction": self.cloud_fraction,
            "shadow_fraction": self.shadow_fraction,
            "snow_fraction": self.snow_fraction,
            "nodata_fraction": self.nodata_fraction,
            "reading_reliability": self.reading_reliability,
            "support_hash": self.support_hash,
            "support_definition": self.support_definition,
            "grid_identity_hash": self.grid_identity_hash,
        }


@dataclass(frozen=True)
class CropProcessingLineageV2:
    provider_product_id: str = ""
    catalog_item_id: str = ""
    processing_timestamp: str = ""
    processing_baseline: str = ""
    content_hash: str = ""
    process_request_hash: str = ""
    provider_response_hash: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CropProcessingLineageV2":
        return cls(**{
            name: str(value.get(name) or "").strip()
            for name in cls.__dataclass_fields__
        })

    def stable_key(self) -> Tuple[str, ...]:
        return tuple(str(getattr(self, name)) for name in self.__dataclass_fields__)

    def to_dict(self) -> Dict[str, str]:
        return {
            name: str(getattr(self, name))
            for name in self.__dataclass_fields__
        }


def _qa_from_mapping(value: Mapping[str, Any]) -> CropObservationQAV2:
    support = value.get("pixel_support_contract")
    support = dict(support) if isinstance(support, Mapping) else {}
    grid_identity = support.get("grid_identity")
    grid_identity = dict(grid_identity) if isinstance(grid_identity, Mapping) else {}
    if not grid_identity:
        raise ContractViolation("crop_observation_grid_identity_required")
    support_hash = str(support.get("support_hash") or "").strip()
    if not support_hash:
        raise ContractViolation("crop_observation_pixel_support_hash_required")
    return CropObservationQAV2(
        admitted=(
            value.get("quality_admitted") is True
            or str(value.get("admission_status") or "").lower() == "admitted"
        ),
        quality_class=str(value.get("quality_class") or "unknown").strip().lower(),
        rejection_reasons=tuple(sorted({
            str(reason).strip() for reason in (
                value.get("quality_rejection_reasons")
                or value.get("admission_reasons")
                or []
            )
            if str(reason).strip()
        })),
        valid_pixel_count=int(value.get("valid_pixel_count") or 0),
        field_pixel_count=int(value.get("field_pixel_count") or 0),
        valid_fraction=_fraction(value.get("valid_fraction"), "valid_fraction"),
        cloud_fraction=_optional_fraction(
            value.get("cloud_fraction"), "cloud_fraction",
        ),
        shadow_fraction=_optional_fraction(
            value.get("shadow_fraction"), "shadow_fraction",
        ),
        snow_fraction=_optional_fraction(
            value.get("snow_fraction"), "snow_fraction",
        ),
        nodata_fraction=_fraction(value.get("nodata_fraction"), "nodata_fraction"),
        reading_reliability=_fraction(
            value.get("reading_reliability"), "reading_reliability",
        ),
        support_hash=support_hash,
        support_definition=str(support.get("support_definition") or ""),
        grid_identity_hash=_hash("GRID-", grid_identity),
    )


def _feature_contributions(
    value: Mapping[str, Any], qa: CropObservationQAV2,
) -> Tuple[CropFeatureContributionV2, ...]:
    contributions = []
    feature_support_root = value.get("feature_support_contracts")
    feature_support_root = (
        dict(feature_support_root)
        if isinstance(feature_support_root, Mapping) else {}
    )
    for container_name in ("band_statistics", "index_statistics"):
        container = value.get(container_name)
        if not isinstance(container, Mapping):
            continue
        for feature_name, raw_stats in container.items():
            if not isinstance(raw_stats, Mapping):
                continue
            valid_count = int(raw_stats.get("valid_count") or 0)
            normalized_name = str(feature_name).lower()
            support_group_name = (
                "bands" if container_name == "band_statistics" else "indices"
            )
            support_group = feature_support_root.get(support_group_name)
            support_group = (
                dict(support_group) if isinstance(support_group, Mapping) else {}
            )
            feature_support = support_group.get(feature_name)
            feature_support = (
                dict(feature_support)
                if isinstance(feature_support, Mapping) else {}
            )
            feature_support_hash = str(
                feature_support.get("support_hash") or qa.support_hash
            )
            declared_count = feature_support.get("valid_pixel_count")
            if declared_count is not None and int(declared_count) != valid_count:
                raise ContractViolation("crop_feature_support_count_mismatch")
            if valid_count > qa.field_pixel_count:
                raise ContractViolation("crop_feature_support_exceeds_field_support")
            source_bands = (
                (str(feature_name).upper(),)
                if container_name == "band_statistics"
                else _FEATURE_SOURCE_BANDS.get(normalized_name, ())
            )
            for statistic, raw_value in raw_stats.items():
                if statistic == "valid_count" or isinstance(raw_value, bool):
                    continue
                if not isinstance(raw_value, (int, float)):
                    continue
                parsed = float(raw_value)
                if not math.isfinite(parsed):
                    raise ContractViolation("crop_feature_value_nonfinite")
                contributions.append(CropFeatureContributionV2(
                    feature_name=normalized_name,
                    statistic=str(statistic),
                    value=parsed,
                    valid_pixel_count=valid_count,
                    support_hash=feature_support_hash,
                    source_bands=tuple(source_bands),
                ))
    return tuple(sorted(
        contributions,
        key=lambda item: (
            item.feature_name, item.statistic, item.source_bands,
        ),
    ))


@dataclass(frozen=True)
class CanonicalCropObservationV2:
    plot_namespace: PlotNamespace
    observation_id: str
    crop_cycle_id: Optional[str]
    source_family: str
    provider: str
    mission: Optional[str]
    sensor: Optional[str]
    sensing_time: str
    processing_time: Optional[str]
    content_hash: str
    geometry_version: str
    physical_acquisition_key: Optional[str]
    independence_cluster_id: Optional[str]
    independence_eligible: bool
    qa: CropObservationQAV2
    feature_contributions: Tuple[CropFeatureContributionV2, ...]
    processing_lineage: Tuple[CropProcessingLineageV2, ...]
    direct_observation: bool
    independent_evidence: bool
    parent_observation_ids: Tuple[str, ...]
    _payload_json: str = field(repr=False)

    def __post_init__(self) -> None:
        _namespace(self.plot_namespace)
        if not self.observation_id.strip():
            raise ContractViolation("crop_observation_id_required")
        if not self.source_family.strip() or not self.provider.strip():
            raise ContractViolation("crop_observation_source_identity_required")
        if not self.sensing_time.strip() or not self.geometry_version.strip():
            raise ContractViolation("crop_observation_time_and_geometry_required")
        if not self.content_hash.strip():
            raise ContractViolation("crop_observation_content_hash_required")
        if not isinstance(self.qa, CropObservationQAV2):
            raise ContractViolation("crop_observation_requires_typed_qa")
        if not isinstance(self.feature_contributions, tuple):
            raise ContractViolation("crop_feature_contributions_must_be_tuple")
        if not isinstance(self.processing_lineage, tuple):
            raise ContractViolation("crop_processing_lineage_must_be_tuple")
        feature_keys = [
            (item.feature_name, item.statistic, item.source_bands)
            for item in self.feature_contributions
        ]
        if len(feature_keys) != len(set(feature_keys)):
            raise ContractViolation("duplicate_crop_feature_contribution")
        if self.independence_eligible:
            if not self.physical_acquisition_key or not self.independence_cluster_id:
                raise ContractViolation("independent_crop_observation_requires_physical_key")
            if self.physical_acquisition_key != self.independence_cluster_id:
                raise ContractViolation("crop_independence_cluster_must_equal_physical_key")
        try:
            payload = json.loads(self._payload_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ContractViolation("invalid_crop_observation_payload_json") from exc
        if _canonical_json(payload) != self._payload_json:
            raise ContractViolation("crop_observation_payload_not_canonical")
        namespace_payload = _namespace_dict(self.plot_namespace)
        if payload.get("plot_namespace") != namespace_payload:
            raise ContractViolation("crop_observation_namespace_payload_mismatch")
        if payload.get("namespace") != namespace_payload:
            raise ContractViolation("crop_observation_namespace_alias_mismatch")
        if payload.get("observation_id") != self.observation_id:
            raise ContractViolation("crop_observation_id_payload_mismatch")
        for name in (
            "source_family", "provider", "sensing_time", "content_hash",
            "geometry_version", "direct_observation", "independent_evidence",
        ):
            if payload.get(name) != getattr(self, name):
                raise ContractViolation(f"crop_observation_{name}_payload_mismatch")
        if payload.get("quality_assessment") != self.qa.to_dict():
            raise ContractViolation("crop_observation_qa_payload_mismatch")
        if payload.get("feature_contributions") != [
            item.to_dict() for item in self.feature_contributions
        ]:
            raise ContractViolation("crop_observation_features_payload_mismatch")
        if payload.get("processing_lineage") != [
            item.to_dict() for item in self.processing_lineage
        ]:
            raise ContractViolation("crop_observation_lineage_payload_mismatch")

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any], *, plot_namespace: Any = None,
    ) -> "CanonicalCropObservationV2":
        if not isinstance(value, Mapping):
            raise ContractViolation("crop_observation_must_be_mapping")
        supplied_hash = str(value.get("observation_hash") or "").strip()
        namespace_value = (
            plot_namespace or value.get("namespace") or value.get("plot_namespace") or {
            "tenant_id": value.get("tenant_id"),
            "farm_id": value.get("farm_id"),
            "plot_id": value.get("plot_id"),
            }
        )
        namespace = _namespace(namespace_value)
        payload = dict(value)
        payload.pop("observation_hash", None)
        payload["contract_version"] = CROP_OBSERVATION_CONTRACT_VERSION
        payload["record_type"] = "CanonicalCropObservationV2"
        payload["plot_namespace"] = _namespace_dict(namespace)
        payload["namespace"] = _namespace_dict(namespace)
        payload.update(_namespace_dict(namespace))
        observation_id = str(payload.get("observation_id") or "").strip()
        if not observation_id:
            raise ContractViolation("crop_observation_id_required")
        qa = _qa_from_mapping(payload)
        features = _feature_contributions(payload, qa)
        lineage_values = payload.get("processing_lineage") or []
        lineage = tuple(sorted({
            CropProcessingLineageV2.from_mapping(item)
            for item in lineage_values if isinstance(item, Mapping)
        }, key=lambda item: item.stable_key()))
        physical_key = str(payload.get("physical_acquisition_key") or "").strip() or None
        source_family = str(
            payload.get("source_family") or payload.get("source") or ""
        ).strip().lower()
        provider = str(payload.get("provider") or "unknown").strip().lower()
        sensing_time = _normalized_time(
            payload.get("sensing_time")
            or payload.get("sensing_timestamp")
            or payload.get("timestamp"),
            required=True,
        )
        processing_time = _normalized_time(
            payload.get("processing_time")
            or payload.get("processing_timestamp")
            or max(
                (item.processing_timestamp for item in lineage), default="",
            ),
        )
        content_hash = str(payload.get("content_hash") or "").strip()
        geometry_version = str(
            payload.get("geometry_version")
            or payload.get("plot_geometry_hash")
            or payload.get("geometry_hash")
            or ""
        ).strip()
        crop_cycle_id = str(payload.get("crop_cycle_id") or "").strip() or None
        mission = str(payload.get("mission") or "").strip() or None
        sensor = str(payload.get("sensor") or "").strip() or None
        direct_observation = payload.get("direct_observation") is True
        parent_observation_ids = tuple(sorted({
            str(item).strip()
            for item in payload.get("parent_observation_ids", [])
            if str(item).strip()
        }))
        independence_eligible = bool(
            physical_key
            and payload.get("physical_identity_complete") is not False
            and payload.get("independence_identity_available") is not False
        )
        cluster_id = physical_key if independence_eligible else None
        independent_evidence = bool(
            independence_eligible and qa.admitted and direct_observation
        )
        normalized_family = source_family.replace("-", "_")
        if normalized_family in {"sentinel1", "s1", "sar", "radar"}:
            # SAR band/index containers are measurements in the SAR summary,
            # not optical spectral evidence merely because they share the
            # generic feature-contribution transport.
            explicit_spectral = payload.get("spectral_summary")
            spectral_summary = (
                dict(explicit_spectral)
                if isinstance(explicit_spectral, Mapping) else {}
            )
        else:
            spectral_summary = {
                "band_statistics": payload.get("band_statistics") or {},
                "index_statistics": payload.get("index_statistics") or {},
                "reflectance_scale_by_band": payload.get("reflectance_scale_by_band") or {},
                "feature_support_contracts": payload.get("feature_support_contracts") or {},
            }
        sar_summary = payload.get("sar_summary") or {}
        spatial_summary = payload.get("spatial_summary") or payload.get("spatial_distribution") or {}
        texture_summary = payload.get("texture_summary") or (
            spatial_summary.get("ndvi_texture", {})
            if isinstance(spatial_summary, Mapping) else {}
        )
        environmental_context = payload.get("environmental_context") or {
            "day_of_year": payload.get("day_of_year"),
            "gdd_accumulated": payload.get("gdd_accumulated"),
            "gdd_basis": payload.get("gdd_basis"),
        }
        payload["physical_acquisition_key"] = physical_key
        payload["independence_cluster_id"] = cluster_id
        payload["independence_identity_available"] = independence_eligible
        payload["independent_observation_count"] = (
            1 if independent_evidence else 0
        )
        payload["crop_cycle_id"] = crop_cycle_id
        payload["source_family"] = source_family
        payload["provider"] = provider
        payload["mission"] = mission
        payload["sensor"] = sensor
        payload["sensing_time"] = sensing_time
        payload["processing_time"] = processing_time
        payload["content_hash"] = content_hash
        payload["geometry_version"] = geometry_version
        payload["quality_admitted"] = qa.admitted
        payload["quality_class"] = qa.quality_class
        payload["quality_rejection_reasons"] = list(qa.rejection_reasons)
        payload["valid_fraction"] = qa.valid_fraction
        payload["cloud_fraction"] = qa.cloud_fraction
        payload["shadow_fraction"] = qa.shadow_fraction
        payload["snow_fraction"] = qa.snow_fraction
        payload["admission_status"] = "admitted" if qa.admitted else "rejected"
        payload["admission_reasons"] = list(qa.rejection_reasons)
        payload["spectral_summary"] = spectral_summary
        payload["sar_summary"] = sar_summary
        payload["spatial_summary"] = spatial_summary
        payload["texture_summary"] = texture_summary
        payload["environmental_context"] = environmental_context
        payload["direct_observation"] = direct_observation
        payload["independent_evidence"] = independent_evidence
        payload["parent_observation_ids"] = list(parent_observation_ids)
        payload["quality_assessment"] = qa.to_dict()
        payload["feature_contributions"] = [item.to_dict() for item in features]
        payload["processing_lineage"] = [item.to_dict() for item in lineage]
        payload["processing_lineage_count"] = len(lineage)
        instance = cls(
            plot_namespace=namespace,
            observation_id=observation_id,
            crop_cycle_id=crop_cycle_id,
            source_family=source_family,
            provider=provider,
            mission=mission,
            sensor=sensor,
            sensing_time=str(sensing_time),
            processing_time=processing_time,
            content_hash=content_hash,
            geometry_version=geometry_version,
            physical_acquisition_key=physical_key,
            independence_cluster_id=cluster_id,
            independence_eligible=independence_eligible,
            qa=qa,
            feature_contributions=features,
            processing_lineage=lineage,
            direct_observation=direct_observation,
            independent_evidence=independent_evidence,
            parent_observation_ids=parent_observation_ids,
            _payload_json=_canonical_json(payload),
        )
        if supplied_hash and supplied_hash != instance.observation_hash:
            raise ContractViolation("crop_observation_hash_mismatch")
        return instance

    @property
    def observation_hash(self) -> str:
        return "CROPOBSV2-" + hashlib.sha256(
            self._payload_json.encode("utf-8")
        ).hexdigest()

    @property
    def namespace(self) -> PlotNamespace:
        """Canonical contract name; ``plot_namespace`` remains a compatibility alias."""
        return self.plot_namespace

    def _section(self, name: str) -> Dict[str, Any]:
        value = json.loads(self._payload_json).get(name)
        return dict(value) if isinstance(value, Mapping) else {}

    @property
    def quality_class(self) -> str:
        return self.qa.quality_class

    @property
    def admission_status(self) -> str:
        return "admitted" if self.qa.admitted else "rejected"

    @property
    def admission_reasons(self) -> Tuple[str, ...]:
        return self.qa.rejection_reasons

    @property
    def valid_fraction(self) -> float:
        return self.qa.valid_fraction

    @property
    def cloud_fraction(self) -> Optional[float]:
        return self.qa.cloud_fraction

    @property
    def shadow_fraction(self) -> Optional[float]:
        return self.qa.shadow_fraction

    @property
    def snow_fraction(self) -> Optional[float]:
        return self.qa.snow_fraction

    @property
    def spectral_summary(self) -> Dict[str, Any]:
        return self._section("spectral_summary")

    @property
    def sar_summary(self) -> Dict[str, Any]:
        return self._section("sar_summary")

    @property
    def spatial_summary(self) -> Dict[str, Any]:
        return self._section("spatial_summary")

    @property
    def texture_summary(self) -> Dict[str, Any]:
        return self._section("texture_summary")

    @property
    def environmental_context(self) -> Dict[str, Any]:
        return self._section("environmental_context")

    def to_dict(self) -> Dict[str, Any]:
        payload = json.loads(self._payload_json)
        payload["observation_hash"] = self.observation_hash
        return payload


@dataclass(frozen=True)
class CropEvidenceIndependenceClusterV2:
    cluster_id: str
    independence_eligible: bool
    selected_observation_hash: str
    observation_hashes: Tuple[str, ...]
    admitted: bool
    processing_lineage: Tuple[CropProcessingLineageV2, ...]
    feature_keys: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.cluster_id.strip() or not self.selected_observation_hash.strip():
            raise ContractViolation("crop_independence_cluster_identity_required")
        if not isinstance(self.observation_hashes, tuple) or not self.observation_hashes:
            raise ContractViolation("crop_independence_cluster_observations_required")
        if len(self.observation_hashes) != len(set(self.observation_hashes)):
            raise ContractViolation("duplicate_observation_in_crop_independence_cluster")
        if self.selected_observation_hash not in self.observation_hashes:
            raise ContractViolation("selected_crop_observation_not_in_cluster")
        if self.independence_eligible and self.cluster_id.startswith("unresolved:"):
            raise ContractViolation("unresolved_crop_cluster_cannot_be_independent")

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "cluster_id": self.cluster_id,
            "independence_eligible": self.independence_eligible,
            "selected_observation_hash": self.selected_observation_hash,
            "observation_hashes": list(self.observation_hashes),
            "admitted": self.admitted,
            "independent_evidence_count": (
                1 if self.independence_eligible and self.admitted else 0
            ),
            "processing_lineage": [item.to_dict() for item in self.processing_lineage],
            "feature_keys": list(self.feature_keys),
        }
        payload["cluster_hash"] = _hash("CROPCLUSTER-", payload)
        return payload


def _selection_score(observation: CanonicalCropObservationV2) -> Tuple[Any, ...]:
    processing_timestamp = max(
        (item.processing_timestamp for item in observation.processing_lineage),
        default="",
    )
    return (
        observation.independent_evidence,
        observation.direct_observation,
        observation.qa.admitted,
        observation.qa.valid_fraction,
        observation.qa.reading_reliability,
        observation.qa.valid_pixel_count,
        processing_timestamp,
        observation.observation_hash,
    )


_OPTICAL_SOURCE_FAMILIES = frozenset({
    "sentinel2", "s2", "optical", "landsat", "planet", "field_spectrometer",
})
_SAR_SOURCE_FAMILIES = frozenset({
    "sentinel1", "s1", "sar", "radar",
})
_FIELD_SOURCE_FAMILIES = frozenset({
    "field", "field_photo", "field_survey", "survey", "lab", "sensor",
})


def _normalized_source_family(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _nonempty_summary(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return any(item not in (None, "", {}, [], ()) for item in value.values())


def _observation_feature_families(
    observation: CanonicalCropObservationV2,
) -> Tuple[str, ...]:
    payload = observation.to_dict()
    source = _normalized_source_family(observation.source_family)
    families = set()
    spectral = payload.get("spectral_summary")
    if source in _OPTICAL_SOURCE_FAMILIES or _nonempty_summary(spectral):
        families.add("optical_spectral")
    if source in _SAR_SOURCE_FAMILIES or _nonempty_summary(payload.get("sar_summary")):
        families.add("sar_backscatter")
    if _nonempty_summary(payload.get("spatial_summary")):
        families.add("spatial_distribution")
    if _nonempty_summary(payload.get("texture_summary")):
        families.add("texture")
    if _nonempty_summary(payload.get("environmental_context")):
        families.add("environmental_context")
    if source in _FIELD_SOURCE_FAMILIES:
        families.add("field_observation")
    return tuple(sorted(families))


def _domain_compatibility(value: Any) -> str:
    if isinstance(value, bool):
        return "compatible" if value else "incompatible"
    normalized = str(value or "unverified").strip().lower().replace("-", "_")
    if normalized in {
        "compatible", "in_domain", "within_domain", "supported", "verified",
    }:
        return "compatible"
    if normalized in {
        "incompatible", "out_of_domain", "unsupported", "failed",
    }:
        return "incompatible"
    return "unverified"


def _numeric_or_none(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _season_phase(context: Mapping[str, Any]) -> Optional[str]:
    raw = str(
        context.get("season_phase") or context.get("season_segment") or ""
    ).strip().lower()
    if raw in {"early", "mid", "late"}:
        return raw
    progress = _numeric_or_none(
        context.get("season_progress_fraction", context.get("season_progress"))
    )
    if progress is None or not 0.0 <= progress <= 1.0:
        return None
    if progress < (1.0 / 3.0):
        return "early"
    if progress < (2.0 / 3.0):
        return "mid"
    return "late"


@dataclass(frozen=True)
class CropEvidenceLedgerV2:
    plot_namespace: PlotNamespace
    observations: Tuple[CanonicalCropObservationV2, ...]
    independence_clusters: Tuple[CropEvidenceIndependenceClusterV2, ...]

    def __post_init__(self) -> None:
        namespace = _namespace(self.plot_namespace)
        hashes = [item.observation_hash for item in self.observations]
        if len(hashes) != len(set(hashes)):
            raise ContractViolation("duplicate_crop_observation_hash_in_ledger")
        if any(item.plot_namespace != namespace for item in self.observations):
            raise ContractViolation("crop_evidence_ledger_namespace_mismatch")
        cluster_ids = [item.cluster_id for item in self.independence_clusters]
        if len(cluster_ids) != len(set(cluster_ids)):
            raise ContractViolation("duplicate_crop_independence_cluster")
        clustered_hashes = [
            observation_hash
            for cluster in self.independence_clusters
            for observation_hash in cluster.observation_hashes
        ]
        if len(clustered_hashes) != len(set(clustered_hashes)):
            raise ContractViolation("crop_observation_in_multiple_independence_clusters")
        if set(clustered_hashes) != set(hashes):
            raise ContractViolation("crop_evidence_clusters_do_not_cover_observations")

    @classmethod
    def from_observations(
        cls, plot_namespace: Any,
        observations: Iterable[CanonicalCropObservationV2 | Mapping[str, Any]],
    ) -> "CropEvidenceLedgerV2":
        namespace = _namespace(plot_namespace)
        indexed: Dict[str, CanonicalCropObservationV2] = {}
        for raw in observations or []:
            observation = (
                raw if isinstance(raw, CanonicalCropObservationV2)
                else CanonicalCropObservationV2.from_mapping(
                    raw, plot_namespace=namespace,
                )
            )
            if observation.plot_namespace != namespace:
                raise ContractViolation("crop_evidence_ledger_namespace_mismatch")
            indexed[observation.observation_hash] = observation
        normalized = tuple(indexed[key] for key in sorted(indexed))
        groups: Dict[str, list[CanonicalCropObservationV2]] = {}
        for observation in normalized:
            group_key = (
                observation.independence_cluster_id
                if observation.independence_eligible
                else f"unresolved:{observation.observation_hash}"
            )
            groups.setdefault(group_key, []).append(observation)
        clusters = []
        for group_key in sorted(groups):
            members = groups[group_key]
            selected = max(members, key=_selection_score)
            lineages = tuple(sorted({
                lineage for member in members
                for lineage in member.processing_lineage
            }, key=lambda item: item.stable_key()))
            feature_keys = tuple(sorted({
                f"{feature.feature_name}:{feature.statistic}"
                for member in members for feature in member.feature_contributions
            }))
            clusters.append(CropEvidenceIndependenceClusterV2(
                cluster_id=group_key,
                independence_eligible=all(
                    member.independence_eligible for member in members
                ),
                selected_observation_hash=selected.observation_hash,
                observation_hashes=tuple(sorted(
                    member.observation_hash for member in members
                )),
                admitted=bool(
                    selected.qa.admitted and selected.independent_evidence
                ),
                processing_lineage=lineages,
                feature_keys=feature_keys,
            ))
        return cls(namespace, normalized, tuple(clusters))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CropEvidenceLedgerV2":
        if not isinstance(value, Mapping):
            raise ContractViolation("crop_evidence_ledger_must_be_mapping")
        ledger = cls.from_observations(
            value.get("namespace") or value.get("plot_namespace"),
            value.get("observations") or [],
        )
        supplied_hash = str(value.get("ledger_hash") or "").strip()
        if supplied_hash and supplied_hash != ledger.ledger_hash:
            raise ContractViolation("crop_evidence_ledger_hash_mismatch")
        supplied_payload = dict(value)
        supplied_payload.pop("ledger_hash", None)
        actual_payload = ledger._payload()
        if _canonical_data(supplied_payload) != _canonical_data(actual_payload):
            raise ContractViolation("crop_evidence_ledger_derived_fields_mismatch")
        return ledger

    def selected_observations(self) -> Tuple[CanonicalCropObservationV2, ...]:
        indexed = {item.observation_hash: item for item in self.observations}
        return tuple(
            indexed[cluster.selected_observation_hash]
            for cluster in self.independence_clusters
        )

    @property
    def namespace(self) -> PlotNamespace:
        """Canonical contract name; ``plot_namespace`` remains a compatibility alias."""
        return self.plot_namespace

    def evidence_items(self) -> Tuple[Dict[str, Any], ...]:
        selected_by_cluster = {
            cluster.cluster_id: cluster.selected_observation_hash
            for cluster in self.independence_clusters
        }
        items = []
        for observation in self.observations:
            payload = observation.to_dict()
            selected_for_cluster = (
                observation.independence_cluster_id is not None
                and selected_by_cluster.get(observation.independence_cluster_id)
                == observation.observation_hash
            )
            feature_families = _observation_feature_families(observation)
            calibration = _domain_compatibility(
                payload.get("calibration_domain_compatibility")
            )
            geography = _domain_compatibility(
                payload.get("geographical_domain_compatibility")
                or payload.get("geographic_domain_compatibility")
            )
            model_eligible = bool(
                selected_for_cluster
                and observation.qa.admitted
                and observation.independence_eligible
                and observation.independent_evidence
                and feature_families
            )
            group_eligible = model_eligible
            species_eligible = bool(
                model_eligible
                and observation.qa.quality_class == "good"
                and calibration == "compatible"
                and geography == "compatible"
            )
            reasons = list(observation.qa.rejection_reasons)
            if not observation.independence_eligible:
                reasons.append("physical_independence_identity_unavailable")
            elif not selected_for_cluster:
                reasons.append("superseded_processing_lineage")
            if not observation.direct_observation:
                reasons.append("derived_observation_not_independent")
            if group_eligible and not species_eligible:
                if calibration != "compatible":
                    reasons.append(f"calibration_domain_{calibration}")
                if geography != "compatible":
                    reasons.append(f"geographical_domain_{geography}")
                if observation.qa.quality_class != "good":
                    reasons.append("quality_insufficient_for_species_level")
            context = observation.environmental_context
            progress = _numeric_or_none(
                context.get(
                    "season_progress_fraction", context.get("season_progress")
                )
            )
            time_coverage = {
                "sensing_time": observation.sensing_time,
                "crop_cycle_id": observation.crop_cycle_id,
                "day_of_year": _numeric_or_none(context.get("day_of_year")),
                "gdd_accumulated": _numeric_or_none(
                    context.get("gdd_accumulated")
                ),
                "season_progress_fraction": progress,
                "season_phase": _season_phase(context),
            }
            item = {
                "observation_id": observation.observation_id,
                "observation_hash": observation.observation_hash,
                "source_family": observation.source_family,
                "provider": observation.provider,
                "mission": observation.mission,
                "sensor": observation.sensor,
                "physical_acquisition_key": observation.physical_acquisition_key,
                "direct_or_derived": (
                    "direct" if observation.direct_observation else "derived"
                ),
                "independence_cluster_id": observation.independence_cluster_id,
                "selected_for_independence_cluster": selected_for_cluster,
                "independent_evidence": observation.independent_evidence,
                "feature_families": list(feature_families),
                "feature_contributions": [
                    feature.to_dict()
                    for feature in observation.feature_contributions
                ],
                "data_quality": observation.qa.to_dict(),
                "model_use_eligible": model_eligible,
                "species_level_eligible": species_eligible,
                "group_level_eligible": group_eligible,
                "calibration_domain_compatibility": calibration,
                "geographical_domain_compatibility": geography,
                "time_coverage": time_coverage,
                "rejection_or_demotion_reasons": sorted(set(reasons)),
                "content_hash": observation.content_hash,
                "geometry_version": observation.geometry_version,
                "crop_cycle_id": observation.crop_cycle_id,
                "parent_observation_ids": list(
                    observation.parent_observation_ids
                ),
                "processing_lineage": [
                    lineage.to_dict()
                    for lineage in observation.processing_lineage
                ],
            }
            item["evidence_item_hash"] = _hash("CROPEVIDENCE-", item)
            items.append(item)
        return tuple(items)

    @staticmethod
    def _coverage_payload(
        eligible_items: Sequence[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        timestamps = []
        day_of_year = []
        gdd = []
        season_progress = []
        phases = set()
        for item in eligible_items:
            coverage = item.get("time_coverage")
            coverage = dict(coverage) if isinstance(coverage, Mapping) else {}
            raw_time = coverage.get("sensing_time")
            if raw_time:
                try:
                    timestamps.append(datetime.fromisoformat(
                        str(raw_time).replace("Z", "+00:00")
                    ))
                except ValueError:
                    pass
            doy_value = _numeric_or_none(coverage.get("day_of_year"))
            if doy_value is not None:
                day_of_year.append(doy_value)
            gdd_value = _numeric_or_none(coverage.get("gdd_accumulated"))
            if gdd_value is not None:
                gdd.append(gdd_value)
            progress_value = _numeric_or_none(
                coverage.get("season_progress_fraction")
            )
            if progress_value is not None and 0.0 <= progress_value <= 1.0:
                season_progress.append(progress_value)
            phase = str(coverage.get("season_phase") or "").lower()
            if phase in {"early", "mid", "late"}:
                phases.add(phase)
        timestamps.sort()
        temporal_span_days = (
            (timestamps[-1] - timestamps[0]).total_seconds() / 86400.0
            if len(timestamps) >= 2 else 0.0 if timestamps else None
        )
        if phases:
            season_proportion = len(phases) / 3.0
        elif len(season_progress) >= 2:
            season_proportion = max(season_progress) - min(season_progress)
        else:
            season_proportion = None
        return {
            "temporal_span": {
                "start": timestamps[0].astimezone(timezone.utc).isoformat()
                if timestamps else None,
                "end": timestamps[-1].astimezone(timezone.utc).isoformat()
                if timestamps else None,
                "span_days": temporal_span_days,
                "observation_time_count": len(timestamps),
            },
            "biological_time_span": {
                "day_of_year_min": min(day_of_year) if day_of_year else None,
                "day_of_year_max": max(day_of_year) if day_of_year else None,
                "day_of_year_span": (
                    max(day_of_year) - min(day_of_year)
                    if day_of_year else None
                ),
                "gdd_min": min(gdd) if gdd else None,
                "gdd_max": max(gdd) if gdd else None,
                "gdd_span": max(gdd) - min(gdd) if gdd else None,
            },
            "crop_season_coverage": {
                "proportion_covered": season_proportion,
                "season_progress_min": (
                    min(season_progress) if season_progress else None
                ),
                "season_progress_max": (
                    max(season_progress) if season_progress else None
                ),
                "early": "early" in phases,
                "mid": "mid" in phases,
                "late": "late" in phases,
                "phase_count": len(phases),
                "coverage_available": bool(phases or season_progress),
            },
        }

    def _payload(self) -> Dict[str, Any]:
        selected = self.selected_observations()
        reason_counts: Dict[str, int] = {}
        for observation in self.observations:
            for reason in observation.qa.rejection_reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        feature_index: Dict[str, set[str]] = {}
        for cluster in self.independence_clusters:
            if not cluster.admitted or not cluster.independence_eligible:
                continue
            for feature_key in cluster.feature_keys:
                feature_index.setdefault(feature_key, set()).add(cluster.cluster_id)
        lineage = tuple(sorted({
            item for cluster in self.independence_clusters
            for item in cluster.processing_lineage
        }, key=lambda item: item.stable_key()))
        evidence_items = self.evidence_items()
        eligible_items = tuple(
            item for item in evidence_items
            if item["model_use_eligible"] is True
        )
        feature_families = tuple(sorted({
            str(family)
            for item in eligible_items
            for family in item.get("feature_families", [])
        }))
        source_families = [
            _normalized_source_family(item.get("source_family"))
            for item in eligible_items
        ]
        coverage = self._coverage_payload(eligible_items)
        namespace = _namespace_dict(self.plot_namespace)
        return {
            "contract_version": CROP_EVIDENCE_LEDGER_CONTRACT_VERSION,
            "namespace": namespace,
            "plot_namespace": namespace,
            "observation_count": len(self.observations),
            "selected_observation_count": len(selected),
            "independence_cluster_count": len(self.independence_clusters),
            "admitted_independent_cluster_count": sum(
                cluster.independence_eligible and cluster.admitted
                for cluster in self.independence_clusters
            ),
            "quality_summary": {
                "admitted_observation_count": sum(
                    observation.qa.admitted for observation in self.observations
                ),
                "rejected_observation_count": sum(
                    not observation.qa.admitted for observation in self.observations
                ),
                "rejection_reason_counts": dict(sorted(reason_counts.items())),
            },
            "evidence_counts": {
                "admitted_physical_observations": len(eligible_items),
                "admitted_optical_acquisitions": sum(
                    source in _OPTICAL_SOURCE_FAMILIES
                    for source in source_families
                ),
                "admitted_sar_acquisitions": sum(
                    source in _SAR_SOURCE_FAMILIES
                    for source in source_families
                ),
                "field_observations": sum(
                    source in _FIELD_SOURCE_FAMILIES
                    for source in source_families
                ),
                "independent_feature_family_count": len(feature_families),
                "independent_feature_families": list(feature_families),
            },
            "eligibility_policy": {
                "model_use": (
                    "selected_physical_cluster&admitted&direct_observation"
                    "&independence_identity&feature_family_present"
                ),
                "group_level": "model_use_eligible",
                "species_level": (
                    "group_level_eligible&quality_good"
                    "&calibration_domain_compatible"
                    "&geographical_domain_compatible"
                ),
                "reprocessed_products_add_independent_evidence": False,
            },
            **coverage,
            "feature_contribution_index": [
                {
                    "feature_key": key,
                    "independence_cluster_ids": sorted(cluster_ids),
                    "admitted_independent_cluster_count": len(cluster_ids),
                }
                for key, cluster_ids in sorted(feature_index.items())
            ],
            "processing_lineage": [item.to_dict() for item in lineage],
            "evidence_items": list(evidence_items),
            "observations": [item.to_dict() for item in self.observations],
            "independence_clusters": [
                item.to_dict() for item in self.independence_clusters
            ],
        }

    @property
    def ledger_hash(self) -> str:
        return _hash("CROPLEDGERV2-", self._payload())

    def to_dict(self) -> Dict[str, Any]:
        payload = self._payload()
        payload["ledger_hash"] = self.ledger_hash
        return payload


__all__ = [
    "CROP_OBSERVATION_CONTRACT_VERSION",
    "CROP_EVIDENCE_LEDGER_CONTRACT_VERSION",
    "CropFeatureContributionV2",
    "CropObservationQAV2",
    "CropProcessingLineageV2",
    "CanonicalCropObservationV2",
    "CropEvidenceIndependenceClusterV2",
    "CropEvidenceLedgerV2",
]

"""Ledger-bound input contracts for Layer-2 crop evidence experts.

The contract closes the provenance gap between a ``CropEvidenceLedgerV2`` and
an executable model tensor.  It intentionally says nothing about whether a
model is production eligible; that remains the responsibility of the model
release receipt and the expert publication gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.scientific_contracts.crop_evidence import (
    CropEvidenceLedgerV2,
)


CROP_FEATURE_SCHEMA_RECEIPT_VERSION = "crop-feature-schema-receipt-v1"
CROP_FEATURE_TRANSFORM_MANIFEST_VERSION = "crop-feature-transform-manifest-v1"
CROP_MODEL_INPUT_RECEIPT_VERSION = "crop-model-input-receipt-v1"
_LEDGER_HASH = re.compile(r"^CROPLEDGERV2-[0-9a-f]{64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Crop model input cannot contain non-finite values")
        return 0.0 if value == 0.0 else value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        rows = [_canonical(item) for item in value]
        return sorted(rows, key=lambda item: _canonical_json(item))
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    if hasattr(value, "item") and callable(value.item):
        return _canonical(value.item())
    raise ValueError(f"Unsupported crop-model-input type: {type(value).__name__}")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


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
        raise ValueError("Crop model input requires a complete PlotNamespace")
    if not candidate.is_valid():
        raise ValueError("Crop model input requires a complete PlotNamespace")
    return PlotNamespace(*candidate.to_tuple())


def _namespace_dict(value: PlotNamespace) -> Dict[str, str]:
    return {
        "tenant_id": value.tenant_id,
        "farm_id": value.farm_id,
        "plot_id": value.plot_id,
    }


def _text_tuple(values: Iterable[Any]) -> Tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


@dataclass(frozen=True)
class CropFeatureSemanticV1:
    """One scientifically defined feature, not merely a column name."""

    name: str
    scientific_definition: str
    unit: str
    source_bands: Tuple[str, ...]
    statistic: str
    support_definition: str
    temporal_coordinate: str
    normalization: str
    missing_value_semantics: str

    def __post_init__(self) -> None:
        for name in (
            "name", "scientific_definition", "unit", "statistic",
            "support_definition", "temporal_coordinate", "normalization",
            "missing_value_semantics",
        ):
            value = str(getattr(self, name) or "").strip()
            if not value:
                raise ValueError(f"Crop feature semantic {name} is required")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "source_bands", _text_tuple(self.source_bands))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "scientific_definition": self.scientific_definition,
            "unit": self.unit,
            "source_bands": list(self.source_bands),
            "statistic": self.statistic,
            "support_definition": self.support_definition,
            "temporal_coordinate": self.temporal_coordinate,
            "normalization": self.normalization,
            "missing_value_semantics": self.missing_value_semantics,
        }


@dataclass(frozen=True)
class CropFeatureSchemaReceiptV1:
    schema_version: str
    features: Tuple[CropFeatureSemanticV1, ...]
    transform_version: str
    contract_version: str = CROP_FEATURE_SCHEMA_RECEIPT_VERSION
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not str(self.schema_version or "").strip() or not str(
            self.transform_version or ""
        ).strip():
            raise ValueError("Crop feature schema and transform versions are required")
        names = [item.name for item in self.features]
        if not names or len(names) != len(set(names)):
            raise ValueError("Crop feature schema requires unique features")
        expected = _sha256(self._payload_without_hash())
        if self.content_hash and self.content_hash != expected:
            raise ValueError("Crop feature schema receipt hash mismatch")
        object.__setattr__(self, "content_hash", expected)

    def _payload_without_hash(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "schema_version": self.schema_version,
            "transform_version": self.transform_version,
            "features": [item.to_dict() for item in self.features],
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = self._payload_without_hash()
        payload["content_hash"] = self.content_hash
        return payload


@dataclass(frozen=True)
class CropFeatureTransformRecipe:
    """Executable scientific recipe bound to one feature column."""

    feature_name: str
    algorithm_id: str
    formula_id: str
    parameters: Tuple[Tuple[str, Any], ...]
    window_definition: str
    thresholds: Tuple[Tuple[str, Any], ...]
    input_bands: Tuple[str, ...]
    mask_semantics: str
    temporal_coordinate: str
    normalization: str
    module_id: str
    module_digest: str

    def __post_init__(self) -> None:
        for name in (
            "feature_name", "algorithm_id", "formula_id", "window_definition",
            "mask_semantics", "temporal_coordinate", "normalization", "module_id",
        ):
            value = str(getattr(self, name) or "").strip()
            if not value:
                raise ValueError(f"Crop feature transform recipe {name} is required")
            object.__setattr__(self, name, value)
        if not _SHA256.fullmatch(str(self.module_digest or "")):
            raise ValueError("Crop feature transform module digest must be SHA-256")
        object.__setattr__(self, "input_bands", _text_tuple(self.input_bands))
        for field_name in ("parameters", "thresholds"):
            rows = tuple(sorted(
                (str(key).strip(), _canonical(value))
                for key, value in getattr(self, field_name)
            ))
            if any(not key for key, _ in rows) or len({key for key, _ in rows}) != len(rows):
                raise ValueError(f"Crop feature transform {field_name} keys must be unique")
            object.__setattr__(self, field_name, rows)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "algorithm_id": self.algorithm_id,
            "formula_id": self.formula_id,
            "parameters": dict(self.parameters),
            "window_definition": self.window_definition,
            "thresholds": dict(self.thresholds),
            "input_bands": list(self.input_bands),
            "mask_semantics": self.mask_semantics,
            "temporal_coordinate": self.temporal_coordinate,
            "normalization": self.normalization,
            "module_id": self.module_id,
            "module_digest": self.module_digest,
        }


@dataclass(frozen=True)
class CropFeatureTransformManifest:
    """Hash-stable identity of the complete ledger-to-feature computation."""

    transform_version: str
    schema_hash: str
    source_policy: str
    mask_policy: str
    time_policy: str
    normalization_policy: str
    smoothing_policy: str
    interpolation_policy: str
    red_edge_policy: str
    sos_threshold: float
    sar_change_point_threshold_db: float
    sar_rolling_window_days: int
    feature_recipes: Tuple[CropFeatureTransformRecipe, ...]
    module_digests: Tuple[Tuple[str, str], ...]
    contract_version: str = CROP_FEATURE_TRANSFORM_MANIFEST_VERSION
    content_hash: str = ""

    def __post_init__(self) -> None:
        for name in (
            "transform_version", "source_policy", "mask_policy", "time_policy",
            "normalization_policy", "smoothing_policy", "interpolation_policy",
            "red_edge_policy",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"Crop feature transform manifest {name} is required")
        if not _SHA256.fullmatch(str(self.schema_hash or "")):
            raise ValueError("Crop feature transform schema hash must be SHA-256")
        if not math.isfinite(float(self.sos_threshold)) or not 0.0 < float(
            self.sos_threshold
        ) < 1.0:
            raise ValueError("SOS threshold must be an amplitude fraction")
        if not math.isfinite(float(self.sar_change_point_threshold_db)):
            raise ValueError("SAR change-point threshold must be finite")
        if int(self.sar_rolling_window_days) <= 0:
            raise ValueError("SAR rolling window must be positive")
        names = [recipe.feature_name for recipe in self.feature_recipes]
        if not names or len(names) != len(set(names)):
            raise ValueError("Transform manifest requires one recipe per feature")
        digests = tuple(sorted(
            (str(module_id).strip(), str(digest).strip())
            for module_id, digest in self.module_digests
        ))
        if (
            any(not module_id or not _SHA256.fullmatch(digest) for module_id, digest in digests)
            or len({module_id for module_id, _ in digests}) != len(digests)
        ):
            raise ValueError("Transform manifest module digests are invalid")
        digest_map = dict(digests)
        if any(
            digest_map.get(recipe.module_id) != recipe.module_digest
            for recipe in self.feature_recipes
        ):
            raise ValueError("Feature recipe is not bound to its module digest")
        object.__setattr__(self, "module_digests", digests)
        expected = _sha256(self._payload_without_hash())
        if self.content_hash and self.content_hash != expected:
            raise ValueError("Crop feature transform manifest hash mismatch")
        object.__setattr__(self, "content_hash", expected)

    def _payload_without_hash(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "transform_version": self.transform_version,
            "schema_hash": self.schema_hash,
            "source_policy": self.source_policy,
            "mask_policy": self.mask_policy,
            "time_policy": self.time_policy,
            "normalization_policy": self.normalization_policy,
            "smoothing_policy": self.smoothing_policy,
            "interpolation_policy": self.interpolation_policy,
            "red_edge_policy": self.red_edge_policy,
            "sos_threshold": float(self.sos_threshold),
            "sar_change_point_threshold_db": float(
                self.sar_change_point_threshold_db
            ),
            "sar_rolling_window_days": int(self.sar_rolling_window_days),
            "feature_recipes": [
                recipe.to_dict() for recipe in self.feature_recipes
            ],
            "module_digests": dict(self.module_digests),
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = self._payload_without_hash()
        payload["content_hash"] = self.content_hash
        return payload


@dataclass(frozen=True)
class CropModelObservationTokenV1:
    observation_id: str
    observation_hash: str
    physical_acquisition_key: str
    source_family: str
    sensing_time: str
    feature_values: Tuple[Tuple[str, str, float], ...]
    quality_admitted: bool
    quality_class: str
    support_hash: str
    day_of_year: Optional[float] = None
    gdd_coordinates: Tuple[Tuple[str, float], ...] = ()
    primary_gdd_basis: Optional[str] = None
    orbit_direction: Optional[str] = None
    relative_orbit: Optional[str] = None
    incidence_angle: Optional[float] = None
    polarizations: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "observation_id", "observation_hash", "physical_acquisition_key",
            "source_family", "sensing_time", "quality_class", "support_hash",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"Crop observation token {name} is required")
        if not self.quality_admitted:
            raise ValueError("Rejected observations cannot enter a crop model token")
        feature_keys = [(name, statistic) for name, statistic, _ in self.feature_values]
        if len(feature_keys) != len(set(feature_keys)):
            raise ValueError("Duplicate crop model token feature")
        for _, _, value in self.feature_values:
            if not math.isfinite(float(value)):
                raise ValueError("Crop model token contains non-finite feature")
        object.__setattr__(self, "polarizations", _text_tuple(self.polarizations))
        coordinates = tuple(sorted(
            (str(name).strip(), float(value))
            for name, value in self.gdd_coordinates
        ))
        if len({name for name, _ in coordinates}) != len(coordinates):
            raise ValueError("Crop observation token GDD bases must be unique")
        if any(not name or not math.isfinite(value) for name, value in coordinates):
            raise ValueError("Crop observation token contains invalid GDD coordinate")
        primary = str(self.primary_gdd_basis or "").strip() or None
        if coordinates and primary not in {name for name, _ in coordinates}:
            raise ValueError(
                "Crop observation token requires an explicit primary GDD basis"
            )
        if not coordinates and primary is not None:
            raise ValueError("Primary GDD basis requires a GDD coordinate")
        object.__setattr__(self, "gdd_coordinates", coordinates)
        object.__setattr__(self, "primary_gdd_basis", primary)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "observation_hash": self.observation_hash,
            "physical_acquisition_key": self.physical_acquisition_key,
            "source_family": self.source_family,
            "sensing_time": self.sensing_time,
            "feature_values": [
                {"name": name, "statistic": statistic, "value": value}
                for name, statistic, value in self.feature_values
            ],
            "quality_admitted": self.quality_admitted,
            "quality_class": self.quality_class,
            "support_hash": self.support_hash,
            "day_of_year": self.day_of_year,
            "gdd_coordinates": dict(self.gdd_coordinates),
            "primary_gdd_basis": self.primary_gdd_basis,
            "s1_geometry": {
                "orbit_direction": self.orbit_direction,
                "relative_orbit": self.relative_orbit,
                "incidence_angle": self.incidence_angle,
                "polarizations": list(self.polarizations),
            },
        }


@dataclass(frozen=True)
class CropModelInputReceiptV1:
    plot_namespace: PlotNamespace
    crop_cycle_hypothesis_id: str
    crop_evidence_ledger_hash: str
    observation_tokens: Tuple[CropModelObservationTokenV1, ...]
    feature_schema_hash: str
    feature_transform_hash: str
    normalization_artifact_hash: str
    feature_order: Tuple[str, ...]
    input_values: Tuple[Optional[float], ...]
    missingness_mask: Tuple[bool, ...]
    sensor_availability_mask: Tuple[Tuple[str, bool], ...]
    quality_mask: Tuple[bool, ...]
    feature_completeness: float
    physical_evidence_sufficiency: str
    phase_coverage: Tuple[str, ...]
    domain_compatibility: str
    calibration_validity: str
    model_execution_eligible: bool
    publication_eligible: bool
    publication_blockers: Tuple[str, ...]
    contract_version: str = CROP_MODEL_INPUT_RECEIPT_VERSION
    input_tensor_hash: str = ""
    content_hash: str = ""

    def __post_init__(self) -> None:
        namespace = _namespace(self.plot_namespace)
        object.__setattr__(self, "plot_namespace", namespace)
        if not str(self.crop_cycle_hypothesis_id or "").strip():
            raise ValueError("Crop cycle hypothesis identity is required")
        if not _LEDGER_HASH.fullmatch(str(self.crop_evidence_ledger_hash or "")):
            raise ValueError("Crop model input requires a verified crop ledger hash")
        for name in (
            "feature_schema_hash", "feature_transform_hash",
            "normalization_artifact_hash",
        ):
            if not _SHA256.fullmatch(str(getattr(self, name) or "")):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        count = len(self.feature_order)
        if not count or len(set(self.feature_order)) != count:
            raise ValueError("Crop model input requires a unique feature order")
        if len(self.input_values) != count or len(self.missingness_mask) != count:
            raise ValueError("Crop model input tensor and missingness mask are misaligned")
        if len(self.quality_mask) != len(self.observation_tokens):
            raise ValueError("Crop model quality mask is not observation aligned")
        for index, value in enumerate(self.input_values):
            if value is not None and not math.isfinite(float(value)):
                raise ValueError("Crop model tensor contains non-finite values")
            if self.missingness_mask[index] != (value is None):
                raise ValueError("Crop model missingness mask does not match tensor")
        completeness = float(self.feature_completeness)
        if not 0.0 <= completeness <= 1.0:
            raise ValueError("Crop model feature completeness must be in [0, 1]")
        object.__setattr__(self, "feature_completeness", completeness)
        object.__setattr__(self, "phase_coverage", _text_tuple(self.phase_coverage))
        blockers = _text_tuple(self.publication_blockers)
        object.__setattr__(self, "publication_blockers", blockers)
        if self.publication_eligible and blockers:
            raise ValueError("Publishable crop model input cannot have blockers")
        if not self.publication_eligible and not blockers:
            raise ValueError("Non-publishable crop model input requires blockers")
        tensor_payload = {
            "feature_order": list(self.feature_order),
            "input_values": list(self.input_values),
            "missingness_mask": list(self.missingness_mask),
        }
        expected_tensor_hash = _sha256(tensor_payload)
        if self.input_tensor_hash and self.input_tensor_hash != expected_tensor_hash:
            raise ValueError("Crop model input tensor hash mismatch")
        object.__setattr__(self, "input_tensor_hash", expected_tensor_hash)
        expected = _sha256(self._payload_without_hash())
        if self.content_hash and self.content_hash != expected:
            raise ValueError("Crop model input receipt hash mismatch")
        object.__setattr__(self, "content_hash", expected)

    @property
    def receipt_id(self) -> str:
        return "CROP-MODEL-INPUT-" + self.content_hash[:24]

    @property
    def observation_ids(self) -> Tuple[str, ...]:
        return tuple(token.observation_id for token in self.observation_tokens)

    @property
    def physical_acquisition_keys(self) -> Tuple[str, ...]:
        return tuple(token.physical_acquisition_key for token in self.observation_tokens)

    def _payload_without_hash(self) -> Dict[str, Any]:
        tokens = [token.to_dict() for token in self.observation_tokens]
        by_family = {
            "optical_observation_ids": [],
            "sar_observation_ids": [],
            "field_observation_ids": [],
        }
        for token in self.observation_tokens:
            source = token.source_family.lower().replace("-", "_")
            if source in {"sentinel2", "s2", "optical", "landsat", "planet"}:
                by_family["optical_observation_ids"].append(token.observation_id)
            elif source in {"sentinel1", "s1", "sar", "radar"}:
                by_family["sar_observation_ids"].append(token.observation_id)
            else:
                by_family["field_observation_ids"].append(token.observation_id)
        temporal = [
            {
                "observation_id": token.observation_id,
                "sensing_time": token.sensing_time,
                "day_of_year": token.day_of_year,
            }
            for token in self.observation_tokens
        ]
        biological = [
            {
                "observation_id": token.observation_id,
                "gdd_coordinates": dict(token.gdd_coordinates),
                "primary_gdd_basis": token.primary_gdd_basis,
            }
            for token in self.observation_tokens
        ]
        return {
            "contract_version": self.contract_version,
            "plot_namespace": _namespace_dict(self.plot_namespace),
            "crop_cycle_hypothesis_id": self.crop_cycle_hypothesis_id,
            "crop_evidence_ledger_hash": self.crop_evidence_ledger_hash,
            "observation_ids": list(self.observation_ids),
            "physical_acquisition_keys": list(self.physical_acquisition_keys),
            **{key: sorted(values) for key, values in by_family.items()},
            "observation_tokens": tokens,
            "feature_schema_hash": self.feature_schema_hash,
            "feature_transform_hash": self.feature_transform_hash,
            "normalization_artifact_hash": self.normalization_artifact_hash,
            "feature_order": list(self.feature_order),
            "input_values": list(self.input_values),
            "temporal_coordinates": temporal,
            "biological_time_coordinates": biological,
            "missingness_mask": list(self.missingness_mask),
            "sensor_availability_mask": dict(self.sensor_availability_mask),
            "quality_mask": list(self.quality_mask),
            "input_tensor_hash": self.input_tensor_hash,
            "feature_completeness": self.feature_completeness,
            "physical_evidence_sufficiency": self.physical_evidence_sufficiency,
            "phase_coverage": list(self.phase_coverage),
            "domain_compatibility": self.domain_compatibility,
            "calibration_validity": self.calibration_validity,
            "model_execution_eligible": self.model_execution_eligible,
            "publication_eligible": self.publication_eligible,
            "publication_blockers": list(self.publication_blockers),
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = self._payload_without_hash()
        payload.update({"receipt_id": self.receipt_id, "content_hash": self.content_hash})
        return payload


def normalize_verified_crop_evidence_ledger(
    ledger: CropEvidenceLedgerV2 | Mapping[str, Any] | Any,
) -> CropEvidenceLedgerV2:
    """Return the locally imported, hash-verified ledger contract.

    Some supported service launch modes expose the same contract through the
    legacy ``scientific_contracts`` package alias.  Class identity is not a
    scientific validity check, so cross-alias instances are serialized and
    parsed again by the canonical class.  ``from_dict`` verifies the supplied
    hash and every derived field; arbitrary duck-typed objects remain rejected.
    """

    if isinstance(ledger, CropEvidenceLedgerV2):
        return ledger
    payload: Any = ledger
    if not isinstance(payload, Mapping):
        serializer = getattr(payload, "to_dict", None)
        if not callable(serializer):
            raise ValueError("A verified CropEvidenceLedgerV2 is required")
        payload = serializer()
    if not isinstance(payload, Mapping):
        raise ValueError("A verified CropEvidenceLedgerV2 is required")
    return CropEvidenceLedgerV2.from_dict(payload)


def observation_tokens_from_ledger(
    ledger: CropEvidenceLedgerV2 | Mapping[str, Any],
) -> Tuple[CropModelObservationTokenV1, ...]:
    """Select only admitted physical ledger representatives for model input."""

    ledger = normalize_verified_crop_evidence_ledger(ledger)
    selected_hashes = {
        cluster.selected_observation_hash
        for cluster in ledger.independence_clusters
        if cluster.independence_eligible and cluster.admitted
    }
    tokens = []
    for observation in ledger.observations:
        if observation.observation_hash not in selected_hashes:
            continue
        payload = observation.to_dict()
        environmental = payload.get("environmental_context") or {}
        sar = payload.get("sar_summary") or {}
        geometry = (
            sar.get("physical_acquisition") or sar.get("geometry")
            if isinstance(sar, Mapping) else {}
        )
        geometry = geometry if isinstance(geometry, Mapping) else {}
        gdd_rows = []
        coordinate_payload = environmental.get("gdd_coordinates")
        if isinstance(coordinate_payload, Mapping):
            gdd_rows.extend(
                (str(key).strip(), float(value))
                for key, value in coordinate_payload.items()
                if str(key).strip() and isinstance(value, (int, float))
            )
        else:
            for key, value in environmental.items():
                normalized = str(key).lower()
                if normalized.startswith("gdd") and isinstance(value, (int, float)):
                    gdd_rows.append((normalized, float(value)))
        if not gdd_rows and isinstance(environmental.get("gdd_accumulated"), (int, float)):
            gdd_rows.append((
                str(environmental.get("gdd_basis") or "gdd_unspecified"),
                float(environmental["gdd_accumulated"]),
            ))
        primary_gdd_basis = str(
            environmental.get("primary_gdd_basis")
            or environmental.get("gdd_basis") or ""
        ).strip() or None
        coordinate_names = {name for name, _ in gdd_rows}
        if primary_gdd_basis not in coordinate_names:
            casefolded = {name.casefold(): name for name in coordinate_names}
            primary_gdd_basis = casefolded.get(
                str(primary_gdd_basis or "").casefold()
            )
        if primary_gdd_basis is None and len(gdd_rows) == 1:
            # Compatibility records carry one named thermal axis.  Selecting
            # that sole axis is explicit and never depends on lexical order.
            primary_gdd_basis = gdd_rows[0][0]
        feature_rows = tuple(sorted(
            (
                item.feature_name,
                item.statistic,
                float(item.value),
            )
            for item in observation.feature_contributions
        ))
        polarizations = geometry.get("polarizations") or sar.get("polarizations") or ()
        if isinstance(polarizations, str):
            polarizations = (polarizations,)
        if not polarizations and observation.source_family.lower().replace("-", "_") in {
            "sentinel1", "s1", "sar", "radar",
        }:
            polarizations = tuple(sorted({
                band
                for contribution in observation.feature_contributions
                for band in contribution.source_bands
                if band in {"VV", "VH"}
            }))
        tokens.append(CropModelObservationTokenV1(
            observation_id=observation.observation_id,
            observation_hash=observation.observation_hash,
            physical_acquisition_key=str(observation.physical_acquisition_key or ""),
            source_family=observation.source_family,
            sensing_time=observation.sensing_time,
            feature_values=feature_rows,
            quality_admitted=observation.qa.admitted,
            quality_class=observation.qa.quality_class,
            support_hash=observation.qa.support_hash,
            day_of_year=(
                float(environmental["day_of_year"])
                if isinstance(environmental.get("day_of_year"), (int, float))
                else None
            ),
            gdd_coordinates=tuple(gdd_rows),
            primary_gdd_basis=primary_gdd_basis,
            orbit_direction=(
                geometry.get("orbit_pass") or sar.get("orbit_pass")
                or geometry.get("orbit_direction") or sar.get("orbit_direction")
            ),
            relative_orbit=(
                geometry.get("relative_orbit") or sar.get("relative_orbit")
                or geometry.get("orbit_reference") or sar.get("orbit_reference")
            ),
            incidence_angle=(
                float(geometry.get("incidence_angle") or sar.get("incidence_angle"))
                if isinstance(
                    geometry.get("incidence_angle") or sar.get("incidence_angle"),
                    (int, float),
                ) else None
            ),
            polarizations=tuple(polarizations),
        ))
    return tuple(sorted(tokens, key=lambda token: (token.sensing_time, token.observation_hash)))


def build_crop_model_input_receipt(
    *,
    ledger: CropEvidenceLedgerV2 | Mapping[str, Any],
    crop_cycle_hypothesis_id: str,
    feature_schema: CropFeatureSchemaReceiptV1,
    feature_values: Mapping[str, Optional[float]],
    feature_transform_hash: str,
    normalization_artifact_hash: str,
    domain_compatibility: str = "unverified",
    calibration_validity: str = "unavailable",
    selected_observation_ids: Optional[Sequence[str]] = None,
) -> CropModelInputReceiptV1:
    ledger = normalize_verified_crop_evidence_ledger(ledger)
    tokens = observation_tokens_from_ledger(ledger)
    if selected_observation_ids is not None:
        selected = {str(value) for value in selected_observation_ids}
        tokens = tuple(
            token for token in tokens if token.observation_id in selected
        )
        if selected and {token.observation_id for token in tokens} != selected:
            raise ValueError("Crop-cycle selection contains observations outside the ledger")
    feature_order = tuple(item.name for item in feature_schema.features)
    values = tuple(
        None if feature_values.get(name) is None else float(feature_values[name])
        for name in feature_order
    )
    missing = tuple(value is None for value in values)
    completeness = sum(not flag for flag in missing) / len(missing)
    families = {token.source_family.lower().replace("-", "_") for token in tokens}
    sensor_mask = (
        ("field", any(item.startswith("field") for item in families)),
        ("optical", bool(families.intersection({"sentinel2", "s2", "optical", "landsat", "planet"}))),
        ("sar", bool(families.intersection({"sentinel1", "s1", "sar", "radar"}))),
    )
    # Readiness is scoped to the exact current-cycle tokens in this receipt.
    # The full ledger remains lineage only; an earlier cycle cannot donate
    # phases or temporal coverage to the selected hypothesis.
    token_ids = {token.observation_id for token in tokens}
    scoped_items = tuple(
        item for item in ledger.evidence_items()
        if item.get("model_use_eligible") is True
        and str(item.get("observation_id")) in token_ids
    )
    coverage = CropEvidenceLedgerV2._coverage_payload(scoped_items).get(
        "crop_season_coverage"
    ) or {}
    phases = tuple(
        phase for phase in ("early", "mid", "late") if coverage.get(phase) is True
    )
    physical_count = len(tokens)
    if physical_count <= 0:
        sufficiency = "unavailable"
    elif physical_count < 4:
        sufficiency = "insufficient"
    elif physical_count < 6:
        sufficiency = "sparse"
    else:
        sufficiency = "observed"
    blockers = []
    if physical_count < 6:
        blockers.append("physical_evidence_insufficient_for_species_publication")
    if len(phases) < 2:
        blockers.append("crop_cycle_phase_coverage_insufficient")
    if domain_compatibility != "compatible":
        blockers.append("model_domain_not_verified")
    if calibration_validity != "valid":
        blockers.append("probability_calibration_not_validated")
    if completeness < 0.4:
        blockers.append("feature_tensor_incomplete")
    execution_eligible = physical_count > 0 and completeness >= 0.4
    return CropModelInputReceiptV1(
        plot_namespace=ledger.plot_namespace,
        crop_cycle_hypothesis_id=crop_cycle_hypothesis_id,
        crop_evidence_ledger_hash=ledger.ledger_hash,
        observation_tokens=tokens,
        feature_schema_hash=feature_schema.content_hash,
        feature_transform_hash=feature_transform_hash,
        normalization_artifact_hash=normalization_artifact_hash,
        feature_order=feature_order,
        input_values=values,
        missingness_mask=missing,
        sensor_availability_mask=sensor_mask,
        quality_mask=tuple(token.quality_admitted for token in tokens),
        feature_completeness=completeness,
        physical_evidence_sufficiency=sufficiency,
        phase_coverage=phases,
        domain_compatibility=domain_compatibility,
        calibration_validity=calibration_validity,
        model_execution_eligible=execution_eligible,
        publication_eligible=not blockers,
        publication_blockers=tuple(blockers),
    )


__all__ = [
    "CROP_FEATURE_SCHEMA_RECEIPT_VERSION",
    "CROP_FEATURE_TRANSFORM_MANIFEST_VERSION",
    "CROP_MODEL_INPUT_RECEIPT_VERSION",
    "CropFeatureSemanticV1",
    "CropFeatureSchemaReceiptV1",
    "CropFeatureTransformRecipe",
    "CropFeatureTransformManifest",
    "CropModelObservationTokenV1",
    "CropModelInputReceiptV1",
    "normalize_verified_crop_evidence_ledger",
    "observation_tokens_from_ledger",
    "build_crop_model_input_receipt",
]

"""Content-addressed ASMAE cache and atomic artifact persistence.

A cache hit is a scientific lineage claim. JSON and raster data are therefore
accepted only as one complete, versioned, checksummed transaction.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, date
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)

# These imports are intentionally independent. Importing through
# ``services.agribrain...`` must not disable NumPy hashing merely because the
# short ``common`` package spelling is unavailable.
try:
    import numpy as np
except ImportError:  # pragma: no cover - ASMAE itself requires NumPy
    np = None  # type: ignore[assignment]

try:
    from scipy import sparse as sp
except ImportError:  # pragma: no cover - dense raster caching still works
    sp = None  # type: ignore[assignment]

try:
    from common.safe_npz import safe_np_load
except ImportError:
    try:
        from ..common.safe_npz import safe_np_load
    except ImportError:
        def safe_np_load(file: Any, fix_imports: bool = True, encoding: str = "ASCII") -> Any:
            if np is None:
                raise ImportError("NumPy is required for ASMAE raster artifacts")
            return np.load(file, allow_pickle=False, fix_imports=fix_imports, encoding=encoding)

from .config import (
    ASMAE_VERSION,
    ENSEMBLE_SIZE_CERTIFICATION,
    ENSEMBLE_SIZE_LARGE_PLOT,
    ENSEMBLE_SIZE_OFFLINE,
    ENSEMBLE_SIZE_SHADOW,
    ENSEMBLE_SIZE_STANDARD,
    LARGE_PLOT_MICROZONE_THRESHOLD,
    LOCALIZATION_HALF_WIDTH,
)
from .schema import ASMAEInput

ASMAE_PROOF_CONTRACT_VERSION = "v1_bc10_17"
ASMAE_FEATURE_FORMULA_VERSION = "v1_optical_stack_full"
ASMAE_SAR_UNITS_VERSION = "v1_db_linear_split"
ASMAE_WEATHER_FEATURE_VERSION = "v1_variable_completeness"

ASMAE_HASH_SCHEMA_VERSION = "v2_exact_dtype_complete_authority"
ASMAE_CACHE_SCHEMA_VERSION = "v10_atomic_manifest_authority"
ASMAE_CACHE_COMMIT_SCHEMA_VERSION = "v1_atomic_npz_json"
STATE_SUPPORT_POLICY_VERSION = "v2_receipt_bounded_20261025"
ENSEMBLE_POLICY_CONTRACT_VERSION = "asmae_ensemble_policy_v1"

HAS_NUMPY = np is not None
HAS_SCIPY = sp is not None
HAS_NUMPY_SCIPY = HAS_NUMPY and HAS_SCIPY  # compatibility export

# Define central paths relative to runtime directory or configured root
RUN_ROOT = os.environ.get("AGRIBRAIN_RUNTIME_DIR") or os.environ.get("AGRIBRAIN_ARTIFACTS_DIR")
if RUN_ROOT:
    ARTIFACTS_DIR = os.path.abspath(RUN_ROOT)
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")

CACHE_DIR = os.path.join(ARTIFACTS_DIR, "asmae_cache")
OPERATORS_DIR = os.path.join(ARTIFACTS_DIR, "asmae_operators")
RASTERS_DIR = os.path.join(ARTIFACTS_DIR, "asmae_rasters")

def ensure_cache_directories_exist() -> None:
    """Safe lazily-called directory initializer."""
    for d in (CACHE_DIR, OPERATORS_DIR, RASTERS_DIR):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass

_RASTER_FIELDS: Tuple[str, ...] = (
    "raster_maps", "uncertainty_maps", "confidence_maps",
    "retrovalidation_maps", "bma_maps",
)
_SCENE_AUTHORITY_FIELDS: Tuple[str, ...] = (
    "source_reality", "real_provider_product", "test_override",
    "production_usable", "diagnostic_only", "visualization_allowed",
    "experimental_visual_allowed", "composite_advisory_allowed",
    "scientific_surface_allowed", "prescription_driver_allowed",
    "current_1m_approval_allowed", "state_update_allowed", "authority",
    "admission_status", "admission_reason", "validation_status",
    "validation_report", "qa_status", "quality_status", "data_status",
    "provenance_ref", "provenance", "source_provenance", "provider",
    "product_id", "source_id", "valid_support_hash", "valid_fraction",
    "spatial_normalization", "transform_convention",
    "provider_product_id", "catalog_item_id", "provider_tile_id",
    "provider_orbit_id", "provider_orbit_pass", "product_binding",
    "binding_proof",
)
_THREAD_LOCKS: Dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()
_LOCK_WAIT_SECONDS = 30.0
_STALE_LOCK_SECONDS = 30.0 * 60.0


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _dtype_descriptor(dtype: Any) -> Any:
    return np.lib.format.dtype_to_descr(dtype) if np is not None else str(dtype)


def _canonical_type_name(value: Any) -> str:
    """Collapse the two supported Agribrain import roots to one identity."""
    module = type(value).__module__
    prefix = "services.agribrain."
    if module.startswith(prefix):
        module = module[len(prefix):]
    return f"{module}.{type(value).__qualname__}"


def stable_value_hash(value: Any) -> str:
    """Hash values with type tags and exact NumPy dtype/shape/content bytes.

    Arrays never use display strings and are never quantized to float32. Object
    arrays are recursively hashed because their raw bytes contain process-local
    pointers. The schema tag makes every caller reject hashes from old rules.
    """
    def visit(item: Any) -> Any:
        if np is not None and (isinstance(item, np.ndarray) or np.ma.isMaskedArray(item)):
            if np.ma.isMaskedArray(item):
                return {
                    "type": "numpy_masked_array",
                    "data": visit(np.asarray(item.data)),
                    "mask": visit(np.asarray(item.mask)),
                    "fill_value": visit(item.fill_value),
                }
            array = np.asarray(item)
            node: Dict[str, Any] = {
                "type": "numpy_ndarray",
                "shape": list(array.shape),
                "dtype": _dtype_descriptor(array.dtype),
            }
            if array.dtype.hasobject:
                node["elements"] = [visit(v) for v in array.ravel(order="C").tolist()]
            else:
                raw = np.ascontiguousarray(array).tobytes(order="C")
                node["bytes_sha256"] = hashlib.sha256(raw).hexdigest()
            return node
        if np is not None and isinstance(item, np.generic):
            scalar = np.asarray(item)
            return {
                "type": "numpy_scalar",
                "dtype": _dtype_descriptor(scalar.dtype),
                "bytes_sha256": hashlib.sha256(scalar.tobytes()).hexdigest(),
            }
        if item is None:
            return {"type": "none"}
        if isinstance(item, Enum):
            return {
                "type": "enum",
                "class": _canonical_type_name(item),
                "value": visit(item.value),
            }
        if isinstance(item, bool):
            return {"type": "bool", "value": item}
        if isinstance(item, int):
            return {"type": "int", "value": str(item)}
        if isinstance(item, float):
            if math.isnan(item):
                encoded = "nan"
            elif math.isinf(item):
                encoded = "+inf" if item > 0 else "-inf"
            else:
                encoded = item.hex()
            return {"type": "float64", "value": encoded}
        if isinstance(item, complex):
            return {"type": "complex", "real": visit(item.real), "imag": visit(item.imag)}
        if isinstance(item, Decimal):
            return {"type": "decimal", "value": str(item)}
        if isinstance(item, UUID):
            return {"type": "uuid", "value": str(item)}
        if isinstance(item, str):
            return {"type": "str", "value": item}
        if isinstance(item, (bytes, bytearray, memoryview)):
            raw = bytes(item)
            return {"type": "bytes", "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        if isinstance(item, datetime):
            return {"type": "datetime", "value": item.isoformat()}
        if isinstance(item, date):
            return {"type": "date", "value": item.isoformat()}
        if isinstance(item, Path):
            return {"type": "path", "value": str(item)}
        if is_dataclass(item) and not isinstance(item, type):
            return {
                "type": "dataclass",
                "class": _canonical_type_name(item),
                "fields": [[f.name, visit(getattr(item, f.name))] for f in fields(item)],
            }
        if isinstance(item, dict):
            entries = [(visit(k), visit(v)) for k, v in item.items()]
            entries.sort(key=lambda pair: _json_bytes(pair[0]))
            return {"type": "dict", "items": [[k, v] for k, v in entries]}
        if isinstance(item, list):
            return {"type": "list", "items": [visit(v) for v in item]}
        if isinstance(item, tuple):
            return {"type": "tuple", "items": [visit(v) for v in item]}
        if isinstance(item, (set, frozenset)):
            nodes = [visit(v) for v in item]
            nodes.sort(key=_json_bytes)
            return {"type": type(item).__name__, "items": nodes}
        if callable(getattr(item, "model_dump", None)):
            return {
                "type": "model",
                "class": _canonical_type_name(item),
                "attributes": visit(item.model_dump(mode="python")),
            }
        if callable(getattr(item, "to_dict", None)):
            return {
                "type": "serializable_object",
                "class": _canonical_type_name(item),
                "attributes": visit(item.to_dict()),
            }
        if hasattr(item, "__dict__"):
            public = {str(k): v for k, v in vars(item).items() if not str(k).startswith("_")}
            return {
                "type": "object",
                "class": _canonical_type_name(item),
                "attributes": visit(public),
            }
        raise TypeError(
            "ASMAE scientific cache identity cannot serialize "
            f"{_canonical_type_name(item)}"
        )

    envelope = {"hash_schema_version": ASMAE_HASH_SCHEMA_VERSION, "value": visit(value)}
    return hashlib.sha256(_json_bytes(envelope)).hexdigest()


def _scene_field(scene: Any, name: str, default: Any = None) -> Any:
    return scene.get(name, default) if isinstance(scene, dict) else getattr(scene, name, default)


def _scene_authority_contract(scene: Any) -> Dict[str, Any]:
    return {
        name: _scene_field(scene, name)
        for name in _SCENE_AUTHORITY_FIELDS
        if (isinstance(scene, dict) and name in scene) or hasattr(scene, name)
    }


def compute_source_hash(inp: ASMAEInput) -> str:
    """Hash the total scientific input contract, excluding only ``run_id``.

    Every scene is recursively hashed in addition to an explicit authority
    summary. This covers future admission, validation, provenance, and reality
    fields without relying on a selective allow-list.
    """
    from .artifact_identity import canonicalize_artifact_references

    scene_contracts: List[Dict[str, Any]] = []
    if isinstance(inp.layer0_source_packages, dict):
        packages = sorted(inp.layer0_source_packages.items(), key=lambda pair: str(pair[0]))
        for package_key, package_value in packages:
            scenes = package_value if isinstance(package_value, (list, tuple)) else [package_value]
            for index, scene in enumerate(scenes):
                scene_contracts.append({
                    "package_key": str(package_key),
                    "scene_index": index,
                    "scene_id": str(_scene_field(scene, "scene_id", "")),
                    "authority_contract_hash": stable_value_hash(_scene_authority_contract(scene)),
                    "complete_scene_hash": stable_value_hash(
                        canonicalize_artifact_references(scene)
                    ),
                })

    input_contract = {
        field.name: stable_value_hash(
            canonicalize_artifact_references(getattr(inp, field.name))
        )
        for field in fields(inp)
        if field.name != "run_id"
    }
    payload = {
        "hash_schema_version": ASMAE_HASH_SCHEMA_VERSION,
        "input_contract": input_contract,
        "layer0_source_packages_hash": stable_value_hash(
            canonicalize_artifact_references(inp.layer0_source_packages)
        ),
        "scene_contracts": scene_contracts,
        "raster_composites_hash": stable_value_hash(
            canonicalize_artifact_references(inp.raster_composites)
        ),
    }
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def get_asmae_cache_key(inp: ASMAEInput) -> str:
    """Generate composite cache key for ASMAE execution."""
    source_hash = compute_source_hash(inp)
    payload = {
        "plot_id": inp.plot_id,
        "geometry_hash": inp.geometry_hash,
        "model_version": ASMAE_VERSION,
        "cache_schema_version": ASMAE_CACHE_SCHEMA_VERSION,
        "hash_schema_version": ASMAE_HASH_SCHEMA_VERSION,
        "state_support_policy_version": STATE_SUPPORT_POLICY_VERSION,
        "ensemble_policy_contract_version": ENSEMBLE_POLICY_CONTRACT_VERSION,
        "ensemble_policy": {
            "shadow": ENSEMBLE_SIZE_SHADOW,
            "standard": ENSEMBLE_SIZE_STANDARD,
            "certification": ENSEMBLE_SIZE_CERTIFICATION,
            "large_plot": ENSEMBLE_SIZE_LARGE_PLOT,
            "offline": ENSEMBLE_SIZE_OFFLINE,
            "large_plot_microzone_threshold": LARGE_PLOT_MICROZONE_THRESHOLD,
            "localization_half_width": LOCALIZATION_HALF_WIDTH,
        },
        "source_hash": source_hash,
        "mode": inp.mode,
        "source_policy": inp.source_policy or "satellite",
        "is_pseudo": inp.is_pseudo,
        "archive_metrics": stable_value_hash(inp.archive_metrics),
        "archive_baselines": stable_value_hash(inp.archive_baselines),
        "archive_bma": stable_value_hash(inp.archive_bma),
        "retrovalidation_residuals": stable_value_hash(inp.retrovalidation_residuals),
        "phenology_envelopes": stable_value_hash(inp.phenology_envelopes),
        "historical_scene_refs": stable_value_hash(inp.historical_scene_refs),
        "plot_timeseries_hash": stable_value_hash(inp.plot_timeseries),
        "archive_posterior_hash": stable_value_hash(inp.archive_posterior),
        "soil_context_hash": stable_value_hash(inp.soil_context),
        "coarse_prior_hash": stable_value_hash(inp.coarse_layer_outputs),
        "crop_context_hash": stable_value_hash(inp.crop_context),
        "crop_posterior_hash": stable_value_hash(inp.crop_posterior),
        "phenology_posterior_hash": stable_value_hash(inp.phenology_posterior),
        "phenology_posterior_lineage": inp.phenology_posterior_hash,
        "phenology_worldline_event_id": inp.phenology_worldline_event_id,
        "crop_posterior_lineage": inp.crop_posterior_lineage,
        "crop_evidence_ledger_hash": inp.crop_evidence_ledger_hash,
        "crop_influence_manifest_hash": inp.crop_influence_manifest_hash,
        "permission_contract_version": inp.permission_contract_version,
        "authority_phase": inp.authority_phase,
        "rollout_state": inp.rollout_state,
        "execution_permissions_hash": stable_value_hash(inp.execution_permissions),
        "evidence_capability_contract_version": inp.evidence_capability_contract_version,
        "capability_plan_hash": inp.capability_plan_hash,
        # Weather / proof / formula / SAR versions (BC.10.17 P0.8)
        "weather_archive_hash": getattr(inp, "weather_archive_hash", None),
        "weather_archive_status": getattr(inp, "weather_archive_status", "unavailable"),
        "weather_source_reality": getattr(inp, "weather_source_reality", "missing"),
        "weather_daily_series_hash": stable_value_hash(getattr(inp, "weather_daily_series", {})),
        "proof_contract_version": ASMAE_PROOF_CONTRACT_VERSION,
        "feature_formula_version": ASMAE_FEATURE_FORMULA_VERSION,
        "sar_units_version": ASMAE_SAR_UNITS_VERSION,
        "weather_feature_version": ASMAE_WEATHER_FEATURE_VERSION,
        "formula_versions": {
            "canopy_formula_version": "v1.1",
            "water_arr_formula_version": "v1.0",
            "salinity_arr_formula_version": "v1.0",
            "risk_arr_formula_version": "v1.0"
        },
        "sar_parameters": {
            "min_s1_scenes": 2,
            "vh_calibration_db": -18.0,
            "vv_calibration_db": -10.0
        }
    }
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def _file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _thread_lock_for(path: str) -> threading.Lock:
    canonical = os.path.abspath(path)
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(canonical, threading.Lock())


@contextmanager
def _cache_key_lock(cache_path: str) -> Iterator[None]:
    """Serialize cache readers/writers across threads and processes."""
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with _thread_lock_for(cache_path):
        lock_path = f"{cache_path}.lock"
        token = f"{os.getpid()}:{threading.get_ident()}:{uuid.uuid4().hex}"
        deadline = time.monotonic() + _LOCK_WAIT_SECONDS
        acquired = False
        while not acquired:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(token)
                    handle.flush()
                    os.fsync(handle.fileno())
                acquired = True
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(lock_path) > _STALE_LOCK_SECONDS:
                        os.unlink(lock_path)
                        logger.warning("Removed stale ASMAE cache lock %s", lock_path)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for ASMAE cache lock {lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                with open(lock_path, "r", encoding="utf-8") as handle:
                    owner = handle.read()
                if owner == token:
                    os.unlink(lock_path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                logger.warning("Failed to release ASMAE cache lock %s: %s", lock_path, exc)


def _atomic_json_write(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    try:
        with open(temp_path, "x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def _artifact_path(rel_ref: str) -> str:
    if not rel_ref or os.path.isabs(rel_ref):
        raise ValueError("artifact reference must be a non-empty relative path")
    root = os.path.realpath(ARTIFACTS_DIR)
    resolved = os.path.realpath(os.path.join(root, rel_ref))
    if os.path.commonpath([root, resolved]) != root:
        raise ValueError("artifact reference escapes the ASMAE artifact root")
    return resolved


def save_ht_matrix_artifact(operator_id: str, h_matrix: Any) -> str:
    """Save H_t sparse matrix to disk as .npz.

    Returns the relative artifact reference.
    """
    if not HAS_NUMPY_SCIPY or h_matrix is None:
        return ""

    ensure_cache_directories_exist()
    rel_ref = f"asmae_operators/ht_{operator_id}.npz"
    full_path = os.path.join(ARTIFACTS_DIR, rel_ref)

    try:
        # Check if already exists to avoid redundant writes
        if os.path.exists(full_path):
            return rel_ref

        # scipy sparse matrices can be saved directly
        if hasattr(h_matrix, "tocsr"):
            sp.save_npz(full_path, h_matrix.tocsr())
        else:
            # Fallback if numpy array
            np.savez_compressed(full_path, data=h_matrix)
        logger.info("Saved H_t matrix to %s", full_path)
    except Exception as e:
        logger.error("Failed to save H_t matrix: %s", e)
        return ""

    return rel_ref


def save_rasters_artifact(cache_key: str, raster_dict: Dict[str, Any]) -> str:
    """Atomically save every 2D numeric raster into one pickle-free NPZ with generation addressing."""
    if np is None or not raster_dict:
        return ""

    generation_id = uuid.uuid4().hex
    rel_ref = f"asmae_rasters/raster_{cache_key}_{generation_id}.npz"
    full_path = _artifact_path(rel_ref)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    temp_path = f"{full_path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        arrays_to_save: Dict[str, Any] = {}
        for key, grid in sorted(raster_dict.items(), key=lambda pair: str(pair[0])):
            if np.ma.is_masked(grid) or isinstance(grid, np.ma.MaskedArray):
                data_part = np.asarray(grid.data)
                mask_part = np.asarray(np.ma.getmaskarray(grid), dtype=bool)
                if data_part.dtype.hasobject:
                    data_part = np.asarray(data_part, dtype=np.float64)
                if data_part.ndim != 2:
                    raise ValueError(f"raster {key} is not 2D: {data_part.shape}")
                if mask_part.shape != data_part.shape:
                    mask_part = np.broadcast_to(mask_part, data_part.shape).copy()
                arrays_to_save[str(key)] = np.ascontiguousarray(data_part)
                arrays_to_save[f"__mask__{key}"] = np.ascontiguousarray(mask_part)
            else:
                array = np.asarray(grid)
                if array.dtype.hasobject:
                    array = np.asarray(grid, dtype=np.float64)
                if array.ndim != 2:
                    raise ValueError(f"raster {key} is not 2D: {array.shape}")
                if not (
                    np.issubdtype(array.dtype, np.bool_)
                    or np.issubdtype(array.dtype, np.integer)
                    or np.issubdtype(array.dtype, np.floating)
                ):
                    raise TypeError(f"unsupported raster dtype {array.dtype}")
                arrays_to_save[str(key)] = np.ascontiguousarray(array)
        if not arrays_to_save:
            return ""
        with open(temp_path, "xb") as handle:
            np.savez_compressed(handle, **arrays_to_save)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, full_path)
        logger.info("Saved generation-addressed rasters NPZ to %s", full_path)
        return rel_ref
    except Exception as exc:
        logger.error("Failed to save rasters NPZ: %s", exc)
        return ""
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def _raster_artifact_manifest(rel_ref: str, cache_key: str) -> Dict[str, Any]:
    if np is None:
        raise RuntimeError("NumPy is required for raster validation")
    full_path = _artifact_path(rel_ref)
    arrays: Dict[str, Dict[str, Any]] = {}
    masks: Dict[str, Dict[str, Any]] = {}
    with safe_np_load(full_path) as data:
        for key in sorted(data.files):
            array = data[key]
            if array.dtype.hasobject or array.ndim != 2:
                raise ValueError(f"invalid cached raster {key}: {array.dtype} {array.shape}")
            entry = {
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "content_hash": stable_value_hash(array),
            }
            if key.startswith("__mask__"):
                masks[key] = entry
            else:
                arrays[key] = entry
    if not arrays:
        raise ValueError("raster artifact contains no arrays")
    return {
        "manifest_version": "v2_generation_addressed",
        "cache_key": cache_key,
        "ref": rel_ref,
        "size_bytes": os.path.getsize(full_path),
        "sha256": _file_sha256(full_path),
        "arrays": arrays,
        "masks": masks,
    }


def _grid_to_lists(array: Any) -> List[List[Optional[float]]]:
    return [
        [None if isinstance(value, float) and not math.isfinite(value) else value for value in row]
        for row in array.tolist()
    ]


def _load_validated_rasters(
    artifact: Dict[str, Any], expected_cache_key: str,
) -> Optional[Dict[str, List[List[Optional[float]]]]]:
    """Validate artifact identity, bytes and members before exposing grids."""
    if np is None or not isinstance(artifact, dict):
        return None
    try:
        if artifact.get("cache_key") != expected_cache_key:
            raise ValueError("raster manifest cache key mismatch")
        rel_ref = artifact.get("ref")
        if not isinstance(rel_ref, str) or ".." in rel_ref or rel_ref.startswith("/") or rel_ref.startswith("\\"):
            raise ValueError("invalid raster manifest reference path")
        is_fixed_ref = (rel_ref == f"asmae_rasters/raster_{expected_cache_key}.npz")
        is_generation_ref = (
            rel_ref.startswith(f"asmae_rasters/raster_{expected_cache_key}_")
            and rel_ref.endswith(".npz")
        )
        if not (is_fixed_ref or is_generation_ref):
            raise ValueError("raster manifest reference mismatch")
        full_path = _artifact_path(rel_ref)
        if not os.path.isfile(full_path):
            raise FileNotFoundError(full_path)
        if os.path.getsize(full_path) != artifact.get("size_bytes"):
            raise ValueError("raster artifact size mismatch")
        if _file_sha256(full_path) != artifact.get("sha256"):
            raise ValueError("raster artifact checksum mismatch")
        expected_arrays = artifact.get("arrays")
        if not isinstance(expected_arrays, dict) or not expected_arrays:
            raise ValueError("raster member manifest missing")
        expected_masks = artifact.get("masks") or {}

        result: Dict[str, List[List[Optional[float]]]] = {}
        masks: Dict[str, np.ndarray] = {}
        with safe_np_load(full_path) as data:
            expected_all_keys = set(expected_arrays.keys()) | set(expected_masks.keys())
            if set(data.files) != expected_all_keys:
                raise ValueError("raster artifact members differ from manifest")
            for key in sorted(data.files):
                array = data[key]
                if key.startswith("__mask__"):
                    metadata = expected_masks.get(key) or expected_arrays.get(key)
                else:
                    metadata = expected_arrays.get(key)
                if metadata is None:
                    raise ValueError(f"unmanifested raster member {key}")
                if array.dtype.hasobject or array.ndim != 2:
                    raise ValueError(f"unsafe/non-2D raster member {key}")
                if list(array.shape) != metadata.get("shape"):
                    raise ValueError(f"raster shape mismatch for {key}")
                if str(array.dtype) != metadata.get("dtype"):
                    raise ValueError(f"raster dtype mismatch for {key}")
                if stable_value_hash(array) != metadata.get("content_hash"):
                    raise ValueError(f"raster content mismatch for {key}")
                if key.startswith("__mask__"):
                    target_var_key = key[len("__mask__"):]
                    masks[target_var_key] = np.asarray(array, dtype=bool)
                else:
                    result[key] = _grid_to_lists(array)

        # Apply explicit masks with exact shape pairing and boolean check
        for target_key, mask_arr in masks.items():
            if target_key not in result:
                raise ValueError(f"orphan mask member for unknown target {target_key}")
            if not np.issubdtype(mask_arr.dtype, np.bool_):
                raise TypeError(f"mask {target_key} is not boolean: {mask_arr.dtype}")
            grid = result[target_key]
            H = len(grid)
            W = len(grid[0]) if H > 0 else 0
            if mask_arr.shape != (H, W):
                raise ValueError(
                    f"mask shape {mask_arr.shape} does not strictly match data shape {(H, W)} for {target_key}"
                )
            for r in range(H):
                for c in range(W):
                    if mask_arr[r, c]:
                        grid[r][c] = None

        return result
    except Exception as exc:
        logger.warning("Rejected ASMAE raster artifact: %s", exc)
        return None


def load_rasters_from_artifact(rel_ref: str) -> Dict[str, List[List[Optional[float]]]]:
    """Compatibility loader; cache reads use the strict manifest validator."""
    if np is None:
        return {}
    try:
        result: Dict[str, List[List[Optional[float]]]] = {}
        masks: Dict[str, np.ndarray] = {}
        with safe_np_load(_artifact_path(rel_ref)) as data:
            for key in data.files:
                array = data[key]
                if array.dtype.hasobject or array.ndim != 2:
                    raise ValueError(f"unsafe/non-2D raster member {key}")
                if key.startswith("__mask__"):
                    masks[key[len("__mask__"):]] = np.asarray(array, dtype=bool)
                else:
                    result[key] = _grid_to_lists(array)
        for target_key, mask_arr in masks.items():
            if target_key not in result:
                raise ValueError(f"orphan mask member for unknown target {target_key}")
            if not np.issubdtype(mask_arr.dtype, np.bool_):
                raise TypeError(f"mask {target_key} is not boolean: {mask_arr.dtype}")
            grid = result[target_key]
            H = len(grid)
            W = len(grid[0]) if H > 0 else 0
            if mask_arr.shape != (H, W):
                raise ValueError(
                    f"mask shape {mask_arr.shape} does not strictly match data shape {(H, W)} for {target_key}"
                )
            for r in range(H):
                for c in range(W):
                    if mask_arr[r, c]:
                        grid[r][c] = None
        return result
    except Exception as exc:
        logger.warning("Failed to load ASMAE rasters from %s: %s", rel_ref, exc)
        return {}


def serialize_and_cache_asmae(inp: ASMAEInput, output_dict: Dict[str, Any]) -> bool:
    """Atomically publish a JSON/NPZ pair without mutating ``output_dict``.

    JSON is the final commit point. A raster write or validation failure leaves
    no new completed-looking JSON entry.
    """
    diagnostics = output_dict.get("diagnostics") or {}
    reason_str = str(output_dict.get("reason") or "").lower()
    res_status = str(output_dict.get("result_status") or "").lower()
    status_str = str(output_dict.get("status") or "").lower()
    diag_reason = str(diagnostics.get("reason") or "").lower()
    diag_failure = str(diagnostics.get("failure_code") or "").lower()
    status_override = str(diagnostics.get("status_override") or "").lower()
    if (
        diagnostics.get("chain_integrity_error")
        or res_status in ("failed_spatial_fallback", "failed", "unavailable", "rejected", "aborted", "failed_spatial_timeout")
        or status_str in ("rejected", "aborted", "failed", "failed_spatial_timeout", "failed_spatial_fallback")
        or status_override in ("failed_spatial_timeout", "failed_spatial_fallback")
        or output_dict.get("is_rejected") is True
        or output_dict.get("rejected") is True
        or "rejected" in reason_str
        or "chain_integrity" in reason_str
        or "timeout" in reason_str
        or "timeout" in status_str
        or "timeout" in diag_reason
        or "timeout" in diag_failure
        or "state_estimation_timeout" in diag_failure
        or "state_estimation_timeout" in diag_reason
    ):
        logger.warning("Refusing to commit failed/rejected/fallback ASMAE spatial result to canonical cache for %s", inp.plot_id)
        return False

    cache_key = get_asmae_cache_key(inp)
    policy = inp.source_policy or "satellite"
    artifact_key = f"{cache_key}_{policy}"
    cache_path = os.path.join(CACHE_DIR, f"{artifact_key}.json")

    try:
        with _cache_key_lock(cache_path):
            cache_payload = dict(output_dict)
            rasters_to_extract: Dict[str, Any] = {}
            for field_name in _RASTER_FIELDS:
                field_value = output_dict.get(field_name)
                if isinstance(field_value, dict):
                    cache_payload[field_name] = {}
                    for variable, grid in field_value.items():
                        rasters_to_extract[f"{field_name}__{variable}"] = grid

            cache_payload.pop("_asmae_cache_commit", None)
            cache_payload["rasters_artifact_ref"] = ""
            raster_manifest: Optional[Dict[str, Any]] = None
            raster_ref: str = ""
            if rasters_to_extract:
                raster_ref = save_rasters_artifact(artifact_key, rasters_to_extract)
                if not raster_ref:
                    raise IOError("ASMAE raster artifact publication failed")
                raster_manifest = _raster_artifact_manifest(raster_ref, artifact_key)
                cache_payload["rasters_artifact_ref"] = raster_ref

            # Hash the exact JSON representation that readers will receive;
            # tuples and NumPy scalars must not change identity during dump.
            persisted_payload = json.loads(json.dumps(cache_payload, default=str))
            payload_hash = stable_value_hash(persisted_payload)
            persisted_payload["_asmae_cache_commit"] = {
                "schema_version": ASMAE_CACHE_COMMIT_SCHEMA_VERSION,
                "cache_schema_version": ASMAE_CACHE_SCHEMA_VERSION,
                "hash_schema_version": ASMAE_HASH_SCHEMA_VERSION,
                "state_support_policy_version": STATE_SUPPORT_POLICY_VERSION,
                "committed": True,
                "cache_key": cache_key,
                "artifact_key": artifact_key,
                "source_policy": policy,
                "payload_sha256": payload_hash,
                "rasters_required": bool(rasters_to_extract),
                "raster_artifact": raster_manifest,
            }
            try:
                _atomic_json_write(cache_path, persisted_payload)
            except Exception as write_exc:
                if raster_ref:
                    try:
                        os.unlink(_artifact_path(raster_ref))
                    except (FileNotFoundError, OSError):
                        pass
                raise write_exc
            logger.info("Committed ASMAE cache transaction to %s", cache_path)
            return True
    except Exception as exc:
        logger.error("Failed to commit ASMAE cache transaction: %s", exc)
        return False


def deserialize_cached_asmae(inp: ASMAEInput) -> Optional[Dict[str, Any]]:
    """Return a fully validated current-schema cache hit, else a clean miss."""
    cache_key = get_asmae_cache_key(inp)
    policy = inp.source_policy or "satellite"
    artifact_key = f"{cache_key}_{policy}"
    cache_path = os.path.join(CACHE_DIR, f"{artifact_key}.json")

    try:
        with _cache_key_lock(cache_path):
            if not os.path.isfile(cache_path):
                return None
            with open(cache_path, "r", encoding="utf-8") as handle:
                output_dict = json.load(handle)
            if not isinstance(output_dict, dict):
                raise ValueError("cache JSON root is not an object")

            diagnostics = output_dict.get("diagnostics") or {}
            reason_str = str(output_dict.get("reason") or "").lower()
            res_status = str(output_dict.get("result_status") or "").lower()
            status_str = str(output_dict.get("status") or "").lower()
            diag_reason = str(diagnostics.get("reason") or "").lower()
            diag_failure = str(diagnostics.get("failure_code") or "").lower()
            status_override = str(diagnostics.get("status_override") or "").lower()
            if (
                diagnostics.get("chain_integrity_error")
                or res_status in ("failed_spatial_fallback", "failed", "unavailable", "rejected", "aborted", "failed_spatial_timeout")
                or status_str in ("rejected", "aborted", "failed", "failed_spatial_timeout", "failed_spatial_fallback")
                or status_override in ("failed_spatial_timeout", "failed_spatial_fallback")
                or output_dict.get("is_rejected") is True
                or output_dict.get("rejected") is True
                or "rejected" in reason_str
                or "chain_integrity" in reason_str
                or "timeout" in reason_str
                or "timeout" in status_str
                or "timeout" in diag_reason
                or "timeout" in diag_failure
                or "state_estimation_timeout" in diag_failure
                or "state_estimation_timeout" in diag_reason
            ):
                raise ValueError("cached ASMAE payload represents a failed/rejected/fallback spatial execution")

            commit = output_dict.get("_asmae_cache_commit")
            if not isinstance(commit, dict):
                raise ValueError("legacy/uncommitted ASMAE cache schema")
            if (
                commit.get("committed") is not True
                or commit.get("schema_version") != ASMAE_CACHE_COMMIT_SCHEMA_VERSION
                or commit.get("cache_schema_version") != ASMAE_CACHE_SCHEMA_VERSION
                or commit.get("hash_schema_version") != ASMAE_HASH_SCHEMA_VERSION
                or commit.get("state_support_policy_version") != STATE_SUPPORT_POLICY_VERSION
                or commit.get("cache_key") != cache_key
                or commit.get("artifact_key") != artifact_key
                or commit.get("source_policy") != policy
            ):
                raise ValueError("ASMAE cache commit identity/schema mismatch")

            payload = dict(output_dict)
            payload.pop("_asmae_cache_commit", None)
            if stable_value_hash(payload) != commit.get("payload_sha256"):
                raise ValueError("ASMAE cache JSON payload checksum mismatch")

            raster_manifest = commit.get("raster_artifact")
            if commit.get("rasters_required") is True:
                rasters = _load_validated_rasters(raster_manifest, artifact_key)
                if rasters is None:
                    raise ValueError("required ASMAE raster artifact is unavailable or invalid")
                if payload.get("rasters_artifact_ref") != raster_manifest.get("ref"):
                    raise ValueError("JSON raster reference differs from commit manifest")
                for flattened_key, grid in rasters.items():
                    if flattened_key.startswith("__mask__"):
                        continue
                    if "__" not in flattened_key:
                        raise ValueError(f"invalid raster member name {flattened_key}")
                    field_name, variable = flattened_key.split("__", 1)
                    if field_name not in _RASTER_FIELDS or not variable:
                        raise ValueError(f"invalid raster member contract {flattened_key}")
                    destination = payload.setdefault(field_name, {})
                    if not isinstance(destination, dict):
                        raise ValueError(f"invalid raster destination {field_name}")
                    destination[variable] = grid
            elif raster_manifest is not None or payload.get("rasters_artifact_ref"):
                raise ValueError("cache declares no rasters but references an artifact")

            try:
                os.utime(cache_path, None)
            except OSError:
                pass
            return payload
    except TimeoutError as exc:
        logger.warning("ASMAE cache lock unavailable; treating as miss: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Rejected ASMAE cache entry %s: %s", cache_path, exc)
        return None

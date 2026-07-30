"""Safe, versioned persistence contract for durable ASMAE jobs.

The manifest is JSON and may reference immutable NumPy/SciPy artifacts.  It
never imports classes named by the payload and never enables pickle while
loading data.  Domain objects are reconstructed as ``SimpleNamespace``
instances because all ASMAE boundary adapters accept public attributes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import threading
import time
import uuid
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Mapping, Optional, Tuple

from .cache import ASMAE_CACHE_SCHEMA_VERSION
from .config import ASMAE_SCHEMA_VERSION, ASMAE_VERSION
from .geometry.support_contract import SUPPORT_CONTRACT_VERSION
from .evidence_capability import EVIDENCE_CAPABILITY_CONTRACT_VERSION

try:
    import numpy as np
except ImportError:  # pragma: no cover - the worker reports a typed failure
    np = None  # type: ignore

try:
    from scipy import sparse as scipy_sparse
except ImportError:  # pragma: no cover
    scipy_sparse = None  # type: ignore


JOB_MANIFEST_CONTRACT_VERSION = "asmae_job_manifest_v2_atomic_evidence"
JOB_RUNNER_CONTRACT_VERSION = 'asmae_external_worker_v4_fenced_leases'
_TYPE = "__asmae_manifest_type__"
_VOLATILE_CONTEXT_KEYS = {
    "run_id",
    "request_id",
    "served_at",
    "is_background_run",
    "_asmae_execution_permissions",
    "orchestrator_parent_run_id",
    "orchestrator_reintegration",
}


class ManifestError(ValueError):
    """Raised when a persisted job cannot be trusted or reconstructed."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _public_fields(value: Any) -> Dict[str, Any]:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: getattr(value, field.name)
            for field in fields(value)
            if not field.name.startswith("_")
        }
    if hasattr(value, "model_dump") and callable(value.model_dump):
        dumped = value.model_dump(mode="python")
        if isinstance(dumped, dict):
            return dumped
    if hasattr(value, "dict") and callable(value.dict):
        try:
            dumped = value.dict()
            if isinstance(dumped, dict):
                return dumped
        except TypeError:
            pass
    if hasattr(value, "__dict__"):
        return {
            str(key): item for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    raise ManifestError(
        f"unsupported manifest value type: {type(value).__module__}."
        f"{type(value).__qualname__}"
    )


def _array_identity(value: Any) -> Dict[str, Any]:
    if np is None:
        raise ManifestError("NumPy is required to persist array job inputs")
    array = np.asarray(value)
    if array.dtype.hasobject:
        raise ManifestError("object-dtype arrays are not allowed in job manifests")
    contiguous = np.ascontiguousarray(array)
    return {
        "dtype": contiguous.dtype.str,
        "shape": list(contiguous.shape),
        "sha256": _sha256_bytes(contiguous.tobytes(order="C")),
    }


def _scientific_form(value: Any) -> Any:
    """Return a deterministic, non-executable representation for identity."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return {_TYPE: "float_v1", "value": "nan"}
        if math.isinf(value):
            return {
                _TYPE: "float_v1",
                "value": "positive_infinity" if value > 0 else "negative_infinity",
            }
        return value
    if np is not None and isinstance(value, np.generic):
        return _scientific_form(value.item())
    if np is not None and isinstance(value, np.ma.MaskedArray):
        return {
            _TYPE: "masked_array_v1",
            "data": _array_identity(value.data),
            "mask": _array_identity(np.ma.getmaskarray(value)),
        }
    if np is not None and isinstance(value, np.ndarray):
        return {_TYPE: "ndarray_v1", **_array_identity(value)}
    if scipy_sparse is not None and scipy_sparse.issparse(value):
        matrix = value.tocsr(copy=False)
        return {
            _TYPE: "scipy_csr_v1",
            "shape": list(matrix.shape),
            "data": _array_identity(matrix.data),
            "indices": _array_identity(matrix.indices),
            "indptr": _array_identity(matrix.indptr),
        }
    if isinstance(value, Enum):
        return _scientific_form(value.value)
    if isinstance(value, datetime):
        return {_TYPE: "datetime_v1", "value": value.isoformat()}
    if isinstance(value, date):
        return {_TYPE: "date_v1", "value": value.isoformat()}
    if isinstance(value, Path):
        return {_TYPE: "path_v1", "value": str(value)}
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return {_TYPE: "bytes_v1", "size": len(raw), "sha256": _sha256_bytes(raw)}
    if isinstance(value, Mapping):
        if all(isinstance(key, str) for key in value):
            return {
                str(key): _scientific_form(item)
                for key, item in sorted(value.items(), key=lambda pair: pair[0])
            }
        pairs = [
            [_scientific_form(key), _scientific_form(item)]
            for key, item in value.items()
        ]
        pairs.sort(key=lambda pair: _canonical_bytes(pair[0]))
        return {_TYPE: "mapping_v1", "items": pairs}
    if isinstance(value, tuple):
        return {_TYPE: "tuple_v1", "items": [_scientific_form(item) for item in value]}
    if isinstance(value, list):
        return [_scientific_form(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_scientific_form(item) for item in value]
        items.sort(key=_canonical_bytes)
        return {_TYPE: "set_v1", "items": items}
    return {
        _TYPE: "object_v1",
        "class": f"{type(value).__module__}.{type(value).__qualname__}",
        "fields": _scientific_form(_public_fields(value)),
    }


def scientific_value_hash(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(_scientific_form(value)))


def build_job_identity(
    plot_id: str,
    context: Mapping[str, Any],
    config: Mapping[str, Any],
) -> Dict[str, Any]:
    scientific_context = {
        str(key): item for key, item in context.items()
        if str(key) not in _VOLATILE_CONTEXT_KEYS
    }
    return {
        "manifest_contract_version": JOB_MANIFEST_CONTRACT_VERSION,
        "worker_contract_version": JOB_RUNNER_CONTRACT_VERSION,
        "asmae_version": ASMAE_VERSION,
        "asmae_schema_version": ASMAE_SCHEMA_VERSION,
        "cache_schema_version": ASMAE_CACHE_SCHEMA_VERSION,
        "pixel_support_contract_version": SUPPORT_CONTRACT_VERSION,
        "evidence_capability_contract_version": str(
            context.get("evidence_capability_contract_version")
            or EVIDENCE_CAPABILITY_CONTRACT_VERSION
        ),
        "capability_plan_hash": str(context.get("capability_plan_hash", "") or ""),
        "plot_id": str(plot_id),
        "geometry_hash": str(context.get("geometry_hash", "") or ""),
        "crop_posterior_lineage": str(
            context.get("crop_posterior_lineage", "") or ""
        ),
        "crop_lineage_id": str(context.get("crop_lineage_id", "") or ""),
        "context_hash": scientific_value_hash(scientific_context),
        "config_hash": scientific_value_hash(dict(config or {})),
    }


def scientific_job_id(identity: Mapping[str, Any]) -> str:
    return _sha256_bytes(_canonical_bytes(dict(identity)))[:24]


class _Encoder:
    def __init__(self, manifest_path: Path, job_id: str) -> None:
        self.manifest_path = manifest_path
        self.job_id = str(job_id)
        self.artifact_dir = manifest_path.parent / f"{job_id}.artifacts"
        self.artifacts: list[Dict[str, Any]] = []
        self.counter = 0

    def _artifact_path(self, suffix: str, digest: str) -> Tuple[Path, str]:
        self.counter += 1
        name = f"{self.counter:05d}-{digest[:20]}{suffix}"
        path = self.artifact_dir / name
        relative = path.relative_to(self.manifest_path.parent).as_posix()
        return path, relative

    @staticmethod
    def _atomic_binary(path: Path, writer: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(
            path.name
            + f".{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with temporary.open("xb") as handle:
                writer(handle)
                handle.flush()
                os.fsync(handle.fileno())
            last_error: Optional[OSError] = None
            for attempt in range(6):
                try:
                    os.replace(temporary, path)
                    return
                except OSError as exc:
                    last_error = exc
                    if attempt == 5:
                        break
                    time.sleep(0.02 * (2 ** attempt))
            assert last_error is not None
            raise last_error
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _encode_array(self, array_value: Any) -> Dict[str, Any]:
        identity = _array_identity(array_value)
        array = np.ascontiguousarray(np.asarray(array_value))
        path, relative = self._artifact_path(".npy", identity["sha256"])
        self._atomic_binary(
            path,
            lambda handle: np.save(handle, array, allow_pickle=False),
        )
        file_hash = _sha256_bytes(path.read_bytes())
        record = {
            "kind": "numpy_npy_v1",
            "relative_path": relative,
            "file_sha256": file_hash,
            **identity,
        }
        self.artifacts.append(record)
        return {_TYPE: "artifact_ref_v1", **record}

    def _encode_sparse(self, value: Any) -> Dict[str, Any]:
        matrix = value.tocsr(copy=False)
        identity = _scientific_form(matrix)
        digest = scientific_value_hash(identity)
        path, relative = self._artifact_path(".npz", digest)

        def write(handle: Any) -> None:
            scipy_sparse.save_npz(handle, matrix, compressed=True)

        self._atomic_binary(path, write)
        record = {
            "kind": "scipy_npz_v1",
            "relative_path": relative,
            "file_sha256": _sha256_bytes(path.read_bytes()),
            "scientific_sha256": digest,
            "shape": list(matrix.shape),
            "format": "csr",
        }
        self.artifacts.append(record)
        return {_TYPE: "artifact_ref_v1", **record}

    def encode(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            if math.isfinite(value):
                return value
            return _scientific_form(value)
        if np is not None and isinstance(value, np.generic):
            return self.encode(value.item())
        if np is not None and isinstance(value, np.ma.MaskedArray):
            return {
                _TYPE: "masked_array_v1",
                "data": self._encode_array(value.data),
                "mask": self._encode_array(np.ma.getmaskarray(value)),
            }
        if np is not None and isinstance(value, np.ndarray):
            return self._encode_array(value)
        if scipy_sparse is not None and scipy_sparse.issparse(value):
            return self._encode_sparse(value)
        if isinstance(value, Enum):
            return self.encode(value.value)
        if isinstance(value, datetime):
            return {_TYPE: "datetime_v1", "value": value.isoformat()}
        if isinstance(value, date):
            return {_TYPE: "date_v1", "value": value.isoformat()}
        if isinstance(value, Path):
            return {_TYPE: "path_v1", "value": str(value)}
        if isinstance(value, (bytes, bytearray, memoryview)):
            return {
                _TYPE: "bytes_v1",
                "value": base64.b64encode(bytes(value)).decode("ascii"),
            }
        if isinstance(value, Mapping):
            if all(isinstance(key, str) for key in value):
                return {str(key): self.encode(item) for key, item in value.items()}
            return {
                _TYPE: "mapping_v1",
                "items": [[self.encode(key), self.encode(item)] for key, item in value.items()],
            }
        if isinstance(value, tuple):
            return {_TYPE: "tuple_v1", "items": [self.encode(item) for item in value]}
        if isinstance(value, list):
            return [self.encode(item) for item in value]
        if isinstance(value, (set, frozenset)):
            items = [self.encode(item) for item in value]
            items.sort(key=_canonical_bytes)
            return {_TYPE: "set_v1", "items": items}
        return {
            _TYPE: "object_v1",
            "class": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": self.encode(_public_fields(value)),
        }


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        path.name + f".{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    raw = _canonical_bytes(dict(payload))
    with temporary.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    last_error: Optional[OSError] = None
    for attempt in range(8):
        try:
            os.replace(temporary, path)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.01 * (2 ** attempt))
    temporary.unlink(missing_ok=True)
    raise last_error or OSError(f"could not publish {path}")


def write_job_manifest(
    manifest_path: Path,
    *,
    job_id: str,
    plot_id: str,
    run_id: str,
    context: Mapping[str, Any],
    config: Mapping[str, Any],
    identity: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    identity_value = dict(identity or build_job_identity(plot_id, context, config))
    if scientific_job_id(identity_value) != str(job_id):
        raise ManifestError("job_id does not match the scientific job identity")
    encoder = _Encoder(Path(manifest_path), str(job_id))
    encoded_context = encoder.encode(dict(context))
    encoded_config = encoder.encode(dict(config or {}))
    body = {
        "contract_version": JOB_MANIFEST_CONTRACT_VERSION,
        "worker_contract_version": JOB_RUNNER_CONTRACT_VERSION,
        "job_id": str(job_id),
        "plot_id": str(plot_id),
        "run_id": str(run_id),
        "identity": identity_value,
        "payload": {
            "context": encoded_context,
            "config": encoded_config,
        },
        "artifacts": encoder.artifacts,
    }
    body["encoded_payload_hash"] = _sha256_bytes(
        _canonical_bytes(body["payload"])
    )
    manifest = dict(body)
    manifest["manifest_hash"] = _sha256_bytes(_canonical_bytes(body))
    _atomic_json(Path(manifest_path), manifest)
    return manifest


def _resolve_artifact(manifest_path: Path, relative_path: str) -> Path:
    root = manifest_path.parent.resolve()
    candidate = (root / str(relative_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ManifestError("artifact path escapes the job directory") from exc
    return candidate


def validate_job_manifest(
    manifest_path: Path,
    *,
    expected_job_id: Optional[str] = None,
    expected_identity: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    path = Path(manifest_path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise ManifestError("job manifest is missing or invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise ManifestError("job manifest root must be an object")
    if manifest.get("contract_version") != JOB_MANIFEST_CONTRACT_VERSION:
        raise ManifestError("job manifest contract is obsolete")
    if manifest.get("worker_contract_version") != JOB_RUNNER_CONTRACT_VERSION:
        raise ManifestError("job worker contract is obsolete")
    if expected_job_id and manifest.get("job_id") != expected_job_id:
        raise ManifestError("job manifest identity mismatch")
    body = dict(manifest)
    supplied_hash = str(body.pop("manifest_hash", ""))
    if not supplied_hash or _sha256_bytes(_canonical_bytes(body)) != supplied_hash:
        raise ManifestError("job manifest hash mismatch")
    payload = manifest.get("payload")
    if not isinstance(payload, dict):
        raise ManifestError("job manifest payload is missing")
    if _sha256_bytes(_canonical_bytes(payload)) != manifest.get("encoded_payload_hash"):
        raise ManifestError("job manifest payload hash mismatch")
    identity = manifest.get("identity")
    if not isinstance(identity, dict):
        raise ManifestError("job scientific identity is missing")
    if scientific_job_id(identity) != manifest.get("job_id"):
        raise ManifestError("job scientific identity hash mismatch")
    current_versions = {
        "manifest_contract_version": JOB_MANIFEST_CONTRACT_VERSION,
        "worker_contract_version": JOB_RUNNER_CONTRACT_VERSION,
        "asmae_version": ASMAE_VERSION,
        "asmae_schema_version": ASMAE_SCHEMA_VERSION,
        "cache_schema_version": ASMAE_CACHE_SCHEMA_VERSION,
        "pixel_support_contract_version": SUPPORT_CONTRACT_VERSION,
        "evidence_capability_contract_version": EVIDENCE_CAPABILITY_CONTRACT_VERSION,
    }
    for key, current in current_versions.items():
        if identity.get(key) != current:
            raise ManifestError(f"job identity is obsolete: {key}")
    if not str(identity.get("capability_plan_hash", "")):
        raise ManifestError("job identity has no atomic capability plan hash")
    if expected_identity is not None and dict(identity) != dict(expected_identity):
        raise ManifestError("persisted job does not match the requested inputs")
    for record in manifest.get("artifacts", []):
        if not isinstance(record, dict):
            raise ManifestError("invalid artifact record")
        artifact_path = _resolve_artifact(path, str(record.get("relative_path", "")))
        try:
            actual_hash = _sha256_bytes(artifact_path.read_bytes())
        except OSError as exc:
            raise ManifestError("job artifact is missing") from exc
        if actual_hash != record.get("file_sha256"):
            raise ManifestError("job artifact hash mismatch")
    return manifest


class _Decoder:
    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path

    def _artifact(self, value: Mapping[str, Any]) -> Any:
        path = _resolve_artifact(
            self.manifest_path, str(value.get("relative_path", ""))
        )
        if _sha256_bytes(path.read_bytes()) != value.get("file_sha256"):
            raise ManifestError("job artifact changed after validation")
        kind = value.get("kind")
        if kind == "numpy_npy_v1":
            if np is None:
                raise ManifestError("NumPy is required to load this job")
            array = np.load(path, allow_pickle=False)
            identity = _array_identity(array)
            for key in ("dtype", "shape", "sha256"):
                if identity.get(key) != value.get(key):
                    raise ManifestError("NumPy artifact scientific identity mismatch")
            return array
        if kind == "scipy_npz_v1":
            if scipy_sparse is None:
                raise ManifestError("SciPy is required to load this job")
            matrix = scipy_sparse.load_npz(path).tocsr()
            if list(matrix.shape) != list(value.get("shape") or []):
                raise ManifestError("sparse artifact shape mismatch")
            if scientific_value_hash(_scientific_form(matrix)) != value.get(
                "scientific_sha256"
            ):
                raise ManifestError("sparse artifact scientific identity mismatch")
            return matrix
        raise ManifestError(f"unsupported job artifact kind: {kind}")

    def decode(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self.decode(item) for item in value]
        if not isinstance(value, dict):
            return value
        kind = value.get(_TYPE)
        if kind is None:
            return {str(key): self.decode(item) for key, item in value.items()}
        if kind == "artifact_ref_v1":
            return self._artifact(value)
        if kind == "masked_array_v1":
            if np is None:
                raise ManifestError("NumPy is required to load this job")
            return np.ma.array(
                self.decode(value.get("data")),
                mask=self.decode(value.get("mask")),
            )
        if kind == "float_v1":
            raw = value.get("value")
            return {
                "nan": float("nan"),
                "positive_infinity": float("inf"),
                "negative_infinity": float("-inf"),
            }.get(str(raw))
        if kind == "datetime_v1":
            return datetime.fromisoformat(str(value.get("value", "")).replace("Z", "+00:00"))
        if kind == "date_v1":
            return date.fromisoformat(str(value.get("value", "")))
        if kind == "path_v1":
            return str(value.get("value", ""))
        if kind == "bytes_v1":
            return base64.b64decode(str(value.get("value", "")), validate=True)
        if kind == "tuple_v1":
            return tuple(self.decode(item) for item in value.get("items", []))
        if kind == "set_v1":
            return set(self.decode(item) for item in value.get("items", []))
        if kind == "mapping_v1":
            return {
                self.decode(pair[0]): self.decode(pair[1])
                for pair in value.get("items", [])
            }
        if kind == "object_v1":
            decoded = self.decode(value.get("fields", {}))
            if not isinstance(decoded, dict):
                raise ManifestError("object fields must decode to a mapping")
            namespace = SimpleNamespace(**decoded)
            setattr(namespace, "_manifest_source_class", value.get("class"))
            return namespace
        raise ManifestError(f"unsupported job manifest type: {kind}")


def load_job_manifest(manifest_path: Path) -> Dict[str, Any]:
    path = Path(manifest_path)
    manifest = validate_job_manifest(path)
    decoder = _Decoder(path)
    payload = manifest["payload"]
    context = decoder.decode(payload.get("context", {}))
    config = decoder.decode(payload.get("config", {}))
    if not isinstance(context, dict) or not isinstance(config, dict):
        raise ManifestError("decoded job context/config must be mappings")
    return {
        "context": context,
        "config": config,
        "identity": dict(manifest["identity"]),
        "manifest_hash": manifest["manifest_hash"],
    }


def manifest_compatibility(
    manifest_path: Path,
    *,
    job_id: str,
    identity: Mapping[str, Any],
) -> Tuple[bool, str]:
    try:
        validate_job_manifest(
            manifest_path,
            expected_job_id=job_id,
            expected_identity=identity,
        )
    except ManifestError as exc:
        return False, str(exc)
    return True, "compatible"

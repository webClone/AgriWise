"""
ASMAE Observation Operator Store.

Persistence layer for H_t operators:
  - Runtime → Manifest conversion
  - Manifest → Runtime loading
  - Content-addressed storage (deterministic H_t)
  - .npz artifact management for scipy sparse matrices

Design:
  - Same scene + same resolution always produces the same H_t
  - Storage is content-addressed via the operator_id hash
  - The manifest carries metadata; the .npz carries the matrix
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..schema import (
    ObservationOperatorManifest,
    ObservationOperatorRuntime,
)

logger = logging.getLogger(__name__)

# Try scipy for sparse matrix serialization
try:
    from scipy import sparse as sp
    import numpy as np
    HAS_SCIPY = True
except ImportError:
    sp = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    HAS_SCIPY = False


def runtime_to_manifest(
    runtime: ObservationOperatorRuntime,
    artifact_ref: str = "",
) -> ObservationOperatorManifest:
    """Convert an in-memory H_t operator to a serializable manifest.

    The sparse matrix is NOT included — it must be saved separately
    as a .npz artifact and referenced by artifact_ref.
    """
    shape = (0, 0)
    nnz = 0
    dtype = "float32"

    if runtime.H_matrix is not None and HAS_SCIPY:
        shape = runtime.H_matrix.shape
        nnz = runtime.H_matrix.nnz
        dtype = str(runtime.H_matrix.dtype)

    # Content hash for determinism verification
    hash_payload = {
        "operator_id": runtime.operator_id,
        "scene_id": runtime.scene_id,
        "source_resolution_m": runtime.source_resolution_m,
        "target_resolution_m": runtime.target_resolution_m,
        "shape": list(shape),
        "nnz": nnz,
        "psf_model": runtime.psf_model,
        "blur_sigma_m": runtime.blur_sigma_m,
    }
    content_hash = hashlib.sha256(
        json.dumps(hash_payload, sort_keys=True, default=str).encode()
    ).hexdigest()

    return ObservationOperatorManifest(
        operator_id=runtime.operator_id,
        scene_id=runtime.scene_id,
        sensor=runtime.sensor,
        source_resolution_m=runtime.source_resolution_m,
        target_resolution_m=runtime.target_resolution_m,
        source_crs=runtime.source_crs,
        target_crs=runtime.target_crs,
        source_transform=runtime.source_transform,
        target_transform=runtime.target_transform,
        h_matrix_artifact_ref=artifact_ref,
        h_matrix_format="csr_v1",
        h_matrix_shape=shape,
        h_matrix_nnz=nnz,
        h_matrix_dtype=dtype,
        psf_model=runtime.psf_model,
        blur_sigma_m=runtime.blur_sigma_m,
        support_score=runtime.support_score,
        condition_number_proxy=runtime.condition_number_proxy,
        registration_uncertainty_m=runtime.registration_uncertainty_m,
        content_hash=content_hash,
    )


def manifest_to_dict(manifest: ObservationOperatorManifest) -> Dict[str, Any]:
    """Convert manifest to JSON-serializable dict."""
    return {
        "operator_id": manifest.operator_id,
        "scene_id": manifest.scene_id,
        "sensor": manifest.sensor,
        "source_resolution_m": manifest.source_resolution_m,
        "target_resolution_m": manifest.target_resolution_m,
        "source_crs": manifest.source_crs,
        "target_crs": manifest.target_crs,
        "source_transform": manifest.source_transform,
        "target_transform": manifest.target_transform,
        "h_matrix_artifact_ref": manifest.h_matrix_artifact_ref,
        "h_matrix_format": manifest.h_matrix_format,
        "h_matrix_shape": list(manifest.h_matrix_shape),
        "h_matrix_nnz": manifest.h_matrix_nnz,
        "h_matrix_dtype": manifest.h_matrix_dtype,
        "psf_model": manifest.psf_model,
        "blur_sigma_m": manifest.blur_sigma_m,
        "support_score": manifest.support_score,
        "condition_number_proxy": manifest.condition_number_proxy,
        "registration_uncertainty_m": manifest.registration_uncertainty_m,
        "content_hash": manifest.content_hash,
    }


def save_h_matrix_npz(
    runtime: ObservationOperatorRuntime,
    path: str,
) -> bool:
    """Save the H_t sparse matrix as a .npz file.

    Returns True if saved, False if no matrix or scipy unavailable.
    """
    if not HAS_SCIPY or runtime.H_matrix is None:
        return False

    try:
        sp.save_npz(path, runtime.H_matrix.tocsr())
        return True
    except Exception as e:
        logger.warning("Failed to save H_t matrix: %s", e)
        return False


def load_h_matrix_npz(path: str) -> Optional[Any]:
    """Load an H_t sparse matrix from a .npz file.

    Returns scipy.sparse.csr_matrix or None.
    """
    if not HAS_SCIPY:
        return None

    try:
        return sp.load_npz(path)
    except Exception as e:
        logger.warning("Failed to load H_t matrix: %s", e)
        return None


class OperatorCache:
    """In-memory cache for H_t operators during an ASMAE run.

    Keyed by (scene_id, resolution_m) → deterministic H_t.
    Ensures the acceptance gate: same inputs → same operator.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, ObservationOperatorRuntime] = {}

    def _key(self, scene_id: str, resolution_m: int) -> str:
        return f"{scene_id}@{resolution_m}m"

    def get(
        self, scene_id: str, resolution_m: int,
    ) -> Optional[ObservationOperatorRuntime]:
        return self._cache.get(self._key(scene_id, resolution_m))

    def put(self, operator: ObservationOperatorRuntime) -> None:
        key = self._key(operator.scene_id, operator.target_resolution_m)
        self._cache[key] = operator

    def has(self, scene_id: str, resolution_m: int) -> bool:
        return self._key(scene_id, resolution_m) in self._cache

    def count(self) -> int:
        return len(self._cache)

    def all_operators(self) -> List[ObservationOperatorRuntime]:
        return list(self._cache.values())

    def clear(self) -> None:
        self._cache.clear()

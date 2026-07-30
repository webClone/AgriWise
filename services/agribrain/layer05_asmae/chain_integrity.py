"""
V922: ASMAE Chain Integrity Module.

Provides the custom exception and shared assertion helpers used by all
downstream pipeline stages (EnKF, radiometric, retrovalidation) to verify
that the operators they receive match the selected resolution.

Design rules:
  1. ASMAEChainIntegrityError is the ONLY exception for resolution mismatch.
  2. The engine catches it specifically and fails closed (production_usable=false).
  3. Assertions are called at the TOP of each downstream function, not buried.
  4. All assertions are deterministic and side-effect-free.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, List, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import ObservationOperatorRuntime

logger = logging.getLogger(__name__)


class ASMAEChainIntegrityError(RuntimeError):
    """Raised when the scientific chain between selected resolution,
    operators, graph, and downstream stages is broken.

    The ASMAE engine must catch this specifically and fail closed:
      - production_usable = False
      - layer1_export_allowed = False
      - state_update_allowed = False
      - weak_label_export_allowed = False
      - diagnostic_only = True
    """
    pass


def assert_operators_match_resolution(
    operators: Sequence[Any],
    expected_resolution_m: int,
    stage_name: str = "unknown",
) -> None:
    """Verify every operator's target_resolution_m matches expected.

    Args:
        operators: Sequence of ObservationOperatorRuntime objects.
        expected_resolution_m: The selected effective resolution.
        stage_name: Human-readable name of the calling stage (for error messages).

    Raises:
        ASMAEChainIntegrityError: If any operator mismatches.
    """
    if not operators:
        return

    for op in operators:
        op_res = getattr(op, "target_resolution_m", None)
        if op_res is not None and op_res != expected_resolution_m:
            op_id = getattr(op, "operator_id", "unknown")
            raise ASMAEChainIntegrityError(
                f"[{stage_name}] operator {op_id} built for {op_res}m "
                f"but stage expected {expected_resolution_m}m"
            )


def assert_operators_match_graph(
    operators: Sequence[Any],
    graph_node_count: int,
    stage_name: str = "unknown",
) -> None:
    """Verify operator H_matrix column count matches graph node count.

    Args:
        operators: Sequence of ObservationOperatorRuntime objects.
        graph_node_count: Expected number of microzones in the graph.
        stage_name: Human-readable name of the calling stage.

    Raises:
        ASMAEChainIntegrityError: If any operator's H_matrix column count mismatches.
    """
    if not operators or graph_node_count <= 0:
        return

    for op in operators:
        h_matrix = getattr(op, "H_matrix", None)
        if h_matrix is not None and hasattr(h_matrix, "shape"):
            n_cols = h_matrix.shape[1]
            if n_cols != graph_node_count:
                op_id = getattr(op, "operator_id", "unknown")
                raise ASMAEChainIntegrityError(
                    f"[{stage_name}] operator {op_id} H_matrix has {n_cols} columns "
                    f"but graph has {graph_node_count} nodes"
                )


def assert_scene_operator_binding(
    scenes: Sequence[Any],
    operators: Sequence[Any],
    stage_name: str = 'unknown',
) -> None:
    if len(scenes) != len(operators):
        raise ASMAEChainIntegrityError(
            f'[{stage_name}] scene/operator count mismatch: '
            f'{len(scenes)} scenes, {len(operators)} operators'
        )
    scene_ids = [str(getattr(scene, 'scene_id', '')) for scene in scenes]
    operator_scene_ids = [str(getattr(op, 'scene_id', '')) for op in operators]
    if not all(scene_ids) or len(set(scene_ids)) != len(scene_ids):
        raise ASMAEChainIntegrityError(
            f'[{stage_name}] scene IDs must be non-empty and unique'
        )
    if scene_ids != operator_scene_ids:
        raise ASMAEChainIntegrityError(
            f'[{stage_name}] exact scene/operator binding mismatch: '
            f'scenes={scene_ids}, operators={operator_scene_ids}'
        )
    for scene, operator in zip(scenes, operators):
        scene_support = str(getattr(scene, 'valid_support_hash', '') or '')
        operator_support = str(getattr(operator, 'valid_support_hash', '') or '')
        if not scene_support or scene_support != operator_support:
            raise ASMAEChainIntegrityError(
                f'[{stage_name}] valid-support binding mismatch for '
                f'{scene.scene_id}'
            )
        if str(getattr(operator, 'source_crs', '')) != str(getattr(scene, 'crs', '')):
            raise ASMAEChainIntegrityError(
                f'[{stage_name}] CRS binding mismatch for {scene.scene_id}'
            )
        matrix = getattr(operator, 'H_matrix', None)
        expected_rows = int(getattr(scene, 'height', 0)) * int(getattr(scene, 'width', 0))
        if matrix is None or int(matrix.shape[0]) != expected_rows:
            raise ASMAEChainIntegrityError(
                f'[{stage_name}] H_t rows do not match pixels for {scene.scene_id}'
            )


def assert_bundle_integrity(
    bundle: Any,
    stage_name: str = "unknown",
) -> None:
    """Full bundle integrity check — resolution + graph + operators.

    Calls both resolution and graph assertions.

    Args:
        bundle: A SelectedOperatorBundle instance.
        stage_name: Human-readable name of the calling stage.

    Raises:
        ASMAEChainIntegrityError: If any invariant is violated.
    """
    if bundle is None:
        raise ASMAEChainIntegrityError(
            f"[{stage_name}] received None bundle — no valid operator binding"
        )

    assert_operators_match_resolution(
        operators=bundle.operators,
        expected_resolution_m=bundle.selected_resolution_m,
        stage_name=stage_name,
    )

    assert_operators_match_graph(
        operators=bundle.operators,
        graph_node_count=bundle.graph_node_count,
        stage_name=stage_name,
    )


def compute_h_matrix_digest(h_matrix: Any) -> str:
    """Compute a content-addressed digest of a sparse H_t matrix.

    Every stored value and structural index is hashed. Sampling is forbidden:
    a change anywhere in a large operator must change its scientific identity.

    Returns:
        64-char hex SHA-256 digest, or "" if matrix is None/unavailable.
    """
    if h_matrix is None:
        return ""

    try:
        h = hashlib.sha256()
        if hasattr(h_matrix, "tocsr"):
            exact = h_matrix.tocsr(copy=True)
            exact.sum_duplicates()
            exact.sort_indices()
            shape = tuple(exact.shape)
            h.update(f"kind=csr|shape={shape}|nnz={int(exact.nnz)}".encode())
            arrays = (
                ("data", exact.data),
                ("indices", exact.indices),
                ("indptr", exact.indptr),
            )
        elif hasattr(h_matrix, "tobytes"):
            shape = tuple(h_matrix.shape) if hasattr(h_matrix, "shape") else (0, 0)
            h.update(f"kind=dense|shape={shape}".encode())
            arrays = (("data", h_matrix),)
        else:
            raise TypeError("operator matrix exposes no exact byte representation")

        for label, array in arrays:
            if not hasattr(array, "tobytes"):
                raise TypeError(f"operator matrix {label} is not byte-addressable")
            h.update(f"|{label}|dtype={getattr(array, 'dtype', '')}|".encode())
            h.update(array.tobytes(order="C"))

        return h.hexdigest()

    except Exception as e:
        raise RuntimeError("exact H-matrix digest failed") from e


def compute_bundle_content_hash(
    selected_resolution_m: int,
    operator_ids: Sequence[str],
    operator_content_hashes: Sequence[str],
    operator_matrix_hashes: Optional[Sequence[str]] = None,
    h_shapes: Optional[Sequence[tuple]] = None,
    graph_hash: str = "",
    graph_node_count: int = 0,
    coreg_hash: str = "",
    diagnostics_summary: Optional[dict] = None,
    builder_version: str = "v922.2a",
) -> str:
    """Compute a comprehensive content hash for an operator bundle.

    Includes resolution, operator identity AND content (matrix digest),
    graph identity, coregistration identity, diagnostics, and builder version.

    V922.2A: Now includes operator_matrix_hashes (from compute_h_matrix_digest)
    for true content-addressed hashing of sparse H_t values.
    """
    if diagnostics_summary is None:
        diagnostics_summary = {}

    payload = {
        "selected_resolution_m": selected_resolution_m,
        "operator_ids": list(operator_ids),
        "operator_content_hashes": list(operator_content_hashes),
        "operator_matrix_hashes": list(operator_matrix_hashes) if operator_matrix_hashes else [],
        "h_shapes": [list(s) for s in h_shapes] if h_shapes else [],
        "graph_hash": graph_hash,
        "graph_node_count": graph_node_count,
        "coreg_hash": coreg_hash,
        "diagnostics_n_passed": diagnostics_summary.get("n_passed", 0),
        "diagnostics_n_errors": diagnostics_summary.get("n_errors", 0),
        "builder_version": builder_version,
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

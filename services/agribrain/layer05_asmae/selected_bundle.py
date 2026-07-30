"""
V922: SelectedOperatorBundle — Immutable Resolution→Operator→Graph Binding.

Once constructed, no downstream step can swap in different operators or
change the resolution. This is the single source of truth for what
operators and graph the EnKF, radiometric consistency, and retrovalidation
modules must use.

Design rules:
  1. frozen=True — immutable after construction
  2. __post_init__ validates all invariants
  3. content_hash covers resolution + operators + graph + diagnostics
  4. Graph is bound — demotion must rebuild both operators AND graph
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .chain_integrity import (
    ASMAEChainIntegrityError,
    assert_operators_match_graph,
    compute_bundle_content_hash,
    compute_h_matrix_digest,
)


@dataclass(frozen=True)
class SelectedOperatorBundle:
    """Immutable bundle binding selected resolution → Hₜ operators → graph.

    Constructed after resolution selection. Passed as the sole operator
    authority to EnKF, radiometric, and retrovalidation.

    Invariants enforced in __post_init__:
      1. Every operator's target_resolution_m == selected_resolution_m
      2. operator_count == len(operators)
      3. operator_ids == tuple(op.operator_id for op in operators)
      4. content_hash is non-empty
    """
    # Resolution binding
    selected_resolution_m: int

    # Operator binding (tuple for immutability)
    operators: Tuple[Any, ...]           # ObservationOperatorRuntime
    operator_count: int
    operator_ids: Tuple[str, ...]

    # Graph binding
    graph_ref: str                       # Graph summary ref / ID
    graph_node_count: int
    graph_hash: str

    # Diagnostics binding
    operator_diagnostics_summary: Dict[str, Any]
    operator_diagnostics_n_errors: int

    # Resolution decision reference
    resolution_decision_ref: Any         # ResolutionDecision (not copied, ref)

    # Provenance
    content_hash: str
    was_rebuilt: bool                     # True if operators were rebuilt post-selection
    was_demoted: bool                    # True if original selection was demoted
    original_selected_resolution_m: int  # Before demotion (== selected if no demotion)
    coreg_hash: str                      # Coregistration identity

    def __post_init__(self) -> None:
        """Validate all invariants. Raises ASMAEChainIntegrityError on violation."""
        # 1. Operator count
        if self.operator_count != len(self.operators):
            raise ASMAEChainIntegrityError(
                f"SelectedOperatorBundle: operator_count={self.operator_count} "
                f"but len(operators)={len(self.operators)}"
            )

        # 2. Operator IDs match
        actual_ids = tuple(
            getattr(op, "operator_id", "") for op in self.operators
        )
        if self.operator_ids != actual_ids:
            raise ASMAEChainIntegrityError(
                f"SelectedOperatorBundle: operator_ids mismatch. "
                f"Declared={self.operator_ids}, actual={actual_ids}"
            )

        # 3. Every operator matches selected resolution
        for op in self.operators:
            op_res = getattr(op, "target_resolution_m", None)
            if op_res is not None and op_res != self.selected_resolution_m:
                op_id = getattr(op, "operator_id", "unknown")
                raise ASMAEChainIntegrityError(
                    f"SelectedOperatorBundle: operator {op_id} built for "
                    f"{op_res}m but bundle declares {self.selected_resolution_m}m"
                )

        # 4. Content hash present
        if not self.content_hash:
            raise ASMAEChainIntegrityError(
                "SelectedOperatorBundle: content_hash is empty"
            )

        # 5. No diagnostic errors in selected operators
        if self.operator_diagnostics_n_errors > 0:
            raise ASMAEChainIntegrityError(
                f"SelectedOperatorBundle: {self.operator_diagnostics_n_errors} "
                f"operator diagnostic errors — bundle should not have been created"
            )

        # 6. H_matrix columns match graph node count (V922.2A)
        # Double validation: also checked downstream by assert_bundle_integrity(),
        # but catching it here is earlier and cleaner.
        if self.graph_node_count > 0:
            assert_operators_match_graph(
                self.operators,
                self.graph_node_count,
                stage_name="SelectedOperatorBundle.__post_init__",
            )

    @property
    def is_valid(self) -> bool:
        """Check if this bundle passes all integrity checks."""
        try:
            # Re-run validation (frozen, so state can't change)
            if self.operator_count != len(self.operators):
                return False
            for op in self.operators:
                op_res = getattr(op, "target_resolution_m", None)
                if op_res is not None and op_res != self.selected_resolution_m:
                    return False
            if self.operator_diagnostics_n_errors > 0:
                return False
            if self.graph_node_count > 0:
                assert_operators_match_graph(self.operators, self.graph_node_count)
            return True
        except Exception:
            return False

    def to_provenance_dict(self) -> Dict[str, Any]:
        """Serialize provenance-relevant fields (no numpy/scipy)."""
        return {
            "selected_resolution_m": self.selected_resolution_m,
            "operator_count": self.operator_count,
            "operator_ids": list(self.operator_ids),
            "graph_ref": self.graph_ref,
            "graph_node_count": self.graph_node_count,
            "graph_hash": self.graph_hash,
            "content_hash": self.content_hash,
            "was_rebuilt": self.was_rebuilt,
            "was_demoted": self.was_demoted,
            "original_selected_resolution_m": self.original_selected_resolution_m,
            "coreg_hash": self.coreg_hash,
            "diagnostics_n_errors": self.operator_diagnostics_n_errors,
            "diagnostics_summary": self.operator_diagnostics_summary,
        }


def build_selected_operator_bundle(
    selected_resolution_m: int,
    operators: Sequence[Any],
    operator_diagnostics: Any,
    graph: Any,
    resolution_decision: Any,
    coreg_results: Optional[Sequence[Any]] = None,
    was_rebuilt: bool = False,
    was_demoted: bool = False,
    original_selected_resolution_m: Optional[int] = None,
) -> SelectedOperatorBundle:
    """Factory function to construct a SelectedOperatorBundle.

    Computes derived fields (IDs, hashes) from the raw inputs.

    Args:
        selected_resolution_m: The final effective resolution.
        operators: List of ObservationOperatorRuntime at that resolution.
        operator_diagnostics: OperatorDiagnosticReport for those operators.
        graph: MicrozoneGraph object.
        resolution_decision: ResolutionDecision from the selector.
        coreg_results: Coregistration results (for hash computation).
        was_rebuilt: Whether operators were rebuilt after selection.
        was_demoted: Whether the resolution was demoted from original selection.
        original_selected_resolution_m: Resolution before demotion.

    Returns:
        SelectedOperatorBundle (frozen, validated).
    """
    op_ids = tuple(getattr(op, "operator_id", "") for op in operators)
    op_count = len(operators)

    # Graph identity
    if hasattr(graph, "content_hash"):
        g_hash = graph.content_hash()
    elif hasattr(graph, "summary"):
        summary = graph.summary()
        g_hash = hashlib.sha256(
            json.dumps(summary, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
    elif isinstance(graph, dict):
        g_hash = hashlib.sha256(
            json.dumps(graph, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
    else:
        g_hash = ""

    if hasattr(graph, "node_count"):
        g_node_count = graph.node_count
    elif isinstance(graph, dict):
        g_node_count = graph.get("node_count", 0)
    else:
        g_node_count = 0

    g_ref = getattr(graph, "graph_id", g_hash)
    if isinstance(graph, dict):
        g_ref = graph.get("graph_id", g_hash)

    # Operator content hashes (metadata-based ID)
    op_content_hashes = []
    for op in operators:
        if hasattr(op, "operator_id"):
            op_content_hashes.append(op.operator_id)
        else:
            op_content_hashes.append("")

    # V922.2A: True H-matrix value digests (data+indices+indptr)
    op_matrix_hashes = []
    h_shapes = []
    for op in operators:
        h_matrix = getattr(op, "H_matrix", None)
        op_matrix_hashes.append(compute_h_matrix_digest(h_matrix))
        if h_matrix is not None and hasattr(h_matrix, "shape"):
            h_shapes.append(tuple(h_matrix.shape))
        else:
            h_shapes.append((0, 0))

    # Coregistration hash
    coreg_hash = ""
    if coreg_results:
        coreg_data = []
        for cr in coreg_results:
            if hasattr(cr, "shift_x_m"):
                coreg_data.append({
                    "shift_x": round(getattr(cr, "shift_x_m", 0.0), 4),
                    "shift_y": round(getattr(cr, "shift_y_m", 0.0), 4),
                    "accepted": getattr(cr, "accepted", False),
                })
        if coreg_data:
            coreg_hash = hashlib.sha256(
                json.dumps(coreg_data, sort_keys=True).encode()
            ).hexdigest()[:16]

    # Diagnostics summary
    if hasattr(operator_diagnostics, "to_dict"):
        diag_summary = operator_diagnostics.to_dict()
    elif isinstance(operator_diagnostics, dict):
        diag_summary = operator_diagnostics
    else:
        diag_summary = {}

    diag_n_errors = 0
    if hasattr(operator_diagnostics, "n_errors"):
        diag_n_errors = operator_diagnostics.n_errors
    elif isinstance(operator_diagnostics, dict):
        diag_n_errors = operator_diagnostics.get("n_errors", 0)

    # Content hash (V922.2A: includes matrix value digests)
    c_hash = compute_bundle_content_hash(
        selected_resolution_m=selected_resolution_m,
        operator_ids=op_ids,
        operator_content_hashes=op_content_hashes,
        operator_matrix_hashes=op_matrix_hashes,
        h_shapes=h_shapes,
        graph_hash=g_hash,
        graph_node_count=g_node_count,
        coreg_hash=coreg_hash,
        diagnostics_summary={
            "n_passed": diag_summary.get("n_passed", 0),
            "n_errors": diag_n_errors,
        },
    )

    if original_selected_resolution_m is None:
        original_selected_resolution_m = selected_resolution_m

    return SelectedOperatorBundle(
        selected_resolution_m=selected_resolution_m,
        operators=tuple(operators),
        operator_count=op_count,
        operator_ids=op_ids,
        graph_ref=g_ref if isinstance(g_ref, str) else str(g_ref),
        graph_node_count=g_node_count,
        graph_hash=g_hash,
        operator_diagnostics_summary=diag_summary,
        operator_diagnostics_n_errors=diag_n_errors,
        resolution_decision_ref=resolution_decision,
        content_hash=c_hash,
        was_rebuilt=was_rebuilt,
        was_demoted=was_demoted,
        original_selected_resolution_m=original_selected_resolution_m,
        coreg_hash=coreg_hash,
    )

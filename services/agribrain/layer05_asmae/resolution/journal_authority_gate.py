"""IR-04: independently hydrate bitemporal replay against pinned Worldline.

A self-digesting replay receipt is only a *claim*. Historical scientific
authority requires a cold journal read from an independently configured,
durably anchored namespace and the exact same (valid T, knowledge K) selection.

This is a journal-and-anchor consistency gate, NOT a signed journal trust root.
Externally signed checkpoints / immutable hardware-backed retention remain
a separate production certification requirement.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Dict, Mapping, Optional, Tuple

from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService
from .observation_footprint_adapter import (
    verify_bitemporal_replay_receipt,
    _ensure_utc_iso,
)


def verify_replay_against_trusted_worldline(
    receipt: Any,
    *,
    tenant_id: str,
    plot_id: str,
    geometry_hash: str,
    namespace: str,
    journal_watermark: Optional[str] = None,
    trusted_worldline: Optional[CanonicalWorldlineService] = None,
) -> Tuple[bool, str, Optional[str]]:
    """Return validated K only after an independent, anchored journal replay.

    The optional object is for explicit trusted dependency injection, not a
    service root or path taken from the untrusted incoming receipt.
    """
    ok, reason, knowledge_k = verify_bitemporal_replay_receipt(
        receipt, tenant_id=tenant_id, plot_id=plot_id,
        geometry_hash=geometry_hash, journal_watermark=journal_watermark,
    )
    if not ok or knowledge_k is None:
        return False, reason, None
    if not namespace or not isinstance(namespace, str):
        return False, "worldline_namespace_required", None

    params = receipt.get("query_parameters") if isinstance(receipt, Mapping) else None
    if not isinstance(params, Mapping):
        return False, "missing_replay_query", None
    valid_t = _ensure_utc_iso(params.get("observation_valid_time"))
    if not valid_t:
        return False, "missing_or_invalid_replay_valid_time", None
    if datetime.fromisoformat(knowledge_k) > datetime.now(timezone.utc):
        return False, "future_replay_knowledge_cutoff", None

    if trusted_worldline is None:
        # Only deployment-owned paths are acceptable. Never take root paths
        # or anchor generations directly from an incoming receipt.
        root = os.environ.get("AKALORIS_ASMAE_TRUSTED_WORLDLINE_ROOT")
        anchor_root = os.environ.get("CANONICAL_DURABLE_CHECKPOINT_ROOT")
        if not root or not anchor_root:
            return False, "trusted_worldline_roots_not_configured", None
        try:
            trusted_worldline = CanonicalWorldlineService(
                root=root, durable_anchor_root=anchor_root,
                require_durable_anchor=True,
            )
        except Exception:
            return False, "trusted_worldline_unavailable", None

    if (trusted_worldline.require_durable_anchor is not True
            or not trusted_worldline.durable_anchor_root):
        return False, "durable_worldline_anchor_required", None

    try:
        cold_context = trusted_worldline.hydrate_context(
            plot_id,
            {
                "tenant_id": tenant_id,
                "worldline_namespace": namespace,
                "geometry_hash": geometry_hash,
            },
            valid_time_T=valid_t,
            knowledge_cutoff_K=knowledge_k,
        )
        expected = cold_context.get("bitemporal_replay_receipt")
        if not isinstance(expected, Mapping):
            return False, "trusted_worldline_replay_unavailable", None
        generation = expected.get("journal_generation")
        if (type(generation) is not int or generation < 1
                or expected.get("durable_anchor_bound") is not True
                or expected.get("durable_anchor_generation") != generation):
            return False, "unanchored_worldline_generation", None
        for field in ("journal_generation", "durable_anchor_generation", "durable_anchor_bound"):
            if receipt.get(field) != expected.get(field):
                return False, f"replay_generation_mismatch:{field}", None
        if receipt.get("selected_evidence_set") != expected.get("selected_evidence_set"):
            return False, "replay_evidence_not_from_trusted_journal", None
        if receipt.get("evidence_set_digest") != expected.get("evidence_set_digest"):
            return False, "replay_digest_not_from_trusted_journal", None
        expected_q = expected.get("query_parameters") or {}
        if (_ensure_utc_iso(expected_q.get("observation_valid_time")) != valid_t
                or _ensure_utc_iso(expected_q.get("knowledge_cutoff_time")) != knowledge_k):
            return False, "replay_dual_clock_mismatch", None
    except Exception:
        # A corrupt, unavailable or rolled-back root must never silently
        # downgrade the proof into "receipt checks itself".
        return False, "trusted_worldline_integrity_unavailable", None

    return True, "verified_anchored_worldline_replay", knowledge_k

"""IR-04: Resolve replay (T, K) from the authoritative Worldline journal.

A caller-controlled bitemporal_replay_receipt is not a signature and must not
confer time authority on its own. Rehydrate the same query from an independently
configured durable journal with a mounted anchor and compare the selected
evidence set, evidence-set digest, namespace, geometry, and journal generation.

The result is a journal-reconciled query, not a cryptographically signed
historical time credential. Signed cutoff provenance remains a separate gate.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping, Optional, Tuple

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _utc_iso(value: Any) -> Optional[str]:
    try:
        if not isinstance(value, str) or not value:
            return None
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            return None
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def verify_bitemporal_replay_receipt(
    receipt: Any,
    *,
    tenant_id: str,
    plot_id: str,
    geometry_sha256: str,
    worldline_namespace: str,
    worldline_service: Optional[Any] = None,
) -> Tuple[Optional[str], Optional[str], str]:
    """Return (T, K, reason) only after independent durable journal replay.

    The optional service is for isolated tests/explicit trusted dependency
    injection, NOT obtained from the receipt or user-provided context.
    """
    if (not all((tenant_id, plot_id, geometry_sha256, worldline_namespace))
            or not _HEX64.fullmatch(str(geometry_sha256))):
        return None, None, "unbound_journal_namespace_or_geometry"
    if not isinstance(receipt, dict):
        return None, None, "missing_authoritative_replay_receipt"
    if (receipt.get("contract_version") != "canonical_bitemporal_replay_receipt_v1"
            or receipt.get("replay_mode") != "bitemporal_deterministic_v1"
            or receipt.get("status") != "replayed"
            or receipt.get("tenant_id") != tenant_id
            or receipt.get("plot_id") != plot_id
            or receipt.get("geometry_hash") != geometry_sha256):
        return None, None, "replay_identity_or_contract_mismatch"

    q = receipt.get("query_parameters")
    if not isinstance(q, dict):
        return None, None, "invalid_replay_clocks"
    T = _utc_iso(q.get("observation_valid_time"))
    K = _utc_iso(q.get("knowledge_cutoff_time"))
    if not T or not K:
        return None, None, "invalid_replay_clocks"
    if receipt.get("durable_anchor_bound") is not True:
        return None, None, "unanchored_replay_receipt"
    if not isinstance(receipt.get("selected_evidence_set"), list):
        return None, None, "missing_replay_evidence_identity"

    try:
        if worldline_service is None:
            from services.agribrain.world_model.canonical_worldline import (
                CanonicalWorldlineService,
            )
            # Trusted process configuration, NEVER a root from a supplied receipt.
            worldline_service = CanonicalWorldlineService(require_durable_anchor=True)
        if (not worldline_service.durable_anchor_root
                or not worldline_service.durable_anchor_root.is_dir()):
            return None, None, "durable_journal_anchor_unavailable"

        clean_context = {
            "tenant_id": tenant_id,
            "worldline_namespace": worldline_namespace,
            "geometry_hash": geometry_sha256,
        }
        hydrated = worldline_service.hydrate_context(
            plot_id, clean_context,
            valid_time_T=T, knowledge_cutoff_K=K,
        )
        independently_replayed = hydrated.get("bitemporal_replay_receipt")
        if not isinstance(independently_replayed, Mapping):
            return None, None, "journal_replay_unavailable"

        compare_keys = (
            "contract_version", "replay_mode", "tenant_id", "plot_id",
            "geometry_hash", "selected_evidence_set", "evidence_set_digest",
            "status",
        )
        if any(receipt.get(key) != independently_replayed.get(key)
               for key in compare_keys):
            return None, None, "replay_not_reconciled_to_journal"
        fresh_q = independently_replayed.get("query_parameters", {})
        if (not isinstance(fresh_q, dict)
                or _utc_iso(fresh_q.get("observation_valid_time")) != T
                or _utc_iso(fresh_q.get("knowledge_cutoff_time")) != K):
            return None, None, "replay_query_not_reconciled_to_journal"
        if independently_replayed.get("durable_anchor_bound") is not True:
            return None, None, "journal_anchor_missing"

        # Refuse an unauthenticated future generation or nonexistent journal.
        head_gen = independently_replayed.get("journal_generation")
        claimed_gen = receipt.get("journal_generation")
        if (type(head_gen) is not int or type(claimed_gen) is not int
                or head_gen <= 0 or claimed_gen <= 0 or claimed_gen > head_gen):
            return None, None, "invalid_journal_generation"
        if (type(receipt.get("durable_anchor_generation")) is not int
                or receipt["durable_anchor_generation"] <= 0
                or receipt["durable_anchor_generation"] > head_gen):
            return None, None, "invalid_anchor_generation"

        return T, K, "verified_against_durable_worldline_journal"
    except Exception:
        # Never authorize source-space precision from a failed journal read.
        return None, None, "authoritative_journal_reconciliation_failed"

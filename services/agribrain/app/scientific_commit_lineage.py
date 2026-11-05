"""B2B-08B: independently bind HTTP scientific assessment to committed L3 state."""
from __future__ import annotations
from collections.abc import Mapping
from datetime import date
from typing import Any
from services.agribrain.layer0.mongo_irrigation_idempotency import _scope_state_id


class ScientificCommitLineageError(RuntimeError):
    """Unverifiable physical commitment; leave assessment STAGED."""


def attest_delivery_commit_lineage(
    database: Any, *, tenant_id: str, plot_id: str,
    geometry_hash: str, geometry_version: int, provenance_log: Any,
) -> list[dict[str, Any]]:
    """Verify server-produced Kalman provenance against exact Mongo commits.

    Does not consume receipts, issue authority, or grant publication/actuation.
    No receipt identifiers are accepted from the caller's HTTP payload.
    """
    if not isinstance(provenance_log, list):
        raise ScientificCommitLineageError("missing_kalman_provenance")
    if (not all(isinstance(x, str) and x for x in
                (tenant_id, plot_id, geometry_hash))
            or type(geometry_version) is not int or geometry_version <= 0):
        raise ScientificCommitLineageError("invalid_commit_scope")
    links = []
    seen_day_zones = set()
    seen_receipts = set()
    seen_evidence = set()
    for daily in provenance_log:
        if not isinstance(daily, Mapping):
            raise ScientificCommitLineageError("invalid_daily_provenance")
        day = daily.get("day")
        try:
            if (not isinstance(day, str) or len(day) != 10
                    or date.fromisoformat(day).isoformat() != day):
                raise ValueError("not a canonical day")
        except ValueError:
            raise ScientificCommitLineageError("invalid_commit_day") from None
        zones = daily.get("zones")
        if not isinstance(zones, Mapping):
            raise ScientificCommitLineageError("missing_zone_provenance")
        for zone_id, zoned in zones.items():
            if (not isinstance(zone_id, str) or not zone_id
                    or not isinstance(zoned, Mapping)
                    or not isinstance(zoned.get("provenance"), Mapping)):
                raise ScientificCommitLineageError("invalid_zone_provenance")
            if (day, zone_id) in seen_day_zones:
                raise ScientificCommitLineageError("duplicate_day_zone")
            seen_day_zones.add((day, zone_id))
            prov = zoned["provenance"]
            receipt_ids = prov.get("verified_delivery_receipts", [])
            applied = prov.get("physical_management_events_applied", 0)
            recovered = prov.get("recovered_from_durable_l3_commit", False)
            if (not isinstance(receipt_ids, list)
                    or any(not isinstance(x, str) or not x for x in receipt_ids)
                    or len(set(receipt_ids)) != len(receipt_ids)
                    or type(applied) is not int or applied < 0
                    or type(recovered) is not bool):
                raise ScientificCommitLineageError("invalid_delivery_provenance")
            if not receipt_ids:
                if applied or recovered:
                    raise ScientificCommitLineageError("unmatched_delivery_claim")
                continue
            if recovered:
                if (applied != 0 or prov.get("event_forcing_status")
                        != "RECOVERED_COMMITTED_CHECKPOINT"):
                    raise ScientificCommitLineageError("invalid_recovery_claim")
            elif applied != len(receipt_ids) or prov.get("event_forcing_status") != "APPLIED":
                raise ScientificCommitLineageError("invalid_application_claim")
            if any(x in seen_receipts for x in receipt_ids):
                raise ScientificCommitLineageError("receipt_reused_across_days")
            scope = {
                "tenant_id": tenant_id, "plot_id": plot_id, "zone_id": zone_id,
                "geometry_hash": geometry_hash, "geometry_version": geometry_version,
                "day": day,
            }
            snapshot_id = _scope_state_id(scope)
            state = database["Layer0IrrigationCommittedState"].find_one(
                {"_id": snapshot_id}
            )
            if (not isinstance(state, Mapping)
                    or any(state.get(k) != v for k, v in scope.items())
                    or state.get("receipt_ids") != receipt_ids
                    or not isinstance(state.get("state"), Mapping)
                    or state["state"].get("day") != day):
                raise ScientificCommitLineageError("durable_state_scope_mismatch")
            evidence = []
            for receipt_id in receipt_ids:
                row = database["Layer0IrrigationReceiptConsumption"].find_one({
                    "_id": receipt_id, "state_snapshot_id": snapshot_id,
                    "status": "COMMITTED",
                })
                if (not isinstance(row, Mapping)
                        or any(row.get(k) != v for k, v in scope.items())
                        or row.get("state_snapshot_id") != snapshot_id
                        or row.get("status") != "COMMITTED"):
                    raise ScientificCommitLineageError("durable_receipt_scope_mismatch")
                fingerprint = row.get("evidence_fingerprint")
                if not isinstance(fingerprint, str) or not fingerprint:
                    raise ScientificCommitLineageError("legacy_unfingerprinted_receipt")
                if fingerprint in seen_evidence:
                    raise ScientificCommitLineageError("duplicate_physical_evidence")
                seen_receipts.add(receipt_id)
                seen_evidence.add(fingerprint)
                evidence.append(fingerprint)
            links.append({
                "day": day, "zone_id": zone_id, "state_snapshot_id": snapshot_id,
                "receipt_ids": list(receipt_ids),
                "evidence_fingerprints": evidence,
                "recovered_from_durable_l3_commit": recovered,
            })
    return links

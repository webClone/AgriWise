"""B2B-08 Operational Recovery, Staged Assessment Reconciliation & Legacy Quarantine.

Provides controlled administrative utilities for Layer 0 operational operators:
  1. Audit and reconciliation of crash-left / ambiguous STAGED assessments:
     - Never silently deletes or automatically retries STAGED claims.
     - Scoped specifically to the submitted receipts of THAT assessment (never blindly
       touches other assessments sharing the same plot).
     - Independently verifies receipt scope match (tenant, plot, geometry, day) before any mutation.
     - Cryptographically authenticates the operator identity and authorization token against
       an independent server authority secret.
     - Executes receipt updates, assessment compare-and-set, and audit metadata in a single
       atomic MongoDB transaction session with fail-closed rollback.
     - For COMPLETE_RECONCILED: verifies exact durable state snapshot and receipt set lineage.
  2. Audit, quarantine, and migration of legacy pre-B2B-08 receipt records:
     - Discovers receipts lacking independent 'evidence_fingerprint'.
     - Applies strict quarantine markers preventing legacy records from corrupting
       modern unique evidence partial indexes.
     - Migration validates exact scope (never inventing default zone/version), authenticates
       historical evidence roots, and reuses the EXACT production canonical JSON fingerprint
       algorithm matching physical_evidence_fingerprint.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from services.agribrain.layer0.verified_irrigation_contract import (
    _parse_iso_utc,
    physical_evidence_fingerprint,
)

UTC = timezone.utc


class OperationalReconciliationError(RuntimeError):
    """Raised on invalid operational action, unverified state, or missing authorization."""


def get_trusted_reconciliation_secret(supplied_secret: Optional[str] = None) -> str:
    """Retrieve trusted reconciliation HMAC secret from server authority environment or injection.
    
    Prevents caller from self-authorizing actions with their own unverified secret.
    """
    server_secret = os.environ.get("AKALORIS_RECONCILIATION_HMAC_SECRET", "").strip()
    if not server_secret:
        raise OperationalReconciliationError("unconfigured_reconciliation_authority_secret")
    if supplied_secret is not None and not hmac.compare_digest(supplied_secret, server_secret):
        raise OperationalReconciliationError("caller_secret_mismatch_with_server_authority")
    return server_secret


def compute_operator_authorization_signature(
    operator_principal: str,
    action: str,
    assessment_id: str,
    timestamp_str: str,
    secret: str,
) -> str:
    """Compute HMAC-SHA256 signature over operator action parameters."""
    msg = f"{operator_principal}:{action}:{assessment_id}:{timestamp_str}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_operator_authorization(
    operator_principal: str,
    action: str,
    assessment_id: str,
    timestamp_str: str,
    signature: str,
    secret: str,
    *,
    now: Optional[datetime] = None,
) -> None:
    """Validate operator cryptographic authorization and timestamp freshness (max 5m skew)."""
    if not operator_principal or not isinstance(operator_principal, str):
        raise OperationalReconciliationError("operator_principal_required")
    if not secret:
        raise OperationalReconciliationError("operator_secret_required")
    if not signature or not isinstance(signature, str):
        raise OperationalReconciliationError("authorization_signature_required")
        
    try:
        ts_dt = _parse_iso_utc(timestamp_str)
    except Exception as e:
        raise OperationalReconciliationError("invalid_authorization_timestamp") from e
        
    now_dt = now or datetime.now(UTC)
    skew = abs((now_dt - ts_dt).total_seconds())
    if skew > 300.0:
        raise OperationalReconciliationError("authorization_timestamp_expired")
        
    expected_sig = compute_operator_authorization_signature(
        operator_principal, action, assessment_id, timestamp_str, secret,
    )
    if not hmac.compare_digest(signature, expected_sig):
        raise OperationalReconciliationError("operator_authorization_signature_invalid")


@dataclass(frozen=True)
class StagedAssessmentAuditReport:
    assessment_id: str
    tenant_id: str
    plot_id: str
    created_at: str
    disposition: str
    submitted_receipt_ids: List[str]
    staged_reservations_count: int
    committed_reservations_count: int
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "tenant_id": self.tenant_id,
            "plot_id": self.plot_id,
            "created_at": self.created_at,
            "disposition": self.disposition,
            "submitted_receipt_ids": self.submitted_receipt_ids,
            "staged_reservations_count": self.staged_reservations_count,
            "committed_reservations_count": self.committed_reservations_count,
            "details": self.details,
        }


def audit_staged_assessments(db: Any) -> List[StagedAssessmentAuditReport]:
    """Scan and audit all assessments currently in STAGED status.
    
    Read-only audit: correlates receipts specifically by submitted_receipt_ids
    and validates scope consistency to avoid confusing independent assessments.
    """
    if db is None or not callable(getattr(db, "command", None)):
        raise TypeError("connected_mongodb_required")
        
    assessments_coll = db["Layer0ScientificAssessment"]
    receipts_coll = db["Layer0IrrigationReceiptConsumption"]
    
    reports = []
    staged_cursor = assessments_coll.find({"status": "STAGED"})
    
    for doc in staged_cursor:
        assess_id = str(doc.get("assessment_id") or doc.get("_id"))
        tenant_id = str(doc.get("tenant_id") or "")
        plot_id = str(doc.get("plot_id") or "")
        created_at = str(doc.get("started_at") or doc.get("created_at") or "")
        submitted_ids = list(doc.get("submitted_receipt_ids") or [])
        
        # Correlate ONLY receipts submitted by this assessment
        if submitted_ids:
            staged_receipts = list(receipts_coll.find({
                "_id": {"$in": submitted_ids},
                "status": "STAGED",
            }))
            committed_receipts = list(receipts_coll.find({
                "_id": {"$in": submitted_ids},
                "status": "COMMITTED",
            }))
        else:
            staged_receipts = []
            committed_receipts = []
        
        if not submitted_ids or (not staged_receipts and not committed_receipts):
            disposition = "CLEAN_STAGED_NO_RESERVATIONS"
        elif staged_receipts and not committed_receipts:
            disposition = "STRANDED_UNCOMMITTED_RESERVATIONS"
        elif committed_receipts and len(committed_receipts) == len(submitted_ids):
            disposition = "DURABLE_COMMIT_READY_FOR_RECONCILIATION"
        elif committed_receipts:
            disposition = "PARTIAL_COMMIT_INCONSISTENCY"
        else:
            disposition = "AMBIGUOUS_MANUAL_REVIEW_REQUIRED"
            
        reports.append(StagedAssessmentAuditReport(
            assessment_id=assess_id,
            tenant_id=tenant_id,
            plot_id=plot_id,
            created_at=created_at,
            disposition=disposition,
            submitted_receipt_ids=submitted_ids,
            staged_reservations_count=len(staged_receipts),
            committed_reservations_count=len(committed_receipts),
            details={
                "staged_receipt_ids": [r["_id"] for r in staged_receipts],
                "committed_receipt_ids": [r["_id"] for r in committed_receipts],
            },
        ))
        
    return reports


def reconcile_staged_assessment(
    db: Any,
    assessment_id: str,
    action: str,
    *,
    operator_principal: str,
    rationale: str,
    authorization_signature: str,
    secret: Optional[str] = None,
    authorization_timestamp: Optional[str] = None,
    now: Optional[datetime] = None,
    expected_claim_nonce: Optional[str] = None,
    _before_cas_hook: Optional[Callable[[Any, Mapping[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Execute controlled administrative reconciliation of a STAGED assessment.
    
    Security Controls:
      - Authenticates operator_principal via authorization_signature against trusted server secret.
      - Uses exact submitted_receipt_ids scoping; never affects other assessments on the plot.
      - Validates that every submitted receipt matches assessment scope before mutation.
      - Executes receipt updates, assessment compare-and-set, and audit metadata in a single
        atomic MongoDB multi-document transaction with automatic rollback on CAS failure.
      - For COMPLETE_RECONCILED: validates that state snapshot receipt set exactly matches submitted_ids
        and reconstructs complete scientific provenance.
    """
    now_dt = now or datetime.now(UTC)
    iso_now = now_dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    auth_ts = authorization_timestamp or iso_now
    
    # 1. Independent Server Secret Authority & Cryptographic Operator Authorization
    effective_secret = get_trusted_reconciliation_secret(secret)
    verify_operator_authorization(
        operator_principal, action, assessment_id, auth_ts, authorization_signature, effective_secret, now=now_dt,
    )
    if not rationale or len(rationale.strip()) < 10:
        raise OperationalReconciliationError("valid_rationale_min_10_chars_required")
        
    assessments_coll = db["Layer0ScientificAssessment"]
    receipts_coll = db["Layer0IrrigationReceiptConsumption"]
    states_coll = db["Layer0IrrigationCommittedState"]
    
    doc = assessments_coll.find_one({"assessment_id": assessment_id})
    if not doc:
        doc = assessments_coll.find_one({"_id": assessment_id})
    if not doc:
        raise OperationalReconciliationError(f"assessment_{assessment_id}_not_found")
    if doc.get("status") != "STAGED":
        raise OperationalReconciliationError(f"assessment_status_not_staged: {doc.get('status')}")
        
    claim_nonce = expected_claim_nonce or doc.get("claim_nonce")
    if expected_claim_nonce and doc.get("claim_nonce") != expected_claim_nonce:
        raise OperationalReconciliationError("concurrent_assessment_mutation_detected")
    submitted_ids = list(doc.get("submitted_receipt_ids") or [])
    receipt_digests = doc.get("submitted_receipt_digests")
    if (len(submitted_ids) != len(set(submitted_ids))
            or not isinstance(receipt_digests, Mapping)
            or set(receipt_digests) != set(submitted_ids)):
        raise OperationalReconciliationError("unverified_assessment_receipt_manifest")
    start_day = doc.get("assessment_start_date") or doc.get("day")
    end_day = doc.get("assessment_end_date") or doc.get("day")
    if submitted_ids and (
        not isinstance(start_day, str) or not isinstance(end_day, str)
        or start_day > end_day
    ):
        raise OperationalReconciliationError("unverified_assessment_temporal_window")

    audit_entry = {
        "reconciled_at": iso_now,
        "operator": operator_principal,
        "rationale": rationale,
        "action": action,
        "authorization_timestamp": auth_ts,
    }

    # 3. Transactional Execution: Atomic CAS + Receipt Mutation
    client = getattr(db, "client", None)
    has_tx = client is not None and callable(getattr(client, "start_session", None))
    if not has_tx:
        raise OperationalReconciliationError("transactional_mongodb_required")

    def _execute_within_session(session):
        sess_kw = {"session": session}

        # All proof checks participate in the same transaction as the CAS.
        # A receipt for the same plot but a different scientific assessment
        # cannot be reassigned or rolled back by this operator procedure.
        for r_id in submitted_ids:
            r_doc = receipts_coll.find_one({"_id": r_id}, **sess_kw)
            if r_doc is None:
                raise OperationalReconciliationError(f"unresolved_submitted_receipt: {r_id}")
            for k in ("tenant_id", "plot_id", "geometry_hash", "geometry_version"):
                if r_doc.get(k) != doc.get(k):
                    raise OperationalReconciliationError(
                        f"receipt_scope_mismatch_with_assessment: {r_id} {k}"
                    )
            if r_doc.get("assessment_claim_id") != doc["_id"]:
                raise OperationalReconciliationError(f"receipt_not_bound_to_assessment: {r_id}")
            if (not isinstance(receipt_digests[r_id], str)
                    or r_doc.get("grant_digest") != receipt_digests[r_id]):
                raise OperationalReconciliationError(f"receipt_grant_digest_mismatch: {r_id}")
            day = r_doc.get("day")
            if not isinstance(day, str) or not (start_day <= day <= end_day):
                raise OperationalReconciliationError(f"receipt_day_mismatch: {r_id}")

        if action == "ABORT_AND_ROLLBACK":
            modified_count = 0
            if submitted_ids:
                res = receipts_coll.update_many(
                    {"_id": {"$in": submitted_ids}, "status": "STAGED"},
                    {"$set": {
                        "status": "ROLLED_BACK",
                        "rolled_back_at": iso_now,
                        "rolled_back_by": operator_principal,
                        "reconciled_assessment_id": assessment_id,
                    }},
                    **sess_kw,
                )
                modified_count = res.modified_count
                
            if callable(_before_cas_hook):
                _before_cas_hook(session, doc)

            cas_res = assessments_coll.update_one(
                {"_id": doc["_id"], "status": "STAGED", "claim_nonce": claim_nonce},
                {"$set": {"status": "ABORTED", "reconciliation_audit": audit_entry}},
                **sess_kw,
            )
            if cas_res.matched_count != 1:
                raise OperationalReconciliationError("concurrent_assessment_mutation_detected")
                
            return {
                "assessment_id": assessment_id,
                "status": "ABORTED",
                "reservations_rolled_back": modified_count,
                "audit": audit_entry,
            }
            
        elif action == "COMPLETE_RECONCILED":
            if not submitted_ids:
                raise OperationalReconciliationError("cannot_complete_assessment_without_submitted_receipts")
                
            committed_rows = list(receipts_coll.find({
                "_id": {"$in": submitted_ids},
                "status": "COMMITTED",
            }, **sess_kw))
            if len(committed_rows) != len(submitted_ids):
                raise OperationalReconciliationError("cannot_complete_unconfirmed_receipt_commit")
                
            snapshot_ids = {r.get("state_snapshot_id") for r in committed_rows}
            if len(snapshot_ids) != 1 or None in snapshot_ids:
                raise OperationalReconciliationError("inconsistent_state_snapshot_linkage")
            snapshot_id = snapshot_ids.pop()
            
            state_doc = states_coll.find_one({"_id": snapshot_id}, **sess_kw)
            if not state_doc:
                raise OperationalReconciliationError("referenced_state_snapshot_missing")
                
            for k in ("tenant_id", "plot_id", "geometry_hash", "geometry_version"):
                if state_doc.get(k) != doc.get(k):
                    raise OperationalReconciliationError(f"scope_mismatch_on_{k}")

            # Verify snapshot's receipt set matches submitted_ids exactly
            snap_rcpts = set(state_doc.get("receipt_ids") or [])
            if snap_rcpts != set(submitted_ids):
                raise OperationalReconciliationError("snapshot_receipt_set_mismatch")
                    
            reconstructed_summary = {
                "assessment_id": assessment_id,
                "reconciled_from_snapshot_id": snapshot_id,
                "state": state_doc.get("state"),
                "covariance": state_doc.get("covariance"),
                "day": state_doc.get("day"),
                "zone_id": state_doc.get("zone_id", "plot"),
                "verified_delivery_commits": [{
                    "state_snapshot_id": snapshot_id,
                    "receipt_ids": submitted_ids,
                    "evidence_fingerprints": [r.get("evidence_fingerprint") for r in committed_rows],
                    "recovered_from_durable_l3_commit": True,
                }],
                "verified_delivery_receipt_count": len(submitted_ids),
                "scientific_publication_authorized": False,
                "actuator_control_authorized": False,
            }
            
            cas_res = assessments_coll.update_one(
                {"_id": doc["_id"], "status": "STAGED", "claim_nonce": claim_nonce},
                {"$set": {
                    "status": "COMMITTED",
                    "result": reconstructed_summary,
                    "reconciliation_audit": audit_entry,
                }},
                **sess_kw,
            )
            if cas_res.matched_count != 1:
                raise OperationalReconciliationError("concurrent_assessment_mutation_detected")
                
            return {
                "assessment_id": assessment_id,
                "status": "COMMITTED",
                "audit": audit_entry,
                "result": reconstructed_summary,
            }
        else:
            raise OperationalReconciliationError(f"unsupported_action: {action}")

    if has_tx:
        try:
            with client.start_session() as session:
                with session.start_transaction():
                    return _execute_within_session(session)
        except Exception as exc:
            if isinstance(exc, OperationalReconciliationError):
                raise
            if "WriteConflict" in str(exc) or "TransientTransactionError" in str(exc):
                raise OperationalReconciliationError("concurrent_assessment_mutation_detected") from exc
            raise OperationalReconciliationError(f"reconciliation_transaction_failed: {exc}") from exc
    raise OperationalReconciliationError("transactional_mongodb_required")


def scan_unfingerprinted_legacy_receipts(db: Any) -> List[Dict[str, Any]]:
    """Scan and list legacy pre-B2B-08 receipt consumption records lacking evidence fingerprints."""
    if db is None or not callable(getattr(db, "command", None)):
        raise TypeError("connected_mongodb_required")
        
    receipts_coll = db["Layer0IrrigationReceiptConsumption"]
    cursor = receipts_coll.find({
        "$or": [
            {"evidence_fingerprint": {"$exists": False}},
            {"evidence_fingerprint": None},
            {"evidence_fingerprint": ""},
        ]
    })
    return list(cursor)


def quarantine_legacy_receipts(
    db: Any,
    *,
    operator_principal: str,
    rationale: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Quarantine all legacy receipt consumption records lacking valid evidence fingerprints."""
    if not operator_principal:
        raise OperationalReconciliationError("operator_principal_required")
    if not rationale:
        raise OperationalReconciliationError("rationale_required")
        
    now_dt = now or datetime.now(UTC)
    iso_now = now_dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    
    receipts_coll = db["Layer0IrrigationReceiptConsumption"]
    res = receipts_coll.update_many(
        {
            "$or": [
                {"evidence_fingerprint": {"$exists": False}},
                {"evidence_fingerprint": None},
                {"evidence_fingerprint": ""},
            ],
            "quarantine_status": {"$ne": "QUARANTINED"},
        },
        {
            "$set": {
                "quarantine_status": "QUARANTINED",
                "quarantined_at": iso_now,
                "quarantined_by": operator_principal,
                "quarantine_rationale": rationale,
            }
        },
    )
    return {
        "quarantined_count": res.modified_count,
        "operator": operator_principal,
        "timestamp": iso_now,
    }


def migrate_legacy_receipt_evidence_fingerprint(
    db: Any,
    receipt_id: str,
    *,
    source_evidence_cas_root: str,
    delivery_interval: Tuple[str, str],
    operator_principal: str,
    rationale: str,
    evidence_authenticator: Optional[Callable[[str, Tuple[str, str], Mapping[str, Any]], bool]] = None,
) -> Dict[str, Any]:
    """Migrate a single verified historical receipt by populating its evidence fingerprint.
    
    Security Controls:
      - Validates exact historical scope (tenant_id, plot_id, zone_id, geometry_hash, geometry_version)
        without inventing fallback defaults.
      - Enforces delivery interval validity (end > start, duration <= 24h) and checks consistency
        against existing receipt delivery fields if present.
      - Validates source_evidence_cas_root format and checks consistency against existing receipt.
      - Executes optional independent historical evidence authenticator callback.
      - Reuses the EXACT production canonical JSON fingerprint algorithm
        (matching physical_evidence_fingerprint), guaranteeing cross-version
        duplicate-evidence protection against newly re-issued grants.
    """
    if not receipt_id or not source_evidence_cas_root or len(delivery_interval) != 2:
        raise OperationalReconciliationError("invalid_migration_parameters")
        
    receipts_coll = db["Layer0IrrigationReceiptConsumption"]
    rec = receipts_coll.find_one({"_id": receipt_id})
    if not rec:
        raise OperationalReconciliationError(f"receipt_{receipt_id}_not_found")
        
    # 1. Exact scope validation without inventing fallbacks
    for key in ("tenant_id", "plot_id", "zone_id", "geometry_hash", "geometry_version"):
        val = rec.get(key)
        if val is None or val == "":
            raise OperationalReconciliationError(f"unverifiable_legacy_record_missing_{key}")

    # 2. Delivery interval validation & consistency
    start_iso, end_iso = delivery_interval
    try:
        start_dt = _parse_iso_utc(start_iso)
        end_dt = _parse_iso_utc(end_iso)
    except Exception as e:
        raise OperationalReconciliationError("invalid_delivery_interval_timestamp") from e

    if end_dt <= start_dt:
        raise OperationalReconciliationError("invalid_delivery_interval_end_must_exceed_start")
    if (end_dt - start_dt).total_seconds() > 86400.0:
        raise OperationalReconciliationError("invalid_delivery_interval_duration_exceeds_24h")

    if not rec.get("delivery_start") or not rec.get("delivery_end"):
        raise OperationalReconciliationError("unverifiable_historical_delivery_interval")
    rec_start_dt = _parse_iso_utc(rec["delivery_start"])
    rec_end_dt = _parse_iso_utc(rec["delivery_end"])
    if rec_start_dt != start_dt or rec_end_dt != end_dt:
        raise OperationalReconciliationError("delivery_interval_mismatch_with_historical_receipt")

    # 3. Evidence root validation & consistency
    if len(source_evidence_cas_root) < 16:
        raise OperationalReconciliationError("invalid_source_evidence_cas_root_format")
    if not rec.get("source_evidence_cas_root"):
        raise OperationalReconciliationError("unverifiable_historical_evidence_root")
    if rec["source_evidence_cas_root"] != source_evidence_cas_root:
        raise OperationalReconciliationError("evidence_cas_root_mismatch_with_historical_receipt")

    # 4. Authentication is mandatory. The trusted operator runtime must
    # supply an evidence verifier; a bare CAS string does not prove origin.
    if not callable(evidence_authenticator):
        raise OperationalReconciliationError("historical_evidence_authenticator_required")
    try:
        if evidence_authenticator(source_evidence_cas_root, delivery_interval, rec) is not True:
            raise OperationalReconciliationError("historical_evidence_unauthenticated")
    except Exception as e:
        if isinstance(e, OperationalReconciliationError):
            raise
        raise OperationalReconciliationError("historical_evidence_authentication_failed") from e

    start_utc = start_dt.isoformat()
    end_utc = end_dt.isoformat()
    
    # Exact production algorithm: sorted JSON dictionary over normalized fields
    fields = {
        "tenant_id": str(rec["tenant_id"]),
        "plot_id": str(rec["plot_id"]),
        "zone_id": str(rec["zone_id"]),
        "geometry_hash": str(rec["geometry_hash"]),
        "geometry_version": int(rec["geometry_version"]),
        "source_evidence_cas_root": str(source_evidence_cas_root),
        "delivery_start": start_utc,
        "delivery_end": end_utc,
    }
    computed_fingerprint = hashlib.sha256(
        json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    
    receipts_coll.update_one(
        {"_id": receipt_id},
        {
            "$set": {
                "evidence_fingerprint": computed_fingerprint,
                "source_evidence_cas_root": source_evidence_cas_root,
                "delivery_start": start_utc,
                "delivery_end": end_utc,
                "migration_status": "MIGRATED",
                "migrated_by": operator_principal,
                "migration_rationale": rationale,
            },
            "$unset": {"quarantine_status": ""},
        },
    )
    return {
        "receipt_id": receipt_id,
        "evidence_fingerprint": computed_fingerprint,
        "migration_status": "MIGRATED",
    }

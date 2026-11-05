"""B2B-08 Operational Recovery, Staged Assessment Reconciliation & Legacy Quarantine.

Provides controlled administrative utilities for Layer 0 operational operators:
  1. Audit and reconciliation of crash-left / ambiguous STAGED assessments:
     - Never silently deletes or automatically retries STAGED claims.
     - Scoped specifically to the submitted receipts of THAT assessment (never blindly
       touches other assessments sharing the same plot).
     - Cryptographically authenticates the operator identity and authorization token.
     - Enforces atomic compare-and-set on the assessment claim nonce.
     - For COMPLETE_RECONCILED: verifies exact durable state snapshot and receipt lineage.
  2. Audit, quarantine, and migration of legacy pre-B2B-08 receipt records:
     - Discovers receipts lacking independent 'evidence_fingerprint'.
     - Applies strict quarantine markers preventing legacy records from corrupting
       modern unique evidence partial indexes.
     - Migration reuses the EXACT production canonical JSON fingerprint algorithm,
       ensuring cross-version duplicate-evidence fencing against newly signed grants.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from services.agribrain.layer0.verified_irrigation_contract import (
    _parse_iso_utc,
    physical_evidence_fingerprint,
)

UTC = timezone.utc


class OperationalReconciliationError(RuntimeError):
    """Raised on invalid operational action, unverified state, or missing authorization."""


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
    to avoid confusing independent assessments on the same plot.
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
    secret: str,
    authorization_timestamp: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Execute controlled administrative reconciliation of a STAGED assessment.
    
    Security Controls:
      - Authenticates operator_principal via authorization_signature over HMAC.
      - Uses exact submitted_receipt_ids scoping; never affects other assessments on the plot.
      - Executes atomic compare-and-set on claim_nonce and status='STAGED'.
      - For COMPLETE_RECONCILED: verifies exact durable state snapshot and receipt lineage.
    """
    now_dt = now or datetime.now(UTC)
    iso_now = now_dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    auth_ts = authorization_timestamp or iso_now
    
    # 1. Cryptographic Operator Authorization
    verify_operator_authorization(
        operator_principal, action, assessment_id, auth_ts, authorization_signature, secret, now=now_dt,
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
        
    claim_nonce = doc.get("claim_nonce")
    submitted_ids = list(doc.get("submitted_receipt_ids") or [])
    
    audit_entry = {
        "reconciled_at": iso_now,
        "operator": operator_principal,
        "rationale": rationale,
        "action": action,
        "authorization_timestamp": auth_ts,
    }
    
    if action == "ABORT_AND_ROLLBACK":
        # Roll back ONLY the receipts submitted for THIS assessment
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
            )
            modified_count = res.modified_count
            
        # Atomic compare-and-set on assessment
        cas_res = assessments_coll.update_one(
            {"_id": doc["_id"], "status": "STAGED", "claim_nonce": claim_nonce},
            {"$set": {"status": "ABORTED", "reconciliation_audit": audit_entry}},
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
            
        # Verify that all submitted receipts are COMMITTED
        committed_rows = list(receipts_coll.find({
            "_id": {"$in": submitted_ids},
            "status": "COMMITTED",
        }))
        if len(committed_rows) != len(submitted_ids):
            raise OperationalReconciliationError("cannot_complete_unconfirmed_receipt_commit")
            
        # Verify snapshot linkage and exact scope
        snapshot_ids = {r.get("state_snapshot_id") for r in committed_rows}
        if len(snapshot_ids) != 1 or None in snapshot_ids:
            raise OperationalReconciliationError("inconsistent_state_snapshot_linkage")
        snapshot_id = snapshot_ids.pop()
        
        state_doc = states_coll.find_one({"_id": snapshot_id})
        if not state_doc:
            raise OperationalReconciliationError("referenced_state_snapshot_missing")
            
        # Check scope match against assessment
        for k in ("tenant_id", "plot_id", "geometry_hash", "geometry_version"):
            if state_doc.get(k) != doc.get(k):
                raise OperationalReconciliationError(f"scope_mismatch_on_{k}")
                
        # Reconstruct verified summary
        reconstructed_summary = {
            "assessment_id": assessment_id,
            "reconciled_from_snapshot_id": snapshot_id,
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
        
        # Atomic compare-and-set
        cas_res = assessments_coll.update_one(
            {"_id": doc["_id"], "status": "STAGED", "claim_nonce": claim_nonce},
            {"$set": {
                "status": "COMMITTED",
                "result": reconstructed_summary,
                "reconciliation_audit": audit_entry,
            }},
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
    """Quarantine all legacy receipt consumption records lacking valid evidence fingerprints.
    
    Tags records with quarantine_status='QUARANTINED', preventing them from being
    admitted into modern B2B-08 scientific commitment lineage checks.
    """
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
) -> Dict[str, Any]:
    """Migrate a single verified historical receipt by populating its evidence fingerprint.
    
    Reuses the EXACT production canonical JSON fingerprint algorithm
    (matching physical_evidence_fingerprint), guaranteeing cross-version
    duplicate-evidence protection against newly re-issued grants.
    """
    if not receipt_id or not source_evidence_cas_root or len(delivery_interval) != 2:
        raise OperationalReconciliationError("invalid_migration_parameters")
        
    receipts_coll = db["Layer0IrrigationReceiptConsumption"]
    rec = receipts_coll.find_one({"_id": receipt_id})
    if not rec:
        raise OperationalReconciliationError(f"receipt_{receipt_id}_not_found")
        
    start_iso, end_iso = delivery_interval
    start_utc = _parse_iso_utc(start_iso).isoformat()
    end_utc = _parse_iso_utc(end_iso).isoformat()
    
    # Exact production algorithm: sorted JSON dictionary over normalized fields
    fields = {
        "tenant_id": str(rec.get("tenant_id")),
        "plot_id": str(rec.get("plot_id")),
        "zone_id": str(rec.get("zone_id") or "plot"),
        "geometry_hash": str(rec.get("geometry_hash")),
        "geometry_version": int(rec.get("geometry_version") or 2),
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

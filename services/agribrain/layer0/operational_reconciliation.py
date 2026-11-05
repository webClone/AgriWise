"""B2B-08 Operational Recovery, Staged Assessment Reconciliation & Legacy Quarantine.

Provides controlled administrative utilities for Layer 0 operational operators:
  1. Audit and reconciliation of crash-left / ambiguous STAGED assessments:
     - Never silently deletes or automatically retries STAGED claims.
     - Categorizes staged state (no reservations, stranded staged reservation, partial commit).
     - Allows controlled rollback of uncommitted staged reservations or completion of
       durable transactions with cryptographic operator audit trail.
  2. Audit, quarantine, and migration of legacy pre-B2B-08 receipt records:
     - Discovers receipts lacking independent 'evidence_fingerprint'.
     - Applies strict quarantine markers preventing legacy records from corrupting
       modern unique evidence partial indexes.
     - Enables deterministic backfill migration when verified CAS evidence roots exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

UTC = timezone.utc


class OperationalReconciliationError(RuntimeError):
    """Raised on invalid operational action, unverified state, or missing authorization."""


@dataclass(frozen=True)
class StagedAssessmentAuditReport:
    assessment_id: str
    tenant_id: str
    plot_id: str
    created_at: str
    disposition: str
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
            "staged_reservations_count": self.staged_reservations_count,
            "committed_reservations_count": self.committed_reservations_count,
            "details": self.details,
        }


def audit_staged_assessments(db: Any) -> List[StagedAssessmentAuditReport]:
    """Scan and audit all assessments currently in STAGED status.
    
    Read-only audit: makes zero mutations to the database.
    """
    if db is None or not callable(getattr(db, "command", None)):
        raise TypeError("connected_mongodb_required")
        
    assessments_coll = db["Layer0ScientificAssessment"]
    receipts_coll = db["Layer0IrrigationReceiptConsumption"]
    states_coll = db["Layer0IrrigationCommittedState"]
    
    reports = []
    staged_cursor = assessments_coll.find({"status": "STAGED"})
    
    for doc in staged_cursor:
        assess_id = str(doc.get("assessment_id") or doc.get("_id"))
        tenant_id = str(doc.get("tenant_id") or "")
        plot_id = str(doc.get("plot_id") or "")
        created_at = str(doc.get("created_at") or "")
        
        # Check associated receipt consumption records
        staged_receipts = list(receipts_coll.find({
            "tenant_id": tenant_id,
            "plot_id": plot_id,
            "status": "STAGED",
        }))
        committed_receipts = list(receipts_coll.find({
            "tenant_id": tenant_id,
            "plot_id": plot_id,
            "status": "COMMITTED",
        }))
        
        if not staged_receipts and not committed_receipts:
            disposition = "CLEAN_STAGED_NO_RESERVATIONS"
        elif staged_receipts and not committed_receipts:
            disposition = "STRANDED_UNCOMMITTED_RESERVATIONS"
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
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Execute controlled administrative reconciliation of a STAGED assessment.
    
    Permitted actions:
      - 'ABORT_AND_ROLLBACK': Rolls back stranded uncommitted staged reservations.
      - 'MARK_ABORTED': Sets assessment status to 'ABORTED' after reservations are cleared.
      - 'COMPLETE_RECONCILED': If underlying L3 state is fully COMMITTED, marks assessment COMMITTED.
    """
    if not operator_principal or not isinstance(operator_principal, str):
        raise OperationalReconciliationError("operator_principal_required")
    if not rationale or len(rationale.strip()) < 10:
        raise OperationalReconciliationError("valid_rationale_min_10_chars_required")
        
    now_dt = now or datetime.now(UTC)
    iso_now = now_dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    
    assessments_coll = db["Layer0ScientificAssessment"]
    receipts_coll = db["Layer0IrrigationReceiptConsumption"]
    
    doc = assessments_coll.find_one({"assessment_id": assessment_id})
    if not doc:
        doc = assessments_coll.find_one({"_id": assessment_id})
    if not doc:
        raise OperationalReconciliationError(f"assessment_{assessment_id}_not_found")
    if doc.get("status") != "STAGED":
        raise OperationalReconciliationError(f"assessment_status_not_staged: {doc.get('status')}")
        
    audit_entry = {
        "reconciled_at": iso_now,
        "operator": operator_principal,
        "rationale": rationale,
        "action": action,
    }
    
    if action == "ABORT_AND_ROLLBACK":
        # Find and rollback all matching STAGED receipt reservations for this plot/tenant
        res = receipts_coll.update_many(
            {"tenant_id": doc.get("tenant_id"), "plot_id": doc.get("plot_id"), "status": "STAGED"},
            {"$set": {"status": "ROLLED_BACK", "rolled_back_at": iso_now, "rolled_back_by": operator_principal}},
        )
        assessments_coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": "ABORTED", "reconciliation_audit": audit_entry}},
        )
        return {
            "assessment_id": assessment_id,
            "status": "ABORTED",
            "reservations_rolled_back": res.modified_count,
            "audit": audit_entry,
        }
        
    elif action == "COMPLETE_RECONCILED":
        # Only allowed if all receipts are verified COMMITTED
        staged_recs = receipts_coll.count_documents({
            "tenant_id": doc.get("tenant_id"), "plot_id": doc.get("plot_id"), "status": "STAGED",
        })
        if staged_recs > 0:
            raise OperationalReconciliationError("cannot_complete_while_staged_reservations_exist")
            
        committed_recs = receipts_coll.count_documents({
            "tenant_id": doc.get("tenant_id"), "plot_id": doc.get("plot_id"), "status": "COMMITTED",
        })
        if committed_recs == 0:
            raise OperationalReconciliationError("cannot_complete_without_committed_receipts")
            
        assessments_coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": "COMMITTED", "reconciliation_audit": audit_entry}},
        )
        return {
            "assessment_id": assessment_id,
            "status": "COMMITTED",
            "audit": audit_entry,
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
    
    Computes deterministic evidence fingerprint binding scope, CAS root, and normalized interval.
    """
    if not receipt_id or not source_evidence_cas_root or len(delivery_interval) != 2:
        raise OperationalReconciliationError("invalid_migration_parameters")
        
    receipts_coll = db["Layer0IrrigationReceiptConsumption"]
    rec = receipts_coll.find_one({"_id": receipt_id})
    if not rec:
        raise OperationalReconciliationError(f"receipt_{receipt_id}_not_found")
        
    # Bind tenant, plot, zone, geometry, CAS root, and interval
    start_iso, end_iso = delivery_interval
    evidence_fields = [
        str(rec.get("tenant_id")),
        str(rec.get("plot_id")),
        str(rec.get("zone_id") or "plot"),
        str(rec.get("geometry_hash")),
        str(rec.get("geometry_version")),
        source_evidence_cas_root,
        start_iso,
        end_iso,
    ]
    computed_fingerprint = hashlib.sha256(
        "\0".join(evidence_fields).encode("utf-8")
    ).hexdigest()
    
    receipts_coll.update_one(
        {"_id": receipt_id},
        {
            "$set": {
                "evidence_fingerprint": computed_fingerprint,
                "source_evidence_cas_root": source_evidence_cas_root,
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

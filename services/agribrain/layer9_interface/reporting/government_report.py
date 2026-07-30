from datetime import datetime, timezone
import uuid
from typing import Dict, Any, List, Optional

from layer9_interface.reporting.schemas import (
    InstitutionalReport, ReportSubject, ReportAuditBlock, ReportDisclaimer, EvidenceWindow
)
from layer9_interface.reporting.report_registry import REPORT_SCHEMA_VERSION, REPORT_POLICY_VERSION
from layer9_interface.reporting.privacy import (
    check_k_anonymity, coarsen_coordinates, remove_owner_identity, suppress_small_cohort
)
from layer9_interface.reporting.report_hashing import (
    compute_report_content_hash, compute_report_instance_hash
)

def weighted_mean(items) -> float:
    weighted_sum = 0.0
    weight_total = 0.0
    for it in items:
        val = 0.0
        try:
            val = float(it.value)
        except (ValueError, TypeError):
            continue
        weighted_sum += val * it.confidence
        weight_total += it.confidence
    return weighted_sum / weight_total if weight_total > 0.0 else 0.0

def build_government_regional_risk(context: Dict[str, Any]) -> InstitutionalReport:
    packet = context["packet"]
    raw_plots = context.get("plots") or []
    region_id = context.get("region_id") or "UNKNOWN_REGION"
    
    # Run privacy anonymity check
    decision = check_k_anonymity(raw_plots)
    
    privacy_block = {
        "suppressed": decision.suppressed,
        "plot_count": decision.plot_count,
        "owner_count": decision.owner_count,
        "coordinate_policy": "coarsened"
    }

    # Filter items that can support government aggregate
    valid_items = [item for item in packet.classified_items if item.can_support_government_aggregate]
    has_evidence = len(valid_items) > 0 and not decision.suppressed

    if not has_evidence:
        metric_status = "suppressed" if decision.suppressed else "unknown"
        metrics = {
            "regional_risk_score": metric_status,
            "water_stressed_fraction": metric_status,
            "salinity_stressed_fraction": metric_status
        }
        confidence = 0.0
        uncertainty = 1.0
        coverage = 0.0
        limitations = ["No valid evidence available for regional risk calculation."]
    else:
        # Compute metrics dynamically
        water_items = [it for it in valid_items if "water" in it.variable.lower() or "moisture" in it.variable.lower() or "dry" in it.variable.lower()]
        salinity_items = [it for it in valid_items if "salinity" in it.variable.lower() or "salt" in it.variable.lower()]
        
        water_stressed_fraction = weighted_mean(water_items) if water_items else 0.0
        salinity_stressed_fraction = weighted_mean(salinity_items) if salinity_items else 0.0
        regional_risk_score = weighted_mean(valid_items)
        
        metrics = {
            "regional_risk_score": round(regional_risk_score, 2),
            "water_stressed_fraction": round(water_stressed_fraction, 2),
            "salinity_stressed_fraction": round(salinity_stressed_fraction, 2)
        }
        confidence = round(sum(it.confidence for it in valid_items) / len(valid_items), 2)
        uncertainty = round(max(it.uncertainty for it in valid_items), 2)
        coverage = round(len(valid_items) / len(packet.raw_items) if packet.raw_items else 0.0, 2)
        limitations = []

    if decision.suppressed:
        metrics["suppressed"] = True
        limitations = [f"Data suppressed: {decision.reason}"]

    payload = {
        "region_id": region_id,
        "privacy": privacy_block,
        "regional_metrics": metrics
    }

    disclaimers = []
    if decision.suppressed:
        disclaimers.append(
            ReportDisclaimer(
                text="⚠️ Data Suppressed: This region does not meet privacy aggregation thresholds (minimum 5 plots and 3 owners).",
                reason="privacy_suppression",
                severity="CRITICAL"
            )
        )

    # Standard warning checks for government report disclaimers
    from layer9_interface.reporting.disclaimers import prepare_standard_disclaimers
    disclaimers = prepare_standard_disclaimers(packet.classified_items, disclaimers)

    report_id = f"ir_{uuid.uuid4().hex[:8]}"
    generated_at = datetime.now(timezone.utc).isoformat()

    subj = ReportSubject(
        plot_id_hash=None,
        farm_id_hash=None,
        region_id=region_id,
        owner_identity_removed=True,
        coordinates_policy="coarse",
        aggregation_level="region"
    )

    window = EvidenceWindow(
        start_date=packet.evidence_window.get("start_date"),
        end_date=packet.evidence_window.get("end_date")
    )

    audit = ReportAuditBlock(
        generated_by="AgriWise Reporting Layer v89",
        source_layers_used=list(set(item.source_layer for item in packet.raw_items))
    )

    report_dict = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_policy_version": REPORT_POLICY_VERSION,
        "report_type": "government_regional_risk",
        "scope": "region",
        "subject": subj,
        "evidence_window": window,
        "confidence": confidence,
        "uncertainty": uncertainty,
        "data_completeness": 0.0 if decision.suppressed else packet.data_completeness,
        "evidence_tiers": {},
        "metrics": metrics,
        "payload": payload,
        "provenance_hashes": dict(packet.provenance_hashes),
        "limitations": packet.limitations + limitations,
        "disclaimers": disclaimers,
        "audit": audit,
        "reporting_only": True,
        "state_mutation_allowed": False,
        "training_allowed": False,
        "certification_allowed": False
    }

    from layer9_interface.reporting.report_hashing import compute_input_hash, compute_verified_evidence_hash
    report_dict["report_input_hash"] = compute_input_hash(packet.raw_items)
    report_dict["verified_evidence_hash"] = compute_verified_evidence_hash(packet.classified_items)
    content_h = compute_report_content_hash(report_dict)
    report_dict["report_content_hash"] = content_h
    report_dict["report_instance_hash"] = compute_report_instance_hash(report_id, generated_at, content_h)

    return InstitutionalReport(
        report_schema_version=REPORT_SCHEMA_VERSION,
        report_policy_version=REPORT_POLICY_VERSION,
        report_id=report_id,
        report_type="government_regional_risk",
        scope="region",
        generated_at=generated_at,
        subject=subj,
        evidence_window=window,
        confidence=confidence,
        uncertainty=uncertainty,
        data_completeness=report_dict["data_completeness"],
        evidence_tiers={},
        metrics=metrics,
        payload=payload,
        provenance_hashes=report_dict["provenance_hashes"],
        report_input_hash=report_dict["report_input_hash"],
        verified_evidence_hash=report_dict["verified_evidence_hash"],
        report_content_hash=content_h,
        report_instance_hash=report_dict["report_instance_hash"],
        limitations=report_dict["limitations"],
        disclaimers=disclaimers,
        audit=audit
    )

def build_government_food_security_signal(context: Dict[str, Any]) -> InstitutionalReport:
    packet = context["packet"]
    raw_plots = context.get("plots") or []
    region_id = context.get("region_id") or "UNKNOWN_REGION"
    
    # Run privacy anonymity check
    decision = check_k_anonymity(raw_plots)
    
    privacy_block = {
        "suppressed": decision.suppressed,
        "plot_count": decision.plot_count,
        "owner_count": decision.owner_count,
        "coordinate_policy": "coarsened"
    }

    # Filter items that can support government aggregate
    valid_items = [item for item in packet.classified_items if item.can_support_government_aggregate]
    has_evidence = len(valid_items) > 0 and not decision.suppressed

    if not has_evidence:
        metric_status = "suppressed" if decision.suppressed else "unknown"
        food_security_signal = {
            "crop_stress_index": metric_status,
            "water_stress_index": metric_status,
            "salinity_watch_index": metric_status,
            "confidence": 0.0,
            "coverage": 0.0
        }
        confidence = 0.0
        uncertainty = 1.0
        coverage = 0.0
        limitations = ["No valid evidence available for regional risk calculation."]
    else:
        # Compute metrics dynamically
        water_items = [it for it in valid_items if "water" in it.variable.lower() or "moisture" in it.variable.lower() or "dry" in it.variable.lower()]
        salinity_items = [it for it in valid_items if "salinity" in it.variable.lower() or "salt" in it.variable.lower()]
        crop_items = [it for it in valid_items if "stress" in it.variable.lower() or "vigor" in it.variable.lower() or "ndvi" in it.variable.lower()]
        
        water_stress_index = weighted_mean(water_items) if water_items else 0.0
        salinity_watch_index = weighted_mean(salinity_items) if salinity_items else 0.0
        crop_stress_index = weighted_mean(crop_items) if crop_items else 0.0
        
        sig_conf = sum(it.confidence for it in valid_items) / len(valid_items)
        sig_cov = len(valid_items) / len(packet.raw_items) if packet.raw_items else 0.0
        
        food_security_signal = {
            "crop_stress_index": round(crop_stress_index, 2),
            "water_stress_index": round(water_stress_index, 2),
            "salinity_watch_index": round(salinity_watch_index, 2),
            "confidence": round(sig_conf, 2),
            "coverage": round(sig_cov, 2)
        }
        confidence = round(sig_conf, 2)
        uncertainty = round(max(it.uncertainty for it in valid_items), 2)
        coverage = round(sig_cov, 2)
        limitations = []

    if decision.suppressed:
        food_security_signal["suppressed"] = True
        limitations = [f"Data suppressed: {decision.reason}"]

    payload = {
        "region_id": region_id,
        "privacy": privacy_block,
        "food_security_signal": food_security_signal
    }

    disclaimers = []
    if decision.suppressed:
        disclaimers.append(
            ReportDisclaimer(
                text="⚠️ Data Suppressed: This region does not meet privacy thresholds.",
                reason="privacy_suppression",
                severity="CRITICAL"
            )
        )

    # Standard warning checks for food security disclaimers
    from layer9_interface.reporting.disclaimers import prepare_standard_disclaimers
    disclaimers = prepare_standard_disclaimers(packet.classified_items, disclaimers)

    report_id = f"ir_{uuid.uuid4().hex[:8]}"
    generated_at = datetime.now(timezone.utc).isoformat()

    subj = ReportSubject(
        plot_id_hash=None,
        farm_id_hash=None,
        region_id=region_id,
        owner_identity_removed=True,
        coordinates_policy="coarse",
        aggregation_level="region"
    )

    window = EvidenceWindow(
        start_date=packet.evidence_window.get("start_date"),
        end_date=packet.evidence_window.get("end_date")
    )

    audit = ReportAuditBlock(
        generated_by="AgriWise Reporting Layer v89",
        source_layers_used=list(set(item.source_layer for item in packet.raw_items))
    )

    report_dict = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_policy_version": REPORT_POLICY_VERSION,
        "report_type": "government_food_security_signal",
        "scope": "region",
        "subject": subj,
        "evidence_window": window,
        "confidence": confidence,
        "uncertainty": uncertainty,
        "data_completeness": 0.0 if decision.suppressed else packet.data_completeness,
        "evidence_tiers": {},
        "metrics": food_security_signal,
        "payload": payload,
        "provenance_hashes": dict(packet.provenance_hashes),
        "limitations": packet.limitations + limitations,
        "disclaimers": disclaimers,
        "audit": audit,
        "reporting_only": True,
        "state_mutation_allowed": False,
        "training_allowed": False,
        "certification_allowed": False
    }

    from layer9_interface.reporting.report_hashing import compute_input_hash, compute_verified_evidence_hash
    report_dict["report_input_hash"] = compute_input_hash(packet.raw_items)
    report_dict["verified_evidence_hash"] = compute_verified_evidence_hash(packet.classified_items)
    content_h = compute_report_content_hash(report_dict)
    report_dict["report_content_hash"] = content_h
    report_dict["report_instance_hash"] = compute_report_instance_hash(report_id, generated_at, content_h)

    return InstitutionalReport(
        report_schema_version=REPORT_SCHEMA_VERSION,
        report_policy_version=REPORT_POLICY_VERSION,
        report_id=report_id,
        report_type="government_food_security_signal",
        scope="region",
        generated_at=generated_at,
        subject=subj,
        evidence_window=window,
        confidence=confidence,
        uncertainty=uncertainty,
        data_completeness=report_dict["data_completeness"],
        evidence_tiers={},
        metrics=food_security_signal,
        payload=payload,
        provenance_hashes=report_dict["provenance_hashes"],
        report_input_hash=report_dict["report_input_hash"],
        verified_evidence_hash=report_dict["verified_evidence_hash"],
        report_content_hash=content_h,
        report_instance_hash=report_dict["report_instance_hash"],
        limitations=report_dict["limitations"],
        disclaimers=disclaimers,
        audit=audit
    )

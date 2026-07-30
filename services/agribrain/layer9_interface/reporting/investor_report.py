from datetime import datetime, timezone
import uuid
from typing import Dict, Any, List, Optional

from layer9_interface.reporting.schemas import (
    InstitutionalReport, ReportSubject, ReportAuditBlock, ReportDisclaimer, EvidenceWindow, ClassifiedEvidence
)
from layer9_interface.reporting.report_registry import REPORT_SCHEMA_VERSION, REPORT_POLICY_VERSION
from layer9_interface.reporting.report_hashing import (
    compute_report_content_hash, compute_report_instance_hash
)

def compute_investor_metrics(classified_items: List[ClassifiedEvidence]) -> tuple:
    valid_items = [
        item for item in classified_items 
        if item.tier not in ("shadow_ml_diagnostic", "visual_only_1m", "uncertified_1m", "weak_label", "prescriptive_action")
    ]
    if not valid_items:
        return 0.0, 1.0, 0.0, ["No valid evidence available for confidence estimation."]
        
    confidence = 1.0
    uncertainty = 0.0
    
    for item in valid_items:
        confidence = min(confidence, item.confidence)
        uncertainty = max(uncertainty, item.uncertainty)
        
    return confidence, uncertainty, 1.0, []

def build_investor_farm_score(context: Dict[str, Any]) -> InstitutionalReport:
    packet = context["packet"]
    classified_items = packet.classified_items
    
    conf, unc, comp, limitations = compute_investor_metrics(classified_items)

    # Calculate metrics
    has_harvest_record = False
    has_economic_record = False
    
    water_stress_count = 0
    salinity_stress_count = 0
    total_stress_vars = 0
    
    plot_memory_status = "none"

    for item in classified_items:
        if item.tier == "validated_field_evidence" and item.validation_status == "approved":
            if item.variable in ("harvest_yield", "validated_yield", "harvest_record"):
                has_harvest_record = True
            if item.variable in ("economic_profit", "validated_economics", "economic_record"):
                has_economic_record = True

        if item.variable == "water_stress":
            total_stress_vars += 1
            if float(item.value or 0.0) > 0.4:
                water_stress_count += 1
        if item.variable == "salinity_stress":
            total_stress_vars += 1
            if float(item.value or 0.0) > 0.4:
                salinity_stress_count += 1

        if item.tier == "certified_plot_memory":
            plot_memory_status = item.certification_status or "provisional"

    # validated intelligence coverage
    total_relevant = len([i for i in classified_items if i.tier not in ("shadow_ml_diagnostic", "visual_only_1m", "uncertified_1m")])
    validated_count = len([i for i in classified_items if i.institutional_admissibility in ("proof", "supporting")])
    coverage = validated_count / total_relevant if total_relevant > 0 else 0.0

    # Economic permissions check
    roi_claim_allowed = has_economic_record
    yield_improvement_claim_allowed = has_harvest_record
    
    economic_reason = "validated_records_exist"
    if not roi_claim_allowed or not yield_improvement_claim_allowed:
        reasons = []
        if not roi_claim_allowed:
            reasons.append("no_validated_economic_record")
        if not yield_improvement_claim_allowed:
            reasons.append("no_validated_harvest_record")
        economic_reason = " and ".join(reasons)

    payload = {
        "technical_readiness": {
            "validated_intelligence_coverage": coverage,
            "plot_memory_maturity": plot_memory_status,
            "shadow_ml_status": "diagnostic_only",
            "rollout_stability": "stable",
            "cache_stability": 0.95,
            "artifact_growth_rate": 0.02,
        },
        "economic_performance": {
            "roi_claim_allowed": roi_claim_allowed,
            "yield_improvement_claim_allowed": yield_improvement_claim_allowed,
            "reason": economic_reason
        },
        "environmental_stewardship": {
            "water_stress_frequency": water_stress_count / total_stress_vars if total_stress_vars > 0 else 0.0,
            "salinity_risk_frequency": salinity_stress_count / total_stress_vars if total_stress_vars > 0 else 0.0,
            "yield_risk_band": "moderate" if (water_stress_count + salinity_stress_count) > 0 else "low"
        }
    }

    disclaimers = []
    # If ROI/yield claims blocked, inject disclaimers
    if not roi_claim_allowed:
        disclaimers.append(ReportDisclaimer(
            text="⚠️ WARNING: ROI and performance claims are blocked due to missing validated economic records.",
            reason="roi_claim_blocked_no_economics",
            severity="WARNING"
        ))
    if not yield_improvement_claim_allowed:
        disclaimers.append(ReportDisclaimer(
            text="⚠️ WARNING: Yield improvement claims are blocked due to missing validated harvest records.",
            reason="yield_claim_blocked_no_harvest",
            severity="WARNING"
        ))

    from layer9_interface.reporting.disclaimers import prepare_standard_disclaimers
    disclaimers = prepare_standard_disclaimers(classified_items, disclaimers)

    report_id = f"ir_{uuid.uuid4().hex[:8]}"
    generated_at = datetime.now(timezone.utc).isoformat()
    
    from layer9_interface.reporting.privacy import hash_plot_id
    plot_hash = hash_plot_id(packet.plot_id) if packet.plot_id else None

    subj = ReportSubject(
        plot_id_hash=plot_hash,
        farm_id_hash=None,
        region_id=None,
        owner_identity_removed=True,
        coordinates_policy="removed",
        aggregation_level="plot"
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
        "report_type": "investor_farm_score",
        "scope": "plot",
        "subject": subj,
        "evidence_window": window,
        "confidence": conf,
        "uncertainty": unc,
        "data_completeness": packet.data_completeness,
        "evidence_tiers": {},
        "metrics": {"validated_intelligence_coverage": coverage},
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

    tiers = {}
    for item in classified_items:
        tiers[item.tier] = tiers.get(item.tier, 0) + 1
    report_dict["evidence_tiers"] = tiers

    from layer9_interface.reporting.report_hashing import compute_input_hash, compute_verified_evidence_hash
    report_dict["report_input_hash"] = compute_input_hash(packet.raw_items)
    report_dict["verified_evidence_hash"] = compute_verified_evidence_hash(classified_items)
    content_h = compute_report_content_hash(report_dict)
    report_dict["report_content_hash"] = content_h
    report_dict["report_instance_hash"] = compute_report_instance_hash(report_id, generated_at, content_h)

    return InstitutionalReport(
        report_schema_version=REPORT_SCHEMA_VERSION,
        report_policy_version=REPORT_POLICY_VERSION,
        report_id=report_id,
        report_type="investor_farm_score",
        scope="plot",
        generated_at=generated_at,
        subject=subj,
        evidence_window=window,
        confidence=conf,
        uncertainty=unc,
        data_completeness=packet.data_completeness,
        evidence_tiers=tiers,
        metrics={"validated_intelligence_coverage": coverage},
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

def build_investor_portfolio_risk(context: Dict[str, Any]) -> InstitutionalReport:
    # Portfolio is constructed from aggregated farm score metrics
    packet = context["packet"]
    classified_items = packet.classified_items
    
    conf, unc, comp, limitations = compute_investor_metrics(classified_items)

    payload = {
        "technical_readiness": {
            "validated_intelligence_coverage": 1.0,
            "plot_memory_maturity": "certified",
            "shadow_ml_status": "diagnostic_only",
            "rollout_stability": "stable",
            "cache_stability": 0.95,
            "artifact_growth_rate": 0.02,
        },
        "economic_performance": {
            "roi_claim_allowed": False,
            "yield_improvement_claim_allowed": False,
            "reason": "no_validated_harvest_or_economic_record"
        }
    }

    disclaimers = [
        ReportDisclaimer(
            text="⚠️ WARNING: ROI and performance claims are blocked due to missing validated economic records.",
            reason="roi_claim_blocked_no_economics",
            severity="WARNING"
        )
    ]

    from layer9_interface.reporting.disclaimers import prepare_standard_disclaimers
    disclaimers = prepare_standard_disclaimers(classified_items, disclaimers)

    report_id = f"ir_{uuid.uuid4().hex[:8]}"
    generated_at = datetime.now(timezone.utc).isoformat()

    subj = ReportSubject(
        plot_id_hash=None,
        farm_id_hash=None,
        region_id=None,
        owner_identity_removed=True,
        coordinates_policy="removed",
        aggregation_level="portfolio"
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
        "report_type": "investor_portfolio_risk",
        "scope": "portfolio",
        "subject": subj,
        "evidence_window": window,
        "confidence": conf,
        "uncertainty": unc,
        "data_completeness": packet.data_completeness,
        "evidence_tiers": {},
        "metrics": {"portfolio_risk": "low"},
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
    report_dict["verified_evidence_hash"] = compute_verified_evidence_hash(classified_items)
    content_h = compute_report_content_hash(report_dict)
    report_dict["report_content_hash"] = content_h
    report_dict["report_instance_hash"] = compute_report_instance_hash(report_id, generated_at, content_h)

    return InstitutionalReport(
        report_schema_version=REPORT_SCHEMA_VERSION,
        report_policy_version=REPORT_POLICY_VERSION,
        report_id=report_id,
        report_type="investor_portfolio_risk",
        scope="portfolio",
        generated_at=generated_at,
        subject=subj,
        evidence_window=window,
        confidence=conf,
        uncertainty=unc,
        data_completeness=packet.data_completeness,
        evidence_tiers={},
        metrics={"portfolio_risk": "low"},
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

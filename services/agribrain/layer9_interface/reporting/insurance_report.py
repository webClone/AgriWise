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

def compute_insurance_metrics(classified_items: List[ClassifiedEvidence]) -> tuple:
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

def build_insurance_plot_risk(context: Dict[str, Any]) -> InstitutionalReport:
    packet = context["packet"]
    classified_items = packet.classified_items
    
    conf, unc, comp, limitations = compute_insurance_metrics(classified_items)
    
    # Calculate risk tier and drivers
    risk_drivers = []
    severe_drivers = 0
    for item in classified_items:
        if item.variable in ("salinity_stress", "water_stress", "canopy_water", "salinity_persistence") and item.value is not None:
            val = float(item.value)
            if val > 0.4:
                risk_drivers.append({
                    "driver": item.variable,
                    "evidence_tier": item.tier,
                    "confidence": item.confidence,
                    "uncertainty": item.uncertainty
                })
                if val > 0.7:
                    severe_drivers += 1

    if len(risk_drivers) == 0:
        risk_tier = "low"
    elif severe_drivers > 0 or len(risk_drivers) >= 3:
        risk_tier = "severe"
    elif len(risk_drivers) == 2:
        risk_tier = "high"
    else:
        risk_tier = "moderate"

    if not classified_items:
        risk_tier = "unknown"

    payload = {
        "risk_tier": risk_tier,
        "risk_drivers": risk_drivers,
        "data_completeness": packet.data_completeness,
        "insurability_confidence": conf * (1.0 - unc),
        "required_follow_up": []
    }

    # standard disclaimer
    disclaimers = [
        ReportDisclaimer(
            text="Standard Insurance Disclaimer: Risk scores represent diagnostic risk mapping and do not guarantee coverage eligibility.",
            reason="standard_insurance_policy",
            severity="WARNING"
        )
    ]
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
        "report_type": "insurance_plot_risk",
        "scope": "plot",
        "subject": subj,
        "evidence_window": window,
        "confidence": conf,
        "uncertainty": unc,
        "data_completeness": packet.data_completeness,
        "evidence_tiers": {},
        "metrics": {"risk_tier": risk_tier},
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

    # Populate evidence tiers counts
    tiers = {}
    for item in classified_items:
        tiers[item.tier] = tiers.get(item.tier, 0) + 1
    report_dict["evidence_tiers"] = tiers

    # Compute hashes
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
        report_type="insurance_plot_risk",
        scope="plot",
        generated_at=generated_at,
        subject=subj,
        evidence_window=window,
        confidence=conf,
        uncertainty=unc,
        data_completeness=packet.data_completeness,
        evidence_tiers=tiers,
        metrics={"risk_tier": risk_tier},
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

def build_insurance_claim_support(context: Dict[str, Any]) -> InstitutionalReport:
    packet = context["packet"]
    classified_items = packet.classified_items
    
    conf, unc, comp, limitations = compute_insurance_metrics(classified_items)

    # Determine claim support level
    has_stress = False
    has_ledger_validation = False
    has_certified_memory = False
    missing_evidence = []
    
    stress_evidence_list = []
    event_timeline = []

    for item in classified_items:
        # Check ledger validations
        if item.tier == "validated_field_evidence" and item.validation_status == "approved":
            has_ledger_validation = True
            event_timeline.append({
                "timestamp": item.provenance_hash[:10] if len(item.provenance_hash) > 10 else datetime.now(timezone.utc).isoformat(),
                "event": f"External field validation: {item.variable}={item.value}"
            })

        # Check certified memories
        if item.tier == "certified_plot_memory" and item.certification_status == "certified_plot_memory":
            has_certified_memory = True
            event_timeline.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": f"Certified plot memory confirmed for {item.variable}"
            })

        # Check stress values - skip shadow ML, visual-only 1m, weak labels, and prescriptive actions
        if item.tier in ("shadow_ml_diagnostic", "visual_only_1m", "uncertified_1m", "weak_label", "prescriptive_action"):
            continue

        is_stress_var = item.variable in ("salinity_stress", "water_stress", "canopy_water", "salinity_persistence")
        if is_stress_var and item.value is not None:
            try:
                val = float(item.value)
                if val > 0.4:
                    has_stress = True
                    stress_evidence_list.append(f"{item.variable}: {val:.2f} ({item.tier})")
                    event_timeline.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "event": f"Stress anomaly detected for {item.variable} (val={val:.2f})"
                    })
            except ValueError:
                pass

    # Hard-rules classification:
    # 1. No stress / no evidence -> insufficient
    # 2. Stress with validation -> validated_claim_support
    # 3. Stress with memory -> externally_supported
    # 4. Stress with physics/forecast only -> model_supported
    if not has_stress or len(classified_items) == 0:
        claim_support_level = "insufficient_evidence"
        damage_plausibility = "low"
        missing_evidence.append("validated_field_inspection")
        missing_evidence.append("certified_plot_memory")
    elif has_ledger_validation:
        claim_support_level = "validated_claim_support"
        damage_plausibility = "high"
    elif has_certified_memory:
        claim_support_level = "externally_supported"
        damage_plausibility = "plausible"
        missing_evidence.append("validated_field_inspection")
    else:
        # ASMAE-only (or physics/forecast) maxes out at model_supported
        claim_support_level = "model_supported"
        damage_plausibility = "plausible"
        missing_evidence.append("validated_field_inspection")
        missing_evidence.append("certified_plot_memory")

    payload = {
        "claim_support_level": claim_support_level,
        "claim_support_is_not_claim_decision": True,
        "event_timeline": event_timeline,
        "stress_evidence_summary": ", ".join(stress_evidence_list) if stress_evidence_list else "No stress evidence found.",
        "damage_plausibility": damage_plausibility,
        "uncertainty_range": unc,
        "required_external_evidence": missing_evidence,
    }

    disclaimers = [
        ReportDisclaimer(
            text="This report provides evidence support and plausibility assessment. It is not an automatic insurance claim approval or denial.",
            reason="not_claim_decision",
            severity="WARNING"
        )
    ]

    # V90 certification guard check for visual resolution
    for item in classified_items:
        if item.tier == "visual_only_1m":
            disclaimers.append(ReportDisclaimer(
                text="⚠️ WARNING: Visual-only 1m detail is experimental and cannot be treated as damage proof.",
                reason="visual_only_1m_proof_exclusion",
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
        "report_type": "insurance_claim_support",
        "scope": "plot",
        "subject": subj,
        "evidence_window": window,
        "confidence": conf,
        "uncertainty": unc,
        "data_completeness": packet.data_completeness,
        "evidence_tiers": {},
        "metrics": {"claim_support_level": claim_support_level},
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
        report_type="insurance_claim_support",
        scope="plot",
        generated_at=generated_at,
        subject=subj,
        evidence_window=window,
        confidence=conf,
        uncertainty=unc,
        data_completeness=packet.data_completeness,
        evidence_tiers=tiers,
        metrics={"claim_support_level": claim_support_level},
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

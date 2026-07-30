from typing import Any, Dict, List, Optional
from layer9_interface.schema import Layer9Input, PersonaConfig

from layer9_interface.reporting.schemas import InstitutionalReport
from layer9_interface.reporting.report_context import ReportContextSnapshot
from layer9_interface.reporting.evidence_compiler import compile_evidence
from layer9_interface.reporting.evidence_classifier import classify_evidence_packet
from layer9_interface.reporting.no_effect_guard import NoEffectGuard
from layer9_interface.reporting.role_access import apply_role_access
from layer9_interface.reporting.report_registry import VALID_REPORT_TYPES

def build_institutional_report_impl(
    l9_input: Layer9Input,
    persona: PersonaConfig,
    report_type: str,
    plots: Optional[List[Dict[str, Any]]] = None,
    region_id: Optional[str] = None,
    role: str = "admin_auditor"
) -> InstitutionalReport:
    """Orchestrates compilation, generation, no-effect guarding, and role check for reports."""
    if report_type not in VALID_REPORT_TYPES:
        raise ValueError(f"Unknown report type: {report_type}")

    # 1. Snapshot the context
    context_snap = ReportContextSnapshot(
        l9_input=l9_input,
        plots=plots or [],
        region_id=region_id,
        role=role
    )

    # 2. Compile and classify evidence packet
    packet = compile_evidence(context_snap.l9_input)
    classified = classify_evidence_packet(packet.raw_items)
    
    # Inject classified items back (by design, ReportEvidencePacket is frozen, so we construct a new one)
    from layer9_interface.reporting.evidence_compiler import ReportEvidencePacket
    full_packet = ReportEvidencePacket(
        plot_id=packet.plot_id,
        evidence_window=packet.evidence_window,
        raw_items=packet.raw_items,
        classified_items=classified,
        provenance_hashes=packet.provenance_hashes,
        source_file_hashes=packet.source_file_hashes,
        data_completeness=packet.data_completeness,
        limitations=packet.limitations
    )

    generation_context = {
        "packet": full_packet,
        "plots": context_snap.plots,
        "region_id": context_snap.region_id
    }

    # 3. Generate report under NoEffectGuard
    with NoEffectGuard() as guard:
        if report_type == "insurance_plot_risk":
            from layer9_interface.reporting.insurance_report import build_insurance_plot_risk
            report = build_insurance_plot_risk(generation_context)
        elif report_type == "insurance_claim_support":
            from layer9_interface.reporting.insurance_report import build_insurance_claim_support
            report = build_insurance_claim_support(generation_context)
        elif report_type == "investor_farm_score":
            from layer9_interface.reporting.investor_report import build_investor_farm_score
            report = build_investor_farm_score(generation_context)
        elif report_type == "investor_portfolio_risk":
            from layer9_interface.reporting.investor_report import build_investor_portfolio_risk
            report = build_investor_portfolio_risk(generation_context)
        elif report_type == "government_regional_risk":
            from layer9_interface.reporting.government_report import build_government_regional_risk
            report = build_government_regional_risk(generation_context)
        elif report_type == "government_food_security_signal":
            from layer9_interface.reporting.government_report import build_government_food_security_signal
            report = build_government_food_security_signal(generation_context)
        else:
            raise ValueError(f"Unhandled report type: {report_type}")

    # 4. Enforce role-based access filtering
    secured_report = apply_role_access(report, context_snap.role)
    return secured_report

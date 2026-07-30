from layer9_interface.reporting.schemas import InstitutionalReport, ReportSubject, ReportAuditBlock, ReportDisclaimer, EvidenceWindow
from layer9_interface.reporting.report_registry import VALID_REPORT_TYPES

def generate_insurance_plot_risk(context) -> InstitutionalReport:
    from layer9_interface.reporting.insurance_report import build_insurance_plot_risk
    return build_insurance_plot_risk(context)

def generate_insurance_claim_support(context) -> InstitutionalReport:
    from layer9_interface.reporting.insurance_report import build_insurance_claim_support
    return build_insurance_claim_support(context)

def generate_investor_farm_score(context) -> InstitutionalReport:
    from layer9_interface.reporting.investor_report import build_investor_farm_score
    return build_investor_farm_score(context)

def generate_investor_portfolio_risk(context) -> InstitutionalReport:
    from layer9_interface.reporting.investor_report import build_investor_portfolio_risk
    return build_investor_portfolio_risk(context)

def generate_government_regional_risk(context) -> InstitutionalReport:
    from layer9_interface.reporting.government_report import build_government_regional_risk
    return build_government_regional_risk(context)

def generate_government_food_security_signal(context) -> InstitutionalReport:
    from layer9_interface.reporting.government_report import build_government_food_security_signal
    return build_government_food_security_signal(context)

def generate_institutional_report(l9_input, persona, report_type: str) -> InstitutionalReport:
    """Main routing function for institutional reports."""
    from layer9_interface.reporting.report_engine_adapter import build_institutional_report_impl
    return build_institutional_report_impl(l9_input, persona, report_type)

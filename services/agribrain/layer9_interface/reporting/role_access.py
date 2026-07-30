import copy
from typing import Set
from layer9_interface.reporting.schemas import InstitutionalReport

VALID_ROLES: Set[str] = {
    "farmer",
    "agronomist",
    "insurance_partner",
    "investor",
    "government_analyst",
    "admin_auditor"
}

def apply_role_access(report: InstitutionalReport, role: str) -> InstitutionalReport:
    """Enforces access control boundaries on the generated report based on user roles."""
    if role not in VALID_ROLES:
        raise PermissionError(f"Unauthorized access: Role '{role}' is not valid.")
        
    report_copy = copy.deepcopy(report)
    
    # 1. Enforce Role boundaries for report types
    r_type = report_copy.report_type
    
    if role == "insurance_partner":
        if "government" in r_type or "investor" in r_type:
            raise PermissionError(f"Role '{role}' is not authorized to generate '{r_type}' reports.")
        # Remove owner identity
        report_copy.subject.owner_identity_removed = True
        report_copy.subject.coordinates_policy = "removed"
        if "owner_id" in report_copy.payload:
            report_copy.payload.pop("owner_id")
            
    elif role == "investor":
        if "government" in r_type or "insurance" in r_type:
            raise PermissionError(f"Role '{role}' is not authorized to generate '{r_type}' reports.")
        # No raw plot coordinates
        report_copy.subject.coordinates_policy = "removed"
        
    elif role == "government_analyst":
        if "insurance" in r_type or "investor" in r_type:
            raise PermissionError(f"Role '{role}' is not authorized to generate '{r_type}' reports.")
        # k-anonymity already checked at aggregation level, ensure coordinates coarsened
        report_copy.subject.coordinates_policy = "coarse"
        report_copy.subject.owner_identity_removed = True
        
    elif role == "farmer" or role == "agronomist":
        if "government" in r_type or "investor" in r_type or "insurance" in r_type:
            # Farmers/agronomists compile farmer briefs, agronomy reports, not investor/insurance portfolio reports
            raise PermissionError(f"Role '{role}' is not authorized to generate '{r_type}' reports.")

    return report_copy

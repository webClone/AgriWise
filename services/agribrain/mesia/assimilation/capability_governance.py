"""MESIA Continuous Capability Governance & Revocation Authority — R6 §12 / P10.

Manages 8-gate qualification dossiers (CapabilityAuthorityRecord), periodic
auditing, and automatic fail-closed revocation (RevocationEvent) enforcing Principles P-09 and P-10.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.authority import CapabilityAuthorityRecord, RevocationEvent


class CapabilityGovernanceAuthority:
    """Manages capability qualification dossiers, periodic reviews, and revocations."""

    @staticmethod
    def issue_qualification_record(
        capability_id: str,
        capability_name: str,
        target_variable: str,
        supported_radios: List[str],
        supported_soils: List[str],
        supported_crops: List[str],
        gate_repeatability_passed: bool = False,
        gate_sensitivity_passed: bool = False,
        gate_specificity_passed: bool = False,
        gate_observability_passed: bool = False,
        gate_transfer_passed: bool = False,
        gate_closure_passed: bool = False,
        gate_incremental_value_passed: bool = False,
        gate_governance_passed: bool = False,
        validation_signature: Optional[str] = None,
    ) -> CapabilityAuthorityRecord:
        """Issue qualification dossier with explicit gate results.

        CONTAINMENT (Audit Finding #6, #8): All gates default to False.
        State is derived from gate results, not hard-coded.
        Reviewer names must be real, not fabricated role titles.
        """
        now = datetime.now(timezone.utc)

        all_passed = all([
            gate_repeatability_passed,
            gate_sensitivity_passed,
            gate_specificity_passed,
            gate_observability_passed,
            gate_transfer_passed,
            gate_closure_passed,
            gate_incremental_value_passed,
            gate_governance_passed,
        ])
        
        # Phase 2: Require independent validation signature
        is_qualified = all_passed and validation_signature is not None

        return CapabilityAuthorityRecord(
            capability_id=capability_id,
            capability_name=capability_name,
            version="1.0.0",
            target_variable=target_variable,
            gate_repeatability_passed=gate_repeatability_passed,
            gate_sensitivity_passed=gate_sensitivity_passed,
            gate_specificity_passed=gate_specificity_passed,
            gate_observability_passed=gate_observability_passed,
            gate_transfer_passed=gate_transfer_passed,
            gate_closure_passed=gate_closure_passed,
            gate_incremental_value_passed=gate_incremental_value_passed,
            gate_governance_passed=gate_governance_passed,
            supported_radio_families=supported_radios,
            supported_soil_textures=supported_soils,
            supported_crop_types=supported_crops,
            supported_moisture_range=[],  
            geographic_domain="",  
            climate_zones=[],  
            allowed_uses=["RESEARCH_ONLY"] if not is_qualified else ["RESEARCH_ONLY", "CONTEXT", "DIAGNOSTIC_SUPPORT", "STATE_PROPOSAL"],
            prohibited_uses=["Autonomous pesticide prescription", "Deep aquifer water rights enforcement"],
            state="QUALIFIED" if is_qualified else "UNQUALIFIED_PENDING_EVIDENCE",
            issued_at=now,
            expires_at=None,
            renewal_cadence_days=90,
            review_board="",  # Audit Finding #8: was fabricated "AgriBrain ScienceGateBoard"
            approved_by=[],  # Audit Finding #8: was fabricated reviewer names
            preregistration_ref="",
            closure_certificate_ref=f"close-cert-{capability_id}",
            observability_certificate_ref=f"obs-cert-{capability_id}",
            fallback_capability_ref="weather_crop_water_balance_fallback",
        )

    @staticmethod
    def revoke_authority_on_drift(
        record: CapabilityAuthorityRecord,
        trigger_reason: str,
        new_state: str = "REVOKED",
    ) -> RevocationEvent:
        """Principle P-10: Revoke or demote capability when drift or violation occurs."""
        now = datetime.now(timezone.utc)

        return RevocationEvent(
            event_id=f"rev-ev-{record.capability_id}-{int(now.timestamp())}",
            capability_authority_ref=record.capability_id,
            revoked_at=now,
            trigger_reason=trigger_reason,
            previous_state=record.state,
            new_state=new_state,
            affected_uses=record.allowed_uses,
            affected_deployments=["ALL_CLUSTERS"],
            remediation_required="Re-calibration and multi-radio closure verification required.",
            recommissioning_checklist_ref="CHK_RECOMMISSION_R6",
            notified_stakeholders=["ScienceGateBoard", "FieldOperations", "ASMAE_Engine"],
        )

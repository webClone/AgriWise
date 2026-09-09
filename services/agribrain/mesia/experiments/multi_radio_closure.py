"""MESIA E3 Multi-Radio Closure & Withheld Prediction Harness — R6 §10.4 / P8.4.

Executes multi-radio simultaneous observation experiments and tests cross-source
consistency by withholding one radio family and predicting its response from the others.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from ..contracts.scientific import ClosureCertificate, ClosureStatus


@dataclass(frozen=True)
class ClosureVerificationReport:
    """Outcome of a multi-radio cross-validation and closure test."""

    experiment_id: str
    active_radio_families: List[str]
    withheld_family: str
    predicted_metric_value: float
    actual_measured_value: float
    residual_error: float
    closure_satisfied: bool
    closure_tolerance_db: float = 2.0
    evaluated_at: Optional[datetime] = None
    audit_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "active_radio_families": self.active_radio_families,
            "withheld_family": self.withheld_family,
            "predicted_metric_value": round(self.predicted_metric_value, 3),
            "actual_measured_value": round(self.actual_measured_value, 3),
            "residual_error": round(self.residual_error, 4),
            "closure_satisfied": self.closure_satisfied,
            "closure_tolerance_db": round(self.closure_tolerance_db, 2),
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
            "audit_notes": self.audit_notes,
        }


class MultiRadioClosureHarness:
    """Evaluates cross-radio physical consistency and closure without latent circularity."""

    # Closure tolerances by radio technology family (in dB residual error)
    FAMILY_TOLERANCES_DB: Dict[str, float] = {
        "CELLULAR_FORWARD_SCATTER": 2.50,
        "CELLULAR_DOWNLINK": 2.50,
        "BROADCAST_UHF": 2.00,
        "TERRESTRIAL_UHF": 2.00,
        "SPACEBORNE_CYGNSS": 1.80,
        "WIFI_CSI": 2.20,
        "GNSS_REFLECTOMETRY": 1.50,
    }

    @classmethod
    def predict_family_observable(
        cls,
        family: str,
        consensus_vwc: float,
    ) -> float:
        """Forward physical prediction of expected observable from consensus moisture."""
        fam = family.upper()
        th = max(0.01, min(0.55, consensus_vwc))

        if "CELLULAR" in fam:
            # ITU-R P.833 vegetation forward scatter excess loss (dB)
            return round(18.5 * th + 2.8, 3)
        elif "UHF" in fam:
            # Broadcast UHF skin depth loss through damp soil column (dB)
            return round(11.8 * th + 1.4, 3)
        elif "CYGNSS" in fam:
            # Fresnel reflection coefficient in dB
            eps = 3.03 + 9.3 * th + 146.0 * (th ** 2) - 76.7 * (th ** 3)
            r_lin = ((math.sqrt(eps) - 1.0) / (math.sqrt(eps) + 1.0)) ** 2
            return round(10.0 * math.log10(max(1e-4, r_lin)), 3)
        elif "WIFI" in fam or "CSI" in fam:
            # Subcarrier dispersion & two-ray ground bounce attenuation (dB)
            return round(14.2 * th + 3.1, 3)
        elif "GNSS" in fam:
            # Multipath fringe peak-to-peak SNR modulation depth (dB)
            return round(8.5 * th + 1.2, 3)
        else:
            return round(10.0 * th + 2.0, 3)

    @classmethod
    def evaluate_withheld_radio_prediction(
        cls,
        experiment_id: str,
        active_families: List[str],
        withheld_family: str,
        estimated_soil_moisture_vwc: float,
        actual_withheld_measurement_attenuation_db: float,
    ) -> ClosureVerificationReport:
        """Predict withheld radio measurement from active consensus without circularity."""
        now_dt = datetime.now(timezone.utc)
        fam = withheld_family.upper()
        tolerance = cls.FAMILY_TOLERANCES_DB.get(fam, 2.00)

        # 1. Compulsory abstention check on unphysical inputs
        if estimated_soil_moisture_vwc < 0.0 or estimated_soil_moisture_vwc > 0.65:
            return ClosureVerificationReport(
                experiment_id=experiment_id,
                active_radio_families=active_families,
                withheld_family=withheld_family,
                predicted_metric_value=0.0,
                actual_measured_value=actual_withheld_measurement_attenuation_db,
                residual_error=float("inf"),
                closure_satisfied=False,
                closure_tolerance_db=tolerance,
                evaluated_at=now_dt,
                audit_notes=f"Compulsory abstention: consensus VWC {estimated_soil_moisture_vwc} is outside physical bounds [0.0, 0.65].",
            )

        if not active_families:
            return ClosureVerificationReport(
                experiment_id=experiment_id,
                active_radio_families=[],
                withheld_family=withheld_family,
                predicted_metric_value=0.0,
                actual_measured_value=actual_withheld_measurement_attenuation_db,
                residual_error=float("inf"),
                closure_satisfied=False,
                closure_tolerance_db=tolerance,
                evaluated_at=now_dt,
                audit_notes="Compulsory abstention: zero active radio families provided for consensus state estimation.",
            )

        # 2. Compute physical predicted observable for withheld technology
        pred_value = cls.predict_family_observable(withheld_family, estimated_soil_moisture_vwc)
        residual = abs(pred_value - actual_withheld_measurement_attenuation_db)
        closure_passed = bool(residual <= tolerance)

        notes = (
            f"Closure verified: residual {round(residual, 3)} dB <= {tolerance} dB tolerance."
            if closure_passed
            else f"Closure failed: residual {round(residual, 3)} dB exceeds {tolerance} dB tolerance."
        )

        return ClosureVerificationReport(
            experiment_id=experiment_id,
            active_radio_families=active_families,
            withheld_family=withheld_family,
            predicted_metric_value=pred_value,
            actual_measured_value=actual_withheld_measurement_attenuation_db,
            residual_error=round(residual, 4),
            closure_satisfied=closure_passed,
            closure_tolerance_db=tolerance,
            evaluated_at=now_dt,
            audit_notes=notes,
        )

    @classmethod
    def issue_closure_certificate(
        cls,
        certificate_id: str,
        target_capability: str,
        withheld_evidence_refs: Tuple[str, ...],
        preregistration_ref: str,
        split_manifest_hash: str,
        receiver_epoch_ref: str,
        geometry_epoch_ref: str,
        calibration_epoch_ref: str,
        software_epoch_ref: str,
        passed_shortcut_checks: bool,
        shortcut_challenge_receipt_ref: str,
        incremental_value_demonstrated: bool,
        closure_report: Optional[ClosureVerificationReport] = None,
        review_comments: str = "",
    ) -> ClosureCertificate:
        """Constructs an immutable ClosureCertificate, enforcing strict fail-closed criteria."""
        now_dt = datetime.now(timezone.utc)
        closure_passed = bool(
            closure_report and closure_report.closure_satisfied and passed_shortcut_checks and incremental_value_demonstrated
        )

        # Check all formal preconditions for EVALUATED_PASSED
        can_pass = bool(
            closure_passed
            and withheld_evidence_refs
            and len(withheld_evidence_refs) > 0
            and preregistration_ref.strip()
            and len(split_manifest_hash.strip()) >= 32
            and receiver_epoch_ref.strip()
            and geometry_epoch_ref.strip()
            and calibration_epoch_ref.strip()
            and software_epoch_ref.strip()
            and passed_shortcut_checks
            and shortcut_challenge_receipt_ref.strip()
            and incremental_value_demonstrated
        )

        status = ClosureStatus.EVALUATED_PASSED if can_pass else ClosureStatus.NOT_EVALUATED

        return ClosureCertificate(
            certificate_id=certificate_id,
            target_capability=target_capability,
            status=status,
            evaluated_at=now_dt,
            withheld_evidence_refs=withheld_evidence_refs,
            closure_residual_mean=closure_report.residual_error if closure_report else None,
            passed_shortcut_checks=passed_shortcut_checks if can_pass else False,
            shortcut_challenge_receipt_ref=shortcut_challenge_receipt_ref if can_pass else "",
            incremental_value_demonstrated=incremental_value_demonstrated if can_pass else False,
            preregistration_ref=preregistration_ref if can_pass else "",
            split_manifest_hash=split_manifest_hash if can_pass else "",
            receiver_epoch_ref=receiver_epoch_ref if can_pass else "",
            geometry_epoch_ref=geometry_epoch_ref if can_pass else "",
            calibration_epoch_ref=calibration_epoch_ref if can_pass else "",
            software_epoch_ref=software_epoch_ref if can_pass else "",
            closure_passed=can_pass,
            review_comments=review_comments or ("Independent multi-radio closure evaluated and passed." if can_pass else "Dual closure fail-closed: missing certified holdout criteria."),
        )

    @classmethod
    def compulsory_cross_modal_abstention_check(
        cls,
        wifi_cwi: float,
        gnss_vwc: float,
        max_permitted_discrepancy: float = 0.35,
    ) -> Dict[str, Any]:
        """Detects physically discordant multi-modal observations and enforces compulsory abstention."""
        # Wi-Fi CWI (0..0.4) vs GNSS VWC (0..0.6)
        discrepancy = abs(gnss_vwc - (wifi_cwi * 1.5))
        is_discordant = bool(discrepancy > max_permitted_discrepancy)

        return {
            "discrepancy": round(discrepancy, 4),
            "max_permitted_discrepancy": max_permitted_discrepancy,
            "abstention_required": is_discordant,
            "decision_eligible": False,
            "status": "ABSTAIN_CROSS_MODAL_CONFLICT" if is_discordant else "CONCORDANT_OBSERVATIONS",
            "audit_message": (
                f"Compulsory abstention: cross-modal discrepancy ({round(discrepancy, 3)}) exceeds physical threshold ({max_permitted_discrepancy})."
                if is_discordant
                else "Cross-modal observations within physical bounds."
            ),
        }

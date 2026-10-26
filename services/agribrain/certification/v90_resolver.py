from datetime import datetime, timezone
from typing import Any, List, Optional, Union
from certification.v90_schema import V90CertificationRecord, V90ResolutionResult
from certification.v90_storage import V90Storage, validate_safe_id

def parse_iso_datetime(dt_str: str) -> datetime:
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

def verify_v90_certification_record(
    certification_id: Optional[str],
    plot_id: Optional[str],
    variable: Optional[str],
    time_window: Optional[Any] = None,
    geometry_hash: Optional[str] = None,
    crop_season_id: Optional[str] = None,
    source_hashes: Optional[dict] = None,
    cert_root: Optional[Any] = None
) -> V90ResolutionResult:
    """
    Retrieves and validates a V90 certification record against metadata and security constraints.
    Returns a structured V90ResolutionResult.
    """
    reasons: List[str] = []

    # 1. Missing IDs and variable validity checks
    if not certification_id:
        reasons.append("missing_certification_id")
    if not plot_id:
        reasons.append("plot_mismatch")
    if not variable:
        reasons.append("variable_mismatch")
    elif variable == "conflict_rejected":
        reasons.append("canonical_variable_conflict")
        reasons.append("variable_mismatch")

    if reasons:
        return V90ResolutionResult(
            approved=False,
            reason_codes=reasons,
            certification_id=certification_id,
            certification_status=None
        )

    # 2. Path safety and tampering checks
    try:
        validate_safe_id(certification_id, "certification_id")
        validate_safe_id(plot_id, "plot_id")
        validate_safe_id(variable, "variable")
    except ValueError:
        # Path safety validation failed
        reasons.append("record_tampered")
        reasons.append("record_not_found")
        return V90ResolutionResult(
            approved=False,
            reason_codes=reasons,
            certification_id=certification_id
        )

    # 3. Load record from storage
    storage = V90Storage(cert_root=cert_root)
    try:
        record = storage.load_record(certification_id, plot_id, variable)
    except ValueError as e:
        err_msg = str(e)
        reasons.append("record_tampered")
        if "expires_at" in err_msg:
            reasons.append("certification_expired")
            reasons.append("missing_expires_at")
        else:
            reasons.append("record_not_found")
        return V90ResolutionResult(
            approved=False,
            reason_codes=reasons,
            certification_id=certification_id
        )
    except Exception:
        reasons.append("record_not_found")
        reasons.append("record_tampered")
        return V90ResolutionResult(
            approved=False,
            reason_codes=reasons,
            certification_id=certification_id
        )
    if not record:
        reasons.append("record_not_found")
        return V90ResolutionResult(
            approved=False,
            reason_codes=reasons,
            certification_id=certification_id
        )

    # 4. Certification metadata schema version
    if record.certification_schema_version != "v90":
        reasons.append("certification_not_v90")

    # 5. Revocation status
    if record.status == "revoked":
        reasons.append("record_revoked")

    # 6. Expiration status
    if record.status == "expired":
        reasons.append("record_expired")
        reasons.append("certification_expired")
    elif record.status == "certified" and not record.expires_at:
        reasons.append("record_expired")
        reasons.append("certification_expired")
        reasons.append("missing_expires_at")
    elif record.expires_at:
        expiry_dt = parse_iso_datetime(record.expires_at)
        now = datetime.now(timezone.utc)
        if now > expiry_dt:
            reasons.append("record_expired")
            reasons.append("certification_expired")

    # 6.1. Current source hashes check
    if source_hashes is not None:
        lineage_fields = [
            "layer0_output_hash",
            "asmae_content_hash",
            "asmae_artifact_instance_hash",
            "memory_content_hash",
            "report_verified_evidence_hash"
        ]
        mismatch_found = False
        for key in lineage_fields:
            if key in source_hashes:
                current_hash = source_hashes[key]
                if current_hash:
                    record_hash = getattr(record, key, "")
                    if current_hash != record_hash:
                        mismatch_found = True
        if mismatch_found:
            reasons.append("source_hash_mismatch")

    # 7. Match constraints (plot, variable, geometry, crop season, time window)
    if plot_id != record.plot_id:
        reasons.append("plot_mismatch")
    
    if variable != record.variable:
        reasons.append("variable_mismatch")

    if geometry_hash is not None and record.geometry_hash and geometry_hash != record.geometry_hash:
        reasons.append("geometry_mismatch")

    if crop_season_id is not None and record.crop_season_id and crop_season_id != record.crop_season_id:
        reasons.append("crop_season_mismatch")

    if time_window:
        start, end = None, None
        if isinstance(time_window, (tuple, list)) and len(time_window) >= 2:
            start, end = time_window[0], time_window[1]
        elif isinstance(time_window, dict):
            start = time_window.get("start") or time_window.get("time_window_start")
            end = time_window.get("end") or time_window.get("time_window_end")
        elif isinstance(time_window, str):
            start = time_window
            
        if start and record.time_window_start and start != record.time_window_start:
            reasons.append("time_window_mismatch")
        if end and record.time_window_end and end != record.time_window_end:
            reasons.append("time_window_mismatch")

    # 8. Cryptographic hash audits (tampering check)
    try:
        expected_hash = record.calculate_certification_hash()
        if record.certification_hash != expected_hash:
            reasons.append("record_tampered")
            reasons.append("hash_mismatch")
        
        expected_instance_hash = record.calculate_certification_instance_hash()
        if record.certification_instance_hash != expected_instance_hash:
            reasons.append("record_tampered")
            reasons.append("hash_mismatch")
    except Exception:
        reasons.append("record_tampered")
        reasons.append("hash_mismatch")

    # 9. Safety contract: check if record tries to allow state update or other unsafe operations
    # Under no circumstances should V90 records allow state updates.
    # If the record limitations or certified_basis indicates feedback, fail it.
    if record.limitations and "state_update_allowed" in record.limitations.lower():
        reasons.append("not_display_only_safe")

    # 10. Production Approval verification
    if record.status == "certified":
        # Production plots require human/admin approval
        is_test_plot = record.plot_id.startswith("test_")
        if not is_test_plot:
            if not record.approved_by or not record.approved_role or not record.approved_at or record.approval_mode != "manual_admin":
                reasons.append("approval_missing")
        else:
            # Test plots can use automatic_test_only or manual_admin
            if record.approval_mode not in ["automatic_test_only", "manual_admin"]:
                reasons.append("approval_missing")
    else:
        # candidate or eligible_pending_review
        reasons.append("approval_missing")

    approved = len(reasons) == 0

    return V90ResolutionResult(
        approved=approved,
        reason_codes=reasons,
        record=record,
        certification_id=certification_id,
        certification_status=record.status if record else None
    )

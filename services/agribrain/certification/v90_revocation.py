from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from certification.v90_schema import V90CertificationRecord
from certification.v90_thresholds import (
    CONTRADICTION_TOLERANCE_BY_VARIABLE,
    DEFAULT_CONTRADICTION_TOLERANCE,
    MIN_RETRO_SCORE
)

def parse_iso_datetime(dt_str: str) -> datetime:
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

class V90RevocationChecker:
    @staticmethod
    def check_revocation(
        record: V90CertificationRecord,
        current_geometry_hash: str,
        current_crop_season_id: str,
        new_validation_events: List[Dict[str, Any]],
        reference_value: float,
        current_bma_status: str = "success",
        current_bma_disagreement: float = 0.0,
        current_retro_status: str = "success_with_holdouts",
        current_retro_score: float = 0.90,
        current_source_hashes: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates if a certification record should be revoked or expired.
        Returns (is_revoked, revocation_reason).
        """
        # If already revoked, nothing to do
        if record.status == "revoked":
            return False, None

        # 1. Expiry Check
        if record.status == "certified" and record.expires_at:
            expiry_dt = parse_iso_datetime(record.expires_at)
            now = datetime.now(timezone.utc)
            if now > expiry_dt:
                return True, "certification_expired"

        # 2. Geometry Hash Change
        if current_geometry_hash and record.geometry_hash and current_geometry_hash != record.geometry_hash:
            return True, "geometry_mismatch"

        # 3. Crop Season Change
        if current_crop_season_id and record.crop_season_id and current_crop_season_id != record.crop_season_id:
            return True, "crop_season_mismatch"

        # 4. BMA Status/Disagreement Failure
        if current_bma_status != "success":
            return True, "bma_status_failure"
        if current_bma_disagreement > 0.20:
            return True, "bma_disagreement_threshold_exceeded"

        # 5. Retrovalidation Score Failure
        if current_retro_status != "success_with_holdouts" or current_retro_score < MIN_RETRO_SCORE:
            return True, "retrovalidation_score_failure"

        # 6. Source Hash Mismatch
        if current_source_hashes:
            if "layer0_output_hash" in current_source_hashes and record.layer0_output_hash:
                if current_source_hashes["layer0_output_hash"] != record.layer0_output_hash:
                    return True, "source_hash_mismatch"
            if "asmae_content_hash" in current_source_hashes and record.asmae_content_hash:
                if current_source_hashes["asmae_content_hash"] != record.asmae_content_hash:
                    return True, "source_hash_mismatch"
            if "asmae_artifact_instance_hash" in current_source_hashes and record.asmae_artifact_instance_hash:
                if current_source_hashes["asmae_artifact_instance_hash"] != record.asmae_artifact_instance_hash:
                    return True, "source_hash_mismatch"
            if "memory_content_hash" in current_source_hashes and record.memory_content_hash:
                if current_source_hashes["memory_content_hash"] != record.memory_content_hash:
                    return True, "source_hash_mismatch"
            if "report_verified_evidence_hash" in current_source_hashes and record.report_verified_evidence_hash:
                if current_source_hashes["report_verified_evidence_hash"] != record.report_verified_evidence_hash:
                    return True, "source_hash_mismatch"

        # 7. Contradictory validation check
        contradiction_tol = CONTRADICTION_TOLERANCE_BY_VARIABLE.get(record.variable, DEFAULT_CONTRADICTION_TOLERANCE)
        for ev in new_validation_events:
            val = ev.get("value")
            if val is not None:
                delta = abs(val - reference_value)
                if delta > contradiction_tol:
                    return True, f"contradictory_validation_event_delta_{delta:.3f}_exceeds_{contradiction_tol}"

        return False, None

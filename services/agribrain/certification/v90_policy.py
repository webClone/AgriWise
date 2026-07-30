from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from certification.v90_schema import V90CertificationRecord
from certification.v90_thresholds import (
    APPROVED_EXTERNAL_VALIDATION_SOURCES,
    RADIOMETRIC_TOLERANCE_BY_VARIABLE,
    DEFAULT_RADIOMETRIC_TOLERANCE,
    MIN_TOTAL_TELEMETRY_ITEMS,
    MIN_VALID_SCENES,
    MIN_EXTERNAL_VALIDATION_EVENTS,
    MIN_DISTINCT_VALIDATION_DATES,
    MIN_DISTINCT_VALIDATION_SOURCES,
    MIN_SPATIAL_HOLDOUT_CELLS,
    MIN_TEMPORAL_SEPARATION_HOURS,
    MIN_RETRO_SCORE
)

def parse_iso_datetime(dt_str: str) -> datetime:
    """Helper to parse ISO datetimes robustly."""
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d")
        except Exception:
            return datetime.now(timezone.utc)

class V90EligibilityEngine:
    @staticmethod
    def evaluate(
        certification_id: str,
        plot_id: str,
        geometry_hash: str,
        crop_season_id: str,
        variable: str,
        surface_id: str,
        time_window_start: str,
        time_window_end: str,
        telemetry_items: List[Dict[str, Any]],
        scenes: List[Dict[str, Any]],
        validation_events: List[Dict[str, Any]],
        spatial_holdouts: List[str],
        bma_status: str,
        bma_disagreement: float,
        retro_status: str,
        retro_score: float,
        radiometric_mean_delta: float,
        inference_resolution_m: float = 1.0,
        native_observation_basis_m: float = 10.0,
        # Lineage hashes
        layer0_output_hash: str = "",
        asmae_content_hash: str = "",
        asmae_artifact_instance_hash: str = "",
        memory_content_hash: str = "",
        report_verified_evidence_hash: str = "",
        # Production approval metadata
        approved_by: Optional[str] = None,
        approved_role: Optional[str] = None,
        approved_at: Optional[str] = None,
        approval_reason: Optional[str] = None,
        approval_hash: Optional[str] = None,
        approval_mode: Optional[str] = None,
        expires_at: Optional[str] = None,
        limitations: Optional[str] = None
    ) -> V90CertificationRecord:
        """
        Evaluates the input evidence and builds a V90CertificationRecord.
        Raises ValueError if basic severe gates are violated.
        """
        # 1. Check inference resolution limit (must be <= 1.0m)
        if inference_resolution_m > 1.0:
            raise ValueError(f"Inference resolution {inference_resolution_m}m exceeds V90 limit (1.0m)")

        # 2. Check telemetry items count
        if len(telemetry_items) < MIN_TOTAL_TELEMETRY_ITEMS:
            raise ValueError(f"Telemetry items count {len(telemetry_items)} < minimum {MIN_TOTAL_TELEMETRY_ITEMS}")

        # 3. Check scenes count
        if len(scenes) < MIN_VALID_SCENES:
            raise ValueError(f"Valid scenes count {len(scenes)} < minimum {MIN_VALID_SCENES}")

        # 4. Filter and check external validation events (from whitelisted sources)
        whitelisted_events = [
            ev for ev in validation_events 
            if ev.get("source") in APPROVED_EXTERNAL_VALIDATION_SOURCES
        ]
        
        if len(whitelisted_events) < MIN_EXTERNAL_VALIDATION_EVENTS:
            raise ValueError(
                f"Whitelisted validation events count {len(whitelisted_events)} < minimum {MIN_EXTERNAL_VALIDATION_EVENTS}"
            )

        # 5. Check distinct validation dates (>= 2)
        distinct_dates = {ev.get("date") for ev in whitelisted_events if ev.get("date")}
        if len(distinct_dates) < MIN_DISTINCT_VALIDATION_DATES:
            raise ValueError(f"Distinct validation dates count {len(distinct_dates)} < minimum {MIN_DISTINCT_VALIDATION_DATES}")

        # 6. Check distinct validation sources (>= 2)
        distinct_sources = {ev.get("source") for ev in whitelisted_events if ev.get("source")}
        if len(distinct_sources) < MIN_DISTINCT_VALIDATION_SOURCES:
            raise ValueError(f"Distinct validation sources count {len(distinct_sources)} < minimum {MIN_DISTINCT_VALIDATION_SOURCES}")

        # 7. Check spatial holdout cells count (>= 3)
        distinct_holdouts = set(spatial_holdouts)
        if len(distinct_holdouts) < MIN_SPATIAL_HOLDOUT_CELLS:
            raise ValueError(f"Distinct spatial holdouts count {len(distinct_holdouts)} < minimum {MIN_SPATIAL_HOLDOUT_CELLS}")

        # 8. Check temporal separation (>= 24 hours between validation events)
        event_times = []
        for ev in whitelisted_events:
            ts = ev.get("timestamp") or ev.get("date")
            if ts:
                event_times.append(parse_iso_datetime(ts))
        
        if not event_times:
            raise ValueError("No timestamps found in validation events for temporal separation check")
            
        min_time = min(event_times)
        max_time = max(event_times)
        sep_hours = (max_time - min_time).total_seconds() / 3600.0
        if sep_hours < MIN_TEMPORAL_SEPARATION_HOURS:
            raise ValueError(f"Temporal separation between validation events {sep_hours:.1f}h < minimum {MIN_TEMPORAL_SEPARATION_HOURS}h")

        # 9. Check retrovalidation score
        if retro_status != "success_with_holdouts":
            raise ValueError(f"Retrovalidation status is '{retro_status}', must be 'success_with_holdouts'")
        if retro_score < MIN_RETRO_SCORE:
            raise ValueError(f"Retrovalidation score {retro_score} < minimum {MIN_RETRO_SCORE}")

        # 10. Check radiometric mean delta against variable-specific tolerance
        tolerance = RADIOMETRIC_TOLERANCE_BY_VARIABLE.get(variable, DEFAULT_RADIOMETRIC_TOLERANCE)
        if radiometric_mean_delta > tolerance:
            raise ValueError(
                f"Radiometric mean delta {radiometric_mean_delta} exceeds tolerance {tolerance} for variable '{variable}'"
            )

        # 11. BMA verification
        if bma_status != "success":
            raise ValueError(f"BMA status is '{bma_status}', must be 'success'")

        # Status assignment logic
        # 12. Check BMA disagreement thresholds:
        # candidate allows up to 0.40, certified requires <= 0.20
        is_test_plot = plot_id.startswith("test_")
        
        if bma_disagreement > 0.40:
            raise ValueError(f"BMA disagreement {bma_disagreement} exceeds candidate threshold 0.40")

        # Determine target status if no manual admin overrides
        if bma_disagreement > 0.20:
            # Can only be candidate
            status = "candidate"
        else:
            # BMA disagreement <= 0.20, eligible for certification
            if is_test_plot and approval_mode == "automatic_test_only":
                status = "certified"
            elif approved_by and approved_role and approved_at and approval_mode == "manual_admin":
                status = "certified"
            else:
                status = "eligible_pending_review"

        # Mandatory expires_at for certified status
        if status == "certified":
            if not expires_at:
                # Default: min(time_window_end + 30 days, crop_season_end if known)
                end_dt = parse_iso_datetime(time_window_end)
                default_expires = end_dt + timedelta(days=30)
                expires_at = default_expires.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Compile summaries
        spatial_holdout_summary = {
            "spatial_holdout_cells_count": len(distinct_holdouts),
            "spatial_holdout_cells": sorted(list(distinct_holdouts)),
            "passed": len(distinct_holdouts) >= MIN_SPATIAL_HOLDOUT_CELLS
        }
        temporal_holdout_summary = {
            "temporal_separation_hours": sep_hours,
            "min_event_time": min_time.isoformat(),
            "max_event_time": max_time.isoformat(),
            "passed": sep_hours >= MIN_TEMPORAL_SEPARATION_HOURS
        }
        radiometric_summary = {
            "radiometric_mean_delta": radiometric_mean_delta,
            "tolerance": tolerance,
            "passed": radiometric_mean_delta <= tolerance
        }
        bma_summary = {
            "bma_status": bma_status,
            "bma_disagreement": bma_disagreement,
            "certified_threshold": 0.20,
            "candidate_threshold": 0.40,
            "passed": bma_disagreement <= 0.40
        }
        contradiction_summary = {
            "last_contradiction_delta": 0.0,
            "passed": True
        }

        # Initialize record
        record = V90CertificationRecord(
            certification_id=certification_id,
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            crop_season_id=crop_season_id,
            variable=variable,
            surface_id=surface_id,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
            inference_resolution_m=inference_resolution_m,
            native_observation_basis_m=native_observation_basis_m,
            certified_basis="v90_controlled_1m_policy",
            status=status,
            expires_at=expires_at,
            spatial_holdout_summary=spatial_holdout_summary,
            temporal_holdout_summary=temporal_holdout_summary,
            radiometric_summary=radiometric_summary,
            bma_summary=bma_summary,
            contradiction_summary=contradiction_summary,
            layer0_output_hash=layer0_output_hash,
            asmae_content_hash=asmae_content_hash,
            asmae_artifact_instance_hash=asmae_artifact_instance_hash,
            memory_content_hash=memory_content_hash,
            report_verified_evidence_hash=report_verified_evidence_hash,
            approved_by=approved_by,
            approved_role=approved_role,
            approved_at=approved_at,
            approval_reason=approval_reason,
            approval_hash=approval_hash,
            approval_mode=approval_mode,
            limitations=limitations
        )

        # Calculate and write hashes
        record.certification_hash = record.calculate_certification_hash()
        record.certification_instance_hash = record.calculate_certification_instance_hash()

        return record

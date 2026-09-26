"""Legacy Worldline Service Adapter (Deprecated).

DEPRECATION WARNING: Canonical worldline ownership moved to:
    services.agribrain.world_model.canonical_worldline.CanonicalWorldlineService

This module remains as a thin delegating adapter for backward compatibility.

Delegation rules enforced:
  1. One-way delegation only to CanonicalWorldlineService.
  2. Does NOT calculate event IDs internally.
  3. Does NOT maintain its own sequence or latest head.
  4. Does NOT perform dual writes.
  5. Does NOT modify payloads.
  6. Does NOT accept caller-supplied canonical event IDs.
  7. Does NOT silently fall back to legacy implementation.

Lifecycle plan:
  R5.0: Adapter introduced, all writes canonical.
  R5.1: Internal callers migrated.
  R5.2: External import warnings become errors in tests.
  R5.3: Adapter removed after artifact compatibility review.
"""

from __future__ import annotations

import logging
import math
import warnings
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

try:
    from services.agribrain.world_model.canonical_worldline import (
        CANONICAL_WORLDLINE_ROOT,
        WORLDLINE_CONTRACT_VERSION,
        CanonicalWorldlineService,
        WorldlineEventProposal,
        _public,
        _stable,
    )
except ImportError:
    try:
        from world_model.canonical_worldline import (
            CANONICAL_WORLDLINE_ROOT,
            WORLDLINE_CONTRACT_VERSION,
            CanonicalWorldlineService,
            WorldlineEventProposal,
            _public,
            _stable,
        )
    except ImportError:
        from ...world_model.canonical_worldline import (
            CANONICAL_WORLDLINE_ROOT,
            WORLDLINE_CONTRACT_VERSION,
            CanonicalWorldlineService,
            WorldlineEventProposal,
            _public,
            _stable,
        )
from ..config import (
    AUTHORITY_CONTRACT_VERSION,
    STATE_SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)

# Keep for backward compatibility of constants
WORLDLINE_ROOT = CANONICAL_WORLDLINE_ROOT


class PlotWorldlineService:
    """Delegating adapter for PlotWorldlineService.

    Delegates all reads and writes to CanonicalWorldlineService.
    Does not maintain separate state or perform dual writes.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        warnings.warn(
            "layer05_asmae.history.worldline_service.PlotWorldlineService is deprecated. "
            "Use services.agribrain.world_model.canonical_worldline.CanonicalWorldlineService.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._canonical = CanonicalWorldlineService(root=root)
        self.root = self._canonical.root

    def _head_path(self, plot_id: str) -> Path:
        return self._canonical._head_path(plot_id)

    def _event_path(self, plot_id: str, event_id: str) -> Path:
        return self._canonical._event_path(plot_id, event_id)

    def load_head(
        self, plot_id: str, tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Delegate head read to canonical service."""
        return self._canonical.load_head(plot_id, tenant_id, namespace)

    def load_event(
        self, plot_id: str, event_id: str,
        tenant_id: str = "default_tenant", namespace: str = "default",
    ) -> Dict[str, Any]:
        """Delegate event read to canonical service."""
        return self._canonical.load_event(plot_id, event_id, tenant_id, namespace)

    def commit_event(
        self,
        *,
        plot_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        geometry_hash: str = "",
        effective_at: Optional[Any] = None,
        observation_or_valid_time: Optional[Any] = None,
        parent_event_ids: Optional[Iterable[Any]] = None,
        authority: str = "",
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Delegate event commit to canonical service via proposal.

        Adapter does NOT compute event_id or maintain separate sequence/head.
        """
        if not str(authority or "").strip():
            raise ValueError("authority is required for worldline writes")
        if not str(geometry_hash or "").strip():
            raise ValueError("geometry_hash is required for worldline writes")

        payload_dict = dict(payload or {})
        if effective_at is None or not str(effective_at).strip():
            raise ValueError("effective_at is required for worldline writes")
        if observation_or_valid_time is None or not str(
            observation_or_valid_time
        ).strip():
            raise ValueError(
                "observation_or_valid_time is required for worldline writes"
            )
        valid_time = observation_or_valid_time
        if hasattr(valid_time, "isoformat"):
            valid_time = valid_time.isoformat()

        parents = tuple(parent_event_ids or ())

        proposal = WorldlineEventProposal(
            event_type=str(event_type),
            payload=payload_dict,
            parent_event_ids=parents,
            geometry_version=str(geometry_hash),
            evidence_set_hash=_stable(payload or {}),
            model_version="asmae_v0.5.0",
            calibration_version="",
            authority_contract_version=AUTHORITY_CONTRACT_VERSION,
            authority_ref=str(authority),
            state_schema_version=STATE_SCHEMA_VERSION,
            observation_or_valid_time=str(valid_time),
        )

        return self._canonical.commit_proposal(
            plot_id=plot_id,
            proposal=proposal,
            effective_at=effective_at,
            tenant_id=tenant_id,
            namespace=namespace,
        )

    def latest_payload(
        self, plot_id: str, event_type: str,
        tenant_id: str = "default_tenant", namespace: str = "default",
    ) -> Dict[str, Any]:
        """Retrieve latest payload for a specific event_type."""
        head = self.load_head(plot_id, tenant_id, namespace)
        event_id = (head.get("latest_by_type") or {}).get(event_type)
        event = (
            self.load_event(plot_id, str(event_id), tenant_id, namespace)
            if event_id else {}
        )
        payload = event.get("payload")
        if not isinstance(payload, dict):
            return {}
        result = dict(payload)
        result["_worldline_event_id"] = event.get("event_id")
        return result

    def hydrate_context(
        self,
        plot_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Hydrate missing live inputs from one geometry-compatible worldline."""
        geometry_hash = str(context.get("geometry_hash", "") or "")
        tenant_id = str(context.get("tenant_id") or "default_tenant")
        namespace = str(context.get("worldline_namespace") or "default")
        archive_event = self.latest_payload(
            plot_id, "ARCHIVE_POSTERIOR_VALIDATED", tenant_id, namespace
        )
        archive = archive_event.get("archive_posterior")
        if (
            not context.get("archive_posterior")
            and isinstance(archive, dict)
            and archive.get("geometry_hash") == geometry_hash
        ):
            context["archive_posterior"] = archive
            context["archive_metrics"] = archive_event.get(
                "historical_metrics", {}
            )
            context["archive_baselines"] = archive_event.get("baseline", {})
            context["archive_bma"] = archive_event.get("archive_bma", {})
            context["retrovalidation_residuals"] = archive_event.get(
                "retrovalidation", {}
            )
            context["archive_metrics_hash"] = archive_event.get(
                "archive_metrics_hash"
            ) or _stable(archive_event)
            context["archive_metrics_status"] = "available"
            context["worldline_archive_event_id"] = archive_event.get(
                "_worldline_event_id"
            )

        crop_payload = self.latest_payload(
            plot_id, "CROP_POSTERIOR", tenant_id, namespace
        )
        if crop_payload and not context.get("crop_posterior"):
            crop_posterior = crop_payload.get("crop_posterior", {})
            context["crop_posterior"] = crop_posterior
            context["crop_posterior_lineage"] = crop_payload.get(
                "content_hash"
            ) or crop_posterior.get(
                "content_hash"
            ) or _stable(crop_payload)
            context["crop_lineage_id"] = crop_posterior.get(
                "lineage_id"
            )
        context["plot_worldline_head"] = self.load_head(
            plot_id, tenant_id, namespace
        )
        return context

    def commit_asmae_result(
        self,
        result: Mapping[str, Any],
        *,
        geometry_hash: str,
        snapshot_ref: str = "",
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> Dict[str, Any]:
        artifact = dict(result.get("plot_state_artifact") or {})
        if not artifact:
            return {}
        event_type = (
            "CURRENT_POSTERIOR_VALIDATED"
            if bool(
                (result.get("diagnostics") or {}).get(
                    "scientific_production_usable", False
                )
            )
            else "CURRENT_POSTERIOR_DIAGNOSTIC"
        )
        artifact_time = str(artifact.get("as_of") or "").strip()
        artifact_authority = str(
            artifact.get("authority_level") or ""
        ).strip()
        if not artifact_time:
            raise ValueError("plot-state artifact as_of is required")
        if not artifact_authority:
            raise ValueError("plot-state artifact authority_level is required")
        event = self.commit_event(
            plot_id=str(result.get("plot_id", "")),
            event_type=event_type,
            geometry_hash=geometry_hash,
            effective_at=artifact_time,
            observation_or_valid_time=artifact_time,
            authority=artifact_authority,
            tenant_id=tenant_id,
            namespace=namespace,
            payload={
                "plot_state_artifact": artifact,
                "output_content_hash": result.get("content_hash"),
                "snapshot_ref": snapshot_ref,
                "archive_update_candidate": event_type
                == "CURRENT_POSTERIOR_VALIDATED",
            },
        )
        return event

    def commit_acquisition_plan(
        self,
        *,
        plot_id: str,
        geometry_hash: str,
        reason: str,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> Dict[str, Any]:
        event_time = datetime.now(timezone.utc)
        return self.commit_event(
            plot_id=plot_id,
            event_type="ARCHIVE_ACQUISITION_PLAN",
            geometry_hash=geometry_hash,
            authority="DIAGNOSTIC",
            effective_at=event_time,
            observation_or_valid_time=event_time,
            tenant_id=tenant_id,
            namespace=namespace,
            payload={
                "status": "needs_observations",
                "reason": reason,
                "requested_sources": ["sentinel2", "sentinel1", "weather"],
                "synthetic_observations_allowed": False,
            },
        )

    def refresh_archive_from_context(
        self,
        *,
        plot_id: str,
        geometry_hash: str,
        context: Mapping[str, Any],
        tenant_id: str = "",
        namespace: str = "",
    ) -> Dict[str, Any]:
        """Run historical filter from admitted real archive records."""
        tenant_id = str(
            tenant_id or context.get("tenant_id") or "default_tenant"
        )
        namespace = str(
            namespace or context.get("worldline_namespace") or "default"
        )
        raw_records = (
            context.get("historical_scene_records")
            or context.get("archive_scene_records")
            or []
        )
        records = list(raw_records) if isinstance(raw_records, (list, tuple)) else []
        if not records:
            event = self.commit_acquisition_plan(
                plot_id=plot_id,
                geometry_hash=geometry_hash,
                reason="no_admitted_historical_scene_records",
                tenant_id=tenant_id,
                namespace=namespace,
            )
            return {"status": "acquisition_required", "event_id": event.get("event_id")}

        from layer0.archive.scene_manifest import validate_scene_for_asmae

        admitted = [
            record for record in records
            if getattr(record, "geometry_hash", None) == geometry_hash
            and validate_scene_for_asmae(record)
        ]
        distinct: Dict[str, Any] = {}
        for record in admitted:
            content_hash = str(getattr(record, "source_content_hash", "") or "")
            if content_hash:
                distinct.setdefault(content_hash, record)
        admitted = sorted(
            distinct.values(),
            key=lambda item: str(getattr(item, "acquisition_time", "")),
        )
        if len(admitted) < 3:
            event = self.commit_acquisition_plan(
                plot_id=plot_id,
                geometry_hash=geometry_hash,
                reason="fewer_than_three_content_distinct_admitted_scenes",
                tenant_id=tenant_id,
                namespace=namespace,
            )
            return {
                "status": "insufficient_archive_evidence",
                "admitted_scene_count": len(admitted),
                "event_id": event.get("event_id"),
            }

        from .historical_assimilation_runner import HistoricalAssimilationRunner
        from .historical_stack_builder import HistoricalStackBuilder
        from ..resilient_posterior import (
            build_archive_posterior_contract,
            build_historical_state_support_ledger,
        )
        from ..retrovalidation.yearly_backtest import YearlyBacktest
        from .archive_metrics_store import ArchiveMetricsStore
        from .weather_archive_adapter import normalize_weather_archive

        stack = HistoricalStackBuilder().build_stack(
            plot_id, geometry_hash, admitted
        )
        weather = normalize_weather_archive(
            context.get("weather_archive")
            or context.get("weather_context")
            or context.get("weather_records")
        )
        daily_weather = dict(weather.get("weather_daily_series") or {})
        runner = HistoricalAssimilationRunner(
            str(Path(__file__).resolve().parents[4])
        )
        historical_output = runner.run_assimilation(
            plot_id,
            geometry_hash,
            stack,
            daily_weather,
            crop_params=dict(context.get("crop_context") or {}),
            management_events=context.get("management_events"),
        )
        backtest = YearlyBacktest(runner).run_backtest(
            plot_id, geometry_hash, stack.scenes, daily_weather
        )
        r2 = backtest.get("r2")
        validation_pass = bool(
            backtest.get("status") == "success"
            and isinstance(r2, (int, float))
            and not isinstance(r2, bool)
            and math.isfinite(float(r2))
            and int(backtest.get("num_folds", 0) or 0) > 0
            and float(r2) >= 0.5
        )
        support = build_historical_state_support_ledger(stack, daily_weather)
        archive_posterior = build_archive_posterior_contract(
            historical_output,
            crop_context=dict(context.get("crop_context") or {}),
            scene_ids=[
                str(getattr(record, "scene_id", "")) for record in admitted
            ],
            historical_validation_status=(
                "validated" if validation_pass else "failed"
            ),
            state_support_ledger=support,
        )
        historical_metrics = {
            "archive_policy_version": "plot_worldline_archive_v1",
            "scene_count": len(admitted),
            "content_distinct_scene_count": len(distinct),
            "date_start": str(getattr(admitted[0], "acquisition_time", "")),
            "date_end": str(getattr(admitted[-1], "acquisition_time", "")),
            "diagnostics": _public(
                getattr(historical_output, "diagnostics", {})
            ),
        }
        retrovalidation = {
            "retrovalidation_policy_version": "worldline_yearly_backtest_v1",
            **_public(backtest),
        }
        archive_bma = {
            "archive_bma_policy_version": "worldline_archive_bma_v1",
            "status": "unavailable",
            "reason": "independent_archive_expert_scoring_not_supplied",
            "weights": {},
        }
        baseline = {
            "baseline_policy_version": "worldline_baseline_v1",
            "status": "pending_season_profile_builder",
        }
        archive_run_id = _stable({
            "plot_id": plot_id,
            "geometry_hash": geometry_hash,
            "scene_hashes": sorted(distinct),
            "weather_hash": weather.get("weather_archive_hash"),
        })[:24]
        store = ArchiveMetricsStore()
        store.save_all_metrics(
            plot_id,
            geometry_hash,
            archive_run_id,
            historical_metrics,
            retrovalidation,
            archive_bma,
            baseline,
            archive_posterior=archive_posterior,
        )
        metrics_info = store.get_latest_metrics_info(plot_id) or {}
        event_type = (
            "ARCHIVE_POSTERIOR_VALIDATED"
            if validation_pass
            else "ARCHIVE_POSTERIOR_REJECTED"
        )
        event = self.commit_event(
            plot_id=plot_id,
            event_type=event_type,
            geometry_hash=geometry_hash,
            effective_at=archive_posterior.get("last_update_date"),
            observation_or_valid_time=archive_posterior.get(
                "last_update_date"
            ),
            authority="RETROVALIDATED" if validation_pass else "DIAGNOSTIC",
            tenant_id=tenant_id,
            namespace=namespace,
            parent_event_ids=[
                str(value) for value in [
                    context.get("archive_trigger_event_id")
                ] if value
            ],
            payload={
                "archive_posterior": archive_posterior,
                "historical_metrics": historical_metrics,
                "retrovalidation": retrovalidation,
                "archive_bma": archive_bma,
                "baseline": baseline,
                "archive_metrics_hash": metrics_info.get(
                    "archive_metrics_hash"
                ),
                "archive_run_id": archive_run_id,
            },
        )
        return {
            "status": "validated" if validation_pass else "rejected",
            "archive_run_id": archive_run_id,
            "event_id": event.get("event_id"),
            "archive_posterior": archive_posterior,
        }

"""Unified Orchestrator for ASMAE Historical State Intelligence.

Wires all four Historical State Intelligence pillars end-to-end atop verified
OBSERVATION_QUALIFIED canonical worldline events and ERA5 weather:
  1. Chronological 13-state ASMAE reconstruction & versioned posterior checkpoints
  2. Event reconstruction & scientific memory (observed vs hypothesis + outcome measurement)
  3. Incremental continuation & non-destructive late-arrival replay
  4. Causal retrovalidation, BMA expert vs baseline comparisons, calibration & seasonal skill
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.agribrain.layer0.asmae_scene_products.scene_product_store import SceneProductStore
from services.agribrain.layer05_asmae.history.archive_bootstrap_service import (
    ArchiveBootstrapService,
    MISSION_START_DATE,
)
from services.agribrain.layer05_asmae.history.historical_event_memory import (
    HistoricalEventMemory,
)
from services.agribrain.layer05_asmae.history.historical_retrovalidation import (
    HistoricalRetrovalidator,
)
from services.agribrain.layer05_asmae.history.historical_state_reconstructor import (
    HistoricalStateReconstructor,
)
from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService


class HistoricalStateIntelligenceService:
    """End-to-end Historical State Intelligence service."""

    def __init__(
        self,
        *,
        worldline: Optional[CanonicalWorldlineService] = None,
        bootstrap_root: Optional[Path] = None,
        checkpoint_root: Optional[Path] = None,
        scene_store: Optional[SceneProductStore] = None,
        n_ensemble: int = 25,
        checkpoint_stride: int = 20,
    ) -> None:
        self.worldline = worldline or CanonicalWorldlineService()
        self.bootstrap = ArchiveBootstrapService(
            worldline=self.worldline,
            bootstrap_root=bootstrap_root,
        )
        self.reconstructor = HistoricalStateReconstructor(
            worldline=self.worldline,
            checkpoint_root=checkpoint_root,
            scene_store=scene_store,
            n_ensemble=n_ensemble,
            checkpoint_stride=checkpoint_stride,
        )
        self.event_memory = HistoricalEventMemory()
        self.retrovalidator = HistoricalRetrovalidator()

    def run_full_intelligence(
        self,
        *,
        plot_id: str,
        geometry_hash: str,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        start_date: str = MISSION_START_DATE,
        target_end_date: Optional[str] = None,
        window_days: int = 180,
        polygon_geojson: Optional[Dict[str, Any]] = None,
        daily_weather: Optional[Dict[str, Dict[str, Any]]] = None,
        crop_context: Optional[Dict[str, Any]] = None,
        soil_context: Optional[Dict[str, Any]] = None,
        management_events: Optional[List[Any]] = None,
        valid_time_T: Optional[Any] = None,
        knowledge_cutoff_K: Optional[Any] = None,
        skip_bootstrap: bool = False,
        emit_worldline_posterior: bool = True,
    ) -> Dict[str, Any]:
        """Bootstrap/extend OBSERVATION_QUALIFIED acquisitions and reconstruct 13-state intelligence."""
        end_iso = target_end_date or datetime.now(timezone.utc).isoformat()
        bootstrap_res: Dict[str, Any] = {"status": "SKIPPED"}
        if not skip_bootstrap:
            bootstrap_res = self.bootstrap.run_bootstrap(
                plot_id=plot_id,
                geometry_hash=geometry_hash,
                tenant_id=tenant_id,
                namespace=namespace,
                start_date=start_date,
                target_end_date=end_iso,
                window_days=window_days,
                polygon_geojson=polygon_geojson,
            )

        recon_res = self.reconstructor.reconstruct(
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            tenant_id=tenant_id,
            namespace=namespace,
            valid_time_T=valid_time_T or end_iso,
            knowledge_cutoff_K=knowledge_cutoff_K,
            daily_weather=daily_weather,
            crop_context=crop_context,
            soil_context=soil_context,
            management_events=management_events,
            polygon_geojson=polygon_geojson,
            emit_worldline_posterior=emit_worldline_posterior,
            event_memory_fn=lambda traj, ctx: self.event_memory.reconstruct_memory(traj, ctx),
            retrovalidation_fn=lambda traj, ctx: self.retrovalidator.evaluate(traj, ctx),
        )

        return {
            "status": recon_res.get("status"),
            "plot_id": plot_id,
            "geometry_hash": geometry_hash,
            "bootstrap": {
                "status": bootstrap_res.get("status"),
                "resumed": bootstrap_res.get("resumed"),
                "total_events_committed": bootstrap_res.get("total_events_committed"),
                "total_gaps_recorded": bootstrap_res.get("total_gaps_recorded"),
            },
            "reconstruction": recon_res,
        }

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
import tempfile
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
        use_cross_layer_priors: bool = True,
        compare_ablation: bool = True,
        crop_fusion: Optional[Dict[str, Any]] = None,
        domain_chronology: Optional[Any] = None,
        enforce_weather_publication_lag: bool = True,
        n_calibrated_field_device_days: int = 0,
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

        eff_T = valid_time_T or end_iso
        eff_K = knowledge_cutoff_K or eff_T
        dom_id_dict = (
            domain_chronology.identity.to_dict()
            if domain_chronology is not None and hasattr(domain_chronology, "identity")
            else {}
        )
        recon_res = self.reconstructor.reconstruct(
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            tenant_id=tenant_id,
            namespace=namespace,
            valid_time_T=eff_T,
            knowledge_cutoff_K=knowledge_cutoff_K,
            daily_weather=daily_weather,
            crop_context=crop_context,
            soil_context=soil_context,
            management_events=management_events,
            polygon_geojson=polygon_geojson,
            emit_worldline_posterior=emit_worldline_posterior,
            use_cross_layer_priors=use_cross_layer_priors,
            crop_fusion=crop_fusion,
            domain_chronology=domain_chronology,
            enforce_weather_publication_lag=enforce_weather_publication_lag,
            event_memory_fn=lambda traj, ctx: self.event_memory.reconstruct_memory(
                traj,
                {**ctx, "valid_time_T": eff_T, "knowledge_cutoff_K": eff_K},
            ),
            retrovalidation_fn=lambda traj, ctx: self.retrovalidator.evaluate(
                traj,
                {
                    **ctx,
                    "domain_identity": dom_id_dict,
                    "crop_fusion": crop_fusion or {},
                    "n_calibrated_field_device_days": n_calibrated_field_device_days,
                },
            ),
        )
        if crop_fusion and recon_res.get("trajectory"):
            from .historical_crop_fusion import apply_post_asmae_crop_refinement
            crop_fusion = apply_post_asmae_crop_refinement(
                dict(crop_fusion),
                recon_res.get("trajectory") or [],
                run_id=f"hist_intel_{plot_id}",
            )

        ablation_res: Dict[str, Any] = {}
        if compare_ablation and use_cross_layer_priors:
            with tempfile.TemporaryDirectory() as tmp_cp_dir:
                ablation_recon = HistoricalStateReconstructor(
                    worldline=self.worldline,
                    checkpoint_root=Path(tmp_cp_dir),
                    scene_store=self.reconstructor.scene_store,
                    n_ensemble=self.reconstructor.n_ensemble,
                    checkpoint_stride=self.reconstructor.checkpoint_stride,
                )
                s1_s2_only_res = ablation_recon.reconstruct(
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
                    emit_worldline_posterior=False,
                    use_cross_layer_priors=False,
                    event_memory_fn=None,
                    retrovalidation_fn=lambda traj, ctx: self.retrovalidator.evaluate(
                        traj, {**ctx, "as_issued_query_fn": None}
                    ),
                )
            ablation_res = self.retrovalidator.compare_cross_layer_ablation(
                recon_res.get("retrovalidation") or {},
                s1_s2_only_res.get("retrovalidation") or {},
            )

        manifest_reconcile = dict(bootstrap_res.get("manifest_reconciliation") or {})
        lean_crop_fusion = None
        if isinstance(crop_fusion, dict):
            lean_crop_fusion = {
                k: (
                    [{sk: sv for sk, sv in s.items() if sk != "raw_posterior"} for s in v]
                    if k == "seasonal_timeline" and isinstance(v, list)
                    else ({sk: sv for sk, sv in v.items() if sk != "raw_posterior"} if k == "latest_crop_posterior" and isinstance(v, dict) else v)
                )
                for k, v in crop_fusion.items()
                if k not in {"full_segmentation_receipt", "_causal_prefix_cache"}
            }
        return {
            "world_model_contract_version": "asmae_world_model_v2",
            "status": recon_res.get("status"),
            "plot_id": plot_id,
            "geometry_hash": geometry_hash,
            "bootstrap": {
                "status": bootstrap_res.get("status"),
                "resumed": bootstrap_res.get("resumed"),
                "total_events_committed": bootstrap_res.get("total_events_committed"),
                "total_gaps_recorded": bootstrap_res.get("total_gaps_recorded"),
                "manifest_reconciliation": manifest_reconcile,
            },
            "manifest_reconciliation": manifest_reconcile,
            "cross_layer_intelligence": recon_res.get("cross_layer_intelligence") or {},
            "cross_layer_ablation": ablation_res,
            "reconstruction": recon_res,
            "domain_identity": dom_id_dict or None,
            "domain_chronology": domain_chronology.to_summary() if domain_chronology is not None else None,
            "crop_fusion": lean_crop_fusion,
        }

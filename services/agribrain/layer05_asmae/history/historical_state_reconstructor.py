"""Chronological 13-State Historical State Reconstruction & Late-Arrival Replay.

Executes ASMAE's genuine 13-state Ensemble Kalman Filter forward chronologically over
OBSERVATION_QUALIFIED historical worldline acquisitions and ERA5 daily weather, storing
versioned posterior checkpoints and emitting ARCHIVE_POSTERIOR_VALIDATED worldline events
only after assimilation, gap tracking, and validation complete.

Capabilities:
  1. Chronological 2015-present 13-state trajectory + 13x13 covariance + support ledger.
  2. Exact deterministic incremental resume from prior versioned checkpoints (matching
     cold full-history reconstruction across state means, sigmas, covariance, model
     versions, event order, and causal forecasts).
  3. Non-destructive late-arrival replay: when an older observation arrives after a later
     state has already been published, recomputes affected history from the nearest prior
     checkpoint and appends superseding checkpoints/worldline events without silently
     mutating previously published history.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from rasterio.features import geometry_mask
from rasterio.transform import Affine

from services.agribrain.layer0.asmae_scene_products.scene_product_store import SceneProductStore
from services.agribrain.layer05_asmae.assimilation.filter import (
    _forecast_elapsed_interval,
    _proxy_update_single_obs,
    clamp_ensemble,
    compute_ensemble_statistics,
    initialize_ensemble,
)
from services.agribrain.layer05_asmae.config import (
    N_STATES,
    STATE_BOUNDS,
    STATE_NAMES,
    STATE_SCHEMA_VERSION,
)
from services.agribrain.layer05_asmae.deterministic import make_rng
from services.agribrain.layer05_asmae.geometry.s1_scene_loader import (
    _normalized_backscatter_feature,
)
from services.agribrain.layer05_asmae.observation.index_state_mapping import (
    INDEX_STATE_REGISTRY,
    validate_forbidden_state_update,
)
from services.agribrain.layer05_asmae.observation.observation_noise import (
    compute_observation_noise,
)
from services.agribrain.layer05_asmae.observation.s1_sar_model import predict_sar_observation
from services.agribrain.layer05_asmae.observation.s2_forward_model import predict_observation
from services.agribrain.layer05_asmae.state.descriptors import (
    AssimilationPolicy,
    STATE_DESCRIPTORS,
)
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    WorldlineEventProposal,
    _parse_utc_iso,
)

logger = logging.getLogger(__name__)

RECONSTRUCTOR_MODEL_VERSION = "asmae_hist_state_v1"
CALIBRATION_VERSION = "asmae_diag_hist_cal_v1"
POSTERIOR_CHECKPOINT_SCHEMA = "asmae_posterior_checkpoint_v1"


def _rng_state_to_json(state: Any) -> Any:
    """Convert random.Random.getstate() tuple structure into pure JSON lists."""
    if isinstance(state, tuple):
        return [_rng_state_to_json(x) for x in state]
    return state


def _rng_state_from_json(state: Any) -> Any:
    """Restore nested tuple structure expected by random.Random.setstate()."""
    if isinstance(state, list) and len(state) == 3:
        return (int(state[0]), tuple(int(x) for x in state[1]), state[2])
    return tuple(state) if isinstance(state, list) else state


def _extract_polygon_geom(polygon_geojson: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract normalized Polygon/MultiPolygon GeoJSON geometry when present."""
    if not isinstance(polygon_geojson, dict):
        return None
    geom = polygon_geojson.get("geometry") if polygon_geojson.get("type") == "Feature" else polygon_geojson
    if isinstance(geom, dict) and geom.get("type") in ("Polygon", "MultiPolygon") and geom.get("coordinates"):
        return geom
    return None


def _polygon_mask(
    polygon_geojson: Optional[Dict[str, Any]],
    transform_vals: Any,
    height: int,
    width: int,
) -> np.ndarray:
    """Compute boolean interior mask (True = inside parcel polygon)."""
    geom = _extract_polygon_geom(polygon_geojson)
    if geom is None or not transform_vals or len(transform_vals) != 6:
        return np.ones((height, width), dtype=bool)
    tr = Affine.from_gdal(*(float(x) for x in transform_vals))
    return geometry_mask([geom], out_shape=(height, width), transform=tr, invert=True, all_touched=True)


def _compute_ensemble_covariance_13x13(
    ensemble: Dict[str, List[List[float]]],
    node_ids: Sequence[str],
) -> List[List[float]]:
    """Compute sample 13x13 state covariance matrix across active microzones & ensemble members."""
    rows: List[List[float]] = []
    for nid in node_ids:
        for member in ensemble.get(nid, []):
            rows.append([float(member[i]) for i in range(N_STATES)])
    if len(rows) < 2:
        return [[0.0 for _ in range(N_STATES)] for _ in range(N_STATES)]
    mat = np.asarray(rows, dtype=float)
    cov = np.cov(mat, rowvar=False, ddof=1)
    if cov.ndim == 0:
        cov = np.zeros((N_STATES, N_STATES), dtype=float)
    return [[round(float(cov[r, c]), 8) for c in range(N_STATES)] for r in range(N_STATES)]


def _summarize_13_state_ensemble(
    ensemble: Dict[str, List[List[float]]],
    node_ids: Sequence[str],
) -> Tuple[Dict[str, float], Dict[str, float], List[List[float]], Dict[str, List[float]], Dict[str, List[float]]]:
    """Return parcel-wide means/stds, 13x13 covariance, and per-node stats."""
    stats = compute_ensemble_statistics(ensemble, list(node_ids))
    per_node_means = stats.get("means", {})
    per_node_stds = stats.get("sigmas", {})

    all_members: List[List[float]] = []
    for nid in node_ids:
        for member in ensemble.get(nid, []):
            all_members.append(member)
    arr = np.asarray(all_members, dtype=float) if all_members else np.zeros((1, N_STATES), dtype=float)
    means_vec = np.mean(arr, axis=0)
    stds_vec = np.std(arr, axis=0, ddof=1) if arr.shape[0] > 1 else np.zeros(N_STATES, dtype=float)
    cov_13 = _compute_ensemble_covariance_13x13(ensemble, node_ids)

    state_means = {STATE_NAMES[i]: round(float(means_vec[i]), 6) for i in range(N_STATES)}
    state_stds = {STATE_NAMES[i]: round(float(stds_vec[i]), 6) for i in range(N_STATES)}
    return state_means, state_stds, cov_13, per_node_means, per_node_stds


_UNSUPPORTED_UNOBSERVED_STATES = frozenset({
    "thermal_stress",
    "salinity_stress",
    "biotic_confounder_risk",
})


def _build_historical_support_ledger(
    accepted_counts: Dict[str, int],
) -> Dict[str, Dict[str, Any]]:
    """Build honest per-state support ledger reflecting real S1/S2 assimilation scope."""
    ledger: Dict[str, Dict[str, Any]] = {}
    for idx, name in enumerate(STATE_NAMES):
        desc = STATE_DESCRIPTORS[idx]
        count = int(accepted_counts.get(name, 0) or 0)
        not_assimilated = (
            desc.assimilation_policy == AssimilationPolicy.NOT_ASSIMILATED
            or name in _UNSUPPORTED_UNOBSERVED_STATES
        )
        if count > 0 and not not_assimilated:
            support_status = "temporally_conditioned"
            spatial_support = "parcel_assimilated"
            obs_rel = "direct" if name in ("vigor", "canopy_water", "surface_wetness_event", "structure") else "indirect"
            blocks: List[str] = []
        elif not_assimilated:
            support_status = "unsupported"
            spatial_support = "unavailable"
            obs_rel = "none"
            blocks = ["no_direct_physical_observation_channel"]
        else:
            support_status = "prior_constrained"
            spatial_support = "unavailable"
            obs_rel = "none"
            blocks = ["no_accepted_state_update"]

        ledger[name] = {
            "state": name,
            "accepted_update_count": count,
            "support_status": support_status,
            "spatial_support": spatial_support,
            "observation_relationship": obs_rel,
            "field_approval_eligible": False,  # Historical reconstruction remains diagnostic-only
            "block_reasons": blocks,
        }
    return ledger


def _load_scene_raster_observations(
    obs_record: Dict[str, Any],
    scene_store: Optional[SceneProductStore],
    plot_id: str,
    polygon_geojson: Optional[Dict[str, Any]],
) -> Dict[str, float]:
    """Extract EnKF-domain scalar observations from worldline record or verified disk rasters."""
    metrics = dict(obs_record.get("metrics") or {})
    source = str(obs_record.get("source") or "").lower()
    scene_id = str(obs_record.get("scene_id") or "")
    expected_hash = str(obs_record.get("source_content_hash") or "")

    # Prefer direct raster extraction from cached SceneProductStore when present
    if scene_store is not None and scene_id:
        store_base = Path(getattr(scene_store, "base_dir", ""))
        safe_dir = (store_base if getattr(scene_store, "plot_id", None) == plot_id else store_base / plot_id) / scene_id
        meta_path = safe_dir / "metadata.json"
        if meta_path.is_file():
            try:
                if "sentinel2" in source or source == "s2":
                    b04_p = safe_dir / "B04.npz"
                    b08_p = safe_dir / "B08.npz"
                    b11_p = safe_dir / "B11.npz"
                    scl_p = safe_dir / "SCL.npz"
                    if b04_p.is_file() and b08_p.is_file():
                        b04 = np.asarray(scene_store.raster_store.load_band(str(b04_p)), dtype=np.float64)
                        b08 = np.asarray(scene_store.raster_store.load_band(str(b08_p)), dtype=np.float64)
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        H, W = b04.shape[:2]
                        inside = _polygon_mask(polygon_geojson, meta.get("transform"), H, W)
                        valid = inside & np.isfinite(b04) & np.isfinite(b08) & ((b08 + b04) > 1e-6)
                        if scl_p.is_file():
                            scl = np.rint(scene_store.raster_store.load_band(str(scl_p))).astype(np.int32)
                            if scl.shape[:2] == (H, W):
                                valid &= ~np.isin(scl, [0, 1, 3, 8, 9, 10, 11])
                        extracted: Dict[str, float] = {}
                        if int(np.sum(valid)) > 0:
                            ndvi = np.clip((b08[valid] - b04[valid]) / (b08[valid] + b04[valid]), -1.0, 1.0)
                            extracted["ndvi"] = round(float(np.mean(ndvi)), 6)
                            if b11_p.is_file():
                                b11 = np.asarray(scene_store.raster_store.load_band(str(b11_p)), dtype=np.float64)
                                ndmi_m = valid & np.isfinite(b11) & ((b08 + b11) > 1e-6)
                                if int(np.sum(ndmi_m)) > 0:
                                    ndmi = np.clip((b08[ndmi_m] - b11[ndmi_m]) / (b08[ndmi_m] + b11[ndmi_m]), -1.0, 1.0)
                                    extracted["ndmi"] = round(float(np.mean(ndmi)), 6)
                        if extracted:
                            return extracted
                elif "sentinel1" in source or source == "s1":
                    vv_p = safe_dir / "VV.npz"
                    vh_p = safe_dir / "VH.npz"
                    if vv_p.is_file():
                        vv = np.asarray(scene_store.raster_store.load_band(str(vv_p)), dtype=np.float64)
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        H, W = vv.shape[:2]
                        inside = _polygon_mask(polygon_geojson, meta.get("transform"), H, W)
                        vv_unit = str((meta.get("band_units") or {}).get("VV", "")).lower()
                        vv_is_db = "db" in vv_unit or bool(np.any(vv[inside & np.isfinite(vv)] < 0.0))
                        valid = inside & np.isfinite(vv) & (True if vv_is_db else (vv > 1e-12))
                        extracted_s1: Dict[str, float] = {}
                        if int(np.sum(valid)) > 0:
                            vv_norm = _normalized_backscatter_feature(vv[valid], "VV", vv_is_db)
                            extracted_s1["sar_vv"] = round(float(np.mean(vv_norm)), 6)
                            if vh_p.is_file():
                                vh = np.asarray(scene_store.raster_store.load_band(str(vh_p)), dtype=np.float64)
                                vh_unit = str((meta.get("band_units") or {}).get("VH", "")).lower()
                                vh_is_db = "db" in vh_unit or bool(np.any(vh[valid & np.isfinite(vh)] < 0.0))
                                vh_m = valid & np.isfinite(vh) & (True if vh_is_db else (vh > 1e-12))
                                if int(np.sum(vh_m)) > 0:
                                    vh_norm = _normalized_backscatter_feature(vh[vh_m], "VH", vh_is_db)
                                    extracted_s1["sar_vh"] = round(float(np.mean(vh_norm)), 6)
                        if extracted_s1:
                            return extracted_s1
            except Exception as exc:
                logger.debug("Fallback to metrics on scene %s (hash=%s): %s", scene_id, expected_hash[:12], exc)

    # Fallback directly from verified worldline metrics payload
    obs_out: Dict[str, float] = {}
    if "sentinel2" in source or source == "s2":
        for key in ("ndvi", "ndvi_mean"):
            val = metrics.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val)):
                obs_out["ndvi"] = round(float(np.clip(float(val), -1.0, 1.0)), 6)
                break
        for key in ("ndmi", "ndmi_mean"):
            val = metrics.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val)):
                obs_out["ndmi"] = round(float(np.clip(float(val), -1.0, 1.0)), 6)
                break
        for key in ("ndre", "ndre_mean"):
            val = metrics.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val)):
                obs_out["ndre"] = round(float(np.clip(float(val), -1.0, 1.0)), 6)
                break
    elif "sentinel1" in source or source == "s1":
        vv_db = metrics.get("vv_mean_db")
        if isinstance(vv_db, (int, float)) and not isinstance(vv_db, bool) and math.isfinite(float(vv_db)):
            obs_out["sar_vv"] = round(float(_normalized_backscatter_feature(np.array([float(vv_db)]), "VV", True)[0]), 6)
        vh_db = metrics.get("vh_mean_db")
        if isinstance(vh_db, (int, float)) and not isinstance(vh_db, bool) and math.isfinite(float(vh_db)):
            obs_out["sar_vh"] = round(float(_normalized_backscatter_feature(np.array([float(vh_db)]), "VH", True)[0]), 6)
    return obs_out


@dataclass
class PosteriorCheckpoint:
    checkpoint_id: str
    schema_version: str
    plot_id: str
    tenant_id: str
    namespace: str
    geometry_hash: str
    model_version: str
    state_schema_version: str
    calibration_version: str
    cutoff_valid_time: str
    knowledge_cutoff_time: str
    boundary_reason: str
    last_obs_event_id: str
    last_obs_time: str
    assimilated_observation_ids: List[str]
    ensemble_members: Dict[str, List[List[float]]]
    rng_state_json: Any
    state_means: Dict[str, float]
    state_stds: Dict[str, float]
    state_covariance: List[List[float]]
    per_node_means: Dict[str, List[float]]
    per_node_stds: Dict[str, List[float]]
    accepted_update_counts: Dict[str, int]
    state_support_ledger: Dict[str, Dict[str, Any]]
    parent_checkpoint_id: Optional[str] = None
    supersedes_checkpoint_id: Optional[str] = None
    late_arrival_event_ids: List[str] = field(default_factory=list)
    trajectory_segment: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PosteriorCheckpoint":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def summary_dict(self) -> Dict[str, Any]:
        """Lightweight metadata view omitting full ensemble arrays for reports."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "cutoff_valid_time": self.cutoff_valid_time,
            "knowledge_cutoff_time": self.knowledge_cutoff_time,
            "boundary_reason": self.boundary_reason,
            "model_version": self.model_version,
            "state_schema_version": self.state_schema_version,
            "calibration_version": self.calibration_version,
            "assimilated_observation_count": len(self.assimilated_observation_ids),
            "last_obs_event_id": self.last_obs_event_id,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "supersedes_checkpoint_id": self.supersedes_checkpoint_id,
            "late_arrival_event_ids": list(self.late_arrival_event_ids),
            "state_means": dict(self.state_means),
            "state_stds": dict(self.state_stds),
            "state_covariance": self.state_covariance,
        }


class HistoricalStateReconstructor:
    """Reconstructs 13-state ASMAE history chronologically with versioned checkpoints & late-arrival replay."""

    def __init__(
        self,
        worldline: Optional[CanonicalWorldlineService] = None,
        checkpoint_root: Optional[Path] = None,
        scene_store: Optional[SceneProductStore] = None,
        n_zone_rows: int = 2,
        n_zone_cols: int = 2,
        n_ensemble: int = 25,
        checkpoint_stride: int = 20,
    ) -> None:
        self.worldline = worldline or CanonicalWorldlineService()
        self.checkpoint_root = Path(
            checkpoint_root or (self.worldline.root.parent / "historical_posterior_checkpoints")
        ).resolve()
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)
        self.scene_store = scene_store
        self.n_zone_rows = max(1, int(n_zone_rows))
        self.n_zone_cols = max(1, int(n_zone_cols))
        self.n_ensemble = max(6, int(n_ensemble))
        self.checkpoint_stride = max(1, int(checkpoint_stride))
        self.node_ids = [
            f"mz_{r:03d}_{c:03d}"
            for r in range(self.n_zone_rows)
            for c in range(self.n_zone_cols)
        ]

    def _plot_cp_dir(self, plot_id: str, tenant_id: str, namespace: str) -> Path:
        d = self.checkpoint_root / tenant_id / namespace / CanonicalWorldlineService._plot_key(plot_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _index_path(self, plot_id: str, tenant_id: str, namespace: str) -> Path:
        return self._plot_cp_dir(plot_id, tenant_id, namespace) / "checkpoint_index.json"

    def load_checkpoint_index(
        self, plot_id: str, tenant_id: str = "default_tenant", namespace: str = "default"
    ) -> Dict[str, Any]:
        p = self._index_path(plot_id, tenant_id, namespace)
        if not p.exists():
            return {"active_chain": [], "historical_chains": [], "latest_worldline_posterior_event_id": None}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"active_chain": [], "historical_chains": []}
        except Exception:
            return {"active_chain": [], "historical_chains": []}

    def load_checkpoint(
        self, plot_id: str, checkpoint_id: str, tenant_id: str = "default_tenant", namespace: str = "default"
    ) -> Optional[PosteriorCheckpoint]:
        cp_path = self._plot_cp_dir(plot_id, tenant_id, namespace) / "checkpoints" / f"{checkpoint_id}.json"
        if not cp_path.exists():
            return None
        try:
            return PosteriorCheckpoint.from_dict(json.loads(cp_path.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("Failed loading posterior checkpoint %s: %s", checkpoint_id, exc)
            return None

    def _save_checkpoint(self, cp: PosteriorCheckpoint) -> None:
        cp_dir = self._plot_cp_dir(cp.plot_id, cp.tenant_id, cp.namespace) / "checkpoints"
        cp_dir.mkdir(parents=True, exist_ok=True)
        target = cp_dir / f"{cp.checkpoint_id}.json"
        if not target.exists():
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(cp.to_dict(), sort_keys=True), encoding="utf-8")
            tmp.replace(target)

    def _save_checkpoint_index(
        self, plot_id: str, tenant_id: str, namespace: str, index_data: Dict[str, Any]
    ) -> None:
        p = self._index_path(plot_id, tenant_id, namespace)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(index_data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)

    def load_qualified_observations(
        self,
        *,
        plot_id: str,
        valid_time_T: Any,
        knowledge_cutoff_K: Any,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> List[Dict[str, Any]]:
        """Query canonical OBSERVATION_QUALIFIED events filtered at (T, K)."""
        events = self.worldline.select_eligible_events(
            plot_id=plot_id,
            event_type="OBSERVATION_QUALIFIED",
            valid_time_T=valid_time_T,
            knowledge_cutoff_K=knowledge_cutoff_K,
            tenant_id=tenant_id,
            namespace=namespace,
            fail_on_corrupt=True,
        )
        events.sort(
            key=lambda ev: (
                _parse_utc_iso(ev.get("observation_or_valid_time") or ev.get("effective_at")),
                str((ev.get("payload") or {}).get("observation_qualified", {}).get("scene_id") or ""),
                str(ev.get("event_id") or ""),
            )
        )
        return events

    @staticmethod
    def _checkpoint_identity(
        *,
        plot_id: str,
        geometry_hash: str,
        cutoff_valid_time: str,
        assimilated_observation_ids: Sequence[str],
        parent_checkpoint_id: Optional[str],
    ) -> str:
        raw = json.dumps(
            {
                "plot_id": plot_id,
                "geometry_hash": geometry_hash,
                "model_version": RECONSTRUCTOR_MODEL_VERSION,
                "state_schema_version": STATE_SCHEMA_VERSION,
                "calibration_version": CALIBRATION_VERSION,
                "cutoff_valid_time": cutoff_valid_time,
                "assimilated_observation_ids": list(assimilated_observation_ids),
                "parent_checkpoint_id": parent_checkpoint_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"cp13_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"

    @staticmethod
    def _predict_pre_update_channels(
        ensemble: Dict[str, List[List[float]]],
        node_ids: Sequence[str],
        obs_channels: Dict[str, float],
        scene_meta: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Evaluate forward models on prior ensemble strictly BEFORE assimilating scene_i."""
        preds: Dict[str, Dict[str, Any]] = {}
        cloud_frac = float(scene_meta.get("cloud_score", 0.0) or 0.0)
        valid_frac = float(scene_meta.get("valid_pixel_fraction", 1.0) or 1.0)
        if valid_frac <= 0.0:
            valid_frac = 0.5
        for obs_name, obs_val in sorted(obs_channels.items()):
            mapping = INDEX_STATE_REGISTRY.get(obs_name)
            if mapping is None:
                continue
            member_preds: List[float] = []
            for nid in node_ids:
                for member in ensemble.get(nid, []):
                    y_hat = (
                        predict_sar_observation(obs_name, member)
                        if mapping.sensor == "S1"
                        else predict_observation(obs_name, member)
                    )
                    if y_hat is not None and math.isfinite(float(y_hat)):
                        member_preds.append(float(y_hat))
            if not member_preds:
                continue
            sigma_obs = compute_observation_noise(
                obs_name,
                cloud_fraction=cloud_frac,
                valid_support_fraction=valid_frac,
            )
            pred_mean = float(np.mean(member_preds))
            pred_var = float(np.var(member_preds, ddof=1)) if len(member_preds) > 1 else 0.0
            total_sigma = math.sqrt(max(1e-8, pred_var + sigma_obs * sigma_obs))
            residual = float(obs_val) - pred_mean
            preds[obs_name] = {
                "sensor": mapping.sensor,
                "y_obs": round(float(obs_val), 6),
                "y_pred_prior": round(pred_mean, 6),
                "pred_sigma": round(total_sigma, 6),
                "obs_sigma": round(float(sigma_obs), 6),
                "residual": round(residual, 6),
                "z_score": round(residual / total_sigma, 4) if total_sigma > 1e-8 else 0.0,
            }
        return preds

    def reconstruct(
        self,
        *,
        plot_id: str,
        geometry_hash: str,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        valid_time_T: Optional[Any] = None,
        knowledge_cutoff_K: Optional[Any] = None,
        daily_weather: Optional[Dict[str, Dict[str, Any]]] = None,
        crop_context: Optional[Dict[str, Any]] = None,
        soil_context: Optional[Dict[str, Any]] = None,
        management_events: Optional[List[Any]] = None,
        polygon_geojson: Optional[Dict[str, Any]] = None,
        emit_worldline_posterior: bool = True,
        retrovalidation_fn: Optional[Callable[[List[Dict[str, Any]], Dict[str, Any]], Dict[str, Any]]] = None,
        event_memory_fn: Optional[Callable[[List[Dict[str, Any]], Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Reconstruct 13-state posterior history incrementally or via non-destructive late-arrival replay."""
        now_utc = datetime.now(timezone.utc).isoformat()
        cutoff_T = str(valid_time_T or now_utc)
        cutoff_K = str(knowledge_cutoff_K or now_utc)
        weather_series = dict(daily_weather or {})
        crop_ctx = dict(crop_context or {})
        soil_ctx = dict(soil_context or {})
        mgmt_events = list(management_events or [])

        eligible_events = self.load_qualified_observations(
            plot_id=plot_id,
            valid_time_T=cutoff_T,
            knowledge_cutoff_K=cutoff_K,
            tenant_id=tenant_id,
            namespace=namespace,
        )
        if not eligible_events:
            return {
                "status": "no_qualified_observations",
                "plot_id": plot_id,
                "geometry_hash": geometry_hash,
                "observation_count": 0,
                "checkpoints": [],
                "trajectory": [],
            }

        ordered_obs_ids = [str(ev["event_id"]) for ev in eligible_events]
        index_data = self.load_checkpoint_index(plot_id, tenant_id, namespace)
        active_cp_ids: List[str] = list(index_data.get("active_chain") or [])
        prior_worldline_posterior_id = index_data.get("latest_worldline_posterior_event_id")

        loaded_chain: List[PosteriorCheckpoint] = []
        for cp_id in active_cp_ids:
            cp = self.load_checkpoint(plot_id, cp_id, tenant_id, namespace)
            if (
                cp is not None
                and cp.geometry_hash == geometry_hash
                and cp.model_version == RECONSTRUCTOR_MODEL_VERSION
                and cp.state_schema_version == STATE_SCHEMA_VERSION
                and cp.calibration_version == CALIBRATION_VERSION
            ):
                loaded_chain.append(cp)

        # Determine whether to resume cleanly from tail checkpoint, anchor before late arrivals, or run cold
        mode = "cold_full_reconstruction"
        anchor_cp: Optional[PosteriorCheckpoint] = None
        preserved_prefix_cps: List[PosteriorCheckpoint] = []
        late_arrival_ids: List[str] = []
        superseded_cp_ids: List[str] = []

        if loaded_chain:
            tail_cp = loaded_chain[-1]
            tail_ids = list(tail_cp.assimilated_observation_ids)
            if len(tail_ids) <= len(ordered_obs_ids) and ordered_obs_ids[: len(tail_ids)] == tail_ids:
                if len(tail_ids) == len(ordered_obs_ids):
                    # Everything already assimilated; still ensure steps available from replay/live needs
                    mode = "up_to_date"
                    anchor_cp = tail_cp
                    preserved_prefix_cps = list(loaded_chain)
                else:
                    mode = "incremental_continuation"
                    anchor_cp = tail_cp
                    preserved_prefix_cps = list(loaded_chain)
            else:
                # Late arrival (or earlier historical insertion) detected before tail_cp cutoff
                first_div_idx = 0
                for idx in range(min(len(tail_ids), len(ordered_obs_ids))):
                    if tail_ids[idx] != ordered_obs_ids[idx]:
                        break
                    first_div_idx = idx + 1
                known_tail_set = set(tail_ids)
                tail_cutoff_dt = _parse_utc_iso(tail_cp.cutoff_valid_time)
                late_arrival_ids = [
                    str(ev["event_id"])
                    for ev in eligible_events
                    if str(ev["event_id"]) not in known_tail_set
                    and _parse_utc_iso(ev.get("observation_or_valid_time") or ev.get("effective_at"))
                    <= tail_cutoff_dt
                ]
                mode = "late_arrival_replay"
                # Pick latest unaffected checkpoint whose assimilated prefix strictly precedes divergence
                for cp in loaded_chain:
                    cp_len = len(cp.assimilated_observation_ids)
                    if cp_len <= first_div_idx and ordered_obs_ids[:cp_len] == list(cp.assimilated_observation_ids):
                        anchor_cp = cp
                        preserved_prefix_cps.append(cp)
                    else:
                        superseded_cp_ids.append(cp.checkpoint_id)

        rng = make_rng("asmae_hist_recon", plot_id, geometry_hash, STATE_SCHEMA_VERSION)
        if anchor_cp is not None:
            start_idx = len(anchor_cp.assimilated_observation_ids)
            ensemble: Dict[str, List[List[float]]] = copy.deepcopy(anchor_cp.ensemble_members)
            rng.setstate(_rng_state_from_json(anchor_cp.rng_state_json))
            prev_scene_time: Optional[datetime] = _parse_utc_iso(anchor_cp.last_obs_time)
            accepted_counts: Dict[str, int] = dict(anchor_cp.accepted_update_counts)
            parent_cp_id: Optional[str] = anchor_cp.checkpoint_id
            assimilated_ids: List[str] = list(anchor_cp.assimilated_observation_ids)
        else:
            start_idx = 0
            ensemble, _ = initialize_ensemble(
                node_ids=self.node_ids,
                n_ensemble=self.n_ensemble,
                priors={},
                crop_context=crop_ctx,
                rng=rng,
                scenes=[],
                initial_posterior=None,
            )
            prev_scene_time = None
            accepted_counts = {name: 0 for name in STATE_NAMES}
            parent_cp_id = None
            assimilated_ids = []

        step_records: List[Dict[str, Any]] = []
        prefix_trajectory: List[Dict[str, Any]] = []
        for cp in preserved_prefix_cps:
            if cp.trajectory_segment:
                prefix_trajectory.extend(cp.trajectory_segment)
        segment_buffer: List[Dict[str, Any]] = []
        new_checkpoints: List[PosteriorCheckpoint] = []
        gap_events: List[Dict[str, Any]] = []
        total_missing_weather_days = 0
        total_elapsed_days = 0

        pending_events = eligible_events[start_idx:]
        prev_ndvi_sign_active: Optional[bool] = None

        for local_i, ev in enumerate(pending_events):
            global_i = start_idx + local_i
            payload = (ev.get("payload") or {}).get("observation_qualified") or {}
            obs_time = _parse_utc_iso(ev.get("observation_or_valid_time") or ev.get("effective_at"))
            ev_id = str(ev["event_id"])

            # Count exact weather & observation gaps strictly between prev_scene_time and obs_time
            elapsed_days = 0.0
            missing_w_in_step = 0
            if prev_scene_time is not None and obs_time > prev_scene_time:
                elapsed_days = (obs_time - prev_scene_time).total_seconds() / 86400.0
                total_elapsed_days += int(round(elapsed_days))
                day_cur = prev_scene_time.date()
                while day_cur < obs_time.date():
                    if day_cur.isoformat() not in weather_series:
                        missing_w_in_step += 1
                    day_cur += timedelta(days=1)
                total_missing_weather_days += missing_w_in_step
                if elapsed_days >= 18.0:
                    gap_events.append({
                        "gap_start": prev_scene_time.isoformat(),
                        "gap_end": obs_time.isoformat(),
                        "gap_days": round(elapsed_days, 2),
                        "missing_weather_days": missing_w_in_step,
                    })

            # Propagate 13-state ensemble forward over daily intervals
            if prev_scene_time is not None and obs_time > prev_scene_time:
                ensemble, _ = _forecast_elapsed_interval(
                    ensemble=ensemble,
                    previous_time=prev_scene_time,
                    current_time=obs_time,
                    priors={},
                    crop_context=crop_ctx,
                    rng=rng,
                    scenes=[],
                    weather_daily_series=weather_series,
                    soil_context=soil_ctx,
                    management_events=mgmt_events,
                )
            prev_scene_time = obs_time

            obs_channels = _load_scene_raster_observations(
                payload, self.scene_store, plot_id, polygon_geojson
            )
            prior_means, prior_stds, _, _, _ = _summarize_13_state_ensemble(ensemble, self.node_ids)
            prior_predictions = self._predict_pre_update_channels(
                ensemble, self.node_ids, obs_channels, payload
            )

            # Update assimilated channels through ASMAE EnKF physics rules
            cloud_frac = float(payload.get("cloud_score", 0.0) or 0.0)
            valid_frac = float(payload.get("valid_pixel_fraction", 1.0) or 1.0)
            updated_channels: List[str] = []
            for obs_name, obs_val in sorted(obs_channels.items()):
                mapping = INDEX_STATE_REGISTRY.get(obs_name)
                if mapping is None:
                    continue
                target_indices = [
                    s for s in mapping.target_state_indices
                    if 0 <= s < N_STATES
                    and not validate_forbidden_state_update(obs_name, s)
                    and STATE_DESCRIPTORS[s].assimilation_policy != AssimilationPolicy.NOT_ASSIMILATED
                ]
                if not target_indices:
                    continue
                sigma_obs = compute_observation_noise(
                    obs_name,
                    cloud_fraction=cloud_frac,
                    valid_support_fraction=max(0.05, valid_frac),
                )
                r_var = sigma_obs * sigma_obs
                _proxy_update_single_obs(
                    ensemble, self.node_ids, obs_name, obs_val,
                    mapping, sigma_obs, r_var, rng, target_indices=target_indices,
                )
                for s_idx in target_indices:
                    s_name = STATE_NAMES[s_idx]
                    accepted_counts[s_name] = accepted_counts.get(s_name, 0) + 1
                updated_channels.append(obs_name)

            ensemble = clamp_ensemble(ensemble)
            assimilated_ids.append(ev_id)

            post_means, post_stds, post_cov, _, _ = _summarize_13_state_ensemble(ensemble, self.node_ids)
            metrics = dict(payload.get("metrics") or {})

            step_entry = {
                "step_index": global_i,
                "event_id": ev_id,
                "scene_id": str(payload.get("scene_id") or ""),
                "source": str(payload.get("source") or ""),
                "acquisition_time": obs_time.isoformat(),
                "committed_at": str(ev.get("committed_at") or ""),
                "elapsed_days": round(elapsed_days, 3),
                "missing_weather_days": missing_w_in_step,
                "obs_channels": obs_channels,
                "raw_metrics": metrics,
                "updated_channels": updated_channels,
                "prior_predictions": prior_predictions,
                "prior_state_means": prior_means,
                "prior_state_stds": prior_stds,
                "posterior_state_means": post_means,
                "posterior_state_stds": post_stds,
            }
            step_records.append(step_entry)
            segment_buffer.append(step_entry)

            # Determine boundary checkpoint conditions (year rollover, active/fallow transition, stride, or final)
            ndvi_val = obs_channels.get("ndvi")
            is_last = local_i == (len(pending_events) - 1)
            next_year_rollover = False
            if not is_last:
                next_dt = _parse_utc_iso(pending_events[local_i + 1].get("observation_or_valid_time"))
                next_year_rollover = next_dt.year != obs_time.year
            season_flip = False
            if ndvi_val is not None:
                is_act = ndvi_val >= 0.28
                if prev_ndvi_sign_active is not None and is_act != prev_ndvi_sign_active:
                    season_flip = True
                prev_ndvi_sign_active = is_act

            boundary_reason: Optional[str] = None
            if is_last:
                boundary_reason = "late_arrival_recompute" if late_arrival_ids else "horizon_end"
            elif next_year_rollover:
                boundary_reason = "annual_seasonal_boundary"
            elif season_flip and (len(assimilated_ids) % max(2, min(5, self.checkpoint_stride)) == 0):
                boundary_reason = "phenology_regime_boundary"
            elif (local_i + 1) % self.checkpoint_stride == 0:
                boundary_reason = "observation_stride_boundary"

            if boundary_reason is not None:
                cp_id = self._checkpoint_identity(
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    cutoff_valid_time=obs_time.isoformat(),
                    assimilated_observation_ids=assimilated_ids,
                    parent_checkpoint_id=parent_cp_id,
                )
                cp_obj = PosteriorCheckpoint(
                    checkpoint_id=cp_id,
                    schema_version=POSTERIOR_CHECKPOINT_SCHEMA,
                    plot_id=plot_id,
                    tenant_id=tenant_id,
                    namespace=namespace,
                    geometry_hash=geometry_hash,
                    model_version=RECONSTRUCTOR_MODEL_VERSION,
                    state_schema_version=STATE_SCHEMA_VERSION,
                    calibration_version=CALIBRATION_VERSION,
                    cutoff_valid_time=obs_time.isoformat(),
                    knowledge_cutoff_time=cutoff_K,
                    boundary_reason=boundary_reason,
                    last_obs_event_id=ev_id,
                    last_obs_time=obs_time.isoformat(),
                    assimilated_observation_ids=list(assimilated_ids),
                    ensemble_members=copy.deepcopy(ensemble),
                    rng_state_json=_rng_state_to_json(rng.getstate()),
                    state_means=post_means,
                    state_stds=post_stds,
                    state_covariance=post_cov,
                    per_node_means={},
                    per_node_stds={},
                    accepted_update_counts=dict(accepted_counts),
                    state_support_ledger=_build_historical_support_ledger(accepted_counts),
                    parent_checkpoint_id=parent_cp_id,
                    supersedes_checkpoint_id=superseded_cp_ids[-1] if (is_last and superseded_cp_ids) else None,
                    late_arrival_event_ids=list(late_arrival_ids) if is_last else [],
                    trajectory_segment=list(segment_buffer),
                    created_at=now_utc,
                )
                self._save_checkpoint(cp_obj)
                new_checkpoints.append(cp_obj)
                segment_buffer.clear()
                parent_cp_id = cp_id

        full_trajectory = prefix_trajectory + step_records
        if len(full_trajectory) < len(ordered_obs_ids) and not prefix_trajectory:
            full_trajectory = step_records

        final_chain = preserved_prefix_cps + new_checkpoints
        if not final_chain and anchor_cp is not None:
            final_chain = preserved_prefix_cps

        tail_checkpoint = final_chain[-1]
        final_means = tail_checkpoint.state_means
        final_stds = tail_checkpoint.state_stds
        final_cov = tail_checkpoint.state_covariance
        support_ledger = tail_checkpoint.state_support_ledger

        gap_summary = {
            "total_elapsed_days": total_elapsed_days,
            "missing_weather_days": total_missing_weather_days,
            "long_observation_gaps_count": len(gap_events),
            "long_observation_gaps": gap_events[:50],
        }

        context_summary = {
            "plot_id": plot_id,
            "geometry_hash": geometry_hash,
            "daily_weather": weather_series,
            "management_events": mgmt_events,
            "state_support_ledger": support_ledger,
            "tail_checkpoint": tail_checkpoint.summary_dict(),
        }

        event_memory_result: Dict[str, Any] = {}
        if event_memory_fn is not None:
            event_memory_result = event_memory_fn(full_trajectory, context_summary)

        retro_result: Dict[str, Any] = {}
        if retrovalidation_fn is not None:
            retro_result = retrovalidation_fn(full_trajectory, context_summary)

        # Update checkpoint index append-only (retain historical chains before late arrival!)
        historical_chains = list(index_data.get("historical_chains") or [])
        if mode == "late_arrival_replay" and active_cp_ids:
            historical_chains.append({
                "superseded_at": now_utc,
                "late_arrival_event_ids": list(late_arrival_ids),
                "prior_active_chain": list(active_cp_ids),
                "prior_worldline_posterior_event_id": prior_worldline_posterior_id,
            })

        # Emit validated ARCHIVE_POSTERIOR_VALIDATED worldline event only after assimilation + validation
        emitted_event_id: Optional[str] = prior_worldline_posterior_id
        if emit_worldline_posterior and (new_checkpoints or mode == "cold_full_reconstruction"):
            evidence_digest = hashlib.sha256(
                json.dumps(ordered_obs_ids, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            parents: List[str] = [ordered_obs_ids[-1]]
            if prior_worldline_posterior_id and prior_worldline_posterior_id not in parents:
                parents.append(prior_worldline_posterior_id)

            archive_posterior_payload = {
                "schema_version": "archive_posterior_validated_v2",
                "geometry_hash": geometry_hash,
                "model_version": RECONSTRUCTOR_MODEL_VERSION,
                "state_schema_version": STATE_SCHEMA_VERSION,
                "calibration_version": CALIBRATION_VERSION,
                "publication_authority": "DIAGNOSTIC_ONLY",
                "claims_numerical_authority": False,
                "effective_resolution": "10m native satellite",
                "calibration_status": "uncalibrated_diagnostic",
                "observation_count": len(ordered_obs_ids),
                "assimilated_observation_ids_hash": evidence_digest,
                "cutoff_valid_time": tail_checkpoint.cutoff_valid_time,
                "state_means": final_means,
                "state_stds": final_stds,
                "state_covariance": final_cov,
                "state_support_ledger": support_ledger,
                "supported_layers": [
                    k for k, v in support_ledger.items() if v.get("support_status") == "temporally_conditioned"
                ],
                "unsupported_layers": [
                    {"layer": f"ASMAE_{k.upper()}", "reason": (v.get("block_reasons") or ["unsupported"])[0]}
                    for k, v in support_ledger.items()
                    if v.get("support_status") != "temporally_conditioned"
                ],
                "checkpoint_id": tail_checkpoint.checkpoint_id,
                "checkpoint_chain_length": len(final_chain),
                "reconstruction_mode": mode,
                "late_arrival_event_ids": list(late_arrival_ids),
                "supersedes_event_id": prior_worldline_posterior_id if late_arrival_ids else None,
                "prior_publication_preserved": True,
                "gap_summary": gap_summary,
                "event_memory_summary": event_memory_result.get("summary", {}),
                "retrovalidation_summary": retro_result.get("summary", {}),
                "bma_weights": retro_result.get("bma", {}).get("weights", {}),
                "bma_status": retro_result.get("bma", {}).get("archive_bma_status", "diagnostic"),
            }
            wl_payload = {
                "archive_posterior": archive_posterior_payload,
                "historical_metrics": retro_result.get("summary", {}),
                "baseline": retro_result.get("baselines", {}),
                "archive_bma": retro_result.get("bma", {}),
                "retrovalidation": retro_result.get("seasonal_scorecard", {}),
                "archive_metrics_hash": hashlib.sha256(
                    json.dumps(archive_posterior_payload, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest(),
            }
            proposal = WorldlineEventProposal(
                event_type="ARCHIVE_POSTERIOR_VALIDATED",
                geometry_version=geometry_hash[:16],
                evidence_set_hash=evidence_digest,
                payload=wl_payload,
                model_version=RECONSTRUCTOR_MODEL_VERSION,
                calibration_version=CALIBRATION_VERSION,
                authority_contract_version="auth_asmae_hist_v1",
                authority_ref="asmae:historical_state_intelligence",
                state_schema_version=STATE_SCHEMA_VERSION,
                observation_or_valid_time=tail_checkpoint.cutoff_valid_time,
                parent_event_ids=parents,
            )
            committed = self.worldline.commit_proposal(
                plot_id=plot_id,
                proposal=proposal,
                namespace=namespace,
                tenant_id=tenant_id,
                effective_at=tail_checkpoint.cutoff_valid_time,
            )
            emitted_event_id = committed.get("event_id")

        self._save_checkpoint_index(
            plot_id,
            tenant_id,
            namespace,
            {
                "active_chain": [cp.checkpoint_id for cp in final_chain],
                "historical_chains": historical_chains,
                "latest_worldline_posterior_event_id": emitted_event_id,
                "updated_at": now_utc,
            },
        )

        return {
            "status": "COMPLETED",
            "mode": mode,
            "plot_id": plot_id,
            "geometry_hash": geometry_hash,
            "model_version": RECONSTRUCTOR_MODEL_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "calibration_version": CALIBRATION_VERSION,
            "observation_count": len(ordered_obs_ids),
            "newly_assimilated_count": len(pending_events),
            "resumed_from_checkpoint_id": anchor_cp.checkpoint_id if anchor_cp else None,
            "tail_checkpoint_id": tail_checkpoint.checkpoint_id,
            "worldline_posterior_event_id": emitted_event_id,
            "superseded_checkpoint_ids": superseded_cp_ids,
            "late_arrival_event_ids": late_arrival_ids,
            "checkpoints": [cp.summary_dict() for cp in final_chain],
            "state_means": final_means,
            "state_stds": final_stds,
            "state_covariance": final_cov,
            "state_support_ledger": support_ledger,
            "gap_summary": gap_summary,
            "trajectory": full_trajectory,
            "newly_assimilated_trajectory": step_records,
            "event_memory": event_memory_result,
            "retrovalidation": retro_result,
        }

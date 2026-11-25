"""Resumable 2015–Present Historical Archive Bootstrap Service (ASMAE IR-05).

Orchestrates the ingestion, partitioned query, and chronological event
reconstruction of historical satellite (Sentinel-2, Sentinel-1) and weather
observations spanning from the start of the Copernicus mission (2015-06-23)
to the present day.

Architectural Guarantees:
  1. Resumability & Incremental Checkpoints:
     Tracks progress window-by-window in durable checkpoints. If interrupted,
     resumes precisely at the unfinished cursor without duplicate STAC queries.
  2. Chronological Lineage & Deterministic DAG:
     Historical satellite acquisitions are committed strictly as
     OBSERVATION_QUALIFIED worldline events in chronological sequence, linking
     parent hashes to form an immutable observation audit trail. Validated
     posteriors (ARCHIVE_POSTERIOR_VALIDATED) are issued separately only after
     ASMAE model assimilation, uncertainty evaluation, and retrovalidation.
  3. Strict Temporal Separation:
     observation_or_valid_time ($T$) is fixed to the scene observation timestamp.
     committed_at ($K$) is fixed to the bootstrap ingestion time.
  4. Idempotence & Safe Re-run:
     Re-running against an already completed bootstrap produces zero duplicates.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, TYPE_CHECKING

import numpy as np
from rasterio.features import geometry_mask
from rasterio.transform import Affine

if TYPE_CHECKING:
    from services.agribrain.layer05_asmae.history.historical_stack_builder import HistoricalStackBuilder

from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    CANONICAL_WORLDLINE_ROOT,
    WorldlineEventProposal,
    _parse_utc_iso,
)

logger = logging.getLogger(__name__)

# Sentinel-2A mission launch date (definitive floor for European open Earth observation)
MISSION_START_DATE = "2015-06-23T00:00:00+00:00"
DEFAULT_WINDOW_DAYS = 180  # Half-yearly partition slices
BOOTSTRAP_STATE_VERSION = "archive_bootstrap_v1"


@dataclass
class BootstrapWindowRecord:
    window_index: int
    window_start: str
    window_end: str
    scenes_discovered: int
    events_committed: int
    completed_at: str
    gap_detected: bool = False
    window_status: str = "COMPLETED"
    sensor_statuses: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BootstrapCheckpoint:
    bootstrap_version: str
    plot_id: str
    tenant_id: str
    namespace: str
    geometry_hash: str
    mission_start_date: str
    target_end_date: str
    window_days: int
    current_cursor: str
    status: str  # "IN_PROGRESS", "COMPLETED", "FAILED"
    completed_windows: List[Dict[str, Any]] = field(default_factory=list)
    gap_windows: List[int] = field(default_factory=list)
    total_gaps_recorded: int = 0
    total_scenes_discovered: int = 0
    total_events_committed: int = 0
    last_committed_event_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BootstrapCheckpoint":
        allowed = set(cls.__dataclass_fields__)
        clean = {k: v for k, v in data.items() if k in allowed}
        return cls(**clean)


class ArchiveBootstrapService:
    """Manages resumable first-visit archive bootstrap across 2015-present."""

    def __init__(
        self,
        worldline: Optional[CanonicalWorldlineService] = None,
        bootstrap_root: Optional[Path] = None,
        fetcher_factory: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None,
        stack_builder: Optional["HistoricalStackBuilder"] = None,
    ) -> None:
        self.worldline = worldline or CanonicalWorldlineService()
        self.bootstrap_root = Path(
            bootstrap_root
            or (self.worldline.root.parent / "archive_bootstrap_checkpoints")
        ).resolve()
        self.bootstrap_root.mkdir(parents=True, exist_ok=True)
        self._fetcher_factory = fetcher_factory
        self.stack_builder = stack_builder

    def _checkpoint_path(
        self, plot_id: str, tenant_id: str, namespace: str
    ) -> Path:
        p = self.bootstrap_root / tenant_id / namespace / plot_id / "checkpoint.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def load_checkpoint(
        self, plot_id: str, tenant_id: str = "default_tenant", namespace: str = "default"
    ) -> Optional[BootstrapCheckpoint]:
        cp_path = self._checkpoint_path(plot_id, tenant_id, namespace)
        if not cp_path.exists():
            return None
        try:
            data = json.loads(cp_path.read_text(encoding="utf-8"))
            return BootstrapCheckpoint.from_dict(data)
        except Exception as exc:
            logger.warning("Corrupted bootstrap checkpoint for %s: %s", plot_id, exc)
            return None

    def save_checkpoint(self, checkpoint: BootstrapCheckpoint) -> None:
        cp_path = self._checkpoint_path(
            checkpoint.plot_id, checkpoint.tenant_id, checkpoint.namespace
        )
        checkpoint.updated_at = datetime.now(timezone.utc).isoformat()
        temp = cp_path.with_suffix(".tmp")
        temp.write_text(json.dumps(checkpoint.to_dict(), indent=2), encoding="utf-8")
        temp.replace(cp_path)

    @staticmethod
    def _generate_windows(
        start_iso: str, end_iso: str, window_days: int
    ) -> Iterator[Tuple[int, str, str]]:
        dt_start = _parse_utc_iso(start_iso)
        dt_end = _parse_utc_iso(end_iso)
        idx = 0
        cur = dt_start
        delta = timedelta(days=window_days)
        while cur < dt_end:
            win_end = min(cur + delta, dt_end)
            yield idx, cur.isoformat(), win_end.isoformat()
            cur = win_end
            idx += 1

    def run_bootstrap(
        self,
        *,
        plot_id: str,
        geometry_hash: str,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
        start_date: str = MISSION_START_DATE,
        target_end_date: Optional[str] = None,
        window_days: int = DEFAULT_WINDOW_DAYS,
        fail_fast: bool = True,
        max_windows: Optional[int] = None,
        polygon_geojson: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute or resume the historical bootstrap.

        Returns a comprehensive summary dict of ingestion metrics,
        checkpoint status, and worldline event lineage.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        target_end = target_end_date or now_iso
        start_iso = start_date

        checkpoint = self.load_checkpoint(plot_id, tenant_id, namespace)
        if not checkpoint:
            checkpoint = BootstrapCheckpoint(
                bootstrap_version=BOOTSTRAP_STATE_VERSION,
                plot_id=plot_id,
                tenant_id=tenant_id,
                namespace=namespace,
                geometry_hash=geometry_hash,
                mission_start_date=start_iso,
                target_end_date=target_end,
                window_days=window_days,
                current_cursor=start_iso,
                status="IN_PROGRESS",
                created_at=now_iso,
                updated_at=now_iso,
            )
            self.save_checkpoint(checkpoint)
        elif checkpoint.status == "COMPLETED":
            # Check if target_end has advanced beyond previous target_end
            if _parse_utc_iso(target_end) <= _parse_utc_iso(checkpoint.target_end_date):
                return {
                    "status": "COMPLETED",
                    "resumed": False,
                    "already_completed": True,
                    "plot_id": plot_id,
                    "total_events_committed": checkpoint.total_events_committed,
                    "total_scenes_discovered": checkpoint.total_scenes_discovered,
                    "total_gaps_recorded": checkpoint.total_gaps_recorded,
                    "gap_windows": checkpoint.gap_windows,
                    "last_committed_event_id": checkpoint.last_committed_event_id,
                    "checkpoint": checkpoint.to_dict(),
                }
            # Target expanded: transition back to IN_PROGRESS from previous cursor/end
            prev_cursor = checkpoint.target_end_date
            checkpoint.target_end_date = target_end
            checkpoint.current_cursor = prev_cursor
            checkpoint.status = "IN_PROGRESS"
            self.save_checkpoint(checkpoint)

        cursor_dt = _parse_utc_iso(checkpoint.current_cursor)
        start_dt = _parse_utc_iso(start_iso)
        windows_processed = 0
        # When resuming after completed windows (including expanding target_end_date beyond
        # a previously completed tail), generate slices starting cleanly from current_cursor
        # so partial/prior boundary windows are never re-queried or double-counted.
        if checkpoint.completed_windows and cursor_dt > start_dt:
            window_origin = checkpoint.current_cursor
            idx_offset = len(checkpoint.completed_windows)
        else:
            window_origin = start_iso
            idx_offset = 0

        try:
            for sub_idx, win_start, win_end in self._generate_windows(
                window_origin, target_end, window_days
            ):
                idx = idx_offset + sub_idx
                win_end_dt = _parse_utc_iso(win_end)
                if win_end_dt <= cursor_dt:
                    # Already completed window
                    continue

                if max_windows is not None and windows_processed >= max_windows:
                    break

                logger.info(
                    "Bootstrapping plot %s window %d: %s -> %s",
                    plot_id, idx, win_start, win_end
                )

                # Fetch historical scenes and explicit acquisition status for this window
                scenes, window_status, sensor_statuses = self._fetch_scenes_with_status(
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    win_start=win_start,
                    win_end=win_end,
                    polygon_geojson=polygon_geojson,
                )

                checkpoint.total_scenes_discovered += len(scenes)
                events_in_win = 0
                is_gap = len(scenes) == 0

                if is_gap:
                    checkpoint.total_gaps_recorded += 1
                    checkpoint.gap_windows.append(idx)
                    logger.info(
                        "Window %d recorded as historical %s gap (%s)",
                        idx, window_status, sensor_statuses,
                    )
                else:
                    # Reconstruct events chronologically
                    sorted_scenes = sorted(
                        scenes,
                        key=lambda s: _parse_utc_iso(
                            s.get("acquisition_time") or s.get("observation_time") or win_start
                        ),
                    )

                    for scene in sorted_scenes:
                        event_id = self._commit_scene_to_worldline(
                            plot_id=plot_id,
                            geometry_hash=geometry_hash,
                            tenant_id=tenant_id,
                            namespace=namespace,
                            scene=scene,
                            parent_event_id=checkpoint.last_committed_event_id,
                        )
                        if event_id:
                            checkpoint.last_committed_event_id = event_id
                            checkpoint.total_events_committed += 1
                            events_in_win += 1

                # Record completed window with explicit NO_DATA/REJECTED/COMPLETED classification
                win_record = BootstrapWindowRecord(
                    window_index=idx,
                    window_start=win_start,
                    window_end=win_end,
                    scenes_discovered=len(scenes),
                    events_committed=events_in_win,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    gap_detected=is_gap,
                    window_status=window_status,
                    sensor_statuses=sensor_statuses,
                )
                checkpoint.completed_windows.append(asdict(win_record))
                checkpoint.current_cursor = win_end
                self.save_checkpoint(checkpoint)
                windows_processed += 1

            if _parse_utc_iso(checkpoint.current_cursor) >= _parse_utc_iso(target_end):
                checkpoint.status = "COMPLETED"
                checkpoint.error_message = None
                self.save_checkpoint(checkpoint)

        except Exception as exc:
            logger.error(
                "Archive bootstrap interrupted on plot %s at cursor %s: %s",
                plot_id, checkpoint.current_cursor, exc
            )
            checkpoint.status = "FAILED"
            checkpoint.error_message = str(exc)
            self.save_checkpoint(checkpoint)
            if fail_fast:
                raise

        return {
            "status": checkpoint.status,
            "resumed": len(checkpoint.completed_windows) > windows_processed,
            "plot_id": plot_id,
            "current_cursor": checkpoint.current_cursor,
            "total_events_committed": checkpoint.total_events_committed,
            "total_scenes_discovered": checkpoint.total_scenes_discovered,
            "last_committed_event_id": checkpoint.last_committed_event_id,
            "completed_windows_count": len(checkpoint.completed_windows),
            "checkpoint": checkpoint.to_dict(),
        }

    @staticmethod
    def _extract_polygon_geometry(
        polygon_geojson: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[List[List[float]]], Optional[float], Optional[float]]:
        """Extract normalized Polygon geometry, outer ring [lng, lat] coords, and centroid (lat, lng)."""
        if not isinstance(polygon_geojson, dict):
            return None, None, None, None
        geom = polygon_geojson.get("geometry") if polygon_geojson.get("type") == "Feature" else polygon_geojson
        if not isinstance(geom, dict):
            return None, None, None, None
        gtype = str(geom.get("type") or "")
        coords = geom.get("coordinates")
        ring: Optional[List[List[float]]] = None
        norm_geom: Optional[Dict[str, Any]] = None
        if gtype == "Polygon" and isinstance(coords, list) and coords and isinstance(coords[0], list):
            ring = [[float(pt[0]), float(pt[1])] for pt in coords[0] if isinstance(pt, (list, tuple)) and len(pt) >= 2]
            norm_geom = {"type": "Polygon", "coordinates": coords}
        elif gtype == "MultiPolygon" and isinstance(coords, list) and coords and isinstance(coords[0], list) and coords[0]:
            # Use largest outer polygon ring for centroid & STAC footprint
            outer_rings = [poly[0] for poly in coords if isinstance(poly, list) and poly and isinstance(poly[0], list)]
            if outer_rings:
                best = max(outer_rings, key=len)
                ring = [[float(pt[0]), float(pt[1])] for pt in best if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                norm_geom = geom
        if not ring or len(ring) < 3:
            return None, None, None, None
        unique_pts = ring[:-1] if len(ring) > 3 and ring[0] == ring[-1] else ring
        lng = sum(p[0] for p in unique_pts) / len(unique_pts)
        lat = sum(p[1] for p in unique_pts) / len(unique_pts)
        return norm_geom, ring, float(lat), float(lng)

    @staticmethod
    def _load_band_array(path: str) -> np.ndarray:
        """Load 2D float64 array from .npz or .npy band artifact."""
        if str(path).endswith(".npy"):
            return np.asarray(np.load(path), dtype=np.float64)
        with np.load(path) as data:
            key = data.files[0]
            return np.asarray(data[key], dtype=np.float64)

    @staticmethod
    def _scene_polygon_mask(scene: Any, norm_geom: Optional[Dict[str, Any]], height: int, width: int) -> np.ndarray:
        """Build boolean mask of pixels inside the parcel polygon using GDAL Affine transform."""
        if not norm_geom or height <= 0 or width <= 0:
            return np.ones((height, width), dtype=bool)
        transform = getattr(scene, "transform", None)
        if not transform or len(transform) != 6:
            return np.ones((height, width), dtype=bool)
        try:
            aff = Affine.from_gdal(*(float(x) for x in transform))
            return np.asarray(
                geometry_mask(
                    [norm_geom],
                    out_shape=(height, width),
                    transform=aff,
                    all_touched=True,
                    invert=True,
                ),
                dtype=bool,
            )
        except Exception:
            return np.ones((height, width), dtype=bool)

    @classmethod
    def _compute_scene_content_hash(cls, scene: Any) -> str:
        """Compute deterministic SHA-256 content hash over actual downloaded band/mask array data.

        Hashes decoded C-contiguous pixel buffers (rather than outer .npz ZIP bytes whose headers
        contain compression timestamps) so identical observations yield identical digests.
        """
        h = hashlib.sha256()
        h.update(str(getattr(scene, "scene_id", "")).encode("utf-8"))
        acq = getattr(scene, "acquisition_datetime", None)
        if acq is not None:
            h.update(acq.isoformat().encode("utf-8"))
        file_hashed = False
        for ref_map_name in ("band_refs", "mask_refs"):
            ref_map = getattr(scene, ref_map_name, None) or {}
            if isinstance(ref_map, dict):
                for key in sorted(ref_map.keys()):
                    ref_path = ref_map[key]
                    if ref_path and Path(str(ref_path)).is_file():
                        h.update(f"{ref_map_name}:{key}".encode("utf-8"))
                        try:
                            arr = cls._load_band_array(str(ref_path))
                            canon = np.ascontiguousarray(arr, dtype="<f8")
                            h.update(f"{canon.shape}:{canon.dtype}".encode("utf-8"))
                            h.update(canon.tobytes())
                        except Exception:
                            h.update(Path(str(ref_path)).read_bytes())
                        file_hashed = True
        if file_hashed:
            return h.hexdigest()
        existing_hash = str(getattr(scene, "content_hash", "") or "").strip()
        if existing_hash and not existing_hash.startswith("hash_"):
            return existing_hash
        raise RuntimeError(
            f"ACQUISITION_ERROR:{getattr(scene, 'sensor', 'unknown')}:missing_band_files_for_hash:{getattr(scene, 'scene_id', '')}"
        )

    @staticmethod
    def _classify_provider_result(sensor: str, raw_result: Any) -> Tuple[List[Any], str, str]:
        """Classify raw provider result into (scenes, status_code, detail).

        Distinguishes COMPLETED, NO_DATA, REJECTED, and raises ACQUISITION_ERROR on failures.
        """
        if isinstance(raw_result, list):
            if len(raw_result) > 0:
                return raw_result, "COMPLETED", f"scenes={len(raw_result)}"
            return [], "NO_DATA", "empty_scene_list"

        if isinstance(raw_result, dict):
            status_val = str(raw_result.get("status") or "").lower()
            reason = str(raw_result.get("reason") or "provider_error")
            if status_val == "unavailable":
                if reason in {"no_scene_found", "empty_catalog", "no_observations"}:
                    return [], "NO_DATA", reason
                if reason in {"cloud_filter_rejected", "cloud_cover_exceeded", "all_clouds"}:
                    return [], "REJECTED", reason
                stage = raw_result.get("stage", "")
                http_status = raw_result.get("http_status", "")
                raise RuntimeError(
                    f"ACQUISITION_ERROR:{sensor}:{reason}:stage={stage}:http_status={http_status}"
                )
            if isinstance(raw_result.get("scenes"), list):
                scenes = raw_result["scenes"]
                return scenes, ("COMPLETED" if scenes else "NO_DATA"), reason

        raise RuntimeError(
            f"ACQUISITION_ERROR:{sensor}:unexpected_provider_response:{type(raw_result).__name__}"
        )

    def _build_s2_observation_record(
        self,
        scene: Any,
        norm_geom: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Extract genuine NDVI, cloud fraction, valid pixel fraction, and SHA-256 from Sentinel-2 bands."""
        band_refs = getattr(scene, "band_refs", None) or {}
        mask_refs = getattr(scene, "mask_refs", None) or {}
        b04_path = band_refs.get("B04")
        b08_path = band_refs.get("B08")
        if not b04_path or not b08_path or not Path(b04_path).is_file() or not Path(b08_path).is_file():
            raise RuntimeError(f"ACQUISITION_ERROR:sentinel2:missing_B04_B08:{getattr(scene, 'scene_id', '')}")

        b04 = self._load_band_array(b04_path)
        b08 = self._load_band_array(b08_path)
        H, W = b04.shape[:2]
        inside_poly = self._scene_polygon_mask(scene, norm_geom, H, W)
        parcel_pixels = max(1, int(np.sum(inside_poly)))

        valid_mask = inside_poly & np.isfinite(b04) & np.isfinite(b08) & ((b08 + b04) > 1e-6)
        dm_path = mask_refs.get("dataMask") or band_refs.get("dataMask")
        if dm_path and Path(dm_path).is_file():
            dm = self._load_band_array(dm_path)
            if dm.shape[:2] == (H, W):
                valid_mask &= dm > 0.5

        scl_path = band_refs.get("SCL") or mask_refs.get("SCL")
        cloud_score: float
        if scl_path and Path(scl_path).is_file():
            scl = np.rint(self._load_band_array(scl_path)).astype(np.int32)
            if scl.shape[:2] == (H, W):
                cloud_mask = np.isin(scl, [3, 8, 9, 10])
                invalid_scl = np.isin(scl, [0, 1, 3, 8, 9, 10, 11])
                cloud_score = round(float(np.sum(cloud_mask & inside_poly)) / parcel_pixels, 6)
                valid_mask &= ~invalid_scl
            else:
                q_dict = getattr(scene, "quality", None) or {}
                cloud_score = float(q_dict.get("cloud_fraction", 0.0) if isinstance(q_dict, dict) else 0.0)
        else:
            q_dict = getattr(scene, "quality", None) or {}
            cloud_score = float(q_dict.get("cloud_fraction", 0.0) if isinstance(q_dict, dict) else 0.0)

        valid_count = int(np.sum(valid_mask))
        valid_pixel_fraction = round(float(valid_count) / parcel_pixels, 6)
        metrics: Dict[str, Any] = {
            "valid_pixel_count": valid_count,
            "parcel_pixel_count": parcel_pixels,
        }
        if valid_count > 0:
            ndvi = np.clip((b08[valid_mask] - b04[valid_mask]) / (b08[valid_mask] + b04[valid_mask]), -1.0, 1.0)
            metrics["ndvi_mean"] = round(float(np.mean(ndvi)), 6)
            metrics["ndvi_std"] = round(float(np.std(ndvi)), 6)
            metrics["ndvi_min"] = round(float(np.min(ndvi)), 6)
            metrics["ndvi_max"] = round(float(np.max(ndvi)), 6)
            b11_path = band_refs.get("B11")
            if b11_path and Path(b11_path).is_file():
                b11 = self._load_band_array(b11_path)
                if b11.shape[:2] == (H, W):
                    ndmi_mask = valid_mask & np.isfinite(b11) & ((b08 + b11) > 1e-6)
                    if int(np.sum(ndmi_mask)) > 0:
                        ndmi = np.clip((b08[ndmi_mask] - b11[ndmi_mask]) / (b08[ndmi_mask] + b11[ndmi_mask]), -1.0, 1.0)
                        metrics["ndmi_mean"] = round(float(np.mean(ndmi)), 6)
        else:
            metrics["ndvi_mean"] = None
            metrics["ndvi_std"] = None

        content_hash = self._compute_scene_content_hash(scene)
        acq = scene.acquisition_datetime.isoformat()
        raw_transform = getattr(scene, "transform", None)
        return {
            "scene_id": scene.scene_id,
            "acquisition_time": acq,
            "source": "sentinel2",
            "product_level": "L2A",
            "cloud_score": cloud_score,
            "quality_score": valid_pixel_fraction,
            "source_content_hash": content_hash,
            "valid_pixel_fraction": valid_pixel_fraction,
            "resolution_m": 10.0,
            "crs": getattr(scene, "crs", None),
            "transform": list(raw_transform) if raw_transform else None,
            "width": getattr(scene, "width", None),
            "height": getattr(scene, "height", None),
            "band_units": dict(getattr(scene, "band_units", None) or {}),
            "effective_resolution": "10m native satellite",
            "calibration_status": "uncalibrated_diagnostic",
            "publication_authority": "DIAGNOSTIC_ONLY",
            "can_render_pixels": valid_count > 0,
            "metrics": metrics,
        }

    def _build_s1_observation_record(
        self,
        scene: Any,
        norm_geom: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Extract genuine VV/VH backscatter dB metrics, valid fraction, and SHA-256 from Sentinel-1 bands."""
        band_refs = getattr(scene, "band_refs", None) or {}
        mask_refs = getattr(scene, "mask_refs", None) or {}
        vv_path = band_refs.get("VV")
        if not vv_path or not Path(vv_path).is_file():
            raise RuntimeError(f"ACQUISITION_ERROR:sentinel1:missing_VV:{getattr(scene, 'scene_id', '')}")

        vv = self._load_band_array(vv_path)
        H, W = vv.shape[:2]
        inside_poly = self._scene_polygon_mask(scene, norm_geom, H, W)
        parcel_pixels = max(1, int(np.sum(inside_poly)))

        valid_mask = inside_poly & np.isfinite(vv)
        dm_path = mask_refs.get("dataMask") or band_refs.get("dataMask")
        if dm_path and Path(dm_path).is_file():
            dm = self._load_band_array(dm_path)
            if dm.shape[:2] == (H, W):
                valid_mask &= dm > 0.5

        vv_unit = str((getattr(scene, "band_units", None) or {}).get("VV", "")).lower()
        already_db = "db" in vv_unit
        if not already_db and int(np.sum(valid_mask)) > 0:
            finite_vals = vv[valid_mask]
            if np.any(finite_vals < 0.0):
                already_db = True
        if not already_db:
            valid_mask &= vv > 1e-12

        valid_count = int(np.sum(valid_mask))
        valid_pixel_fraction = round(float(valid_count) / parcel_pixels, 6)
        metrics: Dict[str, Any] = {
            "valid_pixel_count": valid_count,
            "parcel_pixel_count": parcel_pixels,
        }
        if valid_count > 0:
            vv_db = vv[valid_mask] if already_db else 10.0 * np.log10(vv[valid_mask])
            metrics["vv_mean_db"] = round(float(np.mean(vv_db)), 6)
            metrics["vv_std_db"] = round(float(np.std(vv_db)), 6)
            vh_path = band_refs.get("VH")
            if vh_path and Path(vh_path).is_file():
                vh = self._load_band_array(vh_path)
                if vh.shape[:2] == (H, W):
                    vh_unit = str((getattr(scene, "band_units", None) or {}).get("VH", "")).lower()
                    vh_db_flag = "db" in vh_unit or bool(np.any(vh[valid_mask] < 0.0))
                    vh_mask = valid_mask & np.isfinite(vh) & (True if vh_db_flag else (vh > 1e-12))
                    if int(np.sum(vh_mask)) > 0:
                        vh_db = vh[vh_mask] if vh_db_flag else 10.0 * np.log10(vh[vh_mask])
                        metrics["vh_mean_db"] = round(float(np.mean(vh_db)), 6)
        else:
            metrics["vv_mean_db"] = None
            metrics["vv_std_db"] = None

        content_hash = self._compute_scene_content_hash(scene)
        acq = scene.acquisition_datetime.isoformat()
        raw_transform = getattr(scene, "transform", None)
        return {
            "scene_id": scene.scene_id,
            "acquisition_time": acq,
            "source": "sentinel1",
            "product_level": "GRD",
            "cloud_score": 0.0,
            "quality_score": valid_pixel_fraction,
            "source_content_hash": content_hash,
            "valid_pixel_fraction": valid_pixel_fraction,
            "resolution_m": 10.0,
            "crs": getattr(scene, "crs", None),
            "transform": list(raw_transform) if raw_transform else None,
            "width": getattr(scene, "width", None),
            "height": getattr(scene, "height", None),
            "band_units": dict(getattr(scene, "band_units", None) or {}),
            "effective_resolution": "10m native satellite",
            "calibration_status": "uncalibrated_proxy",
            "publication_authority": "DIAGNOSTIC_ONLY",
            "can_render_pixels": valid_count > 0,
            "metrics": metrics,
        }

    def _fetch_scenes_with_status(
        self,
        plot_id: str,
        geometry_hash: str,
        win_start: str,
        win_end: str,
        polygon_geojson: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
        """Discover historical records for a temporal slice and preserve provider status taxonomy.

        Returns (discovered_records, window_status, sensor_statuses) where window_status is
        COMPLETED, NO_DATA, or REJECTED; raises RuntimeError(ACQUISITION_ERROR:...) on errors.
        """
        if self._fetcher_factory:
            mock_res = self._fetcher_factory(win_start, win_end)
            if isinstance(mock_res, list):
                return (
                    mock_res,
                    "COMPLETED" if len(mock_res) > 0 else "NO_DATA",
                    {"mock": "COMPLETED" if len(mock_res) > 0 else "NO_DATA"},
                )
            if isinstance(mock_res, dict):
                scenes, w_status, detail = self._classify_provider_result("mock_provider", mock_res)
                return scenes, w_status, {"mock_provider": {"status": w_status, "reason": detail}}
            raise RuntimeError(f"ACQUISITION_ERROR:mock_provider:unexpected_type:{type(mock_res).__name__}")

        # Authentic provider query across Sentinel-2 (L2A) and Sentinel-1 (IW GRD)
        try:
            from services.agribrain.layer0.providers.asmae_scene_fetcher import (
                fetch_asmae_s2_scene_stack,
                fetch_asmae_s1_scene_stack,
            )

            norm_geom, ring, lat, lng = self._extract_polygon_geometry(polygon_geojson)
            date_range = (win_start[:10], win_end[:10])
            geom_tag = str(geometry_hash or "nogeom").split(":", 1)[-1][:12]
            win_run_id = f"bootstrap_{geom_tag}_{win_start[:10]}_{win_end[:10]}"
            s2_raw = fetch_asmae_s2_scene_stack(
                plot_id,
                win_run_id,
                date_range,
                {},
                lat=lat,
                lng=lng,
                polygon_coords=ring,
            )
            s1_raw = fetch_asmae_s1_scene_stack(
                plot_id,
                win_run_id,
                date_range,
                {},
                lat=lat,
                lng=lng,
                polygon_coords=ring,
            )

            s2_scenes, s2_status, s2_detail = self._classify_provider_result("sentinel2", s2_raw)
            s1_scenes, s1_status, s1_detail = self._classify_provider_result("sentinel1", s1_raw)

            discovered: List[Dict[str, Any]] = []
            for s in s2_scenes:
                if hasattr(s, "acquisition_datetime"):
                    discovered.append(self._build_s2_observation_record(s, norm_geom))
            for s in s1_scenes:
                if hasattr(s, "acquisition_datetime"):
                    discovered.append(self._build_s1_observation_record(s, norm_geom))

            if len(discovered) > 0:
                window_status = "COMPLETED"
            elif s2_status == "REJECTED" or s1_status == "REJECTED":
                window_status = "REJECTED"
            else:
                window_status = "NO_DATA"

            sensor_statuses = {
                "sentinel2": {"status": s2_status, "detail": s2_detail, "scenes": len(s2_scenes)},
                "sentinel1": {"status": s1_status, "detail": s1_detail, "scenes": len(s1_scenes)},
            }
            return discovered, window_status, sensor_statuses
        except Exception as exc:
            logger.error(
                "Provider acquisition error in window %s -> %s for plot %s: %s",
                win_start, win_end, plot_id, exc,
            )
            if str(exc).startswith("ACQUISITION_ERROR:"):
                raise
            raise RuntimeError(
                f"ACQUISITION_ERROR: Failed to query providers for window {win_start} -> {win_end}: {exc}"
            ) from exc

    def _fetch_scenes_for_window(
        self,
        plot_id: str,
        geometry_hash: str,
        win_start: str,
        win_end: str,
        polygon_geojson: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Discover historical records for a temporal slice.

        Distinguishes genuine empty observation windows (NO_DATA / REJECTED)
        from provider acquisition errors (which raise ACQUISITION_ERROR).
        """
        scenes, _, _ = self._fetch_scenes_with_status(
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            win_start=win_start,
            win_end=win_end,
            polygon_geojson=polygon_geojson,
        )
        return scenes

    def _commit_scene_to_worldline(
        self,
        plot_id: str,
        geometry_hash: str,
        tenant_id: str,
        namespace: str,
        scene: Dict[str, Any],
        parent_event_id: Optional[str],
    ) -> Optional[str]:
        """Commit a qualified satellite acquisition into the canonical worldline.

        Records the scene strictly as OBSERVATION_QUALIFIED without claiming a
        validated model posterior. ARCHIVE_POSTERIOR_VALIDATED events are issued
        separately only after chronological ASMAE assimilation and validation.
        """
        acq_time = (
            scene.get("acquisition_time")
            or scene.get("observation_time")
            or scene.get("datetime")
        )
        if not acq_time:
            return None

        source_name = str(scene.get("source", "sentinel2"))
        supported_obs = (
            ["ndvi", "ndmi"] if "s1" not in source_name.lower() and "sentinel1" not in source_name.lower()
            else ["vv_db", "vh_db"]
        )
        observation_qualified = {
            "schema_version": "observation_qualified_v1",
            "observation_role": "qualified_satellite_observation",
            "assimilated": False,
            "geometry_hash": geometry_hash,
            "scene_id": scene.get("scene_id", f"scene_{acq_time}"),
            "source": source_name,
            "product_level": scene.get("product_level", "L2A"),
            "acquisition_time": acq_time,
            "cloud_score": scene.get("cloud_score", 0.0),
            "quality_score": scene.get("quality_score", 1.0),
            "metrics": scene.get("metrics", {}),
            "valid_pixel_fraction": scene.get("valid_pixel_fraction", 1.0),
            "raw_resolution_m": scene.get("resolution_m", 10.0),
            "crs": scene.get("crs"),
            "transform": scene.get("transform"),
            "width": scene.get("width"),
            "height": scene.get("height"),
            "band_units": scene.get("band_units"),
            "source_content_hash": scene.get("source_content_hash", "hash_mock"),
            "publication_authority": scene.get("publication_authority", "DIAGNOSTIC_ONLY"),
            "claims_numerical_authority": False,
            "observable_quantities": supported_obs,
            "effective_resolution": scene.get("effective_resolution", "10m native satellite"),
            "calibration_status": scene.get("calibration_status", "uncalibrated_diagnostic"),
            "can_render_pixels": scene.get("can_render_pixels", bool(scene.get("values") is not None)),
        }

        payload = {"observation_qualified": observation_qualified}

        parents = [parent_event_id] if parent_event_id else []

        proposal = WorldlineEventProposal(
            event_type="OBSERVATION_QUALIFIED",
            geometry_version=geometry_hash[:16],
            evidence_set_hash=scene.get("source_content_hash", "hash_mock"),
            payload=payload,
            model_version="asmae_archive_observation_v1",
            calibration_version="unassimilated_observation_v1",
            authority_contract_version="auth_copernicus_v1",
            authority_ref=f"stac_{source_name}",
            state_schema_version="observation_qualified_v1",
            observation_or_valid_time=acq_time,
            parent_event_ids=parents,
        )

        committed = self.worldline.commit_proposal(
            plot_id=plot_id,
            proposal=proposal,
            namespace=namespace,
            tenant_id=tenant_id,
            effective_at=acq_time,
        )
        return committed.get("event_id")

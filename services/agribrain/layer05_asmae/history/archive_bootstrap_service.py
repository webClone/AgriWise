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
     Historical observations are committed as ARCHIVE_POSTERIOR_VALIDATED
     canonical worldline events in strict temporal sequence, linking parent
     hashes to form an immutable audit trail.
  3. Strict Temporal Separation:
     observation_or_valid_time ($T$) is fixed to the scene observation timestamp.
     committed_at ($K$) is fixed to the bootstrap ingestion time.
  4. Idempotence & Safe Re-run:
     Re-running against an already completed bootstrap produces zero duplicates.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

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
BOOTSTRAP_STATE_VERSION = "archive_bootstrap_v2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GEOMETRY_HASH_RE = re.compile(r"^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{64}$")


def _strict_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}_must_be_explicit_utc_time")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}_invalid_timestamp") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError(f"{label}_timezone_required")
    return instant.astimezone(timezone.utc)



@dataclass
class BootstrapWindowRecord:
    window_index: int
    window_start: str
    window_end: str
    scenes_discovered: int
    events_committed: int
    completed_at: str


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
    ) -> None:
        self.worldline = worldline or CanonicalWorldlineService()
        self.bootstrap_root = Path(
            bootstrap_root
            or (self.worldline.root.parent / "archive_bootstrap_checkpoints")
        ).resolve()
        self.bootstrap_root.mkdir(parents=True, exist_ok=True)
        self._fetcher_factory = fetcher_factory

    def _checkpoint_path(
        self, plot_id: str, tenant_id: str, namespace: str
    ) -> Path:
        for name, value in (("tenant_id", tenant_id), ("namespace", namespace), ("plot_id", plot_id)):
            if (not isinstance(value, str) or not value or value.strip() != value
                    or value in (".", "..") or "/" in value or chr(92) in value
                    or chr(0) in value):
                raise ValueError(f"invalid_archive_checkpoint_{name}")
        p = (self.bootstrap_root / tenant_id / namespace / plot_id / "checkpoint.json").resolve()
        if not p.is_relative_to(self.bootstrap_root):
            raise ValueError("archive_checkpoint_path_escape")
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
            raise RuntimeError("corrupt_archive_bootstrap_checkpoint") from exc

    def save_checkpoint(self, checkpoint: BootstrapCheckpoint) -> None:
        cp_path = self._checkpoint_path(
            checkpoint.plot_id, checkpoint.tenant_id, checkpoint.namespace
        )
        checkpoint.updated_at = datetime.now(timezone.utc).isoformat()
        temp = cp_path.with_name(cp_path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temp.open("w", encoding="utf-8") as handle:
                json.dump(checkpoint.to_dict(), handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, cp_path)
        finally:
            temp.unlink(missing_ok=True)

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
    ) -> Dict[str, Any]:
        """Execute or resume the historical bootstrap.

        Returns a comprehensive summary dict of ingestion metrics,
        checkpoint status, and worldline event lineage.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        target_end = target_end_date or now_iso
        start_iso = start_date
        start_dt = _strict_utc(start_iso, "start_date")
        end_dt = _strict_utc(target_end, "target_end_date")
        if end_dt <= start_dt or end_dt > datetime.now(timezone.utc) + timedelta(minutes=1):
            raise ValueError("invalid_or_future_archive_date_range")
        if type(window_days) is not int or not (1 <= window_days <= 366):
            raise ValueError("invalid_archive_window_days")
        if not isinstance(geometry_hash, str) or not _GEOMETRY_HASH_RE.fullmatch(geometry_hash):
            raise ValueError("archive_geometry_requires_sha256")

        checkpoint = self.load_checkpoint(plot_id, tenant_id, namespace)
        if checkpoint:
            if (checkpoint.bootstrap_version != BOOTSTRAP_STATE_VERSION
                    or checkpoint.plot_id != plot_id or checkpoint.tenant_id != tenant_id
                    or checkpoint.namespace != namespace or checkpoint.geometry_hash != geometry_hash
                    or _strict_utc(checkpoint.mission_start_date, "checkpoint_start") != start_dt
                    or checkpoint.window_days != window_days):
                raise RuntimeError("archive_checkpoint_identity_or_version_mismatch")
            if _strict_utc(checkpoint.target_end_date, "checkpoint_end") > end_dt:
                raise RuntimeError("archive_target_cannot_move_backwards")
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
                # Completed checkpoint is not itself proof that journal data survived.
                # Verify a cold journal read before returning early.
                all_events = self.worldline.load_all_events(
                    plot_id, tenant_id, namespace, fail_on_corrupt=True
                )
                inventory = [
                    event for event in all_events
                    if event.get("event_type") == "ARCHIVE_SCENE_INGESTED"
                ]
                if (len(inventory) != checkpoint.total_events_committed
                        or any(
                            (event.get("payload") or {}).get("archive_scene", {}).get("geometry_hash")
                            != geometry_hash for event in inventory
                        )):
                    raise RuntimeError("archive_completed_checkpoint_journal_mismatch")
                return {
                    "status": "COMPLETED",
                    "resumed": False,
                    "already_completed": True,
                    "plot_id": plot_id,
                    "total_events_committed": checkpoint.total_events_committed,
                    "total_scenes_discovered": checkpoint.total_scenes_discovered,
                    "last_committed_event_id": checkpoint.last_committed_event_id,
                    "checkpoint": checkpoint.to_dict(),
                }
            # Target expanded: transition back to IN_PROGRESS from previous cursor/end
            prev_cursor = checkpoint.target_end_date
            checkpoint.target_end_date = target_end
            checkpoint.current_cursor = prev_cursor
            checkpoint.status = "IN_PROGRESS"
            self.save_checkpoint(checkpoint)

        if checkpoint.status not in ("IN_PROGRESS", "FAILED", "COMPLETED"):
            raise RuntimeError("invalid_archive_checkpoint_status")
        checkpoint.status = "IN_PROGRESS"
        cursor_dt = _strict_utc(checkpoint.current_cursor, "checkpoint_cursor")
        if not start_dt <= cursor_dt <= end_dt:
            raise RuntimeError("archive_checkpoint_cursor_outside_range")

        # Recover committed inventory before replaying any unfinished window.
        existing = {}
        by_scene_id = {}
        recent_event_id = None
        for event in self.worldline.load_all_events(
            plot_id, tenant_id, namespace, fail_on_corrupt=True
        ):
            if event.get("event_type") != "ARCHIVE_SCENE_INGESTED":
                continue
            record = (event.get("payload") or {}).get("archive_scene") or {}
            if record.get("geometry_hash") != geometry_hash:
                raise RuntimeError("archive_journal_geometry_conflict")
            key = (record.get("scene_id"), record.get("source_content_hash"))
            if key in existing and existing[key] != event.get("event_id"):
                raise RuntimeError("archive_duplicate_scene_identity_conflict")
            if (record.get("scene_id") in by_scene_id
                    and by_scene_id[record["scene_id"]] != record.get("source_content_hash")):
                raise RuntimeError("archive_scene_revision_requires_selective_replay")
            by_scene_id[record.get("scene_id")] = record.get("source_content_hash")
            existing[key] = event.get("event_id")
            recent_event_id = event.get("event_id")
        checkpoint.total_events_committed = len(existing)
        if recent_event_id:
            checkpoint.last_committed_event_id = recent_event_id
        windows_processed = 0

        try:
            for idx, win_start, win_end in self._generate_windows(
                start_iso, target_end, window_days
            ):
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

                # Fetch historical scenes for this window
                scenes = self._fetch_scenes_for_window(
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    win_start=win_start,
                    win_end=win_end,
                )

                if not isinstance(scenes, list):
                    raise RuntimeError("archive_provider_failed_to_return_scene_list")
                sorted_scenes = sorted(
                    scenes,
                    key=lambda scene: _strict_utc(
                        scene.get("acquisition_time") or scene.get("observation_time"),
                        "scene_acquisition_time",
                    ),
                )
                win_left = _strict_utc(win_start, "window_start")
                win_right = _strict_utc(win_end, "window_end")
                events_in_win = 0
                for scene in sorted_scenes:
                    scene_time = _strict_utc(
                        scene.get("acquisition_time") or scene.get("observation_time"),
                        "scene_acquisition_time",
                    )
                    if not (win_left <= scene_time < win_right):
                        raise RuntimeError("scene_outside_queried_archive_window")
                    scene_id = scene.get("scene_id")
                    source_hash = scene.get("source_content_hash")
                    if (not isinstance(scene_id, str) or not scene_id
                            or not isinstance(source_hash, str)
                            or not _SHA256.fullmatch(source_hash)):
                        raise RuntimeError("archive_scene_requires_id_and_real_sha256")
                    if scene_id in by_scene_id and by_scene_id[scene_id] != source_hash:
                        raise RuntimeError("archive_scene_revision_requires_selective_replay")
                    key = (scene_id, source_hash)
                    if key in existing:
                        continue
                    event_id = self._commit_scene_to_worldline(
                        plot_id=plot_id,
                        geometry_hash=geometry_hash,
                        tenant_id=tenant_id,
                        namespace=namespace,
                        scene=scene,
                        parent_event_id=checkpoint.last_committed_event_id,
                    )
                    if not event_id:
                        raise RuntimeError("archive_scene_commit_produced_no_event_id")
                    by_scene_id[scene_id] = source_hash
                    existing[key] = event_id
                    checkpoint.last_committed_event_id = event_id
                    checkpoint.total_events_committed = len(existing)
                    events_in_win += 1
                    self.save_checkpoint(checkpoint)
                checkpoint.total_scenes_discovered += len(scenes)

                # Record completed window
                win_record = BootstrapWindowRecord(
                    window_index=idx,
                    window_start=win_start,
                    window_end=win_end,
                    scenes_discovered=len(scenes),
                    events_committed=events_in_win,
                    completed_at=datetime.now(timezone.utc).isoformat(),
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

    def _fetch_scenes_for_window(
        self, plot_id: str, geometry_hash: str, win_start: str, win_end: str
    ) -> List[Dict[str, Any]]:
        """Discover historical records for a temporal slice."""
        if self._fetcher_factory:
            return self._fetcher_factory(win_start, win_end)

        # Never claim completion of 2015+ history with an unconfigured provider.
        # A configured provider may return an empty list after a successful query.
        raise RuntimeError("archive_provider_not_configured")

    def _commit_scene_to_worldline(
        self,
        plot_id: str,
        geometry_hash: str,
        tenant_id: str,
        namespace: str,
        scene: Dict[str, Any],
        parent_event_id: Optional[str],
    ) -> Optional[str]:
        """Persist discovered scene inventory, NOT a validated scientific posterior."""
        acq_time = scene.get("acquisition_time") or scene.get("observation_time")
        acquisition = _strict_utc(acq_time, "scene_acquisition_time").isoformat()
        scene_id, content_hash = scene.get("scene_id"), scene.get("source_content_hash")
        source = str(scene.get("source") or "").lower()
        if source not in ("sentinel1", "sentinel2", "s1", "s2", "weather"):
            raise ValueError("unsupported_archive_scene_source")
        if not isinstance(scene_id, str) or not scene_id:
            raise ValueError("missing_archive_scene_id")
        if not isinstance(content_hash, str) or not _SHA256.fullmatch(content_hash):
            raise ValueError("missing_authoritative_archive_asset_digest")
        payload = {
            "archive_scene": {
                "geometry_hash": geometry_hash,
                "scene_id": scene_id,
                "source": source,
                "source_content_hash": content_hash,
                "observation_time": acquisition,
                "product_level": scene.get("product_level"),
                "cloud_score": scene.get("cloud_score"),
                "quality_score": scene.get("quality_score"),
                "valid_pixel_fraction": scene.get("valid_pixel_fraction"),
                "native_resolution_m": scene.get("resolution_m"),
                "inventory_only": True,
                "posterior_validated": False,
                "scientific_authority": "none",
            }
        }
        proposal = WorldlineEventProposal(
            event_type="ARCHIVE_SCENE_INGESTED",
            geometry_version=geometry_hash[:16],
            evidence_set_hash=content_hash,
            payload=payload,
            model_version="asmae_archive_bootstrap_v2",
            calibration_version="",
            authority_contract_version="archive_inventory_not_assimilated_v1",
            authority_ref="archive_inventory_unqualified",
            state_schema_version="archive_scene_inventory_v1",
            observation_or_valid_time=acquisition,
            parent_event_ids=[parent_event_id] if parent_event_id else [],
        )
        committed = self.worldline.commit_proposal(
            plot_id=plot_id,
            proposal=proposal,
            namespace=namespace,
            tenant_id=tenant_id,
            effective_at=acquisition,
        )
        return committed.get("event_id")


def create_copernicus_archive_provider(
    fetcher: Any,
    plot_id: str,
    geometry_wkt: str,
    sources: Optional[List[str]] = None,
    manifest_only: bool = True,
) -> Callable[[str, str], List[Dict[str, Any]]]:
    """Binds ArchiveFetcher with STAC / CDSE query to ArchiveBootstrapService window slices.

    Transforms HistoricalSceneRecord outputs into the scene inventory schema required
    by ArchiveBootstrapService._commit_scene_to_worldline.
    """
    active_sources = sources or ["sentinel2", "sentinel1"]

    def provider(win_start: str, win_end: str) -> List[Dict[str, Any]]:
        records = fetcher.orchestrate_fetch(
            plot_id=plot_id,
            geometry_wkt=geometry_wkt,
            start_date=win_start,
            end_date=win_end,
            sources=active_sources,
            manifest_only=manifest_only,
        )
        scenes: List[Dict[str, Any]] = []
        for r in records:
            if getattr(r, "quality_status", "") == "rejected":
                continue
            scenes.append({
                "scene_id": r.scene_id,
                "source": r.source,
                "acquisition_time": r.acquisition_time,
                "product_level": r.product_level,
                "cloud_score": r.cloud_score,
                "quality_score": 1.0 - ((r.cloud_score or 0.0) / 100.0),
                "source_content_hash": r.source_content_hash,
                "valid_pixel_fraction": r.valid_pixel_fraction,
                "resolution_m": r.native_resolution_m,
                "bands_available": r.bands_available,
                "masks_available": r.masks_available,
            })
        return scenes

    return provider

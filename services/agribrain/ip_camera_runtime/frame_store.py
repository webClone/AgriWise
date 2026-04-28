import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
from .schemas import FrameManifest

logger = logging.getLogger(__name__)


class FrameStore:
    """
    Stores raw frames, thumbnails, normalized frames, and their manifests.

    Frame bytes are persisted to disk under the configured storage directory.
    Manifests are kept in memory and can optionally be backed by a database.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        self._manifests: Dict[str, FrameManifest] = {}
        self._storage_dir = Path(storage_dir) if storage_dir else None
        if self._storage_dir:
            self._storage_dir.mkdir(parents=True, exist_ok=True)

    def store_manifest(self, manifest: FrameManifest) -> None:
        self._manifests[manifest.manifest_id] = manifest

    def get_manifest(self, manifest_id: str) -> Optional[FrameManifest]:
        return self._manifests.get(manifest_id)

    def get_recent_manifests(self, camera_id: str, limit: int = 10) -> List[FrameManifest]:
        camera_manifests = [m for m in self._manifests.values() if m.camera_id == camera_id]
        camera_manifests.sort(key=lambda m: m.captured_at, reverse=True)
        return camera_manifests[:limit]

    def store_frame_bytes(self, frame_ref: str, data: bytes) -> str:
        """Persist raw frame bytes to disk.

        Args:
            frame_ref: relative path key (e.g. "frames/cam_001/abc.jpg")
            data: raw JPEG/PNG bytes

        Returns:
            Absolute path where the file was written, or frame_ref if
            no storage_dir is configured (in-memory only mode).
        """
        if not self._storage_dir:
            # In-memory fallback — store in a dict
            if not hasattr(self, "_frame_bytes"):
                self._frame_bytes: Dict[str, bytes] = {}
            self._frame_bytes[frame_ref] = data
            return frame_ref

        target = self._storage_dir / frame_ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        logger.debug("Stored %d bytes to %s", len(data), target)
        return str(target)

    def get_frame_bytes(self, frame_ref: str) -> Optional[bytes]:
        """Retrieve raw frame bytes.

        Args:
            frame_ref: relative path key used in store_frame_bytes

        Returns:
            Raw bytes, or None if not found.
        """
        if not self._storage_dir:
            return getattr(self, "_frame_bytes", {}).get(frame_ref)

        target = self._storage_dir / frame_ref
        if target.exists():
            return target.read_bytes()
        return None

    def has_frame(self, frame_ref: str) -> bool:
        """Check if frame bytes exist for the given reference."""
        if not self._storage_dir:
            return frame_ref in getattr(self, "_frame_bytes", {})
        return (self._storage_dir / frame_ref).exists()


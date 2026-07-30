"""
RTSP Frame Capture Service — live frame delivery from IP cameras.

Connects to RTSP streams via OpenCV (or ffmpeg subprocess fallback),
captures frames according to FrameCapturePolicy, stores them in the
FrameStore, and feeds them into the IP Camera perception engine.

Usage:
    service = RTSPCaptureService(
        registry=registry,
        credential_store=creds,
        frame_store=frame_store,
        health_monitor=health_monitor,
    )
    # Start capture for a camera
    service.start_capture("cam_001")

    # Stop capture
    service.stop_capture("cam_001")

    # Run one capture cycle for all registered cameras
    service.run_capture_cycle()
"""

from __future__ import annotations

import io
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .credential_store import CredentialStore
from .frame_sampler import FrameSampler
from .frame_store import FrameStore
from .health_monitor import HealthMonitor
from .registry_repository import IPCameraRegistryRepository
from .schemas import (
    CameraProtocol,
    FrameArtifact,
    FrameManifest,
    IPCameraRegistration,
)

logger = logging.getLogger(__name__)

# Optional cv2 import for RTSP capture
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None  # type: ignore
    HAS_CV2 = False

try:
    import numpy as np
    HAS_NP = True
except ImportError:
    np = None  # type: ignore
    HAS_NP = False


class CaptureResult:
    """Result of a single frame capture attempt."""

    def __init__(
        self,
        success: bool,
        camera_id: str,
        frame_data: Optional[bytes] = None,
        resolution: Optional[Tuple[int, int]] = None,
        error: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.success = success
        self.camera_id = camera_id
        self.frame_data = frame_data  # JPEG bytes
        self.resolution = resolution or (0, 0)
        self.error = error
        self.timestamp = timestamp or datetime.now(tz=timezone.utc)


class RTSPCaptureService:
    """
    Live RTSP frame capture service.

    Pulls frames from registered camera RTSP streams, applies the
    capture policy (cadence, night-skip), and stores frames for
    downstream perception.

    Architecture:
        Registry -> Credentials -> RTSP URI -> OpenCV capture -> JPEG encode
        -> FrameStore (manifest + artifact) -> HealthMonitor update
    """

    # Timeout for RTSP connection attempts (ms)
    CONNECT_TIMEOUT_MS = 5000
    # Maximum consecutive failures before marking camera offline
    MAX_CONSECUTIVE_FAILURES = 3
    # JPEG encoding quality
    JPEG_QUALITY = 85

    def __init__(
        self,
        registry: IPCameraRegistryRepository,
        credential_store: CredentialStore,
        frame_store: FrameStore,
        health_monitor: HealthMonitor,
        frame_sampler: Optional[FrameSampler] = None,
        on_frame_captured: Optional[Callable] = None,
    ):
        self.registry = registry
        self.credential_store = credential_store
        self.frame_store = frame_store
        self.health_monitor = health_monitor
        self.frame_sampler = frame_sampler or FrameSampler()
        self.on_frame_captured = on_frame_captured

        # Active capture state per camera
        self._captures: Dict[str, Any] = {}  # camera_id -> cv2.VideoCapture
        self._consecutive_failures: Dict[str, int] = {}
        self._last_capture_time: Dict[str, datetime] = {}

    def _resolve_rtsp_uri(self, camera: IPCameraRegistration) -> Optional[str]:
        """Resolve the RTSP URI for a camera from the credential store."""
        if not camera.credentials_ref:
            logger.warning("Camera %s has no credentials_ref", camera.camera_id)
            return None

        uri = self.credential_store.get_raw_uri(camera.credentials_ref)
        if not uri:
            logger.warning(
                "No URI found for camera %s (secret_id=%s)",
                camera.camera_id,
                camera.credentials_ref.secret_id,
            )
            return None
        return uri

    def _open_stream(self, camera_id: str, rtsp_uri: str) -> Optional[Any]:
        """Open an RTSP stream via OpenCV. Returns VideoCapture or None."""
        if not HAS_CV2:
            logger.error("OpenCV not available — cannot open RTSP stream")
            return None

        try:
            cap = cv2.VideoCapture(rtsp_uri, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.CONNECT_TIMEOUT_MS)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.CONNECT_TIMEOUT_MS)

            if not cap.isOpened():
                logger.warning("Failed to open RTSP stream for %s", camera_id)
                return None

            logger.info("RTSP stream opened for %s", camera_id)
            return cap

        except Exception as e:
            logger.error("Error opening stream for %s: %s", camera_id, e)
            return None

    def _grab_frame(self, camera_id: str) -> CaptureResult:
        """Grab a single frame from an active capture."""
        cap = self._captures.get(camera_id)
        if cap is None or not HAS_CV2:
            return CaptureResult(
                success=False,
                camera_id=camera_id,
                error="No active capture",
            )

        try:
            ret, frame = cap.read()
            if not ret or frame is None:
                return CaptureResult(
                    success=False,
                    camera_id=camera_id,
                    error="Frame read failed",
                )

            h, w = frame.shape[:2]

            # Encode to JPEG
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.JPEG_QUALITY]
            ok, buf = cv2.imencode(".jpg", frame, encode_params)
            if not ok:
                return CaptureResult(
                    success=False,
                    camera_id=camera_id,
                    error="JPEG encoding failed",
                )

            return CaptureResult(
                success=True,
                camera_id=camera_id,
                frame_data=buf.tobytes(),
                resolution=(w, h),
            )

        except Exception as e:
            return CaptureResult(
                success=False,
                camera_id=camera_id,
                error=f"Frame capture exception: {e}",
            )

    def start_capture(self, camera_id: str) -> bool:
        """Open an RTSP stream for a registered camera."""
        camera = self.registry.get_camera(camera_id)
        if not camera:
            logger.error("Camera %s not registered", camera_id)
            return False

        if camera.protocol != CameraProtocol.RTSP:
            logger.warning(
                "Camera %s uses protocol %s, not RTSP", camera_id, camera.protocol
            )
            return False

        uri = self._resolve_rtsp_uri(camera)
        if not uri:
            return False

        cap = self._open_stream(camera_id, uri)
        if cap is None:
            return False

        self._captures[camera_id] = cap
        self._consecutive_failures[camera_id] = 0
        self.health_monitor.update_frame_received(camera_id)
        return True

    def stop_capture(self, camera_id: str) -> None:
        """Release the RTSP stream for a camera."""
        cap = self._captures.pop(camera_id, None)
        if cap is not None and HAS_CV2:
            try:
                cap.release()
            except Exception:
                pass
        logger.info("Capture stopped for %s", camera_id)

    def capture_frame(
        self,
        camera_id: str,
        sun_elevation_deg: float = 45.0,
        force: bool = False,
    ) -> Optional[CaptureResult]:
        """
        Capture a single frame from a camera if the policy allows it.

        Args:
            camera_id: registered camera ID
            sun_elevation_deg: current sun elevation for night-skip
            force: bypass capture policy (for burst/manual triggers)

        Returns:
            CaptureResult if a frame was captured, None if skipped by policy
        """
        camera = self.registry.get_camera(camera_id)
        if not camera:
            return CaptureResult(
                success=False, camera_id=camera_id, error="Not registered"
            )

        # Check capture policy
        if not force:
            last_capture = self._last_capture_time.get(camera_id)
            should = self.frame_sampler.should_capture(
                camera.capture_policy, last_capture, datetime.now(tz=timezone.utc), sun_elevation_deg
            )
            if not should:
                return None  # Skipped by policy

        # Ensure stream is open
        if camera_id not in self._captures:
            if not self.start_capture(camera_id):
                return CaptureResult(
                    success=False, camera_id=camera_id, error="Could not open stream"
                )

        # Grab frame
        result = self._grab_frame(camera_id)

        if result.success:
            self._consecutive_failures[camera_id] = 0
            self._last_capture_time[camera_id] = result.timestamp
            self.health_monitor.update_frame_received(camera_id)

            # Store the frame
            manifest = self._store_frame(camera, result)

            # Notify callback (e.g., perception engine)
            if self.on_frame_captured:
                try:
                    self.on_frame_captured(camera_id, result, manifest)
                except Exception as e:
                    logger.error("Frame callback error for %s: %s", camera_id, e)
        else:
            failures = self._consecutive_failures.get(camera_id, 0) + 1
            self._consecutive_failures[camera_id] = failures
            self.health_monitor.record_dropped_frame(camera_id)

            if failures >= self.MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    "Camera %s: %d consecutive failures — closing stream",
                    camera_id,
                    failures,
                )
                self.stop_capture(camera_id)

        return result

    def _store_frame(
        self, camera: IPCameraRegistration, result: CaptureResult
    ) -> FrameManifest:
        """Store a captured frame (manifest + raw bytes) in the FrameStore."""
        manifest_id = str(uuid.uuid4())
        frame_ref = f"frames/{camera.camera_id}/{manifest_id}.jpg"

        # Persist actual JPEG bytes
        if result.frame_data:
            self.frame_store.store_frame_bytes(frame_ref, result.frame_data)

        artifact = FrameArtifact(
            frame_ref=frame_ref,
            camera_id=camera.camera_id,
            timestamp=result.timestamp,
            original_resolution=result.resolution,
        )

        manifest = FrameManifest(
            manifest_id=manifest_id,
            camera_id=camera.camera_id,
            captured_at=result.timestamp,
            trigger_reason="cadence",
            artifacts=[artifact],
        )

        self.frame_store.store_manifest(manifest)
        return manifest

    def run_capture_cycle(
        self,
        camera_ids: Optional[List[str]] = None,
        sun_elevation_deg: float = 45.0,
    ) -> Dict[str, Optional[CaptureResult]]:
        """
        Run one capture cycle for specified cameras (or all registered).

        Returns a dict of camera_id -> CaptureResult (None if skipped by policy).
        """
        results = {}

        if camera_ids is None:
            # Enumerate all registered cameras from the registry
            all_cameras = self.registry.list_all()
            camera_ids = [c.camera_id for c in all_cameras
                          if c.protocol == CameraProtocol.RTSP]

        for cam_id in camera_ids:
            result = self.capture_frame(cam_id, sun_elevation_deg=sun_elevation_deg)
            results[cam_id] = result

        return results

    def get_active_cameras(self) -> List[str]:
        """Return IDs of cameras with active RTSP connections."""
        return list(self._captures.keys())

    def shutdown(self) -> None:
        """Release all active streams."""
        for cam_id in list(self._captures.keys()):
            self.stop_capture(cam_id)
        logger.info("All RTSP captures released")

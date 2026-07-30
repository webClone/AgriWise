from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class CameraProtocol(str, Enum):
    RTSP = "rtsp"
    HLS = "hls"
    WEBRTC_PROXY = "webrtc_proxy"


class CameraType(str, Enum):
    FIXED = "fixed"
    PTZ = "ptz"


@dataclass
class CameraViewConfig:
    """Configuration for camera position and orientation."""
    view_angle_deg: float = 90.0
    mount_height_m: float = 3.0
    mount_position: str = "corner"
    orientation_azimuth_deg: float = 0.0
    orientation_pitch_deg: float = 0.0
    coverage_zone_geojson: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IPCameraCredentialsRef:
    """
    Reference to securely stored credentials.
    Raw passwords must NEVER be stored here or passed to the frontend.
    """
    secret_id: str
    auth_type: str = "basic"  # "basic", "digest", "token"
    proxy_token_id: Optional[str] = None


@dataclass
class FrameCapturePolicy:
    """Rules for when to capture frames."""
    cadence_minutes: int = 60
    burst_mode_enabled: bool = False
    burst_trigger_events: List[str] = field(default_factory=list)
    night_skip_enabled: bool = True
    sun_elevation_min_deg: float = 5.0


@dataclass
class IPCameraRegistration:
    """Core registration identity for a camera mapped to a plot."""
    camera_id: str
    plot_id: str
    protocol: CameraProtocol
    camera_type: CameraType
    is_primary_validation_camera: bool = True
    
    view_config: CameraViewConfig = field(default_factory=CameraViewConfig)
    credentials_ref: Optional[IPCameraCredentialsRef] = None
    capture_policy: FrameCapturePolicy = field(default_factory=FrameCapturePolicy)

    # Runtime state mapped in for convenience, but truly managed by HealthMonitor
    online_status: str = "offline"
    last_frame_received_at: Optional[datetime] = None


@dataclass
class CameraHealthState:
    """Health metrics for the camera stream."""
    camera_id: str
    online: bool = False
    last_frame_at: Optional[datetime] = None
    dropped_frames_count: int = 0
    stream_jitter_ms: float = 0.0
    bitrate_kbps: float = 0.0
    tampered_or_moved: bool = False
    lens_obstruction_risk: float = 0.0  # 0-1, spiderwebs/dirt
    ptz_drift_detected: bool = False


@dataclass
class CalibrationModel:
    """
    Geometric calibration associating the camera 2D view with the 3D plot.
    Must meet hard quality gates to be used for validation.
    """
    camera_id: str
    version: int = 1
    calibration_date: Optional[datetime] = None
    
    # ROI Masks (base64 encoded PNG or URI to mask file)
    crop_roi_mask_ref: str = ""
    soil_roi_mask_ref: str = ""
    sky_roi_mask_ref: str = ""
    
    # Quality Gates (Hard Requirements for Perception Trust)
    registration_quality_score: float = 1.0  # 0-1, must be high for Kalman assimilation
    visible_plot_fraction: float = 1.0       # 0-1
    roi_stability_score: float = 1.0         # 0-1


@dataclass
class FrameArtifact:
    """A stored image captured from the stream."""
    frame_ref: str  # URI
    camera_id: str
    timestamp: datetime
    is_thumbnail: bool = False
    original_resolution: Tuple[int, int] = (1920, 1080)
    ptz_preset_id: Optional[str] = None


@dataclass
class FrameManifest:
    """Manifest describing a collection of frames or a specific capture event."""
    manifest_id: str
    camera_id: str
    captured_at: datetime
    trigger_reason: str = "cadence"  # "cadence", "burst", "manual"
    artifacts: List[FrameArtifact] = field(default_factory=list)


@dataclass
class StreamSession:
    """Backend proxy active session handle."""
    session_id: str
    camera_id: str
    started_at: datetime
    proxy_url: str  # The internal HLS/WebRTC URL that the frontend CAN see
    expires_at: datetime

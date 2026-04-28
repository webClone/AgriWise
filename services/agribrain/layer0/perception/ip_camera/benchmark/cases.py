from typing import Any, Dict, List
from dataclasses import dataclass

@dataclass
class IPCameraBenchmarkCase:
    case_name: str
    description: str
    camera_type: str = "fixed"
    expected_outputs: Dict[str, Any] = None
    expected_qa_failures: List[str] = None
    expected_validations: List[str] = None

BENCHMARK_CASES = [
    IPCameraBenchmarkCase(
        case_name="healthy_stable",
        description="Healthy, stable fixed camera with no anomalous movement or weather.",
        expected_outputs={"canopy_cover": 0.6},
        expected_qa_failures=[],
        expected_validations=[]
    ),
    IPCameraBenchmarkCase(
        case_name="phenology_progression",
        description="Gradual progression of phenology matching GDD.",
        expected_outputs={"phenology_stage_est": 2.5},
        expected_validations=["camera_vs_weather_phenology"]
    ),
    IPCameraBenchmarkCase(
        case_name="heat_stress_visual",
        description="Visible heat stress symptoms responding to high temperatures.",
        expected_outputs={"visible_stress_prob": 0.6},
        expected_validations=["camera_vs_weather_heat"]
    ),
    IPCameraBenchmarkCase(
        case_name="rain_recovery",
        description="Recovery of canopy stress immediately following an irrigation or rain event.",
        expected_outputs={"visible_stress_prob": 0.1},
        expected_validations=["camera_vs_weather_recovery"]
    ),
    IPCameraBenchmarkCase(
        case_name="satellite_cloud_false_positive",
        description="Satellite NDVI drops drastically, but camera shows stable canopy.",
        expected_outputs={"canopy_cover": 0.9},
        expected_validations=["camera_vs_satellite_cloud_artifact"]
    ),
    IPCameraBenchmarkCase(
        case_name="camera_framing_shift",
        description="Camera bumped or moved, causing registration drop. Must not be confused with crop change.",
        expected_outputs={"scene_change_type": "camera_shift"},
        expected_qa_failures=["camera_moved"]
    ),
    IPCameraBenchmarkCase(
        case_name="low_bandwidth_compression",
        description="High artifact/low bitrate rural connection. Should gracefully degrade QA without failing entirely.",
        expected_qa_failures=["high_blur"]
    ),
    IPCameraBenchmarkCase(
        case_name="ptz_preset_validation",
        camera_type="ptz",
        description="PTZ camera returning to standard validation preset to act like a fixed camera.",
        expected_outputs={"canopy_cover": 0.6}
    ),
    IPCameraBenchmarkCase(
        case_name="sun_angle_shadow_drift",
        description="Hard shadow shifts across the day causing apparent structure change without real crop change.",
        expected_outputs={},  # scene_change_type requires histogram for reliable classification
        expected_qa_failures=[]
    ),
]

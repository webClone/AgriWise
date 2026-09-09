"""MESIA mmWave Radar Native Extractor — R6 §5.7 / P5.7.

Parses point cloud and telemetry JSON output from mmWave FMCW radars
(e.g., TI IWR6843/AWR1843) to extract range, velocity, and canopy micro-Doppler.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

from ..mmwave_radar_lane import MmWaveRadarFrame


class NativeMmwaveExtractor:
    """Parses mmWave radar JSON point cloud logs into MESIA radar frames."""

    @staticmethod
    def parse_radar_json(
        file_path: str,
        start_frequency_hz: float = 60e9,
        sweep_bandwidth_hz: float = 4e9,
        num_chirps: int = 128,
        adc_samples: int = 256,
        record_id_prefix: str = "radar-frame-"
    ) -> List[MmWaveRadarFrame]:
        """
        Parses a JSON file containing mmWave radar output (e.g., a parsed UART stream).
        Expected format: list of dicts with 'timestamp', 'pointCloud', 'sensorState', etc.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Radar JSON log not found: {file_path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in Radar log {file_path}: {e}")

        if not isinstance(data, list):
            data = [data]

        frames: List[MmWaveRadarFrame] = []
        for idx, frame_data in enumerate(data):
            try:
                # Target extraction
                targets = []
                point_cloud = frame_data.get("pointCloud", [])
                micro_doppler_spread = 0.0
                velocities = []

                for pt in point_cloud:
                    range_m = float(pt.get("range", 0.0))
                    velocity = float(pt.get("velocity", 0.0))
                    azimuth = float(pt.get("azimuth", 0.0))
                    snr = float(pt.get("snr", 0.0))
                    
                    targets.append({
                        "range_m": range_m,
                        "velocity_m_s": velocity,
                        "azimuth_deg": azimuth,
                        "snr_db": snr
                    })
                    velocities.append(velocity)
                
                # Estimate canopy micro-doppler spread if there are moving points
                if velocities:
                    micro_doppler_spread = max(velocities) - min(velocities)

                # Diagnostic / Environment state
                sensor_state = frame_data.get("sensorState", {})
                is_rain = bool(sensor_state.get("rainClutterDetected", False))
                is_blocked = bool(sensor_state.get("radomeBlocked", False))

                timestamp_str = frame_data.get("timestamp", "")
                if timestamp_str:
                    try:
                        clean_time = timestamp_str.replace("Z", "+00:00")
                        ts = datetime.fromisoformat(clean_time)
                    except ValueError:
                        ts = datetime.now(timezone.utc)
                else:
                    ts = datetime.now(timezone.utc)

                frame = MmWaveRadarFrame(
                    frame_id=f"{record_id_prefix}{idx}",
                    timestamp=ts,
                    start_frequency_hz=start_frequency_hz,
                    sweep_bandwidth_hz=sweep_bandwidth_hz,
                    num_chirps_per_frame=num_chirps,
                    num_adc_samples_per_chirp=adc_samples,
                    detected_targets=targets,
                    is_rain_cluttered=is_rain,
                    is_radome_blocked=is_blocked,
                    canopy_micro_doppler_spread_hz=micro_doppler_spread
                )
                frames.append(frame)
            except Exception:
                continue

        return frames

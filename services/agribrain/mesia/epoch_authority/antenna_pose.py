"""MESIA Antenna Pose & Geometry Epoch Manager — R6 §6.3 / P6.3.

Surveys 6-DoF antenna pose, polarization, phase centre offsets, and issues
immutable GeometryEpoch instances whenever a physical movement occurs.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.epochs import GeometryEpoch


@dataclass(frozen=True)
class AntennaPoseRecord:
    """Surveyed 6-DoF pose of an antenna fixture."""

    antenna_id: str
    position_wgs84: Tuple[float, float, float]  # (lat, lon, alt_m)
    local_xyz_m: Tuple[float, float, float]     # (x, y, z) in meters
    orientation_ypr_deg: Tuple[float, float, float]  # (yaw, pitch, roll) in degrees
    polarisation: str = "VERTICAL"
    phase_centre_offset_m: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    mount_type: str = "MAST_POLE"
    pose_uncertainty_m: float = 0.005  # 5 mm default RTK survey uncertainty


class AntennaPoseAuthority:
    """Manages antenna poses and issues GeometryEpoch instances."""

    @staticmethod
    def create_geometry_epoch(
        epoch_id: str,
        pose: AntennaPoseRecord,
        site_id: str,
        plot_zone_id: str = "PLOT_01",
        valid_from: Optional[datetime] = None,
    ) -> GeometryEpoch:
        """Construct an immutable GeometryEpoch from a surveyed AntennaPoseRecord."""
        now = valid_from or datetime.now(timezone.utc)

        u_m = pose.pose_uncertainty_m
        var_pos = u_m * u_m
        pco_mm = (
            pose.phase_centre_offset_m[0] * 1000.0,
            pose.phase_centre_offset_m[1] * 1000.0,
            pose.phase_centre_offset_m[2] * 1000.0,
        )

        return GeometryEpoch(
            epoch_id=epoch_id,
            triggered_at=now,
            trigger_reason=f"Survey update for {pose.antenna_id} in {site_id} / {plot_zone_id}",
            previous_epoch_id=None,
            position_wgs84=pose.position_wgs84,
            position_local_enu=pose.local_xyz_m,
            orientation_ypr_deg=pose.orientation_ypr_deg,
            antenna_path_ref=f"ant-path-{pose.antenna_id}",
            mount_description=f"{pose.mount_type}, polarisation={pose.polarisation}",
            covariance_m=(u_m, u_m, u_m),
            position_covariance=(var_pos, 0.0, 0.0, var_pos, 0.0, var_pos),
            orientation_covariance_deg2=(0.25, 0.25, 0.25),
            antenna_model="GENERIC_MESIA_SURVEY_ANTENNA",
            phase_center_offset_mm=pco_mm,
            mount_model=pose.mount_type,
            survey_method="RTK_FIXED" if u_m <= 0.01 else "RTK_FLOAT",
            survey_time_utc=now,
        )

    @staticmethod
    def is_material_displacement(
        pose_a: AntennaPoseRecord,
        pose_b: AntennaPoseRecord,
        displacement_threshold_m: float = 0.01,
        angle_threshold_deg: float = 1.0,
    ) -> bool:
        """Determines if the difference between two poses constitutes a material physical change."""
        dx = pose_a.local_xyz_m[0] - pose_b.local_xyz_m[0]
        dy = pose_a.local_xyz_m[1] - pose_b.local_xyz_m[1]
        dz = pose_a.local_xyz_m[2] - pose_b.local_xyz_m[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)

        dyaw = abs(pose_a.orientation_ypr_deg[0] - pose_b.orientation_ypr_deg[0])
        dpitch = abs(pose_a.orientation_ypr_deg[1] - pose_b.orientation_ypr_deg[1])
        droll = abs(pose_a.orientation_ypr_deg[2] - pose_b.orientation_ypr_deg[2])
        max_angle = max(dyaw, dpitch, droll)

        return (dist >= displacement_threshold_m) or (max_angle >= angle_threshold_deg)

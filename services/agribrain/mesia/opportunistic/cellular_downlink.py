"""MESIA Passive Cellular Downlink Forward-Scatter Engine — R6 §10.6 / P8.6.

Leverages ambient 4G LTE Cell-Specific Reference Signals (CRS) and 5G NR Synchronization
Signal Blocks (SSB) as illuminators of opportunity for crop canopy biomass and water sensing.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .contracts import BistaticForwardScatterObservation


class CellularDownlinkCorrelator:
    """Computes bistatic forward-scatter attenuation from public cellular towers."""

    SPEED_OF_LIGHT = 299792458.0

    @staticmethod
    def free_space_path_loss_db(distance_m: float, freq_hz: float) -> float:
        """Computes Friis free-space path loss in dB."""
        if distance_m <= 0.0 or freq_hz <= 0.0:
            return 0.0
        return 20.0 * math.log10(distance_m) + 20.0 * math.log10(freq_hz) - 147.55

    @staticmethod
    def compute_canopy_water_index(
        excess_loss_db: float,
        path_length_m: float,
        carrier_freq_hz: float,
        nominal_specific_attenuation_db_m: float = 0.25,
    ) -> Tuple[float, float]:
        """
        Translates excess path loss into a normalized Canopy Water Index [0.0, 1.0].
        ITU-R P.833 vegetation attenuation model: A_veg = gamma * d
        gamma scales with foliar moisture fraction and leaf area index (LAI).
        Returns: (canopy_water_index, observation_variance)
        """
        if path_length_m <= 0.0:
            return 0.0, 0.25

        freq_ghz = carrier_freq_hz / 1e9
        freq_factor = math.sqrt(max(0.5, freq_ghz / 1.8))  # Normalized to 1.8 GHz

        measured_gamma = max(0.0, excess_loss_db) / path_length_m
        normalized_ratio = measured_gamma / (nominal_specific_attenuation_db_m * freq_factor + 1e-6)

        # Sigmoidal mapping to [0.0, 1.0]
        canopy_water = 1.0 / (1.0 + math.exp(-3.0 * (normalized_ratio - 1.0)))
        variance = 0.02 + 0.05 * abs(1.0 - normalized_ratio)

        return float(min(1.0, max(0.0, canopy_water))), float(variance)

    @classmethod
    def process_bistatic_reception(
        cls,
        source_tower_id: str,
        receiver_node_id: str,
        carrier_freq_hz: float,
        tower_xyz_m: Tuple[float, float, float],
        receiver_xyz_m: Tuple[float, float, float],
        measured_rsrp_dbm: float,
        tower_tx_power_dbm: float = 43.0,  # 20W typical LTE macro carrier
        canopy_depth_m: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> BistaticForwardScatterObservation:
        """
        Evaluates forward scatter attenuation of a public cellular carrier across the plot.
        """
        now = timestamp or datetime.now(timezone.utc)

        # Direct 3D distance
        dx = receiver_xyz_m[0] - tower_xyz_m[0]
        dy = receiver_xyz_m[1] - tower_xyz_m[1]
        dz = receiver_xyz_m[2] - tower_xyz_m[2]
        path_length = math.sqrt(dx * dx + dy * dy + dz * dz)

        fspl_db = cls.free_space_path_loss_db(path_length, carrier_freq_hz)
        expected_rx_power_dbm = tower_tx_power_dbm - fspl_db
        total_loss_db = tower_tx_power_dbm - measured_rsrp_dbm

        # Excess attenuation beyond free space path loss
        excess_loss_db = max(0.0, total_loss_db - fspl_db)
        depth = canopy_depth_m if canopy_depth_m is not None else min(path_length, 50.0)

        canopy_water, variance = cls.compute_canopy_water_index(
            excess_loss_db=excess_loss_db,
            path_length_m=depth,
            carrier_freq_hz=carrier_freq_hz,
        )

        raw_repr = f"CELL_{source_tower_id}_{receiver_node_id}_{carrier_freq_hz}_{measured_rsrp_dbm:.2f}_{now.isoformat()}"
        raw_hash = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()

        return BistaticForwardScatterObservation(
            observation_id=f"bistatic-cell-{source_tower_id}-{int(now.timestamp())}",
            timestamp=now,
            source_tower_id=source_tower_id,
            receiver_node_id=receiver_node_id,
            carrier_freq_hz=carrier_freq_hz,
            path_length_m=round(path_length, 2),
            measured_path_loss_db=round(total_loss_db, 2),
            free_space_loss_db=round(fspl_db, 2),
            excess_canopy_loss_db=round(excess_loss_db, 2),
            estimated_canopy_water_index=round(canopy_water, 4),
            observation_variance=round(variance, 6),
            native_iq_hash=raw_hash,
        )

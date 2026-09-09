"""MESIA Spatial Sensitivity Kernels — R6 §11.2 / P9.2.

Computes physical sensitivity Jacobian K(source, link, band, microzone, stratum)
based on first Fresnel ellipsoid volume overlap and depth attenuation decay.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .spatial_lattice import SharedBeliefLattice, MicrozoneCell, LatticeStrata


@dataclass(frozen=True)
class LinkSensitivityProfile:
    """Sensitivity kernel weights across spatial lattice microzones."""

    link_id: str
    radio_family: str
    carrier_frequency_hz: float
    weights_by_microzone: Dict[str, float]  # microzone_id -> sensitivity weight
    depth_stratum: LatticeStrata
    total_integrated_weight: float


class SensitivityKernelCalculator:
    """Calculates spatial sensitivity weight matrices for radio propagation paths."""

    @staticmethod
    def compute_link_kernel(
        link_id: str,
        radio_family: str,
        tx_pos_m: Tuple[float, float],
        rx_pos_m: Tuple[float, float],
        carrier_freq_hz: float,
        lattice: SharedBeliefLattice,
        stratum: LatticeStrata = LatticeStrata.ROOT_ZONE_5_30CM,
    ) -> LinkSensitivityProfile:
        """Compute Gaussian Fresnel ellipse sensitivity weights over microzones."""
        tx_x, tx_y = tx_pos_m
        rx_x, rx_y = rx_pos_m
        link_len = math.sqrt((rx_x - tx_x) ** 2 + (rx_y - tx_y) ** 2)

        # Wavelength lambda = c / f
        c = 3.0e8
        wavelength = c / max(1e6, carrier_freq_hz)
        fresnel_radius = math.sqrt(wavelength * max(1.0, link_len) / 4.0)

        weights: Dict[str, float] = {}
        total = 0.0

        for cell in lattice.list_all_cells():
            # Distance from cell centre to tx and rx
            d_tx = math.sqrt((cell.centre_east_m - tx_x) ** 2 + (cell.centre_north_m - tx_y) ** 2)
            d_rx = math.sqrt((cell.centre_east_m - rx_x) ** 2 + (cell.centre_north_m - rx_y) ** 2)
            path_diff = (d_tx + d_rx) - link_len

            if path_diff <= fresnel_radius * 2.0:
                w = math.exp(-0.5 * (path_diff / max(0.5, fresnel_radius)) ** 2)
                weights[cell.microzone_id] = w
                total += w

        return LinkSensitivityProfile(
            link_id=link_id,
            radio_family=radio_family,
            carrier_frequency_hz=carrier_freq_hz,
            weights_by_microzone=weights,
            depth_stratum=stratum,
            total_integrated_weight=total,
        )

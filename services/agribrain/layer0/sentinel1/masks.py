"""
Sentinel-1 SAR Mask Engine.

Produces per-pixel mask layers from VV/VH linear power and dataMask.
No cloud/shadow concepts — SAR validity is signal-based.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

# dB thresholds from CONTRACT.md
VV_DB_LOW_SIGNAL = -35.0
VH_DB_LOW_SIGNAL = -40.0
VV_DB_ARTIFACT_HIGH = 5.0  # Extremely high VV → possible artifact


@dataclass
class Sentinel1MaskSet:
    """Per-pixel SAR mask layers."""
    valid_for_backscatter: List[List[int]] = field(default_factory=list)
    valid_for_moisture: List[List[int]] = field(default_factory=list)
    valid_for_structure: List[List[int]] = field(default_factory=list)
    border_noise_like: List[List[int]] = field(default_factory=list)
    low_signal: List[List[int]] = field(default_factory=list)
    possible_water: List[List[int]] = field(default_factory=list)
    possible_layover_shadow: List[List[int]] = field(default_factory=list)


def _safe_to_db(linear: Optional[float]) -> Optional[float]:
    """Convert linear power to dB, or None if invalid."""
    if linear is None or linear <= 0:
        return None
    return 10.0 * math.log10(linear)


def compute_sar_masks(
    vv_linear: List[List[Optional[float]]],
    vh_linear: List[List[Optional[float]]],
    datamask: Optional[List[List[int]]] = None,
    alpha_mask: Optional[List[List[float]]] = None,
    border_buffer_pixels: int = 3,
) -> Sentinel1MaskSet:
    """
    Compute SAR-specific mask layers from VV/VH linear power.

    Args:
        vv_linear: VV backscatter in linear power
        vh_linear: VH backscatter in linear power
        datamask: Provider-supplied validity mask (0=invalid, 1=valid)
        alpha_mask: Plot boundary alpha (used for border noise heuristic)
        border_buffer_pixels: Edge buffer for border noise detection

    Returns:
        Sentinel1MaskSet with all mask layers populated.
    """
    h = len(vv_linear)
    w = len(vv_linear[0]) if vv_linear else 0

    valid_back = [[0] * w for _ in range(h)]
    valid_moist = [[0] * w for _ in range(h)]
    valid_struct = [[0] * w for _ in range(h)]
    border_noise = [[0] * w for _ in range(h)]
    low_sig = [[0] * w for _ in range(h)]
    water = [[0] * w for _ in range(h)]
    layover = [[0] * w for _ in range(h)]

    for r in range(h):
        for c in range(w):
            vv = vv_linear[r][c] if r < len(vv_linear) and c < len(vv_linear[r]) else None
            vh = vh_linear[r][c] if r < len(vh_linear) and c < len(vh_linear[r]) else None

            # dataMask check
            dm = 1
            if datamask is not None:
                dm = datamask[r][c] if r < len(datamask) and c < len(datamask[r]) else 0

            if dm == 0 or vv is None or vh is None or vv <= 0 or vh <= 0:
                continue  # All masks stay 0

            vv_db = _safe_to_db(vv)
            vh_db = _safe_to_db(vh)

            if vv_db is None or vh_db is None:
                continue

            # Valid for backscatter
            valid_back[r][c] = 1

            # Low signal check
            if vv_db < VV_DB_LOW_SIGNAL or vh_db < VH_DB_LOW_SIGNAL:
                low_sig[r][c] = 1
                # Still valid for backscatter but not for moisture
            else:
                valid_moist[r][c] = 1

            # Structure validity (VH must be above threshold)
            if vh_db >= VH_DB_LOW_SIGNAL:
                valid_struct[r][c] = 1

            # Possible water: very low VV and low span
            span_val = vv + vh
            if vv_db < -20.0 and span_val < 0.005:
                water[r][c] = 1

            # Possible layover/shadow artifact: extremely high VV
            if vv_db > VV_DB_ARTIFACT_HIGH:
                layover[r][c] = 1
                valid_back[r][c] = 0
                valid_moist[r][c] = 0
                valid_struct[r][c] = 0

    # Border noise heuristic: edge pixels near plot boundary with abnormally low values
    # Flag: BORDER_NOISE_HEURISTIC — this is not official ESA masking
    if alpha_mask is not None:
        for r in range(h):
            for c in range(w):
                if valid_back[r][c] == 0:
                    continue
                # Check if near plot edge
                a = alpha_mask[r][c] if r < len(alpha_mask) and c < len(alpha_mask[r]) else 0.0
                if a <= 0:
                    continue
                # Near image edge (within buffer of grid boundary)
                near_edge = (
                    r < border_buffer_pixels or r >= h - border_buffer_pixels or
                    c < border_buffer_pixels or c >= w - border_buffer_pixels
                )
                if near_edge:
                    vv = vv_linear[r][c]
                    vv_db = _safe_to_db(vv)
                    if vv_db is not None and vv_db < -25.0:
                        border_noise[r][c] = 1

    return Sentinel1MaskSet(
        valid_for_backscatter=valid_back,
        valid_for_moisture=valid_moist,
        valid_for_structure=valid_struct,
        border_noise_like=border_noise,
        low_signal=low_sig,
        possible_water=water,
        possible_layover_shadow=layover,
    )

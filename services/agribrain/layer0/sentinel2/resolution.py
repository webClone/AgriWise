"""
Sentinel-2 Raster Alignment Validation.

Rejects misaligned inputs before any index computation.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from layer0.sentinel2.schemas import Raster2D


class AlignmentError(Exception):
    """Raised when band rasters are misaligned."""
    pass


def validate_band_alignment(
    bands: Dict[str, Raster2D],
    alpha_mask: Optional[List[List[float]]] = None,
) -> None:
    """
    Validate that all band rasters are mutually aligned and
    match the plot alpha mask.

    Raises AlignmentError if:
    - Band shapes differ from each other
    - Band shapes differ from alpha mask
    - CRS differs between bands
    - Any band has aligned_to_plot_grid=False
    """
    if not bands:
        raise AlignmentError("No bands provided")

    band_names = list(bands.keys())
    ref_band = bands[band_names[0]]
    ref_shape = ref_band.grid_shape
    ref_crs = ref_band.crs

    if ref_shape[0] == 0 or ref_shape[1] == 0:
        raise AlignmentError(
            f"Reference band '{band_names[0]}' has zero-size grid: {ref_shape}"
        )

    for name in band_names:
        band = bands[name]

        # Shape check
        if band.grid_shape != ref_shape:
            raise AlignmentError(
                f"Band '{name}' shape {band.grid_shape} differs from "
                f"reference '{band_names[0]}' shape {ref_shape}"
            )

        # CRS check
        if band.crs and ref_crs and band.crs != ref_crs:
            raise AlignmentError(
                f"Band '{name}' CRS '{band.crs}' differs from "
                f"reference '{band_names[0]}' CRS '{ref_crs}'"
            )

        # Alignment flag check
        if not band.aligned_to_plot_grid:
            raise AlignmentError(
                f"Band '{name}' is not aligned to plot grid "
                f"(aligned_to_plot_grid=False)"
            )

    # Alpha mask shape check
    if alpha_mask is not None:
        alpha_h = len(alpha_mask)
        alpha_w = len(alpha_mask[0]) if alpha_mask else 0
        if (alpha_h, alpha_w) != ref_shape:
            raise AlignmentError(
                f"Alpha mask shape ({alpha_h}, {alpha_w}) differs from "
                f"band shape {ref_shape}"
            )

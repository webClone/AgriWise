"""
Sentinel-1 SAR Raster Alignment Validation.

Rejects misaligned inputs and wrong product types before any feature computation.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from layer0.sentinel1.schemas import SARRaster2D, Sentinel1SceneMetadata


class SARAlignmentError(Exception):
    """Raised when SAR rasters are misaligned or wrong product type."""
    pass


def validate_sar_alignment(
    rasters: Dict[str, SARRaster2D],
    alpha_mask: Optional[List[List[float]]] = None,
    metadata: Optional[Sentinel1SceneMetadata] = None,
) -> None:
    """
    Validate that all SAR rasters are mutually aligned and match the plot alpha mask.

    Raises SARAlignmentError if:
    - No rasters provided
    - VV or VH missing
    - VV not polarization="VV" or VH not polarization="VH"
    - VV or VH not unit="linear_power"
    - Shapes differ between rasters
    - Shapes differ from alpha mask
    - CRS differs between rasters
    - Any raster has aligned_to_plot_grid=False
    - Metadata instrument_mode != IW or polarization != DV
    """
    if not rasters:
        raise SARAlignmentError("No rasters provided")

    # VV and VH must exist
    if "VV" not in rasters:
        raise SARAlignmentError("Missing required VV raster")
    if "VH" not in rasters:
        raise SARAlignmentError("Missing required VH raster")

    # Polarization labels must be correct
    vv = rasters["VV"]
    vh = rasters["VH"]
    if vv.polarization != "VV":
        raise SARAlignmentError(
            f"VV raster has wrong polarization: {vv.polarization}"
        )
    if vh.polarization != "VH":
        raise SARAlignmentError(
            f"VH raster has wrong polarization: {vh.polarization}"
        )

    # Input unit must be linear_power for VV/VH
    if vv.unit != "linear_power":
        raise SARAlignmentError(
            f"VV raster must have unit='linear_power', got '{vv.unit}'. "
            "Convert dB to linear before passing to engine."
        )
    if vh.unit != "linear_power":
        raise SARAlignmentError(
            f"VH raster must have unit='linear_power', got '{vh.unit}'. "
            "Convert dB to linear before passing to engine."
        )

    # Reference shape and CRS
    ref_shape = vv.grid_shape
    ref_crs = vv.crs

    # All rasters must match
    for name, raster in rasters.items():
        if raster.grid_shape != ref_shape:
            raise SARAlignmentError(
                f"Raster '{name}' shape {raster.grid_shape} != "
                f"reference shape {ref_shape}"
            )
        if raster.crs != ref_crs:
            raise SARAlignmentError(
                f"Raster '{name}' CRS '{raster.crs}' != reference CRS '{ref_crs}'"
            )
        if not raster.aligned_to_plot_grid:
            raise SARAlignmentError(
                f"Raster '{name}' is not aligned to PlotGrid"
            )

    # Alpha mask shape check
    if alpha_mask is not None:
        ah = len(alpha_mask)
        aw = len(alpha_mask[0]) if alpha_mask else 0
        if (ah, aw) != ref_shape:
            raise SARAlignmentError(
                f"Alpha mask shape ({ah}, {aw}) != raster shape {ref_shape}"
            )

    # Metadata product type validation
    if metadata is not None:
        if metadata.instrument_mode != "IW":
            raise SARAlignmentError(
                f"V1 only supports IW mode, got '{metadata.instrument_mode}'"
            )
        if metadata.polarization != "DV":
            raise SARAlignmentError(
                f"V1 only supports DV polarization, got '{metadata.polarization}'"
            )

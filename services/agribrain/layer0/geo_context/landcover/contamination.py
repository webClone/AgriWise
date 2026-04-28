"""
Boundary Contamination Analysis.

Computes interior/edge/neighbor-buffer land cover fractions (Revision 7)
and generates plot validity flags.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from layer0.geo_context.schemas import RasterInput
from layer0.geo_context.landcover.schemas import (
    ESA_WORLDCOVER_CLASSES,
    BoundaryContamination,
)


# Interior/edge mask pixel distance thresholds
DEFAULT_EDGE_PIXELS = 2  # pixels from boundary that count as "edge"


def compute_boundary_contamination(
    worldcover_raster: RasterInput,
    alpha_mask: Optional[np.ndarray] = None,
    neighbor_buffer_raster: Optional[RasterInput] = None,
    edge_pixels: int = DEFAULT_EDGE_PIXELS,
) -> BoundaryContamination:
    """Analyze interior, edge, and neighbor-buffer land cover.

    Masks (Revision 7):
        interior = alpha == 1 and distance_to_boundary > edge_pixels
        edge = alpha > 0 and not interior
        neighbor = outside plot within buffer

    Args:
        worldcover_raster: Plot-clipped WorldCover class raster.
        alpha_mask: Plot boundary alpha mask [0,1]. If None, uses raster's alpha.
        neighbor_buffer_raster: Optional WorldCover raster covering neighbor buffer area.
        edge_pixels: Number of pixels from boundary that count as "edge".
    """
    data = worldcover_raster.data.astype(int)
    valid = worldcover_raster.valid_mask

    if alpha_mask is None:
        alpha_mask = worldcover_raster.alpha_mask
    if alpha_mask is None:
        alpha_mask = valid.astype(float)

    # Build interior/edge masks
    interior_mask, edge_mask = _build_interior_edge_masks(alpha_mask, valid, edge_pixels)

    # Interior fractions
    interior_cropland = _class_fraction(data, valid & interior_mask, class_id=40)

    # Edge fractions
    edge_tree = _class_fraction(data, valid & edge_mask, class_id=10)
    edge_water = _class_fraction(data, valid & edge_mask, class_id=80)
    edge_builtup = _class_fraction(data, valid & edge_mask, class_id=50)

    # Neighbor buffer fractions
    neighbor_tree = 0.0
    neighbor_water = 0.0
    neighbor_builtup = 0.0
    neighbor_cropland_continuity = 0.0

    if neighbor_buffer_raster is not None:
        nb_data = neighbor_buffer_raster.data.astype(int)
        nb_valid = neighbor_buffer_raster.valid_mask
        neighbor_tree = _class_fraction(nb_data, nb_valid, class_id=10)
        neighbor_water = _class_fraction(nb_data, nb_valid, class_id=80)
        neighbor_builtup = _class_fraction(nb_data, nb_valid, class_id=50)
        neighbor_cropland_continuity = _class_fraction(nb_data, nb_valid, class_id=40)

    # Contamination scores
    tree_contam = _compute_tree_edge_contamination(
        neighbor_tree, edge_tree,
        edge_mask.sum() / max(valid.sum(), 1),
    )
    water_contam = _compute_water_contamination(edge_water, _class_fraction(data, valid, 80))
    builtup_contam = _compute_builtup_contamination(neighbor_builtup, edge_builtup)
    boundary_mismatch = _compute_boundary_mismatch(
        interior_cropland, edge_tree, edge_water, edge_builtup,
    )

    # Flags
    flags = generate_plot_validity_flags(
        interior_cropland=interior_cropland,
        edge_tree=edge_tree,
        edge_water=edge_water,
        edge_builtup=edge_builtup,
        neighbor_tree=neighbor_tree,
        tree_contam=tree_contam,
        water_contam=water_contam,
        builtup_contam=builtup_contam,
        boundary_mismatch=boundary_mismatch,
    )

    return BoundaryContamination(
        interior_cropland_fraction=round(interior_cropland, 4),
        edge_tree_fraction=round(edge_tree, 4),
        edge_water_fraction=round(edge_water, 4),
        edge_builtup_fraction=round(edge_builtup, 4),
        neighbor_tree_fraction=round(neighbor_tree, 4),
        neighbor_water_fraction=round(neighbor_water, 4),
        neighbor_builtup_fraction=round(neighbor_builtup, 4),
        neighbor_cropland_continuity_score=round(neighbor_cropland_continuity, 4),
        tree_edge_contamination_score=round(tree_contam, 4),
        water_edge_contamination_score=round(water_contam, 4),
        builtup_edge_contamination_score=round(builtup_contam, 4),
        boundary_mismatch_score=round(boundary_mismatch, 4),
        flags=flags,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_interior_edge_masks(
    alpha: np.ndarray, valid: np.ndarray, edge_pixels: int,
) -> tuple:
    """Build interior and edge boolean masks.

    Interior: alpha == 1 and far from boundary.
    Edge: alpha > 0 and close to boundary.
    """
    plot_mask = (alpha > 0) & valid

    # Erode plot mask by edge_pixels to find interior
    interior = plot_mask.copy()
    for _ in range(edge_pixels):
        interior = _erode_mask(interior)

    edge = plot_mask & ~interior
    return interior, edge


def _erode_mask(mask: np.ndarray) -> np.ndarray:
    """Simple 1-pixel erosion using neighbor checking."""
    h, w = mask.shape
    eroded = mask.copy()

    padded = np.pad(mask, 1, mode="constant", constant_values=False)
    for di in [-1, 0, 1]:
        for dj in [-1, 0, 1]:
            if di == 0 and dj == 0:
                continue
            neighbor = padded[1 + di:h + 1 + di, 1 + dj:w + 1 + dj]
            eroded = eroded & neighbor

    return eroded


def _class_fraction(
    data: np.ndarray, mask: np.ndarray, class_id: int,
) -> float:
    """Fraction of masked pixels matching class_id."""
    total = mask.sum()
    if total == 0:
        return 0.0
    class_count = ((data == class_id) & mask).sum()
    return float(class_count / total)


def _compute_tree_edge_contamination(
    neighbor_tree: float, edge_tree: float, edge_fraction: float,
) -> float:
    """Tree edge contamination = neighbor_tree * edge_fraction * edge_tree_boost."""
    return min(neighbor_tree * max(edge_fraction, 0.1) + edge_tree * 0.5, 1.0)


def _compute_water_contamination(
    edge_water: float, interior_water: float,
) -> float:
    """Water contamination from edge and interior presence."""
    return min(edge_water * 0.6 + interior_water * 0.4, 1.0)


def _compute_builtup_contamination(
    neighbor_builtup: float, edge_builtup: float,
) -> float:
    """Built-up contamination from neighbor and edge."""
    return min(neighbor_builtup * 0.5 + edge_builtup * 0.5, 1.0)


def _compute_boundary_mismatch(
    interior_crop: float, edge_tree: float,
    edge_water: float, edge_builtup: float,
) -> float:
    """Boundary mismatch = interior is crop but edge is non-crop."""
    if interior_crop < 0.5:
        return 0.5  # interior isn't crop, boundary is inherently mismatched
    edge_non_crop = edge_tree + edge_water + edge_builtup
    return min(edge_non_crop, 1.0)


def generate_plot_validity_flags(
    interior_cropland: float,
    edge_tree: float,
    edge_water: float,
    edge_builtup: float,
    neighbor_tree: float,
    tree_contam: float,
    water_contam: float,
    builtup_contam: float,
    boundary_mismatch: float,
) -> List[str]:
    """Generate plot validity flags from contamination analysis."""
    flags: List[str] = []

    if interior_cropland < 0.5:
        flags.append("PLOT_NON_AGRICULTURAL_RISK")

    if water_contam > 0.2:
        flags.append("PLOT_WATER_CONTAMINATION")

    if builtup_contam > 0.2:
        flags.append("PLOT_BUILTUP_CONTAMINATION")

    if tree_contam > 0.3:
        flags.append("TREE_EDGE_CONTAMINATION")

    if boundary_mismatch > 0.3:
        flags.append("DECLARED_BOUNDARY_MISMATCH")

    if interior_cropland < 0.3:
        flags.append("LOW_CROPLAND_CONFIDENCE")

    return flags

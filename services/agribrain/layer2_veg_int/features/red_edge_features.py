"""
Crop Intelligence v6.0A — Red-Edge Spectral Feature Extraction.

Extracts temporal features from Sentinel-2 red-edge indices
(NDRE, CIred-edge, MTCI, PSRI, REIP) in FieldTensor plot_timeseries.

Resolution/provenance notes:
  - B04 = 10m native, B05/B06/B07/B8A = 20m native
  - Red-edge indices use 20m bands → extraction_warnings includes
    "red_edge_20m_resampled" when these features are computed
  - B06/B07 are NOT yet in the Copernicus evalscript → CIred_edge,
    MTCI, PSRI, REIP return None until bands are added
  - NDRE (B05+B8A) works today

References:
  - Gitelson (2005): CIred-edge for chlorophyll content
  - Dash & Curran (2004): MTCI — MERIS Terrestrial Chlorophyll Index
  - Merzlyak et al. (1999): PSRI — Plant Senescence Reflectance Index
  - Guyot & Baret (1988): REIP — Red Edge Inflection Point
  - Clevers & Gitelson (2013): NDRE for chlorophyll estimation

Dependencies: None (pure Python, stdlib only)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("agribrain.v6.red_edge_features")


# ============================================================================
# RedEdgeFeatures dataclass
# ============================================================================

@dataclass
class RedEdgeFeatures:
    """Temporal red-edge spectral features.

    All features Optional — graceful degradation when indices unavailable.

    Hierarchy level annotations:
      L1, L2: ndre_mean, cired_mean (broad chlorophyll separation)
      L2, L3: ndre_peak, ndre_at_peak_ndvi, ndre_ndvi_ratio_mean
      L3:     mtci_at_senescence, psri_greenup_vs_senescence, reip_peak
    """
    # NDRE features (available today: B05 + B8A)
    ndre_peak: Optional[float] = None           # Max NDRE value
    ndre_mean: Optional[float] = None           # Average NDRE
    ndre_at_peak_ndvi: Optional[float] = None   # NDRE at NDVI-peak timestep
    ndre_ndvi_ratio_mean: Optional[float] = None  # mean(NDRE/NDVI) — chlorophyll efficiency

    # CIred-edge features (needs B07+B8A — not yet fetched)
    cired_peak: Optional[float] = None          # Max CIred-edge
    cired_mean: Optional[float] = None          # Average CIred-edge

    # MTCI features (needs B04+B05+B06 — B06 not yet fetched)
    mtci_peak: Optional[float] = None           # Max MTCI
    mtci_at_senescence: Optional[float] = None  # MTCI at senescence onset

    # PSRI features (needs B02+B04+B06 — B06 not yet fetched)
    psri_max: Optional[float] = None            # Max PSRI (senescence indicator)
    psri_greenup_vs_senescence: Optional[float] = None  # PSRI early / PSRI late

    # REIP features (needs B04+B05+B06+B07 — B06/B07 not yet fetched)
    reip_peak: Optional[float] = None           # Max REIP (nm)
    reip_mean: Optional[float] = None           # Average REIP (nm)

    # Data quality
    data_completeness: Optional[float] = None   # count(non-null) / total
    n_observations: int = 0
    extraction_warnings: List[str] = field(default_factory=list)


# ============================================================================
# Feature extraction
# ============================================================================

def extract_red_edge_features(
    plot_timeseries: List[Dict],
    *,
    ndvi_peak_idx: Optional[int] = None,
    senescence_start_idx: Optional[int] = None,
) -> RedEdgeFeatures:
    """Extract red-edge temporal features from plot_timeseries entries.

    Each entry in plot_timeseries is expected to be a dict with keys like:
      ndvi_mean, ndre_mean, cired_mean, mtci_mean, psri_mean, reip_mean

    Currently only ndre_mean is populated by L0 Sentinel-2 engine.
    Other indices return None until B06/B07 are added to the evalscript.

    Args:
        plot_timeseries: List of per-timestep dicts from FieldTensor
        ndvi_peak_idx: Index of NDVI peak timestep (for ndre_at_peak_ndvi)
        senescence_start_idx: Index of senescence onset (for mtci_at_senescence)

    Returns:
        RedEdgeFeatures with all extractable metrics.
    """
    feat = RedEdgeFeatures()

    if not plot_timeseries:
        feat.extraction_warnings.append("no_timeseries_data")
        return feat

    feat.n_observations = len(plot_timeseries)

    # ── Extract series from timeseries entries ──
    ndre_values: List[Optional[float]] = []
    ndvi_values: List[Optional[float]] = []
    cired_values: List[Optional[float]] = []
    mtci_values: List[Optional[float]] = []
    psri_values: List[Optional[float]] = []
    reip_values: List[Optional[float]] = []

    for entry in plot_timeseries:
        # Handle both dict-style and attribute-style access
        if isinstance(entry, dict):
            ndre_values.append(entry.get("ndre_mean") or entry.get("ndre"))
            ndvi_values.append(entry.get("ndvi_mean") or entry.get("ndvi"))
            cired_values.append(entry.get("cired_mean") or entry.get("cired_edge"))
            mtci_values.append(entry.get("mtci_mean") or entry.get("mtci"))
            psri_values.append(entry.get("psri_mean") or entry.get("psri"))
            reip_values.append(entry.get("reip_mean") or entry.get("reip"))
        else:
            ndre_values.append(getattr(entry, "ndre_mean", None))
            ndvi_values.append(getattr(entry, "ndvi_mean", None))
            cired_values.append(getattr(entry, "cired_mean", None))
            mtci_values.append(getattr(entry, "mtci_mean", None))
            psri_values.append(getattr(entry, "psri_mean", None))
            reip_values.append(getattr(entry, "reip_mean", None))

    # ── NDRE features (available today) ──
    ndre_valid = [v for v in ndre_values if v is not None]
    if ndre_valid:
        feat.ndre_peak = round(max(ndre_valid), 4)
        feat.ndre_mean = round(sum(ndre_valid) / len(ndre_valid), 4)
        # Add resolution warning: NDRE uses 20m bands
        feat.extraction_warnings.append("red_edge_20m_resampled")

        # NDRE at NDVI peak
        if ndvi_peak_idx is not None and ndvi_peak_idx < len(ndre_values):
            val = ndre_values[ndvi_peak_idx]
            if val is not None:
                feat.ndre_at_peak_ndvi = round(val, 4)

        # NDRE/NDVI ratio
        ndvi_valid = [v for v in ndvi_values if v is not None]
        if ndvi_valid and len(ndre_valid) >= 3:
            ratios = []
            for ndre, ndvi in zip(ndre_values, ndvi_values):
                if ndre is not None and ndvi is not None and ndvi > 0.05:
                    ratios.append(ndre / ndvi)
            if ratios:
                feat.ndre_ndvi_ratio_mean = round(sum(ratios) / len(ratios), 4)

    # ── CIred-edge features ──
    cired_valid = [v for v in cired_values if v is not None]
    if cired_valid:
        feat.cired_peak = round(max(cired_valid), 4)
        feat.cired_mean = round(sum(cired_valid) / len(cired_valid), 4)
    else:
        feat.extraction_warnings.append("CIred_edge_unavailable")

    # ── MTCI features ──
    mtci_valid = [v for v in mtci_values if v is not None]
    if mtci_valid:
        feat.mtci_peak = round(max(mtci_valid), 4)
        if senescence_start_idx is not None and senescence_start_idx < len(mtci_values):
            val = mtci_values[senescence_start_idx]
            if val is not None:
                feat.mtci_at_senescence = round(val, 4)
    else:
        feat.extraction_warnings.append("MTCI_unavailable")

    # ── PSRI features ──
    psri_valid = [v for v in psri_values if v is not None]
    if psri_valid:
        feat.psri_max = round(max(psri_valid), 4)

        # PSRI greenup vs senescence asymmetry
        n = len(psri_values)
        if n >= 6:
            first_half = [v for v in psri_values[:n // 2] if v is not None]
            second_half = [v for v in psri_values[n // 2:] if v is not None]
            if first_half and second_half:
                early_mean = sum(first_half) / len(first_half)
                late_mean = sum(second_half) / len(second_half)
                if abs(late_mean) > 0.001:
                    feat.psri_greenup_vs_senescence = round(early_mean / late_mean, 4)
    else:
        feat.extraction_warnings.append("PSRI_unavailable")

    # ── REIP features ──
    reip_valid = [v for v in reip_values if v is not None]
    if reip_valid:
        feat.reip_peak = round(max(reip_valid), 2)
        feat.reip_mean = round(sum(reip_valid) / len(reip_valid), 2)
    else:
        feat.extraction_warnings.append("REIP_unavailable_missing_B06_B07")

    # ── Data completeness ──
    total_features = 12  # Total numeric features in RedEdgeFeatures
    non_null = sum(1 for v in [
        feat.ndre_peak, feat.ndre_mean, feat.ndre_at_peak_ndvi,
        feat.ndre_ndvi_ratio_mean, feat.cired_peak, feat.cired_mean,
        feat.mtci_peak, feat.mtci_at_senescence, feat.psri_max,
        feat.psri_greenup_vs_senescence, feat.reip_peak, feat.reip_mean,
    ] if v is not None)
    feat.data_completeness = round(non_null / total_features, 3)

    return feat

"""
Crop Intelligence v6.0A — Phenology Feature Extraction.

Extracts multi-season NDVI phenological metrics from FieldTensor
plot_timeseries data. Backbone for crop identity at all 4 hierarchy levels.

Cross-year phenology handling:
  Winter cereals (Algeria/MENA) have SOS in autumn (DOY ~300) and EOS in
  spring (DOY ~160). All DOY arithmetic uses doy_distance() to handle
  year-boundary crossings correctly.

References:
  - Jönsson & Eklundh (2004): TIMESAT phenology extraction
  - Wardlow & Egbert (2008): MODIS NDVI for crop classification
  - Bolton & Friedl (2013): Phenology-based crop identification

Dependencies: numpy (via crop_ml.smooth_ndvi / extract_phenology)
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("agribrain.v6.phenology_features")

# Try numpy + crop_ml (expected to be available)
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from services.agribrain.layer2_veg_int.crop_ml import smooth_ndvi, extract_phenology
    HAS_CROP_ML = True
except ImportError:
    HAS_CROP_ML = False


# ============================================================================
# Cross-year DOY helpers
# ============================================================================

def doy_distance(start: int, end: int) -> int:
    """Compute day-of-year distance handling year-boundary crossings.

    For winter crops (Algeria/MENA), SOS can be in autumn (DOY ~300)
    and EOS in spring (DOY ~160). Naive subtraction gives negative values.

    Args:
        start: Start day-of-year (1-365)
        end: End day-of-year (1-365)

    Returns:
        Positive distance in days, wrapping around year boundary.

    Examples:
        doy_distance(300, 160) = 225  (winter wheat: Oct→Jun)
        doy_distance(90, 270) = 180   (maize: Mar→Sep)
        doy_distance(100, 100) = 0    (same day)
    """
    if end >= start:
        return end - start
    return (365 - start) + end


def doy_midpoint(start: int, end: int) -> int:
    """Compute midpoint DOY between two dates, handling year boundary.

    Args:
        start: Start day-of-year (1-365)
        end: End day-of-year (1-365)

    Returns:
        Midpoint DOY (1-365).
    """
    dist = doy_distance(start, end)
    mid = (start + dist // 2) % 365
    return mid if mid > 0 else 365


def doy_asymmetry(sos: int, pos: int, eos: int) -> float:
    """Compute seasonal asymmetry using cross-year-safe DOY math.

    asymmetry = doy_distance(sos, pos) / doy_distance(sos, eos)

    Returns:
        Float in [0, 1]. < 0.5 = early peak, > 0.5 = late peak.
        Returns 0.5 if season length is zero.
    """
    total = doy_distance(sos, eos)
    if total <= 0:
        return 0.5
    greenup = doy_distance(sos, pos)
    return min(1.0, max(0.0, greenup / total))


# ============================================================================
# Date utility
# ============================================================================

def _date_str_to_doy(date_str: str) -> Optional[int]:
    """Convert 'YYYY-MM-DD' string to day-of-year. Returns None on failure."""
    try:
        parts = date_str[:10].split("-")
        if len(parts) >= 3:
            from datetime import date as dt_date
            d = dt_date(int(parts[0]), int(parts[1]), int(parts[2]))
            return d.timetuple().tm_yday
    except Exception:
        pass
    return None


def _elapsed_calendar_days(dates: List[str]) -> Optional[List[float]]:
    parsed = []
    for value in dates:
        try:
            item = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if item.tzinfo is None:
            item = item.replace(tzinfo=timezone.utc)
        parsed.append(item.astimezone(timezone.utc))
    if not parsed:
        return []
    origin = parsed[0]
    elapsed = [(item - origin).total_seconds() / 86400.0 for item in parsed]
    if any(elapsed[index] <= elapsed[index - 1] for index in range(1, len(elapsed))):
        return None
    return elapsed


# ============================================================================
# PhenologyFeatures dataclass
# ============================================================================

@dataclass
class PhenologyFeatures:
    """Multi-season NDVI phenological features.

    All DOY distances computed with doy_distance() for cross-year safety.
    Inter-annual features are None when only one season is available.

    Hierarchy level annotations:
      L0: peak_ndvi, base_ndvi, amplitude, cv_ndvi (active crop vs non-crop)
      L1: n_seasons, is_evergreen, los_days (annual vs perennial vs fallow)
      L2: sos_doy, pos_doy, growth_rate, senescence_rate (crop group)
      L3: asymmetry, greenup_duration, senescence_duration (exact crop)
    """
    # Per-season features (primary season)
    sos_doy: Optional[int] = None          # Start of Season (day-of-year)
    pos_doy: Optional[int] = None          # Peak of Season (day-of-year)
    eos_doy: Optional[int] = None          # End of Season (day-of-year)
    los_days: Optional[int] = None         # Length of Season (days, cross-year safe)
    peak_ndvi: Optional[float] = None      # Peak NDVI value
    base_ndvi: Optional[float] = None      # Base/trough NDVI (10th percentile)
    amplitude: Optional[float] = None      # Seasonal amplitude (peak - base)
    growth_rate: Optional[float] = None    # NDVI/day during greenup
    senescence_rate: Optional[float] = None  # NDVI/day during senescence
    small_integral: Optional[float] = None   # Area above base (net productivity)
    large_integral: Optional[float] = None   # Total area under curve
    asymmetry: Optional[float] = None      # (pos-sos)/(eos-sos), cross-year safe
    cv_ndvi: Optional[float] = None        # Temporal variability (std/mean)
    greenup_duration_days: Optional[int] = None    # SOS to peak (cross-year safe)
    senescence_duration_days: Optional[int] = None  # Peak to EOS (cross-year safe)
    sos_gdd: Optional[float] = None       # Cumulative GDD at start of season
    pos_gdd: Optional[float] = None       # Cumulative GDD at peak of season
    eos_gdd: Optional[float] = None       # Cumulative GDD at end of season
    growth_rate_per_gdd: Optional[float] = None
    senescence_rate_per_gdd: Optional[float] = None

    # Multi-season features
    n_seasons: Optional[int] = None        # Number of growing seasons detected
    is_evergreen: Optional[bool] = None    # Perennial flat profile

    # NDVI velocity profile — 5-point summary of smoothed 1st derivative
    velocity_p10: Optional[float] = None
    velocity_p25: Optional[float] = None
    velocity_p50: Optional[float] = None   # Median velocity
    velocity_p75: Optional[float] = None
    velocity_p90: Optional[float] = None

    # Inter-annual features (None when only 1 season available)
    sos_interannual_std: Optional[float] = None      # Std of SOS across seasons
    peak_interannual_std: Optional[float] = None      # Std of peak NDVI across seasons
    amplitude_interannual_cv: Optional[float] = None   # CV of amplitude across seasons
    seasonal_pattern_shift: Optional[float] = None     # Curve dissimilarity between seasons

    # Provenance
    data_source: str = "plot_timeseries"
    n_observations: int = 0
    extraction_warnings: List[str] = field(default_factory=list)


# ============================================================================
# Feature extraction
# ============================================================================

def extract_phenology_features(
    ndvi_series: List[float],
    dates: List[str],
    *,
    gdd_series: Optional[List[float]] = None,
) -> PhenologyFeatures:
    """Extract phenological features from an NDVI time-series.

    Args:
        ndvi_series: NDVI values (raw or pre-smoothed)
        dates: ISO date strings corresponding to each NDVI value
        gdd_series: Optional cumulative GDD series aligned with ``dates``.

    Returns:
        PhenologyFeatures with all extractable metrics.
        Features that cannot be computed are None.
    """
    feat = PhenologyFeatures(n_observations=len(ndvi_series))

    if len(ndvi_series) < 5:
        feat.extraction_warnings.append("insufficient_observations")
        return feat
    if len(dates) != len(ndvi_series):
        feat.extraction_warnings.append("ndvi_timestamp_alignment_invalid")
        return feat
    elapsed_days = _elapsed_calendar_days(dates)
    if elapsed_days is None:
        feat.extraction_warnings.append("ndvi_calendar_axis_invalid")
        return feat

    # ── Smooth and extract base phenology ──
    if HAS_CROP_ML and HAS_NUMPY:
        smoothed = smooth_ndvi(list(ndvi_series))
        pheno = extract_phenology(smoothed, dates)
    else:
        # Minimal fallback: use raw series
        feat.extraction_warnings.append("crop_ml_unavailable_using_raw")
        smoothed = ndvi_series
        pheno = {}

    if not pheno:
        feat.extraction_warnings.append("phenology_extraction_failed")
        return feat

    # ── Basic statistics ──
    if HAS_NUMPY:
        arr = np.array(smoothed, dtype=float)
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr))
        feat.cv_ndvi = round(std_val / max(mean_val, 0.01), 4)
    else:
        mean_val = sum(smoothed) / max(len(smoothed), 1)
        variance = sum((x - mean_val) ** 2 for x in smoothed) / max(len(smoothed), 1)
        std_val = math.sqrt(variance)
        feat.cv_ndvi = round(std_val / max(mean_val, 0.01), 4)

    # ── Per-season features from extract_phenology output ──
    feat.peak_ndvi = pheno.get("peak_val")
    feat.base_ndvi = pheno.get("base_val")
    feat.amplitude = pheno.get("amplitude")
    feat.small_integral = pheno.get("small_integral")
    feat.large_integral = pheno.get("large_integral")
    feat.n_seasons = pheno.get("n_seasons")
    feat.is_evergreen = pheno.get("is_evergreen", False)
    feat.growth_rate = pheno.get("growth_rate")
    feat.senescence_rate = pheno.get("senescence_rate")

    # Replace index-based rates and areas with physical calendar-time
    # quantities.  Missing/rejected scenes therefore create a longer interval
    # instead of being mistaken for one nominal timestep.
    sos_idx = pheno.get("sos_idx")
    pos_idx = pheno.get("pos_idx")
    eos_idx = pheno.get("eos_idx")
    if (
        isinstance(sos_idx, int) and isinstance(pos_idx, int)
        and 0 <= sos_idx < pos_idx < len(smoothed)
    ):
        duration = elapsed_days[pos_idx] - elapsed_days[sos_idx]
        if duration > 0.0:
            feat.growth_rate = round(
                (float(smoothed[pos_idx]) - float(smoothed[sos_idx])) / duration,
                8,
            )
    if (
        isinstance(pos_idx, int) and isinstance(eos_idx, int)
        and 0 <= pos_idx < eos_idx < len(smoothed)
    ):
        duration = elapsed_days[eos_idx] - elapsed_days[pos_idx]
        if duration > 0.0:
            feat.senescence_rate = round(
                (float(smoothed[eos_idx]) - float(smoothed[pos_idx])) / duration,
                8,
            )

    valid_gdd = None
    if gdd_series is not None:
        try:
            candidate_gdd = [float(value) for value in gdd_series]
        except (TypeError, ValueError):
            candidate_gdd = []
        if (
            len(candidate_gdd) == len(smoothed)
            and all(math.isfinite(value) for value in candidate_gdd)
            and all(
                candidate_gdd[index] >= candidate_gdd[index - 1]
                for index in range(1, len(candidate_gdd))
            )
        ):
            valid_gdd = candidate_gdd
        else:
            feat.extraction_warnings.append("gdd_axis_invalid_or_misaligned")
    if valid_gdd is not None:
        if isinstance(sos_idx, int) and 0 <= sos_idx < len(valid_gdd):
            feat.sos_gdd = round(valid_gdd[sos_idx], 6)
        if isinstance(pos_idx, int) and 0 <= pos_idx < len(valid_gdd):
            feat.pos_gdd = round(valid_gdd[pos_idx], 6)
        if isinstance(eos_idx, int) and 0 <= eos_idx < len(valid_gdd):
            feat.eos_gdd = round(valid_gdd[eos_idx], 6)
        if (
            isinstance(sos_idx, int) and isinstance(pos_idx, int)
            and 0 <= sos_idx < pos_idx < len(valid_gdd)
        ):
            delta_gdd = valid_gdd[pos_idx] - valid_gdd[sos_idx]
            if delta_gdd > 0.0:
                feat.growth_rate_per_gdd = round(
                    (float(smoothed[pos_idx]) - float(smoothed[sos_idx])) / delta_gdd,
                    10,
                )
        if (
            isinstance(pos_idx, int) and isinstance(eos_idx, int)
            and 0 <= pos_idx < eos_idx < len(valid_gdd)
        ):
            delta_gdd = valid_gdd[eos_idx] - valid_gdd[pos_idx]
            if delta_gdd > 0.0:
                feat.senescence_rate_per_gdd = round(
                    (float(smoothed[eos_idx]) - float(smoothed[pos_idx])) / delta_gdd,
                    10,
                )
    if len(smoothed) == len(elapsed_days):
        base = float(feat.base_ndvi or 0.0)
        large_integral = 0.0
        small_integral = 0.0
        for index in range(1, len(smoothed)):
            delta_days = elapsed_days[index] - elapsed_days[index - 1]
            left = float(smoothed[index - 1])
            right = float(smoothed[index])
            large_integral += 0.5 * (left + right) * delta_days
            small_integral += 0.5 * (
                max(0.0, left - base) + max(0.0, right - base)
            ) * delta_days
        feat.large_integral = round(large_integral, 6)
        feat.small_integral = round(small_integral, 6)

    # ── DOY features with cross-year safety ──
    sos_doy = pheno.get("sos_doy")
    pos_doy = pheno.get("pos_doy")
    eos_doy = pheno.get("eos_doy")

    # If DOY not available from extract_phenology, compute from indices + dates
    if sos_doy is None and "sos_idx" in pheno:
        idx = pheno["sos_idx"]
        if idx is not None and idx < len(dates):
            sos_doy = _date_str_to_doy(dates[idx])
    if pos_doy is None and "pos_idx" in pheno:
        idx = pheno["pos_idx"]
        if idx is not None and idx < len(dates):
            pos_doy = _date_str_to_doy(dates[idx])
    if eos_doy is None and "eos_idx" in pheno:
        idx = pheno["eos_idx"]
        if idx is not None and idx < len(dates):
            eos_doy = _date_str_to_doy(dates[idx])

    feat.sos_doy = sos_doy
    feat.pos_doy = pos_doy
    feat.eos_doy = eos_doy

    # Cross-year-safe durations
    if sos_doy is not None and eos_doy is not None:
        feat.los_days = doy_distance(sos_doy, eos_doy)
    if sos_doy is not None and pos_doy is not None:
        feat.greenup_duration_days = doy_distance(sos_doy, pos_doy)
    if pos_doy is not None and eos_doy is not None:
        feat.senescence_duration_days = doy_distance(pos_doy, eos_doy)

    # Cross-year-safe asymmetry
    if sos_doy is not None and pos_doy is not None and eos_doy is not None:
        feat.asymmetry = round(doy_asymmetry(sos_doy, pos_doy, eos_doy), 4)

    # ── NDVI velocity profile ──
    if HAS_NUMPY and len(smoothed) >= 10:
        day_steps = np.diff(np.array(elapsed_days, dtype=float))
        velocity = np.diff(smoothed) / day_steps
        feat.velocity_p10 = round(float(np.percentile(velocity, 10)), 6)
        feat.velocity_p25 = round(float(np.percentile(velocity, 25)), 6)
        feat.velocity_p50 = round(float(np.percentile(velocity, 50)), 6)
        feat.velocity_p75 = round(float(np.percentile(velocity, 75)), 6)
        feat.velocity_p90 = round(float(np.percentile(velocity, 90)), 6)

    # ── Multi-season segmentation ──
    # If series spans > 300 days and has > 1 season, extract per-season stats
    if feat.n_seasons is not None and feat.n_seasons >= 2 and len(ndvi_series) > 60:
        _extract_multi_season_stats(feat, smoothed, dates)

    return feat


def _extract_multi_season_stats(
    feat: PhenologyFeatures,
    smoothed: Any,  # np.ndarray or list
    dates: List[str],
) -> None:
    """Extract inter-annual features when multiple seasons are detected.

    Modifies feat in-place. If extraction fails, inter-annual features
    remain None.
    """
    if not HAS_NUMPY or not HAS_CROP_ML:
        return

    arr = np.array(smoothed, dtype=float)
    n = len(arr)

    # Segment seasons by finding valleys (local minima below base + 0.3*amplitude)
    base = float(np.percentile(arr, 10))
    peak = float(np.max(arr))
    amp = peak - base
    if amp < 0.05:
        return  # Flat profile, no meaningful seasons

    threshold = base + 0.3 * amp

    # Find season boundaries: consecutive runs above threshold
    above = arr >= threshold
    seasons = []
    in_season = False
    start_idx = 0

    for i, v in enumerate(above):
        if v and not in_season:
            start_idx = i
            in_season = True
        elif not v and in_season:
            if i - start_idx >= 10:  # Minimum 10 observations per season
                seasons.append((start_idx, i - 1))
            in_season = False
    if in_season and n - start_idx >= 10:
        seasons.append((start_idx, n - 1))

    if len(seasons) < 2:
        return

    # Per-season phenology
    season_sos_doys = []
    season_peak_ndvis = []
    season_amplitudes = []
    season_curves = []

    for s_start, s_end in seasons:
        seg = arr[s_start:s_end + 1]
        seg_dates = dates[s_start:s_end + 1]

        seg_peak = float(np.max(seg))
        seg_base = float(np.min(seg))
        seg_amp = seg_peak - seg_base

        season_peak_ndvis.append(seg_peak)
        season_amplitudes.append(seg_amp)

        # SOS DOY
        if s_start < len(dates):
            doy = _date_str_to_doy(dates[s_start])
            if doy is not None:
                season_sos_doys.append(doy)

        # Normalized curve for similarity comparison
        if seg_amp > 0.01:
            norm_curve = (seg - seg_base) / seg_amp
            season_curves.append(norm_curve)

    # Inter-annual statistics
    if len(season_sos_doys) >= 2:
        feat.sos_interannual_std = round(float(np.std(season_sos_doys)), 1)

    if len(season_peak_ndvis) >= 2:
        feat.peak_interannual_std = round(float(np.std(season_peak_ndvis)), 4)

    if len(season_amplitudes) >= 2:
        amp_mean = float(np.mean(season_amplitudes))
        amp_std = float(np.std(season_amplitudes))
        if amp_mean > 0.01:
            feat.amplitude_interannual_cv = round(amp_std / amp_mean, 4)

    # Seasonal pattern shift: mean absolute difference between normalized curves
    if len(season_curves) >= 2:
        min_len = min(len(c) for c in season_curves)
        if min_len >= 5:
            # Resample all curves to min_len for comparison
            diffs = []
            ref = season_curves[0][:min_len]
            for curve in season_curves[1:]:
                cmp = curve[:min_len]
                diff = float(np.mean(np.abs(ref - cmp)))
                diffs.append(diff)
            feat.seasonal_pattern_shift = round(float(np.mean(diffs)), 4)

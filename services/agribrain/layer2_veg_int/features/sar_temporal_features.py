"""
Crop Intelligence v6.0A — SAR Temporal Feature Extraction.

Extracts temporal dynamics from Sentinel-1 VV/VH time-series.
Not just single-date means — temporal behavior is the discriminative signal.

dB/linear conversion rules (adjustment #3):
  - vv_mean_db, vh_mean_db, vv_amplitude_db, vh_amplitude_db: dB domain
  - vv_vh_ratio_mean, vv_vh_ratio_trend: linear power domain (VV/VH)
  - rvi_peak, rvi_mean: linear power domain (4·VH/(VV+VH))
  - All conversions explicitly documented per feature

Change-point detection:
  Simplified CUSUM (cumulative sum of deviations from running mean).
  Detects tillage, harvest, and structural breaks in SAR signal.

Dependencies: Python stdlib only (math, statistics). No numpy required.

References:
  - Veloso et al. (2017): SAR temporal signatures for crop mapping
  - Vreugdenhil et al. (2018): Sentinel-1 for agricultural monitoring
  - Page (1954): CUSUM change-point detection
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("agribrain.v6.sar_temporal_features")


# ============================================================================
# dB / linear conversion utilities (adjustment #3)
# ============================================================================

def db_to_linear(db: float) -> float:
    """Convert dB to linear power.

    Used for: VV/VH ratio, RVI — these are physically meaningful
    only in linear power domain.

    Args:
        db: Backscatter value in dB

    Returns:
        Linear power value (always > 0)
    """
    return 10.0 ** (db / 10.0)


def linear_to_db(x: float) -> float:
    """Convert linear power to dB.

    Used for: amplitude, mean backscatter — reporting convention.

    Args:
        x: Linear power value (must be > 0)

    Returns:
        dB value. Returns -120 for zero/negative inputs.
    """
    if x <= 0:
        return -120.0
    return 10.0 * math.log10(x)


# ============================================================================
# Simple flood score proxy (adjustment #4)
# ============================================================================

def compute_flood_score(
    vv_db: float,
    vh_db: float,
    *,
    ndwi: Optional[float] = None,
    vv_db_baseline: float = -12.0,
) -> float:
    """Transparent flood/waterlogging proxy score [0, 1].

    Science:
      - Standing water causes specular reflection → very low VV and VH
      - Sudden VV drop below baseline indicates surface water
      - NDWI > 0.3 corroborates water presence

    Weights:
      low_vv = 0.35, low_vh = 0.25, sudden_drop = 0.25, ndwi_high = 0.15

    NOT calibrated soil moisture. This is a binary-ish indicator
    of surface water presence, useful for crop cycle disruption detection.

    Args:
        vv_db: VV backscatter in dB
        vh_db: VH backscatter in dB
        ndwi: Optional NDWI value (if available from optical)
        vv_db_baseline: Baseline VV for "sudden drop" detection

    Returns:
        Flood score in [0, 1]. >0.6 suggests potential waterlogging.
    """
    # Low VV component: water → VV drops to -20 dB or below
    low_vv = max(0.0, min(1.0, (-15.0 - vv_db) / 10.0))

    # Low VH component: water → VH drops to -25 dB or below
    low_vh = max(0.0, min(1.0, (-20.0 - vh_db) / 10.0))

    # Sudden VV drop: compared to per-plot baseline
    sudden_drop = max(0.0, min(1.0, (vv_db_baseline - vv_db) / 8.0))

    # Optional NDWI corroboration
    ndwi_component = 0.0
    if ndwi is not None and ndwi > 0.0:
        ndwi_component = max(0.0, min(1.0, (ndwi - 0.1) / 0.4))

    score = (0.35 * low_vv + 0.25 * low_vh +
             0.25 * sudden_drop + 0.15 * ndwi_component)

    return round(max(0.0, min(1.0, score)), 4)


# ============================================================================
# CUSUM change-point detection
# ============================================================================

def _detect_change_points(
    series: List[float],
    threshold: float = 2.0,
    min_spacing: int = 5,
) -> List[int]:
    """Detect change points using simplified CUSUM.

    Cumulative sum of deviations from running mean. When the CUSUM
    exceeds a threshold, a change point is registered.

    Args:
        series: Time-series values
        threshold: CUSUM threshold in standard deviations
        min_spacing: Minimum gap between detected change points

    Returns:
        List of indices where change points were detected.
    """
    if len(series) < 10:
        return []

    # Running statistics
    n = len(series)
    mean_val = sum(series) / n
    std_val = math.sqrt(sum((x - mean_val) ** 2 for x in series) / n)

    if std_val < 1e-8:
        return []

    # CUSUM
    cusum_pos = 0.0
    cusum_neg = 0.0
    change_points = []
    last_cp = -min_spacing

    for i, val in enumerate(series):
        z = (val - mean_val) / std_val
        cusum_pos = max(0.0, cusum_pos + z - 0.5)
        cusum_neg = max(0.0, cusum_neg - z - 0.5)

        if (cusum_pos > threshold or cusum_neg > threshold) and (i - last_cp) >= min_spacing:
            change_points.append(i)
            cusum_pos = 0.0
            cusum_neg = 0.0
            last_cp = i

    return change_points


# ============================================================================
# Rolling median
# ============================================================================

def _rolling_median(series: List[float], window: int = 5) -> List[float]:
    """Simple rolling median using stdlib sorted().

    Args:
        series: Input values
        window: Window size (centered)

    Returns:
        Rolling median series (same length, edge-padded).
    """
    n = len(series)
    if n == 0:
        return []
    half = window // 2
    result = []
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        chunk = sorted(series[start:end])
        mid = len(chunk) // 2
        if len(chunk) % 2 == 0 and len(chunk) >= 2:
            median_val = (chunk[mid - 1] + chunk[mid]) / 2.0
        else:
            median_val = chunk[mid]
        result.append(round(median_val, 4))
    return result


# ============================================================================
# Linear trend slope
# ============================================================================

def _linear_slope(
    series: List[float], coordinates: Optional[List[float]] = None,
) -> Optional[float]:
    """Compute simple linear regression slope.

    Args:
        series: Values to regress.
        coordinates: Optional physical time coordinates.  When supplied the
            result is in units per coordinate (calendar day in crop use).

    Returns:
        Slope (units per step), or None if < 3 values.
    """
    n = len(series)
    if n < 3:
        return None
    x = list(coordinates) if coordinates is not None else [float(i) for i in range(n)]
    if len(x) != n or any(not math.isfinite(value) for value in x):
        return None
    x_mean = sum(x) / n
    y_mean = sum(series) / n
    num = sum((x[i] - x_mean) * (series[i] - y_mean) for i in range(n))
    denom = sum((value - x_mean) ** 2 for value in x)
    if abs(denom) < 1e-12:
        return None
    return num / denom


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _calendar_coordinates(dates: List[str]) -> Optional[List[float]]:
    parsed = [_parse_datetime(value) for value in dates]
    if any(value is None for value in parsed):
        return None
    assert parsed and parsed[0] is not None
    origin = parsed[0]
    values = [
        (value - origin).total_seconds() / 86400.0  # type: ignore[operator]
        for value in parsed
    ]
    if any(values[index] <= values[index - 1] for index in range(1, len(values))):
        return None
    return values


def _calendar_rolling_median(
    series: List[float], coordinates: List[float], window_days: float = 30.0,
) -> List[float]:
    if len(series) != len(coordinates):
        return []
    half_window = window_days / 2.0
    result = []
    for center in coordinates:
        values = sorted(
            value for value, coordinate in zip(series, coordinates)
            if abs(coordinate - center) <= half_window
        )
        if not values:
            continue
        middle = len(values) // 2
        median = (
            (values[middle - 1] + values[middle]) / 2.0
            if len(values) % 2 == 0 else values[middle]
        )
        result.append(round(median, 4))
    return result


# ============================================================================
# SARTemporalFeatures dataclass
# ============================================================================

@dataclass
class SARTemporalFeatures:
    """Temporal SAR features from Sentinel-1 VV/VH time-series.

    dB/linear domain is EXPLICITLY labeled per feature:
      - *_db features: dB domain
      - ratio, rvi features: linear power domain
      - amplitudes: dB domain (max_db - min_db)

    Hierarchy level annotations:
      L0, L1: vv_mean_db, vh_mean_db, vv_std_db (active crop vs non-crop)
      L1, L2: vh_amplitude_db, rvi_peak, sar_crop_cycle_amplitude
      L2, L3: vv_vh_ratio_trend, n_change_points, change_point_doys
      metadata: sar_optical_quality_ratio (dynamic weight hint for v6.0C)
    """
    # ── dB domain features ──
    vv_mean_db: Optional[float] = None          # Mean VV backscatter (dB)
    vv_std_db: Optional[float] = None           # Std VV (dB)
    vh_mean_db: Optional[float] = None          # Mean VH backscatter (dB)
    vh_std_db: Optional[float] = None           # Std VH (dB)
    vh_amplitude_db: Optional[float] = None     # max(VH_dB) - min(VH_dB) — biomass range
    vv_amplitude_db: Optional[float] = None     # max(VV_dB) - min(VV_dB) — moisture range

    # ── Linear power domain features ──
    vv_vh_ratio_mean: Optional[float] = None    # mean(linear VV / linear VH)
    vv_vh_ratio_trend: Optional[float] = None   # Linear slope of ratio series
    rvi_peak: Optional[float] = None            # max RVI: 4·VH_lin/(VV_lin+VH_lin)
    rvi_mean: Optional[float] = None            # mean RVI

    # ── SAR season signal (dB) ──
    sar_crop_cycle_amplitude: Optional[float] = None  # Peak-to-trough VH in season (dB)

    # ── Change-point features (indices → DOY-summarized for ML) ──
    n_change_points: Optional[int] = None              # Number of structural breaks
    first_change_point_doy: Optional[int] = None       # DOY of first break
    last_change_point_doy: Optional[int] = None        # DOY of last break

    # ── Rolling median summaries (for to_flat_dict) ──
    vv_rolling_median_mean: Optional[float] = None
    vv_rolling_median_slope: Optional[float] = None
    vh_rolling_median_mean: Optional[float] = None
    vh_rolling_median_slope: Optional[float] = None

    # ── Event-dependent features (adjustment #5) ──
    post_irrigation_vv_response: Optional[float] = None  # VV spike after irrigation
    flood_signature_count: Optional[int] = None           # Timesteps with flood_score > 0.6

    # ── Dynamic weight metadata ──
    sar_optical_quality_ratio: Optional[float] = None  # sar_count / optical_count

    # Provenance
    n_observations: int = 0
    extraction_warnings: List[str] = field(default_factory=list)

    # Full diagnostic lists (available via to_json, NOT in to_flat_dict)
    _change_point_doys: List[int] = field(default_factory=list)
    _vv_rolling_median_30d: List[float] = field(default_factory=list)
    _vh_rolling_median_30d: List[float] = field(default_factory=list)


# ============================================================================
# Feature extraction
# ============================================================================

def extract_sar_temporal_features(
    plot_timeseries: List[Dict],
    *,
    optical_obs_count: Optional[int] = None,
    irrigation_events: Optional[List[Dict]] = None,
) -> SARTemporalFeatures:
    """Extract SAR temporal features from plot_timeseries entries.

    Each entry is a dict with keys like:
      vv_mean, vh_mean, vv_vh_ratio_mean, date

    Ledger-derived VV/VH values must declare dB or linear-power units and S1
    orbit geometry.  Legacy callers retain a labelled inference fallback.

    Args:
        plot_timeseries: List of per-timestep dicts from FieldTensor
        optical_obs_count: Number of optical observations (for quality ratio)
        irrigation_events: Optional list of {"date": "YYYY-MM-DD"} dicts.
            If absent, post_irrigation_vv_response = None.

    Returns:
        SARTemporalFeatures with all extractable metrics.
    """
    feat = SARTemporalFeatures()

    if not plot_timeseries:
        feat.extraction_warnings.append("no_sar_timeseries_data")
        return feat

    # ── Extract VV/VH series ──
    samples: List[Dict] = []
    for entry in plot_timeseries:
        if isinstance(entry, dict):
            vv = entry.get("vv_mean")
            if vv is None:
                vv = entry.get("vv")
            vh = entry.get("vh_mean")
            if vh is None:
                vh = entry.get("vh")
            date_str = entry.get("date", entry.get("timestamp", ""))
            ndwi = entry.get("ndwi_mean")
            if ndwi is None:
                ndwi = entry.get("ndwi")
            orbit_direction = str(
                entry.get("orbit_direction") or entry.get("orbit_pass") or ""
            ).strip().upper()
            relative_orbit = str(
                entry.get("relative_orbit") or entry.get("orbit_reference") or ""
            ).strip().upper()
            unit = str(entry.get("backscatter_unit") or "").strip().lower()
        else:
            vv = getattr(entry, "vv_mean", None)
            vh = getattr(entry, "vh_mean", None)
            date_str = getattr(entry, "date", "")
            ndwi = getattr(entry, "ndwi_mean", None)
            orbit_direction = str(
                getattr(entry, "orbit_direction", "") or ""
            ).strip().upper()
            relative_orbit = str(
                getattr(entry, "relative_orbit", "") or ""
            ).strip().upper()
            unit = str(getattr(entry, "backscatter_unit", "") or "").strip().lower()
        if vv is None or vh is None:
            continue
        try:
            vv_value = float(vv)
            vh_value = float(vh)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(vv_value) or not math.isfinite(vh_value):
            continue
        parsed_date = _parse_datetime(str(date_str))
        if parsed_date is None:
            feat.extraction_warnings.append("sar_observation_timestamp_invalid")
            continue
        if unit in {"db", "decibel", "decibels"}:
            vv_db, vh_db = vv_value, vh_value
            vv_lin, vh_lin = db_to_linear(vv_value), db_to_linear(vh_value)
        elif unit in {"linear", "linear_power", "power"}:
            if vv_value <= 0.0 or vh_value <= 0.0:
                feat.extraction_warnings.append("sar_linear_backscatter_nonpositive")
                continue
            vv_lin, vh_lin = vv_value, vh_value
            vv_db, vh_db = linear_to_db(vv_value), linear_to_db(vh_value)
        else:
            # Compatibility only. Ledger tokens always declare the unit.
            if vv_value < 0.0 and vh_value < 0.0:
                vv_db, vh_db = vv_value, vh_value
                vv_lin, vh_lin = db_to_linear(vv_value), db_to_linear(vh_value)
                feat.extraction_warnings.append("sar_unit_inferred_legacy_db")
            elif vv_value > 0.0 and vh_value > 0.0:
                vv_lin, vh_lin = vv_value, vh_value
                vv_db, vh_db = linear_to_db(vv_value), linear_to_db(vh_value)
                feat.extraction_warnings.append("sar_unit_inferred_legacy_linear")
            else:
                feat.extraction_warnings.append("sar_backscatter_unit_ambiguous")
                continue
        track = (
            f"{orbit_direction}:{relative_orbit}"
            if orbit_direction in {"ASCENDING", "DESCENDING"} and relative_orbit
            else ""
        )
        samples.append({
            "vv_db": vv_db, "vh_db": vh_db,
            "vv_lin": vv_lin, "vh_lin": vh_lin,
            "date": parsed_date,
            "date_text": parsed_date.date().isoformat(),
            "ndwi": ndwi,
            "track": track,
        })

    explicit_tracks: Dict[str, List[Dict]] = {}
    for sample in samples:
        if sample["track"]:
            explicit_tracks.setdefault(sample["track"], []).append(sample)
    if explicit_tracks:
        selected_track, selected_samples = max(
            explicit_tracks.items(),
            key=lambda item: (
                len(item[1]),
                (max(row["date"] for row in item[1]) - min(
                    row["date"] for row in item[1]
                )).total_seconds(),
                item[0],
            ),
        )
        excluded_count = len(samples) - len(selected_samples)
        samples = selected_samples
        if len(explicit_tracks) > 1 or excluded_count:
            feat.extraction_warnings.append(
                f"sar_single_orbit_track_selected:{selected_track}:excluded={excluded_count}"
            )
    elif samples:
        feat.extraction_warnings.append("sar_orbit_geometry_unavailable")
    samples.sort(key=lambda item: item["date"])

    vv_db_series: List[float] = []
    vh_db_series: List[float] = []
    vv_lin_series: List[float] = []
    vh_lin_series: List[float] = []
    dates: List[str] = []
    ndwi_series: List[Optional[float]] = []

    for sample in samples:
        vv_db_series.append(round(sample["vv_db"], 4))
        vh_db_series.append(round(sample["vh_db"], 4))
        vv_lin_series.append(sample["vv_lin"])
        vh_lin_series.append(sample["vh_lin"])
        dates.append(sample["date_text"])
        ndwi_series.append(sample["ndwi"])

    feat.n_observations = len(vv_db_series)

    if feat.n_observations < 5:
        feat.extraction_warnings.append("insufficient_sar_observations")
        return feat

    elapsed_days = _calendar_coordinates(dates)
    if elapsed_days is None:
        feat.extraction_warnings.append("sar_calendar_axis_invalid")
        return feat

    # ── dB domain statistics ──
    feat.vv_mean_db = round(sum(vv_db_series) / len(vv_db_series), 2)
    feat.vh_mean_db = round(sum(vh_db_series) / len(vh_db_series), 2)

    vv_variance = sum((x - feat.vv_mean_db) ** 2 for x in vv_db_series) / len(vv_db_series)
    vh_variance = sum((x - feat.vh_mean_db) ** 2 for x in vh_db_series) / len(vh_db_series)
    feat.vv_std_db = round(math.sqrt(vv_variance), 3)
    feat.vh_std_db = round(math.sqrt(vh_variance), 3)

    feat.vv_amplitude_db = round(max(vv_db_series) - min(vv_db_series), 2)
    feat.vh_amplitude_db = round(max(vh_db_series) - min(vh_db_series), 2)

    # ── Linear power domain statistics ──
    # VV/VH ratio (physically correct only in linear domain)
    ratios = []
    rvi_values = []
    for vv_l, vh_l in zip(vv_lin_series, vh_lin_series):
        if vh_l > 1e-10:
            ratios.append(vv_l / vh_l)
        denom = vv_l + vh_l
        if denom > 1e-10:
            rvi_values.append(4.0 * vh_l / denom)

    if ratios:
        feat.vv_vh_ratio_mean = round(sum(ratios) / len(ratios), 4)
        feat.vv_vh_ratio_trend = _linear_slope(ratios, elapsed_days)
        if feat.vv_vh_ratio_trend is not None:
            feat.vv_vh_ratio_trend = round(feat.vv_vh_ratio_trend, 6)

    if rvi_values:
        feat.rvi_peak = round(max(rvi_values), 4)
        feat.rvi_mean = round(sum(rvi_values) / len(rvi_values), 4)

    # ── SAR crop cycle amplitude ──
    # Use VH dB: rising VH = growing biomass, falling = harvest/senescence
    feat.sar_crop_cycle_amplitude = feat.vh_amplitude_db

    # ── Change-point detection (on VH dB series) ──
    cp_indices = _detect_change_points(vh_db_series, threshold=2.5)
    feat.n_change_points = len(cp_indices)

    cp_doys = []
    for idx in cp_indices:
        if idx < len(dates) and dates[idx]:
            doy = _date_str_to_doy(dates[idx])
            if doy is not None:
                cp_doys.append(doy)
    feat._change_point_doys = cp_doys

    if cp_doys:
        feat.first_change_point_doy = cp_doys[0]
        feat.last_change_point_doy = cp_doys[-1]

    # ── Rolling median (30-day equivalent ≈ 5 observations at 6-day revisit) ──
    vv_rolling = _calendar_rolling_median(
        vv_db_series, elapsed_days, window_days=30.0,
    )
    vh_rolling = _calendar_rolling_median(
        vh_db_series, elapsed_days, window_days=30.0,
    )
    feat._vv_rolling_median_30d = vv_rolling
    feat._vh_rolling_median_30d = vh_rolling

    if vv_rolling:
        feat.vv_rolling_median_mean = round(sum(vv_rolling) / len(vv_rolling), 3)
        slope = _linear_slope(vv_rolling, elapsed_days)
        feat.vv_rolling_median_slope = round(slope, 6) if slope is not None else None

    if vh_rolling:
        feat.vh_rolling_median_mean = round(sum(vh_rolling) / len(vh_rolling), 3)
        slope = _linear_slope(vh_rolling, elapsed_days)
        feat.vh_rolling_median_slope = round(slope, 6) if slope is not None else None

    # ── Flood signature count (adjustment #4) ──
    # Use transparent flood_score proxy
    vv_baseline = feat.vv_mean_db or -12.0
    flood_count = 0
    for i in range(len(vv_db_series)):
        ndwi_val = ndwi_series[i] if i < len(ndwi_series) else None
        score = compute_flood_score(
            vv_db_series[i], vh_db_series[i],
            ndwi=ndwi_val, vv_db_baseline=vv_baseline
        )
        if score > 0.6:
            flood_count += 1
    feat.flood_signature_count = flood_count

    # ── Post-irrigation VV response (adjustment #5) ──
    # Requires explicit irrigation_events input
    if irrigation_events:
        feat.post_irrigation_vv_response = _compute_irrigation_response(
            vv_db_series, dates, irrigation_events
        )
    else:
        # Explicitly None — do not infer without event timestamps
        feat.post_irrigation_vv_response = None

    # ── SAR/optical quality ratio ──
    if optical_obs_count is not None and optical_obs_count > 0:
        feat.sar_optical_quality_ratio = round(
            feat.n_observations / optical_obs_count, 3
        )

    return feat


def _compute_irrigation_response(
    vv_db_series: List[float],
    dates: List[str],
    irrigation_events: List[Dict],
) -> Optional[float]:
    """Compute mean VV response after known irrigation events.

    Looks for VV increase 1-3 timesteps after each irrigation event.
    VV rises when soil gets wet (higher dielectric constant).

    Returns:
        Mean VV increase (dB) after irrigation events, or None.
    """
    if not irrigation_events or len(vv_db_series) < 3:
        return None

    # Build date-to-index lookup
    date_to_idx = {}
    for i, d in enumerate(dates):
        if d:
            date_to_idx[d] = i

    responses = []
    for event in irrigation_events:
        event_date = event.get("date", "")[:10]
        idx = date_to_idx.get(event_date)
        if idx is None:
            # Try closest date
            continue

        # Look at 1-3 timesteps after irrigation
        pre_val = vv_db_series[idx] if idx < len(vv_db_series) else None
        post_vals = []
        for offset in range(1, 4):
            pi = idx + offset
            if pi < len(vv_db_series):
                post_vals.append(vv_db_series[pi])

        if pre_val is not None and post_vals:
            post_mean = sum(post_vals) / len(post_vals)
            responses.append(post_mean - pre_val)

    if responses:
        return round(sum(responses) / len(responses), 3)
    return None


def _date_str_to_doy(date_str: str) -> Optional[int]:
    """Convert 'YYYY-MM-DD' string to day-of-year."""
    try:
        parts = date_str[:10].split("-")
        if len(parts) >= 3:
            from datetime import date as dt_date
            d = dt_date(int(parts[0]), int(parts[1]), int(parts[2]))
            return d.timetuple().tm_yday
    except Exception:
        pass
    return None

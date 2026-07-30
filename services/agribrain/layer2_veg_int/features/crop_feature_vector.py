"""
Crop Intelligence v6.0A — Crop Feature Vector Assembly.

Assembles phenology, red-edge, and SAR temporal features into a unified
CropFeatureVector consumed by v6.0C hierarchical classifiers.

to_flat_dict() rules (adjustment #6):
  - Returns ONLY fixed-length numeric features (~45-50 keys)
  - Variable-length lists (rolling medians, change points, velocity profiles)
    are summarized as scalar statistics (mean, slope, min, max, percentiles)
  - Full lists are available via to_json() for diagnostics

Feature availability by hierarchy level:
  L0: peak_ndvi, amplitude, cv_ndvi, vv_mean_db (~8 features)
  L1: n_seasons, is_evergreen, los_days, vh_amplitude_db (~12 features)
  L2: sos_doy, growth_rate, ndre ratios, sar_amplitude (~20 features)
  L3: full feature set + red-edge + SAR temporal (~45-50 features)

Dependencies: layer2_veg_int.features.{phenology, red_edge, sar_temporal}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from layer2_veg_int.features.phenology_features import (
    PhenologyFeatures,
    extract_phenology_features,
)
from layer2_veg_int.features.red_edge_features import (
    RedEdgeFeatures,
    extract_red_edge_features,
)
from layer2_veg_int.features.sar_temporal_features import (
    SARTemporalFeatures,
    extract_sar_temporal_features,
)

logger = logging.getLogger("agribrain.v6.crop_feature_vector")


# ============================================================================
# Feature-to-hierarchy-level mapping
# ============================================================================

# Features required at each hierarchy level for completeness scoring
_LEVEL_FEATURES = {
    "L0": [
        "peak_ndvi", "base_ndvi", "amplitude", "cv_ndvi",
        "vv_mean_db", "vh_mean_db", "n_seasons", "is_evergreen",
    ],
    "L1": [
        "peak_ndvi", "amplitude", "cv_ndvi", "n_seasons", "is_evergreen",
        "los_days", "vv_mean_db", "vh_mean_db", "vv_std_db", "vh_std_db",
        "vh_amplitude_db", "rvi_mean",
    ],
    "L2": [
        "sos_doy", "pos_doy", "eos_doy", "los_days", "growth_rate",
        "senescence_rate", "asymmetry", "small_integral",
        "ndre_mean", "ndre_peak", "ndre_ndvi_ratio_mean",
        "vv_vh_ratio_mean", "vh_amplitude_db", "sar_crop_cycle_amplitude",
        "n_change_points", "rvi_peak",
        "latitude", "aridity_index",
    ],
    "L3": [
        "sos_doy", "pos_doy", "eos_doy", "los_days", "growth_rate",
        "senescence_rate", "asymmetry", "greenup_duration_days",
        "senescence_duration_days", "small_integral", "large_integral",
        "velocity_p10", "velocity_p50", "velocity_p90",
        "ndre_peak", "ndre_mean", "ndre_at_peak_ndvi", "ndre_ndvi_ratio_mean",
        "cired_peak", "cired_mean", "mtci_peak", "mtci_at_senescence",
        "psri_max", "reip_peak", "reip_mean",
        "vv_vh_ratio_mean", "vv_vh_ratio_trend", "rvi_peak", "rvi_mean",
        "vh_amplitude_db", "vv_amplitude_db", "sar_crop_cycle_amplitude",
        "n_change_points", "first_change_point_doy", "last_change_point_doy",
        "vv_rolling_median_slope", "vh_rolling_median_slope",
        "latitude", "longitude", "aridity_index", "plot_area_ha",
        "seasonal_pattern_shift",
    ],
}


# ============================================================================
# CropFeatureVector dataclass
# ============================================================================

@dataclass
class CropFeatureVector:
    """Unified feature vector for hierarchical crop classification.

    Consumed by v6.0C classifiers. NOT consumed by current v5.1 engine.
    Each field group is Optional — classifiers handle missingness.

    Designed to feed:
      Level 0 — active_crop vs non_crop
      Level 1 — annual/perennial/orchard/fallow
      Level 2 — crop group
      Level 3 — exact crop candidates
    """
    # Identity
    plot_id: str = ""
    run_id: str = ""
    extraction_timestamp: str = ""
    feature_vector_version: str = "6.0.0"

    # Feature groups (each Optional — partial data is normal)
    phenology: Optional[PhenologyFeatures] = None
    red_edge: Optional[RedEdgeFeatures] = None
    sar_temporal: Optional[SARTemporalFeatures] = None

    # Context features (from L1 / orchestrator)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    koppen_zone: Optional[str] = None
    aridity_index: Optional[float] = None
    soil_texture_class: Optional[str] = None
    irrigation_type: Optional[str] = None
    plot_area_ha: Optional[float] = None

    # Provenance
    data_sources: List[str] = field(default_factory=list)
    data_completeness: float = 0.0
    extraction_warnings: List[str] = field(default_factory=list)

    def to_flat_dict(self) -> Dict[str, Optional[float]]:
        """Flatten all numeric features into a fixed-length dict for ML input.

        Rules (adjustment #6):
          - Only scalar numeric features included
          - Variable-length lists summarized as scalar statistics
          - Boolean features encoded as 0.0/1.0
          - String/categorical features excluded (use to_json())
          - Returns ~45-50 keys with stable naming

        Returns:
            Dict[str, Optional[float]] — fixed-length, ML-ready.
        """
        d: Dict[str, Optional[float]] = {}

        # ── Phenology features (scalars) ──
        if self.phenology:
            p = self.phenology
            d["sos_doy"] = float(p.sos_doy) if p.sos_doy is not None else None
            d["pos_doy"] = float(p.pos_doy) if p.pos_doy is not None else None
            d["eos_doy"] = float(p.eos_doy) if p.eos_doy is not None else None
            d["los_days"] = float(p.los_days) if p.los_days is not None else None
            d["peak_ndvi"] = p.peak_ndvi
            d["base_ndvi"] = p.base_ndvi
            d["amplitude"] = p.amplitude
            d["growth_rate"] = p.growth_rate
            d["senescence_rate"] = p.senescence_rate
            d["small_integral"] = p.small_integral
            d["large_integral"] = p.large_integral
            d["asymmetry"] = p.asymmetry
            d["cv_ndvi"] = p.cv_ndvi
            d["greenup_duration_days"] = float(p.greenup_duration_days) if p.greenup_duration_days is not None else None
            d["senescence_duration_days"] = float(p.senescence_duration_days) if p.senescence_duration_days is not None else None
            d["n_seasons"] = float(p.n_seasons) if p.n_seasons is not None else None
            d["is_evergreen"] = 1.0 if p.is_evergreen else 0.0

            # Velocity profile — fixed-length percentile summary (not raw list)
            d["velocity_p10"] = p.velocity_p10
            d["velocity_p25"] = p.velocity_p25
            d["velocity_p50"] = p.velocity_p50
            d["velocity_p75"] = p.velocity_p75
            d["velocity_p90"] = p.velocity_p90

            # Inter-annual features
            d["sos_interannual_std"] = p.sos_interannual_std
            d["peak_interannual_std"] = p.peak_interannual_std
            d["amplitude_interannual_cv"] = p.amplitude_interannual_cv
            d["seasonal_pattern_shift"] = p.seasonal_pattern_shift
        else:
            # All None when no phenology
            for key in [
                "sos_doy", "pos_doy", "eos_doy", "los_days", "peak_ndvi",
                "base_ndvi", "amplitude", "growth_rate", "senescence_rate",
                "small_integral", "large_integral", "asymmetry", "cv_ndvi",
                "greenup_duration_days", "senescence_duration_days",
                "n_seasons", "is_evergreen",
                "velocity_p10", "velocity_p25", "velocity_p50",
                "velocity_p75", "velocity_p90",
                "sos_interannual_std", "peak_interannual_std",
                "amplitude_interannual_cv", "seasonal_pattern_shift",
            ]:
                d[key] = None

        # ── Red-edge features (all scalars) ──
        if self.red_edge:
            r = self.red_edge
            d["ndre_peak"] = r.ndre_peak
            d["ndre_mean"] = r.ndre_mean
            d["ndre_at_peak_ndvi"] = r.ndre_at_peak_ndvi
            d["ndre_ndvi_ratio_mean"] = r.ndre_ndvi_ratio_mean
            d["cired_peak"] = r.cired_peak
            d["cired_mean"] = r.cired_mean
            d["mtci_peak"] = r.mtci_peak
            d["mtci_at_senescence"] = r.mtci_at_senescence
            d["psri_max"] = r.psri_max
            d["psri_greenup_vs_senescence"] = r.psri_greenup_vs_senescence
            d["reip_peak"] = r.reip_peak
            d["reip_mean"] = r.reip_mean
        else:
            for key in [
                "ndre_peak", "ndre_mean", "ndre_at_peak_ndvi",
                "ndre_ndvi_ratio_mean", "cired_peak", "cired_mean",
                "mtci_peak", "mtci_at_senescence", "psri_max",
                "psri_greenup_vs_senescence", "reip_peak", "reip_mean",
            ]:
                d[key] = None

        # ── SAR features (scalars + list summaries) ──
        if self.sar_temporal:
            s = self.sar_temporal
            d["vv_mean_db"] = s.vv_mean_db
            d["vv_std_db"] = s.vv_std_db
            d["vh_mean_db"] = s.vh_mean_db
            d["vh_std_db"] = s.vh_std_db
            d["vv_amplitude_db"] = s.vv_amplitude_db
            d["vh_amplitude_db"] = s.vh_amplitude_db
            d["vv_vh_ratio_mean"] = s.vv_vh_ratio_mean
            d["vv_vh_ratio_trend"] = s.vv_vh_ratio_trend
            d["rvi_peak"] = s.rvi_peak
            d["rvi_mean"] = s.rvi_mean
            d["sar_crop_cycle_amplitude"] = s.sar_crop_cycle_amplitude
            d["n_change_points"] = float(s.n_change_points) if s.n_change_points is not None else None
            d["first_change_point_doy"] = float(s.first_change_point_doy) if s.first_change_point_doy is not None else None
            d["last_change_point_doy"] = float(s.last_change_point_doy) if s.last_change_point_doy is not None else None

            # Rolling median summaries (fixed-length scalars, not raw lists)
            d["vv_rolling_median_mean"] = s.vv_rolling_median_mean
            d["vv_rolling_median_slope"] = s.vv_rolling_median_slope
            d["vh_rolling_median_mean"] = s.vh_rolling_median_mean
            d["vh_rolling_median_slope"] = s.vh_rolling_median_slope

            d["flood_signature_count"] = float(s.flood_signature_count) if s.flood_signature_count is not None else None
        else:
            for key in [
                "vv_mean_db", "vv_std_db", "vh_mean_db", "vh_std_db",
                "vv_amplitude_db", "vh_amplitude_db", "vv_vh_ratio_mean",
                "vv_vh_ratio_trend", "rvi_peak", "rvi_mean",
                "sar_crop_cycle_amplitude", "n_change_points",
                "first_change_point_doy", "last_change_point_doy",
                "vv_rolling_median_mean", "vv_rolling_median_slope",
                "vh_rolling_median_mean", "vh_rolling_median_slope",
                "flood_signature_count",
            ]:
                d[key] = None

        # ── Context features ──
        d["latitude"] = self.latitude
        d["longitude"] = self.longitude
        d["aridity_index"] = self.aridity_index
        d["plot_area_ha"] = self.plot_area_ha

        return d

    def feature_availability_by_level(self) -> Dict[str, float]:
        """Report feature completeness per hierarchy level.

        Returns {"L0": 0.95, "L1": 0.85, "L2": 0.60, "L3": 0.40}
        Tells v6.0C: "I have enough data for L0+L1 but not L3".
        """
        flat = self.to_flat_dict()
        result = {}
        for level, features in _LEVEL_FEATURES.items():
            available = sum(1 for f in features if flat.get(f) is not None)
            total = len(features)
            result[level] = round(available / max(total, 1), 3)
        return result

    def to_json(self) -> Dict[str, Any]:
        """Full JSON serialization with provenance and diagnostic lists."""
        result: Dict[str, Any] = {
            "plot_id": self.plot_id,
            "run_id": self.run_id,
            "extraction_timestamp": self.extraction_timestamp,
            "feature_vector_version": self.feature_vector_version,
            "data_sources": self.data_sources,
            "data_completeness": self.data_completeness,
            "extraction_warnings": self.extraction_warnings,
            "feature_availability_by_level": self.feature_availability_by_level(),
            "flat_features": self.to_flat_dict(),
            "context": {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "koppen_zone": self.koppen_zone,
                "aridity_index": self.aridity_index,
                "soil_texture_class": self.soil_texture_class,
                "irrigation_type": self.irrigation_type,
                "plot_area_ha": self.plot_area_ha,
            },
        }

        # Full diagnostic lists (NOT in to_flat_dict)
        if self.sar_temporal:
            result["sar_diagnostics"] = {
                "change_point_doys": self.sar_temporal._change_point_doys,
                "vv_rolling_median_30d": self.sar_temporal._vv_rolling_median_30d,
                "vh_rolling_median_30d": self.sar_temporal._vh_rolling_median_30d,
            }

        return result


# ============================================================================
# Main extraction orchestrator
# ============================================================================

def extract_crop_features(
    plot_timeseries: List[Dict],
    plot_id: str,
    run_id: str,
    *,
    dates: Optional[List[str]] = None,
    ndvi_series: Optional[List[float]] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    koppen_zone: Optional[str] = None,
    aridity_index: Optional[float] = None,
    soil_texture_class: Optional[str] = None,
    irrigation_type: Optional[str] = None,
    plot_area_ha: Optional[float] = None,
    irrigation_events: Optional[List[Dict]] = None,
) -> CropFeatureVector:
    """Extract full CropFeatureVector from plot timeseries data.

    Orchestrates phenology, red-edge, and SAR feature extraction.

    Args:
        plot_timeseries: List of per-timestep dicts from FieldTensor
        plot_id: Plot identifier
        run_id: Layer 1 run identifier
        dates: Optional date strings (extracted from timeseries if not provided)
        ndvi_series: Optional NDVI values (extracted from timeseries if not provided)
        latitude, longitude: Plot coordinates
        koppen_zone: Köppen climate zone code
        aridity_index: Aridity index value
        soil_texture_class: Soil texture class string
        irrigation_type: Irrigation type string
        plot_area_ha: Plot area in hectares
        irrigation_events: Optional irrigation event timestamps for SAR analysis

    Returns:
        CropFeatureVector with all extractable features.
    """
    warnings: List[str] = []
    sources: List[str] = []

    # ── Extract dates and NDVI from timeseries if not provided ──
    if dates is None or ndvi_series is None:
        extracted_dates = []
        extracted_ndvi = []
        for entry in plot_timeseries:
            if isinstance(entry, dict):
                d = entry.get("date", entry.get("timestamp", ""))
                n = entry.get("ndvi_mean", entry.get("ndvi"))
            else:
                d = getattr(entry, "date", "")
                n = getattr(entry, "ndvi_mean", None)
            extracted_dates.append(str(d)[:10] if d else "")
            if n is not None:
                extracted_ndvi.append(float(n))
        if dates is None:
            dates = extracted_dates
        if ndvi_series is None:
            ndvi_series = extracted_ndvi

    # ── Phenology features ──
    phenology = None
    if ndvi_series and len(ndvi_series) >= 5:
        try:
            phenology = extract_phenology_features(ndvi_series, dates)
            sources.append("sentinel2")
            warnings.extend(phenology.extraction_warnings)
        except Exception as e:
            logger.warning(f"Phenology extraction failed: {e}")
            warnings.append(f"phenology_extraction_error: {str(e)[:80]}")

    # ── Red-edge features ──
    red_edge = None
    ndvi_peak_idx = None
    senescence_idx = None
    if phenology and phenology.peak_ndvi is not None:
        # Find NDVI peak index
        if ndvi_series:
            peak_val = phenology.peak_ndvi
            for i, v in enumerate(ndvi_series):
                if abs(v - peak_val) < 0.01:
                    ndvi_peak_idx = i
                    break
        # Estimate senescence start (60% of way from peak to end)
        if ndvi_peak_idx is not None:
            remaining = len(ndvi_series) - ndvi_peak_idx
            senescence_idx = ndvi_peak_idx + int(remaining * 0.6)

    try:
        red_edge = extract_red_edge_features(
            plot_timeseries,
            ndvi_peak_idx=ndvi_peak_idx,
            senescence_start_idx=senescence_idx,
        )
        warnings.extend(red_edge.extraction_warnings)
    except Exception as e:
        logger.warning(f"Red-edge extraction failed: {e}")
        warnings.append(f"red_edge_extraction_error: {str(e)[:80]}")

    # ── SAR temporal features ──
    sar_temporal = None
    optical_count = len([v for v in ndvi_series if v is not None]) if ndvi_series else 0
    try:
        sar_temporal = extract_sar_temporal_features(
            plot_timeseries,
            optical_obs_count=optical_count,
            irrigation_events=irrigation_events,
        )
        if sar_temporal.n_observations > 0:
            sources.append("sentinel1")
        warnings.extend(sar_temporal.extraction_warnings)
    except Exception as e:
        logger.warning(f"SAR extraction failed: {e}")
        warnings.append(f"sar_extraction_error: {str(e)[:80]}")

    # Add weather source if we have dates
    if dates and len(dates) > 0:
        sources.append("open_meteo")

    # ── Build feature vector ──
    fv = CropFeatureVector(
        plot_id=plot_id,
        run_id=run_id,
        extraction_timestamp=datetime.now(timezone.utc).isoformat(),
        phenology=phenology,
        red_edge=red_edge,
        sar_temporal=sar_temporal,
        latitude=latitude,
        longitude=longitude,
        koppen_zone=koppen_zone,
        aridity_index=aridity_index,
        soil_texture_class=soil_texture_class,
        irrigation_type=irrigation_type,
        plot_area_ha=plot_area_ha,
        data_sources=sorted(set(sources)),
        extraction_warnings=warnings,
    )

    # ── Compute data completeness ──
    flat = fv.to_flat_dict()
    total_keys = len(flat)
    non_null = sum(1 for v in flat.values() if v is not None)
    fv.data_completeness = round(non_null / max(total_keys, 1), 3)

    return fv


def plot_observations_to_crop_feature_input(
    observations: List[Dict]
) -> Tuple[List[Dict], List[str]]:
    """Adapter to normalize raw PlotObservation docs into a clean timeseries list

    for extract_crop_features. Emits warnings for missing/low-quality data.
    """
    from typing import Tuple
    warnings = []
    if not observations:
        return [], ["insufficient_observations"]

    by_date: Dict[str, Dict] = {}
    duplicate_dates_merged = False
    low_quality_dropped = False

    has_ndvi = False
    has_sar = False

    for obs in observations:
        dt = obs.get("obsDate")
        if not dt:
            continue
        # Format date as YYYY-MM-DD
        dstr = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]

        # Check reliability / quality flags
        is_reliable = obs.get("isReliable", True)
        quality = obs.get("quality", 1.0)
        # Drop if explicitly marked unreliable or low quality
        if not is_reliable or (quality is not None and quality < 0.2):
            low_quality_dropped = True
            continue

        if dstr in by_date:
            duplicate_dates_merged = True
        else:
            by_date[dstr] = {
                "date": dstr,
                "ndvi": None,
                "ndre": None,
                "vv": None,
                "vh": None,
                "ndwi": None,
                "rain": None,
                "et0": None,
                "cloudCover": None,
            }

        # Normalize and merge values
        obs_type = obs.get("obsType", "")
        
        # Read values safely
        if obs_type == "ndvi":
            if obs.get("ndvi") is not None:
                by_date[dstr]["ndvi"] = float(obs["ndvi"])
                has_ndvi = True
            if obs.get("cloudCover") is not None:
                by_date[dstr]["cloudCover"] = float(obs["cloudCover"])
        elif obs_type == "sar_backscatter":
            if obs.get("vv") is not None:
                by_date[dstr]["vv"] = float(obs["vv"])
                has_sar = True
            if obs.get("vh") is not None:
                by_date[dstr]["vh"] = float(obs["vh"])
                has_sar = True
        elif obs_type in ("current_weather", "historical_weather"):
            if obs.get("tempC") is not None:
                by_date[dstr]["tempC"] = float(obs["tempC"])
            if obs.get("precipMm") is not None:
                by_date[dstr]["rain"] = float(obs["precipMm"])
            if obs.get("et0") is not None:
                by_date[dstr]["et0"] = float(obs["et0"])

        # Other fields (ndre, ndwi, evi etc.)
        for src_k, target_k in [("ndre", "ndre"), ("ndwi", "ndwi"), ("evi", "evi")]:
            if obs.get(src_k) is not None:
                by_date[dstr][target_k] = float(obs[src_k])

    # Convert to list sorted by date
    sorted_dates = sorted(by_date.keys())
    timeseries = [by_date[d] for d in sorted_dates]

    # Check completeness
    if len(timeseries) < 5:
        warnings.append("insufficient_observations")
    if not has_ndvi:
        warnings.append("missing_ndvi")
    if not has_sar:
        warnings.append("missing_sar")
    if duplicate_dates_merged:
        warnings.append("duplicate_dates_merged")
    if low_quality_dropped:
        warnings.append("low_quality_observations_dropped")

    return timeseries, warnings

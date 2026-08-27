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
import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.agribrain.layer2_veg_int.features.phenology_features import (
    PhenologyFeatures,
    extract_phenology_features,
)
from services.agribrain.layer2_veg_int.features.red_edge_features import (
    RedEdgeFeatures,
    extract_red_edge_features,
)
from services.agribrain.layer2_veg_int.features.sar_temporal_features import (
    SARTemporalFeatures,
    extract_sar_temporal_features,
)

logger = logging.getLogger("agribrain.v6.crop_feature_vector")


CROP_FEATURE_TRANSFORM_VERSION = "ledger-crop-feature-transform-v2-manifest"
NO_NORMALIZATION_ARTIFACT_HASH = hashlib.sha256(
    b"agribrain-crop-feature-normalization:none:v1"
).hexdigest()


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
        "sos_gdd", "pos_gdd", "eos_gdd", "growth_rate_per_gdd",
        "senescence_rate_per_gdd",
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
            d["sos_gdd"] = p.sos_gdd
            d["pos_gdd"] = p.pos_gdd
            d["eos_gdd"] = p.eos_gdd
            d["growth_rate_per_gdd"] = p.growth_rate_per_gdd
            d["senescence_rate_per_gdd"] = p.senescence_rate_per_gdd
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
                "sos_gdd", "pos_gdd", "eos_gdd", "growth_rate_per_gdd",
                "senescence_rate_per_gdd",
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
        if self.sar_temporal:
            result["sar_diagnostics"] = {
                "change_point_doys": self.sar_temporal._change_point_doys,
                "vv_rolling_median_30d": self.sar_temporal._vv_rolling_median_30d,
                "vh_rolling_median_30d": self.sar_temporal._vh_rolling_median_30d,
            }
        return result


def _feature_semantic(name: str) -> Dict[str, Any]:
    """Return hash-bound scientific semantics for one legacy RF feature.

    The previous compatibility hash covered column order only.  These fields
    deliberately bind scientific meaning so a per-observation slope cannot be
    silently replaced by a per-day slope under the same model schema.
    """
    source_bands: List[str] = []
    support = "ledger-selected admitted physical acquisitions"
    temporal = "calendar_day"
    normalization = "none"
    statistic = "derived"
    unit = "dimensionless"
    definition = name.replace("_", " ")

    if name.startswith("ndre"):
        source_bands = ["B05", "B8A"]
    elif name.startswith("cired"):
        source_bands = ["B05", "B8A"]
    elif name.startswith("mtci"):
        source_bands = ["B04", "B05", "B06"]
    elif name.startswith("psri"):
        source_bands = ["B02", "B04", "B06"]
    elif name.startswith("reip"):
        source_bands = ["B04", "B05", "B06", "B07"]
        unit = "nm"
    elif name.startswith(("vv_", "vh_", "sar_", "rvi", "flood_")):
        source_bands = ["VV", "VH"]
        support = (
            "ledger-selected admitted S1 acquisitions from one explicit "
            "orbit-direction/relative-orbit track"
        )
    elif name in {
        "peak_ndvi", "base_ndvi", "amplitude", "growth_rate",
        "senescence_rate", "small_integral", "large_integral", "cv_ndvi",
        "velocity_p10", "velocity_p25", "velocity_p50", "velocity_p75",
        "velocity_p90", "seasonal_pattern_shift",
    }:
        source_bands = ["B04", "B08"]

    if name.endswith("_gdd") or name.endswith("_per_gdd"):
        temporal = "cumulative_growing_degree_days"
        unit = "gdd" if name.endswith("_gdd") else "value_per_gdd"
        support = "ledger observation environmental context aligned to optical acquisition"

    if name.endswith("_doy") or name in {"sos_doy", "pos_doy", "eos_doy"}:
        unit = "day_of_year"
        temporal = "acquisition_datetime_utc"
    elif name.endswith("_days") or name == "los_days":
        unit = "day"
    elif name.endswith("_db") or "_db" in name:
        unit = "dB"
    elif name.endswith("_slope") or name.endswith("_trend") or name in {
        "growth_rate", "senescence_rate",
    }:
        unit = "value_per_calendar_day"
        statistic = "ordinary_least_squares_over_elapsed_days"
    elif name.endswith("_mean"):
        statistic = "arithmetic_mean"
    elif name.endswith("_peak") or name.startswith("peak_"):
        statistic = "maximum"
    elif name.endswith("_std") or "_std_" in name:
        statistic = "population_standard_deviation"
    elif name.endswith("_count") or name.startswith("n_"):
        statistic = "count"

    if name in {"latitude", "longitude"}:
        support = "authenticated plot context"
        temporal = "static_context"
        unit = "decimal_degree"
    elif name == "plot_area_ha":
        support = "authenticated canonical plot geometry"
        temporal = "static_context"
        unit = "hectare"
    elif name == "aridity_index":
        support = "versioned environmental context"
        temporal = "context_valid_time"

    return {
        "name": name,
        "scientific_definition": definition,
        "unit": unit,
        "source_bands": source_bands,
        "statistic": statistic,
        "support_definition": support,
        "temporal_coordinate": temporal,
        "normalization": normalization,
        "missing_value_semantics": (
            "null means unavailable; zero remains a measured or derived zero"
        ),
    }


def crop_feature_schema_receipt():
    """Build the complete semantic schema used by the engineered EO expert."""
    from services.agribrain.scientific_contracts.crop_model_input import (
        CropFeatureSchemaReceiptV1,
        CropFeatureSemanticV1,
    )

    names = tuple(CropFeatureVector().to_flat_dict().keys())
    features = tuple(
        CropFeatureSemanticV1(**_feature_semantic(name)) for name in names
    )
    return CropFeatureSchemaReceiptV1(
        schema_version="crop-feature-vector-6.0-ledger-semantics-v1",
        features=features,
        transform_version=CROP_FEATURE_TRANSFORM_VERSION,
    )


def _crop_transform_module_digests() -> Dict[str, str]:
    here = Path(__file__).resolve()
    paths = {
        "crop_feature_vector": here,
        "phenology_features": here.with_name("phenology_features.py"),
        "red_edge_features": here.with_name("red_edge_features.py"),
        "sar_temporal_features": here.with_name("sar_temporal_features.py"),
        "ledger_crop_features": here.with_name("ledger_crop_features.py"),
        "crop_ml": here.parent.parent / "crop_ml.py",
        "crop_model_input_contract": (
            here.parents[2] / "scientific_contracts" / "crop_model_input.py"
        ),
    }
    return {
        module_id: hashlib.sha256(path.read_bytes()).hexdigest()
        for module_id, path in sorted(paths.items())
    }


def _transform_recipe_group(feature_name: str) -> str:
    if feature_name in {"latitude", "longitude", "aridity_index", "plot_area_ha"}:
        return "context"
    if feature_name.startswith(("ndre_", "cired_", "mtci_", "psri_", "reip_")):
        return "red_edge"
    if (
        feature_name.startswith(("vv_", "vh_", "rvi_", "sar_", "flood_"))
        or feature_name in {
            "n_change_points", "first_change_point_doy", "last_change_point_doy",
        }
    ):
        return "sar"
    return "phenology"


def crop_feature_transform_manifest():
    """Return the exact, module-bound scientific transform manifest."""
    from services.agribrain.scientific_contracts.crop_model_input import (
        CropFeatureTransformManifest,
        CropFeatureTransformRecipe,
    )

    schema = crop_feature_schema_receipt()
    digests = _crop_transform_module_digests()
    recipes = []
    for semantic in schema.features:
        group = _transform_recipe_group(semantic.name)
        if group == "phenology":
            module_id = "phenology_features"
            algorithm_id = (
                "phenology_features.extract_phenology_features+"
                "crop_ml.smooth_ndvi+crop_ml.extract_phenology:v1"
            )
            parameters: Tuple[Tuple[str, Any], ...] = (
                ("savgol_window_observations", 7),
                ("savgol_polynomial_order", 3),
                ("upper_envelope_pass_count", 3),
                ("cloud_dip_correction_threshold_ndvi", 0.05),
                ("sos_eos_amplitude_fraction", 0.20),
                ("interpolation", "none"),
            )
            window = "sample_index_savgol_window_7_adapted_to_odd_series_length"
            thresholds: Tuple[Tuple[str, Any], ...] = (
                ("sos_eos_amplitude_fraction", 0.20),
                ("cloud_dip_correction_threshold_ndvi", 0.05),
            )
        elif group == "red_edge":
            module_id = "red_edge_features"
            algorithm_id = "red_edge_features.extract_red_edge_features:v1"
            parameters = (
                ("event_alignment", "calendar_date_key"),
                ("interpolation", "none"),
                ("resampling", "preserve_upstream_values"),
                ("senescence_event_fraction_after_peak", 0.60),
            )
            window = "all_admitted_current_cycle_red_edge_observations"
            thresholds = (
                ("ndre_ndvi_ratio_minimum_ndvi", 0.05),
                ("ndre_ndvi_ratio_minimum_pairs", 3),
            )
        elif group == "sar":
            module_id = "sar_temporal_features"
            algorithm_id = "sar_temporal_features.extract_sar_temporal_features:v1"
            parameters = (
                ("change_point_threshold_db", 2.5),
                ("rolling_median_window_days", 30),
                ("rolling_window_alignment", "centered_plus_minus_15_days_inclusive"),
                ("track_policy", "single_orbit_direction_relative_orbit_track"),
                ("interpolation", "none"),
            )
            window = "centered_30_calendar_day_window_inclusive"
            thresholds = (("change_point_threshold_db", 2.5),)
        else:
            module_id = "crop_feature_vector"
            algorithm_id = "crop_feature_vector.authenticated_context_passthrough:v1"
            parameters = (("interpolation", "none"),)
            window = "static_authenticated_plot_context"
            thresholds = ()
        recipes.append(CropFeatureTransformRecipe(
            feature_name=semantic.name,
            algorithm_id=algorithm_id,
            formula_id=f"agribrain.crop.{group}.{semantic.name}:v1",
            parameters=parameters,
            window_definition=window,
            thresholds=thresholds,
            input_bands=semantic.source_bands,
            mask_semantics=(
                "ledger_v2_selected_independence_representative & qa_admitted & "
                "feature_support_hash_bound & finite_feature_values"
            ),
            temporal_coordinate=semantic.temporal_coordinate,
            normalization=semantic.normalization,
            module_id=module_id,
            module_digest=digests[module_id],
        ))
    return CropFeatureTransformManifest(
        transform_version=CROP_FEATURE_TRANSFORM_VERSION,
        schema_hash=schema.content_hash,
        source_policy="crop_evidence_ledger_v2_selected_current_cycle_only",
        mask_policy=(
            "immutable observation support plus admitted QA and physical "
            "independence selection"
        ),
        time_policy="UTC sensing time; rates use elapsed calendar days",
        normalization_policy=(
            f"none;artifact={NO_NORMALIZATION_ARTIFACT_HASH}"
        ),
        smoothing_policy=(
            "three-pass upper-envelope Savitzky-Golay; sample window=7; "
            "polynomial order=3; cloud-dip threshold=0.05"
        ),
        interpolation_policy="none; missing acquisition dates are not filled",
        red_edge_policy=(
            "no feature-stage resampling; preserve ledger values; align "
            "phenology events by UTC calendar date"
        ),
        sos_threshold=0.20,
        sar_change_point_threshold_db=2.5,
        sar_rolling_window_days=30,
        feature_recipes=tuple(recipes),
        module_digests=tuple(digests.items()),
    )


def crop_feature_transform_hash() -> str:
    """Content identity of the exact scientific transform manifest."""
    return crop_feature_transform_manifest().content_hash


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
    data_sources: Optional[List[str]] = None,
    require_ledger_provenance: bool = False,
    gdd_series: Optional[List[float]] = None,
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
    sources: List[str] = sorted({
        str(source).strip() for source in (data_sources or [])
        if str(source).strip()
    })
    if require_ledger_provenance and not sources:
        raise ValueError("ledger-derived crop features require explicit source lineage")

    # ── Extract dates and NDVI from timeseries if not provided ──
    aligned_rows = []
    if dates is not None and ndvi_series is not None:
        candidates = [
            (
                raw_date,
                raw_ndvi,
                gdd_series[index] if gdd_series is not None and index < len(gdd_series) else None,
            )
            for index, (raw_date, raw_ndvi) in enumerate(zip(dates, ndvi_series))
        ]
    else:
        candidates = []
        for index, entry in enumerate(plot_timeseries):
            if isinstance(entry, dict):
                row_date = entry.get("date", entry.get("timestamp", ""))
                row_ndvi = entry.get("ndvi_mean")
                if row_ndvi is None:
                    row_ndvi = entry.get("ndvi")
            else:
                row_date = getattr(entry, "date", "")
                row_ndvi = getattr(entry, "ndvi_mean", None)
            candidate_date = (
                dates[index] if dates is not None and index < len(dates)
                else row_date
            )
            candidate_ndvi = (
                ndvi_series[index]
                if ndvi_series is not None and index < len(ndvi_series)
                else row_ndvi
            )
            row_gdd = (
                gdd_series[index] if gdd_series is not None and index < len(gdd_series)
                else entry.get("gdd_accumulated") if isinstance(entry, dict)
                else getattr(entry, "gdd_accumulated", None)
            )
            candidates.append((candidate_date, candidate_ndvi, row_gdd))
    for raw_date, raw_ndvi, raw_gdd in candidates:
        if raw_date in (None, "") or raw_ndvi is None:
            continue
        try:
            parsed_ndvi = float(raw_ndvi)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(parsed_ndvi):
            continue
        parsed_gdd = None
        if raw_gdd is not None:
            try:
                parsed_gdd = float(raw_gdd)
                if not math.isfinite(parsed_gdd):
                    parsed_gdd = None
            except (TypeError, ValueError):
                parsed_gdd = None
        aligned_rows.append((str(raw_date)[:10], parsed_ndvi, parsed_gdd))
    aligned_rows.sort(key=lambda row: row[0])
    dates = [row[0] for row in aligned_rows]
    ndvi_series = [row[1] for row in aligned_rows]
    aligned_gdd = [row[2] for row in aligned_rows]
    gdd_series = (
        [float(value) for value in aligned_gdd if value is not None]
        if aligned_gdd and all(value is not None for value in aligned_gdd)
        else None
    )

    # ── Phenology features ──
    phenology = None
    if ndvi_series and len(ndvi_series) >= 5:
        try:
            phenology = extract_phenology_features(
                ndvi_series, dates, gdd_series=gdd_series,
            )
            warnings.extend(phenology.extraction_warnings)
        except Exception as e:
            logger.warning(f"Phenology extraction failed: {e}")
            warnings.append(f"phenology_extraction_error: {str(e)[:80]}")

    # ── Red-edge features ──
    red_edge = None
    ndvi_peak_idx = None
    senescence_idx = None
    if phenology and phenology.peak_ndvi is not None:
        # Find the peak on the aligned NDVI/time axis.
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

    # The red-edge extractor operates on the original observation rows.  Map
    # the aligned NDVI event back by date rather than reusing its positional
    # index across a differently sparse series.
    red_edge_rows = sorted(
        list(plot_timeseries),
        key=lambda row: str(
            row.get("date", row.get("timestamp", ""))
            if isinstance(row, dict) else getattr(row, "date", "")
        ),
    )
    aligned_peak_date = (
        dates[ndvi_peak_idx]
        if ndvi_peak_idx is not None and ndvi_peak_idx < len(dates) else None
    )
    aligned_senescence_date = (
        dates[senescence_idx]
        if senescence_idx is not None and senescence_idx < len(dates) else None
    )
    if aligned_peak_date:
        ndvi_peak_idx = next((
            index for index, row in enumerate(red_edge_rows)
            if str(
                row.get("date", row.get("timestamp", ""))
                if isinstance(row, dict) else getattr(row, "date", "")
            )[:10] == aligned_peak_date
        ), None)
    if aligned_senescence_date:
        senescence_idx = next((
            index for index, row in enumerate(red_edge_rows)
            if str(
                row.get("date", row.get("timestamp", ""))
                if isinstance(row, dict) else getattr(row, "date", "")
            )[:10] == aligned_senescence_date
        ), None)
    try:
        red_edge = extract_red_edge_features(
            red_edge_rows,
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
        warnings.extend(sar_temporal.extraction_warnings)
    except Exception as e:
        logger.warning(f"SAR extraction failed: {e}")
        warnings.append(f"sar_extraction_error: {str(e)[:80]}")

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

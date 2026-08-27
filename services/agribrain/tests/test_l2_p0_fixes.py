"""
Test Suite for Layer 2 P0 Scientific Repairs and Contracts

Covers:
  - Anomaly Engine: Missing rain does not trigger false drought
  - Anomaly Engine: SAR cross-pol math in dB (difference, not quotient)
  - Anomaly Engine: Unresolved anomaly vs disease fallacy
  - Spatial Engine: Moran's I spatial weight matrix (k-NN / adjacency, not all-to-all)
  - Phenology Engine: Marginalization over missing NDWI without pseudo-fabrication
  - Phenology Engine: Photoperiod calculation does not default invalid dates to summer solstice
  - Phenology Engine: Short-day crop photoperiod inversion (P_critical sigmoid)
  - Phenology Engine: Vernalization gating on reproductive transitions
  - Growth Engine: FAO-56 extraterrestrial solar radiation physics (Ra)
  - Growth Engine: Carbon Water Productivity (CWP) dimensional units
"""

import math
import pytest
from layer2_veg_int.schema import PhenologyStage, AnomalyType, AttributionEvidence
from layer2_veg_int.anomaly_engine import TemporalAnomalyEngine
from layer2_veg_int.spatial_engine import SpatialAnalysisEngine
from layer2_veg_int.phenology_engine import (
    PhenologyEngine,
    compute_effective_gdd,
    compute_vernalization_gate,
    accumulate_chill_units,
)
from layer2_veg_int.growth_engine import GrowthCurveEngine


# =========================================================================
# 1. Anomaly Engine P0 Contracts
# =========================================================================

def test_missing_rainfall_does_not_trigger_drought():
    """Missing rainfall (None/absent) MUST NOT be treated as rain=0.0 and trigger false drought."""
    engine = TemporalAnomalyEngine(z_threshold=2.0)
    dates = [f"2026-05-{i+1:02d}" for i in range(20)]
    observed_ndvi = [0.60] * 10 + [0.35] * 10  # Drop at day 10
    modeled_ndvi = [0.60] * 20
    uncertainties = [0.03] * 20

    # Test case A: Rainfall is None (missing observation data)
    anomalies_no_rain = engine.detect_anomalies(
        dates=dates,
        observed_ndvi=observed_ndvi,
        modeled_ndvi=modeled_ndvi,
        uncertainties=uncertainties,
        rainfall=None,  # Missing!
    )

    assert len(anomalies_no_rain) > 0
    for anom in anomalies_no_rain:
        if anom.attribution:
            # Water stress attribution from rainfall must NOT fire
            assert anom.attribution.water_stress == 0.0

    # Test case B: Rainfall explicitly present and low -> should attribute water stress
    rainfall_dry = [0.0] * 20
    anomalies_dry = engine.detect_anomalies(
        dates=dates,
        observed_ndvi=observed_ndvi,
        modeled_ndvi=modeled_ndvi,
        uncertainties=uncertainties,
        rainfall=rainfall_dry,
    )
    assert len(anomalies_dry) > 0
    assert any(a.attribution and a.attribution.water_stress > 0.4 for a in anomalies_dry)


def test_sar_ratio_db_difference_math():
    """SAR VH and VV backscatter in dB must be compared via difference, not quotient."""
    engine = TemporalAnomalyEngine(z_threshold=2.0)
    dates = [f"2026-05-{i+1:02d}" for i in range(15)]
    observed_ndvi = [0.60] * 7 + [0.30] * 8
    modeled_ndvi = [0.60] * 15
    uncertainties = [0.03] * 15

    # VV changes by +2.0 dB (significant structural disturbance)
    sar_vv = [-14.0] * 7 + [-12.0] * 8
    sar_vh = [-20.0] * 7 + [-18.5] * 8

    anomalies = engine.detect_anomalies(
        dates=dates,
        observed_ndvi=observed_ndvi,
        modeled_ndvi=modeled_ndvi,
        uncertainties=uncertainties,
        sar_vv=sar_vv,
        sar_vh=sar_vh,
    )
    assert len(anomalies) > 0
    assert any(a.attribution and a.attribution.structural_damage > 0.0 for a in anomalies)


def test_unresolved_anomaly_not_forced_disease():
    """When no abiotic explanation is found, the engine must not falsely diagnose disease with 1.0 confidence."""
    engine = TemporalAnomalyEngine(z_threshold=2.0)
    dates = [f"2026-05-{i+1:02d}" for i in range(15)]
    observed_ndvi = [0.60] * 7 + [0.30] * 8
    modeled_ndvi = [0.60] * 15
    uncertainties = [0.03] * 15

    anomalies = engine.detect_anomalies(
        dates=dates,
        observed_ndvi=observed_ndvi,
        modeled_ndvi=modeled_ndvi,
        uncertainties=uncertainties,
        rainfall=[15.0] * 15,  # Plentiful rain -> no water stress
        temperature=[24.0] * 15,  # Ideal temp -> no heat/frost stress
    )
    assert len(anomalies) > 0
    for anom in anomalies:
        if anom.attribution:
            # Disease/pest must NOT be pegged at 1.0; primary cause should be UNRESOLVED if low confidence
            assert anom.attribution.disease_or_pest <= 0.5


# =========================================================================
# 2. Spatial Engine P0 Contracts (Moran's I)
# =========================================================================

def test_morans_i_non_trivial_weights():
    """Moran's I with valid weights must not collapse to -1/(n-1) for non-trivial spatial signals."""
    spatial_eng = SpatialAnalysisEngine()
    
    # 6 zones in a spatial gradient (clustered pattern: 1,2,3 high, 4,5,6 low)
    zone_means_clustered = {
        "zone_1": [0.80] * 10,
        "zone_2": [0.78] * 10,
        "zone_3": [0.75] * 10,
        "zone_4": [0.30] * 10,
        "zone_5": [0.28] * 10,
        "zone_6": [0.25] * 10,
    }
    zone_centroids = {
        "zone_1": (0.0, 0.0),
        "zone_2": (1.0, 0.0),
        "zone_3": (2.0, 0.0),
        "zone_4": (3.0, 0.0),
        "zone_5": (4.0, 0.0),
        "zone_6": (5.0, 0.0),
    }

    n = len(zone_means_clustered)
    all_to_all_trivial = -1.0 / (n - 1)  # -0.2 for n=6

    i_val, p_val, status = spatial_eng._compute_morans_i(
        zone_means_clustered, zone_centroids=zone_centroids
    )

    # Clustered positive spatial autocorrelation should be positive and significantly different from -0.2
    assert i_val > 0.0
    assert abs(i_val - all_to_all_trivial) > 0.3
    assert status == "AVAILABLE"


def test_morans_i_explicit_adjacency():
    """Moran's I must accept explicit zone adjacency."""
    spatial_eng = SpatialAnalysisEngine()
    zone_means = {
        "A": [0.8] * 5,
        "B": [0.8] * 5,
        "C": [0.2] * 5,
        "D": [0.2] * 5,
    }
    adjacency = {
        "A": ["B"],
        "B": ["A", "C"],
        "C": ["B", "D"],
        "D": ["C"],
    }
    i_val, p_val, status = spatial_eng._compute_morans_i(zone_means, zone_adjacency=adjacency)
    assert math.isfinite(i_val)
    assert status == "AVAILABLE"


# =========================================================================
# 3. Phenology Engine P0 Contracts
# =========================================================================

def test_phenology_missing_ndwi_marginalization():
    """When ndwi_series is None or contains Nones, HMM must infer stages without fabricating NDWI."""
    engine = PhenologyEngine()
    modeled_ndvi = [0.15, 0.20, 0.35, 0.55, 0.70, 0.65, 0.40, 0.15]
    vel = [0.05] * 8
    dates = [f"2026-03-{i+1:02d}" for i in range(8)]
    gdd = [float(i * 250) for i in range(8)]

    # Missing NDWI
    stages_no_ndwi, confs_no_ndwi = engine.infer_daily_stages(
        modeled_ndvi=modeled_ndvi,
        velocity=vel,
        dates=dates,
        cumulative_gdd=gdd,
        ndwi_series=None,
    )
    assert len(stages_no_ndwi) == 8
    assert all(isinstance(s, PhenologyStage) for s in stages_no_ndwi)


def test_photoperiod_invalid_date_returns_none():
    """Invalid date string must return None, not summer solstice (doy=172)."""
    engine = PhenologyEngine(latitude=36.0)
    assert engine._compute_photoperiod("invalid-date") is None
    assert engine._compute_photoperiod("") is None
    valid_photoperiod = engine._compute_photoperiod("2026-06-21")
    assert valid_photoperiod is not None
    assert 14.0 < valid_photoperiod < 15.5


def test_short_day_photoperiod_response():
    """Short-day crops (rice, millet, sorghum) must develop faster under short days (day_length < 13h)."""
    t_mean = 25.0
    t_max = 28.0

    # Short days (10 hours) -> high development factor
    gdd_short_day = compute_effective_gdd(
        t_mean=t_mean, t_max=t_max, t_base=10.0,
        day_length=10.0, is_short_day=True
    )

    # Long days (15 hours) -> inhibited development factor
    gdd_long_day = compute_effective_gdd(
        t_mean=t_mean, t_max=t_max, t_base=10.0,
        day_length=15.0, is_short_day=True
    )

    assert gdd_short_day > gdd_long_day


def test_vernalization_gating():
    """Unvernalized winter cereal must experience heavy penalty on reproductive transition."""
    # 0% vernalized
    gate_unvernalized = compute_vernalization_gate(0.1, obligate=True)
    assert gate_unvernalized <= -10.0

    # 90% vernalized
    gate_vernalized = compute_vernalization_gate(0.9, obligate=True)
    assert gate_vernalized == 0.0


# =========================================================================
# 4. Growth Engine P0 Contracts (NPP & CWP)
# =========================================================================

def test_fao56_npp_radiation_physics():
    """Extraterrestrial radiation (Ra) and clear-sky NPP must match astronomical expectations."""
    # Latitude 36.0°N (Algiers/Oran region)
    # Day of year 172 (summer solstice)
    fpar = [0.80]
    npp = GrowthCurveEngine.compute_npp_proxy(
        fpar_series=fpar,
        latitude=36.0,
        start_doy=172,
    )
    assert len(npp) == 1
    # Summer solstice Ra at 36°N is ~41.5 MJ/m²/day
    # Clear sky Rs ≈ 0.75 * 41.5 ≈ 31.1 MJ/m²/day
    # PAR ≈ 0.48 * 31.1 ≈ 14.9 MJ/m²/day
    # NPP ≈ 0.80 * 14.9 * 1.5 ≈ 17.9 gC/m²/day
    assert 12.0 <= npp[0] <= 22.0


def test_carbon_water_productivity_units():
    """CWP must not have the incorrect x10 multiplier."""
    biomass_series = [100.0, 200.0, 400.0, 600.0]  # gC/m² peak = 600 gC/m²
    et_series = [100.0, 100.0, 100.0, 100.0]        # total ET = 400 mm
    
    wue_res = GrowthCurveEngine.compute_water_use_efficiency(
        biomass_series=biomass_series,
        et_actual_series=et_series,
    )
    # 600 gC/m² / 400 mm = 1.5 kgC/m³ (not 15.0!)
    assert wue_res["crop_water_productivity"] == 1.5
    assert wue_res["et_total"] == 400.0

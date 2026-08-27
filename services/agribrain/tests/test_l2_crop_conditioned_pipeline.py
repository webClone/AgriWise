"""
Comprehensive Test Suite for Layer 2 Crop-Conditioned Dynamic Engine (v4.0.0)

Tests:
1. Hierarchical parameter resolution with provenance tracking.
2. Crop stage graphs and canonical stage mapping (annuals, multi-cut, perennials).
3. Causal biological progress coordinate τ_t ∈ [0, 1] without future leakage.
4. Daily causal vernalization transition gating (V_t gates VEG → REP).
5. Optical water proxy missingness preservation (SCWA/CWSI = None, no false adequacy).
6. Competing hypothesis attribution (absence of abiotic explanation = UNRESOLVED).
7. Normalized crop watchdog consistency (likelihood ratio LR_c).
8. End-to-end runner execution with full crop conditioning and provenance.
"""

import math
import pytest
from types import SimpleNamespace
from typing import List, Dict, Any

from layer2_veg_int.crop_response_profile import (
    ParameterSource,
    AuthorityLevel,
    AdaptabilityClass,
    ParameterEstimate,
    CropStageGraph,
    CropResponseProfile,
    CropParameterResolver,
    CausalBiologicalProgress,
    CropContextConsistency,
)
from layer2_veg_int.schema import PhenologyStage
from layer2_veg_int.growth_engine import GrowthCurveEngine
from layer2_veg_int.phenology_engine import PhenologyEngine
from layer2_veg_int.anomaly_engine import TemporalAnomalyEngine
from layer2_veg_int.spatial_engine import SpatialAnalysisEngine
from layer2_veg_int.runner import VegetationIntelligenceEngine
from layer1_fusion.schema import FieldTensor


def test_degraded_tensor_returns_typed_output_without_datetime_shadowing():
    runner = VegetationIntelligenceEngine()
    tensor = FieldTensor(
        run_id="degraded-reintegration-a",
        plot_id="plot-a",
        plot_timeseries=[{
            "date": "2026-08-25",
            "ndvi_mean": None,
            "is_observed": False,
        }],
    )

    class ReplayInputs:
        crop_config = {
            "crop_posterior_hash": "crop-hash-a",
            "crop_lineage_id": "crop-lineage-a",
        }

    output = runner.analyze_tensor(tensor, orch_inputs=ReplayInputs())

    assert output.provenance["status"] == "degraded"
    assert output.provenance["reason"] == "no_observed_ndvi"
    assert output.provenance["execution_time"].endswith("+00:00")
    assert output.provenance["crop_posterior_lineage"] == "crop-hash-a"
    assert output.provenance["crop_lineage_id"] == "crop-lineage-a"


def test_composite_output_preserves_temporal_crop_lineage():
    from layer2_intelligence.schemas import (
        Layer2CompositeOutput,
        Layer2Output,
        Layer2Provenance,
    )

    canonical = Layer2Output(
        plot_id="plot-a",
        provenance=Layer2Provenance(run_id="layer2-a"),
    )
    temporal = SimpleNamespace(
        run_id="veg-degraded",
        provenance={
            "crop_posterior_lineage": "crop-hash-a",
            "crop_lineage_id": "crop-lineage-a",
            "phenology_posterior_hash": "phenology-hash-a",
        },
    )

    output = Layer2CompositeOutput.from_parts(canonical, temporal)

    assert output.provenance.crop_posterior_lineage == "crop-hash-a"
    assert output.provenance.crop_lineage_id == "crop-lineage-a"
    assert output.provenance.phenology_posterior_hash == "phenology-hash-a"


# =============================================================================
# 1. Hierarchical Parameter Resolution & Provenance
# =============================================================================

def test_hierarchical_parameter_resolution_cultivar_to_architecture():
    """Verify partial pooling: cultivar -> species -> architecture -> plant physics."""
    # Specific wheat cultivar
    profile_cultivar = CropParameterResolver.resolve("winter_wheat", cultivar="Apache")
    assert profile_cultivar.crop_code == "wheat"
    assert profile_cultivar.cultivar == "Apache"
    assert profile_cultivar.requires_vernalization is True
    assert profile_cultivar.photosynthetic_pathway == "C3"
    assert profile_cultivar.t_base.mean == 0.0
    assert profile_cultivar.t_opt_pheno.mean > 15.0

    # Species without cultivar
    profile_species = CropParameterResolver.resolve("maize")
    assert profile_species.crop_code == "maize"
    assert profile_species.photosynthetic_pathway == "C4"
    assert profile_species.requires_vernalization is False
    assert profile_species.t_base.mean == 10.0
    assert profile_species.lue_max.mean > profile_cultivar.lue_max.mean  # C4 LUE > C3 LUE

    # Unknown species falling back to architecture
    profile_arch = CropParameterResolver.resolve("teff")
    assert profile_arch.architecture == "cereal"
    assert profile_arch.t_base.mean == 10.0  # Teff in crop database
    assert profile_arch.authority == AuthorityLevel.TRANSFERRED

    # Unknown crop entirely falling back to generic annual
    profile_generic = CropParameterResolver.resolve("unknown_mysterious_crop")
    assert profile_generic.crop_code == "unknown_mysterious_crop"
    assert profile_generic.fallback_count > 0


# =============================================================================
# 2. Crop Stage Graphs & Biological Topology
# =============================================================================

def test_crop_stage_graphs_and_canonical_mapping():
    """Verify biological sub-stages map upward to canonical PhenologyStage."""
    wheat_graph = CropStageGraph.create_for_crop("wheat", "cereal")
    assert len(wheat_graph.nodes) >= 6
    assert wheat_graph.map_to_canonical("TILLERING") == PhenologyStage.VEGETATIVE
    assert wheat_graph.map_to_canonical("STEM_ELONGATION") == PhenologyStage.VEGETATIVE
    assert wheat_graph.map_to_canonical("ANTHESIS") == PhenologyStage.REPRODUCTIVE
    assert wheat_graph.map_to_canonical("GRAIN_FILLING") == PhenologyStage.REPRODUCTIVE

    alfalfa_graph = CropStageGraph.create_for_crop("alfalfa", "forage")
    assert len(alfalfa_graph.nodes) >= 4
    assert alfalfa_graph.map_to_canonical("EARLY_REGROWTH") == PhenologyStage.EMERGENCE
    assert alfalfa_graph.map_to_canonical("RAPID_VEGETATIVE") == PhenologyStage.VEGETATIVE

    olive_graph = CropStageGraph.create_for_crop("olive", "perennial")
    assert len(olive_graph.nodes) >= 4
    assert olive_graph.map_to_canonical("DORMANCY_QUIESCENCE") == PhenologyStage.DORMANCY
    assert olive_graph.map_to_canonical("FRUIT_SET") == PhenologyStage.REPRODUCTIVE


# =============================================================================
# 3. Causal Biological Progress Coordinate τ_t
# =============================================================================

def test_causal_biological_progress_monotonic_and_non_leaking():
    """Verify τ_t ∈ [0, 1] increases causally and is unpolluted by future days."""
    profile = CropParameterResolver.resolve("spring_wheat")
    dates = [f"2026-03-{d:02d}" for d in range(1, 31)]
    temps_warm = [15.0] * 30
    temps_cold_later = [15.0] * 15 + [5.0] * 15

    tau_warm = CausalBiologicalProgress.compute_daily_progress(temps_warm, dates, profile)
    tau_cold = CausalBiologicalProgress.compute_daily_progress(temps_cold_later, dates, profile)

    # Monotonicity
    for t in range(1, len(tau_warm)):
        assert tau_warm[t] >= tau_warm[t - 1]
        assert 0.0 <= tau_warm[t] <= 1.0

    # Non-leakage: Days 0..14 must be identical between warm and cold_later
    for t in range(15):
        assert math.isclose(tau_warm[t], tau_cold[t], abs_tol=1e-5)

    # Day 29 must reflect less progress in the colder sequence
    assert tau_warm[-1] > tau_cold[-1]


# =============================================================================
# 4. Causal Daily Vernalization Gating
# =============================================================================

def test_causal_vernalization_transition_gating():
    """Verify daily V_t gates VEGETATIVE → REPRODUCTIVE transition in HMM."""
    engine = PhenologyEngine(crop_config={"gdd_base_temp": 0.0}, is_perennial=False)
    n = 50
    dates = [f"2026-04-{d:02d}" if d <= 30 else f"2026-05-{d-30:02d}" for d in range(1, n + 1)]
    ndvi = [0.15] * 10 + [0.45] * 18 + [0.78] * 22
    vel = [0.0] * 10 + [0.03] * 18 + [0.01] * 22
    gdd = [i * 35.0 for i in range(n)]

    # Fully vernalized series
    v_series_complete = [1.0] * n
    stages_comp, _ = engine.infer_daily_stages(
        ndvi, vel, dates, gdd, vernalization_series=v_series_complete
    )
    # Should reach reproductive stage with adequate GDD, NDVI, and vernalization
    assert any(s == PhenologyStage.REPRODUCTIVE for s in stages_comp)

    # Unvernalized series (V_t = 0.0)
    v_series_blocked = [0.0] * n
    stages_blocked, _ = engine.infer_daily_stages(
        ndvi, vel, dates, gdd, vernalization_series=v_series_blocked
    )
    # Transition to reproductive must be blocked
    for s in stages_blocked:
        assert s != PhenologyStage.REPRODUCTIVE


# =============================================================================
# 5. Optical Water Proxy Missingness (SCWA/CWSI)
# =============================================================================

def test_optical_water_proxy_preserves_none_and_prevents_false_adequacy():
    """Missing NDWI must yield None, not 0.0 (which falsely signals 100% water)."""
    ndvi = [0.60, 0.65, 0.70]
    ndwi_missing = [None, None, None]
    ndwi_present = [0.30, 0.10, -0.10]

    # Missing
    scwa_missing = GrowthCurveEngine.compute_spectral_canopy_water_anomaly(ndwi_missing, ndvi)
    assert len(scwa_missing) == 3
    assert all(val is None for val in scwa_missing)

    # Present
    scwa_present = GrowthCurveEngine.compute_spectral_canopy_water_anomaly(ndwi_present, ndvi)
    assert scwa_present[0] is not None
    assert scwa_present[0] < scwa_present[2]  # Higher NDWI -> lower water stress anomaly

    # CASA NPP with missing water proxy produces potential NPP* without crashing
    fpar = [0.70, 0.75, 0.80]
    npp = GrowthCurveEngine.compute_npp_casa(
        fpar_series=fpar,
        latitude=45.0,
        start_doy=120,
        temperature_series=[22.0, 23.0, 24.0],
        cwsi_series=scwa_missing,
        t_opt=22.0,
    )
    assert len(npp) == 3
    assert all(val > 0.0 for val in npp)


# =============================================================================
# 6. Competing Hypotheses & UNRESOLVED Anomaly Attribution
# =============================================================================

def test_unexplained_drop_defaults_to_unresolved_not_disease():
    """When abiotic stressors are absent, residual drops are UNRESOLVED, never fabricated disease."""
    engine = TemporalAnomalyEngine()
    dates = [f"2026-05-{d:02d}" for d in range(1, 21)]
    # Sudden drop in observed NDVI without drought, heat, frost, or SAR disruption
    modeled = [0.75] * 20
    observed = [0.75] * 10 + [0.40] * 10
    unc = [0.02] * 20
    rain = [2.0] * 20  # Normal rain (no drought and no excess moisture)
    temp = [22.0] * 20  # Mild temp (no heat or frost)
    sar_vv = [-10.0] * 20  # Stable structure
    sar_vh = [-16.0] * 20

    anomalies = engine.detect_anomalies(
        dates=dates,
        observed_ndvi=observed,
        modeled_ndvi=modeled,
        uncertainties=unc,
        rainfall=rain,
        temperature=temp,
        sar_vv=sar_vv,
        sar_vh=sar_vh,
    )

    assert len(anomalies) > 0
    anom = anomalies[0]
    assert anom.attribution.primary_cause == "UNRESOLVED"
    assert anom.attribution.disease_or_pest == 0.0


# =============================================================================
# 7. Normalized Crop Watchdog Consistency (Likelihood Ratio LR_c)
# =============================================================================

def test_normalized_crop_watchdog_likelihood_ratio():
    """Watchdog checks if observations match expected trajectory envelope."""
    profile_maize = CropParameterResolver.resolve("maize")
    tau_series = [i / 20.0 for i in range(21)]

    # Matching maize trajectory (starts low, peaks near tau=0.6, senesces)
    ndvi_maize_like = [0.15 + 0.70 * math.sin(math.pi * tau) for tau in tau_series]
    report_good = CropContextConsistency.evaluate_consistency(
        observed_ndvi=ndvi_maize_like,
        tau_series=tau_series,
        profile=profile_maize,
    )
    assert report_good["consistency"] in ("HIGH", "MODERATE")
    assert report_good["action"] == "PROCEED"

    # Conflicting perennial-like flat high NDVI on annual maize profile
    ndvi_perennial_like = [0.85] * 21
    report_bad = CropContextConsistency.evaluate_consistency(
        observed_ndvi=ndvi_perennial_like,
        tau_series=tau_series,
        profile=profile_maize,
    )
    assert report_bad["consistency"] in ("LOW", "CONFLICT")
    assert report_bad["action"] == "CONFIRM_CROP_OR_CYCLE"


# =============================================================================
# 8. End-to-End Pipeline Execution & Provenance
# =============================================================================

def test_runner_end_to_end_crop_conditioning():
    """Verify complete Layer 2 execution attaches full crop conditioning metadata."""
    runner = VegetationIntelligenceEngine()

    n = 25
    dates = [f"2026-04-{d:02d}" for d in range(1, n + 1)]
    timeseries = []
    for idx, d in enumerate(dates):
        val = 0.18 + 0.22 * (idx / n)
        timeseries.append({
            "date": d,
            "ndvi_mean": val,
            "ndvi_interpolated": val,
            "uncertainty": 0.03,
            "is_observed": True,
            "tmean": 10.0 + (idx * 0.4),
            "temp_max": 16.0 + (idx * 0.4),
            "temp_min": 3.0,
            "rain": 5.0,
            "et0": 3.5,
            "evi": val * 0.85,
            "ndwi": 0.20,
            "ndmi": 0.15,
            "vv": -11.0,
            "vh": -17.0,
        })

    tensor = FieldTensor(
        run_id="test_crop_pipeline_001",
        plot_id="plot_test_1",
        plot_timeseries=timeseries,
    )

    class DummyOrchestratorInputs:
        crop_config = {"crop": "wheat", "cultivar": "Apache"}
        operational_context = {"lat": 44.5}
        cultivar = "Apache"

    output = runner.analyze_tensor(tensor, orch_inputs=DummyOrchestratorInputs())

    assert output.run_id.startswith("vegint_")
    assert len(output.curve.ndvi_fit) == n
    assert len(output.curve.lai_series) == n
    assert len(output.curve.fpar_series) == n
    assert len(output.curve.fvc_series) == n
    assert len(output.curve.npp_series) == n
    assert len(output.phenology.stage_by_day) == n

    # Check provenance
    prov = output.provenance
    assert "crop_response_profile" in prov
    assert prov["crop_response_profile"]["crop_name"] == "wheat"
    assert prov["crop_response_profile"]["cultivar"] == "Apache"
    assert "crop_context_consistency" in prov
    assert prov["crop_context_consistency"]["action"] == "PROCEED"


# =============================================================================
# 9. Scientific Invariant Tests
# =============================================================================

def test_non_vernalizing_crop_invariance():
    """Invariant: requires_vernalization=False => P_transition is identical whether V_t=0 or V_t=1."""
    engine = PhenologyEngine(
        crop_config={"gdd_base_temp": 10.0},
        requires_vernalization=False,
    )
    n = 30
    dates = [f"2026-06-{d:02d}" for d in range(1, n + 1)]
    ndvi = [0.20 + 0.02 * i for i in range(n)]
    vel = [0.02] * n
    gdd = [i * 40.0 for i in range(n)]

    stages_v0, confs_v0 = engine.infer_daily_stages(
        ndvi, vel, dates, gdd, vernalization_series=[0.0] * n, vernalization_progress=0.0
    )
    stages_v1, confs_v1 = engine.infer_daily_stages(
        ndvi, vel, dates, gdd, vernalization_series=[1.0] * n, vernalization_progress=1.0
    )

    assert stages_v0 == stages_v1
    assert confs_v0 == confs_v1


def test_unknown_vegetation_abstention():
    """Invariant: Unknown crop resolves to genuine UNKNOWN_VEGETATION with broad uninformative priors."""
    profile = CropParameterResolver.resolve("non_existent_species_xyz")
    assert profile.family == "UNKNOWN"
    assert profile.architecture == "UNKNOWN"
    assert profile.photosynthetic_pathway == "UNKNOWN"
    assert profile.requires_vernalization is False
    assert profile.t_base.variance > 10.0
    assert profile.authority == AuthorityLevel.PRIOR_ONLY
    assert "UNKNOWN_VEGETATION_UNINFORMATIVE_PRIOR" in profile.fallback_levels


def test_missing_scwa_neutrality_and_coverage():
    """Invariant: Missing NDWI reduces component coverage and records UNKNOWN without crashing."""
    runner = VegetationIntelligenceEngine()
    n = 20
    dates = [f"2026-05-{d:02d}" for d in range(1, n + 1)]
    timeseries = [{
        "date": d,
        "ndvi_mean": 0.50,
        "ndvi_interpolated": 0.50,
        "uncertainty": 0.03,
        "is_observed": True,
        "tmean": 20.0,
        "temp_max": 25.0,
        "temp_min": 15.0,
        "rain": 0.0,
        "et0": None,  # No water balance or optical water evidence
        "ndwi": None,  # Missing optical water proxy
        "ndmi": None,
    } for d in dates]

    tensor = FieldTensor(
        run_id="test_missing_water_001",
        plot_id="plot_test_2",
        plot_timeseries=timeseries,
    )

    class DummyOrchestratorInputs:
        crop_config = {"crop": "maize"}
        operational_context = {"lat": 35.0}

    output = runner.analyze_tensor(tensor, orch_inputs=DummyOrchestratorInputs())

    hi = output.health_index
    assert hi.water_stress_index is None
    assert hi.health_component_coverage == 0.75  # 3 of 4 components active (0.25 * 3)
    assert hi.component_state_mask["water_state"] == "UNKNOWN"
    assert hi.component_state_mask["ndvi_state"] == "OBSERVED"


def test_morans_i_geometry_requirements_and_permutation_invariance():
    """Invariant: Moran's I requires geometry and is permutation invariant under reordered zones."""
    engine = SpatialAnalysisEngine()

    # 1. No geometry => UNAVAILABLE (0.0, 1.0)
    zone_means = {
        "z1": [0.4, 0.5, 0.6],
        "z2": [0.7, 0.8, 0.9],
        "z3": [0.2, 0.3, 0.4],
    }
    i_val, p_val, status = engine._compute_morans_i(zone_means, zone_centroids=None, zone_adjacency=None)
    assert i_val == 0.0
    assert p_val == 1.0
    assert status == "UNAVAILABLE"

    # 2. Permutation invariance with geometry
    centroids = {
        "z1": (0.0, 0.0),
        "z2": (10.0, 0.0),
        "z3": (0.0, 10.0),
        "z4": (10.0, 10.0),
    }
    zone_means_4 = {
        "z1": [0.3],
        "z2": [0.3],
        "z3": [0.8],
        "z4": [0.8],
    }
    i_1, _, status1 = engine._compute_morans_i(zone_means_4, zone_centroids=centroids)
    assert status1 == "AVAILABLE"

    # Reordered dictionary
    zone_means_reordered = {
        "z4": [0.8],
        "z1": [0.3],
        "z3": [0.8],
        "z2": [0.3],
    }
    i_2, _, status2 = engine._compute_morans_i(zone_means_reordered, zone_centroids=centroids)
    assert status2 == "AVAILABLE"
    assert math.isclose(i_1, i_2, abs_tol=1e-5)


def test_watchdog_insufficient_evidence_when_short():
    """Invariant: Watchdog returns INSUFFICIENT_EVIDENCE when observations N < 4."""
    profile = CropParameterResolver.resolve("wheat")
    report = CropContextConsistency.evaluate_consistency(
        observed_ndvi=[0.4, 0.5],
        tau_series=[0.2, 0.3],
        profile=profile,
    )
    assert report["consistency"] == "INSUFFICIENT_EVIDENCE"
    assert report["action"] == "PROCEED"
    assert report["mismatch_detected"] is False


def test_adversarial_causal_gdd_trajectory_invariance():
    """Adversarial test: GDD_A(1:t) != GDD_B(1:t) with identical GDD_T MUST produce different transition timing."""
    engine = PhenologyEngine(crop_config={"gdd_base_temp": 10.0}, requires_vernalization=False)
    n = 30
    dates = [f"2026-06-{d:02d}" for d in range(1, n + 1)]
    # Gradually increasing greenness
    ndvi = [0.15 + 0.02 * i for i in range(n)]
    vel = [0.02] * n

    # Season A: Steady progressive thermal accumulation
    gdd_a = [i * 40.0 for i in range(n)]  # Ends at 1160.0
    # Season B: Zero thermal accumulation until sudden spike on the very last day
    gdd_b = [0.0] * (n - 1) + [1160.0]

    stages_a, confs_a = engine.infer_daily_stages(ndvi, vel, dates, gdd_a)
    stages_b, confs_b = engine.infer_daily_stages(ndvi, vel, dates, gdd_b)

    # Invariant: Season A must develop through vegetative/reproductive earlier than Season B
    assert stages_a != stages_b
    assert stages_a.count(PhenologyStage.VEGETATIVE) > stages_b.count(PhenologyStage.VEGETATIVE)
    # Season B was cold for 29 days, so day 15 must remain in bare soil/emergence
    assert stages_b[14] in (PhenologyStage.BARE_SOIL, PhenologyStage.EMERGENCE)
    assert stages_a[14] in (PhenologyStage.VEGETATIVE, PhenologyStage.REPRODUCTIVE)


def test_stress_attribution_biological_impact_vs_physical_magnitude():
    """Invariant: Stage sensitivity s_k(c, z) scales biological impact I_k, leaving S_k unmutated."""
    from layer2_intelligence.schemas import StressEvidence, CropCycleContext
    from layer2_intelligence.phenology_adjuster import adjust_stress_for_phenology

    item = StressEvidence(
        stress_id="test_water_001",
        stress_type="WATER",
        severity=0.50,
        confidence=0.70,
    )
    cycle = CropCycleContext(
        crop_type="maize",
        current_stage="REPRODUCTIVE",
        gdd_accumulated=850.0,
    )

    adjusted = adjust_stress_for_phenology([item], cycle)
    res = adjusted[0]
    # Physical stress magnitude remains 0.50
    assert res.stress_magnitude == 0.50
    # Stage sensitivity scales impact
    from layer2_veg_int.crop_response_profile import CropParameterResolver
    prof = CropParameterResolver.resolve("maize")
    expected_mult = prof.water_sensitivity[PhenologyStage.REPRODUCTIVE]
    assert res.biological_impact == round(0.50 * expected_mult, 3)
    # Diagnostic evidence confidence is NOT multiplied by sensitivity
    assert res.confidence == 0.70


def test_unexplained_drop_does_not_produce_biotic_fallacy():
    """Invariant: Unexplained drop without weed/pathogen indicators returns None (not BIOTIC)."""
    from layer2_intelligence.stress_attributor import _assess_biotic_stress
    from layer2_intelligence.schemas import DataHealthScore

    # Declining NDVI without water or thermal stress, but NO weed or ASMAE pathogen indicators
    biotic_item = _assess_biotic_stress(
        ndvi=0.28,
        evi=0.18,
        veg_fraction=0.25,
        conf_ceiling=1.0,
        base_unc=0.1,
        conflict_penalty=0.0,
        veg_features={"ndvi_mean": 0.28, "evi_mean": 0.18},
        plot_id="plot_test",
        run_id="run_test",
        spatial_scope="plot",
        scope_id=None,
        has_water_stress=False,
        has_thermal_stress=False,
        weed_pressure=None,
        context=None,
    )
    # Must NOT fabricate a biotic diagnosis from absence of abiotic stress
    assert biotic_item is None


def test_decomposed_npp_fields_in_runner_output():
    """Invariant: Runner exposes npp_light_temperature and npp_spectral_water_adjusted in curve output."""
    runner = VegetationIntelligenceEngine()
    n = 20
    dates = [f"2026-05-{d:02d}" for d in range(1, n + 1)]
    timeseries = [{
        "date": d,
        "ndvi_mean": 0.55,
        "ndvi_interpolated": 0.55,
        "uncertainty": 0.03,
        "is_observed": True,
        "tmean": 22.0,
        "temp_max": 28.0,
        "temp_min": 16.0,
        "rain": 10.0,
        "et0": 4.0,
        "ndwi": 0.20,
        "ndmi": 0.15,
    } for d in dates]

    tensor = FieldTensor(
        run_id="test_npp_decomp_001",
        plot_id="plot_test_npp",
        plot_timeseries=timeseries,
    )

    class DummyOrchestratorInputs:
        crop_config = {"crop": "maize"}
        operational_context = {"lat": 32.0}

    output = runner.analyze_tensor(tensor, orch_inputs=DummyOrchestratorInputs())

    curve = output.curve
    assert len(curve.npp_light_temperature_series) == n
    assert len(curve.npp_spectral_water_adjusted_series) == n
    assert curve.water_constraint_source in ("SPECTRAL_PROXY", "NONE")
    assert all(val >= 0.0 for val in curve.npp_light_temperature_series)


def test_canonical_stress_attribution_runtime_coverage_and_no_unbound_locals():
    """Invariant: Water, nutrient, thermal and unconditioned stress adjustment never crash with UnboundLocalError."""
    from layer2_intelligence.stress_attributor import (
        _assess_water_stress,
        _assess_nutrient_stress,
        _assess_thermal_stress,
        attribute_stress,
    )
    from layer2_intelligence.phenology_adjuster import adjust_stress_for_phenology
    from layer2_intelligence.schemas import StressEvidence, CropCycleContext, DataHealthScore

    # 1. Test ordinary water stress combinations (low, normal, high)
    for ndmi, sm in [(0.10, 0.10), (0.40, 0.30), (0.05, 0.25), (0.35, 0.08)]:
        res = _assess_water_stress(
            ndmi=ndmi, soil_moisture=sm, precip=10.0, vpd=1.5, et0=4.0,
            conf_ceiling=1.0, base_unc=0.1, conflict_penalty=0.0,
            water_features={"ndmi_mean": ndmi, "soil_moisture_vwc": sm},
            plot_id="p1", run_id="r1", spatial_scope="plot", scope_id=None,
        )
        if ndmi < 0.2 or sm < 0.2:
            assert res is not None
            assert res.stress_magnitude > 0.0
        else:
            assert res is None

    # 2. Test ordinary nutrient stress combinations
    for ndvi, evi, water_conf in [(0.30, 0.15, False), (0.70, 0.50, False), (0.30, 0.15, True)]:
        res_nut = _assess_nutrient_stress(
            ndvi=ndvi, evi=evi, ndmi=0.35, soil_moisture=0.30,
            conf_ceiling=1.0, base_unc=0.1, conflict_penalty=0.0,
            veg_features={"ndvi_mean": ndvi, "evi_mean": evi},
            water_features={"ndmi_mean": 0.35},
            plot_id="p1", run_id="r1", spatial_scope="plot", scope_id=None,
            has_water_stress=water_conf,
        )
        if ndvi <= 0.45:
            assert res_nut is not None
            assert res_nut.stress_magnitude > 0.0
        else:
            assert res_nut is None

    # 3. Test arbitrary stress types in adjust_stress_for_phenology (including unrepresented types)
    stress_list = [
        StressEvidence(stress_id="s1", stress_type="PHOTOSYNTHETIC_SHUTDOWN", severity=0.60),
        StressEvidence(stress_id="s2", stress_type="MECHANICAL", severity=0.45),
        StressEvidence(stress_id="s3", stress_type="UNKNOWN", severity=0.30),
        StressEvidence(stress_id="s4", stress_type="UNRESOLVED", severity=0.50),
    ]
    cycle = CropCycleContext(crop_type="wheat", current_stage="VEGETATIVE", gdd_accumulated=450.0)
    adjusted = adjust_stress_for_phenology(stress_list, cycle)
    assert len(adjusted) == 4
    for item in adjusted:
        assert item.biological_impact > 0.0
        assert item.stress_magnitude > 0.0


def test_compound_stress_synergy_preserves_physical_magnitude():
    """Invariant: Compound synergy amplifies biological impact I_k without mutating physical magnitude S_k."""
    from layer2_intelligence.stress_attributor import _apply_compound_stress_synergy
    from layer2_intelligence.schemas import StressEvidence

    water_item = StressEvidence(
        stress_id="w1", stress_type="WATER", severity=0.50, stress_magnitude=0.50,
    )
    thermal_item = StressEvidence(
        stress_id="t1", stress_type="THERMAL", severity=0.60, stress_magnitude=0.60,
    )

    _apply_compound_stress_synergy([water_item, thermal_item])

    # Physical magnitude S_k remains 0.50
    assert water_item.stress_magnitude == 0.50
    # Synergy factor 1.25 scales biological impact: 0.50 * 1.25 = 0.625
    assert water_item.compound_synergy_factor == 1.25
    assert water_item.biological_impact == 0.625
    assert water_item.compound_partner == "THERMAL"


def test_operational_unresolved_emission_on_unexplained_decline():
    """Invariant: Unexplained vegetation decline emits an UNRESOLVED item with computed posterior."""
    from layer2_intelligence.stress_attributor import attribute_stress
    from layer2_intelligence.schemas import DataHealthScore

    veg_feats = {
        "ndvi_mean": {"value": 0.42, "source_evidence_ids": ["ev_opt_1"]},
        "evi_mean": {"value": 0.30, "source_evidence_ids": ["ev_opt_2"]},
        "vegetation_fraction_scl": {"value": 0.35, "source_evidence_ids": ["ev_opt_3"]},
    }
    water_feats = {
        "ndmi_mean": {"value": 0.35, "source_evidence_ids": ["ev_water_1"]},
        "soil_moisture_vwc": {"value": 0.30, "source_evidence_ids": ["ev_water_2"]},
    }
    env_feats = {
        "temp_max": {"value": 24.0, "source_evidence_ids": ["ev_weather_1"]},
        "vpd": {"value": 1.2, "source_evidence_ids": ["ev_weather_2"]},
        "precip": {"value": 15.0, "source_evidence_ids": ["ev_weather_3"]},
    }

    stress_items = attribute_stress(
        water_features=water_feats,
        vegetation_features=veg_feats,
        environment_features=env_feats,
        operational_features={},
        soil_site_features={},
        conflicts=[],
        data_health=DataHealthScore(overall=0.9, confidence_ceiling=0.9),
        plot_id="plot_unresolved_test",
        run_id="run_test",
    )

    assert len(stress_items) == 1
    item = stress_items[0]
    assert item.stress_type == "UNRESOLVED"
    assert item.posterior_status == "COMPUTED"
    assert item.hypothesis_posterior is not None
    assert item.hypothesis_posterior >= 0.10


def test_stage_conditioned_compound_synergy_amplification():
    """Invariant: Compound synergy β(c, z) is amplified at reproductive stage (Mittler 2006)."""
    from layer2_intelligence.schemas import StressEvidence, CropCycleContext
    from layer2_intelligence.phenology_adjuster import adjust_stress_for_phenology

    water_item_rep = StressEvidence(
        stress_id="w_rep", stress_type="WATER", severity=0.50, stress_magnitude=0.50,
        compound_partner="THERMAL", compound_synergy_factor=1.25, confidence=0.8,
    )
    cycle_rep = CropCycleContext(crop_type="wheat", current_stage="REPRODUCTIVE", gdd_accumulated=800.0)
    res_rep = adjust_stress_for_phenology([water_item_rep], cycle_rep)[0]

    water_item_veg = StressEvidence(
        stress_id="w_veg", stress_type="WATER", severity=0.50, stress_magnitude=0.50,
        compound_partner="THERMAL", compound_synergy_factor=1.25, confidence=0.8,
    )
    cycle_veg = CropCycleContext(crop_type="wheat", current_stage="VEGETATIVE", gdd_accumulated=250.0)
    res_veg = adjust_stress_for_phenology([water_item_veg], cycle_veg)[0]

    # Invariant: Reproductive synergy factor > Vegetative synergy factor
    assert res_rep.compound_synergy_factor > res_veg.compound_synergy_factor
    assert res_rep.display_priority > 0.0
    assert res_veg.display_priority > 0.0


def test_unknown_vegetation_abstention_in_phenology_adjuster():
    """Invariant: UNKNOWN_VEGETATION never receives crop-specific multiplier and is marked diagnostic-only."""
    from layer2_intelligence.schemas import StressEvidence, CropCycleContext
    from layer2_intelligence.phenology_adjuster import adjust_stress_for_phenology
    from layer2_veg_int.crop_response_profile import CropParameterResolver

    item = StressEvidence(
        stress_id="w_unk", stress_type="WATER", severity=0.60, stress_magnitude=0.60,
    )
    profile_unk = CropParameterResolver.resolve("UNKNOWN_VEGETATION")
    cycle_unk = CropCycleContext(crop_type="UNKNOWN_VEGETATION", current_stage="REPRODUCTIVE")
    cycle_unk.crop_response_profile = profile_unk

    res = adjust_stress_for_phenology([item], cycle_unk)[0]
    # Invariant: No crop-specific sensitivity amplification for unknown vegetation
    assert res.biological_impact == 0.60
    assert res.diagnostic_only is True
    assert "UNKNOWN_VEGETATION_UNCONDITIONED" in res.flags


def test_crop_specific_compound_synergy_divergence():
    """Invariant: Maize (C4 grass silking desynchronization) has higher compound synergy than Olive (sclerophyllous tree)."""
    from layer2_veg_int.crop_response_profile import CropParameterResolver
    from layer2_veg_int.schema import PhenologyStage

    maize_prof = CropParameterResolver.resolve("maize")
    olive_prof = CropParameterResolver.resolve("olive")
    wheat_prof = CropParameterResolver.resolve("wheat")

    # Co-occurring Water + Thermal at Reproductive stage
    maize_synergy = maize_prof.get_compound_synergy(PhenologyStage.REPRODUCTIVE, "WATER", "THERMAL")
    wheat_synergy = wheat_prof.get_compound_synergy(PhenologyStage.REPRODUCTIVE, "WATER", "THERMAL")
    olive_synergy = olive_prof.get_compound_synergy(PhenologyStage.REPRODUCTIVE, "WATER", "THERMAL")

    # Invariant: Maize > Wheat > Olive
    assert maize_synergy > wheat_synergy > olive_synergy
    assert maize_synergy >= 1.60
    assert olive_synergy < 1.30


def test_magnitude_uncertainty_propagation_across_stress_attributions():
    """Invariant: All attributed stress items carry non-zero physical magnitude uncertainty."""
    from layer2_intelligence.stress_attributor import attribute_stress
    from layer2_intelligence.schemas import DataHealthScore

    veg_feats = {
        "ndvi_mean": {"value": 0.32, "source_evidence_ids": ["ev_opt_1"]},
        "evi_mean": {"value": 0.22, "source_evidence_ids": ["ev_opt_2"]},
    }
    water_feats = {
        "ndmi_mean": {"value": -0.10, "source_evidence_ids": ["ev_water_1"]},
        "soil_moisture_vwc": {"value": 0.08, "source_evidence_ids": ["ev_water_2"]},
    }
    env_feats = {
        "temp_max": {"value": 38.5, "source_evidence_ids": ["ev_weather_1"]},
        "vpd": {"value": 3.8, "source_evidence_ids": ["ev_weather_2"]},
    }

    stress_items = attribute_stress(
        water_features=water_feats,
        vegetation_features=veg_feats,
        environment_features=env_feats,
        operational_features={},
        soil_site_features={},
        conflicts=[],
        data_health=DataHealthScore(overall=0.9, confidence_ceiling=0.9),
        plot_id="plot_unc_test",
        run_id="run_test",
    )

    assert len(stress_items) >= 2
    for s in stress_items:
        assert s.magnitude_uncertainty is not None
        assert s.magnitude_uncertainty > 0.0
        assert s.stress_magnitude > 0.0



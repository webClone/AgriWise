"""Tests for Advanced Biophysical Engines in Layer 4 Nutrients."""

from layer4_nutrients.salinity.engine import SalinityEngine
from layer4_nutrients.biological_fixation.engine import BiologicalFixationEngine
from layer4_nutrients.phosphorus_sorption.engine import PhosphorusSorptionEngine
from layer4_nutrients.photosynthesis_nue.engine import PhotosynthesisNUEEngine
from layer4_nutrients.environmental_losses.engine import EnvironmentalLossEngine


def test_salinity_maas_hoffman_yield_reduction():
    engine = SalinityEngine()
    # Baseline low salinity
    res_low = engine.assess_salinity_impact(ec_ds_m=1.0, crop_type="wheat")
    assert res_low.relative_yield >= 0.95
    assert res_low.leaching_requirement <= 0.20

    # High salinity exceeding wheat threshold
    res_high = engine.assess_salinity_impact(ec_ds_m=10.0, crop_type="wheat")
    assert res_high.relative_yield < res_low.relative_yield
    assert res_high.yield_loss_pct > 0.0


def test_biological_fixation_legume_vs_non_legume():
    engine = BiologicalFixationEngine()
    # Non-legume (wheat) -> 0 symbiotic fixation
    res_wheat = engine.estimate_bnf(crop_type="wheat", yield_target_t_ha=5.0)
    assert res_wheat.symbiotic_bnf_kg_ha == 0.0
    assert res_wheat.is_legume is False

    # Legume (soybean) -> active symbiotic fixation
    res_soy = engine.estimate_bnf(crop_type="soybean", yield_target_t_ha=3.0, soil_n_ppm=10.0)
    assert res_soy.symbiotic_bnf_kg_ha > 0.0
    assert res_soy.ndfa_fraction > 0.0
    assert res_soy.is_legume is True

    # High soil nitrogen inhibits biological fixation
    res_soy_high_n = engine.estimate_bnf(crop_type="soybean", yield_target_t_ha=3.0, soil_n_ppm=60.0)
    assert res_soy_high_n.total_bnf_kg_ha < res_soy.total_bnf_kg_ha


def test_phosphorus_sorption_clay_and_ph_effects():
    engine = PhosphorusSorptionEngine()
    # Low sorption (loam, neutral pH)
    res_neutral = engine.compute_p_availability(soil_ph=6.5, clay_pct=15.0, soil_p_ppm=25.0)
    # High sorption (heavy clay, acidic pH)
    res_acid_clay = engine.compute_p_availability(soil_ph=4.8, clay_pct=50.0, soil_p_ppm=25.0)

    assert res_acid_clay.fixation_fraction > res_neutral.fixation_fraction
    assert res_acid_clay.plant_available_p_ppm < res_neutral.plant_available_p_ppm


def test_photosynthesis_nue_coupling():
    engine = PhotosynthesisNUEEngine()
    res = engine.analyze(
        crop_type="wheat",
        lai_current=3.5,
        fpar_current=0.75,
        npp_g_c_m2_day=8.0,
        n_applied_kg_ha=120.0,
        soil_n_supply_kg_ha=40.0,
        growth_stage="vegetative",
    )
    assert res is not None
    assert res.nni > 0.0
    assert res.critical_n_pct > 0.0
    assert res.actual_n_pct > 0.0
    assert res.rue_actual > 0.0


def test_environmental_losses_volatilization_and_leaching():
    engine = EnvironmentalLossEngine()
    # Broadcast urea with high pH and temperature
    res_broadcast = engine.compute_all_losses(
        n_applied_kg_ha=150.0,
        application_method="BROADCAST",
        product="UREA",
        soil_ph=8.0,
        temperature_c=28.0,
        total_drainage_mm=60.0,
    )
    assert res_broadcast.volatilization.loss_kg_ha > 0.0
    assert res_broadcast.leaching.loss_kg_ha > 0.0
    assert res_broadcast.total_loss_kg_ha > 0.0

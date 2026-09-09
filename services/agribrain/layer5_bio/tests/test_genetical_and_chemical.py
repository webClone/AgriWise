import pytest
from layer5_bio.engines.genetical_engine import run_genetical_engine
from layer5_bio.engines.chemical_engine import (
    run_chemical_engine,
    SprayDriftRandomForestRegressor,
    ChemicalSpec,
    CHEMICAL_REGISTRY,
)
from layer5_bio.schema import ThreatId, ThreatClass


def test_genetical_engine_eti_resistance_match():
    """Verify R-gene effector matching triggers Effector-Triggered Immunity (ETI)."""
    # Wheat variety 'giza 168' possesses Sr2 and Yr18, matching FUNGAL_RUST effectors
    res_resistant = run_genetical_engine(
        crop_type="wheat",
        variety="giza 168",
        threat_id=ThreatId.FUNGAL_RUST,
        plot_context={"crop": "wheat", "variety": "giza 168"},
    )
    
    assert res_resistant["match_found"] is True
    assert len(res_resistant["matching_r_genes"]) > 0
    # ETI should strongly suppress the susceptibility score and logit delta
    assert res_resistant["susceptibility_score"] < 0.20
    assert res_resistant["evidence_logit"].logit_delta <= -2.0


def test_genetical_engine_susceptible_variety():
    """Verify that a variety without matching R-genes exhibits higher susceptibility."""
    # Tomato variety 'roma' lacks R-genes for BACTERIAL_BLIGHT (Xantho_R1)
    res_susceptible = run_genetical_engine(
        crop_type="tomato",
        variety="roma",
        threat_id=ThreatId.BACTERIAL_BLIGHT,
        plot_context={"crop": "tomato", "variety": "roma"},
    )
    
    assert res_susceptible["match_found"] is False
    assert res_susceptible["evidence_logit"].logit_delta >= -1.0


def test_chemical_engine_systemic_vs_contact_washoff():
    """Verify pesticide degradation and rainfall wash-off kinetics."""
    ts = [
        {"tmean": 22.0, "humidity": 70.0, "rain": 0.0, "wind_speed": 2.0}
        for _ in range(5)
    ]
    # Add a heavy rain day
    ts.append({"tmean": 20.0, "humidity": 90.0, "rain": 45.0, "wind_speed": 3.0})
    
    biophys_dummy = {
        "canopy_microclimate": {"transpiration_rate_mm_hr": 0.25}
    }
    
    plot_context = {
        "applied_chemicals": [
            {"chemical_id": "azoxystrobin", "applied_days_ago": 3},  # systemic
            {"chemical_id": "copper_hydroxide", "applied_days_ago": 3},  # contact
        ]
    }
    
    chem_res = run_chemical_engine(
        ts=ts,
        veg_output=None,
        decision_output=None,
        plot_context=plot_context,
        biophys_res=biophys_dummy,
    )
    
    assert "chemical_protection_factors" in chem_res
    applied = chem_res["applied_status"]
    assert len(applied) == 2
    
    # Systemic azoxystrobin (wash_off_threshold=40mm) has high translocation,
    # whereas contact copper_hydroxide (threshold=10mm) suffers heavier wash-off
    azoxy = next(a for a in applied if a["chemical_id"] == "azoxystrobin")
    copper = next(a for a in applied if a["chemical_id"] == "copper_hydroxide")
    
    assert azoxy["translocated_fraction"] > copper["translocated_fraction"]
    assert copper["wash_off_pct"] > azoxy["wash_off_pct"]


def test_spray_drift_regressor():
    """Verify spray drift distance under low vs high wind conditions."""
    regressor = SprayDriftRandomForestRegressor()
    
    # Low wind (1.5 m/s)
    drift_calm = regressor.predict(
        wind_speed=1.5,
        temperature=20.0,
        relative_humidity=75.0,
        boom_height_m=0.5,
        droplet_size_vmd=250.0,
        travel_speed_kmh=10.0,
    )
    
    # High wind (8.0 m/s)
    drift_windy = regressor.predict(
        wind_speed=8.0,
        temperature=28.0,
        relative_humidity=40.0,
        boom_height_m=0.8,
        droplet_size_vmd=180.0,
        travel_speed_kmh=16.0,
    )
    
    assert drift_windy["drift_distance_m"] > drift_calm["drift_distance_m"]
    assert drift_windy["neighborhood_deposition_pct"] > drift_calm["neighborhood_deposition_pct"]

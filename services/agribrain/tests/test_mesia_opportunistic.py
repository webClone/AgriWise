"""Comprehensive Automated Test Suite for MESIA Opportunistic & Ambient Sensing Architecture.

Verifies:
1. GNSS-R SNR Interferometry solver & NMEA GSV parsing.
2. Cellular Downlink Forward-Scatter radar & canopy attenuation.
3. Terrestrial Broadcast UHF/VHF deep root-zone skin depth & VWC.
4. Spaceborne CYGNSS / Spire orbital track polygon filtering & reflectivity.
5. Commercial Microwave Link (CML) telecom backhaul attenuation.
6. Opportunistic Orchestrator compliance with Principle P-08.
7. DeploymentDesigner PURE_REMOTE ($0 BOM, 0 nodes) and PERIMETER_SENTINEL.
"""

import math
from datetime import datetime, timezone
import pytest

from services.agribrain.mesia.opportunistic import (
    AmbientOpportunityDescriptor,
    AmbientRadioFamily,
    BistaticForwardScatterObservation,
    BroadcastUhfEngine,
    CellularDownlinkCorrelator,
    CommercialMicrowaveLinkEngine,
    GnssInterferometryObservation,
    GnssReflectometrySolver,
    OpportunisticSensingOrchestrator,
    PureRemoteObservation,
    SensingModality,
    SpaceborneGnssrEngine,
)
from services.agribrain.mesia.planning.deployment_designer import (
    CandidateAnchor,
    Coordinate3D,
    DeploymentMode,
    MESIADeploymentDesigner,
    Microzone,
)
from services.agribrain.mesia.operations.deployment_designer import (
    DeploymentDesigner,
    SiteSurveyInput,
)
from services.agribrain.layer05_asmae.observation.index_state_mapping import (
    get_mapping,
    validate_forbidden_state_update,
)
from services.agribrain.layer05_asmae.config import (
    IDX_ROOT_ZONE_WATER,
    IDX_CANOPY_WATER,
    IDX_SURFACE_WETNESS,
    IDX_CHLOROPHYLL,
    IDX_VIGOR,
    IDX_LAI,
)


def test_gnss_ir_nmea_parsing_and_solver():
    """Verify GNSS-IR parser extracts satellites and solves multipath interferometry."""
    # Synthetic realistic NMEA GSV log with an ascending satellite arc
    nmea_lines = [
        "$GPGSV,2,1,08,01,05,045,32,02,12,120,38,03,45,210,44,04,65,015,48*78",
        "$GPGSV,2,2,08,05,10,050,35,06,18,055,40,07,24,060,42,08,29,065,44*7C",
    ]
    parsed = GnssReflectometrySolver.parse_nmea_gsv_sentences(nmea_lines)
    assert 1 in parsed
    assert 5 in parsed

    # Generate synthetic ascending multipath arc for PRN 05 (elevations 5 to 25 deg)
    h_true = 2.10  # 2.1m antenna height above ground
    wavelength = GnssReflectometrySolver.get_wavelength(GnssReflectometrySolver.GPS_L1_FREQ)
    arc_points = []
    for elev_deg in range(5, 26):
        sin_e = math.sin(math.radians(elev_deg))
        # Direct power + multipath cosine oscillation
        direct_db = 30.0 + 0.5 * elev_deg
        osc = 5.0 * math.cos((4.0 * math.pi * h_true / wavelength) * sin_e + 0.35)
        arc_points.append((float(elev_deg), 120.0, direct_db + osc))

    obs = GnssReflectometrySolver.solve_from_arc(
        prn=5,
        constellation="GPS",
        arc_points=arc_points,
    )

    assert obs.prn == 5
    assert obs.constellation == "GPS"
    # Resolved height should be close to 2.10m (+-0.15m discretisation)
    assert abs(obs.effective_reflector_height_m - h_true) < 0.20
    assert 0.02 <= obs.estimated_vwc <= 0.50
    assert len(obs.content_hash()) == 64


def test_cellular_forward_scatter_engine():
    """Verify passive cellular forward-scatter computes excess canopy loss and moisture index."""
    tower_xyz = (0.0, 0.0, 30.0)      # 30m cell tower
    rx_xyz = (500.0, 200.0, 2.0)      # Field edge receiver
    freq = 1.8e9                      # 1.8 GHz LTE Band 3

    # Case A: Clear air / bare soil
    obs_bare = CellularDownlinkCorrelator.process_bistatic_reception(
        source_tower_id="CELL_TOWER_402",
        receiver_node_id="SENTINEL_RX_01",
        carrier_freq_hz=freq,
        tower_xyz_m=tower_xyz,
        receiver_xyz_m=rx_xyz,
        measured_rsrp_dbm=-82.0,       # Near free-space power
        canopy_depth_m=40.0,
    )

    # Case B: Dense vegetative canopy (higher excess attenuation)
    obs_dense = CellularDownlinkCorrelator.process_bistatic_reception(
        source_tower_id="CELL_TOWER_402",
        receiver_node_id="SENTINEL_RX_01",
        carrier_freq_hz=freq,
        tower_xyz_m=tower_xyz,
        receiver_xyz_m=rx_xyz,
        measured_rsrp_dbm=-98.0,       # 16 dB extra loss
        canopy_depth_m=40.0,
    )

    assert obs_dense.excess_canopy_loss_db > obs_bare.excess_canopy_loss_db
    assert obs_dense.estimated_canopy_water_index > obs_bare.estimated_canopy_water_index
    assert 0.0 <= obs_dense.estimated_canopy_water_index <= 1.0


def test_terrestrial_broadcast_uhf_skin_depth_and_vwc():
    """Verify DVB-T2 UHF broadcast achieves deep sub-surface root-zone skin depth."""
    freq = 600e6  # 600 MHz DVB-T2
    depth_dry = BroadcastUhfEngine.compute_skin_depth_m(freq, conductivity_s_m=0.005)
    depth_wet = BroadcastUhfEngine.compute_skin_depth_m(freq, conductivity_s_m=0.08)

    # In dry soil, 600 MHz UHF skin depth reaches ~30cm, while 100 MHz FM exceeds 50cm
    depth_fm = BroadcastUhfEngine.compute_skin_depth_m(100e6, conductivity_s_m=0.005)
    assert depth_dry > depth_wet
    assert depth_dry >= 0.25, f"Dry soil UHF skin depth should exceed 25cm: {depth_dry}"
    assert depth_fm >= 0.50, f"Dry soil FM skin depth should exceed 50cm: {depth_fm}"

    # Inversion from reflectivity
    vwc_low, depth_low, _ = BroadcastUhfEngine.solve_deep_vwc(0.10, grazing_angle_deg=45.0, freq_hz=freq)
    vwc_high, depth_high, _ = BroadcastUhfEngine.solve_deep_vwc(0.40, grazing_angle_deg=45.0, freq_hz=freq)

    assert vwc_high > vwc_low, "Higher reflectivity must indicate higher moisture"
    assert 0.01 <= vwc_low <= 0.55


def test_spaceborne_gnssr_pure_remote_filtering():
    """Verify 100% pure remote spaceborne reflectometry filters specular points inside polygon."""
    farm_polygon = [
        (33.360, 6.850),
        (33.360, 6.860),
        (33.370, 6.860),
        (33.370, 6.850),
    ]

    tracks = [
        {"lat": 33.365, "lon": 6.855, "reflectivity_db": -16.0},  # Inside
        {"lat": 33.368, "lon": 6.852, "reflectivity_db": -14.0},  # Inside
        {"lat": 33.380, "lon": 6.870, "reflectivity_db": -12.0},  # Outside
    ]

    observations = SpaceborneGnssrEngine.filter_and_ingest_tracks(
        granule_id="CYGNSS_L3_V3.2_20260902",
        mission="CYGNSS",
        specular_tracks=tracks,
        farm_polygon=farm_polygon,
    )

    # Exactly 2 tracks should be accepted inside the farm
    assert len(observations) == 2
    for obs in observations:
        assert obs.mission == "CYGNSS"
        assert 0.02 <= obs.estimated_root_zone_vwc <= 0.55
        assert SpaceborneGnssrEngine.is_point_in_polygon(obs.specular_point_wgs84[0], obs.specular_point_wgs84[1], farm_polygon)


def test_cml_telecom_backhaul_attenuation():
    """Verify Commercial Microwave Link evaluates attenuation and rain/humidity proxy."""
    cml_obs = CommercialMicrowaveLinkEngine.process_link_attenuation(
        link_id="MOBILIS_BH_EL_OUED_08",
        freq_ghz=18.0,
        link_length_km=4.5,
        baseline_rsl_dbm=-45.0,
        measured_rsl_dbm=-52.0,  # 7 dB rain/humidity fade
        specular_center_wgs84=(33.365, 6.855),
    )

    assert cml_obs.mission == "CML_TELECOM"
    assert cml_obs.reflectivity_db == -7.0
    assert 0.0 <= cml_obs.estimated_root_zone_vwc <= 1.0


def test_opportunistic_orchestrator_p08_compliance():
    """Verify orchestrator emits valid ASMAEInnovationProposal objects under Principle P-08."""
    orchestrator = OpportunisticSensingOrchestrator("EL_OUED_50HA")

    now = datetime.now(timezone.utc)
    gnss_obs = GnssInterferometryObservation(
        observation_id="gnss-01",
        timestamp=now,
        prn=14,
        constellation="GPS",
        carrier_freq_hz=1575.42e6,
        elevation_start_deg=5.0,
        elevation_end_deg=28.0,
        azimuth_mean_deg=145.0,
        effective_reflector_height_m=2.05,
        dielectric_phase_shift_rad=0.45,
        estimated_vwc=0.26,
        observation_variance=0.015,
        snr_detrended_peaks=[1.2, -1.5, 2.1],
        raw_nmea_hash="d" * 64,
    )

    proposal = orchestrator.process_gnss_ir_observation(gnss_obs, prior_state_vwc=0.20)
    assert proposal.authority_scope == "evidence_proposal"
    assert proposal.target_state_variable == "root_zone_water"
    assert abs(proposal.innovation_value - 0.06) < 1e-4

    # Pure remote CYGNSS proposal
    remote_obs = PureRemoteObservation(
        observation_id="cygnss-01",
        mission="CYGNSS",
        timestamp=now,
        specular_point_wgs84=(33.365, 6.855),
        reflectivity_db=-15.0,
        estimated_root_zone_vwc=0.28,
        confidence=0.85,
        coverage_fraction=1.0,
        external_granule_id="GRANULE_99",
    )
    remote_prop = orchestrator.process_pure_remote_observation(remote_obs, prior_state_vwc=0.20)
    assert remote_prop.authority_scope == "evidence_proposal"
    assert remote_prop.target_state_variable == "root_zone_water"


def test_deployment_designer_pure_remote_mode():
    """Verify DeploymentDesigner in PURE_REMOTE mode yields 0 in-situ nodes and $0 cost."""
    survey = SiteSurveyInput(
        survey_id="SURVEY-REMOTE-01",
        plot_boundary_wgs84=[
            (33.360, 6.850),
            (33.360, 6.860),
            (33.370, 6.860),
            (33.370, 6.850),
        ],
        terrain_elevation_m=85.0,
        max_budget_usd=0.0,
    )

    plan = DeploymentDesigner.design_deployment(survey, mode=DeploymentMode.PURE_REMOTE)
    assert plan.target_not_observable is False
    assert len(plan.nodes) == 0, "Pure Remote mode must place 0 physical nodes on the farm"
    assert plan.total_estimated_cost_usd == 0.0, "Pure Remote mode must cost $0.00 BOM"
    assert len(plan.commissioning_checklist) >= 2
    assert plan.expected_observable_zones > 0


def test_deployment_designer_perimeter_sentinel_mode():
    """Verify DeploymentDesigner in PERIMETER_SENTINEL mode selects at most 2 boundary sentinels."""
    survey = SiteSurveyInput(
        survey_id="SURVEY-PERIM-01",
        plot_boundary_wgs84=[
            (33.360, 6.850),
            (33.360, 6.860),
            (33.370, 6.860),
            (33.370, 6.850),
        ],
        terrain_elevation_m=85.0,
        max_budget_usd=500.0,
    )

    plan = DeploymentDesigner.design_deployment(survey, mode=DeploymentMode.PERIMETER_SENTINEL)
    assert plan.target_not_observable is False
    assert 1 <= len(plan.nodes) <= 2, f"Perimeter Sentinel must select 1 or 2 nodes, got {len(plan.nodes)}"
    assert plan.total_estimated_cost_usd <= 500.0


def test_asmae_index_state_mapping_ambient_features():
    """Verify all ambient opportunistic features are registered in ASMAE with optical protection."""
    features = [
        ("mesia_gnssr_in_situ_vwc", IDX_ROOT_ZONE_WATER),
        ("mesia_cellular_canopy_water", IDX_CANOPY_WATER),
        ("mesia_dvb_deep_soil_water", IDX_ROOT_ZONE_WATER),
        ("mesia_spaceborne_gnssr_vwc", IDX_ROOT_ZONE_WATER),
        ("mesia_cml_humidity", IDX_SURFACE_WETNESS),
    ]

    for feat_name, target_idx in features:
        m = get_mapping(feat_name)
        assert m is not None, f"Feature {feat_name} must be registered in ASMAE"
        assert m.sensor == "MESIA"
        assert target_idx in m.target_state_indices

        # Optical states must remain strictly forbidden
        assert validate_forbidden_state_update(feat_name, IDX_CHLOROPHYLL) is True
        assert validate_forbidden_state_update(feat_name, IDX_VIGOR) is True
        assert validate_forbidden_state_update(feat_name, IDX_LAI) is True


def test_native_gnss_extractor_real_file_parsing(tmp_path):
    """Verify NativeGnssExtractor parses real NMEA logs without mocks."""
    from services.agribrain.mesia.lanes.gnss.gnss_extractor import NativeGnssExtractor

    nmea_content = (
        "$GPGGA,123519,3321.680,N,00651.300,E,4,08,0.9,545.4,M,46.9,M,,*4C\n"
        "$GPGSV,2,1,08,01,40,085,42,02,20,110,38,03,65,220,45,04,15,040,35*74\n"
        "$GPGSV,2,2,08,05,25,090,39,06,12,050,32,07,75,250,48,08,18,060,36*7D\n"
    )
    nmea_file = tmp_path / "test_log.nmea"
    nmea_file.write_text(nmea_content, encoding="utf-8")

    records = NativeGnssExtractor.parse_nmea_log(str(nmea_file), antenna_height_m=2.5)
    assert len(records) == 8
    # All records should reflect the RTK fixed status from the GGA sentence
    for rec in records:
        assert rec.constellation == "GPS"
        assert rec.rtk_fix_status == "FIXED"
        assert rec.antenna_height_m == 2.5
        assert rec.direct_snr_db_hz > 0.0

    # Verify fail-closed behavior on missing file
    with pytest.raises(FileNotFoundError):
        NativeGnssExtractor.parse_nmea_log(str(tmp_path / "non_existent.nmea"))


def test_public_cellular_survey_harness_evaluation():
    """Verify PublicCellularSurveyHarness calculates statistical network quality."""
    from services.agribrain.mesia.experiments.public_cellular_survey import PublicCellularSurveyHarness

    rsrp_samples = [-85.0, -88.0, -82.0, -90.0, -86.0]
    rsrq_samples = [-10.0, -11.5, -9.0, -12.0, -10.5]

    summary = PublicCellularSurveyHarness.run_operator_survey(
        survey_id="SURVEY_MOBILIS_01",
        operator="Mobilis",
        cell_id=4021,
        rsrp_samples=rsrp_samples,
        rsrq_samples=rsrq_samples,
        handovers=1,
    )

    assert summary.survey_id == "SURVEY_MOBILIS_01"
    assert summary.operator_name == "Mobilis"
    assert summary.mcc_mnc == "603-01"
    assert summary.mean_rsrp_dbm == -86.2
    assert summary.is_stable_for_context is True

    # Empty samples should fail closed
    with pytest.raises(ValueError):
        PublicCellularSurveyHarness.run_operator_survey(
            survey_id="EMPTY",
            operator="Mobilis",
            cell_id=1,
            rsrp_samples=[],
            rsrq_samples=[],
        )

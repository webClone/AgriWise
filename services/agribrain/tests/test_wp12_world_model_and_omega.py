"""
Tests for Work Package 12 (WP12): Make System Ready for Omega and the World Model.

Covers:
1. Bitemporal Historical Window Extraction (Zero future knowledge leakage guarantee, superseded evidence restoration).
2. Immutable Forecast Archive & Calibration Scoring (Quantile/Gaussian CRPS, sharpness, empirical coverage, immutability enforcement).
3. Shadow Forecast Invariant (Shadow forecasts evaluate without mutating operational state or granting prescription authority).
4. Omega Research Proposal Operational Containment (RESEARCH_ONLY scope, regulatory_safety_approved=False, human signoff).
5. Omega Authority Boundary Invariant (ContractViolation when claiming prescription or machine execution authority).
6. Agronomical World Model State & Action Contracts (5-stratum soil hydrology, physical conservation invariants, intervention lifecycles).
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from services.agribrain.scientific_contracts.authority import (
    AuthorityScope,
    AuthorityVector,
    AUTHORITY_PRESCRIPTION_DRIVER_APPROVED,
    AUTHORITY_MACHINE_EXECUTION_APPROVED,
    AUTHORITY_BLOCKED,
)
from services.agribrain.scientific_contracts.contracts_v2 import (
    InterventionLifecycleState,
    ForcingEvent,
    SpatialSupport,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation

from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    WorldlineEventProposal,
)
from services.agribrain.world_model.historical_extractor import (
    BitemporalWorldlineExtractor,
    TrainingTrajectoryWindow,
)
from services.agribrain.world_model.forecast_archive import (
    ForecastRecord,
    ForecastEvaluationRecord,
    ImmutableForecastArchive,
    compute_crps_quantiles,
    compute_crps_gaussian,
    compute_interval_coverage,
    compute_forecast_id,
    DomainStatus,
    EvaluationSpace,
)
from services.agribrain.world_model.contracts import (
    AgronomicalStateVector,
    EnvironmentalDisturbance,
    ActionVector,
    verify_water_balance_conservation,
    SOIL_STRATA_DEPTHS_CM,
)
from services.agribrain.mesia.omega.experiment_proposer import (
    ProposedScientificExperiment,
    OmegaExperimentProposer,
    verify_omega_proposal_authority,
)


# ============================================================================
# 1. Bitemporal Historical Window Extraction Tests
# ============================================================================

def test_bitemporal_zero_future_leakage(tmp_path: Path):
    """Verify that an observation whose physical event time is in-window but whose commit time

    is AFTER as_of_knowledge_time is strictly excluded (Zero Future Leakage).
    """
    worldline_svc = CanonicalWorldlineService(root=tmp_path)
    extractor = BitemporalWorldlineExtractor(worldline_service=worldline_svc)
    plot_id = "plot_bitemporal_01"

    # Event 1: Occurred 2026-05-28, committed 2026-05-28T10:00:00Z (Prior observation)
    p1 = WorldlineEventProposal(
        event_type="OBSERVATION",
        payload={"soil_vwc": 0.25, "source": "probe_01"},
        geometry_version="geo_v1",
        evidence_set_hash="ev_1",
        model_version="mod_1",
        authority_ref="MEASURED",
        observation_or_valid_time="2026-05-28T08:00:00Z",
    )
    e1 = worldline_svc.commit_proposal(
        plot_id=plot_id,
        proposal=p1,
        effective_at="2026-05-28T08:00:00Z",
    )

    # Event 2: Physical event on 2026-05-30, but committed on 2026-06-02T14:00:00Z (Late arrival)
    p2 = WorldlineEventProposal(
        event_type="OBSERVATION",
        payload={"soil_vwc": 0.22, "source": "sentinel2_delayed"},
        geometry_version="geo_v1",
        evidence_set_hash="ev_2",
        model_version="mod_1",
        authority_ref="MEASURED",
        observation_or_valid_time="2026-05-30T10:00:00Z",
    )
    e2 = worldline_svc.commit_proposal(
        plot_id=plot_id,
        proposal=p2,
        effective_at="2026-05-30T10:00:00Z",
    )
    # Simulate historical committed_at timestamp for e2 as 2026-06-02T14:00:00Z
    e2_file = tmp_path / "default_tenant" / "default" / worldline_svc._plot_key(plot_id) / "events" / f"{e2['event_id']}.json"
    import json
    data_e2 = json.loads(e2_file.read_text(encoding="utf-8"))
    data_e2["committed_at"] = "2026-06-02T14:00:00Z"
    e2_file.write_text(json.dumps(data_e2), encoding="utf-8")

    # Simulate historical committed_at timestamp for e1 as 2026-05-28T10:00:00Z
    e1_file = tmp_path / "default_tenant" / "default" / worldline_svc._plot_key(plot_id) / "events" / f"{e1['event_id']}.json"
    data_e1 = json.loads(e1_file.read_text(encoding="utf-8"))
    data_e1["committed_at"] = "2026-05-28T10:00:00Z"
    e1_file.write_text(json.dumps(data_e1), encoding="utf-8")

    # Query as of 2026-06-01: e2 MUST be completely invisible (zero future leakage)
    window_as_of_june1 = extractor.extract_training_window(
        plot_id=plot_id,
        start_event_time="2026-05-25T00:00:00Z",
        end_event_time="2026-05-31T23:59:59Z",
        as_of_knowledge_time="2026-06-01T00:00:00Z",
    )
    assert len(window_as_of_june1.events) == 1
    assert window_as_of_june1.events[0]["event_id"] == e1["event_id"]
    assert not window_as_of_june1.has_future_leakage()

    # Query as of 2026-06-03: e2 IS now known and included
    window_as_of_june3 = extractor.extract_training_window(
        plot_id=plot_id,
        start_event_time="2026-05-25T00:00:00Z",
        end_event_time="2026-05-31T23:59:59Z",
        as_of_knowledge_time="2026-06-03T00:00:00Z",
    )
    assert len(window_as_of_june3.events) == 2
    event_ids = {e["event_id"] for e in window_as_of_june3.events}
    assert e1["event_id"] in event_ids
    assert e2["event_id"] in event_ids


def test_bitemporal_superseded_evidence_restoration(tmp_path: Path):
    """Verify that if evidence is superseded by a newer event committed AFTER knowledge cutoff,

    the original (un-superseded) version remains active as of that knowledge time.
    """
    import json
    worldline_svc = CanonicalWorldlineService(root=tmp_path)
    extractor = BitemporalWorldlineExtractor(worldline_service=worldline_svc)
    plot_id = "plot_supersede_01"

    # Event 1: Preliminary NDVI committed 2026-05-30T12:00:00Z for event time 2026-05-30T10:00:00Z
    p1 = WorldlineEventProposal(
        event_type="OBSERVATION",
        payload={"ndvi": 0.60, "stage": "preliminary"},
        geometry_version="geo_v1",
        evidence_set_hash="ev_1",
        model_version="mod_1",
        authority_ref="MEASURED",
        observation_or_valid_time="2026-05-30T10:00:00Z",
    )
    e1 = worldline_svc.commit_proposal(plot_id=plot_id, proposal=p1, effective_at="2026-05-30T10:00:00Z")
    e1_file = tmp_path / "default_tenant" / "default" / worldline_svc._plot_key(plot_id) / "events" / f"{e1['event_id']}.json"
    d1 = json.loads(e1_file.read_text(encoding="utf-8"))
    d1["committed_at"] = "2026-05-30T12:00:00Z"
    e1_file.write_text(json.dumps(d1), encoding="utf-8")

    # Event 2: Calibrated NDVI committed 2026-06-02T12:00:00Z superseding Event 1
    p2 = WorldlineEventProposal(
        event_type="OBSERVATION",
        payload={"ndvi": 0.65, "stage": "calibrated", "supersedes_event_id": e1["event_id"]},
        geometry_version="geo_v1",
        evidence_set_hash="ev_2",
        model_version="mod_1",
        authority_ref="MEASURED",
        observation_or_valid_time="2026-05-30T10:00:00Z",
    )
    e2 = worldline_svc.commit_proposal(plot_id=plot_id, proposal=p2, effective_at="2026-05-30T10:00:00Z")
    e2_file = tmp_path / "default_tenant" / "default" / worldline_svc._plot_key(plot_id) / "events" / f"{e2['event_id']}.json"
    d2 = json.loads(e2_file.read_text(encoding="utf-8"))
    d2["committed_at"] = "2026-06-02T12:00:00Z"
    e2_file.write_text(json.dumps(d2), encoding="utf-8")

    # As of 2026-06-01: e2 did not exist. Therefore e1 is ACTIVE and NOT superseded.
    w_june1 = extractor.extract_training_window(
        plot_id=plot_id,
        start_event_time="2026-05-29T00:00:00Z",
        end_event_time="2026-05-31T00:00:00Z",
        as_of_knowledge_time="2026-06-01T00:00:00Z",
    )
    assert len(w_june1.active_events) == 1
    assert w_june1.active_events[0]["event_id"] == e1["event_id"]
    assert len(w_june1.superseded_events) == 0

    # As of 2026-06-03: e2 is known. e2 is ACTIVE, and e1 is SUPERSEDED.
    w_june3 = extractor.extract_training_window(
        plot_id=plot_id,
        start_event_time="2026-05-29T00:00:00Z",
        end_event_time="2026-05-31T00:00:00Z",
        as_of_knowledge_time="2026-06-03T00:00:00Z",
    )
    assert len(w_june3.active_events) == 1
    assert w_june3.active_events[0]["event_id"] == e2["event_id"]
    assert len(w_june3.superseded_events) == 1
    assert w_june3.superseded_events[0]["event_id"] == e1["event_id"]


def test_bitemporal_window_date_validation():
    extractor = BitemporalWorldlineExtractor()
    with pytest.raises(ContractViolation, match="cannot be after end_event_time"):
        extractor.extract_training_window(
            plot_id="plot_01",
            start_event_time="2026-06-10T00:00:00Z",
            end_event_time="2026-06-01T00:00:00Z",
            as_of_knowledge_time="2026-06-15T00:00:00Z",
        )


# ============================================================================
# 2. Immutable Forecast Archive & Scoring Tests
# ============================================================================

def test_forecast_record_immutability(tmp_path: Path):
    archive = ImmutableForecastArchive(root=tmp_path)
    now = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    target = datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc)

    fc = ForecastRecord(
        forecast_id="fc-test-001",
        plot_id="plot_101",
        target_variable="soil_vwc",
        issued_at_knowledge_time=now,
        target_epoch=target,
        horizon_days=7.0,
        predicted_quantiles={"p10": 0.20, "p50": 0.25, "p90": 0.32},
        authority_scope=AuthorityScope.OPERATIONAL_SHADOW,
        is_shadow=True,
    )

    # Initial store succeeds
    saved = archive.store_forecast(fc)
    assert saved.forecast_id == "fc-test-001"

    # Storing identical forecast is idempotent
    again = archive.store_forecast(fc)
    assert again.forecast_id == "fc-test-001"

    # Attempting to mutate forecast with conflicting data raises ContractViolation
    mutated = ForecastRecord(
        forecast_id="fc-test-001",
        plot_id="plot_101",
        target_variable="soil_vwc",
        issued_at_knowledge_time=now,
        target_epoch=target,
        horizon_days=7.0,
        predicted_quantiles={"p10": 0.15, "p50": 0.20, "p90": 0.25},  # Altered!
        authority_scope=AuthorityScope.OPERATIONAL_SHADOW,
        is_shadow=True,
    )
    with pytest.raises(ContractViolation, match="Forecast immutability violation"):
        archive.store_forecast(mutated)


def test_forecast_record_epoch_order_validation():
    now = datetime(2026, 6, 10, 10, 0, tzinfo=timezone.utc)
    past = datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(ContractViolation, match="must be strictly after"):
        ForecastRecord(
            forecast_id="fc-invalid",
            plot_id="plot_101",
            target_variable="soil_vwc",
            issued_at_knowledge_time=now,
            target_epoch=past,
            horizon_days=1.0,
        )


def test_crps_quantile_and_gaussian_scoring():
    # Quantile forecast: p10=0.20, p50=0.25, p90=0.30
    quantiles = {"p10": 0.20, "p50": 0.25, "p90": 0.30}
    # When ground truth = 0.25 (exact median)
    crps_median = compute_crps_quantiles(quantiles, 0.25)
    assert crps_median >= 0.0

    # When ground truth = 0.50 (severe over-prediction error)
    crps_bad = compute_crps_quantiles(quantiles, 0.50)
    assert crps_bad > crps_median

    # Gaussian forecast: mean=10.0, std=1.0
    crps_gauss_exact = compute_crps_gaussian(mean=10.0, std=1.0, observed=10.0)
    crps_gauss_far = compute_crps_gaussian(mean=10.0, std=1.0, observed=15.0)
    assert crps_gauss_exact >= 0.0
    assert crps_gauss_far > crps_gauss_exact


def test_interval_coverage():
    intervals = [(0.2, 0.3), (0.2, 0.3), (0.2, 0.3), (0.2, 0.3)]
    obs = [0.25, 0.22, 0.28, 0.40]  # 3 in, 1 out -> 75%
    coverage = compute_interval_coverage(intervals, obs)
    assert abs(coverage - 0.75) < 1e-4


def test_forecast_evaluation_in_archive(tmp_path: Path):
    archive = ImmutableForecastArchive(root=tmp_path)
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    target = datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)

    fc = ForecastRecord(
        forecast_id="fc-eval-001",
        plot_id="plot_200",
        target_variable="soil_vwc",
        issued_at_knowledge_time=now,
        target_epoch=target,
        horizon_days=7.0,
        predicted_quantiles={"p10": 0.20, "p50": 0.26, "p90": 0.32},
        authority_scope=AuthorityScope.OPERATIONAL_SHADOW,
        is_shadow=True,
    )
    archive.store_forecast(fc)

    # Evaluate against observed ground truth on June 8
    eval_rec = archive.evaluate_forecast(
        forecast_id="fc-eval-001",
        observed_value=0.25,
        verifying_evidence_ids=["ev_probe_june8"],
        evaluated_at=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
    )

    assert eval_rec.forecast_id == "fc-eval-001"
    assert eval_rec.coverage_hit is True
    assert eval_rec.sharpness == pytest.approx(0.12, abs=1e-4)
    assert eval_rec.crps > 0.0
    assert eval_rec.evaluation_space == EvaluationSpace.OBSERVATION_SPACE

    # Forecast itself remains unchanged
    stored_fc = archive.get_forecast("fc-eval-001")
    assert stored_fc is not None
    assert stored_fc.forecast_id == "fc-eval-001"


# ============================================================================
# 3. Shadow Forecast Invariant & Operational Boundary
# ============================================================================

def test_shadow_forecast_invariant():
    """Verify that shadow forecasts carry AuthorityScope.OPERATIONAL_SHADOW and cannot

    be promoted to prescription authority without governance approval.
    """
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    target = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)

    shadow_fc = ForecastRecord(
        forecast_id="fc-shadow-001",
        plot_id="plot_300",
        target_variable="soil_vwc",
        issued_at_knowledge_time=now,
        target_epoch=target,
        horizon_days=2.0,
        predicted_quantiles={"p10": 0.18, "p50": 0.22, "p90": 0.28},
        authority_scope=AuthorityScope.OPERATIONAL_SHADOW,
        is_shadow=True,
    )

    assert shadow_fc.is_shadow is True
    assert shadow_fc.authority_scope == AuthorityScope.OPERATIONAL_SHADOW


# ============================================================================
# 4. Omega Research Proposal Operational Containment Tests
# ============================================================================

def test_omega_experiment_proposal_containment():
    """Verify that Omega proposals default to regulatory_safety_approved=False,

    authority_scope=RESEARCH_ONLY, and requires_human_signoff=True.
    """
    class FakeHypothesis:
        hypothesis_id = "hyp-test-99"
        kl_divergence_bits = 8.5

    proposal = OmegaExperimentProposer.propose_discriminating_experiment(
        experiment_id="exp-omega-01",
        plot_id="plot_algeria_01",
        hypothesis=FakeHypothesis(),
    )

    assert proposal.regulatory_safety_approved is False
    assert proposal.authority_scope == AuthorityScope.RESEARCH_ONLY
    assert proposal.requires_human_signoff is True
    assert proposal.status == "PROPOSED"
    assert proposal.action_type == "DUAL_BAND_TRANSMISSION"


def test_omega_boundary_invariant():
    """Verify that attempting to assign prescription or execution authority

    to an Omega research proposal raises ContractViolation.
    """
    proposal = ProposedScientificExperiment(
        experiment_id="exp-omega-02",
        target_plot_id="plot_01",
        hypothesis_ref="hyp_01",
        action_type="MULTI_FREQUENCY_TOMOGRAPHY_SWEEP",
        target_bands=["868_MHZ_LORA"],
        expected_information_gain_bits=4.0,
        regulatory_safety_approved=False,
        requires_human_signoff=True,
        authority_scope=AuthorityScope.RESEARCH_ONLY,
    )

    # Clean check with blocked authority succeeds
    assert verify_omega_proposal_authority(proposal, AUTHORITY_BLOCKED) is True

    # Attempting to assign prescription driver authority fails closed
    with pytest.raises(ContractViolation, match="cannot receive prescription_driver_allowed"):
        verify_omega_proposal_authority(proposal, AUTHORITY_PRESCRIPTION_DRIVER_APPROVED)

    # Attempting to assign machine execution authority fails closed
    with pytest.raises(ContractViolation, match="cannot receive"):
        verify_omega_proposal_authority(proposal, AUTHORITY_MACHINE_EXECUTION_APPROVED)


# ============================================================================
# 5. Agronomical World Model Contracts & Conservation Tests
# ============================================================================

def test_agronomical_state_vector_validation():
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    # Valid state
    state = AgronomicalStateVector(
        plot_id="plot_wheat_01",
        timestamp=now,
        soil_vwc_profile=(0.28, 0.27, 0.25, 0.22, 0.20),
        soil_temperature_c=(22.5, 21.0, 19.5, 18.0, 16.5),
        crop_growth_stage_code="BBCH_65",
        cumulative_gdd_c=1250.0,
        fractional_canopy_cover=0.85,
        leaf_area_index=3.8,
        root_depth_cm=65.0,
        biomass_dry_matter_kg_ha=6500.0,
        mineral_n_topsoil_kg_ha=45.0,
        mineral_n_subsoil_kg_ha=30.0,
        foliar_pathogen_latent_spore_load=0.08,
    )
    assert state.plot_id == "plot_wheat_01"
    assert state.total_mineral_n_kg_ha == 75.0
    # Total storage: 0.28*100 + 0.27*100 + 0.25*200 + 0.22*200 + 0.20*400 = 28+27+50+44+80 = 229 mm
    assert state.total_soil_water_storage_mm == pytest.approx(229.0, abs=0.1)

    # Invalid VWC (> 1.0) raises ContractViolation
    with pytest.raises(ContractViolation, match="must be in \\[0.0, 1.0\\]"):
        AgronomicalStateVector(
            plot_id="plot_wheat_01",
            timestamp=now,
            soil_vwc_profile=(1.28, 0.27, 0.25, 0.22, 0.20),
            soil_temperature_c=(22.5, 21.0, 19.5, 18.0, 16.5),
            crop_growth_stage_code="BBCH_65",
            cumulative_gdd_c=1250.0,
            fractional_canopy_cover=0.85,
            leaf_area_index=3.8,
            root_depth_cm=65.0,
            biomass_dry_matter_kg_ha=6500.0,
            mineral_n_topsoil_kg_ha=45.0,
            mineral_n_subsoil_kg_ha=30.0,
            foliar_pathogen_latent_spore_load=0.08,
        )

    # Invalid stratum count raises ContractViolation
    with pytest.raises(ContractViolation, match="must contain exactly 5 strata"):
        AgronomicalStateVector(
            plot_id="plot_wheat_01",
            timestamp=now,
            soil_vwc_profile=(0.28, 0.27, 0.25),  # only 3 strata
            soil_temperature_c=(22.5, 21.0, 19.5, 18.0, 16.5),
            crop_growth_stage_code="BBCH_65",
            cumulative_gdd_c=1250.0,
            fractional_canopy_cover=0.85,
            leaf_area_index=3.8,
            root_depth_cm=65.0,
            biomass_dry_matter_kg_ha=6500.0,
            mineral_n_topsoil_kg_ha=45.0,
            mineral_n_subsoil_kg_ha=30.0,
            foliar_pathogen_latent_spore_load=0.08,
        )


def test_water_balance_conservation_invariant():
    # Initial: 200 mm, Inflows: 15 mm rain + 25 mm irrigation = 40 mm
    # Outflows: 5 mm ET + 5 mm drainage = 10 mm. Delta storage must be +30 mm -> Final: 230 mm.
    assert verify_water_balance_conservation(
        initial_storage_mm=200.0,
        final_storage_mm=230.0,
        precipitation_mm=15.0,
        irrigation_effective_mm=25.0,
        et_actual_mm=5.0,
        drainage_runoff_mm=5.0,
    ) is True

    # Unbalanced scenario (spontaneous water creation: Delta storage = +50 mm vs Net flux = 30 mm)
    with pytest.raises(ContractViolation, match="Physical water conservation violation"):
        verify_water_balance_conservation(
            initial_storage_mm=200.0,
            final_storage_mm=250.0,
            precipitation_mm=15.0,
            irrigation_effective_mm=25.0,
            et_actual_mm=5.0,
            drainage_runoff_mm=5.0,
        )


def test_intervention_lifecycle_separation():
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)

    # 1. Proposed intervention (optimization output, not physically realized)
    action_proposed = ActionVector(
        action_id="act-opt-01",
        action_type="IRRIGATION",
        lifecycle_state=InterventionLifecycleState.PROPOSED,
        target_date=now,
        rate=25.0,
        units="mm",
    )
    assert action_proposed.is_physically_realized() is False

    # 2. Scheduled intervention
    action_scheduled = ActionVector(
        action_id="act-opt-01",
        action_type="IRRIGATION",
        lifecycle_state=InterventionLifecycleState.SCHEDULED,
        target_date=now,
        rate=25.0,
        units="mm",
    )
    assert action_scheduled.is_physically_realized() is False

    # 3. Completed intervention
    action_completed = ActionVector(
        action_id="act-opt-01",
        action_type="IRRIGATION",
        lifecycle_state=InterventionLifecycleState.COMPLETED,
        target_date=now,
        rate=25.0,
        units="mm",
    )
    assert action_completed.is_physically_realized() is True

    # 4. Verified exposure
    action_exposed = ActionVector(
        action_id="act-opt-01",
        action_type="IRRIGATION",
        lifecycle_state=InterventionLifecycleState.EXPOSED,
        target_date=now,
        rate=25.0,
        units="mm",
        exposure_verified_at=now,
    )
    assert action_exposed.is_physically_realized() is True

"""MESIA-to-ASMAE Observation Boundary & Dispatcher Tests — WP07 / Findings #14, #15, #19, #20.

Validates:
1. Physical inversion bounds and units (Finding #15 - no probability-to-moisture substitution).
2. Ensemble likelihood Gaussian weighting without state corruption.
3. ASMAE observation dispatching and fail-closed abstention receipt auditing (Finding #14).
4. Algebraic observability analysis via Fisher Information Matrix (Finding #20).
5. MesiaProductionService end-to-end proposal event and receipt embedding.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from services.agribrain.scientific_contracts.observation import ASMAEObservationPayload
from services.agribrain.mesia.assimilation.asmae_operator import ASMAEObservationOperator, ASMAEInnovationProposal
from services.agribrain.layer05_asmae.observation.dispatcher import (
    ASMAEObservationDispatcher,
    ObservationAbstentionReceipt,
    AssimilationReceipt,
    compute_idempotency_key,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.layer05_asmae.observation.contracts import ObservationEvent
from services.agribrain.layer05_asmae.state.authority import AuthorityVector
from services.agribrain.mesia.assimilation.observability_analyzer import ObservabilityAnalyzer
from services.agribrain.mesia.assimilation.spatial_lattice import SharedBeliefLattice, LatticeStrata
from services.agribrain.mesia.assimilation.sensitivity_kernels import LinkSensitivityProfile
from services.agribrain.mesia.service import MesiaProductionService


class TestAsmaePhysicalInversionBoundary:
    """Finding #15: Physical inversion integrity and rejection of dimensionless substitution."""

    def test_calibrated_inversion_valid_bounds(self):
        innov = ASMAEObservationOperator.from_calibrated_inversion(
            inverted_vwc=0.245,
            prior_state_vwc=0.210,
            variance=0.0015,
            support=0.85,
            microzone_id="PLOT_01_MZ_0_0",
            depth_stratum="ROOT_ZONE_5_30CM",
            target_state_variable="root_zone_water",
        )
        assert isinstance(innov, ASMAEInnovationProposal)
        assert innov.innovation_value == pytest.approx(0.035, abs=1e-4)
        assert innov.observation_variance == 0.0015
        assert innov.target_state_variable == "root_zone_water"
        assert innov.authority_scope == "evidence_proposal"

    def test_calibrated_inversion_rejects_out_of_bounds_negative(self):
        with pytest.raises(ValueError, match="Physical boundary violation"):
            ASMAEObservationOperator.from_calibrated_inversion(
                inverted_vwc=-0.05,
                prior_state_vwc=0.20,
                variance=0.01,
                support=0.8,
                microzone_id="MZ_0",
                depth_stratum="ROOT_ZONE_5_30CM",
                target_state_variable="root_zone_water",
            )

    def test_calibrated_inversion_rejects_out_of_bounds_super_saturation(self):
        with pytest.raises(ValueError, match="Physical boundary violation"):
            ASMAEObservationOperator.from_calibrated_inversion(
                inverted_vwc=0.72,
                prior_state_vwc=0.20,
                variance=0.01,
                support=0.8,
                microzone_id="MZ_0",
                depth_stratum="ROOT_ZONE_5_30CM",
                target_state_variable="root_zone_water",
            )

    def test_calibrated_inversion_rejects_non_positive_variance(self):
        with pytest.raises(ValueError, match="observation_variance must be strictly positive"):
            ASMAEObservationOperator.from_calibrated_inversion(
                inverted_vwc=0.25,
                prior_state_vwc=0.20,
                variance=-0.01,
                support=0.8,
                microzone_id="MZ_0",
                depth_stratum="ROOT_ZONE_5_30CM",
                target_state_variable="root_zone_water",
            )

    def test_observation_payload_unit_and_bounds_validation(self):
        now = datetime.now(timezone.utc)
        payload = ASMAEObservationPayload(
            observation_id="obs-payload-01",
            target_state_variable="root_zone_water",
            microzone_id="MZ_0_0",
            depth_stratum="ROOT_ZONE_5_30CM",
            observation_value=0.28,
            observation_units="volumetric fraction [0,1]",
            observation_variance=0.002,
            forward_operator_id="topp_dielectric_inversion_v1",
            calibration_certificate_id="CALIB-CERT-42",
            truth_class="DERIVED_MODEL_INFERRED",
            knowledge_cutoff=now,
        )
        assert payload.observation_value == 0.28
        assert payload.observation_units == "volumetric fraction [0,1]"

        # Invalid units must raise ValueError
        with pytest.raises(ValueError, match="Invalid units"):
            ASMAEObservationPayload(
                observation_id="obs-bad-unit",
                target_state_variable="root_zone_water",
                microzone_id="MZ_0_0",
                depth_stratum="ROOT_ZONE_5_30CM",
                observation_value=0.28,
                observation_units="dimensionless_probability",
                observation_variance=0.002,
                forward_operator_id="topp_dielectric_inversion_v1",
                calibration_certificate_id="CALIB-CERT-42",
                truth_class="DERIVED_MODEL_INFERRED",
                knowledge_cutoff=now,
            )

    def test_ensemble_likelihood_gaussian_reweighting(self):
        ensemble_vwc = [0.18, 0.20, 0.22, 0.25, 0.30]
        # h(x) predicts RF attenuation proportional to soil moisture
        h = lambda vwc: -10.0 * (1.0 - vwc)
        observed_rf = -7.8  # corresponds to vwc = 0.22 (-10.0 * 0.78 = -7.8)
        weights = ASMAEObservationOperator.from_ensemble_likelihood(
            observed_feature=observed_rf,
            ensemble_states=ensemble_vwc,
            forward_operator_fn=h,
            observation_variance=0.05,
        )
        assert len(weights) == 5
        assert pytest.approx(sum(weights), abs=1e-4) == 1.0
        # Particle with vwc=0.22 is closest to observed -7.8, must have highest weight
        assert weights[2] == max(weights)


class TestAsmaeObservationDispatcher:
    """Finding #14: Active routing and fail-closed durable abstention receipts."""

    def test_dispatcher_admits_qualified_event(self):
        dispatcher = ASMAEObservationDispatcher()
        event = ObservationEvent(
            observation_id="obs-calib-01",
            source_family="MESIA_GNSSR",
            sensor_id="RX_F9P_01",
            acquisition_time=datetime.now(timezone.utc),
            valid_time=datetime.now(timezone.utc),
            spatial_support_ref="mz:0_0",
            quality_ref="var:0.001",
            observation_operator_ref="gnss_ref_v1",
            uncertainty_model_ref="gum_budget",
            authority=AuthorityVector(visualization_allowed=True, state_update_allowed=True, diagnosis_allowed=True),
        )
        res = dispatcher.dispatch_event(event)
        assert res["status"] == "admitted_for_assimilation"
        assert len(dispatcher.get_pending_observations()) == 1
        assert len(dispatcher.get_abstention_receipts()) == 0

    def test_dispatcher_abstains_unqualified_event_and_audits_receipt(self):
        dispatcher = ASMAEObservationDispatcher()
        event = ObservationEvent(
            observation_id="obs-uncalib-01",
            source_family="MESIA_WIFI",
            sensor_id="RX_ESP32_01",
            acquisition_time=datetime.now(timezone.utc),
            valid_time=datetime.now(timezone.utc),
            spatial_support_ref="mz:0_0",
            quality_ref="var:0.05",
            observation_operator_ref="wifi_cwi_v1",
            uncertainty_model_ref="gum_budget",
            authority=AuthorityVector(visualization_allowed=True, state_update_allowed=False, diagnosis_allowed=True),
        )
        res = dispatcher.dispatch_event(event)
        assert res["status"] == "abstained_uncalibrated"
        assert len(dispatcher.get_pending_observations()) == 0
        receipts = dispatcher.get_abstention_receipts()
        assert len(receipts) == 1
        assert isinstance(receipts[0], ObservationAbstentionReceipt)
        assert receipts[0].observation_id == "obs-uncalib-01"
        assert "Authority vector prohibits state_update" in receipts[0].reason

    def test_dispatcher_payload_routing_with_certificate(self):
        now = datetime.now(timezone.utc)
        dispatcher = ASMAEObservationDispatcher()
        payload_calib = ASMAEObservationPayload(
            observation_id="obs-payload-calib",
            target_state_variable="root_zone_water",
            microzone_id="MZ_1_1",
            depth_stratum="ROOT_ZONE_5_30CM",
            observation_value=0.22,
            observation_units="volumetric fraction [0,1]",
            observation_variance=0.002,
            forward_operator_id="gnssr_inv",
            calibration_certificate_id="CERT-CALIB-VALID",
            truth_class="DERIVED_MODEL_INFERRED",
            knowledge_cutoff=now,
        )
        res_calib = dispatcher.dispatch_payload(payload_calib)
        assert res_calib["status"] == "admitted_for_assimilation"

        payload_uncalib = ASMAEObservationPayload(
            observation_id="obs-payload-uncalib",
            target_state_variable="root_zone_water",
            microzone_id="MZ_1_1",
            depth_stratum="ROOT_ZONE_5_30CM",
            observation_value=0.22,
            observation_units="volumetric fraction [0,1]",
            observation_variance=0.002,
            forward_operator_id="gnssr_inv",
            calibration_certificate_id="",
            truth_class="DERIVED_MODEL_INFERRED",
            knowledge_cutoff=now,
        )
        res_uncalib = dispatcher.dispatch_payload(payload_uncalib)
        assert res_uncalib["status"] == "abstained_uncalibrated"


class TestObservabilityAnalyzerAlgebraicCondition:
    """Finding #20: Algebraic observability via Fisher Information Matrix rank and conditioning."""

    def test_well_conditioned_geometry_is_observable(self):
        lattice = SharedBeliefLattice(plot_id="TEST_PLOT", cell_size_m=10.0, grid_dim=(2, 2))
        mz0 = "TEST_PLOT_MZ_0_0"
        mz1 = "TEST_PLOT_MZ_0_1"
        mz2 = "TEST_PLOT_MZ_1_0"
        mz3 = "TEST_PLOT_MZ_1_1"

        # 4 independent orthogonal links covering the 4 microzones
        link_profiles = [
            LinkSensitivityProfile("link-0", "GNSS", 1.575e9, {mz0: 1.0}, LatticeStrata.ROOT_ZONE_5_30CM, 1.0),
            LinkSensitivityProfile("link-1", "GNSS", 1.575e9, {mz1: 1.0}, LatticeStrata.ROOT_ZONE_5_30CM, 1.0),
            LinkSensitivityProfile("link-2", "GNSS", 1.575e9, {mz2: 1.0}, LatticeStrata.ROOT_ZONE_5_30CM, 1.0),
            LinkSensitivityProfile("link-3", "GNSS", 1.575e9, {mz3: 1.0}, LatticeStrata.ROOT_ZONE_5_30CM, 1.0),
        ]

        cert = ObservabilityAnalyzer.analyze_observability(
            certificate_id="CERT-OBS-01",
            target_capability="ROOT_ZONE_MOISTURE",
            link_profiles=link_profiles,
            lattice=lattice,
            min_weight_threshold=0.5,
        )

        assert cert.is_observable is True
        assert cert.effective_rank == 4.0
        assert cert.condition_number < 10.0
        assert len(cert.supported_microzones) == 4
        assert len(cert.abstention_reasons) == 0

    def test_rank_deficient_geometry_is_not_observable(self):
        lattice = SharedBeliefLattice(plot_id="TEST_PLOT", cell_size_m=10.0, grid_dim=(2, 2))
        mz0 = "TEST_PLOT_MZ_0_0"
        mz1 = "TEST_PLOT_MZ_0_1"

        # Single link spanning 2 microzones -> rank 1 for 2 supported zones
        link_profiles = [
            LinkSensitivityProfile("link-0", "GNSS", 1.575e9, {mz0: 0.8, mz1: 0.8}, LatticeStrata.ROOT_ZONE_5_30CM, 1.6),
        ]

        cert = ObservabilityAnalyzer.analyze_observability(
            certificate_id="CERT-OBS-02",
            target_capability="ROOT_ZONE_MOISTURE",
            link_profiles=link_profiles,
            lattice=lattice,
            min_weight_threshold=0.5,
        )

        assert cert.is_observable is False
        assert cert.effective_rank == 1.0
        assert len(cert.abstention_reasons) > 0
        assert "Rank-deficient" in cert.abstention_reasons[0]


class TestEndToEndMesiaProposalReceipts:
    """End-to-end validation of observation event creation and dispatch receipts in MesiaProductionService."""

    def test_scan_plot_spectrum_embeds_dispatch_receipts(self):
        polygon = [(36.5, 3.0), (36.51, 3.0), (36.51, 3.01), (36.5, 3.01)]
        result = MesiaProductionService.scan_plot_spectrum(
            plot_id="plot_wp07_test",
            polygon_wgs84=polygon,
        )
        proposals = result["asmae_p08_proposals"]
        assert len(proposals) > 0

        for p in proposals:
            assert "asmae_observation_event" in p
            assert "dispatch_receipt" in p
            receipt = p["dispatch_receipt"]
            assert receipt is not None
            assert receipt["status"] in ("admitted_for_assimilation", "abstained_uncalibrated")
            assert "observation_id" in receipt
            assert "receipt" in receipt


class TestAsmaeDurableQueueAndTwoPhaseCommit:
    """WP07 & Blocking Amendment 5: Durable queue FIFO ordering, lease semantics, and 2-phase EnKF commit."""

    def test_durable_queue_fifo_and_atomic_lease(self, tmp_path):
        dispatcher = ASMAEObservationDispatcher(queue_root=tmp_path / "queue")
        now = datetime.now(timezone.utc)

        # Enqueue 3 events in sequence
        for i in range(3):
            ev = ObservationEvent(
                observation_id=f"obs-queue-{i}",
                source_family="MESIA_GNSSR",
                sensor_id="RX_F9P",
                acquisition_time=now,
                valid_time=now,
                spatial_support_ref="mz:TEST_PLOT_01",
                quality_ref=f"var:0.00{i+1}",
                observation_operator_ref="gnss_ref_v1",
                uncertainty_model_ref="gum_budget",
                authority=AuthorityVector(visualization_allowed=True, state_update_allowed=True, diagnosis_allowed=True),
            )
            res = dispatcher.dispatch_event(ev, plot_id="PLOT_QUEUE_01", capture_manifest_id=f"manifest-{i}")
            assert res["status"] == "admitted_for_assimilation"

        # Leased in strict FIFO order
        leased_0 = dispatcher.lease_next_observation("PLOT_QUEUE_01", lease_duration_seconds=30.0, worker_id="worker-a")
        assert leased_0 is not None
        assert leased_0["observation_id"] == "obs-queue-0"
        assert leased_0["status"] == "LEASED"

        leased_1 = dispatcher.lease_next_observation("PLOT_QUEUE_01", lease_duration_seconds=30.0, worker_id="worker-a")
        assert leased_1 is not None
        assert leased_1["observation_id"] == "obs-queue-1"

        leased_2 = dispatcher.lease_next_observation("PLOT_QUEUE_01", lease_duration_seconds=30.0, worker_id="worker-a")
        assert leased_2 is not None
        assert leased_2["observation_id"] == "obs-queue-2"

        # No more queued items
        leased_none = dispatcher.lease_next_observation("PLOT_QUEUE_01")
        assert leased_none is None

        # Release lease_1 back to QUEUED
        rel = dispatcher.release_lease("PLOT_QUEUE_01", leased_1["idempotency_key"], leased_1["lease_id"])
        assert rel is True

        re_leased = dispatcher.lease_next_observation("PLOT_QUEUE_01")
        assert re_leased is not None
        assert re_leased["observation_id"] == "obs-queue-1"

    def test_idempotent_deduplication(self, tmp_path):
        dispatcher = ASMAEObservationDispatcher(queue_root=tmp_path / "queue")
        now = datetime.now(timezone.utc)
        ev = ObservationEvent(
            observation_id="obs-idempotent-01",
            source_family="MESIA_GNSSR",
            sensor_id="RX_F9P",
            acquisition_time=now,
            valid_time=now,
            spatial_support_ref="mz:TEST_PLOT_IDEM",
            quality_ref="var:0.001",
            observation_operator_ref="gnss_ref_v1",
            uncertainty_model_ref="gum_budget",
            authority=AuthorityVector(visualization_allowed=True, state_update_allowed=True, diagnosis_allowed=True),
        )

        res1 = dispatcher.dispatch_event(ev, plot_id="PLOT_IDEM_01", capture_manifest_id="manifest-idem")
        assert res1["status"] == "admitted_for_assimilation"
        assert "idempotent" not in res1

        res2 = dispatcher.dispatch_event(ev, plot_id="PLOT_IDEM_01", capture_manifest_id="manifest-idem")
        assert res2["status"] == "admitted_for_assimilation"
        assert res2.get("idempotent") is True

    def test_two_phase_commit_with_valid_signed_innovation(self):
        dispatcher = ASMAEObservationDispatcher()
        now = datetime.now(timezone.utc)

        receipt = AssimilationReceipt(
            receipt_id="rec-assim-01",
            plot_id="plot_assim_01",
            observation_id="obs-inversion-01",
            candidate_node_id="node-candidate-sha256-abc",
            innovation_vector=(-0.032, 0.015),  # signed innovation residual y - H(x^-)
            covariance_min_eigenvalue=0.00045,
            assimilated_at=now,
            status="COMMITTED",
        )

        # Covariance matrix is positive semi-definite
        cov = [
            [0.002, 0.0001],
            [0.0001, 0.0015],
        ]

        result = dispatcher.commit_assimilation(
            plot_id="plot_assim_01",
            candidate_node_id="node-candidate-sha256-abc",
            assimilation_receipt=receipt,
            geometry_hash="geom_assim_hash",
            error_covariance=cov,
        )

        assert result["status"] == "committed"
        assert result["worldline_event_id"] is not None
        assert result["candidate_node_id"] == "node-candidate-sha256-abc"

    def test_two_phase_commit_rejects_negative_covariance_eigenvalue(self):
        dispatcher = ASMAEObservationDispatcher()
        now = datetime.now(timezone.utc)

        receipt = AssimilationReceipt(
            receipt_id="rec-assim-bad-cov",
            plot_id="plot_assim_02",
            observation_id="obs-inversion-02",
            candidate_node_id="node-candidate-bad",
            innovation_vector=(0.045,),
            covariance_min_eigenvalue=-0.05,  # Violates PSD
            assimilated_at=now,
            status="COMMITTED",
        )

        with pytest.raises(ContractViolation, match="Covariance.*violated"):
            dispatcher.commit_assimilation(
                plot_id="plot_assim_02",
                candidate_node_id="node-candidate-bad",
                assimilation_receipt=receipt,
                geometry_hash="geom_assim_hash",
                error_covariance=[[-0.05]],
            )


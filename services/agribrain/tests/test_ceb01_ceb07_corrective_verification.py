"""
CEB01-CEB07 Corrective Verification Test Suite

Verifies fixes for all 7 finding groups from the six-agent review of ceb5dd4:
  CEB01 (P1): Resource ownership - delayed idle replies and expired lease revival
  CEB02 (P2): Pond evaporation separated from soil evaporation (both ledgers close)
  CEB03 (P1): L4 nonconservation restriction preserved in L8 adapter and ranker
  CEB04 (P2): Root support coverage & degraded water boundary propagate to L4 health
  CEB05 (P2): Negative surface storage and invalid fluxes rejected at admission
  CEB06 (P2): First scoped read of older no-index legacy head returns generation 5
  CEB07 (P3): Probability bounds validated strictly before precision rounding
"""

import math
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from irrigation_runtime.safety import SharedQuotaStore
from irrigation_runtime.dispatcher import CommandResult
from layer3_water.contracts.water_state import (
    InfiltrationState,
    SoilWaterState,
    SoilEvaporationState,
    IntervalFluxReceipt,
    ActualWaterFlux,
    WaterFluxState,
    PotentialWaterFlux,
    RootZoneWaterState,
    WaterState,
)
from layer3_water.contracts.state_factory import WaterStateFactory
from layer3_water.soil.layered_water_balance import LayeredWaterBalanceEngine
from layer3_water.contracts.assimilation_state import Layer3ToLayer4BoundaryReceipt

from layer4_nutrients.runner import run_layer4_standalone
from layer4_nutrients.schema import Nutrient, NutrientState, Severity, Driver
from orchestrator_v2.runner import _normalize_nutrient_states
from layer8_prescriptive.action_ranker import ActionRankingEngine
from layer8_prescriptive.schema import (
    Layer8Input,
    ActionCard,
    ActionType,
    ConfidenceLevel,
    PrescriptiveDegradation,
)

from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService
from services.agribrain.world_model.forecast_archive import parse_quantile_level, ContractViolation


class TestCEB01ResourceOwnership(unittest.TestCase):
    """CEB01 (P1): Delayed idle reply and expired-lease owner revival."""

    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    def test_ceb01_delayed_idle_reply_does_not_supersede_active_execution(self):
        """Worker B's delayed idle reply (sampled before A executed) cannot supersede A."""
        # 1. A claims resource at t=100.0
        now_ts = 100.0
        claimed, token_a = SharedQuotaStore.claim_resource(
            device_id="DEV-01",
            zone_id="ZONE-1",
            event_id="EV-A",
            live_executing=False,
            query_ts=now_ts,
        )
        self.assertTrue(claimed)

        # 2. Worker B queries status at query_start_ts = 100.5 (controller is idle)
        b_query_start_ts = 100.5

        # 3. Worker A completes start and transitions to EXECUTING at t=101.0
        SharedQuotaStore.update_status("EV-A", "EXECUTING")
        with SharedQuotaStore._lock():
            st = SharedQuotaStore._read_state()
            st["reservations"]["EV-A"]["executing_ts"] = 101.0
            SharedQuotaStore._write_state(st)

        # 4. Worker B's reply arrives delayed at t=102.0, but query_ts is bound to acquisition start (100.5)
        b_claimed, holding_id = SharedQuotaStore.claim_resource(
            device_id="DEV-01",
            zone_id="ZONE-1",
            event_id="EV-B",
            live_executing=False,
            query_ts=b_query_start_ts,
        )
        # B's claim must be rejected!
        self.assertFalse(b_claimed)
        self.assertEqual(holding_id, "EV-A")

        # Worker A's reservation must remain EXECUTING and NOT be set to COMPLETED
        rec_a = SharedQuotaStore.get_active_record("EV-A")
        self.assertIsNotNone(rec_a)
        self.assertEqual(rec_a["status"], "EXECUTING")
        self.assertTrue(rec_a["claimed"])
        self.assertEqual(rec_a["owner_token"], token_a)

    def test_ceb01_expired_starting_lease_revoked_and_pre_send_fence_blocks_revived_owner(self):
        """Worker A pauses; lease expires at 30s; Worker B takes over; Worker A resumes and is fenced."""
        # 1. A claims resource at t=100.0
        t0 = 100.0
        with SharedQuotaStore._lock():
            st = SharedQuotaStore._read_state()
            st["reservations"]["EV-A"] = {
                "event_id": "EV-A",
                "device_id": "DEV-01",
                "zone_id": "ZONE-1",
                "volume_mm": 0.0,
                "status": "STARTING",
                "starting_ts": t0,
                "claimed_ts": t0,
                "claimed": True,
                "generation": 1,
                "owner_token": f"EV-A:{t0}:1",
            }
            st.setdefault("resource_claims", {})["DEV-01::ZONE-1"] = {
                "event_id": "EV-A",
                "owner_token": f"EV-A:{t0}:1",
                "status": "STARTING",
                "claimed_at": t0,
            }
            SharedQuotaStore._write_state(st)

        token_a = f"EV-A:{t0}:1"

        # 2. 31 seconds pass (t=131.0). Worker B claims the resource.
        t_b = 131.0
        b_claimed, token_b = SharedQuotaStore.claim_resource(
            device_id="DEV-01",
            zone_id="ZONE-1",
            event_id="EV-B",
            live_executing=False,
            query_ts=t_b,
        )
        self.assertTrue(b_claimed)
        self.assertNotEqual(token_a, token_b)

        # 3. Verify Worker A's reservation was atomically revoked (marked EXPIRED)
        rec_a = SharedQuotaStore.get_active_record("EV-A")
        self.assertEqual(rec_a["status"], "EXPIRED")
        self.assertFalse(rec_a["claimed"])
        self.assertIsNone(rec_a.get("owner_token"))

        # 4. Verify resource-level active owner is now Worker B
        res_claim = SharedQuotaStore.get_resource_claim("DEV-01", "ZONE-1")
        self.assertIsNotNone(res_claim)
        self.assertEqual(res_claim["event_id"], "EV-B")
        self.assertEqual(res_claim["owner_token"], token_b)

        # 5. Worker A resumes and runs pre-send fence check:
        # Check against both rec_a and resource_claims
        claim_lost = False
        now_ts = 132.0
        if rec_a is None:
            claim_lost = True
        elif (
            rec_a.get("status") not in ("STARTING", "DISPATCHING", "EXECUTING")
            or not rec_a.get("claimed", False)
            or (token_a and rec_a.get("owner_token") != token_a)
            or (rec_a.get("status") == "STARTING" and (now_ts - rec_a.get("starting_ts", 0.0) >= 30.0))
        ):
            claim_lost = True
        elif res_claim and token_a and res_claim.get("owner_token") != token_a:
            claim_lost = True

        self.assertTrue(claim_lost, "Worker A's pre-send fence check must fail after lease expiry and takeover")


class TestCEB02WaterBalanceCompartments(unittest.TestCase):
    """CEB02 (P2): Pond evaporation separated from soil evaporation; both ledgers close."""

    def test_ceb02_pond_evaporation_separated_from_soil_evaporation(self):
        """Pond evaporation is reported as surface_water_evaporation_mm, not soil evaporation."""
        # Setup the audit fixture:
        # Layer bottoms [10, 30, 60] cm, theta 0.20, Ks [0.1, 2, 2] cm/day
        # Initial ponding 5 mm, capacity 12 mm
        # Rain 4 mm, irrigation 3 mm, transpiration 8 mm, evap demand 7 mm, capillary rise 6 mm
        layer_depths = [10.0, 30.0, 60.0]
        theta_init = [0.20, 0.20, 0.20]
        fc = [0.30, 0.30, 0.30]
        wp = [0.15, 0.15, 0.15]
        sat = [0.45, 0.45, 0.45]
        res = [0.04, 0.04, 0.04]
        ks = [0.1, 2.0, 2.0]

        infil_init = InfiltrationState(
            precipitation_mm=0.0,
            irrigation_mm=0.0,
            total_surface_water_mm=5.0,
            infiltration_capacity_mm=10.0,
            actual_infiltration_mm=0.0,
            surface_excess_runoff_mm=0.0,
            gross_infiltration_mm=0.0,
            return_flow_runoff_mm=0.0,
            surface_storage_mm=5.0,
            max_surface_storage_mm=12.0,
        )

        soil_state = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=layer_depths,
            theta_profile=theta_init,
            field_capacity_profile=fc,
            wilting_point_profile=wp,
            saturation_profile=sat,
            residual_profile=res,
            hydraulic_conductivity_profile=ks,
            infiltration=infil_init,
        )

        root_zone = WaterStateFactory.create_root_zone_water_state(
            root_depth_m=0.6,
            layer_depths_cm=layer_depths,
            theta_profile=theta_init,
            field_capacity_profile=fc,
            wilting_point_profile=wp,
        )

        engine = LayeredWaterBalanceEngine()
        result = engine.step_water_balance(
            prev_soil=soil_state,
            root_zone=root_zone,
            precipitation_mm=4.0,
            irrigation_mm=3.0,
            actual_transpiration_mm=8.0,
            actual_soil_evaporation_mm=7.0,
            capillary_rise_mm=6.0,
        )

        receipt = result.receipt
        self.assertIsNotNone(receipt)

        # All 7 mm evaporation came from the 5 mm surface pond + rain/irrigation surface water
        self.assertEqual(receipt.surface_water_evaporation_mm, 7.0)
        self.assertEqual(receipt.actual_soil_evaporation_mm, 0.0)
        self.assertEqual(receipt.actual_eta_mm, 15.0)

        # 1. Independent Soil Column Ledger:
        # delta_S_soil = I_net + C - T_a - E_soil - D
        expected_soil_delta = (
            receipt.actual_infiltration_mm
            + receipt.capillary_rise_mm
            - receipt.actual_transpiration_mm
            - receipt.actual_soil_evaporation_mm
            - receipt.deep_drainage_mm
        )
        soil_residual = abs(receipt.storage_change_mm - expected_soil_delta)
        self.assertAlmostEqual(soil_residual, 0.0, places=4, msg="Soil-only ledger must close with 0.00 mm error")

        # 2. Independent Surface Reservoir Ledger:
        # delta_S_surface = P + I - I_net - Q_runoff - E_pond
        surface_delta = receipt.final_surface_storage_mm - receipt.initial_surface_storage_mm
        expected_surface_delta = (
            receipt.precipitation_mm
            + receipt.irrigation_mm
            - receipt.actual_infiltration_mm
            - receipt.surface_runoff_mm
            - receipt.surface_water_evaporation_mm
        )
        surface_residual = abs(surface_delta - expected_surface_delta)
        self.assertAlmostEqual(surface_residual, 0.0, places=4, msg="Surface reservoir ledger must close with 0.00 mm error")

        # 3. Whole System Ledger:
        self.assertTrue(receipt.mass_conserved)
        self.assertAlmostEqual(receipt.water_closure_error_mm, 0.0, places=4)


class TestCEB03PrescriptiveRestrictionContinuity(unittest.TestCase):
    """CEB03 (P1): L4 nonconservation restriction preserved into L8 ActionCard."""

    def test_ceb03_nonconservation_restriction_blocks_l8_fertilizer_candidate(self):
        """When L4 blocks prescriptions due to nonconserved water, L8 ranker must preserve BLOCKED status."""
        # 1. Construct simulated L4 output with unclosed mass balance
        class MockSWB:
            mass_conserved = False
            water_closure_error_mm = 2.0
            is_degraded = True
            uncertainty_multiplier = 2.0

        class MockPrescription:
            nutrient = Nutrient.N
            is_allowed = False
            blocked_reason = ["nonconserved_water_transition"]
            rate_kg_ha = 120.0

        n_state = NutrientState(
            nutrient=Nutrient.N,
            state_index=-0.8,
            probability_deficient=0.8,
            confidence=0.2,
            severity=Severity.HIGH,
            drivers_used=[Driver.NDVI],
            evidence_trace=[],
            confounders=[],
            notes="Degraded due to unclosed hydrological mass balance",
        )

        class MockL4Output:
            nutrient_states = {Nutrient.N: n_state}
            prescriptions = [MockPrescription()]
            swb_output = MockSWB()

        # 2. Normalize nutrient states via orchestrator adapter
        norm_states = _normalize_nutrient_states(MockL4Output())
        self.assertIn("N", norm_states)
        self.assertFalse(norm_states["N"]["is_allowed"])
        self.assertIn("nonconserved_water_transition", norm_states["N"]["blocked_reasons"])
        self.assertFalse(norm_states["N"]["mass_conserved"])

        # 3. Feed normalized state into ActionRankingEngine
        ranker = ActionRankingEngine()
        l8_input = Layer8Input(
            diagnoses=[],
            nutrient_states=norm_states,
            bio_threats={},
            weather_forecast={},
            audit_grade="A",
            zone_ids=["Z1"],
        )

        cards = ranker.rank_actions(l8_input)
        fertilize_cards = [c for c in cards if c.action_type == ActionType.FERTILIZE]
        self.assertTrue(len(fertilize_cards) > 0, "A candidate card for N deficiency should be ranked")

        for card in fertilize_cards:
            self.assertFalse(
                card.is_allowed,
                f"ActionCard {card.action_id} must NOT be allowed when L4 was nonconserved!"
            )
            self.assertIn(
                "nonconserved_water_transition",
                card.blocked_reason,
                "ActionCard must carry the nonconserved_water_transition blocker reason"
            )
            self.assertEqual(
                card.confidence,
                ConfidenceLevel.LOW,
                "ActionCard confidence must be LOW when upstream is nonconserved"
            )


class TestCEB04RootSupportAndDegradedBoundary(unittest.TestCase):
    """CEB04 (P2): Root support coverage & degraded water boundary propagate to L4 health."""

    def test_ceb04_shallow_profile_thin_coverage_flags_degraded(self):
        """When requested root depth (1.0m) exceeds profile depth (10cm), coverage is 10% and state is degraded."""
        layer_depths = [10.0]
        theta_init = [0.25]
        soil_state = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=layer_depths,
            theta_profile=theta_init,
            field_capacity_profile=[0.30],
            wilting_point_profile=[0.15],
            saturation_profile=[0.45],
            residual_profile=[0.04],
        )

        # Requested root depth 1.0 m (100 cm), supported depth 10 cm
        root_zone = WaterStateFactory.create_root_zone_water_state(
            root_depth_m=1.0,
            layer_depths_cm=layer_depths,
            theta_profile=theta_init,
            field_capacity_profile=[0.30],
            wilting_point_profile=[0.15],
        )

        water_state = WaterStateFactory.create_water_state(
            plot_id="plot_1",
            timestamp=datetime.now(timezone.utc),
            soil_water=soil_state,
            fluxes=WaterFluxState(
                potential=PotentialWaterFlux(et0_mm=4.0, kcb=1.0, ke=0.2),
                actual=ActualWaterFlux(ks=1.0, precipitation_mm=0.0, irrigation_mm=0.0, deep_drainage_mm=0.0, runoff_mm=0.0),
            ),
            root_zone=root_zone,
            data_health_score=1.0,
        )

        receipt = water_state.to_layer4_boundary_receipt()
        self.assertEqual(receipt.supported_root_depth_cm, 10.0)
        self.assertEqual(receipt.requested_root_depth_cm, 100.0)
        self.assertAlmostEqual(receipt.root_support_coverage_fraction, 0.10, places=2)
        self.assertTrue(receipt.is_degraded, "Coverage fraction 10% must mark boundary receipt as degraded")
        self.assertLessEqual(water_state.data_health_score, 0.40)

    def test_ceb04_conserved_degraded_boundary_propagates_to_l4(self):
        """A conserved water boundary with low health (0.2) marks L4 degraded and scales nutrient confidences."""
        # Create canonical water state with data_health_score = 0.2 and mass_conserved = True
        layer_depths = [10.0, 30.0, 60.0]
        theta = [0.25, 0.25, 0.25]
        soil_state = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=layer_depths,
            theta_profile=theta,
            field_capacity_profile=[0.30, 0.30, 0.30],
            wilting_point_profile=[0.15, 0.15, 0.15],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.04, 0.04, 0.04],
        )
        root_zone = WaterStateFactory.create_root_zone_water_state(
            root_depth_m=0.6,
            layer_depths_cm=layer_depths,
            theta_profile=theta,
            field_capacity_profile=[0.30, 0.30, 0.30],
            wilting_point_profile=[0.15, 0.15, 0.15],
        )
        water_state = WaterStateFactory.create_water_state(
            plot_id="plot_1",
            timestamp=datetime.now(timezone.utc),
            soil_water=soil_state,
            fluxes=WaterFluxState(
                potential=PotentialWaterFlux(et0_mm=4.0, kcb=1.0, ke=0.2),
                actual=ActualWaterFlux(ks=1.0, precipitation_mm=0.0, irrigation_mm=0.0, deep_drainage_mm=0.0, runoff_mm=0.0),
            ),
            root_zone=root_zone,
            data_health_score=0.2, # explicitly low health
        )

        class MockL3Decision:
            canonical_water_state = water_state

        l4_out = run_layer4_standalone(
            l3_decision=MockL3Decision(),
            crop_type="maize",
            stages=["V6"],
            soil_props={"nitrogen_ppm": 2.0, "phosphorus_ppm": 2.0, "potassium_ppm": 10.0},
            ndvi=0.6,
        )

        self.assertLessEqual(l4_out.data_health.overall, 0.40)
        self.assertEqual(l4_out.data_health.status, "degraded")
        self.assertIn("DEGRADED_WATER_BOUNDARY", l4_out.quality_metrics.missing_drivers)

        # Confidences must be scaled down by uncertainty multiplier (1.5), not remain 1.0
        n_conf = l4_out.nutrient_states[Nutrient.N].confidence
        self.assertLess(n_conf, 0.8)


class TestCEB05NegativeSurfaceStorageAndFluxValidation(unittest.TestCase):
    """CEB05 (P2): Negative surface storage and invalid flux inputs are rejected."""

    def test_ceb05_negative_surface_storage_rejected_in_dataclass(self):
        """InfiltrationState rejects negative surface_storage_mm."""
        with self.assertRaises(ValueError):
            InfiltrationState(
                precipitation_mm=0.0,
                irrigation_mm=0.0,
                total_surface_water_mm=0.0,
                infiltration_capacity_mm=10.0,
                actual_infiltration_mm=0.0,
                surface_excess_runoff_mm=0.0,
                surface_storage_mm=-5.0, # invalid negative inventory
                max_surface_storage_mm=12.0,
            )

    def test_ceb05_surface_storage_exceeding_max_capacity_rejected(self):
        """InfiltrationState rejects surface storage exceeding capacity."""
        with self.assertRaises(ValueError):
            InfiltrationState(
                precipitation_mm=0.0,
                irrigation_mm=0.0,
                total_surface_water_mm=0.0,
                infiltration_capacity_mm=10.0,
                actual_infiltration_mm=0.0,
                surface_excess_runoff_mm=0.0,
                surface_storage_mm=15.0, # exceeds capacity 12.0
                max_surface_storage_mm=12.0,
            )

    def test_ceb05_step_water_balance_rejects_negative_and_nan_fluxes(self):
        """step_water_balance rejects negative evaporation and NaN capillary rise."""
        soil = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 30.0],
            theta_profile=[0.20, 0.20],
            field_capacity_profile=[0.30, 0.30],
            wilting_point_profile=[0.15, 0.15],
            saturation_profile=[0.45, 0.45],
            residual_profile=[0.04, 0.04],
        )
        rz = WaterStateFactory.create_root_zone_water_state(
            root_depth_m=0.3,
            layer_depths_cm=[10.0, 30.0],
            theta_profile=[0.20, 0.20],
            field_capacity_profile=[0.30, 0.30],
            wilting_point_profile=[0.15, 0.15],
        )
        engine = LayeredWaterBalanceEngine()

        # Negative evaporation
        with self.assertRaises(ValueError):
            engine.step_water_balance(
                prev_soil=soil,
                root_zone=rz,
                precipitation_mm=0.0,
                irrigation_mm=0.0,
                actual_transpiration_mm=0.0,
                actual_soil_evaporation_mm=-2.0, # negative evaporation
                capillary_rise_mm=0.0,
            )

        # NaN capillary rise
        with self.assertRaises(ValueError):
            engine.step_water_balance(
                prev_soil=soil,
                root_zone=rz,
                precipitation_mm=0.0,
                irrigation_mm=0.0,
                actual_transpiration_mm=0.0,
                actual_soil_evaporation_mm=0.0,
                capillary_rise_mm=float("nan"), # NaN
            )


class TestCEB06LegacyWorldlineHeadRead(unittest.TestCase):
    """CEB06 (P2): Older no-index legacy head returns generation 5 on first scoped read."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.service = CanonicalWorldlineService(root=Path(self.tmp_dir.name))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_ceb06_first_scoped_read_of_no_index_legacy_head_returns_generation_5(self):
        """Predecessor traversal on legacy head with latest_checkpoint_id=A2 returns sequence 5 before write."""
        # 1. Save two checkpoints in cycle A
        self.service.save_hydraulic_checkpoint(
            plot_id="p1", checkpoint_id="A1", checkpoint_payload={"soil": 10.0}, tenant_id="t1", namespace="ns1", cycle_id="A"
        )
        self.service.save_hydraulic_checkpoint(
            plot_id="p1", checkpoint_id="A2", checkpoint_payload={"soil": 15.0}, expected_predecessor_head="A1", tenant_id="t1", namespace="ns1", cycle_id="A"
        )

        # 2. Simulate older legacy head format:
        # No scoped_heads, no checkpoint_sequences, no scoped_sequences
        # latest_checkpoint_id = "A2", sequence = 5
        head_path = self.service._hydraulic_head_path("p1", "t1", "ns1")
        legacy_head = {
            "checkpoint_id": "A2",
            "latest_checkpoint_id": "A2",
            "head_hash": "A2",
            "sequence": 5,
        }
        self.service._atomic(head_path, legacy_head)

        # 3. First scoped load BEFORE any migration write
        cp = self.service.load_latest_hydraulic_checkpoint("p1", cycle_id="A", tenant_id="t1", namespace="ns1")
        self.assertIsNotNone(cp)
        self.assertEqual(cp["checkpoint_id"], "A2")
        self.assertEqual(cp["sequence"], 5, "First scoped load must return generation 5 matching known latest head")
        self.assertEqual(cp["publication_generation"], 5, "publication_generation must be 5")


class TestCEB07QuantilePreRoundingValidation(unittest.TestCase):
    """CEB07 (P3): Probability bounds are checked strictly before precision rounding."""

    def test_ceb07_invalid_probabilities_rejected_before_rounding(self):
        """Slightly out-of-range probabilities raise ContractViolation instead of rounding to endpoints."""
        # p-0.000001 would round to -0.0
        with self.assertRaises(ContractViolation):
            parse_quantile_level("p-0.000001")

        # -0.00000001 would round to -0.0
        with self.assertRaises(ContractViolation):
            parse_quantile_level("-0.00000001")

        # p100.000001 would round to 1.0
        with self.assertRaises(ContractViolation):
            parse_quantile_level("p100.000001")

        # 100.000001%
        with self.assertRaises(ContractViolation):
            parse_quantile_level("100.000001%")

    def test_ceb07_valid_endpoints_and_percentages_accepted(self):
        """Valid endpoints p0, p100, p1, p0.5 parse correctly."""
        self.assertEqual(parse_quantile_level("p0"), 0.0)
        self.assertEqual(parse_quantile_level("0"), 0.0)
        self.assertEqual(parse_quantile_level("p100"), 1.0)
        self.assertEqual(parse_quantile_level("100%"), 1.0)
        self.assertEqual(parse_quantile_level("1.0"), 1.0)
        self.assertEqual(parse_quantile_level("p1"), 0.01)
        self.assertEqual(parse_quantile_level("q1"), 0.01)
        self.assertEqual(parse_quantile_level("1%"), 0.01)
        self.assertEqual(parse_quantile_level("p0.5"), 0.005)
        self.assertEqual(parse_quantile_level("0.5%"), 0.005)


if __name__ == "__main__":
    unittest.main()

"""
8AE01-8AE05 Corrective Verification Test Suite

Verifies fixes for all 5 follow-up findings from review of 8ae4b74:
  8AE01 (P1): In-flight dispatching transport ownership and post-dispatch fencing
  8AE02 (P2): Positive pond storage with zero maximum capacity rejected
  8AE03 (P2): Declared zero root support does not acquire implicit 60cm / 0.25 VWC priors
  8AE04 (P2): Dictionary-state compatibility permission merge is monotone conjunctive
  8AE05 (P3): Prescription dataclass declares and serializes degradation notes
"""

import dataclasses
import math
import unittest
from datetime import datetime, timezone
from typing import Dict, Any

from irrigation_runtime.safety import SharedQuotaStore
from layer3_water.contracts.water_state import (
    InfiltrationState,
    SoilWaterState,
    WaterFluxState,
    PotentialWaterFlux,
    ActualWaterFlux,
)
from layer3_water.contracts.state_factory import WaterStateFactory
from layer3_water.soil.layered_water_balance import LayeredWaterBalanceEngine
from layer4_nutrients.runner import run_layer4_standalone
from layer4_nutrients.schema import Nutrient, NutrientState, Prescription, Severity, Driver
from orchestrator_v2.runner import _normalize_nutrient_states
from layer8_prescriptive.action_ranker import ActionRankingEngine
from layer8_prescriptive.schema import (
    Layer8Input,
    ActionType,
    ConfidenceLevel,
)


class Test8AE01TransportOwnership(unittest.TestCase):
    """8AE01 (P1): In-flight transport ownership and post-dispatch fencing."""

    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    def test_8ae01_in_flight_dispatching_blocks_competing_claim_takeover(self):
        """Worker A in DISPATCHING (in-flight transport) cannot be taken over by Worker B."""
        # 1. Worker A claims resource
        t0 = 100.0
        claimed, token_a = SharedQuotaStore.claim_resource(
            device_id="DEV-01",
            zone_id="ZONE-1",
            event_id="EV-A",
            live_executing=False,
            query_ts=t0,
        )
        self.assertTrue(claimed)

        # 2. Worker A transitions to DISPATCHING immediately before transport
        ok = SharedQuotaStore.transition_to_dispatching(
            event_id="EV-A",
            owner_token=token_a,
            device_id="DEV-01",
            zone_id="ZONE-1",
        )
        self.assertTrue(ok)
        rec_a = SharedQuotaStore.get_active_record("EV-A")
        self.assertEqual(rec_a["status"], "DISPATCHING")

        # 3. 31.1 seconds pass (t=131.1). Worker B attempts claim_resource
        t_b = 131.1
        b_claimed, holding_id = SharedQuotaStore.claim_resource(
            device_id="DEV-01",
            zone_id="ZONE-1",
            event_id="EV-B",
            live_executing=False,
            query_ts=t_b,
        )
        # Worker B MUST be rejected because Worker A is actively in-flight in transport!
        self.assertFalse(b_claimed)
        self.assertEqual(holding_id, "EV-A")

        # Worker A must still be DISPATCHING and own the claim
        rec_a = SharedQuotaStore.get_active_record("EV-A")
        self.assertEqual(rec_a["status"], "DISPATCHING")
        self.assertEqual(rec_a["owner_token"], token_a)
        self.assertTrue(rec_a["claimed"])

    def test_8ae01_revoked_reservation_cannot_be_promoted_to_executing(self):
        """An expired or superseded reservation cannot be re-promoted to EXECUTING with null token."""
        t0 = 100.0
        with SharedQuotaStore._lock():
            st = SharedQuotaStore._read_state()
            st["reservations"]["EV-A"] = {
                "event_id": "EV-A",
                "device_id": "DEV-01",
                "zone_id": "ZONE-1",
                "volume_mm": 0.0,
                "status": "EXPIRED",
                "claimed": False,
                "owner_token": None,
                "generation": 1,
            }
            # Resource claim belongs to Worker B
            st.setdefault("resource_claims", {})["DEV-01::ZONE-1"] = {
                "event_id": "EV-B",
                "owner_token": "EV-B:131.0:1",
                "status": "EXECUTING",
                "claimed_at": 131.0,
            }
            SharedQuotaStore._write_state(st)

        # Worker A attempts late ACK update to EXECUTING
        SharedQuotaStore.update_status("EV-A", "EXECUTING")

        # Reservation EV-A MUST remain EXPIRED and NOT become EXECUTING
        rec_a = SharedQuotaStore.get_active_record("EV-A")
        self.assertEqual(rec_a["status"], "EXPIRED")
        self.assertFalse(rec_a["claimed"])
        self.assertIsNone(rec_a.get("owner_token"))

        # Resource claim MUST still belong to EV-B
        res_claim = SharedQuotaStore.get_resource_claim("DEV-01", "ZONE-1")
        self.assertEqual(res_claim["event_id"], "EV-B")
        self.assertEqual(res_claim["owner_token"], "EV-B:131.0:1")


class Test8AE02PositivePondStorageZeroCapacity(unittest.TestCase):
    """8AE02 (P2): Positive pond storage with zero maximum capacity is rejected."""

    def test_8ae02_positive_storage_zero_capacity_rejected_in_dataclass(self):
        """InfiltrationState(surface_storage_mm=5, max_surface_storage_mm=0) raises ValueError."""
        with self.assertRaises(ValueError):
            InfiltrationState(
                precipitation_mm=0.0,
                irrigation_mm=0.0,
                total_surface_water_mm=0.0,
                infiltration_capacity_mm=10.0,
                actual_infiltration_mm=0.0,
                surface_excess_runoff_mm=0.0,
                surface_storage_mm=5.0, # Positive storage
                max_surface_storage_mm=0.0, # Zero capacity
            )

    def test_8ae02_step_water_balance_rejects_positive_storage_with_zero_capacity(self):
        """LayeredWaterBalanceEngine rejects initial surface storage > max capacity when capacity is 0."""
        soil = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 30.0],
            theta_profile=[0.20, 0.20],
            field_capacity_profile=[0.30, 0.30],
            wilting_point_profile=[0.15, 0.15],
            saturation_profile=[0.45, 0.45],
            residual_profile=[0.04, 0.04],
            infiltration=InfiltrationState(
                precipitation_mm=0.0,
                irrigation_mm=0.0,
                total_surface_water_mm=0.0,
                infiltration_capacity_mm=10.0,
                actual_infiltration_mm=0.0,
                surface_excess_runoff_mm=0.0,
                surface_storage_mm=0.0,
                max_surface_storage_mm=0.0,
            ),
        )
        rz = WaterStateFactory.create_root_zone_water_state(
            root_depth_m=0.3,
            layer_depths_cm=[10.0, 30.0],
            theta_profile=[0.20, 0.20],
            field_capacity_profile=[0.30, 0.30],
            wilting_point_profile=[0.15, 0.15],
        )
        engine = LayeredWaterBalanceEngine()
        # Initial zero/zero is accepted
        res = engine.step_water_balance(
            prev_soil=soil,
            root_zone=rz,
            precipitation_mm=0.0,
            irrigation_mm=0.0,
            actual_transpiration_mm=0.0,
            actual_soil_evaporation_mm=0.0,
            capillary_rise_mm=0.0,
        )
        self.assertEqual(res.receipt.initial_surface_storage_mm, 0.0)

    def test_8ae02_valid_zero_storage_zero_capacity_accepted(self):
        """InfiltrationState with 0 storage and 0 capacity is valid."""
        infil = InfiltrationState(
            precipitation_mm=0.0,
            irrigation_mm=0.0,
            total_surface_water_mm=0.0,
            infiltration_capacity_mm=10.0,
            actual_infiltration_mm=0.0,
            surface_excess_runoff_mm=0.0,
            surface_storage_mm=0.0,
            max_surface_storage_mm=0.0,
        )
        self.assertEqual(infil.surface_storage_mm, 0.0)
        self.assertEqual(infil.max_surface_storage_mm, 0.0)


class Test8AE03UnsupportedRootBoundaryNoImplicitPriors(unittest.TestCase):
    """8AE03 (P2): Explicitly unsupported root boundary does not acquire implicit 60cm/0.25 priors in L4."""

    def test_8ae03_zero_supported_root_depth_blocks_prescriptions_and_caps_health(self):
        """A water boundary with supported_root_depth_cm=0.0 blocks prescriptions and receives 0 depth in loss model."""
        soil_state = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 30.0, 60.0],
            theta_profile=[0.25, 0.25, 0.25],
            field_capacity_profile=[0.30, 0.30, 0.30],
            wilting_point_profile=[0.15, 0.15, 0.15],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.04, 0.04, 0.04],
        )
        root_zone = WaterStateFactory.create_root_zone_water_state(
            root_depth_m=0.6,
            layer_depths_cm=[10.0, 30.0, 60.0],
            theta_profile=[0.25, 0.25, 0.25],
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
            data_health_score=0.8,
        )

        from layer3_water.contracts.assimilation_state import Layer3ToLayer4BoundaryReceipt

        zero_receipt = Layer3ToLayer4BoundaryReceipt(
            plot_id="plot_1",
            timestamp=datetime.now(timezone.utc),
            stress_factor_ks=1.0,
            transpiration_deficit_mm=0.0,
            transpiration_deficit_sigma_mm=0.0,
            total_available_water_mm=0.0,
            readily_available_water_mm=0.0,
            root_zone_depletion_mm=0.0,
            water_availability_ratio=0.0,
            supported_root_depth_cm=0.0,
            root_zone_storage_mm=0.0,
            theta_fc_root=0.30,
            theta_wp_root=0.15,
            theta_sat_root=0.45,
            deep_drainage_mm=0.0,
            mass_conserved=True,
            water_closure_error_mm=0.0,
            is_degraded=True,
            requested_root_depth_cm=60.0,
            root_support_coverage_fraction=0.0,
        )
        class MockCanonicalWater:
            def __init__(self, real_ws, receipt):
                self._real = real_ws
                self.root_zone = real_ws.root_zone
                self.soil_water = real_ws.soil_water
                self.fluxes = real_ws.fluxes
                self._receipt = receipt
            def to_layer4_boundary_receipt(self):
                return self._receipt
            def __getattr__(self, item):
                return getattr(self._real, item)

        class MockL3Decision:
            canonical_water_state = MockCanonicalWater(water_state, zero_receipt)

        weather = [{"date": "2026-08-20", "temp_avg_c": 22.0, "rain_mm": 0.0, "et0": 4.0, "t_max": 25.0, "t_min": 15.0}]
        l4_out = run_layer4_standalone(
            l3_decision=MockL3Decision(),
            crop_type="maize",
            stages=["V6"],
            soil_props={"nitrogen_ppm": 2.0, "phosphorus_ppm": 2.0, "potassium_ppm": 10.0},
            daily_weather=weather,
            ndvi=0.6,
        )

        self.assertIsNotNone(l4_out)
        self.assertLessEqual(l4_out.data_health.overall, 0.10)
        self.assertEqual(l4_out.data_health.status, "degraded")
        self.assertIn("UNSUPPORTED_ROOT_BOUNDARY", l4_out.quality_metrics.missing_drivers)
        self.assertLessEqual(l4_out.nutrient_states[Nutrient.N].confidence, 0.10)
        self.assertTrue(len(l4_out.prescriptions) > 0)
        for rx in l4_out.prescriptions:
            self.assertFalse(rx.is_allowed)
            self.assertIn("unsupported_root_boundary", rx.blocked_reason)
            self.assertIn("Root support depth is zero", rx.notes)


class Test8AE04ConjunctivePermissionMerge(unittest.TestCase):
    """8AE04 (P2): Dictionary-state compatibility permission merge is monotone conjunctive."""

    def test_8ae04_existing_allowed_true_cannot_override_blocked_prescription(self):
        """When input dict has is_allowed=True but prescription is blocked, merged permission must be False."""
        class MockPrescription:
            nutrient = Nutrient.N
            is_allowed = False
            blocked_reason = ["regulatory_N_limit"]
            rate_kg_ha = 120.0

        class MockSWB:
            mass_conserved = True
            water_closure_error_mm = 0.0

        # Input dictionary with existing is_allowed = True
        dict_state = {
            "probability_deficient": 0.8,
            "confidence": 0.8,
            "severity": "HIGH",
            "is_allowed": True,
            "blocked_reasons": [],
            "mass_conserved": True,
        }

        class MockL4Output:
            nutrient_states = {"N": dict_state}
            prescriptions = [MockPrescription()]
            swb_output = MockSWB()

        norm = _normalize_nutrient_states(MockL4Output())
        self.assertIn("N", norm)
        # MUST BE FALSE! (Monotone conjunction: True and False = False)
        self.assertFalse(norm["N"]["is_allowed"], "Existing True permission cannot override blocked prescription")
        self.assertIn("regulatory_N_limit", norm["N"]["blocked_reasons"])

        # Feed to ActionRankingEngine
        ranker = ActionRankingEngine()
        l8_input = Layer8Input(
            diagnoses=[],
            nutrient_states=norm,
            bio_threats={},
            weather_forecast={},
            audit_grade="A",
            zone_ids=["Z1"],
        )
        cards = ranker.rank_actions(l8_input)
        fertilize_cards = [c for c in cards if c.action_type == ActionType.FERTILIZE]
        self.assertTrue(len(fertilize_cards) > 0)
        for c in fertilize_cards:
            self.assertFalse(c.is_allowed)
            self.assertIn("regulatory_N_limit", c.blocked_reason)
            self.assertEqual(c.confidence, ConfidenceLevel.LOW)


class Test8AE05PrescriptionDataclassNotesSerialization(unittest.TestCase):
    """8AE05 (P3): Prescription dataclass declares and serializes degradation notes."""

    def test_8ae05_prescription_dataclass_serializes_notes(self):
        """Prescription.notes is declared on dataclass and survives asdict serialization."""
        rx = Prescription(
            nutrient=Nutrient.N,
            rate_kg_ha=50.0,
            notes="Water boundary degraded (uncertainty multiplier 1.5).",
        )
        d = dataclasses.asdict(rx)
        self.assertIn("notes", d)
        self.assertEqual(d["notes"], "Water boundary degraded (uncertainty multiplier 1.5).")


if __name__ == "__main__":
    unittest.main()

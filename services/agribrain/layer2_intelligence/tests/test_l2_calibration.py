"""
Layer 2 Intelligence — Calibration Test Suite.

Pinned numeric values, boundary precision, phenology multiplier arithmetic,
monotonicity sweeps, and multi-signal stacking verification.

Mirrors L1's test_l1_calibration.py pattern.
"""

import pytest
from datetime import datetime, timezone

from layer1_fusion.schemas import (
    DataHealthScore, Layer2InputContext, CropCycleContext,
)
from layer2_intelligence.engine import Layer2IntelligenceEngine
from layer2_intelligence.stress_attributor import attribute_stress
from layer2_intelligence.schemas import Layer2Output


_TS = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
_HEALTH = DataHealthScore(
    overall=0.8, confidence_ceiling=0.9, status="ok",
    source_completeness=0.9, provenance_completeness=1.0,
    freshness=0.9, spatial_fidelity=0.7,
)


def _ctx(water=None, veg=None, stress=None, operational=None,
         crop_context=None, data_health=None):
    return Layer2InputContext(
        plot_id="cal_plot", crop_context=crop_context,
        water_context=water or {}, vegetation_context=veg or {},
        stress_evidence_context=stress or {},
        operational_context=operational or {},
        soil_site_context={}, conflicts=[], gaps=[],
        provenance_ref="l1_cal", spatial_index_ref=None,
        data_health=data_health or _HEALTH,
    )


def _raw_water(ndmi=None, sm=None, precip=None, vpd=None):
    """Call stress_attributor directly for precise numeric testing."""
    w = {}
    if ndmi is not None:
        w["ndmi_mean"] = {"value": ndmi, "confidence": 0.7, "source_weights": {}}
    if sm is not None:
        w["soil_moisture_vwc"] = {"value": sm, "confidence": 0.6, "source_weights": {}}
    op = {}
    if precip is not None:
        op["precipitation_mm"] = {"value": precip, "confidence": 0.8, "source_weights": {}}
    env = {}
    if vpd is not None:
        env["vpd"] = {"value": vpd, "confidence": 0.6, "source_weights": {}}
    return attribute_stress(
        water_features=w, vegetation_features={},
        environment_features=env, operational_features=op,
        soil_site_features={}, conflicts=[], data_health=_HEALTH,
        plot_id="cal", run_id="cal_run",
    )


# ══════════════════════════════════════════════════════════════════════════
# 1. Pinned severity values — exact arithmetic from stress_attributor.py
# ══════════════════════════════════════════════════════════════════════════

class TestPinnedWaterSeverity:
    """Water severity formula: 0.3 + (0.2 - ndmi)*2.0 per NDMI component."""

    def test_ndmi_0_10(self):
        # severity = 0.3 + (0.2-0.10)*2.0 = 0.3 + 0.2 = 0.5
        items = _raw_water(ndmi=0.10)
        assert len(items) == 1
        assert items[0].severity == 0.5

    def test_ndmi_0_00(self):
        # severity = 0.3 + (0.2-0.0)*2.0 = 0.3 + 0.4 = 0.7
        items = _raw_water(ndmi=0.0)
        assert items[0].severity == 0.7

    def test_ndmi_0_19(self):
        # severity = 0.3 + (0.2-0.19)*2.0 = 0.3 + 0.02 = 0.32
        items = _raw_water(ndmi=0.19)
        assert items[0].severity == 0.32

    def test_ndmi_plus_soil_moisture(self):
        # NDMI: 0.3 + (0.2-0.10)*2.0 = 0.5
        # SM:   0.2 + (0.2-0.10)*1.5 = 0.35
        # Total: 0.85
        items = _raw_water(ndmi=0.10, sm=0.10)
        assert items[0].severity == 0.85

    def test_ndmi_plus_sm_plus_precip_plus_vpd(self):
        # NDMI: 0.3 + 0.2 = 0.5
        # SM:   0.2 + 0.15 = 0.35
        # precip < 5: +0.1
        # vpd > 2.0: +0.1
        # Total: 1.05 → capped to 1.0
        items = _raw_water(ndmi=0.10, sm=0.10, precip=1.0, vpd=3.0)
        assert items[0].severity == 1.0


class TestPinnedThermalSeverity:
    """Thermal formula: min(1.0, (temp-35)/10 * 0.5)."""

    def test_temp_36(self):
        items = attribute_stress(
            water_features={}, vegetation_features={},
            environment_features={"temp_max": {"value": 36.0, "confidence": 0.8, "source_weights": {}}},
            operational_features={}, soil_site_features={},
            conflicts=[], data_health=_HEALTH, plot_id="cal",
        )
        thermal = [s for s in items if s.stress_type == "THERMAL"]
        assert len(thermal) == 1
        # (36-35)/10 * 0.5 = 0.05
        assert thermal[0].severity == 0.05

    def test_temp_40(self):
        items = attribute_stress(
            water_features={}, vegetation_features={},
            environment_features={"temp_max": {"value": 40.0, "confidence": 0.8, "source_weights": {}}},
            operational_features={}, soil_site_features={},
            conflicts=[], data_health=_HEALTH, plot_id="cal",
        )
        thermal = [s for s in items if s.stress_type == "THERMAL"]
        # (40-35)/10 * 0.5 = 0.25
        assert thermal[0].severity == 0.25

    def test_temp_40_with_vpd(self):
        items = attribute_stress(
            water_features={}, vegetation_features={},
            environment_features={
                "temp_max": {"value": 40.0, "confidence": 0.8, "source_weights": {}},
                "vpd": {"value": 3.5, "confidence": 0.7, "source_weights": {}},
            },
            operational_features={}, soil_site_features={},
            conflicts=[], data_health=_HEALTH, plot_id="cal",
        )
        thermal = [s for s in items if s.stress_type == "THERMAL"]
        # base 0.25 + VPD bonus 0.2 = 0.45
        assert thermal[0].severity == 0.45


# ══════════════════════════════════════════════════════════════════════════
# 2. Boundary precision — ±0.001 around thresholds
# ══════════════════════════════════════════════════════════════════════════

class TestBoundaryPrecision:
    """Thresholds must be exact: crossing by 0.001 changes outcome."""

    def test_ndmi_just_below_threshold(self):
        # NDMI < 0.2 → fires
        items = _raw_water(ndmi=0.199)
        assert len(items) == 1

    def test_ndmi_at_threshold(self):
        # NDMI = 0.2 → does NOT fire (< 0.2 required)
        items = _raw_water(ndmi=0.2)
        assert len(items) == 0

    def test_ndmi_just_above_threshold(self):
        items = _raw_water(ndmi=0.201)
        assert len(items) == 0

    def test_thermal_at_35(self):
        items = attribute_stress(
            water_features={}, vegetation_features={},
            environment_features={"temp_max": {"value": 35.0, "confidence": 0.8, "source_weights": {}}},
            operational_features={}, soil_site_features={},
            conflicts=[], data_health=_HEALTH, plot_id="cal",
        )
        thermal = [s for s in items if s.stress_type == "THERMAL"]
        assert len(thermal) == 0, "35.0 exactly must not trigger thermal"

    def test_thermal_at_35_001(self):
        items = attribute_stress(
            water_features={}, vegetation_features={},
            environment_features={"temp_max": {"value": 35.001, "confidence": 0.8, "source_weights": {}}},
            operational_features={}, soil_site_features={},
            conflicts=[], data_health=_HEALTH, plot_id="cal",
        )
        thermal = [s for s in items if s.stress_type == "THERMAL"]
        assert len(thermal) == 1, "35.001 must trigger thermal"

    def test_soil_moisture_boundary(self):
        # SM < 0.2 triggers, = 0.2 does not
        items_below = _raw_water(sm=0.199)
        items_at = _raw_water(sm=0.2)
        assert len(items_below) == 1
        assert len(items_at) == 0


# ══════════════════════════════════════════════════════════════════════════
# 3. Phenology multiplier arithmetic
# ══════════════════════════════════════════════════════════════════════════

class TestPhenologyMultiplierArithmetic:
    """Verify exact multiplier × severity arithmetic."""

    def test_reproductive_water_multiplier_1_3(self):
        engine = Layer2IntelligenceEngine()
        ctx = _ctx(
            water={"ndmi_mean": {"value": 0.15, "confidence": 0.7, "source_weights": {}}},
            veg={"ndvi_mean": {"value": 0.50, "confidence": 0.7, "source_weights": {}}},
        )
        # Vegetative (1.0x)
        crop_veg = CropCycleContext(current_stage="vegetative", gdd_accumulated=500)
        pkg_v = engine.analyze(ctx, crop_cycle=crop_veg, run_id="cal_pheno_v", run_timestamp=_TS)
        # Reproductive (1.3x)
        crop_rep = CropCycleContext(current_stage="reproductive", gdd_accumulated=1200)
        pkg_r = engine.analyze(ctx, crop_cycle=crop_rep, run_id="cal_pheno_r", run_timestamp=_TS)

        ws_v = [s for s in pkg_v.stress_context if s.stress_type == "WATER"]
        ws_r = [s for s in pkg_r.stress_context if s.stress_type == "WATER"]
        assert len(ws_v) >= 1 and len(ws_r) >= 1

        # Base severity same; reproductive severity = min(1.0, base * 1.3)
        base = ws_v[0].severity
        expected = round(min(1.0, base * 1.3), 3)
        assert ws_r[0].severity == expected, \
            f"Expected {expected}, got {ws_r[0].severity} (base={base})"

    def test_senescence_thermal_multiplier_0_7(self):
        engine = Layer2IntelligenceEngine()
        ctx = _ctx(
            stress={"temp_max": {"value": 40.0, "confidence": 0.8, "source_weights": {}}},
            veg={"ndvi_mean": {"value": 0.50, "confidence": 0.7, "source_weights": {}}},
        )
        crop_veg = CropCycleContext(current_stage="vegetative", gdd_accumulated=500)
        pkg_v = engine.analyze(ctx, crop_cycle=crop_veg, run_id="cal_sen_v", run_timestamp=_TS)
        crop_sen = CropCycleContext(current_stage="senescence", gdd_accumulated=2500)
        pkg_s = engine.analyze(ctx, crop_cycle=crop_sen, run_id="cal_sen_s", run_timestamp=_TS)

        ts_v = [s for s in pkg_v.stress_context if s.stress_type == "THERMAL"]
        ts_s = [s for s in pkg_s.stress_context if s.stress_type == "THERMAL"]
        assert len(ts_v) >= 1 and len(ts_s) >= 1
        assert ts_s[0].severity < ts_v[0].severity, \
            "Senescence should reduce thermal severity"


# ══════════════════════════════════════════════════════════════════════════
# 4. Monotonicity sweeps
# ══════════════════════════════════════════════════════════════════════════

class TestMonotonicitySweeps:
    """Severity must respond monotonically to input signals."""

    def test_ndmi_sweep_monotonic(self):
        """As NDMI decreases from 0.19 to 0.0, severity must increase."""
        ndmi_values = [0.19, 0.15, 0.10, 0.05, 0.02, 0.0]
        severities = []
        for ndmi in ndmi_values:
            items = _raw_water(ndmi=ndmi)
            sev = items[0].severity if items else 0.0
            severities.append(sev)
        for i in range(1, len(severities)):
            assert severities[i] >= severities[i - 1], \
                f"Monotonicity violated: NDMI={ndmi_values[i]} → sev={severities[i]} " \
                f"< NDMI={ndmi_values[i-1]} → sev={severities[i-1]}"

    def test_temperature_sweep_monotonic(self):
        """As temperature increases above 35, severity must increase."""
        temps = [35.5, 37.0, 39.0, 42.0, 45.0]
        severities = []
        for t in temps:
            items = attribute_stress(
                water_features={}, vegetation_features={},
                environment_features={"temp_max": {"value": t, "confidence": 0.8, "source_weights": {}}},
                operational_features={}, soil_site_features={},
                conflicts=[], data_health=_HEALTH, plot_id="cal",
            )
            thermal = [s for s in items if s.stress_type == "THERMAL"]
            severities.append(thermal[0].severity if thermal else 0.0)
        for i in range(1, len(severities)):
            assert severities[i] >= severities[i - 1], \
                f"Monotonicity violated at temp={temps[i]}"

    def test_soil_moisture_sweep_monotonic(self):
        """As soil moisture decreases, water severity must increase."""
        sm_values = [0.19, 0.15, 0.10, 0.05, 0.01]
        severities = []
        for sm in sm_values:
            items = _raw_water(sm=sm)
            sev = items[0].severity if items else 0.0
            severities.append(sev)
        for i in range(1, len(severities)):
            assert severities[i] >= severities[i - 1]


# ══════════════════════════════════════════════════════════════════════════
# 5. Multi-signal stacking
# ══════════════════════════════════════════════════════════════════════════

class TestMultiSignalStacking:
    """Multiple corroborating signals must increase severity."""

    def test_ndmi_alone_less_than_ndmi_plus_sm(self):
        items_ndmi = _raw_water(ndmi=0.10)
        items_both = _raw_water(ndmi=0.10, sm=0.10)
        assert items_both[0].severity > items_ndmi[0].severity

    def test_precip_corroboration_adds_severity(self):
        items_base = _raw_water(ndmi=0.10)
        items_corr = _raw_water(ndmi=0.10, precip=1.0)
        assert items_corr[0].severity > items_base[0].severity

    def test_vpd_corroboration_adds_severity(self):
        items_base = _raw_water(ndmi=0.10)
        items_corr = _raw_water(ndmi=0.10, vpd=3.0)
        assert items_corr[0].severity > items_base[0].severity

    def test_full_stack_highest_severity(self):
        items_min = _raw_water(ndmi=0.10)
        items_max = _raw_water(ndmi=0.10, sm=0.10, precip=0.0, vpd=3.5)
        assert items_max[0].severity > items_min[0].severity

    def test_confidence_scales_with_evidence_count(self):
        """More evidence items → higher confidence."""
        items_1 = _raw_water(ndmi=0.10)
        items_4 = _raw_water(ndmi=0.10, sm=0.10, precip=0.0, vpd=3.5)
        assert items_4[0].confidence > items_1[0].confidence


# ══════════════════════════════════════════════════════════════════════════
# 6. Conflict penalty calibration
# ══════════════════════════════════════════════════════════════════════════

class TestConflictPenaltyCalibration:
    """Conflict penalty must increase uncertainty by exact amounts."""

    def test_major_conflict_adds_0_15(self):
        from layer1_fusion.schemas import EvidenceConflict
        items_clean = attribute_stress(
            water_features={"ndmi_mean": {"value": 0.10, "confidence": 0.7, "source_weights": {}}},
            vegetation_features={}, environment_features={},
            operational_features={}, soil_site_features={},
            conflicts=[], data_health=_HEALTH, plot_id="cal",
        )
        items_conflict = attribute_stress(
            water_features={"ndmi_mean": {"value": 0.10, "confidence": 0.7, "source_weights": {}}},
            vegetation_features={}, environment_features={},
            operational_features={}, soil_site_features={},
            conflicts=[EvidenceConflict(
                conflict_id="c1", conflict_type="TEST", variable_group="water",
                spatial_scope="plot", severity="major",
            )],
            data_health=_HEALTH, plot_id="cal",
        )
        delta = items_conflict[0].uncertainty - items_clean[0].uncertainty
        assert abs(delta - 0.15) < 0.001, f"Major conflict should add 0.15, got delta={delta}"

    def test_moderate_conflict_adds_0_08(self):
        from layer1_fusion.schemas import EvidenceConflict
        items_clean = attribute_stress(
            water_features={"ndmi_mean": {"value": 0.10, "confidence": 0.7, "source_weights": {}}},
            vegetation_features={}, environment_features={},
            operational_features={}, soil_site_features={},
            conflicts=[], data_health=_HEALTH, plot_id="cal",
        )
        items_conflict = attribute_stress(
            water_features={"ndmi_mean": {"value": 0.10, "confidence": 0.7, "source_weights": {}}},
            vegetation_features={}, environment_features={},
            operational_features={}, soil_site_features={},
            conflicts=[EvidenceConflict(
                conflict_id="c1", conflict_type="TEST", variable_group="water",
                spatial_scope="plot", severity="moderate",
            )],
            data_health=_HEALTH, plot_id="cal",
        )
        delta = items_conflict[0].uncertainty - items_clean[0].uncertainty
        assert abs(delta - 0.08) < 0.001

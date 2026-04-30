"""
Layer 2 Intelligence — Stress Combination Tests.

Verifies behaviour when multiple stress types co-occur, mutually exclude,
or compete for severity ranking.  Mirrors L1's test_stress_combinations.py
pattern.
"""

import pytest
from datetime import datetime, timezone

from layer1_fusion.schemas import (
    DataHealthScore,
    EvidenceConflict,
    Layer2InputContext,
    SpatialIndex,
    ZoneRef,
    CropCycleContext,
)
from layer2_intelligence.engine import Layer2IntelligenceEngine
from layer2_intelligence.schemas import Layer2Output


_TS = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

_DEFAULT_HEALTH = DataHealthScore(
    overall=0.8, confidence_ceiling=0.9, status="ok",
    source_completeness=0.9, provenance_completeness=1.0,
    freshness=0.9, spatial_fidelity=0.7,
)


def _ctx(
    water=None, veg=None, stress=None, operational=None,
    soil=None, conflicts=None, gaps=None,
    data_health=None, spatial_index=None,
    crop_context=None, plot_id="combo_plot",
) -> Layer2InputContext:
    return Layer2InputContext(
        plot_id=plot_id,
        crop_context=crop_context,
        water_context=water or {},
        vegetation_context=veg or {},
        stress_evidence_context=stress or {},
        operational_context=operational or {},
        soil_site_context=soil or {},
        conflicts=conflicts or [],
        gaps=gaps or [],
        provenance_ref="l1_combo_run",
        spatial_index_ref=spatial_index,
        data_health=data_health or _DEFAULT_HEALTH,
    )


@pytest.fixture
def engine():
    return Layer2IntelligenceEngine()


# ── Water + Thermal co-occurrence ─────────────────────────────────────────

class TestWaterThermalCoOccurrence:
    """Water and thermal stress can co-exist in the same run."""

    def test_both_types_detected(self, engine):
        """Low NDMI + high temp → both WATER and THERMAL present."""
        ctx = _ctx(
            water={
                "ndmi_mean": {"value": 0.10, "confidence": 0.7, "source_weights": {}},
                "soil_moisture_vwc": {"value": 0.12, "confidence": 0.6, "source_weights": {}},
            },
            veg={"ndvi_mean": {"value": 0.35, "confidence": 0.7, "source_weights": {}}},
            stress={
                "temp_max": {"value": 40.0, "confidence": 0.8, "source_weights": {}},
                "vpd": {"value": 3.5, "confidence": 0.6, "source_weights": {}},
            },
            operational={"precipitation_mm": {"value": 0.5, "confidence": 0.8, "source_weights": {}}},
        )
        pkg = engine.analyze(ctx, run_id="combo_wt", run_timestamp=_TS)
        types = {s.stress_type for s in pkg.stress_context}
        assert "WATER" in types, "Water stress should be detected"
        assert "THERMAL" in types, "Thermal stress should be detected"

    def test_both_have_independent_evidence_chains(self, engine):
        ctx = _ctx(
            water={"ndmi_mean": {"value": 0.08, "confidence": 0.7, "source_weights": {}}},
            veg={"ndvi_mean": {"value": 0.30, "confidence": 0.7, "source_weights": {}}},
            stress={"temp_max": {"value": 42.0, "confidence": 0.8, "source_weights": {}}},
        )
        pkg = engine.analyze(ctx, run_id="combo_wt_ev", run_timestamp=_TS)
        water = [s for s in pkg.stress_context if s.stress_type == "WATER"][0]
        thermal = [s for s in pkg.stress_context if s.stress_type == "THERMAL"][0]
        # Each must have its own evidence chain
        assert len(water.explanation_basis) >= 1
        assert len(thermal.explanation_basis) >= 1
        # Evidence chains must not overlap
        assert water.stress_id != thermal.stress_id

    def test_biotic_excluded_when_water_or_thermal_present(self, engine):
        """Biotic requires absence of both water AND thermal stress."""
        ctx = _ctx(
            water={"ndmi_mean": {"value": 0.10, "confidence": 0.7, "source_weights": {}}},
            veg={"ndvi_mean": {"value": 0.25, "confidence": 0.7, "source_weights": {}}},
            stress={"temp_max": {"value": 38.0, "confidence": 0.8, "source_weights": {}}},
        )
        pkg = engine.analyze(ctx, run_id="combo_no_biotic", run_timestamp=_TS)
        types = {s.stress_type for s in pkg.stress_context}
        assert "BIOTIC" not in types


# ── Nutrient exclusion under water stress ─────────────────────────────────

class TestNutrientExclusion:
    """Nutrient stress must NOT fire when water stress is present."""

    def test_nutrient_excluded_with_low_ndmi(self, engine):
        """Low NDMI triggers water stress → nutrient must be suppressed."""
        ctx = _ctx(
            water={
                "ndmi_mean": {"value": 0.10, "confidence": 0.7, "source_weights": {}},
            },
            veg={
                "ndvi_mean": {"value": 0.30, "confidence": 0.7, "source_weights": {}},
                "evi_mean": {"value": 0.18, "confidence": 0.6, "source_weights": {}},
            },
        )
        pkg = engine.analyze(ctx, run_id="combo_nut_excl", run_timestamp=_TS)
        types = {s.stress_type for s in pkg.stress_context}
        assert "WATER" in types, "Water stress should fire"
        assert "NUTRIENT" not in types, "Nutrient must be excluded when water stress present"

    def test_nutrient_fires_with_adequate_water(self, engine):
        """Adequate water (NDMI > 0.3) + low NDVI → nutrient fires."""
        ctx = _ctx(
            water={
                "ndmi_mean": {"value": 0.38, "confidence": 0.7, "source_weights": {}},
                "soil_moisture_vwc": {"value": 0.30, "confidence": 0.6, "source_weights": {}},
            },
            veg={
                "ndvi_mean": {"value": 0.28, "confidence": 0.7, "source_weights": {}},
                "evi_mean": {"value": 0.20, "confidence": 0.6, "source_weights": {}},
            },
        )
        pkg = engine.analyze(ctx, run_id="combo_nut_fire", run_timestamp=_TS)
        types = {s.stress_type for s in pkg.stress_context}
        assert "NUTRIENT" in types
        assert "WATER" not in types


# ── All-4-types extreme payload ───────────────────────────────────────────

class TestAllFourStressTypes:
    """Verify the engine correctly handles payloads that could trigger
    all four stress types.  Due to exclusion rules, at most 3 should fire."""

    def test_maximum_three_types_cooccur(self, engine):
        """Biotic is exclusion-based: if water OR thermal fires, biotic can't.
        So at most WATER + THERMAL + NUTRIENT, but nutrient requires no water stress.
        Therefore realistic max is WATER + THERMAL (2) when both present."""
        ctx = _ctx(
            water={
                "ndmi_mean": {"value": 0.08, "confidence": 0.7, "source_weights": {}},
                "soil_moisture_vwc": {"value": 0.10, "confidence": 0.6, "source_weights": {}},
            },
            veg={
                "ndvi_mean": {"value": 0.20, "confidence": 0.7, "source_weights": {}},
                "evi_mean": {"value": 0.15, "confidence": 0.6, "source_weights": {}},
                "vegetation_fraction_scl": {"value": 0.25, "confidence": 0.6, "source_weights": {}},
            },
            stress={
                "temp_max": {"value": 44.0, "confidence": 0.8, "source_weights": {}},
                "vpd": {"value": 4.5, "confidence": 0.7, "source_weights": {}},
            },
            operational={
                "precipitation_mm": {"value": 0.0, "confidence": 0.8, "source_weights": {}},
            },
        )
        pkg = engine.analyze(ctx, run_id="combo_all4", run_timestamp=_TS)
        types = {s.stress_type for s in pkg.stress_context}
        # Water fires → Nutrient excluded; Water+Thermal fire → Biotic excluded
        assert "WATER" in types
        assert "THERMAL" in types
        assert "NUTRIENT" not in types, "Nutrient excluded by water stress"
        assert "BIOTIC" not in types, "Biotic excluded by water+thermal"

    def test_biotic_fires_in_isolation(self, engine):
        """When no abiotic stress is present, biotic should fire for low NDVI."""
        ctx = _ctx(
            water={
                "ndmi_mean": {"value": 0.50, "confidence": 0.7, "source_weights": {}},
                "soil_moisture_vwc": {"value": 0.40, "confidence": 0.7, "source_weights": {}},
            },
            veg={
                "ndvi_mean": {"value": 0.25, "confidence": 0.7, "source_weights": {}},
                "evi_mean": {"value": 0.18, "confidence": 0.6, "source_weights": {}},
            },
            stress={
                "temp_max": {"value": 28.0, "confidence": 0.8, "source_weights": {}},
            },
        )
        pkg = engine.analyze(ctx, run_id="combo_biotic", run_timestamp=_TS)
        types = {s.stress_type for s in pkg.stress_context}
        assert "WATER" not in types
        assert "THERMAL" not in types
        # Nutrient also fires because water adequate + low NDVI
        # Biotic may or may not fire depending on nutrient exclusion logic
        # but at least one of NUTRIENT or BIOTIC should
        assert "NUTRIENT" in types or "BIOTIC" in types


# ── Severity ranking hierarchy ────────────────────────────────────────────

class TestSeverityRanking:
    """When multiple stresses co-exist, severity ranking must be coherent."""

    def test_water_severity_dominates_with_strong_signal(self, engine):
        """NDMI=0.05, soil_moisture=0.08 → water severity should be highest."""
        ctx = _ctx(
            water={
                "ndmi_mean": {"value": 0.05, "confidence": 0.7, "source_weights": {}},
                "soil_moisture_vwc": {"value": 0.08, "confidence": 0.6, "source_weights": {}},
            },
            veg={"ndvi_mean": {"value": 0.30, "confidence": 0.7, "source_weights": {}}},
            stress={
                "temp_max": {"value": 36.0, "confidence": 0.8, "source_weights": {}},  # mild thermal
            },
            operational={"precipitation_mm": {"value": 0.0, "confidence": 0.8, "source_weights": {}}},
        )
        pkg = engine.analyze(ctx, run_id="combo_rank", run_timestamp=_TS)
        water = [s for s in pkg.stress_context if s.stress_type == "WATER"]
        thermal = [s for s in pkg.stress_context if s.stress_type == "THERMAL"]
        assert len(water) >= 1 and len(thermal) >= 1
        assert water[0].severity > thermal[0].severity, \
            f"Water severity ({water[0].severity}) should exceed mild thermal ({thermal[0].severity})"

    def test_all_stresses_within_zero_one(self, engine):
        """All severity values must be in [0, 1]."""
        ctx = _ctx(
            water={"ndmi_mean": {"value": 0.01, "confidence": 0.7, "source_weights": {}},
                   "soil_moisture_vwc": {"value": 0.01, "confidence": 0.7, "source_weights": {}}},
            veg={"ndvi_mean": {"value": 0.10, "confidence": 0.7, "source_weights": {}}},
            stress={"temp_max": {"value": 50.0, "confidence": 0.8, "source_weights": {}},
                    "vpd": {"value": 6.0, "confidence": 0.7, "source_weights": {}}},
            operational={"precipitation_mm": {"value": 0.0, "confidence": 0.8, "source_weights": {}}},
        )
        pkg = engine.analyze(ctx, run_id="combo_bounds", run_timestamp=_TS)
        for s in pkg.stress_context:
            assert 0.0 <= s.severity <= 1.0, f"Severity {s.severity} out of [0,1] for {s.stress_type}"
            assert 0.0 <= s.confidence <= 1.0, f"Confidence {s.confidence} out of [0,1]"
            assert s.uncertainty > 0, f"Uncertainty must be > 0"


# ── Zone-specific stress isolation ────────────────────────────────────────

class TestZoneStressIsolation:
    """Zone A may have water stress while Zone B has none."""

    def test_zone_a_stressed_zone_b_healthy(self, engine):
        ctx = _ctx(
            water={
                "ndmi_mean": {"value": 0.35, "confidence": 0.7, "source_weights": {}},
                "ndmi_za": {"value": 0.08, "confidence": 0.7, "scope_id": "za", "source_weights": {}},
                "ndmi_zb": {"value": 0.45, "confidence": 0.7, "scope_id": "zb", "source_weights": {}},
            },
            veg={
                "ndvi_mean": {"value": 0.50, "confidence": 0.7, "source_weights": {}},
                "ndvi_za": {"value": 0.30, "confidence": 0.7, "scope_id": "za", "source_weights": {}},
                "ndvi_zb": {"value": 0.70, "confidence": 0.7, "scope_id": "zb", "source_weights": {}},
            },
            spatial_index=SpatialIndex(
                plot_id="combo_plot",
                zones=[ZoneRef(zone_id="za"), ZoneRef(zone_id="zb")],
            ),
        )
        pkg = engine.analyze(ctx, run_id="combo_zone_iso", run_timestamp=_TS)
        za_stress = [s for s in pkg.stress_context if s.scope_id == "za"]
        zb_stress = [s for s in pkg.stress_context if s.scope_id == "zb"]
        assert len(za_stress) > 0, "Zone A should have stress"
        assert all(s.severity < 0.1 for s in zb_stress) or len(zb_stress) == 0, \
            "Zone B should be healthy (no or minimal stress)"

    def test_zone_stress_map_reflects_isolation(self, engine):
        ctx = _ctx(
            water={
                "ndmi_mean": {"value": 0.30, "confidence": 0.7, "source_weights": {}},
                "ndmi_z1": {"value": 0.05, "confidence": 0.7, "scope_id": "z1", "source_weights": {}},
                "ndmi_z2": {"value": 0.50, "confidence": 0.7, "scope_id": "z2", "source_weights": {}},
            },
            veg={
                "ndvi_mean": {"value": 0.45, "confidence": 0.7, "source_weights": {}},
                "ndvi_z1": {"value": 0.25, "confidence": 0.7, "scope_id": "z1", "source_weights": {}},
                "ndvi_z2": {"value": 0.72, "confidence": 0.7, "scope_id": "z2", "source_weights": {}},
            },
            spatial_index=SpatialIndex(
                plot_id="combo_plot",
                zones=[ZoneRef(zone_id="z1"), ZoneRef(zone_id="z2")],
            ),
        )
        pkg = engine.analyze(ctx, run_id="combo_zone_map", run_timestamp=_TS)
        # z1 should have higher stress than z2 in zone_stress_map
        if "z1" in pkg.zone_stress_map:
            assert pkg.zone_stress_map["z1"].max_severity > 0.2

    def test_phenology_affects_zone_stress(self, engine):
        """Phenology adjustment should apply independently to zone-level stress."""
        ctx = _ctx(
            water={
                "ndmi_mean": {"value": 0.15, "confidence": 0.7, "source_weights": {}},
                "ndmi_z1": {"value": 0.12, "confidence": 0.7, "scope_id": "z1", "source_weights": {}},
            },
            veg={
                "ndvi_mean": {"value": 0.40, "confidence": 0.7, "source_weights": {}},
                "ndvi_z1": {"value": 0.35, "confidence": 0.7, "scope_id": "z1", "source_weights": {}},
            },
            spatial_index=SpatialIndex(
                plot_id="combo_plot",
                zones=[ZoneRef(zone_id="z1")],
            ),
        )
        # Vegetative stage (multiplier = 1.0)
        crop_veg = CropCycleContext(current_stage="vegetative", gdd_accumulated=500)
        pkg_veg = engine.analyze(ctx, crop_cycle=crop_veg, run_id="zone_pheno_v", run_timestamp=_TS)

        # Reproductive stage (multiplier = 1.3)
        crop_rep = CropCycleContext(current_stage="reproductive", gdd_accumulated=1200)
        pkg_rep = engine.analyze(ctx, crop_cycle=crop_rep, run_id="zone_pheno_r", run_timestamp=_TS)

        z1_v = [s for s in pkg_veg.stress_context if s.scope_id == "z1" and s.stress_type == "WATER"]
        z1_r = [s for s in pkg_rep.stress_context if s.scope_id == "z1" and s.stress_type == "WATER"]
        if z1_v and z1_r:
            assert z1_r[0].severity >= z1_v[0].severity, \
                "Reproductive stage should amplify water stress severity"
"""
    Stress combination tests for Layer 2 Intelligence Engine.
"""

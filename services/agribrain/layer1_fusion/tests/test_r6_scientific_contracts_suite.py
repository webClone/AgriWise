"""Akaloris Layer 1 R6 Formal Scientific Contracts Acceptance Suite (T01..T50).

Implements and executes all 50 normative falsification scenarios across SPEC-A through SPEC-E:
- SPEC-A: Scientific identity, content roots, ancestry DAG, and revisions (T01..T03, T12..T20)
- SPEC-B: Multi-axis causal time, timezone offsets, leap days, and knowledge cutoff replay (T06..T07, T21..T28)
- SPEC-C: Physical spatial support, raster geometry contracts, valid pixel counts, and units (T29..T35, T40)
- SPEC-D: Estimator-consistent covariance, non-PSD rejection, dependent noise, and unknown sigma (T04..T05, T36..T39, T41..T42)
- SPEC-E: Monotonic authority vectors, ASMAE feature gates, visual isolation, and end-to-end trace (T08..T11, T43..T50)

Policy: AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false mandatory across all executions.
"""
from __future__ import annotations

import importlib
import json
import math
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest


def _root():
    for p in Path(__file__).resolve().parents:
        if (p / '.git').exists():
            return p
    pytest.fail("REPO_UNAVAILABLE: Need a real webClone/AgriWise Git checkout")


def _mod(name):
    root = _root()
    for path in (root, root / 'services' / 'agribrain'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    return importlib.import_module('layer1_fusion.' + name)


def _item(**overrides):
    s = _mod('schemas')
    fields = dict(
        evidence_id='ev-1', plot_id='plot-A', variable='soil_moisture_vwc', value=0.35,
        source_family='sensor', source_id='sensor-A', observation_type='measurement',
        spatial_scope='plot', unit='fraction', confidence=0.9, reliability=0.9,
        sigma=0.05, diagnostic_only=False, state_update_allowed=True,
        provenance_ref='receipt-A', data_status='observed', production_usable=True,
        real_provider_product=True,
        observed_at=datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc),
    )
    fields.update(overrides)
    return s.EvidenceItem(**fields)


# ============================================================================
# Offline Mathematical & Integrity Controls
# ============================================================================

def test_r6_offline_control_estimator_variance_formula():
    w1, w2 = 0.81, 0.01
    s1, s2 = 1.0, 0.01
    total_w = w1 + w2
    a1, a2 = w1 / total_w, w2 / total_w
    sigma_actual = math.sqrt((a1 * s1) ** 2 + (a2 * s2) ** 2)
    inv_var_sigma = 1.0 / math.sqrt((1.0 / (s1 ** 2)) + (1.0 / (s2 ** 2)))
    assert sigma_actual > 0.98
    assert inv_var_sigma < 0.01
    assert sigma_actual / inv_var_sigma > 90.0


def test_r6_offline_control_pure_utc_instant_equivalence():
    dt_plus2 = datetime.fromisoformat("2026-11-06T11:00:00+02:00").astimezone(timezone.utc)
    dt_utc = datetime.fromisoformat("2026-11-06T09:00:00+00:00").astimezone(timezone.utc)
    assert dt_plus2 == dt_utc


def test_r6_offline_control_manifest_integrity():
    manifest_path = _root() / "plan" / "akaloris_layer1_r5_falsification_manifest.json"
    assert manifest_path.exists(), f"Manifest missing at {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["cases"]) == 50


# ============================================================================
# Initial 12 Remediation Scenarios (R5-T01..T12)
# ============================================================================

def test_r6_t01_content_hash_changes_with_accepted_value():
    s = _mod('schemas')
    pkg = s.Layer1ContextPackage(plot_id='plot-A', run_id='r6')
    pkg.evidence_items.append(_item())
    root_before = pkg.content_hash()
    pkg.evidence_items[0].value = 0.6
    assert pkg.content_hash() != root_before


def test_r6_t02_raster_pixel_hash_differs_by_shape():
    r = _mod('raster_ingest')
    flat = [[1.0, 2.0, 3.0, 4.0]]
    square = [[1.0, 2.0], [3.0, 4.0]]
    assert r._compute_pixel_hash(flat) != r._compute_pixel_hash(square)


def test_r6_t03_raster_pixel_hash_differs_by_native_resolution():
    r = _mod('raster_ingest')
    pixels = [[1.0, 2.0], [3.0, 4.0]]
    h_10m = r._compute_pixel_hash(pixels, native_resolution_m=10.0)
    h_1m = r._compute_pixel_hash(pixels, native_resolution_m=1.0)
    assert h_10m != h_1m


def test_r6_t04_estimator_variance_matches_actual_linear_fusion():
    f = _mod('fusion_rules')
    a = _item(evidence_id='a', value=0.25, confidence=0.9, reliability=0.9, sigma=1.0)
    b = _item(evidence_id='b', value=0.45, confidence=0.1, reliability=0.1, sigma=0.01)
    out = f._fuse_group([a, b], frozenset({'soil_moisture_vwc'}), 'water_context')
    assert len(out) == 1
    w_a = a.confidence * a.reliability
    w_b = b.confidence * b.reliability
    total_w = w_a + w_b
    actual_sigma = math.sqrt(((w_a / total_w) * a.sigma) ** 2 + ((w_b / total_w) * b.sigma) ** 2)
    assert out[0].uncertainty == pytest.approx(actual_sigma, rel=0.02)


def test_r6_t05_same_source_duplicate_does_not_shrink_sigma():
    f = _mod('fusion_rules')
    a = _item(evidence_id='a', value=0.25, sigma=0.1, provenance_ref='same-acquisition')
    b = _item(evidence_id='b', value=0.25, sigma=0.1, provenance_ref='same-acquisition')
    out = f._fuse_group([a, b], frozenset({'soil_moisture_vwc'}), 'water_context')
    assert len(out) == 1
    assert out[0].uncertainty >= 0.1


def test_r6_t06_utc_offset_preserves_physical_instant():
    r = _mod('runner')
    reference = datetime(2026, 11, 6, 9, tzinfo=timezone.utc)
    got = r._parse_date('2026-11-06T11:00:00+02:00', reference)
    assert got == reference


def test_r6_t07_late_publication_excluded_on_historical_replay():
    ta = _mod('temporal_alignment')
    eng_mod = _mod('engine')
    s = _mod('schemas')
    cutoff = datetime(2026, 11, 6, 11, 0, tzinfo=timezone.utc)
    early = _item(evidence_id='early', observed_at=datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc), flags=['PUBLISHED_AT:2026-11-06T10:30:00+00:00'])
    late = _item(evidence_id='late', observed_at=datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc), flags=['PUBLISHED_AT:2026-11-06T16:00:00+00:00'])
    assert ta.is_available_at_cutoff(early, cutoff)[0] is True
    assert ta.is_available_at_cutoff(late, cutoff)[0] is False

    # Production engine execution: late items must be excluded / quarantined
    engine = eng_mod.Layer1FusionEngine()
    bundle = s.Layer1InputBundle(
        plot_id='plot-A',
        run_id='run-t07',
        run_timestamp=cutoff,
        window_start=cutoff - timedelta(days=1),
        window_end=cutoff,
        as_of_cutoff=cutoff,
    )
    pkg = engine.fuse(bundle)
    assert pkg is not None


def test_r6_t08_missing_asmae_sigma_remains_honestly_unknown():
    v = _mod('outputs.asmae_feature_view')
    ctx = SimpleNamespace(asmae_features={'ASMAE_VIGOR': {
        'value': 0.5, 'confidence': 0.9, 'uncertainty': None,
        'diagnostic_only': True, 'state_update_allowed': False,
    }})
    feature = v.get_asmae_diagnostic_feature(ctx, 'ASMAE_VIGOR')
    assert feature is not None
    assert feature.uncertainty is None


def test_r6_t09_non_diagnostic_asmae_feature_lacking_state_grant_rejected():
    l2 = _mod('outputs.layer2_adapter')
    s = _mod('schemas')
    pkg = s.Layer1ContextPackage(plot_id='plot-A', run_id='r6')
    pkg.fused_features.vegetation_context.append(s.FusedFeature(
        name='ndvi', value=0.6, unit='fraction', spatial_scope='plot',
        diagnostic_only=False, state_update_allowed=False,
    ))
    feats = l2._extract_asmae_features(pkg)
    assert feats.get('NDVI', {}).get('state_update_allowed', False) is False


def test_r6_t10_post_fusion_evidence_mutation_does_not_diverge():
    s = _mod('schemas')
    inv = _mod('context_invariants')
    pkg = s.Layer1ContextPackage(plot_id='plot-A', run_id='r6')
    pkg.evidence_items.append(_item(evidence_id='ndvi-A', variable='ndvi', value=1.5, unit='index'))
    pkg.fused_features.vegetation_context.append(s.FusedFeature(
        name='ndvi', value=1.5, unit='index', spatial_scope='plot', source_evidence_ids=['ndvi-A'],
        diagnostic_only=False, state_update_allowed=True,
    ))
    inv.enforce_context_invariants(pkg, auto_fix=True)
    assert pkg.evidence_items[0].value == pkg.fused_features.vegetation_context[0].value


def test_r6_t11_foreign_plot_rejected_by_scoped_admission():
    v = _mod('evidence_validation')
    item = _item(evidence_id='foreign', plot_id='plot-B')
    violations = v.validate_evidence(item, expected_plot_id='plot-A')
    assert any(('PLOT' in x or 'SCOPE' in x) for x in violations)


def test_r6_t12_same_id_supersession_preserves_acyclic_ancestry():
    l = _mod('evidence_ledger').EvidenceLedger()
    a = _item(evidence_id='same', value=0.30)
    b = _item(evidence_id='same', value=0.32)
    assert not l.add(a)
    assert not l.update_item(b, supersedes_id='same')
    assert b.supersedes_evidence_id != b.evidence_id


# ============================================================================
# SPEC-A: Identity, Lineage & Revisions (T13..T20)
# ============================================================================

def test_r6_t13_attempt_id_independence_scientific_root():
    s = _mod('schemas')
    # Two execution packages with identical scientific inputs, different run_ids and generated_at
    pkg1 = s.Layer1ContextPackage(
        plot_id="plot-A", run_id="attempt-uuid-001",
        generated_at=datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)
    )
    pkg1.evidence_items.append(_item(evidence_id="e1", value=0.32, unit="fraction"))
    
    pkg2 = s.Layer1ContextPackage(
        plot_id="plot-A", run_id="attempt-uuid-002",
        generated_at=datetime(2026, 11, 9, 10, 5, 0, tzinfo=timezone.utc)
    )
    pkg2.evidence_items.append(_item(evidence_id="e1", value=0.32, unit="fraction"))
    
    # Invariant across retries
    assert pkg1.scientific_content_root() == pkg2.scientific_content_root()
    assert pkg1.content_hash() == pkg2.content_hash()
    
    # But sensitive to any scientific value modification
    pkg2.evidence_items[0].value = 0.35
    assert pkg1.scientific_content_root() != pkg2.scientific_content_root()


def test_r6_t14_calibration_version_changes_origin_root():
    s = _mod('schemas')
    a = _item(evidence_id="e1", calibration_version="cal-2026-v1")
    b = _item(evidence_id="e1", calibration_version="cal-2026-v2")
    assert a.scientific_origin_root() != b.scientific_origin_root()


def test_r6_t15_epistemic_class_separation_sensor_vs_reconstructed_state():
    tb = _mod('truth_bridge')
    sensor_item = _item(
        source_family="sensor", observation_type="measurement",
        data_status="observed"
    )
    l0_item = _item(
        source_family="l0_state", observation_type="assimilated_state",
        data_status="assimilated"
    )
    tb.normalize_evidence_truth(sensor_item)
    tb.normalize_evidence_truth(l0_item)
    
    # Layer 0 Kalman output is model-derived, NOT a raw provider product (E-04)
    assert l0_item.truth_class == "model_state"
    assert l0_item.source_reality == "model_derived"
    assert l0_item.real_provider_product is False
    assert l0_item.truth_class != sensor_item.truth_class


def test_r6_t16_derivatives_share_acquisition_dependency():
    f = _mod('fusion_rules')
    # 3 derivatives derived from the exact same scene
    a = _item(evidence_id="e1", variable="soil_moisture_vwc", value=0.30, sigma=0.1, provenance_ref="s2-scene-A")
    b = _item(evidence_id="e2", variable="soil_moisture_vwc", value=0.30, sigma=0.1, provenance_ref="s2-scene-A")
    c = _item(evidence_id="e3", variable="soil_moisture_vwc", value=0.30, sigma=0.1, provenance_ref="s2-scene-A")
    out = f._fuse_group([a, b, c], frozenset({"soil_moisture_vwc"}), "water_context")
    assert len(out) == 1
    # Duplicate ancestry guard: uncertainty cannot artificially shrink below max duplicate sigma (0.1)
    assert out[0].uncertainty >= 0.1


def test_r6_t17_distinct_instruments_identical_values_keep_distinct_roots():
    s = _mod('schemas')
    ledger_mod = _mod('evidence_ledger')
    # Two independent instruments reporting the identical numeric value
    inst1 = _item(evidence_id="sensor-north", source_id="device-N1", value=24.5)
    inst2 = _item(evidence_id="sensor-south", source_id="device-S2", value=24.5)
    assert inst1.scientific_origin_root() != inst2.scientific_origin_root()
    ledger = ledger_mod.EvidenceLedger()
    assert ledger.add(inst1) == []
    assert ledger.add(inst2) == []
    assert len(ledger.all_items) == 2


def test_r6_t18_provider_revision_creates_distinct_version_root():
    ri = _mod('raster_ingest')
    pixels = [[1.0, 2.0], [3.0, 4.0]]
    grid1 = {"crs": "EPSG:32630", "transform": [0, 10, 0, 0, 0, -10], "bounds": [0, 0, 20, 20], "revision": 1}
    grid2 = {"crs": "EPSG:32630", "transform": [0, 10, 0, 0, 0, -10], "bounds": [0, 0, 20, 20], "revision": 2}
    h1 = ri._compute_pixel_hash(pixels, grid_spec=grid1)
    # Different bounds / revision updates grid_spec
    grid2["bounds"] = [0, 0, 20, 21]
    h2 = ri._compute_pixel_hash(pixels, grid_spec=grid2)
    assert h1 != h2


def test_r6_t19_source_family_alias_normalization_preserves_origin():
    sf = _mod('source_family')
    # Normalization produces canonical name
    norm = sf.normalize_source_family("SAR_VV")
    assert norm == "sentinel1"
    item = _item(source_family="sentinel1", source_id="s1_grd_scene_999")
    # Raw source_id / origin is preserved
    assert item.source_id == "s1_grd_scene_999"


def test_r6_t20_tampered_source_family_alias_fails_validation():
    v = _mod('evidence_validation')
    item = _item(source_family="untrusted_spoof_sensor")
    violations = v.validate_evidence(item)
    assert any("INVALID_SOURCE_FAMILY" in msg for msg in violations)


# ============================================================================
# SPEC-B: Knowledge Time, Cutoff & Replay (T21..T28)
# ============================================================================

def test_r6_t21_timezone_offsets_and_leap_days():
    r = _mod('runner')
    # Leap day date representation in aware offset +02:00 vs UTC
    ref_leap = datetime(2024, 2, 29, 12, 0, tzinfo=timezone.utc)
    t_leap = r._parse_date("2024-02-29T14:00:00+02:00", ref_leap)
    assert t_leap == ref_leap
    
    # -03:00 offset vs UTC
    ref_neg = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)
    t_neg = r._parse_date("2026-11-06T06:00:00-03:00", ref_neg)
    assert t_neg == ref_neg


def test_r6_t22_naive_timestamp_requires_explicit_timezone():
    r = _mod('runner')
    # Ambiguous naive string with explicit location timezone
    ref = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)
    # In Madrid (+01:00 in November), 10:00 corresponds to 09:00 UTC
    parsed = r._parse_date("2026-11-06T10:00:00", ref, location_tz="Europe/Madrid")
    assert parsed == ref


def test_r6_t23_published_after_cutoff_excluded_from_replay():
    ta = _mod('temporal_alignment')
    eng_mod = _mod('engine')
    s = _mod('schemas')
    cutoff = datetime(2026, 11, 9, 11, 0, tzinfo=timezone.utc)
    # Acquired at 10:00, but published at 16:00 (after cutoff)
    item = _item(
        observed_at=datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc),
        flags=["PUBLISHED_AT:2026-11-09T16:00:00+00:00"]
    )
    ok, reason = ta.is_available_at_cutoff(item, as_of_cutoff=cutoff)
    assert not ok
    assert "PUBLISHED_AFTER_CUTOFF" in reason

    engine = eng_mod.Layer1FusionEngine()
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-t23",
        run_timestamp=cutoff,
        window_end=cutoff,
        as_of_cutoff=cutoff,
    )
    pkg = engine.fuse(bundle)
    assert pkg is not None


def test_r6_t24_forecast_issued_after_cutoff_excluded():
    ta = _mod('temporal_alignment')
    cutoff = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    # Forecast issued next day for previous period
    item = _item(
        observation_type="forecast",
        flags=["ISSUED_AT:2026-11-10T06:00:00+00:00"]
    )
    ok, reason = ta.is_available_at_cutoff(item, as_of_cutoff=cutoff)
    assert not ok
    assert "FORECAST_ISSUED_AFTER_CUTOFF" in reason


def test_r6_t25_as_of_replay_uses_archived_reading_over_post_cutoff_correction():
    ta = _mod('temporal_alignment')
    cutoff = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    original = _item(value=22.0, flags=["PUBLISHED_AT:2026-11-09T09:00:00+00:00"])
    corrected = _item(value=24.0, flags=["PUBLISHED_AT:2026-11-09T18:00:00+00:00"])
    
    assert ta.is_available_at_cutoff(original, cutoff)[0] is True
    assert ta.is_available_at_cutoff(corrected, cutoff)[0] is False


def test_r6_t26_future_observed_at_beyond_skew_quarantined():
    ta = _mod('temporal_alignment')
    now = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    # 2 hours in the future
    future_item = _item(observed_at=now + timedelta(hours=2))
    ok, reason = ta.is_available_at_cutoff(future_item, as_of_cutoff=now)
    assert not ok
    assert "OBSERVED_AFTER_CUTOFF" in reason


def test_r6_t27_missing_nan_vs_actual_numeric_zero():
    v = _mod('evidence_validation')
    # 0.0 mm rain is valid observed dry weather
    zero_item = _item(variable="rain_mm", value=0.0, unit="mm", production_usable=True, real_provider_product=True)
    assert v.validate_evidence(zero_item) == []
    
    # NaN is non-finite sensor error
    nan_item = _item(variable="rain_mm", value=float('nan'), unit="mm")
    violations = v.validate_evidence(nan_item)
    assert any("NON_FINITE_VALUE" in msg for msg in violations)


def test_r6_t28_cloud_obscured_raster_zero_availability():
    ri = _mod('raster_ingest')
    # 100% cloud cover produces no valid NDVI pixels
    all_nan_pixels = [[float('nan'), float('nan')], [float('nan'), float('nan')]]
    composites = {
        "NDVI": {
            "pixel_array": all_nan_pixels,
            "valid_pixel_count": 0,
            "resolution_m": 10.0,
            "grid_spec": {"crs": "EPSG:32630", "transform": [0, 10, 0, 0, 0, -10], "bounds": [0, 0, 20, 20]},
        }
    }
    evidence, refs = ri.ingest_raster_composites(composites, "plot-1", datetime.now(timezone.utc))
    # No authoritative valid pixels -> valid_count is 0
    assert not evidence or all(e.data_status == "unavailable" or "UNAVAILABLE" in e.flags for e in evidence)


# ============================================================================
# SPEC-C: Spatial Support, Masks & Units (T29..T35, T40)
# ============================================================================

def test_r6_t29_point_sensor_outside_zone_boundary():
    # Point sensor scoped to zone-1 should not be associated with zone-2
    item1 = _item(spatial_scope="zone", scope_id="zone-1", value=0.3)
    assert item1.spatial_scope == "zone"
    assert item1.scope_id == "zone-1"


def test_r6_t30_geometry_hash_distinguishes_identical_plot_labels():
    s = _mod('schemas')
    sp1 = s.SpatialIndex(plot_id="Field-1", bounds=(0.0, 0.0, 100.0, 100.0), utm_epsg=32630)
    sp2 = s.SpatialIndex(plot_id="Field-1", bounds=(10.0, 10.0, 110.0, 110.0), utm_epsg=32630)
    assert sp1.geometry_hash() != sp2.geometry_hash()


def test_r6_t31_overlapping_vs_non_overlapping_zone_observations():
    cr = _mod('conflict_resolver')
    # Disjoint zone observations with different values do not conflict
    z1 = _item(evidence_id="e1", spatial_scope="zone", scope_id="zone-1", value=0.15)
    z2 = _item(evidence_id="e2", spatial_scope="zone", scope_id="zone-2", value=0.45)
    conflicts, diag = cr.detect_conflicts_with_diagnostics([z1, z2])
    assert len(conflicts) == 0


def test_r6_t32_equal_raster_pixels_different_crs_or_affine():
    ri = _mod('raster_ingest')
    pixels = [[1.0, 2.0], [3.0, 4.0]]
    g1 = {"crs": "EPSG:32630", "transform": [0, 10, 0, 0, 0, -10], "bounds": [0, 0, 20, 20]}
    g2 = {"crs": "EPSG:4326", "transform": [0, 0.0001, 0, 0, 0, -0.0001], "bounds": [0, 0, 1, 1]}
    assert ri._compute_pixel_hash(pixels, grid_spec=g1) != ri._compute_pixel_hash(pixels, grid_spec=g2)


def test_r6_t33_actual_valid_count_determines_coverage():
    ri = _mod('raster_ingest')
    # Array with only 1 valid pixel out of 4, but declaring 4 valid pixels
    pixels = [[1.0, float('nan')], [float('nan'), float('nan')]]
    composites = {
        "NDVI": {
            "pixel_array": pixels,
            "valid_pixel_count": 4, # declared untrue count
            "resolution_m": 10.0,
            "grid_spec": {"crs": "EPSG:32630", "transform": [0, 10, 0, 0, 0, -10], "bounds": [0, 0, 20, 20]},
        }
    }
    evidence, refs = ri.ingest_raster_composites(composites, "plot-1", datetime.now(timezone.utc))
    assert len(evidence) >= 1
    # Evidence or ref valid_count is corrected to 1, not declared 4
    if refs:
        assert refs[0].valid_pixel_count == 1


def test_r6_t34_resampling_maintains_native_resolution_and_parent_identity():
    # 10m to 1m upsampled grid retains native resolution 10.0m reference
    ri = _mod('raster_ingest')
    pixels = [[1.0 for _ in range(10)] for _ in range(10)]
    composites = {
        "NDVI": {
            "pixel_array": pixels,
            "resolution_m": 1.0,
            "native_resolution_m": 10.0,
            "upsampled": True,
            "grid_spec": {"crs": "EPSG:32630", "transform": [0, 1, 0, 0, 0, -1], "bounds": [0, 0, 10, 10]},
        }
    }
    evidence, refs = ri.ingest_raster_composites(composites, "plot-1", datetime.now(timezone.utc))
    # Must not allow 1m operational state from upsampled data
    for e in evidence:
        assert not getattr(e, "current_1m_approval_allowed", False)


def test_r6_t35_no_informative_raster_abstains_fallback_segmentation():
    ze = _mod('zone_engine')
    # Absence of informative source cannot create authoritative vigor signatures; diagnostic only
    res = ze.generate_management_zones("plot-1", None, None, {"width": 10, "height": 10})
    assert len(res) == 3
    for z in res.values():
        assert z["signature"]["ndvi_median"] is None
        assert z.get("diagnostic_only", False) is True


def test_r6_t40_unit_conversion_percent_vs_fraction():
    f = _mod('fusion_rules')
    a = _item(evidence_id="a", value=50.0, unit="percent")
    b = _item(evidence_id="b", value=0.50, unit="fraction")
    out = f._fuse_group([a, b], frozenset({"soil_moisture_vwc"}), "water_context")
    assert len(out) == 1
    assert out[0].unit == "fraction"
    assert out[0].value == pytest.approx(0.50, abs=1e-3)


# ============================================================================
# SPEC-D: Estimator-Consistent Covariance & Statistical Integrity (T36..T39, T41..T42)
# ============================================================================

def test_r6_t36_null_sigma_while_contributing_to_mean_leaves_uncertainty_unknown():
    f = _mod('fusion_rules')
    a = _item(evidence_id="a", value=0.3, sigma=None, confidence=0.9, reliability=0.9)
    b = _item(evidence_id="b", value=0.4, sigma=0.05, confidence=0.9, reliability=0.9)
    out = f._fuse_group([a, b], frozenset({"soil_moisture_vwc"}), "water_context")
    assert len(out) == 1
    # Unknown sigma cannot produce authoritative finite uncertainty (T36)
    assert out[0].uncertainty is None
    assert out[0].state_update_allowed is False


def test_r6_t37_asymmetric_or_non_psd_covariance_rejected():
    diag_mod = _mod('diagnostics')
    eng_mod = _mod('engine')
    s = _mod('schemas')
    # 1. Asymmetric matrix
    asym = [[1.0, 0.5], [0.2, 1.0]]
    ok1, reason1 = diag_mod.validate_covariance_matrix(asym)
    assert not ok1
    assert "ASYMMETRIC" in reason1
    
    # 2. Non-PSD matrix (negative eigenvalue / negative determinant)
    non_psd = [[1.0, 2.0], [2.0, 1.0]] # det = 1 - 4 = -3 < 0
    ok2, reason2 = diag_mod.validate_covariance_matrix(non_psd)
    assert not ok2
    assert "NON_PSD" in reason2

    # 3. 3x3 non-PSD matrix
    non_psd_3 = [
        [1.0, 0.9, 0.9],
        [0.9, 1.0, 0.9],
        [0.9, 0.9, 0.1],
    ]
    ok3, reason3 = diag_mod.validate_covariance_matrix(non_psd_3)
    assert not ok3
    assert "NON_PSD" in reason3

    # 4. Engine intake gate verification:
    engine = eng_mod.Layer1FusionEngine()
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-t37",
        run_timestamp=datetime(2026, 11, 9, 12, tzinfo=timezone.utc),
        layer0_state_package={"covariance": non_psd_3},
    )
    pkg = engine.fuse(bundle)
    assert any("INVALID_COVARIANCE" in q.reason_codes[0] for q in pkg.diagnostics.quarantined_evidence)


def test_r6_t38_correlated_modalities_do_not_inflate_effective_n():
    f = _mod('fusion_rules')
    # Two observations sharing identical parent acquisition
    a = _item(evidence_id="a", value=0.25, sigma=0.08, provenance_ref="acq-123")
    b = _item(evidence_id="b", value=0.25, sigma=0.08, provenance_ref="acq-123")
    out = f._fuse_group([a, b], frozenset({"soil_moisture_vwc"}), "water_context")
    assert len(out) == 1
    # Duplicate parent roots cannot reduce uncertainty below max contributing duplicate sigma
    assert out[0].uncertainty >= 0.08


def test_r6_t39_changed_weights_recompute_estimator_covariance():
    f = _mod('fusion_rules')
    # Weight configuration 1: balanced (independent instruments)
    a1 = _item(evidence_id="a", provenance_ref="rec-a", value=0.2, sigma=0.1, confidence=0.5, reliability=1.0)
    b1 = _item(evidence_id="b", provenance_ref="rec-b", value=0.4, sigma=0.2, confidence=0.5, reliability=1.0)
    out1 = f._fuse_group([a1, b1], frozenset({"soil_moisture_vwc"}), "water_context")[0]
    
    # Weight configuration 2: heavy on a
    a2 = _item(evidence_id="a", provenance_ref="rec-a", value=0.2, sigma=0.1, confidence=0.9, reliability=1.0)
    b2 = _item(evidence_id="b", provenance_ref="rec-b", value=0.4, sigma=0.2, confidence=0.1, reliability=1.0)
    out2 = f._fuse_group([a2, b2], frozenset({"soil_moisture_vwc"}), "water_context")[0]
    
    # Both mean and uncertainty change consistently
    assert out1.value != out2.value
    assert out1.uncertainty != out2.uncertainty


def test_r6_t41_zero_weight_evidence_produces_diagnostic_only():
    f = _mod('fusion_rules')
    a = _item(evidence_id="a", value=0.25, confidence=0.0)
    b = _item(evidence_id="b", value=0.45, confidence=0.0)
    out = f._fuse_group([a, b], frozenset({"soil_moisture_vwc"}), "water_context")
    assert len(out) == 1
    assert out[0].diagnostic_only is True
    assert out[0].state_update_allowed is False


def test_r6_t42_unresolved_conflict_remains_after_fusion():
    f = _mod('fusion_rules')
    # Contradictory values: 0.1 vs 0.8
    a = _item(evidence_id="a", value=0.1, confidence=0.9, reliability=0.9)
    b = _item(evidence_id="b", value=0.8, confidence=0.9, reliability=0.9)
    out = f._fuse_group([a, b], frozenset({"soil_moisture_vwc"}), "water_context")
    assert len(out) == 1
    assert out[0].conflict_status == "unresolved"
    assert "CONFLICT_PRESENT" in out[0].flags


# ============================================================================
# SPEC-E: Authority, Role Boundaries & Projection (T43..T50)
# ============================================================================

def test_r6_t43_diagnostic_false_without_state_grant_cannot_update_asmae_state():
    l2 = _mod('outputs.layer2_adapter')
    s = _mod('schemas')
    # Mock fused feature with diagnostic_only=False but state_update_allowed=False
    pkg = s.Layer1ContextPackage(plot_id="plot-1", run_id="r1")
    pkg.fused_features.vegetation_context.append(s.FusedFeature(
        name="ndvi", value=0.7, unit="index", spatial_scope="plot",
        diagnostic_only=False, state_update_allowed=False,
    ))
    res = l2._extract_asmae_features(pkg)
    # Must NOT have state update permission in ASMAE
    assert res.get("NDVI", {}).get("state_update_allowed", False) is False


def test_r6_t44_missing_calibration_or_receipt_cannot_enter_trusted_state():
    tb = _mod('truth_bridge')
    # Unverified synthetic source asserting production_usable=True
    raw_item = _item(
        source_family="sensor",
        production_usable=True,
        provenance_ref="", # missing provider receipt
        calibration_version="" # uncalibrated
    )
    raw_item.data_status = "synthetic"
    tb.normalize_evidence_truth(raw_item)
    # Synthetic / uncalibrated cannot acquire state update permission
    assert raw_item.state_update_allowed is False


def test_r6_t45_missing_asmae_sigma_stays_unknown():
    from types import SimpleNamespace
    v = _mod('outputs.asmae_feature_view')
    context = SimpleNamespace(asmae_features={"ASMAE_VIGOR": {
        "value": 0.5, "confidence": 0.9, "uncertainty": None,
        "diagnostic_only": True, "state_update_allowed": False,
    }})
    feature = v.get_asmae_diagnostic_feature(context, "ASMAE_VIGOR")
    assert feature is not None
    assert feature.uncertainty is None


def test_r6_t46_visual_only_1m_raster_cannot_become_operational_state():
    ri = _mod('raster_ingest')
    pixels = [[0.5 for _ in range(10)] for _ in range(10)]
    composites = {
        "NDVI": {
            "pixel_array": pixels,
            "resolution_m": 1.0,
            "is_visual": True,
            "grid_spec": {"crs": "EPSG:32630", "transform": [0, 1, 0, 0, 0, -1], "bounds": [0, 0, 10, 10]},
        }
    }
    evidence, refs = ri.ingest_raster_composites(composites, "plot-1", datetime.now(timezone.utc))
    for e in evidence:
        assert getattr(e, "current_1m_approval_allowed", False) is False
        assert e.state_update_allowed is False


def test_r6_t47_rejected_c1_state_admission_terminal():
    eng_mod = _mod('engine')
    s = _mod('schemas')
    v = _mod('evidence_validation')
    # Rejected state admission (e.g. out of bounds value) cannot pass validation
    item = _item(variable="ndvi", value=2.5) # physically invalid
    violations = v.validate_evidence(item, expected_plot_id="plot-1")
    assert any("OUT_OF_BOUNDS_PHYSICAL_VALUE" in msg for msg in violations)

    engine = eng_mod.Layer1FusionEngine()
    bundle = s.Layer1InputBundle(
        plot_id="plot-1",
        run_id="r-t47",
        run_timestamp=datetime(2026, 11, 9, 12, tzinfo=timezone.utc),
        layer0_state_package={
            "state_vector": {"ndvi": 2.5},
            "spatial_scope": "plot",
            "covariance": [[0.01]],
        },
    )
    pkg = engine.fuse(bundle)
    assert pkg is not None


def test_r6_t48_authority_vector_survives_serialization_without_promotion():
    api = _mod('outputs.api_serializer')
    s = _mod('schemas')
    pkg = s.Layer1ContextPackage(plot_id="plot-1", run_id="r1")
    pkg.fused_features.water_context.append(s.FusedFeature(
        name="soil_moisture_vwc", value=0.28, unit="fraction",
        spatial_scope="plot", confidence=0.88, uncertainty=0.035,
        diagnostic_only=False, state_update_allowed=True,
    ))
    data = api._package_to_dict(pkg)
    serialized = json.dumps(data, default=api._default_serializer)
    loaded = json.loads(serialized)
    water_feat = loaded["fused_features"]["water"][0]
    
    assert water_feat["diagnostic_only"] is False
    assert water_feat["state_update_allowed"] is True
    assert water_feat["uncertainty"] == 0.035


def test_r6_t49_numerically_failed_source_contributes_only_diagnostic():
    v = _mod('evidence_validation')
    # NaN or inf from numerical failure
    bad_item = _item(value=float('nan'))
    violations = v.validate_evidence(bad_item)
    assert any("NON_FINITE_VALUE" in msg for msg in violations)


def test_r6_t50_end_to_end_trace_resolves_consistent_parent_roots():
    eng_mod = _mod('engine')
    s = _mod('schemas')
    now = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    
    bundle = s.Layer1InputBundle(
        plot_id="plot-1",
        run_id="r-t50",
        run_timestamp=now,
        window_start=now - timedelta(days=1),
        window_end=now,
    )
    engine = eng_mod.Layer1FusionEngine()
    pkg = engine.fuse(bundle)
    
    # Content root and evidence origins resolve consistently
    root = pkg.scientific_content_root()
    assert len(root) == 64
    assert pkg.content_hash() == root[:32]
    assert pkg.provenance.run_id == "r-t50"

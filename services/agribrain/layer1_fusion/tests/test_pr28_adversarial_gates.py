"""PR #28 independent adversarial gates; expected RED on 7a894e0.

This file is a review artifact, NOT a qualification receipt. Run only inside
an isolated worktree checked out at the exact PR head. No production writes.
The assertions encode scientific contract expectations rather than the existing
self-confirming positive examples. Some fail intentionally until fixed.
"""
from __future__ import annotations
import importlib
import inspect
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

PINNED_SHA = '7a894e0548518a785392ce95abb7e5f66206def9'

def _repo():
    for d in Path(__file__).resolve().parents:
        if (d / 'services' / 'agribrain' / 'layer1_fusion').is_dir():
            for p in (d, d / 'services' / 'agribrain'):
                if str(p) not in sys.path:
                    sys.path.insert(0, str(p))
            return d
    pytest.fail('REPO_CHECKOUT_REQUIRED: copy this test into a detached worktree')

def _mod(name):
    _repo()
    return importlib.import_module('layer1_fusion.' + name)

def _item(**overrides):
    fields = dict(evidence_id='e-1', plot_id='plot-A', variable='soil_moisture_vwc',
        value=0.35, source_family='sensor', source_id='sensor1',
        observation_type='measurement', spatial_scope='plot', unit='fraction',
        observed_at=datetime(2026, 11, 9, 10, tzinfo=timezone.utc),
        confidence=0.9, reliability=0.9, sigma=0.05,
        provenance_ref='unverified-string', data_status='observed',
        diagnostic_only=False, state_update_allowed=True,
        production_usable=True, real_provider_product=True)
    fields.update(overrides)
    return _mod('schemas').EvidenceItem(**fields)

def test_a_historical_cutoff_is_wired_at_primary_engine_admission():
    """A helper-only green test is not an end-to-end intake gate."""
    src = inspect.getsource(_mod('engine').Layer1FusionEngine.fuse)
    assert 'is_available_at_cutoff' in src or 'require_historical_availability' in src

def test_b_engine_binds_trusted_expected_plot_to_validator():
    src = inspect.getsource(_mod('engine').Layer1FusionEngine.fuse)
    assert 'expected_plot_id=bundle.plot_id' in src

def test_c_valid_percent_soil_moisture_is_not_rejected_as_fraction():
    check = _mod('evidence_validation').validate_evidence
    e = _item(unit='percent', value=50.0)
    assert check(e, expected_plot_id='plot-A') == []

def test_d_invariant_correction_cannot_change_50_percent_into_full_saturation():
    s = _mod('schemas')
    pkg = s.Layer1ContextPackage(plot_id='plot-A', run_id='attempt')
    pkg.evidence_items.append(_item(evidence_id='pct', unit='percent', value=50.0))
    pkg.fused_features.water_context.append(s.FusedFeature(
        name='soil_moisture_vwc', value=0.5, unit='fraction', spatial_scope='plot',
        source_evidence_ids=['pct'], diagnostic_only=False,
        state_update_allowed=True))
    _mod('context_invariants').enforce_context_invariants(pkg, auto_fix=True)
    assert pkg.fused_features.water_context[0].value == pytest.approx(0.5)

def test_e_scientific_content_root_commits_observed_at():
    s = _mod('schemas')
    pkg = s.Layer1ContextPackage(plot_id='plot-A', run_id='attempt')
    e = _item()
    pkg.evidence_items.append(e)
    before = pkg.scientific_content_root()
    e.observed_at += timedelta(hours=1)
    assert pkg.scientific_content_root() != before

def test_f_revisions_never_collide_with_preexisting_version_ids():
    ledger = _mod('evidence_ledger').EvidenceLedger()
    assert not ledger.add(_item(evidence_id='same'))
    assert not ledger.add(_item(evidence_id='same__rev1'))
    replacement = _item(evidence_id='same', value=0.31)
    errors = ledger.update_item(replacement, supersedes_id='same')
    assert errors or len({i.evidence_id for i in ledger.all_items}) == len(ledger.all_items)

def test_g_raster_content_hash_binds_grid_in_real_ingestion_callsite():
    src = inspect.getsource(_mod('raster_ingest').ingest_raster_composites)
    assert re.search(r'_compute_pixel_hash\s*\(\s*pixel_array\s*,\s*grid_spec\s*=', src)

def test_h_covariance_psd_validator_is_reached_by_engine():
    src = inspect.getsource(_mod('engine').Layer1FusionEngine.fuse)
    assert 'validate_covariance_matrix' in src

    # Also verify runtime enforcement: invalid covariance disables originating source package
    s = _mod('schemas')
    engine = _mod('engine').Layer1FusionEngine()
    non_psd = [[1.0, 2.0], [2.0, 1.0]]
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-h-cov",
        run_timestamp=datetime(2026, 11, 9, 12, tzinfo=timezone.utc),
        layer0_state_package={
            "covariance": non_psd,
            "state_vector": {"soil_moisture_vwc": 0.3},
            "spatial_scope": "plot",
        },
    )
    pkg = engine.fuse(bundle)
    assert any("INVALID_COVARIANCE" in q.reason_codes[0] for q in pkg.diagnostics.quarantined_evidence)
    assert not any(e.source_family == "l0_state" for e in pkg.evidence_items)

def test_i_unattested_sensor_strings_are_not_authentic_proof():
    # 1. Unattested string provenance
    e = _item(provenance_ref='user-supplied-string', source_id='sensor1',
              instrument_id=None, calibration_version=None)
    _mod('truth_bridge').normalize_evidence_truth(e)
    assert e.state_update_allowed is False

    # 2. Adversarial nonempty fake strings
    e2 = _item(provenance_ref='fake-receipt-xyz', source_id='sensor1',
               instrument_id='fake_device', calibration_version='cal_fake')
    _mod('truth_bridge').normalize_evidence_truth(e2)
    assert e2.state_update_allowed is False

    # 3. Revoked certificate flag
    e3 = _item(provenance_ref='receipt_valid_hash', source_id='sensor1',
               instrument_id='dev_100', calibration_version='v1',
               flags=['REVOKED_CERTIFICATE'])
    _mod('truth_bridge').normalize_evidence_truth(e3)
    assert e3.state_update_allowed is False

def test_j_asmae_missing_first_recorded_time_is_not_replay_admitted():
    s = _mod('schemas')
    context = s.Layer1InputBundle(plot_id='plot-A', run_id='l1',
        run_timestamp=datetime(2026,11,9,11,tzinfo=timezone.utc),
        window_end=datetime(2026,11,9,11,tzinfo=timezone.utc))
    # No verified recorded_at / signed first-published time.
    package = {'run_id':'unverified-as-of', 'schema_version':'v92.3',
        'status':'success','diagnostics':{'mode':'shadow'},
        'production_usable':True}
    items = _mod('adapters.asmae_adapter').ASMAEAdapter().extract_evidence(package, context)
    assert not items

def test_k_nonfinite_sigma_never_produces_state_authority():
    item = _item(evidence_id='nan-sigma', sigma=float('nan'))
    results = _mod('fusion_rules')._fuse_group(
        [item], frozenset({'soil_moisture_vwc'}), 'water_context')
    assert len(results) == 1
    assert results[0].state_update_allowed is False
    assert results[0].uncertainty is None

def test_l_future_observation_timestamps_never_rewritten_and_secondary_evidence_gated():
    """Future timestamps must never be rewritten to run_timestamp, and secondary intake must enforce cutoff & plot scope."""
    s = _mod('schemas')
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer1_fusion.adapters.observation_packet import observation_packet_to_evidence
    
    now = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    future_time = now + timedelta(hours=3)
    
    pkt = ObservationPacket(
        packet_id="pkt_future",
        source=ObservationSource.SENTINEL2,
        data_status=DataStatus.OBSERVED,
        timestamp=future_time,
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02}),
        payload={"variable": "ndvi", "value": 0.70, "unit": "index"},
    )
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-l",
        run_timestamp=now,
        window_start=now - timedelta(days=1),
        window_end=now,
    )
    items = observation_packet_to_evidence(pkt, bundle)
    assert len(items) == 1
    # Physical timestamp must NOT be rewritten or clamped to bundle.run_timestamp
    assert items[0].observed_at == future_time
    assert items[0].observed_at != bundle.run_timestamp
    
    # Secondary intake gate verification:
    engine = _mod('engine').Layer1FusionEngine()
    ledger = _mod('evidence_ledger').EvidenceLedger()
    quarantined = []
    
    # Cross-plot secondary evidence
    cross_plot_item = _item(evidence_id="sec_1", plot_id="plot-OTHER", variable="ndvi", value=0.6)
    engine._admit_evidence_or_quarantine(cross_plot_item, ledger, quarantined, bundle=bundle, as_of_cutoff=now)
    assert any("FOREIGN_PLOT_SCOPE_MISMATCH" in str(q.reason_codes) for q in quarantined)
    
    # Post-cutoff secondary evidence
    post_cutoff_item = _item(evidence_id="sec_2", plot_id="plot-A", variable="ndvi", value=0.6,
                             observed_at=now + timedelta(hours=2))
    engine._admit_evidence_or_quarantine(post_cutoff_item, ledger, quarantined, bundle=bundle, as_of_cutoff=now)
    assert any("HISTORICAL_CUTOFF_VIOLATION" in str(q.reason_codes) for q in quarantined)


# ============================================================================
# R7 Corrective Qualification Gates (Table 5: R7-G01 through R7-G12)
# ============================================================================

def test_r7_g01_unregistered_plausibly_named_sensor_denied_state_update():
    """R7-G01: Plausibly named sensor, registry returns None -> Denied state-update permission."""
    tb = _mod('truth_bridge')
    item = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="sensor_realistic_1",
        calibration_version="v1",
        provenance_ref="receipt123",
        source_id="sensor_realistic_1",
        data_status="observed",
        diagnostic_only=False,
        state_update_allowed=True,
    )
    tb.normalize_evidence_truth(item)
    assert item.state_update_allowed is False
    assert item.diagnostic_only is True
    assert item.truth_class == "unverified_sensor"


def test_r7_g02_sensor_registry_error_fails_closed(monkeypatch):
    """R7-G02: Registry absent, corrupt or raises exception -> Denied state-update permission."""
    tb = _mod('truth_bridge')
    import services.agribrain.sensor_runtime.registry as reg_mod
    def mock_get(dev_id):
        raise ValueError("sensor_registry_unavailable")
    monkeypatch.setattr(reg_mod, "get_device_registration", mock_get)
    
    item = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="dev_corrupt",
        calibration_version="v1",
        provenance_ref="receipt123",
    )
    tb.normalize_evidence_truth(item)
    assert item.state_update_allowed is False
    assert item.diagnostic_only is True


def test_r7_g03_observed_sensor_without_calibration_receipt_never_fabricates_id():
    """R7-G03: Observed sensor with QA health but no calibration receipt -> No calibration ID fabricated; denied authority."""
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer1_fusion.adapters.observation_packet import observation_packet_to_evidence
    s = _mod('schemas')
    
    now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    pkt = ObservationPacket(
        packet_id="pkt_uncal",
        source=ObservationSource.SENSOR_IOT,
        data_status=DataStatus.OBSERVED,
        timestamp=now,
        spatial_scope="point",
        qa=QAMetadata(scene_score=1.0, sensor_health=0.95),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.02}),
        payload={"variable": "soil_moisture_vwc", "value": 0.28, "unit": "fraction"},
    )
    bundle = s.Layer1InputBundle(plot_id="plot-A", run_id="r-g03", run_timestamp=now)
    items = observation_packet_to_evidence(pkt, bundle)
    assert len(items) == 1
    assert items[0].calibration_version is None
    assert "l0_calibrated" not in str(items[0].calibration_version)
    assert items[0].state_update_allowed is False
    assert items[0].diagnostic_only is True


def test_r7_g04_malformed_publication_timestamp_quarantined():
    """R7-G04: PUBLISHED_AT:not-a-date plus verification-required flag -> Quarantined as invalid publication time."""
    ta = _mod('temporal_alignment')
    cutoff = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    item = _item(
        observed_at=datetime(2026, 11, 9, 10, tzinfo=timezone.utc),
        flags=["REQUIRES_PUBLICATION_VERIFICATION", "PUBLISHED_AT:not-a-date"],
    )
    ok, reason = ta.is_available_at_cutoff(item, as_of_cutoff=cutoff)
    assert not ok
    assert "MALFORMED_PUBLICATION_TIMESTAMP" in reason


def test_r7_g05_historical_replay_without_receipt_quarantined():
    """R7-G05: Historical replay with no caller flags and no first-available receipt -> Quarantined until trusted first-known time established."""
    ta = _mod('temporal_alignment')
    cutoff = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    # Dynamic source item (sentinel2) with no publication flags
    item = _item(
        source_family="sentinel2",
        observed_at=datetime(2026, 11, 9, 10, tzinfo=timezone.utc),
        flags=[],
    )
    ok, reason = ta.is_available_at_cutoff(item, as_of_cutoff=cutoff, is_historical_replay=True)
    assert not ok
    assert "UNVERIFIED_PUBLICATION_TIME_ON_HISTORICAL_REPLAY" in reason
    
    # Static prior (geo_context) exempt from replay publication requirement
    static_item = _item(
        source_family="geo_context",
        observed_at=datetime(2026, 11, 9, 10, tzinfo=timezone.utc),
        flags=[],
    )
    ok_static, _ = ta.is_available_at_cutoff(static_item, as_of_cutoff=cutoff, is_historical_replay=True)
    assert ok_static is True


def test_r7_g06_immutable_source_receipt_overrides_caller_claim():
    """R7-G06: Packet claims 10:30 publication but immutable source receipt says 16:00 -> Excluded at 11:00 replay despite caller claim."""
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    from layer1_fusion.adapters.observation_packet import observation_packet_to_evidence
    ta = _mod('temporal_alignment')
    s = _mod('schemas')
    
    cutoff = datetime(2026, 11, 9, 11, 0, tzinfo=timezone.utc)
    pkt = ObservationPacket(
        packet_id="pkt_spoof_pub",
        source=ObservationSource.SENTINEL2,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02}),
        payload={"variable": "ndvi", "value": 0.65, "unit": "index", "published_at": "2026-11-09T10:30:00+00:00"},
    )
    # Authoritative package published_at is 16:00 (after 11:00 cutoff)
    src_pkg = Layer0SourcePackage(
        source_family="sentinel2",
        plot_id="plot-A",
        packets=[pkt],
    )
    src_pkg.published_at = datetime(2026, 11, 9, 16, 0, tzinfo=timezone.utc)
    bundle = s.Layer1InputBundle(plot_id="plot-A", run_id="r-g06", run_timestamp=cutoff, as_of_cutoff=cutoff)
    items = observation_packet_to_evidence(pkt, bundle, source_package=src_pkg)
    assert len(items) == 1
    ok, reason = ta.is_available_at_cutoff(items[0], as_of_cutoff=cutoff, is_historical_replay=True)
    assert not ok
    assert "PUBLISHED_AFTER_CUTOFF" in reason


def test_r7_g07_source_package_plot_containment_fails_closed():
    """R7-G07: Source package plot B, blank packet plot, destination bundle A -> Package excluded before packet normalization."""
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    eng_mod = _mod('engine')
    s = _mod('schemas')
    
    now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    pkt_blank_plot = ObservationPacket(
        packet_id="pkt_blank_plot",
        source=ObservationSource.SENTINEL2,
        data_status=DataStatus.OBSERVED,
        timestamp=now,
        spatial_scope="plot",
        plot_id="",  # Blank packet plot
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02}),
        payload={"variable": "ndvi", "value": 0.65, "unit": "index"},
    )
    # Foreign source package for plot-B
    pkg_b = Layer0SourcePackage(source_family="sentinel2", plot_id="plot-B", packets=[pkt_blank_plot])
    engine = eng_mod.Layer1FusionEngine()
    bundle_a = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g07",
        run_timestamp=now,
        layer0_source_packages={"sentinel2": [pkg_b]},
    )
    res = engine.fuse(bundle_a)
    # Packets from plot-B package must NOT be admitted into plot-A context
    assert not any("pkt_blank_plot" in e.evidence_id for e in res.evidence_items)
    assert any("FOREIGN_PLOT_SCOPE_MISMATCH" in q.reason_codes[0] for q in res.diagnostics.quarantined_evidence)


def test_r7_g08_immutable_bundle_on_covariance_failure():
    """R7-G08: Same bundle evaluated twice with invalid covariance -> Input unchanged; stable quarantine and output roots."""
    eng_mod = _mod('engine')
    s = _mod('schemas')
    
    now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    non_psd = [[1.0, 2.0], [2.0, 1.0]]
    l0_state = {
        "covariance": non_psd,
        "state_vector": {"soil_moisture_vwc": 0.3},
        "spatial_scope": "plot",
    }
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g08",
        run_timestamp=now,
        layer0_state_package=l0_state,
    )
    engine = eng_mod.Layer1FusionEngine()
    
    # First evaluation
    res1 = engine.fuse(bundle)
    # Verify bundle is NOT mutated in place!
    assert bundle.layer0_state_package is l0_state
    assert bundle.layer0_state_package is not None
    
    # Second evaluation
    res2 = engine.fuse(bundle)
    assert bundle.layer0_state_package is l0_state
    assert res1.scientific_content_root() == res2.scientific_content_root()
    assert len(res1.diagnostics.quarantined_evidence) == len(res2.diagnostics.quarantined_evidence)


def test_r7_g09_registered_sensor_negative_controls():
    """R7-G09: Registered sensor active but receipt forgery / expired / wrong variable / wrong plot -> Denied."""
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    
    # Register active device for plot-A and soil_moisture_vwc
    register_device(SensorDeviceRegistration(
        device_id="sensor_dev_active",
        vendor="acme",
        model="probe-x",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal_valid",
    ))
    
    # Negative 1: Wrong variable (sensor only calibrated for soil_moisture_vwc, trying to report ndvi)
    item_wrong_var = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="sensor_dev_active",
        variable="ndvi",
        calibration_version="cal_valid",
        provenance_ref="urn:agriwise:receipt:sensor_dev_active_plotA",
    )
    tb.normalize_evidence_truth(item_wrong_var)
    assert item_wrong_var.state_update_allowed is False
    
    # Negative 2: Wrong plot (sensor registered for plot-A, item claims plot-B)
    item_wrong_plot = _item(
        source_family="sensor",
        plot_id="plot-B",
        instrument_id="sensor_dev_active",
        variable="soil_moisture_vwc",
        calibration_version="cal_valid",
        provenance_ref="urn:agriwise:receipt:sensor_dev_active_plotA",
    )
    tb.normalize_evidence_truth(item_wrong_plot)
    assert item_wrong_plot.state_update_allowed is False
    
    # Negative 3: Calibration mismatch / forgery
    item_bad_cal = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="sensor_dev_active",
        variable="soil_moisture_vwc",
        calibration_version="cal_forged_999",
        provenance_ref="urn:agriwise:receipt:sensor_dev_active_plotA",
    )
    tb.normalize_evidence_truth(item_bad_cal)
    assert item_bad_cal.state_update_allowed is False
    
    # Positive control: Everything matches with authentic URN receipt
    item_good = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="sensor_dev_active",
        variable="soil_moisture_vwc",
        calibration_version="cal_valid",
        provenance_ref="urn:agriwise:receipt:sensor_dev_active_plotA",
    )
    tb.normalize_evidence_truth(item_good)
    assert item_good.state_update_allowed is True
    assert item_good.truth_class == "observed_sensor"


def test_r7_g10_evidence_ancestry_graph_and_monotonicity():
    """R7-G10: Complete L0 packet -> L1 -> output ancestry; authority never increases."""
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    eng_mod = _mod('engine')
    s = _mod('schemas')
    
    now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    # Create unverified/diagnostic packet
    pkt = ObservationPacket(
        packet_id="pkt_unverified_l0",
        source=ObservationSource.SENSOR_IOT,
        data_status=DataStatus.ESTIMATED,  # Estimated -> cannot drive state
        timestamp=now,
        spatial_scope="point",
        qa=QAMetadata(scene_score=0.8),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.05}),
        payload={"variable": "soil_moisture_vwc", "value": 0.25, "unit": "fraction"},
    )
    src_pkg = Layer0SourcePackage(
        source_family="sensor",
        plot_id="plot-A",
        packets=[pkt],
        package_id="pkg_test_ancestry",
    )
    engine = eng_mod.Layer1FusionEngine()
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g10",
        run_timestamp=now,
        layer0_source_packages={"sensor": [src_pkg]},
    )
    res = engine.fuse(bundle)
    ev_items = [e for e in res.evidence_items if "pkt_unverified_l0" in e.evidence_id]
    assert len(ev_items) == 1
    assert ev_items[0].parent_acquisition_id is not None
    # Monotonicity: Fused feature authority cannot increase beyond evidence authority
    fused_sm = [f for f in res.fused_features.water_context if f.name == "soil_moisture_vwc"]
    if fused_sm:
        for f in fused_sm:
            assert f.state_update_allowed is False


def test_r7_g11_nested_malformed_covariance_quarantined():
    """R7-G11: Non-finite or malformed nested covariance with valid-looking outer wrapper -> No authoritative derivative admitted."""
    eng_mod = _mod('engine')
    s = _mod('schemas')
    
    now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    nested_non_psd = {
        "outer_valid": True,
        "nested_block": {
            "covariance": [[1.0, float('nan')], [float('nan'), 1.0]],
        },
        "state_vector": {"soil_moisture_vwc": 0.3},
    }
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g11",
        run_timestamp=now,
        layer0_state_package=nested_non_psd,
    )
    engine = eng_mod.Layer1FusionEngine()
    res = engine.fuse(bundle)
    assert any("INVALID_COVARIANCE" in q.reason_codes[0] for q in res.diagnostics.quarantined_evidence)
    assert not any(e.source_family == "l0_state" for e in res.evidence_items)


def test_r7_g12_historical_cutoff_revision_replay():
    """R7-G12: Corrected and originally published data from the same acquisition at replay cutoff -> Only temporally available revision participates."""
    ta = _mod('temporal_alignment')
    ledger = _mod('evidence_ledger').EvidenceLedger()
    cutoff = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    
    # Original published at 09:00 (before cutoff)
    orig = _item(
        evidence_id="acq_01",
        value=0.22,
        flags=["PUBLISHED_AT:2026-11-09T09:00:00+00:00"],
    )
    # Corrected revision published at 18:00 (after cutoff)
    rev = _item(
        evidence_id="acq_01__rev1",
        value=0.25,
        flags=["PUBLISHED_AT:2026-11-09T18:00:00+00:00"],
    )
    
    ok_orig, _ = ta.is_available_at_cutoff(orig, cutoff, is_historical_replay=True)
    ok_rev, _ = ta.is_available_at_cutoff(rev, cutoff, is_historical_replay=True)
    assert ok_orig is True
    assert ok_rev is False
    
    # At replay cutoff 12:00, only the original is admitted to ledger
    assert ledger.add(orig) == []
    assert len(ledger.all_items) == 1
    assert ledger.all_items[0].value == 0.22


# =============================================================================
# R8 ADVERSARIAL GATES (R8-G01 through R8-G09)
# =============================================================================


def test_r8_g01_active_sensor_missing_calibration_profile_denied():
    """R8-G01: Active registered sensor missing calibration_profile_id in registry -> Denied authority fail-closed."""
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    
    register_device(SensorDeviceRegistration(
        device_id="sensor_no_cal_profile",
        vendor="acme",
        model="probe-y",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id=None,  # missing profile
    ))
    
    item = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="sensor_no_cal_profile",
        variable="soil_moisture_vwc",
        calibration_version="cal_claimed",
        provenance_ref="urn:agriwise:receipt:probe_y_test",
    )
    tb.normalize_evidence_truth(item)
    assert item.state_update_allowed is False
    assert item.truth_class == "unverified_sensor"


def test_r8_g02_arbitrary_unauthenticated_receipt_string_denied():
    """R8-G02: Arbitrary unauthenticated receipt string (receipt_valid, receipt123) denied; authentic URN receipt accepted."""
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    
    register_device(SensorDeviceRegistration(
        device_id="sensor_auth_test",
        vendor="acme",
        model="probe-z",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal_valid_z",
    ))
    
    # Negative 1: arbitrary mock string receipt_valid
    item_mock_1 = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="sensor_auth_test",
        variable="soil_moisture_vwc",
        calibration_version="cal_valid_z",
        provenance_ref="receipt_valid",
    )
    tb.normalize_evidence_truth(item_mock_1)
    assert item_mock_1.state_update_allowed is False
    
    # Negative 2: arbitrary mock string receipt123
    item_mock_2 = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="sensor_auth_test",
        variable="soil_moisture_vwc",
        calibration_version="cal_valid_z",
        provenance_ref="receipt123",
    )
    tb.normalize_evidence_truth(item_mock_2)
    assert item_mock_2.state_update_allowed is False
    
    # Positive control: authentic URN receipt
    item_auth = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="sensor_auth_test",
        variable="soil_moisture_vwc",
        calibration_version="cal_valid_z",
        provenance_ref="urn:agriwise:receipt:sensor_auth_test:valid_batch_01",
    )
    tb.normalize_evidence_truth(item_auth)
    assert item_auth.state_update_allowed is True
    assert item_auth.truth_class == "observed_sensor"


def test_r8_g03_sensor_registry_missing_plot_or_variable_binding_denied():
    """R8-G03: Incomplete device registration (missing plot_id or empty variables) cannot authorize measurements."""
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    
    # Device registered without plot_id
    reg_no_plot = SensorDeviceRegistration(
        device_id="sensor_no_plot",
        vendor="acme",
        model="probe-w",
        protocol="lora",
        farm_id="farm-1",
        plot_id="",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal_w",
    )
    register_device(reg_no_plot)
    
    item = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="sensor_no_plot",
        variable="soil_moisture_vwc",
        calibration_version="cal_w",
        provenance_ref="urn:agriwise:receipt:sensor_no_plot:01",
    )
    tb.normalize_evidence_truth(item)
    assert item.state_update_allowed is False
    assert item.truth_class == "unverified_sensor"


def test_r8_g04_historical_replay_caller_publication_timestamp_without_verified_receipt_denied():
    """R8-G04: Backdated caller payload publication timestamp without verified receipt denied on historical replay."""
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer1_fusion.adapters.observation_packet import observation_packet_to_evidence
    ta = _mod('temporal_alignment')
    s = _mod('schemas')
    
    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    
    # Packet with backdated published_at only inside payload (caller claim, no receipt)
    pkt_claimed = ObservationPacket(
        packet_id="pkt_caller_claim",
        plot_id="plot-A",
        source=ObservationSource.SENTINEL2,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02}),
        payload={"variable": "ndvi", "value": 0.65, "unit": "index", "published_at": "2026-11-10T10:30:00+00:00"},
    )
    bundle = s.Layer1InputBundle(plot_id="plot-A", run_id="r-g04", run_timestamp=cutoff, as_of_cutoff=cutoff)
    items = observation_packet_to_evidence(pkt_claimed, bundle)
    assert len(items) == 1
    assert "CALLER_CLAIMED_PUBLICATION_TIME" in items[0].flags
    
    ok, reason = ta.is_available_at_cutoff(items[0], as_of_cutoff=cutoff, is_historical_replay=True)
    assert not ok
    assert "CALLER_CLAIMED_PUBLICATION_TIME_REJECTED" in reason


def test_r8_g05_non_psd_covariance_at_3_plus_nested_levels_quarantined_and_source_disabled():
    """R8-G05: Non-PSD covariance at 3+ arbitrary nested levels quarantined and originating source disabled."""
    eng_mod = _mod('engine')
    ri = _mod('raster_ingest')
    s = _mod('schemas')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    
    # 4-level deep non-PSD covariance
    deep_non_psd = {
        "level1": {
            "level2": {
                "level3": {
                    "uncertainty_matrix": [[1.0, 2.0], [2.0, 1.0]],  # det = -3 < 0 (non-PSD)
                }
            }
        },
        "state_vector": {"soil_moisture_vwc": 0.3},
    }
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g05",
        run_timestamp=now,
        layer0_state_package=deep_non_psd,
    )
    engine = eng_mod.Layer1FusionEngine()
    res = engine.fuse(bundle)
    assert any("INVALID_COVARIANCE" in q.reason_codes[0] for q in res.diagnostics.quarantined_evidence)
    assert not any(e.source_family == "l0_state" for e in res.evidence_items)
    
    # Test ASMAE authority check on deeply nested non-PSD covariance
    asmae_deep_bad_cov = {
        "status": "success",
        "grid_spec": {
            "crs": "EPSG:4326",
            "bounds": [10.0, 35.0, 10.1, 35.1],
            "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
            "width": 10,
            "height": 10,
            "resolution_m": 10.0,
        },
        "provenance": {
            "operator_locked": True,
            "graph_locked": True,
            "radiometric_mode": "ht_per_pixel",
            "full_radiometric_credit_allowed": True,
            "enkf_mode": "ht_per_pixel",
            "full_enkf_credit_allowed": True,
            "retrovalidation_score": 0.85,
        },
        "diagnostics": {
            "sub_analysis": {
                "regional": {
                    "covariance": [[1.0, 5.0], [5.0, 1.0]],  # non-PSD
                }
            }
        },
        "raster_maps": {"moisture": [[0.3] * 10] * 10},
    }
    auth_ok, auth_reason = ri.check_asmae_authority(asmae_deep_bad_cov)
    assert auth_ok is False
    assert "invalid_covariance" in auth_reason


def test_r8_g06_missing_package_and_packet_plot_identity_denied():
    """R8-G06: Missing package and packet plot identity fails closed; never synthesized from bundle."""
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    from layer1_fusion.adapters.observation_packet import observation_packet_to_evidence
    s = _mod('schemas')
    eng_mod = _mod('engine')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    
    # Both packet and package have blank plot_id
    blank_pkt = ObservationPacket(
        packet_id="pkt_blank_all",
        plot_id="",
        source=ObservationSource.SENTINEL2,
        data_status=DataStatus.OBSERVED,
        timestamp=now,
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02}),
        payload={"variable": "ndvi", "value": 0.65, "unit": "index"},
    )
    blank_pkg = Layer0SourcePackage(
        source_family="sentinel2",
        plot_id="",
        packets=[blank_pkt],
    )
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g06",
        run_timestamp=now,
        layer0_source_packages={"sentinel2": [blank_pkg]},
    )
    # observation_packet_to_evidence must NOT synthesize from bundle.plot_id
    items = observation_packet_to_evidence(blank_pkt, bundle, source_package=blank_pkg)
    assert len(items) == 1
    assert items[0].plot_id is None
    
    # Full engine must quarantine blank source package
    engine = eng_mod.Layer1FusionEngine()
    res = engine.fuse(bundle)
    assert any("MISSING_SOURCE_PACKAGE_PLOT_SCOPE" in q.reason_codes[0] for q in res.diagnostics.quarantined_evidence)
    assert not any("pkt_blank_all" in e.evidence_id for e in res.evidence_items)


def test_r8_g07_bundle_source_package_source_family_never_mutated_in_place():
    """R8-G07: Bundle containing source packages with aliases is never mutated in-place."""
    from layer0.source_package import Layer0SourcePackage
    s = _mod('schemas')
    eng_mod = _mod('engine')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    
    alias_pkg = Layer0SourcePackage(
        source_family="SENTINEL_2",  # alias with uppercase and underscore
        plot_id="plot-A",
        packets=[],
    )
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g07",
        run_timestamp=now,
        layer0_source_packages={"SENTINEL_2": [alias_pkg]},
    )
    engine = eng_mod.Layer1FusionEngine()
    engine.fuse(bundle)
    
    # Original package object source_family must remain immutable
    assert alias_pkg.source_family == "SENTINEL_2"


def test_r8_g08_historical_replay_zero_clock_skew_enforced():
    """R8-G08: Historical observation 1 minute after cutoff denied (zero clock-skew on replay; live streaming retains 5m)."""
    ta = _mod('temporal_alignment')
    cutoff = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
    
    item_future_1m = _item(
        observed_at=datetime(2026, 11, 10, 12, 1, 0, tzinfo=timezone.utc),
        flags=["PUBLISHED_AT:2026-11-10T12:00:00+00:00", "VERIFIED_PUBLICATION_RECEIPT"],
    )
    
    # On historical replay: zero tolerance -> denied
    ok_replay, reason_replay = ta.is_available_at_cutoff(item_future_1m, cutoff, is_historical_replay=True)
    assert ok_replay is False
    assert "OBSERVED_AFTER_CUTOFF" in reason_replay
    
    # On live streaming: 5-minute tolerance -> accepted
    ok_live, _ = ta.is_available_at_cutoff(item_future_1m, cutoff, is_historical_replay=False)
    assert ok_live is True


def test_r8_g09_full_engine_replay_superseded_revision_cutoff_isolation():
    """R8-G09: Competing revisions in full engine replay: only cutoff-available revision participates in fusion."""
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    eng_mod = _mod('engine')
    s = _mod('schemas')
    
    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    
    # Original revision published at 09:00 with value 20.0
    pkt_orig = ObservationPacket(
        packet_id="acq_temp_orig",
        plot_id="plot-A",
        source=ObservationSource.WEATHER_STATION,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"temp_mean": 0.5}),
        payload={"variable": "temp_mean", "temp_mean": 20.0, "unit": "degC"},
    )
    pkg_orig = Layer0SourcePackage(
        source_family="environment",
        plot_id="plot-A",
        packets=[pkt_orig],
    )
    pkg_orig.published_at = datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)
    
    # Corrected revision published at 18:00 with value 25.0
    pkt_rev = ObservationPacket(
        packet_id="acq_temp_rev",
        plot_id="plot-A",
        source=ObservationSource.WEATHER_STATION,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"temp_mean": 0.5}),
        payload={"variable": "temp_mean", "temp_mean": 25.0, "unit": "degC"},
    )
    pkg_rev = Layer0SourcePackage(
        source_family="environment",
        plot_id="plot-A",
        packets=[pkt_rev],
    )
    pkg_rev.published_at = datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)
    
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g09",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        layer0_source_packages={"environment": [pkg_orig, pkg_rev]},
    )
    engine = eng_mod.Layer1FusionEngine()
    res = engine.fuse(bundle)
    
    # Revision published after cutoff must be quarantined
    assert any("acq_temp_rev" in q.evidence_id for q in res.diagnostics.quarantined_evidence)
    # Original revision published before cutoff must participate
    admitted = [e for e in res.evidence_items if "acq_temp_orig" in e.evidence_id]
    assert len(admitted) == 1
    assert admitted[0].value == 20.0


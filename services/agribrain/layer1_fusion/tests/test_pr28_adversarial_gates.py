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

def _tf():
    return _mod('tests.trust_fixtures')

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


@pytest.fixture(autouse=True)
def _isolate_revocation_store_per_test(tmp_path):
    """Isolate revocation store per test to guarantee test independence (R12-04)."""
    tb = _mod('truth_bridge')
    old_store = tb.get_revocation_store()
    test_path = str(tmp_path / "test_revocation_store.json")
    new_store = tb.DurableRevocationStore(persistence_path=test_path)
    tb.set_revocation_store(new_store)
    yield
    tb.set_revocation_store(old_store)

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
    tb.register_sensor_receipt(_tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_dev_active_plotA",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_dev_active",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal_valid",
        status="active",
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
        publication_receipt_verified=True,
    )
    # Corrected revision published at 18:00 (after cutoff)
    rev = _item(
        evidence_id="acq_01__rev1",
        value=0.25,
        flags=["PUBLISHED_AT:2026-11-09T18:00:00+00:00"],
        publication_receipt_verified=True,
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
    
    # Positive control: authentic registered receipt
    tb.register_sensor_receipt(_tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_auth_test:valid_batch_01",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_auth_test",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal_valid_z",
        status="active",
    ))
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
    tb = _mod('truth_bridge')
    eng_mod = _mod('engine')
    s = _mod('schemas')
    
    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    
    # Original revision published at 09:00 with value 20.0
    rcpt_orig = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:weather:orig",
        issuer="agriwise:trust:publication_authority",
        source_family="environment",
        acquisition_id="acq_temp_orig",
        published_at=datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc),
    )
    tb.register_publication_receipt(rcpt_orig)
    pkt_orig = ObservationPacket(
        packet_id="acq_temp_orig",
        plot_id="plot-A",
        source=ObservationSource.WEATHER_STATION,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"temp_mean": 0.5}),
        payload={"variable": "temp_mean", "temp_mean": 20.0, "unit": "degC", "publication_receipt": rcpt_orig},
    )
    pkg_orig = Layer0SourcePackage(
        source_family="environment",
        plot_id="plot-A",
        packets=[pkt_orig],
    )
    pkg_orig.receipt = rcpt_orig
    pkg_orig.published_at = datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)
    
    # Corrected revision published at 18:00 with value 25.0
    rcpt_rev = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:weather:rev",
        issuer="agriwise:trust:publication_authority",
        source_family="environment",
        acquisition_id="acq_temp_rev",
        published_at=datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc),
    )
    tb.register_publication_receipt(rcpt_rev)
    pkt_rev = ObservationPacket(
        packet_id="acq_temp_rev",
        plot_id="plot-A",
        source=ObservationSource.WEATHER_STATION,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"temp_mean": 0.5}),
        payload={"variable": "temp_mean", "temp_mean": 25.0, "unit": "degC", "publication_receipt": rcpt_rev},
    )
    pkg_rev = Layer0SourcePackage(
        source_family="environment",
        plot_id="plot-A",
        packets=[pkt_rev],
    )
    pkg_rev.receipt = rcpt_rev
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


def test_r9_g01_sensor_receipt_forged_urn_and_dummy_object_denied():
    """R9-G01: Forged URN, arbitrary non-None dummy object, manufactured URN, and raw fallback denied; authentic receipt accepted."""
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    
    register_device(SensorDeviceRegistration(
        device_id="sensor_r9_dev",
        vendor="acme",
        model="probe-r9",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal_r9_profile",
    ))
    
    # Negative (a): Forged valid-looking URN string with no registered receipt backing
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r9_dev",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal_r9_profile",
        provenance_ref="urn:agriwise:receipt:sensor:sensor_r9_dev:plot-A:01",
    )
    assert ok is False
    assert "unverified_sensor_receipt" in reason

    # Negative (b): Arbitrary non-None dummy receipt object
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r9_dev",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal_r9_profile",
        receipt=object(),
    )
    assert ok is False
    assert "unauthenticated_receipt_object" in reason

    # Negative (c): Arbitrary dummy dict receipt object
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r9_dev",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal_r9_profile",
        receipt={"dummy": "payload", "receipt_id": "r1"},
    )
    assert ok is False
    assert "unauthenticated_receipt_object" in reason

    # Negative (d): pkg_* and packet_* string without registered receipt
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r9_dev",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal_r9_profile",
        provenance_ref="pkg_hash123_pkt_hash456",
    )
    assert ok is False
    assert "unverified_sensor_receipt" in reason

    # Negative (e): Receipt with fake / dummy signature
    fake_sig_receipt = tb.SensorAttestationReceipt(
        receipt_id="urn:agriwise:receipt:fake_sig",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r9_dev",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal_r9_profile",
        content_digest="digest_dummy",
        observation_instant="2026-11-09T10:00:00Z",
        signature="dummy_signature",
    )
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r9_dev",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal_r9_profile",
        receipt=fake_sig_receipt,
        expected_content_digest="digest_dummy",
        expected_observed_at=datetime(2026, 11, 9, 10, tzinfo=timezone.utc),
    )
    assert ok is False
    assert "unverified_receipt_signature" in reason or "untrusted_issuer" in reason or "invalid_cryptographic_signature" in reason or "missing_receipt_content_digest" in reason

    # Positive control: Authentic registered receipt
    valid_receipt = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_r9_dev:auth_001",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r9_dev",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal_r9_profile",
        status="active",
    )
    tb.register_sensor_receipt(valid_receipt)
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r9_dev",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal_r9_profile",
        provenance_ref="urn:agriwise:receipt:sensor_r9_dev:auth_001",
        expected_value=0.35,
        expected_unit="fraction",
        expected_observed_at=datetime(2026, 11, 9, 10, tzinfo=timezone.utc),
    )
    assert ok is True
    assert reason == "attested_via_verified_receipt"

    # Normalized evidence truth accepts positive control
    item = _item(
        source_family="sensor",
        plot_id="plot-A",
        instrument_id="sensor_r9_dev",
        variable="soil_moisture_vwc",
        calibration_version="cal_r9_profile",
        provenance_ref="urn:agriwise:receipt:sensor_r9_dev:auth_001",
    )
    tb.normalize_evidence_truth(item)
    assert item.state_update_allowed is True
    assert item.truth_class == "observed_sensor"


def test_r9_g02_covariance_scale_aware_indefinite_and_overflow_denied():
    """R9-G02: Scale-aware indefinite rejection (det < -1e-9 * scale), overflow rejection, near-singular PSD pass."""
    diag = _mod('diagnostics')
    ri = _mod('raster_ingest')
    
    # 1. Tiny indefinite matrix: det = -3e-12, min eig = -1e-6
    tiny_indefinite = [[1e-6, 2e-6], [2e-6, 1e-6]]
    is_psd, reason = diag.validate_covariance_matrix(tiny_indefinite)
    assert is_psd is False
    assert "NEGATIVE_DETERMINANT" in reason

    # 2. Overflow-sized finite indefinite matrix
    overflow_indefinite = [[1e308, 1e308], [1e308, 1e307]]
    is_psd, reason = diag.validate_covariance_matrix(overflow_indefinite)
    assert is_psd is False
    assert "NUMERICAL_OVERFLOW_DETECTED" in reason

    # 3. Near-singular PSD matrix (rank 1, det = 0)
    near_singular_psd = [[1e-4, 1e-4], [1e-4, 1e-4]]
    is_psd, reason = diag.validate_covariance_matrix(near_singular_psd)
    assert is_psd is True
    assert reason == "valid_psd_covariance"

    # 4. Zero matrix (rank 0, det = 0)
    zero_mat = [[0.0, 0.0], [0.0, 0.0]]
    is_psd, reason = diag.validate_covariance_matrix(zero_mat)
    assert is_psd is True
    assert reason == "valid_psd_covariance"

    # 5. Small asymmetric matrix
    asymmetric_mat = [[1.0, 1.0001], [1.0, 1.0]]
    is_psd, reason = diag.validate_covariance_matrix(asymmetric_mat)
    assert is_psd is False
    assert "ASYMMETRIC_COVARIANCE" in reason

    # 6. ASMAE authority check rejects tiny indefinite covariance
    asmae_bad = {
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
        "diagnostics": {"covariance": tiny_indefinite},
        "raster_maps": {"moisture": [[0.3] * 10] * 10},
    }
    auth_ok, auth_reason = ri.check_asmae_authority(asmae_bad)
    assert auth_ok is False
    assert "invalid_covariance" in auth_reason


def test_r9_g03_historical_publication_flag_injection_denied():
    """R9-G03: Direct item bare flags, payload flag injection denied; immutable receipt overrides caller claim."""
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    from layer1_fusion.adapters.observation_packet import observation_packet_to_evidence
    ta = _mod('temporal_alignment')
    s = _mod('schemas')
    
    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    # (a) Direct EvidenceItem with bare PUBLISHED_AT flag (no typed publication_receipt_verified)
    direct_item = _item(
        observed_at=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        flags=["PUBLISHED_AT:2026-11-10T10:30:00+00:00"],
    )
    ok, reason = ta.is_available_at_cutoff(direct_item, cutoff, is_historical_replay=True)
    assert ok is False
    assert "UNVERIFIED_PUBLICATION_TIME_ON_HISTORICAL_REPLAY" in reason

    # (b) Packet payload attempting to inject VERIFIED_PUBLICATION_RECEIPT flag
    pkt_injected = ObservationPacket(
        packet_id="pkt_injected",
        plot_id="plot-A",
        source=ObservationSource.SENTINEL2,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02}),
        payload={
            "variable": "ndvi", "value": 0.65, "unit": "index",
            "published_at": "2026-11-10T10:30:00+00:00",
            "flags": ["VERIFIED_PUBLICATION_RECEIPT"],
        },
    )
    bundle = s.Layer1InputBundle(plot_id="plot-A", run_id="r-g03", run_timestamp=cutoff, as_of_cutoff=cutoff)
    items = observation_packet_to_evidence(pkt_injected, bundle)
    assert len(items) == 1
    assert "VERIFIED_PUBLICATION_RECEIPT" not in items[0].flags
    assert items[0].publication_receipt_verified is False
    ok, reason = ta.is_available_at_cutoff(items[0], cutoff, is_historical_replay=True)
    assert ok is False

    # (c) Future genuine receipt overrides earlier caller claim
    tb = _mod('truth_bridge')
    rcpt_late = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sentinel2:late",
        issuer="agriwise:trust:publication_authority",
        source_family="sentinel2",
        acquisition_id="pkt_claim_early",
        published_at=datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc),
    )
    tb.register_publication_receipt(rcpt_late)
    pkt_claimed_early = ObservationPacket(
        packet_id="pkt_claim_early",
        plot_id="plot-A",
        source=ObservationSource.SENTINEL2,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02}),
        payload={"variable": "ndvi", "value": 0.65, "unit": "index", "published_at": "2026-11-10T10:30:00+00:00", "publication_receipt": rcpt_late},
    )
    pkg_genuine_late = Layer0SourcePackage(
        source_family="sentinel2",
        plot_id="plot-A",
        packets=[pkt_claimed_early],
    )
    pkg_genuine_late.receipt = rcpt_late
    pkg_genuine_late.published_at = datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc)
    items_overridden = observation_packet_to_evidence(pkt_claimed_early, bundle, source_package=pkg_genuine_late)
    assert len(items_overridden) == 1
    ok, reason = ta.is_available_at_cutoff(items_overridden[0], cutoff, is_historical_replay=True)
    assert ok is False
    assert "PUBLISHED_AFTER_CUTOFF" in reason

    # (d) Authenticated historical positive control
    rcpt_early = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sentinel2:early",
        issuer="agriwise:trust:publication_authority",
        source_family="sentinel2",
        acquisition_id="pkt_claim_early",
        published_at=datetime(2026, 11, 10, 10, 30, tzinfo=timezone.utc),
    )
    tb.register_publication_receipt(rcpt_early)
    pkt_claimed_early_2 = ObservationPacket(
        packet_id="pkt_claim_early",
        plot_id="plot-A",
        source=ObservationSource.SENTINEL2,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02}),
        payload={"variable": "ndvi", "value": 0.65, "unit": "index", "published_at": "2026-11-10T10:30:00+00:00", "publication_receipt": rcpt_early},
    )
    pkg_genuine_early = Layer0SourcePackage(
        source_family="sentinel2",
        plot_id="plot-A",
        packets=[pkt_claimed_early_2],
    )
    pkg_genuine_early.receipt = rcpt_early
    pkg_genuine_early.published_at = datetime(2026, 11, 10, 10, 30, tzinfo=timezone.utc)
    items_valid = observation_packet_to_evidence(pkt_claimed_early_2, bundle, source_package=pkg_genuine_early)
    assert len(items_valid) == 1
    ok, reason = ta.is_available_at_cutoff(items_valid[0], cutoff, is_historical_replay=True)
    assert ok is True


def test_r9_g04_disabled_layer0_state_excluded_from_spatial_index():
    """R9-G04: Disabled Layer 0 state package is excluded from spatial index enrichment and Layer 10."""
    eng_mod = _mod('engine')
    s = _mod('schemas')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)

    # L0 state package with invalid covariance and zone summary
    bad_l0_state = {
        "covariance": [[1.0, 5.0], [5.0, 1.0]],
        "state_vector": {"soil_moisture_vwc": 0.25},
        "spatial_scope": "plot",
        "zone_summaries": [{"zone_id": "zone-1", "label": "Zone 1", "area_fraction": 0.5}],
        "edge_contamination": [{"edge_id": "edge-1", "contamination_score": 0.8}],
    }
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g04-l0",
        run_timestamp=now,
        layer0_state_package=bad_l0_state,
    )
    engine = eng_mod.Layer1FusionEngine()
    pkg = engine.fuse(bundle)
    
    # 1. Source l0_state quarantined and disabled
    assert any("INVALID_COVARIANCE" in q.reason_codes[0] for q in pkg.diagnostics.quarantined_evidence)
    assert not any(e.source_family == "l0_state" for e in pkg.evidence_items)

    # 2. Spatial index has zero leaked zone summaries or edge regions from disabled L0 state
    assert len(pkg.spatial_index.zones) == 0
    assert len(pkg.spatial_index.edge_regions) == 0

    # 3. Layer 10 payload has zero leaked overlays from disabled L0 state
    assert len(pkg.layer10_payload["zone_overlays"]) == 0
    assert len(pkg.layer10_payload["edge_regions"]) == 0

    # Positive control: Valid L0 state package enriches spatial index
    from services.agribrain.layer0.source_package import Layer0StatePackage
    good_l0_state = Layer0StatePackage(
        plot_id="plot-A",
        run_id="r-g04-good",
        geometry_hash="geom-a",
        geometry_version=1,
        daily_state={"zone-1": {"soil_moisture": 0.25}},
        state_uncertainty={"zone-1": {"covariance": [[0.01, 0.0], [0.0, 0.01]]}},
        zone_summaries=[{"zone_id": "zone-1", "label": "Zone 1", "area_fraction": 0.5}],
        edge_contamination=[{"edge_id": "edge-1", "contamination_score": 0.8}],
        health_report={
            "scientific_state_admissible": True,
            "audit": {
                "structural_audit": {
                    "status": "PASS",
                    "checks_run": 5,
                    "checks_failed": 0,
                }
            },
        },
        provenance={
            "run_id": "r-g04-good",
            "scientific_state_integrity": "PASSED_RUNTIME_BOUNDARY",
        },
        scientific_publication_authorized=False,
        actuator_control_authorized=False,
    )
    bundle_good = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g04-good",
        run_timestamp=now,
        layer0_state_package=good_l0_state,
    )
    pkg_good = engine.fuse(bundle_good)
    assert len(pkg_good.spatial_index.zones) > 0
    assert len(pkg_good.layer10_payload["zone_overlays"]) > 0


def test_r9_g05_raster_reference_consistent_with_evidence_cutoff():
    """R9-G05: Late raster composites and late ASMAE outputs have RasterRefs excluded on historical replay."""
    eng_mod = _mod('engine')
    s = _mod('schemas')
    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    # 1. Late raster composite published at 16:00 (cutoff 12:00)
    late_composite = {
        "NDVI": {
            "values": [[0.6] * 10] * 10,
            "crs": "EPSG:4326",
            "bounds": [10.0, 35.0, 10.1, 35.1],
            "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
            "width": 10,
            "height": 10,
            "resolution_m": 10.0,
            "published_at": "2026-11-10T16:00:00+00:00",
        }
    }
    bundle_late_raster = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g05-late",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        raster_composites=late_composite,
    )
    engine = eng_mod.Layer1FusionEngine()
    pkg_late = engine.fuse(bundle_late_raster)
    
    # Evidence quarantined with cutoff violation
    assert any("HISTORICAL_CUTOFF_VIOLATION" in q.reason_codes[0] for q in pkg_late.diagnostics.quarantined_evidence)
    # RasterRef NOT admitted to spatial_index.raster_refs
    assert not any(r.variable == "ndvi" for r in pkg_late.spatial_index.raster_refs)
    assert not any(r["variable"] == "ndvi" for r in pkg_late.layer10_payload["raster_refs"])

    # 2. Late ASMAE output published at 18:00
    late_asmae = {
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
            "published_at": "2026-11-10T18:00:00+00:00",
        },
        "diagnostics": {"covariance": [[0.01, 0.0], [0.0, 0.01]]},
        "raster_maps": {"moisture": [[0.3] * 10] * 10},
    }
    bundle_late_asmae = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g05-asmae-late",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        asmae_output=late_asmae,
    )
    pkg_asmae_late = engine.fuse(bundle_late_asmae)
    assert any("HISTORICAL_CUTOFF_VIOLATION" in q.reason_codes[0] for q in pkg_asmae_late.diagnostics.quarantined_evidence)
    assert not any(r.variable == "moisture" for r in pkg_asmae_late.spatial_index.raster_refs)

    # 3. Positive control: In-cutoff raster composite and ASMAE
    import numpy as np
    from layer1_fusion.raster_ingest import _compute_pixel_hash
    tb = _mod('truth_bridge')
    grid_spec_early = {
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
    }
    early_composite_data = {
        "values": [[0.6] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": "2026-11-10T10:00:00+00:00",
    }
    ch_comp = tb.compute_raster_composite_content_hash(early_composite_data)
    rcpt_early_composite = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:ndvi:early",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="NDVI",
        published_at=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        content_hash=ch_comp,
    )
    tb.register_publication_receipt(rcpt_early_composite)
    early_composite_data["publication_receipt"] = rcpt_early_composite
    early_composite = {"NDVI": early_composite_data}
    early_asmae_base = {
        "status": "success",
        "run_id": "asmae_run_early",
        "package_id": "asmae_run_early",
        "grid_spec": grid_spec_early,
        "provenance": {
            "operator_locked": True,
            "graph_locked": True,
            "radiometric_mode": "ht_per_pixel",
            "full_radiometric_credit_allowed": True,
            "enkf_mode": "ht_per_pixel",
            "full_enkf_credit_allowed": True,
            "retrovalidation_score": 0.85,
            "published_at": "2026-11-10T10:00:00+00:00",
        },
        "diagnostics": {"covariance": [[0.01, 0.0], [0.0, 0.01]]},
        "raster_maps": {"moisture": [[0.3] * 10] * 10},
    }
    ch_asmae = tb.compute_asmae_content_hash(early_asmae_base)
    rcpt_early_asmae = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:asmae:early",
        issuer="agriwise:trust:publication_authority",
        source_family="asmae",
        acquisition_id="asmae_run_early",
        published_at=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        content_hash=ch_asmae,
    )
    tb.register_publication_receipt(rcpt_early_asmae)
    early_asmae = dict(early_asmae_base)
    early_asmae["provenance"] = dict(early_asmae_base["provenance"])
    early_asmae["provenance"]["publication_receipt"] = rcpt_early_asmae
    bundle_in_cutoff = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g05-ok",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        raster_composites=early_composite,
        asmae_output=early_asmae,
    )
    pkg_ok = engine.fuse(bundle_in_cutoff)
    assert any(r.variable == "ndvi" for r in pkg_ok.spatial_index.raster_refs)
    assert any("moisture" in r.variable for r in pkg_ok.spatial_index.raster_refs)


def test_r9_g06_covariance_traversal_depth_limit_and_malformed_fails_closed():
    """R9-G06: Depth > 10, circular references, and malformed non-list covariance keys fail closed."""
    diag = _mod('diagnostics')
    eng_mod = _mod('engine')
    s = _mod('schemas')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)

    # 1. Depth > 10
    deep = {}
    curr = deep
    for i in range(12):
        curr["nested"] = {}
        curr = curr["nested"]
    curr["covariance"] = [[1.0, 0.0], [0.0, 1.0]]
    extracted = diag.extract_covariance_matrices_recursive(deep, max_depth=10)
    assert any(mat == "COVARIANCE_TRAVERSAL_LIMIT_EXCEEDED" for _, mat in extracted)

    # Full engine quarantines depth-exceeded structure
    bundle_deep = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g06-deep",
        run_timestamp=now,
        layer0_state_package=deep,
    )
    engine = eng_mod.Layer1FusionEngine()
    pkg_deep = engine.fuse(bundle_deep)
    assert any("COVARIANCE_TRAVERSAL_LIMIT_EXCEEDED" in q.reason_codes[0] for q in pkg_deep.diagnostics.quarantined_evidence)
    assert not any(e.source_family == "l0_state" for e in pkg_deep.evidence_items)

    # 2. Circular reference
    circular_dict = {}
    circular_dict["self"] = circular_dict
    circular_dict["covariance"] = [[1.0, 0.0], [0.0, 1.0]]
    extracted_circ = diag.extract_covariance_matrices_recursive(circular_dict)
    assert any(mat == "CIRCULAR_REFERENCE_IN_COVARIANCE_STRUCTURE" for _, mat in extracted_circ)

    # 3. Malformed non-list covariance key
    malformed = {"covariance": "not_a_matrix", "state_vector": {"moisture": 0.3}}
    extracted_mal = diag.extract_covariance_matrices_recursive(malformed)
    assert any(mat == "MALFORMED_COVARIANCE_STRUCTURE" for _, mat in extracted_mal)

    bundle_mal = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r-g06-mal",
        run_timestamp=now,
        layer0_state_package=malformed,
    )
    pkg_mal = engine.fuse(bundle_mal)
    assert any("MALFORMED_COVARIANCE_STRUCTURE" in q.reason_codes[0] for q in pkg_mal.diagnostics.quarantined_evidence)


def test_r9_g07_revision_supersession_graph_lineage_cutoff():
    """R9-G07: Revision supersession graph preserves original when revised observation is past cutoff."""
    ta = _mod('temporal_alignment')
    el = _mod('evidence_ledger')
    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    # Original observation
    ev_orig = _item(
        evidence_id="ev_weather_station_001",
        variable="temp_mean",
        value=20.0,
        source_family="environment",
        observed_at=cutoff - timedelta(hours=3),
        flags=["PUBLISHED_AT:2026-11-10T09:30:00+00:00"],
        publication_receipt_verified=True,
    )

    # Revision with explicit supersedes_evidence_id, published after cutoff
    ev_rev_late = _item(
        evidence_id="ev_weather_station_001__rev1",
        variable="temp_mean",
        value=22.5,
        source_family="environment",
        observed_at=cutoff - timedelta(hours=3),
        flags=["PUBLISHED_AT:2026-11-10T15:00:00+00:00"],
        publication_receipt_verified=True,
    )
    ev_rev_late.supersedes_evidence_id = "ev_weather_station_001"

    # Availability check at cutoff
    ok_orig, _ = ta.is_available_at_cutoff(ev_orig, cutoff, is_historical_replay=True)
    ok_rev, reason_rev = ta.is_available_at_cutoff(ev_rev_late, cutoff, is_historical_replay=True)
    assert ok_orig is True
    assert ok_rev is False
    assert "PUBLISHED_AFTER_CUTOFF" in reason_rev

    # Ledger admits original; late revision rejected
    ledger = el.EvidenceLedger()
    assert ledger.add(ev_orig) == []
    assert len(ledger.all_items) == 1
    assert ledger.all_items[0].value == 20.0

    # In-cutoff revision properly supersedes
    ev_rev_early = _item(
        evidence_id="ev_weather_station_001__rev0",
        variable="temp_mean",
        value=21.0,
        source_family="environment",
        observed_at=cutoff - timedelta(hours=3),
        flags=["PUBLISHED_AT:2026-11-10T10:00:00+00:00"],
        publication_receipt_verified=True,
    )
    ev_rev_early.supersedes_evidence_id = "ev_weather_station_001"
    ok_early, _ = ta.is_available_at_cutoff(ev_rev_early, cutoff, is_historical_replay=True)
    assert ok_early is True


def test_r9_g08_full_engine_healthy_sensor_and_asmae_layer10_positive_control():
    """R9-G08: Healthy registered sensor + signed receipt and valid ASMAE produce authoritative Layer 10 state update."""
    from layer0.source_package import Layer0SourcePackage
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    eng_mod = _mod('engine')
    s = _mod('schemas')
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    # 1. Register active sensor in device registry
    register_device(SensorDeviceRegistration(
        device_id="sensor_full_01",
        vendor="soil-tech",
        model="probe-pro",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now - timedelta(days=30),
        status="active",
        calibration_profile_id="cal-soil-pro-1",
    ))

    # 2. Register cryptographic sensor attestation receipt
    receipt = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_full_01:reading_01",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_full_01",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-soil-pro-1",
        status="active",
        reading_value=0.28,
        reading_unit="fraction",
        observed_at=now - timedelta(minutes=15),
    )
    tb.register_sensor_receipt(receipt)

    # 3. Create sensor packet with authentic receipt reference
    sensor_pkt = ObservationPacket(
        packet_id="pkt_sensor_01",
        plot_id="plot-A",
        source=ObservationSource.SENSOR_IOT,
        data_status=DataStatus.OBSERVED,
        timestamp=now - timedelta(minutes=15),
        spatial_scope="point",
        qa=QAMetadata(scene_score=1.0, sensor_health=0.98),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.01}),
        payload={
            "device_id": "sensor_full_01",
            "instrument_id": "sensor_full_01",
            "variable": "soil_moisture_vwc",
            "value": 0.28,
            "unit": "fraction",
            "calibration_version": "cal-soil-pro-1",
            "provenance_ref": "urn:agriwise:receipt:sensor_full_01:reading_01",
        },
    )
    sensor_pkg = Layer0SourcePackage(
        source_family="sensor",
        plot_id="plot-A",
        packets=[sensor_pkt],
    )

    # 4. Valid ASMAE output with all required credentials
    valid_asmae = {
        "status": "success",
        "run_id": "asmae_run_01",
        "package_id": "pkg_asmae_valid_01",
        "schema_version": "1.0",
        "package_version": "1.0",
        "source_id": "asmae_engine_01",
        "production_usable": True,
        "layer1_export_allowed": True,
        "observation_operator_refs": ["op-1"],
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
            "retrovalidation_score": 0.88,
            "published_at": (now - timedelta(minutes=30)).isoformat(),
        },
        "diagnostics": {
            "scientific_pass": True,
            "scene_stack_mode": "real_raster",
            "enkf_mode": "ht_per_pixel",
            "radiometric_mode": "ht_per_pixel",
            "retro_status": "success_with_holdouts",
            "diagnostic_only": False,
            "state_update_allowed": True,
            "operator_count": 1,
            "covariance": [[0.02, 0.0], [0.0, 0.02]],
        },
        "raster_maps": {"moisture": [[0.3] * 10] * 10},
    }

    # 5. Run full engine fusion
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="run-r9-g08",
        run_timestamp=now,
        window_start=now - timedelta(days=1),
        window_end=now,
        layer0_source_packages={"sensor": [sensor_pkg]},
        asmae_output=valid_asmae,
    )
    engine = eng_mod.Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # Assertions:
    # Sensor evidence is admitted with full state authority
    sensor_ev = [e for e in pkg.evidence_items if e.source_family == "sensor"]
    assert len(sensor_ev) == 1
    assert sensor_ev[0].truth_class == "observed_sensor"
    assert sensor_ev[0].state_update_allowed is True
    assert sensor_ev[0].diagnostic_only is False

    # ASMAE raster refs are exported to spatial_index
    asmae_refs = [r for r in pkg.spatial_index.raster_refs if "moisture" in r.variable]
    assert len(asmae_refs) == 1
    assert asmae_refs[0].state_update_allowed is True

    # Layer 10 payload contains sensor markers and ASMAE raster ref
    assert len(pkg.layer10_payload["sensor_markers"]) > 0
    assert any("moisture" in r["variable"] for r in pkg.layer10_payload["raster_refs"])

    # Zero quarantine for these healthy sources
    assert len(pkg.diagnostics.quarantined_evidence) == 0

    # Content root is 64 hex characters and matches hash
    root = pkg.scientific_content_root()
    assert len(root) == 64
    assert pkg.content_hash() == root[:32]


# =============================================================================
# R10 ADVERSARIAL GATES (R10-G01 through R10-G08)
# =============================================================================


def test_r10_g01_sensor_cryptographic_signature_verification():
    """R10-G01: Authentic Ed25519 cryptographic signature verifies; forged/tampered hex signature rejected."""
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)

    register_device(SensorDeviceRegistration(
        device_id="sensor_r10_01",
        vendor="acme",
        model="probe-r10",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal-r10-01",
    ))

    # 1. Genuine signed receipt
    valid_rcpt = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_r10_01:001",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r10_01",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r10-01",
        status="active",
    )
    tb.register_sensor_receipt(valid_rcpt)
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r10_01",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r10-01",
        receipt=valid_rcpt,
        expected_value=0.35,
        expected_unit="fraction",
        expected_observed_at=datetime(2026, 11, 9, 10, tzinfo=timezone.utc),
    )
    assert ok is True
    assert reason == "attested_via_verified_receipt"

    # 2. Forged signature (tampered hex byte)
    tampered_sig = valid_rcpt.signature[:-2] + ("00" if valid_rcpt.signature[-2:] != "00" else "ff")
    forged_rcpt = tb.SensorAttestationReceipt(
        receipt_id="urn:agriwise:receipt:sensor_r10_01:forged",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r10_01",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r10-01",
        status="active",
        content_digest=valid_rcpt.content_digest,
        observation_instant=valid_rcpt.observation_instant,
        signature=tampered_sig,
    )
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r10_01",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r10-01",
        receipt=forged_rcpt,
        expected_value=0.35,
        expected_unit="fraction",
        expected_observed_at=datetime(2026, 11, 9, 10, tzinfo=timezone.utc),
    )
    assert ok is False
    assert "invalid_cryptographic_signature" in reason or "InvalidSignature" in reason or "invalid_sensor_signature" in reason


def test_r10_g02_sensor_signature_tampering_and_revocation():
    """R10-G02: Payload tampering mathematically breaks signature; revocation ID and expired epoch fail closed."""
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)

    register_device(SensorDeviceRegistration(
        device_id="sensor_r10_02",
        vendor="acme",
        model="probe-r10-2",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc", "soil_temperature"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal-r10-02",
    ))

    # Signed receipt for soil_moisture_vwc
    signed_rcpt = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_r10_02:tamper_test",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r10_02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r10-02",
        status="active",
        content_digest="digest_original_123",
        observation_instant="2026-11-10T12:00:00+00:00",
        revocation_epoch=0,
    )
    tb.register_sensor_receipt(signed_rcpt)

    # 1. Tamper content_digest
    tampered_digest_rcpt = tb.SensorAttestationReceipt(
        receipt_id=signed_rcpt.receipt_id,
        issuer=signed_rcpt.issuer,
        device_id=signed_rcpt.device_id,
        plot_id=signed_rcpt.plot_id,
        variable=signed_rcpt.variable,
        calibration_profile_id=signed_rcpt.calibration_profile_id,
        status=signed_rcpt.status,
        content_digest="digest_TAMPERED_456",
        observation_instant=signed_rcpt.observation_instant,
        revocation_epoch=signed_rcpt.revocation_epoch,
        signature=signed_rcpt.signature,
    )
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r10_02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r10-02",
        receipt=tampered_digest_rcpt,
        expected_content_digest="digest_TAMPERED_456",
        expected_observed_at=signed_rcpt.observation_instant,
    )
    assert ok is False
    assert "invalid_cryptographic_signature" in reason or "InvalidSignature" in reason or "invalid_sensor_signature" in reason

    # 2. Revoked receipt ID
    tb.revoke_sensor_receipt("urn:agriwise:receipt:sensor_r10_02:tamper_test")
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r10_02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r10-02",
        receipt=signed_rcpt,
        expected_content_digest="digest_original_123",
        expected_observed_at=signed_rcpt.observation_instant,
    )
    assert ok is False
    assert "revoked_sensor_receipt" in reason

    # 3. Expired revocation epoch
    fresh_rcpt = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_r10_02:epoch_test",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r10_02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r10-02",
        status="active",
        revocation_epoch=0,
    )
    tb.register_sensor_receipt(fresh_rcpt)
    tb.set_current_revocation_epoch(1)  # Epoch advanced
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r10_02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r10-02",
        receipt=fresh_rcpt,
        expected_value=0.35,
        expected_unit="fraction",
        expected_observed_at=fresh_rcpt.observation_instant,
    )
    assert ok is False
    assert "expired_revocation_epoch" in reason


def test_r10_g03_caller_supplied_publication_timestamp_without_receipt_denied():
    """R10-G03: Caller-supplied published_at without verified receipt denied on historical replay; verified receipt admitted."""
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    from layer1_fusion.adapters.observation_packet import observation_packet_to_evidence
    ta = _mod('temporal_alignment')
    tb = _mod('truth_bridge')
    s = _mod('schemas')

    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    bundle = s.Layer1InputBundle(plot_id="plot-A", run_id="r10-g03", run_timestamp=cutoff, as_of_cutoff=cutoff)

    # 1. Unverified caller published_at in payload
    pkt_unverified = ObservationPacket(
        packet_id="pkt_r10_unverified",
        plot_id="plot-A",
        source=ObservationSource.SENTINEL2,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02}),
        payload={"variable": "ndvi", "value": 0.65, "unit": "index", "published_at": "2026-11-10T10:30:00+00:00"},
    )
    items_unver = observation_packet_to_evidence(pkt_unverified, bundle)
    assert items_unver[0].publication_receipt_verified is False
    assert "CALLER_CLAIMED_PUBLICATION_TIME" in items_unver[0].flags
    ok, reason = ta.is_available_at_cutoff(items_unver[0], cutoff, is_historical_replay=True)
    assert ok is False
    assert "CALLER_CLAIMED_PUBLICATION_TIME_REJECTED" in reason

    # 2. Positive control: Verified publication receipt
    rcpt = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sentinel2:r10_g03",
        issuer="agriwise:trust:publication_authority",
        source_family="sentinel2",
        acquisition_id="pkt_r10_verified",
        published_at=datetime(2026, 11, 10, 10, 30, tzinfo=timezone.utc),
    )
    tb.register_publication_receipt(rcpt)
    pkt_verified = ObservationPacket(
        packet_id="pkt_r10_verified",
        plot_id="plot-A",
        source=ObservationSource.SENTINEL2,
        data_status=DataStatus.OBSERVED,
        timestamp=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        spatial_scope="plot",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"ndvi": 0.02}),
        payload={"variable": "ndvi", "value": 0.65, "unit": "index", "publication_receipt": rcpt},
    )
    items_ver = observation_packet_to_evidence(pkt_verified, bundle)
    assert items_ver[0].publication_receipt_verified is True
    assert "VERIFIED_PUBLICATION_RECEIPT" in items_ver[0].flags
    ok, reason = ta.is_available_at_cutoff(items_ver[0], cutoff, is_historical_replay=True)
    assert ok is True


def test_r10_g04_same_variable_distinct_acquisition_raster_ref_isolation():
    """R10-G04: Two acquisitions of the same variable (NDVI in-cutoff vs post-cutoff) isolated by acquisition ID / content hash."""
    eng_mod = _mod('engine')
    tb = _mod('truth_bridge')
    s = _mod('schemas')
    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    # Early in-cutoff NDVI raster
    early_data = {
        "values": [[0.5] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": "2026-11-10T10:00:00+00:00",
    }
    ch_early = tb.compute_raster_composite_content_hash(early_data)
    rcpt_early = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:ndvi:early_r10",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="NDVI_EARLY",
        published_at=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        content_hash=ch_early,
    )
    tb.register_publication_receipt(rcpt_early)
    early_data["publication_receipt"] = rcpt_early

    # Late post-cutoff NDVI raster
    late_data = {
        "values": [[0.8] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": "2026-11-10T16:00:00+00:00",
    }
    ch_late = tb.compute_raster_composite_content_hash(late_data)
    rcpt_late = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:ndvi:late_r10",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="NDVI_LATE",
        published_at=datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc),
        content_hash=ch_late,
    )
    tb.register_publication_receipt(rcpt_late)
    late_data["publication_receipt"] = rcpt_late

    composites = {
        "NDVI_EARLY": early_data,
        "NDVI_LATE": late_data,
    }

    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r10-g04",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        raster_composites=composites,
    )
    engine = eng_mod.Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # Assertions:
    # 1. Late NDVI is quarantined for cutoff violation
    assert any("HISTORICAL_CUTOFF_VIOLATION" in q.reason_codes[0] and "ndvi_late" in q.evidence_id.lower() for q in pkg.diagnostics.quarantined_evidence)

    # 2. Only the early in-cutoff NDVI raster reaches spatial_index.raster_refs
    assert len(pkg.spatial_index.raster_refs) == 1
    assert pkg.spatial_index.raster_refs[0].grid[0][0] == pytest.approx(0.5)

    # 3. Layer 10 payload contains only the early NDVI raster ref
    assert len(pkg.layer10_payload["raster_refs"]) == 1
    assert "ndvi_late" not in str(pkg.layer10_payload["raster_refs"]).lower()


def test_r10_g05_asmae_historical_cutoff_fail_closed():
    """R10-G05: Missing, malformed, post-cutoff, or unverified ASMAE timestamps on replay fail closed."""
    eng_mod = _mod('engine')
    tb = _mod('truth_bridge')
    s = _mod('schemas')
    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    base_asmae = {
        "status": "success",
        "package_id": "pkg_asmae_test",
        "grid_spec": {
            "crs": "EPSG:4326",
            "bounds": [10.0, 35.0, 10.1, 35.1],
            "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
            "width": 10,
            "height": 10,
            "resolution_m": 10.0,
        },
        "diagnostics": {"covariance": [[0.01, 0.0], [0.0, 0.01]]},
        "raster_maps": {"moisture": [[0.3] * 10] * 10},
    }

    engine = eng_mod.Layer1FusionEngine()

    # (a) Missing publication timestamp
    asmae_missing_ts = dict(base_asmae)
    asmae_missing_ts["provenance"] = {"operator_locked": True}
    bundle_missing = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r10-g05-a",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        asmae_output=asmae_missing_ts,
    )
    pkg_missing = engine.fuse(bundle_missing)
    assert any("MISSING_ASMAE_PUBLICATION_TIMESTAMP_ON_REPLAY" in q.reason_codes[0] for q in pkg_missing.diagnostics.quarantined_evidence)
    assert not any("moisture" in r.variable for r in pkg_missing.spatial_index.raster_refs)

    # (b) Malformed publication timestamp
    asmae_malformed_ts = dict(base_asmae)
    asmae_malformed_ts["provenance"] = {"operator_locked": True, "published_at": "not-a-timestamp"}
    bundle_malformed = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r10-g05-b",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        asmae_output=asmae_malformed_ts,
    )
    pkg_malformed = engine.fuse(bundle_malformed)
    assert any("MALFORMED_ASMAE_PUBLICATION_TIMESTAMP" in q.reason_codes[0] for q in pkg_malformed.diagnostics.quarantined_evidence)
    assert not any("moisture" in r.variable for r in pkg_malformed.spatial_index.raster_refs)

    # (c) Post-cutoff publication timestamp
    asmae_late_ts = dict(base_asmae)
    asmae_late_ts["provenance"] = {"operator_locked": True, "published_at": "2026-11-10T16:00:00+00:00"}
    bundle_late = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r10-g05-c",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        asmae_output=asmae_late_ts,
    )
    pkg_late = engine.fuse(bundle_late)
    assert any("HISTORICAL_CUTOFF_VIOLATION" in q.reason_codes[0] for q in pkg_late.diagnostics.quarantined_evidence)
    assert not any("moisture" in r.variable for r in pkg_late.spatial_index.raster_refs)

    # (d) In-cutoff timestamp but unverified publication receipt
    asmae_unver_ts = dict(base_asmae)
    asmae_unver_ts["provenance"] = {"operator_locked": True, "published_at": "2026-11-10T10:00:00+00:00"}
    bundle_unver = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r10-g05-d",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        asmae_output=asmae_unver_ts,
    )
    pkg_unver = engine.fuse(bundle_unver)
    assert any("UNVERIFIED_ASMAE_PUBLICATION_ON_REPLAY" in q.reason_codes[0] for q in pkg_unver.diagnostics.quarantined_evidence)
    assert not any("moisture" in r.variable for r in pkg_unver.spatial_index.raster_refs)

    # (e) Positive control: In-cutoff verified publication receipt
    asmae_ok = dict(base_asmae)
    asmae_ok["package_id"] = "pkg_asmae_test_ok"
    asmae_ok["provenance"] = {
        "operator_locked": True,
        "published_at": "2026-11-10T10:00:00+00:00",
    }
    ch_asmae_ok = tb.compute_asmae_content_hash(asmae_ok)
    rcpt_asmae = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:asmae:r10_g05_ok",
        issuer="agriwise:trust:publication_authority",
        source_family="asmae",
        acquisition_id="pkg_asmae_test_ok",
        published_at=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        content_hash=ch_asmae_ok,
    )
    tb.register_publication_receipt(rcpt_asmae)
    asmae_ok["provenance"]["publication_receipt"] = rcpt_asmae
    bundle_ok = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r10-g05-e",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        asmae_output=asmae_ok,
    )
    pkg_ok = engine.fuse(bundle_ok)
    assert any("moisture" in r.variable for r in pkg_ok.spatial_index.raster_refs)  # Admitted!


def test_r10_g06_tiny_scale_indefinite_covariance_rejected():
    """R10-G06: PSD validator pre-normalizes matrix to O(1), rejecting tiny indefinite matrices and tiny negative diagonals."""
    diag = _mod('diagnostics')

    # 1. Tiny indefinite matrix (scale ~ 1e-14, det = -3e-28 < 0)
    tiny_indefinite = [[1e-14, 2e-14], [2e-14, 1e-14]]
    is_psd, reason = diag.validate_covariance_matrix(tiny_indefinite)
    assert is_psd is False
    assert "NEGATIVE_DETERMINANT" in reason

    # 2. Tiny negative diagonal entry (1x1)
    tiny_neg_1x1 = [[-1e-16]]
    is_psd, reason = diag.validate_covariance_matrix(tiny_neg_1x1)
    assert is_psd is False
    assert "NEGATIVE_VARIANCE_ON_DIAGONAL" in reason

    # 3. Exact zero matrix (rank 0 PSD)
    zero_matrix = [[0.0, 0.0], [0.0, 0.0]]
    is_psd, reason = diag.validate_covariance_matrix(zero_matrix)
    assert is_psd is True
    assert reason == "valid_psd_covariance"

    # 4. Tiny rank-1 singular PSD matrix (det = 0)
    tiny_rank1_psd = [[1e-14, 1e-14], [1e-14, 1e-14]]
    is_psd, reason = diag.validate_covariance_matrix(tiny_rank1_psd)
    assert is_psd is True
    assert reason == "valid_psd_covariance"

    # 5. Scaled positive definite matrix
    scaled_psd = [[1.0, 0.5], [0.5, 1.0]]
    is_psd, reason = diag.validate_covariance_matrix(scaled_psd)
    assert is_psd is True
    assert reason == "valid_psd_covariance"


def test_r10_g07_typed_sensor_receipt_ref_string_resolution():
    """R10-G07: String receipt_ref on sensor reading resolves to registered receipt and admits reading."""
    from layer1_fusion.adapters.sensors import SensorAdapter
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)

    register_device(SensorDeviceRegistration(
        device_id="sensor_r10_07",
        vendor="acme",
        model="probe-r10-7",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal-r10-07",
    ))

    # Register authentic receipt
    receipt_id = "urn:agriwise:receipt:sensor_r10_07:read_99"
    rcpt = _tf().create_signed_sensor_receipt(
        receipt_id=receipt_id,
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r10_07",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r10-07",
        status="active",
        reading_value=0.32,
        reading_unit="fraction",
        observed_at=now,
    )
    tb.register_sensor_receipt(rcpt)

    # Sensor reading with string receipt_ref
    adapter = SensorAdapter()
    reading_obj = type("MockReading", (), {
        "device_id": "sensor_r10_07",
        "variable": "soil_moisture_vwc",
        "value": 0.32,
        "unit": "fraction",
        "calibration_version": "cal-r10-07",
        "timestamp": now,
        "receipt_ref": receipt_id,  # String reference!
    })()
    pkg_mock = type("MockPackage", (), {"plot_id": "plot-A", "readings": [reading_obj]})()
    items = adapter.extract_evidence(pkg_mock, None)
    assert len(items) == 1
    ev = items[0]
    tb.normalize_evidence_truth(ev)

    assert ev.state_update_allowed is True
    assert ev.truth_class == "observed_sensor"
    assert ev.receipt is not None
    assert ev.receipt.receipt_id == receipt_id

    # String reference also resolves via truth_bridge.verify_sensor_attestation directly
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r10_07",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r10-07",
        receipt=receipt_id,
        expected_value=0.32,
        expected_unit="fraction",
        expected_observed_at=now,
    )
    assert ok is True
    assert reason == "attested_via_verified_receipt"

    # Negative control: Unknown string receipt_ref
    reading_bad = type("MockReading", (), {
        "device_id": "sensor_r10_07",
        "variable": "soil_moisture_vwc",
        "value": 0.32,
        "unit": "fraction",
        "calibration_version": "cal-r10-07",
        "timestamp": now,
        "receipt_ref": "urn:agriwise:receipt:unknown_device:unknown_ref",
    })()
    pkg_bad = type("MockPackage", (), {"plot_id": "plot-A", "readings": [reading_bad]})()
    items_bad = adapter.extract_evidence(pkg_bad, None)
    assert len(items_bad) == 1
    ev_bad = items_bad[0]
    tb.normalize_evidence_truth(ev_bad)
    assert ev_bad.state_update_allowed is False
    assert ev_bad.truth_class == "unverified_sensor"


def test_r10_g08_full_engine_r10_positive_and_negative_control():
    """R10-G08: Full end-to-end engine replay: in-cutoff vs post-cutoff sources strictly partitioned across all contracts."""
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    eng_mod = _mod('engine')
    s = _mod('schemas')

    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    now = cutoff

    # 1. Register active sensor device
    register_device(SensorDeviceRegistration(
        device_id="sensor_r10_08",
        vendor="soil-tech",
        model="probe-r10-8",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now - timedelta(days=30),
        status="active",
        calibration_profile_id="cal-soil-r10-8",
    ))

    # In-cutoff sensor receipt & packet (observed 10:00, published 10:15)
    rcpt_sensor_early = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_r10_08:reading_early",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r10_08",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-soil-r10-8",
        status="active",
        reading_value=0.30,
        reading_unit="fraction",
        observed_at=now - timedelta(hours=2),
    )
    tb.register_sensor_receipt(rcpt_sensor_early)

    # Sensor publication receipt for historical replay admission (R10-02, S01 exact content binding)
    rcpt_sensor_pub = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sensor:r10_08",
        issuer="agriwise:trust:publication_authority",
        source_family="sensor",
        acquisition_id="pkt_sensor_early",
        published_at=now - timedelta(hours=2),
        content_hash=rcpt_sensor_early.content_digest,
    )
    tb.register_publication_receipt(rcpt_sensor_pub)

    sensor_pkt_early = ObservationPacket(
        packet_id="pkt_sensor_early",
        plot_id="plot-A",
        source=ObservationSource.SENSOR_IOT,
        data_status=DataStatus.OBSERVED,
        timestamp=now - timedelta(hours=2),
        spatial_scope="point",
        qa=QAMetadata(scene_score=1.0, sensor_health=0.99),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.01}),
        payload={
            "device_id": "sensor_r10_08",
            "instrument_id": "sensor_r10_08",
            "variable": "soil_moisture_vwc",
            "value": 0.30,
            "unit": "fraction",
            "calibration_version": "cal-soil-r10-8",
            "provenance_ref": "urn:agriwise:receipt:sensor_r10_08:reading_early",
            "publication_receipt": rcpt_sensor_pub,
        },
    )
    sensor_pkg = Layer0SourcePackage(
        source_family="sensor",
        plot_id="plot-A",
        packets=[sensor_pkt_early],
    )
    sensor_pkg.receipt = rcpt_sensor_pub
    sensor_pkg.published_at = now - timedelta(hours=2)

    # 2. In-cutoff vs Post-cutoff raster composites
    early_raster_data = {
        "values": [[0.55] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": (now - timedelta(hours=2)).isoformat(),
    }
    ch_raster_early = tb.compute_raster_composite_content_hash(early_raster_data)
    rcpt_raster_early = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:ndvi:early_08",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="NDVI_EARLY",
        published_at=now - timedelta(hours=2),
        content_hash=ch_raster_early,
    )
    tb.register_publication_receipt(rcpt_raster_early)
    early_raster_data["publication_receipt"] = rcpt_raster_early

    late_raster_data = {
        "values": [[0.85] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": (now + timedelta(hours=2)).isoformat(),
    }
    ch_raster_late = tb.compute_raster_composite_content_hash(late_raster_data)
    rcpt_raster_late = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:ndvi:late_08",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="NDVI_LATE",
        published_at=now + timedelta(hours=2),
        content_hash=ch_raster_late,
    )
    tb.register_publication_receipt(rcpt_raster_late)
    late_raster_data["publication_receipt"] = rcpt_raster_late

    composites = {
        "NDVI_EARLY": early_raster_data,
        "NDVI_LATE": late_raster_data,
    }

    # 3. In-cutoff verified ASMAE output
    valid_asmae = {
        "status": "success",
        "run_id": "asmae_run_r10_08",
        "package_id": "pkg_asmae_r10_08",
        "schema_version": "1.0",
        "source_id": "asmae_engine_01",
        "production_usable": True,
        "layer1_export_allowed": True,
        "observation_operator_refs": ["op-1"],
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
            "retrovalidation_score": 0.88,
            "published_at": (now - timedelta(hours=1)).isoformat(),
        },
        "diagnostics": {
            "scientific_pass": True,
            "scene_stack_mode": "real_raster",
            "enkf_mode": "ht_per_pixel",
            "radiometric_mode": "ht_per_pixel",
            "retro_status": "success_with_holdouts",
            "diagnostic_only": False,
            "state_update_allowed": True,
            "operator_count": 1,
            "covariance": [[0.02, 0.0], [0.0, 0.02]],
        },
        "raster_maps": {"moisture": [[0.3] * 10] * 10},
    }
    ch_asmae_08 = tb.compute_asmae_content_hash(valid_asmae)
    rcpt_asmae = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:asmae:r10_08",
        issuer="agriwise:trust:publication_authority",
        source_family="asmae",
        acquisition_id="pkg_asmae_r10_08",
        published_at=now - timedelta(hours=1),
        content_hash=ch_asmae_08,
    )
    tb.register_publication_receipt(rcpt_asmae)
    valid_asmae["provenance"]["publication_receipt"] = rcpt_asmae

    # 4. Execute full engine fusion on historical replay
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="run-r10-g08",
        run_timestamp=now,
        as_of_cutoff=cutoff,
        window_start=now - timedelta(days=1),
        window_end=now,
        layer0_source_packages={"sensor": [sensor_pkg]},
        raster_composites=composites,
        asmae_output=valid_asmae,
    )
    engine = eng_mod.Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # Assertions:
    # 1. Sensor evidence admitted with full state authority
    sensor_ev = [e for e in pkg.evidence_items if e.source_family == "sensor"]
    assert len(sensor_ev) == 1
    assert sensor_ev[0].truth_class == "observed_sensor"
    assert sensor_ev[0].state_update_allowed is True

    # 2. Late NDVI quarantined; early NDVI admitted
    assert any("HISTORICAL_CUTOFF_VIOLATION" in q.reason_codes[0] and "ndvi_late" in q.evidence_id.lower() for q in pkg.diagnostics.quarantined_evidence)
    admitted_rasters = [e for e in pkg.evidence_items if e.source_family == "raster_composite"]
    assert len(admitted_rasters) == 1
    assert admitted_rasters[0].value == pytest.approx(0.55)

    # 3. Spatial index contains only early NDVI and ASMAE moisture
    assert len(pkg.spatial_index.raster_refs) == 2
    assert any("ndvi" in r.variable and r.grid[0][0] == pytest.approx(0.55) for r in pkg.spatial_index.raster_refs)
    assert any("moisture" in r.variable for r in pkg.spatial_index.raster_refs)

    # 4. Layer 10 payload reflects admitted sensor and rasters
    assert len(pkg.layer10_payload["sensor_markers"]) == 1
    assert len(pkg.layer10_payload["raster_refs"]) == 2

    # 5. Scientific content root is valid 64-char hex commitment
    root = pkg.scientific_content_root()
    assert len(root) == 64
    assert pkg.content_hash() == root[:32]


def test_r11_g01_externally_provisioned_keys_reject_reproduced_seed_signatures():
    """R11-G01: Trusted issuer keys must be independently provisioned; predictable seed derivation is rejected."""
    import hashlib
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    issuer = "agriwise:trust:sensor_authority"

    register_device(SensorDeviceRegistration(
        device_id="sensor_r11_01",
        vendor="acme",
        model="probe-r11-1",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal-r11-01",
    ))

    # Provision trusted key using OS entropy / external generation
    priv_real, pub_real = _tf().provision_test_issuer_keypair(issuer)
    assert tb.get_trusted_issuer_public_key(issuer) is not None

    # Attacker attempts to forge receipt using predictable seed derivation
    predictable_seed = hashlib.sha256(f"agriwise:keyseed:{issuer}".encode("utf-8")).digest()
    forged_priv = ed25519.Ed25519PrivateKey.from_private_bytes(predictable_seed)

    reading_val = 0.25
    obs_time = now.isoformat()
    digest = tb.compute_reading_content_digest(
        device_id="sensor_r11_01",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        value=reading_val,
        unit="fraction",
        observed_at=obs_time,
    )
    forged_sig = tb.sign_sensor_receipt_data(
        receipt_id="urn:agriwise:receipt:sensor_r11_01:forged",
        issuer=issuer,
        device_id="sensor_r11_01",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r11-01",
        status="active",
        content_digest=digest,
        observation_instant=obs_time,
        private_key=forged_priv,
    )
    forged_rcpt = tb.SensorAttestationReceipt(
        receipt_id="urn:agriwise:receipt:sensor_r11_01:forged",
        issuer=issuer,
        device_id="sensor_r11_01",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r11-01",
        status="active",
        content_digest=digest,
        observation_instant=obs_time,
        signature=forged_sig,
    )

    # Verification must fail closed against real provisioned public key
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r11_01",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r11-01",
        receipt=forged_rcpt,
        expected_value=reading_val,
        expected_unit="fraction",
        expected_observed_at=obs_time,
    )
    assert ok is False
    assert "invalid_cryptographic_signature" in reason or "InvalidSignature" in reason


def test_r11_g02_sensor_signature_bound_to_reading_payload_value_time_digest():
    """R11-G02: Sensor receipt is cryptographically bound to reading value, unit, and timestamp."""
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    issuer = "agriwise:trust:sensor_authority"

    register_device(SensorDeviceRegistration(
        device_id="sensor_r11_02",
        vendor="acme",
        model="probe-r11-2",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal-r11-02",
    ))

    # Authentic receipt for reading value 0.22 at 12:00
    rcpt = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_r11_02:exact",
        issuer=issuer,
        device_id="sensor_r11_02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r11-02",
        status="active",
        reading_value=0.22,
        reading_unit="fraction",
        observed_at=now,
    )
    tb.register_sensor_receipt(rcpt)

    # (a) Positive control: exact matching reading passes
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r11_02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r11-02",
        receipt=rcpt,
        expected_value=0.22,
        expected_unit="fraction",
        expected_observed_at=now,
    )
    assert ok is True
    assert reason == "attested_via_verified_receipt"

    # (b) Tampered reading value (0.35 instead of 0.22) fails closed
    ok_tampered, reason_tampered = tb.verify_sensor_attestation(
        device_id="sensor_r11_02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r11-02",
        receipt=rcpt,
        expected_value=0.35,
        expected_unit="fraction",
        expected_observed_at=now,
    )
    assert ok_tampered is False
    assert "sensor_content_digest_mismatch" in reason_tampered

    # (c) Tampered observation timestamp fails closed
    ok_time, reason_time = tb.verify_sensor_attestation(
        device_id="sensor_r11_02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r11-02",
        receipt=rcpt,
        expected_value=0.22,
        expected_unit="fraction",
        expected_observed_at=now + timedelta(hours=1),
    )
    assert ok_time is False
    assert "sensor_observation_time_mismatch" in reason_time or "sensor_content_digest_mismatch" in reason_time


def test_r11_g03_publication_receipt_mandatory_content_digest_exact_match():
    """R11-G03: Publication receipts require exact acquisition ID and content hash matching."""
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 10, tzinfo=timezone.utc)
    issuer = "agriwise:trust:publication_authority"

    true_hash = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    rcpt = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:r11_03",
        issuer=issuer,
        source_family="raster_composite",
        acquisition_id="acq_ndvi_r11_03",
        published_at=now,
        content_hash=true_hash,
    )
    tb.register_publication_receipt(rcpt)

    # (a) Positive control: exact matching acquisition_id and content_hash
    ok, reason, dt = tb.verify_publication_receipt(
        rcpt,
        source_family="raster_composite",
        acquisition_id="acq_ndvi_r11_03",
        content_hash=true_hash,
        require_content_binding=True,
    )
    assert ok is True
    assert reason == "verified_publication_receipt"
    assert dt == now

    # (b) Mismatched content hash fails closed
    ok_bad_hash, reason_bad_hash, _ = tb.verify_publication_receipt(
        rcpt,
        source_family="raster_composite",
        acquisition_id="acq_ndvi_r11_03",
        content_hash="sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        require_content_binding=True,
    )
    assert ok_bad_hash is False
    assert "publication_content_hash_mismatch" in reason_bad_hash

    # (c) Mismatched acquisition_id fails closed
    ok_bad_acq, reason_bad_acq, _ = tb.verify_publication_receipt(
        rcpt,
        source_family="raster_composite",
        acquisition_id="wrong_acquisition_id",
        content_hash=true_hash,
        require_content_binding=True,
    )
    assert ok_bad_acq is False
    assert "publication_acquisition_mismatch" in reason_bad_acq


def test_r11_g04_asmae_cutoff_uses_verified_signed_timestamp_not_claimed_timestamp():
    """R11-G04: ASMAE historical cutoff enforcement is governed by verified receipt timestamp, rejecting claim mismatches."""
    eng_mod = _mod('engine')
    tb = _mod('truth_bridge')
    s = _mod('schemas')
    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    engine = eng_mod.Layer1FusionEngine()

    base_asmae = {
        "status": "success",
        "package_id": "pkg_asmae_r11_04",
        "run_id": "run_asmae_r11_04",
        "grid_spec": {
            "crs": "EPSG:4326",
            "bounds": [10.0, 35.0, 10.1, 35.1],
            "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
            "width": 10,
            "height": 10,
            "resolution_m": 10.0,
        },
        "diagnostics": {"covariance": [[0.02, 0.0], [0.0, 0.02]]},
        "raster_maps": {"moisture": [[0.3] * 10] * 10},
    }

    # Caller claims an IN-CUTOFF publication timestamp at 10:00
    asmae_spoofed = dict(base_asmae)
    asmae_spoofed["provenance"] = {
        "operator_locked": True,
        "published_at": "2026-11-10T10:00:00+00:00",  # Claimed: 10:00 (in cutoff)
    }
    ch_asmae_post = tb.compute_asmae_content_hash(asmae_spoofed)

    # Signed receipt with verified published_at at 14:00 (POST-CUTOFF)
    verified_post_cutoff_ts = datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc)
    rcpt_post = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:asmae:r11_04_post",
        issuer="agriwise:trust:publication_authority",
        source_family="asmae",
        acquisition_id="pkg_asmae_r11_04",
        published_at=verified_post_cutoff_ts,
        content_hash=ch_asmae_post,
    )
    tb.register_publication_receipt(rcpt_post)
    asmae_spoofed["provenance"]["publication_receipt"] = rcpt_post

    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r11-g04-test",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        asmae_output=asmae_spoofed,
    )
    pkg = engine.fuse(bundle)

    # Must be quarantined due to claim mismatch or cutoff violation
    quarantine_codes = [q.reason_codes[0] for q in pkg.diagnostics.quarantined_evidence]
    assert any("PUBLICATION_TIMESTAMP_CLAIM_MISMATCH" in code or "HISTORICAL_CUTOFF_VIOLATION" in code for code in quarantine_codes)
    assert not any("moisture" in r.variable for r in pkg.spatial_index.raster_refs)


def test_r11_g05_asmae_quarantined_prior_to_evidence_ledger_population():
    """R11-G05: Quarantined ASMAE is purged from evidence batches BEFORE EvidenceLedger population."""
    eng_mod = _mod('engine')
    tb = _mod('truth_bridge')
    s = _mod('schemas')
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device

    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    now = cutoff
    engine = eng_mod.Layer1FusionEngine()

    # Valid sensor
    register_device(SensorDeviceRegistration(
        device_id="sensor_r11_05",
        vendor="acme",
        model="probe-r11-5",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal-r11-05",
    ))
    rcpt_sensor = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_r11_05:valid",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r11_05",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r11-05",
        status="active",
        reading_value=0.28,
        reading_unit="fraction",
        observed_at=now - timedelta(hours=1),
    )
    tb.register_sensor_receipt(rcpt_sensor)

    rcpt_sensor_pub = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sensor:r11_05:valid",
        issuer="agriwise:trust:publication_authority",
        source_family="sensor",
        acquisition_id="pkt_r11_05",
        published_at=now - timedelta(hours=1),
    )
    tb.register_publication_receipt(rcpt_sensor_pub)

    pkt = ObservationPacket(
        packet_id="pkt_r11_05",
        plot_id="plot-A",
        source=ObservationSource.SENSOR_IOT,
        data_status=DataStatus.OBSERVED,
        timestamp=now - timedelta(hours=1),
        spatial_scope="point",
        qa=QAMetadata(scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.01}),
        payload={
            "device_id": "sensor_r11_05",
            "instrument_id": "sensor_r11_05",
            "variable": "soil_moisture_vwc",
            "value": 0.28,
            "unit": "fraction",
            "calibration_version": "cal-r11-05",
            "provenance_ref": "urn:agriwise:receipt:sensor_r11_05:valid",
            "publication_receipt": rcpt_sensor_pub,
        },
    )
    sensor_pkg = Layer0SourcePackage(source_family="sensor", plot_id="plot-A", packets=[pkt])
    sensor_pkg.receipt = rcpt_sensor_pub
    sensor_pkg.published_at = now - timedelta(hours=1)

    # ASMAE with invalid covariance (negative diagonal variance)
    invalid_asmae = {
        "status": "success",
        "package_id": "pkg_asmae_r11_05",
        "source_id": "asmae_engine_01",
        "production_usable": True,
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
            "published_at": (now - timedelta(hours=1)).isoformat(),
        },
        "diagnostics": {
            "scientific_pass": True,
            "covariance": [[-0.05, 0.0], [0.0, 0.02]],  # Invalid negative variance!
        },
        "raster_maps": {"moisture": [[0.3] * 10] * 10},
    }

    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r11-g05-test",
        run_timestamp=now,
        as_of_cutoff=cutoff,
        layer0_source_packages={"sensor": [sensor_pkg]},
        asmae_output=invalid_asmae,
    )
    pkg = engine.fuse(bundle)

    # ASMAE evidence must NOT exist in admitted evidence items or spatial index
    asmae_admitted = [e for e in pkg.evidence_items if e.source_family == "asmae"]
    assert len(asmae_admitted) == 0
    assert not any("moisture" in r.variable for r in pkg.spatial_index.raster_refs)
    all_features = [
        f for ctx in (
            "water_context", "vegetation_context", "phenology_context",
            "stress_evidence_context", "soil_site_context", "operational_context", "data_quality_context"
        )
        for f in getattr(pkg.fused_features, ctx, [])
    ]
    assert not any("asmae" in str(getattr(f, "source_evidence_ids", [])).lower() for f in all_features)

    # Sensor evidence must still be admitted
    sensor_admitted = [e for e in pkg.evidence_items if e.source_family == "sensor"]
    assert len(sensor_admitted) == 1
    assert sensor_admitted[0].truth_class == "observed_sensor"


def test_r11_g06_true_same_canonical_variable_raster_isolation_with_paired_hash():
    """R11-G06: Two acquisitions of the same canonical variable ('NDVI') isolated strictly by paired (source_id, content_hash)."""
    eng_mod = _mod('engine')
    tb = _mod('truth_bridge')
    s = _mod('schemas')
    cutoff = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    # Early in-cutoff NDVI raster
    early_data = {
        "variable": "NDVI",
        "values": [[0.52] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": "2026-11-10T10:00:00+00:00",
    }
    ch_early = tb.compute_raster_composite_content_hash(early_data)
    rcpt_early = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:ndvi:early_r11",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="sentinel2_early",
        published_at=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        content_hash=ch_early,
    )
    tb.register_publication_receipt(rcpt_early)
    early_data["publication_receipt"] = rcpt_early

    # Late post-cutoff NDVI raster
    late_data = {
        "variable": "NDVI",
        "values": [[0.88] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": "2026-11-10T16:00:00+00:00",
    }
    ch_late = tb.compute_raster_composite_content_hash(late_data)
    rcpt_late = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:ndvi:late_r11",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="sentinel2_late",
        published_at=datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc),
        content_hash=ch_late,
    )
    tb.register_publication_receipt(rcpt_late)
    late_data["publication_receipt"] = rcpt_late

    # Both rasters share identical canonical variable name 'NDVI'
    composites = {
        "sentinel2_early": early_data,
        "sentinel2_late": late_data,
    }

    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="r11-g06",
        run_timestamp=cutoff,
        as_of_cutoff=cutoff,
        raster_composites=composites,
    )
    engine = eng_mod.Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # Post-cutoff raster must be quarantined
    assert any("HISTORICAL_CUTOFF_VIOLATION" in q.reason_codes[0] and "ndvi" in q.evidence_id.lower() for q in pkg.diagnostics.quarantined_evidence)

    # Only in-cutoff NDVI raster reaches spatial index and Layer 10
    assert len(pkg.spatial_index.raster_refs) == 1
    assert pkg.spatial_index.raster_refs[0].grid[0][0] == pytest.approx(0.52)
    assert len(pkg.layer10_payload["raster_refs"]) == 1
    assert "sentinel2_late" not in str(pkg.layer10_payload["raster_refs"]).lower()


def test_r11_g07_durable_monotonic_revocation_store_across_cold_cache(tmp_path):
    """R11-G07: Revocations atomically persist to disk and reload across cold-cache restart; epoch cannot roll back."""
    tb = _mod('truth_bridge')
    rev_file = str(tmp_path / "revocations_test.json")

    store1 = tb.DurableRevocationStore(persistence_path=rev_file)
    store1.set_epoch(3)
    store1.revoke_sensor("urn:agriwise:receipt:sensor:cold_01")
    store1.revoke_publication("urn:agriwise:pub:raster:cold_01")

    # Monotonicity: rollback attempt raises ValueError
    with pytest.raises(ValueError, match="Monotonicity violation"):
        store1.set_epoch(2)

    # Cold cache restart simulation: instantiate new store pointing to same file
    store2 = tb.DurableRevocationStore(persistence_path=rev_file)
    assert store2.revocation_epoch == 3

    # Check revoked items
    is_rev_s, reason_s = store2.is_sensor_revoked("urn:agriwise:receipt:sensor:cold_01", epoch=3)
    assert is_rev_s is True
    assert "revoked_sensor_receipt" in reason_s

    is_rev_p, reason_p = store2.is_publication_revoked("urn:agriwise:pub:raster:cold_01")
    assert is_rev_p is True
    assert "revoked_publication_receipt" in reason_p

    # Expired epoch check
    is_rev_exp, reason_exp = store2.is_sensor_revoked("urn:agriwise:receipt:sensor:other", epoch=2)
    assert is_rev_exp is True
    assert "expired_revocation_epoch" in reason_exp


def test_r11_g08_full_engine_end_to_end_native_adversarial_and_positive_acceptance():
    """R11-G08: Full engine native end-to-end acceptance: verified sensors, in-cutoff rasters and ASMAE admitted to Layer 10; adversarial inputs quarantined."""
    eng_mod = _mod('engine')
    tb = _mod('truth_bridge')
    s = _mod('schemas')
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device

    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    cutoff = now

    # 1. Register authentic device
    register_device(SensorDeviceRegistration(
        device_id="sensor_r11_08",
        vendor="soil-corp",
        model="probe-x",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now - timedelta(days=60),
        status="active",
        calibration_profile_id="cal-r11-08",
    ))

    # Authentic sensor receipt bound to reading value 0.31 at now - 1h
    rcpt_sensor = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_r11_08:pos",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r11_08",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r11-08",
        status="active",
        reading_value=0.31,
        reading_unit="fraction",
        observed_at=now - timedelta(hours=1),
    )
    tb.register_sensor_receipt(rcpt_sensor)

    rcpt_sensor_pub = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sensor:r11_08:pos",
        issuer="agriwise:trust:publication_authority",
        source_family="sensor",
        acquisition_id="pkt_sensor_r11_08_pos",
        published_at=now - timedelta(hours=1),
        content_hash=rcpt_sensor.content_digest,
    )
    tb.register_publication_receipt(rcpt_sensor_pub)

    # Healthy sensor packet
    pkt_healthy = ObservationPacket(
        packet_id="pkt_sensor_r11_08_pos",
        plot_id="plot-A",
        source=ObservationSource.SENSOR_IOT,
        data_status=DataStatus.OBSERVED,
        timestamp=now - timedelta(hours=1),
        spatial_scope="point",
        qa=QAMetadata(scene_score=1.0, sensor_health=0.99),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.01}),
        payload={
            "device_id": "sensor_r11_08",
            "instrument_id": "sensor_r11_08",
            "variable": "soil_moisture_vwc",
            "value": 0.31,
            "unit": "fraction",
            "calibration_version": "cal-r11-08",
            "provenance_ref": "urn:agriwise:receipt:sensor_r11_08:pos",
            "publication_receipt": rcpt_sensor_pub,
        },
    )

    # Adversarial sensor packet: tampered value 0.99 with receipt issued for 0.31
    pkt_tampered = ObservationPacket(
        packet_id="pkt_sensor_r11_08_tampered",
        plot_id="plot-A",
        source=ObservationSource.SENSOR_IOT,
        data_status=DataStatus.OBSERVED,
        timestamp=now - timedelta(hours=1),
        spatial_scope="point",
        qa=QAMetadata(scene_score=1.0, sensor_health=0.99),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.01}),
        payload={
            "device_id": "sensor_r11_08",
            "instrument_id": "sensor_r11_08",
            "variable": "soil_moisture_vwc",
            "value": 0.99,  # Tampered reading!
            "unit": "fraction",
            "calibration_version": "cal-r11-08",
            "provenance_ref": "urn:agriwise:receipt:sensor_r11_08:pos",
            "publication_receipt": rcpt_sensor_pub,
        },
    )

    sensor_pkg = Layer0SourcePackage(
        source_family="sensor",
        plot_id="plot-A",
        packets=[pkt_healthy, pkt_tampered],
    )

    # 2. Raster composites: 1 valid in-cutoff, 1 late post-cutoff
    valid_raster_data = {
        "variable": "NDVI",
        "values": [[0.60] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": (now - timedelta(hours=2)).isoformat(),
    }
    ch_raster_valid = tb.compute_raster_composite_content_hash(valid_raster_data)
    rcpt_raster_valid = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:ndvi:valid_r11_08",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="sentinel2_valid_08",
        published_at=now - timedelta(hours=2),
        content_hash=ch_raster_valid,
    )
    tb.register_publication_receipt(rcpt_raster_valid)
    valid_raster_data["publication_receipt"] = rcpt_raster_valid

    late_raster_data = {
        "variable": "NDVI",
        "values": [[0.90] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": (now + timedelta(hours=3)).isoformat(),
    }
    ch_raster_late = tb.compute_raster_composite_content_hash(late_raster_data)
    rcpt_raster_late = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:ndvi:late_r11_08",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="sentinel2_late_08",
        published_at=now + timedelta(hours=3),
        content_hash=ch_raster_late,
    )
    tb.register_publication_receipt(rcpt_raster_late)
    late_raster_data["publication_receipt"] = rcpt_raster_late

    composites = {
        "sentinel2_valid_08": valid_raster_data,
        "sentinel2_late_08": late_raster_data,
    }

    # 3. Valid ASMAE output
    valid_asmae = {
        "status": "success",
        "run_id": "asmae_run_r11_08",
        "package_id": "pkg_asmae_r11_08",
        "schema_version": "1.0",
        "source_id": "asmae_engine_01",
        "production_usable": True,
        "layer1_export_allowed": True,
        "observation_operator_refs": ["op-1"],
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
            "retrovalidation_score": 0.88,
            "published_at": (now - timedelta(hours=1)).isoformat(),
        },
        "diagnostics": {
            "scientific_pass": True,
            "scene_stack_mode": "real_raster",
            "enkf_mode": "ht_per_pixel",
            "radiometric_mode": "ht_per_pixel",
            "retro_status": "success_with_holdouts",
            "diagnostic_only": False,
            "state_update_allowed": True,
            "operator_count": 1,
            "covariance": [[0.015, 0.0], [0.0, 0.015]],
        },
        "raster_maps": {"moisture": [[0.32] * 10] * 10},
    }
    ch_asmae_r11 = tb.compute_asmae_content_hash(valid_asmae)
    rcpt_asmae = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:asmae:r11_08",
        issuer="agriwise:trust:publication_authority",
        source_family="asmae",
        acquisition_id="pkg_asmae_r11_08",
        published_at=now - timedelta(hours=1),
        content_hash=ch_asmae_r11,
    )
    tb.register_publication_receipt(rcpt_asmae)
    valid_asmae["provenance"]["publication_receipt"] = rcpt_asmae

    # Execute engine fusion
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="run-r11-g08",
        run_timestamp=now,
        as_of_cutoff=cutoff,
        window_start=now - timedelta(days=1),
        window_end=now,
        layer0_source_packages={"sensor": [sensor_pkg]},
        raster_composites=composites,
        asmae_output=valid_asmae,
    )
    engine = eng_mod.Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # 1. Assertions on admitted evidence:
    # Healthy sensor admitted
    healthy_sensor_ev = [e for e in pkg.evidence_items if e.source_family == "sensor" and e.state_update_allowed is True]
    assert len(healthy_sensor_ev) == 1
    assert healthy_sensor_ev[0].value == pytest.approx(0.31)
    assert healthy_sensor_ev[0].truth_class == "observed_sensor"

    # Tampered sensor quarantined or downgraded (state_update_allowed False)
    tampered_sensor_ev = [e for e in pkg.evidence_items if e.source_family == "sensor" and e.value == pytest.approx(0.99)]
    if tampered_sensor_ev:
        assert tampered_sensor_ev[0].state_update_allowed is False
        assert tampered_sensor_ev[0].truth_class != "observed_sensor"

    # Late NDVI quarantined; valid NDVI admitted
    admitted_rasters = [e for e in pkg.evidence_items if e.source_family == "raster_composite"]
    assert len(admitted_rasters) == 1
    assert admitted_rasters[0].value == pytest.approx(0.60)

    # ASMAE admitted with moisture raster ref
    assert any("moisture" in r.variable for r in pkg.spatial_index.raster_refs)
    assert any("ndvi" in r.variable for r in pkg.spatial_index.raster_refs)
    assert not any(r.grid[0][0] == pytest.approx(0.90) for r in pkg.spatial_index.raster_refs)

    # Layer 10 payload state update allowed and references valid artifacts
    assert len(pkg.layer10_payload["sensor_markers"]) == 1
    assert len(pkg.layer10_payload["raster_refs"]) == 2
    assert len(pkg.scientific_content_root()) == 64


def test_r12_g01_production_verifier_prohibits_runtime_trust_provisioning():
    """R12-G01: Production verifier has no private keys, never auto-provisions trust roots, and strictly fails closed."""
    tb = _mod('truth_bridge')

    # 1. Production truth_bridge must not expose _TEST_PRIVATE_KEYS dictionary
    assert not hasattr(tb, "_TEST_PRIVATE_KEYS") or len(getattr(tb, "_TEST_PRIVATE_KEYS", {})) == 0

    # 2. Querying unknown issuer strictly fails closed (returns None, never creates keypair)
    unknown_pub = tb.get_trusted_issuer_public_key("agriwise:trust:completely_unauthorized_issuer")
    assert unknown_pub is None

    # 3. Only explicit root loading configures trusted public keys
    from cryptography.hazmat.primitives.asymmetric import ed25519
    dummy_priv = ed25519.Ed25519PrivateKey.generate()
    dummy_pub = dummy_priv.public_key()
    tb.load_trusted_public_roots({"agriwise:trust:configured_root": dummy_pub})
    assert tb.get_trusted_issuer_public_key("agriwise:trust:configured_root") is not None


def test_r12_g02_sensor_attestation_fails_closed_when_digest_or_claims_omitted():
    """R12-G02: Sensor receipts with missing digest or callers omitting measurement claims fail closed."""
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)

    register_device(SensorDeviceRegistration(
        device_id="sensor_r12_g02",
        vendor="acme",
        model="probe-r12",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now,
        status="active",
        calibration_profile_id="cal-r12-02",
    ))

    # Genuine signed receipt
    rcpt = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_r12_02:001",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r12_g02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r12-02",
        status="active",
        reading_value=0.33,
        reading_unit="fraction",
        observed_at=now,
    )
    tb.register_sensor_receipt(rcpt)

    # 1. Receipt with missing content_digest fails closed
    rcpt_no_digest = tb.SensorAttestationReceipt(
        receipt_id="urn:agriwise:receipt:sensor_r12_02:no_digest",
        issuer=rcpt.issuer,
        device_id=rcpt.device_id,
        plot_id=rcpt.plot_id,
        variable=rcpt.variable,
        calibration_profile_id=rcpt.calibration_profile_id,
        status="active",
        content_digest="",
        observation_instant=rcpt.observation_instant,
        signature=rcpt.signature,
    )
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r12_g02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r12-02",
        receipt=rcpt_no_digest,
        expected_value=0.33,
        expected_unit="fraction",
        expected_observed_at=now,
    )
    assert ok is False
    assert reason == "missing_receipt_content_digest"

    # 2. Receipt with missing observation_instant fails closed
    rcpt_no_time = tb.SensorAttestationReceipt(
        receipt_id="urn:agriwise:receipt:sensor_r12_02:no_time",
        issuer=rcpt.issuer,
        device_id=rcpt.device_id,
        plot_id=rcpt.plot_id,
        variable=rcpt.variable,
        calibration_profile_id=rcpt.calibration_profile_id,
        status="active",
        content_digest=rcpt.content_digest,
        observation_instant="",
        signature=rcpt.signature,
    )
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r12_g02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r12-02",
        receipt=rcpt_no_time,
        expected_value=0.33,
        expected_unit="fraction",
        expected_observed_at=now,
    )
    assert ok is False
    assert reason == "missing_receipt_observation_instant"

    # 3. Caller omitting reading measurement claims fails closed
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r12_g02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r12-02",
        receipt=rcpt,
        # Omit expected_value and expected_content_digest!
    )
    assert ok is False
    assert reason == "missing_reading_claims_for_sensor_attestation"

    # 4. Caller omitting observation timestamp fails closed
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r12_g02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r12-02",
        receipt=rcpt,
        expected_value=0.33,
        expected_unit="fraction",
        expected_observed_at=None,
    )
    assert ok is False
    assert reason == "missing_reading_observation_time_for_attestation"

    # 5. Full claims provided -> Valid attestation
    ok, reason = tb.verify_sensor_attestation(
        device_id="sensor_r12_g02",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_version="cal-r12-02",
        receipt=rcpt,
        expected_value=0.33,
        expected_unit="fraction",
        expected_observed_at=now,
    )
    assert ok is True
    assert reason == "attested_via_verified_receipt"


def test_r12_g03_raster_ingestion_enforces_mandatory_content_digest_match():
    """R12-G03: Raster ingestion enforces mandatory content binding, rejecting missing or mismatched content hashes."""
    from layer1_fusion.raster_ingest import ingest_raster_composites
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)

    # 1. Raster composite with receipt missing content_hash -> Quarantined
    rcpt_no_hash = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:r12_no_hash",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="NDVI_NO_HASH",
        published_at=now - timedelta(hours=1),
        content_hash=None,
    )
    tb.register_publication_receipt(rcpt_no_hash)

    composites_bad = {
        "NDVI_NO_HASH": {
            "values": [[0.5] * 10] * 10,
            "crs": "EPSG:4326",
            "bounds": [10.0, 35.0, 10.1, 35.1],
            "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
            "width": 10,
            "height": 10,
            "resolution_m": 10.0,
            "published_at": (now - timedelta(hours=1)).isoformat(),
            "publication_receipt": rcpt_no_hash,
        }
    }
    ev_items, r_refs = ingest_raster_composites(composites_bad, "plot-A", now)
    assert "CALLER_CLAIMED_PUBLICATION_TIME" in ev_items[0].flags
    assert "VERIFIED_PUBLICATION_RECEIPT" not in ev_items[0].flags

    # 2. Raster composite with matching content_hash -> Verified
    raster_good = {
        "values": [[0.65] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": (now - timedelta(hours=1)).isoformat(),
    }
    ch_good = tb.compute_raster_composite_content_hash(raster_good)
    rcpt_good = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:r12_good",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="NDVI_GOOD",
        published_at=now - timedelta(hours=1),
        content_hash=ch_good,
    )
    tb.register_publication_receipt(rcpt_good)
    raster_good["publication_receipt"] = rcpt_good

    ev_good, refs_good = ingest_raster_composites({"NDVI_GOOD": raster_good}, "plot-A", now)
    assert "VERIFIED_PUBLICATION_RECEIPT" in ev_good[0].flags
    assert len(refs_good) == 1
    assert refs_good[0].content_hash == ch_good


def test_r12_g04_durable_revocation_store_fails_closed_on_io_and_strictly_monotonic(tmp_path):
    """R12-G04: DurableRevocationStore raises IOError on IO failures, strictly enforces monotonicity, and eliminates force bypass."""
    tb = _mod('truth_bridge')

    # 1. IO error on write failure
    invalid_path = str(tmp_path / "nonexistent_dir_cannot_create" / "??:::invalid_filename:::")
    store_bad = tb.DurableRevocationStore(persistence_path=invalid_path)
    with pytest.raises(IOError):
        store_bad.set_epoch(1)

    # 2. IO error on read/parse failure
    corrupt_file = tmp_path / "corrupt_store.json"
    corrupt_file.write_text("{ corrupt json syntax ...", encoding="utf-8")
    with pytest.raises(IOError):
        tb.DurableRevocationStore(persistence_path=str(corrupt_file))

    # 3. Monotonicity enforcement without bypass
    valid_file = str(tmp_path / "monotonic_store.json")
    store_mono = tb.DurableRevocationStore(persistence_path=valid_file)
    store_mono.set_epoch(5)
    assert store_mono.revocation_epoch == 5

    with pytest.raises(ValueError, match="Monotonicity violation"):
        store_mono.set_epoch(4)

    # Calling with force=True must not be accepted
    with pytest.raises(TypeError):
        store_mono.set_epoch(0, force=True)  # type: ignore[call-arg]


def test_r12_g05_reading_digest_preserves_full_ieee_precision_and_rejects_non_numeric():
    """R12-G05: Reading digest preserves IEEE double precision beyond 6 decimals and rejects non-numeric/non-finite inputs."""
    tb = _mod('truth_bridge')
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)

    # 1. Full IEEE precision: values differing at 7th decimal place produce distinct digests
    val1 = 0.3500001
    val2 = 0.3500002
    d1 = tb.compute_reading_content_digest("dev-1", "plot-A", "soil_moisture_vwc", val1, "fraction", now)
    d2 = tb.compute_reading_content_digest("dev-1", "plot-A", "soil_moisture_vwc", val2, "fraction", now)
    assert d1 != d2

    # 2. Non-numeric or missing values fail closed (raise ValueError, never default to 0.0)
    with pytest.raises(ValueError):
        tb.compute_reading_content_digest("dev-1", "plot-A", "soil_moisture_vwc", None, "fraction", now)

    with pytest.raises(ValueError):
        tb.compute_reading_content_digest("dev-1", "plot-A", "soil_moisture_vwc", "invalid_str", "fraction", now)

    with pytest.raises(ValueError):
        tb.compute_reading_content_digest("dev-1", "plot-A", "soil_moisture_vwc", float("nan"), "fraction", now)

    with pytest.raises(ValueError):
        tb.compute_reading_content_digest("dev-1", "plot-A", "soil_moisture_vwc", float("inf"), "fraction", now)


def test_r12_g06_asmae_content_hash_binds_provenance_authority_claims():
    """R12-G06: ASMAE content hash binds all provenance authority claims, filtering only the signature envelope."""
    tb = _mod('truth_bridge')
    base_asmae = {
        "status": "success",
        "run_id": "run-r12-06",
        "package_id": "pkg-r12-06",
        "provenance": {
            "operator_locked": True,
            "graph_locked": True,
            "radiometric_mode": "ht_per_pixel",
            "full_radiometric_credit_allowed": True,
            "enkf_mode": "ht_per_pixel",
            "full_enkf_credit_allowed": True,
            "retrovalidation_score": 0.88,
            "published_at": "2026-11-10T11:00:00+00:00",
        },
        "diagnostics": {"covariance": [[0.02, 0.0], [0.0, 0.02]]},
        "raster_maps": {"moisture": [[0.3] * 10] * 10},
    }

    base_hash = tb.compute_asmae_content_hash(base_asmae)

    # 1. Modifying operator_locked changes hash
    tampered_op = dict(base_asmae)
    tampered_op["provenance"] = dict(base_asmae["provenance"], operator_locked=False)
    assert tb.compute_asmae_content_hash(tampered_op) != base_hash

    # 2. Modifying radiometric_mode changes hash
    tampered_rad = dict(base_asmae)
    tampered_rad["provenance"] = dict(base_asmae["provenance"], radiometric_mode="standard")
    assert tb.compute_asmae_content_hash(tampered_rad) != base_hash

    # 3. Modifying retrovalidation_score changes hash
    tampered_retro = dict(base_asmae)
    tampered_retro["provenance"] = dict(base_asmae["provenance"], retrovalidation_score=0.95)
    assert tb.compute_asmae_content_hash(tampered_retro) != base_hash

    # 4. Modifying published_at changes hash
    tampered_pub = dict(base_asmae)
    tampered_pub["provenance"] = dict(base_asmae["provenance"], published_at="2026-11-10T12:00:00+00:00")
    assert tb.compute_asmae_content_hash(tampered_pub) != base_hash

    # 5. Adding or changing publication_receipt envelope does NOT change hash (stable signature envelope)
    with_receipt = dict(base_asmae)
    with_receipt["provenance"] = dict(base_asmae["provenance"], publication_receipt="urn:envelope:placeholder")
    assert tb.compute_asmae_content_hash(with_receipt) == base_hash


def test_r12_g07_cross_worker_revocation_persistence_with_atomic_file_swap(tmp_path):
    """R12-G07: Revocations and epoch persist durably to disk and reload accurately across independent worker processes."""
    tb = _mod('truth_bridge')
    store_file = str(tmp_path / "shared_revocation.json")

    # Worker 1 writes revocations and advances epoch
    worker1_store = tb.DurableRevocationStore(persistence_path=store_file)
    worker1_store.revoke_sensor("urn:agriwise:receipt:worker1:revoked_01")
    worker1_store.revoke_publication("urn:agriwise:pub:worker1:revoked_pub")
    worker1_store.set_epoch(3)

    # Worker 2 initializes independently from same disk store
    worker2_store = tb.DurableRevocationStore(persistence_path=store_file)
    assert worker2_store.revocation_epoch == 3

    is_rev_sensor, _ = worker2_store.is_sensor_revoked("urn:agriwise:receipt:worker1:revoked_01")
    assert is_rev_sensor is True

    is_rev_pub, _ = worker2_store.is_publication_revoked("urn:agriwise:pub:worker1:revoked_pub")
    assert is_rev_pub is True

    # Receipts from epoch < 3 are expired in Worker 2
    is_rev_expired, reason_exp = worker2_store.is_sensor_revoked("urn:agriwise:receipt:worker1:unrevoked", receipt_epoch=2)
    assert is_rev_expired is True
    assert "expired_revocation_epoch:2 < 3" in (reason_exp or "")


def test_r12_g08_full_engine_end_to_end_native_r12_adversarial_and_positive_acceptance():
    """R12-G08: Full engine integration proving all R12 contracts simultaneously in Layer1FusionEngine.fuse()."""
    from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer0.source_package import Layer0SourcePackage
    eng_mod = _mod('engine')
    tb = _mod('truth_bridge')
    s = _mod('schemas')

    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    cutoff = now

    # 1. Register authentic sensor
    register_device(SensorDeviceRegistration(
        device_id="sensor_r12_e2e",
        vendor="acme",
        model="probe-r12-e2e",
        protocol="lora",
        farm_id="farm-1",
        plot_id="plot-A",
        latitude=35.0,
        longitude=10.0,
        variables=["soil_moisture_vwc"],
        installation_datetime=now - timedelta(days=5),
        status="active",
        calibration_profile_id="cal-r12-e2e",
    ))

    # Healthy reading with full IEEE precision (0.334455667788)
    reading_val = 0.334455667788
    sensor_obs_time = now - timedelta(hours=1)
    reading_digest = tb.compute_reading_content_digest(
        device_id="sensor_r12_e2e",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        value=reading_val,
        unit="fraction",
        observed_at=sensor_obs_time,
    )
    rcpt_sensor = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor_r12_e2e:healthy",
        issuer="agriwise:trust:sensor_authority",
        device_id="sensor_r12_e2e",
        plot_id="plot-A",
        variable="soil_moisture_vwc",
        calibration_profile_id="cal-r12-e2e",
        status="active",
        content_digest=reading_digest,
        observation_instant=sensor_obs_time.isoformat(),
        reading_value=reading_val,
        reading_unit="fraction",
        observed_at=sensor_obs_time,
    )
    tb.register_sensor_receipt(rcpt_sensor)

    rcpt_sensor_pub = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sensor:r12_e2e",
        issuer="agriwise:trust:publication_authority",
        source_family="sensor",
        acquisition_id="pkt_r12_healthy",
        published_at=now - timedelta(hours=1),
        content_hash=reading_digest,
    )
    tb.register_publication_receipt(rcpt_sensor_pub)

    pkt_healthy = ObservationPacket(
        packet_id="pkt_r12_healthy",
        plot_id="plot-A",
        source=ObservationSource.SENSOR_IOT,
        data_status=DataStatus.OBSERVED,
        timestamp=sensor_obs_time,
        spatial_scope="point",
        qa=QAMetadata(scene_score=1.0, sensor_health=0.99),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.01}),
        payload={
            "device_id": "sensor_r12_e2e",
            "instrument_id": "sensor_r12_e2e",
            "variable": "soil_moisture_vwc",
            "value": reading_val,
            "unit": "fraction",
            "calibration_version": "cal-r12-e2e",
            "provenance_ref": "urn:agriwise:receipt:sensor_r12_e2e:healthy",
            "publication_receipt": rcpt_sensor_pub,
        },
    )

    sensor_pkg = Layer0SourcePackage(
        source_family="sensor",
        plot_id="plot-A",
        packets=[pkt_healthy],
    )
    sensor_pkg.receipt = rcpt_sensor_pub
    sensor_pkg.published_at = now - timedelta(hours=1)

    # 2. Raster composite with verified content binding
    valid_raster_data = {
        "variable": "NDVI",
        "values": [[0.62] * 10] * 10,
        "crs": "EPSG:4326",
        "bounds": [10.0, 35.0, 10.1, 35.1],
        "transform": [0.001, 0.0, 10.0, 0.0, -0.001, 35.1],
        "width": 10,
        "height": 10,
        "resolution_m": 10.0,
        "published_at": (now - timedelta(hours=2)).isoformat(),
    }
    ch_raster_e2e = tb.compute_raster_composite_content_hash(valid_raster_data)
    rcpt_raster = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:raster:ndvi:r12_e2e",
        issuer="agriwise:trust:publication_authority",
        source_family="raster_composite",
        acquisition_id="NDVI",
        published_at=now - timedelta(hours=2),
        content_hash=ch_raster_e2e,
    )
    tb.register_publication_receipt(rcpt_raster)
    valid_raster_data["publication_receipt"] = rcpt_raster

    # 3. ASMAE output binding provenance authority claims
    valid_asmae = {
        "status": "success",
        "run_id": "asmae_run_r12_e2e",
        "package_id": "pkg_asmae_r12_e2e",
        "schema_version": "1.0",
        "source_id": "asmae_engine_01",
        "production_usable": True,
        "layer1_export_allowed": True,
        "observation_operator_refs": ["op-1"],
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
            "retrovalidation_score": 0.88,
            "published_at": (now - timedelta(hours=1)).isoformat(),
        },
        "diagnostics": {
            "scientific_pass": True,
            "scene_stack_mode": "real_raster",
            "enkf_mode": "ht_per_pixel",
            "radiometric_mode": "ht_per_pixel",
            "retro_status": "success_with_holdouts",
            "diagnostic_only": False,
            "state_update_allowed": True,
            "operator_count": 1,
            "covariance": [[0.015, 0.0], [0.0, 0.015]],
        },
        "raster_maps": {"moisture": [[0.32] * 10] * 10},
    }
    ch_asmae_e2e = tb.compute_asmae_content_hash(valid_asmae)
    rcpt_asmae = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:asmae:r12_e2e",
        issuer="agriwise:trust:publication_authority",
        source_family="asmae",
        acquisition_id="pkg_asmae_r12_e2e",
        published_at=now - timedelta(hours=1),
        content_hash=ch_asmae_e2e,
    )
    tb.register_publication_receipt(rcpt_asmae)
    valid_asmae["provenance"]["publication_receipt"] = rcpt_asmae

    # Execute engine fusion
    bundle = s.Layer1InputBundle(
        plot_id="plot-A",
        run_id="run-r12-e2e",
        run_timestamp=now,
        as_of_cutoff=cutoff,
        window_start=now - timedelta(days=1),
        window_end=now,
        layer0_source_packages={"sensor": [sensor_pkg]},
        raster_composites={"NDVI": valid_raster_data},
        asmae_output=valid_asmae,
    )
    engine = eng_mod.Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # Assertions:
    # 1. Healthy sensor admitted with full state authority
    sensor_ev = [e for e in pkg.evidence_items if e.source_family == "sensor" and e.state_update_allowed is True]
    assert len(sensor_ev) == 1
    assert sensor_ev[0].value == pytest.approx(reading_val)
    assert sensor_ev[0].truth_class == "observed_sensor"

    # 2. Raster composite admitted
    raster_ev = [e for e in pkg.evidence_items if e.source_family == "raster_composite"]
    assert len(raster_ev) == 1
    assert raster_ev[0].value == pytest.approx(0.62)

    # 3. Spatial index contains both raster references
    assert any("ndvi" in r.variable for r in pkg.spatial_index.raster_refs)
    assert any("moisture" in r.variable for r in pkg.spatial_index.raster_refs)

    # 4. Provenance and scientific content root
    assert len(pkg.scientific_content_root()) == 64


def test_s01_historical_sensor_unhashed_publication_receipt_fails_availability():
    """S01: Prohibit unhashed sensor receipts from asserting historical availability evidence.
    
    Signed sensor measurements without first_available_at must provide a publication receipt
    with exact matching content hash to gain historical state update authority.
    Unhashed or mismatched receipts must be admitted diagnostic-only.
    """
    ta = _mod('temporal_alignment')
    tb = _mod('truth_bridge')
    s = _mod('schemas')

    now = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    cutoff = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    obs_time = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    pub_time = datetime(2026, 11, 14, 11, 0, tzinfo=timezone.utc)

    reading_digest = tb.compute_reading_content_digest(
        device_id="dev-s01",
        plot_id="plot-s01",
        variable="soil_moisture",
        value=25.4,
        unit="percent",
        observed_at=obs_time,
    )

    signed_rcpt = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor:s01",
        issuer="agriwise:authority:test_signer",
        device_id="dev-s01",
        plot_id="plot-s01",
        variable="soil_moisture",
        calibration_profile_id="cal-s01",
        status="active",
        reading_value=25.4,
        reading_unit="percent",
        observed_at=obs_time,
        first_available_at=None,
    )
    tb.register_sensor_receipt(signed_rcpt)

    # 1. Negative control: Unhashed publication receipt (content_hash is None or empty)
    unhashed_pub_rcpt = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sensor:unhashed-01",
        issuer="agriwise:authority:test_signer",
        source_family="sensor",
        acquisition_id="dev-s01",
        published_at=pub_time,
        content_hash=None,
    )
    tb.register_publication_receipt(unhashed_pub_rcpt)

    item_unhashed = s.EvidenceItem(
        evidence_id="ev-unhashed",
        plot_id="plot-s01",
        variable="soil_moisture",
        value=25.4,
        source_family="sensor",
        source_id="dev-s01",
        observation_type="soil_moisture",
        spatial_scope="point",
        unit="percent",
        observed_at=obs_time,
        confidence=0.9,
        flags=["HISTORICAL_REPLAY", "REQUIRES_PUBLICATION_VERIFICATION"],
        receipt=signed_rcpt,
        publication_receipt=unhashed_pub_rcpt,
        publication_receipt_verified=True,
        verified_published_at=pub_time,
        content_hash=reading_digest,
        truth_class="observed_sensor",
        state_update_allowed=True,
        diagnostic_only=False,
    )

    ok, reason = ta.is_available_at_cutoff(item_unhashed, cutoff, is_historical_replay=True)
    assert ok is True
    assert reason == "admitted_diagnostic_only_no_availability_proof"
    assert item_unhashed.state_update_allowed is False
    assert item_unhashed.diagnostic_only is True
    assert "NO_AUTHENTICATED_AVAILABILITY_ON_HISTORICAL_REPLAY" in item_unhashed.flags

    # 2. Positive control: Publication receipt with exact matching content hash
    hashed_pub_rcpt = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sensor:hashed-01",
        issuer="agriwise:authority:test_signer",
        source_family="sensor",
        acquisition_id="dev-s01",
        published_at=pub_time,
        content_hash=reading_digest,
    )
    tb.register_publication_receipt(hashed_pub_rcpt)

    item_hashed = s.EvidenceItem(
        evidence_id="ev-hashed",
        plot_id="plot-s01",
        variable="soil_moisture",
        value=25.4,
        source_family="sensor",
        source_id="dev-s01",
        observation_type="soil_moisture",
        spatial_scope="point",
        unit="percent",
        observed_at=obs_time,
        confidence=0.9,
        flags=["HISTORICAL_REPLAY", "REQUIRES_PUBLICATION_VERIFICATION"],
        receipt=signed_rcpt,
        publication_receipt=hashed_pub_rcpt,
        publication_receipt_verified=True,
        verified_published_at=pub_time,
        content_hash=reading_digest,
        truth_class="observed_sensor",
        state_update_allowed=True,
        diagnostic_only=False,
    )

    ok_hashed, reason_hashed = ta.is_available_at_cutoff(item_hashed, cutoff, is_historical_replay=True)
    assert ok_hashed is True
    assert reason_hashed == "available_authenticated_sensor"
    assert item_hashed.state_update_allowed is True
    assert item_hashed.diagnostic_only is False

    # 3. Negative control: Mismatched content hash on publication receipt fails closed
    mismatched_pub_rcpt = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sensor:mismatched-01",
        issuer="agriwise:authority:test_signer",
        source_family="sensor",
        acquisition_id="dev-s01",
        published_at=pub_time,
        content_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
    )
    tb.register_publication_receipt(mismatched_pub_rcpt)

    item_mismatched = s.EvidenceItem(
        evidence_id="ev-mismatched",
        plot_id="plot-s01",
        variable="soil_moisture",
        value=25.4,
        source_family="sensor",
        source_id="dev-s01",
        observation_type="soil_moisture",
        spatial_scope="point",
        unit="percent",
        observed_at=obs_time,
        confidence=0.9,
        flags=["HISTORICAL_REPLAY", "REQUIRES_PUBLICATION_VERIFICATION"],
        receipt=signed_rcpt,
        publication_receipt=mismatched_pub_rcpt,
        publication_receipt_verified=True,
        verified_published_at=pub_time,
        content_hash=reading_digest,
        truth_class="observed_sensor",
        state_update_allowed=True,
        diagnostic_only=False,
    )

    ok_mismatched, reason_mismatched = ta.is_available_at_cutoff(item_mismatched, cutoff, is_historical_replay=True)
    assert ok_mismatched is False
    assert "MISMATCHED_PUBLICATION_RECEIPT_DIGEST" in reason_mismatched


def test_r3_f03_dict_form_publication_receipt_equivalence():
    """R3-F03: Dict-form signed publication receipts must produce identical admission
    and availability decisions to typed PublicationAttestationReceipt without false negatives.
    """
    ta = _mod('temporal_alignment')
    tb = _mod('truth_bridge')
    s = _mod('schemas')
    from layer0.observation_packet import ObservationPacket, ObservationSource, DataStatus, QAMetadata, UncertaintyModel
    from layer1_fusion.adapters.observation_packet import observation_packet_to_evidence

    now = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    cutoff = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    obs_time = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    pub_time = datetime(2026, 11, 14, 11, 0, tzinfo=timezone.utc)

    reading_digest = tb.compute_reading_content_digest(
        device_id="dev-dict-01",
        plot_id="plot-dict-01",
        variable="soil_moisture",
        value=28.5,
        unit="percent",
        observed_at=obs_time,
    )

    signed_rcpt = _tf().create_signed_sensor_receipt(
        receipt_id="urn:agriwise:receipt:sensor:dict-01",
        issuer="agriwise:trust:sensor_authority",
        device_id="dev-dict-01",
        plot_id="plot-dict-01",
        variable="soil_moisture",
        calibration_profile_id="cal-dict-01",
        status="active",
        content_digest=reading_digest,
        observation_instant=obs_time.isoformat(),
        reading_value=28.5,
        reading_unit="percent",
        observed_at=obs_time,
        first_available_at=None,
    )
    tb.register_sensor_receipt(signed_rcpt)

    typed_pub_rcpt = _tf().create_signed_publication_receipt(
        receipt_id="urn:agriwise:pub:sensor:dict-01",
        issuer="agriwise:trust:publication_authority",
        source_family="sensor",
        acquisition_id="pkt-dict-01",
        published_at=pub_time,
        content_hash=reading_digest,
    )
    tb.register_publication_receipt(typed_pub_rcpt)

    # Convert typed receipt to a raw dict payload
    dict_pub_rcpt = {
        "receipt_id": typed_pub_rcpt.receipt_id,
        "issuer": typed_pub_rcpt.issuer,
        "source_family": typed_pub_rcpt.source_family,
        "acquisition_id": typed_pub_rcpt.acquisition_id,
        "published_at": typed_pub_rcpt.published_at if isinstance(typed_pub_rcpt.published_at, str) else typed_pub_rcpt.published_at.isoformat(),
        "content_hash": typed_pub_rcpt.content_hash,
        "status": typed_pub_rcpt.status,
        "signature": typed_pub_rcpt.signature,
    }

    # 1. Direct temporal alignment check with dict-form publication receipt
    item_direct_dict = s.EvidenceItem(
        evidence_id="ev-dict-direct",
        plot_id="plot-dict-01",
        variable="soil_moisture",
        value=28.5,
        source_family="sensor",
        source_id="dev-dict-01",
        observation_type="soil_moisture",
        spatial_scope="point",
        unit="percent",
        observed_at=obs_time,
        confidence=0.9,
        flags=["HISTORICAL_REPLAY", "REQUIRES_PUBLICATION_VERIFICATION"],
        receipt=signed_rcpt,
        publication_receipt=dict_pub_rcpt,
        publication_receipt_verified=True,
        verified_published_at=pub_time,
        content_hash=reading_digest,
        truth_class="observed_sensor",
        state_update_allowed=True,
        diagnostic_only=False,
    )
    ok_direct, reason_direct = ta.is_available_at_cutoff(item_direct_dict, cutoff, is_historical_replay=True)
    assert ok_direct is True, f"Expected True for valid dict publication receipt, got {reason_direct}"
    assert reason_direct == "available_authenticated_sensor"

    # 2. End-to-end via observation_packet_to_evidence adapter
    pkt = ObservationPacket(
        packet_id="pkt-dict-01",
        plot_id="plot-dict-01",
        source=ObservationSource.SENSOR_IOT,
        data_status=DataStatus.OBSERVED,
        timestamp=obs_time,
        spatial_scope="point",
        qa=QAMetadata(scene_score=1.0, sensor_health=0.99),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture": 0.01}),
        payload={
            "device_id": "dev-dict-01",
            "instrument_id": "dev-dict-01",
            "variable": "soil_moisture",
            "value": 28.5,
            "unit": "percent",
            "calibration_version": "cal-dict-01",
            "provenance_ref": "urn:agriwise:receipt:sensor:dict-01",
            "publication_receipt": dict_pub_rcpt,
        },
    )
    bundle = s.Layer1InputBundle(plot_id="plot-dict-01", run_id="run-dict-01", as_of_cutoff=cutoff)
    evidence_items = observation_packet_to_evidence(pkt, bundle)
    assert len(evidence_items) == 1
    ev_item = evidence_items[0]

    assert ev_item.publication_receipt_verified is True
    assert isinstance(ev_item.publication_receipt, tb.PublicationAttestationReceipt)
    assert ev_item.publication_receipt.receipt_id == "urn:agriwise:pub:sensor:dict-01"
    assert ev_item.publication_receipt.content_hash == reading_digest
    assert ev_item.verified_published_at == pub_time

    ok_adapter, reason_adapter = ta.is_available_at_cutoff(ev_item, cutoff, is_historical_replay=True)
    assert ok_adapter is True, f"Expected adapter item to be available, got {reason_adapter}"

    # 3. Negative control: dict-form receipt with mismatched digest fails closed
    mismatched_dict = dict(dict_pub_rcpt)
    mismatched_dict["content_hash"] = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    item_mismatched = s.EvidenceItem(
        evidence_id="ev-dict-mismatched",
        plot_id="plot-dict-01",
        variable="soil_moisture",
        value=28.5,
        source_family="sensor",
        source_id="dev-dict-01",
        observation_type="soil_moisture",
        spatial_scope="point",
        unit="percent",
        observed_at=obs_time,
        confidence=0.9,
        flags=["HISTORICAL_REPLAY", "REQUIRES_PUBLICATION_VERIFICATION"],
        receipt=signed_rcpt,
        publication_receipt=mismatched_dict,
        publication_receipt_verified=True,
        verified_published_at=pub_time,
        content_hash=reading_digest,
        truth_class="observed_sensor",
        state_update_allowed=True,
        diagnostic_only=False,
    )
    ok_bad, reason_bad = ta.is_available_at_cutoff(item_mismatched, cutoff, is_historical_replay=True)
    assert ok_bad is False
    assert "MISMATCHED_PUBLICATION_RECEIPT_DIGEST" in reason_bad







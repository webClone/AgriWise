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

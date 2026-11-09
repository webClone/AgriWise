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

def test_i_unattested_sensor_strings_are_not_authentic_proof():
    e = _item(provenance_ref='user-supplied-string', source_id='sensor1',
              instrument_id=None, calibration_version=None)
    _mod('truth_bridge').normalize_evidence_truth(e)
    assert e.state_update_allowed is False

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

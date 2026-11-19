"""IR-04 Batch A contract tests A01-A12 (NOT end-to-end integration evidence)."""

import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "resolution" / "state_cell_support.py"
spec = importlib.util.spec_from_file_location("asmae_state_cell_support", MODULE)
m = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = m
spec.loader.exec_module(m)

H = lambda ch: ch * 64
T = "2026-09-08T12:00:00+00:00"
K1 = "2026-09-09T12:00:00+00:00"
K2 = "2026-11-18T12:00:00+00:00"
G = m.GridSpec(crs="EPSG:32631", transform=(500000., 10., 0., 4100000., 0., -10.), width=3, height=1)
G_FINE = m.GridSpec(crs="EPSG:32631", transform=(500000., 1., 0., 4100000., 0., -1.), width=30, height=10)
G_2M = m.GridSpec(crs="EPSG:32631", transform=(500000., 2., 0., 4100000., 0., -2.), width=15, height=5)


def ev(*, state=("vigor",), res=10., bbox=None, source="a", valid=T, committed=K1,
       psf=None, calibration=True, holdout=False, nodata=False, classification="physical", crs="EPSG:32631"):
    return m.EvidenceFootprint(observation_id=source, source_sha256=H("a"), operator_sha256=H("b"),
        tenant_id="tenant", farm_id="farm", plot_id="plot", geometry_sha256=H("c"),
        observation_valid_time=valid, committed_at=committed, supported_states=state,
        bbox=bbox or (500000., 4099990., 500010., 4100000.), crs=crs,
        native_resolution_m=res, psf_fwhm_m=psf if psf is not None else res,
        observability=0.95, calibrated_operator_sha256=H("d") if calibration else None,
        independent_holdout_sha256=H("e") if holdout else None,
        classification=classification, nodata=nodata)


def run(state="vigor", col=0, evidence=None, k=K1, val=0.6, propagated=(), grid=G, **kw):
    return m.evaluate_state_cell_support(state=state, row=0, col=col, grid=grid,
        tenant_id="tenant", farm_id="farm", plot_id="plot", geometry_sha256=H("c"),
        valid_time=T, knowledge_cutoff=k, estimated_value=val, sigma=0.15,
        evidences=evidence or [], propagation_source_hashes=propagated, **kw)


def test_a01_global_approval_and_retro_cannot_certify_10m_as_1m():
    record = run(evidence=[ev()], scene_wide_1m_approval=True, retrovalidation_score=1, bma_agreement=1,
                 display_resolution_m=1)
    assert record.effective_resolution_m == 10 and not record.certified_1m


def test_a02_local_1m_evidence_never_certifies_neighbor_or_other_state():
    source = ev(res=1, psf=1, state=("vigor",))
    left = run(evidence=[source], grid=G_FINE); right = run(col=11, evidence=[source], grid=G_FINE)
    soil = run(state="root_zone_water", evidence=[source], grid=G_FINE)
    assert left.effective_resolution_m == 1 and left.certified_1m is False
    assert right.effective_resolution_m is None and soil.effective_resolution_m is None


def test_a03_statewise_support_differs_at_same_cell():
    ss = [ev(), ev(state=("surface_wetness_event",), res=20., psf=20., source="sar")]
    vigor = run(evidence=ss)
    wet = run(state="surface_wetness_event", evidence=ss)
    rootzone = run(state="root_zone_water", evidence=ss)
    assert (vigor.effective_resolution_m, wet.effective_resolution_m, rootzone.effective_resolution_m) == (10,20,None)


def test_a04_bad_crs_nodata_and_partial_footprint_fail_local_support():
    for source in [ev(crs="EPSG:4326"), ev(nodata=True), ev(bbox=(500000,4099990,500005,4100000))]:
        assert run(evidence=[source]).effective_resolution_m is None
    with pytest.raises(m.SpatialSupportViolation):
        m.GridSpec("EPSG:32631", (0.,10.,1.,0.,0.,-10.), 1,1)


def test_a05_display_interpolation_never_upgrades_scientific_resolution():
    record = run(evidence=[ev()])
    overlay = m.describe_display_resampling(record, 1)
    assert overlay["is_resampled_display"] and overlay["source_effective_resolution_m"] == 10
    assert record.effective_resolution_m == 10


def test_a06_high_retro_bma_and_holdout_digest_cannot_certify_fine_detail():
    record = run(evidence=[ev(holdout=True)], retrovalidation_score=1, bma_agreement=1,
                 scene_wide_1m_approval=True)
    assert not record.certified_1m and record.effective_resolution_m == 10


def test_a07_late_backfill_alters_k2_not_k1():
    source = ev(res=2, psf=2, committed=K2)
    at_k1 = run(evidence=[source], k=K1, grid=G_2M)
    at_k2 = run(evidence=[source], k=K2, grid=G_2M)
    assert at_k1.effective_resolution_m is None
    assert at_k2.effective_resolution_m == 2
    assert run(evidence=[source], k=K1, grid=G_2M).digest() == at_k1.digest()


def test_a08_uncalibrated_mesia_style_descriptor_remains_diagnostic():
    source = ev(res=.5, psf=.5, calibration=False, source="mesia")
    record = run(evidence=[source])
    assert record.effective_resolution_m is None
    assert "uncalibrated_observation_operator" in record.demotion_reasons


def test_a09_all_13_states_addressable_without_fake_rasters():
    t = m.statewise_support_tensor([run(state="vigor", evidence=[ev()]), run(state="root_zone_water")])
    assert tuple(t) == m.STATE_NAMES and len(t) == 13
    assert t["vigor"]["0:0"]["estimate_kind"] == "posterior"
    assert t["root_zone_water"]["0:0"]["estimate_kind"] == "prior_only"
    assert t["chlorophyll"] == {}


def test_a10_cross_tenant_evidence_fails_closed_and_synthetic_excluded():
    source = ev()
    from dataclasses import replace
    with pytest.raises(m.SpatialSupportViolation):
        run(evidence=[replace(source, tenant_id="attacker")])
    assert run(evidence=[ev(classification="synthetic")]).effective_resolution_m is None


def test_a11_immutable_digest_binds_value_uncertainty_cutoff_and_resolution():
    record = run(evidence=[ev()])
    from dataclasses import replace
    assert run(evidence=[ev()]).digest() == record.digest()
    assert replace(record, estimated_value=.8).digest() != record.digest()
    assert replace(record, knowledge_cutoff=K2).digest() != record.digest()
    assert replace(record, effective_resolution_m=2).digest() != record.digest()


def test_a12_coupling_can_change_neighbor_estimate_without_local_evidence_claim():
    record = run(col=1, propagated=[H("f")], val=.7, evidence=[ev()])
    assert record.estimated_value == .7
    assert record.spatial_support == "modeled_coupling"
    assert record.effective_resolution_m is None
    assert record.propagated_source_hashes == (H("f"),)


def test_adversarial_future_observation_is_not_valid_historical_evidence():
    e = ev(valid="2026-10-01T00:00:00+00:00", committed=K1)
    assert run(evidence=[e]).effective_resolution_m is None


def test_adversarial_bad_dates_and_geometry_do_not_pass():
    with pytest.raises(m.SpatialSupportViolation):
        run(evidence=[ev()], k="2026-09-09T12:00:00")
    with pytest.raises(m.SpatialSupportViolation):
        ev(bbox=(500000,4099990,500000,4100000))


def test_adversarial_duplicate_state_cell_support_rejected():
    r=run()
    with pytest.raises(m.SpatialSupportViolation):
        m.statewise_support_tensor([r,r])


def test_adversarial_fine_sensor_on_coarse_model_grid_cannot_upgrade_output_resolution():
    rec = run(evidence=[ev(res=1., psf=1.)], grid=G)
    assert rec.effective_resolution_m == 10
    assert "fine_evidence_requires_finer_scientific_state_grid" in rec.demotion_reasons


def test_adversarial_direct_constructor_cannot_inject_certification():
    from dataclasses import replace
    with pytest.raises(m.SpatialSupportViolation):
        replace(run(evidence=[ev()]), certified_1m=True)


def test_adversarial_psf_larger_than_native_pixel_limits_effective_resolution():
    source = ev(res=1, psf=5)
    record = run(evidence=[source], grid=G_FINE)
    assert record.effective_resolution_m == 5
    assert record.certified_1m is False

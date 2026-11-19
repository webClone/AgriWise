"""Bounded engine bridge qualification; this is not full ASMAE integration QA."""
from datetime import datetime, timezone
from hashlib import sha256

from services.agribrain.layer05_asmae.resolution.statewise_engine_bridge import build_statewise_engine_support
from services.agribrain.layer05_asmae.resolution.state_cell_support import EvidenceFootprint, STATE_NAMES

S = 'a' * 64
BASE = dict(grid_spec={'crs': 'EPSG:32631', 'transform': (0., 10., 0., 20., 0., -10.),
                       'width': 2, 'height': 2},
            tenant_id='tenant', farm_id='farm', plot_id='plot', geometry_sha256=S,
            valid_time='2026-11-18T00:00:00+00:00', knowledge_cutoff='2026-11-19T00:00:00+00:00')


def test_b01_no_evidence_gives_no_fine_claims():
    r = build_statewise_engine_support(**BASE, raster_maps={'vigor': [[.1,.2],[.3,.4]]}, uncertainty_maps={})
    assert r['certified_1m'] is False
    assert set(r['effective_resolution_m_by_state']) == set(STATE_NAMES)
    assert r['effective_resolution_m_by_state']['vigor'] == [[None, None], [None, None]]
    assert r['spatial_support_class_by_state']['root_zone_water'][0][0] == 'none'


def test_b02_grid_mismatch_is_not_reinterpreted_as_science():
    r = build_statewise_engine_support(**BASE, raster_maps={'vigor': [[.1]*8]*8}, uncertainty_maps={})
    assert r['status'] == 'unavailable'
    assert r['reason'] == 'display_resampling_or_grid_shape_mismatch'


def test_b03_missing_knowledge_cutoff_blocks_support():
    kwargs = dict(BASE); kwargs['knowledge_cutoff'] = ''
    r = build_statewise_engine_support(**kwargs, raster_maps={}, uncertainty_maps={})
    assert r['status'] == 'unavailable'


def test_b04_local_support_separates_states_and_cells():
    e = EvidenceFootprint(observation_id='qualified-input', source_sha256='b'*64,
          operator_sha256='c'*64, tenant_id='tenant', farm_id='farm', plot_id='plot',
          geometry_sha256=S, observation_valid_time='2026-11-18T00:00:00+00:00',
          committed_at='2026-11-18T10:00:00+00:00', supported_states=('vigor',),
          bbox=(0.,10.,10.,20.), crs='EPSG:32631', native_resolution_m=5.,
          psf_fwhm_m=4., observability=.95, calibrated_operator_sha256='d'*64)
    r = build_statewise_engine_support(**BASE, raster_maps={'vigor': [[.1,.2],[.3,.4]],
           'root_zone_water': [[.2,.2],[.2,.2]]}, uncertainty_maps={}, qualified_footprints=[e])
    assert r['effective_resolution_m_by_state']['vigor'][0][0] == 10.
    assert r['effective_resolution_m_by_state']['vigor'][0][1] is None
    assert r['effective_resolution_m_by_state']['root_zone_water'][0][0] is None
    assert not r['certified_1m']


def test_b05_unqualified_future_source_is_ignored():
    e = EvidenceFootprint(observation_id='future', source_sha256='b'*64,
          operator_sha256='c'*64, tenant_id='tenant', farm_id='farm', plot_id='plot',
          geometry_sha256=S, observation_valid_time='2026-11-20T00:00:00+00:00',
          committed_at='2026-11-20T10:00:00+00:00', supported_states=('vigor',),
          bbox=(0.,10.,10.,20.), crs='EPSG:32631', native_resolution_m=1.,
          psf_fwhm_m=1., observability=.99, calibrated_operator_sha256='d'*64)
    r = build_statewise_engine_support(**BASE, raster_maps={'vigor': [[.1,.2],[.3,.4]]},
           uncertainty_maps={}, qualified_footprints=[e])
    assert r['effective_resolution_m_by_state']['vigor'][0][0] is None


def test_b06_deterministic_support_digest():
    kwargs = dict(BASE, raster_maps={'vigor': [[.1,.2],[.3,.4]]}, uncertainty_maps={})
    assert build_statewise_engine_support(**kwargs)['support_records_sha256'] == build_statewise_engine_support(**kwargs)['support_records_sha256']


def test_b07_malformed_geometry_digest_fails_closed():
    kw = dict(BASE); kw['geometry_sha256'] = 'legacy-short'
    result = build_statewise_engine_support(**kw, raster_maps={'vigor': [[.1,.2],[.3,.4]]}, uncertainty_maps={})
    assert result['status'] == 'unavailable'
    assert result['reason'] == 'unqualified_geometry_digest'


def test_b08_invalid_knowledge_cutoff_fails_closed():
    kw = dict(BASE); kw['knowledge_cutoff'] = '2026-11-19T12:00:00'
    result = build_statewise_engine_support(**kw, raster_maps={'vigor': [[.1,.2],[.3,.4]]}, uncertainty_maps={})
    assert result['status'] == 'unavailable'
    assert result['reason'] == 'invalid_bitemporal_boundary'


def test_b09_native_scientific_support_ignores_resampled_display_arrays():
    """The engine must pass original scientific grids, not quick-visual overlays."""
    native_values = {'vigor': [[0.1, 0.2], [0.3, 0.4]]}
    native_sigmas = {'vigor': [[0.02, 0.03], [0.04, 0.05]]}
    original = build_statewise_engine_support(
        **BASE, raster_maps=native_values, uncertainty_maps=native_sigmas)
    assert original['status'] == 'exploratory_statewise_metadata'
    assert original['effective_resolution_m_by_state']['vigor'] == [[None] * 2 for _ in range(2)]
    # A display-only interpolation can expand 2x2 to 8x8 independently.
    display_values = {'vigor': [[0.2] * 8 for _ in range(8)]}
    assert build_statewise_engine_support(
        **BASE, raster_maps=display_values, uncertainty_maps=native_sigmas
    )['reason'] == 'display_resampling_or_grid_shape_mismatch'
    assert build_statewise_engine_support(
        **BASE, raster_maps=native_values, uncertainty_maps=native_sigmas
    )['support_records_sha256'] == original['support_records_sha256']


def test_b10_oversize_grid_is_an_explicit_capacity_gap_not_fine_scientific_proof():
    kw = dict(BASE)
    kw['grid_spec'] = dict(BASE['grid_spec'], width=65, height=65)
    result = build_statewise_engine_support(
        **kw, raster_maps={}, uncertainty_maps={})
    assert result['status'] == 'unavailable'
    assert result['reason'] == 'missing_or_oversize_scientific_grid'

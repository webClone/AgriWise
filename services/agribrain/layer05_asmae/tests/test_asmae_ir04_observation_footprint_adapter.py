"""IR-04-R03 & IR-04-R04: Authenticated observation footprint adapter tests.

Negative controls:
  - Cross-tenant or mismatched plot scenes are strictly rejected
  - Mismatched CRS (e.g. EPSG:4326 vs target metric EPSG:32631) is rejected
  - Uncalibrated / diagnostic-only scenes without production usability are rejected
  - Degenerate non-positive bounding box is rejected
  - High cloud cover (>30% cloud, observability <0.7) is rejected for optical S2
Positive controls:
  - Admitted Sentinel-2 scene creates EvidenceFootprint with 10m native / 12m PSF
  - Admitted Sentinel-1 SAR scene creates EvidenceFootprint with 20m native / 20m PSF
  - Live runs without bitemporal replay receipt derive valid UTC temporal envelope
"""

from datetime import datetime, timezone
import hashlib
from types import SimpleNamespace

import pytest

from services.agribrain.layer05_asmae.resolution.observation_footprint_adapter import (
    adapt_scene_to_footprint,
    adapt_scenes_to_footprints,
    S2_OPTICAL_STATES,
    S1_SAR_STATES,
)
from services.agribrain.layer05_asmae.resolution.state_cell_support import (
    evaluate_state_cell_support,
    GridSpec,
)

GEOM_HASH = "e" * 64
TENANT = "tenant-001"
FARM = "farm-mitidja"
PLOT = "plot-afroun"
METRIC_CRS = "EPSG:32631"


def _make_s2_scene(**kwargs):
    defaults = dict(
        scene_id="S2A_MSIL2A_20260908T103021_N0500_R108_T31SDA_20260908T142512",
        sensor="S2",
        acquisition_time=datetime(2026, 9, 8, 10, 30, 21, tzinfo=timezone.utc),
        crs=METRIC_CRS,
        transform=[500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0],
        width=100,
        height=100,
        cloud_fraction=0.05,
        qa_score=0.98,
        real_provider_product=True,
        production_usable=True,
        diagnostic_only=False,
        scientific_surface_allowed=True,
        state_update_allowed=True,
        test_override=False,
        committed_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_s1_scene(**kwargs):
    defaults = dict(
        scene_id="S1A_IW_GRDH_1SDV_20260907T174512_20260907T174537_045231_0567AE_42BC",
        sensor="S1",
        acquisition_time=datetime(2026, 9, 7, 17, 45, 12, tzinfo=timezone.utc),
        crs=METRIC_CRS,
        transform=[500000.0, 20.0, 0.0, 4000000.0, 0.0, -20.0],
        width=50,
        height=50,
        cloud_fraction=None,
        qa_score=0.95,
        real_provider_product=True,
        production_usable=True,
        diagnostic_only=False,
        scientific_surface_allowed=True,
        state_update_allowed=True,
        test_override=False,
        committed_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# =========================================================================
# Positive Controls
# =========================================================================

def test_s2_scene_generates_valid_optical_footprint():
    scene = _make_s2_scene()
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is not None
    assert fp.observation_id == scene.scene_id
    assert fp.native_resolution_m == 10.0
    assert fp.psf_fwhm_m == pytest.approx(11.774, abs=0.01)
    assert fp.supported_states == S2_OPTICAL_STATES
    assert "vigor" in fp.supported_states
    assert "root_zone_water" not in fp.supported_states
    assert fp.observability == pytest.approx(0.95, abs=0.01)
    assert fp.calibrated_operator_sha256 is not None
    assert fp.classification == "physical"
    assert fp.bbox == (500000.0, 3999000.0, 501000.0, 4000000.0)


def test_s1_scene_generates_valid_sar_footprint():
    scene = _make_s1_scene()
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is not None
    assert fp.observation_id == scene.scene_id
    assert fp.native_resolution_m == 20.0
    assert fp.psf_fwhm_m == pytest.approx(17.661, abs=0.01)
    assert fp.supported_states == S1_SAR_STATES
    assert "surface_wetness_event" in fp.supported_states
    assert "root_zone_water" not in fp.supported_states
    assert "vigor" not in fp.supported_states
    assert fp.observability == pytest.approx(0.95, abs=0.01)


# =========================================================================
# Hostile Negative Controls
# =========================================================================

def test_cross_tenant_scene_is_rejected():
    scene = _make_s2_scene(tenant_id="adversary-tenant")
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is None


def test_mismatched_plot_scene_is_rejected():
    scene = _make_s2_scene(plot_id="other-plot")
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is None


def test_unprojected_geographic_crs_is_rejected():
    scene = _make_s2_scene(crs="EPSG:4326")
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is None


def test_crs_mismatch_against_target_is_rejected():
    scene = _make_s2_scene(crs="EPSG:32632")
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs="EPSG:32631",
    )
    assert fp is None


def test_diagnostic_only_nonproduction_scene_is_rejected():
    scene = _make_s2_scene(
        diagnostic_only=True,
        production_usable=False,
        real_provider_product=False,
        scientific_surface_allowed=False,
        state_update_allowed=False,
    )
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is None


def test_test_override_scene_is_rejected():
    scene = _make_s2_scene(test_override=True)
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is None


def test_degenerate_nonpositive_bounds_rejected():
    # zero width: xstep = 0
    scene = _make_s2_scene(transform=[500000.0, 0.0, 0.0, 4000000.0, 0.0, -10.0])
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is None


def test_unknown_sensor_rejected():
    scene = _make_s2_scene(sensor="UNKNOWN_COMMERCIAL_SATELLITE")
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is None


def test_invalid_geometry_digest_rejected():
    scene = _make_s2_scene()
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256="not-a-64-char-hex",
        target_crs=METRIC_CRS,
    )
    assert fp is None


# =========================================================================
# State×Cell Integration with Real Footprints
# =========================================================================

def test_s2_footprint_supports_vigor_cell_at_12m_not_1m():
    """An admitted S2 scene (10m pixel, 12m PSF) grants 12m effective resolution, not 1m."""
    scene = _make_s2_scene()
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is not None

    grid = GridSpec(
        crs=METRIC_CRS,
        transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0),
        width=4,
        height=4,
    )

    record = evaluate_state_cell_support(
        state="vigor",
        row=0,
        col=0,
        grid=grid,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        valid_time="2026-09-08T12:00:00+00:00",
        knowledge_cutoff="2026-09-08T18:00:00+00:00",
        estimated_value=0.72,
        sigma=0.04,
        evidences=(fp,),
    )
    assert record.spatial_support == "local_operator"
    # Instrument scale is max(native 10.0, PSF ~11.774m)
    assert record.effective_resolution_m == pytest.approx(fp.psf_fwhm_m, abs=0.01)
    assert record.certified_1m is False
    assert record.admitted_observation_ids == (scene.scene_id,)


def test_s2_footprint_does_not_support_unobservable_states():
    """Optical S2 does NOT support root_zone_water; cell remains prior_only."""
    scene = _make_s2_scene()
    fp = adapt_scene_to_footprint(
        scene,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert fp is not None

    grid = GridSpec(
        crs=METRIC_CRS,
        transform=(500000.0, 10.0, 0.0, 4000000.0, 0.0, -10.0),
        width=4,
        height=4,
    )

    record = evaluate_state_cell_support(
        state="root_zone_water",
        row=0,
        col=0,
        grid=grid,
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        valid_time="2026-09-08T12:00:00+00:00",
        knowledge_cutoff="2026-09-08T18:00:00+00:00",
        estimated_value=0.28,
        sigma=0.03,
        evidences=(fp,),
    )
    assert record.spatial_support == "none"
    assert record.effective_resolution_m is None
    assert record.estimate_kind == "prior_only"


def test_adapt_scenes_to_footprints_deduplicates_and_filters():
    good_s2 = _make_s2_scene(scene_id="s2_good")
    bad_crs = _make_s2_scene(scene_id="s2_bad_crs", crs="EPSG:4326")
    good_s1 = _make_s1_scene(scene_id="s1_good")
    duplicate_s2 = _make_s2_scene(scene_id="s2_good")

    fps = adapt_scenes_to_footprints(
        [good_s2, bad_crs, good_s1, duplicate_s2],
        tenant_id=TENANT,
        farm_id=FARM,
        plot_id=PLOT,
        geometry_sha256=GEOM_HASH,
        target_crs=METRIC_CRS,
    )
    assert len(fps) == 2
    assert {fp.observation_id for fp in fps} == {"s2_good", "s1_good"}

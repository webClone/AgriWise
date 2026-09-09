from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from services.agribrain.layer2_veg_int.crop_observations import (
    CROP_OBSERVATION_CONTRACT_VERSION,
    build_canonical_crop_observations,
    build_crop_evidence_ledger,
    build_sentinel2_crop_observation,
    deduplicate_physical_acquisitions,
    sentinel2_physical_identity,
)
from services.agribrain.scientific_contracts.crop_model_input import (
    observation_tokens_from_ledger,
)


PRODUCT_A = "S2B_MSIL2A_20260806T102559_N0512_R108_T31SDA_20260806T142406.SAFE"
PRODUCT_A_REPROCESSED = "S2B_MSIL2A_20260806T102559_N0512_R108_T31SDA_20260806T145601.SAFE"
PRODUCT_B = "S2B_MSIL2A_20260811T102559_N0512_R108_T31SDA_20260811T142406.SAFE"
FULL_PLOT_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [3, 0], [3, 3], [0, 3], [0, 0]]],
}
NAMESPACE = {"tenant_id": "tenant-a", "farm_id": "farm-a", "plot_id": "plot-a"}


def _package(
    product_id: str = PRODUCT_A,
    *,
    scl: int | np.ndarray = 4,
    content_hash: str = "content-a",
) -> SimpleNamespace:
    shape = (3, 3)
    scl_array = (
        np.full(shape, scl, dtype=np.uint8)
        if isinstance(scl, int) else np.asarray(scl, dtype=np.uint8)
    )
    arrays = {
        "B02": np.full(shape, 0.05),
        "B03": np.full(shape, 0.08),
        "B04": np.full(shape, 0.10),
        "B05": np.full(shape, 0.15),
        "B06": np.full(shape, 0.18),
        "B07": np.full(shape, 0.20),
        "B08": np.full(shape, 0.20),
        "B8A": np.full(shape, 0.22),
        "B11": np.full(shape, 0.12),
        "B12": np.full(shape, 0.09),
        "SCL": scl_array,
        "DATAMASK": np.ones(shape, dtype=np.uint8),
    }
    band_units = {
        key: "reflectance" for key in arrays if key.startswith("B")
    }
    band_units.update({"SCL": "classification", "DATAMASK": "binary_mask"})
    metadata = SimpleNamespace(
        scene_id="scene-a",
        acquisition_datetime="2026-08-06T10:40:52+00:00",
        plot_geometry_hash="geom-a",
        provider_product_id=product_id,
        catalog_item_id=product_id,
        content_hash=content_hash,
        source_reality="real_raster",
        production_usable=True,
        real_provider_product=True,
        diagnostic_only=False,
        crs="EPSG:4326",
        transform=(0.0, 1.0, 0.0, 3.0, 0.0, -1.0),
        width=3,
        height=3,
        band_units=band_units,
        plot_geometry=FULL_PLOT_GEOMETRY,
        plot_geometry_crs="EPSG:4326",
        tenant_id="tenant-a",
        farm_id="farm-a",
        plot_id="plot-a",
    )
    return SimpleNamespace(
        metadata=metadata,
        band_arrays=arrays,
        local_cache_refs={},
        mask_refs={},
        band_units=band_units,
        source_reality="real_raster",
        production_usable=True,
        real_provider_product=True,
        diagnostic_only=False,
        packets=[],
    )


def test_real_sentinel_arrays_become_rich_admitted_crop_observation() -> None:
    observation = build_sentinel2_crop_observation(
        _package(),
        geometry_hash="geom-a",
        season_start="2026-08-01",
        weather_records=[
            {"date": "2026-08-01", "temp_mean": 20.0},
            {"date": "2026-08-02", "temp_mean": 21.0},
        ],
    )

    assert observation is not None
    assert observation["contract_version"] == CROP_OBSERVATION_CONTRACT_VERSION
    assert observation["record_type"] == "CanonicalCropObservationV2"
    assert observation["plot_namespace"] == {
        "tenant_id": "tenant-a", "farm_id": "farm-a", "plot_id": "plot-a",
    }
    assert observation["observation_hash"].startswith("CROPOBSV2-")
    assert observation["quality_admitted"] is True
    assert observation["quality_class"] == "good"
    assert observation["valid_pixel_count"] == 9
    assert observation["valid_fraction"] == 1.0
    assert observation["day_of_year"] == 218
    assert observation["gdd_accumulated"] == 21.0
    assert observation["gdd_basis"] == "season_start_weather_gdd_base_10c"
    assert observation["primary_gdd_basis"] == "GDD10"
    assert observation["gdd_coordinates"] == {
        "GDD0": 41.0,
        "GDD5": 31.0,
        "GDD10": 21.0,
        "GDD12": 17.0,
    }
    ledger = build_crop_evidence_ledger(
        [observation], plot_namespace=NAMESPACE,
    )
    [token] = observation_tokens_from_ledger(ledger)
    assert token.primary_gdd_basis == "GDD10"
    assert dict(token.gdd_coordinates) == observation["gdd_coordinates"]
    assert observation["ndvi_mean"] == pytest.approx(1 / 3, abs=1e-6)
    assert observation["evi_mean"] == pytest.approx(0.175439, abs=1e-6)
    assert observation["ndre_mean"] == pytest.approx(0.189189, abs=1e-6)
    assert observation["cired_mean"] == pytest.approx(0.466667, abs=1e-6)
    assert observation["ndmi_mean"] == pytest.approx(0.25, abs=1e-6)
    assert observation["lswi_mean"] == observation["ndmi_mean"]
    assert observation["psri_mean"] == pytest.approx(0.277778, abs=1e-6)
    assert observation["red_edge_slope_1_mean"] == pytest.approx(0.00125)
    assert observation["band_statistics"]["B08"]["median"] == 0.20
    assert observation["spatial_distribution"]["ndvi_within_field_variance"] == 0.0
    assert observation["physical_identity_complete"] is True
    assert observation["physical_acquisition_key"].startswith("S2ACQ-")
    assert observation["reflectance_units_verified"] is True
    assert observation["reflectance_scale_by_band"]["B08"] == 1.0
    assert observation["pixel_support_contract"]["immutable"] is True
    assert observation["pixel_support_contract"]["support_definition"] == (
        "plot_geometry&DATAMASK&SCL_4_5&finite_B04_B08"
    )


def test_missing_provider_content_hash_uses_full_array_content() -> None:
    first_package = _package(content_hash="")
    second_package = _package(content_hash="")
    second_package.band_arrays["B02"] = np.array(
        second_package.band_arrays["B02"], copy=True,
    )
    second_package.band_arrays["B02"][1, 1] = 0.051

    first = build_sentinel2_crop_observation(
        first_package, geometry_hash="geom-a",
    )
    second = build_sentinel2_crop_observation(
        second_package, geometry_hash="geom-a",
    )

    assert first is not None and second is not None
    assert first["content_hash"].startswith("S2CONTENT-")
    assert first["content_hash"] != second["content_hash"]
    assert first["physical_acquisition_key"] == second["physical_acquisition_key"]


def test_cloud_pixels_and_field_geometry_share_one_admission_support() -> None:
    scl = np.array([
        [4, 4, 9],
        [4, 4, 9],
        [4, 4, 9],
    ])
    polygon = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 0], [2, 3], [0, 3], [0, 0]]],
    }
    observation = build_sentinel2_crop_observation(
        _package(scl=scl), plot_geometry=polygon, geometry_hash="geom-a",
    )

    assert observation is not None
    assert observation["plot_mask_basis"] == "plot_polygon_gdal_affine"
    assert observation["field_pixel_count"] == 6
    assert observation["valid_pixel_count"] == 6
    assert observation["valid_fraction"] == 1.0
    assert observation["cloud_fraction"] == 0.0
    assert observation["quality_admitted"] is True


def test_all_cloud_scene_is_rejected_even_with_finite_reflectance() -> None:
    observation = build_sentinel2_crop_observation(
        _package(scl=9), geometry_hash="geom-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is False
    assert observation["usable"] is False
    assert observation["valid_pixel_count"] == 0
    assert "cloud_dominated" in observation["quality_rejection_reasons"]
    assert "low_valid_fraction" in observation["quality_rejection_reasons"]


def test_datamask_and_nonfinite_core_bands_are_excluded_from_same_support() -> None:
    package = _package()
    package.band_arrays["DATAMASK"][0, 0] = 0
    package.band_arrays["B08"][0, 1] = np.nan

    observation = build_sentinel2_crop_observation(
        package, geometry_hash="geom-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is True
    assert observation["field_pixel_count"] == 9
    assert observation["valid_pixel_count"] == 7
    assert observation["ndvi_valid_count"] == 7
    assert observation["nodata_fraction"] == pytest.approx(1 / 9, abs=1e-6)
    assert np.isfinite(observation["ndvi_mean"])


def test_each_optional_band_and_index_applies_its_own_finite_support() -> None:
    package = _package()
    package.band_arrays["B11"][0, 0] = np.nan

    observation = build_sentinel2_crop_observation(
        package, geometry_hash="geom-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is True
    assert observation["valid_pixel_count"] == 9
    assert observation["ndvi_valid_count"] == 9
    assert observation["b11_valid_count"] == 8
    assert observation["ndmi_valid_count"] == 8
    assert np.isfinite(observation["ndmi_mean"])
    base_hash = observation["pixel_support_contract"]["support_hash"]
    b11_hash = observation["feature_support_contracts"]["bands"]["B11"]["support_hash"]
    ndmi_hash = observation["feature_support_contracts"]["indices"]["ndmi"]["support_hash"]
    assert b11_hash == ndmi_hash
    assert b11_hash != base_hash
    ndmi_contributions = [
        item for item in observation["feature_contributions"]
        if item["feature_name"] == "ndmi"
    ]
    assert ndmi_contributions
    assert {item["support_hash"] for item in ndmi_contributions} == {ndmi_hash}


def test_missing_or_misaligned_datamask_fails_closed() -> None:
    missing = _package()
    missing.band_arrays.pop("DATAMASK")
    misaligned = _package()
    misaligned.band_arrays["DATAMASK"] = np.ones((2, 2), dtype=np.uint8)

    missing_observation = build_sentinel2_crop_observation(
        missing, geometry_hash="geom-a",
    )
    misaligned_observation = build_sentinel2_crop_observation(
        misaligned, geometry_hash="geom-a",
    )

    assert missing_observation is not None
    assert missing_observation["quality_admitted"] is False
    assert "missing_mask:DATAMASK" in missing_observation["quality_rejection_reasons"]
    assert missing_observation["valid_pixel_count"] == 0
    assert misaligned_observation is not None
    assert misaligned_observation["quality_admitted"] is False
    assert "misaligned_mask:DATAMASK" in misaligned_observation["quality_rejection_reasons"]
    assert misaligned_observation["valid_pixel_count"] == 0


def test_missing_or_invalid_plot_geometry_fails_closed() -> None:
    package = _package()
    del package.metadata.plot_geometry

    observation = build_sentinel2_crop_observation(
        package, geometry_hash="geom-a",
    )
    invalid = build_sentinel2_crop_observation(
        _package(), plot_geometry={"type": "Polygon", "coordinates": []},
        geometry_hash="geom-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is False
    assert "missing_plot_geometry" in observation["quality_rejection_reasons"]
    assert observation["field_pixel_count"] == 0
    assert invalid is not None
    assert invalid["quality_admitted"] is False
    assert "missing_plot_geometry" in invalid["quality_rejection_reasons"]


def test_plot_and_scene_crs_mismatch_fails_closed() -> None:
    observation = build_sentinel2_crop_observation(
        _package(),
        plot_geometry=FULL_PLOT_GEOMETRY,
        plot_geometry_crs="EPSG:3857",
        geometry_hash="geom-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is False
    assert "plot_scene_crs_mismatch" in observation["quality_rejection_reasons"]
    assert observation["pixel_support_contract"]["grid_identity"]["scene_crs"] == "EPSG:4326"
    assert observation["pixel_support_contract"]["grid_identity"]["plot_geometry_crs"] == "EPSG:3857"


def test_missing_scene_crs_fails_closed() -> None:
    package = _package()
    package.metadata.crs = None

    observation = build_sentinel2_crop_observation(
        package, geometry_hash="geom-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is False
    assert "missing_scene_crs" in observation["quality_rejection_reasons"]
    assert observation["valid_pixel_count"] == 0


def test_polygon_holes_are_excluded_from_field_support() -> None:
    polygon_with_hole = {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [3, 0], [3, 3], [0, 3], [0, 0]],
            [[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]],
        ],
    }

    observation = build_sentinel2_crop_observation(
        _package(), plot_geometry=polygon_with_hole, geometry_hash="geom-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is True
    assert observation["field_pixel_count"] == 8
    assert observation["valid_pixel_count"] == 8


def test_support_identity_binds_mask_to_transform_crs_and_geometry() -> None:
    first = build_sentinel2_crop_observation(
        _package(), geometry_hash="geom-a",
    )
    shifted_package = _package()
    shifted_package.metadata.transform = (0.1, 1.0, 0.0, 3.0, 0.0, -1.0)
    shifted = build_sentinel2_crop_observation(
        shifted_package, geometry_hash="geom-a",
    )
    other_geometry = build_sentinel2_crop_observation(
        _package(), geometry_hash="geom-b",
    )

    assert first is not None and shifted is not None and other_geometry is not None
    first_hash = first["pixel_support_contract"]["support_hash"]
    assert first_hash != shifted["pixel_support_contract"]["support_hash"]
    assert first_hash != other_geometry["pixel_support_contract"]["support_hash"]


def test_unverified_reflectance_units_fail_closed() -> None:
    package = _package()
    package.band_units.pop("B08")

    observation = build_sentinel2_crop_observation(
        package, geometry_hash="geom-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is False
    assert "unverified_units:B08" in observation["quality_rejection_reasons"]
    assert "required_reflectance_unavailable" in observation["quality_rejection_reasons"]


def test_scaled_reflectance_is_explicitly_normalized_before_indices() -> None:
    package = _package()
    for name in tuple(package.band_arrays):
        if name.startswith("B"):
            package.band_arrays[name] = package.band_arrays[name] * 10000.0
            package.band_units[name] = "scaled_0_10000"

    observation = build_sentinel2_crop_observation(
        package, geometry_hash="geom-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is True
    assert observation["reflectance_scale_by_band"]["B08"] == 0.0001
    assert observation["b08_median"] == 0.20
    assert observation["ndvi_mean"] == pytest.approx(1 / 3, abs=1e-6)


def test_processing_products_for_one_sensing_event_are_one_observation() -> None:
    first = build_sentinel2_crop_observation(
        _package(PRODUCT_A, content_hash="content-a"), geometry_hash="geom-a",
    )
    second = build_sentinel2_crop_observation(
        _package(PRODUCT_A_REPROCESSED, content_hash="content-b"), geometry_hash="geom-a",
    )
    assert first is not None and second is not None
    assert first["physical_acquisition_key"] == second["physical_acquisition_key"]

    deduplicated = deduplicate_physical_acquisitions([first, second])

    assert len(deduplicated) == 1
    assert deduplicated[0]["provider_product_id"] == PRODUCT_A_REPROCESSED
    assert deduplicated[0]["processing_lineage_count"] == 2
    assert deduplicated[0]["duplicate_processing_product_count"] == 1
    assert deduplicated[0]["independent_observation_count"] == 1
    assert {
        item["content_hash"] for item in deduplicated[0]["processing_lineage"]
    } == {"content-a", "content-b"}


def test_physical_identity_normalizes_provider_spelling_variants() -> None:
    product_authority = sentinel2_physical_identity({
        "provider_product_id": PRODUCT_A,
        "mission": "Sentinel-2A",
        "relative_orbit": "R999",
        "mgrs_tile_id": "T99ZZZ",
    }, geometry_hash="geom-a", plot_namespace=NAMESPACE)
    explicit_metadata = sentinel2_physical_identity({
        "mission": "Sentinel-2B",
        "sensing_timestamp": "2026-08-06T10:25:59Z",
        "relative_orbit": 108,
        "mgrs_tile_id": "31sda",
    }, geometry_hash="geom-a", plot_namespace=NAMESPACE)

    assert product_authority["mission"] == "S2B"
    assert product_authority["relative_orbit"] == "R108"
    assert product_authority["tile_id"] == "T31SDA"
    assert product_authority["physical_acquisition_key"] == (
        explicit_metadata["physical_acquisition_key"]
    )
    assert len(product_authority["physical_acquisition_key"]) == len("S2ACQ-") + 64
    other_tenant = sentinel2_physical_identity(
        {"provider_product_id": PRODUCT_A},
        geometry_hash="geom-a",
        plot_namespace={**NAMESPACE, "tenant_id": "tenant-b"},
    )
    assert product_authority["physical_acquisition_key"] != (
        other_tenant["physical_acquisition_key"]
    )


def test_distinct_sensing_events_and_plot_geometries_remain_distinct() -> None:
    first = build_sentinel2_crop_observation(
        _package(PRODUCT_A), geometry_hash="geom-a",
    )
    later = build_sentinel2_crop_observation(
        _package(PRODUCT_B), geometry_hash="geom-a",
    )
    other_plot_identity = sentinel2_physical_identity(
        {"provider_product_id": PRODUCT_A}, geometry_hash="geom-b",
        plot_namespace={**NAMESPACE, "plot_id": "plot-b"},
    )
    assert first is not None and later is not None
    assert first["physical_acquisition_key"] != later["physical_acquisition_key"]
    assert first["physical_acquisition_key"] != other_plot_identity["physical_acquisition_key"]
    assert len(deduplicate_physical_acquisitions([first, later])) == 2


def test_source_package_builder_deduplicates_before_crop_inference() -> None:
    source_packages = {
        "asmae_sentinel2_real": [
            _package(PRODUCT_A, content_hash="content-a"),
            _package(PRODUCT_A_REPROCESSED, content_hash="content-b"),
            _package(PRODUCT_B, content_hash="content-c"),
        ],
    }

    records = build_canonical_crop_observations(
        source_packages, geometry_hash="geom-a",
    )

    assert len(records) == 2
    assert sum(record["processing_lineage_count"] for record in records) == 3
    assert all(record["quality_admitted"] is True for record in records)
    assert all(record["record_type"] == "CanonicalCropObservationV2" for record in records)
    ledger = build_crop_evidence_ledger(records, plot_namespace=NAMESPACE)
    assert ledger.to_dict()["admitted_independent_cluster_count"] == 2


def test_legacy_sentinel_packet_derives_physical_identity_from_product_lineage() -> None:
    package = SimpleNamespace(
        source_family="sentinel2",
        metadata=SimpleNamespace(
            source_family="sentinel2",
            provider_product_id=PRODUCT_A,
            plot_geometry_hash="geom-a",
            source_reality="real_raster",
            production_usable=True,
            real_provider_product=True,
            diagnostic_only=False,
            tenant_id="tenant-a",
            farm_id="farm-a",
            plot_id="plot-a",
        ),
        packets=[{
            "timestamp": "2026-08-06T10:25:59+00:00",
            "ndvi_mean": 0.4,
            "quality_admitted": True,
            "usable": True,
            "source_reality": "real_raster",
            "production_usable": True,
            "real_provider_product": True,
            "diagnostic_only": False,
        }],
    )

    records = build_canonical_crop_observations({"sentinel2": [package]})

    assert len(records) == 1
    assert records[0]["independence_identity_available"] is True
    assert records[0]["physical_acquisition_key"].startswith("S2ACQ-")
    assert records[0]["independent_observation_count"] == 1


def test_sentinel_packet_without_physical_identity_cannot_inflate_support() -> None:
    from services.agribrain.layer2_veg_int.crop_posterior import _admitted_records

    package = SimpleNamespace(
        source_family="sentinel2",
        metadata=SimpleNamespace(
            source_family="sentinel2",
            provider_product_id="opaque-processing-product",
            plot_geometry_hash="geom-a",
            source_reality="real_raster",
            production_usable=True,
            real_provider_product=True,
            diagnostic_only=False,
            tenant_id="tenant-a",
            farm_id="farm-a",
            plot_id="plot-a",
        ),
        packets=[{
            "timestamp": "2026-08-06T10:25:59+00:00",
            "ndvi_mean": 0.4,
            "quality_admitted": True,
            "usable": True,
            "source_reality": "real_raster",
            "production_usable": True,
            "real_provider_product": True,
            "diagnostic_only": False,
        }],
    )

    records = build_canonical_crop_observations({"sentinel2": [package]})

    assert len(records) == 1
    assert records[0]["independence_identity_available"] is False
    assert records[0]["independent_observation_count"] == 0
    assert _admitted_records(records) == []


def test_orchestrator_adapter_derives_metrics_when_temporal_packet_has_none() -> None:
    from services.agribrain.orchestrator_v2.runner import (
        _canonical_crop_temporal_records,
        to_layer0_sentinel2_package,
    )

    source = _package()
    metadata = vars(source.metadata)
    record = {
        **metadata,
        "band_arrays": source.band_arrays,
        "band_units": source.band_units,
        "mask_refs": {},
        "quality": {"valid_fraction": 1.0},
        "acquisition_datetime": "2026-08-06T10:40:52+00:00",
    }
    packages = to_layer0_sentinel2_package({
        "plot_id": "plot-a",
        "plot_geometry_hash": "geom-a",
        "data": [record],
    })
    assert packages[0].packets[0]["ndvi_mean"] is None

    records = _canonical_crop_temporal_records(
        SimpleNamespace(layer0_source_packages={"asmae_sentinel2_real": packages}),
        plot_geometry=FULL_PLOT_GEOMETRY,
        plot_geometry_crs="EPSG:4326",
        plot_namespace={
            "tenant_id": "tenant-a", "farm_id": "farm-a", "plot_id": "plot-a",
        },
        geometry_hash="geom-a",
    )

    assert len(records) == 1
    assert records[0]["record_type"] == "CanonicalCropObservationV2"
    assert records[0]["quality_admitted"] is True
    assert records[0]["ndvi_mean"] == pytest.approx(1 / 3, abs=1e-6)
    assert records[0]["valid_pixel_count"] == 9

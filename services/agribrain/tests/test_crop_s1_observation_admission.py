from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from services.agribrain.layer0.asmae_scene_products.product_binding import (
    verify_exact_product_binding,
)
from services.agribrain.layer0.asmae_scene_products.s1_real_scene_product_fetcher import (
    _has_complete_s1_orbit_metadata,
)
from services.agribrain.layer2_veg_int.crop_observations import (
    build_canonical_crop_observations,
    build_crop_evidence_ledger,
    build_sentinel1_crop_observation,
    deduplicate_physical_acquisitions,
    sentinel1_physical_identity,
)


PRODUCT = (
    "S1A_IW_GRDH_1SDV_20260806T052312_20260806T052337_060001_"
    "076ABC_1234.SAFE"
)
PRODUCT_REPROCESSED = (
    "S1A_IW_GRDH_1SDV_20260806T052312_20260806T052337_060001_"
    "076ABC_5678.SAFE"
)
PRODUCT_S1D = (
    "S1D_IW_GRDH_1SDV_20260806T052312_20260806T052337_000123_"
    "076ABC_1234.SAFE"
)
GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [3, 0], [3, 3], [0, 3], [0, 0]]],
}
NAMESPACE = {
    "tenant_id": "tenant-a", "farm_id": "farm-a", "plot_id": "plot-a",
}


def _package(
    *, product_id: str = PRODUCT, unit: str = "linear_power",
    content_hash: str = "s1-content-a",
) -> SimpleNamespace:
    if unit == "db":
        vv = np.full((3, 3), -10.0)
        vh = np.full((3, 3), 10.0 * np.log10(0.025))
    else:
        vv = np.full((3, 3), 0.1)
        vh = np.full((3, 3), 0.025)
    metadata = SimpleNamespace(
        scene_id="s1-scene-a",
        acquisition_datetime="2026-08-06T05:23:12+00:00",
        provider_product_id=product_id,
        catalog_item_id=product_id,
        content_hash=content_hash,
        processing_timestamp="2026-08-06T08:00:00+00:00",
        source_reality="real_raster",
        production_usable=True,
        real_provider_product=True,
        diagnostic_only=False,
        provider_orbit_pass="ascending",
        relative_orbit=108,
        crs="EPSG:4326",
        transform=(0.0, 1.0, 0.0, 3.0, 0.0, -1.0),
        band_units={"VV": unit, "VH": unit, "DATAMASK": "binary_mask"},
        plot_geometry=GEOMETRY,
        plot_geometry_crs="EPSG:4326",
        plot_geometry_hash="geometry-a",
        tenant_id="tenant-a",
        farm_id="farm-a",
        plot_id="plot-a",
        sensor="S1",
    )
    return SimpleNamespace(
        metadata=metadata,
        source_family="sentinel1",
        band_arrays={
            "VV": vv,
            "VH": vh,
            "DATAMASK": np.ones((3, 3), dtype=np.uint8),
        },
        band_units=metadata.band_units,
        local_cache_refs={},
        mask_refs={},
        source_reality="real_raster",
        production_usable=True,
        real_provider_product=True,
        diagnostic_only=False,
        packets=[],
    )


def test_linear_power_arrays_are_normalized_to_db_and_rich_sar_features() -> None:
    observation = build_sentinel1_crop_observation(
        _package(), geometry_hash="geometry-a",
    )

    assert observation is not None
    assert observation["record_type"] == "CanonicalCropObservationV2"
    assert observation["quality_admitted"] is True
    assert observation["physical_acquisition_key"].startswith("S1ACQ-")
    assert observation["mission"] == "S1A"
    assert observation["orbit_reference"] == "R108"
    assert observation["orbit_pass"] == "ASCENDING"
    assert observation["canonical_backscatter_unit"] == "db"
    assert observation["backscatter_units_verified"] is True
    assert observation["vv_db_mean"] == pytest.approx(-10.0)
    assert observation["vh_db_mean"] == pytest.approx(-16.0206, abs=1e-6)
    assert observation["vv_vh_ratio_mean"] == pytest.approx(4.0)
    assert observation["vv_minus_vh_db_mean"] == pytest.approx(6.0206, abs=1e-6)
    assert observation["rvi_mean"] == pytest.approx(0.8)
    assert observation["cross_pol_fraction_mean"] == pytest.approx(0.2)
    assert observation["texture_summary"]["vv_db"][
        "mean_absolute_neighbor_difference"
    ] == 0.0
    assert observation["spectral_summary"] == {}
    assert observation["sar_summary"]["backscatter_statistics"]["VV"][
        "valid_count"
    ] == 9
    rvi_features = [
        item for item in observation["feature_contributions"]
        if item["feature_name"] == "rvi"
    ]
    assert rvi_features
    assert {tuple(item["source_bands"]) for item in rvi_features} == {
        ("VV", "VH"),
    }


def test_declared_db_and_linear_power_produce_same_physical_statistics() -> None:
    linear = build_sentinel1_crop_observation(
        _package(unit="linear_power"), geometry_hash="geometry-a",
    )
    db = build_sentinel1_crop_observation(
        _package(unit="db", content_hash="s1-content-db"),
        geometry_hash="geometry-a",
    )

    assert linear is not None and db is not None
    assert linear["physical_acquisition_key"] == db["physical_acquisition_key"]
    for name in (
        "vv_db_mean", "vh_db_mean", "vv_vh_ratio_mean", "rvi_mean",
        "cross_pol_fraction_mean",
    ):
        assert linear[name] == pytest.approx(db[name], abs=1e-6)


@pytest.mark.parametrize("unit", ["normalized_display", "sigma0", "gamma0"])
def test_unverified_or_display_units_fail_closed_without_range_inference(
    unit: str,
) -> None:
    package = _package(unit=unit)

    observation = build_sentinel1_crop_observation(
        package, geometry_hash="geometry-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is False
    assert observation["valid_pixel_count"] == 0
    assert observation["backscatter_units_verified"] is False
    assert "unverified_units:VV" in observation["quality_rejection_reasons"]
    assert "unverified_units:VH" in observation["quality_rejection_reasons"]
    assert "required_backscatter_unavailable" in (
        observation["quality_rejection_reasons"]
    )


def test_every_sar_statistic_uses_one_plot_mask_and_finite_support() -> None:
    package = _package()
    package.band_arrays["DATAMASK"][0, 0] = 0
    package.band_arrays["VV"][0, 1] = np.nan
    package.band_arrays["VH"][0, 2] = 0.0

    observation = build_sentinel1_crop_observation(
        package, geometry_hash="geometry-a",
    )

    assert observation is not None
    assert observation["quality_admitted"] is True
    assert observation["field_pixel_count"] == 9
    assert observation["valid_pixel_count"] == 6
    assert observation["nodata_fraction"] == pytest.approx(1 / 3, abs=1e-6)
    base_hash = observation["pixel_support_contract"]["support_hash"]
    supports = observation["feature_support_contracts"]
    assert {
        item["valid_pixel_count"]
        for group in supports.values() for item in group.values()
    } == {6}
    assert {
        item["support_hash"]
        for group in supports.values() for item in group.values()
    } == {base_hash}
    assert {
        stats["valid_count"]
        for container in (
            observation["band_statistics"], observation["index_statistics"],
        )
        for stats in container.values()
    } == {6}


def test_missing_datamask_and_crs_mismatch_are_rejected() -> None:
    missing_mask = _package()
    missing_mask.band_arrays.pop("DATAMASK")
    mismatch = build_sentinel1_crop_observation(
        _package(), plot_geometry=GEOMETRY,
        plot_geometry_crs="EPSG:3857", geometry_hash="geometry-a",
    )
    missing = build_sentinel1_crop_observation(
        missing_mask, geometry_hash="geometry-a",
    )

    assert missing is not None and mismatch is not None
    assert missing["quality_admitted"] is False
    assert missing["valid_pixel_count"] == 0
    assert "missing_mask:DATAMASK" in missing["quality_rejection_reasons"]
    assert mismatch["quality_admitted"] is False
    assert mismatch["valid_pixel_count"] == 0
    assert "plot_scene_crs_mismatch" in mismatch["quality_rejection_reasons"]


def test_pass_identity_requires_orbit_and_pass_and_is_namespace_scoped() -> None:
    base = sentinel1_physical_identity(
        {
            "provider_product_id": PRODUCT,
            "relative_orbit": 108,
            "provider_orbit_pass": "ascending",
        },
        geometry_hash="geometry-a", plot_namespace=NAMESPACE,
    )
    reprocessed = sentinel1_physical_identity(
        {
            "provider_product_id": PRODUCT_REPROCESSED,
            "relative_orbit": "R108",
            "orbit_direction": "ASCENDING",
        },
        geometry_hash="geometry-a", plot_namespace=NAMESPACE,
    )
    other_pass = sentinel1_physical_identity(
        {
            "provider_product_id": PRODUCT,
            "relative_orbit": 108,
            "provider_orbit_pass": "descending",
        },
        geometry_hash="geometry-a", plot_namespace=NAMESPACE,
    )
    other_plot = sentinel1_physical_identity(
        {
            "provider_product_id": PRODUCT,
            "relative_orbit": 108,
            "provider_orbit_pass": "ascending",
        },
        geometry_hash="geometry-b",
        plot_namespace={**NAMESPACE, "plot_id": "plot-b"},
    )
    missing_pass = sentinel1_physical_identity(
        {"provider_product_id": PRODUCT, "relative_orbit": 108},
        geometry_hash="geometry-a", plot_namespace=NAMESPACE,
    )

    assert base["physical_identity_complete"] is True
    assert base["physical_acquisition_key"] == reprocessed[
        "physical_acquisition_key"
    ]
    assert base["physical_acquisition_key"] != other_pass[
        "physical_acquisition_key"
    ]
    assert base["physical_acquisition_key"] != other_plot[
        "physical_acquisition_key"
    ]
    assert missing_pass["physical_identity_complete"] is False
    assert missing_pass["physical_acquisition_key"] is None


def test_s1d_identity_resolves_process_then_catalog_then_official_fields() -> None:
    identity = sentinel1_physical_identity(
        {
            "provider_product_id": PRODUCT_S1D,
            "process_metadata": {
                "userData": {"tiles": [{
                    "relativeOrbitNumber": 33,
                    "orbitDirection": "descending",
                }]},
            },
            "catalog_metadata": {"properties": {
                "platform": "sentinel-1d",
                "datetime": "2026-08-06T05:23:12Z",
                # Process metadata has authority over conflicting Catalog
                # geometry metadata.
                "sat:relative_orbit": 77,
                "sat:orbit_state": "ascending",
            }},
        },
        geometry_hash="geometry-a", plot_namespace=NAMESPACE,
    )

    assert identity["mission"] == "S1D"
    assert identity["sensing_timestamp"] == "2026-08-06T05:23:12+00:00"
    assert identity["relative_orbit"] == "R033"
    assert identity["orbit_pass"] == "DESCENDING"
    assert identity["physical_identity_complete"] is True
    assert identity["identity_resolution"] == {
        "mission_source": "catalog_stac_metadata",
        "sensing_source": "catalog_stac_metadata",
        "relative_orbit_source": "process_metadata",
        "orbit_pass_source": "process_metadata",
    }


def test_invalid_process_orbit_fields_fall_through_to_valid_catalog_metadata() -> None:
    identity = sentinel1_physical_identity(
        {
            "provider_product_id": PRODUCT_S1D,
            "process_metadata": {"userData": {"tiles": [{
                "relativeOrbitNumber": 999,
                "orbitDirection": "sideways",
            }]}},
            "catalog_metadata": {"properties": {
                "platform": "sentinel-1d",
                "datetime": "2026-08-06T05:23:12Z",
                "sat:relative_orbit": 33,
                "sat:orbit_state": "descending",
            }},
        },
        geometry_hash="geometry-a", plot_namespace=NAMESPACE,
    )

    assert identity["physical_identity_complete"] is True
    assert identity["relative_orbit"] == "R033"
    assert identity["orbit_pass"] == "DESCENDING"
    assert identity["identity_resolution"]["relative_orbit_source"] == (
        "catalog_stac_metadata"
    )
    assert identity["identity_resolution"]["orbit_pass_source"] == (
        "catalog_stac_metadata"
    )


def test_process_binding_persists_orbit_metadata_and_legacy_cache_requires_refresh() -> None:
    userdata = {"userData": {"tiles": [{
        "sentinel1ProductId": PRODUCT_S1D,
        "relativeOrbitNumber": 33,
        "orbitDirection": "descending",
        "orbitId": 123,
    }]}}
    binding = verify_exact_product_binding(PRODUCT_S1D, userdata, "S1")

    assert binding["is_exact"] is True
    assert binding["provider_relative_orbit"] == 33
    assert binding["provider_absolute_orbit"] == 123
    assert binding["provider_orbit_pass"] == "descending"
    assert binding["process_metadata"] == userdata
    assert _has_complete_s1_orbit_metadata(binding) is True
    assert _has_complete_s1_orbit_metadata({
        "provider_absolute_orbit": 60001,
        "provider_orbit_pass": "ascending",
    }) is False
    assert _has_complete_s1_orbit_metadata({
        "catalog_metadata": {"properties": {
            "sat:relative_orbit": 33,
            "sat:orbit_state": "descending",
        }},
    }) is True


def test_official_s1_product_id_cannot_invent_pass_or_relative_orbit() -> None:
    missing_relative = sentinel1_physical_identity(
        {
            "provider_product_id": PRODUCT_S1D,
            "catalog_metadata": {"sat:orbit_state": "ascending"},
        },
        geometry_hash="geometry-a", plot_namespace=NAMESPACE,
    )
    invalid_relative = sentinel1_physical_identity(
        {
            "provider_product_id": PRODUCT_S1D,
            "relative_orbit": 999,
            "orbit_direction": "ascending",
        },
        geometry_hash="geometry-a", plot_namespace=NAMESPACE,
    )

    assert missing_relative["mission"] == "S1D"
    assert missing_relative["sensing_timestamp"] == "2026-08-06T05:23:12+00:00"
    assert missing_relative["relative_orbit"] is None
    assert missing_relative["physical_identity_complete"] is False
    assert missing_relative["physical_acquisition_key"] is None
    assert invalid_relative["physical_identity_complete"] is False
    assert invalid_relative["relative_orbit"] is None


def test_raw_s1_precedes_scalar_packet_and_reprocessing_is_one_evidence_item() -> None:
    first_package = _package()
    first_package.packets = [{
        "timestamp": "2026-08-06T05:23:12+00:00",
        "vv_db_mean": 99.0,
        "quality_admitted": True,
    }]
    second_package = _package(
        product_id=PRODUCT_REPROCESSED, content_hash="s1-content-b",
    )
    second_package.metadata.processing_timestamp = "2026-08-06T09:00:00+00:00"

    records = build_canonical_crop_observations(
        {"asmae_sentinel1_real": [first_package, second_package]},
        geometry_hash="geometry-a",
    )

    assert len(records) == 1
    record = records[0]
    assert record["vv_db_mean"] == pytest.approx(-10.0)
    assert record["processing_lineage_count"] == 2
    assert record["duplicate_processing_product_count"] == 1
    assert record["independent_observation_count"] == 1
    ledger = build_crop_evidence_ledger(records, plot_namespace=NAMESPACE)
    counts = ledger.to_dict()["evidence_counts"]
    assert counts["admitted_sar_acquisitions"] == 1
    assert counts["admitted_optical_acquisitions"] == 0


def test_raw_candidate_without_sensing_time_cannot_fall_back_to_packet() -> None:
    package = _package()
    package.metadata.provider_product_id = "opaque-s1-product"
    package.metadata.catalog_item_id = "opaque-s1-product"
    package.metadata.acquisition_datetime = None
    package.packets = [{
        "timestamp": "2026-08-06T05:23:12+00:00",
        "vv_db_mean": -10.0,
        "quality_admitted": True,
    }]

    records = build_canonical_crop_observations(
        {"sentinel1": [package]}, geometry_hash="geometry-a",
    )

    assert records == []


def test_s1_array_content_hash_reads_every_cell() -> None:
    first_package = _package(content_hash="")
    second_package = _package(content_hash="")
    second_package.band_arrays["VV"] = np.array(
        second_package.band_arrays["VV"], copy=True,
    )
    second_package.band_arrays["VV"][1, 1] = 0.101

    first = build_sentinel1_crop_observation(
        first_package, geometry_hash="geometry-a",
    )
    second = build_sentinel1_crop_observation(
        second_package, geometry_hash="geometry-a",
    )

    assert first is not None and second is not None
    assert first["content_hash"].startswith("S1CONTENT-")
    assert first["content_hash"] != second["content_hash"]
    assert first["physical_acquisition_key"] == second[
        "physical_acquisition_key"
    ]


def test_orchestrator_s1_adapter_preserves_physical_and_processing_lineage() -> None:
    from services.agribrain.orchestrator_v2.runner import (
        _canonical_crop_temporal_records,
        to_layer0_sentinel1_package,
    )

    source = _package()
    record = {
        **vars(source.metadata),
        "band_arrays": source.band_arrays,
        "band_units": source.band_units,
        "mask_refs": {},
        "quality": {"valid_fraction": 1.0},
        "width": 3,
        "height": 3,
        "acquisition_datetime": "2026-08-06T05:23:12+00:00",
        "process_request_hash": "request-hash-a",
        "provider_response_hash": "response-hash-a",
    }
    packages = to_layer0_sentinel1_package({
        "tenant_id": "tenant-a",
        "farm_id": "farm-a",
        "plot_id": "plot-a",
        "plot_geometry_hash": "geometry-a",
        "plot_geometry": GEOMETRY,
        "plot_geometry_crs": "EPSG:4326",
        "data": [record],
    })

    assert packages[0].metadata.provider_orbit_pass == "ascending"
    assert packages[0].metadata.relative_orbit == 108
    assert packages[0].metadata.process_request_hash == "request-hash-a"
    assert packages[0].provenance["provider_orbit_pass"] == "ascending"
    assert packages[0].provenance["relative_orbit"] == 108

    # The adapter output is also a complete Layer-0 wrapper input.  This
    # guards the production failure where S1 omitted ``provenance`` and made
    # Layer0Runner abandon the modern L1 path before raster ingestion.
    from services.agribrain.layer0.runner import Layer0Runner, Layer0RunnerInput

    layer0 = Layer0Runner().run(Layer0RunnerInput(
        plot_id="plot-a",
        geometry_hash="geometry-a",
        geometry_version=1,
        start_date="2026-08-06",
        end_date="2026-08-06",
        sentinel1_packages=packages,
    ))
    [wrapped_s1] = layer0.layer0_source_packages["sentinel1"]
    assert wrapped_s1.provenance["provider_orbit_pass"] == "ascending"
    assert wrapped_s1.provenance["relative_orbit"] == 108

    records = _canonical_crop_temporal_records(
        SimpleNamespace(
            layer0_source_packages={"asmae_sentinel1_real": packages}
        ),
        plot_geometry=GEOMETRY,
        plot_geometry_crs="EPSG:4326",
        plot_namespace=NAMESPACE,
        geometry_hash="geometry-a",
    )

    assert len(records) == 1
    assert records[0]["quality_admitted"] is True
    assert records[0]["physical_acquisition_key"].startswith("S1ACQ-")
    assert records[0]["processing_lineage"][0][
        "process_request_hash"
    ] == "request-hash-a"


def test_orchestrator_s1_adapter_preserves_scene_product_orbit_authority() -> None:
    """Production SceneProduct fields must not depend on legacy aliases."""

    from services.agribrain.orchestrator_v2.runner import (
        to_layer0_sentinel1_package,
    )

    source = _package()
    record = {
        **vars(source.metadata),
        "band_arrays": source.band_arrays,
        "band_units": source.band_units,
        "quality": {"valid_fraction": 1.0},
        "width": 3,
        "height": 3,
        "acquisition_datetime": "2026-08-06T05:23:12+00:00",
        "provider_relative_orbit": 33,
        "provider_absolute_orbit": 44201,
        "process_metadata": {
            "relativeOrbitNumber": 33,
            "orbitDirection": "ASCENDING",
        },
        "catalog_metadata": {
            "sat:relative_orbit": 33,
            "sat:orbit_state": "ascending",
        },
    }
    record.pop("relative_orbit", None)
    record.pop("relative_orbit_number", None)
    record.pop("orbit_number", None)

    [package] = to_layer0_sentinel1_package({
        "tenant_id": "tenant-a",
        "farm_id": "farm-a",
        "plot_id": "plot-a",
        "plot_geometry_hash": "geometry-a",
        "plot_geometry": GEOMETRY,
        "plot_geometry_crs": "EPSG:4326",
        "data": [record],
    })

    assert package.metadata.provider_relative_orbit == 33
    assert package.metadata.provider_absolute_orbit == 44201
    assert package.metadata.relative_orbit == 33
    assert package.metadata.process_metadata["relativeOrbitNumber"] == 33
    assert package.metadata.catalog_metadata["sat:relative_orbit"] == 33
    assert package.packets[0]["provider_relative_orbit"] == 33
    assert package.provenance["provider_relative_orbit"] == 33

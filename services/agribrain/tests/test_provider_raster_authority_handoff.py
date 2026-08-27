from types import SimpleNamespace
from pathlib import Path
from datetime import datetime, timezone

from layer1_fusion.outputs.legacy_compat import (
    _merge_authorized_raster_ndvi_observation,
    _rebuild_map_metadata,
)
from layer1_fusion.raster_backend import GridSpec
from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
from services.agribrain.layer10_sire.schema import Layer10Input
from services.agribrain.layer10_sire.surfaces.vegetation import (
    generate_vegetation_surfaces,
)
from services.agribrain.layer10_sire.surfaces.agronomic_models import (
    _get_weather_metrics,
)
from services.agribrain.layer10_sire.surfaces.derivation_lineage import (
    attach_derived_surface_lineage,
)
from services.agribrain.orchestrator_v2.runner import to_layer0_environment_package
from services.agribrain.layer0.runner import Layer0Runner, Layer0RunnerInput
from services.agribrain.layer1_fusion.runner import run_layer1_fusion
from services.agribrain.orchestrator_v2.schema import OrchestratorInput
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer0.data_gateway.request_broker import (
    _raster_candidate_valid,
)
from services.agribrain.layer0.data_gateway.fetch_registry import (
    _fetch_raster_composite_ndvi,
)
from services.agribrain.layer1_fusion.runner import (
    RASTER_GATEWAY_CONTRACT_VERSION,
)


def test_provider_truth_survives_legacy_map_bridge():
    bounds = (2.0, 36.0, 2.2, 36.2)
    transform = (2.0, 0.1, 0.0, 36.2, 0.0, -0.1)
    rr = SimpleNamespace(
        raster_id="provider-ndvi",
        variable="ndvi",
        grid=[[0.2, 0.4], [0.6, 0.8]],
        crs="EPSG:4326",
        bounds=bounds,
        transform=transform,
        width=2,
        height=2,
        resolution_m=10.0,
        content_hash="abc",
        visualization_allowed=True,
        truth_class="observed_provider_product",
        source_reality="provider_temporal_composite_raster",
        real_provider_product=True,
        production_usable=True,
        grounding_class="RASTER_GROUNDED",
        diagnostic_only=False,
        state_update_allowed=True,
        observed_spatial_surface=True,
        prescription_driver_allowed=False,
        observed_ratio=1.0,
        provenance={"provider": "sentinel_hub"},
    )
    package = SimpleNamespace(spatial_index=SimpleNamespace(raster_refs=[rr]))
    grid_spec = GridSpec(
        crs="EPSG:4326", transform=transform, width=2, height=2,
        bounds=bounds, resolution=10.0,
    )

    metadata = _rebuild_map_metadata(package, grid_spec)

    assert metadata["ndvi"]["source_reality"] == "provider_temporal_composite_raster"
    assert metadata["ndvi"]["real_provider_product"] is True
    assert metadata["ndvi"]["production_usable"] is True
    assert metadata["NDVI"]["content_hash"] == "abc"

    tensor = SimpleNamespace(
        run_id="l1-run",
        grid_spec=grid_spec,
        maps={"ndvi": rr.grid},
        map_metadata=metadata,
        data=[],
        channels=[],
        plot_timeseries=[],
        daily_state={},
        zone_stats={},
        zones={},
        provenance={},
        static={},
    )
    l1_data = adapt_l1(tensor, 2, 2)
    surface = generate_vegetation_surfaces(
        Layer10Input(
            plot_namespace=PlotNamespace("tenant", "farm", "plot"),
            field_tensor=tensor,
            grid_height=2,
            grid_width=2,
        ),
        2,
        2,
        l1_data=l1_data,
    )[0]

    assert surface.provenance["source_reality"] == "provider_temporal_composite_raster"
    assert surface.provenance["real_provider_product"] is True
    assert surface.provenance["production_usable"] is True


def _provider_raster_candidate(**overrides):
    candidate = {
        "width": 2,
        "height": 2,
        "values": [[0.2, 0.4], [0.6, 0.8]],
        "valid_mask": [[1, 1], [1, 1]],
        "valid_pixel_count": 4,
        "truth_class": "provider_derived_composite",
        "source_reality": "provider_temporal_composite_raster",
        "real_provider_product": True,
        "production_usable": True,
        "diagnostic_only": False,
        "raster_contract_version": RASTER_GATEWAY_CONTRACT_VERSION,
        "grid_spec": {
            "crs": "EPSG:4326",
            "bounds": [2.0, 36.0, 2.2, 36.2],
            "transform": [2.0, 0.1, 0.0, 36.2, 0.0, -0.1],
            "width": 2,
            "height": 2,
            "resolution_m": 10.0,
        },
    }
    candidate.update(overrides)
    return candidate


def test_raster_cache_candidate_requires_current_explicit_authority_contract():
    current = _provider_raster_candidate()
    assert _raster_candidate_valid(current, RASTER_GATEWAY_CONTRACT_VERSION)

    old_cache_entry = dict(current)
    old_cache_entry.pop("raster_contract_version")
    assert not _raster_candidate_valid(
        old_cache_entry, RASTER_GATEWAY_CONTRACT_VERSION
    )

    missing_authority = dict(current, source_reality="")
    assert not _raster_candidate_valid(
        missing_authority, RASTER_GATEWAY_CONTRACT_VERSION
    )


def test_raster_fetch_registry_transports_authority_contract(monkeypatch):
    import eo.sentinel as sentinel

    received = {}

    def fake_fetch(lat, lng, start, end, **kwargs):
        received.update(kwargs)
        return _provider_raster_candidate()

    monkeypatch.setattr(sentinel, "fetch_ndvi_raster_composite", fake_fetch)
    result = _fetch_raster_composite_ndvi(
        36.5,
        2.9,
        "2026-08-01",
        "2026-08-17",
        polygon_coords=[[2.9, 36.5]],
        target_resolution_m=20.0,
        raster_contract_version=RASTER_GATEWAY_CONTRACT_VERSION,
    )

    assert result["source_reality"] == "provider_temporal_composite_raster"
    assert received == {
        "polygon_coords": [[2.9, 36.5]],
        "target_resolution_m": 20.0,
        "raster_contract_version": RASTER_GATEWAY_CONTRACT_VERSION,
    }


def test_all_production_runner_modules_compile():
    """Lazy imports must not demote production runs via hidden syntax errors."""
    agribrain_root = Path(__file__).resolve().parents[1]
    runner_paths = sorted(agribrain_root.rglob("runner.py"))
    assert runner_paths, "no production runner modules found"

    failures = []
    for path in runner_paths:
        try:
            compile(path.read_bytes(), str(path), "exec")
        except (OSError, SyntaxError) as exc:
            failures.append(f"{path.relative_to(agribrain_root)}: {exc}")

    assert not failures, "production runner source is invalid:\n" + "\n".join(failures)


def test_authorized_provider_ndvi_reaches_layer2_temporal_contract():
    rows = [{"date": "2026-07-31", "is_observed": False, "ndvi_mean": None}]
    metadata = {
        "ndvi": {
            "raster_id": "provider-ndvi",
            "content_hash": "ndvi-content-a",
            "source_reality": "provider_temporal_composite_raster",
            "production_usable": True,
            "real_provider_product": True,
            "diagnostic_only": False,
            "observed_ratio": 1.0,
            "confidence": 0.9,
            "state_update_allowed": False,
        },
    }
    changed = _merge_authorized_raster_ndvi_observation(
        rows,
        {"ndvi": [[0.2, 0.4], [0.6, 0.8]]},
        metadata,
        datetime(2026, 7, 31, tzinfo=timezone.utc),
    )
    assert changed is True
    assert rows[0]["is_observed"] is True
    assert rows[0]["ndvi_mean"] == 0.5
    assert rows[0]["observation_type"] == "provider_raster_spatial_aggregate"
    assert rows[0]["content_hash"] == "ndvi-content-a"


def test_empty_forecast_context_falls_back_to_l1_weather_forcing():
    forecast = SimpleNamespace(
        temperature_max_forecast=[], temperature_min_forecast=[],
        wind_speed_forecast=[], humidity_forecast=[], precipitation_forecast=[],
    )
    inp = SimpleNamespace(forecast_context=forecast, field_tensor=None)
    l1_data = SimpleNamespace(weather_history=[{
        "tmean": 29.0,
        "wind_speed": 3.5,
        "humidity": 62.0,
        "rain": 1.2,
    }])
    assert _get_weather_metrics(inp, l1_data) == (29.0, 3.5, 62.0, 1.2)


def test_layer0_v2_weather_package_reaches_l1_timeseries():
    native = to_layer0_environment_package({
        "plot_id": "plot-weather",
        "weather_consensus": [{
            "date": "2026-07-01", "temp_max": 34.0, "temp_min": 22.0,
            "precipitation": 1.5, "et0": 5.2, "humidity": 61.0,
            "wind_speed": 3.4,
        }],
        "soilgrids": {}, "fao_context": {},
        "timestamp_window": {
            "window_start": "2026-07-01T00:00:00+00:00",
            "window_end": "2026-07-01T23:59:59+00:00",
        },
    })
    layer0 = Layer0Runner().run(Layer0RunnerInput(
        plot_id="plot-weather", geometry_hash="geometry-weather",
        start_date="2026-07-01", end_date="2026-07-01",
        environment_package=native,
    ))
    assert layer0.layer0_source_packages["environment"][0].contract_version == (
        "layer0-source-package-v2"
    )
    tensor = run_layer1_fusion(
        OrchestratorInput(
            plot_namespace=PlotNamespace("tenant", "farm", "plot-weather"),
            geometry_hash="geometry-weather",
            date_range={"start": "2026-07-01", "end": "2026-07-01"},
            crop_config={}, operational_context={}, policy_snapshot={},
        ),
        layer0, {}, None, {},
    )
    [row] = tensor.plot_timeseries
    assert row["temp_max"] == 34.0
    assert row["temp_min"] == 22.0
    assert row["rain"] == 1.5
    assert row["et0"] == 5.2
    assert row["humidity"] == 61.0
    assert row["wind_speed"] == 3.4
    l1_data = adapt_l1(tensor)
    metrics = _get_weather_metrics(
        SimpleNamespace(forecast_context=None, field_tensor=tensor), l1_data,
    )
    assert metrics == (28.0, 3.4, 61.0, 1.5)


def test_provider_derived_surface_gets_typed_diagnostic_lineage():
    grid = {
        "crs": "EPSG:4326",
        "transform": [2.0, 0.1, 0.0, 36.2, 0.0, -0.1],
    }
    surface = SimpleNamespace(
        semantic_type="NDVI_DEVIATION",
        raster_basis=["ndvi"],
        observed_ratio=1.0,
        grid_spec=grid,
        provenance={},
    )
    l1_data = SimpleNamespace(
        grid_spec=grid,
        raster_metadata={
            "ndvi": {
                "raster_id": "provider-ndvi",
                "content_hash": "ndvi-content-a",
                "source_reality": "provider_temporal_composite_raster",
                "real_provider_product": True,
                "production_usable": True,
                **grid,
            },
        },
    )
    assert attach_derived_surface_lineage(surface, l1_data) is True
    assert surface.provenance["source_reality"] == "provider_derived"
    assert surface.provenance["derived_from_surface_ids"] == ["provider-ndvi"]
    assert surface.provenance["derived_from_content_hashes"] == ["ndvi-content-a"]
    assert surface.provenance["crs_transform_closure"] is True
    assert surface.provenance["diagnostic_only"] is True
    assert surface.provenance["prescription_driver_allowed"] is False

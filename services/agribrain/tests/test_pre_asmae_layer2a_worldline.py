from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer1_fusion.schema import FieldTensor
from services.agribrain.orchestrator_v2.pre_asmae_layer2a import (
    CROP_POSTERIOR_EVENT_TYPE,
    PHENOLOGY_POSTERIOR_EVENT_TYPE,
    build_pre_asmae_layer2a_input,
    commit_crop_posterior_worldline,
    commit_phenology_posterior_worldline,
    load_latest_crop_posterior,
    load_latest_crop_posterior_record,
    load_latest_crop_phenology_event,
    load_latest_phenology_posterior,
    run_pre_asmae_layer2a,
)
from services.agribrain.orchestrator_v2.schema import OrchestratorInput
from services.agribrain.scientific_contracts.crop_evidence import (
    CanonicalCropObservationV2,
    CropEvidenceLedgerV2,
)
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
)


NS = PlotNamespace("tenant-a", "farm-a", "plot-a")


def _observation(
    *,
    suffix: str,
    timestamp: str,
    cycle: str,
    ndvi: float,
) -> CanonicalCropObservationV2:
    raw = {
        "observation_id": f"obs-{suffix}",
        "timestamp": timestamp,
        "date": timestamp[:10],
        "physical_acquisition_key": f"S2ACQ-{suffix}",
        "physical_identity_complete": True,
        "independence_identity_available": True,
        "source_family": "sentinel2",
        "provider": "copernicus",
        "mission": "S2B",
        "sensor": "MSI",
        "plot_geometry_hash": "geometry-a",
        "quality_admitted": True,
        "quality_class": "good",
        "valid_pixel_count": 8,
        "field_pixel_count": 9,
        "valid_fraction": 8 / 9,
        "cloud_fraction": 1 / 9,
        "shadow_fraction": 0.0,
        "snow_fraction": 0.0,
        "nodata_fraction": 0.0,
        "reading_reliability": 0.8,
        "pixel_support_contract": {
            "support_hash": f"support-{suffix}",
            "support_definition": "plot&DATAMASK&SCL&finite",
            "grid_identity": {
                "shape": [3, 3],
                "transform": [0, 1, 0, 3, 0, -1],
                "scene_crs": "EPSG:4326",
                "plot_geometry_crs": "EPSG:4326",
                "plot_geometry_hash": "geometry-a",
            },
        },
        "band_statistics": {
            "B08": {"valid_count": 8, "mean": 0.2},
            "B04": {"valid_count": 8, "mean": 0.1},
        },
        "index_statistics": {
            "ndvi": {"valid_count": 8, "mean": ndvi},
            "ndre": {"valid_count": 8, "mean": 0.2},
        },
        "environmental_context": {
            "day_of_year": 180,
            "gdd_coordinates": {"weather_station_v1": 420.0},
            "primary_gdd_basis": "weather_station_v1",
            "season_phase": "vegetative",
        },
        "calibration_domain_compatibility": "compatible",
        "geographical_domain_compatibility": "compatible",
        "crop_cycle_id": cycle,
        "direct_observation": True,
        "provider_product_id": f"product-{suffix}",
        "content_hash": f"content-{suffix}",
        "processing_lineage": [{
            "provider_product_id": f"product-{suffix}",
            "processing_timestamp": timestamp,
            "content_hash": f"content-{suffix}",
        }],
    }
    return CanonicalCropObservationV2.from_mapping(raw, plot_namespace=NS)


def _ledger(*, include_future: bool = False) -> CropEvidenceLedgerV2:
    observations = [
        _observation(
            suffix="old-1", timestamp="2025-04-01T10:00:00+00:00",
            cycle="cycle-old", ndvi=0.20,
        ),
        _observation(
            suffix="old-2", timestamp="2025-04-11T10:00:00+00:00",
            cycle="cycle-old", ndvi=0.65,
        ),
    ]
    for index, (date, ndvi) in enumerate((
        ("2026-06-01", 0.24),
        ("2026-06-11", 0.38),
        ("2026-06-21", 0.55),
        (("2026-08-10" if include_future else "2026-07-01"), 0.68),
    )):
        observations.append(_observation(
            suffix=f"current-{index}",
            timestamp=f"{date}T10:00:00+00:00",
            cycle="cycle-current",
            ndvi=ndvi,
        ))
    return CropEvidenceLedgerV2.from_observations(NS, observations)


def _inputs(ledger: CropEvidenceLedgerV2) -> OrchestratorInput:
    return OrchestratorInput(
        plot_namespace=NS,
        geometry_hash="geometry-a",
        date_range={"start": "2026-06-01", "end": "2026-07-31"},
        crop_config={
            "crop": "tomato",
            "crop_cycle_id": "cycle-current",
            "crop_evidence_ledger": ledger.to_dict(),
            "crop_evidence_ledger_hash": ledger.ledger_hash,
            "crop_posterior": {
                "content_hash": "crop-posterior-hash",
                "crop_cycle_identity": "cycle-current",
            },
        },
        operational_context={"lat": 36.5, "lng": 2.9},
    )


def test_pre_asmae_layer2a_uses_only_selected_ledger_representatives() -> None:
    ledger = _ledger()
    original = FieldTensor(
        plot_id=NS.plot_id,
        run_id="layer1-run",
        plot_timeseries=[{
            "date": "2026-06-01",
            "ndvi": 0.99,
            "source": "unledgered-poison-row",
        }],
        zone_stats={"ndvi": {"zone-a": [{"mean": 0.99}]}},
    )
    weather = [
        {
            "date": f"2026-06-{day:02d}",
            "tmean": 24.0 + day / 100,
            "rainfall": float(day),
            "ndvi": 0.99,
        }
        for day in (1, 11, 21)
    ] + [{
        "date": "2026-07-01", "tmean": 27.0, "rainfall": 1.0,
        "ndvi": 0.99,
    }]

    bundle = build_pre_asmae_layer2a_input(
        _inputs(ledger), original, weather_records=weather,
    )

    assert bundle.segmentation.status == "ledger_cycle_identity_scoped"
    assert len(bundle.selected_observation_ids) == 4
    assert all("current" in value for value in bundle.selected_observation_ids)
    assert [row["observation_id"] for row in bundle.tensor.plot_timeseries] == list(
        bundle.selected_observation_ids
    )
    assert [row["ndvi"] for row in bundle.tensor.plot_timeseries] == [
        0.24, 0.38, 0.55, 0.68,
    ]
    assert bundle.tensor.plot_timeseries[0]["rain"] == 1.0
    assert bundle.tensor.plot_timeseries[0]["tmean"] == pytest.approx(24.01)
    assert bundle.tensor.zone_stats == {}
    assert original.plot_timeseries[0]["ndvi"] == 0.99
    assert original.zone_stats
    assert bundle.input_receipt[
        "generic_plot_timeseries_consumed_as_crop_evidence"
    ] is False
    assert bundle.input_receipt["source_crop_evidence_ledger_hash"] == ledger.ledger_hash
    assert bundle.inputs.crop_config[
        "pre_asmae_layer2a_input_receipt"
    ]["content_hash"] == bundle.input_receipt["content_hash"]
    with_unrelated_weather = build_pre_asmae_layer2a_input(
        _inputs(ledger),
        original,
        weather_records=weather + [{
            "date": "2020-01-01", "tmean": -20.0, "rainfall": 999.0,
        }],
    )
    assert with_unrelated_weather.input_receipt == bundle.input_receipt


def test_pre_asmae_layer2a_rejects_future_selected_evidence() -> None:
    ledger = _ledger(include_future=True)
    with pytest.raises(ValueError, match="future evidence"):
        build_pre_asmae_layer2a_input(
            _inputs(ledger),
            FieldTensor(plot_id=NS.plot_id, run_id="layer1-run"),
        )


def test_pre_asmae_layer2a_exposes_canonical_context_only() -> None:
    ledger = _ledger()
    bundle = build_pre_asmae_layer2a_input(
        _inputs(ledger),
        FieldTensor(plot_id=NS.plot_id, run_id="layer1-run"),
    )
    seen = {}

    def fake_layer2(inputs, tensor):
        seen["inputs"] = inputs
        seen["tensor"] = tensor
        return SimpleNamespace(
            run_id="layer2a-run",
            phenology=SimpleNamespace(canonical_posterior={
                "content_hash": "phenology-hash",
                "current_stage": "VEGETATIVE",
                "authority": "diagnostic",
            }),
            crop_season_evidence_receipt={
                "content_hash": "season-hash",
                "source_evidence_ledger_hash": ledger.ledger_hash,
            },
            crop_active_acquisition_plan={"content_hash": "plan-hash"},
        )

    result = run_pre_asmae_layer2a(bundle, layer2_runner=fake_layer2)

    assert seen == {"inputs": bundle.inputs, "tensor": bundle.tensor}
    assert result.asmae_context["pre_asmae_layer2a_status"] == "available"
    assert result.asmae_context["phenology_posterior_hash"] == "phenology-hash"
    assert result.asmae_context[
        "crop_season_evidence_receipt_hash"
    ] == "season-hash"
    assert result.asmae_context["crop_active_acquisition_plan_hash"] == "plan-hash"
    assert result.asmae_context["layer2a_run_id"] == "layer2a-run"


def test_crop_and_phenology_worldline_use_full_namespace(tmp_path) -> None:
    service = CanonicalWorldlineService(root=tmp_path)
    crop = {
        "contract_version": "crop-posterior-v1",
        "plot_id": NS.plot_id,
        "authority": "diagnostic",
        "crop_evidence_ledger_hash": "CROPLEDGERV2-" + "a" * 64,
        "content_hash": "crop-hash",
        "top_group": "vegetable",
    }
    crop_event = commit_crop_posterior_worldline(
        service,
        plot_namespace=NS,
        crop_posterior=crop,
        geometry_version="geometry-a",
        effective_at="2026-07-01T12:00:00+00:00",
        observation_or_valid_time="2026-07-01T10:00:00+00:00",
        parent_orchestrator_run_id="run-a",
    )
    phenology = {
        "contract_version": "canonical-phenology-v2",
        "namespace": {
            "tenant_id": NS.tenant_id,
            "farm_id": NS.farm_id,
            "plot_id": NS.plot_id,
        },
        "authority": "diagnostic",
        "stage_authority": "diagnostic",
        "evidence_ledger_hash": "CROPLEDGERV2-" + "a" * 64,
        "content_hash": "phenology-hash",
        "current_stage": "VEGETATIVE",
    }
    phenology_event = commit_phenology_posterior_worldline(
        service,
        plot_namespace=NS,
        phenology_posterior=phenology,
        geometry_version="geometry-a",
        effective_at="2026-07-01T12:01:00+00:00",
        observation_or_valid_time="2026-07-01T10:00:00+00:00",
        parent_event_ids=(crop_event["event_id"],),
        parent_orchestrator_run_id="run-a",
    )

    crop_latest = load_latest_crop_phenology_event(
        service, plot_namespace=NS, event_type=CROP_POSTERIOR_EVENT_TYPE,
    )
    phenology_latest = load_latest_crop_phenology_event(
        service, plot_namespace=NS, event_type=PHENOLOGY_POSTERIOR_EVENT_TYPE,
    )
    assert crop_latest["event_id"] == crop_event["event_id"]
    assert phenology_latest["event_id"] == phenology_event["event_id"]
    assert phenology_latest["parent_event_ids"] == [crop_event["event_id"]]
    assert phenology_latest["tenant_id"] == NS.tenant_id
    assert phenology_latest["namespace"] == NS.farm_id
    assert phenology_latest["plot_id"] == NS.plot_id
    assert phenology_latest["payload"]["plot_namespace"] == {
        "tenant_id": NS.tenant_id,
        "farm_id": NS.farm_id,
        "plot_id": NS.plot_id,
    }
    assert load_latest_crop_posterior(
        service, plot_namespace=NS,
    )["content_hash"] == "crop-hash"
    crop_record = load_latest_crop_posterior_record(
        service, plot_namespace=NS,
    )
    assert crop_record is not None
    assert crop_record.worldline_event_id == crop_event["event_id"]
    assert crop_record.event_sequence == crop_event["sequence"]
    assert crop_record.posterior["content_hash"] == "crop-hash"
    assert "_worldline_event_id" not in crop_record.posterior
    assert load_latest_phenology_posterior(
        service, plot_namespace=NS,
    )["content_hash"] == "phenology-hash"

    other_farm = PlotNamespace(NS.tenant_id, "farm-b", NS.plot_id)
    assert load_latest_crop_posterior(
        service, plot_namespace=other_farm,
    ) is None


def test_worldline_rejects_cross_namespace_scientific_payload(tmp_path) -> None:
    service = CanonicalWorldlineService(root=tmp_path)
    with pytest.raises(ValueError, match="namespace mismatch"):
        commit_phenology_posterior_worldline(
            service,
            plot_namespace=NS,
            phenology_posterior={
                "namespace": {
                    "tenant_id": NS.tenant_id,
                    "farm_id": "other-farm",
                    "plot_id": NS.plot_id,
                },
                "authority": "diagnostic",
                "evidence_ledger_hash": "ledger-a",
                "content_hash": "phenology-a",
            },
            geometry_version="geometry-a",
            effective_at="2026-07-01T12:00:00+00:00",
            observation_or_valid_time="2026-07-01T10:00:00+00:00",
        )


def test_orchestrator_runs_layer2a_before_asmae_and_has_no_default_worldline() -> None:
    source = (
        Path(__file__).parents[1] / "orchestrator_v2" / "runner.py"
    ).read_text(encoding="utf-8")

    layer2a_call = source.index("build_pre_asmae_layer2a_input(")
    asmae_start = source.index("# --- ASMAE Execution ---")
    assert layer2a_call < asmae_start
    assert source.count("**pre_asmae_layer2a_context") == 2
    assert source.count('"worldline_namespace": inputs.farm_id') == 2
    assert "PlotWorldlineService" not in source
    assert 'namespace="default"' not in source
    assert "commit_crop_posterior_worldline(" in source
    assert "commit_phenology_posterior_worldline(" in source


def test_crop_identify_reads_the_same_namespaced_canonical_worldline() -> None:
    source = (
        Path(__file__).parents[1] / "app" / "main.py"
    ).read_text(encoding="utf-8")
    endpoint = source.split("def api_v2_crop_identify(", 1)[1].split(
        "# ============================================================================",
        1,
    )[0]

    assert "load_latest_crop_posterior_record(" in endpoint
    assert "plot_namespace=namespace" in endpoint
    assert "crop_record.worldline_event_id" in endpoint
    assert "crop_event.get" not in endpoint
    assert "PlotWorldlineService" not in endpoint
    assert '"default"' not in endpoint

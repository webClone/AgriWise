from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer2_veg_int.crop_ml import CropFeedbackStore
from services.agribrain.layer2_veg_int.crop_posterior import (
    _apply_cycle_bounded_temporal_prior,
    _scientific_content_hash,
    infer_crop_posterior,
)
from services.agribrain.orchestrator_v2.run_entrypoint import _build_inputs


def _previous_posterior(
    *, cycle: str, support: int = 2, declared_crop: str | None = None,
):
    previous = {
        "plot_id": "plot-1",
        "crop_cycle_identity": cycle,
        "generated_at": (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat(),
        "declared_crop_normalized": declared_crop,
        "crop_group_posterior": {
            "solanaceae_veg": 0.8,
            "unknown": 0.2,
        },
        "evidence_quality": {"physical_acquisition_count": support},
    }
    previous["content_hash"] = _scientific_content_hash(previous)
    return previous


def test_temporal_prior_is_same_cycle_bounded_capped_and_not_evidence():
    current = {"winter_cereal": 0.2, "unknown": 0.8}
    blended, audit = _apply_cycle_bounded_temporal_prior(
        current,
        _previous_posterior(cycle="cycle-a"),
        plot_id="plot-1",
        cycle_identity="cycle-a",
        current_declared_crop=None,
        current_authority="MODEL_GROUP_POSTERIOR",
        current_physical_acquisition_count=4,
        generated_at=datetime.now(timezone.utc),
    )

    assert audit["applied"] is True
    assert audit["role"] == "prior_only_not_observation"
    assert audit["counted_as_evidence"] is False
    assert 0.0 < audit["weight"] <= audit["maximum_weight"] == 0.12
    assert audit["new_physical_acquisition_count"] == 2
    assert blended["solanaceae_veg"] > 0.0
    assert blended["unknown"] < current["unknown"]


def test_temporal_prior_resets_on_cycle_change_and_decays_with_new_support():
    current = {"winter_cereal": 0.2, "unknown": 0.8}
    unchanged, reset = _apply_cycle_bounded_temporal_prior(
        current,
        _previous_posterior(cycle="cycle-a"),
        plot_id="plot-1",
        cycle_identity="cycle-b",
        current_declared_crop=None,
        current_authority="MODEL_GROUP_POSTERIOR",
        current_physical_acquisition_count=2,
        generated_at=datetime.now(timezone.utc),
    )
    assert reset["applied"] is False
    assert reset["reason"] == "crop_cycle_changed_reset"
    assert unchanged == current

    _, low_support = _apply_cycle_bounded_temporal_prior(
        current,
        _previous_posterior(cycle="cycle-a"),
        plot_id="plot-1",
        cycle_identity="cycle-a",
        current_declared_crop=None,
        current_authority="MODEL_GROUP_POSTERIOR",
        current_physical_acquisition_count=2,
        generated_at=datetime.now(timezone.utc),
    )
    _, high_support = _apply_cycle_bounded_temporal_prior(
        current,
        _previous_posterior(cycle="cycle-a"),
        plot_id="plot-1",
        cycle_identity="cycle-a",
        current_declared_crop=None,
        current_authority="MODEL_GROUP_POSTERIOR",
        current_physical_acquisition_count=8,
        generated_at=datetime.now(timezone.utc),
    )
    assert high_support["weight"] < low_support["weight"]


def test_temporal_prior_rejects_corruption_and_declaration_correction():
    current = {"winter_cereal": 0.2, "unknown": 0.8}
    corrupted = _previous_posterior(cycle="cycle-a")
    corrupted["crop_group_posterior"] = {"solanaceae_veg": 0.99, "unknown": 0.01}
    unchanged, invalid = _apply_cycle_bounded_temporal_prior(
        current,
        corrupted,
        plot_id="plot-1",
        cycle_identity="cycle-a",
        current_declared_crop=None,
        current_authority="MODEL_GROUP_POSTERIOR",
        current_physical_acquisition_count=2,
        generated_at=datetime.now(timezone.utc),
    )
    assert unchanged == current
    assert invalid["reason"] == "previous_prior_content_hash_invalid"

    unchanged, corrected = _apply_cycle_bounded_temporal_prior(
        current,
        _previous_posterior(cycle="cycle-a", declared_crop="tomato"),
        plot_id="plot-1",
        cycle_identity="cycle-a",
        current_declared_crop="wheat",
        current_authority="USER_CONFIRMED",
        current_physical_acquisition_count=2,
        generated_at=datetime.now(timezone.utc),
    )
    assert unchanged == current
    assert corrected["reason"] == "declared_identity_changed_reset"

    unchanged, authoritative = _apply_cycle_bounded_temporal_prior(
        current,
        _previous_posterior(cycle="cycle-a", declared_crop="tomato"),
        plot_id="plot-1",
        cycle_identity="cycle-a",
        current_declared_crop="tomato",
        current_authority="USER_CONFIRMED",
        current_physical_acquisition_count=2,
        generated_at=datetime.now(timezone.utc),
    )
    assert unchanged == current
    assert authoritative["reason"] == "confirmed_declaration_authoritative"


def _admitted_ndvi_record(index: int, value: float) -> dict:
    return {
        "date": f"2026-06-{1 + index * 7:02d}T10:00:00Z",
        "source_reality": "provider_catalog_scene_observation",
        "provider_product_id": f"S2A_PRODUCT_{index}",
        "physical_acquisition_key": f"S2ACQ-{index}",
        "content_hash": f"content-{index}",
        "ndvi": value,
        "usable": True,
        "quality_class": "good",
        "production_usable": True,
        "real_provider_product": True,
        "diagnostic_only": False,
    }


def test_model_context_group_ranking_is_separate_from_registry_and_memory():
    result = infer_crop_posterior(
        plot_id="plot-1",
        run_id="run-1",
        plot_timeseries=[
            _admitted_ndvi_record(index, value)
            for index, value in enumerate((0.31, 0.39, 0.46, 0.52))
        ],
        crop_config={"crop": "tomato", "crop_cycle_id": "cycle-a"},
        operational_context={"lat": 36.5, "lng": 2.9},
    )

    support = result["model_context_support"]
    # Generic Layer-1 rows are not canonical crop observations. Without a
    # verified CropEvidenceLedgerV2 the EO ranking must remain unavailable;
    # the registry declaration is still represented as its own prior.
    assert support["status"] == "unavailable"
    assert support["admitted_physical_acquisition_count"] == 0
    assert support["registry_declaration_included"] is False
    assert support["temporal_prior_included"] is False
    assert support["species_confirmation_allowed"] is False
    assert support["generic_plot_timeseries_included"] is False
    assert result["model_context_group_posterior"] == {"unknown": 1.0}
    assert result["crop_group_posterior"] != result["model_context_group_posterior"]
    assert result["content_hash"] == _scientific_content_hash(result)

    no_observations = infer_crop_posterior(
        plot_id="plot-2",
        run_id="run-2",
        plot_timeseries=[],
        crop_config={"crop": "tomato", "crop_cycle_id": "cycle-b"},
    )
    assert no_observations["model_context_support"]["status"] == "unavailable"
    assert no_observations["model_context_support"][
        "admitted_physical_acquisition_count"
    ] == 0
    assert no_observations["model_context_group_posterior"] == {"unknown": 1.0}
    assert no_observations["crop_group_posterior"].get("solanaceae_veg", 0) > 0


def test_run_input_transports_active_crop_cycle_identity():
    namespace = PlotNamespace(
        tenant_id="tenant-1", farm_id="farm-1", plot_id="plot-1"
    )
    inputs = _build_inputs(
        {
            "tenant_id": namespace.tenant_id,
            "farm_id": namespace.farm_id,
            "plot_id": namespace.plot_id,
            "crop": "tomato",
            "stage": "GROWING",
            "crop_cycle_id": "cycle-123",
            "crop_season_id": "cycle-123",
            "planting_date": "2026-06-01T00:00:00.000Z",
            "polygon": {
                "type": "Polygon",
                "coordinates": [[[2.0, 36.0], [2.1, 36.0], [2.0, 36.1], [2.0, 36.0]]],
            },
        },
        authenticated_namespace=namespace,
    )
    assert inputs.crop_config["crop_cycle_id"] == "cycle-123"
    assert inputs.crop_config["crop_season_id"] == "cycle-123"
    assert inputs.crop_config["planting_date"].startswith("2026-06-01")
    assert inputs.operational_context["crop_cycle_id"] == "cycle-123"


def test_farmer_feedback_is_audit_only_and_cannot_form_global_prior(tmp_path):
    store = CropFeedbackStore(str(tmp_path))
    partition = {
        "tenant_id": "tenant-1",
        "region_partition": "dz-north",
        "season_partition": "2026-summer",
        "sensor_regime": "sentinel-2-l2a",
    }
    for index in range(40):
        store.record_observation(
            plot_id=f"plot-{index}",
            confirmed_crop="tomato",
            engine_prediction="wheat",
            engine_confidence=0.2,
            phenology={},
            tenant_id="tenant-1",
            farm_id=f"farm-{index % 8}",
            crop_cycle_id=f"cycle-{index}",
            region_partition="dz-north",
            season_partition="2026-summer",
            sensor_regime="sentinel-2-l2a",
            # Default label_source is a farmer confirmation and is not ground truth.
        )

    assert store.compute_learned_priors(partition=partition) == {}
    assert store.compute_learned_priors() == {}
    support = store.learning_support(partition)
    assert support["eligible_samples"] == 0
    assert support["farmer_feedback_is_training_label"] is False


def test_validated_feedback_requires_partition_diversity_and_deduplicates_cycle(tmp_path):
    store = CropFeedbackStore(str(tmp_path))
    partition = {
        "tenant_id": "tenant-1",
        "region_partition": "dz-north",
        "season_partition": "2026-summer",
        "sensor_regime": "sentinel-2-l2a",
    }
    crops = ("tomato", "wheat", "olive")
    for index in range(36):
        store.record_observation(
            plot_id=f"plot-{index}",
            confirmed_crop=crops[index % len(crops)],
            engine_prediction="unknown",
            engine_confidence=0.0,
            phenology={"peak_ndvi": 0.5 + (index % 3) * 0.01},
            tenant_id="tenant-1",
            farm_id=f"farm-{index % 6}",
            crop_cycle_id=f"cycle-{index}",
            region_partition="dz-north",
            season_partition="2026-summer",
            sensor_regime="sentinel-2-l2a",
            label_source="official_parcel_label",
            label_confidence="HIGH",
            authority_validated=True,
        )

    priors = store.compute_learned_priors(partition=partition)
    assert set(priors) == set(crops)
    assert sum(priors.values()) == pytest.approx(1.0)
    assert store.compute_learned_priors(partition={
        **partition, "region_partition": "dz-south",
    }) == {}

    # A repeated click for the same plot-cycle is one independent label.
    store.record_observation(
        plot_id="plot-0",
        confirmed_crop="tomato",
        engine_prediction="tomato",
        engine_confidence=0.9,
        phenology={},
        tenant_id="tenant-1",
        farm_id="farm-0",
        crop_cycle_id="cycle-0",
        region_partition="dz-north",
        season_partition="2026-summer",
        sensor_regime="sentinel-2-l2a",
        label_source="official_parcel_label",
        label_confidence="HIGH",
        authority_validated=True,
    )
    assert store.learning_support(partition)["eligible_samples"] == 36


def test_feedback_sigmas_require_multiple_independent_farms_per_crop(tmp_path):
    partition = {
        "tenant_id": "tenant-1",
        "region_partition": "dz-north",
        "season_partition": "2026-summer",
        "sensor_regime": "sentinel-2-l2a",
    }

    def populate(store: CropFeedbackStore, *, one_farm: bool) -> None:
        for index in range(6):
            store.record_observation(
                plot_id=f"plot-{index}",
                confirmed_crop="tomato",
                engine_prediction="unknown",
                engine_confidence=0.0,
                phenology={"peak_ndvi": 0.42 + index * 0.03},
                tenant_id="tenant-1",
                farm_id="farm-1" if one_farm else f"farm-{index % 3}",
                crop_cycle_id=f"cycle-{index}",
                region_partition="dz-north",
                season_partition="2026-summer",
                sensor_regime="sentinel-2-l2a",
                label_source="official_parcel_label",
                label_confidence="HIGH",
                authority_validated=True,
            )

    diverse = CropFeedbackStore(str(tmp_path / "diverse"))
    populate(diverse, one_farm=False)
    assert "tomato" in diverse.compute_learned_sigmas(
        min_samples=6,
        partition=partition,
        min_plots=6,
        min_farms=3,
        min_cycles=6,
    )

    concentrated = CropFeedbackStore(str(tmp_path / "concentrated"))
    populate(concentrated, one_farm=True)
    assert concentrated.compute_learned_sigmas(
        min_samples=6,
        partition=partition,
        min_plots=6,
        min_farms=3,
        min_cycles=6,
    ) == {}


def test_four_scene_sequence_is_ranking_only_not_species_detection():
    from services.agribrain.layer2_veg_int.crop_identification import identify_crop

    result = identify_crop(
        ndvi_series=[0.36, 0.39, 0.42, 0.40],
        ndvi_dates=["2026-06-01", "2026-06-11", "2026-06-21", "2026-07-01"],
        evi_mean=0.31,
        ndmi_mean=0.12,
        lat=36.5,
        lng=2.9,
        _force_rule_engine=True,
    )

    assert result.inference_mode == "sparse_timeseries"
    assert result.evidence_strength == "LOW"
    assert result.top_crop is None
    assert result.top_confidence == 0.0
    assert result.confidence_label == "LOW"
    assert result.detected_crop is False
    assert result.detected_crop_group is False
    assert result.prediction_depth == "L2"
    assert result.evidence["ndvi_observation_count"] == 4
    assert result.evidence["sparse_temporal_ranking"] is True
    assert result.evidence["species_detection_allowed"] is False
    assert result.evidence["ml_features"]["advanced_phenology"] is False
    assert result.candidates


def test_dense_rule_sequence_remains_l2_ranking_not_species_detection():
    from services.agribrain.layer2_veg_int.crop_identification import identify_crop

    result = identify_crop(
        ndvi_series=[0.22, 0.31, 0.44, 0.58, 0.66, 0.61],
        ndvi_dates=[
            "2026-04-01", "2026-04-11", "2026-04-21",
            "2026-05-01", "2026-05-11", "2026-05-21",
        ],
        evi_mean=0.40,
        ndmi_mean=0.16,
        lat=36.5,
        lng=2.9,
        _force_rule_engine=True,
    )

    assert result.inference_mode == "observed_timeseries"
    assert result.top_crop is None
    assert result.top_confidence == 0.0
    assert result.confidence_label == "LOW"
    assert result.detected_crop is False
    assert result.detected_crop_group is False
    assert result.prediction_depth == "L2"
    assert result.evidence["species_detection_allowed"] is False
    assert result.evidence["validated_ml_species_detection_required"] is True
    assert result.candidates


def test_sar_only_rule_path_is_explicit_ranking_not_temporal_detection():
    from services.agribrain.layer2_veg_int.crop_identification import identify_crop

    result = identify_crop(
        sar_vh_mean=-18.0,
        sar_vv_mean=-11.0,
        lat=36.5,
        lng=2.9,
        _force_rule_engine=True,
    )

    assert result.inference_mode == "sar_ranking_only"
    assert result.top_crop is None
    assert result.top_confidence == 0.0
    assert result.confidence_label == "LOW"
    assert result.detected_crop is False
    assert result.detected_crop_group is False
    assert result.prediction_depth == "L2"
    assert result.evidence["species_detection_allowed"] is False
    assert result.candidates


def test_nonproduction_ml_artifact_is_denied_in_production(monkeypatch):
    from services.agribrain.layer2_veg_int.crop_identification import (
        CropIdentificationEngine,
    )

    engine = CropIdentificationEngine()

    class NonProductionClassifier:
        models = object()
        production_eligible = False
        feature_names = []
        metadata = {}

        def predict(self, *_args, **_kwargs):
            raise AssertionError("nonproduction model must not execute")

    engine._ml_classifier = NonProductionClassifier()
    engine._ml_load_status = {"loaded": True}
    monkeypatch.setenv("AGRIBRAIN_CROP_ML_ENABLED", "true")
    monkeypatch.setenv("AGRIBRAIN_CROP_ML_ALLOW_NONPRODUCTION_ARTIFACT", "true")
    monkeypatch.setenv("AGRIBRAIN_ENV", "production")

    result = engine.identify(
        ndvi_series=[0.2, 0.3, 0.5, 0.7, 0.6, 0.4],
        ndvi_dates=[
            "2026-04-01", "2026-04-11", "2026-04-21",
            "2026-05-01", "2026-05-11", "2026-05-21",
        ],
        lat=36.5,
        lng=2.9,
        feature_vector_snapshot={"data_completeness": 1.0},
    )
    assert result.evidence["ml_runtime_gate"]["runtime_allowed"] is False
    assert result.evidence["ml_runtime_gate"]["production_eligible"] is False

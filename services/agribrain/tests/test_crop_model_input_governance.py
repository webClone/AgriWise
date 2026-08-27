from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from sklearn.impute import SimpleImputer

from services.agribrain.layer2_veg_int.features.crop_feature_vector import (
    CropFeatureVector,
    crop_feature_schema_receipt,
    crop_feature_transform_hash,
    crop_feature_transform_manifest,
)
from services.agribrain.layer2_veg_int.features.phenology_features import (
    extract_phenology_features,
)
from services.agribrain.layer2_veg_int.features.sar_temporal_features import (
    extract_sar_temporal_features,
)
from services.agribrain.layer2_veg_int.features.ledger_crop_features import (
    _token_row,
    build_ledger_crop_feature_input,
)
from services.agribrain.layer2_veg_int.labels.classifier import (
    HierarchicalCropClassifier,
)
from services.agribrain.layer2_veg_int.labels.label_schema import CropLabel
from services.agribrain.layer2_veg_int.crop_posterior import (
    infer_crop_posterior,
)
from services.agribrain.scientific_contracts.crop_evidence import (
    CanonicalCropObservationV2,
    CropEvidenceLedgerV2,
)
from services.agribrain.scientific_contracts.crop_model_input import (
    CropFeatureSchemaReceiptV1,
    CropModelObservationTokenV1,
    build_crop_model_input_receipt,
    observation_tokens_from_ledger,
)
from services.agribrain.scientific_contracts.crop_cycle_segmentation import (
    _candidate_boundaries,
    build_crop_cycle_segmentation_receipt,
)


NAMESPACE = {"tenant_id": "tenant-a", "farm_id": "farm-a", "plot_id": "plot-a"}


def _observation(
    *, physical_key: str, product_id: str, timestamp: str, content: str,
    ndvi: float = 1 / 3, season_phase: str | None = None,
    gdd_accumulated: float = 420.0,
    calibration_domain: str = "compatible",
    crop_cycle_id: str | None = None,
) -> CanonicalCropObservationV2:
    raw = {
        "observation_id": f"crop-{product_id}",
        "timestamp": timestamp,
        "date": timestamp[:10],
        "physical_acquisition_key": physical_key,
        "physical_identity_complete": True,
        "independence_identity_available": True,
        "source_family": "sentinel2",
        "provider": "copernicus",
        "mission": "S2B",
        "sensor": "MSI",
        "tile_id": "T31SDA",
        "relative_orbit": "R108",
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
            "support_hash": "support-a",
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
            "day_of_year": 218,
            "gdd_accumulated": gdd_accumulated,
            "season_phase": season_phase,
        },
        "calibration_domain_compatibility": calibration_domain,
        "geographical_domain_compatibility": "compatible",
        "crop_cycle_id": crop_cycle_id,
        "direct_observation": True,
        "provider_product_id": product_id,
        "content_hash": content,
        "processing_lineage": [{
            "provider_product_id": product_id,
            "processing_timestamp": timestamp,
            "content_hash": content,
        }],
    }
    return CanonicalCropObservationV2.from_mapping(raw, plot_namespace=NAMESPACE)


def test_model_input_uses_one_selected_processing_lineage_per_physical_acquisition() -> None:
    first = _observation(
        physical_key="S2ACQ-a", product_id="product-a",
        timestamp="2026-08-01T10:00:00+00:00", content="content-a",
    )
    reprocessed = _observation(
        physical_key="S2ACQ-a", product_id="product-a-new",
        timestamp="2026-08-01T10:00:00+00:00", content="content-b",
    )
    later = _observation(
        physical_key="S2ACQ-b", product_id="product-b",
        timestamp="2026-08-10T10:00:00+00:00", content="content-c",
    )
    ledger = CropEvidenceLedgerV2.from_observations(
        NAMESPACE, [first, reprocessed, later],
    )
    tokens = observation_tokens_from_ledger(ledger)
    assert len(tokens) == 2
    assert {token.physical_acquisition_key for token in tokens} == {"S2ACQ-a", "S2ACQ-b"}
    assert all(token.quality_admitted for token in tokens)

    schema = crop_feature_schema_receipt()
    receipt = build_crop_model_input_receipt(
        ledger=ledger,
        crop_cycle_hypothesis_id="cycle-a",
        feature_schema=schema,
        feature_values={feature.name: None for feature in schema.features},
        feature_transform_hash="a" * 64,
        normalization_artifact_hash="b" * 64,
        domain_compatibility="compatible",
    )
    assert receipt.model_execution_eligible is False
    assert receipt.physical_evidence_sufficiency == "insufficient"
    assert "feature_tensor_incomplete" in receipt.publication_blockers
    assert receipt.to_dict()["optical_observation_ids"]
    vector, governed_receipt, segmentation = build_ledger_crop_feature_input(
        ledger=ledger, crop_cycle_hypothesis_id="cycle-a", run_id="run-a",
    )
    assert vector.data_sources == ["sentinel2"]
    assert governed_receipt.observation_ids == segmentation.current_observation_ids
    assert governed_receipt.crop_cycle_hypothesis_id.endswith(
        segmentation.primary_hypothesis_id
    )


def test_feature_schema_hash_binds_scientific_semantics_not_only_names() -> None:
    schema = crop_feature_schema_receipt()
    changed = replace(
        schema.features[0],
        scientific_definition=schema.features[0].scientific_definition + " changed",
    )
    second = CropFeatureSchemaReceiptV1(
        schema_version=schema.schema_version,
        transform_version=schema.transform_version,
        features=(changed,) + schema.features[1:],
    )
    assert second.content_hash != schema.content_hash
    assert CropFeatureVector().to_json()["flat_features"]


def test_transform_hash_is_exact_manifest_with_parameters_and_module_digests() -> None:
    schema = crop_feature_schema_receipt()
    manifest = crop_feature_transform_manifest()
    payload = manifest.to_dict()
    recipes = {recipe.feature_name: recipe for recipe in manifest.feature_recipes}

    assert set(recipes) == {feature.name for feature in schema.features}
    assert manifest.sos_threshold == 0.20
    assert manifest.sar_change_point_threshold_db == 2.5
    assert manifest.sar_rolling_window_days == 30
    assert "window=7" in manifest.smoothing_policy
    assert manifest.interpolation_policy.startswith("none")
    assert "no feature-stage resampling" in manifest.red_edge_policy
    assert crop_feature_transform_hash() == manifest.content_hash
    assert payload["content_hash"] == manifest.content_hash
    assert all(
        recipe.algorithm_id and recipe.formula_id
        and recipe.mask_semantics and recipe.temporal_coordinate
        and len(recipe.module_digest) == 64
        for recipe in recipes.values()
    )
    sar_parameters = dict(recipes["vv_rolling_median_slope"].parameters)
    assert sar_parameters["rolling_median_window_days"] == 30
    assert sar_parameters["change_point_threshold_db"] == 2.5
    phenology_parameters = dict(recipes["sos_doy"].parameters)
    assert phenology_parameters["sos_eos_amplitude_fraction"] == 0.20
    assert phenology_parameters["savgol_window_observations"] == 7

    # The content identity is the recipe, not a manually bumped version label.
    # A parameter edit carrying the old digest is rejected; recomputing it
    # produces a distinct transform hash.
    with pytest.raises(ValueError, match="manifest hash mismatch"):
        replace(manifest, sos_threshold=0.25)
    changed_threshold = replace(
        manifest, sos_threshold=0.25, content_hash="",
    )
    assert changed_threshold.content_hash != manifest.content_hash

    changed_recipe = replace(
        recipes["vv_rolling_median_slope"],
        parameters=tuple(
            (key, 21 if key == "rolling_median_window_days" else value)
            for key, value in recipes["vv_rolling_median_slope"].parameters
        ),
    )
    changed_recipes = tuple(
        changed_recipe if recipe.feature_name == changed_recipe.feature_name
        else recipe
        for recipe in manifest.feature_recipes
    )
    changed_window = replace(
        manifest, feature_recipes=changed_recipes, content_hash="",
    )
    assert changed_window.content_hash != manifest.content_hash


def test_primary_gdd_basis_controls_feature_axis_without_lexical_selection() -> None:
    token = CropModelObservationTokenV1(
        observation_id="obs-gdd",
        observation_hash="hash-gdd",
        physical_acquisition_key="S2ACQ-gdd",
        source_family="sentinel2",
        sensing_time="2026-08-06T10:00:00+00:00",
        feature_values=(("ndvi", "mean", 0.5),),
        quality_admitted=True,
        quality_class="good",
        support_hash="support-gdd",
        gdd_coordinates=(("GDD0", 400.0), ("GDD5", 250.0), ("GDD10", 100.0), ("GDD12", 60.0)),
        primary_gdd_basis="GDD5",
    )

    row = _token_row(token)
    assert row["gdd_accumulated"] == 250.0
    assert row["primary_gdd_basis"] == "GDD5"
    assert row["gdd_coordinates"]["GDD12"] == 60.0
    with pytest.raises(ValueError, match="explicit primary GDD basis"):
        replace(token, primary_gdd_basis=None)


def test_current_cycle_segmentation_excludes_prior_cycle_from_model_selection() -> None:
    dates_and_ndvi = [
        ("2026-01-01T10:00:00+00:00", 0.2),
        ("2026-01-10T10:00:00+00:00", 0.5),
        ("2026-01-20T10:00:00+00:00", 0.75),
        ("2026-02-01T10:00:00+00:00", 0.3),
        ("2026-04-15T10:00:00+00:00", 0.2),
        ("2026-04-25T10:00:00+00:00", 0.45),
        ("2026-05-05T10:00:00+00:00", 0.65),
    ]
    observations = [
        _observation(
            physical_key=f"S2ACQ-{index}", product_id=f"product-{index}",
            timestamp=timestamp, content=f"content-{index}", ndvi=ndvi,
        )
        for index, (timestamp, ndvi) in enumerate(dates_and_ndvi)
    ]
    ledger = CropEvidenceLedgerV2.from_observations(NAMESPACE, observations)
    segmentation = build_crop_cycle_segmentation_receipt(ledger)
    assert segmentation.calibrated is False
    assert len(segmentation.segments) >= 2
    assert segmentation.current_observation_ids == tuple(
        observation.observation_id for observation in observations[-3:]
    )
    assert len(segmentation.current_cycle_hypotheses) >= 2
    assert sum(
        hypothesis.probability
        for hypothesis in segmentation.current_cycle_hypotheses
    ) == pytest.approx(1.0)
    assert any(
        len(hypothesis.observation_ids) == len(observations)
        for hypothesis in segmentation.current_cycle_hypotheses
    )


def test_segment_scoped_readiness_cannot_borrow_old_cycle_phase_or_gdd() -> None:
    rows = [
        ("2026-01-01T10:00:00+00:00", 0.2, "early", 20.0),
        ("2026-01-12T10:00:00+00:00", 0.5, "mid", 120.0),
        ("2026-01-24T10:00:00+00:00", 0.7, "mid", 240.0),
        ("2026-04-15T10:00:00+00:00", 0.2, "late", 500.0),
        ("2026-04-25T10:00:00+00:00", 0.4, "late", 560.0),
        ("2026-05-05T10:00:00+00:00", 0.6, "late", 620.0),
    ]
    observations = [
        _observation(
            physical_key=f"S2ACQ-scoped-{index}",
            product_id=f"scoped-{index}", timestamp=timestamp,
            content=f"scoped-content-{index}", ndvi=ndvi,
            season_phase=phase, gdd_accumulated=gdd,
            calibration_domain=(
                "incompatible" if index < 3 else "compatible"
            ),
        )
        for index, (timestamp, ndvi, phase, gdd) in enumerate(rows)
    ]
    ledger = CropEvidenceLedgerV2.from_observations(NAMESPACE, observations)
    _, receipt, segmentation = build_ledger_crop_feature_input(
        ledger=ledger, crop_cycle_hypothesis_id="unresolved-cycle",
        run_id="run-scoped",
    )
    readiness = segmentation.current_evidence_readiness

    assert readiness.observation_ids == tuple(
        observation.observation_id for observation in observations[-3:]
    )
    assert readiness.phase_coverage == ("late",)
    assert readiness.physical_acquisition_count == 3
    assert readiness.temporal_span_days == pytest.approx(20.0)
    assert readiness.gdd_spans == (("gdd_accumulated", 500.0, 620.0, 120.0, 3),)
    assert dict(readiness.sensor_counts) == {"sentinel2": 3}
    assert readiness.calibration_domain_compatibility == "compatible"
    assert receipt.phase_coverage == ("late",)
    assert receipt.domain_compatibility == "compatible"
    assert receipt.physical_evidence_sufficiency == "insufficient"


def test_sensor_specific_boundary_ignores_interleaved_sar_adjacency() -> None:
    def token(
        observation_id: str, sensing_time: str, source: str,
        ndvi: float | None = None,
    ) -> CropModelObservationTokenV1:
        return CropModelObservationTokenV1(
            observation_id=observation_id,
            observation_hash=f"hash-{observation_id}",
            physical_acquisition_key=f"physical-{observation_id}",
            source_family=source,
            sensing_time=sensing_time,
            feature_values=(
                (("ndvi", "mean", ndvi),) if ndvi is not None else ()
            ),
            quality_admitted=True,
            quality_class="good",
            support_hash=f"support-{observation_id}",
        )

    tokens = [
        token("s2-1", "2026-01-01T00:00:00+00:00", "sentinel2", 0.2),
        token("s2-2", "2026-01-10T00:00:00+00:00", "sentinel2", 0.4),
        token("s2-3", "2026-01-20T00:00:00+00:00", "sentinel2", 0.72),
        token("s1-between", "2026-02-20T00:00:00+00:00", "sentinel1"),
        token("s2-4", "2026-03-20T00:00:00+00:00", "sentinel2", 0.2),
        token("s2-5", "2026-03-30T00:00:00+00:00", "sentinel2", 0.4),
    ]
    candidates = _candidate_boundaries(
        tokens, long_gap_days=45.0, harvest_drop=0.25,
    )
    boundary = next(
        item for item in candidates if item.following_observation_id == "s2-4"
    )
    assert boundary.preceding_observation_id == "s2-3"
    assert boundary.sensor_family == "sentinel2"
    assert "long_optical_observation_gap" in boundary.reasons
    assert "harvest_like_optical_ndvi_drop" in boundary.reasons


def test_canonical_eo_posterior_is_invariant_to_unledgered_temporal_rows() -> None:
    timestamps = (
        "2026-06-01T10:00:00+00:00", "2026-06-08T10:00:00+00:00",
        "2026-06-15T10:00:00+00:00", "2026-06-22T10:00:00+00:00",
        "2026-06-29T10:00:00+00:00", "2026-07-06T10:00:00+00:00",
    )
    observations = [
        _observation(
            physical_key=f"S2ACQ-invariant-{index}",
            product_id=f"invariant-{index}",
            timestamp=timestamps[index],
            content=f"invariant-content-{index}",
            ndvi=value,
        )
        for index, value in enumerate((0.22, 0.31, 0.44, 0.58, 0.66, 0.61))
    ]
    ledger = CropEvidenceLedgerV2.from_observations(NAMESPACE, observations)
    operational = {
        "crop_evidence_ledger": ledger.to_dict(),
        "crop_evidence_ledger_hash": ledger.ledger_hash,
        "lat": 36.5,
        "lng": 2.9,
    }
    first = infer_crop_posterior(
        plot_id="plot-a", run_id="run-invariant",
        plot_timeseries=[
            {"date": "2026-01-01", "ndvi": 0.05},
            {"date": "2026-07-01", "ndvi": 0.95},
        ],
        crop_config={"crop_cycle_id": "cycle-invariant"},
        operational_context=operational,
    )
    second = infer_crop_posterior(
        plot_id="plot-a", run_id="run-invariant",
        plot_timeseries=[
            {"date": "2025-01-01", "ndvi": 0.9, "vv_db": -2.0},
            {"date": "2025-02-01", "ndvi": 0.1, "vh_db": -30.0},
            {"date": "2025-03-01", "ndvi": 0.9},
        ],
        crop_config={"crop_cycle_id": "cycle-invariant"},
        operational_context=operational,
    )

    for key in (
        "model_context_group_posterior", "crop_group_posterior",
        "species_ranking", "engine_evidence", "evidence_quality",
        "crop_model_input_receipt_hash",
        "crop_cycle_segmentation_receipt_hash", "lineage_id", "content_hash",
    ):
        assert first[key] == second[key]
    assert first["observational_input_policy"][
        "generic_plot_timeseries_consumed"
    ] is False


def test_canonical_eo_posterior_rejects_cross_plot_ledger_replay() -> None:
    observations = [
        _observation(
            physical_key="S2ACQ-namespace",
            product_id="namespace-product",
            timestamp="2026-06-01T10:00:00+00:00",
            content="namespace-content",
            ndvi=0.42,
        )
    ]
    ledger = CropEvidenceLedgerV2.from_observations(NAMESPACE, observations)

    with pytest.raises(ValueError, match="plot namespace mismatch"):
        infer_crop_posterior(
            plot_id="different-plot",
            run_id="run-namespace-mismatch",
            plot_timeseries=[],
            operational_context={
                "crop_evidence_ledger": ledger.to_dict(),
                "crop_evidence_ledger_hash": ledger.ledger_hash,
            },
        )


def test_phenology_rates_use_calendar_days_and_expose_gdd_coordinates() -> None:
    values = [0.1, 0.2, 0.5, 0.8, 0.7, 0.4, 0.2]
    dates = [
        "2026-01-01", "2026-01-02", "2026-01-10", "2026-01-20",
        "2026-02-01", "2026-02-15", "2026-03-01",
    ]
    gdd = [0, 5, 50, 140, 230, 330, 410]
    feature = extract_phenology_features(values, dates, gdd_series=gdd)
    assert feature.growth_rate is None or abs(feature.growth_rate) < 0.1
    if feature.pos_gdd is not None:
        assert feature.pos_gdd in gdd
        assert feature.growth_rate_per_gdd is not None


def test_sar_features_never_mix_orbit_tracks_and_use_elapsed_days() -> None:
    dates = ["2026-01-01", "2026-01-02", "2026-01-10", "2026-01-20", "2026-02-01"]
    rows = [
        {
            "date": date, "vv": -12.0 + index, "vh": -18.0,
            "backscatter_unit": "db", "orbit_direction": "ASCENDING",
            "relative_orbit": "R108",
        }
        for index, date in enumerate(dates)
    ]
    rows.extend([
        {
            "date": "2026-01-03", "vv": -2.0, "vh": -3.0,
            "backscatter_unit": "db", "orbit_direction": "DESCENDING",
            "relative_orbit": "R022",
        },
        {
            "date": "2026-01-09", "vv": -1.0, "vh": -2.0,
            "backscatter_unit": "db", "orbit_direction": "DESCENDING",
            "relative_orbit": "R022",
        },
    ])
    feature = extract_sar_temporal_features(rows)
    assert feature.n_observations == 5
    assert feature.vv_mean_db == pytest.approx(-10.0)
    assert any("sar_single_orbit_track_selected:ASCENDING:R108:excluded=2" in warning for warning in feature.extraction_warnings)
    assert feature.vv_rolling_median_slope is not None
    assert abs(feature.vv_rolling_median_slope) < 0.2


class _StaticModel:
    def __init__(self, classes: list[str], probabilities: list[float]):
        self.classes_ = np.asarray(classes)
        self._probabilities = np.asarray(probabilities, dtype=float)

    def predict_proba(self, values):
        return np.asarray([self._probabilities for _ in values])


def test_hierarchy_is_parent_conditioned_and_ambiguous_species_abstains() -> None:
    schema = crop_feature_schema_receipt()
    names = [feature.name for feature in schema.features]
    classifier = HierarchicalCropClassifier("unused")
    classifier.feature_names = names
    classifier.imputer = SimpleImputer(strategy="median").fit(
        np.zeros((2, len(names)), dtype=float)
    )
    classifier.models = {
        "L0": _StaticModel(["active_crop", "non_crop"], [0.9, 0.1]),
        "L1": _StaticModel(["annual", "orchard"], [0.9, 0.1]),
        "L2": _StaticModel(["winter_cereal", "evergreen_orchard"], [0.4, 0.6]),
        "L3": _StaticModel(["wheat", "barley", "olive"], [0.51, 0.49, 0.0]),
    }
    classifier.metadata = {
        "level_status": {level: "trained" for level in ("L0", "L1", "L2", "L3")},
        "feature_schema_hash": schema.content_hash,
        "calibration_modes": {level: "unavailable" for level in ("L0", "L1", "L2", "L3")},
    }
    classifier.production_eligible = False
    result = classifier.predict({
        "feature_vector_version": "6.0.0",
        "data_completeness": 1.0,
        "flat_features": {name: 0.0 for name in names},
    }, apply_constraints=True)
    levels = result["ml_classifier_output"]
    assert levels["L2"]["prediction"] == "winter_cereal"
    assert levels["L2"]["distribution"] == {"winter_cereal": 1.0}
    assert levels["L3"]["prediction"] is None
    assert levels["L3"]["reason"] == "high_entropy_l3"
    assert levels["L3"]["agronomic_filter"]["removed_candidates"] == []
    assert result["publication_eligible"] is False


def test_partial_label_round_trip_does_not_claim_species_support() -> None:
    label = CropLabel(
        label_id="label-a", plot_id="plot-a", geometry_hash="geometry-a",
        crop_code="unknown", crop_group="winter_cereal",
        label_source="official_parcel_label", label_confidence="HIGH",
        supported_hierarchy_levels=["L0", "L1", "L2"],
    )
    restored = CropLabel.from_dict(label.to_dict())
    assert restored.supported_hierarchy_levels == ["L0", "L1", "L2"]
    assert "L3" not in restored.supported_hierarchy_levels

from types import SimpleNamespace

from services.agribrain.common.downstream_crop_context import (
    resolve_downstream_crop_phenology,
)
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer2_veg_int.crop_posterior import (
    _scientific_content_hash,
)
from services.agribrain.layer8_prescriptive.runner import _semantic_authority
from services.agribrain.layer8_prescriptive.schema import Layer8Input
from services.agribrain.scientific_contracts.crop_governance import (
    CropModelReceiptV1,
)
from services.agribrain.scientific_contracts.crop_phenology import (
    CanonicalPhenologyPosteriorV2,
)


NAMESPACE = PlotNamespace("tenant-1", "farm-1", "plot-1")
CYCLE_ID = "cycle-1"


def _inputs(declared_crop="tomato"):
    return SimpleNamespace(
        plot_id=NAMESPACE.plot_id,
        plot_namespace=NAMESPACE,
        crop_config={
            "crop": declared_crop,
            "crop_cycle_id": CYCLE_ID,
        },
        crop_cycle_context={
            "plot_namespace": {
                "tenant_id": NAMESPACE.tenant_id,
                "farm_id": NAMESPACE.farm_id,
                "plot_id": NAMESPACE.plot_id,
            },
            "crop_cycle_id": CYCLE_ID,
            "declared_crop_code": declared_crop,
        },
    )


def _crop_posterior(**overrides):
    payload = {
        "contract_version": "crop_identity_posterior_v3",
        "plot_id": NAMESPACE.plot_id,
        "parent_run_id": "run-1",
        "pass": "PRE_ASMAE",
        "crop_cycle_identity": CYCLE_ID,
        "authority": "FARMER_CONFIRMED",
        "selected_identity": "tomato",
        "deepest_supported_level": "SPECIES",
        "species_probability_published": False,
        "species_posterior": {"tomato": 1.0},
        "crop_group_posterior": {"vegetable": 0.95, "unknown": 0.05},
    }
    payload.update(overrides)
    payload["content_hash"] = _scientific_content_hash(payload)
    return payload


def _phenology(crop_hash, *, authority="diagnostic"):
    return CanonicalPhenologyPosteriorV2(
        namespace=NAMESPACE,
        crop_cycle_id=CYCLE_ID,
        effective_at="2026-08-10T00:00:00+00:00",
        current_stage="REPRODUCTIVE",
        candidate_stage="REPRODUCTIVE",
        stage_posterior=(("REPRODUCTIVE", 0.8), ("UNKNOWN", 0.2)),
        authority=authority,
        stage_authority=authority,
        stage_confidence=0.8,
        calibration_status=(
            "temperature-scaled-v1" if authority == "calibrated"
            else "uncalibrated_hmm_viterbi"
        ),
        season_anchor_status="season_gdd_carried",
        crop_identity_posterior_hash=crop_hash,
        plant_date_status="confirmed",
        plant_date_min="2026-05-01",
        plant_date_max="2026-05-01",
        independent_evidence_count=2,
        evidence_observation_ids=("obs-1", "obs-2"),
    ).to_dict()


def _production_model_receipt():
    digest = "a" * 64
    return CropModelReceiptV1(
        model_family="temporal-multisensor-transformer",
        semantic_version="1.0.0",
        artifact_sha256=digest,
        feature_schema_version="crop-observation-v2",
        feature_schema_hash="b" * 64,
        class_hierarchy_version="crop-taxonomy-v2",
        training_dataset_manifest_hash="c" * 64,
        calibration_artifact_hash="d" * 64,
        validation_report_hash="e" * 64,
        region_domain_compatibility=(("dz-16", "approved"),),
        production_eligible=True,
        inference_device="cpu",
        runtime_version="python-3.13",
        deterministic_preprocessing_version="crop-preprocess-v2",
    )


def test_confirmed_species_can_condition_diagnostics_but_not_diagnostic_prescriptions():
    crop = _crop_posterior()
    result = resolve_downstream_crop_phenology(
        inputs=_inputs(),
        crop_posterior=crop,
        phenology_posterior=_phenology(crop["content_hash"]),
    )

    assert result.species_specific_allowed is True
    assert result.stage_specific_allowed is True
    assert result.crop_for_species_engine == "tomato"
    assert result.stage_for_discrete_engine == "REPRODUCTIVE"
    assert result.prescriptive_ready is False


def test_tampered_or_wrong_cycle_crop_posterior_fails_closed():
    tampered = _crop_posterior()
    tampered["selected_identity"] = "pepper"
    wrong_cycle = _crop_posterior(crop_cycle_identity="cycle-elsewhere")

    for payload in (tampered, wrong_cycle):
        result = resolve_downstream_crop_phenology(
            inputs=_inputs(), crop_posterior=payload
        )
        assert result.crop_resolution == "declared_only"
        assert result.selected_crop is None
        assert result.species_specific_allowed is False
        assert result.crop_posterior_hash == ""


def test_tampered_phenology_receipt_never_authorizes_stage():
    crop = _crop_posterior()
    phenology = _phenology(crop["content_hash"])
    phenology["current_stage"] = "VEGETATIVE"

    result = resolve_downstream_crop_phenology(
        inputs=_inputs(),
        crop_posterior=crop,
        phenology_posterior=phenology,
    )
    assert result.stage_specific_allowed is False
    assert result.phenology_stage == "UNKNOWN"
    assert result.phenology_posterior_hash == ""


def test_group_only_posterior_propagates_mixture_without_species_authority():
    crop = _crop_posterior(
        authority="MODEL_GROUP_POSTERIOR",
        selected_identity=None,
        deepest_supported_level="CROP_GROUP",
        species_posterior={},
        crop_group_posterior={"vegetable": 0.7, "orchard": 0.2, "unknown": 0.1},
        top_group="vegetable",
    )
    result = resolve_downstream_crop_phenology(
        inputs=_inputs(), crop_posterior=crop
    )

    assert result.crop_resolution == "group_only"
    assert result.selected_group == "vegetable"
    assert result.crop_mixture["vegetable"] == 0.7
    assert result.species_specific_allowed is False
    assert result.crop_for_species_engine == "unknown"


def test_only_artifact_bound_species_and_calibrated_stage_are_prescriptive_ready():
    receipt = _production_model_receipt()
    crop = _crop_posterior(
        authority="EO_SPECIES_CALIBRATED",
        calibrated=True,
        species_probability_published=True,
        ml_production_eligible=True,
        crop_model_receipt=receipt.to_dict(),
        crop_model_receipt_hash=receipt.content_hash,
    )
    result = resolve_downstream_crop_phenology(
        inputs=_inputs(),
        crop_posterior=crop,
        phenology_posterior=_phenology(
            crop["content_hash"], authority="calibrated"
        ),
    )

    assert result.species_specific_allowed is True
    assert result.stage_specific_allowed is True
    assert result.prescriptive_ready is True
    assert result.crop_posterior_hash == crop["content_hash"]
    assert len(result.phenology_posterior_hash) == 64


def test_calibrated_species_claim_without_bound_model_receipt_is_rejected():
    crop = _crop_posterior(
        authority="EO_SPECIES_CALIBRATED",
        calibrated=True,
        species_probability_published=True,
        ml_production_eligible=True,
    )
    result = resolve_downstream_crop_phenology(
        inputs=_inputs(), crop_posterior=crop
    )
    assert result.species_specific_allowed is False
    assert result.crop_resolution == "group_only"


def _l8_input(*, phenology_authority):
    return Layer8Input(
        diagnoses=[],
        nutrient_states={},
        bio_threats={},
        weather_forecast=[],
        zone_ids=["plot"],
        crop="tomato",
        crop_posterior_hash="a" * 64,
        phenology_posterior_hash="b" * 64,
        crop_resolution="species_confirmed",
        crop_authority="FARMER_CONFIRMED",
        phenology_authority=phenology_authority,
        species_specific_allowed=True,
        stage_specific_allowed=True,
        phenology_stage="REPRODUCTIVE",
    )


def test_layer8_requires_calibrated_stage_before_prescriptive_authority():
    species, stage, reasons = _semantic_authority(
        _l8_input(phenology_authority="diagnostic")
    )
    assert species is True
    assert stage is False
    assert "calibrated_stage_authority_required_for_prescription" in reasons

    species, stage, reasons = _semantic_authority(
        _l8_input(phenology_authority="calibrated")
    )
    assert species is True
    assert stage is True
    assert "calibrated_stage_authority_required_for_prescription" not in reasons


def test_layer3_plot_context_accepts_resolved_crop_authority_fields():
    from services.agribrain.layer3_decision.runner import _extract_plot_context

    inputs = _inputs()
    inputs.operational_context = {"irrigation_type": "drip"}
    inputs.policy_snapshot = {}

    context = _extract_plot_context(inputs)

    assert context.declared_crop_type == "tomato"
    assert context.crop_resolution == "declared_only"
    assert context.species_specific_allowed is False
    assert context.irrigation_type == "drip"

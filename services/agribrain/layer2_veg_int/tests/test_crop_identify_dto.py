from services.agribrain.app.crop_identify_dto import (
    CROP_IDENTIFY_DTO_VERSION,
    build_crop_identify_dto,
    normalize_crop_candidate,
)


def test_internal_species_ranking_is_normalized_from_registry():
    candidate = normalize_crop_candidate({
        "code": "wheat",
        "crop_group": "winter_cereal",
        "ranking_share": 0.052,
        "score": 0.948,
    })

    assert candidate["code"] == "wheat"
    assert candidate["name"] == "Wheat"
    assert candidate["name_ar"]
    assert candidate["architecture"] == "cereal"
    assert candidate["crop_group"] == "winter_cereal"
    assert candidate["ranking_share"] == 0.052
    assert candidate["score"] == 0.948
    assert "calibrated_probability" not in candidate
    assert "softmax_candidate_share" not in candidate


def test_public_dto_separates_declaration_group_support_and_species_confirmation():
    dto = build_crop_identify_dto({
        "authority": "REGISTRY_DECLARED",
        "declared_crop_normalized": "tomato",
        "top_group": "solanaceae_veg",
        "top_group_probability": 0.446,
        "crop_group_posterior": {
            "solanaceae_veg": 0.446,
            "unknown": 0.377,
        },
        "deepest_supported_level": "UNKNOWN",
        "calibration_status": "uncalibrated_group_mixture",
        "species_probability_published": False,
        "species_ranking": [{
            "code": "wheat",
            "crop_group": "winter_cereal",
            "ranking_share": 0.052,
            "score": 0.948,
        }],
    })

    assert dto["crop_identify_dto_version"] == CROP_IDENTIFY_DTO_VERSION
    assert dto["identity_authority"] == "REGISTRY_DECLARED"
    assert dto["declared_crop"]["code"] == "tomato"
    assert dto["top_crop"] == "tomato"
    assert dto["eo_group_support"] == {
        "available": False,
        "code": None,
        "label": None,
        "ranking_share": None,
        "calibrated": False,
        "calibration_status": "uncalibrated_model_context_ranking",
        "deepest_supported_level": "UNKNOWN",
        "status": "unavailable",
        "source_class": None,
        "admitted_physical_acquisition_count": 0,
        "admitted_ndvi_count": 0,
        "context_features_may_be_included": False,
    }
    assert dto["context_conditioned_group_ranking"] == {
        "available": True,
        "code": "solanaceae_veg",
        "label": "Solanaceae vegetables",
        "ranking_share": 0.446,
        "calibrated": False,
        "calibration_status": "uncalibrated_group_mixture",
        "includes_registry_declaration": True,
        "includes_temporal_prior": False,
        "role": "asmae_conditioning_not_independent_eo_evidence",
    }
    assert dto["independent_species_confirmation"]["available"] is False
    assert dto["candidates"][0]["name"] == "Wheat"
    assert dto["candidates"][0]["ranking_share"] == 0.052
    assert "registry declared" in dto["identity_summary"]
    assert "insufficient" in dto["identity_summary"]


def test_zero_observation_registry_declaration_is_never_labeled_eo_support():
    dto = build_crop_identify_dto({
        "authority": "REGISTRY_DECLARED",
        "declared_crop_normalized": "tomato",
        "top_group": "solanaceae_veg",
        "top_group_probability": 0.446,
        "crop_group_posterior": {
            "solanaceae_veg": 0.446,
            "unknown": 0.377,
        },
        "evidence_quality": {
            "admitted_record_count": 0,
            "admitted_ndvi_count": 0,
            "physical_acquisition_count": 0,
        },
        "model_context_group_posterior": {
            "solanaceae_veg": 0.50,
            "unknown": 0.50,
        },
        "model_context_support": {
            "status": "insufficient",
            "admitted_physical_acquisition_count": 0,
            "admitted_ndvi_count": 0,
            "registry_declaration_included": False,
            "temporal_prior_included": False,
            "context_features_may_be_included": True,
        },
        "species_probability_published": False,
    })

    assert dto["declared_crop"]["code"] == "tomato"
    assert dto["eo_group_support"]["available"] is False
    assert dto["eo_group_support"]["admitted_physical_acquisition_count"] == 0
    assert dto["context_conditioned_group_ranking"]["available"] is True
    assert dto["context_conditioned_group_ranking"][
        "includes_registry_declaration"
    ] is True


def test_admitted_declaration_free_model_context_can_publish_group_support():
    dto = build_crop_identify_dto({
        "authority": "REGISTRY_DECLARED",
        "declared_crop_normalized": "tomato",
        "top_group": "solanaceae_veg",
        "top_group_probability": 0.446,
        "crop_group_posterior": {"solanaceae_veg": 0.446, "unknown": 0.377},
        "model_context_group_posterior": {
            "solanaceae_veg": 0.61,
            "winter_cereal": 0.24,
            "unknown": 0.15,
        },
        "model_context_support": {
            "status": "available",
            "admitted_physical_acquisition_count": 4,
            "admitted_ndvi_count": 4,
            "registry_declaration_included": False,
            "temporal_prior_included": False,
            "context_features_may_be_included": True,
        },
        "species_probability_published": False,
    })

    assert dto["eo_group_support"]["available"] is True
    assert dto["eo_group_support"]["code"] == "solanaceae_veg"
    assert dto["eo_group_support"]["ranking_share"] == 0.61
    assert dto["eo_group_support"]["source_class"] == "model_context_eo_informed"
    assert dto["eo_group_support"]["calibrated"] is False


def test_unknown_candidate_has_stable_complete_shape():
    candidate = normalize_crop_candidate({
        "code": "unregistered_test_crop",
        "ranking_share": "0.12",
    })

    assert candidate["name"] == "Unregistered Test Crop"
    assert candidate["name_ar"] == ""
    assert candidate["architecture"] == "unknown"
    assert candidate["score"] == 0.0
    assert candidate["ranking_share"] == 0.12

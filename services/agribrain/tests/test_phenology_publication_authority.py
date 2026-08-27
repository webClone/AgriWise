from types import SimpleNamespace

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer10_sire.adapters.l2_adapter import adapt_l2
from services.agribrain.layer9_interface.engines.context_assembly import (
    ContextAssemblyEngine,
)
from services.agribrain.scientific_contracts.crop_phenology import (
    CanonicalPhenologyPosteriorV2,
    consume_canonical_phenology_output,
    normalize_published_phenology,
)


def _receipt(stage: str = "VEGETATIVE") -> dict:
    posterior = (
        ((stage, 0.8), ("UNKNOWN", 0.2))
        if stage != "UNKNOWN"
        else (("UNKNOWN", 1.0),)
    )
    return CanonicalPhenologyPosteriorV2(
        namespace=PlotNamespace("tenant-a", "farm-a", "plot-a"),
        crop_cycle_id="cycle-a",
        effective_at="2026-08-11T00:00:00+00:00",
        current_stage=stage,
        stage_posterior=posterior,
        authority="diagnostic" if stage != "UNKNOWN" else "unavailable",
        calibration_status="uncalibrated_hmm_viterbi",
        season_anchor_status="confirmed_plant_date",
        stage_confidence=0.8 if stage != "UNKNOWN" else 0.0,
        degradation_reasons=(
            () if stage != "UNKNOWN" else ("additional_independent_phenology_evidence_required",)
        ),
    ).to_dict()


def test_valid_layer2_receipt_is_the_only_known_stage_path():
    veg = SimpleNamespace(
        phenology=SimpleNamespace(
            canonical_posterior=_receipt(),
            stage_by_day=["HARVESTED"],
        )
    )

    result = consume_canonical_phenology_output(veg)

    assert result["resolved_crop_stage"] == "VEGETATIVE"
    assert result["phenology_authority"] == "diagnostic"
    assert result["phenology_receipt_valid"] is True
    assert len(result["phenology_posterior_hash"]) == 64


def test_phenology_receipt_binds_typed_crop_evidence_ledger_identity():
    ledger_identity = "CROPLEDGERV2-" + "a" * 64
    receipt = CanonicalPhenologyPosteriorV2(
        namespace=PlotNamespace("tenant-a", "farm-a", "plot-a"),
        crop_cycle_id="cycle-a",
        effective_at="2026-08-11T00:00:00+00:00",
        current_stage="UNKNOWN",
        stage_posterior=(("UNKNOWN", 1.0),),
        authority="unavailable",
        calibration_status="uncalibrated_hmm_viterbi",
        season_anchor_status="archive_weather_required",
        evidence_ledger_hash=ledger_identity,
    )

    assert receipt.evidence_ledger_hash == ledger_identity
    assert CanonicalPhenologyPosteriorV2.from_dict(
        receipt.to_dict()
    ).evidence_ledger_hash == ledger_identity

    with pytest.raises(ValueError, match="verified CropEvidenceLedgerV2"):
        CanonicalPhenologyPosteriorV2(
            namespace=PlotNamespace("tenant-a", "farm-a", "plot-a"),
            crop_cycle_id="cycle-a",
            effective_at="2026-08-11T00:00:00+00:00",
            current_stage="UNKNOWN",
            stage_posterior=(("UNKNOWN", 1.0),),
            authority="unavailable",
            calibration_status="uncalibrated_hmm_viterbi",
            season_anchor_status="archive_weather_required",
            evidence_ledger_hash="a" * 64,
        )


def test_raw_stage_array_and_tampered_receipt_are_demoted_to_unknown():
    raw_only = SimpleNamespace(
        phenology=SimpleNamespace(stage_by_day=["REPRODUCTIVE"])
    )
    assert consume_canonical_phenology_output(raw_only)["resolved_crop_stage"] == "UNKNOWN"

    tampered = _receipt()
    tampered["most_likely_stage"] = "REPRODUCTIVE"
    invalid = SimpleNamespace(
        phenology=SimpleNamespace(canonical_posterior=tampered)
    )
    result = consume_canonical_phenology_output(invalid)
    assert result["resolved_crop_stage"] == "UNKNOWN"
    assert result["phenology_evidence_needed_reason"] == "canonical_layer2_phenology_receipt_invalid"


def test_layer10_adapter_never_promotes_raw_stage_by_day():
    adapted = adapt_l2(
        SimpleNamespace(
            run_id="l2-raw",
            phenology=SimpleNamespace(stage_by_day=["REPRODUCTIVE"]),
        )
    )

    assert adapted.current_stage == "UNKNOWN"
    assert adapted.phenology_receipt_valid is False
    assert adapted.stage_progression == []


def test_publication_dto_demotes_legacy_stage_and_preserves_valid_unknown_receipt():
    stage, context = normalize_published_phenology(
        "REPRODUCTIVE",
        {
            "phenology_source": "layer2_legacy_phenology",
            "phenology_evidence_class": "legacy_l2_diagnostic",
        },
    )
    assert stage == "UNKNOWN"
    assert context["phenology_receipt_valid"] is False

    unknown_receipt = _receipt("UNKNOWN")
    stage, context = normalize_published_phenology(
        "UNKNOWN",
        {
            "phenology_source": "layer2_canonical_phenology",
            "phenology_authority": "unavailable",
            "phenology_evidence_class": "unavailable",
            "phenology_posterior_hash": unknown_receipt["content_hash"],
            "phenology_receipt_valid": True,
            "phenology_evidence_needed_reason": "additional_independent_phenology_evidence_required",
        },
    )
    assert stage == "UNKNOWN"
    assert context["phenology_receipt_valid"] is True
    assert context["phenology_posterior_hash"] == unknown_receipt["content_hash"]


def test_layer9_publishes_unknown_reason_instead_of_raw_stage():
    layer9_input, explanations = ContextAssemblyEngine().assemble(
        SimpleNamespace(plot_id="plot-a"),
        l2_output=SimpleNamespace(
            phenology=SimpleNamespace(stage_by_day=["REPRODUCTIVE"]),
            anomalies=[],
        ),
    )

    phenology = layer9_input.l2_vegetation_data
    assert phenology["stage"] == "UNKNOWN"
    assert phenology["phenology_receipt_valid"] is False
    assert any("Growth stage is UNKNOWN" in item["statement"] for item in explanations)

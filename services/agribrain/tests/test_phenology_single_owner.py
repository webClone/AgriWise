from types import SimpleNamespace

import pytest

from services.agribrain.app.pi_helpers import compute_phenology
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer2_veg_int.phenology_engine import PhenologyEngine
from services.agribrain.layer10_sire.runner import _resolve_phenology_context
from services.agribrain.orchestrator_v2.runner import (
    _derive_phenology_stage,
    _legacy_derive_phenology_stage_for_migration,
)
from services.agribrain.scientific_contracts.crop_phenology import (
    CanonicalPhenologyPosteriorV2,
)


def _posterior() -> CanonicalPhenologyPosteriorV2:
    return CanonicalPhenologyPosteriorV2(
        namespace=PlotNamespace("tenant-1", "farm-1", "plot-1"),
        crop_cycle_id="cycle-1",
        effective_at="2026-08-10T00:00:00+00:00",
        current_stage="REPRODUCTIVE",
        candidate_stage="REPRODUCTIVE",
        stage_posterior=(("REPRODUCTIVE", 0.7), ("UNKNOWN", 0.3)),
        authority="diagnostic",
        calibration_status="uncalibrated_hmm_viterbi",
        season_anchor_status="season_gdd_carried",
        plant_date_status="confirmed",
        plant_date_min="2026-05-01",
        plant_date_max="2026-05-01",
        independent_evidence_count=3,
        evidence_observation_ids=("obs-1", "obs-2", "obs-3"),
    )


def test_phenology_contract_is_hash_stable_and_tamper_evident():
    value = _posterior()
    restored = CanonicalPhenologyPosteriorV2.from_dict(value.to_dict())
    assert restored.content_hash == value.content_hash

    tampered = value.to_dict()
    tampered["most_likely_stage"] = "VEGETATIVE"
    with pytest.raises(ValueError, match="stage aliases disagree|content_hash mismatch"):
        CanonicalPhenologyPosteriorV2.from_dict(tampered)


def test_initial_gdd_is_added_to_window_gdd_inside_hmm():
    engine = PhenologyEngine()
    seen = []

    def record_gdd(_state, current_gdd, _priors):
        seen.append(current_gdd)
        return 0.0

    engine._gdd_gate_penalty = record_gdd
    engine.infer_daily_stages(
        modeled_ndvi=[0.5],
        velocity=[0.0],
        dates=["2026-08-10"],
        cumulative_gdd=[12.0],
        initial_gdd=500.0,
    )

    assert seen
    assert set(seen) == {512.0}


def test_phenology_confidence_has_no_floor_and_nested_contract_is_immutable():
    payload = _posterior().to_dict()
    payload.pop("content_hash")
    payload["stage_confidence"] = 0.12
    payload["planting_date_posterior"] = {
        "status": "interval", "range": {"lower": "2026-05-01"}
    }
    posterior = CanonicalPhenologyPosteriorV2.from_dict(payload)
    assert posterior.stage_confidence == pytest.approx(0.12)
    with pytest.raises(TypeError):
        posterior.planting_date_posterior["status"] = "confirmed"
    with pytest.raises(TypeError):
        posterior.planting_date_posterior["range"]["lower"] = "2026-05-02"


def test_orchestrator_consumes_canonical_layer2_stage_not_crop_status():
    phenology = SimpleNamespace(
        canonical_posterior=_posterior().to_dict(),
        stage_by_day=["BARE_SOIL"],
    )
    layer2 = SimpleNamespace(output=SimpleNamespace(phenology=phenology))
    inputs = SimpleNamespace(crop_config={"stage": "HARVESTED"})

    assert _derive_phenology_stage(layer2, inputs) == "REPRODUCTIVE"


def test_layer10_does_not_reinfer_stage_from_contradictory_ndvi():
    veg = SimpleNamespace(
        phenology=SimpleNamespace(canonical_posterior=_posterior().to_dict()),
        ndvi_records=[{"ndvi": 0.01}],
    )

    context = _resolve_phenology_context(veg, ndvi_surface_mean=0.01, crop="tomato")
    assert context["resolved_crop_stage"] == "REPRODUCTIVE"
    assert context["ndvi_source"] == "not_used_by_layer10"
    assert context["phenology_source"] == "layer2_canonical_phenology"


def test_tampered_or_legacy_layer2_stage_fails_closed_downstream():
    tampered = _posterior().to_dict()
    tampered["current_stage"] = "VEGETATIVE"
    veg = SimpleNamespace(
        phenology=SimpleNamespace(
            canonical_posterior=tampered,
            stage_by_day=["HARVESTED"],
        )
    )
    assert _resolve_phenology_context(veg)["resolved_crop_stage"] == "UNKNOWN"

    legacy_only = SimpleNamespace(
        output=SimpleNamespace(
            phenology=SimpleNamespace(stage_by_day=["HARVESTED"])
        )
    )
    assert _derive_phenology_stage(legacy_only, SimpleNamespace()) == "UNKNOWN"


def test_legacy_orchestrator_phenology_owner_is_hard_disabled():
    with pytest.raises(RuntimeError, match="canonical Layer 2 phenology receipt"):
        _legacy_derive_phenology_stage_for_migration(
            SimpleNamespace(),
            SimpleNamespace(crop_config={"stage": "FLOWERING"}),
        )


def test_plot_intelligence_never_converts_status_or_dap_to_stage():
    result = compute_phenology("2026-04-01", "FLOWERING", 0.83)

    assert result["stage"] == "UNKNOWN"
    assert result["administrative_status"] == "FLOWERING"
    assert result["scientific_authority"] is False

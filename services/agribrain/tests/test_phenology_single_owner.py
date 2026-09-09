from dataclasses import dataclass
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
from services.agribrain.orchestrator_v2.serialization import to_plain_data
from services.agribrain.scientific_contracts.crop_phenology import (
    CanonicalPhenologyPosteriorV2,
)
from services.agribrain.layer05_asmae.bma.physics_experts import (
    compute_physics_experts,
)
from services.agribrain.layer05_asmae.priors.coarse_context import (
    build_coarse_layer_outputs,
)
from services.agribrain.layer05_asmae.priors.layer2_vegetation_priors import (
    extract_layer2_priors,
)
from services.agribrain.layer05_asmae.runner import ASMAERunner


@dataclass
class SimpleNamespaceReceipt:
    phenology: CanonicalPhenologyPosteriorV2


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


def test_immutable_phenology_contract_serializes_without_pickle():
    payload = _posterior().to_dict()
    payload.pop("content_hash")
    payload["planting_date_posterior"] = {
        "status": "interval", "range": {"lower": "2026-05-01"}
    }
    posterior = CanonicalPhenologyPosteriorV2.from_dict(payload)

    serialized = to_plain_data(
        SimpleNamespaceReceipt(phenology=posterior)
    )

    assert serialized["phenology"]["planting_date_posterior"] == {
        "status": "interval", "range": {"lower": "2026-05-01"}
    }


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


@pytest.mark.parametrize("ndvi", [[], [0.31], [0.25, 0.62, 0.31]])
def test_generated_coarse_evidence_passes_worker_contract_without_phenology(ndvi):
    coarse = build_coarse_layer_outputs(
        SimpleNamespace(plot_timeseries=[{"ndvi": value} for value in ndvi], static={}),
        crop_context={},
        weather_records=[],
        management_events=[],
    )
    runner = ASMAERunner(config={"disable_job_recovery": True})
    fatal, _, _ = runner._validate_contracts({"coarse_layer_outputs": coarse})
    assert fatal == []
    prior = extract_layer2_priors(coarse, {}, {})
    assert prior["usable_as_prior"] is False
    assert prior["growth_position"] is None

    # Available metadata alone must still be rejected. Accepting renamed
    # evidence must not bypass the scientific-field or provenance checks.
    coarse["layer2_intelligence"] = {
        "status": "available",
        "source_layer": "layer1_coarse_temporal",
        "source_timestamp": "2026-09-04T00:00:00+00:00",
        "evidence": ["NDVI"],
        "trajectory_authority": "ndvi_shape_prior_only",
        "canonical_phenology_allowed": False,
    }
    fatal, _, _ = runner._validate_contracts({"coarse_layer_outputs": coarse})
    assert fatal == [
        "coarse_layer_outputs: No declared scientific field present: layer2_intelligence"
    ]
    coarse["layer2_intelligence"]["vigor"] = 0.4
    del coarse["layer2_intelligence"]["evidence"]
    fatal, _, _ = runner._validate_contracts({"coarse_layer_outputs": coarse})
    assert fatal == [
        "coarse_layer_outputs: Missing coarse prior proof field: layer2_intelligence.evidence"
    ]


def test_ndvi_trajectory_is_not_published_or_consumed_as_phenology():
    layer1 = SimpleNamespace(
        plot_timeseries=[
            {"ndvi": 0.25},
            {"ndvi": 0.62},
            {"ndvi": 0.31},
        ],
        static={},
    )
    coarse = build_coarse_layer_outputs(
        layer1,
        crop_context={},
        weather_records=[],
        management_events=[],
    )
    trajectory = coarse["layer2_intelligence"]
    assert trajectory["ndvi_trajectory_phase"] == "declining"
    assert trajectory["canonical_phenology_allowed"] is False
    assert "phenology_stage" not in trajectory
    assert "growth_position" not in trajectory

    # Old cached aliases must also fail closed when canonical authority is
    # absent; they cannot revive the former hidden senescence prior.
    trajectory.update({
        "phenology_stage": "senescence",
        "growth_position": 0.9,
    })
    prior = extract_layer2_priors(
        coarse,
        {},
        {
            "current_stage": "UNKNOWN",
            "stage_authority": "unavailable",
            "season_progress": {"mean": None, "status": "unknown"},
        },
    )
    assert prior["phenology_stage"] == "UNKNOWN"
    assert prior["usable_as_prior"] is False
    assert prior["growth_position"] is None
    assert prior["ndvi_trajectory_used_as_phenology"] is False

    experts = compute_physics_experts(
        {"zone-a": [0.4] * 13},
        {
            "plot_timeseries": layer1.plot_timeseries,
            "phenology_posterior": {
                "current_stage": "UNKNOWN",
                "stage_authority": "unavailable",
            },
        },
    )
    assert "phenology_memory" not in experts


def test_canonical_phenology_can_authorize_position_prior():
    prior = extract_layer2_priors(
        {"layer2_intelligence": {
            "status": "available",
            "ndvi_trajectory_phase": "plateau",
            "ndvi_trajectory_position": 0.7,
        }},
        {},
        {
            "current_stage": "REPRODUCTIVE",
            "stage_authority": "diagnostic",
            "stage_confidence": 0.7,
            "season_progress": {"mean": 0.58, "status": "estimated"},
            "content_hash": "phenology-hash-a",
        },
    )
    assert prior["usable_as_prior"] is True
    assert prior["growth_position"] == pytest.approx(0.58)
    assert prior["phenology_authority"] == "diagnostic"
    assert prior["ndvi_trajectory_used_as_phenology"] is False

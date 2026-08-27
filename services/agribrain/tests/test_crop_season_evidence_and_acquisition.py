from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.scientific_contracts.crop_season_evidence import (
    CropActiveAcquisitionPlanV1,
    CropSeasonEvidenceReceiptV1,
    build_crop_active_acquisition_plan,
    build_crop_season_evidence_receipt,
)
from services.agribrain.scientific_contracts.crop_evidence import (
    CropEvidenceLedgerV2,
)


NS = PlotNamespace("tenant-a", "farm-a", "plot-a")
AS_OF = datetime(2026, 7, 1, tzinfo=timezone.utc)
LEDGER_HASH = "CROPLEDGERV2-" + "a" * 64


def _observation(
    observation_id: str,
    day: int,
    physical_key: str,
    *,
    family: str = "sentinel2",
    cloud: float = 0.1,
    red_edge: bool = True,
):
    return {
        "observation_id": observation_id,
        "sensing_time": (AS_OF + timedelta(days=day)).isoformat(),
        "physical_acquisition_key": physical_key,
        "source_family": family,
        "admission_status": "admitted",
        "direct_observation": True,
        "independent_evidence": True,
        "is_observed": True,
        "valid_fraction": 0.9,
        "cloud_fraction": cloud,
        "spectral_summary": {"ndre": {"mean": 0.2}} if red_edge else {"ndvi": {"mean": 0.5}},
    }


def _weather(day: int):
    return {
        "date": (AS_OF + timedelta(days=day)).date().isoformat(),
        "tmean": 24.0,
        "rain": 0.0,
    }


def _receipt(observations=(), weather=(), context=None):
    return build_crop_season_evidence_receipt(
        namespace=NS,
        observations=list(observations),
        source_evidence_ledger_hash=LEDGER_HASH,
        weather_records=list(weather),
        crop_cycle_context=context
        or {
            "crop_cycle_id": "cycle-a",
            "plant_date_status": "confirmed",
            "plant_date_nominal": "2026-03-01T00:00:00Z",
            "effective_at": "2026-02-20T00:00:00Z",
        },
        as_of=AS_OF,
        model_domain_compatible=False,
    )


def test_as_of_excludes_future_observations_and_weather_from_all_counts():
    receipt = _receipt(
        observations=[
            _observation("past", -10, "physical-past"),
            _observation("future", 1, "physical-future"),
        ],
        weather=[_weather(-1), _weather(1)],
    )

    assert receipt.independent_observation_ids == ("past",)
    assert receipt.independent_acquisition_count == 1
    assert receipt.excluded_future_observation_ids == ("future",)
    assert receipt.weather_available_day_count == 1
    assert receipt.excluded_future_weather_dates == ("2026-07-02",)
    assert receipt.backtest_safe is True


def test_processing_duplicates_count_once_and_selection_is_order_independent():
    cloudy = _observation("reprocess-cloudy", -20, "same-physical", cloud=0.8)
    clear = _observation("reprocess-clear", -20, "same-physical", cloud=0.05)
    radar = _observation(
        "radar", -5, "radar-physical", family="sentinel1", red_edge=False
    )

    forward = _receipt([cloudy, clear, radar])
    reverse = _receipt([radar, clear, cloudy])

    assert forward.independent_acquisition_count == 2
    assert forward.independent_observation_ids == ("radar", "reprocess-clear")
    assert forward.duplicate_observation_ids == ("reprocess-cloudy",)
    assert forward.content_hash == reverse.content_hash

    restored = CropSeasonEvidenceReceiptV1.from_dict(forward.to_dict())
    assert restored.content_hash == forward.content_hash
    tampered = forward.to_dict()
    tampered["archive_completeness"] = 0.99
    with pytest.raises(ValueError, match="content_hash mismatch"):
        CropSeasonEvidenceReceiptV1.from_dict(tampered)


def test_unknown_planting_date_stays_unknown_and_requests_a_range():
    receipt = _receipt(
        observations=[_observation("recent-s2", -3, "s2-recent")],
        context={
            "crop_cycle_id": "cycle-unknown",
            "plant_date_status": "unknown",
            "plant_date_nominal": None,
            "effective_at": "2026-01-01T00:00:00Z",
        },
    )
    plan = build_crop_active_acquisition_plan(receipt=receipt)

    assert receipt.plant_date_status == "unknown"
    assert receipt.season_window_status == "latent_unanchored"
    assert receipt.phenology_sufficient is False
    action_types = [action.action_type for action in plan.actions]
    assert "confirm_planting_date_range" in action_types
    assert "archive_retrieval" in action_types
    assert "field_photo" in action_types
    assert all(
        action.information_gain_status == "estimated" for action in plan.actions
    )


def test_planner_selects_lowest_cloud_s2_opportunity_and_marks_eig_estimated():
    receipt = _receipt([])
    plan = build_crop_active_acquisition_plan(
        receipt=receipt,
        crop_posterior={
            "l3_species_posterior": {"tomato": 0.55, "pepper": 0.45},
            "calibrated": False,
        },
        opportunities=[
            {
                "source_family": "sentinel2",
                "start": "2026-07-06T10:00:00Z",
                "end": "2026-07-06T11:00:00Z",
                "cloud_probability": 0.7,
            },
            {
                "source_family": "sentinel2",
                "start": "2026-07-08T10:00:00Z",
                "end": "2026-07-08T11:00:00Z",
                "cloud_probability": 0.08,
            },
        ],
    )

    s2 = next(action for action in plan.actions if action.action_type == "sentinel2_red_edge")
    assert s2.cloud_probability == pytest.approx(0.08)
    assert s2.availability_start == "2026-07-08T10:00:00Z"
    assert s2.information_gain_status == "estimated"
    assert plan.entropy_status == "estimated"
    assert plan.planner_authority == "diagnostic_estimated_utility"

    round_trip = CropActiveAcquisitionPlanV1.from_dict(plan.to_dict())
    assert round_trip.content_hash == plan.content_hash


def test_calibrated_labels_require_explicit_receipts():
    receipt = _receipt([])
    plan = build_crop_active_acquisition_plan(
        receipt=receipt,
        crop_posterior={
            "l3_species_posterior": {"tomato": 0.8, "pepper": 0.2},
            "calibrated": True,
            "calibration_receipt_id": "CAL-POSTERIOR-1",
        },
        eig_calibration_receipt_id="CAL-EIG-1",
    )

    assert plan.entropy_status == "calibrated"
    assert all(
        action.information_gain_status == "calibrated"
        and action.calibration_receipt_id == "CAL-EIG-1"
        for action in plan.actions
    )


def test_future_crop_context_cannot_anchor_historical_replay():
    receipt = _receipt(
        observations=[_observation("past", -2, "past-key")],
        context={
            "crop_cycle_id": "cycle-a",
            "plant_date_status": "confirmed",
            "plant_date_nominal": "2026-03-01T00:00:00Z",
            "effective_at": "2026-07-02T00:00:00Z",
        },
    )

    assert receipt.plant_date_status == "unknown"
    assert receipt.season_window_status == "latent_unanchored"


def test_layer2_integration_requires_and_binds_verified_evidence_ledger():
    from services.agribrain.layer2_veg_int.runner import (
        _build_crop_season_products,
    )

    ledger = CropEvidenceLedgerV2.from_observations(NS, [])
    ledger_payload = ledger.to_dict()
    orch_inputs = SimpleNamespace(
        plot_namespace=NS,
        crop_config={
            "crop_evidence_ledger": ledger_payload,
            "crop_evidence_ledger_hash": ledger.ledger_hash,
            "crop_posterior": {
                "deepest_publishable_level": "unavailable",
                "unknown_probability": 1.0,
            },
        },
        crop_cycle_context={
            "crop_cycle_id": "cycle-a",
            "plant_date_status": "unknown",
        },
        date_range={"start": "2026-06-01", "end": "2026-07-01"},
        operational_context={},
    )
    tensor = SimpleNamespace(
        plot_timeseries=[{"date": "2026-07-01", "tmean": 24.0}]
    )

    receipt, plan, error = _build_crop_season_products(
        orch_inputs,
        tensor,
        phenology_posterior={"current_stage": "UNKNOWN"},
    )

    assert error is None
    assert receipt["source_evidence_ledger_hash"] == ledger.ledger_hash
    assert receipt["independent_acquisition_count"] == 0
    assert receipt["species_sufficient"] is False
    assert plan["evidence_receipt_hash"] == receipt["content_hash"]
    assert plan["planner_authority"] == "diagnostic_estimated_utility"


def test_season_receipt_rejects_unbound_ledger_identity():
    with pytest.raises(ValueError, match="verified CropEvidenceLedgerV2"):
        build_crop_season_evidence_receipt(
            namespace=NS,
            observations=[],
            source_evidence_ledger_hash="unbound",
            as_of=AS_OF,
        )

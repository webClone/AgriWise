import pytest
from types import SimpleNamespace
from services.agribrain.orchestrator_v2.runner import _structured_output_status
from services.agribrain.orchestrator_v2.schema import LayerStatus
from services.agribrain.scientific_contracts.stage_receipt import (
    ExecutionStatus,
    ScientificUsability,
    StageReceipt,
)


def test_structured_output_status_none():
    status, errors = _structured_output_status(None)
    assert status == LayerStatus.DEGRADED
    assert "structured_output_missing" in errors


def test_structured_output_status_ok():
    out = SimpleNamespace(status="OK", run_id="RUN-123")
    status, errors = _structured_output_status(out)
    assert status == LayerStatus.OK
    assert errors == []


def test_structured_output_status_nested_run_meta():
    out = SimpleNamespace(
        run_meta=SimpleNamespace(run_id="L5-RUN", degradation_mode="DATA_GAP"),
        quality_metrics=SimpleNamespace(decision_reliability=0.8),
    )
    status, errors = _structured_output_status(out)
    assert status == LayerStatus.DEGRADED
    assert "structured_output_degraded" in errors


def test_structured_output_status_low_reliability():
    out = SimpleNamespace(
        run_id="L7-RUN",
        quality_metrics=SimpleNamespace(decision_reliability=0.35),
    )
    status, errors = _structured_output_status(out)
    assert status == LayerStatus.DEGRADED
    assert any("low_decision_reliability" in e for e in errors)


def test_structured_output_status_stage_receipt_failed():
    receipt = StageReceipt(
        stage_id="L10",
        execution_status=ExecutionStatus.FAILED,
        scientific_usability=ScientificUsability.UNUSABLE,
        degradation_reasons=("PHYSICS_FAILURE",),
    )
    out = SimpleNamespace(run_id="L10-RUN", stage_receipt=receipt)
    status, errors = _structured_output_status(out)
    assert status == LayerStatus.FAILED
    assert "structured_output_failed" in errors


def test_structured_output_status_stage_receipt_degraded():
    receipt = StageReceipt(
        stage_id="L10",
        execution_status=ExecutionStatus.SUCCESS,
        scientific_usability=ScientificUsability.DEGRADED,
        degradation_reasons=("FALLBACK_INTERPOLATION",),
    )
    out = SimpleNamespace(run_id="L10-RUN", stage_receipt=receipt)
    status, errors = _structured_output_status(out)
    assert status == LayerStatus.DEGRADED
    assert "structured_output_degraded" in errors

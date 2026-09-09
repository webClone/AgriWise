import pytest
from layer6_exec.schema import (
    ExecutionState,
    TaskStatus,
    InterventionCandidate,
    InterventionDomain,
    UpstreamDigest,
    OutcomeMetricId,
    CausalMethod,
)
from layer6_exec.execution.dag_runner import build_execution_state
from layer6_exec.evidence.normalizer import normalize_evidence_batch
from layer6_exec.outcomes.metrics import compute_outcomes, project_outcomes
from layer6_exec.engines.calibration import propose_calibration


@pytest.fixture
def sample_candidate():
    return InterventionCandidate(
        intervention_id="INV-IRR-001",
        domain=InterventionDomain.IRRIGATION,
        action_type="APPLY",
        title="Drip Irrigation Application",
        instructions="Apply 25mm via pivot",
        utility_score=0.85,
        expected_impact=0.75,
        urgency=0.80,
        confidence=0.90,
        timing_window={"start": "2026-04-05", "end": "2026-04-10"},
    )


def test_dag_state_machine_transitions(sample_candidate):
    """Verify that the DAG runner builds states and correctly transitions tasks."""
    # 1. Initial State: Candidate is ready (no dependencies)
    state_init = build_execution_state(
        portfolio=[sample_candidate],
        previous_state=ExecutionState(),
        evidence=[],
        current_time="2026-04-01T00:00:00Z",
    )
    assert state_init.tasks[sample_candidate.intervention_id] == TaskStatus.READY

    # 2. Add an evidence record indicating completion
    raw_evidence = [
        {
            "evidence_id": "EV-IRR-DONE",
            "type": "MACHINE_LOG",
            "source_refs": {"task_id": sample_candidate.intervention_id},
            "status": "COMPLETED",
            "recorded_at": "2026-04-05T12:00:00Z",
        }
    ]
    norm_evidence = normalize_evidence_batch(raw_evidence, plot_id="PLOT-01")
    state_completed = build_execution_state(
        portfolio=[sample_candidate],
        previous_state=state_init,
        evidence=norm_evidence,
        current_time="2026-04-06T00:00:00Z",
    )
    assert state_completed.tasks[sample_candidate.intervention_id] == TaskStatus.COMPLETED


def test_outcome_metrics_and_projections(sample_candidate):
    """Verify post-intervention causal outcome evaluation and forward projections."""
    # Synthetic timeseries around intervention date (2026-04-05)
    timeseries = [
        {"date": f"2026-04-{i:02d}", "ndvi_smoothed": 0.45 + 0.02 * i}
        for i in range(1, 16)
    ]
    outcomes = compute_outcomes(
        timeseries=timeseries,
        completed_interventions=[sample_candidate],
        confounders=["LOW_SOIL_N"],
    )

    assert len(outcomes) >= 2
    for om in outcomes:
        assert 0.0 <= om.confidence <= 1.0
        assert om.method in (CausalMethod.PRE_POST, CausalMethod.DIFF_IN_DIFF)
        assert isinstance(om.delta_value, float)

    # Projections
    projections = project_outcomes(
        portfolio=[sample_candidate],
        digest=UpstreamDigest(ndvi_current=0.55),
    )
    assert len(projections) == 1
    assert projections[0].intervention_id == sample_candidate.intervention_id
    assert projections[0].projected_ndvi_delta >= 0.0

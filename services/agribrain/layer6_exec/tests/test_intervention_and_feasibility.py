import pytest
from layer6_exec.schema import (
    UpstreamDigest,
    OperationalContext,
    InterventionDomain,
    FeasibilityGrade,
)
from layer6_exec.engines.intervention_synthesis import synthesize_interventions
from layer6_exec.engines.resource_feasibility import assess_feasibility


def test_intervention_synthesis_from_diagnoses():
    """Verify that active diagnoses from upstream generate appropriate intervention candidates."""
    digest = UpstreamDigest(
        active_diagnoses=[
            {
                "problem_id": "WATER_STRESS",
                "probability": 0.82,
                "severity": 0.75,
                "confidence": 0.88,
                "explain": "Severe root zone soil moisture depletion detected",
            }
        ],
        nutrient_deficiencies=[
            {
                "nutrient": "N",
                "probability_deficient": 0.70,
                "severity": 0.60,
                "recommended_kg_ha": 40.0,
            }
        ],
    )
    portfolio, conflict_log = synthesize_interventions(digest)
    
    assert len(portfolio) >= 1
    domains = {c.domain for c in portfolio}
    assert InterventionDomain.IRRIGATION in domains
    # Utilities must be positive
    for c in portfolio:
        assert c.utility_score > 0.0
        assert c.confidence > 0.0


def test_resource_feasibility_gating_unconstrained():
    """Verify that candidates pass with Grade A when all resources are abundant."""
    digest = UpstreamDigest(
        active_diagnoses=[
            {"problem_id": "WATER_STRESS", "probability": 0.8, "severity": 0.7, "confidence": 0.85}
        ]
    )
    portfolio, _ = synthesize_interventions(digest)
    
    op = OperationalContext(
        equipment_ids=["TRACTOR_1", "PIVOT_1"],
        workforce_available=True,
        labor_hours_available=80.0,
        water_quota_remaining=2000.0,
        budget_remaining=10000.0,
    )
    graded = assess_feasibility(portfolio, op, area_ha=10.0)
    
    assert len(graded) > 0
    assert graded[0].feasibility_grade in (FeasibilityGrade.A, FeasibilityGrade.B)
    assert len(graded[0].blocked_reasons) == 0


def test_resource_feasibility_gating_water_quota_exhausted():
    """Verify that exhausting the water quota demotes feasibility grade and appends blocked reasons."""
    digest = UpstreamDigest(
        active_diagnoses=[
            {"problem_id": "WATER_STRESS", "probability": 0.8, "severity": 0.7, "confidence": 0.85}
        ]
    )
    portfolio, _ = synthesize_interventions(digest)
    
    # 0 water quota remaining
    op = OperationalContext(
        water_quota_remaining=0.0,
        budget_remaining=5000.0,
        labor_hours_available=40.0,
    )
    graded = assess_feasibility(portfolio, op, area_ha=10.0)
    
    irrigation_candidate = next(c for c in graded if c.domain == InterventionDomain.IRRIGATION)
    assert irrigation_candidate.feasibility_grade in (FeasibilityGrade.C, FeasibilityGrade.D, FeasibilityGrade.F)
    assert len(irrigation_candidate.blocked_reasons) > 0
    assert any("Water quota" in r for r in irrigation_candidate.blocked_reasons)

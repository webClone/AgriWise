"""
Unit tests for Layer 9 Safety Gates and Hallucination Guard.
"""
import pytest
from layer9_interface.schema import (
    Layer9Input, PhrasingMode,
)
from layer9_interface.hallucination_guard import HallucinationGuard
from layer9_interface.engines.policy_enforcer import policy_enforcer


def test_hallucination_guard_ungrounded_numbers_and_dates():
    """Verify that HallucinationGuard catches ungrounded numbers and dates."""
    guard = HallucinationGuard(
        upstream_numbers={25.0, 50.0},
        upstream_dates={"2026-09-15"},
        upstream_zones={"zone_north", "zone_south"},
    )

    # 1. Ungrounded number: 180 kg/ha
    text_bad_num = "We recommend applying 180 kg/ha of fertilizer."
    _, flags_num = guard.validate(text_bad_num)
    assert any(f.claim_type == "number" and "180" in f.claim_value for f in flags_num)

    # 2. Grounded number: 25 kg/ha
    text_ok_num = "We recommend applying 25 kg/ha of fertilizer on 2026-09-15."
    _, flags_ok = guard.validate(text_ok_num)
    num_flags = [f for f in flags_ok if f.claim_type in ("number", "date")]
    assert len(num_flags) == 0

    # 3. Ungrounded date: 2026-10-01
    text_bad_date = "The next spray is planned for 2026-10-01."
    _, flags_date = guard.validate(text_bad_date)
    assert any(f.claim_type == "date" and f.claim_value == "2026-10-01" for f in flags_date)


def test_hallucination_guard_zones_and_physical_limits():
    """Verify zone validation and biophysical safety bounds (urea rate and anoxia waterlogging)."""
    guard = HallucinationGuard(
        upstream_numbers={20.0, 150.0},
        upstream_zones={"zone_north", "zone_south"},
        soil_moisture=40.0,  # Saturation condition (>= 38%)
    )

    # 1. Invalid zone
    text_bad_zone = "High stress detected in zone east."
    _, flags_zone = guard.validate(text_bad_zone)
    assert any(f.claim_type == "zone" and "east" in f.claim_value for f in flags_zone)

    # 2. Excessive urea application rate (> 200 kg/ha)
    text_excess_urea = "You should apply 250 kg/ha of urea fertilizer immediately."
    _, flags_urea = guard.validate(text_excess_urea)
    assert any(f.claim_type == "physical_constraint" and "200 kg/ha" in f.replacement for f in flags_urea)

    # 3. Over-irrigation on saturated soil (> 25 mm when soil_moisture >= 38%)
    text_excess_water = "Schedule an irrigation of 35 mm for the field today."
    _, flags_water = guard.validate(text_excess_water)
    assert any(f.claim_type == "physical_constraint" and "15 mm" in f.replacement for f in flags_water)


def test_policy_enforcer_phrasing_mode_and_gates():
    """Verify phrasing mode degradation and chemical / blocked / economic policy gates."""
    # 1. Phrasing modes
    assert policy_enforcer.assess_phrasing_mode("A") == PhrasingMode.CONFIDENT
    assert policy_enforcer.assess_phrasing_mode("B") == PhrasingMode.CONFIDENT
    assert policy_enforcer.assess_phrasing_mode("C") == PhrasingMode.HEDGED
    assert policy_enforcer.assess_phrasing_mode("D") == PhrasingMode.RESTRICTED
    assert policy_enforcer.assess_phrasing_mode("F") == PhrasingMode.RESTRICTED

    # 2. Invariant enforcement: chemical compliance and blocked actions
    l9_input = Layer9Input(
        audit_grade="C",
        source_reliability={"L1": 0.8},
        conflicts=[],
        diagnoses=[{"problem_id": "WEED_INFESTATION", "probability": 0.8, "severity": 0.7}],
        actions=[
            {
                "action_id": "ACT-001",
                "action_type": "SPRAY",
                "product_name": "unapproved_toxic_chemical_xyz",
                "is_allowed": True,
                "cost_per_ha": 50.0,
                "potential_yield_delta_pct": 10.0,
            },
            {
                "action_id": "ACT-002",
                "action_type": "TILL",
                "is_allowed": False,
            },
            {
                "action_id": "ACT-003",
                "action_type": "FERTILIZE",
                "is_allowed": True,
                "cost_per_ha": 400.0,
                "potential_yield_delta_pct": 0.5,  # Revenue gain = 4.2 * 0.005 * 320 = 6.72 EUR, net loss = 393.28 EUR
            },
        ],
        schedule=[],
        zone_plan={"zone_north": {}},
    )

    violations = policy_enforcer.enforce_invariants(l9_input)
    gates = [v.get("gate") for v in violations]
    assert "chemical_compliance" in gates
    assert "blocked_action" in gates
    assert "economic_roi_safety" in gates

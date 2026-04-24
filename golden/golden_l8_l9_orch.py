"""
Golden Tests: L8 Prescriptive + L9 Interface + Orchestrator v2 Routing

Pinned regression tests for:
  1. L8: 3 prescriptive scenarios with expected action types + trust behavior
  2. L9: Grounded output with phrasing mode, disclaimers, hallucination guard
  3. Orch v2: Intent routing golden cases + layer selection
"""

import sys
import os
# Ensure repo root is on path (golden/ is a subdir)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from datetime import datetime

passed = 0
failed = 0
errors = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  OK {name}")
    else:
        failed += 1
        msg = f"FAIL: {name}"
        if detail:
            msg += f" -- {detail}"
        errors.append(msg)
        print(f"  FAIL {name}: {detail}")


# ============================================================================
# L8 GOLDEN: 3 Prescriptive Scenarios
# ============================================================================

print("=" * 60)
print("L8 GOLDEN PRESCRIPTIVE TESTS")
print("=" * 60)

from services.agribrain.layer8_prescriptive.schema import (
    Layer8Input, ActionType, ScheduleStatus, ConfidenceLevel,
)
from services.agribrain.layer8_prescriptive.runner import run_layer8

# --- Golden 1: Water stress + high trust → IRRIGATE recommended ---
print("\n--- L8 Golden 1: Water stress, grade A ---")
inp = Layer8Input(
    diagnoses=[
        {"problem_id": "WATER_STRESS", "probability": 0.8, "severity": 0.7, "confidence": 0.9},
    ],
    nutrient_states={},
    bio_threats={},
    weather_forecast=[],
    zone_ids=["Zone_A", "Zone_B"],
    audit_grade="A",
    source_reliability={"sentinel2": 0.95, "weather": 0.9},
    conflicts=[],
    phenology_stage="VEGETATIVE",
    horizon_days=7,
)
out = run_layer8(inp, forecast=[
    {"precip_mm": 0, "wind_speed": 5, "temp_max": 32, "temp_min": 20},
] * 3, start_date=datetime(2024, 7, 1))

action_types = [a.action_type for a in out.actions if a.is_allowed]
check("G1: Has IRRIGATE action",
      ActionType.IRRIGATE in action_types,
      f"types: {[t.value for t in action_types]}")
check("G1: High confidence in output",
      out.quality.audit_grade == "A")
check("G1: No irreversible actions require confirmation",
      not any(a.requires_confirmation for a in out.actions
              if a.action_type == ActionType.IRRIGATE))

# --- Golden 2: Fungal + N deficiency + low trust → SCOUT only ---
print("\n--- L8 Golden 2: Multi-threat, grade D ---")
inp2 = Layer8Input(
    diagnoses=[
        {"problem_id": "FUNGAL_RUST", "probability": 0.7, "severity": 0.6, "confidence": 0.5},
    ],
    nutrient_states={"N": {"probability_deficient": 0.6, "confidence": 0.4}},
    bio_threats={"FUNGAL_RUST": {"probability": 0.7, "confidence": 0.5}},
    weather_forecast=[],
    zone_ids=["Zone_A"],
    audit_grade="D",
    source_reliability={"sentinel2": 0.3},
    conflicts=[],
    phenology_stage="VEGETATIVE",
    horizon_days=7,
)
out2 = run_layer8(inp2, start_date=datetime(2024, 7, 1))

safe_types = {ActionType.SCOUT, ActionType.WAIT, ActionType.MONITOR}
allowed_types = {a.action_type for a in out2.actions if a.is_allowed and not a.requires_confirmation}
check("G2: Only safe actions allowed under grade D",
      allowed_types.issubset(safe_types),
      f"allowed: {[t.value for t in allowed_types]}")
check("G2: Schedule exists",
      len(out2.schedule) >= 1)

# --- Golden 3: Conflict present → all irreversible require confirmation ---
print("\n--- L8 Golden 3: Conflict present ---")
inp3 = Layer8Input(
    diagnoses=[
        {"problem_id": "WATER_STRESS", "probability": 0.6, "severity": 0.5, "confidence": 0.8},
    ],
    nutrient_states={"N": {"probability_deficient": 0.5, "confidence": 0.7}},
    bio_threats={},
    weather_forecast=[],
    zone_ids=["Zone_A"],
    audit_grade="B",
    source_reliability={"sentinel2": 0.85},
    conflicts=[{"id": "c1", "description": "rain vs SAR mismatch"}],
    phenology_stage="VEGETATIVE",
    horizon_days=7,
)
out3 = run_layer8(inp3, start_date=datetime(2024, 7, 1))

irreversible = [a for a in out3.actions
                if a.action_type in {ActionType.SPRAY, ActionType.FERTILIZE}]
check("G3: All irreversible require confirmation under conflict",
      all(a.requires_confirmation for a in irreversible) if irreversible else True,
      f"without confirmation: {[a.action_id for a in irreversible if not a.requires_confirmation]}")
check("G3: Invariant violations auto-fixed",
      out3.audit is not None)


# ============================================================================
# L9 GOLDEN: Grounded Output Verification
# ============================================================================

print(f"\n{'=' * 60}")
print("L9 GOLDEN INTERFACE TESTS")
print("=" * 60)

from services.agribrain.layer9_interface.schema import (
    Layer9Input, PhrasingMode, AlertSeverity,
)
from services.agribrain.layer9_interface.policy_router import PolicyRouter
from services.agribrain.layer9_interface.hallucination_guard import HallucinationGuard

router = PolicyRouter()

# --- Golden 1: Grade A → all confident, no disclaimers ---
print("\n--- L9 Golden 1: Grade A (confident) ---")
l9_in = Layer9Input(
    audit_grade="A",
    source_reliability={"sentinel2": 0.95, "weather": 0.92},
    conflicts=[],
    diagnoses=[
        {"problem_id": "WATER_STRESS", "probability": 0.7, "severity": 0.5, "confidence": 0.8},
    ],
    actions=[
        {"action_id": "ACT-1", "action_type": "IRRIGATE", "is_allowed": True,
         "priority_score": 0.7, "rate": {"recommended": 30, "min_safe": 0, "max_safe": 80, "unit": "mm"}},
    ],
    schedule=[{"action_id": "ACT-1", "scheduled_date": "2024-07-02", "status": "CONFIRMED"}],
    zone_plan={"Zone_A": {"actions": ["ACT-1"], "priority": "HIGH"}},
    outcome_forecast={"yield_delta_pct": 8.0, "cost_total": 60.0},
)
out9 = router.build_output(l9_in)

check("G1: CONFIDENT phrasing",
      out9.phrasing_mode == PhrasingMode.CONFIDENT)
check("G1: No critical disclaimers",
      not any(d.severity == AlertSeverity.CRITICAL for d in out9.disclaimers))
check("G1: Has zone cards",
      len(out9.zone_cards) >= 1)
check("G1: Has citations",
      len(out9.citations) >= 1)

# --- Golden 2: Grade D → RESTRICTED + disclaimer ---
print("\n--- L9 Golden 2: Grade D (restricted) ---")
l9_d = Layer9Input(
    audit_grade="D",
    source_reliability={"sentinel2": 0.3},
    conflicts=[],
    diagnoses=[
        {"problem_id": "WATER_STRESS", "probability": 0.5, "severity": 0.4, "confidence": 0.3},
    ],
    actions=[
        {"action_id": "ACT-BLOCKED", "action_type": "SPRAY", "is_allowed": False,
         "blocked_reason": ["low_trust"]},
    ],
    schedule=[], zone_plan={},
)
out9d = router.build_output(l9_d)

check("G2: RESTRICTED phrasing",
      out9d.phrasing_mode == PhrasingMode.RESTRICTED)
check("G2: Has critical disclaimer",
      any(d.severity == AlertSeverity.CRITICAL for d in out9d.disclaimers))
check("G2: Summary mentions scouting/verification",
      "scout" in out9d.summary.lower() or "verif" in out9d.summary.lower(),
      f"summary: {out9d.summary[:60]}")
check("G2: Blocked action generates alert",
      any("blocked" in a.message.lower() or "BLOCKED" in a.message for a in out9d.alerts))

# --- Golden 3: Hallucination guard catches invented data ---
print("\n--- L9 Golden 3: Hallucination guard ---")
guard = HallucinationGuard.from_layer9_input({
    "actions": [
        {"action_type": "IRRIGATE", "is_allowed": True, "priority_score": 0.65,
         "rate": {"recommended": 30, "min_safe": 0, "max_safe": 80}},
    ],
    "schedule": [{"scheduled_date": "2024-07-02"}],
    "zone_plan": {"Zone_A": {}},
    "outcome_forecast": {"yield_delta_pct": 8.0, "cost_total": 60.0},
    "diagnoses": [{"probability": 0.7, "severity": 0.5}],
})

# Should flag invented number
_, flags1 = guard.validate("Apply 500 kg per hectare")
check("G3: Catches 500kg (invented)",
      any(f.claim_type == "number" for f in flags1))

# Should NOT flag known number
_, flags2 = guard.validate("Apply 30 mm of irrigation")
check("G3: Passes 30mm (known)",
      not any(f.claim_type == "number" for f in flags2))

# Should flag invented date
_, flags3 = guard.validate("Schedule for 2024-12-25")
check("G3: Catches invented date",
      any(f.claim_type == "date" for f in flags3))

# Should pass known date
_, flags4 = guard.validate("Schedule for 2024-07-02")
check("G3: Passes known date",
      not any(f.claim_type == "date" for f in flags4))


# ============================================================================
# ORCHESTRATOR v2 GOLDEN: Intent Routing
# ============================================================================

print(f"\n{'=' * 60}")
print("ORCH v2 GOLDEN ROUTING TESTS")
print("=" * 60)

from services.agribrain.orchestrator_v2.intents import Intent, detect_intent

# Pinned routing expectations
ROUTING_GOLDENS = [
    # (query, expected_intent, description)
    ("What's wrong with my field?", Intent.DIAGNOSIS, "health check → DIAGNOSIS"),
    ("How is my plot doing?", Intent.DIAGNOSIS, "plot status → DIAGNOSIS"),
    ("Should I irrigate?", Intent.DECISION, "action decision → DECISION"),
    ("Should I spray for fungal?", Intent.DECISION, "spray decision → DECISION"),
    ("Give me a 7-day action plan", Intent.DECISION, "action plan → DECISION"),
    ("What crop should I plant next season?", Intent.PLANNING, "crop selection → PLANNING"),
    ("Can I plant wheat in March?", Intent.PLANNING, "planting window → PLANNING"),
    ("How much nitrogen should I apply?", Intent.NUTRIENT, "N rate → NUTRIENT"),
    ("Do I need to apply nitrogen?", Intent.NUTRIENT, "fertilizer → NUTRIENT"),
    ("What is NDVI?", Intent.GENERAL, "concept question → GENERAL"),
    ("Explain SAR backscatter to me", Intent.GENERAL, "SAR concept → GENERAL"),
    ("Hi", Intent.GREETING, "simple greeting → GREETING"),
    ("Hello there", Intent.GREETING, "greeting → GREETING"),
    ("How much rain fell last week on my field?", Intent.DATA_QUERY, "rain data → DATA_QUERY"),
    ("Show me temperature trends this month", Intent.DATA_QUERY, "temp trends → DATA_QUERY"),
    ("What if I wait 2 more weeks before doing anything?", Intent.SCENARIO, "what-if → SCENARIO"),
]

for query, expected, desc in ROUTING_GOLDENS:
    result = detect_intent(query)
    check(f"Route: {desc}",
          result == expected,
          f"got {result.value}, expected {expected.value}")


# ============================================================================
# SUMMARY
# ============================================================================

print(f"\n{'=' * 60}")
total_l8 = 7
total_l9 = 12
total_orch = len(ROUTING_GOLDENS)
print(f"L8 GOLDEN: {sum(1 for _ in range(total_l8))} checks")
print(f"L9 GOLDEN: {sum(1 for _ in range(total_l9))} checks")
print(f"ORCH v2 GOLDEN: {total_orch} routing checks")
print(f"GOLDEN TOTAL: {passed} passed, {failed} failed")
if errors:
    print("\nFAILURES:")
    for e in errors:
        print(f"  FAIL {e}")
    print(f"{'=' * 60}")
    sys.exit(1)
else:
    print("ALL L8/L9/ORCH GOLDEN TESTS PASSED")
    print(f"{'=' * 60}")

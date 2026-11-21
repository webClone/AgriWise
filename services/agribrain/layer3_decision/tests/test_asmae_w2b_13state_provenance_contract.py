"""W2-B RED: executable Layer3 recommendation guard for all canonical states.

Exercise the exact guard from the current runner with independent context
objects. This targeted source-slice harness does not replace full engine tests.
"""
from pathlib import Path
from types import SimpleNamespace
import textwrap
import pytest
from services.agribrain.scientific_contracts.state_schema_ref import STATE_ORDER

_RUNNER = (Path(__file__).resolve().parents[2] / "layer3_decision" / "runner.py").read_text(
    encoding="utf-8"
)
_START = _RUNNER.index("        # Phase 3 Guard: ASMAE decision guarding")
_END = _RUNNER.index("        audit_log.append({", _START)
_GUARD = textwrap.dedent(_RUNNER[_START:_END])
assert len(STATE_ORDER) == 13


@pytest.mark.parametrize("state", STATE_ORDER)
@pytest.mark.parametrize("prefix", ["asmae_artifact:", "asmae_", "AsMaE_"])
def test_w2b_l3_all_13_canonical_states_are_recognized_in_provenance(state, prefix):
    evidence = f"{prefix}{state}"
    recommendation = SimpleNamespace(
        linked_diagnosis_ids=["nutrient"],
        is_allowed=True,
        blocked_reason=[],
        explain="independent-looking but ASMAE-only recommendation",
    )
    context = SimpleNamespace(
        asmae_features={},
        stress_detail={
            "nutrient": {
                "primary_driver": "unknown",
                "contributing_evidence_ids": [evidence],
            }
        },
    )
    scope = {"recommendations": [recommendation], "l3_context": context}
    exec(_GUARD, scope)
    assert recommendation.is_allowed is False, (
        f"Layer3 failed to recognize the ASMAE-only evidence {evidence}"
    )
    assert "asmae_alone_gated" in recommendation.blocked_reason

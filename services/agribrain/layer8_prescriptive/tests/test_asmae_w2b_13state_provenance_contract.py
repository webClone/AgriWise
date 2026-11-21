"""W2-B RED: Layer8 action cards recognize all 13 ASMAE source identities.

Executes the existing trust-adjustment provenance block with controlled
ActionCard-like objects. This is a bounded unit harness; the full Layer8
irreversible-action integration gate must follow implementation.
"""
from pathlib import Path
from types import SimpleNamespace
import textwrap
import pytest

from services.agribrain.scientific_contracts.state_schema_ref import STATE_ORDER

_SOURCE = (Path(__file__).resolve().parents[2] / "layer8_prescriptive" / "action_ranker.py").read_text(
    encoding="utf-8"
)
_START = _SOURCE.index("            # 1. Populating driver provenance")
_END = _SOURCE.index("            # 2. Irreversible ASMAE-driven action safety gates", _START)
_PROVENANCE_BODY = textwrap.dedent(_SOURCE[_START:_END])
_BLOCK = "for card in cards:\n" + textwrap.indent(_PROVENANCE_BODY, "    ")
assert len(STATE_ORDER) == 13


@pytest.mark.parametrize("state", STATE_ORDER)
@pytest.mark.parametrize("prefix", ["asmae_artifact:", "asmae_", "AsMaE_"])
def test_w2b_l8_all_13_states_bind_diagnostic_evidence_provenance(state, prefix):
    candidate = f"{prefix}{state}"
    canonical = f"ASMAE_{state.upper()}"
    feat = {
        "value": 0.4,
        "confidence": 0.95, "uncertainty": None,
        "state_update_allowed": False, "diagnostic_only": True,
        "asmae_channel": "diagnostic",
    }
    card = SimpleNamespace(
        evidence=[SimpleNamespace(reference_id=candidate, description="")],
        explain="diagnosis from an observation",
        driver_source_family="unknown",
        primary_driver=None,
        driver_confidence=None,
        driver_uncertainty=None,
        driver_channel=None,
        corroborating_sources=[],
    )
    l8_input = SimpleNamespace(asmae_features={canonical: feat})
    exec(_BLOCK, {"cards": [card], "l8_input": l8_input})
    assert card.driver_source_family == "asmae", (
        f"Layer8 lost ASMAE provenance for {candidate}"
    )
    assert isinstance(card.primary_driver, str)
    assert card.primary_driver.lower().endswith(state.lower()), (
        f"Layer8 assigned a different state to {candidate}: {card.primary_driver}"
    )


def test_w2b_l8_source_guard_does_not_manufacture_missing_sigma():
    # Source contract until the real irreversible-action integration tests
    # are written. Dict/object fallbacks must not imply sigma=0.1.
    trust_adjustment = _SOURCE[
        _SOURCE.index("    def _apply_trust_adjustments("):
    ]
    assert 'feat.get("uncertainty", 0.1)' not in trust_adjustment
    assert 'getattr(feat, "uncertainty", 0.1)' not in trust_adjustment

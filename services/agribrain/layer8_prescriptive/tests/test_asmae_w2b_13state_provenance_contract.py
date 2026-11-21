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



@pytest.mark.parametrize("action_name", ["IRRIGATE", "SPRAY", "FERTILIZE", "REPLANT"])
def test_w2b_irreversible_asmae_action_cannot_self_certify(action_name):
    from layer8_prescriptive.action_ranker import (
        ActionRankingEngine, ActionType, IRREVERSIBLE_ACTIONS,
    )
    kind = getattr(ActionType, action_name)
    assert kind in IRREVERSIBLE_ACTIONS
    card = SimpleNamespace(
        action_type=kind,
        evidence=[SimpleNamespace(reference_id="asmae_lai", description="")],
        explain="ASMAE LAI driven action",
        driver_source_family="unknown",
        primary_driver=None,
        driver_confidence=None,
        driver_uncertainty=None,
        driver_channel=None,
        corroborating_sources=[],
        is_allowed=True,
        blocked_reason=[],
        requires_confirmation=False,
        rate=None,
    )
    purported = {
        "value": 3.2, "confidence": 0.99, "uncertainty": 0.01,
        "bma_disagreement": 0.01, "resolution_m": 20.0,
        "state_update_allowed": True, "diagnostic_only": False,
        "asmae_channel": "state_evidence",
    }
    engine = object.__new__(ActionRankingEngine)
    l8_input = SimpleNamespace(conflicts=[], asmae_features={"ASMAE_LAI": purported})
    result = engine._apply_trust_adjustments([card], None, None, l8_input)
    assert result[0].driver_source_family == "asmae"
    assert result[0].is_allowed is False
    assert "blocked_by_asmae_safety_gate" in result[0].blocked_reason


def test_w2b_independent_non_asmae_action_is_not_globally_disabled():
    from layer8_prescriptive.action_ranker import ActionRankingEngine, ActionType
    card = SimpleNamespace(
        action_type=ActionType.SCOUT,
        evidence=[SimpleNamespace(reference_id="field_verified_soil_sample", description="")],
        explain="Independent soil test",
        driver_source_family="independent_lab",
        primary_driver=None, driver_confidence=0.8,
        driver_uncertainty=0.2, driver_channel="lab",
        corroborating_sources=[], is_allowed=True, blocked_reason=[],
        requires_confirmation=False, rate=None,
    )
    engine = object.__new__(ActionRankingEngine)
    result = engine._apply_trust_adjustments(
        [card], None, None, SimpleNamespace(conflicts=[], asmae_features={})
    )
    assert result[0].is_allowed is True

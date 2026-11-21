"""W3-A RED: exercise actual Layer10 nested diagnostic gates, not mock helpers.

A bounded executable source slice checks the existing runner policy branches.
After production remediation, keep end-to-end Layer10Output tests as a separate
acceptance gate for qualified masks, support and grid provenance.
"""
from pathlib import Path
from types import SimpleNamespace
import textwrap
import pytest

_FILE = Path(__file__).resolve().parents[1] / "runner.py"
_SOURCE = _FILE.read_text(encoding="utf-8")


def _extract(start_marker, end_marker):
    left = _SOURCE.index(start_marker)
    right = _SOURCE.index(end_marker, left)
    return textwrap.dedent(_SOURCE[left:right])


_GATE_SOURCE = _extract(
    "        def asmae_state_gate(t_upper: str):",
    "        def asmae_surface_gate(surface, t_upper: str):",
)
_IDENTITIES = _extract(
    "        def is_asmae_type(t: str) -> bool:",
    "        def asmae_family_gate(t_upper: str):",
)


def _call_state_gate(surface_type, *, spatial=True):
    scope = {
        "state_support_ledger": {},
        "current_spatial_asmae": spatial,
        "current_1m_allowed": False,
        "output": SimpleNamespace(
            asmae_proof={
                "retrovalidation_proof": {"real_holdout_count": 0},
                "bma_proof": {"production_bma_valid": False},
            },
            asmae_evidence_state={
                "spatial_raster_available": spatial,
                "visualization_allowed": spatial,
            },
        ),
    }
    exec(_GATE_SOURCE, scope)
    return scope["asmae_state_gate"](surface_type)


def test_w3a_posterior_concentration_uses_explicit_diagnostic_spatial_support():
    ok, reason = _call_state_gate("ASMAE_POSTERIOR_CONCENTRATION", spatial=True)
    assert ok is True, (
        "Posterior concentration should have an explicit spatial diagnostic "
        f"support family, not {reason!r}"
    )
    assert reason != "surface_state_requirement_unmapped"


def test_w3a_missing_spatial_posterior_still_blocks_concentration_render():
    ok, reason = _call_state_gate("ASMAE_POSTERIOR_CONCENTRATION", spatial=False)
    assert ok is False


def _route_composite_base(surface_type, *, policy="asmae_diagnostic"):
    scope = {
        "stype": surface_type,
        "stype_upper": surface_type.upper(),
        "p": policy,
        "s": SimpleNamespace(provenance={
            "visual_only": True, "state_update_allowed": False,
            "prescription_driver_allowed": False,
        }),
        "asmae_surface_gate": lambda *_: (True, ""),
        "non_asmae_auth": True,       # makes incorrect satellite fallback visible
        "non_asmae_kind": "full_raster",
        "non_asmae_reason": "ordinary_satellite",
        "asmae_authorized": False,
        "asmae_production_usable": False,
        "base_auth": False,
        "base_kind": "none",
        "base_reason": "default_denied",
    }
    exec(_IDENTITIES, scope)
    section = _SOURCE.index('                    # 1. Base Role')
    predicate = f'elif p == "{policy}":'
    start = _SOURCE.index('                    ' + predicate, section)
    end_marker = '                    elif p == "hybrid":' if policy == "asmae_diagnostic" else '                    base_auth, base_kind, base_reason = _apply_grid_gate('
    end = _SOURCE.index(end_marker, start + len(predicate))
    branch = textwrap.dedent(_SOURCE[start:end]).replace(
        predicate, predicate.replace('elif ', 'if ', 1), 1,
    )
    exec(branch, scope)
    return scope


@pytest.mark.parametrize("composite", [
    "COMPOSITE_ADVISORY_CANOPY",
    "COMPOSITE_UNCERTAINTY",
    "COMPOSITE_ARCHIVE_SUPPORT",
])
def test_w3a_composite_advisory_is_reachable_in_asmae_diagnostic_policy(composite):
    scope = _route_composite_base(composite)
    assert scope["is_composite_advisory_type"](composite) is True
    assert scope["base_kind"] == "diagnostic_overlay", (
        "A composite advisory must not fall through into an ordinary "
        f"full-raster satellite authorization: {scope['base_kind']!r}"
    )
    assert scope["base_reason"] == "composite_advisory_diagnostic_only_no_global_full_raster"


def test_w3a_composite_cannot_gain_production_raster_from_non_asmae_fallback():
    scope = _route_composite_base("COMPOSITE_EFFECTIVE_RESOLUTION")
    assert scope["base_kind"] != "full_raster"



@pytest.mark.parametrize("composite", [
    "COMPOSITE_ADVISORY_CANOPY",
    "COMPOSITE_CONFIDENCE",
    "COMPOSITE_EFFECTIVE_RESOLUTION",
])
def test_w3a_composite_advisory_is_reachable_in_hybrid_policy(composite):
    scope = _route_composite_base(composite, policy="hybrid")
    assert scope["base_kind"] == "diagnostic_overlay", (
        f"Hybrid policy lost composite advisory routing for {composite}"
    )
    assert scope["base_reason"] == "composite_advisory_diagnostic_only_no_global_full_raster"

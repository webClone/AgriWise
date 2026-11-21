"""W1-A negative controls: caller grants cannot override rollout, or shadow mode."""
import inspect
from pathlib import Path

import pytest

from services.agribrain.layer05_asmae.runner import (
    intersect_execution_permissions, ASMAERunner,
)
from services.agribrain.layer05_asmae.engine import production_mode_allowed


@pytest.mark.parametrize("mode", ["shadow", "quick_visual"])
def test_shadow_and_quick_visual_cannot_grant_production_even_if_registry_allows(mode):
    registry = {
        "compute_allowed": True,
        "production_authority_allowed": True,
        "training_export_allowed": True,
        "diagnostic_allowed": True,
        "permission_contract_version": "test_reg",
    }
    request = {"production_authority_allowed": True, "training_export_allowed": True}
    effective = intersect_execution_permissions(registry, request, mode)
    assert effective["compute_allowed"] is True
    assert effective["production_authority_allowed"] is False
    assert effective["training_export_allowed"] is False
    assert effective["permission_contract_version"] == "test_reg"
    assert production_mode_allowed(mode, effective) is False


@pytest.mark.parametrize("mode", ["standard", "scientific_refresh", "shadow"])
def test_request_cannot_promote_unregistered_plot(mode):
    registry = {"compute_allowed": True,
                "production_authority_allowed": False,
                "training_export_allowed": False,
                "visual_authority_allowed": True}
    attempted_escalation = dict(registry, production_authority_allowed=True,
                                training_export_allowed=True,
                                authority_phase="production",
                                permission_contract_version="forged")
    effective = intersect_execution_permissions(registry, attempted_escalation, mode)
    assert effective["production_authority_allowed"] is False
    assert effective["training_export_allowed"] is False
    assert "authority_phase" not in effective
    assert "permission_contract_version" not in effective
    assert production_mode_allowed(mode, effective) is False


def test_explicit_request_restrictions_can_only_downgrade():
    registry = {"compute_allowed": True,
                "diagnostic_allowed": True,
                "production_authority_allowed": True,
                "training_export_allowed": True}
    effective = intersect_execution_permissions(
        registry, {"compute_allowed": False, "training_export_allowed": False,
                   "production_authority_allowed": False}, "standard",
    )
    assert all(effective[k] is False for k in
               ("compute_allowed", "training_export_allowed", "production_authority_allowed"))


@pytest.mark.parametrize("mode", ["standard", "scientific_refresh"])
def test_genuine_registry_grant_remains_available_in_authorized_modes(mode):
    registry = {"compute_allowed": True,
                "production_authority_allowed": True,
                "training_export_allowed": True}
    effective = intersect_execution_permissions(registry, {}, mode)
    assert effective["production_authority_allowed"] is True
    assert production_mode_allowed(mode, effective) is True


def test_engine_output_uses_mode_gate_and_hardcoded_orchestrator_grant_is_gone():
    # AST-independent source control ensures the tested pure mode predicate is
    # in the actual final assembled-output path, not a disconnected helper.
    from services.agribrain.layer05_asmae import engine
    engine_source = inspect.getsource(engine.ASMAEEngine._assemble_output)
    assert "production_allowed = production_mode_allowed(inp.mode, permissions)" in engine_source
    assert 'diagnostics["state_update_allowed"] = final_production_usable' in engine_source
    assert 'diagnostics["layer1_export_allowed"] = final_production_usable' in engine_source

    root = Path(__file__).resolve().parents[2]
    orch_path = root / "orchestrator_v2" / "runner.py"
    text = orch_path.read_text(encoding="utf-8")
    segment = text[text.index('"orchestrator_reintegration": {'):][:500]
    assert '"production_authority_allowed": False' in segment
    assert '"training_export_allowed": False' in segment


def test_runner_effective_authority_uses_narrowing_resolver():
    runner_source = inspect.getsource(ASMAERunner.execute)
    assert "permissions = intersect_execution_permissions(" in runner_source
    assert 'context["_asmae_execution_permissions"] = permissions' in runner_source

"""Regression checks for the canonical backend package namespace."""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


CANONICAL_PREFIX = "services.agribrain"
LEGACY_SCIENTIFIC_ROOTS = {
    "common",
    "diagnostic_integration",
    "layer05_asmae",
    "scientific_contracts",
    "world_model",
}


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_scientific_tests_use_one_installed_namespace() -> None:
    tests_root = Path(__file__).resolve().parent
    violations: list[str] = []
    for path in sorted(tests_root.glob("test_*.py")):
        legacy = _import_roots(path) & LEGACY_SCIENTIFIC_ROOTS
        if legacy:
            violations.append(f"{path.name}: {', '.join(sorted(legacy))}")
    assert violations == [], "legacy backend imports found: " + "; ".join(violations)


def test_legacy_asmae_package_is_not_discoverable_or_loaded() -> None:
    sys.modules.pop("layer05_asmae", None)
    sys.modules.pop("layer05_asmae.cache", None)
    import services.agribrain.layer05_asmae.cache as canonical_cache

    assert canonical_cache.__name__.startswith(f"{CANONICAL_PREFIX}.")
    assert "layer05_asmae" not in sys.modules
    assert "layer05_asmae.cache" not in sys.modules
    assert "services.agribrain.layer05_asmae.cache" in sys.modules


def test_canonical_layer0_and_orchestrator_smoke_imports() -> None:
    from services.agribrain.layer0.wrappers import wrap_environment
    import services.agribrain.orchestrator_v2.runner as orchestrator_runner

    assert wrap_environment.__module__ == "services.agribrain.layer0.wrappers"
    assert orchestrator_runner.__name__ == "services.agribrain.orchestrator_v2.runner"
    assert orchestrator_runner.Layer10Input.__module__ == (
        "services.agribrain.layer10_sire.schema"
    )


def test_transitional_service_style_smoke_imports() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "services" / "agribrain")
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from layer0.wrappers import wrap_environment; "
                "import orchestrator_v2.runner as runner; "
                "assert runner.Layer10Input.__module__ == "
                "'services.agribrain.layer10_sire.schema'"
            ),
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr or probe.stdout

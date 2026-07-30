"""Layer 0 data-assimilation package.

The runner exports are loaded lazily so importing a leaf contract does not also
bootstrap the complete Layer 0 runtime.  This is important for package-style
imports such as ``services.agribrain.layer0.asmae_scene_products`` and removes
the former dependency on a synthetic ``PYTHONPATH=services/agribrain``.
"""

from __future__ import annotations

from typing import Any

__all__ = ["Layer0Runner", "Layer0RunnerInput", "Layer0RunnerOutput"]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(name)
    from .runner import Layer0Runner, Layer0RunnerInput, Layer0RunnerOutput

    exports = {
        "Layer0Runner": Layer0Runner,
        "Layer0RunnerInput": Layer0RunnerInput,
        "Layer0RunnerOutput": Layer0RunnerOutput,
    }
    return exports[name]

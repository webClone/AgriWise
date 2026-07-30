"""Scene-product contracts and provider loaders.

Provider clients are intentionally lazy: importing the immutable scene schema
must not initialize provider credentials or unrelated acquisition modules.
"""

from __future__ import annotations

from typing import Any

from .scene_product_schema import SceneProduct

__all__ = [
    "SceneProduct",
    "SceneProductStore",
    "fetch_asmae_s2_scene_stack",
    "fetch_asmae_s1_scene_stack",
    "fetch_experimental_composite_s2_stack",
    "fetch_experimental_composite_s1_stack",
]


def __getattr__(name: str) -> Any:
    if name == "SceneProductStore":
        from .scene_product_store import SceneProductStore

        return SceneProductStore
    if name == "fetch_asmae_s2_scene_stack":
        from .s2_real_scene_product_fetcher import fetch_asmae_s2_scene_stack

        return fetch_asmae_s2_scene_stack
    if name == "fetch_asmae_s1_scene_stack":
        from .s1_real_scene_product_fetcher import fetch_asmae_s1_scene_stack

        return fetch_asmae_s1_scene_stack
    if name in {
        "fetch_experimental_composite_s2_stack",
        "fetch_experimental_composite_s1_stack",
    }:
        from .experimental_composite_product_fetcher import (
            fetch_experimental_composite_s1_stack,
            fetch_experimental_composite_s2_stack,
        )

        exports = {
            "fetch_experimental_composite_s2_stack": fetch_experimental_composite_s2_stack,
            "fetch_experimental_composite_s1_stack": fetch_experimental_composite_s1_stack,
        }
        return exports[name]
    raise AttributeError(name)

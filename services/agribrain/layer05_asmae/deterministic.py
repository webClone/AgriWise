"""
V79A Phase 2: Deterministic utilities.

All stochastic ASMAE operations must be reproducible given the same inputs.

Rules:
  - NEVER use Python's built-in hash() — it is salted per process.
  - Use SHA-256 for stable, cross-platform deterministic seeds.
  - Every function that uses randomness accepts a `rng: random.Random` parameter.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Dict, List, Optional


def stable_seed(*parts: str) -> int:
    """Compute a deterministic seed from string parts using SHA-256.

    Unlike Python's hash(), this is stable across processes, platforms,
    and Python versions.

    Args:
        *parts: String components to hash (run_id, plot_id, geometry_hash, etc.)

    Returns:
        A 32-bit unsigned integer suitable for random.Random(seed).
    """
    raw = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def make_rng(
    run_id: str,
    plot_id: str,
    geometry_hash: str,
    model_version: str = "",
    extra: str = "",
) -> random.Random:
    """Create a deterministic Random instance for an ASMAE run.

    Same inputs → same RNG → same outputs (reproducibility).

    Args:
        run_id: Unique run identifier.
        plot_id: Plot identifier.
        geometry_hash: Geometry fingerprint.
        model_version: ASMAE model/config version.
        extra: Optional extra salt (e.g., step name).

    Returns:
        A seeded random.Random instance.
    """
    from .config import ASMAE_VERSION
    version = model_version or ASMAE_VERSION
    seed = stable_seed(run_id, plot_id, geometry_hash, version, extra)
    return random.Random(seed)


def hash_grid_dict(grid_dict: Dict[str, Any]) -> str:
    """Deterministic hash of a {name: 2D_grid} dict.

    Used for content-based output hashing (P0-9).
    Handles both {state_name: [[vals]]} and {mz_id: [vals]} formats.
    """
    if not grid_dict:
        return hashlib.sha256(b"empty").hexdigest()[:16]

    # Sort keys for determinism
    parts = []
    for key in sorted(grid_dict.keys()):
        val = grid_dict[key]
        if isinstance(val, list):
            # Flatten and round for stability
            flat = _flatten_to_floats(val)
            # Round to 6 decimals to avoid floating-point noise
            rounded = [round(v, 6) for v in flat]
            parts.append(f"{key}:{rounded}")
        else:
            parts.append(f"{key}:{val}")

    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def hash_weak_labels(labels: List[dict]) -> str:
    """Deterministic hash of weak label values."""
    if not labels:
        return hashlib.sha256(b"no_labels").hexdigest()[:16]

    # Hash the training weights and estimates (the scientific content)
    parts = []
    for label in sorted(labels, key=lambda l: (l.get("microzone_id", ""), l.get("state_name", ""))):
        parts.append(
            f"{label.get('microzone_id')}:{label.get('state_name')}:"
            f"{label.get('estimate', 0):.6f}:{label.get('training_weight', 0):.4f}"
        )

    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _flatten_to_floats(val: Any) -> List[float]:
    """Recursively flatten nested lists to a flat list of floats."""
    result: List[float] = []
    if isinstance(val, (int, float)):
        result.append(float(val))
    elif isinstance(val, (list, tuple)):
        for item in val:
            result.extend(_flatten_to_floats(item))
    return result

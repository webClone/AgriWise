"""Shared qualification of numeric evidence at scientific input boundaries."""

from __future__ import annotations

import math
from numbers import Real
from typing import Any, Optional


def finite_real(value: Any) -> Optional[float]:
    """Return a finite real scalar; do not coerce booleans or numeric strings.

    Zero is valid. Missing, malformed and non-finite evidence stays missing
    rather than becoming a physical zero or a clipped extreme state.
    """
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None

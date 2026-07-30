"""
Sentinel-1 Orbit Metadata.

Lightweight V1 — stores and validates orbit direction + relative orbit
for temporal consistency. No orbital mechanics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class OrbitInfo:
    """SAR orbit metadata for temporal compatibility checking."""

    orbit_direction: str = ""      # ASCENDING or DESCENDING
    relative_orbit: int = 0        # Repeat-track orbit number
    platform: str = ""             # S1A, S1C, etc.

    def validate(self) -> List[str]:
        """Return list of validation errors."""
        errors = []
        if self.orbit_direction not in ("ASCENDING", "DESCENDING"):
            errors.append(
                f"Invalid orbit_direction: '{self.orbit_direction}'. "
                "Must be ASCENDING or DESCENDING."
            )
        if self.relative_orbit <= 0:
            errors.append(
                f"Invalid relative_orbit: {self.relative_orbit}. Must be > 0."
            )
        if not self.platform:
            errors.append("Missing platform identifier.")
        return errors

    def is_compatible(self, other: OrbitInfo) -> bool:
        """
        Check if two orbit infos are compatible for temporal comparison.

        Compatible means: same orbit_direction + same relative_orbit.
        Platform can differ (S1A vs S1C).
        """
        return (
            self.orbit_direction == other.orbit_direction
            and self.relative_orbit == other.relative_orbit
        )

"""
Temporal Diff Engine.

Compares two successive MissionRecords and flags significant changes
in structural metrics.  Produces a list of TemporalChange objects with
direction (improved / worsened / stable) and significance grading.
"""

from dataclasses import dataclass
from typing import List

from .mission_history import MissionRecord


@dataclass
class TemporalChange:
    """A detected change between two mission runs."""
    metric: str                   # "canopy_cover", "weed_pressure", etc.
    previous_value: float
    current_value: float
    delta: float                  # current - previous (positive = increase)
    direction: str                # "improved", "worsened", "stable"
    significance: str             # "minor", "moderate", "severe"


# Per-metric thresholds: (minor, moderate, severe) for absolute delta
# Direction semantics: positive_is_good means an increase = improvement
_METRIC_CONFIG = {
    "canopy_cover": {
        "thresholds": (0.05, 0.15, 0.25),
        "positive_is_good": True,   # More canopy = healthier
    },
    "weed_pressure": {
        "thresholds": (0.03, 0.10, 0.20),
        "positive_is_good": False,  # More weeds = worse
    },
    "row_break_count": {
        "thresholds": (2, 5, 10),
        "positive_is_good": False,  # More breaks = worse
    },
    "tree_count": {
        "thresholds": (0, 1, 1),     # Any loss is severe
        "positive_is_good": True,
    },
    "missing_tree_count": {
        "thresholds": (0, 1, 2),     # Any increase is moderate+
        "positive_is_good": False,
    },
    "in_row_weed_fraction": {
        "thresholds": (0.02, 0.05, 0.10),
        "positive_is_good": False,
    },
    "inter_row_weed_fraction": {
        "thresholds": (0.03, 0.10, 0.20),
        "positive_is_good": False,
    },
    "canopy_uniformity_cv": {
        "thresholds": (0.05, 0.15, 0.30),
        "positive_is_good": False,  # Higher CV = less uniform = worse
    },
}


class TemporalDiffEngine:
    """Compares two mission records and flags significant changes."""

    def compare(self, current: MissionRecord, previous: MissionRecord) -> List[TemporalChange]:
        """Compare current vs previous mission and flag changes.
        
        Returns a list of TemporalChange objects, one per metric that changed.
        Metrics that are "stable" (delta within minor threshold) are still included.
        """
        changes = []

        for metric, config in _METRIC_CONFIG.items():
            cur_val = getattr(current, metric, 0.0)
            prev_val = getattr(previous, metric, 0.0)

            # Ensure numeric
            cur_val = float(cur_val) if cur_val is not None else 0.0
            prev_val = float(prev_val) if prev_val is not None else 0.0

            delta = cur_val - prev_val
            abs_delta = abs(delta)

            # Classify significance
            minor_t, mod_t, sev_t = config["thresholds"]
            if abs_delta >= sev_t:
                significance = "severe"
            elif abs_delta >= mod_t:
                significance = "moderate"
            elif abs_delta > minor_t:
                significance = "minor"
            else:
                significance = "stable"

            # Classify direction
            if significance == "stable":
                direction = "stable"
            else:
                positive_is_good = config["positive_is_good"]
                if delta > 0:
                    direction = "improved" if positive_is_good else "worsened"
                else:
                    direction = "worsened" if positive_is_good else "improved"

            changes.append(TemporalChange(
                metric=metric,
                previous_value=prev_val,
                current_value=cur_val,
                delta=delta,
                direction=direction,
                significance=significance,
            ))

        return changes

    def summary(self, changes: List[TemporalChange]) -> str:
        """Generate a human-readable summary of temporal changes."""
        non_stable = [c for c in changes if c.significance != "stable"]
        if not non_stable:
            return "No significant changes between missions."

        lines = []
        for c in sorted(non_stable, key=lambda x: ("severe", "moderate", "minor").index(x.significance)):
            arrow = "↑" if c.delta > 0 else "↓"
            lines.append(
                f"  {c.significance.upper()}: {c.metric} {c.previous_value:.3f} → "
                f"{c.current_value:.3f} ({arrow}{abs(c.delta):.3f}) [{c.direction}]"
            )
        return "\n".join(lines)

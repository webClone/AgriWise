"""
Zone Labeler — Attach semantic labels and link to upstream evidence/actions
"""
from typing import List, Optional, Tuple
from layer10_sire.schema import (
    Layer10Input, ZoneArtifact, ZoneFamily,
)


# ── Human-readable type nouns ─────────────────────────────────────────────────
_ZONE_NOUNS = {
    "LOW_VIGOR":        "low-vigor patch",
    "WATER_STRESS":     "water-stress zone",
    "NUTRIENT_RISK":    "nutrient-risk zone",
    "DISEASE_RISK":     "disease-pressure zone",
    "LOW_CONFIDENCE":   "low-confidence area",
}

_SEVERITY_ADJ = [
    (0.75, "severe"),
    (0.50, "moderate"),
    (0.25, "mild"),
    (0.0,  "low"),
]


def _spatial_anchor(centroid_r: float, centroid_c: float, H: int, W: int) -> str:
    """Map normalised centroid (0‥1) to a cardinal-region string."""
    v = centroid_r / max(1, H - 1)  # 0=North, 1=South
    h = centroid_c / max(1, W - 1)  # 0=West, 1=East

    ns = "North" if v < 0.35 else ("South" if v > 0.65 else "Central")
    ew = "west" if h < 0.35 else ("east" if h > 0.65 else "")
    return (ns + "-" + ew).rstrip("-") if ew else ns


def generate_human_label(zone: ZoneArtifact, H: int, W: int,
                         field_valid_cells: Optional[int] = None) -> str:
    """Produce a human-readable spatial label for a zone.

    Examples
    --------
    "North-central low-vigor patch"
    "South-east disease-pressure zone"
    "Field-wide low-confidence area"
    """
    cells = zone.cell_indices
    noun = _ZONE_NOUNS.get(zone.zone_type.value, "zone")

    # Field-wide check (>60 % of field footprint, not bbox)
    total = field_valid_cells if (field_valid_cells and field_valid_cells > 0) else H * W
    if total > 0 and len(cells) / total > 0.6:
        return f"Field-wide {noun}"

    if not cells:
        return zone.zone_type.value.replace("_", " ").lower()

    # Centroid
    cr = sum(r for r, _ in cells) / len(cells)
    cc = sum(c for _, c in cells) / len(cells)
    anchor = _spatial_anchor(cr, cc, H, W)

    # Severity adjective
    adj = "low"
    for threshold, label in _SEVERITY_ADJ:
        if zone.severity >= threshold:
            adj = label
            break

    return f"{anchor} {adj} {noun}"


def label_zones(
    zones: List[ZoneArtifact],
    inp: Layer10Input,
    H: int = 0,
    W: int = 0,
    field_valid_cells: Optional[int] = None,
) -> List[ZoneArtifact]:
    """Enrich zones with human labels, upstream linkage, and action references."""
    prescriptive = inp.prescriptive

    for zone in zones:
        # ── Human-readable spatial label ─────────────────────────────────────
        zone.label = generate_human_label(zone, H, W,
                                          field_valid_cells=field_valid_cells)
        # Keep description in sync with current (post-deconfliction) cell count
        zone.description = (
            f"{zone.zone_type.value}: {len(zone.cell_indices)} cells "
            f"({zone.area_pct * 100:.1f}% of field)"
        )

        # ── Link to L8 actions ───────────────────────────────────────────────
        if prescriptive is not None and zone.zone_family == ZoneFamily.AGRONOMIC:
            actions = getattr(prescriptive, 'actions', [])
            for act in actions:
                act_type = getattr(act, 'action_type', None)
                if act_type is not None:
                    at_val = act_type.value if hasattr(act_type, 'value') else str(act_type)
                    if 'WATER' in zone.zone_type.value and 'IRRIGAT' in at_val:
                        zone.linked_actions.append(getattr(act, 'action_id', ''))
                    elif 'NUTRIENT' in zone.zone_type.value and 'FERTILIZ' in at_val:
                        zone.linked_actions.append(getattr(act, 'action_id', ''))
                    elif 'DISEASE' in zone.zone_type.value and 'SPRAY' in at_val:
                        zone.linked_actions.append(getattr(act, 'action_id', ''))

        # ── Link to L3 diagnoses ─────────────────────────────────────────────
        decision = inp.decision
        if decision is not None:
            for dx in getattr(decision, 'diagnoses', []):
                pid = getattr(dx, 'problem_id', '')
                prob = getattr(dx, 'probability', 0.0)
                zone.linked_findings.append({
                    "source": "L3",
                    "problem_id": pid,
                    "probability": prob,
                })

    return zones

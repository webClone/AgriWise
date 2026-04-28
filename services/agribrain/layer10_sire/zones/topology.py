"""
Zone Topology Validator — Ensures zone integrity invariants
"""
from typing import List
from layer10_sire.schema import ZoneArtifact


def validate_topology(zones: List[ZoneArtifact]) -> bool:
    """
    Validate zone topology invariants.
    Returns True if all valid, False if violations found.

    Checks:
      - No overlapping cells within the same ZoneFamily
      - All zones have area > 0
      - All zones have confidence in [0, 1]
    """
    # Group by family
    family_cells = {}
    violations = []

    for z in zones:
        fam = z.zone_family.value
        if fam not in family_cells:
            family_cells[fam] = set()

        for cell in z.cell_indices:
            key = (cell[0], cell[1])
            if key in family_cells[fam]:
                violations.append(f"Overlap in {fam}: {z.zone_id} at {key}")
            family_cells[fam].add(key)

        if z.area_m2 <= 0:
            violations.append(f"Zone {z.zone_id} has area <= 0")
        if z.confidence < 0 or z.confidence > 1:
            violations.append(f"Zone {z.zone_id} confidence {z.confidence} out of [0,1]")

    return len(violations) == 0

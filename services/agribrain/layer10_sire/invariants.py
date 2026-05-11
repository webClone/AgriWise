"""
Layer 10 Invariants — Runtime Safety Checks
=============================================

Enforced after every L10 run. Violations → warning + quality degradation.
"""

from typing import List
from layer10_sire.schema import (
    Layer10Output, SurfaceArtifact, ZoneArtifact, SurfaceType,
    ZoneFamily, SIREDegradation,
)


def enforce_layer10_invariants(output: Layer10Output, grid_h: int, grid_w: int) -> List[str]:
    """
    Enforce all Layer 10 invariants. Returns list of violation descriptions.
    Updates quality_report in-place.
    """
    violations: List[str] = []

    # INV-1: Grid alignment — all surfaces must match grid dimensions
    for s in output.surface_pack:
        if len(s.values) != grid_h:
            violations.append(f"INV-1: Surface {s.surface_id} height {len(s.values)} != grid {grid_h}")
        elif any(len(row) != grid_w for row in s.values):
            violations.append(f"INV-1: Surface {s.surface_id} has rows with wrong width (expected {grid_w})")
        # Confidence same shape
        if s.confidence is not None:
            if len(s.confidence) != grid_h:
                violations.append(f"INV-1: Surface {s.surface_id} confidence height mismatch")

    output.quality_report.grid_alignment_ok = not any("INV-1" in v for v in violations)

    # INV-2: Semantic value ranges
    RANGE_MAP = {
        SurfaceType.NDVI_CLEAN: (-1.0, 1.0),
        SurfaceType.NDVI_DEVIATION: (-2.0, 2.0),
        SurfaceType.WATER_STRESS_PROB: (0.0, 1.0),
        SurfaceType.NUTRIENT_STRESS_PROB: (0.0, 1.0),
        SurfaceType.BIOTIC_PRESSURE: (0.0, 1.0),
        SurfaceType.SPREAD_LIKELIHOOD: (0.0, 1.0),
        SurfaceType.CROP_SUITABILITY: (0.0, 1.0),
        SurfaceType.COMPOSITE_RISK: (0.0, 1.0),
        SurfaceType.UNCERTAINTY_SIGMA: (0.0, None),  # >= 0 only
        SurfaceType.DATA_RELIABILITY: (0.0, 1.0),
        SurfaceType.SOURCE_DOMINANCE: (0.0, 1.0),
        SurfaceType.CONFLICT_DENSITY: (0.0, 1.0),
    }
    for s in output.surface_pack:
        rng = RANGE_MAP.get(s.semantic_type)
        if rng is None:
            continue
        lo, hi = rng
        for row in s.values:
            for v in row:
                if v is None:
                    continue
                if lo is not None and v < lo - 1e-6:
                    violations.append(
                        f"INV-2: Surface {s.surface_id} value {v} < min {lo}"
                    )
                    break
                if hi is not None and v > hi + 1e-6:
                    violations.append(
                        f"INV-2: Surface {s.surface_id} value {v} > max {hi}"
                    )
                    break
            else:
                continue
            break  # break outer on first violation per surface

    # INV-3: Source dominance weights sum to ~1.0
    for s in output.surface_pack:
        if s.source_weights is None:
            continue
        for r, row in enumerate(s.source_weights):
            for c, w in enumerate(row):
                if w is None:
                    continue
                total = sum(w.values())
                if abs(total - 1.0) > 0.05:
                    violations.append(
                        f"INV-3: Surface {s.surface_id} source_weights[{r}][{c}] sum={total:.3f} != 1.0"
                    )
                    break
            else:
                continue
            break

    # INV-4: Zone evidence — every zone must have evidence + confidence
    for z in output.zone_pack:
        if z.confidence < 0.0 or z.confidence > 1.0:
            violations.append(f"INV-4: Zone {z.zone_id} confidence {z.confidence} out of [0,1]")
        if not z.top_drivers:
            violations.append(f"INV-4: Zone {z.zone_id} has no top_drivers (evidence required)")

    # INV-5: Zone topology — no overlapping cells within same family
    family_cells = {}
    for z in output.zone_pack:
        fam = z.zone_family
        if fam not in family_cells:
            family_cells[fam] = set()
        for cell in z.cell_indices:
            cell_key = (cell[0], cell[1])
            if cell_key in family_cells[fam]:
                violations.append(
                    f"INV-5: Zone {z.zone_id} overlaps existing zone in family {fam.value} at {cell_key}"
                )
                break
            family_cells[fam].add(cell_key)

    # INV-6: No action overlay without upstream action evidence
    for z in output.zone_pack:
        if z.zone_family == ZoneFamily.DECISION and z.linked_actions:
            # Each linked action should exist
            pass  # Can't fully validate without L8 reference, but ensure list is non-empty
        if z.zone_family == ZoneFamily.DECISION and not z.linked_actions and not z.linked_findings:
            violations.append(
                f"INV-6: Decision zone {z.zone_id} has no linked_actions or linked_findings"
            )

    # INV-7: Histogram consistency — bin counts sum to valid pixels
    for h in output.histogram_bundle.field_histograms:
        total = sum(h.bin_counts)
        if total != h.valid_pixels:
            violations.append(
                f"INV-7: Histogram {h.surface_type.value}/{h.region_id} "
                f"bin_counts sum={total} != valid_pixels={h.valid_pixels}"
            )

    # INV-8: Temporal slice grid alignment — all slices must match H×W
    tb = output.temporal_bundle
    if tb and tb.slices:
        for ts in tb.slices:
            if len(ts.values) != grid_h:
                violations.append(
                    f"INV-8: TemporalSlice {ts.date} (offset={ts.day_offset}) "
                    f"height {len(ts.values)} != grid {grid_h}"
                )
            elif any(len(row) != grid_w for row in ts.values):
                violations.append(
                    f"INV-8: TemporalSlice {ts.date} (offset={ts.day_offset}) "
                    f"has rows with wrong width (expected {grid_w})"
                )

    # INV-9: Forecast confidence decay — forecast slices must have confidence ≤ retrospective
    if tb and tb.slices:
        retro_confs = [s.confidence for s in tb.slices if not s.is_forecast]
        forecast_confs = [s.confidence for s in tb.slices if s.is_forecast]
        if retro_confs and forecast_confs:
            max_retro = max(retro_confs)
            for fs in tb.slices:
                if fs.is_forecast and fs.confidence > max_retro + 0.01:
                    violations.append(
                        f"INV-9: Forecast slice {fs.date} confidence "
                        f"{fs.confidence} exceeds retrospective max {max_retro}"
                    )

    # INV-10: Temporal bundle date ordering — day_offset must be monotonic
    if tb and tb.slices:
        offsets = [s.day_offset for s in tb.slices]
        for i in range(1, len(offsets)):
            if offsets[i] < offsets[i - 1]:
                violations.append(
                    f"INV-10: TemporalBundle slice ordering violation at index {i}: "
                    f"offset {offsets[i]} follows {offsets[i-1]}"
                )
                break  # One violation is enough

    # INV-11: Execution surface range — readiness/priority/timing must be [0, 1]
    EXEC_TYPES = {
        SurfaceType.EXECUTION_READINESS,
        SurfaceType.INTERVENTION_PRIORITY,
        SurfaceType.INTERVENTION_TIMING,
        SurfaceType.CONFLICT_RESOLUTION,
    }
    for s in output.surface_pack:
        if s.semantic_type not in EXEC_TYPES:
            continue
        for row in s.values:
            for v in row:
                if v is None:
                    continue
                if v < -1e-6 or v > 1.0 + 1e-6:
                    violations.append(
                        f"INV-11: Execution surface {s.surface_id} "
                        f"value {v} outside [0, 1]"
                    )
                    break
            else:
                continue
            break

    # Store violations
    output.quality_report.warnings = violations
    if violations:
        output.quality_report.reliability_score = max(
            0.0,
            output.quality_report.reliability_score - 0.1 * len(violations)
        )

    return violations


"""
Layer 10 Invariants — Runtime Safety Checks
=============================================

Enforced after every L10 run. Violations → warning + quality degradation.
"""

from typing import List
from services.agribrain.layer10_sire.schema import (
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
        prov = s.provenance or {}
        is_visual_quarantine = (prov.get("visual_only") is True and prov.get("state_update_allowed") is False)
        is_experimental_1m = (
            s.semantic_type.value.endswith("_EXPERIMENTAL_FINE_DETAIL")
            or s.semantic_type in (
                SurfaceType.EXPERIMENTAL_FINE_DETAIL_CANDIDATE,
                SurfaceType.EXPERIMENTAL_VISUAL_CANOPY_HIGHRES,
                SurfaceType.ASMAE_VISUAL_FUSION_CANOPY,
            )
        )
        if is_visual_quarantine or is_experimental_1m:
            continue

        if len(s.values) != grid_h:
            violations.append(f"INV-1: Surface {s.surface_id} height {len(s.values)} != grid {grid_h}")
        elif any(len(row) != grid_w for row in s.values):
            violations.append(f"INV-1: Surface {s.surface_id} has rows with wrong width (expected {grid_w})")
        # Confidence same shape
        if s.confidence is not None:
            if len(s.confidence) != grid_h:
                violations.append(f"INV-1: Surface {s.surface_id} confidence height mismatch")

    output.quality_report.grid_alignment_ok = not any("INV-1" in v for v in violations)

    RANGE_MAP = {
        SurfaceType.NDVI_CLEAN: (-1.0, 1.0),
        SurfaceType.NDVI_DEVIATION: (-2.0, 2.0),
        SurfaceType.WATER_STRESS_PROB: (0.0, 1.0),
        SurfaceType.NUTRIENT_STRESS_PROB: (0.0, 1.0),
        SurfaceType.BIOTIC_PRESSURE: (0.0, 1.0),
        SurfaceType.SPREAD_LIKELIHOOD: (0.0, 1.0),
        SurfaceType.CROP_SUITABILITY: (0.0, 1.0),
        SurfaceType.WATER_FEASIBILITY: (0.0, 1.0),
        SurfaceType.BIOTIC_FEASIBILITY: (0.0, 1.0),
        SurfaceType.ECONOMIC_SUITABILITY: (0.0, 1.0),
        SurfaceType.SUITABILITY_WINDOW: (0.0, 1.0),
        SurfaceType.SEASON_PROGRESS: (0.0, 1.0),
        SurfaceType.COMPOSITE_RISK: (0.0, 1.0),
        SurfaceType.UNCERTAINTY_SIGMA: (0.0, None),  # >= 0 only
        SurfaceType.DATA_RELIABILITY: (0.0, 1.0),
        SurfaceType.SOURCE_DOMINANCE: (0.0, 1.0),
        SurfaceType.CONFLICT_DENSITY: (0.0, 1.0),
        SurfaceType.SOIL_CARBON: (0.0, None),
        SurfaceType.SOIL_COMPACTION: (0.0, 1.0),
        SurfaceType.THERMAL_STRESS: (0.0, 1.0),
        SurfaceType.N_LEACHING_RISK: (0.0, 1.0),
        SurfaceType.N_VOLATILIZATION_RISK: (0.0, 1.0),

        # ASMAE ranges (V82)
        SurfaceType.ASMAE_VIGOR: (0.0, 1.0),
        SurfaceType.ASMAE_LAI: (0.0, 8.0),
        SurfaceType.ASMAE_CHLOROPHYLL: (0.0, 80.0),
        SurfaceType.ASMAE_ML_AGREEMENT: (0.0, 1.0),
        SurfaceType.ASMAE_ARCHIVE_SUPPORT: (0.0, 1.0),
        SurfaceType.ASMAE_ENKF_SUPPORT: (0.0, 1.0),
        SurfaceType.ASMAE_RADIOMETRIC_SUPPORT: (0.0, 1.0),
        SurfaceType.ASMAE_VISUAL_FUSION_CANOPY: (0.0, 1.0),

        # Composite Surfaces
        SurfaceType.COMPOSITE_ADVISORY_CANOPY: (0.0, 1.0),
        SurfaceType.COMPOSITE_VEG_ATTENTION: (0.0, 1.0),
        SurfaceType.COMPOSITE_WATER_SUPPORT: (-1.0, 1.0),
        SurfaceType.COMPOSITE_NUTRIENT_SUPPORT: (0.0, 1.0),
        SurfaceType.COMPOSITE_SALINITY_STRESS: (0.0, 1.0),
        SurfaceType.COMPOSITE_RISK_DIAGNOSTIC: (0.0, 1.0),
        SurfaceType.COMPOSITE_CONFIDENCE: (0.0, 1.0),
        SurfaceType.COMPOSITE_EFFECTIVE_RESOLUTION: (0.03, 10.0),
        SurfaceType.COMPOSITE_UNCERTAINTY: (0.0, 1.0),
        SurfaceType.COMPOSITE_BMA_DISAGREEMENT: (0.0, 1.0),
        SurfaceType.COMPOSITE_ARCHIVE_SUPPORT: (0.0, 1.0),
        SurfaceType.COMPOSITE_RETRO_SCORE: (0.0, 1.0),
        SurfaceType.COMPOSITE_ML_SUPPORT: (0.0, 1.0),
        SurfaceType.COMPOSITE_TEXTURE_DETAIL: (-1.0, 1.0),
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

    # ASMAE Truthfulness Invariants (V82)
    from services.agribrain.layer10_sire.schema import ASMAE_STATE_SURFACES, ASMAE_DIAGNOSTIC_SURFACES
    
    for s in output.surface_pack:
        is_asmae = s.semantic_type.value.startswith("ASMAE_")
        if not is_asmae:
            continue
            
        is_composite = s.semantic_type.value.startswith("COMPOSITE_")
        if is_composite:
            prov = s.provenance or {}
            # INV-COMPOSITE block validating static attributes
            if prov.get("source_reality") != "raster_composite_proxy":
                violations.append(f"INV-COMPOSITE: Surface {s.surface_id} source_reality is not raster_composite_proxy")
            if prov.get("real_asmae_evidence") is not False:
                violations.append(f"INV-COMPOSITE: Surface {s.surface_id} real_asmae_evidence is not False")
            if prov.get("asmae_advisory_evidence") is not True:
                violations.append(f"INV-COMPOSITE: Surface {s.surface_id} asmae_advisory_evidence is not True")
            if prov.get("current_1m_approval_allowed") is not False:
                violations.append(f"INV-COMPOSITE: Surface {s.surface_id} current_1m_approval_allowed is not False")
            if prov.get("authority") != "experimental_asmae_advisory":
                violations.append(f"INV-COMPOSITE: Surface {s.surface_id} authority is not experimental_asmae_advisory")
            if prov.get("state_update_allowed") is not False:
                violations.append(f"INV-COMPOSITE: Surface {s.surface_id} state_update_allowed is not False")
            if prov.get("prescription_driver_allowed") is not False:
                violations.append(f"INV-COMPOSITE: Surface {s.surface_id} prescription_driver_allowed is not False")
            
            # matching grid shape
            if len(s.values) != grid_h:
                violations.append(f"INV-COMPOSITE: Surface {s.surface_id} height {len(s.values)} != grid {grid_h}")
            elif any(len(row) != grid_w for row in s.values):
                violations.append(f"INV-COMPOSITE: Surface {s.surface_id} has rows with wrong width (expected {grid_w})")
            continue

        prov = s.provenance or {}
        
        # 1. no_missing_asmae_provenance
        required_prov_keys = [
            "resolution_m", "confidence", "uncertainty", "retro_status", 
            "bma_status", "bma_disagreement", "cross_layer_conflict", 
            "state_update_allowed", "diagnostic_only", "visual_only", 
            "content_hash", "artifact_instance_hash", "warning_codes",
            "display_trust_tier"
        ]
        missing_keys = [k for k in required_prov_keys if k not in prov]
        if missing_keys:
            violations.append(
                f"INV-12 (no_missing_asmae_provenance): Surface {s.surface_id} is missing provenance keys: {missing_keys}"
            )
            
        res_m = prov.get("resolution_m", 10.0)
        state_allowed = prov.get("state_update_allowed", False)
        diag_only = prov.get("diagnostic_only", True)
        vis_only = prov.get("visual_only", False)
        warning_codes = prov.get("warning_codes", [])
        bma_status = prov.get("bma_status")
        conf = prov.get("confidence", 0.0)
        unc = prov.get("uncertainty", 0.0)
        warning_wording = prov.get("warning_wording", "")
        has_spatial_grid = prov.get("has_spatial_grid", True)
        
        # 2. no_1m_direct_observation_claim
        if res_m <= 1.0:
            if "warning_wording" not in prov or "not a direct 1m satellite observation" not in warning_wording.lower():
                violations.append(
                    f"INV-13 (no_1m_direct_observation_claim): Surface {s.surface_id} has resolution <= 1m but lacks standard warning_wording"
                )
                
        # 3. no_1m_state_update_allowed
        if res_m <= 1.0:
            if state_allowed or not diag_only or not vis_only:
                violations.append(
                    f"INV-14 (no_1m_state_update_allowed): Surface {s.surface_id} has resolution <= 1m but allows state updates or is not quarantined visual-only"
                )
                
        # 4. no_diagnostic_surface_as_state_evidence
        if s.semantic_type in ASMAE_DIAGNOSTIC_SURFACES:
            if state_allowed or not diag_only:
                violations.append(
                    f"INV-15 (no_diagnostic_surface_as_state_evidence): Diagnostic surface {s.surface_id} is marked as state evidence"
                )
                
        # 5. no_low_trust_surface_without_warning
        if conf < 0.60 or unc > 0.40:
            if "low_confidence" not in warning_codes and "high_uncertainty" not in warning_codes:
                violations.append(
                    f"INV-16 (no_low_trust_surface_without_warning): Surface {s.surface_id} is low-trust but lacks low_confidence/high_uncertainty warning codes"
                )
            if not prov.get("requires_user_warning") or not (prov.get("desaturation_level", 0.0) > 0.0 or prov.get("desaturated", False)):
                violations.append(
                    f"INV-16 (no_low_trust_surface_without_warning): Surface {s.surface_id} is low-trust but does not require warning or desaturation"
                )

        # 6. no_bma_failure_without_diagnostic_badge
        if bma_status != "success":
            if "bma_not_success" not in warning_codes or prov.get("display_trust_tier") != "diagnostic":
                violations.append(
                    f"INV-17 (no_bma_failure_without_diagnostic_badge): Surface {s.surface_id} BMA failed but display trust tier is not diagnostic or lacks bma_not_success warning code"
                )
                
        # 7. no_scalar_broadcast_state_surface
        if s.semantic_type in ASMAE_STATE_SURFACES:
            if not has_spatial_grid:
                if not diag_only or not vis_only or state_allowed:
                    violations.append(
                        f"INV-18 (no_scalar_broadcast_state_surface): Placeholder state surface {s.surface_id} is not properly quarantined"
                    )

        # 8. no_1m_certified_basis_claim
        certified_basis_m = prov.get("certified_basis_m", 10.0)
        if res_m <= 1.0 and certified_basis_m <= 1.0:
            if prov.get("source_basis") != "asmae_learn":
                violations.append(
                    f"INV-19 (no_1m_certified_basis_claim): Surface {s.surface_id} has resolution <= 1m and claims certified_basis_m <= 1m"
                )

    # Store violations
    output.quality_report.warnings = violations
    if violations:
        output.quality_report.reliability_score = max(
            0.0,
            output.quality_report.reliability_score - 0.1 * len(violations)
        )

    return violations


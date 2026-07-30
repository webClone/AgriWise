"""
ASMAE source adapter for Layer 1.

Implements a graduated trust model that extracts audit, diagnostic, visual,
state, and training evidence from ASMAE outputs based on channel eligibility gates.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from layer1_fusion.schemas import (
    EvidenceItem,
    Layer1InputBundle,
    SourceEnvelope,
)


def asmae_audit_allowed(output: Dict[str, Any]) -> bool:
    """Audit is always allowed if output has a run_id and diagnostics."""
    if not isinstance(output, dict):
        return False
    return bool(output.get("run_id") and output.get("diagnostics") is not None)


def asmae_diagnostic_allowed(output: Dict[str, Any]) -> bool:
    """Diagnostics are allowed for shadow, partial, degraded_mean_only, and success runs."""
    if not isinstance(output, dict):
        return False
    status = output.get("status")
    diag = output.get("diagnostics", {})
    mode = diag.get("mode") or output.get("provenance", {}).get("mode", "")
    scene_mode = diag.get("scene_stack_mode", "")
    return (
        status in ("success", "partial")
        or mode in ("shadow", "training_export", "certification")
        or "mean" in scene_mode
        or bool(output.get("plot_state_artifact"))
    )


def asmae_plot_state_allowed(output: Dict[str, Any]) -> bool:
    artifact = output.get("plot_state_artifact") if isinstance(output, dict) else None
    if not isinstance(artifact, dict) or not artifact:
        return False
    return bool(
        output.get("plot_state_publication_allowed", True)
        and artifact.get("state_availability")
    )


def asmae_visual_allowed(output: Dict[str, Any]) -> bool:
    """Visual allowed if layer10_scientific_surface_allowed is True or diagnostic_only is True."""
    if not isinstance(output, dict):
        return False
    diag = output.get("diagnostics", {})
    return bool(diag.get("layer10_scientific_surface_allowed") or diag.get("diagnostic_only"))


def asmae_state_evidence_allowed(output: Dict[str, Any], raster_key: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> bool:
    """State evidence requires passing strict scientific gates.
    
    1m resolution state updates are strictly blocked in V80.
    """
    if not isinstance(output, dict):
        return False

    diag = output.get("diagnostics", {})
    res_decision = output.get("resolution_decision") or {}
    res_m = res_decision.get("selected_effective_resolution_m", 10)

    # 1m is strictly blocked from state updates in V80
    if res_m <= 1:
        return False

    if output.get("status") != "success":
        return False
    if output.get("production_usable") is not True:
        return False
    if diag.get("scientific_pass") is not True:
        return False
    if output.get("layer1_export_allowed") is not True:
        return False
    if diag.get("scene_stack_mode") != "real_raster":
        return False
    if diag.get("enkf_mode") != "ht_per_pixel":
        return False
    if diag.get("radiometric_mode") != "ht_per_pixel":
        return False
    if diag.get("retro_status") != "success_with_holdouts":
        return False
    # Require explicit flags, no permissive default values
    if diag.get("diagnostic_only") is not False:
        return False
    if diag.get("state_update_allowed") is not True:
        return False

    # Require real observation operators and matching counts
    operator_refs = output.get("observation_operator_refs") or []
    operator_count = int(diag.get("operator_count") or 0)
    if not operator_refs:
        return False
    if operator_count <= 0:
        return False
    if operator_count != len(operator_refs):
        return False

    return True


def asmae_training_allowed(output: Dict[str, Any]) -> bool:
    """Training allowed if weak_label_export_allowed is True and mode is training_export or certification."""
    if not isinstance(output, dict):
        return False
    weak_label_export = output.get("weak_label_export_allowed")
    diag = output.get("diagnostics", {})
    mode = diag.get("mode") or output.get("provenance", {}).get("mode", "")
    return bool(weak_label_export is True and mode in ("training_export", "certification"))


def _mean_of_grids(grids: Dict[str, List[List[float]]]) -> float:
    """Helper to calculate mean value of multiple 2D grids."""
    if not grids:
        return 0.0
    total_sum = 0.0
    total_count = 0
    for grid in grids.values():
        if not grid:
            continue
        for row in grid:
            if not row:
                continue
            total_sum += sum(row)
            total_count += len(row)
    return total_sum / total_count if total_count > 0 else 0.0


def calculate_asmae_trust(output: Dict[str, Any]) -> Tuple[float, str]:
    """Calculate trust score and trust level from ASMAE diagnostics."""
    if not isinstance(output, dict):
        return 0.0, "blocked"

    diag = output.get("diagnostics", {})
    scientific_pass_val = 1.0 if diag.get("scientific_pass") is True else 0.0
    radiometric_pass_val = 1.0 if diag.get("radiometric_overall_pass") is True else 0.0
    retro_score = float(diag.get("retro_mean_score") or 0.0)
    bma_disagreement = float(diag.get("bma_mean_disagreement") or 0.0)
    confidence_val = float(_mean_of_grids(output.get("confidence_maps", {})) or 0.5)

    scene_mode = diag.get("scene_stack_mode", "")
    if scene_mode == "real_raster":
        source_reality_score = 1.0
    elif scene_mode == "degraded_mean_only":
        source_reality_score = 0.5
    else:
        source_reality_score = 0.0

    trust_score = (
        0.25 * scientific_pass_val
        + 0.20 * radiometric_pass_val
        + 0.20 * retro_score
        + 0.15 * (1.0 - bma_disagreement)
        + 0.10 * confidence_val
        + 0.10 * source_reality_score
    )
    trust_score = round(trust_score, 4)

    state_allowed = asmae_state_evidence_allowed(output)

    # Trust level assignment
    if trust_score < 0.25:
        trust_level = "blocked"
    elif trust_score >= 0.75:
        trust_level = "trusted" if state_allowed else "diagnostic"
    elif trust_score >= 0.50:
        trust_level = "provisional"
    else:
        trust_level = "diagnostic"

    return trust_score, trust_level


class ASMAEAdapter:
    source_family = "asmae"

    def can_read(self, package: Any) -> bool:
        """Can read if package is a dictionary and has a run_id."""
        return isinstance(package, dict) and "run_id" in package

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if not self.can_read(package):
            return items

        plot_id = context.plot_id
        run_id = package.get("run_id", "")
        generated_str = package.get("generated_at")
        if generated_str:
            observed_at = datetime.fromisoformat(generated_str)
            if context.run_timestamp.tzinfo is not None and observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=context.run_timestamp.tzinfo)
            elif context.run_timestamp.tzinfo is None and observed_at.tzinfo is not None:
                observed_at = observed_at.replace(tzinfo=None)
        else:
            observed_at = context.run_timestamp

        # Canonical non-spatial plot state is always diagnostic evidence. It
        # is deliberately non-updating and is never converted into a raster.
        if asmae_plot_state_allowed(package):
            artifact = dict(package.get("plot_state_artifact") or {})
            artifact_as_of = artifact.get("as_of")
            if artifact_as_of:
                try:
                    observed_at = datetime.fromisoformat(
                        str(artifact_as_of).replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            plot_vars = [
                (
                    "ASMAE_STATE_AVAILABILITY",
                    artifact.get("state_availability", "UNAVAILABLE"),
                    "class",
                ),
                (
                    "ASMAE_AUTHORITY_LEVEL",
                    artifact.get("authority_level", "DIAGNOSTIC"),
                    "class",
                ),
                (
                    "ASMAE_PLOT_STATE_CONTENT_HASH",
                    artifact.get("content_hash", ""),
                    "index",
                ),
            ]
            for var, val, unit in plot_vars:
                items.append(EvidenceItem(
                    evidence_id=f"asmae_{run_id}_{var.lower()}",
                    plot_id=plot_id,
                    variable=var,
                    value=val,
                    unit=unit,
                    source_family="asmae",
                    source_id=run_id,
                    observation_type="diagnostic",
                    spatial_scope="plot",
                    observed_at=observed_at,
                    confidence=1.0,
                    reliability=1.0,
                    provenance_ref=f"asmae_plot_state_{artifact.get('content_hash', run_id)}",
                    diagnostic_only=True,
                    state_update_allowed=False,
                ))
            for state, estimate in dict(artifact.get("posterior") or {}).items():
                if not isinstance(estimate, dict):
                    continue
                value = estimate.get("mean")
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                sigma = estimate.get("sigma")
                confidence = (
                    max(0.0, min(1.0, 1.0 - float(sigma)))
                    if isinstance(sigma, (int, float)) and not isinstance(sigma, bool)
                    else 0.25
                )
                items.append(EvidenceItem(
                    evidence_id=f"asmae_{run_id}_plot_{state}",
                    plot_id=plot_id,
                    variable=f"ASMAE_PLOT_{str(state).upper()}",
                    value=float(value),
                    unit="state_unit",
                    source_family="asmae",
                    source_id=run_id,
                    observation_type="derived_feature",
                    spatial_scope="plot",
                    observed_at=observed_at,
                    confidence=confidence,
                    reliability=confidence,
                    provenance_ref=f"asmae_plot_state_{artifact.get('content_hash', run_id)}",
                    diagnostic_only=True,
                    state_update_allowed=False,
                    flags=["PLOT_STATE_ONLY", "NON_SPATIAL"],
                ))
        
        # 1. Audit evidence (always allowed if audit_allowed)
        if asmae_audit_allowed(package):
            audit_vars = [
                ("ASMAE_EXPORT_ELIGIBILITY", package.get("layer1_export_allowed", False), "bool"),
                ("ASMAE_RUN_STATUS", package.get("status", "error"), "class"),
                ("ASMAE_CONTENT_HASH", package.get("content_hash", ""), "index"),
                ("ASMAE_ARTIFACT_INSTANCE_HASH", package.get("artifact_instance_hash", ""), "index"),
                ("ASMAE_DIAGNOSTICS", json.dumps(package.get("diagnostics", {})), "index"),
                ("ASMAE_SOURCE_REALITY", package.get("diagnostics", {}).get("scene_stack_mode", "unknown"), "class"),
            ]
            for var, val, unit in audit_vars:
                items.append(EvidenceItem(
                    evidence_id=f"asmae_{run_id}_{var.lower()}",
                    plot_id=plot_id,
                    variable=var,
                    value=val,
                    unit=unit,
                    source_family="asmae",
                    source_id=run_id,
                    observation_type="diagnostic",
                    spatial_scope="plot",
                    observed_at=observed_at,
                    confidence=1.0,
                    reliability=1.0,
                    provenance_ref=f"asmae_run_{run_id}",
                    diagnostic_only=True,
                    state_update_allowed=False,
                ))

        # 2. Diagnostic/visual evidence
        if asmae_diagnostic_allowed(package):
            res_decision = package.get("resolution_decision") or {}
            res_m = res_decision.get("selected_effective_resolution_m", 10)
            diag = package.get("diagnostics", {})
            
            conf_val = float(_mean_of_grids(package.get("confidence_maps", {})) or 0.5)
            unc_val = float(_mean_of_grids(package.get("uncertainty_maps", {})) or 0.1)

            diag_vars = [
                ("ASMAE_CONFIDENCE", conf_val, "fraction"),
                ("ASMAE_UNCERTAINTY", unc_val, "fraction"),
                ("ASMAE_RETROVALIDATION_SCORE", float(diag.get("retro_mean_score") or 0.0), "fraction"),
                ("ASMAE_BMA_DISAGREEMENT", float(diag.get("bma_mean_disagreement") or 0.0), "fraction"),
                ("ASMAE_EXPORT_ELIGIBILITY", package.get("layer1_export_allowed", False), "bool"),
            ]
            if package.get("raster_maps"):
                diag_vars.insert(0, ("ASMAE_EFFECTIVE_RESOLUTION", float(res_m), "m"))
            for var, val, unit in diag_vars:
                # Deduplicate ASMAE_EXPORT_ELIGIBILITY if already added as audit
                if var == "ASMAE_EXPORT_ELIGIBILITY" and any(item.variable == "ASMAE_EXPORT_ELIGIBILITY" for item in items):
                    continue
                items.append(EvidenceItem(
                    evidence_id=f"asmae_{run_id}_{var.lower()}",
                    plot_id=plot_id,
                    variable=var,
                    value=val,
                    unit=unit,
                    source_family="asmae",
                    source_id=run_id,
                    observation_type="diagnostic",
                    spatial_scope="plot",
                    observed_at=observed_at,
                    confidence=conf_val,
                    reliability=conf_val,
                    provenance_ref=f"asmae_run_{run_id}",
                    diagnostic_only=True,
                    state_update_allowed=False,
                ))

            # 3. State evidence (state variables from raster_maps)
            # Map of uppercase evidence variable name → lowercase key in raster_maps
            state_map = {
                "ASMAE_VIGOR": "vigor",
                "ASMAE_LAI": "lai",
                "ASMAE_CHLOROPHYLL": "chlorophyll",
                "ASMAE_CANOPY_WATER": "canopy_water",
                "ASMAE_ROOT_ZONE_WATER": "root_zone_water",
                "ASMAE_SURFACE_WETNESS_EVENT": "surface_wetness_event",
                "ASMAE_STRUCTURE": "structure",
                "ASMAE_BARE_SOIL": "bare_soil_fraction",
                "ASMAE_SALINITY_STRESS": "salinity_stress",
                "ASMAE_THERMAL_STRESS": "thermal_stress",
                "ASMAE_BIOTIC_CONFOUNDER_RISK": "biotic_confounder_risk",
            }
            state_allowed = asmae_state_evidence_allowed(package)
            
            raster_maps = package.get("raster_maps", {})
            for var, key in state_map.items():
                grid = raster_maps.get(key)
                if grid and grid[0]:
                    # Compute plot stats to get the mean
                    flat = [v for r in grid for v in r if v is not None and v == v]
                    if flat:
                        val = sum(flat) / len(flat)
                        unit = "index" if var in ("ASMAE_LAI", "ASMAE_CHLOROPHYLL") else "fraction"
                        
                        items.append(EvidenceItem(
                            evidence_id=f"asmae_{run_id}_{var.lower()}",
                            plot_id=plot_id,
                            variable=var,
                            value=val,
                            unit=unit,
                            source_family="asmae",
                            source_id=run_id,
                            observation_type="derived_feature",
                            spatial_scope="plot",
                            observed_at=observed_at,
                            confidence=conf_val,
                            reliability=conf_val,
                            provenance_ref=f"asmae_run_{run_id}",
                            diagnostic_only=not state_allowed,
                            state_update_allowed=state_allowed,
                        ))

            # 4. Training labels (weak labels)
            if asmae_training_allowed(package):
                w_labels = package.get("weak_labels", [])
                avg_weight = sum(l.get("training_weight", 0.0) for l in w_labels) / len(w_labels) if w_labels else 0.0
                items.append(EvidenceItem(
                    evidence_id=f"asmae_{run_id}_training_weight",
                    plot_id=plot_id,
                    variable="ASMAE_TRAINING_WEIGHT",
                    value=avg_weight,
                    unit="fraction",
                    source_family="asmae",
                    source_id=run_id,
                    observation_type="diagnostic",
                    spatial_scope="plot",
                    observed_at=observed_at,
                    confidence=1.0,
                    reliability=1.0,
                    provenance_ref=f"asmae_run_{run_id}",
                    diagnostic_only=True,
                    state_update_allowed=False,
                    flags=["TRAINING_LABEL"],
                ))

        from layer1_fusion.truth_bridge import normalize_evidence_truth
        for item in items:
            normalize_evidence_truth(item, source_context=package)
        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="asmae_missing",
                source_family="asmae",
                source_name="ASMAE Engine",
                package_id="",
                package_version="",
                source_status="missing",
            )

        status = package.get("status", "error")
        run_id = package.get("run_id", "")
        schema_version = package.get("schema_version", "")
        content_hash = package.get("content_hash", "")
        diag = package.get("diagnostics", {})
        usable = package.get("production_usable", False)

        trust_score, _ = calculate_asmae_trust(package)
        source_status = "ok" if status == "success" and usable else "degraded"

        generated_str = package.get("generated_at")
        produced_at = datetime.fromisoformat(generated_str) if generated_str else None

        return SourceEnvelope(
            source_id=run_id,
            source_family="asmae",
            source_name="ASMAE Engine",
            package_id=run_id,
            package_version=schema_version,
            input_hash=content_hash,
            produced_at=produced_at,
            observed_start=None,
            observed_end=None,
            spatial_scope="raster" if package.get("raster_maps") else "plot",
            temporal_scope="instant",
            trust_score=trust_score,
            source_status=source_status,
            diagnostics=diag,
        )

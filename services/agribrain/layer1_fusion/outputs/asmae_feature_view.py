"""
Central ASMAE Downstream Accessor.

Provides a unified interface for Layers 2–8 to consume ASMAE evidence
and evaluate its usability without raw RasterRef or context dictionary inspection.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ASMAEFeature:
    variable: str
    value: float
    confidence: float
    uncertainty: Optional[float]
    resolution_m: float
    asmae_channel: str
    diagnostic_only: bool
    state_update_allowed: bool
    content_hash: Optional[str] = None
    artifact_instance_hash: Optional[str] = None
    retro_status: Optional[str] = None
    bma_status: Optional[str] = None
    source_basis: str = "asmae"
    bma_disagreement: float = 0.0
    cross_layer_conflict: float = 0.0


@dataclass
class ASMAEUsabilityResult:
    usable: bool
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.0
    uncertainty: float = 0.0
    resolution_m: float = 10.0
    channel: str = "diagnostic"


def _clean_var_name(variable: str) -> str:
    v = variable.upper()
    if not v.startswith("ASMAE_"):
        v = f"ASMAE_{v}"
    return v


def _find_raster_refs(obj: Any) -> List[Any]:
    if hasattr(obj, "spatial_index_ref") and obj.spatial_index_ref:
        return getattr(obj.spatial_index_ref, "raster_refs", [])
    if hasattr(obj, "spatial_index") and obj.spatial_index:
        return getattr(obj.spatial_index, "raster_refs", [])
    return []


def _find_diagnostics_dict(obj: Any) -> Dict[str, Any]:
    # Try diagnostic_values in Layer2InputContext
    if hasattr(obj, "diagnostic_values") and isinstance(obj.diagnostic_values, dict):
        diag_item = obj.diagnostic_values.get("ASMAE_DIAGNOSTICS")
        if diag_item and isinstance(diag_item, dict):
            val = diag_item.get("value")
            if val:
                try:
                    return json.loads(val)
                except Exception:
                    pass

    # Try diagnostics in Layer2Output / Layer1ContextPackage
    if hasattr(obj, "diagnostics") and obj.diagnostics:
        # Check if it has a diagnostics field
        if hasattr(obj.diagnostics, "status"):
            # L2/L3 Diagnostics
            pass

    # Try conflicts/gaps for ASMAE_DIAGNOSTICS value
    # Check if obj is a dict (like in test mocks)
    if isinstance(obj, dict):
        return obj.get("diagnostics") or {}

    return {}


def _extract_feature_from_obj(obj: Any, variable: str) -> Optional[ASMAEFeature]:
    """Inspect the object (context, package, output, or dict) to build ASMAEFeature."""
    v_upper = _clean_var_name(variable)
    v_base = v_upper[6:].lower()  # e.g., "vigor"

    # 1. Look up value, confidence, uncertainty from context/package feature groups
    val, conf, unc = None, None, None
    diag_only, state_allowed = True, False

    # Check Layer 2 input contexts / outputs / dicts
    groups = ["vegetation_context", "water_context", "stress_evidence_context", "diagnostic_values", "data_quality_context"]
    found = False

    for gname in groups:
        group = getattr(obj, gname, None)
        if isinstance(group, dict):
            # check exact upper case name (e.g., "ASMAE_VIGOR")
            if v_upper in group:
                f = group[v_upper]
                val = f.get("value")
                conf = f.get("confidence")
                unc = f.get("uncertainty")
                diag_only = f.get("diagnostic_only", True)
                state_allowed = f.get("state_update_allowed", False)
                found = True
                break
            # check evidence variant (e.g., "ASMAE_VIGOR_evidence")
            ev_name = f"{v_upper}_evidence"
            if ev_name in group:
                f = group[ev_name]
                val = f.get("value")
                conf = f.get("confidence")
                unc = f.get("uncertainty")
                diag_only = f.get("diagnostic_only", True)
                state_allowed = f.get("state_update_allowed", False)
                found = True
                break

    # Check Layer 1 Context Package (fused_features list)
    if not found and hasattr(obj, "fused_features") and obj.fused_features:
        ffs = (
            obj.fused_features.vegetation_context +
            obj.fused_features.water_context +
            obj.fused_features.stress_evidence_context +
            obj.fused_features.data_quality_context
        )
        for ff in ffs:
            if ff.name in (v_upper, f"{v_upper}_evidence"):
                val = ff.value
                conf = ff.confidence
                unc = ff.uncertainty
                diag_only = ff.diagnostic_only
                state_allowed = not ff.diagnostic_only
                found = True
                break

    # If the feature value wasn't found, check if it's in the asmae_features dictionary
    # (e.g. if passed a Layer3InputContext which has pre-populated asmae_features)
    res_m = None
    channel = None
    c_hash = None
    a_hash = None
    retro_status = None
    bma_status = None
    bma_disagreement = 0.0
    cross_layer_conflict = 0.0
    source_basis = "asmae"

    if not found and hasattr(obj, "asmae_features") and isinstance(obj.asmae_features, dict):
        if v_upper in obj.asmae_features:
            feat_val = obj.asmae_features[v_upper]
            if isinstance(feat_val, ASMAEFeature):
                return feat_val
            elif isinstance(feat_val, dict):
                val = feat_val.get("value")
                conf = feat_val.get("confidence")
                unc = feat_val.get("uncertainty")
                diag_only = feat_val.get("diagnostic_only", True)
                state_allowed = feat_val.get("state_update_allowed", False)
                res_m = feat_val.get("resolution_m")
                channel = feat_val.get("asmae_channel", feat_val.get("channel"))
                c_hash = feat_val.get("content_hash")
                a_hash = feat_val.get("artifact_instance_hash")
                retro_status = feat_val.get("retro_status")
                bma_status = feat_val.get("bma_status")
                bma_disagreement = feat_val.get("bma_disagreement", 0.0)
                cross_layer_conflict = feat_val.get("cross_layer_conflict", 0.0)
                source_basis = feat_val.get("source_basis", "asmae")
                found = True

    # If still not found, we cannot build the feature
    if not found or val is None:
        return None

    # Clean up NaNs / Infs
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None

    # 2. Extract metadata from RasterRef
    raster_refs = _find_raster_refs(obj)
    main_ref = None
    target_ref_id = f"asmae_{v_base}"
    for r in raster_refs:
        # Check both raster_id and variable
        r_id = getattr(r, "raster_id", "")
        r_var = getattr(r, "variable", "")
        if r_id == target_ref_id or r_var == target_ref_id:
            main_ref = r
            break

    res_m_val = res_m if res_m is not None else 10.0
    channel_val = channel if channel is not None else "diagnostic"
    c_hash_val = c_hash
    a_hash_val = a_hash
    src_basis = source_basis

    if main_ref is not None:
        res_m_val = getattr(main_ref, "resolution_m", 10.0)
        channel_val = getattr(main_ref, "asmae_channel", "diagnostic")
        diag_only = getattr(main_ref, "diagnostic_only", diag_only)
        state_allowed = getattr(main_ref, "state_update_allowed", state_allowed)
        c_hash_val = getattr(main_ref, "content_hash", None)
        a_hash_val = getattr(main_ref, "artifact_instance_hash", None)
        src_basis = getattr(main_ref, "source_basis", src_basis)
        retro_status = getattr(main_ref, "retro_status", retro_status)
        bma_status = getattr(main_ref, "bma_status", bma_status)
        bma_disagreement = getattr(main_ref, "bma_disagreement", bma_disagreement)
        cross_layer_conflict = getattr(main_ref, "cross_layer_conflict", cross_layer_conflict)

    # 3. Extract diagnostics (retro/BMA status) from global diagnostic values if still missing
    if retro_status is None or bma_status is None or bma_disagreement == 0.0:
        diag_dict = _find_diagnostics_dict(obj)
        if retro_status is None:
            retro_status = diag_dict.get("retro_status")
        if bma_status is None:
            bma_status = diag_dict.get("bma_status")
        if bma_disagreement == 0.0:
            bma_disagreement = diag_dict.get("bma_mean_disagreement", diag_dict.get("bma_disagreement", 0.0))

    # Fallback default values
    if conf is None:
        conf = 0.5
    # SPEC-E: missing uncertainty remains unknown
    # if unc is None: unc = 0.1

    return ASMAEFeature(
        variable=v_upper,
        value=float(val),
        confidence=float(conf),
        uncertainty=float(unc) if unc is not None else None,
        resolution_m=float(res_m_val),
        asmae_channel=channel_val,
        diagnostic_only=bool(diag_only),
        state_update_allowed=bool(state_allowed),
        content_hash=c_hash_val,
        artifact_instance_hash=a_hash_val,
        retro_status=retro_status,
        bma_status=bma_status,
        source_basis=src_basis,
        bma_disagreement=float(bma_disagreement or 0.0),
        cross_layer_conflict=float(cross_layer_conflict or 0.0),
    )


def get_asmae_state_feature(obj: Any, variable: str) -> Optional[ASMAEFeature]:
    """Retrieve ASMAE feature only if allowed to update state, is not diagnostic-only, and is usable."""
    feat = _extract_feature_from_obj(obj, variable)
    if feat is not None:
        if feat.state_update_allowed and not feat.diagnostic_only and is_asmae_state_usable(feat):
            return feat
    return None


def get_asmae_diagnostic_feature(obj: Any, variable: str) -> Optional[ASMAEFeature]:
    """Retrieve ASMAE feature for diagnostic or visual overlays."""
    return _extract_feature_from_obj(obj, variable)


def evaluate_asmae_state_usability(feature: Optional[ASMAEFeature]) -> ASMAEUsabilityResult:
    """Evaluate and explain ASMAE feature usability."""
    if feature is None:
        return ASMAEUsabilityResult(usable=False, reasons=["feature_missing"])

    reasons = []
    if feature.diagnostic_only:
        reasons.append("diagnostic_only")
    if not feature.state_update_allowed:
        reasons.append("state_update_not_allowed")
    if feature.resolution_m <= 1.0:
        reasons.append("resolution_1m_blocked")
    if feature.confidence < 0.60:
        reasons.append("confidence_below_threshold")
    if feature.uncertainty is None:
        reasons.append("uncertainty_missing")
    elif feature.uncertainty > 0.40:
        reasons.append("uncertainty_above_threshold")
    if feature.retro_status != "success_with_holdouts":
        reasons.append("retrovalidation_failed")
    if feature.bma_status != "success":
        reasons.append("bma_not_success")
    if feature.asmae_channel != "state_evidence":
        reasons.append("channel_not_state_evidence")

    usable = len(reasons) == 0
    return ASMAEUsabilityResult(
        usable=usable,
        reasons=reasons,
        confidence=feature.confidence,
        uncertainty=feature.uncertainty,
        resolution_m=feature.resolution_m,
        channel=feature.asmae_channel,
    )


def is_asmae_state_usable(feature: Optional[ASMAEFeature]) -> bool:
    """Convenience wrapper for state usability."""
    return evaluate_asmae_state_usability(feature).usable

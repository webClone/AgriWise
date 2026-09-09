"""
Composite Runner — Coordinates vegetation modeling and canonical stress attribution.
Produces Layer2CompositeOutput.
"""

import copy
import hashlib
import json
from typing import Any, Optional
from layer1_fusion.schemas import Layer2InputContext, DataHealthScore
from layer2_veg_int.runner import run_layer2_veg
from layer2_intelligence.engine import Layer2IntelligenceEngine
from layer2_intelligence.schemas import Layer2CompositeOutput
from layer2_intelligence.weather_normalizer import normalize_weather_context
from layer2_intelligence.veg_context_enricher import enrich_context_with_veg_output

def run_layer2_composite(inputs: Any, tensor: Any) -> Layer2CompositeOutput:
    """Orchestrator-compatible composite runner for Layer 2."""
    # Resolve Layer 2 input context
    pkg = getattr(tensor, "_context_package", None)
    if pkg and getattr(pkg, "layer2_input", None):
        orig_context = pkg.layer2_input
    else:
        orig_context = build_context_from_tensor_fallback(tensor)

    # 1. Do not mutate pkg.layer2_input in place (deepcopy)
    context = copy.deepcopy(orig_context)

    # 2. Run temporal vegetation engine
    veg_out = run_layer2_veg(inputs, tensor)

    # 3. Enrich copied context with vegetation output
    context = enrich_context_with_veg_output(
        context=context,
        veg_out=veg_out,
        tensor=tensor,
        inputs=inputs,
    )

    # 4. Normalize weather variables
    normalize_weather_context(context=context, tensor=tensor)

    # 5. Run canonical stress engine
    canonical = Layer2IntelligenceEngine().analyze(
        context=context,
        crop_cycle=context.crop_context,
    )

    # 6. Build one canonical transition-state adapter for both live L2
    # subpackages.  Downstream layers and the tribunal share this belief ID.
    output = Layer2CompositeOutput.from_parts(
        canonical=canonical,
        veg_temporal=veg_out,
    )
    output.scientific_state_envelope = _build_scientific_state_envelope(
        inputs=inputs, tensor=tensor, output=output,
    )
    output.belief_id = output.scientific_state_envelope.belief_id
    output.composite_diagnostics["canonical_state_adapter"] = {
        "status": "connected",
        "belief_id": output.belief_id,
        "content_hash": output.scientific_state_envelope.content_hash,
        "authority": "DIAGNOSTIC_NO_STATE_UPDATE",
    }
    return output


def _build_scientific_state_envelope(inputs: Any, tensor: Any, output: Any):
    """Adapt temporal vegetation and stress attribution into S[t]."""

    from services.agribrain.scientific_contracts import (
        AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
        ScientificStateEnvelopeV1,
    )

    temporal_run_id = str(getattr(output.veg_temporal, "run_id", "") or "")
    canonical_run_id = str(output.run_id or output.provenance.run_id or "l2-canonical")
    layer1_run_id = str(output.layer1_run_id or output.provenance.layer1_run_id or "l1-unresolved")
    identity_payload = {
        "canonical_run_id": canonical_run_id,
        "temporal_run_id": temporal_run_id,
        "layer1_run_id": layer1_run_id,
        "canonical_content_hash": output.content_hash(),
    }
    belief_id = "L2B-" + hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()

    # Derive hypothesis weights from Bayesian posterior probabilities P(H_k | E),
    # strictly separating diagnostic probability from physical/biological severity (Finding #23).
    by_type = {}
    for stress in output.stress_context:
        raw_type = getattr(stress, "stress_type", "UNRESOLVED") or "UNRESOLVED"
        key = str(getattr(raw_type, "value", raw_type)).upper()
        post_p = getattr(stress, "hypothesis_posterior", None)
        if post_p is None:
            post_p = getattr(stress, "damage_probability", None)
        if post_p is None:
            post_p = getattr(stress, "confidence", 0.0) or 0.0
        p_val = max(0.0, min(1.0, float(post_p)))
        # For multiple evidence items of the same stress type, retain maximum posterior probability
        by_type[key] = max(by_type.get(key, 0.0), p_val)

    # UNRESOLVED probability reflects joint residual non-occurrence under independent hypotheses:
    # P(UNRESOLVED) = prod(1 - P(H_k))
    explicit_unresolved = by_type.pop("UNRESOLVED", None)
    if explicit_unresolved is not None and explicit_unresolved > 0:
        residual_unresolved = explicit_unresolved
    else:
        residual_unresolved = 1.0
        for p in by_type.values():
            residual_unresolved *= (1.0 - min(0.95, p))
        residual_unresolved = max(0.05, min(1.0, residual_unresolved))

    # Normalize to strict probability distribution summing to 1.0
    total_mass = sum(by_type.values()) + residual_unresolved
    hypotheses = {
        key: round(value / total_mass, 6) for key, value in sorted(by_type.items())
    }
    # Ensure exact sum to 1.0 for contract validator
    assigned_sum = sum(hypotheses.values())
    hypotheses["UNRESOLVED"] = round(1.0 - assigned_sum, 6)

    generated_at = getattr(output, "generated_at", None)
    evidence_cutoff = (
        generated_at.isoformat() if hasattr(generated_at, "isoformat")
        else str(getattr(inputs, "date_range", {}).get("end") or "UNRESOLVED_TIME")
    )
    geometry_version = str(
        getattr(inputs, "geometry_hash", None)
        or getattr(tensor, "geometry_hash", None)
        or "UNRESOLVED_GEOMETRY"
    )
    worldline_head = str(
        getattr(inputs, "worldline_head_hash", None)
        or getattr(tensor, "worldline_head_hash", None)
        or f"layer1:{layer1_run_id}"
    )
    gaps = [
        str(getattr(gap, "variable", None) or getattr(gap, "reason", None) or gap)
        for gap in output.gaps_inherited
    ]
    limitations = [
        "transition_adapter_not_full_world_model",
        "temporal_and_stress_subpackages_share_identity_but_not_joint_dynamics",
    ]
    if output.data_health.status != "healthy":
        limitations.append(f"data_health:{output.data_health.status}")

    x_refs = tuple(value for value in (
        f"layer2-canonical:{canonical_run_id}",
        f"layer2-temporal:{temporal_run_id}" if temporal_run_id else "",
    ) if value)
    return ScientificStateEnvelopeV1(
        belief_id=belief_id,
        worldline_head=worldline_head,
        X_refs=x_refs,
        Z_ref=None,
        H_distribution=hypotheses,
        M_refs=(f"layer1:{layer1_run_id}",),
        U={
            "uncertainty": {
                "data_health": max(0.0, 1.0 - float(output.data_health.overall or 0.0)),
                "stress": max(
                    [float(getattr(item, "uncertainty", 0.0) or 0.0) for item in output.stress_context]
                    or [1.0]
                ),
            },
            "missingness": gaps,
            "ood_status": "UNRESOLVED",
            "limitations": limitations,
        },
        geometry_version=geometry_version,
        evidence_cutoff=evidence_cutoff,
        authority_vector=AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
    )

def build_context_from_tensor_fallback(tensor: Any) -> Layer2InputContext:
    """Fallback context builder when no Layer 1 package is attached to tensor.

    V91.2: Fallback context has unusable health — no L1 context means no real data.
    """
    return Layer2InputContext(
        plot_id=getattr(tensor, "plot_id", "unknown"),
        data_health=DataHealthScore(overall=0.0, status="unusable", confidence_ceiling=0.0),
    )

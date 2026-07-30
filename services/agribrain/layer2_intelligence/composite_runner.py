"""
Composite Runner — Coordinates vegetation modeling and canonical stress attribution.
Produces Layer2CompositeOutput.
"""

import copy
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

    # 6. Build and return Composite Output
    return Layer2CompositeOutput.from_parts(
        canonical=canonical,
        veg_temporal=veg_out,
    )

def build_context_from_tensor_fallback(tensor: Any) -> Layer2InputContext:
    """Fallback context builder when no Layer 1 package is attached to tensor.

    V91.2: Fallback context has unusable health — no L1 context means no real data.
    """
    return Layer2InputContext(
        plot_id=getattr(tensor, "plot_id", "unknown"),
        data_health=DataHealthScore(overall=0.0, status="unusable", confidence_ceiling=0.0),
    )

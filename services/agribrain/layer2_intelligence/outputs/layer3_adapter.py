"""
Layer 2 → Layer 3 Output Adapter.

Builds a clean Layer3InputContext from Layer2Output.
Layer 3 (Decision Engine) should not need raw L1 data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from layer1_fusion.schemas import DataHealthScore

from layer2_intelligence.schemas import Layer2Output


@dataclass
class Layer3InputContext:
    """What Layer 3 receives from Layer 2.

    Clean, actionable summary — no raw features, only interpreted intelligence.
    """
    plot_id: str = ""
    layer2_run_id: str = ""

    # Stress summary: stress_type → max_severity
    stress_summary: Dict[str, float] = field(default_factory=dict)

    # Per-zone stress map: zone_id → {dominant_type, severity, confidence}
    zone_status: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Vegetation status
    vegetation_status: Dict[str, Any] = field(default_factory=dict)

    # Phenology
    phenology_stage: str = "unknown"
    gdd_adjusted_vigor: Optional[float] = None

    # Quality gates
    data_health: DataHealthScore = field(default_factory=DataHealthScore)
    confidence_ceiling: float = 0.0
    usable_for_layer3: bool = False

    provenance_ref: str = ""
    flags: List[str] = field(default_factory=list)


def build_layer3_context(pkg: Layer2Output) -> Layer3InputContext:
    """Build the Layer 3 input payload from a Layer 2 output."""

    # Stress summary: max severity per type
    stress_summary: Dict[str, float] = {}
    for s in pkg.stress_context:
        current_max = stress_summary.get(s.stress_type, 0.0)
        stress_summary[s.stress_type] = max(current_max, s.severity)

    # Zone status
    zone_status: Dict[str, Dict[str, Any]] = {}
    for zone_id, zsm in pkg.zone_stress_map.items():
        zone_status[zone_id] = {
            "dominant_stress_type": zsm.dominant_stress_type,
            "severity": zsm.max_severity,
            "confidence": zsm.avg_confidence,
            "stress_count": zsm.stress_count,
        }

    # Vegetation status (plot-level features)
    veg_status: Dict[str, Any] = {}
    for vf in pkg.vegetation_intelligence:
        if vf.spatial_scope == "plot":
            veg_status[vf.name] = {
                "value": vf.value,
                "unit": vf.unit,
                "confidence": vf.confidence,
            }

    # Phenology
    stage = "unknown"
    vigor = None
    for pf in pkg.phenology_adjusted_indices:
        if pf.name == "gdd_adjusted_vigor":
            vigor = pf.value
            stage = pf.crop_stage
            break

    # Usability
    usable = (
        pkg.diagnostics.status != "unusable"
        and pkg.data_health.overall >= 0.2
    )

    return Layer3InputContext(
        plot_id=pkg.plot_id,
        layer2_run_id=pkg.run_id,
        stress_summary=stress_summary,
        zone_status=zone_status,
        vegetation_status=veg_status,
        phenology_stage=stage,
        gdd_adjusted_vigor=vigor,
        data_health=pkg.data_health,
        confidence_ceiling=pkg.data_health.confidence_ceiling,
        usable_for_layer3=usable,
        provenance_ref=pkg.run_id,
        flags=pkg.diagnostics.input_degradation_flags,
    )

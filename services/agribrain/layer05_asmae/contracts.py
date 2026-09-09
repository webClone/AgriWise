"""
ASMAE Data Contracts.

Formal contract definitions between ASMAE and adjacent layers.
Each contract specifies:
  - What ASMAE requires from the layer (input schema)
  - What ASMAE provides to the layer (output schema)
  - Invariants that must hold at the boundary

These contracts are the source of truth for integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================================
# Contract: Layer 0 → ASMAE
# ============================================================================

@dataclass
class Layer0ToASMAEContract:
    """What ASMAE requires from Layer 0 source acquisition.

    ASMAE needs per-scene source data, NOT pre-fused composites.
    Layer 0 must provide:
      - Individual scene metadata (time, CRS, transform, bands)
      - Quality masks (cloud, shadow, nodata, snow)
      - Sun/sensor geometry
      - SAR incidence angles
      - Source state package (acquisition log, failures)
    """
    required_fields: List[str] = field(default_factory=lambda: [
        "scene_id",
        "sensor",
        "acquisition_time",
        "crs",
        "transform",
        "width",
        "height",
        "band_refs",
        "mask_refs",
        "qa_score",
    ])

    optional_fields: List[str] = field(default_factory=lambda: [
        "sun_angles",
        "incidence_angle_ref",
        "cloud_fraction",
        "provenance_ref",
    ])

    invariants: List[str] = field(default_factory=lambda: [
        "scene_id must be unique within a run",
        "acquisition_time must be UTC ISO 8601",
        "CRS must be a valid EPSG code",
        "transform must be 6-element affine",
        "qa_score in [0, 1]",
        "band_refs must resolve to accessible artifacts",
    ])


# ============================================================================
# Contract: Layer 1 → ASMAE
# ============================================================================

@dataclass
class Layer1ToASMAEContract:
    """What ASMAE requires from Layer 1 coarse evidence fusion.

    ASMAE uses Layer 1's trust metrics and data health to weight
    scene reliability, but does NOT use Layer 1's fused composites
    as state truth — those are observations, not states.
    """
    required_fields: List[str] = field(default_factory=lambda: [
        "plot_id",
        "run_id",
        "time_window",
        "spatial_index",
        "fused_features",
        "state_summary",
        "source_health",
        "provenance",
        "diagnostics",
    ])

    optional_fields: List[str] = field(default_factory=lambda: [
        "conflicts",
        "gaps",
        "evidence_items",
        "layer2_input",
        "layer10_payload",
    ])

    invariants: List[str] = field(default_factory=lambda: [
        "Layer 1 composites are observations, NOT state truth",
        "Trust scores must be per-source, not aggregated",
        "Temporal coverage must include date ranges",
    ])


# ============================================================================
# Contract: Layers 2–8 → ASMAE (Coarse Priors)
# ============================================================================

@dataclass
class CoarseLayerPriorsContract:
    """What ASMAE requires from Layers 2–8 coarse pass (Pass A).

    ASMAE uses these as soft priors to constrain state estimation.
    Layer 8 outputs are constraints only — never truth.
    """
    layer_keys: Dict[str, List[str]] = field(default_factory=lambda: {
        "layer2_intelligence": [
            # Descriptive NDVI evidence is valid coarse input. Biological
            # stage authority still comes from the canonical phenology receipt.
            "ndvi_trajectory_phase",
            "ndvi_trajectory_position",
            "vigor",
            "phenology_stage",
            "growth_curve",
            "crop_identity_probability",
            "vegetation_trend",
            "stress_anomaly_envelope",
            "stage_specific_reliability",
        ],
        "layer3_water": [
            "et0",
            "soil_moisture",
            "water_stress",
            "irrigation_requirement",
            "water_balance",
        ],
        "layer4_nutrients": [
            "nutrient_demand",
            "chlorophyll_proxy",
            "salinity",
            "nue",
        ],
        "layer5_biotic": [
            "biotic_threat_risk",
            "disease_suitability",
            "outbreak_probability",
        ],
        "layer6_yield": [
            "yield_sensitivity",
            "economic_value_of_confidence",
            "scouting_roi_priority",
        ],
        "layer7_risk": [
            "climate_shock_risk",
            "scenario_outputs",
            "future_stress_windows",
        ],
        "layer8_action": [
            "do_not_prescribe_zones",
            "action_feasibility",
            "spray_drift_constraints",
            "salinity_leaching_constraints",
            "phenology_dosing_windows",
        ],
    })

    invariants: List[str] = field(default_factory=lambda: [
        "Layer 8 outputs are constraints only — NEVER ASMAE truth",
        "NDVI trajectory descriptors do not confer canonical phenology authority",
        "All priors must be versioned with run_id",
        "No future holdout leakage allowed",
        "Low-confidence ASMAE must never trigger irreversible Layer 8 action",
    ])


# ============================================================================
# Contract: ASMAE → Layer 1 (Refined Rasters)
# ============================================================================

@dataclass
class ASMAEToLayer1Contract:
    """What ASMAE provides back to Layer 1 refined pass.

    ASMAE-accepted rasters become typed evidence in Layer 1.
    They carry resolution metadata and confidence labels.
    """
    provided_fields: List[str] = field(default_factory=lambda: [
        "raster_maps",           # state → 2D grid
        "uncertainty_maps",      # state → 2D grid
        "confidence_maps",       # state → 2D grid
        "resolution_decision",   # selected resolution + reason
        "certification",         # plot certification status
        "provenance",            # full ASMAE run provenance
    ])

    invariants: List[str] = field(default_factory=lambda: [
        "All rasters must include uncertainty",
        "Resolution decision must include reason codes",
        "No ASMAE output may be called 'direct 1m satellite observation'",
        "Certification level must be explicit",
        "Content hash must be deterministic for same inputs",
    ])


# ============================================================================
# Contract: ASMAE → Layer 10 (Visual Surfaces)
# ============================================================================

@dataclass
class ASMAEToLayer10Contract:
    """What ASMAE provides to Layer 10 for rendering.

    Layer 10 consumes ASMAE surfaces only when confidence is sufficient.
    Surfaces below confidence threshold fall back to 10m baseline.
    """
    provided_fields: List[str] = field(default_factory=lambda: [
        "layer10_surfaces",      # pre-formatted for SIRE rendering
        "resolution_decision",   # for resolution display
        "confidence_maps",       # for adaptive fallback
        "retrovalidation_maps",  # for quality indicators
    ])

    invariants: List[str] = field(default_factory=lambda: [
        "Visual surfaces must respect resolution decision",
        "Low-confidence zones must fall back to 10m baseline",
        "1m display requires explicit certification",
        "Visual_intensity must be computed from ASMAE confidence",
    ])


# ============================================================================
# Contract Summary
# ============================================================================

ALL_CONTRACTS = {
    "layer0_to_asmae": Layer0ToASMAEContract,
    "layer1_to_asmae": Layer1ToASMAEContract,
    "coarse_priors_to_asmae": CoarseLayerPriorsContract,
    "asmae_to_layer1": ASMAEToLayer1Contract,
    "asmae_to_layer10": ASMAEToLayer10Contract,
}


def validate_contract(contract_name: str, data: Dict[str, Any]) -> List[str]:
    """Validate data against a named contract. Returns list of violations."""
    if contract_name not in ALL_CONTRACTS:
        return [f"Unknown contract: {contract_name}"]

    contract = ALL_CONTRACTS[contract_name]()
    violations = []

    if hasattr(contract, "required_fields"):
        for field_name in contract.required_fields:
            if field_name not in data or data.get(field_name) is None:
                violations.append(f"Missing required field: {field_name}")

    if hasattr(contract, "layer_keys"):
        for layer_name, scientific_fields in contract.layer_keys.items():
            layer = data.get(layer_name)
            if layer is None:
                violations.append(f"Missing coarse prior layer: {layer_name}")
                continue
            if not isinstance(layer, dict):
                violations.append(f"Coarse prior layer must be a mapping: {layer_name}")
                continue
            status = layer.get("status")
            if status not in ("available", "partial", "unavailable"):
                violations.append(f"Invalid coarse prior status: {layer_name}")
            for proof_field in ("source_layer", "source_timestamp", "evidence"):
                if proof_field not in layer:
                    violations.append(
                        f"Missing coarse prior proof field: {layer_name}.{proof_field}"
                    )
            if status in ("available", "partial") and not any(
                field_name in layer for field_name in scientific_fields
            ):
                violations.append(
                    f"No declared scientific field present: {layer_name}"
                )
        action = data.get("layer8_action")
        if isinstance(action, dict) and action.get("contains_recommendations") is True:
            violations.append("Layer 8 coarse pass must not contain recommendations")

    return violations

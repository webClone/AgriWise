"""
Layer 2 Intelligence — Canonical Schemas.

All data contracts for the Vegetation & Stress Intelligence engine.
Mirrors Layer 1 schema conventions: strict typing, full provenance,
uncertainty propagation, deterministic content_hash().

Vocabulary rules enforced here:
- Layer 2 produces EVIDENCE and ATTRIBUTION, never prescriptions.
- Forbidden terms: irrigate, apply, spray, harvest, prescribe, recommend, should, must
- Allowed terms: evidence, indicates, consistent_with, suggests, attributed_to, observed, detected
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

# Import shared types from Layer 1
from layer1_fusion.schemas import (
    DataHealthScore,
    EvidenceConflict,
    EvidenceGap,
    SpatialIndex,
    CropCycleContext,
)


# ============================================================================
# Vocabulary guardrails
# ============================================================================

FORBIDDEN_L2_VOCABULARY = (
    "irrigate", "apply", "spray", "harvest", "prescribe",
    "recommend", "should", "must", "action", "treatment",
    "dose", "schedule", "urgently",
)

ALLOWED_L2_VOCABULARY = (
    "evidence", "indicates", "consistent_with", "suggests",
    "attributed_to", "correlated_with", "observed", "detected",
    "elevated", "reduced", "deficit", "excess", "anomaly",
)

# ============================================================================
# Stress types
# ============================================================================

STRESS_TYPES = (
    "WATER",
    "NUTRIENT",
    "THERMAL",
    "BIOTIC",
    "PHOTOSYNTHETIC_SHUTDOWN",
    "MECHANICAL",
    "SALINITY",           # v3.2: Allbed & Kumar (2013)
    "UNKNOWN",
)

# ============================================================================
# Core intelligence dataclasses
# ============================================================================

@dataclass
class StressEvidence:
    """Single stress observation with multi-factor attribution.

    Layer 2 produces EVIDENCE, not prescriptions.
    Every stress item carries its full attribution chain.
    """
    stress_id: str
    stress_type: str                       # one of STRESS_TYPES
    severity: float = 0.0                  # 0.0–1.0 normalized
    confidence: float = 0.5                # 0.0–1.0
    uncertainty: float = 0.1               # propagated from L1

    spatial_scope: str = "plot"            # plot | zone
    scope_id: Optional[str] = None

    # Attribution basis (evidence-only, no prescriptions)
    primary_driver: str = ""               # e.g. "low_ndmi_adequate_precip"
    contributing_evidence_ids: List[str] = field(default_factory=list)
    # V91.2: Derived artifact references (from L2 enrichment, never real L1 evidence)
    derived_artifact_ids: List[str] = field(default_factory=list)
    # V91.2: Real upstream evidence the curve was fitted from (audit trail only)
    lineage_source_evidence_ids: List[str] = field(default_factory=list)
    explanation_basis: List[str] = field(default_factory=list)

    # Inherited quality
    data_health_at_attribution: float = 0.0
    diagnostic_only: bool = False

    # Temporal
    observed_at: Optional[datetime] = None

    # v3.2: Stress persistence classification (EWMA tracker)
    persistence_class: str = ""         # ACUTE | CHRONIC | TRANSIENT | ""
    persistence_ewma: float = 0.0       # Running EWMA severity value

    # v3.2: Compound stress synergy (Mittler 2006)
    compound_synergy_factor: float = 1.0  # 1.0 = no synergy, >1.0 = supra-additive
    compound_partner: str = ""            # Stress type that causes synergy

    flags: List[str] = field(default_factory=list)


@dataclass
class VegetationFeature:
    """Zone-aware vegetation metric."""
    name: str                              # vigor_index | uniformity_cv | canopy_cover_proxy | greenness_trend
    value: float = 0.0
    unit: str = "index"

    spatial_scope: str = "plot"
    scope_id: Optional[str] = None

    confidence: float = 0.5
    uncertainty: Optional[float] = None

    source_evidence_ids: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)


@dataclass
class PhenologyFeature:
    """Phenology-adjusted index."""
    name: str                              # gdd_adjusted_vigor | stage_expected_ndvi | deviation_from_expected
    value: float = 0.0
    unit: str = "index"

    crop_stage: str = "unknown"
    gdd_accumulated: float = 0.0

    confidence: float = 0.5
    uncertainty: Optional[float] = None

    explanation_basis: List[str] = field(default_factory=list)
    source_evidence_ids: List[str] = field(default_factory=list)


@dataclass
class ZoneStressSummary:
    """Per-zone aggregated stress profile."""
    zone_id: str = ""
    dominant_stress_type: Optional[str] = None
    stress_count: int = 0
    avg_severity: float = 0.0
    avg_confidence: float = 0.0
    max_severity: float = 0.0

    vegetation_features: List[VegetationFeature] = field(default_factory=list)
    stress_items: List[str] = field(default_factory=list)  # stress_ids
    flags: List[str] = field(default_factory=list)


# ============================================================================
# Provenance & Diagnostics
# ============================================================================

@dataclass
class Layer2Provenance:
    """Full provenance for Layer 2 output."""
    run_id: str = ""
    engine_version: str = "layer2_intelligence_v1"
    contract_version: str = "1.0.0"
    layer1_run_id: str = ""

    stress_count: int = 0
    vegetation_feature_count: int = 0
    phenology_feature_count: int = 0
    zone_count: int = 0

    invariant_violations: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: Optional[datetime] = None


# L2 hard prohibitions — evidence/interpretation boundary rules
L2_HARD_PROHIBITIONS = (
    "no_prescription_vocabulary",         # explanation_basis must not contain forbidden terms
    "no_action_recommendations",          # stress output must not prescribe actions
    "no_stress_from_diagnostic_only",     # diagnostic_only features can't drive severity > 0.5
    "no_stress_without_evidence",         # every stress must have ≥1 contributing_evidence_id
    "no_zone_stress_without_zone_ref",    # zone stress must reference a real zone in spatial_index
    "no_severity_above_confidence",       # severity must not exceed confidence (can't be more sure than data allows)
    "uncertainty_propagated",             # all stress items must have uncertainty > 0
    "data_health_inherited",              # L2 data_health must reflect L1 data_health
    "no_fabricated_evidence_ids",         # contributing_evidence_ids must reference real L1 evidence
    "content_hash_deterministic",         # same input → same hash
)


@dataclass
class Layer2Diagnostics:
    """Detailed diagnostics for Layer 2."""
    status: Literal["ok", "degraded", "unusable"] = "ok"

    data_health: DataHealthScore = field(default_factory=DataHealthScore)
    hard_prohibition_results: Dict[str, bool] = field(default_factory=dict)

    stress_type_counts: Dict[str, int] = field(default_factory=dict)
    zone_coverage: float = 0.0  # fraction of zones with stress assessment

    input_degradation_flags: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ============================================================================
# Layer 2 Output — the canonical output package
# ============================================================================

@dataclass
class Layer2Output:
    """Canonical output of the Layer 2 Vegetation & Stress Intelligence engine.

    Deterministic: same Layer2InputContext → same Layer2Output + content_hash().
    """
    schema_version: str = "layer2_v1"
    plot_id: str = ""
    run_id: str = ""
    layer1_run_id: str = ""
    generated_at: Optional[datetime] = None

    # Core intelligence
    vegetation_intelligence: List[VegetationFeature] = field(default_factory=list)
    stress_context: List[StressEvidence] = field(default_factory=list)
    phenology_adjusted_indices: List[PhenologyFeature] = field(default_factory=list)
    asmae_features: Dict[str, Any] = field(default_factory=dict)

    # Spatial
    spatial_index_ref: Optional[SpatialIndex] = None
    zone_stress_map: Dict[str, ZoneStressSummary] = field(default_factory=dict)

    # Quality & provenance
    data_health: DataHealthScore = field(default_factory=DataHealthScore)
    conflicts_inherited: List[EvidenceConflict] = field(default_factory=list)
    gaps_inherited: List[EvidenceGap] = field(default_factory=list)
    provenance: Layer2Provenance = field(default_factory=Layer2Provenance)
    diagnostics: Layer2Diagnostics = field(default_factory=Layer2Diagnostics)

    # Audit
    audit_log: List[Dict[str, Any]] = field(default_factory=list)

    def content_hash(self) -> str:
        """Deterministic hash for reproducibility verification."""
        payload = {
            "schema_version": self.schema_version,
            "plot_id": self.plot_id,
            "stress_count": len(self.stress_context),
            "veg_count": len(self.vegetation_intelligence),
            "pheno_count": len(self.phenology_adjusted_indices),
            "zone_count": len(self.zone_stress_map),
            "stress_types": sorted(set(s.stress_type for s in self.stress_context)),
            "stress_severities": [round(s.severity, 4) for s in self.stress_context],
            "veg_values": [round(v.value, 4) for v in self.vegetation_intelligence],
            "zone_ids": sorted(self.zone_stress_map.keys()),
            "health_overall": round(self.data_health.overall, 4),
            "health_status": self.data_health.status,
        }
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


# ============================================================================
# Layer 2 Input Bundle (thin wrapper for orchestrator convenience)
# ============================================================================

@dataclass
class Layer2CompositeOutput(Layer2Output):
    veg_temporal: Optional[Any] = None

    # compatibility aliases
    curve: Any = None
    phenology: Any = None
    anomalies: list = field(default_factory=list)
    stability: Any = None
    health_index: Any = None
    growth_metrics: Any = None
    zone_metrics: dict = field(default_factory=dict)
    
    # Composite diagnostics block
    composite_diagnostics: dict = field(default_factory=dict)

    @classmethod
    def from_parts(cls, canonical: Layer2Output, veg_temporal: Any) -> Layer2CompositeOutput:
        from dataclasses import fields
        kwargs = {}
        for f in fields(Layer2Output):
            kwargs[f.name] = getattr(canonical, f.name)

        # Pull alias values from veg_temporal if it exists
        curve = getattr(veg_temporal, "curve", None)
        phenology = getattr(veg_temporal, "phenology", None)
        anomalies = getattr(veg_temporal, "anomalies", [])
        stability = getattr(veg_temporal, "stability", None)
        health_index = getattr(veg_temporal, "health_index", None)
        growth_metrics = getattr(veg_temporal, "growth_metrics", None)
        zone_metrics = getattr(veg_temporal, "zone_metrics", {})

        # Compute temporal enrichment status
        is_degraded = getattr(veg_temporal, "run_id", "").endswith("_degraded") if veg_temporal else True
        obs_coverage = 0.0
        if curve is not None:
            q = getattr(curve, "quality", None)
            if q is not None:
                obs_coverage = getattr(q, "obs_coverage", 0.0)

        if not veg_temporal:
            enrichment_status = "skipped"
        elif is_degraded:
            enrichment_status = "degraded"
        elif obs_coverage < 0.60:
            enrichment_status = "diagnostic_only"
        else:
            enrichment_status = "used"

        comp_diag = {
            "composite_version": "v91_layer2_composite_v1",
            "veg_temporal_used": veg_temporal is not None,
            "canonical_stress_used": True,
            "temporal_enrichment_status": enrichment_status,
            "layer3_contract_status": "canonical",
            "legacy_bridge_expected": False,
            "evidence_policy_version": "v91_evidence_policy_v1"
        }

        return cls(
            veg_temporal=veg_temporal,
            curve=curve,
            phenology=phenology,
            anomalies=anomalies,
            stability=stability,
            health_index=health_index,
            growth_metrics=growth_metrics,
            zone_metrics=zone_metrics,
            composite_diagnostics=comp_diag,
            **kwargs
        )


@dataclass
class Layer2InputBundle:
    """Optional thin wrapper if orchestrator wants to add extra context
    beyond what Layer2InputContext provides.

    For most cases, the engine consumes Layer2InputContext directly.
    """
    layer2_input_context: Any = None  # Layer2InputContext from L1
    crop_cycle: Optional[CropCycleContext] = None
    run_id: str = ""
    run_timestamp: Optional[datetime] = None

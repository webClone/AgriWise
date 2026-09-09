"""Fail-closed diagnostic integration foundation for Layers 2--8."""

from typing import Tuple, List
from datetime import datetime, timezone
import hashlib

from .adapters import (
    ADAPTERS,
    AdapterContext,
    adapt_layer2,
    adapt_layer3,
    adapt_layer4,
    adapt_layer5,
    adapt_layer6,
    adapt_layer7,
    adapt_layer8,
)
from .contracts import (
    ContributionRole,
    DiagnosticContribution,
    IdentifiabilityClass,
    InfluenceUse,
)
from .dependency_graph import DependencyGraph, validate_dependency_map
from .influence import InfluenceEntry, InfluenceManifest, InfluenceManifestBuilder
from .ledger import ContributionLedger, ContributionLedgerEntry
from .registry import (
    DiagnosticEngineRegistration,
    DiagnosticRegistry,
    build_default_registry,
)
from .promotion_service import (
    DiagnosticPromotionService,
    PromotionResult,
)
from .runtime import (
    DiagnosticIntegrationResult,
    DiagnosticIntegrationRuntime,
    build_default_runtime,
)
from .tribunal import (
    ConsistencyTribunal,
    FindingSeverity,
    TribunalFinding,
    TribunalVerdict,
)

def pre_decision_tribunal(belief_id: str, context: dict) -> Tuple[TribunalVerdict, List[TribunalFinding]]:
    """Evaluates data quality, sensor confidence, and authority limits BEFORE decision planning."""
    findings: List[TribunalFinding] = []
    auth_level = str(context.get("authority_level") or context.get("authority") or "none")
    evidence_tier = str(context.get("evidence_tier") or context.get("state") or "unknown")
    blocked_ids = []
    cautioned_ids = []
    accepted_ids = ["l1_fusion", "l2_veg_int"]
    if auth_level != "asmae_certified":
        findings.append(TribunalFinding(
            code="AUTHORITY_UNAPPROVED",
            severity=FindingSeverity.CAUTION,
            contribution_ids=("l8_prescriptive",),
            target_state="1m_approval_allowed",
            message="1m approval and prescription driver authority blocked due to missing certification proof",
        ))
        cautioned_ids.append("l8_prescriptive")
    if evidence_tier in ("plot_level_observation_evidence", "unavailable"):
        findings.append(TribunalFinding(
            code="NO_SPATIAL_STACK",
            severity=FindingSeverity.BLOCK,
            contribution_ids=("l8_prescriptive",),
            target_state="spatial_scene_stack",
            message="No spatial scene stack available; restricting downstream decision authority",
        ))
        blocked_ids.append("l8_prescriptive")
    verdict = TribunalVerdict(
        input_belief_id=str(belief_id or "canonical_belief_head"),
        accepted_contribution_ids=tuple(accepted_ids),
        blocked_contribution_ids=tuple(blocked_ids),
        cautioned_contribution_ids=tuple(cautioned_ids),
        findings=tuple(findings),
    )
    return verdict, list(verdict.findings)

def post_execution_audit(results: dict) -> DiagnosticIntegrationResult:
    """Post-execution audit pass across completed layer results."""
    from services.agribrain.scientific_contracts.authority import (
        AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
    )

    runtime = build_default_runtime()
    belief_id = str(
        results.get("input_belief_id")
        or results.get("belief_id")
        or results.get("run_id")
        or "post-execution-audit"
    )
    parent_ids: Tuple[str, ...] = ()
    for layer_id in ("L2", "L3", "L4", "L5", "L6", "L7", "L8"):
        raw = results.get(layer_id)
        if raw is None:
            raw = results.get(layer_id.lower())
        output = getattr(raw, "output", raw)
        if output is None:
            continue
        contributions = runtime.ingest_layer(
            layer_id,
            output,
            AdapterContext(
                input_belief_id=belief_id,
                input_evidence_ids=(f"post-execution:{layer_id}",),
                input_contribution_ids=parent_ids,
                dependency_families=(f"post-execution:{layer_id}",),
                authority=AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE,
            ),
        )
        parent_ids = tuple(item.contribution_id for item in contributions)
    return runtime.finalize(belief_id, InfluenceUse.DIAGNOSIS)

__all__ = [
    "ADAPTERS",
    "AdapterContext",
    "ConsistencyTribunal",
    "ContributionLedger",
    "ContributionLedgerEntry",
    "ContributionRole",
    "DependencyGraph",
    "DiagnosticContribution",
    "DiagnosticEngineRegistration",
    "DiagnosticIntegrationResult",
    "DiagnosticIntegrationRuntime",
    "DiagnosticRegistry",
    "FindingSeverity",
    "IdentifiabilityClass",
    "InfluenceEntry",
    "InfluenceManifest",
    "InfluenceManifestBuilder",
    "InfluenceUse",
    "TribunalFinding",
    "TribunalVerdict",
    "adapt_layer2",
    "adapt_layer3",
    "adapt_layer4",
    "adapt_layer5",
    "adapt_layer6",
    "adapt_layer7",
    "adapt_layer8",
    "build_default_registry",
    "build_default_runtime",
    "validate_dependency_map",
    "DiagnosticPromotionService",
    "PromotionResult",
    "pre_decision_tribunal",
    "post_execution_audit",
]

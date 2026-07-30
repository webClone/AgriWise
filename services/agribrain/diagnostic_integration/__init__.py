"""Fail-closed diagnostic integration foundation for Layers 2--8."""

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
]

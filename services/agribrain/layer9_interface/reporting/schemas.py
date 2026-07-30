from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class ReportSubject:
    plot_id_hash: Optional[str] = None
    farm_id_hash: Optional[str] = None
    region_id: Optional[str] = None
    owner_identity_removed: bool = True
    coordinates_policy: str = "removed"  # removed | coarse | exact_internal_only
    aggregation_level: str = "plot"       # plot | farm | region | portfolio

@dataclass
class ReportDisclaimer:
    text: str
    reason: str
    severity: str = "WARNING"  # INFO | WARNING | CRITICAL

@dataclass
class ReportAuditBlock:
    generated_by: str = "AgriWise ReportEngine"
    report_engine_version: str = "v89_report_engine_v1"
    source_layers_used: List[str] = field(default_factory=list)
    no_effect_guard_passed: bool = True
    suppressed_fields: List[str] = field(default_factory=list)
    privacy_policy_applied: str = "v89_privacy_policy_v1"
    evidence_classifier_version: str = "v89_evidence_classifier_v1"

@dataclass
class EvidenceWindow:
    start_date: Optional[str] = None
    end_date: Optional[str] = None

@dataclass
class InstitutionalReport:
    report_schema_version: str
    report_policy_version: str

    report_id: str
    report_type: str
    scope: str
    generated_at: str

    subject: ReportSubject
    evidence_window: EvidenceWindow

    confidence: float
    uncertainty: float
    data_completeness: float

    evidence_tiers: Dict[str, int] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)

    provenance_hashes: Dict[str, Optional[str]] = field(default_factory=dict)
    report_input_hash: str = ""
    verified_evidence_hash: str = ""
    report_content_hash: str = ""
    report_instance_hash: str = ""

    limitations: List[str] = field(default_factory=list)
    disclaimers: List[ReportDisclaimer] = field(default_factory=list)
    audit: ReportAuditBlock = field(default_factory=ReportAuditBlock)

    # V89 Boundary Visible Invariants
    reporting_only: bool = True
    state_mutation_allowed: bool = False
    training_allowed: bool = False
    certification_allowed: bool = False

@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source_layer: str
    source_type: str
    variable: str
    value: Any
    confidence: float
    uncertainty: float
    provenance_hash: str
    timestamp: Optional[str] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ClassifiedEvidence:
    evidence_id: str
    tier: str
    institutional_admissibility: str  # proof | supporting | diagnostic | excluded
    source_layer: str
    source_type: str
    variable: str
    value: Any
    confidence: float
    uncertainty: float
    validation_status: str
    certification_status: Optional[str]
    can_support_claim: bool
    can_support_investor_metric: bool
    can_support_government_aggregate: bool
    exclusion_reasons: List[str]
    provenance_hash: str
    certification_reason_codes: List[str] = field(default_factory=list)


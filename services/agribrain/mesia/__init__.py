"""
MESIA — Multi-Environment Spectrum Intelligence Architecture.

R6 Full-Scale Multi-Radio Implementation — Phase P0 Contract Freeze.

MESIA discovers, identifies and models radio behaviour across multiple
front-end classes. It produces calibrated evidence proposals for ASMAE;
it does NOT own the agricultural posterior.

Design rules (constitutional principles P-01 through P-10):
  1. No universal-receiver fiction — coverage manifests before scans.
  2. Discover before identify — detection precedes protocol naming.
  3. Identify before sense — agricultural interpretation requires
     PROTOCOL_CONFIRMED or CONTROLLED_SOURCE.
  4. Native evidence survives — IQ/CSI/range/radar cubes are immutable.
  5. No raw-phase stitching across independent RATs.
  6. Configuration is part of the measurement — epochs are mandatory.
  7. UNKNOWN is a valid result — never force into known classes.
  8. ASMAE owns the posterior — MESIA emits proposals only.
  9. Capabilities qualify separately — no global cluster certificate.
  10. Fail closed and revoke — failed gates demote automatically.
"""

from __future__ import annotations

MESIA_VERSION = "0.1.0"
MESIA_SCHEMA_VERSION = "mesia_r6_p0"
MESIA_CONTRACT_VERSION = "mesia_contract_v1_p0_freeze"

# Re-exports from subpackages
from .ontology import (
    IdentityState,
    IdentityStateMachine,
    VALID_IDENTITY_TRANSITIONS,
    InvalidIdentityTransition,
    CoverageOutcome,
    ConfirmationLevel,
    EvidenceRole,
    CapabilityState,
    CapabilityLifecycle,
    VALID_CAPABILITY_TRANSITIONS,
    InvalidCapabilityTransition,
    FrontEndClass,
)

from .contracts import (
    GeometryEpoch,
    InstrumentEpoch,
    NetworkEpoch,
    CoexistenceEpoch,
    CalibrationState,
    SoftwareModelEpoch,
    SpectrumCalibrationEpoch,
    ReceiverCapabilityManifest,
    AntennaPathManifest,
    CoverageGraph,
    CoverageTuple,
    WaveCandidate,
    WaveSurveyPlan,
    SignalIdentityHypothesis,
    ProtocolConfirmationReceipt,
    RadioBehaviourContract,
    BehaviourLikelihood,
    RadioObservationPacket,
    ObservabilityCertificate,
    ClosureCertificate,
    CapabilityAuthorityRecord,
    RevocationEvent,
    SensingTaskReceipt,
)

from .constitution import (
    ConstitutionalViolation,
    check_p01_no_universal_receiver,
    check_p02_discover_before_identify,
    check_p03_identify_before_sense,
    check_p04_native_evidence_survives,
    check_p05_no_raw_phase_stitching,
    check_p06_configuration_is_measurement,
    check_p07_unknown_is_valid,
    check_p08_asmae_owns_posterior,
    check_p09_capabilities_qualify_separately,
    check_p10_fail_closed_and_revoke,
    validate_observation_packet,
    SupportedFamily,
    ExcludedClaim,
    TargetState,
    EXCLUDED_CLAIMS,
)

from .radio_families import (
    RadioFamily,
    RadioFamilyProfile,
    RADIO_FAMILY_REGISTRY,
    get_radio_family_profile,
    list_supported_families,
)

from .metrology import (
    DistributionType,
    UncertaintyComponent,
    UncertaintyBudget,
    make_type_a_component,
    make_type_b_component,
    ClockStabilityReport,
    calculate_allan_deviation,
    estimate_time_uncertainty_growth,
    TriggerLatencyCharacterization,
    SParameterMeasurement,
    RFBenchTestReport,
    calculate_cascaded_noise_figure,
    calculate_p1db_and_iip3,
    TraceabilityNode,
    CalibrationCertificate,
    OutOfToleranceDetector,
)

from .truth import (
    SoilTextureClass,
    HysteresisBranch,
    SoilStratumMeasurement,
    SoilColumnExperimentRecord,
    CanopySurfaceTruthRecord,
    SentinelFixtureType,
    SentinelVerificationResult,
)

from .control_plane import (
    ReceiverInterrogator,
    HardwareInterrogationError,
    CoverageEngine,
    JurisdictionRegion,
    FrequencyBandPolicy,
    JurisdictionProfile,
    get_default_algeria_profile,
    PrioritizedScanObjective,
    ScanPlanCompiler,
    DiagnosticSelfTestReport,
    SelfTestRunner,
    CoverageAuditResult,
    CoverageAuditor,
)

from .discovery import (
    NoiseFloorEstimate,
    NoiseBaselineTracker,
    DetectionPeak,
    DetectorBank,
    TimeFrequencySegmenter,
    AssociatedBurstSequence,
    BurstAssociator,
    CorroboratedEventRecord,
    MultiObserverCorroborator,
    EscalationDecision,
    EscalationPlan,
    CaptureEscalationController,

    RadioTopologyNode,
    MultiHopRadioGraph,
    MultiHopRadioMeshHopper,
)

from .identity import (
    RuleMatchResult,
    DeterministicProtocolRules,
    CorrelatorEngine,
    OpenSetClassificationResult,
    OpenSetWaveformClassifier,
    EvidenceFusionEngine,
    AmbiguityManager,
    SignalIdentityProfile,
    SignalIdentityProfileRegistry,
)

from .lanes import (
    WifiCsiFrame,
    WifiCsiLaneAdapter,
    CellularObservationRecord,
    CellularLaneAdapter,
    LoRaObservationRecord,
    LoRaSubGhzLaneAdapter,
    GnssReflectometryRecord,
    GnssLaneAdapter,
    RfidObservationRecord,
    RfidLaneAdapter,
    GprTraceRecord,
    UwbGprLaneAdapter,
    MmWaveRadarFrame,
    MmWaveRadarLaneAdapter,
    CoexistenceEventRecord,
    CoexistenceTransportLaneAdapter,
    ConformanceValidationReport,
    LaneConformanceValidator,
)

from .epoch_authority import (
    TimeSourceType,
    TimeQualityReport,
    TimeAuthority,
    LocalEnuPoint,
    SpatialCoordinateAuthority,
    AntennaPoseRecord,
    AntennaPoseAuthority,
    ReceiverActiveEpochState,
    CentralEpochAuthority,
    DriftEvaluationResult,
    DriftSentinelMonitor,
)

from .behaviour import (
    BEHAVIOUR_CONTRACT_REGISTRY,
    get_behaviour_contract,
    ExtractedBehaviourFeatures,
    NativeFeatureExtractor,
    TimeScaleDomain,
    MultiClockTimeWindow,
    MultiClockCoordinator,
    NuisanceAttributionReport,
    BayesianNuisanceModel,
    AgriculturalRegime,
    GrammarValidationResult,
    ResponseGrammarEngine,
    CausalProbePlan,
    CausalProbePlanner,
    BehaviourLikelihoodEngine,
    ModelCard,
)

from .experiments import (
    BenchExperimentResult,
    BenchExperimentHarness,
    SoilColumnTrialSummary,
    SoilColumnExperimentHarness,
    FieldPlotTrialReport,
    FieldPlotExperimentHarness,
    ClosureVerificationReport,
    MultiRadioClosureHarness,
    ChallengeExecutionResult,
    NuisanceChallengeMatrixHarness,
    OperatorSurveySummary,
    PublicCellularSurveyHarness,
    ExternalTransferEvaluationResult,
    ExternalTransferHarness,
    NegativeControlResult,
    TeacherControlComparison,
    TeacherControlsAuthority,
    LivingObservatoryAuditReport,
    LivingObservatoryExperimentRunner,
)

from .assimilation import (
    LatticeStrata,
    MicrozoneCell,
    SharedBeliefLattice,
    LinkSensitivityProfile,
    SensitivityKernelCalculator,
    ObservabilityAnalyzer,
    MultiRadioClosureEngine,
    ASMAEInnovationProposal,
    ASMAEObservationOperator,
    EvidenceAdmissionStatus,
    Layer0EvidenceRecord,
    Layer0EvidenceSpine,
    CapabilityGovernanceAuthority,
)

from .cellular import (
    CellularTier,
    TierValidationRecord,
    CellularTierValidator,
    OperatorEvidenceBundle,
    OranE2NodeStatus,
    OranConnector,
)

from .planning import (
    CapabilityCard,
    CAPABILITY_CARD_CATALOGUE,
    PlannedMeasurementTask,
    L7MeasurementPlanner,
    PolicyGuardrailCheck,
    L8PolicyGuardrails,
    DeploymentMode,
    TopologyType,
    MESIADeploymentDesigner,
)

from .operations import (
    NodeHealthSnapshot,
    FleetOperationsMonitor,
    SecurityAuditRecord,
    SecurityGovernanceManager,
    SiteSurveyInput,
    PlannedNodePlacement,
    CommissioningCheckItem,
    DeploymentPlan,
    DeploymentDesigner,
)

from .storage import (
    SigMFMetadata,
    SigMFCapture,
    SigMFAnnotation,
    SigMFAdapter,
    RinexObservationHeader,
    RinexSatelliteObservation,
    RinexAdapter,
)

from .omega import (
    AggregationScale,
    AggregatedEvidenceSummary,
    HierarchicalAggregator,
    ScientificSurpriseHypothesis,
    OmegaSurpriseDetector,
    ProposedScientificExperiment,
    OmegaExperimentProposer,
)

from .integration import MesiaAgriBrainBridge
from .integration_layer3 import (
    MesiaHydrologicalComparison,
    MesiaLayer3WaterBridge,
)

__all__ = [
    # Metadata
    "MESIA_VERSION",
    "MESIA_SCHEMA_VERSION",
    "MESIA_CONTRACT_VERSION",
    # Ontology
    "IdentityState",
    "IdentityStateMachine",
    "VALID_IDENTITY_TRANSITIONS",
    "InvalidIdentityTransition",
    "CoverageOutcome",
    "ConfirmationLevel",
    "EvidenceRole",
    "CapabilityState",
    "CapabilityLifecycle",
    "VALID_CAPABILITY_TRANSITIONS",
    "InvalidCapabilityTransition",
    "FrontEndClass",
    # Contracts
    "GeometryEpoch",
    "InstrumentEpoch",
    "NetworkEpoch",
    "CoexistenceEpoch",
    "CalibrationState",
    "SoftwareModelEpoch",
    "SpectrumCalibrationEpoch",
    "ReceiverCapabilityManifest",
    "AntennaPathManifest",
    "CoverageGraph",
    "CoverageTuple",
    "WaveCandidate",
    "WaveSurveyPlan",
    "SignalIdentityHypothesis",
    "ProtocolConfirmationReceipt",
    "RadioBehaviourContract",
    "BehaviourLikelihood",
    "RadioObservationPacket",
    "ObservabilityCertificate",
    "ClosureCertificate",
    "CapabilityAuthorityRecord",
    "RevocationEvent",
    "SensingTaskReceipt",
    # Constitution
    "ConstitutionalViolation",
    "check_p01_no_universal_receiver",
    "check_p02_discover_before_identify",
    "check_p03_identify_before_sense",
    "check_p04_native_evidence_survives",
    "check_p05_no_raw_phase_stitching",
    "check_p06_configuration_is_measurement",
    "check_p07_unknown_is_valid",
    "check_p08_asmae_owns_posterior",
    "check_p09_capabilities_qualify_separately",
    "check_p10_fail_closed_and_revoke",
    "validate_observation_packet",
    "SupportedFamily",
    "ExcludedClaim",
    "TargetState",
    "EXCLUDED_CLAIMS",
    # Radio Families
    "RadioFamily",
    "RadioFamilyProfile",
    "RADIO_FAMILY_REGISTRY",
    "get_radio_family_profile",
    "list_supported_families",
    # Metrology
    "DistributionType",
    "UncertaintyComponent",
    "UncertaintyBudget",
    "make_type_a_component",
    "make_type_b_component",
    "ClockStabilityReport",
    "calculate_allan_deviation",
    "estimate_time_uncertainty_growth",
    "TriggerLatencyCharacterization",
    "SParameterMeasurement",
    "RFBenchTestReport",
    "calculate_cascaded_noise_figure",
    "calculate_p1db_and_iip3",
    "TraceabilityNode",
    "CalibrationCertificate",
    "OutOfToleranceDetector",
    # Truth
    "SoilTextureClass",
    "HysteresisBranch",
    "SoilStratumMeasurement",
    "SoilColumnExperimentRecord",
    "CanopySurfaceTruthRecord",
    "SentinelFixtureType",
    "SentinelVerificationResult",
    # Control Plane
    "ReceiverInterrogator",
    "HardwareInterrogationError",
    "CoverageEngine",
    "JurisdictionRegion",
    "FrequencyBandPolicy",
    "JurisdictionProfile",
    "get_default_algeria_profile",
    "PrioritizedScanObjective",
    "ScanPlanCompiler",
    "DiagnosticSelfTestReport",
    "SelfTestRunner",
    "CoverageAuditResult",
    "CoverageAuditor",
    # Discovery
    "NoiseFloorEstimate",
    "NoiseBaselineTracker",
    "DetectionPeak",
    "DetectorBank",
    "TimeFrequencySegmenter",
    "AssociatedBurstSequence",
    "BurstAssociator",
    "CorroboratedEventRecord",
    "MultiObserverCorroborator",
    "EscalationDecision",
    "EscalationPlan",
    "CaptureEscalationController",

    # Multi-Hop Radio Mesh Hopper (§4/§14)
    "RadioTopologyNode",
    "MultiHopRadioGraph",
    "MultiHopRadioMeshHopper",
    # Identity
    "RuleMatchResult",
    "DeterministicProtocolRules",
    "CorrelatorEngine",
    "OpenSetClassificationResult",
    "OpenSetWaveformClassifier",
    "EvidenceFusionEngine",
    "AmbiguityManager",
    "SignalIdentityProfile",
    "SignalIdentityProfileRegistry",
    # Lanes
    "WifiCsiFrame",
    "WifiCsiLaneAdapter",
    "CellularObservationRecord",
    "CellularLaneAdapter",
    "LoRaObservationRecord",
    "LoRaSubGhzLaneAdapter",
    "GnssReflectometryRecord",
    "GnssLaneAdapter",
    "RfidObservationRecord",
    "RfidLaneAdapter",
    "GprTraceRecord",
    "UwbGprLaneAdapter",
    "MmWaveRadarFrame",
    "MmWaveRadarLaneAdapter",
    "CoexistenceEventRecord",
    "CoexistenceTransportLaneAdapter",
    "ConformanceValidationReport",
    "LaneConformanceValidator",
    # Epoch Authority
    "TimeSourceType",
    "TimeQualityReport",
    "TimeAuthority",
    "LocalEnuPoint",
    "SpatialCoordinateAuthority",
    "AntennaPoseRecord",
    "AntennaPoseAuthority",
    "ReceiverActiveEpochState",
    "CentralEpochAuthority",
    "DriftEvaluationResult",
    "DriftSentinelMonitor",
    # Behaviour & ASMAE Interface
    "BEHAVIOUR_CONTRACT_REGISTRY",
    "get_behaviour_contract",
    "ExtractedBehaviourFeatures",
    "NativeFeatureExtractor",
    "TimeScaleDomain",
    "MultiClockTimeWindow",
    "MultiClockCoordinator",
    "NuisanceAttributionReport",
    "BayesianNuisanceModel",
    "AgriculturalRegime",
    "GrammarValidationResult",
    "ResponseGrammarEngine",
    "CausalProbePlan",
    "CausalProbePlanner",
    "BehaviourLikelihoodEngine",
    "ModelCard",
    # Experiments & Living Observatory
    "BenchExperimentResult",
    "BenchExperimentHarness",
    "SoilColumnTrialSummary",
    "SoilColumnExperimentHarness",
    "FieldPlotTrialReport",
    "FieldPlotExperimentHarness",
    "ClosureVerificationReport",
    "MultiRadioClosureHarness",
    "ChallengeExecutionResult",
    "NuisanceChallengeMatrixHarness",
    "OperatorSurveySummary",
    "PublicCellularSurveyHarness",
    "ExternalTransferEvaluationResult",
    "ExternalTransferHarness",
    "NegativeControlResult",
    "TeacherControlComparison",
    "TeacherControlsAuthority",
    "LivingObservatoryAuditReport",
    "LivingObservatoryExperimentRunner",
    # Assimilation & Governance
    "LatticeStrata",
    "MicrozoneCell",
    "SharedBeliefLattice",
    "LinkSensitivityProfile",
    "SensitivityKernelCalculator",
    "ObservabilityAnalyzer",
    "MultiRadioClosureEngine",
    "ASMAEInnovationProposal",
    "ASMAEObservationOperator",
    "EvidenceAdmissionStatus",
    "Layer0EvidenceRecord",
    "Layer0EvidenceSpine",
    "CapabilityGovernanceAuthority",
    # Cellular Framework (P11)
    "CellularTier",
    "TierValidationRecord",
    "CellularTierValidator",
    "OperatorEvidenceBundle",
    "OranE2NodeStatus",
    "OranConnector",
    # Planning & Guardrails (P12)
    "CapabilityCard",
    "CAPABILITY_CARD_CATALOGUE",
    "PlannedMeasurementTask",
    "L7MeasurementPlanner",
    "PolicyGuardrailCheck",
    "L8PolicyGuardrails",
    "DeploymentMode",
    "TopologyType",
    "MESIADeploymentDesigner",
    # Operations & Security (P13)
    "NodeHealthSnapshot",
    "FleetOperationsMonitor",
    "SecurityAuditRecord",
    "SecurityGovernanceManager",
    # Deployment Designer (P10)
    "SiteSurveyInput",
    "PlannedNodePlacement",
    "CommissioningCheckItem",
    "DeploymentPlan",
    "DeploymentDesigner",
    # Native Storage Adapters (§8.2)
    "SigMFMetadata",
    "SigMFCapture",
    "SigMFAnnotation",
    "SigMFAdapter",
    "RinexObservationHeader",
    "RinexSatelliteObservation",
    "RinexAdapter",
    # Omega Scientific Automation (P14)
    "AggregationScale",
    "AggregatedEvidenceSummary",
    "HierarchicalAggregator",
    "ScientificSurpriseHypothesis",
    "OmegaSurpriseDetector",
    "ProposedScientificExperiment",
    "OmegaExperimentProposer",
    # Integration Bridges
    "MesiaAgriBrainBridge",
    "MesiaHydrologicalComparison",
    "MesiaLayer3WaterBridge",
]

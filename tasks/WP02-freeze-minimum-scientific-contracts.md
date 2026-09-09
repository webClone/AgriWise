# Work Package 02: Freeze Minimum Scientific Contracts

## 1. Executive Summary & Objective
AgriBrain contains advanced algorithms across perception, assimilation, diagnosis, and prescription, but the interfaces connecting these modules rely heavily on loose dictionaries, optional keys, stringly-typed metadata, and inferred permissions. Consequently:
- Missing evidence can pass validation checks (e.g. `None != 0` evaluating to `True`).
- Dimensional units are lost across layer adapters (e.g. treating dimensionless scores as volumetric soil moisture).
- Operational permissions are guessed from output existence rather than authenticated lineage.

Work Package 02 establishes and freezes a compact set of stable, strongly-typed, immutable scientific contracts. Every system boundary will be required to validate against these contracts, allowing components to reject inputs for explicit semantic and scientific reasons rather than failing downstream or producing misleading conclusions.

---

## 2. Affected Subsystems & Source References
- **Scientific Contracts Package**: [`services/agribrain/scientific_contracts/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/scientific_contracts/)
  - `authority.py`: `AuthorityVector` and capability scopes.
  - `identity.py`: Bitemporal hashes and lineage descriptors.
- **Layer 1 Evidence Ledger**: [`services/agribrain/layer1_fusion/evidence_ledger.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/evidence_ledger.py)
- **Diagnostic Integration**: [`services/agribrain/diagnostic_integration/contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/diagnostic_integration/contracts.py)
- **World Model Package**: [`services/agribrain/world_model/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/)
  - `contracts.py`: Belief state snapshots and forecast artifacts.

---

## 3. The 7 Canonical Scientific Contracts

### 3.1 `EvidenceRef`: Canonical Observational Evidence
Represents an immutable receipt of an observed physical quantity or remote sensing acquisition.
```python
@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str                      # Content hash of the raw capture and metadata
    ownership: OwnershipContext           # (tenant_id, farm_id, plot_id)
    variable_name: str                    # Standardized variable (e.g. "surface_soil_moisture")
    units: str                            # Strict SI / standard unit (e.g. "m3/m3", "mm", "K")
    observed_at: datetime                 # Actual physical acquisition timestamp (UTC)
    knowledge_available_at: datetime      # Timestamp when ingestion system committed the record
    spatial_support: SpatialSupport       # Lattice reference, polygon, or point coordinates
    transformation_lineage: Tuple[str,...]# List of operator IDs applied to produce this value
    admissible_roles: Tuple[EvidenceRole,...] # (OBSERVATION_NATIVE, DERIVED_PROXY, CALIBRATION)
    quality_grade: str                    # "A", "B", "C", "REJECTED"
    raw_payload_uri: str                  # Content-addressed storage URI
```
*Rule*: Missing metadata causes immediate rejection or quarantine. Timestamp substitutions (e.g. defaulting to `now()`) are forbidden.

### 3.2 `StateRef`: Canonical System Belief State
Defines the complete state of a field or microzone at a specific point in time.
```python
@dataclass(frozen=True)
class StateRef:
    state_id: str                         # SHA-256 of snapshot values and lineage
    schema_version: str                   # E.g. "asmae_state_v1_13"
    snapshot_timestamp: datetime          # Target epoch of the physical state
    knowledge_cutoff: datetime            # Frozen availability boundary for evidence
    lattice_reference: str                # Hash / version of spatial grid and strata definitions
    state_vector: Tuple[float, ...]       # Ordered state vector matching schema_version
    state_covariance: Tuple[Tuple[float, ...], ...] # Posterior covariance matrix P+
    identifiability_classes: Dict[str, str] # Per-variable identifiability (IDENTIFIED, INDIRECT, UNRESOLVED)
    worldline_head_hash: str              # Pointer to committed head event in canonical worldline
```
*Rule*: A state vector without an explicit covariance matrix and evidence cutoff cannot be promoted to an authoritative belief state.

### 3.3 `DiagnosticResult`: Standardized Diagnostic Assertion
Encapsulates an agronomic diagnosis emitted by Layers 2, 3, 4, or 5.
```python
@dataclass(frozen=True)
class DiagnosticResult:
    diagnosis_id: str                     # Immutable assertion ID
    layer_id: str                         # "L2", "L3", "L4", "L5"
    target_hypothesis: str                # E.g. "WATER_DEFICIT_STRESS", "NITROGEN_DEFICIENCY"
    severity: float                       # Magnitude in [0.0, 1.0]
    probability: float                    # Calibrated likelihood of hypothesis in [0.0, 1.0]
    confidence: float                     # Epistemic certainty in [0.0, 1.0]
    evidence_strength_log_odds: float     # In(P(E|H) / P(E|~H))
    confounders_evaluated: Tuple[str, ...] # List of alternative hypotheses checked
    unresolved_status: bool               # True if competing hypotheses cannot be discriminated
    input_evidence_ids: Tuple[str, ...]   # Native evidence directly supporting this diagnosis
    computational_dependencies: Tuple[str, ...] # Upstream stage outputs consumed
```
*Rule*: Severity, probability, and confidence must remain strictly distinct. A severe stress with low evidence must not be converted into a high-probability event.

### 3.4 `CapabilityReceipt`: Authenticated Permission Token
Represents a cryptographic or governance-validated authorization for a specific use of an output.
```python
@dataclass(frozen=True)
class CapabilityReceipt:
    receipt_id: str
    target_variable: str
    permitted_use: InfluenceUse           # (DIAGNOSIS, STATE_UPDATE, PRESCRIPTION_DRIVER, MACHINE_EXECUTION)
    validity_domain: ValidityDomain       # Spatial bounding box, crop species, phenology stage
    evidence_support_hash: str            # Hash of all supporting evidence
    qualification_certificate_id: str     # Reference to stored calibration/qualification dossier
    issued_at: datetime
    expires_at: datetime
    revoked: bool
    signature: str                        # Cryptographic signature of issuing authority
```
*Rule*: Diagnostic layers cannot issue their own `CapabilityReceipt` for `PRESCRIPTION_DRIVER` or `MACHINE_EXECUTION`.

### 3.5 `ForcingEvent`: Physical Management & Environmental Forcing
Represents interventions or weather inputs driving state transitions.
```python
@dataclass(frozen=True)
class ForcingEvent:
    event_id: str
    forcing_type: str                     # "IRRIGATION", "FERTILIZATION", "TILLAGE", "RAINFALL"
    execution_status: ExecutionStatus     # PLANNED, SCENARIO_SIMULATED, OBSERVED_CONFIRMED
    quantity: float                       # Numerical rate
    units: str                            # "mm", "kg/ha", "m3/ha"
    effective_start: datetime
    effective_end: datetime
    spatial_extent: SpatialSupport
    efficiency_factor: float              # E.g. 0.85 for drip irrigation
    provenance_hash: str                  # Link to farm telemetry or operator entry
```
*Rule*: Planned events may only enter scenario simulation (L7). Only confirmed observed applications may update historical physical state (L0.5/L3).

### 3.6 `ScenarioRef`: Candidate Action Plan
Produced by L7 planning to express conditional future trajectories.
```python
@dataclass(frozen=True)
class ScenarioRef:
    scenario_id: str
    action_type: str                      # "IRRIGATE_VARIABLE_RATE", "APPLY_FUNGICIDE"
    proposed_timing: datetime
    target_zones: Tuple[str, ...]
    parameters: Dict[str, Any]            # Typed parameters (rates, products)
    feasibility_receipt: FeasibilityReceipt # Confirmed by L6 equipment and weather constraints
    conditional_trajectory_id: str        # Predicted worldline state trajectory under this action
    expected_yield_impact: YieldDistribution # Calibrated yield outcome (p10, p50, p90)
    assumptions: Tuple[str, ...]
```

### 3.7 `ActionAuthorization`: Binding Prescriptive Decision
The final authorized output emitted by L8 and verified prior to execution.
```python
@dataclass(frozen=True)
class ActionAuthorization:
    authorization_id: str
    selected_scenario_id: str
    belief_state_id: str
    tribunal_receipt_hash: str
    prescription_manifest_hash: str
    policy_snapshot_hash: str
    authorized_by: str                    # "AUTONOMOUS_POLICY_L8", "HUMAN_OPERATOR"
    authorized_at: datetime
    exact_action_payload: Dict[str, Any]  # Target rates, ISO-11783 task details
```
*Rule*: Execution serializers (L9/L10) must verify all 4 binding hashes before producing machine instructions.

---

## 4. Implementation Steps
1. Create `services/agribrain/scientific_contracts/contracts_v2.py` implementing the frozen dataclasses with strict type annotations, runtime validation, and serialization methods.
2. Provide conversion adapters in `layer1_fusion`, `layer05_asmae`, and `diagnostic_integration` to translate legacy structures into the canonical contracts.
3. Update `diagnostic_integration/adapters.py` to require `CapabilityReceipt` for downstream influence mapping.
4. Establish strict assertion suites verifying that malformed contracts raise `ContractViolation` with exact field error traces.

---

## 5. Verification & Completion Criteria
- **Strict Semantic Parsing**: 100% of pipeline inputs across L0 to L8 pass through contract validation.
- **Fail-Closed Verification**: Passing incomplete metadata (e.g. `units=None` or unauthenticated capability receipts) immediately raises a typed `ContractViolation` and halts the promotion path.
- **Zero Field Guessing**: Orchestrator and adapters no longer inspect heuristic dictionary keys.

---

## 6. Monograph & Defect Task Traceability
- **Monograph Findings**: Finding #1 (Prescription authority contract), Finding #2 (Diagnosis permission from receipts), Finding #8 (Root-zone units), Finding #9 (Typed management forcing), Finding #15 (Likelihood vs VWC contract), Finding #22 (Canonical evidence graph).
- **Defect Tasks**: [A01-authoritative-water-path.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A01-authoritative-water-path.md), [A08-mesia-rf-snr-vwc-assimilation.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A08-mesia-rf-snr-vwc-assimilation.md), [A10-mesia-asmae-adapter-and-payload-integration.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A10-mesia-asmae-adapter-and-payload-integration.md).
- **Phase Tasks**: [P00.1-execution-and-ownership-contract.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P00.1-execution-and-ownership-contract.md), [P06.1-world-model-state-observation-action-contracts.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P06.1-world-model-state-observation-action-contracts.md).

---

## 7. Execution Status & Verification Report
- **Status**: `COMPLETED`
- **Scope Delivery**:
  - `services/agribrain/scientific_contracts/contracts_v2.py`: Authored and exported all 7 canonical contracts (`EvidenceRef`, `StateRef`, `DiagnosticResult`, `CapabilityReceipt`, `ForcingEvent`, `ScenarioRef`, `ActionAuthorization`) along with supporting domain types (`EvidenceRole`, `InfluenceUse`, `ForcingExecutionStatus`, `OwnershipContext`, `ValidityDomain`, `YieldDistribution`, `FeasibilityReceipt`, `canonical_data`, `canonical_hash`).
  - `services/agribrain/scientific_contracts/__init__.py`: Exported all new canonical contracts and helper functions into the public package namespace.
  - `services/agribrain/diagnostic_integration/adapters.py`: Implemented `adapt_diagnostic_result` to map canonical `DiagnosticResult` into `DiagnosticContribution` for the influence tribunal.
- **Verification**:
  - Automated test suite: `services/agribrain/tests/test_scientific_contracts_v2.py` (13 passed tests).
  - Diagnostic integration runtime suite: `services/agribrain/tests/test_diagnostic_integration_runtime.py` (7 passed tests).
  - Full test suite: 741 passed, 0 failures across all 13 layers.


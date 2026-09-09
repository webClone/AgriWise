# AgriBrain Capability-Gated Release Framework

## 1. Executive Summary & Governance Model
AgriBrain is a safety-critical agricultural intelligence platform controlling physical farm interventions, chemical applications, and irrigation equipment. In accordance with the system monograph, **release decisions must not be treated as an all-or-nothing binary flag**. Instead, capabilities are partitioned into 7 distinct operational levels, each guarded by strict, non-negotiable scientific, numerical, and architectural release gates.

Under no circumstances may an operational capability be enabled in production until all of its prerequisite gates are verified by automated integration test suites and certified by cryptographic qualification receipts.

---

## 2. Capability Release Gates Matrix

| Capability Level | Operational Scope | Mandatory Release Conditions | Blocking Work Packages |
| :--- | :--- | :--- | :--- |
| **G-1: Diagnostic Monitoring** | Read-only observation, visual maps, crop stress alerts, and farmer advice. | • State variables have consistent physical units ($\theta_v \in [0, 1]$).<br>• Observational missingness is preserved (no synthetic defaults).<br>• Explicit `StageReceipt` health reporting.<br>• Validated evidence lineage without double-counting. | **WP01, WP02, WP04, WP08, WP10** |
| **G-2: MESIA Research Collection** | Ingestion, storage, and feature extraction of opportunistic RF signals (CSI/GNSS). | • Immutable capture manifests binding data and metadata.<br>• Multi-tenant ownership isolation.<br>• Real radio acquisition timestamps (no `now()` substitution).<br>• Truth-class separation (`DERIVED_MODEL_INFERRED`). | **WP02, WP03, WP06** |
| **G-3: MESIA State Updates** | Ingesting MESIA observations into ASMAE's ensemble Kalman filter. | • Mathematical observation operator (no probability-as-moisture).<br>• Active observation dispatcher connected.<br>• Mapped directly to ASMAE canonical spatial lattice.<br>• Finite observability and unexpired calibration certificates. | **WP04, WP05, WP06, WP07** |
| **G-4: Exact Prescriptions** | Autonomous calculation of variable-rate fertilizer and irrigation volumes. | • Reachable promotion path (`DiagnosticPromotionService`).<br>• Minimum epistemic confidence gates enforced.<br>• L7 candidate scenarios directly evaluated by L8 policy.<br>• Binding `ActionAuthorization` receipts generated. | **WP01, WP02, WP08, WP09** |
| **G-5: Machine Execution** | Exporting ISOBUS/ISO-11783 XML task files or commanding connected field equipment. | • 4-way cryptographic binding of action authorization.<br>• Feasibility verified against equipment & weather constraints.<br>• Idempotent execution receipts with rollback safety.<br>• Universal API route authentication and authorization. | **WP09, WP10, WP11** |
| **G-6: World-Model Development** | Training learned neural transition models and counterfactual simulators. | • Bitemporally indexed historical worldline corpus.<br>• Separation of planned vs confirmed intervention events.<br>• Verified model/operator registry with rollback capabilities.<br>• Immutable forecast archive evaluating prospective skill. | **WP02, WP03, WP04, WP05, WP12** |
| **G-7: Omega Autonomous Discovery** | Active experiment proposal, surprise tracking, and hypothesis lifecycle courts. | • Complete canonical evidence graph.<br>• Measurement policy audit logging.<br>• Automated hypothesis lifecycle with falsification gates.<br>• Strict isolation of research proposals from operational authority. | **WP02, WP03, WP07, WP12** |

---

## 3. Detailed Capability Gates & Acceptance Verification

### Gate G-1: Diagnostic Monitoring
- **Objective**: Ensure farmer-facing visualizations and diagnostic alerts reflect true physical observations and uncertainty.
- **Verification Checklist**:
  - [ ] ASMAE root-zone moisture increment scales strictly with soil depth ($10\text{ mm} / 400\text{ mm} = 0.025$).
  - [ ] Layer 4 Nutrients sets `spectral_completeness = 0.0` when satellite imagery is cloudy, rather than defaulting to $0.5$ NDVI.
  - [ ] Layer 5 Bio Threat returns `LayerStatus.DEGRADED` whenever agronomical invariants are violated.
  - [ ] Layer 10 Water Surfaces caller signature matches `water.py` parameters; no surfaces fail silently.
  - [ ] Layer 9 conversational summaries explicitly state `UNRESOLVED` when competing hypotheses cannot be discriminated.
- **Enforcement Test**: `tests/release_gates/test_gate_g1_diagnostic_monitoring.py`.

### Gate G-2: MESIA Research Collection
- **Objective**: Ensure opportunistic RF data is captured cleanly without corrupting time, ownership, or truth semantics.
- **Verification Checklist**:
  - [ ] Wi-Fi CSI ingestion writes `.sigmf-data` and `.sigmf-meta` with identical base hashes in atomic operations.
  - [ ] Missing metadata causes capture quarantine; system never substitutes current UTC time.
  - [ ] Captures are strictly scoped under `/tenant_id/farm_id/plot_id/`; legacy unscoped lookups are removed.
  - [ ] Derived biological proposals are strictly tagged as `DERIVED_MODEL_INFERRED`.
- **Enforcement Test**: `services/agribrain/mesia/tests/test_gate_g2_research_collection.py`.

### Gate G-3: MESIA State Updates
- **Objective**: Prevent uncalibrated or dimensionally invalid RF data from entering ASMAE's Kalman state.
- **Verification Checklist**:
  - [ ] `measured_vwc = likelihood.likelihood_value` is permanently removed.
  - [ ] Innovations are calculated in observation space with matching physical units.
  - [ ] Observation proposals are routed to `ASMAEObservationDispatcher`; discarded `l0_rec, _` assignments are eliminated.
  - [ ] MESIA consumes ASMAE's canonical spatial lattice rather than manufacturing coordinate-based microzones.
  - [ ] Active state updates occur only when `is_observable == True` and calibration certificates are valid.
- **Enforcement Test**: `services/agribrain/mesia/tests/test_gate_g3_state_updates.py`.

### Gate G-4: Exact Prescriptions
- **Objective**: Ensure variable-rate application plans are authorized through a reachable, policy-governed promotion service.
- **Verification Checklist**:
  - [ ] `DiagnosticPromotionService` bridges the tribunal and action generation; manifest entries are non-empty for qualified diagnoses.
  - [ ] Diagnoses with confidence $< 0.75$ or identifiability $\ne \text{IDENTIFIED}$ are rejected from prescription promotion.
  - [ ] Pipeline sequence follows: Feasibility (L6) $\to$ Planning (L7) $\to$ Prescription (L8).
  - [ ] L8 evaluates L7 candidate scenarios directly; `Layer8Input.candidate_scenarios` is populated.
- **Enforcement Test**: `tests/release_gates/test_gate_g4_exact_prescriptions.py`.

### Gate G-5: Machine Execution
- **Objective**: Prevent unauthorized, unsafe, or non-idempotent machine execution commands.
- **Verification Checklist**:
  - [ ] Serializer verifies all 4 cryptographic hashes: belief, tribunal, manifest, and policy snapshot.
  - [ ] Actions violating L6 weather windows (e.g. spraying in $> 20\text{ km/h}$ wind) are rejected.
  - [ ] Universal route authentication dependency (`require_internal_service_request`) active on all API endpoints.
  - [ ] Replaying an execution instruction generates an idempotent `AlreadyExecutedReceipt`.
- **Enforcement Test**: `tests/release_gates/test_gate_g5_machine_execution.py`.

### Gate G-6: World-Model Development
- **Objective**: Guarantee that offline model learning trains on faithful, non-leaking historical windows.
- **Verification Checklist**:
  - [ ] Bitemporal extractor filters out any event committed after `as_of_knowledge_time`.
  - [ ] Forecast archive stores prospective predictions at issue time and evaluates them against future ground truth without rewriting history.
  - [ ] Planned interventions are separated from confirmed applications in worldline event storage.
- **Enforcement Test**: `tests/release_gates/test_gate_g6_world_model_readiness.py`.

### Gate G-7: Omega Autonomous Discovery
- **Objective**: Allow active hypothesis exploration while strictly containing machine authority.
- **Verification Checklist**:
  - [ ] Omega surprise calculations and experiment proposals operate in a sandboxed, read-only environment.
  - [ ] Proposals are classified as `AuthorityScope.RESEARCH_ONLY`.
  - [ ] Hardcoded `regulatory_safety_approved = True` is replaced with independent governance validation.
- **Enforcement Test**: `tests/release_gates/test_gate_g7_omega_isolation.py`.

---

## 4. Operational Sign-Off Protocol
To promote a capability level from `STAGING_SHADOW` to `PRODUCTION_ACTIVE`:
1. Execute the corresponding automated gate test suite with zero failures.
2. Generate an immutable `CapabilityPromotionReceipt` signed by the lead platform engineer and chief agronomist.
3. Commit the promotion receipt hash to the canonical worldline metadata repository.

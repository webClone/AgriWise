# AgriBrain Capability-Gated Release Framework

## 1. Executive Summary & Governance Model
AgriBrain is a safety-critical agricultural intelligence platform controlling physical farm interventions, chemical applications, and irrigation equipment. In accordance with the system monograph, **release decisions must not be treated as an all-or-nothing binary flag**. Instead, capabilities are partitioned into 7 distinct operational levels, each guarded by strict, non-negotiable scientific, numerical, and architectural release gates.

Under no circumstances may an operational capability be enabled in production until all of its prerequisite gates are verified by automated integration test suites and certified by cryptographic qualification receipts.

### 1.1 The 5-Tier Capability Status Taxonomy
To avoid premature completion claims, AgriBrain tracks every capability and work package through five rigorous developmental and operational qualification tiers:

1. **Tier 1: Implemented**  
   Data contracts, algorithms, state vector representations, and transformation pipelines exist in the codebase and pass static syntax/compilation checks.
2. **Tier 2: Wired**  
   Endpoints, orchestrator runner loops, inter-layer boundaries, and background job dispatchers actively pass typed parameters and invoke the implementation without deadlocks or early bypass.
3. **Tier 3: Enforced**  
   Active invariant assertions, fail-closed validation gates, identifiability filters, permission policies, and cryptographic receipts actively reject uncalibrated, ungrounded, or unsafe inputs.
4. **Tier 4: Verified**  
   Comprehensive automated regression suites, unit tests, and bitemporal replay tests validate numerical stability, mass balance, unit consistency, and idempotency with zero test failures.
5. **Tier 5: Operationally Qualified**  
   Multi-month empirical field trials with physical ground-truth calibration (in-situ TDR moisture probes, lysimeters, yield monitor weigh-wagons, pathology traps) and formal sign-off by the Chief Agronomist and Lead Platform Engineer.

### 1.2 Zero Mock & Zero Hardcoded Data Invariant
A foundational release condition across all seven capability levels is that **production execution paths must contain zero mock, dummy, synthetic, or hardcoded shortcuts**:
1. **Observational Missingness Preservation**: When telemetry, meteorological data, or spectral observations are absent or occluded by clouds, systems must preserve explicit missingness (`None`, `DATA_GAP`, `MISSING_TELEMETRY`), never substituting synthetic default values (e.g. dummy zero temperatures, neutral NDVI fills, or static crop stages).
2. **Deterministic Calibration & Replayability**: Any stochastic simulation or Monte Carlo projection must strictly require or default to deterministic RNG seeds (`np.random.default_rng(seed)`) bound to the execution hash, preventing non-reproducible run variations.
3. **Fail-Closed Gate Enforcement**: Where ground truth, physical models, or spatial overlaps cannot be verified, components must fail closed (e.g. `0.0` overlap, `LayerStatus.DEGRADED`, or quarantine) rather than defaulting to permissive `1.0` stub passes.
4. **Test & Simulation Quarantine**: Simulation drivers (MAVSDK/DJI drone simulators, synthetic visual basemap tiles, and offline fixtures) must remain strictly isolated behind explicit test-override environment variables (`ALLOW_SYNTHETIC_VISUAL_PREVIEW=true`, `ASMAE_TEST_OVERRIDE=true`), which default to `false` in production.

---

## 2. Capability Release Gates Matrix

| Capability Level | Operational Scope | Current Status | Mandatory Release Conditions | Blocking Work Packages |
| :--- | :--- | :---: | :--- | :--- |
| **G-1: Diagnostic Monitoring** | Read-only observation, visual maps, crop stress alerts, and farmer advice. | **Verified & Enforced** | • State variables have consistent physical units ($\theta_v \in [0, 1]$, PAW with root depth $Z_r$).<br>• Observational missingness is preserved (no synthetic defaults).<br>• Explicit `StageReceipt` health reporting in `RunArtifact`.<br>• Validated evidence lineage without double-counting. | **WP01, WP02, WP04, WP08, WP10** |
| **G-2: MESIA Research Collection** | Ingestion, storage, and feature extraction of opportunistic RF signals (CSI/GNSS). | **Wired & Enforced** | • Immutable capture manifests binding data and metadata.<br>• Multi-tenant ownership isolation.<br>• Real radio acquisition timestamps (no `now()` substitution).<br>• Truth-class separation (`DERIVED_MODEL_INFERRED`). | **WP02, WP03, WP06** |
| **G-3: MESIA State Updates** | Ingesting MESIA observations into ASMAE's ensemble Kalman filter. | **Implemented (Contained Shadow)** | • Mathematical observation operator (no probability-as-moisture).<br>• Active observation dispatcher connected with abstention persistence.<br>• Mapped directly to ASMAE canonical spatial lattice.<br>• Finite observability ($cond(F) < 10^6$) and unexpired calibration certificates.<br>*Gated in shadow mode pending empirical ground-truth sensor correlation.* | **WP04, WP05, WP06, WP07** |
| **G-4: Exact Prescriptions** | Autonomous calculation of variable-rate fertilizer and irrigation volumes. | **Enforced (Gated on Evidence)** | • Reachable promotion path (`DiagnosticPromotionService`) with 6-tier promotion hierarchy.<br>• Epistemic confidence gates ($\ge 0.75$) and identifiability gating (`IDENTIFIED` required; `PARTIALLY_IDENTIFIED` gated).<br>• L7 candidate scenarios directly evaluated by L8 policy via typed `InterventionScenarioCandidate`.<br>• Binding `ActionAuthorization` receipts generated.<br>*Field actuation blocked until G-5 qualification.* | **WP01, WP02, WP08, WP09** |
| **G-5: Machine Execution** | Exporting ISOBUS/ISO-11783 XML task files or commanding connected field equipment. | **Blocked** | • 4-way cryptographic binding of action authorization (belief, tribunal, manifest, policy).<br>• Feasibility verified against equipment & weather constraints.<br>• Idempotent execution receipts with rollback safety.<br>• Universal API route authentication and authorization (`require_internal_service_request`).<br>*Awaiting multi-season field safety qualification and equipment failsafe sign-off.* | **WP09, WP10, WP11** |
| **G-6: World-Model Development** | Training learned neural transition models and counterfactual simulators. | **Implemented (Historical Extractor & Contracts)** | • Bitemporally indexed historical worldline corpus with non-leaking window extraction.<br>• Separation of planned vs confirmed intervention events.<br>• Verified model/operator registry with rollback capabilities.<br>• Immutable forecast archive evaluating prospective skill.<br>*Transition model training active in research environment.* | **WP02, WP03, WP04, WP05, WP12** |
| **G-7: Omega Autonomous Discovery** | Active experiment proposal, surprise tracking, and hypothesis lifecycle courts. | **Implemented (Read-Only Scaffolding)** | • Complete canonical evidence graph.<br>• Measurement policy audit logging.<br>• Automated hypothesis lifecycle with falsification gates.<br>• Strict isolation of research proposals from operational authority (`RESEARCH_ONLY`).<br>*Autonomous intervention authority strictly blocked.* | **WP02, WP03, WP07, WP12** |

---

## 3. Detailed Capability Gates & Acceptance Verification

### Gate G-1: Diagnostic Monitoring
* **Current Status**: **Verified & Enforced (Tier 4)**
* **Operational Qualification**: *Requires multi-season field scouting correlation to reach Tier 5.*
* **Objective**: Ensure farmer-facing visualizations and diagnostic alerts reflect true physical observations and uncertainty.
* **Verification Checklist**:
  - [x] ASMAE root-zone moisture increment scales strictly with soil depth ($10\text{ mm} / 400\text{ mm} = 0.025$).
  - [x] Layer 4 Nutrients sets `spectral_completeness = 0.0` when satellite imagery is cloudy, rather than defaulting to $0.5$ NDVI.
  - [x] Layer 5 Bio Threat returns `LayerStatus.DEGRADED` whenever agronomical invariants are violated.
  - [x] Layer 10 Water Surfaces caller signature matches `water.py` parameters; no surfaces fail silently.
  - [x] Layer 9 conversational summaries explicitly state `UNRESOLVED` when competing hypotheses cannot be discriminated.
* **Enforcement Test**: `tests/release_gates/test_gate_g1_diagnostic_monitoring.py`.

### Gate G-2: MESIA Research Collection
* **Current Status**: **Wired & Enforced (Tier 3)**
* **Operational Qualification**: *Requires deployed radio testbed multi-tenant data logging.*
* **Objective**: Ensure opportunistic RF data is captured cleanly without corrupting time, ownership, or truth semantics.
* **Verification Checklist**:
  - [x] Wi-Fi CSI ingestion writes `.sigmf-data` and `.sigmf-meta` with identical base hashes in atomic operations.
  - [x] Missing metadata causes capture quarantine; system never substitutes current UTC time.
  - [x] Captures are strictly scoped under `/tenant_id/farm_id/plot_id/`; legacy unscoped lookups are removed.
  - [x] Derived biological proposals are strictly tagged as `DERIVED_MODEL_INFERRED`.
* **Enforcement Test**: `services/agribrain/mesia/tests/test_gate_g2_research_collection.py`.

### Gate G-3: MESIA State Updates
* **Current Status**: **Implemented (Contained Shadow - Tier 1/2)**
* **Operational Qualification**: *Gated in permanent shadow mode. Requires 90-day TDR probe correlation ($\text{RMSE} \le 0.04$) before state authority.*
* **Objective**: Prevent uncalibrated or dimensionally invalid RF data from entering ASMAE's Kalman state.
* **Verification Checklist**:
  - [x] `measured_vwc = likelihood.likelihood_value` is permanently removed.
  - [x] Innovations are calculated in observation space with matching physical units.
  - [x] Observation proposals are routed to `ASMAEObservationDispatcher`; discarded `l0_rec, _` assignments are eliminated.
  - [x] MESIA consumes ASMAE's canonical spatial lattice rather than manufacturing coordinate-based microzones.
  - [ ] Active state updates into production Kalman filter remain disabled until field sensor calibration certificates pass.
* **Enforcement Test**: `services/agribrain/mesia/tests/test_gate_g3_state_updates.py`.

### Gate G-4: Exact Prescriptions
* **Current Status**: **Enforced (Gated on Evidence - Tier 3)**
* **Operational Qualification**: *Calculated prescriptions gated by identifiability and confidence; variable-rate equipment actuation blocked.*
* **Objective**: Ensure variable-rate application plans are authorized through a reachable, policy-governed promotion service.
* **Verification Checklist**:
  - [x] `DiagnosticPromotionService` bridges the tribunal and action generation; manifest entries are non-empty for qualified diagnoses.
  - [x] Diagnoses with confidence $< 0.75$ or identifiability $\ne \text{IDENTIFIED}$ are rejected from prescription promotion (partial identifiability requires explicit override flag).
  - [x] Pipeline sequence follows: Feasibility (L6) $\to$ Planning (L7) $\to$ Prescription (L8).
  - [x] L8 evaluates L7 candidate scenarios directly; `Layer8Input.candidate_scenarios` is populated with `InterventionScenarioCandidate`.
* **Enforcement Test**: `tests/release_gates/test_gate_g4_exact_prescriptions.py`.

### Gate G-5: Machine Execution
* **Current Status**: **Blocked (Tier 0 for Physical Machinery)**
* **Operational Qualification**: *Requires physical implement safety interlock, operator emergency e-stop, and agronomist sign-off.*
* **Objective**: Prevent unauthorized, unsafe, or non-idempotent machine execution commands.
* **Verification Checklist**:
  - [x] Serializer verifies all 4 cryptographic hashes: belief, tribunal, manifest, and policy snapshot.
  - [x] Actions violating L6 weather windows (e.g. spraying in $> 20\text{ km/h}$ wind) are rejected.
  - [x] Universal route authentication dependency (`require_internal_service_request`) active on all API endpoints.
  - [ ] Machine execution task generation remains blocked pending hardware qualification.
* **Enforcement Test**: `tests/release_gates/test_gate_g5_machine_execution.py`.

### Gate G-6: World-Model Development
* **Current Status**: **Implemented (Historical Extractor & Contracts - Tier 1)**
* **Operational Qualification**: *Requires multi-season historical dataset curation and prospective skill evaluation.*
* **Objective**: Guarantee that offline model learning trains on faithful, non-leaking historical windows.
* **Verification Checklist**:
  - [x] Bitemporal extractor filters out any event committed after `as_of_knowledge_time`.
  - [x] Forecast archive stores prospective predictions at issue time and evaluates them against future ground truth without rewriting history.
  - [x] Planned interventions are separated from confirmed applications in worldline event storage.
* **Enforcement Test**: `tests/release_gates/test_gate_g6_world_model_readiness.py`.

### Gate G-7: Omega Autonomous Discovery
* **Current Status**: **Implemented (Read-Only Scaffolding - Tier 1)**
* **Operational Qualification**: *Isolated in research sandbox; zero physical intervention authority.*
* **Objective**: Allow active hypothesis exploration while strictly containing machine authority.
* **Verification Checklist**:
  - [x] Omega surprise calculations and experiment proposals operate in a sandboxed, read-only environment.
  - [x] Proposals are classified as `AuthorityScope.RESEARCH_ONLY`.
  - [x] Hardcoded `regulatory_safety_approved = True` is replaced with independent governance validation.
* **Enforcement Test**: `tests/release_gates/test_gate_g7_omega_isolation.py`.

---

## 4. Operational Sign-Off Protocol
To promote a capability level from `STAGING_SHADOW` to `PRODUCTION_ACTIVE`:
1. Execute the corresponding automated gate test suite with zero failures.
2. Generate an immutable `CapabilityPromotionReceipt` signed by the lead platform engineer and chief agronomist.
3. Commit the promotion receipt hash to the canonical worldline metadata repository.

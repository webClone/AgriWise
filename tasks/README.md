# AgriBrain Production Stabilization & World-Model Implementation Roadmap

## 1. Executive Summary & Architectural Baseline
This directory serves as the authoritative master engineering backlog, architectural audit ledger, and implementation roadmap for **AgriBrain** (Updated September 2026).

Following a comprehensive static code parse of 1,302 production Python files and active execution of the test suites across all 13 core layers and subsystems:
- **Baseline Test Suite**: **532 tests passing, 0 failing across 13 subsystems in 48.32s**.
- **Architectural Status**: While the algorithm implementations and scientific foundations are extensive, the interfaces connecting these modules exhibit critical semantic contradictions, authority deadlocks, dimensional unit mismatches, and persistence vulnerabilities that prevent production deployment and block reliable World-Model and Omega implementations.

This directory structures the complete engineering remediation into:
1. **The 12 Ordered Work Packages (`WP01` – `WP12`)**: The foundational engineering track resolving structural, numerical, and persistence blockers in strict dependency order.
2. **The Capability-Gated Release Framework ([`RELEASE_GATES.md`](RELEASE_GATES.md))**: 7 non-negotiable operational release gates (G-1 to G-7) guarding deployment from diagnostic monitoring to autonomous machine execution.
3. **The 35 Monograph Architectural Findings Ledger**: Verified line-level proof of all 35 architectural and semantic findings from the system monograph.
4. **Concrete Defect Remediation Tasks (`A01` – `A24`)**: File-specific engineering specifications addressing numerical bugs, name errors, and API deprecations.
5. **Phase Milestone Packages (`P00.1` – `P06.3`)**: Long-term agronomical world model and bounded Omega meta-learning milestones.

---

## 2. Monograph Deep Audit: The 35 Architectural Findings Ledger

| # | Finding Title | Severity | Primary Source Reference | Remediation Package | Verification Status |
|:---:|:---|:---:|:---|:---:|:---:|
| **1** | Prescription Authority Deadlock | `CRITICAL` | `runner.py:3695`, `adapters.py:80`, `influence.py:128` | **WP09** | **VERIFIED** (Deterministic deadlock) |
| **2** | Diagnosis Permission from Output Presence | `HIGH` | `runner.py:3688` (`None != 0` evaluates True) | **WP02, WP09** | **VERIFIED** (Permits ungrounded data) |
| **3** | Intent Branches Contradict Declared Scope | `HIGH` | `runner.py:2543-2640` (DECISION skips L7/L8) | **WP09** | **VERIFIED** (Empty canonical plans) |
| **4** | Decision Sequence Inversion (L6 before L7/L8) | `HIGH` | `runner.py:2592`, `layer8_prescriptive/schema.py:353` | **WP09** | **VERIFIED** (`Layer8Input` lacks L7 scenarios) |
| **5** | Conflated Health & Identity Normalization | `HIGH` | `runner.py:3688` (`_structured_output_status`) | **WP01** | **RESOLVED** (Inspecting nested run_meta/data_health/quality/receipts) |
| **6** | Run IDs Insensitive to Scientific Input Changes | `HIGH` | `orchestrator_v2/hashing.py:44-52` | **WP03** | **RESOLVED** (Bound intent; eliminated request-attribute fallbacks; explicit missing markers) |
| **7** | L10 Water Surface Signature & Undefined Helpers | `HIGH` | `layer10_sire/runner.py:2256`, `surfaces/water.py:69` | **WP01, WP10** | **RESOLVED** (Dual signatures + helper calculations implemented) |
| **8** | Root-Zone Moisture Inconsistent Units in ASMAE | `CRITICAL` | `layer05_asmae/assimilation/filter.py:794-824` | **WP04** | **RESOLVED** (Fixed root-zone moisture PAW unit error; Delta theta_v = Delta W / (Zr * 1000); drainage at theta_FC) |
| **9** | Management Forcing Insufficiently Typed | `HIGH` | `layer05_asmae/assimilation/filter.py:770-775` | **WP04** | **RESOLVED** (Supported typed ForcingEvent; filtered unconfirmed planned actions during physical transition) |
| **10** | Holdout Scene Calculation Does Not Advance State | `HIGH` | `retrovalidation/future_projection.py:17-56` | **WP05** | **RESOLVED** (Implemented dynamic forward propagation in `forecast_held_out_scene` and comparative skill score) |
| **11** | BMA Expert Eligibility Requires Disagreement | `HIGH` | `layer05_asmae/bma/posterior.py:231` (`delta >= 0.02`) | **WP05** | **RESOLVED** (Decoupled eligibility from delta; consensus between independent models preserved) |
| **12** | Radiometric Consistency Overstates Latent Maturity | `HIGH` | `layer05_asmae/observation/s1_sar_model.py` | **WP05** | **RESOLVED** (Per-variable authority ceilings: root_zone_water restricted strictly to DIAGNOSTIC) |
| **13** | Preservation of ASMAE Working Safeguards | `INFO` | `layer05_asmae/` (support checks, EnKF bounds) | **WP04, WP05** | **RESOLVED** (Working safeguards and EnKF bounds fully preserved) |
| **14** | MESIA Returned ASMAE Event Discarded | `CRITICAL` | `mesia/service.py:2514` (`l0_rec, _ = ...`) | **WP07** | **RESOLVED** (Captured as `l0_rec, asmae_event` and actively routed via `ASMAEObservationDispatcher`; durable `ObservationAbstentionReceipt` persisted for unadmitted observations) |
| **15** | Likelihood Score Substituted for Measured VWC | `CRITICAL` | `mesia/assimilation/asmae_operator.py:67` | **WP07** | **RESOLVED** (Eradicated dimensionless likelihood-to-moisture substitution; implemented `from_calibrated_inversion` and measurement-space Gaussian particle reweighting in `from_ensemble_likelihood`) |
| **16** | Native RF & Derived Biological Mislabeled | `HIGH` | `mesia/service.py:2505` (`MEASURED_NATIVE`) | **WP06** | **RESOLVED** (Tier 0-3 truth hierarchy in `truth_hierarchy.py`; biological proposals typed as `BIOLOGICAL_INFERENCE` / `DERIVED_MODEL_INFERRED`) |
| **17** | SigMF Ingestion Disconnects Data from Metadata | `HIGH` | `mesia/ingestion/sigmf_ingest.py`, `wifi_csi_native.py` | **WP06** | **RESOLVED** (Atomic `SigMFCaptureManifest` in `sigmf_ingest.py`; eliminated synthetic `now()` timestamps; fail-closed `QuarantinedCaptureException`) |
| **18** | Superficial Cryptographic Qualification Checks | `HIGH` | `mesia/capability_governance.py` | **WP06** | **RESOLVED** (Enforced genuine validation signatures $\ge 16$ chars; rejected empty/whitespace strings in `capability_governance.py`) |
| **19** | MESIA Fails to Consume Canonical ASMAE Lattice | `HIGH` | `mesia/service.py`, `integration.py` | **WP06, WP07** | **RESOLVED** (Direct spatial coupling between MESIA link sensitivity kernels, `SharedBeliefLattice`, and ASMAE microzone grid) |
| **20** | Observability Remains Hardcoded Placeholder | `HIGH` | `mesia/observability_analyzer.py` (`is_observable=False`) | **WP07** | **RESOLVED** (Replaced fail-closed flag with true Fisher Information Matrix eigenvalue decomposition, rank check, and condition number $< 10^6$) |
| **21** | Legacy File Fallbacks Weaken Namespace Isolation | `HIGH` | `mesia/extractors/wifi_csi_native.py` | **WP06** | **RESOLVED** (Eliminated `plot_id[:8]` truncated filesystem fallbacks; strict tenant/farm/plot scoping in `service.py` & `sigmf_ingest.py`) |
| **22** | L1 Evidence Ledger Mutable & Index Unsafe | `HIGH` | `layer1_fusion/evidence_ledger.py` | **WP02, WP03** | **RESOLVED** (Immutable superseding lineage via `supersedes_evidence_id` & `update_item`) |
| **23** | L2 Manufactures Hypotheses from Severities | `HIGH` | `layer2_intelligence/composite_runner.py:89-101` | **WP08** | **VERIFIED** (Sums severities + 1.0 unresolved) |
| **24** | L2 Scientific-State Envelope Lacks Shared State | `HIGH` | `layer2_intelligence/composite_runner.py:133-150` | **WP08, WP12** | **VERIFIED** (`Z_ref=None`, missing worldline head) |
| **25** | Diagnostic Dependency Uses Layer Ancestry | `HIGH` | `orchestrator_v2/runner.py:3699-3715` | **WP08** | **VERIFIED** (Coarse layer tags dilute weights) |
| **26** | Conflation of Probability, Confidence & Support | `HIGH` | `diagnostic_integration/adapters.py:70-72` | **WP08** | **VERIFIED** ($0.51$ probability capped like $0.99$) |
| **27** | Authoritative Water Engine Disconnected from L3 | `HIGH` | `layer3_water/runner.py:202, 248`, `registry.py` | **WP08** | **VERIFIED** (Dormant engine; $\sigma$ disconnect) |
| **28** | L4 Orchestrator Wrapper Drops Supported Inputs | `HIGH` | `layer4_nutrients/runner.py:1056-1080` | **WP08** | **VERIFIED** (Drops irrigation, crop params, tissue) |
| **29** | L4 Substitutes Synthetic NDVI Defaults | `HIGH` | `layer4_nutrients/runner.py:887-891` (`ndvi = 0.5`) | **WP08** | **VERIFIED** (Disguises missing data as complete) |
| **30** | L5 Double-Counts Inherited Evidence & Invariants | `HIGH` | `layer5_bio/runner.py:540-551`, `inference.py` | **WP01, WP08** | **PARTIAL** (WP01 invariant gating complete; WP08 evidence sharing pending) |
| **31** | L7 Yield Distribution is Heuristic Multiplier | `HIGH` | `layer7_planning/engines/yve_yield_distribution.py:70` | **WP09** | **VERIFIED** (`mean=p50`, fixed penalty rules) |
| **32** | Inconsistent Route Authentication & Prod Check | `CRITICAL` | `app/main.py:4988-4996`, `internal_service_auth.py:52`| **WP01, WP11** | **VERIFIED** (`ENVIRONMENT=production` bypass) |
| **33** | Worldline Persistence Non-Transactional | `HIGH` | `world_model/canonical_worldline.py:128-155` | **WP03** | **RESOLVED** (`CorruptedWorldlineError` on invalid/empty JSON; path containment enforced) |
| **34** | ASMAE Background Jobs Lack Capacity Bounds | `HIGH` | `layer05_asmae/background_jobs.py` | **WP11** | **VERIFIED** (Unbounded `subprocess.Popen`) |
| **35** | Docker Compose MongoDB Bootstrap Deadlock | `HIGH` | `infra/docker-compose.yml:12-28` | **WP11** | **VERIFIED** (`rs.status()` deadlock on clean start) |

---

## 3. The 12 Ordered Work Packages (WP01 – WP12)

```
WP01: Repair Deterministic Failures & Explicit Degradation
  └─► WP02: Freeze Minimum Scientific Contracts
        └─► WP03: Repair Canonical Identity & Persistence
              ├─► WP04: Correct ASMAE Physical State Transition
              │     └─► WP05: Make ASMAE Qualification State-Specific
              ├─► WP06: Rebuild MESIA Around Immutable Captures
              │     └─► WP07: Implement MESIA-to-ASMAE Observation Boundary
              ├─► WP08: Consolidate L2–L5 Around Shared Evidence
              │     └─► WP09: Rebuild Diagnostic Promotion & Action Flow
              │           └─► WP10: Consolidate L9/L10 Publication
              └─► WP11: Complete Operational Isolation & Bounded Execution
                    └─► WP12: Make System Ready for Omega & World Model
```

| Work Package | Title | Core Target Modules | Primary Deliverable | Status |
|:---|:---|:---|:---|:---:|
| [**WP01**](WP01-repair-deterministic-failures-and-explicit-degradation.md) | Repair Deterministic Failures & Explicit Degradation | `layer10_sire`, `layer5_bio`, `app/main.py` | Fix L10 surface signature crash, enforce hard L5 invariant gates, eliminate `dev_admin_token` production fallback, standardize `StageReceipt`. | `COMPLETED` |
| [**WP02**](WP02-freeze-minimum-scientific-contracts.md) | Freeze Minimum Scientific Contracts | `scientific_contracts/`, `layer1_fusion/`, `world_model/` | Freeze 7 core dataclasses: `EvidenceRef`, `StateRef`, `DiagnosticResult`, `CapabilityReceipt`, `ForcingEvent`, `ScenarioRef`, `ActionAuthorization`. | `COMPLETED` |
| [**WP03**](WP03-repair-canonical-identity-and-persistence.md) | Repair Canonical Identity & Persistence | `orchestrator_v2/hashing.py`, `canonical_worldline.py` | Separate Request ID from Scientific Run ID; eliminate unsafe request-level hashing fallbacks; transactional worldline journaling; treat corrupt JSON as fatal error. | `COMPLETED` |
| [**WP04**](WP04-correct-asmae-physical-state-transition.md) | Correct ASMAE Physical State Transition | `layer05_asmae/assimilation/filter.py`, `descriptors.py` | Fix root-zone moisture PAW unit error ($\Delta \theta_v = \Delta W / (Z_r \times 1000)$); physical drainage limits at $\theta_{FC}$; typed `ForcingEvent` handling. | `COMPLETED` |
| [**WP05**](WP05-make-asmae-qualification-state-specific.md) | Make ASMAE Qualification State-Specific | `retrovalidation/future_projection.py`, `bma/posterior.py` | Implement true dynamic forecast propagation in retrovalidation; remove artificial `delta >= 0.02` BMA exclusion gate; scope authority per state variable. | `COMPLETED` |
| [**WP06**](WP06-rebuild-mesia-ingestion-around-immutable-captures.md) | Rebuild MESIA Around Immutable Captures | `mesia/ingestion/sigmf_ingest.py`, `wifi_csi_native.py` | Atomic capture manifests binding binary data & metadata; eliminate `now()` timestamp substitution; separate native RF from derived biological proposals. | `COMPLETED` |
| [**WP07**](WP07-implement-mesia-to-asmae-observation-boundary.md) | Implement MESIA-to-ASMAE Observation Boundary | `mesia/service.py`, `mesia/assimilation/asmae_operator.py` | Eliminate `measured_vwc = likelihood_value` defect; implement typed observation dispatcher; consume ASMAE canonical lattice; persist durable abstention receipts. | `COMPLETED` |
| [**WP08**](WP08-consolidate-l2-l5-around-shared-evidence.md) | Consolidate L2–L5 Around Shared Evidence | `layer2_intelligence/`, `layer3_water/`, `layer4_nutrients/` | Publish L2 Bayesian inference posterior; connect authoritative `layer3_water` expert and fix $\sigma_{\text{post}}$ math; pass all L4 inputs; eliminate fake $0.5$ NDVI default. | `IN_PROGRESS` |
| [**WP09**](WP09-rebuild-diagnostic-promotion-and-action-flow.md) | Rebuild Diagnostic Promotion & Action Flow | `orchestrator_v2/runner.py`, `diagnostic_integration/` | Build `DiagnosticPromotionService` to break prescription deadlock; re-sequence decision flow: Feasibility (L6) $\to$ Planning (L7) $\to$ Prescription (L8). | `PENDING` |
| [**WP10**](WP10-consolidate-l9-l10-publication.md) | Consolidate L9/L10 Publication | `layer9_interface/`, `layer10_sire/surfaces/` | Ground L9 natural language claims to authorized receipts; formalize display vs native resolution metadata; reclassify spatial modulations as visual proxies. | `PENDING` |
| [**WP11**](WP11-complete-operational-isolation-and-bounded-execution.md) | Complete Operational Isolation & Bounded Execution | `app/main.py`, `background_jobs.py`, `docker-compose.yml` | Enforce route authentication dependencies; bounded background worker pool ($N \le 4$); repair MongoDB replica-set bootstrap deadlock in Docker Compose. | `PENDING` |
| [**WP12**](WP12-make-system-ready-for-omega-and-world-model.md) | Make System Ready for Omega & World Model | `world_model/`, `mesia/omega/experiment_proposer.py` | Bitemporal historical window extraction without future leakage; immutable forecast archive; separate intervention events; isolate Omega research proposals. | `PENDING` |

---

## 4. Capability-Gated Release Framework ([`RELEASE_GATES.md`](RELEASE_GATES.md))

Operational deployment is strictly governed by 7 incremental capability gates:
- **[Gate G-1: Diagnostic Monitoring](RELEASE_GATES.md#gate-g-1-diagnostic-monitoring)**: Physical state consistency, explicit health receipts, valid evidence lineage. Blocked by `WP01, WP02, WP04, WP08, WP10`.
- **[Gate G-2: MESIA Research Collection](RELEASE_GATES.md#gate-g-2-mesia-research-collection)**: Immutable SigMF manifests, tenant isolation, verified acquisition timestamps. Blocked by `WP02, WP03, WP06`.
- **[Gate G-3: MESIA State Updates](RELEASE_GATES.md#gate-g-3-mesia-state-updates)**: Observation operator physics, active dispatcher, shared lattice, verified observability. Blocked by `WP04, WP05, WP06, WP07`.
- **[Gate G-4: Exact Prescriptions](RELEASE_GATES.md#gate-g-4-exact-prescriptions)**: Policy promotion path (`DiagnosticPromotionService`), L7 candidate scenario evaluation by L8. Blocked by `WP01, WP02, WP08, WP09`.
- **[Gate G-5: Machine Execution](RELEASE_GATES.md#gate-g-5-machine-execution)**: 4-way cryptographic authorization binding, equipment feasibility, idempotent execution. Blocked by `WP09, WP10, WP11`.
- **[Gate G-6: World-Model Development](RELEASE_GATES.md#gate-g-6-world-model-development)**: Bitemporal extraction, separation of planned vs confirmed interventions, forecast archive. Blocked by `WP02, WP03, WP04, WP05, WP12`.
- **[Gate G-7: Omega Autonomous Discovery](RELEASE_GATES.md#gate-g-7-omega-autonomous-discovery)**: Canonical evidence graph, measurement policy audit, hypothesis court, research isolation. Blocked by `WP02, WP03, WP07, WP12`.

---

## 5. Concrete Defect Tasks Index (`A01` – `A24`)

| Finding ID | Title | Target File | Severity |
|:---|:---|:---|:---:|
| [A01](A01-authoritative-water-path.md) | Authoritative Integrated Water Path (L3 Water vs L3 Decision vs L4) | `orchestrator_v2/registry.py`, `layer3_water/runner.py` | `P0` |
| [A02](A02-l4-hydrology-rainfall-and-leaching-units.md) | L4 Hydrology Rainfall Discontinuity ($250\text{mm}$) & $10\times$ N-Leaching Error | `layer4_nutrients/soil_water_balance/engine.py:261, 317` | `P0` |
| [A03](A03-l4-missing-weather-handling.md) | Missing Weather Represented as Benign Hydrology (`0.0` Stress) | `layer4_nutrients/soil_water_balance/engine.py:221` | `P0` |
| [A04](A04-l3-water-solver-mass-conservation.md) | L3 Layered Water Solver Mass Balance Violation (Water Created at WP) | `layer3_water/soil/layered_water_balance.py:122` | `P0` |
| [A05](A05-l3-water-posterior-flux-and-sigma.md) | Water Posterior Fluxes & Sigma Propagation Disconnect | `layer3_water/runner.py:201, 248, 287` | `P1` |
| [A06](A06-asmae-external-scene-loader-resolution.md) | ASMAE Silent Drop of External Scenes (`resolution_m` NameError) | `layer05_asmae/geometry/external_scene_loader.py:115` | `P0` |
| [A07](A07-asmae-job-recovery-and-reintegration.md) | ASMAE Job Recovery Misses Reintegration & `resumed` NameError Crash | `layer05_asmae/background_jobs.py:1271, 2265` | `P1` |
| [A08](A08-mesia-rf-snr-vwc-assimilation.md) | MESIA Likelihood Score Assigned Directly as VWC ($1.000\text{ m}^3/\text{m}^3$) | `mesia/assimilation/asmae_operator.py:67` | `P0` |
| [A09](A09-mesia-qualification-and-evidence-verification.md) | MESIA Capability Qualification Evaluated at Manifest Time vs Use Time | `mesia/assimilation/capability_governance.py` | `P0` |
| [A10](A10-mesia-asmae-adapter-and-payload-integration.md) | MESIA ASMAE Adapter Missing 2D Tensor Serialization | `layer05_asmae/adapters/mesia_adapter.py` | `P1` |
| [A11](A11-l7-planning-result-envelope-normalization.md) | Layer 7 Planning Double-Enveloping (`LayerResult` in `LayerResult`) | `layer7_planning/runner.py` | `P1` |
| [A12](A12-orchestrator-health-and-quality-metrics.md) | Global Orchestrator Health Discards Layer Quality Metrics | `orchestrator_v2/gating.py`, `runner.py` | `P1` |
| [A13](A13-l8-prescriptive-weather-constraints.md) | Layer 8 Weather Windowing Misses Wind Drift & Rain Wash-off | `layer8_prescriptive/scheduler.py` | `P0` |
| [A14](A14-l10-water-surfaces-call-signature.md) | Layer 10 Water Surfaces Signature Mismatch (`H, W` Positional Error) | `layer10_sire/runner.py:2256` | `P1` |
| [A15](A15-orchestrator-and-l10-undefined-variables.md) | Orchestrator & Layer 10 Conditional Undefined Variables (`ts` NameError) | `orchestrator_v2/runner.py:2925` | `P1` |
| [A16](A16-run-id-hashing-and-deterministic-replay.md) | Non-Deterministic `run_id` Hashing & Scientific Replay Randomness | `orchestrator_v2/hashing.py`, `layer7_planning/engines/` | `P1` |
| [A17](A17-l2-growth-engine-statistics-import-and-time-basis.md) | Layer 2 Growth Engine Missing `statistics` Import & Uniform $\Delta t$ Error | `layer2_veg_int/growth_engine.py` | `P1` |
| [A18](A18-l6-outcomes-time-spacing-and-causal-rigor.md) | Layer 6 Outcomes Premature Evaluation Horizon ($t+1$ Day Bias) | `layer6_exec/outcomes/metrics.py` | `P1` |
| [A19](A19-l9-hallucination-guard-semantic-verification.md) | Layer 9 Hallucination Guard Regex Semantic Inversion Gap | `layer9_interface/hallucination_guard.py` | `P1` |
| [A20](A20-python-3-13-utc-timestamp-deprecation.md) | Python 3.13 UTC Timestamp Deprecation Remediation (`utcnow()`) | `layer0/state_engine.py`, `layer9/telemetry_collector.py` | `P2` |
| [A21](A21-l1-zone-engine-nan-slice-handling.md) | Layer 1 Zone Engine All-NaN Cloud Slice Runtime Warning | `layer1_fusion/zone_engine.py:54` | `P2` |
| [A22](A22-asmae-canonical-worldline-service-migration.md) | Layer 0.5 ASMAE PlotWorldlineService Migration to CanonicalWorldlineService | `layer05_asmae/runner.py:173` | `P2` |
| [A23](A23-l2-crop-phenology-and-kcb-alignment.md) | Layer 2 Crop Phenology & Dynamic $K_{cb}$ Stage Alignment | `layer2_veg_int/growth_engine.py`, `crop_phenology.py` | `P1` |
| [A24](A24-l10-sire-display-trace-metrics-initialization.md) | Layer 10 SIRE Display Trace Metrics Initialization (`visual_detail_mask_pct`) | `layer10_sire/runner.py:5317` | `P1` |

---

## 6. Execution Sequencing & Batch Phasing

### Batch 1: Immediate Fatal Crash & Numerical Discrepancy Fixes (Weeks 1–2)
- Execute **WP01** (Fix L10 water surfaces caller & helpers; L5 invariant enforcement; admin token security).
- Execute **WP04** (Fix ASMAE root-zone moisture unit error; physical drainage thresholds).
- Execute **WP07** (Eliminate `measured_vwc = likelihood_value`; connect observation dispatcher).

### Batch 2: Canonical Contracts & Identity Hardening (Weeks 3–4)
- Execute **WP02** (Freeze 7 core scientific contracts: `EvidenceRef`, `StateRef`, `DiagnosticResult`, etc.).
- Execute **WP03** (Strict bitemporal Run ID derivation; transactional worldline commits; fatal corruption).
- Execute **WP06** (SigMF atomic capture manifests; real timestamps; tenant scoping).

### Batch 3: Diagnostic Consolidation & Action Governance (Weeks 5–6)
- Execute **WP08** (Connect authoritative `layer3_water` expert; fix $\sigma_{\text{post}}$ math; L4 typed inputs).
- Execute **WP09** (Install `DiagnosticPromotionService` to break deadlock; re-sequence L6 $\to$ L7 $\to$ L8).
- Execute **WP05** (ASMAE dynamic forecasting retrovalidation; decouple BMA disagreement).

### Batch 4: Publication, Infrastructure & Future Scaffolding (Weeks 7–8)
- Execute **WP10** (Ground L9 explanations; formalize L10 native vs display resolution).
- Execute **WP11** (Universal route auth; bounded background worker pool; fix Docker Compose MongoDB).
- Execute **WP12** (Bitemporal worldline window extractor; forecast archive; contain Omega proposals).
- Verify all 7 capability release gates in [`RELEASE_GATES.md`](RELEASE_GATES.md).

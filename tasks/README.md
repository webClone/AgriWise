# AgriBrain Stabilization & Agronomical World Model Implementation Roadmap

## 1. Overview
This directory serves as the unified engineering backlog, architectural specification index, and implementation tracker for the **AgriBrain Production Stabilization and World-Model Implementation Plan** (Updated September 2026).

It integrates:
1. **Defect Remediation Tasks (`A01` – `A24`):** Concrete, line-level code fixes addressing verified defects, numerical discontinuities, swallowed exceptions, unit discrepancies, and forward deprecations identified during the full Layer 0 through Layer 10 + MESIA architectural audit.
2. **Phase Milestone Packages (`P00.1` – `P06.3`):** Architectural, governance, mathematical, and machine-learning milestones required to transition AgriBrain from a stabilized deterministic system to a fully calibrated agronomical world model with bounded Omega meta-learning.

---

## 2. Seven-Phase Master Roadmap

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 0: Define the Supported System (P00.1, P00.2)                             │
│   Execution profiles, single state ownership, frozen golden evidence baselines   │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────────────────┐
│ PHASE 1: Repair Runtime & Status Contracts (P01.1 - P01.4)                      │
│   Envelope normalization [A11], Global quality [A12], Scene drop [A06],          │
│   SIRE crashes [A14, A15, A24], ASMAE recovery [A07], Replay [A16], Py3.13 [A20]│
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────────────────┐
│ PHASE 2: Make Physical & Temporal State Coherent (P02.1 - P02.5)                │
│   L4 Hydrology [A02, A03], L3 Water Conservation [A04, A05], Authoritative Path  │
│   [A01], Growth/Outcome Time Basis [A17, A18], Phenology & Crops [A23, P02.5]   │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────────────────┐
│ PHASE 3: Complete MESIA as a Scientific Observation Lane (P03.1 - P03.4)         │
│   Observation model [A08], Cryptographic qualification [A09], Adapter [A10],     │
│   Permanent shadow-mode trial [P03.4]                                            │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────────────────┐
│ PHASE 4: Prescriptions & Explanations Consume Single Truth (P04.1 - P04.3)      │
│   Prescriptive weather constraints [A13], Grounded explanations [A19],           │
│   Operational stress & concurrency hardening [P04.3]                             │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │  === [ CURRENT-AGRIBRAIN RELEASE GATE ] ===
┌──────────────────────────────▼───────────────────────────────────────────────────┐
│ PHASE 5: Introduce Omega Under Controlled Authority (P05.1 - P05.3)              │
│   Read-only surprise & proposals [P05.1], Offline evaluation & registry [P05.2], │
│   Tiered promotion & instant rollback [P05.3]                                    │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────────────────┐
│ PHASE 6: Complete the Agronomical World Model (P06.1 - P06.3)                    │
│   Formal state/action/disturbance spaces [P06.1], Calibrated multi-step rollouts │
│   [P06.2], Structural causal models & counterfactual policy optimization [P06.3] │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Work Package Index & Status Dashboard

### Phase 0: Define the Supported System
| Work Package | Title | Target Subsystems | Status |
|:---|:---|:---|:---:|
| [P00.1](P00.1-execution-and-ownership-contract.md) | Publish Execution Profiles & State Ownership Contract | `orchestrator_v2/schema.py`, `scientific_contracts/authority.py` | `[ ] Ready` |
| [P00.2](P00.2-freeze-reviewable-baseline.md) | Freeze 7 Reviewable Golden Evidence Baselines & Budgets | `golden/bundles/`, `data/` | `[ ] Ready` |

### Phase 1: Repair Runtime and Status Contracts
| Work Package | Title | Linked Audit Findings | Target Files | Status |
|:---|:---|:---:|:---|:---:|
| [P01.1](P01.1-normalize-layer-returns-and-health.md) | Normalize Layer Returns & Requested-Profile Health | [A11](A11-l7-planning-result-envelope-normalization.md), [A12](A12-orchestrator-health-and-quality-metrics.md) | `orchestrator_v2/runner.py`, `gating.py`, `layer7_planning/runner.py` | `[ ] Ready` |
| [P01.2](P01.2-repair-asmae-scene-and-sire-failures.md) | Repair ASMAE Scene Admission & Publication Failures | [A06](A06-asmae-external-scene-loader-resolution.md), [A14](A14-l10-water-surfaces-call-signature.md), [A15](A15-orchestrator-and-l10-undefined-variables.md), [A24](A24-l10-sire-display-trace-metrics-initialization.md) | `external_scene_loader.py`, `layer10_sire/runner.py`, `surfaces/water.py` | `[ ] Ready` |
| [P01.3](P01.3-make-asmae-job-recovery-resilient.md) | Make ASMAE Background Job Recovery Resilient | [A07](A07-asmae-job-recovery-and-reintegration.md), [A22](A22-asmae-canonical-worldline-service-migration.md) | `layer05_asmae/background_jobs.py`, `layer05_asmae/runner.py` | `[ ] Ready` |
| [P01.4](P01.4-establish-deterministic-replay-identity.md) | Establish Deterministic Scientific Replay Identity | [A16](A16-run-id-hashing-and-deterministic-replay.md) | `orchestrator_v2/hashing.py`, `layer7_planning/engines/ccr_resilience.py` | `[ ] Ready` |

### Phase 2: Make Physical and Temporal State Coherent
| Work Package | Title | Linked Audit Findings | Target Files | Status |
|:---|:---|:---:|:---|:---:|
| [P02.1](P02.1-repair-l4-hydrology-and-leaching.md) | Repair Active Layer 4 Hydrology & Leaching Units | [A02](A02-l4-hydrology-rainfall-and-leaching-units.md), [A03](A03-l4-missing-weather-handling.md) | `layer4_nutrients/soil_water_balance/engine.py`, `runner.py` | `[ ] Ready` |
| [P02.2](P02.2-repair-l3-water-solver-and-uncertainty.md) | Repair Layer 3 Water Solver & Uncertainty Sigma | [A04](A04-l3-water-solver-mass-conservation.md), [A05](A05-l3-water-posterior-flux-and-sigma.md) | `layer3_water/soil/layered_water_balance.py`, `layer3_water/runner.py` | `[ ] Ready` |
| [P02.3](P02.3-install-single-authoritative-water-owner.md) | Install Single Authoritative Water State Owner | [A01](A01-authoritative-water-path.md) | `orchestrator_v2/registry.py`, `layer4_nutrients/runner.py` | `[ ] Ready` |
| [P02.4](P02.4-correct-vegetation-and-outcome-temporality.md) | Correct Vegetation & Outcome Temporal Semantics | [A17](A17-l2-growth-engine-statistics-import-and-time-basis.md), [A18](A18-l6-outcomes-time-spacing-and-causal-rigor.md), [A23](A23-l2-crop-phenology-and-kcb-alignment.md) | `layer2_veg_int/growth_engine.py`, `layer6_exec/outcomes/metrics.py` | `[ ] Ready` |
| [P02.5](P02.5-qualify-remaining-agronomical-outputs.md) | Qualify Remaining Agronomical Crop Domains & Bounds | [A23](A23-l2-crop-phenology-and-kcb-alignment.md) | `scientific_contracts/crop_governance.py`, `layer6_yield/` | `[ ] Ready` |

### Phase 3: Complete MESIA as a Scientific Observation Lane
| Work Package | Title | Linked Audit Findings | Target Files | Status |
|:---|:---|:---:|:---|:---:|
| [P03.1](P03.1-specify-native-rf-measurements-and-models.md) | Specify Native RF Measurements & Observation Models | [A08](A08-mesia-rf-snr-vwc-assimilation.md) | `mesia/behaviour/likelihood_engine.py`, `asmae_operator.py` | `[ ] Ready` |
| [P03.2](P03.2-enforce-cryptographic-qualification-at-use-time.md) | Enforce Cryptographic Qualification at Use-Time | [A09](A09-mesia-qualification-and-evidence-verification.md) | `mesia/assimilation/capability_governance.py`, `integration.py` | `[ ] Ready` |
| [P03.3](P03.3-connect-complete-asmae-numerical-tensors.md) | Connect Complete ASMAE Ingestion & Numerical Tensors | [A10](A10-mesia-asmae-adapter-and-payload-integration.md) | `layer05_asmae/adapters/mesia_adapter.py`, `runner.py` | `[ ] Ready` |
| [P03.4](P03.4-mesia-shadow-operation-before-authority.md) | MESIA Shadow Operation Before State Authority | Constitutional Safety Gate | `mesia/analytics/shadow_evaluation.py` | `[ ] Ready` |

### Phase 4: Prescriptions & Explanations Consume Single Truth
| Work Package | Title | Linked Audit Findings | Target Files | Status |
|:---|:---|:---:|:---|:---:|
| [P04.1](P04.1-enforce-per-action-weather-constraints.md) | Enforce Per-Action Weather Constraints & Eligibility | [A13](A13-l8-prescriptive-weather-constraints.md) | `layer8_prescriptive/scheduler.py` | `[ ] Ready` |
| [P04.2](P04.2-ground-scientific-explanations-structurally.md) | Ground Scientific Explanations Structurally | [A19](A19-l9-hallucination-guard-semantic-verification.md) | `layer9_interface/hallucination_guard.py` | `[ ] Ready` |
| [P04.3](P04.3-demonstrate-operational-readiness.md) | Demonstrate Operational Readiness Under Production Stress | Release Gate | `tests/load/`, `layer10_sire/` | `[ ] Ready` |

---

### Phase 5: Introduce Omega Under Controlled Authority
| Work Package | Title | Prerequisites | Target Subsystems | Status |
|:---|:---|:---|:---|:---:|
| [P05.1](P05.1-omega-readonly-surprise-and-experiment-proposals.md) | Read-Only Predictive Surprise & Experiment Proposals | P01.4, P02.1–P02.3, P04.1 | `world_model/forecast_archive.py`, `omega/` | `[ ] Ready` |
| [P05.2](P05.2-omega-offline-evaluation-and-model-registry.md) | Offline Evaluation, Data Anti-Leakage & Model Registry | P05.1 | `model_registry/`, `omega/evaluation/` | `[ ] Ready` |
| [P05.3](P05.3-omega-bounded-promotion-and-rollback.md) | Bounded Canary Promotion & Instant Rollback ($<100\text{ms}$) | P05.2 | `orchestrator_v2/watchdogs/model_drift.py` | `[ ] Ready` |

---

### Phase 6: Complete the Agronomical World Model
| Work Package | Title | Prerequisites | Target Subsystems | Status |
|:---|:---|:---|:---|:---:|
| [P06.1](P06.1-world-model-state-observation-action-contracts.md) | State, Observation, Action & Disturbance Contracts | Phase 2, Phase 4 | `world_model/contracts/` | `[ ] Ready` |
| [P06.2](P06.2-world-model-calibrated-forecasts-evaluation.md) | Calibrated Multi-Step Forward Forecasting (CRPS $\ge 85\%$) | P06.1, P05.2 | `world_model/dynamics/rollout.py` | `[ ] Ready` |
| [P06.3](P06.3-world-model-causal-intervention-modeling.md) | Causal Counterfactuals & SCM Policy Optimization | P06.2, P02.4 | `world_model/causal/scm.py`, `layer8_prescriptive/` | `[ ] Ready` |

---

## 4. Complete Inventory of Line-Level Remediation Tasks (A01 – A24)

| Finding ID | Title | Primary Target File | Severity |
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

## 5. Architectural Baseline: Current Verified Test Suite Status

Following the deep layer-by-layer audit and test relocation across all 13 subsystems, the active AgriBrain test baseline is:

| Subsystem / Layer | Dedicated Test Package | Tests | Status | Key Focus Area |
|---|---|:---:|:---:|---|
| **Layer 0** | `layer0/tests/` | 42 | **PASS** | Microclimate boundary forcing, Open-Meteo, psychrometric calculations. |
| **Layer 0.5** | `layer05_asmae/tests/` | 134 | **PASS** | ASMAE multimodal belief lattice, worldline history, raster fusion. |
| **Layer 1** | `layer1_fusion/tests/` | 40 | **PASS** | Multi-sensor spatial alignment, FieldCube, zone clustering. |
| **Layer 2** | `layer2_veg_int/tests/` | 15 | **PASS** | Crop canopy biophysics, vegetation indices, phenological curves. |
| **Layer 3** | `layer3_water/tests/` | 74 | **PASS** | FAO-56 dual $K_c$, multi-layer soil hydrology, probe assimilation. |
| **Layer 4** | `layer4_nutrients/tests/`| 19 | **PASS** | Soil chemistry, NPK budgeting, nutrient deficiency diagnostics. |
| **Layer 5** | `layer5_bio/tests/` | 12 | **PASS** | Phytopathology, fungal spores, pest risk modeling. |
| **Layer 6** | `layer6_yield/tests/` | 33 | **PASS** | Yield forecasting, stress degree-days, Monte Carlo economic bounds. |
| **Layer 7** | `layer7_risk/tests/` | 22 | **PASS** | Climatic risk resilience, sirocco heatwaves, seasonal scenario planning. |
| **Layer 8** | `layer8_prescriptive/tests/`| 13 | **PASS** | Variable-rate prescriptions, ActionCards, safety gate windowing. |
| **Layer 9** | `layer9_interface/tests/`| 9 | **PASS** | Cognitive advisory dialogues, telemetry, hallucination verification. |
| **Layer 10** | `layer10_sire/tests/` | 17 | **PASS** | SIRE 17-engine spatial renderer, One-Meter Policy, surface packs. |
| **MESIA** | `mesia/tests/` | 101 | **PASS** | RF opportunistic sensing, CA-CFAR detection, ISO GUM metrology. |
| **Total** | **All 13 Subsystems** | **532** | **100% PASS** | **Complete Full-Stack Verification (0 failures in 48.32s)** |

---

## 6. Recommended Immediate Execution Order (Batch 1 & Batch 2)

### Batch 1: Fatal Runtime NameErrors, Signature Mismatches & Critical Math
1. **[A06](A06-asmae-external-scene-loader-resolution.md), [A14](A14-l10-water-surfaces-call-signature.md), [A15](A15-orchestrator-and-l10-undefined-variables.md), [A24](A24-l10-sire-display-trace-metrics-initialization.md) (`P01.2`):**
   - Fix fatal calling signature in `generate_water_surfaces`.
   - Fix `resolution_m` in external scene loader.
   - Fix `one_meter_visual_coverage_pct` and `ts` NameErrors in SIRE and Orchestrator.
2. **[A02](A02-l4-hydrology-rainfall-and-leaching-units.md) & [A03](A03-l4-missing-weather-handling.md) (`P02.1`):**
   - Fix $250\text{mm}$ rainfall cliff.
   - Fix $10\times$ leaching unit dimensional error.
   - Fix missing weather treated as benign $0.0$ stress.
3. **[A04](A04-l3-water-solver-mass-conservation.md) & [A05](A05-l3-water-posterior-flux-and-sigma.md) (`P02.2`):**
   - Eliminate spontaneous water creation at wilting point.
   - Harmonize mass balance ledger equation.
   - Correctly propagate posterior uncertainty sigma.
4. **[A07](A07-asmae-job-recovery-and-reintegration.md) (`P01.3`):**
   - Fix `resumed` NameError in job recovery.
   - Recover `COMPLETED_REINTEGRATION_PENDING` state.
5. **[A17](A17-l2-growth-engine-statistics-import-and-time-basis.md) (`P02.4`):**
   - Add missing `statistics` import in Layer 2 growth engine.
6. **[A20](A20-python-3-13-utc-timestamp-deprecation.md):**
   - Replace deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)`.

### Batch 2: Architectural Pipeline Harmonization
1. **[P00.1](P00.1-execution-and-ownership-contract.md) & [P00.2](P00.2-freeze-reviewable-baseline.md):**
   - Enforce execution profiles and state ownership matrix.
   - Freeze 7 reviewable golden evidence baselines.
2. **[A01](A01-authoritative-water-path.md) (`P02.3`):**
   - Connect Layer 3 Water as the sole authoritative hydrology provider for Layer 4 Nutrients.
3. **[A11](A11-l7-planning-result-envelope-normalization.md) & [A12](A12-orchestrator-health-and-quality-metrics.md) (`P01.1`):**
   - Flatten Layer 7 double envelope.
   - Expose composite pipeline quality index.
4. **[A08](A08-mesia-rf-snr-vwc-assimilation.md), [A09](A09-mesia-qualification-and-evidence-verification.md), [A10](A10-mesia-asmae-adapter-and-payload-integration.md) (`P03.1`–`P03.3`):**
   - Formalize RF observation forward operator.
   - Enforce use-time cryptographic qualification.
5. **[A13](A13-l8-prescriptive-weather-constraints.md) & [A19](A19-l9-hallucination-guard-semantic-verification.md) (`P04.1`, `P04.2`):**
   - Enforce wind drift and rain wash-off constraints on prescriptions.
   - Upgrade hallucination guard to propositional semantic verification.

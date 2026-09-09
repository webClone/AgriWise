# AgriBrain Stabilization & Agronomical World Model Implementation Roadmap

## 1. Overview
This directory serves as the unified engineering backlog and implementation tracker for the **AgriBrain Production Stabilization and World-Model Implementation Plan** (8 September 2026).

It integrates:
1. **Defect Remediation Tasks (`A01` – `A19`):** Concrete, line-level code fixes addressing every issue verified in the production-code audit.
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
│   SIRE crashes [A14, A15], ASMAE recovery [A07], Deterministic replay [A16]      │
└──────────────────────────────┬───────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────────────────┐
│ PHASE 2: Make Physical & Temporal State Coherent (P02.1 - P02.5)                │
│   L4 Hydrology [A02, A03], L3 Water Conservation [A04, A05], Authoritative Path  │
│   [A01], Growth/Outcome Time Basis [A17, A18], Crop Domain Qualification [P02.5] │
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
| Work Package | Title | Target Files | Status |
|:---|:---|:---|:---:|
| [P00.1](P00.1-execution-and-ownership-contract.md) | Publish Execution Profiles & State Ownership Contract | `orchestrator_v2/schema.py`, `scientific_contracts/authority.py` | `[ ] Ready` |
| [P00.2](P00.2-freeze-reviewable-baseline.md) | Freeze 7 Reviewable Golden Evidence Baselines & Budgets | `golden/bundles/`, `data/` | `[ ] Ready` |

### Phase 1: Repair Runtime and Status Contracts
| Work Package | Title | Linked Audit Findings | Target Files | Status |
|:---|:---|:---:|:---|:---:|
| **P01.1** | Normalize Layer Returns & Requested-Profile Health | [A11](A11-l7-planning-result-envelope-normalization.md), [A12](A12-orchestrator-health-and-quality-metrics.md) | `orchestrator_v2/runner.py`, `gating.py`, `layer7_planning/runner.py` | `[ ] Ready` |
| **P01.2** | Repair ASMAE Scene Admission & Publication Failures | [A06](A06-asmae-external-scene-loader-resolution.md), [A14](A14-l10-water-surfaces-call-signature.md), [A15](A15-orchestrator-and-l10-undefined-variables.md) | `external_scene_loader.py`, `layer10_sire/runner.py`, `surfaces/water.py` | `[ ] Ready` |
| **P01.3** | Make ASMAE Background Job Recovery Resilient | [A07](A07-asmae-job-recovery-and-reintegration.md) | `layer05_asmae/background_jobs.py` | `[ ] Ready` |
| **P01.4** | Establish Deterministic Scientific Replay Identity | [A16](A16-run-id-hashing-and-deterministic-replay.md) | `orchestrator_v2/hashing.py`, `layer7_planning/engines/ccr_resilience.py` | `[ ] Ready` |

### Phase 2: Make Physical and Temporal State Coherent
| Work Package | Title | Linked Audit Findings | Target Files | Status |
|:---|:---|:---:|:---|:---:|
| **P02.1** | Repair Active Layer 4 Hydrology & Leaching Units | [A02](A02-l4-hydrology-rainfall-and-leaching-units.md), [A03](A03-l4-missing-weather-handling.md) | `layer4_nutrients/soil_water_balance/engine.py`, `runner.py` | `[ ] Ready` |
| **P02.2** | Repair Layer 3 Water Solver & Uncertainty Sigma | [A04](A04-l3-water-solver-mass-conservation.md), [A05](A05-l3-water-posterior-flux-and-sigma.md) | `layer3_water/soil/layered_water_balance.py`, `layer3_water/runner.py` | `[ ] Ready` |
| **P02.3** | Install Single Authoritative Water State Owner | [A01](A01-authoritative-water-path.md) | `orchestrator_v2/registry.py`, `layer4_nutrients/runner.py` | `[ ] Ready` |
| **P02.4** | Correct Vegetation & Outcome Temporal Semantics | [A17](A17-l2-growth-engine-statistics-import-and-time-basis.md), [A18](A18-l6-outcomes-time-spacing-and-causal-rigor.md) | `layer2_veg_int/growth_engine.py`, `layer6_exec/outcomes/metrics.py` | `[ ] Ready` |
| **P02.5** | [Qualify Remaining Agronomical Crop Domains & Bounds](P02.5-qualify-remaining-agronomical-outputs.md) | General Agronomy | `scientific_contracts/crop_governance.py`, `layer6_yield/` | `[ ] Ready` |

### Phase 3: Complete MESIA as a Scientific Observation Lane
| Work Package | Title | Linked Audit Findings | Target Files | Status |
|:---|:---|:---:|:---|:---:|
| **P03.1** | Specify Native RF Measurements & Observation Models | [A08](A08-mesia-rf-snr-vwc-assimilation.md) | `mesia/behaviour/likelihood_engine.py`, `asmae_operator.py` | `[ ] Ready` |
| **P03.2** | Enforce Cryptographic Qualification at Use-Time | [A09](A09-mesia-qualification-and-evidence-verification.md) | `mesia/assimilation/capability_governance.py`, `integration.py` | `[ ] Ready` |
| **P03.3** | Connect Complete ASMAE Ingestion & Numerical Tensors | [A10](A10-mesia-asmae-adapter-and-payload-integration.md) | `layer05_asmae/adapters/mesia_adapter.py`, `runner.py` | `[ ] Ready` |
| **P03.4** | [MESIA Shadow Operation Before State Authority](P03.4-mesia-shadow-operation-before-authority.md) | Safety Gate | `mesia/analytics/shadow_evaluation.py` | `[ ] Ready` |

### Phase 4: Prescriptions & Explanations Consume Single Truth
| Work Package | Title | Linked Audit Findings | Target Files | Status |
|:---|:---|:---:|:---|:---:|
| **P04.1** | Enforce Per-Action Weather Constraints & Eligibility | [A13](A13-l8-prescriptive-weather-constraints.md) | `layer8_prescriptive/scheduler.py` | `[ ] Ready` |
| **P04.2** | Ground Scientific Explanations Structurally | [A19](A19-l9-hallucination-guard-semantic-verification.md) | `layer9_interface/hallucination_guard.py` | `[ ] Ready` |
| **P04.3** | [Demonstrate Operational Readiness Under Production Stress](P04.3-demonstrate-operational-readiness.md) | Release Gate | `tests/load/`, `layer10_sire/` | `[ ] Ready` |

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

## 4. First Immediate Implementation Batch (Batch 1)

When coding execution is approved, work should proceed strictly in this order:
1. **[P00.1](P00.1-execution-and-ownership-contract.md) & [P00.2](P00.2-freeze-reviewable-baseline.md):** Define execution profiles, state ownership, and freeze evidence baselines.
2. **[A02](A02-l4-hydrology-rainfall-and-leaching-units.md) & [A03](A03-l4-missing-weather-handling.md) (`P02.1`):** Fix active L4 hydrology rainfall cliff, $10\times$ leaching unit error, and missing weather benign defaults.
3. **[A06](A06-asmae-external-scene-loader-resolution.md), [A14](A14-l10-water-surfaces-call-signature.md), [A15](A15-orchestrator-and-l10-undefined-variables.md) (`P01.2`):** Fix fatal NameErrors and argument signature mismatches in ASMAE and SIRE.
4. **[A07](A07-asmae-job-recovery-and-reintegration.md) (`P01.3`):** Fix ASMAE recovery NameError and include `COMPLETED_REINTEGRATION_PENDING`.
5. **[A11](A11-l7-planning-result-envelope-normalization.md) & [A12](A12-orchestrator-health-and-quality-metrics.md) (`P01.1`):** Remove L7 double-envelope and integrate `quality_metrics` into global orchestrator health.
6. **[A17](A17-l2-growth-engine-statistics-import-and-time-basis.md) (`P02.4`):** Fix missing `statistics` import in Layer 2 growth engine.

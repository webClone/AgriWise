# AgriBrain Detailed Implementation Plan (52 Packages across 17 Execution Stages)

**Plan Revision**: 7 October 2026 (Revision 2 - Fully Reconciled)  
**Status**: Reviewed Execution Roadmap  
**Historical Production Baseline**: Main at `26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`  
**Draft PR #1 Reference**: `bcb9eda6b8ef1aa6425f5828669f753a191227bc` (Draft, unmerged)  
**Target Specification**: French Master Monograph R3 (30 September 2026), 153 requirements  
**Sequencing Authority**: [AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md](AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md)  
**Authority Map**: [README.md](README.md)

---

## 1. Executive Framework & Engineering Operating Model

This blueprint translates the 52 repair and extension packages into a rigorous, stage-by-stage engineering plan. It incorporates all corrections specified in the review: portable relative links, capability-specific invariants, clean acceptance criteria, and exact lane contracts.

### 1.1 The Two-Tier Delivery Model: Early Slices vs. Full Acceptance

Six packages feature early-slice boundaries to unblock cold startup and local verification before full persistence or distributed integration completes:

| Package | Early Slice Scope (Immediate Startup / Boundary) | Full Package Completion Stage & Prerequisites |
|---|---|---|
| **F37** | Correct GaussianMixture import and establish supported startup | Full package Stage 0; namespace/identity migration must also pass |
| **F35** | Isolate missing optional driver import; make driver availability explicit | Durable job lifecycle after F09; full reliability Stage 11 |
| **F38** | Fix local undefined names using real input/context; reject fabricated namespace | F01/F02/F09/F31/F37; full integration Stage 10 |
| **F39** | Reproduce and remove nonce lost updates at the actual admission boundary | F01/F09; full shared replay and telemetry persistence Stage 03 |
| **F40** | Resolve annotation names needed by actual schema/introspection consumers | F37/F38; complete runtime/manifest verification Stage 10 |
| **F32** | Dashboard errors return unavailable, preserving legitimate account zeros | Full records/calendar/scoped integration after F09 at Stage 10 |

### 1.2 Lane-Based Concurrency & Evidence Contracts

Engineering work proceeds across six architectural tracks:
- **Evidence Lane (F01, F02, F38)**: Enforces finite numeric validation, zero preservation, and observation vs availability cutoffs.
- **Trajectory Lane (F03–F11, F39)**: Enforces physical mass conservation, strictly increasing soil depth increments, and atomic multi-worker replay protection.
- **Execution Lane (F15–F20, F34)**: Enforces autonomous watchdog execution, non-bypassable quota checks, immutable hard caps, and exposure verification separation.
- **Learning Lane (F21–F29, F36)**: Enforces immutable dataset manifests, valid forecast scores (never RMSE 0 on missing medians), and honest model backends.
- **Application Lane (F30–F34, F35, F37, F40)**: Enforces Next.js/TypeScript clean builds, 503 unavailable on database failure, and runtime type introspection.
- **Target Capability Lane (T01–T12)**: Enforces coupled trajectories, longitudinal learning, multimodal foundation representations, hybrid world models, and Omega investigation loops.

### 1.3 Scientific Scope & Target Package Expansions (T01–T12)

In accordance with Monograph R3 (Volumes XI–XVII), target packages are decomposed into distinct engineering infrastructure and empirical validation milestones:
- **T01/T02**: Versioned state transitions and longitudinal learning contracts before tensor projection; explicit support masks and physical memory.
- **T03**: Foundation model baselines, modality adapters, masked representation training, and rich-to-sparse distillation.
- **T04/T05**: Mechanistic conserved transitions paired with bounded residual rollouts; multi-horizon evaluation and shared outcome distributions for farm economics.
- **T06/T12**: Native complex CSI/RF metrology archives, geometric lattice calibration, and independent agronomic validation in reference field plots.
- **T07 (Omega)**: Complete scientific investigation loop covering competing explanations, Bayesian laboratory, causal discovery vs. identification, symbolic equation holdouts, value of information, discriminating experiments, falsification, and replication.

---

## 2. Stage-by-Stage Implementation Blueprint (Stages 00 to 16)

### Stage 00: F37 (24–48 hours)

**Stage Focus**: Execution of 1 package(s): F37.  
**Engineering Estimate**: 24 to 48 hours.  

#### [F37] Repair optional imports and establish one Python package identity

- **Priority**: `P1` | **Estimate**: `24-48 hours` | **Dependencies**: `none` | **Lane**: `Application Lane`
- **R3 Requirements**: `AB-ARC-004, AB-ARC-008, AB-DAT-002`
- **Target Production Files**:
  - [`services/agribrain/layer1_fusion/segmentation.py`](../services/agribrain/layer1_fusion/segmentation.py)
  - [`services/agribrain/layer1_fusion/engine.py`](../services/agribrain/layer1_fusion/engine.py)
  - [`services/agribrain/drone_control/dispatcher.py`](../services/agribrain/drone_control/dispatcher.py)
  - [`services/agribrain/drone_mission/__init__.py`](../services/agribrain/drone_mission/__init__.py)
  - [`services/agribrain/layer0/perception/drone_rgb/structural.py`](../services/agribrain/layer0/perception/drone_rgb/structural.py)
  - [`services/agribrain/app/main.py`](../services/agribrain/app/main.py)

**Architectural Problem & Defect Basis**:
GaussianMixture is imported from sklearn.cluster and the module fails to load. The missing drone mock driver is confirmed, but adding a production mock is not the only remedy. Both alleged package cycles cold-import successfully under the configured path. Mixing qualified and bare drone_mission imports creates different MissionType class objects. The active L1 engine uses zone_engine, so the broken segmentation import is not proof that all L1 fails.

**Step-by-Step Implementation Instructions**:
1. Import GaussianMixture from sklearn.mixture and identify actual consumers of the legacy segmentation module.
2. Isolate optional drivers and model backends behind explicit capability loading, retaining simulation as a qualified mode.
3. Select one installed package namespace and migrate entrypoints/imports coherently instead of mechanically prefixing every import.
4. Verify service, worker, CLI and public module startup in fresh processes with declared dependency extras.

**Domain Invariants & Edge Case Handling**:
- Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Cold imports work for each supported entrypoint without incidental prior imports.
- Qualified and internal callers share enum/dataclass identities.
- An unavailable optional backend disables its capability without breaking unrelated science.
- The two successfully loaded cycles are not treated as demonstrated circular-import failures.

**Verification & Recovery Strategy**:
- **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.
- **Recovery**: Safe UI fallback: return explicit UNAVAILABLE status to users rather than synthetic mocks or empty collections during service degradation.

---

### Stage 01: F01 + F02 (48–80 hours)

**Stage Focus**: Execution of 2 package(s): F01, F02.  
**Engineering Estimate**: 48 to 80 hours.  

#### [F01] Qualify provenance and numeric evidence at every admission boundary

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `none` | **Lane**: `Evidence Lane`
- **R3 Requirements**: `AB-DAT-005, AB-DAT-006, AB-ARC-005, AB-ARC-006`
- **Target Production Files**:
  - [`services/agribrain/layer0/observation_packet.py`](../services/agribrain/layer0/observation_packet.py)
  - [`services/agribrain/layer0/wrappers.py`](../services/agribrain/layer0/wrappers.py)
  - [`services/agribrain/scientific_contracts/observation.py`](../services/agribrain/scientific_contracts/observation.py)
  - [`services/agribrain/layer3_water/assimilation/water_state_assimilator.py`](../services/agribrain/layer3_water/assimilation/water_state_assimilator.py)

**Architectural Problem & Defect Basis**:
Main admits infinite soil values and reports assimilation. A fresh probe moved every layer from 0.20 to 0.4499. PR #1 adds finite numeric checks and fail-closed provenance, but is unmerged.

**Step-by-Step Implementation Instructions**:
1. Review PR #1 against source consumers and preserve its corrected zero and missingness semantics.
2. Make accepted/rejected components explicit before authority or solver selection.
3. Carry source roles through all typed and dictionary adapters without allowing caller promotion.
4. Apply the same qualification to weather, RF, crop observations and training admission, with migration of ambiguous legacy records.

**Domain Invariants & Edge Case Handling**:
- Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- NaN, infinity, booleans and malformed numeric values cannot alter state or training weight.
- Legitimate zero survives serialization and round trips.
- Authority and accepted counts follow actual admitted components.

**Verification & Recovery Strategy**:
- **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

#### [F02] Enforce observation time and availability at issuance

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01` | **Lane**: `Evidence Lane`
- **R3 Requirements**: `AB-DAT-004, AB-DAT-014, AB-ML-008`
- **Target Production Files**:
  - [`services/agribrain/layer05_asmae/resilient_posterior.py`](../services/agribrain/layer05_asmae/resilient_posterior.py)
  - [`services/agribrain/layer0/temporal_evidence.py`](../services/agribrain/layer0/temporal_evidence.py)
  - [`services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)

**Architectural Problem & Defect Basis**:
PR #1 repairs explicit prospective initialization, including nested future soil records. That does not establish availability filtering throughout retrospective reconstruction, Worldline extraction and downstream adapters.

**Step-by-Step Implementation Instructions**:
1. Retain the PR explicit-cutoff fix and require both observation and availability provenance for prospective measurements.
2. Define typed timing for measurements, priors, forecasts and management scenarios.
3. Propagate the decision cutoff through each layer and reject records with unresolved eligibility.
4. Record every excluded revision and force historical replays to use the archived knowledge view.

**Domain Invariants & Edge Case Handling**:
- Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Late-arriving measurements and revised weather are excluded from earlier issuance.
- Earlier-issued future forecasts remain eligible as scenarios.
- Replay identifies exactly which input versions were available.

**Verification & Recovery Strategy**:
- **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

### Stage 02: F03 + F04 (36–60 hours)

**Stage Focus**: Execution of 2 package(s): F03, F04.  
**Engineering Estimate**: 36 to 60 hours.  

#### [F03] Publish the fluxes actually integrated and separate analysis increments

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01` | **Lane**: `Trajectory Lane`
- **R3 Requirements**: `AB-AGR-004, AB-AGR-005, AB-AGR-008`
- **Target Production Files**:
  - [`services/agribrain/layer3_water/runner.py`](../services/agribrain/layer3_water/runner.py)
  - [`services/agribrain/layer3_water/soil/layered_water_balance.py`](../services/agribrain/layer3_water/soil/layered_water_balance.py)
  - [`services/agribrain/layer3_water/contracts/water_state.py`](../services/agribrain/layer3_water/contracts/water_state.py)

**Architectural Problem & Defect Basis**:
Fresh pipeline probe: propagated transpiration demand 1.32 mm, published posterior-based transpiration 8.52 mm, reported mass error 0.0. The posterior also gains water from assimilation, without a separately published storage increment.

**Step-by-Step Implementation Instructions**:
1. Return a transition receipt containing bounded actual evaporation, transpiration, drainage, infiltration and initial/final storage.
2. Publish that receipt as realized interval flux and expose posterior demand as a separate next-interval diagnostic.
3. Return an analysis receipt with storage increment, covariance change and bound corrections.
4. Calculate closure from the serialized state and receipt rather than an internal pre-rounding ledger.

**Domain Invariants & Edge Case Handling**:
- Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Integrated and published realized fluxes agree.
- Physical closure includes bounded extraction and quantization, while analysis increments are explicit.
- Assimilation cannot retroactively rewrite the water used in the preceding interval.

**Verification & Recovery Strategy**:
- **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

#### [F04] Validate soil geometry and hydraulic parameter vectors

- **Priority**: `P0` | **Estimate**: `12-20 hours` | **Dependencies**: `F01` | **Lane**: `Trajectory Lane`
- **R3 Requirements**: `AB-AGR-003, AB-DAT-007`
- **Target Production Files**:
  - [`services/agribrain/layer3_water/contracts/state_factory.py`](../services/agribrain/layer3_water/contracts/state_factory.py)
  - [`services/agribrain/layer3_water/soil/layered_water_balance.py`](../services/agribrain/layer3_water/soil/layered_water_balance.py)

**Architectural Problem & Defect Basis**:
The production factory accepts nonmonotonic depths [30,10] and negative conductivity [-1,-1]. These can create negative layer thickness, storage or drainage inputs even though retention ordering passes.

**Step-by-Step Implementation Instructions**:
1. Require a nonempty strictly increasing finite positive depth vector.
2. Validate the length and physical domain of every retention, conductivity and van Genuchten vector.
3. Reject degenerate saturation/residual intervals and inconsistent units before computing suction.
4. Document parameter provenance and distinguish measured values from texture priors.

**Domain Invariants & Edge Case Handling**:
- Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Nonmonotonic, repeated, zero or nonfinite depths are rejected.
- Negative conductivity and invalid n or alpha cannot enter the solver.
- Valid heterogeneous profiles retain their parameters and storage.

**Verification & Recovery Strategy**:
- **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

### Stage 03: F06 + F07 + F08 + F09 + F39 (148–252 hours)

**Stage Focus**: Execution of 5 package(s): F06, F07, F08, F09, F39.  
**Engineering Estimate**: 148 to 252 hours.  

#### [F06] Stop substituting another date at the weather endpoint

- **Priority**: `P0` | **Estimate**: `12-20 hours` | **Dependencies**: `F02` | **Lane**: `Trajectory Lane`
- **R3 Requirements**: `AB-DAT-004, AB-DAT-005, AB-AGR-007, AB-AGR-013`
- **Target Production Files**:
  - [`services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)

**Architectural Problem & Defect Basis**:
When the target date has no weather, rec = next(iter(weather_daily.values())) supplies an arbitrary record. A Jan 2 request with only Jan 3 rain returned a Jan 2 state using 12 mm of Jan 3 rainfall.

**Step-by-Step Implementation Instructions**:
1. Remove arbitrary-record selection at the endpoint.
2. Resolve forcing by exact interval and declared timezone.
3. Route missing target forcing through an explicit prior or missing-data result with uncertainty and source role.
4. Apply the same policy to intermediate gaps and keep zero rainfall distinct from unobserved rainfall.

**Domain Invariants & Edge Case Handling**:
- Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- No future record supplies a historical daily forcing.
- Missing rainfall is visible and cannot become observed zero.
- Daily and sparse executions use identical qualified interval inputs.

**Verification & Recovery Strategy**:
- **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

#### [F07] Remove future canopy fallback and restore evaporation memory

- **Priority**: `P1` | **Estimate**: `24-40 hours` | **Dependencies**: `F03, F04, F06` | **Lane**: `Trajectory Lane`
- **R3 Requirements**: `AB-AGR-006, AB-AGR-007, AB-AGR-008`
- **Target Production Files**:
  - [`services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - [`services/agribrain/layer3_water/runner.py`](../services/agribrain/layer3_water/runner.py)

**Architectural Problem & Defect Basis**:
The historical vegetation extractor eventually falls back to the current veg_state when no earlier canopy exists. The water runner defaults days_since_wetting to zero and calculates top storage as theta[0]*100 regardless of actual top-layer thickness.

**Step-by-Step Implementation Instructions**:
1. Resolve historical canopy only from records eligible for each step and label persisted priors.
2. Remove endpoint canopy fallback into earlier days unless it is explicitly a scenario reconstruction.
3. Restore the previous evaporation state and wetted fraction into each step.
4. Derive surface storage from actual layer thickness and propagate method-specific wetting.

**Domain Invariants & Edge Case Handling**:
- Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Earlier steps never consume later observed canopy.
- A dry sequence advances evaporation memory across restart and sparse replay.
- Changing top-layer thickness changes surface storage consistently.

**Verification & Recovery Strategy**:
- **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

#### [F08] Make trajectory invalidation include parameters and predecessor content

- **Priority**: `P1` | **Estimate**: `24-40 hours` | **Dependencies**: `F03, F04, F06` | **Lane**: `Trajectory Lane`
- **R3 Requirements**: `AB-DAT-011, AB-DAT-012, AB-AGR-007`
- **Target Production Files**:
  - [`services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)

**Architectural Problem & Defect Basis**:
_state_digest returns theta values when present and omits the rest of a SoilWaterState. Step forcing hashes also omit soil parameter epoch and model identity. A profile correction can therefore leave earlier cached transitions intact.

**Step-by-Step Implementation Instructions**:
1. Replace repr and rounded scalar fingerprints with canonical content digests.
2. Include full profile, crop/geometry epoch, solver version, observation payload and predecessor digest.
3. Invalidate from the earliest changed transition for parameter corrections as well as weather changes.
4. Preserve previously issued forecasts while creating a separate corrected retrospective trajectory.

**Domain Invariants & Edge Case Handling**:
- Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Identical moisture with different conductivity or retention cannot share a trajectory key.
- Parameter changes recompute affected predecessors and descendants.
- Repeated identical requests are idempotent.

**Verification & Recovery Strategy**:
- **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

#### [F09] Persist coupled state with scoped concurrency and restart recovery

- **Priority**: `P1` | **Estimate**: `48-80 hours` | **Dependencies**: `F02, F03, F08` | **Lane**: `Trajectory Lane`
- **R3 Requirements**: `AB-DAT-003, AB-DAT-012, AB-DAT-013, AB-ARC-008, AB-AGR-006`
- **Target Production Files**:
  - [`services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - [`services/agribrain/world_model/canonical_worldline.py`](../services/agribrain/world_model/canonical_worldline.py)
  - [`services/agribrain/layer05_asmae/history/worldline_service.py`](../services/agribrain/layer05_asmae/history/worldline_service.py)

**Architectural Problem & Defect Basis**:
Hydraulic histories, event versions and withdrawals are held in process dictionaries keyed principally by plot ID. These cannot themselves establish durable multi-replica recovery, tenant scope or an atomic predecessor chain.

**Step-by-Step Implementation Instructions**:
1. Move parameter epochs, action versions and hydraulic checkpoints to the canonical scoped store.
2. Use tenant, plot, cycle, geometry and namespace in identities.
3. Commit transition and analysis receipts with compare-and-swap on the predecessor head.
4. Recover from committed checkpoints and replay appended corrections under a fenced lease.

**Domain Invariants & Edge Case Handling**:
- Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Cold restart equals warm replay.
- Two workers cannot publish different successors for one head.
- Cancellation, withdrawal and late correction survive restart and replica changes.

**Verification & Recovery Strategy**:
- **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

#### [F39] Make telemetry persistence and replay protection concurrency safe

- **Priority**: `P0` | **Estimate**: `40-72 hours` | **Dependencies**: `F01, F09` | **Lane**: `Trajectory Lane`
- **R3 Requirements**: `AB-DAT-001, AB-DAT-003, AB-DAT-011, AB-DAT-013, AB-ARC-008, AB-ARC-009`
- **Target Production Files**:
  - [`services/agribrain/sensor_runtime/security.py`](../services/agribrain/sensor_runtime/security.py)
  - [`services/agribrain/sensor_runtime/storage.py`](../services/agribrain/sensor_runtime/storage.py)
  - [`services/agribrain/app/main.py`](../services/agribrain/app/main.py)
  - [`services/agribrain/visual_sources/tile_proxy.py`](../services/agribrain/visual_sources/tile_proxy.py)

**Architectural Problem & Defect Basis**:
Two concurrent nonce writers both report success but the production file retains one nonce. Atomic rename protects file replacement, not the preceding read-modify-write. Five growing collections have no cardinality limits; their presence proves retention risk, not an observed OOM. Blind ring-buffer replacement could destroy raw scientific evidence.

**Step-by-Step Implementation Instructions**:
1. Combine nonce eligibility and registration in a shared atomic conditional insert with scoped unique keys and retention derived from the accepted replay window.
2. Persist immutable raw/normalized telemetry durably with message idempotency before making it visible.
3. Keep memory caches bounded by byte/cardinality budgets and expose retention/eviction metrics.
4. Use safe lock striping or lifecycle-managed keyed locks that cannot be evicted while held or awaited.
5. Bound rate-limiter identity retention without permitting an eviction/reset bypass across replicas.
6. Key bounding-box caches by tenant and geometry epoch with explicit invalidation.

**Domain Invariants & Edge Case Handling**:
- Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Two simultaneous unique nonces remain registered and the same nonce is accepted at most once.
- Replay rejection survives restart and concurrent replicas.
- Cache pressure does not erase the durable evidence corpus.
- High-cardinality keys stay within declared budgets without duplicating locks for one active key.
- Geometry corrections cannot reuse an old plot bounding box.

**Verification & Recovery Strategy**:
- **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

### Stage 04: F05 + F10 + F11 + F12 (100–176 hours)

**Stage Focus**: Execution of 4 package(s): F05, F10, F11, F12.  
**Engineering Estimate**: 100 to 176 hours.  

#### [F05] Use depth-aware soil observations and carry covariance

- **Priority**: `P1` | **Estimate**: `32-56 hours` | **Dependencies**: `F01, F04` | **Lane**: `Trajectory Lane`
- **R3 Requirements**: `AB-AGR-009, AB-DAT-007, AB-MES-013`
- **Target Production Files**:
  - [`services/agribrain/layer3_water/contracts/assimilation_state.py`](../services/agribrain/layer3_water/contracts/assimilation_state.py)
  - [`services/agribrain/layer3_water/assimilation/water_state_assimilator.py`](../services/agribrain/layer3_water/assimilation/water_state_assimilator.py)
  - [`services/agribrain/layer3_water/root_zone/availability.py`](../services/agribrain/layer3_water/root_zone/availability.py)

**Architectural Problem & Defect Basis**:
Probe profile values are assigned by array position to model layers. The contract does not provide a general per-reading depth support operator; a surface reading and a root-depth reading cannot be safely treated as interchangeable.

**Step-by-Step Implementation Instructions**:
1. Represent individual readings with depth interval, location, time, instrument and noise.
2. Construct the vertical observation operator from overlap or point support instead of list index.
3. Preserve correlated posterior uncertainty by layer and carry unsupported-depth flags to L4 and decisions.
4. Treat thermal and RF surrogates as calibrated conditional constraints with their own support.

**Domain Invariants & Edge Case Handling**:
- Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Reordered input readings yield the same update.
- A shallow reading cannot claim direct full root-zone observation.
- Depth mismatch and absent support produce a qualified partial result.

**Verification & Recovery Strategy**:
- **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

#### [F10] Repair the L3-to-L4 water boundary

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F03, F04, F05` | **Lane**: `Trajectory Lane`
- **R3 Requirements**: `AB-AGR-008, AB-AGR-010, AB-DAT-007`
- **Target Production Files**:
  - [`services/agribrain/layer4_nutrients/runner.py`](../services/agribrain/layer4_nutrients/runner.py)
  - [`services/agribrain/layer3_water/contracts/water_state.py`](../services/agribrain/layer3_water/contracts/water_state.py)
  - [`services/agribrain/layer3_water/contracts/assimilation_state.py`](../services/agribrain/layer3_water/contracts/assimilation_state.py)

**Architectural Problem & Defect Basis**:
L4 reads theta_fc, theta_wp, theta_sat and root_zone_storage_mm from SoilWaterState, which exposes profiles and total_profile_water_mm. Defaults 0.30/0.15/0.45 and 0.7*TAW replace actual supplied soil information.

**Step-by-Step Implementation Instructions**:
1. Consume a typed depth-aware Layer3ToLayer4BoundaryReceipt.
2. Integrate storage and retention over the defined root support instead of replacing them with generic scalars.
3. Keep daily drainage flux separate from seasonal accumulated drainage.
4. Carry missing support and uncertainty into nutrient, salinity and leaching calculations.

**Domain Invariants & Edge Case Handling**:
- Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- A non-loam profile reaches L4 without generic substitution.
- Root-zone storage matches the same depth integration as L3.
- One daily drainage receipt is counted once in cumulative nutrient transport.

**Verification & Recovery Strategy**:
- **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

#### [F11] Correct residual nitrogen demand and expose conservative pools

- **Priority**: `P0` | **Estimate**: `24-48 hours` | **Dependencies**: `F10` | **Lane**: `Trajectory Lane`
- **R3 Requirements**: `AB-AGR-010, AB-AGR-008`
- **Target Production Files**:
  - [`services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py`](../services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py)
  - [`services/agribrain/layer4_nutrients/runner.py`](../services/agribrain/layer4_nutrients/runner.py)

**Architectural Problem & Defect Basis**:
Actual N already includes applied N. The residual deficit is divided by recovery efficiency and then applied N is subtracted again. Controlled 5 t/ha, critical N 2%, 50 kg applied and 30 kg soil supply returned 36.67 rather than 86.67 kg/ha under the same assumed 0.60 efficiency.

**Step-by-Step Implementation Instructions**:
1. Remove the second subtraction under the existing residual-demand convention.
2. Define whether each quantity is cumulative applied, available soil, recovered plant N or additional dose.
3. Replace independent cumulative heuristics with conservative mineralization, uptake, loss and application pools.
4. Carry dose timing, formulation and recovery uncertainty into recommendations.

**Domain Invariants & Edge Case Handling**:
- Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- The controlled residual case returns 86.67 under its declared assumptions.
- Zero deficit produces zero additional demand.
- Nitrogen stock changes reconcile uptake, losses and applied mass.

**Verification & Recovery Strategy**:
- **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

#### [F12] Separate exposure verification from causal attribution

- **Priority**: `P0` | **Estimate**: `20-32 hours` | **Dependencies**: `F02` | **Lane**: `Execution Lane`
- **R3 Requirements**: `AB-EXE-005, AB-WM-006, AB-OMG-008`
- **Target Production Files**:
  - [`services/agribrain/layer6_exec/outcomes/metrics.py`](../services/agribrain/layer6_exec/outcomes/metrics.py)

**Architectural Problem & Defect Basis**:
A verified execution timestamp immediately assigns CAUSAL_ATTRIBUTED even though the implemented estimator is PRE_POST. A controlled +0.1 NDVI comparison received that causal label without a control or identification design.

**Step-by-Step Implementation Instructions**:
1. Keep delivered exposure as a separate qualification field.
2. Label uncontrolled pre/post metrics as observed associations even after verified execution.
3. Require an explicit identification record before estimating or labelling causal effect.
4. Integrate by real timestamps, preserve valid zero indices and record missing confounder data.

**Domain Invariants & Edge Case Handling**:
- Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict separation of exposure verification from causal attribution.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Verified exposure alone never grants causal effect.
- Unequal sampling intervals do not masquerade as NDVI-time integral changes.
- Negative results and unknown confounding remain in the outcome record.

**Verification & Recovery Strategy**:
- **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict separation of exposure verification from causal attribution.
- **Recovery**: Safe actuator state reconciliation: never erase delivered action records from operational logs; never blindly resend unacknowledged commands. Revert software behind explicit capability flags while maintaining field physical safety.

---

### Stage 05: F13 + F14 + F15 (68–124 hours)

**Stage Focus**: Execution of 3 package(s): F13, F14, F15.  
**Engineering Estimate**: 68 to 124 hours.  

#### [F13] Correct yield quantiles and distinguish calibrated distributions from heuristics

- **Priority**: `P1` | **Estimate**: `24-48 hours` | **Dependencies**: `F02, F12` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-AGR-014, AB-ML-005, AB-ECO-002`
- **Target Production Files**:
  - [`services/agribrain/layer6_yield/yield_forecast.py`](../services/agribrain/layer6_yield/yield_forecast.py)
  - [`services/agribrain/layer7_planning/engines/yve_yield_distribution.py`](../services/agribrain/layer7_planning/engines/yve_yield_distribution.py)
  - [`services/agribrain/layer7_planning/schema.py`](../services/agribrain/layer7_planning/schema.py)

**Architectural Problem & Defect Basis**:
L6 labels mean +/-1.645*sigma as P10/P90; these are approximately P5/P95 for a Gaussian. L7 constructs heuristic bands and returns p50 as mean despite explicitly noting skew.

**Step-by-Step Implementation Instructions**:
1. Use one distribution contract with quantile levels and support.
2. Correct normal P10/P90 to +/-1.2815516 sigma when a Gaussian assumption is actually intended.
3. Label L7 deterministic penalty bands as heuristic until fitted and calibrated.
4. Share joint yield, quality and economic samples across L6/L7/L8 instead of treating their numbers as interchangeable.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Quantile labels match their mathematical levels.
- Mean and median are distinct when the distribution is skewed.
- Mixture tails are derived from the mixture distribution and prospective coverage is reported.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

#### [F14] Repair L7-to-L8 crop scenario mapping

- **Priority**: `P0` | **Estimate**: `12-20 hours` | **Dependencies**: `F13` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-EXE-001, AB-DEC-001, AB-ECO-002`
- **Target Production Files**:
  - [`services/agribrain/layer7_planning/schema.py`](../services/agribrain/layer7_planning/schema.py)
  - [`services/agribrain/layer8_prescriptive/scenario_contract.py`](../services/agribrain/layer8_prescriptive/scenario_contract.py)
  - [`services/agribrain/layer8_prescriptive/runner.py`](../services/agribrain/layer8_prescriptive/runner.py)

**Architectural Problem & Defect Basis**:
The actual L7 fields are crop, yield_dist and econ. from_crop_planning_option reads crop_type, expected_yield or expected_profit. A representative actual-schema option lost potato and yield 42, returning unknown and 1.0.

**Step-by-Step Implementation Instructions**:
1. Map the actual typed L7 contract explicitly.
2. Preserve stable option ID, crop, yield distribution, economics and units.
3. Reject a schema mismatch instead of falling back to unknown and unitless 1.0.
4. Carry scenario provenance and compare operational interventions separately from seasonal crop choices.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Actual CropOptionEvaluation preserves crop and distribution.
- Profit can never fill a yield field.
- Missing required option data produces a qualified unavailable scenario.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

#### [F15] Unify weather constraints and final hard action limits

- **Priority**: `P0` | **Estimate**: `32-56 hours` | **Dependencies**: `F01, F06, F14` | **Lane**: `Execution Lane`
- **R3 Requirements**: `AB-DEC-003, AB-ECO-003, AB-EXE-001`
- **Target Production Files**:
  - [`services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py`](../services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py)
  - [`services/agribrain/layer8_prescriptive/engines/salinity_leaching.py`](../services/agribrain/layer8_prescriptive/engines/salinity_leaching.py)
  - [`services/agribrain/layer8_prescriptive/scheduler.py`](../services/agribrain/layer8_prescriptive/scheduler.py)
  - [`services/agribrain/layer8_prescriptive/runner.py`](../services/agribrain/layer8_prescriptive/runner.py)

**Architectural Problem & Defect Basis**:
Missing spray weather remains allowed. [{}] schedules a spray as CONFIRMED. Leaching raised max_safe from 21 to 27.7 mm and recommended 23.1. Scheduler derives dates by list position and its wind threshold differs from the drift gate.

**Step-by-Step Implementation Instructions**:
1. Normalize weather units, valid intervals and quality before every action constraint.
2. Treat absent mandatory safety variables as unqualified, with a clear measurement or confirmation requirement.
3. Preserve immutable hard constraints and never increase their ceiling during agronomic adjustments.
4. Apply one final feasibility pass after all rate modifiers, zone aggregation and scheduling, including dated legal/resource constraints.

**Domain Invariants & Edge Case Handling**:
- Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Missing or invalid wind cannot yield a confirmed spray.
- Every final dose stays within the original hard cap and budget.
- Reordering dated forecast rows does not change the chosen valid slot.

**Verification & Recovery Strategy**:
- **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.
- **Recovery**: Safe actuator state reconciliation: never erase delivered action records from operational logs; never blindly resend unacknowledged commands. Revert software behind explicit capability flags while maintaining field physical safety.

---

### Stage 06: F16 + F17 + F18 + F19 (88–148 hours)

**Stage Focus**: Execution of 4 package(s): F16, F17, F18, F19.  
**Engineering Estimate**: 88 to 148 hours.  

#### [F16] Enforce quota and watchdog independently of telemetry

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01` | **Lane**: `Execution Lane`
- **R3 Requirements**: `AB-EXE-004, AB-DEC-003`
- **Target Production Files**:
  - [`services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)
  - [`services/agribrain/irrigation_runtime/safety.py`](../services/agribrain/irrigation_runtime/safety.py)

**Architectural Problem & Defect Basis**:
An exhausted quota blocked dispatch only when a nonempty readings dictionary was supplied. An expired duration stopped the local driver only after nonempty readings arrived. Both checks currently sit behind if sensor_readings.

**Step-by-Step Implementation Instructions**:
1. Always check water budgets before command submission.
2. Run duration watchdogs on an independent monotonic timer.
3. Define critical sensor freshness and missingness policies explicitly.
4. Persist reservation and delivered-water reconciliation so concurrent commands cannot overspend quota.

**Domain Invariants & Edge Case Handling**:
- Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Zero remaining budget produces zero physical start calls with None, empty or present telemetry.
- Duration expiration stops a running event without new sensor messages.
- Two reservations cannot jointly exceed the remaining budget.

**Verification & Recovery Strategy**:
- **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.
- **Recovery**: Safe actuator state reconciliation: never erase delivered action records from operational logs; never blindly resend unacknowledged commands. Revert software behind explicit capability flags while maintaining field physical safety.

---

#### [F17] Keep actuator operation state until physical completion

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F16` | **Lane**: `Execution Lane`
- **R3 Requirements**: `AB-EXE-002, AB-EXE-003, AB-EXE-004`
- **Target Production Files**:
  - [`services/agribrain/irrigation_runtime/actuator.py`](../services/agribrain/irrigation_runtime/actuator.py)
  - [`services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)

**Architectural Problem & Defect Basis**:
On successful start acknowledgement, execute_with_safety clears active_command and sets ONLINE although the driver is physically running. A second start was accepted; excessive-flow checks lost the commanded rate. STOP_ZONE is also rejected while EXECUTING.

**Step-by-Step Implementation Instructions**:
1. Separate command transport acknowledgement from operation completion.
2. Retain operation ownership, target flow and active event until verified stop/completion.
3. Allow stop and emergency stop through busy-state checks.
4. Reconcile controller telemetry against the persistent operation rather than transport status.

**Domain Invariants & Edge Case Handling**:
- Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Second conflicting start is rejected while physical execution continues.
- Dynamic flow checks retain the target command.
- Normal stop remains admissible during execution and is recorded once.

**Verification & Recovery Strategy**:
- **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.
- **Recovery**: Safe actuator state reconciliation: never erase delivered action records from operational logs; never blindly resend unacknowledged commands. Revert software behind explicit capability flags while maintaining field physical safety.

---

#### [F18] Reconcile ambiguous command failures before retry

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F17` | **Lane**: `Execution Lane`
- **R3 Requirements**: `AB-EXE-003, AB-ARC-008`
- **Target Production Files**:
  - [`services/agribrain/irrigation_runtime/actuator.py`](../services/agribrain/irrigation_runtime/actuator.py)
  - [`services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)

**Architectural Problem & Defect Basis**:
A transient acknowledgement failure leaves EXECUTING; the retry is then rejected by the same busy-state validator. Only one send occurred, followed by FAILED, despite the declared retry path.

**Step-by-Step Implementation Instructions**:
1. Give retries the same operation identity and attempt sequence.
2. Query controller state after timeout to distinguish applied, not applied and unknown.
3. Permit only safe idempotent retries and retain ownership during uncertainty.
4. Restore event and controller reconciliation on process restart.

**Domain Invariants & Edge Case Handling**:
- Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- A retry never duplicates a delivered dose.
- An acknowledgement timeout does not automatically mean no physical application.
- Own-operation retry is not rejected as an unrelated competing command.

**Verification & Recovery Strategy**:
- **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.
- **Recovery**: Safe actuator state reconciliation: never erase delivered action records from operational logs; never blindly resend unacknowledged commands. Revert software behind explicit capability flags while maintaining field physical safety.

---

#### [F19] Implement interlock persistence, debounce and stable violation keys

- **Priority**: `P1` | **Estimate**: `16-28 hours` | **Dependencies**: `F16, F17` | **Lane**: `Execution Lane`
- **R3 Requirements**: `AB-EXE-004, AB-EXE-003`
- **Target Production Files**:
  - [`services/agribrain/irrigation_runtime/safety.py`](../services/agribrain/irrigation_runtime/safety.py)
  - [`services/agribrain/irrigation_runtime/actuator.py`](../services/agribrain/irrigation_runtime/actuator.py)

**Architectural Problem & Defect Basis**:
The monitor emits a high-pressure violation immediately despite a configured 5-second duration. It tests interlock:device in _active_violations but stores violations by generated violation_id, so the same breach emits repeatedly.

**Step-by-Step Implementation Instructions**:
1. Track first breach, duration, recovery and freshness using monotonic time.
2. Index active violation state by device and interlock while preserving unique event records.
3. Implement the declared manual/automatic reset rules.
4. Make stop actions idempotent and rehydrate active protections after restart.

**Domain Invariants & Edge Case Handling**:
- Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict separation of exposure verification from causal attribution.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Configured debounce is honored with fake-clock probes.
- A sustained breach emits one active violation until a qualifying reset.
- Missing or nonfinite readings cannot count as normal pressure.

**Verification & Recovery Strategy**:
- **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict separation of exposure verification from causal attribution.
- **Recovery**: Safe actuator state reconciliation: never erase delivered action records from operational logs; never blindly resend unacknowledged commands. Revert software behind explicit capability flags while maintaining field physical safety.

---

### Stage 07: F20 + F34 (64–104 hours)

**Stage Focus**: Execution of 2 package(s): F20, F34.  
**Engineering Estimate**: 64 to 104 hours.  

#### [F20] Qualify post-irrigation readings before confirming delivery

- **Priority**: `P0` | **Estimate**: `32-48 hours` | **Dependencies**: `F02, F05, F12, F17` | **Lane**: `Execution Lane`
- **R3 Requirements**: `AB-EXE-005, AB-DAT-007, AB-DAT-013`
- **Target Production Files**:
  - [`services/agribrain/irrigation_runtime/validation.py`](../services/agribrain/irrigation_runtime/validation.py)

**Architectural Problem & Defect Basis**:
Foreign stale duplicate readings returned CONFIRMED with confidence 0.95 while the report listed the configured authorized sensor ID. The validator appends readings without enforcing the configured device, time window or uniqueness.

**Step-by-Step Implementation Instructions**:
1. Validate reading identity, tenant, plot/zone, depth, calibration and time support.
2. Deduplicate measurement IDs and require post-action measurements inside the window.
3. Base expected response on verified delivered exposure and the same hydrological support, not solely target_volume_mm.
4. Keep moisture response distinct from delivery proof and disallow calibration promotion from unqualified samples.

**Domain Invariants & Edge Case Handling**:
- Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict separation of exposure verification from causal attribution.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Foreign, stale and duplicate records do not raise confirmation confidence.
- Reports list the sensors that actually contributed.
- Rain, drainage, sensor support and delivery uncertainty are accounted for.

**Verification & Recovery Strategy**:
- **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict separation of exposure verification from causal attribution.
- **Recovery**: Safe actuator state reconciliation: never erase delivered action records from operational logs; never blindly resend unacknowledged commands. Revert software behind explicit capability flags while maintaining field physical safety.

---

#### [F34] Separate input accounting from applied agronomic exposure

- **Priority**: `P1` | **Estimate**: `32-56 hours` | **Dependencies**: `F09, F11, F20` | **Lane**: `Execution Lane`
- **R3 Requirements**: `AW-PRO-009, AW-PRO-013, AB-DAT-007, AB-DAT-010, AB-AGR-010`
- **Target Production Files**:
  - [`src/app/api/inputs/route.ts`](../src/app/api/inputs/route.ts)
  - [`prisma/schema.prisma`](../prisma/schema.prisma)
  - [`services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - [`services/agribrain/layer4_nutrients/runner.py`](../services/agribrain/layer4_nutrients/runner.py)

**Architectural Problem & Defect Basis**:
InputLog accepts arbitrary nonempty unit and type with an appliedAt default. Quantity/cost logging is not a complete exposure contract for formulation, applied status, spatial support and delivered dose. Future appliedAt is accepted as a date.

**Step-by-Step Implementation Instructions**:
1. Validate unit and input category against controlled registries.
2. Store purchased, stocked, planned and applied events separately.
3. Convert product quantity to nutrient mass or delivered water using formulation, area and support references.
4. Publish verified application exposure to Worldline and update financial totals idempotently.

**Domain Invariants & Edge Case Handling**:
- Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- A purchase or future plan cannot enter historical water/N balance.
- Product kg and elemental nutrient kg are never interchanged.
- Retry cannot double-count stock, cost or applied mass.

**Verification & Recovery Strategy**:
- **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.
- **Recovery**: Safe actuator state reconciliation: never erase delivered action records from operational logs; never blindly resend unacknowledged commands. Revert software behind explicit capability flags while maintaining field physical safety.

---

### Stage 08: F21 + F22 + F23 + F24 (88–144 hours)

**Stage Focus**: Execution of 4 package(s): F21, F22, F23, F24.  
**Engineering Estimate**: 88 to 144 hours.  

#### [F21] Freeze training-window payloads and include partition identity

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F02, F09` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-DAT-011, AB-DAT-013, AB-ML-001, AB-ML-007`
- **Target Production Files**:
  - [`services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)
  - [`services/agribrain/world_model/canonical_worldline.py`](../services/agribrain/world_model/canonical_worldline.py)

**Architectural Problem & Defect Basis**:
The frozen window contains mutable nested dictionaries. Mutating a value leaves its hash unchanged. The hash includes active event IDs but omits payload digests, tenant and namespace; two partitions produced the same hash.

**Step-by-Step Implementation Instructions**:
1. Use immutable or deeply copied canonical event snapshots.
2. Hash payload content, schema, partition, geometry/cycle and extraction policy.
3. Include supersession/retraction resolution and ordered parent evidence in the manifest.
4. Verify the digest again before dataset loading and model artifact creation.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Any included content change alters the manifest identity.
- Caller mutation cannot alter an issued window.
- Tenant/namespace boundaries have distinct manifest identities.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

#### [F22] Classify timing by event role rather than a universal causality rule

- **Priority**: `P0` | **Estimate**: `20-32 hours` | **Dependencies**: `F02, F21` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-DAT-004, AB-DAT-014, AB-ML-008`
- **Target Production Files**:
  - [`services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)
  - [`services/agribrain/world_model/contracts.py`](../services/agribrain/world_model/contracts.py)

**Architectural Problem & Defect Basis**:
The extractor quarantines knowledge_time < event_time for all event types. A weather forecast committed Jan 2 and valid Jan 3 was excluded as causality_violation_knowledge_precedes_event even though it was available at issuance.

**Step-by-Step Implementation Instructions**:
1. Define event-specific observation, forecast validity, planned action and availability fields.
2. Apply measurement chronology checks to measurements and issuance eligibility to forecasts/scenarios.
3. Validate each child input and revision against the cutoff.
4. Build separate manifests for inputs, later targets and retrospective reconstructions.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- An archived earlier-issued future forecast remains an eligible input.
- A future measurement is still excluded.
- A planned action stays a scenario and never becomes historical applied water.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

#### [F23] Commit forecast archives atomically before publishing cache entries

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F21, F22` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-DAT-011, AB-ARC-007, AB-ARC-008, AB-ASM-014`
- **Target Production Files**:
  - [`services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)

**Architectural Problem & Defect Basis**:
store_forecast populates cache before checking durable conflict. A rejected mean=99 remained retrievable in the new instance. In the rerun of the existing controlled example, the rejected prediction received RMSE 0.0 while disk retained the original forecast.

**Step-by-Step Implementation Instructions**:
1. Validate immutable content and resolve the durable record before altering cache.
2. Use an atomic conditional insert or equivalent lock/fence instead of exists-then-replace races.
3. Deep-freeze nested predictions and metadata.
4. Treat corrupt or conflicting records as explicit integrity errors instead of absence.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- After conflict, warm and cold readers return the committed forecast only.
- Concurrent incompatible writes produce one committed identity.
- Mutation cannot alter archived predictions or subsequent evaluation.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

#### [F24] Validate forecast distributions and make missing scores unavailable

- **Priority**: `P0` | **Estimate**: `20-32 hours` | **Dependencies**: `F13, F23` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-ML-005, AB-ML-010, AB-ASM-016`
- **Target Production Files**:
  - [`services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)
  - [`services/agribrain/layer6_yield/yield_forecast.py`](../services/agribrain/layer6_yield/yield_forecast.py)

**Architectural Problem & Defect Basis**:
ForecastRecord accepts NaN or an inconsistent 100-day horizon for a one-day target, crossed quantiles and negative standard deviation. compute_crps_quantiles({},10) returns 0.0; negative Gaussian sigma also gives a seemingly perfect score at its mean.

**Step-by-Step Implementation Instructions**:
1. Require finite consistent horizon, timezone-aware origin/target and a supported finite distribution.
2. Validate quantile levels and monotonicity, variable units/domain and nonnegative sigma.
3. Return unavailable with reason for missing distributions and reject invalid sigma.
4. Name finite-quantile pinball scoring accurately or implement a documented integration rule rather than silently treating an unweighted sparse average as exact CRPS.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Empty or malformed forecasts receive no numeric skill credit.
- Origin-target interval and horizon agree.
- Quantile coverage and scores use explicit levels and independently supported targets.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

### Stage 09: F25 + F26 + F27 + F28 + F29 (140–232 hours)

**Stage Focus**: Execution of 5 package(s): F25, F26, F27, F28, F29.  
**Engineering Estimate**: 140 to 232 hours.  

#### [F25] Report the actual EO inference backend and normalize its input contract

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-ML-002, AB-ML-014, AB-DAT-006`
- **Target Production Files**:
  - [`services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)

**Architectural Problem & Defect Basis**:
An ONNX session failure falls back internally to the spectral encoder, but infer still returns model_id=onnx_foundation and mode=onnx. _infer_onnx supplies 48 statistics while its stated adapter describes image tensors for Prithvi or Clay.

**Step-by-Step Implementation Instructions**:
1. Return backend identity and model artifact digest with every inference result.
2. Create explicit per-model tensor, band order, normalization and mask adapters.
3. On backend failure, publish the fallback role and cause, or make the capability unavailable.
4. Derive confidence from evaluated model/domain evidence rather than file presence.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- A failed ONNX call cannot label fallback features as learned model output.
- Wrong input shape fails at a clear contract boundary.
- Model identity includes weights, preprocessing and calibration versions.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

#### [F26] Hash complete EO support and distinguish missing bands from zero

- **Priority**: `P1` | **Estimate**: `20-32 hours` | **Dependencies**: `F25` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-DAT-002, AB-DAT-008, AB-DAT-011, AB-ML-002`
- **Target Production Files**:
  - [`services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)

**Architectural Problem & Defect Basis**:
EO tile hashes omit band identity, shape, cloud mask and geometry. B2 versus B3 with the same pixels, and 1x2 versus 2x1 arrays, collided. Missing bands are zero-filled without a general missing-modality token.

**Step-by-Step Implementation Instructions**:
1. Build digests from band identity/order, shape, numeric encoding, CRS/affine and validity/cloud masks.
2. Validate aligned shapes and mask coverage before pooling.
3. Pass missing-band masks into supported models or declare the fallback feature policy.
4. Require finite pixels and model-specific reflectance scale.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Different spectral support or masks have distinct identities.
- A missing band is distinguishable from true zero reflectance.
- A model cannot silently consume misaligned channels.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

#### [F27] Repair MESIA link-time axes and graph topology

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01, F26` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-MES-009, AB-ML-002`
- **Target Production Files**:
  - [`services/agribrain/mesia/learning/neural_receiver.py`](../services/agribrain/mesia/learning/neural_receiver.py)

**Architectural Problem & Defect Basis**:
Input ordering is B,L,S,C but flattened link embeddings are restored directly as B,S,L,D without a permutation. RadioGraphRepresentation accepts adjacency_mask and passes attn_mask=None; topology is ignored.

**Step-by-Step Implementation Instructions**:
1. Restore B,L,S,D and explicitly permute to B,S,L,D.
2. Define valid-link padding and graph masks with batch/time semantics.
3. Thread geometry, antenna and instrument epochs through the neural receiver.
4. Compare topology-aware output with an intentionally topology-free baseline.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Distinct link/time marker tensors preserve their identities.
- Invalid links do not affect pooling or attention.
- Changing topology affects only permitted message paths.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

#### [F28] Make MESIA masked pretraining respect complex channel semantics

- **Priority**: `P1` | **Estimate**: `32-48 hours` | **Dependencies**: `F27` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-MES-010, AB-MES-011, AB-ML-004`
- **Target Production Files**:
  - [`services/agribrain/mesia/learning/masked_link_trainer.py`](../services/agribrain/mesia/learning/masked_link_trainer.py)
  - [`services/agribrain/mesia/learning/neural_receiver.py`](../services/agribrain/mesia/learning/neural_receiver.py)

**Architectural Problem & Defect Basis**:
The decoder hardcodes latent_dim=128 although the receiver accepts other latent dimensions. Magnitude and phase masks are sampled independently; phase uses ordinary MSE, which makes values near -pi and +pi appear far apart.

**Step-by-Step Implementation Instructions**:
1. Derive decoder dimensions from the actual ModelArtifact configuration.
2. Use paired masks for complex channel elements and explicit link/time/frequency mask tokens.
3. Represent phase circularly or complex-valued and apply the corresponding likelihood/loss.
4. Exclude padded, missing and uncalibrated-invalid samples from objectives that require them, while retaining compatible discovery objectives.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Non-128 receiver configurations have compatible decoders.
- Equivalent phase angles have small circular error.
- Masked-loss support and normalization are reproducible and finite.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

#### [F29] Correct MESIA evaluation labels and establish independent biological validation

- **Priority**: `P1` | **Estimate**: `40-72 plus field work hours` | **Dependencies**: `F05, F24, F27, F28` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-MES-014, AB-MES-012, AB-ASM-003`
- **Target Production Files**:
  - [`services/agribrain/mesia/learning/asmae_evaluator.py`](../services/agribrain/mesia/learning/asmae_evaluator.py)
  - [`services/agribrain/mesia/behaviour/likelihood_engine.py`](../services/agribrain/mesia/behaviour/likelihood_engine.py)
  - [`services/agribrain/mesia/assimilation/observability_analyzer.py`](../services/agribrain/mesia/assimilation/observability_analyzer.py)

**Architectural Problem & Defect Basis**:
Evaluator loops over four hardcoded state names regardless of num_asmae_states and calls residual coefficient-of-determination Pearson R^2. ASMAE agreement alone cannot establish an independent biological reference or causal RF sensitivity.

**Step-by-Step Implementation Instructions**:
1. Bind evaluation channels to the actual state registry and support contract.
2. Label R-squared, correlation and predictive error as distinct metrics with constant-target handling.
3. Evaluate held-out sites, instruments, seasons and nuisance interventions against independent qualified measurements.
4. Promote only demonstrated per-variable capabilities and keep discovery representations available without biological claims.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Changing the configured state count cannot crash or mislabel channels.
- Agreement with an ASMAE teacher is reported as dependent evaluation.
- Biological capability requires independent calibration and nuisance-controlled validation.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

### Stage 10: F30 + F31 + F32 + F33 + F38 + F40 (172–296 hours)

**Stage Focus**: Execution of 6 package(s): F30, F31, F32, F33, F38, F40.  
**Engineering Estimate**: 172 to 296 hours.  

#### [F30] Scope conversational memory and cache identity

- **Priority**: `P1` | **Estimate**: `32-48 hours` | **Dependencies**: `F02, F09` | **Lane**: `Application Lane`
- **R3 Requirements**: `AB-L9-008, AB-L9-009, AB-DAT-013`
- **Target Production Files**:
  - [`services/agribrain/layer9_interface/runner.py`](../services/agribrain/layer9_interface/runner.py)
  - [`services/agribrain/layer9_interface/engines/conversation_memory.py`](../services/agribrain/layer9_interface/engines/conversation_memory.py)
  - [`services/agribrain/layer9_interface/engines/semantic_cache.py`](../services/agribrain/layer9_interface/engines/semantic_cache.py)

**Architectural Problem & Defect Basis**:
Runner opens conversational sessions by plot rather than user/thread identity. Semantic cache hashes rounded sensor values but omits tenant, plot, crop, language, policy and canonical state; tokenization removes numbers. Hashes for different tenants/crops matched, and apply 10 versus 100 kg tokenized identically. The active cache call path was not established in this pass.

**Step-by-Step Implementation Instructions**:
1. Define explicit tenant/user/thread/plot/cycle scope for conversational memory.
2. Resolve references only from sources authorized for the active thread.
3. Include state head, policy, model, language, intent and claim artifacts in cache identity.
4. Preserve numeric quantities and negation, and cache canonically generated artifacts rather than free-standing operational advice.

**Domain Invariants & Edge Case Handling**:
- Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- No user thread inherits another user narrative without authorized sharing.
- A changed dose, cutoff or policy invalidates the advice cache.
- Runtime tracing proves which cache paths are active before rollout.

**Verification & Recovery Strategy**:
- **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.
- **Recovery**: Safe UI fallback: return explicit UNAVAILABLE status to users rather than synthetic mocks or empty collections during service degradation.

---

#### [F31] Close the independent public AI advice path

- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01, F02, F15, F30` | **Lane**: `Application Lane`
- **R3 Requirements**: `AB-ARC-010, AB-L9-001, AB-L9-002, AB-L9-003, AW-PRO-018`
- **Target Production Files**:
  - [`src/app/api/ai/chat/route.ts`](../src/app/api/ai/chat/route.ts)
  - [`src/lib/agribrain/gemini-advisor.ts`](../src/lib/agribrain/gemini-advisor.ts)
  - [`src/app/api/agribrain/intent/route.ts`](../src/app/api/agribrain/intent/route.ts)

**Architectural Problem & Defect Basis**:
/api/ai/chat POST calls getAIAdvice/getQuickAdvice on caller-supplied farmContext with no session/plot authorization in the route and no canonical claim artifact. It is a separate advice path from the authorized intent pipeline.

**Step-by-Step Implementation Instructions**:
1. Require authentication and authorize any requested plot context.
2. Resolve trusted context server-side rather than treating browser fields as evidence.
3. Route plot-specific advice through canonical intent, claims, constraints and visible response.
4. Keep educational content explicitly educational and apply provider quotas and body limits.

**Domain Invariants & Edge Case Handling**:
- Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Unauthorized context cannot become plot-specific advice.
- Rendered numbers and prohibitions match the canonical artifact.
- Provider failures and missing evidence produce explicit unavailable or educational responses.

**Verification & Recovery Strategy**:
- **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.
- **Recovery**: Safe UI fallback: return explicit UNAVAILABLE status to users rather than synthetic mocks or empty collections during service degradation.

---

#### [F32] Replace demo calendar and misleading empty/error application states

- **Priority**: `P1` | **Estimate**: `32-56 hours` | **Dependencies**: `F09` | **Lane**: `Application Lane`
- **R3 Requirements**: `AW-PRO-008, AW-PRO-004, AB-DAT-005, AB-DAT-013`
- **Target Production Files**:
  - [`src/app/calendar/page.tsx`](../src/app/calendar/page.tsx)
  - [`src/app/api/cycles/[id]/tasks/route.ts`](../src/app/api/cycles/[id]/tasks/route.ts)
  - [`src/app/farm/page.tsx`](../src/app/farm/page.tsx)
  - [`src/app/api/dashboard/stats/route.ts`](../src/app/api/dashboard/stats/route.ts)

**Architectural Problem & Defect Basis**:
Calendar displays five static Jan/Feb 2026 demo tasks with readOnly completion. Farm page returns an empty farm list on database failure and exposes all farms in development fallback. Main dashboard returns successful zero stats after errors; PR #1 corrects that route only.

**Step-by-Step Implementation Instructions**:
1. Connect calendar to authorized persisted task/cycle records and scoped date-range queries.
2. Persist completion, deviations, assignees and timezone instead of local demo state.
3. Distinguish loading, empty, unauthorized and unavailable states in farms and dashboards.
4. Put demo records in an explicit isolated demo namespace and remove real-tenant development fallback.

**Domain Invariants & Edge Case Handling**:
- Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- A new empty account sees no fabricated tasks.
- Task edits survive reload and appear in the scientific exposure workflow when qualified.
- Database outage shows unavailable instead of a successful empty farm or zero statistics.

**Verification & Recovery Strategy**:
- **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.
- **Recovery**: Safe UI fallback: return explicit UNAVAILABLE status to users rather than synthetic mocks or empty collections during service degradation.

---

#### [F33] Validate photo zone ownership and database insert success

- **Priority**: `P1` | **Estimate**: `12-24 hours` | **Dependencies**: `F01, F02, F09` | **Lane**: `Application Lane`
- **R3 Requirements**: `AW-PRO-005, AW-PRO-011, AB-DAT-013, AB-ARC-007`
- **Target Production Files**:
  - [`src/app/api/evidence/add/route.ts`](../src/app/api/evidence/add/route.ts)
  - [`prisma/schema.prisma`](../prisma/schema.prisma)

**Architectural Problem & Defect Basis**:
The route authorizes plotId but only checks the format of zoneId; it does not verify zone membership. It returns success after raw insert without explicitly checking writeErrors, n or the inserted evidence identity.

**Step-by-Step Implementation Instructions**:
1. Resolve optional zone against the authorized plot and geometry epoch.
2. Validate observation timing and retain the server availability timestamp.
3. Check raw write outcome and return the canonical created evidence ID.
4. Preserve pending processing and use a durable admission/outbox event for retries.

**Domain Invariants & Edge Case Handling**:
- Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- A foreign valid-looking zone cannot be attached.
- Failed raw insertion cannot return success.
- Photo availability and processing state are recoverable after retry.

**Verification & Recovery Strategy**:
- **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.
- **Recovery**: Safe UI fallback: return explicit UNAVAILABLE status to users rather than synthetic mocks or empty collections during service degradation.

---

#### [F38] Restore failure ledgers, scoped loading and degraded publication

- **Priority**: `P0` | **Estimate**: `48-80 hours` | **Dependencies**: `F01, F02, F09, F31, F37` | **Lane**: `Evidence Lane`
- **R3 Requirements**: `AB-DAT-005, AB-DAT-013, AB-ARC-005, AB-ARC-007, AB-ARC-008, AB-L9-002, AB-L10-001`
- **Target Production Files**:
  - [`services/agribrain/orchestrator_v2/runner.py`](../services/agribrain/orchestrator_v2/runner.py)
  - [`services/agribrain/orchestrator_v2/chat_adapter.py`](../services/agribrain/orchestrator_v2/chat_adapter.py)
  - [`services/agribrain/layer10_sire/l10_frontend_bridge.py`](../services/agribrain/layer10_sire/l10_frontend_bridge.py)
  - [`services/agribrain/layer05_asmae/runner.py`](../services/agribrain/layer05_asmae/runner.py)
  - [`services/agribrain/layer05_asmae/geometry/external_scene_loader.py`](../services/agribrain/layer05_asmae/geometry/external_scene_loader.py)
  - [`services/agribrain/mesia/service.py`](../services/agribrain/mesia/service.py)
  - [`services/agribrain/layer2_veg_int/growth_engine.py`](../services/agribrain/layer2_veg_int/growth_engine.py)
  - [`services/agribrain/app/main.py`](../services/agribrain/app/main.py)
  - [`services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)
  - [`services/agribrain/orchestrator_v2/run_entrypoint.py`](../services/agribrain/orchestrator_v2/run_entrypoint.py)

**Architectural Problem & Defect Basis**:
The attached audit identifies nine real undefined-name sites, but several are caught and lose ledgers, scenes, scope or metadata instead of crashing the whole process. np annotation and guarded args are not the alleged immediate NameErrors. Progress can mark a mismatched completed job published merely because any canonical head exists. String MESIA plot references fabricate default tenant/farm after the missing coercer fails.

**Step-by-Step Implementation Instructions**:
1. Use the function-local decision timestamp in terminal no-data output and verify degraded output commits through the canonical publication contract.
2. Thread actual intent and userMode from typed context into local compression, routing and response policy.
3. Build geometry explicitly in the synthetic bridge helper and isolate that helper from normal product inputs.
4. Build failed ASMAE validation receipts from inp and its qualified geometry, removing arbitrary geometry-hash fallback.
5. Resolve external-scene resolution from validated grid metadata and preserve each rejected-scene reason.
6. Require qualified MESIA namespace rather than fabricated default scope.
7. Import statistics and IrrigationSystemType at their actual runtime definitions and verify relevant branches.
8. Parse completed timestamps robustly but derive published only from the exact committed output relation, including superseded heads.
9. Classify each caught failure as unavailable capability or partial result with observable diagnostic instead of silently manufacturing success.

**Domain Invariants & Edge Case Handling**:
- Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- The three reproduced external-scene, growth-spacing and missing-event cases no longer fail.
- Degraded L1 emits a committed no-data response using ts_now.
- ASMAE failure still returns its original error and also persists its failure receipt.
- A foreign or mismatched head cannot prove the completed job was published.
- Missing scope never becomes default_tenant/default_farm.
- Local response compression/routing use the real intent and mode.

**Verification & Recovery Strategy**:
- **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.
- **Recovery**: Additive schema versioning: historical states and issued forecasts remain immutable. Backward-compatible read adapters for legacy records; recompute retrospective views as new versioned entries referencing corrections.

---

#### [F40] Resolve annotation consumers and close verification evidence gaps

- **Priority**: `P1` | **Estimate**: `24-48 hours` | **Dependencies**: `F37, F38` | **Lane**: `Application Lane`
- **R3 Requirements**: `AB-ARC-004, AB-ARC-006, AB-ARC-012, AB-ML-014`
- **Target Production Files**:
  - [`services/agribrain/layer0/kalman_engine.py`](../services/agribrain/layer0/kalman_engine.py)
  - [`services/agribrain/mesia/identity/correlators.py`](../services/agribrain/mesia/identity/correlators.py)
  - [`services/agribrain/world_model/belief_snapshot.py`](../services/agribrain/world_model/belief_snapshot.py)
  - [`services/agribrain/layer4_nutrients/schema.py`](../services/agribrain/layer4_nutrients/schema.py)
  - [`services/agribrain/sensor_runtime/registry.py`](../services/agribrain/sensor_runtime/registry.py)
  - [`services/agribrain/layer05_asmae/background_jobs.py`](../services/agribrain/layer05_asmae/background_jobs.py)

**Architectural Problem & Defect Basis**:
The attachment lists 18 unique typing files rather than 19. Future annotations defer name evaluation: Kalman np and correlator Tuple definitions work, while get_type_hints fails. The fresh selected 410-file syntax check used Python 3.12.14, not the claimed full 1,310-file Python 3.13 environment. Zero syntax failures does not establish dataclass, Pydantic or runtime compatibility.

**Step-by-Step Implementation Instructions**:
1. Import or explicitly resolve annotation names where runtime consumers need them.
2. Use postponed type-only imports only when schema/introspection frameworks do not require resolution.
3. Audit the 18 cited files and every public dataclass/Pydantic/tool-schema consumer with the installed declared runtime.
4. Create a pinned full production manifest with exact exclusion rules and supported Python/dependency versions.
5. Compile the manifest and cold-load decorated schemas separately.
6. Classify exception handlers by recovery and published scientific effect, and run a history-aware secrets check without exposing values.
7. Publish scope and reproducible receipts rather than extending subset zero counts to the whole tree.

**Domain Invariants & Edge Case Handling**:
- Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- get_type_hints and production schema generation succeed for supported public contracts.
- The runtime and file manifest accompany every verification count.
- An unresolved annotation cannot silently invalidate a tool/schema registration.
- Secret, portability, dataclass and full-repository claims remain unqualified until their own checks complete.

**Verification & Recovery Strategy**:
- **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.
- **Recovery**: Safe UI fallback: return explicit UNAVAILABLE status to users rather than synthetic mocks or empty collections during service degradation.

---

### Stage 11: F35 + F36 + T11 (168–296 hours)

**Stage Focus**: Execution of 3 package(s): F35, F36, T11.  
**Engineering Estimate**: 168 to 296 hours.  

#### [F35] Repair drone driver import and complete process cleanup

- **Priority**: `P1` | **Estimate**: `20-36 hours` | **Dependencies**: `F09` | **Lane**: `Application Lane`
- **R3 Requirements**: `AW-PRO-011, AB-ARC-006, AB-ARC-008, AB-ARC-012`
- **Target Production Files**:
  - [`services/agribrain/drone_control/dispatcher.py`](../services/agribrain/drone_control/dispatcher.py)
  - [`services/agribrain/app/drone_routes.py`](../services/agribrain/app/drone_routes.py)
  - [`services/agribrain/layer05_asmae/background_jobs.py`](../services/agribrain/layer05_asmae/background_jobs.py)

**Architectural Problem & Defect Basis**:
Dispatcher imports drivers.mock_driver, absent from the pinned tree. The current ASMAE supervisor does terminate/wait on metadata-update failure, so the older blanket orphan-child finding must not be repeated. Its forced-kill branch does not wait again before releasing ownership.

**Step-by-Step Implementation Instructions**:
1. Lazy-load explicitly configured real drivers and move simulation behind an explicit test/development capability.
2. Return unavailable driver capability without breaking unrelated service import.
3. Complete terminate-kill-wait lifecycle and process-group cleanup under a bounded deadline.
4. Fence all child writes and publish final cleanup/ownership receipts.

**Domain Invariants & Edge Case Handling**:
- Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Missing optional drivers cannot disable service startup.
- Simulation cannot publish observed mission evidence.
- Forced-kill cleanup confirms process exit before resource ownership is released.

**Verification & Recovery Strategy**:
- **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.
- **Recovery**: Safe UI fallback: return explicit UNAVAILABLE status to users rather than synthetic mocks or empty collections during service degradation.

---

#### [F36] Require per-variable observability and independent predictive calibration

- **Priority**: `P1` | **Estimate**: `48-80 plus reference data hours` | **Dependencies**: `F01, F02, F24, F29` | **Lane**: `Learning Lane`
- **R3 Requirements**: `AB-ASM-003, AB-ASM-011, AB-ASM-013, AB-ASM-014, AB-ASM-015, AB-ASM-016, AB-ASM-001, AB-ASM-002, AB-ASM-004, AB-ASM-005, AB-ASM-009, AB-ASM-010, AB-ASM-012`
- **Target Production Files**:
  - [`services/agribrain/layer05_asmae/training/exporter.py`](../services/agribrain/layer05_asmae/training/exporter.py)
  - [`services/agribrain/layer05_asmae/observation/index_state_mapping.py`](../services/agribrain/layer05_asmae/observation/index_state_mapping.py)
  - [`services/agribrain/layer05_asmae/constraints/radiometric.py`](../services/agribrain/layer05_asmae/constraints/radiometric.py)
  - [`services/agribrain/layer05_asmae/retrovalidation/engine.py`](../services/agribrain/layer05_asmae/retrovalidation/engine.py)

**Architectural Problem & Defect Basis**:
Exporter grants weights per state from shared microzone retro score, sigma, BMA disagreement and blocked states. Those gates are useful, but do not themselves demonstrate independent sensitivity for every exported state. A primary sensor pass and two active experts cannot prove all physiological coordinates or calibrated prediction.

**Step-by-Step Implementation Instructions**:
1. Build a per-state support ledger connecting actual operator sensitivity and independent references to each label.
2. Carry dependence groups for indices from shared native acquisitions and BMA experts sharing evidence.
3. Use archived prospective issuance cohorts separately from hindcasts and persistence, with per-variable/horizon calibration.
4. Tune process noise and rejection thresholds on frozen independent cohorts instead of selecting values for a passing pipeline flag.

**Domain Invariants & Edge Case Handling**:
- Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- An unsupported coordinate has explicit prior/reconstruction role and compatible objective weight.
- Derived indices and shared teachers do not count as independent references.
- Forecast skill, coverage and domain evidence are reported per variable and horizon against stated baselines.

**Verification & Recovery Strategy**:
- **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).
- **Recovery**: Model and dataset demotion: deprecate invalid training manifests by hash identity without overwriting historical run logs. Retain committed forecast evaluation records with explicit invalidation markers.

---

#### [T11] Operational reproducibility, provider resilience and publication integrity

- **Priority**: `Target` | **Estimate**: `100-180 hours` | **Dependencies**: `F09, F23, F25, F31, F35` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-ARC-004, AB-ARC-005, AB-ARC-006, AB-ARC-007, AB-ARC-008, AB-ARC-009, AB-ARC-010, AB-ARC-011, AB-ARC-012, AB-DAT-001, AB-DAT-002, AB-DAT-009, AB-ASM-006, AB-ASM-007, AB-ASM-008`
- **Target Production Files**:
  - [`services/agribrain/layer0/data_gateway/request_broker.py`](../services/agribrain/layer0/data_gateway/request_broker.py)
  - [`services/agribrain/layer05_asmae/background_jobs.py`](../services/agribrain/layer05_asmae/background_jobs.py)
  - [`services/agribrain/orchestrator_v2/storage.py`](../services/agribrain/orchestrator_v2/storage.py)
  - [`services/agribrain/app/main.py`](../services/agribrain/app/main.py)

**Architectural Problem & Defect Basis**:
The selected corpus contains substantial gateway, lease and publication foundations. Complete failure behavior must be demonstrated across live service boundaries, rather than inferred from module presence.

**Step-by-Step Implementation Instructions**:
1. Lock dependencies and produce code/image/model/config identities for each run.
2. Trace all production entrypoints to one source admission and scoped publication policy.
3. Run bounded provider outage, corruption, timeout, restart, duplicate and concurrent-writer drills.
4. Add operational telemetry for rejected evidence, stale state, scope, compute resources and committed publication heads.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- A response never points to an uncommitted or foreign result.
- Provider outage degrades only dependent capabilities.
- Recovery reproduces the same canonical artifacts without duplicate execution.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

### Stage 12: T01 + T02 + T12 (240–420 hours)

**Stage Focus**: Execution of 3 package(s): T01, T02, T12.  
**Engineering Estimate**: 240 to 420 hours.  

#### [T01] One canonical coupled agricultural trajectory

- **Priority**: `Target` | **Estimate**: `80-140 hours` | **Dependencies**: `F03, F09, F10, F11` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-WM-001, AB-AGR-002, AB-AGR-008, AB-ARC-001, AB-ARC-002, AB-ARC-003, AB-AGR-001`
- **Target Production Files**:
  - [`services/agribrain/world_model/canonical_worldline.py`](../services/agribrain/world_model/canonical_worldline.py)
  - [`services/agribrain/world_model/belief_snapshot.py`](../services/agribrain/world_model/belief_snapshot.py)
  - [`services/agribrain/layer2_contracts/state_transition.py`](../services/agribrain/layer2_contracts/state_transition.py)
  - [`services/agribrain/orchestrator_v2/runner.py`](../services/agribrain/orchestrator_v2/runner.py)

**Architectural Problem & Defect Basis**:
Existing specialist states and Worldline contracts are a basis, but a shared sequential water/nutrient/vegetation transition must be established before learned rollout targets are trusted.

**Step-by-Step Implementation Instructions**:
1. Define a versioned X/Z/H/M/U snapshot with availability and support per coordinate.
2. Specify operator-splitting order and feed L3/L4 constraints back into the next vegetation growth transition.
3. Link transition, analysis, management and diagnostic receipts to one predecessor.
4. Publish read-only projections for L7-L10 rather than independent local physical reconstructions.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- A consumed-feedback receipt proves water/N limitations affected subsequent growth.
- Daily, sparse, cold and corrected replay agree on the same interval semantics.
- Every output resolves to the same authorized state head.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

#### [T02] Objective-specific longitudinal learning corpus

- **Priority**: `Target` | **Estimate**: `80-140 hours` | **Dependencies**: `F21, F22, F25, F26, F36, T01` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-ML-001, AB-ML-006, AB-ML-007, AB-ML-008, AB-ML-014, AB-ML-015`
- **Target Production Files**:
  - [`services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)
  - [`services/agribrain/asmae_learn/dataset_builder.py`](../services/agribrain/asmae_learn/dataset_builder.py)
  - [`services/agribrain/asmae_learn/model_registry.py`](../services/agribrain/asmae_learn/model_registry.py)

**Architectural Problem & Defect Basis**:
ASMAE candidate builders and bitemporal extraction provide useful scaffolding; they do not replace a complete objective-specific multimodal corpus with frozen independent splits.

**Step-by-Step Implementation Instructions**:
1. Define input tokens, masks, observation policy, labels and target-support eligibility per objective.
2. Build immutable manifests and partition plots/sites/seasons/instruments before fitting preprocessing.
3. Permit partial and synthetic data for compatible objectives and prohibit promotion to independent biological truth.
4. Produce reproducible dataset/model artifacts with lineage, consent, licensing and calibration metadata.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- No target parent or post-cutoff input leaks into a predictive window.
- Holdout partitions remain isolated across derived products.
- A dataset snapshot can be regenerated byte-for-byte.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

#### [T12] Independent agronomic validation and reference field program

- **Priority**: `Target` | **Estimate**: `80-140 engineering plus seasonal research hours` | **Dependencies**: `F12, F20, F24, F29, F36, T01` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-ASM-016, AB-AGR-011, AB-AGR-012, AB-MES-014, AB-ML-009, AB-ML-010, AB-OMG-013, AB-OMG-015`
- **Target Production Files**:
  - [`services/agribrain/ground_truth/registry.py`](../services/agribrain/ground_truth/registry.py)
  - [`services/agribrain/layer05_asmae/retrovalidation/engine.py`](../services/agribrain/layer05_asmae/retrovalidation/engine.py)
  - [`services/agribrain/mesia/learning/asmae_evaluator.py`](../services/agribrain/mesia/learning/asmae_evaluator.py)

**Architectural Problem & Defect Basis**:
Passing suites and software probes verify behaviors, not empirical biological sensitivity, calibrated yield, intervention value or mechanisms. R3 requires independent observations and discriminating experiments.

**Step-by-Step Implementation Instructions**:
1. Predeclare targets, horizons, cohorts, metrics and applicability domains before tuning.
2. Recruit independent reference plots with depth water, EC, delivery, canopy and qualified crop/outcome observations.
3. Compare simpler mechanistic/statistical baselines and inspect calibration, missingness and measurement selection.
4. Run safe discriminating studies separating water shortage, salinity, hypoxia, hydraulic memory, delivery heterogeneity and biological alternatives.

**Domain Invariants & Edge Case Handling**:
- Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Reference labels are independent of the model under evaluation.
- Prospective results include uncertainty, sample size and negative outcomes.
- Field evidence is reviewed against the declared target before any new capability is promoted.

**Verification & Recovery Strategy**:
- **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

### Stage 13: T03 + T06 (280–520 hours)

**Stage Focus**: Execution of 2 package(s): T03, T06.  
**Engineering Estimate**: 280 to 520 hours.  

#### [T03] Multimodal foundation representation and local adaptation

- **Priority**: `Target` | **Estimate**: `160-300 plus compute hours` | **Dependencies**: `T02, F27, F28` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-ML-002, AB-ML-003, AB-ML-004, AB-ML-009, AB-ML-010, AB-ML-011, AB-ML-012, AB-ML-013`
- **Target Production Files**:
  - [`services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - [`services/agribrain/mesia/learning/neural_receiver.py`](../services/agribrain/mesia/learning/neural_receiver.py)
  - [`services/agribrain/asmae_learn/model_registry.py`](../services/agribrain/asmae_learn/model_registry.py)

**Architectural Problem & Defect Basis**:
An EO inference wrapper and an RF encoder are not yet a demonstrated shared longitudinal foundation model. The existing specialist encoders should be retained and corrected.

**Step-by-Step Implementation Instructions**:
1. Start with small time-series and single-modality baselines on the frozen corpus.
2. Train masked temporal/multimodal encoders with support and modality dropout.
3. Add shared X/Z alignment, calibrated heads, OOD detection and local adapters.
4. Evaluate transfer and rich-to-sparse distillation before federated deployment with secure aggregation and privacy accounting.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Representation improves at least one predeclared held-out task beyond smaller baselines.
- Missing modalities have defined behavior and measured degradation.
- Artifact, preprocessing, split and calibration versions reproduce the result.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

#### [T06] MESIA native acquisition, metrology and capability commissioning

- **Priority**: `Target` | **Estimate**: `120-220 plus hardware/field work hours` | **Dependencies**: `F01, F05, F27, F28, F29, T02` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-MES-001, AB-MES-002, AB-MES-003, AB-MES-004, AB-MES-005, AB-MES-006, AB-MES-007, AB-MES-008, AB-MES-012, AB-MES-013, AB-MES-015`
- **Target Production Files**:
  - [`services/agribrain/mesia/service.py`](../services/agribrain/mesia/service.py)
  - [`services/agribrain/mesia/lanes/wifi/csi_extractor.py`](../services/agribrain/mesia/lanes/wifi/csi_extractor.py)
  - [`services/agribrain/mesia/behaviour/likelihood_engine.py`](../services/agribrain/mesia/behaviour/likelihood_engine.py)
  - [`services/agribrain/mesia/assimilation/spatial_lattice.py`](../services/agribrain/mesia/assimilation/spatial_lattice.py)

**Architectural Problem & Defect Basis**:
Recent missing-SNR, calibration uncertainty and north-up corrections are retained. Native instrument commissioning and independent biological capability remain distinct from a passing software suite.

**Step-by-Step Implementation Instructions**:
1. Archive native complex CSI and available GNSS/RF observations with instrument and two-clock timing.
2. Version topology, actual poses, antenna, firmware, channel/band and calibration epochs.
3. Qualify missingness, nuisance covariance and geometric kernels against the canonical lattice.
4. Progress discovery/configuration/commissioning/calibration states and promote only validated individual capabilities.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Commodity hardware modalities remain optional and explicitly characterized.
- Calibration drift does not become biology.
- Native records and instrument state reproduce the same qualified likelihood.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

### Stage 14: T04 + T05 (240–440 hours)

**Stage Focus**: Execution of 2 package(s): T04, T05.  
**Engineering Estimate**: 240 to 440 hours.  

#### [T04] Hybrid world model with conservative multi-horizon rollout

- **Priority**: `Target` | **Estimate**: `160-300 plus prospective data hours` | **Dependencies**: `T01, T02, T03, F23, F24, F12` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-WM-002, AB-WM-003, AB-WM-004, AB-WM-005, AB-WM-006`
- **Target Production Files**:
  - [`services/agribrain/world_model/contracts.py`](../services/agribrain/world_model/contracts.py)
  - [`services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)
  - [`services/agribrain/layer05_asmae/retrovalidation/future_projection.py`](../services/agribrain/layer05_asmae/retrovalidation/future_projection.py)

**Architectural Problem & Defect Basis**:
Forecast/archive and state contracts are scaffolding. They should be the basis of a learned hybrid transition, rather than being counted as the learned world model itself.

**Step-by-Step Implementation Instructions**:
1. Retain mechanistic conserved transitions and fit bounded residual dynamics conditioned on actual/scenario action.
2. Forecast explicit states, latent representation and future observation distributions jointly.
3. Test memory sufficiency against simpler Markov and history baselines.
4. Evaluate paired intervention rollouts only where exposure, support and identification assumptions are valid.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Rollouts remain physically admissible with explicit residual ledgers.
- Prospective multi-horizon skill exceeds stated persistence/mechanistic baselines on held-out domains.
- Counterfactual output states its identifying assumptions and uncertainty.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

#### [T05] Decision economics from shared outcome distributions

- **Priority**: `Target` | **Estimate**: `80-140 plus outcomes hours` | **Dependencies**: `F12, F13, F14, F15, T04` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-DEC-001, AB-DEC-002, AB-DEC-003, AB-ECO-001, AB-ECO-002, AB-ECO-003, AB-ECO-004`
- **Target Production Files**:
  - [`services/agribrain/layer7_planning/runner.py`](../services/agribrain/layer7_planning/runner.py)
  - [`services/agribrain/layer8_prescriptive/runner.py`](../services/agribrain/layer8_prescriptive/runner.py)
  - [`services/agribrain/layer6_exec/outcomes/metrics.py`](../services/agribrain/layer6_exec/outcomes/metrics.py)

**Architectural Problem & Defect Basis**:
Current heuristics can be useful baselines but fixed yield/impact ratios are not measured marginal economic value. Decisions must share distributions and actual constraints.

**Step-by-Step Implementation Instructions**:
1. Add versioned price, labor, energy, water, input, quality and transport assumptions.
2. Derive margins and downside risk from joint outcome samples.
3. Compare no-action, measurement and intervention policies with immutable hard feasibility constraints.
4. Evaluate value of information against transparent measurement baselines and actual realized costs.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Currency, date, area and quantity units are explicit.
- Missing price becomes an assumption with sensitivity rather than observed value.
- Policy value uses independently observed outcomes and qualified causal assumptions.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

### Stage 15: T08 + T09 (300–540 hours)

**Stage Focus**: Execution of 2 package(s): T08, T09.  
**Engineering Estimate**: 300 to 540 hours.  

#### [T08] Finish AgriWise operational records and financial workflows

- **Priority**: `Target` | **Estimate**: `180-320 hours` | **Dependencies**: `F32, F33, F34, F09` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AW-PRO-001, AW-PRO-002, AW-PRO-005, AW-PRO-008, AW-PRO-009, AW-PRO-010, AW-PRO-012, AW-PRO-013, AW-PRO-014`
- **Target Production Files**:
  - [`prisma/schema.prisma`](../prisma/schema.prisma)
  - [`src/app/api/inputs/route.ts`](../src/app/api/inputs/route.ts)
  - [`src/app/api/cycles/[id]/tasks/route.ts`](../src/app/api/cycles/[id]/tasks/route.ts)

**Architectural Problem & Defect Basis**:
Existing farm, crop-cycle, task, equipment, input, market-price and cooperative models are a basis. The schema has no livestock model and price/trend records do not provide complete offer/order/logistics execution.

**Step-by-Step Implementation Instructions**:
1. Complete farm/cycle/rotation history with delegated ownership and scoped task resources.
2. Add stock ledger, equipment use/maintenance and linked actual exposures.
3. Add typed livestock, market offers/orders/quality/storage/transport workflows as proposed new modules.
4. Implement budget, costs and realized versus scenario economics without double counting.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Each workflow has persisted authorized records and error recovery.
- Livestock events and costs use their own domain schema.
- Stock/order/financial totals reconcile across cancellation, retry and correction.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

#### [T09] Unify language, voice, map and offline product projections

- **Priority**: `Target` | **Estimate**: `120-220 hours` | **Dependencies**: `F30, F31, F32, T01` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AW-PRO-003, AW-PRO-004, AW-PRO-006, AW-PRO-007, AW-PRO-015, AW-PRO-016, AW-PRO-017, AW-PRO-018, AB-L9-001, AB-L9-002, AB-L9-003, AB-L9-004, AB-L9-005, AB-L9-006, AB-L9-007, AB-L9-008, AB-L9-009, AB-L9-010, AB-L10-001`
- **Target Production Files**:
  - [`src/app/api/agribrain/intent/route.ts`](../src/app/api/agribrain/intent/route.ts)
  - [`src/lib/agribrain/surface-contract.ts`](../src/lib/agribrain/surface-contract.ts)
  - [`services/agribrain/layer9_interface/runner.py`](../services/agribrain/layer9_interface/runner.py)
  - [`services/agribrain/layer10_sire/runner.py`](../services/agribrain/layer10_sire/runner.py)

**Architectural Problem & Defect Basis**:
Authorized routes and surface contracts should become one consistent product projection. Multiple local advice and demo paths still need convergence; offline conflict and voice fidelity require explicit acceptance.

**Step-by-Step Implementation Instructions**:
1. Resolve one intent to one canonical visible response and typed claims.
2. Keep maps, numbers and explanations linked to the same state/support, including effective resolution.
3. Preserve values, negation and prohibitions across Arabic/French/voice and accessibility rendering.
4. Implement offline pending events with conflict resolution and visibly stale decision cutoffs.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Every visible response resolves to one canonical artifact.
- UI and translation do not manufacture numerical science.
- Offline actions reconcile without retroactively changing what a user knew.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

### Stage 16: T07 + T10 (360–660 hours)

**Stage Focus**: Execution of 2 package(s): T07, T10.  
**Engineering Estimate**: 360 to 660 hours.  

#### [T07] Omega scientific investigation loop

- **Priority**: `Target` | **Estimate**: `240-440 plus experiments hours` | **Dependencies**: `F12, F21, F36, T01, T02, T04` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-OMG-001, AB-OMG-002, AB-OMG-003, AB-OMG-004, AB-OMG-005, AB-OMG-006, AB-OMG-007, AB-OMG-008, AB-OMG-009, AB-OMG-010, AB-OMG-011, AB-OMG-012, AB-OMG-013, AB-OMG-014, AB-OMG-015, AB-OMG-016, AB-OMG-017, AB-OMG-018`
- **Target Production Files**:
  - [`services/agribrain/diagnostic_integration/contracts.py`](../services/agribrain/diagnostic_integration/contracts.py)
  - [`services/agribrain/world_model/canonical_worldline.py`](../services/agribrain/world_model/canonical_worldline.py)
  - [`services/agribrain/diagnostic_integration/promotion_service.py`](../services/agribrain/diagnostic_integration/promotion_service.py)

**Architectural Problem & Defect Basis**:
Diagnostic hypotheses and promotion services are reusable foundations. Omega as specified in R3 is a scientific discovery loop, not a confidence label or a renamed diagnostic tribunal.

**Step-by-Step Implementation Instructions**:
1. Create ScientificCase and a sealed epistemic Worldline for surprises, alternatives and model inadequacy.
2. Implement Bayesian/mechanistic comparison, simulation/BEL and causal identification with explicit assumptions.
3. Propose discriminating measurements/experiments with measurement-selection analysis, power, interference, stopping and consent.
4. Record falsification, negative results, independent replication and domain-bound knowledge artifacts before per-capability promotion.

**Domain Invariants & Edge Case Handling**:
- Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- A case follows surprise to competing explanations, discriminating prediction, experiment and replication.
- A latent or symbolic equation remains a candidate until appropriate evidence separates alternatives.
- Scientific success includes reduced ambiguity and negative findings, not only promoted claims.

**Verification & Recovery Strategy**:
- **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

#### [T10] Institutional aggregation and territorial world-model extension

- **Priority**: `Target` | **Estimate**: `120-220 plus regional data hours` | **Dependencies**: `T04, T05, T08, T09` | **Lane**: `Target Capability Lane`
- **R3 Requirements**: `AB-WM-007, AB-ECO-005, AW-PRO-014, AB-ARC-010, AB-ARC-011`
- **Target Production Files**:
  - [`prisma/schema.prisma`](../prisma/schema.prisma)
  - [`services/agribrain/world_model/contracts.py`](../services/agribrain/world_model/contracts.py)

**Architectural Problem & Defect Basis**:
Cooperatives and RegionalStats support product records but do not establish independently evaluated territorial policy effects, privacy-preserving aggregation or sovereign operation.

**Step-by-Step Implementation Instructions**:
1. Authorize aggregation cohorts and suppress potentially identifying small groups.
2. Model supply, water, market and environmental interactions hierarchically with uncertainty.
3. Evaluate policy and resource scenarios against independent regional outcomes.
4. Version sovereign deployment, licensing, egress and review/appeal pathways for high-impact use.

**Domain Invariants & Edge Case Handling**:
- Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- Fail-closed guarantee: any malformed input, non-finite float, or contract violation produces an explicit failure receipt.
- Multi-tenant isolation: enforce scoped tenant keys on all state caches and queries.

**Downstream Consumer Reconciliation**:
- All callers and downstream layers must consume typed objects with documented units and support.
- Preserve backward compatibility where legacy callers exist; deprecate unqualified dictionary fallbacks.

**Completion & Acceptance Criteria**:
- Regional summaries preserve uncertainty and authorized cohort scope.
- Policy scenarios are separated from observed effects.
- Territorial capability is evaluated independently rather than inherited from a plot metric.

**Verification & Recovery Strategy**:
- **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.
- **Recovery**: Scientific protocol versioning: maintain full provenance of hypotheses, priors, and baseline comparisons. Scientific conclusions and operational permissions remain decoupled.

---

## 3. Reference Catalog & Quality Standards

All 94 pinned production references are cataloged in [AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:Section 13](AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md). Every file matches its Git blob SHA-1 against historical baseline `26d5c3f`.

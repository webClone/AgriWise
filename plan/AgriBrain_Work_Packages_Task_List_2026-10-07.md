# AgriBrain Work Packages Task List & Engineering Ticket Register

**Document Revision**: 7 October 2026 (Revision 2 - Fully Reconciled)  
**Program Scope**: 52 Work Packages across 17 Stages (2,564–4,540 hours total)  
**Historical Production Baseline**: Main at `26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`  
**Schedule Authority**: [AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md](AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md)  
**Technical Specifications**: [AgriBrain_Detailed_Implementation_Plan_2026-10-07.md](AgriBrain_Detailed_Implementation_Plan_2026-10-07.md)  
**Authority Map**: [README.md](README.md)

---

## 1. Operating Guide & Ticket Lifecycle

Every ticket is actionable and reviewable. Prerequisites encode strict dataflow and boundary order.
- `ST[stage]-[pkg]-[task]`: Standard numeric full-delivery ticket.
- `ST[stage]-[pkg]-ES[task]`: Early-slice ticket for immediate cold-start unblock.
- `ST[stage]-[pkg]-FA`: Full package acceptance milestone.
- **Ticket Statuses**: `[ ] Ready` (prerequisites met), `[ ] Blocked` (waiting on upstream tickets/stages), `[-] In Progress`, `[x] Completed`.

### Master Execution Dashboard

| Stage | Packages | Focus Area | Hours Budget | Readiness Status |
|:---:|---|---|:---:|:---:|
| **Stage 00** | F37 | Core Delivery | 24–48 hrs | `[ ] Ready to Start` |
| **Stage 01** | F01, F02 | Core Delivery | 48–80 hrs | `[ ] Blocked on Stage 00 (F37)` |
| **Stage 02** | F03, F04 | Core Delivery | 36–60 hrs | `[ ] Blocked on Stage 01` |
| **Stage 03** | F06, F07, F08, F09, F39 | Core Delivery | 148–252 hrs | `[ ] Blocked on Stage 02` |
| **Stage 04** | F05, F10, F11, F12 | Core Delivery | 100–176 hrs | `[ ] Blocked on Stage 03` |
| **Stage 05** | F13, F14, F15 | Core Delivery | 68–124 hrs | `[ ] Blocked on Stage 04` |
| **Stage 06** | F16, F17, F18, F19 | Core Delivery | 88–148 hrs | `[ ] Blocked on Stage 05` |
| **Stage 07** | F20, F34 | Core Delivery | 64–104 hrs | `[ ] Blocked on Stage 06` |
| **Stage 08** | F21, F22, F23, F24 | Core Delivery | 88–144 hrs | `[ ] Blocked on Stage 07` |
| **Stage 09** | F25, F26, F27, F28, F29 | Core Delivery | 140–232 hrs | `[ ] Blocked on Stage 08` |
| **Stage 10** | F30, F31, F32, F33, F38, F40 | Core Delivery | 172–296 hrs | `[ ] Blocked on Stage 09` |
| **Stage 11** | F35, F36, T11 | Core Delivery | 168–296 hrs | `[ ] Blocked on Stage 10` |
| **Stage 12** | T01, T02, T12 | Core Delivery | 240–420 hrs | `[ ] Blocked on Stage 11` |
| **Stage 13** | T03, T06 | Core Delivery | 280–520 hrs | `[ ] Blocked on Stage 12` |
| **Stage 14** | T04, T05 | Core Delivery | 240–440 hrs | `[ ] Blocked on Stage 13` |
| **Stage 15** | T08, T09 | Core Delivery | 300–540 hrs | `[ ] Blocked on Stage 14` |
| **Stage 16** | T07, T10 | Core Delivery | 360–660 hrs | `[ ] Blocked on Stage 15` |
| **TOTAL** | **52 Packages** | **Full Remediation & Extension Program** | **2,564–4,540 hrs** | **Planned** |

---

## 2. Early-Slice Ticket Register (Immediate Cold-Start & Local Boundaries)

These tickets are executed in Stage 00 and Stage 01. Their hours are drawn from parent package allocations:

- [ ] **`ST00-F37-ES01`: [F37 Early Slice] Correct GaussianMixture import from sklearn.mixture; verify clean cold module im**
  - **Target File**: [`../services/agribrain/layer1_fusion/segmentation.py`](../services/agribrain/layer1_fusion/segmentation.py)
  - **Action**: Correct GaussianMixture import from sklearn.mixture; verify clean cold module import.
  - **Estimate**: 4–8 hours (allocated from F37) | **Prerequisites**: `none`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST00-F35-ES01`: [F35 Early Slice] Isolate optional mock_driver behind dynamic capability check; ensure simulation **
  - **Target File**: [`../services/agribrain/drone_control/dispatcher.py`](../services/agribrain/drone_control/dispatcher.py)
  - **Action**: Isolate optional mock_driver behind dynamic capability check; ensure simulation mode remains explicitly labelled.
  - **Estimate**: 4–8 hours (allocated from F35) | **Prerequisites**: `none`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST00-F38-ES01`: [F38 Early Slice] Import statistics module for Savitzky-Golay derivative spacing at line 296.**
  - **Target File**: [`../services/agribrain/layer2_veg_int/growth_engine.py`](../services/agribrain/layer2_veg_int/growth_engine.py)
  - **Action**: Import statistics module for Savitzky-Golay derivative spacing at line 296.
  - **Estimate**: 2–4 hours (allocated from F38) | **Prerequisites**: `none`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST00-F38-ES02`: [F38 Early Slice] Import IrrigationSystemType enum in CommandDispatcher device construction at lin**
  - **Target File**: [`../services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action**: Import IrrigationSystemType enum in CommandDispatcher device construction at line 272.
  - **Estimate**: 2–4 hours (allocated from F38) | **Prerequisites**: `none`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST00-F38-ES03`: [F38 Early Slice] Initialize resolution_m from scene metadata to stop discarding valid external gr**
  - **Target File**: [`../services/agribrain/layer05_asmae/geometry/external_scene_loader.py`](../services/agribrain/layer05_asmae/geometry/external_scene_loader.py)
  - **Action**: Initialize resolution_m from scene metadata to stop discarding valid external grid scenes at line 115.
  - **Estimate**: 4–8 hours (allocated from F38) | **Prerequisites**: `none`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST00-F39-ES01`: [F39 Early Slice] Reproduce concurrent nonce lost-update race; implement atomic conditional insert**
  - **Target File**: [`../services/agribrain/sensor_runtime/security.py`](../services/agribrain/sensor_runtime/security.py)
  - **Action**: Reproduce concurrent nonce lost-update race; implement atomic conditional insert with process lock.
  - **Estimate**: 6–10 hours (allocated from F39) | **Prerequisites**: `none`
  - **Verification**: Validate atomic multi-worker replay protection, nonce idempotency, finite sensor telemetry filtering, and strict hardware failure receipts.

- [ ] **`ST00-F40-ES01`: [F40 Early Slice] Resolve runtime numpy and typing annotations so get_type_hints() passes without **
  - **Target File**: [`../services/agribrain/layer0/kalman_engine.py`](../services/agribrain/layer0/kalman_engine.py)
  - **Action**: Resolve runtime numpy and typing annotations so get_type_hints() passes without NameError.
  - **Estimate**: 4–8 hours (allocated from F40) | **Prerequisites**: `ST00-F37-ES01`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST01-F32-ES01`: [F32 Early Slice] Return explicit 503 unavailable on database failure while preserving authentic z**
  - **Target File**: [`../src/app/api/dashboard/stats/route.ts`](../src/app/api/dashboard/stats/route.ts)
  - **Action**: Return explicit 503 unavailable on database failure while preserving authentic zero statistics for empty farms.
  - **Estimate**: 4–8 hours (allocated from F32) | **Prerequisites**: `none`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

---

## 3. Exhaustive Stage-by-Stage Engineering Task Checklist (Stages 00 to 16)

### Stage 00: F37 (24–48 hours)

#### Package F37: Repair optional imports and establish one Python package identity
- **Priority**: `P1` | **Budget**: `24-48 hours` | **Dependencies**: `none` | **Lane**: `Application Lane`

- [ ] **`ST00-F37-01`: 1. Import GaussianMixture from sklearn.mixture and identify actual consumers of ...**
  - **Target File**: [`../services/agribrain/layer1_fusion/segmentation.py`](../services/agribrain/layer1_fusion/segmentation.py)
  - **Action**: 1. Import GaussianMixture from sklearn.mixture and identify actual consumers of the legacy segmentation module.
  - **Estimate**: 6–12 hours | **Prerequisites**: `none`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST00-F37-02`: 2. Isolate optional drivers and model backends behind explicit capability loadin...**
  - **Target File**: [`../services/agribrain/layer1_fusion/engine.py`](../services/agribrain/layer1_fusion/engine.py)
  - **Action**: 2. Isolate optional drivers and model backends behind explicit capability loading, retaining simulation as a qualified mode.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST00-F37-01`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST00-F37-03`: 3. Select one installed package namespace and migrate entrypoints/imports cohere...**
  - **Target File**: [`../services/agribrain/drone_control/dispatcher.py`](../services/agribrain/drone_control/dispatcher.py)
  - **Action**: 3. Select one installed package namespace and migrate entrypoints/imports coherently instead of mechanically prefixing every import.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST00-F37-02`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST00-F37-04`: 4. Verify service, worker, CLI and public module startup in fresh processes with...**
  - **Target File**: [`../services/agribrain/drone_mission/__init__.py`](../services/agribrain/drone_mission/__init__.py)
  - **Action**: 4. Verify service, worker, CLI and public module startup in fresh processes with declared dependency extras.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST00-F37-03`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST00-F37-FA`: Package F37 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (6 files) | **Prerequisites**: `ST00-F37-01 through ST00-F37-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Cold imports work for each supported entrypoint without incidental prior imports.*
    - *Qualified and internal callers share enum/dataclass identities.*
    - *An unavailable optional backend disables its capability without breaking unrelated science.*
    - *The two successfully loaded cycles are not treated as demonstrated circular-import failures.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 01: F01, F02 (48–80 hours)

#### Package F01: Qualify provenance and numeric evidence at every admission boundary
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `none` | **Lane**: `Evidence Lane`

- [ ] **`ST01-F01-01`: 1. Review PR #1 against source consumers and preserve its corrected zero and mis...**
  - **Target File**: [`../services/agribrain/layer0/observation_packet.py`](../services/agribrain/layer0/observation_packet.py)
  - **Action**: 1. Review PR #1 against source consumers and preserve its corrected zero and missingness semantics.
  - **Estimate**: 6–10 hours | **Prerequisites**: `none`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST01-F01-02`: 2. Make accepted/rejected components explicit before authority or solver selecti...**
  - **Target File**: [`../services/agribrain/layer0/wrappers.py`](../services/agribrain/layer0/wrappers.py)
  - **Action**: 2. Make accepted/rejected components explicit before authority or solver selection.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST01-F01-01`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST01-F01-03`: 3. Carry source roles through all typed and dictionary adapters without allowing...**
  - **Target File**: [`../services/agribrain/scientific_contracts/observation.py`](../services/agribrain/scientific_contracts/observation.py)
  - **Action**: 3. Carry source roles through all typed and dictionary adapters without allowing caller promotion.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST01-F01-02`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST01-F01-04`: 4. Apply the same qualification to weather, RF, crop observations and training a...**
  - **Target File**: [`../services/agribrain/layer3_water/assimilation/water_state_assimilator.py`](../services/agribrain/layer3_water/assimilation/water_state_assimilator.py)
  - **Action**: 4. Apply the same qualification to weather, RF, crop observations and training admission, with migration of ambiguous legacy records.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST01-F01-03`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST01-F01-FA`: Package F01 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files) | **Prerequisites**: `ST01-F01-01 through ST01-F01-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *NaN, infinity, booleans and malformed numeric values cannot alter state or training weight.*
    - *Legitimate zero survives serialization and round trips.*
    - *Authority and accepted counts follow actual admitted components.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F02: Enforce observation time and availability at issuance
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F01` | **Lane**: `Evidence Lane`

- [ ] **`ST01-F02-01`: 1. Retain the PR explicit-cutoff fix and require both observation and availabili...**
  - **Target File**: [`../services/agribrain/layer05_asmae/resilient_posterior.py`](../services/agribrain/layer05_asmae/resilient_posterior.py)
  - **Action**: 1. Retain the PR explicit-cutoff fix and require both observation and availability provenance for prospective measurements.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F01`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST01-F02-02`: 2. Define typed timing for measurements, priors, forecasts and management scenar...**
  - **Target File**: [`../services/agribrain/layer0/temporal_evidence.py`](../services/agribrain/layer0/temporal_evidence.py)
  - **Action**: 2. Define typed timing for measurements, priors, forecasts and management scenarios.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST01-F02-01`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST01-F02-03`: 3. Propagate the decision cutoff through each layer and reject records with unre...**
  - **Target File**: [`../services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)
  - **Action**: 3. Propagate the decision cutoff through each layer and reject records with unresolved eligibility.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST01-F02-02`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST01-F02-04`: 4. Record every excluded revision and force historical replays to use the archiv...**
  - **Target File**: [`../services/agribrain/layer05_asmae/resilient_posterior.py`](../services/agribrain/layer05_asmae/resilient_posterior.py)
  - **Action**: 4. Record every excluded revision and force historical replays to use the archived knowledge view.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST01-F02-03`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST01-F02-FA`: Package F02 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST01-F02-01 through ST01-F02-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Late-arriving measurements and revised weather are excluded from earlier issuance.*
    - *Earlier-issued future forecasts remain eligible as scenarios.*
    - *Replay identifies exactly which input versions were available.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 02: F03, F04 (36–60 hours)

#### Package F03: Publish the fluxes actually integrated and separate analysis increments
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F01` | **Lane**: `Trajectory Lane`

- [ ] **`ST02-F03-01`: 1. Return a transition receipt containing bounded actual evaporation, transpirat...**
  - **Target File**: [`../services/agribrain/layer3_water/runner.py`](../services/agribrain/layer3_water/runner.py)
  - **Action**: 1. Return a transition receipt containing bounded actual evaporation, transpiration, drainage, infiltration and initial/final storage.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST02-F03-02`: 2. Publish that receipt as realized interval flux and expose posterior demand as...**
  - **Target File**: [`../services/agribrain/layer3_water/soil/layered_water_balance.py`](../services/agribrain/layer3_water/soil/layered_water_balance.py)
  - **Action**: 2. Publish that receipt as realized interval flux and expose posterior demand as a separate next-interval diagnostic.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST02-F03-01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST02-F03-03`: 3. Return an analysis receipt with storage increment, covariance change and boun...**
  - **Target File**: [`../services/agribrain/layer3_water/contracts/water_state.py`](../services/agribrain/layer3_water/contracts/water_state.py)
  - **Action**: 3. Return an analysis receipt with storage increment, covariance change and bound corrections.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST02-F03-02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST02-F03-04`: 4. Calculate closure from the serialized state and receipt rather than an intern...**
  - **Target File**: [`../services/agribrain/layer3_water/runner.py`](../services/agribrain/layer3_water/runner.py)
  - **Action**: 4. Calculate closure from the serialized state and receipt rather than an internal pre-rounding ledger.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST02-F03-03`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST02-F03-FA`: Package F03 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST02-F03-01 through ST02-F03-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Integrated and published realized fluxes agree.*
    - *Physical closure includes bounded extraction and quantization, while analysis increments are explicit.*
    - *Assimilation cannot retroactively rewrite the water used in the preceding interval.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F04: Validate soil geometry and hydraulic parameter vectors
- **Priority**: `P0` | **Budget**: `12-20 hours` | **Dependencies**: `F01` | **Lane**: `Trajectory Lane`

- [ ] **`ST02-F04-01`: 1. Require a nonempty strictly increasing finite positive depth vector....**
  - **Target File**: [`../services/agribrain/layer3_water/contracts/state_factory.py`](../services/agribrain/layer3_water/contracts/state_factory.py)
  - **Action**: 1. Require a nonempty strictly increasing finite positive depth vector.
  - **Estimate**: 3–5 hours | **Prerequisites**: `F01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST02-F04-02`: 2. Validate the length and physical domain of every retention, conductivity and ...**
  - **Target File**: [`../services/agribrain/layer3_water/soil/layered_water_balance.py`](../services/agribrain/layer3_water/soil/layered_water_balance.py)
  - **Action**: 2. Validate the length and physical domain of every retention, conductivity and van Genuchten vector.
  - **Estimate**: 3–5 hours | **Prerequisites**: `ST02-F04-01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST02-F04-03`: 3. Reject degenerate saturation/residual intervals and inconsistent units before...**
  - **Target File**: [`../services/agribrain/layer3_water/contracts/state_factory.py`](../services/agribrain/layer3_water/contracts/state_factory.py)
  - **Action**: 3. Reject degenerate saturation/residual intervals and inconsistent units before computing suction.
  - **Estimate**: 3–5 hours | **Prerequisites**: `ST02-F04-02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST02-F04-04`: 4. Document parameter provenance and distinguish measured values from texture pr...**
  - **Target File**: [`../services/agribrain/layer3_water/soil/layered_water_balance.py`](../services/agribrain/layer3_water/soil/layered_water_balance.py)
  - **Action**: 4. Document parameter provenance and distinguish measured values from texture priors.
  - **Estimate**: 3–5 hours | **Prerequisites**: `ST02-F04-03`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST02-F04-FA`: Package F04 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST02-F04-01 through ST02-F04-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Nonmonotonic, repeated, zero or nonfinite depths are rejected.*
    - *Negative conductivity and invalid n or alpha cannot enter the solver.*
    - *Valid heterogeneous profiles retain their parameters and storage.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 03: F06, F07, F08, F09, F39 (148–252 hours)

#### Package F06: Stop substituting another date at the weather endpoint
- **Priority**: `P0` | **Budget**: `12-20 hours` | **Dependencies**: `F02` | **Lane**: `Trajectory Lane`

- [ ] **`ST03-F06-01`: 1. Remove arbitrary-record selection at the endpoint....**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 1. Remove arbitrary-record selection at the endpoint.
  - **Estimate**: 3–5 hours | **Prerequisites**: `F02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F06-02`: 2. Resolve forcing by exact interval and declared timezone....**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 2. Resolve forcing by exact interval and declared timezone.
  - **Estimate**: 3–5 hours | **Prerequisites**: `ST03-F06-01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F06-03`: 3. Route missing target forcing through an explicit prior or missing-data result...**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 3. Route missing target forcing through an explicit prior or missing-data result with uncertainty and source role.
  - **Estimate**: 3–5 hours | **Prerequisites**: `ST03-F06-02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F06-04`: 4. Apply the same policy to intermediate gaps and keep zero rainfall distinct fr...**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 4. Apply the same policy to intermediate gaps and keep zero rainfall distinct from unobserved rainfall.
  - **Estimate**: 3–5 hours | **Prerequisites**: `ST03-F06-03`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F06-FA`: Package F06 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files) | **Prerequisites**: `ST03-F06-01 through ST03-F06-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *No future record supplies a historical daily forcing.*
    - *Missing rainfall is visible and cannot become observed zero.*
    - *Daily and sparse executions use identical qualified interval inputs.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F07: Remove future canopy fallback and restore evaporation memory
- **Priority**: `P1` | **Budget**: `24-40 hours` | **Dependencies**: `F03, F04, F06` | **Lane**: `Trajectory Lane`

- [ ] **`ST03-F07-01`: 1. Resolve historical canopy only from records eligible for each step and label ...**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 1. Resolve historical canopy only from records eligible for each step and label persisted priors.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F03, F04, F06`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F07-02`: 2. Remove endpoint canopy fallback into earlier days unless it is explicitly a s...**
  - **Target File**: [`../services/agribrain/layer3_water/runner.py`](../services/agribrain/layer3_water/runner.py)
  - **Action**: 2. Remove endpoint canopy fallback into earlier days unless it is explicitly a scenario reconstruction.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST03-F07-01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F07-03`: 3. Restore the previous evaporation state and wetted fraction into each step....**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 3. Restore the previous evaporation state and wetted fraction into each step.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST03-F07-02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F07-04`: 4. Derive surface storage from actual layer thickness and propagate method-speci...**
  - **Target File**: [`../services/agribrain/layer3_water/runner.py`](../services/agribrain/layer3_water/runner.py)
  - **Action**: 4. Derive surface storage from actual layer thickness and propagate method-specific wetting.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST03-F07-03`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F07-FA`: Package F07 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST03-F07-01 through ST03-F07-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Earlier steps never consume later observed canopy.*
    - *A dry sequence advances evaporation memory across restart and sparse replay.*
    - *Changing top-layer thickness changes surface storage consistently.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F08: Make trajectory invalidation include parameters and predecessor content
- **Priority**: `P1` | **Budget**: `24-40 hours` | **Dependencies**: `F03, F04, F06` | **Lane**: `Trajectory Lane`

- [ ] **`ST03-F08-01`: 1. Replace repr and rounded scalar fingerprints with canonical content digests....**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 1. Replace repr and rounded scalar fingerprints with canonical content digests.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F03, F04, F06`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F08-02`: 2. Include full profile, crop/geometry epoch, solver version, observation payloa...**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 2. Include full profile, crop/geometry epoch, solver version, observation payload and predecessor digest.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST03-F08-01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F08-03`: 3. Invalidate from the earliest changed transition for parameter corrections as ...**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 3. Invalidate from the earliest changed transition for parameter corrections as well as weather changes.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST03-F08-02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F08-04`: 4. Preserve previously issued forecasts while creating a separate corrected retr...**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 4. Preserve previously issued forecasts while creating a separate corrected retrospective trajectory.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST03-F08-03`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F08-FA`: Package F08 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files) | **Prerequisites**: `ST03-F08-01 through ST03-F08-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Identical moisture with different conductivity or retention cannot share a trajectory key.*
    - *Parameter changes recompute affected predecessors and descendants.*
    - *Repeated identical requests are idempotent.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F09: Persist coupled state with scoped concurrency and restart recovery
- **Priority**: `P1` | **Budget**: `48-80 hours` | **Dependencies**: `F02, F03, F08` | **Lane**: `Trajectory Lane`

- [ ] **`ST03-F09-01`: 1. Move parameter epochs, action versions and hydraulic checkpoints to the canon...**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 1. Move parameter epochs, action versions and hydraulic checkpoints to the canonical scoped store.
  - **Estimate**: 12–20 hours | **Prerequisites**: `F02, F03, F08`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F09-02`: 2. Use tenant, plot, cycle, geometry and namespace in identities....**
  - **Target File**: [`../services/agribrain/world_model/canonical_worldline.py`](../services/agribrain/world_model/canonical_worldline.py)
  - **Action**: 2. Use tenant, plot, cycle, geometry and namespace in identities.
  - **Estimate**: 12–20 hours | **Prerequisites**: `ST03-F09-01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F09-03`: 3. Commit transition and analysis receipts with compare-and-swap on the predeces...**
  - **Target File**: [`../services/agribrain/layer05_asmae/history/worldline_service.py`](../services/agribrain/layer05_asmae/history/worldline_service.py)
  - **Action**: 3. Commit transition and analysis receipts with compare-and-swap on the predecessor head.
  - **Estimate**: 12–20 hours | **Prerequisites**: `ST03-F09-02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F09-04`: 4. Recover from committed checkpoints and replay appended corrections under a fe...**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 4. Recover from committed checkpoints and replay appended corrections under a fenced lease.
  - **Estimate**: 12–20 hours | **Prerequisites**: `ST03-F09-03`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F09-FA`: Package F09 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST03-F09-01 through ST03-F09-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Cold restart equals warm replay.*
    - *Two workers cannot publish different successors for one head.*
    - *Cancellation, withdrawal and late correction survive restart and replica changes.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F39: Make telemetry persistence and replay protection concurrency safe
- **Priority**: `P0` | **Budget**: `40-72 hours` | **Dependencies**: `F01, F09` | **Lane**: `Trajectory Lane`

- [ ] **`ST03-F39-01`: 1. Combine nonce eligibility and registration in a shared atomic conditional ins...**
  - **Target File**: [`../services/agribrain/sensor_runtime/security.py`](../services/agribrain/sensor_runtime/security.py)
  - **Action**: 1. Combine nonce eligibility and registration in a shared atomic conditional insert with scoped unique keys and retention derived from the accepted replay window.
  - **Estimate**: 6–12 hours | **Prerequisites**: `F01, F09`
  - **Verification**: Validate atomic multi-worker replay protection, nonce idempotency, finite sensor telemetry filtering, and strict hardware failure receipts.

- [ ] **`ST03-F39-02`: 2. Persist immutable raw/normalized telemetry durably with message idempotency b...**
  - **Target File**: [`../services/agribrain/sensor_runtime/storage.py`](../services/agribrain/sensor_runtime/storage.py)
  - **Action**: 2. Persist immutable raw/normalized telemetry durably with message idempotency before making it visible.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST03-F39-01`
  - **Verification**: Validate atomic multi-worker replay protection, nonce idempotency, finite sensor telemetry filtering, and strict hardware failure receipts.

- [ ] **`ST03-F39-03`: 3. Keep memory caches bounded by byte/cardinality budgets and expose retention/e...**
  - **Target File**: [`../services/agribrain/app/main.py`](../services/agribrain/app/main.py)
  - **Action**: 3. Keep memory caches bounded by byte/cardinality budgets and expose retention/eviction metrics.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST03-F39-02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F39-04`: Implement bounded plot-lock lifecycle (_plot_cache_locks, _plot_cache_locks_lock...**
  - **Target File**: [`../services/agribrain/app/main.py`](../services/agribrain/app/main.py)
  - **Action**: Implement bounded plot-lock lifecycle (_plot_cache_locks, _plot_cache_locks_lock) at lines 3803–3830 without losing mutual exclusion.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST03-F39-03`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F39-05`: 5. Bound rate-limiter identity retention without permitting an eviction/reset by...**
  - **Target File**: [`../services/agribrain/sensor_runtime/security.py`](../services/agribrain/sensor_runtime/security.py)
  - **Action**: 5. Bound rate-limiter identity retention without permitting an eviction/reset bypass across replicas.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST03-F39-04`
  - **Verification**: Validate atomic multi-worker replay protection, nonce idempotency, finite sensor telemetry filtering, and strict hardware failure receipts.

- [ ] **`ST03-F39-06`: Scope and invalidate bounding-box cache (_plot_bbox_cache) at lines 66–71 with L...**
  - **Target File**: [`../services/agribrain/visual_sources/tile_proxy.py`](../services/agribrain/visual_sources/tile_proxy.py)
  - **Action**: Scope and invalidate bounding-box cache (_plot_bbox_cache) at lines 66–71 with LRU cardinality bounds.
  - **Estimate**: 10–12 hours | **Prerequisites**: `ST03-F39-05`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST03-F39-FA`: Package F39 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files) | **Prerequisites**: `ST03-F39-01 through ST03-F39-06`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Two simultaneous unique nonces remain registered and the same nonce is accepted at most once.*
    - *Replay rejection survives restart and concurrent replicas.*
    - *Cache pressure does not erase the durable evidence corpus.*
    - *High-cardinality keys stay within declared budgets without duplicating locks for one active key.*
    - *Geometry corrections cannot reuse an old plot bounding box.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 04: F05, F10, F11, F12 (100–176 hours)

#### Package F05: Use depth-aware soil observations and carry covariance
- **Priority**: `P1` | **Budget**: `32-56 hours` | **Dependencies**: `F01, F04` | **Lane**: `Trajectory Lane`

- [ ] **`ST04-F05-01`: 1. Represent individual readings with depth interval, location, time, instrument...**
  - **Target File**: [`../services/agribrain/layer3_water/contracts/assimilation_state.py`](../services/agribrain/layer3_water/contracts/assimilation_state.py)
  - **Action**: 1. Represent individual readings with depth interval, location, time, instrument and noise.
  - **Estimate**: 8–14 hours | **Prerequisites**: `F01, F04`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F05-02`: 2. Construct the vertical observation operator from overlap or point support ins...**
  - **Target File**: [`../services/agribrain/layer3_water/assimilation/water_state_assimilator.py`](../services/agribrain/layer3_water/assimilation/water_state_assimilator.py)
  - **Action**: 2. Construct the vertical observation operator from overlap or point support instead of list index.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST04-F05-01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F05-03`: 3. Preserve correlated posterior uncertainty by layer and carry unsupported-dept...**
  - **Target File**: [`../services/agribrain/layer3_water/root_zone/availability.py`](../services/agribrain/layer3_water/root_zone/availability.py)
  - **Action**: 3. Preserve correlated posterior uncertainty by layer and carry unsupported-depth flags to L4 and decisions.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST04-F05-02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F05-04`: 4. Treat thermal and RF surrogates as calibrated conditional constraints with th...**
  - **Target File**: [`../services/agribrain/layer3_water/contracts/assimilation_state.py`](../services/agribrain/layer3_water/contracts/assimilation_state.py)
  - **Action**: 4. Treat thermal and RF surrogates as calibrated conditional constraints with their own support.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST04-F05-03`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F05-FA`: Package F05 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST04-F05-01 through ST04-F05-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Reordered input readings yield the same update.*
    - *A shallow reading cannot claim direct full root-zone observation.*
    - *Depth mismatch and absent support produce a qualified partial result.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F10: Repair the L3-to-L4 water boundary
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F03, F04, F05` | **Lane**: `Trajectory Lane`

- [ ] **`ST04-F10-01`: 1. Consume a typed depth-aware Layer3ToLayer4BoundaryReceipt....**
  - **Target File**: [`../services/agribrain/layer4_nutrients/runner.py`](../services/agribrain/layer4_nutrients/runner.py)
  - **Action**: 1. Consume a typed depth-aware Layer3ToLayer4BoundaryReceipt.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F03, F04, F05`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F10-02`: 2. Integrate storage and retention over the defined root support instead of repl...**
  - **Target File**: [`../services/agribrain/layer3_water/contracts/water_state.py`](../services/agribrain/layer3_water/contracts/water_state.py)
  - **Action**: 2. Integrate storage and retention over the defined root support instead of replacing them with generic scalars.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST04-F10-01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F10-03`: 3. Keep daily drainage flux separate from seasonal accumulated drainage....**
  - **Target File**: [`../services/agribrain/layer3_water/contracts/assimilation_state.py`](../services/agribrain/layer3_water/contracts/assimilation_state.py)
  - **Action**: 3. Keep daily drainage flux separate from seasonal accumulated drainage.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST04-F10-02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F10-04`: 4. Carry missing support and uncertainty into nutrient, salinity and leaching ca...**
  - **Target File**: [`../services/agribrain/layer4_nutrients/runner.py`](../services/agribrain/layer4_nutrients/runner.py)
  - **Action**: 4. Carry missing support and uncertainty into nutrient, salinity and leaching calculations.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST04-F10-03`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F10-FA`: Package F10 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST04-F10-01 through ST04-F10-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *A non-loam profile reaches L4 without generic substitution.*
    - *Root-zone storage matches the same depth integration as L3.*
    - *One daily drainage receipt is counted once in cumulative nutrient transport.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F11: Correct residual nitrogen demand and expose conservative pools
- **Priority**: `P0` | **Budget**: `24-48 hours` | **Dependencies**: `F10` | **Lane**: `Trajectory Lane`

- [ ] **`ST04-F11-01`: 1. Remove the second subtraction under the existing residual-demand convention....**
  - **Target File**: [`../services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py`](../services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py)
  - **Action**: 1. Remove the second subtraction under the existing residual-demand convention.
  - **Estimate**: 6–12 hours | **Prerequisites**: `F10`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F11-02`: 2. Define whether each quantity is cumulative applied, available soil, recovered...**
  - **Target File**: [`../services/agribrain/layer4_nutrients/runner.py`](../services/agribrain/layer4_nutrients/runner.py)
  - **Action**: 2. Define whether each quantity is cumulative applied, available soil, recovered plant N or additional dose.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST04-F11-01`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F11-03`: 3. Replace independent cumulative heuristics with conservative mineralization, u...**
  - **Target File**: [`../services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py`](../services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py)
  - **Action**: 3. Replace independent cumulative heuristics with conservative mineralization, uptake, loss and application pools.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST04-F11-02`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F11-04`: 4. Carry dose timing, formulation and recovery uncertainty into recommendations....**
  - **Target File**: [`../services/agribrain/layer4_nutrients/runner.py`](../services/agribrain/layer4_nutrients/runner.py)
  - **Action**: 4. Carry dose timing, formulation and recovery uncertainty into recommendations.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST04-F11-03`
  - **Verification**: Validate physical mass conservation ($S_- - S_{prev} = \text{Infil} + \text{Rise} - \text{Evap} - \text{Transp} - \text{Drain}$), strictly increasing depth increments ($\Delta z_i > 0$), exact dated weather matching, and atomic multi-worker replay protection.

- [ ] **`ST04-F11-FA`: Package F11 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST04-F11-01 through ST04-F11-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *The controlled residual case returns 86.67 under its declared assumptions.*
    - *Zero deficit produces zero additional demand.*
    - *Nitrogen stock changes reconcile uptake, losses and applied mass.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F12: Separate exposure verification from causal attribution
- **Priority**: `P0` | **Budget**: `20-32 hours` | **Dependencies**: `F02` | **Lane**: `Execution Lane`

- [ ] **`ST04-F12-01`: 1. Keep delivered exposure as a separate qualification field....**
  - **Target File**: [`../services/agribrain/layer6_exec/outcomes/metrics.py`](../services/agribrain/layer6_exec/outcomes/metrics.py)
  - **Action**: 1. Keep delivered exposure as a separate qualification field.
  - **Estimate**: 5–8 hours | **Prerequisites**: `F02`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict separation of exposure verification from causal attribution.

- [ ] **`ST04-F12-02`: 2. Label uncontrolled pre/post metrics as observed associations even after verif...**
  - **Target File**: [`../services/agribrain/layer6_exec/outcomes/metrics.py`](../services/agribrain/layer6_exec/outcomes/metrics.py)
  - **Action**: 2. Label uncontrolled pre/post metrics as observed associations even after verified execution.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST04-F12-01`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict separation of exposure verification from causal attribution.

- [ ] **`ST04-F12-03`: 3. Require an explicit identification record before estimating or labelling caus...**
  - **Target File**: [`../services/agribrain/layer6_exec/outcomes/metrics.py`](../services/agribrain/layer6_exec/outcomes/metrics.py)
  - **Action**: 3. Require an explicit identification record before estimating or labelling causal effect.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST04-F12-02`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict separation of exposure verification from causal attribution.

- [ ] **`ST04-F12-04`: 4. Integrate by real timestamps, preserve valid zero indices and record missing ...**
  - **Target File**: [`../services/agribrain/layer6_exec/outcomes/metrics.py`](../services/agribrain/layer6_exec/outcomes/metrics.py)
  - **Action**: 4. Integrate by real timestamps, preserve valid zero indices and record missing confounder data.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST04-F12-03`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict separation of exposure verification from causal attribution.

- [ ] **`ST04-F12-FA`: Package F12 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files) | **Prerequisites**: `ST04-F12-01 through ST04-F12-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Verified exposure alone never grants causal effect.*
    - *Unequal sampling intervals do not masquerade as NDVI-time integral changes.*
    - *Negative results and unknown confounding remain in the outcome record.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 05: F13, F14, F15 (68–124 hours)

#### Package F13: Correct yield quantiles and distinguish calibrated distributions from heuristics
- **Priority**: `P1` | **Budget**: `24-48 hours` | **Dependencies**: `F02, F12` | **Lane**: `Learning Lane`

- [ ] **`ST05-F13-01`: 1. Use one distribution contract with quantile levels and support....**
  - **Target File**: [`../services/agribrain/layer6_yield/yield_forecast.py`](../services/agribrain/layer6_yield/yield_forecast.py)
  - **Action**: 1. Use one distribution contract with quantile levels and support.
  - **Estimate**: 6–12 hours | **Prerequisites**: `F02, F12`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST05-F13-02`: 2. Correct normal P10/P90 to +/-1.2815516 sigma when a Gaussian assumption is ac...**
  - **Target File**: [`../services/agribrain/layer7_planning/engines/yve_yield_distribution.py`](../services/agribrain/layer7_planning/engines/yve_yield_distribution.py)
  - **Action**: 2. Correct normal P10/P90 to +/-1.2815516 sigma when a Gaussian assumption is actually intended.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST05-F13-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST05-F13-03`: 3. Label L7 deterministic penalty bands as heuristic until fitted and calibrated...**
  - **Target File**: [`../services/agribrain/layer7_planning/schema.py`](../services/agribrain/layer7_planning/schema.py)
  - **Action**: 3. Label L7 deterministic penalty bands as heuristic until fitted and calibrated.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST05-F13-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST05-F13-04`: 4. Share joint yield, quality and economic samples across L6/L7/L8 instead of tr...**
  - **Target File**: [`../services/agribrain/layer6_yield/yield_forecast.py`](../services/agribrain/layer6_yield/yield_forecast.py)
  - **Action**: 4. Share joint yield, quality and economic samples across L6/L7/L8 instead of treating their numbers as interchangeable.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST05-F13-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST05-F13-FA`: Package F13 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST05-F13-01 through ST05-F13-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Quantile labels match their mathematical levels.*
    - *Mean and median are distinct when the distribution is skewed.*
    - *Mixture tails are derived from the mixture distribution and prospective coverage is reported.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F14: Repair L7-to-L8 crop scenario mapping
- **Priority**: `P0` | **Budget**: `12-20 hours` | **Dependencies**: `F13` | **Lane**: `Target Capability Lane`

- [ ] **`ST05-F14-01`: 1. Map the actual typed L7 contract explicitly....**
  - **Target File**: [`../services/agribrain/layer7_planning/schema.py`](../services/agribrain/layer7_planning/schema.py)
  - **Action**: 1. Map the actual typed L7 contract explicitly.
  - **Estimate**: 3–5 hours | **Prerequisites**: `F13`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST05-F14-02`: 2. Preserve stable option ID, crop, yield distribution, economics and units....**
  - **Target File**: [`../services/agribrain/layer8_prescriptive/scenario_contract.py`](../services/agribrain/layer8_prescriptive/scenario_contract.py)
  - **Action**: 2. Preserve stable option ID, crop, yield distribution, economics and units.
  - **Estimate**: 3–5 hours | **Prerequisites**: `ST05-F14-01`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST05-F14-03`: 3. Reject a schema mismatch instead of falling back to unknown and unitless 1.0....**
  - **Target File**: [`../services/agribrain/layer8_prescriptive/runner.py`](../services/agribrain/layer8_prescriptive/runner.py)
  - **Action**: 3. Reject a schema mismatch instead of falling back to unknown and unitless 1.0.
  - **Estimate**: 3–5 hours | **Prerequisites**: `ST05-F14-02`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST05-F14-04`: 4. Carry scenario provenance and compare operational interventions separately fr...**
  - **Target File**: [`../services/agribrain/layer7_planning/schema.py`](../services/agribrain/layer7_planning/schema.py)
  - **Action**: 4. Carry scenario provenance and compare operational interventions separately from seasonal crop choices.
  - **Estimate**: 3–5 hours | **Prerequisites**: `ST05-F14-03`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST05-F14-FA`: Package F14 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST05-F14-01 through ST05-F14-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Actual CropOptionEvaluation preserves crop and distribution.*
    - *Profit can never fill a yield field.*
    - *Missing required option data produces a qualified unavailable scenario.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F15: Unify weather constraints and final hard action limits
- **Priority**: `P0` | **Budget**: `32-56 hours` | **Dependencies**: `F01, F06, F14` | **Lane**: `Execution Lane`

- [ ] **`ST05-F15-01`: 1. Normalize weather units, valid intervals and quality before every action cons...**
  - **Target File**: [`../services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py`](../services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py)
  - **Action**: 1. Normalize weather units, valid intervals and quality before every action constraint.
  - **Estimate**: 8–14 hours | **Prerequisites**: `F01, F06, F14`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST05-F15-02`: 2. Treat absent mandatory safety variables as unqualified, with a clear measurem...**
  - **Target File**: [`../services/agribrain/layer8_prescriptive/engines/salinity_leaching.py`](../services/agribrain/layer8_prescriptive/engines/salinity_leaching.py)
  - **Action**: 2. Treat absent mandatory safety variables as unqualified, with a clear measurement or confirmation requirement.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST05-F15-01`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST05-F15-03`: 3. Preserve immutable hard constraints and never increase their ceiling during a...**
  - **Target File**: [`../services/agribrain/layer8_prescriptive/scheduler.py`](../services/agribrain/layer8_prescriptive/scheduler.py)
  - **Action**: 3. Preserve immutable hard constraints and never increase their ceiling during agronomic adjustments.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST05-F15-02`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST05-F15-04`: 4. Apply one final feasibility pass after all rate modifiers, zone aggregation a...**
  - **Target File**: [`../services/agribrain/layer8_prescriptive/runner.py`](../services/agribrain/layer8_prescriptive/runner.py)
  - **Action**: 4. Apply one final feasibility pass after all rate modifiers, zone aggregation and scheduling, including dated legal/resource constraints.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST05-F15-03`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST05-F15-FA`: Package F15 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files) | **Prerequisites**: `ST05-F15-01 through ST05-F15-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Missing or invalid wind cannot yield a confirmed spray.*
    - *Every final dose stays within the original hard cap and budget.*
    - *Reordering dated forecast rows does not change the chosen valid slot.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 06: F16, F17, F18, F19 (88–148 hours)

#### Package F16: Enforce quota and watchdog independently of telemetry
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F01` | **Lane**: `Execution Lane`

- [ ] **`ST06-F16-01`: 1. Always check water budgets before command submission....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action**: 1. Always check water budgets before command submission.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F01`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F16-02`: 2. Run duration watchdogs on an independent monotonic timer....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/safety.py`](../services/agribrain/irrigation_runtime/safety.py)
  - **Action**: 2. Run duration watchdogs on an independent monotonic timer.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST06-F16-01`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F16-03`: 3. Define critical sensor freshness and missingness policies explicitly....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action**: 3. Define critical sensor freshness and missingness policies explicitly.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST06-F16-02`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F16-04`: 4. Persist reservation and delivered-water reconciliation so concurrent commands...**
  - **Target File**: [`../services/agribrain/irrigation_runtime/safety.py`](../services/agribrain/irrigation_runtime/safety.py)
  - **Action**: 4. Persist reservation and delivered-water reconciliation so concurrent commands cannot overspend quota.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST06-F16-03`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F16-FA`: Package F16 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST06-F16-01 through ST06-F16-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Zero remaining budget produces zero physical start calls with None, empty or present telemetry.*
    - *Duration expiration stops a running event without new sensor messages.*
    - *Two reservations cannot jointly exceed the remaining budget.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F17: Keep actuator operation state until physical completion
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F16` | **Lane**: `Execution Lane`

- [ ] **`ST06-F17-01`: 1. Separate command transport acknowledgement from operation completion....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/actuator.py`](../services/agribrain/irrigation_runtime/actuator.py)
  - **Action**: 1. Separate command transport acknowledgement from operation completion.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F16`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F17-02`: 2. Retain operation ownership, target flow and active event until verified stop/...**
  - **Target File**: [`../services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action**: 2. Retain operation ownership, target flow and active event until verified stop/completion.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST06-F17-01`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F17-03`: 3. Allow stop and emergency stop through busy-state checks....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/actuator.py`](../services/agribrain/irrigation_runtime/actuator.py)
  - **Action**: 3. Allow stop and emergency stop through busy-state checks.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST06-F17-02`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F17-04`: 4. Reconcile controller telemetry against the persistent operation rather than t...**
  - **Target File**: [`../services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action**: 4. Reconcile controller telemetry against the persistent operation rather than transport status.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST06-F17-03`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F17-FA`: Package F17 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST06-F17-01 through ST06-F17-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Second conflicting start is rejected while physical execution continues.*
    - *Dynamic flow checks retain the target command.*
    - *Normal stop remains admissible during execution and is recorded once.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F18: Reconcile ambiguous command failures before retry
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F17` | **Lane**: `Execution Lane`

- [ ] **`ST06-F18-01`: 1. Give retries the same operation identity and attempt sequence....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/actuator.py`](../services/agribrain/irrigation_runtime/actuator.py)
  - **Action**: 1. Give retries the same operation identity and attempt sequence.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F17`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F18-02`: 2. Query controller state after timeout to distinguish applied, not applied and ...**
  - **Target File**: [`../services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action**: 2. Query controller state after timeout to distinguish applied, not applied and unknown.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST06-F18-01`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F18-03`: 3. Permit only safe idempotent retries and retain ownership during uncertainty....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/actuator.py`](../services/agribrain/irrigation_runtime/actuator.py)
  - **Action**: 3. Permit only safe idempotent retries and retain ownership during uncertainty.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST06-F18-02`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F18-04`: 4. Restore event and controller reconciliation on process restart....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action**: 4. Restore event and controller reconciliation on process restart.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST06-F18-03`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F18-FA`: Package F18 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST06-F18-01 through ST06-F18-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *A retry never duplicates a delivered dose.*
    - *An acknowledgement timeout does not automatically mean no physical application.*
    - *Own-operation retry is not rejected as an unrelated competing command.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F19: Implement interlock persistence, debounce and stable violation keys
- **Priority**: `P1` | **Budget**: `16-28 hours` | **Dependencies**: `F16, F17` | **Lane**: `Execution Lane`

- [ ] **`ST06-F19-01`: 1. Track first breach, duration, recovery and freshness using monotonic time....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/safety.py`](../services/agribrain/irrigation_runtime/safety.py)
  - **Action**: 1. Track first breach, duration, recovery and freshness using monotonic time.
  - **Estimate**: 4–7 hours | **Prerequisites**: `F16, F17`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F19-02`: 2. Index active violation state by device and interlock while preserving unique ...**
  - **Target File**: [`../services/agribrain/irrigation_runtime/actuator.py`](../services/agribrain/irrigation_runtime/actuator.py)
  - **Action**: 2. Index active violation state by device and interlock while preserving unique event records.
  - **Estimate**: 4–7 hours | **Prerequisites**: `ST06-F19-01`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F19-03`: 3. Implement the declared manual/automatic reset rules....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/safety.py`](../services/agribrain/irrigation_runtime/safety.py)
  - **Action**: 3. Implement the declared manual/automatic reset rules.
  - **Estimate**: 4–7 hours | **Prerequisites**: `ST06-F19-02`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F19-04`: 4. Make stop actions idempotent and rehydrate active protections after restart....**
  - **Target File**: [`../services/agribrain/irrigation_runtime/actuator.py`](../services/agribrain/irrigation_runtime/actuator.py)
  - **Action**: 4. Make stop actions idempotent and rehydrate active protections after restart.
  - **Estimate**: 4–7 hours | **Prerequisites**: `ST06-F19-03`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST06-F19-FA`: Package F19 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST06-F19-01 through ST06-F19-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Configured debounce is honored with fake-clock probes.*
    - *A sustained breach emits one active violation until a qualifying reset.*
    - *Missing or nonfinite readings cannot count as normal pressure.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 07: F20, F34 (64–104 hours)

#### Package F20: Qualify post-irrigation readings before confirming delivery
- **Priority**: `P0` | **Budget**: `32-48 hours` | **Dependencies**: `F02, F05, F12, F17` | **Lane**: `Execution Lane`

- [ ] **`ST07-F20-01`: 1. Validate reading identity, tenant, plot/zone, depth, calibration and time sup...**
  - **Target File**: [`../services/agribrain/irrigation_runtime/validation.py`](../services/agribrain/irrigation_runtime/validation.py)
  - **Action**: 1. Validate reading identity, tenant, plot/zone, depth, calibration and time support.
  - **Estimate**: 8–12 hours | **Prerequisites**: `F02, F05, F12, F17`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST07-F20-02`: 2. Deduplicate measurement IDs and require post-action measurements inside the w...**
  - **Target File**: [`../services/agribrain/irrigation_runtime/validation.py`](../services/agribrain/irrigation_runtime/validation.py)
  - **Action**: 2. Deduplicate measurement IDs and require post-action measurements inside the window.
  - **Estimate**: 8–12 hours | **Prerequisites**: `ST07-F20-01`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST07-F20-03`: 3. Base expected response on verified delivered exposure and the same hydrologic...**
  - **Target File**: [`../services/agribrain/irrigation_runtime/validation.py`](../services/agribrain/irrigation_runtime/validation.py)
  - **Action**: 3. Base expected response on verified delivered exposure and the same hydrological support, not solely target_volume_mm.
  - **Estimate**: 8–12 hours | **Prerequisites**: `ST07-F20-02`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST07-F20-04`: 4. Keep moisture response distinct from delivery proof and disallow calibration ...**
  - **Target File**: [`../services/agribrain/irrigation_runtime/validation.py`](../services/agribrain/irrigation_runtime/validation.py)
  - **Action**: 4. Keep moisture response distinct from delivery proof and disallow calibration promotion from unqualified samples.
  - **Estimate**: 8–12 hours | **Prerequisites**: `ST07-F20-03`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST07-F20-FA`: Package F20 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files) | **Prerequisites**: `ST07-F20-01 through ST07-F20-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Foreign, stale and duplicate records do not raise confirmation confidence.*
    - *Reports list the sensors that actually contributed.*
    - *Rain, drainage, sensor support and delivery uncertainty are accounted for.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F34: Separate input accounting from applied agronomic exposure
- **Priority**: `P1` | **Budget**: `32-56 hours` | **Dependencies**: `F09, F11, F20` | **Lane**: `Execution Lane`

- [ ] **`ST07-F34-01`: 1. Validate unit and input category against controlled registries....**
  - **Target File**: [`../src/app/api/inputs/route.ts`](../src/app/api/inputs/route.ts)
  - **Action**: 1. Validate unit and input category against controlled registries.
  - **Estimate**: 8–14 hours | **Prerequisites**: `F09, F11, F20`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST07-F34-02`: 2. Store purchased, stocked, planned and applied events separately....**
  - **Target File**: [`../prisma/schema.prisma`](../prisma/schema.prisma)
  - **Action**: 2. Store purchased, stocked, planned and applied events separately.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST07-F34-01`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST07-F34-03`: 3. Convert product quantity to nutrient mass or delivered water using formulatio...**
  - **Target File**: [`../services/agribrain/layer3_decision/runner.py`](../services/agribrain/layer3_decision/runner.py)
  - **Action**: 3. Convert product quantity to nutrient mass or delivered water using formulation, area and support references.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST07-F34-02`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST07-F34-04`: 4. Publish verified application exposure to Worldline and update financial total...**
  - **Target File**: [`../services/agribrain/layer4_nutrients/runner.py`](../services/agribrain/layer4_nutrients/runner.py)
  - **Action**: 4. Publish verified application exposure to Worldline and update financial totals idempotently.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST07-F34-03`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST07-F34-FA`: Package F34 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files) | **Prerequisites**: `ST07-F34-01 through ST07-F34-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *A purchase or future plan cannot enter historical water/N balance.*
    - *Product kg and elemental nutrient kg are never interchanged.*
    - *Retry cannot double-count stock, cost or applied mass.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 08: F21, F22, F23, F24 (88–144 hours)

#### Package F21: Freeze training-window payloads and include partition identity
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F02, F09` | **Lane**: `Learning Lane`

- [ ] **`ST08-F21-01`: 1. Use immutable or deeply copied canonical event snapshots....**
  - **Target File**: [`../services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)
  - **Action**: 1. Use immutable or deeply copied canonical event snapshots.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F02, F09`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F21-02`: 2. Hash payload content, schema, partition, geometry/cycle and extraction policy...**
  - **Target File**: [`../services/agribrain/world_model/canonical_worldline.py`](../services/agribrain/world_model/canonical_worldline.py)
  - **Action**: 2. Hash payload content, schema, partition, geometry/cycle and extraction policy.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST08-F21-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F21-03`: 3. Include supersession/retraction resolution and ordered parent evidence in the...**
  - **Target File**: [`../services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)
  - **Action**: 3. Include supersession/retraction resolution and ordered parent evidence in the manifest.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST08-F21-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F21-04`: 4. Verify the digest again before dataset loading and model artifact creation....**
  - **Target File**: [`../services/agribrain/world_model/canonical_worldline.py`](../services/agribrain/world_model/canonical_worldline.py)
  - **Action**: 4. Verify the digest again before dataset loading and model artifact creation.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST08-F21-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F21-FA`: Package F21 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST08-F21-01 through ST08-F21-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Any included content change alters the manifest identity.*
    - *Caller mutation cannot alter an issued window.*
    - *Tenant/namespace boundaries have distinct manifest identities.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F22: Classify timing by event role rather than a universal causality rule
- **Priority**: `P0` | **Budget**: `20-32 hours` | **Dependencies**: `F02, F21` | **Lane**: `Learning Lane`

- [ ] **`ST08-F22-01`: 1. Define event-specific observation, forecast validity, planned action and avai...**
  - **Target File**: [`../services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)
  - **Action**: 1. Define event-specific observation, forecast validity, planned action and availability fields.
  - **Estimate**: 5–8 hours | **Prerequisites**: `F02, F21`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F22-02`: 2. Apply measurement chronology checks to measurements and issuance eligibility ...**
  - **Target File**: [`../services/agribrain/world_model/contracts.py`](../services/agribrain/world_model/contracts.py)
  - **Action**: 2. Apply measurement chronology checks to measurements and issuance eligibility to forecasts/scenarios.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST08-F22-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F22-03`: 3. Validate each child input and revision against the cutoff....**
  - **Target File**: [`../services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)
  - **Action**: 3. Validate each child input and revision against the cutoff.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST08-F22-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F22-04`: 4. Build separate manifests for inputs, later targets and retrospective reconstr...**
  - **Target File**: [`../services/agribrain/world_model/contracts.py`](../services/agribrain/world_model/contracts.py)
  - **Action**: 4. Build separate manifests for inputs, later targets and retrospective reconstructions.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST08-F22-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F22-FA`: Package F22 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST08-F22-01 through ST08-F22-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *An archived earlier-issued future forecast remains an eligible input.*
    - *A future measurement is still excluded.*
    - *A planned action stays a scenario and never becomes historical applied water.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F23: Commit forecast archives atomically before publishing cache entries
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F21, F22` | **Lane**: `Learning Lane`

- [ ] **`ST08-F23-01`: 1. Validate immutable content and resolve the durable record before altering cac...**
  - **Target File**: [`../services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)
  - **Action**: 1. Validate immutable content and resolve the durable record before altering cache.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F21, F22`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F23-02`: 2. Use an atomic conditional insert or equivalent lock/fence instead of exists-t...**
  - **Target File**: [`../services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)
  - **Action**: 2. Use an atomic conditional insert or equivalent lock/fence instead of exists-then-replace races.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST08-F23-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F23-03`: 3. Deep-freeze nested predictions and metadata....**
  - **Target File**: [`../services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)
  - **Action**: 3. Deep-freeze nested predictions and metadata.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST08-F23-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F23-04`: 4. Treat corrupt or conflicting records as explicit integrity errors instead of ...**
  - **Target File**: [`../services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)
  - **Action**: 4. Treat corrupt or conflicting records as explicit integrity errors instead of absence.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST08-F23-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F23-FA`: Package F23 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files) | **Prerequisites**: `ST08-F23-01 through ST08-F23-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *After conflict, warm and cold readers return the committed forecast only.*
    - *Concurrent incompatible writes produce one committed identity.*
    - *Mutation cannot alter archived predictions or subsequent evaluation.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F24: Validate forecast distributions and make missing scores unavailable
- **Priority**: `P0` | **Budget**: `20-32 hours` | **Dependencies**: `F13, F23` | **Lane**: `Learning Lane`

- [ ] **`ST08-F24-01`: 1. Require finite consistent horizon, timezone-aware origin/target and a support...**
  - **Target File**: [`../services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)
  - **Action**: 1. Require finite consistent horizon, timezone-aware origin/target and a supported finite distribution.
  - **Estimate**: 5–8 hours | **Prerequisites**: `F13, F23`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F24-02`: 2. Validate quantile levels and monotonicity, variable units/domain and nonnegat...**
  - **Target File**: [`../services/agribrain/layer6_yield/yield_forecast.py`](../services/agribrain/layer6_yield/yield_forecast.py)
  - **Action**: 2. Validate quantile levels and monotonicity, variable units/domain and nonnegative sigma.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST08-F24-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F24-03`: 3. Return unavailable with reason for missing distributions and reject invalid s...**
  - **Target File**: [`../services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)
  - **Action**: 3. Return unavailable with reason for missing distributions and reject invalid sigma.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST08-F24-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F24-04`: Implement accurate sparse quantile scoring (compute_crps_quantiles lines 163–199...**
  - **Target File**: [`../services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)
  - **Action**: Implement accurate sparse quantile scoring (compute_crps_quantiles lines 163–199); require explicit p50 (never obs fallback).
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST08-F24-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST08-F24-FA`: Package F24 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST08-F24-01 through ST08-F24-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Empty or malformed forecasts receive no numeric skill credit.*
    - *Origin-target interval and horizon agree.*
    - *Quantile coverage and scores use explicit levels and independently supported targets.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 09: F25, F26, F27, F28, F29 (140–232 hours)

#### Package F25: Report the actual EO inference backend and normalize its input contract
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F01` | **Lane**: `Learning Lane`

- [ ] **`ST09-F25-01`: 1. Return backend identity and model artifact digest with every inference result...**
  - **Target File**: [`../services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action**: 1. Return backend identity and model artifact digest with every inference result.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F25-02`: 2. Create explicit per-model tensor, band order, normalization and mask adapters...**
  - **Target File**: [`../services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action**: 2. Create explicit per-model tensor, band order, normalization and mask adapters.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST09-F25-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F25-03`: 3. On backend failure, publish the fallback role and cause, or make the capabili...**
  - **Target File**: [`../services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action**: 3. On backend failure, publish the fallback role and cause, or make the capability unavailable.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST09-F25-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F25-04`: 4. Derive confidence from evaluated model/domain evidence rather than file prese...**
  - **Target File**: [`../services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action**: 4. Derive confidence from evaluated model/domain evidence rather than file presence.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST09-F25-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F25-FA`: Package F25 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files) | **Prerequisites**: `ST09-F25-01 through ST09-F25-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *A failed ONNX call cannot label fallback features as learned model output.*
    - *Wrong input shape fails at a clear contract boundary.*
    - *Model identity includes weights, preprocessing and calibration versions.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F26: Hash complete EO support and distinguish missing bands from zero
- **Priority**: `P1` | **Budget**: `20-32 hours` | **Dependencies**: `F25` | **Lane**: `Learning Lane`

- [ ] **`ST09-F26-01`: 1. Build digests from band identity/order, shape, numeric encoding, CRS/affine a...**
  - **Target File**: [`../services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action**: 1. Build digests from band identity/order, shape, numeric encoding, CRS/affine and validity/cloud masks.
  - **Estimate**: 5–8 hours | **Prerequisites**: `F25`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F26-02`: 2. Validate aligned shapes and mask coverage before pooling....**
  - **Target File**: [`../services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action**: 2. Validate aligned shapes and mask coverage before pooling.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST09-F26-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F26-03`: 3. Pass missing-band masks into supported models or declare the fallback feature...**
  - **Target File**: [`../services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action**: 3. Pass missing-band masks into supported models or declare the fallback feature policy.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST09-F26-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F26-04`: 4. Require finite pixels and model-specific reflectance scale....**
  - **Target File**: [`../services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action**: 4. Require finite pixels and model-specific reflectance scale.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST09-F26-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F26-FA`: Package F26 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files) | **Prerequisites**: `ST09-F26-01 through ST09-F26-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Different spectral support or masks have distinct identities.*
    - *A missing band is distinguishable from true zero reflectance.*
    - *A model cannot silently consume misaligned channels.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F27: Repair MESIA link-time axes and graph topology
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F01, F26` | **Lane**: `Learning Lane`

- [ ] **`ST09-F27-01`: 1. Restore B,L,S,D and explicitly permute to B,S,L,D....**
  - **Target File**: [`../services/agribrain/mesia/learning/neural_receiver.py`](../services/agribrain/mesia/learning/neural_receiver.py)
  - **Action**: 1. Restore B,L,S,D and explicitly permute to B,S,L,D.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F01, F26`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F27-02`: 2. Define valid-link padding and graph masks with batch/time semantics....**
  - **Target File**: [`../services/agribrain/mesia/learning/neural_receiver.py`](../services/agribrain/mesia/learning/neural_receiver.py)
  - **Action**: 2. Define valid-link padding and graph masks with batch/time semantics.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST09-F27-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F27-03`: 3. Thread geometry, antenna and instrument epochs through the neural receiver....**
  - **Target File**: [`../services/agribrain/mesia/learning/neural_receiver.py`](../services/agribrain/mesia/learning/neural_receiver.py)
  - **Action**: 3. Thread geometry, antenna and instrument epochs through the neural receiver.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST09-F27-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F27-04`: 4. Compare topology-aware output with an intentionally topology-free baseline....**
  - **Target File**: [`../services/agribrain/mesia/learning/neural_receiver.py`](../services/agribrain/mesia/learning/neural_receiver.py)
  - **Action**: 4. Compare topology-aware output with an intentionally topology-free baseline.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST09-F27-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F27-FA`: Package F27 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files) | **Prerequisites**: `ST09-F27-01 through ST09-F27-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Distinct link/time marker tensors preserve their identities.*
    - *Invalid links do not affect pooling or attention.*
    - *Changing topology affects only permitted message paths.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F28: Make MESIA masked pretraining respect complex channel semantics
- **Priority**: `P1` | **Budget**: `32-48 hours` | **Dependencies**: `F27` | **Lane**: `Learning Lane`

- [ ] **`ST09-F28-01`: 1. Derive decoder dimensions from the actual ModelArtifact configuration....**
  - **Target File**: [`../services/agribrain/mesia/learning/masked_link_trainer.py`](../services/agribrain/mesia/learning/masked_link_trainer.py)
  - **Action**: 1. Derive decoder dimensions from the actual ModelArtifact configuration.
  - **Estimate**: 8–12 hours | **Prerequisites**: `F27`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F28-02`: 2. Use paired masks for complex channel elements and explicit link/time/frequenc...**
  - **Target File**: [`../services/agribrain/mesia/learning/neural_receiver.py`](../services/agribrain/mesia/learning/neural_receiver.py)
  - **Action**: 2. Use paired masks for complex channel elements and explicit link/time/frequency mask tokens.
  - **Estimate**: 8–12 hours | **Prerequisites**: `ST09-F28-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F28-03`: 3. Represent phase circularly or complex-valued and apply the corresponding like...**
  - **Target File**: [`../services/agribrain/mesia/learning/masked_link_trainer.py`](../services/agribrain/mesia/learning/masked_link_trainer.py)
  - **Action**: 3. Represent phase circularly or complex-valued and apply the corresponding likelihood/loss.
  - **Estimate**: 8–12 hours | **Prerequisites**: `ST09-F28-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F28-04`: 4. Exclude padded, missing and uncalibrated-invalid samples from objectives that...**
  - **Target File**: [`../services/agribrain/mesia/learning/neural_receiver.py`](../services/agribrain/mesia/learning/neural_receiver.py)
  - **Action**: 4. Exclude padded, missing and uncalibrated-invalid samples from objectives that require them, while retaining compatible discovery objectives.
  - **Estimate**: 8–12 hours | **Prerequisites**: `ST09-F28-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F28-FA`: Package F28 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST09-F28-01 through ST09-F28-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Non-128 receiver configurations have compatible decoders.*
    - *Equivalent phase angles have small circular error.*
    - *Masked-loss support and normalization are reproducible and finite.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F29: Correct MESIA evaluation labels and establish independent biological validation
- **Priority**: `P1` | **Budget**: `40-72 plus field work hours` | **Dependencies**: `F05, F24, F27, F28` | **Lane**: `Learning Lane`

- [ ] **`ST09-F29-01`: 1. Bind evaluation channels to the actual state registry and support contract....**
  - **Target File**: [`../services/agribrain/mesia/learning/asmae_evaluator.py`](../services/agribrain/mesia/learning/asmae_evaluator.py)
  - **Action**: 1. Bind evaluation channels to the actual state registry and support contract.
  - **Estimate**: 10–18 hours | **Prerequisites**: `F05, F24, F27, F28`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F29-02`: 2. Label R-squared, correlation and predictive error as distinct metrics with co...**
  - **Target File**: [`../services/agribrain/mesia/behaviour/likelihood_engine.py`](../services/agribrain/mesia/behaviour/likelihood_engine.py)
  - **Action**: 2. Label R-squared, correlation and predictive error as distinct metrics with constant-target handling.
  - **Estimate**: 10–18 hours | **Prerequisites**: `ST09-F29-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F29-03`: 3. Evaluate held-out sites, instruments, seasons and nuisance interventions agai...**
  - **Target File**: [`../services/agribrain/mesia/assimilation/observability_analyzer.py`](../services/agribrain/mesia/assimilation/observability_analyzer.py)
  - **Action**: 3. Evaluate held-out sites, instruments, seasons and nuisance interventions against independent qualified measurements.
  - **Estimate**: 10–18 hours | **Prerequisites**: `ST09-F29-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F29-04`: 4. Promote only demonstrated per-variable capabilities and keep discovery repres...**
  - **Target File**: [`../services/agribrain/mesia/learning/asmae_evaluator.py`](../services/agribrain/mesia/learning/asmae_evaluator.py)
  - **Action**: 4. Promote only demonstrated per-variable capabilities and keep discovery representations available without biological claims.
  - **Estimate**: 10–18 hours | **Prerequisites**: `ST09-F29-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST09-F29-FA`: Package F29 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST09-F29-01 through ST09-F29-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Changing the configured state count cannot crash or mislabel channels.*
    - *Agreement with an ASMAE teacher is reported as dependent evaluation.*
    - *Biological capability requires independent calibration and nuisance-controlled validation.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 10: F30, F31, F32, F33, F38, F40 (172–296 hours)

#### Package F30: Scope conversational memory and cache identity
- **Priority**: `P1` | **Budget**: `32-48 hours` | **Dependencies**: `F02, F09` | **Lane**: `Application Lane`

- [ ] **`ST10-F30-01`: 1. Define explicit tenant/user/thread/plot/cycle scope for conversational memory...**
  - **Target File**: [`../services/agribrain/layer9_interface/runner.py`](../services/agribrain/layer9_interface/runner.py)
  - **Action**: 1. Define explicit tenant/user/thread/plot/cycle scope for conversational memory.
  - **Estimate**: 8–12 hours | **Prerequisites**: `F02, F09`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F30-02`: 2. Resolve references only from sources authorized for the active thread....**
  - **Target File**: [`../services/agribrain/layer9_interface/engines/conversation_memory.py`](../services/agribrain/layer9_interface/engines/conversation_memory.py)
  - **Action**: 2. Resolve references only from sources authorized for the active thread.
  - **Estimate**: 8–12 hours | **Prerequisites**: `ST10-F30-01`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F30-03`: 3. Include state head, policy, model, language, intent and claim artifacts in ca...**
  - **Target File**: [`../services/agribrain/layer9_interface/engines/semantic_cache.py`](../services/agribrain/layer9_interface/engines/semantic_cache.py)
  - **Action**: 3. Include state head, policy, model, language, intent and claim artifacts in cache identity.
  - **Estimate**: 8–12 hours | **Prerequisites**: `ST10-F30-02`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F30-04`: 4. Preserve numeric quantities and negation, and cache canonically generated art...**
  - **Target File**: [`../services/agribrain/layer9_interface/runner.py`](../services/agribrain/layer9_interface/runner.py)
  - **Action**: 4. Preserve numeric quantities and negation, and cache canonically generated artifacts rather than free-standing operational advice.
  - **Estimate**: 8–12 hours | **Prerequisites**: `ST10-F30-03`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F30-FA`: Package F30 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST10-F30-01 through ST10-F30-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *No user thread inherits another user narrative without authorized sharing.*
    - *A changed dose, cutoff or policy invalidates the advice cache.*
    - *Runtime tracing proves which cache paths are active before rollout.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F31: Close the independent public AI advice path
- **Priority**: `P0` | **Budget**: `24-40 hours` | **Dependencies**: `F01, F02, F15, F30` | **Lane**: `Application Lane`

- [ ] **`ST10-F31-01`: 1. Require authentication and authorize any requested plot context....**
  - **Target File**: [`../src/app/api/ai/chat/route.ts`](../src/app/api/ai/chat/route.ts)
  - **Action**: 1. Require authentication and authorize any requested plot context.
  - **Estimate**: 6–10 hours | **Prerequisites**: `F01, F02, F15, F30`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F31-02`: 2. Resolve trusted context server-side rather than treating browser fields as ev...**
  - **Target File**: [`../src/lib/agribrain/gemini-advisor.ts`](../src/lib/agribrain/gemini-advisor.ts)
  - **Action**: 2. Resolve trusted context server-side rather than treating browser fields as evidence.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST10-F31-01`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F31-03`: 3. Route plot-specific advice through canonical intent, claims, constraints and ...**
  - **Target File**: [`../src/app/api/agribrain/intent/route.ts`](../src/app/api/agribrain/intent/route.ts)
  - **Action**: 3. Route plot-specific advice through canonical intent, claims, constraints and visible response.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST10-F31-02`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F31-04`: 4. Keep educational content explicitly educational and apply provider quotas and...**
  - **Target File**: [`../src/app/api/ai/chat/route.ts`](../src/app/api/ai/chat/route.ts)
  - **Action**: 4. Keep educational content explicitly educational and apply provider quotas and body limits.
  - **Estimate**: 6–10 hours | **Prerequisites**: `ST10-F31-03`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F31-FA`: Package F31 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST10-F31-01 through ST10-F31-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Unauthorized context cannot become plot-specific advice.*
    - *Rendered numbers and prohibitions match the canonical artifact.*
    - *Provider failures and missing evidence produce explicit unavailable or educational responses.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F32: Replace demo calendar and misleading empty/error application states
- **Priority**: `P1` | **Budget**: `32-56 hours` | **Dependencies**: `F09` | **Lane**: `Application Lane`

- [ ] **`ST10-F32-01`: 1. Connect calendar to authorized persisted task/cycle records and scoped date-r...**
  - **Target File**: [`../src/app/calendar/page.tsx`](../src/app/calendar/page.tsx)
  - **Action**: 1. Connect calendar to authorized persisted task/cycle records and scoped date-range queries.
  - **Estimate**: 8–14 hours | **Prerequisites**: `F09`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F32-02`: 2. Persist completion, deviations, assignees and timezone instead of local demo ...**
  - **Target File**: [`../src/app/api/cycles/[id]/tasks/route.ts`](../src/app/api/cycles/[id]/tasks/route.ts)
  - **Action**: 2. Persist completion, deviations, assignees and timezone instead of local demo state.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST10-F32-01`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F32-03`: 3. Distinguish loading, empty, unauthorized and unavailable states in farms and ...**
  - **Target File**: [`../src/app/farm/page.tsx`](../src/app/farm/page.tsx)
  - **Action**: 3. Distinguish loading, empty, unauthorized and unavailable states in farms and dashboards.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST10-F32-02`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F32-04`: 4. Put demo records in an explicit isolated demo namespace and remove real-tenan...**
  - **Target File**: [`../src/app/api/dashboard/stats/route.ts`](../src/app/api/dashboard/stats/route.ts)
  - **Action**: 4. Put demo records in an explicit isolated demo namespace and remove real-tenant development fallback.
  - **Estimate**: 8–14 hours | **Prerequisites**: `ST10-F32-03`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F32-FA`: Package F32 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files) | **Prerequisites**: `ST10-F32-01 through ST10-F32-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *A new empty account sees no fabricated tasks.*
    - *Task edits survive reload and appear in the scientific exposure workflow when qualified.*
    - *Database outage shows unavailable instead of a successful empty farm or zero statistics.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F33: Validate photo zone ownership and database insert success
- **Priority**: `P1` | **Budget**: `12-24 hours` | **Dependencies**: `F01, F02, F09` | **Lane**: `Application Lane`

- [ ] **`ST10-F33-01`: 1. Resolve optional zone against the authorized plot and geometry epoch....**
  - **Target File**: [`../src/app/api/evidence/add/route.ts`](../src/app/api/evidence/add/route.ts)
  - **Action**: 1. Resolve optional zone against the authorized plot and geometry epoch.
  - **Estimate**: 3–6 hours | **Prerequisites**: `F01, F02, F09`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F33-02`: 2. Validate observation timing and retain the server availability timestamp....**
  - **Target File**: [`../prisma/schema.prisma`](../prisma/schema.prisma)
  - **Action**: 2. Validate observation timing and retain the server availability timestamp.
  - **Estimate**: 3–6 hours | **Prerequisites**: `ST10-F33-01`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F33-03`: 3. Check raw write outcome and return the canonical created evidence ID....**
  - **Target File**: [`../src/app/api/evidence/add/route.ts`](../src/app/api/evidence/add/route.ts)
  - **Action**: 3. Check raw write outcome and return the canonical created evidence ID.
  - **Estimate**: 3–6 hours | **Prerequisites**: `ST10-F33-02`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F33-04`: 4. Preserve pending processing and use a durable admission/outbox event for retr...**
  - **Target File**: [`../prisma/schema.prisma`](../prisma/schema.prisma)
  - **Action**: 4. Preserve pending processing and use a durable admission/outbox event for retries.
  - **Estimate**: 3–6 hours | **Prerequisites**: `ST10-F33-03`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST10-F33-FA`: Package F33 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST10-F33-01 through ST10-F33-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *A foreign valid-looking zone cannot be attached.*
    - *Failed raw insertion cannot return success.*
    - *Photo availability and processing state are recoverable after retry.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F38: Restore failure ledgers, scoped loading and degraded publication
- **Priority**: `P0` | **Budget**: `48-80 hours` | **Dependencies**: `F01, F02, F09, F31, F37` | **Lane**: `Evidence Lane`

- [ ] **`ST10-F38-01`: 1. Use the function-local decision timestamp in terminal no-data output and veri...**
  - **Target File**: [`../services/agribrain/orchestrator_v2/runner.py`](../services/agribrain/orchestrator_v2/runner.py)
  - **Action**: 1. Use the function-local decision timestamp in terminal no-data output and verify degraded output commits through the canonical publication contract.
  - **Estimate**: 5–8 hours | **Prerequisites**: `F01, F02, F09, F31, F37`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST10-F38-02`: Thread intent and user mode through chat_adapter and run_entrypoint.py lines 444...**
  - **Target File**: [`../services/agribrain/orchestrator_v2/chat_adapter.py`](../services/agribrain/orchestrator_v2/chat_adapter.py)
  - **Action**: Thread intent and user mode through chat_adapter and run_entrypoint.py lines 444, 471.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST10-F38-01`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST10-F38-03`: 3. Build geometry explicitly in the synthetic bridge helper and isolate that hel...**
  - **Target File**: [`../services/agribrain/layer10_sire/l10_frontend_bridge.py`](../services/agribrain/layer10_sire/l10_frontend_bridge.py)
  - **Action**: 3. Build geometry explicitly in the synthetic bridge helper and isolate that helper from normal product inputs.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST10-F38-02`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST10-F38-04`: 4. Build failed ASMAE validation receipts from inp and its qualified geometry, r...**
  - **Target File**: [`../services/agribrain/layer05_asmae/runner.py`](../services/agribrain/layer05_asmae/runner.py)
  - **Action**: 4. Build failed ASMAE validation receipts from inp and its qualified geometry, removing arbitrary geometry-hash fallback.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST10-F38-03`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST10-F38-05`: 5. Resolve external-scene resolution from validated grid metadata and preserve e...**
  - **Target File**: [`../services/agribrain/layer05_asmae/geometry/external_scene_loader.py`](../services/agribrain/layer05_asmae/geometry/external_scene_loader.py)
  - **Action**: 5. Resolve external-scene resolution from validated grid metadata and preserve each rejected-scene reason.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST10-F38-04`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST10-F38-06`: 6. Require qualified MESIA namespace rather than fabricated default scope....**
  - **Target File**: [`../services/agribrain/mesia/service.py`](../services/agribrain/mesia/service.py)
  - **Action**: 6. Require qualified MESIA namespace rather than fabricated default scope.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST10-F38-05`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST10-F38-07`: Import statistics.mean in growth_engine.py line 296 and IrrigationSystemType in ...**
  - **Target File**: [`../services/agribrain/layer2_veg_int/growth_engine.py`](../services/agribrain/layer2_veg_int/growth_engine.py)
  - **Action**: Import statistics.mean in growth_engine.py line 296 and IrrigationSystemType in dispatcher.py line 272.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST10-F38-06`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST10-F38-08`: 8. Parse completed timestamps robustly but derive published only from the exact ...**
  - **Target File**: [`../services/agribrain/app/main.py`](../services/agribrain/app/main.py)
  - **Action**: 8. Parse completed timestamps robustly but derive published only from the exact committed output relation, including superseded heads.
  - **Estimate**: 5–8 hours | **Prerequisites**: `ST10-F38-07`
  - **Verification**: Validate finite numeric filtering (`math.isfinite`), legitimate zero round-trip, observation vs knowledge cutoffs, and truthful failure receipts without fabricated defaults.

- [ ] **`ST10-F38-09`: 9. Classify each caught failure as unavailable capability or partial result with...**
  - **Target File**: [`../services/agribrain/irrigation_runtime/dispatcher.py`](../services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action**: 9. Classify each caught failure as unavailable capability or partial result with observable diagnostic instead of silently manufacturing success.
  - **Estimate**: 8–16 hours | **Prerequisites**: `ST10-F38-08`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST10-F38-FA`: Package F38 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (10 files) | **Prerequisites**: `ST10-F38-01 through ST10-F38-09`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *The three reproduced external-scene, growth-spacing and missing-event cases no longer fail.*
    - *Degraded L1 emits a committed no-data response using ts_now.*
    - *ASMAE failure still returns its original error and also persists its failure receipt.*
    - *A foreign or mismatched head cannot prove the completed job was published.*
    - *Missing scope never becomes default_tenant/default_farm.*
    - *Local response compression/routing use the real intent and mode.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F40: Resolve annotation consumers and close verification evidence gaps
- **Priority**: `P1` | **Budget**: `24-48 hours` | **Dependencies**: `F37, F38` | **Lane**: `Application Lane`

- [ ] **`ST10-F40-01`: 1. Import or explicitly resolve annotation names where runtime consumers need th...**
  - **Target File**: [`../services/agribrain/layer0/kalman_engine.py`](../services/agribrain/layer0/kalman_engine.py)
  - **Action**: 1. Import or explicitly resolve annotation names where runtime consumers need them.
  - **Estimate**: 3–6 hours | **Prerequisites**: `F37, F38`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST10-F40-02`: 2. Use postponed type-only imports only when schema/introspection frameworks do ...**
  - **Target File**: [`../services/agribrain/mesia/identity/correlators.py`](../services/agribrain/mesia/identity/correlators.py)
  - **Action**: 2. Use postponed type-only imports only when schema/introspection frameworks do not require resolution.
  - **Estimate**: 3–6 hours | **Prerequisites**: `ST10-F40-01`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST10-F40-03`: 3. Audit the 18 cited files and every public dataclass/Pydantic/tool-schema cons...**
  - **Target File**: [`../services/agribrain/world_model/belief_snapshot.py`](../services/agribrain/world_model/belief_snapshot.py)
  - **Action**: 3. Audit the 18 cited files and every public dataclass/Pydantic/tool-schema consumer with the installed declared runtime.
  - **Estimate**: 3–6 hours | **Prerequisites**: `ST10-F40-02`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST10-F40-04`: 4. Create a pinned full production manifest with exact exclusion rules and suppo...**
  - **Target File**: [`../services/agribrain/layer4_nutrients/schema.py`](../services/agribrain/layer4_nutrients/schema.py)
  - **Action**: 4. Create a pinned full production manifest with exact exclusion rules and supported Python/dependency versions.
  - **Estimate**: 3–6 hours | **Prerequisites**: `ST10-F40-03`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST10-F40-05`: 5. Compile the manifest and cold-load decorated schemas separately....**
  - **Target File**: [`../services/agribrain/sensor_runtime/registry.py`](../services/agribrain/sensor_runtime/registry.py)
  - **Action**: 5. Compile the manifest and cold-load decorated schemas separately.
  - **Estimate**: 3–6 hours | **Prerequisites**: `ST10-F40-04`
  - **Verification**: Validate atomic multi-worker replay protection, nonce idempotency, finite sensor telemetry filtering, and strict hardware failure receipts.

- [ ] **`ST10-F40-06`: 6. Classify exception handlers by recovery and published scientific effect, and ...**
  - **Target File**: [`../services/agribrain/layer05_asmae/background_jobs.py`](../services/agribrain/layer05_asmae/background_jobs.py)
  - **Action**: 6. Classify exception handlers by recovery and published scientific effect, and run a history-aware secrets check without exposing values.
  - **Estimate**: 3–6 hours | **Prerequisites**: `ST10-F40-05`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST10-F40-07`: 7. Publish scope and reproducible receipts rather than extending subset zero cou...**
  - **Target File**: [`../services/agribrain/layer0/kalman_engine.py`](../services/agribrain/layer0/kalman_engine.py)
  - **Action**: 7. Publish scope and reproducible receipts rather than extending subset zero counts to the whole tree.
  - **Estimate**: 6–12 hours | **Prerequisites**: `ST10-F40-06`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST10-F40-FA`: Package F40 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (6 files) | **Prerequisites**: `ST10-F40-01 through ST10-F40-07`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *get_type_hints and production schema generation succeed for supported public contracts.*
    - *The runtime and file manifest accompany every verification count.*
    - *An unresolved annotation cannot silently invalidate a tool/schema registration.*
    - *Secret, portability, dataclass and full-repository claims remain unqualified until their own checks complete.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 11: F35, F36, T11 (168–296 hours)

#### Package F35: Repair drone driver import and complete process cleanup
- **Priority**: `P1` | **Budget**: `20-36 hours` | **Dependencies**: `F09` | **Lane**: `Application Lane`

- [ ] **`ST11-F35-01`: 1. Lazy-load explicitly configured real drivers and move simulation behind an ex...**
  - **Target File**: [`../services/agribrain/drone_control/dispatcher.py`](../services/agribrain/drone_control/dispatcher.py)
  - **Action**: 1. Lazy-load explicitly configured real drivers and move simulation behind an explicit test/development capability.
  - **Estimate**: 5–9 hours | **Prerequisites**: `F09`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST11-F35-02`: 2. Return unavailable driver capability without breaking unrelated service impor...**
  - **Target File**: [`../services/agribrain/app/drone_routes.py`](../services/agribrain/app/drone_routes.py)
  - **Action**: 2. Return unavailable driver capability without breaking unrelated service import.
  - **Estimate**: 5–9 hours | **Prerequisites**: `ST11-F35-01`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST11-F35-03`: 3. Complete terminate-kill-wait lifecycle and process-group cleanup under a boun...**
  - **Target File**: [`../services/agribrain/layer05_asmae/background_jobs.py`](../services/agribrain/layer05_asmae/background_jobs.py)
  - **Action**: 3. Complete terminate-kill-wait lifecycle and process-group cleanup under a bounded deadline.
  - **Estimate**: 5–9 hours | **Prerequisites**: `ST11-F35-02`
  - **Verification**: Validate Next.js/TypeScript clean build, Prisma migration consistency, 503 unavailable on database outage (preserving authentic zero stats), and runtime type introspection without deferred NameError.

- [ ] **`ST11-F35-04`: 4. Fence all child writes and publish final cleanup/ownership receipts....**
  - **Target File**: [`../services/agribrain/drone_control/dispatcher.py`](../services/agribrain/drone_control/dispatcher.py)
  - **Action**: 4. Fence all child writes and publish final cleanup/ownership receipts.
  - **Estimate**: 5–9 hours | **Prerequisites**: `ST11-F35-03`
  - **Verification**: Validate autonomous duration watchdog execution regardless of telemetry presence, non-bypassable pre-flight quota checks, immutable hard caps (salinity leaching), and strict physical actuator interlocks.

- [ ] **`ST11-F35-FA`: Package F35 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST11-F35-01 through ST11-F35-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Missing optional drivers cannot disable service startup.*
    - *Simulation cannot publish observed mission evidence.*
    - *Forced-kill cleanup confirms process exit before resource ownership is released.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F36: Require per-variable observability and independent predictive calibration
- **Priority**: `P1` | **Budget**: `48-80 plus reference data hours` | **Dependencies**: `F01, F02, F24, F29` | **Lane**: `Learning Lane`

- [ ] **`ST11-F36-01`: 1. Build a per-state support ledger connecting actual operator sensitivity and i...**
  - **Target File**: [`../services/agribrain/layer05_asmae/training/exporter.py`](../services/agribrain/layer05_asmae/training/exporter.py)
  - **Action**: 1. Build a per-state support ledger connecting actual operator sensitivity and independent references to each label.
  - **Estimate**: 12–20 hours | **Prerequisites**: `F01, F02, F24, F29`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST11-F36-02`: 2. Carry dependence groups for indices from shared native acquisitions and BMA e...**
  - **Target File**: [`../services/agribrain/layer05_asmae/observation/index_state_mapping.py`](../services/agribrain/layer05_asmae/observation/index_state_mapping.py)
  - **Action**: 2. Carry dependence groups for indices from shared native acquisitions and BMA experts sharing evidence.
  - **Estimate**: 12–20 hours | **Prerequisites**: `ST11-F36-01`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST11-F36-03`: 3. Use archived prospective issuance cohorts separately from hindcasts and persi...**
  - **Target File**: [`../services/agribrain/layer05_asmae/constraints/radiometric.py`](../services/agribrain/layer05_asmae/constraints/radiometric.py)
  - **Action**: 3. Use archived prospective issuance cohorts separately from hindcasts and persistence, with per-variable/horizon calibration.
  - **Estimate**: 12–20 hours | **Prerequisites**: `ST11-F36-02`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST11-F36-04`: 4. Tune process noise and rejection thresholds on frozen independent cohorts ins...**
  - **Target File**: [`../services/agribrain/layer05_asmae/retrovalidation/engine.py`](../services/agribrain/layer05_asmae/retrovalidation/engine.py)
  - **Action**: 4. Tune process noise and rejection thresholds on frozen independent cohorts instead of selecting values for a passing pipeline flag.
  - **Estimate**: 12–20 hours | **Prerequisites**: `ST11-F36-03`
  - **Verification**: Validate immutable dataset window hashes, explicit UNAVAILABLE scores on invalid distributions, exact Gaussian multipliers ($1.28155\sigma$ for P10/P90), and truthful backend reporting (`spectral_basis_v2` vs `onnx_foundation`).

- [ ] **`ST11-F36-FA`: Package F36 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files) | **Prerequisites**: `ST11-F36-01 through ST11-F36-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *An unsupported coordinate has explicit prior/reconstruction role and compatible objective weight.*
    - *Derived indices and shared teachers do not count as independent references.*
    - *Forecast skill, coverage and domain evidence are reported per variable and horizon against stated baselines.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T11: Operational reproducibility, provider resilience and publication integrity
- **Priority**: `Target` | **Budget**: `100-180 hours` | **Dependencies**: `F09, F23, F25, F31, F35` | **Lane**: `Target Capability Lane`

- [ ] **`ST11-T11-01`: [Engineering Infrastructure] 1. Lock dependencies and produce code/image/model/c...**
  - **Target File**: [`../services/agribrain/layer0/data_gateway/request_broker.py`](../services/agribrain/layer0/data_gateway/request_broker.py)
  - **Action**: [Engineering Infrastructure] 1. Lock dependencies and produce code/image/model/config identities for each run.
  - **Estimate**: 25–45 hours | **Prerequisites**: `F09, F23, F25, F31, F35`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST11-T11-02`: [Engineering Infrastructure] 2. Trace all production entrypoints to one source a...**
  - **Target File**: [`../services/agribrain/layer05_asmae/background_jobs.py`](../services/agribrain/layer05_asmae/background_jobs.py)
  - **Action**: [Engineering Infrastructure] 2. Trace all production entrypoints to one source admission and scoped publication policy.
  - **Estimate**: 25–45 hours | **Prerequisites**: `ST11-T11-01`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST11-T11-03`: 3. Run bounded provider outage, corruption, timeout, restart, duplicate and conc...**
  - **Target File**: [`../services/agribrain/orchestrator_v2/storage.py`](../services/agribrain/orchestrator_v2/storage.py)
  - **Action**: 3. Run bounded provider outage, corruption, timeout, restart, duplicate and concurrent-writer drills.
  - **Estimate**: 25–45 hours | **Prerequisites**: `ST11-T11-02`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST11-T11-04`: 4. Add operational telemetry for rejected evidence, stale state, scope, compute ...**
  - **Target File**: [`../services/agribrain/app/main.py`](../services/agribrain/app/main.py)
  - **Action**: 4. Add operational telemetry for rejected evidence, stale state, scope, compute resources and committed publication heads.
  - **Estimate**: 25–45 hours | **Prerequisites**: `ST11-T11-03`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST11-T11-FA`: Package T11 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files) | **Prerequisites**: `ST11-T11-01 through ST11-T11-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *A response never points to an uncommitted or foreign result.*
    - *Provider outage degrades only dependent capabilities.*
    - *Recovery reproduces the same canonical artifacts without duplicate execution.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 12: T01, T02, T12 (240–420 hours)

#### Package T01: One canonical coupled agricultural trajectory
- **Priority**: `Target` | **Budget**: `80-140 hours` | **Dependencies**: `F03, F09, F10, F11` | **Lane**: `Target Capability Lane`

- [ ] **`ST12-T01-01`: [Engineering Infrastructure] 1. Define a versioned X/Z/H/M/U snapshot with avail...**
  - **Target File**: [`../services/agribrain/world_model/canonical_worldline.py`](../services/agribrain/world_model/canonical_worldline.py)
  - **Action**: [Engineering Infrastructure] 1. Define a versioned X/Z/H/M/U snapshot with availability and support per coordinate.
  - **Estimate**: 20–35 hours | **Prerequisites**: `F03, F09, F10, F11`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST12-T01-02`: [Engineering Infrastructure] 2. Specify operator-splitting order and feed L3/L4 ...**
  - **Target File**: [`../services/agribrain/world_model/belief_snapshot.py`](../services/agribrain/world_model/belief_snapshot.py)
  - **Action**: [Engineering Infrastructure] 2. Specify operator-splitting order and feed L3/L4 constraints back into the next vegetation growth transition.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST12-T01-01`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST12-T01-03`: [Empirical Milestone] 3. Link transition, analysis, management and diagnostic re...**
  - **Target File**: [`../services/agribrain/layer2_contracts/state_transition.py`](../services/agribrain/layer2_contracts/state_transition.py)
  - **Action**: [Empirical Milestone] 3. Link transition, analysis, management and diagnostic receipts to one predecessor.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST12-T01-02`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST12-T01-04`: [Empirical Milestone] 4. Publish read-only projections for L7-L10 rather than in...**
  - **Target File**: [`../services/agribrain/orchestrator_v2/runner.py`](../services/agribrain/orchestrator_v2/runner.py)
  - **Action**: [Empirical Milestone] 4. Publish read-only projections for L7-L10 rather than independent local physical reconstructions.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST12-T01-03`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST12-T01-FA`: Package T01 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files) | **Prerequisites**: `ST12-T01-01 through ST12-T01-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *A consumed-feedback receipt proves water/N limitations affected subsequent growth.*
    - *Daily, sparse, cold and corrected replay agree on the same interval semantics.*
    - *Every output resolves to the same authorized state head.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T02: Objective-specific longitudinal learning corpus
- **Priority**: `Target` | **Budget**: `80-140 hours` | **Dependencies**: `F21, F22, F25, F26, F36, T01` | **Lane**: `Target Capability Lane`

- [ ] **`ST12-T02-01`: [Engineering Infrastructure] 1. Define input tokens, masks, observation policy, ...**
  - **Target File**: [`../services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)
  - **Action**: [Engineering Infrastructure] 1. Define input tokens, masks, observation policy, labels and target-support eligibility per objective.
  - **Estimate**: 20–35 hours | **Prerequisites**: `F21, F22, F25, F26, F36, T01`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST12-T02-02`: [Engineering Infrastructure] 2. Build immutable manifests and partition plots/si...**
  - **Target File**: [`../services/agribrain/asmae_learn/dataset_builder.py`](../services/agribrain/asmae_learn/dataset_builder.py)
  - **Action**: [Engineering Infrastructure] 2. Build immutable manifests and partition plots/sites/seasons/instruments before fitting preprocessing.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST12-T02-01`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST12-T02-03`: [Empirical Milestone] 3. Permit partial and synthetic data for compatible object...**
  - **Target File**: [`../services/agribrain/asmae_learn/model_registry.py`](../services/agribrain/asmae_learn/model_registry.py)
  - **Action**: [Empirical Milestone] 3. Permit partial and synthetic data for compatible objectives and prohibit promotion to independent biological truth.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST12-T02-02`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST12-T02-04`: [Empirical Milestone] 4. Produce reproducible dataset/model artifacts with linea...**
  - **Target File**: [`../services/agribrain/world_model/historical_extractor.py`](../services/agribrain/world_model/historical_extractor.py)
  - **Action**: [Empirical Milestone] 4. Produce reproducible dataset/model artifacts with lineage, consent, licensing and calibration metadata.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST12-T02-03`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST12-T02-FA`: Package T02 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST12-T02-01 through ST12-T02-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *No target parent or post-cutoff input leaks into a predictive window.*
    - *Holdout partitions remain isolated across derived products.*
    - *A dataset snapshot can be regenerated byte-for-byte.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T12: Independent agronomic validation and reference field program
- **Priority**: `Target` | **Budget**: `80-140 engineering plus seasonal research hours` | **Dependencies**: `F12, F20, F24, F29, F36, T01` | **Lane**: `Target Capability Lane`

- [ ] **`ST12-T12-01`: 1. Predeclare targets, horizons, cohorts, metrics and applicability domains befo...**
  - **Target File**: [`../services/agribrain/ground_truth/registry.py`](../services/agribrain/ground_truth/registry.py)
  - **Action**: 1. Predeclare targets, horizons, cohorts, metrics and applicability domains before tuning.
  - **Estimate**: 20–35 hours | **Prerequisites**: `F12, F20, F24, F29, F36, T01`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST12-T12-02`: 2. Recruit independent reference plots with depth water, EC, delivery, canopy an...**
  - **Target File**: [`../services/agribrain/layer05_asmae/retrovalidation/engine.py`](../services/agribrain/layer05_asmae/retrovalidation/engine.py)
  - **Action**: 2. Recruit independent reference plots with depth water, EC, delivery, canopy and qualified crop/outcome observations.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST12-T12-01`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST12-T12-03`: [Empirical Milestone] 3. Compare simpler mechanistic/statistical baselines and i...**
  - **Target File**: [`../services/agribrain/mesia/learning/asmae_evaluator.py`](../services/agribrain/mesia/learning/asmae_evaluator.py)
  - **Action**: [Empirical Milestone] 3. Compare simpler mechanistic/statistical baselines and inspect calibration, missingness and measurement selection.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST12-T12-02`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST12-T12-04`: [Empirical Milestone] 4. Run safe discriminating studies separating water shorta...**
  - **Target File**: [`../services/agribrain/ground_truth/registry.py`](../services/agribrain/ground_truth/registry.py)
  - **Action**: [Empirical Milestone] 4. Run safe discriminating studies separating water shortage, salinity, hypoxia, hydraulic memory, delivery heterogeneity and biological alternatives.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST12-T12-03`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST12-T12-FA`: Package T12 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST12-T12-01 through ST12-T12-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Reference labels are independent of the model under evaluation.*
    - *Prospective results include uncertainty, sample size and negative outcomes.*
    - *Field evidence is reviewed against the declared target before any new capability is promoted.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 13: T03, T06 (280–520 hours)

#### Package T03: Multimodal foundation representation and local adaptation
- **Priority**: `Target` | **Budget**: `160-300 plus compute hours` | **Dependencies**: `T02, F27, F28` | **Lane**: `Target Capability Lane`

- [ ] **`ST13-T03-01`: [Engineering Infrastructure] 1. Start with small time-series and single-modality...**
  - **Target File**: [`../services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action**: [Engineering Infrastructure] 1. Start with small time-series and single-modality baselines on the frozen corpus.
  - **Estimate**: 40–75 hours | **Prerequisites**: `T02, F27, F28`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST13-T03-02`: [Engineering Infrastructure] 2. Train masked temporal/multimodal encoders with s...**
  - **Target File**: [`../services/agribrain/mesia/learning/neural_receiver.py`](../services/agribrain/mesia/learning/neural_receiver.py)
  - **Action**: [Engineering Infrastructure] 2. Train masked temporal/multimodal encoders with support and modality dropout.
  - **Estimate**: 40–75 hours | **Prerequisites**: `ST13-T03-01`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST13-T03-03`: [Empirical Milestone] 3. Add shared X/Z alignment, calibrated heads, OOD detecti...**
  - **Target File**: [`../services/agribrain/asmae_learn/model_registry.py`](../services/agribrain/asmae_learn/model_registry.py)
  - **Action**: [Empirical Milestone] 3. Add shared X/Z alignment, calibrated heads, OOD detection and local adapters.
  - **Estimate**: 40–75 hours | **Prerequisites**: `ST13-T03-02`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST13-T03-04`: [Empirical Milestone] 4. Evaluate transfer and rich-to-sparse distillation befor...**
  - **Target File**: [`../services/agribrain/layer1_fusion/eo_foundation_model.py`](../services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action**: [Empirical Milestone] 4. Evaluate transfer and rich-to-sparse distillation before federated deployment with secure aggregation and privacy accounting.
  - **Estimate**: 40–75 hours | **Prerequisites**: `ST13-T03-03`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST13-T03-FA`: Package T03 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST13-T03-01 through ST13-T03-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Representation improves at least one predeclared held-out task beyond smaller baselines.*
    - *Missing modalities have defined behavior and measured degradation.*
    - *Artifact, preprocessing, split and calibration versions reproduce the result.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T06: MESIA native acquisition, metrology and capability commissioning
- **Priority**: `Target` | **Budget**: `120-220 plus hardware/field work hours` | **Dependencies**: `F01, F05, F27, F28, F29, T02` | **Lane**: `Target Capability Lane`

- [ ] **`ST13-T06-01`: [Engineering Infrastructure] 1. Archive native complex CSI and available GNSS/RF...**
  - **Target File**: [`../services/agribrain/mesia/service.py`](../services/agribrain/mesia/service.py)
  - **Action**: [Engineering Infrastructure] 1. Archive native complex CSI and available GNSS/RF observations with instrument and two-clock timing.
  - **Estimate**: 30–55 hours | **Prerequisites**: `F01, F05, F27, F28, F29, T02`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST13-T06-02`: [Engineering Infrastructure] 2. Version topology, actual poses, antenna, firmwar...**
  - **Target File**: [`../services/agribrain/mesia/lanes/wifi/csi_extractor.py`](../services/agribrain/mesia/lanes/wifi/csi_extractor.py)
  - **Action**: [Engineering Infrastructure] 2. Version topology, actual poses, antenna, firmware, channel/band and calibration epochs.
  - **Estimate**: 30–55 hours | **Prerequisites**: `ST13-T06-01`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST13-T06-03`: [Empirical Milestone] 3. Qualify missingness, nuisance covariance and geometric ...**
  - **Target File**: [`../services/agribrain/mesia/behaviour/likelihood_engine.py`](../services/agribrain/mesia/behaviour/likelihood_engine.py)
  - **Action**: [Empirical Milestone] 3. Qualify missingness, nuisance covariance and geometric kernels against the canonical lattice.
  - **Estimate**: 30–55 hours | **Prerequisites**: `ST13-T06-02`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST13-T06-04`: [Empirical Milestone] 4. Progress discovery/configuration/commissioning/calibrat...**
  - **Target File**: [`../services/agribrain/mesia/assimilation/spatial_lattice.py`](../services/agribrain/mesia/assimilation/spatial_lattice.py)
  - **Action**: [Empirical Milestone] 4. Progress discovery/configuration/commissioning/calibration states and promote only validated individual capabilities.
  - **Estimate**: 30–55 hours | **Prerequisites**: `ST13-T06-03`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST13-T06-FA`: Package T06 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files) | **Prerequisites**: `ST13-T06-01 through ST13-T06-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Commodity hardware modalities remain optional and explicitly characterized.*
    - *Calibration drift does not become biology.*
    - *Native records and instrument state reproduce the same qualified likelihood.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 14: T04, T05 (240–440 hours)

#### Package T04: Hybrid world model with conservative multi-horizon rollout
- **Priority**: `Target` | **Budget**: `160-300 plus prospective data hours` | **Dependencies**: `T01, T02, T03, F23, F24, F12` | **Lane**: `Target Capability Lane`

- [ ] **`ST14-T04-01`: [Engineering Infrastructure] 1. Retain mechanistic conserved transitions and fit...**
  - **Target File**: [`../services/agribrain/world_model/contracts.py`](../services/agribrain/world_model/contracts.py)
  - **Action**: [Engineering Infrastructure] 1. Retain mechanistic conserved transitions and fit bounded residual dynamics conditioned on actual/scenario action.
  - **Estimate**: 40–75 hours | **Prerequisites**: `T01, T02, T03, F23, F24, F12`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST14-T04-02`: [Engineering Infrastructure] 2. Forecast explicit states, latent representation ...**
  - **Target File**: [`../services/agribrain/world_model/forecast_archive.py`](../services/agribrain/world_model/forecast_archive.py)
  - **Action**: [Engineering Infrastructure] 2. Forecast explicit states, latent representation and future observation distributions jointly.
  - **Estimate**: 40–75 hours | **Prerequisites**: `ST14-T04-01`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST14-T04-03`: [Empirical Milestone] 3. Test memory sufficiency against simpler Markov and hist...**
  - **Target File**: [`../services/agribrain/layer05_asmae/retrovalidation/future_projection.py`](../services/agribrain/layer05_asmae/retrovalidation/future_projection.py)
  - **Action**: [Empirical Milestone] 3. Test memory sufficiency against simpler Markov and history baselines.
  - **Estimate**: 40–75 hours | **Prerequisites**: `ST14-T04-02`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST14-T04-04`: [Empirical Milestone] 4. Evaluate paired intervention rollouts only where exposu...**
  - **Target File**: [`../services/agribrain/world_model/contracts.py`](../services/agribrain/world_model/contracts.py)
  - **Action**: [Empirical Milestone] 4. Evaluate paired intervention rollouts only where exposure, support and identification assumptions are valid.
  - **Estimate**: 40–75 hours | **Prerequisites**: `ST14-T04-03`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST14-T04-FA`: Package T04 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST14-T04-01 through ST14-T04-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Rollouts remain physically admissible with explicit residual ledgers.*
    - *Prospective multi-horizon skill exceeds stated persistence/mechanistic baselines on held-out domains.*
    - *Counterfactual output states its identifying assumptions and uncertainty.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T05: Decision economics from shared outcome distributions
- **Priority**: `Target` | **Budget**: `80-140 plus outcomes hours` | **Dependencies**: `F12, F13, F14, F15, T04` | **Lane**: `Target Capability Lane`

- [ ] **`ST14-T05-01`: [Engineering Infrastructure] 1. Add versioned price, labor, energy, water, input...**
  - **Target File**: [`../services/agribrain/layer7_planning/runner.py`](../services/agribrain/layer7_planning/runner.py)
  - **Action**: [Engineering Infrastructure] 1. Add versioned price, labor, energy, water, input, quality and transport assumptions.
  - **Estimate**: 20–35 hours | **Prerequisites**: `F12, F13, F14, F15, T04`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST14-T05-02`: [Engineering Infrastructure] 2. Derive margins and downside risk from joint outc...**
  - **Target File**: [`../services/agribrain/layer8_prescriptive/runner.py`](../services/agribrain/layer8_prescriptive/runner.py)
  - **Action**: [Engineering Infrastructure] 2. Derive margins and downside risk from joint outcome samples.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST14-T05-01`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST14-T05-03`: [Empirical Milestone] 3. Compare no-action, measurement and intervention policie...**
  - **Target File**: [`../services/agribrain/layer6_exec/outcomes/metrics.py`](../services/agribrain/layer6_exec/outcomes/metrics.py)
  - **Action**: [Empirical Milestone] 3. Compare no-action, measurement and intervention policies with immutable hard feasibility constraints.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST14-T05-02`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST14-T05-04`: [Empirical Milestone] 4. Evaluate value of information against transparent measu...**
  - **Target File**: [`../services/agribrain/layer7_planning/runner.py`](../services/agribrain/layer7_planning/runner.py)
  - **Action**: [Empirical Milestone] 4. Evaluate value of information against transparent measurement baselines and actual realized costs.
  - **Estimate**: 20–35 hours | **Prerequisites**: `ST14-T05-03`
  - **Verification**: Validate empirical protocol: out-of-domain holdouts, sample size and power calculation, independent biological reference plots, and explicit falsification thresholds.

- [ ] **`ST14-T05-FA`: Package T05 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST14-T05-01 through ST14-T05-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Currency, date, area and quantity units are explicit.*
    - *Missing price becomes an assumption with sensitivity rather than observed value.*
    - *Policy value uses independently observed outcomes and qualified causal assumptions.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 15: T08, T09 (300–540 hours)

#### Package T08: Finish AgriWise operational records and financial workflows
- **Priority**: `Target` | **Budget**: `180-320 hours` | **Dependencies**: `F32, F33, F34, F09` | **Lane**: `Target Capability Lane`

- [ ] **`ST15-T08-01`: [Engineering Infrastructure] 1. Complete farm/cycle/rotation history with delega...**
  - **Target File**: [`../prisma/schema.prisma`](../prisma/schema.prisma)
  - **Action**: [Engineering Infrastructure] 1. Complete farm/cycle/rotation history with delegated ownership and scoped task resources.
  - **Estimate**: 45–80 hours | **Prerequisites**: `F32, F33, F34, F09`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST15-T08-02`: [Engineering Infrastructure] 2. Add stock ledger, equipment use/maintenance and ...**
  - **Target File**: [`../src/app/api/inputs/route.ts`](../src/app/api/inputs/route.ts)
  - **Action**: [Engineering Infrastructure] 2. Add stock ledger, equipment use/maintenance and linked actual exposures.
  - **Estimate**: 45–80 hours | **Prerequisites**: `ST15-T08-01`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST15-T08-03`: 3. Add typed livestock, market offers/orders/quality/storage/transport workflows...**
  - **Target File**: [`../src/app/api/cycles/[id]/tasks/route.ts`](../src/app/api/cycles/[id]/tasks/route.ts)
  - **Action**: 3. Add typed livestock, market offers/orders/quality/storage/transport workflows as proposed new modules.
  - **Estimate**: 45–80 hours | **Prerequisites**: `ST15-T08-02`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST15-T08-04`: 4. Implement budget, costs and realized versus scenario economics without double...**
  - **Target File**: [`../prisma/schema.prisma`](../prisma/schema.prisma)
  - **Action**: 4. Implement budget, costs and realized versus scenario economics without double counting.
  - **Estimate**: 45–80 hours | **Prerequisites**: `ST15-T08-03`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST15-T08-FA`: Package T08 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST15-T08-01 through ST15-T08-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Each workflow has persisted authorized records and error recovery.*
    - *Livestock events and costs use their own domain schema.*
    - *Stock/order/financial totals reconcile across cancellation, retry and correction.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T09: Unify language, voice, map and offline product projections
- **Priority**: `Target` | **Budget**: `120-220 hours` | **Dependencies**: `F30, F31, F32, T01` | **Lane**: `Target Capability Lane`

- [ ] **`ST15-T09-01`: [Engineering Infrastructure] 1. Resolve one intent to one canonical visible resp...**
  - **Target File**: [`../src/app/api/agribrain/intent/route.ts`](../src/app/api/agribrain/intent/route.ts)
  - **Action**: [Engineering Infrastructure] 1. Resolve one intent to one canonical visible response and typed claims.
  - **Estimate**: 30–55 hours | **Prerequisites**: `F30, F31, F32, T01`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST15-T09-02`: [Engineering Infrastructure] 2. Keep maps, numbers and explanations linked to th...**
  - **Target File**: [`../src/lib/agribrain/surface-contract.ts`](../src/lib/agribrain/surface-contract.ts)
  - **Action**: [Engineering Infrastructure] 2. Keep maps, numbers and explanations linked to the same state/support, including effective resolution.
  - **Estimate**: 30–55 hours | **Prerequisites**: `ST15-T09-01`
  - **Verification**: Validate Next.js/TypeScript clean build (`tsc --noEmit`), Prisma migration schema consistency, 503 HTTP status on DB outage (preserving authentic zeros), and zero client bundle errors.

- [ ] **`ST15-T09-03`: 3. Preserve values, negation and prohibitions across Arabic/French/voice and acc...**
  - **Target File**: [`../services/agribrain/layer9_interface/runner.py`](../services/agribrain/layer9_interface/runner.py)
  - **Action**: 3. Preserve values, negation and prohibitions across Arabic/French/voice and accessibility rendering.
  - **Estimate**: 30–55 hours | **Prerequisites**: `ST15-T09-02`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST15-T09-04`: 4. Implement offline pending events with conflict resolution and visibly stale d...**
  - **Target File**: [`../services/agribrain/layer10_sire/runner.py`](../services/agribrain/layer10_sire/runner.py)
  - **Action**: 4. Implement offline pending events with conflict resolution and visibly stale decision cutoffs.
  - **Estimate**: 30–55 hours | **Prerequisites**: `ST15-T09-03`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST15-T09-FA`: Package T09 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files) | **Prerequisites**: `ST15-T09-01 through ST15-T09-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Every visible response resolves to one canonical artifact.*
    - *UI and translation do not manufacture numerical science.*
    - *Offline actions reconcile without retroactively changing what a user knew.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 16: T07, T10 (360–660 hours)

#### Package T07: Omega scientific investigation loop
- **Priority**: `Target` | **Budget**: `240-440 plus experiments hours` | **Dependencies**: `F12, F21, F36, T01, T02, T04` | **Lane**: `Target Capability Lane`

- [ ] **`ST16-T07-01`: [O1 Case & Epistemic History] Define ScientificCase schema, immutable evidence cutoffs, branching alternatives...**
  - **Target File**: [`../services/agribrain/world_model/scientific_case.py`](../services/agribrain/world_model/scientific_case.py)
  - **Action**: Define ScientificCase schema, immutable evidence cutoffs, branching alternatives, and replayable theory versions.
  - **Estimate**: 20–36 hours | **Requirements**: `AB-OMG-001, AB-OMG-002` | **Prerequisites**: `Stage 15 (ST15-T06-FA, ST15-T08-FA, ST15-T10-FA)`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-02`: [O2 Surprise & Candidate-Space Inadequacy] Compare instrument faults, missing management, domain/parameter shifts, and mode...**
  - **Target File**: [`../services/agribrain/world_model/surprise_engine.py`](../services/agribrain/world_model/surprise_engine.py)
  - **Action**: Compare instrument faults, missing management, domain/parameter shifts, and model inadequacy; preserve unknown mass.
  - **Estimate**: 20–36 hours | **Requirements**: `AB-OMG-003, AB-OMG-004` | **Prerequisites**: `ST16-T07-01`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-03`: [O3 Bayesian Inference Laboratory] Implement priors, likelihoods, and inference adapters; verify posterior-predicti...**
  - **Target File**: [`../services/agribrain/world_model/bayesian_lab.py`](../services/agribrain/world_model/bayesian_lab.py)
  - **Action**: Implement priors, likelihoods, and inference adapters; verify posterior-predictive convergence and sensitivity.
  - **Estimate**: 24–44 hours | **Requirements**: `AB-OMG-005` | **Prerequisites**: `ST16-T07-01, ST16-T07-02`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-04`: [O4 BEL & Simulation Adequacy] Simulator prior, observation compression, and QoI; verify simulator adequacy and...**
  - **Target File**: [`../services/agribrain/world_model/bel_simulator.py`](../services/agribrain/world_model/bel_simulator.py)
  - **Action**: Simulator prior, observation compression, and QoI; verify simulator adequacy and calibration without role confusion.
  - **Estimate**: 24–44 hours | **Requirements**: `AB-OMG-006` | **Prerequisites**: `ST16-T07-02, ST16-T07-03`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-05`: [O5 Causal Discovery vs Identification] Separate candidate graph/lag discovery from causal estimands, identification ass...**
  - **Target File**: [`../services/agribrain/world_model/causal_discovery.py`](../services/agribrain/world_model/causal_discovery.py)
  - **Action**: Separate candidate graph/lag discovery from causal estimands, identification assumptions, positivity, and sensitivity.
  - **Estimate**: 24–44 hours | **Requirements**: `AB-OMG-007, AB-OMG-008` | **Prerequisites**: `ST16-T07-01, ST16-T07-03`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-06`: [O6 Latents & Equation Discovery] Compare equivalent latent representations; discover candidate symbolic equations...**
  - **Target File**: [`../services/agribrain/world_model/symbolic_discovery.py`](../services/agribrain/world_model/symbolic_discovery.py)
  - **Action**: Compare equivalent latent representations; discover candidate symbolic equations with physical conservation holdouts.
  - **Estimate**: 24–44 hours | **Requirements**: `AB-OMG-009, AB-OMG-012` | **Prerequisites**: `ST16-T07-05`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-07`: [O7 Value of Information & Policy] Candidate measurement set, inclusion rules, acquisition cost, and information va...**
  - **Target File**: [`../services/agribrain/world_model/value_of_information.py`](../services/agribrain/world_model/value_of_information.py)
  - **Action**: Candidate measurement set, inclusion rules, acquisition cost, and information value; track performative policy history.
  - **Estimate**: 20–36 hours | **Requirements**: `AB-OMG-010, AB-OMG-011` | **Prerequisites**: `ST16-T07-03, ST16-T07-05`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-08`: [O8 Discriminating Experiments] Design experiments discriminating between competing alternatives; specify power,...**
  - **Target File**: [`../services/agribrain/world_model/experiment_designer.py`](../services/agribrain/world_model/experiment_designer.py)
  - **Action**: Design experiments discriminating between competing alternatives; specify power, stopping rules, and outcome collection.
  - **Estimate**: 24–44 hours | **Requirements**: `AB-OMG-013` | **Prerequisites**: `ST16-T07-02, ST16-T07-07`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-09`: [O9 Falsification & Replication] Predeclared falsifiers, negative/inconclusive outcomes, independent replication,...**
  - **Target File**: [`../services/agribrain/world_model/falsification_engine.py`](../services/agribrain/world_model/falsification_engine.py)
  - **Action**: Predeclared falsifiers, negative/inconclusive outcomes, independent replication, and scoped transport assumptions.
  - **Estimate**: 20–36 hours | **Requirements**: `AB-OMG-014, AB-OMG-015` | **Prerequisites**: `ST16-T07-08`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-10`: [O10 Scientific Memory & Epistemic Value] Versioned scientific knowledge including revocation; report ambiguity reduction ...**
  - **Target File**: [`../services/agribrain/world_model/scientific_memory.py`](../services/agribrain/world_model/scientific_memory.py)
  - **Action**: Versioned scientific knowledge including revocation; report ambiguity reduction and replication separately from loss.
  - **Estimate**: 20–36 hours | **Requirements**: `AB-OMG-016, AB-OMG-017` | **Prerequisites**: `ST16-T07-09`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-11`: [O11 Capability Integration & Promotion] Integrate Omega investigation loop with diagnostic promotion; ensure promotion d...**
  - **Target File**: [`../services/agribrain/diagnostic_integration/promotion_service.py`](../services/agribrain/diagnostic_integration/promotion_service.py)
  - **Action**: Integrate Omega investigation loop with diagnostic promotion; ensure promotion does not replace scientific discovery.
  - **Estimate**: 20–40 hours | **Requirements**: `AB-OMG-018` | **Prerequisites**: `ST16-T07-10`
  - **Verification**: Validate discriminating agricultural hypothesis cases, Bayesian posterior-predictive convergence, causal identification assumptions, and independent falsification/replication.

- [ ] **`ST16-T07-FA`: Package T07 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files) | **Prerequisites**: `ST16-T07-01 through ST16-T07-11`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *A case follows surprise to competing explanations, discriminating prediction, experiment and replication.*
    - *A latent or symbolic equation remains a candidate until appropriate evidence separates alternatives.*
    - *Scientific success includes reduced ambiguity and negative findings, not only promoted claims.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T10: Institutional aggregation and territorial world-model extension
- **Priority**: `Target` | **Budget**: `120-220 plus regional data hours` | **Dependencies**: `T04, T05, T08, T09` | **Lane**: `Target Capability Lane`

- [ ] **`ST16-T10-01`: [Engineering Infrastructure] 1. Authorize aggregation cohorts and suppress poten...**
  - **Target File**: [`../prisma/schema.prisma`](../prisma/schema.prisma)
  - **Action**: [Engineering Infrastructure] 1. Authorize aggregation cohorts and suppress potentially identifying small groups.
  - **Estimate**: 30–55 hours | **Prerequisites**: `T04, T05, T08, T09`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST16-T10-02`: [Engineering Infrastructure] 2. Model supply, water, market and environmental in...**
  - **Target File**: [`../services/agribrain/world_model/contracts.py`](../services/agribrain/world_model/contracts.py)
  - **Action**: [Engineering Infrastructure] 2. Model supply, water, market and environmental interactions hierarchically with uncertainty.
  - **Estimate**: 30–55 hours | **Prerequisites**: `ST16-T10-01`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST16-T10-03`: 3. Evaluate policy and resource scenarios against independent regional outcomes....**
  - **Target File**: [`../prisma/schema.prisma`](../prisma/schema.prisma)
  - **Action**: 3. Evaluate policy and resource scenarios against independent regional outcomes.
  - **Estimate**: 30–55 hours | **Prerequisites**: `ST16-T10-02`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST16-T10-04`: 4. Version sovereign deployment, licensing, egress and review/appeal pathways fo...**
  - **Target File**: [`../services/agribrain/world_model/contracts.py`](../services/agribrain/world_model/contracts.py)
  - **Action**: 4. Version sovereign deployment, licensing, egress and review/appeal pathways for high-impact use.
  - **Estimate**: 30–55 hours | **Prerequisites**: `ST16-T10-03`
  - **Verification**: Validate independent proper scores, out-of-domain holdouts, memory sufficiency, scientific falsification criteria, and reference field protocol standards.

- [ ] **`ST16-T10-FA`: Package T10 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files) | **Prerequisites**: `ST16-T10-01 through ST16-T10-04`
  - **Action**: Run controlled local regression probe on production symbols; verify criteria:
    - *Regional summaries preserve uncertainty and authorized cohort scope.*
    - *Policy scenarios are separated from observed effects.*
    - *Territorial capability is evaluated independently rather than inherited from a plot metric.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

## 4. Verification & Proof Evidence Ledger

| Ticket ID | Completed Commit SHA | Local Probe Receipt / Evidence | Reviewer | Sign-off Date |
|---|---|---|---|:---:|
| `ST00-F37-ES01` | Pending | Import verification passes under clean Python 3.12 | Pending | Pending |
| `ST00-F37-FA` | Pending | All F37 target modules cold-import without warning | Pending | Pending |
| `ST01-F01-01` | Pending | Finite float validation rejects NaN and Inf | Pending | Pending |
| `ST01-F01-FA` | Pending | Observation packets serialize legitimate zeros faithfully | Pending | Pending |

# AgriBrain Work Packages Task List & Engineering Ticket Register
**Document Date**: 7 October 2026  **Program Scope**: 52 Work Packages (F01–F40, T01–T12) across 17 Execution Stages  **Source Baseline**: Main at `26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`  **Schedule Authority**: [`plan/AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md`](file:///c:/Users/E-C/Desktop/agriwise/plan/AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md)  **Technical Specifications**: [`plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md`](file:///c:/Users/E-C/Desktop/agriwise/plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md)
---
## 1. Operating Guide & Ticket Lifecycle
This document provides an atomic, reviewable work breakdown structure (WBS) for engineering teams. Every package is decomposed into actionable tickets with explicit prerequisites, target files, code actions, deliverables, and acceptance verification checkboxes.
### Ticket Naming Convention
- `ST[stage_idx]-[pkg_id]-[task_idx]`: Standard full package delivery task (e.g., `ST00-F37-01`, `ST04-F11-02`).
- `ST[stage_idx]-[pkg_id]-ES[task_idx]`: Early-slice task for immediate cold-start unblock (e.g., `ST00-F35-ES01`, `ST00-F39-ES01`).
- `Status Checkbox`: `[ ]` Pending / Ready, `[-]` In Progress, `[x]` Completed and Verified.

### Master Execution Dashboard (17 Stages)

| Stage | Packages in Execution Order | Scope / Focus | Hours Budget | Status |
|:---:|---|---|:---:|:---:|
| **Stage 00** | F37 | Foundation / Core Delivery | 24–48 hrs | `[ ] Ready` |
| **Stage 01** | F01, F02 | Foundation / Core Delivery | 48–80 hrs | `[ ] Ready` |
| **Stage 02** | F03, F04 | Foundation / Core Delivery | 36–60 hrs | `[ ] Ready` |
| **Stage 03** | F06, F07, F08, F09, F39 | Foundation / Core Delivery | 148–252 hrs | `[ ] Ready` |
| **Stage 04** | F05, F10, F11, F12 | Foundation / Core Delivery | 100–176 hrs | `[ ] Ready` |
| **Stage 05** | F13, F14, F15 | Foundation / Core Delivery | 68–124 hrs | `[ ] Ready` |
| **Stage 06** | F16, F17, F18, F19 | Foundation / Core Delivery | 88–148 hrs | `[ ] Ready` |
| **Stage 07** | F20, F34 | Foundation / Core Delivery | 64–104 hrs | `[ ] Ready` |
| **Stage 08** | F21, F22, F23, F24 | Foundation / Core Delivery | 88–144 hrs | `[ ] Ready` |
| **Stage 09** | F25, F26, F27, F28, F29 | Foundation / Core Delivery | 140–232 hrs | `[ ] Ready` |
| **Stage 10** | F30, F31, F32, F33, F38, F40 | Foundation / Core Delivery | 172–296 hrs | `[ ] Ready` |
| **Stage 11** | F35, F36, T11 | Foundation / Core Delivery | 168–296 hrs | `[ ] Ready` |
| **Stage 12** | T01, T02, T12 | Foundation / Core Delivery | 240–420 hrs | `[ ] Ready` |
| **Stage 13** | T03, T06 | Foundation / Core Delivery | 280–520 hrs | `[ ] Ready` |
| **Stage 14** | T04, T05 | Foundation / Core Delivery | 240–440 hrs | `[ ] Ready` |
| **Stage 15** | T08, T09 | Foundation / Core Delivery | 300–540 hrs | `[ ] Ready` |
| **Stage 16** | T07, T10 | Foundation / Core Delivery | 360–660 hrs | `[ ] Ready` |
| **TOTAL** | **52 Packages** | **Full Remediation & Extension Program** | **2,564–4,540 hrs** | **Planned** |

---
## 2. Exhaustive Engineering Task Checklist (Stages 0 to 16)

### Stage 00: F37 (24–48 hours)

#### Package F37: Repair optional imports and establish one Python package identity
- **Priority**: `P1` | **Estimate**: `24-48 hours` | **Dependencies**: `none` | **R3 Requirements**: `AB-ARC-004, AB-ARC-008, AB-DAT-002`
- **Note on Early Slice**: Early scope `24-48`. Full acceptance requires ``.

- [ ] **`ST00-F37-01`: 1. Import GaussianMixture from sklearn.mixture and identify actual consumers of ...**
  - **Target File**: [`services/agribrain/layer1_fusion/segmentation.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/segmentation.py)
  - **Action Required**: 1. Import GaussianMixture from sklearn.mixture and identify actual consumers of the legacy segmentation module.
  - **Estimate**: 6–12 hours | **Prerequisites**: none
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST00-F37-02`: 2. Isolate optional drivers and model backends behind explicit capability loadin...**
  - **Target File**: [`services/agribrain/layer1_fusion/engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/engine.py)
  - **Action Required**: 2. Isolate optional drivers and model backends behind explicit capability loading, retaining simulation as a qualified mode.
  - **Estimate**: 6–12 hours | **Prerequisites**: none
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST00-F37-03`: 3. Select one installed package namespace and migrate entrypoints/imports cohere...**
  - **Target File**: [`services/agribrain/drone_control/dispatcher.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/drone_control/dispatcher.py)
  - **Action Required**: 3. Select one installed package namespace and migrate entrypoints/imports coherently instead of mechanically prefixing every import.
  - **Estimate**: 6–12 hours | **Prerequisites**: none
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST00-F37-04`: 4. Verify service, worker, CLI and public module startup in fresh processes with...**
  - **Target File**: [`services/agribrain/drone_mission/__init__.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/drone_mission/__init__.py)
  - **Action Required**: 4. Verify service, worker, CLI and public module startup in fresh processes with declared dependency extras.
  - **Estimate**: 6–12 hours | **Prerequisites**: none
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST00-F37-FA`: Package F37 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (6 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Cold imports work for each supported entrypoint without incidental prior imports.*
    - *Qualified and internal callers share enum/dataclass identities.*
    - *An unavailable optional backend disables its capability without breaking unrelated science.*
    - *The two successfully loaded cycles are not treated as demonstrated circular-import failures.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 01: F01, F02 (48–80 hours)

#### Package F01: Qualify provenance and numeric evidence at every admission boundary
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `none` | **R3 Requirements**: `AB-DAT-005, AB-DAT-006, AB-ARC-005, AB-ARC-006`

- [ ] **`ST01-F01-01`: 1. Review PR #1 against source consumers and preserve its corrected zero and mis...**
  - **Target File**: [`services/agribrain/layer0/observation_packet.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/observation_packet.py)
  - **Action Required**: 1. Review PR #1 against source consumers and preserve its corrected zero and missingness semantics.
  - **Estimate**: 6–10 hours | **Prerequisites**: none
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST01-F01-02`: 2. Make accepted/rejected components explicit before authority or solver selecti...**
  - **Target File**: [`services/agribrain/layer0/wrappers.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/wrappers.py)
  - **Action Required**: 2. Make accepted/rejected components explicit before authority or solver selection.
  - **Estimate**: 6–10 hours | **Prerequisites**: none
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST01-F01-03`: 3. Carry source roles through all typed and dictionary adapters without allowing...**
  - **Target File**: [`services/agribrain/scientific_contracts/observation.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/scientific_contracts/observation.py)
  - **Action Required**: 3. Carry source roles through all typed and dictionary adapters without allowing caller promotion.
  - **Estimate**: 6–10 hours | **Prerequisites**: none
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST01-F01-04`: 4. Apply the same qualification to weather, RF, crop observations and training a...**
  - **Target File**: [`services/agribrain/layer3_water/assimilation/water_state_assimilator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/assimilation/water_state_assimilator.py)
  - **Action Required**: 4. Apply the same qualification to weather, RF, crop observations and training admission, with migration of ambiguous legacy records.
  - **Estimate**: 6–10 hours | **Prerequisites**: none
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST01-F01-FA`: Package F01 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *NaN, infinity, booleans and malformed numeric values cannot alter state or training weight.*
    - *Legitimate zero survives serialization and round trips.*
    - *Authority and accepted counts follow actual admitted components.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F02: Enforce observation time and availability at issuance
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01` | **R3 Requirements**: `AB-DAT-004, AB-DAT-014, AB-ML-008`

- [ ] **`ST01-F02-01`: 1. Retain the PR explicit-cutoff fix and require both observation and availabili...**
  - **Target File**: [`services/agribrain/layer05_asmae/resilient_posterior.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/resilient_posterior.py)
  - **Action Required**: 1. Retain the PR explicit-cutoff fix and require both observation and availability provenance for prospective measurements.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST01-F02-02`: 2. Define typed timing for measurements, priors, forecasts and management scenar...**
  - **Target File**: [`services/agribrain/layer0/temporal_evidence.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/temporal_evidence.py)
  - **Action Required**: 2. Define typed timing for measurements, priors, forecasts and management scenarios.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST01-F02-03`: 3. Propagate the decision cutoff through each layer and reject records with unre...**
  - **Target File**: [`services/agribrain/world_model/historical_extractor.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/historical_extractor.py)
  - **Action Required**: 3. Propagate the decision cutoff through each layer and reject records with unresolved eligibility.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST01-F02-04`: 4. Record every excluded revision and force historical replays to use the archiv...**
  - **Target File**: [`services/agribrain/layer05_asmae/resilient_posterior.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/resilient_posterior.py)
  - **Action Required**: 4. Record every excluded revision and force historical replays to use the archived knowledge view.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST01-F02-FA`: Package F02 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Late-arriving measurements and revised weather are excluded from earlier issuance.*
    - *Earlier-issued future forecasts remain eligible as scenarios.*
    - *Replay identifies exactly which input versions were available.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 02: F03, F04 (36–60 hours)

#### Package F03: Publish the fluxes actually integrated and separate analysis increments
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01` | **R3 Requirements**: `AB-AGR-004, AB-AGR-005, AB-AGR-008`

- [ ] **`ST02-F03-01`: 1. Return a transition receipt containing bounded actual evaporation, transpirat...**
  - **Target File**: [`services/agribrain/layer3_water/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/runner.py)
  - **Action Required**: 1. Return a transition receipt containing bounded actual evaporation, transpiration, drainage, infiltration and initial/final storage.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST02-F03-02`: 2. Publish that receipt as realized interval flux and expose posterior demand as...**
  - **Target File**: [`services/agribrain/layer3_water/soil/layered_water_balance.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/soil/layered_water_balance.py)
  - **Action Required**: 2. Publish that receipt as realized interval flux and expose posterior demand as a separate next-interval diagnostic.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST02-F03-03`: 3. Return an analysis receipt with storage increment, covariance change and boun...**
  - **Target File**: [`services/agribrain/layer3_water/contracts/water_state.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/contracts/water_state.py)
  - **Action Required**: 3. Return an analysis receipt with storage increment, covariance change and bound corrections.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST02-F03-04`: 4. Calculate closure from the serialized state and receipt rather than an intern...**
  - **Target File**: [`services/agribrain/layer3_water/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/runner.py)
  - **Action Required**: 4. Calculate closure from the serialized state and receipt rather than an internal pre-rounding ledger.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST02-F03-FA`: Package F03 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Integrated and published realized fluxes agree.*
    - *Physical closure includes bounded extraction and quantization, while analysis increments are explicit.*
    - *Assimilation cannot retroactively rewrite the water used in the preceding interval.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F04: Validate soil geometry and hydraulic parameter vectors
- **Priority**: `P0` | **Estimate**: `12-20 hours` | **Dependencies**: `F01` | **R3 Requirements**: `AB-AGR-003, AB-DAT-007`

- [ ] **`ST02-F04-01`: 1. Require a nonempty strictly increasing finite positive depth vector....**
  - **Target File**: [`services/agribrain/layer3_water/contracts/state_factory.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/contracts/state_factory.py)
  - **Action Required**: 1. Require a nonempty strictly increasing finite positive depth vector.
  - **Estimate**: 3–5 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST02-F04-02`: 2. Validate the length and physical domain of every retention, conductivity and ...**
  - **Target File**: [`services/agribrain/layer3_water/soil/layered_water_balance.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/soil/layered_water_balance.py)
  - **Action Required**: 2. Validate the length and physical domain of every retention, conductivity and van Genuchten vector.
  - **Estimate**: 3–5 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST02-F04-03`: 3. Reject degenerate saturation/residual intervals and inconsistent units before...**
  - **Target File**: [`services/agribrain/layer3_water/contracts/state_factory.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/contracts/state_factory.py)
  - **Action Required**: 3. Reject degenerate saturation/residual intervals and inconsistent units before computing suction.
  - **Estimate**: 3–5 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST02-F04-04`: 4. Document parameter provenance and distinguish measured values from texture pr...**
  - **Target File**: [`services/agribrain/layer3_water/soil/layered_water_balance.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/soil/layered_water_balance.py)
  - **Action Required**: 4. Document parameter provenance and distinguish measured values from texture priors.
  - **Estimate**: 3–5 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST02-F04-FA`: Package F04 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Nonmonotonic, repeated, zero or nonfinite depths are rejected.*
    - *Negative conductivity and invalid n or alpha cannot enter the solver.*
    - *Valid heterogeneous profiles retain their parameters and storage.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 03: F06, F07, F08, F09, F39 (148–252 hours)

#### Package F06: Stop substituting another date at the weather endpoint
- **Priority**: `P0` | **Estimate**: `12-20 hours` | **Dependencies**: `F02` | **R3 Requirements**: `AB-DAT-004, AB-DAT-005, AB-AGR-007, AB-AGR-013`

- [ ] **`ST03-F06-01`: 1. Remove arbitrary-record selection at the endpoint....**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 1. Remove arbitrary-record selection at the endpoint.
  - **Estimate**: 3–5 hours | **Prerequisites**: F02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F06-02`: 2. Resolve forcing by exact interval and declared timezone....**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 2. Resolve forcing by exact interval and declared timezone.
  - **Estimate**: 3–5 hours | **Prerequisites**: F02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F06-03`: 3. Route missing target forcing through an explicit prior or missing-data result...**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 3. Route missing target forcing through an explicit prior or missing-data result with uncertainty and source role.
  - **Estimate**: 3–5 hours | **Prerequisites**: F02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F06-04`: 4. Apply the same policy to intermediate gaps and keep zero rainfall distinct fr...**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 4. Apply the same policy to intermediate gaps and keep zero rainfall distinct from unobserved rainfall.
  - **Estimate**: 3–5 hours | **Prerequisites**: F02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F06-FA`: Package F06 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *No future record supplies a historical daily forcing.*
    - *Missing rainfall is visible and cannot become observed zero.*
    - *Daily and sparse executions use identical qualified interval inputs.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F07: Remove future canopy fallback and restore evaporation memory
- **Priority**: `P1` | **Estimate**: `24-40 hours` | **Dependencies**: `F03, F04, F06` | **R3 Requirements**: `AB-AGR-006, AB-AGR-007, AB-AGR-008`

- [ ] **`ST03-F07-01`: 1. Resolve historical canopy only from records eligible for each step and label ...**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 1. Resolve historical canopy only from records eligible for each step and label persisted priors.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F06
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F07-02`: 2. Remove endpoint canopy fallback into earlier days unless it is explicitly a s...**
  - **Target File**: [`services/agribrain/layer3_water/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/runner.py)
  - **Action Required**: 2. Remove endpoint canopy fallback into earlier days unless it is explicitly a scenario reconstruction.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F06
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F07-03`: 3. Restore the previous evaporation state and wetted fraction into each step....**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 3. Restore the previous evaporation state and wetted fraction into each step.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F06
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F07-04`: 4. Derive surface storage from actual layer thickness and propagate method-speci...**
  - **Target File**: [`services/agribrain/layer3_water/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/runner.py)
  - **Action Required**: 4. Derive surface storage from actual layer thickness and propagate method-specific wetting.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F06
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F07-FA`: Package F07 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Earlier steps never consume later observed canopy.*
    - *A dry sequence advances evaporation memory across restart and sparse replay.*
    - *Changing top-layer thickness changes surface storage consistently.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F08: Make trajectory invalidation include parameters and predecessor content
- **Priority**: `P1` | **Estimate**: `24-40 hours` | **Dependencies**: `F03, F04, F06` | **R3 Requirements**: `AB-DAT-011, AB-DAT-012, AB-AGR-007`

- [ ] **`ST03-F08-01`: 1. Replace repr and rounded scalar fingerprints with canonical content digests....**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 1. Replace repr and rounded scalar fingerprints with canonical content digests.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F06
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F08-02`: 2. Include full profile, crop/geometry epoch, solver version, observation payloa...**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 2. Include full profile, crop/geometry epoch, solver version, observation payload and predecessor digest.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F06
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F08-03`: 3. Invalidate from the earliest changed transition for parameter corrections as ...**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 3. Invalidate from the earliest changed transition for parameter corrections as well as weather changes.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F06
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F08-04`: 4. Preserve previously issued forecasts while creating a separate corrected retr...**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 4. Preserve previously issued forecasts while creating a separate corrected retrospective trajectory.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F06
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F08-FA`: Package F08 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Identical moisture with different conductivity or retention cannot share a trajectory key.*
    - *Parameter changes recompute affected predecessors and descendants.*
    - *Repeated identical requests are idempotent.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F09: Persist coupled state with scoped concurrency and restart recovery
- **Priority**: `P1` | **Estimate**: `48-80 hours` | **Dependencies**: `F02, F03, F08` | **R3 Requirements**: `AB-DAT-003, AB-DAT-012, AB-DAT-013, AB-ARC-008, AB-AGR-006`

- [ ] **`ST03-F09-01`: 1. Move parameter epochs, action versions and hydraulic checkpoints to the canon...**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 1. Move parameter epochs, action versions and hydraulic checkpoints to the canonical scoped store.
  - **Estimate**: 12–20 hours | **Prerequisites**: F02, F03, F08
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F09-02`: 2. Use tenant, plot, cycle, geometry and namespace in identities....**
  - **Target File**: [`services/agribrain/world_model/canonical_worldline.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/canonical_worldline.py)
  - **Action Required**: 2. Use tenant, plot, cycle, geometry and namespace in identities.
  - **Estimate**: 12–20 hours | **Prerequisites**: F02, F03, F08
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F09-03`: 3. Commit transition and analysis receipts with compare-and-swap on the predeces...**
  - **Target File**: [`services/agribrain/layer05_asmae/history/worldline_service.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/history/worldline_service.py)
  - **Action Required**: 3. Commit transition and analysis receipts with compare-and-swap on the predecessor head.
  - **Estimate**: 12–20 hours | **Prerequisites**: F02, F03, F08
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F09-04`: 4. Recover from committed checkpoints and replay appended corrections under a fe...**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 4. Recover from committed checkpoints and replay appended corrections under a fenced lease.
  - **Estimate**: 12–20 hours | **Prerequisites**: F02, F03, F08
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F09-FA`: Package F09 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Cold restart equals warm replay.*
    - *Two workers cannot publish different successors for one head.*
    - *Cancellation, withdrawal and late correction survive restart and replica changes.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F39: Make telemetry persistence and replay protection concurrency safe
- **Priority**: `P0` | **Estimate**: `40-72 hours` | **Dependencies**: `F01, F09` | **R3 Requirements**: `AB-DAT-001, AB-DAT-003, AB-DAT-011, AB-DAT-013, AB-ARC-008, AB-ARC-009`
- **Note on Early Slice**: Early scope `Reproduce and remove nonce lost updates at the actual admission boundary`. Full acceptance requires `F01/F09; full shared replay and telemetry persistence stage 3`.

- [ ] **`ST03-F39-01`: 1. Combine nonce eligibility and registration in a shared atomic conditional ins...**
  - **Target File**: [`services/agribrain/sensor_runtime/security.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/sensor_runtime/security.py)
  - **Action Required**: 1. Combine nonce eligibility and registration in a shared atomic conditional insert with scoped unique keys and retention derived from the accepted replay window.
  - **Estimate**: 6–12 hours | **Prerequisites**: F01, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F39-02`: 2. Persist immutable raw/normalized telemetry durably with message idempotency b...**
  - **Target File**: [`services/agribrain/sensor_runtime/storage.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/sensor_runtime/storage.py)
  - **Action Required**: 2. Persist immutable raw/normalized telemetry durably with message idempotency before making it visible.
  - **Estimate**: 6–12 hours | **Prerequisites**: F01, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F39-03`: 3. Keep memory caches bounded by byte/cardinality budgets and expose retention/e...**
  - **Target File**: [`services/agribrain/app/main.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/app/main.py)
  - **Action Required**: 3. Keep memory caches bounded by byte/cardinality budgets and expose retention/eviction metrics.
  - **Estimate**: 6–12 hours | **Prerequisites**: F01, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F39-04`: 4. Use safe lock striping or lifecycle-managed keyed locks that cannot be evicte...**
  - **Target File**: [`services/agribrain/visual_sources/tile_proxy.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/visual_sources/tile_proxy.py)
  - **Action Required**: 4. Use safe lock striping or lifecycle-managed keyed locks that cannot be evicted while held or awaited.
  - **Estimate**: 6–12 hours | **Prerequisites**: F01, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F39-05`: 5. Bound rate-limiter identity retention without permitting an eviction/reset by...**
  - **Target File**: [`services/agribrain/sensor_runtime/security.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/sensor_runtime/security.py)
  - **Action Required**: 5. Bound rate-limiter identity retention without permitting an eviction/reset bypass across replicas.
  - **Estimate**: 6–12 hours | **Prerequisites**: F01, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F39-06`: 6. Key bounding-box caches by tenant and geometry epoch with explicit invalidati...**
  - **Target File**: [`services/agribrain/sensor_runtime/storage.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/sensor_runtime/storage.py)
  - **Action Required**: 6. Key bounding-box caches by tenant and geometry epoch with explicit invalidation.
  - **Estimate**: 6–12 hours | **Prerequisites**: F01, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST03-F39-FA`: Package F39 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Two simultaneous unique nonces remain registered and the same nonce is accepted at most once.*
    - *Replay rejection survives restart and concurrent replicas.*
    - *Cache pressure does not erase the durable evidence corpus.*
    - *High-cardinality keys stay within declared budgets without duplicating locks for one active key.*
    - *Geometry corrections cannot reuse an old plot bounding box.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 04: F05, F10, F11, F12 (100–176 hours)

#### Package F05: Use depth-aware soil observations and carry covariance
- **Priority**: `P1` | **Estimate**: `32-56 hours` | **Dependencies**: `F01, F04` | **R3 Requirements**: `AB-AGR-009, AB-DAT-007, AB-MES-013`

- [ ] **`ST04-F05-01`: 1. Represent individual readings with depth interval, location, time, instrument...**
  - **Target File**: [`services/agribrain/layer3_water/contracts/assimilation_state.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/contracts/assimilation_state.py)
  - **Action Required**: 1. Represent individual readings with depth interval, location, time, instrument and noise.
  - **Estimate**: 8–14 hours | **Prerequisites**: F01, F04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F05-02`: 2. Construct the vertical observation operator from overlap or point support ins...**
  - **Target File**: [`services/agribrain/layer3_water/assimilation/water_state_assimilator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/assimilation/water_state_assimilator.py)
  - **Action Required**: 2. Construct the vertical observation operator from overlap or point support instead of list index.
  - **Estimate**: 8–14 hours | **Prerequisites**: F01, F04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F05-03`: 3. Preserve correlated posterior uncertainty by layer and carry unsupported-dept...**
  - **Target File**: [`services/agribrain/layer3_water/root_zone/availability.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/root_zone/availability.py)
  - **Action Required**: 3. Preserve correlated posterior uncertainty by layer and carry unsupported-depth flags to L4 and decisions.
  - **Estimate**: 8–14 hours | **Prerequisites**: F01, F04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F05-04`: 4. Treat thermal and RF surrogates as calibrated conditional constraints with th...**
  - **Target File**: [`services/agribrain/layer3_water/contracts/assimilation_state.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/contracts/assimilation_state.py)
  - **Action Required**: 4. Treat thermal and RF surrogates as calibrated conditional constraints with their own support.
  - **Estimate**: 8–14 hours | **Prerequisites**: F01, F04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F05-FA`: Package F05 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Reordered input readings yield the same update.*
    - *A shallow reading cannot claim direct full root-zone observation.*
    - *Depth mismatch and absent support produce a qualified partial result.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F10: Repair the L3-to-L4 water boundary
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F03, F04, F05` | **R3 Requirements**: `AB-AGR-008, AB-AGR-010, AB-DAT-007`

- [ ] **`ST04-F10-01`: 1. Consume a typed depth-aware Layer3ToLayer4BoundaryReceipt....**
  - **Target File**: [`services/agribrain/layer4_nutrients/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/runner.py)
  - **Action Required**: 1. Consume a typed depth-aware Layer3ToLayer4BoundaryReceipt.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F05
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F10-02`: 2. Integrate storage and retention over the defined root support instead of repl...**
  - **Target File**: [`services/agribrain/layer3_water/contracts/water_state.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/contracts/water_state.py)
  - **Action Required**: 2. Integrate storage and retention over the defined root support instead of replacing them with generic scalars.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F05
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F10-03`: 3. Keep daily drainage flux separate from seasonal accumulated drainage....**
  - **Target File**: [`services/agribrain/layer3_water/contracts/assimilation_state.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/contracts/assimilation_state.py)
  - **Action Required**: 3. Keep daily drainage flux separate from seasonal accumulated drainage.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F05
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F10-04`: 4. Carry missing support and uncertainty into nutrient, salinity and leaching ca...**
  - **Target File**: [`services/agribrain/layer4_nutrients/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/runner.py)
  - **Action Required**: 4. Carry missing support and uncertainty into nutrient, salinity and leaching calculations.
  - **Estimate**: 6–10 hours | **Prerequisites**: F03, F04, F05
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F10-FA`: Package F10 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *A non-loam profile reaches L4 without generic substitution.*
    - *Root-zone storage matches the same depth integration as L3.*
    - *One daily drainage receipt is counted once in cumulative nutrient transport.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F11: Correct residual nitrogen demand and expose conservative pools
- **Priority**: `P0` | **Estimate**: `24-48 hours` | **Dependencies**: `F10` | **R3 Requirements**: `AB-AGR-010, AB-AGR-008`

- [ ] **`ST04-F11-01`: 1. Remove the second subtraction under the existing residual-demand convention....**
  - **Target File**: [`services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py)
  - **Action Required**: 1. Remove the second subtraction under the existing residual-demand convention.
  - **Estimate**: 6–12 hours | **Prerequisites**: F10
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F11-02`: 2. Define whether each quantity is cumulative applied, available soil, recovered...**
  - **Target File**: [`services/agribrain/layer4_nutrients/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/runner.py)
  - **Action Required**: 2. Define whether each quantity is cumulative applied, available soil, recovered plant N or additional dose.
  - **Estimate**: 6–12 hours | **Prerequisites**: F10
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F11-03`: 3. Replace independent cumulative heuristics with conservative mineralization, u...**
  - **Target File**: [`services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py)
  - **Action Required**: 3. Replace independent cumulative heuristics with conservative mineralization, uptake, loss and application pools.
  - **Estimate**: 6–12 hours | **Prerequisites**: F10
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F11-04`: 4. Carry dose timing, formulation and recovery uncertainty into recommendations....**
  - **Target File**: [`services/agribrain/layer4_nutrients/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/runner.py)
  - **Action Required**: 4. Carry dose timing, formulation and recovery uncertainty into recommendations.
  - **Estimate**: 6–12 hours | **Prerequisites**: F10
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F11-FA`: Package F11 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *The controlled residual case returns 86.67 under its declared assumptions.*
    - *Zero deficit produces zero additional demand.*
    - *Nitrogen stock changes reconcile uptake, losses and applied mass.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F12: Separate exposure verification from causal attribution
- **Priority**: `P0` | **Estimate**: `20-32 hours` | **Dependencies**: `F02` | **R3 Requirements**: `AB-EXE-005, AB-WM-006, AB-OMG-008`

- [ ] **`ST04-F12-01`: 1. Keep delivered exposure as a separate qualification field....**
  - **Target File**: [`services/agribrain/layer6_exec/outcomes/metrics.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/outcomes/metrics.py)
  - **Action Required**: 1. Keep delivered exposure as a separate qualification field.
  - **Estimate**: 5–8 hours | **Prerequisites**: F02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F12-02`: 2. Label uncontrolled pre/post metrics as observed associations even after verif...**
  - **Target File**: [`services/agribrain/layer6_exec/outcomes/metrics.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/outcomes/metrics.py)
  - **Action Required**: 2. Label uncontrolled pre/post metrics as observed associations even after verified execution.
  - **Estimate**: 5–8 hours | **Prerequisites**: F02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F12-03`: 3. Require an explicit identification record before estimating or labelling caus...**
  - **Target File**: [`services/agribrain/layer6_exec/outcomes/metrics.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/outcomes/metrics.py)
  - **Action Required**: 3. Require an explicit identification record before estimating or labelling causal effect.
  - **Estimate**: 5–8 hours | **Prerequisites**: F02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F12-04`: 4. Integrate by real timestamps, preserve valid zero indices and record missing ...**
  - **Target File**: [`services/agribrain/layer6_exec/outcomes/metrics.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/outcomes/metrics.py)
  - **Action Required**: 4. Integrate by real timestamps, preserve valid zero indices and record missing confounder data.
  - **Estimate**: 5–8 hours | **Prerequisites**: F02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST04-F12-FA`: Package F12 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Verified exposure alone never grants causal effect.*
    - *Unequal sampling intervals do not masquerade as NDVI-time integral changes.*
    - *Negative results and unknown confounding remain in the outcome record.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 05: F13, F14, F15 (68–124 hours)

#### Package F13: Correct yield quantiles and distinguish calibrated distributions from heuristics
- **Priority**: `P1` | **Estimate**: `24-48 hours` | **Dependencies**: `F02, F12` | **R3 Requirements**: `AB-AGR-014, AB-ML-005, AB-ECO-002`

- [ ] **`ST05-F13-01`: 1. Use one distribution contract with quantile levels and support....**
  - **Target File**: [`services/agribrain/layer6_yield/yield_forecast.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_yield/yield_forecast.py)
  - **Action Required**: 1. Use one distribution contract with quantile levels and support.
  - **Estimate**: 6–12 hours | **Prerequisites**: F02, F12
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F13-02`: 2. Correct normal P10/P90 to +/-1.2815516 sigma when a Gaussian assumption is ac...**
  - **Target File**: [`services/agribrain/layer7_planning/engines/yve_yield_distribution.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/engines/yve_yield_distribution.py)
  - **Action Required**: 2. Correct normal P10/P90 to +/-1.2815516 sigma when a Gaussian assumption is actually intended.
  - **Estimate**: 6–12 hours | **Prerequisites**: F02, F12
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F13-03`: 3. Label L7 deterministic penalty bands as heuristic until fitted and calibrated...**
  - **Target File**: [`services/agribrain/layer7_planning/schema.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/schema.py)
  - **Action Required**: 3. Label L7 deterministic penalty bands as heuristic until fitted and calibrated.
  - **Estimate**: 6–12 hours | **Prerequisites**: F02, F12
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F13-04`: 4. Share joint yield, quality and economic samples across L6/L7/L8 instead of tr...**
  - **Target File**: [`services/agribrain/layer6_yield/yield_forecast.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_yield/yield_forecast.py)
  - **Action Required**: 4. Share joint yield, quality and economic samples across L6/L7/L8 instead of treating their numbers as interchangeable.
  - **Estimate**: 6–12 hours | **Prerequisites**: F02, F12
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F13-FA`: Package F13 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Quantile labels match their mathematical levels.*
    - *Mean and median are distinct when the distribution is skewed.*
    - *Mixture tails are derived from the mixture distribution and prospective coverage is reported.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F14: Repair L7-to-L8 crop scenario mapping
- **Priority**: `P0` | **Estimate**: `12-20 hours` | **Dependencies**: `F13` | **R3 Requirements**: `AB-EXE-001, AB-DEC-001, AB-ECO-002`

- [ ] **`ST05-F14-01`: 1. Map the actual typed L7 contract explicitly....**
  - **Target File**: [`services/agribrain/layer7_planning/schema.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/schema.py)
  - **Action Required**: 1. Map the actual typed L7 contract explicitly.
  - **Estimate**: 3–5 hours | **Prerequisites**: F13
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F14-02`: 2. Preserve stable option ID, crop, yield distribution, economics and units....**
  - **Target File**: [`services/agribrain/layer8_prescriptive/scenario_contract.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/scenario_contract.py)
  - **Action Required**: 2. Preserve stable option ID, crop, yield distribution, economics and units.
  - **Estimate**: 3–5 hours | **Prerequisites**: F13
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F14-03`: 3. Reject a schema mismatch instead of falling back to unknown and unitless 1.0....**
  - **Target File**: [`services/agribrain/layer8_prescriptive/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/runner.py)
  - **Action Required**: 3. Reject a schema mismatch instead of falling back to unknown and unitless 1.0.
  - **Estimate**: 3–5 hours | **Prerequisites**: F13
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F14-04`: 4. Carry scenario provenance and compare operational interventions separately fr...**
  - **Target File**: [`services/agribrain/layer7_planning/schema.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/schema.py)
  - **Action Required**: 4. Carry scenario provenance and compare operational interventions separately from seasonal crop choices.
  - **Estimate**: 3–5 hours | **Prerequisites**: F13
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F14-FA`: Package F14 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Actual CropOptionEvaluation preserves crop and distribution.*
    - *Profit can never fill a yield field.*
    - *Missing required option data produces a qualified unavailable scenario.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F15: Unify weather constraints and final hard action limits
- **Priority**: `P0` | **Estimate**: `32-56 hours` | **Dependencies**: `F01, F06, F14` | **R3 Requirements**: `AB-DEC-003, AB-ECO-003, AB-EXE-001`

- [ ] **`ST05-F15-01`: 1. Normalize weather units, valid intervals and quality before every action cons...**
  - **Target File**: [`services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py)
  - **Action Required**: 1. Normalize weather units, valid intervals and quality before every action constraint.
  - **Estimate**: 8–14 hours | **Prerequisites**: F01, F06, F14
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F15-02`: 2. Treat absent mandatory safety variables as unqualified, with a clear measurem...**
  - **Target File**: [`services/agribrain/layer8_prescriptive/engines/salinity_leaching.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/engines/salinity_leaching.py)
  - **Action Required**: 2. Treat absent mandatory safety variables as unqualified, with a clear measurement or confirmation requirement.
  - **Estimate**: 8–14 hours | **Prerequisites**: F01, F06, F14
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F15-03`: 3. Preserve immutable hard constraints and never increase their ceiling during a...**
  - **Target File**: [`services/agribrain/layer8_prescriptive/scheduler.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/scheduler.py)
  - **Action Required**: 3. Preserve immutable hard constraints and never increase their ceiling during agronomic adjustments.
  - **Estimate**: 8–14 hours | **Prerequisites**: F01, F06, F14
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F15-04`: 4. Apply one final feasibility pass after all rate modifiers, zone aggregation a...**
  - **Target File**: [`services/agribrain/layer8_prescriptive/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/runner.py)
  - **Action Required**: 4. Apply one final feasibility pass after all rate modifiers, zone aggregation and scheduling, including dated legal/resource constraints.
  - **Estimate**: 8–14 hours | **Prerequisites**: F01, F06, F14
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST05-F15-FA`: Package F15 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Missing or invalid wind cannot yield a confirmed spray.*
    - *Every final dose stays within the original hard cap and budget.*
    - *Reordering dated forecast rows does not change the chosen valid slot.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 06: F16, F17, F18, F19 (88–148 hours)

#### Package F16: Enforce quota and watchdog independently of telemetry
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01` | **R3 Requirements**: `AB-EXE-004, AB-DEC-003`

- [ ] **`ST06-F16-01`: 1. Always check water budgets before command submission....**
  - **Target File**: [`services/agribrain/irrigation_runtime/dispatcher.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action Required**: 1. Always check water budgets before command submission.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F16-02`: 2. Run duration watchdogs on an independent monotonic timer....**
  - **Target File**: [`services/agribrain/irrigation_runtime/safety.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/safety.py)
  - **Action Required**: 2. Run duration watchdogs on an independent monotonic timer.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F16-03`: 3. Define critical sensor freshness and missingness policies explicitly....**
  - **Target File**: [`services/agribrain/irrigation_runtime/dispatcher.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action Required**: 3. Define critical sensor freshness and missingness policies explicitly.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F16-04`: 4. Persist reservation and delivered-water reconciliation so concurrent commands...**
  - **Target File**: [`services/agribrain/irrigation_runtime/safety.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/safety.py)
  - **Action Required**: 4. Persist reservation and delivered-water reconciliation so concurrent commands cannot overspend quota.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F16-FA`: Package F16 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Zero remaining budget produces zero physical start calls with None, empty or present telemetry.*
    - *Duration expiration stops a running event without new sensor messages.*
    - *Two reservations cannot jointly exceed the remaining budget.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F17: Keep actuator operation state until physical completion
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F16` | **R3 Requirements**: `AB-EXE-002, AB-EXE-003, AB-EXE-004`

- [ ] **`ST06-F17-01`: 1. Separate command transport acknowledgement from operation completion....**
  - **Target File**: [`services/agribrain/irrigation_runtime/actuator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/actuator.py)
  - **Action Required**: 1. Separate command transport acknowledgement from operation completion.
  - **Estimate**: 6–10 hours | **Prerequisites**: F16
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F17-02`: 2. Retain operation ownership, target flow and active event until verified stop/...**
  - **Target File**: [`services/agribrain/irrigation_runtime/dispatcher.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action Required**: 2. Retain operation ownership, target flow and active event until verified stop/completion.
  - **Estimate**: 6–10 hours | **Prerequisites**: F16
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F17-03`: 3. Allow stop and emergency stop through busy-state checks....**
  - **Target File**: [`services/agribrain/irrigation_runtime/actuator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/actuator.py)
  - **Action Required**: 3. Allow stop and emergency stop through busy-state checks.
  - **Estimate**: 6–10 hours | **Prerequisites**: F16
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F17-04`: 4. Reconcile controller telemetry against the persistent operation rather than t...**
  - **Target File**: [`services/agribrain/irrigation_runtime/dispatcher.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action Required**: 4. Reconcile controller telemetry against the persistent operation rather than transport status.
  - **Estimate**: 6–10 hours | **Prerequisites**: F16
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F17-FA`: Package F17 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Second conflicting start is rejected while physical execution continues.*
    - *Dynamic flow checks retain the target command.*
    - *Normal stop remains admissible during execution and is recorded once.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F18: Reconcile ambiguous command failures before retry
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F17` | **R3 Requirements**: `AB-EXE-003, AB-ARC-008`

- [ ] **`ST06-F18-01`: 1. Give retries the same operation identity and attempt sequence....**
  - **Target File**: [`services/agribrain/irrigation_runtime/actuator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/actuator.py)
  - **Action Required**: 1. Give retries the same operation identity and attempt sequence.
  - **Estimate**: 6–10 hours | **Prerequisites**: F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F18-02`: 2. Query controller state after timeout to distinguish applied, not applied and ...**
  - **Target File**: [`services/agribrain/irrigation_runtime/dispatcher.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action Required**: 2. Query controller state after timeout to distinguish applied, not applied and unknown.
  - **Estimate**: 6–10 hours | **Prerequisites**: F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F18-03`: 3. Permit only safe idempotent retries and retain ownership during uncertainty....**
  - **Target File**: [`services/agribrain/irrigation_runtime/actuator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/actuator.py)
  - **Action Required**: 3. Permit only safe idempotent retries and retain ownership during uncertainty.
  - **Estimate**: 6–10 hours | **Prerequisites**: F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F18-04`: 4. Restore event and controller reconciliation on process restart....**
  - **Target File**: [`services/agribrain/irrigation_runtime/dispatcher.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action Required**: 4. Restore event and controller reconciliation on process restart.
  - **Estimate**: 6–10 hours | **Prerequisites**: F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F18-FA`: Package F18 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *A retry never duplicates a delivered dose.*
    - *An acknowledgement timeout does not automatically mean no physical application.*
    - *Own-operation retry is not rejected as an unrelated competing command.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F19: Implement interlock persistence, debounce and stable violation keys
- **Priority**: `P1` | **Estimate**: `16-28 hours` | **Dependencies**: `F16, F17` | **R3 Requirements**: `AB-EXE-004, AB-EXE-003`

- [ ] **`ST06-F19-01`: 1. Track first breach, duration, recovery and freshness using monotonic time....**
  - **Target File**: [`services/agribrain/irrigation_runtime/safety.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/safety.py)
  - **Action Required**: 1. Track first breach, duration, recovery and freshness using monotonic time.
  - **Estimate**: 4–7 hours | **Prerequisites**: F16, F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F19-02`: 2. Index active violation state by device and interlock while preserving unique ...**
  - **Target File**: [`services/agribrain/irrigation_runtime/actuator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/actuator.py)
  - **Action Required**: 2. Index active violation state by device and interlock while preserving unique event records.
  - **Estimate**: 4–7 hours | **Prerequisites**: F16, F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F19-03`: 3. Implement the declared manual/automatic reset rules....**
  - **Target File**: [`services/agribrain/irrigation_runtime/safety.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/safety.py)
  - **Action Required**: 3. Implement the declared manual/automatic reset rules.
  - **Estimate**: 4–7 hours | **Prerequisites**: F16, F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F19-04`: 4. Make stop actions idempotent and rehydrate active protections after restart....**
  - **Target File**: [`services/agribrain/irrigation_runtime/actuator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/actuator.py)
  - **Action Required**: 4. Make stop actions idempotent and rehydrate active protections after restart.
  - **Estimate**: 4–7 hours | **Prerequisites**: F16, F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST06-F19-FA`: Package F19 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Configured debounce is honored with fake-clock probes.*
    - *A sustained breach emits one active violation until a qualifying reset.*
    - *Missing or nonfinite readings cannot count as normal pressure.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 07: F20, F34 (64–104 hours)

#### Package F20: Qualify post-irrigation readings before confirming delivery
- **Priority**: `P0` | **Estimate**: `32-48 hours` | **Dependencies**: `F02, F05, F12, F17` | **R3 Requirements**: `AB-EXE-005, AB-DAT-007, AB-DAT-013`

- [ ] **`ST07-F20-01`: 1. Validate reading identity, tenant, plot/zone, depth, calibration and time sup...**
  - **Target File**: [`services/agribrain/irrigation_runtime/validation.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/validation.py)
  - **Action Required**: 1. Validate reading identity, tenant, plot/zone, depth, calibration and time support.
  - **Estimate**: 8–12 hours | **Prerequisites**: F02, F05, F12, F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST07-F20-02`: 2. Deduplicate measurement IDs and require post-action measurements inside the w...**
  - **Target File**: [`services/agribrain/irrigation_runtime/validation.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/validation.py)
  - **Action Required**: 2. Deduplicate measurement IDs and require post-action measurements inside the window.
  - **Estimate**: 8–12 hours | **Prerequisites**: F02, F05, F12, F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST07-F20-03`: 3. Base expected response on verified delivered exposure and the same hydrologic...**
  - **Target File**: [`services/agribrain/irrigation_runtime/validation.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/validation.py)
  - **Action Required**: 3. Base expected response on verified delivered exposure and the same hydrological support, not solely target_volume_mm.
  - **Estimate**: 8–12 hours | **Prerequisites**: F02, F05, F12, F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST07-F20-04`: 4. Keep moisture response distinct from delivery proof and disallow calibration ...**
  - **Target File**: [`services/agribrain/irrigation_runtime/validation.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/validation.py)
  - **Action Required**: 4. Keep moisture response distinct from delivery proof and disallow calibration promotion from unqualified samples.
  - **Estimate**: 8–12 hours | **Prerequisites**: F02, F05, F12, F17
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST07-F20-FA`: Package F20 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Foreign, stale and duplicate records do not raise confirmation confidence.*
    - *Reports list the sensors that actually contributed.*
    - *Rain, drainage, sensor support and delivery uncertainty are accounted for.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F34: Separate input accounting from applied agronomic exposure
- **Priority**: `P1` | **Estimate**: `32-56 hours` | **Dependencies**: `F09, F11, F20` | **R3 Requirements**: `AW-PRO-009, AW-PRO-013, AB-DAT-007, AB-DAT-010, AB-AGR-010`

- [ ] **`ST07-F34-01`: 1. Validate unit and input category against controlled registries....**
  - **Target File**: [`src/app/api/inputs/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/inputs/route.ts)
  - **Action Required**: 1. Validate unit and input category against controlled registries.
  - **Estimate**: 8–14 hours | **Prerequisites**: F09, F11, F20
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST07-F34-02`: 2. Store purchased, stocked, planned and applied events separately....**
  - **Target File**: [`prisma/schema.prisma`](file:///c:/Users/E-C/Desktop/agriwise/prisma/schema.prisma)
  - **Action Required**: 2. Store purchased, stocked, planned and applied events separately.
  - **Estimate**: 8–14 hours | **Prerequisites**: F09, F11, F20
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST07-F34-03`: 3. Convert product quantity to nutrient mass or delivered water using formulatio...**
  - **Target File**: [`services/agribrain/layer3_decision/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)
  - **Action Required**: 3. Convert product quantity to nutrient mass or delivered water using formulation, area and support references.
  - **Estimate**: 8–14 hours | **Prerequisites**: F09, F11, F20
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST07-F34-04`: 4. Publish verified application exposure to Worldline and update financial total...**
  - **Target File**: [`services/agribrain/layer4_nutrients/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/runner.py)
  - **Action Required**: 4. Publish verified application exposure to Worldline and update financial totals idempotently.
  - **Estimate**: 8–14 hours | **Prerequisites**: F09, F11, F20
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST07-F34-FA`: Package F34 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *A purchase or future plan cannot enter historical water/N balance.*
    - *Product kg and elemental nutrient kg are never interchanged.*
    - *Retry cannot double-count stock, cost or applied mass.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 08: F21, F22, F23, F24 (88–144 hours)

#### Package F21: Freeze training-window payloads and include partition identity
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F02, F09` | **R3 Requirements**: `AB-DAT-011, AB-DAT-013, AB-ML-001, AB-ML-007`

- [ ] **`ST08-F21-01`: 1. Use immutable or deeply copied canonical event snapshots....**
  - **Target File**: [`services/agribrain/world_model/historical_extractor.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/historical_extractor.py)
  - **Action Required**: 1. Use immutable or deeply copied canonical event snapshots.
  - **Estimate**: 6–10 hours | **Prerequisites**: F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F21-02`: 2. Hash payload content, schema, partition, geometry/cycle and extraction policy...**
  - **Target File**: [`services/agribrain/world_model/canonical_worldline.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/canonical_worldline.py)
  - **Action Required**: 2. Hash payload content, schema, partition, geometry/cycle and extraction policy.
  - **Estimate**: 6–10 hours | **Prerequisites**: F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F21-03`: 3. Include supersession/retraction resolution and ordered parent evidence in the...**
  - **Target File**: [`services/agribrain/world_model/historical_extractor.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/historical_extractor.py)
  - **Action Required**: 3. Include supersession/retraction resolution and ordered parent evidence in the manifest.
  - **Estimate**: 6–10 hours | **Prerequisites**: F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F21-04`: 4. Verify the digest again before dataset loading and model artifact creation....**
  - **Target File**: [`services/agribrain/world_model/canonical_worldline.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/canonical_worldline.py)
  - **Action Required**: 4. Verify the digest again before dataset loading and model artifact creation.
  - **Estimate**: 6–10 hours | **Prerequisites**: F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F21-FA`: Package F21 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Any included content change alters the manifest identity.*
    - *Caller mutation cannot alter an issued window.*
    - *Tenant/namespace boundaries have distinct manifest identities.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F22: Classify timing by event role rather than a universal causality rule
- **Priority**: `P0` | **Estimate**: `20-32 hours` | **Dependencies**: `F02, F21` | **R3 Requirements**: `AB-DAT-004, AB-DAT-014, AB-ML-008`

- [ ] **`ST08-F22-01`: 1. Define event-specific observation, forecast validity, planned action and avai...**
  - **Target File**: [`services/agribrain/world_model/historical_extractor.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/historical_extractor.py)
  - **Action Required**: 1. Define event-specific observation, forecast validity, planned action and availability fields.
  - **Estimate**: 5–8 hours | **Prerequisites**: F02, F21
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F22-02`: 2. Apply measurement chronology checks to measurements and issuance eligibility ...**
  - **Target File**: [`services/agribrain/world_model/contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/contracts.py)
  - **Action Required**: 2. Apply measurement chronology checks to measurements and issuance eligibility to forecasts/scenarios.
  - **Estimate**: 5–8 hours | **Prerequisites**: F02, F21
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F22-03`: 3. Validate each child input and revision against the cutoff....**
  - **Target File**: [`services/agribrain/world_model/historical_extractor.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/historical_extractor.py)
  - **Action Required**: 3. Validate each child input and revision against the cutoff.
  - **Estimate**: 5–8 hours | **Prerequisites**: F02, F21
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F22-04`: 4. Build separate manifests for inputs, later targets and retrospective reconstr...**
  - **Target File**: [`services/agribrain/world_model/contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/contracts.py)
  - **Action Required**: 4. Build separate manifests for inputs, later targets and retrospective reconstructions.
  - **Estimate**: 5–8 hours | **Prerequisites**: F02, F21
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F22-FA`: Package F22 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *An archived earlier-issued future forecast remains an eligible input.*
    - *A future measurement is still excluded.*
    - *A planned action stays a scenario and never becomes historical applied water.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F23: Commit forecast archives atomically before publishing cache entries
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F21, F22` | **R3 Requirements**: `AB-DAT-011, AB-ARC-007, AB-ARC-008, AB-ASM-014`

- [ ] **`ST08-F23-01`: 1. Validate immutable content and resolve the durable record before altering cac...**
  - **Target File**: [`services/agribrain/world_model/forecast_archive.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/forecast_archive.py)
  - **Action Required**: 1. Validate immutable content and resolve the durable record before altering cache.
  - **Estimate**: 6–10 hours | **Prerequisites**: F21, F22
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F23-02`: 2. Use an atomic conditional insert or equivalent lock/fence instead of exists-t...**
  - **Target File**: [`services/agribrain/world_model/forecast_archive.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/forecast_archive.py)
  - **Action Required**: 2. Use an atomic conditional insert or equivalent lock/fence instead of exists-then-replace races.
  - **Estimate**: 6–10 hours | **Prerequisites**: F21, F22
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F23-03`: 3. Deep-freeze nested predictions and metadata....**
  - **Target File**: [`services/agribrain/world_model/forecast_archive.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/forecast_archive.py)
  - **Action Required**: 3. Deep-freeze nested predictions and metadata.
  - **Estimate**: 6–10 hours | **Prerequisites**: F21, F22
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F23-04`: 4. Treat corrupt or conflicting records as explicit integrity errors instead of ...**
  - **Target File**: [`services/agribrain/world_model/forecast_archive.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/forecast_archive.py)
  - **Action Required**: 4. Treat corrupt or conflicting records as explicit integrity errors instead of absence.
  - **Estimate**: 6–10 hours | **Prerequisites**: F21, F22
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F23-FA`: Package F23 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *After conflict, warm and cold readers return the committed forecast only.*
    - *Concurrent incompatible writes produce one committed identity.*
    - *Mutation cannot alter archived predictions or subsequent evaluation.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F24: Validate forecast distributions and make missing scores unavailable
- **Priority**: `P0` | **Estimate**: `20-32 hours` | **Dependencies**: `F13, F23` | **R3 Requirements**: `AB-ML-005, AB-ML-010, AB-ASM-016`

- [ ] **`ST08-F24-01`: 1. Require finite consistent horizon, timezone-aware origin/target and a support...**
  - **Target File**: [`services/agribrain/world_model/forecast_archive.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/forecast_archive.py)
  - **Action Required**: 1. Require finite consistent horizon, timezone-aware origin/target and a supported finite distribution.
  - **Estimate**: 5–8 hours | **Prerequisites**: F13, F23
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F24-02`: 2. Validate quantile levels and monotonicity, variable units/domain and nonnegat...**
  - **Target File**: [`services/agribrain/layer6_yield/yield_forecast.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_yield/yield_forecast.py)
  - **Action Required**: 2. Validate quantile levels and monotonicity, variable units/domain and nonnegative sigma.
  - **Estimate**: 5–8 hours | **Prerequisites**: F13, F23
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F24-03`: 3. Return unavailable with reason for missing distributions and reject invalid s...**
  - **Target File**: [`services/agribrain/world_model/forecast_archive.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/forecast_archive.py)
  - **Action Required**: 3. Return unavailable with reason for missing distributions and reject invalid sigma.
  - **Estimate**: 5–8 hours | **Prerequisites**: F13, F23
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F24-04`: 4. Name finite-quantile pinball scoring accurately or implement a documented int...**
  - **Target File**: [`services/agribrain/layer6_yield/yield_forecast.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_yield/yield_forecast.py)
  - **Action Required**: 4. Name finite-quantile pinball scoring accurately or implement a documented integration rule rather than silently treating an unweighted sparse average as exact CRPS.
  - **Estimate**: 5–8 hours | **Prerequisites**: F13, F23
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST08-F24-FA`: Package F24 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Empty or malformed forecasts receive no numeric skill credit.*
    - *Origin-target interval and horizon agree.*
    - *Quantile coverage and scores use explicit levels and independently supported targets.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 09: F25, F26, F27, F28, F29 (140–232 hours)

#### Package F25: Report the actual EO inference backend and normalize its input contract
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01` | **R3 Requirements**: `AB-ML-002, AB-ML-014, AB-DAT-006`

- [ ] **`ST09-F25-01`: 1. Return backend identity and model artifact digest with every inference result...**
  - **Target File**: [`services/agribrain/layer1_fusion/eo_foundation_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action Required**: 1. Return backend identity and model artifact digest with every inference result.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F25-02`: 2. Create explicit per-model tensor, band order, normalization and mask adapters...**
  - **Target File**: [`services/agribrain/layer1_fusion/eo_foundation_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action Required**: 2. Create explicit per-model tensor, band order, normalization and mask adapters.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F25-03`: 3. On backend failure, publish the fallback role and cause, or make the capabili...**
  - **Target File**: [`services/agribrain/layer1_fusion/eo_foundation_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action Required**: 3. On backend failure, publish the fallback role and cause, or make the capability unavailable.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F25-04`: 4. Derive confidence from evaluated model/domain evidence rather than file prese...**
  - **Target File**: [`services/agribrain/layer1_fusion/eo_foundation_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action Required**: 4. Derive confidence from evaluated model/domain evidence rather than file presence.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F25-FA`: Package F25 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *A failed ONNX call cannot label fallback features as learned model output.*
    - *Wrong input shape fails at a clear contract boundary.*
    - *Model identity includes weights, preprocessing and calibration versions.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F26: Hash complete EO support and distinguish missing bands from zero
- **Priority**: `P1` | **Estimate**: `20-32 hours` | **Dependencies**: `F25` | **R3 Requirements**: `AB-DAT-002, AB-DAT-008, AB-DAT-011, AB-ML-002`

- [ ] **`ST09-F26-01`: 1. Build digests from band identity/order, shape, numeric encoding, CRS/affine a...**
  - **Target File**: [`services/agribrain/layer1_fusion/eo_foundation_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action Required**: 1. Build digests from band identity/order, shape, numeric encoding, CRS/affine and validity/cloud masks.
  - **Estimate**: 5–8 hours | **Prerequisites**: F25
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F26-02`: 2. Validate aligned shapes and mask coverage before pooling....**
  - **Target File**: [`services/agribrain/layer1_fusion/eo_foundation_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action Required**: 2. Validate aligned shapes and mask coverage before pooling.
  - **Estimate**: 5–8 hours | **Prerequisites**: F25
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F26-03`: 3. Pass missing-band masks into supported models or declare the fallback feature...**
  - **Target File**: [`services/agribrain/layer1_fusion/eo_foundation_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action Required**: 3. Pass missing-band masks into supported models or declare the fallback feature policy.
  - **Estimate**: 5–8 hours | **Prerequisites**: F25
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F26-04`: 4. Require finite pixels and model-specific reflectance scale....**
  - **Target File**: [`services/agribrain/layer1_fusion/eo_foundation_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action Required**: 4. Require finite pixels and model-specific reflectance scale.
  - **Estimate**: 5–8 hours | **Prerequisites**: F25
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F26-FA`: Package F26 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Different spectral support or masks have distinct identities.*
    - *A missing band is distinguishable from true zero reflectance.*
    - *A model cannot silently consume misaligned channels.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F27: Repair MESIA link-time axes and graph topology
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01, F26` | **R3 Requirements**: `AB-MES-009, AB-ML-002`

- [ ] **`ST09-F27-01`: 1. Restore B,L,S,D and explicitly permute to B,S,L,D....**
  - **Target File**: [`services/agribrain/mesia/learning/neural_receiver.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/neural_receiver.py)
  - **Action Required**: 1. Restore B,L,S,D and explicitly permute to B,S,L,D.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01, F26
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F27-02`: 2. Define valid-link padding and graph masks with batch/time semantics....**
  - **Target File**: [`services/agribrain/mesia/learning/neural_receiver.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/neural_receiver.py)
  - **Action Required**: 2. Define valid-link padding and graph masks with batch/time semantics.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01, F26
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F27-03`: 3. Thread geometry, antenna and instrument epochs through the neural receiver....**
  - **Target File**: [`services/agribrain/mesia/learning/neural_receiver.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/neural_receiver.py)
  - **Action Required**: 3. Thread geometry, antenna and instrument epochs through the neural receiver.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01, F26
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F27-04`: 4. Compare topology-aware output with an intentionally topology-free baseline....**
  - **Target File**: [`services/agribrain/mesia/learning/neural_receiver.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/neural_receiver.py)
  - **Action Required**: 4. Compare topology-aware output with an intentionally topology-free baseline.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01, F26
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F27-FA`: Package F27 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (1 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Distinct link/time marker tensors preserve their identities.*
    - *Invalid links do not affect pooling or attention.*
    - *Changing topology affects only permitted message paths.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F28: Make MESIA masked pretraining respect complex channel semantics
- **Priority**: `P1` | **Estimate**: `32-48 hours` | **Dependencies**: `F27` | **R3 Requirements**: `AB-MES-010, AB-MES-011, AB-ML-004`

- [ ] **`ST09-F28-01`: 1. Derive decoder dimensions from the actual ModelArtifact configuration....**
  - **Target File**: [`services/agribrain/mesia/learning/masked_link_trainer.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/masked_link_trainer.py)
  - **Action Required**: 1. Derive decoder dimensions from the actual ModelArtifact configuration.
  - **Estimate**: 8–12 hours | **Prerequisites**: F27
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F28-02`: 2. Use paired masks for complex channel elements and explicit link/time/frequenc...**
  - **Target File**: [`services/agribrain/mesia/learning/neural_receiver.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/neural_receiver.py)
  - **Action Required**: 2. Use paired masks for complex channel elements and explicit link/time/frequency mask tokens.
  - **Estimate**: 8–12 hours | **Prerequisites**: F27
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F28-03`: 3. Represent phase circularly or complex-valued and apply the corresponding like...**
  - **Target File**: [`services/agribrain/mesia/learning/masked_link_trainer.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/masked_link_trainer.py)
  - **Action Required**: 3. Represent phase circularly or complex-valued and apply the corresponding likelihood/loss.
  - **Estimate**: 8–12 hours | **Prerequisites**: F27
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F28-04`: 4. Exclude padded, missing and uncalibrated-invalid samples from objectives that...**
  - **Target File**: [`services/agribrain/mesia/learning/neural_receiver.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/neural_receiver.py)
  - **Action Required**: 4. Exclude padded, missing and uncalibrated-invalid samples from objectives that require them, while retaining compatible discovery objectives.
  - **Estimate**: 8–12 hours | **Prerequisites**: F27
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F28-FA`: Package F28 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Non-128 receiver configurations have compatible decoders.*
    - *Equivalent phase angles have small circular error.*
    - *Masked-loss support and normalization are reproducible and finite.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F29: Correct MESIA evaluation labels and establish independent biological validation
- **Priority**: `P1` | **Estimate**: `40-72 plus field work hours` | **Dependencies**: `F05, F24, F27, F28` | **R3 Requirements**: `AB-MES-014, AB-MES-012, AB-ASM-003`

- [ ] **`ST09-F29-01`: 1. Bind evaluation channels to the actual state registry and support contract....**
  - **Target File**: [`services/agribrain/mesia/learning/asmae_evaluator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/asmae_evaluator.py)
  - **Action Required**: 1. Bind evaluation channels to the actual state registry and support contract.
  - **Estimate**: 10–18 hours | **Prerequisites**: F05, F24, F27, F28
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F29-02`: 2. Label R-squared, correlation and predictive error as distinct metrics with co...**
  - **Target File**: [`services/agribrain/mesia/behaviour/likelihood_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/behaviour/likelihood_engine.py)
  - **Action Required**: 2. Label R-squared, correlation and predictive error as distinct metrics with constant-target handling.
  - **Estimate**: 10–18 hours | **Prerequisites**: F05, F24, F27, F28
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F29-03`: 3. Evaluate held-out sites, instruments, seasons and nuisance interventions agai...**
  - **Target File**: [`services/agribrain/mesia/assimilation/observability_analyzer.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/assimilation/observability_analyzer.py)
  - **Action Required**: 3. Evaluate held-out sites, instruments, seasons and nuisance interventions against independent qualified measurements.
  - **Estimate**: 10–18 hours | **Prerequisites**: F05, F24, F27, F28
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F29-04`: 4. Promote only demonstrated per-variable capabilities and keep discovery repres...**
  - **Target File**: [`services/agribrain/mesia/learning/asmae_evaluator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/asmae_evaluator.py)
  - **Action Required**: 4. Promote only demonstrated per-variable capabilities and keep discovery representations available without biological claims.
  - **Estimate**: 10–18 hours | **Prerequisites**: F05, F24, F27, F28
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST09-F29-FA`: Package F29 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Changing the configured state count cannot crash or mislabel channels.*
    - *Agreement with an ASMAE teacher is reported as dependent evaluation.*
    - *Biological capability requires independent calibration and nuisance-controlled validation.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 10: F30, F31, F32, F33, F38, F40 (172–296 hours)

#### Package F30: Scope conversational memory and cache identity
- **Priority**: `P1` | **Estimate**: `32-48 hours` | **Dependencies**: `F02, F09` | **R3 Requirements**: `AB-L9-008, AB-L9-009, AB-DAT-013`

- [ ] **`ST10-F30-01`: 1. Define explicit tenant/user/thread/plot/cycle scope for conversational memory...**
  - **Target File**: [`services/agribrain/layer9_interface/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/runner.py)
  - **Action Required**: 1. Define explicit tenant/user/thread/plot/cycle scope for conversational memory.
  - **Estimate**: 8–12 hours | **Prerequisites**: F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F30-02`: 2. Resolve references only from sources authorized for the active thread....**
  - **Target File**: [`services/agribrain/layer9_interface/engines/conversation_memory.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/conversation_memory.py)
  - **Action Required**: 2. Resolve references only from sources authorized for the active thread.
  - **Estimate**: 8–12 hours | **Prerequisites**: F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F30-03`: 3. Include state head, policy, model, language, intent and claim artifacts in ca...**
  - **Target File**: [`services/agribrain/layer9_interface/engines/semantic_cache.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/semantic_cache.py)
  - **Action Required**: 3. Include state head, policy, model, language, intent and claim artifacts in cache identity.
  - **Estimate**: 8–12 hours | **Prerequisites**: F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F30-04`: 4. Preserve numeric quantities and negation, and cache canonically generated art...**
  - **Target File**: [`services/agribrain/layer9_interface/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/runner.py)
  - **Action Required**: 4. Preserve numeric quantities and negation, and cache canonically generated artifacts rather than free-standing operational advice.
  - **Estimate**: 8–12 hours | **Prerequisites**: F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F30-FA`: Package F30 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *No user thread inherits another user narrative without authorized sharing.*
    - *A changed dose, cutoff or policy invalidates the advice cache.*
    - *Runtime tracing proves which cache paths are active before rollout.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F31: Close the independent public AI advice path
- **Priority**: `P0` | **Estimate**: `24-40 hours` | **Dependencies**: `F01, F02, F15, F30` | **R3 Requirements**: `AB-ARC-010, AB-L9-001, AB-L9-002, AB-L9-003, AW-PRO-018`

- [ ] **`ST10-F31-01`: 1. Require authentication and authorize any requested plot context....**
  - **Target File**: [`src/app/api/ai/chat/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/ai/chat/route.ts)
  - **Action Required**: 1. Require authentication and authorize any requested plot context.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01, F02, F15, F30
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F31-02`: 2. Resolve trusted context server-side rather than treating browser fields as ev...**
  - **Target File**: [`src/lib/agribrain/gemini-advisor.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/lib/agribrain/gemini-advisor.ts)
  - **Action Required**: 2. Resolve trusted context server-side rather than treating browser fields as evidence.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01, F02, F15, F30
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F31-03`: 3. Route plot-specific advice through canonical intent, claims, constraints and ...**
  - **Target File**: [`src/app/api/agribrain/intent/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/agribrain/intent/route.ts)
  - **Action Required**: 3. Route plot-specific advice through canonical intent, claims, constraints and visible response.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01, F02, F15, F30
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F31-04`: 4. Keep educational content explicitly educational and apply provider quotas and...**
  - **Target File**: [`src/app/api/ai/chat/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/ai/chat/route.ts)
  - **Action Required**: 4. Keep educational content explicitly educational and apply provider quotas and body limits.
  - **Estimate**: 6–10 hours | **Prerequisites**: F01, F02, F15, F30
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F31-FA`: Package F31 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Unauthorized context cannot become plot-specific advice.*
    - *Rendered numbers and prohibitions match the canonical artifact.*
    - *Provider failures and missing evidence produce explicit unavailable or educational responses.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F32: Replace demo calendar and misleading empty/error application states
- **Priority**: `P1` | **Estimate**: `32-56 hours` | **Dependencies**: `F09` | **R3 Requirements**: `AW-PRO-008, AW-PRO-004, AB-DAT-005, AB-DAT-013`
- **Note on Early Slice**: Early scope `Dashboard errors return unavailable, preserving legitimate account zeros`. Full acceptance requires `Full records/calendar/scoped integration after F09 at stage 10`.

- [ ] **`ST10-F32-01`: 1. Connect calendar to authorized persisted task/cycle records and scoped date-r...**
  - **Target File**: [`src/app/calendar/page.tsx`](file:///c:/Users/E-C/Desktop/agriwise/src/app/calendar/page.tsx)
  - **Action Required**: 1. Connect calendar to authorized persisted task/cycle records and scoped date-range queries.
  - **Estimate**: 8–14 hours | **Prerequisites**: F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F32-02`: 2. Persist completion, deviations, assignees and timezone instead of local demo ...**
  - **Target File**: [`src/app/api/cycles/[id]/tasks/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/cycles/[id]/tasks/route.ts)
  - **Action Required**: 2. Persist completion, deviations, assignees and timezone instead of local demo state.
  - **Estimate**: 8–14 hours | **Prerequisites**: F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F32-03`: 3. Distinguish loading, empty, unauthorized and unavailable states in farms and ...**
  - **Target File**: [`src/app/farm/page.tsx`](file:///c:/Users/E-C/Desktop/agriwise/src/app/farm/page.tsx)
  - **Action Required**: 3. Distinguish loading, empty, unauthorized and unavailable states in farms and dashboards.
  - **Estimate**: 8–14 hours | **Prerequisites**: F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F32-04`: 4. Put demo records in an explicit isolated demo namespace and remove real-tenan...**
  - **Target File**: [`src/app/api/dashboard/stats/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/dashboard/stats/route.ts)
  - **Action Required**: 4. Put demo records in an explicit isolated demo namespace and remove real-tenant development fallback.
  - **Estimate**: 8–14 hours | **Prerequisites**: F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F32-FA`: Package F32 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *A new empty account sees no fabricated tasks.*
    - *Task edits survive reload and appear in the scientific exposure workflow when qualified.*
    - *Database outage shows unavailable instead of a successful empty farm or zero statistics.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F33: Validate photo zone ownership and database insert success
- **Priority**: `P1` | **Estimate**: `12-24 hours` | **Dependencies**: `F01, F02, F09` | **R3 Requirements**: `AW-PRO-005, AW-PRO-011, AB-DAT-013, AB-ARC-007`

- [ ] **`ST10-F33-01`: 1. Resolve optional zone against the authorized plot and geometry epoch....**
  - **Target File**: [`src/app/api/evidence/add/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/evidence/add/route.ts)
  - **Action Required**: 1. Resolve optional zone against the authorized plot and geometry epoch.
  - **Estimate**: 3–6 hours | **Prerequisites**: F01, F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F33-02`: 2. Validate observation timing and retain the server availability timestamp....**
  - **Target File**: [`prisma/schema.prisma`](file:///c:/Users/E-C/Desktop/agriwise/prisma/schema.prisma)
  - **Action Required**: 2. Validate observation timing and retain the server availability timestamp.
  - **Estimate**: 3–6 hours | **Prerequisites**: F01, F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F33-03`: 3. Check raw write outcome and return the canonical created evidence ID....**
  - **Target File**: [`src/app/api/evidence/add/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/evidence/add/route.ts)
  - **Action Required**: 3. Check raw write outcome and return the canonical created evidence ID.
  - **Estimate**: 3–6 hours | **Prerequisites**: F01, F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F33-04`: 4. Preserve pending processing and use a durable admission/outbox event for retr...**
  - **Target File**: [`prisma/schema.prisma`](file:///c:/Users/E-C/Desktop/agriwise/prisma/schema.prisma)
  - **Action Required**: 4. Preserve pending processing and use a durable admission/outbox event for retries.
  - **Estimate**: 3–6 hours | **Prerequisites**: F01, F02, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F33-FA`: Package F33 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *A foreign valid-looking zone cannot be attached.*
    - *Failed raw insertion cannot return success.*
    - *Photo availability and processing state are recoverable after retry.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F38: Restore failure ledgers, scoped loading and degraded publication
- **Priority**: `P0` | **Estimate**: `48-80 hours` | **Dependencies**: `F01, F02, F09, F31, F37` | **R3 Requirements**: `AB-DAT-005, AB-DAT-013, AB-ARC-005, AB-ARC-007, AB-ARC-008, AB-L9-002, AB-L10-001`
- **Note on Early Slice**: Early scope `Fix local undefined names using real input/context; reject fabricated namespace; repair exact snapshot relation`. Full acceptance requires `F01/F02/F09/F31/F37; full integration stage 10`.

- [ ] **`ST10-F38-01`: 1. Use the function-local decision timestamp in terminal no-data output and veri...**
  - **Target File**: [`services/agribrain/orchestrator_v2/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/runner.py)
  - **Action Required**: 1. Use the function-local decision timestamp in terminal no-data output and verify degraded output commits through the canonical publication contract.
  - **Estimate**: 5–8 hours | **Prerequisites**: F01, F02, F09, F31, F37
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F38-02`: 2. Thread actual intent and userMode from typed context into local compression, ...**
  - **Target File**: [`services/agribrain/orchestrator_v2/chat_adapter.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/chat_adapter.py)
  - **Action Required**: 2. Thread actual intent and userMode from typed context into local compression, routing and response policy.
  - **Estimate**: 5–8 hours | **Prerequisites**: F01, F02, F09, F31, F37
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F38-03`: 3. Build geometry explicitly in the synthetic bridge helper and isolate that hel...**
  - **Target File**: [`services/agribrain/layer10_sire/l10_frontend_bridge.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/l10_frontend_bridge.py)
  - **Action Required**: 3. Build geometry explicitly in the synthetic bridge helper and isolate that helper from normal product inputs.
  - **Estimate**: 5–8 hours | **Prerequisites**: F01, F02, F09, F31, F37
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F38-04`: 4. Build failed ASMAE validation receipts from inp and its qualified geometry, r...**
  - **Target File**: [`services/agribrain/layer05_asmae/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/runner.py)
  - **Action Required**: 4. Build failed ASMAE validation receipts from inp and its qualified geometry, removing arbitrary geometry-hash fallback.
  - **Estimate**: 5–8 hours | **Prerequisites**: F01, F02, F09, F31, F37
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F38-05`: 5. Resolve external-scene resolution from validated grid metadata and preserve e...**
  - **Target File**: [`services/agribrain/layer05_asmae/geometry/external_scene_loader.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/geometry/external_scene_loader.py)
  - **Action Required**: 5. Resolve external-scene resolution from validated grid metadata and preserve each rejected-scene reason.
  - **Estimate**: 5–8 hours | **Prerequisites**: F01, F02, F09, F31, F37
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F38-06`: 6. Require qualified MESIA namespace rather than fabricated default scope....**
  - **Target File**: [`services/agribrain/mesia/service.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/service.py)
  - **Action Required**: 6. Require qualified MESIA namespace rather than fabricated default scope.
  - **Estimate**: 5–8 hours | **Prerequisites**: F01, F02, F09, F31, F37
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F38-07`: 7. Import statistics and IrrigationSystemType at their actual runtime definition...**
  - **Target File**: [`services/agribrain/layer2_veg_int/growth_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_veg_int/growth_engine.py)
  - **Action Required**: 7. Import statistics and IrrigationSystemType at their actual runtime definitions and verify relevant branches.
  - **Estimate**: 5–8 hours | **Prerequisites**: F01, F02, F09, F31, F37
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F38-08`: 8. Parse completed timestamps robustly but derive published only from the exact ...**
  - **Target File**: [`services/agribrain/app/main.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/app/main.py)
  - **Action Required**: 8. Parse completed timestamps robustly but derive published only from the exact committed output relation, including superseded heads.
  - **Estimate**: 5–8 hours | **Prerequisites**: F01, F02, F09, F31, F37
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F38-09`: 9. Classify each caught failure as unavailable capability or partial result with...**
  - **Target File**: [`services/agribrain/irrigation_runtime/dispatcher.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/irrigation_runtime/dispatcher.py)
  - **Action Required**: 9. Classify each caught failure as unavailable capability or partial result with observable diagnostic instead of silently manufacturing success.
  - **Estimate**: 5–8 hours | **Prerequisites**: F01, F02, F09, F31, F37
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F38-FA`: Package F38 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (10 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *The three reproduced external-scene, growth-spacing and missing-event cases no longer fail.*
    - *Degraded L1 emits a committed no-data response using ts_now.*
    - *ASMAE failure still returns its original error and also persists its failure receipt.*
    - *A foreign or mismatched head cannot prove the completed job was published.*
    - *Missing scope never becomes default_tenant/default_farm.*
    - *Local response compression/routing use the real intent and mode.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F40: Resolve annotation consumers and close verification evidence gaps
- **Priority**: `P1` | **Estimate**: `24-48 hours` | **Dependencies**: `F37, F38` | **R3 Requirements**: `AB-ARC-004, AB-ARC-006, AB-ARC-012, AB-ML-014`
- **Note on Early Slice**: Early scope `Resolve annotation names needed by actual schema/introspection consumers`. Full acceptance requires `F37/F38; complete runtime/manifest verification stage 10`.

- [ ] **`ST10-F40-01`: 1. Import or explicitly resolve annotation names where runtime consumers need th...**
  - **Target File**: [`services/agribrain/layer0/kalman_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/kalman_engine.py)
  - **Action Required**: 1. Import or explicitly resolve annotation names where runtime consumers need them.
  - **Estimate**: 3–6 hours | **Prerequisites**: F37, F38
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F40-02`: 2. Use postponed type-only imports only when schema/introspection frameworks do ...**
  - **Target File**: [`services/agribrain/mesia/identity/correlators.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/identity/correlators.py)
  - **Action Required**: 2. Use postponed type-only imports only when schema/introspection frameworks do not require resolution.
  - **Estimate**: 3–6 hours | **Prerequisites**: F37, F38
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F40-03`: 3. Audit the 18 cited files and every public dataclass/Pydantic/tool-schema cons...**
  - **Target File**: [`services/agribrain/world_model/belief_snapshot.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/belief_snapshot.py)
  - **Action Required**: 3. Audit the 18 cited files and every public dataclass/Pydantic/tool-schema consumer with the installed declared runtime.
  - **Estimate**: 3–6 hours | **Prerequisites**: F37, F38
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F40-04`: 4. Create a pinned full production manifest with exact exclusion rules and suppo...**
  - **Target File**: [`services/agribrain/layer4_nutrients/schema.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer4_nutrients/schema.py)
  - **Action Required**: 4. Create a pinned full production manifest with exact exclusion rules and supported Python/dependency versions.
  - **Estimate**: 3–6 hours | **Prerequisites**: F37, F38
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F40-05`: 5. Compile the manifest and cold-load decorated schemas separately....**
  - **Target File**: [`services/agribrain/sensor_runtime/registry.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/sensor_runtime/registry.py)
  - **Action Required**: 5. Compile the manifest and cold-load decorated schemas separately.
  - **Estimate**: 3–6 hours | **Prerequisites**: F37, F38
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F40-06`: 6. Classify exception handlers by recovery and published scientific effect, and ...**
  - **Target File**: [`services/agribrain/layer05_asmae/background_jobs.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/background_jobs.py)
  - **Action Required**: 6. Classify exception handlers by recovery and published scientific effect, and run a history-aware secrets check without exposing values.
  - **Estimate**: 3–6 hours | **Prerequisites**: F37, F38
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F40-07`: 7. Publish scope and reproducible receipts rather than extending subset zero cou...**
  - **Target File**: [`services/agribrain/layer0/kalman_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/kalman_engine.py)
  - **Action Required**: 7. Publish scope and reproducible receipts rather than extending subset zero counts to the whole tree.
  - **Estimate**: 3–6 hours | **Prerequisites**: F37, F38
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST10-F40-FA`: Package F40 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (6 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *get_type_hints and production schema generation succeed for supported public contracts.*
    - *The runtime and file manifest accompany every verification count.*
    - *An unresolved annotation cannot silently invalidate a tool/schema registration.*
    - *Secret, portability, dataclass and full-repository claims remain unqualified until their own checks complete.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 11: F35, F36, T11 (168–296 hours)

#### Package F35: Repair drone driver import and complete process cleanup
- **Priority**: `P1` | **Estimate**: `20-36 hours` | **Dependencies**: `F09` | **R3 Requirements**: `AW-PRO-011, AB-ARC-006, AB-ARC-008, AB-ARC-012`
- **Note on Early Slice**: Early scope `Isolate missing optional driver import; make driver availability explicit`. Full acceptance requires `Durable job lifecycle after F09; full reliability stage 11`.

- [ ] **`ST11-F35-01`: 1. Lazy-load explicitly configured real drivers and move simulation behind an ex...**
  - **Target File**: [`services/agribrain/drone_control/dispatcher.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/drone_control/dispatcher.py)
  - **Action Required**: 1. Lazy-load explicitly configured real drivers and move simulation behind an explicit test/development capability.
  - **Estimate**: 5–9 hours | **Prerequisites**: F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-F35-02`: 2. Return unavailable driver capability without breaking unrelated service impor...**
  - **Target File**: [`services/agribrain/app/drone_routes.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/app/drone_routes.py)
  - **Action Required**: 2. Return unavailable driver capability without breaking unrelated service import.
  - **Estimate**: 5–9 hours | **Prerequisites**: F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-F35-03`: 3. Complete terminate-kill-wait lifecycle and process-group cleanup under a boun...**
  - **Target File**: [`services/agribrain/layer05_asmae/background_jobs.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/background_jobs.py)
  - **Action Required**: 3. Complete terminate-kill-wait lifecycle and process-group cleanup under a bounded deadline.
  - **Estimate**: 5–9 hours | **Prerequisites**: F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-F35-04`: 4. Fence all child writes and publish final cleanup/ownership receipts....**
  - **Target File**: [`services/agribrain/drone_control/dispatcher.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/drone_control/dispatcher.py)
  - **Action Required**: 4. Fence all child writes and publish final cleanup/ownership receipts.
  - **Estimate**: 5–9 hours | **Prerequisites**: F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-F35-FA`: Package F35 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Missing optional drivers cannot disable service startup.*
    - *Simulation cannot publish observed mission evidence.*
    - *Forced-kill cleanup confirms process exit before resource ownership is released.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package F36: Require per-variable observability and independent predictive calibration
- **Priority**: `P1` | **Estimate**: `48-80 plus reference data hours` | **Dependencies**: `F01, F02, F24, F29` | **R3 Requirements**: `AB-ASM-003, AB-ASM-011, AB-ASM-013, AB-ASM-014, AB-ASM-015, AB-ASM-016, AB-ASM-001, AB-ASM-002, AB-ASM-004, AB-ASM-005, AB-ASM-009, AB-ASM-010, AB-ASM-012`

- [ ] **`ST11-F36-01`: 1. Build a per-state support ledger connecting actual operator sensitivity and i...**
  - **Target File**: [`services/agribrain/layer05_asmae/training/exporter.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/training/exporter.py)
  - **Action Required**: 1. Build a per-state support ledger connecting actual operator sensitivity and independent references to each label.
  - **Estimate**: 12–20 hours | **Prerequisites**: F01, F02, F24, F29
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-F36-02`: 2. Carry dependence groups for indices from shared native acquisitions and BMA e...**
  - **Target File**: [`services/agribrain/layer05_asmae/observation/index_state_mapping.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/observation/index_state_mapping.py)
  - **Action Required**: 2. Carry dependence groups for indices from shared native acquisitions and BMA experts sharing evidence.
  - **Estimate**: 12–20 hours | **Prerequisites**: F01, F02, F24, F29
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-F36-03`: 3. Use archived prospective issuance cohorts separately from hindcasts and persi...**
  - **Target File**: [`services/agribrain/layer05_asmae/constraints/radiometric.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/constraints/radiometric.py)
  - **Action Required**: 3. Use archived prospective issuance cohorts separately from hindcasts and persistence, with per-variable/horizon calibration.
  - **Estimate**: 12–20 hours | **Prerequisites**: F01, F02, F24, F29
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-F36-04`: 4. Tune process noise and rejection thresholds on frozen independent cohorts ins...**
  - **Target File**: [`services/agribrain/layer05_asmae/retrovalidation/engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/retrovalidation/engine.py)
  - **Action Required**: 4. Tune process noise and rejection thresholds on frozen independent cohorts instead of selecting values for a passing pipeline flag.
  - **Estimate**: 12–20 hours | **Prerequisites**: F01, F02, F24, F29
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-F36-FA`: Package F36 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *An unsupported coordinate has explicit prior/reconstruction role and compatible objective weight.*
    - *Derived indices and shared teachers do not count as independent references.*
    - *Forecast skill, coverage and domain evidence are reported per variable and horizon against stated baselines.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T11: Operational reproducibility, provider resilience and publication integrity
- **Priority**: `Target` | **Estimate**: `100-180 hours` | **Dependencies**: `F09, F23, F25, F31, F35` | **R3 Requirements**: `AB-ARC-004, AB-ARC-005, AB-ARC-006, AB-ARC-007, AB-ARC-008, AB-ARC-009, AB-ARC-010, AB-ARC-011, AB-ARC-012, AB-DAT-001, AB-DAT-002, AB-DAT-009, AB-ASM-006, AB-ASM-007, AB-ASM-008`

- [ ] **`ST11-T11-01`: 1. Lock dependencies and produce code/image/model/config identities for each run...**
  - **Target File**: [`services/agribrain/layer0/data_gateway/request_broker.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/data_gateway/request_broker.py)
  - **Action Required**: 1. Lock dependencies and produce code/image/model/config identities for each run.
  - **Estimate**: 25–45 hours | **Prerequisites**: F09, F23, F25, F31, F35
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-T11-02`: 2. Trace all production entrypoints to one source admission and scoped publicati...**
  - **Target File**: [`services/agribrain/layer05_asmae/background_jobs.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/background_jobs.py)
  - **Action Required**: 2. Trace all production entrypoints to one source admission and scoped publication policy.
  - **Estimate**: 25–45 hours | **Prerequisites**: F09, F23, F25, F31, F35
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-T11-03`: 3. Run bounded provider outage, corruption, timeout, restart, duplicate and conc...**
  - **Target File**: [`services/agribrain/orchestrator_v2/storage.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/storage.py)
  - **Action Required**: 3. Run bounded provider outage, corruption, timeout, restart, duplicate and concurrent-writer drills.
  - **Estimate**: 25–45 hours | **Prerequisites**: F09, F23, F25, F31, F35
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-T11-04`: 4. Add operational telemetry for rejected evidence, stale state, scope, compute ...**
  - **Target File**: [`services/agribrain/app/main.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/app/main.py)
  - **Action Required**: 4. Add operational telemetry for rejected evidence, stale state, scope, compute resources and committed publication heads.
  - **Estimate**: 25–45 hours | **Prerequisites**: F09, F23, F25, F31, F35
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST11-T11-FA`: Package T11 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *A response never points to an uncommitted or foreign result.*
    - *Provider outage degrades only dependent capabilities.*
    - *Recovery reproduces the same canonical artifacts without duplicate execution.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 12: T01, T02, T12 (240–420 hours)

#### Package T01: One canonical coupled agricultural trajectory
- **Priority**: `Target` | **Estimate**: `80-140 hours` | **Dependencies**: `F03, F09, F10, F11` | **R3 Requirements**: `AB-WM-001, AB-AGR-002, AB-AGR-008, AB-ARC-001, AB-ARC-002, AB-ARC-003, AB-AGR-001`

- [ ] **`ST12-T01-01`: 1. Define a versioned X/Z/H/M/U snapshot with availability and support per coord...**
  - **Target File**: [`services/agribrain/world_model/canonical_worldline.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/canonical_worldline.py)
  - **Action Required**: 1. Define a versioned X/Z/H/M/U snapshot with availability and support per coordinate.
  - **Estimate**: 20–35 hours | **Prerequisites**: F03, F09, F10, F11
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T01-02`: 2. Specify operator-splitting order and feed L3/L4 constraints back into the nex...**
  - **Target File**: [`services/agribrain/world_model/belief_snapshot.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/belief_snapshot.py)
  - **Action Required**: 2. Specify operator-splitting order and feed L3/L4 constraints back into the next vegetation growth transition.
  - **Estimate**: 20–35 hours | **Prerequisites**: F03, F09, F10, F11
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T01-03`: 3. Link transition, analysis, management and diagnostic receipts to one predeces...**
  - **Target File**: [`services/agribrain/layer2_contracts/state_transition.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_contracts/state_transition.py)
  - **Action Required**: 3. Link transition, analysis, management and diagnostic receipts to one predecessor.
  - **Estimate**: 20–35 hours | **Prerequisites**: F03, F09, F10, F11
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T01-04`: 4. Publish read-only projections for L7-L10 rather than independent local physic...**
  - **Target File**: [`services/agribrain/orchestrator_v2/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/runner.py)
  - **Action Required**: 4. Publish read-only projections for L7-L10 rather than independent local physical reconstructions.
  - **Estimate**: 20–35 hours | **Prerequisites**: F03, F09, F10, F11
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T01-FA`: Package T01 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *A consumed-feedback receipt proves water/N limitations affected subsequent growth.*
    - *Daily, sparse, cold and corrected replay agree on the same interval semantics.*
    - *Every output resolves to the same authorized state head.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T02: Objective-specific longitudinal learning corpus
- **Priority**: `Target` | **Estimate**: `80-140 hours` | **Dependencies**: `F21, F22, F25, F26, F36, T01` | **R3 Requirements**: `AB-ML-001, AB-ML-006, AB-ML-007, AB-ML-008, AB-ML-014, AB-ML-015`

- [ ] **`ST12-T02-01`: 1. Define input tokens, masks, observation policy, labels and target-support eli...**
  - **Target File**: [`services/agribrain/world_model/historical_extractor.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/historical_extractor.py)
  - **Action Required**: 1. Define input tokens, masks, observation policy, labels and target-support eligibility per objective.
  - **Estimate**: 20–35 hours | **Prerequisites**: F21, F22, F25, F26, F36, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T02-02`: 2. Build immutable manifests and partition plots/sites/seasons/instruments befor...**
  - **Target File**: [`services/agribrain/asmae_learn/dataset_builder.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/asmae_learn/dataset_builder.py)
  - **Action Required**: 2. Build immutable manifests and partition plots/sites/seasons/instruments before fitting preprocessing.
  - **Estimate**: 20–35 hours | **Prerequisites**: F21, F22, F25, F26, F36, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T02-03`: 3. Permit partial and synthetic data for compatible objectives and prohibit prom...**
  - **Target File**: [`services/agribrain/asmae_learn/model_registry.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/asmae_learn/model_registry.py)
  - **Action Required**: 3. Permit partial and synthetic data for compatible objectives and prohibit promotion to independent biological truth.
  - **Estimate**: 20–35 hours | **Prerequisites**: F21, F22, F25, F26, F36, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T02-04`: 4. Produce reproducible dataset/model artifacts with lineage, consent, licensing...**
  - **Target File**: [`services/agribrain/world_model/historical_extractor.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/historical_extractor.py)
  - **Action Required**: 4. Produce reproducible dataset/model artifacts with lineage, consent, licensing and calibration metadata.
  - **Estimate**: 20–35 hours | **Prerequisites**: F21, F22, F25, F26, F36, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T02-FA`: Package T02 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *No target parent or post-cutoff input leaks into a predictive window.*
    - *Holdout partitions remain isolated across derived products.*
    - *A dataset snapshot can be regenerated byte-for-byte.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T12: Independent agronomic validation and reference field program
- **Priority**: `Target` | **Estimate**: `80-140 engineering plus seasonal research hours` | **Dependencies**: `F12, F20, F24, F29, F36, T01` | **R3 Requirements**: `AB-ASM-016, AB-AGR-011, AB-AGR-012, AB-MES-014, AB-ML-009, AB-ML-010, AB-OMG-013, AB-OMG-015`

- [ ] **`ST12-T12-01`: 1. Predeclare targets, horizons, cohorts, metrics and applicability domains befo...**
  - **Target File**: [`services/agribrain/ground_truth/registry.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/ground_truth/registry.py)
  - **Action Required**: 1. Predeclare targets, horizons, cohorts, metrics and applicability domains before tuning.
  - **Estimate**: 20–35 hours | **Prerequisites**: F12, F20, F24, F29, F36, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T12-02`: 2. Recruit independent reference plots with depth water, EC, delivery, canopy an...**
  - **Target File**: [`services/agribrain/layer05_asmae/retrovalidation/engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/retrovalidation/engine.py)
  - **Action Required**: 2. Recruit independent reference plots with depth water, EC, delivery, canopy and qualified crop/outcome observations.
  - **Estimate**: 20–35 hours | **Prerequisites**: F12, F20, F24, F29, F36, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T12-03`: 3. Compare simpler mechanistic/statistical baselines and inspect calibration, mi...**
  - **Target File**: [`services/agribrain/mesia/learning/asmae_evaluator.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/asmae_evaluator.py)
  - **Action Required**: 3. Compare simpler mechanistic/statistical baselines and inspect calibration, missingness and measurement selection.
  - **Estimate**: 20–35 hours | **Prerequisites**: F12, F20, F24, F29, F36, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T12-04`: 4. Run safe discriminating studies separating water shortage, salinity, hypoxia,...**
  - **Target File**: [`services/agribrain/ground_truth/registry.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/ground_truth/registry.py)
  - **Action Required**: 4. Run safe discriminating studies separating water shortage, salinity, hypoxia, hydraulic memory, delivery heterogeneity and biological alternatives.
  - **Estimate**: 20–35 hours | **Prerequisites**: F12, F20, F24, F29, F36, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST12-T12-FA`: Package T12 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Reference labels are independent of the model under evaluation.*
    - *Prospective results include uncertainty, sample size and negative outcomes.*
    - *Field evidence is reviewed against the declared target before any new capability is promoted.*
    - *[prisma/schema.prisma](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/prisma/schema.prisma) - blob `6aaee7b4292a3c1a9ee14eb427bd67437353c587`.*
    - *[services/agribrain/app/drone_routes.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/app/drone_routes.py) - blob `a0adcde3bf06c70a7a842f62511f9e8f8be9719d`.*
    - *[services/agribrain/app/main.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/app/main.py) - blob `9ea06f5f706e767491bd28653cc817823d300a6f`.*
    - *[services/agribrain/asmae_learn/dataset_builder.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/asmae_learn/dataset_builder.py) - blob `ddc08a80a47b4bdeb56206ea4d1976acd06dcbf8`.*
    - *[services/agribrain/asmae_learn/model_registry.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/asmae_learn/model_registry.py) - blob `2af5ea677200074cdc5c7136cdb5c0de0ea3f7d2`.*
    - *[services/agribrain/diagnostic_integration/contracts.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/diagnostic_integration/contracts.py) - blob `007a04f8c50312b9cf66e428dc80f8a2475bee85`.*
    - *[services/agribrain/diagnostic_integration/promotion_service.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/diagnostic_integration/promotion_service.py) - blob `3b8227b4d9ffda9c2ba38e1bad7c3b485da9dc3a`.*
    - *[services/agribrain/drone_control/dispatcher.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/drone_control/dispatcher.py) - blob `1974173b837846528a04e36886ad9f447d5d6c0f`.*
    - *[services/agribrain/drone_mission/__init__.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/drone_mission/__init__.py) - blob `7de41336d2734bd30a72c4b0c20fe57f46f30401`.*
    - *[services/agribrain/ground_truth/registry.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/ground_truth/registry.py) - blob `2486e1524d0a066df92ef6a17cd3018e05313093`.*
    - *[services/agribrain/irrigation_runtime/actuator.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/irrigation_runtime/actuator.py) - blob `97665b052fd083707589eb393926cbef9e50707f`.*
    - *[services/agribrain/irrigation_runtime/dispatcher.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/irrigation_runtime/dispatcher.py) - blob `e3233e45775992b5ca1e605ce7be91866a46c1ac`.*
    - *[services/agribrain/irrigation_runtime/safety.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/irrigation_runtime/safety.py) - blob `609095d7e46db1bd9abb197fb98537292a706d95`.*
    - *[services/agribrain/irrigation_runtime/validation.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/irrigation_runtime/validation.py) - blob `d2f8c0aad82ad3da45051be9541943a733a93383`.*
    - *[services/agribrain/layer0/data_gateway/request_broker.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/data_gateway/request_broker.py) - blob `e44494d091fcbb88230b7dff473cc3f9ed8d874b`.*
    - *[services/agribrain/layer0/kalman_engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/kalman_engine.py) - blob `31ed7e640e6133f7daa308221a3830576de4b4bd`.*
    - *[services/agribrain/layer0/observation_packet.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/observation_packet.py) - blob `860e617acae4c18458e99c8387efd4793f4cb91c`.*
    - *[services/agribrain/layer0/perception/drone_rgb/structural.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/perception/drone_rgb/structural.py) - blob `78bfdb0d30dc1b81371743eda642f7ae63161931`.*
    - *[services/agribrain/layer0/temporal_evidence.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/temporal_evidence.py) - blob `855a80727b2c7b70264b2190bcc63ceebe9529ab`.*
    - *[services/agribrain/layer0/wrappers.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/wrappers.py) - blob `2f500e08d0144395f0ede6d48598355b21f591c2`.*
    - *[services/agribrain/layer05_asmae/background_jobs.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/background_jobs.py) - blob `bb13b1a27b5996dbbe78747c327b08a4723ed7b9`.*
    - *[services/agribrain/layer05_asmae/constraints/radiometric.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/constraints/radiometric.py) - blob `12d21b471014147e45927d9114611351c87fb871`.*
    - *[services/agribrain/layer05_asmae/geometry/external_scene_loader.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/geometry/external_scene_loader.py) - blob `823bb1d2919756e58c4ca0536868db0e0d2d5a0f`.*
    - *[services/agribrain/layer05_asmae/history/worldline_service.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/history/worldline_service.py) - blob `0d30032eee9c939512cabf2453f6e4c7f88c8897`.*
    - *[services/agribrain/layer05_asmae/observation/index_state_mapping.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/observation/index_state_mapping.py) - blob `6854252e94740523f690c4e790733a64db8a75b8`.*
    - *[services/agribrain/layer05_asmae/resilient_posterior.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/resilient_posterior.py) - blob `452897042f01dd02c1be8fc1bef2395251fcd01a`.*
    - *[services/agribrain/layer05_asmae/retrovalidation/engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/retrovalidation/engine.py) - blob `4acfe79f40989e0076902e8be2b10023a5083d90`.*
    - *[services/agribrain/layer05_asmae/retrovalidation/future_projection.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/retrovalidation/future_projection.py) - blob `c82c4e4d7c299addde27235d16d34a264ab19937`.*
    - *[services/agribrain/layer05_asmae/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/runner.py) - blob `cb182ac4791510a78e2be8be6f77e5c4fbd4d503`.*
    - *[services/agribrain/layer05_asmae/training/exporter.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/training/exporter.py) - blob `61305e2180e15a8eac3b04e76b88e8f1750a6d58`.*
    - *[services/agribrain/layer10_sire/l10_frontend_bridge.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer10_sire/l10_frontend_bridge.py) - blob `d46dfe032ad18118f95d3234b3882ea1b0da7197`.*
    - *[services/agribrain/layer10_sire/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer10_sire/runner.py) - blob `9dc4ade7451de52ee6e4740d959c167811a63957`.*
    - *[services/agribrain/layer1_fusion/engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer1_fusion/engine.py) - blob `0d3f3bb734e2bfc9afd8f318e87e36ad0b8dafb9`.*
    - *[services/agribrain/layer1_fusion/eo_foundation_model.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer1_fusion/eo_foundation_model.py) - blob `0cf95efcdf54b765300f72b6a7aba0e264ee05cb`.*
    - *[services/agribrain/layer1_fusion/segmentation.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer1_fusion/segmentation.py) - blob `8bd43399cdfb5ff91e727f53ad7b51a1bb5ed0c4`.*
    - *[services/agribrain/layer2_contracts/state_transition.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer2_contracts/state_transition.py) - blob `51e3c52b7c557420e3c64c3054a4f1dc2d663d6a`.*
    - *[services/agribrain/layer2_veg_int/growth_engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer2_veg_int/growth_engine.py) - blob `63b566fec50d0265a02eec8dad03765012b64b47`.*
    - *[services/agribrain/layer3_decision/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_decision/runner.py) - blob `51c55a5b4c95e02f3a207dc9b918304244b8e39f`.*
    - *[services/agribrain/layer3_water/assimilation/water_state_assimilator.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/assimilation/water_state_assimilator.py) - blob `41ee312b7430d28b23a4b2eaa6144d79e0a3b4e1`.*
    - *[services/agribrain/layer3_water/contracts/assimilation_state.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/contracts/assimilation_state.py) - blob `0687a7dc7beceb04d59aabfb2a617d9c4ff8c07c`.*
    - *[services/agribrain/layer3_water/contracts/state_factory.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/contracts/state_factory.py) - blob `275bff4e7a20385b9a05c5948359ac6309b9c32a`.*
    - *[services/agribrain/layer3_water/contracts/water_state.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/contracts/water_state.py) - blob `6c9cd057043ff4b8c1f9ccc4fe8ee463d4ccebfa`.*
    - *[services/agribrain/layer3_water/root_zone/availability.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/root_zone/availability.py) - blob `2e97ceee04b89b73f9ea470ebffeea70956221d3`.*
    - *[services/agribrain/layer3_water/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/runner.py) - blob `67304903196ca68bcf7465718204c22e5f7de21d`.*
    - *[services/agribrain/layer3_water/soil/layered_water_balance.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/soil/layered_water_balance.py) - blob `e445703e0640c77df072b7fe72b2933352ebdfb6`.*
    - *[services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py) - blob `e13697be599862a9417e6f272bda37a09041e624`.*
    - *[services/agribrain/layer4_nutrients/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer4_nutrients/runner.py) - blob `b780f91594bdc2f227beebe696989289f25bdae2`.*
    - *[services/agribrain/layer4_nutrients/schema.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer4_nutrients/schema.py) - blob `8ab9a1bbaeb513cfc643f4f16131abe54b6317e4`.*
    - *[services/agribrain/layer6_exec/outcomes/metrics.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer6_exec/outcomes/metrics.py) - blob `aed318c372a47c19b9a600adbb51d38c3cdd5c89`.*
    - *[services/agribrain/layer6_yield/yield_forecast.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer6_yield/yield_forecast.py) - blob `1c3a5d0b0d0bfff4e8197705f31d905307c1e64b`.*
    - *[services/agribrain/layer7_planning/engines/yve_yield_distribution.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer7_planning/engines/yve_yield_distribution.py) - blob `4bf72cffda0f16370e2864bdc3768fc2cdff3ff8`.*
    - *[services/agribrain/layer7_planning/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer7_planning/runner.py) - blob `45216b1da80a5617e31357b2079e5aa0e1bcc3d5`.*
    - *[services/agribrain/layer7_planning/schema.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer7_planning/schema.py) - blob `15b1bafdb65011dc93c8469df42af6ef153f5443`.*
    - *[services/agribrain/layer8_prescriptive/engines/salinity_leaching.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/engines/salinity_leaching.py) - blob `7e58d605c40bd91368d54d82a6c189736927b0ac`.*
    - *[services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py) - blob `be683ec61bac7c9c50364b1c369fa04169a24dff`.*
    - *[services/agribrain/layer8_prescriptive/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/runner.py) - blob `ea9076293d58f37fb57140ca84d5fdc0f7b3a310`.*
    - *[services/agribrain/layer8_prescriptive/scenario_contract.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/scenario_contract.py) - blob `ad60b0f249214a8c0ddf8a3acb9c5caf9e3404d4`.*
    - *[services/agribrain/layer8_prescriptive/scheduler.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/scheduler.py) - blob `b1612db59a9357a4665e09036f1399988ec2d33d`.*
    - *[services/agribrain/layer9_interface/engines/conversation_memory.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer9_interface/engines/conversation_memory.py) - blob `f6551073a2c4d5ca387ce852fcd3a5ab3400ea42`.*
    - *[services/agribrain/layer9_interface/engines/semantic_cache.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer9_interface/engines/semantic_cache.py) - blob `6e65e05d7247fbd17badd1a6de95bd4f689cf196`.*
    - *[services/agribrain/layer9_interface/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer9_interface/runner.py) - blob `a0c6ae7baa06b2d739454d16828be0a5b9e9f306`.*
    - *[services/agribrain/mesia/assimilation/observability_analyzer.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/assimilation/observability_analyzer.py) - blob `20b9c909e6eeef55020c89021370c75f95bbc8dd`.*
    - *[services/agribrain/mesia/assimilation/spatial_lattice.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/assimilation/spatial_lattice.py) - blob `f7f9a224e9a253d234332dd818e7784825cf9ff3`.*
    - *[services/agribrain/mesia/behaviour/likelihood_engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/behaviour/likelihood_engine.py) - blob `105483ef6b7cafd749983b61657e496e605a3f4f`.*
    - *[services/agribrain/mesia/identity/correlators.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/identity/correlators.py) - blob `46be01c2694fd1cb06b62b4128372b8c94c367d8`.*
    - *[services/agribrain/mesia/lanes/wifi/csi_extractor.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/lanes/wifi/csi_extractor.py) - blob `e18e17ea09c6848b4c3a7ad484bde58b648946a9`.*
    - *[services/agribrain/mesia/learning/asmae_evaluator.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/learning/asmae_evaluator.py) - blob `60bdd8c8c7bfa332bfadc85d3424f1d718056dde`.*
    - *[services/agribrain/mesia/learning/masked_link_trainer.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/learning/masked_link_trainer.py) - blob `c0fc768d3cd807165e9159199556a20fa5aa00cf`.*
    - *[services/agribrain/mesia/learning/neural_receiver.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/learning/neural_receiver.py) - blob `bd224bb65c03f5c533d96ddb1009eafcc62e881f`.*
    - *[services/agribrain/mesia/service.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/service.py) - blob `76f0e881d4c6b5ddd4b4520ef03b68e2bb3412f2`.*
    - *[services/agribrain/orchestrator_v2/chat_adapter.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/orchestrator_v2/chat_adapter.py) - blob `1cff479e9c324eb6fca22c1fdf5a172f60497f4d`.*
    - *[services/agribrain/orchestrator_v2/run_entrypoint.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/orchestrator_v2/run_entrypoint.py) - blob `9a522ba111d3fdf939cb498dcd04a4f893052d73`.*
    - *[services/agribrain/orchestrator_v2/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/orchestrator_v2/runner.py) - blob `6706c3bcfb39ff22054cd9088b634cd2d5cf925c`.*
    - *[services/agribrain/orchestrator_v2/storage.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/orchestrator_v2/storage.py) - blob `f9886816eca2d9b648c12cca6e00867df69c34f9`.*
    - *[services/agribrain/scientific_contracts/observation.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/scientific_contracts/observation.py) - blob `c5bf8fbcf01aa005a789c5e5297e7b8b0b1239a4`.*
    - *[services/agribrain/sensor_runtime/registry.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/sensor_runtime/registry.py) - blob `2acc6f49135d7da9ba700b21870ed98839b901f9`.*
    - *[services/agribrain/sensor_runtime/security.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/sensor_runtime/security.py) - blob `85a654ddef1995d15b555f52d638bdbd905e30c8`.*
    - *[services/agribrain/sensor_runtime/storage.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/sensor_runtime/storage.py) - blob `23de3ea521c183e8e791014f0bd3f1cde8ccfb20`.*
    - *[services/agribrain/visual_sources/tile_proxy.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/visual_sources/tile_proxy.py) - blob `aecccec4275c25ea8d40821ea4b31b16dfd62193`.*
    - *[services/agribrain/world_model/belief_snapshot.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/belief_snapshot.py) - blob `b77f52bf8eafb2912d7aea0b99693bf5e9adc647`.*
    - *[services/agribrain/world_model/canonical_worldline.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/canonical_worldline.py) - blob `eebca540a391ce46ee0f93fab870c776214748a0`.*
    - *[services/agribrain/world_model/contracts.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/contracts.py) - blob `8ff042bae7f1259c9bb565203cb9ce184ab46986`.*
    - *[services/agribrain/world_model/forecast_archive.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/forecast_archive.py) - blob `cb5fc4cae9dbb74a13f33ed29af90669ef79c076`.*
    - *[services/agribrain/world_model/historical_extractor.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/historical_extractor.py) - blob `922577032f2a2fdaac2c3611e933a72fae9ebda2`.*
    - *[src/app/api/agribrain/intent/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/agribrain/intent/route.ts) - blob `de16f24d6f1522f645364bdc2d1380cb441410e9`.*
    - *[src/app/api/ai/chat/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/ai/chat/route.ts) - blob `8dcb383f7b3c2ef5fa19c7582257e0095e121850`.*
    - *[src/app/api/cycles/[id]/tasks/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/cycles/[id]/tasks/route.ts) - blob `f2d3ad12260b355afe246dd8e80e8562ae5082b0`.*
    - *[src/app/api/dashboard/stats/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/dashboard/stats/route.ts) - blob `bf35a17e86451fdbf9d7aca00c6d5ce94a1e3c48`.*
    - *[src/app/api/evidence/add/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/evidence/add/route.ts) - blob `15575f98b30e69cadefc22c28a291f152e6a2503`.*
    - *[src/app/api/inputs/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/inputs/route.ts) - blob `46235b0e39e68a51d3aeeba825402e75bf3e9b3a`.*
    - *[src/app/calendar/page.tsx](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/calendar/page.tsx) - blob `24347d354ae6c651b78d680da61c9ba47ea7b6c6`.*
    - *[src/app/farm/page.tsx](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/farm/page.tsx) - blob `0abb4476cd85bc6e7ab595439e1af16ab853e839`.*
    - *[src/lib/agribrain/gemini-advisor.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/lib/agribrain/gemini-advisor.ts) - blob `1a1d0de6250eb2c4c5253f302049675c48713e07`.*
    - *[src/lib/agribrain/surface-contract.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/lib/agribrain/surface-contract.ts) - blob `8bacf29c68ff8d15222f8b96592c55afd1163531`.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 13: T03, T06 (280–520 hours)

#### Package T03: Multimodal foundation representation and local adaptation
- **Priority**: `Target` | **Estimate**: `160-300 plus compute hours` | **Dependencies**: `T02, F27, F28` | **R3 Requirements**: `AB-ML-002, AB-ML-003, AB-ML-004, AB-ML-009, AB-ML-010, AB-ML-011, AB-ML-012, AB-ML-013`

- [ ] **`ST13-T03-01`: 1. Start with small time-series and single-modality baselines on the frozen corp...**
  - **Target File**: [`services/agribrain/layer1_fusion/eo_foundation_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action Required**: 1. Start with small time-series and single-modality baselines on the frozen corpus.
  - **Estimate**: 40–75 hours | **Prerequisites**: T02, F27, F28
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST13-T03-02`: 2. Train masked temporal/multimodal encoders with support and modality dropout....**
  - **Target File**: [`services/agribrain/mesia/learning/neural_receiver.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/learning/neural_receiver.py)
  - **Action Required**: 2. Train masked temporal/multimodal encoders with support and modality dropout.
  - **Estimate**: 40–75 hours | **Prerequisites**: T02, F27, F28
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST13-T03-03`: 3. Add shared X/Z alignment, calibrated heads, OOD detection and local adapters....**
  - **Target File**: [`services/agribrain/asmae_learn/model_registry.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/asmae_learn/model_registry.py)
  - **Action Required**: 3. Add shared X/Z alignment, calibrated heads, OOD detection and local adapters.
  - **Estimate**: 40–75 hours | **Prerequisites**: T02, F27, F28
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST13-T03-04`: 4. Evaluate transfer and rich-to-sparse distillation before federated deployment...**
  - **Target File**: [`services/agribrain/layer1_fusion/eo_foundation_model.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/eo_foundation_model.py)
  - **Action Required**: 4. Evaluate transfer and rich-to-sparse distillation before federated deployment with secure aggregation and privacy accounting.
  - **Estimate**: 40–75 hours | **Prerequisites**: T02, F27, F28
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST13-T03-FA`: Package T03 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Representation improves at least one predeclared held-out task beyond smaller baselines.*
    - *Missing modalities have defined behavior and measured degradation.*
    - *Artifact, preprocessing, split and calibration versions reproduce the result.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T06: MESIA native acquisition, metrology and capability commissioning
- **Priority**: `Target` | **Estimate**: `120-220 plus hardware/field work hours` | **Dependencies**: `F01, F05, F27, F28, F29, T02` | **R3 Requirements**: `AB-MES-001, AB-MES-002, AB-MES-003, AB-MES-004, AB-MES-005, AB-MES-006, AB-MES-007, AB-MES-008, AB-MES-012, AB-MES-013, AB-MES-015`

- [ ] **`ST13-T06-01`: 1. Archive native complex CSI and available GNSS/RF observations with instrument...**
  - **Target File**: [`services/agribrain/mesia/service.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/service.py)
  - **Action Required**: 1. Archive native complex CSI and available GNSS/RF observations with instrument and two-clock timing.
  - **Estimate**: 30–55 hours | **Prerequisites**: F01, F05, F27, F28, F29, T02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST13-T06-02`: 2. Version topology, actual poses, antenna, firmware, channel/band and calibrati...**
  - **Target File**: [`services/agribrain/mesia/lanes/wifi/csi_extractor.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/lanes/wifi/csi_extractor.py)
  - **Action Required**: 2. Version topology, actual poses, antenna, firmware, channel/band and calibration epochs.
  - **Estimate**: 30–55 hours | **Prerequisites**: F01, F05, F27, F28, F29, T02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST13-T06-03`: 3. Qualify missingness, nuisance covariance and geometric kernels against the ca...**
  - **Target File**: [`services/agribrain/mesia/behaviour/likelihood_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/behaviour/likelihood_engine.py)
  - **Action Required**: 3. Qualify missingness, nuisance covariance and geometric kernels against the canonical lattice.
  - **Estimate**: 30–55 hours | **Prerequisites**: F01, F05, F27, F28, F29, T02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST13-T06-04`: 4. Progress discovery/configuration/commissioning/calibration states and promote...**
  - **Target File**: [`services/agribrain/mesia/assimilation/spatial_lattice.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/assimilation/spatial_lattice.py)
  - **Action Required**: 4. Progress discovery/configuration/commissioning/calibration states and promote only validated individual capabilities.
  - **Estimate**: 30–55 hours | **Prerequisites**: F01, F05, F27, F28, F29, T02
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST13-T06-FA`: Package T06 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Commodity hardware modalities remain optional and explicitly characterized.*
    - *Calibration drift does not become biology.*
    - *Native records and instrument state reproduce the same qualified likelihood.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 14: T04, T05 (240–440 hours)

#### Package T04: Hybrid world model with conservative multi-horizon rollout
- **Priority**: `Target` | **Estimate**: `160-300 plus prospective data hours` | **Dependencies**: `T01, T02, T03, F23, F24, F12` | **R3 Requirements**: `AB-WM-002, AB-WM-003, AB-WM-004, AB-WM-005, AB-WM-006`

- [ ] **`ST14-T04-01`: 1. Retain mechanistic conserved transitions and fit bounded residual dynamics co...**
  - **Target File**: [`services/agribrain/world_model/contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/contracts.py)
  - **Action Required**: 1. Retain mechanistic conserved transitions and fit bounded residual dynamics conditioned on actual/scenario action.
  - **Estimate**: 40–75 hours | **Prerequisites**: T01, T02, T03, F23, F24, F12
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST14-T04-02`: 2. Forecast explicit states, latent representation and future observation distri...**
  - **Target File**: [`services/agribrain/world_model/forecast_archive.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/forecast_archive.py)
  - **Action Required**: 2. Forecast explicit states, latent representation and future observation distributions jointly.
  - **Estimate**: 40–75 hours | **Prerequisites**: T01, T02, T03, F23, F24, F12
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST14-T04-03`: 3. Test memory sufficiency against simpler Markov and history baselines....**
  - **Target File**: [`services/agribrain/layer05_asmae/retrovalidation/future_projection.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/retrovalidation/future_projection.py)
  - **Action Required**: 3. Test memory sufficiency against simpler Markov and history baselines.
  - **Estimate**: 40–75 hours | **Prerequisites**: T01, T02, T03, F23, F24, F12
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST14-T04-04`: 4. Evaluate paired intervention rollouts only where exposure, support and identi...**
  - **Target File**: [`services/agribrain/world_model/contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/contracts.py)
  - **Action Required**: 4. Evaluate paired intervention rollouts only where exposure, support and identification assumptions are valid.
  - **Estimate**: 40–75 hours | **Prerequisites**: T01, T02, T03, F23, F24, F12
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST14-T04-FA`: Package T04 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Rollouts remain physically admissible with explicit residual ledgers.*
    - *Prospective multi-horizon skill exceeds stated persistence/mechanistic baselines on held-out domains.*
    - *Counterfactual output states its identifying assumptions and uncertainty.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T05: Decision economics from shared outcome distributions
- **Priority**: `Target` | **Estimate**: `80-140 plus outcomes hours` | **Dependencies**: `F12, F13, F14, F15, T04` | **R3 Requirements**: `AB-DEC-001, AB-DEC-002, AB-DEC-003, AB-ECO-001, AB-ECO-002, AB-ECO-003, AB-ECO-004`

- [ ] **`ST14-T05-01`: 1. Add versioned price, labor, energy, water, input, quality and transport assum...**
  - **Target File**: [`services/agribrain/layer7_planning/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/runner.py)
  - **Action Required**: 1. Add versioned price, labor, energy, water, input, quality and transport assumptions.
  - **Estimate**: 20–35 hours | **Prerequisites**: F12, F13, F14, F15, T04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST14-T05-02`: 2. Derive margins and downside risk from joint outcome samples....**
  - **Target File**: [`services/agribrain/layer8_prescriptive/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/runner.py)
  - **Action Required**: 2. Derive margins and downside risk from joint outcome samples.
  - **Estimate**: 20–35 hours | **Prerequisites**: F12, F13, F14, F15, T04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST14-T05-03`: 3. Compare no-action, measurement and intervention policies with immutable hard ...**
  - **Target File**: [`services/agribrain/layer6_exec/outcomes/metrics.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/outcomes/metrics.py)
  - **Action Required**: 3. Compare no-action, measurement and intervention policies with immutable hard feasibility constraints.
  - **Estimate**: 20–35 hours | **Prerequisites**: F12, F13, F14, F15, T04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST14-T05-04`: 4. Evaluate value of information against transparent measurement baselines and a...**
  - **Target File**: [`services/agribrain/layer7_planning/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/runner.py)
  - **Action Required**: 4. Evaluate value of information against transparent measurement baselines and actual realized costs.
  - **Estimate**: 20–35 hours | **Prerequisites**: F12, F13, F14, F15, T04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST14-T05-FA`: Package T05 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Currency, date, area and quantity units are explicit.*
    - *Missing price becomes an assumption with sensitivity rather than observed value.*
    - *Policy value uses independently observed outcomes and qualified causal assumptions.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 15: T08, T09 (300–540 hours)

#### Package T08: Finish AgriWise operational records and financial workflows
- **Priority**: `Target` | **Estimate**: `180-320 hours` | **Dependencies**: `F32, F33, F34, F09` | **R3 Requirements**: `AW-PRO-001, AW-PRO-002, AW-PRO-005, AW-PRO-008, AW-PRO-009, AW-PRO-010, AW-PRO-012, AW-PRO-013, AW-PRO-014`

- [ ] **`ST15-T08-01`: 1. Complete farm/cycle/rotation history with delegated ownership and scoped task...**
  - **Target File**: [`prisma/schema.prisma`](file:///c:/Users/E-C/Desktop/agriwise/prisma/schema.prisma)
  - **Action Required**: 1. Complete farm/cycle/rotation history with delegated ownership and scoped task resources.
  - **Estimate**: 45–80 hours | **Prerequisites**: F32, F33, F34, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST15-T08-02`: 2. Add stock ledger, equipment use/maintenance and linked actual exposures....**
  - **Target File**: [`src/app/api/inputs/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/inputs/route.ts)
  - **Action Required**: 2. Add stock ledger, equipment use/maintenance and linked actual exposures.
  - **Estimate**: 45–80 hours | **Prerequisites**: F32, F33, F34, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST15-T08-03`: 3. Add typed livestock, market offers/orders/quality/storage/transport workflows...**
  - **Target File**: [`src/app/api/cycles/[id]/tasks/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/cycles/[id]/tasks/route.ts)
  - **Action Required**: 3. Add typed livestock, market offers/orders/quality/storage/transport workflows as proposed new modules.
  - **Estimate**: 45–80 hours | **Prerequisites**: F32, F33, F34, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST15-T08-04`: 4. Implement budget, costs and realized versus scenario economics without double...**
  - **Target File**: [`prisma/schema.prisma`](file:///c:/Users/E-C/Desktop/agriwise/prisma/schema.prisma)
  - **Action Required**: 4. Implement budget, costs and realized versus scenario economics without double counting.
  - **Estimate**: 45–80 hours | **Prerequisites**: F32, F33, F34, F09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST15-T08-FA`: Package T08 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Each workflow has persisted authorized records and error recovery.*
    - *Livestock events and costs use their own domain schema.*
    - *Stock/order/financial totals reconcile across cancellation, retry and correction.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T09: Unify language, voice, map and offline product projections
- **Priority**: `Target` | **Estimate**: `120-220 hours` | **Dependencies**: `F30, F31, F32, T01` | **R3 Requirements**: `AW-PRO-003, AW-PRO-004, AW-PRO-006, AW-PRO-007, AW-PRO-015, AW-PRO-016, AW-PRO-017, AW-PRO-018, AB-L9-001, AB-L9-002, AB-L9-003, AB-L9-004, AB-L9-005, AB-L9-006, AB-L9-007, AB-L9-008, AB-L9-009, AB-L9-010, AB-L10-001`

- [ ] **`ST15-T09-01`: 1. Resolve one intent to one canonical visible response and typed claims....**
  - **Target File**: [`src/app/api/agribrain/intent/route.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/app/api/agribrain/intent/route.ts)
  - **Action Required**: 1. Resolve one intent to one canonical visible response and typed claims.
  - **Estimate**: 30–55 hours | **Prerequisites**: F30, F31, F32, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST15-T09-02`: 2. Keep maps, numbers and explanations linked to the same state/support, includi...**
  - **Target File**: [`src/lib/agribrain/surface-contract.ts`](file:///c:/Users/E-C/Desktop/agriwise/src/lib/agribrain/surface-contract.ts)
  - **Action Required**: 2. Keep maps, numbers and explanations linked to the same state/support, including effective resolution.
  - **Estimate**: 30–55 hours | **Prerequisites**: F30, F31, F32, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST15-T09-03`: 3. Preserve values, negation and prohibitions across Arabic/French/voice and acc...**
  - **Target File**: [`services/agribrain/layer9_interface/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/runner.py)
  - **Action Required**: 3. Preserve values, negation and prohibitions across Arabic/French/voice and accessibility rendering.
  - **Estimate**: 30–55 hours | **Prerequisites**: F30, F31, F32, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST15-T09-04`: 4. Implement offline pending events with conflict resolution and visibly stale d...**
  - **Target File**: [`services/agribrain/layer10_sire/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/runner.py)
  - **Action Required**: 4. Implement offline pending events with conflict resolution and visibly stale decision cutoffs.
  - **Estimate**: 30–55 hours | **Prerequisites**: F30, F31, F32, T01
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST15-T09-FA`: Package T09 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (4 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Every visible response resolves to one canonical artifact.*
    - *UI and translation do not manufacture numerical science.*
    - *Offline actions reconcile without retroactively changing what a user knew.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

### Stage 16: T07, T10 (360–660 hours)

#### Package T07: Omega scientific investigation loop
- **Priority**: `Target` | **Estimate**: `240-440 plus experiments hours` | **Dependencies**: `F12, F21, F36, T01, T02, T04` | **R3 Requirements**: `AB-OMG-001, AB-OMG-002, AB-OMG-003, AB-OMG-004, AB-OMG-005, AB-OMG-006, AB-OMG-007, AB-OMG-008, AB-OMG-009, AB-OMG-010, AB-OMG-011, AB-OMG-012, AB-OMG-013, AB-OMG-014, AB-OMG-015, AB-OMG-016, AB-OMG-017, AB-OMG-018`

- [ ] **`ST16-T07-01`: 1. Create ScientificCase and a sealed epistemic Worldline for surprises, alterna...**
  - **Target File**: [`services/agribrain/diagnostic_integration/contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/diagnostic_integration/contracts.py)
  - **Action Required**: 1. Create ScientificCase and a sealed epistemic Worldline for surprises, alternatives and model inadequacy.
  - **Estimate**: 60–110 hours | **Prerequisites**: F12, F21, F36, T01, T02, T04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST16-T07-02`: 2. Implement Bayesian/mechanistic comparison, simulation/BEL and causal identifi...**
  - **Target File**: [`services/agribrain/world_model/canonical_worldline.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/canonical_worldline.py)
  - **Action Required**: 2. Implement Bayesian/mechanistic comparison, simulation/BEL and causal identification with explicit assumptions.
  - **Estimate**: 60–110 hours | **Prerequisites**: F12, F21, F36, T01, T02, T04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST16-T07-03`: 3. Propose discriminating measurements/experiments with measurement-selection an...**
  - **Target File**: [`services/agribrain/diagnostic_integration/promotion_service.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/diagnostic_integration/promotion_service.py)
  - **Action Required**: 3. Propose discriminating measurements/experiments with measurement-selection analysis, power, interference, stopping and consent.
  - **Estimate**: 60–110 hours | **Prerequisites**: F12, F21, F36, T01, T02, T04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST16-T07-04`: 4. Record falsification, negative results, independent replication and domain-bo...**
  - **Target File**: [`services/agribrain/diagnostic_integration/contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/diagnostic_integration/contracts.py)
  - **Action Required**: 4. Record falsification, negative results, independent replication and domain-bound knowledge artifacts before per-capability promotion.
  - **Estimate**: 60–110 hours | **Prerequisites**: F12, F21, F36, T01, T02, T04
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST16-T07-FA`: Package T07 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (3 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *A case follows surprise to competing explanations, discriminating prediction, experiment and replication.*
    - *A latent or symbolic equation remains a candidate until appropriate evidence separates alternatives.*
    - *Scientific success includes reduced ambiguity and negative findings, not only promoted claims.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

#### Package T10: Institutional aggregation and territorial world-model extension
- **Priority**: `Target` | **Estimate**: `120-220 plus regional data hours` | **Dependencies**: `T04, T05, T08, T09` | **R3 Requirements**: `AB-WM-007, AB-ECO-005, AW-PRO-014, AB-ARC-010, AB-ARC-011`

- [ ] **`ST16-T10-01`: 1. Authorize aggregation cohorts and suppress potentially identifying small grou...**
  - **Target File**: [`prisma/schema.prisma`](file:///c:/Users/E-C/Desktop/agriwise/prisma/schema.prisma)
  - **Action Required**: 1. Authorize aggregation cohorts and suppress potentially identifying small groups.
  - **Estimate**: 30–55 hours | **Prerequisites**: T04, T05, T08, T09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST16-T10-02`: 2. Model supply, water, market and environmental interactions hierarchically wit...**
  - **Target File**: [`services/agribrain/world_model/contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/contracts.py)
  - **Action Required**: 2. Model supply, water, market and environmental interactions hierarchically with uncertainty.
  - **Estimate**: 30–55 hours | **Prerequisites**: T04, T05, T08, T09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST16-T10-03`: 3. Evaluate policy and resource scenarios against independent regional outcomes....**
  - **Target File**: [`prisma/schema.prisma`](file:///c:/Users/E-C/Desktop/agriwise/prisma/schema.prisma)
  - **Action Required**: 3. Evaluate policy and resource scenarios against independent regional outcomes.
  - **Estimate**: 30–55 hours | **Prerequisites**: T04, T05, T08, T09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST16-T10-04`: 4. Version sovereign deployment, licensing, egress and review/appeal pathways fo...**
  - **Target File**: [`services/agribrain/world_model/contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/contracts.py)
  - **Action Required**: 4. Version sovereign deployment, licensing, egress and review/appeal pathways for high-impact use.
  - **Estimate**: 30–55 hours | **Prerequisites**: T04, T05, T08, T09
  - **Verification Check**: Code compiles cleanly under Python 3.12/3.13; contract assertions pass.

- [ ] **`ST16-T10-FA`: Package T10 End-to-End Acceptance Sign-off**
  - **Target Files**: All package targets (2 files)
  - **Action Required**: Run controlled local regression probe; verify criteria:
    - *Regional summaries preserve uncertainty and authorized cohort scope.*
    - *Policy scenarios are separated from observed effects.*
    - *Territorial capability is evaluated independently rather than inherited from a plot metric.*
  - **Deliverable**: Passed probe receipt and regression evidence record.

---

## 3. Verification & Proof Evidence Ledger
When completing each ticket, record the Git commit SHA, the verified probe receipt, and sign-off:

| Ticket ID | Completed Commit SHA | Local Probe Receipt / Evidence | Reviewer | Sign-off Date |
|---|---|---|---|:---:|
| `ST00-F37-01` | Pending | Import verification passes under clean Python 3.12 | Pending | Pending |
| `ST00-F37-FA` | Pending | All F37 target modules cold-import without warning | Pending | Pending |
| `ST01-F01-01` | Pending | Finite float validation rejects NaN and Inf | Pending | Pending |
| `ST01-F01-FA` | Pending | Observation packets serialize legitimate zeros faithfully | Pending | Pending |

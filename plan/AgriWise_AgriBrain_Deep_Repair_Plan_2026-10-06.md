# AgriWise and AgriBrain: deep code gap review and repair plan

Review date: 6 October 2026. Target: French R3 master monograph, 30 September 2026. Source baseline: main at `26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`.

## 1. Implementation decision

Correct the production foundations before making the learned world model or Omega depend on them. Retain the existing Next.js/TypeScript application, Prisma/MongoDB records, Python scientific engines, ASMAE, MESIA, Worldline contracts and specialist layers. The immediate problem is not absence of modules: it is inconsistent meanings and data across modules. A sensor admission can be invalid while its output acquires authority; a published flux can differ from the integrated flux; an archive can reject a record but later evaluate it from cache; an action acknowledgement can release ownership while physical execution continues.

This plan contains 40 correction packages and 12 capability-extension packages. Packages are units of delivery, not a count of distinct defects. Some bundle several related defects; others close an integration or empirical qualification gap. Each has source targets, R3 requirements, concrete steps, dependencies, engineering estimates and observable acceptance criteria. The companion traceability register retains all 153 R3 requirements and the original 90-package roadmap ownership, and adds the related repair packages. The 52 packages regroup and deepen that roadmap; their effort is not added on top of all 90 earlier packages.

## 2. Source state, evidence and review coverage

GitHub main was checked directly during this review. It remains at the baseline above. Draft PR #1 is open and unmerged at `bcb9eda6b8ef1aa6425f5828669f753a191227bc`. Its provenance, finite numeric, explicit prospective-cutoff, water authority and dashboard-error changes are proposed corrections, not current main behavior. The review does not merge, modify or deploy repository code.

The source tree has 4,016 entries. A broad filename filter identifies 1,713 production-code/configuration candidates under services/agribrain, src and prisma; this is an inventory count, not a claim that every candidate is executable or manually reviewed. The selected source corpus contains 510 unique production files matched to exact Git blob identities against the current tree, including the additional modules named in the supplied audit. Of these, 410 Python files passed a fresh syntax/AST check under Python 3.12.14. This does not verify the supplied audit’s complete 1,310-file Python 3.13 claim. The deep review concentrated on scientific and application boundaries; the work packages list their specific source targets in the pinned-reference appendix. Presence in the source corpus is not equivalent to a complete line-by-line manual review.

Production source and fresh controlled probes establish the findings. Repository test files, claimed suite results, the supplied audit’s assertions and stored/generated artifacts were not used as independent correctness evidence; its named production sources were checked directly. New probes ran production functions with local fixtures and a local driver, without network, database, provider or hardware calls. The L3 adapter and outcome/NUE function probes isolate production definitions while supplying lightweight surrounding contracts. PyTorch is unavailable, so MESIA tensor findings are static source findings; no neural training or inference result is claimed. No whole-repository suite, Next build, live MongoDB, satellite acquisition, irrigation hardware or drone was exercised in this review.

The R3 scientific chapters and complete requirement register were reread from the current document. R3 is the target specification. This review records implementation evidence separately and does not change the monograph's status-free description of the target. No finite selected review can establish that these are every remaining defect: complete source-inventory closure, runtime entrypoint tracing and field qualification are explicit work in T11 and T12.

Source links: [pinned main](https://github.com/webClone/AgriWise/tree/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4); [draft PR #1](https://github.com/webClone/AgriWise/pull/1).

## 3. Most consequential confirmed counterexamples

| Boundary | Actual controlled behavior | Required behavior |
|---|---|---|
| Daily weather | Jan 2 request with only Jan 3 weather used 12 mm of Jan 3 rainfall | Exact qualified forcing interval; no future observation substitution |
| Water flux | Integration used 1.32 mm transpiration while output published 8.52 mm; mass error was 0.0 | Publish integrated realized flux; separate posterior demand and analysis increment |
| Nitrogen residual | Declared 5 t/ha, 2% critical N, 50 kg applied, 30 kg soil supply produced 36.67 kg/ha additional N | 86.67 under the same declared 0.60 recovery convention |
| Irrigation quota | Zero remaining budget still sent a start with None or empty telemetry | Quota enforced regardless of telemetry presence |
| Irrigation duration | Expired event remained executing with empty telemetry | Independent duration watchdog stops expired operation |
| Acknowledgement | Physical local-driver execution continued after active command cleared and actuator became ONLINE | Operation ownership survives transport acknowledgement |
| Forecast conflict | Rejected mean=99 stayed in cache; another conflict probe scored rejected prediction at RMSE 0.0 | Evaluation reads the immutable committed forecast |
| Forecast validity | NaN horizon, 100-day horizon for a one-day target, crossed quantiles and negative sigma were accepted | Finite consistent validated distributions |
| Missing score | Empty quantile forecast produced score 0.0 | Missing score with reason, no skill credit |
| Historical forecast | Jan 2-known forecast valid Jan 3 was quarantined as a causality violation | Issuance-known future forecast is a permissible scenario input |
| Training manifest | Nested content mutated without hash change; two tenants had identical hashes | Frozen payload and partition-aware identity |
| EO inference | Failed ONNX session returned spectral fallback labelled onnx_foundation | Actual backend and artifact identity |
| Crop adapter | L7 crop/yield fields became unknown and 1.0 in L8 | Preserve actual crop and typed yield/economic fields |
| Action constraints | Empty weather record confirmed spray; leaching increased 21 mm cap to 27.7 mm | Mandatory qualified weather and immutable hard ceiling |
| Outcome interpretation | Verified exposure plus uncontrolled pre/post gave CAUSAL_ATTRIBUTED | Exposure truth separate from causal identification |

These fixtures demonstrate software behavior, not measured agricultural effects. The nitrogen probe fixes biomass, critical concentration and sink submodels to isolate the production residual equation. The water probe supplies an intentionally informative soil observation to make the prior/posterior flux mismatch visible. A soil clipping scenario in the fresh probe set closed correctly and is not reported as a proven clipping defect.

## 3a. Validation of the supplied forensic audit

The companion claim-verification report distinguishes two confirmed broken import statements, nine genuine undefined-name sites with different failure scopes, two reported cycles that actually cold-import successfully, and two alleged immediate NameErrors that are guarded or postponed. It also documents a newly reproduced nonce lost update and duplicate Python class identities under mixed package names. The 18 listed typing files need consumer-specific resolution, not a blanket claim of 19 immediate import failures. Aggregate audit counts are not adopted without a pinned manifest and matching runtime. These findings are incorporated in F37-F40.

## 4. Scientific contracts to settle before broad refactoring

### Time, support and data role

Use explicit observation/valid time, availability/commit time, decision cutoff and interval start/end. A future-valid weather forecast can be known today; a measurement taken yesterday but received tomorrow cannot initialize today's decision. A planned irrigation is a scenario. An actual delivered irrigation is an exposure with measurement uncertainty. Type each role before applying time rules.

Preserve units and support by variable: fractional vegetation cover versus canopy percent, volumetric water content versus storage depth, root-depth versus full-profile support, product mass versus nutrient mass, gross versus soil-boundary water and currency per area versus total cost. An adapter may derive an aggregate over a documented support; it may not silently replace a supplied heterogeneous profile with a loam prior.

### Transition, analysis and conservation

Define S as water storage in mm. For a physical interval, S_minus - S_previous = infiltration + capillary_rise - actual_evaporation - actual_transpiration - drainage + numerical_residual. If rainfall and irrigation are gross boundary inflow, include runoff explicitly and avoid subtracting it twice. For assimilation, S_plus = S_minus + analysis_increment + bound_correction. Store these receipts separately.

The realized flux belongs to the physical interval. Demand recomputed from S_plus is a posterior diagnostic or input to the next interval, not proof that the preceding interval used that amount. Check closure against the published rounded profile, bounded extraction and explicit numerical corrections.

### Residual nitrogen and yield distribution

Within the existing simple N convention, B t/ha with N_critical percent needs 10*B*N_critical kg/ha plant N. Existing recovered N is 0.60*(applied_N+soil_supply). The additional required application is max(0, target_plant_N-recovered_N)/0.60. Since applied N already enters recovered N, subtracting it again is incorrect. This algebra does not validate the universal use of 0.60; later pool and recovery calibration must replace that assumption where evidence supports it.

For a Gaussian distribution, P10/P90 are mean plus/minus 1.2815516 standard deviations. The 1.645 multiplier corresponds approximately to P5/P95. Clipping, mixtures and skew alter the distribution: derive quantiles from the actual distribution or samples. A median cannot generally substitute for a mean in expected economic value.

### Independence and discovery

Optical indices from one acquisition, teacher reconstructions, downstream state estimates and shared-model experts are dependent evidence. BMA success and radiometric consistency are useful diagnostics; they are not independent confirmation of every state variable. Mark target support and teacher dependence at the label and objective level.

Allow imperfect, partial and synthetic data for compatible discovery objectives. Distinguish a useful latent representation, a predictive capability, an agronomic interpretation and a causal/mechanistic claim. Each requires different evidence. Omega's main function is to investigate surprises, compare explanations and design discriminating experiments; authority controls support that scientific loop.

## 5. Hardcoded data and parameter policy

Do not remove every constant indiscriminately. Replace fabricated observations and schema fallback values; parameterize and version legitimate scientific assumptions; calibrate empirical settings on independent evidence.

| Example in source | Classification | Required treatment |
|---|---|---|
| Static calendar tasks dated Jan/Feb 2026 | Demo product data | Isolated demo scope; authorized real task API in normal use |
| Successful zero dashboard after DB error | Fabricated availability state | Explicit unavailable response; PR #1 pending |
| L4 FC/WP/saturation 0.30/0.15/0.45 despite real L3 profile | Incorrect adapter defaults | Consume actual supported profile/boundary receipt |
| Missing weather becomes 0 rain or 20/10 C prior | Imputation assumption | Explicit source role, timing, uncertainty and suitability limits |
| Neutral zoning 0.50 without rasters | Legitimate neutral prior if labelled | Retain; do not manufacture observed spatial structure |
| Vigor process noise 0.035; NDVI reject 0.35 | Empirical model settings | Configuration/artifact identity; independent calibration and sensitivity study |
| N recovery 0.60; heuristic yield/impact multipliers | Agronomic/model priors | Declare applicability, uncertainty and calibration; do not present as measured value |
| Decoder latent size 128 despite configurable encoder | Configuration mismatch | Derive from versioned model configuration |
| Spray wind gates 15 and 25 km/h | Competing policy constraints | Single contextual policy with validated units and final feasibility check |
| Post-action confidence from count of unqualified readings | Unsupported confidence heuristic | Qualify independent observations before calibrated confidence |

Inventory all remaining default/fallback/mock/random/sample paths by runtime role during T11. A documented prior may be used by a model with corresponding uncertainty; it must not appear as an observed field value. A simulation may be useful for research or commissioning and must keep that identity across serialization, cache, UI and export.

## 6. Delivery sequence and reviewable change batches

Interface drafting and reference-plot recruitment can overlap. Acceptance follows the package dependencies. Avoid one repository-wide rewrite: each batch should establish a coherent boundary, preserve compatibility and include a rollback path.

| Batch | Packages | Concrete deliverable |
|---|---|---|
| 0 Immediate import and replay fixes | Initial slices of F37-F40 and F35; complete integrations follow their dependencies | Supported cold startup, restored degraded paths and atomic nonce admission |
| 1 Evidence boundaries | F01, F02 and dashboard portion of F32 | Reviewed PR #1 plus admission/cutoff consumer coverage |
| 2 Water receipts | F04, F03 | Valid profiles and actual transition/analysis receipts |
| 3 Temporal trajectory | F06-F09 | Exact interval forcing, memory, digests and durable scoped replay |
| 4 Root/nutrient boundary | F05, F10, F11 | Depth-aware observations, true L3/L4 receipt and correct residual N |
| 5 Scenario constraints | F13-F15 | Typed yield/economic/crop scenarios and final hard feasibility |
| 6 Physical execution | F16-F19 | Independent quota/watchdog, operation lifecycle and reconciled retries |
| 7 Qualified outcomes | F20, F12, F34 | Actual exposures, eligible observations and correctly labelled associations |
| 8 Learning archives | F21-F24 | Frozen manifests, role-aware timing, committed forecasts and valid scoring |
| 9 EO and RF learning | F25-F29 | Truthful backend, full support identity and corrected MESIA tensor/objective contracts |
| 10 Application convergence | F30-F33, remaining F32 | Scoped conversations, canonical advice, real calendar and evidence writes |
| 11 Reliability and scientific qualification | F35, F36, T11 | Optional driver integrity, complete source-inventory closure and per-variable evaluation |
| 12 Coupled baseline and corpus | T01, T02, T12 | Reproducible coupled trajectory, frozen corpus and reference program |

Emergency operational boundaries in batches 5-7 should be repaired early alongside the scientific data work; the table describes coherent batches, not a requirement to delay actuator safety until every scientific package finishes. Live control stays behind its commissioning acceptance. Manual qualified exposure logging can work independently of actuator automation.

### Release gates

R0: corrected boundary release. The reproduced P0 cases have the required behavior; invalid evidence cannot acquire authority or numerical skill, and unsafe/missing action constraints do not become confirmed execution. Selected fixes alone are not a declaration that the entire application is production validated.

R1: coupled trajectory release. Daily versus sparse replay, cold restart, late correction, withdrawals, parameter epochs and concurrent writers have consistent results. Water and nutrient receipts reconcile and the growth transition consumes supported hydraulic/nutrient feedback.

R2: corpus and representation release. Input cutoffs, objective eligibility, independent splits and model artifacts are frozen. Start with simpler baselines, missing modalities and domain calibration. RF/EO discovery can proceed before biological qualification using compatible objectives.

R3: world-model shadow release. Hybrid trajectories show prospective multi-horizon skill and calibrated uncertainty within declared domains. Scenario actions remain assumptions; only delivered exposures enter historical action truth. Paired outcomes are interpreted according to identification evidence.

R4: scientific discovery and complete product releases. Omega cases progress through alternatives, discriminating experiments, falsification and replication. Product workflow, language/offline and institutional extensions have their own gates; none inherit biological or policy validity from a software suite.

## 7. First working cycle

1. Freeze baseline, source manifest and the exact PR #1 diff. Check its call-site compatibility and explicit-cutoff semantics; keep main and proposed PR behavior distinct.
2. Repair the independent import, replay-admission and undefined-name slices in F37-F40. Complete their shared-store, authentication and publication integration after the declared dependencies; an early local fix is not full package acceptance.
3. Correct F04/F03 and F06 first in the scientific branch: geometry, realized flux receipt and exact dated forcing. Preserve the existing improved ASMAE sensor-support behavior.
4. Correct F16-F18 and F15 in independent small execution/constraint changes. Use a local controller fixture before any commissioned-device run.
5. Correct F21-F24 before creating new training or forecast evaluation artifacts. Retain older committed artifacts and add explicit retrospective invalidation/review records rather than silently overwriting them.
6. Connect F10/F11 and F14 with actual typed upstream objects. Confirm the end-to-end consumer sees the same units, support and values.
7. Remove calendar/demo and error substitutions, then converge public advice through the authorized canonical response path.
8. Close remaining correction packages, establish T01 and create the objective-specific T02 corpus. Begin T12 reference recruitment and Omega case/interface design in parallel.

Use engineering hours instead of promising a calendar date without an assigned team. Per-package estimates cover implementation, focused verification and integration review; they are planning ranges, not measured work logs. They exclude data acquisition, hardware procurement, seasonal outcomes and independent replication. Packages overlap the earlier roadmap and should be re-estimated after the first accepted boundary changes.

## 8. Verification and rollback rules

For each change: pin the production baseline, reproduce the failure from the production function or real call boundary, implement the smallest coherent correction, then verify the required invariant with varied inputs and its downstream consumer. Compile/type-check/build the affected service and run appropriate regression suites as engineering checks. Suite success supplements the contract/probe evidence; it does not establish agronomic or causal truth.

Numerical validation must cover finite values, valid zero, extreme but valid inputs, support/unit conversion, heterogeneous depths, missingness, bounded extraction and actual published receipt closure. Temporal validation covers earlier-issued forecasts, late measurements, date/timezones, supersession, cancellation and both daily/sparse replay. Persistence validation covers cache-versus-disk agreement, crash/restart, corrupt payloads, concurrent conditional writes and immutable publication. Execution validation covers acknowledgement versus delivery, absent telemetry, quota reservation, timeout, duplicate/reordered messages, stop/retry and unknown controller state.

Migrate old records additively with explicit schema versions. Preserve old issuance artifacts. Recompute retrospective views as new records referencing corrections; invalidate dependent caches and learning manifests by content identity. Deploy behind explicit capability flags where necessary. Roll back by capability/version, retaining receipts and delivered-action truth. An operational rollback must not reclassify an actually delivered dose as absent.

## 9. Detailed correction packages

### F01 - Qualify provenance and numeric evidence at every admission boundary

Priority: P0. Evidence class: Main defect; partial correction in draft PR #1. Engineering estimate: 24-40 hours. Dependencies: none.

R3 requirements: AB-DAT-005, AB-DAT-006, AB-ARC-005, AB-ARC-006.

**Source finding / basis.** Main admits infinite soil values and reports assimilation. A fresh probe moved every layer from 0.20 to 0.4499. PR #1 adds finite numeric checks and fail-closed provenance, but is unmerged.

**Production targets.**

- `services/agribrain/layer0/observation_packet.py`
- `services/agribrain/layer0/wrappers.py`
- `services/agribrain/scientific_contracts/observation.py`
- `services/agribrain/layer3_water/assimilation/water_state_assimilator.py`

**Implementation steps.**

1. Review PR #1 against source consumers and preserve its corrected zero and missingness semantics.
2. Make accepted/rejected components explicit before authority or solver selection.
3. Carry source roles through all typed and dictionary adapters without allowing caller promotion.
4. Apply the same qualification to weather, RF, crop observations and training admission, with migration of ambiguous legacy records.

**Completion criteria.**

- NaN, infinity, booleans and malformed numeric values cannot alter state or training weight.
- Legitimate zero survives serialization and round trips.
- Authority and accepted counts follow actual admitted components.

### F02 - Enforce observation time and availability at issuance

Priority: P0. Evidence class: Main defect; partial correction in draft PR #1. Engineering estimate: 24-40 hours. Dependencies: F01.

R3 requirements: AB-DAT-004, AB-DAT-014, AB-ML-008.

**Source finding / basis.** PR #1 repairs explicit prospective initialization, including nested future soil records. That does not establish availability filtering throughout retrospective reconstruction, Worldline extraction and downstream adapters.

**Production targets.**

- `services/agribrain/layer05_asmae/resilient_posterior.py`
- `services/agribrain/layer0/temporal_evidence.py`
- `services/agribrain/world_model/historical_extractor.py`

**Implementation steps.**

1. Retain the PR explicit-cutoff fix and require both observation and availability provenance for prospective measurements.
2. Define typed timing for measurements, priors, forecasts and management scenarios.
3. Propagate the decision cutoff through each layer and reject records with unresolved eligibility.
4. Record every excluded revision and force historical replays to use the archived knowledge view.

**Completion criteria.**

- Late-arriving measurements and revised weather are excluded from earlier issuance.
- Earlier-issued future forecasts remain eligible as scenarios.
- Replay identifies exactly which input versions were available.

### F03 - Publish the fluxes actually integrated and separate analysis increments

Priority: P0. Evidence class: Confirmed controlled production probe. Engineering estimate: 24-40 hours. Dependencies: F01.

R3 requirements: AB-AGR-004, AB-AGR-005, AB-AGR-008.

**Source finding / basis.** Fresh pipeline probe: propagated transpiration demand 1.32 mm, published posterior-based transpiration 8.52 mm, reported mass error 0.0. The posterior also gains water from assimilation, without a separately published storage increment.

**Production targets.**

- `services/agribrain/layer3_water/runner.py`
- `services/agribrain/layer3_water/soil/layered_water_balance.py`
- `services/agribrain/layer3_water/contracts/water_state.py`

**Implementation steps.**

1. Return a transition receipt containing bounded actual evaporation, transpiration, drainage, infiltration and initial/final storage.
2. Publish that receipt as realized interval flux and expose posterior demand as a separate next-interval diagnostic.
3. Return an analysis receipt with storage increment, covariance change and bound corrections.
4. Calculate closure from the serialized state and receipt rather than an internal pre-rounding ledger.

**Completion criteria.**

- Integrated and published realized fluxes agree.
- Physical closure includes bounded extraction and quantization, while analysis increments are explicit.
- Assimilation cannot retroactively rewrite the water used in the preceding interval.

### F04 - Validate soil geometry and hydraulic parameter vectors

Priority: P0. Evidence class: Confirmed controlled production probes. Engineering estimate: 12-20 hours. Dependencies: F01.

R3 requirements: AB-AGR-003, AB-DAT-007.

**Source finding / basis.** The production factory accepts nonmonotonic depths [30,10] and negative conductivity [-1,-1]. These can create negative layer thickness, storage or drainage inputs even though retention ordering passes.

**Production targets.**

- `services/agribrain/layer3_water/contracts/state_factory.py`
- `services/agribrain/layer3_water/soil/layered_water_balance.py`

**Implementation steps.**

1. Require a nonempty strictly increasing finite positive depth vector.
2. Validate the length and physical domain of every retention, conductivity and van Genuchten vector.
3. Reject degenerate saturation/residual intervals and inconsistent units before computing suction.
4. Document parameter provenance and distinguish measured values from texture priors.

**Completion criteria.**

- Nonmonotonic, repeated, zero or nonfinite depths are rejected.
- Negative conductivity and invalid n or alpha cannot enter the solver.
- Valid heterogeneous profiles retain their parameters and storage.

### F05 - Use depth-aware soil observations and carry covariance

Priority: P1. Evidence class: Static contract defect and scientific integration gap. Engineering estimate: 32-56 hours. Dependencies: F01, F04.

R3 requirements: AB-AGR-009, AB-DAT-007, AB-MES-013.

**Source finding / basis.** Probe profile values are assigned by array position to model layers. The contract does not provide a general per-reading depth support operator; a surface reading and a root-depth reading cannot be safely treated as interchangeable.

**Production targets.**

- `services/agribrain/layer3_water/contracts/assimilation_state.py`
- `services/agribrain/layer3_water/assimilation/water_state_assimilator.py`
- `services/agribrain/layer3_water/root_zone/availability.py`

**Implementation steps.**

1. Represent individual readings with depth interval, location, time, instrument and noise.
2. Construct the vertical observation operator from overlap or point support instead of list index.
3. Preserve correlated posterior uncertainty by layer and carry unsupported-depth flags to L4 and decisions.
4. Treat thermal and RF surrogates as calibrated conditional constraints with their own support.

**Completion criteria.**

- Reordered input readings yield the same update.
- A shallow reading cannot claim direct full root-zone observation.
- Depth mismatch and absent support produce a qualified partial result.

### F06 - Stop substituting another date at the weather endpoint

Priority: P0. Evidence class: Confirmed controlled production probe. Engineering estimate: 12-20 hours. Dependencies: F02.

R3 requirements: AB-DAT-004, AB-DAT-005, AB-AGR-007, AB-AGR-013.

**Source finding / basis.** When the target date has no weather, rec = next(iter(weather_daily.values())) supplies an arbitrary record. A Jan 2 request with only Jan 3 rain returned a Jan 2 state using 12 mm of Jan 3 rainfall.

**Production targets.**

- `services/agribrain/layer3_decision/runner.py`

**Implementation steps.**

1. Remove arbitrary-record selection at the endpoint.
2. Resolve forcing by exact interval and declared timezone.
3. Route missing target forcing through an explicit prior or missing-data result with uncertainty and source role.
4. Apply the same policy to intermediate gaps and keep zero rainfall distinct from unobserved rainfall.

**Completion criteria.**

- No future record supplies a historical daily forcing.
- Missing rainfall is visible and cannot become observed zero.
- Daily and sparse executions use identical qualified interval inputs.

### F07 - Remove future canopy fallback and restore evaporation memory

Priority: P1. Evidence class: Static integration defects. Engineering estimate: 24-40 hours. Dependencies: F03, F04, F06.

R3 requirements: AB-AGR-006, AB-AGR-007, AB-AGR-008.

**Source finding / basis.** The historical vegetation extractor eventually falls back to the current veg_state when no earlier canopy exists. The water runner defaults days_since_wetting to zero and calculates top storage as theta[0]*100 regardless of actual top-layer thickness.

**Production targets.**

- `services/agribrain/layer3_decision/runner.py`
- `services/agribrain/layer3_water/runner.py`

**Implementation steps.**

1. Resolve historical canopy only from records eligible for each step and label persisted priors.
2. Remove endpoint canopy fallback into earlier days unless it is explicitly a scenario reconstruction.
3. Restore the previous evaporation state and wetted fraction into each step.
4. Derive surface storage from actual layer thickness and propagate method-specific wetting.

**Completion criteria.**

- Earlier steps never consume later observed canopy.
- A dry sequence advances evaporation memory across restart and sparse replay.
- Changing top-layer thickness changes surface storage consistently.

### F08 - Make trajectory invalidation include parameters and predecessor content

Priority: P1. Evidence class: Static cache defect. Engineering estimate: 24-40 hours. Dependencies: F03, F04, F06.

R3 requirements: AB-DAT-011, AB-DAT-012, AB-AGR-007.

**Source finding / basis.** _state_digest returns theta values when present and omits the rest of a SoilWaterState. Step forcing hashes also omit soil parameter epoch and model identity. A profile correction can therefore leave earlier cached transitions intact.

**Production targets.**

- `services/agribrain/layer3_decision/runner.py`

**Implementation steps.**

1. Replace repr and rounded scalar fingerprints with canonical content digests.
2. Include full profile, crop/geometry epoch, solver version, observation payload and predecessor digest.
3. Invalidate from the earliest changed transition for parameter corrections as well as weather changes.
4. Preserve previously issued forecasts while creating a separate corrected retrospective trajectory.

**Completion criteria.**

- Identical moisture with different conductivity or retention cannot share a trajectory key.
- Parameter changes recompute affected predecessors and descendants.
- Repeated identical requests are idempotent.

### F09 - Persist coupled state with scoped concurrency and restart recovery

Priority: P1. Evidence class: Integration gap. Engineering estimate: 48-80 hours. Dependencies: F02, F03, F08.

R3 requirements: AB-DAT-003, AB-DAT-012, AB-DAT-013, AB-ARC-008, AB-AGR-006.

**Source finding / basis.** Hydraulic histories, event versions and withdrawals are held in process dictionaries keyed principally by plot ID. These cannot themselves establish durable multi-replica recovery, tenant scope or an atomic predecessor chain.

**Production targets.**

- `services/agribrain/layer3_decision/runner.py`
- `services/agribrain/world_model/canonical_worldline.py`
- `services/agribrain/layer05_asmae/history/worldline_service.py`

**Implementation steps.**

1. Move parameter epochs, action versions and hydraulic checkpoints to the canonical scoped store.
2. Use tenant, plot, cycle, geometry and namespace in identities.
3. Commit transition and analysis receipts with compare-and-swap on the predecessor head.
4. Recover from committed checkpoints and replay appended corrections under a fenced lease.

**Completion criteria.**

- Cold restart equals warm replay.
- Two workers cannot publish different successors for one head.
- Cancellation, withdrawal and late correction survive restart and replica changes.

### F10 - Repair the L3-to-L4 water boundary

Priority: P0. Evidence class: Static schema mismatch. Engineering estimate: 24-40 hours. Dependencies: F03, F04, F05.

R3 requirements: AB-AGR-008, AB-AGR-010, AB-DAT-007.

**Source finding / basis.** L4 reads theta_fc, theta_wp, theta_sat and root_zone_storage_mm from SoilWaterState, which exposes profiles and total_profile_water_mm. Defaults 0.30/0.15/0.45 and 0.7*TAW replace actual supplied soil information.

**Production targets.**

- `services/agribrain/layer4_nutrients/runner.py`
- `services/agribrain/layer3_water/contracts/water_state.py`
- `services/agribrain/layer3_water/contracts/assimilation_state.py`

**Implementation steps.**

1. Consume a typed depth-aware Layer3ToLayer4BoundaryReceipt.
2. Integrate storage and retention over the defined root support instead of replacing them with generic scalars.
3. Keep daily drainage flux separate from seasonal accumulated drainage.
4. Carry missing support and uncertainty into nutrient, salinity and leaching calculations.

**Completion criteria.**

- A non-loam profile reaches L4 without generic substitution.
- Root-zone storage matches the same depth integration as L3.
- One daily drainage receipt is counted once in cumulative nutrient transport.

### F11 - Correct residual nitrogen demand and expose conservative pools

Priority: P0. Evidence class: Confirmed controlled formula probe. Engineering estimate: 24-48 hours. Dependencies: F10.

R3 requirements: AB-AGR-010, AB-AGR-008.

**Source finding / basis.** Actual N already includes applied N. The residual deficit is divided by recovery efficiency and then applied N is subtracted again. Controlled 5 t/ha, critical N 2%, 50 kg applied and 30 kg soil supply returned 36.67 rather than 86.67 kg/ha under the same assumed 0.60 efficiency.

**Production targets.**

- `services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py`
- `services/agribrain/layer4_nutrients/runner.py`

**Implementation steps.**

1. Remove the second subtraction under the existing residual-demand convention.
2. Define whether each quantity is cumulative applied, available soil, recovered plant N or additional dose.
3. Replace independent cumulative heuristics with conservative mineralization, uptake, loss and application pools.
4. Carry dose timing, formulation and recovery uncertainty into recommendations.

**Completion criteria.**

- The controlled residual case returns 86.67 under its declared assumptions.
- Zero deficit produces zero additional demand.
- Nitrogen stock changes reconcile uptake, losses and applied mass.

### F12 - Separate exposure verification from causal attribution

Priority: P0. Evidence class: Confirmed controlled production-function probe. Engineering estimate: 20-32 hours. Dependencies: F02.

R3 requirements: AB-EXE-005, AB-WM-006, AB-OMG-008.

**Source finding / basis.** A verified execution timestamp immediately assigns CAUSAL_ATTRIBUTED even though the implemented estimator is PRE_POST. A controlled +0.1 NDVI comparison received that causal label without a control or identification design.

**Production targets.**

- `services/agribrain/layer6_exec/outcomes/metrics.py`

**Implementation steps.**

1. Keep delivered exposure as a separate qualification field.
2. Label uncontrolled pre/post metrics as observed associations even after verified execution.
3. Require an explicit identification record before estimating or labelling causal effect.
4. Integrate by real timestamps, preserve valid zero indices and record missing confounder data.

**Completion criteria.**

- Verified exposure alone never grants causal effect.
- Unequal sampling intervals do not masquerade as NDVI-time integral changes.
- Negative results and unknown confounding remain in the outcome record.

### F13 - Correct yield quantiles and distinguish calibrated distributions from heuristics

Priority: P1. Evidence class: Static numerical and semantic defects. Engineering estimate: 24-48 hours. Dependencies: F02, F12.

R3 requirements: AB-AGR-014, AB-ML-005, AB-ECO-002.

**Source finding / basis.** L6 labels mean +/-1.645*sigma as P10/P90; these are approximately P5/P95 for a Gaussian. L7 constructs heuristic bands and returns p50 as mean despite explicitly noting skew.

**Production targets.**

- `services/agribrain/layer6_yield/yield_forecast.py`
- `services/agribrain/layer7_planning/engines/yve_yield_distribution.py`
- `services/agribrain/layer7_planning/schema.py`

**Implementation steps.**

1. Use one distribution contract with quantile levels and support.
2. Correct normal P10/P90 to +/-1.2815516 sigma when a Gaussian assumption is actually intended.
3. Label L7 deterministic penalty bands as heuristic until fitted and calibrated.
4. Share joint yield, quality and economic samples across L6/L7/L8 instead of treating their numbers as interchangeable.

**Completion criteria.**

- Quantile labels match their mathematical levels.
- Mean and median are distinct when the distribution is skewed.
- Mixture tails are derived from the mixture distribution and prospective coverage is reported.

### F14 - Repair L7-to-L8 crop scenario mapping

Priority: P0. Evidence class: Confirmed adapter probe. Engineering estimate: 12-20 hours. Dependencies: F13.

R3 requirements: AB-EXE-001, AB-DEC-001, AB-ECO-002.

**Source finding / basis.** The actual L7 fields are crop, yield_dist and econ. from_crop_planning_option reads crop_type, expected_yield or expected_profit. A representative actual-schema option lost potato and yield 42, returning unknown and 1.0.

**Production targets.**

- `services/agribrain/layer7_planning/schema.py`
- `services/agribrain/layer8_prescriptive/scenario_contract.py`
- `services/agribrain/layer8_prescriptive/runner.py`

**Implementation steps.**

1. Map the actual typed L7 contract explicitly.
2. Preserve stable option ID, crop, yield distribution, economics and units.
3. Reject a schema mismatch instead of falling back to unknown and unitless 1.0.
4. Carry scenario provenance and compare operational interventions separately from seasonal crop choices.

**Completion criteria.**

- Actual CropOptionEvaluation preserves crop and distribution.
- Profit can never fill a yield field.
- Missing required option data produces a qualified unavailable scenario.

### F15 - Unify weather constraints and final hard action limits

Priority: P0. Evidence class: Confirmed controlled probes plus static scheduler defect. Engineering estimate: 32-56 hours. Dependencies: F01, F06, F14.

R3 requirements: AB-DEC-003, AB-ECO-003, AB-EXE-001.

**Source finding / basis.** Missing spray weather remains allowed. [{}] schedules a spray as CONFIRMED. Leaching raised max_safe from 21 to 27.7 mm and recommended 23.1. Scheduler derives dates by list position and its wind threshold differs from the drift gate.

**Production targets.**

- `services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py`
- `services/agribrain/layer8_prescriptive/engines/salinity_leaching.py`
- `services/agribrain/layer8_prescriptive/scheduler.py`
- `services/agribrain/layer8_prescriptive/runner.py`

**Implementation steps.**

1. Normalize weather units, valid intervals and quality before every action constraint.
2. Treat absent mandatory safety variables as unqualified, with a clear measurement or confirmation requirement.
3. Preserve immutable hard constraints and never increase their ceiling during agronomic adjustments.
4. Apply one final feasibility pass after all rate modifiers, zone aggregation and scheduling, including dated legal/resource constraints.

**Completion criteria.**

- Missing or invalid wind cannot yield a confirmed spray.
- Every final dose stays within the original hard cap and budget.
- Reordering dated forecast rows does not change the chosen valid slot.

### F16 - Enforce quota and watchdog independently of telemetry

Priority: P0. Evidence class: Confirmed local-driver probes. Engineering estimate: 24-40 hours. Dependencies: F01.

R3 requirements: AB-EXE-004, AB-DEC-003.

**Source finding / basis.** An exhausted quota blocked dispatch only when a nonempty readings dictionary was supplied. An expired duration stopped the local driver only after nonempty readings arrived. Both checks currently sit behind if sensor_readings.

**Production targets.**

- `services/agribrain/irrigation_runtime/dispatcher.py`
- `services/agribrain/irrigation_runtime/safety.py`

**Implementation steps.**

1. Always check water budgets before command submission.
2. Run duration watchdogs on an independent monotonic timer.
3. Define critical sensor freshness and missingness policies explicitly.
4. Persist reservation and delivered-water reconciliation so concurrent commands cannot overspend quota.

**Completion criteria.**

- Zero remaining budget produces zero physical start calls with None, empty or present telemetry.
- Duration expiration stops a running event without new sensor messages.
- Two reservations cannot jointly exceed the remaining budget.

### F17 - Keep actuator operation state until physical completion

Priority: P0. Evidence class: Confirmed local-driver probes. Engineering estimate: 24-40 hours. Dependencies: F16.

R3 requirements: AB-EXE-002, AB-EXE-003, AB-EXE-004.

**Source finding / basis.** On successful start acknowledgement, execute_with_safety clears active_command and sets ONLINE although the driver is physically running. A second start was accepted; excessive-flow checks lost the commanded rate. STOP_ZONE is also rejected while EXECUTING.

**Production targets.**

- `services/agribrain/irrigation_runtime/actuator.py`
- `services/agribrain/irrigation_runtime/dispatcher.py`

**Implementation steps.**

1. Separate command transport acknowledgement from operation completion.
2. Retain operation ownership, target flow and active event until verified stop/completion.
3. Allow stop and emergency stop through busy-state checks.
4. Reconcile controller telemetry against the persistent operation rather than transport status.

**Completion criteria.**

- Second conflicting start is rejected while physical execution continues.
- Dynamic flow checks retain the target command.
- Normal stop remains admissible during execution and is recorded once.

### F18 - Reconcile ambiguous command failures before retry

Priority: P0. Evidence class: Confirmed local-driver probe. Engineering estimate: 24-40 hours. Dependencies: F17.

R3 requirements: AB-EXE-003, AB-ARC-008.

**Source finding / basis.** A transient acknowledgement failure leaves EXECUTING; the retry is then rejected by the same busy-state validator. Only one send occurred, followed by FAILED, despite the declared retry path.

**Production targets.**

- `services/agribrain/irrigation_runtime/actuator.py`
- `services/agribrain/irrigation_runtime/dispatcher.py`

**Implementation steps.**

1. Give retries the same operation identity and attempt sequence.
2. Query controller state after timeout to distinguish applied, not applied and unknown.
3. Permit only safe idempotent retries and retain ownership during uncertainty.
4. Restore event and controller reconciliation on process restart.

**Completion criteria.**

- A retry never duplicates a delivered dose.
- An acknowledgement timeout does not automatically mean no physical application.
- Own-operation retry is not rejected as an unrelated competing command.

### F19 - Implement interlock persistence, debounce and stable violation keys

Priority: P1. Evidence class: Confirmed controlled monitor probe. Engineering estimate: 16-28 hours. Dependencies: F16, F17.

R3 requirements: AB-EXE-004, AB-EXE-003.

**Source finding / basis.** The monitor emits a high-pressure violation immediately despite a configured 5-second duration. It tests interlock:device in _active_violations but stores violations by generated violation_id, so the same breach emits repeatedly.

**Production targets.**

- `services/agribrain/irrigation_runtime/safety.py`
- `services/agribrain/irrigation_runtime/actuator.py`

**Implementation steps.**

1. Track first breach, duration, recovery and freshness using monotonic time.
2. Index active violation state by device and interlock while preserving unique event records.
3. Implement the declared manual/automatic reset rules.
4. Make stop actions idempotent and rehydrate active protections after restart.

**Completion criteria.**

- Configured debounce is honored with fake-clock probes.
- A sustained breach emits one active violation until a qualifying reset.
- Missing or nonfinite readings cannot count as normal pressure.

### F20 - Qualify post-irrigation readings before confirming delivery

Priority: P0. Evidence class: Confirmed controlled production probe. Engineering estimate: 32-48 hours. Dependencies: F02, F05, F12, F17.

R3 requirements: AB-EXE-005, AB-DAT-007, AB-DAT-013.

**Source finding / basis.** Foreign stale duplicate readings returned CONFIRMED with confidence 0.95 while the report listed the configured authorized sensor ID. The validator appends readings without enforcing the configured device, time window or uniqueness.

**Production targets.**

- `services/agribrain/irrigation_runtime/validation.py`

**Implementation steps.**

1. Validate reading identity, tenant, plot/zone, depth, calibration and time support.
2. Deduplicate measurement IDs and require post-action measurements inside the window.
3. Base expected response on verified delivered exposure and the same hydrological support, not solely target_volume_mm.
4. Keep moisture response distinct from delivery proof and disallow calibration promotion from unqualified samples.

**Completion criteria.**

- Foreign, stale and duplicate records do not raise confirmation confidence.
- Reports list the sensors that actually contributed.
- Rain, drainage, sensor support and delivery uncertainty are accounted for.

### F21 - Freeze training-window payloads and include partition identity

Priority: P0. Evidence class: Confirmed controlled production probes. Engineering estimate: 24-40 hours. Dependencies: F02, F09.

R3 requirements: AB-DAT-011, AB-DAT-013, AB-ML-001, AB-ML-007.

**Source finding / basis.** The frozen window contains mutable nested dictionaries. Mutating a value leaves its hash unchanged. The hash includes active event IDs but omits payload digests, tenant and namespace; two partitions produced the same hash.

**Production targets.**

- `services/agribrain/world_model/historical_extractor.py`
- `services/agribrain/world_model/canonical_worldline.py`

**Implementation steps.**

1. Use immutable or deeply copied canonical event snapshots.
2. Hash payload content, schema, partition, geometry/cycle and extraction policy.
3. Include supersession/retraction resolution and ordered parent evidence in the manifest.
4. Verify the digest again before dataset loading and model artifact creation.

**Completion criteria.**

- Any included content change alters the manifest identity.
- Caller mutation cannot alter an issued window.
- Tenant/namespace boundaries have distinct manifest identities.

### F22 - Classify timing by event role rather than a universal causality rule

Priority: P0. Evidence class: Confirmed controlled extractor probe. Engineering estimate: 20-32 hours. Dependencies: F02, F21.

R3 requirements: AB-DAT-004, AB-DAT-014, AB-ML-008.

**Source finding / basis.** The extractor quarantines knowledge_time < event_time for all event types. A weather forecast committed Jan 2 and valid Jan 3 was excluded as causality_violation_knowledge_precedes_event even though it was available at issuance.

**Production targets.**

- `services/agribrain/world_model/historical_extractor.py`
- `services/agribrain/world_model/contracts.py`

**Implementation steps.**

1. Define event-specific observation, forecast validity, planned action and availability fields.
2. Apply measurement chronology checks to measurements and issuance eligibility to forecasts/scenarios.
3. Validate each child input and revision against the cutoff.
4. Build separate manifests for inputs, later targets and retrospective reconstructions.

**Completion criteria.**

- An archived earlier-issued future forecast remains an eligible input.
- A future measurement is still excluded.
- A planned action stays a scenario and never becomes historical applied water.

### F23 - Commit forecast archives atomically before publishing cache entries

Priority: P0. Evidence class: Confirmed controlled production probes. Engineering estimate: 24-40 hours. Dependencies: F21, F22.

R3 requirements: AB-DAT-011, AB-ARC-007, AB-ARC-008, AB-ASM-014.

**Source finding / basis.** store_forecast populates cache before checking durable conflict. A rejected mean=99 remained retrievable in the new instance. In the rerun of the existing controlled example, the rejected prediction received RMSE 0.0 while disk retained the original forecast.

**Production targets.**

- `services/agribrain/world_model/forecast_archive.py`

**Implementation steps.**

1. Validate immutable content and resolve the durable record before altering cache.
2. Use an atomic conditional insert or equivalent lock/fence instead of exists-then-replace races.
3. Deep-freeze nested predictions and metadata.
4. Treat corrupt or conflicting records as explicit integrity errors instead of absence.

**Completion criteria.**

- After conflict, warm and cold readers return the committed forecast only.
- Concurrent incompatible writes produce one committed identity.
- Mutation cannot alter archived predictions or subsequent evaluation.

### F24 - Validate forecast distributions and make missing scores unavailable

Priority: P0. Evidence class: Confirmed controlled production probes. Engineering estimate: 20-32 hours. Dependencies: F13, F23.

R3 requirements: AB-ML-005, AB-ML-010, AB-ASM-016.

**Source finding / basis.** ForecastRecord accepts NaN or an inconsistent 100-day horizon for a one-day target, crossed quantiles and negative standard deviation. compute_crps_quantiles({},10) returns 0.0; negative Gaussian sigma also gives a seemingly perfect score at its mean.

**Production targets.**

- `services/agribrain/world_model/forecast_archive.py`
- `services/agribrain/layer6_yield/yield_forecast.py`

**Implementation steps.**

1. Require finite consistent horizon, timezone-aware origin/target and a supported finite distribution.
2. Validate quantile levels and monotonicity, variable units/domain and nonnegative sigma.
3. Return unavailable with reason for missing distributions and reject invalid sigma.
4. Name finite-quantile pinball scoring accurately or implement a documented integration rule rather than silently treating an unweighted sparse average as exact CRPS.

**Completion criteria.**

- Empty or malformed forecasts receive no numeric skill credit.
- Origin-target interval and horizon agree.
- Quantile coverage and scores use explicit levels and independently supported targets.

### F25 - Report the actual EO inference backend and normalize its input contract

Priority: P0. Evidence class: Confirmed controlled backend probe. Engineering estimate: 24-40 hours. Dependencies: F01.

R3 requirements: AB-ML-002, AB-ML-014, AB-DAT-006.

**Source finding / basis.** An ONNX session failure falls back internally to the spectral encoder, but infer still returns model_id=onnx_foundation and mode=onnx. _infer_onnx supplies 48 statistics while its stated adapter describes image tensors for Prithvi or Clay.

**Production targets.**

- `services/agribrain/layer1_fusion/eo_foundation_model.py`

**Implementation steps.**

1. Return backend identity and model artifact digest with every inference result.
2. Create explicit per-model tensor, band order, normalization and mask adapters.
3. On backend failure, publish the fallback role and cause, or make the capability unavailable.
4. Derive confidence from evaluated model/domain evidence rather than file presence.

**Completion criteria.**

- A failed ONNX call cannot label fallback features as learned model output.
- Wrong input shape fails at a clear contract boundary.
- Model identity includes weights, preprocessing and calibration versions.

### F26 - Hash complete EO support and distinguish missing bands from zero

Priority: P1. Evidence class: Confirmed hash probes and static data-contract defect. Engineering estimate: 20-32 hours. Dependencies: F25.

R3 requirements: AB-DAT-002, AB-DAT-008, AB-DAT-011, AB-ML-002.

**Source finding / basis.** EO tile hashes omit band identity, shape, cloud mask and geometry. B2 versus B3 with the same pixels, and 1x2 versus 2x1 arrays, collided. Missing bands are zero-filled without a general missing-modality token.

**Production targets.**

- `services/agribrain/layer1_fusion/eo_foundation_model.py`

**Implementation steps.**

1. Build digests from band identity/order, shape, numeric encoding, CRS/affine and validity/cloud masks.
2. Validate aligned shapes and mask coverage before pooling.
3. Pass missing-band masks into supported models or declare the fallback feature policy.
4. Require finite pixels and model-specific reflectance scale.

**Completion criteria.**

- Different spectral support or masks have distinct identities.
- A missing band is distinguishable from true zero reflectance.
- A model cannot silently consume misaligned channels.

### F27 - Repair MESIA link-time axes and graph topology

Priority: P0. Evidence class: Static tensor defect; PyTorch execution unavailable. Engineering estimate: 24-40 hours. Dependencies: F01, F26.

R3 requirements: AB-MES-009, AB-ML-002.

**Source finding / basis.** Input ordering is B,L,S,C but flattened link embeddings are restored directly as B,S,L,D without a permutation. RadioGraphRepresentation accepts adjacency_mask and passes attn_mask=None; topology is ignored.

**Production targets.**

- `services/agribrain/mesia/learning/neural_receiver.py`

**Implementation steps.**

1. Restore B,L,S,D and explicitly permute to B,S,L,D.
2. Define valid-link padding and graph masks with batch/time semantics.
3. Thread geometry, antenna and instrument epochs through the neural receiver.
4. Compare topology-aware output with an intentionally topology-free baseline.

**Completion criteria.**

- Distinct link/time marker tensors preserve their identities.
- Invalid links do not affect pooling or attention.
- Changing topology affects only permitted message paths.

### F28 - Make MESIA masked pretraining respect complex channel semantics

Priority: P1. Evidence class: Static learning-contract defects. Engineering estimate: 32-48 hours. Dependencies: F27.

R3 requirements: AB-MES-010, AB-MES-011, AB-ML-004.

**Source finding / basis.** The decoder hardcodes latent_dim=128 although the receiver accepts other latent dimensions. Magnitude and phase masks are sampled independently; phase uses ordinary MSE, which makes values near -pi and +pi appear far apart.

**Production targets.**

- `services/agribrain/mesia/learning/masked_link_trainer.py`
- `services/agribrain/mesia/learning/neural_receiver.py`

**Implementation steps.**

1. Derive decoder dimensions from the actual ModelArtifact configuration.
2. Use paired masks for complex channel elements and explicit link/time/frequency mask tokens.
3. Represent phase circularly or complex-valued and apply the corresponding likelihood/loss.
4. Exclude padded, missing and uncalibrated-invalid samples from objectives that require them, while retaining compatible discovery objectives.

**Completion criteria.**

- Non-128 receiver configurations have compatible decoders.
- Equivalent phase angles have small circular error.
- Masked-loss support and normalization are reproducible and finite.

### F29 - Correct MESIA evaluation labels and establish independent biological validation

Priority: P1. Evidence class: Static evaluator defect plus research gap. Engineering estimate: 40-72 plus field work hours. Dependencies: F05, F24, F27, F28.

R3 requirements: AB-MES-014, AB-MES-012, AB-ASM-003.

**Source finding / basis.** Evaluator loops over four hardcoded state names regardless of num_asmae_states and calls residual coefficient-of-determination Pearson R^2. ASMAE agreement alone cannot establish an independent biological reference or causal RF sensitivity.

**Production targets.**

- `services/agribrain/mesia/learning/asmae_evaluator.py`
- `services/agribrain/mesia/behaviour/likelihood_engine.py`
- `services/agribrain/mesia/assimilation/observability_analyzer.py`

**Implementation steps.**

1. Bind evaluation channels to the actual state registry and support contract.
2. Label R-squared, correlation and predictive error as distinct metrics with constant-target handling.
3. Evaluate held-out sites, instruments, seasons and nuisance interventions against independent qualified measurements.
4. Promote only demonstrated per-variable capabilities and keep discovery representations available without biological claims.

**Completion criteria.**

- Changing the configured state count cannot crash or mislabel channels.
- Agreement with an ASMAE teacher is reported as dependent evaluation.
- Biological capability requires independent calibration and nuisance-controlled validation.

### F30 - Scope conversational memory and cache identity

Priority: P1. Evidence class: Static contract defects; cache activation needs runtime tracing. Engineering estimate: 32-48 hours. Dependencies: F02, F09.

R3 requirements: AB-L9-008, AB-L9-009, AB-DAT-013.

**Source finding / basis.** Runner opens conversational sessions by plot rather than user/thread identity. Semantic cache hashes rounded sensor values but omits tenant, plot, crop, language, policy and canonical state; tokenization removes numbers. Hashes for different tenants/crops matched, and apply 10 versus 100 kg tokenized identically. The active cache call path was not established in this pass.

**Production targets.**

- `services/agribrain/layer9_interface/runner.py`
- `services/agribrain/layer9_interface/engines/conversation_memory.py`
- `services/agribrain/layer9_interface/engines/semantic_cache.py`

**Implementation steps.**

1. Define explicit tenant/user/thread/plot/cycle scope for conversational memory.
2. Resolve references only from sources authorized for the active thread.
3. Include state head, policy, model, language, intent and claim artifacts in cache identity.
4. Preserve numeric quantities and negation, and cache canonically generated artifacts rather than free-standing operational advice.

**Completion criteria.**

- No user thread inherits another user narrative without authorized sharing.
- A changed dose, cutoff or policy invalidates the advice cache.
- Runtime tracing proves which cache paths are active before rollout.

### F31 - Close the independent public AI advice path

Priority: P0. Evidence class: Static application integration and authorization defect. Engineering estimate: 24-40 hours. Dependencies: F01, F02, F15, F30.

R3 requirements: AB-ARC-010, AB-L9-001, AB-L9-002, AB-L9-003, AW-PRO-018.

**Source finding / basis.** /api/ai/chat POST calls getAIAdvice/getQuickAdvice on caller-supplied farmContext with no session/plot authorization in the route and no canonical claim artifact. It is a separate advice path from the authorized intent pipeline.

**Production targets.**

- `src/app/api/ai/chat/route.ts`
- `src/lib/agribrain/gemini-advisor.ts`
- `src/app/api/agribrain/intent/route.ts`

**Implementation steps.**

1. Require authentication and authorize any requested plot context.
2. Resolve trusted context server-side rather than treating browser fields as evidence.
3. Route plot-specific advice through canonical intent, claims, constraints and visible response.
4. Keep educational content explicitly educational and apply provider quotas and body limits.

**Completion criteria.**

- Unauthorized context cannot become plot-specific advice.
- Rendered numbers and prohibitions match the canonical artifact.
- Provider failures and missing evidence produce explicit unavailable or educational responses.

### F32 - Replace demo calendar and misleading empty/error application states

Priority: P1. Evidence class: Static production UI and API defects; one partial fix in PR #1. Engineering estimate: 32-56 hours. Dependencies: F09.

R3 requirements: AW-PRO-008, AW-PRO-004, AB-DAT-005, AB-DAT-013.

**Source finding / basis.** Calendar displays five static Jan/Feb 2026 demo tasks with readOnly completion. Farm page returns an empty farm list on database failure and exposes all farms in development fallback. Main dashboard returns successful zero stats after errors; PR #1 corrects that route only.

**Production targets.**

- `src/app/calendar/page.tsx`
- `src/app/api/cycles/[id]/tasks/route.ts`
- `src/app/farm/page.tsx`
- `src/app/api/dashboard/stats/route.ts`

**Implementation steps.**

1. Connect calendar to authorized persisted task/cycle records and scoped date-range queries.
2. Persist completion, deviations, assignees and timezone instead of local demo state.
3. Distinguish loading, empty, unauthorized and unavailable states in farms and dashboards.
4. Put demo records in an explicit isolated demo namespace and remove real-tenant development fallback.

**Completion criteria.**

- A new empty account sees no fabricated tasks.
- Task edits survive reload and appear in the scientific exposure workflow when qualified.
- Database outage shows unavailable instead of a successful empty farm or zero statistics.

### F33 - Validate photo zone ownership and database insert success

Priority: P1. Evidence class: Static application boundary defects. Engineering estimate: 12-24 hours. Dependencies: F01, F02, F09.

R3 requirements: AW-PRO-005, AW-PRO-011, AB-DAT-013, AB-ARC-007.

**Source finding / basis.** The route authorizes plotId but only checks the format of zoneId; it does not verify zone membership. It returns success after raw insert without explicitly checking writeErrors, n or the inserted evidence identity.

**Production targets.**

- `src/app/api/evidence/add/route.ts`
- `prisma/schema.prisma`

**Implementation steps.**

1. Resolve optional zone against the authorized plot and geometry epoch.
2. Validate observation timing and retain the server availability timestamp.
3. Check raw write outcome and return the canonical created evidence ID.
4. Preserve pending processing and use a durable admission/outbox event for retries.

**Completion criteria.**

- A foreign valid-looking zone cannot be attached.
- Failed raw insertion cannot return success.
- Photo availability and processing state are recoverable after retry.

### F34 - Separate input accounting from applied agronomic exposure

Priority: P1. Evidence class: Static unit/lifecycle integration gap. Engineering estimate: 32-56 hours. Dependencies: F09, F11, F20.

R3 requirements: AW-PRO-009, AW-PRO-013, AB-DAT-007, AB-DAT-010, AB-AGR-010.

**Source finding / basis.** InputLog accepts arbitrary nonempty unit and type with an appliedAt default. Quantity/cost logging is not a complete exposure contract for formulation, applied status, spatial support and delivered dose. Future appliedAt is accepted as a date.

**Production targets.**

- `src/app/api/inputs/route.ts`
- `prisma/schema.prisma`
- `services/agribrain/layer3_decision/runner.py`
- `services/agribrain/layer4_nutrients/runner.py`

**Implementation steps.**

1. Validate unit and input category against controlled registries.
2. Store purchased, stocked, planned and applied events separately.
3. Convert product quantity to nutrient mass or delivered water using formulation, area and support references.
4. Publish verified application exposure to Worldline and update financial totals idempotently.

**Completion criteria.**

- A purchase or future plan cannot enter historical water/N balance.
- Product kg and elemental nutrient kg are never interchanged.
- Retry cannot double-count stock, cost or applied mass.

### F35 - Repair drone driver import and complete process cleanup

Priority: P1. Evidence class: Static runtime defects; one earlier failure path is already improved. Engineering estimate: 20-36 hours. Dependencies: F09.

R3 requirements: AW-PRO-011, AB-ARC-006, AB-ARC-008, AB-ARC-012.

**Source finding / basis.** Dispatcher imports drivers.mock_driver, absent from the pinned tree. The current ASMAE supervisor does terminate/wait on metadata-update failure, so the older blanket orphan-child finding must not be repeated. Its forced-kill branch does not wait again before releasing ownership.

**Production targets.**

- `services/agribrain/drone_control/dispatcher.py`
- `services/agribrain/app/drone_routes.py`
- `services/agribrain/layer05_asmae/background_jobs.py`

**Implementation steps.**

1. Lazy-load explicitly configured real drivers and move simulation behind an explicit test/development capability.
2. Return unavailable driver capability without breaking unrelated service import.
3. Complete terminate-kill-wait lifecycle and process-group cleanup under a bounded deadline.
4. Fence all child writes and publish final cleanup/ownership receipts.

**Completion criteria.**

- Missing optional drivers cannot disable service startup.
- Simulation cannot publish observed mission evidence.
- Forced-kill cleanup confirms process exit before resource ownership is released.

### F36 - Require per-variable observability and independent predictive calibration

Priority: P1. Evidence class: Scientific qualification gap supported by exporter structure. Engineering estimate: 48-80 plus reference data hours. Dependencies: F01, F02, F24, F29.

R3 requirements: AB-ASM-003, AB-ASM-011, AB-ASM-013, AB-ASM-014, AB-ASM-015, AB-ASM-016, AB-ASM-001, AB-ASM-002, AB-ASM-004, AB-ASM-005, AB-ASM-009, AB-ASM-010, AB-ASM-012.

**Source finding / basis.** Exporter grants weights per state from shared microzone retro score, sigma, BMA disagreement and blocked states. Those gates are useful, but do not themselves demonstrate independent sensitivity for every exported state. A primary sensor pass and two active experts cannot prove all physiological coordinates or calibrated prediction.

**Production targets.**

- `services/agribrain/layer05_asmae/training/exporter.py`
- `services/agribrain/layer05_asmae/observation/index_state_mapping.py`
- `services/agribrain/layer05_asmae/constraints/radiometric.py`
- `services/agribrain/layer05_asmae/retrovalidation/engine.py`

**Implementation steps.**

1. Build a per-state support ledger connecting actual operator sensitivity and independent references to each label.
2. Carry dependence groups for indices from shared native acquisitions and BMA experts sharing evidence.
3. Use archived prospective issuance cohorts separately from hindcasts and persistence, with per-variable/horizon calibration.
4. Tune process noise and rejection thresholds on frozen independent cohorts instead of selecting values for a passing pipeline flag.

**Completion criteria.**

- An unsupported coordinate has explicit prior/reconstruction role and compatible objective weight.
- Derived indices and shared teachers do not count as independent references.
- Forecast skill, coverage and domain evidence are reported per variable and horizon against stated baselines.

### F37 - Repair optional imports and establish one Python package identity

Priority: P1. Evidence class: Confirmed cold-import failure and class-identity probe. Engineering estimate: 24-48 hours. Dependencies: none.

R3 requirements: AB-ARC-004, AB-ARC-008, AB-DAT-002.

**Source finding / basis.** GaussianMixture is imported from sklearn.cluster and the module fails to load. The missing drone mock driver is confirmed, but adding a production mock is not the only remedy. Both alleged package cycles cold-import successfully under the configured path. Mixing qualified and bare drone_mission imports creates different MissionType class objects. The active L1 engine uses zone_engine, so the broken segmentation import is not proof that all L1 fails.

**Production targets.**

- `services/agribrain/layer1_fusion/segmentation.py`
- `services/agribrain/layer1_fusion/engine.py`
- `services/agribrain/drone_control/dispatcher.py`
- `services/agribrain/drone_mission/__init__.py`
- `services/agribrain/layer0/perception/drone_rgb/structural.py`
- `services/agribrain/app/main.py`

**Implementation steps.**

1. Import GaussianMixture from sklearn.mixture and identify actual consumers of the legacy segmentation module.
2. Isolate optional drivers and model backends behind explicit capability loading, retaining simulation as a qualified mode.
3. Select one installed package namespace and migrate entrypoints/imports coherently instead of mechanically prefixing every import.
4. Verify service, worker, CLI and public module startup in fresh processes with declared dependency extras.

**Completion criteria.**

- Cold imports work for each supported entrypoint without incidental prior imports.
- Qualified and internal callers share enum/dataclass identities.
- An unavailable optional backend disables its capability without breaking unrelated science.
- The two successfully loaded cycles are not treated as demonstrated circular-import failures.

### F38 - Restore failure ledgers, scoped loading and degraded publication

Priority: P0. Evidence class: Nine genuine undefined-name cases; three controlled failures and six scoped source findings. Engineering estimate: 48-80 hours. Dependencies: F01, F02, F09, F31, F37.

R3 requirements: AB-DAT-005, AB-DAT-013, AB-ARC-005, AB-ARC-007, AB-ARC-008, AB-L9-002, AB-L10-001.

**Source finding / basis.** The attached audit identifies nine real undefined-name sites, but several are caught and lose ledgers, scenes, scope or metadata instead of crashing the whole process. np annotation and guarded args are not the alleged immediate NameErrors. Progress can mark a mismatched completed job published merely because any canonical head exists. String MESIA plot references fabricate default tenant/farm after the missing coercer fails.

**Production targets.**

- `services/agribrain/orchestrator_v2/runner.py`
- `services/agribrain/orchestrator_v2/chat_adapter.py`
- `services/agribrain/layer10_sire/l10_frontend_bridge.py`
- `services/agribrain/layer05_asmae/runner.py`
- `services/agribrain/layer05_asmae/geometry/external_scene_loader.py`
- `services/agribrain/mesia/service.py`
- `services/agribrain/layer2_veg_int/growth_engine.py`
- `services/agribrain/app/main.py`
- `services/agribrain/irrigation_runtime/dispatcher.py`
- `services/agribrain/orchestrator_v2/run_entrypoint.py`

**Implementation steps.**

1. Use the function-local decision timestamp in terminal no-data output and verify degraded output commits through the canonical publication contract.
2. Thread actual intent and userMode from typed context into local compression, routing and response policy.
3. Build geometry explicitly in the synthetic bridge helper and isolate that helper from normal product inputs.
4. Build failed ASMAE validation receipts from inp and its qualified geometry, removing arbitrary geometry-hash fallback.
5. Resolve external-scene resolution from validated grid metadata and preserve each rejected-scene reason.
6. Require qualified MESIA namespace rather than fabricated default scope.
7. Import statistics and IrrigationSystemType at their actual runtime definitions and verify relevant branches.
8. Parse completed timestamps robustly but derive published only from the exact committed output relation, including superseded heads.
9. Classify each caught failure as unavailable capability or partial result with observable diagnostic instead of silently manufacturing success.

**Completion criteria.**

- The three reproduced external-scene, growth-spacing and missing-event cases no longer fail.
- Degraded L1 emits a committed no-data response using ts_now.
- ASMAE failure still returns its original error and also persists its failure receipt.
- A foreign or mismatched head cannot prove the completed job was published.
- Missing scope never becomes default_tenant/default_farm.
- Local response compression/routing use the real intent and mode.

### F39 - Make telemetry persistence and replay protection concurrency safe

Priority: P0. Evidence class: Confirmed lost-update probe plus five static unbounded collection findings. Engineering estimate: 40-72 hours. Dependencies: F01, F09.

R3 requirements: AB-DAT-001, AB-DAT-003, AB-DAT-011, AB-DAT-013, AB-ARC-008, AB-ARC-009.

**Source finding / basis.** Two concurrent nonce writers both report success but the production file retains one nonce. Atomic rename protects file replacement, not the preceding read-modify-write. Five growing collections have no cardinality limits; their presence proves retention risk, not an observed OOM. Blind ring-buffer replacement could destroy raw scientific evidence.

**Production targets.**

- `services/agribrain/sensor_runtime/security.py`
- `services/agribrain/sensor_runtime/storage.py`
- `services/agribrain/app/main.py`
- `services/agribrain/visual_sources/tile_proxy.py`

**Implementation steps.**

1. Combine nonce eligibility and registration in a shared atomic conditional insert with scoped unique keys and retention derived from the accepted replay window.
2. Persist immutable raw/normalized telemetry durably with message idempotency before making it visible.
3. Keep memory caches bounded by byte/cardinality budgets and expose retention/eviction metrics.
4. Use safe lock striping or lifecycle-managed keyed locks that cannot be evicted while held or awaited.
5. Bound rate-limiter identity retention without permitting an eviction/reset bypass across replicas.
6. Key bounding-box caches by tenant and geometry epoch with explicit invalidation.

**Completion criteria.**

- Two simultaneous unique nonces remain registered and the same nonce is accepted at most once.
- Replay rejection survives restart and concurrent replicas.
- Cache pressure does not erase the durable evidence corpus.
- High-cardinality keys stay within declared budgets without duplicating locks for one active key.
- Geometry corrections cannot reuse an old plot bounding box.

### F40 - Resolve annotation consumers and close verification evidence gaps

Priority: P1. Evidence class: Deferred-annotation definition and introspection probes; incomplete aggregate audit counts. Engineering estimate: 24-48 hours. Dependencies: F37, F38.

R3 requirements: AB-ARC-004, AB-ARC-006, AB-ARC-012, AB-ML-014.

**Source finding / basis.** The attachment lists 18 unique typing files rather than 19. Future annotations defer name evaluation: Kalman np and correlator Tuple definitions work, while get_type_hints fails. The fresh selected 410-file syntax check used Python 3.12.14, not the claimed full 1,310-file Python 3.13 environment. Zero syntax failures does not establish dataclass, Pydantic or runtime compatibility.

**Production targets.**

- `services/agribrain/layer0/kalman_engine.py`
- `services/agribrain/mesia/identity/correlators.py`
- `services/agribrain/world_model/belief_snapshot.py`
- `services/agribrain/layer4_nutrients/schema.py`
- `services/agribrain/sensor_runtime/registry.py`
- `services/agribrain/layer05_asmae/background_jobs.py`

**Implementation steps.**

1. Import or explicitly resolve annotation names where runtime consumers need them.
2. Use postponed type-only imports only when schema/introspection frameworks do not require resolution.
3. Audit the 18 cited files and every public dataclass/Pydantic/tool-schema consumer with the installed declared runtime.
4. Create a pinned full production manifest with exact exclusion rules and supported Python/dependency versions.
5. Compile the manifest and cold-load decorated schemas separately.
6. Classify exception handlers by recovery and published scientific effect, and run a history-aware secrets check without exposing values.
7. Publish scope and reproducible receipts rather than extending subset zero counts to the whole tree.

**Completion criteria.**

- get_type_hints and production schema generation succeed for supported public contracts.
- The runtime and file manifest accompany every verification count.
- An unresolved annotation cannot silently invalidate a tool/schema registration.
- Secret, portability, dataclass and full-repository claims remain unqualified until their own checks complete.

## 10. Target-capability implementation packages

### T01 - One canonical coupled agricultural trajectory

Priority: Target. Evidence class: Capability extension. Engineering estimate: 80-140 hours. Dependencies: F03, F09, F10, F11.

R3 requirements: AB-WM-001, AB-AGR-002, AB-AGR-008, AB-ARC-001, AB-ARC-002, AB-ARC-003, AB-AGR-001.

**Source finding / basis.** Existing specialist states and Worldline contracts are a basis, but a shared sequential water/nutrient/vegetation transition must be established before learned rollout targets are trusted.

**Production targets.**

- `services/agribrain/world_model/canonical_worldline.py`
- `services/agribrain/world_model/belief_snapshot.py`
- `services/agribrain/layer2_contracts/state_transition.py`
- `services/agribrain/orchestrator_v2/runner.py`

**Implementation steps.**

1. Define a versioned X/Z/H/M/U snapshot with availability and support per coordinate.
2. Specify operator-splitting order and feed L3/L4 constraints back into the next vegetation growth transition.
3. Link transition, analysis, management and diagnostic receipts to one predecessor.
4. Publish read-only projections for L7-L10 rather than independent local physical reconstructions.

**Completion criteria.**

- A consumed-feedback receipt proves water/N limitations affected subsequent growth.
- Daily, sparse, cold and corrected replay agree on the same interval semantics.
- Every output resolves to the same authorized state head.

### T02 - Objective-specific longitudinal learning corpus

Priority: Target. Evidence class: Capability extension. Engineering estimate: 80-140 hours. Dependencies: F21, F22, F25, F26, F36, T01.

R3 requirements: AB-ML-001, AB-ML-006, AB-ML-007, AB-ML-008, AB-ML-014, AB-ML-015.

**Source finding / basis.** ASMAE candidate builders and bitemporal extraction provide useful scaffolding; they do not replace a complete objective-specific multimodal corpus with frozen independent splits.

**Production targets.**

- `services/agribrain/world_model/historical_extractor.py`
- `services/agribrain/asmae_learn/dataset_builder.py`
- `services/agribrain/asmae_learn/model_registry.py`

**Implementation steps.**

1. Define input tokens, masks, observation policy, labels and target-support eligibility per objective.
2. Build immutable manifests and partition plots/sites/seasons/instruments before fitting preprocessing.
3. Permit partial and synthetic data for compatible objectives and prohibit promotion to independent biological truth.
4. Produce reproducible dataset/model artifacts with lineage, consent, licensing and calibration metadata.

**Completion criteria.**

- No target parent or post-cutoff input leaks into a predictive window.
- Holdout partitions remain isolated across derived products.
- A dataset snapshot can be regenerated byte-for-byte.

### T03 - Multimodal foundation representation and local adaptation

Priority: Target. Evidence class: Capability extension. Engineering estimate: 160-300 plus compute hours. Dependencies: T02, F27, F28.

R3 requirements: AB-ML-002, AB-ML-003, AB-ML-004, AB-ML-009, AB-ML-010, AB-ML-011, AB-ML-012, AB-ML-013.

**Source finding / basis.** An EO inference wrapper and an RF encoder are not yet a demonstrated shared longitudinal foundation model. The existing specialist encoders should be retained and corrected.

**Production targets.**

- `services/agribrain/layer1_fusion/eo_foundation_model.py`
- `services/agribrain/mesia/learning/neural_receiver.py`
- `services/agribrain/asmae_learn/model_registry.py`

**Implementation steps.**

1. Start with small time-series and single-modality baselines on the frozen corpus.
2. Train masked temporal/multimodal encoders with support and modality dropout.
3. Add shared X/Z alignment, calibrated heads, OOD detection and local adapters.
4. Evaluate transfer and rich-to-sparse distillation before federated deployment with secure aggregation and privacy accounting.

**Completion criteria.**

- Representation improves at least one predeclared held-out task beyond smaller baselines.
- Missing modalities have defined behavior and measured degradation.
- Artifact, preprocessing, split and calibration versions reproduce the result.

### T04 - Hybrid world model with conservative multi-horizon rollout

Priority: Target. Evidence class: Capability extension. Engineering estimate: 160-300 plus prospective data hours. Dependencies: T01, T02, T03, F23, F24, F12.

R3 requirements: AB-WM-002, AB-WM-003, AB-WM-004, AB-WM-005, AB-WM-006.

**Source finding / basis.** Forecast/archive and state contracts are scaffolding. They should be the basis of a learned hybrid transition, rather than being counted as the learned world model itself.

**Production targets.**

- `services/agribrain/world_model/contracts.py`
- `services/agribrain/world_model/forecast_archive.py`
- `services/agribrain/layer05_asmae/retrovalidation/future_projection.py`

**Implementation steps.**

1. Retain mechanistic conserved transitions and fit bounded residual dynamics conditioned on actual/scenario action.
2. Forecast explicit states, latent representation and future observation distributions jointly.
3. Test memory sufficiency against simpler Markov and history baselines.
4. Evaluate paired intervention rollouts only where exposure, support and identification assumptions are valid.

**Completion criteria.**

- Rollouts remain physically admissible with explicit residual ledgers.
- Prospective multi-horizon skill exceeds stated persistence/mechanistic baselines on held-out domains.
- Counterfactual output states its identifying assumptions and uncertainty.

### T05 - Decision economics from shared outcome distributions

Priority: Target. Evidence class: Capability extension. Engineering estimate: 80-140 plus outcomes hours. Dependencies: F12, F13, F14, F15, T04.

R3 requirements: AB-DEC-001, AB-DEC-002, AB-DEC-003, AB-ECO-001, AB-ECO-002, AB-ECO-003, AB-ECO-004.

**Source finding / basis.** Current heuristics can be useful baselines but fixed yield/impact ratios are not measured marginal economic value. Decisions must share distributions and actual constraints.

**Production targets.**

- `services/agribrain/layer7_planning/runner.py`
- `services/agribrain/layer8_prescriptive/runner.py`
- `services/agribrain/layer6_exec/outcomes/metrics.py`

**Implementation steps.**

1. Add versioned price, labor, energy, water, input, quality and transport assumptions.
2. Derive margins and downside risk from joint outcome samples.
3. Compare no-action, measurement and intervention policies with immutable hard feasibility constraints.
4. Evaluate value of information against transparent measurement baselines and actual realized costs.

**Completion criteria.**

- Currency, date, area and quantity units are explicit.
- Missing price becomes an assumption with sensitivity rather than observed value.
- Policy value uses independently observed outcomes and qualified causal assumptions.

### T06 - MESIA native acquisition, metrology and capability commissioning

Priority: Target. Evidence class: Capability extension. Engineering estimate: 120-220 plus hardware/field work hours. Dependencies: F01, F05, F27, F28, F29, T02.

R3 requirements: AB-MES-001, AB-MES-002, AB-MES-003, AB-MES-004, AB-MES-005, AB-MES-006, AB-MES-007, AB-MES-008, AB-MES-012, AB-MES-013, AB-MES-015.

**Source finding / basis.** Recent missing-SNR, calibration uncertainty and north-up corrections are retained. Native instrument commissioning and independent biological capability remain distinct from a passing software suite.

**Production targets.**

- `services/agribrain/mesia/service.py`
- `services/agribrain/mesia/lanes/wifi/csi_extractor.py`
- `services/agribrain/mesia/behaviour/likelihood_engine.py`
- `services/agribrain/mesia/assimilation/spatial_lattice.py`

**Implementation steps.**

1. Archive native complex CSI and available GNSS/RF observations with instrument and two-clock timing.
2. Version topology, actual poses, antenna, firmware, channel/band and calibration epochs.
3. Qualify missingness, nuisance covariance and geometric kernels against the canonical lattice.
4. Progress discovery/configuration/commissioning/calibration states and promote only validated individual capabilities.

**Completion criteria.**

- Commodity hardware modalities remain optional and explicitly characterized.
- Calibration drift does not become biology.
- Native records and instrument state reproduce the same qualified likelihood.

### T07 - Omega scientific investigation loop

Priority: Target. Evidence class: Capability extension. Engineering estimate: 240-440 plus experiments hours. Dependencies: F12, F21, F36, T01, T02, T04.

R3 requirements: AB-OMG-001, AB-OMG-002, AB-OMG-003, AB-OMG-004, AB-OMG-005, AB-OMG-006, AB-OMG-007, AB-OMG-008, AB-OMG-009, AB-OMG-010, AB-OMG-011, AB-OMG-012, AB-OMG-013, AB-OMG-014, AB-OMG-015, AB-OMG-016, AB-OMG-017, AB-OMG-018.

**Source finding / basis.** Diagnostic hypotheses and promotion services are reusable foundations. Omega as specified in R3 is a scientific discovery loop, not a confidence label or a renamed diagnostic tribunal.

**Production targets.**

- `services/agribrain/diagnostic_integration/contracts.py`
- `services/agribrain/world_model/canonical_worldline.py`
- `services/agribrain/diagnostic_integration/promotion_service.py`

**Implementation steps.**

1. Create ScientificCase and a sealed epistemic Worldline for surprises, alternatives and model inadequacy.
2. Implement Bayesian/mechanistic comparison, simulation/BEL and causal identification with explicit assumptions.
3. Propose discriminating measurements/experiments with measurement-selection analysis, power, interference, stopping and consent.
4. Record falsification, negative results, independent replication and domain-bound knowledge artifacts before per-capability promotion.

**Completion criteria.**

- A case follows surprise to competing explanations, discriminating prediction, experiment and replication.
- A latent or symbolic equation remains a candidate until appropriate evidence separates alternatives.
- Scientific success includes reduced ambiguity and negative findings, not only promoted claims.

### T08 - Finish AgriWise operational records and financial workflows

Priority: Target. Evidence class: Capability extension. Engineering estimate: 180-320 hours. Dependencies: F32, F33, F34, F09.

R3 requirements: AW-PRO-001, AW-PRO-002, AW-PRO-005, AW-PRO-008, AW-PRO-009, AW-PRO-010, AW-PRO-012, AW-PRO-013, AW-PRO-014.

**Source finding / basis.** Existing farm, crop-cycle, task, equipment, input, market-price and cooperative models are a basis. The schema has no livestock model and price/trend records do not provide complete offer/order/logistics execution.

**Production targets.**

- `prisma/schema.prisma`
- `src/app/api/inputs/route.ts`
- `src/app/api/cycles/[id]/tasks/route.ts`

**Implementation steps.**

1. Complete farm/cycle/rotation history with delegated ownership and scoped task resources.
2. Add stock ledger, equipment use/maintenance and linked actual exposures.
3. Add typed livestock, market offers/orders/quality/storage/transport workflows as proposed new modules.
4. Implement budget, costs and realized versus scenario economics without double counting.

**Completion criteria.**

- Each workflow has persisted authorized records and error recovery.
- Livestock events and costs use their own domain schema.
- Stock/order/financial totals reconcile across cancellation, retry and correction.

### T09 - Unify language, voice, map and offline product projections

Priority: Target. Evidence class: Capability extension. Engineering estimate: 120-220 hours. Dependencies: F30, F31, F32, T01.

R3 requirements: AW-PRO-003, AW-PRO-004, AW-PRO-006, AW-PRO-007, AW-PRO-015, AW-PRO-016, AW-PRO-017, AW-PRO-018, AB-L9-001, AB-L9-002, AB-L9-003, AB-L9-004, AB-L9-005, AB-L9-006, AB-L9-007, AB-L9-008, AB-L9-009, AB-L9-010, AB-L10-001.

**Source finding / basis.** Authorized routes and surface contracts should become one consistent product projection. Multiple local advice and demo paths still need convergence; offline conflict and voice fidelity require explicit acceptance.

**Production targets.**

- `src/app/api/agribrain/intent/route.ts`
- `src/lib/agribrain/surface-contract.ts`
- `services/agribrain/layer9_interface/runner.py`
- `services/agribrain/layer10_sire/runner.py`

**Implementation steps.**

1. Resolve one intent to one canonical visible response and typed claims.
2. Keep maps, numbers and explanations linked to the same state/support, including effective resolution.
3. Preserve values, negation and prohibitions across Arabic/French/voice and accessibility rendering.
4. Implement offline pending events with conflict resolution and visibly stale decision cutoffs.

**Completion criteria.**

- Every visible response resolves to one canonical artifact.
- UI and translation do not manufacture numerical science.
- Offline actions reconcile without retroactively changing what a user knew.

### T10 - Institutional aggregation and territorial world-model extension

Priority: Target. Evidence class: Capability extension. Engineering estimate: 120-220 plus regional data hours. Dependencies: T04, T05, T08, T09.

R3 requirements: AB-WM-007, AB-ECO-005, AW-PRO-014, AB-ARC-010, AB-ARC-011.

**Source finding / basis.** Cooperatives and RegionalStats support product records but do not establish independently evaluated territorial policy effects, privacy-preserving aggregation or sovereign operation.

**Production targets.**

- `prisma/schema.prisma`
- `services/agribrain/world_model/contracts.py`

**Implementation steps.**

1. Authorize aggregation cohorts and suppress potentially identifying small groups.
2. Model supply, water, market and environmental interactions hierarchically with uncertainty.
3. Evaluate policy and resource scenarios against independent regional outcomes.
4. Version sovereign deployment, licensing, egress and review/appeal pathways for high-impact use.

**Completion criteria.**

- Regional summaries preserve uncertainty and authorized cohort scope.
- Policy scenarios are separated from observed effects.
- Territorial capability is evaluated independently rather than inherited from a plot metric.

### T11 - Operational reproducibility, provider resilience and publication integrity

Priority: Target. Evidence class: Capability extension. Engineering estimate: 100-180 hours. Dependencies: F09, F23, F25, F31, F35.

R3 requirements: AB-ARC-004, AB-ARC-005, AB-ARC-006, AB-ARC-007, AB-ARC-008, AB-ARC-009, AB-ARC-010, AB-ARC-011, AB-ARC-012, AB-DAT-001, AB-DAT-002, AB-DAT-009, AB-ASM-006, AB-ASM-007, AB-ASM-008.

**Source finding / basis.** The selected corpus contains substantial gateway, lease and publication foundations. Complete failure behavior must be demonstrated across live service boundaries, rather than inferred from module presence.

**Production targets.**

- `services/agribrain/layer0/data_gateway/request_broker.py`
- `services/agribrain/layer05_asmae/background_jobs.py`
- `services/agribrain/orchestrator_v2/storage.py`
- `services/agribrain/app/main.py`

**Implementation steps.**

1. Lock dependencies and produce code/image/model/config identities for each run.
2. Trace all production entrypoints to one source admission and scoped publication policy.
3. Run bounded provider outage, corruption, timeout, restart, duplicate and concurrent-writer drills.
4. Add operational telemetry for rejected evidence, stale state, scope, compute resources and committed publication heads.

**Completion criteria.**

- A response never points to an uncommitted or foreign result.
- Provider outage degrades only dependent capabilities.
- Recovery reproduces the same canonical artifacts without duplicate execution.

### T12 - Independent agronomic validation and reference field program

Priority: Target. Evidence class: Capability extension. Engineering estimate: 80-140 engineering plus seasonal research hours. Dependencies: F12, F20, F24, F29, F36, T01.

R3 requirements: AB-ASM-016, AB-AGR-011, AB-AGR-012, AB-MES-014, AB-ML-009, AB-ML-010, AB-OMG-013, AB-OMG-015.

**Source finding / basis.** Passing suites and software probes verify behaviors, not empirical biological sensitivity, calibrated yield, intervention value or mechanisms. R3 requires independent observations and discriminating experiments.

**Production targets.**

- `services/agribrain/ground_truth/registry.py`
- `services/agribrain/layer05_asmae/retrovalidation/engine.py`
- `services/agribrain/mesia/learning/asmae_evaluator.py`

**Implementation steps.**

1. Predeclare targets, horizons, cohorts, metrics and applicability domains before tuning.
2. Recruit independent reference plots with depth water, EC, delivery, canopy and qualified crop/outcome observations.
3. Compare simpler mechanistic/statistical baselines and inspect calibration, missingness and measurement selection.
4. Run safe discriminating studies separating water shortage, salinity, hypoxia, hydraulic memory, delivery heterogeneity and biological alternatives.

**Completion criteria.**

- Reference labels are independent of the model under evaluation.
- Prospective results include uncertainty, sample size and negative outcomes.
- Field evidence is reviewed against the declared target before any new capability is promoted.

## 11. Coverage closure and remaining uncertainty

The 153-requirement companion register maps target criteria to the earlier primary package and the relevant correction/extension packages here. Mapping does not imply that a requirement is absent, implemented or empirically validated. Already improved ASMAE requirements are retained as regression targets: identical localized observation support, acquisition-time state projection, positive primary-channel certification, auxiliary state export blocking, modality-aware folds, forecast/hindcast distinction, neutral evidence-free zoning and geometry fail-closed behavior. MESIA missing SNR, calibration uncertainty and north-up coordinates are also retained.

Before declaring the foundation ready, inventory all production entrypoints and each adapter/provider/consumer. For the production candidates outside the selected corpus, record exact blob identity, runtime role, source review status, failure contracts and appropriate probe. Trace the active L9 cache invocation, dependent-input chains and external service fallbacks. Review routes/controllers, persistence schemas and frontend consumers together. The omission of a defect from this register is not a correctness certificate for an unreviewed module.

The remaining highest uncertainty is empirical: which latent states are observable under which crop, stage, soil, instrument and weather domain; whether uncertainty intervals are calibrated; and which intervention effects are identifiable. Resolve it with T12 and the per-variable qualification work, not by weakening thresholds until a pipeline reports success.

## 12. Selected fresh probe receipts

The following are compact local reproduction outputs. They support the associated production-source findings; they are not field observations, external reference data or stored suite claims.

### Probe: forecast nan horizon

```json
NaN
```

### Probe: forecast wrong horizon

```json
100
```

### Probe: forecast crossed negative distribution

```json
{
  "forecast_id": "F",
  "plot_id": "P",
  "target_variable": "vigor",
  "issued_at_knowledge_time": "2026-01-02T12:00:00+00:00",
  "target_epoch": "2026-01-03T12:00:00+00:00",
  "horizon_days": 1,
  "predicted_quantiles": {
    "p10": 10,
    "p50": 5,
    "p90": 1
  },
  "predicted_mean": null,
  "predicted_std": -1,
  "model_id": "",
  "model_version": "",
  "calibration_version": "",
  "authority_scope": "OPERATIONAL_SHADOW",
  "is_shadow": true,
  "metadata": {},
  "schema_version": "forecast_record_v1"
}
```

### Probe: empty forecast perfect score

```json
0.0
```

### Probe: negative gaussian sigma score

```json
0
```

### Probe: frozen forecast mutation

```json
{
  "p10": 0.1,
  "p50": 99,
  "p90": 0.3
}
```

### Probe: archive rejected record in cache

```json
{
  "rejected": "ContractViolation",
  "subsequent_cache_mean": 99,
  "disk_mean": null
}
```

### Probe: training window content and partition

```json
{
  "different_tenants_same_hash": true,
  "nested_value_mutable": 99,
  "hash_unchanged_after_mutation": true
}
```

### Probe: issuance forecast wrongly quarantined

```json
{
  "active": 0,
  "quarantine": "causality_violation_knowledge_precedes_event"
}
```

### Probe: onnx failure mislabelled

```json
{
  "model_id": "onnx_foundation",
  "mode": "onnx",
  "dimension": 128
}
```

### Probe: eo hash omits band shape

```json
{
  "different_band_identity_same_hash": true,
  "different_shapes_same_hash": true
}
```

### Probe: missing spray weather

```json
{
  "allowed_without_wind": true
}
```

### Probe: scheduler empty record confirmed

```json
{
  "empty_weather_status": "CONFIRMED",
  "scheduled_date": "2026-01-02"
}
```

### Probe: leaching raises hard ceiling

```json
{
  "old_max": 21,
  "new_max": 27.7,
  "recommended": 23.1
}
```

### Probe: L7 L8 actual field names

```json
{
  "scenario_id": "SCN-CROP-crop_opt_0",
  "scenario_type": "CROP_SELECTION",
  "action_type": "SELECT_CROP_ROTATION",
  "assumed_state": {
    "target_crop": "unknown"
  },
  "weather_scenario": {
    "scenario_source": "seasonal_normal"
  },
  "management_params": {
    "crop_choice": "unknown"
  },
  "expected_outcomes": {
    "expected_yield_relative": 1.0
  },
  "constraints": {
    "seasonal_window": true
  },
  "uncertainty": {
    "outcome_sigma": 0.2
  },
  "is_reversible": false,
  "required_evidence": [
    "crop_history",
    "soil_type"
  ],
  "validity_domain": {
    "crop_suitability": true
  }
}
```

### Probe: soil nonmonotonic depths accepted

```json
20.0
```

### Probe: soil negative conductivity accepted

```json
[
  -1,
  -1
]
```

### Probe: water analysis and flux receipt

```json
{
  "published_transpiration": 8.52,
  "requested_transpiration": 1.32,
  "prognostic_storage": 297.15,
  "prior_vs_posterior_storage_change": 274.04999999999995,
  "mass_error": 0.0,
  "assimilation_count": 5
}
```

### Probe: interlock debounce and duplicate

```json
{
  "first_violation_count": 1,
  "repeated_same_breach_count": 1,
  "configured_debounce_seconds": 5
}
```

### Probe: semantic cache tenant crop collision

```json
true
```

### Probe: semantic cache numeric query collision

```json
true
```

### Probe: verified exposure not causal identification

```json
{
  "classification": "CAUSAL_ATTRIBUTED",
  "method": "pre_post",
  "delta": 0.1
}
```

### Probe: date

```json
{"request_date": "2026-01-02T12:00:00+00:00", "only_weather_date": "2026-01-03", "returned_water_date": "2026-01-02T12:00:00+00:00", "used_precip_mm": 12.0}
```

### Probe: nitrogen

```json
{"critical_n_pct": 2, "actual_n_pct": 0.96, "returned_additional_N": 36.67, "residual_additional_N_same_efficiency": 86.66666666666667}
```

### Probe: attachment claim probe results.json

```json
{
  "external_scene_valid_grid_discarded": {
    "accepted_scene_count": 0
  },
  "growth_method": "_savgol_derivatives",
  "growth_derivative_spacing": {
    "exception": "NameError",
    "message": "name 'statistics' is not defined"
  },
  "unknown_irrigation_event": {
    "exception": "NameError",
    "message": "name 'IrrigationSystemType' is not defined"
  },
  "deferred_np_annotation_definition": {
    "definition_succeeded": true,
    "return_annotation": "Tuple[np.ndarray, np.ndarray]"
  },
  "np_annotation_introspection": {
    "exception": "NameError",
    "message": "name 'np' is not defined"
  },
  "deferred_Tuple_definition": {
    "definition_succeeded": true,
    "runtime_function_result": [
      true,
      1.0
    ]
  },
  "Tuple_annotation_introspection": {
    "exception": "NameError",
    "message": "name 'Tuple' is not defined"
  },
  "nonce_concurrent_lost_update": {
    "successful_writers": 2,
    "persisted_nonce_count": 1,
    "errors": []
  }
}
```

## 13. Pinned production source references

All links below resolve to the reviewed baseline rather than floating main. Implementation targets include existing scaffolding used for extensions; listing a source does not assert that its complete body was manually audited or that the corresponding target capability is implemented.

- [prisma/schema.prisma](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/prisma/schema.prisma) - blob `6aaee7b4292a3c1a9ee14eb427bd67437353c587`.

- [services/agribrain/app/drone_routes.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/app/drone_routes.py) - blob `a0adcde3bf06c70a7a842f62511f9e8f8be9719d`.

- [services/agribrain/app/main.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/app/main.py) - blob `9ea06f5f706e767491bd28653cc817823d300a6f`.

- [services/agribrain/asmae_learn/dataset_builder.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/asmae_learn/dataset_builder.py) - blob `ddc08a80a47b4bdeb56206ea4d1976acd06dcbf8`.

- [services/agribrain/asmae_learn/model_registry.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/asmae_learn/model_registry.py) - blob `2af5ea677200074cdc5c7136cdb5c0de0ea3f7d2`.

- [services/agribrain/diagnostic_integration/contracts.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/diagnostic_integration/contracts.py) - blob `007a04f8c50312b9cf66e428dc80f8a2475bee85`.

- [services/agribrain/diagnostic_integration/promotion_service.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/diagnostic_integration/promotion_service.py) - blob `3b8227b4d9ffda9c2ba38e1bad7c3b485da9dc3a`.

- [services/agribrain/drone_control/dispatcher.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/drone_control/dispatcher.py) - blob `1974173b837846528a04e36886ad9f447d5d6c0f`.

- [services/agribrain/drone_mission/__init__.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/drone_mission/__init__.py) - blob `7de41336d2734bd30a72c4b0c20fe57f46f30401`.

- [services/agribrain/ground_truth/registry.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/ground_truth/registry.py) - blob `2486e1524d0a066df92ef6a17cd3018e05313093`.

- [services/agribrain/irrigation_runtime/actuator.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/irrigation_runtime/actuator.py) - blob `97665b052fd083707589eb393926cbef9e50707f`.

- [services/agribrain/irrigation_runtime/dispatcher.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/irrigation_runtime/dispatcher.py) - blob `e3233e45775992b5ca1e605ce7be91866a46c1ac`.

- [services/agribrain/irrigation_runtime/safety.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/irrigation_runtime/safety.py) - blob `609095d7e46db1bd9abb197fb98537292a706d95`.

- [services/agribrain/irrigation_runtime/validation.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/irrigation_runtime/validation.py) - blob `d2f8c0aad82ad3da45051be9541943a733a93383`.

- [services/agribrain/layer0/data_gateway/request_broker.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/data_gateway/request_broker.py) - blob `e44494d091fcbb88230b7dff473cc3f9ed8d874b`.

- [services/agribrain/layer0/kalman_engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/kalman_engine.py) - blob `31ed7e640e6133f7daa308221a3830576de4b4bd`.

- [services/agribrain/layer0/observation_packet.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/observation_packet.py) - blob `860e617acae4c18458e99c8387efd4793f4cb91c`.

- [services/agribrain/layer0/perception/drone_rgb/structural.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/perception/drone_rgb/structural.py) - blob `78bfdb0d30dc1b81371743eda642f7ae63161931`.

- [services/agribrain/layer0/temporal_evidence.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/temporal_evidence.py) - blob `855a80727b2c7b70264b2190bcc63ceebe9529ab`.

- [services/agribrain/layer0/wrappers.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer0/wrappers.py) - blob `2f500e08d0144395f0ede6d48598355b21f591c2`.

- [services/agribrain/layer05_asmae/background_jobs.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/background_jobs.py) - blob `bb13b1a27b5996dbbe78747c327b08a4723ed7b9`.

- [services/agribrain/layer05_asmae/constraints/radiometric.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/constraints/radiometric.py) - blob `12d21b471014147e45927d9114611351c87fb871`.

- [services/agribrain/layer05_asmae/geometry/external_scene_loader.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/geometry/external_scene_loader.py) - blob `823bb1d2919756e58c4ca0536868db0e0d2d5a0f`.

- [services/agribrain/layer05_asmae/history/worldline_service.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/history/worldline_service.py) - blob `0d30032eee9c939512cabf2453f6e4c7f88c8897`.

- [services/agribrain/layer05_asmae/observation/index_state_mapping.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/observation/index_state_mapping.py) - blob `6854252e94740523f690c4e790733a64db8a75b8`.

- [services/agribrain/layer05_asmae/resilient_posterior.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/resilient_posterior.py) - blob `452897042f01dd02c1be8fc1bef2395251fcd01a`.

- [services/agribrain/layer05_asmae/retrovalidation/engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/retrovalidation/engine.py) - blob `4acfe79f40989e0076902e8be2b10023a5083d90`.

- [services/agribrain/layer05_asmae/retrovalidation/future_projection.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/retrovalidation/future_projection.py) - blob `c82c4e4d7c299addde27235d16d34a264ab19937`.

- [services/agribrain/layer05_asmae/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/runner.py) - blob `cb182ac4791510a78e2be8be6f77e5c4fbd4d503`.

- [services/agribrain/layer05_asmae/training/exporter.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer05_asmae/training/exporter.py) - blob `61305e2180e15a8eac3b04e76b88e8f1750a6d58`.

- [services/agribrain/layer10_sire/l10_frontend_bridge.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer10_sire/l10_frontend_bridge.py) - blob `d46dfe032ad18118f95d3234b3882ea1b0da7197`.

- [services/agribrain/layer10_sire/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer10_sire/runner.py) - blob `9dc4ade7451de52ee6e4740d959c167811a63957`.

- [services/agribrain/layer1_fusion/engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer1_fusion/engine.py) - blob `0d3f3bb734e2bfc9afd8f318e87e36ad0b8dafb9`.

- [services/agribrain/layer1_fusion/eo_foundation_model.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer1_fusion/eo_foundation_model.py) - blob `0cf95efcdf54b765300f72b6a7aba0e264ee05cb`.

- [services/agribrain/layer1_fusion/segmentation.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer1_fusion/segmentation.py) - blob `8bd43399cdfb5ff91e727f53ad7b51a1bb5ed0c4`.

- [services/agribrain/layer2_contracts/state_transition.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer2_contracts/state_transition.py) - blob `51e3c52b7c557420e3c64c3054a4f1dc2d663d6a`.

- [services/agribrain/layer2_veg_int/growth_engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer2_veg_int/growth_engine.py) - blob `63b566fec50d0265a02eec8dad03765012b64b47`.

- [services/agribrain/layer3_decision/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_decision/runner.py) - blob `51c55a5b4c95e02f3a207dc9b918304244b8e39f`.

- [services/agribrain/layer3_water/assimilation/water_state_assimilator.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/assimilation/water_state_assimilator.py) - blob `41ee312b7430d28b23a4b2eaa6144d79e0a3b4e1`.

- [services/agribrain/layer3_water/contracts/assimilation_state.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/contracts/assimilation_state.py) - blob `0687a7dc7beceb04d59aabfb2a617d9c4ff8c07c`.

- [services/agribrain/layer3_water/contracts/state_factory.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/contracts/state_factory.py) - blob `275bff4e7a20385b9a05c5948359ac6309b9c32a`.

- [services/agribrain/layer3_water/contracts/water_state.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/contracts/water_state.py) - blob `6c9cd057043ff4b8c1f9ccc4fe8ee463d4ccebfa`.

- [services/agribrain/layer3_water/root_zone/availability.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/root_zone/availability.py) - blob `2e97ceee04b89b73f9ea470ebffeea70956221d3`.

- [services/agribrain/layer3_water/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/runner.py) - blob `67304903196ca68bcf7465718204c22e5f7de21d`.

- [services/agribrain/layer3_water/soil/layered_water_balance.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer3_water/soil/layered_water_balance.py) - blob `e445703e0640c77df072b7fe72b2933352ebdfb6`.

- [services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py) - blob `e13697be599862a9417e6f272bda37a09041e624`.

- [services/agribrain/layer4_nutrients/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer4_nutrients/runner.py) - blob `b780f91594bdc2f227beebe696989289f25bdae2`.

- [services/agribrain/layer4_nutrients/schema.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer4_nutrients/schema.py) - blob `8ab9a1bbaeb513cfc643f4f16131abe54b6317e4`.

- [services/agribrain/layer6_exec/outcomes/metrics.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer6_exec/outcomes/metrics.py) - blob `aed318c372a47c19b9a600adbb51d38c3cdd5c89`.

- [services/agribrain/layer6_yield/yield_forecast.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer6_yield/yield_forecast.py) - blob `1c3a5d0b0d0bfff4e8197705f31d905307c1e64b`.

- [services/agribrain/layer7_planning/engines/yve_yield_distribution.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer7_planning/engines/yve_yield_distribution.py) - blob `4bf72cffda0f16370e2864bdc3768fc2cdff3ff8`.

- [services/agribrain/layer7_planning/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer7_planning/runner.py) - blob `45216b1da80a5617e31357b2079e5aa0e1bcc3d5`.

- [services/agribrain/layer7_planning/schema.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer7_planning/schema.py) - blob `15b1bafdb65011dc93c8469df42af6ef153f5443`.

- [services/agribrain/layer8_prescriptive/engines/salinity_leaching.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/engines/salinity_leaching.py) - blob `7e58d605c40bd91368d54d82a6c189736927b0ac`.

- [services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/engines/spray_drift_gate.py) - blob `be683ec61bac7c9c50364b1c369fa04169a24dff`.

- [services/agribrain/layer8_prescriptive/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/runner.py) - blob `ea9076293d58f37fb57140ca84d5fdc0f7b3a310`.

- [services/agribrain/layer8_prescriptive/scenario_contract.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/scenario_contract.py) - blob `ad60b0f249214a8c0ddf8a3acb9c5caf9e3404d4`.

- [services/agribrain/layer8_prescriptive/scheduler.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/scheduler.py) - blob `b1612db59a9357a4665e09036f1399988ec2d33d`.

- [services/agribrain/layer9_interface/engines/conversation_memory.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer9_interface/engines/conversation_memory.py) - blob `f6551073a2c4d5ca387ce852fcd3a5ab3400ea42`.

- [services/agribrain/layer9_interface/engines/semantic_cache.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer9_interface/engines/semantic_cache.py) - blob `6e65e05d7247fbd17badd1a6de95bd4f689cf196`.

- [services/agribrain/layer9_interface/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer9_interface/runner.py) - blob `a0c6ae7baa06b2d739454d16828be0a5b9e9f306`.

- [services/agribrain/mesia/assimilation/observability_analyzer.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/assimilation/observability_analyzer.py) - blob `20b9c909e6eeef55020c89021370c75f95bbc8dd`.

- [services/agribrain/mesia/assimilation/spatial_lattice.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/assimilation/spatial_lattice.py) - blob `f7f9a224e9a253d234332dd818e7784825cf9ff3`.

- [services/agribrain/mesia/behaviour/likelihood_engine.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/behaviour/likelihood_engine.py) - blob `105483ef6b7cafd749983b61657e496e605a3f4f`.

- [services/agribrain/mesia/identity/correlators.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/identity/correlators.py) - blob `46be01c2694fd1cb06b62b4128372b8c94c367d8`.

- [services/agribrain/mesia/lanes/wifi/csi_extractor.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/lanes/wifi/csi_extractor.py) - blob `e18e17ea09c6848b4c3a7ad484bde58b648946a9`.

- [services/agribrain/mesia/learning/asmae_evaluator.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/learning/asmae_evaluator.py) - blob `60bdd8c8c7bfa332bfadc85d3424f1d718056dde`.

- [services/agribrain/mesia/learning/masked_link_trainer.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/learning/masked_link_trainer.py) - blob `c0fc768d3cd807165e9159199556a20fa5aa00cf`.

- [services/agribrain/mesia/learning/neural_receiver.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/learning/neural_receiver.py) - blob `bd224bb65c03f5c533d96ddb1009eafcc62e881f`.

- [services/agribrain/mesia/service.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/mesia/service.py) - blob `76f0e881d4c6b5ddd4b4520ef03b68e2bb3412f2`.

- [services/agribrain/orchestrator_v2/chat_adapter.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/orchestrator_v2/chat_adapter.py) - blob `1cff479e9c324eb6fca22c1fdf5a172f60497f4d`.

- [services/agribrain/orchestrator_v2/run_entrypoint.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/orchestrator_v2/run_entrypoint.py) - blob `9a522ba111d3fdf939cb498dcd04a4f893052d73`.

- [services/agribrain/orchestrator_v2/runner.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/orchestrator_v2/runner.py) - blob `6706c3bcfb39ff22054cd9088b634cd2d5cf925c`.

- [services/agribrain/orchestrator_v2/storage.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/orchestrator_v2/storage.py) - blob `f9886816eca2d9b648c12cca6e00867df69c34f9`.

- [services/agribrain/scientific_contracts/observation.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/scientific_contracts/observation.py) - blob `c5bf8fbcf01aa005a789c5e5297e7b8b0b1239a4`.

- [services/agribrain/sensor_runtime/registry.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/sensor_runtime/registry.py) - blob `2acc6f49135d7da9ba700b21870ed98839b901f9`.

- [services/agribrain/sensor_runtime/security.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/sensor_runtime/security.py) - blob `85a654ddef1995d15b555f52d638bdbd905e30c8`.

- [services/agribrain/sensor_runtime/storage.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/sensor_runtime/storage.py) - blob `23de3ea521c183e8e791014f0bd3f1cde8ccfb20`.

- [services/agribrain/visual_sources/tile_proxy.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/visual_sources/tile_proxy.py) - blob `aecccec4275c25ea8d40821ea4b31b16dfd62193`.

- [services/agribrain/world_model/belief_snapshot.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/belief_snapshot.py) - blob `b77f52bf8eafb2912d7aea0b99693bf5e9adc647`.

- [services/agribrain/world_model/canonical_worldline.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/canonical_worldline.py) - blob `eebca540a391ce46ee0f93fab870c776214748a0`.

- [services/agribrain/world_model/contracts.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/contracts.py) - blob `8ff042bae7f1259c9bb565203cb9ce184ab46986`.

- [services/agribrain/world_model/forecast_archive.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/forecast_archive.py) - blob `cb5fc4cae9dbb74a13f33ed29af90669ef79c076`.

- [services/agribrain/world_model/historical_extractor.py](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/historical_extractor.py) - blob `922577032f2a2fdaac2c3611e933a72fae9ebda2`.

- [src/app/api/agribrain/intent/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/agribrain/intent/route.ts) - blob `de16f24d6f1522f645364bdc2d1380cb441410e9`.

- [src/app/api/ai/chat/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/ai/chat/route.ts) - blob `8dcb383f7b3c2ef5fa19c7582257e0095e121850`.

- [src/app/api/cycles/[id]/tasks/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/cycles/[id]/tasks/route.ts) - blob `f2d3ad12260b355afe246dd8e80e8562ae5082b0`.

- [src/app/api/dashboard/stats/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/dashboard/stats/route.ts) - blob `bf35a17e86451fdbf9d7aca00c6d5ce94a1e3c48`.

- [src/app/api/evidence/add/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/evidence/add/route.ts) - blob `15575f98b30e69cadefc22c28a291f152e6a2503`.

- [src/app/api/inputs/route.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/api/inputs/route.ts) - blob `46235b0e39e68a51d3aeeba825402e75bf3e9b3a`.

- [src/app/calendar/page.tsx](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/calendar/page.tsx) - blob `24347d354ae6c651b78d680da61c9ba47ea7b6c6`.

- [src/app/farm/page.tsx](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/app/farm/page.tsx) - blob `0abb4476cd85bc6e7ab595439e1af16ab853e839`.

- [src/lib/agribrain/gemini-advisor.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/lib/agribrain/gemini-advisor.ts) - blob `1a1d0de6250eb2c4c5253f302049675c48713e07`.

- [src/lib/agribrain/surface-contract.ts](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/src/lib/agribrain/surface-contract.ts) - blob `8bacf29c68ff8d15222f8b96592c55afd1163531`.

## 14. Ready-to-proceed decision

Proceed with foundation/world-model production training after the relevant corrected trajectory, timing, immutable corpus, independent split and label-support gates are accepted. Begin compatible exploratory representation work and scientific protocols earlier, keeping their role explicit. Proceed with Omega implementation as a scientific case and experiment program grounded in the same evidence, with independent discriminating outcomes required for knowledge promotion.

The immediate next deliverable is a corrected coupled baseline with truthful receipts and qualified actions. That baseline lets AgriBrain learn from what was actually known and done, lets AgriWise display the same state, and gives the future world model and Omega a defensible scientific basis.

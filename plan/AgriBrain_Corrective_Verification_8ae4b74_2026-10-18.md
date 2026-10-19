# AgriBrain corrective verification and implementation readiness — 8ae4b74

Review date: 18 October 2026. Reviewed candidate: **8ae4b7499766ce9e8a8acd020078e2a152aca5d6**. Parent: **ceb5dd47250a9aca5482dcb2904a5bb3f4105626**. GitHub main was independently observed at the reviewed candidate both during staging and final verification.

**All seven original CEB counterexample groups earn targeted repair credit in the executed scope.** Resource admission now rejects the original delayed-idle and before-fence lease-revival schedules. Soil and pond evaporation are separate through the full water pipeline. Actual typed L4 restrictions survive normalization, ranking and complete standalone L8 scheduling. Qualitative water degradation reaches nutrient confidence and output health. Original invalid flux/negative pond inputs reject. Legacy first-read generation and pre-rounding probability bounds are repaired.

The release still does not establish full package acceptance. A bounded adjacent **after-fence transport lease** schedule produces two simulated START effects and inconsistent owners. Other narrower receiving-contract limitations remain: pond storage above zero capacity, zero root support acquiring implicit loss-model priors, a dictionary-state permission merge, and a prescription warning outside its serialized dataclass contract. Those findings are distinguished from the repaired originals, unsupported assumptions, calibration targets and unexercised public paths.

**Proceed with planned implementation and qualified scientific work now.** Prioritize the transport ownership repair before claiming execution exclusivity, and complete the receiving-boundary items alongside the next planned scientific packages. Retain all full-acceptance milestones until their own integrated criteria are demonstrated. This review does not turn unfinished unrelated application features into universal prerequisites for world-model or Omega experiments.

## 1. Scope and evidence discipline

The candidate changes twelve production Python files, plus two repository audit/register documents and one repository test file. The review inspected the production delta and active dependencies. Repository tests and audit conclusions were excluded as correctness evidence. The reported 12/12, 6/6, 6/6 and 4/4 test-suite outcomes remain **user-reported**, not independently rerun here.

Six review lanes were assigned. Completed specialist evidence was combined with direct root follow-up for resource ownership and the full L4→L8 composition. Every conclusion below is tied to actual current-source execution or explicitly labeled static qualification. Four standalone L8 compositions were executed after exact missing dependencies were staged; the initial missing-file import gaps belonged to the review's partial source layout, not the repository implementation.

The initial staged 715 files and later dependency additions all match the exact candidate Git blobs. The final primary source layout has **730 production/configuration paths**; ledger dependencies are separately verified. These counts establish source identity, not reviewed lines or branch coverage. The twelve modified production files also pass independent syntax compilation without imports or bytecode writes.

Only inert data and local private stores/controller collaborators were used. No production/Git edit, repository push, service/DB/broker call, physical controller, actuator, drone or external training job occurred. The runtime findings concern command effects in a simulated collaborator, not measured litres or observed field behavior.

The normative inputs remain the original master repair plan, execution addendum, task register and supplied R3 monograph. All three plan files match their candidate blobs and are unchanged:

| Normative document | Exact candidate blob |
|---|---|
| `AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md` | `08d378a65992de859369950599df198e64244f01` |
| `AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md` | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| `AgriBrain_Work_Packages_Task_List_2026-10-07.md` | `8a564647af7e588802537817159117b349ff606b` |

The R3 PDF identity is SHA-256 `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; requirement references in the appendices use the supplied scientific extraction. The relevant scientific contracts concern conserved compartments, explicit support, separate physical/analysis increments, uncertainty/provenance, immutable history, qualified learning targets and command/execution/delivery identity.

The register has **52 open FA milestones, zero checked**. Its identities are **F01–F40 plus T01–T12**, rather than F01–F52. This corrects the supplied summary's label; it is not a production defect. An open milestone is a governance fact, not evidence that its implementation is wholly absent or defective. The original 2,564–4,540 programme hours are not a fresh remaining-effort estimate.

## 2. Original CEB repair disposition

| Group | Fresh production result | Disposition |
|---|---|---|
| CEB01 | Four original admission controls each produce one START. Original real lease-expiry revival before the fence produces one START; the old worker fails before sending. | **Original schedules fixed**; distinct after-fence transport case remains |
| CEB02 | Former 7 mm soil-only discrepancy now has soil evaporation 0, pond evaporation 7, total ET 15; soil/surface/whole ledgers close. Full pipeline publishes .59 + 5.71 + 3.50 = 9.80 mm total ET. | **Original and actual full-pipeline propagation fixed** |
| CEB03 | Actual full L4 nonconservation output → active normalizer → ranker → complete standalone L8 keeps all fertilizer actions blocked with LOW confidence and the original physical reason. | **Typed production path fixed**, beyond the former ranker-only scope |
| CEB04 | Conserved degraded water now reduces nutrient confidence, caps L4 health, records quality reasons; actual below-half root coverage also degrades. Former missing-root/10 cm profile now exposes .10 coverage, health .10 and water confidence .188. | **Original qualitative propagation symptoms fixed**; calibration/support-admission limits remain |
| CEB05 | Negative/nonfinite/bool flux fixtures and negative pond/positive-capacity overrun reject; negative serialized pond hydration returns None. Valid zero remains accepted. | **Original invalid inputs fixed**; zero-capacity inconsistency remains |
| CEB06 | Known-latest no-index legacy scoped first read, retry and restart all return publication generation 5 before any migration write; immutable head/checkpoint bytes preserved. | **Original fixed**; no new defect in two scoped adjacent controls |
| CEB07 | Tiny negative and over-100% raw probabilities reject before rounding in parser, validation, helper and store. Valid endpoints/aliases/true zeros remain legal. | **Original fixed**; no new parser finding in the bounded pass |

The W01 water-conservation controls remain correct: original impeding-profile soil 180→225 mm, net infiltration 45.10, runoff 54.90, drainage .10, direct closure 0. Full-pipeline serialized closure .02 remains within .05 mm. Repeated ponding warm/cold continuation and cumulative whole-system closure pass. Full L4 still receives actual posterior root storage **137.55→137.55 mm**, weighted FC/WP/saturation **.295/.0966667/.44**, VWC **.2293** over **60 cm**; the old 83.30 mm substitution does not recur.

The comparison uses the candidate's actual posterior and declared tolerances. It does not force the older 137.57 mm value or describe .01/.02 mm serialized residuals as exact zero.

## 3. Remaining concrete findings

### 8AE01 — an in-flight START outlives resource-lease revocation

**P1; actual OS-process ordinary submissions; F16–F18, Stage 6.** The repaired original checks occur before entering the actuator. One added bounded schedule pauses A **inside the inert driver transport after it has passed that production fence**. B waits a real 31.1 seconds, sees the still-idle collaborator, expires A's STARTING reservation, obtains the resource and applies START/ACK. A's already-entered transport then resumes and applies another START/ACK.

Observed result: **START B, then START A, no intervening STOP; both submissions return EXECUTING**. A's reservation is re-promoted to EXECUTING with `owner_token=None`, while B is also EXECUTING and the resource map still names B as owner. These are duplicate simulated command effects and inconsistent software ownership, not measured duplicate water delivery.

The before-fence repair is real: a worker that resumes before the check now sees expiration/revocation and fails. The adjacent case is different because its command already crossed that check. [irrigation_runtime/dispatcher.py:L886-L924](https://github.com/webClone/AgriWise/blob/8ae4b7499766ce9e8a8acd020078e2a152aca5d6/services/agribrain/irrigation_runtime/dispatcher.py#L886-L924) checks a token, then enters an effect-producing await; [irrigation_runtime/safety.py:L1633-L1642](https://github.com/webClone/AgriWise/blob/8ae4b7499766ce9e8a8acd020078e2a152aca5d6/services/agribrain/irrigation_runtime/safety.py#L1633-L1642) permits takeover of STARTING after timeout without distinguishing an unresolved transport. Subsequent ACK handling does not keep the revoked worker from returning EXECUTING in this schedule.

**Concrete repair:** under one resource transaction, validate token/generation and move an admitted claim into a durable SENDING/DISPATCHING phase before entering transport. A revoked worker cannot enter that phase. An operation already in an unresolved effect-producing phase must retain ownership/exposure until controller reconciliation proves unstarted, stopped or complete; software lease expiry alone cannot transfer its dispatch right. If takeover of in-flight operations is required for availability, use enforceable controller/driver generation fencing or qualified stop confirmation before transfer. Bind ACK promotion to current resource ownership too; an uncertain already-applied old operation needs reconciliation/cutoff obligations, not a silent null-token revival.

**Acceptance:** retain all five passing original controls, then replay this exact after-fence lease schedule. Require one consistent owner, no competing START while prior effect status is unresolved, no EXPIRED→EXECUTING promotion without authority, and conservative quota/watchdog/reconciliation continuity. Hardware commissioning is separate; the review operated no hardware.

### 8AE02 — pond storage with zero maximum capacity still passes admission

**P2; scientific API/domain consistency; CEB05/F04/F07.** `InfiltrationState(surface_storage_mm=5,max_surface_storage_mm=0)` is accepted by its constructor, soil factory and full water pipeline. The pipeline consumes that initial 5 mm as gross/net infiltration. It closes the ledger using the supplied initial store; this is not creation of water by a valid transition.

Both constructor and solver enforce storage≤capacity only when maximum capacity is positive: [layer3_water/contracts/water_state.py:L35-L50](https://github.com/webClone/AgriWise/blob/8ae4b7499766ce9e8a8acd020078e2a152aca5d6/services/agribrain/layer3_water/contracts/water_state.py#L35-L50), [layer3_water/soil/layered_water_balance.py:L139-L151](https://github.com/webClone/AgriWise/blob/8ae4b7499766ce9e8a8acd020078e2a152aca5d6/services/agribrain/layer3_water/soil/layered_water_balance.py#L139-L151). Yet zero capacity disables new pond retention elsewhere. The same zero therefore means both “no capacity limit check” and “no retained ponding.”

**Correction/acceptance:** define zero as no storage and validate 0≤storage≤capacity including zero, or migrate unknown legacy capacity into a distinct nullable/qualified representation. Reject this inconsistent input before propagation/hydration while keeping valid zero storage, positive-capacity ponding, dry and conservation controls. No external exploit or naturally generated invalid pond is claimed.

### 8AE03 — declared zero root support acquires implicit physical priors in L4

**P2; actual receiving-boundary execution on an explicitly constructed input; F10.** A frozen actual water object is deliberately changed to support 0 cm/storage 0 mm while keeping its other preexisting root quantities. The typed receipt correctly marks coverage 0 and degraded. The full L4 consumer nevertheless passes **60 cm root depth and VWC .25** into the actual environmental-loss model, and N/P prescriptions remain allowed under the generic degraded policy.

This is an inconsistent/unsupported boundary admission case, **not a claim that the validated factory normally generates it**. The valid root-profile controls all pass. The fallback is at [layer4_nutrients/runner.py:L517-L533](https://github.com/webClone/AgriWise/blob/8ae4b7499766ce9e8a8acd020078e2a152aca5d6/services/agribrain/layer4_nutrients/runner.py#L517-L533): nonpositive support becomes 60 cm, and storage truthiness chooses .25 for zero. A finite result over an invented physical domain must not be mistaken for an estimate supported by the supplied state.

**Correction/acceptance:** validate root-support/storage/retention consistency before water-dependent loss computation. Return qualified unavailable output, or an explicitly identified prior/scenario with its uncertainty and permitted uses. Preserve genuine zeros on valid support. The exact unsupported fixture must not silently become a 60 cm/.25 observation-like computation. Keep the valid 15/60 cm, deeper-request, nonconserved and conserved-degraded controls.

### 8AE04 — dictionary-state permission merge can discard a current prohibition

**P2 compatibility contract; active public-route reachability not established; F10/F15.** The actual typed L4 path is fixed. The explicitly supported dictionary branch of the normalizer still uses `setdefault` for permission. Given an existing `is_allowed=True` dictionary and a newly blocked typed prescription, the computed false permission is not applied. The hard restriction reason is appended but the permission remains true.

The actual ranker emits an allowed HIGH-confidence 120 kg_N/ha fertilizer candidate, and direct scheduler confirms it. However, the **complete L8 fixture independently blocks it through `multi_source_required`**. The review therefore does not claim complete L8 approval, publication or actuation bypass. It demonstrates contradictory restriction merging within this compatibility composition, not a recurrence on normal dataclass output.

[orchestrator_v2/runner.py:L3484-L3501](https://github.com/webClone/AgriWise/blob/8ae4b7499766ce9e8a8acd020078e2a152aca5d6/services/agribrain/orchestrator_v2/runner.py#L3484-L3501) must combine current and incoming permissions monotonically: a preexisting true cannot override a newly imposed false, and a preexisting false cannot be erased. Normalize strict types, preserve causes and make conservation metadata consistent. If this shape is unsupported, remove/reject it explicitly rather than accepting weaker semantics than the typed branch.

**Acceptance:** the same dictionary input is blocked before ranking and scheduling, independently of unrelated evidence gates. Typed mixed prescriptions must retain both regulatory and farmer reasons. Verify actual cache/API producers before asserting deployed reachability.

### 8AE05 — the new prescription-level degradation note is not serialized

**P3 contract detail; F10 and downstream product explanation.** L4 dynamically assigns `prescription.notes` for a degraded conserved boundary at [layer4_nutrients/runner.py:L677-L679](https://github.com/webClone/AgriWise/blob/8ae4b7499766ce9e8a8acd020078e2a152aca5d6/services/agribrain/layer4_nutrients/runner.py#L677-L679), but [layer4_nutrients/schema.py:L434-L464](https://github.com/webClone/AgriWise/blob/8ae4b7499766ce9e8a8acd020078e2a152aca5d6/services/agribrain/layer4_nutrients/schema.py#L434-L464) declares no such dataclass field. The actual live objects contain the warning; standard dataclass serialization of the actual output drops it.

Nutrient notes and top-level health/quality still carry the degradation, so this is not total loss of visibility. The probe does not establish what a deployed UI displays. Add a declared serialized explanation field or use an existing appropriate typed rationale; verify the actual API serialization/consumer while retaining top-level qualification.

## 4. Scientific meaning of the uncertainty repair

CEB04 now has real qualitative propagation. The conserved degraded fixture reduces N/P/K/S confidences from **1/.9/.88/.5** to **.667/.600/.587/.333**, changes health to **.4/degraded**, lowers reliability to **.333**, and records missing-driver/penalty metadata. A real 121 cm requested root over 60 cm support yields coverage **.4959** and a degraded receipt; exactly 120 cm gives .5 and is outside the code's strict <.5 policy. The former missing-root/thin-profile input also now receives a coverage penalty.

These are implemented conservative policies, not empirically calibrated uncertainty probabilities. The water factory rounds coverage-derived health: the .4959 case reports water health .5 before the receiving L4 cap of .4. That differs from interpreting the supplied summary as a universal upstream .4 cap, but does not undo the demonstrated degradation signal. Requested-root source/provenance and the biological meaning of the 50% threshold still require explicit scientific support.

An additional declared uncertainty control changes water confidence to .1 and deficit sigma from .412→2.145 mm; full L4 still uses the same generic 1.5 degradation multiplier and yields identical dependent confidence/quality as the low-health control. This is a reproduced **quantitative propagation limitation**, not evidence of measured calibration failure or a failure of the repaired qualitative claim. The target is typed uncertainty with units, support, dependence and empirical validation, rather than another arbitrary global scalar.

The economics implication is dependency quality: nutrient loss, application, yield response and profit calculations need the relevant physical support and uncertainty. This review establishes code-boundary behavior, not a measured change in yields, realized profit, environmental benefit or treatment effect. Calibration and counterfactual outcome packages retain their independent acceptance criteria.

## 5. Detailed next implementation sequence

| Lane | Deliverable | Decisive acceptance | Plan context |
|---|---|---|---|
| A — transport ownership | Atomic token-to-SENDING transition; no lease-only takeover of unresolved transport; qualified ACK/recovery ownership | Original delayed/before-fence controls stay at one START; after-fence schedule has no competing effect or dual EXECUTING/null-token revival | F16–F18, with F19 regression obligations; Stage 6 |
| B — physical admission | Zero-capacity semantics and root-supported boundary consistency; qualified unavailable/prior treatment | Pond5/cap0 rejected or explicitly migrated; support0 never becomes unqualified60cm/.25; valid zeros and supported states preserved | F03/F04/F07/F10 |
| C — adapter/explanation consistency | Conjunctive dictionary permission merge; declared prescription warning field | All accepted input shapes preserve current prohibitions; typed/dataclass JSON retains the warning; healthy controls remain usable | F10/F15, typed F01/F02 contracts |
| D — uncertainty and durable scientific records | Separate policy discount from calibrated uncertainty; persist or content-address transition/analysis/eligibility receipts | Relevant uncertainty changes have justified effects; scope/cutoff/restart preserve receipt identity and failed-transition qualification | F05/F08/F09/F10, objective-specific F23–F25/T02/T04 |
| E — planned scientific/product implementation | Continue the existing package dependencies on the qualified interfaces | Active-caller composition, numerical support, replay, role-qualified independent outcomes and appropriate empirical evidence for each package | Existing 17-stage addendum and 52-package register |

Practical steps for Lane A:

1. Name the exact resource key and capability policy: per device, per zone, or a qualified multi-zone controller. Use one authoritative owner/generation per applicable resource.
2. Separate “admitted but never entered transport” from “transport may have applied.” Make the transition atomic and permission-consuming. Expiry may revoke only the first category without physical reconciliation.
3. Keep delivery exposure and operation identity through unresolved send/ACK. Reconciliation must not invent delivered depth or lose cutoff/watchdog duties.
4. Bind ACK, retry and restart to the same generation. Define stale-result behavior explicitly, including failure to stop an applied stale command.
5. Reproduce both original and new OS-process schedules, then run the repository's relevant regression suites. Evidence from a real driver/controller contract is a separate commissioning gate.

Practical steps for Lanes B/C:

1. Define support/store/capacity validity once in typed contracts and enforce it on constructor, deserializer and consumer entry.
2. Keep unavailable physical estimates separate from explicit priors/scenarios. Preserve values of zero when zero is valid; reject contradictory support rather than substituting a denominator.
3. Normalize all supported nutrient shapes into one strict typed eligibility record, with immutable cause identities and conjunctive permissions.
4. Consume that record when generating candidates and finalizing schedules; explanation fields must survive actual serialization.
5. Test the real full L4→normalizer→standalone L8 flow with nonempty positive/negative prescriptions, then the public promotion path under its own independent gates.

Lanes B/C can proceed alongside A. Legacy generation and quantile parsing do not need another corrective cycle for their now-passing originals; retain their controls as regression boundaries. The next review should focus on the precise changed contracts and strongest integration evidence, rather than reclassifying repaired originals as unresolved because a narrower adjacent case exists.

## 6. Programme readiness and world-model/Omega work

This batch supplies a stronger physical and prescriptive foundation than its parent. It does not close every F03/F09/F10/F16–F19 or F24 criterion. The earlier broader work-in-progress register remains the guide for unchanged packages; this twelve-file review is not a new full-repository certification. It does not supply fresh acceptance for nutrient pool conservation, causal outcome metrics, crop scenario schema, durable sensor evidence, immutable learning windows, spatial/MESIA calibration, model registry/validation, economics or territorial products merely because those files were outside this delta.

World-model and Omega preparation can proceed on **objective-eligible subsets**: dataset/window definitions, independent targets, mechanistic baselines/residual experiments, archived prospective forcing and falsifiable diagnostic/experiment protocols. They must preserve observations versus reconstructions, requested versus supported domains, actual versus planned/delivered management and decision-time cutoffs. Failed transitions and unqualified priors need explicit roles/exclusion per objective. No measured field skill or biological identification follows from these software probes.

For implementation readiness: proceed with the scheduled scientific/product packages and the focused remaining repairs now. Keep live execution exclusivity acceptance open until 8AE01 is resolved and integrated; keep each full FA milestone open until its complete criteria are met. This is a task-specific boundary, not a universal serial prohibition on research or development.

## 7. Reproduction and limits

The evidence bundle provides authored offline probes, current observed JSON, exact-source manifests, normative receipts, specialist appendices and a read-only Git-object materializer. It includes no production source copies, repository tests/historical audits, generated controller/quota/checkpoint stores, field data or credentials. Original prior authored scripts are retained only as fixture definitions; earlier outputs are not accepted as current correctness evidence.

All **eleven official commands** completed successfully in a separate reconstructed workspace, including both real lease waits. **732 source-layout copies / 712 unique Git blobs** were verified, with unchanged production bytes afterward; **27 root observation comparisons** matched repaired controls and remaining counterexamples. Two initial replay commands needed missing bundle metadata/provenance inputs added, then passed targeted retries. Those were packaging omissions, not production failures; both initial logs and the correction are retained in the replay receipt. Successful exit means declared observations—including counterexamples—were reproduced, **not** that a number of production tests passed. The Git-object materializer is syntax-checked and uses `git cat-file` without fetch/checkout/commit/push; that route was not executed against a separate full Git checkout here. The local reconstructed-source replay verifies exact production bytes before and after execution.

No full repository test certification, complete orchestrator promotion, commissioned hardware, empirical uncertainty calibration, prospective field yield skill, causal treatment benefit or realized economic result is established. All such limits are reflected in the claim register and package-specific next acceptance work.


---

# Specialist appendix: Water conservation and compartments

# CEB02 and CEB05 verification — 8ae4b74

Pinned candidate: `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`, parent `ceb5dd47250a9aca5482dcb2904a5bb3f4105626`. Review date: 2026-10-18.

**The original CEB02 and CEB05 counterexamples are fixed in this executed scope.** Soil and pond evaporation are separated in the transition receipt and full water pipeline; the original invalid negative/nonfinite flux and negative pond states reject. Original W01 conservation and repeated ponding/restart controls also continue to pass. One adjacent validation boundary remains: positive pond storage with capacity0 is accepted and used by the full pipeline.

## Method and reproduction

The authored harness was adapted from the prior lane; all result values here were regenerated against this candidate. It imports production functions and actual data contracts, not repository tests/audits or copied old outputs. Calls cover `WaterStateFactory.create_soil_water_state`, `create_root_zone_water_state`, `LayeredWaterBalanceEngine.step_water_balance`, `WaterIntelligenceEngine.execute_pipeline`, and the production `_deserialize_soil_water`.

All89 imported repository module files resolve under the candidate source and match its Git tree; receipts are in `source-manifest.json`. That is verification of imported bytes, not all-function/branch coverage. No prior production dependency copy was required. Fixtures are inert local data; no production service, network, hardware, controller, Git mutation or production source edit was used. Both worldline module aliases point to a private lane path before using the deserializer.

There are exactly three bounded boundary groups beyond retained original W01 controls: A1 repeated ponding/round-trip, A2 compartment ET/capillary ledgers including the full water pipeline, and A3 original plus adjacent validation. No further exploration was added.

Official command from the workspace root:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-8ae4b74-review/trajectory/probes.py
```

`results.json` contains full inputs, states, receipts and independent calculations. There are no harness errors. The scientific basis is master-plan F03/F04/F07, execution stages2–3, and R3 AB-AGR-003/004/005/006 plus AB-DAT-005/007. Exact local normative receipts are in `normative-manifest.json`.

In source references below, all paths begin `services/agribrain/` and all lines refer to the pinned SHA above.

## CEB02 — Soil versus pond evaporation: fixed

The precise previous counterexample uses layer bottoms `[10,30,60]` cm, theta .20, FC .30, WP .15, saturation .45, residual .04, K `[.1,2,2]` cm/day, alpha .03, n1.5, initial pond5/capacity12 mm, P4, irrigation3, requested T8, evaporation7 and capillary rise6 mm.

| Coordinate | Candidate result |
|---|---:|
| Soil storage | 120→119.50 mm |
| Pond storage | 5→3.50 mm |
| Net infiltration | 1.50 mm |
| Transpiration | 8 mm |
| Soil evaporation | **0 mm** |
| Pond evaporation | **7 mm** |
| Total ETA | **15 mm** |
| Capillary rise | 6 mm |
| Drainage/runoff | 0/0 mm |
| Independent soil/whole residuals | **0/0 mm** |

The repaired soil ledger closes as ΔS_soil−.5 = netI1.5 + C6 − T8 − E_soil0. The surface ledger closes as ΔS_surface−1.5 = P4 + I3 − netI1.5 − E_pond7. Total ET is8+0+7=15. The former7 mm soil-only discrepancy is absent.

The candidate still physically extracts pond evaporation first, then soil evaporation (`layer3_water/soil/layered_water_balance.py:226–235`), and now publishes the two quantities separately (`326–345`). The receipt documents soil storage, net infiltration, total runoff, soil evaporation and pond evaporation with explicit control volumes (`layer3_water/contracts/water_state.py:315–334`). Its closure flag explicitly concerns soil+surface. These are substantive repairs, not just a renamed counter.

The no-ponding control produces T5.03, soil E7, pond E0, C6 and soil120→113.97 mm; both balances close. Bounded uptake is therefore preserved alongside the new evaporation partition.

### Full production pipeline: partition and total ETA both pass

To check propagation rather than only the low-level receipt, use the same .20 profile, K `[.1,2,2]`, initial pond5/capacity12, with no new rain/irrigation. The full pipeline receives explicit weather: Tmax38°C, Tmin22°C, wind2m/s, RHmin25%, RHmax65%, net radiation18MJ/m². Vegetation is LAI0/FVC0 with root depth.60m. Its internally generated ET is not overridden by the harness.

| Published actual coordinate | Result |
|---|---:|
| T | .59 mm |
| E_soil | 5.71 mm |
| E_pond | 3.50 mm |
| ETA | **9.80 mm** |
| Soil storage | 120→115.21 mm |
| Pond storage | 5→0 mm |
| Net infiltration | 1.50 mm |
| Soil/whole residuals | .01/.01 mm |

Both evaporation compartments are nonzero, so omission of either would be detected. Published ETA equals .59+5.71+3.50 exactly at publication precision. Every published component matches the transition receipt to .01 mm; receipt ETA also equals its components. The .01 mm serialized-state residual is within the declared .05 mm tolerance and is not reported as zero. Source: `layer3_water/runner.py:306–336` now reads `surface_water_evaporation_mm` and includes it in total ETA; `water_state.py:186–190` defines the matching actual-flux coordinate.

Acceptance credited: the original direct CEB02 counterexample, no-ponding control, and actual full-pipeline component/ETA propagation. This does not certify empirical ET calibration or every downstream consumer.

## Retained W01 and A1 round-trip controls: pass

For the original impedance fixture (theta/FC .30, K `[100,.01,.01]`, rain100, other direct fluxes0), the candidate returns soil180→225, gross infiltration100, net45.10, return runoff54.90, drainage.10 and closure0. The same profile through the complete pipeline returns soil214.56, ETA10.46 and closure.02, still within .05 mm. Dry and permeable controls close exactly. The original saturation-loss repair remains intact.

With pond capacity12, first interval rain100 and E2, surface0→10, soil180→225, runoff42.90 and drainage.10. Next dry interval E3 gives surface10→6.90, unchanged soil225, netI.10, drainage.10 and zero runoff. Both interval whole-system residuals and the cumulative residual are0. Candidate soil/pond evaporation coordinates preserve the correct soil ledger as well.

After JSON serialization and actual `_deserialize_soil_water`, warm and cold second-interval states and receipts are exactly equal. The new pond-evaporation field survives hydration. Source: `layer3_decision/runner.py:857–875`. This is state-shape continuation, not a new test of publication CAS, timeline corrections or cache identity.

## CEB05 — Original invalid inputs: fixed

Fresh A3 results:

| Fixture | Candidate outcome |
|---|---|
| Valid zero fluxes | Accepted; unchanged state, ETA0, no pond |
| Evaporation−2 | `ValueError` before transition |
| Capillary−2 | `ValueError` before transition |
| Capillary NaN | `ValueError` before transition |
| Boolean transpiration | `ValueError` before transition |
| Surface storage−5/capacity12 | Rejected at `InfiltrationState` construction |
| Surface storage13/capacity12 | Rejected at `InfiltrationState` construction |
| Serialized negative pond passed to production hydration | Returns None; no invalid soil state is hydrated |

The direct step validates all five flux scalars before arithmetic (`layered_water_balance.py:94–105`), and validates supplied surface fields (`139–151`). `InfiltrationState.__post_init__` rejects negative/nonfinite/boolean fields (`water_state.py:35–46`); the soil factory also converts dictionary infiltration into that typed contract (`state_factory.py:61–66`). These repairs prevent the old negative-E pond creation and negative-pond full-pipeline case while preserving valid zero.

## 8AE-C01 — Positive storage with zero capacity remains admissible

**Executed adjacent P2 validation limitation; CEB05/F04/F07, AB-AGR-003 and AB-DAT-007. This is not a valid-input conservation regression or an external exploit.**

In the same A3 validation group, construct `InfiltrationState(surface_storage_mm=5,max_surface_storage_mm=0)` and pass it through the production soil factory and full water pipeline. It is accepted. With a valid .20 profile and K `[2,2,2]`, no new rain or irrigation, the full pipeline consumes the supposedly zero-capacity initial reservoir as5 mm gross/net infiltration. It returns soil120→115.21, initial pond5→0, ETA9.80, closure.01 and data health1.

The constructor only enforces storage≤capacity when capacity>0 (`water_state.py:47–50`); the direct step repeats that guard (`layered_water_balance.py:150–151`). The field is documented as **maximum surface ponding capacity**, and the integration branches treat capacity0 as no retained ponding. Thus the same zero value disables capacity checking while disabling new storage retention.

Scientific implication: invalid or ambiguous initial storage metadata can enter a physically balanced calculation. The ledger honors the supplied5 mm and does not create it; the defect is admitting a reservoir beyond the stated maximum. No claim is made that a normal candidate-generated valid state spontaneously becomes inconsistent.

Remediation: if0 means no storage, require0≤storage≤capacity including capacity0 at construction, hydration and execution. If legacy records use0 to mean unknown capacity, migrate them into an explicit unknown/legacy state with a documented eligibility policy; avoid overloading the same numeric value with both meanings.

Acceptance: the5/0 fixture rejects or returns an explicitly qualified legacy result before ordinary scientific execution;0/0 and5/12 remain valid; all original CEB02/CEB05 and W01 controls continue to pass.

## Disposition and limits

Credit CEB02's component/control-volume repair through the actual full pipeline, CEB05's original negative/nonfinite admission repairs, and preserved W01 conservation/restart behavior. Keep the zero-capacity initial-reservoir boundary open at P2. Exactly the original controls and three bounded groups were executed; no broader sweep, extra cache/concurrency probe, field calibration, service, hardware or complete R3/master-plan certification was attempted.


---

# Specialist appendix: Typed L3 to L4 boundary and nutrient qualification

# CEB04, W02 and root-support review at 8ae4b74

Reviewed main `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`, parent `ceb5dd47250a9aca5482dcb2904a5bb3f4105626`, 18 October 2026.

**CEB04's original downstream degradation failure is repaired in the executed full-L4 implementation.** The conserved low-health fixture now changes nutrient confidence, L4 health, quality and explanations. Root coverage is explicitly reported, and coverage below the chosen 50% threshold produces degradation through the actual water pipeline. The earlier W02 root-storage/unit correction and nonconserved prescription hard gate remain intact.

The remaining bounded concerns are an accepted zero-support boundary acquiring invented loss-model support/moisture, and heuristic confidence scaling that does not propagate distinct quantitative inherited uncertainty. A prescription explanation is also attached outside its declared dataclass contract. These do not erase the demonstrated repairs or establish a deployed physical failure.

## Execution and source identity

`probes.py` runs the prior six compositions plus **exactly three** additional boundary cases. All nine completed with their authored assertions. `results.json` contains the complete inputs/receipts, independently integrated support references, actual loss-model arguments and full output dataclasses. `executed-source-manifest.json` verifies **113 candidate production files**, with each import checked against the exact candidate tree before execution and all loaded candidate files rechecked afterward. `review-source-manifest.json` records focus line references and normative-source hashes.

All imports resolve to this candidate; no prior result or prior production bytes are correctness evidence. The actual water pipeline, root factory, typed receipt and full `run_layer4_standalone` execute. The loss-engine observer records arguments and calls the real method unchanged. No target AST/body edits, repository tests/audits, production/Git writes, services, network, controller or hardware calls occurred.

The original, shallow/deep root and new 121 cm root cases use unchanged pipeline-produced water states. Nonconserved, low-health, zero-support and inherited-uncertainty cases deliberately replace fields on actual frozen production dataclasses to test the receiving boundary. Such cases demonstrate boundary behavior; they do not demonstrate that the current water solver naturally emits those records. Standalone calls omit semantic lineage as allowed by that API; no complete orchestrator/species-authority/physical-action acceptance is claimed. Platform CEB03 normalization/ranking is owned by the other lane and was not re-audited here.

## Repaired controls

The profile has layer bottoms `[10,30,60] cm`, prior theta `[.18,.23,.28]`, FC `[.25,.28,.32]`, WP `[.07,.09,.11]`, saturation `[.40,.43,.46]`, conductivity `[2,2,2] cm/day`, and lab-measured parameter provenance. Weather is the same hot dry controlled fixture: Tmax38/Tmin22°C, rain0, wind2m/s, RH25/65%, net radiation18 MJ/m²; LAI3/FVC.8. All references integrate the **candidate posterior profile**, not a fixed target storage constant.

| Reused control | Current result |
|---|---|
| Original W02, 60 cm roots | Independently integrated **137.55 mm reaches L4 as137.55**; FC/WP/saturation **.295/.0966667/.44**; actual loss engine gets VWC**.2293** and depth**60cm**. The old supplied137.57 differs by only.02mm after integration; the prior83.30 substitution does not recur. |
| Shallow15cm roots | 100/50/0mm active overlaps; **20.60mm** storage, FC/WP/saturation **.26/.0766667/.41**, VWC**.1373**, depth**15cm**. |
| Requested120cm roots/profile60cm | Storage remains **137.55mm over60cm**, requested depth**120cm**, coverage**.5**. No water below the modeled profile is invented. The explicit `<.50` policy does not degrade this exact boundary. |
| Healthy deficient-evidence prescription control | Soil N1/P1/K10ppm, NDVI.2/NDRE.05, vegetative stage: **APPLY_N163.1 allowed**, **APPLY_P43.8 allowed**; K250 independently blocked by its existing rate constraint. State N/P/K/S confidence **1/.9/.88/.5**; health**.75/status ok**, reliability**.5**. |
| Same evidence, declared nonconserved receipt+1mm closure | All three prescriptions blocked with `nonconserved_water_transition`; all nutrient confidence, L4 health/ceiling/reliability **.2**, status degraded, hydrology quality reason/penalty present. This is a non-vacuous hard-gate control. |
| Same evidence, conserved but declared water health.2 | Now confidence **.667/.600/.587/.333**, health **.4**, ceiling/reliability **.333**, status **degraded**, `DEGRADED_WATER_BOUNDARY` and penalty recorded. N/P remain allowed with unchanged doses; allowing some capabilities is not itself a failure. |

The low-health result is the material correction: its state and top-level health/quality are no longer identical to the healthy control. Nutrient notes explicitly acknowledge degraded transport/availability. The hard conservation gate is retained rather than replaced by the softer confidence penalty.

Current source references, relative to `services/agribrain/`:

- `layer3_water/contracts/state_factory.py:261–338` integrates actual supported overlap/weighted retentions. `layer3_water/runner.py:299–305` evaluates the posterior root zone. `root_zone/availability.py:25–35` forwards supplied saturation.
- `layer3_water/contracts/assimilation_state.py:84–95` now includes requested depth and coverage. `water_state.py:424–472` computes coverage and emits the typed receipt.
- `layer4_nutrients/runner.py:192–210,250–271` consumes the actual receipt; **517–533** uses supported depth for VWC and loss calculations, with no fixed300mm denominator in this canonical path.
- `runner.py:655–679` retains the nonconserved hard block and adds conserved-degraded confidence/note handling. **787–797** now records degraded health/quality. The public wrapper passes its L3 output into the same implementation at **1209–1230** (static caller trace only).

## Three additional boundaries

### 1. Root coverage below50% now propagates through actual production

Requested root depth **1.21m** over the same60cm profile produces a typed requested depth121cm, supported60cm and coverage **.4959**, while preserving137.55mm storage. The actual factory/pipeline lowers water health to **.5** and water confidence to **.465**; receipt `is_degraded=True`. Full L4 becomes degraded with confidence/reliability/health as in the repaired low-health case above.

This credits a real producer→receipt→L4 path, not only a manually toggled flag. At exactly120cm, coverage.5 is outside the `<.50` gate; at121cm it is inside. Source: `state_factory.py:424–439`, `water_state.py:430–440`. The arithmetic and chosen threshold behavior are verified. **The50% threshold, coverage-to-confidence multiplication, fixed1.5 L4 multiplier and quality caps are policy heuristics, not empirically calibrated error probabilities.** The supplied R3 does not establish50% as a universal biological sufficiency threshold; domain/parameter provenance and empirical validation remain necessary for such a claim.

### 2. Zero-support boundary is marked degraded but still acquires physical priors

**Reproduced receiving-boundary defect; review priority P2; declared input, not a generated solver incident.** Starting from the same actual water object, the case explicitly declares supported depth**0cm** and root storage**0mm**. The typed receipt reports requested60cm, support0, coverage0 and degradation. The remaining preexisting root quantities deliberately remain available, making this an inconsistent/unsupported boundary that the receiver should reject or qualify before physical calculation.

L4 keeps support0/storage0 in SWB, but its actual loss-engine call receives **root_depth_cm60** and **soil_moisture_vwc.25**. Both are newly substituted physical support/state, rather than derived measurements. It still emits allowed N163.1/P43.8 with a generic degraded warning and confidence reduction. The numeric loss-model result is finite, so it can be mistaken for an estimate over supplied root support.

The cause is exact at `layer4_nutrients/runner.py:517–521`: nonpositive supported depth is replaced by60cm; storage truthiness selects.25 for zero. This is not the original W02 corruption on valid profiles—the valid profile controls still pass. It is a separate unqualified-support admission path in the same repaired boundary. No claim is made that a candidate validated factory normally creates zero support, or that a literal zero storage is physically possible with this fixture's residual profile.

**Fix and acceptance:** validate consistency/availability of requested/supported depth, storage and hydraulic aggregates before calling water-dependent loss models. An unsupported or contradictory boundary must yield a qualified unavailable transport/loss estimate or an explicitly identified prior/scenario with its authority and uncertainty; it must not silently create a60cm physical domain. Preserve genuine zeros on valid support. Re-run this exact declared-support fixture and require no implicit60cm/.25 observation-like calculation, while preserving all valid-root and nonconserved controls.

### 3. Quantitatively different inherited uncertainty produces the same L4 penalty

The conserved low-health case is repeated with explicitly inherited soil sigma **.25**, model sigma **.2**, overall water confidence **.1**, and root Ks sigma **.25**. The typed receipt correctly differs: water confidence **.1 instead of.938**, transpiration-deficit sigma **2.145 instead of.412mm**. Yet L4's physical loss arguments, state confidence, prescriptions, quality and health are identical to the original low-health case: its adapter uses the boolean degradation to choose the same fixed multiplier1.5.

**Classification:** demonstrated quantitative propagation limitation, not a measured calibration failure or contradiction of the repaired qualitative CEB04 behavior. No exact downstream sigma/confidence mapping can be certified from these fixtures. `runner.py:198–210,225–226` consumes physical fields/degradation but not receipt water confidence/deficit sigma; **668–676** divides existing scalar confidence by the fixed multiplier. `WaterUncertaintyBudget` retains heterogeneous scalar components without a downstream joint-support/covariance model in this path.

**Next step:** separate explicit conservative policy discounts from calibrated uncertainty. Transport uncertainty with units, support, provenance and dependence to the relevant water-dependent nutrient/loss estimates and action policy; validate it against independent outcomes. Demonstrate a justified monotone response to increased relevant uncertainty, or document why an independently supported action remains unaffected. Do not present the fixed scalar penalty or these nine offline calls as empirical uncertainty calibration.

## Smaller contract detail and decision-order qualification

At `runner.py:677–679`, the new prescription warning is assigned dynamically as `prescription.notes`. `layer4_nutrients/schema.py:435–465` declares no notes field. The actual live N/P objects have the warning, but standard dataclass conversion of the actual output drops it; `results.json` records both live notes and declared-field serialization. Nutrient notes and top-level quality remain present, so this is a limited prescription-contract issue, not total loss of degradation visibility. Add the explanation to a declared serialized field and verify the actual API consumer before claiming a missing UI warning.

The confidence discount occurs after optimization (`runner.py:540–545` versus668–679). The executed N/P cases remain above the optimizer's.5 action-confidence threshold, so unchanged doses do not demonstrate wrong eligibility. Moving or reconciling dependent decision gates should be reviewed if confidence is intended to control action choice, but this pass does not claim an unexecuted threshold-crossing prescription defect. No additional scenarios were opened.

## Scientific acceptance scope

Master plan F10, **389–413**, stage4 (dependencies F03/F04/F05), requires typed root-supported boundaries, interval drainage separation and missing-support/uncertainty propagation. Tasks `ST04-F10-01..04/FA`, **546–571**; the sequencing addendum line9 distinguishes verified slices from full acceptance. R3: **AB-AGR-008874–876**, **AB-AGR-010882–884**, **AB-DAT-007683–685**, **AB-DAT-005675–677**, **AB-ARC-006742–744** in the supplied scientific sections.

CEB04's original qualitative degradation-propagation symptom is corrected, and root coverage metadata/under-threshold propagation are verified. W02's valid-profile storage/unit fix and the nonconserved hard gate survive. Zero/missing-support admission, quantitative uncertainty semantics, empirical threshold justification and declared prescription serialization remain bounded follow-ups. Nonzero multi-day drainage/replay, whole F10/F11 acceptance, full orchestrator authority and physical delivery were not tested or certified.


---

# Specialist appendix: Concurrent resource ownership and driver admission

# Resource ownership verification — 8ae4b74

Pinned candidate `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`, parent `ceb5dd47250a9aca5482dcb2904a5bb3f4105626`.

**Both original CEB01 failures are repaired at their tested boundary.** Delayed truthful idle replies no longer supersede another acknowledged execution, and a worker resuming before the pre-send fence after lease takeover is refused. A distinct, bounded ordinary-submit schedule still yields two START command effects when the first transport pauses after that fence. The new resource map improves admission but does not fence a command already in flight.

## Method and original repair credit

The root reviewer freshly ran the authored current-source simulations after the delegated runtime lane stopped. Production dispatcher, actuator, quota store and data contracts run unchanged. Only the transport/controller collaborator is inert local code, with explicit scheduling barriers and a shared simulated controller file. OS workers have independent dispatcher/driver instances and share the actual quota-store implementation in a private directory. No network, controller, broker, hardware, production store, repository test, audit assertion or Git mutation was used.

`run_originals.py` executes the four retained schedules. `run_fixed_ttl.py` executes the original before-fence timeout schedule with a real 31.1-second wait; no production clock or ledger byte is patched. The controlled exception comparison uses two independent dispatchers in one process, matching the original; all race/lease schedules use two actual OS processes. Imported production bytes are checked against the candidate tree in the wrappers and `build_receipts.py`.

| Schedule | START effects | Current result |
|---|---:|---|
| A claims, B samples idle, A ACKs, delayed B reply arrives | 1 | A EXECUTING; B STOP_REQUESTED |
| Query raises after A is executing | 1 | A EXECUTING; B STOP_REQUESTED |
| Simultaneous two-process idle replies | 1 | One EXECUTING, one STOP_REQUESTED |
| Both idle replies, B's held until A ACK | 1 | One EXECUTING, one STOP_REQUESTED |
| A pauses before production fence, B starts after lease expiry | 1 | B EXECUTING; revived A FAILED before any A START |

The first correction binds `query_ts` to the time before the status request (`dispatcher.py:519–525`), preventing response delivery time from masquerading as acquisition time. The second atomically revokes the old reservation when the STARTING lease expires (`safety.py:1633–1642`), records a resource owner/token (`1681–1687`), and checks reservation, lease and resource token before calling the actuator (`dispatcher.py:886–924`). These are substantive fixes to the original schedules.

## 8AE01 — transport already in flight survives lease revocation

**P1, reproduced ordinary public submissions in two OS processes; F16–F18, Stage 6.** Exactly one adjacent schedule is added by `run_transport_boundary.py`:

1. A submits normally, obtains ownership and passes the new production token/lease check.
2. A enters the inert `send_command` transport and pauses before its simulated START effect. Its command is now in flight; the production checks are not modified.
3. B waits a real 31.1 seconds, queries the still-idle collaborator and submits normally. Claim takeover expires A and B sends START/ACK.
4. A's already-entered transport resumes and sends its own START/ACK.

The collaborator records **START B followed by START A**, with no intervening STOP. Both submissions return **EXECUTING**. A's reservation is promoted back to EXECUTING with `owner_token=None`; the resource map still identifies B's token as current. B's reservation also remains EXECUTING. `transport-boundary-results.json` retains workers, exit codes, pauses, command effects, reservations and the resource map; `timelines.json` records the schedule.

This is distinct from the repaired before-fence lease revival: A has already passed the new check and entered transport before B's takeover. No direct claim-API reissue or artificial ledger corruption is needed. The witness demonstrates duplicate command effects and inconsistent software ownership, **not** duplicate delivered litres, simultaneous physical water flow or the behavior of any deployed controller's own interlocks.

### Cause and concrete repair

STARTING can expire irrespective of whether transport has already begun. A one-time pre-send check cannot revoke a transport effect that is paused after it. The shared row is atomically revoked, but the old transport has no qualified generation check and the ACK promotion does not reject the revoked owner. The two steps that need a single contract are resource ownership and permission to enter an effect-producing transport.

Use an atomic resource-token transition from an admitted pre-send claim into SENDING/DISPATCHING, immediately before entering transport. A revoked or expired worker must fail that transition. Once transport has entered an unresolved effect-producing phase, do not grant a competing operation solely because a software lease elapsed. Retain ownership/exposure until qualified controller reconciliation proves unstarted, stopped or complete. If the design needs availability through takeover of such an operation, the controller/driver must support enforceable operation/generation fencing, or the prior operation must be safely stopped and confirmed before transfer.

Bind ACK promotion to the current resource generation as well. A revoked reservation must not silently regain EXECUTING with a null token; an already-applied but unowned outcome needs retained reconciliation/cutoff obligations. Merely adding another local timestamp or token check leaves the final check-to-effect interval unless takeover respects the unresolved transport phase.

### Acceptance

Retain all five now-passing original controls. Add this exact after-fence, before-effect schedule and distinguish it from direct token-API fixtures. Require no competing START while prior transport outcome is unresolved, no EXPIRED→EXECUTING revival without authority, one consistent resource owner, and preserved quota/watchdog/reconciliation obligations. Software simulation acceptance is separate from controller commissioning; no hardware was operated here.

## Reproduction and limits

Run, from the workspace root:

```bash
python repair-8ae4b74-review/protocol/run_originals.py
python repair-8ae4b74-review/protocol/run_fixed_ttl.py
python repair-8ae4b74-review/protocol/run_transport_boundary.py
python repair-8ae4b74-review/protocol/build_receipts.py
```

Each lease command takes roughly 32–34 seconds. The copied `run_adjacent.py` supplies scheduling helpers to official entrypoints; its old broad wrapper is not an additional required scenario. The evidence bundle documents only the official commands. No new cancellation/watchdog/driver-family full acceptance is inferred. R3 AB-EXE-002/003/004 and AB-ARC-008, with plan F16–F18 and the F19 regression obligations, remain the relevant contract scope.


---

# Specialist appendix: Legacy receipt and gust-unit regressions

# Scoped checkpoint receipt verification

Candidate: `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`; parent: `ceb5dd47250a9aca5482dcb2904a5bb3f4105626`.

**CEB06 is fixed in the executed candidate.** The older unindexed legacy head now returns the known publication generation **5 on its first scoped read**, before any migrating write. Unscoped read, fresh-instance read and idempotent retry agree; none changes the head bytes. The original indexed pre-map 2E02 regression also remains fixed. No new concrete defect was found in the two bounded adjacent scoped-generation cases.

## Evidence and scope

`probes.py` executes production checkpoint APIs from the exact candidate `source` tree, reusing the original indexed schedule in `legacy_receipt_probe.py` and the previous CEB06 no-index schedule. `adjacent_probe.py` is a minimal private-store helper. The no-index schedule adds observations before its existing migration write: unscoped read, fresh service instance, idempotent retry and head-byte comparisons. The original schedule's checkpoint allocation, controlled head-write failure, independent B commits and A2 recovery are preserved. These fixture operations use inert private files only.

Exactly two adjacent scoped-generation inputs were added: retained receipt maps without the scoped index, and an explicit older cross-scope predecessor chain whose historical publication generation is unknown. The original four gust cases were retained as cheap unchanged positive controls; no additional unit cases or broad decision suite ran. Fixture function bodies for gust scheduling are reused unchanged from the authored original harness. They invoke the actual drift gate, scheduler and final invariant functions; a `CONFIRMED` result here is not top-level authorization or a physical spray.

`source-manifest.json` verifies **42 imported production modules** against the candidate Git tree and records each local source path, Git blob, SHA-256 and line count. The manifest hashes the prior authored harnesses for reproducibility; their old outputs and audit claims are not candidate evidence. `source-diff.txt` captures the four-line production change from the exact parent. No repository test suite, production/Git edit, network service, credentials, controller, device or field hardware was used.

## Fresh results

| Scenario | Candidate result |
|---|---|
| Original indexed pre-map 2E02: A2 allocated 2, recovered/published 5, then B publishes 6 | A2 load before/after B, retry and restart all return sequence/publication generation 5 |
| Original CEB06: receipt maps, scoped index and scope labels absent; latest A2 head generation 5 | **First scoped read = 5**, publication generation = 5 |
| CEB06 before any migration write: unscoped read, restart read, idempotent retry | Each returns 5; head bytes unchanged |
| CEB06 after independent B6 write | A2 load/retry/restart remain 5; immutable A2 bytes unchanged |
| Adjacent 1: receipt maps retained, scoped index/labels removed | Correct scoped A2 receipt returned; wrong cycle or geometry returns `None`; no head write |
| Adjacent 2: explicit older cross-scope chain, current head generation 9, historical checkpoint allocation 2 without receipt | Current scoped receipt resolves 9; older scoped read/restart retain allocation 2 with **no** `publication_generation`; head unchanged |
| Four previous gust controls: 2 m/s single, 7.2 km/h single, equivalent duplicates in both orders | All `CONFIRMED`, allowed, no blocked reason |

Raw details are in `results.json` and the original indexed output `legacy-receipt-results.json`. The runner completed successfully. None of these bounded results closes all coupled-state or weather-constraint acceptance criteria.

## Why CEB06 is repaired

References below are relative to `source/`. In `services/agribrain/world_model/canonical_worldline.py:291–313`, scoped fallback traverses predecessor records and checks cycle/geometry. The candidate adds `309–312`: when the matching record is the **current latest checkpoint** and the head has a known sequence, it returns that head sequence as `sequence` and `publication_generation`. This matches the known-current-latest behavior already present in the indexed branch (`270–289`) and unscoped read (`318–331`). The immutable record's allocation sequence remains unchanged.

The original 2E02 publication-map migration remains effective in both orphan publication (`418–432`) and normal publication (`490–504`). The executed indexed fixture exercises the latter when independent B6 preserves A2's publication receipt. Already-published retry uses maps or the known current head fallback (`390–407`). Historical non-head A1 retry still returns typed `ConcurrencyConflictError` without changing the head; this is recorded separately and is not a receipt-loss failure.

This supports **F09 stage 3**, particularly R3 AB-DAT-003/012 and AB-ARC-008: stable append-only provenance, consistent replay/persistence and reproducible identities. The supplied master-plan F09 card additionally maps AB-DAT-013 and AB-AGR-006 (`sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:362–391`). The scientific benefit is trustworthy checkpoint ordering/receipt metadata across reads, writes and restart. No numerical water-state corruption, dose error or delivered irrigation effect was tested or inferred.

## Historical scope qualification

The new fallback is intentionally limited to a known current latest head. The adjacent historical fixture is explicitly constructed private legacy input: its predecessor chain crosses scopes, unlike the modern per-scope writer. It is not a claim that modern valid checkpoints spontaneously acquire that chain. The current head supplies publication generation 9; an older checkpoint has allocation sequence 2 but no historical receipt map. Scoped traversal (`302–313`) returns the older allocation metadata without fabricating publication generation 9. A fresh service instance does the same.

This is a passing non-promotion control, **not recovery or validation of every historical publication generation**. Consumers must distinguish an absent `publication_generation` from a known publication order. The bounded review does not establish that all older formats, malformed heads, cross-process schedules, partial-scope requests or historical generations are repaired. No further migration defect is asserted from these two inputs.

## Reproduction and acceptance boundary

```bash
PYTHONDONTWRITEBYTECODE=1 python /workspace/scratch/de6bc2428cec/repair-8ae4b74-review/ownership/probes.py
```

The explicit CEB06 criterion passes: first scoped read 5 before migration; restart/retry agreement; unchanged checkpoint/head bytes on read; receipt 5 after B6 and restart. The original 2E02 fixture retains its passing credit. Keep both as acceptance examples, plus unknown-historical generation and scope-isolation controls. Full F09 and end-to-end scientific/field acceptance remain outside this bounded verification.


---

# Specialist appendix: Forecast archive and scoring

# CEB07 forecast probability-bounds verification — 8ae4b74

Exact candidate **`8ae4b7499766ce9e8a8acd020078e2a152aca5d6`**, parent `ceb5dd47250a9aca5482dcb2904a5bb3f4105626`.

**The original CEB07 pre-rounding probability-bounds counterexamples are fixed.** Tiny negative and over-100-percent levels now reject before rounding, consistently through parsing, helper scoring, constructor validation and archive admission. The earlier 2E03 percent grammar, numeric-percent metrics, timezone and archive repairs retain their credit. One new bounded endpoint/neighbor group found no additional defect. Wider independent-target qualification and sparse-score method conventions remain separate known acceptance limits; this is not full F24/world-model or field-validation sign-off.

## Execution and exact-source receipts

One fresh run completed **30 case groups**: all 29 previously authored groups adapted to this exact candidate, plus **one** new bounded valid-endpoint/invalid-neighbor group. `results.json` contains all current outcomes. No prior report/test result was reused as correctness evidence.

All **37 imported staged production blobs** and **two dependency blobs** matched the candidate tree. Archive Git blob: `68148135fc69e951c23c3b174e5f3e80b0313c87`; SHA-256 `7bd3771b567ae885ebe8f1611e77083230ce0440f6fb30885199509e08afd871`. `source-receipts.json` records runtime, source hashes and isolated run path; `executed-file-manifest.json` lists all 39 modules/dependencies and the authored/executed script hash. This is an import receipt, not per-line coverage.

Reproduce with Python 3.12 and NumPy/Pandas available:

```bash
python /workspace/scratch/de6bc2428cec/repair-8ae4b74-review/ledger/probes.py
```

Keep the sibling exact `source`, `git-tree.json`, `commit-metadata.json`, `source-manifest.json`, and `ledger/dependencies/crop_database/{__init__.py,registry.py}`. The two dependency files were copied from local source bytes and independently matched this candidate's tree blobs `462a82e514f8a954ebf8a53748313c18fae842d3` and `17aef77d0a0cdbaee919644b6715bc1d0c5703bb`; no network retrieval was needed. The script verifies candidate/parent/tree/source-manifest identity, core/dependency hashes and all imported source blobs, disables bytecode writes and creates a new `ledger/isolated` directory.

The pass uses direct production functions and private fixtures. Existing groups include selected thread schedules, injected link error, controlled process exit during valid serialization, existing-file corruption and a custom timezone. Ordinary invalid caller type/JSON exceptions are distinct from that process exit. No repository tests/audits, production/Git edits, external jobs/services/controllers or hardware were used. Controlled process interruption does not establish power-loss durability.

**FA** references below are current `source/services/agribrain/world_model/forecast_archive.py`; **YF** is current `source/services/agribrain/layer6_yield/yield_forecast.py`, under this review root.

## CEB07 original repair

The parser now checks finite normalized probability bounds at FA **202–204**, then rounds at **206**. The shared parser is called by the quantile helper (**227**), `ForecastRecord.validate` (**390**) and evaluator metric extraction (**667**).

| Original key | Current parse/helper/store outcome | Evaluation after rejected admission |
|---|---|---|
| `p-0.000001` | `ContractViolation` | Forecast absent; no numerical score |
| `-0.00000001` | `ContractViolation` | Forecast absent; no numerical score |
| `p100.000001` | `ContractViolation` | Forecast absent; no numerical score |

The original narrow failure—out-of-range raw levels becoming legal endpoints through six-decimal rounding—no longer occurs for these fixtures. Malformed keys (`''`, `pabc`, `q1%`), nonfinite suffixes and obvious out-of-range p keys remain rejected. Bare `1.0000004` retains the existing documented bare-number-percent interpretation, becoming approximately 0.01; it is not counted as an out-of-domain probability fixture.

## One new bounded adjacent group

`new_endpoint_alias_and_invalid_neighbor_controls` checks the opposite side of the contract: rejecting invalid neighbors must preserve valid endpoints and aliases.

| Cases | Actual result |
|---|---|
| `p0`, `q0`, `0%`, `0.0`, `p-0` | Legal level 0 (signed zero is equal to zero); store/evaluate successfully and preserve missing median/interval metrics as null. |
| `p100`, `q100`, `100%`, `1.0` | Legal level 1; store/evaluate successfully with null unsupported metrics. |
| Conflicting equal-level aliases `p0:0,q0:1` | `ContractViolation` during record validation. |
| `q-0.000001`, `-0.000001%`, `q100.000001`, `100.000001%` | Parser/helper/store each reject; cache count remains 0 and no final forecast exists. |

For quantile value 0 and observation 10, the valid lower-endpoint pinball loss is 0 and upper-endpoint loss is 20. Those values are mathematical endpoint losses, not proof of complete predictive skill. The valid point-mass-at-truth zero controls below remain valid too. No new defect was established by this bounded group; no second adjacent expansion was needed.

## Prior grammar, missingness and numerical repair controls

| Retained check | Fresh result on 8ae4b74 | Current code |
|---|---|---|
| Original 2E03 p/q percent grammar | `p1/q1/1%/0.01` → 0.01 and helper/evaluation score 0.2 for q=0,y=10. `p0.5/P.5/q.5/0.5%` → 0.005 and score 0.1. No fabricated median RMSE. | FA 187–206, 227, 390, 667 |
| Numeric-percent/canonical alias metrics | Canonical p, uppercase, decimal, explicit-percent and bare 10/50/90 encodings yield score 3, RMSE 5, sharpness 20, coverage true. Equal aliases deduplicate; conflicts reject. | FA 225–255, 388–405, 664–689 |
| Sparse missingness | q1/p99 tails give finite grid score≈0.2 with null RMSE/sharpness/coverage. q50-only gives score/RMSE 2 with null intervals. P90-only observation77 retains score4.6 and null unsupported metrics. Strict JSON parses all files. | FA 664–689 |
| True zero / Gaussian controls | q10=q50=q90=0 at truth gives score/RMSE/sharpness 0 and coverage true. Sigma-zero truth/error gives 0/2; N(10,1) at 10 gives 0.23369497725510913. | FA 258–276, 664–697 |
| Time/horizon | Ordinary naive and injected tzinfo-without-offset reject; horizons0.01/2 for a one-day interval reject. Aware fixed/cross-offset times preserve instants in cold round-trip. | FA 360–378 |
| Finite distribution / observed values | Empty helper input, nonfinite observation/mean/sigma, negative sigma and malformed/crossed/nonfinite quantiles reject. Missing predictive distribution rejects before temporal checks. | FA 219–276, 379–405, 630–658 |
| Producer interval convention | Real base/single-branch-posterior wheat methods retain mean4.5 and rounded P10/P90 3.92/5.08 using 1.28155σ. The explicit local archive adapter agrees with Gaussian coverage at observed5.175. | YF 104–131, 224–244; FA 691–697 |

The producer adapter is an offline numerical control, not proof of a deployed training/forecast pipeline, independent target support or field calibration. Minor interval-width differences arise from two-decimal producer endpoints. Finite-grid and analytical Gaussian scores need not be equal.

## Retained archive integrity controls

Current execution preserves the prior repaired archive behaviors:

- A committed mean1 rejects both attempts to replace it with mean99. Disk bytes and warm/cold reads remain unchanged; observation99 yields RMSE98.
- A child exiting83 during temp serialization leaves no partial final; retry succeeds. The orphan temp is inert. A reader during a paused temp dump sees absence of an uncommitted final; complete identical writers can both succeed.
- Concurrent incompatible link inserts yield one complete winner and one conflict. Identical inserts succeed. An injected link `OSError` leaves no final/cache/temp and permits retry.
- Caller P50 mutation1→99 after the production snapshot and later retrieved-copy mutation do not alter disk/cache/evaluation.
- Injected malformed JSON, top-level array, list metadata, malformed horizon and missing required field produce integrity exceptions. These fixtures were not generated by the successful writer.
- Colon-containing evidence sets remain distinct; reordered/identical evaluation retries deduplicate memory/disk; observation/microsecond differences retain distinct identities. Blank/None/scalar evidence IDs reject.
- Strict metadata JSON rejects nonfinite values without final/cache publication; nested zero remains valid. Invalid caller type errors remain separate from process-interruption fixtures.

Mechanisms: FA **30–58** complete temporary publication/conditional link; **479–527** snapshot, conflict resolution and durable-before-cache behavior; **529–588** reader/corruption handling; **703–729** evaluation identity and deduplicated durable-first append. These selected interleavings do not certify every scheduler or filesystem durability model.

## Remaining acceptance scope

No new parser defect was found in the completed bounded pass. **Known wider limits are unchanged**, and are not failures of CEB07:

- Nonblank evidence syntax does not establish independently qualified target variable/unit/support/time/role/domain. Direct API defaults remain `in_domain` and `observation_space` (FA **442–443**, **636–647**, **707–718**). The retained opaque-ID fixture does not test a deployed resolver or prove a deployed caller supplies bad evidence.
- The finite unweighted pinball average (FA **247–255**) remains named CRPS (**209–218**). It needs accurate method/grid/weight labeling or a documented integration rule. Valid Gaussian formulas and legitimate zero scores remain positive controls.
- Some malformed caller types have mixed exceptions; rejected cases publish no final/cache. A distribution-free record may be stored but evaluation rejects without numerical credit. Full scientific domain/horizon calibration and corpus lineage were not established.

To close the broader F24 package, preserve these now-passing parser/original controls while supplying checked independent target bindings and a transparent score/calibration convention. Full world-model, field-readiness and machine-authority conclusions require their separate plan work.

Normative references: master plan `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`, F23 **730–753**, F24 **755–779**; task list `AgriBrain_Work_Packages_Task_List_2026-10-07.md` **1069–1139**; sequencing addendum **36** (Stage8). Supplied R3 `current-plan-review/R3_current_scientific_sections.txt`: AB-DAT-005 **675–677**, AB-DAT-011 **699–701**, AB-ARC-007 **746–748**, AB-ARC-008 **750–752**, AB-ASM-014 **828–830**, AB-ASM-016 **836–838**, AB-ML-005 **990–992**, AB-ML-010 **1010–1012**. This bounded repair verification does not close those entire scientific capabilities.


---

# Specialist appendix: Active integration and plan traceability

# L4 to L8 restriction continuity — 8ae4b74

Candidate `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`, parent `ceb5dd47250a9aca5482dcb2904a5bb3f4105626`.

**The original CEB03 normalizer/ranker failure is fixed for the actual typed L4 output, and the prohibition survives the complete standalone L8 pipeline and scheduler.** Two bounded alternate-shape controls were also exercised. Typed mixed prescriptions preserve all blockers; the dictionary-state compatibility branch can still retain a stale `is_allowed=True` despite a blocked prescription. That branch's direct rank/schedule composition confirms a candidate, but the complete L8 fixture independently blocks it through its evidence invariant. No public approval or actuation bypass is established.

## Evidence and current execution

`eligibility_probes.py` runs actual L3 water generation and full `run_layer4_standalone`, then the exact active orchestrator `_normalize_nutrient_states` function, actual action ranker, constraint scheduler and complete standalone `run_layer8`. The normalizer and original L4 gate are loaded as unchanged AST function/node bodies with explicit namespace dependencies; the full orchestrator is not run. Later wrapper authorization/promotion is not claimed. The fixture supplies known crop/stage flags, seven explicit finite weather rows and a fixed planning date to isolate restriction preservation.

The nonconservation receipt is deliberately placed on a valid actual water object. It tests a declared failed boundary; it is not evidence that the water solver naturally generated the injected 2 mm discrepancy. A network guard prevents outbound socket calls, and no DB, deployed service, controller or hardware is used. Repository test/audit assertions are not proof. Missing source dependencies initially prevented importing full L8; exact candidate files were then staged and the complete probe was rerun. Those staging gaps were not production defects.

`verify_metadata.py` validates every imported/reference candidate blob and the normative plan documents. Final execution imports 138 production files; 146 unique imported/reference files match the candidate. This is source identity, not line coverage. The original exact-gate fixture plus real full-L4 composition and two alternate-shape controls are the bounded scope.

## CEB03 original and stronger integration control: pass

The actual full L4 run supplies N/P/K deficiency probabilities .9995/.9241/.937 and confidence .20 after its nonconserved gate. Its local prescriptions are blocked. The new normalizer forwards `mass_conserved=False`, closure 2 mm, `is_allowed=False` and the physical blocker for each state. The ranker produces blocked LOW-confidence fertilizer candidates, and the direct scheduler keeps all three BLOCKED.

The complete L8 run may transform the numerical candidate rates through its phenology/nutrient engines, but all three fertilizer actions remain disallowed, LOW-confidence and BLOCKED. Their schedules have no date and preserve `nonconserved_water_transition`. The K candidate additionally keeps its upstream rate blocker. A MONITOR action remains available under its separate policy. The returned authorization envelope is null, so this composition is not an authorization receipt.

The exact original probability-.8 composition also changes from the prior allowed 120 kg_N/ha candidate to blocked LOW confidence. Full L8 still blocks it after its rate becomes 48 kg_N/ha. Thus the repair is not credited merely because an empty prescription list or a low confidence score happened to occur.

Sources under `services/agribrain/`: `orchestrator_v2/runner.py:3432–3509` normalizes physical and prescription restrictions; `layer8_prescriptive/action_ranker.py:212–253` consumes permission/conservation, preserves reasons and adjusts categorical confidence. `layer4_nutrients/runner.py:655–679` is the upstream gate. Full L8 remains responsible for independent semantic, evidence, environmental and final invariant constraints.

## Two bounded compatibility controls

### Typed mixed prescriptions: pass

One typed nutrient state with two same-nutrient prescriptions—one allowed, one disallowed with `regulatory_N_limit` and `farmer_prohibition`—becomes disallowed in the normalizer. Both reasons survive ranker, direct scheduler and full L8. This verifies conjunction of typed restrictions and distinct cause preservation, rather than only the hydrology-specific string.

### 8AE04 — dictionary-state permission can override a new restriction

**P2 compatibility-contract defect; public-route reachability not established.** Supply the explicitly supported dictionary-state branch with N probability .8, confidence .8 and existing `is_allowed=True`, alongside a typed blocked N prescription carrying `regulatory_N_limit`. Water conservation is true to isolate the general prescription restriction.

The normalizer copies the dictionary and uses `entry.setdefault("is_allowed", is_allowed)`. The prior true value therefore survives despite the newly computed false permission. The blocker string is appended, leaving contradictory data: `is_allowed=True` plus a hard restriction reason. The actual ranker produces an allowed HIGH-confidence fertilizer candidate of 120 kg_N/ha, and the actual direct scheduler CONFIRMS it. This is an actual compatibility API composition, not a claim that normal dataclass L4 output takes this branch.

The complete standalone L8 run **blocks this fixture** through its independent `multi_source_required` invariant. Its resulting action is disallowed and its schedule says `action_blocked_after_evidence_invariant`; the regulatory reason remains in the action's reason list. Therefore the probe does not establish an end-to-end L8 bypass, successful publication or executed application. It shows that the new adapter's explicit dictionary branch does not preserve the same restriction conjunction as its typed branch.

Correct permission merging must be monotone: existing permission and newly computed upstream permission are conjunctive, with strict typed booleans and cause preservation. Do not let a cached true value override a current hard restriction; likewise do not erase a prior false value. Either validate/normalize the supported dictionary contract or remove the unsupported compatibility branch explicitly. Preserve conservation false and closure metadata consistently, rather than retaining contradictory stale values via setdefault.

Acceptance: this same alternate-shape input must be blocked before ranking/scheduling, even when unrelated independent evidence gates are satisfied; the healthy and typed mixed controls retain their legitimate behavior. Verify actual serialization/cache/API producers before claiming deployed reachability or closing broader promotion acceptance.

## Original thin-profile root-support control

The separate `root_support_control.py` reruns the exact former accepted missing-root input: actual `VegetationState(root_depth_proxy_m=None)` and a 10 cm profile. The runner still uses its assumed 1 m root prior, but the candidate now reports requested 100 cm, supported 10 cm, coverage .10, degraded true, water health .10 and overall water confidence .188. The original unqualified health1/confidence.938 boundary symptom is therefore corrected. The assumed-root provenance and empirical meaning of the coverage discount remain qualification targets, not newly measured calibration results. This direct-engine fixture does not establish an authenticated frontend route, public prescription promotion or actuation.

## Plan and scientific scope

All three normative plan blobs are unchanged and exact; `plan-results.json` shows 52 unique open FA rows and zero checked. The package identities are F01–F40 and T01–T12, not F01–F52. This is an editorial correction to the supplied summary, not a production defect.

CEB03's actual typed restriction loss is repaired, with stronger standalone L8 integration evidence than the previous ranker-only audit. F10/F15 and typed provenance F01/F02 remain relevant; broader F38 integration, durable transition/failure receipt identity, qualified weak-label/corpus objectives and public prescription promotion are separate acceptance criteria. The latter are not inferred from a successful standalone run. Scope did not expand into training, field calibration, economic outcomes or hardware.

Official commands:

```bash
python repair-8ae4b74-review/platform/eligibility_probes.py
python repair-8ae4b74-review/platform/verify_metadata.py
python repair-8ae4b74-review/platform/root_support_control.py
```

The report combines the completed specialist fixtures with direct root-review execution after exact candidate dependency staging. Raw current outputs, source receipts and normative mappings accompany it.

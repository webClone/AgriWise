# AgriBrain corrective implementation audit — ceb5dd4

Reviewed 18 October 2026. Candidate and observed GitHub main: **ceb5dd47250a9aca5482dcb2904a5bb3f4105626**. Parent: **2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc**.

The W01 water-loss counterexample and W02 canonical L3→L4 substitution are repaired. The actual L4 nonconservation gate also works, including nonempty nitrogen and phosphorus prescription controls. Original 2E02 legacy-receipt migration, 2E03 percentage quantile parsing and 2E04 gust-unit ordering now pass their reproduced cases. **The delayed-idle-reply branch of 2E01 remains reproducible: two independent OS processes issue two simulated START effects on the same resource.** The query-exception branch and simultaneous-admission controls are repaired.

This is substantial implementation progress, with specific credit earned by execution. It is not full package acceptance. New adjacent checks also expose component-ledger semantics, qualification propagation and invalid-input boundaries. The appropriate next step is bounded corrective implementation and integration, while retaining the plan's full acceptance gates. The evidence does not support closing F03, F09, F10 or F16–F19 solely from this release, or describing all downstream scientific products as qualified.

## 1. Scope, source identity and evidence rules

Six parallel specialist reviews covered the twelve changed production files and their active callers/dependencies. The initial source staging contained 715 production/configuration paths, all verified byte-for-byte against the candidate's Git blobs. Additional dependency copies used by probes were separately verified to this same candidate. **A source count is not a coverage count.** Imported modules, statically traced code and executed functions are distinguished in each appendix.

The GitHub commit metadata reports 18 changed files: 12 production files, three plan/audit/register artifacts and three repository test files. The production changes were inspected; repository tests, audit assertions and generated diagnostic records were not accepted as correctness evidence. The authored offline probes use inert fixtures and private stores. No production service, broker, radio, field controller, physical actuator, drone or external training job was operated. No production or Git changes were made by this review.

The master repair plan, execution addendum and task register are normative inputs, rather than evidence that their implementations work. Their candidate blobs match the previously supplied originals:

| Normative document | Candidate Git blob |
|---|---|
| `plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md` | `08d378a65992de859369950599df198e64244f01` |
| `plan/AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md` | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| `plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md` | `8a564647af7e588802537817159117b349ff606b` |

The R3 scientific basis is the supplied monograph, PDF SHA-256 `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`, with the supplied scientific requirement extraction. It establishes the target contracts for conservation, root support, missingness, uncertainty, durable history, qualified scientific products and distinct command/execution/delivery states.

The register still has **52 open full-acceptance milestones and zero checked milestones**. This is a governance fact, not proof that all 52 packages are defective. The original 2,564–4,540 hour programme estimate is not a fresh remaining-work estimate. This corrective review does not invent a completion percentage or reclassify every package from a twelve-file change.

The reported 64 targeted and 490 full-suite tests are user-reported results. They were not independently rerun or treated as a substitute for these production counterexamples. All twelve changed production files independently pass syntax compilation without imports or bytecode writes.

## 2. Disposition of the six claimed repair areas

| Claim | Fresh production result | Disposition |
|---|---|---|
| W01 original impeding-profile water loss | Initial soil 180 mm, rain 100 mm, final soil 225 mm, gross infiltration 100 mm, net infiltration 45.10 mm, runoff 54.90 mm, drainage 0.10 mm, closure 0 | **Original fixed** |
| W01 full pipeline and surface-memory continuation | Full pipeline closure 0.02 mm within the 0.05 mm tolerance; repeated ponding warm/cold states and receipts agree, cumulative whole-system residual 0 | **Tested controls pass**, component receipt semantics remain qualified |
| W02 typed root-supported L3→L4 boundary | Candidate posterior storage 137.55→137.55 mm; FC/WP/saturation .295/.0966667/.44; supported depth 60 cm; actual loss engine receives VWC .2293 and 60 cm | **Original fixed** |
| W02 nonconserved-water gate | Previously allowed APPLY_N 163.1 and APPLY_P 43.8 become blocked; all nutrient confidences and downstream health/reliability capped at .20 | **Local L4 gate fixed**; restriction continuity into L8 remains open |
| 2E01 shared resource admission | Query failure after another execution: one START. Simultaneous two-process admission: one START. Delayed truthful idle reply returning after the first ACK: **two STARTs** | **Partially repaired; high-priority original branch remains** |
| 2E02 legacy publication-generation maps | Known A2 publication generation 5 survives independent B6, retry and restart; immutable allocation sequence stays 2 | **Original fixed**; older no-index first-read branch remains |
| 2E03 p/q percentage grammar | p1/q1/1%→.01; p.5/q.5/.5%→.005 across parser, record, durable read and evaluation | **Original fixed**; tiny pre-rounding range boundary remains |
| 2E04 gust-only unit normalization | Equivalent 2 m/s and 7.2 km/h single/duplicate rows confirm in either order; 5 m/s gust remains blocked | **Original fixed** |

The independent W02 result is 137.55 mm for the fully specified forcing in the appendix, rather than forcing the older solver output 137.57 mm to be a constant expectation. The pertinent boundary invariant is equality with the candidate's actual posterior, and it now holds. Similarly, full-pipeline closure 0.02 mm is within tolerance but must not be reported as exact zero.

## 3. Remaining corrective findings, ordered by consequence

### CEB01 — delayed idle evidence can replace a live durable resource owner

**Priority P1; actual OS-process reproduction; F16–F18, Stage 6.** The repaired exception path correctly leaves `query_ts=None`, and the original simultaneous-admission schedules now admit one owner. The remaining schedule is:

1. Worker A obtains a durable STARTING claim and pauses in its inert driver before applying START.
2. Worker B independently queries the same device/zone; the controller truthfully samples ONLINE at that instant. Its reply is held.
3. A applies START, returns ACK and durably records EXECUTING.
4. B's old idle reply is delivered. The dispatcher timestamps its **return**, then the shared claim accepts it as newer evidence and B sends START.

Both workers return EXECUTING. The inert controller records START A followed by START B, with B replacing A as its operation. There is no intervening STOP. A's durable reservation can be changed to COMPLETED by the competitor despite its driver still owning an executing command. This demonstrates two command effects in a controlled collaborator; it does not measure duplicate delivered water or prove a deployed controller lacks its own protection.

The timing seam is in [irrigation_runtime/dispatcher.py:L519-L524](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/irrigation_runtime/dispatcher.py#L519-L524): `query_ts` is taken after `await get_status()`, so it is not the observation's acquisition time. The shared resource-claim policy trusts this freshness when superseding an existing executing owner. Token generation and token checking on each worker's own claim do not undo a START already applied by A.

A second ordinary-submit OS-process schedule also fails: A pauses before the new token check; after the real 30-second STARTING lease expires, B obtains the resource and starts. A resumes after 31.1 seconds. Its own old reservation still has a matching STARTING/token, so it passes the fence and sends a second START. Both workers return EXECUTING. This is a resource-generation ownership gap, not just query freshness. A direct claim-API control correctly rejects a token replaced before the fence; replacement after the fence does not prevent the paused transport effect. That direct API control is separately qualified and is not presented as an ordinary duplicate-submit producer.

**Required correction:** make existing resource ownership authoritative through qualified stop/completion, rather than releasing another owner's execution from a later-arriving idle sample. Bind status evidence to request start/acquisition and operation/resource generation. Validate the admission token under the shared resource transaction immediately before transport, and define how an in-flight or expired START is fenced before transfer. For controllers without generation-aware reconciliation, uncertainty must retain ownership instead of granting a competing START.

**Acceptance:** run the exact four-step OS-process schedule above, delayed replies after ACK, query exception/UNKNOWN, simultaneous idle samples and any exercised lease-expiry schedule. Require one physical command effect in the collaborator, no false COMPLETED publication for an executing owner, no quota release on unresolved transport, and no stale watchdog cutoff of a confirmed foreign operation. A timestamp-only patch must not be accepted without these event-order probes. The appendix separates each observed schedule and any remaining driver-boundary limits.

### CEB02 — whole-system conservation passes, but the soil-only receipt conflates pond evaporation

**Priority P2; valid-input numerical reproduction; F03 with F07 support, Stages 2–3.** The new whole-system ledger is correct in the tested ponded fixture. It also closes through repeated ponding and production deserialization. The remaining issue is the meaning of the published ET components.

For the ponded mixed-flux fixture, soil storage changes 120→119.50 mm, net infiltration is 1.5 mm, actual capillary rise 6 mm and transpiration 8 mm. All 7 mm evaporation is taken from the surface pond, not the soil. The receipt nevertheless publishes `actual_soil_evaporation_mm=7` and `actual_eta_mm=15`. Using those quantities in the claimed soil-column equation gives a **7 mm residual** while the whole-system equation closes.

[layer3_water/soil/layered_water_balance.py:L204-L213](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/layer3_water/soil/layered_water_balance.py#L204-L213) evaporates pond storage first, then adds pond and soil evaporation together. [layer3_water/soil/layered_water_balance.py:L303-L321](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/layer3_water/soil/layered_water_balance.py#L303-L321) publishes only the combined evaporation. The correct distinguishable ledgers are:

\[
\Delta S_{soil}=I_{net}+C-T_a-E_{soil}-D
\]
\[
\Delta S_{surface}=P+I-I_{net}-Q-E_{pond}
\]
\[
\Delta(S_{soil}+S_{surface})=P+I+C-T_a-E_{soil}-E_{pond}-D-Q.
\]

**Required correction:** publish separate actual pond/surface evaporation and soil evaporation, while retaining total actual ET for whole-system consumers. State which storage compartment each receipt field belongs to. Update the active flux consumers and serialization together. Net infiltration must remain a surface↔soil interface flux; it should not be adjusted to conceal evaporation.

**Acceptance:** independently close both serialized compartment ledgers and their sum on ponded ET/capillary input, no-pond controls, pond carryover/restart and the repaired impeding profile. This is a component-accounting correction; the evidence does not justify revoking the original whole-system conservation repair.

### CEB03 — L4 nonconservation restrictions disappear at the L8 adapter/ranker seam

**Priority P1 for scientific prescription integration; bounded actual adapter/ranker composition; F10/F15 with F38 integration.** The local L4 hard gate is genuinely repaired. An explicitly nonconserved transition blocks nonempty N/P prescriptions in a full standalone L4 run. A separate exact-function composition establishes a restriction-loss boundary:

- The actual L4 gate changes N confidence .9→.2 and adds `nonconserved_water_transition` to a blocked prescription.
- The active orchestrator nutrient normalizer retains deficiency probability .8 and confidence .2, but discards the water receipt, blocked prescription and reason.
- The actual L8 ranker creates an **allowed FERTILIZE candidate, 120 kg_N/ha, HIGH categorical confidence**, with priority confidence .2 and no blocked reason.

Sources: [layer4_nutrients/runner.py:L655-L667](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/layer4_nutrients/runner.py#L655-L667), [orchestrator_v2/runner.py:L3432-L3459](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/orchestrator_v2/runner.py#L3432-L3459) and [layer8_prescriptive/action_ranker.py:L196-L237](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/layer8_prescriptive/action_ranker.py#L196-L237).

**Qualification:** this probe stops at ranking. The main L8 path has additional manifest, semantic, weather/soil, feasibility and publication constraints. The review does **not** establish a complete approval bypass, an executed fertilizer application or a naturally generated solver failure. It establishes that a scientifically meaningful exclusion is lost before those later gates and is not available for them to enforce by this route.

**Required correction:** carry variable-specific eligibility and its causes in the nutrient input contract, preserve the conservation receipt identity, and enforce inherited exclusions when creating and finalizing L8 candidates. Recomputing an action from a probability must not erase a required upstream restriction. Monitoring/measurement candidates may remain available under their own qualified policy.

**Acceptance:** use the full L4 nonconserved output, active adapter and main L8 path with independently satisfied unrelated gates. No fertilizer prescription depending on that failed boundary should regain permission. Record the same restriction identity through candidate, schedule and publication. Keep the conserved positive N/P controls allowed when their independent constraints are met.

### CEB04 — supported geometry is preserved, but qualification does not follow it consistently

**Priority P2; two different reproduced inputs, not a claim of arithmetic corruption; F04/F05/F10.** Partial overlap arithmetic is now correct: a 15 cm root uses 10 cm plus 5 cm, and a requested 120 cm root over a 60 cm profile integrates only the supported 60 cm. No unsupported deeper storage is invented in those calculations.

Two qualification seams remain:

1. An actual water-pipeline fixture supplies a 10 cm profile and `root_depth_proxy_m=None`. The runner substitutes 1.0 m, reports only 10 cm supported depth, yet returns overall water confidence .938, data health 1.0 and a boundary marked not degraded. Its internal MPC proposes 5.4 mm gross irrigation. This is an internal candidate from a thin-profile fixture, **not** observed publication or actuation.
2. A full L4 fixture changes only water-state health from 1.0→.2 while conservation remains true. The actual receipt marks itself degraded; SWB becomes DEGRADED with uncertainty multiplier 1.5. Nutrient confidences, previously allowed N/P rates, overall L4 health .75/status ok and reliability .5 remain unchanged from the healthy control. This is a deliberately declared low-health boundary, **not** a demonstrated upstream-generated incident.

[layer3_water/contracts/water_state.py:L400-L413](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/layer3_water/contracts/water_state.py#L400-L413) carries supported depth and a degradation flag, but lacks requested-depth/coverage/unknown-interval semantics. [layer4_nutrients/runner.py:L192-L226](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/layer4_nutrients/runner.py#L192-L226) labels SWB degradation; its later confidence/health gates act on nonconservation only.

**Required correction:** distinguish requested root depth, observed/supported depth, assumed root prior and unsupported intervals. Preserve their provenance and uncertainty through the receipt. Propagate each relevant water-quality limitation into dependent nutrient/loss uncertainty, output health and capability eligibility. A fixed global confidence penalty is not a substitute for a justified dependency policy, and every degraded input need not block every useful observation or monitoring action.

**Acceptance:** missing-root, shallow/deep-root, healthy and explicitly degraded controls preserve numeric support and expose the qualified domain. Any remaining allowed water-dependent prescription must explain its dependency and uncertainty. Healthy conserved controls must not be unnecessarily disabled. Check upstream generation separately from declared-input consumption.

### CEB05 — new surface-state fields admit invalid scientific states

**Priority P2; scientific API/domain validation, not a demonstrated external exploit; F03/F04.** An ordinary factory-built state can contain `surface_storage_mm=-5`. The full production water pipeline accepts it and publishes gross/net infiltration −5 mm with `mass_conserved=true` and closure .01 mm. Closure proves consistency of the admitted algebra, not validity of a negative water inventory. The direct transition also accepts requested evaporation −2 mm, creates 2 mm surface water even with zero pond capacity, and reports negative ET; negative/NaN capillary values can be silently ignored.

The new surface fields enter via [layer3_water/contracts/water_state.py:L25-L33](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/layer3_water/contracts/water_state.py#L25-L33) and are consumed at [layer3_water/soil/layered_water_balance.py:L126-L138](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/layer3_water/soil/layered_water_balance.py#L126-L138). The direct ET/capillary cases are contract admission tests; ordinary runner generation of negative ET was not demonstrated.

**Required correction:** validate finite real scalar types, nonnegative compartment stores/capacities and flux requests, consistent stored volume versus capacity, and supported hydraulic/profile shape at the factory and transition boundaries. Preserve explicit zero. Reject or explicitly quarantine unavailable/invalid values rather than accepting them as a conserved physical transition.

**Acceptance:** rejected inputs do not publish a candidate posterior/checkpoint or alter the predecessor state. Keep valid zero flux, dry, saturated/perched, ponding and restart controls. Test serialized round-trips so validation is not present only in one constructor.

### CEB06 — first scoped read of an older no-index legacy head has inconsistent generation

**Priority P2; explicit supported older-format input; F09.** The original indexed legacy migration is fixed. A narrower input removes the scoped index, top-level scope labels and receipt maps while retaining latest A2 and global publication generation 5. Before any migrating write, the scoped fallback returns A2 allocation sequence 2 with no publication generation. After B6 writes, A2 load/retry/restart correctly return 5 and immutable checkpoint bytes are unchanged.

[world_model/canonical_worldline.py:L291-L309](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/world_model/canonical_worldline.py#L291-L309) lacks the known-latest-head fallback used by the indexed and unscoped branches. This is a **read-before-migration receipt inconsistency**, not a repeated original after-write failure, global sequence regression or reproduced water-state change.

**Correction/acceptance:** share generation resolution among indexed, predecessor, unscoped and retry paths. The known latest checkpoint must return generation 5 on the first scoped read without requiring a write. Unknown historical publication order must remain unknown rather than be presented as established allocation order. Preserve the now-passing original migration and immutable-record controls.

### CEB07 — probability bounds are checked after rounding

**Priority P3; narrow adjacent input-validation gap; F24.** All original percentage grammar and caller-parity repairs pass. However, [world_model/forecast_archive.py:L187-L204](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/world_model/forecast_archive.py#L187-L204) rounds to six decimals before validating [0,1]. Thus `p-0.000001` and bare `-0.00000001` become −0.0, while `p100.000001` becomes 1.0, and real record/store/evaluation calls accept them.

This tiny boundary does not invalidate all scores or make every zero score false. Valid point-mass and legitimate endpoint controls retain their meaning. **Correction/acceptance:** validate the finite, unrounded normalized probability before identity/dedup quantization, retaining valid endpoints, alias parity and conflict checks. Recheck all three invalid examples, p0/p100 and valid zero forecasts. This can proceed independently of the resource and water repairs.

## 4. Durable qualification and broader work-in-progress limits

Static inspection of the active hydraulic checkpoint payload/history shows persisted soil, memory, evidence and forcing identities, but not the complete transition/analysis receipt or its conservation/eligibility qualification. The soil object alone cannot reconstruct every prior external flux, control-volume budget or admission decision. This review did not execute a nonconserved checkpoint crash/restart/promotion path; it is an **open integration criterion**, not a separately reproduced state-corruption finding. F08/F09 acceptance should preserve failed-transition ledgers while preventing an unqualified posterior from silently becoming a qualified operational predecessor.

Likewise, legacy compatibility branches in the L4 standalone caller still have scalar priors when a typed receipt is unavailable; the valid canonical path no longer uses them. Zero/missing support and incomplete legacy object shapes require explicit prior/scenario or unavailable semantics. Their existence must not be confused with the repaired canonical path falling back in the executed cases.

This twelve-file corrective batch does not recertify the broader findings from the previous full work-in-progress review. Production components outside the delta still need their own plan acceptance: measured delivery validation and calibration, nutrient trajectory accounting, post-action causal metrics, crop-scenario schema integration, immutable learning windows, temporal role qualification, independent forecast targets, spatial evidence/support, MESIA scientific evaluation, model validation/registry, platform failure semantics and the world-model/Omega capability extensions. These are scope reminders and carry-forward workstreams, not new failures claimed from this review's probes. The original plan and R3 remain the coverage register.

To make this distinction concrete, five current leaf-file blobs were compared with the parent and inspected statically again. All five are unchanged (`carry-forward-source-check.json`). These entries preserve prior review scope; **their prior independent probes were not rerun in this corrective batch**, and they are not added to the seven fresh finding groups above.

| Carry-forward work | Current source still present | Required follow-through |
|---|---|---|
| F17/F18 qualified STOP feedback | Modbus `_stop_zone` bases success on coil-write acceptance; LoRaWAN normal commands return success on downlink queueing, and emergency stop uses an unconfirmed downlink | Verify controller-level applied/stopped confirmation and retain operation ownership when only transport/queue acceptance is known; a water-math repair does not establish this driver contract |
| F02/F39 evidence durability | `sensor_runtime/storage.py:5–20` retains process dictionaries/lists and returns the stored raw object directly | Durable immutable raw evidence, versioned normalization and nonce/evidence commit or recovery semantics |
| F12 outcome attribution | `layer6_exec/outcomes/metrics.py:69–73,156–217` still distinguishes causal status principally from exposure verification and calculates pre/post sample-based summaries | Support-matched time-weighted outcomes, causal qualification and independent counterfactual assessment |
| F14 crop-scenario schema | `layer8_prescriptive/scenario_contract.py:54–68` still reads `crop_type/expected_yield` and can substitute `expected_profit` into a yield-relative field | Bind actual crop/yield-distribution schema, units and uncertainty at the active adapter |

This table is a source-continuity check, not evidence of observed field failure or a newly executed full caller path. It prevents the W01/W02 and 2E fixes from being mistaken for completion of unrelated packages.

## 5. Concrete implementation sequence and acceptance gates

Several workstreams can proceed together. A scientific correction does not require waiting for an unrelated controller repair, and qualified world-model/Omega experiments do not require treating every unfinished application feature as a universal prerequisite.

| Workstream | Concrete implementation | Evidence required to close this slice | Plan relationship |
|---|---|---|---|
| A — resource ownership | Correct CEB01 evidence timing and shared admission/transfer semantics; preserve uncertainty through token/lease/transport boundaries | Actual OS processes, controlled delayed idle reply, one START, durable/driver owner agreement, retained quota and stop obligations | F16–F18, with F19 safety regression controls; Stage 6 |
| B — water compartments | Separate pond/soil evaporation and total ET; validate new surface inventories and transition scalar inputs | Independent serialized soil, surface and whole ledgers; valid original/dry/permeable/pond/restart controls; rejected invalid input leaves predecessor unchanged | F03/F04/F07; Stages 2–3 |
| C — scientific qualification | Carry requested/supported root domain, water uncertainty and inherited restrictions through L4→L8; preserve failed-transition qualification in durable history | Full L4→adapter→main L8 composed probe, nonempty positive/negative prescriptions; qualification survives restart and cannot promote a rejected transition | F05/F08/F09/F10/F15/F38 integration; accept only the relevant bounded slices |
| D — provenance and scoring precision | Shared legacy generation resolver and pre-rounding quantile bounds | First legacy read=5 before a write; original indexed migration/retry/restart remain correct; invalid probability aliases reject before persistence | F09 and F24, independently executable |
| E — broader planned implementation | Resume the established package-specific order using qualified physical/evidence contracts; keep independent research objectives explicitly scoped | Active-caller, numerical, scope, replay, uncertainty and independent empirical evidence appropriate to each package | Existing 17-stage addendum; no new universal serial barrier |

Implementation details for A–D:

1. Freeze the exact candidate/reproduction set before editing. Give each repair a contract owner and one clearly defined control volume/resource/eligibility invariant. Keep original passing controls in the acceptance matrix so a local fix cannot erase previous credit.
2. Version the changed receipt/admission semantics. Include migrations for persisted surface fields and qualification metadata, and a read policy for legacy heads with unknown receipt history. Unknown support/provenance should remain visible.
3. Make shared operation ownership and scientific state publication transactional at their own boundaries. A generated token, local confidence value or nested degraded flag is insufficient if its active consumer discards it.
4. Use independently authored counterexamples plus the repository's relevant regression suites after implementation. Do not use test totals as evidence for an unexercised integration boundary. Hardware commissioning remains separate from software simulation.
5. Review exact production deltas and rerun the decisive fixtures before closing any bounded slice. Full `-FA` requires that package's complete criteria and objective-appropriate integrated evidence. Do not close all 52 merely because this corrective batch becomes green.

For world-model and Omega work, the immediate scientific basis is a qualified worldline: conserved prognostic transitions with separate analysis increments, known or explicitly partial support, actual action/delivery roles, durable cutoff/provenance and independent evaluation targets. Dataset assembly, shadow objective design, conservative residual experiments and falsifiable investigation protocols may proceed on eligible subsets. Failed transitions and unsupported assumptions must be explicitly excluded or represented as such for each objective; they must not become high-confidence training targets through a cache, adapter or successful test status. This preserves the monograph's agronomic, data-science and experimental target without claiming that a bounded software repair establishes biological calibration or economics.

## 6. Reproduction and audit limits

The evidence bundle contains the six specialist appendices, authored offline probes, observed JSON, exact-source manifests, normative input receipts and a read-only Git-object materializer. It contains no repository test files, historical repository audits, production source copies, generated controller/quota/checkpoint stores or field data. Use the bundle README and `prepare_and_run.py` with a local checkout containing the pinned commit; the helper reads Git objects and builds a separate workspace without checkout, fetch, commit or push.

All **nine** official probe/receipt commands completed successfully in a separate reconstructed workspace, with **717 source-layout copies / 698 unique Git blobs verified**, unchanged production bytes after execution, and no recorded harness errors. This includes an independent rerun of both OS-process admission counterexamples and the real lease wait. Details are in `portable-replay-validation.json` and the replay logs. A successful probe command means its declared observations, including counterexamples, reproduced; it is **not** a count of production tests passed. The materializer is syntax-checked; its Git-object route was not executed against a separate full Git checkout here. Source bytes in the reconstructed local layout are checked independently.

Full repository test certification, complete orchestrator promotion, nonconserved crash/restart acceptance, deployed-controller behavior, soil/crop calibration, MESIA biological specificity, prospective field skill, economic realized benefit and full world-model/Omega acceptance remain outside this corrective evidence. The next action is to implement the bounded items above and then verify their actual integration contracts.


---

# Specialist appendix: Water conservation and compartments

# W01 conservation verification — candidate ceb5dd4

Candidate: `ceb5dd47250a9aca5482dcb2904a5bb3f4105626`, parent `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`. Review date: 2026-10-18. The original valid-profile conservation counterexample is repaired in the executed candidate. Exactly three adjacent boundary groups were checked: repeated ponding/restart, pond evaporation with ET/capillary receipts, and numeric/domain validation. Two adjacent limitations remain: the receipt calls pond evaporation soil evaporation, and invalid scalar/surface-state inputs are not consistently rejected.

This report credits the repaired original without claiming full F03/F04/F07 or R3 acceptance. It does not infer physical water loss from a change in control-volume semantics. All numbers below are fresh outputs from this candidate's production functions, not repository tests, audit artifacts, or copied prior results.

## Evidence and scope

`probes.py` imports production `WaterStateFactory`, `LayeredWaterBalanceEngine`, `WaterIntelligenceEngine`, the actual data contracts, and the production soil checkpoint deserializer. It uses inert local data only. No hardware, production service, network fetch, repository test, source edit, or Git mutation was performed. Both worldline module aliases are redirected to a private lane path before the deserializer is used; no checkpoint publication is needed by these fixtures.

`source-manifest.json` verifies all 89 imported production module files against the candidate Git tree. This verifies loaded bytes; it is not branch coverage or proof that every function in those modules was exercised. All imports resolved under candidate source; no prior production dependency copy was necessary. The called paths are the soil factory, root-state factory, layered transition, full water pipeline, and checkpoint soil deserializer. `results.json` contains the complete inputs, serialized states, receipts and independently calculated residuals. There were no harness errors.

Reproduce from the workspace root:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-ceb5dd4-review/trajectory/probes.py
```

Normative basis: master-plan F03 (integrated fluxes, serialized closure and separate analysis), F04 (valid hydraulic parameters), F07 (durable evaporation state); execution stages 2 and 3; R3 `AB-AGR-003` (closed stocks/fluxes/geometry/roots), `AB-AGR-004` (physical fluxes, analysis and clamps separated), `AB-AGR-005` (ET components identified), `AB-AGR-006` (restart memory), and `AB-DAT-005/007` (missingness/zero, units/support). The exact local normative file receipts are in `normative-manifest.json`.

For the line references below, `LB` means `services/agribrain/layer3_water/soil/layered_water_balance.py`, `WaterState` means `services/agribrain/layer3_water/contracts/water_state.py`, `Factory` means `services/agribrain/layer3_water/contracts/state_factory.py`, `Runner` means `services/agribrain/layer3_water/runner.py`, and `Decision` means `services/agribrain/layer3_decision/runner.py`. Every reference is pinned to the candidate SHA above; exact blobs are in the source manifest.

## Original W01 counterexample: fixed

Use layer bottoms `[10,30,60]` cm, initial theta `[.30,.30,.30]`, FC .30, WP .15, saturation .45, residual .04, conductivity `[100,.01,.01]` cm/day, alpha .03 and n1.5. Apply 100 mm rainfall with zero irrigation and, for the exact direct transition, zero ET/capillary input. All geometry/hydraulic parameters are valid.

| Executed case | Soil storage, mm | Gross infiltration | Net infiltration | Runoff | Drainage | Closure error |
|---|---:|---:|---:|---:|---:|---:|
| Dry impedance control | 180→180 | 0 | 0 | 0 | 0 | 0 |
| Rain, permeable control `[100,100,100]` | 180→180 | 100 | 100 | 0 | 100 | 0 |
| Original impedance counterexample | **180→225** | **100** | **45.10** | **54.90** | **.10** | **0** |
| Original profile through full water pipeline | **180→214.56** | **100** | **45.10** | **54.90** | **.10** | **.02** |

The full pipeline integrates ET10.46 mm (T1.25 + evaporation9.21). Its .02 mm serialization residual is within the declared .05 mm receipt tolerance; it must not be described as exact zero. Every row reports `mass_conserved=true`. The old 69.90/69.38 mm losses are absent from this precise reproduction.

The repair routes saturation excess upward into available upper-layer storage, then sends top overflow to depression storage or return runoff (`LB:175–202`). It no longer removes the original excess solely by theta clipping. Gross infiltration100 minus return flow54.90 gives net infiltration45.10; the direct soil ledger closes: ΔS45 = 45.10 − .10. Whole-system closure now includes surface storage and external P/I/C versus ET/drainage/runoff (`LB:291–321`). The full runner continues to publish integrated fluxes from the receipt and keeps analysis increments separate (`Runner:248–282,306–334`).

Acceptance credited: the original valid impedance counterexample, positive dry/permeable controls, gross/net return-flow accounting, and full-pipeline realization. This is numerical verification of these fixtures, not empirical validation of the chosen bucket/perching process approximation.

## A1 — Repeated ponding and restart: passed

Use the same impedance profile, initial ponding0 mm and depression capacity12 mm. First interval: rain100, evaporation2, zero transpiration/capillary input. Second interval: no new rain/irrigation, evaporation3. Compare warm continuation with JSON serialization plus the production `_deserialize_soil_water` followed by the same second step (`Decision:857–875`).

| Quantity | First interval | Second interval |
|---|---:|---:|
| Soil storage, mm | 180→225 | 225→225 |
| Surface storage, mm | 0→10 | 10→6.90 |
| Gross infiltration, mm | 100 | 10 |
| Net infiltration, mm | 45.10 | .10 |
| Return-flow runoff, mm | 42.90 | 0 |
| Drainage, mm | .10 | .10 |
| Evaporation, mm | 2 | 3 |
| Whole-system closure error, mm | 0 | 0 |

Warm/cold serialized states and receipts are exactly equal. The two-interval whole-system residual calculated independently from the returned states is0. The second interval's gross10 is recycled pond water, not new rainfall or additional external input. Its gross-minus-net return9.90 returns to ponding and does not become runoff. This distinction passes in the tested fixture.

The added surface fields survive the actual hydration path. This check does not exercise checkpoint CAS, event corrections, or hydraulic cache invalidation; it establishes round-trip continuation of this state shape only. The soil-only ledger interpretation of the evaporation field is addressed next.

## W01-A2 — Pond evaporation is published as soil evaporation

**Status: executed receipt/semantic limitation, medium priority; F03/F07, AB-AGR-004/005 and AB-DAT-007. Whole-system conservation passes.**

Use the same geometry with theta .20, conductivity `[.1,2,2]` cm/day, initial ponding5 mm, capacity12 mm, rain4, irrigation3, requested transpiration8, evaporation7 and capillary rise6 mm. The direct production transition returns:

| Coordinate | Returned value |
|---|---:|
| Soil storage | 120→119.50 mm |
| Surface storage | 5→3.50 mm |
| Net infiltration | 1.50 mm |
| Transpiration | 8 mm |
| Capillary rise | 6 mm |
| Drainage/runoff | 0/0 mm |
| `actual_soil_evaporation_mm` | **7 mm** |
| `actual_eta_mm` | **15 mm** |
| Whole-system residual | **0 mm** |

All7 mm evaporation comes from the surface reservoir; actual extraction of water by evaporation from the soil column is0. This follows directly from the executed surface balance: 5 + 4 + 3 − 1.5 − 3.5 = 7. The correct soil ledger is ΔS−.5 = netI1.5 + C6 − T8 − E_soil0. Using the published field as the documented soil evaporation instead gives −7.5 mm, a7 mm discrepancy.

The code explicitly takes `evap_from_surface` first and then calculates `actual_top_evap` (`LB:204–213`), but publishes their sum as `actual_soil_evaporation_mm` (`LB:303–311`). The contract still documents that field as “actual topsoil evaporation extracted” (`WaterState:299–303`). `storage_change_mm` remains the **soil** change while `water_closure_error_mm` now covers **soil + surface**. The full runner forwards this mixed evaporation value unchanged into its soil evaporation coordinate (`Runner:312–333`).

The no-ponding control returns E_soil7, bounded T5.03 and capillary6: soil120→113.97, both ledgers close, and surface evaporation is0. That isolates the semantic mismatch to the added surface reservoir rather than capillary accounting or ordinary extraction.

Scientific implication: a downstream consumer that follows the old soil-only field meaning cannot reconcile the soil column or distinguish soil drying from open-water evaporation. The whole-system receipt is mathematically conserved; this is **not** a second water-loss counterexample, and no downstream misprescription was demonstrated.

Remediation: retain distinct `soil_evaporation_mm` and `surface_water_evaporation_mm`; define total ET as T + E_soil + E_surface. State the control volume explicitly and either publish both soil and whole-system closure errors, or version the receipt semantics with unambiguous names. Keep net infiltration as gross entry minus total return flow and record return-flow-to-storage separately or make it directly reconstructible.

Acceptance: from serialized outputs, independently reconcile both ΔS_soil = I_net+C−T−E_soil−D and Δ(S_soil+S_surface) = P+I+C−T−E_soil−E_surface−D−Q for this fixture and the no-ponding control. The repaired original must remain closed.

## W01-A3 — Invalid flux and new surface-state admission

**Status: executed validation limitation, medium priority; F01/F04/F07, AB-DAT-005/007 and AB-AGR-003. These are invalid-input cases, not valid-forcing conservation failures.**

The direct step validates depth geometry (`LB:84–101`) but does not qualify ET/capillary scalars before using them. On a valid .20 profile with no surface reservoir and depression capacity0:

| Input boundary | Executed result |
|---|---|
| Valid zero fluxes | State unchanged; no pond; ETA0; closure0 |
| Evaporation−2 mm | **Creates surface storage2 mm despite capacity0**; soil unchanged; ETA−2; closure0; `mass_conserved=true` |
| Capillary−2 mm | Accepted and silently treated as capillary0 |
| Capillary NaN | Accepted and silently treated as capillary0 |

Negative evaporation makes `min(-2,0)=-2`, then subtracting that quantity creates a positive pond (`LB:206–207`). Negative/NaN capillary values bypass `if capillary_rise_mm > 0` (`LB:227–232`). The resulting algebraic closure can pass despite physically invalid components.

Reachability is qualified: the ordinary full pipeline derives ET internally and currently validates weather precipitation and applied irrigation (`Runner:107–130`). This review did not find an ordinary path injecting a caller-supplied negative ET into that pipeline. The direct-step failures demonstrate a weak public scientific boundary, not an executed controller-risk path.

The new surface-state path is reachable through the full water pipeline. An `InfiltrationState(surface_storage_mm=-5,max_surface_storage_mm=12)` is accepted by `WaterStateFactory.create_soil_water_state` and then by `WaterIntelligenceEngine.execute_pipeline`. The latter returns gross infiltration−5, net infiltration−5, soil120→105.43, ETA9.58, closure.01 and `mass_conserved=true`. The initial negative reservoir makes the algebra balance, but it is not a physically admissible state. The dataclass has no surface domain checks (`WaterState:19–31`); the factory passes it through (`Factory:160–175`); the step converts it with `float(... or0)` and adds it to available surface water (`LB:126–141`). The existing deserializer reconstructs the same fields without domain validation (`Decision:861–875`). No claim is made that a normal valid candidate-generated pond becomes negative spontaneously.

Remediation: validate all hydrological flux inputs as finite, nonboolean real scalars with explicit nonnegative domains before arithmetic; reject missing/nonfinite values rather than silently interpreting them as0. Validate initial surface0≤storage≤capacity, finite nonnegative capacity, and consistency of replayed surface state at construction/hydration and execution. If signed exchange is intended for capillary/drainage, use a separate explicitly signed contract rather than silently ignoring the sign.

Acceptance: the listed invalid inputs return a typed rejection before state mutation/publication; valid zeros and the original/A1/A2 positive fixtures remain admitted. A successful numeric closure flag must not override invalid component admission.

## Static integration limits and final disposition

The state digest in `Decision:2000–2023` still excludes the newly consumed infiltration/surface-storage/capacity fields. This was read in current candidate source; no extra cache probe was added beyond the three adjacent groups. Treat it as a follow-up F08 integration acceptance gate, not a demonstrated stale-output reproduction in this lane. Hydration preservation did pass; content identity and CAS are different acceptance boundaries.

Surface state is rounded to .01 mm while the receipt carries up to four decimals (`LB:263–273,291–321`), and the factory still rounds theta to four decimals (`Factory:160–166`). This bounded pass did not run subthreshold cumulative/precision cases or expand into a parameter sweep. The original full-pipeline .02 mm residual is within the declared tolerance and is reported accurately.

**Disposition:** credit W01's original saturation-loss repair and the tested gross/net, return-flow, repeated-ponding and restart behavior. Keep the explicit soil-versus-surface ET/control-volume contract and invalid-input surface/flux qualification open. No additional valid-input whole-system conservation counterexample was found in these three adjacent groups. No field calibration, hardware behavior, production service, complete coupled trajectory, or full master-plan acceptance was certified.


---

# Specialist appendix: Typed L3 to L4 boundary and nutrient qualification

# W02 and root-support verification at candidate ceb5dd4

Candidate: `ceb5dd47250a9aca5482dcb2904a5bb3f4105626`, parent `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`. Reviewed 18 October 2026.

**The original W02 boundary corruption is repaired in the executed canonical path.** Root-supported storage, depth-weighted retention and the supported depth reach the full L4 caller without the previous generic substitution or fixed 300 mm VWC denominator. The nonconserved-water gate also propagates into nutrient state, actual nonempty prescriptions and quality. One remaining adjacent boundary failure is reproduced: a conserved but explicitly degraded water boundary changes the SWB label but does not change downstream nutrient confidence, allowed prescriptions or L4 health/quality.

## Scope and provenance

Six offline production compositions ran: the original full-L4 fixture, paired positive/nonconserved prescription-gate controls, and exactly three adjacent scenarios (15 cm root, requested 120 cm root over a 60 cm profile, conserved low-health boundary). `probes.py` is runnable and `results.json` contains exact inputs, full receipts/output and assertions. All six completed.

Every production import was checked against the candidate Git tree **before execution**, and rechecked after execution. `executed-source-manifest.json` records **113 exact production source files**, Git blobs and SHA256s. All production imports came from this candidate's source; no older dependencies were executed. `review-source-manifest.json` adds focus line references and normative document hashes. Source identity is a prerequisite, not proof of scientific correctness.

Execution uses the actual `WaterIntelligenceEngine.execute_pipeline`, actual water/root factories, actual `to_layer4_boundary_receipt`, and full `run_layer4_standalone`. A loss-engine argument observer delegates unchanged to the actual `EnvironmentalLossEngine.compute_all_losses`. The L3 decision collaborator only carries the actual canonical water object, as in the original fixture. No target-body rewriting, repository tests/audits, service/network/controller/hardware calls or production/Git writes were used.

The nonconserved and low-health controls deliberately replace fields in actual frozen production dataclasses after a valid pipeline run. They test L4 admission/propagation for those declared states; they do not demonstrate that the water solver naturally generated those failures. The original and two root-overlap scenarios use actual pipeline-produced states unchanged.

The standalone API permits omitted semantic lineage for research calls (`layer4_nutrients/runner.py:143–146`). This fixture uses that mode, as the original did. The public L4 wrapper passes `l3_output` and semantic lineage to the same full implementation (`runner.py:1186–1230`, static trace only). These receipts establish this L4 implementation's behavior; they do not certify a full orchestrator run, upstream species/stage authority, deployment or actuation.

## Repaired W02 and root-overlap controls

Profile layer bottoms are `[10,30,60] cm`; prior theta `[.18,.23,.28]`; FC `[.25,.28,.32]`; WP `[.07,.09,.11]`; saturation `[.40,.43,.46]`; conductivity `[2,2,2] cm/day`. The 2 January 2026 forcing uses Tmax38/Tmin22 °C, no rain, 2 m/s wind, RH25/65%, net radiation18 MJ/m², LAI3/FVC.8. Expected quantities below are independently integrated from the **candidate's posterior theta profile**, rather than compared with a second nutrient model.

| Actual pipeline scenario | Active layer overlap | Independent storage → L4 storage | Supported depth | FC / WP / saturation passed to L4 | VWC / depth at actual loss engine |
|---|---|---:|---:|---|---|
| Original 60 cm root | 100/200/300 mm | 137.55 → **137.55 mm** | **60 cm** | **.295 / .0966667 / .44** | **.2293 / 60 cm** |
| Adjacent 1: 15 cm root | 100/50/0 mm | 20.60 → **20.60 mm** | **15 cm** | **.26 / .0766667 / .41** | **.1373 / 15 cm** |
| Adjacent 2: requested 120 cm root, profile ends 60 cm | 100/200/300 mm | 137.55 → **137.55 mm** | **60 cm** | **.295 / .0966667 / .44** | **.2293 / 60 cm** |

The original reported `137.57→83.30 mm` W02 corruption is absent. Candidate hydrology gives 137.55 mm in this fresh run, only **0.02 mm** from the reported prior integration, so the scientifically relevant comparison is **137.55→137.55**, not forcing the old solver's 137.57 as an expected candidate value. This is an independently recomputed **post-integration** reference, not a fixed storage target constant. All storage/retention/depth comparisons pass, including partial overlap in the second layer. All scenarios produce the actual `Layer3ToLayer4BoundaryReceipt`.

Production sources (paths below are relative to `services/agribrain/`):

- `contracts/state_factory.py` under `layer3_water`: lines 254–313 integrate FC/WP/saturation/theta over actual root overlap and divide by supported thickness; 316–331 publish those aggregates. `root_zone/availability.py:25–35` forwards the actual saturation profile.
- `layer3_water/runner.py:299–305` recomputes the final root zone from posterior soil. `layer3_water/contracts/water_state.py:392–443` publishes root aggregates, drainage and conservation in the typed receipt. The contract fields are explicit at `contracts/assimilation_state.py:84–93`.
- `layer4_nutrients/runner.py:192–210` invokes and consumes the actual receipt; 250–271 transfers it into SWB output. Lines 517–533 derive supported depth in mm, compute storage/depth VWC, and pass supported **cm** to the actual loss model. `environmental_losses/engine.py:115–140` uses the passed depth/retention/VWC in the appropriate loss calculations.

This earns concrete credit for F10 steps 1–2 and the supported-depth portion of step 4. The dry fixture's drainage is zero. Nonzero daily drainage accumulation/replay and counting a receipt exactly once across dates were not exercised; this pass does not close F10 step 3 or whole-package acceptance.

## Nonconserved gate: repaired, with non-vacuous prescription controls

The positive control adds actual L4 evidence: soil N1/P1/K10 ppm, NDVI.2, NDRE.05 and vegetative stage. It returns three prescriptions: **APPLY_N163.1 kg/ha allowed**, **APPLY_P43.8 kg/ha allowed**, and APPLY_K250 kg/ha already blocked by its independent rate safety limit. Nutrient confidences N/P/K/S are **1.0/.9/.88/.5**; L4 health **.75, status ok**, reliability **.5**.

The paired negative control changes only the actual canonical transition receipt's declared conservation fields to `mass_conserved=False`, `water_closure_error_mm=1.0`, together with the water state's matching closure field. The full L4 run then yields:

- SWB `DEGRADED_NONCONSERVED_WATER`, uncertainty multiplier **2.0**;
- all four nutrient confidences **.2**, each with a mass-balance uncertainty note;
- all three prescriptions blocked, including previously allowed N/P, each carrying `nonconserved_water_transition`;
- L4 overall health/confidence ceiling/reliability **.2**, status **degraded**;
- quality missing driver `PHYSICALLY_CONSERVED_WATER_BOUNDARY` and a hydrology mass-balance penalty.

This directly verifies the state/prescription/quality gate, rather than relying on an empty prescription list. Sources: `layer4_nutrients/runner.py:655–667` applies the gate before quality synthesis at 669–675; 764–774 caps health and records the quality reason. No solver conservation failure is alleged by this deliberately declared negative control.

## Remaining finding: degraded conserved boundary loses downstream uncertainty

**Evidence class: reproduced full-L4 boundary propagation defect under an explicitly constructed declared input; review priority P2.** It is not a naturally generated solver failure or demonstrated deployed recommendation.

Adjacent scenario 3 starts from the exact positive prescription control and changes only `WaterState.data_health_score` from 1.0 to **.2**. Conservation stays true and closure stays 0. The actual receipt marks `is_degraded=True` because `water_state.py:411–413` explicitly tests low health. L4 receives that signal and produces SWB **status DEGRADED, is_degraded true, uncertainty_multiplier1.5**. Yet the downstream output is identical to the healthy positive control:

| Output quantity | Healthy water boundary | Conserved boundary with health .2 |
|---|---:|---:|
| Nutrient confidence N / P / K / S | 1 / .9 / .88 / .5 | **1 / .9 / .88 / .5** |
| N prescription | 163.1, allowed | **163.1, allowed** |
| P prescription | 43.8, allowed | **43.8, allowed** |
| L4 data health overall / ceiling | .75 / .5 | **.75 / .5** |
| L4 data health status | ok | **ok** |
| Decision reliability | .5 | **.5** |
| Hydrology quality penalty / missing reason | none | **none** |

The receipt-level water confidence itself also remains .938, because it comes from a separate confidence structure. These observations do not establish that every degraded boundary must block every nutrient action: a valid propagation policy can preserve some useful capabilities. They do establish that the new generic degradation signal/uncertainty multiplier has no downstream effect on the checked confidence/quality/prescription outputs, while L4 reports healthy status.

The reason is local and traceable. `layer4_nutrients/runner.py:210,225–226,266–268` labels a degraded conserved SWB but the remaining downstream propagation gates at **655–667 and764–774 test only `not mass_conserved`**. A production source search under L4 finds no consumer of SWB `uncertainty_multiplier` or conserved `is_degraded` after those fields are constructed. Thus marking the SWB alone does not carry its uncertainty into dependent nutrient/transport estimates.

**Implication:** callers relying on nutrient confidence, overall health or prescription eligibility rather than inspecting nested SWB can miss an explicitly degraded water basis. In this fixture there is no numerical loss change because physical water values are intentionally held constant; the demonstrated failure is epistemic/quality continuity, not a proven wrong nutrient mass or economic loss.

**Concrete fix:** retain conservation as a hard gate, and add an explicit boundary-quality/support policy for the water-dependent nutrient and loss calculations. Carry the cause, relevant support/coverage and uncertainty into state confidence or uncertainty, output quality/missingness and permitted capabilities; derive overall health from those dependencies. Do not merely multiply every nutrient by an arbitrary global factor or treat all degradation as a conservation failure. Where an action remains allowed, its uncertainty and explanation must reflect the qualified dependency.

**Acceptance:** the same low-health fixture must preserve root/storage units while recording degraded downstream health and the hydrology reason, with an explicit justified effect on relevant state uncertainty/confidence and any allowed water-dependent prescription. The healthy positive control must retain legitimate capabilities; the nonconserved control must continue blocking its previously allowed N/P prescriptions. Verify upstream generation/transport of the health/support signal separately before claiming full app closure.

## Bounded support qualifications

The 120 cm root scenario correctly stops all aggregates at the available **60 cm** and preserves that supported depth in the typed receipt; no unsupported 60–120 cm water was invented. Its SWB remains OK and uncertainty multiplier1.0. Whether this is a supported-domain calculation or a truncated full-root estimate must be explicit in the receiving contract: the receipt carries supported depth but does not carry requested depth, coverage fraction or unsupported interval. This is a **remaining policy/contract qualification**, not a reproduced arithmetic defect in the supported interval.

Missing/zero depth was not a fourth adjacent scenario. Static source still falls back from nonpositive supported depth to **60 cm** at `layer4_nutrients/runner.py:517–520`; a zero/missing storage value selects **VWC.25** at line521. Receipt fields also have physical scalar defaults (`assimilation_state.py:85–93`). These compatibility paths require explicit missing-support rejection or prior/scenario qualification; they are not evidence that an actual candidate factory-generated profile reaches L4 with missing support. The factory validates profile shapes and root depth; the executed valid canonical cases preserve support correctly.

## Normative mapping and closure scope

F10 is stage4 and depends on F03/F04/F05. The master plan `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:389–413` requires a typed receipt, root-supported storage/retention, separated daily drainage and downstream missing-support/uncertainty propagation. The task list locates these at `ST04-F10-01..04` and FA, lines546–571. The sequencing addendum line9 permits slice credit while retaining full integration criteria.

R3 supplied scientific sections: **AB-AGR-008:874–876** (compatible L2/L3/L4 cover, roots, water and uptake), **AB-AGR-010:882–884** (distinct nutrient/formulation/efficiency/application credit), **AB-DAT-007:683–685** (traceable units/support), with **AB-DAT-005:675–677** and **AB-ARC-006:742–744** governing missingness and bounded degradation.

W02's original canonical scalar/substitution failure and the tested nonconserved propagation are repaired. Supported-root arithmetic passes the original and both geometry-adjacent controls. Conserved degraded-boundary propagation remains open in the executed scope. Nonzero multi-day drainage/replay, arbitrary missing-support admission, full F10/F11 scientific acceptance, full orchestrator authority and any physical action are outside these receipts.


---

# Specialist appendix: Concurrent resource ownership and driver admission

# Candidate resource-admission verification — ceb5dd4

**Candidate `ceb5dd47250a9aca5482dcb2904a5bb3f4105626` repairs the query-exception admission case and adds a working token mismatch check, but the original delayed idle-reply 2E01 counterexample remains. A separate live-owner TTL revival schedule also produces two START effects.** These are effects in an inert controller collaborator, not measured duplicate water delivery.

Five actually imported production modules match the exact candidate Git blobs (`source-import-manifest.json`). The reused author-controlled schedules were freshly executed against this source. Repository tests, audits and earlier result artifacts were not used as correctness evidence. Every competing event uses the same `device` / `zone` / `plot` physical resource.

## Original 2E01 delayed reply — not repaired

Two actual OS processes reproduce the original schedule:

1. A holds durable STARTING ownership and pauses in the inert transport before applying START.
2. B truthfully samples ONLINE while the collaborator is still idle. Its reply is held.
3. A applies START, returns its ACK and durably becomes EXECUTING.
4. B's old idle reply returns. Candidate code assigns `query_ts` at this later return, claims the resource and sends another START.

Fresh monitored times from `original-results.json`:

| Event | Epoch seconds |
|---|---:|
| B actually samples idle | 1792334655.793924 |
| A START is applied | 1792334655.794508 |
| A durable EXECUTING timestamp | 1792334655.798323 |
| B delayed query returns | 1792334655.802212 |
| B production `query_ts` is assigned | 1792334655.802344 |
| B START is applied, previous operation A | 1792334655.805253 |

Both submit calls return EXECUTING with their own active command. The collaborator contains two START effects and no STOP. A's ledger row is changed to COMPLETED by B's claim; that terminal row is an admission-side rewrite, not a physical completion receipt. A's active command was still present at its submission return. The witness does not assert an old process continued running after exit or measure two simultaneous water flows.

**Mechanism:** [`dispatcher.py:519–524`](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/irrigation_runtime/dispatcher.py#L519-L524) timestamps the idle observation after `await get_status()`. [`safety.py:1629–1638`](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/irrigation_runtime/safety.py#L1629-L1638) compares that receipt time with A's EXECUTING transition and accepts the stale sample as newer. The execution timestamp itself is now recorded (`965–986`), but the compared query time is not the actual observation time. New own-record tokens cannot undo A's already-applied START.

**Required correction:** bind idle evidence conservatively to request/sample time or a controller state generation; revalidate against the resource transition before granting an effect permit. Timestamping response delivery is insufficient.

## New adjacent schedule — live owner revives after real TTL

Two OS workers use ordinary `submit_event` calls. A pauses **before** the new production pre-send fence. B waits a real 31.1 seconds; no production clock is patched and no ledger JSON is directly edited. B truthfully sees idle, passes the expired STARTING claim and reaches EXECUTING. A then resumes its original live process.

A's old row is still STARTING, `claimed=true`, with the same token and generation 1. B has its own EXECUTING row/token, also generation 1. A's pre-send check validates only A's row, passes, and applies a second START after B. Both rows end EXECUTING. See `adjacent-results.json#/TTL_live_owner_revival`; `timelines.json` preserves all query, claim, application, ACK, pause and durable timestamps.

**Mechanism:** [`safety.py:1621–1624`](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/irrigation_runtime/safety.py#L1621-L1624) lets an expired STARTING record stop blocking another claimant, while [`1648–1656`](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/irrigation_runtime/safety.py#L1648-L1656) issues per-event tokens without revoking the old event's token/state. [`dispatcher.py:885–918`](https://github.com/webClone/AgriWise/blob/ceb5dd47250a9aca5482dcb2904a5bb3f4105626/services/agribrain/irrigation_runtime/dispatcher.py#L885-L918) checks the old event's record rather than one authoritative current owner/generation for the resource.

This is a distinct schedule from the original: B's idle observation is genuinely current, and A has not yet passed the new token check when takeover occurs. A live paused owner survives a lease timeout and still retains a valid local permit.

**Required correction:** use one resource-scoped owner/generation; a takeover must atomically revoke the old permit, and a revived owner must fail before producing an effect. TTL expiry alone cannot safely create a second valid dispatch right.

## Fixing credit and acceptance matrix

| Schedule/control | START effects | Candidate outcome |
|---|---:|---|
| Original A claim → B idle sample held → A ACK → B claim | 2 | **Original 2E01 remains** |
| Original query exception after A EXECUTING | 1 | Repaired: B STOP_REQUESTED, no B START |
| Original simultaneous two-OS idle barrier | 1 | Exclusive admission control passes |
| Original both idle replies; B held until A ACK | 2 | Delayed-reply failure retained |
| New real-TTL live-owner revival, before token fence | 2 | **Adjacent lease/fence failure** |
| Explicit token API reissue before production fence | 0 | Token mismatch correctly refuses A |
| Explicit token API reissue after fence, before inert application | 1 | Check-to-effect boundary remains |

The exception case now has no `query_ts` after failed transport (`dispatcher.py:574–577`), and existing execution refuses a claim without idle evidence (`safety.py:1632–1633`). This is genuine repair credit. Token replacement **before** the check also genuinely blocks a START.

The two token reissue controls call the public claim API directly for the same event in a separate OS process. They are deliberately labeled API scheduling controls: ordinary duplicate event submission is not claimed to use this path. The after-check control shows that a token is not consumed or rechecked at the physical-effect boundary; it is supplemental contract evidence, not a third demonstrated ordinary-submission race. No production source or admission predicate was replaced.

The original query-exception comparison uses two independent dispatchers in one process, matching the authored original. Other race/control schedules use two actual OS processes. Worker PIDs, exit codes, active-command identities and unfiltered ledger snapshots are recorded.

## Scope, requirements and reproduction

The retained 2E01 failure and new TTL failure block execution exclusivity acceptance under R3 section 183, AB-EXE-002/003/004 and AB-ARC-008 (Stage 6 F16–F19 scope). This report does not re-open unrelated MQTT status or sensor packages. It does not establish commissioned controller idempotency, measured delivery, or full cancellation/restart acceptance.

Official entrypoints, from `/workspace/scratch/de6bc2428cec`:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-ceb5dd4-review/protocol/run_originals.py
PYTHONDONTWRITEBYTECODE=1 python repair-ceb5dd4-review/protocol/run_adjacent.py
PYTHONDONTWRITEBYTECODE=1 python repair-ceb5dd4-review/protocol/build_receipts.py
```

`run_adjacent.py` takes about 34 seconds because its TTL schedule uses real elapsed time. The two copied `resource_*_probe.py` files are reusable helpers; the official wrappers select the reported schedules. Their direct candidate handoff assertion was updated to expect the repaired query-exception count of one. `build_receipts.py` only verifies imports/hashes and extracts source/timeline receipts.

All controller effects are local file collaborators. The source's real shared quota file and file-lock implementation run in private per-schedule folders. There are no production/Git edits, network calls, brokers, physical controllers or hardware. Exactly three adjacent schedules were executed; no further expansion was performed.


---

# Specialist appendix: Legacy receipt and gust-unit regressions

# Bounded verification: receipt migration and gust units

Candidate `ceb5dd47250a9aca5482dcb2904a5bb3f4105626`, parent `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`.

**Both original counterexamples are repaired in the executed candidate source.** The original pre-receipt-map fixture retains publication generation 5 after another scope publishes generation 6. Equivalent gust-only forecasts now produce the same confirmed schedule in either duplicate order. One older no-index legacy input still returns an allocation sequence on its first scoped read; a subsequent commit repairs that receipt through migration.

## Scope and provenance

All production imports come from `repair-ceb5dd4-review/source`. `source-manifest.json` records 41 imported production modules with their Git blob, SHA-256, local path and line count; every blob matches the exact candidate tree. It also hashes the two original authored harnesses. `source-diff.txt` records the two relevant production-file differences from the pinned parent. No repository tests or audit conclusions are used as correctness evidence.

The original legacy schedule is copied to `legacy_receipt_probe.py`, changing only its commit label. Its old broad trajectory helper is replaced by `adjacent_probe.py`, which invokes the same production checkpoint API and redirects all storage into this lane. The default root used by its restart is explicitly configured to that same private store. For the decision script, the original `serial`, `card`, `wx`, `finalize` and `combined_spray` fixture function bodies are loaded unchanged by AST; only its four original gust regression cases run. The unrelated nitrogen, leaching and broad weather suite is excluded. These are harness adaptations, not production repair models.

Exactly two adjacent scenarios were added: an older no-index legacy-head input and an equivalent-gust unit-alias input with an unsafe control. All data and files are inert private fixtures. No production/Git edits, service calls, controller/hardware use or physical action occurred. `CONFIRMED` below is the Layer 8 function's schedule result, not top-level prescription authorization or an executed spray.

## Executed results

| Slice | Candidate outcome | Conclusion |
|---|---|---|
| Original 2E02: A2 allocation 2, interrupted head write, B commits 2–4, A2 recovery publication 5; receipt maps removed while scoped index retained; B publishes 6 | A2 load before B=5; after B=5; idempotent retry=5; restart load=5; immutable A2 record sequence remains 2 | Original receipt-loss counterexample fixed |
| Original historical non-head A1 retry | Typed `ConcurrencyConflictError`; head unchanged before/after B | Recorded separately; no rollback or receipt corruption inferred |
| Original 2E04: gust-only 2 m/s and 7.2 km/h single rows | Both `CONFIRMED` | Single-row controls retained |
| Original 2E04: equivalent duplicates m/s first, km/h first | Both `CONFIRMED`, allowed, no block reason | Original order-dependent double conversion fixed |
| Adjacent unit aliases: `wind_unit=mps` vs `unit=km/h`, both orders | Both `CONFIRMED` | Alias normalization passes |
| Adjacent unit control: gust 5 m/s | `BLOCKED`, not allowed; drift gate reports 18 km/h above 15 km/h limit | Repair preserves rejection of unsafe physical gust |
| Adjacent older legacy head: receipt maps, scoped index and top-level scope labels absent | First scoped A2 load=2, publication generation absent; after B6 migration load/retry/restart=5 | Narrow read-before-migration receipt gap remains |

These outcomes are fresh candidate executions in `results.json`, with the original receipt details also in `legacy-receipt-results.json`. The initial runner attempt stopped at a harness manifest-key mismatch (`commit` versus the supplied tree's `sha`); that was corrected and the complete runner then exited successfully. No production exception is attributed to that harness error.

## Original 2E02 repair: passing credit

Relevant package: **F09, stage 3**; R3 AB-DAT-003/012 and AB-ARC-008 for immutable/scoped/restart-consistent provenance. The exact master plan maps F09 to AB-DAT-003/012/013, AB-ARC-008 and AB-AGR-006 (`sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:362–391`).

In `services/agribrain/world_model/canonical_worldline.py`, the candidate seeds the old known latest checkpoint's publication generation into `checkpoint_sequences` and relevant `scoped_sequences` before replacing the head. It performs this in both orphan-recovery publication (`414–428`) and normal new publication (`486–500`). The original's next independent B publication takes the normal path and preserves A2's known generation 5. Scoped loads use those maps (`270–289`); idempotent save returns them (`387–403`). The executed original therefore no longer changes A2's receipt from publication 5 to allocation 2.

Scientific impact of the repair is reproducible ordering/provenance and restart consistency of the checkpoint receipt. The fixture does not demonstrate numerical water-state corruption, global generation regression or incorrect delivered irrigation; none is claimed. It also does not establish completion of every F09 criterion.

## Original 2E04 repair: passing credit

Relevant package: **F15, stage 5**; master-plan R3 AB-DEC-003, AB-ECO-003, AB-EXE-001, with the unit semantics also relevant to AB-DAT-007 (`Deep_Repair_Plan:521–549`; R3 scientific sections `679–681`).

`services/agribrain/layer8_prescriptive/scheduler.py:186–200` converts duplicate-row wind/gust values to km/h. The candidate now stamps the merged representative as km/h whenever **either speed or gust** exists, and rewrites present unit aliases (`238–251`). The later constraint parse (`417–427`) therefore does not multiply a previously converted gust again. This directly addresses the original gust-only m/s-first failure and passes both duplicate orders plus alias controls. The drift gate still blocks the unsafe 18 km/h gust (`engines/spray_drift_gate.py:41–85`).

Scientific/decision impact: physically equal weather inputs now retain equal constraint outcomes at this seam; the repair removes a false, order-dependent block. These checks do not certify all weather units, legal/resource constraints, or end-to-end action authorization.

## Remaining adjacent case: first read of a no-index legacy head

**P2, receipt metadata consistency; narrower than the original 2E02 fixture.** The added fixture deliberately supplies the still-supported older fallback shape: it removes `scoped_heads`, `cycle_id`, `geometry_version`, `scoped_sequences` and `checkpoint_sequences`, leaving latest checkpoint A2 and global head sequence 5. The immutable checkpoint still records allocation sequence 2. This is an explicit legacy input, not spontaneous deletion from a valid modern store.

The first scoped load finds A2 through the predecessor traversal at `canonical_worldline.py:291–309`. This branch uses `checkpoint_sequences` when present, but lacks the known-current-latest fallback that the indexed branch has at `285–288` and unscoped load has at `324–326`. It therefore returns `sequence=2` with no `publication_generation`, despite the known latest head generation being 5. After B's first write seeds the maps, the same A2 load/retry/restart returns 5 and checkpoint bytes are unchanged. This is a receipt inconsistency before the first migrating write, not a reappearance of the original after-write loss.

Concrete fix: use a shared receipt-resolution helper across indexed load, predecessor fallback, unscoped load and retry. For the checkpoint demonstrably equal to the current latest head, preserve the known head generation even when no scoped index exists. For older non-latest checkpoints whose publication generation cannot be reconstructed, mark it unknown rather than presenting an allocation sequence as established publication order. A read-only resolution can avoid requiring a migration write merely to return the right receipt.

Acceptance: this exact no-index input must return A2 generation 5 on the **first scoped load**, before any B write, and keep 5 after B6, retry and restart; immutable bytes must remain unchanged. Retain the original pre-map fixture and modern receipt behavior. No broader historical-generation reconstruction claim is justified by this bounded fixture.

## Reproduction and bounded acceptance

```bash
PYTHONDONTWRITEBYTECODE=1 python /workspace/scratch/de6bc2428cec/repair-ceb5dd4-review/ownership/probes.py
```

Outputs: `results.json`, `legacy-receipt-results.json`, `source-manifest.json`. The runner uses only candidate production and two explicitly bounded adjacent scenarios. The originals receive passing credit independently of the narrower legacy-read gap. No broader admission-concurrency or field acceptance is inferred.


---

# Specialist appendix: Forecast archive and scoring

# Forecast archive/scoring verification — ceb5dd4

Reviewed **`ceb5dd47250a9aca5482dcb2904a5bb3f4105626`**, parent `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`.

**The original 2E03 small-percent grammar counterexamples are fixed.** `p1`/`q1` now mean 0.01, and `p.5`/`q.5` mean 0.005. Parsing, forecast validation, helper scoring, durable round-trip and evaluation agree. The original numeric-percent metric, timezone, schema, alias and archive-publication controls retain their fixes.

One bounded adjacent check exposes a **narrow, preserved range-validation gap**: a level slightly outside the permitted range can be rounded onto 0 or 1 before validation. This does not undo the 2E03 grammar repair, and it is not evidence that every zero score is false. The previously identified independent-target qualification and sparse-score naming limits also remain. This review makes no full F24, world-model, field-calibration or operational-authorization claim.

## Evidence and reproduction

`probes.py` completed **29 case groups** in one full run: the prior 26 authored case definitions freshly executed against this candidate, plus **exactly three** adjacent groups. The first launch stopped before imports because the new tree export uses `sha` rather than `commit`; the script was adapted to the candidate metadata format and then completed. No production behavior was inferred from that initial schema error.

All **37 staged imported production files** and **two dependency files** matched this candidate's Git tree. `executed-file-manifest.json` lists all 39 production modules/dependencies and the authored/executed script SHA-256. It is an import/execution receipt, not per-line coverage. `source-receipts.json` retains Git blob/SHA-256 receipts, runtime and isolated run path. Archive blob: `a51fd9a918a1d5ea0f5c6e3d08e3f0bdc3c09b8e`; SHA-256 `14bfcc7c19ea1956327b6b1921e199dc9a0288801bc0f1c1f745daa83518b422`.

The two `crop_database` dependency files were copied from local source bytes and checked against the **candidate** tree, not trusted from prior results. Their Git blobs are `462a82e514f8a954ebf8a53748313c18fae842d3` (`__init__.py`) and `17aef77d0a0cdbaee919644b6715bc1d0c5703bb` (`registry.py`). No network retrieval was needed.

Reproduction with Python 3.12 and NumPy/Pandas available:

```bash
python /workspace/scratch/de6bc2428cec/repair-ceb5dd4-review/ledger/probes.py
```

Keep the sibling exact `source`, `git-tree.json`, `commit-metadata.json`, and `ledger/dependencies/crop_database` files. The script verifies candidate/parent identity and source/dependency blobs, disables bytecode writes and creates a fresh isolated archive root. The authored fixtures use direct production calls and selected scheduling, link-failure, child-exit, existing-file-corruption and custom-timezone injections. They use no repository tests/audits as correctness evidence, production/Git edits, external jobs/services/controllers or hardware. The child exit during valid serialization is a controlled interruption, not power-loss testing; ordinary invalid caller type/JSON exceptions are separately labeled.

All **FA** references below are to current `source/services/agribrain/world_model/forecast_archive.py`; **YF** references are to current `source/services/agribrain/layer6_yield/yield_forecast.py`, beneath this review root. Raw evidence is in `results.json`.

## Fixed original 2E03 and caller parity

The percent-prefixed branch now divides p/q suffixes uniformly by 100 (FA **187–204**). The same function is used for validation (**388**), quantile helper scoring (**225**) and evaluation metric extraction (**665**).

For a forecast containing one quantile with value 0 and observation 10:

| Encoding | Parsed level | Helper and archived evaluation score | Median/interval metrics |
|---|---:|---:|---|
| `p1`, `q1`, `1%`, `0.01` | 0.01 | 0.2 | unavailable/null |
| `p0.5`, `P.5`, `q.5`, `0.5%`, `.5%` | 0.005 | 0.1 | unavailable/null |
| `p100`, `100%` | 1.0 | parser endpoint control | — |

Each new caller-parity fixture constructs and validates a real `ForecastRecord`, stores it, cold-loads equal content and evaluates it. A half-percent level no longer receives fabricated median RMSE. This closes the original 2E03 mismatch between p1/q1 and 1%, and between p.5 and .5%.

Retained original FC04-style numeric-percent keys `10/50/90`, canonical p keys, uppercase, explicit-percent and decimal forms all yield score **3**, RMSE **5**, sharpness **20**, coverage **true** for the common distribution. Equal median aliases leave the score unchanged; conflicting values reject. Effective no-offset `tzinfo` and ordinary naive datetimes reject before storage; fixed and cross-offset aware times cold-round-trip with the same instants. These prior repair slices should not be reopened because an adjacent issue remains.

## Three bounded adjacent groups

1. **Percent grammar caller parity:** the p/q small-level aliases above agree across parser, constructor validation, helper, disk round-trip and evaluation.
2. **Malformed aliases and unrounded range:** blank, `pabc`, `q1%`, `pnan`, `pinf`, `p-1` and `p101` reject with `ContractViolation` in parser/helper/store. No rejected record gains evaluation credit. The small out-of-range boundary described below remains accepted.
3. **Sparse scientific-distribution missingness:** tails `q1:0,p99:20` at observation 10 yield finite grid score ≈0.2 and null RMSE/sharpness/coverage. Median-only `q50:10` at observation 12 yields score/RMSE 2 and null interval metrics. A zero point mass `q10=q50=q90=0` at truth yields score/RMSE/sharpness 0 and coverage true. All evaluation files pass strict JSON parsing. Declared unit metadata is not treated here as independently qualified target evidence.

### CEB-L01 — raw out-of-range levels can be rounded into the legal domain

**Confirmed adjacent input-validation gap; not a regression of the repaired p/q percentage branch.** FA **199** rounds the level to six decimals before checking the [0,1] domain at **202–203**:

| Input key | Normalized value before rounding | Accepted returned level | Actual stored evaluation at quantile value 0 / observation 10 |
|---|---:|---:|---:|
| `p-0.000001` | −0.00000001 | −0.0 | grid score 0.0 |
| `-0.00000001` | −0.00000001 | −0.0 | grid score 0.0 |
| `p100.000001` | 1.00000001 | 1.0 | grid score 20.0 |

These malformed level inputs are accepted by the constructor, committed to disk and scored because every caller shares the post-rounding check (FA **225**, **388**, **665**). The practical boundary is tiny; this should be described proportionately as validation ordering, not wholesale failure of forecast scoring. The zero comes from converting an invalid negative level into the valid lower endpoint. A genuine point mass at truth or a legitimate endpoint pinball score may also be zero and remains a positive control.

The fixture also records bare `1.0000004` normalizing to 0.01 through the already supported bare-number-percent convention. That is not counted as this out-of-range defect: its interpretation is governed by the declared mixed fraction/percentage grammar.

**Acceptance:** validate finiteness and the unrounded normalized probability within [0,1] before any identity/dedup precision rounding. Then apply a documented quantization policy and preserve valid endpoints, uniform p/q percentage grammar, alias conflict detection and caller parity. Recheck the three keys above alongside exact p0/p100 and valid-zero controls. Plan F24 **770–779**, task `ST08-F24-02` **1115–1119** and `ST08-F24-04` **1127–1131**; supplied R3 AB-ML-005 **990–992**, AB-ML-010 **1010–1012**.

## Retained archive and numeric controls

| Control | Fresh result on ceb5dd4 | Current source |
|---|---|---|
| Durable conflict / retry | Committed mean 1 cannot be replaced by 99; both rejected attempts leave bytes and warm/cold value unchanged. Observation 99 gives RMSE 98. | FA 477–525 |
| Valid-record interruption / in-flight reader | Exit 83 during temp dump leaves no final record; retry succeeds. Reader sees no partial final, and a complete identical competitor can commit. Crash orphan temp stays inert. | FA 30–58 |
| Concurrent link / injected link error | One incompatible winner; identical writers succeed. Ordinary temp cleanup and retry after injected `OSError` work. | FA 38–58 |
| Caller/retrieved-copy mutation | P50 changed 1→99 after ingress snapshot does not alter archive/cold read/evaluation. | FA 479–480, 523–525, 544, 581 |
| Corrupt/schema-invalid cold records | Injected malformed JSON, top-level array, list metadata, invalid horizon and missing field raise explicit integrity errors. These fixtures were not generated by the successful writer. | FA 549–585 |
| Evidence identity/cache | Colon-containing distinct evidence sets differ; reordered/exact retries deduplicate; observation/microsecond changes remain distinct. Blank/None/scalar IDs reject. | FA 634–645, 701–727 |
| Numeric/time guards | Empty distributions for evaluation, nonfinite/bool/string observation, invalid/crossed/nonfinite quantiles, negative sigma, nonfinite/bool/gross/mismatched horizon and pre-target evaluation reject. Missing distribution is checked before time. | FA 217–274, 358–403, 628–656 |
| Missing scores / JSON | P90-only forecast keeps missing RMSE/interval metrics null; strict JSON rejects nonfinite metadata without cache/final publication. Valid nested zero is retained. | FA 35, 670–687 |
| Valid Gaussian / zero | N(10,1) at 10 gives 0.23369497725510913; sigma-zero truth/error gives 0/2. Gaussian and P10/P50/P90 standard-normal intervals agree on observation 1.5 being outside central 80%. | FA 256–274, 689–695 |
| Yield producer convention | Base and single-branch posterior wheat keep mean 4.5 and rounded P10/P90 3.92/5.08. Explicit local producer/archive adapter and Gaussian representation agree on coverage at observation 5.175. | YF 104–131, 224–244 |

The local producer adapter is a bounded numerical integration control, not deployed pipeline or field validation. Two-decimal producer endpoints explain minor width differences from unrounded Gaussian bounds. No claim is made that finite-grid and analytical continuous-distribution scores must be equal.

## Retained scientific and typed-input limits

**Known target qualification limit, not a new finding:** evidence syntax checks do not establish an independently qualified target's variable/unit/spatial/temporal support, role, availability or domain. Direct evaluation still defaults `in_domain` / `observation_space` (FA **440–441**, **634–645**, **705–716**). The retained opaque-ID fixture does not exercise a deployed resolver or prove a deployed caller supplies unsupported evidence. Acceptance remains a checked target receipt or verified upstream binding contract.

**Known sparse-score convention, not a failed grammar repair:** FA **207–216** calls the unweighted finite pinball average (**245–253**) CRPS. It still needs accurate finite-grid method/levels/weights or a documented integration rule. Gaussian CRPS remains numerically valid in the exercised controls. Domain/horizon calibration and independent scientific skill remain outside this bounded API check.

Malformed caller type exceptions remain mixed; rejected cases publish no final/cache entry. A completely absent distribution can still be archived but evaluation explicitly rejects and receives no numeric credit. These are retained contract limits, not process crashes or newly demonstrated false scientific skill.

## Plan/R3 scope

The master plan is `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`: F23 **730–753**, F24 **755–779**. Task references use `AgriBrain_Work_Packages_Task_List_2026-10-07.md` **1069–1139**; Stage 8 is in `AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md` **36**. This review credits specific original repairs and preserves the wider dependency gates.

Normative references use supplied `current-plan-review/R3_current_scientific_sections.txt`: AB-DAT-005 **675–677**, AB-DAT-011 **699–701**, AB-ARC-007 **746–748**, AB-ARC-008 **750–752**, AB-ASM-014 **828–830**, AB-ASM-016 **836–838**, AB-ML-005 **990–992**, AB-ML-010 **1010–1012**. Prospective corpus lineage, learned world-model capability, independent field calibration and operational promotion were not certified here.


---

# Specialist appendix: Active integration and plan traceability

# Candidate integration review — ceb5dd47250a9aca5482dcb2904a5bb3f4105626

The candidate improves the L3→L4 physical boundary: realized flux receipts and separate analysis increments are present, root support is explicit, nonconservation survives into the typed L4 receipt, and L4 blocks its own prescriptions and lowers confidence when that receipt is nonconserved. This does **not yet close the full integration contract**. Two bounded offline cases show a root-support confidence/provenance gap and a lossy adapter that can regenerate an internal L8 fertilizer candidate after L4 blocks it. Neither case demonstrates published or actuated unsafe instructions.

This lane reviews caller flow and preservation, leaving pure water-balance mathematics and L4 nutrient mathematics to the other reviewers. W01/W02 are review labels, not normative package IDs. No repository test, audit report or historical result is correctness evidence here. No production/Git edit, network provider, DB, deployed service, worker, or hardware was used.

## Executed evidence and source identity

`integration_probes.py` executes **two counterexample scenarios** in the current candidate source: (1) actual `WaterIntelligenceEngine.execute_pipeline`, state/receipt contracts and factory, with an explicit single-layer profile and weather; (2) exact L4 nonconservation-gate AST plus the exact active nutrient-normalizer AST, followed by the actual `ActionRankingEngine`. A receipt-preservation positive control injects a failed receipt; it does not claim that the solver produced a conservation error. The checkpoint portion is an AST key inventory only.

`results.json` and `probe-stdout.json` retain raw output. Python is3.12.14. `source-manifest.json` verifies77 unique candidate files:65 actually imported files plus static reference files. Every byte matches the candidate Git tree. AST code comes from `layer4_nutrients/runner.py`, `orchestrator_v2/runner.py`, and `layer3_decision/runner.py`; the actual ranker, L3 engine, contracts and dependencies are candidate files, not copied historical implementations. This is not a complete supported deployment/runtime certification.

## Active caller flow and fixed controls

| Boundary | Current source behavior | Evidence |
|---|---|---|
| Entry to hydraulic engine | Both canonical and legacy L3 decision bridges invoke `_execute_canonical_water_engine`; it executes one dated `WaterIntelligenceEngine` step per day. | `layer3_decision/runner.py:755–784,2480–2504`; orchestrator L3→L4 sequencing at `orchestrator_v2/runner.py:2636–2654` |
| Step→published water state | Layered balance attaches `IntervalFluxReceipt`; L3 uses integrated transpiration/evaporation/drainage/runoff/capillary fluxes and builds a separate `AnalysisIncrementReceipt`. | `layer3_water/soil/layered_water_balance.py:298–329`; `layer3_water/runner.py:249–285,306–341,399–422` |
| Physical boundary to L4 | `WaterState.mass_conserved` prioritizes the transition receipt. `to_layer4_boundary_receipt()` carries root storage, depth-weighted FC/WP/saturation, supported depth, drainage, closure and degraded status. L4 reads this receipt before legacy SWB comparison. | `layer3_water/contracts/water_state.py:386–444`; `layer4_nutrients/runner.py:190–273` |
| Local nonconservation gate | L4 caps states at0.20, appends a physical uncertainty note, disallows each local prescription and adds `nonconserved_water_transition`; its data health is degraded and missing-driver/penalty metadata is emitted. | `layer4_nutrients/runner.py:655–667,764–776` |
| Checkpoint commit | Wrapper stages local state, uses scoped predecessor CAS, verifies durable head, then commits authoritative RAM; persistence conflicts/errors roll RAM back and are re-raised. | `layer3_decision/runner.py:2515–2553,2642–2759`; `world_model/canonical_worldline.py:330–348,460–513` |
| Scheduling control | Scheduler preserves an already-blocked card as BLOCKED and now validates finite nonnegative consistent rate envelopes before scheduling. This is a positive source control, not a reproduced full schedule. | `layer8_prescriptive/scheduler.py:260–309` |

All paths above are under `services/agribrain/`. Numerical closure correctness across all forcing regimes is outside this lane; preservation of a field does not establish its physical validity.

## Executed case1: unknown root support is not reflected in confidence

The fixture uses the actual `VegetationState` contract, whose root proxy is legitimately `Optional[float]=None` (`layer2_contracts/state_contracts.py:198–230`), an explicit10cm profile and complete finite weather. The actual L3 pipeline returns:

- substituted root depth1.0m, supported depth10cm;
- mass conserved, closure0;
- water confidence0.938, data health1.0;
- L4 boundary `is_degraded=false`, supported depth10cm, physics authority ASSIMILATED, assimilation status PROGNOSTIC_MODEL;
- an internal MPC IRRIGATE decision of5.4mm gross at confidence0.75.

The supported storage/geometry is correctly restricted to10cm in this case. Low coverage alone is **not proof the mathematical rate is unsafe**. The defect is that unknown/requested versus supported root depth and its provenance do not lower or qualify the aggregate confidence/degraded claim. `runner.py:174–182` substitutes1.0m for a missing proxy (0.3m without a vegetation state); `state_factory.py:304–332` retains supported depth, but `create_water_state` defaults data health1.0 and computes confidence only from closure, solver and atmospheric quality (`375–415`). `water_uncertainty.py:58–87` does not consume root coverage/provenance. The boundary degraded decision uses conservation and data health only (`water_state.py:411–414`).

This is an actual direct-engine/contract counterexample. The full wrapper may synthesize/default root depth earlier, or reject some missing dated roots during coercion (`layer3_decision/runner.py:1142–1218,2048–2072`); this direct fixture is not proof that a browser request reaches the same missing-root shape. It shows the accepted public L3 engine contract loses the uncertainty dimension. The internal MPC decision is not a published prescription, successful eligibility promotion or actuator call.

Acceptance: carry root-depth source, requested/support depth and coverage in the typed boundary, distinguish bounded partial support from complete root knowledge, and propagate that uncertainty into water/L4 claims. Verify supported-profile computation, confidence qualification and crop-neutral diagnostics separately. This maps primarily to **F10** (`AB-AGR-008,AB-AGR-010,AB-DAT-007`), **F04/F05** soil/support/covariance criteria, and the broader scientific uncertainty contract; it does not close or invalidate all of those packages.

## Executed case2: L4 blocking reason is lost before the L8 candidate ranker

The fixture starts with a diagnostic nutrient probability0.8/confidence0.9 and an explicit `swb.mass_conserved=false`, closure2mm. It executes the exact new L4 gate (`runner.py:656–667`). The local prescription becomes disallowed with `nonconserved_water_transition`, the state confidence becomes0.2 and its notes retain the physical warning. This positive control passes.

The actual orchestrator normalizer (`orchestrator_v2/runner.py:3432–3459`), called while constructing L8 input (`2858–2867`), forwards probability, confidence, severity, state index and driver names. It drops SWB conservation/closure/degraded state, the notes, local prescription blockers and data health. The exact resulting normalized state sent to the actual ranker produces a new **allowed FERTILIZE120kg_N/ha** card with HIGH categorical confidence, confidence-score component0.2 and no blocking reason. The ranker derives its categorical confidence/degradation from L0 audit grade, while using deficiency probability to generate a fresh rate (`layer8_prescriptive/action_ranker.py:96–115,196–236`).

This demonstrates a **conditional internal candidate eligibility gap**, not an end-to-end promotion bypass. The fixture explicitly uses audit gradeA to isolate the adapter; it stops at the ranker. Main still applies prescription influence-manifest, tribunal, planning, weather and soil gates (`orchestrator_v2/runner.py:2712–2736,2940–2964`); L8 also has crop/phenology authority handling (`layer8_prescriptive/runner.py:94–158`). Public output requires further authorization. This lane did not demonstrate those gates accept the candidate, final scheduling, publication or actuation.

Acceptance: preserve typed physical blocker identity in the L4→L8 adapter and final feasibility contract, so a fresh candidate cannot silently discard a failed upstream physical boundary. Do not confuse a low numerical confidence-score component with a categorical hard prohibition. Carry the same reason through diagnostic adapters (`diagnostic_integration/adapters.py:341–380` currently preserves state confidence and payload, not this SWB failure reason). Map to **F10** boundary/degradation and **F15** final hard action limits, with **F01/F02** typed authority and provenance as cross-cutting dependencies. Existing F15 weather/rate fixes are positive partial controls, not closure of this different blocker-preservation criterion.

## Static preservation limit: checkpoint state is not a durable transition/failure ledger

The wrapper's candidate history retains `water_state` in RAM (`layer3_decision/runner.py:2529–2553`). The durable payload projection (`2650–2691`) writes soil, hydraulic memory, initial states, forcing/evidence hashes, events, withdrawals and a history summary. It omits `IntervalFluxReceipt`, `AnalysisIncrementReceipt`, mass-conservation/closure flags, root-support confidence qualifications and explicit downstream admissibility. The store atomically persists the supplied projection (`canonical_worldline.py:469–481`); it does not restore omitted fields. Cold hydration creates history entries with `water_state=None,feedback=None` (`layer3_decision/runner.py:2597–2607`), expecting recomputation.

This is a current-source serialization omission, **not a reproduced restart failure or proof a nonconserved checkpoint is inadmissibly published**. Stored forcing/priors may permit deterministic reconstruction; that has not been executed here. The checkpoint CAS and rollback controls remain valuable. Acceptance for **F03/F09** should explicitly retain or content-address the transition, assimilation increment and failed/degraded eligibility receipt across checkpoint/restart, and prove reconstruction if that is the intended design. A durable hydraulic state snapshot and a published scientific-admissibility receipt are separate claims.

## Weak-label and adjacent consumer scope

The identified actual weak-label producer is ASMAE `_export_weak_labels → training.exporter.export_weak_labels` (`layer05_asmae/engine.py:1576–1603`), using state/uncertainty, retro holdouts, BMA, radiometric validity, processed scenes, production usability and export mode (`training/exporter.py:35–123,135–184`). Its inputs do not include L3 transition or L4 SWB receipts. ASMAE execution precedes the later L3/L4 run in this orchestrator (`orchestrator_v2/runner.py:1938–2105,2636–2654`). No direct same-run L4→weak-label producer call was established. The new L4 block therefore cannot be claimed as a newly proven global training-export gate, and this lane does not claim that an independent ASMAE label is invalid merely because a later hydraulic transition fails. Corpus/objective-specific eligibility remains **F25/T02/T04** work requiring its own lineage acceptance.

An adjacent map consumer still looks for scalar `canonical_water.soil_water.theta_fc` (`layer10_sire/surfaces/water.py:92–98`) while the canonical state carries profile values. This is a static consumer limitation: the new root-supported L4 boundary does not certify all L10 map projections. No map rendering or scientific authority claim was executed in this lane.

## Normative identity and remaining work order

`verify_metadata.py` independently checks the candidate tree against the supplied normative documents. All3 plan blobs are exact and unchanged from parent2e1fbcb:

| Document | Git blob |
|---|---|
| Deep Repair Plan | `08d378a65992de859369950599df198e64244f01` |
| Execution Sequencing Addendum | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| Work Packages / acceptance register | `8a564647af7e588802537817159117b349ff606b` |

The register has52 unique full-acceptance rows,0checked. This describes the register, not52 demonstrated defective implementations. `plan-results.json` contains direct master-card requirements, stages, R3 line references and R3 SHA256 for the relevant packages.

A rational next order respects those dependencies and allows parallel work:

1. **F03/F04/F05/F10 physical-boundary lane:** finish mathematical verification with the other reviewers, then integrate explicit uncertainty/root provenance and invariant receipt semantics. This review supports partial improvements; it does not replace their mathematics.
2. **F08/F09 durability lane in parallel:** persist or hash the new transition/analysis/failure receipts and prove same-day, historical and restarted reconstruction under predecessor CAS. Do not declare scientific publication admissibility solely from checkpoint success.
3. **F10/F15 authority lane in parallel:** preserve physical prohibitions across normalizers, diagnostic promotion and fresh action generation, then test final public feasibility/authorization with a nonconserved upstream case. Keep current weather/rate and manifest positive controls.
4. **F11 nutrient lane after F10 contract stabilizes:** independently close residual nitrogen/pool accounting; this candidate's water changes are not evidence F11 is repaired.
5. **F23/F24/F25 and T02/T04/T11 evaluation/operations lane:** bind forecast/corpus/labels to exact run/receipt/availability identities, run independent outcome validation and supported-image recovery drills. Planned scientific validation is not counted as a current code defect merely because it is unfinished.

Reproduce locally with `python integration_probes.py` and `python verify_metadata.py` from this directory. The former is limited to the two explicit scenarios and a preservation control; the latter only reads metadata and source bytes.

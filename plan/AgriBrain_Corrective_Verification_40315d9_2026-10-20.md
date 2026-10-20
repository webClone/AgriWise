# AgriBrain corrective verification and implementation readiness

**Candidate/main:** `40315d95ff875914bd2f83cd1e75d88fdae859ff`  
**Parent:** `51932bfd7c588395b45e353d41f9519a0fe08bc4`  
**Date:** 20 October 2026  
**Verdict:** Both R51901 and R51902 are resolved in the independently executed contracts. No new reproducible finding was established in the bounded follow-up scope. **Proceed with the next dependency-ready implementation work in the existing plan.** These two findings no longer justify another corrective repair cycle.

## 1. What is now verified

The runtime fix removes the false delivery/stop obligation from a positively unsent contender without disrupting the actual owner. A fresh B refused while A runs is FAILED, holds no reservation, has no active/watchdog tracking, and cannot stop A when polled. A's own positive cancellation releases the resource so a fresh C can execute. The complete three-process effects are exactly START(A), STOP(A), START(C).

The scientific fix rejects nonfinite/boolean support as a valid physical root domain at the typed receipt, L4 consumer and direct loss-engine boundaries. The original positive-infinite-supported-depth fixture now produces supported depth0, coverage0 and degradation; root-dependent losses are unavailable rather than healthy low-risk estimates. Fertilizer prescriptions are blocked, state/health/reliability cap at0.1, and serialized explanations survive downstream.

The earlier repaired admission, claim-idempotence, true in-flight retention, water accounting, zero/missing-root qualification and L4→L8 restrictions also retain their demonstrated behavior. This is meaningful progress toward the R3 target, not merely a code-presence or repository-test assertion.

| Finding | Disposition | Independent evidence |
|---|---|---|
| **R51901: positively unsent B leaves STOP_REQUESTED exposure and blocks later C** | **Verified resolved** | Actual OS-process ordinary submit/poll/cancel/subsequent-submit lifecycle: B FAILED/no exposure/no monitoring, A unaffected by B polling, positive STOP(A), C EXECUTING. |
| **R51902: positive infinity treated as healthy root support** | **Verified resolved** | Actual typed receipt→full standalone L4 and full L8; independent direct loss-engine +Inf/NaN/boolean checks; supported finite controls retained. |

The machine-readable register records both resolutions and an empty new-finding list. This closes the reviewed corrective findings in the executed scope; it is not an assertion that all52 master packages are fully accepted.

## 2. Exact candidate, scope and methodology

GitHub metadata verifies40315d9 directly follows51932bf, and main was observed at the candidate. The recursive tree has4,085entries, is not truncated and contains no AGENTS.md. The commit changes four production Python files: irrigation dispatcher, water-state contract, environmental-loss engine and nutrient runner. Two prior review documents and two repository tests also appear in its file list; those files are not correctness evidence.

A private source reconstruction contains **732 production/configuration files**, matched byte-for-byte to candidate Git blobs. All four changed production files compile without importing/executing them. This corpus supports reconstruction/import identity; it is not a claim of dynamic review coverage for every repository function. Import counts overlap and must not be added together as repository coverage.

Three parallel reviewers own runtime/protocol, full L4 science and downstream integration. The root reviewer owns retained public-store/hydrology regressions, normative identity and serializer/direct-loss checks. Six appendices distinguish these owners; this is not presented as six independent final-agent reviews.

Probes execute actual production functions against private inert collaborators. Runtime workers are actual OS processes. Two lease schedules wait a real31.1seconds; direct-store controls separately inject a clock. Full standalone L4 and L8 execute; the exact unchanged orchestrator normalizer is isolated by AST extraction rather than initializing the whole orchestrator. Malformed scientific inputs deliberately replace fields on actual dataclasses and are labeled contract-admission fixtures, not naturally generated solver states.

Repository tests, old audit conclusions and the reported521-test suite are not adopted as independent proof. No production/Git edits, service startup, provider/network calls, live brokers, controllers, radios, drone missions or physical hardware operate. The evidence bundle excludes production source copies, repository tests/audits and private generated stores.

## 3. R51901: actual lifecycle and preserved resource safety

The correction at [irrigation_runtime/dispatcher.py:L562-L577](https://github.com/webClone/AgriWise/blob/40315d95ff875914bd2f83cd1e75d88fdae859ff/services/agribrain/irrigation_runtime/dispatcher.py#L562-L577) removes B from local active execution, ends monitoring, releases safety quota and removes the durable reservation before publishing FAILED. It now agrees with the existing positively-unsent claim-refusal branch at [irrigation_runtime/dispatcher.py:L594-L617](https://github.com/webClone/AgriWise/blob/40315d95ff875914bd2f83cd1e75d88fdae859ff/services/agribrain/irrigation_runtime/dispatcher.py#L594-L617).

| Stage | Current observed state |
|---|---|
| A submits | EXECUTING; START count1, STOP count0; A owns resource and exposure. |
| B arrives while A runs | FAILED before transport; no B reservation, local active record or watchdog. No START(B). |
| B status is checked | FAILED; A still running, no extra STOP. |
| A owner cancels A | Positive STOP(A); A CANCELLED; resource can be reused. |
| Fresh C submits | EXECUTING; START count2, STOP count1; only C remains active. |

This is the exact original residual schedule, including three actual worker processes and B's poll. It now progresses without a phantom8mm B reservation. It does not infer delivered depth from command targets; the actual owner retains its own stopped-delivery receipt/accounting.

The broader retained schedules also pass: both simultaneous-idle barriers, a delayed idle reply across ownership/ACK, query failure after execution, preparation lease expiration before the transport fence, and in-flight protection after the fence. Each conflict schedule yields exactly one START. A before-fence expired owner cannot dispatch; an owner already inside transport cannot be displaced merely by lease age. The atomic transport transition/current token checks are preserved ([irrigation_runtime/dispatcher.py:L948-L968](https://github.com/webClone/AgriWise/blob/40315d95ff875914bd2f83cd1e75d88fdae859ff/services/agribrain/irrigation_runtime/dispatcher.py#L948-L968), [irrigation_runtime/safety.py:L1742-L1800](https://github.com/webClone/AgriWise/blob/40315d95ff875914bd2f83cd1e75d88fdae859ff/services/agribrain/irrigation_runtime/safety.py#L1742-L1800)).

No new adjacent runtime scenario was necessary: the fix is narrow, the original residual plus existing race/lease controls cover its changed decision boundary. Store corruption, arbitrary transport faults and every restart branch were not reopened as a new general runtime audit.

## 4. R51902: scientific support validity and loss meaning

The receipt validates numeric/nonboolean/finite/positive supported and requested depths before calculating coverage ([layer3_water/contracts/water_state.py:L429-L456](https://github.com/webClone/AgriWise/blob/40315d95ff875914bd2f83cd1e75d88fdae859ff/services/agribrain/layer3_water/contracts/water_state.py#L429-L456)). In the original fixture, supported depthInf/requested60cm now yields supported0/requested60/coverage0/degradedtrue. The underlying water transition remains physically conserved with closure0; invalid support is not disguised as a fabricated mass-balance failure.

L4 additionally checks finite supported depth on receipt consumption and before VWC/loss calculation ([layer4_nutrients/runner.py:L226-L235](https://github.com/webClone/AgriWise/blob/40315d95ff875914bd2f83cd1e75d88fdae859ff/services/agribrain/layer4_nutrients/runner.py#L226-L235), [layer4_nutrients/runner.py:L535-L550](https://github.com/webClone/AgriWise/blob/40315d95ff875914bd2f83cd1e75d88fdae859ff/services/agribrain/layer4_nutrients/runner.py#L535-L550)). Direct environmental-loss entry points apply the same scalar qualification ([layer4_nutrients/environmental_losses/engine.py:L130-L147](https://github.com/webClone/AgriWise/blob/40315d95ff875914bd2f83cd1e75d88fdae859ff/services/agribrain/layer4_nutrients/environmental_losses/engine.py#L130-L147), [layer4_nutrients/environmental_losses/engine.py:L239-L255](https://github.com/webClone/AgriWise/blob/40315d95ff875914bd2f83cd1e75d88fdae859ff/services/agribrain/layer4_nutrients/environmental_losses/engine.py#L239-L255)).

| Output in the original +Inf-supported-depth fixture | Verified result |
|---|---|
| Actual full-L4 loss arguments | root0, VWC0 placeholders after invalid support qualification |
| Leaching/denitrification | availabilityUNAVAILABLE_UNSUPPORTED_ROOT, is_supportedfalse, riskUNAVAILABLE |
| Aggregate | availabilityUNAVAILABLE_UNSUPPORTED_ROOT, is_root_supportedfalse, explanatory note |
| Water-dependent N-budget debits | Excluded; no unsupported104.4kg/ha leaching debit |
| N/P/K prescriptions | All blocked with unsupported_root_boundary |
| State confidence, health/ceiling/reliability |≤0.10; degraded |
| Notes and downstream fertilizer actions | Notes serialize; full L8 retains false/LOW/BLOCKED actions |

Separate direct actual loss-engine calls verify positive infinity, NaN and booleanTrue produce unavailable pathways without relying on the canonical receipt sanitizer. A finite60cm control remains supported/AVAILABLE. Zero/missing-support excluded-debit placeholders must be interpreted with their typed availability; they are not measurements of physical zero flux.

The earlier explicit zero-root dry and declared20mm-drainage controls retain their corrected meaning. Missing canonical water plus missing weather remains explicitly unavailable, massfalse, root0, blocked and health0.1 with the hydrology-missing reasons. Finite full/shallow/partial support and the supported-root nonconservation gates retain their prior behavior.

## 5. Precision qualification: invalid request is not identical to invalid supported depth

One bounded adjacent composition sets **requested** depthInf while keeping a separately known finite60cm supported profile. The current receipt preserves supported60, normalizes requested0, reports coverage0 and degradation. L4 evaluates the finite supported domain: VWC0.2293, declared20mm drainage produces11.8kg/ha modeled leaching, with a corresponding qualified supported-domain budget debit. N/P remain allowed under the existing degraded-supported policy, with explanatory notes, reduced confidence0.667/0.600, health0.4/degraded and reliability0.333.

This differs from the broad prose claim that any invalid requested extent zeros every supported-depth field. It is **not** an independently demonstrated defect: known finite supported-profile estimates are retained with degradation, rather than silently presenting healthy full-root coverage. The plan does not make every degraded partial-domain state an automatic fertilizer prohibition. The original malformed **supported-depth** failure is fixed; this qualification should be reflected in documentation without inventing another mandatory hard block.

A second naming correction: the finite checks occur twice inside the actual standalone runner; that file has no `_extract_soil_water_boundary` function definition. The checks execute in the reviewed function, so this is a description correction, not a missing implementation.

## 6. Integration and retained scientific controls

Eight complete standalone L8 compositions preserve the actual N/P/K blockers: prior dictionary/typed permission and nonconservation controls, explicitzero support, missingwater/weather and the repaired +Inf case. Fertilizer candidates are present and BLOCKED; MONITOR remains allowed/CONFIRMED, avoiding a vacuous universally-disabled pass. Conservation status/closure remain distinct from support validity: the repaired +Inf case can be conserved yet unsupported, while the separate nonconserved fixture retains false conservation and closure2mm. Standalone outputs have no authorization envelope.

All eight retained hydrology checks pass: independent soil/whole ledgers, ET partition, warm/cold round-trip, zero-capacity rejection and valid pond controls. These are bounded surrounding-physics regressions; rounding tolerances are retained rather than treating displayed zero as universal unrounded proof.

Public-store regressions preserve ADMITTED quota identity, one-owner admission and positively-unsent cleanup without altering the owner. Repeated same-event STARTING/DISPATCHING/SENDING/EXECUTING claims retain token, generation, timestamps, phase and store bytes. The stale preparation retry does not renew its lease; mandatory transport entry still expires/rejects it. Synthetic public-store phases and injected-clock results are distinguished from ordinary dispatcher schedules.

Actual raw serialization retains declared prescription notes and loss availability. The isolated actual public adapter yields degraded L4, no recommendations and BLOCKED authorization for the fixture without L8. It deliberately summarizes the raw artifact; no new consumer defect is inferred simply because a summary omits some raw fields. Complete conservative nutrient pools, measured delivery, local agronomic calibration and economics remain wider plan criteria rather than newly asserted failures in this patch.

## 7. Plan/R3 alignment and acceptance accounting

Three normative documents match current committed blobs exactly: master `08d378a65992de859369950599df198e64244f01`, sequencing addendum `40751038dc8760e91bc3ab115e30c5e28395953a`, register `8a564647af7e588802537817159117b349ff606b`. Supplied R3PDF SHA256 is `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; its scientific sections/requirement extraction accompany the evidence.

| Plan area | Meaning of the verified repairs |
|---|---|
| F16–F18, Stage6 | R51901 supplies missing truthful unsent lifecycle/resource reuse evidence. Retained ownership/uncertainty controls stay intact. It does not certify every device/recovery/settlement criterion. |
| F01/F04, Stages1/2 | Finite, nonboolean supported-domain admission now prevents malformed support from receiving healthy interpretation at the checked boundaries. |
| F10/F11, Stage4 | Literal F10 scientific IDs AB-AGR-008/010 and AB-DAT-007; F11 AB-AGR-010/008. Root/loss missingness and excluded debits retain correctness; complete nutrient-stock/pool criteria remain separate. |
| F15 and consumer/publication work | Full L8 preserves restrictions through checked compositions; consumer summaries and full operational routes have their own scope. |

F/T package IDs and R3 scientific requirement IDs are different namespaces. The register contains **52 unique FA headers, all open: F01–F40 plus T01–T12;0checked**. Its68 textual FA mentions include cross-references. Open full acceptance is not proof52 implementations are missing or broken, and this report does not invent a program completion percentage.

Resolving these corrective finding IDs does not automatically close full packages. Conversely, every software/scientific package should not be held open solely because unrelated hardware commissioning is pending: apply each package's actual acceptance criteria and dependencies. This report leaves the existing register unchanged.

## 8. When to proceed and what to do next

**Proceed now beyond this corrective batch.** Record R51901/R51902 as verified resolved within these software contracts, retain the small regression set, and advance the next dependency-ready ticket in the execution addendum. No further repair iteration on these two originals is warranted by the current evidence.

Use one coherent integration baseline at40315d9. For the next package, complete its own scientific equations/data availability, caller integration, state persistence and acceptance evidence rather than treating module presence or a generic passing test count as completion. Prioritize remaining connected water→nutrient conservative pool/application work and runtime delivery integration according to their declared dependencies; this review does not independently determine which remaining ticket has already been completed outside its scope.

Omega/world-model research/design can continue with supported or explicitly qualified scenario/shadow inputs. Full implementation, empirical forecast/calibration claims and operational release should satisfy their own R3/plan requirements; this review introduces no universal prerequisite that all52 packages or all hardware must finish before research progresses.

Only broaden verification when a changed file, failed retained control or unresolved dependency warrants it. Repeating an unbounded whole-repository defect search after every small patch would not improve the evidence for these now-resolved cases. The original program's2,564–4,540hour estimate is not a freshly calculated remaining effort for this commit.

## 9. Reproduction and limits

The report has six appendices, separating three parallel specialist reviews and three root-owned control lanes. The machine-readable register records two resolved claims, no newly reproduced findings and the documentation qualifications above. The ZIP contains authored scripts, current outputs, source/plan hashes, timelines, a reconstruction layout and read-only Git-object materializer. It contains no production source copies or repository tests/audits.

Eleven commands are replayed from a separate exact-source layout, with production bytes checked before and afterward. Zero exit means declared observations reproduced; it is not a repository-test pass count. The Git-object materializer is syntax/layout checked rather than executed against a separate complete Git checkout. No public authenticated HTTP route, complete live orchestrator service, publication, real sensor/controller or field-delivery acceptance is claimed. Those limits do not negate the concrete repair credit documented above.


---

# Specialist appendix: Water conservation and compartments

# Root-owned hydrology regression controls

Candidate `40315d95ff875914bd2f83cd1e75d88fdae859ff`, parent `51932bfd7c588395b45e353d41f9519a0fe08bc4`. This is a root-owned rerun of the established authored hydrology controls, not an additional independent-agent final review.

All eight retained acceptance checks pass: no harness errors, W01 independent closure, warm/cold round-trip equality, direct pond/soil evaporation partition, full-pipeline ET component consistency, rejection of positive pond storage at zero capacity, valid0/0 acceptance and valid5/12 acceptance. The receipt module changed in this commit; no blanket unchanged-water-code claim is made. Imported current production bytes match the candidate tree.

`probes.py` executes actual production water factories, layered solver, full water pipeline and soil-water hydration with explicit soil/weather fixtures. It computes soil and whole-system residuals independently from serialized states/receipts. The zero-capacity direct solver fixture deliberately supplies an inert legacy-shaped infiltration object to reach the admission guard. Private checkpoint roots are isolated. No repository tests/audits, production/Git mutations, provider calls, services, field controllers, radios or hardware operate.

The checks retain numerical tolerances appropriate to published rounding; they do not equate a displayed0.0000 with proof of unrounded mathematical identity for every profile. The root-support validity method's new branches and complete L4 consumption are evaluated by the decision/platform lanes. This lane is bounded surrounding-physics regression evidence, not a new exhaustive support, soil-parameter or empirical calibration study.

Reproduce with `PYTHONDONTWRITEBYTECODE=1 python repair-40315d9-review/trajectory/probes.py`. `results.json` contains fixtures, states, receipts, residuals and explicit assertions; `source-manifest.json` verifies every imported production file. No new hydrology finding was reproduced.


---

# Specialist appendix: Typed L3 to L4 boundary and nutrient qualification

# R51902 and retained L4 root-boundary verification

Candidate `40315d95ff875914bd2f83cd1e75d88fdae859ff`, parent `51932bfd7c588395b45e353d41f9519a0fe08bc4`. Reviewed 20 October2026.

**R51902's original infinite-supported-depth failure is repaired in the executed full standalone L4 path.** The malformed supported depth is sanitized to unavailable support; the actual environmental engine emits unavailable root-dependent pathways; previously allowed nutrient prescriptions block and health/confidence degrade. R47803/R47804's explicit-zero and absent-canonical fixes, along with valid-root arithmetic, nonconserved gates and serialized notes, retain their verified behavior.

The single adjacent group preserves a valid60cm supported profile while making requested root extent invalid. It retains estimates over that finite domain and marks the overall boundary degraded. This is a distinct partial-domain policy, **not a newly demonstrated hard-block failure or silent promotion to healthy/full-root authority**. No new empirical defect was established by the bounded lane.

## Reproduction, source identity and limits

The exact command executed from `/workspace/scratch/de6bc2428cec` was:

```bash
python repair-40315d9-review/decision/probes.py
```

`probes.py` executes the twelve prior compositions against the new source and exactly **one** adjacent group. All **13** completed with assertions. `results.json` records complete input fixtures, independent posterior-depth references, actual loss-engine arguments, typed receipts, loss availability, budget/audit scalars, nutrient confidence, prescriptions, notes and health/quality. Nonfinite floats are stringified only when saving JSON, after actual production execution; they are not coerced before the production call.

`executed-source-manifest.json` verifies **113 exact candidate production files** against the pinned Git tree, each before import and all loaded candidate files again after execution. `review-source-manifest.json` supplies focus-source hashes/line references, normative-document hashes and scoped dispositions. Source identity is a prerequisite, not scientific correctness evidence.

The actual water engine/root factories, actual typed-receipt method, full `run_layer4_standalone` and actual environmental-loss engine execute. Its observer records arguments and delegates unchanged. There is no model stub, target-body/AST rewrite, prior result as correctness proof, repository-test/audit proof, production/Git modification, network/service/controller/hardware execution.

The valid-root/partial-root cases use actual unchanged pipeline output. The malformed supported/requested-depth, low-health, nonconserved and declared-drainage cases deliberately replace fields on actual frozen production dataclasses after a valid run. They test receiving-boundary behavior; they **do not demonstrate a validated solver-generated malformed state, a public-route bypass, a full orchestrator run or physical actuation**. The full standalone API is exercised in its documented research mode without semantic lineage. Broader store/normative regressions belong to the coordinator.

## Original R51902: corrected behavior

The original reproducer starts with a valid profile: layer bottoms10/30/60cm; theta.18/.23/.28; FC.25/.28/.32; WP.07/.09/.11; saturation.40/.43/.46; lab parameter provenance; the same hot/dry weather and LAI3/FVC.8. The actual water pipeline produces finite posterior storage137.55mm over60cm. The malformed fixture replaces **supported_root_depth_cm with+Inf** and declares20mm drainage, retaining the other finite profile fields. This intentionally violates the typed domain's physical consistency; no solver-generation claim is made.

Current results:

| Layer/quantity | Actual candidate output |
|---|---|
| Typed boundary | **supported depth0cm**, requested depth60cm, coverage0, `is_degraded=True` |
| Full-L4 SWB | supported0, degraded; no positive infinite support retained |
| Actual loss-engine call | **root_depth_cm0, soil_moisture_vwc0**, drainage20mm |
| Leaching and denitrification | numeric0 placeholders with **risk_classUNAVAILABLE**, **availabilityUNAVAILABLE_UNSUPPORTED_ROOT**, **is_supportedFalse** |
| Aggregate result | **availabilityUNAVAILABLE_UNSUPPORTED_ROOT**, **is_root_supportedFalse**, explanation that root-dependent pathways are unavailable/excluded from debit |
| N budget | unsupported leaching/denitrification debits0; no former104.4kg/ha artifact |
| N/P prescriptions | proposed163.1/43.8kg/ha retained as proposals, **both blocked** with `unsupported_root_boundary`; K also blocked |
| State and quality | N/P/K/S confidence.1; L4 overall/ceiling/reliability.1; degraded status; `UNSUPPORTED_ROOT_BOUNDARY` and penalty |
| Notes | unsupported-root reason survives actual dataclass serialization |

The preserved numeric zeros are **qualified placeholders**, not claims of measured zero loss. Likewise the aggregate still stores6.56kg/ha supported-component subtotal and173.44kg/ha arithmetic remainder with a result-level unavailable flag/note. They must not be presented as a complete root-zone loss or fully known available-N estimate. The initial N180kg/ha is the model's preliminary demand argument, not independently verified applied fertilizer. The checked complete output retains the availability context; this review does not count every numeric placeholder as a remaining defect.

Source chain, repository-relative under `services/agribrain/`:

- `layer3_water/contracts/water_state.py:429–455` checks finite positive nonboolean supported **and requested** depths; the invalid supported value becomes0, coverage0, degraded. Valid counterpart values are retained.
- `layer4_nutrients/runner.py:226–235` normalizes invalid received support; **535–558** applies a finite positive nonboolean support gate before computing loss-model VWC/depth.
- `environmental_losses/engine.py:131–149,199–222,240–256` classifies invalid root support as unavailable for the two root-dependent pathways and aggregate. The isolated helper's direct invalid-input guards were source-inspected; in this full-L4 reproducer its actual received depth is already0.
- `layer4_nutrients/runner.py:615–630` excludes unavailable root-dependent pathway debits; **698–710** applies the hard unsupported-root prescription/confidence gate; **831–844** records top-level missingness/health qualification.

This earns R51902 original-case credit. The current policy does **not** zero both depths indiscriminately: when only supported depth is invalid, the valid requested60cm remains in the receipt. That is exact candidate behavior, not a failure of the fix.

## Retained controls

| Current composition | Fresh actual result |
|---|---|
| Original W02/non-loam60cm root | Independent candidate-posterior storage **137.55→137.55mm**, FC/WP/saturation.295/.0966667/.44; actual loss VWC.2293 over60cm. The historical137.57 differs by.02mm after integration;83.30 substitution remains absent. |
| Shallow15cm root | 100/50/0mm overlap,20.60mm storage, VWC.1373 and correct weighted retention over15cm. |
| Requested120cm/profile60cm | Finite supported60/requested120, coverage.5. Correct supported arithmetic; exact.5 is outside chosen `<.50` policy. |
| Requested121cm/profile60cm | Actual pipeline coverage.4959; reduced water confidence.465 and downstream degradation persist. |
| Healthy deficient-evidence fixture | N163.1/P43.8 allowed; N/P/K/S confidence1/.9/.88/.5; health.75/statusok/reliability.5. K250 independently blocked by existing safety limit. |
| Nonconserved receipt+1mm closure | Previously allowed N/P block with `nonconserved_water_transition`; confidence/health/reliability.2 and hydrology quality reason retained. |
| Conserved health.2 | Confidence.667/.600/.587/.333; health.4/statusdegraded; reliability.333; degraded notes retain serialization. |
| Explicit support0/storage0, dry and declared20mm-drainage variants | Root-dependent losses unavailable/supportfalse in both; all recommendations blocked; confidence/health/reliability.1. No1mm-denominator104.4kg debit. **R47803 retained.** |
| No canonical water and no weather | SWB `UNAVAILABLE_MISSING_WATER_AND_WEATHER`, support0, no healthy default60cm; all recommendations blocked, health.1 with missing-hydrology and unsupported-root reasons. **R47804 retained.** |
| Prescription-note conversion | Declared notes and their nonempty warnings survive `dataclasses.asdict`. **8AE05 retained.** |

For partial availability, volatilization5.83 and runoff.73 remain available under their modeled input assumptions while root-dependent components are unavailable. Their6.56 subtotal and the budget's excluded-debit zeros do not establish complete physical loss. Numeric budget/audit projections lack their own per-component status, so consumers extracting them must carry the parent availability, SWB and quality context. No downstream consumer dropping that context was executed or alleged here.

## One adjacent group: finite supported domain, invalid requested extent

The only new adjacent group retains the finite60cm supported profile, valid storage/retention and a declared20mm drainage flux, while replacing the root object's requested-extent source (`root_depth_m`) with+Inf. It is an explicitly malformed injected input, not an output produced by the validated root factory.

The actual typed receipt preserves **supported60cm**, sanitizes **requested0cm**, sets **coverage0 and degradedTrue**. Full L4 evaluates the known supported domain: root60cm, VWC.2293, leaching**11.8kg/ha/AVAILABLE**, total modeled loss18.36 and available-N arithmetic remainder161.64. The11.8 debit matches `180*.58*20/(.295*600)` after rounding over the finite60cm support. The N budget records that11.8 debit.

N/P proposals163.1/43.8 remain allowed, with **serialized degraded-water notes**; N/P/K/S confidence becomes.667/.600/.587/.333, health.4/statusdegraded, reliability.333, `DEGRADED_WATER_BOUNDARY` and its penalty. Thus the invalid request is **not silently promoted to a healthy/full-root boundary**. Availability of the finite-domain calculation is distinct from confidence that this domain covers the requested crop root extent.

The governing source is `water_state.py:445–454`: an invalid requested extent sets the request/coverage qualification while retaining a valid supported scalar. L4's support predicate uses the preserved finite positive depth; the degraded flag follows through its soft qualification branch (`runner.py:723–737,856–867`). A blanket prescription block for every degraded field is not required by the cited plan, and this selected fixture supplies no independent evidence that the finite-domain estimate is numerically false. Therefore this is reported as an **observed partial-support policy and claim-scope qualification, not a new empirical defect**.

## Scientific limits and next acceptance work

The bounded reproduction establishes the stated R51902 fix and retained R47803/R47804 behavior. It does not certify whole F10/F11, all malformed combinations, receipt consumers outside this path, public operational authority or actuation. No second new adjacent group was opened.

Static limitations remain separate: the50% coverage threshold and1.5 confidence discount are policy heuristics rather than prospectively calibrated uncertainty; a finite-domain AVAILABLE flag must not be interpreted as full requested-root coverage; flattened loss/budget scalars need their enclosing qualification. Document those domains and test intended consumers before broader capability claims. Empirical calibration and multi-day drainage/replay are outside these13 compositions.

Normative references: master repair plan **F10:389–413**, stage4/dependenciesF03/F04/F05; tasks **ST04-F10-01..04/FA:546–571**; sequencing addendum line9 for limited slice acceptance. Supplied R3 scientific sections: **AB-DAT-005675–677**, **AB-DAT-007683–685**, **AB-AGR-008874–876**, **AB-AGR-010882–884**, **AB-ARC-006742–744**. These require truthful missingness, support and bounded degradation; they do not turn every degraded estimate over a known finite domain into an automatic hard prohibition.


---

# Specialist appendix: Concurrent resource ownership and driver admission

# Targeted ordinary-dispatch verification

Candidate `40315d95ff875914bd2f83cd1e75d88fdae859ff`; parent and comparison baseline `51932bfd7c588395b45e353d41f9519a0fe08bc4`.

**R51901 is repaired in its original ordinary-submit process lifecycle.** B is positively refused before transport as FAILED, retains no quota reservation or watchdog tracking, cannot stop the live A owner when polled, and does not block C after A's confirmed stop. All six retained admission, delayed-query and lease controls also pass. No additional failure was demonstrated in this bounded review.

## Fresh acceptance results

| Authored schedule | Current observation |
|---|---|
| Original R51901: A executes; fresh B submits; B polls while A runs; A positively cancels; fresh C submits | B stays FAILED with empty dispatcher/monitor tracking and no reservation. A becomes CANCELLED. C becomes EXECUTING. Exactly START(A), STOP(A), START(C); final active reservation belongs only to C. |
| Two OS workers both reach the idle-query barrier | One EXECUTING, one FAILED; exactly one START. The loser has no reservation or local dispatcher/monitor tracking. |
| Two idle replies held across the ownership/ACK barrier | One EXECUTING, one FAILED; exactly one START. The loser is cleaned up. |
| Original delayed idle: B samples ONLINE before A's application, then returns its sample after A's ACK and durable EXECUTING | A EXECUTING, B FAILED; exactly one START. |
| Original query exception after A executes | A EXECUTING, B FAILED; exactly one START. |
| A paused before production transport fence; B submits after a real 31.1-second lease wait | B EXECUTING, expired A FAILED; exactly one START from B. |
| A paused inside inert transport after production fence; B submits after a real 31.1-second lease wait | A EXECUTING, B FAILED; exactly one START from A. Entered transport remains protected. |

Each result is fresh against this candidate. The lifecycle uses three actual spawned OS workers; the delayed-idle, idle-barrier and lease schedules use two. The query-exception control uses independent dispatcher/driver instances in one process sharing the actual file quota store, matching its original authored setup. Both lease waits use real elapsed time, without clock injection or direct ledger/token mutation. C is submitted only after A's positive STOP; B receives no extra recovery poll after A stops.

## Mechanism and exact source

Paths below are relative to the pinned `source/` directory, under `services/agribrain/irrigation_runtime/`.

* `dispatcher.py:545–560` identifies a live different owner from the active command, inert controller identity, or durable resource record. The changed branch at **562–577** removes B from active events and safety tracking, releases quota, records/releases its shared reservation and returns FAILED before sending. The original lifecycle exercises this branch rather than only the later atomic-claim refusal.
* `dispatcher.py:594–617` retains the equivalent positively-unsent cleanup after resource-claim refusal. Both idle-admission barriers exercise this other refusal route.
* `safety.py:757–762` retains ADMITTED, unclaimed quota preparation. `dispatcher.py:948–968` invokes the atomic entry fence; `safety.py:1742–1800` validates/changes the current owner to DISPATCHING, and `safety.py:1662–1664` excludes a competing operation while transport is in flight. The real before/after-fence schedules verify that availability is restored without revoking entered transport by age alone.
* `dispatcher.py:1585–1686` handles public cancellation; **1662–1680** records the confirmed stopped owner and finalizes it. The original lifecycle checks the resulting command effects, tracking, quota ledger and later C acquisition together.

R3 mapping: section183 at `R3_current_scientific_sections.txt:484–488`; AB-EXE-002 at1110–1112, AB-EXE-003 at1114–1116, AB-EXE-004 at1118–1120; AB-ARC-008 at750–752. These are targeted execution-cycle, reconciliation, budget and concurrent-worker slices of F16–F19 / Stage6. Full package acceptance is undemonstrated by these schedules.

## Reproduction and provenance

Run from `/workspace/scratch/de6bc2428cec`:

```sh
PYTHONDONTWRITEBYTECODE=1 python repair-40315d9-review/protocol/run_originals.py
PYTHONDONTWRITEBYTECODE=1 python repair-40315d9-review/protocol/run_admission_lifecycle.py
PYTHONDONTWRITEBYTECODE=1 python repair-40315d9-review/protocol/run_fixed_ttl.py
PYTHONDONTWRITEBYTECODE=1 python repair-40315d9-review/protocol/run_transport_boundary.py
PYTHONDONTWRITEBYTECODE=1 python repair-40315d9-review/protocol/build_receipts.py
```

`run_adjacent.py`, `resource_claim_probe.py` and `resource_handoff_probe.py` provide local scheduling/driver helpers. Their optional historical standalone scenarios are outside the official command list and were not additional acceptance runs. No new adjacent group was added.

Raw outcomes are `original-results.json`, `admission-lifecycle-results.json`, `original-TTL-results.json` and `transport-boundary-results.json`. `timelines.json`/`.md` retain query request/sample/return times, actual production query timestamps, PIDs, application/ACK times, and durable claim/dispatch/execution times where recorded. The lifecycle exports snapshots before/after B's poll, after A's stop and after C's acquisition.

Every schedule checks five core production blobs against the exact candidate Git tree before running. `source-import-manifest.json` additionally verifies35 imported candidate files and records SHA256/Git blob identities and function ranges. This is import provenance, not statement coverage. `artifact-manifest.json` hashes lane artifacts.

The driver is an authored inert local file collaborator; the shared lock/store, dispatcher, actuator, safety and schemas are actual pinned production code. Observations establish software command effects and ledger lifecycle only. No broker, device transport, deployed service, physical water delivery, controller calibration or complete restart/recovery matrix was exercised. Repository tests, audit documents and historical results were not correctness evidence; production files and Git state were not edited.


---

# Specialist appendix: Public-store phase and quota contracts

# Root-owned public-store ownership regressions

Candidate40315d95ff875914bd2f83cd1e75d88fdae859ff, parent51932bfd7c588395b45e353d41f9519a0fe08bc4. The safety store production file is unchanged, while the dispatcher refusal branch changes. These root-owned direct-store/safety-monitor controls retain prior repaired contracts; the protocol lane separately executes the actual dispatcher lifecycle.

`probes.py` runs two existing regression groups and the existing stale-preparation lifecycle with an injected store clock. It uses actual public writers, private stores and actual SafetyMonitor cleanup; no JSON record is hand-edited. No driver, physical effect, service, network or repository test/audit correctness evidence is used. Store import manifests match candidate blobs; dispatcher is recorded as static-only in this lane. The reused older file is an authored harness identity, not old output accepted as proof.

Admission creates ADMITTED, claimedfalse, first_dispatched_atnull. Two4mm quota admissions both succeed. A's resource claim succeeds; B's refuses A. Cleanup of the positively unsent B removes only B's reservation and leaves A's claim/4mm exposure intact, without inventing stopped or settled delivery. A's remaining STARTING lease is deliberately only preparation; a later claim after100 injected seconds can expire it normally. A separate entered-DISPATCHING positive control remains protected beyond31seconds.

Repeated same-event claim returns the same token and preserves complete JSON/state bytes, generation, timestamps and phase in STARTING, DISPATCHING, SENDING and EXECUTING controls. Competitors remain refused under each control's stated inputs. SENDING is constructed by a public writer and EXECUTING uses an explicit live-executing flag; neither is asserted to be an ordinary dispatcher path observed here.

The stale STARTING retry returns the old token but does not renew its timestamp. Mandatory `transition_to_dispatching` rejects the expired preparation and clears its claim. A competitor can acquire; old A cannot revive ownership or enter transport afterward. Thus idempotence does not itself grant stale transport authority.

All controls pass without a new store finding. These are unchanged R47801/R47802 slice regressions, not full quota settlement/restart/corruption/multi-process hardware acceptance. Reproduce with `PYTHONDONTWRITEBYTECODE=1 python repair-40315d9-review/ownership/probes.py`; actual phase/ledger snapshots and source identities are retained.


---

# Specialist appendix: Normative readiness and actual serialization/API projection

# Root-owned validity, serialization and normative checks

Candidate40315d95ff875914bd2f83cd1e75d88fdae859ff, parent51932bfd7c588395b45e353d41f9519a0fe08bc4. This lane is root-owned, distinct from the three parallel specialist reviews. It performs bounded serialization and explicitly claimed direct loss-domain checks, not complete L4 inference or operational route execution.

The three normative documents match current committed blobs: master repair plan `08d378a65992de859369950599df198e64244f01`, sequencing addendum `40751038dc8760e91bc3ab115e30c5e28395953a`, task register `8a564647af7e588802537817159117b349ff606b`. There are52unique full-acceptance headers, all open: F01–F40 plus T01–T12. The68textual FA mentions include cross-references. Supplied R3PDF identity remains SHA256 `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`. Open register rows are not evidence52 implementations are absent, and these checks do not establish a completion percentage.

`probes.py` executes three bounded groups against51 verified imported production modules:

1. A hand-built typed nutrient artifact with a blocked prescription/note, root0, missing-driver diagnostics and explicit unavailable aggregate/pathway flags passes through actual `to_plain_data` and `artifact_to_run`. Its illustrative loss12 is fixture data, not a model estimate. Raw notes/support/availability survive. Public adapter yields degraded L4/confidence.1, no recommendations and BLOCKED authorization because L8 is absent. It does not expose every raw note/depth; compact projection is not automatically a defect.
2. Actual environmental-loss computation at explicit root0/drainage20 then actual raw serialization preserves root-unavailable aggregate/pathway flags, riskUNAVAILABLE and excluded-debit zero placeholders. This verifies declared fields survive rather than disappearing as dynamic attributes.
3. The directly claimed positive-infinity, NaN and booleanTrue root inputs each produce unavailable leaching/denitrification and unsupported aggregate through the actual environmental engine. A finite60cm control remains AVAILABLE/supported. This confirms the advertised scalar-domain guards independently of the canonical receipt sanitizer. No additional malformed-value search or public injection path is asserted.

All groups pass. The emitted field names remain individual `LossPathway.is_supported` and aggregate `EnvLossResult.is_root_supported`, both with `availability`. Numeric zero placeholders are interpreted with those fields; they are not measured physical zero. Partial aggregate losses/effectiveN must retain their qualifier wherever consumed. Empirical uncertainty, complete conservative N pools, actual fertilizer delivery and economic response remain wider target criteria, not automatically closed by these scalar contracts.

No repository tests/audit conclusions, production/Git edits, providers, services, HTTP endpoints, controller commands, radios, drones or hardware are used. Historical claim/audit files newly tracked in the commit are not correctness evidence. Reproduce with `PYTHONDONTWRITEBYTECODE=1 python repair-40315d9-review/ledger/probes.py`. `results.json`, plan identities and exact import receipts retain each fixture and scope. No new finding is inferred from an unexecuted UI/authorization/economic path.


---

# Specialist appendix: Active integration and plan traceability

# Platform regression continuity — 40315d95ff875914bd2f83cd1e75d88fdae859ff

**All seven established compositions and the sole added positive-infinite-root-support composition pass through the actual full standalone L8 pipeline.** The original dictionary permission fix, typed reason preservation, nonconservation block, unsupported-root block and missing-water/weather block retain their verified behavior. The new invalid-support case produces blocked fertilizer prescriptions, false downstream permission and preserved reasons through the exact normalizer, ranker, scheduler and full standalone L8.

This is bounded integration credit. It does not certify public-route promotion, canonical publication, actuation, diagnostic rate accuracy, every input shape or complete package acceptance. No new qualifier-loss finding is asserted.

## Candidate and executed source

Candidate `40315d95ff875914bd2f83cd1e75d88fdae859ff`, parent `51932bfd7c588395b45e353d41f9519a0fe08bc4`. Source is `../source`. `source-manifest.json` verifies151 unique referenced/imported files against the candidate Git tree;138 were actually imported by the probe. These counts are the lane's corpus, not whole-repository certification.

`eligibility_probes.py` executes the actual L3 engine, actual full `run_layer4_standalone`, ranker, direct scheduler and **full `run_layer8`**, including final invariants. `_normalize_nutrient_states` is extracted from the exact candidate `orchestrator_v2/runner.py` AST to avoid starting the entire orchestrator. The original probability0.8 regression uses exact current L4 gate AST selected semantically, with supported roots explicitly supplied; it does not depend on an old line number. Current full L4 and full L8 modules/dependencies are imported from the candidate.

The +Inf, zero-support and nonconserved cases explicitly replace contract fields on a freshly calculated L3 WaterState. They do not claim a normal solver or public request produced those invalid states. The missing canonical-water/weather case directly calls full L4 with `l3_decision=None,daily_weather=[]`. Network connections are blocked in the probe. No DB, provider, service, hardware, HTTP/public-route call, repository test/audit correctness evidence, or production/Git mutation occurs.

Python3.12.14 and installed dependency versions are recorded. The declared deployment image was not built or certified. `results.json` and `probe-stdout.txt` retain raw outputs; each composition has explicit regression assertions.

## Eight bounded compositions

| Composition | Observed full standalone L8 result |
|---|---|
| Actual full L4, nonconserved receipt with supported roots | N/P/K prescriptions remain false/LOW with `nonconserved_water_transition`; fertilizer schedules BLOCKED. False conservation and closure2mm survive normalization. |
| Actual full L4, explicit zero supported depth | Generated N/P/K prescriptions retain `unsupported_root_boundary`, confidence0.10 and BLOCKED schedules. |
| Original CEB03 probability0.8 exact-gate regression | The diagnostic120kg_N/ha candidate remains false/LOW, retains its nonconservation blocker and is BLOCKED. |
| Original8AE04 dictionary permission override | Existing true permission cannot override the blocked typed prescription; `regulatory_N_limit` and false permission survive through BLOCKED scheduling. |
| Typed allowed+blocked same-nutrient control | False wins; both regulatory and farmer prohibition reasons remain in blocked actions/schedules. |
| Dictionary existing-false control | False and `preexisting_farmer_prohibition` survive an allowed incoming typed prescription; fertilizer remains BLOCKED. |
| Missing canonical water and weather | Unavailable SWB/root0/mass-conserved false/closure0 remain qualified. L4 unsupported-root reason and SWB conservation restriction both reach normalized N/P/K and L8; all fertilizer schedules BLOCKED. |
| **Added: positive-infinite supported root depth** | L3 receipt normalizes support to0, coverage0 and degraded=true. Actual L4 then blocks N/P/K for unsupported roots; false permission/LOW confidence/blocker survive full standalone L8. |

All eight full L8 calls execute successfully. Fertilizer actions are present in every case and none receive CONFIRMED schedules. MONITOR remains allowed/CONFIRMED, so this is not a vacuous empty-output or universal-disable pass. Every output has `authorization_envelope=None`, consistent with standalone shadow output.

## Added +Inf case: exact behavior

The fixture sets `supported_root_depth_cm=float('inf')` on a fresh L3 WaterState. The actual typed boundary (`layer3_water/contracts/water_state.py:429–456`) checks numeric, nonboolean, finite, positive supported/requested depths. Its output contains supported depth0, requested depth60cm, support coverage0 and `is_degraded=true`. The original physical transition remains conserved with closure0; invalid root support is not relabeled as a fabricated conservation failure.

The actual full L4 output has:

- SWB supported depth0, degraded status;
- nutrient confidence/data-health ceilings0.10;
- generated N/P/K prescriptions disallowed with `unsupported_root_boundary`;
- root-dependent environmental pathways marked `UNAVAILABLE_UNSUPPORTED_ROOT`, not ordinary supported pathway results.

The exact normalizer carries false permission, the unsupported-root reason, the unchanged true conservation flag and closure0. The actual ranker emits false/LOW fertilizer candidates. Full L8 retains those blockers and BLOCKED schedules after its additional dosing, environmental, allocation, scheduling and invariant stages. Nonzero diagnostic rate fields remain in blocked actions; this is not an executed recommendation.

The L4 runner also independently checks a finite positive nonboolean support depth (`layer4_nutrients/runner.py:535–546`), and environmental loss calculations use corresponding finite-root checks (`environmental_losses/engine.py:130–147,239–255`). The executed +Inf composition reaches the canonical boundary sanitizer before the L4 check. This proves the repaired canonical integration path; it does not independently exercise every legacy receipt-less input shape.

## Blocker and conservation continuity

The actual L4 unsupported-root gate is before nonconservation (`layer4_nutrients/runner.py:697–728`), so the missing-water/weather output's local prescriptions need only carry the root blocker. Its SWB still retains false conservation and closure0. The exact normalizer independently derives `nonconserved_water_transition` and merges the local root reason, and full L8 preserves both.

For the separate supported-root nonconservation case, false conservation and closure2 remain intact. For the +Inf root-support case, conservation remains true and closure0 while permission remains false due to unsupported roots. This distinction is preserved in the actual outputs rather than collapsing separate admissibility dimensions into one flag.

The dictionary permission conjunction and typed matching-prescription merge remain active in `_normalize_nutrient_states` (`orchestrator_v2/runner.py:3435–3510`), called by current main's L8 input construction (`2860`). The ranker consumes permissions/reasons/conservation/confidence (`layer8_prescriptive/action_ranker.py:213–250`), scheduler preserves blocked cards (`scheduler.py:260–272`), and final L8 invariants reconcile late blockers (`invariants.py:286–336`). Full L8 (`runner.py:247–608`) was executed in all cases.

Environmental availability stays present in the complete L4 dataclass output. L4 budget assembly guards water-dependent loss debit on supported roots and AVAILABLE pathways (`layer4_nutrients/runner.py:616–630`). The verified N/P/K action consumers remain blocked. This lane does not turn a metadata omission in a narrower scalar projection into a new exposure claim without an executed consumer using it. It does not add a sulfur, arbitrary serialized-object, map, forecast or economics scenario.

## Public route and whole-orchestrator limit

Current public caller source authorizes the plot before backend execution (`src/app/api/agribrain/run/route.ts:829–860`, backend request502). Python `/v2/run` remains at `services/agribrain/app/main.py:3870–3871`. Current main uses the exact normalizer, and independent influence-manifest, tribunal, planning, live-weather and soil gates precede its L8 invocation (`orchestrator_v2/runner.py:2712–2736,2940–2964`). These are source traces. This lane does **not** invoke the HTTP route, entire orchestrator, canonical promotion/publication or an actuator. Fixture semantic hashes/audit grade isolate internal blocker preservation; they are not earned production authority.

Earlier checkpoint-receipt scope remains a static qualification, not a newly reproduced recovery or publication failure. No unchanged forecast/economic package is reopened in this lane.

## Normative identity and package mapping

`verify_metadata.py` compares candidate and parent trees with the supplied normative documents. All3 blobs remain exact and unchanged:

| Document | Blob |
|---|---|
| Deep Repair Plan | `08d378a65992de859369950599df198e64244f01` |
| Execution Sequencing Addendum | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| Work Packages / acceptance register | `8a564647af7e588802537817159117b349ff606b` |

The register contains52 unique full-acceptance rows,0checked: F01–F40 and T01–T12. Register state is not evidence52 implementations are defective or absent. `plan-results.json` contains literal master-card requirement sets, sequencing stages and supplied R3 line mappings for this lane's relevant packages.

Primary acceptance: F10 (`AB-AGR-008,AB-AGR-010,AB-DAT-007`) for the typed water boundary/degraded semantics, and F15 (`AB-DEC-003,AB-ECO-003,AB-EXE-001`) for preserved hard-action restrictions. F01/F02 concern authority/provenance; F03/F04/F05/F09 provide the surrounding flux, support and recovery contracts. The eight positive compositions support the original repairs and new finite-support boundary; they do not alone close every criterion in those packages.

## Reproduction

From this directory run `python eligibility_probes.py`, then `python verify_metadata.py`. These are authored offline review commands against `../source`; no repository tests/audits are used as correctness proof. Raw source/import receipts and outputs accompany the scripts. Advertised service/build commands were not executed.

# AgriBrain corrective verification and work-in-progress audit

**Reviewed candidate/main:** `51932bfd7c588395b45e353d41f9519a0fe08bc4`  
**First corrective commit/immediate parent:** `26d47b17dc419797964eeca7dcfda262d71b87da`  
**Comparison baseline:** `4788dac8c56e4ec8d2caecc53317fd5c5144f675`  
**Date:** 19 October 2026  
**Decision:** Continue planned implementation. Three original findings are repaired in their executed scope; R47801's original idle race is repaired but a separate positively-unsent refusal branch remains. Correct that branch before concurrent operational staging. One bounded malformed-support finding also remains.

## 1. Outcome

The remediation substantially improves both runtime phase identity and scientific missingness. Two idle workers no longer block each other merely because they hold quota reservations: exactly one executes and the other fails before transport. Same-event claims preserve phase/token/generation rather than resetting in-flight protection. Unsupported root losses are now explicitly unavailable and excluded from N-budget debits; missing water and weather no longer yield healthy default60 cm support.

The statement that **all** pre-transport refusals cleanly fail/release is broader than the final code. The second commit restored a different early refusal to STOP_REQUESTED when a fresh worker positively observes a foreign live owner. Actual process probes reproduce retained false stop intent/8 mm exposure and refusal of a later eligible submission after the real owner is positively stopped.

One additional malformed typed-boundary probe supplies positive-infinite root support. It passes the positive-depth classifier, produces apparently AVAILABLE root-dependent estimates and allows N/P prescriptions in standalone L4. This is a finite-domain admission weakness, not evidence that the validated solver naturally emits infinity or that an authenticated operational route can be bypassed.

There are **two deduplicated follow-ups**: R51901 is residual R47801 runtime scope; R51902 is the single new finite-support admission case. Neither justifies describing the repaired zero/missing-root cases or original idle race as still broken.

## 2. Claim disposition

| Claim | Independent disposition | Evidence and qualification |
|---|---|---|
| **R47801 — admission/preparation/transport phases** | **Original race repaired; claim incomplete across entry paths** | Direct-store admissions are ADMITTED/claimedfalse/first_dispatched_atnull. Both ordinary idle barriers give one EXECUTING, one FAILED, one START. But the positively foreign-running preflight branch still leaves an unsent B STOP_REQUESTED and blocks later C (R51901). |
| **R47802 — idempotent same-event claim** | **Repaired in checked public-store contract** | STARTING/DISPATCHING/SENDING/EXECUTING repeats preserve complete store bytes, token/generation/timestamps/phase. Real transport retains its lease-age protection. Synthetic SENDING/EXECUTING fixtures are not ordinary dispatcher reachability evidence. |
| **R47803 — unsupported root losses/debits** | **Original zero-root dry/drainage counterexamples repaired** | Leaching/denitrification are UNAVAILABLE_UNSUPPORTED_ROOT, `is_supported=false`, riskUNAVAILABLE; the104.4 kg/ha debit is gone. Aggregate flags/notes serialize. Numeric zeros are qualified excluded-debit placeholders. Nonfinite positive support is separate R51902. |
| **R47804 — missing canonical water and weather** | **Original standalone omission counterexample repaired** | SWB statusUNAVAILABLE_MISSING_WATER_AND_WEATHER/support0/massfalse, missing-driver reasons, all prescriptions blocked and health/confidence≤.1. Full standalone L8 preserves both unsupported-root and conservation restrictions. |

The actual aggregate field is `EnvLossResult.is_root_supported`; individual pathways use `LossPathway.is_supported`. Both have `availability`. This small naming qualification prevents consumers from looking for a nonexistent aggregate field.

## 3. Source identity, method and exclusions

GitHub metadata verifies `4788dac→26d47b1→51932bf`. Main was observed at51932bf at the beginning and again before delivery preparation. The candidate recursive tree has4,082 entries and is not truncated; no AGENTS.md was found. Across the pair, four production files change: dispatcher, safety store, environmental-loss engine and nutrient runner. Two previous review documents and one repository test are also added/changed; those were not used as correctness proof.

The private reconstruction contains **732 exact production/configuration files**, each matched to the candidate Git blob; all four changed production files compile without imports. This is a staged/import corpus, not a claim of dynamic coverage for every repository function. Import manifests distinguish executed production files and static references. Lane import counts overlap and must not be summed as total coverage.

Six review streams were assigned. Three agent-authored final specialist reports completed; decision/protocol probes and results also completed before the unfinished final-summary stage. An agent usage-limit interruption prevented all six independent final reports from finishing. The root reviewer completed the missing narratives, source/timeline receipts and bounded serialization lane, and reruns all declared commands in a separate workspace. This report does **not** claim six independently completed final reviews.

Evidence comprises actual production functions, authored offline probes, private inert controller/store collaborators, explicit scientific fixtures, source identities and normative documents. Repository tests, audit conclusions, scratch probe claims supplied by others and the user's reported516-test count were not adopted as independent verification. No production/Git edits, services, external providers, real brokers, controllers, radios, drones or physical hardware were operated.

Actual OS workers are used for protocol schedules; direct-store lease controls inject the clock and are labeled separately. Negative root fixtures explicitly replace production dataclass fields and declare drainage; they are not naturally generated solver failures. Full standalone L4/L8 execute, while the exact normalizer function is extracted unchanged to avoid starting the entire orchestrator. The public response adapter is tested in isolation, not through HTTP authorization or publication.

## 4. R51901 — positively unsent foreign-owner refusal still leaves stop intent

**P1 availability and lifecycle consistency; residual R47801, ordinary public-submit reproduction.**

The original two-idle-workers failure is corrected. The remaining case starts a different way: A is already executing before a fresh B submits. Preflight positively identifies A as the foreign active operation. B never enters transport, but final51932bf moves it into STOP_REQUESTED and retains local/durable exposure.

| Step in the actual three-process lifecycle | Observed effect and accounting |
|---|---|
| A submits normally | A EXECUTING; one START(A), active owner and reservation. |
| Fresh B submits while A runs | B STOP_REQUESTED, no START(B), local dispatcher/watchdog track B; B reservation8 mm. |
| B polls once while A is still live | A remains executing; no foreign-owner STOP. B remains STOP_REQUESTED/tracked. |
| A's owner cancels A | Positive STOP(A), A CANCELLED and its tracking cleared; stopped receipt retained. |
| Fresh C submits after that positive stop | C FAILED; B's STOP_REQUESTED reservation still blocks the resource. No START(C). |

Final controller effects are **START(A),STOP(A)**; all three workers exit0. B still retains8 mm. C's own unsent claim failure cleans up correctly. No B poll is made after A stops, so the result is a selected lifecycle stall, not a proof of permanent deadlock or absence of every periodic recovery mechanism.

The two-commit sequence matters. `26d47b1` used FAILED/tracking/quota cleanup for the positively foreign-running refusal. **`51932bf` reverted that branch to STOP_REQUESTED** at [irrigation_runtime/dispatcher.py:L561-L570](https://github.com/webClone/AgriWise/blob/51932bfd7c588395b45e353d41f9519a0fe08bc4/services/agribrain/irrigation_runtime/dispatcher.py#L561-L570). The later resource-claim failure still performs unsent cleanup at [irrigation_runtime/dispatcher.py:L597-L609](https://github.com/webClone/AgriWise/blob/51932bfd7c588395b45e353d41f9519a0fe08bc4/services/agribrain/irrigation_runtime/dispatcher.py#L597-L609). Protected foreign STOP_REQUESTED rows then block resource admission ([irrigation_runtime/safety.py:L1645-L1668](https://github.com/webClone/AgriWise/blob/51932bfd7c588395b45e353d41f9519a0fe08bc4/services/agribrain/irrigation_runtime/safety.py#L1645-L1668)).

Retaining exposure is correct for a possibly applied command or unconfirmed STOP. Here the event is refused before transport with positively identified foreign ownership. Its phase must preserve that distinction; a reservation is not evidence B irrigated or needs its own physical cutoff.

**Repair:** centralize positively-unsent refusal/defer cleanup across both early branches. Remove B's execution/watchdog/resource/quota obligations without altering A, and retain an audit record of the refusal. Keep ambiguous sent-command ownership and conservative stop accounting intact.

**Acceptance:** replay A-start→B-refusal→B-poll-with-A-live→positive-A-stop→C-submit. B must have truthful unsent status/accounting, B polling must not stop A, and eligible C must acquire and execute ordinarily after A relinquishes the resource. Verify durable phase/receipts, local monitoring, quota and resource tokens together. Retain all simultaneous-idle, delayed-query, real before-fence expiry and real after-fence in-flight one-START controls.

## 5. R51902 — nonfinite root support is accepted as a healthy domain

**P2 numeric/physical boundary admission; malformed injected typed record, operational reachability unestablished.**

The sole added scientific case replaces supported_root_depth_cm with **positive infinity** on an otherwise finite actual WaterState and explicitly declares20 mm drainage. It does not alter the L4/loss algorithms. The receipt caps coverage at1 and does not degrade on the root value ([layer3_water/contracts/water_state.py:L429-L440](https://github.com/webClone/AgriWise/blob/51932bfd7c588395b45e353d41f9519a0fe08bc4/services/agribrain/layer3_water/contracts/water_state.py#L429-L440)). L4 checks only `depth>0` ([layer4_nutrients/runner.py:L524-L538](https://github.com/webClone/AgriWise/blob/51932bfd7c588395b45e353d41f9519a0fe08bc4/services/agribrain/layer4_nutrients/runner.py#L524-L538)), so infinity is classified as supported.

The actual loss call receives rootInf/VWC0. Root-dependent leaching becomes0/LOW, denitrification0/LOW, bothAVAILABLE/is_supportedtrue, aggregateAVAILABLE/is_root_supportedtrue, with all-pathways-acceptable notes. Full standalone L4 emits N163.1/P43.8kg/ha **allowed**, health.75/statusok. K remains independently blocked by existing constraints. The result JSON converts infinity to the stringInfinity only after production execution, to retain standards-compliant evidence JSON.

This is separate from repaired R47803/R47804: zero and missing support now produce correct unavailability and blocks. The new weakness is accepting a malformed nonfinite positive value as a finite physical support domain. No validated factory-generated infinite profile, public endpoint injection, canonical operational promotion or hardware action was demonstrated.

**Repair:** validate root/support values as strict finite, non-boolean real values before coverage, VWC or loss calculation. Reject malformed values or return explicit unavailable/degraded output; do not cap infinity into apparently complete support. Bind supported depth to actual finite profile/requested support under the declared contract.

**Acceptance:** this exact fixture must reject or carry unsupported/invalid-domain qualification, with no healthy AVAILABLE root-loss interpretation and no allowed fertilizer prescriptions. Keep finite full/shallow/partial support, explicitzero, absentwater, nonconserved and valid-zero-drainage controls. Broader malformed-input matrices and outer authorization remain separate evidence requirements.

## 6. Preserved scientific and integration repairs

The root0/declared20 mm case now emits leaching/denitrificationUNAVAILABLE with zero excluded-debit placeholders. N-budget leaching is0 rather than104.4. All prescriptions remain blocked and health/confidence≤.1. The new raw availability fields survive the actual serializer, alongside declared prescription notes. These are substantive repairs and are credited accordingly.

Partial supported volatilization/runoff still contribute to numeric loss totals and effectiveN. In the matched L4 fixture total6.56/effectiveN173.44/overallLOW coexist with aggregateunavailability and explicit explanatory notes. Those numeric fields must retain their partial-model qualifier wherever consumed; their existence alone is not a fresh reproduced defect now that the missing-domain distinction is carried. No empirical calibration or full physical/economic total is certified.

The missingcanonical/weather case now carries SWBunavailability/root0/massfalse and both hydrology-missing flags. Local L4 prioritizes unsupportedroot; the exact normalizer independently preserves massfalse and adds `nonconserved_water_transition`. All seven full standalone L8 compositions keep N/P/K fertilizer candidates false/LOW/BLOCKED, while MONITOR remains allowed/CONFIRMED. Standalone outputs have no authorization envelope, consistent with shadow/research scope.

Hydrology production code is unchanged from4788dac:34 staged water Python blobs and89 imported production modules match both trees. All eight retained zero-capacity, independent soil/surface/whole ledger, ET partition and round-trip controls pass. This is bounded regression credit, not full water-model acceptance. The finite non-loam L4 control still integrates137.55mm and weighted.295/.0966667/.44, retaining shallow/partial support behavior and notes serialization.

The isolated real API adapter returns degraded L4/confidence.1, empty recommendations and BLOCKED authorization for the typed fixture lacking L8. It deliberately summarizes the raw artifact and need not expose every note/root field. This projection is not automatically another defect; no HTTP route or user publication path is tested.

## 7. Normative plan and monograph alignment

The master repair plan, sequencing addendum and work register are byte-identical to current committed blobs: `08d378a65992de859369950599df198e64244f01`, `40751038dc8760e91bc3ab115e30c5e28395953a`, `8a564647af7e588802537817159117b349ff606b`. The supplied R3PDF is SHA256 `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; its scientific sections/requirement extraction accompany the bundle.

| Plan work | R3 relationship and current evidence |
|---|---|
| F16–F18, Stage6 | Admission/ownership/quota and uncertain-command reconciliation. R47802 earns scoped acceptance credit; R51901 still prevents blanket concurrent-dispatch closure. Literal card requirements remain in the normative package map, including AB-EXE/AB-DEC/AB-ARC execution identities. |
| F10/F11, Stage4 | Literal F10 requirements AB-AGR-008/010,AB-DAT-007; F11 AB-AGR-010/008. Explicit zero/missing support and excluded loss debit are repaired. Whole conservative N pools and actual application/demand semantics remain wider acceptance. |
| F01/F04, Stages1/2 | Numeric and finite geometry/support admission are prerequisites for truthful domain qualification. R51902 belongs here and at the consuming F10 boundary. |
| F15/F38/F40 | Hard restriction and consumer/degraded publication continuity; seven actual L8 compositions support the checked slices. These thematic consumers do not imply all package criteria are complete. |
| T05 and wider model work | Empirical response, uncertainty and economics remain separate from policy caps and typed missingness. No observed causal agronomic/economic value is inferred from finite scalars. |

F/T package IDs are not monograph scientific requirement IDs. The register has **52 unique full-acceptance headers: F01–F40 plus T01–T12, all open,0 checked**. Its68 textual mentions include cross-references. Open sign-off does not mean52 implementations are missing or broken, and these repairs do not establish a completion percentage.

## 8. Next implementation steps and readiness

Continue the existing plan now. Fix R51901 before operational concurrent resource staging; scientific finite-domain hardening can proceed independently. Objective-qualified Omega/world-model research can continue with eligible supported inputs or explicitly prior/scenario/shadow outputs. The entire research program need not wait for unrelated physical commissioning, and this review does not authorize field dispatch.

| Order | Concrete change | Evidence required for the next review |
|---|---|---|
|1 — runtime | One positively-unsent refusal routine for the foreign-running and failed-claim branches; retain other-owner and uncertain-transport guards. | Exact A/B/C lifecycle progresses without phantom B exposure or a STOP of A; original one-START schedules preserved. |
|2 — scientific boundary, parallel | Strict finite root/support admission before coverage/classification/loss arithmetic. | +Inf fixture rejects/degrades; all repaired zero/missing and supported controls remain correct. |
|3 — integration | Preserve typed availability/notes/permissions through actual consumers that show numerical totals or budgets. | Explicitly qualified partial aggregates; no unsupported scalar promoted as complete supported inference. Do not re-open every unchanged consumer without evidence. |
|4 — plan acceptance | Complete remaining package-specific integrated, persistence, scientific validation and hardware criteria where required. | Attach evidence to each FA milestone; distinguish software simulation, research evaluation and field commissioning. |

Do not restart an unbounded whole-repository defect hunt after each patch. Re-run the original repaired failures, these two follow-ups and the bounded adjacent controls. Broaden only for changed code, a failed control or an unresolved prerequisite. The original2,564–4,540hour program estimate is not a fresh remaining-effort calculation.

## 9. Reproduction and deliverables

The accompanying machine-readable register records four claim dispositions and two qualified follow-ups. The evidence ZIP contains authored scripts, actual results, normative documents/extraction, source hashes, timelines, reconstruction layout and a read-only Git-object materializer. Production source copies, repository tests/audits and private generated stores are excluded.

Eleven commands are replayed from a separate candidate-exact source layout. Zero exit means declared observations—including the two counterexamples—reproduced; it is not a repository-test count. The Git-object materializer itself is syntax/layout checked rather than executed against a separate complete Git checkout. Source bytes are verified before and after replay; the final bundle has per-file hashes and ZIP integrity checks. Six appendices preserve narrower methods, limits and source references.


---

# Specialist appendix: Water conservation and compartments

# Unchanged hydrology regression controls — 51932bf

Candidate: `51932bfd7c588395b45e353d41f9519a0fe08bc4`. Comparison baseline: `4788dac8c56e4ec8d2caecc53317fd5c5144f675`.

**All eight retained acceptance checks pass.** The zero-capacity repair, soil/surface/whole-system ledgers, full-pipeline ET component publication and ponding round-trip controls remain intact. No exploratory cases or new finding were added. This is an unchanged-control regression check, not full water-model or master-plan acceptance.

## Source and execution receipts

All34 staged production Python files under `services/agribrain/layer3_water/` are byte-identical to the baseline and verified against the candidate tree (`unchanged-water-manifest.json`). All89 production modules imported by the probes are also unchanged from baseline and match the candidate tree (`source-manifest.json`, `dependency-comparison.json`). No reused production dependency copy was needed. Imported-file verification is not all-function or branch coverage.

The authored prior harness was adapted only for the candidate identity/path and regenerated every result. It calls the actual soil/root factories, layered transition, complete `WaterIntelligenceEngine.execute_pipeline`, typed contracts and production soil checkpoint deserializer. There are no harness errors. No repository tests/audits, old result files, hardware, network, production services, source edits or Git mutations were used as correctness evidence. Both worldline aliases point to a private lane path before hydration.

Official command from the workspace root:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-51932bf-review/trajectory/probes.py
```

`results.json` contains complete fresh states/receipts, independent residuals and the eight assertions. Normative scope remains master-plan F03/F04/F07 and R3 AB-AGR-003/004/005/006, AB-DAT-005/007; local document hashes are recorded separately.

## Retained results

| Control | Candidate result |
|---|---|
| No harness errors | Pass |
| W01 conservation | Direct original impedance fixture closure0 mm; full-pipeline closure.02 mm, within .05 tolerance; dry/permeable controls exact0 |
| Ponding round-trip | Warm/cold states and receipts exactly equal; cumulative whole-system residual0 |
| CEB02 direct compartment ledger | T8 + soil E0 + pond E7 = ETA15; soil and whole residuals0 |
| CEB02 complete water pipeline | T.59 + soil E5.71 + pond E3.50 = ETA9.80; published components match receipt; soil/whole residuals.01/.01 mm |
| Original8AE02 pond5/capacity0 | Constructor and direct solver raise ValueError; production hydration returns None |
| Legitimate0/0 reservoir | Constructor, direct solver and hydration accept |
| Supported5/12 reservoir | Constructor, direct solver and hydration accept |

The direct invalid-reservoir fixture intentionally supplies an inert legacy-shaped object to reach the lower solver guard independently of constructor rejection. It is not claimed to pass current typed construction. Original negative/nonfinite/boolean flux and negative-pond controls remain rejected in the saved validation results. No invalid pond was executed as an ordinary current full-pipeline state.

Current source references, all under `services/agribrain/` at the candidate SHA:

- Capacity admission: `layer3_water/contracts/water_state.py:35–50`; `layer3_water/soil/layered_water_balance.py:139–151`; hydration `layer3_decision/runner.py:857–877`.
- Separate soil/pond evaporation and whole-system receipt: `layer3_water/soil/layered_water_balance.py:226–235,314–345`; component semantics `layer3_water/contracts/water_state.py:315–334`.
- Actual full-pipeline propagation: `layer3_water/runner.py:306–336`.

The .01/.02 mm serialization residuals are within tolerance and are not described as exact zero. No empirical calibration claim follows from these arithmetic controls.

## Typed root support and serialization boundary

The retained full-pipeline fixture requests a.60m root over a60cm profile. Its current typed root state carries storage115.21mm, supported depth60cm, depth-weighted FC.30/WP.15/saturation.45, TAW90mm and depletion64.79mm. The normal factory construction and JSON→production-deserializer round-trip continue to execute successfully. They do not certify arbitrary unsupported depths or parameter precision beyond these fixtures.

Static bridge only: the unchanged soil helper integrates actual depth overlap (`layer3_water/contracts/water_state.py:99–150`), the factory serializes the actual profile and infiltration/evaporation state (`layer3_water/contracts/state_factory.py:167–182`), and `WaterState.to_layer4_boundary_receipt` publishes typed root storage/retention/support plus conservation status (`water_state.py:413–473`). Current L4 reads those typed coordinates and uses root-support availability (`layer4_nutrients/runner.py:192–207,524–550`). The bridge-file blobs are verified in the source manifest; this lane does **not** execute the changed L4 nutrient path. Its actual behavior is reviewed by the separate L4 lane.

Disposition: retain credit for the repaired originals on unchanged production bytes and fresh executions. There is no new hydrology finding in this scoped pass. The result does not close all water, root-support, nutrient integration, trajectory or R3 acceptance criteria.


---

# Specialist appendix: Typed L3 to L4 boundary and nutrient qualification

# Full L4 scientific-boundary corrective verification

Candidate `51932bfd7c588395b45e353d41f9519a0fe08bc4`; reviewed baseline `4788dac8c56e4ec8d2caecc53317fd5c5144f675` through26d47b1.

**R47803 and R47804's original fixtures are repaired.** Unsupported root-zone leaching/denitrification now carry explicit unavailability, are excluded from N-budget loss debits, and retain prescription blocks. Missing canonical water plus missing weather no longer yields healthy default60cm support. One additional malformed positive-infinite support fixture remains accepted as healthy support.

The reviewer completed the authored production probes/results and sent its findings; root completed this narrative after the unfinished final-summary stage. All twelve cases are included in the portable replay. No repository tests, historical audit assertions or old result files are correctness proof.

## Executed functions and fixture boundaries

`probes.py` executes the actual water engine/factories, actual typed L3→L4 receipt, complete standalone L4 and actual environmental-loss engine. A temporary argument observer delegates unchanged. There are113 imported candidate files, Git-blob verified before import and after execution. No production function body/AST is rewritten. Unsupported/nonconserved/low-health/infinite-support cases explicitly replace fields on actual dataclasses; they are contract-admission cases, not naturally emitted solver states. The absence case passes no canonical state and empty weather, not a comparison state secretly supplied to L4.

All eleven earlier compositions run again, plus **one** new adjacent case: positive-infinite supported depth with explicitly declared20mm drainage. Output JSON represents nonfinite numbers as strings only after the actual calls, with `allow_nan=False`; the physical calls receive actual floating-point infinity. Standalone research API authority applies; no authenticated HTTP/full-orchestrator permission bypass, service or hardware operation is asserted.

Run `PYTHONDONTWRITEBYTECODE=1 python repair-51932bf-review/decision/probes.py`.

## Repaired R47803: unavailable pathways no longer debit unsupported root losses

The actual explicit root0/storage0 dry case and root0/declared20mm drainage case both return:

| Field | Current value |
|---|---|
| Leaching availability / support / risk | `UNAVAILABLE_UNSUPPORTED_ROOT` / false / `UNAVAILABLE` |
| Denitrification availability / support / risk | `UNAVAILABLE_UNSUPPORTED_ROOT` / false / `UNAVAILABLE` |
| Water-dependent pathway numeric loss |0 placeholder, explicitly qualified by the fields above |
| Aggregate availability / root support | `UNAVAILABLE_UNSUPPORTED_ROOT` / false |
| Aggregate notes | Root boundary unsupported; water-dependent pathways unavailable and excluded from debit |
| N-budget leaching / denitrification debit |0 /0 |
| Prescriptions | All blocked with `unsupported_root_boundary` |
| State confidence, health and reliability |≤.1, degraded |

The old104.4kg/ha leaching debit is absent. The runner now requires supported root and pathway availabilityAVAILABLE before debiting those quantities (`layer4_nutrients/runner.py:602–613`). The zero in this typed contract is an excluded-debit placeholder, **not evidence of a measured physical zero**. The code now carries the distinction that the preceding review required.

Independent volatilization/runoff estimates still contribute to the partial numerical aggregate. In the matched full-L4 fixture they total6.56kg/ha, with effectiveN173.44 and overallLOW. These values now coexist with explicit aggregate unavailability and an explanatory note, so this review does not re-label their mere existence as another R47803 failure. Consumers must retain the qualifier and describe totals/effectiveN as partial modeled quantities rather than complete supported physical totals. This is ongoing contract/economic-calibration scope, not a newly reproduced promotion bypass.

Exact types differ slightly from the prose claim: individual `LossPathway` uses `availability` and `is_supported`; aggregate `EnvLossResult` uses `availability` and **`is_root_supported`** (`environmental_losses/engine.py:37–70`). New unsupported gates are at129–151,194–217 and234–249.

## Repaired R47804: absent water/weather is explicitly unavailable

With `l3_decision=None,daily_weather=[]`, SWB now has status`UNAVAILABLE_MISSING_WATER_AND_WEATHER`, supporteddepth0, degradedtrue, uncertainty2.5 and mass_conservedfalse. All N/P/K prescriptions are blocked; all nutrient confidence and health/ceiling/reliability are.1. Quality includes both `MISSING_HYDROLOGY_AND_WEATHER` and `UNSUPPORTED_ROOT_BOUNDARY`. Notes serialize. The default-positive support path from the prior candidate is gone in this exact fixture.

The unsupported gate now precedes nonconservation at the L4 level, so this combined-invalid case primarily uses the unsupported reason. The platform composition independently confirms that the actual normalizer also reads SWBmass_conservedfalse and adds the conservation reason downstream. The local branch order is not by itself evidence that conservation restrictions disappeared.

## Retained valid and restriction controls

The non-loam60cm supported fixture independently integrates137.55mm posterior storage and weighted FC/WP/saturation.295/.0966667/.44. The old83.30mm substitution does not recur. Shallow15cm overlap remains20.60mm. Requested120/profile60cm gives coverage.5; requested121cm gives.4959 and degradation. These are actual overlap/propagation checks, not calibration of a chosen50% threshold.

The healthy deficient-evidence control retains allowed N163.1/P43.8kg/ha; its K rate is independently blocked by the existing safety limit. Nonconserved supported water keeps all prescriptions blocked with confidence/health≤.2. Conserved low-health water retains degraded status/health.4 and reduced state confidence. Declared prescription notes equal nonempty `asdict` values. The inherited-uncertainty fixture still changes the receipt uncertainty while generic L4 quality uses its policy discount; this older propagation limit is retained as a qualification, not a new finding or empirical miscalibration claim.

## R51902: positive infinity is classified as supported

**P2 finite-domain admission defect; malformed typed fixture, operational exposure unestablished.**

The sole new case replaces only supported_root_depth_cm with positive infinity on an otherwise finite actual water state and explicitly declares20mm drainage. `to_layer4_boundary_receipt` computes coverage`min(1,Inf/requested)=1`; its receipt is not degraded on that basis (`layer3_water/contracts/water_state.py:429–440`). L4 tests only `raw_supp_depth is not None and raw_supp_depth>0` (`layer4_nutrients/runner.py:524–538`), so infinity passes.

Actual environmental arguments then contain rootInf and VWC0. Storage divided by infinite depth becomes0; the leaching denominator is infinite, giving leaching0/LOW. New `root_depth_cm<=0` checks do not catch infinity, so leaching and denitrification are markedAVAILABLE/is_supportedtrue, aggregateavailabilityAVAILABLE/is_root_supportedtrue and notes say all pathways acceptable. Full L4 returns allowed N163.1/P43.8, health.75/statusok, with no unsupported-root restriction. K remains independently blocked.

This does not undo the correctly repaired zero/missing cases. It demonstrates that the consumer and receipt classify a malformed nonfinite support value as a healthy scientific domain. The validated water factory was not shown to emit it, and no JSON endpoint/public-route ingestion was executed. It is an actual typed contract-boundary hardening gap, not a field recommendation or calibrated loss result.

**Correction:** use strict finite-real, non-boolean root/support admission before coverage/VWC or loss arithmetic. Reject malformed support or convert it to typed unavailable/degraded output, preserving downstream blockers; do not clamp infinite depth into apparently complete coverage. Also enforce supported depth against finite actual profile/requested support under the declared contract. Avoid silently converting invalid input into measured dry conditions.

**Acceptance:** this exact +Inf fixture must reject or emit unavailable supported-domain diagnostics, no healthyAVAILABLE root-dependent losses, and no allowed fertilizer prescriptions. Retain finite supported, shallow/partial, explicitzero, missingcanonical, nonconserved and valid-zero-drainage controls. Broader malformed-input matrices and outer operational reachability require their own evidence; none is implied here.

Normative basis: F01 numeric admission and F04 geometry/hydraulic support; F10 boundary missing-support propagation and F11 conservative N-pool meaning. Literal F10/F11 scientific IDs are AB-AGR-008,AB-AGR-010,AB-DAT-007 from the master cards. R3 AB-DAT-005/007 and AB-ARC-006 additionally motivate typed validity/provenance; these thematic references do not change package identities or close full acceptance.


---

# Specialist appendix: Concurrent resource ownership and driver admission

# Ordinary dispatcher and transport verification

Candidate `51932bfd7c588395b45e353d41f9519a0fe08bc4`, immediate parent `26d47b17dc419797964eeca7dcfda262d71b87da`, patch baseline `4788dac8c56e4ec8d2caecc53317fd5c5144f675`.

**R47801's original simultaneous-idle mutual refusal is repaired. One sequential foreign-owner preflight branch still preserves false stop intent for an unsent event and blocks a later ordinary submission.** Genuine in-flight transport remains protected in the original real-time lease schedule.

This lane's authored schedules/results were produced before its reviewer was interrupted by an agent usage limit. The root reviewer inspected the scripts and output, completed this narrative/source receipts, and includes all commands in the separate-workspace replay. It is not presented as an independently completed sixth final review. No production code was edited.

## Method

The probes import the exact candidate's dispatcher, actuator, safety store and schema. A local inert controller records effects in private files. Workers are actual `multiprocessing.spawn` OS processes. No MQTT, Modbus, external service, physical actuator or field delivery operates. `source-import-manifest.json` checks35 imported production files against the candidate tree. Counts are import evidence, not statement coverage.

Official commands, in order:

1. `python repair-51932bf-review/protocol/run_originals.py`
2. `python repair-51932bf-review/protocol/run_fixed_ttl.py`
3. `python repair-51932bf-review/protocol/run_transport_boundary.py`
4. `python repair-51932bf-review/protocol/run_admission_lifecycle.py`
5. `python repair-51932bf-review/protocol/build_receipts.py`

The before/after-fence schedules each wait a real31.1seconds. The others use explicit process barriers. Results include PIDs, queries, dispatch receipts, resource tokens, ledger phases and effects. Exit zero establishes that observations reproduced, including the residual counterexample; it is not a production-test pass count. Repository tests/audits are not correctness evidence.

## Repaired controls

| Schedule | Current observation |
|---|---|
| Both workers sample idle before resource admission | Exactly one START; one owner EXECUTING and one unsent contender FAILED. The old both-STOP_REQUESTED/zero-START result no longer occurs. |
| Idle replies held across ownership/ACK barrier | Exactly one START; unsent competitor FAILED, without superseding the owner. |
| Delayed idle sampled before another successful execution | Exactly one START; owner remains executing. |
| Query failure after existing execution | Exactly one START; no competing dispatch is certified from failed query. |
| A pauses before the mandatory transport-entry fence; B waits beyond preparation lease | Exactly one START from B; expired A fails. Preparation remains expirable. |
| A pauses inside inert send after the production fence; B waits31.1seconds and samples idle | Exactly one START from A; B is FAILED. A remains the consistent reservation/resource/active-command owner. Entered transport is not revoked by age alone. |

The new `ADMITTED` quota reservation and local `QUEUED` preparation no longer pretend to be transport. The ordinary claim-failure path cleans up an unsent loser (`dispatcher.py:483–486,589–615`). The atomic current-token `transition_to_dispatching` remains immediately before transport; the positive in-flight schedule is retained rather than weakened to cure availability.

## Residual R51901: already-running foreign owner takes a different refusal branch

**P1 availability/lifecycle consistency; public ordinary-submit path reproduced.** This is residual R47801 scope, not a new duplicate-START or physical dosing finding.

One bounded adjacent lifecycle uses three actual OS workers and public `submit_event`, `check_execution_status`, and `cancel_event`:

1. A submits and executes normally. Its START is the only effect.
2. Fresh B submits to the same resource after A is confirmed running. Live query and durable identity positively identify A as the foreign owner. B never enters transport, but returns STOP_REQUESTED. Its local dispatcher and monitor both track B; its8mm reservation remains STOP_REQUESTED.
3. B is polled once while A is still live. A remains running: no foreign-owner STOP is issued. B remains tracked with its reservation.
4. A's own worker cancels A, and the inert controller positively records STOP. A is CANCELLED, its active/watchdog tracking is cleared, and its stopped receipt is retained.
5. Fresh C submits after the positive A stop. It returns FAILED. The remaining B STOP_REQUESTED claim blocks resource admission. B still retains8mm; C does not START.

The final effects are precisely **START(A),STOP(A)**. C does not execute. All three worker processes exit0. B is not polled again after A's stop; therefore this establishes the selected ordinary lifecycle stall and remaining false exposure, not permanent deadlock or absence of every external recovery path. It also does not criticize conservative exposure retention for a genuinely ambiguous sent operation: the branch refused B before transport.

The cause is visible in the two-commit sequence. `26d47b1` changed the foreign-running preflight refusal to FAILED plus tracking/quota cleanup. **`51932bf` reverted that branch** to STOP_REQUESTED plus store update. The final code is `irrigation_runtime/dispatcher.py:561–570`. Its claim-resource refusal branch still performs the correct unsent cleanup at597–609, so concurrent-idle success alone does not cover the earlier foreign-running branch. Store `claim_resource` protects foreign STOP_REQUESTED rows at `irrigation_runtime/safety.py:1645–1668`.

## Required correction and exit evidence

Use one authoritative positively-unsent refusal operation for both branches, distinguishing caller-local delivery uncertainty from a confirmed different owner. B's admission must be failed/deferred with appropriate tracking/quota/resource cleanup and an audit receipt, without stopping A. Do not release exposure for operations that actually entered transport or for unresolved ACK/STOP outcomes.

Repeat this exact lifecycle: A starts, B is positively refused, polling B cannot STOP A, A's own positive stop occurs, and eligible C can acquire/dispatch ordinarily. Check B's local monitor, durable reservation, receipt/journal and resource map together; merely setting a local enum is insufficient. Retain all one-START barrier and real31.1second controls above. No field-acceptance milestone is closed by these simulations.

## Static limits

Final restart code additionally recognizes ADMITTED/RESERVED snapshots and maps them into local DISPATCHING for recovery. This was inspected, not exercised as another schedule. It needs truthful unsent-versus-entered interpretation in full recovery acceptance; no separate restart failure is claimed here. The late-ACK fence terminal-status precedence also changed in51932bf; the retained original transport schedules do not prove every fence-stop success/failure branch. Do not expand these static limits into additional reproduced findings.


---

# Specialist appendix: Public-store phase and quota contracts

# Shared quota store corrective verification

Candidate `51932bfd7c588395b45e353d41f9519a0fe08bc4`, immediate parent `26d47b17dc419797964eeca7dcfda262d71b87da`, reviewed patch base `4788dac8c56e4ec8d2caecc53317fd5c5144f675`.

**The owned R47801 direct-store phase/accounting slice and R47802 idempotent resource-claim counterexample pass in fresh candidate executions.** Admission no longer impersonates effect-producing transport. Repeated claims for the same event preserve phase and ownership metadata. One adjacent stale-preparation lifecycle also retains the mandatory pre-send expiry fence. No new concrete defect was demonstrated in this bounded store scope.

This conclusion does not close the entire R47801 dispatcher/protocol claim or all irrigation-runtime packages. The protocol lane owns ordinary dispatcher reachability and the foreign-live-operation preflight branch. This report exercises public store and safety-monitor writers with inert local data, not device/controller behavior.

## Method and exact-source evidence

`probes.py` adapts the two prior authored public-store probes. It imports candidate production functions directly and uses private store directories under this lane. Only the store clock is injected. No JSON record is hand-edited, and no prior result is adopted. The revised original admission schedule applies current refusal cleanup **only to the event whose claim failed**, rather than the previous harness's now-obsolete unconditional STOP writers.

There are two regression groups plus exactly one adjacent lifecycle group. The four-phase matrix is one resource-claim regression group. `SENDING` is constructed using the public `update_status` writer; it is not claimed to be an observed ordinary dispatcher phase. `EXECUTING` is likewise a store fixture; its competitor is tested with `live_executing=True` as an explicit input, without querying hardware.

`source-manifest.json` verifies 55 imported production modules against the exact candidate tree, records each local path/Git blob/SHA-256/line count, and hashes the reused harness. The dispatcher is separately recorded as **static-only**. `source-diff.txt` contains the production safety/dispatcher differences from the reviewed patch base. Neither repository tests nor audit/claim documents are correctness evidence. No production/Git edits, services, network, credentials, instruments, radio/controller operations or hardware were used.

```bash
PYTHONDONTWRITEBYTECODE=1 python /workspace/scratch/de6bc2428cec/repair-51932bf-review/ownership/probes.py
```

Fresh outputs: `results.json`, `source-manifest.json`. The complete runner exits successfully.

## R47801: corrected admission identity and unsent-refusal accounting

`services/agribrain/irrigation_runtime/safety.py:748–764` now creates a quota reservation with:

| Admission field | Fresh result |
|---|---|
| `status` | `ADMITTED` |
| `claimed` | `False` |
| `first_dispatched_at` | `None` |
| reserved volume | 4 mm for each admitted event |

With A and B admitted on the same device/zone, A's resource claim now succeeds. B's claim refuses A. This fixes the original direct-store mutual refusal, where both quota admissions already carried `DISPATCHING` and each blocked the other despite zero transports.

The current unsent-refusal writer sequence (`dispatcher.py:597–609`) removes local tracking, ends the watchdog, releases quota, then writes failure/releases. The direct probe executes its actual `SafetyMonitor.track_event_end`, `release_quota`, `SharedQuotaStore.update_status` and `release` writers for B only. B's reservation disappears; A's reservation and resource claim are unchanged. Reserved exposure drops from 8 to **4 mm**, and no settled/stopped delivery receipt is invented. Thus quota reservation is retained for the owner without treating the refused event as delivered water.

The paired schedule leaves A in `STARTING` because it deliberately never enters transport. A later claim after 100 injected seconds may expire that preparation lease and succeed; this is expected pre-transport expiration, not loss of an entered transport. A separate original positive control actually invokes `transition_to_dispatching`; its competitor is refused after 31 seconds even with a newer idle-query input.

Static call-path credit: preparation is now local `QUEUED` without prematurely persisting `DISPATCHING` (`dispatcher.py:483–486`), resource ownership is obtained at `589–615`, and the mandatory transition is still immediately before transport in `_dispatch_with_retry`. The full foreign-live-controller branch and restart behavior are not exercised by this lane. Consequently, this is **passing direct-store/admission-accounting credit**, not blanket acceptance of every R47801 entry path.

## R47802: same-event resource claims preserve phase and owner

The candidate adds an existing-owner return path at `safety.py:1686–1696`: for a claimed `STARTING`, `DISPATCHING`, `SENDING` or `EXECUTING` reservation with an owner token, it returns the current token without writing a new lease.

Fresh controls for each phase compare the complete before/after store JSON and exact file bytes across a repeated same-event claim:

| Phase | Same token/generation/timestamps/phase | Store bytes unchanged | Competitor control |
|---|---|---|---|
| `STARTING` | Yes | Yes | Refused while the original lease is 20 seconds old |
| `DISPATCHING` | Yes | Yes | Refused after 100 seconds with a newer idle-query input |
| `SENDING` | Yes | Yes | Refused after 100 seconds with a newer idle-query input |
| `EXECUTING` | Yes | Yes | Refused after 100 seconds with `live_executing=True` |

The original counterexample changed `DISPATCHING` to `STARTING`, generated a new token and timestamp, then allowed a competitor to expire that new lease. This no longer occurs. The current foreign in-flight barrier remains at `1663–1665`; it does not use preparation-lease age for `DISPATCHING`/`SENDING`.

The `EXECUTING` result does not assert that a newer qualified observation of idle hardware can never allow reconciliation: that path has different explicit inputs and remains separate. These are actual store-contract controls, not an overlapping-START experiment. Ordinary duplicate-submit dispatcher paths also have active-record guards and are not executed here.

## Adjacent lifecycle: stale preparation is not renewed by idempotence

The selected adjacent group ages A's `STARTING` lease to 31 seconds, then repeats `claim_resource` for A. The method returns the existing token and success, but **does not renew any metadata**. Calling the mandatory `transition_to_dispatching` with that token returns false, marks A `EXPIRED`, clears its ownership, and removes its resource claim (`safety.py:1770–1780`). Thus the idempotent fast path's success is not by itself transport authority.

B can then obtain the resource. A's subsequent claim is refused by B; its old transition is rejected. Late `EXECUTING`/`DISPATCHING` status writes leave A expired, and B's owner token remains intact. This group supports the intended preparation-versus-transport distinction and the late-promotion guards at `967–1002`.

The review does not claim that an expired event can never be explicitly re-admitted or recovered in any other state. It demonstrates that this selected idempotent retry does not renew the old preparation lease, cannot enter transport after expiry, and cannot revive the old owner after a competitor has taken the resource. The return value of `claim_resource` must continue to be consumed together with the mandatory transition/fencing check.

## Acceptance boundary and remaining scope

The passing slices relate to F16–F18 quota/execution ownership and uncertain-command reconciliation, with AB-EXE-003/004, AB-DEC-003 and AB-ARC-008 from the supplied master plan. Reserved depth is accounting exposure, not delivery evidence; admission, preparation and transport must retain distinct meaning through every consumer.

The report establishes the two owned software contract repairs and one bounded lifecycle control. It does not certify physical delivery, sensor validation, full stop/settlement reconciliation, malformed store recovery, arbitrary resource-envelope rebinding, all restart phases or the complete F16–F20 packages. No new defect is inferred solely from those untested boundaries.


---

# Specialist appendix: Normative readiness and actual serialization/API projection

# Normative and serialization readiness verification

Candidate51932bfd7c588395b45e353d41f9519a0fe08bc4, immediate parent26d47b17dc419797964eeca7dcfda262d71b87da, patch baseline4788dac8c56e4ec8d2caecc53317fd5c5144f675. The root reviewer completed this lane after delegated work stopped before a final runnable serialization artifact. No claim of a fully completed independent sixth review is made.

## Normative identity and acceptance accounting

The supplied master repair plan, sequencing addendum and work-package register match current committed blobs exactly: `08d378a65992de859369950599df198e64244f01`, `40751038dc8760e91bc3ab115e30c5e28395953a`, and `8a564647af7e588802537817159117b349ff606b`. The register contains52uniqueFAheaders, all open: F01–F40 and T01–T12. Its68textual FA mentions include cross-references. The supplied R3PDF SHA256 is `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`.

These are normative identities/register state, not proof52 implementations are absent or complete. Historical audit/claim documents added in26d47b1 are not correctness or scientific acceptance evidence. Literal master cards supply package mappings: runtime corrections relate to F16–F18; typed root/loss and missing-water corrections relate to F10/F11, with numeric F01/F04 prerequisites. F38/F40 consumer qualification and T05 economics remain separate thematic acceptance considerations.

## Two bounded serialization fixtures

Run `PYTHONDONTWRITEBYTECODE=1 python repair-51932bf-review/ledger/probes.py`. Both fixtures execute actual production serializers, with51imported source files checked against candidate Git blobs. They do not contact an HTTP endpoint, provider or hardware and do not run complete L4 inference; the decision lane owns that execution.

1. A hand-built typed nutrient output includes a blocked prescription/note, rootdepth0, missing-driver diagnostics, explicit root-unavailable aggregate/pathway flags and an illustrative loss12. The loss12 is supplied by the fixture, not a model estimate. Actual `to_plain_data` preserves prescription notes, depth0, aggregateavailability/is_root_supportedfalse and pathwayavailability/is_supportedfalse. Actual `artifact_to_run` returns L4DEGRADED/confidence.1/unsupportedflag, empty recommendations and BLOCKED authorization because L8 is absent. It does not expose every raw note/root field; this compact projection is not automatically a defect.
2. Actual `EnvironmentalLossEngine.compute_all_losses` receives explicit root0, drainage20 and finite matched environmental parameters, then actual `to_plain_data` serializes it. Leaching/denitrification preserveUNAVAILABLE_UNSUPPORTED_ROOT, riskUNAVAILABLE, supportfalse and zero excluded-debit placeholders. Aggregateavailability and explanatory note survive. This verifies the new type fields are carried by the real serializer rather than dynamically attached attributes that disappear.

The field names are individual `LossPathway.is_supported` and aggregate `EnvLossResult.is_root_supported`, both with `availability`. The new flags are not a calibrated uncertainty distribution or proof of physical zero flux. Numeric aggregate losses/effectiveN still describe the computed supported subset and need their qualifier wherever shown. The corresponding full-L4 budget omission no longer incurs the prior104.4kg/ha unsupported debit.

## Remaining target criteria, not newly reproduced defects

The raw artifact can preserve more scientific detail than the public summary by design. Consumer acceptance should verify that a UI, export or downstream model that displays quantitative environmental/N-budget claims retains their availability/support meaning. This lane does not demonstrate a public consumer dropping those flags to authorize an action. Standalone L8 authorization and actual operation completion remain separate packages.

Empirical calibration of local fertilizer response, correlated outcome risk, actual application/loss accounting and economic marginal value remains wider F11/F13/T05 work. Confidence caps, policy penalties, narrative notes and typed unavailability improve truthful output but do not establish observed agronomic or economic performance. No previous forecast/archive issues were reopened in this lane because those production files did not change.

The three exact normative documents, complete scientific requirement extraction, candidate/patch metadata and reconstruction manifests accompany the bundle. Full-acceptance milestones remain open; repaired software slices earn explicit credit without an invented completion percentage.


---

# Specialist appendix: Active integration and plan traceability

# Platform continuity review — 51932bfd7c588395b45e353d41f9519a0fe08bc4

**The six prior regression compositions and the sole new missing-water/weather composition pass through the actual full standalone L8 pipeline.** The dictionary permission repair, typed reason preservation, nonconserved-water block and generated N/P/K unsupported-root blocks remain intact. The new missing-water/weather case remains unavailable, and both unsupported-root and conservation restrictions survive into L8. No fertilizer schedule is CONFIRMED in these seven cases; MONITOR remains available.

This supports the verified integration slices. It does not certify public-route promotion, scientific accuracy of the diagnostic rates, an authorization envelope, publication, actuation, every serialization shape or the complete normative packages.

## Candidate and proof scope

Current candidate `51932bfd7c588395b45e353d41f9519a0fe08bc4` has immediate parent `26d47b17dc419797964eeca7dcfda262d71b87da`; the comparison baseline is `4788dac8c56e4ec8d2caecc53317fd5c5144f675`. Exact candidate source is `../source`. All151 unique import/reference source files in `source-manifest.json` match the candidate tree;138 were actually imported by the probe. These are lane-specific counts, not whole-repository coverage.

`eligibility_probes.py` executes the actual L3 engine, actual full `run_layer4_standalone`, actual ranker/scheduler and **full `run_layer8`**, including its final invariants. It extracts the exact current `_normalize_nutrient_states` through AST to avoid initializing the entire orchestrator. The original CEB03 regression uses exact L4 gate AST selected by semantic condition; current unsupported-first ordering is respected with an explicit supported-root fixture for that nonconservation control. No fixed historical line selector is used.

The nonconserved and zero-root cases explicitly replace fields on a fresh actual L3 WaterState. They test receipt/blocker continuity, not spontaneous solver failures. The new missing-water/weather case needs no such receipt injection: actual full L4 receives `l3_decision=None,daily_weather=[]`. All cases use explicit offline fixture inputs. Network connections are blocked; no DB, provider, service, hardware, public-route, repository test/audit or production/Git mutation executes.

Raw evidence: `results.json`, `probe-stdout.txt`. Python3.12.14 and installed dependency versions are retained. The supported production image was not built or certified.

## Seven bounded compositions

| Composition | Result through normalizer, ranker and full standalone L8 |
|---|---|
| Full L4 nonconserved receipt, supported roots | N/P/K states retain confidence0.20 and local prescription blocks. Normalizer/L8 retain `nonconserved_water_transition`, false permission and LOW confidence; three fertilizer schedules BLOCKED. |
| Full L4 explicit zero-supported root boundary | Actual generated N/P/K prescriptions carry `unsupported_root_boundary`; states/health confidence ceilings0.10. All three fertilizer candidates remain false/LOW and schedules BLOCKED. |
| Original CEB03 probability0.8 exact-gate regression | The diagnostic120kg_N/ha candidate stays false/LOW with `nonconserved_water_transition`; schedule BLOCKED. |
| Original8AE04 dictionary permission override | Existing `is_allowed=true` cannot override a blocked typed prescription. `regulatory_N_limit` survives and fertilizer remains false/LOW/BLOCKED. |
| Typed mixed-prescription control | Allowed plus blocked same-nutrient prescriptions combine to false; both `regulatory_N_limit` and `farmer_prohibition` survive through BLOCKED scheduling. |
| Dictionary existing-false control | Existing false permission and `preexisting_farmer_prohibition` survive an allowed incoming typed prescription; fertilizer remains BLOCKED. |
| **New: missing canonical water and weather** | Actual full L4 reports unavailable hydrology, blocks local prescriptions, and the normalizer/L8 retain both `nonconserved_water_transition` and `unsupported_root_boundary`; all three fertilizer schedules BLOCKED. |

All seven full L8 calls completed. Fertilizer actions are present in every case, so the result is not a vacuous empty-output pass. MONITOR remains allowed/CONFIRMED. Every full L8 result has `authorization_envelope=None`; these are standalone shadow outputs. `bounded_checks` in `results.json` records explicit assertions for candidate presence, blocked permission/reasons, successful full L8 execution, no confirmed fertilizer schedule and absence of authorization envelope.

## New missing-water/weather behavior and gate ordering

`layer4_nutrients/runner.py:284–306` now constructs a clearly unavailable SWB when canonical water and weather are both missing. The executed case returns:

- `status=UNAVAILABLE_MISSING_WATER_AND_WEATHER`, `is_degraded=true`;
- supported depth0, uncertainty multiplier2.5, missing weather days7;
- `mass_conserved=false`, closure0;
- L4 health/ceiling0.10 and `MISSING_HYDROLOGY_AND_WEATHER` plus `UNSUPPORTED_ROOT_BOUNDARY` quality drivers.

Unsupported-root handling now precedes nonconservation in the L4 `if/elif` gate (`runner.py:680–709`). Consequently local N/P/K prescriptions contain `unsupported_root_boundary`, rather than both reasons. This does not erase the SWB flag: the exact unchanged normalizer independently reads `swb.mass_conserved=false`, preserves closure0 and adds `nonconserved_water_transition`, then merges the local unsupported-root reason. Full L8 retains both reasons and remains blocked. This composition demonstrates preservation despite the reordered local gate; the lack of two local reasons alone is not counted as a defect.

The supported-root nonconservation control still retains closure2mm and the nonconservation block. In the missing-data case, closure0 is not interpreted here as measured perfect conservation: the unavailable status, false conservation flag and blocked permission are the operative contract. The literal normalizer reason is preserved without claiming a physical2mm error occurred in the missing-input case.

## Availability and quantitative consumers

The new environmental loss metadata survives in the actual L4 object and its dataclass serialization. With unsupported roots, both leaching and denitrification have:

- `availability=UNAVAILABLE_UNSUPPORTED_ROOT`, `is_supported=false`;
- `risk_class=UNAVAILABLE` and numeric loss0 placeholders.

The aggregate has `availability=UNAVAILABLE_UNSUPPORTED_ROOT,is_root_supported=false`, with notes explicitly stating the root-dependent pathways are unavailable and excluded from debit (`environmental_losses/engine.py:38–74,130–148,193–217,226–242`). This corrects the earlier root-zero result that lacked those explicit availability qualifications.

Existing aggregate numeric fields remain populated: this fixture returns total loss7.73kg/ha, effective N189.89kg/ha and `overall_risk=LOW`. Those numbers describe the remaining calculated components; the availability flag/notes qualify the incomplete assessment. This lane does not independently validate their scientific magnitude or treat LOW as proof all pathways are known safe.

Actual L4 N-budget assembly now admits leaching/denitrification debits only when roots are supported and the corresponding pathway reports AVAILABLE (`layer4_nutrients/runner.py:599–614`). The raw result confirms zero placeholders for those two debits under unsupported/missing hydrology, with separate nonzero volatilization retained. The complete L4 object carries the unavailable status and prescription prohibition.

**Consumer scope limit:** numeric `NutrientBudget` fields themselves do not contain pathway availability, and the nutrient normalizer does not export environmental availability/status/notes as separate fields. It exports permission, reasons, conservation and closure. The tested N/P/K prescription consumers remain blocked, so no availability-to-eligible promotion is demonstrated. A downstream consumer reading only budget scalars would need the outer L4 availability/health context to distinguish unavailable pathways from measured zero. No live UI, public numeric display or arbitrary budget consumer was invoked. Current selected production search finds direct environmental-loss use in L4 budget assembly/output; it does not establish every possible consumer in the repository.

Availability based on root support is also distinct from conservation admissibility: a supported but explicitly nonconserved receipt produces root-supported environmental metadata while L4 confidence/permission still carry the separate physical-failure block. Neither flag is treated as a universal scientific-authority verdict.

## Active callers and public-path boundary

Paths below are relative to `services/agribrain/` unless a `src/` path is shown.

- Actual full L4 uses the receipt boundary (`layer4_nutrients/runner.py:190–273`), explicitly unavailable fallback (`284–306`), zero-root computation guard (`532–546`), physical prescription gates (`680–718`) and health/quality limits (`813–849`).
- Active main constructs L8 input with `_normalize_nutrient_states(l4_res.output)` (`orchestrator_v2/runner.py:2860`). The entire orchestrator file is byte-identical to baseline4788dac, blob `60cc31c30bbd0754a50c84fc3a71c52158a8e0e2`. Its normalizer retains conjunctive dictionary permissions, typed prescription blockers and conservation metadata (`3435–3510`).
- Ranker carries restrictions/confidence (`layer8_prescriptive/action_ranker.py:213–250`); scheduler preserves blocked schedules (`scheduler.py:260–272`); full L8 final invariants reconcile late blockers (`invariants.py:286–336`). These functions were executed, not inferred only from their presence.
- The public Next route still authorizes the plot before backend execution (`src/app/api/agribrain/run/route.ts:829–860`, backend call502). Python `/v2/run` is at `app/main.py:3870–3871`. Main retains independent influence-manifest/tribunal/planning/weather/soil gates (`orchestrator_v2/runner.py:2712–2736,2940–2964`). These are static current caller traces, not authenticated route or canonical-promotion executions. Fixture audit grade and semantic hashes isolate internal continuity; they are not earned authority receipts.

The earlier sulfur coverage limit remains qualified: actual unsupported-root sulfur has no matching local prescription and low probability0.1192, so no sulfur candidate is generated; the normalizer does not directly propagate the global unsupported-root driver to that state. No extra sulfur scenario or public bypass was tested. Likewise, checkpoint receipt omission remains a static serialization scope observation from `layer3_decision/runner.py:2650–2691`, not a newly executed restart/publication failure.

## Normative identity and acceptance

`verify_metadata.py` verifies all3 supplied normative document blobs against current candidate and baseline tree; all are exact and unchanged:

| Document | Blob |
|---|---|
| Deep Repair Plan | `08d378a65992de859369950599df198e64244f01` |
| Execution Sequencing Addendum | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| Work Packages / acceptance register | `8a564647af7e588802537817159117b349ff606b` |

There are52 unique full-acceptance rows,0checked. Codes are **F01–F40 plus T01–T12**. This is register metadata, not evidence52 defective/absent implementations. `plan-results.json` retains exact master-card requirements, sequencing stages and supplied R3 line mappings.

Relevant acceptance remains F10 (`AB-AGR-008,AB-AGR-010,AB-DAT-007`: typed water boundary and degraded semantics) and F15 (`AB-DEC-003,AB-ECO-003,AB-EXE-001`: final hard-action restrictions), with F01/F02 provenance/authority, F03/F09 receipt/recovery and F11/T04 broader nutrient/world-model work. The original dictionary and blocker repairs receive positive regression credit; seven compositions do not establish complete closure of those packages or the scientific validation program.

## Reproduction

From this directory: `python eligibility_probes.py`, then `python verify_metadata.py`. Scripts and raw outputs are self-contained against the exact `../source` corpus. No repository tests or audit contents are used. The repository advertises `npm run api` using `py -m uvicorn services.agribrain.app.main:app --port 8000 --reload`; that service command, build/lint and public-route execution were not run.

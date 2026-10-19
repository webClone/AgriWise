# AgriBrain corrective verification and work-in-progress audit

**Candidate:** `4788dac8c56e4ec8d2caecc53317fd5c5144f675`  
**Parent:** `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`  
**Review date:** 19 October 2026  
**Decision:** Continue planned development, with the four qualified follow-ups below. This patch repairs its original transport race and several important scientific/integration boundaries; it does not establish full package or operational acceptance.

## 1. Executive assessment

Six agents independently reviewed runtime protocol, durable ownership/accounting, hydrology, full nutrient calculations, downstream permissions, and plan/serialization contracts. The original after-fence transport race no longer reproduces: with two actual OS workers and a real 31.1-second pause inside an inert transport, only A issues a START and B is refused. The new distinction between expirable preparation and non-expirable unresolved transport is valuable.

However, earlier admission writers already label reservations `DISPATCHING`. The strengthened claim barrier now treats those unsent reservations as transport. Two ordinary simultaneous submissions can refuse each other; a subsequent third submission also refuses. This is an **availability and lifecycle regression with zero START effects**, not a newly demonstrated duplicate-dose race.

The zero-capacity check, dictionary permission conjunction, and declared prescription notes are repaired in the executed scope. Explicit zero-root support now blocks prescriptions and produces degraded confidence/health as claimed. That last repair is scientifically incomplete: unsupported zero placeholders still enter ordinary environmental-loss formulas, and a separate absent-canonical/absent-weather branch fabricates positive default support. A direct-store same-event claim also demotes an in-flight phase back into an expiring preparation phase, though normal duplicate-submit reachability was not demonstrated.

These observations form **four distinct remaining finding groups**. The protocol and store reproductions of the same pre-admission defect are merged into one finding. Static seams and unexecuted API paths are qualified separately rather than counted as additional defects.

## 2. Evidence, exclusions and confidence limits

GitHub commit metadata and the observed main ref identify the candidate above. Its recursive tree contains 4,079 entries and was not truncated. No `AGENTS.md` was present. The commit changes ten paths: seven production Python files, two review/register documents, and one repository test. Only production and normative target material were used to establish behavior; repository tests, historical audit reports and generated artifacts were excluded as correctness evidence.

The private source corpus contains **732 production/configuration files**, each matched byte-for-byte to the candidate Git blob. This is a reconstruction/import corpus, not a claim that every function was dynamically examined. All seven changed production files compiled without importing or executing them. Imported-source manifests distinguish executed modules from static caller references. Agent import counts overlap and must not be added together as coverage.

The authored probes use actual production functions, private local files, inert collaborators and controlled physical input fixtures. The runtime schedules use actual OS processes, not two objects presented as multi-process evidence. The separate ownership API checks use an **injected clock**, not a real transport. Full standalone L4 and L8 functions execute. To isolate the orchestrator normalizer, its exact unchanged function AST is extracted and executed; this is not a full orchestrator run. Some negative scientific fixtures deliberately replace fields on actual production dataclasses; they are admission/qualification counterexamples, not naturally generated solver failures.

The evidence bundle includes eleven reproducible command invocations, six specialist reports, fresh result files, source/plan hashes, reconstruction instructions and replay validation. Exit zero means declared observations—including counterexamples—reproduced. It is not an additional passing repository-test count. The user's reported 36-test run was not adopted as independent proof or re-advertised as our own execution.

No production or Git edits, service startup, provider calls, field controllers, brokers, radios, drone missions or physical hardware were used. The Git-object reconstruction helper is syntax/layout checked; it was not run against a separate complete Git checkout. A separate exact-source workspace replay checks the packaged layout and observations.

## 3. Disposition of the five claimed repairs

| Claim | Fresh disposition | Demonstrated scope and limit |
|---|---|---|
| **8AE01 — transport ownership** | **Original defect repaired; new admission regression** | Original after-fence real-time schedule produces one START, with A's resource token, reservation and active command consistent. Genuine in-flight ownership survives lease age. Earlier pre-admission `DISPATCHING` labels now cause mutual refusal (R47801); a direct same-event claim can reset phase (R47802). |
| **8AE02 — zero surface capacity** | **Repaired** | Storage5/capacity0 is rejected by constructor and direct solver guard; production hydration refuses it. Valid0/0 and5/12 controls pass. Independent soil/whole ledgers and ET partition controls remain consistent. |
| **8AE03 — unsupported root boundary** | **Explicit-zero gate repaired; availability incomplete** | Root0/VWC0 replaces60/.25 in the explicit-zero branch; N/P/K prescriptions block, confidence/health cap at.1, reason persists through full L8. Loss/budget outputs still acquire unsupported physical semantics (R47803), and an omitted boundary follows a different default-support path (R47804). |
| **8AE04 — monotone permission merge** | **Repaired in executed typed/dictionary compositions** | Existing false or incoming false remains false, reasons survive, and actual ranker/full standalone L8 keeps fertilizer schedules BLOCKED. No public-route promotion or all-shape guarantee is claimed. |
| **8AE05 — declared notes** | **Repaired for raw serialization** | Live nonempty prescription notes equal `asdict` output and survive actual `to_plain_data`. The public response adapter deliberately summarizes layers; omission of raw notes/depth there is not automatically a new bug. |

The seven production targets and exact blobs are recorded in commit metadata/source manifests. Relevant source references below are pinned to the full candidate, not a moving branch.

## 4. R47801 — admission is confused with entered transport

**Priority P1; ordinary submission and actual OS-process reproduction.**

Two workers A/B submit to the same idle device/zone. Both truthfully observe ONLINE. Both return `STOP_REQUESTED`; the inert controller records **zero STARTs**. A fresh third OS worker C then submits ordinarily and also returns `STOP_REQUESTED`, still with zero STARTs. No periodic reconciliation/monitor was invoked: this establishes the observed stalled admission lifecycle, not a universally permanent deadlock or proof that all recovery is absent.

The initial atomic quota writer creates `status="DISPATCHING"` before resource admission ([irrigation_runtime/safety.py:L745-L763](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/irrigation_runtime/safety.py#L745-L763)). The dispatcher additionally persists that phase before status query/claim ([irrigation_runtime/dispatcher.py:L483-L493](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/irrigation_runtime/dispatcher.py#L483-L493)); the new update logic marks it claimed and assigns an execution timestamp ([irrigation_runtime/safety.py:L998-L1012](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/irrigation_runtime/safety.py#L998-L1012)). The new claim barrier unconditionally protects foreign `DISPATCHING` rows as entered transport ([irrigation_runtime/safety.py:L1661-L1666](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/irrigation_runtime/safety.py#L1661-L1666)). Each unsent reservation therefore blocks its competitor. Refusal converts both to protected stop intent, which also blocks C.

The independent public-store reproduction has no driver at all: two4mm admissions succeed, A/B claims mutually refuse, actual refusal-path status writes retain8mm, and C also refuses. Its positive control confirms genuinely entered transport remains protected after an injected31seconds. This corroborates the mechanism without being counted as another finding or a physical experiment.

**Required repair:** use distinct phases for quota admission, resource preparation and entered transport. An admitted quota holder must not imply physical uncertainty. Only the atomic current-token transition immediately preceding transport should establish `DISPATCHING`. Positively unsent losers need an explicit deferred/refused policy and appropriate accounting cleanup; unresolved sent operations must retain exposure and stop/reconciliation obligations. Do not fix availability by restoring age-only takeover of real in-flight transport.

**Acceptance:** repeat both simultaneous-idle schedules and the later-C lifecycle. One eligible owner should progress, or a documented pre-transport deferral/refusal should resolve without false stop intent. Check physical effects, resource tokens, phase receipts and reserved totals independently. Retain the real31.1-second after-fence one-START control, the before-fence expiration control and delayed-idle/query-failure protection.

## 5. R47802 — same-event claim resets an in-flight phase

**Priority P2; reproduced public-store contract, dispatcher exposure unproven.**

A is admitted, acquires a resource claim and enters `DISPATCHING`. Calling `claim_resource` again for A returns success with generation2 and a new token, but changes A back to `STARTING`. After an injected31seconds, B can expire A and acquire the resource. The old token is correctly rejected and late promotions of expired/stop-requested rows remain fenced; the defect is the same-owner demotion itself.

The conflict loop skips the same event; subsequent code unconditionally generates a new token and writes `STARTING` ([irrigation_runtime/safety.py:L1627-L1715](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/irrigation_runtime/safety.py#L1627-L1715)). This contradicts the method's idempotent ownership promise and turns non-expiring effect uncertainty into an expiring preparation lease.

Normal `submit_event` duplicate guards usually join an active/already-reserved event before this call. The probe does **not** establish a normal duplicate-submit schedule, overlapping hardware operation, or a concrete driver failure. It establishes a production store API contract defect that should be corrected before broader recovery writers rely on it.

**Required repair/acceptance:** repeated same-event claim on a live owner returns the same token/generation and preserves the current phase. Any generation change must be an explicit fenced recovery/transfer operation retaining unresolved dispatch/stop meaning. A competitor must remain refused after31seconds when A was already in transport; legitimate pre-transport expiry and old-token rejection must continue to work.

## 6. R47803 — unavailable roots become ordinary environmental estimates

**Priority P2; complete standalone L4 reproduction, hard prescription blocks preserved.**

The explicit-zero-root repair passes root0 and VWC0 to the environmental engine and later blocks prescriptions. It does not provide a typed unavailable-domain value to water-dependent loss calculations. The actual engine interprets zeros physically, emits loss/risk/available-N values, and L4 writes them into its nutrient budget before applying the permission gate.

| Explicit unsupported fixture | Actual full-L4 output | Qualification |
|---|---|---|
| Root0/storage0, dry forcing | Leaching0/LOW, denitrification0/LOW; total6.56kg/ha, effectiveN173.44; aerobic/low-risk and all-pathways-acceptable notes | Missing root/moisture support does not establish aerobic soil or a fully valid low-loss estimate. |
| Same unsupported root, explicitly declared20mm drainage | Leaching104.4kg/ha/HIGH; denitrification0/LOW; total110.96, effectiveN69.04;104.4 enters N-budget leaching | This is a deliberate unsupported-domain contract fixture, not a validated solver-generated trajectory or measured field loss. |

The arithmetic explains the second result: `soil_water=theta_fc*root_depth*10=0`, then `drainage/max(1,soil_water)` becomes20/1 and is capped at1. With modeled Ninput180 and soluble fraction.58, the result is104.4. See [layer4_nutrients/environmental_losses/engine.py:L219-L231](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/layer4_nutrients/environmental_losses/engine.py#L219-L231). VWC0 also becomes zero WFPS and an aerobic interpretation; output dataclasses lack per-path availability/status ([layer4_nutrients/environmental_losses/engine.py:L37-L66](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/layer4_nutrients/environmental_losses/engine.py#L37-L66)). Budgets consume the loss scalars at [layer4_nutrients/runner.py:L590-L623](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/layer4_nutrients/runner.py#L590-L623). The180kg/ha is preliminary modeled demand passed to a parameter named appliedN, not independently verified applied fertilizer.

All unsupported-root prescriptions remain blocked and health/confidence remain≤.1 in these fixtures. The finding concerns scientific meaning and downstream budget integrity, not an observed operational recommendation bypass.

**Required repair:** carry availability, support, provenance and uncertainty into each relevant loss/budget quantity. Distinguish valid zero flux from missing root domain and missing moisture. A supported zero-drainage observation may establish zero leaching without establishing soil aerobicity or validity of all other pathways. Independent pathways can retain estimates only with their own qualified support. Unknown water-dependent losses must not silently become known0 or an arbitrary1mm-domain loss in a physical budget.

**Acceptance:** both zero-root fixtures keep their prescription blocks and serialized explanations while exposing unavailable/explicitly qualified loss components and budgets. Healthy supported controls retain finite results. Verify actual applied exposure versus proposed demand separately; no field-calibration claim follows from passing these contract probes.

## 7. R47804 — absent canonical support takes a healthy default path

**Priority P2; standalone research API behavior, public exposure unestablished.**

The bounded fixture supplies `l3_decision=None` and `daily_weather=[]` with the same deficient nutrient evidence. The default SWB supplies support60cm, generic retention.30/.15/.45, moisture0 and statusOK ([layer4_nutrients/runner.py:L284-L301](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/layer4_nutrients/runner.py#L284-L301), [layer4_nutrients/schema.py:L279-L286](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/layer4_nutrients/schema.py#L279-L286)). The new gate checks positive depth rather than actual boundary presence/availability. The loss engine receives root60/VWC0; full L4 returns allowed N163.1/P43.8kg/ha, health.75/statusok and no hydrology missing-driver explanation.

This differs from bypassing the repaired explicit-zero branch. Omission selects a separate compatibility path. The standalone API permits research mode, and this review did not execute the outer semantic-lineage authorization wrapper or authenticated full orchestrator. It does not establish live actuation or a public-route exploit.

**Required repair/acceptance:** represent canonical-boundary presence and support provenance independently from positive default numeric fields. No-canonical/no-weather output must be unavailable or explicitly prior/scenario-qualified through losses, budget, health and recommendation authority. It must not look like healthy canonical root evidence. Check the outer authority consumer separately before claiming public operational closure.

## 8. Regressions that remain repaired

Hydrology independently closes soil/surface/whole ledgers in the retained impedance, ponding, ET and restart controls. The mixed full pipeline publishes T.59, soilE5.71, pondE3.50 and ETA9.80mm; rounding leaves.01mm closure, not exact unrounded zero. Direct pond evaporation uses soilE0/pondE7 with zero closure residual. Valid capacity controls remain accepted.

The full supported-root nutrient control independently integrates137.55mm into L4 with weighted FC/WP/saturation.295/.0966667/.44. Its small difference from the historical137.57 fixture is not the old83.30 substitution. Shallow15cm support integrates20.60mm. Requested120cm/profile60cm produces coverage.5; requested121cm produces.4959 and degraded status. These are overlap/qualification checks, not calibration of the policy threshold.

Six actual standalone L8 compositions preserve nonconserved/unsupported N/P/K restrictions and both directions of dictionary permission conjunction. All generated fertilizer candidates in those cases are present and BLOCKED; MONITOR remains allowed/CONFIRMED, avoiding a vacuous everything-disabled result. `authorization_envelope=None` remains appropriate for those standalone shadow outputs.

The actual raw serializer preserves declared notes/root0/missing-driver fields. The isolated actual public adapter returns degraded L4/confidence.1/unsupported flag, no recommendations and BLOCKED authorization because L8 is absent. Its fixture loss12 is hand-supplied, not a modeled numerical reproduction. Compact API projection choices, ungenerated sulfur candidates, optional store-token contracts and unexecuted late-fence cleanup branches are recorded as limits in appendices, not additional reproduced findings.

## 9. R3 and repair-plan alignment

All three normative plan documents match current committed blobs exactly. The supplied R3 PDF identity is SHA256 `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; its scientific requirement extraction is included in the evidence bundle. R3 scientific IDs and master-plan package IDs are distinct namespaces.

| Work package | Literal master-card R3 requirements relevant to this review | Current implication |
|---|---|---|
| F03 | AB-AGR-004/005/008 | Integrated flux/compartment controls retain scoped credit. |
| F04 | AB-AGR-003; AB-DAT-007 | Zero-capacity admission repaired; entire hydraulic parameter acceptance remains wider. |
| F10 | AB-AGR-008/010; AB-DAT-007 | Explicit boundary/blocker continuity improved; R47803/04 remain. |
| F11 | AB-AGR-010/008 | Unsupported losses cannot count as qualified conservative N-pool evidence. |
| F16–F18 | Exact individual mappings retained in `platform/plan-results.json` and master cards | R47801/02 require phase/idempotence correction; commissioning and uncertainty reconciliation remain separate. |
| F15 | AB-DEC-003; AB-ECO-003; AB-EXE-001 | False upstream permission remains false through checked L8 compositions. |

F38/F40 consumer/degraded publication and T05 economics are additional thematic acceptance considerations, not arbitrary additions to literal package mappings. Narrative notes and scalar confidence caps are useful policy mechanisms; they do not prove calibrated posterior uncertainty, local fertilizer-response curves, causal economic value, or actual delivered water/fertilizer.

The task register contains **52 unique full-acceptance headers: F01–F40 and T01–T12;52 open,0checked**. Its68 textual references include repeated prerequisite mentions. Open acceptance does not mean52 implementations are absent or defective; it means full sign-off has not been recorded. This candidate's narrow repairs do not justify closing package milestones or inventing a completion percentage.

## 10. Implementation order and when to proceed

Continue implementation now on the existing dependency schedule. Correct the runtime phase regression before treating concurrent admission as ready for operational staging. Scientific boundary work can proceed in parallel. Objective-qualified Omega/world-model research can continue using explicitly eligible inputs and shadow/scenario outputs; unrelated research need not wait for all hardware commissioning. These findings do not authorize production field dispatch.

| Order / owner stream | Concrete work | Reviewable exit evidence |
|---|---|---|
| A1 — runtime F16–F18 | Define admitted→STARTING→DISPATCHING lifecycle; move early writers off transport phase; define positively unsent refusal/defer cleanup. | Two actual idle contenders, laterC, ledger totals and tokens consistent; real in-flight lease protection preserved. |
| A2 — same stream | Idempotent same-event resource claim; explicit generation-changing recovery contract. | Token/generation/phase unchanged on retry; competitor refused after lease age; valid transfer remains fenced. |
| B1 — scientific F10/F11 | Typed support/availability for loss pathways and physical N-budget terms; actual applied versus candidate demand explicit. | Root0 dry/drainage fixtures qualified; known supported zeros remain zero; no unsupported loss debit. |
| B2 — same stream | Remove healthy interpretation of absent canonical/weather defaults; retain explicit research-prior mode. | Missing-boundary result truthfully qualified; actual outer authority behavior recorded. |
| C — integration F15/F38/F40 | Retain normalizer conjunction, serialized notes and typed blocker continuity; verify actual consumers where quantitative outputs are shown. | Supported, nonconserved, unsupported, dictionary and typed compositions retain intended authority/diagnostics. |
| D — existing full acceptance | Complete package-specific integrated, persistence, operational and hardware criteria where the plan requires them. | Acceptance evidence attached per milestone; software fixtures distinguished from field commissioning. |

Do not restart the entire audit loop for unchanged packages after each small patch. Re-run original repaired counterexamples, these four follow-ups, and bounded adjacent controls. Broaden only where changed behavior, failures or an unresolved dependency warrants it. The master program's2,564–4,540hour estimate is an original program estimate, not a fresh remaining-work calculation for this candidate.

The appended reports preserve exact recipes, source identities, results, limitations and narrower static observations. The machine-readable register supplies the five claim dispositions and four deduplicated finding records; the bundle supplies reproducible evidence without copying production source.


---

# Specialist appendix: Water conservation and compartments

# 8AE02 pond-capacity verification — 4788dac

Pinned candidate: `4788dac8c56e4ec8d2caecc53317fd5c5144f675`, parent `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`. Review date: 2026-10-19.

**The original 8AE02 pond5/capacity0 counterexample is fixed at all three requested boundaries.** Valid zero and valid pond states remain accepted. Retained W01 conservation, CEB02 soil/pond evaporation propagation through the full water pipeline, and ponding round-trip controls pass. No new defect was reproduced in this bounded lane.

## Reproduction and evidence

Run from the workspace root:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-4788dac-review/trajectory/probes.py
```

The harness is adapted from the prior authored lane, with fresh execution and candidate assertions. `results.json` contains complete inputs, returned states/receipts, independent ledger residuals and eight acceptance checks; every check is true. `source-manifest.json` verifies89 imported production module files against this candidate's Git tree. This verifies loaded bytes, not all-function or branch coverage. No reused production dependency copy was needed.

Calls use actual production data contracts, the soil/root factories, layered transition, complete `WaterIntelligenceEngine.execute_pipeline`, and `_deserialize_soil_water`. No repository tests/audits or old generated results establish correctness here. No production source/Git edits, hardware, network or service calls were made. Worldline aliases are redirected to a private lane path before hydration. No additional adjacent case group was added.

Normative scope: master-plan F03/F04/F07 and R3 AB-AGR-003/004/005/006, AB-DAT-005/007. The local normative source receipts are in `normative-manifest.json`. All code references below are to the candidate SHA; paths begin `services/agribrain/`.

## 8AE02 — Original invalid reservoir now rejects

The prior source accepted `surface_storage_mm=5,max_surface_storage_mm=0`: its maximum-capacity check was conditional on capacity>0. The candidate removes that condition in both the typed constructor and direct solver:

- `layer3_water/contracts/water_state.py:35–50`, especially line47, now checks storage≤capacity even when capacity0. Blob: `e4750e68c7171d53d2601d6890593ce3d7fd239e`.
- `layer3_water/soil/layered_water_balance.py:139–151`, especially line150, applies the same unconditional bound before surface water is integrated. Blob: `5fbfacdab31906eedbb84aedc8d03eaed1e9aad3`.
- Production hydration constructs that validated `InfiltrationState`, catches rejection, and returns None rather than an invalid soil object: `layer3_decision/runner.py:857–877`.

| Initial surface storage / maximum, mm | Constructor | Direct solver | Production hydration |
|---|---|---|---|
| **5 / 0 — original counterexample** | **ValueError** | **ValueError** | **None** |
| 0 / 0 — legitimate zero | Accepted | Accepted | Accepted |
| 5 / 12 — supported pond | Accepted | Accepted | Accepted |

Constructor rejection prevents ordinary creation of the invalid current contract. To exercise the lower solver guard independently, the harness deliberately supplies an inert legacy-shaped infiltration object inside an otherwise valid soil state; it does not claim that this object passed the repaired constructor. Hydration is tested with an actual serialized soil record whose infiltration fields contain5/0. Both independently reject before integration. This distinction prevents constructor success/failure from masking the other requested boundaries.

The direct error is `Initial surface storage (5.0) cannot exceed max capacity (0.0)`. The constructor gives the corresponding storage-versus-maximum error. No invalid-reservoir full-pipeline result is published by this reproduction.

Retained CEB05 controls also pass: negative evaporation, negative capillary, NaN capillary and boolean transpiration reject; negative surface storage and storage13/capacity12 reject at typed construction; ordinary zero fluxes preserve state. Source: `layered_water_balance.py:94–105,139–151`; `water_state.py:35–50`.

Scientific implication: numeric closure can no longer bless this specific5 mm reservoir when its stated maximum is0. The fix is at domain admission, not an alteration of measured water or a recalibration of soil physics.

## Retained conservation and ET controls

All fixtures below were executed anew against this candidate.

| Control | Fresh result |
|---|---|
| W01 dry impedance profile | Exact whole-system closure0 mm |
| W01 permeable rain100 profile | Exact closure0; infiltration100, drainage100 mm |
| W01 original impedance rain100 | Soil180→225; net infiltration45.10, runoff54.90, drainage.10; closure0 mm |
| W01 original through full pipeline | Soil180→214.56, ETA10.46; closure.02 mm |
| CEB02 original mixed rain/irrigation/capillary fixture | T8, soil evaporation0, pond evaporation7, ETA15; independent soil and whole residuals0/0 mm |
| CEB02 no-ponding control | T5.03, soil evaporation7, pond evaporation0, capillary6; soil120→113.97; both residuals0 |
| Full pipeline with both evaporation compartments nonzero | T.59 + soil E5.71 + pond E3.50 = **ETA9.80**; soil/whole residuals.01/.01 mm |

The full pipeline's published components match the transition receipt at .01 mm precision, and both receipt and published ETA equal the sum of all three components. This verifies actual integration in `layer3_water/runner.py:306–336`, not merely the presence of the new field. Receipt control-volume definitions remain explicit at `layer3_water/contracts/water_state.py:315–334`; the transition publishes the separate extraction values at `layered_water_balance.py:326–345`.

The .01/.02 mm serialized-state residuals are within the declared .05 mm tolerance and are not described as exact zero. Complete fixture geometry, hydraulic parameters, weather and independent balances are recorded in `probes.py` and `results.json`.

For the two-interval ponding control, surface storage0→10→6.90 mm; cumulative whole-system residual0. JSON serialization followed by the actual soil deserializer gives exactly the same second-interval state and receipt as warm continuation. Thus the capacity guard preserves the valid round-trip fixture and the separated pond-evaporation coordinate.

## Disposition

Credit the original8AE02 repair, with constructor/direct-solver/hydration rejection and preserved valid zeros. Retain credit for executed W01, CEB02 and CEB05 controls. No new finding or remediation is proposed by this lane. Acceptance remains limited to these numerical/admission/round-trip fixtures; it does not certify empirical calibration, every hydrological workload, unrelated candidate changes, or complete R3/master-plan closure.


---

# Specialist appendix: Typed L3 to L4 boundary and nutrient qualification

# L4 unsupported-root and prescription-note verification

Main `4788dac8c56e4ec8d2caecc53317fd5c5144f675`, parent `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`. Reviewed 19 October 2026.

**8AE03's explicit-zero-root prescription failure is repaired, and 8AE05's prescription-note serialization defect is repaired.** Unsupported-root N/P recommendations now remain blocked, and their warning survives `dataclasses.asdict`. Valid-root arithmetic, partial-root coverage, nonconserved hard gates and conserved-degraded confidence/quality handling retain their demonstrated behavior.

Two distinctions remain material. Passing **0** into the loss engine is not a qualified missing-loss representation: the engine still emits physical risk/available-N claims on the unsupported domain. Also, completely absent canonical/weather support takes a separate default-SWB path that remains treated as supported. These are reproduced local L4 behaviors; no full-orchestrator permission bypass or physical action is claimed.

## Method and exact source

`probes.py` reuses the nine authored compositions against the new source and adds exactly **two** bounded cases: no canonical water/no weather support, and declared zero root support with20mm drainage. All **11** completed with assertions. `results.json` records input fixtures, complete typed receipts, independent posterior-depth integration, actual environmental-loss arguments, nutrient states/budgets, prescriptions, notes and health/quality. `executed-source-manifest.json` records **113 candidate production files**, each checked against the pinned Git tree before import and rechecked after execution. `review-source-manifest.json` adds focus line references, normative hashes and scoped claim status.

The actual water engine/factories, actual typed boundary method, complete `run_layer4_standalone` and actual environmental-loss engine execute. Its argument observer delegates unchanged. No target-body/AST rewrite, older production dependency, repository tests/audits as correctness proof, production/Git edits, network/service/controller/hardware operation occurred.

Root-depth cases use actual unchanged pipeline output. Low-health/nonconserved/zero-support/inherited-uncertainty controls deliberately replace fields on actual frozen production dataclasses. The new drainage case explicitly declares a flux on that unsupported boundary and does not establish a self-consistent solver-generated water trajectory. The missing-canonical case passes `l3_decision=None`, `daily_weather=[]`; the harness-generated comparison water object is **not supplied** to that L4 call. These are admission/qualification checks, not claims that the current water solver naturally generated all negative records.

The full standalone L4 API is executed in its permitted research mode without semantic lineage. The outer L4 wrapper's authority checks and a full orchestrator run were not executed. Platform owns actual L4→normalizer→ranker/L8 blocker continuity and is reviewing it separately.

## Fixed behavior and retained controls

The controlled non-loam profile has bottoms10/30/60cm, theta.18/.23/.28, FC.25/.28/.32, WP.07/.09/.11, saturation.40/.43/.46 and lab-measured parameter provenance. The same hot/dry daily forcing, LAI3/FVC.8 and soil chemistry are used throughout. Independent expected storage/retentions integrate each candidate posterior over actual layer overlap, not a fixed target constant.

| Control | Fresh current result |
|---|---|
| Original W02,60cm root | Independent posterior storage **137.55mm reaches L4 unchanged**, FC/WP/saturation **.295/.0966667/.44**, loss-engine VWC**.2293** and root**60cm**. The supplied historical137.57 differs by.02mm; its83.30 substitution does not recur. |
| Shallow15cm root | Actual overlap100/50/0mm gives **20.60mm** storage, weighted.26/.0766667/.41, VWC.1373, depth15cm. |
| Requested120cm/profile60cm | Supported60cm, requested120cm, coverage.5 and correct137.55mm. Exact.5 remains outside the chosen `<.50` degradation gate. |
| Requested121cm/profile60cm | Actual pipeline emits coverage.4959, water confidence.465 and downstream degraded status; valid supported aggregates remain unchanged. |
| Healthy deficient-evidence fixture | Soil N1/P1/K10ppm, NDVI.2/NDRE.05, vegetative stage produces **N163.1 and P43.8kg/ha allowed**; K250 is independently blocked by the existing safety limit. State confidence1/.9/.88/.5; health.75/statusok, reliability.5. |
| Same evidence, nonconserved receipt+1mm closure | All prescriptions blocked with `nonconserved_water_transition`; state confidence, L4 health/ceiling/reliability at.2, degraded status and quality reason retained. |
| Same evidence, conserved water health.2 | Nutrient confidence.667/.600/.587/.333; health.4/statusdegraded; ceiling/reliability.333; degradation reason retained. N/P may remain allowed—degradation is not automatically nonconservation. |

Sources, repository-relative under `services/agribrain/`: `layer3_water/contracts/state_factory.py:261–338,424–439`; `layer3_water/contracts/water_state.py:424–472`; `layer4_nutrients/runner.py:192–271,517–546,665–704,798–832`. These verify repaired slices, not empirical calibration of the50% threshold or scalar confidence penalties.

### 8AE03: explicit unsupported-root gate is now non-vacuous

The prior zero-root boundary declares support**0cm**, storage**0mm**, requested60cm/coverage0 while retaining the remaining hydraulic fields, so it is deliberately unsupported/inconsistent metadata that the receiving API must qualify. L4 now passes **root_depth_cm0** and **soil_moisture_vwc0** instead of inventing60cm/.25 at that call. It blocks all three prescriptions with `unsupported_root_boundary`, including the healthy control's previously allowed N/P. All nutrient confidences and health/ceiling/reliability become **.1**; status is degraded and quality includes `UNSUPPORTED_ROOT_BOUNDARY` with the.9 policy penalty.

This repairs the explicit-zero fallback and recommendation-permission behavior observed in the previous candidate. `runner.py:517–523` supplies unsupported placeholders; **678–690** applies the state/prescription gate; **810–820** applies health/quality qualification. A blocked card retaining its proposed rate is not an allowed dose.

### 8AE05: notes now belong to the serialized contract

`layer4_nutrients/schema.py:435–467` now declares `Prescription.notes`. The actual low-health N/P live notes match their nonempty `asdict` values; explicit-zero-root blocked prescriptions also retain the unsupported-root explanation in `asdict`. The old dynamic-attribute omission no longer occurs. This closes the stated dataclass-serialization defect in the checked scope, without claiming a separately unexecuted UI/rendering path.

## Remaining finding1: unsupported zeros still become unqualified loss estimates

**Reproduced full-L4 environmental-output qualification defect; review priority P2.** This is separate from the repaired hard prescription block.

In the explicit-zero-root dry case, the actual loss engine receives root0/VWC0 and returns:

- leaching**0/LOW**, with a no-significant-drainage explanation;
- denitrification**0/LOW**, with **“Aerobic conditions — denitrification risk is low”**;
- total modeled loss**6.56kg/ha**, overall**LOW**, effective N available**173.44kg/ha**, and **“All pathways within acceptable limits.”**

Those zeros are **unsupported placeholders**, not evidence that soil is dry/aerobic or that root-zone losses were measured or validly estimated. A legitimate measured zero drainage can support a zero leaching flux; it does not establish missing soil-moisture state or the validity of all pathways. The output dataclasses (`environmental_losses/engine.py:37–66`) contain no per-path availability/domain/status field that distinguishes unsupported calculation from a valid physical zero.

The second bounded addition makes the numerical consequence visible. It keeps explicit root support0/storage0 and declares **20mm drainage**. Actual full L4 calls the same engine with depth0, thetaFC.295, VWC0 and preliminary N input180kg/ha. It emits **leaching104.4kg/ha/HIGH**, denitrification0/LOW, total110.96, effective N69.04 and overallMODERATE. The104.4 value is written into the emitted **N budget's leaching_loss**. All prescriptions correctly remain blocked with unsupported-root health.1.

The leaching result follows the engine's arithmetic, not a validated root-domain inference: `soil_water_mm=theta_fc*root_depth_cm*10=0`; `drainage/max(1,soil_water_mm)` becomes20/1, capped at1; soluble fraction is `.8−.22=.58`, so `180*.58=104.4`. This silently supplies a1mm denominator on an unavailable physical domain (`engine.py:219–231`). VWC0 similarly creates zero WFPS and an aerobic denitrification interpretation (`engine.py:134–139,328–365`). Aggregate notes/available-N are emitted at **163–189**, and L4 uses those scalars in budgets at **590–623**, before the later permission/health gate.

The180kg/ha is the L4 model's preliminary demand passed to a parameter named applied N (`runner.py:513–516,534`); it is not independently verified applied fertilizer. This report does not interpret the modeled loss as a realized field measurement or re-open broader N-pool work. The concrete failure is that unsupported physical quantities still acquire ordinary loss/risk/available-N semantics despite correct top-level blocking.

**Fix/acceptance:** qualify support and physical missingness at the loss-engine boundary and in the emitted loss/budget contract. Return unavailable/qualified modeled values for water-dependent pathways when their domain/state is unsupported; preserve legitimate zero values when their required support is established. Retain independent pathways only with explicit valid input/support assumptions. Do not feed unknown leaching/denitrification into a physical mass budget as known0 or104.4. The zero-support dry and20mm fixtures must keep the hard blocks and notes while exposing unavailable loss components and a correspondingly qualified budget, rather than a low-risk/all-acceptable or arbitrary-domain numeric estimate. Healthy valid-support controls must retain their finite outputs.

## Remaining finding2: absent canonical support takes a default-positive support path

**Reproduced standalone API missing-support behavior; review priority P2, app exposure unestablished.** The first additional fixture supplies no canonical L3 water object and no daily weather, retaining only the healthy deficient nutrient evidence. L4 constructs its default SWB at `runner.py:284–301`: generic FC/WP/saturation.30/.15/.45, TAW150, moisture0, statusOK and default supported depth**60cm** (`schema.py:279–286`).

The new gate tests only positive depth at **517–518**, so this default60cm is accepted as support. The loss engine receives **root60cm/VWC0**, again producing the LOW/acceptable6.56kg/ha output. Full L4 returns **N163.1/P43.8 allowed**, confidence1/.9/.88/.5, health.75/statusok/reliability.5, no hydrology missing-driver entry and empty prescription notes. Its physical support is a fallback, not an actual supplied root boundary.

This is distinct from bypassing the repaired explicit-zero block: omission follows a separate compatibility/default branch. The API documents standalone research use and the full orchestrator may impose additional authority gates. These receipts do **not** demonstrate that a user can force this path into live operational advice or an actuator. They establish that the standalone output does not distinguish its root/water prior from qualified canonical support.

**Fix/acceptance:** track boundary presence/source/availability separately from numeric depth. Mark absent canonical support as unavailable or explicitly prior/scenario, including relevant downstream loss/budget/health and prescription authority. Do not infer support solely from a default-positive schema scalar. This exact no-canonical/no-weather fixture must not produce a healthy canonical-root interpretation. Test the actual outer authority path separately before asserting operational closure.

## Retained scientific qualifications

The inherited-uncertainty control still changes receipt water confidence.938→.1 and transpiration-deficit sigma.412→2.145mm, while generic-degraded L4 quality/confidence retains the fixed1.5 policy discount. That is a previously established quantitative propagation limitation, not new evidence of empirical miscalibration. No exact error-probability claim can be certified by these fixtures. Full nonzero multi-day drainage accumulation/replay, whole conservative N pools and physical actuation remain outside scope.

Normative basis: master repair plan **F10:389–413**, stage4/dependenciesF03/F04/F05, especially missing-support/uncertainty step4; tasks `ST04-F10-01..04/FA:546–571`; sequencing addendum line9 for slice acceptance. R3 supplied scientific sections: **AB-DAT-005675–677**, **AB-DAT-007683–685**, **AB-AGR-008874–876**, **AB-AGR-010882–884**, **AB-ARC-006742–744**. The repaired explicit-zero hard gate and serialization earn their scoped credit; unknown→physical-loss output qualification and absent-boundary defaults remain distinct follow-ups.


---

# Specialist appendix: Concurrent resource ownership and driver admission

# Resource-phase verification — 4788dac

**The original 8AE01 after-fence lease race is repaired in the executed software schedule. Delayed-idle and before-fence lease controls also retain their fixes. A separate admission/lifecycle regression remains: two idle contenders can both be classified as in-flight before either enters transport, leaving both STOP_REQUESTED and blocking a later ordinary submission.**

Pinned source: `4788dac8c56e4ec8d2caecc53317fd5c5144f675`, parent `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`. Current production bytes were freshly imported and checked against the candidate tree; `source-import-manifest.json` records 35 imported production files. Prior results, repository tests and audits are not proof for this candidate.

## Repair credit: ownership now survives unresolved transport

The original two-OS 8AE01 schedule pauses A inside its inert `send_command`, after the production fence but before its START effect. B waits a real 31.1 seconds, truthfully samples idle and submits normally. **B is now refused.** A resumes and produces the only START effect. A returns EXECUTING with its active command, reservation token and resource-map owner consistent; B returns STOP_REQUESTED without a START. No competing takeover or EXPIRED→EXECUTING revival occurs in this schedule.

The substantive correction is an atomic STARTING→DISPATCHING transition immediately before entering transport: [`dispatcher.py:934–961`](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/irrigation_runtime/dispatcher.py#L934-L961), [`safety.py:1729–1787`](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/irrigation_runtime/safety.py#L1729-L1787). Entered DISPATCHING/SENDING transport is no longer revocable merely by lease age (`safety.py:1661–1663`). Pre-admission STARTING remains expirable; the before-fence real-time control still gives one START from B and a failed revived A.

The candidate additionally guards late promotion against revoked/terminal reservations and owner-token changes (`safety.py:971–987`) and checks ownership after a successful command result (`dispatcher.py:685–732`). Those guards were inspected; this pass did not create a direct claim-API mutation to exercise every post-ACK guard branch.

## P1 — pre-admission reservations are mistaken for entered transport

This is a fresh **ordinary-submission, OS-process lifecycle counterexample**, distinct from the repaired duplicate-effect race.

The retained simultaneous-idle barrier runs A and B through normal `submit_event` calls on one resource. Both truthfully observe ONLINE. Both return STOP_REQUESTED, neither has an active command, and the inert controller records **zero effects**. The second retained barrier also gives zero effects; because A never starts, that schedule now waits for A's submission return rather than reaching the intended ACK state.

The one adjacent lifecycle check repeats the idle pair, then starts a fresh third OS worker submitting C normally. C also returns STOP_REQUESTED without a START. All workers exit normally. Pre-query snapshots show A/B reservations already marked DISPATCHING, with `claimed=true`, quota-owner strings such as `7:A`, and **no resource-map permit**. These events have not passed `transition_to_dispatching` or entered effect-producing transport. After refusal, A/B retain STOP_REQUESTED reservations; C encounters those records.

Evidence: `original-results.json#/barrier_two_OS_processes` and `admission-lifecycle-results.json`. This is an observed admission/availability regression in the submitted lifecycle. **No periodic monitor or recovery was invoked, so this report does not claim a universally permanent deadlock or absence of external recovery.**

### Mechanism

Two existing pre-admission writers still use the same phase name now reserved for unresolved transport:

- [`safety.py:745–763`](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/irrigation_runtime/safety.py#L745-L763) creates an initial quota reservation with `status="DISPATCHING"`.
- [`dispatcher.py:483–493`](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/irrigation_runtime/dispatcher.py#L483-L493) calls `update_status(DISPATCHING)` before live query/resource admission. The new update logic marks it claimed and assigns `executing_ts` (`safety.py:998–1012`).
- [`claim_resource():1661–1666`](https://github.com/webClone/AgriWise/blob/4788dac8c56e4ec8d2caecc53317fd5c5144f675/services/agribrain/irrigation_runtime/safety.py#L1661-L1666) unconditionally blocks a competing DISPATCHING row as entered transport. Both idle contenders therefore block each other; refusal changes each row to STOP_REQUESTED, which continues blocking a fresh C.

The new irrevocable transport policy is appropriate for genuinely entered transport. Its inputs also include earlier reservation/preflight phases, producing the regression.

### Required correction and acceptance

Keep the atomic transport transition and real in-flight protection. Give quota reservation/pre-admission a distinct phase, and allow the current resource-token transition to be the authority for entry into effect-producing DISPATCHING. Handle positively unsent contenders with an explicit failed/deferred/retry policy and appropriate reservation cleanup, while preserving ownership for genuinely uncertain transport outcomes.

Retain the repaired delayed-idle, before-fence and after-fence lease controls. For the simultaneous truthful-idle admission schedule, require a consistent winner/deferred-loser or documented bounded recovery; both unsent events must not acquire indistinguishable nonrevocable transport state. Verify a subsequent request can progress after the rejected contenders are resolved.

## Fresh outcome matrix

| Schedule | START effects | Result |
|---|---:|---|
| Original delayed idle sample, A ACK before B reply | 1 | A EXECUTING; B STOP_REQUESTED — fix retained |
| Original query exception after A execution | 1 | A EXECUTING; B STOP_REQUESTED — fix retained |
| Retained simultaneous two-OS idle barrier | 0 | Both STOP_REQUESTED — phase/admission regression |
| Retained B reply held until A submission returns | 0 | Both STOP_REQUESTED; ACK state never reached |
| Original before-fence real 31.1s lease | 1 | B EXECUTING; expired A FAILED — fix retained |
| Original 8AE01 after-fence real 31.1s lease | 1 | A EXECUTING; B STOP_REQUESTED — **8AE01 repaired** |
| One adjacent ordinary lifecycle: idle A/B, then C | 0 | All three STOP_REQUESTED; no transport effects |

The original exception comparison uses independent same-process dispatchers, matching its authored fixture. Race/lease/lifecycle checks use actual OS workers sharing the real quota-store/file-lock implementation in private folders. All requests use `device` / `zone` / `plot`. No current case directly reissues a token through the claim API. The inherited helper's pause-point label does not change that: the after-fence competitor uses ordinary `submit_event`, not an API token-replacement fixture.

## Evidence, reproduction and readiness boundary

`timelines.json` and `timelines.md` retain query request/sample/return times, production query timestamps, local START/ACK times, pauses and durable phase timestamps where present. Exact source references and package mappings are in `coverage.json`. R3 section 183 and AB-EXE-002/003/004 plus AB-ARC-008 apply to Stage 6 F16–F19 execution ownership. This audit supports the specified software repair, not complete package or field readiness.

Run from the workspace root:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-4788dac-review/protocol/run_originals.py
PYTHONDONTWRITEBYTECODE=1 python repair-4788dac-review/protocol/run_fixed_ttl.py
PYTHONDONTWRITEBYTECODE=1 python repair-4788dac-review/protocol/run_transport_boundary.py
PYTHONDONTWRITEBYTECODE=1 python repair-4788dac-review/protocol/run_admission_lifecycle.py
PYTHONDONTWRITEBYTECODE=1 python repair-4788dac-review/protocol/build_receipts.py
```

Each lease entrypoint takes about 33 seconds; the two are independent and may run concurrently. The copied `resource_*_probe.py` and `run_adjacent.py` are scheduling helpers, not extra required scenarios. Exactly one adjacent ordinary lifecycle case was added. No production source, clock, admission predicate or ledger bytes were patched. All command effects are inert local collaborator effects; **no delivered water, real device, network transport, broker, service or hardware behavior was measured**. There were no production/Git edits or production-store access.


---

# Specialist appendix: Public-store phase and quota contracts

# Shared dispatch phase and accounting review

Pinned candidate `4788dac8c56e4ec8d2caecc53317fd5c5144f675`, parent `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`.

The candidate adds useful in-flight retention and late-promotion guards. Two bounded production-store probes found a phase-identity problem before transport and a same-event claim idempotence gap. Neither probe sends commands or demonstrates physical overlapping irrigation. The separate protocol lane owns the original 31-second transport regression; no claim about its result is made here.

## Scope and reproducibility

Exactly two probes ran against actual public `SharedQuotaStore` writers with private local files and an injected clock. No store record was hand-edited. All state changes came from `atomic_check_and_reserve`, `claim_resource`, `transition_to_dispatching` or `update_status`. Read-only snapshots use the JSON store for evidence. No repository test/audit claims, service calls, drivers, credentials, hardware, production/Git edits or network operations were used.

`source-manifest.json` blob-verifies every imported production module against the exact candidate tree, with local paths, SHA-256 and line counts. The inspected dispatcher is recorded separately as **static only**, because the two probes execute the store rather than `submit_event` or restart reconciliation. `source-diff.txt` preserves the two relevant production-file diffs from the pinned parent. Fresh outputs are in `results.json`.

```bash
PYTHONDONTWRITEBYTECODE=1 python /workspace/scratch/de6bc2428cec/repair-4788dac-review/ownership/probes.py
```

## Passing credit

The positive single-operation control performs admission, claim and the new `transition_to_dispatching`, then asks a competitor to claim after an injected 31 seconds with `live_executing=False` and a newer query timestamp. The competitor is refused; A remains `DISPATCHING`. Unlike the pre-transport `STARTING` lease, this phase is no longer displaced solely by time or an idle query (`safety.py:1645–1684`). This establishes the intended **store boundary**, not a live-controller result.

The second probe confirms new late-promotion guards: after A is expired, `update_status(A, EXECUTING)` leaves it expired; after B is stop-requested, both `EXECUTING` and `DISPATCHING` promotions leave it stop-requested. The guards are at `safety.py:965–1012`. A wrong old owner token is refused by `transition_to_dispatching` after ownership generation changes. The new transition writes reservation and resource-claim phase together under the shared store lock (`1729–1787`). The dispatcher invokes it immediately before command construction/transport (`dispatcher.py:934–961`), and post-ACK fencing now checks durable ownership before promoting (`686–731`). These are concrete improvements.

## SQ01 — admission is already named in-flight before claim or transport

**P1 availability and durable-phase consistency; reproduced with public writer paths.**

`atomic_check_and_reserve` writes `status=DISPATCHING` (`services/agribrain/irrigation_runtime/safety.py:741–765`). This occurs before transport, and even before the resource claim. `submit_event` also persists `DISPATCHING` at `dispatcher.py:484–489`, before the live status query (`519–590`) and `claim_resource` (`593–610`). The new claim logic unconditionally refuses every foreign `DISPATCHING` reservation as in-flight (`safety.py:1661–1663`), without requiring `dispatching_ts` or a resource claim established by `transition_to_dispatching`.

The direct-store schedule admits A and B for the same device/zone. Both admissions succeed and hold 4 mm each. Neither event has called `claim_resource` or `transition_to_dispatching`; no transport exists in this probe. A's claim refuses B; B's claim refuses A. Applying the actual dispatcher refusal-path writer (`update_status(..., STOP_REQUESTED)`, `dispatcher.py:600–608`) leaves both reservations stop-requested, with **8 mm still reserved**, and a later C claim remains blocked. Performing A's refusal write before B's claim does not remove the blocker, because `STOP_REQUESTED` is also protected.

This is a false unresolved-transport state and mutual refusal, not unsafe admission of two commands. Conservative quota retention is appropriate for a genuinely uncertain effect, but this particular public-writer schedule has no effect-producing transition at all. The probe does not claim how subsequent device reconciliation will resolve it, or that it permanently leaks quota under all operator actions.

Concrete fix: distinguish quota admission from the resource lease and actual transport phase. For example, an admitted reservation can remain `RESERVED`/`ADMITTED`; `claim_resource` establishes `STARTING`; only successful `transition_to_dispatching` establishes durable `DISPATCHING`. Update pre-send/restart logic consistently so pre-transport quota holders cannot impersonate an in-flight transport. A positively rejected-before-send operation should retain the appropriate audit receipt without acquiring physical stop intent.

Acceptance: two same-resource public admissions followed by concurrent/sequential resource claims must permit one owner to reach transport or return an explicit pre-transport refusal, without both being stuck solely because of admission labels. Preserve the positive 31-second in-flight refusal and STOP uncertainty controls. Check reserved and settled totals independently of physical resource ownership.

## SQ02 — same-event claim demotes an in-flight phase into a new expiring lease

**P2 public-store lifecycle contract; reproduced, dispatcher reachability qualified.**

`claim_resource` documents successful/idempotent ownership when the event already holds the claim (`safety.py:1627–1632`). It skips reservations with the same event ID while checking conflicts (`1641–1643`), then unconditionally increments generation and writes `STARTING`, a fresh timestamp and a new token (`1686–1715`).

The probe executes A admission → claim → `transition_to_dispatching`, then calls `claim_resource` again for A. The method returns success with generation 2, replaces the token, and changes A from `DISPATCHING` to `STARTING`. The original token is now correctly fenced. After 31 more injected seconds, B's claim expires A and succeeds. Thus the public store can make the new non-expiring in-flight protection expiring again through an ostensibly same-event claim.

No normal duplicate-submit dispatcher path is established by this probe. `submit_event` has active-record and already-reserved guards (`dispatcher.py:253–308,428–451`) that ordinarily join the existing event rather than re-enter this writer. The result is a concrete idempotence/monotonic-phase defect in the store API, **not evidence of overlapping hardware commands or a driver bug**.

Concrete fix: make same-event claim idempotent for an existing live owner, returning the existing token and phase. Require an explicit, fenced recovery operation to change owner generation; that operation must preserve dispatch/stop uncertainty instead of converting it back to an expiring preparation lease. Reject automatic reclaims of revoked or stop-requested events without reconciliation.

Acceptance: repeated same-event claim in `DISPATCHING` retains token, generation and non-expiring phase; a competitor remains refused after 31 seconds. Retain old-token rejection after a legitimate ownership transfer, and retain late-ACK guards on expired/stop-requested phases.

## Restart, release and accounting contracts: static boundaries

`transition_to_dispatching` accepts `STARTING` or `DISPATCHING`, checks a supplied token, expires stale preparation, and synchronizes the durable claim. Its token argument is optional and its device/zone arguments are not compared to the reservation's envelope (`safety.py:1729–1787`). The inspected dispatcher supplies the event token and canonical resource; no mismatched-input or missing-token dispatcher defect was demonstrated. Tightening this public contract would make the intended ownership invariant explicit.

`release_resource_claim` only changes reservation phase when it is `STARTING`; it can remove a same-event resource-claim row by event ID without a token (`1790–1811`). Removing the row alone does **not** release an in-flight reservation: `claim_resource` still refuses a foreign `DISPATCHING` or `STOP_REQUESTED` record. Conversely, `release` removes the quota reservation (`1039–1047`) and should remain limited to positively unstarted/refused paths. Physical exclusion and quota accounting are distinct contracts.

`mark_unsettled` changes the durable reservation to `VALIDATING` with `accounting_status=UNSETTLED` and keeps its exposure (`1028–1036`); it does not itself certify delivery or settle volume. `claim_resource` intentionally does not treat validation-only accounting as physical execution. Settlement validates finite measurements, preserves canonical envelope and writes an idempotent settled receipt/journal (`1050–1277`). These paths were inspected, not exercised as a third probe.

Restart explicitly restores `STARTING` as local `DISPATCHING`, preserves durable dispatch/stop phases and conservative timestamps, and keeps `VALIDATING` as an accounting phase (`dispatcher.py:1880–1916`). An online controller with unresolved dispatch is sent to `STOP_REQUESTED`, not assumed completed (`2114–2142`); missing/unknown controllers retain reconciliation exposure. `SENDING` is recognized by the new claim barrier but is not a typed phase or an observed writer path in the inspected dispatcher/restart whitelist. Compatibility with externally created `SENDING` records remains untested; no spontaneous production occurrence is claimed.

The new successful late-ACK fencing branch can return local `FAILED`, remove active tracking and call `track_event_end` (`dispatcher.py:721–733`), which writes durable `VALIDATING/UNSETTLED` (`safety.py:2009–2012`). This conservatively retains quota rather than inventing delivered depth, but local failure versus durable validation needs an explicit settlement/reconciliation receipt. The review did not execute this branch, prove an irrecoverable leak, or assume the command applied. It is an acceptance boundary for the protocol/recovery lane.

## Plan and scientific meaning

The findings concern F16–F18 ownership/quota/uncertain-command boundaries and F20's separation of verified delivery from command outcomes. The supplied plan maps these to AB-EXE-003/004/005, AB-DEC-003 and AB-ARC-008 (master plan F16–F20). A durable phase must identify whether a dose is merely planned/admitted, possibly in transport, stopped or measured. Phase names and ownership changes must not silently turn quota into evidence of delivery, or lose uncertainty on restart. This bounded software review does not validate delivery sensors or field behavior, and does not close the complete packages.


---

# Specialist appendix: Normative readiness and actual serialization/API projection

# Scientific-contract and plan readiness — 4788dac

Reviewed exact main **`4788dac8c56e4ec8d2caecc53317fd5c5144f675`**, parent `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`. This lane verifies normative identity, maps seven production changes to five repair claims, and checks nutrient serialization/API projection. Protocol, full L4 and normalizer regression execution belong to the other review lanes; their reports are not used here as correctness evidence.

**The new declared `Prescription.notes` field survives real raw serialization.** A bounded fixture also confirms that the actual public response adapter publishes degraded L4 status/confidence/flags and blocks recommendations without L8 authorization. Its omission of raw notes/root-depth fields is a projection choice requiring a consumer contract, not automatically a new bug. Qualitative blocks and confidence caps do not establish calibrated nutrient uncertainty, independently validated losses/economics or safe physical execution.

## Exact plans and acceptance identities

All three supplied local normative documents match the candidate's committed `plan/` blobs byte-for-byte:

| Document | Exact candidate Git blob |
|---|---|
| `AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md` | `08d378a65992de859369950599df198e64244f01` |
| `AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md` | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| `AgriBrain_Work_Packages_Task_List_2026-10-07.md` | `8a564647af7e588802537817159117b349ff606b` |

The task list has **52 distinct acceptance headers**, one per master package, with identical package-ID coverage. There are **68 textual FA mentions** because prerequisites/cross-references mention some identities again. This is expected, not an identity discrepancy. `plan-identities.json` records every header's `STxx-Fxx/Txx-FA` identity and exact line. Header existence, checkbox state and source changes are not acceptance execution or a progress percentage.

## Seven production files / five repair claims

| Claim | Changed production files and current lines | Master-plan requirement mapping | Acceptance qualification |
|---|---|---|---|
| 8AE01: dispatch admission/late-ACK fencing | `irrigation_runtime/dispatcher.py` 686–738,930–956; `irrigation_runtime/safety.py` 970–1010,1643–1683,1728–1788 | F16 quota/watchdog (549–573), F17 physical operation state (575–599), F18 ambiguous retry reconciliation (601–625), F09 scoped concurrency (362–387) | Current source adds DISPATCHING admission and lost-owner/final-status fencing. This lane does not execute transport schedules or certify hardware safety. |
| 8AE02: pond storage versus zero capacity | `layer3_water/contracts/water_state.py` 35–50; `layer3_water/soil/layered_water_balance.py` 136–151 | F04 geometry/hydraulics (233–257), F03 integrated flux/state receipt (206–231), F01 numeric admission (151–177) | Removes the positive-capacity exception before checking initial storage. Physical solver and full pipeline regression receipts remain the trajectory lane's scope. |
| 8AE03: unsupported root boundary | `layer4_nutrients/runner.py` 517–543,678–690,810–820 | F10 typed depth-aware boundary and missing-support propagation (389–414), F11 conservative pools/dose semantics (416–440), F05 support-aware observation (259–284) | Preserves depth zero instead of substituting60cm; explicitly blocks prescriptions/caps confidence. Availability of derived transport/loss numbers still needs a scientific contract. |
| 8AE04: dictionary permission merge | `orchestrator_v2/runner.py` 3484–3504 | F10 downstream boundary, F15 immutable hard feasibility (521–547), F38 degraded publication (1131–1171), F40 consumer verification (1205–1231) | Monotone conjunction/reason union is a useful correction. It does not calibrate diagnosis or independently authorize execution. Platform lane owns runtime normalization checks. |
| 8AE05: degraded prescription notes | `layer4_nutrients/schema.py` 434–465; `layer4_nutrients/runner.py` 691–702 | F10 missing support/uncertainty propagation; F38 truthful degraded publication; F40 actual consumer contract verification | Declared notes now survive dataclass serialization; fixture below verifies this. Narrative notes are not a formal calibrated distribution or loss-validity receipt. |

These are requirement mappings, not claims that five whole master packages are complete. In particular, F10 also requires matched depth integration and drainage counted once; F11 requires reconciled stocks/uptake/loss/application pools; F16–18 require the full execution/recovery criteria beyond a software branch.

## Actual scientific data and downstream path

The current L4 runner derives `is_root_supported` from positive supported depth (517–518). Unsupported support now produces depth0 and intermediate VWC0 rather than the prior60cm/0.25 substitution (519–531). This is useful preservation of a boundary signal. However, it still calls `EnvironmentalLossEngine.compute_all_losses` with those scalars (533–546), **before** the unsupported-support prescription gate (678–690). Its `n_applied_kg_ha` argument is `preliminary_n_rate` derived from estimated crop demand (513–516), not independently verified actual applied exposure.

The loss model's root-zone storage uses `theta_fc * root_depth_cm *10` and divides drainage by `max(1,soil_water_mm)` (`environmental_losses/engine.py` 198–239). Output `EnvLossResult` exposes numeric loss, risk, emissions and effective-N fields, plus notes, but no explicit support/availability status (35–66). Thus domain absence can coexist with scalar process-model results unless a downstream consumer carries the boundary qualifier. This is a **remaining F10/F11 scientific-meaning criterion**, not a new demonstrated model-calibration result. No full L4 run or numerical loss experiment was performed in this lane.

The runner positively marks unsupported state/prescriptions (confidence≤0.1, notes, `unsupported_root_boundary`, 678–690) and health/missing-driver diagnostics (810–820). A degraded but supported boundary reduces confidence and adds notes at691–702; this branch can retain allowed prescriptions. Nonconservation takes the earlier fail-closed branch at665–677. These qualitative mechanisms deserve credit while their penalty factors remain policy/heuristic quantities rather than empirical uncertainty calibration.

The raw orchestrator artifact retains `layer_4` and hashes layers through `to_plain_data` (orchestrator runner4394–4427). The nutrient dataclass normalizer feeds L8 at2860; its dataclass projection includes probability/confidence/permission/conservation but omits notes, explicit support depth, degraded-water flag and uncertainty multiplier (3432–3483). L8's nutrient candidate uses probability>0.3 and `min(probability*150,max_rate)` in kgN/ha, and carries permission/reasons/confidence into the card (`layer8_prescriptive/action_ranker.py`196–251). This is a heuristic candidate path, not recovery of L4's physically supported nutrient-dose response or measured marginal economic value.

The separate L4 optimizer does compute a marginal-revenue/marginal-cost optimum under crop-database prices, product costs and declared response parameters (`optimization/engine.py`345–417). Those are useful modeled assumptions. Notes/degraded caps do not validate local response curves, date/currency-specific prices, correlated outcome downside, actual realized losses or causal policy value. Those remain F11/F13 and T05 requirements. Neither code path should be described as observed economic return merely because a scalar is present.

## One bounded serializer/public-adapter fixture

`probes.py` constructs a typed nutrient output in memory, with explicitly labeled **fixture** notes, root depth0, a blocked prescription, a missing-driver diagnostic and an arbitrary example loss scalar. It calls the actual `to_plain_data` and actual `artifact_to_run`. It does **not** run L4 inference, invoke an HTTP endpoint/authenticated namespace, publish a user route, execute normalization or contact a controller. Private plot `P` and synthetic artifact `INERT` are used; no real namespace authority is asserted.

Fresh successful results (`results.json`):

- Raw serialization retains declared prescription notes, root depth0 and `UNSUPPORTED_ROOT_BOUNDARY`.
- The illustrative raw loss scalar remains12, with no loss support/availability-status field. That number was supplied by the fixture; it is **not** a measured or model-generated unsupported-domain loss.
- The real public adapter returns L4 `DEGRADED`, confidence0.1 and `unsupported_root_boundary` in degradation flags. It does not directly expose the raw note or `supported_root_depth_cm` field.
- Recommendations are empty; authorization is `BLOCKED` because L8 is unavailable/degraded. This is a bounded API adapter isolation control, not a safe-execution certification.

API path from source: FastAPI `/v2/run` selects full mode (`app/main.py`3870–3920); `run_full_mode` calls the orchestrator then `artifact_to_run` (`run_entrypoint.py`454–480); the route returns result (`app/main.py`4453). The canonical adapter deliberately publishes layer summaries (run_schema44–92,236–254), while recommendations require verified exact L8 authorization (108–133,365–400,403–465). A consumer may legitimately present a compact summary. The next contract check is whether that summary and UI/diagnostic guidance preserve support/availability distinctions wherever numerical nutrient/loss claims are shown, not whether every raw field is copied to every response.

The first adapter imports were blocked by missing staged dependencies and one transient staging encoding error; those did not execute the fixture and are not candidate production defects. After exact candidate `surface_contract.py` and `fallback_actions.py` were staged, the fresh process completed the same bounded fixture. All **51 imported source blobs** then matched the candidate tree. No fake modules, production-source repair or dependency-version substitution was used.

## Concrete next acceptance packages

1. **F10/F11:** attach a typed availability/support receipt to environmental transport/loss/budget quantities. Preserve physical zero when observed/defined, and represent unavailable root domain distinctly from physical dryness/zero loss. Keep daily versus cumulative drainage and actual applied versus demand/scenario dose explicit. Validate stock/uptake/loss/application closure under declared support.
2. **F38/F40:** verify raw artifact→normalized L8→public summary/UI consumers against a declared projection contract. Retain the passing notes/qualitative-gate behavior, and ensure omitted raw context cannot become an unqualified diagnostic/economic claim. A field omission alone is not an automatic defect.
3. **F13/T05:** qualify uncertainty and economics against independent outcomes, domain/crop/horizon calibration, explicit price/cost assumptions and causal exposure/identification. Confidence caps and response-curve formulas do not replace that evidence.
4. **F16/F17/F18:** use the protocol/ownership acceptance receipts for admission, in-flight state, late effects, stop/reconciliation and physical completion. Software projection/notes tests cannot establish field-controller commissioning or safe execution.

R3 references use supplied `current-plan-review/R3_current_scientific_sections.txt`: zero/missingness AB-DAT-005 **675–677**, units/support AB-DAT-007 **683–685**, bounded degradation AB-ARC-006 **742–744**, probabilistic validity AB-ML-005 **990–992**, calibration/OOD AB-ML-010 **1010–1012**, decision/economic contracts AB-DEC-001…003 **1068–1078**, AB-ECO-001…004 **1080–1094**, execution AB-EXE-001…005 **1106–1124**. The verified plan/task identities and source slices do not close those entire capabilities.

Artifacts: `probes.py`, `results.json`, `plan-identities.json`, `executed-file-manifest.json`, `source-receipts.json`, and `claim-map.json`. Reproduce with Python using `python repair-4788dac-review/ledger/probes.py` from the workspace root; retain sibling exact source/metadata/tree and the normative plan copies under `sr-team-review/plan`. No repository tests/audits as proof, production/Git edits, network/services or hardware were used.


---

# Specialist appendix: Active integration and plan traceability

# Platform eligibility review — 4788dac8c56e4ec8d2caecc53317fd5c5144f675

**8AE04 passes the original dictionary-permission composition and the bounded typed controls.** The current normalizer combines existing and incoming permissions conjunctively, preserves reasons, and carries conservation metadata. The actual ranker and full standalone L8 pipeline retain false permission and BLOCKED fertilizer schedules. The new zero-supported-root L4 block also survives the actual L4→normalizer→ranker→full standalone L8 composition for all N/P/K fertilizer candidates produced by the fixture.

These are bounded internal integration results. They do not certify public-route promotion, a canonical authorization envelope, publication, hardware execution, all serialization shapes, or the scientific accuracy of nutrient rates.

## Source and execution scope

Candidate `4788dac8c56e4ec8d2caecc53317fd5c5144f675`, parent `8ae4b7499766ce9e8a8acd020078e2a152aca5d6`. Source is the exact staged candidate tree at `../source`; every source file named in this report and actually imported by the probe has a matching candidate Git blob. `source-manifest.json` records151 unique files, including138 actually imported candidate files. Counts describe this lane's import/reference corpus, not full-repository correctness.

`eligibility_probes.py` uses the actual L3 engine, actual full `run_layer4_standalone`, actual ranker, scheduler, and **full `run_layer8`**. It executes the exact current `_normalize_nutrient_states` function through AST extraction to avoid initializing the rest of the orchestrator; it does not rewrite the function. One original CEB03 regression also selects the exact L4 physical gate by semantic AST predicate, not a historical line number. All full L4 dependencies and the full L8 engine dependency set are current candidate files. Network connections are blocked in the probe; no DB, provider, service, repository test/audit, hardware or Git operation executes.

Physical-failure inputs are explicit contract fixtures: a freshly calculated L3 WaterState is replaced with a nonconserved receipt/closure2mm, or with zero supported root depth/storage. This verifies downstream failure preservation; it is not evidence that the normal solver spontaneously produces either condition. The unsupported-root fixture follows the coordinated decision review recipe while independently generating its own current source output.

## Executed cases

| Case | Current result through full standalone L8 |
|---|---|
| Full actual L4 with nonconserved receipt | N/P/K deficiency probabilities0.9995/0.9241/0.937, confidence0.20; all generated local prescriptions blocked. Normalizer, ranker and full L8 preserve `nonconserved_water_transition`; three fertilizer schedules BLOCKED. |
| Full actual L4 with zero supported root depth | All nutrient confidence/data-health ceilings0.10. N/P/K local prescriptions blocked with `unsupported_root_boundary`; all three resulting fertilizer actions remain false/LOW and schedules BLOCKED in full L8. |
| Original CEB03 probability0.8 exact-gate composition | The120kg_N/ha internal candidate remains false/LOW, retains `nonconserved_water_transition`, and is BLOCKED through full L8. Its diagnostic rate is not an executable recommendation. |
| **Original8AE04 dictionary case:** preexisting `is_allowed=true`, conserved SWB, blocked typed N prescription | Normalizer now returns false, preserves `regulatory_N_limit`; ranker and full L8 keep the fertilizer action false/LOW and BLOCKED. The prior dictionary override does not reproduce. |
| Adjacent typed control: allowed and blocked prescriptions for the same nutrient | False wins. Both `regulatory_N_limit` and `farmer_prohibition` survive normalizer, ranker, full L8 and BLOCKED schedule. |
| Adjacent dictionary control: preexisting false permission with an allowed incoming typed prescription | Existing false and `preexisting_farmer_prohibition` survive; fertilizer remains false/LOW and BLOCKED. |

All six full L8 calls completed. Every fertilizer action in these cases was present and blocked; none had a CONFIRMED fertilizer schedule. MONITOR remained allowed/CONFIRMED, so this was not a fixture that simply disabled every output. Every full L8 output had `authorization_envelope=None`, consistent with standalone shadow output. `results.json` contains each normalization, ranked card, direct schedule, full L8 output summary and explicit regression assertions; `probe-stdout.txt` preserves execution output.

## Why the repaired behavior is active

All paths below are under `services/agribrain/` unless otherwise stated.

- The actual full L4 primary pipeline receives the canonical water receipt, uses its support and conservation fields (`layer4_nutrients/runner.py:190–273`), handles zero support without inventing60cm (`517–528`), blocks nonconserved/unsupported prescriptions (`665–690`) and emits degraded health plus the corresponding missing driver (`799–820`). Prescription notes are now a declared schema field (`layer4_nutrients/schema.py:465`).
- `_normalize_nutrient_states` is the function called during active L8 input construction (`orchestrator_v2/runner.py:2860`). It merges matching typed prescription restrictions and global SWB nonconservation (`3435–3470`). The dictionary branch now assigns `existing_allowed and incoming_allowed`, merges reason identities, conserves false conservation flags and takes the maximum closure error (`3486–3504`).
- `ActionRankingEngine` reads `is_allowed`, `blocked_reasons`, conservation and numerical confidence rather than replacing a blocked upstream nutrient candidate with an allowed HIGH-confidence one (`layer8_prescriptive/action_ranker.py:213–250`). The scheduler preserves an already blocked action as BLOCKED (`scheduler.py:260–272`).
- Full standalone L8 runs the additional dosing, nutrient interaction, risk, scheduling and invariant stages (`layer8_prescriptive/runner.py:247–608`). The probe executes this function; it does not infer its behavior only from module presence. Final invariants also reconcile schedules after later evidence checks (`invariants.py:286–336`).

The full public route is separately guarded. `src/app/api/agribrain/run/route.ts:829–860` authorizes the plot before executing the backend request (`502`). Python `/v2/run` is at `app/main.py:3870–3871`. Main calls L4 (`orchestrator_v2/runner.py:2653`), uses the exact normalizer, and has independent influence-manifest, tribunal, planning, live weather and soil gates before invoking L8 (`2712–2736,2940–2964`). Those are current static caller traces; this lane did not invoke the authenticated HTTP route, canonical promotion or publication. Standalone semantic hashes and audit gradeA are explicit fixtures isolating blocker continuity, not a claim to have earned real scientific authority.

## Remaining scope limits

The zero-root result proves continuity for the **actual N/P/K prescriptions produced in this fixture**. The normalizer does not directly export the global `UNSUPPORTED_ROOT_BOUNDARY` health driver or supported depth. Its unsupported-root reason reaches a nutrient through matching blocked prescriptions. The actual sulfur state in this fixture has probability0.1192, no local prescription, and normalizes with `is_allowed=true`; no sulfur candidate is generated. `MACRO_NUTRIENTS` contains N/P/K (`layer4_nutrients/schema.py:46`), while L8 iterates all normalized nutrient states above probability0.3. This is a static coverage seam, **not an executed sulfur eligibility bypass or proof a public fertilizer recommendation is exposed**. A broader guarantee for every nutrient should carry typed boundary prohibitions directly rather than relying only on generated prescriptions. No additional sulfur scenario was run, preserving the bounded adjacent-control scope.

This review also does not certify dictionary prescriptions, dictionary SWB objects, arbitrary malformed permission types or all cached serialization forms. Actual full L4 returns typed nutrient states/prescriptions; the dictionary case is an explicit compatibility branch accepted by the normalizer, not an established public input shape.

The previous checkpoint qualification remains static: `layer3_decision/runner.py:2650–2691` serializes soil, memory, initial state and forcing/history rather than the complete transition/analysis/failure receipt. That is a serialization scope observation, not a new restart failure or evidence of inadmissible publication. It was not rerun as a dynamic finding here.

## Plan acceptance and identities

`verify_metadata.py` compares the candidate tree with the supplied normative documents and parent tree. All3 normative plan blobs are exact and unchanged:

| Document | Blob |
|---|---|
| Deep Repair Plan | `08d378a65992de859369950599df198e64244f01` |
| Execution Sequencing Addendum | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| Work Packages / acceptance register | `8a564647af7e588802537817159117b349ff606b` |

There are52 full-acceptance register rows,0checked. The package codes are **F01–F40 plus T01–T12**, not F01–F52. This naming clarification is metadata, not a production defect; unchecked rows are not evidence52 implementations are absent or broken.

The relevant normative acceptance remains **F10** (L3→L4 boundary/degraded semantics; `AB-AGR-008,AB-AGR-010,AB-DAT-007`) and **F15** (final hard action limits; `AB-DEC-003,AB-ECO-003,AB-EXE-001`), with F01/F02 authority/provenance dependencies and F03/F09 receipt/durability scope. `plan-results.json` contains direct master-card requirement sets, sequencing stages and exact supplied R3 line mappings. The repaired regression slices support progress in F10/F15; they do not close every criterion in either package or the entire register.

## Reproduction and advertised commands

From this review directory run `python eligibility_probes.py`, then `python verify_metadata.py`. These are authored offline review commands, and their exact source paths and fixture boundaries are retained in the scripts. Python3.12.14 and installed dependency versions are in `results.json`; a declared production image was not built or certified.

For deployment context only, the repository advertises `npm run api` as `py -m uvicorn services.agribrain.app.main:app --port 8000 --reload` (`package.json:13`), plus `npm run build`/`npm run lint`; `pyproject.toml` declares Python>=3.11 and requirements from `services/agribrain/requirements.txt`. These advertised commands were read, not executed. No repository tests or audit contents were used as correctness proof.

# AgriBrain corrective verification — 6762543

**Completed:** 17 October 2026. **Reviewed main:** `6762543c7b9279fcebf279beaf1689cbbec070fa`. **Parent:** `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`.

## Implementation decision

**Substantial repairs are verified, but “DV01–DV18 all resolved” is not supported.** The original lost-ACK, forecast publication/mutation/scoring, timeout-cache and prescription-boundary cases now pass in the checked scope. Device/zone exclusivity remains absent, and A→B→A continuity now fails with an explicit predecessor conflict. Adjacent regression and qualification cases also remain.

Proceed with bounded corrective implementation using the sequence below. Keep the affected full-acceptance gates open. This does not require pausing independent eligible plan packages or exploratory World Model/Omega research; data and results used for those objectives must meet their relevant scientific contracts.

The highest-priority results are concrete:

- Two actual OS workers sample the same idle device, both send START to its single simulated zone, and both return EXECUTING.
- A refused NEW event sends no START, but its later poll sends STOP to OLD's running operation. OLD remains durably EXECUTING after the simulated controller stops.
- A new START is sent after a predispatch query timeout while `_fault_latched=True`, with no reset.
- Two telemetry processes enter the same primary lock's protected section under a selected live-aged-recovery schedule.
- A→B→A hydraulic continuation fails warm and cold because a scoped A predecessor is compared with the global B head.

These are software simulations and local persistence experiments, not observations of deployed equipment or measured field delivery.

## Scope and evidence

GitHub main and the full nontruncated tree were retrieved; main was rechecked on Oct17 and still points to the reviewed SHA. The delta has **13 production files** and one added historical verification document. The historical document and repository tests were excluded from correctness evidence. All **444 staged production files** match their Git blobs in the current tree; lane-specific imported dependencies were verified separately. Overlapping source counts are not independent review counts.

The six workstreams were covered by five specialist agents plus the coordinating reviewer. The delegated telemetry worker was blocked by its service's content filter; the coordinator completed that lane through direct source inspection and executed isolated probes. Its conclusions do not depend on the failed worker. Original harnesses were reused as authored code, not accepted as previous-result evidence; current production outputs determine the verdicts.

The user's suite counts sum to **701 reported passing tests**: 478+124+84+15. This review did not inspect those test files, rerun the suite, or independently certify those counts. The user's local working-tree-clean claim is also not independently observable from the remote GitHub read. No production code or Git state was changed by this review, and no external service, broker, controller, field actuator or drone was operated.

The R3 monograph remains the target, with 153 scientific requirement IDs. Verified PDF SHA-256: `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`. The three normative plan documents exactly match current-tree bytes and are unchanged from the parent. Their full-acceptance register has **52 unique rows, all open, zero checked**. That register state is governance evidence, not proof that every package is technically defective.

## DV01–DV18 disposition

“Original fixed” means the prior precise counterexample no longer reproduces. It does not close the whole F/T package or every adjacent contract. These are the prior review's DV identifiers, not R3 requirement IDs.

| Finding | Current verification | Remaining boundary |
|---|---|---|
| DV01 — applied START/lost ACK | **Original fixed.** Poll sends STOP, confirms cessation, then releases active tracking. Failed/exceptional STOP retains STOP_REQUESTED, watchdog and 8 mm exposure. | Refused-NEW handling regresses the foreign-owner cutoff control; see R02. |
| DV02 — device/zone exclusivity | **Open.** Two OS workers both send START and have EXECUTING reservations for the same resource. | Per-event idempotency and water quota do not supply an exclusive resource lease. |
| DV03 — STOP decoding | **Original fixed.** Contradictory STOP/ESTOP replies reject; nonfinite flags no longer normalize to true; pending-map cancellation race is repaired. | START still accepts a contradictory status/flag reply; see protocol appendix. |
| DV04 — retained fault | **Original stop/fence/dispatcher overwrites fixed.** ERROR is retained in those paths. | Query timeout allows a new START with the latch still set; R03. |
| DV05 — orphan recovery mutex | **Original crash case fixed.** Dead recovery owner is recovered and two subsequent acquisitions succeed. | Age-only takeover of a live recovery guard permits two primary-lock owners; R04. |
| DV06 — cleanup ownership/errors | **Original cases fixed.** One inactive cleanup, later accepted nonce survives, later duplicate rejects; strict rollback OSError propagates and retry succeeds. | General transaction receipt/persistence criteria remain unclosed; no new same-message double-admission claim is made here. |
| DV07 — same-scope CAS observations | **Numerical recovery fixed:** loser continuation and cold winner both 201.15 mm, observations retained. | Losing first request hits an undefined registry and returns `(None,None)`; R06. |
| DV08 — cross-scope rollback | **Original fixed.** B remains free of A state/events and follows fresh B at 448.75 mm. | Full scoped publication still fails in DV09. |
| DV09 — A→B→A | **Open.** Both warm/cold A continuation raise ConcurrencyConflictError; A-only control is 448.11 mm. | Scoped scientific predecessor and global publication token are conflated; R05. |
| DV10 — registered future weather | **Original fixed.** Registered 20 mm rain is recovered; warm/cold/control all 122.75 mm. | New archive scan's cross-scope/orphan/cutoff selection is a static acceptance limit, not newly certified. |
| DV11 — interrupted forecast publication | **Original fixed.** Process interruption leaves no partial final record; valid retry succeeds. Concurrent temp/link and injected link-error controls pass. | Existing corrupt cold record still looks absent; appendix D-01. |
| DV12 — mutation during archive store | **Original fixed.** Disk/cache/return retain p50=1 despite caller changing to99; RMSE against99 is98. | No unchanged mutation defect is carried forward. |
| DV13 — false numeric skill/missingness | **Original fixed.** Nonfinite targets/means reject; unavailable RMSE/coverage/sharpness are null and strict JSON parses. | Evidence qualification, distribution admission and score conventions remain; R11/R12. |
| DV14 — evidence order/cache commit | **Original fixed.** Reordered IDs canonicalize consistently; failed writes no longer append to cache. | Colon-delimited ID encoding collides for distinct evidence sets; R10. |
| DV15 — invalid recommendation becomes dose | **Original fixed.** Missing/NaN/Boolean recommendations and invalid bounds remain BLOCKED with reasons. | Full normalized weather/action schema remains partial. |
| DV16 — modifier violates minimum | **Original fixed.** Actual 21→14.7 mm/min20 case is BLOCKED with `rate_min_safe`. | Full aggregate-resource feasibility was not exercised. |
| DV17 — calendar qualification | **Original fixtures fixed:** old expiry, 2020/2030 horizon, malformed dates, UTC sorting and large duplicate conflict. | Smaller decision-threshold duplicate conflicts and same-day expiry remain; R07/R08. |
| DV18 — ASMAE timeout cache | **Original fixed.** Actual timeout producer→serializer is refused by writer and missed by reader; parent-artifact migration misses. | F38/T11 whole-package criteria remain separate; no new authority promotion demonstrated. |

Preserved hydraulic controls include the exact original warm/cold correction **201.13/201.13 mm**, three accepted readings, valid cancellation, non-noon continuation and historical-query idempotence. The separate CAS continuation fixture uses **201.15 mm**; these values are not interchangeable field measurements. Identical explicit K/epoch replacement retry now passes.

## Remaining implementation register

R01–R12 below are local identifiers for this report. P1 means repair before relying on the affected execution, data-continuity or decision contract. P2 identifies narrower qualification/identity/measurement-contract gaps. These priorities do not rewrite the master plan's package priorities.

### R01 — P1: resource ownership is still per event, not exclusive per device/zone

**F16–F18; stage6; R3 AB-EXE-002/003/004, AB-ARC-008.**

The exact production dispatcher/base actuator/shared quota code is exercised by two independent OS processes, one shared quota file and one inert simulated single-zone controller. A barrier pauses both truthful idle replies before either START. Both then send START, both return EXECUTING and both durable claims name the same device/zone. Both processes exit0. This proves two command effects; it does not measure doubled field dose or claim that every vendor controller lacks its own protection.

The owner token at `dispatcher.py:413–425` is stored under event ID. `safety.py:468–805` checks event payload and plot budget, not a resource claim across distinct event IDs. The live preflight at `dispatcher.py:504–520` is not atomic with resource admission. The same-event positive control sends one START and retains 8 mm, so ordinary event idempotency is working and does not solve the different-event case.

**Implement:** an atomic shared claim for the actual exclusive controller/zone resource under a declared capability policy. Bind immutable event payload and an owner/fencing generation to the resource and exposure reservation. Join compatible retries, reject incompatible or foreign claims before physical send, and fence stale commands at the driver/controller boundary where supported. A query is useful evidence, not the resource lock.

**Acceptance:** two workers racing for an exclusive zone produce one physical START effect; same-event retries remain idempotent; legitimate independently operable zones follow their declared capability policy; restart retains the authoritative claim.

Sources: [irrigation_runtime/dispatcher.py#L409-L425](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/irrigation_runtime/dispatcher.py#L409-L425), [irrigation_runtime/dispatcher.py#L504-L520](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/irrigation_runtime/dispatcher.py#L504-L520), [irrigation_runtime/safety.py#L468-L805](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/irrigation_runtime/safety.py#L468-L805).

### R02 — P1: the refused operation's poll stops a different live operation

**F16–F19; R3 AB-EXE-003/004, AB-ARC-008.**

OLD starts for20minutes. A second driver/dispatcher queries the same simulated device as EXECUTING, refuses NEW's START, and retains NEW as STOP_REQUESTED. NEW has no active/pending command, no acknowledged start, zero START effects and no device hazard. At66seconds, polling NEW sends EMERGENCY_STOP to OLD, cancels NEW and leaves OLD's durable record EXECUTING even though the simulated hardware is stopped.

The previous never-started shortcut caused unsafe lost-ACK finalization. The new predicate repairs that case but no longer distinguishes this positively refused request across workers. The local `act_cmd_eid` guard has no command in the new driver instance; it does not consult the durable live resource owner. Missing local command identity is not evidence that the polled event owns the running device.

**Implement:** persist admission/refusal and transport phase explicitly. Couple stop rights to the authoritative resource claim and generation, while preserving device-level hazard cutoff. Do not assign a physical STOP obligation or delivery exposure to an operation positively refused before send. Do not infer positive refusal merely from missing ACK.

**Acceptance:** repeat both fixtures together: lost ACK must stop/reconcile the possibly applied own operation; refused NEW's event watchdog must issue zero STOPs against OLD, with consistent durable status. Device pressure/electrical faults must still stop the actual resource owner.

Sources: [irrigation_runtime/dispatcher.py#L830-L995](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/irrigation_runtime/dispatcher.py#L830-L995), coordinating `resource-claim-results.json`.

### R03 — P1: a query timeout masks an independent latched fault

**F17–F19; R3 AB-EXE-002/003/004.**

The protocol fixture runs normal submit→EXECUTING→fault query→positive fault-bearing stop. ERROR and `_fault_latched=True` survive, and a subsequent healthy query still returns ERROR. No reset occurs. The next submit's status query times out to UNKNOWN; predispatch rejects only `live_st==ERROR` **and** latch. Base START validation also checks transient status rather than the independent latch. The new START is sent and acknowledged EXECUTING with the latch still true.

**Implement:** enforce latched fault independently of connectivity/query status before every START/PULSE path. Specify and implement qualified reset evidence explicitly; a timeout or healthy heartbeat is not an implicit reset. STOP remains available. Share command-specific contradiction handling with START: `{status:STOPPED,running:true,stopped:false}` still succeeds for START while query/STOP reject it.

**Acceptance:** the exact timeout-after-fault fixture emits no new START; qualified reset restores admission; late START/fence/STOP retain the repaired ownership and fault behavior. Treat bare OK according to a declared vendor contract rather than generic physical-start evidence.

Sources: [irrigation_runtime/dispatcher.py#L504-L520](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/irrigation_runtime/dispatcher.py#L504-L520), [irrigation_runtime/actuator.py#L205-L214](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/irrigation_runtime/actuator.py#L205-L214), [irrigation_runtime/drivers/mqtt_driver.py#L379-L417](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L379-L417), [irrigation_runtime/drivers/mqtt_driver.py#L563-L573](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L563-L573).

### R04 — P1: a live aged recovery guard can be stolen

**F39; stage3; R3 AB-DAT-003/011/013, AB-ARC-008.**

The original crash-orphan and cleanup cases are repaired. However, recovery cleanup at `security.py:151` uses `age>30 OR owner-dead`, so age alone removes a live owner's guard. A controlled two-process schedule pauses A after the actual primary owner-text check before unlink; ages A's recovery-file mtime31seconds while confirming A alive; lets B recover and enter the real primary protected section; then resumes A's stale unlink. A enters while B remains inside: **maximum protected-section owners2, expected1**, both exit0.

This is explicit scheduling/mtime fault injection representing a slow/live recovery owner, not a measured production latency or newly demonstrated lost update. No lock decision predicate is replaced. The primary unlink and guard cleanup are path operations without an atomic owner/inode fence.

**Implement:** a process-safe lock primitive or properly fenced storage transaction for the supported deployment. Do not invalidate a live owner from elapsed time alone or delete a newer guard by path. Preserve recoverability after process death and explicit strict I/O failures.

**Acceptance:** same/unique process, ten-thread, original crash, single-cleanup, strict rollback and live-aged-recovery controls together must retain one owner. Full raw/normalized persistence and receipt criteria remain distinct full-F39 obligations.

Sources: [sensor_runtime/security.py#L138-L200](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/sensor_runtime/security.py#L138-L200), telemetry appendix and current `actual-nonce-results.json`.

### R05 — P1: scoped predecessor lookup and publication CAS disagree

**DV09/F09; stage3; R3 AB-DAT-012/013, AB-ARC-008, AB-AGR-006.**

A Jan2 and B Jan3 commit for the same tenant/namespace/plot but different cycle/geometry. Scoped lookup correctly recovers A, but A Jan4 continuation compares that expected A head with the global latest B head at save. Warm and cold both raise ConcurrencyConflictError without a concurrent writer; isolated A control is448.11mm. This replaces the old silent numeric drift with an explicit failure, but does not satisfy continuity.

**Implement:** distinguish the full-scope scientific predecessor from the global publication generation. Validate/update the scoped predecessor atomically under the shared plot lock, preserving other scoped heads. Legacy discovery must produce the same compatible scope and identity.

**Acceptance:** A→B→A succeeds warm/cold and matches A-only; B remains intact; incompatible successors for one scope still conflict correctly.

Sources: [layer3_decision/runner.py#L1268-L1284](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer3_decision/runner.py#L1268-L1284), [world_model/canonical_worldline.py#L251-L294](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/canonical_worldline.py#L251-L294), [world_model/canonical_worldline.py#L310-L315](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/canonical_worldline.py#L310-L315), [world_model/canonical_worldline.py#L365-L400](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/canonical_worldline.py#L365-L400).

### R06 — P1: winner recovery references an undefined registry and returns null

**DV07/F09 plus F38; R3 AB-DAT-012, AB-ARC-006/008.**

The same-scope CAS loser now restores all winner observations and its next request matches cold recovery at201.15mm. The losing first request logs undefined `_PLOT_INIT_WATER_STATE_HISTORY` at runner1544 and returns `(None,None)` instead of the classified CAS outcome. The defined registry is `_PLOT_INITIAL_STATE_HISTORY`. This is a failure-receipt/control-flow defect, not the repaired numerical evidence-loss defect.

**Implement:** use the actual registry and one complete typed winner-hydration function for cold, rollback and historical recovery. Preserve the original conflict as an explicit exception or typed receipt after recovery; do not silently return a null success path.

**Acceptance:** one process publishes, the other emits the expected conflict without undefined-name logging/null return; follow-up retains all observations and equals the winner control.

Sources: [layer3_decision/runner.py#L1497-L1546](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer3_decision/runner.py#L1497-L1546), [layer3_decision/runner.py#L790-L801](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer3_decision/runner.py#L790-L801).

### R07 — P1: duplicate-weather resolution ignores decision-relevant conflicts

**F15; stage5; R3 AB-DEC-003, AB-ECO-003, AB-EXE-001.**

The large 0/100mm duplicate case is fixed. Two same-day spray rows with rain0 and1mm are not considered conflicting because the new precipitation difference threshold is5mm. Dry-first confirms; reverse order blocks at the actual spray limit0.5mm. Wind5 versus16km/h and temperature25 versus42°C can also discard a hazardous second row. Final invariants execute in these cases.

**Implement:** canonical source/version identity and a decision-aware duplicate policy. Reject incompatible support, select an explicitly authoritative version, or intersect the relevant constraints conservatively. A generic5mm discrepancy threshold cannot establish consistent spray eligibility.

**Acceptance:** row order cannot change eligibility for conflicting duplicates; identical duplicates and qualified version selection remain deterministic. Verify rain, wind, gust, temperature and validity together with the repaired original fixtures.

Sources: [layer8_prescriptive/scheduler.py#L155-L179](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer8_prescriptive/scheduler.py#L155-L179), decision appendix.

### R08 — P1: same-day expiry is compared with row midnight rather than planning time

**F15; R3 AB-DEC-003, AB-EXE-001, AB-DAT-014.**

Planning begins Oct13 at12:00Z, but an Oct13 daily row whose `valid_until` is08:00Z still confirms because row midnight precedes expiry. Malformed declared validity is ignored. A valid same-day14:00 row with18:00 validity confirms appropriately. Supplied `valid_from` and `issued_at` are unused, but their stronger support/cutoff interpretation remains policy-dependent until the typed boundary is defined.

**Implement:** separate forecast issuance/availability from weather-valid time and actionable slot. Parse declared timestamps in UTC, reject malformed declared validity, and intersect the supported interval with the actual planning-start instant. If only daily intervals are supported, declare that policy instead of accepting and then discarding timestamp precision.

**Acceptance:** expired-before-planning same-day rows block; valid current slots pass; offsets, validity starts, knowledge cutoffs and the previous old-date/horizon cases obey one contract.

Sources: [layer8_prescriptive/scheduler.py#L82-L107](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer8_prescriptive/scheduler.py#L82-L107), [layer8_prescriptive/scheduler.py#L270-L319](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer8_prescriptive/scheduler.py#L270-L319).

### R09 — P2: equivalent weather units still diverge across modifiers

**F15/F06 boundary; R3 AB-DAT-007, AB-DEC-003.**

The runner now fixes numeric-string temperature. It does not normalize physical units and aliases before every consumer. The unchanged frost modifier emits3.3mm/hr for2m/s and4.1mm/hr for equivalent7.2km/h under the same−5°C forecast; a `t_min_c` alias produces no frost card. Scheduler knots conversion works, but unrecognized mph is treated as multiplier1. These are raw modifier/function results, not field prescription or execution evidence.

**Implement/acceptance:** one qualified weather representation for values, units, aliases, ranges, time and support before modifiers. Equivalent physical inputs must produce equivalent output; unknown units and invalid ranges must have an explicit rejection/conversion policy. The decision appendix separately records missing/incompatible action-unit and unbounded-cap schema cases without inventing actuator reachability.

Sources: [layer8_prescriptive/runner.py#L291-L316](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer8_prescriptive/runner.py#L291-L316), [layer8_prescriptive/engines/frost_sprinkling.py#L27-L72](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer8_prescriptive/engines/frost_sprinkling.py#L27-L72), [layer8_prescriptive/scheduler.py#L194-L218](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer8_prescriptive/scheduler.py#L194-L218).

### R10 — P2: evidence-ID encoding can collide despite repaired canonical order

**F23; R3 AB-DAT-011, AB-ARC-008/009.**

Reordered evidence now has consistent ID/payload, and failed writes stay out of cache. Distinct sets `['A:B','C']` and `['A','B:C']` still yield the same colon-joined signature and evaluation ID. The second payload conflicts; no overwrite or failed-cache append occurs. Compatible retries also append duplicate references in memory; downstream double weighting was not tested.

**Implement/acceptance:** hash an unambiguous canonical object/list encoding; make evaluation history idempotent by ID or explicitly deduplicate consumers. Distinct sets get distinct IDs; order-only retries reuse the existing record; memory/disk membership remains consistent.

Source: [world_model/forecast_archive.py#L649-L673](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/forecast_archive.py#L649-L673).

### R11 — P2: archive and evidence admission remain weaker than scoring validation

**F23/F24; R3 AB-ML-005/008/010, AB-DAT-005/007/011.**

Scoring now rejects invalid quantiles, but archival admission can persist NaN, crossed or illegal-level quantile maps. Aliases `p50` and `0.5` can conflict at one level and still score numerically. Nonempty evidence syntax accepts `['']`, `[None]` or scalar `'AB'`, without a resolved qualified target receipt. These are direct API boundaries; no deployed upstream service or operational use is asserted.

**Implement/acceptance:** validate/canonicalize the supported distribution before immutable commit, retaining scoring validation as defense in depth. Require typed nonblank IDs and a bound qualified target receipt with variable, units, time, domain and support, or prove the documented upstream qualification boundary. Missing data must not inherit a default valid-domain label. Existing corrupt cold-file read must be distinguishable from absence; the repaired writer itself no longer creates partial final files.

Sources: [world_model/forecast_archive.py#L334-L361](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/forecast_archive.py#L334-L361), [world_model/forecast_archive.py#L536-L599](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/forecast_archive.py#L536-L599), ledger appendix D-01/D-03/D-05.

### R12 — P2: horizon and probabilistic interval conventions remain inconsistent

**F24; R3 AB-ML-005/010, AB-ASM-016.**

For an exactly one-day target interval, declared horizons0.01 and2days pass a1.05-day tolerance; both-naive timestamps construct. If inclusive-calendar or rounded bins are intended, their policy is unspecified. Equivalent normal distributions also disagree on coverage: Gaussian mean0/std1 at observed1.5 returns true and sharpness3.29, while actual p10/p50/p90 quantiles return false and≈2.563103. Gaussian±1.645σ is approximately p05/p95, not p10/p90. The common metric has no nominal interval level. Finite-level pinball averaging also needs an accurate approximation label/integration rule before comparison across grids as continuous CRPS.

**Implement/acceptance:** derive timezone-aware elapsed horizon or validate declared bins precisely; attach nominal interval levels and use matching Gaussian/quantile conventions. Equivalent distributions must agree on the compared metric. Preserve the now-correct finite CRPS, valid point masses and null missing-score components.

Sources: [world_model/forecast_archive.py#L344-L355](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/forecast_archive.py#L344-L355), [world_model/forecast_archive.py#L618-L642](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/forecast_archive.py#L618-L642), [world_model/forecast_archive.py#L231-L260](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/forecast_archive.py#L231-L260).

## Concrete implementation sequence

| Stream | Next bounded change | Closure gate |
|---|---|---|
| A — F16–F19 | Implement one resource ownership/admission state model in shared store and dispatcher; distinguish refused-before-send from uncertain-after-send. Enforce fault latch separately from queried status, and share START/STOP contradiction decoding. | R01–R03 together, including stale watchdog, lost ACK, failed STOP, real multi-process admission and reset controls. |
| B — F39 | Replace/fence file recovery ownership; stop age-only live-owner takeover and unowned guard deletion. Keep single cleanup and strict errors. | R04 plus original crash/same/unique/thread/cleanup controls, maxone protected-section owner. |
| C — F08/F09 | Separate scoped predecessor from global publication generation; fix undefined registry and use one typed recovery function. | R05/R06, A→B→A, same/cross-scope CAS, retained-weather and exact parameter retries. |
| E — F15 | Canonicalize weather once before consumers; define duplicate/version policy and actual actionable validity. Final feasibility must use the same qualified support. | R07–R09 plus all repaired original dose/weather/date cases; deterministic duplicate ordering and physical-unit equivalence. |
| D — F23/F24 | Canonical evidence identity and qualified receipt, validation before archive commit, explicit score/horizon/interval conventions and integrity signaling. | R10–R12 plus existing temp/link/crash/snapshot/null-score controls. |
| F — T11/F38 | Retain verified timeout-cache fix and migration controls; continue already defined full degraded-output/publication criteria. | No new P1 cache defect reproduced. Do not equate this bounded fix with full T11/F38 closure. |

Assign one mutation owner per shared production file; these streams can otherwise progress in parallel under the plan's prerequisites. Correct the governing contract once across callers rather than adding a predicate only for the latest fixture. Keep the existing positive cases in the same acceptance run so a repair cannot silently reopen a neighboring failure.

The original plan's estimate is not a current remaining-effort estimate. No new hours or project-wide completion percentage is inferred from these probes. Complete software acceptance evidence first; field/controller commissioning remains a separate gate. No result here establishes installation-level safety, prospective agronomic skill or full World Model/Omega implementation.

## Static limits and reproducibility

The repaired archive-weather scan is sampled successfully but scans checkpoint files by mtime. Its scope, committed-head membership, issuance/cutoff and orphan selection were not newly fault-tested. Recursive removal of `evidence_hash`/`interval_hash` fixes the parameter retry but changes shared serialization; required lineage preservation is not certified for every caller. These are explicit acceptance limits, not additional demonstrated runtime failures.

The companion bundle contains authored probes, fresh results, source-object manifests, selected plan/R3 requirements and the six detailed workstream appendices. It excludes repository tests/audits, production source copies and generated controller/quota/checkpoint stores. A portable materializer reads exact Git objects into a separate workspace without fetch/checkout changes. Probe exit0 means the recorded observations were reproduced, including counterexamples; it is not a production pass score. The user's701-suite result remains reported rather than independently rerun.

All **12 authored probe scripts** were replayed from a separate layout containing **1,427 verified source copies / 539 unique blobs**. Duplicate dependency layouts account for repeated copies. The Git-object materializer was compiled and its layout verified; it was not executed against a separate full Git checkout here.

Specialist/coordinator appendices follow with exact current line/blob references, controls, injection qualifications, limits and reproduction commands.


---

# Specialist appendix: Trajectory and hydraulic recovery

# Workstream C — actual 6762543 trajectory review

Pinned source `6762543c7b9279fcebf279beaf1689cbbec070fa`, parent `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`. This is a bounded production review of DV07–DV10 and adjacent F08/F09 seams under the master repair plan. It uses the existing completed current-source receipts; no additional probes were added during finalization.

The original DV07 numerical recovery, DV08 cross-scope rollback, DV10 retained-weather and parameter-retry counterexamples now pass. **DV09 remains open:** A→B→A recovers A's scoped head but attempts to compare it against B's global publication head, so both warm and cold A continuation raise a predecessor conflict. Winner recovery also contains a new undefined registry name that turns the losing request into a null result; its subsequent scientific state is now correct.

| Check | Current production result | Assessment |
|---|---|---|
| Original registered-observation correction | Warm/cold **201.13/201.13 mm**, 3 readings each | Pass |
| Same-scope CAS loser follow-up | **201.15 mm**, normal-cold control **201.15 mm**, readings retained | Numerical recovery pass; first-request receipt defect |
| Cross-scope CAS loser | B cache empty; follow-up **448.75 mm**, fresh B **448.75 mm** | Original DV08 pass |
| A→B→A | Warm/cold **ConcurrencyConflictError**; A-only control **448.11 mm** | DV09 open |
| Previously registered Jan 3 20 mm rain after earlier correction | Warm/cold/control all **122.75 mm** | Original DV10 pass |
| Identical explicit K/epoch replacement retry | Same head/state, no conflict | Pass |

## Reproducible residuals

### C-01 — P1: Scoped recovery head is compared against the global publication head

DV09; packages F09; stage 3; R3 AB-DAT-013, AB-DAT-012, AB-ARC-008, AB-AGR-006.

After A Jan 2 and B Jan 3 commit for the same tenant/namespace/plot but different cycle/geometry, both warm and cold A Jan 4 resume raise ConcurrencyConflictError: expected A cp_hyd_p_2026-01-02_e865a17f98fe, found global B cp_hyd_p_2026-01-03_0997ab7d2644. The A-only control returns 448.11 mm. Scoped lookup now recovers A correctly, but save validates expected_predecessor_head against global head_hash/latest_checkpoint_id. No concurrent writer is needed.

Fix: Separate full-scope scientific predecessor from any global publication-generation token; validate the scoped predecessor and atomically update its scoped head under the plot lock.

Acceptance: A→B→A succeeds warm and cold, matches A-only scientific state, preserves B head/history, and still rejects two incompatible successors for the same scoped predecessor.

Receipt: `deep-results.json:scope_A_B_A`.

- [services/agribrain/layer3_decision/runner.py:1268–1284](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer3_decision/runner.py#L1268-L1284) — blob `188c71b7bf58e9a3c3e6b0c0a4989d77ee19cf2e`.
- [services/agribrain/world_model/canonical_worldline.py:251–294](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/canonical_worldline.py#L251-L294) — blob `dd0112c21bc359259c2bae749f83c7c9a28e148e`.
- [services/agribrain/world_model/canonical_worldline.py:310–315](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/canonical_worldline.py#L310-L315) — blob `dd0112c21bc359259c2bae749f83c7c9a28e148e`.
- [services/agribrain/world_model/canonical_worldline.py:365–400](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/canonical_worldline.py#L365-L400) — blob `dd0112c21bc359259c2bae749f83c7c9a28e148e`.

### C-02 — P1: Winner rollback restores observations but hits an undefined registry name

DV07; packages F09, F38; stage 3; R3 AB-ARC-006, AB-ARC-008, AB-DAT-012.

In separate same-scope workers, winner observations are now restored correctly. The losing request logs "name _PLOT_INIT_WATER_STATE_HISTORY is not defined" and returns (None,None), recorded as status returned with state null instead of a classified CAS conflict. That registry appears only at runner line 1544; the defined registry is _PLOT_INITIAL_STATE_HISTORY. Follow-up state is repaired numerically: 201.15 mm, equal to the normal cold control, retaining all three readings. This is a failure-receipt/control-flow defect, not a remaining 109.43/201.15 numerical divergence.

Fix: Use the defined initial-state registry (and full-scope aliases) in winner recovery, and preserve the original ConcurrencyConflictError or a typed conflict receipt after successful recovery.

Acceptance: Both subprocesses exit normally; one publishes, one emits the expected conflict outcome without undefined-name logging or silent null success; loser follow-up retains the winner observations and equals 201.15 mm.

Receipt: `deep-results.json:same_scope_process_CAS_observation_recovery`.

- [services/agribrain/layer3_decision/runner.py:1497–1546](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer3_decision/runner.py#L1497-L1546) — blob `188c71b7bf58e9a3c3e6b0c0a4989d77ee19cf2e`.
- [services/agribrain/layer3_decision/runner.py:790–801](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer3_decision/runner.py#L790-L801) — blob `188c71b7bf58e9a3c3e6b0c0a4989d77ee19cf2e`.

## Controls and harness fidelity

The original correction retains the precise Jan 2 12:00 UTC readings [.4,.4,.4], 120 mm initial prior and declared hydraulic memory, with Jan 2 rain changed 0→1 mm for a Jan 3 target. Warm/cold each execute Jan 2 and Jan 3 once. Both now accept three readings; the previous 109.93 mm cold result is superseded.

CAS scheduling is controlled only at the production save boundary. The same-scope test uses separate processes with the same full scope and store; A commits before B attempts real CAS. Production performs its own rollback and follow-up. The source logs the undefined _PLOT_INIT_WATER_STATE_HISTORY name, and the JSON records B's first status returned with state null. Its follow-up retains [.4,.4,.4] and equals 201.15 mm. The repaired history is legitimately archived without a materialized WaterState; the harness was adapted to record archived_not_reexecuted instead of dereferencing that absent object. That earlier harness assumption is not classified as a code defect.

The cross-scope test uses two full scopes and the same plot store. B receives the real conflict and retains no A memory, history or events. Its ordinary next request matches fresh B. Original A checkpoint bytes remain intact through A→B→A; the remaining problem is publication token mismatch, not deleted checkpoints.

The new weather scan imports world_model.canonical_worldline, while the main adapter imports services.agribrain.world_model.canonical_worldline. Production defaults resolve to the same physical store. The isolated harness redirects **both module aliases** to the same lane directory. Redirecting only one would make the new scan miss the test archive and falsely report the original DV10 as unfixed. The current retained-weather pass uses the corrected isolation setup.

Fourteen inherited focused groups, the exact correction and non-noon gates, and six authored deep cases completed on current source. No new case was added during this finalization. No repository tests/audit outputs, prior authored findings or stored production artifacts are used in place of current production behavior. Prior probe code was reused as harness code; all new data was simulated locally.

Other passing controls include equivalent explicitly dated daily/sparse canopy/weather replay, unchanged cold replay/idempotence, non-noon forward continuation (105 mm), exact historical query (114.13 mm without head advance), valid-ISO cancellation (cancelled v2, zero delivered irrigation), and withdrawal omission after restart.

## Static acceptance limits

**Archive forcing selection — static acceptance boundary; not a newly probed defect.** DV10 scans all checkpoint JSON in the plot directory by file mtime and accepts the first parseable weather for a date. This code slice does not filter cycle/geometry, committed-head membership or issuance availability, and numeric adaptation drops metadata. The original retained-weather repair passes, but cross-scope/orphan/revised-availability and missing-channel behavior were not newly certified in this bounded pass.

- [services/agribrain/layer3_decision/runner.py:1913–1936](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer3_decision/runner.py#L1913-L1936) — blob `188c71b7bf58e9a3c3e6b0c0a4989d77ee19cf2e`.
- [services/agribrain/layer3_decision/runner.py:1079–1127](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer3_decision/runner.py#L1079-L1127) — blob `188c71b7bf58e9a3c3e6b0c0a4989d77ee19cf2e`.

**Evidence/interval hash volatility — static contract change; semantic sufficiency not certified.** evidence_hash and interval_hash are now recursively stripped by shared _public, not merely ignored during retry equality; it also builds persisted checkpoint and general scientific event payloads. The parameter retry passes. This review does not establish that every field with those names is dispensable authoritative lineage. Specify volatile bookkeeping versus retained evidence identity and verify required lineage remains resolvable.

- [services/agribrain/world_model/canonical_worldline.py:69–107](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/canonical_worldline.py#L69-L107) — blob `dd0112c21bc359259c2bae749f83c7c9a28e148e`.
- [services/agribrain/world_model/canonical_worldline.py:317–323](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/canonical_worldline.py#L317-L323) — blob `dd0112c21bc359259c2bae749f83c7c9a28e148e`.
- [services/agribrain/world_model/canonical_worldline.py:375–381](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/canonical_worldline.py#L375-L381) — blob `dd0112c21bc359259c2bae749f83c7c9a28e148e`.
- [services/agribrain/world_model/canonical_worldline.py:503–506](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/world_model/canonical_worldline.py#L503-L506) — blob `dd0112c21bc359259c2bae749f83c7c9a28e148e`.

Scoped-head map updates are inside the existing plot lock and atomic head-file replacement. That static structure does not resolve C-01, and this pass did not add an interrupted-head-write fault experiment. Missing-channel, foreign-scope archive, orphan checkpoint and revised-availability behavior therefore receive no new passing claim.

F08 full predecessor-content acceptance also remains open: the bounded exact-function digest probe still collides for different evaporation surface stores/wetted fractions with equal evaporation days, while a conductivity change is distinguished. Withdrawal reappearance remains an optional unversioned reinstatement-semantics question, not a blocker without a revision contract.

## Master-plan status and reproduction

F08/F09 are stage-3 whole packages. Passing original counterexamples is credited as bounded correction. C-01/C-02 keep F09 full acceptance and the master-plan R1 coupled-trajectory gate open. Their mappings are AB-DAT-012/013, AB-ARC-006/008 and AB-AGR-006; F08 additionally retains AB-DAT-011 and AB-AGR-007 content/forcing requirements. Fix scientific scoped predecessor validation, preserve classified failure receipts, and rerun these same controls before broadening claims.

The accompanying coverage.json contains one status per DV07–DV10, package acceptance, concrete fixes, limits, data/control values and source refs. source-manifest.json verifies all 23 supporting assigned target blobs against the current tree; dependency-manifest.json records four reused dependency blobs verified unchanged. No production/Git file, external service, vendor/controller or hardware was changed or called.

Completed reproduction commands from the workspace root:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-6762543-review/trajectory/probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-6762543-review/trajectory/claim_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-6762543-review/trajectory/gate_probe.py new
PYTHONDONTWRITEBYTECODE=1 python repair-6762543-review/trajectory/deep_probe.py
```

Raw receipts are probe-results.json, claim-results.json, gates-new.json and deep-results.json. The undefined-name log was observed in the completed deep-probe tool output; B's null first result and correct subsequent state are recorded in deep-results.json.



---

# Specialist appendix: Nonce ownership and ingestion

# Workstream B — telemetry file recovery at 6762543

Reviewed `6762543c7b9279fcebf279beaf1689cbbec070fa`, parent `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`. The coordinating reviewer completed this lane directly after the delegated worker could not execute it because of a service content-filter rejection. The conclusions below come from actual production source and executed local probes, not from the failed worker or a modeled repair.

## Verified repairs

The authored `actual_nonce_probes.py` imports the current production telemetry modules. Ten imported files are matched against their current-tree Git blobs. It uses inert sensor messages, isolated temporary registry/calibration/data files and actual OS processes; it does not contact a device, credential service or external system. All subprocess controls completed, and the final script exited 0.

| Prior case/control | Current result |
|---|---|
| Two same-message processes | One accepted reading; the other rejected; fresh process rejects the duplicate. |
| Two distinct-message processes | Both retained; fresh-process checks reject both duplicates. |
| Ten threads | One winner, nine rejections. |
| Registry/calibration/pre-write failures | No nonce/seen/raw residue after rejection; restored retry returns one reading. |
| Original crash inside recovery mutex | The actual child exits after creating a recovery record. Both subsequent acquisitions succeed; recovery file is removed. |
| Original double-cleanup schedule | Old inactive worker releases exactly once. Another worker accepts between release and exception. Its accepted receipt remains, and a fresh later duplicate returns zero readings. All three children exit0. |
| Strict rollback replacement failure | OSError propagates. Exception cleanup makes a second replacement attempt, clears the nonce, and restored retry returns one reading. This is no longer the old silent rollback error. |

Original DV05's orphan-recovery case and DV06's two demonstrated cleanup/error cases are repaired in these controls. Full F39 acceptance requires more than those schedules.

## Remaining P1: age alone can remove a live recovery guard and permit two lock owners

At `sensor_runtime/security.py:151`, the new recovery cleanup condition is:

```python
rec_age > 30.0 or (rec_pid > 0 and not _is_pid_alive(rec_pid))
```

Thus a recovery guard older than30seconds is removed even when its recorded process is alive. Recovery ownership is not fenced through the later primary-lock unlink (`184–189`), and guard cleanup unlinks by path without verifying the token (`197–198`).

The bounded local schedule uses two actual processes and the real production context manager:

1. A detects a dead primary owner, acquires the recovery guard and reaches the actual primary unlink after the production owner-text equality check. The harness pauses that filesystem call.
2. A remains alive. The harness ages its recovery-file mtime by31seconds, representing a slow/live recovery owner; it does not wait or claim measured production latency.
3. B removes the aged live recovery guard, recovers the old primary lock, acquires its own primary lock and enters the protected section.
4. A resumes its stale unlink, removes B's new primary lock, then acquires another primary lock and enters while B remains inside.

Observed **maximum simultaneous primary-lock owners: 2**, expected1. Both processes exit0. Scheduling hooks select the real unlink ordering; no production decision predicate or lock implementation is replaced. This proves broken mutual exclusion under a live-aged-recoverer interleaving. It does **not** claim that a production telemetry update was actually lost or that the same message was admitted twice under this new schedule.

Source: [security.py:138–200](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/sensor_runtime/security.py#L138-L200). Current security blob: `2d8fa7545f3728151ae6d93254a1cc096ba48cf5`; ingestion blob: `1dd6a8bdd20727b5fce668c2941d83459551e9e7`.

## Repair and acceptance

Use a process-safe locking primitive supported by the deployment, or a rigorously fenced store transaction whose owner cannot be invalidated by time alone. A check-then-unlink sequence cannot establish ownership of the inode that remains at that path. Recovery cleanup must not delete a newer owner's guard. Retain explicit crash recovery without granting two simultaneous owners.

Acceptance must include the original same/unique-process, ten-thread, dead-recovery and single-cleanup controls together with the live-aged-recovery schedule. Require one protected-section owner throughout, recoverability after process exit, and explicit strict-mode I/O failure. Durable evidence receipts, complete raw/normalized transactions and scope/retention criteria remain separate full-F39 obligations; they were not newly certified here.

Canonical mapping: **F39 stage3**, prerequisites F01/F09; R3 **AB-DAT-001/003/011/013, AB-ARC-008/009**. The original DV05 reproduction is fixed, but this adjacent mutex counterexample keeps the concurrency contract open. Passing the single-cleanup case does not establish a general owned transaction protocol for all future callers.

Reproduce with `PYTHONDONTWRITEBYTECODE=1 python repair-6762543-review/ownership/actual_nonce_probes.py`. `actual-nonce-results.json` records current source receipts, all positive controls, the strict error and two-owner interleaving. Probe exit0 means the recorded outcome was reproduced; the two-owner outcome is a production contract failure.


---

# Specialist appendix: MQTT protocol and actuator faults

# 6762543 protocol verification — DV03/DV04

**The original DV03/DV04 counterexamples are repaired at the inspected commit. An adjacent dispatcher path still permits START while its fault latch remains set.** This bounded pass executes exact source `6762543c7b9279fcebf279beaf1689cbbec070fa`, parent `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`.

Five core production files independently match the new Git tree (`source-index.json`). The previous 71-row matrix plus stale-query case, 40 additional command rows and targeted lifecycle/fence/dispatcher controls were rerun. One additional reset/timeout integration fixture checks the requested sticky-fault boundary. No production/Git edits, repository tests/audits, cached review results as proof, services, broker or hardware were used. These local controller-reply fixtures prove code behavior for declared replies; they do not establish vendor interoperability, physical cessation or delivered volume. DV01/DV02 and the refused-NEW cutoff case belong to root's separate lane.

## Repairs verified

**DV03 — STOP contradictions and pending-request cleanup.** Normal STOP and emergency STOP now reject RUNNING-versus-stopped and STOPPED-versus-running contradictions. Bare OK no longer certifies a normal STOP. The query decoder remains UNKNOWN for contradictory replies. Numeric NaN/infinity no longer normalize to true (`mqtt_driver.py:49–62, 402–439, 475–533, 653–687`). The old mixed fixture containing `running=0` and `stopped=NaN` can still stop because the separate running flag supplies explicit false; this is not evidence that NaN still becomes true. Qualified input semantics must state whether that independent not-running evidence suffices.

The real callback/cancellation interleaving that formerly raised KeyError now returns normally: `pop(request_id, None)` removes the check/pop race (`:257–269`). The explicit duplicate-ID fixture also improves: cancelling the older call leaves the newer Future registered and its positive STOP reply completes successfully. Cleanup now checks Future identity. This is an API boundary control; the normal dispatcher uses per-event/attempt IDs, and ordinary STOP defaults to a UUID. No normal-producer correlation collision is asserted.

**DV04 — Direct/fence/dispatcher fault retention.** A positively stopped FAULT reply leaves ERROR after direct stop, after the late START fence, and after the tested dispatcher error-stop path. In the actual `submit_event → EXECUTING → fault query → positive fault-bearing stop` fixture, the event becomes FAILED, a stopped receipt exists, command ownership clears, and actuator ERROR remains. This repairs the exact earlier dispatcher/fence overwrites (`actuator.py:343–360, 551–558`; `dispatcher.py:1159–1172`). Releasing a positively stopped operation while retaining equipment fault is appropriate; a stop ACK does not establish measured volume.

The prior simpler controls remain intact: non-object payload rejection, safe loop wake under asyncio debug and normal callback threads, ordinary cancellation/publish cleanup, finite defaults for ordinary invalid timeout values, explicit START-stopped/STOP-running rejection, and UNKNOWN after unanswered status queries. A late unmatched ACK does not promote operational state. Supplementary extreme-integer/API fixtures are retained in results with their limited scope; they are not deployment settings or the basis for the original DV03/DV04 verdict.

The rejected late-fence control also passes: after initial STOP success and a delayed START ACK, rejection of the second STOP returns STOP_FAILED, leaves ERROR, and retains the original active command (`fence_failure_results.json`). The successful stop-generation repair does not turn a failed fence into confirmed cessation.

## Adjacent actual finding: sticky fault can be bypassed after a query timeout

`fault_reset_probe.py` runs the normal production dispatcher/actuator/driver, with local correlated replies:

1. An event reaches EXECUTING.
2. Its fault query and positive stopped FAULT reply leave the event FAILED, actuator ERROR, `_fault_latched=True`, and a stopped receipt.
3. A fresh healthy STOPPED/zero-fault query still returns ERROR: the latch is sticky, as intended.
4. No reset occurs. A new event's predispatch query receives no reply. The query becomes UNKNOWN, and the new START is sent and acknowledged. Both event and actuator reach EXECUTING while `_fault_latched` remains **true**.

The concrete bypass is `dispatcher.py:504–520`: rejection requires **both** `live_st == ERROR` and a set latch. `get_status():563–573` changes cached status to UNKNOWN on timeout. Base validation tests `_status == ERROR`, rather than the latch independently (`actuator.py:205–214`); START parsing also does not consult the latch (`mqtt_driver.py:379–399`). Consequently the physical-status timeout masks the separate equipment-health prohibition.

This is a new adjacent DV04 counterexample, not a claim that the repaired stop paths still overwrite ERROR. It does not depend on a lost START ACK, concurrent workers, resource-lease collision, or unqualified manual reset. The source contains latch-setting paths but no qualified public reset operation in the selected irrigation runtime; a healthy query alone intentionally does not clear the set latch. Define that recovery contract, and enforce the latch independently of transient query status until qualified reset evidence clears it.

Acceptance: repeat the same fixture and require the new event to be refused/blocked with **no START publication**, while STOP remains available. Also verify that an explicitly qualified reset restores admissible START. Do not use an unanswered query as reset evidence.

## Adjacent ACK boundary retained

The exercised START reply `{status: "STOPPED", running: true, stopped: false}` still succeeds and promotes EXECUTING, while the same reply is UNKNOWN to query and rejected by both stop paths. START's parser does not share the new contradiction check (`mqtt_driver.py:379–399` versus `:402–417`). Bare OK likewise still promotes START to EXECUTING. The latter requires a declared vendor contract if OK is meant to certify physical beginning. The explicit status/flag contradiction should be handled consistently without discarding uncertain post-send ownership. This is an adjacent START case; the original DV03 STOP cases now pass.

## Acceptance matrix

| Case | Actual 6762543 outcome | Assessment |
|---|---|---|
| Contradictory normal STOP/ESTOP | Rejected | Original DV03 repaired |
| NaN/infinity boolean normalization | None, rather than true | Original parser case repaired |
| Callback lookup overlaps cancellation | Returns normally, no pending leak | Original race repaired |
| Older cancellation with reused request ID | Newer Future retained; STOP succeeds | Cleanup control repaired |
| Direct fault-bearing stop | ERROR retained | Original control passes |
| Fault-bearing late START fence | ERROR retained | Original DV04 repaired |
| Rejected late fence | STOP_FAILED, ERROR, original command retained | Failure control passes |
| Tested dispatcher error-stop path | FAILED + stopped receipt; actuator ERROR | Original DV04 repaired |
| Healthy query after set latch | ERROR, latch still true | Sticky positive control |
| New submit after latched fault, query timeout | START sent; EXECUTING with latch true | Adjacent DV04 open |
| START STOPPED word + running flag | EXECUTING | Adjacent command contract open |

R3 section 183 and AB-EXE-002/003/004 require acknowledgement, execution, uncertainty and safety permissions to remain distinct. Preserve the repaired controls; block new actuation on an independent latched fault, define qualified reset, and apply consistent contradiction handling to START. This bounded pass does not declare all execution contracts or field commissioning complete.

Reproduce using `protocol_matrix.py`, `boundary_probes.py`, and `fault_reset_probe.py` in this folder, with `PYTHONDONTWRITEBYTECODE=1`. Their outputs are `new_source_protocol_results.json`, `boundary_results.json`, `fault_reset_results.json`, and `fence_failure_results.json`.


---

# Specialist appendix: Forecast archive and scoring

# Workstream D — actual 6762543 forecast archive review

Reviewed **`6762543c7b9279fcebf279beaf1689cbbec070fa`**, parent `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`. **The four described repairs—complete temporary-file publication, one ingress snapshot, finite-score validation, and distribution validation before temporal checks—pass their original counterexamples in this bounded review.** The prior partial-final-file, mutation-during-store, false-CRPS-NaN and missing-score-NaN failures should not be carried forward as still failing.

F23/F24 whole-package acceptance remains partial because the adjacent integrity, evidence identity/qualification and forecast time/score conventions below remain open. Those are distinct from the verified repairs; this report does not claim a new regression merely because a remaining contract is incomplete.

## Evidence and scope

`probes.py` completed **19 case groups**. All **36 imported production files** matched the exact commit’s Git tree; blob/SHA-256 receipts and Python version are in `results.json` and `source-receipts.json`. On the Oct17 continuation, the completed receipts and exact source were reviewed without restarting or expanding the pass.

Evidence consists of direct production function calls, isolated archive files, selected thread interleavings, one injected link error and a child exiting during a valid write. No repository tests, historical audit artifacts, Git writes, production changes, network/controller calls or field hardware were used as correctness evidence. The crash probe is a controlled process interruption, not a power-loss durability test. Actuation was not exercised in this archive workstream.

All source line references below use `source/services/agribrain/world_model/forecast_archive.py` under this review root, abbreviated **FA**.

## Verified fixes and positive controls

| Original or adjacent check | Actual result on 6762543 | Exact source |
|---|---|---|
| Valid-record process interruption during dump | Child exits83 after flushing a prefix into its temporary file. No final forecast exists. Cold get correctly returns none for an uncommitted record; a valid retry succeeds. The orphan `.tmp` remains inert and is not presented as a committed forecast. | FA `30–58` |
| Invalid-caller serialization failure | Set-valued metadata raises `TypeError`; final file is absent, temporary file is cleaned, and corrected retry succeeds. This is failure isolation, not acceptance of invalid caller data. | FA `32–58` |
| Reader and identical writer during serialization | Before publication the final filename is absent. A competing identical writer can finish; the paused writer then accepts the same complete record. No temporary files remain after normal completion. | FA `34–50` |
| Incompatible concurrent links | A barrier immediately before the original `os.link` produces one accepted content identity and one conflict; both readers see the winner. Temporary files are cleaned. | FA `38–58` |
| Identical concurrent links | Both return the same complete forecast; no conflicting content and no temporary residue. | FA `38–58` |
| Injected link failure | The injected `OSError` leaves no final file or temporary residue; a normal retry succeeds. | FA `38–58` |
| Mutation during and after storage | Caller p50 is changed1→99 after the serialized snapshot is selected. Disk, cache and return all retain1; scoring against99 gives RMSE98. Mutating a retrieved copy also leaves the archive unchanged. | FA `435–483` |
| Durable conflict and retry | Both attempts to replace committed mean1 with99 reject. Warm/cold readers remain1, disk bytes are unchanged, and RMSE against99 is98. | FA `454–483` |
| Evidence ordering and date precision | `['A','B']` and `['B','A']` now persist the same canonical evidence tuple without a conflict. A different observation/microsecond has a distinct evaluation ID. | FA `586–588,649–673` |
| Nonfinite target/mean and typed numeric guards | NaN/infinite observations, boolean/numeric-string observations, NaN mean, negative sigma and invalid/nonfinite quantiles reject. NaN/infinite/boolean horizon and a 100-day label on a one-day forecast also reject. | FA `197–249,351–361,580–584` |
| Missing-score representation | A p90-only forecast retains its legitimate finite quantile score4.6; RMSE, sharpness and coverage are null. Its durable evaluation passes the strict JSON parser, with no fabricated median or false missing-coverage boolean. | FA `605–635` |
| Distribution before time | A forecast with no supported distribution, evaluated at an early time, raises the distribution error before temporal validation. An otherwise valid forecast evaluated before its target rejects; empty evidence also rejects. | FA `586–599` |
| Valid zero and Gaussian controls | Zero-sigma point mass scores0 at the truth and2 for error2. Gaussian mean10/std1 scores≈0.233695 at its mean. Valid zero error remains available. | FA `242–260` |

These results verify the changed publication and numerical boundaries. They do not imply that every archive record, evidence pointer or calibration convention is fully qualified.

## Remaining F23 boundaries

### D-01 — Corrupt cold storage is still reported as absence

An **injected existing-file corruption** fixture contains `{` at a final forecast path. Cold `get_forecast` returns none because FA `536–537` catches all exceptions. A store retry correctly raises a corruption error and does not overwrite it (`467–477`). This is a preserved reader-integrity gap, **not** a partial record generated by the repaired temporary/link writer.

**Acceptance:** distinguish absent, excluded and corrupt/unreadable records through an explicit integrity error or typed status. Preserve the current non-overwrite behavior and the verified interruption recovery. Crash-orphan cleanup may be an operational policy; the observed inert orphan is not evidence of canonical corruption.

### D-02 — Canonical evidence order is fixed, but token encoding remains ambiguous

The evidence tuple is now sorted consistently in both ID and payload (`588`, `657`), fixing the original order-conflict case. However, FA `649` joins tokens with `:`. Distinct ID sets `['A:B','C']` and `['A','B:C']` generate the same signature and evaluation ID for the same forecast/observation/time. The second valid-string set then conflicts with the first payload.

The repaired commit-before-cache ordering works: the failed second write leaves the in-memory count at1. This is a remaining identity-encoding seam, not the old rejected-evaluation cache contamination.

Compatible identical retries also append duplicate references to the same ID in memory: the order/precision probe lists three in-memory records but two durable records. No downstream aggregation was tested, so no double-weighted skill claim is made.

**Acceptance:** hash an unambiguous canonical list/object encoding. Define whether a compatible retry returns the existing identity once in history or whether consumers explicitly deduplicate; keep failed writes out of cache and preserve date/observation discrimination.

## Remaining F24 qualification and convention boundaries

### D-03 — Nonempty evidence is not yet a qualified evidence contract

The new nonempty check is effective, but `['']`, `[None]` and the scalar string `'AB'` pass the API. FA `588` converts them to `('',)`, `('None',)` and `('A','B')`; each receives a numeric evaluation marked `in_domain`. The boundary does not verify that these are resolvable, independent target observations with the correct variable, units, time and support.

This is a **direct API syntax/qualification seam**. It does not prove that a deployed upstream evidence service supplies such values or that an operational decision used them.

**Acceptance:** require a proper collection of nonblank typed IDs and a qualified target receipt, or enforce a documented upstream qualification contract whose evidence is bound into the evaluation. Determine domain/support and observation timing from that qualification rather than the default domain label. Keep the new finite-value, empty-sequence and pre-target rejection guards.

### D-04 — Time/horizon consistency remains more permissive than the stated contract

FA `351–355` rejects nonfinite and grossly inconsistent horizons, but its1.05-day tolerance accepts both **0.01 days and2 days for an exactly one-day target interval**. Both-naive origin/target timestamps also construct successfully (`344–350`).

These are observed constructor results. If rounded or inclusive-calendar horizon labels are intended, their policy must be explicit; the current broad tolerance does not describe which labels are admissible for calibration by horizon.

**Acceptance:** derive elapsed horizon from timezone-aware timestamps, or declare and validate an exact supported rounding/binning convention. The resulting metadata must identify the actual valid interval and its forecast/calibration horizon consistently. Gross mismatch rejection is useful progress, not full temporal qualification.

### D-05 — Distribution validation is stronger at scoring than at archival admission

`ForecastRecord.validate` now checks mean/std but does not validate predicted quantiles (`334–361`). The store accepts and persists quantile maps containing NaN, crossed values or an illegal level. Their subsequent evaluations now correctly reject in `compute_crps_quantiles` (`197–228`), so the prior numeric-credit failure for those cases is repaired.

Two aliases for one level, `{'p50':0,'0.5':10}`, are accepted and receive a numeric score. Sorting and monotonicity do not resolve the conflicting representation of the same level. The writer’s JSON settings also allow a NaN quantile to be stored even though scoring refuses it.

**Acceptance:** canonicalize levels once, reject conflicting duplicate aliases, and validate the supported distribution before committing it. Keep scoring validation as defense in depth. Invalid archived content should be explicitly quarantined or rejected rather than merely waiting for evaluation to fail.

### D-06 — Coverage conventions still differ between Gaussian and quantile forms

For a standard normal forecast evaluated at1.5:

- Gaussian mean0/std1 returns coverage true and sharpness3.29.
- Its actual p10/p50/p90 quantiles return coverage false and sharpness≈2.563103.

FA `639–642` uses±1.645σ, approximately p05/p95, while the quantile branch uses p10/p90 (`618–632`). The common coverage field carries no nominal level. This is a preserved score-convention mismatch, not a failure of the repaired finite CRPS calculation.

The quantile score is still an unweighted finite-level pinball average (`231–239`). It needs an accurate approximation label or a declared integration rule before being treated as exact continuous CRPS across different level grids.

**Acceptance:** declare interval levels, use matching Gaussian/quantile conventions for comparable metrics, and name or integrate the finite-quantile score accurately. Report calibration by horizon/domain with qualified target evidence, rather than inferring calibration from these software checks.

## Plan/R3 status and reproduction

The precise original repair cases above are **verified repaired**. F23/F24 remain **partial at full stage8 acceptance**, not reopened on the same counterexamples. F23 maps to AB-DAT-011 (R3 `699–701`), AB-ARC-007/008 (`746–752`) and AB-ASM-014 (`828–830`); F24 maps to AB-ML-005 (`990–992`), AB-ML-010 (`1010–1012`) and AB-ASM-016 (`836–838`). Missingness/support/time also relate to AB-DAT-005/007 (`675–685`) and AB-ML-008 (`1002–1004`). Stage8 is the sequencing addendum line36; master-plan lines118–126 separate software release gates from corpus/prospective/scientific capability. Its line134 requires F21–F24 closure before new training/forecast evaluation artifacts.

Run `PYTHONDONTWRITEBYTECODE=1 python3 probes.py` with this exact commit’s production files at `../source` and its `../git-tree.json`. The script verifies source blobs and writes only under a fresh lane-local `isolated/<timestamp>` directory. Injections are labeled in the results. Nonfinite values in review receipts are represented by explicit markers; no such marker is substituted into production code or its actual archive files. Source receipts identify the completed pass; no broader hardware, production deployment or biological qualification is claimed.


---

# Specialist appendix: Prescriptions and hard envelopes

# F15 bounded actual-source review at 6762543

The supplied DV15–DV17 reproductions are corrected at `6762543c7b9279fcebf279beaf1689cbbec070fa` (parent `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`). The original 116 groups now complete without production exceptions. A single bounded adjacent pass adds 22 groups, for 138 total. Full F15 acceptance remains open for decision-relevant duplicate conflicts, complete validity/cutoff qualification, and consistent units across all consumers.

All 30 manifest entries, covering 29 unique production files, match the new pinned Git tree. Exact unchanged dependencies were reused and reverified; no network was used in this pass. The probes execute actual production functions, the actual environmental modifier and four raw `run_layer8` calls. No repair models, repository tests/audits, shared production edits, Git changes, hardware or external services were used. Composed ActionCards carry two independent evidence families. Raw L8 shadow output is not top-level authorization or a physical execution claim.

## Verified repairs and positive controls

| Original finding/control | Current actual result |
|---|---|
| DV15: None/NaN/Boolean recommendation with positive minimum previously became 5 mm CONFIRMED | BLOCKED with the original invalidity reason; final value0 does not regain authority. |
| DV15: invalid cap or contradictory min 25/max 21 previously became a valid-looking confirmed envelope | BLOCKED; retained invalid/contradictory-bound reason. Legitimate zero dose/cap remains usable. |
| DV16: actual environmental modifier 21→14.7 mm below original minimum 20 | Scheduler and final gate now BLOCK the action; the final receipt includes `rate_min_safe`. |
| DV17: expired valid-until fixture, dates 2020/2030 outside the seven-day planning interval, malformed dates | BLOCKED. |
| DV17: ISO timestamps and offsets | Parsed to UTC instants and valid YYYY-MM-DD schedule dates. Simple reversed date rows consistently choose actual Oct 15. |
| DV17: duplicate 0/100 mm rain disagreement | BLOCKED by conflict handling. |
| Whole-run string temperature seam | The same actual `run_layer8` fixture now succeeds; finite numeric strings are normalized before modifiers. Numeric controls still succeed. |
| Weather qualification controls | Missing mandatory spray weather and NaN/Infinity/Boolean wind/rain block; speed 5+gust 20 blocks ; 10 m/s converts to 36 km/h and blocks ; 10 knots converts to 18.52 km/h and blocks. Safe wind, legitimate zero wind and safe 2 m/s remain accepted. |
| F11 unchanged arithmetic control | 86.67 kg N/ha remains correct under the declared controlled fixture. This pass does not revisit broader F11 science. |

Relevant changed blobs: salinity `3c66e7783b603e8cbb95e9485f66764bf6ff857b`; invariants `71850d57f46bd9007eabddf23f22122bcc46d9af`; L8 runner `5ccedfe3af9c8e3f59161b05a3a0e729be31250b`; scheduler `fb8f2fc3d47185c1d959ec090e7c9f5bbd03c74e`.

## Remaining reproduced cases

### E1 — Review priority P1: Duplicate conflict logic can discard a row that crosses the action's safety limit

Two same-date spray rows with rain 0 and 1 mm are not marked conflicting because the duplicate check requires a difference greater than 5 mm. The scheduler retains the first row. Dry-first therefore returns CONFIRMED, while reversing the same rows returns BLOCKED against the spray limit 0.5 mm. All final invariants run. Same-day speed 5 versus 16 km/h and temperature 25 versus 42°C can also retain the safe first row and confirm, although the discarded row violates the action's constraints.

This is a duplicate-input qualification defect, not evidence that normal single-row forecasts are unsafe. The original large 0/100 mm duplicate fixture is fixed. These smaller disagreements matter because they straddle the actual action thresholds; a generic magnitude threshold does not establish consistent safety evidence.

Source: `services/agribrain/layer8_prescriptive/scheduler.py:155–179` compares only precipitation and retains the first row; action limits at 31–35; validation at336 onward. Cases: `F15_COMBINED_duplicate_crosses_spray_rain_threshold` and its reversed control, plus wind and temperature variants.

Concrete repair/acceptance: normalize duplicate identity and units, then either reject conflicting same-day support, resolve a versioned authoritative source, or conservatively intersect all decision-relevant constraints. Reordering contradictory duplicates must not switch CONFIRMED to BLOCKED. Retain the large-conflict and identical-duplicate positive controls.

### E2 — Review priority P1: Validity is checked against the row instant, not the actual planning cutoff

Planning starts at `2026-10-13T12:00:00Z`; a daily row dated Oct13 with `valid_until=2026-10-13T08:00:00Z` still confirms Oct13. Its parsed row instant is midnight, which precedes expiry, although its validity has already ended before planning starts. The positive control with a 14:00 row and 18:00 validity confirms legitimately.

Malformed `valid_until='not-a-date'` is ignored and confirms. A supplied `valid_from` after the action date and `issued_at` after planning are also unused. The latter two are policy-dependent until a typed field contract defines whether they are weather-support intervals or artifact/knowledge cutoffs; this review does not silently assign them a stronger established meaning. The implementation already consumes `valid_until`, so malformed or already-expired validity needs an explicit unavailable result. An offset-aware planning start is reduced to its local calendar date while row dates are UTC, allowing a tested candidate instant earlier than the planning start to remain confirmed.

Source: `scheduler.py:82–107,270–272,295–319`. Cases: `F15_TIME_expired_before_planning_start`, valid same-day control, `F15_COMBINED_invalid_valid_until`, `valid_from_after_action`, `issued_after_planning`, and `F15_TIME_start_offset_past_UTC`. The older date/expiry fixtures remain fixed.

Concrete repair/acceptance: define weather validity and artifact knowledge cutoffs separately, parse them once in UTC, reject invalid declared validity, and intersect the actionable slot with the actual planning-start instant. Test same-day expiry, start offsets, validity starts, issuance cutoffs and the original expired/future/malformed fixtures. If only daily dates are supported, publish a daily interval policy rather than accepting timestamp precision and then discarding it.

### E3 — Review priority P2: Numeric normalization still does not give every modifier the same physical units/support

The unchanged frost modifier emits 3.3 mm/hr for wind 2 m/s and 4.1 mm/hr for the equivalent 7.2 km/h with the same −5°C forecast. It reads the raw speed and does not convert its unit tag. An equivalent `t_min_c` alias produces no frost card because that modifier only reads `temp_min`. These are actual modifier outputs; no claim is made that the generated heuristic cards passed top-level authorization or reached hardware.

The new runner fixes finite numeric-string conversion before consumers but does not canonicalize weather units or aliases there. The scheduler's new knots conversion works; an unrecognized `mph` tag is still treated as multiplier 1 (10 mph crosses the 15 km/h spray threshold but confirms), and finite negative wind/rain is accepted. At the selected function boundary, an irrigation card with empty unit or `kg_N/ha` can also be confirmed; None upper bounds remain accepted as unbounded. Whether optional bounds are intentionally unbounded versus unavailable needs an explicit typed contract. These are bounded schema/unit observations, not proof of an actuator bypass.

Source: `runner.py:291–316`; unchanged dependency `engines/frost_sprinkling.py:27–49,67–72`; `scheduler.py:194–218,321–334`; `salinity_leaching.py` preserves the supplied rate unit. Cases: `F15_MODIFIER_equivalent_weather_units`, `F15_COMBINED_mph_unrecognized`, `F15_UNIT_missing_rate_unit`, `F15_UNIT_incompatible_rate_unit`, and `F15_CAP_none_cap`.

Concrete repair/acceptance: normalize qualified values, aliases, units, ranges and support once before every modifier; require a known unit for each action quantity and an explicit missing/unbounded ceiling type. Equivalent physical inputs must produce equivalent modifier output. Unsupported units should be rejected or converted under a declared policy.

## F15 plan disposition

F15 remains stage 5, dependent on F01/F06/F14, mapped to R3 AB-DEC-003 (`R3_current_scientific_sections.txt:1076–1078`), AB-ECO-003 (`1088–1090`) and AB-EXE-001 (`1106–1108`). Review P1/P2 priorities above are separate from the original package's P0 priority.

- `ST05-F15-01`: partial. Finite/type parsing, common conversions and UTC row parsing are verified; all-consumer units, actionable validity and duplicate support remain incomplete.
- `ST05-F15-02`: the reproduced mandatory-weather and invalid-rate cases are fixed. Continue qualification across the canonical boundary rather than promoting missingness to a number.
- `ST05-F15-03`: the tested original finite upper/lower envelopes and invalidity flags now survive correctly through the changed gates; broader aggregate resource/budget qualification was not exercised.
- `ST05-F15-04` and `ST05-F15-FA`: remain open for the concrete E1/E2 integration cases and the documented units/support criteria. Legal/resource/aggregate-budget integration and operational commissioning are not certified.

All original DV15–DV17 fixture closures should be retained. The bounded residuals above refine full acceptance; they do not reverse those verified repairs. Artifacts: `actual_decision_probes.py`, `actual-decision-results.json`, `coverage.json`, `source-verification.json`, and the run summary/stderr receipts.


---

# Specialist appendix: ASMAE cache and plan register

# DV18 cache repair — bounded actual-source verification

The reproduced timeout-cache issue is fixed at main `6762543c7b9279fcebf279beaf1689cbbec070fa`, parent `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`. The actual timeout producer and runner serializer now lead to writer refusal and a reader miss. A valid negative artifact freshly written by the actual parent writer also becomes a clean miss under the new reader. This closes the previously reported P2 timeout-cache policy case within the tested contract; it does not close full T11 or F38 acceptance.

The review uses actual production source, with 510 selected runtime/dependency blobs verified against the new exact tree. Current cache blob: `3c82ea6aaa221e7a1e7a5e68edb3d248d209eb8b`; parent cache blob: `3050e02b98ff33d31c17227090a213a4e58fc418`. Production files and Git state were not modified. No repository tests, audit assertions, historical production artifacts, network/database/provider/controller calls or hardware were correctness evidence. Every JSON/NPZ fixture was generated locally by an exact production writer.

## Actual producer and migration results

The exact timeout output constructor/postprocessing from [`engine.py:624-696`](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer05_asmae/engine.py#L624) and exact serializer from [`runner.py:1114-1196`](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer05_asmae/runner.py#L1114) were executed with supplied estimator, provenance and plot-artifact data. This preserves the earlier evidence limit: it is the real producer/serializer fragment, not a full ASMAE scientific inference or service execution.

Its output still contains `status:'failed_spatial_timeout'`, diagnostic `failure_code:'STATE_ESTIMATION_TIMEOUT'` and diagnostic `reason:'state_estimation_timeout'`, with no top-level result_status/reason. The new writer and reader reject these actual fields, including diagnostic status_override and case normalization. Source: [`cache.py:650-675`](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer05_asmae/cache.py#L650) and [`cache.py:745-772`](https://github.com/webClone/AgriWise/blob/6762543c7b9279fcebf279beaf1689cbbec070fa/services/agribrain/layer05_asmae/cache.py#L745).

| Fresh control | Writer | Reader | Interpretation |
|---|---|---|---|
| Actual timeout producer → serializer → current cache | refuses | miss | Reproduced DV18 failure case fixed. |
| Same actual timeout → actual 1ee8 parent writer/reader | commits | hit | Confirms the comparison artifact is a valid parent transaction. |
| Parent timeout artifact → current reader | — | miss | Existing parent-format negatives are rejected without erasing their bytes. |
| Six actual a2-writer negative fixtures → current reader | all six old writers commit | all six miss | Earlier migration protection retained. |

Those six retained cases are result_status rejected/aborted, status failed/uppercase REJECTED, is_rejected true and uppercase TIMEOUT reason. Current writers refuse all six. Cache/hash schema identities remain unchanged; this is reader eligibility enforcement, not a changed key hiding old entries. The actual a2 writer blob is verified as `d30fae61cc8ab7c0d02c51edfcf30fc9d6bbd8b1`.

The current writer and reader rejection expressions have identical ASTs. Additional boundary combinations use actual producer strings: timeout failure codes, reasons or overrides reject even when outer status is success/partial, including mixed/uppercase text. Partial results with non-failure no-scene reason and success results with unavailable retrovalidation/BMA stage metadata remain cacheable. These combinations test the admission boundary and are not asserted to be separate live producer traces. No Enum fault or undocumented producer type is invented.

## Integrity and authority controls retained

A valid JSON/NPZ pair reloads exact grids. NPZ-byte corruption, JSON modification without checksum update and raster-manifest shape mismatch each produce a clean miss; restoring the exact pair restores its hit. Key controls still distinguish band, shape, dtype, exact pixel precision, validity mask and transform. Caller dictionaries remain unchanged.

Accepted diagnostic products preserve all nine checked authority/availability fields: production usability, L1 export, state update, weak-label export, visual permission, diagnostic-only, state availability, authority level and posterior availability. The denied timeout payload also retains every input field and diagnostics unchanged; no artifact is returned for a reader-side authority comparison. A cache hit remains a storage outcome, not scientific authority or canonical publication. The producer's public content_hash is retained rather than scientifically recomputed by this storage layer.

The exact progressive helper still returns `status:'unavailable'` with its timeout explanation in `diagnostics.fallback_reason`; that structured no-raster result remains cacheable with demoted authority. This is not reopened as DV18's operational defect: the current execute method has an earlier quick_visual serving return, and reachability of its later catch was not established. No promotion, live failure loop or new high-priority regression is asserted from that helper observation.

## Canonical acceptance and plan proof

DV18 is a local verification label. The checked failure/migration slice maps to **T11 stage 11**, ST11-T11-02/03/04 and T11-FA, and the relevant degraded-result slice of **F38 stage 10**, ST10-F38-09/F38-FA. Applicable R3 requirements include AB-ARC-006/007/008/012 and AB-DAT-001/002. It does not close backend identity, per-variable scientific qualification, all entrypoints, provider drills or exact job/output/head publication relations.

Bootstrap, drone_mission identity sources, structural imports and app/main are unchanged from parent by exact blob comparison. The prior F37 availability slice and its remaining single-identity/supported-entrypoint limitations are retained source scope, not freshly rerun broad acceptance. This pass does not certify canonical publication from cache success or re-review the changed canonical-worldline implementation owned by the other workstream.

The three supplied plan documents match the new exact tree and are unchanged from parent:

| Document | Verified Git blob |
|---|---|
| Deep Repair Plan | `08d378a65992de859369950599df198e64244f01` |
| Execution Sequencing Addendum | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| Work Packages Task List / acceptance register | `8a564647af7e588802537817159117b349ff606b` |

Fresh register parsing finds **52 unique full-acceptance rows, zero checked**. This reports register state; it does not independently prove every package is technically defective. Narrow verified fixes should be recorded separately until full card criteria and integrations pass.

Artifacts: `cache_reader_probes.py`, `cache-reader-results.json`, `cache-reader-console.txt`, `source-receipt.json`, `coverage.json`. Reproduce with `PYTHONDONTWRITEBYTECODE=1 python cache_reader_probes.py` from this directory. Python 3.12.14 and previously disclosed installed-dependency differences remain the execution limits; no supported-image or full-service certification is claimed.

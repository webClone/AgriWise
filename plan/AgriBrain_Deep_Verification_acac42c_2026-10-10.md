# AgriBrain deep verification of acac42c — C01–C11 corrective implementation

Review date: 2026-10-10 UTC  
Pinned commit: `acac42c2627f699fe1f44192dcec2997b528cdbb`  
Parent: `49b8696be562305000259b350e8c4870251386be`  
Repository: [webClone/AgriWise](https://github.com/webClone/AgriWise)  
Method: production-source inspection and independent controlled software reproductions.

## 1. Implementation readiness decision

**The changes are now published, and the original nominal counterexamples show substantial correction. The claim that C01–C11 are fully remediated is still too broad.** Deep checking reproduced 12 actionable remaining defect groups (D01–D12) and an additional calculation-identity qualification (Q01). These IDs belong to this report and do not replace the canonical F/T package or R3 requirement IDs.

Proceed with targeted implementation repairs. Do not treat the remaining gates as waiting only for field validation: several controlled-software acceptance criteria are still violated. The six full acceptance tickets should stay open for that reason as well as any relevant integrated driver/field objectives.

The exact historical replay numerical fix and the original two-worker CAS rollback fix pass their specific cases. They should be retained. Their broader boundaries still need scoped cache publication and candidate isolation rather than additional special-case fallbacks.

Independent world-model/Omega exploration can continue using eligible observations and qualified states. Production acceptance or scientific promotion of affected execution receipts/trajectories must exclude the failures below. This review is not a complete re-audit or sign-off of all AgriWise/AgriBrain modules.

## 2. Evidence scope and reproducibility

- GitHub main was pinned to acac42c and rechecked after execution; it remained at this commit.
- Inspected the five changed production Python modules and their production-only differences. canonical_worldline.py is unchanged from the parent; its exercised production APIs remain part of the verification.
- Assembled **430 production Python dependency files**, each verified against the pinned tree's Git blob SHA-1. This is source integrity, not full semantic coverage of 430 modules.
- All five changed production modules parse successfully. No repository test file was read or used as correctness evidence.
- Executed **88 independent probe groups**: the previous 68 groups plus 17 runtime boundary groups and three hydraulic boundary groups. Groups contain multiple subcases; 88 is not a pytest pass count.
- No harness errors were recorded. Successful controls and counterexamples both appear in the transcripts.
- No production source, plan or GitHub branch was modified. All drivers are independent controlled software simulations. No field hardware was operated.
- The claimed 11 corrective tests / 383 total tests are user-reported and were not independently recertified. Passing those tests can coexist with these counterexamples.
- Runtime used: `3.12.14` on `Linux`. The concurrency evidence covers same-host OS processes/threads as specified in the probe, not multi-host controller fencing.
- The companion ZIP includes the eight independent harnesses, observed results, a production blob manifest and reproduction instructions. It excludes repository tests, audit files, production source copies and credentials.

### Changed production source hashes

| File | Pinned Git blob |
|---|---|
| [services/agribrain/irrigation_runtime/actuator.py](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/actuator.py) | `1487fb7f00ce68e7ceed1713804440ad4a5f3ad2` |
| [services/agribrain/irrigation_runtime/dispatcher.py](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py) | `40a4184d015b0b2f2c8381d14543f4e33e93be92` |
| [services/agribrain/irrigation_runtime/safety.py](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/safety.py) | `dcc994d93cba033771221c6193db1d0bbc2951a7` |
| [services/agribrain/irrigation_runtime/schemas.py](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/schemas.py) | `d7a09ee232c6900cc3913404ad86604e4356c45a` |
| [services/agribrain/layer3_decision/runner.py](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/layer3_decision/runner.py) | `62b565ab1dce3ee21235e7ad29b943641c73e9a8` |

### Acceptance register and monograph basis

The current task register retains Git blob `8a564647af7e588802537817159117b349ff606b`, matching the local production-plan copy used to inspect acceptance criteria. All six entries below remain unchecked:

| Ticket | Line | Acceptance scope includes |
|---|---:|---|
| ST03-F08-FA | 406 | Correct trajectory identities, dependency invalidation and idempotent requests. |
| ST03-F09-FA | 443 | Warm/cold equality, competing-worker publication, restart/withdrawal/correction persistence. |
| ST06-F16-FA | 796 | Non-bypassable budgets, duration cutoff, concurrent quota conservation. |
| ST06-F17-FA | 833 | Retaining operation state until physical completion. |
| ST06-F18-FA | 870 | Safe retry and reconciliation. |
| ST06-F19-FA | 907 | Qualified interlock behaviour and violation handling. |

The register specifies controlled production-symbol regression evidence for these gates; it is inaccurate to describe them as exclusively awaiting field trials. Additional field/device acceptance can be necessary for deployment, but it does not replace the failing software invariants here.

R3 mappings below use the previously supplied monograph requirement register. No R3 monograph file exists in this pinned repository tree. This report neither modifies the monograph nor claims coverage of all 153 requirements.

## 3. C01–C11 reconciliation

“Original case passes” credits the exercised repair, not full F-package acceptance.

| Original group | Verified improvement | Remaining boundary |
|---|---|---|
| C01 pending START cancellation | Physical STOP is sent while START is pending; premature ALREADY_STOPPED is removed. Original case passes. | Failure of the additional late fence belongs to D01/C02. |
| C02 late START fencing | Successful cancellation/fence and successful watchdog/late stop preserve terminal event status and stop the simulation. | Fence rejection/exception is ignored; watchdog post-stop failure also leaves untracked running state. D01. |
| C03 quota-store integrity | Negative/NaN volume and missing established file now block admission. | Rollups can contradict receipts, non-volume fields remain unvalidated, and marker-write failure is suppressed. D04. |
| C04 stopped delivery accounting | Cancel/watchdog paths retain an 8 mm accounting amount and prevent a second 8 mm request against 10 mm. | ERROR-stop path still releases exposure; unknown target debit is stored as delivered quantity without provenance. D03/D08. |
| C05 stopped terminal idempotency | Cancelled retry issues no second START; identical 3 mm receipt stays 3 mm. | Corrections overwrite receipts and use new periods; stopped→settled double accounting and conflicting settlement retries remain. D08. |
| C06 payload and zero-depth claims | Positive changed zone/duration/flow is rejected; budgeted zero-depth operation issues one START. | No-budget admissions can duplicate; valid zero fields bypass conflict comparisons; area/support is unbound. D05/D06. |
| C07 phase preservation | A duplicate during unacknowledged START reports DISPATCHING rather than EXECUTING. | Failed STOP/OFFLINE durable state remains EXECUTING; VALIDATING is serialized as UNSETTLED then returned as DISPATCHING. D07. |
| C08 qualified settlement | Inf/bool area and Inf volume fail without losing reservation; explicit zero with valid area gets a zero receipt; durable settlement precedes COMPLETED. | Early completion lacks lifecycle/stop guard; absent area still makes 0 L into target depth; invalid duration becomes zero. D02/D09. |
| C09 separate command and outcome | Valid 4/8/16 mm deliveries preserve commanded 8 mm identity and litre observations on repeat. | Duration/support/outcome rehydration is incomplete; settlement conflicts and cross-kind receipts are inconsistent. D08/D10. |
| C10 historical cold replay | January 2 exact replay after January 3 preserves theta and head sequence 2. Original numerical case passes. | An interposed historical query changes a later calculation's checkpoint identity despite identical numerical profile. Q01. |
| C11 competing-worker rollback | Original two-worker loser now retains the winner's cached head, history and water memory. | A newer publication during rehydration is overwritten; uncommitted candidate events contaminate the winning calculation. D11/D12. |

Prior controls also pass: failed STOP retention, uncertain ACK handling, invalid-budget rejection, same-host cross-process quota exclusion, live-lock owner protection, orphan-head recovery, persistence error propagation, scope/parameter invalidation, exact latest-day replay, and ISO withdrawal roundtrip. The explicitly polled deadline control is not proof of autonomous scheduler/device cutoff when polling itself stops.

## 4. Actionable remaining defects

P0 identifies demonstrated physical-command or quota fail-open behaviour. P1 identifies demonstrated data/receipt/trajectory consistency failure. These priorities apply to the affected capability, not a universal dependency block on independent research.

### D01 — P0 — Failed late fencing discards live ownership

Source: [actuator.py:508–551](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/actuator.py#L508-L551); [dispatcher.py:398–412](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py#L398-L412).

The return value of `send_command(fence_stop)` is ignored. Its exception is logged, then the actuator is unconditionally made ONLINE with no active command. The dispatcher ignores the late result for a finalized event. Its extra emergency stop also has no failure handling in this terminal guard.

Probe: acknowledge the first STOP, apply delayed START afterwards, then reject CMD-FENCE or raise an OSError. In both cases the event stays CANCELLED while the simulation is running, actuator reports ONLINE, active events = 0, monitored events = 0, and shared reserved exposure = 0. The prior 8 mm debit remains, but it is not a monitor or a qualified bound on continued delivery. The watchdog version leaves EMERGENCY_STOPPED with the simulation running when its late emergency stop fails.

Repair: inspect/reconcile the fence receipt and propagate failure. Reacquire/preserve STOP_REQUESTED ownership, actual operation context, monitoring and conservative unresolved exposure. Every stop route, including driver-specific emergency stop, must participate in the generation/operation protocol. Do not certify a stopped physical state solely because an attempted command was preempted.

Exit: test rejected, timed-out, exceptional and successful late STOP; pending application both before/after initial STOP; restart/owner change. Failure cannot produce a terminal unmonitored running operation.

Mapping: C02; F17/F18; AB-EXE-002/003/004, AB-ARC-006/008.

### D02 — P0 — complete_event can finalize a physically executing operation

Source: [dispatcher.py:718–794](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py#L718-L794).

complete_event checks that the event is in the local active dictionary but does not require VALIDATING or an operation-qualified stopped/completed receipt.

Probe: submit 8 mm, leave the controlled actuator EXECUTING, call complete_event(E, 0 L, 0 min) with area 1 ha. It writes COMPLETED, settles zero, removes active/watchdog tracking and releases the reservation while the simulation is still running. A second 8 mm command on another device is then admitted against the same 10 mm plot budget; both simulations run. These are admitted command targets, not measured field-delivery totals.

Repair: require an authoritative lifecycle transition from physically completed/stopped operation into validation; reject premature completion without changing reservations. Bind measurement to the operation and time/support before closing exposure. Settlement is downstream of physical completion, not a substitute for it.

Exit: completion during QUEUED/DISPATCHING/EXECUTING/STOP_REQUESTED, duplicate validation calls and delayed controller outcomes cannot terminate monitoring or release live exposure.

Mapping: C08; F16/F17; AB-EXE-002/004, AB-DAT-010, AB-ARC-007.

### D03 — P0 — The ERROR-stop path still releases unmeasured delivery

Source: [dispatcher.py:688–696](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py#L688-L696).

The controller ERROR branch successfully stops the actuator, transitions to FAILED and calls release_quota, bypassing the newly centralized stopped-delivery accounting path.

Probe: start E targeting 8 mm, then report controller ERROR and acknowledge emergency stop. There is no reservation, stopped receipt or settled debit afterwards. Another independent 8 mm request is EXECUTING against the original 10 mm budget. The prior delivered amount is unknown; the bug is loss of unresolved exposure, not a demonstrated 8 mm measurement.

Repair: route this branch and every physically applied/possibly applied failure through one accounting finalization transaction. Preserve outcome FAILED separately from physical delivery/accounting status; failure must not mean no water.

Exit: enumerate every successful stop/reconciliation/error return branch and prove conservation of prior outstanding exposure across each.

Mapping: C04; F16/F17; AB-EXE-002/004, AB-DAT-005/010.

### D04 — P0 — Quota integrity still permits contradictory rollups and ignores marker durability

Source: [safety.py:180–219](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/safety.py#L180-L219); [safety.py:255–271](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/safety.py#L255-L271).

Validation checks types/numeric values for selected fields, but not receipt-to-aggregate conservation. Duration/flow/target/support fields are not fully validated. Established-marker write failure is swallowed after ledger publication.

Probe A: settle 8 mm and keep its valid receipt, but clear all three aggregate maps to empty dictionaries. The store is accepted; get_settled reports 0 and a new 8 mm request is admitted against a 10 mm budget. Persisted receipt plus newly admitted target is 16 mm. No invalid JSON/number is required.

Probe B: reservation duration = -1 and flow = True are accepted by _validate_state. They are not the already-fixed core volume corruption case.

Probe C: inject a marker-write OSError. START is admitted without an established marker. A later loss of the ledger file is consequently treated as fresh empty state and admits another START. This is a two-fault reproduction with explicitly injected filesystem failure, not a claim that marker disappearance normally occurs.

Repair: validate the complete versioned record schema and reconcile aggregates to an authoritative operation/accounting journal. Marker/recovery publication cannot be best effort: fail closed until initialization is durably established. Preserve typed degraded errors without inventing an empty ledger.

Exit: syntactically valid inconsistent rollups, all scalar types, missing fields, marker publication failure and established-file loss cannot reset exposure or admit unsupported commands.

Mapping: C03; F16; AB-EXE-004, AB-DAT-005/012, AB-ARC-006/007.

### D05 — P0 — Durable operation admission remains conditional on a budget

Source: [dispatcher.py:321–349](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py#L321-L349); [safety.py:978–1006](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/safety.py#L978-L1006).

submit_event accepts budget=None, but atomic_check_and_reserve is skipped in that case. Later monitoring can create a positive reservation but is not an atomic operation-admission decision. Zero-depth monitoring creates no claim when the atomic budget path is absent.

Probe A: same event ID, zero depth, no budget, two independent dispatcher/driver instances: two START calls.

Probe B: positive 8 mm, no budget, two independent dispatchers with a barrier after the shared is_active checks: both return EXECUTING and two START calls occur for the same operation. This is a same-host two-thread interleaving with independent simulated drivers representing separate process-local controller clients.

Repair: perform durable scoped operation admission independently of quota data and numeric depth. If physical execution requires a budget, reject missing budget explicitly; if a mode legitimately lacks one, it still needs atomic operation identity/ownership and qualified exposure policy.

Exit: absent/present budget and zero/positive depth, local/fresh/concurrent callers all produce at most one compatible physical dispatch. Controller-side idempotency, if supported, is an additional qualified protection.

Mapping: C06; F16/F18; AB-EXE-003/004, AB-ARC-008.

### D06 — P1 — Valid zero fields and support changes evade payload conflicts

Source: [dispatcher.py:235–297](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py#L235-L297); [safety.py:430–448](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/safety.py#L430-L448).

Durable conflict checks compare duration/flow only when both stored and supplied values are positive. Zero is a valid scalar according to the event contract and must not disable identity binding. effective_area_ha is declared but not part of durable command/support identity.

Probe: original 8 mm/10 min/10 L min⁻¹/1 ha operation active. A fresh caller with the same ID and duration 0, flow 0, or area 2 ha gets EXECUTING and retains that conflicting value. Positive duration/flow/zone changes correctly fail (control).

Repair: compare canonical typed command/support identity, including valid zero; do not use truthiness as a compatibility rule. Missing value must be explicitly represented and qualified, not silently compatible. Include geometry/area support used to interpret dose/measurement, or reference its immutable version.

Exit: independently mutate zero, positive and missing command fields/support in active/stopped/settled/atomic-race paths; conflicts must be explicit and exact repeats must return the original command.

Mapping: C06; F18; AB-DAT-005/007/013, AB-EXE-001/003, AB-ARC-008.

### D07 — P1 — Durable lifecycle phases still disagree with the owner

Source: [dispatcher.py:298–309](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py#L298-L309); [dispatcher.py:565–570](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py#L565-L570); [dispatcher.py:666–706](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py#L666-L706); [safety.py:635–643](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/safety.py#L635-L643).

Shared update_status is used on initial submit ACK/error, but several later STOP_REQUESTED transitions do not update it. track_event_end writes UNSETTLED, which is not an EventStatus; duplicate handling catches enum conversion failure and returns DISPATCHING.

Probe: failed cancellation and controller OFFLINE both leave owner STOP_REQUESTED while durable record/fresh duplicate are EXECUTING. Normal physical completion leaves owner VALIDATING, durable UNSETTLED, and fresh duplicate DISPATCHING.

Repair: centralize lifecycle transitions with durable phase updates and a single explicit phase schema. Accounting state such as unsettled must be distinct from physical phase, with a defined projection. Duplicate callers must observe the authoritative current operation and preserve its outcome.

Exit: join during ACK wait, failed STOP, OFFLINE, validation, completed and emergency states. Fresh duplicate phase equals the qualified authoritative phase; no fallback changes the phase’s meaning.

Mapping: C07; F17/F18; AB-EXE-002, AB-DAT-010, AB-ARC-006.

### D08 — P1 — Terminal receipt corrections are non-immutable and non-conserving

Source: [safety.py:675–713](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/safety.py#L675-L713); [safety.py:730–774](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/safety.py#L730-L774).

Stopped correction computes a difference but, after the first receipt removes the reservation, derives date/season from current defaults instead of the original receipt. It overwrites the receipt. Settled and stopped ledgers do not enforce one operation accounting identity; settled retries return early without verifying the retry payload. Unknown stopped exposure is stored as delivered_volume_mm with no observed/estimated/unresolved distinction.

Probe A: first stopped receipt is 8 mm on January 1 / S1. Correct to 3 mm without re-supplying date/season. It leaves original-period +8, writes current-period -5 under default_season, replaces the receipt’s period, and the next read raises CorruptedQuotaStoreError. Valid inputs created a corrupt store.

Probe B: stopped 8 mm followed by measured settlement 3 mm records both and total becomes 11 mm, rather than reconciling provisional exposure to 3 mm.

Probe C: after settled target 8/delivered 4, retry with target 99/delivered 7. The store silently returns without a conflict, keeping the first receipt; the caller is not told that its incompatible mutation was refused.

Repair: one immutable operation ledger with separate provisional exposure, observed delivery and accounting adjustment records. Every adjustment preserves original scope/period and records lineage; aggregate deltas are atomic and validated before write. Exact retries return the same receipt; incompatible retries conflict. A target debit is not a demonstrated upper bound on an overrun, nor an observed delivered quantity.

Exit: repeated identical receipts, cross-kind transitions, under/over-delivery corrections, original day/season changes and payload conflicts conserve totals and never produce negative/misallocated rollups or silent incompatible success.

Mapping: C04/C05/C09; F16/F18; AB-DAT-003/005/006/010/011, AB-ARC-007/008.

### D09 — P1 — Missing area and invalid duration still become completed physical values

Source: [dispatcher.py:730–757](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py#L730-L757); [schemas.py:345–356](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/schemas.py#L345-L356).

The explicit-zero correction is conditional on valid area. Without area, complete_event still uses target_volume_mm. Invalid actual_duration_minutes is replaced by 0 rather than rejected or marked missing. Default numeric zero still cannot distinguish omitted measurement from explicit observed zero.

Probe: complete with 0 L and effective_area_ha=None (the ordinary event default): receipt is COMPLETED with actual_volume_l=0 and delivered_volume_mm=8. With area 1 ha, the same explicit zero correctly settles 0 (control). Supply Inf actual duration with valid volume/area: COMPLETED stores actual duration 0.

Source qualification: area is now a declared event field, but the standard scheduler does not populate it in the reviewed dependency workspace. No normal scheduling-to-settlement area/support integration was demonstrated.

Repair: preserve exact observed zero independently of area; nonzero volume requires qualified support to derive depth. Missing measurement, conservative target accounting and observed delivery must be different fields/states. Validate duration and bind measurement provenance rather than coercing invalid data.

Exit: explicit zero versus omitted volume, missing/invalid support and invalid duration produce mathematically/provenance-consistent receipts without fabricated measurements or exposure loss.

Mapping: C08; F16/F17; AB-DAT-005/006/007, AB-EXE-002.

### D10 — P1 — Completed retries omit duration and measurement support

Source: [dispatcher.py:259–272](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/dispatcher.py#L259-L272); [safety.py:690–705](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/irrigation_runtime/safety.py#L690-L705).

The durable settled receipt now persists actual duration, but repeat rehydration only restores target, delivered depth and litres. Area/support is not stored in the receipt, and the original status/timing/validation context is not fully rehydrated.

Probe: settle 40,000 L over 6 minutes on 1 ha. Fresh exact repeat restores litres correctly but reports actual_duration_minutes=0 and effective_area_ha=None; the persisted actual duration is 6. Area is absent from the receipt entirely.

Repair: define a typed immutable receipt carrying commanded identity, physical/outcome phase, actual quantity/time, support/version and provenance. Return it completely on retry rather than populating a new event with defaults. Declare derived delivered depth in the serialization contract where it is intended to survive roundtrip.

Exit: serialize/restart/retry under/exact/over/zero delivery and emergency outcomes; every qualified receipt field is preserved and remains interpretable.

Mapping: C09; F17/F18; AB-DAT-006/007/010/011, AB-EXE-002/003.

### D11 — P1 — A newer winner can arrive during rollback rehydration

Source: [runner.py:1330–1386](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/layer3_decision/runner.py#L1330-L1386).

Rollback reads a winning checkpoint and then publishes its RAM contents without checking that the durable/cache generation is still current or holding a per-scope publication lock. The original two-worker case is fixed; read-then-publish remains a race.

Probe with real production CAS and controlled scheduling: A loses to B at January 3. Pause A after its last rollback head read. C commits January 4 and publishes that RAM/head. Release A: it rehydrates January 3 over C. Durable head remains January 4 while cached head/history return to January 3. The second (outer) rollback invocation is explicitly accounted for; the pause is at its final read. Disk remains correct.

Repair: publish/rehydrate a generation-qualified snapshot under scoped synchronization or cache CAS; never apply a snapshot that has been superseded. A losing computation may not overwrite a newer publication. Keep both scoped and compatibility aliases consistent.

Exit: two/three workers, winner arriving before/during/after head read, and failure during rehydration all leave RAM and disk at the same current committed generation.

Mapping: C11; F09; AB-ARC-007/008, AB-DAT-012.

### D12 — P1 — Uncommitted candidate evidence leaks into the winning trajectory

Source: [runner.py:1432–1511](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/layer3_decision/runner.py#L1432-L1511); [runner.py:1513–1539](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/layer3_decision/runner.py#L1513-L1539); [runner.py:1330–1386](https://github.com/webClone/AgriWise/blob/acac42c2627f699fe1f44192dcec2997b528cdbb/services/agribrain/layer3_decision/runner.py#L1330-L1386).

Candidate water histories are local, but input event ingestion still mutates shared plot_events before CAS. A different worker reads that uncommitted event and can persist it as its own forcing. Rehydrating the winner cannot undo contamination already included in the winning checkpoint.

Probe: control B has January 3 rain 10 mm, no irrigation: theta=[0.2423,0.2293,0.2210,0.2259,0.2295]. Concurrent A supplies a 5 mm irrigation event candidate-A and pauses before save. B then uses its own identical no-irrigation request but reads A's event from RAM: theta=[0.2423,0.2543,0.2210,0.2259,0.2295]. Its durable checkpoint contains candidate-A and irrigation=5. A subsequently loses CAS. This demonstrates input/candidate isolation failure; it does not establish that the event was false in a real field.

Repair: ingest all event/vegetation/soil/withdrawal inputs into per-attempt candidate registries and compute against an explicit committed evidence snapshot. Publish the entire compatible registry generation atomically after persistence. If evidence commits independently, give that commit explicit identity, cutoff and synchronization rather than exposing a mutable pending record implicitly.

Exit: a losing or aborted worker cannot alter another request's forcing or committed evidence. Check all registries, not only water history/memory.

Mapping: C11; F08/F09; AB-DAT-001/004/010/011/012, AB-ARC-007/008.

## 5. Additional calculation-identity qualification — Q01

The cold January 2 query after a January 3 head now preserves the returned theta and head sequence. A further control compares the next identical January 4 calculation with versus without that intervening historical query:

| Path | January 4 theta | January 4 checkpoint ID |
|---|---|---|
| No historical query | [0.1489, 0.2052, 0.2163, 0.2239, 0.2295] | cp_hyd_P_2026-01-04_09f99a85589f |
| Historical query first | Identical profile | cp_hyd_P_2026-01-04_0d9fff5478af |

The query changes cached history while restoring only latest water memory, so subsequent dependency reconstruction differs. This is an identity/provenance qualification, not a demonstrated numerical moisture error in this case. Scientific checkpoint identity should not change solely because a historical read was interposed over the same durable head and later calculation input. Separate query response/cache from the operational scientific generation; verify full state/forcing identity and replay lineage. R3: AB-ARC-009 and AB-DAT-011/012. This lower-priority qualification should not obscure the successful C10 numerical fix.

## 6. Focused next implementation plan

| Order | Work | Findings | Exit evidence |
|---:|---|---|---|
| 1 | One durable operation lifecycle: generation, STOP intent/receipt, physical completion guard and phase projection | D01/D02/D07 | Every failure/late completion remains owned and monitored until qualified completion; duplicates preserve phase. |
| 2 | Unconditional atomic operation admission with explicit budget eligibility and canonical payload/support binding | D05/D06 | No-budget/zero-depth/field-mutation/interleaving matrix cannot duplicate or falsely join incompatible commands. |
| 3 | One conserving immutable accounting journal, qualified measurement contract, original-period adjustment semantics | D03/D08/D09/D10 | All stop paths conserve unresolved exposure; corrections/retries preserve quantities, periods and support. |
| 4 | Complete state validation, authoritative aggregate reconciliation and durable initialization/recovery | D04 | Corrupt/inconsistent ledger or failed initialization cannot invent zero exposure. |
| 5 | Fully local candidate evidence and generation-protected RAM publication/rehydration | D11/D12 | Losing workers cannot contaminate winners or erase later publications. |
| 6 | Separate historical query cache from operational calculation identity | Q01 | Exact scientific inputs/current head produce the same later checkpoint identity regardless of interposed reads. |
| 7 | Integrated acceptance of relevant F08/F09/F16–F19 targets | All relevant criteria | Controlled-software invariants first, then the required process/driver/field objectives; preserve explicit open gates until evidence exists. |

Orders 1/2 converge on one operation schema. Orders 3/4 converge on one receipt/journal schema. Order 5 can proceed independently in the trajectory lane. Do not solve each finding with another parallel receipt format or unconditional cache fallback. Maintain the already passing controls alongside the new invariant checks.

No program estimate rollup is changed here. The current findings need schema/integration agreement before credible per-task sizing; the existing master-plan estimates remain plan estimates.

## 7. Scientific relevance to R3

These failures affect agronomic interpretation as well as software reliability. A command target or provisional quota debit is not observed irrigation input. False zero or lost duration changes water balances, intervention response attribution and downstream training/profit inputs. Uncommitted irrigation appearing in a trajectory makes the state depend on concurrent scheduling rather than its declared evidence lineage. Historical reads must preserve the scientific state/identity of the live trajectory.

| R3 requirement | Relevant target | Findings |
|---|---|---|
| AB-EXE-002 | ACK, physical start, delivery, outcome and unknown remain distinct. | D01/D02/D03/D07/D09/D10 |
| AB-EXE-003 | Reconciliation/idempotency precedes potential duplication. | D01/D05/D06/D08/D10 |
| AB-EXE-004 | Budgets, timers and fencing protect operations despite missing telemetry. | D01/D02/D03/D04/D05 |
| AB-DAT-003/011 | Immutable previous receipts/events and consistent scientific identity. | D08/D10/D12/Q01 |
| AB-DAT-004 | Committed evidence/cutoff controls temporal replay. | D12 |
| AB-DAT-005/006 | Missing/zero and observed/prior/reconstructed provenance remain separate. | D03/D04/D06/D08/D09/D10 |
| AB-DAT-007 | Quantities and geometry/support conversions remain traceable. | D06/D09/D10 |
| AB-DAT-010 | Management command, delivery, cancellation and unknown states remain distinct. | D01/D02/D03/D07/D08/D10/D12 |
| AB-DAT-012/013 | Persistence, invalidation and scope isolation support coherent replay. | D04/D06/D11/D12/Q01 |
| AB-ARC-006/007/008 | Degradation cannot promote certainty; compatible publication and concurrent effects are controlled. | D01/D02/D04/D05/D07/D08/D11/D12 |
| AB-ARC-009 | Scientific calculation identity is separate from query/response history. | Q01 |

This is targeted traceability, not a claim that every mapped requirement is entirely missing. Corrected finite-value checks, exact numerical replay, separate target/litre observations and the original two-worker winner recovery are genuine progress.

## 8. Verbatim new reproduction observations

The following are controlled-software observations, not field measurements. The marker failure and receipt-corruption cases include explicit injected faults. The concurrency cases use real production persistence/CAS with controlled interleavings.

```json
{
  "cancel_fence_rejected": {
    "before_late_START": {
      "event_status": "CANCELLED",
      "physical_running": false,
      "physical_start_calls": 1,
      "physical_stop_calls": 1,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 0.0,
      "settled_mm": 8.0,
      "delivery_context": null,
      "actuator_status": "ONLINE",
      "shared_reserved_mm": 0.0
    },
    "after_late_START": {
      "event_status": "CANCELLED",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 2,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 0.0,
      "settled_mm": 8.0,
      "delivery_context": null,
      "actuator_status": "ONLINE",
      "shared_reserved_mm": 0.0
    }
  },
  "cancel_fence_exception": {
    "before_late_START": {
      "event_status": "CANCELLED",
      "physical_running": false,
      "physical_start_calls": 1,
      "physical_stop_calls": 1,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 0.0,
      "settled_mm": 8.0,
      "delivery_context": null,
      "actuator_status": "ONLINE",
      "shared_reserved_mm": 0.0
    },
    "after_late_START": {
      "event_status": "CANCELLED",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 2,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 0.0,
      "settled_mm": 8.0,
      "delivery_context": null,
      "actuator_status": "ONLINE",
      "shared_reserved_mm": 0.0
    }
  },
  "watchdog_late_stop_rejected": {
    "before_late_START": {
      "event_status": "EMERGENCY_STOPPED",
      "physical_running": false,
      "physical_start_calls": 1,
      "physical_stop_calls": 1,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 0.0,
      "settled_mm": 8.0,
      "delivery_context": null,
      "actuator_status": "ONLINE",
      "shared_reserved_mm": 0.0
    },
    "after_late_START": {
      "event_status": "EMERGENCY_STOPPED",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 2,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 0.0,
      "settled_mm": 8.0,
      "delivery_context": "START_ZONE",
      "actuator_status": "EXECUTING",
      "shared_reserved_mm": 0.0
    }
  },
  "error_stop_exposure": {
    "first_status": "FAILED",
    "first_stopped": true,
    "stopped_receipts": {},
    "reserved_after_first": {},
    "settled_after_first": {},
    "second_8mm_status": "EXECUTING"
  },
  "completion_while_executing": {
    "after_completion": {
      "event_status": "COMPLETED",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 0,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 0.0,
      "settled_mm": 0.0,
      "delivery_context": "START_ZONE",
      "actuator_status": "EXECUTING",
      "shared_reserved_mm": 0.0
    },
    "second_status": "EXECUTING",
    "both_running": true
  },
  "phase_projection": [
    {
      "case": "failed_cancel",
      "owner_status": "STOP_REQUESTED",
      "durable_status": "EXECUTING",
      "fresh_duplicate_status": "EXECUTING"
    },
    {
      "case": "offline",
      "owner_status": "STOP_REQUESTED",
      "durable_status": "EXECUTING",
      "fresh_duplicate_status": "EXECUTING"
    },
    {
      "case": "validating",
      "owner_status": "VALIDATING",
      "durable_status": "UNSETTLED",
      "fresh_duplicate_status": "DISPATCHING"
    }
  ],
  "zero_and_area_payload_conflicts": [
    {
      "field": "target_duration_minutes",
      "changed_to": 0,
      "status": "EXECUTING",
      "returned_value": 0
    },
    {
      "field": "target_flow_rate_lpm",
      "changed_to": 0,
      "status": "EXECUTING",
      "returned_value": 0
    },
    {
      "field": "effective_area_ha",
      "changed_to": 2,
      "status": "EXECUTING",
      "returned_value": 2
    }
  ],
  "zero_without_budget": {
    "statuses": [
      "EXECUTING",
      "EXECUTING"
    ],
    "START_calls": 2
  },
  "inconsistent_rollups": {
    "prior_receipt_mm": 8.0,
    "second_status": "EXECUTING",
    "settled_reported": 0.0,
    "reserved_reported": 8.0
  },
  "unvalidated_numeric_fields": [
    {
      "field": "duration_minutes",
      "value": -1,
      "schema_result": "accepted"
    },
    {
      "field": "flow_rate_lpm",
      "value": true,
      "schema_result": "accepted"
    }
  ],
  "marker_write_failure_then_ledger_loss": {
    "marker_exists": false,
    "statuses": [
      "EXECUTING",
      "EXECUTING"
    ],
    "both_running": true
  },
  "settlement_missingness": [
    {
      "case": "zero_missing_area",
      "status": "COMPLETED",
      "settled_mm": 8.0,
      "actual_duration": 10.0,
      "receipt": {
        "actual_duration_minutes": 10.0,
        "actual_volume_l": 0.0,
        "date": "2026-10-10",
        "delivered_volume_mm": 8.0,
        "device_id": "device",
        "duration_minutes": 10,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "season",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T14:53:46.200499+00:00",
        "volume_mm": 8.0,
        "zone_id": "zone"
      }
    },
    {
      "case": "zero_with_area",
      "status": "COMPLETED",
      "settled_mm": 0.0,
      "actual_duration": 10.0,
      "receipt": {
        "actual_duration_minutes": 10.0,
        "actual_volume_l": 0.0,
        "date": "2026-10-10",
        "delivered_volume_mm": 0.0,
        "device_id": "device",
        "duration_minutes": 10,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "season",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T14:53:46.203946+00:00",
        "volume_mm": 0.0,
        "zone_id": "zone"
      }
    },
    {
      "case": "invalid_duration",
      "status": "COMPLETED",
      "settled_mm": 8.0,
      "actual_duration": 0.0,
      "receipt": {
        "actual_duration_minutes": 0.0,
        "actual_volume_l": 80000.0,
        "date": "2026-10-10",
        "delivered_volume_mm": 8.0,
        "device_id": "device",
        "duration_minutes": 10,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "season",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T14:53:46.207846+00:00",
        "volume_mm": 8.0,
        "zone_id": "zone"
      }
    }
  ],
  "completed_receipt_rehydration": {
    "original_actual_duration": 6.0,
    "retry_actual_duration": 0.0,
    "retry_area_ha": null,
    "persisted_actual_duration": 6.0,
    "persisted_area_present": false
  },
  "stopped_correction_period": {
    "before_receipt": {
      "date": "2026-01-01",
      "delivered_volume_mm": 8.0,
      "device_id": "",
      "duration_minutes": 0.0,
      "flow_rate_lpm": 0.0,
      "plot_id": "plot",
      "season": "S1",
      "target_volume_mm": 8,
      "timestamp": "2026-10-10T14:53:46.213592+00:00",
      "zone_id": ""
    },
    "after_receipt": {
      "date": "2026-10-10",
      "delivered_volume_mm": 3.0,
      "device_id": "",
      "duration_minutes": 0.0,
      "flow_rate_lpm": 0.0,
      "plot_id": "plot",
      "season": "default_season",
      "target_volume_mm": 8,
      "timestamp": "2026-10-10T14:53:46.214019+00:00",
      "zone_id": ""
    },
    "after_daily": {
      "plot:2026-01-01": 8.0,
      "plot:2026-10-10": -5.0
    },
    "after_season": {
      "plot:S1": 8.0,
      "plot:default_season": -5.0
    },
    "next_read": "CorruptedQuotaStoreError"
  },
  "stop_then_settle_double_accounting": {
    "total_mm": 11.0,
    "stopped": {
      "date": "2026-10-10",
      "delivered_volume_mm": 8.0,
      "device_id": "",
      "duration_minutes": 0.0,
      "flow_rate_lpm": 0.0,
      "plot_id": "plot",
      "season": "season",
      "target_volume_mm": 8,
      "timestamp": "2026-10-10T14:53:46.215316+00:00",
      "zone_id": ""
    },
    "settled": {
      "actual_duration_minutes": 0.0,
      "actual_volume_l": 30000.0,
      "date": "2026-10-10",
      "delivered_volume_mm": 3.0,
      "device_id": "",
      "duration_minutes": 0.0,
      "flow_rate_lpm": 0.0,
      "plot_id": "plot",
      "season": "default_season",
      "target_volume_mm": 8,
      "timestamp": "2026-10-10T14:53:46.215627+00:00",
      "volume_mm": 3.0,
      "zone_id": ""
    }
  },
  "conflicting_settlement_retry": {
    "outcome": "silently_accepted",
    "persisted_receipt": {
      "actual_duration_minutes": 0.0,
      "actual_volume_l": 40000.0,
      "date": "2026-10-10",
      "delivered_volume_mm": 4.0,
      "device_id": "",
      "duration_minutes": 0.0,
      "flow_rate_lpm": 0.0,
      "plot_id": "plot",
      "season": "default_season",
      "target_volume_mm": 8,
      "timestamp": "2026-10-10T14:53:46.216898+00:00",
      "volume_mm": 4.0,
      "zone_id": ""
    }
  },
  "no_budget_same_operation_race": {
    "workers": [
      {
        "worker": "A",
        "status": "EXECUTING",
        "starts": 1
      },
      {
        "worker": "B",
        "status": "EXECUTING",
        "starts": 1
      }
    ],
    "total_STARTs": 2
  },
  "forward_after_historical_query": [
    {
      "historical_query_first": false,
      "head_before": "cp_hyd_P_2026-01-03_15b2c4cb6d22",
      "future_theta": [
        0.1489,
        0.2052,
        0.2163,
        0.2239,
        0.2295
      ],
      "head_after": "cp_hyd_P_2026-01-04_09f99a85589f",
      "history_days": [
        "2026-01-02",
        "2026-01-03",
        "2026-01-04"
      ]
    },
    {
      "historical_query_first": true,
      "head_before": "cp_hyd_P_2026-01-03_15b2c4cb6d22",
      "future_theta": [
        0.1489,
        0.2052,
        0.2163,
        0.2239,
        0.2295
      ],
      "head_after": "cp_hyd_P_2026-01-04_0d9fff5478af",
      "history_days": [
        "2026-01-02",
        "2026-01-03",
        "2026-01-04"
      ]
    }
  ],
  "loser_evidence_in_winning_checkpoint": {
    "control_winner_theta": [
      0.2423,
      0.2293,
      0.221,
      0.2259,
      0.2295
    ],
    "concurrent_winner_theta": [
      0.2423,
      0.2543,
      0.221,
      0.2259,
      0.2295
    ],
    "loser_outcome": "ConcurrencyConflictError",
    "winner_irrigation_mm": 5.0,
    "winner_event_ids": [
      "candidate-A"
    ]
  },
  "new_winner_during_rollback_rehydration": {
    "loser_outcome": "ConcurrencyConflictError",
    "first_winner_head": "cp_hyd_P_2026-01-03_4293170e59c5",
    "new_winner_head": "cp_hyd_P_2026-01-04_de9579c93a20",
    "cached_head_before_loser": "cp_hyd_P_2026-01-04_de9579c93a20",
    "cached_head_after_loser": "cp_hyd_P_2026-01-03_4293170e59c5",
    "durable_head_after_loser": "cp_hyd_P_2026-01-04_de9579c93a20",
    "third_water_returned": true,
    "history_days_after_loser": [
      "2026-01-02",
      "2026-01-03"
    ]
  }
}
```

## 9. All 88 independent probe groups

Full observed transcripts are included in the companion ZIP. Some old key names still describe the original defect even when the current result passes; use observed values and the reconciliation table as the verdict. Production import metadata in two transcripts is excluded from the group count.

| Harness | Groups | Identifiers |
|---|---:|---|
| probe | 32 | `failed_stop_retention`; `failed_cancel_retention`; `same_dispatcher_duplicate`; `empty_source_conflict`; `same_process_monitor_quota`; `direct_command_numeric`; `dispatcher_flow_default_laundering`; `idle_ack_loss_no_redose`; `uncertain_start_query_failure`; `offline_status_completion`; `lost_registry_completion`; `validation_gap_releases_quota`; `new_dispatcher_redoses_completed_operation`; `conflicting_identity_false_success`; `inflight_duplicate_false_success`; `bare_executing_misattributed_to_new_operation`; `restart_elapsed_utc`; `restart_naive_start_resets_allowance`; `restart_forgets_stop_requested`; `restart_expired_failed_stop_no_reservation`; `restart_uncertain_releases_reservation`; `elapsed_without_poll`; `elapsed_after_poll`; `settlement_uses_target_not_measurement`; `settlement_not_idempotent`; `yesterday_debit_reduces_new_daily_budget`; `nonfinite_budget_admitted`; `actual_two_process_quota`; `fresh_process_forgets_quota_store`; `two_thread_check_reserve_race`; `weather_numeric_control`; `early_handler_control` |
| hydraulic | 11 | `checkpoint_controls`; `checkpoint_retry_after_head_failure`; `runner_retry_publishes_orphan_cache`; `warm_exact_repeat`; `cold_exact_repeat`; `changed_dependencies_reuse_cached_result`; `fresh_store_failure`; `fresh_CAS_conflict`; `warm_revision_CAS_conflict`; `changed_head_warm_cold`; `withdrawal_roundtrip` |
| adversarial | 10 | `corrupt_quota_fail_open`; `season_identity_lost`; `confirmed_stop_drops_unreconciled_delivery`; `fresh_dispatcher_active_payload_conflict`; `fresh_dispatcher_settled_payload_conflict`; `invalid_restart_timestamp_fresh_allowance`; `missing_registry_restart_elapsed`; `pending_START_blocks_monitor_and_cancel`; `same_event_double_admission`; `stale_live_lock_takeover` |
| edge | 13 | `pending_cancel_applied_before_ack`; `pending_cancel_applied_after_stop`; `pending_watchdog_late_application`; `payload_binding`; `atomic_payload_binding`; `pending_duplicate_failure`; `operation_claim_quota_gating`; `storage_validation`; `stop_accounting`; `cancelled_operation_replay`; `stopped_receipt_repeat`; `measured_settlement`; `cold_historical_replay` |
| concurrency | 1 | `loser_rollback_erases_winner_RAM` |
| dependency | 1 | `individual_dependency_changes` |
| boundary | 17 | `cancel_fence_rejected`; `cancel_fence_exception`; `watchdog_late_stop_rejected`; `error_stop_exposure`; `completion_while_executing`; `phase_projection`; `zero_and_area_payload_conflicts`; `zero_without_budget`; `inconsistent_rollups`; `unvalidated_numeric_fields`; `marker_write_failure_then_ledger_loss`; `settlement_missingness`; `completed_receipt_rehydration`; `stopped_correction_period`; `stop_then_settle_double_accounting`; `conflicting_settlement_retry`; `no_budget_same_operation_race` |
| hydraulic-boundary | 3 | `forward_after_historical_query`; `loser_evidence_in_winning_checkpoint`; `new_winner_during_rollback_rehydration` |

## 10. Scope limits and acceptance conclusion

The source is pinned and the nominal fixes are reproduced. The new failure-boundary evidence prevents full C01–C11/F-package closure. It is not evidence that the entire project fails, nor does it cancel independent implementation/research work.

No externally reachable exploitation route is asserted for a production-symbol counterexample. Physical failure observations refer to the controlled driver state, not field-controller performance. Same-host lock and quota probes do not prove cross-host fencing or hardware protections. The duration case requiring an explicit poll does not establish autonomous cutoff if the polling scheduler dies. The supplied monograph remains the target; this report verifies only the affected clauses, not every scientific/agronomic/economic/ML claim.

Start the concrete next repairs above. Keep all six acceptance tickets open until the relevant controlled-software and integrated evidence succeeds. Passing the reported repository tests is useful regression evidence, but it does not establish the invariants that these independent cases violate.

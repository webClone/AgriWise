# AgriBrain deep verification of c9de418 — D01–D12 and Q01

Review date: 2026-10-10 UTC  
Pinned GitHub main: `c9de418a1e7060d4842320579cea5e9a0b1a8433`  
Parent: `acac42c2627f699fe1f44192dcec2997b528cdbb`  
Commit publication: 2026-10-10T16:21:23Z  
Method: production source inspection, independent controlled-software reproduction, R3 target traceability.

## 1. Readiness decision

**The original specific D01–D12/Q01 cases show substantial, independently reproduced correction. Full defect-group and package closure is still unsupported.** This review identifies nine remaining groups N01–N09, including one pre-existing global emergency-stop failure newly covered here. These review-local IDs do not replace canonical F/T package IDs or R3 requirements.

Proceed with focused corrective implementation. Keep ST03-F08-FA, ST03-F09-FA and ST06-F16-FA through ST06-F19-FA open. Several controlled-software acceptance invariants still fail; the gates are not waiting solely for field tests.

The successful original numerical historical replay, sequential historical-query identity, candidate-event isolation and scoped rollback corrections should be retained. New failures are concentrated in operation recovery, measurement/receipt contracts, full publication coverage and scope isolation.

Independent world-model/Omega research need not wait for every repair. Its scientific input eligibility must exclude unqualified delivery receipts and must establish scope isolation before interpreting separate scenarios as independent.

## 2. Scope and integrity

- Main was pinned and rechecked at c9de418 after the probe execution.
- Four production modules changed: actuator, dispatcher, safety and Layer 3 decision runner. schemas.py and canonical_worldline.py are unchanged from acac42c but their exercised APIs remain dependencies.
- 430 production Python dependency files exactly match Git blob hashes in the pinned tree. This verifies source identity, not semantic coverage of every module.
- All four changed modules parse successfully. No repository test source or audit assertion was used as correctness evidence. No production source, plan, branch or hardware was modified/operated.
- **99 independent probe groups** were executed: the previous 88 groups, adapted only where the repaired production contract rejected corrupt input or removed a superseded receipt, plus 11 new continuity groups. Groups contain subcases and are not pytest pass counts. Successful controls and failures both appear in the results.
- No remaining harness errors. The global-stop NameError is an observed production exception captured by the reproduction, not an independent-harness error.
- Original three-worker rollback probing was adapted to account for the new publication lock: the third worker commits on disk then waits for RAM publication while rollback is paused; release occurs explicitly, with no artificial timeout. Final RAM and disk agree.
- Runtime: Linux / Python 3.12.14. Evidence includes same-host process and thread scheduling; it does not certify multi-host or device-side fencing.
- The reported 13 new corrective tests, 11 prior corrective tests and 396 repository tests were not independently recertified. Those results can coexist with these counterexamples.

| Changed production file | Exact pinned Git blob |
|---|---|
| [services/agribrain/irrigation_runtime/actuator.py](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/actuator.py) | `2a90b1336ec3fe51cf250872dc7607f6b75e59dd` |
| [services/agribrain/irrigation_runtime/dispatcher.py](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/dispatcher.py) | `233942b7e1d65f1c64f5e263b114f197669df335` |
| [services/agribrain/irrigation_runtime/safety.py](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/safety.py) | `4c390383e2c9ba64b22e292de514ec8060057c44` |
| [services/agribrain/layer3_decision/runner.py](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/layer3_decision/runner.py) | `a5a47dfb75e5e28bbf07136f3250bda0cc548396` |

## 3. Original-claim reconciliation

Each result below credits the specific exercised correction. It is not full F-package acceptance.

| Original item | Independently observed result | Remaining scope |
|---|---|---|
| D01 failed late STOP | Failure restores STOP_REQUESTED, active monitoring and exposure. | Old stopped receipt still wins fresh lookup; deadline re-registration resets origin. N01. |
| D02 premature completion | EXECUTING event stays active and reserved; second over-budget command is blocked. | Missing observations after VALIDATING still release exposure as zero. N02. |
| D03 ERROR-stop accounting | 8 mm stopped exposure is retained; a second 8 mm against 10 mm is blocked. | Target debit is still unqualified delivery, requiring receipt provenance. N02/N06. |
| D04 ledger corruption / marker | Deleted rollups and invalid duration/flow now raise typed corruption; marker-write failure blocks the first physical START. | Full physical cross-field schema and aggregate reverse conservation are incomplete. N03. |
| D05 no-budget admission | Zero and positive no-budget repeats/interleavings issue one START. | Corrected specific operation-admission case; integrated ownership recovery still needed. N01. |
| D06 payload binding | Changed valid zero duration/flow and 1→2 ha support are rejected. | Missing/present support, restart payload and receipt observations differ. N04. |
| D07 phase projection | Failed cancellation, OFFLINE and VALIDATING agree across owner/store/fresh duplicate. | Late reopened terminal records conflict; other recovery routes are not fully integrated. N01/N04/N09. |
| D08 conserving receipts | January 1/S1 correction stays in that period; stopped 8→settled 3 yields 3; conflicting depth/target retry raises ValueError. | Reverse receipt order, observation conflicts and immutable lineage remain. N04/N05/N06. |
| D09 zero/duration | Explicit 0 L without area settles 0; Inf actual duration rejects and keeps exposure. | Omitted vs explicit zero and nonzero without support remain conflated. N02/N03. |
| D10 completed replay | Ordinary fresh replay restores actual duration 6 min and area 1 ha. | Full command/outcome identity across missingness and restart is incomplete. N04. |
| D11 rollback race | Two-worker and lock-qualified three-worker final RAM/disk equality pass. | Initial hydration/exact historical read are outside that protocol. N07. |
| D12 pending irrigation | Winning no-irrigation theta matches control and its checkpoint contains no losing candidate event. | Full scope/publication isolation still has N07/N08. |
| Q01 sequential historical query | Identical January 4 theta and checkpoint ID with/without interposed January 2 query. | Concurrent historical query can still overwrite live RAM. N07. |

Controls from earlier review also cover invalid numeric commands/budgets, failed STOP retention, uncertain ACK handling, cross-process quotas, live-owner locking, persistence error propagation and ISO withdrawals. The elapsed-without-poll control does not prove an autonomous watchdog if the polling scheduler stops.

## 4. Remaining reproducible findings

P0 concerns a demonstrated cutoff/recovery failure or unsupported release of unresolved exposure. P1 concerns scientific state, accounting, identity or lineage consistency. Service-level findings do not establish externally reachable exploitation paths.

### N01 — P0 recovery / P1 phase and deadline consistency — Recovered late-STOP ownership conflicts with a terminal receipt

Source: [irrigation_runtime/dispatcher.py:208–249](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/dispatcher.py#L208-L249); [irrigation_runtime/dispatcher.py:432–477](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/dispatcher.py#L432-L477); [irrigation_runtime/dispatcher.py:1020–1023](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/dispatcher.py#L1020-L1023); [irrigation_runtime/safety.py:1173–1188](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/safety.py#L1173-L1188).

**Mechanism.** The new late-fence failure path correctly restores local and durable STOP_REQUESTED ownership. It does not supersede the stopped receipt written by the earlier successful cancellation. Fresh submit checks stopped receipts before active records. It therefore returns CANCELLED for the same operation that is now STOP_REQUESTED. Restart reconciliation skips that terminal event. Monitoring is also registered with elapsed_minutes omitted, replacing the original monotonic start with the current clock.

**Independent observation.** At clock 601 s for a 10-minute operation, delayed START applies after cancellation; CMD-FENCE and the subsequent emergency STOP fail. Owner and durable active phase are STOP_REQUESTED and the simulation is running. A fresh caller returns CANCELLED. Passing that returned event to fresh reconcile_on_restart yields zero active events and zero monitored events. The restored monitor has start_monotonic=601 and reports zero duration violations at the original expiry. The original owner does attempt another STOP on its next poll; this is not a claim that every STOP retry is disabled.

**Qualification.** The fresh-call→restart combination is a production-service reproduction with software controllers. An actual HTTP/persistence loader using this exact combination was not established. The confirmed problem is contradictory authoritative views and skipped recovery for that returned event.

**Implementation repair.** Make one durable operation record authoritative over older terminal/accounting receipts. A failed late fence must append a superseding unresolved phase and preserve the original operation deadline. Recovery must reconcile the current operation state even if an older receipt says cancelled. Do not infer physical closure from receipt lookup order.

**Acceptance evidence.** After late application and every STOP failure variant, local owner, fresh caller and restart recovery agree on unresolved STOP intent; ownership/monitoring survive, and original elapsed time is preserved.

**Target mapping.** D01/D07; F16/F17/F18; AB-EXE-002/003/004, AB-DAT-010, AB-ARC-006/008.

### N02 — P0 unresolved-accounting release / P1 physical provenance — Omitted completion measurements are still treated as observed zero

Source: [irrigation_runtime/dispatcher.py:810–865](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/dispatcher.py#L810-L865); [irrigation_runtime/safety.py:849–858](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/safety.py#L849-L858).

**Mechanism.** The EXECUTING/VALIDATING guard is corrected, but complete_event still defaults both observation arguments to 0.0. Missing and explicit measured zero remain indistinguishable. Nonzero litres without effective area still become target_volume_mm. Store settlement also defaults absent/invalid observations to zero.

**Independent observation.** Submit an 8 mm command, let the simulated controller become idle, and enter VALIDATING with 8 mm unresolved reservation. Calling complete_event(E) with no measurements publishes COMPLETED, removes the reservation, and settles 0 mm. Explicit complete_event(E,0,0) produces the same receipt. With 160,000 L but no area, it completes at the commanded 8 mm, not a support-qualified measured depth.

**Qualification.** No actual water amount is asserted for the omitted-measurement simulation. The failure is release of unmeasured exposure and publication of a fabricated observation. The explicit-zero control correctly remains zero, and invalid duration through complete_event is now rejected.

**Implementation repair.** Use optional typed observations with explicit missingness/provenance. Missing delivery must retain unresolved accounting or a clearly labelled estimate; it must not become observed zero. Preserve volume when support is missing and defer measured-depth certification. Measurement validation should retain a recoverable validation phase rather than manufacture a terminal result.

**Acceptance evidence.** Omitted, explicit zero, nonzero, invalid and support-missing observations produce distinct qualified outcomes; no unsupported physical observation releases exposure.

**Target mapping.** D02/D09; F16/F17; AB-DAT-005/006/007/010, AB-EXE-002/004.

### N03 — P1 — The ledger reader and writer still disagree on the full physical schema

Source: [irrigation_runtime/safety.py:187–303](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/safety.py#L187-L303); [irrigation_runtime/safety.py:787–866](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/safety.py#L787-L866).

**Mechanism.** Settled volume_mm is validated but settled delivered_volume_mm is not validated or checked against it. Aggregate reconciliation iterates expected receipt keys only, so unrelated nonzero aggregates can survive without a receipt. Direct settlement coerces invalid actual volume/duration to zero before writing.

**Independent observation.** For a settled 4 mm / 40,000 L / 1 ha receipt, replace delivered_volume_mm with True or 99 while keeping volume_mm=4. _read_state accepts both. NaN is correctly rejected by JSON numeric parsing (control). Add 9 mm aggregate entries for a ghost plot with no receipt: the store accepts them and reports 9. Direct settle with NaN litres and Inf duration accepts the request and writes both actual fields as 0.0.

**Qualification.** These schema and writer probes exercise production store APIs and controlled file corruption. They do not demonstrate a remote file modification path. The extra aggregate case is an erroneous debit, not quota undercount or an observed physical overrun.

**Implementation repair.** Validate the complete typed command/receipt/measurement schema before every write and every read, including cross-field physical identities. Reconcile both directions over the union of aggregate and receipt keys. Invalid scalar values must raise typed errors or remain explicitly missing, never be laundered to zero.

**Acceptance evidence.** All supported scalar fields reject bool/nonfinite/negative values; delivered depth agrees with its measured volume/support when certified; receipt/aggregate conservation holds in both directions; invalid writes cannot publish a contradictory ledger.

**Target mapping.** D04/D09; F16/F17; AB-DAT-005/006/007/012, AB-ARC-006/007.

### N04 — P1 — Missing support, settlement observations and restart payloads are not fully bound

Source: [irrigation_runtime/dispatcher.py:302–329](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/dispatcher.py#L302-L329); [irrigation_runtime/safety.py:789–819](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/safety.py#L789-L819); [irrigation_runtime/dispatcher.py:1150–1160](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/dispatcher.py#L1150-L1160); [irrigation_runtime/safety.py:699–728](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/safety.py#L699-L728).

**Mechanism.** The zero/positive duration and flow comparisons are fixed. Area conflicts are checked only when both values are present in durable paths, unlike the stricter local comparison. Settlement retry identity omits actual litres/duration, device, zone and date/season. Restart monitoring calls omit command flow, so reserve replaces a valid stored 10 L/min with default 0.

**Independent observation.** A fresh active repeat with original area 1 ha and new area None is returned EXECUTING with None; the reverse direction also succeeds. The stopped/settled versions accept those missing/present changes. After settling 4 mm with 40,000 L / 6 min, retries changing litres to 99,999, actual duration to 99, device, zone or period all return success while retaining the old receipt. Restart an executing 10 L/min operation: the store becomes flow_rate_lpm=0 and a subsequent exact original repeat is FAILED as a payload conflict.

**Qualification.** The original concrete 1→2 ha conflict is correctly rejected and measured duration/area are rehydrated on an ordinary exact completed repeat. The new cases concern missingness, omitted identity dimensions and restart preservation.

**Implementation repair.** Define one canonical command identity and one immutable outcome identity. Missing support must have an explicit compatibility rule; it cannot silently add or remove support. Exact settlement retries compare every qualified receipt dimension. Carry the full original command/support through restart registration instead of default parameters.

**Acceptance evidence.** Local, fresh, atomic and restarted callers apply the same compatibility rule. Changing any supplied qualified command/outcome field conflicts; exact retries recover the complete original receipt without changing durable payload.

**Target mapping.** D06/D08/D10; F17/F18; AB-DAT-005/007/010/011/013, AB-EXE-003, AB-ARC-008.

### N05 — P1 — The reverse settled→stopped transition still double counts and changes the outcome

Source: [irrigation_runtime/safety.py:787–841](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/safety.py#L787-L841); [irrigation_runtime/safety.py:872–965](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/safety.py#L872-L965); [irrigation_runtime/dispatcher.py:208–286](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/dispatcher.py#L208-L286).

**Mechanism.** settle now removes/reconciles an earlier stopped receipt, correctly fixing stopped→settled. record_stopped_delivery does not check for an existing settled receipt, so the reverse order creates another debit and contradictory terminal receipts. Fresh submit gives stopped receipt precedence.

**Independent observation.** Settle E at 3 mm with commanded target 8. Record a later stopped exposure of 8 for E. The total becomes 11 mm and both settled and stopped receipts remain. A fresh repeat reports CANCELLED instead of the previously completed outcome.

**Qualification.** This is a production-store/service counterexample, not a measured 11 mm application. It is incorrect accounting and outcome projection under reversed/out-of-order receipt arrival.

**Implementation repair.** Use one operation accounting state machine with explicit transitions and adjustment lineage. Reordered/duplicate terminal notifications must reconcile or conflict, never create independent debits for one operation. Physical, accounting and validation outcomes need separate projections.

**Acceptance evidence.** Stopped→settled, settled→stopped and concurrent/repeated receipts conserve one operation total and retain a coherent terminal outcome.

**Target mapping.** D08; F16/F17/F18; AB-DAT-010/011, AB-EXE-002/003, AB-ARC-007/008.

### N06 — P1 scientific lineage — Receipt correction remains destructive rather than append-only

Source: [irrigation_runtime/safety.py:886–963](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/safety.py#L886-L963).

**Mechanism.** Original date/season retention and delta accounting are corrected, but the old stopped receipt is still replaced under the same event key. Settlement removes it entirely. There is no correction/reconciliation journal preserving the prior assertion and its lineage.

**Independent observation.** Record stopped E at 8 mm on January 1 / S1, then correct to 3 mm. Aggregates correctly become 3 and the next read succeeds. The original 8 mm receipt is absent from the ledger; the remaining dictionaries contain only the latest receipt and aggregates.

**Qualification.** This is a direct failure of the R3 immutable/append-only target, not a claim that the corrected 3 mm arithmetic is wrong. A separate external immutable journal could satisfy the target if integrated and demonstrated; none is written by the exercised store operation.

**Implementation repair.** Append immutable provisional, measured and correction records with supersession links, reason, actor/source identity and original scope/period. Materialize current balances and current receipt as projections of that journal. Do not use the mutable latest receipt as the entire history.

**Acceptance evidence.** A correction and stopped→measured reconciliation preserve both previous and new scientific assertions, permit deterministic aggregate reconstruction, and survive restart without losing lineage.

**Target mapping.** D08; F16/F18; AB-DAT-003/006/010/011, AB-ARC-007.

### N07 — P1 — Concurrent historical hydration can still overwrite a newer publication

Source: [layer3_decision/runner.py:1216–1232](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/layer3_decision/runner.py#L1216-L1232); [layer3_decision/runner.py:2356–2421](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/layer3_decision/runner.py#L2356-L2421); [layer3_decision/runner.py:2484–2521](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/layer3_decision/runner.py#L2484-L2521).

**Mechanism.** The new scoped lock protects rollback and normal publication. Initial hydration and the exact historical replay branch still mutate authoritative RAM without the same lock/generation check. A historical reader uses a checkpoint captured before another worker advances the head.

**Independent observation.** Commit January 2 and January 3. Pause an exact January 2 reader immediately after it reads the January 3 checkpoint. A second worker commits and publishes January 4. Resume the reader. It returns successfully, but RAM head becomes cp_hyd_P_2026-01-03_15b2c4cb6d22 and history contains only January 2–3; durable head remains cp_hyd_P_2026-01-04_09f99a85589f. No CAS failure or timeout is needed.

**Qualification.** The original rollback interleaving is corrected. This is a different same-process two-thread read/publication race, not a disk-head rollback. Disk remains correct; operational RAM is stale after both calls complete.

**Implementation repair.** Treat hydration and historical queries as generation-qualified reads into local snapshots. Use one scoped publication protocol across hydration, normal commit, rollback and exact historical replay. Return historical results without replacing live operational state from a stale capture; recheck the generation under synchronization before any RAM mutation.

**Acceptance evidence.** A newer head arriving before/during/after a historical load cannot be erased from RAM; disk and operational RAM converge to the latest committed generation after all workers finish.

**Target mapping.** D11/Q01; F08/F09; AB-DAT-012, AB-ARC-007/008/009.

### N08 — P1 scientific scope isolation — The legacy plot-only alias still supplies another scope’s hydraulic prior

Source: [layer3_decision/runner.py:1173–1204](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/layer3_decision/runner.py#L1173-L1204); [layer3_decision/runner.py:2181–2195](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/layer3_decision/runner.py#L2181-L2195); [layer3_decision/runner.py:2518–2521](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/layer3_decision/runner.py#L2518-L2521).

**Mechanism.** Registries are keyed by tenant/namespace/plot, but authoritative initial-state lookup falls back to _PLOT_WATER_STATE_MEMORY[plot_id]. That alias points to whichever scope ran most recently. A fresh independent scope with no checkpoint can therefore integrate from another tenant/namespace’s posterior.

**Independent observation.** For the same P identifier in an independent tenant or namespace, the fresh dry January 2 control gives theta=[0.2007,0.2218,0.2253,0.2277,0.2295]. First run P with 20 mm rain in the other scope, then run that identical fresh dry request: theta=[0.2124,0.2546,0.2473,0.2259,0.2295]. Both tenant and namespace variants reproduce the difference.

**Qualification.** The collision is deliberately tested with the same local plot identifier in distinct declared scopes. A globally unique plot-ID constraint could narrow tenant collisions, but it does not demonstrate namespace/scenario isolation. This test asserts numerical coupling, not data exfiltration.

**Implementation repair.** Use only fully scoped committed state as an authoritative prior. Keep plot-only compatibility aliases as read-only/display projections or remove them from scientific lookup. Qualify explicit shared priors with scope/version/provenance, rather than inheriting the latest alias. Include cycle/geometry/state epochs wherever the target requires separate trajectories.

**Acceptance evidence.** Fresh requests in tenant, namespace, cycle and geometry scenarios are invariant to unrelated scope execution order, unless an explicit qualified shared prior is supplied.

**Target mapping.** F01/F08/F09; AB-DAT-013, AB-ARC-007/008; relevant to isolated world-model/Omega experiments.

### N09 — P0 — Global emergency stop aborts on an undefined ActuatorStatus

Source: [irrigation_runtime/dispatcher.py:49–61](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/dispatcher.py#L49-L61); [irrigation_runtime/dispatcher.py:964–1007](https://github.com/webClone/AgriWise/blob/c9de418a1e7060d4842320579cea5e9a0b1a8433/services/agribrain/irrigation_runtime/dispatcher.py#L964-L1007).

**Mechanism.** emergency_stop_all references ActuatorStatus.ONLINE/ERROR, but the module does not import ActuatorStatus. Imports inside other methods are local bindings and cannot satisfy this method’s global lookup.

**Independent observation.** Start independent simulated devices A and B, then invoke emergency_stop_all. With either a successful or failed first STOP, it raises NameError: name ActuatorStatus is not defined on the first iteration. B remains running with zero STOP calls, and the registry-wide emergency stop callback is never reached. With successful first STOP, A is physically stopped but both event statuses still say EXECUTING.

**Qualification.** This defect also exists in the parent source; it was not introduced by c9de418. Previous probes did not exercise this global stop route. The failure is reproduced with unmodified production dispatcher code and simulated drivers.

**Implementation repair.** Import the production enum in the appropriate scope and independently handle each device’s stop outcome so one failure cannot abort remaining STOP attempts. Persist each unresolved phase, preserve accounting and execute registry fallback even when a per-event operation fails.

**Acceptance evidence.** With multiple actuators and success/rejection/exception/unavailable registry outcomes, every eligible STOP is attempted and every operation retains the correct owned/terminal state; no undefined name aborts the global cutoff.

**Target mapping.** F16/F17/F19; AB-EXE-004, AB-ARC-006. Independent import correction can proceed immediately.

## 5. Next implementation order and concrete exit conditions

The following is a targeted corrective batch, not a replacement estimate of the 52-package master program.

| Order | Deliverable | Concrete work | Exit evidence |
|---:|---|---|---|
| 0 | Reliable global cutoff | Fix enum import; attempt every device even on one rejection/exception; persist unresolved states; guarantee registry fallback. N09. | Multi-device STOP matrix reaches every device; preserves ownership/accounting and phases. |
| 1 | One authoritative durable operation lifecycle | Superseding phase/generation for late application; receipt precedence; original deadline; restart of active and validation states. N01. | Owner/fresh/restart state and deadline agree through successful/failed late fencing. |
| 2 | Qualified delivery contract | Optional observations; distinct omitted/zero/invalid; volume support; recoverable validation; no target-as-observed fallback. N02/N03. | Missing delivery retains exposure; explicit zero remains zero; certified depth traces to volume and support. |
| 3 | Complete operation and receipt identity | Full typed command/support identity; full immutable measured outcome identity; preserve original payload across restart. N04. | Exact retries succeed; every incompatible qualified mutation conflicts; restart preserves all command fields. |
| 4 | One immutable conserving journal | Both receipt arrival orders, idempotency, corrections with supersession lineage, schema validation on reads/writes, aggregate reconstruction. N03/N05/N06. | One operation debit; no contradictory receipt/status; previous assertions retained; rebuild matches all aggregates. |
| 5 | One scoped scientific snapshot protocol | Local hydration/read snapshots; generation-qualified publish for every path; eliminate plot-only authoritative prior fallback. N07/N08. | Historical reads cannot overwrite newer RAM; independent scopes are invariant to unrelated execution order. |
| 6 | Integrated acceptance evidence | Preserve original passing controls; exercise recovery and multi-process driver/service wiring; keep hardware-specific conclusions separate. | Relevant F08/F09/F16–F19 criteria demonstrably pass before marking their gates complete. |

Order 0 is an independent small cutoff repair and can proceed immediately. Operation/measurement/journal lanes need one agreed schema rather than independent ad hoc formats. The hydraulic lane can proceed in parallel as independent implementation work. No new engineer-hour estimate is asserted before those interfaces are agreed.

## 6. Plan and R3 monograph qualifications

The pinned task register Git blob is `8a564647af7e588802537817159117b349ff606b`, unchanged from the previously inspected register. ST03-F08-FA (line 406), ST03-F09-FA (443), ST06-F16-FA (796), ST06-F17-FA (833), ST06-F18-FA (870) and ST06-F19-FA (907) remain unchecked. Their criteria explicitly include controlled production-symbol software evidence, so open status cannot be explained solely as awaiting field trials.

Mappings use the previously supplied R3 monograph scientific requirement register. The pinned GitHub tree contains the earlier R2 monograph, not the supplied R3 document. No monograph was rewritten here; this targeted comparison does not re-audit all 153 requirements.

| R3 target | Scientific / architecture implication | Current findings |
|---|---|---|
| AB-EXE-002/003/004 | ACK, physical execution, delivery, uncertainty and reconciliation remain distinct; budgets/cutoff work through missing telemetry. | N01/N02/N04/N05/N09 |
| AB-DAT-003/011 | Correction retains earlier events/receipts; immutable assertions and identities support reproducible scientific history. | N04/N05/N06 |
| AB-DAT-005/006 | Missing, explicit zero, observed and provisional quantities have distinct field provenance. | N01/N02/N03/N04/N06 |
| AB-DAT-007 | Volume-depth conversion has qualified geometry/support and preserves units. | N02/N03/N04 |
| AB-DAT-010 | Command, delivery, cancellation and unknown outcomes are separate management facts. | N01/N02/N04/N05/N06 |
| AB-DAT-012/013 | Persistent state, coherent replay and declared tenant/namespace/cycle/geometry isolation are maintained. | N03/N04/N07/N08 |
| AB-ARC-006/007/008 | Degradation cannot invent certainty; all publication and recovery effects are generation/idempotency compatible. | N01/N03/N04/N05/N07/N08/N09 |
| AB-ARC-009 | A historical response must not alter the live calculation generation merely by being queried. | N07; sequential Q01 control passes |

Agronomic implication: inferred soil-water state must reflect its declared weather, intervention and prior scope. Command targets or provisional exposure are not measured irrigation. Missing delivery converted to zero, destructive receipt revisions and cross-scope priors can corrupt intervention attribution and downstream learning/economic evaluation, even while individual equations and ordinary replay controls pass.

## 7. Independent evidence — new continuity results

The JSON below is the observed output, with multiple subcases per group. It includes successful controls as well as failures. No literal physical water amount is inferred from simulated driver running flags.

### continuity

```json
{
  "late_stop_deadline_and_terminal_precedence": {
    "owner_status": "STOP_REQUESTED",
    "running": true,
    "elapsed_since_original_start_seconds": 601,
    "new_start_monotonic": 601.0,
    "watchdog_violations_at_original_expiry": 0,
    "stops_added_by_next_poll": 1,
    "durable_active_status": "STOP_REQUESTED",
    "stopped_receipt_also_present": true,
    "fresh_retry_status": "CANCELLED",
    "reserved_mm": 8.0,
    "settled_mm": 8.0,
    "fresh_recovery_active_events": 0,
    "fresh_recovery_monitored_events": 0
  },
  "global_emergency_stop_execution": [
    {
      "first_stop_fails": false,
      "outcome": "NameError: name 'ActuatorStatus' is not defined",
      "first_running": false,
      "second_running": true,
      "second_stop_calls": 0,
      "first_event_status": "EXECUTING",
      "second_event_status": "EXECUTING",
      "registry_stop_called": false
    },
    {
      "first_stop_fails": true,
      "outcome": "NameError: name 'ActuatorStatus' is not defined",
      "first_running": true,
      "second_running": true,
      "second_stop_calls": 0,
      "first_event_status": "EXECUTING",
      "second_event_status": "EXECUTING",
      "registry_stop_called": false
    }
  ],
  "restart_payload_preservation": {
    "recovered_owner_status": "EXECUTING",
    "command_flow": 10,
    "durable_flow": 0.0,
    "fresh_original_retry": "FAILED",
    "running": true
  },
  "completion_missingness": [
    {
      "case": "omitted",
      "status": "COMPLETED",
      "before_unsettled_mm": 8.0,
      "after_reserved_mm": 0.0,
      "after_settled_mm": 0.0,
      "receipt": {
        "actual_duration_minutes": 0.0,
        "actual_volume_l": 0.0,
        "date": "2026-10-10",
        "delivered_volume_mm": 0.0,
        "device_id": "device",
        "duration_minutes": 10,
        "effective_area_ha": 1.0,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "season",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T16:34:31.459349+00:00",
        "volume_mm": 0.0,
        "zone_id": "zone"
      }
    },
    {
      "case": "explicit_zero",
      "status": "COMPLETED",
      "before_unsettled_mm": 8.0,
      "after_reserved_mm": 0.0,
      "after_settled_mm": 0.0,
      "receipt": {
        "actual_duration_minutes": 0.0,
        "actual_volume_l": 0.0,
        "date": "2026-10-10",
        "delivered_volume_mm": 0.0,
        "device_id": "device",
        "duration_minutes": 10,
        "effective_area_ha": 1.0,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "season",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T16:34:31.465753+00:00",
        "volume_mm": 0.0,
        "zone_id": "zone"
      }
    },
    {
      "case": "nonzero_no_area",
      "status": "COMPLETED",
      "before_unsettled_mm": 8.0,
      "after_reserved_mm": 0.0,
      "after_settled_mm": 8.0,
      "receipt": {
        "actual_duration_minutes": 10.0,
        "actual_volume_l": 160000.0,
        "date": "2026-10-10",
        "delivered_volume_mm": 8.0,
        "device_id": "device",
        "duration_minutes": 10,
        "effective_area_ha": null,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "season",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T16:34:31.478711+00:00",
        "volume_mm": 8.0,
        "zone_id": "zone"
      }
    }
  ],
  "area_missingness_identity": [
    {
      "phase": "active",
      "original_area": 1,
      "new_area": null,
      "status": "EXECUTING",
      "returned_area": null
    },
    {
      "phase": "active",
      "original_area": null,
      "new_area": 1,
      "status": "EXECUTING",
      "returned_area": 1
    },
    {
      "phase": "stopped",
      "original_area": 1,
      "new_area": null,
      "status": "CANCELLED",
      "returned_area": 1.0
    },
    {
      "phase": "stopped",
      "original_area": null,
      "new_area": 1,
      "status": "CANCELLED",
      "returned_area": 1
    },
    {
      "phase": "settled",
      "original_area": 1,
      "new_area": null,
      "status": "COMPLETED",
      "returned_area": 1.0
    },
    {
      "phase": "settled",
      "original_area": null,
      "new_area": 1,
      "status": "COMPLETED",
      "returned_area": 1
    }
  ],
  "settled_retry_observation_conflicts": [
    {
      "changed": {
        "actual_volume_l": 99999
      },
      "retry": {
        "outcome": "accepted",
        "return": null
      },
      "persisted": {
        "actual_duration_minutes": 6.0,
        "actual_volume_l": 40000.0,
        "date": "2026-01-01",
        "delivered_volume_mm": 4.0,
        "device_id": "D",
        "duration_minutes": 10,
        "effective_area_ha": 1,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "S1",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T16:34:31.520790+00:00",
        "volume_mm": 4.0,
        "zone_id": "Z"
      }
    },
    {
      "changed": {
        "actual_duration_minutes": 99
      },
      "retry": {
        "outcome": "accepted",
        "return": null
      },
      "persisted": {
        "actual_duration_minutes": 6.0,
        "actual_volume_l": 40000.0,
        "date": "2026-01-01",
        "delivered_volume_mm": 4.0,
        "device_id": "D",
        "duration_minutes": 10,
        "effective_area_ha": 1,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "S1",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T16:34:31.522318+00:00",
        "volume_mm": 4.0,
        "zone_id": "Z"
      }
    },
    {
      "changed": {
        "device_id": "other"
      },
      "retry": {
        "outcome": "accepted",
        "return": null
      },
      "persisted": {
        "actual_duration_minutes": 6.0,
        "actual_volume_l": 40000.0,
        "date": "2026-01-01",
        "delivered_volume_mm": 4.0,
        "device_id": "D",
        "duration_minutes": 10,
        "effective_area_ha": 1,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "S1",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T16:34:31.523447+00:00",
        "volume_mm": 4.0,
        "zone_id": "Z"
      }
    },
    {
      "changed": {
        "zone_id": "other"
      },
      "retry": {
        "outcome": "accepted",
        "return": null
      },
      "persisted": {
        "actual_duration_minutes": 6.0,
        "actual_volume_l": 40000.0,
        "date": "2026-01-01",
        "delivered_volume_mm": 4.0,
        "device_id": "D",
        "duration_minutes": 10,
        "effective_area_ha": 1,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "S1",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T16:34:31.525282+00:00",
        "volume_mm": 4.0,
        "zone_id": "Z"
      }
    },
    {
      "changed": {
        "date": "2026-01-02",
        "season": "S2"
      },
      "retry": {
        "outcome": "accepted",
        "return": null
      },
      "persisted": {
        "actual_duration_minutes": 6.0,
        "actual_volume_l": 40000.0,
        "date": "2026-01-01",
        "delivered_volume_mm": 4.0,
        "device_id": "D",
        "duration_minutes": 10,
        "effective_area_ha": 1,
        "flow_rate_lpm": 10,
        "plot_id": "plot",
        "season": "S1",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T16:34:31.526626+00:00",
        "volume_mm": 4.0,
        "zone_id": "Z"
      }
    }
  ],
  "settled_then_stopped": {
    "total_mm": 11.0,
    "both_receipts_present": true,
    "fresh_retry_status": "CANCELLED",
    "state": {
      "reservations": {},
      "settled_daily": {
        "plot:2026-10-10": 11.0
      },
      "settled_plot_total": {
        "plot": 11.0
      },
      "settled_receipts": {
        "E": {
          "actual_duration_minutes": 0.0,
          "actual_volume_l": 30000.0,
          "date": "2026-10-10",
          "delivered_volume_mm": 3.0,
          "device_id": "device",
          "duration_minutes": 10,
          "effective_area_ha": 1,
          "flow_rate_lpm": 10,
          "plot_id": "plot",
          "season": "default_season",
          "target_volume_mm": 8,
          "timestamp": "2026-10-10T16:34:31.528113+00:00",
          "volume_mm": 3.0,
          "zone_id": "zone"
        }
      },
      "settled_season": {
        "plot:default_season": 11.0
      },
      "stopped_receipts": {
        "E": {
          "date": "2026-10-10",
          "delivered_volume_mm": 8.0,
          "device_id": "device",
          "duration_minutes": 10,
          "effective_area_ha": 1,
          "flow_rate_lpm": 10,
          "plot_id": "plot",
          "season": "default_season",
          "target_volume_mm": 8,
          "timestamp": "2026-10-10T16:34:31.529077+00:00",
          "zone_id": "zone"
        }
      }
    }
  },
  "correction_lineage": {
    "original": {
      "date": "2026-01-01",
      "delivered_volume_mm": 8.0,
      "device_id": "",
      "duration_minutes": 0.0,
      "effective_area_ha": null,
      "flow_rate_lpm": 0.0,
      "plot_id": "plot",
      "season": "S1",
      "target_volume_mm": 8,
      "timestamp": "2026-10-10T16:34:31.531869+00:00",
      "zone_id": ""
    },
    "latest": {
      "date": "2026-01-01",
      "delivered_volume_mm": 3.0,
      "device_id": "",
      "duration_minutes": 0.0,
      "effective_area_ha": null,
      "flow_rate_lpm": 0.0,
      "plot_id": "plot",
      "season": "S1",
      "target_volume_mm": 8,
      "timestamp": "2026-10-10T16:34:31.532916+00:00",
      "zone_id": ""
    },
    "journal_keys": [
      "reservations",
      "settled_daily",
      "settled_plot_total",
      "settled_receipts",
      "settled_season",
      "stopped_receipts"
    ],
    "old_receipt_still_present": false
  },
  "schema_and_writer_contracts": [
    {
      "field": "delivered_volume_mm",
      "value": "nan",
      "schema_result": "CorruptedQuotaStoreError"
    },
    {
      "field": "delivered_volume_mm",
      "value": "True",
      "schema_result": "accepted"
    },
    {
      "field": "delivered_volume_mm",
      "value": "99",
      "schema_result": "accepted"
    },
    {
      "case": "aggregate_without_receipt",
      "schema_result": "accepted",
      "ghost_amount": 9.0
    },
    {
      "case": "invalid_measurements_store_api",
      "result": {
        "outcome": "accepted",
        "return": null
      },
      "receipt": {
        "actual_duration_minutes": 0.0,
        "actual_volume_l": 0.0,
        "date": "2026-10-10",
        "delivered_volume_mm": 4.0,
        "device_id": "",
        "duration_minutes": 0.0,
        "effective_area_ha": 1,
        "flow_rate_lpm": 0.0,
        "plot_id": "plot",
        "season": "default_season",
        "target_volume_mm": 8,
        "timestamp": "2026-10-10T16:34:31.542157+00:00",
        "volume_mm": 4.0,
        "zone_id": ""
      }
    }
  ]
}
```

### hydraulic-continuity

```json
{
  "historical_read_overwrites_newer_publication": {
    "historical_read_returned": true,
    "winner_returned": true,
    "durable_head_before_read_finish": "cp_hyd_P_2026-01-04_09f99a85589f",
    "ram_head_before_read_finish": "cp_hyd_P_2026-01-04_09f99a85589f",
    "ram_head_after_read_finish": "cp_hyd_P_2026-01-03_15b2c4cb6d22",
    "durable_head_after_read_finish": "cp_hyd_P_2026-01-04_09f99a85589f",
    "history_days_after_read": [
      "2026-01-02",
      "2026-01-03"
    ]
  },
  "plot_alias_cross_scope_prior": [
    {
      "dimension": "tenant_id",
      "other_scope_ran_first": false,
      "theta": [
        0.2007,
        0.2218,
        0.2253,
        0.2277,
        0.2295
      ]
    },
    {
      "dimension": "tenant_id",
      "other_scope_ran_first": true,
      "theta": [
        0.2124,
        0.2546,
        0.2473,
        0.2259,
        0.2295
      ]
    },
    {
      "dimension": "namespace",
      "other_scope_ran_first": false,
      "theta": [
        0.2007,
        0.2218,
        0.2253,
        0.2277,
        0.2295
      ]
    },
    {
      "dimension": "namespace",
      "other_scope_ran_first": true,
      "theta": [
        0.2124,
        0.2546,
        0.2473,
        0.2259,
        0.2295
      ]
    }
  ]
}
```

## 8. Probe inventory and limits

| Result file | Groups | Keys |
|---|---:|---|
| probe-results.json | 32 | `failed_stop_retention`; `failed_cancel_retention`; `same_dispatcher_duplicate`; `empty_source_conflict`; `same_process_monitor_quota`; `direct_command_numeric`; `dispatcher_flow_default_laundering`; `idle_ack_loss_no_redose`; `uncertain_start_query_failure`; `offline_status_completion`; `lost_registry_completion`; `validation_gap_releases_quota`; `new_dispatcher_redoses_completed_operation`; `conflicting_identity_false_success`; `inflight_duplicate_false_success`; `bare_executing_misattributed_to_new_operation`; `restart_elapsed_utc`; `restart_naive_start_resets_allowance`; `restart_forgets_stop_requested`; `restart_expired_failed_stop_no_reservation`; `restart_uncertain_releases_reservation`; `elapsed_without_poll`; `elapsed_after_poll`; `settlement_uses_target_not_measurement`; `settlement_not_idempotent`; `yesterday_debit_reduces_new_daily_budget`; `nonfinite_budget_admitted`; `actual_two_process_quota`; `fresh_process_forgets_quota_store`; `two_thread_check_reserve_race`; `weather_numeric_control`; `early_handler_control` |
| hydraulic-results.json | 11 | `checkpoint_controls`; `checkpoint_retry_after_head_failure`; `runner_retry_publishes_orphan_cache`; `warm_exact_repeat`; `cold_exact_repeat`; `changed_dependencies_reuse_cached_result`; `fresh_store_failure`; `fresh_CAS_conflict`; `warm_revision_CAS_conflict`; `changed_head_warm_cold`; `withdrawal_roundtrip` |
| adversarial-results.json | 10 | `corrupt_quota_fail_open`; `season_identity_lost`; `confirmed_stop_drops_unreconciled_delivery`; `fresh_dispatcher_active_payload_conflict`; `fresh_dispatcher_settled_payload_conflict`; `invalid_restart_timestamp_fresh_allowance`; `missing_registry_restart_elapsed`; `pending_START_blocks_monitor_and_cancel`; `same_event_double_admission`; `stale_live_lock_takeover` |
| edge-results.json | 13 | `pending_cancel_applied_before_ack`; `pending_cancel_applied_after_stop`; `pending_watchdog_late_application`; `payload_binding`; `atomic_payload_binding`; `pending_duplicate_failure`; `operation_claim_quota_gating`; `storage_validation`; `stop_accounting`; `cancelled_operation_replay`; `stopped_receipt_repeat`; `measured_settlement`; `cold_historical_replay` |
| concurrency-results.json | 1 | `loser_rollback_erases_winner_RAM` |
| dependency-results.json | 1 | `individual_dependency_changes` |
| boundary-results.json | 17 | `cancel_fence_rejected`; `cancel_fence_exception`; `watchdog_late_stop_rejected`; `error_stop_exposure`; `completion_while_executing`; `phase_projection`; `zero_and_area_payload_conflicts`; `zero_without_budget`; `inconsistent_rollups`; `unvalidated_numeric_fields`; `marker_write_failure_then_ledger_loss`; `settlement_missingness`; `completed_receipt_rehydration`; `stopped_correction_period`; `stop_then_settle_double_accounting`; `conflicting_settlement_retry`; `no_budget_same_operation_race` |
| hydraulic-boundary-results.json | 3 | `forward_after_historical_query`; `loser_evidence_in_winning_checkpoint`; `new_winner_during_rollback_rehydration` |
| continuity-results.json | 9 | `late_stop_deadline_and_terminal_precedence`; `global_emergency_stop_execution`; `restart_payload_preservation`; `completion_missingness`; `area_missingness_identity`; `settled_retry_observation_conflicts`; `settled_then_stopped`; `correction_lineage`; `schema_and_writer_contracts` |
| hydraulic-continuity-results.json | 2 | `historical_read_overwrites_newer_publication`; `plot_alias_cross_scope_prior` |


The companion ZIP contains ten independent harnesses, ten observed result files, pinned source manifest and reproduction instructions. It excludes repository tests/audit claims, production source copies and credentials. Use only software drivers in an isolated pinned checkout. The JSON key names inherited from earlier probes may describe an old defect that now passes; consult the reconciliation table rather than interpreting a key name as a current finding.

Source integrity and targeted numerical/concurrency checks are not a whole-project scientific certification, field-controller acceptance or full suite recertification. No externally reachable HTTP exploit is asserted. Process-local locks do not prove multi-host/device fencing. Scope coupling was tested with intentionally reused local plot identifiers in declared separate scopes. Conservative command-target accounting is not a measured dose or demonstrated upper bound on a physical overrun.

Conclusion: proceed with the focused corrective implementation above. Preserve the verified improvements, keep all six gates open, and promote affected capabilities only after the remaining scoped acceptance evidence is obtained.

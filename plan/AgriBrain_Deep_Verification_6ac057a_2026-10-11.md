# AgriBrain production verification — commit 6ac057a

Review date: 2026-10-11 UTC. Reviewed commit: `6ac057ab6144a2c69b9b50e1184a9fb27d977d66`. Parent: `1fb78cc53f4327cf1e6dc641d6db368309f7c793`.

## 1. Decision

The pushed commit is present on GitHub and was the `main` branch head when rechecked during this review. All nine **original RV counterexamples** now exhibit the intended corrections. In particular, the foreign hydraulic publication reproduction now gives the same warm and cold soil-water profile, with top-layer VWC `0.2124`.

The broader claim that the runtime boundaries are closed is not supported. Independent production probes establish **seven remaining defect groups**, designated RC01–RC07 within this review. These identifiers are local finding identifiers; they do not replace the master plan's F/T packages or the monograph's scientific requirement identifiers. Two particularly consequential regressions are a ledger-dependent ordinary watchdog and stale terminal restart snapshots that can stop a different live operation.

Proceed with corrective implementation for these findings. Keep runtime full acceptance open. Independent foundation work and research can continue where their own prerequisites and eligibility conditions are satisfied. This commit review does not establish readiness of the complete AgriBrain system, Omega, or the world model.

## 2. Evidence, scope, and exclusions

This review used production source, independent simulations, and the supplied R3 scientific requirements. Repository tests and prior audit reports were not used as proof that the corrections work. The new test file was not used to design the observed outcomes. Production files were not modified and no field hardware was operated.

| Evidence | Verification performed |
|---|---|
| GitHub commit and branch | Full SHA retrieved; `main` rechecked at the reviewed SHA |
| Three changed production files | Exact Git blobs verified; parent/current production diff examined |
| Local dependency source | 430 production Python files matched their pinned Git blob hashes and parsed successfully with Python AST |
| Independent execution | 14 harness drivers completed; 127 named JSON result groups, comprising 125 behavioral/scientific groups and two import diagnostic groups |
| Parent regression comparison | Additional watchdog comparison against the exact parent source, with healthy/read-fault/write-fault cases |
| R3 target | Relevant requirements checked against the supplied scientific requirements export |
| Acceptance register | Six requested full-acceptance tickets remain unchecked in the pinned task register |

The 127 groups are observations, including demonstrated defects, controls, and import diagnostics. They are **not 127 passing acceptance tests**. The user's reported `538 passed` repository test result was not independently rerun or recertified here. Matching and parsing 430 files does not mean all 430 received a full semantic audit. This is a deep verification of the remediation and its reachable runtime/hydraulic boundaries, not a new exhaustive audit of all project features.

The simulation driver exposes separate cached status, queried status, command counts, and simulated running state. That separation is deliberate: it permits verification of recovery and stale-cache behavior without operating hardware. An observed missing STOP establishes a software cutoff failure under the fixture. Actual field operating duration also depends on controller protections, which this review does not verify. No externally reachable HTTP exploitation path is asserted for the conflicting snapshot or low-level writer examples.

### Pinned production identities

| File | Git blob SHA-1 |
|---|---|
| [irrigation_runtime/dispatcher.py](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py) | `4d753669876e7012c282d662b5ba2f0676aa57f9` |
| [irrigation_runtime/safety.py](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/safety.py) | `395bf4b24a4fa28a96470b5f757684b5fcc6af34` |
| [layer3_decision/runner.py](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/layer3_decision/runner.py) | `e4572e4e72332ebb5ef3f1e7946ea5095d027cd5` |

The production dispatcher class is `CommandDispatcher`. The commit timestamp is `2026-10-11T13:52:22Z`.

The supplied R3 scientific export has SHA-256 `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`. It is the supplied target reference; this report does not claim that an identically named R3 document was fetched from this Git commit, or that all 153 requirements were recertified.

## 3. Original RV01–RV09 verification

| Finding | Independent observation on 6ac057a | Qualification |
|---|---|---|
| RV01 — global cutoff traversal | With a first driver exception, corrupt ledger, or simulated ledger write failure, the second actuator receives a STOP; registry fallback runs and the method returns a result dictionary | With ledger faults, successful simulated cutoff can still be reported as `STOP_ERROR` and retained as `STOP_REQUESTED`, because subsequent accounting fails. This is conservative degradation. It does not invalidate the traversal correction |
| RV02 — foreign hydraulic publication | A separate OS process publishes a historical correction. Subsequent warm and cold runs both return `[0.2124, 0.2546, 0.2616, 0.2652, 0.2295]`; RAM and durable heads agree | This is actual process separation, not two instances standing in for a multi-process publication test |
| RV03 — recovery deadline | Original default duplicate/restart cases with expired or missing verified start timing now attempt STOP and finish `EMERGENCY_STOPPED`; persisted old start is recovered where available | Caller-supplied conflicting start timing and storage failures expose additional contracts, RC01/RC04 |
| RV04 — pending validation recovery | A pending validation snapshot is restored and measured completion settles `4.0 mm`, releases the reservation, and returns `COMPLETED`; terminal record reads no longer return `None` | Returning terminal records introduces an unhandled terminal-classification branch, RC02. Restored validation also needs fresh controller qualification, RC05 |
| RV05 — qualified observations | A store-backed idle restart retains `8.0 mm` unresolved exposure and creates no measured delivery receipt. A nonzero measured volume with omitted duration preserves `actual_duration_minutes = None` | Zero-volume missing duration and the no-store restart branch remain inconsistent, RC06 |
| RV06 — settlement scalar validation | `target_volume_mm=NaN`, boolean duration, infinite flow, and negative area raise `ValueError`; the existing ledger remains readable | Alternate writers can still publish invalid negative values, RC07 |
| RV07 — retry support identity | Changed target/support retries are rejected locally and by fresh callers; an atomic missing-area versus present-area conflict does not produce another START | Recovery and first settlement do not consistently bind the entire canonical payload, RC03 |
| RV08 — zero-depth journal | Zero-depth and positive-depth production admissions each have a durable reservation and exactly one `RESERVATION` journal entry | Zero depth does not mean that an operation has no physical duration or needs no ownership |
| RV09 — reopen period/support | Reopening preserves original date, season, support, and first-dispatch timestamp when omitted; cross-midnight failed fencing retains the original admission period | Payload immutability and actual-start authority remain separate contracts |

Evidence: `recovery-boundary-results.json` and `publication-generation-results.json` in the reproduction bundle. These results credit the exact repaired counterexamples without promoting them to universal feature acceptance.

### Hydraulic publication control

The foreign correction publishes outer checkpoint sequence `3` while its scientific payload sequence is `1`. The subsequent run uses the committed publication generation rather than history length: both warm and cold paths publish generation `4` and agree on the same head and profile. This supports the RV02 correction.

An additional interleaving probe pauses cold hydration while a newer January 4 publication commits. The historical attempt loses compare-and-swap and returns `ConcurrencyConflictError`; RAM soil state, durable soil state, head, and generation remain equal to the winner. The history cache is cleared in this fixture. No scientific profile divergence was established by that extra probe. Its JSON key, `hydration_mutates_newer_RAM_memory`, records the original hypothesis, not a confirmed finding. It is not counted as an eighth defect group.

## 4. Remaining findings

Priority P1 means resolve before accepting the reviewed runtime command/recovery path. P2 means a narrower service-contract defect requiring correction, without an asserted public input exploit.

| ID | Priority | Remaining contract failure | Relevant R3 requirements |
|---|---|---|---|
| RC01 | P1 | A start-time ledger operation prevents ordinary watchdog cutoff | AB-EXE-004, AB-ARC-006 |
| RC02 | P1 | Terminal receipts do not fence stale restart snapshots; an old event can stop another operation | AB-EXE-002/003, AB-ARC-008 |
| RC03 | P1 | Recovery and initial settlement can rebind immutable command scope/payload | AB-DAT-003/010/013, AB-ARC-007/008, AB-EXE-004 |
| RC04 | P1 | Caller timing supersedes durable deadline; acknowledged start is not immediately durable | AB-EXE-002/004, AB-ARC-008 |
| RC05 | P1 | Restored validation completes using cached controller status without querying the running controller | AB-EXE-002/005, AB-ARC-006 |
| RC06 | P2 | Zero volume fabricates duration; no-store idle recovery certifies target depth without measurements | AB-DAT-005/006/007/010, AB-EXE-005 |
| RC07 | P2 | Alternate ledger writers publish invalid candidate state and poison later reads | AB-ARC-007, AB-EXE-004 |

The mappings describe the requirement affected by each reproduction. They are not a claim that all subclauses of each requirement were audited.

### RC01 — ordinary watchdog depends on successful start-time storage

Source: [dispatcher.py, lines 708–711](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py#L708-L711).

`check_execution_status()` calls `SharedQuotaStore.set_actual_start()` before controller lookup and safety evaluation. The call is not shielded. A corrupt ledger read or a start-time write failure therefore aborts the poll before the monotonic duration watchdog executes.

The reproduction starts a ten-minute operation and advances the injected monotonic clock to `661 seconds`. Empty sensor readings are used in all cases.

| Case | Commit | Watchdog evaluated | STOP commands | Simulation remains running |
|---|---|---:|---:|---:|
| Healthy ledger | 6ac057a | Yes | 1 | No |
| Corrupt ledger read | 6ac057a | No | 0 | Yes |
| Start-time write raises `OSError` | 6ac057a | No | 0 | Yes |
| Corrupt ledger read | Parent 1fb78cc | Yes | 1 | No |
| Write raises `OSError` | Parent 1fb78cc | Yes | 1 | No |

The parent can still raise an accounting exception after issuing STOP; the significant comparison is that its physical simulation cutoff occurs. The current commit preserves active ownership during the failing poll, but does not attempt the overdue cutoff. This establishes a regression, rather than merely an old untested limitation.

Evidence: `contract-results.json → start_time_write_blocks_expired_watchdog`; `parent-watchdog-control.json`.

Repair criteria:

1. Perform required STOP/interlock traversal even if any start-time, phase, quota, or receipt write fails.
2. Isolate bookkeeping failure from physical deadline enforcement while retaining unresolved ownership/exposure.
3. Keep corrupt-ledger admission blocked; fixing STOP availability must not permit new unaccounted commands.
4. Run the same expired-operation cases through ordinary polling, global cutoff, cancellation, and restart. Verify command attempts as well as returned statuses.
5. Persist acknowledged timing at its state transition, rather than adding an unguarded durable write to every safety poll.

### RC02 — authoritative terminal state is ignored during restart

Sources: [safety.py, lines 1263–1275](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/safety.py#L1263-L1275), [dispatcher.py, lines 1147–1180](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py#L1147-L1180).

`get_active_record()` now returns terminal settled and stopped receipts. `reconcile_on_restart()` only applies selected active phases from that record. `COMPLETED` and `CANCELLED` are ignored, leaving the incoming stale snapshot's `EXECUTING` phase intact.

Two terminal controls establish the error: a stale snapshot of a settled event and a stale snapshot of a stopped event both become `VALIDATING`, with one restored owner, no reservation, and an existing terminal receipt.

A more consequential reproduction completes event `E`, starts distinct event `NEW` on the same simulated device, then recovers an expired stale snapshot of `E`. Recovery issues one STOP against the controller currently running `NEW`. The simulation stops, but `NEW` remains `EXECUTING` in local and durable records with `3 mm` reserved. The old snapshot becomes `EMERGENCY_STOPPED` while its canonical record remains `COMPLETED`.

The observed failure is incorrect cutoff and inconsistent state, not a duplicate physical START. Inferring which operation is running from bare controller status permits the old event's deadline to affect the new event.

Evidence: `terminal_records_reopened_for_validation`; `terminal_snapshot_stops_different_live_operation`.

Repair criteria:

1. Classify canonical terminal receipts before any controller query, deadline computation, ownership restoration, or STOP dispatch for that snapshot.
2. Hydrate the canonical terminal outcome and return without reopening the operation.
3. Distinguish an active-reservation read from an operation/receipt read in API semantics.
4. Bind live controller reconciliation to an operation receipt or qualified identity. Bare `EXECUTING` cannot establish that a controller is executing the recovered event.
5. Verify stale settled/stopped snapshots while another operation is running. The current operation must receive no command or phase mutation from the stale operation.

### RC03 — restart and initial settlement can change canonical scope

Sources: [dispatcher.py, lines 1147–1170](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py#L1147-L1170), [safety.py, reserve](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/safety.py#L739-L811), [safety.py, settle](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/safety.py#L854-L1016).

Restart hydrates only part of an operation's payload and can pass conflicting snapshot fields into `track_event_start()`/`reserve()`. The resulting reservation can overwrite canonical plot and target without a corresponding correction journal entry.

Reproduction:

1. Admit `E` for original plot `plot`, target `8 mm`, with a `10 mm` budget.
2. Recover an otherwise matching snapshot whose plot is `different_plot` and target is `12 mm`.
3. The reservation moves from `plot: 8` to `different_plot: 12`; the driver's local active-command metadata also changes, although only the original `8 mm` START was physically sent.
4. The original plot now reports zero exposure. A second `8 mm` operation for that original plot is admitted under the original `10 mm` budget. Both original-plot driver simulations are running.

The demonstrated commanded exposure is `8 + 8 = 16 mm > 10 mm`; this is not a measurement of actual delivered water. The reservation journal still records the first operation against the original plot at `8 mm`.

A separate low-level settlement control reserves `8 mm` against the original plot, then accepts first settlement against `different_plot` for `4 mm`. The original plot exposure becomes zero and the other plot is debited `4 mm`; the next ledger read accepts it. Retry checks do not prevent this first-transition scope change.

Evidence: `restart_rebinds_active_payload`; `first_settlement_rebinds_reserved_plot`.

Repair criteria:

1. Define one canonical operation envelope: event ID, plot, device, zone, commanded target, duration, flow, effective area, and admitted accounting period. Bind tenant/namespace where those dimensions are part of the application's operation identity.
2. Validate compatibility under the same ledger lock for admission, reserve, reopen, restart, stop recording, and first settlement. Do not limit identity checks to retries.
3. Restore authoritative fields from the canonical envelope; reject conflicting snapshots rather than moving exposure.
4. Separate delivered observations from commanded identity. New measured depth may change accounting without rewriting the commanded target or operation scope.
5. Require explicit correction lineage for legitimate supported revisions. Check journal/current-record agreement as well as numerical rollups.
6. Reproduce the two-device quota case: the second `8 mm` operation must remain blocked against a `10 mm` budget.

### RC04 — caller timing overrides the durable watchdog origin

Sources: [dispatcher.py, active retry hydration](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py#L275-L295), [restart hydration](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py#L1163-L1170), [ACK transition](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py#L550-L565).

Both fresh active retry and restart only copy the durable start when the input event lacks `actual_start`. A non-empty caller value therefore supersedes a qualified old start.

The durable operation has a start eleven minutes ago and a ten-minute duration. With an empty retry timestamp, recovery attempts STOP and returns `EMERGENCY_STOPPED`. With the same identity/payload but caller timestamp set to now, recovery returns `EXECUTING`, issues zero STOP commands, and the simulation remains running. The ledger still contains the old start. Later polling can also call `set_actual_start()` with the caller-derived value; the setter has no immutable-start conflict check.

There is a distinct durability gap at initial ACK: local `actual_start` is set, but the status write does not pass it to `update_status()`, although that method accepts it. Immediately after successful submission, the durable record has `EXECUTING` and `first_dispatched_at`, but no `actual_start`. Recovery's conservative expiration is safe degradation in this gap; it can cause an unnecessary early stop. That gap alone is not evidence of an overrun.

Evidence: `caller_timing_overrides_durable_deadline`; `ack_start_persistence_before_first_poll`.

Repair criteria:

1. Make verified durable timing authoritative over caller snapshots. Reject or explicitly qualify conflicts.
2. Preserve `first_dispatched_at` and acknowledged `actual_start` as different facts.
3. Publish ACK phase and acknowledged start together; reconcile publication failure without resetting the deadline or losing ownership.
4. Once established, start time must not move forward on retry/poll. Legitimate corrections require explicit provenance and conservative deadline treatment.
5. Verify omitted, malformed, future, older, and conflicting timestamps across fresh instances and process restart.

### RC05 — restored validation uses cached controller status

Sources: [dispatcher.py, lines 1172–1176](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py#L1172-L1176), [completion guard, lines 906–915](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py#L906-L915).

A restored `VALIDATING` event is registered and immediately skipped past controller reconciliation. `complete_event()` then checks the actuator's cached `_status`, not a fresh query.

The controlled fixture restores a `VALIDATING` snapshot with a freshly constructed driver whose cache is `ONLINE`, while its separate physical simulation is running. With no explicit pre-query, recovery makes zero status queries; completion returns `COMPLETED`, releases the `8 mm` reservation, settles `4 mm`, and removes the owner while the simulation remains running. In the matched control, one pre-query changes the cached status to `EXECUTING`; completion then stays `VALIDATING`, retains `8 mm`, and settles nothing.

This establishes dependence on stale cache. It does not establish how any specific deployed controller behaves after restart.

Evidence: `validating_restore_does_not_query_running_controller`.

Repair criteria:

1. Query/reconcile the operation before certifying terminal completion after restart.
2. Treat query failure, unknown identity, or confirmed running status as unresolved. Preserve tracking and conservative exposure.
3. Record valid measurements separately if needed; a volume observation does not itself establish that the physical operation has ended.
4. Verify identical outcomes for cached `ONLINE` and cached `EXECUTING` when the queried controller truth is the same.
5. Exercise query timeouts and operation mismatch, not only healthy idle responses.

### RC06 — two remaining missingness/provenance exceptions

Sources: [dispatcher.py, lines 933–942](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py#L933-L942), [idle no-record branch, lines 1334–1343](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/dispatcher.py#L1334-L1343).

First, `complete_event(E, actual_volume_l=0)` with duration omitted creates `actual_duration_minutes=0.0`. The explicit zero volume is correct; the fabricated duration is not. A zero-volume observation does not imply zero elapsed time. The ordinary nonzero-volume omitted-duration case is now corrected.

Second, an idle restarted event without a durable active record still takes a fallback that marks it `COMPLETED` and settles its commanded target. The reproduction creates an `8 mm` completed receipt while actual volume and actual duration are `None`; support and device/zone provenance are also absent in that receipt. The store-backed version correctly stays unresolved, so the fallback is a remaining branch rather than failure of that original correction.

For qualified nonzero delivery:

\[
I_{\mathrm{mm}} = \frac{V_{\mathrm{L}}}{10{,}000 A_{\mathrm{ha}}}.
\]

`40,000 L` on `1 ha` establishes `4 mm`. An unobserved volume cannot establish that the commanded `8 mm` was delivered. Conservative exposure can remain `8 mm`, but it needs unresolved/estimated accounting semantics rather than measured-completion authority.

Evidence: `zero_volume_missing_duration`; `idle_restart_without_store_record`.

Repair criteria:

1. Preserve omitted actual duration as `None`, including when volume is explicitly zero.
2. Preserve explicit measured zero volume as zero; do not regress it to a target fallback.
3. Route no-record/legacy recovery into qualified reconciliation with explicit uncertainty and provenance.
4. Distinguish reserved/estimated exposure, commanded target, measured volume, and derived delivered depth in receipts.
5. Confirm that downstream hydraulic/event consumers cannot interpret unresolved conservative exposure as certified applied irrigation.

### RC07 — writer contracts do not protect the candidate ledger

Sources: [safety.py, `_write_state`](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/safety.py#L368-L384), [atomic admission](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/safety.py#L406-L736), [reserve](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/safety.py#L739-L811), [reopen](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/services/agribrain/irrigation_runtime/safety.py#L1150-L1225).

`allow_nan=False` correctly prevents non-finite JSON constants. It does not reject finite negative numbers, inconsistent identities, or invalid accounting candidates. `_write_state()` does not validate the assembled candidate before replacing the healthy ledger.

Starting with a valid `SAFE` reservation, each of `reserve()`, `reopen_active()`, and `atomic_check_and_reserve()` accepts a new reservation with `duration_minutes=-1`. Each reports acceptance and changes durable bytes. The next read raises `CorruptedQuotaStoreError` because the published scalar violates the reader's schema.

These are direct production service-writer calls. The ordinary dispatcher input validation rejects such raw negative requests, so this finding must not be described as a demonstrated public registration/HTTP vulnerability. Its consequence is a poisoned shared ledger if an internal caller violates the contract; RC01 amplifies the effect by coupling storage failure to cutoff.

Evidence: `alternate_writers_publish_invalid_candidate`.

Repair criteria:

1. Apply strict scalar validation consistently to all public writers, without coercing invalid or missing values into physical zero.
2. Validate complete candidate schema, phase/identity compatibility, and receipt/aggregate conservation before publication.
3. Reject invalid candidates without changing durable ledger bytes, marker state, or journal history.
4. Keep strict JSON encoding as an additional defense.
5. Exercise all alternate writers with invalid scalars and incompatible identities; a healthy prior ledger must remain readable after each rejection.

## 5. Implementation sequence and acceptance criteria

The following order addresses actual demonstrated dependencies. Independent cutoff work can begin immediately; it need not wait for every broader data-model repair.

| Step | Scope | Required result |
|---|---|---|
| 1 | RC01 | Storage failure cannot suppress any required physical cutoff attempt; corrupt-store admission remains blocked |
| 2 | RC02 and RC04 | Canonical phase and timing control restart/retry before controller commands; stale terminal records cannot affect newer operations |
| 3 | RC03 and RC07 | Every transition uses the immutable operation envelope and validates its complete candidate before durable publication |
| 4 | RC05 and RC06 | Qualified controller termination and measurement provenance govern completion; missing facts remain missing |
| 5 | Integrated acceptance | Separate-process owners, restart boundaries, delivery accounting, controller operation receipts, and fault injection satisfy the F08/F09/F16–F19 package criteria |

Use explicit expected invariants, rather than checks that merely confirm a function returns without throwing:

\[
\text{commanded identity}(e) = \text{admitted identity}(e),
\qquad
\text{terminal}(e) \Rightarrow \text{no recovery command for stale snapshot}(e).
\]

For plot/period exposure, reservations and unresolved conservative receipts must continue to count until a compatible measured outcome reconciles them. Moving a receipt to another plot must not be a way to free the original plot's allowance. Settling a stopped `8 mm` exposure to measured `3 mm` should result in total `3 mm` for that event, preserving correction lineage rather than debiting `11 mm`.

For timing, use a verified origin and a conservative elapsed bound. Recovery must not grant a fresh allowance simply because a caller supplies a later timestamp or a storage step fails. Required safety commands must remain possible when observations or the ledger are unavailable.

Before declaring closure, rerun the exact counterexamples with assertions reversed to the required behavior, add paired healthy/fault controls, and run integrated multi-process acceptance. Run the repository regression suite as an additional check, not as a substitute for these contracts. Controller-specific hardware acceptance remains a separate task; this review has performed controlled software simulation only.

### Acceptance register

The pinned [task register](https://github.com/webClone/AgriWise/blob/6ac057ab6144a2c69b9b50e1184a9fb27d977d66/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md) has Git blob `8a564647af7e588802537817159117b349ff606b`. The following entries are still explicitly open:

| Ticket | Pinned line | Status |
|---|---:|---|
| ST03-F08-FA | 406 | `[ ]` |
| ST03-F09-FA | 443 | `[ ]` |
| ST06-F16-FA | 796 | `[ ]` |
| ST06-F17-FA | 833 | `[ ]` |
| ST06-F18-FA | 870 | `[ ]` |
| ST06-F19-FA | 907 | `[ ]` |

The extra hydraulic probes did not establish a new hydraulic profile blocker on this commit. That does not, by itself, close all F08/F09 acceptance criteria. Runtime gates remain blocked by the demonstrated command/recovery defects, and the user's explicit requirement to keep these tickets open is preserved. Acceptance includes integrated software criteria; it should not be summarized as merely waiting for future field hardware.

## 6. Reproduction bundle and interpretation

The accompanying ZIP contains independent harness source, their recorded JSON outcomes and logs, the pinned production blob manifest, sanitized commit metadata, the three-file production diff, a runner, and an evidence verifier. It excludes repository test suites, prior audit documents, production runtime copies, scratch quota ledgers, checkpoints, bytecode, and credentials.

Run the supplied `run_probes.py --repo /absolute/path/to/pinned/checkout` against a clean checkout of the exact reviewed commit. It verifies all 430 expected source blobs before loading production code. `verify_observations.py` checks the supplied evidence without rerunning the simulations. Its successful assertions confirm that the recorded corrections and counterexamples match this report; they are not assertions that the faulty production behavior is acceptable.

The optional parent watchdog control must use the exact parent checkout on `PYTHONPATH`. It is not part of the current-commit driver count. The runtime used Python 3.12, NumPy 2.3.5, SciPy 1.17.0, Pydantic 2.13.5, and scikit-learn 1.8.0. Import diagnostics in the bundle concern the exercised modules only and do not certify full application startup.

The decision supported by this evidence is to continue repairs now, credit the specific RV01–RV09 corrections, and defer full command-runtime acceptance until RC01–RC07 and the integrated gates are satisfied.

# AgriBrain production verification — eade402

Reviewed commit: [`eade4020a1368bc23a41e4da150d69a64b341b98`](https://github.com/webClone/AgriWise/commit/eade4020a1368bc23a41e4da150d69a64b341b98). Parent: `7e66d0c5b3a978339480d9f50856d3e433f01978`. Review date: 12 October 2026. Commit timestamp: 11 October 2026, 20:34:37 UTC / 21:34:37 Algeria time.

The original RP01–RP04 reproductions now show the claimed corrections. Five expanded production-contract groups remain reproducible. The strongest is premature stopped publication during a pending START: after the simulated sender process is terminated, fresh recovery skips a controller that is running. Two accounting examples additionally show understatement of measured exposure and publication of an unreadable ledger.

Proceed with corrective implementation. Keep physical-operation acceptance open until the remaining lifecycle and ledger gates below pass. Independent agronomic, interface, numerical, and exploratory work can proceed where its own prerequisites permit it; do not certify uncertain or understated delivery records as operational evidence.

## 1. Review scope and evidence qualifications

GitHub `main` was pinned at the reviewed SHA. Two production files changed: `services/agribrain/irrigation_runtime/dispatcher.py` and `safety.py`. Repository test changes and the repository verification document were excluded as correctness evidence. No production files were edited, no repository pytest suite was invoked, and no field hardware was operated.

The runtime used 430 production dependency files. All exact Git blob identities were verified and every file parsed successfully with Python's AST parser. This establishes source integrity and syntax for that dependency set. It does not establish semantic correctness of 430 modules or recertify the whole AgriWise application.

Eighteen independent drivers produced 158 named JSON groups: 156 behavioral/scientific groups and two import diagnostic groups. Final qualified executions completed successfully and the result files contain no harness-error group. These groups include demonstrated defects; they are not 158 passing acceptance tests.

The original RP paused-send reproduction uses two actual spawned OS processes, a common quota directory, and simulated controller state. Its preserved-reservation result now passes the intended contract. The additional crash reproduction runs a separate sender process, deliberately terminates only that simulation worker after queued START application but before ACK processing, and runs fresh recovery from another process. The sender's exit code −15 is an intentional injected failure, not an unexplained harness crash.

One repeat of the crash harness exposed a probe synchronization issue when a worker was terminated around an IPC acknowledgement-event lock. The ACK hold was changed to a local asynchronous future, removing that unnecessary IPC lock from crash cleanup. Only the independent probe was changed; production code was untouched. The report relies on completed qualified runs, not on the interrupted repeat.

The other probes exercise controlled scheduler interleavings, refreshed driver caches, and direct internal quota writers. Controller running flags, STOP outcomes, sensor faults, and measurements are simulated. Direct writer examples establish service contracts, without asserting an externally reachable HTTP exploit. Field-controller protections and actual physical duration are unverified; the review does not claim indefinite field operation.

The user's reported 566 passing repository tests remain a reported result. This review did not rerun them or use them to override counterexamples.

The scientific target is the supplied R3 export `R3_current_scientific_sections.txt`, SHA-256 `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`. Exact relevant register excerpts accompany the evidence. This is a targeted comparison against that supplied monograph, not a new certification of all 153 requirements or an assertion about an unseen later revision.

## 2. Original RP01–RP04 verification

| Original finding | Independently observed corrective behavior | Scope qualification |
|---|---|---|
| RP01 — separate-worker pending completion | Recovery sees durable DISPATCHING, retains STOP_REQUESTED and 8 mm, and blocks competing 8 mm admission against 10 mm. Failed and exceptional ACK-fence STOP retain an active event, watchdog, and reservation. Actual two-process reproduction gives the same result. | STOP retry's idle branch can still terminalize a pending send: ER01. Failed late fencing also rebases watchdog age. |
| RP01 — local stop intent lost | Recovery now persists STOP_REQUESTED. Late ACK sees it and attempts cutoff rather than returning EXECUTING. | Successful cutoff leaves local CANCELLED, durable VALIDATING, and 8 mm unresolved reservation in the exercised case. That is not full phase-publication certification. |
| RP02 — failed STOP creates stopped receipt | Failed-result cutoff of NEW through an OLD poll retains NEW's durable STOP_REQUESTED, active reservation, and restart monitoring; no stopped receipt is created. | A STOP exception bypasses that failure branch and latches the fault without persistent retry intent: ER02. |
| RP03 — empty source ID treated as another owner | Before restart, empty-ID cancellation retains STOP_REQUESTED, one owner/watchdog, and 8 mm, without sending STOP. Qualified same/different controls retain their expected behavior. | No-command stale caches and conflicting active/pending identities remain ER03. |
| RP04 — raw envelope retry rejects canonicalization | All seven area/duration/flow/device/zone/date/season original requests now accept identical retries. Canonical fields and measurements stay unchanged; no additional debit or byte change occurs. | The new receipt-reopening and overlapping-state paths expose accounting failures ER04/ER05. |

Evidence: `post_pb_probes.py`, `post-pb-results.json`. The cancellation observation is captured explicitly before restart to distinguish retained unknown intent from a later confirmed STOP during recovery.

The sampled earlier PB/BV/RC corrected scenarios are retained in the bundle. An earlier unrelated-pending cancellation control now regresses: where it previously left NEW running with zero STOPs, current code preempts NEW. That regression is documented under ER03 rather than describing every earlier control as unchanged.

## 3. Remaining groups and scientific traceability

ER01–ER05 are review-local finding IDs, not monograph IDs or new F/T package identities. P1 denotes a demonstrated physical-command recovery or conservative-budget failure requiring repair before affected physical-operation acceptance. P2 denotes a demonstrated ledger publication failure requiring repair before affected accounting results are certified.

| ID | Priority | Remaining failure | R3 requirements |
|---|---|---|---|
| ER01 | P1 | STOP retry certifies idle while START is pending; sender termination leaves a running controller behind a terminal receipt. | AB-ARC-007/008; AB-DAT-010/012; AB-EXE-002/003/004 |
| ER02 | P1 | Device STOP exception escapes before stop intent is published; the fault is already latched and the next poll does not retry. | AB-ARC-006; AB-DAT-010; AB-EXE-002/004 |
| ER03 | P1 | Cancellation trusts an unqueried cache as idle, and prefers cached OLD identity over qualified pending NEW. | AB-ARC-006/008; AB-DAT-010; AB-EXE-002/003/004 |
| ER04 | P1 | Reopening a settled operation replaces a measured 12 mm lower bound with commanded exposure 8 mm. | AB-DAT-003/007/010; AB-ARC-007; AB-EXE-004/005 |
| ER05 | P2 | Active-plus-settled re-settlement overwrites the receipt but adds the new debit to the old aggregate. | AB-DAT-003/011/012; AB-ARC-007/008; AB-EXE-003 |

### ER01 — Pending-send protection is bypassed by STOP retry

Production locations: [STOP retry idle branch, dispatcher.py L819–843](https://github.com/webClone/AgriWise/blob/eade4020a1368bc23a41e4da150d69a64b341b98/services/agribrain/irrigation_runtime/dispatcher.py#L819-L843), [pending recovery L1636–1662](https://github.com/webClone/AgriWise/blob/eade4020a1368bc23a41e4da150d69a64b341b98/services/agribrain/irrigation_runtime/dispatcher.py#L1636-L1662), and [late failed-fence tracking L630–641](https://github.com/webClone/AgriWise/blob/eade4020a1368bc23a41e4da150d69a64b341b98/services/agribrain/irrigation_runtime/dispatcher.py#L630-L641).

The new completion guard correctly protects durable DISPATCHING/STOP_REQUESTED. The existing STOP retry branch does not apply equivalent pending-send qualification. It queries current status and, if ONLINE, immediately declares the event stopped, publishes a stopped receipt, and removes tracking.

In a shared-driver fixture, recovery correctly sets durable/local STOP_REQUESTED while `_pending_command` names E. The next `check_execution_status` call sees the still-idle controller and changes both phases to CANCELLED. The pending command still names E; zero STOPs were sent, and recovery owner/watchdog counts become zero. Reservation 8 mm is converted to conservative stopped exposure 8 mm. Numeric exposure is conserved in this case, but physical resolution is falsely certified.

The subsequent ACK control attempts a late STOP and stops the simulation if the sender remains alive. The process-crash reproduction removes that assumption:

1. A separate sender process admits and queues START, paused before controller application.
2. Recovery sees DISPATCHING and correctly publishes STOP_REQUESTED.
3. Its STOP retry sees idle and publishes CANCELLED/stopped receipt without sending STOP.
4. The queued START is released and the simulated controller applies it, while its ACK remains held.
5. The simulated sender process is deliberately terminated before it can process ACK or run its late fence.
6. Fresh recovery sees the stopped receipt and returns CANCELLED without consulting/stopping the running controller.

| Actual process-crash observation | Result |
|---|---|
| Terminal phase before queued START applies | CANCELLED |
| STOP attempts before application | 0 |
| Sender exit | −15, deliberate termination |
| Simulated controller after sender termination | Running |
| Fresh recovered phase | CANCELLED |
| Fresh STOP / owner / watchdog counts | 0 / 0 / 0 |
| Quota projection | Reserved 0 mm; conservative stopped debit 8 mm |

This is loss of physical-operation recovery, not an 8 mm quota erasure. Actual controller protections may independently stop delivery; they are not verified here.

**Watchdog-age subcase.** In the new failed late-fence branch, `track_event_start` is called without elapsed time. With an original monotonic origin 0 s and current clock 661 s for a 600 s operation, the origin becomes 661 s. The expiry helper emits DURATION_EXCEEDED before that call and no violation afterward. A subsequent STOP_REQUESTED poll still attempts STOP immediately. Thus this probe establishes lost deadline age, not an additional ten minutes of physical operation.

**Repair.** Apply one shared unresolved-command predicate to completion, STOP polling, restart, and successful fencing cleanup. Current idle cannot certify STOP while an admitted transport may still apply START. Require an operation-specific not-applied/completed receipt or a qualified generation fence of the queued command. Terminal receipt precedence must not skip an unresolved physical generation after sender failure.

Preserve original monotonic/deadline authority during every re-registration. Do not reset watchdog age when reopening exposure after a failed fence. Where a prior terminal record is corrected, retain its history and explicitly bind the unresolved activity to the corrected authority.

**Acceptance.** The exact queued-send/recovery-poll/sender-termination scenario must retain recoverable STOP_REQUESTED or fence the queued command before terminal publication. Fresh recovery must not skip a running unresolved operation. Test delayed ACK, sender death, successful/failed/exceptional STOP, and controller receipts. Numeric quota conservation and physical resolution must both hold. Deadline origin must remain unchanged except for qualified reconstruction of elapsed time.

Evidence: `pending_STOP_poll_certifies_idle_before_send_resolution`, `actual_process_queued_START_survives_false_terminal_and_sender_crash`, `failed_late_fence_rebases_original_watchdog` in `post-rp-results.json`.

### ER02 — STOP exception bypasses failure handling and loses retry intent

Production location: [dispatcher.py L915–917](https://github.com/webClone/AgriWise/blob/eade4020a1368bc23a41e4da150d69a64b341b98/services/agribrain/irrigation_runtime/dispatcher.py#L915-L917), followed by success/failure processing through L989. The safety monitor latches a detected violation before returning it to the dispatcher.

OLD is stale and NEW is running. A configured pressure fault is detected; the fixture uses zero debounce to isolate routing. Successful STOP correctly stops the simulation. A returned unsuccessful result correctly puts the live owner in STOP_REQUESTED without a stopped receipt.

When the same STOP call raises OSError, the unguarded await escapes before either branch. OLD and NEW remain locally EXECUTING, and NEW's durable phase remains EXECUTING. The safety monitor already has one latched PRESSURE_HIGH violation. A subsequent poll returns without another STOP attempt while the simulation remains running, because sustained latched faults do not re-emit the same violation.

Active tracking remains present; it is not dropped. The failure is absence of persistent cutoff intent and immediate failed-cutoff reconciliation. This probe does not claim that later duration expiry or another independent monitor can never stop the controller.

**Repair.** Normalize raised transport errors, timeouts, missing responses, and unsuccessful STOP results into one unresolved cutoff outcome. Publish/retain stop intent for the actual affected operation and original deadline before asynchronous cutoff can fail. Separate fault latching from cutoff-resolution status: a latched hazard with unconfirmed STOP remains actionable until qualified resolution. Ledger failure must not suppress physical cutoff or the retained local retry obligation.

**Acceptance.** Success, failed result, exception, timeout, and unavailable response must leave compatible local/durable outcome states. Failed/unknown STOP cannot leave the affected owner in ordinary EXECUTING without a cutoff obligation. Repeated polls and restart must resume that obligation even when the fault is already latched. Preserve stale-event duration fencing so an old timer cannot stop a different healthy operation.

Evidence: `device_STOP_exception_latches_without_stop_intent_or_retry`.

### ER03 — Cancellation still has unqualified idle and conflicting-identity paths

Production location: [dispatcher.py L1209–1255](https://github.com/webClone/AgriWise/blob/eade4020a1368bc23a41e4da150d69a64b341b98/services/agribrain/irrigation_runtime/dispatcher.py#L1209-L1255).

**Unqueried cache.** A refreshed adapter has no local active/pending command and cached status ONLINE, OFFLINE, or UNKNOWN. The simulated controller is running, and a current query would report that. `cancel_event` makes zero queries. Its `is_running` check uses cached adapter state; with no command object, it reaches the branch labelled confirmed idle and sets `stop_success = True`.

For all three caches: zero STOPs, physical simulation running, local/durable CANCELLED, zero owner/watchdog count, reservation 0, and conservative stopped exposure 8 mm. The charge is preserved, but the controller is not confirmed stopped. OFFLINE/UNKNOWN are especially clear examples of missing confirmation.

**Conflicting identities.** OLD has finished on the controller, leaving a cached active-command reference to OLD while status is ONLINE. NEW is now a qualified pending command on the same device. Cancelling OLD satisfies the first same-owner predicate because of cached OLD; it never reaches the different pending-owner branch.

The STOP preempts NEW through the production actuator's stop generation. One STOP occurs on cancellation and another after NEW's late send completion. NEW is no longer running; its returned/durable phase remains DISPATCHING in the fixture. The previously retained unrelated-pending cancellation control also regresses from zero STOPs/NEW executing to preemption of NEW.

The three-way empty-ID correction itself works in its original fixture. The remaining problem is qualification of current status and the complete active/pending identity set, rather than selection using one matching cached field.

**Repair.** Obtain positive current idle confirmation before successful idle cancellation. Failed query, absent registry, OFFLINE, UNKNOWN, or ambiguous running state retains unresolved intent. Reconcile active and pending identities together with controller generation and receipt evidence. A cached match cannot authorize STOP against a different qualified pending operation. Keep event cancellation distinct from device/global safety cutoff.

**Acceptance.** All three refreshed-cache cases must retain unresolved ownership unless a current operation-specific result confirms resolution. Qualified same-owner cancellation still stops that operation, qualified different-owner cancellation still preserves it, and conflicting OLD/NEW identities do not cancel NEW. Test adapter refresh, stale cache, query failure, mixed active/pending references, and sender/recovery concurrency.

Evidence: `cancel_treats_unqueried_cache_as_confirmed_idle`, `cancel_old_cached_owner_preempts_different_pending_NEW`; the earlier control is `unrelated_pending_recovery_identity` in `post-pb-results.json`.

### ER04 — Reopening reduces exposure below known measured delivery

Production location: [safety.py L1293–1344](https://github.com/webClone/AgriWise/blob/eade4020a1368bc23a41e4da150d69a64b341b98/services/agribrain/irrigation_runtime/safety.py#L1293-L1344). The new path consumes settled receipts as well as stopped receipts, subtracts their delivery aggregates, and reserves the original commanded target.

The direct service fixture uses consistent small-area units: 0.001 ha = 10 m², a target of 8 mm, and nominal 8 L/min for 10 minutes = 80 L. The accepted outcome is 120 L over that support, or measured 12 mm:

\[
I_{mm}=\frac{120}{10{,}000\times0.001}=12.
\]

Reopen the same operation with canonical target 8 mm. The writer removes the current settled receipt, subtracts all 12 mm from aggregates, and creates an 8 mm reservation. Effective quota exposure becomes 8 mm, less than the already accepted measured 12 mm. The historical receipt remains in the REOPEN_ACTIVE journal's supersession payload; this is not total destruction of historical evidence. The current budget projection is understated.

With presented daily/season remaining budget 20 mm and no reflected consumed amount, another 10 mm request is admitted. The ledger reserves 18 mm and shows settled total zero, although accepted prior delivery 12 mm plus the new commanded 10 mm is already 22 mm. The second request's command parameters correspond to 100 L over the same support. This is a direct writer/admission contract example, not a claim that the second request was physically executed.

Zero-delivery and partial 4 mm controls reopen into 8 mm exposure and remain readable. They isolate the failure when known delivery exceeds the original target. Reopening an incorrectly published zero may need different treatment from reopening a valid measured outcome.

**Repair.** Preserve measured delivery as a lower bound while tracking additional unresolved exposure. Reopening changes operation authority; it does not itself invalidate a qualified observation. At minimum, effective exposure cannot fall below known delivered depth. Distinguish superseding an erroneous observation from reopening execution uncertainty, with explicit correction reason/provenance. Avoid double counting known delivery and remaining command exposure, but do not replace larger observed delivery with a smaller target.

**Acceptance.** For zero, partial, exact-target, and over-delivery receipts, reopening preserves an effective bound at least as large as qualified measured delivery. A 12 mm accepted delivery must prevent the 10 mm admission under a 20 mm budget. Preserve canonical plot/support/period, immutable journal lineage, idempotent reopen, and settled-to-stopped protections.

Evidence: `reopen_discards_confirmed_delivery_lower_bound`.

### ER05 — Re-settlement publishes a receipt/aggregate contradiction

Production locations: [safety.py L967–970](https://github.com/webClone/AgriWise/blob/eade4020a1368bc23a41e4da150d69a64b341b98/services/agribrain/irrigation_runtime/safety.py#L967-L970) and [receipt/debit construction L1074–1110](https://github.com/webClone/AgriWise/blob/eade4020a1368bc23a41e4da150d69a64b341b98/services/agribrain/irrigation_runtime/safety.py#L1074-L1110).

The new retry condition handles an existing settled receipt only when there is no active reservation. Another public writer, `reserve`, permits an active reservation to coexist with that settled receipt. That state passes the current reader validation.

An accepted internal sequence demonstrates the mismatch:

1. Reserve E for 8 mm; settle a measured 4 mm outcome.
2. Call `reserve(E, ...)` again; active E and settled E now coexist, and the store is readable.
3. Call settlement for 3 mm under E. The new active-precedence condition bypasses existing-receipt retry validation.
4. The receipt is overwritten with 3 mm, while the old 4 mm aggregate is retained and another 3 mm is added.
5. The write returns successfully; the next read raises CorruptedQuotaStoreError because aggregate 7 mm contradicts receipt sum 3 mm.

The normal dispatcher terminal-admission guard is not shown to redose a completed event here. The counterexample is at supported internal writer boundaries. Reader fail-closed detection works, but the writer has published the corruption it subsequently detects. Correction lineage for the overwritten settled receipt is also absent from this new settlement path.

**Repair.** Enforce compatible reservation/receipt exclusivity or explicit generation/correction semantics atomically across all writers. Reject or join a terminal event in `reserve` unless entering an authorized, auditable reopen transition. If settlement legitimately supersedes a prior settled receipt, compute net aggregate correction against it and record lineage. Validate receipt-to-aggregate conservation before replacing the durable file.

**Acceptance.** Every accepted reserve/reopen/settle sequence remains readable. Conflicting re-settlement either fails before publication without byte change or produces a correctly conserved audited correction. No accepted transaction leaves aggregate 7 with only receipt 3. Retain identical-retry no-debit/no-byte-change behavior and active-owner recovery.

Evidence: `active_plus_settled_resettlement_publishes_corrupt_aggregate`.

## 4. Implementation sequence and readiness

The remaining pattern is inconsistent lifecycle qualification across entry points: completion now consults durable pending state, while STOP polling and cancellation still use weaker evidence. Receipt reopening now supports settled records, while budgeting and settlement do not yet enforce that expanded transition consistently.

| Order | Concrete work | Acceptance gate |
|---|---|---|
| 1 | Centralize physical-resolution qualification for completion, STOP retry, cancellation, restart, and ACK fencing. | No terminal publication while a queued generation can still execute; fresh recovery survives sender death. |
| 2 | Repair ER02/ER03 cutoff outcomes and full identity/status qualification. | Exceptions retain actionable cutoff intent; stale/unknown caches cannot manufacture idle; OLD cannot cancel pending NEW. |
| 3 | Preserve original deadline age across all tracking/reopen paths. | Existing 661 s age is not reset to zero; STOP retry remains immediate. |
| 4 | Repair ER04 measured lower bounds and ER05 atomic receipt/reservation projection. | Known water is conserved, every accepted ledger remains readable, and corrections preserve lineage. |
| 5 | Run integrated process/crash/lost-ACK/STOP-error/cache-refresh/receipt-correction matrices, then designated controller acceptance. | Compatible local, durable, controller, measurement, and quota authority at every transition. |

Two complementary invariants should drive implementation:

\[
\text{terminal physical outcome}\Rightarrow\text{qualified resolution of the same operation generation},
\]

\[
\text{effective budget exposure}\geq\text{qualified delivered depth}.
\]

Presence of a journal, retention of a numeric charge, and current controller idle each address different evidence. None alone establishes all lifecycle contracts. Likewise, a reader rejecting corruption does not establish that preceding writers are correct.

For R3's agronomic/data-science target, understated irrigation changes water forcing, stress attribution, intervention response, economic costs, and training/rollout labels. Keep commanded, unknown, conservatively charged, and measured delivery distinct. Exploratory Omega/world-model work may continue with objective-specific eligible evidence; uncertain runtime receipts cannot become certified management observations merely because a software suite passes.

The independent hydraulic process-publication control still yields equal warm/cold profiles, top-layer VWC 0.2124, and durable generation 4 after a foreign historical correction. The scheduled RAM hydration control preserves the winning state/head under CAS conflict. These bounded observations do not close F08/F09 or recertify all hydraulic replay behavior.

The evidence verifier intentionally asserts the reproduced defects. After repair, replace those assertions with the acceptance outcomes above. Successful assertion of a faulty outcome is not remediation acceptance.

## 5. Milestone integrity and source provenance

The unchanged task-register blob is `8a564647af7e588802537817159117b349ff606b`. All six full-acceptance entries remain open:

| Ticket | Line | State |
|---|---:|---|
| ST03-F08-FA | 406 | `[ ]` |
| ST03-F09-FA | 443 | `[ ]` |
| ST06-F16-FA | 796 | `[ ]` |
| ST06-F17-FA | 833 | `[ ]` |
| ST06-F18-FA | 870 | `[ ]` |
| ST06-F19-FA | 907 | `[ ]` |

Register: [pinned task list](https://github.com/webClone/AgriWise/blob/eade4020a1368bc23a41e4da150d69a64b341b98/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md). It establishes planning status rather than production correctness.

| Production path | Git blob |
|---|---|
| `services/agribrain/irrigation_runtime/dispatcher.py` | `1dcb37482ad5c9af3ced371c2d4dc3dc34b0506a` |
| `services/agribrain/irrigation_runtime/safety.py` | `5c6054fa5ef54d1f65bae38a40f20763029b2f6b` |

The companion ZIP includes independent drivers, observations/logs, a 430-file source-integrity manifest, sanitized commit metadata, production-only diff, exact R3 register excerpts, evidence verifier, runner, and checksums. Production runtime copies, repository tests/audit documents, temporary ledgers/checkpoints, bytecode, and credentials are excluded. Obtain an exact pinned checkout separately; the runner verifies the dependency blobs before importing source.

Corrective implementation can proceed with the sequence above. Physical-operation acceptance and dependent evidence certification remain open until the documented gates are verified.

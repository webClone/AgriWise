# AgriBrain production verification — 7e66d0c

Reviewed commit: [`7e66d0c5b3a978339480d9f50856d3e433f01978`](https://github.com/webClone/AgriWise/commit/7e66d0c5b3a978339480d9f50856d3e433f01978). Parent: `19fdb677c626b1d8b5430ab7b81e7376fdbb8b99`. Review date: 11 October 2026. Commit timestamp: 19:04:48 UTC / 20:04:48 Algeria time.

The original seven PB reproduction fixtures now show the claimed corrective behavior. Four expanded contract groups remain reproducible, including a pending START / failed fence failure demonstrated with two actual OS processes and a simulated controller. Physical-operation acceptance is therefore still open.

The central remaining problem is that terminal accounting can still be published before command uncertainty or failed cutoff is resolved. Corrective implementation can proceed immediately. Keep full-acceptance milestones open, and qualify dependent management observations before using them for agronomic decisions, training, economics, or world-model evaluation.

## 1. What was independently verified

GitHub `main` was pinned at the reviewed SHA. Three production files changed: `irrigation_runtime/dispatcher.py`, `safety.py`, and `schemas.py`. Repository test additions/changes and the repository verification document were excluded as correctness evidence. This review made no production edits, invoked no repository pytest suite, and operated no field hardware.

The review runtime consists of 430 production dependency files, all checked against their exact Git blob identities at this commit and parsed with Python's AST parser. This establishes source integrity and syntax for that set; it is not a semantic certification of the entire application or of every dependency file.

Seventeen independent drivers produced 150 named JSON result groups: 148 behavioral/scientific groups and two import diagnostic groups. Every driver completed successfully on its final qualified execution, and the recorded results contain no harness-error group. These groups include counterexamples. They are not 150 passing production-acceptance tests.

The original post-BV driver required a result-serialization adjustment because corrected quota admission now returns a `SafetyViolation` object instead of `None`. The harness now serializes dataclass results. No production behavior was changed to accommodate that adjustment. The new boundary driver was run twice, with the second execution additionally exercising actual OS-process separation.

The process reproduction uses Python's spawn start method, two independent production dispatcher/driver instances, the same durable quota directory, and a shared simulated controller-running flag. Both child processes exit with code zero. It establishes an actual process-boundary software failure, while controller behavior is simulated. It does not establish field behavior or satisfy hardware acceptance.

Other scheduling probes use independent worker-local driver objects in one process or two dispatcher instances sharing a simulated driver. Direct store probes establish internal writer contracts; they do not establish an externally reachable HTTP attack. Simulated loss of source-event metadata is stated explicitly in the identity probe.

The user's reported 558 passing repository tests were not independently rerun. Successful fixtures do not supersede a production counterexample outside their exercised boundary.

The scientific comparison uses the supplied R3 export `R3_current_scientific_sections.txt`, SHA-256 `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`. The evidence bundle includes exact relevant requirement-register excerpts. This review does not recertify all 153 R3 requirements or assert identity with an unseen later monograph revision.

## 2. Original PB01–PB07 reproduction results

| Original finding | Verified corrective behavior | Remaining qualification |
|---|---|---|
| PB01 — pending START after terminal settlement | With a shared driver object, recovery sees the pending send, returns STOP_REQUESTED, blocks completion, retains 8 mm, and rejects the second 8 mm admission under a 10 mm budget. | Another process cannot see that object's pending field. Failed late fencing and durable stop intent remain RP01. |
| PB02 — cancelling OLD stops NEW | Cancelling a qualified OLD while NEW owns the actuator adds zero STOPs and leaves NEW running. Cancelling the actual owner still sends one STOP. | An empty/unknown source identity is treated as a different owner: RP03. |
| PB03 — pressure cutoff suppressed by stale identity | Pressure-high discovered while polling OLD now sends one STOP to the currently running NEW; the successful STOP control stops the simulation. | NEW is recorded terminal even when that STOP fails: RP02. |
| PB04 — invalid area becomes missing support | Negative, zero, boolean, string, NaN, and positive/negative infinity fail before START with no reservation record. Positive 1 ha and absent-support controls retain their expected values. | No new failure reproduced in this scalar boundary. |
| PB05 — stopped-only envelope mutation | Reopen preserves original 8 mm, duration 10 min, flow 10 L/min, and original support including `None`. A second 8 mm admission is blocked. Plot rebinding raises ValueError and the ledger remains readable. | These results cover the original active/stopped-only identity fixtures, not every possible correction history. |
| PB06 — normalized depth/target identical retry | The original raw depth 5 → canonical 4 mm and target 99 → canonical 8 mm cases now accept identical retries without another debit or byte mutation. | Area, duration, flow, device, zone, date, and season normalization remain inconsistent on identical retries: RP04. |
| PB07 — explicit zero litres certified as 8 mm | The direct store now records actual 0 L, delivered 0 mm, and aggregate 0 mm, preserving omitted duration. | The normal dispatcher measured-zero control also remains correct. |

Evidence: `post_bv_probes.py` and `post-bv-results.json`. Older result keys retain their hypothesis names; conclusions follow current recorded values rather than those names.

The sampled original BV01–BV06 and RC01–RC07 reproduction controls also retain their corrected behavior. Their evidence is preserved separately in `remaining-contract-results.json` and `contract-results.json`.

## 3. Remaining contract groups and R3 mapping

Priority P1 means a demonstrated physical-command ownership, cutoff, or conservative-exposure failure requiring repair before the affected physical-operation acceptance. P2 means a demonstrated accounting/identity contract failure requiring repair before affected results are certified. RP01–RP04 are review-local finding IDs, not monograph IDs or new master-plan F/T package identities.

| Finding | Priority | Remaining failure | R3 requirements |
|---|---|---|---|
| RP01 | P1 | Pending state is worker-local; another process can settle it. A failed/exceptional late STOP still discards ownership. Recovery stop intent is not persisted. | AB-ARC-007/008; AB-DAT-003/010/012; AB-EXE-002/003/004 |
| RP02 | P1 | Device cutoff records the actual live owner as stopped before evaluating STOP success. | AB-ARC-006/007/008; AB-DAT-010; AB-EXE-002/004 |
| RP03 | P1 | Missing source-event identity is classified as a confirmed different operation during cancellation. | AB-DAT-005/010; AB-ARC-006/008; AB-EXE-002/003/004 |
| RP04 | P2 | First settlement canonicalizes seven envelope fields that its identical retry compares as raw conflicts. | AB-DAT-007/011; AB-ARC-008; AB-EXE-003 |

### RP01 — Shared command uncertainty and failed late fencing

Production locations: [late ACK terminal guard, dispatcher.py L569–590](https://github.com/webClone/AgriWise/blob/7e66d0c5b3a978339480d9f50856d3e433f01978/services/agribrain/irrigation_runtime/dispatcher.py#L569-L590), [completion pending check L1036–1047](https://github.com/webClone/AgriWise/blob/7e66d0c5b3a978339480d9f50856d3e433f01978/services/agribrain/irrigation_runtime/dispatcher.py#L1036-L1047), and [idle pending recovery L1575–1602](https://github.com/webClone/AgriWise/blob/7e66d0c5b3a978339480d9f50856d3e433f01978/services/agribrain/irrigation_runtime/dispatcher.py#L1575-L1602).

**Actual OS-process reproduction.** Process A reserves 8 mm and holds START before application/ACK. Process B queries the same simulated controller, which is truthfully idle. B has its own actuator object: its pending field is empty, although A's pending field is populated and the durable record is DISPATCHING.

B converts the operation to VALIDATING and completes it with explicit 0 L/0 min. Its durable receipt becomes COMPLETED and the original reservation disappears. An independent second-device 8 mm command is admitted under the same 10 mm budget.

Release A's START. It executes, and the new ACK guard recognizes the terminal receipt and attempts emergency STOP. The controlled driver returns a failed STOP result. The guard ignores that result, assigns COMPLETED, removes A's active event, and ends its watchdog.

| Observed field | Result |
|---|---|
| Child-process exit codes | `[0, 0]` |
| Recovery result | COMPLETED, reservation 0 mm |
| Original result after late ACK | COMPLETED |
| Original simulated controller | Running |
| Original START / STOP attempts | 1 / 1, with STOP unsuccessful |
| Original active owner / watchdog count | 0 / 0 |
| Original durable reservation | Absent |
| Original receipt | 0 L, 0 min, 0 mm, COMPLETED |
| Second operation | EXECUTING |
| Final quota reservation | 8 mm, representing only the second operation |

Two commands of 8 mm are now running in the simulation under a 10 mm budget. This is commanded exposure, not a claim of 16 mm measured delivery. The full original exposure is no longer represented.

The independent worker-view reproduction also covers STOP exceptions. Both a failed result and an exception leave the first operation running with zero active owner/watchdog and a terminal zero-delivery receipt. A fresh restart trusts COMPLETED and adds no STOP. The successful fence control stops the first controller, confirming that the problematic boundary is the unresolved send plus failed-fence handling rather than universal fence failure.

**Durable intent subcase.** Even with a shared driver object, pending recovery writes STOP_REQUESTED only to its local event. The durable phase remains DISPATCHING. If that recovery worker disappears before polling, the original ACK promotes the durable event to EXECUTING. A later cold recovery returns EXECUTING, sends zero STOPs, and the simulated controller runs. Reservation 8 mm remains conserved, but the asserted stop intent does not survive the worker boundary.

**Required repair.** Pending-send identity, owner/generation, and unresolved physical outcome must be represented durably. A local pending field can supplement this record; it cannot authorize release by another process. A current idle query must not settle a durable DISPATCHING operation whose transport can still deliver it. Require operation-specific not-applied/completed evidence or a qualified fence of the outstanding command.

Persist STOP_REQUESTED and its generation before recovery returns or asynchronous cutoff begins. ACK promotion must compare-and-swap against the expected generation/phase; an ACK cannot erase a newer stop intent. Check a late STOP result and exceptions before terminal publication or cleanup. Failed/unknown cutoff retains active ownership, original deadline monitoring, and conservative exposure.

If a zero-delivery receipt was already published before subsequent physical activity, preserve its original observation and add explicit correction/supersession lineage plus unresolved exposure. Do not silently alter old measurements. Do not simply call `reopen_active` on a settled event and assume recovery is fixed: terminal settled-receipt precedence must also be reconciled so restart cannot bypass the reopened activity.

**Acceptance gates.** Repeat the actual two-process paused-send scenario with successful, failed, exceptional, and lost STOP responses. No potentially executable send may release conservative exposure before qualified resolution. Failed cutoff must retain recoverable STOP_REQUESTED ownership and block the competing 8 mm request. Restart must resume the original deadline and stop intent. Every accepted terminal receipt must be compatible with the controller operation generation and the measurement window it certifies.

Evidence keys: `actual_OS_process_pending_terminal_fence`, `separate_worker_pending_terminal_fence`, `pending_recovery_stop_intent_not_durable` in `post-pb-results.json`.

### RP02 — Failed device cutoff terminalizes the actual owner

Production location: [dispatcher.py L867–934](https://github.com/webClone/AgriWise/blob/7e66d0c5b3a978339480d9f50856d3e433f01978/services/agribrain/irrigation_runtime/dispatcher.py#L867-L934).

OLD has completed on the controller between polls; NEW now runs on the same device. Pressure 2 bar exceeds a configured maximum of 1 bar. The fixture uses zero debounce to isolate routing. The monitor identifies NEW as the affected operation, and the dispatcher now correctly attempts physical cutoff.

When STOP returns unsuccessful, however, the new branch has already updated NEW to EMERGENCY_STOPPED and called `record_stopped_delivery`. That call consumes NEW's active reservation into a stopped receipt. If NEW is in the same dispatcher's local map, the branch also finalizes NEW and removes its watchdog before checking `stop_result.success`.

The later attempt to update NEW back to STOP_REQUESTED does not restore it: `update_status` operates on reservations, while NEW's reservation has already been removed. Its authoritative record is now the terminal stopped receipt, exposed by `get_active_record` as CANCELLED.

| Failed-cutoff observation | Same dispatcher owns NEW | Different dispatcher owns NEW |
|---|---|---|
| Simulated controller | Running | Running |
| NEW local phase | EMERGENCY_STOPPED and removed | Still EXECUTING in the other worker |
| NEW durable active reservation | Absent | Absent |
| NEW stopped receipt | Present | Present |
| Fresh restart result | CANCELLED, no active owner | CANCELLED, no active owner |
| Additional STOPs from old-event retry and restart | 0 | 0 |

Conservative numeric exposure is not dropped here: 8 mm remains charged as stopped delivery, alongside OLD's 1 mm reservation. The defect is false terminal authority and loss of reliable cutoff recovery, not quota erasure. The same-owner fixture directly removes NEW's local watchdog. In the separate-owner fixture, the other live worker initially retains its monitor, but a fresh restart skips NEW as terminal.

The successful STOP control stops the simulation and finalizes both relevant local events. This confirms the healthy device-cutoff fix while isolating failed-result handling.

**Required repair.** Select the actual affected operation before executing cutoff. Evaluate the cutoff result before publishing any stopped receipt or removing that operation's tracking. Failed or unknown STOP must leave the live owner in durable/local STOP_REQUESTED with conservative exposure and original timer, including when discovered through another event's poll. Device-level protection must remain independent of stale-event duration fencing and of ledger errors.

**Acceptance gates.** With NEW running and OLD being polled, unsuccessful/exceptional cutoff retains NEW as active and recoverable. Repeated polls and fresh restart must retry or reconcile the actual live operation. Successful cutoff may then publish stopped outcome/accounting. Validate same-worker and cross-worker ownership, latched sensor faults, absent telemetry, and ledger read/write failure without preventing the initial physical cutoff.

Evidence key: `failed_device_cutoff_terminalizes_actual_owner`.

### RP03 — Unknown identity is promoted to a different-owner cancellation

Production location: [dispatcher.py L1155–1185](https://github.com/webClone/AgriWise/blob/7e66d0c5b3a978339480d9f50856d3e433f01978/services/agribrain/irrigation_runtime/dispatcher.py#L1155-L1185).

The `other_active` predicate treats any present command whose source ID differs from the requested event ID as proof of another owner. An empty source ID satisfies that comparison. The branch then sets `stop_success = True` without sending STOP and proceeds to finalize cancellation.

The probe first runs E, then explicitly simulates loss of the driver's source-event metadata while the same application continues running. The command object remains present, with source ID `""`. Cancelling E produces zero STOP attempts, returns CANCELLED, removes all local ownership/watchdog entries, and publishes a stopped receipt. A fresh restart returns CANCELLED with zero active owners while the controller simulation still runs.

The 8 mm conservative exposure remains charged; it is not lost. The lost contract is qualified identity and physical-outcome recovery. Missing identity does not establish that the running operation is a different one.

Controls distinguish all three cases: a matching qualified E identity sends one STOP and stops the simulation; a qualified different identity suppresses STOP as intended; an empty identity wrongly follows the different-owner terminal branch.

**Required repair.** Use an explicit three-way result: qualified same operation, qualified different operation, or unknown. A different-owner result requires nonempty compatible identity and adequate receipt/generation evidence. Unknown identity retains unresolved cancellation/STOP_REQUESTED and monitoring/exposure until reconciled. The action taken must respect the distinction between event-specific cancellation and an explicitly authorized device/global safety cutoff; do not blindly stop a possibly different healthy owner.

**Acceptance gates.** Empty, absent, malformed, or stale operation identity cannot manufacture a successful stopped outcome. Both qualified controls must retain their current behavior. A fresh restart must preserve unknown cancellation intent and original duration authority rather than skipping a fabricated terminal receipt.

Evidence key: `empty_identity_treated_as_other_live_owner`. This is a controlled driver-metadata-loss boundary, not an HTTP exploitation claim.

### RP04 — Normalization remains inconsistent across the full envelope

Production locations: [retry candidate, safety.py L982–1021](https://github.com/webClone/AgriWise/blob/7e66d0c5b3a978339480d9f50856d3e433f01978/services/agribrain/irrigation_runtime/safety.py#L982-L1021) and [first-publication canonical envelope L1028 onward](https://github.com/webClone/AgriWise/blob/7e66d0c5b3a978339480d9f50856d3e433f01978/services/agribrain/irrigation_runtime/safety.py#L1028-L1068).

The original depth and target cases are corrected. The broader accepted-request idempotence property is still violated for seven other dimensions. Begin with an 8 mm reservation over 1 ha, duration 10 min, flow 10 L/min, canonical device/zone, date 11 October, season S1. Actual 40,000 L over the canonical 1 ha yields 4 mm:

\[
I_{mm}=\frac{40{,}000}{10{,}000\times1}=4.
\]

For each row below, submit a first settlement with one changed caller field and then repeat the exact same request. First publication accepts and restores the canonical envelope. Identical retry compares the caller's raw field instead of the same canonical representation.

| Caller field | First supplied value | First result | Identical retry |
|---|---|---|---|
| Area | 2 ha | Accepts; canonical 1 ha and 4 mm | ValueError |
| Command duration | 20 min | Accepts; canonical 10 min | ValueError |
| Flow | 3 L/min | Accepts; canonical 10 L/min | ValueError |
| Device | Other device | Accepts; original device | ValueError |
| Zone | Other zone | Accepts; original zone | ValueError |
| Date | 12 October | Accepts; 11 October | ValueError |
| Season | S2 | Accepts; S1 | ValueError |

Matching canonical requests and changed-target normalization controls succeed on both calls. Failed retries do not change bytes or add debit. The finding is asymmetric acceptance, not double counting.

For area, retry depth normalization itself also uses caller area 2 ha, yielding 2 mm before area mismatch checks, while first publication used canonical area 1 ha and recorded 4 mm. Target-only normalization cannot resolve this wider inconsistency.

**Required repair.** Build one validated canonical settlement candidate before both first-publication and retry paths. Choose and document whether incompatible envelope inputs fail before the first write or are normalized using immutable admission identity. Compare that same candidate on retries. Accepted request identity, measurements, support, missingness, device/zone, and accounting period must follow a consistent policy. New observations/corrections require explicit lineage rather than being silently treated as retries.

**Acceptance gates.** Every successful first request has an identical retry returning the same result without receipt/journal/debit mutation. Every genuine conflict is rejected before first publication or consistently rejected as a changed request. Apply the rule across all envelope fields while preserving strict numeric validation and measured-zero behavior.

Evidence key: `full_envelope_normalization_retry_inconsistency`. This is an expanded remaining PB06 contract, not a claim that the original depth/target examples are still broken.

## 4. Regression observations and implementation plan

The independent evidence verifier confirms the sampled original RC/BV fixes and the seven original PB fixture outcomes, while also confirming the four remaining groups above. Its successful completion does not signify production acceptance: its assertions deliberately include demonstrated defects.

The hydraulic process-publication probe still returns equal warm/cold profiles, with top-layer VWC 0.2124 and durable publication generation 4 after a foreign historical correction. The scheduled RAM hydration control preserves the winning soil state/head under CAS conflict. These bounded observations do not close F08/F09. This commit changes runtime schemas, safety, and dispatch; it does not alter the hydraulic runner.

| Order | Implementation work | Concrete gate |
|---|---|---|
| 1 | Define one durable operation lifecycle: immutable envelope, owner/generation, pending send, qualified ACK, stop intent, physical resolution, and exposure projection. | Independent workers observe the same unresolved command and cannot complete it from local idle state. |
| 2 | Repair RP01 pending admission/completion and late fencing; persist stop intent and fence ACK promotion by generation. | Actual process reproduction conserves exposure and ownership through failed/exceptional STOP and restart. |
| 3 | Repair RP02 result ordering and affected-operation recovery. | Failed device cutoff cannot create a stopped receipt or remove the real owner's monitor. |
| 4 | Repair RP03 three-way identity qualification across cancellation/recovery. | Unknown identity remains unresolved; qualified same/different controls continue to work. |
| 5 | Repair RP04 using a shared settlement-candidate function or consistent reject-before-write policy. | All accepted first requests have idempotent retries across the complete envelope. |
| 6 | Integrate process crash, late ACK, lost receipt, corrupt store, STOP failure, zero/missing measurement, and historical hydraulic publication scenarios. | Local events, durable authority, simulated controller identity, receipt lineage, and exposure remain consistent across transitions. |
| 7 | Complete designated hardware/controller acceptance with actual device protections and receipt semantics. | Evidence justifies the relevant full-acceptance tickets rather than inferring them from unit simulations. |

A useful explicit transition rule is:

\[
\text{terminal publication and exposure release}
\Rightarrow
\text{qualified physical resolution for the same operation generation}.
\]

Controller idle at one instant, absent local pending state, a STOP attempt, or an unknown source ID does not establish that resolution. Measurement zero must be bound to its acquisition window; a zero before a later START cannot certify that subsequent operation's outcome.

For R3's agronomic and data-science target, preserve this distinction in downstream management events and learning records. False zero irrigation or a falsely stopped operation changes water forcing, stress attribution, nutrient response, intervention economics, and rollout evaluation. Exploratory Omega/world-model work can continue under objective-specific eligibility; uncertain command receipts must not be promoted into certified delivered-management observations or labels.

After remediation, update the evidence verifier's faulty-outcome assertions to require these gates. Keep successful controls for positive area/missing support, measured zero/missing duration, quota conservation, stale-duration fencing, device cutoff, and hydraulic publication.

## 5. Milestones, source identity, and reproduction

All six full-acceptance entries remain open in the unchanged task-register blob `8a564647af7e588802537817159117b349ff606b`:

| Ticket | Line | State |
|---|---:|---|
| ST03-F08-FA | 406 | `[ ]` |
| ST03-F09-FA | 443 | `[ ]` |
| ST06-F16-FA | 796 | `[ ]` |
| ST06-F17-FA | 833 | `[ ]` |
| ST06-F18-FA | 870 | `[ ]` |
| ST06-F19-FA | 907 | `[ ]` |

Register: [pinned task list](https://github.com/webClone/AgriWise/blob/7e66d0c5b3a978339480d9f50856d3e433f01978/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md). It establishes planned acceptance status, not production correctness.

| Production path | Git blob |
|---|---|
| `services/agribrain/irrigation_runtime/dispatcher.py` | `8fc13b2d76167c1d30e63cc8c1b0618986d41430` |
| `services/agribrain/irrigation_runtime/safety.py` | `a13deebb4c1fd2103381cf193e96c578cdf98f28` |
| `services/agribrain/irrigation_runtime/schemas.py` | `2136a933f83ced4ee0a17fbce34ac70473098eac` |

The companion ZIP contains 17 independent drivers, JSON observations/logs, source-integrity manifest, sanitized commit metadata, production-only diff, R3 requirement excerpts, evidence verifier, runner, and checksums. It excludes production runtime copies, repository test/audit documents, temporary quota/checkpoint files, bytecode, and credentials. Obtain an exact pinned checkout separately; the runner verifies all 430 dependency blobs before importing source.

Proceed with these corrective repairs and independent eligible work. Physical runtime acceptance remains open until the remaining lifecycle contracts and integrated controller gates are verified.

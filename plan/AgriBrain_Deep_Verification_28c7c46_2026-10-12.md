# AgriBrain production verification — 28c7c46

Reviewed commit: [`28c7c46ef69031c6482db7f5a6afbf93fbe1e288`](https://github.com/webClone/AgriWise/commit/28c7c46ef69031c6482db7f5a6afbf93fbe1e288). Parent: `eade4020a1368bc23a41e4da150d69a64b341b98`. Review date: 12 October 2026. Commit timestamp: 16:47:34 UTC / 17:47:34 Algeria time.

The original ER01–ER05 reproductions now show the claimed corrections. Four broader contract groups remain reproducible. Two concern physical operation recovery and concrete driver STOP confirmation; two concern command identity and terminal ledger projections. Runtime physical-operation acceptance should remain open.

The new findings include failed MQTT publications and negative Modbus responses being promoted to a stopped outcome by the production driver/dispatcher integration. No field hardware or network connection was used: the real production functions were exercised with local transport substitutes.

## 1. Scope and evidence qualifications

GitHub `main` was pinned at the reviewed SHA. The commit changes two production files, `irrigation_runtime/dispatcher.py` and `safety.py`. Its repository tests and repository verification document were excluded as correctness evidence. This review modified no production files and invoked no repository pytest suite.

The review runtime contains 430 production dependency files. Every file's exact Git blob identity was checked and every file parsed successfully with Python's AST parser. This establishes source identity and syntax for that set, not semantic certification of 430 modules or of the entire AgriWise application.

Nineteen independent drivers produced 163 named JSON groups: 161 behavioral/scientific groups and two import diagnostic groups. Final executions completed successfully, with no harness-error result group. These groups include demonstrated defects; they are not 163 passing acceptance tests. The evidence verifier asserts both correct controls and faulty outcomes to establish consistency with this report.

The new recovery adapter implements the production `IrrigationActuator` interface and deliberately has no public `running` attribute. Current MQTT, HTTP, and Modbus classes likewise use status/cache/query mechanisms rather than that simulator-specific attribute. The adapter's live query would report the simulated controller's actual running state; query counts establish whether production recovery consulted it.

The protocol integration uses the real `MQTTActuator.emergency_stop`, `ModbusActuator.emergency_stop`, and dispatcher functions. Local clients return failed publication or write responses without operating a controller. Other probes are controlled worker/scheduler simulations or direct internal quota writer sequences. They do not establish field-controller protections, indefinite physical duration, or an externally reachable HTTP attack.

The earlier queued-send/crash fixture still uses real OS-process separation and intentional termination of its simulated sender. At this commit its exercised recovery correctly attempts STOP. Its sender exit −15 is deliberate fault injection. The previously qualified ACK hold uses a local asynchronous future rather than an IPC event lock.

The user's reported 575 passing repository tests were not independently rerun. They remain separate from the production observations below.

The scientific target is the supplied R3 export `R3_current_scientific_sections.txt`, SHA-256 `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`. The evidence bundle contains exact relevant register excerpts. This review compares against that supplied target; it does not recertify all 153 requirements or assert identity with an unseen later monograph revision.

## 2. Original ER01–ER05 corrective verification

| Original finding | Independent result at 28c7c46 | Qualification |
|---|---|---|
| ER01 — STOP polling terminalizes pending START | Pending poll retains local/durable STOP_REQUESTED, 8 mm reservation, owner, and watchdog. No premature stopped receipt is published. | Recovery through a fresh production-shaped adapter remains NR01. |
| ER01 — queued sender crash leaves controller skipped | The original process fixture's cold recovery issues one STOP and stops the simulated controller. | That fixture exposes public `running` state; the new adapter cases do not. |
| ER01 — late-fence watchdog rebased | Original and restored monotonic origin both remain 0 at clock 661 s. STOP_REQUESTED polling still retries cutoff. | A latched duration violation need not re-emit; origin equality establishes the correction. |
| ER02 — raised STOP loses intent/retry | Exception is normalized rather than propagated. OLD/NEW retain STOP_REQUESTED; a second poll adds another cutoff attempt. Failed-result control behaves similarly. | Concrete drivers can still return false positive success instead of a failed/exceptional result: NR03. |
| ER03 — cancellation trusts cache or preempts pending NEW | Cancellation performs a live query; stale cached ONLINE/OFFLINE/UNKNOWN cases retain unresolved intent when the controller reports running. OLD cancellation sends zero STOPs to qualified pending NEW, which completes its START normally. | Stopped-receipt recovery has a different, weaker status/identity path: NR01. |
| ER04 — reopening lowers measured exposure | Measured 12 mm remains 12 mm effective exposure. Competing 10 mm admission under 20 mm is blocked. | The exposure is stored as the command volume, mutating command identity: NR02. |
| ER05 — conflicting re-settlement corrupts aggregate | Conflicting 3 mm re-settlement raises ValueError, retains the original 4 mm receipt/aggregate, and subsequent reads succeed. | Active and settled records can still coexist and hide completion: NR04. |

Evidence: `post_rp_probes.py`, `post-rp-results.json`. Older result keys retain their hypothesis names; current values determine the result.

ER05's demonstrated correction is uniform conflict rejection. Under the normal guarded flow, an existing settled receipt returns or raises before reaching the later `prior_settled` subtraction block. The fixture does not demonstrate a newly accepted replacement using net-delta accounting. That distinction matters when describing the implemented correction policy.

## 3. Remaining findings and R3 mapping

NR01–NR04 are review-local finding IDs, not monograph IDs or master-plan F/T package identities. P1 identifies a demonstrated physical-command authority/recovery failure requiring repair before the affected physical-operation acceptance. P2 identifies a demonstrated identity/accounting projection failure requiring repair before affected results are certified.

| Finding | Priority | Remaining contract failure | R3 requirements |
|---|---|---|---|
| NR01 | P1 | Stopped recovery skips live querying, and device running state is misattributed to an old stopped event. | AB-ARC-006/008; AB-DAT-010/012; AB-EXE-002/003/004 |
| NR02 | P2 | Effective exposure replaces immutable commanded target, causing false payload conflict and rewritten target history. | AB-DAT-007/010/011; AB-ARC-008; AB-EXE-003/005 |
| NR03 | P1 | Concrete MQTT/Modbus drivers report STOP success after failed transport responses; dispatcher removes physical recovery ownership. | AB-ARC-006; AB-DAT-006/010; AB-EXE-002/004/005 |
| NR04 | P2 | Repeated terminal reservation hides a settled receipt, reports DISPATCHING, and adds phantom exposure. | AB-DAT-010/012; AB-ARC-007/008; AB-EXE-003 |

### NR01 — Stopped recovery lacks live status and operation qualification

Production location: [dispatcher.py L1487–1521](https://github.com/webClone/AgriWise/blob/28c7c46ef69031c6482db7f5a6afbf93fbe1e288/services/agribrain/irrigation_runtime/dispatcher.py#L1487-L1521), followed by active-record hydration and STOP_REQUESTED reconciliation.

The new stopped-receipt branch determines running state from `getattr(actuator, "running", False)` or private cached `_status == EXECUTING`. It does not call `get_status` before either accepting the terminal receipt or reopening it.

**Fresh-adapter case.** The controller simulation is running an already queued OLD operation after a previous stopped receipt. The recovery adapter has no public `running` flag and cached ONLINE, UNKNOWN, or OFFLINE. A current status query would return EXECUTING, but the branch performs zero queries and returns CANCELLED with zero STOPs, owners, or watchdogs. The simulation keeps running. An already-EXECUTING-cache control performs one STOP and stops it, showing that behavior depends on the cache rather than a current observation.

| Adapter's initial cache | Live queries | STOPs | Controller after recovery | Recovered outcome |
|---|---:|---:|---|---|
| ONLINE | 0 | 0 | Running | CANCELLED |
| UNKNOWN | 0 | 0 | Running | CANCELLED |
| OFFLINE | 0 | 0 | Running | CANCELLED |
| EXECUTING control | 0 | 1 | Stopped | CANCELLED |

**Different-operation case.** OLD is properly cancelled, and NEW then starts on the same device. A recovery worker replays OLD's stopped snapshot with a busy cache. If its local command metadata identifies NEW, physical STOP is correctly suppressed later, but the branch has already reopened OLD and reports it as active STOP_REQUESTED. A valid terminal OLD is unnecessarily resurrected.

If the recovery worker has no local active-command metadata, the same busy cache is treated as evidence that OLD is running. It reopens OLD and sends one device STOP. NEW is stopped in the simulation, while NEW's local/durable event remains EXECUTING. A device being busy does not identify the old event as the current operation.

Both status freshness and operation binding are needed. Merely adding a live device query would address the first case but still leave the second attribution error.

**Repair.** Resolve canonical receipt scope before lookup. Obtain current controller evidence and bind it to operation ID/generation and the authoritative current device owner. Reopen an old terminal event only when qualified evidence contradicts its physical outcome for that same operation generation. Preserve a different confirmed live operation. Device-busy status without identity follows an explicit unresolved reconciliation path, rather than assigning activity to whichever snapshot is being replayed. Device/global safety cutoff remains a distinct action with its own hazard basis.

**Acceptance.** Fresh ONLINE/UNKNOWN/OFFLINE caches cannot bypass current qualification when unresolved physical activity is suspected. A same-operation contradiction is recovered and cut off with retained exposure/deadline. Replaying stopped OLD while NEW owns the device leaves NEW running and OLD terminal. Unknown identity must not manufacture an OLD ownership claim or silently certify stopped activity. Cover adapter refresh, status timeout, receipt loss, delayed commands, and independent worker views.

Evidence: `stopped_recovery_skips_live_query_on_production_shaped_adapter`, `stopped_OLD_recovery_reopens_or_stops_different_NEW` in `post-er-results.json`.

### NR02 — Exposure bound mutates command target and retry identity

Production locations: [safety.py L1347–1373](https://github.com/webClone/AgriWise/blob/28c7c46ef69031c6482db7f5a6afbf93fbe1e288/services/agribrain/irrigation_runtime/safety.py#L1347-L1373), [dispatcher target hydration L1523–1528](https://github.com/webClone/AgriWise/blob/28c7c46ef69031c6482db7f5a6afbf93fbe1e288/services/agribrain/irrigation_runtime/dispatcher.py#L1523-L1528), and the active-reservation payload comparison in `submit_event`.

The lower-bound correction correctly raises exposure from target 8 mm to measured 12 mm. It writes the maximum into `volume_mm`, however, which other paths interpret as immutable commanded volume. The reopened record has `volume_mm = 12`, `delivered_volume_mm = 12`, and no separate retained commanded target.

The fixture uses 0.001 ha = 10 m². Original target 8 mm corresponds to 80 L; accepted measured 120 L corresponds to 12 mm. Those remain different facts:

\[
I_{target}=8\ \mathrm{mm},\qquad I_{measured}=12\ \mathrm{mm},\qquad E\geq12\ \mathrm{mm}.
\]

After reopening:

- An identical original 8 mm event retry returns FAILED with payload conflict against active 12 mm. It sends zero additional STARTs; this is false rejection, not demonstrated redosing.
- Cold recovery reads the exposure as `event.target_volume_mm = 12`.
- The resulting stopped receipt records target 12 mm and delivery 12 mm, whereas the original command target was 8 mm.

The budget lower bound is now correct, but command identity and post-action interpretation are not. An observed over-delivery ratio 12/8 = 1.5 becomes 12/12 = 1.0 if downstream code relies on the rewritten target.

**Repair.** Separate immutable commanded depth, qualified delivered depth, and effective exposure. For example, command envelope target remains 8; measured outcome remains 12; exposure projection uses at least 12. Use exposure for quota admission, commanded target for command construction/payload compatibility, and qualified outcome for response metrics. Preserve support, period, provenance, and correction lineage.

Migrate existing reopened records using immutable admission/journal or superseded-receipt target evidence. Do not blindly treat current `volume_mm` as the historical target, because it may already hold the enlarged exposure.

**Acceptance.** Reopening a target-8/measured-12 operation keeps both values distinct and preserves exposure at least 12. Original target-8 retries remain compatible without another START. Cold recovery, stopped/settled receipts, and response metrics retain target 8 and outcome 12. Competing 10 mm admission under 20 mm must still fail. Include zero, partial, exact-target, and over-delivery controls.

Evidence: `effective_exposure_replaces_immutable_command_target`.

### NR03 — Concrete drivers falsely confirm STOP after transport failure

Production locations: [MQTT emergency STOP, mqtt_driver.py L324–350](https://github.com/webClone/AgriWise/blob/28c7c46ef69031c6482db7f5a6afbf93fbe1e288/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L324-L350), [Modbus emergency STOP L468–501](https://github.com/webClone/AgriWise/blob/28c7c46ef69031c6482db7f5a6afbf93fbe1e288/services/agribrain/irrigation_runtime/drivers/modbus_driver.py#L468-L501), and [Modbus coil-result helper L187–193](https://github.com/webClone/AgriWise/blob/28c7c46ef69031c6482db7f5a6afbf93fbe1e288/services/agribrain/irrigation_runtime/drivers/modbus_driver.py#L187-L193).

These driver files are unchanged in this commit. They were examined because dispatcher correctness now depends on the meaning of `CommandResult.success` supplied by them.

**MQTT.** The concrete method publishes at QoS 0 and QoS 1 and immediately returns `success=True` when `_client` and `_connected` are set. It does not check either publication result or await controller stop confirmation. The probe supplies a local client returning a failed publication result with nonzero `rc = 4` for both calls. No STOP reaches the simulated controller, but the method reports success.

**Modbus.** `_write_coil` returns `False` when a response reports `isError()`. The emergency-stop method awaits its coil calls without checking those booleans. Its local `success=True` changes only on a raised exception. The probe supplies six negative responses covering emergency-stop, valve, and pump coils; every response reports error, yet the method returns success.

Both concrete functions are integrated with the real dispatcher at an expired 600 s operation, using clock 601 s. In each case, the dispatcher treats the returned success as physical resolution, sets driver cache ONLINE, publishes a stopped receipt, and removes the event and watchdog.

| Concrete driver | Injected transport outcome | Simulated controller | Published event | Owner/watchdog |
|---|---|---|---|---|
| MQTT | Both publications fail | Running | EMERGENCY_STOPPED | 0 / 0 |
| Modbus | All six coil responses report errors | Running | EMERGENCY_STOPPED | 0 / 0 |

The canonical stopped view is CANCELLED in both cases and conservative charge 8 mm is retained. This is loss of qualified physical cutoff authority and recovery monitoring, not numeric quota erasure. No physical controller or network broker was contacted.

**Repair.** Define a shared driver result contract separating local send, protocol acceptance, controller ACK, and qualified stopped outcome. Negative publish/write results cannot be reported as successful STOP. MQTT publication or broker delivery acknowledgement alone does not prove valve closure or operation completion; maintain unresolved stop intent until controller-specific evidence resolves it. Modbus must check each required write outcome and report failed/unknown outputs; qualified readback or controller outcome must have explicit semantics.

The dispatcher should finalize from a qualified stopped outcome, not from a generic successful transport flag. Preserve immediate emergency sending and fault isolation while allowing asynchronous confirmation. Ensure every protocol supplies equivalent authority semantics rather than letting different transports assign different meanings to one boolean.

**Acceptance.** Failed publish, negative coil response, exception, disconnected client, accepted transport without physical ACK, and partial-output success retain unresolved cutoff and exposure. A qualified current same-operation stop confirmation may finalize. Exercise the concrete drivers with local transport substitutes before hardware acceptance, including restart and stale-cache behavior. Keep global/device safety cutoff able to reach all intended outputs despite individual failures.

Evidence: `concrete_driver_failed_transport_promoted_to_stopped`.

### NR04 — Terminal reservation hides completion and creates phantom exposure

Production locations: [SharedQuotaStore.reserve, safety.py L780 onward](https://github.com/webClone/AgriWise/blob/28c7c46ef69031c6482db7f5a6afbf93fbe1e288/services/agribrain/irrigation_runtime/safety.py#L780), [terminal queries L1419–1464](https://github.com/webClone/AgriWise/blob/28c7c46ef69031c6482db7f5a6afbf93fbe1e288/services/agribrain/irrigation_runtime/safety.py#L1419-L1464), and active-record join handling in dispatcher.py L283 onward.

ER05 now rejects the original conflicting re-settlement and preserves a readable ledger. An overlapping active-plus-settled state is still accepted by `reserve`, and an identical settlement retry does not remove that overlap.

The internal writer sequence reserves E for 8 mm, settles measured 4 mm, then repeats reservation under the same E and envelope without an explicit reopen or new generation. It repeats the identical successful settlement as well. The ledger remains readable and the identical settlement changes no bytes, but:

- The raw 4 mm settled receipt still exists.
- `is_settled(E)` returns False and `get_settled_receipt(E)` returns None because an active reservation exists.
- Duplicate submission reports DISPATCHING instead of the settled outcome, with zero physical STARTs.
- Quota projection counts 8 mm reserved plus 4 mm settled for the same operation.
- A second 4 mm request is blocked under a 10 mm budget, although known prior delivery 4 plus requested 4 is only 8 mm. The phantom reservation consumes eligibility.

The example uses the same plot/day/season and consistent 10 m² support. It establishes internal writer and response-projection contracts. It does not establish an HTTP path or physical redosing of a completed event.

**Repair.** Enforce terminal/reservation transition semantics at the writer boundary under one atomic contract. A reservation retry of a terminal event joins its canonical outcome or rejects before mutation, unless an explicit qualified reopen/new generation is being created. Reopen transitions require lineage and appropriate exposure semantics. Avoid hiding a valid terminal receipt merely because another writer recreated a reservation. Align reader projection, dispatcher join response, settlement retry behavior, and quota accounting.

**Acceptance.** The exact repeated-reserve/identical-settle sequence retains visible completion and its 4 mm debit without a phantom reservation. An eligible subsequent 4 mm request under 10 mm succeeds. Genuine conflicts still fail without byte changes or unreadable aggregates. Explicitly reopened unresolved operations retain exposure and remain recoverable, rather than being mistaken for terminal retries.

Evidence: `terminal_reserve_hides_receipt_and_adds_phantom_exposure`.

## 4. Implementation sequence and readiness

The remaining defects are cross-component contract differences: simulator versus concrete driver state, device status versus operation identity, exposure versus command target, and terminal history versus active reservation projection. Shared definitions and transition rules should replace endpoint-specific interpretations.

| Order | Concrete work | Completion gate |
|---|---|---|
| 1 | Define stop-result authority and repair concrete MQTT/Modbus negative-result handling. | Failed or merely accepted transport cannot produce a stopped outcome or remove recovery ownership. |
| 2 | Repair stopped-receipt recovery with live evidence and operation/generation binding. | Same-operation contradiction is recovered; stopped OLD cannot stop qualified NEW; stale caches do not bypass unresolved recovery. |
| 3 | Split immutable target, measured outcome, and effective exposure across schema, persistence, hydration, retry comparison, and command construction. | Target 8, outcome 12, and exposure at least 12 remain distinct across all transitions. |
| 4 | Make reserve/reopen/settle/read projections obey one atomic lifecycle. | Terminal retries preserve completion; explicit reopen is auditable; every accepted ledger remains readable and correctly charged. |
| 5 | Run integrated concrete-driver/worker/restart/correction scenarios, then designated hardware acceptance. | Local, durable, controller, observation, and accounting authority agree for the same operation generation. |

Useful invariant boundaries are:

\[
\text{command identity}\neq\text{exposure projection},\qquad E\geq\max(I_{target},I_{qualified}).
\]

\[
\text{device busy}\not\Rightarrow\text{old event executing},\qquad
\text{transport accepted}\not\Rightarrow\text{physical STOP confirmed}.
\]

For R3's agronomic/data-science target, these distinctions preserve management forcing, stress attribution, intervention response, over-delivery metrics, water cost, and training/rollout eligibility. Exploratory Omega/world-model work can proceed with objective-specific eligible evidence; falsely stopped or target-rewritten management records cannot become certified labels merely because a software suite passes.

The independent hydraulic process-publication control still produces equal warm/cold profiles, top-layer VWC 0.2124, and durable generation 4 after a foreign historical correction. The scheduled RAM hydration control preserves the winning state/head under CAS conflict. These bounded observations do not close F08/F09 or recertify all hydraulic replay behavior.

The evidence verifier intentionally asserts current counterexamples. After repair, replace those faulty-outcome assertions with the acceptance results above while preserving successful controls. A verifier confirming a defect is not a remediation acceptance suite.

## 5. Milestones, source identity, and reproduction

The unchanged task-register blob is `8a564647af7e588802537817159117b349ff606b`. All six full-acceptance entries remain open:

| Ticket | Line | State |
|---|---:|---|
| ST03-F08-FA | 406 | `[ ]` |
| ST03-F09-FA | 443 | `[ ]` |
| ST06-F16-FA | 796 | `[ ]` |
| ST06-F17-FA | 833 | `[ ]` |
| ST06-F18-FA | 870 | `[ ]` |
| ST06-F19-FA | 907 | `[ ]` |

Register: [pinned task list](https://github.com/webClone/AgriWise/blob/28c7c46ef69031c6482db7f5a6afbf93fbe1e288/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md). It establishes planning status rather than correctness.

| Production path | Git blob |
|---|---|
| `services/agribrain/irrigation_runtime/dispatcher.py` | `7100640092a6ad74ff66d4327feb25f12c8d6925` |
| `services/agribrain/irrigation_runtime/safety.py` | `0e9240dcef64ce13bda634e03bcacf9f5a7fb6b9` |
| `services/agribrain/irrigation_runtime/drivers/mqtt_driver.py` | `19dede1168145cc715aee47cfd7790548d046020` |
| `services/agribrain/irrigation_runtime/drivers/modbus_driver.py` | `5d9a39722ee8e9a5fcde51758926382d9928a622` |

The companion ZIP contains 19 independent drivers, observations/logs, a 430-file integrity manifest, sanitized commit metadata, production-only diff, exact R3 register excerpts, evidence verifier, runner, and checksums. Production runtime copies, repository tests/audit documents, temporary quota/checkpoint files, bytecode, and credentials are excluded. Obtain an exact pinned checkout separately; the runner verifies the production dependency blobs before importing source.

Proceed with corrective implementation and independently eligible work. Physical runtime acceptance and affected evidence certification remain open until the remaining contracts and integrated controller gates pass.

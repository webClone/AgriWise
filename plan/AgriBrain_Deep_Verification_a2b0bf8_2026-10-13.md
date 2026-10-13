# AgriBrain production verification — a2b0bf8

Reviewed commit: [`a2b0bf8923ca9f848083fdf702419ade889f3e38`](https://github.com/webClone/AgriWise/commit/a2b0bf8923ca9f848083fdf702419ade889f3e38). Parent: `a7a8a384209fb2986ee371038ca0d1166845112e`. Review date: 13 October 2026. Commit timestamp: 12:32:05 UTC / 13:32:05 Algeria time. GitHub main matched the reviewed SHA at the final source check.

**The original XR01–XR05 counterexamples show the claimed corrections. Four expanded groups remain reproducible: MQTT acknowledgement interpretation, valid zero-depth persistence, first-settlement command identity, and device ownership across independent workers.**

The highest-priority boundaries are SR01 and SR04. A concrete MQTT reply explicitly indicating continued operation can still finalize STOP or completion. Two live OS processes can also start the same device/zone; OLD's duration watchdog then stops NEW while NEW remains durably EXECUTING. Corrective implementation can proceed. Physical runtime acceptance and affected evidence certification should remain open.

## 1. Scope, scientific target, and evidence limits

This commit modifies four production files: irrigation_runtime/dispatcher.py, safety.py, drivers/mqtt_driver.py, and drivers/modbus_driver.py. Its repository tests and repository verification document were excluded as correctness evidence. This review changed no production repository code and did not invoke the repository pytest suite. The user's reported 584 passing tests were not independently rerun.

The review runtime contains 430 production dependency files. Their exact pinned Git blobs were verified, and all parsed successfully with Python's AST parser. The repository tree was retrieved without truncation and contains no AGENTS.md. Source identity and syntax for 430 files do not constitute semantic certification of 430 modules, the entire AgriWise platform, or every AgriBrain capability.

Twenty-one independent drivers produced 172 current-commit JSON groups: 170 behavioral/scientific groups and two import diagnostics. Final executions exited successfully and delivered no harness-error group. They include demonstrated defects, so they are not 172 passing acceptance tests. The evidence verifier deliberately asserts both successful controls and faulty outcomes.

Concrete MQTT methods and callbacks are exercised with local transport substitutes; the callbacks run in the local event-loop thread. Broker-thread delivery, vendor hardware behaviour, and physical field protections are not certified. The device-ownership reproduction uses two spawned OS processes, shared-memory simulated controller state, and the real shared quota store. Both processes remain alive through the stale cutoff, and both exit with code zero. No broker, network controller, driver connect method, or field hardware was operated.

SR02 and SR03 use normal production writer calls; SR02 does not edit ledger bytes. SR03's direct writer fixture establishes an internal data contract, and its second fixture mutates a local event object before ordinary completion. Neither establishes an externally reachable HTTP exploit. SR04 assumes a controller that accepts another START; vendor-side exclusivity or generation fencing could alter a field outcome and was not verified. The demonstrated defect is absence of software ownership enforcement across these workers.

Two earlier harnesses were updated to synchronize only the first admission lookup per thread. The new monitoring code adds more is_active calls; synchronizing every call caused artificial broken barriers. The XR05 fixture now records the expected typed corruption rejection instead of allowing its final diagnostic read to become a harness error. These changes affect independent instrumentation, not production source.

The scientific target is the supplied R3 export `R3_current_scientific_sections.txt`, SHA-256 `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`. Exact relevant requirement-register excerpts accompany the bundle. This review does not recertify all 153 requirements or assert identity with an unseen later monograph revision. SR identifiers are local review IDs, separate from R3 scientific requirements and the master plan's F/T package identities.

## 2. Original XR corrective verification

| Original group | Independent observation at a2b0bf8 | Qualification |
|---|---|---|
| XR01 — no controller ACK / missing publish result | Both original MQTT cases remain STOP_REQUESTED with one owner, one watchdog, and no stopped receipt. | Reply content and current-status decoding remain SR01. |
| XR02 — mapping omission / exception traversal | Zone-only address 77 is attempted. All six original outputs are attempted despite raised write exceptions. Failed responses retain unresolved ownership. | The fixture injects failed transport responses: it verifies attempted coverage, not physical valve closure. |
| XR02 — failed status read means idle | Actual Modbus get_status returns ERROR; completion remains VALIDATING with active ownership and no settlement. | This bounded failed-read case is corrected. |
| XR03 — unknown/wrong-device recovery | Canonical device is queried first. Original adapter cases attempt STOP and stop the simulation; the concrete no-reply MQTT case remains actively STOP_REQUESTED. | Adapter STOP success permits terminalization; it does not prove a real disconnected controller can be stopped. |
| XR03 — reservation phases misattribute activity | Foreign STOP_REQUESTED is protected; unrelated VALIDATING no longer suppresses recovery of running OLD. | These original controls do not establish an authoritative device lease or controller generation. |
| XR04 — lifecycle loses target/delivery | Reserve and reopened settlement retain target 8, delivery/exposure 12. Nullable repeated reopen returns safely. Failed STOP registration followed by successful retry still charges 12 and blocks competing 10 under 20. | Repeated reopen adds journal/timestamp changes; compatibility is verified, not byte-identical replay. Fresh atomic admission remains SR03. |
| XR05 — malformed new fields / inconsistent bounds | Boolean/negative fields and exposure zero below a known 12 mm bound raise CorruptedQuotaStoreError. The inconsistent 8 mm exposure case blocks admission. | A genuinely valid all-zero operation is different and fails through a normal writer: SR02. |

Evidence: `post_nr_probes.py` and `post-nr-results.json`. Older keys retain the hypotheses that motivated them; inspect current values. Earlier NR/ER and sampled runtime/hydraulic controls checked by the verifier also retain their exercised outcomes.

## 3. Remaining findings and R3 mapping

| Finding | Priority | Remaining contract failure | R3 requirements |
|---|---|---|---|
| SR01 | P1 | MQTT STOP accepts contradictory ACK contents; query ignores returned state and can reuse an unrelated old response. | AB-DAT-006/010; AB-ARC-006; AB-EXE-002/004/005 |
| SR02 | P2 | Valid zero-depth reopen publishes a ledger record that its own reader rejects, blocking later admissions. | AB-DAT-005/012; AB-ARC-007/008; AB-EXE-004 |
| SR03 | P2 | Fresh atomic claims omit target identity; first settlement can replace admitted target 8 with caller target 2. | AB-DAT-007/010/011; AB-ARC-008; AB-EXE-003/005 |
| SR04 | P1 | Event-level quota claims and local driver mutexes permit two processes to own one physical device/zone; stale cutoff affects NEW. | AB-DAT-010/012; AB-ARC-008; AB-EXE-002/003/004 |

### SR01 — Waiting for an ACK does not interpret its physical outcome

Sources: [MQTT status callback L190–203](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L190-L203), [query L308–340](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L308-L340), [STOP qualification L391–412](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L391-L412), and dispatcher completion/cutoff guards.

The original no-reply correction is effective. Three expanded cases remain:

1. **Contradictory STOP acknowledgement.** An actual status-topic callback matches the generated request ID and supplies status=OK, stopped=False, running=True. emergency_stop accepts OK, sets cache ONLINE, and returns success. Integrated watchdog handling publishes EMERGENCY_STOPPED, writes a conservative 8 mm stopped receipt, and removes owner/watchdog while the separate simulation remains running. A positive STOPPED/stopped=True/running=False control stops the simulation and finalizes correctly.
2. **Correlated query state is ignored.** get_status awaits the future but does not interpret the returned payload. _handle_status stores the frame and resolves the future without updating _status. With cache ONLINE, matched replies reporting EXECUTING or ERROR, running=True, stopped=False still return ONLINE. In a restored VALIDATING fixture, ordinary complete_event accepts this as idle, publishes COMPLETED, settles measured 80 L over 0.001 ha as 8 mm, and removes ownership while the simulation runs.
3. **No fresh reply with recent old payload.** A prior unrelated status frame gives a recent heartbeat. The current query receives no correlated response, yet its timeout branch returns cached ONLINE because an old payload exists and the heartbeat is recent. Completion again succeeds. The user's broad statement that unconfirmed queries return UNKNOWN is therefore not true for this case.

The frames are accepted through actual production callbacks. Their explicit physical-state fields are not qualified by the code. This review does not assert a particular vendor's undocumented wire schema; the repair must define and decode that schema and reject unsupported or contradictory states.

**Repair.** Introduce one typed decoder for query and command outcomes. Distinguish command receipt/acceptance from confirmed stopped or idle state. Validate explicit contradictions and map supported status fields to ActuatorStatus. Return the state established by the current correlated reply, including operation/generation and observation time where supported. A recent unrelated heartbeat can support connectivity, not confirmation of this query's idle result. Missing or invalid physical-state support remains unknown/unresolved.

**Acceptance.** OK plus running=True/stopped=False retains STOP_REQUESTED and monitoring. Matched EXECUTING/ERROR cannot pass completion. Timeout with a recent old frame cannot certify current idle. Explicit qualified stopped and idle controls still succeed. Preserve original no-ACK and negative-publication controls, and cover vendor schema variants with documented semantics.

Evidence: `mqtt_stop_and_query_ACK_payloads_not_qualified` in `post-xr-results.json`.

### SR02 — Valid zero-depth writer publishes unreadable state

Sources: [exposure scalar validation L251–272](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/safety.py#L251-L272), [reopened record L1476 onward](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/safety.py#L1476), and [store publication L423–449](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/safety.py#L423-L449).

XR05 correctly rejects exposure zero when delivery is known to be 12. Its new scalar check also rejects every explicit effective_exposure_mm <= 0, including a valid zero operation. That contradicts the non-negative contract stated in the remediation and other writer/schema paths.

Two ordinary sequences reserve target zero and reopen: one has no delivery observation, the other previously settled an explicit measured zero. Both reopen calls return normally and publish a record with target=0, exposure=0, and delivery respectively None or 0. The next read raises CorruptedQuotaStoreError for effective_exposure_mm=0. Another valid 1 mm admission is blocked as store corruption. No bytes were externally edited.

The corruption guard fails closed, so this is availability and self-consistency failure, not demonstrated quota fail-open. _write_state serializes and atomically replaces bytes without validating the candidate using the same reader contract, allowing a production writer to create a store the service cannot read.

**Repair.** Accept finite non-negative exposure, including zero when the lower bound is zero. Apply the lower-bound inequality independently of scalar validity. Preserve absent delivery versus measured zero. Validate the complete candidate before publication so any genuinely invalid candidate fails without replacing readable canonical state. Apply the same schema to every writer and reader.

**Acceptance.** Both zero sequences remain readable and keep a durable operation claim without exposure debit. Subsequent eligible admission succeeds. Negative, boolean, non-finite, and below-positive-bound exposure still fail closed. Failed candidate validation must leave prior store bytes and receipts intact.

Evidence: `valid_zero_reopen_publishes_unreadable_quota_store`.

### SR03 — Fresh admission target can be rewritten at first settlement

Sources: [atomic reservation construction L744–759](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/safety.py#L744-L759), [monitor attachment L1729 onward](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/safety.py#L1729), and [settlement target precedence L1129–1141](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/safety.py#L1129-L1141).

Fresh atomic admission records volume_mm=8 but no target_volume_mm. Monitoring now attaches to the existing claim without calling reserve, so the target field is not added later. Settlement uses caller target before legacy reservation volume when that explicit field is absent.

The probe starts a real production event for target 8 and captures the sent START volume 8. A first direct settlement specifying target 2 records canonical target 2, despite durable admitted volume 8. A second fixture lets the controller simulation become idle and the event enter VALIDATING, mutates the local event target to 2, then calls ordinary complete_event. It publishes COMPLETED with the same wrong target 2. Measured delivery and plot debit remain correctly 8; this finding does not claim a quota debit reduction.

Both sequences were also run against the exact parent a7a8a38 runtime. The parent retains target 8 in both receipts, confirming a regression across the new admission/monitoring/settlement combination.

**Repair.** Persist an immutable command envelope at atomic admission, including explicit target identity on every path. Read the authoritative command target from that envelope at first settlement and retry. A differing caller target cannot silently replace it. Legacy fallback must use original admission/journal evidence, especially where historical volume_mm may have represented exposure rather than target. Local event objects and caller_input may carry requests or diagnostics, but cannot define a different canonical command under the same operation identity.

**Acceptance.** An admitted/sent target 8 remains target 8 through first settlement and completion when caller/local objects contain target 2. Either reject the conflict before mutation or preserve canonical identity with a documented outcome. Actual 80 L over 0.001 ha still settles 8. Reopened target-8/delivery-12 controls remain correct. Original target-8 retries remain compatible without new STARTs.

Evidence: `fresh_atomic_claim_settlement_rebinds_command_target`; parent comparison in `parent-target-control.json`.

### SR04 — Two processes can own the same device and zone

Sources: [SharedQuotaStore.atomic_check_and_reserve L468 onward](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/safety.py#L468), the reservation construction above, [local actuator admission L222 onward](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/actuator.py#L222), and [watchdog identity/cutoff L934–1015](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/services/agribrain/irrigation_runtime/dispatcher.py#L934-L1015).

The quota transaction protects budgets and same-event identity. It does not atomically establish exclusive ownership for a physical device/zone across different event IDs. The actuator's dispatch mutex and active command are local to its instance. A worker's local OLD command can therefore appear to be the current owner after another worker has started NEW.

The deterministic OS-process sequence is:

| Step | Shared physical simulation | Durable/local result |
|---|---|---|
| OLD worker starts target 1 for one minute | OLD running; START count 1 | OLD EXECUTING |
| NEW worker starts target 1 for twenty minutes on the same device/zone | NEW running; START count 2 | OLD and NEW both durably EXECUTING |
| OLD worker clock advances to 61 s | OLD watchdog sends one STOP; NEW stops | OLD EMERGENCY_STOPPED; NEW durable record still EXECUTING |

Both admissions use a positive 10 mm budget; aggregate 2 mm is within it. This is not plot-budget overcommit. Both processes are alive through cutoff and have different PIDs; final exit codes are [0,0]. A single-adapter control makes only one physical START; its NEW request remains STOP_REQUESTED after the local guard, rather than starting NEW.

The simulated controller accepts a later START and reports device activity without an operation-specific receipt, matching a supported degraded capability. No vendor device's exclusivity or takeover protections are assumed. The failed invariant is software ownership agreement and stale cutoff attribution, not proof that every physical controller will permit this takeover.

**Repair.** Add atomic physical-resource ownership alongside event identity and quota admission. Scope it to the actual device/zone conflict policy, including explicit multi-zone capabilities. Bind owner event, operation, generation, and unresolved transport/stop state. A new conflicting operation must not dispatch while the incumbent is unresolved. Require reconciliation before handoff; a lease timeout alone cannot prove the old operation stopped.

Carry and enforce generation fencing through capable controllers or a serialized actuator gateway. For legacy controllers without operation fencing, use a single authoritative transport owner and resolve queued/in-flight effects before handoff. A store-generation check followed by an unfenced network send is insufficient if an old STOP can arrive after NEW starts. Keep device/global emergency hazards able to stop intended outputs independently of stale event-duration ownership.

**Acceptance.** Two actual workers requesting the same conflict scope yield at most one START while an incumbent is live/unresolved. Same-event retries still join; independent permitted resources can still run concurrently. Restart, expired lease, delayed ACK/STOP, stale watchdog, and handoff cannot let OLD silently stop NEW or leave NEW falsely EXECUTING. Existing global/device interlock protections must remain effective.

Evidence: `actual_two_process_same_device_zone_admission_and_stale_cutoff`.

## 4. Corrective implementation sequence

| Order | Work | Completion gate |
|---|---|---|
| 1 | Define and implement MQTT status/outcome decoding with correlation, freshness, contradiction handling, and supported vendor schemas. | SR01 accepted replies establish the returned state; unqualified replies cannot finalize. |
| 2 | Add authoritative device/zone ownership, safe handoff, and controller/gateway fencing. Integrate all admission, restart, cancellation, watchdog, and emergency paths. | SR04 actual two-process and late-transport cases have one consistent owner and outcome. |
| 3 | Centralize immutable admission envelope, measured outcome, and exposure schema. Correct fresh settlement precedence and legacy migration. | Target 8 cannot become 2; target 8/delivery 12/exposure at least 12 remain distinct. |
| 4 | Align zero/null contracts and validate candidates before durable publication. | Valid zero states remain readable; invalid candidates preserve prior canonical state. |
| 5 | Run integrated concrete-driver and multi-worker scenarios, followed by designated hardware acceptance. | Software, controller, measurements, accounting, and operation generation agree. |

Retain the corrected XR/NR/ER controls while replacing SR faulty-outcome assertions with the acceptance results after repair. Adding another callback, lookup, or field fallback alone will not establish the missing shared contracts.

For the monograph's agronomic/economic/data-science target, these distinctions protect management timing, intervention response, hydraulic forcing, water cost, and training/evaluation labels. For example, rewriting an actual target 8/delivery 8 to target 2 makes delivery/target appear 4 instead of 1. Those downstream implications are inferences from R3; this review directly reproduces the runtime and record failures, not every downstream model consequence.

Independently eligible Omega/world-model work may continue. Affected management records require qualified current outcome, immutable command identity, support, and chronology before certification as labels or rollout targets.

## 5. Hydraulic controls and milestone state

The sampled hydraulic process-publication control still produces equal warm/cold profiles, top-layer VWC 0.2124, and durable publication generation 4 after a foreign historical correction. The scheduled hydration/CAS control preserves the winning RAM state and durable head. These bounded checks do not close F08/F09 or certify all replay behaviour.

Task-register blob: `8a564647af7e588802537817159117b349ff606b`. All six full-acceptance entries remain open:

| Ticket | Line | State |
|---|---:|---|
| ST03-F08-FA | 406 | `[ ]` |
| ST03-F09-FA | 443 | `[ ]` |
| ST06-F16-FA | 796 | `[ ]` |
| ST06-F17-FA | 833 | `[ ]` |
| ST06-F18-FA | 870 | `[ ]` |
| ST06-F19-FA | 907 | `[ ]` |

[Pinned task register](https://github.com/webClone/AgriWise/blob/a2b0bf8923ca9f848083fdf702419ade889f3e38/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md). Checkbox state establishes planning status, not correctness.

## 6. Source identity and reproduction bundle

| Production path under services/agribrain/irrigation_runtime/ | Git blob |
|---|---|
| dispatcher.py | `4e49f511bf6c39f7ec8fdbbd91d15c2fb9c287f0` |
| safety.py | `e9ffdd90a8e51497af7319f8ba63a9292f62787e` |
| drivers/mqtt_driver.py | `8b854f0f9bb4224213da86592b6fa08cc6823196` |
| drivers/modbus_driver.py | `ff9c41d6d8337e2e6b719acb386db1ac2f1c759b` |
| actuator.py | `2a90b1336ec3fe51cf250872dc7607f6b75e59dd` |
| schemas.py | `2136a933f83ced4ee0a17fbce34ac70473098eac` |

The companion ZIP contains 21 independent drivers, observations/logs, the exact 430-file integrity manifest, sanitized commit metadata, production-only diff, relevant R3 register excerpts, parent target-identity comparison, evidence verifier, runner, and checksums. Runtime source copies, repository tests/audits, temporary ledgers/checkpoints, bytecode, credentials, and saving helpers are excluded. Use an exact pinned checkout separately; the runner verifies source identity before importing code.

Proceed with corrective implementation, prioritizing SR01 and SR04. Keep the six milestones open until their respective integrated acceptance criteria are met.

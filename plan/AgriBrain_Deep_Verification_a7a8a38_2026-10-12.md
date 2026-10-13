# AgriBrain production verification — a7a8a38

Reviewed commit: [`a7a8a384209fb2986ee371038ca0d1166845112e`](https://github.com/webClone/AgriWise/commit/a7a8a384209fb2986ee371038ca0d1166845112e). Parent: `28c7c46ef69031c6482db7f5a6afbf93fbe1e288`. Review date: 12 October 2026. Commit timestamp: 18:14:24 UTC / 19:14:24 Algeria time. GitHub main matched the reviewed SHA at the final source check.

**The original NR01–NR04 counterexamples now show the claimed corrections. Five expanded production contract groups remain reproducible. Corrective implementation can proceed; physical runtime acceptance and affected evidence certification should remain open.**

The most consequential new accounting result uses ordinary production recovery calls: known measured delivery of 12 mm becomes an 8 mm stopped charge after failed STOP recovery and a successful retry. A competing 10 mm operation is admitted under a 20 mm budget, although known prior delivery plus the new request is 22 mm. No ledger corruption injection is needed for this chain.

## 1. Scope, provenance, and limits

This commit modifies four production files: dispatcher.py, safety.py, mqtt_driver.py, and modbus_driver.py. Repository tests and repository verification/audit documents were excluded as correctness evidence. This review changed no production repository code and did not invoke the repository pytest suite. The reported 579 passing tests were not independently rerun.

The review runtime contains 430 production dependency files. Each was verified against its exact pinned Git blob and parsed successfully with Python's AST parser. The repository tree was retrieved without truncation and contained no AGENTS.md. The 430-file verification establishes source identity and syntax for that set, not semantic certification of the entire AgriWise platform or all AgriBrain capabilities.

Twenty independent drivers produced 168 named JSON groups: 166 behavioral/scientific groups and two import diagnostics. Final driver executions exited successfully, with no harness-error group in the delivered observations. These are evidence groups containing both correct controls and defects, not 168 passing production acceptance tests. The evidence verifier asserts the observed defects deliberately.

The probes exercise actual production dispatcher/store functions and concrete MQTT/Modbus methods. Local transport substitutes return controlled publication/write/read outcomes. No driver connect method, broker, network controller, or physical field hardware was operated. The existing worker/crash fixtures include real OS-process separation with simulated controllers. Their intentionally terminated sender is fault injection, not an uncontrolled crash of this review.

XR05 is specifically a local ledger-corruption fixture: it edits finite JSON fields to test fail-closed validation. It does not establish an externally reachable write/API exploit. XR04's admission failure is independent of that corruption fixture and occurs through normal production calls.

The scientific target is the supplied R3 export `R3_current_scientific_sections.txt`, SHA-256 `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`. Exact relevant requirement-register excerpts accompany the evidence. This is not a recertification of all 153 requirements or an assertion about an unseen later monograph revision. XR identifiers below are review-local; they are separate from R3 requirement IDs and the master plan's F/T package IDs.

## 2. NR01–NR04: original corrective verification

| Claim | Independent observation at a7a8a38 | Qualification |
|---|---|---|
| NR01 — refresh status instead of trusting cache | All four original ONLINE/UNKNOWN/OFFLINE/EXECUTING cache cases query the production-shaped adapter once and stop the simulated OLD operation. | Concrete driver freshness, unavailable status, and canonical device binding remain XR03. |
| NR01 — stopped OLD does not preempt NEW | Both original cases, with and without local NEW command metadata, send zero STOPs, keep NEW executing, and leave OLD terminal/inactive. | Presence of an arbitrary reservation phase does not itself qualify current physical ownership; see XR03. |
| NR02 — target versus delivery/exposure | Reopened record contains target 8, delivery 12, and exposure 12. Original 8 mm retry joins STOP_REQUESTED with zero extra STARTs; cold stopped recovery retains target 8/delivery 12. | Other lifecycle writers erase or reinterpret the new fields: XR04. |
| NR03 — negative concrete transport outcomes | Failed MQTT publications and negative Modbus coil responses retain STOP_REQUESTED, one active owner, one watchdog, and no premature stopped receipt. | Accepted/unqualified MQTT results still finalize without controller outcome; Modbus mapping and read failures remain XR01/XR02. |
| NR04 — terminal reserve retry | Compatible reserve retry preserves the completed receipt; duplicate submission returns COMPLETED with zero STARTs. A second 4 mm operation is admitted under a 10 mm budget. | The observed final 4 mm reservation belongs to SECOND, not phantom exposure for E. |

Evidence: `post_er_probes.py` and `post-er-results.json`. Older JSON keys describe the original hypotheses; the current values establish correction. Prior ER/RC/BV/PB/RP controls covered by the verifier also retain their exercised corrections.

## 3. Remaining finding register

P1 denotes a reproduced operational authority, recovery, or quota-conservation boundary requiring repair before the affected acceptance. Subcases limited to false retry rejection or historical target identity are P2 within XR04. XR05's P1 consequence requires a damaged local ledger, explicitly qualified below.

| Finding | Priority | Remaining defect | Relevant R3 requirements |
|---|---|---|---|
| XR01 | P1 | MQTT accepted/missing publication results still become confirmed physical STOP. | AB-DAT-006/010; AB-ARC-006; AB-EXE-002/004/005 |
| XR02 | P1 | Modbus omits configured zone outputs, aborts later outputs on one exception, and converts failed status reads into idle. | AB-DAT-005/006/010; AB-ARC-006; AB-EXE-002/004/005 |
| XR03 | P1 | Restart recovery still promotes unavailable/stale or wrong-device evidence and guesses ownership from reservation phases. | AB-DAT-010/012; AB-ARC-006/008; AB-EXE-002/003/004 |
| XR04 | P1/P2 | New target/delivery/exposure fields do not survive reserve, settlement, repeated reopen, and failed-STOP recovery. | AB-DAT-003/007/010/011/012; AB-ARC-007/008; AB-EXE-003/004/005 |
| XR05 | P1 under ledger corruption | New reservation fields and exposure bounds are not validated; inconsistent damaged state is admitted. | AB-DAT-005/010/012; AB-ARC-006/007; AB-EXE-004 |

### XR01 — Publication acceptance still means physical STOP

Source: [mqtt_driver.py L324–379](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L324-L379), with [dispatcher cutoff finalization L1007 onward](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/dispatcher.py#L1007).

The negative-return correction is effective. However, `emergency_stop()` still returns success immediately when either publish result has rc zero. It does not await a controller ACK or a qualified current stopped outcome. A missing publish-result object also becomes rc zero through `getattr(result, "rc", 0)`.

In the probe, an operation is acknowledged and running in a separate simulated controller state. At clock 601 s for a 600 s operation, the concrete MQTT function is substituted into the real dispatcher. Both publications return queue-accepted rc zero, but no controller ACK arrives and no STOP is applied. The dispatcher publishes EMERGENCY_STOPPED, makes the driver cache ONLINE, records a stopped receipt, and removes the owner/watchdog. The controller simulation remains running. Repeating with no publication-result object produces the same outcome.

This is the accepted-but-unresolved send case, not a recurrence of the now-fixed negative-publish case. The existing conservative 8 mm stopped charge remains; the failure is physical outcome authority and recovery monitoring.

**Repair.** Separate emergency transmission acceptance from confirmed stopped outcome. Keep immediate sending, but preserve STOP_REQUESTED and deadline/exposure while awaiting operation-bound controller confirmation. Unknown/missing publication results cannot supply success authority. Use request/operation/generation correlation; broker acknowledgement alone cannot certify the operation stopped.

**Acceptance.** Queue acceptance without controller reply retains ownership and retry monitoring. Missing result, negative result, disconnect, timeout, and delayed ACK are explicit states. A qualified same-operation stopped response may finalize. A response from another generation cannot finalize this one. Preserve the corrected negative-result controls.

Evidence: `mqtt_accepted_or_unqualified_send_finalizes_running_operation`.

### XR02 — Modbus output coverage and missing status still fail

Sources: [zone mapping and START L304 onward](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/drivers/modbus_driver.py#L304), [status L445–485](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/drivers/modbus_driver.py#L445-L485), and [emergency STOP L487–545](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/drivers/modbus_driver.py#L487-L545).

Three bounded cases remain:

1. **Zone-map omission.** A supported configuration supplies `zone_coil_map={"zone":77}` and an empty generic coil_map. START/STOP_ZONE use the zone mapping, but emergency_stop only scans the generic coil map. It makes zero writes and returns success. Integrated watchdog processing publishes EMERGENCY_STOPPED and removes monitoring while the simulation runs. An empty required-output set must not certify cutoff.
2. **First exception aborts the rest.** A raised transport exception on emergency-stop coil 9 exits one outer try block. No valve or pump output is attempted. The dispatcher correctly retains STOP_REQUESTED/owner/watchdog; output traversal is still incomplete. Repeated attempts can repeatedly fail at the same first output without reaching independent outputs.
3. **Failed reads become idle.** Negative input-register responses produce empty status data. get_status defaults missing fault_code and status_word to zero, then reports ONLINE. In a restored VALIDATING fixture with a genuinely acknowledged simulated START still running, complete_event accepts that status, settles 80 L over 0.001 ha as 8 mm, publishes COMPLETED, and drops active ownership. No valid status observation established idle.

The third fixture uses actual Modbus read/status functions and a separate controller simulation, not a literal assertion standing in for physical state. It starts through the real dispatcher, restores the validation phase, then exercises completion with failed register responses. No field protections are inferred.

**Repair.** Build the required cutoff output set from both mapping sources and actuator capabilities. Validate configuration before operation admission. Deduplicate equivalent addresses, qualify every required write, and isolate exceptions per output so other outputs are still attempted. Report partial coverage explicitly. Require valid current status-word data; missing/error responses remain unknown/error and cannot be laundered into zero-running/zero-fault observations.

**Acceptance.** A zone mapped only through zone_coil_map receives cutoff. An individual failed output does not prevent other required outputs from being attempted. Empty/invalid configuration cannot produce successful cutoff. Failed/missing status reads cannot pass the current-idle completion guard. Valid idle and running register controls must remain distinct.

Evidence: `modbus_cutoff_coverage_and_failed_status_read`.

### XR03 — Recovery evidence is queried but not consistently qualified

Sources: [dispatcher stopped-receipt branch L1488–1558](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/dispatcher.py#L1488-L1558), canonical hydration immediately afterward, and [MQTT status L308–322](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L308-L322).

The original fresh-query cases are corrected. The query result and scope still have these failures:

| Fixture | Observed result |
|---|---|
| Query raises; no public running flag; cache ONLINE | CANCELLED, zero STOPs/owners/watchdogs; simulation continues running. |
| Live result OFFLINE or UNKNOWN | Same terminal result; unavailable evidence is treated as absence of running activity. |
| Snapshot device ID differs from canonical stopped receipt | Queries the snapshot's idle device, then restores canonical device afterward. Zero canonical-device queries/STOPs; canonical controller continues running. |
| Concrete MQTT get_status receives no reply | Publishes QUERY_STATUS, waits its fixed delay, returns cached ONLINE, and leaves OLD CANCELLED/unmonitored while simulation runs. |
| Other reservation is VALIDATING; actual operation is OLD | Reservation presence is labeled a confirmed foreign owner; OLD is left terminal and running. |
| Other reservation is STOP_REQUESTED; actual operation is NEW | That phase is omitted from the scan; activity is attributed to OLD, one STOP is sent, and OLD accounting is updated while NEW remains durably STOP_REQUESTED. |

The STOP_REQUESTED example demonstrates wrong attribution/accounting, not an assertion that stopping an operation which already requested STOP is inherently undesired. The VALIDATING example demonstrates that an accounting phase alone is not proof of current physical ownership. These are controlled separate-worker views with no local command identity; the originally qualified NEW controls remain correct.

**Repair.** Hydrate immutable canonical device/scope before any controller lookup or query. Return an observation carrying request correlation, timestamp/freshness, status support, and operation identity rather than a cache-only enum. Distinguish confirmed idle, confirmed same operation, confirmed foreign operation, and unresolved identity/status. Include all unresolved phases in device ownership reconciliation, but do not call mere reservation presence a confirmed physical identity. Query failure must preserve a reconciliation obligation without blindly preempting a qualified different operation.

**Acceptance.** Wrong caller device cannot redirect recovery qualification. Missing/offline/stale/no-response status cannot certify stopped or idle. Same-operation contradictions are recovered with original exposure and deadline. Qualified NEW remains protected. Conflicting/absent identities and all active phases have explicit unresolved outcomes and accounting ownership. Use concrete driver functions as well as interface-shaped adapters.

Evidence: `stopped_recovery_uncertainty_scope_and_phase_identity`.

### XR04 — The new schema does not survive the lifecycle

Sources: [reserve L833–866](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/safety.py#L833-L866), [settle target selection L1080](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/safety.py#L1080), [reopen L1391–1439](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/safety.py#L1391-L1439), and [watchdog registration L1642–1689](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/safety.py#L1642-L1689).

The original reopened record now correctly separates target 8, delivery 12, and effective exposure 12. Four transitions break that distinction:

- reserve reconstructs an existing reservation using volume_mm while dropping target_volume_mm, delivered_volume_mm, and effective_exposure_mm. Original target-8 retry then fails against active 12, with zero duplicate STARTs.
- settle selects canonical target from existing_res.volume_mm rather than existing_res.target_volume_mm. Re-settlement after reopen records target 12 even though caller_input retains target 8.
- A first reopen without measurement writes delivered_volume_mm=None. A second reopen evaluates float(None), raising TypeError. Store bytes stay unchanged, but a compatible recovery retry fails.
- Failed-STOP restart recovery registers its watchdog through reserve, erasing the measured-delivery lower bound. A later successful STOP records only target 8. Known delivery 12 is reduced to an 8 mm debit; a competing 10 mm START is admitted under budget 20.

The last fixture establishes a qualified durable original actual_start before reboot, avoiding ambiguity about unresolved pending dispatch. The first STOP returns failure, the next STOP succeeds, and a separate device submits the competing event. This is ordinary production call flow with intact local ledger bytes.

For 0.001 ha support, measured 120 L is 12 mm:

\[
I_{measured}=\frac{120}{10000\times0.001}=12\ \mathrm{mm}.
\]

\[
I_{target}=8,\quad I_{measured}=12,\quad E\geq12;\qquad12+10=22>20.
\]

The faulty stopped projection uses 8+10=18, enabling admission. This is a direct conservation failure, in addition to the P2 historical-target and false-retry failures.

**Repair.** Use one typed reservation/operation schema across every writer and reader. Preserve immutable command target separately from measured outcome and conservative exposure. Watchdog registration should attach monitoring to an existing canonical claim rather than reconstruct its scientific/accounting fields. Settlement must read commanded target, not exposure. Nullable observations stay nullable; reopening without a measurement is an idempotent transition, not float(None). Cancellation, global cutoff, failed fence, restart, and terminal reconciliation must carry the known qualified lower bound.

**Acceptance.** Target 8/delivery 12/exposure at least 12 survives each writer, repeated registration, failed STOP, successful retry, restart, and settlement. Original target-8 retries remain compatible without another START. The exact recovery chain must block competing 10 under 20. Receipts and intervention metrics retain target 8 versus measured 12. Missing measurement remains missing while conservative exposure remains protected.

Evidence: `target_delivery_exposure_lost_across_other_writers`.

### XR05 — New fields bypass established ledger validation

Sources: [reservation validation L234–254](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/safety.py#L234-L254), [atomic budget projection L656 onward](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/safety.py#L656), and [reserved exposure projection L1439–1449](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/services/agribrain/irrigation_runtime/safety.py#L1439-L1449).

Reservation validation checks the legacy volume/duration/flow/area fields, but not the newly introduced target_volume_mm, delivered_volume_mm, or effective_exposure_mm and their mutual constraints.

Controlled ledger-file edits show that target=True, delivery=−5, exposure=−1, and exposure=0 are accepted on read. get_reserved even returns −1 for the negative exposure fixture. No non-finite JSON extension is needed for these examples.

An inconsistent record retaining measured 12 and target 8 but shrinking both volume_mm and effective_exposure_mm to 8 also passes validation. Atomic admission accepts another 10 under budget 20; known measured 12 plus requested 10 is 22. Atomic admission sums volume_mm, while get_reserved reads effective_exposure_mm, allowing differing projections if those aliases diverge.

These cases require a damaged local ledger. They establish missing integrity checks, not an unauthenticated production writer or HTTP exploitation path.

**Repair.** Validate every canonical reservation field with its nullable/finite/nonnegative contract. Enforce exposure at least max(commanded target, qualified delivered lower bound), and define or remove duplicate volume aliases. Readers and atomic admission must use the same exposure projection. Validate before publishing and after reading; reject incompatible schema/state before any new dispatch. Add versioned migration for legacy entries whose target and exposure were conflated, using immutable admission/journal evidence where available.

**Acceptance.** Invalid scalars and inconsistent bounds raise the typed corruption error and block new admission. Both atomic and monitoring projections agree. Legacy records migrate without inventing measured zero or discarding known delivery. Valid target-8/measured-12 records still reserve at least 12.

Evidence: `new_reservation_fields_unvalidated_and_exposure_inconsistent`.

## 4. Coherent corrective implementation plan

The repeated boundaries share a cause: callers assign different meanings to status enums, success booleans, and volume_mm. Implement the contracts centrally and migrate all callers together.

| Stage | Concrete work | Required completion evidence |
|---|---|---|
| 1 | Define controller observation/result authority: request, operation/generation, current status, freshness, transport acceptance, confirmed outcome, and unknown. Apply it to MQTT/Modbus and dispatcher completion/cutoff. | Accepted send cannot finalize; failed reads cannot mean idle; qualified current outcome can finalize. |
| 2 | Repair Modbus required-output coverage and per-output exception isolation. Validate device configuration before admission. | Zone-map-only cutoff reaches address 77; first-output failure still attempts independent valves/pump; partial outcomes remain unresolved. |
| 3 | Centralize canonical operation hydration and recovery identity resolution before driver access. | Wrong-device snapshot cannot influence lookup; unavailable observations retain reconciliation; qualified foreign owner remains protected across every phase. |
| 4 | Introduce one versioned ledger schema/transition layer separating target, qualified delivery, exposure, and monitoring metadata. Migrate reserve/reopen/settle/stopped/registration paths together. | All XR04 sequences preserve target 8/delivery 12 and block excess admission; repeated missing-measurement reopen is idempotent. |
| 5 | Enforce schema and conservation validation on all writes/reads and unify quota projections. | All XR05 corrupt states fail closed; intact legacy/current records remain readable and correctly charged. |
| 6 | Run integrated concrete-driver, delayed-ACK, worker-restart, receipt-correction, and configured-output scenarios, then designated hardware acceptance. | Local/durable/controller/measurement/accounting states agree for the same operation generation. |

Keep successful NR/ER controls while replacing each faulty-outcome assertion with its acceptance criterion after repair. A verifier asserting the current counterexamples is evidence consistency, not remediation acceptance. Do not close a package because one narrow fixture passes while another normal transition violates the same invariant.

The scientific implications are inferences from R3: losing 12 mm delivery to an 8 mm record can distort management forcing, hydraulic memory, intervention response, water cost, and training/rollout eligibility. This review directly proves the runtime/accounting defects; it does not claim to have reproduced every downstream agronomic or ML consequence.

Independently eligible Omega/world-model research can continue. Affected intervention records require qualified outcome, support, chronology, and retained measurements before use as certified training labels or evaluation targets.

## 5. Hydraulic controls and acceptance milestones

The existing independent hydraulic process-publication control still gives identical warm/cold profiles, top-layer VWC 0.2124, and durable publication generation 4 after a foreign historical correction. The scheduled RAM hydration/CAS control preserves the winning state/head. These bounded controls do not close F08/F09 or certify all replay behavior.

The unchanged task-register blob is `8a564647af7e588802537817159117b349ff606b`. All six entries remain open:

| Ticket | Line | State |
|---|---:|---|
| ST03-F08-FA | 406 | `[ ]` |
| ST03-F09-FA | 443 | `[ ]` |
| ST06-F16-FA | 796 | `[ ]` |
| ST06-F17-FA | 833 | `[ ]` |
| ST06-F18-FA | 870 | `[ ]` |
| ST06-F19-FA | 907 | `[ ]` |

[Pinned task register](https://github.com/webClone/AgriWise/blob/a7a8a384209fb2986ee371038ca0d1166845112e/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md). Its checkboxes establish planning state, not implementation correctness.

## 6. Source identity and delivered reproduction

| Production path under services/agribrain/irrigation_runtime/ | Git blob |
|---|---|
| dispatcher.py | `055acb47178f7dc6a1a6129e9a08967e1c572c8b` |
| safety.py | `2d996cd4ad9a6390e50b32bf2ba6b6a4bff8c33a` |
| drivers/mqtt_driver.py | `765b9e9077b4f6fd503e32013cb53309fc27026c` |
| drivers/modbus_driver.py | `4881614ec7f5112d8c6639b0ee2edffe8db608da` |

The companion bundle includes 20 independent drivers, recorded observations/logs, a 430-file source manifest, sanitized commit metadata, production-only diff, exact relevant R3 excerpts, verifier, runner, and checksums. Obtain an exact pinned checkout separately; the runner verifies the dependency blobs before importing production code. Source copies, repository tests/audit documents, temporary ledgers/checkpoints, bytecode, credentials, and upload helpers are excluded.

Proceed with the corrective stages above. Keep physical-operation full acceptance and affected scientific evidence certification open until these contracts and the designated integrated controller gates pass.

# AgriBrain production verification — 19fdb67

Review date: 11 October 2026. Reviewed commit: [`19fdb677c626b1d8b5430ab7b81e7376fdbb8b99`](https://github.com/webClone/AgriWise/commit/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99). Parent: `16b470f900af4cfd69ebed140cfc09f29eedd69d`.

The six original BV01–BV06 counterexamples are corrected in the independent reproductions. Seven adjacent contract groups remain reproducible. Four concern physical command ownership, safety cutoff, or conservative exposure; three concern support qualification, settlement retry identity, or contradictory measurements. The remediation batch should not be treated as full runtime acceptance.

Continue corrective implementation and independent work whose prerequisites permit it. Keep physical-operation acceptance open until the command, accounting, and recovery paths satisfy the gates below. This review does not authorize or perform field operation.

## 1. Scope and evidence qualifications

GitHub `main` was checked at the reviewed SHA. The commit changes two production Python files: `irrigation_runtime/dispatcher.py` and `irrigation_runtime/safety.py`. The corresponding test addition and repository verification document were excluded as correctness evidence. No repository source was edited, no repository pytest suite was invoked, and no field hardware was operated.

The runtime contains 430 production Python dependency files, all verified against their Git blob identities at this commit and parsed successfully with Python's AST parser. This verifies source integrity and syntax for that dependency set. It is not a semantic certification of 430 modules or of the entire AgriWise application.

Sixteen independent drivers produced 143 named JSON result groups: 141 behavioral/scientific groups and two import diagnostic groups. All drivers completed with exit code zero, with no result named `harness_error`. These groups contain both correct behavior and demonstrated defects. They are not 143 passing acceptance tests. The additional post-BV driver was executed twice; its reported boundary failures reproduced on both executions. The evidence verifier checks that the observations support this report, including observations of faulty behavior.

The pending START and operation-handoff reproductions use two independent dispatcher/monitor instances in one asyncio process, with a controlled simulated driver. They establish cross-worker logic failures under a scheduled interleaving; they do not establish hardware behavior or full multi-process hardware acceptance. Separate existing drivers exercise actual OS-process quota and hydraulic publication boundaries. Direct store probes establish internal writer contracts, without asserting an externally reachable HTTP exploit.

The scientific target is the supplied R3 export `R3_current_scientific_sections.txt`, SHA-256 `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`. The bundle includes the exact relevant requirement-register excerpts. This comparison uses that supplied target; it does not claim a fresh certification of all 153 R3 requirements or identity with an unseen later monograph revision.

The user's reported 551 pytest passes remain a reported result, independently of this review. They were not rerun or used to override production counterexamples.

## 2. Original BV claim verification

| Claim | Independent production result | Qualification |
|---|---|---|
| BV01 — protect another live operation during poll/restart | Recovering OLD while NEW owns the actuator adds zero STOPs; NEW remains running. EXECUTING and STOP_REQUESTED snapshots are both covered. | Cancellation and device-level interlock purpose remain separate failures, PB02/PB03. |
| BV02 — current positive idle confirmation before completion | Healthy idle settles 4 mm. Running, query exception, OFFLINE, and missing registry retain VALIDATING, 8 mm reservation, and active ownership. | Idle can coexist with a pending START; PB01 covers that interleaving. |
| BV03 — strict writer area scalar validation | Direct `reserve`, `reopen_active`, and atomic admission reject negative, zero, boolean, string, NaN, and infinite area; store bytes remain unchanged and subsequent reads succeed. Positive and absent-area controls remain readable. | The dispatcher cleans invalid raw area into `None` before these writers see it: PB04. |
| BV04 — canonical active envelope/support | Existing active reservations retain 8 mm, duration 10 min, flow 10 L/min, and area 1 ha despite conflicting caller values. A second 8 mm request fails the 10 mm budget. Restart preserves canonical missing area. First settlement uses canonical target, support, device/zone, and period. | Stopped-only reopening does not apply the same binding: PB05. Canonicalization and retry comparison disagree: PB06. |
| BV05 — failed ACK publication deadline | With ACK-start publication deliberately failed and 661 s elapsed for a 600 s operation, recovery uses the older dispatch bound, issues one STOP, and stops the simulation. | The dispatch timestamp is a conservative deadline bound, not an observed physical-start measurement. Preserve that provenance distinction. |
| BV06 — terminal delivery hydration | A stale completed snapshot recovers 40,000 L and 6 min from the canonical receipt, adds zero STOPs, and retains the 4 mm outcome. | This verifies the settled-receipt case exercised by the original probe; it is not universal certification of every terminal field. |

Evidence: `remaining_contract_probes.py` and `remaining-contract-results.json`. Historical result keys retain their original hypothesis names; their current values, rather than their names, determine the conclusions.

## 3. Remaining findings

Priority P1 means a demonstrated command-safety or conservative-exposure failure requiring repair before physical-operation acceptance. P2 means a demonstrated scientific/accounting contract failure requiring repair before the affected results are certified. Finding IDs PB01–PB07 belong to this review; they are not monograph requirement IDs or replacements for master-plan F/T packages.

| ID | Priority | Remaining failure | R3 target |
|---|---|---|---|
| PB01 | P1 | Completion consumes exposure while a START remains pending; late START executes behind a terminal receipt. | AB-ARC-007/008; AB-DAT-010; AB-EXE-002/003/004 |
| PB02 | P1 | Cancelling OLD physically stops a different live NEW operation. | AB-ARC-008; AB-EXE-003/004 |
| PB03 | P1 | The stale-event guard suppresses a device pressure safety STOP, even when the violation identifies NEW. | AB-ARC-006; AB-EXE-004 |
| PB04 | P2 | Invalid area is converted to missing support before admission, allowing START. | AB-DAT-005/007; AB-EXE-005 |
| PB05 | P1 | Stopped-only reopening can shrink exposure, alter support, and rebind plot into an unreadable ledger. | AB-DAT-003/010/011/013; AB-ARC-007/008; AB-EXE-004 |
| PB06 | P2 | First settlement accepts normalization that the identical retry then rejects. | AB-ARC-008; AB-DAT-007/011; AB-EXE-003 |
| PB07 | P2 | Direct settlement certifies 8 mm alongside explicit measured 0 L. | AB-DAT-005/007/010; AB-EXE-005 |

### PB01 — Pending START can outlive terminal settlement

Production locations: [restart idle branch, dispatcher.py L1486–1492](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/services/agribrain/irrigation_runtime/dispatcher.py#L1486-L1492), [completion guards L956–977](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/services/agribrain/irrigation_runtime/dispatcher.py#L956-L977), and [late ACK publication L568–576](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/services/agribrain/irrigation_runtime/dispatcher.py#L568-L576).

Worker A reserves 8 mm under a 10 mm budget and enters START dispatch. The driver holds the send before application/ACK, so the controller truthfully reports idle while `_pending_command` still names E. Worker B recovers the store's DISPATCHING E, converts it to VALIDATING, then accepts explicit 0 L/0 min. The durable record becomes COMPLETED and reservation becomes zero.

When the held send is released, the simulated START executes. A returns EXECUTING, while B and the durable receipt remain COMPLETED. There is one START, zero STOPs, physical simulation running, reserved depth 0, and settled depth 0. A subsequent independent 8 mm request is admitted; both drivers are running, with 16 mm of commanded exposure against the 10 mm budget while the ledger reserves only 8 mm. This is an exposure/admission result, not a claim that 16 mm was measured as delivered.

Current idle confirmation establishes present controller state. It does not resolve a previously admitted command still capable of arriving. Completion must reconcile transport/operation uncertainty before publishing a terminal outcome or consuming its exposure.

**Repair:** Persist command ownership/generation and pending-send identity under the same operation admission contract. Require a qualified operation outcome or successful cancellation/fence of the pending send before settlement. Check the durable operation generation after ACK before promoting a local event to EXECUTING. A local `_pending_command` check is useful but insufficient across independent processes; controller receipts or an equivalent qualified reconciliation boundary are needed.

**Acceptance:** During every paused-send/late-ACK interleaving, either E retains unresolved exposure and cannot complete, or a confirmed fence prevents its subsequent execution. No physical execution may coexist with a zero-exposure terminal receipt. Repeating the second admission must respect the original conservative exposure.

Evidence key: `pending_START_can_complete_then_run`.

### PB02 — Cancellation does not preserve operation identity

Production location: [dispatcher.py L1072–1093](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/services/agribrain/irrigation_runtime/dispatcher.py#L1072-L1093). The unchanged actuator direct-stop path accepts STOP without checking the live source event.

OLD finishes on the controller between owner polls. A different dispatcher admits NEW on the same device/zone. Cancelling OLD then dispatches one STOP_ZONE and stops NEW. OLD returns CANCELLED, while NEW's local event and durable reservation still say EXECUTING. The matching-operation control also sends one STOP and stops its own event, as expected.

The BV01 poll/restart checks do not cover this public dispatcher method. An event-specific cancellation must identify and fence that operation; it cannot use an unqualified device STOP when the device has a different confirmed owner.

**Repair:** Apply operation identity and generation fencing at the shared command boundary, including `cancel_event` and direct actuator stops used for event cancellation. Distinguish event-scoped cancellation from device/global safety cutoff. Where the controller cannot target an old operation, reconcile OLD's unresolved exposure without cancelling a different qualified live operation.

**Acceptance:** Cancelling OLD after NEW takes ownership adds zero STOPs to NEW and leaves its local/durable/physical state consistent. Cancelling the actual owner still stops it. Pending cancellation and failed STOP must retain their conservative exposure and late-ACK fence behavior.

Evidence key: `cancel_event_stops_different_live_operation`.

### PB03 — Device interlock cutoff is suppressed by the stale-event guard

Production locations: [dispatcher.py L802–833](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/services/agribrain/irrigation_runtime/dispatcher.py#L802-L833) and `SafetyMonitor.evaluate`/`_check_interlock` in safety.py L1722–1875.

With NEW currently running, the old owner polls OLD with pressure 2 bar against a configured maximum of 1 bar. The independent fixture uses zero debounce to isolate dispatch routing. The safety monitor emits PRESSURE_HIGH and explicitly identifies `event_id_affected = NEW`. The dispatcher compares NEW's active identity with OLD, finalizes OLD as EMERGENCY_STOPPED, and returns before calling the actuator's emergency STOP.

Observed result: zero STOPs, NEW still running, NEW durable phase EXECUTING. A second OLD poll adds zero STOPs. The violation is latched in that monitor. The matching-operation control correctly sends one STOP. Another independent monitor could later act; this probe establishes the dropped cutoff in the evaluating path, not indefinite field operation.

**Repair:** Route each violation by its own scope, device, and affected operation. An old operation's duration expiry must not stop a different healthy owner. A current device-level pressure/electrical fault must stop the device's current operation, including when discovered while processing stale event state. Update the actual affected event/exposure and retain evidence when ledger writes fail. Do not blanket-bypass safety violations using the polled event ID.

**Acceptance:** The stale-duration control preserves NEW, while current device PRESSURE_HIGH produces physical cutoff of NEW. Both paths must retain correct affected-event identity. Verify sustained breaches, already-latched violations, failed STOP, absent telemetry, and ledger failure without introducing a new cutoff bypass.

Evidence key: `device_interlock_suppressed_by_stale_event_guard`.

### PB04 — Dispatcher launders invalid area into missing support

Production locations: [dispatcher.py L75–79](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/services/agribrain/irrigation_runtime/dispatcher.py#L75-L79), [admission L408–421](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/services/agribrain/irrigation_runtime/dispatcher.py#L408-L421), and `IrrigationEvent.validate` in schemas.py L413–434.

Raw event areas −1, 0, True, False, string `"1"`, NaN, +Inf, and −Inf all reach EXECUTING and produce one START. The durable area is `None`, while the returned event retains its invalid raw area. Positive 1 ha and absent-area controls are also admitted, with their expected support values.

The direct store writer now rejects these invalid scalars correctly. The dispatcher defeats that protection by converting invalid input to `None` first. This is not a claim that optional area must always block all depth-command dispatch. The failure is loss of the distinction between absent support and explicitly invalid support, with inconsistent event/store identity.

**Repair:** Validate provided raw area before coercion or admission. Preserve `None` as absent support; reject provided invalid values with a typed event failure and zero sends. Use the same validated canonical representation in event, command context, reservation, recovery, and settlement.

**Acceptance:** Every invalid fixture fails before reservation/START and leaves the ledger unchanged. Valid positive and explicitly absent support retain their declared semantics, including the existing restriction on certifying nonzero litres as depth without qualified area.

Evidence key: `dispatcher_launders_invalid_area_to_missing`.

### PB05 — Stopped-only reopening loses the canonical envelope

Production location: [safety.py L1252–1314](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/services/agribrain/irrigation_runtime/safety.py#L1252-L1314).

Start from a valid 8 mm admission with duration 10 min, flow 10 L/min, and canonical area either missing or 1 ha. Convert it to a stopped receipt with conservative exposure 8 mm. There is now no active reservation. `reopen_active` called with target 1 mm, duration 20 min, flow 3 L/min, and area 2 ha accepts the changed values. Original device, zone, date, and season remain, but the reopened reservation carries the changed depth/duration/flow/support. Original missing area becomes qualified 2 ha.

A second 8 mm request is then admitted under the 10 mm budget; the ledger sees 1 + 8 = 9 mm, despite reopening an originally admitted 8 mm operation. This direct-store example does not claim a second physical delivery; it establishes exposure understatement at the writer boundary. The matching stopped-only reopening control retains 8 mm.

A separate plot-rebinding example is accepted and written. It removes the old stopped receipt but debits aggregates using the new caller plot. The old plot's 8 mm aggregate remains orphaned. The next read correctly raises `CorruptedQuotaStoreError`. Reader detection works; the production writer has nevertheless published an invalid candidate.

**Repair:** Choose the canonical operation envelope from active reservation, stopped receipt, or immutable admission record before any mutation. Bind plot, target, duration, flow, support including missingness, and original periods consistently. Reject incompatible caller values or apply an explicitly documented canonical retry policy. Compute debit corrections from the superseded receipt's canonical plot/period. Validate receipt-to-aggregate conservation before atomic publication.

**Acceptance:** Active, stopped-only, and correction/reopen paths enforce identical immutable identity. Conflicting plot/support/depth cannot reduce exposure or corrupt the ledger. A valid reopen retains 8 mm and blocks the second 8 mm admission. Rejections leave durable bytes unchanged; accepted writes remain readable with conserved aggregates and correction lineage.

Evidence keys: `stopped_only_reopen_mutates_envelope`, `stopped_only_reopen_plot_rebind_poisoning`.

### PB06 — Accepted settlement normalization breaks exact retry

Production locations: [retry comparison, safety.py L982–1011](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/services/agribrain/irrigation_runtime/safety.py#L982-L1011) and [canonical depth construction L1018–1062](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/services/agribrain/irrigation_runtime/safety.py#L1018-L1062).

For a canonical target of 8 mm over 1 ha, 40,000 L yields 4 mm:

\[
I_{mm}=\frac{V_L}{10{,}000\,A_{ha}}=4.
\]

A first settlement supplied as depth 5 mm with actual 40,000 L succeeds and normalizes the receipt to 4 mm. The byte-for-byte identical call then raises conflicting-retry `ValueError`, because retry comparison uses the caller's unnormalized 5 mm. A supplied target of 99 mm similarly succeeds first by restoring canonical target 8 mm, then fails on exact retry. The matching 4 mm/8 mm control succeeds on both calls. Failed retries leave receipt bytes unchanged and do not double debit.

**Repair:** Select one contract before the first write: reject inconsistent supplied values, or normalize them consistently and compare normalized retry identity. Preserve an immutable accepted request identity when compatibility intentionally permits normalization. Apply the same rule to target, support, device, zone, period, and measurements.

**Acceptance:** Every successful first request has an identical retry that returns the same outcome without additional debit or journal mutation. Every rejected conflict fails before first publication. Preserve rejection of genuinely changed measurements and supports.

Evidence key: `accepted_normalization_breaks_exact_retry`.

### PB07 — Explicit zero litres can coexist with certified nonzero depth

Production location: safety.py L1044–1062, the same canonical depth construction as PB06.

Reserve 8 mm with absent area, then call the public store settlement writer with depth 8 mm and explicit actual volume 0 L. It succeeds, publishes `actual_volume_l = 0.0` and `delivered_volume_mm = 8.0`, and debits 8 mm. The record is readable because current validation checks aggregate agreement, not this cross-unit contradiction.

This is a direct-store contract failure. Normal dispatcher completion already treats explicit 0 L as 0 mm correctly, including omitted duration preservation. That positive control is retained in the RC evidence.

**Repair:** At the canonical writer, explicit measured zero must certify zero delivery or reject contradictory supplied depth. For nonzero litres with missing area, preserve unresolved conversion unless a separately qualified depth observation is supplied with its own support/provenance. Do not infer physical delivery from a target or unqualified depth argument.

**Acceptance:** Direct store and dispatcher paths agree on measured zero. Distinguish missing volume from zero, missing duration from zero duration, and unknown area from invalid area. No accepted receipt may certify incompatible volume/depth observations.

Evidence key: `direct_settlement_zero_litres_nonzero_depth`.

## 4. Regression controls and implementation sequence

The independently rerun RC01–RC07 original counterexamples retain their corrected behavior. Under corrupt store reads or failed writes, the expired-watchdog reproduction issues physical STOP before the subsequent storage exception. Terminal snapshots do not stop a different live operation. Restart restores canonical plot/target, established timing cannot be advanced, healthy ACK timing persists before polling, running-controller completion remains blocked, omitted duration stays missing, and invalid writer duration leaves bytes unchanged.

The hydraulic process-publication control returns top-layer VWC 0.2124 from warm and cold workers after the same foreign historical correction, with equal full returned profiles and durable publication generation 4. The scheduled RAM hydration control preserves the winning soil state/head under compare-and-swap conflict. The two production files changed here do not alter the hydraulic runner; these are bounded regression observations, not closure of F08/F09 or all historical replay cases.

The recurring pattern is inconsistent qualification across entry points and phases. Canonical admission, cancellation, idle recovery, settlement, and stopped-only reopening each apply a different subset of identity and evidence rules. Additional isolated conditionals will leave those differences difficult to review.

| Delivery order | Concrete work | Required result |
|---|---|---|
| 1 | Define immutable operation envelope and persisted owner/generation. Distinguish event cancellation, operation watchdog, and device/global cutoff. | All dispatch paths use one qualified identity contract; sensor cutoff cannot be suppressed by a stale poll ID. |
| 2 | Repair PB01–PB03 across pending transport, late ACK, completion, cancellation, and interlock routing. | No late execution behind terminal zero exposure; unrelated cancellation is fenced; device hazards still stop current execution. |
| 3 | Repair PB05 using canonical stopped/admission records and pre-publication conservation. | Reopening cannot change support/scope or understate exposure; every accepted ledger remains readable. |
| 4 | Repair PB04, PB06, PB07 at shared validation/normalization boundaries. | Raw invalid support fails before START; accepted retries are idempotent; measurements agree across units. |
| 5 | Exercise integrated process restart, two workers, receipt corrections, device status loss, storage failure, pending send, STOP failure, and historical hydraulic publication. | Consistent local/durable/physical identities and conservative exposure across the complete transition matrix. |
| 6 | Complete the designated multi-process/hardware acceptance using the actual controller protections and receipts. | Evidence supports the relevant full-acceptance tickets; simulation alone does not close them. |

The pending-send fence and canonical exposure repair are prerequisites for qualifying this runtime's physical commands and dependent delivered-management evidence. Independent agronomic, numerical, interface, or exploratory world-model/Omega work can proceed where its own eligibility gates permit. Do not promote uncertain irrigation receipts into certified observations, labels, economics, or rollout evaluation.

The replay bundle's verifier intentionally asserts the current counterexamples. After repair, replace those faulty-outcome assertions with the acceptance behaviors specified above; a verifier that confirms a defect is not a remediation acceptance suite.

## 5. Milestone integrity and source provenance

The task register blob is `8a564647af7e588802537817159117b349ff606b`. Its unchanged source retains all six full-acceptance boxes open:

| Ticket | Line | State |
|---|---:|---|
| ST03-F08-FA | 406 | `[ ]` |
| ST03-F09-FA | 443 | `[ ]` |
| ST06-F16-FA | 796 | `[ ]` |
| ST06-F17-FA | 833 | `[ ]` |
| ST06-F18-FA | 870 | `[ ]` |
| ST06-F19-FA | 907 | `[ ]` |

Register: [pinned task list](https://github.com/webClone/AgriWise/blob/19fdb677c626b1d8b5430ab7b81e7376fdbb8b99/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md). These entries are planning evidence only; they are not used to establish production correctness.

| Production path | Git blob |
|---|---|
| `services/agribrain/irrigation_runtime/dispatcher.py` | `b2a4d1362d4b93e205b2583ba34b0702c36c7631` |
| `services/agribrain/irrigation_runtime/safety.py` | `02fd9342152b5908e850e4cbcdf178106c3bf0b7` |

The reproduction ZIP contains the 16 independent drivers, observed JSON/logs, integrity manifest, sanitized commit metadata, production-only diff, R3 register excerpt, evidence verifier, and reproduction instructions. Production runtime copies, repository tests/audit documents, temporary ledgers/checkpoints, bytecode, and credentials are excluded. Obtain an exact pinned checkout separately; the runner verifies all 430 dependency blob identities before importing it.

Proceed with the corrective implementation sequence above. Keep full acceptance open until the remaining contracts and integrated verification gates pass.

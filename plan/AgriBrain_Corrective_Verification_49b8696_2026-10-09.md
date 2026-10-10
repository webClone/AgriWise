# AgriBrain corrective implementation verification — 49b8696

Date: 2026-10-09 UTC  
Reviewed commit: `49b8696be562305000259b350e8c4870251386be`  
Parent: `dcb272d94c03a8115d3d09d5b800d6b436ec1364`  
Repository: [webClone/AgriWise](https://github.com/webClone/AgriWise)  
Review type: read-only production-source review plus independent software reproduction.

## 1. Decision

**The claim that all V01–V11 are fully resolved is not supported by this commit.** There are genuine corrective changes, including five findings whose original, bounded counterexamples now pass. Six original findings remain only partially resolved. Expanding the boundary checks produces **11 distinct remaining defect groups**, identified below as C01–C11. These new identifiers belong only to this verification report; they do not replace the plan's F/T packages or the monograph's R3 requirement IDs.

Proceed with targeted corrective implementation. Keep Batch A/B completion qualified and the full acceptance tickets open. Physical command admission/STOP/accounting failures must be resolved before those command paths satisfy F16–F19 acceptance. Historical hydraulic replay and competing-worker RAM publication must be resolved before affected water states can serve as a qualified canonical foundation for downstream scientific acceptance.

Independent exploratory world-model/Omega work need not wait for unrelated packages. Its eligibility must explicitly exclude affected states, unqualified execution receipts and contaminated replay windows. This review supplies no full world-model/Omega implementation or acceptance sign-off.

## 2. Scope and evidence quality

- Retrieved and pinned the six changed production Python files from GitHub at the full SHA above, including their production-only diff against the parent.
- Assembled an executable dependency workspace containing **430 production Python files**. Every file's Git blob SHA-1 matches the pinned repository tree. This is dependency/source integrity, not a claim that all 430 files underwent complete semantic review.
- All six changed production files parse successfully with Python's AST parser. This is narrower than a full repository compilation or deployment check.
- Executed **68 independent probe groups**: 32 runtime baseline groups, 11 hydraulic baseline groups, 10 adversarial baseline groups, 13 new boundary groups, one controlled hydraulic concurrency group, and one group with six individual dependency-change cases. Groups can contain several subcases; this is not a pytest pass count.
- No harness errors were recorded. Probe observations include successful controls and counterexamples, not 68 passing acceptance tests.
- Did not read or execute repository test files as correctness evidence. Existing audit reports were not accepted as proof of current correctness. The prior counterexample definitions and R3 requirements establish the targets being checked.
- No production source was modified or pushed. All actuator interactions used independent controlled software drivers; no field hardware was operated.
- Rechecked GitHub main at completion: it still points to this SHA.
- The claimed `14 passed` and `372 passed` are user-reported results, not independently recertified here. They can coexist with these counterexamples.

### Production source identity

| File | Pinned Git blob |
|---|---|
| [services/agribrain/irrigation_runtime/actuator.py](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/actuator.py) | `a5d9373b49ed0e7c7b3429d92719191864f6d64a` |
| [services/agribrain/irrigation_runtime/dispatcher.py](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py) | `c0c3a0e529c797dc3bd5bed84ea281776563132b` |
| [services/agribrain/irrigation_runtime/safety.py](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py) | `05af555d3c949014f343129f63770ec1aa769dcb` |
| [services/agribrain/irrigation_runtime/schemas.py](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/schemas.py) | `3b65060a2683299fab45ef261b555320ca6447dd` |
| [services/agribrain/layer3_decision/runner.py](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/layer3_decision/runner.py) | `6ed9a4dbf119d13202a7a9f8f85f9b135f4b3be4` |
| [services/agribrain/world_model/canonical_worldline.py](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/world_model/canonical_worldline.py) | `aa11d851b502edb4db30e617209347ca17f92635` |

### Plan and monograph qualifications

The current task register matches the previously retrieved Git blob `8a564647af7e588802537817159117b349ff606b`. The following full acceptance entries remain unchecked in the pinned source:

| Ticket | Register line | Current state |
|---|---:|---|
| ST03-F08-FA | 406 | `[ ]` |
| ST03-F09-FA | 443 | `[ ]` |
| ST06-F16-FA | 796 | `[ ]` |
| ST06-F17-FA | 833 | `[ ]` |
| ST06-F18-FA | 870 | `[ ]` |
| ST06-F19-FA | 907 | `[ ]` |

The scientific requirements below use the previously supplied R3 monograph requirement register. R3 is not present as an R3 monograph file in this pinned Git tree. This review does not claim that the monograph was newly revised or that every monograph requirement was re-audited.

## 3. V01–V11 claim-by-claim result

“Bounded pass” means the named original mechanics were corrected in the exercised cases. It is not full package acceptance.

| Previous finding | Result at 49b8696 | Verified correction | Remaining qualification |
|---|---|---|---|
| V01 corrupt quota storage | Partial | Blank, malformed JSON and non-object JSON raise CorruptedQuotaStoreError and prevent a second START. | Nested negative/NaN reservation amounts are accepted; loss of an established store resets exposure. C03. |
| V02 live-owner lock takeover | Bounded pass | A separate live process retains a lock aged past 30 seconds; the competitor times out instead of entering. Ownership-token release is implemented. | This demonstrates same-host process ownership, not distributed-host/container fencing or full deployment acceptance. |
| V03 operation admission and payload binding | Partial | Normal positive-volume, budgeted same-ID concurrent admission issues one START. Volume/device/plot conflicts are checked. | Duration/zone/flow binding remains incomplete; pending/UNSETTLED records become false EXECUTING receipts; zero-depth events lack durable claims. C06/C07. |
| V04 season and stopped exposure | Partial | Season/date survive reservation and normal settlement. With an explicitly attached valid 1 ha area, 160,000 L converts to 16 mm. | Unknown stopped deliveries are stored as zero or dropped; stop receipts can redose/double debit; settlement input and receipt identity remain defective. C04/C05/C08/C09. |
| V05 invalid-budget exception | Bounded pass | NaN and Inf budgets become FAILED with zero START calls; no secondary NameError. | Not a certification of all budget/settlement corruption paths. |
| V06 deadline monitoring and STOP preemption | Partial | The monitor exists before START awaits ACK; an explicit deadline poll can invoke emergency_stop while ACK is pending. Malformed restart time expires conservatively. | Ordinary cancellation can falsely return ALREADY_STOPPED; late START completion defeats terminal STOP intent and tracking. C01/C02. |
| V07 cold exact replay | Partial | Replaying the latest committed day after clearing RAM preserves theta and sequence. | Replaying an older day after a later head exists consumes future posterior state and advances a new older-day head. C10. |
| V08 dependencies and scope | Bounded pass | Changing cycle, geometry, parameter epoch, soil type, timestamp, or weather ensemble individually avoids the old cached object and head. | This establishes cache invalidation for these cases, not calibration correctness of the resulting model or all namespace isolation. |
| V09 RAM rollback | Partial | Fresh/warm single-worker CAS failures restore prior history; write failure returns no usable water result. | A losing worker's rollback erases a winning worker's newly published RAM state. Durable winner survives. C11. |
| V10 persistence failure propagation | Bounded pass | Injected OSError propagates as RuntimeError instead of returning unpersisted water as usable. | Does not establish crash/power-loss durability or caller-level application acceptance. |
| V11 orphan recovery and identity | Bounded pass | Same-identity interrupted head publication recovers, publishes head, and permits RAM commit; changed cycle/geometry is rejected. | Limited to exercised identity/CAS/head failure cases; historical replay correctness remains separate. |

Additional successful controls: failed STOP retains STOP_REQUESTED, delivery context, monitoring and quota; missing/failed controller queries preserve uncertain exposure; missing telemetry still permits the explicitly invoked watchdog; validation retains UNSETTLED exposure; same receipt normal settlement is idempotent; a fresh process observes prior reservation/settlement; two real processes competing for 8 mm against 10 mm accept only one reservation; withdrawal dates survive ISO-string checkpoint roundtrip.

## 4. Remaining defects and exact repairs

Priority P0 means a demonstrated command-safety or quota fail-open boundary. P1 means a demonstrated identity, receipt, replay or concurrency correctness failure. Priorities apply to the affected capability; they do not impose a universal block on independent work.

### C01 — P0 — Pending START is mistaken for an already stopped actuator

Source: [actuator.py:276–295](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/actuator.py#L276-L295); [dispatcher.py:629–658](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L629-L658).

While START awaits its ACK, `_pending_command` is set, `_active_command` is unset and local status remains ONLINE. `_execute_stop_direct` considers ONLINE plus no active command sufficient to return `ALREADY_STOPPED`; it does not inspect the pending command or obtain an operation-specific stopped receipt.

Reproduction: the simulated driver applies START but withholds ACK. `cancel_event` returns CANCELLED, sends **zero STOP commands**, removes dispatcher/watchdog tracking, and writes a stopped receipt while the simulated actuator remains running. The local monitor's legacy reservation cache still reports 8 mm; the durable shared store reports **0 mm**. This local/shared distinction matters: a local diagnostic is not durable exposure protection.

Repair: STOP must be physically attempted or operation-level reconciled whenever a START is pending/uncertain. Do not use local ONLINE to certify stopped. Persist STOP intent first and retain ownership, deadline and conservative exposure until that operation cannot subsequently start.

Acceptance: pause START before ACK both before and after physical application; ordinary cancellation must send/reconcile STOP, preserve uncertainty when needed, and never declare terminal cancellation solely from local ONLINE.

R3: AB-EXE-002, AB-EXE-003, AB-EXE-004, AB-DAT-010.

### C02 — P0 — Late START completion revives a finalized operation

Source: [actuator.py:464–482](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/actuator.py#L464-L482); [actuator.py:561–575](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/actuator.py#L561-L575); [dispatcher.py:326–334](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L326-L334); [dispatcher.py:514–532](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L514-L532).

Both actuator and dispatcher unconditionally publish EXECUTING when an outstanding START returns success. They do not compare a STOP/cancel generation, terminal operation state or remaining owner token after the await.

Reproduction: delay application/ACK of START; advance the controlled clock to 601 seconds for a 10-minute command; explicitly poll. The watchdog sends emergency stop and finalizes EMERGENCY_STOPPED, with active events = 0, monitored events = 0 and shared reserved exposure = 0. Release the delayed START so it applies after STOP. The result becomes EXECUTING and the simulated driver becomes running, while active events and monitored events remain **0** and shared exposure remains **0 mm**. A second control applies START before STOP: late ACK still falsely revives EXECUTING even though the physical simulation is now stopped.

Repair: introduce an operation generation/fence and persistent STOP intent. Every completion must compare the generation it started under. A preempted in-flight command must not restore execution; controller/driver protocol must qualify whether a queued START could apply after STOP. Where physical cancellation is unproven, retain unresolved ownership and reissue/reconcile STOP instead of releasing the event.

Acceptance: exercise both application orders and delayed ACK, failed STOP, restart between STOP and ACK, and owner loss. Terminal intent must not be reversed by a stale completion. Software task cancellation alone must not be presented as proof that an external controller did not apply the request.

R3: AB-EXE-002, AB-EXE-003, AB-EXE-004, AB-ARC-008.

### C03 — P0 — Quota validation does not validate ledger values or established-store loss

Source: [safety.py:176–201](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py#L176-L201); [safety.py:349–366](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py#L349-L366).

`_read_state` validates the top-level dictionary, required-key presence and the reservations container type. It does not validate reservation record shapes, finite/nonnegative amounts, the other ledger container types, or receipt/aggregate coherence. Python JSON also accepts NaN unless explicitly disallowed. A missing file returns an empty store with no distinction between initial bootstrap and loss of an established ledger.

Reproduction: start/reserve A for 8 mm against a 10 mm budget. Independently replace its stored amount with -8, replace it with NaN, or delete the established quota file. In each case a second independent dispatcher admits B for 8 mm: **both simulated drivers are running and joint admitted targets are 16 mm against 10 mm**. This measures admitted exposure; it is not a field measurement of delivered depth. Blank/malformed/non-object controls now correctly block.

Repair: version and validate every record and aggregate, reject booleans/non-finite/negative amounts, reject inconsistent receipts/rollups, and explicitly qualify initialization versus unavailable/lost established state. Recover exposure from an authoritative journal or require a qualified recovery/reset; do not manufacture a zero-exposure bootstrap over known prior operations.

Acceptance: fuzz nested values and all ledger maps, missing keys, malformed records, and established-file disappearance. A corrupt or unavailable ledger cannot admit new physical STARTs or release unresolved prior exposure.

R3: AB-EXE-004, AB-DAT-005, AB-DAT-012, AB-ARC-006.

### C04 — P0 — Confirmed stop still discards unknown delivered exposure

Source: [dispatcher.py:650–658](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L650-L658); [dispatcher.py:686–694](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L686-L694); [dispatcher.py:497–530](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L497-L530); [safety.py:551–583](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py#L551-L583).

Cancellation/global emergency stop always supply `delivered_volume_mm=0.0`. The stopped record keeps target metadata but removes the reservation, and quota arithmetic does not charge that target or unknown delivered exposure. Watchdog and several retry/restart/error stop paths call release_quota directly and create no stopped receipt. Confirmation that a valve is stopped establishes current operation state; it does not establish that historical delivered water was zero.

Reproduction: start A targeting 8 mm under a 10 mm limit, then cancel after acknowledged START without a delivered-depth observation. The stopped receipt says delivered_volume_mm = 0, reservations/settled totals are empty, and another 8 mm START is admitted. The watchdog path also admits the second 8 mm, with no stopped receipt at all. Prior actual depth is unmeasured in these simulations, so the demonstrated defect is loss of unresolved exposure, not a claim that precisely 16 mm was delivered.

Repair: centralize every stop-finalization path into one durable transaction. Represent stopped delivery as observed, bounded or unknown; keep conservative unsettled exposure until qualified measurement/reconciliation. Targets are not automatically proven upper bounds for an overrun. Use qualified flow/time/controller protections when forming bounds; preserve source/uncertainty and period metadata.

Acceptance: cancellation, watchdog, global emergency, STOP retry, ERROR and restart branches conserve outstanding accounting until settlement. Missing measurement cannot become observed zero. A second command cannot spend the same unresolved allowance.

R3: AB-EXE-002, AB-EXE-004, AB-DAT-005, AB-DAT-006, AB-DAT-010.

### C05 — P1 — Stopped receipts do not provide terminal idempotency

Source: [safety.py:563–583](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py#L563-L583); [safety.py:602–623](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py#L602-L623); [dispatcher.py:200–256](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L200-L256).

The shared admission checks consult reservations and settled_receipts, but not stopped_receipts. The stopped-settlement helper also overwrites the receipt and increments aggregates on every call, without an idempotent identity guard.

Reproduction A: acknowledge START E, cancel successfully, construct a fresh dispatcher and resubmit the exact same E. It returns EXECUTING and total START calls become **2**.

Reproduction B: record a 3 mm stopped delivery, then retry the identical record. Total settled depth changes **3 → 6 mm**. That is an accounting error, even though it errs conservatively for quota admission.

Repair: maintain one immutable operation identity and terminal receipt ledger across completed/cancelled/emergency/failed-but-delivered outcomes. Identical retries return the same receipt; a correction becomes a separately identified adjustment with lineage, rather than another debit under the same settlement identity.

Acceptance: exact cancelled/emergency retries issue zero extra STARTs, return their original qualified outcome and do not re-debit. Changed commands or inconsistent settlement retries produce explicit conflicts.

R3: AB-EXE-003, AB-DAT-003, AB-DAT-010, AB-DAT-011, AB-ARC-008.

### C06 — P1 — Command payload binding is incomplete and operation claims depend on positive depth

Source: [dispatcher.py:176–191](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L176-L191); [dispatcher.py:231–280](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L231-L280); [safety.py:313–347](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py#L313-L347).

Local duplicate checks compare target depth, duration, device and plot but omit zone and flow. Fresh/durable checks compare depth, device and plot, omitting duration, zone and flow. Atomic admission receives duration/zone but does not compare them; flow is not represented. Atomic operation claiming is also conditional on a budget and positive target depth rather than being an independent execution identity transaction.

Reproduction: with original 8 mm/10 min/zone/10 L min⁻¹ active, a fresh dispatcher resubmits the same ID with duration = 20, zone = other-zone, or flow = 20. Each returns EXECUTING for the conflicting request. The local dispatcher rejects changed duration (positive control) but accepts changed zone/flow as an idempotent repeat. Direct atomic duration/zone changes return ALREADY_RESERVED rather than conflict.

Zero-depth reproduction: two independent simulated driver/dispatcher instances submit the same event ID with valid target depth 0 and a budget. Both execute and total START calls = **2**. A sequential positive-depth request without a budget is still deduplicated by the reservation created during monitoring (positive control); this report does not claim that every no-budget submission duplicates.

Repair: hash a canonical typed command payload and bind it to a scoped durable operation independently of quota amount. Include command kind, plot/tenant/namespace, zone, device, depth/volume units and support, duration, flow, pulse/configuration parameters and authorization/version references. Decide explicitly whether a duration-only/zero-depth operation is eligible and reserve a qualified exposure bound where needed.

Acceptance: mutate each physical field individually in local, fresh-worker and atomic-race paths. Every incompatible repeat conflicts; exact repeats share the original operation. Valid zero must not disable durable operation identity.

R3: AB-EXE-001, AB-EXE-003, AB-DAT-005, AB-DAT-013, AB-ARC-008.

### C07 — P1 — A durable reservation is promoted to an executing receipt

Source: [dispatcher.py:249–256](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L249-L256); [dispatcher.py:276–284](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L276-L284); [safety.py:491–498](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py#L491-L498).

A reservation establishes an admission claim, not acknowledged physical execution. Returning a new event with status EXECUTING loses the original DISPATCHING/STOP_REQUESTED/VALIDATING phase and does not attach the caller to the owner's future receipt. UNSETTLED reservation records are treated as active execution in the same way.

Reproduction: pause the owner's START until a duplicate fresh dispatcher returns. The duplicate is immediately EXECUTING before ACK. Release the owner with a NOT_APPLIED driver error; the production conservative reconciliation makes the original STOP_REQUESTED while the duplicate remains EXECUTING and the controlled driver is not running. Only one START send occurred; the remaining failure is false authority and disconnected lifecycle propagation, not duplicate dosing in this positive-volume case.

Repair: persist the operation phase, owner, attempt/generation and qualified receipt; join/read that authoritative operation. Pending, uncertain and validation phases must remain explicit, and duplicate callers must observe outcome changes consistently.

Acceptance: join before ACK, after failed ACK, during STOP_REQUESTED and during UNSETTLED validation. Duplicate requests cannot report acknowledged execution merely because water was reserved.

R3: AB-EXE-002, AB-EXE-003, AB-DAT-010, AB-ARC-006.

### C08 — P0 — Settlement can erase exposure on invalid measurement and mistakes zero for target delivery

Source: [dispatcher.py:585–612](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L585-L612); [safety.py:518–548](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py#L518-L548); [schemas.py:345–353](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/schemas.py#L345-L353).

complete_event publishes COMPLETED before qualifying actual volume, duration, area or successful settlement. Its conversion uses float/truthiness rather than finite_real. settle pops the reservation before checking that depth is valid and positive; invalid/zero depth yields no receipt. Explicit 0 L takes the target-depth fallback, conflating valid zero with missing measurement.

Reproduction with explicitly attached area = 1 ha: actual volume = Inf yields COMPLETED, reserved = 0, settled = 0 and no receipt. Finite 80,000 L with area = Inf also produces COMPLETED with no exposure/receipt. Area = True is accepted as 1 ha. Explicit measured 0 L settles the planned **8 mm**, not zero. Finite 160,000 L / 1 ha correctly produces **16 mm** (positive control).

The equation is correct when its operands are qualified:

\[ I_{mm} = \frac{V_L}{10{,}000\, A_{ha}}. \]

Integration qualification: effective_area_ha is not a declared IrrigationEvent field, and the standard scheduler does not populate it. The conversion branch was exercised by explicitly attaching that attribute. This verifies the conditional arithmetic, not that the normal scheduling/serialization pipeline supplies qualified area.

Repair: make observed volume, time, area/support and uncertainty typed and optional; validate before any status or accounting mutation; preserve valid zero; distinguish gross withdrawal/application depth from effective infiltration. Commit immutable receipt plus ledger delta atomically, then publish COMPLETED. Invalid/missing observation must retain an explicit unresolved/bounded accounting status rather than releasing exposure.

Acceptance: NaN/Inf/bool/negative/missing values in actual delivery and area; exact zero; fractional/zone area; serialization roundtrip; settlement storage failure. No invalid value may delete the prior exposure or create a completed qualified receipt.

R3: AB-EXE-002, AB-EXE-004, AB-DAT-005, AB-DAT-006, AB-DAT-007, AB-ARC-007.

### C09 — P1 — Settled identity compares command target to delivery outcome and loses observations

Source: [safety.py:528–541](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py#L528-L541); [dispatcher.py:202–225](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/dispatcher.py#L202-L225); [safety.py:278–310](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/irrigation_runtime/safety.py#L278-L310).

The settled receipt stores volume_mm as delivered depth and later compares it against a retry's target_volume_mm as if those were the same command parameter. The receipt also omits actual_volume_l/duration, despite the retry code trying to recover actual_volume_l.

Reproduction: command target = 8 mm, valid area = 1 ha, measured delivery = 40,000 L = 4 mm. Settlement correctly debits 4 mm, but resubmitting the exact original 8 mm command via a fresh dispatcher returns FAILED with a payload conflict. The 16 mm delivered-depth case has the same identity error. In the exact 8 mm/80,000 L case the repeat returns COMPLETED but reports actual_volume_l = **0.0**, because the original 80,000 L observation was not persisted.

Repair: store immutable commanded payload/hash separately from observed delivery, derived depth/support, timestamps, sensor/controller provenance and outcome. Compare retry command identity only to original command identity. Rehydrate the complete qualified receipt, not a newly synthesized event with defaults.

Acceptance: under/over/exact delivery, valid zero and no measurement; exact retry returns the original outcome and observations; changed command conflicts. Outcome corrections preserve original receipts and carry distinct adjustment lineage.

R3: AB-EXE-002, AB-EXE-003, AB-DAT-006, AB-DAT-007, AB-DAT-010, AB-DAT-011.

### C10 — P1 — Older-date cold replay integrates from future posterior state

Source: [runner.py:1225–1246](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/layer3_decision/runner.py#L1225-L1246); [runner.py:1256–1296](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/layer3_decision/runner.py#L1256-L1296); [runner.py:2045–2071](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/layer3_decision/runner.py#L2045-L2071); [runner.py:2242–2257](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/layer3_decision/runner.py#L2242-L2257).

The new cold replay guard chooses the initial prior only when latest checkpoint step_key equals the requested day. When the durable head is later than the request, hydration loads that later posterior into memory. Earlier historical states can be absent for the first requested step; the generic memory fallback then supplies the future posterior.

Reproduction with identical weather and vegetation: January 2 theta = [0.2007, 0.2218, 0.2253, 0.2277, 0.2295]. Commit January 3: theta = [0.1730, 0.2139, 0.2210, 0.2259, 0.2295]. Clear all RAM dictionaries, replay the same January 2 request: theta becomes **[0.1489, 0.2052, 0.2163, 0.2239, 0.2295]**, head sequence advances **2 → 3**, and the new head step_key is January 2 rather than the original transition receipt. The latest-day-only cold replay control now passes unchanged.

Repair: select a checkpoint/prior whose valid time strictly precedes the transition (or the exact transition's persisted initial prior). Never use latest posterior as an undated fallback for historical requests. Exact historical queries should return/reconstruct the original qualified transition without replacing the operational head. A true historical revision must identify a branch/revision, rebuild affected descendants and publish its head deliberately.

Acceptance: request D after D+1/D+n already exists, both warm and cold, with/without first-step prior, rolling weather windows, evidence withdrawal and revisions. Exact replay preserves states and identity; revisions conserve temporal lineage and exclude future state/evidence.

R3: AB-DAT-003, AB-DAT-004, AB-DAT-011, AB-DAT-012, AB-ARC-009.

### C11 — P1 — A losing hydraulic rollback erases a winning worker’s RAM publication

Source: [runner.py:1304–1342](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/layer3_decision/runner.py#L1304-L1342); [runner.py:2297–2327](https://github.com/webClone/AgriWise/blob/49b8696be562305000259b350e8c4870251386be/services/agribrain/layer3_decision/runner.py#L2297-L2327).

Rollback clears shared per-plot dictionaries and restores an unconditional snapshot. Candidate computation does not protect that snapshot/commit/rollback interval with per-scope synchronization or a cache-generation guard. A CAS failure on disk does not authorize restoration over a different worker's already committed RAM state.

Reproduction uses real production persistence/CAS and two threads, with only scheduling controlled: commit January 2; worker A computes January 3 with 5 mm rain and pauses immediately before save; worker B computes/commits January 3 with 10 mm rain; release A. A receives ConcurrencyConflictError as intended. Its rollback removes B's January 3 cache, returns cached head to January 2, and changes cached top-layer theta **0.2423 → 0.2007**. The durable head remains B's January 3 checkpoint. Thus disk CAS works; shared RAM publication/rollback is still unsafe.

Repair: keep mutable candidates local, serialize publication for a scoped plot/cycle or compare-and-swap a cache generation, and allow rollback to undo only changes owned by that generation. Use durable state rehydration instead of restoring a stale snapshot over a newer head. Protect compatibility aliases as well as scoped registries.

Acceptance: barrier-controlled two-worker winner/loser/revision interleavings. After a loser returns, durable head, cached head, history and hydraulic memory must agree with the winner. A subsequent engine call may rehydrate and heal the current implementation; that does not make the intervening stale publication correct.

R3: AB-ARC-007, AB-ARC-008, AB-DAT-012.

## 5. Focused implementation sequence

This is the next corrective slice, not a replacement for the 52-package master plan/addendum. Preserve existing F/T/R3 IDs and map the C findings back into their owning acceptance gates.

| Order | Concrete work | Findings | Required exit evidence |
|---:|---|---|---|
| 1 | Durable operation record: scoped command hash, lifecycle, owner/generation, STOP intent and qualified controller receipt | C01/C02/C06/C07 | Pending START stop/late ACK interleavings cannot create untracked execution or false authority; conflicts rejected field by field; zero-depth identity covered. |
| 2 | Fail-closed store schema and established-store recovery | C03 | Nested corruption and store loss cannot reset live exposure; qualified recovery preserves all outstanding operations. |
| 3 | Unified stopped/unsettled/completed accounting transaction and terminal idempotency | C04/C05 | Every stop route preserves unknown exposure; exact retries neither redose nor double debit. |
| 4 | Typed delivery/support contract and immutable command/outcome receipts | C08/C09 | Valid zero preserved; bad numbers rejected before mutation; partial delivery retries reproduce original observations; scheduler/serialization supplies support. |
| 5 | Historical checkpoint selection, exact receipts and deliberate revision publication | C10 | Warm/cold D-after-D+n replay matches the original state and does not replace the operational head on an exact query. |
| 6 | Scoped candidate isolation and generation-aware RAM publication | C11 | The real-CAS losing worker cannot erase a concurrent winner; disk and RAM agree after each return. |
| 7 | Integrated acceptance across drivers, restart, workers, persistence and applications | Relevant F08/F09/F16–F19 tickets | Objective-specific end-to-end evidence, remaining plan criteria and explicit sign-off; reported unit counts alone do not close these gates. |

Orders 2, 5 and 6 can proceed independently where prerequisites permit. Order 3/4 must converge on the same operation/receipt schema as order 1; avoid separate contradictory receipt ledgers. Implement independently reviewable slices and retain an invariant-based reproduction case for every card above.

No effort rollup is recalculated here. The existing program estimates remain plan estimates; assigning precise hours to these interdependent corrections without agreeing schema and deployment scope would create false precision.

## 6. R3 scientific and architectural alignment

| Requirement | Monograph target, paraphrased | Remaining affected findings |
|---|---|---|
| AB-EXE-001 | Canonical action retains dose, unit, support/window, driver and constraints. | C06 |
| AB-EXE-002 | ACK, execution start, delivery, outcome and unknown are distinct. | C01/C02/C04/C07/C08/C09 |
| AB-EXE-003 | Uncertainty after send is reconciled before potential duplicate execution. | C01/C02/C05/C06/C07/C09 |
| AB-EXE-004 | Quotas, timers, fencing and protection operate despite missing sensor data. | C01/C02/C03/C04/C08 |
| AB-DAT-003 | Revisions preserve prior events and decisions in an append-only worldline. | C05/C10 |
| AB-DAT-004 | Issuance replay excludes later data/revisions and respects temporal cutoff. | C10 |
| AB-DAT-005 | Valid zero is preserved and absence gains no invented physical value. | C03/C04/C06/C08 |
| AB-DAT-006 | Observation, prior, reconstruction, forecast and synthetic provenance remain distinct. | C04/C08/C09 |
| AB-DAT-007 | Unit/support conversions are traceable. | C08/C09 |
| AB-DAT-010 | Planned, authorized, commanded, delivered, cancelled and unknown management events remain distinct. | C01/C04/C05/C07/C09 |
| AB-DAT-011 | Immutable data/receipt content and identity remain bound. | C05/C09/C10 |
| AB-DAT-012 | Persistence and invalidation support coherent replay. | C03/C10/C11 |
| AB-DAT-013 | Tenant/farm/plot/cycle/geometry define isolated namespaces. | C06 command contract scope |
| AB-ARC-006 | Degraded outputs expose limitations without fallback promotion. | C03/C07 |
| AB-ARC-007 | Partial/incompatible publications cannot replace validated canonical state. | C08/C11 |
| AB-ARC-008 | Retries and concurrent workers cannot publish incompatible effects. | C02/C05/C06/C11 |
| AB-ARC-009 | Scientific calculation identities stay distinct from question/response identity. | C10 replay/query versus operational publication |

These are traceability associations, not an assertion that every listed requirement is wholly unimplemented. Examples: the new conditional volume/area formula is dimensionally correct, but its value qualification and receipt semantics are incomplete; disk CAS protects the winning checkpoint, but rollback still violates RAM publication consistency.

## 7. Reproduction bundle and interpretation

The companion ZIP contains only independent review harnesses, observed JSON results, the production blob manifest and instructions. It contains no repository tests, audit files, credentials, full commit API payloads, production source copies or hardware drivers. Harnesses subclass the production abstract actuator interface with controlled software simulation.

Some JSON keys retain the name of the original counterexample even where its trigger now passes. Interpret the observed status/values and the V01–V11 table, not a key name as a verdict. For example, corrupt_quota_fail_open now contains typed rejections for blank/malformed JSON, while storage_validation supplies the distinct remaining nested-corruption counterexamples.

The two-process positive quota probe tests separate OS processes on the same host and shared configured directory. The same-ID thread probe tests independent dispatcher/monitor/driver instances within one process. The hydraulic concurrency probe uses a real production CAS with a controlled pre-save interleaving. These scopes must not be generalized to multi-host hardware acceptance.

## 8. Selected verbatim numerical observations

The following JSON is the observation transcript from the new boundary and concurrency probes. Timestamps identify simulated calls; they are not field observations.

```json
{
  "pending_cancel_applied_before_ack": {
    "after_cancel": {
      "event_status": "CANCELLED",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 0,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 8.0,
      "settled_mm": 0.0,
      "delivery_context": null,
      "shared_reserved_mm": 0.0
    },
    "after_ACK": {
      "event_status": "EXECUTING",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 0,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 8.0,
      "settled_mm": 0.0,
      "delivery_context": "START_ZONE",
      "shared_reserved_mm": 0.0
    },
    "stop_error_codes": [
      "ALREADY_STOPPED"
    ]
  },
  "pending_cancel_applied_after_stop": {
    "after_cancel": {
      "event_status": "CANCELLED",
      "physical_running": false,
      "physical_start_calls": 1,
      "physical_stop_calls": 0,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 8.0,
      "settled_mm": 0.0,
      "delivery_context": null,
      "shared_reserved_mm": 0.0
    },
    "after_ACK": {
      "event_status": "EXECUTING",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 0,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 8.0,
      "settled_mm": 0.0,
      "delivery_context": "START_ZONE",
      "shared_reserved_mm": 0.0
    },
    "stop_error_codes": [
      "ALREADY_STOPPED"
    ]
  },
  "pending_watchdog_late_application": {
    "after_stop": {
      "event_status": "EMERGENCY_STOPPED",
      "physical_running": false,
      "physical_start_calls": 1,
      "physical_stop_calls": 1,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 0.0,
      "settled_mm": 0.0,
      "delivery_context": null
    },
    "after_late_START": {
      "event_status": "EXECUTING",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 1,
      "active_events": 0,
      "tracked_events": [],
      "reserved_mm": 0.0,
      "settled_mm": 0.0,
      "delivery_context": "START_ZONE"
    }
  },
  "payload_binding": [
    {
      "scope": "local",
      "field": "target_duration_minutes",
      "requested": 20,
      "returned_status": "FAILED",
      "returned_value": 20,
      "starts": 1
    },
    {
      "scope": "local",
      "field": "target_flow_rate_lpm",
      "requested": 20,
      "returned_status": "EXECUTING",
      "returned_value": 10,
      "starts": 1
    },
    {
      "scope": "local",
      "field": "zone_id",
      "requested": "other-zone",
      "returned_status": "EXECUTING",
      "returned_value": "zone",
      "starts": 1
    },
    {
      "scope": "fresh",
      "field": "target_duration_minutes",
      "requested": 20,
      "returned_status": "EXECUTING",
      "returned_value": 20,
      "starts": 1
    },
    {
      "scope": "fresh",
      "field": "target_flow_rate_lpm",
      "requested": 20,
      "returned_status": "EXECUTING",
      "returned_value": 20,
      "starts": 1
    },
    {
      "scope": "fresh",
      "field": "zone_id",
      "requested": "other-zone",
      "returned_status": "EXECUTING",
      "returned_value": "other-zone",
      "starts": 1
    }
  ],
  "atomic_payload_binding": [
    {
      "field": "duration_minutes",
      "action": "ALREADY_RESERVED",
      "notes": "Event E already reserved by concurrent worker"
    },
    {
      "field": "zone_id",
      "action": "ALREADY_RESERVED",
      "notes": "Event E already reserved by concurrent worker"
    }
  ],
  "pending_duplicate_failure": {
    "duplicate_before_ACK": "EXECUTING",
    "duplicate_after_original_failed": "EXECUTING",
    "original_status": "STOP_REQUESTED",
    "driver_running": false,
    "sends": 1,
    "reserved_mm": 8.0
  },
  "operation_claim_quota_gating": [
    {
      "case": "zero_depth_with_budget",
      "statuses": [
        "EXECUTING",
        "EXECUTING"
      ],
      "START_calls": 2,
      "same_event_id": true
    },
    {
      "case": "positive_depth_without_budget",
      "statuses": [
        "EXECUTING",
        "EXECUTING"
      ],
      "START_calls": 1,
      "same_event_id": true
    }
  ],
  "storage_validation": [
    {
      "corruption": "negative_volume",
      "second_status": "EXECUTING",
      "both_simulated_running": true,
      "joint_target_mm": 16
    },
    {
      "corruption": "nan_volume",
      "second_status": "EXECUTING",
      "both_simulated_running": true,
      "joint_target_mm": 16
    },
    {
      "corruption": "missing_file",
      "second_status": "EXECUTING",
      "both_simulated_running": true,
      "joint_target_mm": 16
    }
  ],
  "stop_accounting": [
    {
      "kind": "cancel",
      "first_status": "CANCELLED",
      "reservations_after_stop": {},
      "stopped_receipts": {
        "E": {
          "date": "2026-10-09",
          "delivered_volume_mm": 0.0,
          "device_id": "device",
          "plot_id": "plot",
          "season": "season",
          "target_volume_mm": 8,
          "timestamp": "2026-10-09T13:57:55.467915+00:00"
        }
      },
      "settled_total": {},
      "next_8mm_status": "EXECUTING"
    },
    {
      "kind": "watchdog",
      "first_status": "EMERGENCY_STOPPED",
      "reservations_after_stop": {},
      "stopped_receipts": {},
      "settled_total": {},
      "next_8mm_status": "EXECUTING"
    }
  ],
  "cancelled_operation_replay": {
    "status": "EXECUTING",
    "START_calls": 2
  },
  "stopped_receipt_repeat": {
    "first_settled_mm": 3.0,
    "after_identical_retry_mm": 6.0
  },
  "measured_settlement": [
    {
      "label": "valid_16mm",
      "status": "COMPLETED",
      "reserved_mm": 0.0,
      "settled_mm": 16.0,
      "receipt": {
        "date": "2026-10-09",
        "device_id": "device",
        "plot_id": "plot",
        "season": "season",
        "timestamp": "2026-10-09T13:57:55.479181+00:00",
        "volume_mm": 16.0,
        "zone_id": "zone"
      },
      "replay_original_8mm_status": "FAILED",
      "repeat_actual_volume_l": 0.0
    },
    {
      "label": "valid_4mm",
      "status": "COMPLETED",
      "reserved_mm": 0.0,
      "settled_mm": 4.0,
      "receipt": {
        "date": "2026-10-09",
        "device_id": "device",
        "plot_id": "plot",
        "season": "season",
        "timestamp": "2026-10-09T13:57:55.482433+00:00",
        "volume_mm": 4.0,
        "zone_id": "zone"
      },
      "replay_original_8mm_status": "FAILED",
      "repeat_actual_volume_l": 0.0
    },
    {
      "label": "valid_8mm",
      "status": "COMPLETED",
      "reserved_mm": 0.0,
      "settled_mm": 8.0,
      "receipt": {
        "date": "2026-10-09",
        "device_id": "device",
        "plot_id": "plot",
        "season": "season",
        "timestamp": "2026-10-09T13:57:55.485170+00:00",
        "volume_mm": 8.0,
        "zone_id": "zone"
      },
      "replay_original_8mm_status": "COMPLETED",
      "repeat_actual_volume_l": 0.0
    },
    {
      "label": "known_zero",
      "status": "COMPLETED",
      "reserved_mm": 0.0,
      "settled_mm": 8.0,
      "receipt": {
        "date": "2026-10-09",
        "device_id": "device",
        "plot_id": "plot",
        "season": "season",
        "timestamp": "2026-10-09T13:57:55.487771+00:00",
        "volume_mm": 8.0,
        "zone_id": "zone"
      },
      "replay_original_8mm_status": null,
      "repeat_actual_volume_l": null
    },
    {
      "label": "infinite_litres",
      "status": "COMPLETED",
      "reserved_mm": 0.0,
      "settled_mm": 0.0,
      "receipt": null,
      "replay_original_8mm_status": null,
      "repeat_actual_volume_l": null
    },
    {
      "label": "infinite_area",
      "status": "COMPLETED",
      "reserved_mm": 0.0,
      "settled_mm": 0.0,
      "receipt": null,
      "replay_original_8mm_status": null,
      "repeat_actual_volume_l": null
    },
    {
      "label": "boolean_area",
      "status": "COMPLETED",
      "reserved_mm": 0.0,
      "settled_mm": 8.0,
      "receipt": {
        "date": "2026-10-09",
        "device_id": "device",
        "plot_id": "plot",
        "season": "season",
        "timestamp": "2026-10-09T13:57:55.495485+00:00",
        "volume_mm": 8.0,
        "zone_id": "zone"
      },
      "replay_original_8mm_status": null,
      "repeat_actual_volume_l": null
    }
  ],
  "cold_historical_replay": {
    "first_theta": [
      0.2007,
      0.2218,
      0.2253,
      0.2277,
      0.2295
    ],
    "second_theta": [
      0.173,
      0.2139,
      0.221,
      0.2259,
      0.2295
    ],
    "heads_before": [
      "cp_hyd_P_2026-01-02_f2772ac53036",
      "cp_hyd_P_2026-01-03_15b2c4cb6d22"
    ],
    "replay_theta": [
      0.1489,
      0.2052,
      0.2163,
      0.2239,
      0.2295
    ],
    "replay_step": "2026-01-02",
    "sequence_before": 2,
    "sequence_after": 3,
    "same_original_head": false
  },
  "loser_rollback_erases_winner_RAM": {
    "base_head": "cp_hyd_P_2026-01-02_f2772ac53036",
    "winner_head": "cp_hyd_P_2026-01-03_4293170e59c5",
    "durable_after_loser": "cp_hyd_P_2026-01-03_4293170e59c5",
    "winner_theta": [
      0.2423,
      0.2293,
      0.221,
      0.2259,
      0.2295
    ],
    "loser_outcome": "ConcurrencyConflictError",
    "before_loser_rollback": {
      "history_days": [
        "2026-01-02",
        "2026-01-03"
      ],
      "cached_head": "cp_hyd_P_2026-01-03_4293170e59c5",
      "theta": [
        0.2423,
        0.2293,
        0.221,
        0.2259,
        0.2295
      ]
    },
    "after_loser_rollback": {
      "history_days": [
        "2026-01-02"
      ],
      "cached_head": "cp_hyd_P_2026-01-02_f2772ac53036",
      "theta": [
        0.2007,
        0.2218,
        0.2253,
        0.2277,
        0.2295
      ]
    }
  },
  "individual_dependency_changes": [
    {
      "field": "cycle_id",
      "same_object": false,
      "same_head": false,
      "returned_water": true
    },
    {
      "field": "geometry_version",
      "same_object": false,
      "same_head": false,
      "returned_water": true
    },
    {
      "field": "parameter_epoch",
      "same_object": false,
      "same_head": false,
      "returned_water": true
    },
    {
      "field": "soil_type",
      "same_object": false,
      "same_head": false,
      "returned_water": true
    },
    {
      "field": "timestamp",
      "same_object": false,
      "same_head": false,
      "returned_water": true
    },
    {
      "field": "weather_ensemble",
      "same_object": false,
      "same_head": false,
      "returned_water": true
    }
  ]
}
```

## 9. Independent probe inventory

The inventory accounts for all 68 groups. Each group’s full observed JSON is included in the companion ZIP. Production import manifests embedded in two transcripts are excluded from this group count.

| Harness | Groups | Group identifiers |
|---|---:|---|
| probe | 32 | `failed_stop_retention`; `failed_cancel_retention`; `same_dispatcher_duplicate`; `empty_source_conflict`; `same_process_monitor_quota`; `direct_command_numeric`; `dispatcher_flow_default_laundering`; `idle_ack_loss_no_redose`; `uncertain_start_query_failure`; `offline_status_completion`; `lost_registry_completion`; `validation_gap_releases_quota`; `new_dispatcher_redoses_completed_operation`; `conflicting_identity_false_success`; `inflight_duplicate_false_success`; `bare_executing_misattributed_to_new_operation`; `restart_elapsed_utc`; `restart_naive_start_resets_allowance`; `restart_forgets_stop_requested`; `restart_expired_failed_stop_no_reservation`; `restart_uncertain_releases_reservation`; `elapsed_without_poll`; `elapsed_after_poll`; `settlement_uses_target_not_measurement`; `settlement_not_idempotent`; `yesterday_debit_reduces_new_daily_budget`; `nonfinite_budget_admitted`; `actual_two_process_quota`; `fresh_process_forgets_quota_store`; `two_thread_check_reserve_race`; `weather_numeric_control`; `early_handler_control` |
| hydraulic | 11 | `checkpoint_controls`; `checkpoint_retry_after_head_failure`; `runner_retry_publishes_orphan_cache`; `warm_exact_repeat`; `cold_exact_repeat`; `changed_dependencies_reuse_cached_result`; `fresh_store_failure`; `fresh_CAS_conflict`; `warm_revision_CAS_conflict`; `changed_head_warm_cold`; `withdrawal_roundtrip` |
| adversarial | 10 | `corrupt_quota_fail_open`; `season_identity_lost`; `confirmed_stop_drops_unreconciled_delivery`; `fresh_dispatcher_active_payload_conflict`; `fresh_dispatcher_settled_payload_conflict`; `invalid_restart_timestamp_fresh_allowance`; `missing_registry_restart_elapsed`; `pending_START_blocks_monitor_and_cancel`; `same_event_double_admission`; `stale_live_lock_takeover` |
| edge | 13 | `pending_cancel_applied_before_ack`; `pending_cancel_applied_after_stop`; `pending_watchdog_late_application`; `payload_binding`; `atomic_payload_binding`; `pending_duplicate_failure`; `operation_claim_quota_gating`; `storage_validation`; `stop_accounting`; `cancelled_operation_replay`; `stopped_receipt_repeat`; `measured_settlement`; `cold_historical_replay` |
| concurrency | 1 | `loser_rollback_erases_winner_RAM` |
| dependency | 1 | `individual_dependency_changes` |

## 10. Acceptance conclusion

The commit materially improves the original failure paths. It does not establish complete remediation of Batch A/B or full F08/F09/F16–F19 acceptance. Keep their six tickets open, fix the demonstrated boundaries above, and re-run the original successful controls alongside each new counterexample. Avoid replacing physical uncertainty with optimistic lifecycle labels or replacing a historical prior with the latest posterior.

The next useful work is concrete corrective implementation against these invariants. No additional general audit-document polishing is required to begin that authorized engineering work; full acceptance should follow the relevant integrated evidence, not precede it.

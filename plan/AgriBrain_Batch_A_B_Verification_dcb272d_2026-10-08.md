# AgriBrain — Batch A and expanded Batch B verification

8 October 2026 · Reviewed main: [`dcb272d94c03a8115d3d09d5b800d6b436ec1364`](https://github.com/webClone/AgriWise/commit/dcb272d94c03a8115d3d09d5b800d6b436ec1364) · Parent: `319fd9404da0c88ba9b20669e04cb57c87d6f0cc`.

**Decision: this revision closes many earlier counterexamples, but Batch A and expanded Batch B are partially remediated. Continue corrective implementation now. Keep their full acceptance open and resolve the remaining transactional, delivery-accounting and hydraulic-replay failures before accepting dependent integrated capabilities.**

The file-backed quota mechanism works for the exercised normal shared-directory contention. Command serialization prevents the previous in-flight false acknowledgement. Hydraulic head changes refresh the exercised warm state, and withdrawal dates survive restart. Those improvements are real.

However, exact hydraulic replay after cold restart still integrates the same day again; checkpoint persistence failure still returns an ordinary water result; failed head publication can be mistaken for a successful committed retry; corrupt quota files erase exposure; concurrent owners of the same operation can both dispatch; and normal settlement loses the budget's season identity. These are production-function counterexamples rather than conclusions drawn from test totals.

## 1. Scope and evidence

- Main was pinned and rechecked at the reviewed SHA. The commit is dated 8 October 2026, 18:37:41 UTC.
- All **seven changed production Python files** were inspected and parsed: the four irrigation runtime files, Layer 3 decision runner, canonical worldline service, and ASMAE background-job queue.
- An isolated runtime contains **430 production Python files**, all byte-matched to Git blob identities at this commit. The completed probes imported **93 distinct production files**, all hash-verified.
- **53 independent probe groups** completed without unresolved harness errors: 32 earlier command/numeric/control groups, 11 hydraulic/store groups, and 10 additional failure/concurrency groups. A group can include several variants; this count is not a repository test-suite pass count.
- Existing repository tests, reported pytest totals, audit assertions and earlier correctness reports were excluded as correctness evidence. The claimed `358 passed, 128 subtests passed` was not independently rerun or certified here.
- The command drivers were controlled simulations. Actual spawned processes and threads exercised the real production quota/dispatcher functions. No field hardware, valve, pump, live irrigation output or external controller was operated.
- Quota process tests shared one directory on one machine. They establish that topology, not distributed replica behavior on separate filesystems, power-loss durability or deployment-volume configuration.
- Fault probes injected explicit errors at production I/O boundaries. The orphan-head example models interruption between checkpoint write and head publication; it is not a claim that a physical power-loss experiment was performed.
- The R3 master monograph's scientific contracts and requirement register remain the target. F/T package IDs belong to the repair plan; AB-* IDs belong to R3. This report keeps implementation status outside the scientific monograph.
- This is a deep review of this revision and relevant production dependencies, not a fresh exhaustive audit of every AgriBrain module or every plan document.
- No repository production files were changed, pushed or merged during this review. Probe state and fault injection were confined to the isolated review workspace.

## 2. Verified improvements

| Earlier boundary | Current independent result | Scope of conclusion |
|---|---|---|
| Failed STOP/cancellation | STOP_REQUESTED retains original START context, monitoring and 8 mm reservation; explicit later polling retries STOP. | The earlier failed-STOP removal counterexample is closed. Delivery reconciliation after a successful stop remains incomplete. |
| Unknown START | ACK loss plus failed status query retains STOP_REQUESTED, active event, watchdog entry and reservation. Idle ACK loss does not redose. | The earlier immediate ownership-loss case is closed after the dispatch function returns. A pending/hung send is a separate gap. |
| OFFLINE/registry loss | Active tracking and quota remain; no premature FAILED/VALIDATING finalization. | Verified on the exercised execution branches. |
| Distinct-request quota contention | Two spawned processes requesting 8 mm each against 10 mm admit only one; accepted total is 8 mm. Two threads also dispatch at most one. | Verified for distinct event IDs on a healthy shared directory. |
| Fresh-process visibility | A new process sees the parent's 8 mm reservation and 1 mm settled amount. | File-backed cross-process visibility works; this is not a full crash/power-loss certification. |
| Validation accounting window | Entering VALIDATING preserves 8 mm as UNSETTLED; a second 8 mm request against 10 mm is blocked. | The earlier immediate release window is closed. |
| Same-event completed replay | A fresh dispatcher recognizes an existing settlement and avoids another START. | Works for this sequential same-payload case; it does not validate changed payloads or atomically own concurrent admission. |
| In-flight duplicate | Duplicate waits for the original outcome; when original dispatch fails, duplicate does not falsely report success. | The original optimistic EXECUTING false-ACK case is closed within one actuator instance. |
| Conflicting actuator payload | Different delivery parameters under the same source-event ID are rejected. | Actual error code is VALIDATION_FAILED, because validation runs before the later PAYLOAD_CONFLICT branch. |
| Bare EXECUTING after failed START | Returns UNCERTAIN_OUTCOME instead of attributing an unrelated running controller to the new command. | The previous misattribution case is closed. |
| Raw flow | Negative and boolean flow are rejected with zero sends; numeric zero remains zero. | The 15 L/min laundering counterexample is closed. |
| Direct command numbers | The 18 invalid combinations are rejected, with zero sends. | This remains a passing control. |
| Restart | Valid UTC and naive-as-UTC nine-minute starts exceed a ten-minute allowance after two further minutes and stop on polling. STOP_REQUESTED is not changed back to ordinary EXECUTING. Failed expired STOP restores monitoring/reservation/context. | These nominal cases are corrected. Invalid timestamps and pending send deadlines remain. Naive timestamp interpretation needs an explicit UTC policy. |
| R07 warm repeat | Identical request returns the same WaterState object, unchanged VWC and unchanged head/sequence. | Warm idempotence works; cold idempotence fails. |
| R08 checkpoint payload immutability | Modified payload under an existing ID is rejected. Identical retry returns the existing receipt without sequence advancement. Stale predecessor is rejected for a new ID. | These controls pass; orphan-head recovery and full record identity remain incomplete. |
| R09 changed durable head | Warm and cold next-day profiles agree after a foreign supported head: top-layer VWC 0.2412 in both; warm predecessor is the foreign head. | The earlier stale-soil-cache reproduction is closed. This does not certify every coupled registry or scope migration. |
| R10 new water-memory publication | Fresh CAS rejection leaves no new water-memory entry or new computed history record. | Improved, but earlier evidence mutations and warm history deletion remain outside the candidate transaction. |
| R12 withdrawal dates | ISO soil-withdrawal date persists and is recovered on the next cold execution. | The original serialization mismatch is closed in this round-trip case. |
| R17 traversal | The previous checkpoint-ID traversal is rejected. | Actual exception is ValueError, not the claimed SecurityViolation. No external HTTP exploit path was established. |
| R13/R15 controls | Early malformed timestamp returns `(None, None)` without import-shadowing failure. Boolean precipitation is rejected; numeric zero rain remains 0.0 mm. | These previously verified boundaries remain corrected. |

ASMAE's additional queue change removes the manifest-hash predicate from queue enumeration. Source inspection also shows that lease entry still rejects a missing manifest hash. This review does not claim that unqualified jobs now execute, nor does it certify deployed queue liveness; that worker path was not exercised here.

## 3. Remaining findings

V-* identifiers below are local review labels, not new canonical packages. Priorities describe the repair urgency of these observed boundaries.

### V01 — P0 — Corrupt quota storage is treated as zero exposure

`SharedQuotaStore._read_state()` returns an empty reservation/settlement structure when the file is blank, malformed JSON, the wrong JSON type, or unreadable. That behavior also occurs after a previously valid store has recorded an active operation.

**Reproduction:** admit an 8 mm operation against a 10 mm budget, then replace only the isolated quota file with malformed JSON, empty text or `[]`. A second 8 mm operation becomes EXECUTING in every variant. Both simulated drivers are running, START applications = 2, but the rewritten store records only 8 mm.

**Repair:** distinguish explicit new-store initialization from loss/corruption of an established ledger. Validate state schema and quantities. Corruption or I/O failure must return a typed admission-blocked/storage-failure outcome, preserve reconciliation evidence and prohibit silent ledger reset. Recovery must establish outstanding exposure from authoritative receipts/controllers before admitting new physical work.

**Acceptance:** corrupt, truncated, wrong-schema, missing-established-store and unreadable-state scenarios produce zero new START calls until qualified recovery. Existing operations retain a bounded safety/reconciliation path.

**R3:** AB-EXE-004; AB-ARC-006/008; AB-DAT-012. **Packages:** F16/F18 and persistence foundations.

**Source:** [safety.py:123–185](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/safety.py#L123-L185).

### V02 — P0, conditional — Age-only lock takeover can break mutual exclusion

The mechanism is an exclusive-create lock file using O_CREAT/O_EXCL. It is not a process-lifetime advisory lock. A contender deletes the lock once its modification time is older than 30 seconds; it neither establishes owner death nor fences the prior writer. Any owner finally unlinks the pathname without checking that it still owns that lock generation.

**Reproduction:** one real child process holds the production critical section. The isolated lock file's mtime is deliberately aged beyond the threshold, without waiting 30 seconds. A second owner enters while the first is still alive and unreleased. Releasing the first causes it to remove the second owner's lock file. The probe verifies the stale-condition branch and overlapping ownership; it does not claim a real field transaction already lasted 30 seconds or directly measure quota overspend from this particular case.

**Repair:** use a lock whose exclusion follows process/file-descriptor lifetime for the supported filesystem, or a verified renewable lease with immutable ownership token and fencing. A displaced owner cannot write or unlink a successor's lock. Define the deployment shared-storage contract and failure behavior. Increasing the TTL alone does not establish exclusion.

**Acceptance:** a slow live owner cannot be displaced into concurrent unfenced publication. Owner crash is recoverable; stale owners cannot publish or release successor ownership. Exercise the actual production filesystem/replica topology.

**R3:** AB-ARC-008; AB-EXE-004. **Packages:** F16/F18 and shared concurrency foundations.

**Source:** [safety.py:94–121](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/safety.py#L94-L121). The worldline head lock has an analogous age-only pattern with a different threshold; that separate pattern was inspected, not independently raced in this run.

### V03 — P0 — Operation identity is not atomically admitted or bound to payload

Three cases remain despite successful serialization within one actuator instance:

1. Two threads use separate dispatcher/driver instances for the **same event ID, same device and same delivery request**. A barrier after the real `is_active()` read exposes both legitimate false reads. Both later atomic quota admissions succeed because each excludes/overwrites the same event key. Both events become EXECUTING, each driver receives START, and the store records only one 8 mm reservation.
2. A fresh dispatcher submits the existing active event ID with a 12 mm target while the driver is executing its original 8 mm command. The early durable-active branch returns the new request as EXECUTING; the actuator's payload guard is never reached.
3. After settlement of the original 8 mm event, a fresh dispatcher submits that ID with a 12 mm target. The early settled branch returns the new request as COMPLETED, actual liters still 0, with no payload comparison and without returning the original qualified receipt.

The synchronized thread probe schedules the check/claim interleaving; it does not replace the production admission algorithm. It demonstrates duplicate sends at the simulated driver boundary, not field delivery measurement.

**Repair:** one scoped atomic operation claim must precede physical I/O. Include canonical payload digest, owner/fence, lifecycle and original result/unknown receipt. Same identity with changed content is a conflict. A duplicate returns or joins the stored operation, including pending/UNSETTLED outcomes; it must not assign status to the caller's altered object. Scope settlement and active lookup fully; the current optional plot arguments are not used to qualify identity.

**Acceptance:** independent owners of the same operation send START at most once; distinct requests still respect quota. Active, pending, completed, unsettled and stopped duplicates return the original typed receipt. Changed plot/device/delivery content is rejected rather than fabricated as success.

**R3:** AB-EXE-002/003; AB-ARC-008/009; AB-DAT-013. **Packages:** F17/F18.

**Sources:** [dispatcher.py:158–199](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/dispatcher.py#L158-L199), [safety.py:236–303](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/safety.py#L236-L303), [safety.py:388–399](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/safety.py#L388-L399).

### V04 — P0 — Delivery reconciliation still loses season and potentially delivered water

**Season mismatch:** atomic admission records `budget.season`, but `track_event_start()` calls `reserve()` again, replacing the record without that season. `settle_quota()` passes neither season nor date, and `settle()` therefore writes `default_season` and the current date.

**Reproduction:** budget season = `season`, season remaining = 10 mm, daily remaining = 100 mm. Complete an 8 mm operation, then submit another 8 mm operation against that season. The second becomes EXECUTING. Receipt season is `default_season`; settled plus reserved exposure = **16 mm** against the **10 mm** seasonal cap. The generous daily allocation isolates the seasonal defect.

**Stopped delivery:** successful cancellation after START removes the reservation and records no settlement/unsettled-delivery receipt. A later 8 mm request is admitted. Confirming physical cessation does not establish that earlier delivered water was zero. This probe shows lost accounting for a started-and-stopped operation, not a measured claim that the first delivered exactly 8 mm.

**Measured depth:** completion still records actual liters but settles the planned target depth. The 160,000 L probe settles the 8 mm target unchanged. No qualified area is present on the event, so an actual depth cannot be inferred from those liters here. For qualified effective area A in hectares, depth is `I_mm = V_L / (10,000 × A_ha)`.

Store-level duplicate settlement is now idempotent, and the reset-daily-budget control with an explicitly earlier delivery date passes. Those positive controls do not fix the dispatcher's missing period propagation or measured/unknown-delivery distinction.

**Repair:** preserve immutable period/scope metadata from admission to delivery receipts. Transfer active exposure to unsettled delivery on normal completion, cancellation, safety stop and recovery. Reconcile qualified measured volume/depth, area/version, delivery interval and uncertainty; retain a conservative bound where actual delivery is unknown. Allocate periods by delivery support, not blindly by callback time. Corrections require receipt lineage rather than silently changing planned quantities into observations.

**Acceptance:** completed/partial/stopped/unknown delivery is accounted exactly once in the correct day and season; no metadata is lost on tracking restoration. Vary actual volume and area independently. Duplicate receipts remain idempotent; changed receipt content requires explicit conflict or revision handling.

**R3:** AB-EXE-002/004; AB-DAT-007/010/013. **Packages:** F16/F18 and delivery consumers.

**Sources:** [safety.py:307–377](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/safety.py#L307-L377), [safety.py:529–577](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/safety.py#L529-L577), [dispatcher.py:504–557](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/dispatcher.py#L504-L557).

### V05 — P1 — Invalid-budget reporting raises NameError

`submit_event()` validates the budget, but its error receipt uses `finite_real(event.target_volume_mm)` without importing/defining `finite_real` in the dispatcher module.

**Reproduction:** valid 8 mm event plus NaN or infinity in budget remaining fields raises `NameError: name 'finite_real' is not defined`. Driver sends = 0. The raw guard prevents dispatch in these cases, which is an improvement; the promised typed failure receipt is still broken.

**Repair:** use the canonical helper with a valid module import or the already-qualified event value. Exercise invalid budget type/value branches at the dispatcher boundary, not only `WaterBudget.validate()` directly.

**Acceptance:** invalid budgets return explicit FAILED/admission-blocked outcomes with zero sends, preserve the intended error details and raise no secondary handler exception.

**Source:** [dispatcher.py:130–153](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/dispatcher.py#L130-L153).

### V06 — P0 — Deadline safety is incomplete during pending send and malformed recovery

**Pending START:** the simulated driver applies START but holds its acknowledgement. Advance the injected monotonic clock beyond the ten-minute target and explicitly poll the real dispatcher. The event remains DISPATCHING, driver running = true, STOP calls = 0, monitor entries = []. Reservation is retained, but duration tracking is installed only after send returns. A concurrent `cancel_event()` also remains pending behind the actuator dispatch lock. After the controlled ACK is released, cancellation finally sends STOP.

This probe models a delayed/hung driver acknowledgement. It does not assert that every existing hardware driver lacks its own timeout or deadline. The framework cannot claim bounded physical-command safety without establishing that driver contract or enforcing its own boundary.

**Invalid restart timestamp:** an EXECUTING persisted event with `actual_start='not-a-timestamp'` receives elapsed = 0 and a fresh allowance. After two post-restart minutes it remains running. The exception fallback is not restricted to unstarted DISPATCHING events.

**Missing-registry recovery:** the early branch restores tracking without calculating the persisted elapsed time; the monitored start is the new clock origin. Stop intent remains and registry loss is retained, but original elapsed duration is not restored there.

**Caller scheduling:** advancing the fake clock alone still does not cause STOP. An explicit poll does. Autonomous scheduler/hardware watchdog deployment was not independently exercised.

**Repair:** persist/track a conservative execution deadline before physical send can apply, bound driver I/O and provide a stop path that cannot wait indefinitely behind a hung START. Preserve pending/unknown ownership on cancellation or timeout. Parse recovery timestamps under an explicit policy; malformed/unknown elapsed time cannot become a fresh permitted runtime. Restore deadline/exposure before every registry/query branch. Verify independent scheduling/controller cutoffs without telemetry.

**Acceptance:** START-applied/ACK-pending, hung send, cancelled coroutine, expired pending execution, malformed/missing start, missing registry and restart cannot evade a bounded deadline. STOP can be issued or enforced independently within its declared communication/controller bound.

**R3:** AB-EXE-002/003/004. **Packages:** F16/F17/F18.

**Sources:** [dispatcher.py:226–271](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/dispatcher.py#L226-L271), [dispatcher.py:605–633](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/dispatcher.py#L605-L633), [actuator.py:267–401](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/irrigation_runtime/actuator.py#L267-L401).

### V07 — P1 — Cold exact replay still integrates an already committed day

Warm replay is now stable. Cold recovery omits the target day from hydrated history and sets water memory to the checkpoint's final posterior. The subsequent identical request has no target WaterState/feedback receipt to return and can integrate that posterior over the same day again.

| Exact request | Top-layer VWC | Head sequence |
|---|---:|---:|
| Initial execution | 0.2007 | 1 |
| Identical warm repeat | 0.2007 | 1 |
| Identical cold repeat after clearing RAM | 0.1730 | 2 |

All five layer values appear in the receipts. Input timestamp, weather, plot, vegetation and scope are unchanged. This is repeated integration, not a serialization-tolerance error.

**Repair:** persist immutable transition identity and the full committed output/feedback needed to hydrate a repeat, with stable initial and final states and exact predecessor lineage. An already committed interval is retrieved, not re-solved from its posterior. Revisions replay from the initial predecessor of the affected transition.

**Acceptance:** warm/cold/process-restart repeats preserve state, head and sequence exactly. Repeated and revised intervals have distinct, reproducible lineage; daily/sparse execution agrees under declared physical tolerances.

**R3:** AB-AGR-007; AB-DAT-011/012; AB-ARC-008. **Packages:** F08/F09.

**Sources:** [runner.py:1217–1279](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/layer3_decision/runner.py#L1217-L1279), [runner.py:1939–2001](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/layer3_decision/runner.py#L1939-L2001).

### V08 — P1 — The new warm shortcut omits scope and parameter dependencies

The new forcing-hash shortcut considers weather, irrigation, selected vegetation/soil observations and cached initial soil/predecessor hashes. It does not bind the returned transition to cycle, geometry, parameter epoch, soil-type policy, issuance timestamp or weather ensemble.

**Reproduction:** after one committed result, one combined follow-up changes cycle C→C2, geometry G→G2, parameter epoch v1→v2, soil type to sand and timestamp by six hours. The runner returns the same WaterState object and same head, with the old cycle/geometry/parameter epoch and old result timestamp. This combined scenario was executed; the omitted individual dependencies are also visible in the source hash.

Sharing an unchanged daily physical calculation can be valid when its interval/support is explicitly the same. It cannot silently treat a changed geometry/cycle/parameter epoch as an identical scoped transition. A separate issuance/response receipt is needed when scientific state is shared across requests.

**Repair:** define and hash the complete scientific transition dependencies, scope and parameter/model versions. Handle scope change by qualified migration or rejection. Separate valid interval from request/issuance identity, and recompute forecast/response objects where those dependencies change.

**Acceptance:** parameter, geometry, cycle and relevant ensemble changes cannot return an unqualified stale artifact. Legitimate calculation sharing preserves support and produces correctly bound response/issuance receipts.

**R3:** AB-DAT-008/011/012/013; AB-ARC-009. **Packages:** F08/F09 and consumers.

**Sources:** [runner.py:1165–1171](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/layer3_decision/runner.py#L1165-L1171), [runner.py:1777–1807](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/layer3_decision/runner.py#L1777-L1807), [runner.py:1939–1964](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/layer3_decision/runner.py#L1939-L1964).

### V09 — P1 — Candidate isolation does not cover all RAM changes

The new candidate dictionaries defer newly computed water-memory and history updates. Before those dictionaries exist, the runner still mutates vegetation, management/soil registries and withdrawal sets, and removes prior history during invalidation.

**Fresh CAS fault:** no new water-memory entry is published, but a vegetation-history entry for the failed day remains after the function raises ConcurrencyConflictError.

**Warm revision CAS fault:** a committed `2026-01-02` history entry exists before a changed-rain request. The injected commit conflict leaves that history empty afterward, while the prior water-memory entries remain. Thus `plot_hist` itself is still changed before successful CAS.

**Repair:** stage invalidation, evidence/history maps, initial states, withdrawal sets, events, head tokens and computed state together. Alternatively, independently commit admitted evidence with explicit durable receipts and version binding before using it; mere RAM mutation is not such a transaction. On failed state commit, preserve/reload a coherent authoritative snapshot and discard unpublished derived candidates.

**Acceptance:** every coupled registry either belongs to the old committed snapshot or to a separately committed evidence revision. No rejected candidate or uncommitted deletion survives as if bound to the accepted head.

**R3:** AB-DAT-012; AB-ARC-007/008. **Package:** F09.

**Sources:** [runner.py:1348–1519](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/layer3_decision/runner.py#L1348-L1519), [runner.py:1903–1914](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/layer3_decision/runner.py#L1903-L1914), [runner.py:2033–2062](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/layer3_decision/runner.py#L2033-L2062).

### V10 — P1 — R11 persistence failure still returns an ordinary water result

The non-CAS persistence catch still logs and suppresses the exception, then returns `last_water_state, last_feedback`. Candidate isolation improves RAM behavior but does not supply a committed/degraded result distinction to the caller.

**Reproduction:** inject OSError at `save_hydraulic_checkpoint()`. Returned WaterState is non-null, with top-layer VWC 0.2007; there is no committed checkpoint. New water-memory entries remain absent, which is a positive change. The ordinary returned tuple does not carry a durable-commit failure receipt. The water model's normal physics authority is distinct from persistence status.

**Repair:** return or raise a typed commit failure. Diagnostic computation may remain available under an explicit limited contract; consumers requiring committed canonical state must not receive ordinary success. Couple this to V09 rollback/reload and caller propagation.

**Acceptance:** store outage cannot produce an indistinguishable committed result. Verify the Layer 3 caller and downstream decisions, not only the internal save function.

**R3:** AB-DAT-003/012; AB-ARC-006/007/008. **Package:** F09.

**Source:** [runner.py:2195–2224](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/layer3_decision/runner.py#L2195-L2224).

### V11 — P1 — An identical retry can certify an orphan checkpoint without publishing its head

Checkpoint data and hydraulic head are separate writes. The new existing-ID branch compares payload and returns before establishing committed head membership or handling an interrupted publication.

**Direct store reproduction:** checkpoint file ORPHAN is written, then the head write raises OSError. Retrying the identical checkpoint returns success, but `load_latest_hydraulic_checkpoint()` remains null and the head file does not exist.

**Runner reproduction:** repeat the same interruption through the real Layer 3 save path. First call returns water despite the head error. Retry returns water again and publishes two water-memory aliases plus `_PLOT_CURRENT_HEAD=cp_hyd_...`; the durable latest checkpoint is still null. This defeats the intended “RAM only after successful CAS checkpoint persistence” guarantee.

**Record identity qualification:** matching only payload also accepts changed requested cycle/geometry metadata under an existing ID, returning the old default metadata. The immutable scientific record identity includes more than the payload object.

**Repair:** distinguish prepared checkpoint content from a committed transition/head receipt. On identical retry, verify the full immutable record identity and durable publication state. Recover interrupted head publication only through a safe current-head/predecessor transaction; otherwise return the existing historical receipt with explicit status or reject. The runner must validate the committed receipt/head it actually received before publishing RAM. Preserve append-only lineage and forbid self-parent/cyclic recovery.

**Acceptance:** failures before checkpoint write, after checkpoint write and before/after head publication recover idempotently. No successful committed receipt or cached authoritative head exists while durable head membership is absent. Changed metadata cannot masquerade as an identical record.

**R3:** AB-DAT-003/011/012/013; AB-ARC-007/008. **Package:** F09.

**Sources:** [canonical_worldline.py:275–332](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/world_model/canonical_worldline.py#L275-L332), [runner.py:2181–2208](https://github.com/webClone/AgriWise/blob/dcb272d94c03a8115d3d09d5b800d6b436ec1364/services/agribrain/layer3_decision/runner.py#L2181-L2208).

## 4. Current plan and acceptance state

The task register is unchanged at blob `8a564647af7e588802537817159117b349ff606b`. ST06-F16-FA, ST06-F17-FA, ST06-F18-FA and ST06-F19-FA remain open `[ ]`, as claimed. Preserve those open milestones. F19's complete persistence/debounce scope is not established by this review of the Batch A/B changes.

| Existing claim | Correct current status |
|---|---|
| BA-01 | Earlier returned-uncertainty, OFFLINE and registry-loss retention cases corrected; pending send and post-stop delivery reconciliation still need work. |
| BA-02 | Healthy shared-directory distinct-ID contention corrected; corrupt state, lock takeover and same-operation ownership remain. |
| BA-03 | Same-instance serialization and actuator conflict/misattribution controls corrected; durable admission/payload binding remain. |
| BA-04 | Raw flow laundering corrected; invalid-budget failure receipt has a new NameError. |
| BA-05 | Nominal UTC/naive-as-UTC recovery and stop-intent cases corrected; malformed starts/pending-send bounds and full scheduler evidence remain. |
| BA-06 | Normal VALIDATING→UNSETTLED window corrected; stopped/unknown delivery paths remain incomplete. |
| BA-07 | Duplicate receipt and explicit period-store controls improved; dispatcher season propagation and measured/unknown delivery are incomplete. |
| R07 | Warm exact-repeat corrected; cold repeat and complete dependency identity fail. |
| R08 | Basic payload immutability/identical retry corrected; interrupted publication and full record identity fail. |
| R09 | Exercised foreign-head warm/cold state control corrected; full scope/registry integration is not certified. |
| R10 | New calculated water state is staged; history invalidation and other RAM mutations remain outside the commit transaction. |
| R11 | Still open: non-CAS persistence failure returns the ordinary water tuple. |
| R12 | Original ISO withdrawal serialization/hydration counterexample corrected. Keep integrated commit-failure/replay acceptance tied to R10/R11. |
| R17 | Original ID traversal counterexample corrected; align the typed exception with the documented SecurityViolation contract. |
| R13/R15 | Previously corrected boundaries remain passing controls. |

R14 temporal admission and R16 conductivity precision were not the claimed scope of this commit and were not fully re-audited here. Do not infer their completion from the Batch A/B title or reported overall test total.

## 5. Detailed follow-up implementation plan

Use the existing canonical packages and keep each package's full acceptance separate from its implementation slices. The following tracks can progress concurrently where their actual dependencies permit.

### Track A — Shared operation and delivery transactions

1. **Typed numeric/storage admission:** fix V05; distinguish a new quota store from V01 corruption/unavailability. Validate every persisted ledger field and return typed failures without erasing the ledger. Add outage recovery receipts and reconciliation state.
2. **Verified ownership primitive:** fix V02 before depending on it for atomic publication. Specify storage sharing, lock/lease lifecycle, renewal/fencing and owner-death recovery. Ensure a stale owner cannot remove or write under successor ownership.
3. **One atomic operation claim:** fix V03 by moving operation existence, payload comparison, budget admission, reservation and owner acquisition into one transaction. Include full scope and immutable command content. Return canonical stored pending/completed/unknown receipts rather than relabelled caller objects.
4. **Durable pre-send intent/deadline:** fix V06. Persist and monitor exposure before sending. Bound send/status/stop operations, support an independent stop/deadline path, and preserve uncertainty through cancellation or communication failure. Validate recovery time explicitly; normalize only under a declared timestamp policy.
5. **One delivery lifecycle:** fix V04. Preserve season/date/scope from admitted operation; transition running→unsettled→settled atomically on every completion/stop/recovery path. Carry qualified area, volume/depth, delivery interval and uncertainty. Distinguish planned target from measured delivery and partial/unknown delivery.
6. **Integrated acceptance matrix:** distinct-ID and same-ID contention across independent processes/threads; changed payload/scope; kill before/after send; lost ACK; hung send; stop during pending send; corrupted ledger; slow live owner; settled retry; correction receipt; day/season rollover; partial stop; measured volume/area; invalid budget; recovery timestamps; store outage. Run the matrix against the actual supported shared store and driver capability boundary.

**Exit:** at most one owner can issue the logical operation; no unqualified success receipt exists; all delivered/unresolved exposure remains counted; deadlines remain bounded independent of new telemetry.

### Track B — Durable hydraulic transition and replay

1. **Committed transition representation:** fix V07/V08. Persist complete immutable initial/final hydraulic state, feedback/output, interval support, scope, predecessor and all admitted evidence/model/parameter dependencies. Distinguish computation identity from issuance/response identity. Hydrate identical repeats without another solve.
2. **Prepared-versus-committed persistence:** fix V11. Define the checkpoint/head publication transaction and interrupted-publication recovery. Compare the full immutable record, validate predecessor/head state on retry, and return a committed receipt the runner can verify. Preserve containment and existing conflict controls.
3. **All coupled candidate state:** fix V09. Stage maps, tombstones, evidence revisions, invalidation, history, initial states, memory and head tokens. Publish only after the verified commit; otherwise discard/reload coherently. Independently durable evidence ingestion is acceptable if explicitly versioned and receipted.
4. **Typed durability propagation:** fix V10. A failed commit must be visible in the result or exception and propagated through the real Layer 3 caller. Diagnostic calculations remain explicitly scoped; no silent ordinary success.
5. **Full F08/F09 acceptance:** warm/cold exact repeat; earlier-date replay; sparse/daily integration; corrected weather/irrigation/soil/vegetation; withdrawal; scope/parameter change; supported head replacement; competing writers; orphan checkpoint; store/head corruption; commit interruption; failed CAS; typed caller propagation. Numerical tolerances apply to defined solver quantities and discretization, not to a repeated-day state drift.

**Exit:** one identical interval has one committed transition; a changed request has an explicit correct dependency/scope receipt; failed commits cannot seed accepted RAM or success outputs; cold replay and revision lineage are reproducible.

### Track C — Plan reconciliation and independent scientific work

1. Update implementation receipts with this commit and the exact passing/failing subcases. Keep full acceptance unchecked until integrated criteria pass; do not mark a package complete solely because these code changes or test totals exist.
2. Retain corrected positive controls, especially healthy shared quota, failed-STOP retention, invalid flow rejection, warm identity, foreign-head refresh, withdrawal round-trip and checkpoint immutability.
3. Continue independent temporal-admission/precision repairs and objective-specific world-model/Omega research where their own evidence requirements permit. Integrated capability acceptance must retain the intervening canonical prerequisite packages; this review neither authorizes skipping them nor prohibits all exploratory work.

## 6. Production identities

| Repository path | Git blob |
|---|---|
| services/agribrain/irrigation_runtime/actuator.py | d7a604b6a1ff443260ed495e81e816918c7453ad |
| services/agribrain/irrigation_runtime/dispatcher.py | 07674ed5ae71b9ad646b52a00d6a0460a02271f1 |
| services/agribrain/irrigation_runtime/safety.py | f0c26b764aa9a8eff9c5f9b77fc28423f1c56066 |
| services/agribrain/irrigation_runtime/schemas.py | d3f4f5ffa025ca551692765ce813ad517d7a366f |
| services/agribrain/layer05_asmae/background_jobs.py | 013703462d50e94042425b2790367d0a76d6847d |
| services/agribrain/layer3_decision/runner.py | 903738ef5f548b54b5f144701b1ea11a2134cfcf |
| services/agribrain/world_model/canonical_worldline.py | de6e02655a1ac64f2fe9ea501e6dd7ecb2052dd3 |

## 7. Independent probe receipts

The following output comes from calls to the hash-verified production classes/functions. Names retained from the earlier harness, such as `physical_running` or `physical_start_calls`, refer to simulated driver behavior. Historical counterexample names are retained so before/after comparisons remain possible; read their current values rather than treating the name as a current failure claim. The earlier-date quota control now supplies an explicit earlier delivery date. Runtime import inventories were checked separately and are omitted for readability.

### Earlier command and numeric controls

```json
{
  "failed_stop_retention": {
    "first": {
      "event_status": "STOP_REQUESTED",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 1,
      "active_events": 1,
      "tracked_events": [
        "E"
      ],
      "reserved_mm": 8.0,
      "settled_mm": 0.0,
      "delivery_context": "START_ZONE"
    },
    "second": {
      "event_status": "STOP_REQUESTED",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 2,
      "active_events": 1,
      "tracked_events": [
        "E"
      ],
      "reserved_mm": 8.0,
      "settled_mm": 0.0,
      "delivery_context": "START_ZONE"
    }
  },
  "failed_cancel_retention": {
    "event_status": "STOP_REQUESTED",
    "physical_running": true,
    "physical_start_calls": 1,
    "physical_stop_calls": 1,
    "active_events": 1,
    "tracked_events": [
      "E"
    ],
    "reserved_mm": 8.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "same_dispatcher_duplicate": {
    "same_object": true,
    "physical_start_calls": 1
  },
  "empty_source_conflict": {
    "successes": [
      true,
      false
    ],
    "physical_start_calls": 1
  },
  "same_process_monitor_quota": {
    "statuses": [
      "EXECUTING",
      "FAILED"
    ],
    "reserved_mm": 8.0
  },
  "direct_command_numeric": {
    "invalid_rows": [
      {
        "field": "volume_mm",
        "value": "nan",
        "success": false,
        "sends": 0
      },
      {
        "field": "volume_mm",
        "value": "inf",
        "success": false,
        "sends": 0
      },
      {
        "field": "volume_mm",
        "value": "True",
        "success": false,
        "sends": 0
      },
      {
        "field": "volume_mm",
        "value": "False",
        "success": false,
        "sends": 0
      },
      {
        "field": "volume_mm",
        "value": "'8'",
        "success": false,
        "sends": 0
      },
      {
        "field": "volume_mm",
        "value": "-1",
        "success": false,
        "sends": 0
      },
      {
        "field": "duration_minutes",
        "value": "nan",
        "success": false,
        "sends": 0
      },
      {
        "field": "duration_minutes",
        "value": "inf",
        "success": false,
        "sends": 0
      },
      {
        "field": "duration_minutes",
        "value": "True",
        "success": false,
        "sends": 0
      },
      {
        "field": "duration_minutes",
        "value": "False",
        "success": false,
        "sends": 0
      },
      {
        "field": "duration_minutes",
        "value": "'8'",
        "success": false,
        "sends": 0
      },
      {
        "field": "duration_minutes",
        "value": "-1",
        "success": false,
        "sends": 0
      },
      {
        "field": "flow_rate_lpm",
        "value": "nan",
        "success": false,
        "sends": 0
      },
      {
        "field": "flow_rate_lpm",
        "value": "inf",
        "success": false,
        "sends": 0
      },
      {
        "field": "flow_rate_lpm",
        "value": "True",
        "success": false,
        "sends": 0
      },
      {
        "field": "flow_rate_lpm",
        "value": "False",
        "success": false,
        "sends": 0
      },
      {
        "field": "flow_rate_lpm",
        "value": "'8'",
        "success": false,
        "sends": 0
      },
      {
        "field": "flow_rate_lpm",
        "value": "-1",
        "success": false,
        "sends": 0
      }
    ],
    "valid_zero_success": true
  },
  "dispatcher_flow_default_laundering": [
    {
      "input_flow": "-1",
      "status": "FAILED",
      "sends": 0,
      "sent_flow": null
    },
    {
      "input_flow": "False",
      "status": "FAILED",
      "sends": 0,
      "sent_flow": null
    },
    {
      "input_flow": "0",
      "status": "EXECUTING",
      "sends": 1,
      "sent_flow": 0
    }
  ],
  "idle_ack_loss_no_redose": {
    "event_status": "STOP_REQUESTED",
    "physical_running": false,
    "physical_start_calls": 1,
    "physical_stop_calls": 0,
    "active_events": 1,
    "tracked_events": [
      "E"
    ],
    "reserved_mm": 8.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "uncertain_start_query_failure": {
    "event_status": "STOP_REQUESTED",
    "physical_running": true,
    "physical_start_calls": 1,
    "physical_stop_calls": 0,
    "active_events": 1,
    "tracked_events": [
      "E"
    ],
    "reserved_mm": 8.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "offline_status_completion": {
    "event_status": "STOP_REQUESTED",
    "physical_running": true,
    "physical_start_calls": 1,
    "physical_stop_calls": 0,
    "active_events": 1,
    "tracked_events": [
      "E"
    ],
    "reserved_mm": 8.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "lost_registry_completion": {
    "event_status": "STOP_REQUESTED",
    "physical_running": true,
    "physical_start_calls": 1,
    "physical_stop_calls": 0,
    "active_events": 1,
    "tracked_events": [
      "E"
    ],
    "reserved_mm": 8.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "validation_gap_releases_quota": {
    "after_idle_before_validation": {
      "event_status": "VALIDATING",
      "physical_running": false,
      "physical_start_calls": 1,
      "physical_stop_calls": 0,
      "active_events": 1,
      "tracked_events": [],
      "reserved_mm": 8.0,
      "settled_mm": 0.0,
      "delivery_context": "START_ZONE"
    },
    "second_status": "FAILED",
    "after_first_settlement_reserved_mm": 0.0,
    "settled_mm": 8.0
  },
  "new_dispatcher_redoses_completed_operation": {
    "status": "COMPLETED",
    "physical_start_calls": 1
  },
  "conflicting_identity_false_success": {
    "successes": [
      true,
      false
    ],
    "second_code": "VALIDATION_FAILED",
    "physical_start_calls": 1,
    "retained_operation": "A"
  },
  "inflight_duplicate_false_success": {
    "duplicate_finished_before_outcome": false,
    "duplicate_success": false,
    "duplicate_code": "VALIDATION_FAILED",
    "original_success": false,
    "physical_running": false
  },
  "bare_executing_misattributed_to_new_operation": {
    "success": false,
    "code": "UNCERTAIN_OUTCOME",
    "physical_start_applications": 0,
    "retained_operation": "E"
  },
  "restart_elapsed_utc": {
    "event_status": "EMERGENCY_STOPPED",
    "physical_running": false,
    "physical_start_calls": 0,
    "physical_stop_calls": 1,
    "active_events": 0,
    "tracked_events": [],
    "reserved_mm": 0.0,
    "settled_mm": 0.0,
    "delivery_context": null
  },
  "restart_naive_start_resets_allowance": {
    "event_status": "EMERGENCY_STOPPED",
    "physical_running": false,
    "physical_start_calls": 0,
    "physical_stop_calls": 1,
    "active_events": 0,
    "tracked_events": [],
    "reserved_mm": 0.0,
    "settled_mm": 0.0,
    "delivery_context": null
  },
  "restart_forgets_stop_requested": {
    "event_status": "CANCELLED",
    "physical_running": false,
    "physical_start_calls": 0,
    "physical_stop_calls": 1,
    "active_events": 0,
    "tracked_events": [],
    "reserved_mm": 0.0,
    "settled_mm": 0.0,
    "delivery_context": null
  },
  "restart_expired_failed_stop_no_reservation": {
    "event_status": "STOP_REQUESTED",
    "physical_running": true,
    "physical_start_calls": 0,
    "physical_stop_calls": 1,
    "active_events": 1,
    "tracked_events": [
      "E"
    ],
    "reserved_mm": 8.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "restart_uncertain_releases_reservation": {
    "event_status": "STOP_REQUESTED",
    "physical_running": true,
    "physical_start_calls": 0,
    "physical_stop_calls": 0,
    "active_events": 1,
    "tracked_events": [
      "E"
    ],
    "reserved_mm": 8.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "elapsed_without_poll": {
    "event_status": "EXECUTING",
    "physical_running": true,
    "physical_start_calls": 1,
    "physical_stop_calls": 0,
    "active_events": 1,
    "tracked_events": [
      "E"
    ],
    "reserved_mm": 8.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "elapsed_after_poll": {
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
  "settlement_uses_target_not_measurement": {
    "event_actual_volume_l": 160000,
    "target_mm": 8,
    "settled_mm": 8.0,
    "area_contract_present": false
  },
  "settlement_not_idempotent": {
    "same_event_settled_twice_mm": 8.0
  },
  "yesterday_debit_reduces_new_daily_budget": {
    "today_8mm_blocked": false
  },
  "nonfinite_budget_admitted": [
    {
      "limit": "nan",
      "exception": "NameError",
      "message": "name 'finite_real' is not defined",
      "sends": 0
    },
    {
      "limit": "inf",
      "exception": "NameError",
      "message": "name 'finite_real' is not defined",
      "sends": 0
    }
  ],
  "actual_two_process_quota": {
    "rows": [
      {
        "event": "A",
        "blocked": false,
        "reserved": 8.0
      },
      {
        "event": "B",
        "blocked": true,
        "reserved": 8.0
      }
    ],
    "joint_accepted_mm": 8,
    "budget_mm": 10,
    "exitcodes": [
      0,
      0
    ]
  },
  "fresh_process_forgets_quota_store": {
    "parent_reserved": 8.0,
    "parent_settled": 1.0,
    "fresh_process": {
      "reserved": 8.0,
      "settled": 1.0
    }
  },
  "two_thread_check_reserve_race": {
    "rows": [
      {
        "id": "A",
        "status": "FAILED",
        "sends": 0
      },
      {
        "id": "B",
        "status": "EXECUTING",
        "sends": 1
      }
    ],
    "reserved_mm": 8.0
  },
  "weather_numeric_control": [
    {
      "rain": "True",
      "returned_water": false,
      "rain_mm": null
    },
    {
      "rain": "0",
      "returned_water": true,
      "rain_mm": 0.0
    }
  ],
  "early_handler_control": {
    "returned_none": true
  }
}
```

### Hydraulic replay, candidate and checkpoint controls

```json
{
  "checkpoint_controls": {
    "modified": {
      "rejected": true,
      "type": "ConcurrencyConflictError"
    },
    "stale": {
      "rejected": true,
      "type": "ConcurrencyConflictError"
    },
    "escape": {
      "rejected": true,
      "type": "ValueError"
    },
    "retry": {
      "same_receipt": true,
      "sequence": 1
    },
    "changed_scope_metadata": {
      "accepted": true,
      "returned_cycle": "default_cycle",
      "returned_geometry": "default_geom"
    }
  },
  "checkpoint_retry_after_head_failure": {
    "retry_success": true,
    "latest_checkpoint": null,
    "head_exists": false
  },
  "runner_retry_publishes_orphan_cache": {
    "first_returned_water": true,
    "retry_returned_water": true,
    "durable_latest": null,
    "cached_head": "cp_hyd_P_2026-01-02_27f7f11906b7",
    "memory_entries": 2
  },
  "warm_exact_repeat": {
    "first_theta": [
      0.2007,
      0.2218,
      0.2253,
      0.2277,
      0.2295
    ],
    "repeat_theta": [
      0.2007,
      0.2218,
      0.2253,
      0.2277,
      0.2295
    ],
    "same_object": true,
    "same_head": true,
    "sequences": [
      1,
      1
    ]
  },
  "cold_exact_repeat": {
    "first_theta": [
      0.2007,
      0.2218,
      0.2253,
      0.2277,
      0.2295
    ],
    "repeat_theta": [
      0.173,
      0.2139,
      0.221,
      0.2259,
      0.2295
    ],
    "same_head": false,
    "sequences": [
      1,
      2
    ]
  },
  "changed_dependencies_reuse_cached_result": {
    "same_object": true,
    "requested_timestamp": "2026-01-02T06:00:00+00:00",
    "returned_timestamp": "2026-01-02 00:00:00+00:00",
    "requested_geometry": "G2",
    "committed_geometry": "G",
    "requested_cycle": "C2",
    "committed_cycle": "C",
    "requested_parameter_epoch": "v2",
    "committed_parameter_epoch": "v1",
    "same_head": true
  },
  "fresh_store_failure": {
    "before": {
      "_PLOT_WATER_STATE_HISTORY": [],
      "_PLOT_MANAGEMENT_EVENTS": [],
      "_PLOT_VEGETATION_HISTORY": [],
      "_PLOT_SOIL_OBS_HISTORY": [],
      "_PLOT_WITHDRAWN_SOIL_OBS": null
    },
    "returned_water": true,
    "physics_authority": "WaterPhysicsAuthority.ASSIMILATED",
    "returned_theta": [
      0.2007,
      0.2218,
      0.2253,
      0.2277,
      0.2295
    ],
    "after": {
      "_PLOT_WATER_STATE_HISTORY": [],
      "_PLOT_MANAGEMENT_EVENTS": [],
      "_PLOT_VEGETATION_HISTORY": [
        "2026-01-02"
      ],
      "_PLOT_SOIL_OBS_HISTORY": [],
      "_PLOT_WITHDRAWN_SOIL_OBS": "set()"
    },
    "memory_entries": 0
  },
  "fresh_CAS_conflict": {
    "before": {
      "_PLOT_WATER_STATE_HISTORY": [],
      "_PLOT_MANAGEMENT_EVENTS": [],
      "_PLOT_VEGETATION_HISTORY": [],
      "_PLOT_SOIL_OBS_HISTORY": [],
      "_PLOT_WITHDRAWN_SOIL_OBS": null
    },
    "exception": "ConcurrencyConflictError",
    "after": {
      "_PLOT_WATER_STATE_HISTORY": [],
      "_PLOT_MANAGEMENT_EVENTS": [],
      "_PLOT_VEGETATION_HISTORY": [
        "2026-01-02"
      ],
      "_PLOT_SOIL_OBS_HISTORY": [],
      "_PLOT_WITHDRAWN_SOIL_OBS": "set()"
    },
    "memory_entries": 0
  },
  "warm_revision_CAS_conflict": {
    "before": {
      "_PLOT_WATER_STATE_HISTORY": [
        "2026-01-02"
      ],
      "_PLOT_MANAGEMENT_EVENTS": [],
      "_PLOT_VEGETATION_HISTORY": [
        "2026-01-02"
      ],
      "_PLOT_SOIL_OBS_HISTORY": [],
      "_PLOT_WITHDRAWN_SOIL_OBS": "set()"
    },
    "exception": "ConcurrencyConflictError",
    "after": {
      "_PLOT_WATER_STATE_HISTORY": [],
      "_PLOT_MANAGEMENT_EVENTS": [],
      "_PLOT_VEGETATION_HISTORY": [
        "2026-01-02"
      ],
      "_PLOT_SOIL_OBS_HISTORY": [],
      "_PLOT_WITHDRAWN_SOIL_OBS": "set()"
    },
    "memory_entries": 2
  },
  "changed_head_warm_cold": {
    "warm_theta": [
      0.2412,
      0.2623,
      0.2658,
      0.2682,
      0.28
    ],
    "cold": {
      "theta": [
        0.2412,
        0.2623,
        0.2658,
        0.2682,
        0.28
      ]
    },
    "warm_predecessor": "foreign"
  },
  "withdrawal_roundtrip": {
    "returned_water": true,
    "saved_withdrawals": [
      "2026-01-02"
    ],
    "recovered_withdrawals": [
      "2026-01-02"
    ],
    "next_error": null
  }
}
```

### Additional storage, ownership and recovery probes

```json
{
  "corrupt_quota_fail_open": [
    {
      "store_content": "'{broken'",
      "second_status": "EXECUTING",
      "start_applications": 2,
      "both_running": true,
      "recorded_reserved_mm": 8.0
    },
    {
      "store_content": "''",
      "second_status": "EXECUTING",
      "start_applications": 2,
      "both_running": true,
      "recorded_reserved_mm": 8.0
    },
    {
      "store_content": "'[]'",
      "second_status": "EXECUTING",
      "start_applications": 2,
      "both_running": true,
      "recorded_reserved_mm": 8.0
    }
  ],
  "season_identity_lost": {
    "reservation_after_start": {
      "date": "2026-10-08",
      "plot_id": "plot",
      "status": "RESERVED",
      "timestamp": "2026-10-08T19:03:55.127242+00:00",
      "volume_mm": 8.0
    },
    "receipt": {
      "date": "2026-10-08",
      "plot_id": "plot",
      "season": "default_season",
      "timestamp": "2026-10-08T19:03:55.128444+00:00",
      "volume_mm": 8.0
    },
    "second_status": "EXECUTING",
    "season_limit_mm": 10,
    "first_settled_plus_second_reserved_mm": 16.0
  },
  "confirmed_stop_drops_unreconciled_delivery": {
    "first_status": "CANCELLED",
    "first_start_applications": 1,
    "after_stop_reservations": {},
    "after_stop_receipts": {},
    "second_status": "EXECUTING"
  },
  "fresh_dispatcher_active_payload_conflict": {
    "returned_status": "EXECUTING",
    "returned_target_mm": 12,
    "active_driver_target_mm": 8,
    "start_applications": 1
  },
  "fresh_dispatcher_settled_payload_conflict": {
    "returned_status": "COMPLETED",
    "returned_target_mm": 12,
    "returned_actual_volume_l": 0.0,
    "receipt_target_mm": 8.0,
    "start_applications": 1
  },
  "invalid_restart_timestamp_fresh_allowance": {
    "event_status": "EXECUTING",
    "physical_running": true,
    "physical_start_calls": 0,
    "physical_stop_calls": 0,
    "active_events": 1,
    "tracked_events": [
      "E"
    ],
    "reserved_mm": 8.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "missing_registry_restart_elapsed": {
    "monitor_record": {
      "start_time": "2026-10-08 19:03:55.139020+00:00",
      "start_monotonic": 0.0,
      "max_duration_minutes": 10,
      "device_id": "device",
      "plot_id": "plot",
      "volume_mm": 8
    },
    "status": "STOP_REQUESTED"
  },
  "pending_START_blocks_monitor_and_cancel": {
    "after_deadline_while_ACK_pending": {
      "event_status": "DISPATCHING",
      "physical_running": true,
      "physical_start_calls": 1,
      "physical_stop_calls": 0,
      "active_events": 1,
      "tracked_events": [],
      "reserved_mm": 8.0,
      "settled_mm": 0.0,
      "delivery_context": null
    },
    "cancel_finished_while_START_pending": false,
    "after_release_stop_calls": 1
  },
  "same_event_double_admission": {
    "workers": [
      {
        "worker": "A",
        "device": "device",
        "status": "EXECUTING",
        "starts": 1
      },
      {
        "worker": "B",
        "device": "device",
        "status": "EXECUTING",
        "starts": 1
      }
    ],
    "reserved_mm": 8.0
  },
  "stale_live_lock_takeover": {
    "second_entered_while_first_alive": true,
    "first_released": false,
    "first_notice": "holder_still_owned_critical_section",
    "lock_file_removed_by_first_owner": true
  }
}
```


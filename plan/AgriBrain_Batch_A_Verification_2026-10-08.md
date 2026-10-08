# AgriBrain — independent verification of Batch A

8 October 2026 · Reviewed GitHub main: [`319fd9404da0c88ba9b20669e04cb57c87d6f0cc`](https://github.com/webClone/AgriWise/commit/319fd9404da0c88ba9b20669e04cb57c87d6f0cc) · Previous review: `170e8666db314d2711703f7b82f57c8096f095cf`.

**Decision: Batch A contains genuine corrections, but it is partially remediated. Keep F16–F19 full acceptance open. Proceed with isolated Batch B development alongside the remaining priority Batch A repairs; this commit does not establish readiness for live physical-command acceptance.**

The strongest remaining counterexample is now an actual two-process reproduction: two processes independently admit 8 mm against the same 10 mm budget. A separate two-thread dispatcher reproduction admits and dispatches both requests, reserving 16 mm. Other reproduced paths release command ownership after uncertain START outcomes, convert OFFLINE to completion, falsely acknowledge an unconfirmed duplicate, and replace invalid flow with a hardcoded value.

## 1. Scope, evidence and limits

- Main was pinned and rechecked at the reviewed SHA. The commit is dated 8 October 2026, 17:13:25 UTC.
- All five changed production Python files were inspected: `irrigation_runtime/{schemas,actuator,dispatcher,safety}.py` and `layer3_decision/runner.py`.
- The isolated runtime contains 430 production Python files. Every file matches the current Git tree's blob hash; the probe run imported 93 distinct production files, all independently hash-matched to this revision.
- All five changed production files parse successfully. This is a syntax result, not a deployment certification.
- **32 independent probe cases/groups completed without harness errors.** These include positive controls, invalid numeric variants, asynchronous in-flight failure, restart scenarios, actual spawned processes and synchronized threads.
- Existing repository tests, test logs, audit assertions and prior correctness reports were not used as proof that the production fixes work. The reported `23 passed, 17 subtests passed` was not independently rerun or certified in this review.
- Hardware behavior was simulated only at the actuator driver boundary. No field equipment, network controller, valve, pump or irrigation output was operated. Statements about continued operation refer to this controlled simulation; actual field duration and controller protections were not verified.
- This is a deep verification of the Batch A changes and their relevant production boundaries. It is not a fresh exhaustive audit of every AgriBrain module.
- The R3 master monograph's scientific contracts and requirement register were used as the target. The monograph is not annotated with implementation status. F/T identifiers belong to the repair plan; R3 uses AB-* requirement identifiers.
- No production repository files were modified, pushed or merged during this review. Independent probe code and temporary state were confined to the review workspace.

The supplied record should retain the distinction between implementation, a passing local example, and full integrated acceptance. The unchecked acceptance milestones correctly preserve that distinction.

## 2. Claim-by-claim result

| Claimed repair | Independently verified improvement | Remaining qualification |
|---|---|---|
| R01: failed STOP retains delivery context and tracking | A failed watchdog STOP and failed cancellation remain `STOP_REQUESTED`; the original START context, active tracking and 8 mm reservation survive. A later explicit poll retries STOP. | Other unknown-outcome paths still finalize or release exposure. Restart can restore `STOP_REQUESTED` without monitor/reservation state or erase stop intent. |
| R02: no duplicate logical operation | Repeated submission to the same dispatcher returns the existing event and sends START once. The actuator suppresses a matching active request. Bare ONLINE after ACK loss no longer causes a blind retry. | Idempotency is not durable across dispatcher replacement; conflicting payloads can be acknowledged as success; an in-flight request can be acknowledged before its original dispatch fails. Bare EXECUTING still lacks operation attribution. |
| R03: empty IDs do not bypass mutual exclusion | Distinct operation IDs with both source-event IDs empty now produce one successful START and one rejection. | Matching a nonempty source-event ID is still accepted even when operation ID and delivery payload differ. |
| R04: shared durable quota and settled debit | Sequential independent monitors within one process share reservations and correctly deny the second 8 mm request against a 10 mm limit. | The store is a class dictionary plus a thread lock. It is neither durable nor cross-process. Admission is not atomic. Validation creates an accounting gap. Settlement lacks event, period and measured-depth reconciliation. |
| R05: elapsed restart limits | A valid UTC start nine minutes earlier plus two minutes after recovery exceeds a ten-minute limit and is stopped on polling. | Naive/missing/invalid starts can receive a fresh allowance. Restart loses stop intent or ownership on several branches. The watchdog still requires an external caller. |
| R06: command scalar qualification | At the direct command boundary, 18 combinations of NaN, infinity, boolean, string and negative values across three fields are rejected, with zero driver sends. | The dispatcher rewrites negative/boolean flow to 15 L/min before this validation. NaN budget limits permit dispatch. |
| R13: exception-import shadowing | The local shadowing import is removed. An early malformed-timestamp exception returns `(None, None)` without a secondary `UnboundLocalError`. | This closes the specific exception-shadowing counterexample; it does not close persistence publication failures. |
| R15: atmospheric boolean coercion | Boolean precipitation is rejected as incomplete/invalid weather; numeric zero precipitation produces a water result with 0.0 mm precipitation. | This verifies the relevant canonical water adapter boundary, not every weather ingest/provider path. |

## 3. Remaining findings and required repairs

BA-* labels below are local review identifiers. They do not replace the canonical F/T packages or the existing R01–R17 record.

### BA-01 — P0 — Unknown physical outcomes still lose dispatcher ownership

**Production paths:** `submit_event()`, `check_execution_status()`, `reconcile_on_restart()`.

1. START is applied by the simulated driver, its ACK is lost, and the status query fails. The actuator retains its START context, but the dispatcher marks the event `FAILED`, removes it from active events and releases the reservation. The driver remains running, with no dispatcher watchdog entry.
2. While an event is running, the driver reports OFFLINE. The generic `status != EXECUTING` branch marks the event `VALIDATING`, removes duration tracking and releases quota. OFFLINE does not establish cessation or delivered volume.
3. Removing the actuator from the registry during execution produces `FAILED` and finalization while the simulated driver continues running.
4. Restart status-query failure releases an existing reservation and leaves the running event outside active tracking.

**Observed:** uncertain START and lost-registry cases end with active events = 0, tracked events = [], reserved depth = 0.0 mm, driver running = true. The OFFLINE case retains a validation record but drops both watchdog and reservation.

**Repair:** model dispatch intent, attributable acknowledgement, confirmed execution, unknown execution, stop requested, confirmed stop and delivery settlement separately. Preserve ownership and conservative exposure whenever application or cessation is unknown. Registry loss and communications loss require degraded reconciliation; they must not mean physically stopped. Record failure of communication separately from failure to apply water. A bare idle status can establish an observed controller state but cannot reconstruct attributable delivered volume.

**Acceptance:** ACK loss, status loss, registry loss and restart failure cannot create a terminal confirmed receipt or free unresolved exposure. Same-operation stop/reconciliation remains possible, including after owner process failure.

**R3:** AB-EXE-002/003/004; AB-DAT-010. **Packages:** F16/F17/F18.

**Sources:** [dispatcher.py:100–199](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/dispatcher.py#L100-L199), [dispatcher.py:300–414](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/dispatcher.py#L300-L414), [dispatcher.py:505–587](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/dispatcher.py#L505-L587).

### BA-02 — P0 — Quota admission is process-local and not atomic

`SharedQuotaStore` contains a `threading.Lock`, `_reservations` and `_settled_deliveries`. No durable store or inter-process admission transaction backs these dictionaries. Individually locking reads and writes does not make the quota-check-plus-reserve sequence atomic.

**Actual process reproduction:** two spawned Python processes import the unchanged production classes and each request 8 mm from the same plot/budget. Both pass the real quota check and reserve 8 mm in their respective address spaces. Accepted total = **16 mm**, budget = **10 mm**, both child exit codes = 0. This reproduction exercises the production monitor/store API; it does not claim deployment-level integration across a real database or multiple hosts.

**Actual thread reproduction:** two threads each execute a real dispatcher. A barrier after the real preflight check exposes the permitted interleaving before reservation. Both events become `EXECUTING`, both drivers receive START, and shared reserved depth becomes **16 mm**. The barrier schedules the race; it does not substitute a different quota algorithm. This is a two-thread topology, not a claim about an admission race in one uninterrupted asyncio event loop.

**Fresh-process visibility:** with 8 mm reserved and 1 mm settled in the parent, a fresh child reads 0 mm reserved and 0 mm settled. This demonstrates absent cross-process visibility; persistence cannot be inferred from the class name.

**Repair:** one durable transactional admission operation must validate budget version, numeric values, scoped ownership, operation identity and total exposure, then reserve before physical dispatch. Use a store supported by the deployment topology, with conditional writes/transactions and worker fencing. Scope day/season accounting explicitly; plot ID alone is not the complete R3 namespace. Store outage must produce an explicit execution-blocked receipt where shared enforcement is required.

**Acceptance:** two independent processes/replicas contending for two 8 mm requests against 10 mm admit at most one; restart preserves unresolved reservations and settled delivery. Kill the owner between reservation, send, ACK and settlement and recover without redosing or forgetting exposure.

**R3:** AB-EXE-004; AB-ARC-008; AB-DAT-013. **Packages:** F16/F18 and the relevant shared-store/concurrency foundations.

**Sources:** [safety.py:64–118](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/safety.py#L64-L118), [safety.py:546–625](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/safety.py#L546-L625), [dispatcher.py:145–199](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/dispatcher.py#L145-L199).

### BA-03 — P0 — Local idempotency can fabricate success or repeat a completed operation

Four independent cases remain:

- **Fresh dispatcher:** complete operation E, then submit E through a new dispatcher. Its empty local history permits START again; simulated START applications increase from 1 to 2.
- **Conflicting identity:** active operation A uses 8 mm/10 min/10 L/min. Operation B uses the same source-event ID but a different operation ID and 12 mm/20 min/20 L/min. It is returned as successful `ALREADY_EXECUTING` even though only A was sent. Avoiding a duplicate send is useful, but falsely acknowledging the different request is incorrect.
- **In-flight duplicate:** the actuator sets local EXECUTING before awaiting its first send. While that send is pending, a duplicate returns successful `ALREADY_EXECUTING`. The original then returns `NOT_APPLIED`; the simulated controller has never started. A local optimistic flag is not an attributable ACK.
- **Unrelated running operation:** a new START is rejected while the controller is already running an unrelated operation. Bare EXECUTING is converted to successful `RECONCILED_EXECUTING` and the new operation becomes the active context, despite zero applications of that new command.

**Repair:** durable scoped operation identity plus an immutable canonical payload digest; atomic pending ownership and terminal receipts; distinguish pending from acknowledged/applied. A duplicate joins or returns the existing typed pending/result receipt. Changed content under the same identity is a conflict. Driver reconciliation must attribute the result to the requested operation; bare controller status is insufficient to confirm a new dose. Retain uncertainty when operation-level reconciliation is unavailable.

**Acceptance:** replacements, restarts and concurrent owners cannot repeat a completed operation. No duplicate reports success before the original outcome is established. Payload conflict cannot masquerade as acceptance. Unrelated EXECUTING does not prove application of a rejected command.

**R3:** AB-EXE-002/003; AB-ARC-008. **Packages:** F17/F18.

**Sources:** [actuator.py:208–218](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/actuator.py#L208-L218), [actuator.py:274–435](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/actuator.py#L274-L435), [dispatcher.py:122–137](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/dispatcher.py#L122-L137).

### BA-04 — P0 — Numeric qualification is bypassed by upstream rewriting and unqualified budgets

The direct `IrrigationCommand.validate()` checks work for the tested invalid inputs. However `_build_command()` replaces any flow satisfying `flow_rate <= 0.0` with **15.0 L/min** before command validation. Negative flow `-1`, boolean `False` and legitimate numeric zero each reach EXECUTING and one driver START with flow = 15.0. Validation sees the fabricated valid value, not the original invalid input.

Separately, a valid 8 mm request with both budget remaining fields set to NaN reaches EXECUTING and sends START. Comparisons with NaN do not enforce the quota. Infinity also passes; any deliberately unlimited policy needs an explicit policy contract rather than accidental nonfinite numeric evidence.

**Repair:** qualify raw event and budget values before comparisons, substitutions or arithmetic. Reject booleans, strings, NaN, infinity and invalid signs according to each field's semantics. Preserve valid zero. If a driver requires a positive flow, obtain it from an explicit qualified capability/configuration or reject the operation. Do not use a universal physical fallback rate. Validate budget identity/version and quantity consistency alongside numeric type.

**Acceptance:** the invalid direct-command matrix must also pass at the public dispatcher/event boundary with zero driver sends. Zero retains its meaning or is rejected with a typed field-specific reason; it is never silently promoted to 15 L/min. NaN budget evidence blocks execution.

**R3:** AB-EXE-001/004; AB-DAT-005/006/007. **Packages:** F16/F17.

**Sources:** [dispatcher.py:204–234](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/dispatcher.py#L204-L234), [schemas.py:616–662](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/schemas.py#L616-L662).

### BA-05 — P0 — Restart can reset limits, erase stop intent or restore incomplete ownership

The valid UTC elapsed-time correction works. The following recovery branches do not:

| Recovery input | Observed outcome |
|---|---|
| Naive start nine minutes earlier; two more minutes elapse after recovery; ten-minute limit | Timestamp subtraction fails, exception is swallowed, elapsed defaults to zero. Event remains EXECUTING, driver running, STOP calls = 0. |
| Persisted STOP_REQUESTED; controller running; duration remains | Event is changed back to EXECUTING with no STOP attempt. Prior stop intent is lost. |
| Expired persisted execution; STOP fails | STOP_REQUESTED is added to the dispatcher but monitor entries are empty, reserved depth is 0.0, and original delivery command is absent. |
| Persisted execution with status-query failure | FAILED, no active ownership, released reservation, simulated driver still running. |

If timestamps must be UTC-aware, invalid/unknown timestamps should be explicitly rejected or handled conservatively; silently granting a new full allowance is not a safe interpretation. Wall-clock recovery also needs an explicit clock-skew policy. This review did not simulate arbitrary clock jumps.

**Repair:** persist immutable start/deadline and stop intent with the operation. Restore exposure and ownership before attempting communications. Normalize qualified timestamps or retain unknown elapsed time conservatively. Restore all monitor/delivery state on every unresolved branch. STOP_REQUESTED remains stop intent regardless of remaining duration. Fenced workers may resume same-operation reconciliation, not create a new allowance.

**Acceptance:** valid UTC, naive/invalid/missing timestamp, past deadline, clock-skew policy, failed STOP, dropped controller and process restart preserve a bounded, explicitly qualified outcome. Failed STOP cannot produce an unreserved running operation.

**R3:** AB-EXE-002/003/004. **Packages:** F16/F17/F18.

**Sources:** [dispatcher.py:505–578](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/dispatcher.py#L505-L578), [safety.py:249–297](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/safety.py#L249-L297).

### BA-06 — P0 — Entering validation frees unaccounted delivery

When a running controller becomes ONLINE, `check_execution_status()` calls `track_event_end()`. That method removes watchdog tracking **and releases quota**. Settlement happens later in `complete_event()`.

**Probe:** first operation targets 8 mm. After observed idle and before validation completion, both reservation and settlement equal zero. A second device therefore admits another 8 mm against the same 10 mm budget. Completing the first event leaves settled = 8 mm and reserved = 8 mm: total accounted exposure = **16 mm**.

**Repair:** separate cessation of runtime monitoring from reservation release. Atomically transfer running exposure to unsettled-delivery exposure, then reconcile/settle once. A delayed, failing or absent validation callback cannot create free budget. Unknown delivered volume needs an explicit conservative bound and reconciliation status.

**Acceptance:** no intermediate state between running, stopped, validating and settled allows both the old delivery and another request to escape the same cap. Repeated callbacks and callback failure preserve accounting.

**R3:** AB-EXE-004; AB-DAT-010. **Packages:** F16/F18.

**Sources:** [dispatcher.py:401–439](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/dispatcher.py#L401-L439), [safety.py:274–297](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/safety.py#L274-L297).

### BA-07 — P1 — Settlement does not reconcile measured depth, event identity or accounting period

- `complete_event()` records `actual_volume_l` but settles `target_volume_mm`. In the probe, changing recorded actual volume to 160,000 L still settles exactly the 8 mm target. The event has no `area_ha` contract; therefore this review does **not** infer an actual depth or claim the measured volume is twice the target. Conversion requires qualified effective area and spatial support.
- Calling `SharedQuotaStore.settle()` twice for the same event adds 8 mm twice, producing 16 mm. The store has no unique settlement receipt. This is a store-API reproduction, not a claim that the same-dispatcher `complete_event()` repeats after removal.
- Settled depth is cumulative per plot, with no day/season identity. Quota checking subtracts `max(0, cumulative_settled - daily_consumed)` from both daily and seasonal remaining values. A previously settled 8 mm represented in season consumption but outside a newly reset daily budget incorrectly blocks today's 8 mm request against a fresh 10 mm daily allocation. The probe presents these budget states explicitly; it does not advance a deployment clock through midnight.

For a qualified area A in hectares and volume V in liters, application depth is `I_mm = V_L / (10,000 × A_ha)`. Area/version, delivered-volume support and uncertainty must accompany this conversion. A planned depth is not a measured delivery simply because it is stored at completion.

**Repair:** an append-only delivery ledger keyed by scoped operation and unique receipt, with qualified volume/depth, area version, delivery interval, uncertainty/provenance and correction lineage. Reconcile period-specific budget snapshots by version/receipt coverage, not by subtracting cumulative plot delivery from today's consumption. Duplicate receipts are idempotent; corrections adjust through explicit revision records.

**Acceptance:** exact duplicate settlement has no effect; corrected delivery affects the right day and season exactly once; measured and planned quantities remain distinguishable; unknown area/volume cannot fabricate measured depth. Restart and separate-worker settlement retain the same result.

**R3:** AB-EXE-002/004; AB-DAT-007/010/013. **Packages:** F16/F18 and delivery reconciliation consumers.

**Sources:** [dispatcher.py:416–439](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/dispatcher.py#L416-L439), [safety.py:98–118](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/safety.py#L98-L118), [safety.py:580–600](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/irrigation_runtime/safety.py#L580-L600).

### Operational qualification — deadline enforcement still requires an independently scheduled caller

Advancing the injected monotonic clock beyond ten minutes and yielding the event loop causes no STOP by itself. Calling `check_execution_status()` then invokes the watchdog and stops the simulated driver. The new code correctly evaluates the watchdog before waiting for the status query, but that improves a poll rather than establishing autonomous scheduling.

The source method itself says it should be called periodically. This review does not establish absence of every deployment scheduler or hardware watchdog. Full F16 acceptance needs direct evidence that a bounded scheduler or controller-enforced deadline operates without new telemetry, including dropped polls, hung driver calls, owner failure and restart. Keep this qualification separate from the directly reproduced production defects above.

## 4. Plan-folder qualifications

The new Section 1.1 in `plan/AgriBrain_Claims_Deep_Check_2026-10-08.md` contains the supplied qualifications: original quota-probe scope, simulated valve duration, service-level checkpoint traversal, canonical identities, solver precision, executed-vs-inspected controls, objective-specific research eligibility and partial ordering of repairs. Its main report remains explicitly pinned to the older `170e866` production revision. Treat that body as a historical finding record, not the current fix verification; append this newer receipt rather than implying the earlier probes ran against this commit.

The execution task list is unchanged at Git blob `8a564647af7e588802537817159117b349ff606b`. These full acceptance tickets remain unchecked:

| Ticket | Current status | Required treatment |
|---|---|---|
| ST06-F16-FA | Open `[ ]` | Keep open: quota durability/admission, unresolved exposure and autonomous deadline evidence remain incomplete. |
| ST06-F17-FA | Open `[ ]` | Keep open: typed controller outcomes, raw input qualification and recovery are incomplete. |
| ST06-F18-FA | Open `[ ]` | Keep open: durable idempotency, attributed reconciliation and restart ownership are incomplete. |
| ST06-F19-FA | Open `[ ]` | Keep open: this review does not independently establish its complete interlock persistence/debounce acceptance. |

Record R13 and the tested R15 boundary as corrected; record R01–R06 as improved with the above remaining subcases. Add the BA-* counterexamples to the existing canonical package acceptance evidence instead of declaring new package identities or changing the R3 scientific target.

## 5. Concrete next implementation sequence

These priorities do not create universal serial dependencies. Independent precision, temporal-admission and hydraulic work can proceed where its real prerequisites permit.

### A1. Fix the raw admission and unknown-outcome branches

1. Validate event scalars and budget quantities before `_build_command()` performs any transformation. Remove the 15 L/min physical fallback.
2. Introduce explicit pending/unknown outcome receipts and preserve ownership/reservations on ACK loss, OFFLINE/UNKNOWN, registry loss and failed recovery.
3. Separate runtime-monitor termination from exposure termination. Preserve unsettled delivery through validation and callback failure.
4. Preserve stop intent and original deadline across every restart branch. Restore monitor, quota and delivery context before querying hardware.

This can close local counterexamples promptly, while the durable admission work proceeds. It does not alone establish multi-process acceptance.

### A2. Implement one durable admission/operation/delivery boundary

1. Define the authoritative scope: tenant, farm/plot, zone/geometry revision, season/day policy, device, operation ID and immutable payload digest.
2. Implement atomic check-and-reserve with budget version and worker lease/fencing. Do not rely on independent dictionary reads/writes.
3. Persist pending send ownership before physical I/O; reconcile operation-attributed receipts after failures. Never promote local optimistic EXECUTING or bare controller status to proof of new application.
4. Persist stop intent and deadline; transfer exposure atomically from active reservation to unsettled/settled delivery.
5. Make unique delivery receipts idempotent, period-specific and tied to qualified volume/depth and area. Represent corrections without rewriting prior receipts.
6. Prove bounded deadline enforcement independently of sensor arrival and reconcile crashes at every transition boundary.

**Acceptance matrix:** separate processes sharing the actual durable store; two threads; duplicate pending requests; completed replay; conflicting payload; lost ACK; unrelated running operation; lost registry; OFFLINE; invalid raw flow/budget; delayed validation; duplicate settlement; daily reset; process death before/after send; restart with STOP_REQUESTED; expired restart with failed STOP; missing/invalid start time; store outage. Existing passing examples must remain as positive controls.

### B. Start hydraulic repairs with the complete original scope

The supplied Batch B shorthand R07–R10 is narrower than the documented Batch B. Include **R07, R08, R09, R10, R11, R12 and R17**. R13's specific import-shadowing counterexample is already corrected and should remain a control.

| Order | Repair | Concrete deliverable | Acceptance |
|---|---|---|---|
| B1 | R12 withdrawal representation | One date representation and immutable withdrawal/tombstone serialization, hydration and lookup. | Withdrawal persists through cold restart and replay; excluded evidence does not reappear. |
| B2 | R08 + R17 checkpoint identity/containment | Immutable content identity, identical retry receipt, conflicting-ID rejection, contained storage keys and acyclic predecessor references. | Old content cannot be overwritten; no self-parent; caller IDs cannot escape the store. The previously demonstrated traversal is service-level, not an established external HTTP exploit. |
| B3 | R07 transition identity | Capture the actual predecessor before computing the successor. Define scope, interval and admitted forcing/parameter digests. | An identical request returns the committed transition without solving again or advancing the sequence/head. |
| B4 | R10 + R11 candidate publication | Isolated candidate state; typed committed/degraded result; durable CAS before authoritative cache/output publication. | CAS rejection or store outage cannot leave accepted candidate state in RAM or return an unqualified canonical result. Diagnostics may remain explicitly limited. |
| B5 | R09 head/cache binding | Every cached snapshot records the exact durable predecessor it represents; changed heads reload before solving. | Warm/cold and competing workers compute from the same committed predecessor; a new head token cannot legitimize stale RAM. |
| B6 | Integrated F08/F09 proof | Production transition/store integration across replay, corrections, withdrawals, restart and concurrent workers. | Exact-repeat identity, scoped isolation, declared physical tolerances, sparse/daily equality, rollback/reload on failure and durable head consistency. |

The hydraulic defects above are carried forward from the explicitly pinned previous review. This Batch A probe run does not claim to re-execute every historical hydraulic reproduction. The current patch closes neither checkpoint immutability nor the previously documented transactional candidate/publication scope merely by fixing an exception import.

### Research and later integration

Qualified world-model/Omega experiment design and objective-specific research can continue. Integrated capability acceptance must use the actual prerequisite gates and canonical downstream packages, including the intervening yield/outcome, data/training, forecast-skill, driver and target-extension work. Do not train or evaluate an objective as though an uncommitted hydraulic candidate, unattributed delivery or hidden fallback were measured authoritative evidence. No universal ban on all research follows from these findings.

## 6. Source identities

All paths below are relative to the repository at the reviewed commit.

| Production path | Git blob |
|---|---|
| services/agribrain/irrigation_runtime/actuator.py | 36342d0cdf8c1411ab4f0dfbd8095a6feca36c21 |
| services/agribrain/irrigation_runtime/dispatcher.py | 5cb6d2ae33e355b10444076c0dbbf26dad3a45ad |
| services/agribrain/irrigation_runtime/safety.py | d79cd8b5fd86ee5cc666bf123e2bc7adb0ec4b86 |
| services/agribrain/irrigation_runtime/schemas.py | 0102806f6b2899e9c28a69c9bde2d75c2cc31264 |
| services/agribrain/layer3_decision/runner.py | 755e25f6525761990bf8ff24ac4474a7ba95c168 |

Relevant positive adapter controls: [runner.py:1014–1039](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/layer3_decision/runner.py#L1014-L1039), [runner.py:2138–2148](https://github.com/webClone/AgriWise/blob/319fd9404da0c88ba9b20669e04cb57c87d6f0cc/services/agribrain/layer3_decision/runner.py#L2138-L2148).

## 7. Independent probe receipts

The receipts below are generated by the review harness calling the hash-verified production classes/functions. The driver is controlled simulation. Historical names such as `physical_running` and `physical_start_calls` refer to that simulated boundary, not field I/O. `yesterday_debit_reduces_new_daily_budget` presents an already-accounted earlier delivery and a reset daily budget; it is not a deployed midnight rollover test. Full source-import inventory was checked separately and is omitted here for readability.

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
      "status": "EXECUTING",
      "sends": 1,
      "sent_flow": 15.0
    },
    {
      "input_flow": "False",
      "status": "EXECUTING",
      "sends": 1,
      "sent_flow": 15.0
    },
    {
      "input_flow": "0",
      "status": "EXECUTING",
      "sends": 1,
      "sent_flow": 15.0
    }
  ],
  "idle_ack_loss_no_redose": {
    "event_status": "FAILED",
    "physical_running": false,
    "physical_start_calls": 1,
    "physical_stop_calls": 0,
    "active_events": 0,
    "tracked_events": [],
    "reserved_mm": 0.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "uncertain_start_query_failure": {
    "event_status": "FAILED",
    "physical_running": true,
    "physical_start_calls": 1,
    "physical_stop_calls": 0,
    "active_events": 0,
    "tracked_events": [],
    "reserved_mm": 0.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "offline_status_completion": {
    "event_status": "VALIDATING",
    "physical_running": true,
    "physical_start_calls": 1,
    "physical_stop_calls": 0,
    "active_events": 1,
    "tracked_events": [],
    "reserved_mm": 0.0,
    "settled_mm": 0.0,
    "delivery_context": "START_ZONE"
  },
  "lost_registry_completion": {
    "event_status": "FAILED",
    "physical_running": true,
    "physical_start_calls": 1,
    "physical_stop_calls": 0,
    "active_events": 0,
    "tracked_events": [],
    "reserved_mm": 0.0,
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
      "reserved_mm": 0.0,
      "settled_mm": 0.0,
      "delivery_context": "START_ZONE"
    },
    "second_status": "EXECUTING",
    "after_first_settlement_reserved_mm": 8.0,
    "settled_mm": 8.0
  },
  "new_dispatcher_redoses_completed_operation": {
    "status": "EXECUTING",
    "physical_start_calls": 2
  },
  "conflicting_identity_false_success": {
    "successes": [
      true,
      true
    ],
    "second_code": "ALREADY_EXECUTING",
    "physical_start_calls": 1,
    "retained_operation": "A"
  },
  "inflight_duplicate_false_success": {
    "duplicate_success": true,
    "duplicate_code": "ALREADY_EXECUTING",
    "original_success": false,
    "physical_running": false
  },
  "bare_executing_misattributed_to_new_operation": {
    "success": true,
    "code": "RECONCILED_EXECUTING",
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
  "restart_forgets_stop_requested": {
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
  "restart_expired_failed_stop_no_reservation": {
    "event_status": "STOP_REQUESTED",
    "physical_running": true,
    "physical_start_calls": 0,
    "physical_stop_calls": 1,
    "active_events": 1,
    "tracked_events": [],
    "reserved_mm": 0.0,
    "settled_mm": 0.0,
    "delivery_context": null
  },
  "restart_uncertain_releases_reservation": {
    "event_status": "FAILED",
    "physical_running": true,
    "physical_start_calls": 0,
    "physical_stop_calls": 0,
    "active_events": 0,
    "tracked_events": [],
    "reserved_mm": 0.0,
    "settled_mm": 0.0,
    "delivery_context": null
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
    "same_event_settled_twice_mm": 16.0
  },
  "yesterday_debit_reduces_new_daily_budget": {
    "today_8mm_blocked": true
  },
  "nonfinite_budget_admitted": [
    {
      "limit": "nan",
      "status": "EXECUTING",
      "sends": 1
    },
    {
      "limit": "inf",
      "status": "EXECUTING",
      "sends": 1
    }
  ],
  "actual_two_process_quota": {
    "rows": [
      {
        "event": "B",
        "blocked": false,
        "reserved": 8.0
      },
      {
        "event": "A",
        "blocked": false,
        "reserved": 8.0
      }
    ],
    "joint_accepted_mm": 16,
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
      "reserved": 0.0,
      "settled": 0.0
    }
  },
  "two_thread_check_reserve_race": {
    "rows": [
      {
        "id": "A",
        "status": "EXECUTING",
        "sends": 1
      },
      {
        "id": "B",
        "status": "EXECUTING",
        "sends": 1
      }
    ],
    "reserved_mm": 16.0
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

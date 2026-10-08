# AgriBrain: deep check of implementation-completion claims

8 October 2026 · Production revision reviewed: `170e8666db314d2711703f7b82f57c8096f095cf` · Historical plan baseline: `26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`.

**Decision: continue corrective implementation now, but do not accept the attachment's “11 packages complete” claim or mark the corresponding full acceptance tickets complete. The new F09 commit also requires repair. The structural plan is usable; several implemented production behaviors still violate its acceptance criteria and the R3 monograph.**

The next batch should close the reproducible safety, temporal-admission, replay and persistence defects below. Full world-model/Omega integration depends on these boundaries. Scientific-case design, discriminating experiments and research preparation can proceed with explicitly limited scope; empirical capability claims require their own evidence.

## 1. Exact scope and evidence

This review checks the attached `Texte collé(6).txt` against the current GitHub branch, all eight `plan/` documents, the canonical package cards, and the R3 monograph's scientific contracts and requirement register. It inspects the 23 production files changed since the preceding plan revision, plus production dependencies and consumers. The review does not claim an exhaustive fresh audit of every production file in the repository.

- Main was pinned and rechecked at [`170e866`](https://github.com/webClone/AgriWise/commit/170e8666db314d2711703f7b82f57c8096f095cf), dated 8 October 2026, 15:42:22 UTC. Its message describes the F09 hydraulic persistence implementation.
- Eight commits separate the prior reviewed plan revision `f243953` from this production revision.
- All eight plan files were verified against current Git blob identities.
- The isolated production runtime contains **430 Python files whose bytes match this revision**. The principal probe run imported **130** verified production files. Existing repository tests, audit assertions and previously generated correctness reports were not used as correctness evidence.
- **30 independent probe cases/groups**, including positive controls, exercised production functions. A separate fresh-process GMM import and 20-pixel consumer probe also completed. Hardware/controller behavior was represented at the driver boundary; there was no network, field equipment or live irrigation I/O.
- All 22 changed production Python files parsed successfully. This is a syntax result, not a deployment or full-pipeline certification. The changed TypeScript route was inspected; a Next.js build and real database outage were not independently exercised.
- The current R3 source was read, including scientific sections and the complete 153-requirement register. Its version is dated 30 September 2026. It remains a target specification, without implementation-status annotations.
- PR #1 remains draft, open and unmerged at `bcb9eda6b8ef1aa6425f5828669f753a191227bc`.

No repository production files were edited, pushed or merged in this review. Temporary checkpoint writes and fault injection occurred only in the isolated probe environment.

## 1.1 Authoritative verification qualifications

Before this document serves as an authoritative verification record, these specific qualifications govern its findings:

| Point | Required correction |
|---|---|
| **“Two workers in separate processes”** | The quota probe used two independent dispatcher/monitor instances within one process. It demonstrates isolated reservation stores; actual multi-process acceptance remains required. |
| **Valve “spraying indefinitely”** | The probe demonstrates continued simulated operation after failed STOP and removal of tracking. Actual duration depends on controller protections, which were not verified. |
| **Checkpoint traversal** | Service-level escape is reproduced. An externally reachable HTTP exploitation path was not established. |
| **Canonical “Monograph R3 package identities”** | F/T package IDs belong to the master repair plan. R3 defines the scientific requirement IDs mapped to those packages. |
| **Conductivity precision “≥4 decimals”** | A fixed four-decimal rule still rounds smaller positive values to zero. Preserve solver precision and round only for presentation. |
| **Positive controls** | Distinguish executed probes from source inspection. Dashboard/database behavior and optional-driver capability were not fully exercised against deployed services. |
| **Mandatory completion before any world-model/Omega training** | Too broad. Exploratory research and qualified experiments can proceed with objective-specific eligibility. Integrated capability acceptance requires the stated dependencies. |
| **Batch D jumps toward world model/Omega** | Retain the intervening canonical packages and prerequisite gates, particularly F12, F21, F23, F24, F36 and T01–T04. |
| **Entirely serial A→B→C→D execution** | These are priorities, not universal blocking dependencies. Independent cutoff or precision repairs can proceed alongside other work where their actual prerequisites permit. |

## 2. The attachment's main claims

| Claim | Independent result |
|---|---|
| F09 is uncommitted/in progress | Stale: it is committed in `170e866`. Commitment does not establish acceptance. |
| Eleven full packages are complete | Not supported. Several named packages have direct failing counterexamples. |
| F09's issue is only a small numerical tolerance | Not supported by this review: identical-request replay changes the state, checkpoints can be overwritten, stale memory can supersede a newer head, and withdrawals fail to persist. |
| F06 eliminated zero-rain forward persistence through continuous interpolation | False as a description of current code. Explicit zero-rain persistence/climatological priors remain. They are labelled and uncertainty is inflated, which is an improvement. |
| F18 provides transactional idempotency without repeated discharge | False at the production API boundary: the same operation can be physically sent twice. Idle status after ACK loss also permits a duplicated application. |
| F19 includes multi-zone concurrent-pressure guards | The changed implementation establishes debounce and stable violation keys. It does not establish the additional claimed multi-zone scheduling/pressure capability. The master F19 scope is interlock persistence/debounce, not that renamed capability. |
| Five early slices are complete, three remain | Its own list contains five Stage 00 slices plus the F32 slice: six implementation slices. Of eight ES tickets, two remain unclaimed. `ST00-F37-FA` is a full acceptance milestone, not a third early slice. |
| All 285 task checkboxes are unchecked | Verified. This proves the register has not recorded acceptance; it does not prove no implementation exists. |
| The pending package descriptions match the roadmap | False for many IDs. The correct definitions are restored in section 7. |
| Reported unit-test totals establish completion | Not independently verified here. Counts alone cannot establish the master criteria, especially where independent counterexamples remain. |

The arithmetic “52 minus 11 equals 41” is correct under the attachment's assumed completion count. That assumption is not an acceptance result. With F09 now committed there are 12 package-labelled implementations in these commits, but it would be equally incorrect to infer 12 accepted packages or 40 accepted-to-be-completed packages from commit titles.

## 3. Production findings and concrete repairs

The following 17 grouped findings are supported by fresh production probes. Priorities indicate implementation urgency within this review; they are not replacements for the master package priorities. Related probes are grouped when they exercise the same boundary.

### R01 — P0 — Failed stops are finalized as stopped or cancelled

**Packages:** F16, F17, F18. **R3:** AB-EXE-002/003/004.

`check_execution_status()` ignores the result of `emergency_stop()`, marks the event `EMERGENCY_STOPPED`, releases quota and removes event tracking. `cancel_event()` likewise ignores a failed stop and finalizes `CANCELLED`. The duration monitor also removes expired event/reservation tracking before a confirmed stop.

**Probe:** a driver acknowledges START and explicitly returns failure for STOP. After deadline processing, the controller remains physically running, event status is `EMERGENCY_STOPPED`, reservation is `0.0`, and active-event tracking is empty. A cancellation probe similarly leaves the controller running with status `CANCELLED`.

**Repair:** retain operation ownership, reservation and deadline monitoring while stop/delivery is unknown. Record `STOP_REQUESTED` or an equivalent unknown-outcome state separately from a physically confirmed stopped state. Retry/reconcile the same stop operation through bounded communication failures; finalize only after an attributable controller receipt. Preserve the original delivery command when a stop attempt fails.

**Acceptance:** explicit stop failure cannot produce a confirmed terminal stopped/cancelled receipt or release an unresolved physical exposure. The same applies to global stop and controller-error branches.

**Sources:** [services/agribrain/irrigation_runtime/dispatcher.py:311](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/dispatcher.py#L311-L399); [services/agribrain/irrigation_runtime/safety.py:405](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/safety.py#L405-L466); [services/agribrain/irrigation_runtime/actuator.py:253](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/actuator.py#L253-L335).

### R02 — P0 — Stable operation IDs do not provide idempotent delivery

**Packages:** F18, F17. **R3:** AB-EXE-003, AB-ARC-008.

The dispatcher builds stable `operation_id` values but maintains no demonstrated durable operation-admission/result transaction. Re-submitting a new QUEUED event object with the same ID dispatches START again. `execute_with_safety()` permits an own-operation retry and sends it rather than returning/reconciling an existing result.

The ACK-reconciliation branch treats bare controller `ONLINE` status as proof that the command was never applied. An already completed pulse or operation can also be ONLINE. Bare `EXECUTING` status does not identify which operation is executing.

**Probes:** two submissions of event `same` produced two physical START calls with `OP-same`. A driver representing completed application followed by ACK loss reported idle; retry produced two physical applications with `OP-E`, while the event ultimately became `FAILED`.

**Repair:** persist scoped operation identity, payload hash, attempt IDs, controller receipt and cumulative delivery. Atomically admit an operation once, fence its owner, and reconcile via operation-specific controller data. Unknown outcome retains ownership. A confirmed idle state alone must not authorize a new dose.

**Acceptance:** replayed submission, ACK loss before/after application, and restart cannot create a second physical application for one logical operation. A driver lacking operation-level reconciliation must retain an explicit uncertainty boundary and bounded capability.

**Sources:** [services/agribrain/irrigation_runtime/dispatcher.py:118](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/dispatcher.py#L118-L275); [services/agribrain/irrigation_runtime/actuator.py:176](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/actuator.py#L176-L326).

### R03 — P0 — Empty source-event IDs defeat conflicting-operation rejection

**Package:** F17. **R3:** AB-EXE-002/003/004.

`validate_command()` uses `active.source_event_id == incoming.source_event_id` as one way to recognize an own-operation retry. Both source IDs default to empty strings. Two unrelated operations therefore compare equal through that branch.

**Probe:** valid commands with operation IDs `operation-A` and `operation-B`, both with the schema's default empty source-event ID, both succeeded and produced two START calls while the first operation was running.

**Repair:** require a nonempty, scoped operation identity and matching immutable payload for own-operation reconciliation. Empty source IDs must never establish equality of logical operations. Reject conflicting commands atomically at the actual actuator lease boundary.

**Acceptance:** a second distinct operation is rejected regardless of absent optional provenance IDs; a genuine retry uses reconciliation rather than duplicate physical dispatch.

**Sources:** [services/agribrain/irrigation_runtime/actuator.py:174](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/actuator.py#L174-L190); [services/agribrain/irrigation_runtime/schemas.py:210](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/schemas.py#L210-L236).

### R04 — P0 — Quota reservations are local, not shared durable enforcement

**Package:** F16. **R3:** AB-EXE-004, AB-ARC-008.

Reservations live in each `SafetyMonitor`'s `_reserved_quota` dictionary, keyed by event and plot. Two independently constructed workers do not see one another's reservations.

**Probe:** two independent dispatcher/monitor instances, distinct devices, one plot, and a daily/season budget of 10 mm each accepted an 8 mm event. Total accepted reservation was 16 mm. The earlier exhausted-budget telemetry bypass is fixed: 0 mm remaining produced no START calls with `None`, empty and populated telemetry.

A separate completion probe accepted a second 8 mm event after the first completed while the supplied budget still reported 10 mm remaining. This demonstrates that the inspected runtime does not itself debit that budget object. A correctly integrated external budget owner could address consumption; that integration must be explicit and verified rather than assumed.

**Repair:** use a shared atomic budget owner with tenant/farm/plot/cycle scope, transactionally reserve before command admission, and settle measured delivery or retain unknown exposure. Define exactly which component debits cumulative usage. Use fencing and idempotent reserve/settle transitions across workers/restarts.

**Acceptance:** two processes against the same shared store cannot jointly exceed budget. Confirmed delivered volume cannot become reusable budget after mere reservation removal. Missing telemetry cannot bypass this rule.

**Qualification:** no single-event-loop check/reserve race is alleged here. The shown defect is separation of worker-local stores and missing demonstrated settlement integration.

**Sources:** [services/agribrain/irrigation_runtime/safety.py:133](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/safety.py#L133-L224); [services/agribrain/irrigation_runtime/safety.py:470](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/safety.py#L470-L545); [services/agribrain/irrigation_runtime/dispatcher.py:144](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/dispatcher.py#L144-L192).

### R05 — P0 — Restart resets the deadline; the watchdog still needs a caller

**Package:** F16, with F18 restart integration. **R3:** AB-EXE-004.

The monotonic clock and unconditional evaluation within the polling call are improvements. The dispatcher/monitor do not themselves install a deadline task. `check_execution_status()` first awaits a controller query and then evaluates the watchdog. Protection still depends on the polling owner and communication behavior.

On restart, `reconcile_on_restart()` calls `track_event_start()` with the full planned duration, assigning a new monotonic start. It does not reconstruct remaining runtime from a persisted original deadline.

**Probes:** after 601 simulated seconds for a 10-minute event, no stop occurred until the explicit poll; an empty/None-telemetry poll then stopped it. For a restarted event with 9 minutes already elapsed, 2 further simulated minutes left it `EXECUTING` with no stop: restart granted a fresh allowance.

**Repair:** persist original start/deadline and delivery limits. Recover remaining runtime conservatively, with explicit uncertainty where necessary. Give the deadline watchdog a verified scheduling owner independent of incoming telemetry; ensure a stalled status query cannot postpone a due stop. Use controller-side maximum runtime where supported and reconcile timer ownership across workers.

**Acceptance:** telemetry silence and blocked status queries cannot defeat deadline handling; restarting at minute 9 of a 10-minute limit does not grant another 10 minutes. The probe does not claim that every deployed controller lacks its own hardware watchdog; such protection was not established by these changes.

**Sources:** [services/agribrain/irrigation_runtime/safety.py:174](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/safety.py#L174-L198); [services/agribrain/irrigation_runtime/dispatcher.py:281](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/dispatcher.py#L281-L333); [services/agribrain/irrigation_runtime/dispatcher.py:408](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/dispatcher.py#L408-L460).

### R06 — P0 — Nonfinite command parameters reach physical dispatch

**Packages:** F16/F17, shared F01 numeric admission. **R3:** AB-EXE-004, AB-DAT-005/006.

`IrrigationCommand.validate()` uses comparisons such as `< 0` and `<= 0`. NaN fails neither comparison. Capability comparisons also fail to reject it.

**Probe:** START with NaN volume, duration and flow returned an empty validation-error list, succeeded and generated one physical START call in the driver boundary.

**Repair:** apply finite-real validation before coercion to every physical dose/rate/duration field, reject booleans and malformed types, enforce physical bounds, and preserve valid zero only where that command's semantics permit it. Apply the same contract before quota admission and serialization.

**Acceptance:** invalid numeric values produce zero physical sends and cannot weaken quota/deadline arithmetic.

**Sources:** [services/agribrain/irrigation_runtime/schemas.py:219](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/schemas.py#L219-L237); [services/agribrain/irrigation_runtime/actuator.py:128](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/actuator.py#L128-L165).

### R07 — P1 — Identical hydraulic requests integrate water twice

**Packages:** F08, F09. **R3:** AB-DAT-011/012, AB-AGR-007.

The runner stores the newly computed step hash as `predecessor_hash`. On a later comparison, the forcing hash is recomputed using that stored hash as predecessor. The replay/initial-state selection path can then use already advanced memory for the same day. The cache's idempotence guard does not prevent the resulting repeat transition.

**Probe:** same input object, timestamp, weather, plot and vegetation, run twice:

| Result | First call | Identical second call |
|---|---:|---:|
| Top-layer VWC | 0.2007 | 0.1730 |
| Second-layer VWC | 0.2218 | 0.2139 |
| Checkpoint sequence | 1 | 2 |

The full profiles and checkpoint IDs are recorded in section 10. This is not a serialization-tolerance discrepancy: the second call consumes another transition.

**Repair:** retain the actual predecessor before computing the successor. Key immutable transitions by full scope, interval, admitted evidence/parameter identities and predecessor state content. A repeated identical transition returns the committed result without integration or sequence advancement. Revisions replay from a stable earlier snapshot, not the affected day's posterior.

**Acceptance:** repeated identical calls preserve soil/hydraulic memory and checkpoint head exactly. Daily, sparse, warm and cold execution agree for the same admitted interval inputs.

**Sources:** [services/agribrain/layer3_decision/runner.py:1735](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L1735-L1803); [services/agribrain/layer3_decision/runner.py:1850](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L1850-L1948); [services/agribrain/layer3_decision/runner.py:2000](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L2000-L2050).

### R08 — P1 — A checkpoint ID can overwrite immutable history and become its own parent

**Package:** F09. **R3:** AB-DAT-003/011/012.

`save_hydraulic_checkpoint()` atomically replaces the checkpoint file even when its ID already exists. The CAS head value is the caller's checkpoint ID rather than demonstrated immutable payload identity. Reusing an ID with different content therefore changes the record without changing that identity.

**Probe:** commit `C1` with theta 0.2; commit `C1` again with theta 0.9 and expected predecessor `C1`. Both succeed. The record now has theta 0.9, sequence 2 and predecessor `C1`: a self-parent.

**Repair:** immutable insert with content verification; an identical retry returns the existing result, while conflicting content under the same ID is rejected. Derive or verify identity from canonical content and predecessor; prohibit self-parent/cyclic lineage. Publish the head only to a fully durable immutable record.

**Acceptance:** earlier records cannot be rewritten, conflicting duplicate IDs fail, identical retries do not create new sequence numbers, and lineage is acyclic. The positive CAS probe did reject a genuinely stale expected head; that narrow guarantee remains real.

**Sources:** [services/agribrain/world_model/canonical_worldline.py:253](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/world_model/canonical_worldline.py#L253-L305).

### R09 — P1 — A newer durable head does not refresh warm cached state

**Package:** F09. **R3:** AB-DAT-012/013, AB-ARC-008.

The runner reads the latest checkpoint and updates `expected_head` on each call, but hydrates its state only if in-memory history is empty. A warm worker can therefore acknowledge the newest head identity while computing from older RAM state. Its CAS then succeeds because it presents the new identity, not the identity of the state it used.

**Probe:** another writer commits `foreign-head`, with a different supported soil state. Warm and cold execution of the same next-day forcing yield different profiles: top-layer 0.1489 versus 0.2412. The warm worker successfully commits with predecessor `foreign-head` despite not loading its state. This is a controlled replica-interleaving simulation against the real store API, not a claim that a stress test of all process topologies was run.

**Repair:** bind every cached state to its committed head/version. If the head differs, reload and reconcile before solving. CAS must compare the exact predecessor used in computation. On conflict, discard the candidate and retry from the newly committed head.

**Acceptance:** workers cannot publish a successor from stale RAM under a newly read head token.

**Sources:** [services/agribrain/layer3_decision/runner.py:1111](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L1111-L1208); [services/agribrain/layer3_decision/runner.py:2040](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L2040-L2088).

### R10 — P1 — A rejected CAS leaves unpublished hydraulic state in RAM

**Package:** F09. **R3:** AB-DAT-012, AB-ARC-008.

History, vegetation/soil registries and hydraulic memory are mutated before checkpoint CAS. `ConcurrencyConflictError` is re-raised, but those mutations are not rolled back or replaced by the authoritative head.

**Probe:** force the real commit boundary to reject a raced head. The function raises `ConcurrencyConflictError` but leaves two memory entries (scoped entry and legacy alias) and a history record for `2026-01-02`.

**Repair:** solve against an isolated candidate snapshot. Publish cache mutations only after durable commit, or transactionally restore/reload all coupled registries after rejection.

**Acceptance:** a failed commit cannot seed subsequent execution, replay, withdrawal state or output authority.

**Sources:** [services/agribrain/layer3_decision/runner.py:2000](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L2000-L2099).

### R11 — P1 — Persistence failure still returns an ordinary water result

**Package:** F09. **R3:** AB-DAT-003/012, AB-ARC-008.

Non-CAS checkpoint failures are logged and suppressed, after which the runner returns the water state and feedback normally. The caller receives no explicit durable-commit failure in this returned tuple.

**Probe:** injected `OSError` at checkpoint persistence; the runner returned a non-null water result, retained two memory entries and recorded the day in history.

**Repair:** distinguish a speculative/degraded calculation from a committed canonical state in the typed return contract. A durability failure must block canonical publication/action where that capability requires a committed state. Restore or isolate RAM candidates and preserve an explicit failure receipt.

**Acceptance:** disk/store outage cannot silently return a result that consumers treat as durably canonical. Diagnostic calculations can remain available with an explicit limited role.

**Sources:** [services/agribrain/layer3_decision/runner.py:2085](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L2085-L2099); caller attachment [services/agribrain/layer3_decision/runner.py:756](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L756-L766).

### R12 — P1 — Withdrawn-date representation prevents checkpoint persistence

**Package:** F09. **R3:** AB-DAT-003/012.

Withdrawal admission adds ISO date strings to the sets. Checkpoint serialization later calls `.isoformat()` on each member. Hydration instead constructs date objects, while lookups generally use strings. These representations disagree.

**Probe:** `soil_observations_daily={'2026-01-02': {'status':'withdrawn'}}` returns a water result but creates zero checkpoint JSON files. The persistence branch logs `'str' object has no attribute 'isoformat'`. The withdrawal exists only in memory in this fixture.

**Repair:** one canonical date-key representation across admission, serialization, hydration and lookup. Persist tombstones with affected evidence IDs, cutoff/version and revision lineage. Apply identical rules to vegetation withdrawals.

**Acceptance:** withdrawal survives cold restart and subsequent replay; cancelled/deleted evidence cannot be resurrected by retained maps or checkpoint hydration.

**Sources:** [services/agribrain/layer3_decision/runner.py:1153](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L1153-L1163); [services/agribrain/layer3_decision/runner.py:1387](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L1387-L1449); [services/agribrain/layer3_decision/runner.py:2057](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L2057-L2062).

### R13 — P1 — The new exception handler can itself raise UnboundLocalError

**Packages:** F09 and F38 integration. **R3:** AB-ARC-008/011.

The module-level `ConcurrencyConflictError` import is shadowed by an import inside `_execute_canonical_water_engine()`. That local name is assigned late in the function. Earlier errors reach `except ConcurrencyConflictError` while the local variable is unbound.

**Probe:** valid weather with malformed L2 `lai_mean='bad'` raised `UnboundLocalError: cannot access local variable 'ConcurrencyConflictError' where it is not associated with a value` instead of a structured qualification failure.

**Repair:** import the exception once through the canonical namespace outside the execution function; avoid local rebinding. Validate adapters explicitly and return/raise the intended typed error.

**Acceptance:** errors before and after hydration, solve and persistence resolve to the intended error contract without secondary handler failures. Include this regression in the F38 scope when its full package is delivered.

**Sources:** [services/agribrain/layer3_decision/runner.py:798](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L798-L806); [services/agribrain/layer3_decision/runner.py:2044](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L2044-L2099).

### R14 — P1 — Temporal admission is incomplete for archives and direct soil assimilation

**Package:** F02. **R3:** AB-DAT-004/014, AB-ML-008.

The new dynamic-record helper requires both observation and availability timestamps, and rejects late availability in the positive-control probe. The archive path still gates primarily by `last_update_date`; it ignores later archive issuance/availability. At the direct water-engine boundary, a `SoilObservationVector.timestamp` after the run time is not rejected before assimilation.

**Probes:** a certified archive with observation/update date 2 January, but `available_at` and `issued_at` 3 January, remains contract-valid at a 2 January cutoff and contributes vigor 0.9. Separately, the water engine running 2 January accepted five soil values timestamped 3 January, introducing a 317.64 mm analysis increment in this fixture.

**Repair:** gate archived posteriors on immutable issuance/availability and admissible parent versions, not only measurement date. Pass an explicit knowledge cutoff through water observation admission, enforce timestamp/support roles at public engine boundaries and dictionary adapters, and retain late data only for a correctly labelled later reconstruction. Prior-issued future weather remains eligible for the scenario role, not the observed-state role.

**Acceptance:** late archives and future/late soil observations cannot modify earlier-issued state or labels through any supported caller. Preserve eligible prior-issued forecast scenarios.

**Sources:** [services/agribrain/layer05_asmae/resilient_posterior.py:129](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer05_asmae/resilient_posterior.py#L129-L156); [services/agribrain/layer05_asmae/resilient_posterior.py:864](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer05_asmae/resilient_posterior.py#L864-L923); [services/agribrain/layer3_water/runner.py:134](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/runner.py#L134-L145); [services/agribrain/layer3_water/runner.py:262](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/runner.py#L262-L272).

### R15 — P1 — Weather-adapter coercion launders booleans into observations

**Package:** F01. **R3:** AB-DAT-005/006, AB-ARC-005/006.

The shared `finite_real()` helper correctly rejects booleans, NaN, infinity and numeric strings while preserving numeric zero. The L3 adapter first applies `float()` to raw weather values. This removes the original type before the water engine's finite-real check.

**Probe:** `precipitation_mm=True` in the raw weather record produced a valid water result with published precipitation 1.0 mm.

**Repair:** qualify original raw values before any coercion; preserve rejected component reasons and field-level roles through adapter boundaries. Apply the same rule to vegetation and uncertainty fields.

**Acceptance:** booleans/malformed values cannot alter soil state, while actual numeric 0 mm remains 0 mm.

**Sources:** [services/agribrain/layer3_decision/runner.py:971](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py#L971-L1033); [services/agribrain/layer3_water/runner.py:104](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/runner.py#L104-L114); [services/agribrain/scientific_contracts/numeric.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/scientific_contracts/numeric.py).

### R16 — P2 — Valid positive conductivity is rounded to zero

**Package:** F04. **R3:** AB-AGR-003, AB-DAT-007.

The factory checks conductivity is strictly positive, then rounds the returned vector to two decimal places. The returned dataclass does not repeat the positivity check.

**Probe:** `[0.001, 0.001]` cm/day was accepted and returned as `[0.0, 0.0]`, changing the declared physical parameters and eliminating conductivity in subsequent calculations.

**Repair:** retain solver precision for hydraulic parameters; limit rounding to display/serialized conventions that explicitly preserve required precision. Validate after any canonical transformation, and keep computed potentials consistent with the actual stored parameters.

**Acceptance:** valid heterogeneous positive profiles retain their parameters and storage; accepted alpha/n/Ks values are not silently replaced by incompatible bounded values.

**Sources:** [services/agribrain/layer3_water/contracts/state_factory.py:114](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/contracts/state_factory.py#L114-L135); [services/agribrain/layer3_water/contracts/state_factory.py:142](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/contracts/state_factory.py#L142-L184).

### R17 — P1 — Caller-supplied checkpoint IDs bypass store containment

**Package:** F09. **R3:** AB-DAT-013, AB-ARC-008.

`_hydraulic_checkpoint_path()` appends `checkpoint_id` directly to a path. The plot-directory containment check does not validate this new component.

**Probe:** within an isolated temporary directory, checkpoint ID `../../../../../escaped` was accepted and wrote `escaped.json` outside the configured store root. No real repository or unrelated user file was touched.

**Repair:** restrict ID syntax and verify the final resolved path stays inside the intended scoped checkpoint directory; reject path separators, absolute paths and traversal. Validate stored head references before using them for reads as well.

**Acceptance:** malformed identity cannot read/write outside its allowed scope. This is a demonstrated service-boundary containment defect; an externally reachable HTTP exploitation path was not established in this review.

**Sources:** [services/agribrain/world_model/canonical_worldline.py:237](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/world_model/canonical_worldline.py#L237-L250); [services/agribrain/world_model/canonical_worldline.py:290](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/world_model/canonical_worldline.py#L290-L304).

## 4. Additional qualification limits

These source-level observations deserve acceptance coverage, but are not counted as additional reproduced findings:

- Hydraulic cache keys and checkpoint paths distinguish tenant/namespace/plot, while cycle, geometry and parameter epoch are primarily metadata. No complete validation/migration contract for changing these scopes is established by the new path. Physical soil continuity across crop cycles can be legitimate; it must be an explicit scoped transition rather than implicit cache reuse.
- Checkpoint history persists computed soil/memory and weather/vegetation summaries, but omits accepted soil-observation payloads and hydrates `soil_observations=None`. Replaying an earlier corrected interval requires original admitted evidence, not just its former posterior. Full restart/correction acceptance should exercise that case.
- The new checkpoint API's default `CAS_UNSET` permits calls without a predecessor check. Its guarantee therefore depends on every admitted writer providing the required expected head and using the same store/lock topology. Multi-host replicas need a verified shared transaction boundary.
- Imputed weather remains explicitly marked and its 0.08 uncertainty reaches the ET0 calculation. This is a real improvement. It is not evidence of continuous interpolation or of observed missing-day rainfall. Downstream outputs/training must preserve the prior role and the associated authority/eligibility limits.
- A nominal debit callback, hardware watchdog, controller idempotency feature or replica store could close a deployment integration gap, but it must be identified and exercised. This review does not assume such components exist merely because an interface can support them.

## 5. Which implementation claims can be retained

| Package/slice | Verified improvement | Acceptance qualification |
|---|---|---|
| F37-ES | GMM imported from `sklearn.mixture`; fresh import and actual GMM consumer run succeed | Full F37 namespace/entrypoint migration remains separate |
| F35-ES | Optional driver import is isolated by capability logic | Full durable driver/job cleanup is not established by this slice |
| F38-ES01/02/03 | Local missing imports and resolution initialization are present in production source | Local scope only; R13 demonstrates a new runtime-name regression elsewhere |
| F32-ES | Dashboard catch path returns HTTP 503, `stats:null`; genuine account counts retain zeros | Source verified; full product/calendar integration and actual DB behavior not independently accepted here |
| F01 | Shared numeric helper, payload checks and rejected observation components improve admission | R15 shows an adapter bypass; R06 shows physical numeric admission still unsafe |
| F02 | Dynamic evidence cutoff helper rejects late availability | R14 shows archive and direct soil paths remain incomplete |
| F03 | Explicit transition and analysis receipts exist; published and integrated transpiration agree at 5.22 mm in the probe | This verifies the sampled receipt behavior, not all modes/consumers or entire package acceptance |
| F04 | Reversed depths are rejected; retention/vector validation is stronger | R16 violates positive-parameter preservation |
| F06 | Exact target-date selection and past-only gap priors improve weather timing; imputation uncertainty propagates | Attachment overstates interpolation; full trajectory/timing acceptance remains linked to F02/F08/F09 |
| F07 | Past-only canopy selection and wetting/evaporation memory changes exist | Cross-restart and idempotent sparse integration are not accepted while R07–R12 remain |
| F08 | Full retention/conductivity/n/alpha profiles enter the soil digest | R07 violates identical-request idempotence |
| F09 | Checkpoint read/write, scoping and expected-head CAS are implemented; stale-CAS positive control passes | R07–R13 and R17 block full acceptance |
| F16 | Exhausted-budget checks run without telemetry; monotonic watchdog runs during explicit polling | R01/R04/R05/R06 block full safety acceptance |
| F17 | START keeps an active command; explicit stop is admissible | R01/R03 and numeric admission still violate supported boundary behavior |
| F18 | Attempt identity and status reconciliation are present | R02 directly disproves idempotent application; restart/unknown outcomes require qualification |
| F19 | Debounce honors 15 seconds; the sustained probe emits one new violation | Narrow sampled behavior verified; additional multi-zone-pressure claim is not established |

“Implemented”, “narrow probe verified” and “full acceptance passed” are distinct states. No package should be signed off solely because a commit title names it or because a small test count is green.

## 6. Current plan-folder integrity

| Check | Result |
|---|---:|
| Plan documents, exact current blob content | 8/8 |
| Canonical packages | 52 |
| Scheduled stages | 17 |
| Package appearances, unique and complete | 52/52 |
| Declared package dependency inversions | 0 |
| Atomic tickets | 285 |
| Numeric/full-delivery tickets | 225 |
| Early-slice tickets | 8 |
| Full acceptance milestones | 52 |
| Unresolved named ticket prerequisites | 0 |
| Ticket dependency cycles | 0 |
| Checked acceptance/work tickets | 0 |
| Original engineering-hour sum | 2,564–4,540 |
| Historical pinned reference blobs verified | 94/94 |
| Those reference paths changed since historical baseline | 20 |

The historical 94 blob references are correct for `26d5c3f`; they should not be described as matching all current production files. Twenty of their referenced paths now have different current content. Keep historical evidence and current verification revisions separately pinned.

The previously identified Omega dangling prerequisites are corrected. O1 now names the real FA milestones for F12, F21, F36, T01, T02 and T04. Early-slice reuse links exist, and the concurrency note explicitly permits the safety lane without waiting for unrelated stages. F29's R² task now targets `asmae_evaluator.py`; F36's noise/threshold task now targets the filter and config; F38's two-file corrections have co-targets. These earlier findings should not be repeated as still unfixed.

Three execution-document issues remain material:

1. **Acceptance progress is absent.** All checkboxes are unchecked. Reconcile each implementation commit to actual numeric/ES work tickets with scoped evidence, date and current revision. Keep FA unchecked where the counterexamples fail. Do not mass-check eleven or twelve packages.
2. **Some verification contracts remain too broad or attached to the wrong task type.** F40's local Python annotation slice still includes Next.js/Prisma checks. T04's joint rollout task targets the forecast archive without a complete dynamics/observation-engine decomposition. T08's proposed livestock/order/quality/logistics work is still concentrated on a cycle-task route. O1's schema verification requests Bayesian convergence/causal identification/replication that belong to later scientific milestones. Rewrite these before their respective task starts; they do not justify blocking the urgent fixes above.
3. **The authoritative R3 reference is not directly accessible from the repository.** README names an R3 PDF, while the current tree contains the R2 DOCX and no named R3 document. Add an accessible versioned R3 reference, content identity and requirement-register location. Preserve the monograph's target-only character. Do not replace R3 with the attachment's package paraphrases.

The program total is an original estimate, not a verified remaining-effort estimate. Early work is included in parent budgets. Update remaining effort from accepted task scope and measured work; do not deduct invented full-package completions or add the 30–58 early-slice hours twice.

**Sources:** [plan/README.md](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/plan/README.md); [plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md); [plan/AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/plan/AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md); [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md).

## 7. Restore the correct pending-work definitions

The attachment replaces many canonical package meanings with unrelated features. Those features may be legitimate target work elsewhere, but must not inherit the acceptance identity, dependencies or estimate of another package. The following are the actual master definitions.

| ID | Canonical package meaning |
|---|---|
| F05 | Use depth-aware soil observations and carry covariance |
| F10 | Repair the L3-to-L4 water boundary |
| F11 | Correct residual nitrogen demand and expose conservative pools |
| F12 | Separate exposure verification from causal attribution |
| F13 | Correct yield quantiles and distinguish calibrated distributions from heuristics |
| F14 | Repair L7-to-L8 crop scenario mapping |
| F15 | Unify weather constraints and final hard action limits |
| F20 | Qualify post-irrigation readings before confirming delivery |
| F21 | Freeze training-window payloads and include partition identity |
| F22 | Classify timing by event role rather than a universal causality rule |
| F23 | Commit forecast archives atomically before publishing cache entries |
| F24 | Validate forecast distributions and make missing scores unavailable |
| F25 | Report the actual EO inference backend and normalize its input contract |
| F26 | Hash complete EO support and distinguish missing bands from zero |
| F27 | Repair MESIA link-time axes and graph topology |
| F28 | Make MESIA masked pretraining respect complex channel semantics |
| F29 | Correct MESIA evaluation labels and establish independent biological validation |
| F30 | Scope conversational memory and cache identity |
| F31 | Close the independent public AI advice path |
| F32 | Replace demo calendar and misleading empty/error application states |
| F33 | Validate photo zone ownership and database insert success |
| F34 | Separate input accounting from applied agronomic exposure |
| F35 | Repair drone driver import and complete process cleanup |
| F36 | Require per-variable observability and independent predictive calibration |
| F37 | Repair optional imports and establish one Python package identity |
| F38 | Restore failure ledgers, scoped loading and degraded publication |
| F39 | Make telemetry persistence and replay protection concurrency safe |
| F40 | Resolve annotation consumers and close verification evidence gaps |
| T01 | One canonical coupled agricultural trajectory |
| T02 | Objective-specific longitudinal learning corpus |
| T03 | Multimodal foundation representation and local adaptation |
| T04 | Hybrid world model with conservative multi-horizon rollout |
| T05 | Decision economics from shared outcome distributions |
| T06 | MESIA native acquisition, metrology and capability commissioning |
| T07 | Omega scientific investigation loop |
| T08 | Finish AgriWise operational records and financial workflows |
| T09 | Unify language, voice, map and offline product projections |
| T10 | Institutional aggregation and territorial world-model extension |
| T11 | Operational reproducibility, provider resilience and publication integrity |
| T12 | Independent agronomic validation and reference field program |

Examples of consequential substitutions: F11 is residual **nitrogen** demand, not multilayer root-water uptake; F14 is the **L7-to-L8 crop adapter**, not deep percolation; F27–F29 are **MESIA learning/evaluation** repairs, not weeds/cover crops/carbon modules; T04 is the **hybrid world model**, not actuator HIL; T05 is **decision economics**, not edge inference; T06 is **native MESIA acquisition/metrology**, not generic multi-tenant compliance. Reassigning those IDs would leave their original defects untreated while falsely closing requirements.

Use [plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md) as the package-identity authority. The attachment is a progress claim to be checked, not a substitute roadmap.

## 8. Detailed next implementation sequence

Proceed with bounded corrective work now. Apply this order by dependency and urgency; the addendum's full-acceptance stages are not a requirement to serialize independent engineering.

### Batch A — Contain physical-command failures

1. **Close raw numeric admission first:** R06 and R15. Qualify original values with the shared finite-real contract before conversion, reservation or command dispatch. Exercise NaN/Inf/bool/string, negative, zero and valid positive values at both supported adapter and direct API boundaries.
2. **Repair stop/unknown states:** R01. Introduce an explicit typed unresolved-stop outcome; preserve the originating delivery command and quota/lease until confirmation. Cover cancellation, watchdog, controller ERROR and global stop through the same reconciliation contract.
3. **Repair logical operation admission:** R02/R03. Establish an immutable scoped operation record, payload identity, attempt receipts and atomic owner/fencing. Prevent empty provenance IDs from equating unrelated operations. Document each driver's reconciliation capability.
4. **Persist and schedule limits:** R04/R05. Shared atomic reservation/settlement, original deadlines and telemetry-independent deadline ownership. Verify two actual processes against the selected store topology, clock/restart behavior and hung status queries.
5. **Re-evaluate F16–F19 full acceptance:** retain verified debounce work and execute the master criteria against the integrated runtime. Do not weaken those criteria to match the previous small tests.

**Exit:** physical failures remain unknown until reconciled; invalid inputs generate zero sends; one operation cannot cause duplicate delivery; independent workers cannot overspend; restart cannot extend the original limit.

### Batch B — Make one hydraulic transition durable and replayable

1. **Fix error handling and date representation:** R13/R12. Move the canonical exception import out of the function; standardize date keys and withdrawal serialization/hydration.
2. **Make checkpoint identity immutable and contained:** R08/R17. Canonical content identity, immutable insert/conflicting-ID rejection, containment checks and validated head references. Preserve historical records and rejection receipts.
3. **Fix the transition/predecessor model:** R07. Capture predecessor before updating its hash; distinguish the interval's initial state from its posterior; return a committed identical transition without another solve.
4. **Stage coupled candidate changes:** R10/R11. No authoritative RAM mutation/publication before durable CAS. On failure, preserve explicit limited diagnostics and reload or roll back all candidate registries.
5. **Bind RAM to durable head and scope:** R09. Reconcile every changed head before solving; validate tenant/namespace/plot/cycle/geometry/parameter epoch or use an explicit migration transition. Persist admitted evidence required for earlier-interval replay, not only computed state summaries.
6. **Verify full F08/F09 integration:** exact-repeat idempotence; warm/cold equality; sparse/daily equality; late weather/soil/management correction; withdrawal; mid-commit failure; process crash; separate worker contention; changed scope and shared-store replica behavior.

**Exit:** an identical interval has one transition/head; stale workers cannot replace newer authoritative state; a rejected candidate cannot survive as accepted RAM; withdrawals and corrections survive restart. Declare numerical tolerances per physical quantity and solver discretization, not by expanding them until a repeated-day error passes.

### Batch C — Complete scientific admission and physical precision

1. **Close archive and direct observation cutoff gaps:** R14. Immutable archive issuance/availability, parent versions, run knowledge cutoff and typed observation-support roles. Retain retrospective reconstructions with a separate role.
2. **Preserve hydraulic parameters:** R16. Remove solver-input rounding that creates zero conductivity; check consistency of stored alpha/n with computed hydraulic potentials and explicit parameter provenance.
3. **Re-evaluate F01–F07 acceptance:** trace raw input to accepted component, transition receipt, uncertainty, label eligibility and downstream boundary. Confirm valid zero and missingness semantics across all supported paths.

**Exit:** no post-cutoff data can enter an earlier-issued state; priors/reconstructions/forecasts cannot be promoted to measurements by adapters; realized fluxes and analysis increments remain distinct.

### Batch D — Reconcile plan progress, then resume canonical downstream packages

1. Map verified ES/numeric work to commits and independent receipts. Record implemented/limited-verified/full-accepted states distinctly. Reopen the affected FA gates.
2. Restore the pending-package meanings from section 7; pin current verification revisions alongside historical defect references.
3. Complete F39-ES/F40-ES and full F37 using their actual startup, nonce topology and introspection contracts. Avoid an unrelated frontend acceptance requirement for a local Python annotation fix.
4. Resume F05, F10, F11 and F12 according to admitted dependencies: depth-aware observation support, L3-to-L4 boundary, residual nitrogen/pools, and exposure-versus-causal-attribution. They are not the energy/salinity replacements in the attachment.
5. Continue remaining correction packages in the addendum order, rewriting each eligible task's exact symbols, consumers and controlled verification before implementation. Keep independent application/research work moving when its own prerequisites are satisfied.

**Exit:** progress claims resolve to the correct package contract and demonstrably current production behavior. Original estimates and completed work are not double-counted.

## 9. When to proceed with the world model and Omega

**Proceed now with the repairs above and limited research preparation.** Do not wait for another general repository-wide review before implementing the concrete reproducible fixes.

**Proceed with integrated hybrid-world-model delivery** once T01/T02/T03 and the corrected F12/F23/F24 prerequisites provide one scoped, durable coupled trajectory; an objective-specific immutable corpus; admitted representations; qualified actual/scenario actions; as-issued forecasts; and honest evaluation. A forecast archive alone is not the dynamics model. Full T04 acceptance requires conservative multi-horizon rollout, memory sufficiency and predeclared held-out skill/calibration checks.

**Proceed with full Omega integration** when its master prerequisites F12, F21, F36, T01, T02 and T04 are accepted at their required scope. Preserve the R3 scientific progression: immutable ScientificCase and competing explanations; surprise and model inadequacy; Bayesian laboratory; causal identification and measurement policy; hidden regimes; candidate mechanisms/equations; experimental design; falsification, replication and transport. O1 schema creation should not require O11 empirical success merely to be implemented.

Experimental design and independent reference-data collection can begin earlier through a clearly scoped research milestone. They must retain evidence cutoffs, intervention/delivery uncertainty, missingness and identification assumptions. An engineering pass is not empirical agronomic certification, and an Omega authority tag is not scientific discovery.

## 10. Independent probe receipts

These are fresh outputs of production calls at the pinned revision. They are included for reproducibility and comparison; the findings are established by inspected source plus controlled calls, not by treating this report as an independent source of truth. The hardware boundary is simulated, and the temporary-store failures/interleavings are deliberately controlled.

```json
{
  "numeric_helper_positive_control": [
    {
      "input": "0",
      "result": 0.0
    },
    {
      "input": "True",
      "result": null
    },
    {
      "input": "nan",
      "result": null
    },
    {
      "input": "inf",
      "result": null
    },
    {
      "input": "0",
      "result": null
    }
  ],
  "soil_geometry_positive_control": {
    "reversed_depths_rejected": true
  },
  "CAS_positive_control": {
    "stale_predecessor_rejected": true
  },
  "checkpoint_same_id_overwrite": {
    "before_theta": 0.2,
    "after_theta": 0.9,
    "checkpoint_id": "C1",
    "predecessor_head": "C1",
    "sequence": 2
  },
  "checkpoint_id_escapes_store": {
    "rejected": false,
    "outside_store_file_exists": true
  },
  "runner_early_exception": {
    "exception_type": "UnboundLocalError",
    "message": "cannot access local variable 'ConcurrencyConflictError' where it is not associated with a value"
  },
  "runner_persistence_failure": {
    "returned_water_state": true,
    "memory_entries": 2,
    "history_days": [
      "2026-01-02"
    ]
  },
  "runner_CAS_conflict_leaves_memory": {
    "exception_type": "ConcurrencyConflictError",
    "memory_entries": 2,
    "history_days": [
      "2026-01-02"
    ]
  },
  "runner_good_persistence_control": {
    "returned_water_state": true,
    "files": 2
  },
  "repeat_identical_request": {
    "returned_state": true,
    "theta_first": [
      0.2007,
      0.2218,
      0.2253,
      0.2277,
      0.2295
    ],
    "theta_repeat": [
      0.173,
      0.2139,
      0.221,
      0.2259,
      0.2295
    ],
    "checkpoint_sequence_first": 1,
    "checkpoint_sequence_repeat": 2,
    "checkpoint_id_first": "cp_hyd_P_2026-01-02_27f7f11906b7",
    "checkpoint_id_repeat": "cp_hyd_P_2026-01-02_7168fd8b582e"
  },
  "warm_cache_ignores_new_committed_head": {
    "warm_theta": [
      0.1489,
      0.2052,
      0.2163,
      0.2239,
      0.2295
    ],
    "cold_theta": [
      0.2412,
      0.2623,
      0.2658,
      0.2682,
      0.28
    ],
    "warm_committed_predecessor": "foreign-head",
    "foreign_theta": [
      0.4,
      0.4,
      0.4,
      0.4,
      0.4
    ]
  },
  "withdrawal_checkpoint_serialization": {
    "returned_water_state": true,
    "checkpoint_json_files": 0,
    "in_memory_withdrawals": [
      "2026-01-02"
    ]
  },
  "future_soil_observation_at_direct_engine_boundary": {
    "run_time": "2026-01-02T00:00:00+00:00",
    "observation_time": "2026-01-03T00:00:00+00:00",
    "assimilated_count": 5,
    "analysis_increment_mm": 317.64
  },
  "flux_receipt_positive_control": {
    "published_transpiration": 5.22,
    "receipt_transpiration": 5.22,
    "analysis_increment_mm": 317.64
  },
  "small_positive_conductivity": {
    "published": [
      0.0,
      0.0
    ]
  },
  "availability_cutoff_positive_control": {
    "early_observation_late_available_accepted": false,
    "both_early_accepted": true
  },
  "archive_after_issuance_admitted": {
    "cutoff": "2026-01-02T00:00:00+00:00",
    "archive_available_at": "2026-01-03",
    "archive_issued_at": "2026-01-03",
    "contract_valid": true,
    "vigor": {
      "mean": 0.9,
      "sigma": 0.1,
      "status": "temporally_conditioned",
      "support": [
        "scene-A",
        "scene-B",
        "certified_archive_posterior"
      ],
      "spatial_support": "plot_level_only",
      "archive_age_days": 0
    }
  },
  "boolean_weather_accepted": {
    "input_rain_repr": "True",
    "returned_water_state": true,
    "published_rain_mm": 1.0
  },
  "quota_exhaustion_positive_control": [
    {
      "readings": null,
      "status": "FAILED",
      "sends": 0
    },
    {
      "readings": {},
      "status": "FAILED",
      "sends": 0
    },
    {
      "readings": {
        "air_temperature_c": 25
      },
      "status": "FAILED",
      "sends": 0
    }
  ],
  "watchdog_requires_poll": {
    "after_elapsed_before_poll": {
      "running": true,
      "stop_calls": 0
    },
    "after_poll": {
      "running": false,
      "stop_calls": 1,
      "status": "EMERGENCY_STOPPED"
    }
  },
  "failed_emergency_stop_finalizes": {
    "running": true,
    "stop_calls": 1,
    "status": "EMERGENCY_STOPPED",
    "reserved_mm": 0.0,
    "tracked_events": [],
    "active_events": 0
  },
  "failed_cancel_finalizes": {
    "running": true,
    "status": "CANCELLED",
    "reserved_mm": 0.0,
    "active_command_type": "STOP_ZONE"
  },
  "duplicate_operation_reapplied": {
    "first_status": "EXECUTING",
    "second_status": "EXECUTING",
    "start_sends": 2,
    "operation_ids": [
      "OP-same",
      "OP-same"
    ]
  },
  "blank_source_ids_bypass_conflict_guard": {
    "operation_ids": [
      "operation-A",
      "operation-B"
    ],
    "source_event_ids": [
      "",
      ""
    ],
    "successes": [
      true,
      true
    ],
    "physical_start_sends": 2
  },
  "idle_after_ack_timeout_retried": {
    "physical_deliveries": 2,
    "event_status": "FAILED",
    "operation_ids": [
      "OP-E",
      "OP-E"
    ]
  },
  "independent_worker_quota": {
    "statuses": [
      "EXECUTING",
      "EXECUTING"
    ],
    "total_reserved_mm": 16.0,
    "budget_daily_mm": 10
  },
  "completion_does_not_debit_supplied_budget": {
    "second_status": "EXECUTING",
    "total_requested_mm": 16,
    "budget_daily_mm": 10
  },
  "restart_extends_watchdog": {
    "elapsed_before_restart_minutes": 9,
    "elapsed_after_restart_minutes": 2,
    "status": "EXECUTING",
    "running": true,
    "stop_calls": 0
  },
  "nonfinite_command_admitted": {
    "validation_errors": [],
    "success": true,
    "physical_start_sends": 1
  },
  "debounce_positive_control": {
    "counts_at_0_14_15_16": [
      0,
      0,
      1,
      0
    ]
  }
}
```

## 11. Changed production source inventory

All entries below were retrieved and verified against their current Git blob identities. Test files and historical audit contents are excluded from the production inventory.

| Production file | Current blob SHA-1 |
|---|---|
| [services/agribrain/drone_control/dispatcher.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/drone_control/dispatcher.py) | `c355ac69bcdd20e3fcfe91911917fe83d16a1c34` |
| [services/agribrain/irrigation_runtime/actuator.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/actuator.py) | `2bce26756180da610c2fc9c0e00081429a7bec0f` |
| [services/agribrain/irrigation_runtime/dispatcher.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/dispatcher.py) | `759c3279eac340fd09fad85bfe9afca92077a6c0` |
| [services/agribrain/irrigation_runtime/safety.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/safety.py) | `365b702bb09e5e9b3a214a5220c2443ab02b2739` |
| [services/agribrain/irrigation_runtime/schemas.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/irrigation_runtime/schemas.py) | `d5420cadb04b44764fa84298759425fa1f09fe61` |
| [services/agribrain/layer0/observation_packet.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer0/observation_packet.py) | `4623373b5d05ecf6e2834fd9eae33c4fec4fc0fb` |
| [services/agribrain/layer0/wrappers.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer0/wrappers.py) | `c14e579608a3d68fe437d9dd514efb5e8477ae29` |
| [services/agribrain/layer05_asmae/geometry/external_scene_loader.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer05_asmae/geometry/external_scene_loader.py) | `c565bb7bbf3427044cb1392a80a672a44e297c89` |
| [services/agribrain/layer05_asmae/history/worldline_service.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer05_asmae/history/worldline_service.py) | `4a88625a77b4a4efcc722358f34a56d3abbc7731` |
| [services/agribrain/layer05_asmae/resilient_posterior.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer05_asmae/resilient_posterior.py) | `70d0d2aa38f2885c7b059dcf374360b728ddba50` |
| [services/agribrain/layer1_fusion/segmentation.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer1_fusion/segmentation.py) | `1cb4482969630f77bda06f7999d70a37c980e171` |
| [services/agribrain/layer2_veg_int/growth_engine.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer2_veg_int/growth_engine.py) | `3c253b235a95dd5220f77b4e7aeeac6f0c0f1d5e` |
| [services/agribrain/layer3_decision/runner.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_decision/runner.py) | `393bb60352d52236af649fa1aef74bcc9cf5e36b` |
| [services/agribrain/layer3_water/assimilation/water_state_assimilator.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/assimilation/water_state_assimilator.py) | `7d5c84ed00e9e080ad97e42dcc4ff349831d0765` |
| [services/agribrain/layer3_water/contracts/__init__.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/contracts/__init__.py) | `9641a4e31fcced8a90a6fd04a3f86e4160a9cf97` |
| [services/agribrain/layer3_water/contracts/state_factory.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/contracts/state_factory.py) | `db3df1ef8c00a52c0002f964bb505f8e4c3df4eb` |
| [services/agribrain/layer3_water/contracts/water_state.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/contracts/water_state.py) | `830f0325048f7af889b02c62c90942f2985a0c45` |
| [services/agribrain/layer3_water/runner.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/runner.py) | `18dbcc048e660831b343fdd67af1004b5e020769` |
| [services/agribrain/layer3_water/soil/layered_water_balance.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/layer3_water/soil/layered_water_balance.py) | `7af837176741944a27b441fe2376688ad066d2a7` |
| [services/agribrain/scientific_contracts/numeric.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/scientific_contracts/numeric.py) | `6d5ab43e9553398a27c3f8bd2f4c53fe74aaf640` |
| [services/agribrain/scientific_contracts/observation.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/scientific_contracts/observation.py) | `d9849fcc76f1d18c0b6c86298a6fa98030b78323` |
| [services/agribrain/world_model/canonical_worldline.py](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/services/agribrain/world_model/canonical_worldline.py) | `796c6b20b36e139430e08cf1b7786c956e948fc5` |
| [src/app/api/dashboard/stats/route.ts](https://github.com/webClone/AgriWise/blob/170e8666db314d2711703f7b82f57c8096f095cf/src/app/api/dashboard/stats/route.ts) | `b1fd8b82c746f0193257f120f7498b0e51b3a4f1` |

The isolated probe runtime was assembled from exact production files, not replacement implementations of the algorithms. Its imported files were checked against the current recursive tree. Driver substitutes supply physical-boundary outcomes; fault injection changes only that boundary or the temporary store's commit result. No real execution, certification, database migration or field experiment was performed.

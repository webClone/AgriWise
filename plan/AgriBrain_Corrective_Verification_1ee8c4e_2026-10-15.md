# AgriBrain corrective verification — 1ee8c4e

**Date:** 15 October 2026. **Reviewed commit:** `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`. **Parent:** `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`.

## Decision

**The changes repair several original counterexamples, but the claim that all priority areas are resolved is not supported.** The six specialist reviews and coordinating probes reproduced failures in physical-operation ownership, nonce recovery, hydraulic recovery, forecast publication/scoring, and prescription feasibility. Keep the affected package acceptance gates open. Continue bounded implementation on these contracts before treating this batch as complete.

The most urgent regression is concrete: a simulated controller applies START, its ACK is lost, and production polling changes the event from STOP_REQUESTED to CANCELLED while the controller remains running. The reservation, dispatcher tracking and watchdog are removed, with a zero-delivery stopped receipt and no physical STOP. Separately, two actual OS processes both pass truthful idle preflight and send START to the same device/zone.

The principal hydraulic repair works on ordinary cold hydration: the original warm/cold correction now produces **201.13 mm on both paths**. It does not cover losing-CAS hydration: another actual two-process case produces **109.43 mm** in the losing worker versus **201.15 mm** from ordinary cold recovery of the same winning checkpoint. These are different fixtures; the values are not field measurements.

## Scope and evidence

- Retrieved the current GitHub commit, branch metadata and nontruncated tree. The delta contains **12 changed production Python files**; the user's 15-file total also includes two test files and a historical review document. Those three files were excluded from correctness evidence.
- Verified **444 staged production files** against Git blob identities in the candidate tree. Each specialist also verified imported or additionally retrieved dependencies. These overlapping counts are not a count of independently reviewed files.
- Reviewed actual production paths, then exercised isolated local collaborators, controlled thread/process schedules, and explicitly labeled I/O/crash injections. No production source or Git state was changed. No vendor, broker, controller, field hardware or drone was contacted.
- Repository test files, repository audit assertions and existing generated artifacts were not used as evidence. The claimed **602 passing tests** remains the user's reported result; this review did not rerun or certify that suite. An independent counterexample can coexist with that result.
- This is a deep corrective review of the changed areas and their consumers, **not a new full acceptance review of all 52 packages**, MESIA, Omega or the complete World Model.

Normative inputs are the R3 monograph and the three plan documents. All three local plan documents exactly match the candidate tree. The verified R3 PDF SHA-256 is `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; its scientific register contains 153 requirement IDs. The acceptance register contains **52 unique full-acceptance milestones: 52 open, 0 checked**.

## Repairs independently confirmed

| Area | Verified behavior on this commit | Limit |
|---|---|---|
| Hydraulic observations | Ordinary cold correction restores all three probe readings; warm/cold result 201.13 mm. Cold cancellation and immediate A→B scope switch also match controls. | Losing-CAS recovery and return to a previous scope still fail. |
| Nonce admission | Same-nonce OS workers have one winner; distinct nonces survive; ten threads yield one winner/nine rejections; prior stale-recoverer schedule is serialized. Registry/calibration/pre-write failures roll back and retry successfully. | Crash recovery and ownership of rollback are incomplete. |
| Shared dispatch | The missing `os` import is fixed. A refused NEW event's later poll no longer stops the known OLD owner in the sequential control. | There is no atomic cross-event device/zone admission claim; the new never-started shortcut mishandles an applied START with lost ACK. |
| MQTT | Explicit START-stopped and STOP-running cases reject; non-dictionary callbacks, thread-safe wakeup, ordinary cancellation cleanup and timeout defaults improve. Direct STOP retains a fault latch in its tested path. | STOP/query decoding differs and other successful-stop paths still clear faults. |
| Forecast archive | Durable conflicts/retries preserve the winner; post-store mutation no longer poisons it; incompatible inserts have one winner; evaluation IDs distinguish observations and microseconds; unsafe IDs reject. | A final filename is exposed before serialization completes, and copies taken at different times can disagree. |
| Scoring | Empty quantiles, illegal levels/values and invalid sigma reject. Missing p50 is no longer borrowed from the observation. Valid Gaussian and point-mass controls work. | Missing components are NaN; invalid observations/means can still receive CRPS 0. |
| ASMAE cache | Six legacy negative fixtures now miss on read; writer/reader predicates match; NPZ/JSON integrity and input-identity controls pass. | An actual timeout producer uses an unrecognized failure status. Its restrictive flags remain intact. |
| Weather and dose | The original 21 mm ceiling is preserved. m/s conversion, gust checks, finite/Boolean checks, missing spray weather and simple date-only sorting pass. | Invalidity can be erased before final validation; lower bounds and temporal validity remain incomplete. |

## Remaining review groups

The identifiers DV01–DV18 below apply only to this report. They consolidate related counterexamples; they are not 18 new plan packages. P1 means repair before relying on the affected execution, canonical-state or scientific-evaluation contract; P2 means a narrower qualification/availability defect. These review priorities do not replace the master plan's priorities.

| ID | Priority | Plan | Reproduced result |
|---|---|---|---|
| DV01 | P1 | F16–F18 | Applied START + lost ACK becomes CANCELLED on poll while still running; reservation/watchdog/tracking removed. |
| DV02 | P1 | F16–F18 | Two OS workers, same device/zone, both EXECUTING and two physical START effects after both sampled idle. |
| DV03 | P1 | F17/F18 | Contradictory RUNNING word plus stopped flags is UNKNOWN on query but successful STOP/EMERGENCY_STOP. |
| DV04 | P1 | F17/F19 | Late START fencing and dispatcher fault-stop paths clear a retained actuator ERROR to ONLINE. |
| DV05 | P2 | F39 | Crashed recovery owner leaves an ownerless `.recovery` mutex; repeated later acquisitions time out. |
| DV06 | P1 | F39 | Old double rollback deletes a newer accepted nonce; another process accepts it again. Strict rollback I/O failure is also hidden. |
| DV07 | P1 | F08/F09 | Same-scope losing CAS hydrates without winner's soil observations; continuation diverges from cold recovery. |
| DV08 | P1 | F09 | Cross-scope losing CAS installs A's state/event into B's full RAM scope and next B checkpoint. |
| DV09 | P1 | F08/F09 | A→B→A recovery loses A's predecessor chain because durable head identity is narrower than RAM identity. |
| DV10 | P1 | F08/F09 | Earlier correction drops lookup of already registered later weather; replay imputes zero rain instead of 20 mm. |
| DV11 | P1 | F23 | Interrupted exclusive write leaves partial canonical filename, hidden as a miss, and poisons valid retry. |
| DV12 | P1 | F23 | Mutation during storage gives disk p50=1 but returned/cache p50=99; warm evaluation reports RMSE 0. |
| DV13 | P1 | F24 | NaN observation or mean receives CRPS 0; missing scores serialize as nonstandard NaN. |
| DV14 | P2 | F23 | Reordered evidence gives same evaluation ID/different payload; rejected write has already appended to cache. |
| DV15 | P1 | F15 | Missing/NaN recommendation becomes positive 5 mm and CONFIRMED; invalid bounds can lose their invalidity. |
| DV16 | P1 | F15 | Real modifier lowers 21 mm to 14.7 below original min20; scheduler and final gate still CONFIRM. |
| DV17 | P2 | F15 | Expired/out-of-horizon/malformed dates remain CONFIRMED; a recorded format error does not demote the slot. |
| DV18 | P2 | T11/F38 | Actual `failed_spatial_timeout` producer is written and read as a cache hit. All restrictive flags remain unchanged. |

### DV01–DV02: operation ownership needs a durable resource claim

`dispatcher.py:865–891` equates absence of acknowledged `actual_start` and absence of a **pending** command with never having started. The branch ignores the same event's **active** command and the live EXECUTING query. In the actual base actuator, applying START then losing its ACK can legitimately leave an active command with no acknowledged start timestamp.

The coordinating probe obtains STOP_REQUESTED, active command `ACK_LOST`, and an 8 mm reservation before polling. After one poll it obtains CANCELLED, 0 mm stopped receipt, zero reservation, no dispatcher/watchdog entries, but the controller still runs `ACK_LOST` and its effect log contains START with no STOP. Fix the distinction between positively refused-before-send and possibly applied-without-ACK; only the former can be finalized without physical reconciliation. Preserve conservative exposure until a qualified stop/delivery outcome exists.

For device admission, `dispatcher.py:409–425` stores an owner token under the event ID, while `safety.py:468–805` reserves by event/plot budget. This is not exclusive ownership of a device/zone across distinct event IDs. The preflight query at `504–511` is outside an atomic resource admission protocol. Two independent processes are paused after truthful idle snapshots; both then send START, both return EXECUTING, and both have durable EXECUTING claims. Both processes exit 0. This demonstrates duplicate command effects, not a measured doubling of field dose. UNKNOWN and raised preflight-query controls also proceed to START; those controls expose why a live-query-only design cannot supply exclusivity.

Use an atomic, shared resource claim with a declared controller/zone concurrency policy and a generation/fencing token, joined to event payload identity and exposure. A genuine controller may implement idempotency or exclusivity too; no such protection was verified here. Preserve the now-passing refused-NEW/known-OLD control while fixing the lost-ACK case.

Sources: [irrigation_runtime/dispatcher.py#L409-L425](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/irrigation_runtime/dispatcher.py#L409-L425), [irrigation_runtime/dispatcher.py#L830-L901](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/irrigation_runtime/dispatcher.py#L830-L901), [irrigation_runtime/actuator.py#L575-L650](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/irrigation_runtime/actuator.py#L575-L650), [irrigation_runtime/safety.py#L468-L805](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/irrigation_runtime/safety.py#L468-L805). R3: AB-EXE-002/003/004, AB-ARC-008.

### DV03–DV04: one controller-state contract through every STOP path

The exact local MQTT callback fixture `{status: RUNNING, running: false, stopped: true}` produces UNKNOWN from query but success/ONLINE from both normal STOP and emergency STOP. A NaN stopped flag is also interpreted as true rather than invalid. The issue is inconsistent and permissive decoding of untrusted controller data; these are controlled callback payloads, not observations from a deployed broker.

The direct-stop fault-latch repair passes. A separate late-START fence returns PREEMPTED_BY_STOP yet leaves ONLINE after a fault-bearing stop. An actual dispatcher composition goes EXECUTING→fault query→fault-bearing stopped ACK, ends with a FAILED event and stopped receipt, but actuator ONLINE. Stopped motion and cleared fault are separate facts. Keep the latched fault until an explicit qualified reset; use the same strict finite/typed decoder for heartbeat, query, START, STOP and fence acknowledgments. The protocol appendix identifies exact lines and secondary callback/cancellation races separately.

Sources: [irrigation_runtime/drivers/mqtt_driver.py#L388-L419](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L388-L419), [irrigation_runtime/drivers/mqtt_driver.py#L618-L666](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L618-L666), [irrigation_runtime/actuator.py#L543-L548](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/irrigation_runtime/actuator.py#L543-L548), [irrigation_runtime/dispatcher.py#L1134-L1137](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/irrigation_runtime/dispatcher.py#L1134-L1137). R3: AB-EXE-002/003/004.

### DV05–DV06: lock serialization is not crash recovery or transaction ownership

The new recovery mutex prevents the original two-recoverer overlap. A child exiting inside actual stale-lock recovery leaves an empty `.lock.recovery`. Aging it an hour does not make it recoverable: two future acquisitions both time out. Each call is bounded; the defect is persistent availability lockout, not one infinitely blocked call.

More seriously, the inactive-device branch releases a nonce then raises; its surrounding exception handler releases again. A three-process schedule lets B successfully accept the nonce between A's releases. A's second cleanup deletes B's accepted nonce, allowing C to accept it again. All three children exit 0. Cleanup by nonce value lacks transaction ownership/generation. Under strict mode, injecting an error on rollback replacement also returns no readings while leaving a durable nonce and no raw evidence; a repaired retry remains blocked.

Make cleanup single, owned and state-aware. Separate reserved, evidence-committed, accepted and rejected receipts; do not use one membership bit for every phase. Use a crash-recoverable lock primitive/protocol rather than indefinitely nesting ownerless lock files. Preserve the successful same/unique-nonce process controls and avoid erasing committed evidence to make retries work. Raw/normalized persistence and scope limits predating this commit are qualified separately in the appendix.

Sources: [sensor_runtime/security.py#L128-L178](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/sensor_runtime/security.py#L128-L178), [sensor_runtime/security.py#L295-L322](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/sensor_runtime/security.py#L295-L322), [sensor_runtime/ingestion.py#L89-L103](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/sensor_runtime/ingestion.py#L89-L103), [sensor_runtime/ingestion.py#L190-L239](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/sensor_runtime/ingestion.py#L190-L239). R3: AB-DAT-001/003/011/013, AB-ARC-008/009.

### DV07–DV10: every hydraulic recovery path must reconstruct the same scoped evidence

The improved ordinary cold path must become the common recovery implementation, rather than a separate implementation beside rollback. In two OS processes for the same full scope, A commits three soil readings and B loses the actual CAS. B's rollback creates history with no soil observations and an empty soil registry. B's next day returns **109.43 mm**; ordinary cold recovery from the exact winning checkpoint returns **201.15 mm**. The fixture only gates save ordering; it does not delete the registry manually.

For different cycle/geometry scopes, a controlled A-wins/B-loses schedule installs A's **468.76 mm** state and `A_water` event in B's five-field RAM scope. B's next publication is **458.31 mm**, versus **448.75 mm** for fresh B, and contains A's event. A one-plot durable head does not become correctly scoped simply because the receiving RAM dictionary has a five-field key.

An A→B→A sequence independently gives A continuation **439.74 mm**, versus **448.11 mm** for the A-only control. A's old checkpoint bytes still exist; the active head/index no longer retrieves its predecessor chain correctly. In the historical-correction case, the Jan3 20 mm rainfall remains in an older immutable file but disappears from active replay history after a Jan2 correction. Both warm and cold Jan4 continuation impute Jan3 zero rain and give **105.53 mm**, versus **122.75 mm** when the already registered original weather is supplied again. This is loss of evidence lookup/replay, not deletion of immutable files.

Define one scientific scope and durable head/index identity across load, CAS, rollback, legacy migration and historical lookup. Reject or isolate a winner from another scope. Rehydrate every typed evidence channel through one shared function. A correction should invalidate descendant calculations while retaining their registered inputs for qualified recomputation. Preserve cutoff/version/tombstone semantics. The appendix separately qualifies unversioned withdrawal reinstatement and an explicit-prior exact-retry conflict; neither is silently treated as proof about an undefined policy.

Sources: [layer3_decision/runner.py#L1275-L1411](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L1275-L1411), [layer3_decision/runner.py#L1441-L1525](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L1441-L1525), [layer3_decision/runner.py#L2225-L2255](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L2225-L2255), [layer3_decision/runner.py#L2599-L2642](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L2599-L2642), [world_model/canonical_worldline.py#L133-L154](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/world_model/canonical_worldline.py#L133-L154). R3: AB-DAT-003/012/013, AB-ARC-008, AB-AGR-006/007.

### DV11–DV14: publish one immutable forecast snapshot and qualified evaluations

The exclusive archive branch creates the **final** filename before JSON dumping, flushing and fsync. Exclusive creation gives one winner, not atomic visibility of a complete record. A child writing a valid forecast exits after flushing a prefix; cold read returns None and a valid retry raises corruption. A normal serialization failure and a read-during-write schedule demonstrate the same visibility boundary. This is process interruption/failure isolation, not a power-loss durability certification.

Write validated bytes to an unpublished complete file, then conditionally publish without replacing another identity. Keep corruption distinguishable from absence and keep the verified single-winner property. Disk, cache and return must use **one detached validated snapshot**: today the disk payload is captured before a mutation but cache/return are copied afterward. The recorded schedule yields disk p50=1, cache p50=99 and warm RMSE0, while the quantiles remain ordered.

Missing median no longer causes fake point accuracy; that original fix is retained. However, missing RMSE/sharpness becomes NaN in evaluation JSON, and unavailable coverage becomes false. NaN observed value or Gaussian mean still receives CRPS0 through the clamp. Validate typed finite targets/means, monotone distributions, horizon and target evidence/support/time; represent unavailable components explicitly without a numeric skill contribution. Gaussian ±1.645σ is approximately P5/P95, not P10/P90; the retained bound names/convention still need correction or explicit metadata.

Evidence-order retry also needs one canonical representation. IDs sort evidence IDs, stored payload preserves caller order, and memory is appended before the exclusive evaluation write. Reordering A/B creates the same ID with a different payload, rejects on disk, but leaves two memory entries versus one durable entry. Canonicalize identity and payload consistently and publish memory only after durable success. The original target/area/depth completion projection passes; narrower stale duration/flow and canonical-null support seams are documented with their fixture limits in the ledger appendix.

Sources: [world_model/forecast_archive.py#L28-L65](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/world_model/forecast_archive.py#L28-L65), [world_model/forecast_archive.py#L433-L462](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/world_model/forecast_archive.py#L433-L462), [world_model/forecast_archive.py#L549-L634](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/world_model/forecast_archive.py#L549-L634). R3: F23 AB-DAT-011, AB-ARC-007/008, AB-ASM-014; F24 AB-ML-005/010, AB-ASM-016; missingness/support AB-DAT-005/007.

### DV15–DV17: validate original feasibility before and after every modifier

Leaching maps an invalid recommendation to zero, then applies a minimum floor. Missing/NaN recommendation with min5/max21 becomes **5 mm and CONFIRMED**, with an empty final invariant receipt. Invalid caps can become zero and confirm; the same NaN cap outside that modifier is correctly blocked. An original contradictory min25/max21 is rewritten to21/21 rather than rejected. Valid zero is a separate passing control.

A fully finite counterexample does not depend on malformed input: the actual environmental modifier turns rate21/min20/max21 into **14.7 mm**, preserving min20. Scheduler and final invariants still confirm it. Validate the original immutable envelope, propagate invalid/unavailable reasons, and run a final feasibility check after every modifier against both lower and upper bounds and aggregate constraints. Do not manufacture scientific input by sanitation.

Simple date sorting is repaired. Temporal qualification is not: malformed dates retain CONFIRMED despite a format error; 2020/2030 rows fit a documented seven-day horizon by row count; and supplied expired validity metadata is ignored. The dictionary boundary has no enforced typed expiry contract, so that last result identifies a missing contract rather than bypass of an established one. Parse actual instants, define issuance/validity/cutoff fields, qualify duplicates, enforce the planning interval, and demote invalid slots. A raw full-L8 numeric-string temperature call also raises before the new scheduler parser; normalize or reject weather once before all consumers. These probes exercise raw shadow recommendations, not top-level execution authorization.

Sources: [layer8_prescriptive/engines/salinity_leaching.py#L83-L145](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer8_prescriptive/engines/salinity_leaching.py#L83-L145), [layer8_prescriptive/scheduler.py#L116-L173](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer8_prescriptive/scheduler.py#L116-L173), [layer8_prescriptive/invariants.py#L56-L114](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer8_prescriptive/invariants.py#L56-L114), [layer8_prescriptive/engines/environmental_risk.py#L120-L150](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer8_prescriptive/engines/environmental_risk.py#L120-L150), [layer8_prescriptive/runner.py#L294-L372](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer8_prescriptive/runner.py#L294-L372). R3: AB-DEC-003, AB-ECO-003, AB-EXE-001.

### DV18: reader/writer parity must cover actual producer vocabulary

The actual engine timeout constructor plus the exact runner serializer emits top-level status `failed_spatial_timeout`, with diagnostic timeout reason/code but no top-level reason/result_status. Both new cache predicates miss this form; the writer returns true and the reader returns a hit. This is an eligibility-policy gap in the claimed failed-record exclusion. All nine checked authority/availability fields and diagnostics remain restrictive and unchanged: **the cache hit does not demonstrate promotion to production usability, state update, training or execution permission**. The six older rejection fixtures are verified repaired.

Share a typed eligibility predicate with producers and consumers, account for diagnostic-only persistence explicitly, and preserve restrictive flags on every cache path. The appendix's progressive-helper case is a narrower helper result; reachability of its late catch is not established.

Sources: [layer05_asmae/cache.py#L650-L661](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer05_asmae/cache.py#L650-L661), [layer05_asmae/cache.py#L732-L746](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer05_asmae/cache.py#L732-L746), [layer05_asmae/engine.py#L585-L696](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer05_asmae/engine.py#L585-L696), [layer05_asmae/runner.py#L1114-L1196](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer05_asmae/runner.py#L1114-L1196). Canonical packages: T11 stage11 and F38 stage10; R3 AB-ARC-006/007/008/012 and AB-DAT-001/002, with AB-ARC-005/AB-ASM-016 relevant to the preserved authority limits. This does not close F25 backend identity or F36 scientific qualification.

## Implementation order within the existing plan

| Workstream | Concrete next implementation | Required closure evidence |
|---|---|---|
| A: F16–F19, stage6 | Separate refused-before-send from uncertain applied effects; atomic device resource lease/fence; consistent STOP decoding and persistent fault latch. | Lost ACK remains owned until qualified stop; two real workers cannot both START an exclusive resource; stale event cannot stop a qualified foreign owner; device hazards still stop the actual owner; failed/contradictory ACK retains monitoring/exposure. |
| B: F39, stage3 | Owned admission/rollback receipts and crash-recoverable locking; resumable evidence publication. | Same/unique-process and thread controls retained; recovery-owner crash recoverable; old rollback cannot erase newer commit; strict rollback error explicit and recoverable; no accepted evidence lost. |
| C: F08/F09, stage3 | Common typed hydration for cold/rollback/replay; fully scoped durable head/index; descendant recomputation retains registered inputs. | Same-scope CAS loser equals cold winner; cross-scope winner cannot enter another scope; A→B→A equals isolated controls; historical correction reuses registered future weather; exact retries preserve identity. |
| D: F23/F24, stage8 | One frozen forecast snapshot; complete conditional publication; canonical evaluation identity; finite/qualified score components and JSON-safe unavailable results. | Crash at each write boundary leaves absence or complete record and supports retry; warm/disk/return byte identity under mutation; no failed memory append; invalid mean/target cannot earn CRPS0; declared quantile coverage verified. |
| E: F15, stage5 | Validate immutable original envelope; normalize weather before all modifiers; final bounds/resources/calendar feasibility. | Unknown dose never becomes positive confirmed dose; every modifier respects min/max; invalidity survives to final receipt; malformed/expired/out-of-window slots cannot confirm; valid zero and safe units still work. |
| F: T11/F38, stages11/10 | Shared typed producer/cache eligibility, explicitly separating failed reuse from retained diagnostics. | Actual timeout/fallback producers have the intended miss/diagnostic behavior; all restrictive flags and integrity checks preserved. |

These streams can run in parallel where their declared prerequisites and code ownership permit. They are bounded repairs within the existing plan; the plan's original **2,564–4,540 hour** estimate is not a new remaining-effort estimate. Do not close a package from a single passing local fixture.

Proceed now with these corrective implementations and other independently eligible plan slices. Continue Omega/World Model exploratory work using explicitly eligible data and objectives. Defer claims that require the affected operational/scientific contracts until their closure evidence exists. Field commissioning remains separate; no result here validates a real controller installation.

## Reproduction and coverage

The companion bundle contains authored probes, recorded results, exact source-object layout, package mappings, source receipts, this report and specialist appendices. It excludes repository test/audit files, production source copies and generated runtime stores. `prepare_and_run.py` can reconstruct required source bytes from a local repository containing the pinned Git objects into a separate workspace without checkout changes or network access. See its README for dependencies and per-lane commands.

All **11 probe scripts** were also replayed successfully from a separate reconstructed layout containing **1,426 verified source copies / 536 unique blobs**. Those counts include repeated dependency layouts. The Git-object materializer was compiled and its layout checked; it was not executed against a separate full Git checkout here. A missing normative excerpt in the initial portable layout was added before the protocol-matrix replay passed; the validation receipt records this packaging correction. GitHub main was rechecked before delivery and still points to the reviewed SHA.

Probe exit0 means the recorded observations/assertions were reproduced; it is **not a claim that the production contract passed**. Controlled fault schedules, schema-level fragments, raw shadow paths and policy limits are stated in each appendix. No combined percentage or artificial whole-project pass score is assigned.

The six specialist appendices follow. Their detailed IDs and priorities are local to their lanes; DV01–DV18 above are the consolidated register for this report.


---

# Specialist appendix: Trajectory and hydraulic recovery

# Actual 1ee8c4e trajectory review

Pinned source `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`, parent `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`. All 13 assigned master-plan cards have current-source coverage; the deeper delta focuses on F08/F09 at stage 3. The original cold-observation, valid-date cancellation and immediate scope-switch defects are corrected in the sampled production paths. Full F08/F09 acceptance remains open because winner rollback and scoped predecessor recovery still violate the same data guarantees.

## Verified corrections and controls

- **Original exact cold-correction case now passes:** same 120 mm initial prior, identical hydraulic memory, Jan 2 readings [.4,.4,.4] registered at 12:00 UTC, Jan 3 issuance target, Jan 2 rain corrected 0→1 mm. Warm and cold both accept 3 readings, integrate Jan 2 and Jan 3 once, and return **201.13 mm**. Ordinary recovery now serializes/hydrates SoilObservationVector.
- **Cold cancellation now passes:** valid ISO Jan 2 dates, applied version 1→cancelled version 2; delivered irrigation is zero and cancellation persists in the new checkpoint.
- **Immediate A→B switch now passes:** new full RAM scope and ordinary hydration guard produce fresh-B-equivalent **448.75 mm**, without A events.
- **Retained controls:** identical dated-canopy daily/sparse execution agrees; unchanged warm/cold replay and idempotence pass. Non-noon Jan 4 continuation runs only Jan 4 at **105 mm**; exact cold Jan 2 query matches **114.13 mm** without moving the Jan 3 head. Basic two-process checkpoint CAS admits one successor and rejects one competitor.
- **Withdrawal:** warm/cold removal agrees at **109.43 mm** and the tombstone survives an omitted next-day request after restart. Current-interval K/epoch replacement changes identity and matches a fresh replacement control; its identical retry fails as detailed below.

The inherited N residual fix remains **86.67 kg/ha**, zero-deficit **0**. These are bounded controls, not whole-package closure. Ordinary cold hydration and winner rollback are distinct production paths.

## Confirmed remaining defects

### F09-CAS-SCOPE — P0: CAS loser rollback hydrates another cycle/geometry into the full RAM scope

Packages F09; stage 3; R3 AB-DAT-013, AB-ARC-008, AB-DAT-012.

Two different full scopes read the same empty durable head. A commits with 20 mm applied irrigation; B loses the real CAS. The rollback copies A's 468.76 mm soil, A_water event and Jan 2 history into B's five-field scope without checking cycle/geometry. B's next request publishes 458.31 mm versus a fresh B control 448.75 mm, with A_water in the B checkpoint. The normal first-hydration guard passes its direct B-after-A control; rollback bypasses that guard.

Raw receipt: `deep-results.json:cross_scope_CAS_rollback`.

- [services/agribrain/layer3_decision/runner.py:1441–1518](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L1441-L1518) — blob `366d09057c69e217a49a224891c89944719c1835`.
- [services/agribrain/layer3_decision/runner.py:1229–1237](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L1229-L1237) — blob `366d09057c69e217a49a224891c89944719c1835`.

### F09-CAS-OBS — P0: CAS loser recovery still drops winner observations in a separate process

Packages F09; stage 3; R3 AB-DAT-012, AB-ARC-008, AB-AGR-006.

Two processes share exactly the same full scope. A commits Jan 2 with three .4 readings. B loses actual CAS, then production rollback stores soil_observations=None and leaves its soil-observation registry empty. B's next Jan 3 request replays Jan 2 with count 0 and returns 109.43 mm. Normal cold hydration from an exact copy of A's winner checkpoint returns 201.15 mm. Both processes exit 0. The ordinary cold-correction fix passes, but the winner-recovery branch still uses the old partial history reconstruction.

Raw receipt: `deep-results.json:same_scope_process_CAS_observation_recovery`.

- [services/agribrain/layer3_decision/runner.py:1491–1525](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L1491-L1525) — blob `366d09057c69e217a49a224891c89944719c1835`.
- [services/agribrain/layer3_decision/runner.py:1368–1411](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L1368-L1411) — blob `366d09057c69e217a49a224891c89944719c1835`.

### F09-SCOPE-REVISIT — P1: A→B→A cannot restore A's compatible predecessor chain

Packages F09; stage 3; R3 AB-DAT-013, AB-DAT-012, AB-AGR-006.

A has a Jan 2 committed state after 20 mm irrigation. B commits Jan 3 in another cycle/geometry. Reopening A for Jan 4 yields 439.74 mm warm or cold versus 448.11 mm for an A-only checkpoint control. A's Jan 2 history disappears from its active checkpoint. The original A checkpoint bytes remain intact, so this is compatible-head discovery/replay failure, not deletion. Five-field RAM keys and first-hydration guards are improvements, but the durable head is still tenant/namespace/plot only.

Raw receipt: `deep-results.json:scope_A_B_A`.

- [services/agribrain/layer3_decision/runner.py:1275–1326](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L1275-L1326) — blob `366d09057c69e217a49a224891c89944719c1835`.
- [services/agribrain/world_model/canonical_worldline.py:133–154](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/world_model/canonical_worldline.py#L133-L154) — blob `aa11d851b502edb4db30e617209347ca17f92635`.
- [services/agribrain/world_model/canonical_worldline.py:249–273](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/world_model/canonical_worldline.py#L249-L273) — blob `aa11d851b502edb4db30e617209347ca17f92635`.

### F09-RETAIN-FORCING — P1: Earlier correction loses later registered weather from the active replay view

Packages F08, F09; stage 3; R3 AB-DAT-003, AB-DAT-012, AB-AGR-007.

Jan 3 20 mm rain was previously integrated and committed. Correcting Jan 2 with a Jan 2 target creates a head whose history contains only Jan 2. Next Jan 4 warm/cold replay imputes Jan 3 zero rain and returns 105.53 mm; re-supplying the already registered Jan 3 weather gives 122.75 mm. Original checkpoint bytes are preserved, but their eligible forcing is not retrieved by the new head. The zero is flagged as imputation; the defect is loss of previously admitted forcing during corrected replay, not an assertion that the imputation is labelled observed.

Raw receipt: `deep-results.json:retroactive_correction_forcing_retention`.

- [services/agribrain/layer3_decision/runner.py:2225–2255](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L2225-L2255) — blob `366d09057c69e217a49a224891c89944719c1835`.
- [services/agribrain/layer3_decision/runner.py:2599–2642](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L2599-L2642) — blob `366d09057c69e217a49a224891c89944719c1835`.
- [services/agribrain/layer3_decision/runner.py:1878–1950](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L1878-L1950) — blob `366d09057c69e217a49a224891c89944719c1835`.

### F08-PARAM-RETRY — P1: Identical explicit parameter-replacement retry conflicts with its own immutable checkpoint

Packages F08; stage 3; R3 AB-DAT-011, AB-DAT-012.

Replacing conductivity [2,2,2] by [4,4,4] and epoch v1 by v2 for the same declared current-interval prior changes checkpoint identity and matches the fresh replacement control. Repeating the identical request raises ConcurrencyConflictError on that same checkpoint ID. Normalized production payload capture shows only history evidence_hash/interval_hash differ (ae7588cdf7b7a5f001189e02 versus ec7f7a44f024400040422748); the head remains intact. This is an idempotence failure for a current-interval explicit replacement, not a claimed effective-dated historical parameter correction.

Raw receipt: `deep-results.json:current_interval_parameter_identity`.

- [services/agribrain/layer3_decision/runner.py:2373–2395](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L2373-L2395) — blob `366d09057c69e217a49a224891c89944719c1835`.
- [services/agribrain/layer3_decision/runner.py:2599–2627](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer3_decision/runner.py#L2599-L2627) — blob `366d09057c69e217a49a224891c89944719c1835`.
- [services/agribrain/world_model/canonical_worldline.py:282–315](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/world_model/canonical_worldline.py#L282-L315) — blob `aa11d851b502edb4db30e617209347ca17f92635`.

## Controlled interleavings and evidence limits

The cross-scope concurrency probe uses two threads with independent five-field scopes. Both reach the real save after reading an empty shared durable head; the harness gates B's save until A's full production request returns. A commits and B receives the real ConcurrencyConflictError. Production rollback then performs the observed cross-scope mutation; the next B request runs with the ordinary adapter. The harness does not write a registry or substitute a state.

The same-scope evidence-recovery probe uses **separate processes** sharing exactly the same tenant/namespace/plot/cycle/geometry and local checkpoint store. A commits the three readings; B is ordered to attempt its real CAS afterward and loses. B then calls the ordinary production entry point again. An exact copy of A's committed store is used for the normal-cold-hydration positive control. Both processes exit 0. This verifies a local multi-worker recovery defect; it does not certify arbitrary multi-host filesystem leases.

Original checkpoint files are hashed before retrospective correction and scope switching and remain byte-identical afterward. The reported losses concern compatible-head/evidence retrieval, not deletion or destruction of prior records. The historical rain zero remains explicitly flagged as imputed; the prior admitted 20 mm record is what became unreachable by active replay.

Parameter retry capture applies the production _public normalization before comparing attempted and committed payloads. The immutable-save exception is a production outcome, not an uncaught harness failure. Only evidence_hash/interval_hash differ; the scientific state agrees with the fresh control and the committed head remains intact. The F08 evaporation/wetted-fraction digest collision also remains reproduced by an AST-extracted exact production function, with changed-conductivity positive control.

The optional withdrawal-reappearance observation is **not a blocker**: explicitly resending an identical unversioned pre-withdrawal vector removes the tombstone and yields 201.15 mm. The current contract cannot distinguish stale retry from intentional re-admission. Define revision/reinstatement semantics before claiming that guarantee.

## Broader assigned-plan coverage

Other previously reported lane issues remain in current focused receipts: temporal NaN/infinity admission, dictionary role/zero-reliability promotion, weather availability loss, partial historical canopy coordinate fallback, missing depth/covariance integration, L3→L4 generic retention/storage substitution, unverified delivery states entering water exposure, and conservative N/growth coupling gaps. T01 remains a capability target. Their exact mappings and current source references are in coverage.json.

| Package | Stage | Current assessment |
|---|---:|---|
| F01 | 1 | partial boundary fixed; acceptance open |
| F02 | 1 | partial time filter fixed; acceptance open |
| F03 | 2 | sampled boundary pass; full acceptance unverified |
| F04 | 2 | original validation cases fixed; serialization boundary open |
| F05 | 4 | open depth and covariance integration |
| F06 | 3 | endpoint substitution fixed; forcing qualification open |
| F07 | 3 | memory and complete fallback fixed; coordinate fallback open |
| F08 | 3 | bounded identity controls pass; full content parameter retry and retained forcing open |
| F09 | 3 | original cold correction cancellation direct scope fixed; CAS recovery scoped heads and replay retention open |
| F10 | 4 | open schema boundary defect |
| F11 | 4 | residual formula fixed; conservative pool and actual application integration open |
| F34 | 7 | open exposure lifecycle and accounting |
| T01 | 12 | capability target not established |

## Acceptance and reproduction

F09 must use one qualified full-scope recovery path for initial hydration, historical queries and CAS winners; its durable compatible-head identity must include cycle/geometry and preserve access to admitted forcing after earlier corrections. F08 must align immutable identity with canonical payload and make explicit parameter retries idempotent. Re-run A→B→A, same/cross-scope loser recovery, retained-weather corrections and the original positive controls together. These map to AB-DAT-003/011/012/013, AB-ARC-008 and AB-AGR-006/007. The master-plan R1 trajectory gate is still open.

All 23 assigned targets and four reused dependencies are blob-verified against the current tree. Fourteen focused groups plus the precise correction/non-noon gates and six deeper probe cases execute actual production symbols. Digest and L4 fragments remain explicitly bounded AST probes. No repository pytest/audit is used as implementation proof; no source/Git mutation or field/controller/vendor call occurred. Prior reports/sources remain unchanged.

Run from the workspace root: `PYTHONDONTWRITEBYTECODE=1 python repair-1ee8c4e-review/trajectory/probe.py`, `claim_probe.py`, `gate_probe.py new`, and `deep_probe.py` at the same path. Numerical traces, controlled-process results, manifests and per-package acceptance records accompany this report.



---

# Specialist appendix: Nonce ownership and ingestion

# F39 actual repair review — 1ee8c4e

**The intended normal-path repairs are verified, but F39 is not complete.** Actual commit `1ee8c4e777afa85e2ff7230d146f4ad17eff309f` serializes the previously reproduced stale-recoverer schedule and successfully rolls back the earlier registry/calibration/pre-write failures. Three concrete remaining failures concern recovery ownership and transaction cleanup: an orphan recovery mutex blocks future work; duplicate cleanup removes a newer accepted nonce; rollback I/O errors are swallowed even in strict mode.

## Source, execution and scope

```bash
PYTHONDONTWRITEBYTECODE=1 python /workspace/scratch/de6bc2428cec/repair-1ee8c4e-review/ownership/actual_nonce_probes.py
```

Final run exited 0, all assertions passed. `actual-nonce-results.json` and `probe-run-output.json` contain the complete results. Ten imported source blobs were matched to the exact new Git tree, whose commit is asserted by the harness. Key blobs:

| Production file | Git blob |
|---|---|
| `sensor_runtime/security.py` | `0b5f1574ed565ead319c1155fcc6c34cc9394937` |
| `sensor_runtime/ingestion.py` | `55ae72248c953bb25d4a14895ac215be66de31fd` |
| `sensor_runtime/storage.py` | `23de3ea521c183e8e791014f0bd3f1cde8ccfb20` (unchanged) |

Paths below are relative to `repair-1ee8c4e-review/source/services/agribrain`. Tests use real local OS processes/shared files, controlled scheduling barriers, fixture registry/calibration snapshots and explicitly identified fault injection. Lock decisions and ingestion consumers are actual production code, not modeled substitutes. No production/Git edits, repository test suites/audit assertions, hardware or vendor services were used.

This lane covers F39 and its F01/F09 boundary dependencies, stage 3 in the supplied execution addendum. Full F39 also includes durable immutable telemetry, scoped identities and bounded cache/lock/rate retention. Those pre-existing requirements are distinguished from newly exposed repair failures below.

## Intended changes that now pass

| Control | Observed result |
|---|---|
| Two OS processes, same nonce through actual ingestion | One accepted reading, one rejected duplicate |
| Two OS processes, unique A/B | Both accepted; both registrations persisted |
| Fresh process replays after those cases | Rejected; all six ingestion/restart children exited 0 |
| Ten concurrent reservation threads | One winner, nine blocked |
| Prior stale-evictor scheduling boundary | B observed recovery mutex busy while A held it; both later entered serially; maximum critical-section owners **1**, both exited 0 |
| Registry unavailable, then restored | First call left no nonce/seen/raw record; retry accepted one reading |
| Calibration unavailable, then restored | Same successful cleanup/retry |
| Raw writer failure before any side effect, then restored | Same successful cleanup/retry |
| Read-only check | `reserve=False` consumed no nonce |

The previous two-recoverer critical-section overlap and pre-validation nonce consumption are not carried forward as unchanged defects. The passing controls verify the new recovery mutex and rollback on these schedules; they do not establish crash-safe recovery or transaction ownership.

## N1 — a crash leaves an unrecoverable recovery mutex

`_nonce_store_lock` creates `<store>.lock.recovery` with `O_CREAT|O_EXCL` to serialize stale recovery. It writes no PID/token to that file and removes it only in its `finally` block. If the recovery process dies, subsequent recoverers encounter the existing recovery file, set `rec_fd=None`, and retry until the ordinary acquisition timeout. There is no recovery protocol for the recovery mutex itself.

The probe used an actual child acquiring the real recovery mutex for an already dead primary-lock owner. The child then exited abruptly inside the real dead-PID check. This is an explicit crash injection, bypassing finally as a crashed process would. The resulting primary lock and empty `.recovery` file persisted. After aging the recovery file one hour, two later actual acquisitions both raised TimeoutError and left both files in place. Test acquisitions use a short timeout; production defaults to ten seconds per attempt. The observed failure is **repeated acquisition timeout/availability lockout**, not a claim that one function call waits forever.

References: `security.py:138–146` creates/contends on the recovery file; `169–178` only unlinks it during normal unwinding; `135–136` bounds each failed acquisition. F39; AB-ARC-008/012 and AB-DAT-003/011 reliability obligations. Introduce a recovery mechanism whose own ownership and crash cleanup can be established safely; do not merely add another indefinitely orphanable guard. Retain the passing serialization control and test nested recovery crashes and interrupted owner-token publication.

## N2 — double release in an actual caller erases a newer accepted nonce

The inactive-device branch explicitly releases its nonce at `ingestion.py:99`, then raises. The surrounding exception handler calls `release_nonce` again at `192–194`. `release_nonce` deletes by nonce value alone, without reservation owner/generation or commit state.

Controlled actual-consumer schedule:

1. Old worker A reads an inactive registration snapshot, reserves nonce ABA, releases it once and pauses before raising.
2. Worker B, with an active registration snapshot, successfully ingests ABA and persists its nonce.
3. A resumes, raises the expected ValueError, and its exception handler performs the second release. B's already accepted nonce disappears.
4. Fresh worker C ingests ABA successfully again.

Three OS processes exited 0. B and C each returned one accepted reading for the same nonce; the store was `[ABA]` after B, empty after A's second cleanup, then accepted again by C. The test supplies old/new registry snapshots, as can occur across a registration change or workers. It does not assume inactive-device rejection must be transient or permanent: **an old cleanup must not delete a newer successful admission under either policy**.

References: `ingestion.py:98–103,190–194`; `security.py:295–322`, especially value-only deletion at `307–317`. F39; AB-ARC-008, AB-DAT-003/011/013. Eliminate duplicate rollback and bind cleanup to its own reserved transaction. Verify that cleanup cannot remove a subsequently reserved or committed receipt; a mutex serializes operations but does not supply transaction ownership.

## N3 — rollback persistence failure is hidden, leaving the original retry gap

`release_nonce` catches file-read errors and returns; it also catches replacement failures and continues. These paths do not honor the strict-mode failure behavior used by the reservation writer.

With `AGRIWISE_STRICT_SECURITY=true`, the probe allowed reservation to persist, returned registry unavailable, and injected an OSError specifically on the rollback `os.replace`. Ingestion returned zero readings **without propagating a rollback error**. The durable nonce remained, no raw evidence existed, and after restoring the writer and registry the retry again returned zero. Local seen state had been cleared, so the remaining durable nonce caused rejection.

References: `security.py:300–305,307–322`; caller `ingestion.py:89–92`. F39; AB-DAT-001/003/011, AB-ARC-008/009. An unsuccessful rollback needs an explicit failed/pending receipt and recovery path, rather than silent success. This is controlled I/O fault injection at an actual writer boundary, not a claim that a real storage outage was contacted.

## Additional transaction checks and their limits

- **Two-variable validation control:** a message with VWC plus temperature and an incompatible second calibration failed before raw storage. Its nonce/seen state was cleared, no partial normalized values were returned, and a corrected calibration fixture allowed a retry returning both readings. This is a positive whole-message validation result.
- **Post-side-effect raw-writer fault drill:** an injected wrapper called the actual raw writer and then raised. Rollback released the nonce, but the raw record remained. A retry failed on the production immutable-overwrite check and released the nonce again, leaving raw-without-successful-return. This exposes a transaction acceptance gap when a writer's effect precedes its error. The post-effect exception is injected; it is not asserted to occur spontaneously after today's plain dictionary assignment.
- **Metadata failure after the try block:** invalid RSSI raised during `float(rssi)` after raw storage. No readings returned; raw and nonce remained; a corrected retry returned zero. This accurately shows the current error boundary. Permanent rejection versus recoverable error policy for invalid transport metadata is unspecified; no claim is made that every invalid value must be retryable. The final disposition needs an explicit receipt.

References: `ingestion.py:137–163,190–194,196–239`; `storage.py:9–13`. These drills support a receipt/transaction design that distinguishes validation rejection, reserved work, raw commit, normalized publication and completed acceptance instead of using a set membership flag for all phases.

## Pre-existing full-F39 limits, separate from new remediation failures

The accepted two-variable call returns two readings but stores zero normalized records: the actual ingestion function does not call `store_normalized_reading`. A hypothetical normalized consumer was not invented to manufacture a failure. Separate callers outside the inspected path require their own trace.

Raw/normalized storage remains module memory (`storage.py:5–20`). Fresh process controls reject persisted nonce values but contain no raw evidence from the earlier accepting process. This persistence shortfall predates the current changes and remains a full-package requirement, not a new recovery-mutex regression.

The store still contains only global nonce strings. Two registered devices supplying the same device-local sequence ID return `[1,0]`. The permitted ID-uniqueness domain must be declared; this observation is not represented as an independently demonstrated foreign-tenant exploit. Scope, payload binding, transaction receipts, retention, cache budgets and geometry invalidation still require acceptance.

## R3 mapping and next acceptance

The supplied plan places F39 full acceptance after F01/F09 at stage 3. AB-ARC-008 requires incompatible concurrent-worker effects to be prevented; AB-DAT-001/003/011/013 require resolvable evidence, preserved history/identity and scoped data; AB-ARC-009 requires correctly bound calculation/response identity. AB-ARC-012 covers explainable failure/receipt behavior. A passing early nonce-admission slice does not close durable corpus and recovery criteria.

Priority acceptance:

1. Fix orphan recovery-mutex handling without reintroducing the stale-evictor race. Re-run same/unique process and ten-thread controls plus crash recovery.
2. Make nonce cleanup single, owned and state-aware; re-run the actual inactive-branch ABA schedule and concurrent completion/rollback schedules.
3. Report and recover failed rollback writes under strict and supported deployment modes.
4. Prove a durable, immutable, idempotently resumable raw/normalized/receipt transaction under failures before and after each effect. Retain accepted data; do not blindly erase evidence to make replay pass.
5. Declare scope/payload/uniqueness and rejection policies; verify replica topology and remaining bounded-retention criteria separately.

All central findings above are actual-source results on `1ee8c4e`, with explicit fault/scheduling qualifications. No model-only or source-unavailable conclusion is used for this commit.


---

# Specialist appendix: MQTT protocol and actuator faults

# Actual 1ee8c4e MQTT verification

**The patch repairs several previously reproduced failures. Stop contradiction handling and fault retention remain incomplete across callers.** This review executes exact commit `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`, parent `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`.

Five core production files independently match the new Git tree (`source-index.json`). The previous **71-row MQTT matrix plus stale-query case** was rerun unchanged in scope. Forty additional command/flag rows, targeted lifecycle/fence/dispatcher cases and helper controls are in `boundary_results.json`. No production edits, Git mutations, repository tests/audits, paho broker, vendor service or physical controller were used. Callback fixtures state their own simulated controller contract; they prove production-code behavior for those replies, not field interoperability or physical cessation. Paho is absent. The trace-controlled race below is a scheduling witness, not a live transport test.

## Verified repairs and positive controls

- Ordinary STOP rejects `running=true`/`stopped=false`; an explicit STOPPED reply succeeds. START/PULSE reject explicit stopped/not-running replies (`mqtt_driver.py:281–450`). The old ordinary-STOP/START counterexamples are therefore repaired.
- Query decoding rejects both-true flags and RUNNING-versus-stopped contradictions as UNKNOWN (`:456–514`). Numeric strings `"0"`/`"1"`, and trimmed false/true words, normalize consistently in the exercised controls. Fault code `"0"` is treated as no fault, while a nonzero numeric fault is recognized.
- A fault-bearing positive stopped reply preserves ERROR in direct emergency STOP and in `execute_with_safety(STOP_ZONE)`. The direct base stop clears the physically stopped command while retaining its fault; that is an appropriate separation of cessation and equipment health (`actuator.py:343–352`).
- Non-object JSON payloads now return without changing payload/heartbeat metadata. An unhashable request ID no longer raises or fulfills a Future, though its object still updates payload/heartbeat metadata (`mqtt_driver.py:246–266`).
- `_complete_future():86–103` wakes the owning loop safely in the normal and asyncio-debug thread controls. The done callback runs near receipt rather than waiting for the independent 40 ms wake. No prior thread-safety RuntimeError appears in those controls.
- All three ordinary cancellation controls remove pending ACKs. Query/send/emergency publish exceptions clean up. NaN, infinity, booleans, nonpositive values and bad-string timeout fixtures receive finite defaults; ordinary finite timeout controls complete. The matrix's deliberately shorter outer deadline can still cancel a default 0.1/5-second wait, but cleanup is now verified. These are not claims of production latency.
- A late unmatched ACK after cancellation does not change operational `_status`; the following unanswered query returns UNKNOWN. It does update heartbeat/payload metadata, so that metadata must not independently certify current physical state.

## Strongest remaining command and fault cases

**M1 — Query and STOP paths disagree about a contradictory reply.** For `{status: "RUNNING", running: false, stopped: true}`, the query decoder correctly returns UNKNOWN, but both normal STOP and emergency STOP return success and ONLINE. The two stop parsers do not apply the decoder's status-word contradiction rule (`mqtt_driver.py:388–419, 618–666`). This is an internal contract inconsistency under AB-EXE-002/003, independent of a particular vendor: the same production driver already recognizes RUNNING and stopped as contradictory when queried.

Normal STOP also accepts bare OK/ACK with no physical flags; emergency STOP rejects the bare OK control. START still accepts bare OK and becomes EXECUTING. Whether a vendor's OK response certifies physical execution must be declared and independently checked. A generic acknowledgement cannot be assumed to prove beginning, cessation or delivery across every command. The explicit flags are improved; command-wide positive-evidence semantics remain open.

**M2 — Nonfinite flags can become positive stop evidence.** `_to_bool():49–60` treats any numeric nonzero value as true, including NaN and infinity. Actual reply `{status: "OK", running: 0, stopped: NaN}` produces ONLINE from query and success from both stop methods. The probe uses Python's accepted JSON NaN extension; it does not assert that a real broker/vendor emits it. The driver nevertheless parses those bytes and promotes an invalid physical flag. Reject nonfinite numeric flags before interpretation; define the accepted numeric and textual encodings explicitly. This maps to R3's missingness/qualification boundary and AB-EXE-002/004.

**M3 — The direct fault fix is overwritten by a late START fence.** The production base-class probe starts a command, preempts it with a positively stopped FAULT reply, and delivers its delayed START ACK. Direct stop initially preserves ERROR. The late fence then receives another positively stopped FAULT reply, but `actuator.py:543–548` unconditionally sets ONLINE on successful fence return. The START result is PREEMPTED_BY_STOP, the active command is cleared, and the concurrent fault has been erased. Positive cessation is retained; fault retention is not. The new ERROR-preserving conditions at the ordinary stop branches do not cover this fence branch.

**M4 — The dispatcher also overwrites the retained fault.** An actual offline production path goes `submit_event → EXECUTING → fault status query → fault-bearing stopped emergency ACK → check_execution_status`. The event becomes FAILED and gets a stopped receipt, while the actuator changes to ONLINE and loses its active command. The overwrite is at `dispatcher.py:1134–1137`, after the driver has correctly set ERROR. Other successful-stop paths also assign ONLINE (`:1045–1047, 1458–1461`). This test confirms the ordinary execution-to-fault branch; the other assignments are static observations. A stopped receipt may be justified by qualified cessation; it must not clear a simultaneously reported equipment fault. No measured volume or biological delivery is established by these ACKs.

## Remaining lifecycle boundary

**M5 — Future wake is repaired, but pending-map mutation still races cancellation.** `_handle_status()` tests request-ID membership, then does an unguarded `pop` on the callback thread (`mqtt_driver.py:264–266`); coroutine cleanup can remove it between those steps. A trace hook pauses the real callback immediately before the real pop, cancels the real pending query, then resumes the callback. It raises KeyError at line 265. Neither the production dict nor handler was replaced. This is a deterministic witness of a permitted thread/cancellation ordering; frequency and paho exception handling were not measured. Marshal lookup/pop and completion onto the owning loop together, or coordinate the whole operation. The successful uncomplicated thread controls should remain as regression controls.

Supplementary API fixtures are retained in the results, rather than used as normal-production claims. Concurrent commands explicitly reusing one request ID overwrite the pending slot, and cancellation of the older call removes the newer slot; the latter STOP times out despite its reply. Normal dispatcher commands use `REQ-event-attempt`, and ordinary STOP defaults to a UUID (`dispatcher.py:744`); this review does not claim the normal dispatcher creates the demonstrated collision. A 1001-digit timeout integer raises uncaught OverflowError before the helper's cleanup region and leaves a pending Future; such a configuration is a boundary fixture, not an observed deployment setting. Base START cancellation removes pending metadata without recording local post-send uncertainty, but this fixture does not establish loss of an upstream durable dispatcher claim. Root's separate device-lease review owns the cross-worker and lost-ACK-polling conclusions.

## Acceptance matrix

| Case | Actual 1ee8c4e behavior | Result |
|---|---|---|
| START says stopped; STOP says running | Rejected | Prior counterexamples repaired |
| Explicit normal STOPPED ACK | Success | Positive control passes |
| Current matched query / no fresh query reply | Decoded / UNKNOWN | Previous controls retained |
| Numeric-string false/true and zero fault code | Correct exercised normalization | Positive controls pass |
| Non-object payload; unhashable request ID | No escaping exception | Prior simple cases repaired |
| Ordinary cancellation / publish exception | Pending map cleaned | Prior simple cases repaired |
| Ordinary callback thread under asyncio debug | Safe Future wake | Prior simple case repaired |
| Query RUNNING + stopped true | UNKNOWN | Repaired query control |
| STOP RUNNING + stopped true | Success, ONLINE | Open contradiction handling |
| NaN stopped flag | Accepted as true | Open flag qualification |
| Fault-bearing direct stop | ERROR retained, command cleared | Direct latch fix verified |
| Fault-bearing late fence / dispatcher stop | ONLINE overwrites ERROR | Open integration |
| Callback lookup overlaps cancellation cleanup | KeyError | Open map lifetime race |
| Late unmatched ACK followed by query timeout | No operational promotion; UNKNOWN | Positive freshness control |

R3 section 183 and AB-EXE-002/003/004 require acknowledgement, execution, uncertainty, ownership, deadlines and protections to remain distinct. Stop success may justify releasing physical command ownership while a fault remains latched; it does not require inventing a delivered volume or keeping a stopped operation active forever. Share one validated command-specific ACK policy across query, ordinary stop, emergency stop and fence, preserve concurrent fault state through callers, and make pending-request ownership atomic. Those concrete cases remain before full protocol acceptance. Cache-reader parity and device leases are separate review lanes and are not inferred from this driver matrix.

Reproduction:

```bash
PYTHONDONTWRITEBYTECODE=1 python /workspace/scratch/de6bc2428cec/repair-1ee8c4e-review/protocol/protocol_matrix.py
PYTHONDONTWRITEBYTECODE=1 python /workspace/scratch/de6bc2428cec/repair-1ee8c4e-review/protocol/boundary_probes.py
```


---

# Specialist appendix: Forecast archive and scoring

# Actual-source forecast and receipt review — 1ee8c4e

Reviewed **`1ee8c4e777afa85e2ff7230d146f4ad17eff309f`**, parent `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`. The archive repairs resolve several original counterexamples. **F23/F24 remain partly open:** interrupted publication, a different mutation interleaving, and invalid-target scoring still fail. The original canonical target/area/depth return mismatch is repaired; two narrower receipt seams remain.

`probes.py` produced **19 case groups**. All **65 imported production files** matched their Git blob in the exact candidate tree; identities and Python version are recorded in `results.json`. No repository tests/audits, production edits, Git writes, network/vendor calls or field hardware were used. Scheduling hooks select actual source interleavings. A controlled child-process exit tests interruption of a valid write; it is not a power-loss test. Dispatcher probes use deliberately stale local snapshots and an inert status-only stub.

References below are relative to `repair-1ee8c4e-review/source/services/agribrain/`. `FA` means `world_model/forecast_archive.py`.

## Verified progress on the original cases

| Original case | Actual candidate result | Source |
|---|---|---|
| Durable conflict and rejected retry | Both attempts to replace mean1 by mean99 reject. Warm/cold readers retain1; disk is unchanged; evaluation against99 gives RMSE98. | FA `433–462` |
| Mutation after storage | Constructor inputs, caller record, returned store record, retrieved record and listed record are detached. Mutating their nested dictionaries does not change the archived prediction. A caller’s later rejected metadata cannot poison the archive. | FA `318–321,460–462,470–481,526` |
| Competing incompatible inserts | Exactly one of two controlled independent writers commits; the other rejects. Both subsequent readers see the winner. | FA `30–49,441–458` |
| Original evaluation collision | Different observations/evidence within the same second have different IDs and distinct durable records. An additional microsecond also changes identity. | FA `610–634` |
| Missing median copied from observation | Removed. Only-p90 forecast against77 yields RMSE NaN, not fabricated0; its finite quantile score remains4.6. A separately supplied mean50 yields point error27. | FA `566–577` |
| Forecast ID path segments | `../outside`, `/`, `\\`, dot and dot-dot forms reject at construction; unsafe retrieval returns none. | FA `323–328,420–421,466–468` |
| Invalid levels/values/sigma | Empty quantiles, p−10, NaN quantile value, negative sigma and NaN sigma reject. | FA `202–218,235–238` |
| Valid distributions | Gaussian mean10/std1 scores ≈0.233695 at its mean; zero-sigma point mass scores0 at10 and2 at12. Absent distribution still rejects. | FA `235–249,598–608` |
| Original canonical completion projection | With durable target10/area2 and local target3/area1, 20,000L now returns COMPLETED target10/area2/delivery1mm matching the durable receipt. Missing local area is also hydrated successfully. | `irrigation_runtime/dispatcher.py:1265–1277,1325–1332` |

These successes should be retained. They do not establish interruption safety, complete deep immutability throughout a call, or qualified target scoring.

## F23-01 — Final filename becomes visible before a complete conditional commit

**Confirmed new publication gap in the replacement writer.** FA `34` creates the final filename with O_EXCL before `json.dump`, flush and fsync at `36–38`. Exclusive creation prevents two winners, but the final record is visible while empty or partial. The previous temporary-file branch at `51–63` is bypassed for the forecast/evaluation calls using `exclusive=True` (`458`, `634`).

Three distinct probes establish the practical limits:

- **Valid record, interrupted process:** a child handling a valid forecast exits with code83 inside its dump after flushing a prefix. The final file remains `{"forecast_id": `; a cold reader returns none, and a valid retry is rejected as a corrupt existing record. This is the robust interruption counterexample; it does not depend on invalid caller metadata.
- **Invalid caller serialization:** unsupported set-valued metadata produces a normal `TypeError`. The failed call nevertheless leaves a partial final file and prevents a corrected retry. The caller input is not JSON serializable; the defect is failure isolation/publication, not a claim that this input should be accepted.
- **Read during a valid write:** while a selected valid writer is paused after final-file creation, cold get returns none and an identical competing store reports corruption. After release, the initial writer succeeds and a cold reader returns the committed record.

Cold read catches the parsing failure and returns none at FA `485–516`, so corrupt/in-progress and absent records are not distinguished. No observation in these cases establishes power-loss durability.

**Acceptance:** serialize and validate a frozen candidate before publication; write/fsync an unpublished complete record and conditionally publish it without replacing another identity. Readers must observe absence or a complete committed record with explicit integrity/unavailability semantics. Process interruption and failed serialization must leave the ID recoverable without silently replacing an accepted forecast. Keep the verified single-winner property.

## F23-02 — In-flight caller mutation recreates cache/disk disagreement

**Confirmed additional interleaving, distinct from the repaired post-store mutation case.** Store constructs `new_payload` at FA `445`, writes it at `458`, then builds cache and returned values by copying the still-mutable caller object at `460–462`.

The probe pauses after the payload snapshot, changes the caller record’s nested p50 from1 to99, then lets the original writer and store complete. The durable file has p50=1; returned and warm-cached records have p50=99; evaluation against99 gets RMSE0. The other quantiles remain ordered (`p10=0`, `p90=100`), so this counterexample does not depend on an invalid distribution. It uses public nested mutability plus a controlled scheduling boundary; no source file is edited.

**Acceptance:** take one detached validated canonical snapshot and use that exact snapshot/bytes for disk, cache and return. Mutation of any caller object at any point in the call must not change what the archive publishes or evaluates. Defensive copies taken at different times do not establish that property.

## F24-01 — Missing scores no longer receive fake point accuracy, but NaN is published

**Original observation-filled RMSE is repaired; missing-score representation remains incomplete.** Missing p50 without a mean produces RMSE NaN at FA `577`; absent bounds produce sharpness NaN and `coverage_hit=False` at `595–596`. The evaluation remains `in_domain`, with no component availability reason. Actual evaluation files contain NaN constants because the writer uses unrestricted `json.dump` (`36`); the probe’s strict JSON parser rejects them.

This is not the earlier fabricated-median defect. It is a residual availability/serialization boundary: missing coverage becomes a false boolean, and missing numeric components are nonfinite rather than explicitly unavailable. No production downstream parser or score aggregation was executed in this lane.

**Acceptance:** optional score components with explicit availability/reason/level metadata, JSON-safe null or a typed unavailable object, and no unqualified numeric skill contribution. Preserve the supplied-mean and valid Gaussian alternatives. A missing median does not invalidate every score that can legitimately be computed from the supplied distribution.

## F24-02 — Invalid verification data can still receive numeric skill

**Confirmed preserved qualification gaps.** FA `559` coerces observed values with `float`; no finite-value, independent evidence, target-time or support qualification precedes scoring. With a finite Gaussian forecast:

- NaN observed value yields CRPS0 and RMSE NaN.
- Infinite observation yields infinite scores.
- Boolean and numeric-string observations are coerced to1.0.
- Empty evidence IDs and evaluation before forecast issuance/target are accepted; the record defaults to `in_domain`.

A forecast with mean NaN/std1 is also accepted and evaluated with CRPS0. Sigma validation now rejects invalid sigma, but it does not validate mean or observation; `max(0.0, NaN)` in FA `249` hides the resulting invalid CRPS as zero.

Additional checked contract limits: NaN/infinite horizon, horizon100 for a one-day target, and boolean horizon pass the limited validator at FA `333–341`. Crossed p10=99/p90=1 quantiles receive a numeric score88.2 because levels are sorted but values are not checked for monotonicity (`214–232`). Gaussian coverage uses ±1.645σ while naming bounds p10/p90 (`600–603`); the standard normal CDF at1.645 is≈0.950015, whereas its p90 is≈1.281552. Quantile level and coverage conventions therefore need explicit consistent semantics.

**Acceptance:** finite typed mean/observation/horizon and a supported nonnegative sigma, distribution monotonicity and declared units/domain; origin-target interval consistent with the declared horizon; qualified independent target evidence/support/time before numeric scores. Invalid target values must not acquire zero CRPS through a clamp. Preserve valid zero-error point masses and valid Gaussian CRPS.

## F23-03 — Evaluation identity and payload canonicalization disagree

**Original second-based overwrite is repaired; a new exact retry seam is confirmed.** FA `610–612` sorts evidence IDs for the signature, but the stored record at `618` preserves input order. Evaluating evidence `['A','B']`, then the same observations/time with `['B','A']`, generates the same evaluation ID with a different payload. Exclusive publication rejects the second payload. However, FA `628` has already appended it to memory: memory lists two evaluations, including the rejected one, while disk holds one.

**Acceptance:** use the same unambiguous canonical representation for identity and persisted payload; if evidence order is meaningful, include it consistently, and if not, make the retry idempotent. Commit durably before adding the evaluation to cache/history. A failed write must not leave an accepted-looking in-memory evaluation. The verified observation/microsecond discrimination must remain intact.

## Canonical receipt projection — progress and separately qualified seams

The committed target/area/depth projection is verified repaired in the original stale-area case. Two additional local-snapshot cases remain:

1. Stale local duration99/flow999 are still returned with COMPLETED, while the durable receipt preserves duration10/flow100. The final hydration covers only volume, target and non-null area (`dispatcher.py:1325–1332`).
2. If canonical area is null but local area1 is supplied, nonzero 20,000L completes as2mm with a durable area-null receipt; returned event retains area1. The input support is taken from the local event unless omitted (`1265–1271`); canonical null is not a supported area correction.

These probes represent deliberately stale/missing local snapshots and an inert idle stub. They establish publication/support seams, not actual field operation or device ownership behavior. **Acceptance:** derive depth using authoritative support or retain qualified unsettled accounting; publish the complete committed envelope, including explicit null/missingness, rather than only selected non-null fields.

## R3 and master-plan status

F23 and F24 remain **stage8, partial acceptance**. F23 maps to AB-DAT-011 (R3 `699–701`), AB-ARC-007/008 (`746–752`) and AB-ASM-014 (`828–830`). F24 maps to AB-ML-005 (`990–992`), AB-ML-010 (`1010–1012`) and AB-ASM-016 (`836–838`). Score missingness and physical support also relate to AB-DAT-005/007 (`675–685`); receipt intention/delivery and immutable publication relate to AB-DAT-010/011 (`695–701`). The supplied master plan, line134, requires F21–F24 closure before creating new training/forecast evaluation artifacts. Selected software fixes do not establish prospective biological calibration.

Reproduce with exact candidate source at `../source` and its `../git-tree.json`, then run `PYTHONDONTWRITEBYTECODE=1 python3 probes.py`. The script verifies exact source blobs and uses a fresh `isolated/<timestamp>` directory. Results encode nonfinite observations explicitly as markers so the review JSON itself is strict; the raw archive files preserve actual candidate encoding.


---

# Specialist appendix: Prescriptions and hard envelopes

# F15 actual-source acceptance review at 1ee8c4e

Main `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`, parent `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`, makes substantial verified progress on F15. The original 21 mm cap violation, malformed weather confirmations and simple dated-row order error no longer reproduce. Full `ST05-F15-FA` remains open: invalid recommendations can become positive confirmed doses, lower hard bounds are not enforced after every modifier, and date/expiry qualification remains incomplete.

## Evidence boundary

116 focused groups ran against actual production bodies; there are no repair models. The original 71 cases were rerun, then extended for expiry, timestamps, conflicting duplicate dates, partially missing rows, original-versus-rewritten envelopes, a real downstream rate modifier, and four complete raw `run_layer8` calls. Thirty manifest entries cover 29 unique production files, all verified against the new pinned tree. Fourteen additional direct L8 dependencies were fetched at the same exact SHA into this lane; their provenance is recorded separately.

The function-composition cases use actual ActionCards with sensor and satellite evidence families, avoiding accidental blocking by unrelated evidence rules. The only recorded production exception is the complete L8 numeric-string temperature case described below. Safe complete-run controls succeed. No repository tests, audits, shared production edits, Git changes, external services or hardware were used. The complete L8 calls exercise raw shadow output, not top-level prescription authorization or physical execution. F11's unchanged controlled 86.67 kg N/ha arithmetic remains a positive control; its broader scientific package was not reopened here.

## Fixes confirmed and retained

| Production case | New result |
|---|---|
| Irrigation 20 mm with original maximum 21, salinity 3 | Leaching 21/21; unchanged after scheduler and final invariants. |
| None/empty forecast, empty row, absent wind | BLOCKED. |
| NaN/±Infinity/Boolean wind or rain; selected NaN gust | BLOCKED. |
| Speed 10 with `wind_speed_unit='m/s'` | Converted to 36 km/h and BLOCKED. Safe 2 m/s is accepted. |
| Speed 5 plus gust 20 km/h, or gust-only 20 | BLOCKED. |
| Missing spray rain or either temperature | BLOCKED. A partly missing day is skipped and a later qualified day can confirm. |
| Finite numeric-string weather | Explicitly parsed by `_parse_weather_val`; standalone drift/scheduler/final-gate composition succeeds. |
| Reversed simple date-only rows | Both orders select the actual safe date Oct 15, not a positional date. |
| Legitimate numeric zero wind and legitimate zero dose/zero cap | Preserved. |
| Invalid NaN cap outside the salinity-adjustment path | Scheduler blocks it and the final gate keeps the schedule BLOCKED. |

The prior negative final dose is eliminated. Numerical nonnegativity alone does not establish qualification: the new sanitizer can erase why the original envelope was invalid.

## Remaining reproduced findings

### F15-R1 — P0: Missing/NaN recommendation becomes a positive confirmed dose

An irrigation card with `recommended=None` or NaN, `min_safe=5`, `max_safe=21`, potato and salinity 3 is changed to **5 mm**. The exact scheduler and final invariant gate then return allowed/CONFIRMED with an empty invariant receipt. The modifier first maps the invalid recommendation to0, then applies the minimum floor. A Boolean recommendation has the same promotion. This is not the legitimate-zero control: the original recommendation is unavailable or invalid and carries no numeric scientific authority.

Similarly, NaN/negative/infinite/Boolean caps become numeric0 and can return CONFIRMED with no structured invalidity receipt after leaching. The *same* NaN-cap input with low salinity bypasses sanitation and is correctly blocked by the scheduler. Thus the qualification depends on whether an earlier modifier erased the evidence of invalidity. Original `min_safe=25, max_safe=21` is also silently rewritten as21/21 and confirmed, rather than rejecting the contradictory hard envelope.

Source: `services/agribrain/layer8_prescriptive/engines/salinity_leaching.py:83–108,125–145`; `scheduler.py:140–173`; `invariants.py:56–89`. Reproductions: `F15_CAP_none_orig_positive_min`, `F15_CAP_nan_orig_positive_min`, `F15_CAP_nan_cap`, `F15_CAP_nan_cap_low_salinity`, `F15_CAP_inconsistent_min_max`.

Closure: validate and preserve the original envelope before any modifier; carry invalid/unavailable status to the final gate; do not create a positive suggestion from an unknown rate or reinterpret an unknown limit as an observed zero. Keep legitimate zeros separately qualified. Any repair of contradictory bounds must produce a blocked/unavailable result or an explicitly authorized replacement envelope.

### F15-R2 — P0: A real later modifier violates the original minimum and still confirms

The actual environmental-risk modifier receives an irrigation `RateRange(21,20,21,'mm')` and two rainy days followed by a safe day. It reduces the recommendation to **14.7 mm**, preserving minimum20. The exact scheduler selects the later safe day and the final invariant gate leaves allowed/CONFIRMED with no violations. This starts with a finite, internally consistent envelope; it does not rely on NaN or malformed input. A direct5/min10/max21 case likewise confirms.

Source: dependency `engines/environmental_risk.py:120–130,143–150`; `scheduler.py:140–173` checks envelope shape but not whether the recommendation satisfies the minimum; `invariants.py:56–89` enforces nonnegativity and upper bounds, with no lower-bound pass. The runner applies environmental adjustments before scheduling (`runner.py:367–372`) and calls the final gate at `559`. Reproduction: `F15_MODIFIER_environment_below_min`.

Closure: apply one final feasibility check to the original immutable bounds after all modifiers, including every minimum, maximum and aggregate budget. Where a proposed reduction is agronomically desirable but below a true action minimum, abstain or choose an explicitly valid alternative rather than changing the meaning of `min_safe`.

### F15-R3 — P0: Explicit expiry and invalid execution dates remain CONFIRMED

With planning start Oct13, a safe row dated Oct 15 carrying `issued_at=Oct10`, `valid_from=Oct10`, `valid_until=Oct12 23:59:59Z` is still CONFIRMED on Oct 15. An otherwise equivalent unexpired validity control also confirms; the fields are not inspected. These metadata keys are accepted at the dictionary API boundary but are not yet an enforced typed validity contract, so this is evidence of a missing qualification boundary, not a claim that an established typed expiry contract was deliberately bypassed.

A row dated 2020 and a row dated 2030 both confirm with `horizon_days=7`. The function documents a planning horizon in days, but limits the number of rows scanned instead of the actual date interval. If the product intends a different horizon policy, that must become explicit; the current implementation does not enforce the documented interpretation.

`date='not-a-date'` and ISO timestamps with `Z` or offsets remain CONFIRMED even after the final gate records `schedule_date_format` as an error. Sorting timezone strings is not chronological sorting by instant: the tested offset pair selects the lexicographically earlier but later UTC instant. Conflicting same-day rain rows (0 versus 100 mm) can confirm without deduplication or conflict qualification. An undated row still receives a positional date.

Source: `scheduler.py:116–125,210–224,324–346`; `invariants.py:104–114` only records the format failure. Reproductions: `F15_COMBINED_explicitly_expired_validity`, `expired_date`, `beyond_horizon`, `malformed_date`, `timestamp_Z`, `timezone_lexicographic_order`, `duplicate_conflicting_rain`, `mixed_dated_undated`.

Closure: define a typed issued-at/validity/cutoff contract, parse and normalize actual instants/timezones, filter to the declared planning interval, qualify duplicate rows, and demote malformed/expired slots. A recorded error must not leave an execution schedule confirmed.

### F15-R4 — P1: Weather parsing is not shared with earlier production modifiers

The complete actual `run_layer8` call succeeds with numeric weather and with a numeric-string wind. With otherwise safe `temp_min='10', temp_max='25'`, it raises TypeError in the frost modifier before the new scheduler parser can run. The standalone new weather parser accepts those same finite numeric strings. This establishes inconsistent normalization within the actual runner, not merely an isolated helper discrepancy. If strings are intended to be forbidden at the public boundary, reject them there with a qualified receipt; otherwise normalize before every consumer.

Source: `runner.py:294–304`; dependency `engines/frost_sprinkling.py:27–30`; `scheduler.py:58–79`. Reproduction: `F15_FULL_L8_string_temperature`; controls: `F15_FULL_L8_safe_control`, `string_wind`, `mps_control`.

Additional bounded observations: unknown unit `knots` is treated as multiplier 1 (10 knots exceeds the scheduler's 15 km/h limit but confirms); finite negative speed/rain confirms. Drift still takes a maximum over the whole forecast: a future 30 km/h day blocks an otherwise qualified safe slot, while the scheduler alone accepts it. The latter is conservative overblocking, not unsafe confirmation. These belong to F15's shared unit/range/per-slot policy; no new packages are inferred.

## Complete modifier and tail review

All direct runner imports were read: ranking, phenology, cooling, frost, salinity, tillage, nutrient interactions, volatilization, IPM, lodging, environmental risk, zone allocation, cognitive pruning, adoption and framing. Rate-producing or modifying sites were traced. None supplies an immutable copy of the original minimum/maximum plus a final aggregate budget to the invariant gate. The reproduced environmental case proves a concrete consequence. Adoption/framing occur after scheduling and read rates for cost/framing; they do not restore missing lower-bound/expiry qualification. Raw L8 publication remains shadow-only pending separate authorization; this lane makes no actuator acceptance claim.

## F15 master-plan disposition

Stage 5, dependencies F01/F06/F14; R3 AB-DEC-003 (`R3_current_scientific_sections.txt:1076–1078`), AB-ECO-003 (`1088–1090`), AB-EXE-001 (`1106–1108`).

- `ST05-F15-01`: partial. Finite/Boolean parsing, common m/s conversion and simple date sorting work; shared normalization, all units, true validity intervals and timezone/conflict qualification remain incomplete.
- `ST05-F15-02`: partial. Mandatory spray wind/rain/temperature checks work in the composed boundary; original invalid dose/cap authority can still be erased before that boundary.
- `ST05-F15-03`: partial. The finite 21 mm ceiling is preserved, but contradictory original bounds are rewritten and invalid values become numeric authority.
- `ST05-F15-04` and `ST05-F15-FA`: open. Original lower bounds, expiration, invalidity receipts and complete final feasibility are not satisfied. Legal/resource/aggregate-budget integration and operational commissioning were not exercised.

Reproducible artifacts: `actual_decision_probes.py`, `actual-decision-results.json`, `coverage.json`, `dependency-provenance.json`. Production copies under `deps/` are evidence inputs and can be excluded from the user-facing bundle; their exact hashes and fetch URLs are retained.


---

# Specialist appendix: ASMAE cache and plan register

# ASMAE reader repair — actual source review

Baseline: `webClone/AgriWise` main `1ee8c4e777afa85e2ff7230d146f4ad17eff309f`, parent `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`. The reader repair closes the six previously reproduced old-writer/new-reader negative-artifact cases. The reader and writer now have identical rejection predicates. A real producer-vocabulary gap remains: the state-estimation timeout producer emits `status:'failed_spatial_timeout'`, and both current writer and reader still accept that artifact into the normal cache.

This is a bounded production-source review. `cache_reader_probes.py` freshly generates local cache fixtures using exact production methods. It executes the exact timeout output constructor/postprocessing and exact runner serializer with supplied estimator/provenance/artifact data; it does not execute a whole ASMAE inference. No repository tests, audit assertions, historical production-cache contents, provider/database/controller calls, hardware, Git changes or production edits supply evidence. All 510 selected review-copy source files match the new Git tree. The comparison writer matches the actual `a2b0bf8` cache blob `d30fae61cc8ab7c0d02c51edfcf30fc9d6bbd8b1`.

## What the reader repair establishes

| Fresh old-writer artifact | Old writer committed / old reader hit | New reader hit | New writer committed |
|---|---|---|---|
| `result_status:'rejected'` | yes / yes | no | no |
| `result_status:'aborted'` | yes / yes | no | no |
| `status:'failed'` | yes / yes | no | no |
| `status:'REJECTED'` | yes / yes | no | no |
| `is_rejected:true` | yes / yes | no | no |
| `reason:'TIMEOUT'` | yes / yes | no | no |

The old negative JSON bytes remain on disk, but cannot become current hits. Cache/hash schemas are unchanged, so this is an actual reader-side migration defense rather than a schema-key change hiding those fixtures. These are fresh boundary fixtures, not a claim that historical production caches contain all six records. No Enum-based producer is invented.

Current plain-string, explicit rejection-flag and chain-integrity-diagnostic cases show writer/reader parity. Successful and partial diagnostic artifacts still round-trip, preserving demoted authority. The two predicates also have identical ASTs. Source: [`cache.py:650-661`](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer05_asmae/cache.py#L650) and [`cache.py:732-746`](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer05_asmae/cache.py#L732).

Integrity controls remain strong within this storage contract: a valid JSON/NPZ pair reloads exact grids; corrupt NPZ bytes, tampered JSON without a payload rehash, and mismatched raster manifest shape each produce clean misses; restoring the pair restores the hit. Caller output dictionaries remain unchanged. Input key controls distinguish band identity, shape, dtype, exact sub-rounding pixel changes, validity mask and transform. These checks verify persisted identity and integrity; the producer's public `content_hash` is retained rather than scientifically recomputed by this cache.

## Confirmed remaining producer gap

The actual timeout producer at [`engine.py:585-696`](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer05_asmae/engine.py#L585) builds diagnostics containing:

- `status_override:'failed_spatial_timeout'`
- `failure_code:'STATE_ESTIMATION_TIMEOUT'`
- `reason:'state_estimation_timeout'`
- `production_usable:false`, `state_update_allowed:false`, `diagnostic_only:true`

The normal engine path calls that producer at `engine.py:405`. The exact runner serializer reads the override into top-level **status**, retaining reason/failure code inside diagnostics; it emits neither top-level `result_status` nor top-level `reason` (`runner.py:1114-1196`). Normal execution serializes and calls the cache writer at [`runner.py:568-608`](https://github.com/webClone/AgriWise/blob/1ee8c4e777afa85e2ff7230d146f4ad17eff309f/services/agribrain/layer05_asmae/runner.py#L568).

Fresh production-constructor → production-serializer → current-writer → current-reader result:

| Field / outcome | Actual result |
|---|---|
| Top-level status | `failed_spatial_timeout` |
| Top-level result_status / reason | absent / absent |
| Diagnostic failure code / reason | `STATE_ESTIMATION_TIMEOUT` / `state_estimation_timeout` |
| Writer return / reader hit | `true` / `true` |
| Producer authority and availability | all nine checked fields preserved exactly |
| Diagnostics | preserved exactly |

This is a **P2 failure-cache/retry-policy gap**, not demonstrated promotion to usable scientific authority. The preserved fields include production usability, L1 export, state update, weak-label export and visual permissions (all false), diagnostic-only (true), state availability (UNAVAILABLE), authority level (DIAGNOSTIC) and posterior availability (false). A matching ordinary request can reuse the failed timeout cache entry through `runner.py:343-498`; scientific_refresh separately bypasses read. Cache hits therefore cannot be equated with successful scientific execution or canonical publication.

The exact `_progressive_visual_fallback_output` helper also emits `status:'unavailable'` with its timeout reason nested in diagnostics. It likewise round-trips with authority demotion intact. This is a narrower helper boundary observation: the current execute method has an earlier quick_visual serving return, so the later catch's live reachability was not established and is not asserted as a second operational defect.

Closure should make cache admission consume one typed execution-result contract covering the actual producer vocabulary and nested failure metadata. Decide explicitly whether negative entries belong in a separate bounded negative-cache policy. Verify old-artifact migration, unchanged positive/partial diagnostic caching, retry eligibility and preserved authority with the real producer/serializer chain. Do not reject all diagnostic-only or non-production artifacts, since those can be legitimate products.

## Canonical mapping and retained scope

V09/V10 are local/reused review labels, not master-plan package IDs; V09 must not be silently interpreted as F09, nor V10 as F10. This cache migration/failure work maps primarily to **T11 stage 11**, ST11-T11-02/03/04 and T11-FA (R3 AB-ARC-006/007/008/012 and AB-DAT-001/002 among the full card mapping), and the relevant degraded-output work in **F38 stage 10**, ST10-F38-09/F38-FA. Storage integrity does not close F25 backend identity, F36 per-state scientific qualification, or either complete package.

The previous platform scope remains bounded: package bootstrap, drone_mission identities, structural imports and app/main publication code have exactly the same blobs as parent `1d5f15b`. The verified F37 availability improvement remains valid; adding the internal directory to sys.path still does not unify bare/qualified classes. F37's single-identity and supported-entrypoint acceptance remains open at stage 0 (AB-ARC-004/008, AB-DAT-002). The unchanged progress code at `app/main.py:594-624` still infers publication from an unrelated head in the previously reproduced completed-job cases; this cache reader patch neither changes nor validates exact job/output/head publication relations. This retained source scope maps to F38-08 and T11, not a new whole-pipeline result.

## Plan and register check

The three supplied plan documents were read directly and their bytes recomputed against the new exact tree. All match and are unchanged from parent:

| Document | Verified Git blob |
|---|---|
| Deep Repair Plan | `08d378a65992de859369950599df198e64244f01` |
| Execution Sequencing Addendum | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| Work Packages Task List / acceptance register | `8a564647af7e588802537817159117b349ff606b` |

Fresh parsing finds **52 unique full-acceptance rows, all unchecked; zero closed**. This establishes the register's state, not independent proof that every package remains technically defective. Narrow fixes and passing controls cannot be counted as full FA closure without the corresponding complete criteria and integrations. The R3/scientific requirements retain their supplied definitions and are not replaced by cache/import success.

Artifacts: `cache-reader-results.json`, `cache-reader-console.txt`, `cache_reader_probes.py`, `source-receipt.json`, `coverage.json`. Reproduce with `PYTHONDONTWRITEBYTECODE=1 python cache_reader_probes.py` from this directory. Python is 3.12.14 with the previously disclosed declared-versus-installed dependency differences; no supported-image or full-service certification is claimed.

# AgriBrain corrective verification — e63a942

**Date:** 17 October 2026. **Reviewed main:** `e63a94280b03ed390ce5dd2be25190405bc7f953`. **Parent:** `6762543c7b9279fcebf279beaf1689cbbec070fa`.

## Decision

**Many corrective changes are verified, but the claim that R01–R12 are all resolved is not supported.** R01's original two-worker admission race still reproduces. R07/R08 now block the supplied examples but do not yet enforce the general duplicate-weather and execution-validity properties. R12's Gaussian interval is corrected while its original horizon/time cases remain accepted. Bounded adjacent recovery and fault-latching failures also remain.

Proceed with the concrete corrections below, preserving the passing original controls in the same acceptance run. Keep the affected full-acceptance gates open. Independent eligible plan work and exploratory World Model/Omega research can proceed under their relevant data/model contracts; this review is not a blanket block on those objectives.

## Evidence and scope

Five specialist agents reviewed protocol, hydraulic continuity, prescriptions, forecast archive and cross-workstream/plan contracts in parallel. The coordinator independently exercised resource admission and telemetry recovery. GitHub main, the exact commit and its nontruncated tree were retrieved. The delta contains **10 production files** and one added historical review document. The historical document and repository test files were excluded from correctness evidence.

All **445 staged production blobs** match the candidate tree; lane import/dependency receipts verify their own additional inputs. Counts overlap and are not a claim that every staged file was deeply reviewed. Previous authored scripts supplied fixture scaffolding, while current execution/source determines every reported result. Simulated controller replies, selected process schedules, filesystem failures and legacy fixtures are labeled explicitly.

The reported **701 passing tests** were not independently rerun or certified. The user's local working-tree-clean claim cannot be verified through remote GitHub reads. This review made no production/Git changes and contacted no broker, field controller, actuator, drone or vendor service. Simulation outcomes do not establish measured field delivery, vendor interoperability, installation safety or prospective agronomic skill.

Normative references are the R3 monograph and three supplied plan documents. Verified R3 PDF SHA-256: `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; scientific register:153 IDs. The three plans are unchanged and exactly match current-tree bytes. The register contains **52 unique FA rows, all open, zero checked**, covering all52 master cards. All requested R01–R12 scientific-focus IDs were found in R3, and the52 cards' exact declared requirements were reconciled. Cross-cutting focus requirements are distinguished from each card's literal requirement list in the platform appendix.

## R01–R12 disposition

“Original fixed” credits a precise reproduction, not whole-package acceptance. These R identifiers belong to the prior review; canonical plan IDs are F/T packages and R3 uses AB/AW requirement IDs.

| Prior finding | Current result | Qualification |
|---|---|---|
| R01 resource exclusivity | **Open:** two actual OS workers both send START to the same device/zone and both return EXECUTING. | New locked lookup is not an atomic resource claim. |
| R02 refused NEW stops OLD | **Original fixed:** NEW is FAILED before send; no NEW START/STOP; OLD remains running. | This sequential known-owner control does not resolve R01's concurrent idle snapshots. |
| R03 latch/START decoding | **Original cases fixed:** latched fault blocks START through query timeout; contradictory START rejects. | Fault first observed by QUERY_STATUS is not latched and a later timeout permits START. |
| R04 live-aged recovery guard | **Original fixed:** live owner retained, B waits, maxowners1. | Distinct stale-recoverer replacement race still gives maxowners2. |
| R05 A→B→A predecessor | **Original fixed:** warm/cold/control all448.11mm, no conflict. | Interrupted orphan recovery can regress global publication generation4→2. |
| R06 undefined rollback registry | **Original fixed:** loser reports classified conflict; no null/undefined-name outcome; follow-up/cold both201.15mm. | No unchanged null-result defect is carried forward. |
| R07 duplicate weather | **Supplied examples fixed:** 0/1rain,5/16wind,25/42temperature block. | Smaller conflicts crossing action limits still switch disposition by row order. |
| R08 validity | **Supplied examples fixed:** already-expired daily support and malformed validity block. | Same-day future candidate18Z after expiry17Z still confirms when planning starts12Z. |
| R09 physical units/alias | **Checked examples fixed:** equivalent2m/s and7.2km/h both produce4.1mm/hr; `t_min_c` produces the card; mph/knots conversions work. | No full frost-heuristic calibration or action authorization is inferred. |
| R10 evidence identity | **Original fixed:** colon sets get distinct IDs; reordered/identical retries have one cached/durable evaluation. | Stored schema integrity and supported quantile encodings still have narrower gaps. |
| R11 distribution/evidence admission | **Syntax/distribution examples fixed:** invalid/crossed/nonfinite/conflicting aliases reject before publication; strict JSON works. | Equal aliases change scoring weights; target support/domain binding remains unqualified at the direct API. |
| R12 horizon/interval convention | **Archive interval fixed:** mean/std coverage now agrees with P10/P90 representation. | Original0.01/2-day labels on a one-day forecast and naive times still construct; unchanged yield producer still uses1.645 for namedP10/P90. |

Other preserved controls: original warm/cold observation correction201.13/201.13mm; retained-weather replay122.75mm; explicit parameter retry; non-noon/historical idempotence; same-event dispatch retry sends one START; lost ACK sends qualified STOP before finalization; failed/exceptional STOP retains active monitoring and8mm exposure. Numerical water values come from different declared fixtures and are not field measurements.

## Remaining execution and recovery contracts

### Atomic resource admission — R01, F16–F18, priority P1

Both workers are paused after truthful ONLINE snapshots from the same inert single-zone controller, before either START. They use independent production dispatcher/actuator instances and one real shared quota file. Both then send START, both return EXECUTING, and both durable claims name the same resource. Both processes exit0. This demonstrates two command effects, not doubled measured water dose.

`atomic_check_and_reserve` still checks same-event identity and plot budgets, then inserts by event ID. The new resource reader returns one matching reservation under a lock, but is consulted only after a live query returns EXECUTING. Concurrent ONLINE replies skip that branch. A query/read cannot provide atomic conditional ownership of the device for the duration of an operation.

**Implement:** put declared resource uniqueness inside admission itself. Bind exclusive resource key, immutable event envelope, exposure and a fencing generation atomically. Every reserve/reopen/release/status writer must preserve and validate that contract. Define controller-wide versus zone/pump-group exclusivity from actual capabilities. The platform appendix records static phase/zone/token seams without counting them as extra reproduced failures.

**Acceptance:** racing distinct events for one exclusive resource produce one START; identical event retries stay idempotent; admitted independent-zone capability remains usable; restart/uncertain stop preserves the rightful claim and stop rights.

Sources: [irrigation_runtime/dispatcher.py#L409-L568](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/dispatcher.py#L409-L568), [irrigation_runtime/safety.py#L468-L783](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/safety.py#L468-L783), [irrigation_runtime/safety.py#L1570-L1578](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/safety.py#L1570-L1578). R3: AB-EXE-002/003/004, AB-ARC-008.

### Query-only fault does not become a persistent latch — adjacent R03, priority P1

The original already-latched timeout case passes. In a separate fixture, the first fault arrives only through a correlated QUERY_STATUS reply. Query returns ERROR and the first submit safely fails, but `_fault_latched` remains false. A second event's query times out, changes status to UNKNOWN, then START is published and the event reaches EXECUTING without reset. No prior running operation or disputed resource lease is involved.

**Implement:** centralize validated equipment-health transitions for query, heartbeat and every command reply. A positively observed hardware fault must latch regardless of which channel delivered it. Connectivity UNKNOWN must not clear known health restrictions. Define qualified reset separately and retain STOP availability.

**Acceptance:** first-query-fault→timeout emits zero STARTs until qualified reset; the current START-fault latch and original direct/fence/STOP controls remain correct. See protocol appendix for exact current lines and fresh `r03_adjacent_results.json`. R3: AB-EXE-002/003/004.

### Stale recovery takeover still violates mutual exclusion — adjacent R04, priority P1

The live-aged-owner case now serializes at maxowners1. A distinct schedule starts with dead primary/recovery owners. A decides the recovery guard is stale and pauses before its real unlink. B replaces that guard and pauses after the primary owner-text check before its real unlink. A resumes its stale unlink, removes B's replacement guard and enters the primary section. B resumes its stale primary unlink, removes A's replacement lock and enters concurrently: **maxowners2**, both exit0.

No production decision predicate is replaced; hooks select actual filesystem-call order. This proves broken mutual exclusion, not a newly measured lost telemetry update or duplicate accepted message. The new PID check in normal finalization does not make earlier stale takeover atomic.

**Implement/acceptance:** use a process-safe locking primitive or a properly fenced storage transaction for the supported runtime. Never invalidate a newer owner based on an earlier pathname/text check. Require maxowners1 for both recovery schedules, while preserving crash recovery, same/unique-process, ten-thread, cleanup and strict-error controls.

Source: [sensor_runtime/security.py#L138-L207](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/sensor_runtime/security.py#L138-L207). F39 stage3; R3 AB-DAT-003/011/013, AB-ARC-008.

### Interrupted scoped publication regresses generation — adjacent R05/F09, priority P1

The repaired modern A→B→A and same-scope CAS cases pass. In a controlled interrupted publication, A2's checkpoint with sequence2 is written, then its head replacement fails once. Independent B publications advance the global head to4. Recovering orphan A2 reuses its old sequence2; the next B successor receives3 after its prior4. Scoped pointers remain correct; no numerical water corruption is asserted.

**Implement:** allocate monotonic publication generation at actual publication/recovery under the lock, separating it from immutable checkpoint identity/scientific sequence. Return the correct committed generation to cache/lease fencing.

**Acceptance:** the same interruption advances global generation beyond4, then the next B commit advances again; scoped heads and immutable records remain intact; already committed retries do not advance generation.

A second **P2 legacy fixture** omits the newer scoped index/head labels. A lookup initially succeeds through fallback; the first independent B publication writes only B's scoped pointer and A becomes undiscoverable while A's file remains unchanged. Migrate the supported legacy committed scope heads before the first scoped successor, or preserve a separate committed ancestry. This is an explicitly older-format input, not spontaneous loss of a modern valid index.

Sources: [world_model/canonical_worldline.py#L340-L359](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/world_model/canonical_worldline.py#L340-L359), [world_model/canonical_worldline.py#L379-L409](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/world_model/canonical_worldline.py#L379-L409), [world_model/canonical_worldline.py#L264-L291](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/world_model/canonical_worldline.py#L264-L291). F09 stage3; R3 AB-ARC-008, AB-DAT-003/012/013.

## Remaining prescription feasibility — F15

### Duplicate tolerance is not action feasibility — R07 remains partial, priority P1

The new0.5mm/2kmh/3°C discrepancy thresholds block the reported larger conflicts. Smaller differences can still straddle the action's hard limit:

| Duplicate pair | Action boundary | Safe first | Unsafe first |
|---|---|---|---|
| Rain0.49/0.51mm | Max0.5mm | CONFIRMED | BLOCKED |
| Wind14.9/15.1km/h | Max15km/h | CONFIRMED | BLOCKED |
| Tmax37.9/38.1°C | Max38°C | CONFIRMED | BLOCKED |
| Tmin5.1/4.9°C | Min5°C | CONFIRMED | BLOCKED |

Exact drift/scheduler/final-invariant functions execute; raw shadow output is not top-level authorization or hardware execution. These are input-conflict fixtures, not a claim that ordinary single-row forecasts fail.

**Implement/acceptance:** resolve canonical source/version/support or conservatively evaluate all authoritative alternatives. Do not discard a row that changes feasible versus infeasible status merely because its numeric disagreement is small. Require row-order-invariant eligibility around every action boundary, retaining identical/safe/equivalent-unit controls.

Source: [layer8_prescriptive/scheduler.py#L169-L217](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/layer8_prescriptive/scheduler.py#L169-L217), [layer8_prescriptive/scheduler.py#L382-L422](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/layer8_prescriptive/scheduler.py#L382-L422). R3: AB-DEC-003, AB-ECO-003, AB-EXE-001.

### Candidate validity is compared with planning time — R08 remains partial, priority P1

For planning12:00Z, candidate18:00Z and validity ending17:00Z on the same day, the scheduler confirms because the same-day branch uses planning time instead of the later candidate. Candidate16:00Z passes appropriately; moving the invalid18:00/17:00 pair to the next day correctly blocks. These controls isolate the branch rather than a timezone or undefined-field policy.

**Implement/acceptance:** intersect actual candidate support with the planning cutoff and declared validity; for point candidates compare the later of planning/candidate instant under declared endpoint semantics. The same candidate/expiry relation must behave consistently on the planning day and later days. Preserve original already-expired and malformed-validity controls.

Source: [layer8_prescriptive/scheduler.py#L349-L365](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/layer8_prescriptive/scheduler.py#L349-L365). F15 stage5; R3 AB-DEC-003, AB-EXE-001.

## Scientific archive and scoring limits — F23/F24

The temp/link writer, frozen snapshot, strict JSON, evidence syntax/JSON identity, failed-write isolation and central80% archive interval all pass their described corrections. Remaining bounded results are narrower:

- **Quantile encodings are not canonical across consumers.** Adding equal alias `0.5` to `p50` changes the reported finite-grid score3.0→3.5. Accepted uppercase/percentage encodings preserve that score but lose median/interval metrics to null. Normalize to one unique numeric-level map for validation, identity, scoring and metric extraction.
- **Schema-corrupt cold records still look absent.** Injected valid JSON `[]` or `metadata:[1]` returns None, whereas malformed JSON now raises ContractViolation. This is pre-existing corruption input, not a partial record generated by the repaired writer. Validate stored schema and distinguish integrity failure from absence.
- **R12's original time/horizon case remains.** Exactly one-day targets still accept horizon0.01 or2days and naive timestamps. Derive timezone-aware elapsed horizon or declare a precise supported binning convention before calibration by horizon.
- **R11's target support/domain contract is still unqualified at the direct API.** Nonblank opaque IDs get numeric in-domain evaluations without a bound target receipt. No deployed upstream resolver failure is asserted. Bind qualified variable/unit/time/spatial support/domain receipts or verify the documented upstream contract.
- **Producer interval and sparse-score conventions remain partial.** The archive now uses1.28155σ; statically inspected yield producer still labels±1.645σ as P10/P90. No end-to-end producer/archive failure was exercised. Finite-level pinball averaging also needs accurate naming or declared CRPS integration/grid weights. Equivalent distributions/encodings must receive comparable, correctly labeled metrics.

Exact examples, positive-zero controls, current lines, target blob and qualifications are in the ledger appendix. R3: AB-DAT-005/007/011, AB-ML-005/008/010, AB-ASM-016; F23/F24 remain stage8 partial packages. Cross-cutting scientific mappings do not rewrite the exact card lists.

## Implementation order and acceptance

| Parallel owner | Next change | Required integrated closure |
|---|---|---|
| Runtime — F16–F19 | Atomic resource claim and fencing across all writers; consistent equipment-fault latch from every valid reply channel. | Two idle workers cannot both START; refused foreign event cannot STOP owner; query-first and already-latched fault cases both block START; lost ACK/failed STOP retain proper ownership. |
| Telemetry — F39 | Replace/fence pathname recovery protocol. | Live-aged and stale-replacement schedules both maxowners1; crash/retry/cleanup controls retained. |
| Hydraulic — F08/F09 | Separate immutable scientific identity from monotonic committed publication generation; supported legacy-index migration. | A→B→A, same/cross-scope CAS, interrupted recovery and legacy lookup all satisfy scope/generation contracts. |
| Prescriptions — F15 | Decision-aware duplicate qualification and candidate-interval validity. | Safe/unsafe duplicate order cannot alter disposition; same-day/later-day expiry consistent; corrected units, bounds and missingness retained. |
| Forecast — F23/F24 | One canonical quantile representation, stored-schema integrity, target receipt binding and explicit horizon/interval/score conventions. | Equivalent encodings agree; invalid stores are distinguishable; original horizon case closes; qualified independent targets and common interval levels used. |

Use one mutation owner per shared production file while these independent streams progress. Fix the contract at its shared boundary rather than only widening the latest example's numeric threshold. Keep previously passing controls in the same acceptance run. The source-only plan/contract lane confirms that resource token/phase/zone policy still needs one coherent implementation; those static concerns are not counted as extra observed physical failures.

The original program estimate is not a new remaining-effort estimate. This bounded review assigns no whole-project completion percentage. All52 FA rows correctly remain open. Complete the relevant software evidence before closing affected packages; field commissioning and prospective scientific validation remain separate. The unchanged ASMAE cache fix was not rerun in this delta and is not silently converted into a fresh whole-ASMAE result.

## Reproduction

The bundle contains authored probes, fresh receipts, exact Git-object layout, selected plan/R3 requirements and six workstream appendices. Repository tests/audits, production source copies and generated controller/quota/checkpoint stores are excluded. The materializer reconstructs exact source into a separate workspace using local Git objects without fetch/checkout changes.

All **16 reproduction/verification scripts** completed from a separate reconstructed layout containing **917 verified source copies / 482 unique blobs**. Repeated dependency layouts account for duplicate copies. The Git-object materializer was compiled and its layout checked; it was not executed against a separate full Git checkout here.

Exit0 means the recorded observations were reproduced, including counterexamples; it is not a production pass score or certification of the reported701 tests. Scheduling, process-exit, filesystem and legacy-fixture qualifications appear beside each conclusion. Specialist/coordinator appendices follow with detailed current references and reproduction commands.


---

# Specialist appendix: Trajectory and hydraulic recovery

# Workstream C — e63a942 R05/R06 verification

Pinned source `e63a94280b03ed390ce5dd2be25190405bc7f953`, parent `6762543c7b9279fcebf279beaf1689cbbec070fa`. **The original R05 and R06 counterexamples are fixed in the tested production paths.** A single bounded adjacent batch found a publication-generation regression during interrupted recovery and a qualified legacy-head migration seam. These do not negate the original repaired controls; they keep whole-package F09 acceptance open.

## Verified fixes

| Actual production control | Result |
|---|---|
| R05 A→B→A warm/cold/control | **448.11 / 448.11 / 448.11 mm**, no conflict |
| R06 same-scope losing process | Classified **ConcurrencyConflictError**, no undefined-name/null-result outcome |
| Loser follow-up versus normal cold hydration | **201.15 / 201.15 mm**, all three readings retained |
| Independent full-scope concurrent writers | Both commit; B follow-up/control **439.45 / 439.45 mm**, no A events in B |
| Original registered-observation correction | Warm/cold **201.13 / 201.13 mm** |
| Original retained-weather correction | Warm/cold/resupplied control all **122.75 mm** |
| Explicit conductivity/epoch replacement retry | Same state/head; no conflict; matches fresh replacement |
| Non-noon forward and exact historical query | **105 mm** forward; **114.13 mm** historical, operational head unchanged |

Scoped CAS now validates the requested scope's predecessor, and new checkpoints link to that scoped predecessor. R06 uses the defined _PLOT_INITIAL_STATE_HISTORY registry in winner recovery. The same-scope subprocesses both exit 0; the loser's first request reports the expected conflict and its next request preserves the winner observations.

- [services/agribrain/layer3_decision/runner.py:1412–1419](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/layer3_decision/runner.py#L1412-L1419) — blob `775ac468ab8d37f47bcbe3ddcfa266e7cc3a44f9`.
- [services/agribrain/world_model/canonical_worldline.py:317–324](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/world_model/canonical_worldline.py#L317-L324) — blob `3f707522b82493693999df280ad435b5dc3bf90f`.
- [services/agribrain/world_model/canonical_worldline.py:374–388](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/world_model/canonical_worldline.py#L374-L388) — blob `3f707522b82493693999df280ad435b5dc3bf90f`.
- [services/agribrain/layer3_decision/runner.py:1502–1549](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/layer3_decision/runner.py#L1502-L1549) — blob `775ac468ab8d37f47bcbe3ddcfa266e7cc3a44f9`.

## Bounded adjacent recovery findings

### C-A01 — P1: Interrupted scoped publication reuses an orphan generation and rolls sequence backward

F09, stage 3; R3 AB-ARC-008, AB-DAT-012.

A2 writes a checkpoint record with sequence 2, then the harness fails only its head-file replacement. A remains committed at A1. Independent B commits advance the global head to sequence 4. Retrying A2 reuses the orphan record sequence and publishes global sequence 2. The next B successor receives sequence 3 after its previous committed sequence 4. Scoped checkpoint pointers remain correct; no numerical state corruption was claimed. The observed failure is monotonic publication generation across supported interrupted recovery.

Fix: Allocate a monotonic publication generation at actual head publication/recovery under the lock; distinguish immutable checkpoint identity/sequence from publication generation and expose the correct generation to cache/lease fencing.

Acceptance: Repeat the same fault/interleaving: orphan remains hidden before recovery; recovery advances head generation beyond 4; next B successor advances again; scoped A/B pointers and immutable records remain intact; idempotent replay does not advance an already committed head.

Receipt: `adjacent-results.json:interrupted_scoped_publication_generation`.

- [services/agribrain/world_model/canonical_worldline.py:340–359](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/world_model/canonical_worldline.py#L340-L359) — blob `3f707522b82493693999df280ad435b5dc3bf90f`.
- [services/agribrain/world_model/canonical_worldline.py:379–409](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/world_model/canonical_worldline.py#L379-L409) — blob `3f707522b82493693999df280ad435b5dc3bf90f`.

### C-A02 — P2: Legacy head fallback loses the older scope after the first independent scoped commit

F09, stage 3; R3 AB-DAT-003, AB-DAT-012, AB-DAT-013.

A1 has an intact cycle/geometry-bearing checkpoint. The controlled head fixture omits only the newer scoped_heads/cycle_id/geometry_version head fields. Scoped A lookup initially finds A1 through the fallback. Committing B1 records predecessor None and only B in scoped_heads. Subsequent A lookup returns None although the A1 file is unchanged. This is a legacy migration/fallback seam, not a claim that a normal modern scoped index disappears spontaneously.

Fix: Before publishing the first scoped successor from a legacy head, recover/validate the legacy committed scope heads and seed the scoped index, or preserve a separate committed global ancestry for legacy discovery.

Acceptance: The explicit legacy fixture resolves A before and after independent B publication, without scanning or promoting uncommitted checkpoint files; both scoped heads survive restart and ordinary scoped CAS controls continue to pass.

Receipt: `adjacent-results.json:legacy_scoped_head_fallback`.

- [services/agribrain/world_model/canonical_worldline.py:264–291](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/world_model/canonical_worldline.py#L264-L291) — blob `3f707522b82493693999df280ad435b5dc3bf90f`.
- [services/agribrain/world_model/canonical_worldline.py:317–324](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/world_model/canonical_worldline.py#L317-L324) — blob `3f707522b82493693999df280ad435b5dc3bf90f`.
- [services/agribrain/world_model/canonical_worldline.py:385–407](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/world_model/canonical_worldline.py#L385-L407) — blob `3f707522b82493693999df280ad435b5dc3bf90f`.

## Generation trace and controls

| Publication step | Global head sequence | Relevant scoped record |
|---|---:|---|
| A1 committed | 1 | A1 |
| A2 record written, head replacement deliberately fails | 1 | A head remains A1; orphan A2 has sequence 2 |
| B1, B2, B3 committed | 4 | B3 sequence 4 |
| Retry/recover A2 | **2** | A2 published; A/B pointers preserved |
| Next B4 committed | **3** | B4 sequence 3, below B3 sequence 4 |

The fault is injected once at the head replacement boundary after the real checkpoint write; all subsequent independent commits and orphan recovery use unchanged production methods. The orphan is correctly excluded from committed A lookup before recovery. This test establishes a generation/fencing defect, not numerical water corruption or arbitrary distributed-filesystem behavior.

The ordinary nonempty-head conflicting-successor control passes: two workers both expect A1; one commits at sequence 2 and the other receives a real scoped conflict. Retrying the winner returns the same record without changing the head. After B publishes independently, repeating A's winner leaves B as the global latest and preserves both scoped pointers. Reusing the same checkpoint ID with different payload correctly rejects.

## Fixture and harness qualification

The legacy test deliberately supplies an older-format head with no scoped index/head scope labels while preserving the actual checkpoint's cycle/geometry. Before B publication, current production fallback finds A1. After B, it cannot. The A1 file remains byte-identical. This is a migration-input test, not evidence that modern valid indexes spontaneously vanish; severity is P2 and separate from R05's repaired modern-head case.

The previous cross-scope harness expected B to lose a global CAS. Under the repaired scoped design, both independent scopes legitimately commit. Its B control now includes B's accepted Jan 2 interval before comparing Jan 3; comparing only a fresh Jan 3 would falsely report a defect. Same-scope CAS remains conflicting and is tested separately. Archived history rows may legitimately have no materialized WaterState, so the harness records their retained observations rather than treating an absent object as a code failure.

Both qualified and unqualified Worldline module aliases are redirected to the same isolated store, matching production's default physical-store behavior. No registry contents are repaired by the harness. The same-scope process interleaving gates only save order; winner restoration, conflict classification and follow-up are production behavior.

## Scope, acceptance and reproduction

This pass reran current production from the exact source. Earlier authored scripts supplied fixtures/instrumentation only; old reports and generated results are not proof of the new code. Fourteen focused supporting groups, the precise original correction, non-noon gates, six inherited deep cases, and one three-case adjacent batch completed. No further expansion or untested static-gap finding is included. All 23 supporting target blobs and four reused dependency blobs are verified against the current tree.

F09 stage-3 acceptance still requires monotonic committed generations and coherent supported legacy recovery (AB-ARC-008, AB-DAT-003/012/013). The original R05/R06 bounded fixes receive passing credit. F08's parameter and retained-forcing controls pass; this finite review does not certify every F08 or master-plan R1 coupled-trajectory criterion. No repository pytest/audit was used as implementation proof; no production/Git source, external service or hardware was changed or called. All store mutations were isolated simulated fixtures.

Completed commands from the workspace root:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/trajectory/probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/trajectory/claim_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/trajectory/gate_probe.py new
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/trajectory/deep_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/trajectory/adjacent_probe.py
```

coverage.json contains exact status, requirements, fixes/acceptance and source refs. Raw results, scripts and manifests accompany this report.



---

# Specialist appendix: Nonce ownership and ingestion

# Workstream B — exact e63a942 recovery verification

Reviewed `e63a94280b03ed390ce5dd2be25190405bc7f953`, parent `6762543c7b9279fcebf279beaf1689cbbec070fa`. The coordinating reviewer executed this lane directly using current production modules, isolated inert telemetry fixtures and actual OS processes. Ten imported source blobs match the candidate tree. No repository tests/audits or historical results supply correctness evidence; no production/Git changes, external service, credentials or devices were used.

## Original repairs and controls pass

The original R04 live-aged-owner schedule is repaired. A stays alive while its recovery file is aged31seconds; B encounters the busy guard and cannot delete it. A completes before B enters, with maximum primary-lock owners **1** and both children exiting0. The condition no longer treats elapsed age as sufficient to remove a known live owner.

Retained controls also pass:

- Same-message workers have one accepted reading and one rejection; distinct-message workers retain both entries; fresh-process duplicates reject.
- Ten threads produce one winner/nine rejections.
- Registry/calibration/pre-write failures leave no nonce/raw residue; restored retry succeeds.
- Actual recovery-owner crash is recovered; two later acquisitions succeed.
- Old inactive cleanup releases once, leaves a newer accepted receipt intact, and a later duplicate rejects.
- Strict rollback OSError propagates; cleanup restores retryability.

These are checked paths, not full F39 acceptance. Exit0 from the authored probe means its observations/assertions were reproduced, including the remaining counterexample below.

## Remaining P1 — stale recovery cleanup can invalidate a newer guard

The cleanup decision at `security.py:140–153` reads the recovery owner's identity and later unlinks the path. The new finalizer at `197–207` checks a PID prefix before its cleanup, but does not make the earlier takeover check-and-unlink atomic. The primary lock likewise checks text before unlinking at `184–189`.

One bounded actual-source schedule uses two processes:

1. Seed a dead primary owner and a dead recovery owner, both older than31seconds. A reads that recovery owner and pauses immediately before its real stale-guard unlink.
2. B removes the dead guard, creates its own live recovery guard, then pauses immediately before the real primary unlink after its owner-text check. The parent verifies that the current recovery file names live B.
3. A resumes its previously authorized path unlink, removes B's replacement guard, recovers the primary and enters its real protected section.
4. B resumes its previously authorized primary unlink, removes A's replacement primary lock, and enters while A remains inside.

The result is **2 simultaneous primary-lock owners**, expected1. Both processes exit0. The hooks select actual filesystem-call order; no production decision predicate or lock implementation is replaced. This is distinct from the now-fixed live-aged-owner case. It proves broken mutual exclusion for a takeover race; it does not establish a production lost update or same-message double acceptance under this new schedule.

Current security blob: `a674242c01a0c67b9270a92bd640abd1b38f3b9d`.

Source: [security.py:138–207](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/sensor_runtime/security.py#L138-L207).

## Repair and acceptance

Use a process-safe lock primitive for the supported deployment or a properly fenced storage transaction. An owner-text check followed by an independent path unlink cannot establish that the same owner/inode is still present. Recovery and release must never invalidate a newer owner. Keep dead-owner recovery and strict I/O error propagation.

Acceptance must run the original aged-live-owner control (max1) alongside this stale-takeover schedule (also must become max1), crash recovery, same/unique-process, thread, single-cleanup and strict-error controls. Full durable raw/normalized evidence transactions, scoped identities and retention remain separate F39 obligations; they were not newly certified here.

Canonical mapping: F39 stage3, prerequisites F01/F09; R3 AB-DAT-003/011/013 and AB-ARC-008, with the full card's AB-DAT-001/AB-ARC-009 obligations retained. Script: `actual_nonce_probes.py`. Receipt: `actual-nonce-results.json`, including current source identities, repaired `live_recovery_owner_age` and failing `stale_recovery_takeover` observations.


---

# Specialist appendix: MQTT protocol and actuator faults

# R03 protocol verification — e63a942

**The original sticky-latch bypass and contradictory START reply are repaired. One adjacent fault-origin gap remains: a fault first observed by QUERY_STATUS is not latched, so a later query timeout can permit START without a reset.**

This bounded review executes production source at `e63a94280b03ed390ce5dd2be25190405bc7f953`, parent `6762543c7b9279fcebf279beaf1689cbbec070fa`. Five executed core modules independently match the exact Git blobs in the supplied tree (`source-index.json`). Prior scripts were adapted as harnesses; every reported outcome was freshly produced against this source. Prior results, repository tests and audits are not correctness evidence.

## Remaining finding: QUERY_STATUS fault does not establish the latch

The offline integration sequence uses the real dispatcher, actuator and MQTT parser:

1. The first event's correlated QUERY_STATUS reply is `{"status":"FAULT","running":false,"stopped":true,"fault_code":7}`. The event becomes FAILED and the actuator becomes ERROR. No START is published. `_fault_latched` remains false.
2. No reset occurs. A second event's fresh QUERY_STATUS receives no reply and times out to UNKNOWN.
3. A START is published. Its local RUNNING reply makes the second event EXECUTING; the latch is still false.

The source directly explains the result. [`mqtt_driver.py:501–503`](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L501-L503) returns ERROR for an observed fault without setting the persistent latch. [`get_status():577–583`](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L577-L583) subsequently replaces the status with UNKNOWN on timeout. The new independent guards in [`actuator.py:210–213`](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/actuator.py#L210-L213) and [`dispatcher.py:504–532`](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/dispatcher.py#L504-L532) work when the latch is set, but cannot retain a query-only fault that never sets it.

Evidence: `r03_adjacent_results.json#/query_only_fault_then_timeout`, reproduced by `r03_adjacent_probe.py`. This does not require an earlier running operation, a lost START ACK, competing workers, disputed resource ownership, manual private-attribute mutation, or any reset. The FAULT payload is a supported parser input; the witness does not establish what a particular vendor controller emits in the field.

**Acceptance:** a supported fault observed through a current correlated query must preserve the equipment-health prohibition through a later timeout. New START/PULSE must remain refused until the defined qualified recovery action. Merely changing the physical-status cache to UNKNOWN must not remove that prohibition. This is a high-priority remaining R03 safety-gate gap, not a failure of the repaired already-set-latch guards.

## Repaired controls and retained protections

| Control | Fresh observation | Assessment |
|---|---|---|
| Existing latch → healthy query → query timeout | Healthy query stays ERROR; timeout becomes UNKNOWN with latch true | Sticky health state retained |
| Direct START after that timeout | VALIDATION_FAILED; zero publications | Original R03 bypass repaired |
| New dispatcher submit after that timeout | FAILED; zero query/START publications | Original R03 bypass repaired |
| START with STOPPED word + running=true, or RUNNING word + stopped=true | CONTRADICTORY_STATUS; uncertain active command retained | Original START contradiction repaired |
| START-origin FAULT | Sets latch; timeout cannot enable a later START | New latch-setting control passes |
| Clean STOP while fault-latched | STOP succeeds; command cleared; ERROR and latch retained | Physical stopping remains available |
| Direct and late-fence stopped FAULT replies | ERROR retained; stopped command cleared | Prior DV04 controls retained |
| Dispatcher fault-stop handling | FAILED, ERROR, stopped receipt, command cleared | Prior DV04 control retained |
| Failed normal STOP / failed late fence STOP | ERROR and original delivery command retained; late fence returns STOP_FAILED | No false stopped certification |
| Callback paused at real pending-map pop while query is cancelled | Callback returns; no KeyError or remaining slot | Prior DV03 race control retained |
| Older cancelled Future sharing explicit request ID with newer STOP | New slot retained; STOP receives its ACK | Identity cleanup control retained |
| Worker-thread callback, asyncio debug off/on | Loop Future completes; no callback exception | Thread completion control retained |
| Three-method cancellation and publish exceptions | Pending slots cleaned | Lifetime controls retained |
| Stale/late unmatched ACK | Does not promote the fresh query; unanswered query is UNKNOWN | Freshness control retained |
| Boolean/timeout helpers | NaN/infinity flags become unknown; representative timeout outputs finite and positive | Helper controls retained; not complete payload certification |
| Fault first observed only by query, followed by query timeout | START published without reset | **Remaining gap** |

The START contradiction and new START-origin latch are at [`mqtt_driver.py:380–412`](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L380-L412). Direct STOP retention is at [`actuator.py:345–360`](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/actuator.py#L345-L360), and late fence ownership at [`actuator.py:523–562`](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/actuator.py#L523-L562). The callback uses defaulted atomic pop and loop-owned completion at [`mqtt_driver.py:88–105`](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L88-L105) and [`257–269`](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L257-L269).

## Contract boundaries and plan coverage

Bare `{"status":"OK"}` still makes START successful/EXECUTING while retaining its active command (`mqtt_driver.py:404–406`); the same bare reply does not prove a STOP or a current query state. This is an observed implementation policy and a vendor-protocol acceptance question. It is not evidence that physical delivery occurred or that a vendor actually uses OK for transport acceptance alone. Require the commissioned controller contract to distinguish receipt, physical start, operation identity and measured delivery. A supplied unparseable flag is also normalized to unknown; this is not a promise that every command rejects the entire payload. For example, the retained matrix records `OK/running=0/stopped=NaN` as accepted by STOP. No field producer or valid strict-JSON producer of NaN is asserted.

No public qualified fault-reset operation was identified in the selected irrigation runtime. A healthy query or clean STOP does not clear an established latch in these controls. Recovery acceptance remains a specified-interface requirement; this review does not manually clear a private attribute and call that a valid reset.

R3 section 183 (lines 484–488) and AB-EXE-002/003/004 (1110–1120) require acknowledgement, execution, uncertainty, reconciliation and safety protections to remain distinct. The R3 input SHA256 is `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`.

| Master-plan package | Stage | Bounded coverage | Acceptance limit |
|---|---:|---|---|
| F17 — operation state until physical completion | 6 | START contradiction; command retained during uncertainty; STOP through fault; stopped/fault state separation | Full operation/telemetry completion not certified |
| F18 — reconcile ambiguous failures before retry | 6 | Correlated reply cleanup, cancellation, failed STOP/fence command retention | No process-restart or whole retry acceptance in this pass |
| F19 — interlock persistence and reset | 6 | Sticky equipment fault through timeout; supported query-only fault gap; no unqualified reset | Debounce, rehydration and full reset policy not reviewed here |

The master card is `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:575–652`; execution sequencing assigns F16–F19 to Stage 6. This report accepts only the listed controls, not all three packages.

## Reproduction and limits

From `/workspace/scratch/de6bc2428cec`, run each command in order:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/protocol/verify_source.py
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/protocol/protocol_matrix.py
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/protocol/boundary_probes.py
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/protocol/fault_reset_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/protocol/r03_adjacent_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-e63a942-review/protocol/collect_evidence.py
```

Fresh evidence includes 71 original matrix rows, 40 additional command rows, targeted latch/fence controls and 15 verified control assertions plus the one demonstrated query-fault gap (`acceptance_matrix.json`). Row count is not a universal pass count. Invalid timeout integration cases use an explicit 25 ms harness deadline, so finite helper validation and cancellation cleanup are verified separately from waiting for every production default timeout. The inherited harness also preserves scoped supplemental boundary observations; it is not full configuration or cancellation-ownership certification.

All publications and correlated replies are in-memory fixtures. Worker-thread callbacks exercise real Future/map code but do not verify a live paho lifecycle. Nothing here measures flow, establishes delivered volume, invokes a broker/controller service, edits production source, or uses repository tests/audits as proof. Resource leases and telemetry are separate review lanes.


---

# Specialist appendix: Forecast archive and scoring

# Workstream D — exact e63a942 forecast archive review

Reviewed **`e63a94280b03ed390ce5dd2be25190405bc7f953`**, parent `6762543c7b9279fcebf279beaf1689cbbec070fa`. **The described encoding, distribution, interval and malformed-JSON corruption repairs pass their specified checks. R10 evidence encoding is fixed; R11 remains partial for qualified target support, and R12 remains partial because its original horizon/time cases still reproduce.** Colon-separated evidence sets no longer collide; invalid evidence syntax is rejected; repeated evaluations no longer duplicate the cache; invalid/crossed/nonfinite/conflicting-alias quantiles are rejected before archive publication; strict JSON prevents nonfinite metadata publication; Gaussian archive coverage now uses the P10/P90 multiplier; malformed JSON now raises an integrity error.

F23 and F24 whole-package acceptance remains **partial**. A narrower injected schema-corruption case still looks absent; quantile aliases are validated but not canonicalized consistently for scoring/metrics. The original R12 one-day horizon 0.01/2 and naive-time cases are unchanged, and R11 qualified evidence support remains incomplete. The unchanged yield producer still labels ±1.645σ bounds as P10/P90. These are qualified residuals, not reasons to carry the repaired original failures forward.

## Evidence and reproduction

`probes.py` executed **24 case groups**: the previous 19 case definitions rerun against this exact source, plus five requested adjacent groups. Results are in `results.json`. All **36 imported production files** matched this commit's Git tree by Git blob SHA; the statically read yield target was verified separately. `source-receipts.json` contains both kinds of receipts. The core archive blob is `ffedff44c138c3dc371ce5765bde1fce176df210` (SHA-256 `0cf2dd90caecb8f05148a77d9dbdedb1653faf2379e8c0483ea70d80bafe024e`).

Run from any working directory with Python 3.12 and the same source dependencies:

```bash
python /workspace/scratch/de6bc2428cec/repair-e63a942-review/ledger/probes.py
```

The script requires the sibling `source` tree and `git-tree.json`; it verifies the archive before import and all loaded production blobs before writing receipts, disables bytecode writes, and creates a fresh isolated archive directory beneath `ledger/isolated`. It contains direct production API calls and explicitly labeled scheduling, link-error, existing-file-corruption and process-exit injections. It uses no repository tests, historical audit reports, production edits, Git writes, controllers, network services or hardware. Previous scripts supplied case scaffolding; **all reported behavioral receipts are fresh executions on e63a942**. The controlled child exit is not a power-loss durability test. No actuation or deployed evidence resolver was exercised.

Source references below use `source/services/agribrain/world_model/forecast_archive.py` (**FA**) and `source/services/agribrain/layer6_yield/yield_forecast.py` (**YF**) under this review root. Static YF observations do not imply an end-to-end producer-to-archive failure.

## Verified repairs and retained positive controls

| Check / result case | Observed result on e63a942 | Current source |
|---|---|---|
| Former colon identity collision | `['A:B','C']` and `['A','B:C']` produce different evaluation IDs and both commit successfully. | FA 701–703 hashes a JSON evidence list |
| Blank / None / scalar evidence syntax | `['']`, `[None]` and scalar `'AB'` each raise `ContractViolation`. | FA 629–640 |
| Reordered and repeated evaluation | Reordered IDs retain one canonical evaluation. Three identical/reordered retries produce one memory and one disk record. Changing observation/time by one microsecond produces a different ID. | FA 640, 701–727 |
| Invalid quantiles at ingress | NaN values, crossed quantiles, illegal level and conflicting `p50`/`0.5` values all reject before a forecast is published; subsequent evaluation finds no forecast. | FA 366–402; 478–479 |
| Strict JSON metadata | Nested NaN and infinity metadata raise JSON `ValueError`, leave no final/cache entry or temp, while nested zero commits unchanged. These are invalid-caller serialization checks, not process crashes. | FA 35, 503–524 |
| Archive Gaussian interval | Standard normal at observation 1.5 now yields coverage false in both mean/std and P10/P50/P90 representations; widths are 2.5631 and 2.5631031311 respectively. | FA 670–695 |
| Original malformed JSON | Injected existing final file containing `{` raises `ContractViolation` on cold read and retry, without overwrite. This is an injected corruption fixture, not a writer-created file. | FA 517–518, 577–580 |
| Original durable conflict / rejected retry | Both attempts to replace committed mean 1 with mean 99 reject. Warm/cold readers remain 1, bytes unchanged; observation 99 gives RMSE 98. | FA 495–524 |
| Process interruption before publication | Child exits 83 during dump after writing/flushing a prefix into its temp. No final file exists; cold read is correctly absent; retry succeeds. Orphan temp stays inert. | FA 30–58 |
| Reader during temp write / identical writer | Reader sees no uncommitted final; a complete identical competitor and the resumed writer both succeed; ordinary temps are cleaned. | FA 30–58 |
| Concurrent incompatible / identical link | Barrier immediately before actual link: incompatible candidates yield one accepted winner and one conflict, all readers see winner. Identical candidates both succeed. No normal temps remain. | FA 38–58 |
| Injected link failure | `OSError` leaves no final/temp/cache; normal retry succeeds. | FA 38–58; 520–524 |
| In-flight caller and retrieved-copy mutation | Caller P50 changed from 1 to 99 after production snapshot does not change returned, warm or cold prediction. Retrieved-copy mutation also stays isolated; observation 99 gives RMSE 98. | FA 478–479, 522–524, 543, 576 |
| Unavailable partial metrics | P90-only prediction at observation 77 gives finite grid score 4.6, while RMSE, sharpness and coverage are JSON null. No observation-filled P50 is used. Strict JSON parse succeeds. | FA 657–687 |
| Finite numeric guards / distribution-before-time | Nonfinite/bool/string observation, NaN mean, nonfinite/bool horizon and gross 100-day mismatch reject. Missing distribution rejects before pre-target time check. | FA 355–365, 623–651 |
| Valid zero / Gaussian controls | Sigma 0 and exact truth correctly score 0; sigma 0 and error 2 score 2. Gaussian N(10,1) at 10 scores 0.23369497725510913. Empty quantiles and negative sigma reject. | FA 197–264 |

## Residual findings and acceptance

### D-E63-01 — some schema-corrupt final records still look absent

**Confirmed, injected fixture; narrower than the repaired malformed-JSON case.** `cold_reader_schema_corruption_signaling` writes existing files with valid JSON but invalid record schema. Top-level `[]` and `{'metadata':[1]}` return `None` on cold read. The corresponding `AttributeError` is outside the selected exception classes and is swallowed by FA **577–580**. A malformed horizon in the same group does raise `ContractViolation`, demonstrating the repaired branch works for recognized exceptions.

This does not show successful temp/link publication creates corrupt records. It shows F23 step 4 is only partly satisfied for pre-existing corrupt state. Missing, excluded and corrupt state cannot all be inferred from `None`.

**Acceptance:** validate the decoded top-level and metadata schema before access, and raise an explicit integrity exception for all unreadable/invalid stored records; preserve explicit absence for a genuinely missing file and preserve non-overwrite/retry safety. Repeat `{`, `[]`, wrong metadata type, missing required field and valid-record controls. Plan F23 **744–753**, task `ST08-F23-04` **1090–1094**; R3 AB-ARC-007 **746–748**, AB-DAT-011 **699–701**.

### D-E63-02 — quantile level validation does not establish one canonical scoring representation

**Confirmed direct production behavior.** `canonical_quantile_level_equivalence` evaluates the same level/value distribution at observation 5:

| Accepted map | Reported `crps` | RMSE / sharpness / coverage |
|---|---:|---|
| `p10:0,p50:10,p90:20` | 3.0 | 5 / 20 / true |
| Same map plus equal alias `0.5:10` | 3.5 | 5 / 20 / true |
| `10:0,50:10,90:20` | 3.0 | null / null / null |
| `P10:0,P50:10,P90:20` | 3.0 | null / null / null |

The new `level_map` rejects conflicting aliases, which is verified. Equal aliases still append duplicate entries to `parsed` at FA **220–223**, and the unweighted average counts each at **235–243**. Accepted normalized percent/uppercase syntax is then not recognized by the exact-string metric lookups at **657–680**. Returning null is safer than fabricating a perfect metric, but here the required median and interval are present under accepted aliases.

**Acceptance:** normalize quantile levels once into a unique numeric-level map, reject conflicts, collapse equal aliases without changing weight, and use that same representation for score, median, endpoints and canonical identity. Equivalent supported encodings must yield the same numerical metrics. Plan F24 **770–779**, task `ST08-F24-04` **1127–1131**; R3 AB-ML-005 **990–992**, AB-ML-010 **1010–1012**.

### D-E63-03 — horizon/time consistency remains permissive

**Confirmed constructor behavior, preserved contract gap.** For exactly one day between issuance and target, `horizon_days=0.01` and `2` both construct successfully, and both-naive datetimes are accepted. FA **348–359** checks datetime type/order and finite positive horizon but does not require timezone awareness; its 1.05-day tolerance accepts those cases. Gross mismatch and nonfinite horizon rejection are positive controls, not still-failing findings.

**Acceptance:** require timezone-aware times, then derive the elapsed horizon or validate an explicit documented rounding/bin convention tightly enough to distinguish the exercised cases. Use the same convention in horizon calibration groups. This review does not assume every conceivable calendar bin is invalid; no such bin contract is declared here. Plan F24 **770, 778–779**, task `ST08-F24-01` **1109–1113**; R3 AB-ML-010 **1010–1012**, AB-ML-008 **1002–1004**.

### D-E63-04 — typed evidence syntax is fixed; independent support/domain qualification remains an API seam

**Confirmed direct API behavior, deployment qualification required.** The new evidence syntax checks work. `invalid_support_metadata_binding` supplies a nonblank ID that has no evidence object in the isolated fixture and forecast metadata declaring a different plot support, `out_of_domain` and `posterior_diagnostic`. Evaluation still emits numeric metrics with default `in_domain` and `observation_space` (FA **439–440**, **705–716**). The function has no typed target/evidence receipt parameter and only checks ID syntax at **629–640**.

This does **not** establish a deployed caller supplies unsupported references. Metadata is not itself a verified evidence receipt. It establishes the archive API cannot substantiate independent observation support, variable/unit agreement or domain from these arguments; an upstream binding contract has not been exercised in this pass.

**Acceptance:** bind evaluation to a typed, independently qualified target receipt (variable/unit, temporal/spatial support, role, availability and domain), or demonstrate and verify an upstream contract that supplies equivalent checked bindings. Unqualified references must remain unavailable/unknown rather than gaining default in-domain certification. Preserve zero-valued valid observations and the new syntax/identity checks. Plan F24 **771, 779**; R3 AB-DAT-007 **683–685**, AB-DAT-009 **691–693**, AB-ML-005 **990–992**, AB-ML-010 **1010–1012**, AB-ASM-016 **836–838**.

### D-E63-05 — interval naming and sparse-score conventions are only partly repaired across targets

**Archive multiplier repaired, producer convention remains static evidence.** FA **691–694** now uses 1.28155σ for the central 80% interval. YF **130–131**, **243–244** still emits fields named `yield_p10`/`yield_p90` using ±1.645σ; YF **224–228** uses 1.645 to invert those widths. The code explicitly derives a standard deviation at YF **104–116**, so the field names and Gaussian multiplier encode different quantile levels. This is an unchanged F24 target gap; no producer-to-archive execution was inferred.

FA **187–196** continues to describe the finite unweighted pinball average **235–243** as CRPS. For the standard normal control at observation 1.5, analytical Gaussian CRPS is 0.9944240039774529 while the three-level average is 0.8165058317095463. This difference alone is expected from a finite score approximation; it is not a failure of the valid Gaussian formula. F24 explicitly requires accurate naming or a documented integration convention.

**Acceptance:** use correctly named explicit interval levels consistently in both target files, preserve physical zero/support handling, and label the finite-grid score and grid/weights or implement the documented CRPS integration rule. Check Gaussian and quantile representations at common levels, with declared target domains and horizon grouping. Plan F24 **765–779**, task `ST08-F24-02` **1115–1119** and `ST08-F24-04` **1127–1131**; R3 AB-ML-005 **990–992**, AB-ML-010 **1010–1012**.

## Adjacent input-type outcomes and limits

`typed_distribution_and_metadata_json_boundary` distinguishes invalid caller types from numerical/publication failures. Nonempty quantile list rejects with `ContractViolation`; `None` reaches a later `TypeError`; empty list/string are converted to an empty dict at serialization while a valid mean=0/std=0 distribution remains present. List metadata fails with `AttributeError`. None of these rejected cases publishes a final/cache entry. These outcomes support a consistent typed-input contract as follow-up, but do not establish false numerical skill credit. A forecast with no distribution can still be archived; its evaluation explicitly rejects before time checks, so no numeric credit was observed.

The script probes selected interleavings rather than every scheduler or filesystem. The crash leaves an inert orphan temp, an operational cleanup consideration, not a partial canonical forecast. No claim is made about power-loss/directory durability, deployed evidence resolution, field calibration, full learning lineage or promotion permission.

## Plan and R3 coverage

The master plan is `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`; F23 is **730–753**, F24 **755–779**. Stage 8 includes F21–F24 in `AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md` **36**; the master plan **134** gates new training/evaluation artifacts on correction of these packages. This review signs off the listed archive counterexamples, not all Stage 8 dependencies.

The supplied normative text is `current-plan-review/R3_current_scientific_sections.txt`. F23 maps to AB-DAT-011 **699–701**, AB-ARC-007 **746–748**, AB-ARC-008 **750–752**, AB-ASM-014 **828–830**. F24 maps to AB-ML-005 **990–992**, AB-ML-010 **1010–1012**, AB-ASM-016 **836–838**. Zero/missingness handling is supported by AB-DAT-005 **675–677**. This bounded pass does not certify prospective-versus-reconstruction provenance or all R3 scope simply because atomicity and numeric guards pass.


---

# Specialist appendix: Prescriptions and hard envelopes

# F15 bounded actual-source review at e63a942

The supplied R07–R09 examples improve at `e63a94280b03ed390ce5dd2be25190405bc7f953` (parent `6762543c7b9279fcebf279beaf1689cbbec070fa`). Original R07 disagreement examples now block, original R08 same-day expiry and malformed-validity examples now block, and R09's physical-unit/temperature-alias examples are consistent. Two closely related acceptance failures remain: smaller duplicate disagreements can still change safety disposition by row order, and same-day future execution can outlive its declared validity.

167 focused groups ran: all 138 previous groups plus one bounded 29-group adjacency pass. There were no production exceptions. All 30 manifest entries, covering 29 unique production files, match the new pinned tree. Newly changed frost/scheduler files are used before any old dependency copy; unchanged dependencies were reverified. No network, repository tests/audits, production/Git changes, external services or hardware were used. Actual production bodies execute; there are no repair models.

Function-composition fixtures use real ActionCards with two independent evidence families and the final invariant gate. Four raw `run_layer8` controls also run. Modifier outputs and raw L8 shadow results do not establish top-level authorization or physical execution.

## Verified fixes and retained controls

| Case | Current result |
|---|---|
| R07 original duplicate rain 0/1 mm, speed 5/16 km/h, maximum temperature 25/42°C | BLOCKED for conflicting same-day support. |
| R08 planning 12:00Z, daily row with validity ending 08:00Z | BLOCKED. |
| R08 malformed `valid_until` | BLOCKED with an unqualified-validity reason. |
| R09 equivalent wind 2 m/s and 7.2 km/h at −5°C | Both frost modifiers return 4.1 mm/hr. |
| R09 equivalent `t_min_c` alias | Produces the frost card; previous zero-card discrepancy is removed. |
| mph and knots | The previously supplied 10 mph/10 knot spray cases now block after conversion. |
| Earlier DV15 invalid rate/cap and DV16 later-modifier lower-bound cases | Remain BLOCKED; missing/NaN recommendation does not become an authorized positive dose. |
| Numeric-string whole-run control | Continues to succeed; no temperature TypeError. |
| Safe same-day future slot before expiry; identical duplicate zero wind; equivalent-unit duplicates | CONFIRMED. |
| Original date/horizon/UTC controls and legitimate zero dose/cap/wind | Their corrected behavior is retained. |

Changed source blobs: scheduler `7174fe2c91f98bca0187bd57776a559f9a534aba`; frost modifier `70f5d69ca14efaeab731a65e0c52fdda449ea040`.

## Remaining E1 — Review priority P1: Conflict tolerance still differs from action feasibility

The scheduler now checks rain, speed, gust and temperature differences, but only declares conflict when the difference exceeds 0.5 mm, 2 km/h or 3°C. It then retains the first same-day row. Smaller differences can cross the actual action limit and therefore cannot be discarded merely because they fall within a magnitude tolerance.

| Same-day pair | Actual action boundary | Safe row first | Unsafe row first |
|---|---|---|---|
| Rain 0.49  / 0.51 mm | Maximum 0.5 mm | CONFIRMED | BLOCKED |
| Speed 14.9  / 15.1 km/h | Maximum 15 km/h | CONFIRMED | BLOCKED |
| Maximum temperature 37.9  / 38.1°C | Maximum 38°C | CONFIRMED | BLOCKED |
| Minimum temperature 5.1  / 4.9°C | Minimum 5°C | CONFIRMED | BLOCKED |

The rain 0.25/0.75 mm pair also changes disposition by order because its difference equals, rather than exceeds, the 0.5 mm conflict threshold. The exact drift gate, scheduler and final invariant function all execute. Both-safe rain duplicates, identical zero-wind duplicates and equivalent-unit duplicates remain valid positive controls.

Source: `services/agribrain/layer8_prescriptive/scheduler.py:169–217` applies difference tolerances and keeps the first row; actual spray limits at 31–35 and feasibility checks at382–422. Reproductions: `F15_COMBINED_near_limit_*` and their reversed variants, plus `exact_conflict_tolerance_rain_*`.

This is the remaining general property behind R07, not a reversal of the corrected larger examples. It is an input-conflict qualification defect: no claim is made that normal single-row forecasts fail.

Concrete repair and acceptance: group the same support once, normalize values/units, and evaluate the action's feasible set using all authoritative alternatives or an explicit version/source rule. A pair that changes feasible versus infeasible status must not be silently collapsed to the first row. Assert order-invariant disposition just below/above every action threshold, including equality boundaries. Keep all safe/identical/equivalent-unit controls.

## Remaining E2 — Review priority P1: Same-day validity chooses planning time instead of the later candidate time

With planning start `2026-10-13T12:00:00Z`, candidate `2026-10-13T18:00:00Z`, and `valid_until=2026-10-13T17:00:00Z`, the exact scheduler returns CONFIRMED for Oct13. The expiry branch uses planning 12:00 whenever the candidate and start share a day, so it does not compare the actual 18:00 candidate with 17:00 validity.

The positive control with a 16:00 candidate and the same 17:00 validity confirms legitimately. Moving the invalid 18:00/17:00 pair to the next day correctly blocks it. The original daily-midnight row whose validity ends before planning now also blocks. These controls isolate the new same-day branch; the issue is not a timezone parsing ambiguity or an unsupported metadata field.

Source: `scheduler.py:349–365`, especially `ref_dt = start_instant if cand_d == start_d else ...` at 362. Reproductions: `F15_TIME_same_day_candidate_after_expiry`, `same_day_candidate_before_expiry_control`, `next_day_candidate_after_expiry_control`.

Concrete repair and acceptance: compute the actionable support from both the actual planning cutoff and the candidate interval, rather than choosing one by calendar-day equality. For point candidates the earliest defensible comparison is the later of planning start and candidate instant. Preserve UTC normalization and explicitly declare inclusive/exclusive expiry semantics. The same candidate/expiry relationship must have the same disposition on the planning day and on a later day. Keep the original already-expired daily-row and malformed-validity controls.

## Bounded scope and F15 acceptance

R09's specific physical-unit/alias regression is verified fixed at the actual modifier boundary. It does not independently calibrate the frost heuristic or prove operational eligibility. Earlier observations about unsupported/absent rate units, optional unbounded versus unavailable ceilings, remaining metadata-policy semantics and broader budget/resource integration are retained as unqualified acceptance scope; they were not expanded into new findings in this pass.

F15 is stage 5, dependencies F01/F06/F14. R3 mappings remain AB-DEC-003 (`R3_current_scientific_sections.txt:1076–1078`), AB-ECO-003 (`1088–1090`) and AB-EXE-001 (`1106–1108`). The original package priority is P0; the P1 labels above are current review priorities and do not rename the plan.

- `ST05-F15-01`: partial. Physical normalization examples and UTC parsing work, while decision-relevant duplicate support and actionable validity still fail E1/E2.
- `ST05-F15-02`: supplied mandatory-weather and invalid-envelope reproductions remain fixed in the checked scope.
- `ST05-F15-03`: supplied original finite upper/lower-bound and invalidity cases remain fixed through final feasibility.
- `ST05-F15-04` and `ST05-F15-FA`: remain open for E1/E2 and full declared legal/resource/aggregate-budget integration. Operational commissioning was not exercised.

Artifacts: `actual_decision_probes.py`, `actual-decision-results.json`, `coverage.json`, `source-verification.json`, `probe-summary.json`, `probe-stderr.txt`. They distinguish original repaired fixtures, positive controls and the two bounded remaining cases.


---

# Specialist appendix: ASMAE cache and plan register

# Cross-workstream contract and plan check

Actual source: `e63a94280b03ed390ce5dd2be25190405bc7f953`, parent `6762543c7b9279fcebf279beaf1689cbbec070fa`. This lane independently verifies the normative plan/register and traces the shared resource-owner contract. All **445 supplied production source blobs match the exact new tree**. This is a read-only static/source and document check; no new physical, concurrent-worker, database, network or controller reproduction is claimed here. The coordinating workstream owns the current resource and nonce probes.

The added durable resource lookup improves access to foreign-event information, but does not establish atomic resource admission across different event IDs. Existing event-idempotency/quota locking and the new device lookup remain different contracts. The following limitations are source-confirmed static findings; their physical consequences are left to the coordinating current-source probes rather than inferred from old reports.

## Shared owner/admission trace

| Boundary | Actual current behavior | Contract implication |
|---|---|---|
| `safety.py:170-217` | One thread/file lock serializes store mutations; ownership of that lock has a token. | Protects each store transaction, not ownership of a physical device for the whole operation. |
| `atomic_check_and_reserve`, `safety.py:468-783` | Checks existing same-event stopped/settled/active payloads and plot budget; inserts `reservations[event_id]` with device, zone and owner_token. No scan rejects another event owning that resource. | Different event IDs can pass this admission boundary for the same device/zone; the quota lock is not a unique resource constraint. |
| Dispatcher admission, `dispatcher.py:409-425,486-503` | Claims by event, marks DISPATCHING and starts tracking before the live query. | Event identity is established before physical send, but no atomic device/group claim is created. |
| Live query, `dispatcher.py:504-568` | Independent fault latch is now checked before querying and after query failures; foreign resource lookup is consulted only when returned status is EXECUTING. | Fault gating has useful source improvements. Truthful concurrent ONLINE snapshots still are not an exclusive admission primitive. No new physical effect is asserted by this static lane. |
| New resource lookup, `safety.py:1570-1578` | Locked read returns the first reservation matching device and compatible zone in DISPATCHING/EXECUTING/VALIDATING. | It is a lookup over potentially multiple claims, not an atomic conditional claim or uniqueness invariant. A first own-event record may hide another matching record when multiple reservations exist. |
| Actuator command lock, `actuator.py:90-94,379-385` | asyncio dispatch lock belongs to one actuator instance. | Useful local serialization does not establish cross-process ownership. |

Source links: [shared admission](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/safety.py#L468), [new resource reader](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/safety.py#L1570), [dispatcher pre-send logic](https://github.com/webClone/AgriWise/blob/e63a94280b03ed390ce5dd2be25190405bc7f953/services/agribrain/irrigation_runtime/dispatcher.py#L504).

The resource policy is also narrower than a universal device exclusion: when both zones are nonempty and unequal, the new reader ignores the other zone even on the same device. The base actuator's EXECUTING validation is device-wide (`actuator.py:220-259`). The deployment must declare whether the exclusive resource is a whole controller, one valve/zone, a pump group, or a supported concurrent-zone capability. This lane does not assume all zones must serialize or that the current cross-zone behavior caused a field failure.

Lifecycle scope needs the same explicit policy. The new reader excludes STOP_REQUESTED, although failed-stop reopening writes exactly that state (`safety.py:1481-1502`) to retain uncertain operation/exposure. It includes VALIDATING, while its new dispatcher consumers specifically check only EXECUTING/DISPATCHING (`dispatcher.py:548,938`). These are static phase-contract differences, not proof that validation always requires a running device or every STOP_REQUESTED record denotes actual delivery. The cutoff/fault exception must continue to operate on the actual resource owner.

## Every shared writer must participate in the same contract

The AST inventory includes all ten SharedQuotaStore methods that call `_write_state`; it records their exact arguments and source lines in `plan-contract-results.json`.

| Writer family | Current owner behavior |
|---|---|
| Atomic admission (`468-783`) | Writes owner_token, but no device/zone uniqueness check across event IDs. |
| Compatibility `reserve` (`816-944`) | Rebuilds an existing reservation while preserving many admitted dimensions; does not carry owner_token into its new record. It can create a reservation without consulting the resource reader. |
| `reopen_active` (`1381-1517`) | Restores the canonical event envelope and conservative exposure as STOP_REQUESTED; reconstructed reservation has no owner_token/resource generation. |
| `set_actual_start`, `update_status`, `mark_unsettled`, `release` (`947-1007`) | Locked per-event mutation with useful start/stop rules, but no expected owner/fencing generation argument. |
| `settle`, `record_stopped_delivery` (`1010-1378`) | Bind event/delivery dimensions and update accounting; do not accept resource-owner fencing identity. This is not a new settlement/accounting reproduction. |

The owner_token is currently metadata rather than a complete enforced operation lease. Its loss in compatibility writers is a closure concern if the token is to become authoritative; it is not presented as a separately demonstrated authorization exploit. A coherent repair needs a declared resource key plus atomic conditional ownership, immutable event binding and a fencing/stop-right policy respected by admission, restart/reopen, status, stop, release and finalization writers. Preserve compatible event retries and legitimate independent-zone capability. F16–F19 full acceptance must exercise these paths together rather than equate a locked lookup with the claim itself.

## R01–R12 requirement mapping

R01–R12 are local review-topic identifiers, not canonical master-plan package IDs. The table maps their requested scope, not their current technical disposition; other workstreams establish current numerical/protocol outcomes. All referenced scientific requirement IDs were found in the supplied R3 scientific sections. The exact requirements printed in **all 52 master cards** were independently compared with their direct normative document sections and match.

| Topic | Canonical packages / full stage | Scientific focus |
|---|---|---|
| R01 resource exclusivity | F16/F17/F18 / 6 | AB-EXE-002, AB-EXE-003, AB-EXE-004, AB-ARC-008 |
| R02 refused versus live-owner cutoff | F16/F17/F18/F19 / 6 | AB-EXE-003, AB-EXE-004, AB-ARC-008 |
| R03 latched fault/start admission | F17/F18/F19 / 6 | AB-EXE-002, AB-EXE-003, AB-EXE-004 |
| R04 replay/recovery ownership | F39 / 3 | AB-DAT-003, AB-DAT-011, AB-DAT-013, AB-ARC-008 |
| R05 scoped predecessor/publication | F08/F09 / 3 | AB-DAT-012, AB-DAT-013, AB-ARC-008, AB-AGR-006 |
| R06 winner recovery/failure response | F09 / 3; F38 / 10 | AB-DAT-012, AB-ARC-006, AB-ARC-008 |
| R07 duplicate-weather constraints | F15 / 5 | AB-DEC-003, AB-ECO-003, AB-EXE-001 |
| R08 actionable time/forecast validity | F15 / 5 | AB-DEC-003, AB-EXE-001, AB-DAT-014 |
| R09 weather units/support boundary | F15 / 5; adjacent F06 / 3 | AB-DAT-007, AB-DEC-003 |
| R10 immutable evidence identity | F23 / 8 | AB-DAT-011, AB-ARC-008, AB-ARC-009 |
| R11 archive/target admission | F23/F24 / 8 | AB-ML-005, AB-ML-008, AB-ML-010, AB-DAT-005, AB-DAT-007, AB-DAT-011 |
| R12 horizon/interval convention | F24 / 8 | AB-ML-005, AB-ML-010, AB-ASM-016 |

Some focus requirements are cross-cutting R3 mappings rather than requirements explicitly listed on the selected card: R06 AB-ARC-006; R08 AB-DAT-014; R09 AB-DAT-007; R10 AB-ARC-009; R11 AB-DAT-005/007 and AB-ML-008. `plan-contract-results.json` preserves both the unmodified exact card lists and these additional mappings. In particular, F06's actual card concerns exact dated forcing; it is not silently rewritten as the unit-normalization package.

## Normative register and retained startup scope

| Normative document | New-tree/local Git blob | Parent comparison |
|---|---|---|
| Deep Repair Plan | `08d378a65992de859369950599df198e64244f01` | unchanged |
| Execution Sequencing Addendum | `40751038dc8760e91bc3ab115e30c5e28395953a` | unchanged |
| Work Packages Task List / FA register | `8a564647af7e588802537817159117b349ff606b` | unchanged |

Fresh parsing yields **52 unique full-acceptance rows, all unchecked, zero closed**, covering exactly the 52 master cards. This is register state, not independent proof that every package is technically defective. Slice completion and complete package sign-off must remain distinct.

The bootstrap, drone enum, structural-import and app/main blobs are unchanged from parent. The prior verified F37 import-availability improvement and remaining identity/supported-runtime limits are therefore retained scope, not new startup failures or fresh full-startup certification. ASMAE cache source is also unchanged; its passing DV18 controls were not rerun. No new claim about canonical publication or scientific validity follows from this document check.

Artifacts: `verify_plan_contracts.py`, `plan-contract-results.json`, `plan-contract-console.txt`, `source-receipt.json`, `coverage.json`. The script reproduces exact source hashes, all three plan hashes, register counts, R3/card mappings and the writer inventory without executing production control functions.

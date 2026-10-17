# AgriBrain corrective verification — fc82f14

**Date:** 17 October 2026. **Reviewed commit:** `fc82f14975cff7a90d15e21747ceb4fbc22a5457`. **Parent:** `e63a94280b03ed390ce5dd2be25190405bc7f953`.

## Decision

**Most supplied corrections are verified. The same-device admission guarantee still fails under a deterministic two-process schedule, so the claim of complete resolution is not supported.** Both workers obtain idle snapshots; A fully acknowledges and becomes durably EXECUTING before B claims; B nevertheless sends a second START. Both return EXECUTING for the same device and zone.

Proceed with the bounded corrective implementation below. Close the atomic ownership gap before qualifying concurrent actuation or signing the affected Stage 6 acceptance gates. The other checked repairs receive explicit passing credit. Independent plan work and exploratory World Model/Omega objectives can proceed under their own qualified data/model contracts; this is not a blanket block on research or unrelated packages.

Five specialists reviewed hydraulic continuity, protocol/fault handling, forecasts, prescriptions and cross-workstream plan contracts in parallel. The coordinator independently exercised resource admission and nonce recovery. The review follows the original plan and R3; it is a corrective claim check with declared boundaries, not a fresh whole-repository certification.

## Evidence, exclusions and provenance

The candidate commit, main and its nontruncated 4,067-entry Git tree were retrieved. A final GitHub branch read still names the reviewed SHA. Its delta contains **8 production files** plus a historical verification document. **445 staged production blobs** match the candidate tree exactly; lane-specific import/dependency manifests verify additional executed inputs. These overlapping counts measure source identity, not depth of review of every staged file. No repository test files or historical audit/generated results were adopted as correctness evidence. Authored offline probes execute current production methods with isolated collaborators and explicitly selected schedules/failures.

The user's **701 passing tests** are reported evidence; that suite was not independently rerun here. The local-working-tree-clean claim is not visible through GitHub reads. There were no production edits, Git writes, controller/broker/vendor contacts, field actuators or drone dispatches. Numerical water values are isolated scientific fixtures, not measurements of field delivery. No claim of field safety, installed interoperability, prospective forecast skill or complete monograph implementation follows.

Normative inputs are the R3 monograph and the unchanged master repair plan, execution addendum and package task register. The supplied R3 PDF SHA-256 is `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; its scientific register has 153 requirement IDs. All three normative plan blobs match the candidate tree and are unchanged from parent. The task register contains **52 unique full-acceptance rows, all open, zero checked**, with all 52 master cards represented. This is register integrity, not proof that all 52 packages are defective or unimplemented.

## Supplied R01–R12 corrections

“Fixed” means the specified original reproduction and retained controls passed in this bounded execution. It does not close an entire F/T package. Prior-review R identifiers, master-plan F/T package IDs and monograph AB/AW requirement IDs are distinct namespaces.

| Prior topic | Current observed result | Disposition |
|---|---|---|
| R01 concurrent resource admission | Delayed B claims after A's full ACK: 2 STARTs, both EXECUTING, both processes exit 0. | **Open, P1.** Locked STARTING check is an improvement but depends on an earlier hardware snapshot for EXECUTING exclusion. |
| R02 refused NEW cuts off OLD | Competing NEW is STOP_REQUESTED with no START; polling NEW leaves OLD running. | Original foreign-owner cutoff control fixed. This does not resolve R01. |
| R03 query-only fault latch | First query FAULT latches ERROR; unanswered query retains ERROR; new START refused. Callback-origin and STOP controls retained. | Original and bounded adjacent cases fixed. No new protocol failure demonstrated. |
| R04 stale recovery mutual exclusion | Earlier replacement schedule now has maximum 1 critical-section owner. | Original two-owner failure fixed; narrower availability gap FC02 remains. |
| R05 scoped/CAS generation | A→B→A warm/cold/control 448.11 mm; interrupted global head 4→5, next B6; legacy A retained after B. | Original cases fixed. Recovery response/load sequence semantics remain inconsistent, FC03. |
| R06 rollback registry | Classified loser conflict; no undefined registry/null result; follow-up/control 201.15 mm. | Checked fix retained. |
| R07 duplicate weather order | Near-boundary rain/wind/temperature pairs and exact-tolerance rain block in both orders; safe duplicates confirm. | Original order-dependent examples fixed. Untested merge-provenance/partial-unit boundaries remain acceptance scope only. |
| R08 candidate expiry | Candidate18Z after expiry17Z blocks when planning12Z; valid16Z control confirms. | Original expiry gap fixed. Existing offset-aware start without expiry still accepts a past point candidate, FC05. |
| R09 weather units/alias | Equivalent2m/s and7.2km/h both give4.1mm/hr; alias and previous mph/knots controls retained. | Checked fix retained; no agronomic frost calibration inferred. |
| R10 immutable archive/schema | Malformed JSON, list root/metadata, invalid horizon and missing required field raise ContractViolation. Mutation, atomic publication and evidence-ID controls retained. | Original checked failures fixed. |
| R11 quantiles/evidence | Equal aliases no longer reweight score; crossed/nonfinite/invalid distribution rejects. Most accepted aliases now yield equivalent metrics. | Alias weighting fixed; bare numeric-percent metric extraction remains partial, FC04. Independent target qualification is a known API acceptance limit. |
| R12 time/horizon/interval | Ordinary naive times and one-day labels0.01/2 reject; UTC/fixed offsets pass. Archive and base/posterior yield use1.28155σ. | Original checked failures fixed. Injected no-offset tzinfo cold round-trip edge FC06 is separate. |

## Reproduced remaining boundaries

| ID | Priority and plan scope | Evidence | Practical limit |
|---|---|---|---|
| FC01 | P1, F16–F18, Stage6 | Two actual OS workers send START to the same device/zone even when B claims only after A is durably EXECUTING. | Demonstrates duplicate command effects, not doubled measured water. |
| FC02 | P2, F39, Stage3 | Superseded recovery leaves empty primary; worker and fresh acquisition time out; aging31s restores access. | Maximum current owners remains1; no lost update or permanent deadlock demonstrated. |
| FC03 | P2, F09, Stage3 | Same recovered checkpoint returns sequence5 then2 on concurrent retry/fresh load; global head remains5 and next B6. | Receipt/field semantics inconsistency; no renewed global generation rollback or water-state corruption. |
| FC04 | P2, F24, Stage8 | Accepted `10/50/90` quantile keys score3 but lose RMSE/sharpness/coverage; canonical keys yield5/20/true. | Safe null handling, but available metrics disappear under an accepted equivalent representation. |
| FC05 | P2, F15, Stage5 | Candidate13Oct20Z confirms while planning starts13Oct23:00−12:00 (=14Oct11Z), without validity metadata. | Point-time versus daily-support policy is unresolved; no physical scheduling effect demonstrated. |
| FC06 | P2 input contract, F24, Stage8 | Injected tzinfo with `utcoffset()=None` stores/warm-reads, serializes naive, then cold-read rejects. | Controlled caller-type edge; ordinary naive-time rejection is fixed. |

These six rows are scoped contract observations, not six equally severe production incidents. Source-only TTL/release/restart concerns and previously known scoring/target qualification limits are listed separately; they are not inflated into additional reproduced failure counts.

### FC01: make resource ownership independent of earlier hardware snapshots

`resource_claim_probe.py` uses independent dispatcher/actuator instances, one quota file and an inert file-backed exclusive controller. Both OS processes sample truthful ONLINE before either START. In the decisive schedule, B's sampled reply is held until A has returned from submit with ACK and durable EXECUTING. B then calls the new real `claim_resource` with `live_executing=False`, so the existing EXECUTING owner is ignored. A second physical-send effect occurs. The ordinary simultaneous release also produced2STARTs in this run, but the delayed-after-ACK schedule makes the failure independent of the narrower in-flight STARTING timing.

The current transaction rejects a competing STARTING reservation for thirty seconds. Its EXECUTING/DISPATCHING branch is conditional on the caller's earlier `live_executing` Boolean. That Boolean cannot override newer authoritative ownership. A status query and a locked claim are both useful, but their composition must preserve resource uniqueness across the whole operation lifecycle.

Sources: [irrigation_runtime/dispatcher.py#L566-L596](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/dispatcher.py#L566-L596), [irrigation_runtime/safety.py#L1585-L1642](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/safety.py#L1585-L1642), [irrigation_runtime/safety.py#L965-L978](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/safety.py#L965-L978). Blob identities are recorded in the delta manifest. R3 focus: AB-EXE-002/003/004 and AB-ARC-008.

**Implement:** admit resource ownership, immutable operation envelope and budget exposure in one durable transaction or equivalent fenced protocol. An acknowledged or unresolved physical owner excludes conflicting admissions independently of a stale ONLINE snapshot. Declare device, zone and shared-pump capability explicitly. Use an owner generation on every subsequent update/release; keep uncertain STOP ownership until positively resolved. Define renewal/recovery of slow or crashed STARTING operations without treating TTL expiry alone as proof of physical stop.

**Acceptance:** preserve the new fresh-STARTING exclusion and require exactly one START for the delayed-after-ACK two-process schedule. Then qualify same-event retry, stale release, slow send beyond lease age, crash/restart, failed ACK/STOP and supported independent zones. Static review finds no owner-generation token, incomplete STARTING lifecycle integration and unsuccessful release before uncertainty classification; those are implementation acceptance concerns, not separately executed physical failures in this pass.

### FC02: finish recovery without leaving an ownerless primary lock

The current recovery detects supersession before B enters, repairing mutual exclusion in the earlier schedule. It has already replaced A's primary path with an empty descriptor, then closes that descriptor. Restoration only runs when the path is absent, leaving the empty path. A's release cannot match an empty owner token. B and a fresh acquisition raise TimeoutError; explicit mtime aging31s permits recovery.

Use a platform-supported interprocess ownership primitive or a checked takeover protocol that cannot unlink a successor's acquisition. Define token publication, recovery, release and rollback together. Acceptance must demonstrate both maximum owners1 and immediate post-release availability under this schedule while retaining process nonce/replay, strict rollback and single-cleanup controls. See the nonce appendix for exact hooks, current source lines and limits.

### FC03: distinguish immutable checkpoint sequence from publication generation

Recovery correctly advances global4→5, but returns a modified record copy with `sequence=5` while the immutable checkpoint file remains at2. A simultaneous identical retry, a fresh load and later retry return2 for the same checkpoint. The next independent publication reaches6. Both scientific payload and scoped pointers agree.

Keep immutable checkpoint sequence/identity separate from committed publication generation. Persist a publication receipt or scoped head metadata, and expose stable defined fields on first recovery, idempotent retry and load. Acceptance must preserve4→5→6, immutable checkpoint bytes and idempotence while readers agree on the meaning/value of the published generation. Sources: [world_model/canonical_worldline.py#L251-L274](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/canonical_worldline.py#L251-L274), [world_model/canonical_worldline.py#L343-L379](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/canonical_worldline.py#L343-L379). R3: AB-ARC-008 and AB-DAT-012.

### FC04–FC06: normalize forecast and time support once

For quantiles, reuse one accepted level parser/map in validation, finite-grid scoring and metric extraction. Bare numeric-percent keys are divided by100 in validation/scoring but not in the evaluator's plain numeric branch. Keep equal-alias deduplication and conflicting-alias rejection. Acceptance requires all accepted encodings to produce identical supported fields. Source: [world_model/forecast_archive.py#L203-L244](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/forecast_archive.py#L203-L244), [world_model/forecast_archive.py#L668-L701](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/forecast_archive.py#L668-L701). R3: AB-ML-005/010.

For scheduler time, declare whether a row is an actionable instant or a daily support interval. Normalize planning start and candidate support before comparing the horizon, even when `valid_until` is absent. A point candidate must not precede planning. A daily support interval needs explicit timezone/bounds before reducing output to a date. Retain the repaired same-day expiry and valid candidate controls. Source: [layer8_prescriptive/scheduler.py#L82-L107](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/layer8_prescriptive/scheduler.py#L82-L107), [layer8_prescriptive/scheduler.py#L369-L406](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/layer8_prescriptive/scheduler.py#L369-L406). F15 maps to AB-DEC-003, AB-ECO-003 and AB-EXE-001.

For forecast timestamps, require non-null effective `utcoffset()` as well as non-null `tzinfo`, then normalize/validate before publication and prove cold round-trip. The custom tzinfo fixture is deliberately injected; do not describe it as an observed deployment timezone. Preserve UTC/fixed-offset, ordinary-naive rejection and horizon consistency. Source: [world_model/forecast_archive.py#L349-L362](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/forecast_archive.py#L349-L362), [world_model/forecast_archive.py#L416-L417](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/forecast_archive.py#L416-L417), [world_model/forecast_archive.py#L555-L590](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/forecast_archive.py#L555-L590). R3: AB-DAT-011, AB-ML-008/010.

## Detailed implementation order and completion evidence

This is a bounded corrective sequence within the existing addendum, not a replacement 52-package program or a new remaining-hours estimate.

| Slice | Concrete work | Required completion evidence | Parallelism |
|---|---|---|---|
| 1 — Stage6 resource owner | Fix FC01 admission; define exclusive resource capability, canonical immutable envelope, owner generation and durable uncertainty phases. Integrate claim/release/status/reopen/restart under that contract. | One START under delayed B after A ACK; valid same-event replay; no foreign-owner stop; no quota/monitor release on unresolved outcome. | Runtime owner; other slices can proceed independently. |
| 2 — Stage3 lock recovery | Fix FC02 ownership takeover/token publication; reject retirement of a successor's lock; preserve strict ingress rollback. | Maxowners1 and post-release fresh acquisition without stale grace; distinct nonces persist; same nonce has one winner; crash and failed evidence retries remain valid. | Separate security owner. |
| 3 — Stage3 publication receipt | Fix FC03 field contract with durable publication receipt; preserve scoped CAS and immutable checkpoint records. | First/concurrent recovery, retry and cold reader agree on published generation; global4→5→6; A→B→A and same-scope loser controls retained. | Separate state-persistence owner. |
| 4 — Stage8 forecast normalization | Fix FC04 accepted alias parity and FC06 aware-time round-trip through shared normalizers. Keep schema corruption and immutable publication checks. | Identical metric fields for every accepted alias; accepted time types survive cold read; invalid types reject before publication; no observation borrowing. | Forecast owner independent of actuation. |
| 5 — Stage5 schedule support | Fix FC05 start/candidate support semantics; qualify duplicate merge provenance, partial fields, gust-only unit conversions and validity/version intersection. | Past point candidate rejects; daily support handled explicitly; repaired expiry/permutation positives and negatives remain invariant. | Prescriptive owner; merge extensions need their own executed receipts. |
| 6 — Integrated package gates | Run required supported-image regressions and independent process acceptance after the contract changes. Reconcile receipts to exact package criteria before changing task register. | Evidence for every gate being closed, not only a larger suite total; commissioning/field prerequisites remain explicit. | Coordinate after each affected slice is stable. |

Do not claim Stage6 acceptance from a single starts==1 schedule: a competing claim may be refused while another dispatch is STARTING yet still enter after that owner ACKs. Likewise, do not close F09 from global-head monotonicity alone when returned generation semantics differ. Preserve repaired examples alongside the new counterexamples so corrections cannot regress earlier safety/scientific behavior.

## Known acceptance limits retained without rediscovery

The direct forecast API still checks opaque evidence-ID syntax rather than independently verifying variable/unit/spatial/temporal/role/domain support. A deployed upstream resolver could provide such a contract, but that binding was not established here. Numerical scores are not independent validation authority by themselves.

The finite quantile pinball-grid average is still named CRPS. It is a declared finite-grid score, distinct from analytical Gaussian CRPS; a different value across those constructions is expected. F24 should label levels/weights or implement documented integration before comparing/calibrating across representations. The corrected Gaussian P10/P90 multipliers do not close that separate plan criterion.

The scheduler's first-row provenance/validity merge and gust-only unit reset require additional executed acceptance. Those observations are static scope notes; the167 current decision groups did not demonstrate new failures for them. Controller vendor interpretation, qualified reset, full restart/debounce and field calibration are also outside these finite simulated receipts.

ASMAE cache, bootstrap and other unchanged package slices were not broadly rerun in this candidate pass. Their earlier reported repairs are not newly certified here. The master plan's complete original estimate2,564–4,540hours is not a remaining-work estimate; this report assigns neither a fabricated completion percentage nor new program hours.

## Package and monograph alignment

| Package focus | Addendum stage | Current review contribution |
|---|---:|---|
| F08/F09 | 3 | Scoped continuity, cold replay, CAS loser and generation controls pass; FC03 receipt semantics remain. |
| F39 | 3 | Earlier mutual exclusion/rollback controls pass; FC02 recovery availability remains. |
| F15 | 5 | Original finite/unit/envelope, duplicate-boundary and expiry cases pass; FC05 time-support qualification remains. |
| F16/F17/F18/F19 | 6 | Protocol/fault and foreign-owner controls pass; FC01 concurrent exclusive admission remains. |
| F23/F24 | 8 | Immutable publication/schema/evidence-ID and original time/alias controls pass; FC04/FC06 and known qualification/scoring criteria remain. |
| F38 / T11 | 10 / 11 | Register/source identity checked; no fresh broad cache/authority runtime certification. |

The bundle contains the exact twelve selected master package cards, their literal requirement lists, a scientific requirement extract and the platform mapping for all R01–R12 focus topics. Cross-cutting requirement focus is recorded separately from literal card declarations. All52 FA rows remain open; no task status was changed.

## Reproduction and delivery

The accompanying bundle contains authored probe scripts, raw observations, source-object manifests, normative extracts, the six specialist appendices and a portable materializer. It excludes production source copies, repository tests, audit documents as source inputs, and simulated quota/controller/checkpoint stores. The complete report itself is a new independent review, not historical correctness evidence.

All **18 reproduction/verification scripts** were additionally executed from a separate reconstructed layout containing **922 verified source copies / 484 unique blobs**. Every script exited0, reproducing its expected controls and counterexamples. The replay validation records the actual commands, exit codes and reconstructed blob checks. Exit0 means observations, including counterexamples, were reproduced. It is not a production-pass total. The materializer reads exact Git objects into a separate workspace; it performs no fetch, checkout, production edit, commit or push. It was compiled/layout-verified, rather than executed here against a separate full Git checkout. Required Python dependencies and POSIX-only process/locking requirements are recorded in the bundle.


---

# Specialist appendix: Trajectory and hydraulic recovery

# Workstream C — fc82f14 bounded verification

Pinned source `fc82f14975cff7a90d15e21747ceb4fbc22a5457`, parent `e63a94280b03ed390ce5dd2be25190405bc7f953`. **The original scoped-CAS, registry-recovery, publication-generation and legacy-lookup counterexamples now pass.** One bounded adjacent schedule finds a P2 inconsistency in the sequence returned by recovery versus idempotent retry/load. The persisted global generation and scientific state pointers remain correct; this is not the previous generation rollback.

## Original fixes and controls

| Production case | Current result |
|---|---|
| R05 A→B→A warm/cold/control | **448.11 / 448.11 / 448.11 mm**, no conflict |
| R06 same-scope loser recovery | Expected **ConcurrencyConflictError**; no null result or undefined registry |
| Loser follow-up / normal cold control | **201.15 / 201.15 mm**, readings retained, both processes exit 0 |
| Original interrupted-generation case | Global **4→5**, next B **4→6**; orphan hidden before recovery |
| Original legacy-head fixture | A1 found before and after B; both scope entries retained |
| Independent full-scope writers | Both commit; B follow-up/control **439.45 / 439.45 mm**, no A event |
| Original registered-observation correction | **201.13 / 201.13 mm** warm/cold |
| Retained-weather and parameter controls | **122.75 mm** warm/cold/control; parameter retry same head/state |

The current recovery computes max(current head+1, orphan sequence), so the original global 4→2 and B 4→3 regressions are gone. Legacy index backfill walks the committed predecessor chain before the first scoped write, preserving A when B publishes. The legacy fixture remains explicitly an older-format head, not spontaneous loss of a modern valid index.

- [services/agribrain/world_model/canonical_worldline.py:357–379](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/canonical_worldline.py#L357-L379) — blob `ce943cc59c355715df18df76076aecfb9aed3812`.
- [services/agribrain/world_model/canonical_worldline.py:317–341](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/canonical_worldline.py#L317-L341) — blob `ce943cc59c355715df18df76076aecfb9aed3812`.
- [services/agribrain/world_model/canonical_worldline.py:413–428](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/canonical_worldline.py#L413-L428) — blob `ce943cc59c355715df18df76076aecfb9aed3812`.

## One adjacent recovery receipt seam

**C-R01 — P2; F09 stage 3; AB-ARC-008 and AB-DAT-012.** A controlled one-time failure occurs after orphan A2 is written at sequence 2 but before its head is replaced. B then advances the committed head to 4. Two recoverers submit the same A2 payload, synchronized at the real production save boundary.

| Observation | Sequence |
|---|---:|
| First recovered publication response | **5** |
| Concurrent idempotent response for the same A2 ID/payload | **2** |
| Load through a fresh service instance | **2** |
| Later identical retry | **2** |
| Persisted global head after recovery | **5** |
| Next B publication | **6** |

Both recoverers succeed without errors and return the same checkpoint identity/scientific payload. Their sequence fields differ because the recovery branch returns a modified copy with sequence 5, while the immutable stored record remains at 2; the idempotent and load branches return that stored record. Repeating A2 after B publishes preserves the global head and both scoped pointers. No water-state corruption or global-generation regression is claimed. This is a low-severity response/field-semantics seam requiring a clear checkpoint-sequence versus publication-generation contract.

Concrete fix: keep immutable checkpoint identity/sequence separate from durable publication generation. Persist the latter in a publication receipt or scoped head metadata and expose consistent defined fields on first recovery, retry and load. Acceptance: the same controlled schedule preserves global 4→5→6 and immutable records while both recoverers and a restarted reader agree on the published generation; idempotent retries do not advance it.

- [services/agribrain/world_model/canonical_worldline.py:251–274](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/canonical_worldline.py#L251-L274) — blob `ce943cc59c355715df18df76076aecfb9aed3812`.
- [services/agribrain/world_model/canonical_worldline.py:343–379](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/world_model/canonical_worldline.py#L343-L379) — blob `ce943cc59c355715df18df76076aecfb9aed3812`.

## Harness and acceptance qualification

The fault is injected once at the isolated head-file replacement boundary. Real checkpoint writing, B publications, orphan recovery, idempotence and fresh-service loading run unchanged production methods. The two recoverers share a barrier only to establish the interleaving. The legacy input is explicitly synthesized from the older supported head shape; its immutable checkpoint bytes remain intact. No external repository results or old generated artifacts substitute for current execution.

Same-scope conflicting successors still produce one accepted successor and one real scoped CAS conflict; identical retry returns the same record in ordinary publication, retry after another scope preserves the global head, and a different payload using the same ID rejects. Ordinary cold replay, equivalent dated-canopy daily/sparse replay, non-noon forward continuation, exact historical query, valid-ISO cancellation and withdrawal omission remain passing.

Independent scopes legitimately both commit under the repaired design. The B control therefore includes B's newly accepted first interval before comparing its follow-up. Both Worldline module aliases point to the same isolated test store, matching their common production default. Archived history rows without materialized WaterState are handled as archived data, not misclassified as source failures.

This finalization uses completed receipts only. The bounded review adds no further probes or untested static gap. All 23 supporting targets and four reused dependency blobs are verified against the current tree. Original R05/R06 and the two previous adjacent counterexamples receive passing credit. F08/F09 whole-package and master-plan R1 acceptance are not inferred from these finite controls; the remaining P2 is precisely scoped to recovery receipt semantics. No production/Git source, network service, vendor/controller or hardware was changed or called. All data-store writes were isolated simulated fixtures.

## Completed reproduction commands

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/trajectory/probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/trajectory/claim_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/trajectory/gate_probe.py new
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/trajectory/deep_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/trajectory/adjacent_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/trajectory/recovery_receipt_probe.py
```

Raw results, authored scripts, exact source/dependency manifests, and coverage.json accompany this report.



---

# Specialist appendix: Nonce ownership and ingestion

# Sensor nonce recovery — fc82f14

The previous two-owner critical-section counterexample is corrected in the selected process schedule. A narrower availability failure remains: a superseded recoverer can replace the active owner's primary lock with an empty file, detect that it lost recovery ownership, then leave that empty primary in place. The competing recovery and a fresh acquisition both time out until stale-lock recovery becomes eligible.

Pinned production security blob: `ee47ac23f33fde1e439ef60f641bb71705bee56d` at `fc82f14975cff7a90d15e21747ceb4fbc22a5457`. Ten imported production modules were independently verified against the current Git tree, including the reused layer0 sensor schema dependency. Earlier authored fixture code supplies the schedule only; results were freshly executed against the current production methods. No repository tests/audits, hardware, network service or production store was used.

## Repaired cases and retained controls

| Case | Fresh current observation |
|---|---|
| Same nonce, two OS processes | Exactly one accepted reading; durable nonce retained; fresh process rejects replay; all exits 0. |
| Distinct nonces, two OS processes | Both accepted and persisted; fresh process rejects repeated A; no lost update in this control. |
| Ten threads, same nonce | One winner, nine rejected. |
| Registry, calibration and pre-write raw-store failures | Failed attempt leaves no nonce/seen/raw evidence; restored identical retry accepts. |
| Interrupted primary/recovery owner | Two follow-up acquisitions succeed; no surviving recovery guard. |
| Earlier double cleanup schedule | One cleanup call; replacement accepted worker's nonce survives; later duplicate rejects. |
| Strict rollback I/O failure | `OSError` propagates; restored retry accepts. |
| Aged live recovery owner | B cannot take over A's guard; both serialize; maximum simultaneous primary owners 1. |
| Earlier stale-recoverer replacement schedule | Maximum simultaneous critical-section owners is now 1, rather than the earlier 2. |

## FC02 — P2 recovery availability seam

The final schedule seeds explicitly dead primary and recovery owner records aged 31 seconds. A pauses immediately before unlinking the recovery guard it found stale. B replaces that guard and pauses immediately before unlinking the primary lock after its owner-text equality check. A resumes its already-selected unlink, acquires the primary and enters the protected section. B then resumes its already-selected primary unlink and creates a replacement primary descriptor. B detects A's live recovery guard and refuses entry.

This new detection prevents the old second critical-section entry. However, the replacement primary is still empty: the owner token is written only after the acquisition loop exits, and this branch closes its descriptor and continues instead. The live-owner restoration writes a token only if the primary path is absent, so an existing empty path is retained.

Fresh observations in `actual-nonce-results.json#/stale_recovery_takeover`:

- A enters alone; B observes supersession and raises the real production `TimeoutError`.
- Both child processes exit 0 because the harness records the expected production exception.
- Primary contents are empty during supersession and remain empty after A completes.
- A separate fresh acquisition with a short bounded deadline also raises `TimeoutError`.
- Advancing that file's mtime to age 31 seconds allows acquisition again.

The aging is an explicit fixture operation, not a measured thirty-second wait. The production threshold is thirty seconds. This proves a recovery availability gap in the selected interleaving; it does not prove a permanent deadlock, a duplicate accepted message, two current critical-section owners or a lost telemetry update.

Source boundaries: `sensor_runtime/security.py:138–167` recovery-guard retirement/acquisition, `185–195` primary replacement, `203–230` superseded-owner handling, and `243–265` token publication/release. The production decision predicates are unchanged. Hooks block real filesystem calls and observe the actual liveness result only to select the interleaving.

## Concrete correction and acceptance

Use one durable ownership primitive whose recovery cannot retire a successor's lock. Prefer the supported platform's kernel-backed interprocess lock, or implement a checked generation/identity takeover with explicit owner-token publication and release semantics. PID liveness alone is insufficient to identify a particular acquisition. A superseded recoverer must not remove another owner's primary or leave an ownerless primary that survives successful owner completion.

Acceptance must keep maximum owners at 1 for the earlier aged-live and stale-replacement schedules, then show that a fresh acquisition succeeds after the legitimate owner releases without waiting for an artificial stale-file grace period. Preserve the same/distinct nonce process controls, single-cleanup replacement-owner control, strict rollback error and valid retry controls. Check normal acquisition, recovery, failure before token publication and release under one ownership contract; do not patch only the final empty-file condition.

This is Stage 3 F39 coverage. The exact master card and R3 mappings are retained in the platform appendix/selected package register; cross-cutting ownership focus includes AB-ARC-008 and typed provenance/missingness requirements. F39 full acceptance remains open. Source staging and these finite process controls do not qualify every deployment filesystem, OS or ingress/evidence transaction.

Reproduce with `PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/ownership/actual_nonce_probes.py`. Exit 0 means the controls and remaining counterexample match the recorded expectations, not that all production contracts pass.


---

# Specialist appendix: MQTT protocol and actuator faults

# R03 verification — fc82f14

**The query-first fault gap is repaired. The existing sticky-latch, START contradiction, STOP/fence and callback cleanup controls remain effective. No additional R03 failure was demonstrated in this bounded pass.**

Executed source: `fc82f14975cff7a90d15e21747ceb4fbc22a5457`, parent `e63a94280b03ed390ce5dd2be25190405bc7f953`. The five executed core production modules independently match the supplied Git tree (`source-index.json`). All results were freshly generated; earlier scripts served only as harnesses. Repository tests, audits and prior results were not adopted as correctness evidence.

## Original fault-origin case

The real dispatcher/actuator/MQTT path receives a correlated `FAULT/running=false/stopped=true/fault_code=7` reply for its first predispatch query. The event becomes FAILED, the driver becomes ERROR, and the fault latch is now true. A subsequent public query receives no reply: it returns ERROR and retains the latch. A second event submission is FAILED before any additional query or START publication. No reset is performed.

This reverses the earlier exact-source counterexample, in which query-only FAULT never set the latch and a later timeout enabled START. Fresh evidence is `r03_adjacent_results.json#/query_only_fault_then_timeout`; the publication sequence now contains only the original fault query and the explicitly forced unanswered query.

Current implementation: status callbacks latch faults before correlation at [`mqtt_driver.py:257–272`](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L257-L272), telemetry callbacks do likewise at [`274–284`](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L274-L284), and the decoder also sets the latch at [`507–511`](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L507-L511). Query publish failures and timeouts retain ERROR while latched at [`578–600`](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L578-L600). Independent command guards remain at [`actuator.py:210–213`](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/actuator.py#L210-L213) and [`dispatcher.py:504–532`](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/dispatcher.py#L504-L532).

## Bounded adjacent callback sequence

One sequence was exercised through each ingress: uncorrelated status/heartbeat and telemetry. First, a positive START reply establishes an active command. Then a `FAULT` packet with contradictory `running=true/stopped=true` flags arrives through the selected callback. Both variants produce the same safe separation:

- Health becomes ERROR and latched; the original running command remains owned. The fault packet is not treated as positive physical stop evidence.
- A query timeout and then a query publish exception both retain ERROR, the latch and the original command, with no pending ACK slots left behind.
- Another START is rejected with VALIDATION_FAILED and zero publications.
- A correlated positive STOP succeeds and clears the stopped command while retaining ERROR and the health latch.
- Replaying the already-consumed healthy START ACK does not clear the latch or recreate ownership.

Evidence: `callback_origin_probe.py` and `callback_origin_results.json`. These are local callback fixtures, not claims about controller replay behavior in the field.

## Acceptance matrix

| Control | Fresh outcome | Assessment |
|---|---|---|
| Query-first FAULT → unanswered query → new submission | Latch true; ERROR retained; second event FAILED; no new publications | Original gap repaired |
| Previously set latch → healthy query / timeout → direct and dispatcher START | ERROR retained; direct validation failure and dispatcher failure; no new publications | Previous repair retained |
| Contradictory START word/flags | CONTRADICTORY_STATUS; uncertain command retained | Previous repair retained |
| START-origin FAULT → timeout → another START | Latch persists; START blocked | Previous repair retained |
| Clean STOP while fault-latched | STOP succeeds; command cleared; ERROR/latch retained | STOP remains available |
| Direct, late-fence and dispatcher stopped-FAULT controls | ERROR retained; confirmed-stopped ownership cleared; dispatcher stopped receipt present | Prior DV04 controls retained |
| Failed normal STOP / second late-fence STOP | ERROR and original delivery command retained; late result STOP_FAILED | No false stop certification |
| Actual pending-map pop interleaved with cancellation | Callback returns without KeyError; map empty | Prior DV03 race repair retained |
| Older cancelled Future sharing an explicit correlation ID | New STOP Future survives and receives ACK | Identity cleanup retained |
| Worker-thread callbacks, asyncio debug off/on | Loop-owned Future completes without callback exception | Thread completion retained |
| Three-method cancellation / publish exceptions | Pending ACK slots cleaned | Lifetime controls retained |
| Stale/late unmatched ACK | Does not certify a current query | Freshness control retained |
| Representative boolean/timeout helpers | Nonfinite flags become unknown; timeout helper output finite and positive | Helper controls retained |
| Adjacent status/telemetry contradictory-fault sequence | Health retained independently of ownership; positive STOP required | Both ingress variants pass |

`acceptance_matrix.json` records 18 verified control assertions. The fresh raw matrix contains 71 original rows and 40 extra command rows; these counts are observations, not a blanket pass count for every possible protocol input.

## Requirements, limits and remaining contract work

This is bounded Stage 6 coverage for F17 operation state, F18 uncertainty/reconciliation and F19 fault protection/reset. R3 section 183 (lines 484–488) and AB-EXE-002/003/004 (1110–1120) require acknowledgement, physical execution, uncertainty and safety permissions to stay distinct. The R3 input SHA256 is `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`. Master cards are `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:575–652`; this pass does not certify their complete acceptance criteria.

Bare OK still permits START/EXECUTING with command ownership retained. Its vendor meaning remains a contract question, not demonstrated physical delivery. No public qualified fault-reset operation was identified in the selected runtime, and these probes perform no manual private-attribute reset. Full reset/restart/debounce acceptance and commissioned controller semantics remain separate work. The raw harness preserves scoped supplemental API-boundary observations; this bounded R03 pass does not newly adjudicate them or claim universal malformed-input acceptance.

All publications and replies are in-memory fixtures. No paho/broker lifecycle, physical controller, measured flow, delivered volume, repository tests or audit claims were used as proof. Invalid timeout integration rows are bounded by a 25 ms harness deadline; finite helper output is checked separately. Resource claims, TTL/nonce behavior and telemetry qualification are separate review lanes.

## Reproduction

From `/workspace/scratch/de6bc2428cec`, run in order:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/protocol/verify_source.py
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/protocol/protocol_matrix.py
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/protocol/boundary_probes.py
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/protocol/fault_reset_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/protocol/r03_adjacent_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/protocol/callback_origin_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-fc82f14-review/protocol/collect_evidence.py
```


---

# Specialist appendix: Forecast archive and scoring

# Workstream D — exact fc82f14 archive and yield review

Reviewed **`fc82f14975cff7a90d15e21747ceb4fbc22a5457`**, parent `e63a94280b03ed390ce5dd2be25190405bc7f953`.

The original schema-corruption, equal-alias score weighting, ordinary naive-time and one-day horizon 0.01/2 cases are **fixed in this run**. Uppercase, decimal and explicit-percent quantile metrics now work; yield production uses the correct P10/P90 multiplier. Retained publication, snapshot, finite-score, evidence-ID and retry controls continue to pass. **This is not an all-R10–R12 or whole-F24 sign-off:** the already tested bare numeric-percent metric case remains incomplete, independent target/support qualification is still unimplemented at this API, and sparse-score naming remains unresolved. One bounded injected timezone case also exposes a warm/cold round-trip gap.

## Evidence and reproduction

`probes.py` completed **25 case groups**: all 24 earlier case definitions freshly rerun against this exact source, plus **one** bounded adjacent group covering level equivalence, stored schema, aware time and the yield producer/archive adapter. No further probe expansion was performed. `results.json` contains the complete current execution; `source-receipts.json` records hashes for **37 imported staged production blobs** plus **two exact-commit dependency blobs**.

The shared staged subset omitted `services/agribrain/crop_database/{__init__.py,registry.py}`. For the requested producer invocation, those two files were fetched at this exact commit into `ledger/dependencies/crop_database` and matched the Git-tree blobs `462a82e514f8a954ebf8a53748313c18fae842d3` and `17aef77d0a0cdbaee919644b6715bc1d0c5703bb`. No shared source was changed. The yield target blob is `22bc95df4eee397792089c59e949e213c903ad7d`. All archive/import receipts are in the JSON artifacts.

Reproduce with Python 3.12 and NumPy/Pandas available:

```bash
python /workspace/scratch/de6bc2428cec/repair-fc82f14-review/ledger/probes.py
```

Keep the sibling exact `source` tree and `git-tree.json`, plus the two dependency files at the paths above. The script validates dependency/core hashes before import, all imported staged hashes before receipt publication, disables bytecode writes and allocates a fresh `ledger/isolated` archive directory. Previous script definitions were reused as scaffolding; previous results or audit artifacts are not correctness evidence.

All runtime evidence is from production functions with isolated local files and selected thread schedules, one injected link error, a controlled child exit, injected existing-file corruption and an injected custom timezone. The child exit during serialization is **not** power-loss durability testing. Invalid caller JSON/type exceptions are separate from that process interruption. There were no production edits, Git writes, repository tests/audits, deployed pipeline/controller calls or hardware interactions. The only remote reads were the two exact-SHA source dependencies.

References below abbreviate `source/services/agribrain/world_model/forecast_archive.py` as **FA**, and `source/services/agribrain/layer6_yield/yield_forecast.py` as **YF**, under this review root.

## Precise repair matrix

| Area | Result on fc82f14 | Exact current source |
|---|---|---|
| R10 evidence identity / retry | Former `['A:B','C']` vs `['A','B:C']` collision stays fixed. Reordered/repeated evaluations yield one ID/cache/disk entry; observation/time changes remain distinct. | FA 640–651, 715–741 |
| R11 syntax / distribution | Blank, None and scalar evidence rejects. NaN/crossed/illegal/conflicting-alias quantiles reject before publication. Qualified independent evidence support remains the known API limit below. | FA 369–409, 640–656 |
| R12 original time/horizon | For a one-day interval, horizons 0.01 and 2 now each raise `ContractViolation`; ordinary naive origin/target raises too. UTC and UTC+02:00 controls succeed. The injected no-offset timezone case below is distinct from these repaired originals. | FA 349–362 |
| Stored schema corruption | Injected malformed JSON, top-level `[]`, list metadata, invalid horizon and missing required `plot_id` all raise `ContractViolation`. Prior schema-as-absence cases should be closed. | FA 555–590 |
| Equal aliases | Adding equal `0.5:10` to `p50:10` leaves the score at 3.0; conflicting values reject. Prior alias weighting failure should be closed. | FA 203–244, 372–409 |
| Metric normalization | Uppercase P10/P50/P90, explicit 10%/50%/90%, decimal 0.1/0.5/0.9 and canonical p keys give the same RMSE 5, sharpness 20, coverage true. Bare numeric-percent strings remain incomplete below. | FA 668–701 |
| Gaussian/yield interval convention | Archive uses 1.28155σ. Base and single-branch posterior wheat producer return mean 4.5, P10 3.92, P90 5.08, matching the rounded expected endpoints for σ=0.45. | FA 703–709; YF 104–131, 224–244 |

The bounded producer check invokes the real base/posterior yield functions, then uses an **explicit local field adapter** to construct archive records. At observed yield 5.175, both producer-quantile and equivalent Gaussian records return RMSE 0.675 and coverage false. Widths differ by expected two-decimal endpoint rounding (1.16 versus 1.153395). Finite-grid versus analytical score values differ as expected; this does not validate field calibration or a deployed integration path. The producer's existing eligibility fields were observed, not used to certify crop or evidence authority.

## Retained regression controls

| Current case group(s) | Actual result |
|---|---|
| `original_conflict_retry` | Replacing committed mean 1 by 99 fails twice, bytes remain unchanged, warm/cold remain 1; observation 99 gives RMSE 98. |
| `original_valid_record_process_interruption`, `original_inflight_reader_and_identical_writer` | Exit 83 during temp serialization leaves no final record; retry succeeds. Reader sees no partial final while paused; identical competing writer and resumed writer both succeed. Crash orphan temp remains inert. |
| `conditional_link_incompatible`, `conditional_link_identical`, `injected_link_failure_cleanup` | One incompatible winner; both identical writes succeed; normal temps cleaned. Injected link failure leaves no final/temp/cache and permits retry. |
| `original_mutation_during_and_after_store` | Caller P50 mutation 1→99 after ingress snapshot and retrieved-copy mutation do not alter committed, warm/cold or evaluated prediction. RMSE against 99 remains 98. |
| `original_serialization_failure_isolation`, `typed_distribution_and_metadata_json_boundary` | Unsupported set metadata and nonfinite metadata reject without final/cache; cleanup and corrected retry work. Nested zero metadata remains zero. Invalid caller type outcomes are described separately below. |
| `original_evidence_order_cache_and_precision`, `idempotent_cache_repeated_evaluation`, `evidence_signature_colon_ambiguity_failure_isolation`, `nonempty_evidence_guard_semantics` | Canonical order/retry/precision, colon separation and typed nonblank syntax pass. Three identical/reordered retries produce one cache and one disk record. |
| `finite_crps_and_pointmass_controls`, `original_nonfinite_targets_means_horizon_and_temporal_guards`, `quantile_validation_at_archive_vs_evaluation` | Empty quantiles, nonfinite observed/mean/sigma, negative sigma, malformed/crossed quantiles, nonfinite/gross horizon and pre-target evaluation reject. Valid σ=0 at truth scores 0, error 2 scores 2; valid N(10,1) at 10 scores 0.23369497725510913. |
| `distribution_presence_precedes_temporal_guard`, `original_unavailable_score_json` | Missing distribution rejects before temporal checks. P90-only forecast at observation 77 gets finite-grid score 4.6 while RMSE/sharpness/coverage stay JSON null; no observation-filled P50 or nonfinite JSON. |
| `quantile_coverage_convention_same_normal` | Gaussian and exact standard-normal P10/P50/P90 representation both classify observation 1.5 outside the central 80% interval. |

The source mechanisms are FA **30–58** (complete temp then conditional link), **483–531** (snapshot/validate, durable before cache, defensive copies), **539–590** (cold/warm reader) and **732–741** (durable evaluation before deduplicated cache append). These controls substantiate the checked F23 mutation/conflict/concurrency criteria without claiming every scheduler or filesystem has been exercised.

## Remaining findings and acceptance

### D-FC-01 — accepted bare numeric-percent levels still lose median and interval metrics

**Preserved original metric-field gap, narrowed by the successful repairs.** `canonical_quantile_level_equivalence` stores `{'10':0,'50':10,'90':20}`. Its score is correctly 3.0, but RMSE/sharpness/coverage are null. Canonical p keys, equal median aliases, uppercase keys and the bounded `%`/decimal controls yield 3.0 / 5 / 20 / true for the same levels and values.

The validator and score parser divide bare numeric levels greater than 1 by 100 at FA **210–214**, **385–390**. The evaluator's plain numeric branch at **678–680** does not, so its normalized map contains 10/50/90 instead of 0.1/0.5/0.9. Null is safe missingness handling, but these specific metrics are present under an accepted encoding and should not disappear.

**Acceptance:** reuse one canonical level parser/map in validation, scoring and metric extraction; every accepted representation above must produce identical supported metric fields. Preserve equal-alias deduplication and conflicting-alias rejection. F24 plan **770–779**, task `ST08-F24-04` **1127–1131**; R3 AB-ML-005 **990–992**, AB-ML-010 **1010–1012**.

### D-FC-02 — injected timezone without an offset passes ingress but fails cold round-trip

**Adjacent controlled injection; original ordinary-naive rejection is fixed.** The one bounded group uses a custom `tzinfo` object whose `utcoffset()` returns `None`. The current check only tests that `tzinfo is not None` (FA **351–352**). With both endpoints carrying that object, construction and durable store succeed; warm read succeeds. ISO serialization omits the offset (FA **416–417**); cold `fromisoformat` reconstructs ordinary naive times and the new validation rejects them as corrupt (FA **572–590**).

UTC and fixed UTC+02:00 round-trip successfully. This demonstrates a constructor/serialization contract edge for an injected caller type, not an observed deployed timezone or a regression of the repaired normal-naive case.

**Acceptance:** require both `tzinfo` and effective `utcoffset()` to be non-null, validate/normalize to a canonical aware representation before publication, and require accepted forecasts to round-trip cold. Preserve the passing UTC/fixed-offset, original naive and horizon mismatch controls. F24 plan **770, 778**, task `ST08-F24-01` **1109–1113**; R3 AB-DAT-011 **699–701**, AB-ML-008 **1002–1004**, AB-ML-010 **1010–1012**.

### D-FC-03 — retained independent-target qualification limit

**Known unimplemented API limit, not newly rediscovered.** `invalid_support_metadata_binding` still accepts a syntactically valid opaque evidence ID and emits numerical metrics with `in_domain` / `observation_space` defaults (FA **446–447**, **719–730**) despite arbitrary metadata declaring different support/domain/role. The function checks ID syntax (FA **640–651**), not a typed variable/unit/spatiotemporal/role/independence receipt. Such metadata is not a verified receipt either. No deployed resolver/caller or real unsupported evidence was exercised.

**Acceptance:** bind evaluations to independently qualified target receipts or verify an upstream checked binding contract; unsupported/unqualified targets retain unavailable/unknown status. Preserve valid zero observations and the passing evidence syntax/identity repairs. F24 **771, 779**; R3 AB-DAT-007 **683–685**, AB-DAT-009 **691–693**, AB-ML-005 **990–992**, AB-ML-010 **1010–1012**, AB-ASM-016 **836–838**. R11 therefore remains partial on qualification while its syntax/distribution fixes pass.

### D-FC-04 — retained finite-grid score naming convention

**Known F24 step still incomplete; Gaussian and interval repairs pass.** FA **187–196** continues to call the unweighted finite pinball average at **236–244** CRPS. For standard normal at observation 1.5, analytical Gaussian CRPS is 0.9944240039774529 and the three-level grid score is 0.8165058317095463. The numerical difference is expected from those different scoring constructions; it is not a defect in the positive Gaussian control.

**Acceptance:** label the finite-quantile score with its levels/weights or implement a documented CRPS integration rule, then report calibration by declared variable/domain/horizon. Retain the now-correct archive and both producer multipliers. F24 **773, 779**, task `ST08-F24-04` **1127–1131**; R3 AB-ML-005 **990–992**, AB-ML-010 **1010–1012**.

## Input-type limits and plan coverage

Direct malformed caller types still produce mixed exceptions: quantiles `None` reaches `TypeError`, metadata list reaches `AttributeError`, and empty list/string quantiles can serialize as `{}` while the tested valid mean=0/std=0 distribution remains present. Rejected cases publish no final/cache entry. This is a typed-input consistency follow-up, not demonstrated false skill credit. A wholly absent distribution can still be archived but its evaluation rejects explicitly; no numeric score was observed for it.

Master-plan references are `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`: F23 **730–753**, F24 **755–779**; Stage 8 is `AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md` **36**. Task references use `AgriBrain_Work_Packages_Task_List_2026-10-07.md` **1069–1139**. The master plan **134** gates new training/evaluation artifact creation on F21–F24; this bounded pass does not certify those dependencies or all Stage 8 work.

Normative references use the supplied `current-plan-review/R3_current_scientific_sections.txt`: F23 maps to AB-DAT-011 **699–701**, AB-ARC-007 **746–748**, AB-ARC-008 **750–752**, AB-ASM-014 **828–830**; F24 maps to AB-ML-005 **990–992**, AB-ML-010 **1010–1012**, AB-ASM-016 **836–838**. AB-DAT-005 **675–677** supports the preserved zero/missingness controls. No prospective-versus-reconstruction, field calibration, promotion, actuation or machine-authority conclusion follows from these archive receipts.


---

# Specialist appendix: Prescriptions and hard envelopes

# F15 actual-source review at fc82f14

The previously reproduced near-threshold duplicate permutations and same-day candidate-expiry failures are corrected at `fc82f14975cff7a90d15e21747ceb4fbc22a5457` (parent `e63a94280b03ed390ce5dd2be25190405bc7f953`). The checked R07/R08 repairs pass while their valid controls remain usable. Full F15 completion is not established by this bounded pass.

All 167 existing focused groups were freshly rerun against actual production code. There were no production exceptions. All 30 source manifest entries, covering 29 unique files, match the current pinned Git tree; old dependency copies are used only after this verification. No new scenarios were added. No repair models, repository tests/audits, production/Git changes, network/services or hardware were used.

The composition fixtures use actual ActionCards with two independent evidence families and execute the actual drift/scheduler/final invariant functions. Four actual raw `run_layer8` cases also run. Raw L8 shadow output and modifier output do not establish top-level authorization or physical execution.

## Repairs confirmed

| Reproduction/control | Current actual result |
|---|---|
| Rain 0.49/0.51 mm, wind 14.9/15.1 km/h, maximum temperature 37.9/38.1°C and minimum temperature 5.1/4.9°C duplicates | Both orders BLOCKED. |
| Rain 0.25/0.75 mm, exactly at the previous conflict tolerance | Both orders BLOCKED. |
| Identical zero-wind duplicates, both-safe rain duplicates, equivalent-unit wind duplicates | CONFIRMED. |
| Planning 12:00Z, candidate 18:00Z, validity ends 17:00Z on the same day | BLOCKED. |
| Planning 12:00Z, candidate 16:00Z, validity ends 17:00Z | CONFIRMED. |
| Equivalent next-day candidate 18:00Z after validity 17:00Z | BLOCKED. |
| Earlier already-expired daily row and malformed-validity examples | Remain BLOCKED. |
| DV15 invalid recommendation/cap, DV16 actual modifier below original minimum | Remain BLOCKED with retained reasons. |
| R09 equivalent 2 m/s versus 7.2 km/h frost wind, and temperature alias | Both rates remain 4.1 mm/hr; alias produces the frost card. |
| Whole-run numeric-string temperature control and earlier date/finite/weather controls | Corrected behavior is retained without exceptions. |

Source: `services/agribrain/layer8_prescriptive/scheduler.py:174–236` evaluates normalized duplicate values and safety-boundary crossings; `238–250` constructs the numeric representative; `385–406` compares validity against `max(start_instant, candidate_instant)`. Scheduler blob: `7e50cf01277d1ced60cc6fbf927fc2dbab3c6dc7`.

These receipts close the supplied failures in the checked scope. They are stronger than merely matching the larger original rain/wind/temperature examples: the just-below/just-above action-limit cases now have order-invariant disposition, and valid duplicate controls still confirm.

## Existing receipt requiring an explicit time-support policy

The current `F15_TIME_start_offset_past_UTC` receipt still returns CONFIRMED for candidate `2026-10-13T20:00:00Z` when planning starts `2026-10-13T23:00:00-12:00`—which is `2026-10-14T11:00:00Z`. No `valid_until` is supplied in that fixture. Row timestamps are normalized to UTC, but the planning horizon begins from `start_date.date()` in its supplied timezone. Therefore the accepted candidate instant precedes the planning start, although its UTC date equals the start's local calendar date.

This is an unchanged review-priority P2 time-contract gap, not a regression of the repaired expiry comparison. The scheduler's public output is a date, while its input parser accepts precise instants. If inputs represent pointwise actionable slots, the candidate must not precede planning. If they represent daily support intervals, that interval and its timezone need to be explicit before reducing the result to a date. The bounded receipt does not establish a physical scheduling or actuator error.

Source: `scheduler.py:82–107` normalizes row instants; `start_d = start_date.date()` in the scan setup; `369–378` compares UTC candidate dates with the local start date. `max(start,candidate)` is applied only inside the optional declared-validity branch at 385–406.

Acceptance: put the planning interval and candidate support into one declared timezone/instant convention. Preserve the repaired expiry fixtures, then qualify offset-aware planning starts both with and without validity metadata. Do not label a past point candidate feasible merely because two calendar dates compare equal.

## Conservative merge acceptance not demonstrated by these receipts

Source review confirms that numeric extrema cover rain, speed, gust, maximum temperature and minimum temperature. The existing 167 groups exercise the repaired threshold crossings, equivalent speed units and safe duplicate controls. They do not establish every duplicate support/provenance permutation.

Two specific code boundaries remain to qualify before claiming complete merge convergence:

- `merged_row = dict(group[0])` retains date, expiry and version metadata from the first row (`scheduler.py:238–253`). The numeric representative combines group extrema, while no explicit validity/version intersection is constructed there. Runtime acceptance for differing duplicate validity/version metadata was not executed in this pass; this is not counted as a reproduced new failure.
- Gust values are normalized before merging, but the common unit is reset to km/h only when speed values exist (`242–246`). Gust-only mixed-unit/idempotence permutations need a focused acceptance receipt. They were not executed here and are not counted as confirmed runtime findings.

Concrete merge acceptance should cover permutations with partial missing fields, only-gust wind, all supported physical units, equivalent UTC offsets and differing validity/version metadata. The result should either resolve one qualified authoritative support or explicitly reconcile all contributors. Equivalent physical support must remain equivalent after merging and re-parsing.

## F15 master-plan disposition

F15 remains stage 5, dependent on F01/F06/F14, with R3 AB-DEC-003 (`R3_current_scientific_sections.txt:1076–1078`), AB-ECO-003 (`1088–1090`) and AB-EXE-001 (`1106–1108`). The original plan priority is P0; the P2 time-contract review qualification above is separate.

- `ST05-F15-01`: the supplied finite/unit/date and numeric duplicate safety examples pass. Complete typed support, timezone and merge provenance acceptance remains partial.
- `ST05-F15-02`: supplied missing-weather and invalid-envelope cases remain fixed.
- `ST05-F15-03`: supplied original upper/lower bound and invalidity cases remain fixed through the checked gates.
- `ST05-F15-04` / `ST05-F15-FA`: full acceptance remains open for complete support/time/merge convergence and the still-unverified legal/resource/aggregate-budget and commissioning criteria.

Artifacts: `actual_decision_probes.py`, `actual-decision-results.json`, `coverage.json`, `source-verification.json`, `probe-summary.json`, `probe-stderr.txt`. Source-only acceptance gaps are distinguished from the 167 executed receipts; no additional failed-case count is inferred from them.


---

# Specialist appendix: Resource-claim lifecycle and plan register

# Resource-claim lifecycle and normative-plan verification

Actual main: `fc82f14975cff7a90d15e21747ceb4fbc22a5457`, parent `e63a94280b03ed390ce5dd2be25190405bc7f953`. The new `claim_resource` introduces a real locked conditional check for a fresh STARTING operation before dispatch. This is an improvement over a read-only resource lookup. It is not yet a complete physical-operation lease: exclusion depends on the caller's earlier hardware snapshot and a fixed STARTING age, without renewal or fencing generation.

This lane is a bounded **static source/AST and normative-document check**. It performed no inert store, hardware, network, database, concurrent-worker or command-effect probe. The coordinator owns the delayed-claim, TTL and nonce reproductions. The limitations below qualify the existing resource-owner contract; they are not additional reproduced finding counts. All 445 supplied production source blobs match the exact new tree. No repository tests, audits, prior generated results, production edits or Git changes were used as correctness evidence.

## Current claim and release contract

| Boundary | Actual current code | Evidence and scope |
|---|---|---|
| Atomic claim | `safety.py:1585-1627` checks compatible device/zone reservations while holding the shared store lock, then changes the requesting reservation to STARTING and stores starting_ts/claimed_at. | Fresh in-flight admission now has a shared transaction rather than only a live query. No all-schedules success claim follows from the static check. |
| Fresh STARTING exclusion | `safety.py:1611-1615` blocks another STARTING record while its wall-clock age is below 30 seconds. | Conditional source protection is present. Age alone is not proof that a live delayed sender has stopped. No TTL takeover was executed in this lane. |
| Existing EXECUTING exclusion | `safety.py:1616-1618` blocks EXECUTING/DISPATCHING/STARTING only when caller live_executing is true. | The caller derives that Boolean from its earlier get_status result at `dispatcher.py:575-578`. An older ONLINE result can differ from a subsequently committed EXECUTING state. The coordinator's delayed-B-after-A-ACK case tests this schedule. |
| Claim renewal/fencing | One dispatcher claim call exists at line577; no renewal call or owner/generation argument is part of claim_resource. Persistent starting_ts is set at line1622. | No source mechanism shown here fences a stale sender after age-based admission of another event. Static closure gap, not newly demonstrated command duplication. |
| Release | `safety.py:1629-1642` changes the named event's STARTING to DISPATCHING and removes starting_ts. Supplied device_id and zone_id are unused; no expected owner/generation is checked. | This is per-event phase mutation rather than a fenced release of one specific lease attempt. A stale-call consequence was not executed here. |
| Failure ordering | `dispatcher.py:594-596` calls release_resource_claim for every unsuccessful dispatch result before later refused/uncertain classification. | The relationship between transport uncertainty and retained resource exclusion requires explicit lifecycle acceptance; this lane does not assert that every failed result represents physical delivery. |

Sources: [claim and TTL](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/safety.py#L1585), [release](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/safety.py#L1629), [pre-send claim and failure release](https://github.com/webClone/AgriWise/blob/fc82f14975cff7a90d15e21747ceb4fbc22a5457/services/agribrain/irrigation_runtime/dispatcher.py#L575).

The new lookup and claim predicates are not identical. The lookup includes STARTING/DISPATCHING/EXECUTING/VALIDATING or claimed=true (`safety.py:1574-1581`); claim_resource does not consult claimed, VALIDATING or STOP_REQUESTED. update_status explicitly makes claimed=false for STOP_REQUESTED and terminal phases (`safety.py:965-982`). Failed-stop reopening still reconstructs STOP_REQUESTED with conservative exposure. This is a policy mismatch to resolve against actual physical cessation and stop rights, not proof that every retained accounting record requires an exclusive running controller.

The resource key is device plus compatible zone, with an empty zone acting as a wildcard. The existing base actuator validation still excludes a foreign running operation at device scope. A declared controller/valve/zone/pump-group capability policy must decide whether distinct zones are independently executable. No same-device cross-zone physical failure is asserted by this static lane.

## Lifecycle writers and restart integration

The read-only inventory finds all **12 SharedQuotaStore methods** calling `_write_state`, including the new claim/release methods. Atomic quota admission remains event-bound and stores owner_token. Compatibility reserve and failed-stop reopen reconstruct records without preserving that token or the new claim timestamps/claimed metadata (`safety.py:816-944,1385-1521`). These writers retain many canonical target/delivery dimensions, but do not participate in one enforced resource fencing generation. Status/start/release/settlement methods likewise operate by event ID without an expected resource-owner generation. This is not an assertion that every method must independently authorize users, nor a demonstrated owner-forgery or accounting exploit.

STARTING is now a persisted resource phase but is not an EventStatus member in the current schema. Restart's existing other-owner scan recognizes DISPATCHING/EXECUTING/RESERVED/STOP_REQUESTED, omitting STARTING (`dispatcher.py:1730-1737`). Generic fallback paths may handle some records; this lane has not executed recovery of a crashed or delayed STARTING worker. Treat this as integration acceptance to verify, not a newly confirmed restart failure.

The resource contract should bind one declared exclusive resource, immutable event envelope and owner/fencing generation across claim, renewal, uncertain send, stop, release, reopen and restart. Required controls include fresh competing claims, delayed admission after a completed ACK, live slow START beyond the chosen lease interval, stale release, same-event retry, compatible independent zones, crashed-owner recovery and failed STOP. Existing hazard cutoff and conservative exposure must survive. These are one coherent F16–F19/R01 acceptance boundary, not separate counted defects.

## Current plan and R3 proof

| Normative document | Exact current/local Git blob | Parent |
|---|---|---|
| Deep Repair Plan | `08d378a65992de859369950599df198e64244f01` | unchanged |
| Execution Sequencing Addendum | `40751038dc8760e91bc3ab115e30c5e28395953a` | unchanged |
| Work Packages Task List / FA register | `8a564647af7e588802537817159117b349ff606b` | unchanged |

Fresh parsing finds **52 unique full-acceptance rows, all unchecked, zero closed**, covering exactly all 52 master cards. All 52 card requirement lists also match their direct normative master sections. These facts report the register and document identities; they do not independently prove all packages technically defective or deny verified narrow repairs.

R01–R12 remain local topic labels. Their requirement mappings were checked again against the current unchanged normative plans and the supplied R3 scientific sections:

| Topic | Canonical packages / full stages | Scientific focus |
|---|---|---|
| R01 | F16/F17/F18 / 6 | AB-EXE-002/003/004, AB-ARC-008 |
| R02 | F16/F17/F18/F19 / 6 | AB-EXE-003/004, AB-ARC-008 |
| R03 | F17/F18/F19 / 6 | AB-EXE-002/003/004 |
| R04 | F39 / 3 | AB-DAT-003/011/013, AB-ARC-008 |
| R05 | F08/F09 / 3 | AB-DAT-012/013, AB-ARC-008, AB-AGR-006 |
| R06 | F09 / 3; F38 / 10 | AB-DAT-012, AB-ARC-006/008 |
| R07 | F15 / 5 | AB-DEC-003, AB-ECO-003, AB-EXE-001 |
| R08 | F15 / 5 | AB-DEC-003, AB-EXE-001, AB-DAT-014 |
| R09 | F15 / 5; adjacent F06 / 3 | AB-DAT-007, AB-DEC-003 |
| R10 | F23 / 8 | AB-DAT-011, AB-ARC-008/009 |
| R11 | F23/F24 / 8 | AB-ML-005/008/010, AB-DAT-005/007/011 |
| R12 | F24 / 8 | AB-ML-005/010, AB-ASM-016 |

The JSON retains complete unmodified card lists and separately identifies additional cross-cutting focus requirements, avoiding silently rewriting card scope. This mapping is not a technical-status claim about other workstreams.

Bootstrap, enum/import, app/main and ASMAE cache blobs are unchanged from parent; broad startup and cache controls were not repeated. Passing import/cache slices do not establish resource, scientific authority or canonical publication acceptance.

Artifacts: `verify_plan_contracts.py`, `plan-contract-results.json`, `plan-contract-console.txt`, `source-receipt.json`, `coverage.json`. The script reproduces source/plan hashes, FA counts, R3/card mapping and the AST writer/call inventory without executing production control functions.

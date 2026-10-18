# AgriBrain corrective verification — 2e1fbcb

**Date:** 17 October 2026. **Candidate:** `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`. **Parent:** `fc82f14975cff7a90d15e21747ceb4fbc22a5457`.

## Decision

**All six original FC01–FC06 reproductions pass in this review. The general resource-exclusivity contract remains open:** a new, realistic interleaving of claim→idle query→START acknowledgement still produces two START command effects for the same exclusive device/zone. A second bounded query-failure case reaches the same result. These are one P1 resource-admission finding group, not two unrelated incidents.

Three adjacent P2 findings remain: publication generation is lost when upgrading a pre-receipt-map head, small percent-prefixed quantiles change meaning at 1, and gust-only equivalent duplicate rows are converted twice depending on order. They are distinct from the repaired original cases. A daily-interval/point-time question and known scientific qualification limits are recorded separately without inflating the confirmed-failure count.

Proceed with the bounded corrective implementation below. Prioritize Stage 6 ownership before concurrent-actuation sign-off. Independent plan packages and exploratory World Model/Omega work can continue under their own applicable evidence/model contracts. No full-package acceptance gate is closed by this review.

## Evidence, scope and provenance

Five specialist agents reviewed trajectory, protocol, forecasts, prescriptions and normative/lifecycle contracts in parallel. The coordinator independently ran resource admission and sensor file-lock recovery probes. A final GitHub branch read still names the candidate SHA. The candidate and main were retrieved with a nontruncated **4,068-entry tree**, no AGENTS.md, **6 changed production files** and one added historical report. **445 staged production blobs** match the candidate tree; lane receipts verify their additional/reused imported dependencies. These overlapping source counts establish identity, not a claim that every file was deeply reviewed.

Repository tests, historical audits and prior generated outputs were excluded as correctness evidence. Earlier authored probe definitions supplied fixture scaffolding, while freshly executed current code determines the findings. Simulated transport delays, file-write failures, process barriers, corruption injections and older-format fixtures are explicitly identified in the appendices. No production code, Git state, broker, field controller, actuator, drone or vendor service was changed or operated.

The reported **701 passing repository tests** were not independently rerun. Remote GitHub reads cannot verify the user's local clean-working-tree statement. Local simulation proves the stated contract observations, not measured double watering, field installation safety, vendor interoperability, calibration or prospective agronomic skill.

Normative inputs are the R3 monograph and the original master repair plan, execution addendum and task register. Verified supplied R3 PDF SHA-256: `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; register: 153 requirements. All three plan blobs remain exact and unchanged from parent. Fresh parsing confirms **52 unique FA rows, all open, zero checked**, covering all 52 master cards; each card's literal requirement list agrees with its direct master section. This verifies register integrity, not that every package is unimplemented or defective.

## Original corrections receive passing credit

| Original focus | Fresh observed candidate result | Disposition |
|---|---|---|
| FC01 simultaneous idle queries before claims | Two actual OS workers: 1 START; EXECUTING/STOP_REQUESTED. | Original case fixed. |
| FC01 B's earlier query held until A fully ACKs | 1 START; EXECUTING/STOP_REQUESTED. | Original delayed case fixed. General resource property remains incomplete below. |
| FC02 superseded recovery availability | Maximum owners 1; B enters after A; immediate fresh acquisition succeeds without mtime aging. | Original fixed; earlier nonce/cleanup/crash controls retained. |
| FC03 modern recovery receipts | Concurrent responses [5,5]; restarted load/retry 5; global head 5; next B 6. | Original fixed. Immutable allocation sequence 2 is correctly separate from publication view 5. |
| FC04 accepted numeric-percent 10/50/90 | Same score 3, RMSE 5, sharpness 20, coverage true as canonical aliases. | Original fixed; equal-alias deduplication retained. |
| FC05 offset-aware past point | Candidate 13 October 20:00Z before planning 14 October 11:00Z is BLOCKED. | Original fixed; same-day expiry and valid 16Z controls retained. |
| FC06 injected tzinfo with null offset | ContractViolation before store; UTC/fixed-offset and cross-offset cold round-trip pass. | Original fixed. |
| R03 query-first hardware fault | ERROR latches and survives timeout; further START refused without publication. | Checked earlier repair retained. |
| R05/R06 hydraulic continuity | A→B→A 448.11 warm/cold/control; CAS loser classified; follow-up/control 201.15. | Checked earlier repairs retained. |
| R07/R08/R09 weather/expiry/units | Near-boundary permutations block symmetrically; expired 18Z candidate blocks;16:00Z positive confirms; units/alias controls retained. | Checked earlier repairs retained. |
| R10–R12 archive/time/schema/interval | Corrupt final records reject; immutable publication/mutation controls retained; ordinary naive/horizon mismatch rejects; Gaussian/yield 1.28155σ retained. | Checked earlier repairs retained. |

The decision lane freshly ran 172 groups, the archive lane 26 groups, and the protocol lane 18 declared controls with its 71 original / 40 command rows. These heterogeneous, overlapping counts are not added into a fabricated repository pass total. Hydraulic values belong to different declared fixtures and are not field measurements.

## Remaining confirmed findings

| ID | Priority, scope | Current reproduction | Practical qualification |
|---|---|---|---|
| 2E01 | P1; F16–F18, Stage 6 | A claims STARTING, B truthfully queries idle, A sends/ACKs, delayed B sends second START. Separate failed-query-after-existing-execution also sends second START. | One resource contract group; two command-effect schedules; no measured duplicate dose. |
| 2E02 | P2; F09, Stage 3 | Legacy head exposes A2 publication 5, then independent B 6 publication causes A2 read/retry/restart to expose allocation 2 with publication generation absent. | Explicit upgrade fixture; scientific identity/payload and global 6 remain correct. |
| 2E03 | P2; F24, Stage 8 | New parser maps p1→1.0 and 1%→0.01; equivalent intended percent tails score 20 versus 0.2. | Shared normalization fixes original aliases but changes small-percent semantics. |
| 2E04 | P2; F15, Stage 5 | Equivalent gust-only 2m/s and 7.2km/h duplicates: m/s-first BLOCKED at 25.9km/h; reverse CONFIRMED; each single confirms. | Conservative overblocking/order dependence, not unsafe authorization or actuator bypass. |

### 2E01: query timing does not fence the pending physical operation

`resource_handoff_probe.py` uses **two actual spawned OS processes**, independent production dispatcher/base-actuator instances, one real shared quota file and an inert file-backed controller. The driver collaborator pauses A's send before applying the physical effect; production claim/dispatch/status methods remain unchanged.

1. A queries idle and commits STARTING ownership.
2. A reaches the transport but is paused before applying START.
3. B begins its status query after A's claim and truthfully samples ONLINE.
4. A's transport resumes, applies START, returns ACK and is durably EXECUTING.
5. B's sampled reply is released. Its query timestamp is later than A's claim timestamp, so `claim_resource` admits B despite A's current EXECUTING record.
6. B sends START. Both return EXECUTING, both processes exit 0, and the controller log contains two START effects for the same device/zone.

The older repaired schedule puts both idle queries before A's claim, so its query timestamp is correctly rejected. The new ordering puts B's query between A's durable claim and delayed physical application. A newer idle query cannot cancel a still-authorized in-flight send. There is no clock-skew injection; barriers select transport timing only.

The companion bounded case starts A normally to durable EXECUTING. A fresh independent dispatcher for B receives an injected transport exception from its query. Dispatcher retains a non-null query timestamp, sets live statusUNKNOWN, and the claim admits B because the timestamp is newer than A's claim. The actual inert controller is still running A; B sends a second START. This case uses independent instances in one process rather than OS spawn and is labeled accordingly. An unsuccessful query is not positive idle evidence.

Source: [irrigation_runtime/dispatcher.py#L518-L592](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/dispatcher.py#L518-L592), [irrigation_runtime/safety.py#L1590-L1658](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/safety.py#L1590-L1658). Query_ts is set before awaiting the query and retained on exception; existing EXECUTING exclusion depends on comparing claim time to that query. The generated owner token is metadata rather than an enforced fencing credential: claim returns only bool/holding-event, subsequent release/status/reopen writers do not consume an expected generation, and the inspected command path carries no winning generation to the driver. The platform appendix inventories these static lifecycle boundaries without counting them as extra runtime failures.

**Implement:** retain authoritative exclusion for an acknowledged or unresolved owner until positively reconciled. A hardware query must be qualified by outcome and the resource generation it observed; wall-clock ordering alone is insufficient. Make resource key, immutable operation envelope, exposure and owner generation one durable contract. A newly generated token must be returned, consumed on mutations and validated at the last possible pre-send boundary; define controller-supported fencing or a dispatch design that prevents an earlier pending sender from acting after replacement. Preserve STOP/recovery obligations while outcomes remain uncertain. Declare device/zone/shared-pump capability explicitly.

**Acceptance:** retain 1 START for both original FC01 fixtures, then require 1 START for the claim→idle query→ACK schedule and no second START after a failed query with an existing unresolved owner. Include same-event retry, slow send beyond lease age, stale release, crash/restart, failed ACK/STOP and supported independent zones under the same lifecycle. TTL expiry and UNKNOWN alone must not prove a physical stop. These additional acceptance items are not independently counted as reproduced failures here.

R3 focus: AB-EXE-002/003/004 and AB-ARC-008. Master cards F16–F18 and cross-cutting F19 remain Stage 6; this is still the original resource-ownership target, not a newly invented feature requirement.

### 2E02: preserve known publication generations during upgrade

The modern FC03 receipt maps work. The adjacent trajectory fixture deliberately uses the parent's supported pre-receipt-map head shape, with a known latest A2/global generation 5 but no new maps. Current read fallback correctly exposes A2 publication 5. The first independent B publication writes generation 6 and initializes receipt maps for B only. A2 then ceases to be global latest, loses its fallback and returns old allocation sequence 2 with publication_generation absent. Its identity, scientific payload and scope pointer remain intact; global head 6 does not regress.

**Implement:** before first upgraded publication, backfill generations established by the legacy head, especially the known latest checkpoint/global generation. Older history whose publication generation cannot be established should be explicitly unknown, not silently equated to its allocation sequence. Preserve immutable checkpoint bytes.

**Acceptance:** A2 must continue exposing known publication 5 after B 6 across retry/restart, while modern [5,5]/load 5/retry 5 and global 4→5→6 remain valid. Sources: [world_model/canonical_worldline.py#L270-L288](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/canonical_worldline.py#L270-L288), [world_model/canonical_worldline.py#L387-L403](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/canonical_worldline.py#L387-L403), [world_model/canonical_worldline.py#L470-L486](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/canonical_worldline.py#L470-L486). R3: AB-DAT-003/012, AB-ARC-008. This is a qualified upgrade receipt gap, not renewed scientific-state corruption.

### 2E03: declare the complete quantile grammar

The shared parser treats p/q suffix values greater than 1 as percent and values ≤1 as fractions. Thus p1 aliases p100 instead of 1%; p0.5 becomes the median instead of 0.5%. Actual archive evaluation of a single predicted 0 at observed 10 reports finite-grid scores 20 versus 0.2 for p1/1%, and 10 versus 0.1 for p0.5/0.5%. p0.5 also receives a median RMSE. The previous p-prefix parser uniformly divided by 100, so this is a bounded small-percent regression distinct from repaired bare 10/50/90 metrics.

**Implement:** choose a documented grammar for the whole range. Under the established P-percent convention, P0/P0.5/P1/P10/P50/P90/P100 convert uniformly by 100. Define fraction and q-prefix forms separately or reject ambiguity. Reuse one canonical parser in store validation, scoring and metric extraction; keep equal aliases deduplicated and conflicts rejected.

**Acceptance:** p1 and 1% both mean 0.01; p0.5 and 0.5% both mean 0.005; no false median; preserve original 10/50/90 parity, effective-awareness rejection, horizon and cold-round-trip controls. Source: [world_model/forecast_archive.py#L187-L206](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/forecast_archive.py#L187-L206), [world_model/forecast_archive.py#L225-L255](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/forecast_archive.py#L225-L255), [world_model/forecast_archive.py#L385-L405](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/forecast_archive.py#L385-L405), [world_model/forecast_archive.py#L664-L689](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/forecast_archive.py#L664-L689). R3: AB-ML-005/010; F24 Stage 8.

### 2E04: canonicalize gust units before merge/reparse

The scheduler normalizes gusts to km/h, then copies first-row unit metadata. It resets that shared unit only when wind speed values exist. For a gust-only m/s-first group, normalized 7.2 is later parsed as m/s and multiplied by 3.6 again, yielding 25.92 km/h. Equivalent rows in the opposite order remain 7.2. Actual drift, scheduler and final invariant functions execute; this is not a rewritten repair model.

**Implement:** assign canonical unit metadata whenever normalized speed **or** gust is written, or use explicit component units. Merging and reparsing equivalent physical support must be idempotent.

**Acceptance:** both single-row controls and both equivalent duplicate permutations yield the same feasible result; above-limit gusts still block and repaired near-boundary duplicate safety remains invariant. Source: [layer8_prescriptive/scheduler.py#L181-L200](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer8_prescriptive/scheduler.py#L181-L200), [layer8_prescriptive/scheduler.py#L238-L246](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer8_prescriptive/scheduler.py#L238-L246). F15 Stage 5; R3 AB-DEC-003, AB-ECO-003 and AB-EXE-001. The observed impact is avoidable rejection of a feasible slot, not an unsafe confirmation.

## Corrective implementation sequence

| Order / owner | Concrete deliverable | Evidence required before considering closure | Parallel work |
|---|---|---|---|
| 1 / runtime | Fix 2E01 through a single resource-owner lifecycle; qualify status-query evidence; consume generation on admission/update/release/recovery and final pre-send. | Both original 1 START cases retained; new two-process handoff and failed-query cases no longer produce duplicate START; uncertainty preserves owner/exposure/monitoring. | Highest priority; independent P2 work can proceed. |
| 2 / state persistence | Backfill known legacy receipt generations before replacing a head; distinguish allocation/publication/unknown history. | Legacy A2 publication 5 survives independent B 6, retries and restart; modern FC03 and scoped/CAS controls retained. | Independent of runtime and forecast parser. |
| 3 / forecasting | Specify full quantile grammar and canonical map; preserve accepted encodings without threshold-dependent meanings. | Small-percent equivalence and no fabricated median; original FC04/FC06 and immutable archive positives remain valid. | Independent Stage 8 slice. |
| 4 / prescriptions | Fix gust-only canonical units; specify point versus daily interval support. | Equivalent duplicate gust order invariant; above-limit/expiry blocks retained; daily support policy has explicit positives/negatives. | Independent Stage 5 slice. |
| 5 / integration | Run supported-image regressions and independent process acceptance against exact final code; reconcile receipts to full package criteria. | Closure evidence per gate; no substitution of aggregate pass counts for concurrency, scientific support or operational commissioning. | Coordinate after affected slices stabilize. |

These are bounded corrections within the existing addendum, not a replacement program or a new estimate of remaining hours. Original plan effort 2,564–4,540 hours covers all 52 packages and must not be described as the remaining workload. No artificial implementation-complete percentage is assigned.

## Qualified acceptance limits

**Daily support versus point candidates:** a safe date-only current-day row with declared validity spanning planning noon is rejected as a midnight point before planning. That is correct for a point slot; it may unnecessarily reject a daily interval. This review records a contract question rather than unconditional unsafe behavior or a second confirmed scheduling defect. Declare support type/timezone/endpoints; intersect daily support with planning and validity, select a future feasible instant, and retain the repaired past-point rejection. Separate duplicate-validity/version permutations were not executed in this bounded pass.

**Forecast scientific qualification:** the direct archive checks opaque evidence-ID syntax but still does not establish an independently qualified variable/unit/spatial/temporal/role/domain target receipt. A deployed upstream binding could satisfy that contract but was not verified. Numerical scores alone do not certify independent validation authority. This is a known unchanged F24 acceptance limit, not a newly rediscovered failure.

**Finite-grid scoring:** the finite pinball-grid average remains labeled CRPS. It differs from analytical Gaussian CRPS by construction; that numerical difference is not itself a Gaussian defect. Label the grid/levels/weights accurately or implement documented integration before cross-representation calibration. Retain the corrected 1.28155σ central 80% Gaussian intervals.

**Operational scope:** protocol query/heartbeat/telemetry fault, cancellation, callback/fence and STOP controls pass locally; deployed vendor meaning, qualified reset and commissioning remain separate. ASMAE/cache, MESIA, bootstrap and other unchanged full packages were not broadly rerun here. Their reported repository suites are not newly certified. Independent eligible plan work remains possible while package-specific gates stay open.

## Package/R3 traceability and delivery

| Focus | Addendum stage | Current evidence |
|---|---:|---|
| F08/F09 |3| Original continuity/CAS and modern receipt controls pass;2E02 legacy upgrade receipt gap. |
| F39 |3| Original FC02 and retained lock/ingress controls pass; no new confirmed finding in this lane. |
| F15 |5| Original FC05/weather/expiry/unit controls pass;2E04 gust merge plus separately qualified daily support question. |
| F16–F19 |6| Original FC01 and protocol/foreign-owner controls pass;2E01 general resource admission still open. |
| F23/F24 |8| Original FC04/FC06 and archive controls pass;2E03 small-percent semantics; known scientific limits retained. |
| F38/T11 |10/11| Normative/source identity checked; no fresh broad runtime/cache authority certification. |

The bundle retains the exact selected master cards and scientific requirement extracts. The platform appendix maps all R01–R12 topics and distinguishes each card's literal requirement list from additional cross-cutting focus. All 52 FA milestones remain open; no task register was changed.

The accompanying report has six detailed lane appendices. The bundle provides authored scripts, fresh raw results, exact source-object manifests, normative inputs, environment versions, SHA-256 checksums and a portable materializer. It excludes production source copies, repository test files, historical audit inputs and generated controller/quota/checkpoint stores. All **20 authored reproduction/verification scripts** were replayed from a separate layout containing **922 verified source copies / 484 unique blobs**, with final exit codes0. An initial packaging verifier expected an unnecessary parent source copy; its authored unchanged-code comparison was switched to the supplied exact parent Git tree and that step reran successfully. Production bytes were unchanged. The replay record preserves that correction and the commands, outcomes and blob checks. Exit 0 means the stated observations—including counterexamples—were reproduced, not a production-pass total. The materializer reads Git objects into a separate workspace without fetch/checkout/commit/push; it is compiled/layout-verified rather than run against a separate full Git checkout. Python/POSIX environment limits are recorded.


---

# Specialist appendix: Trajectory and hydraulic recovery

# Workstream C — 2e1fbcb FC03 verification

Pinned source `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`, parent `fc82f14975cff7a90d15e21747ceb4fbc22a5457`. **FC03's original modern recovery-receipt counterexample passes.** Concurrent recoverers now both expose generation 5; new-instance load and retries also expose 5. Global head generation and scientific scoped pointers remain correct. One bounded adjacent legacy-upgrade fixture still loses the known generation after another scope publishes. It is P2 receipt metadata behavior, not scientific corruption.

## Original fixed controls

| Actual current-source check | Result |
|---|---|
| FC03 concurrent recovery responses | **[5,5]**, same A2 identity/payload |
| New-instance load / identical retry / retry after B publishes | **5 / 5 / 5** |
| Global recovered head and next B publication | **5**, then **6** |
| Immutable checkpoint allocation sequence | **2**, correctly separate from publication view |
| R05 A→B→A warm/cold/control | **448.11 / 448.11 / 448.11 mm** |
| R06 losing process | Expected **ConcurrencyConflictError**; follow-up/control **201.15 mm** |
| Independent scopes / same-scope competing successors | Both independent scopes commit; same-scope successors yield one commit/one conflict |
| Original corrected observations / retained weather | **201.13/201.13 mm**; weather warm/cold/control **122.75 mm** |
| Parameter retry, legacy scoped-head lookup and generation controls | Retained passes |

The new head maps durably associate checkpoint identity and scope with publication generation, and read/idempotent paths overlay that generation. The immutable A2 record retaining sequence 2 is not itself a defect; current public receipts consistently expose publication_generation 5 in the modern case.

- [services/agribrain/world_model/canonical_worldline.py:270–288](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/canonical_worldline.py#L270-L288) — blob `b946b1accb9e2ce32be13b77ff8564e7c2a70a9e`.
- [services/agribrain/world_model/canonical_worldline.py:387–403](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/canonical_worldline.py#L387-L403) — blob `b946b1accb9e2ce32be13b77ff8564e7c2a70a9e`.
- [services/agribrain/world_model/canonical_worldline.py:407–433](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/canonical_worldline.py#L407-L433) — blob `b946b1accb9e2ce32be13b77ff8564e7c2a70a9e`.
- [services/agribrain/world_model/canonical_worldline.py:470–490](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/canonical_worldline.py#L470-L490) — blob `b946b1accb9e2ce32be13b77ff8564e7c2a70a9e`.

## C-L01 — P2: legacy publication-map migration seam

F09 stage 3; R3 AB-DAT-003/012 and AB-ARC-008. The single adjacent scenario deliberately supplies the **pre-receipt-map fc82 head shape**. Current production records generate the state; only the two newly introduced receipt-map fields are omitted from the private fixture. Scoped head pointers and global sequence remain intact. This is an explicit upgrade input, not spontaneous corruption of a modern valid head.

| Step | A2 sequence / publication_generation | Global head |
|---|---|---:|
| Legacy fixture: latest A2, immutable allocation sequence 2 | **5 / 5**, via latest-head fallback | 5 |
| First new independent B publication | A receipt maps are not backfilled | 6 |
| Load A2 afterward | **2 / absent** | 6 |
| Identical A2 retry / new-instance load | **2 / absent** | 6 |

B's first upgraded write creates receipt maps containing only B. A2 is no longer the global latest, so the fallback that had recovered its known generation 5 stops applying. A2 identity/scientific payload and both scoped pointers remain preserved; the global head does not roll backward. The original modern FC03 case remains a passing control.

Concrete fix: before replacing a legacy head, persist publication generations that can be established from it—especially the known current latest checkpoint and global generation. Qualify any historically unrecoverable generation as unknown rather than silently using its old allocation sequence as known publication time/order. Acceptance: the same legacy fixture continues returning A2 generation 5 after independent B generation 6, across restart and idempotent retry, while all modern receipt controls retain [5,5]/load5/retry5.

- [services/agribrain/world_model/canonical_worldline.py:270–288](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/canonical_worldline.py#L270-L288) — blob `b946b1accb9e2ce32be13b77ff8564e7c2a70a9e`.
- [services/agribrain/world_model/canonical_worldline.py:387–403](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/canonical_worldline.py#L387-L403) — blob `b946b1accb9e2ce32be13b77ff8564e7c2a70a9e`.
- [services/agribrain/world_model/canonical_worldline.py:470–486](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/canonical_worldline.py#L470-L486) — blob `b946b1accb9e2ce32be13b77ff8564e7c2a70a9e`.

## Historical retry semantics and scope

The adjacent scenario also repeats a previously committed **non-head A1 save** before and after B publication. Production returns a typed ConcurrencyConflictError and preserves the head. Its message calls the record an uncommitted orphan even though the fixture had previously committed it, but this review does not classify the rejection as an unsafe rollback or a new blocking defect. An historical save request is distinct from the read/query path; the exact historical water-query control still matches its archived state without moving the operational head.

All data are generated by executing current production symbols. Earlier authored scripts supply fixtures and capture logic only; prior generated results or repository suites/audits are not proof of the new code. Every reused dependency is blob-verified against the current tree. Both Worldline module aliases are redirected to the same private store, matching their common production default. The legacy head fixture now omits both new receipt maps as well as older scope-index fields where appropriate; this adaptation is not reported as a source bug.

The original head-write failure is injected once at the isolated store boundary after the real checkpoint write. Recovery, save/read overlay, idempotence and scoped CAS execute unchanged production code. Archived rows without materialized WaterState are treated as archived data. Independent-scope controls include each scope's accepted prior interval; different accepted histories are not compared as identical inputs.

This is one bounded adjacent upgrade/receipt scenario, including historical-save semantics; no broader static issue is added. The original FC03, R05/R06, scoped-generation and legacy-head discovery fixes receive passing credit. The remaining P2 is scoped to receipt migration. Full F08/F09 and master-plan R1 acceptance is not inferred from finite passing probes. No production/Git source, network service, vendor/controller or hardware was changed or called. All store writes are private simulated fixtures.

## Completed reproduction commands

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/trajectory/probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/trajectory/claim_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/trajectory/gate_probe.py new
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/trajectory/deep_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/trajectory/adjacent_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/trajectory/recovery_receipt_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/trajectory/legacy_receipt_probe.py
```

Raw results, runnable scripts, coverage.json, and exact source/dependency manifests accompany this report. Twenty-three supporting target blobs and four reused dependency blobs are verified against the current tree.



---

# Specialist appendix: Nonce ownership and ingestion

# Sensor file-lock recovery — 2e1fbcb

**FC02's original recovery availability failure is fixed in the checked schedule.** The previous two-owner critical-section counterexample also remains repaired. Superseded B now restores live A's ownership marker; A completes; B subsequently enters alone; a fresh acquisition succeeds immediately without aging a leftover empty file.

Exact current source is `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`, parent `fc82f14975cff7a90d15e21747ceb4fbc22a5457`. Executed security module blob: `e82a274f3ab26d84188291d0ab9baf43f9c7342f`. The coordinator ran the existing authored harness against current production code and verified all ten imported production modules against the candidate tree. Old results/audits and repository tests were not used as correctness evidence. No production/Git edits, network/controller or hardware interaction occurred.

## Fresh observations

| Current case | Result |
|---|---|
| Two OS processes, identical message nonce | Exactly one accepted reading; durable nonce survives; fresh-process replay rejected. |
| Two OS processes, distinct nonces | Both accepted/persisted; subsequent repeated A rejected. |
| Ten threads, same nonce | One winner; nine blocked. |
| Registry/calibration/raw-store pre-write failures | Failed attempt leaves no committed nonce/seen/raw evidence; restored retry accepts. |
| Interrupted primary/recovery owner | Two follow-up acquisitions succeed; recovery guard removed. |
| Earlier double-cleanup replacement-owner schedule | One cleanup; replacement's nonce survives; later replay rejected. |
| Strict rollback I/O failure | OSError propagates; restored retry accepts. |
| Aged live recovery guard | A and B serialize; maximum simultaneous primary owners1. |
| Original FC02 stale-recoverer schedule | A then B enter with maximum owners1; no production exception; immediate fresh acquisition succeeds; no surviving primary; no31secondmtime-aging step required. |

The final schedule starts with explicitly dead, aged primary/recovery fixtures. Hooks pause actual unlink calls and observe the actual liveness result to establish the same interleaving used previously. No production lock predicate is substituted. The parent releases A after B detects supersession; B's subsequent successful entry and fresh post-release acquisition are both observed. The raw momentary primary contents sampled during supersession may precede the restoration write; the completed owners and follow-up result establish the repaired outcome.

The old harness expected TimeoutError and an empty surviving primary. Its expectations were updated to the new observed repair: B enters after A and no empty artifact remains. That expectation change is explicitly a harness adaptation, not a production change or independent failure finding.

Current source at `sensor_runtime/security.py:222–239` restores the live owner token on the superseded path, and `254–269` permits cleanup of an empty artifact. The existing thread lock, process lock, failure rollback and ingress cleanup execute unchanged production methods in these fixtures. The selected receipts do not certify every possible takeover/release interleaving, PID reuse, filesystem, OS or deployed ingress transaction.

## Plan/R3 disposition

This is bounded Stage3 F39 acceptance evidence. The exact master-card requirement list and cross-cutting AB-DAT-003/011/013 and AB-ARC-008 focus are preserved separately in the platform mapping. Passing these controls repairs the supplied FC02 failure; it does not close the whole F39 full-acceptance gate or establish hardware/data science authority.

Reproduce with `PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/ownership/actual_nonce_probes.py`. Artifacts: `actual-nonce-results.json`, `coverage.json` and the authored script. Exit0 means its declared controls/expectations were reproduced; it is not a repository-suite result.


---

# Specialist appendix: MQTT protocol and actuator faults

# Protocol regression verification — 2e1fbcb

**The protocol repairs remain effective at `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc` (parent `fc82f14975cff7a90d15e21747ceb4fbc22a5457`). No additional protocol failure was demonstrated in this bounded pass. Resource admission and the physical resource race remain the separate root review.**

The seven authored verification scripts were executed freshly against this source. Actual imported paths and Git-blob hashes were independently verified for MQTT, actuator, dispatcher, safety and schemas (`source-index.json`). MQTT, actuator and schemas are byte-identical to the parent; dispatcher and safety use the new source. Previous results, repository tests and audit documents are not correctness evidence.

## Delta-linked interactions

The dispatcher now timestamps its live query and passes that timestamp to the resource claim. Its new ONLINE branch may update a prior same-dispatcher durable reservation to COMPLETED. STARTING is also recognized in other-owner, rehydration and pending-dispatch paths. These are resource/lifecycle changes, whose whole acceptance is not certified by protocol results.

The independent existing-latch guard and post-query fault guard still precede both the new ONLINE branch and the resource claim: [`dispatcher.py:505–545`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/dispatcher.py#L505-L545). The timestamped claim is at [`588–592`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/dispatcher.py#L588-L592). Fresh fault-origin submissions are refused without START publication, so the checked protocol safety gate remains effective ahead of resource admission. `delta-interactions.json` separates this static ordering and runtime evidence from the untested resource/restart cases.

## Fresh outcomes

| Control | Current observation | Assessment |
|---|---|---|
| Fault first observed by correlated QUERY_STATUS | First event FAILED, ERROR, latch true | Earlier fault-origin fix retained |
| Subsequent unanswered public query and second submit, without reset | Query remains ERROR; second event FAILED; no new query/START publication | Timeout cannot remove health prohibition |
| Existing latch after healthy report/timeout | Direct START validation failure and dispatcher refusal; zero publications | Earlier sticky-latch fix retained |
| Contradictory START status/flags | CONTRADICTORY_STATUS; uncertain command retained | START contradiction fix retained |
| START-origin FAULT | Latch set; later START blocked | Fault source covered |
| Status/heartbeat or telemetry contradictory FAULT during a running command | ERROR/latch set; original command retained | Fault does not certify physical stop |
| Query timeout and publish failure after either callback origin | ERROR/latch and command retained; pending map empty | Health and physical ownership remain separate |
| Clean correlated STOP while latched | STOP succeeds and clears command; ERROR/latch persist | STOP remains available |
| Late unmatched healthy ACK after that STOP | Does not clear latch or recreate command ownership | Stale callback does not act as reset |
| Direct, late-fence and dispatcher stopped-FAULT paths | ERROR retained; stopped command cleared; dispatcher stopped receipt present | Prior fault-retention controls pass |
| Failed normal STOP / failed second late-fence STOP | ERROR and original delivery command retained; late result STOP_FAILED | No false stop certification |
| Callback pop/cancellation interleaving, duplicate-ID cleanup, thread completion | No KeyError; newer STOP Future survives; debug off/on Futures complete | Prior pending-map controls pass |
| Three-method cancellation/publish exceptions and stale queries | Pending slots cleaned; stale ACK cannot certify fresh query | Lifetime/freshness controls pass |

`acceptance_matrix.json` records **18 verified control assertions**. The fresh raw matrix contains 71 original rows and 40 additional command rows; row counts do not imply universal protocol acceptance. Fixtures and outcomes are in `new_source_protocol_results.json`, `boundary_results.json`, `fault_reset_results.json`, `fence_failure_results.json`, `r03_adjacent_results.json` and `callback_origin_results.json`.

Current implementation references: fault ingress [`mqtt_driver.py:257–284`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L257-L284); fault decoding [`507–511`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L507-L511); query failure/timeout retention [`578–600`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/drivers/mqtt_driver.py#L578-L600); independent base guard [`actuator.py:210–213`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/actuator.py#L210-L213); direct STOP and late fence ownership [`345–360`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/actuator.py#L345-L360), [`523–562`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/actuator.py#L523-L562).

## Acceptance boundary

This is partial Stage 6 coverage for F17 operation state, F18 uncertainty/reconciliation and F19 fault protection/reset. R3 section 183 (484–488) and AB-EXE-002/003/004 (1110–1120) require acknowledgement, physical execution, uncertainty and safety permission to remain distinct. The supplied R3 text SHA256 is `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`; master cards are `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:575–652`.

Bare OK START meaning, a qualified public fault-reset interface, full restart/debounce behavior and measured delivery remain separate contract/acceptance work. They are not newly demonstrated failures here. The inherited harness retains scoped supplemental boundary observations; this pass does not newly adjudicate every API configuration case.

All publications, controller replies and worker-thread callbacks are private offline fixtures. There is no broker, hardware, physical-flow measurement or vendor-protocol certification. Invalid timeout integration rows use a 25 ms harness bound; finite helper output is checked separately. This pass makes no production or Git edits and does not certify resource admission, nonce/TTL correctness or the physical resource race.

## Reproduction

From `/workspace/scratch/de6bc2428cec`, run in order:

```bash
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/protocol/verify_source.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/protocol/protocol_matrix.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/protocol/boundary_probes.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/protocol/fault_reset_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/protocol/r03_adjacent_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/protocol/callback_origin_probe.py
PYTHONDONTWRITEBYTECODE=1 python repair-2e1fbcb-review/protocol/collect_evidence.py
```


---

# Specialist appendix: Forecast archive and scoring

# Forecast/scoring lane — exact 2e1fbcb verification

Reviewed **`2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`**, parent `fc82f14975cff7a90d15e21747ceb4fbc22a5457`.

**FC04's original numeric-percent metric case and FC06's injected no-offset-timezone case are fixed.** Retained alias, schema, horizon, publication, mutation, retry, zero, Gaussian and yield controls continue to pass. One bounded adjacent parser scenario found a **separate small-percent-prefix semantic defect**: `p1` and `p100` both normalize to 1.0, while `1%` normalizes to 0.01; this changes actual archived evaluation scores. F24 remains partial for that issue and the separately identified, unchanged target-qualification and score-naming acceptance limits. The repaired originals should not be reported as still failing.

## Evidence and scope

`probes.py` completed **26 case groups**: all 25 prior authored case definitions freshly executed against this candidate, plus **one** bounded adjacent parser/time round-trip scenario tied to the changed parser and effective-awareness guard. No additional expansion followed that run. `results.json` contains raw current outcomes; `source-receipts.json` records exact Git blob and SHA-256 receipts.

All **37 imported staged production blobs** and **two dependency blobs** matched this candidate's Git tree. The archive blob is `6a0f9caa16960bde29b552f5f942b741653e46af`, SHA-256 `3427e645e4da1f8405199ed1f75cc02d65ed54a367f76452710a5bc50ced2a42`. The yield target remains blob `22bc95df4eee397792089c59e949e213c903ad7d`.

The staged subset omitted `services/agribrain/crop_database/{__init__.py,registry.py}`. Existing local source bytes were copied into this lane's `dependencies/crop_database` and verified against the **candidate** tree blobs `462a82e514f8a954ebf8a53748313c18fae842d3` and `17aef77d0a0cdbaee919644b6715bc1d0c5703bb` before import. Previous receipts/results/audits were not used as correctness evidence. There was no network retrieval in this pass.

Reproduction, with Python 3.12 and NumPy/Pandas available:

```bash
python /workspace/scratch/de6bc2428cec/repair-2e1fbcb-review/ledger/probes.py
```

Keep the sibling exact `source` tree, `git-tree.json`, and the two dependency files above. The script verifies core/dependency hashes before import and loaded staged hashes before writing receipts, disables bytecode writes and creates a fresh `ledger/isolated` directory. Fixtures are private local archive files and selected thread schedules, plus explicitly labeled link failure, child-process exit, existing-file corruption and custom-timezone injections. No production edits, Git writes, repository tests/audits, network/controller or hardware calls were used. A child exit during valid serialization is not power-loss testing. Invalid caller JSON/type failures are distinguished from that interruption.

Source abbreviations: **FA** = `source/services/agribrain/world_model/forecast_archive.py`; **YF** = `source/services/agribrain/layer6_yield/yield_forecast.py`, under this review root.

## Original fixes and retained controls

| Checked behavior | Fresh result on 2e1fbcb | Exact source |
|---|---|---|
| **FC04 original** bare `10/50/90` keys | Same metrics as canonical, equal-alias, uppercase, `%` and decimal forms: score 3, RMSE 5, sharpness 20, coverage true. Conflicting aliases reject. | FA 187–206, 225–255, 385–405, 664–689 |
| **FC06 original injected type** `tzinfo.utcoffset() is None` | `ContractViolation` before store. Ordinary naive times also reject. Fixed UTC+02:00 still round-trips warm/cold. | FA 360–378 |
| Original horizon 0.01/2 for one day | Both reject; nonfinite/bool and gross mismatch controls also reject. | FA 374–378 |
| New bounded cross-offset aware control | Issuance UTC+02:00 and target UTC−04:00 preserve the same instants through cold storage, with horizon 1; numeric-percent metrics remain populated. | FA 362–378, 412–413, 568–570, 664–689 |
| Original schema-as-absence cases | Injected `{`, top-level `[]`, list metadata, invalid horizon and missing `plot_id` raise `ContractViolation`. These are existing-file corruption fixtures, not files generated by the normal writer. | FA 551–587 |
| Durable conflict / rejected retry | Replacing committed mean 1 with 99 rejects twice. Warm/cold retain 1, disk bytes unchanged, observation 99 yields RMSE 98. | FA 479–527 |
| Temporary publication / interruption | Controlled exit 83 during temp dump leaves no final forecast; retry succeeds. Reader during paused serialization sees no partial final. Inert orphan temp does not become a committed record. | FA 30–58 |
| Concurrent conditional link / injected error | Incompatible writers produce one complete winner and one conflict (this run mean 99 won); identical writers both succeed. Injected link error cleans ordinary temp/final state and permits retry. | FA 38–58 |
| Caller/retrieved-copy mutation | P50 mutation 1→99 after production snapshot does not alter returned, warm/cold prediction or subsequent RMSE 98 against 99. | FA 481–482, 525–527, 546, 583 |
| Evidence encoding / retry / syntax | Colon-containing evidence sets stay distinct; reordered/identical retries deduplicate cache/disk; changed observation/microsecond changes identity. Blank, None and scalar string evidence reject. | FA 636–647, 703–729 |
| Finite numbers / missingness | Nonfinite observations, means, sigma, invalid/crossed quantiles and negative sigma reject. P90-only prediction at observation 77 has finite grid score 4.6 and null RMSE/sharpness/coverage; no observed-filled median or NaN JSON. Missing distribution rejects before time checks. | FA 219–276, 379–405, 630–689 |
| Valid zeros / Gaussian | Valid point mass at truth scores 0; point mass error 2 scores 2. Valid N(10,1) at 10 scores 0.23369497725510913. Strict metadata JSON rejects nonfinite values without cache/final/temp; nested zero is retained. | FA 35, 258–276, 519–527 |
| Yield producer / archive interval | Base and single-branch posterior wheat outputs retain mean 4.5, P10 3.92 and P90 5.08 for σ=0.45. Explicit local adapter and Gaussian archive both classify observation 5.175 outside the interval. | YF 104–131, 224–244; FA 691–697 |

The producer check invokes production yield methods with an explicit local field adapter into the archive. It does not certify deployed wiring, independent evidence, field calibration or the producer's existing eligibility flags. Minor interval-width difference (1.16 versus 1.153395) is explained by the producer's two-decimal endpoints. Finite-grid and analytical Gaussian scores need not match.

## One new bounded parser finding

### D-2E-01 — percent-prefix interpretation changes at the value 1

**Confirmed on current production parser and archive evaluation, separate from the fixed FC04 original.** `bounded_parser_small_percent_and_cross_offset_roundtrip` records:

| Key | Parsed level | Stored forecast value 0, observation 10: reported grid score |
|---|---:|---:|
| `p1` | 1.0 | 20.0 |
| `1%` | 0.01 | 0.2 |
| `p0.5` | 0.5 | 10.0 |
| `0.5%` | 0.005 | 0.1 |
| `p100` | 1.0 | parser control only |
| `100%` | 1.0 | parser control only |

`p0.5` also becomes a median and receives RMSE 10, while `0.5%` correctly has no median metric. `q1` likewise parses as 1.0, but the unambiguous defect is the percent-prefix convention represented by p keys: the parser treats numbers above 1 as percent and numbers at or below 1 as fractions (FA **191–201**). Thus `p1` aliases `p100` rather than `1%`. All three callers now consistently use this shared interpretation at FA **227**, **390**, **667**; consistency alone does not make the small-level meaning correct.

The fresh run substantiates the changed interpretation and numerical effect. The previous percent-prefix parser divided p values by 100; this finding should be scoped as a small-level parser regression/convention error, not a return of the repaired bare numeric-percent metric defect. These are valid scalar keys and values, not injected malformed runtime objects.

**Acceptance:** give prefixed percent levels a single declared grammar across their full range, including P0/P0.5/P1/P10/P50/P90/P100; convert p-percent values uniformly, or reject ambiguous forms explicitly. Define q-prefix/fraction forms separately if necessary. Parser, store validation, score and metric extraction must agree with that declared grammar, preserve equal-alias deduplication and conflict rejection, and retain all fixed FC04/FC06 originals. For the percent grammar, `p1` and `1%` must both mean 0.01 and produce identical supported metrics. Plan F24 **770–779**, task `ST08-F24-04` **1127–1131**; R3 AB-ML-005 **990–992**, AB-ML-010 **1010–1012**.

## Known acceptance limits, unchanged and not new findings

**Independent target qualification:** typed nonblank IDs are checked, but the archive function still does not bind a typed variable/unit/support/time/role/independence receipt. The retained isolated opaque-ID case receives numerical metrics with default `in_domain` / `observation_space` (FA **442–443**, **636–647**, **707–718**). Arbitrary contradictory metadata is not itself a verified receipt, and no deployed evidence resolver/caller was exercised. Acceptance remains a checked target receipt or verified upstream binding, with unsupported/unqualified targets unavailable/unknown and valid zero preserved. Plan F24 **771, 779**; R3 AB-DAT-007 **683–685**, AB-DAT-009 **691–693**, AB-ML-005 **990–992**, AB-ML-010 **1010–1012**, AB-ASM-016 **836–838**.

**Finite-grid score naming:** the unweighted finite pinball average (FA **247–255**) is still labeled CRPS (FA **209–218**). At observation 1.5 for standard normal, analytical Gaussian CRPS is 0.9944240039774529 and the three-level grid score is 0.8165058317095463; this expected difference is not a failure of the Gaussian formula. Acceptance remains accurate finite-grid naming/levels/weights or a documented CRPS integration rule, with declared calibration domain/horizon. Plan F24 **773, 779**, task `ST08-F24-04` **1127–1131**; R3 AB-ML-005 **990–992**, AB-ML-010 **1010–1012**.

Malformed caller type outcomes remain mixed (`None` quantiles→`TypeError`, list metadata→`AttributeError`; empty list/string quantiles can normalize to `{}` alongside the tested valid mean=0/std=0). Rejected cases publish no final/cache entry. This is a typed-input consistency limit, not demonstrated false credit. A wholly absent distribution can still be archived, but scoring rejects explicitly; no numerical skill credit was observed for it.

## Coverage boundaries

F23's checked original conflict/concurrency/mutation and corruption criteria pass in this bounded run. F24 is partial: its original numeric-percent metric and no-offset-timezone counterexamples are repaired; the new parser boundary case and the retained scientific acceptance limits remain. There is no all-R10–R12, full Stage 8, field-calibration, promotion or machine-authority sign-off.

Master plan: `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`, F23 **730–753**, F24 **755–779**, gate **134**. Stage 8: `AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md` **36**. Task list: `AgriBrain_Work_Packages_Task_List_2026-10-07.md` **1069–1139**. R3: supplied `current-plan-review/R3_current_scientific_sections.txt`; F23 maps to AB-DAT-011 **699–701**, AB-ARC-007 **746–748**, AB-ARC-008 **750–752**, AB-ASM-014 **828–830**; F24 to AB-ML-005 **990–992**, AB-ML-010 **1010–1012**, AB-ASM-016 **836–838**. AB-DAT-005 **675–677** supports preserved zero/missingness behavior. Prospective/reconstruction lineage and package dependencies were not certified by these archive controls.


---

# Specialist appendix: Prescriptions and hard envelopes

# F15 / FC05 bounded actual-source review at 2e1fbcb

FC05's offset-aware past-candidate reproduction is corrected at `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc` (parent `fc82f14975cff7a90d15e21747ceb4fbc22a5457`). The previous same-day expiry and near-threshold duplicate repairs remain effective. The bounded additional checks identify one confirmed conservative merge/unit defect and one daily-versus-point-support contract question. Full F15 is not certified.

All 167 previous groups were freshly rerun, then five authorized adjacent fixtures were added, for 172 total. There were no production exceptions. All 30 source manifest entries, covering 29 unique production files, match the current pinned tree; unchanged dependency copies were independently reverified. No repair models, repository tests/audits, production/Git changes, controller/network/services or hardware were used.

Function-composition cases use actual ActionCards with two independent evidence families and run the actual drift, scheduler and final invariant gate. Four actual raw `run_layer8` controls remain included. Raw L8 shadow output and local schedule labels do not prove top-level authorization or physical execution.

## Repairs and controls verified

| Case | Actual current result |
|---|---|
| FC05 planning `2026-10-13T23:00-12:00` (= Oct 14 11:00Z), candidate Oct 13 20:00Z | BLOCKED: candidate precedes planning start. |
| Planning 12:00Z, same-day candidate 18:00Z, validity ends 17:00Z | BLOCKED. |
| Planning 12:00Z, candidate 16:00Z, validity ends 17:00Z | CONFIRMED. |
| Near-threshold rain/speed/minimum-temperature/maximum-temperature duplicate permutations | Both orders remain BLOCKED. |
| Identical zero-wind duplicates, both-safe rain duplicates, equivalent speed-unit duplicates | Remain CONFIRMED. |
| Earlier invalid dose/cap and actual later-modifier lower-bound cases | Remain BLOCKED; invalidity is not promoted into an authorized dose. |
| Physical frost wind/temperature alias and raw-run numeric-string controls | Corrected behavior is retained. |

Source: `services/agribrain/layer8_prescriptive/scheduler.py:345–350` normalizes planning start to UTC; `375–392` rejects past candidate instants and checks the planning horizon; `400–410` retains the later-of-planning/candidate expiry check. Scheduler blob: `90290fb03edcb36ed5f24452aae86b1c9774bfeb`.

## Confirmed remaining case — Review priority P2: Gust-only duplicate merge converts the same wind twice

The single adjacent merge scenario uses two same-date rows representing the same physical gust:2 m/s and 7.2 km/h. Neither row supplies wind speed; both supply qualified zero rain and safe temperatures. Each single-row control returns CONFIRMED.

Combining these equivalent rows with the m/s row first returns BLOCKED at a reported 25.9 km/h. Reversing the same rows returns CONFIRMED. The drift gate correctly accepts the physical 7.2 km/h gust; the difference arises in the scheduler. The final invariant gate also executes.

The group collector normalizes gust values to km/h. The representative stores that normalized gust, but resets the shared unit to km/h only when a speed value exists. In the gust-only m/s-first case, the representative retains m/s metadata, so the later weather parser multiplies 7.2 by 3.6 again, producing 25.92 km/h. The km/h-first permutation avoids the second conversion.

Source: `scheduler.py:181–200` collects normalized wind/gust values; `238–246` copies first-row metadata and resets the unit only inside `if w_vals`; the later common wind-unit conversion and parsing apply to gust as well. Receipts: `F15_GUST_DUP_mps_single_control`, `kmh_single_control`, `equivalent_mps_first`, `equivalent_kmh_first`.

This is conservative overblocking and order dependence, not unsafe confirmation or an actuator bypass. It is now an executed reproduction, unlike the earlier source-only observation.

Concrete repair/acceptance: store a canonical unit whenever either normalized speed or gust is written, or use a typed wind object with explicit component units. Equivalent physical values must be idempotent under merge and reparse. Require both single-row controls and both equivalent duplicate permutations to return the same feasible disposition, while retaining above-limit gust blocks and the repaired boundary-crossing controls.

## Qualified contract result — Current-day daily weather is treated as a past midnight point

At planning `2026-10-13T12:00:00Z`, a safe row with `date='2026-10-13'`, `valid_from=Oct 13 00:00Z` and `valid_until=Oct 14 00:00Z` returns BLOCKED because the parser turns the date-only label into a midnight point preceding planning start. Its declared daily validity spans planning time, but the scheduler has no explicit daily support type.

The rejection is correct if the row denotes a point candidate at midnight. If it denotes a daily forecast interval—as the function's “one per day” description can imply—the new comparison prevents use of otherwise current-day support. This pass therefore reports a review-priority P2 support-contract question, not a proven unsafe result or an unqualified regression. The safe 14:00 timestamp control remains usable, and the intentionally past point remains correctly blocked.

Source: `scheduler.py:82–107` maps date-only labels to UTC midnight; `375–389` rejects earlier candidate points. Receipt: `F15_TIME_current_day_daily_support_contract`.

Concrete acceptance: distinguish point slots from daily intervals. For a daily interval, intersect its explicit support and validity with planning time and choose a future feasible instant; for a point candidate, keep the past-point rejection. Specify timezone and interval endpoints. Both the FC05 past-point fixture and a supported current-day daily-interval fixture need the intended disposition under that declared contract.

## F15 disposition and limits

F15 remains stage 5, dependencies F01/F06/F14, mapped to R3 AB-DEC-003 (`R3_current_scientific_sections.txt:1076–1078`), AB-ECO-003 (`1088–1090`) and AB-EXE-001 (`1106–1108`). Review P2 labels above are separate from the master plan's P0 priority.

- `ST05-F15-01`: supplied UTC cutoff, finite weather, physical-unit and numeric threshold cases pass; gust-only merge idempotence fails and daily support semantics remain undeclared.
- `ST05-F15-02`: supplied missing-weather and invalid-envelope cases remain fixed in the checked scope.
- `ST05-F15-03`: supplied original upper/lower-bound and invalidity cases remain fixed through the checked gates.
- `ST05-F15-04` / `ST05-F15-FA`: full acceptance remains open for support/merge convergence and unverified legal/resource/aggregate-budget and commissioning criteria.

This pass does not execute a separate duplicate-validity/version permutation batch or expand into other packages. Artifacts: `actual_decision_probes.py`, `actual-decision-results.json`, `coverage.json`, `source-verification.json`, `probe-summary.json`, `probe-stderr.txt`.


---

# Specialist appendix: Resource-claim lifecycle and plan register

# Resource token lifecycle and normative-plan check

Actual main: `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`, parent `fc82f14975cff7a90d15e21747ceb4fbc22a5457`. The repair adds persisted generation/token metadata, preserves claimed_ts when STARTING becomes EXECUTING, rejects STOP_REQUESTED owners, and explicitly handles STARTING during restart. These are substantive source improvements. The token is not yet an end-to-end fencing credential: it is not returned to the dispatcher or required by release/status/reopen/finalization writers, and the remaining admission logic depends on an earlier wall-clock query timestamp.

This lane independently performed **read-only source/AST and normative-document verification only**. It ran no direct-store, TTL, command-effect, concurrency, hardware, network, database or service probe. The coordinator owns current physical/resource-effect tests. Static schedules below qualify the existing R01 resource contract rather than add reproduced-finding counts. All **445 supplied production blobs match the current exact tree**. No repository tests, audits, prior generated results, source edits or Git mutations supply correctness evidence.

## What is present in actual source

| Contract element | Current source and behavior |
|---|---|
| New claim metadata | `safety.py:1590-1658` increments per-event generation and writes status STARTING, starting_ts, claimed_at, claimed=true and owner_token formatted as event:time:generation. The operation remains inside the shared store lock. |
| Query-age guard | `safety.py:1623-1644` now blocks STOP_REQUESTED and rejects an EXECUTING/DISPATCHING owner if the caller has no query timestamp or if recorded claim time is at least that query timestamp. This addresses the specific ordering where an idle query predates the competing claim. |
| Claim-time persistence | `safety.py:965-991` moves starting_ts into claimed_ts on STARTING/EXECUTING updates instead of losing it; stop/terminal updates clear starting_ts and claimed. |
| Restart integration | `dispatcher.py:1748,1816-1826,2045` recognizes STARTING in competing-owner/pending scans and maps it to DISPATCHING. STARTING still is not an EventStatus member, but an explicit translation now exists; the earlier absence-of-handling concern is partially addressed. |

Sources: [claim metadata and query ordering](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/safety.py#L1590), [claimed_ts persistence](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/safety.py#L965), [restart translation](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/dispatcher.py#L1816).

## Token consumption, time fencing and lifecycle limits

**Token consumption remains incomplete.** claim_resource returns `(bool, holding_event_id)`, not the winning owner token or generation. No shared writer accepts expected_token/expected_generation/fencing arguments. The token can be read to recover a fallback timestamp, but it is not compared as an authority credential on subsequent mutations. The inspected dispatcher command path does not carry the new generation to the driver/controller.

`release_resource_claim` (`safety.py:1661-1675`) still accepts device, zone and event, but reads neither supplied device nor zone. It changes any matching event's STARTING to RESERVED, clears claimed and starting_ts, without checking a particular claim attempt. Dispatcher calls it at line609 after an unsuccessful dispatch and before later refused/uncertain classification. Stale release and applied-without-ACK consequences are **static acceptance questions in this lane**, not additional executed failures.

**The fixed STARTING age remains.** A different worker is blocked only while STARTING age is below 30 seconds (`safety.py:1617-1621`). There is no claim renewal call in the inspected dispatcher path and no generation check at physical send. Persisting a generation does not itself prevent an older delayed sender from acting after another admission. No TTL takeover or stale-sender operation was executed here.

**Query_ts is temporal metadata rather than resource-generation evidence.** It is recorded before the get_status await and passed to claim_resource at `dispatcher.py:518-591`. On a query exception, status becomes UNKNOWN but the timestamp remains non-null. The claim method uses live_executing=false plus this timestamp to consider replacement of older EXECUTING/DISPATCHING records; it does not distinguish a positively idle query from a failed query. A separate static schedule is also possible from the source: A claims STARTING and pauses before physical send; B then truthfully queries ONLINE after A's claim; A sends/ACKs and becomes EXECUTING; delayed B compares a later query timestamp against A's earlier claim timestamp. The coordinator owns reproduction or rejection of these schedules. They are not claimed as this lane's observed command effects.

**All writers must preserve one contract.** The inventory covers all 12 SharedQuotaStore methods calling `_write_state`. Atomic quota admission binds event dimensions; compatibility reserve (`816-944`) and reopen (`1385-1521`) reconstruct records without carrying the new resource token/generation/claimed_ts fields as a coherent owner object. Start/status/release/settlement calls remain event-based. This does not demonstrate an independent permission bypass or accounting regression. It means resource authority is not yet a single fenced contract consumed across mutation, restart, stop and finalization.

**Resource policy is still explicit acceptance work.** Matching uses device and compatible zone, with empty zone as wildcard. The lookup includes VALIDATING or claimed=true, whereas claim_resource's exclusion branches do not uniformly consume those signals. The deployment must declare whole-controller, valve/zone or shared-pump exclusivity and supported independent-zone operation. This lane does not assume every zone must serialize, every validation record physically runs, or each static phase difference causes harm.

The coordinator's current `resource_handoff_probe.py` separately reports two concrete controls: after A's durable STARTING claim but before its physical send, B samples truthful ONLINE; A then ACKs and B's delayed claim produces a second START. A separate query-error control also produces a second START against A's durable EXECUTING record. Earlier both-query-before-claim controls now produce one START. Those current runtime outcomes belong to the coordinating workstream and are not counted again as this lane's independent reproductions; the source trace above explains the same R01 contract boundary.

These limits belong to the existing **R01 / F16–F19 stage 6** resource/operation contract, particularly R3 AB-EXE-002/003/004 and AB-ARC-008. They should be evaluated together with fresh/delayed claims, positive idle versus UNKNOWN queries, same-event retries, claim expiry, live delayed sends, stale releases, restart, failed STOP and compatible-zone capability. Do not turn each static note into a new reproduced-finding count.

## Exact normative-plan and register proof

| Normative document | Current tree/local Git blob | Parent |
|---|---|---|
| Deep Repair Plan | `08d378a65992de859369950599df198e64244f01` | unchanged |
| Work Packages Task List / FA register | `8a564647af7e588802537817159117b349ff606b` | unchanged |
| Execution Sequencing Addendum | `40751038dc8760e91bc3ab115e30c5e28395953a` | unchanged |

Fresh parsing yields **52 unique full-acceptance rows, all unchecked, zero closed**, covering exactly the 52 master cards. Every card's requirement list matches its direct normative master section. This verifies the register's state, not independent proof all packages are technically defective; narrow source improvements remain distinct from complete acceptance.

All R01–R12 mappings were retained and checked against the current unchanged normative documents and supplied R3 scientific sections:

| Topic | Canonical packages / stages | Scientific focus |
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

These are local-topic mappings, not current technical dispositions of other workstreams. JSON preserves both the complete unmodified master-card lists and explicitly additional cross-cutting R3 focus IDs. Startup/import/enum/app-main and ASMAE cache blobs are unchanged from parent and were not broadly retested. No scientific, supported-runtime or canonical-publication acceptance follows from this static lane.

Artifacts: `verify_plan_contracts.py`, `plan-contract-results.json`, `plan-contract-console.txt`, `source-receipt.json`, `coverage.json`. The verifier reads source/documents and reproduces hashes, register counts, requirement mappings and token/writer/call inventory without executing production control functions.

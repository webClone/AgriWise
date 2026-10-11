# AgriBrain production verification — 16b470f

Reviewed commit: `16b470f900af4cfd69ebed140cfc09f29eedd69d`. Parent: `6ac057ab6144a2c69b9b50e1184a9fb27d977d66`. Review date: 2026-10-11 UTC.

## 1. Decision and scope

The commit is available on GitHub and was `main` when rechecked. The seven **specific RC01–RC07 counterexamples from the preceding review are corrected**. Their independent reproduction harness completed with the intended corrected outcomes and zero harness errors. Healthy ACKs now publish actual start timing, the ordinary expired watchdog issues STOP under ledger faults, stale terminal records do not command the other live operation, and the original negative-duration writer probes preserve the ledger.

The surrounding contracts are not fully closed. Eight additional named probe groups establish **six remaining defect groups**, designated BV01–BV06 in this report. These are local review identifiers, not new master-plan packages or monograph requirement IDs. They concern continued operation ownership, unknown-controller completion, area qualification, immutable payload/support, failed ACK persistence, and recovered measurements.

Proceed with corrective implementation. Keep the six full-acceptance tickets open. Independent development can proceed where its own prerequisites are satisfied; this limited commit review does not establish whole-project, Omega, or world-model readiness.

This review used production code and independent controlled simulations. Repository tests and audit artifacts were excluded as correctness evidence. No production files were modified and no physical hardware was operated. The user's reported `545 passed` regression result was not independently rerun or recertified here.

## 2. Source and evidence identities

The commit timestamp is `2026-10-11T15:24:37Z`; the production changes are limited to two files:

| Production file | Git blob SHA-1 |
|---|---|
| [irrigation_runtime/dispatcher.py](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/dispatcher.py) | `2e5fec56e9df0e4c1ff394444757003e0ba4e3fa` |
| [irrigation_runtime/safety.py](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/safety.py) | `dc6a10424a1470384ffea7705b8674f6796b25f7` |

All 430 production dependency files used by the harnesses matched their exact pinned Git blob hashes and parsed with Python AST. Only these two files differ from the previous pinned dependency set. Integrity checking and parsing are not exhaustive semantic audits of every dependency.

Fifteen independent drivers produced **135 named current-commit JSON result groups**: 133 behavioral/scientific groups and two import diagnostic groups. These include successful controls and demonstrated defects. They are not 135 passing acceptance tests. All drivers exited successfully, and the final result files contain no harness-error groups.

The older expiry fixture was qualified for the new durable ACK behavior: simulated aging now updates the durable start as well as the local snapshot and injected timer. Without that adjustment, an old caller-only timestamp conflicts with the newly persisted recent ACK and is correctly ignored. The adjusted fixture was rerun; production code was unchanged.

The R3 comparison uses the previously supplied scientific requirements export, SHA-256 `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c`. This is the supplied target reference; it is not an assertion that an identically named R3 document was fetched from this Git tree or that all 153 requirements were recertified.

Simulated running state, cached status, queried status, and command counts are distinct in the driver fixture. This permits reproducing stale-cache and communication failures without field hardware. Actual field operating duration depends on controller protections, which were not verified. No externally reachable HTTP exploitation path is asserted for conflicting snapshots or low-level writer calls.

## 3. Original RC01–RC07 results

| Original finding | Independent current-commit observation | Qualification |
|---|---|---|
| RC01 — storage blocks watchdog | At `661 s` in a `600 s` operation, both corrupt reads and failed writes still produce one STOP and stop the simulation | The poll can raise a later accounting exception and retain ownership. Physical cutoff precedes that failure; accounting degradation remains explicit |
| RC02 — terminal snapshot commands another event | Settled and stopped snapshots return `COMPLETED`/`CANCELLED`, restore zero active owners, and issue no STOP to a newer operation | The active nonterminal mismatch guard must also survive later transitions, BV01; terminal measurements still need hydration, BV06 |
| RC03 — plot/target rebound on restart | Restart restores the original plot and `8 mm` target; the second `8 mm` request against `10 mm` fails; no changed-plot exposure appears | First settlement with a conflicting input plot preserves the canonical plot rather than raising. Other envelope dimensions remain mutable, BV04 |
| RC04 — caller replaces established deadline | Both empty and caller-supplied recent timestamps recover the old durable start, issue STOP, and become `EMERGENCY_STOPPED`; healthy ACK start equals durable start before polling | Failed ACK publication leaves a separate missing-durable-start branch, BV05 |
| RC05 — validation relies on stale cache | Restart and completion query the controller; healthy running response retains `VALIDATING`, `8 mm` reserved, zero settled | Failed, OFFLINE, and unavailable queries still permit completion, BV02 |
| RC06 — missing measurement becomes physical value | Explicit zero volume retains omitted duration as `None`; no-store idle restart stays `VALIDATING` with no receipt and zero settled | Recovered terminal snapshots can still return schema-default zeros instead of their measured outcomes, BV06 |
| RC07 — negative duration poisons writers | `reserve`, `reopen_active`, and atomic admission reject `-1` duration with `ValueError`, preserve durable bytes, and leave the ledger readable | `effective_area_ha` is passed to the new helper but not validated, BV03; full candidate identity also remains unchecked, BV04 |

These outcomes are in `contract-results.json`. The original counterexamples are credited as corrected without interpreting a narrow probe as proof of every branch in its defect group.

The hydraulic implementation is unchanged. The process-publication control again gives warm/cold profiles `[0.2124, 0.2546, 0.2616, 0.2652, 0.2295]`. The additional hydration interleaving control again preserves the winning soil state, head, and generation while rejecting the historical attempt with a compare-and-swap conflict. This review establishes no new hydraulic profile blocker.

## 4. Remaining defect groups

Priority P1 means resolve before full acceptance of this runtime path. Priority P2 identifies a narrower data/service contract defect that still requires correction before the affected capability is certified.

| ID | Priority | Contract failure | Relevant R3 requirements |
|---|---|---|---|
| BV01 | P1 | Restart's operation-mismatch protection is lost during the next poll or STOP recovery | AB-EXE-002/003, AB-ARC-008 |
| BV02 | P1 | Unknown/unavailable controller status can authorize completion | AB-EXE-002/005, AB-ARC-006 |
| BV03 | P2 | Area is unvalidated; reopen can publish a corrupt ledger and other writers erase invalid support | AB-DAT-005/007, AB-ARC-007 |
| BV04 | P1 | Command envelope, accounting period, and missing support are still rewritable | AB-DAT-003/006/007/010/013, AB-EXE-004/005, AB-ARC-007/008 |
| BV05 | P1 | Failed ACK publication permits a caller timestamp to create a fresh recovery allowance | AB-EXE-002/004, AB-ARC-006/008 |
| BV06 | P2 | Terminal recovery returns stale measurement defaults instead of canonical outcomes | AB-DAT-005/010, AB-EXE-005, AB-ARC-009 |

Mappings identify requirements affected by the observed counterexamples. They do not certify every subclause of those requirements.

### BV01 — operation fencing is checked at one transition only

Sources: [restart mismatch branch, lines 1320–1348](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/dispatcher.py#L1320-L1348), [polling STOP recovery, lines 725–782](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/dispatcher.py#L725-L782), [restart STOP recovery](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/dispatcher.py#L1259-L1315).

The new mismatch guard protects a live different operation during the `EXECUTING` restart branch. For an unexpired old event, it changes the old snapshot to `STOP_REQUESTED` and restores it as active. The next ordinary poll handles `STOP_REQUESTED` without checking the current operation identity and issues an emergency STOP against the different operation.

Reproduction: `OLD` ends on the controller between owner polls; a second worker starts `NEW` on the same simulated device. A fresh worker restores `OLD` while `NEW` is active. Restart itself issues zero STOPs, as intended. The next `check_execution_status(OLD)` issues one STOP and stops `NEW`, while `NEW` stays `EXECUTING` in local and durable records. A snapshot already in `STOP_REQUESTED` bypasses the mismatch guard and stops `NEW` during restart itself.

| Recovered old phase | STOP during restart | Total STOP after next relevant step | NEW simulation |
|---|---:|---:|---|
| EXECUTING, unexpired | 0 | 1 after polling OLD | Stopped |
| STOP_REQUESTED | 1 | 1 | Stopped |

Evidence: `remaining-contract-results.json → operation_identity_fence_not_preserved`.

Required correction: make per-operation stop eligibility a persistent invariant, shared by restart, retry/poll, and cancellation. Retain unresolved old exposure without treating a generic `STOP_REQUESTED` phase as authority to stop whichever operation currently occupies the device. Verify the operation receipt/identity at the point of command issuance. Keep intentional device/global emergency cutoff semantics separate: an authorized global cutoff still needs to traverse all actuators.

Acceptance: restart, poll, and STOP retry for `OLD` issue zero commands against `NEW`; both records remain truthful; unresolved accounting is retained. Also exercise same-operation cutoff to ensure the identity guard does not prevent required STOPs.

### BV02 — completion continues after failed or non-idle qualification

Source: [complete_event, lines 908–921](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/dispatcher.py#L908-L921).

Completion now queries status, but catches exceptions and continues. It rejects cached `EXECUTING`/`is_running`, rather than requiring a qualified idle result. A missing registry entry also permits the code to proceed. OFFLINE is not equivalent to stopped.

| Controller fixture | Completion | Reserved depth | Settled depth | Simulation |
|---|---|---:|---:|---|
| Healthy idle | COMPLETED | 0 | 4 mm | Stopped |
| Healthy running | VALIDATING | 8 mm | 0 | Running |
| Query raises OSError, cached ONLINE | COMPLETED | 0 | 4 mm | Running |
| Query reports OFFLINE | COMPLETED | 0 | 4 mm | Running |
| Actuator unavailable in registry | COMPLETED | 0 | 4 mm | Running |

The query-error fixture fails twice, on recovery and completion. The owner is removed despite unresolved physical execution. The `40,000 L` observation is valid in the fixture; it does not establish that the controller has ended its operation.

Evidence: `completion_after_unknown_controller`.

Required correction: completion needs positive, current, compatible termination/idle evidence. Query failure, timeout, OFFLINE, ERROR, unknown identity, or registry absence must leave the operation unresolved. Measurements can be recorded separately without declaring physical completion or dropping ownership. Do not let the catch block turn unavailable evidence into authorization through cached status.

Acceptance: healthy idle completes; healthy running and every unavailable/unknown case retain recovery ownership and unresolved exposure. Changing the cached status must not change the decision when controller evidence is unchanged.

### BV03 — the area validator parameter has no implementation

Sources: [scalar helper, lines 80–104](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/safety.py#L80-L104), [reopen writer](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/safety.py#L1218-L1303), [candidate publication](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/safety.py#L395-L411).

`_validate_writer_scalars()` declares `effective_area_ha` and all three writers pass it, but its body validates only volume, duration, and flow. The omission is code verified and independently reproduced.

The area probe covers each writer with `-1`, `0`, `True`, a numeric string, NaN, infinity, positive `1`, and omitted `None`. All invalid-area calls report acceptance. `reopen_active()` publishes `-1` or `0` area; the next read rejects the ledger with `CorruptedQuotaStoreError`. `reserve()` and atomic admission convert the tested invalid areas to `None` and publish them. This avoids corruption in those branches but silently erases invalid supplied support instead of rejecting it.

The positive-area and genuinely omitted-area controls remain readable. The required contract is: omitted area may remain missing; explicitly supplied area must be a strictly positive finite real, excluding booleans and strings.

Evidence: `writer_area_not_validated` (24 cases).

Required correction: implement the missing area validation, preserve explicit missingness, and validate the fully assembled candidate before replacement. Strict JSON encoding alone does not reject a finite negative area. Reject invalid requests without changing the prior healthy ledger or its history.

These are production service-writer calls, not a demonstrated public HTTP input exploit. Healthy prior state is preserved in the original negative-duration cases; those fixes are credited.

### BV04 — plot binding does not make the operation envelope immutable

Sources: [restart support hydration, lines 1171–1189](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/dispatcher.py#L1171-L1189), [reserve writer](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/safety.py#L774-L856), [initial settlement, lines 1007–1084](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/safety.py#L1007-L1084).

Three linked counterexamples establish that canonical plot recovery is only part of the required identity.

**Missing support becomes supplied support through restart.** An operation admitted with `effective_area_ha=None` is restored from a caller snapshot with area `1`. Because hydration only overwrites area when the canonical value is present, the caller value survives. Subsequent reserve writes make it durable. Measured completion now certifies `4 mm` on that caller-introduced area. The original missing-versus-present support compatibility rule is bypassed without a qualified geometry revision.

**Same-plot rewrites free quota.** After physically starting an `8 mm` operation, either `reserve()` or `reopen_active()` under the same event/plot accepts target `1 mm`, different device/zone, duration `20`, flow `3`, and area `2`. The current ledger then counts `1 mm` for an operation whose START commanded `8 mm`. A second `8 mm` operation is admitted under a `10 mm` budget. Both simulations run; ledger reservation is `9 mm`, while commanded total is `16 mm`. This is commanded exposure, not measured delivered water. The example is an internal writer contract violation; it does not establish an external attack route.

**First settlement rewrites other identity and period fields.** An `8 mm` reservation for date `2026-10-10`, season `S1`, device/zone and area `1` accepts first settlement with target `99`, changed device/zone, duration `20`, flow `3`, area `2`, date `2026-10-11`, season `S2`. Plot remains correctly bound, but the other canonical dimensions change. The journal records the original admission and incompatible settlement with no supported revision lineage.

The last receipt also accepts `40,000 L`, area `2 ha`, and delivered depth `4 mm`; these values are mutually inconsistent:

\[
I_{\mathrm{mm}}=\frac{V_{\mathrm{L}}}{10{,}000A_{\mathrm{ha}}}
=\frac{40{,}000}{20{,}000}=2\ \mathrm{mm}.
\]

This is a low-level settlement contract example. The normal dispatcher's conversion formula is not alleged to be wrong.

Evidence: `restart_absent_support_becomes_qualified`, `same_plot_envelope_rewrite`, `first_settlement_rewrites_envelope_and_period`.

Required correction: centralize an immutable admitted envelope for event, plot, device, zone, target, duration, flow, support, and accounting identity. Apply it at every writer and recovery transition, including first settlement. Preserve canonical `None` as a value in compatibility checks; do not interpret it as permission to accept any caller field. Separate observed outcomes from commanded identity. Qualified support/accounting changes need explicit revision provenance rather than silent overwrites. Validate cross-field volume/area/depth consistency when sufficient measurements are present.

Acceptance: changed fields are rejected or handled through a supported revision, old commanded exposure remains counted, the second `8 mm` request is blocked, canonical missing area cannot certify depth through an unqualified retry, and the settlement period/envelope stays compatible with admission.

### BV05 — failed ACK persistence leaves a caller-timing fallback

Sources: [ACK publication, lines 561–570](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/dispatcher.py#L561-L570), [active retry timing](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/dispatcher.py#L280-L299), [restart timing](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/dispatcher.py#L1187-L1238).

Healthy ACK publication is fixed. If the ACK write fails, submission logs a warning and returns with physical execution active, while the ledger retains `DISPATCHING` and no `actual_start`. A fresh caller's non-empty timestamp is only replaced when durable timing exists. It is therefore accepted when the durable fact is missing.

The controlled timeline places command/ACK eleven minutes earlier, fails only the acknowledged-start publication, and advances the owner's monotonic clock to `661 s`. A fresh duplicate supplies current time. Recovery grants `EXECUTING`, sends zero STOPs, and leaves the simulation running. The durable record still says `DISPATCHING` without start timing. This reproduces missing-timing promotion after a realistic publication failure, not overwriting an established durable timestamp.

Evidence: `missing_durable_start_accepts_caller_timing`. The fixture advances dispatcher/store wall time as well as the monotonic timer; no real eleven-minute wait is required.

Required correction: missing durable timing must remain unqualified on a fresh caller/restart. Do not use caller operational fields to synthesize a verified start. Preserve conservative expiration/unknown handling unless a qualified operation receipt supplies timing. Failed ACK publication must publish a degraded result/ownership boundary and recovery path, rather than merely logging while returning ordinary execution authority. Keep local safety available if persistence fails.

Acceptance: healthy ACK timing remains durable; ACK publication failure plus restart cannot renew the allowance; established timestamps stay authoritative; missing timing is either recovered from qualified controller evidence or treated conservatively.

### BV06 — terminal phase is hydrated but measurements are not

Source: [terminal restart fencing, lines 1152–1169](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/services/agribrain/irrigation_runtime/dispatcher.py#L1152-L1169).

A natural snapshot taken after ACK but before measured completion has the event schema's defaults `actual_volume_l=0.0`, `actual_duration_minutes=0.0`. The owner later completes with `40,000 L`, duration `6 minutes`, and `4 mm` derived delivery. Recovering the earlier snapshot now correctly returns `COMPLETED` and sends no STOP, but leaves its defaults untouched.

| Field | Returned recovered event | Canonical receipt |
|---|---:|---:|
| Actual volume | 0 L | 40,000 L |
| Actual duration | 0 min | 6 min |
| Delivered depth | Not rehydrated from receipt | 4 mm |

This does not damage the receipt or debit the ledger twice. It creates an inconsistent recovered result for downstream consumers. No downstream model contamination was directly reproduced here; that consequence is an inference if a consumer treats the returned `COMPLETED` event as authoritative.

Evidence: `terminal_recovery_does_not_hydrate_measurements`.

Required correction: terminal recovery must hydrate the full canonical operation/outcome view, including measured fields and their missingness/provenance, before returning. Avoid physical defaults for absent measurements. Verify that a warm completed result and recovered completed result describe the same operation and measured outcome.

Acceptance: stale snapshots recover `40,000 L` and `6 min` for this fixture; genuine missing values remain missing; no commands or additional debits occur.

## 5. Implementation order and closure gates

The repeated residual failures have a common cause: admission, restart, polling, completion, and ledger writers each implement portions of the same contract separately. The next implementation should share the contract checks across transitions.

| Order | Work | Acceptance target |
|---|---|---|
| 1 | BV01/BV02: shared command and completion eligibility | Per-event STOP respects current operation identity; unknown controller state cannot authorize completion |
| 2 | BV03/BV04: complete scalar, envelope, and candidate validation | Invalid support cannot publish; identity is immutable across every writer; admission exposure and receipt units remain consistent |
| 3 | BV05: durable timing and degraded ACK recovery | Failed ACK publication cannot create fresh timing authority or lose cutoff capability |
| 4 | BV06: canonical result hydration | Recovered terminal output equals the durable scientific/operational outcome |
| 5 | Integrated full acceptance | Separate processes, restart at every phase, real operation receipt semantics, fault injection, and package-specific criteria satisfy the open gates |

The minimum integrated matrix should combine normal and failed queries, healthy and failed writes, same/different/unknown operation identity, active/terminal/unsettled phases, and present/missing/invalid support. Include **the next transition after recovery**; testing only the immediate restart return misses BV01. Rejection must preserve prior durable bytes and accounting. Candidate publication should validate schema, full identity, journal lineage, and aggregate conservation together.

No separate estimate is invented for these repairs. Their effort depends on how much of the existing runtime is consolidated into shared transition rules. Run the independent counterexamples with expected results changed to the corrected contract, then run relevant repository regression checks and integrated multi-process acceptance. Passing unit probes alone does not complete a full-acceptance milestone.

## 6. Acceptance register and scientific limits

The pinned [task register](https://github.com/webClone/AgriWise/blob/16b470f900af4cfd69ebed140cfc09f29eedd69d/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md) has unchanged blob `8a564647af7e588802537817159117b349ff606b`. These tickets remain explicitly open:

| Ticket | Line | Status |
|---|---:|---|
| ST03-F08-FA | 406 | `[ ]` |
| ST03-F09-FA | 443 | `[ ]` |
| ST06-F16-FA | 796 | `[ ]` |
| ST06-F17-FA | 833 | `[ ]` |
| ST06-F18-FA | 870 | `[ ]` |
| ST06-F19-FA | 907 | `[ ]` |

The current runtime findings block command/recovery acceptance. The unchanged hydraulic profiles do not independently close all F08/F09 criteria. Full acceptance includes integrated software requirements as well as any required controller-specific hardware qualification; it is not merely waiting for field hardware.

R3's distinction between plan, command, measured delivery, reconstruction, missingness, and unknown outcomes remains relevant to agronomic state estimation. A controller status or unqualified support value cannot become applied irrigation evidence through a fallback. That is the scientific implication of BV02/BV04/BV06. This review establishes the local contract failures; it does not claim that all downstream agronomic, AI, economic, or training paths were re-audited.

## 7. Reproduction delivery

The accompanying ZIP contains fifteen independent simulation drivers, recorded result JSON/logs, pinned source identities, the production-only diff, relevant R3 excerpts, a rerun tool, and an evidence verifier. It excludes repository test/audit documents, production runtime copies, temporary quota ledgers/checkpoints, bytecode, and credentials.

`run_probes.py --repo /absolute/path/to/pinned/checkout` verifies the 430 expected source blobs before loading production modules. `verify_observations.py` validates recorded evidence without rerunning simulations. Successful verification confirms the corrected original cases and the six remaining counterexamples; it is not a passing-production-acceptance assertion.

The runtime used Python 3.12, NumPy 2.3.5, SciPy 1.17.0, Pydantic 2.13.5, and scikit-learn 1.8.0. Import diagnostic groups concern the exercised modules, not full application startup. The independent record supports crediting the seven original corrections and proceeding with BV01–BV06 repairs before closing runtime acceptance.

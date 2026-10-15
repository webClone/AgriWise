# AgriBrain corrective verification — 1d5f15b

**Date:** 13 October 2026. **Repository:** webClone/AgriWise. **Reviewed main:** `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`. **Parent:** `fcf726ca5eeafacf359d34fefbd7a452bf751709`. **Comparison:** `a2b0bf8923ca9f848083fdf702419ade889f3e38`.

## Result and implementation readiness

Several bounded repairs are independently verified. The new source fixes the stated nitrogen residual, preserves the finite positive 21 mm leaching ceiling, blocks the reproduced missing-weather/wind spray cases, improves non-noon hydraulic continuation/exact historical queries, improves ordinary nonce concurrency, rejects explicitly marked forecast inputs, and strengthens cache-write and MQTT query/emergency-stop handling.

**The reported bounded fixes do not close every cited counterexample.** The original 201.13/109.93 mm corrected-history failure and original forecast cache/missing-median counterexamples still reproduce. New nonce reservation ordering creates recoverability failures, stale-lock cleanup still admits two owners in a controlled process interleaving, and the pushed SR04 preflight does not establish distributed device exclusivity. All 52 full-acceptance checkboxes remain open in the exact published task register, as intended.

Continue bounded implementation, with the remaining end-to-end contracts below as the next targets. Preserve the verified improvements. Do not close F08/F09/F15/F23/F24/F37/F39 or the physical-operation packages from these slices alone. World Model/Omega experimentation can proceed on qualified objectives and explicitly typed data; operational prediction, causal-effect, training-label and action promotion require their own dependency and scientific gates. This review does not validate seasonal agronomic performance or field delivery.

## Evidence and scope

Both previously pending commits were fetched after the user supplied the pushed SHA. The final report uses actual code, replacing the earlier conditional models. Nine production files changed in 1d5f15b and four in its parent; all **13 changed files** and all **443 shared staged production copies** match the exact current Git blobs. Lane dependencies and extra startup copies have separate identities. No production or Git source was edited. Review-copy serialization was corrected to preserve exact bytes before verification; this did not change production semantics.

Six reviewers completed trajectory, decision, nonce/ingestion, bootstrap, forecast/ledger and MQTT/cache checks. The root added a real two-process device-admission probe and selected polling/unknown-query cases. Repository test files and audit conclusions were excluded as correctness evidence. The supplied **476+124=600** suite result is recorded as the user's report; those suites were not rerun or inspected here. A successful independent probe execution may intentionally reproduce a failed contract and must not be read as a production pass.

The scope is the repair delta and selected production consumers, with additional current trajectory checks. It is not a new exhaustive 52-package certification. The earlier whole-plan review remains the broader baseline; unaffected findings require closure under their existing cards. Normative inputs remain the master repair plan, execution addendum, task register and R3 requirement/scientific sections. The register's blob is `8a564647af7e588802537817159117b349ff606b`; all **52** full-acceptance rows are unchecked at this commit.

All controller, broker, registry/provider outages and database-like collaborators were simulated locally. The nonce and device-admission checks use actual independent OS processes and shared local files. No field actuator, live broker, vendor endpoint or production database was contacted. Supported service-image startup remains unverified where installed dependencies are missing. Numerical N fixtures fix only the stated upstream biomass/critical curve; selected AST fragments and interface seams are labelled in their reports.

## Claim-by-claim disposition

| Claimed repair | Verified current behavior | Remaining boundary |
|---|---|---|
| F37 package bootstrap | Real internal AgriBrain path insertion makes selected root-only L1/drone/worker imports pass | Bare and qualified packages still create different enum/dataclass identities; complete supported entrypoint acceptance remains open |
| F39 atomic nonce admission | Two-process same nonce accepts once; concurrent unique nonces both persist; restart replay rejects; independently reproduced 10-thread 1/9 result | Two stale recoverers can enter concurrently; registry/calibration/raw failures consume identity without evidence; raw corpus is in memory |
| F11 residual N | Controlled additional dose **86.67 kg/ha**, zero-deficit **0**, zero-applied **136.67** | Conservative pools, applied-event integration and invalid scalar qualification remain separate work |
| F15 finite hard cap | Recommended20/cap21 becomes recommended21/cap21 through the final gate | Invalid bounds can create negative/NaN/inconsistent confirmed rates; complete final feasibility remains open |
| F15 missing weather/wind | None/empty forecasts, empty rows and missing wind block; legitimate zero/safe wind remains usable | Units, finite/type checks, dates, gust/speed reconciliation and other required safety weather remain open |
| F08/F09 continuation and time identity | Non-noon continuation integrates the newly required date once; warm/cold forward summaries agree at **105.00 mm**; exact historical query preserves head | Original corrected-history observations disappear after cold reload; cancellation, scope and full predecessor content still fail |
| Empty CRPS helper | Empty quantile helper raises `ContractViolation`; a valid Gaussian alternative remains supported | Nonempty missing median still copies the observation into p50 and receives fabricated RMSE0 |
| Rejected forecast ingress | Six explicit metadata rejection cases block before publication | Later durable conflict still contaminates warm cache; retry/mutation/concurrent publication/evaluation identity remain open |
| ASMAE cache write rejection | New string status/reason/flag guards refuse the intended fresh negative entries | Six valid old-writer/new-reader negative cache records still return hits; read policy/schema migration is unchanged |
| SR01 MQTT | Matched running/fault query decoding and timeout UNKNOWN controls pass; emergency STOP rejects explicit running/not-stopped and bare OK | Ordinary STOP/START use weaker ACK rules; contradictions/fault retention/request lifecycle/deadlines remain open |
| SR02/SR03 ledger | Zero exposure remains readable with strict lower bounds; admitted target/exposure persist; canonical target wins at settlement | Local completed event can disagree with canonical receipt; physical ownership and projection remain separate acceptance |
| SR04 exclusivity | A later worker sees EXECUTING and does not send its START | Simultaneous idle samples permit two processes to START; polling the never-started event can cut off the live owner; UNKNOWN/query exception can still permit START |

## Priority findings and exact next fixes

The IDs below group interfaces and do not imply that every observation is newly introduced. Most are preserved gaps; some were newly exercised or arise from the new default reservation/cap behavior. Appendices retain detailed source references and classifications.

### V01 — F08/F09: corrected-history observation recovery still fails

Both warm and cold corrections begin with the same **120 mm** prior and hydraulic memory, use the same timestamps and integrate Jan 2 and Jan 3 **once each**. On Jan 2, both physical transitions end at **115.13 mm**. Warm recovery accepts three previously registered observations and adds a **116.44 mm analysis increment**; cold recovery accepts none. Final stores remain **201.13 versus 109.93 mm**. Re-supplying those exact registered readings to the identical cold checkpoint restores 201.13 mm.

This counterexample is missing evidence recovery, not repeated Day 1 integration. The pushed timestamp/guarded-continuation fix improves a different selected path and should remain. It cannot reconstruct observation payloads omitted from history. The actual `cp_step+1` branch is guarded; the earlier hypothetical unconditional model is not this implementation.

Current references: `layer3_decision/runner.py:1296–1346` restores `soil_observations=None`; `2509–2527` omits observations from history summary; corrected time/continuation is at `2087–2107,2154–2186`.

Repair: persist immutable dated observation identities, values/support/calibration/uncertainty/availability or resolvable durable references; rehydrate them under the original issuance policy. Normalize checkpoint dates at loading and preserve cancellation/supersession. Bind cycle/geometry recovery explicitly, including any legitimate soil carry-over lineage. Hash the full predecessor physical/memory/covariance content.

Acceptance: same-evidence warm/cold correction reproduces the same registered-observation count, flux/analysis receipts and posterior; callers need not resend already committed evidence. Include valid ISO cold cancellation, historical query, changing parameters/support and concurrent publication. Existing cancellation still raises `str has no attribute strftime`; cycle/geometry B still inherits A's state/events. These are separate F09 gates.

### V02 — F39: stale cleanup can steal a live lock

Two actual processes first read the same dead-owner lock token. A removes it and acquires a new live lock. B resumes its earlier cleanup and unlinks A's lock without verifying the lock it removes is still the dead token. B then enters while A remains inside. Observed maximum simultaneous critical-section owners: **2**, both processes exit cleanly. Normal two-process controls do pass; the race is specifically recovery/handoff.

Reference: `sensor_runtime/security.py:138–158`, especially `151–155`.

Repair: use an OS-backed interprocess lock or a store with atomic conditional ownership/fencing and crash recovery. A read-then-unlink stale check is not a conditional release. Merely checking the token again before unlink leaves another check/use race unless protected by a genuine atomic primitive. Preserve exact owner release, live-owner protection and the thread lock. Define the deployment/filesystem scope of the locking guarantee.

Acceptance: two stale recoverers, old-owner/new-owner handoff, process death, delayed release, timeout and concurrent writers never overlap ownership or erase the new owner. Keep same-nonce one-winner and unique-nonce no-loss controls.

### V03 — F39: nonce admission is not a recoverable evidence transaction

Actual default `detect_replay(..., reserve=True)` now reserves before registry and calibration validation. A temporary missing registry or calibration consumes the nonce with no raw evidence; restoring the prerequisite and replaying the same authenticated payload accepts **0**. Raw-store failure after reservation also leaves nonce/no evidence and blocks restored retry. After a new process starts, the nonce exists but raw storage has disappeared because it is process memory.

References: `security.py:235–266`; `sensor_runtime/ingestion.py:83–90,137–194`; `storage.py:5–20`.

Repair: durably capture authenticated raw evidence and bind the message ID to scope/payload digest and processing state. Publish canonical admission and replay receipt in a recoverable transaction/outbox. A retry must return or finish the same immutable attempt, with typed retryable versus permanent rejection outcomes; do not simply delete the nonce and allow a changed payload to reuse it. Preserve rejected/quarantined evidence and reason. Define whether IDs are globally unique or device/tenant-scoped before adding a scope key.

Acceptance: registry/calibration/normalization/raw-write outage followed by process restart produces one durable raw attempt and at most one canonical admission, with deterministic retry and no evidence loss. This closes the data foundation needed by the longitudinal corpus; locking alone does not establish F39.

### V04 — SR04/F16–F19: idle preflight is not a device resource claim

The root probe executes unmodified current dispatcher, actuator and quota code. Two OS processes with independent driver objects sample truthful idle replies before either START is sent. Both return **EXECUTING**; the simulated shared zone records **2 START commands**. The ledger has two EXECUTING claims for the same device/zone with empty owner tokens. A per-event quota transaction and per-object mutex do not reserve the conflicting hardware resource.

A separate sequential control sends only OLD's START; NEW is refused and held in STOP_REQUESTED with no active command and no latched device hazard. Polling NEW emits an emergency STOP against OLD's live simulated operation. OLD's durable record remains EXECUTING. The cutoff occurs in the STOP_REQUESTED reconciliation branch; this is not presented as a newly proved duration-watchdog branch failure.

With a forced current query returning UNKNOWN, or a query exception while the local cached state was ONLINE, submit still sends START and returns EXECUTING. The return from the added preflight is ignored, and UNKNOWN is not rejected by base validation.

References: `irrigation_runtime/dispatcher.py:408–450,501–507,678–683,830–945`; `actuator.py:205–260`. The new `hw.event_id/operation` matching is not a shared resource lease or a commissioned controller receipt contract.

Repair: atomically claim overlapping device/zone/resources with immutable event envelope and generation/fence before transport. Distinguish a known refused fresh operation from a potentially transmitted unresolved operation; the former must not gain authority to stop another owner. Reconcile ownership through the durable resource claim and qualified controller operation receipt. A new START requires admissible current state; an unknown existing operation remains a reconciliation obligation. Keep real device-hazard/global cutoff able to act independently of event-specific ownership.

Acceptance: simultaneous idle queries across replicas produce one physical START; a never-started/refused caller's polling/cancellation cannot stop the legitimate owner; delayed old START/STOP cannot act on a new generation; UNKNOWN and query exceptions preserve uncertainty without issuing a fresh duplicate-prone START. The controlled endpoint does not measure field dose or certify a particular firmware's behavior.

### V05 — SR01/F17/F18: MQTT command methods disagree about physical evidence

The emergency path is improved, but normal `send_command` still defines success as `status == OK`. Ordinary STOP_ZONE with `{status:OK,running:true,stopped:false}` succeeds, sets ONLINE and clears the active command. START with `{status:OK,running:false,stopped:true}` promotes EXECUTING. A normal explicit STOPPED reply is considered failure. Cancellation and late START fencing use the ordinary path.

`{status:RUNNING,running:false,stopped:true}` still becomes ONLINE/stop success. Fault status/nonzero fault code with stopped flags is ERROR in a query but emergency-stop success overwrites it to ONLINE. Positive cessation can confirm STOP while leaving a fault latched; it must not silently certify readiness for a new START.

References: `drivers/mqtt_driver.py:214–302,308–384,444–491`; `actuator.py:264–359,518–540`; `dispatcher.py:1335–1354`.

Repair: one strict typed, command-specific response contract for normal STOP, emergency STOP, fencing, START and query; preserve contradictory/unknown/fault states separately from acknowledgement and cessation. Require qualified operation attribution where supported. Marshal callback completion onto the owning event loop, validate payload shape/types before mutating cached state, clean request entries in all success/error/cancellation paths, and validate finite positive deadlines before publication.

Acceptance: all command methods agree on the same reply matrix; contradictory running STOP never clears ownership; an idle ACK cannot alone certify START; stopped-with-fault cannot erase the fault. Thread/cancellation/malformed-message/publish-failure/deadline controls leave no pending entries. These local probes use in-memory callbacks, not a broker or commissioned field controller.

### V06 — F23: durable forecast rejection still contaminates cache

Mean1 is committed. Another archive instance attempts mean99 under the same ID and receives `ContractViolation`; durable bytes remain mean1, warm retrieval returns99, cold retrieval returns1. Evaluation against99 receives RMSE0, and retrying the previously rejected candidate through the same instance succeeds from its cache.

The new metadata filter correctly rejects already flagged inputs. This durable-conflict rejection is another path: insertion still occurs before the durable conflict check. Nested mutation changes warm predictions without changing disk; incompatible concurrent inserts both accept; same-second evaluation IDs overwrite durable history.

References: `world_model/forecast_archive.py:379–418,422–425,510,524–530`.

Repair: immutable validated record → atomic conditional durable commit → committed readback/digest → cache publication. Failed attempts must not populate cache; cached records must be deeply immutable and read/evaluation eligibility must be enforced. Give forecast/evaluation identities complete content, scope, target, evidence and revision binding; reject unsafe ID path segments. Use append-only evaluation/correction lineage rather than replace-by-second.

Acceptance: conflicting failure and identical retry never expose the rejected candidate; warm/cold views agree; two incompatible publishers have one winner; caller mutation cannot change an issued forecast; distinct verifying evidence never overwrites another evaluation.

### V07 — F24: empty-helper repair does not remove observation-filled predictions

`compute_crps_quantiles({})` now rejects as intended. Valid mean/std forecasts with no quantiles remain supported. But nonempty `{p90:100}` evaluated against77 still fills p50 from the observation and yields **RMSE0** and coverage true. Its CRPS is **4.6**, not zero; the fabricated perfect point score is a different path from the repaired helper. Invalid quantile level `p-10` can produce CRPS−0.2, and negative Gaussian sigma remains accepted by the scored path.

References: `forecast_archive.py:173–199,202–214,490–508`.

Repair: validate finite predictive distributions, legal quantile levels/order, sigma domain and temporal/support eligibility. Required missing components yield unavailable scores with reasons. Never use verifying outcomes to fill issued predictions or interval endpoints. Score only emitted levels with their declared approximation. Preserve legitimate point-mass/valid Gaussian zero-error cases and distinguish prospective forecasts from hindcast reconstruction.

Acceptance: a missing median cannot earn a point score; invalid levels/std cannot produce a score; valid zero-error predictions remain valid; scoring is deterministic from the frozen issuance distribution and qualified verifying evidence.

### V08 — ASMAE cache: policy changed at writing but not reading

The exact prior writer creates six valid checksummed negative records. The actual new reader still accepts all six, even after the new writer refuses replacement. Rejected/aborted result_status, failed/REJECTED top-level status, `is_rejected=true` and uppercase TIMEOUT demonstrate the upgrade seam. Schema versions and the reader predicate are unchanged. This is a fixture-based migration proof; it does not assert that live caches contain these records.

References: `layer05_asmae/cache.py:643–713,716–791`.

Repair: apply the same normalized eligibility policy to both read and write, or invalidate old policy versions and reject incompatible artifacts. Keep diagnostic/unavailable caching policy explicit and preserve per-variable permissions. Retain the strong typed full-input hashing, JSON/NPZ checksum/schema/shape validation and clean corruption misses already demonstrated. This replaceable cache is separate from forecast archives and historical scientific publication.

Acceptance: every new-writer-refused negative migration fixture becomes an explicit miss/unavailable record under the new reader; valid diagnostic-only artifacts and content integrity controls continue to work. No Enum-valued ASMAE producer was found, so Enum cases remain defensive API checks rather than asserted production regressions.

### V09 — F15: final weather and hard-envelope validation is incomplete

The positive finite cap and missing-wind fixes pass. Remaining actual final-gate witnesses include wind10 marked m/s being accepted as numeric10 instead of36 km/h; NaN rain and Boolean/negative-infinite wind/rain; simultaneous speed5/gust20 bypassing the scheduler's15 km/h gust limit; and row-order-dependent dates. Required intervals are still computed from list position rather than the forecast date.

Under invalid hard envelopes, max_safe−1 can create a **negative recommended rate after the earlier nonnegative check**, while the card remains allowed and CONFIRMED. NaN cap leaves23.1 CONFIRMED; min_safe25/max_safe21 confirms21 without rejecting the inconsistent interval. A zero cap is ultimately clamped correctly by the final gate; do not report that working final control as a violation. None/string cases can raise production TypeErrors and are not qualified unavailable receipts.

References: `engines/spray_drift_gate.py:18–44`; `scheduler.py:141–194`; `engines/salinity_leaching.py:61–69`; unchanged `schema.py:209–216`, `invariants.py:50–77`, `runner.py:560–566` under `layer8_prescriptive`.

Repair: finite non-Boolean typed rates and consistent immutable min/max/budget envelopes; normalize weather units and date/interval support once; evaluate speed/gust and required rain/temperature under one policy. Apply a final validation after every adjustment/repair so a clamp cannot create another invalid value. Missing prerequisites yield blocked/measure/unavailable results, not fabricated benign weather.

Acceptance: identical dated rows reordered select the same interval; units/finite/type/missingness matrices agree at drift, scheduling and final publication; invalid bounds never yield an allowed rate. These invalid-envelope fixtures prove a function-boundary omission, not a commissioned actuator receiving negative doses.

### V10 — F37 and canonical publication: narrow success does not close identity/projection

The real package initializer inserts the internal AgriBrain root, allowing selected clean imports. It still permits bare and qualified drone packages with distinct MissionType and MissionIntent classes, including false cross-isinstance. One installed namespace and consistent imports remain necessary. Missing dotenv/FastAPI/Torch prevent broader entrypoint certification in this reviewer environment; those are environment limitations, not asserted production bugs.

SR03 canonical target storage passes, yet completion can return a stale local target3/area1/delivery2mm while its durable receipt contains target10/area2/delivery1mm for the same measured20,000L. This is a controlled mutable local-event/status-stub seam, not an external exploit or measured physical operation.

References: `services/agribrain/__init__.py:1–6`; `layer0/perception/drone_rgb/structural.py:17–20`; `irrigation_runtime/dispatcher.py:1225–1286`; `safety.py:1133–1188`.

Repair: unify module identity at package and entrypoint imports; return/hydrate the exact committed canonical receipt into event/history/callback/public projections, retaining support and measurement missingness. Acceptance includes fresh entrypoint identities and equality of published outcome with its durable canonical record.

## Next implementation sequence

| Lane | Immediate bounded work | Full-package acceptance retained |
|---|---|---|
| Scientific trajectory | Persist/rehydrate observations, normalize cold dates, explicit cycle/geometry transfer, full predecessor hash | Stage3 F08/F09 after F02/F03 and their declared prerequisites |
| Ingestion | OS-safe locking plus durable raw/admission/replay processing transaction | Stage3 F39 after F01/F09 |
| Physical execution | Shared resource admission/fences, unknown-state policy, qualified ACKs across all stop/start paths | Stage6 F16–F19 after relevant F01/F16/F17 |
| Prescriptive decisions | Shared typed weather interval and immutable valid envelope; final post-adjustment validation | Stage5 F15 after F01/F06/F14 |
| Forecast evidence | Durable-first immutable publication, complete evaluation identity, unavailable missing scores | Stage8 F23/F24 after F21/F22/F13 and declared dependencies |
| Runtime/publication | One Python identity; same read/write cache policy and migration; canonical receipt projection | F37 stage0, cache integrity slices, F38/F40/T11 at their full stages |

Implement complete interface contracts and their consumers, instead of adding another isolated flag at one method. Independent contained fixes can progress in parallel; full-package acceptance still follows the addendum. F11's arithmetic slice can be recorded as verified without claiming conservative nutrient pools or calibrated field dose. The 52-package engineering estimate is not recalculated from this review.

## Evidence bundle and limitations

The bundle includes actual-source lane reports, exact production identities, independent scripts/results, controlled process receipts, acceptance-register check and reproduction layout. It omits production code copies, repository tests/audits, runtime fixture stores, credentials and preliminary models. A helper can reconstruct exact old/current source bytes from an existing repository's Git objects into a separate workspace without modifying the checkout or contacting services. The helper workflow is structurally checked; the lane probes themselves were executed in the recorded review layouts.

The detailed reviewer appendices distinguish corrected slices, preserved defects, newly exercised boundaries, defensive API cases and empirical work. Use their exact acceptance criteria; neither 600 reported tests nor a successful focused probe execution proves full scientific capability, process fencing or field commissioning.

## Detailed actual-source reviewer appendices

The following six reports preserve their scope, source identities, positive controls and remaining acceptance cases. Related observations overlap; their row counts are not a unique-defect count or a passing production-test total.

## Appendix 1: trajectory

### Actual pushed repair review — trajectory lane

Current source: `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`, parent `fcf726ca5eeafacf359d34fefbd7a452bf751709`; comparison source `a2b0bf8923ca9f848083fdf702419ade889f3e38`. The actual pushed code is now available and reviewed. Earlier unavailable-source conclusions and the unconditional scheduling MODEL are preliminary history, not claims about this implementation.

The pushed code corrects the residual-N arithmetic and the sampled non-noon historical timestamp/continuation behavior. It does **not** close the original registered-observation cold-correction failure, valid-date cold cancellation, cycle/geometry scope, or full predecessor-content criteria. All 13 assigned master-plan cards are covered below; no whole-package acceptance is certified.

#### Verified corrected boundaries

For runs at 06:00 UTC with unchanged explicitly dated canopy/weather, old production falsely replays Jan 2 when advancing to Jan 3, and Jan 3 when advancing to Jan 4. New production reuses the stored historical timestamp: Jan 3 continuation executes only Jan 3, and both warm/cold Jan 4 continuation execute only Jan 4, producing identical complete summaries at **105.00 mm**. This is a real, bounded improvement. Old replay starts from the correct earlier prior, so its final forward storage also happened to be 105 mm; the observed correction is unnecessary recomputation/temporal identity, not a newly proved net double water extraction.

The exact cold Jan 2 query after a Jan 3 checkpoint now reproduces the original **114.13 mm** full summary without moving the operational head. The same old-source query raises an immutable-checkpoint ConcurrencyConflictError. Raw actual-code comparisons are `gates-old.json` and `gates-new.json`.

The actual new start-date branch is guarded by earliest_invalid_day and checkpoint-versus-target date checks. It preserves the earlier invalidation branch for historical corrections. The preliminary unconditional `cp_step+1` MODEL is therefore **not this patch** and is superseded. The selected continuation fixture primarily demonstrates the historical timestamp fix; it does not individually isolate every newly added checkpoint-fallback branch.

The declared N case now returns **86.67 kg/ha**, replacing the prior 36.67, with a zero-deficit control of **0**. Only the double-credit formula boundary is accepted here; actual application feed and conservative N pools remain open.

- [services/agribrain/layer3_decision/runner.py:2087–2107](https://github.com/webClone/AgriWise/blob/1d5f15bfe13cd9f55b9028508d82e0f8b95fb249/services/agribrain/layer3_decision/runner.py#L2087-L2107) — blob `916918e41a00f68c797d49867659b64aed8c8a22`.
- [services/agribrain/layer3_decision/runner.py:2154–2186](https://github.com/webClone/AgriWise/blob/1d5f15bfe13cd9f55b9028508d82e0f8b95fb249/services/agribrain/layer3_decision/runner.py#L2154-L2186) — blob `916918e41a00f68c797d49867659b64aed8c8a22`.
- [services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py:159–165](https://github.com/webClone/AgriWise/blob/1d5f15bfe13cd9f55b9028508d82e0f8b95fb249/services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py#L159-L165) — blob `7d879784ebcbc4830d306327a22770c02c2fb2c0`.

#### Original cold-correction counterexample remains

The exact original fixture is rerun on the pushed source. Scope is tenant_A/scientific/p/cycle_A/geometry_A. The observation `[.4,.4,.4]` is registered at **Jan 2 12:00 UTC** during the seed run. Both correction requests target **Jan 3 12:00 UTC**, receive identical dated canopy/weather with Jan 2 rain revised from 0 to 1 mm, and omit the already registered observations. Both recover the same serialized initial soil (**120 mm**) and declared hydraulic memory. Instrumentation confirms both integrate Jan 2 and Jan 3 **once**, at identical timestamps.

| Step | Initial water | Physical final water | Accepted readings | Analysis increment | Posterior water |
|---|---:|---:|---:|---:|---:|
| Warm Jan 2 | 120.00 | 115.13 | 3 | +116.44 | 231.57 |
| Cold Jan 2 | 120.00 | 115.13 | 0 | 0.00 | 115.13 |
| Warm Jan 3 | 231.57 | 201.13 | 0 | 0.00 | 201.13 |
| Cold Jan 3 | 115.13 | 109.93 | 0 | 0.00 | 109.93 |

All water quantities are mm. Thus **201.13 versus 109.93 mm persists** because the cold replay loses accepted evidence. Re-supplying the same registered Jan 2 readings to an otherwise identical cold checkpoint copy restores **201.13 mm exactly**. This isolates the missing-evidence mechanism. Hash/time repair cannot itself reconstruct absent values, observation support and analysis lineage.

The pushed checkpoint still omits soil observations from history_summary; recovery still sets soil_observations=None. References:

- [services/agribrain/layer3_decision/runner.py:1296–1346](https://github.com/webClone/AgriWise/blob/1d5f15bfe13cd9f55b9028508d82e0f8b95fb249/services/agribrain/layer3_decision/runner.py#L1296-L1346) — blob `916918e41a00f68c797d49867659b64aed8c8a22`.
- [services/agribrain/layer3_decision/runner.py:2509–2527](https://github.com/webClone/AgriWise/blob/1d5f15bfe13cd9f55b9028508d82e0f8b95fb249/services/agribrain/layer3_decision/runner.py#L2509-L2527) — blob `916918e41a00f68c797d49867659b64aed8c8a22`.

#### Adjacent gates and remaining findings

- **F09 cancellation:** valid ISO `2026-01-02` appears in both stored event and version-2 cancellation input. Cold cancellation still logs str has no attribute strftime, returns no state, and leaves applied version 1 durable. This is not malformed input.
- **F09 scope:** cycle/geometry B still hydrates A's previously applied 20 mm water and history/events for the same tenant/namespace/plot: B storage **458.31 mm** versus **448.75 mm** in fresh B. This proves cycle/geometry leakage, not cross-tenant leakage.
- **F08 full content:** evaporation states with equal days but different wetted fractions/surface stores still collide at digest `6fa154884ced27b53b0b89b6`; conductivity-change control is distinguished. Digest verification is an AST-extracted production function, not a claimed whole-request stale result.
- **F01/F02:** temporal admission still accepts NaN/infinity; dictionary PRIOR/FORECAST/SYNTHETIC becomes observed and explicit zero reliability becomes weight 1. Jan 2 weather can still consume a Jan 10 available revision.
- **F05/F10:** positional depth support and covariance integration remain absent; the exact L4 branch still replaces actual profile retention/storage with generic scalars and 0.7*TAW. The L4 probe is an exact AST branch with real output schema, not full L4 runner execution.
- **F07/F34:** incomplete historical canopy still fills missing coordinates from later endpoint canopy; unknown/authorized/commanded/in-progress/omitted irrigation status still enters historical water as delivered.
- **F11/T01:** repaired residual arithmetic does not establish conservative nutrient stocks/actual exposures or a consumed water/N feedback receipt for subsequent vegetation growth. T01 remains a capability target.

Detailed current-source findings, requirements, precise code refs and next acceptance steps remain in `coverage.json`. Selected positive controls still pass for finite soil filtering, integrated realized flux and explicit analysis increment, original geometry rejection, exact-date endpoint weather, evaporation memory, identical dated-canopy daily/sparse replay, simple cold replay/idempotence, and two-process local CAS. Those controls do not establish corrected-observation recovery or distributed fenced lease correctness.

#### Full assigned-card coverage

| Package | Stage | Current assessment |
|---|---:|---|
| F01 | 1 | partial boundary fixed; acceptance open |
| F02 | 1 | partial time filter fixed; acceptance open |
| F03 | 2 | sampled boundary pass; full acceptance unverified |
| F04 | 2 | original validation cases fixed; serialization boundary open |
| F05 | 4 | open depth and covariance integration |
| F06 | 3 | endpoint substitution fixed; forcing qualification open |
| F07 | 3 | memory and complete fallback fixed; coordinate fallback open |
| F08 | 3 | historical timestamp identity fixed; full content invalidation open |
| F09 | 3 | bounded continuation and exact query pass; observation recovery cancellation scope open |
| F10 | 4 | open schema boundary defect |
| F11 | 4 | residual formula fixed; conservative pool and actual application integration open |
| F34 | 7 | open exposure lifecycle and accounting |
| T01 | 12 | capability target not established |

#### Evidence and acceptance scope

All 23 assigned targets and four reused dependencies are blob-verified against the new pinned tree. Dependency copies were normalized only by removing an extra terminal newline until exact current-tree blob identity matched; the prior artifacts were left unchanged. Fourteen focused probe groups completed without harness errors, followed by instrumented same-prior correction and separate old/new forward/query processes. Production capture wrappers preserve the original result and only record it. N fixtures replace only biomass/critical curve with the master-plan case. No repository suite/audit result is used as production evidence, and no production or Git file was edited.

A suite covering unchanged continuation or requiring callers to resend all observations can pass while registered-observation recovery fails; the current controls demonstrate this distinction directly. F08/F09 remain stage-3 integration packages under AB-DAT-003/011/012/013, AB-AGR-006/007 and AB-ARC-008. F11's stage-4 formula slice passes, while AB-AGR-008/010 pool/application integration remains open. The master-plan R1 coupled-trajectory gate is not closed.

Reproduce from the workspace root: `PYTHONDONTWRITEBYTECODE=1 python repair-1d5f15b-review/trajectory/probe.py`, then `claim_probe.py`, and `gate_probe.py old` / `gate_probe.py new` at the same path. Raw results and exact manifests accompany this report.



## Appendix 2: decision

### Actual F11/F15 repair review at 1d5f15b

The declared narrow F11 and F15 repairs are now verified against actual production source at `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`, parent `fcf726ca5eeafacf359d34fefbd7a452bf751709`. These results supersede the earlier conditional MODEL conclusions for the checked files. They do not close either full master-plan package.

71 focused groups exercised exact production nitrogen, drift, leaching, scheduler and final invariant functions. All 11 source/dependency files match the new pinned Git tree, including unchanged dependencies read from the previous source snapshot. The F11 controlled fixture fixes only the upstream biomass and critical-N helpers to the stated 5 t/ha and 2% assumptions; the actual `analyze` body executes unchanged. F15 uses actual ActionCards with two distinct non-blocked evidence families, so evidence-family gates do not conceal constraint failures. No shared production files, repository tests, external services, field hardware or Git changes were used. Six malformed-input cases produced recorded production TypeErrors; these are boundary outcomes, not harness failures.

#### Repairs confirmed

| Check | Actual new result |
|---|---|
| F11 residual case: 5 t/ha biomass, critical N 2%, applied 50 and soil 30 kg/ha, recovery 0.60 | **86.67 kg N/ha** additional demand; the old 36.67 double subtraction is removed. |
| F11 zero deficit and zero applied positive controls | 0 and 136.67 kg N/ha respectively. |
| F15 finite leaching case: recommended 20, cap 21 mm | Recommended21/cap 21 mm, preserved through final invariants. |
| F15 absent/empty forecast, `[{}]`, missing/None/empty-string wind | Combined drift→scheduler→final gate returns blocked action and BLOCKED schedule. |
| Measured zero/safe 5 km/h wind | CONFIRMED; legitimate zero is preserved. |
| Wind 30 km/h and gust-only 20 km/h | BLOCKED. The scheduler now uses gust if speed/kmh is absent. |
| Recommended 0/cap 0 mm | Remains 0. With a positive candidate and cap 0, leaching temporarily returns 23.1, but the final invariant correctly clamps it to 0. This is not a final zero-cap violation. |

Source: `layer4_nutrients/photosynthesis_nue/engine.py:131–136,159–165` (blob `7d879784ebcbc4830d306327a22770c02c2fb2c0`); `layer8_prescriptive/engines/spray_drift_gate.py:29–40` (`44013cc6239c4a6c1b57b5f8e39222c0a125e535`); `engines/salinity_leaching.py:61–69` (`ddace11be570390ed3b60dd543852c8d5a97e481`); `scheduler.py:149–157` (`c82ee5c2c7394864ba35342eff74e7a1461a5180`). All paths are under `services/agribrain/`.

#### Reproduced remaining boundaries

**P0 — Invalid hard envelopes can survive the actual final gate.** With `max_safe=-1`, leaching returns 23.1 and retains−1 as cap; the final invariant subsequently sets the rate to−1 after its earlier nonnegative pass. The action remains allowed and CONFIRMED. With `max_safe=NaN`, recommended23.1 survives CONFIRMED with an empty invariant receipt. `min_safe=25, max_safe=21` returns recommended21 and remains CONFIRMED without detecting the inconsistent range. A negative recommendation is clamped to 0, but a declared minimum5 is still violated. Infinite and Boolean ceilings are also accepted at this boundary. A None ceiling raises TypeError. These fixtures enter an invalid envelope directly; they demonstrate absent validation at these functions, not a commissioned actuator accepting such inputs.

Source: new `salinity_leaching.py:62–69`; unchanged and newly hash-verified `layer8_prescriptive/schema.py:209–216`, `invariants.py:50–77` (blob `aa33a4a16e15f1bf6204fddd6bbfeee849651b57`). `runner.py:560–566` invokes this final gate. Closure requires finite non-Boolean quantities, consistent finite bounds, immutable original dose/budget envelopes, and a final pass whose repairs cannot create another violation.

**P0 — Presence checks do not qualify weather.** NaN rain, negative infinity wind/rain, Boolean wind/rain, missing rain and missing temperatures all remain CONFIRMED through the actual final gate. `wind_speed=10` with a supplied `m/s` unit remains CONFIRMED as numeric10; its physical speed is 36 km/h. Standalone NaN wind and positive infinity wind are blocked by drift, and positive infinity rain blocks scheduling—retain those working controls. The scheduler alone accepts NaN wind. Mixed rows can also select a row with NaN gust: an earlier speed 20 row passes the drift 25 threshold but fails the scheduler 15 threshold; a later speed 5/NaN-gust row then confirms. This demonstrates missing finite/type/unit/slot qualification, not a universal claim that every invalid wind case passes.

Source: `spray_drift_gate.py:18–27,42–44`; `scheduler.py:149–178`; unchanged `invariants.py` has no final weather qualification. Closure requires normalized units, finite supported values and mandatory safety variables for the actual selected interval, with explicit unavailable/measurement status when they are absent.

**P1 — Date and gust policies remain inconsistent.** Rows dated Oct 15 (safe) and Oct 14(speed 20) schedule Oct 13 when forward and Oct 14 when reversed. The safe date Oct 15 is ignored because dates still derive from list position. Gust-only20 is correctly blocked, but simultaneous speed 5/gust 20 confirms: the scheduler chooses speed first, whereas drift prioritizes gust and uses 25 rather than 15 km/h. Numeric-string wind/rain and the scheduler-only empty-string wind case raise TypeErrors, rather than qualified weather-unavailable receipts.

Source: `scheduler.py:31,141–150,164–170,180–194`; `spray_drift_gate.py:9,18–22`. Closure requires one dated per-slot policy, explicit conversion/validation and row-order-invariant selection.

**F11 scientific package remains open.** NaN/Infinity applied N still return nonfinite actual concentration, capped NNI 3 and zero additional demand; negative applied N produces 186.67 additional demand in the controlled fixture. The formula repair does not reconcile cumulative application, measured recovered plant N, available soil N, mineralization, uptake and losses. The unchanged runner still supplies applied N 0 to this call and sums cumulative mineralization, BNF and residual credits; separate heuristic budgets and loss estimates do not establish conservative stock accounting.

Source: `photosynthesis_nue/engine.py:131–143,159–165`; unchanged `layer4_nutrients/runner.py:459–475,482–489,553–578`. The conventional arithmetic fix is confirmed; calibrated crop demand and conservative pools are not established by that fixture.

#### Master-plan disposition

- **F11, stage 4:** `ST04-F11-01` and the controlled 86.67/zero criterion pass in the checked scope. `ST04-F11-02..04` and `ST04-F11-FA` remain open for semantic pool definitions, stock reconciliation, timing/formulation and recovery uncertainty. R3 AB-AGR-008 (`R3_current_scientific_sections.txt:874–876`), AB-AGR-010 (`882–884`).
- **F15, stage 5:** The reproduced missing-forecast/wind cases and finite positive-cap leaching case are corrected. `ST05-F15-01/04` and full `ST05-F15-FA` remain open; steps 2/3 have limited fixes, not full weather/range/resource qualification. R3 AB-DEC-003 (`1076–1078`), AB-ECO-003 (`1088–1090`), AB-EXE-001 (`1106–1108`). Legal/resource/budget integration, all later modifiers and actual operational commissioning were not exercised.

Artifacts: `actual_decision_probes.py`, `actual-decision-results.json`, `coverage.json`. This report certifies the stated source-level slices and identifies the remaining reproduced gates; it does not certify live execution or full F11/F15 completion.


## Appendix 3: ownership

### Actual F39 nonce repair review — 1d5f15b

**Normal shared-store replay admission is repaired in the exercised cases. Full F39 acceptance remains blocked by stale-lock recovery and evidence-commit ordering.** This review executes actual source from `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`; the earlier model-only/unavailable-source qualification no longer applies to this commit.

#### Provenance and reproduction

```bash
PYTHONDONTWRITEBYTECODE=1 python /workspace/scratch/de6bc2428cec/repair-1d5f15b-review/ownership/actual_nonce_probes.py
```

Final run: exit 0, all assertions passed. Results: `actual-nonce-results.json`. Every imported production sensor module and SensorQA schema was hash-matched to the new Git tree. Main blobs: security `8ce69fbe0aeb37e6698e050c43d8a47572d98aef`, unchanged ingestion `b456258123b15f8587b032c2cf62d11ba3c30402`, unchanged storage `23de3ea521c183e8e791014f0bd3f1cde8ccfb20`. Source paths and ten import blob hashes are recorded in the results.

Real OS processes use isolated local nonce files. Test barriers/delays control existing scheduling boundaries; local fixture registry/calibration and a controlled writer outage are injected. No lock implementation or lock ownership decision is modeled. No production/Git edits, repository suites/audit proof, vendor/controller/field operation were used. The initial stale-race logger was corrected to capture A's token before releasing B; the final run is complete.

#### Positive controls now independently verified

| Actual control | Result |
|---|---|
| Two processes, same nonce through `ingest_sensor_payload` | One returned one reading; the other returned zero; one durable nonce |
| Two processes, unique A/B nonces through ingestion | Both returned one reading; both durable registrations survived |
| Fresh-process replay after each case | Replay rejected; all six ingestion/restart processes exited 0 |
| Ten concurrent `check_and_reserve_nonce` threads | One winner, nine blocked; durable singleton |
| `reserve=False` | Read-only check consumed no nonce |
| Single stale/dead lock owner | Recovery succeeded |
| Old lock belonging to a living process | Acquisition timed out; living token remained |
| Release after token replacement | Old owner preserved the replacement token |

The normal unchanged ingestion `detect_replay` followed later by `save_nonce` works; the second write is idempotent for the same nonce. The former normal-case same-nonce double acceptance and unique-nonce lost-update traces are not reproduced on this commit. These controls cover processes sharing the same filesystem path, not independently provisioned replica volumes or every failure interleaving.

#### Reproduced remaining failure: two stale evictors acquire concurrently

The actual lock reads a stale lock token and verifies its PID is dead, then unlinks by pathname without ensuring the pathname still contains the examined token. Controlled schedule:

1. A and B both read the same stale/dead owner token and perform the real dead-PID check.
2. A unlinks that old file, acquires a fresh lock, writes its live owner token and enters the critical section.
3. B resumes its already-decided unlink, removing A's fresh token based on its earlier dead-owner read.
4. B creates its own lock and enters while A is still inside.

The two actual OS processes recorded **two simultaneous critical-section owners**, then exited 0. This proves a mutual-exclusion violation in recovery; this particular probe does not assert a lost nonce write or field effect. The normal-case process controls pass because they do not take the stale-eviction branch.

Exact references: `sensor_runtime/security.py:138–158`, especially `151–155`; protected admission `218–254` relies on this lock. Token matching on release (`166–172`) does not protect stale deletion during acquisition. F39 stage 3; R3 AB-ARC-008 and AB-DAT-003/011/013.

Repair must make stale recovery ownership-safe across competing recoverers. Do not assume a token comparison followed by ordinary unlink is itself atomic; validate the actual recovery protocol/OS primitive under this schedule. Keep the passing living-owner/dead-owner/release-token controls.

#### Actual integration failures: nonce consumed before evidence eligibility/commit

The new default reserve commits the nonce and adds the seen marker before baseline ingestion performs registry, decoder and calibration validation. Actual results:

| First-call condition | First result | Persisted nonce/raw evidence | Restored retry |
|---|---|---|---|
| Valid message | One accepted reading | Nonce and raw record present in that process | Zero, correctly duplicate |
| Registry unavailable | Zero readings | Nonce present; no raw record | Zero after registry restored |
| Calibration unavailable | ValueError | Nonce present; no raw record | Zero after calibration restored |
| Controlled raw-store outage | OSError | Nonce present; no raw record | Zero after writer restored |

Retries clear local rate/seen state; rejection still follows from the persisted nonce. Registry/calibration failures therefore confirm the earlier default-reserve model with actual source. The raw-store ordering defect already existed in the prior baseline and remains after nonce locking. There is no reservation/commit/rejection state or recovery receipt in the nonce set to distinguish these incomplete transactions.

References: new `security.py:235–254,257–266`; unchanged `ingestion.py:83–90,137–170,193–194`. F39 stage 3; AB-DAT-001/003/011, AB-ARC-008/009. Reservation must be recoverable and bound to evidence eligibility/commit; avoid dropping a valid retry silently while also preventing duplicated scientific effects.

#### Durability and scope limits remain

The fresh restart processes correctly reject the persistent nonce but contain no raw message from the earlier accepted process. This is expected from unchanged `sensor_runtime/storage.py:5–20`, which stores mutable objects in module dictionaries/lists. Passing replay rejection does not demonstrate a durable evidence corpus, and F39's raw/normalized persistence criterion remains unmet.

The actual store records only nonce strings, with no tenant/device/protocol/payload or transaction-receipt binding. Two independently registered devices using the same supplied device-local sequence ID returned reading counts `[1,0]`; only the global ID was persisted. This establishes implementation behavior, while whether device-local IDs are permitted must be settled by an explicit protocol uniqueness contract. It is not presented as an independently demonstrated foreign-tenant exploit. Same-key/different-payload conflict and scoped identities need dedicated acceptance.

Bounded cache/rate/lock retention, geometry-epoch invalidation and durable immutable telemetry requirements were outside this focused rerun; no new closure is claimed for them. They remain in the master-plan F39 scope. The supplied execution addendum places full F39 after F01/F09 at stage 3 and distinguishes an early nonce slice from whole-package acceptance.

#### Next acceptance

1. Re-run normal two-process same/unique nonce and ten-thread controls after any lock change.
2. Re-run the concrete two-stale-evictor schedule; at most one owner can enter. Also test interrupted owner-token publication, slow living owners, PID/permission/namespace behavior and bounded recovery.
3. Make registry/calibration/decode/evidence-write interruptions recover through explicit transaction states/receipts; restart at every reserve/write/commit boundary without duplicate effects or missing evidence.
4. Persist immutable raw and normalized evidence with acceptance receipts; verify original evidence survives a fresh process and is retrievable on idempotent replay.
5. Define authenticated scope and payload identity, replay window/retention and shared-replica storage topology; verify conflicts explicitly rather than treating every repeated global string as the same scientific message.

The proposed normal-case repair is now positively verified under isolated controls. The lock recovery and evidence recovery failures are actual-source findings, so full F39 remains open.


## Appendix 4: platform

### Actual bootstrap repair review — F37

The actual `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249` bootstrap improves clean import availability: GaussianMixture, qualified L1 engine, drone dispatcher and background-worker module all load in fresh processes with only the repository root initially on Python’s path. F37’s full acceptance remains open because bare and qualified callers still get different enum/dataclass identities, and the declared service/CLI runtime has not been validated.

This now reviews available production code, rather than the earlier described-effect model. The new commit’s parent is `fcf726ca5eeafacf359d34fefbd7a452bf751709`, whose parent was the earlier `a2b0bf8923ca9f848083fdf702419ade889f3e38` baseline. The review copy contains 507 source files whose Git blobs all match the new commit, including the actual bootstrap blob `808a45111b8a1204532b46069ec6dc77982f6794`.

The repair at [`services/agribrain/__init__.py:1-7`](https://github.com/webClone/AgriWise/blob/1d5f15bfe13cd9f55b9028508d82e0f8b95fb249/services/agribrain/__init__.py#L1) inserts the internal `services/agribrain` directory into `sys.path`. It does not insert the repository root or alias entries in `sys.modules`. Once the qualified package is imported, the insertion makes existing bare imports reachable, including [`layer1_fusion/adapters/sentinel2.py:20`](https://github.com/webClone/AgriWise/blob/1d5f15bfe13cd9f55b9028508d82e0f8b95fb249/services/agribrain/layer1_fusion/adapters/sentinel2.py#L20). This explains the passing clean L1 import and supersedes the previous root-only model’s failure as an account of the actual repair.

| Fresh actual-code experiment | Result | Evidence scope |
|---|---|---|
| Root initially on path: GaussianMixture/segmentation | Pass; GaussianMixture from sklearn.mixture | Actual module import, no segmentation computation. |
| Root initially on path: qualified L1 engine | Pass; internal AgriBrain root added by actual bootstrap | Actual import graph, no science execution/provider calls. |
| Root initially on path: qualified drone dispatcher | Pass | Optional-backend review copy; no configured driver/controller commissioning claim. |
| Root initially on path: qualified drone_mission followed by bare drone_mission | Both pass; MissionType identity false; MissionIntent identity false; cross-namespace enum isinstance false | Actual namespace identity defect persists after bootstrap. |
| Both roots initially on path: bare drone_mission followed by qualified drone_mission | Same false identity/isinstance results | Changing load order does not unify classes. |
| Qualified background-worker module | Pass; worker not launched | Cold module loading only, not restart/job lifecycle acceptance. |
| Service module and CLI `--help` | Both blocked by missing installed python-dotenv | Environment gap, not a demonstrated production-source defect. |
| Two relevant annotation consumers | Background-worker hints fail on missing List; Kalman hints fail on missing np | Definitions import; runtime introspection remains unresolved. |

The remaining F37 identity issue is concrete. Production code still exposes the same files through distinct names: `services.agribrain.drone_mission.schemas` and `drone_mission.schemas` are separately registered. Structural perception uses the bare enum amid qualified neighboring imports at [`structural.py:17-20`](https://github.com/webClone/AgriWise/blob/1d5f15bfe13cd9f55b9028508d82e0f8b95fb249/services/agribrain/layer0/perception/drone_rgb/structural.py#L17). Both enum and dataclass class objects differ. This verifies the master card’s identity criterion remains unmet; it does not claim every enum equality check or drone operation fails.

The two bounded annotation checks preserve the F40 distinction between definition and consumer resolution: [`background_jobs.py:21,147`](https://github.com/webClone/AgriWise/blob/1d5f15bfe13cd9f55b9028508d82e0f8b95fb249/services/agribrain/layer05_asmae/background_jobs.py#L147) lacks List in module globals, and [`kalman_engine.py:159`](https://github.com/webClone/AgriWise/blob/1d5f15bfe13cd9f55b9028508d82e0f8b95fb249/services/agribrain/layer0/kalman_engine.py#L159) references np in its return annotation while importing NumPy locally within the method. These introspection failures were rerun against new-SHA source. They are not attributed to the bootstrap as newly introduced regressions, and no broad F40 re-audit is claimed.

F37 step assessment: (1) corrected GaussianMixture import passes; (2) optional dispatcher imports remain isolated at module loading; (3) the availability shim is now verified but single installed namespace/class identity is incomplete; (4) selected fresh public/worker module imports pass, while supported service/worker/CLI entrypoint acceptance still requires the declared image and extras. Full stage 0 acceptance (ST00-F37-03/04 and F37-FA; R3 AB-ARC-004, AB-ARC-008, AB-DAT-002) therefore remains **partial**. Resolve all entrypoints/imports coherently to one namespace, assert equal enum/dataclass identities across callers, and cold-start supported entrypoints with explicit unavailable-backend/simulation states.

Python was 3.12.14. Installed NumPy 2.3.5 and Pydantic 2.13.5 differ from production requirements; python-dotenv, FastAPI and Torch are unavailable. These conditions prevent supported-image certification. No hardware, providers, databases, repository tests, stored audit results, production edits or Git mutations were used. Network connections were blocked. Reproduce with `PYTHONDONTWRITEBYTECODE=1 python current_bootstrap_probes.py` from this directory; results, console and source receipts accompany the report.


## Appendix 5: ledger

### Actual-source review of forecast and ledger repairs

Reviewed commit **`1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`**, parent `fcf726ca5eeafacf359d34fefbd7a452bf751709`, compared with prior baseline `a2b0bf8923ca9f848083fdf702419ade889f3e38`. The new source is available and was executed directly. This report supersedes the earlier conditional assessment for these changed boundaries.

**Outcome:** the empty-quantile exception, explicit rejected-metadata ingress gate, SR02 zero/exposure consistency and SR03 canonical target priority are verified in the focused cases. **F23/F24 package closure is not established:** the original cache/publication/scoring counterexamples remain reproducible in this actual commit. SR03 fixes the durable target, while the dispatcher can still return a conflicting local completion result.

`probes.py` produced **16 isolated cases**. Every one of its **65 imported production source files** matched the exact candidate Git-tree blob SHA; the results include those identities and SHA-256 hashes. No repair model, repository test/audit evidence, Git mutation, production edit, controller connection or field hardware was used. One dispatcher seam uses an inert status-only stub and deliberately stale local event. The concurrency case selects a feasible interleaving before the unchanged production atomic writer.

All source references below are relative to `repair-1d5f15b-review/source/services/agribrain/`.

#### Verified narrow repairs

| Boundary | Exact current source | Observed result |
|---|---|---|
| Empty quantile helper | `world_model/forecast_archive.py:173–174` | `compute_crps_quantiles({},10)` raises `ContractViolation`. |
| Explicit rejected metadata ingress | `world_model/forecast_archive.py:379–387` | Lowercase status rejected/aborted/failed, `is_rejected=True`, `rejected=True`, and a nonblank rejection reason each reject before cache/file publication. Six cases leave the forecast unreachable and create no forecast file. |
| Valid Gaussian alternative | `world_model/forecast_archive.py:498–504` | Empty quantiles with finite mean10/std1 remain supported. CRPS≈0.233695 and RMSE0 against10. Empty quantiles without mean/std raise the existing absent-distribution error (`505–508`). |
| SR02 zero and explicit admission fields | `irrigation_runtime/safety.py:260–271,745–781` | Both zero and positive admission persist matching target/exposure in reservation and journal; reads succeed. Zero STOP_REQUESTED reopen remains readable. |
| SR02 numeric/conservation guards | `irrigation_runtime/safety.py:260–271` | Negative, bool, string, NaN and infinite exposure reject. Exposure9 below target10 also rejects. Allowing zero did not weaken these tested guards. |
| SR03 canonical target | `irrigation_runtime/safety.py:1133–1147` | Caller target99 cannot replace active target10, legacy active volume10, stopped target10 or stopped target0. Reopened overdelivery preserves target10, delivered/exposure14 and settles with target10. |

The source diff shows an empty-input exception and a metadata gate in the archive; it does **not** move cache insertion after durable conflict resolution. The metadata gate rejects forecasts already carrying those flags. A candidate rejected later because it conflicts with an existing durable forecast is a different rejection path.

#### Original forecast counterexamples still fail in this commit

| Counterexample | Actual observed result | Exact current source |
|---|---|---|
| Durable conflict contaminates warm cache | Mean1 is committed. A second instance attempts mean99 with the same ID and receives `ContractViolation`; disk bytes remain mean1, warm retrieval returns99, cold retrieval returns1. Warm evaluation against99 receives RMSE0. Full committed/warm/cold receipts are retained. | `world_model/forecast_archive.py:399–418,422–425` |
| Rejected candidate retry succeeds | The same instance retries the same rejected mean99 candidate and succeeds through its cached record without rechecking disk. | `world_model/forecast_archive.py:389–399` |
| Nonempty missing median is filled with the target | `{p90:100}` evaluated against77 gets p50=observed77, RMSE0 and coverage true. Its CRPS is4.6, **not zero**. The repaired empty-input helper is never invoked with empty input on this path. | `world_model/forecast_archive.py:490–497` |
| Nested mutation changes predictions and evaluation | Stored p50=1 and nested metadata value1 are mutated by the caller to99; warm reader and RMSE change while cold disk still contains1. | `world_model/forecast_archive.py:264–280,302–323,399,424–425` |
| Competing incompatible insert | Two independent archive instances pass `exists` before either original atomic writer runs. Both accept means1/99; one overwrites the other on disk. | `world_model/forecast_archive.py:404–418`, atomic writer `27–34` |
| Evaluation ID collision overwrites history | Same forecast and evaluation second, observations1/99 with different evidence IDs, produce one ID. Memory contains two records; disk contains one overwritten record. | `world_model/forecast_archive.py:510,524–530` |
| Invalid nonempty/Gaussian qualification | Quantile level `p-10` produces CRPS−0.2; Gaussian sigma−1 at its mean produces0. Sigma0 can legitimately represent a point mass and score0; valid positive sigma remains supported. | `world_model/forecast_archive.py:177–199,202–214` |

These are preserved gaps, not defects newly introduced by the two archive additions. Numeric zero by itself does not establish a scoring defect: the missing-median problem concerns fabricated RMSE, and valid point/Gaussian predictions may legitimately have zero point error.

#### Additional concrete boundary observations

The new metadata gate is enforced only during store. A public caller can mutate already stored mutable metadata to `status='rejected'`. A subsequent store call correctly rejects it, yet `get_forecast` still returns the rejected cached record and `evaluate_forecast` still scores it. This is a newly exercised **gate/read seam within the existing mutability and qualification gap**, not a claim that storing explicitly marked rejected metadata failed. Current references: `world_model/forecast_archive.py:379–387,424–425,471–491`.

`forecast_id='../outside_forecasts_subdir'` passes the nonblank ID validator and writes outside the `forecasts` subdirectory. The probe keeps the file inside its own isolated archive root and performs no broader filesystem escape. This is an additionally reproduced, preexisting ID-containment gap in the unchanged path construction, relevant to archive identity/isolation rather than an introduced regression. References: `world_model/forecast_archive.py:286–288,402–404`.

SR03’s durable target repair also does not synchronize the returned dispatcher event. With canonical target10/area2, local target3/area1, and an explicit 20,000L completion measurement, the actual store publishes target10/area2/delivery1mm; dispatcher returns COMPLETED with target3/area1/delivery2mm. This reproduces the previously identified local/canonical publication seam with candidate code. References: `irrigation_runtime/dispatcher.py:1225–1270,1277–1286`; canonical target/support/depth in `irrigation_runtime/safety.py:1133–1147,1175–1188`. No physical operation is inferred from the stub.

#### Acceptance and plan boundaries

| Item | Focused status | Remaining acceptance evidence |
|---|---|---|
| SR02 | Verified for explicit zero/positive admission, zero reopen, and tested reader guards | Broader ownership, missing delivery, candidate validation and projection closure remain separate ledger work. |
| SR03 | Verified at durable canonical-target selection | Return the committed canonical receipt to event/history/callbacks; preserve authoritative support and missingness. |
| F23, stage8 | Not closed | Resolve durable conditional commit before cache publication; incompatible failure/retry cannot expose a rejected candidate. Freeze returned/retrieved content, qualify read/evaluation eligibility, preserve concurrent identities and append-only evaluation history. Reject unsafe ID path segments. |
| F24, stage8 | Empty-helper repair verified; package not closed | Validate nonempty levels/order/finite distributions and sigma; no observation-filled prediction components. Missing score components become unavailable with reasons, and qualified target/time/support evidence is required. Preserve valid Gaussian alternatives. |

R3 mappings: SR02 relates to AB-DAT-005 (`675–677`) and AB-EXE-004 (`1118–1120`). Canonical support/publication relates to AB-DAT-007 (`683–685`), AB-DAT-010/011 (`695–701`) and AB-ARC-007 (`746–748`). F23 owns AB-DAT-011, AB-ARC-007/008 (`746–752`) and AB-ASM-014 (`828–830`); F24 owns AB-ML-005 (`990–992`), AB-ML-010 (`1010–1012`) and AB-ASM-016 (`836–838`). The master plan’s line134 requires F21–F24 closure before new training/forecast evaluation artifacts. These narrow successes do not satisfy that whole-package gate or prospective biological validation.

To reproduce, retain the exact candidate source at `../source` and exact `../git-tree.json` beside this lane directory, then run `PYTHONDONTWRITEBYTECODE=1 python3 probes.py`. It verifies every imported source blob against the candidate tree and writes only inside a fresh `isolated/<timestamp>` directory beside the script. Source identities, Python version, complete receipts and classifications are in `results.json`.


## Appendix 6: protocol

### Actual 1d5f15bf MQTT and ASMAE cache verification

**The new source fixes the narrow MQTT query/emergency-stop cases and broadens ASMAE cache write rejection. Full protocol acceptance remains open, and rejected cache records can still be read after an upgrade.** This review executes commit `1d5f15bfe13cd9f55b9028508d82e0f8b95fb249`, whose parent is `fcf726ca5eeafacf359d34fefbd7a452bf751709`. It replaces conditional predictions with evidence for this exact inspected commit; it does not claim execution of every parent revision.

The focused run contains **71 MQTT array rows plus one stale-query case**, 12 fresh cache status cases, six actual previous-writer/new-reader migration cases, cache identity/integrity checks and three semantic-scope controls. Eight relevant production source files independently match the new Git tree in `source-index.json`; cache dependencies are also hashed in `new_cache_scope_results.json`. No repository tests/audits, production edits, Git mutations, broker/controller calls or physical hardware were used. Transport callbacks were simulated locally; paho is not installed. Whole service startup, empirical calibration and forecast-archive execution are outside this pass.

#### MQTT: verified improvements

Actual `_decode_status_payload()` gives error/fault precedence, maps matched `running=true` to EXECUTING, and qualifies stopped/idle replies (`mqtt_driver.py:308–353`). `get_status():355–384` consumes the matched reply and returns UNKNOWN after timeout, including when a recent unmatched old reply exists. The probe reproduces the corrected behavior from an initial ONLINE cache.

Actual `emergency_stop():444–491` rejects `running=true` or `stopped=false`, rejects bare `status=OK`, and accepts explicit stopped confirmation. Positive STOP controls pass. The dispatcher still blocks completion unless a current query confirms ONLINE and there is no pending/unresolved dispatch (`dispatcher.py:1151–1206`). These improvements should be retained.

#### MQTT: remaining reproduced contract failures

**P1 — Ordinary STOP and START acknowledgements still use a different, weaker contract.** `send_command():214–302` remains `success = ack_payload.get("status") == "OK"`. With STOP_ZONE ACK `{status: OK, running: true, stopped: false}`, `execute_with_safety()` returns success, sets ONLINE and clears its active command. Cancellation's matching-owner STOP path and the late START fence use this method (`actuator.py:264–359, 518–540`; `dispatcher.py:1335–1354`). An emergency-stop safeguard does not protect those commands. START ACK `{status: OK, running: false, stopped: true}` still promotes EXECUTING. A normal STOP reply with explicit `status=STOPPED` is still treated as failure. AB-EXE-002 requires command-specific acknowledgement, start, end and unknown distinctions.

**P2 — Contradictory/malformed positive flags can still certify idle.** The actual query reply `{status: RUNNING, running: false, stopped: true}` returns ONLINE; emergency STOP accepts it. `{status: STOPPED, running: "true", stopped: true}` also returns ONLINE and stop success. These are observed code outcomes, not assertions of actual physical state. The decoder's “stopped true” branch runs before interpreting the running status word, and no exact field-type contract rejects malformed booleans.

**P3 — Emergency STOP can erase a fault that the query decoder recognizes.** Replies with `status=FAULT` or `fault_code=7`, alongside valid stopped flags, return ERROR from `get_status()` but success plus ONLINE from `emergency_stop()`. Positive physical cessation may justify stop success; it must not by itself erase the concurrent fault and permit a new START. Query fault precedence is improved, but fault retention across methods is not complete.

**P4 — Callback safety and request lifetime defects remain.** The unchanged `_handle_status():193–203` writes payload/heartbeat, then directly pops and completes an asyncio Future. Valid JSON arrays/null/scalars and an unhashable request ID raise after cache/heartbeat changes. A simulated callback thread produces asyncio debug RuntimeError; in ordinary mode the registered done callback waits until the independent 40 ms loop wake instead of receipt at about 5 ms. This demonstrates unsafe loop interaction; it does not assert that every real ACK fails. Cancelling query/send/emergency stop leaves a cancelled pending Future. Query/send publish exceptions leave non-done pending Futures; emergency STOP cleans its ordinary Exception path.

**P5 — Finite deadline qualification remains absent.** NaN/infinite query, command ACK and stop timeouts do not complete within the harness's external 25 ms bound; external cancellation leaves a pending entry. Nonpositive values publish before timing out, and bad strings fail after publication in query/send. These are bounded local proofs of configuration/lifecycle handling, not production latency measurements. AB-EXE-004 requires finite policy deadlines and cleanup on every outcome.

The new predispatch status query (`dispatcher.py:501–507`) is useful, but its return value is ignored; UNKNOWN has no new rejection rule in actuator validation. Cross-worker ownership and SR04 races are reviewed in the root's separate execution lane. This pass does not claim a full dispatcher reconciliation proof from a driver-only matrix.

#### ASMAE cache: write guard is improved, read guard is unchanged

`serialize_and_cache_asmae():643–713` lowercases string statuses/reasons, rejects `result_status` rejected/aborted, rejects top-level status rejected/aborted/failed and boolean rejection flags, and recognizes rejection text. Fresh regular-string rejected/aborted/uppercase failed controls now refuse publication.

**C1 — Existing committed negative records remain readable.** `deserialize_cached_asmae():716–791` still checks only the old lowercase `result_status` failed_spatial_fallback/failed/unavailable and case-sensitive chain-integrity/timeout reason text. Cache/hash schema versions are unchanged. The probe uses the exact a2b0bf8 writer to create valid checksummed transactions, then the actual 1d5 reader: all six migration fixtures remain cache hits despite the new writer refusing the same payloads. Cases include rejected/aborted result_status, failed/REJECTED top-level status, `is_rejected=true`, and uppercase TIMEOUT. Refusing a replacement does not remove or reject the previously stored entry. This is a real old-writer/new-reader boundary proof, not a claim that a historical live cache contains these records.

Actual producer scope was traced. `_serialize_output()` emits a regular-string **`status`** from diagnostics (`runner.py:1113–1144`); the normal cache call is at `:608`, with a separate quick fallback call at `:776`. Engine overrides include `partial`, `unavailable`, `failed_spatial_timeout` and `degraded` (`engine.py:544, 656, 1325`); worker bookkeeping copies string status into result_status (`background_jobs.py:1698, 1763, 2213–2221`). No actual ASMAE cache caller assigning an Enum to these top-level fields was found. Enum/whitespace/missing-status probe rows are defensive API controls, **not evidence of a production Enum regression**. Unavailable diagnostic-only output may be intentionally cacheable; document that policy separately from rejected scientific results.

#### ASMAE cache: strong integrity retained; scientific scope remains bounded

Actual input keys change for band identity, array shape/dtype/exact pixel precision, cloud mask, transform and permission demotion. Identical referenced bytes relocated to another path retain identity; changed bytes change the key. `stable_value_hash():142–257`, `compute_source_hash():272–315`, and `get_asmae_cache_key():318–387` already provide exact typed recursive input identity. A run ID alone is deliberately excluded. **The internal EO tile-hash collisions do not imply an ASMAE cache-key collision when complete input support reaches this cache.**

The JSON/NPZ commit checks also pass: input output-dict remains unmodified, valid rasters round-trip, and corrupted NPZ or tampered JSON produces a clean miss. The commit manifest checks payload hash, schema, cache key, raster reference, byte checksum, members, shapes, dtypes and array content (`cache.py:579–622, 686–710, 743–782`). These protections should be preserved.

**C2 — A checksummed success payload is not independently qualified science.** Actual cache writer/reader round-trip success-status fixtures containing contradictory EO backend identity, a positive weak label with no variable support ledger, or negative uncertainty. The diagnostic-only/state-update-disabled/production-unusable guards remain intact. This is a cache-boundary semantic test, not proof that the full engine promotes those crafted fixtures. Consequently the status patch does not complete F25 model/backend provenance, F26 missing-band/model input support or F36 per-variable observability/calibration/label eligibility. Their producer contracts and independent evidence remain necessary.

**C3 — Integrity is different from write-once history.** The actual writer permits a different output at the same input key, with a new valid checksum. A producer's separate public `content_hash` is preserved without recomputation; the cache commit's `payload_sha256` is the integrity check that is verified. This is a replaceable content-keyed cache, not an append-only historical artifact archive. It should not be cited as proof that prior published scientific states or forecasts are immutable.

The spatial state cache and `world_model/forecast_archive.py` are separate mechanisms: different storage, record contracts, caches and validation methods. This commit also changes forecast admission independently; changing ASMAE status rejection cannot prove forecast immutability, retrieval validation or forecast calibration. That archive requires its own exact-source checks. No forecast cache behavior is inferred from the NPZ controls here.

#### Acceptance matrix

| Contract case | Actual 1d5 outcome | Acceptance |
|---|---|---|
| Current correlated running/error query | EXECUTING / ERROR | Narrow fix verified |
| Query timeout with recent unmatched payload | UNKNOWN | Narrow fix verified |
| Emergency STOP explicitly still running/not stopped | Failure, EXECUTING or UNKNOWN | Narrow fix verified |
| Bare emergency STOP OK ACK | Failure | Narrow fix verified |
| Explicit stopped emergency reply | Success | Positive control passes |
| Normal STOP OK + still running | Success, clears active command | Open |
| START OK + stopped | EXECUTING | Open |
| RUNNING status + stopped flags; malformed running string | ONLINE / stop success | Open |
| Fault alongside stopped flags | Stop clears ERROR to ONLINE | Fault retention open |
| Transport-thread callbacks / malformed JSON shape | Unsafe Future completion / escaping exception | Open |
| Cancellation / publish exception / invalid deadline | Pending ACK leaks or post-send failure | Open |
| Fresh cache rejected/aborted/failed string | Writer refuses | Write slice verified |
| Prior validly committed negative cache record | New reader accepts | Read/migration open |
| Typed full input identity and JSON/NPZ corruption | Distinct keys / clean miss | Positive controls pass |
| Positive payload missing scientific qualification | Cache round-trip with authority guards retained | F25/F26/F36 remain separate acceptance work |
| Same cache key, different valid output | Replaces entry | Historical immutability not demonstrated |
| Actual ASMAE root status is Enum | No such caller found | Defensive-only test; no live defect claim |

Use one normalized admission predicate for both cache write and read, or invalidate older policy-version entries; retain valid diagnostic-only cache behavior explicitly. Apply one command-specific physical ACK contract across normal STOP, emergency STOP and fencing, while preserving fault and unknown-outcome ownership. Complete callback marshaling, lifecycle cleanup and finite deadlines before full protocol acceptance. These are concrete remaining cases at the inspected commit; neither a narrow status filter nor a successful local control proves field commissioning or delivered volume.


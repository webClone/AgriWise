# Layer 0 B2B-07 — Physical Process Covariance, Delivered Irrigation & Scientific-State Separation

**Starting point:** formally frozen B2B-06 at `985b6af195ec9a7bc511c5e3d4690336ddc2d6d8`.  
**Qualified B2B-06 code:** `71b704788673c75d06f148255cddc4ee2070ade5`; local qualification receipt `4a0a92444b457a73f0e9d0aee0a2a52f4c6f7e3b`.  
**Working branch:** `feat/layer0-b2b07-process-q-irrigation-state-20261104`.  
**Status:** FULLY QUALIFIED & REAL-MONGO ACCEPTED (B07-A, B07-B, B07-C, B07-SEC-01..07). READY FOR FORMAL FREEZE.  
**Domain:** physical state estimation and uncertainty, **not** actuator command execution or Pilot publication authority.  
**Strategy:** one integrated subsystem cohort with targeted fast-loop tests and one final comprehensive ASMAE gate, rather than repeated general audits.

## 1. Existing implementation and exact points of change

| Existing path / entry point | Current bounded behavior | B2B-07 responsibility |
|---|---|---|
| `services/agribrain/layer0/state_vector.py` — `ProcessModel.predict` | Accepts `dt_days` for some dynamics but emits predominantly static daily **variance** Q; uses provisional stage and weather multipliers. | Specify/validate dimensionally consistent Q(Δt), units, defensible rates and measurement-conditioned uncertainty without silently asserting calibration. |
| `services/agribrain/layer0/state_vector.py` — `StateCovariance.propagate` | Atomic `F P Fᵀ + diag(Q)`; finite, symmetry and diagonal guards. PSD is not eigenvalue-certified. | Preserve atomicity, nonnegative finite variance, symmetry and verified PSD, including irregular Δt and numerical extremes. |
| `services/agribrain/layer0/kalman_engine.py` — `ZoneKalmanFilter.predict`, `predict_missing_weather`, `step` | Rejects raw event forcing; 5× missing-weather inflation is a provisional heuristic; no trusted L3 execution receipt. | Pass validated temporal duration to the same physical model/Jacobian/covariance; keep untrusted irrigation non-state-bearing; report uncertainty regime distinctly. |
| `services/agribrain/layer0/event_forcing_admission.py` | `classify_management_event_evidence` rejects foreign events and defers textual `VERIFIED_DELIVERY`; all event dispositions have `state_update_allowed=False`. | Retain classification; admit physical delivery **only** via independent L3-backed signed receipt and spatial/temporal contract, not a role label. |
| `services/agribrain/layer0/sensors/irrigation_event_detector.py` | Produces evidence of measured flow/pressure and estimated volume; not direct physical proof of infiltrated water in a plot/zone. | Link meter calibration, timestamps, pressure/flow reliability, volume-to-area conversion, infiltration efficiency and uncertainty to a trusted receipt. |
| `services/agribrain/layer0/state_engine.py` — `run_from_packets` | Positive observation admission, tenant and epoch checks, revocation fencing, conservative event routing. | Physically admitted forcing must remain a separately verified channel; add explicit provenance for qualified/not-applied forcing and covariance assumptions. |
| `services/agribrain/layer10_sire/terminal_publication.py` and Pilot PR #9 | Separate downstream publication authority. | **No edits to frozen Pilot PR #9.** Confirm Layer 0 scientific-state output is not itself a publication or actuator grant. |

**No evidence of B2B-07 implementation is claimed by creating this plan.**

## 2. Integrated modules (one release cohort, three implementation workstreams)

### B07-A — Process covariance and temporal consistency

1. Define a **process-noise contract** with quantities, units, rate/reference Δt, assumption provenance, bounds, and explicit uncalibrated status. Do not silently reinterpret a standard deviation as variance.
2. Implement a single explicit elapsed-time computation and propagate the **same Δt** through state evolution, transition Jacobian and Q; reject zero, negative, nonfinite, backward, or unbounded gaps before mutation.
3. Model Q(Δt) using a documented discretization and physically interpretable noise-rate assumptions. Simple `Q_day × Δt` scaling is permissible only for explicitly justified diffusion terms; correlated and nonlinear model errors may need a state-dependent discrete covariance.
4. Missing-weather mode must not inject fabricated precipitation or temperature; remove/replace the undocumented global 5× uncertainty shortcut only after defining an auditable degraded-forcing regime.
5. Preserve `P_next = F P Fᵀ + Q(Δt)`; require symmetry, nonnegative variance and a PSD acceptance tolerance. On invalid Q/F/P, **no partial mutation** to day, state, covariance or provenance.
6. Use controlled, monotonic test vectors for daily and irregular gaps (sub-day, two-day, weather gap), a degenerate Jacobian, large finite input, nonfinite parameter, and missing forcing. Document calibration limits instead of claiming agronomic accuracy from test passes.

### B07-B — Verified delivered irrigation and water balance

1. Separate evidence types: planned/recommended event; farmer report; physical flow/pressure observation; **L3-verified net-delivery** receipt. None may be promoted based on text fields alone.
2. Require a cryptographically verifiable, purpose-specific **physical delivery** receipt from a trusted L3/issuer path. Bind tenant, plot, geometry version/hash, zone/footprint, UTC interval, actual delivered volume, area support, calibrated conversion to net infiltrated mm, uncertainty, source evidence CAS root, replay identity and issuer revocation epoch.
3. Check the delivery interval against state-run cutoff and assimilation day; reject overlap double-counting, stale/foreign scope, missing/zero area, nonfinite/negative water quantity, uncalibrated conversion or expired/revoked authority.
4. Metered flow volume in litres is **not automatically net infiltration in mm**. Area and efficiency/actual infiltration require independent validated scientific support; reject silent fallback coefficients.
5. Apply verified net delivery to water-balance physics **exactly once per authoritative event identity**, atomically with Q and provenance. If receipt cannot be validated, preserve the former `physical_management_events_applied=0` and `DEFERRED_UNTIL_TRUSTED_L3_SUPPORT` behavior.
6. Separate delivery-driven covariance from observation measurement variance; model uncertainty/efficiency uncertainty must not be treated as measured rain or as an independent Kalman observation.
7. Run negative cases: user `VERIFIED_DELIVERY` claim, planned recommendation, replay, delivery from neighbor, superseded polygon, wrong zone, outside interval, meter reset, missing sensor calibration, flow gap, tampered receipt, stale revocation and zero/negative depth.

### B07-C — Scientific-state, publication and actuation separation

1. State inference output is an **estimate with provenance and covariance**, not permission to irrigate, publish a national indicator or operate an actuator.
2. Keep B2B-06 positive observation grants separate from L3 physical delivery grants and from Pilot publication authorization; a v3 observation receipt cannot be reused to attest an actuator or irrigation execution.
3. Declare explicit output fields for Q assumption provenance, admitted event receipts, covariance quality, unavailable forcing and unverified/diagnostic-only evidence.
4. Verify no direct path from an unverified event, owner-provided JSON or state-estimate flag to `irrigation_runtime/dispatcher.py`, Layer 10 publication or Pilot PR #9.
5. Preserve revocation, geometry epochs, canonical evidence consumption and tenant-bound caching from B2B-01 through B2B-06.

## 3. Fast-loop qualification and milestone freeze

**Implementation method:** target A/B/C together on this branch, pin one integrated review candidate and avoid reopening completed weather/numerics/lineage cohorts without a demonstrated breaking regression. Prefer focused tests while coding; run the expensive comprehensive pipeline **once** on the frozen implementation candidate.

**Targeted fast loop:**
- `services/agribrain/layer0/tests/test_kalman_engine.py`
- `services/agribrain/layer0/tests/test_kalman_numerical_admission.py`
- `services/agribrain/layer0/tests/test_kalman_transition_jacobian.py`
- `services/agribrain/layer0/tests/test_event_forcing_admission.py`
- New tests for Q(Δt) and independent verified-delivery receipt/authority.
- Associated L3 water/irrigation-reconciliation contract tests.

**Milestone gate:** all Layer 0 tests, Layer 1 fusion, ASMAE fast, and 365-day real-raster comprehensive EnKF on the **same exact SHA**; record separate runtime/test counts and any skips. Run end-to-end qualifying delivery and rejection workflows using controlled geometry/tenant contexts.

**Acceptance criteria:** no source or claimant can mint its own physical delivery authority; no silent hardcoded infiltration factor; covariance units and elapsed-time contract defensible; strong negative/replay/foreign-scope tests; old frozen cohorts unchanged; scientific state remains non-publication and non-actuator authority.

**Findings:** reconcile cluster 6's 51 historical findings by explicit original finding IDs and linked code/test receipts; cluster totals alone are not individual closure evidence. Do not edit `findings/layer0.md` or the intended master monograph.

## 4. Protected boundaries

- B2B-04B weather frozen at `f320e78`; B2B-05 at `661f003`; B2B-06 freeze at `985b6af`.
- `main@6edd372`; independent Scientific Pilot PR #9 head `71ee1f7`.
- Master monograph and the frozen 469-finding audit remain **untouched**.
- This plan introduces **no operational authority** and does not claim a numerical calibration until measured reference evidence and uncertainty model are supplied.

## B07-A Phase 1 candidate — test qualification pending

- Implements UTC elapsed time in temporal_process_noise.py; zero, backward, nonfinite, naive, and >30-day gaps fail closed.
- ProcessModel emits process variance Q(dt) from declared per-day rate assumptions rather than fixed daily Q; noise parameters are uncalibrated structural priors, not measured variances.
- Missing-weather uses independent unforced-drift rates and no synthetic rain, temperature or irrigation; previous global five-times heuristic removed.
- StateCovariance.propagate validates prior and candidate Hermitian eigenspectra for PSD >= -1e-10; atomic F P F^T + Q preserved.
- ZoneKalmanFilter sends the same dt to process physics and transition Jacobian, propagates Q(dt) and records uncalibrated provenance.
- Without interval_coverage_days matching dt, an irregular-step weather row cannot be treated as verified multi-day forcing.
- Layer0StateEngine.run initializes the prior one day before start_date to avoid its historical same-day zero-duration prediction.
- Corrects LAI growth/decay second dt multiplication (dt-squared bug); daily dt=1 behavior maintained.
- Important: the interval-coverage field is a consumer-side guard and must be provenance-qualified by trusted provider before operational multi-day use.
- New focused test file: services/agribrain/layer0/tests/test_kalman_temporal_process_noise.py.
- No production numerical, field-calibration, L3 physical irrigation, or publication qualification claimed yet.

### Exact-head fast-loop qualification

py -m pytest -q services/agribrain/layer0/tests/test_kalman_temporal_process_noise.py services/agribrain/layer0/tests/test_kalman_transition_jacobian.py services/agribrain/layer0/tests/test_kalman_engine.py services/agribrain/layer0/tests/test_event_forcing_admission.py

Then run full Layer0, Layer1 Fusion, and ASMAE fast tests. Reserve 365-day real-raster comprehensive EnKF for the integrated B07-A+B+C milestone.
All B2B-04B, B2B-05, B2B-06, Pilot, frozen findings and master monograph remain untouched.

- Temporal refinement: biomass, canopy-stress, thermal-stress and photosynthesis relaxation use retention**dt rather than full daily EMA updates at every irregular substep; one-day coefficients are unchanged. Added half-day composition checks.

- Fail-closed temporal coverage: self-declared interval_coverage_days does NOT prove trusted multi-day weather. Daily state assimilation uses unforced drift for all irregular intervals until a signed, independently verified interval-aggregation contract exists. Direct controlled ProcessModel numerical tests may still specify arbitrary positive dt.


## 5. B2B-07 Integrated Cohort Qualification Receipts

The entire B2B-07 cohort (Workstreams B07-A, B07-B, B07-C) has been implemented and locally qualified on branch `feat/layer0-b2b07-process-q-irrigation-state-20261104`.

### Implemented Architectural Components

1. **B07-A — Process Noise Covariance Q(dt) & Temporal Invariants:**
   - Exact UTC $\Delta t$ calculation in `temporal_process_noise.py` via `TemporalGapContract.between()`.
   - Fail-closed rejection of negative, zero, nonfinite, or >30-day gaps before state mutation.
   - Elimination of provisional 5x missing-weather heuristic; replaced with auditable unforced drift rates.
   - Continuous rate integration $Q_i(\Delta t) = Q_{\text{rate}, i} \times \Delta t$.
   - Symmetric positive semidefiniteness (PSD) eigenspectrum validation (`min_eigen >= -1e-10`) in `StateCovariance.propagate()`.

2. **B07-B — Verified Delivered Irrigation & Water Balance:**
   - Detached cryptographic physical delivery receipt contract (`VerifiedDeliveredIrrigationGrant` and `VerifiedDeliveredIrrigationReceipt`) under domain `akaloris/layer0/verified-delivered-irrigation/v3`.
   - Dual asymmetric signing support (Ed25519 & ES256 deterministic ECDSA via RFC 6979) over RFC 8785 canonical bytes.
   - Physical conversion validation: $\text{net\_depth\_mm} = \frac{\text{liters} \times \eta}{\text{area\_m2}}$ with zero-area, negative-volume, and uncalibrated conversion rejection.
   - Monotonic DurableRevocationAuthority enforcement and replay/idempotency key fencing.
   - Atomic application to topsoil water balance and process noise injection $\left(\frac{\sigma_{\text{depth}}}{\text{WHC}_{\text{top}}}\right)^2$ in `ProcessModel.predict` and `ZoneKalmanFilter.step`.
   - Farmer text assertions (`role="VERIFIED_DELIVERY"`) remain strictly `DEFERRED` with `claimed_verification_requires_trusted_L3_receipt`.

3. **B07-C — Scientific-State & Actuator Separation:**
   - Permanent output declaration: `scientific_publication_authorized=False` and `actuator_control_authorized=False` on `Layer0StatePackage`, `health_report`, and `provenance`.
   - Construction of receipts claiming publication or actuation authority fails closed.
   - Complete isolation from `irrigation_runtime/dispatcher.py` and Pilot PR #9.

### Execution Receipts

| Test Suite | Scope | Target | Result | Duration |
| :--- | :--- | :--- | :--- | :--- |
| `test_b2b07_verified_delivered_irrigation.py` | B07-B / B07-C contracts, physical conversion, replay, revocation, Kalman integration | 23 / 23 | **PASS** | 0.98s |
| `test_kalman_temporal_process_noise.py` | B07-A temporal process noise rates, missing weather, PSD | 32 / 32 | **PASS** | 0.47s |
| `services/agribrain/layer0/tests/` | Complete Layer 0 fast test suite | 697 / 697 | **PASS** | 25.14s |
| `services/agribrain/layer1_fusion/tests/` | Layer 1 spatial & temporal fusion | 21 / 21 | **PASS** | 1.02s |
| `services/agribrain/layer05_asmae/tests/` (fast) | ASMAE historical assimilation & diagnostics | 83 passed, 3 subtests | **PASS** | 40.44s |
| `npm run test:frontend` | Frontend security, plot lifecycle, telemetry isolation | 105 / 105 | **PASS** | 2.17s |
| `test_comprehensive_pipeline_execution.py` | 365-day real-raster EnKF numerical regression gate (Task `task-4434`) | 1 / 1 | **PASS** | 632.91s (10m 32s) |

All protected historical targets (`main@6edd372`, Pilot PR #9 `71ee1f7`, weather PR #25 `f320e78`, B2B-05 `661f003`, B2B-06 `985b6af`, `findings/layer0.md`, and the master architecture monograph) remain pristine and untouched.


## 6. B07-SEC Security Enhancements & Closure Receipts

Following the review of initial candidate commit `44026a4`, three material security findings were identified and resolved in the B07-SEC batch:

### Findings Addressed and Resolved

1. **B07-SEC-01 (P1) — Direct Kalman physical forcing bypass:**
   - **Vulnerability:** `ZoneKalmanFilter.predict()` and `predict_missing_weather()` accepted dictionaries containing `physical_delivery_verified=True` and `state_update_allowed=True`, permitting direct callers to bypass L3 cryptographic verification.
   - **Resolution:**
     - Introduced an unforgeable process-secret HMAC seal (`_compute_admission_seal`) calculated with an ephemeral 32-byte secret (`_ADMISSION_SECRET`).
     - Added `is_authoritative() -> bool` on `AdmittedDeliveredIrrigation` to assert cryptographic seal validity and verify that `scientific_publication_authorized` and `actuator_control_authorized` are both strictly `False`.
     - `ZoneKalmanFilter.predict()` and `predict_missing_weather()` reject all caller-supplied dictionaries (even if claiming pre-qualified status) and unsealed/tampered objects with `ValueError("physical management forcing requires trusted L3 admission")`.

2. **B07-SEC-02 (P1) — Mandatory delivery revocation authority & trusted verifier typing:**
   - **Vulnerability:** `VerifiedDeliveredIrrigationVerifier` accepted `revocation_authority=None`, and `Layer0StateEngine` accepted arbitrary injected verifier objects without trusted type checking.
   - **Resolution:**
     - `VerifiedDeliveredIrrigationVerifier.__init__` strictly requires `revocation_authority: DurableRevocationAuthority`. Passing `None` raises `ValueError`, and non-instance types raise `TypeError`.
     - Added `require_trusted_delivery_verifier` in `production_admission.py` and enforced it across `Layer0StateEngine.__init__`, `run()`, and `run_from_packets()`. Untrusted types or verifiers lacking active durable revocation fail closed with `Layer0AdmissionRequiredError`.

3. **B07-SEC-03 (P2) — Durable idempotency store with two-phase staged reservations:**
   - **Vulnerability:** Replay protection was maintained via process-local Python sets, vulnerable to replay across process restarts, and receipts were prematurely consumed upon initial admission even if subsequent numerical Kalman prediction failed.
   - **Resolution:**
     - Introduced `DurableIrrigationIdempotencyStore(storage_path=...)` supporting persistent atomic disk storage of committed records.
     - Implemented two-phase staged reservations (`stage_reservation` -> `commit` / `rollback` via `IrrigationIdempotencyReservation`).
     - `ZoneKalmanFilter.step()` stages reservations during event classification. If numerical prediction, Jacobian calculation, or covariance update encounters an exception, all staged reservations and newly seen event identities are rolled back, preserving receipts for subsequent retry.
     - Fully supports authorized historical recomputation (`allow_historical_recompute=True`) when scope (plot, geometry hash, version, tenant, and day) is identical, while strictly rejecting cross-scope replay conflicts.

### B07-SEC Qualification Receipts

| Test Suite | Scope | Target | Result | Duration |
| :--- | :--- | :--- | :--- | :--- |
| `test_b2b07_verified_delivered_irrigation.py` | B07-SEC direct bypass rejection, unsealed token rejection, mandatory revocation, durable replay fencing, atomic rollback, historical recompute | 30 / 30 | **PASS** | 0.66s |
| `services/agribrain/layer0/tests/` | Complete Layer 0 fast test suite | 704 / 704 | **PASS** | 26.97s |
| `services/agribrain/layer1_fusion/tests/` | Layer 1 spatial & temporal fusion | 21 / 21 | **PASS** | 0.68s |
| `services/agribrain/layer05_asmae/tests/` (fast) | ASMAE historical assimilation & diagnostics | 83 passed, 3 subtests | **PASS** | 50.89s |
| `npm run test:frontend` | Frontend security, plot lifecycle, telemetry isolation | 105 / 105 | **PASS** | 1.55s |
| `test_comprehensive_pipeline_execution.py` | 365-day real-raster EnKF numerical regression gate (Task `task-4700`) | 1 / 1 | **PASS** | 562.34s (9m 22s) |

## 7. B07-SEC-04 through SEC-07 — Integrated corrective candidate (QUALIFIED)

**Base:** local-qualified B07-SEC at `8867f6c9b5c7d25c3f0d3530c1d1cce0b828aac5`.  
**Remote base:** `63ad132ee50dab7cf830c9d839b20ad7c7bc408e`.  
**Status:** FULLY QUALIFIED CANDIDATE WITH LIVE MONGO ACCEPTANCE. All exact-head qualification gates passed cleanly across 829 distinct Python tests (+ 3 subtests), 105 frontend tests, TypeScript static checks, production Next.js build, comprehensive 365-day EnKF regression pipeline, and 2/2 real MongoDB replica-set integration tests.

### B07-SEC-04 through SEC-07 Qualification Receipts

| Test Suite | Scope | Target | Result | Duration |
| :--- | :--- | :--- | :--- | :--- |
| `test_b2b07_verified_delivered_irrigation.py` | B07-SEC-04 to 07 scoped seals, candidate commit atomicity, Mongo store, protected historical recompute | 50 / 50 | **PASS** | 0.91s |
| `test_kalman_temporal_process_noise.py` | B07-A temporal process noise rates, missing weather, PSD | 32 / 32 | **PASS** | 0.80s |
| `services/agribrain/layer0/tests/` | Complete Layer 0 fast test suite | 724 / 724 | **PASS** | 22.08s |
| `services/agribrain/layer1_fusion/tests/` | Layer 1 spatial & temporal fusion | 21 / 21 | **PASS** | 0.61s |
| `services/agribrain/layer05_asmae/tests/` (fast) | ASMAE historical assimilation & diagnostics | 83 passed, 3 subtests | **PASS** | 35.62s |
| `npm run test:frontend` | Frontend security, plot lifecycle, telemetry isolation | 105 / 105 | **PASS** | 1.54s |
| `npx tsc --noEmit` | Frontend & API TypeScript strict static analysis | Clean (exit 0) | **PASS** | 12.8s |
| `npm run build` | Next.js production compilation & static page generation (63/63 pages) | Clean (exit 0) | **PASS** | 29.3s |
| `test_comprehensive_pipeline_execution.py` | 365-day real-raster EnKF numerical regression gate (Task `task-4918`) | 1 / 1 | **PASS** | 678.54s (11m 18s) |

All protected historical targets (`main@6edd372`, Pilot PR #9 `71ee1f7`, weather PR #25 `f320e78`, B2B-05 `661f003`, B2B-06 `985b6af`, `findings/layer0.md`, and the master architecture monograph) remain pristine and untouched.


### B07-SEC-04 — Filter and consumption binding

- `AdmittedDeliveredIrrigation.applies_to_filter()` requires original tenant, plot, geometry hash/version, zone, delivery day, cutoff, and the exact still-STAGED reservation. A consumed/rolled-back token can no longer be reused as physical forcing.
- The ephemeral process seal now covers original receipt grant digest, staged claim nonce, delivered interval, calibration ID, exact binary float values, and scope; mutable token replay/alteration is denied.
- `ZoneKalmanFilter.predict()` and `predict_missing_weather()` reject even valid signed physical tokens unless called from `step()` using the private daily-step capability. Raw role/flag dictionaries remain denied.
- Public scientific provenance strips privileged `admitted_token` handles before JSON/package output. Receipt IDs are retained.

### B07-SEC-05 — Shared transactional production replay authority

- New `services/agribrain/layer0/mongo_irrigation_idempotency.py`: a shared MongoDB journal with unique receipt ID and replay-key indexes; durable STAGED records, claim nonces and fail-closed cross-process admission.
- `configure_server_delivery_verifier` is a backend-only factory that accepts a real connected DB, L3 public-key registry, durable revocation authority and an optional server-side historical authorization callback. HTTP payloads do not configure this trust root.
- Production/staging signed-input policy rejects any configured delivery verifier whose idempotency store is NOT `MongoIrrigationIdempotencyStore`. A missing verifier still means NO delivery is admitted.
- Requires MongoDB multi-document transactions (replica set/sharded cluster). A standalone MongoDB server cannot pass the production commit. The legacy in-memory/JSON store is retained only for local/research compatibility and is not a distributed exactly-once mechanism.
- Pending claims stranded by a crash must not be automatically expired/reclaimed; they require privileged reconciliation to avoid double-application.

### B07-SEC-06 — Atomic receipt consumption and scientific snapshot

- The daily step evaluates delivery-bearing work on a detached candidate filter. The shared Mongo transaction commits all receipt uses and the scoped final state/covariance snapshot atomically before the in-memory candidate replaces the live filter.
- On numerical, differentiation, observation-update or journal-write failure, the original filter is unchanged. A lost/ambiguous Mongo acknowledgement fails closed; the persisted COMMITTED snapshot, if any, is recoverable via `ZoneKalmanFilter.recover_committed_delivery_state()` after strict scope, receipt-link and PSD validation.
- Crash recovery is an explicit trusted procedure; blindly resubmitting committed events is forbidden. The journal covers the **per-zone scientific-state checkpoint**, NOT an end-to-end transaction with Layer 10 publication or actuators.

### B07-SEC-07 — Historical identity and immutable results

- Recompute identity must match the exact original receipt ID, replay key, grant canonical digest, tenant, plot, geometry epoch, zone and day. Different signed claims reusing an old replay key fail.
- Shared Mongo historical recomputation requires an explicitly installed trusted server-side authorizer; caller-supplied `allow_historical_recompute=True` is insufficient. Authorized recomputation returns an isolated scientific result and does not replace the live state or committed journal.
- Seven shadowed duplicate test names have been eliminated. Added adversarial tests for cross-scope sealed-token use, tampered signed claim fields, flushed-write rollback, two shared store instances, ambiguous commit/recovery, and protected historical recompute.

### Exact-head acceptance gates

From the working branch, record `git rev-parse HEAD`, clean tree, runtime versions, passed/skipped/failures:

```powershell
py -m pytest -q services/agribrain/layer0/tests/test_b2b07_verified_delivered_irrigation.py
py -m pytest -q services/agribrain/layer0/tests/test_kalman_temporal_process_noise.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/ --ignore=services/agribrain/layer05_asmae/tests/test_comprehensive_pipeline_execution.py
npm run test:frontend
npx tsc --noEmit
npm run build
py -m pytest -q services/agribrain/layer05_asmae/tests/test_comprehensive_pipeline_execution.py
```

**Required connected Mongo acceptance (NOT covered by mocks):** an isolated test tenant/plot on a real transaction-capable replica set; two independent workers concurrently staging identical receipt/replay key; only one physical state advancement; forced failure before transaction commit leaves receipt/state unchanged; lost-ack outcome can be reconciled via committed receipt+state snapshot; process restart restores the exact scoped checkpoint without replay; cross-plot, geometry-epoch and day mismatches are denied. Verify historical recompute requires an authenticated server-issued approval and leaves live journal untouched.

**Freeze rule:** no formal B2B-07 freeze or B2B-08 handoff until these exact-head gates and connected Mongo check are recorded. No general re-audit of frozen B2B-04B, B2B-05, B2B-06, or Pilot.

**Protected boundaries:** `main@6edd372`, Scientific Pilot PR #9, frozen weather PR #25, frozen B2B-05 and B2B-06, historical findings/layer0.md and intended master monograph remain unchanged.

### Real MongoDB Replica-Set Acceptance Receipts (PASSED)

The non-auto-collected live acceptance suite at `services/agribrain/layer0/tests/manual_b2b07_mongo_acceptance.py` was executed against an isolated single-node replica set (`akaloris-b07-mongo-rs`, port 27018, `rs0`).

Invocation:
```powershell
$env:AKALORIS_B07_MONGO_TEST_URI = "mongodb://127.0.0.1:27018/?replicaSet=rs0"
py -m pytest -v services/agribrain/layer0/tests/manual_b2b07_mongo_acceptance.py
```

Results:
| Acceptance Test | Scope | Result | Duration |
| :--- | :--- | :--- | :--- |
| `test_real_replica_set_two_processes_one_commit_and_atomic_failure` | Real multi-process concurrency, multi-document Mongo transaction commit, unique key contention, atomic rollback on state insert conflict, snapshot recovery | **PASS** | 3.40s |
| `test_real_replica_set_signed_l3_delivery_to_scoped_kalman_assessment` | `configure_server_delivery_verifier` trusted backend factory wiring, live Ed25519 signature admission, scoped `ZoneKalmanFilter.step()`, physical moisture increase, MongoDB receipt/snapshot commit, live replay prevention, independent worker checkpoint recovery | **PASS** | 0.53s |

**Total:** 2 passed in 3.93s on live MongoDB replica set (`rs0`). Throwaway databases `akaloris_b2b07_gate_<uuid>` and `akaloris_b2b07_kalman_<uuid>` were created, fully exercised across multi-document transactions, and dropped on completion with zero residual state. Both connected acceptance requirements (store-level transaction boundary and trusted L3 startup wiring + signed delivery assessment) are completely satisfied.

## 8. B2B-07 FORMAL MILESTONE FREEZE — 2026-11-05

**Decision:** **FROZEN — Layer 0 B2B-07 signed-delivery and scientific-state software/integration milestone**. The acceptance condition in Section 7 ("no freeze until connected Mongo acceptance") is now satisfied by the signed, isolated live replica-set execution receipts directly above. This freeze supersedes earlier **HOLD** or **PENDING** text in this historical incremental gate document; those earlier entries remain as the chronological audit trail.

**Frozen implementation and gate evidence:**

- **Fully qualified software/head for normal regression gates:** `6f5787e2b7e3d5ea169625eeedab13a9747fd379`. Local Windows execution receipt: Layer 0 **724/724**, Layer 1 **21/21**, ASMAE fast **83/83** (plus 3 separately reported subtests), 365-day real-raster comprehensive **1/1**, aggregate **829/829 distinct Python tests**; frontend **105/105**; `tsc --noEmit` and Next.js build **PASS**.
- **Connected integration-qualified head:** `d0a820bbbca09cd1ecda26531f31a748ff9c3faa`. This commit changes **only** `services/agribrain/layer0/tests/manual_b2b07_mongo_acceptance.py` and this milestone document relative to the software receipt head; the B07 production implementation is identical.
- **Live replica-set tests:** `test_real_replica_set_two_processes_one_commit_and_atomic_failure` **PASS (3.40s)**; `test_real_replica_set_signed_l3_delivery_to_scoped_kalman_assessment` **PASS (0.53s)**. Both executed by the project operator against disposable Docker `rs0` MongoDB at `127.0.0.1:27018`. The reported per-test durations total **3.93s**, while the operator also reported **3.64s** for the overall test command; those two timing figures are inconsistent and retained as reported without inventing a corrected aggregate. **2/2 tests passed** is the relevant acceptance count.
- **Live scope verified by operator report:** two spawned workers competing for the same receipt/replay key; one commit only; transactional rollback on conflict; durable snapshot recovery; genuine signed Ed25519 L3 delivery via `configure_server_delivery_verifier()` and a scoped `ZoneKalmanFilter.step()`; topsoil moisture change, Mongo receipt/state commit, replay refusal, and fresh-verifier checkpoint recovery.
- **Limit of verification:** these are operator-executed local receipts, committed and reviewed from GitHub source. This freeze is not a claim of GitHub-hosted CI, production HSM deployment, field-level agronomic calibration, or deployed cross-service publication/actuation qualification. The trusted verifier factory is exercised by the integration test, not proof that a production application deployment has enabled it.

**Release contract:**

1. Freeze and protect B07-A covariance/temporal contracts, B07-B trusted physical delivery authority, B07-C scientific publication/actuation separation and B07-SEC-01 through SEC-07 replay/transaction protections. Do not amend this qualified implementation as part of later cohorts except for a demonstrated regression subject to an explicit new acceptance gate.
2. Keep B2B-04B weather, B2B-05 plot/tenant authority, B2B-06 KMS and the independent Scientific Pilot PR #9 at their existing frozen versions; leave `main`, `findings/layer0.md`, and the master intended-architecture monograph unchanged.
3. PR #27 remains a stacked, unmerged integration PR targeting the frozen B2B-06 branch; the formal milestone freeze **does not authorize a merge** or direct deployment.
4. Any future B2B-08 work must branch from this **formal freeze documentation commit**, not from an older B07 candidate.

**Disposition:** **B2B-07 COMPLETE / FROZEN** at the milestone level; external deployment, real-field calibration, and release integration remain distinct milestones.

# Layer 0 B2B-07 — Physical Process Covariance, Delivered Irrigation & Scientific-State Separation

**Starting point:** formally frozen B2B-06 at `985b6af195ec9a7bc511c5e3d4690336ddc2d6d8`.  
**Qualified B2B-06 code:** `71b704788673c75d06f148255cddc4ee2070ade5`; local qualification receipt `4a0a92444b457a73f0e9d0aee0a2a52f4c6f7e3b`.  
**Working branch:** `feat/layer0-b2b07-process-q-irrigation-state-20261104`.  
**Status:** INITIAL INTEGRATED COHORT PLAN — **NOT IMPLEMENTED OR QUALIFIED**.  
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

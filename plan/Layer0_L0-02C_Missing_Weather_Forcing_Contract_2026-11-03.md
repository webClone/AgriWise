# L0-02C — Missing-Weather Forcing and Process-Uncertainty Admission

**Track:** Layer 0 remediation, independent of Scientific Pilot PR #9  
**Specification baseline:** `9ae80de727aa9f4be18e05ac628c5b90026f452f` (L0-02B draft)  
**Master monograph:** authoritative intended architecture; unchanged  
**State:** scoped pre-implementation contract; NOT an accepted software repair

## 1. Observed production boundary and why event pass-through alone is unsafe

- `layer0/kalman_engine.py:ZoneKalmanFilter.step` invokes
  `predict_missing_weather(day)` without its `events` argument.
- `ZoneKalmanFilter.predict_missing_weather` invokes
  `ProcessModel.predict(state, {}, None, skip_weather_forcing=True)`.
- In `layer0/state_vector.py:ProcessModel.predict`,
  `skip_weather_forcing=True` returns a state clone and fixed Q without
  processing management events.
- The normal weather path sums any `{"event_type": "irrigation",
  "amount_mm": ...}` without distinguishing a forecast, plan, user report,
  or independently verified delivered exposure.
- `layer0/user_input_schema.py:IrrigationEvent` describes its amount as
  **user-declared**. `user_input_adapter.py` transports it as a
  `USER_EVENT` with heuristic uncertainty, not verified actuator telemetry.
- `layer0/state_engine.py:run_from_packets` collects event payloads based
  on `event_type`; it does not establish physical delivery authority.

Therefore, forwarding every event to missing-weather prediction would create
an unsafe new physical-state path. A user-declared event is useful evidence
but cannot silently acquire **measured net infiltration** authority.

## 2. Required typed admission contract (before physics changes)

Each relevant management event must preserve:

- Tenant/plot/zone identity and canonical geometry version.
- Immutable event/receipt ID and occurrence interval (UTC, role-aware).
- Event role: `PLANNED_SCENARIO`, `USER_REPORTED_EXPOSURE`,
  `VERIFIED_DELIVERY`, or `UNKNOWN` (not inferred from source alone).
- Gross delivered water versus **net plot/soil-boundary infiltrated depth**,
  with units and explicit support. A gross pump meter reading is not a
  soil-infiltration observation.
- Measurement/error model, interval, source, and verification receipt ID.
- Reconciliation status: accepted, deferred, duplicate, blocked, or unusable,
  with reason and retention of the original evidence.

Fail closed for malformed, nonfinite, negative, time-incompatible, wrong-plot,
duplicated or unsupported events. Zero observed delivery is a valid zero;
it must not be conflated with missing. A reported event may be retained for
diagnostics or scenario analysis without applying a verified water impulse.

## 3. Separate missing-weather physical transition

If temperature, precipitation, ET0 or required weather qualification is missing:

1. Do not borrow tomorrow's weather or substitute silent typical temperatures,
   rain=0, or ET0=3. This path must remain visibly `MISSING_FORCING`.
2. Keep unknown weather-driven GDD, ET, thermal stress and LAI response
   unavailable or explicitly modeled with stated assumptions/uncertainty.
3. Apply a **verified net infiltration** event only if its physical soil
   boundary, depth and uncertainty are specified; otherwise defer it.
4. Propagate soil profile response using a support-aware water operator and
   its Jacobian, recording infiltration, percolation, storage-bound correction,
   and remaining unknown weather terms separately.
5. Do not equate `delivery_mm` with `infiltrated_mm`, and never manufacture
   actual water from an irrigation recommendation.
6. Use the same admission rules for weather-present and weather-missing paths.
   Exactly-once event identity must survive retries and day replays.

## 4. Q(Δt) qualification

The current `5.0 * Q` missing-weather factor is a heuristic, not a physical
covariance model. **VPD cannot be reconstructed from absent weather**.
Avoid replacing a heuristic with a more elaborate invented climate signal.

Proposed Q contract:

- `Q_process`: validated/declared model-error covariance by crop, stage,
  support, Δt, calibration version, and horizon.
- `Q_forcing`: Jacobian-propagated **available** forcing measurement
  uncertainties (if any), with inter-source dependence preserved.
- `Q_exposure`: uncertainty from qualified delivery/infiltration inputs,
  including measurement and allocation support.
- `Q_missing`: explicitly versioned conservative uncertainty for missing
  drivers, calibrated from withheld-weather replay on reference sites;
  it may grow with outage duration and must not claim measurement authority.
- Validate matrix finiteness, units, positive semidefiniteness,
  boundedness/applicability and serialization provenance; no arbitrary
  minimum uncertainty disguised as a measurement.
- For each supported mode:
  `P_next = F P_prev Fᵀ + Q_process + Q_forcing + Q_exposure + Q_missing`.
  Conservative missing-input behavior must be checked against actual
  reference observations and operational eligibility constraints.

## 5. Cohesive implementation slices

1. **L0-02C1 — Event identity/admission ledger**: typed roles, finite/support
   checks, duplicate detection, preserved deferred and blocked evidence,
   temporal and spatial admission checks.
2. **L0-02C2 — Qualified event forwarding**: normal and missing weather
   consume the same admitted event envelope; unqualified exposures never
   mutate state. Demonstrate user-declared versus verified receipts.
3. **L0-02C3 — Partial transition + Q composition**: physically supported
   net infiltration transition, explicit unknown weather, full covariance
   propagation and uncertainty provenance. Retire `Q×5` only when replaced
   by qualified/identified uncertainty.
4. **L0-02C4 — Replay & integration gates**: cross-zone conservation,
   exactly-once delivery, historical cutoff, Layer 1/ASMAE receipts, long
   horizon PSD, time/memory benchmark and per-crop calibration sensitivity.

## 6. Mandatory counterexample acceptance cases

- Missing weather + verified delivered/net infiltrated water => one recorded
  supported water impulse, no fabricated temperature, rain, ET or phenology.
- Missing weather + **user-declared** or **planned** irrigation => preserved
  evidence and reason for no authoritative physical application.
- Available weather + planned irrigation => no actual exposure promotion.
- Repeated event IDs or replayed windows => no double application.
- A zero-volume verified event => retained as zero, not missing.
- Wrong plot, zone, geometry, time cutoff, units, negative or nonfinite
  infiltration => blocked before any state/covariance mutation.
- Unknown weather over 1, 5, 30 days => monotone defensible uncertainty
  according to qualified missing-driver policy, PSD covariance.
- Weather observed again => reconciliation avoids reapplying same event or
  treating missing-weather assumptions as measured history.

## 7. Release criterion

This document is a preflight acceptance contract, not an implementation
receipt. Do not merge L0-02C on the strength of this specification or
the previous L0-02B suites; each code slice needs its own focused tests,
downstream Layer 1 and ASMAE verification and compatibility review. The
monograph and Pilot PR #9 remain untouched.

# Layer 0 — Bounded Remediation Disposition Supplement (2026-11-03)

**Role:** status-only supplement to the frozen `layer0.md` source audit and
`Akaloris_Layer0_Remediation_Parallel_Deep_Check_2026-11-03.md`. This does
**not** rewrite the audit, recategorize its 469 IDs or modify the R3 monograph.

**Repository:** `webClone/AgriWise` — all entries below need to be evaluated
against exactly pinned commits, never the mutable branch name alone.

## Independent workstream / source pins

- Scientific Pilot PR #9: `71ee1f788ec981bd0824089e46dc68164260444d`
  (independent branch; not modified).
- Legacy frozen Layer 0 source audit: `main@6edd3721c0defa7eed94b44cf96601ba59a49696`.
- L0-01/02A fixes: `cca8fedcb0f21c5e294571a8cd2c044d05953f71`.
- L0-02B smooth-stage/Jacobian and 365-day regression source:
  `9ae80de727aa9f4be18e05ac628c5b90026f452f`, draft PR #10.
- L0-02C plan-only baseline:
  `699074d0c4c2c71f3f07d853540d28a42729ec26`.
- Bounded math/QA corrections:
  `511e4e5781b82796f79911c41122be29200173d3`, draft PR #11.
- Event evidence admission and weather availability:
  `91a9b49500e26ca2ac94ddaf29221867a3db6ddf`, draft PR #12.

## Current disposition register

| Finding / scope | Source evidence | Corrective candidate | Disposition |
| --- | --- | --- | --- |
| L0-JAC-01 (new PR-specific numerical counterexample) | Native derivative diverged near photosynthesis switch; sigma 316.1556 | C1 smooth recovery/shutdown blend, parameter domain guard, transition and step-size tests in PR #11 | **Code corrected; fresh tests and empirical qualification PENDING** |
| L0-005 effective scene QA | Native scene score 0 moved LAI 0.2→1.8721 despite zero packet effective weight | Canonical `pkt.effective_weight()`, reject/counter, propagate actual weight, remove hidden 0.1 R floor in PR #11 | **Code corrected; fresh native/downstream tests PENDING** |
| L0-014/015 observation dispatch + sigma | Source mapping and sigma mismatch | L0-01 exact type/sigma mapping | **Prior bounded tests reported passing; not universal sensor calibration** |
| L0-017/018 weather/event semantics | Missing weather ignores events; partial truthy weather invents defaults; Q×5 | PR #12 complete/partial/missing availability and evidence-only role ledger | **Partial software control: no raw physical impulse; Q and verified L3 forcing OPEN** |
| Event replay and role authority | Planned/reported/claimed-verified treated alike; duplicate event IDs | PR #12 per-zone per-run evidence identity, explicit defer/reject reasons | **Partial. Trusted delivery, durable exactly-once, L3 net infiltration OPEN** |
| L0-001 forcing hash identity | Forcing values omitted from source package hash | No correction in PR #11/12 | **OPEN; publication identity prerequisite** |
| L0-002 plot/geometry binding for observations | Foreign packet can move a requested plot | Event evidence scope now checked in PR #12 only | **Observation identity OPEN** |
| L0-003 plot observations replicated to unsupported zones | Cloned plot evidence reported as independent zone update | No correction in PR #11/12 | **OPEN; spatial support prerequisite** |
| L0-004 missing affirmative source grants | Absence of positive grants can still admit observations | PR #11 fixes only zero effective quality | **OPEN; positive authority receipt prerequisite** |
| L0-009/F09 persistence | Legacy serializes only covariance diagonal | Not activated by canonical state engine | **CONDITIONAL / OPEN before activation** |
| Crop-specific calibration and bounded states | Provisional GDD/emergence, QA and response model coefficients | Smoothness guards are numerical, not empirical | **Scientific validation OPEN** |

## Execution receipts and merge policy

The independent uploaded review re-ran selected native controls at prior
`699074d` / `9ae80de` production blobs, not at PR #11 or PR #12 heads.
Previously user-reported 42/42 L0, 21/21 L1 and 84/84 ASMAE refer to the
older `6fe7360` baseline, **not** these new corrections.

**No fresh suite execution has been performed by the authoring assistant in
this GitHub connector session**. The new tests and code changes are present
as candidates, not accepted repairs. Required on the exact candidate SHA:

```powershell
py -m pytest -q services/agribrain/layer0/tests/test_photo_shutdown_jacobian_regression.py
py -m pytest -q services/agribrain/layer0/tests/test_packet_scene_qa_influence.py
py -m pytest -q services/agribrain/layer0/tests/test_event_forcing_admission.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

Then a separate pinned cross-track integration must qualify:
- Legitimate and numeric-zero weather/observation, missing and partial weather,
  zero scene QA/reliability, foreign plot/geometry and zone evidence.
- Time/availability cutoff, source and scientific-role authority.
- Event reported/planned/verified claims; no delivery from a role string.
- No plot-level observation cloning into unqualified local zones.
- Layer 0 state stays `state_estimate`, never a measured raw observation.
- Proof chain binds exact model/parameter/version, forcing data values and
  source lineage before any new pilot publication or authorization.
- Actual provider/DB/browser/field receipts when stronger claims are made.

Do not promote any output to physical/prescription authority based solely on
the numerical model being smooth or its covariance being PSD. No implicit
pilot rebase and no merge to `main` until owner/integration gates pass.

## Explicit C1/C2 boundary

PR #12 deliberately **does not** create a privileged `VERIFIED_DELIVERY`
channel from untrusted packet text: every event disposition is
`state_update_allowed=False`. Even an event claiming
`VERIFIED_DELIVERY` remains deferred pending actual receipt verification.
Direct raw Kalman `predict(events)` is rejected; the canonical daily
`step` retains role/identity/time evidence and calls the process
transition without raw management events.

The lower-level `ProcessModel.predict(events)` still provides legacy
bucket-model simulation behavior for test/scenario code. It is **not**
a production authorization or a calibrated L3 water model. Until its direct
callers and shared hydrological boundary are reviewed, do not claim that
all Layer 0 event access paths are physically qualified.

L0-02C3 must bind the canonical trusted support-aware L3 water operator,
receipt verification, actual net infiltrated depth and its covariance.
L0-02C4 must supply durable exactly-once/restart and historical replay
checks. The current missing-weather `Q×5` heuristic remains open.

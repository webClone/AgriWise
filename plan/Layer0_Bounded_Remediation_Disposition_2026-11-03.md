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

## Addendum — L0-001 / L0-003 / L0-002 negative-scope implementation

**Basis:** user-reported local L0 **101/101**, Layer 1 **21/21**, ASMAE
**83/83** at exact `e1f37707b8a59ce7249b7b57a965d23ca0873d79`.
These reports qualify that **prior** head, not the following new commits.

- **L0-001, content identity candidate:** `source_package.py` now hashes
  all values in ordered `process_forcing` records, including typed
  `ProcessForcing` and `IrrigationProcessForcing` dataclasses,
  temporal/primitive/nested data. Unsupported objects or nonfinite numbers
  fail closed rather than being converted to arbitrary `repr()`.
  Counterexamples: equal count, different mm; typed amount/time; key-order
  invariance; actual zero versus absent; invalid records.
  **Status: PATCHED / UNTESTED**, not complete signed publication binding.
  Package identity is currently computed at construction; mutation/rebuild
  and downstream verification of identity before publication remain a
  separate integration gate.

- **L0-003, zonal support candidate:** `state_engine.run` no longer
  duplicates `observations_by_day["plot"]` into added zones. Unmeasured
  zones retain their own predictions and `n_obs=0`; explicitly supplied
  zone evidence may still assimilate. This removes one known route
  to invented independent zone observations but does not certify zone
  geometry/local support or correlated evidence.
  **Status: PATCHED / UNTESTED**.

- **L0-002, negative identity candidate:** canonical
  `run_from_packets` now rejects packets that **explicitly contradict**
  caller plot, supplied geometry hash or supplied geometry version; it no
  longer selects the canonical run geometry from the first packet.
  This also rejects explicitly foreign weather packets before forcing
  construction. **Status: PARTIALLY PATCHED / UNTESTED**.
  Packets with missing plot identity and calls lacking caller geometry
  still lack an affirmative receipt; matching caller-supplied strings are
  not independently signed/authorized proof. Close L0-002 only when
  trusted scope and geometry version are required at producer/caller
  boundaries and historical-cutoff checks pass.

- **L0-004, positive source admission:** **OPEN**. Explicitly false grants
  are denied, but missing affirmative provider/admission receipts are not
  yet universally blocked. Source-specific issuance and compatibility
  need a separate integrator-led gate, not additional arbitrary flags.

**New top-of-stack candidate:**
`fix/layer0-observation-scope-20261103` (draft, unqualified);
individual modules may be reviewed by commit, but integrate only one
pinned tip after all tests and shared-contract checks.

### Qualification commands at exact candidate HEAD

```powershell
git fetch origin
git switch fix/layer0-observation-scope-20261103
git pull --ff-only
git rev-parse HEAD
py -m pytest -q services/agribrain/layer0/tests/test_forcing_content_identity.py
py -m pytest -q services/agribrain/layer0/tests/test_plot_zone_observation_support.py
py -m pytest -q services/agribrain/layer0/tests/test_packet_scope_negative_admission.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

Record collection counts as well as passed counts. ASMAE **83/83**
at `e1f3770` versus older **84/84** must be reconciled to exact
collection/interpreter and revision before interpreting a changed count.

Do not merge any Layer 0 draft PR into the scientific pilot or `main`
on the strength of unit tests alone. Pilot PR #9 remains independent.
Cross-track proof still needs full model/forcing source binding, qualified
positive observation grants, plot/zone support and availability, and
issuance/replay validation.

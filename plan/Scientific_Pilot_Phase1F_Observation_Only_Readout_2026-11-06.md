# Akaloris Scientific Pilot — Phase 1F Observation-Only Readout

**Implementation:** isolated pilot continuation branch `feat/pilot-phase1f-observation-only-readout-20261106`.
**Base:** Scientific Pilot PR #9 head `71ee1f788ec981bd0824089e46dc68164260444d`.
**Status:** Source implementation and tests added; exact-head qualification **PENDING**.
**Protected:** PR #9, frozen B2B-01..08, post-freeze signed-delivery branch `6b6767c`,
`main@6edd372`, weather PR #25, historical `findings/layer0.md`, intended master monograph.

## Purpose

Make the existing canonical ASMAE publication **safely inspectable in the
observation-only pilot** without coupling pilot progress to the outstanding
signed-delivery checkpoint/recovery defects.

This phase is **not** a field-validated agronomic recommendation, machine
control capability, independent source attestation, new ASMAE assimilation,
or approval to merge/release the broader pilot.

### Included code

- `services/agribrain/orchestrator_v2/pilot_observation_only_gate.py`:
  `read_observation_only_pilot_status(...)` only accepts an authenticated,
  server-owned `PlotNamespace` plus expected snapshot/geometry/cycle obtained
  from trusted server state; it never accepts a raw snapshot from a client.
  Reuses `read_trusted_current_asmae_publication`, which re-fetches the
  locally revalidated canonical head and checks exact owner/plot/cycle/geometry,
  all ten existing publication-integrity flags, immutable publication receipt,
  and temporal ordering. No L8 proof attestation is required for observational
  inspection.
- Returns a deliberately limited observation status: immutable snapshot
  identity and receipt/manifest hashes, observed time window, cutoff, age,
  freshness/archival classification and explicit uncertainty about field truth.
  It **never** returns an irrigation recommendation, authorization envelope,
  executable plan, issuer material or approved action. Publication and
  actuator authority are both false, always.
- The existing `pilot_scientific_fail_closed_probe.py` now records the
  local signed-L3 enablement check and refuses to read a snapshot when the
  local `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION` flag is not disabled.
  This is a **local-process check**, not a remote deployment attestation.
- Unit and source-wiring tests are added. The canonical store is stubbed in
  these tests to exercise the native reader's scope/temporal/flag validation:
  they **do not** claim independent physical evidence, live sensor ingestion
  or production HTTP authentication.

## Invariants

1. Set `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false` in every
   Scientific Pilot process. Unknown or enabled settings refuse execution.
   An unset flag has the existing disabled-by-default semantics, but explicit
   `false` is recommended for operator-visible staging.
2. A canonical snapshot is an observation product, **not** a permission
   to issue prescriptions, export positive L8 authorizations, enable an
   actuator, or state that the field measurement has been calibrated.
3. Preserve the complete source cutoff / observation window; detect
   future or stale publication heads without fabricating newer evidence.
   A publication older than seven days is `STALE_OBSERVATION_ONLY` and
   cannot be described as current.
4. Canonical publication integrity is not independent agronomic accuracy.
   `live_sensor_to_asmae_chain_verified` and
   `independent_field_accuracy_verified` remain false.
5. The caller of the readout must have an **existing authenticated
   PlotNamespace**. Passing arbitrary namespace values from a public HTTP
   request is not authentication. Do not expose this callable directly
   as an unauthenticated endpoint.

## Focused qualification (operator's Windows workspace)

```powershell
git checkout feat/pilot-phase1f-observation-only-readout-20261106
git pull
git rev-parse HEAD
$env:AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION = "false"

py -m pytest -q services/agribrain/tests/test_pilot_phase1f_observation_only.py
py -m pytest -q services/agribrain/tests/test_scientific_pilot_baseline_probe.py
py -m pytest -q services/agribrain/tests/test_pilot_publication_gate.py
py -m pytest -q services/agribrain/tests/test_pilot_plot_a_e2e_qualification.py
```

The last Plot A test needs already locally provisioned genuine published
snapshot artifacts and has fixture-built downstream L8 proof objects. It
must be counted **separately** from independent source-to-ASMAE field proof.

For an existing live authenticated Plot A GET and an existing run record,
the baseline read-only operator procedure remains:

```powershell
$env:AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION = "false"
py services/agribrain/scripts/pilot_scientific_fail_closed_probe.py --self-test --snapshot-json pilot-snapshot.json --run-json pilot-existing-run.json --output pilot-observation-baseline-local.json
```

Do not commit the raw snapshot, run response, owner session cookie, or local
qualification receipts. The check **does not POST** or execute assimilation.

## Next scientific acceptance after this bounded readout

A real observed-only **sensor/provider → qualified Layer 0 observation →
Layer 1 fusion → ASMAE state update → canonical native publication →
authenticated owner read** chain is the next separate integration gate.

It must use an immutable actual source acquisition/provider receipt and
preserve exact event timestamps, units, spatial scope, signed provenance,
current authenticated plot identity, source QA/support and ASMAE lineage.
Forbid any fabricated source calibration, L8 decision witness, or
post-hoc evidence root. Run at least one concrete acceptance on a
captured source without constructing signed irrigation receipts.
Measure reliability, coverage, posterior consistency and currentness;
keep field truth and bias/calibration claims pending independent reference.

**Do not merge** this branch or PR #9 without explicit review. Signed L3
remains disabled, and the separate open checkpoint equivalence/journal gaps
stay in the dedicated physical-delivery workstream.

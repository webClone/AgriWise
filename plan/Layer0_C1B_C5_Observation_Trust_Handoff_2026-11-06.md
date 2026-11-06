# Layer 0 C1B / C5 — Observation-Only Cross-Layer Trust Candidate

**State:** CODE CANDIDATE. Exact-head regression and connected qualification **NOT RUN**.
**Branch:** `fix/layer0-c1b-layer1-handoff-20261106`
**Parent:** L0-C1A documentation head `9844892097876c9a8aff0b50e8a638e54b23ce67`
**Source L1 baseline:** `main@6edd3721c0defa7eed94b44cf96601ba59a49696` (unchanged).
**Signed irrigation:** MUST remain `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false` for Scientific Pilot.

## Bounded implementation

1. **C1B-01 — Canonical L0 state intake:** `Layer1FusionEngine.fuse`
   calls `require_admissible_layer0_state` before any adapters operate
   when `bundle.layer0_state_package` is provided. An absent L0 state
   is a missing-source gap, not an invented observation.
   The gate checks nominal Layer0StatePackage type, plot match, native
   contract version, nonempty run ID/geometry identity, C1 scientific
   state flag and runtime-integrity provenance, native structural audit
   PASS, zero execution/actuator permissions, zone/uncertainty presence,
   run-ID consistency and recomputed output hash. A dict or a manually
   relabeled unqualified result is refused before creating fusion evidence.

2. **C1B-02 — Derived-state truth:** `truth_bridge.normalize_evidence_truth`
   no longer classifies Layer 0 Kalman state as external observed
   `real_provider_raster`. It emits `data_status="assimilated"`,
   `truth_class="assimilated_state"`,
   `source_reality="model_estimate"`, no real-provider or
   scientific publication authority, and diagnostic-only,
   non-updating evidence.

3. **C1B-03 — Future evidence admission:** `validate_evidence`
   accepts an optional explicit replay reference time and permits
   **at most 5 minutes of positive clock skew** for a datetime
   `observed_at`. Normal engine and raster admission callsites pass
   `bundle.run_timestamp`. Larger future offsets or naive time
   references become structured quarantine reasons **before ledger
   insertion and freshness weighting**.

## Qualification commands

```powershell
git fetch origin
git switch fix/layer0-c1b-layer1-handoff-20261106
git pull --ff-only
git rev-parse HEAD
$env:AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION = 'false'
py -m pytest -q services/agribrain/layer1_fusion/tests/test_c1b_l0_state_temporal_gate.py
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
py -m pytest -q services/agribrain/tests/test_pilot_plot_a_e2e_qualification.py
```

**Expected new cases, not yet execution receipts:** canonical valid
state; missing state gap; 9 invalid/forged/tampered state variants;
3 future offsets; 4-minute clock-skew positive control; naive
timestamp rejection.

## Scope limitations and HOLD conditions

- **Tenant namespace not proven here:** `Layer1InputBundle` has a
  `plot_id` but no authenticated `tenant_id`, `scope_hash` or
  authoritative server principal. An in-process caller can construct
  a structurally valid Layer0StatePackage; output-hash recomputation
  detects mutation, **not a forged signed issuer or tenant authorization**.
  C5 must bind a trusted server-side `PlotNamespace` to the exact
  input root before public/remote Layer 1 admission.
- **Run identity:** L0 `run_id` denotes its execution attempt;
  L1 `run_id` denotes a separate fusion attempt. They are not
  incorrectly forced to be equal. Provenance run identity must match
  the original L0 run.
- **Source-backed chain not yet run:** The new tests are deterministic
  fixtures; do not claim independent field or calibrated sensor proof.
- **Future timestamps within tolerance** may be accepted and
  classified fresh. That is an explicit bounded clock-skew policy,
  not proof of physical availability at run timestamp. Timestamp-less
  observational records require separate source-specific controls.
- **Direct validator callers without `run_timestamp`** retain
  backward-compatible behavior; production acquisition acceptance
  must flow through the qualified engine path. Audit other public
  callsites before claiming systemwide enforcement.
- **C1 numerical PSD** and nonmutating Layer 1 context invariants
  are outside this batch.
- **L0-C2 physical receipt cutoff/journal recovery** remains open on
  its own workstream and should not be merged into this branch.
- **No production enablement, no merge, no Pilot modifications.**

## Acceptance (not yet granted)

Only after a verified exact-head test receipt, source-level consumer
trace, and **one real observation → L0 → L1 → ASMAE → canonical read**
qualified run can C5 be declared accepted. Until then C1B is a
corrective candidate, **not a frozen milestone**.

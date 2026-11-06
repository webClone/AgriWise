# Layer 0 C1 — Scientific Integrity / Full-Coverage Exit Gate

**Status:** Corrective candidate. Code is committed, **exact-head tests not yet executed**.
**Parent:** exit-gate report `plan/Akaloris_Layer0_Exit_Gate_Deep_Audit_2026-11-06.md` on this branch.
**Base:** `6b6767c655a3093d1bea9e40b8df792dd5a65267`.
**Dedicated branch:** `fix/layer0-c1-scientific-integrity-20261106`.
**Protected:** `main`, frozen B2B branches, signed-delivery post-freeze
branch, PR #9, Scientific Pilot Phase 1F/G, `findings/layer0.md`,
master architecture monograph.

## What is corrected in this bounded batch

### L0-X05 — Fail-closed scientific state export

`Layer0StateEngine.run` now executes the previously unused native
`enforce_all_invariants` via `assert_layer0_scientific_integrity` using
`auto_fix=False`. This does **not** inject default values, clamp a bad
posterior, or hide nonfinite/negative uncertainties.

Fail-closed errors now apply to:
- failed cross-source validation execution (previously converted to a
  printable conflict);
- invalid/nonfinite state or uncertainty, mismatching day/zone timeline,
  invalid/missing invariant checker, substantive invariant violation;
- failed self-audit execution (previously logged and then ignored);
- absent, malformed, DEGRADED or ALERT structural self-audit reports with
  failed checks.

The state package can only declare
`health_report.scientific_state_admissible=True` after these checks pass.
A Kalman-unavailable diagnostic package explicitly declares
`scientific_state_admissible=False`.
All output authority flags remain **false**. No actuation/pilot publication
authority is introduced.

`Layer0ScientificIntegrityError` is a terminal admission exception, not
a completed persistent operator failure ledger. L0-C4 must subsequently
record stable failure receipts and confirm Layer 1 enforces this marker at
all entrypoints. Legacy direct `Layer0Runner` and public consumer reachability
must be checked before claiming cross-layer acceptance.

### L0-X06 — Large-plot silent raster clipping

`PlotGrid.from_polygon_wgs84` now raises
`plot_grid_full_coverage_exceeds_single_grid_limit` if the requested
projected extent is wider or taller than the existing 500-pixel limit.

This is a **safe rejection**, not a tiled large-plot implementation. Full
large-plot support requires a separately qualified tiler with exact area,
mask and pixel-provenance continuity. The current approximate UTM projection
is unchanged; external authoritative projection/CRS validation is still
required before representing geometry as geodetically calibrated.

## Explicitly not closed by this batch

- L0-X01 signed irrigation checkpoint scope/cutoff equivalence.
- L0-X02–04 submitted/staged/committed journal and multi-day recovery.
- L0-X07 timestamp-based attempt ID vs stable scientific-input root.
- Empirical crop/sensor calibration, farmer-photo model training, SIF path,
  optional legacy persistence, complete 469-ID adjudication.
- Layer 1 trusted input and independent field validation.

## Focused execution and regression requirements

```powershell
git fetch origin
git switch fix/layer0-c1-scientific-integrity-20261106
git pull --ff-only
git rev-parse HEAD
$env:AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION = 'false'

py -m pytest -q services/agribrain/layer0/tests/test_l0_c1_scientific_integrity_exit_gate.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

Acceptance:
1. New invariants and audit negatives reject **before** a state package
   reaches Layer 1, without silently modifying the evidence.
2. Actual existing full Layer 0 regression does not reveal expected
   unqualified outputs previously treated as valid. If it does, fix
   those upstream defects; **do not disable the new gate to make tests pass**.
3. Explicitly run large-plot and small-plot bounds tests; reject before
   allocating a truncated alpha raster.
4. Preserve exact authority flags as false and signed irrigation OFF.
5. Record exact branch/commit/test/warning/skip/error receipts. No
   formal C1 freeze until the operator executes and confirms all gates.

## Scientific caution

A passing numerical contract establishes a structurally valid **state
estimate**, not measured ground truth. It is not a proof of full covariance
PSD, plant-model calibration, exact field-area support or a successful
L0→L1 evidence-ledger handoff. Those remain separate acceptance gates.

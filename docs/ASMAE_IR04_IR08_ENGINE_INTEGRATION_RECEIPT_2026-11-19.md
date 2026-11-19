# ASMAE IR-04 / IR-08 — Bounded engine integration receipt

**Date:** 2026-11-19  
**Target:** `webClone/AgriWise`  
**Integration branch:** `feat/akaloris-asmae-ir04-ir08-engine-integration-20261119`  
**Verified branch parent:** `3f92f7038a35a7834f1eea08f1be718978dbb401`  
**Pushed integration head (before this receipt):** `eaf7bee7f52f5745dfa086c15290bde9d00888c0`

## Scope delivered

1. Removed both scene-wide/plot-wide `current_1m_approval_allowed` promotion shortcuts from the engine's local-resolution certification logic. Current fine-resolution certification remains disabled without independent state × cell evidence.
2. Kept 1 m and 2.5 m model-assisted diagnostics as advisory **display**, without raising the effective scientific support scale above 10 m based on retro/BMA or interpolation alone.
3. Added `resolution/statewise_engine_bridge.py` to evaluate all 13 states against the selected *scientific graph grid*, with per-state, per-cell effective-resolution metadata and local-support classes. Cells with no admitted state-specific evidence keep `effective_resolution_m = null`.
4. Wired the engine to the new bridge using the authoritative `grid_spec` and `(T, K)` replay receipt; runner now passes tenant and farm namespace and replay receipt into `ASMAEInput`.
5. Bound a nonempty statewise support digest into scientific output `content_hash`; legacy outputs without a valid support digest do not acquire invented authority.
6. Added bounded memory and spatial-grid mismatch guards. Display-resampled quick-visual pixels cannot be reinterpreted as scientific graph cells.

## Local verification actually executed

`PYTHONPATH=/mnt/data/asmae_ir04_integration python -m pytest -q .../test_asmae_ir04_engine_bridge.py`

**8 / 8 local bridge tests passed**: no-evidence negative control, graph/display mismatch, missing K, state/cell differentiation using an illustrative footprint, future observation exclusion, deterministic digest, invalid geometry hash, and invalid knowledge cutoff.

**Not executed:** full `layer05_asmae` regression, end-to-end ASMAE ensemble runtime tests, JavaScript/frontend tests, hardware tests, provider tests, publication tests. There were no CI status checks/workflow runs on the pushed head at verification time.

## Scientific/operational limitations — remain OPEN

- `qualified_footprints=()` is intentionally supplied by the engine until there is an **independent authenticated source-to-state observation-operator binding**. No incoming client metadata can certify 1 m or create fine authoritative maps. The bridge is a conservative metadata pipeline, **not proof of actual subpixel reconstruction**.
- The ASMAE EnKF/ETKF numerical graph still uses its selected run-level scientific grid; the new statewise tensor does **not** implement a locally adaptive finite-element mesh or physically justified multiscale operator yet.
- Scalar-only states are not fabricated into raster maps. Actual 13-state exploratory map/UI and state-specific source footprints require further work.
- Legacy `ASMAE_EFFECTIVE_RESOLUTION_MAP` is labelled advisory/display-only; only new statewise support with independent evidence should be used for scientific resolution claims.
- Historical archive and R01 publication certifications, 1 m spatial certification, and physical actuator authority remain on hold.
- The frozen 238 findings, the 40/48/150 repair cohorts, main at `6edd3721`, and PR #30 at `599c4f6` are unchanged. No finding is independently closed by this receipt alone.

## Next bounded qualification gates

1. Run root fast tests + ASMAE tests on **this exact remote branch** and capture stdout/versions; fix regressions before moving patches into candidate.
2. Introduce an independently authenticated `EvidenceFootprint` adapter from the actually consumed H_t operators, sensors, PSF, registration, geometry and bitemporal receipts; test local support per state and location.
3. Verify the tensor and digest survive immutable snapshot publication/replay without spatial authority upgrades; then continue the existing IR-08 numerical mesh and IR-06 frontend sequence.

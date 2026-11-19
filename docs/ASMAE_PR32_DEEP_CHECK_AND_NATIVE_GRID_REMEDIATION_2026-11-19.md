# ASMAE IR-04 / IR-08 — PR #32 independent source review and bounded native-grid corrections

**Date:** 2026-11-19  
**Repository:** `webClone/AgriWise`  
**Target:** Draft PR #32 (`feat/akaloris-asmae-ir04-ir08-engine-integration-20261119`), base `feat/akaloris-asmae-ir03-bitemporal-replay@3f92f7038a35a7834f1eea08f1be718978dbb401`  
**Verified starting head:** `22db86940c0f3cea186dea01fb072bc2fd241ef0`  
**Frozen audit:** `a86effb364e46f0806613babcd1b1edfed018157` / 155 files / 238 findings (3 P0, 133 P1, 99 P2, 3 P3). **No original finding is independently closed by this review.**

## Independent verification

- GitHub PR #32 is open, draft, and targets the remediation branch; it is **not merged**.
- Source inspected directly from GitHub: `engine.py`, `resolution/statewise_engine_bridge.py`, `resolution/state_cell_support.py`, `schema.py`, `runner.py`, `invariants.py`, and `feature_export.py`.
- Locally reran the independently mountable, bounded new suites against the same module blobs: **28/28 passed** (18 contract + 10 bridge, after two additional regression tests). These tests **do not exercise full ASMAE, the complete feature exporter, or actual publication**.
- The user's **176-pass Layer 05** and **337-pass frontend** reports are retained as **reported external test receipts**, not independently reproduced by the present tools. No PR-head CI checks or workflow runs were found at the starting head.

## Confirmed defects and disposition

| ID | Severity | Evidence / consequence | Action and status |
| --- | --- | --- | --- |
| IR04-R01 | P1 | `engine._assemble_output()` bilinearly resampled `raster_maps` before `build_statewise_engine_support()` compared those rasters against the native graph. Enlarged quick-visual grids were marked `display_resampling_or_grid_shape_mismatch`, even when a valid native posterior existed. | **Corrected in draft branch**: capture the native scientific map dictionaries before display interpolation; feed these into the statewise bridge. Negative-control tests B09 and B10 added. Full engine regression pending. |
| IR04-R02 | P1 | Before correction, `raster_maps`, `uncertainty_maps`, `confidence_maps`, `retrovalidation_maps`, and `bma_maps` were **reassigned** to display-interpolated arrays while `ASMAEOutput.grid_spec` retained the authoritative graph geometry. `invariants.py` does not test this shape binding; `feature_export.py` reads those arrays as scientific features. This can misrepresent spatial provenance and change the scientific numerical identity merely due to display resolution. | **Corrected in draft branch**: retain canonical map dictionaries on the scientific graph; write interpolated arrays into `diagnostics["display_only_overlays"]` with a display-only, uncertified role. Full exporter/UI/publisher regression pending. |
| IR04-R03 | P1 | Actual engine passes `qualified_footprints=()` to statewise bridge. The contract accepts `EvidenceFootprint` instances, but does **not authenticate** their source/operator digests or receipt provenance. Fictitious fingerprints can be passed to the *isolated contract test* to simulate valid support; they must not become an upstream admission path. | **Open**. Implement a source-authoritative Hₜ-to-footprint adapter (admitted scene, actual Hₜ operator, calibrated PSF, nodata mask, immutable tenant/plot/geometry, valid time T, committed time K, and parent lineage), with forged-manifest negative controls. Until then, no state-cell fine claim. |
| IR04-R04 | P1 product availability | `ASMAEInput` receives a `bitemporal_replay_receipt`, but ordinary live executions may lack an explicit `(T,K)` receipt. The bridge fails closed and returns `unavailable`, even when a model posterior exists. | **Open**. Bind actual runtime knowledge watermarks from Worldline; never synthesize K from a present wall clock or a historical observation date. Retain exploratory posterior separately when temporal evidence is absent. |
| IR08-R05 | P1 scale | Bridge stops at `MAX_STATEWISE_CELLS=4096`. This is an explicit capacity guard, **not** a scalable heterogeneous spatial model; selected-graph EnKF remains run-wide resolution. | **Open**. Tile/chunk state-cell evidence with cryptographically bound tile geometry and deterministic composition. Do not remove resource bounds before bounded storage and serving. |
| IR04-R06 | P2 epistemic | Legacy `ASMAE_1M_ADVISORY_MASK` is still derived from retro/BMA and may be 1 on 10 m scientific output, while `ASMAE_EFFECTIVE_RESOLUTION_MAP` is constrained to >=10 m. It is an advisory research diagnostic, **not** evidence of 1 m resolved science. | **Open**. Preserve the distinction at downstream UI/publication and test that no consumer promotes advisory 1 m flags to certified effective resolution. |

## Corrections pushed to Draft PR #32

- `07fc538680f5402099d6a8b9187d3ff34fb7f2ef` — preserve original native scientific map inputs for the statewise support bridge before display resampling.
- `1bf1481645ccd510c5b90e0127dd24753cced498` — add B09 native/display isolation and B10 explicit oversize-grid negative controls; **10/10 bridge tests**, **28/28 combined isolated tests** pass locally.
- `e7fcc428d1a4c5badacd1196b92dc29d11b8b423` — keep canonical `ASMAEOutput` scientific maps on the unresampled graph grid and store bilinear overlays separately in `diagnostics["display_only_overlays"]`.

## Next bounded qualification sequence (existing plan unchanged)

1. **Full Layer 05 regression** on updated PR head; specifically exercise standard and quick_visual paths with input scientific graph ≠ requested display grid; check output `grid_spec.height/width` matches each state grid, uncertainty, confidence, retrovalidation, and BMA grid. An existing full suite result for the prior PR head is insufficient.
2. **Immutable cold publication + historical replay** with both modes. Ensure downstream exporters and surface admission read only native, graph-bound `raster_maps`; display-only overlays must not be accepted as scientific pixels.
3. **Authenticated Hₜ operator adapter** with forged receipt, tenant crossing, wrong geometry, late commitment, future-valid time, PSF mismatch, masked pixel, shifted transform, cross-state observability, and no-subpixel-observation adversarial controls. This is the actual next IR-04 qualification step, rather than another fake-geometry positive test.
4. **IR-08 adaptive numerical graph and tiled statewise support** after verified footprints, preserving memory bounds and stage-separated display resampling.
5. **IR-06 thirteen-state UI** may show legitimate spatial/scalar/prior/unavailable results with uncertainty, but never imply that scene-level or model-only evidence constitutes local fine resolution.

**Governance:** All 238 frozen findings remain unchanged. Protected `main` and PR #30 must remain untouched. Actuator authority, numerical publication certification, and 1 m spatial certification remain on hold. PR #32 must stay draft until full engine regression and cold publication are independently evidenced.

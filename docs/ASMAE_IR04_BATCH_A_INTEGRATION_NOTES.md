# ASMAE IR-04 Batch A — integration boundary

**Intent:** prepare a defensive, state × cell × valid-time × knowledge-time evidence-support contract that can be cherry-picked onto the real candidate branch. It does **not** authorize certified 1 m maps and does **not** modify ASMAE's engine, publisher, historical journal, UI, monograph, or the original finding register.

## What is in this patch

- `resolution/state_cell_support.py`: `GridSpec`, `EvidenceFootprint`, `StateCellSupport`, `evaluate_state_cell_support`, `statewise_support_tensor`, and display-only metadata.
- `tests/test_asmae_ir04_ir08_adaptive_resolution.py`: 16 isolated contract tests covering A01–A12 logic and extra negative controls. These are **contract-level tests only**. They do not simulate a real EnKF, reconstruct a mesh, attest providers, prove full bitemporal journal replay, or validate the frontend.

## Important security boundary

`EvidenceFootprint` is an **input record**. Merely providing `calibrated_operator_sha256`, `source_sha256`, `observability`, or `independent_holdout_sha256` does **not** authenticate a sensor or certify a resolution. Upstream Layer 0/1 proof admission, signatures, calibrated observation operators and independent validation remain mandatory before any output is operationally trusted. This module never sets `certified_1m=True`, even for local 1 m source support.

The evaluator explicitly ignores scene-wide `1m` approval and high retro/BMA scores as substitute evidence. A finer source sensor cannot improve the resolution of a coarser **scientific output grid** until the solver itself uses a finer grid or a physically legitimate adaptive representation. Display resampling retains a source-support digest.

The implementation is intentionally strict about metric, unrotated reference grids. Reprojection, sheared grids, PSF convolution, spatial localization, full operator conditioning and adaptive solver mesh are not provided by this additive patch. It fails closed rather than pretending to resolve mismatched CRS.

## Planned integration, in the existing work order

1. Confirm `git rev-parse HEAD` on `feat/akaloris-asmae-ir03-bitemporal-replay` equals the *full* expected candidate SHA and working tree is clean.
2. Apply the additive patch (`git am path/to/patch`), inspect files and run `py -3.13 -m pytest services/agribrain/layer05_asmae/tests/test_asmae_ir04_ir08_adaptive_resolution.py -q`.
3. **Batch A integration**: build `EvidenceFootprint` from actual admitted observations, calibrated H operators, and immutable `(T,K)` receipts; do **not** instantiate evidence hashes directly from a request or trusted-by-default flag. Replace scene-wide local claim shortcuts in `engine.py` and `resolution/policy.py` only after upstream authorizations are anchored. Keep the certification hold.
4. **Batch B integration**: maintain real statewise spatial grids/partitions (or equivalent multiscale representation) through EnKF, graph coupling, numerical support, publication identity, replays and rendering. A tensor on a single reference grid alone is not adaptive inference.
5. **Batch C integration**: expose all 13 states via spatial posterior / scalar posterior / prior-only / unavailable modes without synthetic raster creation. Validate cold/historical API and frontend.
6. Run R01, IR-03, IR-05 regression suites, A01–A12 end-to-end acceptance tests, and genuine provider/field spatial qualification before closing frozen findings.

## Known limitations

No existing production file is modified; the test is standalone. There is no guarantee of compatibility with the inaccessible `8b1cc96` source until the patch is applied and reviewed there. The patch's own Git commit is a packaging identity, not an AgriWise deployment or GitHub commit. No 1 m certification, numerical publication authority or actuator authorization is granted.

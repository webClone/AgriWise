# ASMAE W3-A implementation — qualification hold

Base: PR #32 `64a9f699` via the original red-spec branch; PR #32 itself unchanged.

## Implemented
- `layer1_fusion/raster_ingest.py`: retain actual `RasterRef` class instance for canonical posterior-concentration confidence; deterministic priority over legacy aliases; dedupe alias duplicates. Diagnostic references never gain state or prescription authority. When the source omits a sigma, retain `uncertainty=None` instead of fabricating 1.0.
- `layer10_sire/invariants.py`: evaluate `INV-COMPOSITE` truthfulness and grid checks before any non-ASMAE early exit.
- `layer10_sire/runner.py`: classify `COMPOSITE_*` as a separate advisory branch of ASMAE policy, not a satellite full-raster fallback. Require current spatial evidence and visualization authorization. Map `ASMAE_POSTERIOR_CONCENTRATION` explicitly to diagnostic support without equating it with any of the 13 latent states or 1m certification.

## Acceptance commands (not run here)
```powershell
python -m pytest services/agribrain/layer1_fusion/tests/test_asmae_w3a_confidence_composite_contract.py -q
python -m pytest services/agribrain/layer10_sire/tests/test_asmae_w3a_runner_diagnostic_mapping.py -q
python -m pytest services/agribrain/layer1_fusion/tests/ services/agribrain/layer10_sire/tests/ -q
python -m pytest services/agribrain/layer05_asmae/tests/ -q
node scripts/run-frontend-tests.mjs
npx tsc --noEmit
```
Add full production artifact mutation, real Layer10Output and cold plot-workspace pixel mask tests before closing spatial integrity issues. No certified 1m, no numerical scientific publishing, no actuation.

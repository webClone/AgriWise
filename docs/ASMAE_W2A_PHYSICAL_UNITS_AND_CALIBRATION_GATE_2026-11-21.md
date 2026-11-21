# ASMAE W2-A — Unit-bearing physical semantics and crop calibration gate
**Date:** 2026-11-21
**Baseline:** draft PR #32 `64a9f69945d8e3eda2bf33de9ff24e98186c9a17`
**Status:** Implementation candidate, tests authored but **NOT executed**.

## Physical scientific contract
- Chlorophyll is **`ug/cm2`**, numeric domain [0,80]; canopy water is physically dimensionless *content*, source semantic tag **`fraction_content`**, domain [0,1]. Neither is directly leaf N concentration, nitrogen deficiency probability, canopy water stress probability or an irrigation prescription.
- The new `scientific_contracts/asmae_physical_semantics.py` rejects untagged floats, wrong units, nonfinite/bool and out-of-domain values. It separates a research crop-calibrated chlorophyll deficiency index from downstream scientific authority.
- Even a client-created calibration record marked `qualified` cannot affect Layer2/Layer4 without a **trusted calibration verifier callback**. No production callback is wired in this batch: absence means no chlorophyll-driven inference, preserving the hold.
- Central ASMAE feature accessor now preserves only explicitly supplied source units, with optional unit field appended for positional constructor compatibility.
- Layer4 runner passes physical tagged quantities and no longer relabels `ASMAE_CANOPY_WATER` as `asmae_water_stress`. Nutrient inference withdraws uncalibrated 0.45/0.65 heuristic from N and generic chlorophyll-to-P/K adjustment; requires separate trustworthy crop calibration before N mapping. Old direct water-content penalty removed.
- Layer2 attribution similarly withholds uncalibrated chlorophyll-to-N attribution. Layer7 stops treating high water content plus moist soil as stress conflict, and stops comparing leaf chlorophyll units directly with soil lab N ppm. Unit violations are explicit diagnostic reasons without creating a false conflict penalty.
- `layer2_veg_int/asmae_prior_bridge.py` comment corrected: crop group chlorophyll bounds 24–72 **ug/cm2**, not 0–1 normalized. Catalog metadata explicitly states `source_unit_tag` for chlorophyll and canopy content.

## Qualification
```powershell
python -m pytest services/agribrain/tests/test_asmae_w2a_physical_semantics.py -q
python -m pytest services/agribrain/tests/ -q
python -m pytest services/agribrain/layer05_asmae/tests/ -q
node scripts/run-frontend-tests.mjs
npx tsc --noEmit
```
Plus all Layer2, Layer4, Layer7 and cross-layer product regression tests at the exact SHA. Validate healthy/stressed field scenarios per crop and phenology against **real leaf-assay + canopy-water observations**, including inter-observer calibration uncertainty. A genuine calibrated model must bind crop, phenology, lab method, expiry, revocation and uncertainty. Current source test mappings are controlled examples only, not field-calibrated results.

## Deliberately unresolved
- Actual trusted issuer implementation for calibration verifier and crop/phenology calibration evidence dataset.
- Older stored ASMAE features without source unit tags fail closed for physical downstream inference until re-ingested with validated metadata.
- Production soil N and canopy-water cause attribution, yield adjustments, action permissions, 13-state maps, 1m scientific resolution and physical actuation remain separate gates.
- PR #32 unchanged, original 238 register retained, zero new independently closed findings.

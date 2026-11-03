# Layer 0 — B2B-03A Native Sentinel-1 Acquisition and SAR Structure Screening

**Date:** 2026-11-03  
**Parent SHA:** `2644100a8b89422bec195a8f53b155850175a27b` (PR #21, reported fully software-qualified 425/425)  
**Branch:** `fix/layer0-s1-native-qualification-20261103`  
**Status:** Source-level IMPLEMENTED CANDIDATE; exact-head pytest, live provider, calibration and scientific authorization pending  
**Governing plan:** PR #17 `fb28f0e49edeeb350db8651dfdd4d0c7a36e6722`  
**Isolation:** no edits to Scientific Pilot PR #9, main, R3 monograph or frozen historical Layer 0 audit.

## Parent qualification reconciliation

The repository owner supplied the final PR #21 Windows Python 3.13.13 receipt at `2644100`:
- Layer 0 **320/320** (including native request replay 23 and S2 qualifier 48)
- Layer 1 Fusion **21/21**
- Layer 0.5 ASMAE **84/84** (83 fast plus comprehensive real-raster 1/1 in 683.23 seconds)
- Aggregate **425/425**, 0 failures, 731.67 seconds reported.

**These qualifications belong to the parent revision only.** B2B-03A does not inherit these test passes.

## Proven SAR-specific requirements

Sentinel Hub's documented S1 GRD processing API specifies `input.data[].dataFilter.timeRange`; allowed backscatter coefficients are `BETA0`, `SIGMA0_ELLIPSOID`, `GAMMA0_ELLIPSOID` (default), and `GAMMA0_TERRAIN` (requires orthorectification). Sentinel-1 VV/VH are linear powers in the selected backscatter coefficient, not decibel rasters. The API's S1 processing documentation indicates border noise handling, orbit product provenance and optional speckle/radiometric terrain correction; these are NOT proven merely by product binding.

- https://docs.sentinel-hub.com/api/latest/data/sentinel-1-grd/
- https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/ApiReference.html
- https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process/Examples/S1GRD.html

The existing live S1 fetcher had two acquisition-contract gaps: `timeRange` was outside `dataFilter`, and the selected coefficient was only an undocumented implicit default. That S1 fetcher also allowed one missing polarization or mask, and marked exact-product-binding metadata usable in various applications before independent SAR science qualification. The changes here deliberately preserve those legacy flags for compatibility but **do not treat them as scientific authority**.

## Changes

### A. Native S1 source and orbit screen

**Module:** `services/agribrain/layer0/native_issuer/sentinel1_qualifier.py` — entirely read-only.

- Require independently retained and re-verified native S1 Catalog and Process acquisitions, exact provider/endpoint/sensor/request SHA/response SHA/product identity and original requests from `NativeEvidenceStore.verified_request_body()`.
- Require exactly one selected `sentinel-1-grd` Catalog product; match selected timestamp against scene UTC; reject source responses predating acquisition.
- Verify full original Process `userdata.json`, per-tile product ID equality and stored original exact binding proof; reject mixed S1 product responses.
- Require declared dual-polarization VV+VH GRD; reject contradictory polarizations/products, defer when original provider polarization properties are missing.
- Match Catalog relative-orbit and direction to every returned Process tile and cached scene. Compare absolute orbit when independently present. Contradictions **REJECT**; missing orbit provenance **DEFER**; never infer independently observed multi-temporal crop changes from same orbit label alone.
- Verify original Catalog and Process request region, requested time coverage, output affine/pixel shape, EPSG:4326, required response identifiers, selected product Evalscript and any requested orbit, polarization or acquisition-mode filters. Do not reconstruct unsigned Process JSON from scene metadata.
- Replay the exact bounded Process TAR VV, VH and dataMask TIFFs; enforce member/shape/decoded-size caps, no extraction, correct mask binary semantics and measured positive finite linear-power pixels. Recompute native content hash and compare actual stored NPZ bands/masks to captured TIFF arrays.
- Enforce an existing provisional **>=70%** valid sampled pixel-center QA floor; no silent mask truncation, and defer large/complex geometry to MESIA. Plot identity is supplied through a typed backend context but requires a separate authenticated registry in B2B-05.
- Enforce documented explicit backscatter calibration choices and `GAMMA0_TERRAIN` orthorectification; missing coefficient is **DEFERRED_NATIVE_AUTHORITY**, not an assumed scientific mode.
- Emit deterministic domain-separated unsigned diagnostic proof root only for `SCREENED_NATIVE_SAR_STRUCTURE`, never an issued grant. Always `eligible_for_state_grant=False`, `scientific_publication_authorized=False`, `independent_multitemporal_eligibility=False`, `incidence_angle_proven=False`, `border_noise_removed_proven=False`, `speckle_calibrated=False` and `observation_sigma_calibrated=False`.

### B. Exact live producer request

**Module:** `services/agribrain/layer0/asmae_scene_products/s1_real_scene_product_fetcher.py`.

- Introduce pure `_build_native_s1_process_request()` building the exact live production POST.
- Place `timeRange` correctly in `input.data[0].dataFilter`; retain `mosaickingOrder="mostRecent"`.
- Explicitly set `input.data[0].processing.backCoeff="GAMMA0_ELLIPSOID"`, preserving Sentinel Hub's documented default rather than silently altering coefficients to sigma0.
- Retain existing response parser, cache metadata and admission behavior for a bounded first implementation; this is **not** real-world provider proof or authorization. Historical old request-sidecar evidence cannot be retroactively normalized to the new format; its B2B-03 screen returns a failure/deferred outcome as appropriate.

### C. Regression tests

**File:** `services/agribrain/layer0/tests/test_sentinel1_native_qualifier.py`.

Positive fixture: exact raw Catalog→Process product, identical relative/absolute orbit, dual-pol source TIFFs and mask, native Process request, correct grid and captured calibration. Assert unsigned diagnostic output and no state grant.

Adversarial/negative fixture categories: missing/mixed product; duplicate Catalog ID; incomplete dual-pol or missing mask; malformed mask; zero/negative/nonfinite VV/VH; mismatched stored pixel or mask; wrong relative/direction/absolute orbit; absent orbit proof; bogus polarization/processing request; time-window/CRS/grid mismatch; missing/corrupt original request/response; wrong or missing gamma calibration; malicious production_usable metadata; foreign/unsupported footprint; missing polygon; invalid QA threshold. Bound concurrent original request validation by the existing B2B-02B tests.

## Required exact-head acceptance

```powershell
git fetch origin
git switch fix/layer0-s1-native-qualification-20261103
git pull --ff-only
git rev-parse HEAD

py -m pytest -q services/agribrain/layer0/tests/test_sentinel1_native_qualifier.py
py -m pytest -q services/agribrain/layer0/tests/test_native_request_replay.py
py -m pytest -q services/agribrain/layer0/tests/test_native_scene_cache_lineage.py
py -m pytest -q services/agribrain/layer0/tests/

py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

The new production Process builder must also be validated using real Sentinel Hub S1 Catalog/Process endpoints and authentic product/TIFF/provenance with approved credentials before external science qualification. Mocked request objects and fabricated SAR TIFFs do not qualify live providers, or validate independent orbital time series.

## Open SAR production/scientific gates

1. **Source-specific radiometry:** confirm instrument mode, orbit production metadata, actual provider backscatter coefficient and units on real API responses; compare incidence angle/terrain-orthorectification, radar layover/shadow and border noise against original source.
2. **Speckle and independence:** statistical speckle/texture model, spatial correlation and correlated repeated passes; physically meaningful uncertainty inflation, no false independent evidence from overlapping samples.
3. **True plot/zone authority:** tenant IAM, immutable geometry version, MESIA raster-footprint area containment, source-bound polygon and pixel support. Pixel-center sampling is only a bounded diagnostic.
4. **Positive signed scientific grants:** B2B-06 v3 asymmetric issuer, issuer decision ledger, source-specific permitted observation variables and empirically validated uncertainty. No signed grant from this diagnostic code.
5. **Downstream legacy flags:** existing S1 `production_usable=True` and `usable_for_advisory=True` remain potentially unsafe as direct authority shortcuts. Reconcile consumers separately with verified qualified-source contracts.
6. **Other Layer 0 modules:** B2B-04 weather, B2B-05 spatial, B2B-06 issuer and L0-02C3/C4 infiltration/process-noise calibration remain open. Scientific Pilot PR #9 has its own publication gate and is untouched.

## Disposition

**B2B-03A source-level structural SAR candidate implemented; not qualified on new head.** B2B-03 complete scientific native Sentinel-1 qualification OPEN. No merge to pilot or main; no change to the monograph or frozen 469-finding audit.

# Layer 0 — B2B S1/S2 Shared Request, Operator & Complete Product Proof Repair

**Date:** 2026-11-03  
**Parent (qualified):** PR #22 at `582aba89a774e428e9f7e9a241505b6f632c973b`  
**Branch:** `fix/layer0-native-operator-product-proof-20261103`  
**Scope:** The three demonstrated P2 native-screen defects only.  
**Status:** Implementation candidate; **no new-head pytest, live provider, physical or deployment qualifications** are claimed.  
**Immutable governance:** Do not modify the master architecture monograph, historical 469-finding Layer 0 audit or independent Scientific Pilot PR #9. Do not re-open previously closed observation order/deduplication, S1/S2 cold acquisition-reference or geometry-version software findings.

## 0. Pin and non-overlapping qualification

The repository owner reported at exact parent SHA `582aba8`:
- Layer 0 **373/373**
- Layer 1 Fusion **21/21**
- ASMAE **84/84**, including full real-raster pipeline **1/1** (681.97 s, `task-960`).
- Aggregate **478/478**, 0 failures (reported 738.41 s).

This is the **parent** software receipt, not a result for this batch. PR remains draft pending tests on its exact new head.

## 1. P2 — S2 Process request / screen disagree with documented API

**Original evidence:** S2 producer constructed `input.data[0].timeRange` as a sibling of `dataFilter`; `_verify_process_request()` accepted the same incorrect nesting and rejected documented `input.data[0].dataFilter.timeRange` requests.

**Correction:**
- Introduce `_build_native_s2_process_request()`, mirroring the S1 bounded producer pattern, with correct nested `dataFilter: {mosaickingOrder: "leastCC", timeRange: {from, to}}`.
- Route real S2 POST construction through the builder so the live producer and verifier follow the same documented source request contract.
- Reject the legacy sibling-level `timeRange` in the independent S2 screen. The requested time window remains bound to selected Catalog acquisition, original replayed POST, bbox, EPSG:4326 and scene grid.

Provider API: https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process/Examples/S2L2A.html

**Backward compatibility:** An old Process response with a retained but invalid original POST is **REJECTED** by the new screen, not silently rewritten or reissued under a modern request hash. Legacy caching may remain visible as diagnostic/unqualified; no automatic provider provenance promotion.

## 2. P2 — processing-script semantics previously not verified

**Original evidence:** S1/S2 screens accepted a request Evalscript merely containing the expected selected product ID. An original request which hardcoded optical bands or `dataMask=1` could pass if returned TIFF pixels and metadata looked plausible.

**Correction:**
- `native_issuer/process_operator_contract.py` contains the complete reviewed S1 and S2 **Evalscript v3** templates. Both actual producers call `render_native_process_operator(sensor, product_id)`; neither maintains a separate editable copy.
- The independent screens call `verify_native_process_operator(sensor, product_id, actual_original_post_evalscript)`. This requires byte-for-byte equality with the complete reviewed script, not a product-id substring or a handful of safe keywords. Exact approved operator SHA-256 and policy domain `akaloris/layer0/native-s1-s2-process-operator/v2` are included in positive diagnostic proof lineage.
- Altering sampled VV/VH, B04/B08, SCL or dataMask, removing the pre-filter or appending code causes fail-closed request/operator mismatch. This does not imply that an untrusted HTTP response cryptographically attests that the provider executed the script.
- The approved operators preserve `setup()`, TILE mosaicking, `preProcessScenes()`, `updateOutputMetadata()`, and `evaluatePixel()`. They include an **unidentified-tile counter set from the original unfiltered scene list**, initialized to `-1` to detect a prefilter that did not execute. The resulting userdata includes selected product ID and the counter.

**Limits:** This is an internally pinned software allowlist. Provider runtime semantics, any actual browser/user-modifiable code paths, external operator attestation, production deployment hashes and real scientific calibration still require validation. A compromised source server could return fabricated TIFFs and userdata without independent cryptographic authenticity; not solved by string equality.

## 3. P2 — one named and one unnamed Process tile accepted

**Original evidence:** The v1 exact binding utility collapsed all nonempty tile IDs to a set and ignored unnamed/malformed extra tiles. A Process archive with one exact Catalog product plus another unidentified tile could remain `exact_catalog_item`.

**Correction:**
- `verify_exact_product_binding()` now evaluates every returned tile, rejects malformed records, missing **product-typed** `sentinel1ProductId`, `sentinel2ProductId` or `productId` fields, and contradictory typed product IDs in the same tile. Generic `id` and `tileId` fields do not establish product identity.
- Require **every** tile identified, identical to selected normalized Catalog product, with selected `expectedProductId` and **integer `unidentifiedTileCount == 0`** emitted by the pinned operator's prefilter. A missing counter cannot prove that preProcessScenes did not quietly remove unknown input tiles.
- Change the persisted binding schema to `exact_catalog_process_v2`, recording returned/identified/unidentified/conflicting counts, explicit counter and selected product. `exact_binding_proof_valid()` rejects v1 or conflicting/forged counters rather than silently upgrading legacy `production_usable` metadata.
- Both independent S1/S2 native screens demand explicit original operator metadata and recompute the v2 binding from captured `userdata.json` before any structural screen pass. No valid-looking returned TIFFs or self-declared `scene.production_usable` flags bypass source proof.

**Legacy impact:** Old v1 exact-binding proofs no longer pass the new v2 positive check. They remain historical artifacts that must be re-fetched/re-qualified with genuine provider data, not silently rewritten or granted authority.

## 4. Regression acceptance and anti-counterexamples

The focused new `test_native_operator_product_proof.py` and additions to S1/S2 source screen suites check:
1. Actual S2 POST builder equals documented nested S2 time range, and legacy sibling-level timeRange is rejected by replay verification.
2. Actual S1/S2 Process producers obtain operators from the single shared pinned contract.
3. Full exact script passes; constant B04/VV, `dataMask=1`, removal of preProcessScenes, extra script code and changed selected product do **not** pass.
4. One known tile plus unknown `tileId`, generic `id`, malformed or `None` tile is not a valid exact product proof.
5. Two typed IDs conflicting inside a single tile reject.
6. Operator did not run (`-1`), missing count, missing expected product ID, positive/negative/noninteger count reject.
7. Fully identified matching product-typed tiles with zero unknown count remain positive in the bounded product proof, with v2 counts checked.
8. Historical v1 cached proof and tampered v2 proof counters cannot regain positive cached product binding.
9. All S1/S2 positive screen results continue returning `eligible_for_state_grant=False` and `scientific_publication_authorized=False`.
10. Existing Layer 0, Layer 1 Fusion and full ASMAE regression suites must pass at **the new exact SHA**. Do not inherit `478/478` from the parent.

Run:

```powershell
git fetch origin
git switch fix/layer0-native-operator-product-proof-20261103
git pull --ff-only
git rev-parse HEAD

py -m pytest -q services/agribrain/layer0/tests/test_native_operator_product_proof.py
py -m pytest -q services/agribrain/layer0/tests/test_sentinel2_native_qualifier.py
py -m pytest -q services/agribrain/layer0/tests/test_sentinel1_native_qualifier.py
py -m pytest -q services/agribrain/layer0/tests/test_native_scene_cache_lineage.py
py -m pytest -q services/agribrain/layer0/tests/

py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

## 5. Open scope and parallel workstreams

- **Not yet closed:** live Sentinel Hub request/response and Evalscript runtime validation; physical source/raster georeference; actual provider authenticity; externally protected WORM/origin proof; measured scientific uncertainty; complete MSI radiometry or SAR terrain, speckle and border calibration.
- **Legacy consumers:** old source flags `production_usable` and `usable_for_advisory` are not admission or pilot authority; consumer-side inventory/fencing remains a separately reviewed task. A diagnostic positive screen remains unsigned, non-authorizing.
- **Parallel unchanged:** B2B-04 weather provenance, B2B-05 authenticated tenant/plot/MESIA area-exact containment, B2B-06 v3 KMS issuer, independent pilot PR #9, and L0-02C3/C4 infiltration/process Q.
- **No broad re-audit:** prior numerical and cold-cache closures remain software-qualified at their pinned revisions, subject only to routine regression after these shared source-code edits.

## 6. Disposition

**Three P2 request/operator/product-proof defects: implemented as a bounded repair candidate. Exact-head full qualification PENDING.** No new P1 or state/publication grant bypass is claimed. PR must remain draft and isolated until fresh full suites and real provider compatibility assessments justify promotion.

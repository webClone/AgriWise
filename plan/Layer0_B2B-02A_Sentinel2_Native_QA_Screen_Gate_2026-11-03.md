# Layer 0 B2B-02A — Sentinel-2 Native Acquisition QA Screen
**Date:** 2026-11-03  
**Parent SHA:** `8e203f998e3829825095390b53791e7a1bb630a7` (PR #19)  
**Branch:** `fix/layer0-s2-native-qualification-20261103`  
**Status:** SOURCE-LEVEL CANDIDATE; NEW-HEAD TESTS AND REAL PROVIDER GATES PENDING  
**No changes to:** Scientific Pilot PR #9, `main`, R3 governing monograph, PR #17 plan, frozen 469-finding audit.

## Parent baseline

User-provided exact-SHA Windows execution at `8e203f9`:
- Layer 0 **249/249**; Layer 1 Fusion **21/21**; ASMAE **84/84** including comprehensive raster EnKF.
- Aggregate **354/354**, 0 failures. This qualifies **only the parent**; do not inherit passes or infer provider/KMS/physical validation for this branch.

Existing closed software findings: L0-LINEAGE-01, R18-RUNTIME-01, L0-SCOPE-TYPE-01, Jacobian discontinuity, zero-quality state influence (within their respective tested scopes).

## Intent and scientific trust boundary

B2B-02A adds a read-only independent **native QA screen**, `native_issuer/sentinel2_qualifier.py`, over independently captured Sentinel Hub **Catalog response** and **Process TAR response** already retained by B2B-01. It verifies pixel/identity/structural conditions and can produce a reproducible **diagnostic QA proof hash**.

It is **not** an issuer, and no `ObservationPacket` or signature is minted. A `SCREENED_NATIVE_QA` result sets `eligible_for_state_grant=False` and `scientific_publication_authorized=False`. Legacy S2 `production_usable=True` metadata remains independent and **must not** substitute for this receipt or authorize pilot publication. The science screen does not mutate a `SceneProduct`, state/covariance, or its legacy flags.

An S2-native screen is not independent provider PKI attestation; the B2B-01 local CAS is not WORM storage; a `TrustedPlotContext` constructed by an application is not proof of an authenticated tenant/geometry registry. A nonzero pixel-center support fraction is NOT area-exact MESIA containment or a verified exposure footprint. No scientifically calibrated observation sigma, crop model, or measured soil moisture is inferred.

## Implemented checks

1. **Captured origin:** both exact native acquisition IDs required. Replay and hash-verify Catalog and Process CAS records and raw response bytes. Deny wrong S1/S2 sensor, provider, endpoint, product ID, missing CAS, altered response or self-declared scene/test override.
2. **Catalog scene identity:** selected product must appear exactly once among captured response features, collection must be Sentinel-2 L2A, UTC acquisition timestamp must match the scene, and captured retrieval must not precede source acquisition.
3. **Process product binding:** extract raw `userdata.json`, independently recompute `verify_exact_product_binding()`, require the **original** persisted binding proof to match the captured response and prove that no returned tile has a different product. A local `exact_match=True` alone is not accepted.
4. **Original TIFF evidence:** bounded TAR decoding without path extraction; cap member count/member sizes/TIFF dimensions/userdata. Require B04, B08, SCL and dataMask. Compare original byte-layout raster content hash with scene hash and compare each numeric cached raster to the raw Process TIFF array. Reject missing, mismatched, corrupt or doctored cached measurements.
5. **Optical QA:** enforce finite 0–1 reflectance on valid pixels; SCL classes 0,1,2,3,6,7,8,9,10,11 excluded; dataMask strictly binary; undefined denominator (red+NIR near zero) is not synthetic NDVI 0. Preserve genuine NDVI zero when both valid red/NIR are nonzero and equal. Use the existing >=0.70 good-pixel benchmark only as a **bounded non-calibrated QA floor**, which callers cannot lower. Derived output **NDVI only**, not NDMI/NDRE or calibrated sigma.
6. **Request ↔ grid/time:** B2B-01 retained the request SHA-256 but not full Process request JSON. A caller-provided `captured_process_request` must reproduce that stored canonical request SHA-256, exact selected source, time window, bounding box, WGS84 CRS, output width/height/required band response identifiers and scene affine. **No request mapping = DEFERRED**, not screen pass. This is suitable for in-process fresh acquisitions; cold-cache replay requires future immutable request-body storage.
7. **Trusted polygon input:** an application-level `TrustedPlotContext` with pinned plot/version/hash and WGS84 ring is required to *attempt* pixel-center screening. It must originate from a future separately authorized backend geometry resolver, NOT user packets. Reject unsupported/foreign extent or no interior centers; large/complex scenes defer to a robust MESIA spatial operator, never truncate silently. A successful screen remains non-authorizing.
8. **Proof lineage:** hash exact Catalog+Process acquisition identities, product ID, raw response binding, bounded raster metrics, geometry ID/version and science-screen policy as a deterministic, domain-separated diagnostic proof. This is an **unsigned** hash, not a pilot or issuer signature.

## Test targets on the new head

```powershell
git fetch origin
git switch fix/layer0-s2-native-qualification-20261103
git pull --ff-only
git rev-parse HEAD
py -m pytest -q services/agribrain/layer0/tests/test_sentinel2_native_qualifier.py
py -m pytest -q services/agribrain/layer0/tests/test_native_acquisition_evidence.py
py -m pytest -q services/agribrain/layer0/tests/test_native_scene_cache_lineage.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

Focused counterexamples (synthetic source fixtures **only**, no network/provider proof): exact product and raw pixel replay; missing/duplicate Catalog selected products; wrong collection or Process tile product; altered binding proof; corrupted CAS or changed cached optical pixel; missing B04/B08/SCL/dataMask; all cloud/shadow/snow or masked zero; true bare-soil zero NDVI vs undefined 0/0; negative/out-of-range/nonfinite reflectance; wrong/missing captured Process request; fabricated scene grid or foreign polygon extent; test override/metadata flag self-promotion; unjustified lowering of the QA threshold; scope/complexity deferral; deterministic proof and explicit non-publication.

**No new-head pytest was run by this authoring session.** Previously reported 354/354 qualifies the source **parent SHA only**. CI/Windows qualification and optional live provider validation are required before software acceptance.

## Explicitly remaining B2B-02B/B2B-05/06 gates

- **Production acquisition request retention:** B2B-01 recorded request SHA but not raw canonical request bytes. Implement protected, immutable request-body retrieval with explicit object version and replay lineage. Cold cache must then use **original** authenticated request, not reconstruct a plausible client string.
- **Real provider acceptance:** run authenticated Sentinel Hub Catalog→Process responses with traceable quotas/credentials, exact item ID, date, signed or independently validated origin, source TIFF georeferencing and real raster QA; test negatives including mixed mosaics. Synthetic TAR fixtures do not qualify a true Sentinel scene.
- **Trusted parcel authority:** real server IAM plot/tenant rights, immutable polygon hash/version, same-CRS grid support and an area-correct MESIA containment proof; current ring object and pixel-center sampling cannot close L0-002.
- **Persisted QA decision and variable noise:** independently enforce allowed NDVI variable and measured-support sigma with an append-only policy revision. Existing `scene.production_usable` from exact binding is an **open legacy bypass risk for consumers that trust scene flags**; inventory and fence it in a separate reviewed integration before allowing S2 data to influence production advice.
- **Privileged v3 issuer:** isolated private-key service, qualification decision ID/ledger, purpose-specific signed packet digest and current independently authenticated revocation authority. No client-generated `production_usable` or `state_update_allowed` claim may mint a grant.
- **Cross-layer and pilot:** only a future separate pinned integration can bind source qualification to Layer 0/Kalman → Layer 1/ASMAE → Pilot PR #9 publication authorization, with `STATE_ESTIMATE` status retained.
- **Other modules:** Sentinel-1 B2B-03, weather B2B-04, L0-02C3/C4 trusted infiltration and calibrated Q remain open.

## Disposition

**B2B-02A: IMPLEMENTED AS A READ-ONLY QA SCREEN; UNQUALIFIED AT THIS NEW HEAD.**  
**B2B-02 full native provider qualification: PARTIAL, OPEN.**  
**L0-004 positive source authority: PARTIAL, OPEN.**  
**Pilot publication authorization: INDEPENDENT, UNCHANGED.**

No merge to `main` or the Scientific Pilot; no update to the master monograph or historical audit.

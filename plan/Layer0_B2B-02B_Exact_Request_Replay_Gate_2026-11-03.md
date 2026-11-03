# Layer 0 — B2B-02B: Original Native HTTP Request Retention & Cold Replay

**Date:** 2026-11-03  
**Base:** PR #20 at `a02373bd9dd6fe1940df2543286ab6c09525f19d`  
**Branch:** `fix/layer0-native-request-replay-20261103`  
**Scope:** Native acquisition store and read-only Sentinel-2 QA screen, original POST request persistence, adversarial tests.  
**Status:** Implemented candidate; new-head exact-SHA local pytest and real provider qualification **NOT YET RUN**.  
**Track isolation:** Scientific Pilot PR #9, `main`, master R3 monograph, PR #17 implementation blueprint and frozen Layer 0 audit unchanged.

## Parent qualification reconciliation

The repository owner reported Windows Python 3.13.13 results at `a02373b`:
- Sentinel-2 native qualifier **41/41**, included in Layer 0 **290/290**.
- Layer 1 Fusion **21/21**.
- Fast ASMAE **83/83**.
- **394/394 distinct fast executed suites**, zero reported failures.
- The **one comprehensive ASMAE raster/EnKF test** (task-723) was still RUNNING in that receipt. The complete ASMAE catalog and **395/395 total** must not be asserted until that terminal result is reported on the same SHA.
- No real Sentinel Hub acquisition and no independent production issuer qualification claimed.

The previous PR #19 **354/354** full catalog receipt belongs to `8e203f9`, not the B2B-02B branch.

## Provenance problem

B2B-01 already captured both responses and recorded the canonical SHA-256 of the HTTP PreparedRequest JSON, but **discarded the actual transmitted request body**. B2B-02A accepted a caller-provided `captured_process_request` mapping to reconstruct the hash, which creates an avoidable provenance dependency for cold replay. A real immutable request record must precede any science screening from cached S2 scenes.

## Change 1 — Exact wire-body retention, backward-compatible acquisition IDs

`services/agribrain/layer0/native_issuer/acquisition_evidence.py` now persists:
1. **Original prepared HTTP POST bytes** at `request_wire/<sha256_of_exact_wire_bytes>`, with the existing 1 MiB request bound. Only request **body**, never Authorization headers or backend OAuth token, is stored.
2. An append-only companion at `request_replays/<acquisition_id>`: domain `akaloris/layer0/native-request-replay/v1`, original acquisition ID, existing **canonical request SHA-256**, original **wire byte SHA-256**, and byte length. These companion objects are written **before** the response object and acquisition manifest become visible.
3. Existing v1 `NativeAcquisitionReceipt` wire schema, domain, `acquisition_id`, `request_sha256`, response SHA and existing response-manifest identity are **unchanged**. Older captures retain their identities but have no invented request-body evidence.
4. `verified_request_body(acquisition_id)`: first validates the native response acquisition manifest and raw response, then verifies the companion ID/hash/shape and original wire object against its size and both cryptographic digests, parses JSON with duplicate-key rejection and canonicalizes it through the existing credential-safe request validator. Returns only the validated backend request mapping.
5. A historical capture with **no replay sidecar** reports `captured_request_not_retained`, not an implicitly authorized reconstruction; corrupt sidecar, missing wire, symlink, mismatched canonical digest or duplicate keys fail closed.
6. Repeated content-identical captures are idempotent. Captures with the same **canonical semantics but different exact prepared bytes** cannot silently replace an already immutably recorded wire body for the same acquisition ID: the companion conflict is explicit.
7. Raw request metadata and embedded string values with standard bearer/basic/API-key/secret markers are rejected at capture, reducing the chance of persisting credentials that might be embedded in a provider evalscript. This detection is a **bounded safeguard**, not complete data-loss prevention; production request-schema validation and secured storage are still mandatory.

**Limits:** This is a locally append-only content-addressed store, not a true externally signed provider statement, KMS signature, distributed WORM or attacker-proof audit. The companion is keyed by the original acquisition ID and its canonical SHA-256; the exact wire byte hash is protected by append-only local storage, but the original v1 manifest does **not** cryptographically root the new companion wire hash. The scientific meaning is bound by the canonical request SHA. A compromised filesystem operator can still rewrite artifacts unless protected immutable object storage is deployed.

## Change 2 — Remove caller-supplied request from native QA

`native_issuer/sentinel2_qualifier.py` no longer accepts a `captured_process_request` argument. Instead, after replay-validating Catalog and Process captures, the screen calls `evidence_store.verified_request_body(process.acquisition_id)`. It reuses the existing bounded source/collection, timestamp, bbox, affine, Evalscript product and required-response checks, but now the parameters are anchored to the original POST object rather than a caller-supplied reconstruction.

- **Old source record without retained request:** `DEFERRED_SPATIAL_AUTHORITY`, reason `historical_native_capture_missing_original_request`. This is an explicit transitional status, not a successful QA screen.
- **Present but corrupted source request:** `REJECTED`, reason `invalid_captured_process_request_evidence`.
- **Valid original request inconsistent with item/scene/grid:** `REJECTED`, reason `captured_process_request_grid_or_time_mismatch`.
- **Valid original request and prior QA checks:** may return `SCREENED_NATIVE_QA`, still with `eligible_for_state_grant=False` and `scientific_publication_authorized=False`.

The verified request is obtained from protected backend acquisition storage; a client must never control the evidence root or its files.

## Exact-head acceptance commands

```powershell
git fetch origin
git switch fix/layer0-native-request-replay-20261103
git pull --ff-only
git rev-parse HEAD

py -m pytest -q services/agribrain/layer0/tests/test_native_request_replay.py
py -m pytest -q services/agribrain/layer0/tests/test_sentinel2_native_qualifier.py
py -m pytest -q services/agribrain/layer0/tests/test_native_acquisition_evidence.py
py -m pytest -q services/agribrain/layer0/tests/test_native_scene_cache_lineage.py

py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

**Positive tests:** Original raw wire body roundtrip, canonical request hash, cold reopening, exact stable response and request IDs, deterministic subsequent S2 QA without supplying a POST payload, a missing source request no longer being silently invented, no state-grant/publication authority.

**Negative tests:** Tampered original request bytes or sidecar digest, duplicate JSON keys, foreign companion, missing wire object, oversized request, embedded secret-bearing request strings, body/claim mismatches, changed byte representation of same canonical identity, denied acquisition on failed disk write, old captures without sidecar deferred, fake S2 geometry/time rejected, full inherited Layer 0/Layer 1/ASMAE regressions.

## Still open after B2B-02B

1. **Live Sentinel Hub** authenticated Catalog and Process network qualification and quota/credential integration; current tests use simulated responses only.
2. Production immutable distributed storage and anti-rollback publication roots. Also require request/response body retention/license review.
3. Trusted **tenant and plot geometry registry**, source raster GeoTIFF georeferencing and MESIA area-exact support; B2B-02A currently has pixel-center diagnostics only.
4. Independent QA-derived/empirically calibrated observation sigma; signed purpose/variable/geometry-limited v3 issuance from an isolated KMS/HSM and trusted revocation.
5. Legacy S2 `production_usable=True` behavior is still a **separate consumer-side authority risk**; no existing consumer or production admission pathway is modified by this batch.
6. S1 B2B-03, weather B2B-04, L0-02C3/4 trusted infiltration and process-Q calibration, and the scientific Pilot publication authorization remain independent.

**Disposition:** B2B-02B implemented as a **source-level candidate**. Await exact-head Windows tests. Do not call full B2B-02/L0-004 source authority closed or merge into the pilot.

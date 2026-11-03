# Layer 0 Cohort A — Consumed Input Identity + S1/S2 Cache Lineage Completion

**Date:** 2026-11-03  
**Parent:** PR #18 at `31ae92fbb2fc613075e567554b331f9db5d48449`  
**Track:** Layer 0 only, stacked on PR #18. Scientific Pilot PR #9 remains independently pinned.  
**Review source:** User-supplied 2026-11-03 integrated deep check (P1 L0-LINEAGE-01, P2 R18-RUNTIME-01, adjacent type hardening).  
**Status:** Implemented as a bounded software candidate; exact-head full pytest, real providers, and pilot tests have **NOT been executed** by this authoring session. Never inherit the 302/302 PR #16 receipt or the 30 native acquisition probes as a new-head qualification.  
**Governing R3 monograph and historical 469-finding audit:** unchanged.

## 1. P1: consumed Kalman observation identity (L0-LINEAGE-01)

**Demonstrated original defect:** Signed duplicate packet was assimilated twice, increasing LAI from ~1.8721 to ~2.0774 while the input hash remained the same. Two distinct valid packets assimilated in opposite orders changed the nonlinear posterior despite identical input roots. Raw observations were a multiset while signed receipts were a sorted set.

**Correction implemented in `state_engine.py`:**
- Stage each **numerically admissible** packet-field update only once under `(full_signed_packet_digest, day, accepted_zone, packet_field)`, before passing any observations to the Kalman filter. An exact transport retry does not count as an independent measurement.
- Distinct packets with different complete digests remain independent, even if the legacy auto-derived `packet_id` collides for the same source/timestamp/bbox. A source ID/timestamp alone is insufficient for deduplication.
- An explicitly provided, signed `qualification_decision_id` must not be reused for different content for the same source/variable: conflicting entries fail closed rather than silently selecting one. This condition is **conditional** on having a real immutable qualified ID; native trusted issuer issuance remains B2B-06 and is not manufactured here.
- Sort the accepted numerical updates by `(day, zone, acquisition_timestamp_in_UTC, source, full_packet_digest, packet_field)`. This is a policy decision: the resulting nonlinear Kalman order is deterministic regardless of transport order. Qualifying distinct observations are still separate updates.
- Build `observations_by_day` from that exact staged order; add `ordered_observation_updates` containing the exact submitted source digest, target variable/model type, value, sigma, effective reliability, UTC time, day and zone to the verified input manifest.
- Version the input-manifest domain from `akaloris/layer0/verified-state-input-manifest/v1` to `.../v2`, with policy `canonical-utc-source-digest-field/v1`. Do **not** reuse a cached v1 identity as equivalent to v2.
- Keep rejected/diagnostic/zero-QA evidence outside the consumed observation plan. Maintain the previously qualified signed weather contributor manifest and pre/post-computation revocation fences.

**Important hash distinction:** `input_hash` now identifies this canonical science input plan. `Layer0StatePackage.output_hash` also includes the raw transport packet list and exclusion diagnostics, so it may differ between a single packet and duplicate delivery even if the actual numerical state and **input_hash** are identical. The output hash is not an assertion that these two raw audit trails were identical, nor is it a signed pilot publication receipt.

**Limits:** The plan records exact scalar updates submitted to the Kalman engine; some model-level innovation gates can still decline an update after submission. Complete downstream scientific identity also requires process parameter/operator versions and replay-state identity, outside this bounded P1 counterexample. A malicious issuer minting different signed packet identities for the same physical source must be prevented by B2B provider qualification/issuer decisions.

## 2. P2: fresh-to-cold S1/S2 acquisition references (R18-RUNTIME-01)

**Demonstrated original defect:** Fresh S1 and S2 paths persisted Catalog/Process acquisition IDs but the cold `SceneProduct` constructors omitted those fields, returning `None/None/UNATTESTED` even when the acquisition store was available.

**Correction implemented:**
- Introduce `restore_cached_native_references(metadata, sensor)` in `native_issuer/acquisition_evidence.py`.
- Only consider an exact pair of 64-character Catalog and Process acquisition IDs. If absent, return `None/None/UNATTESTED` (true legacy cache).
- With backend-provisioned `AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT`, call `verified_cache_receipt()` on both source records, re-reading and SHA-256-verifying each original CAS object/manifest.
- Check expected sensor, trusted Sentinel Hub provider, exact Catalog/Process endpoints, Process product identity, original Process response digest and request digest against the cached scene metadata, and a non-authorizing captured/cache status.
- Cold constructors of `s1_real_scene_product_fetcher.py` and `s2_real_scene_product_fetcher.py` now populate both native IDs plus `native_evidence_status=PROVENANCE_VERIFIED_CACHE` **only after** these checks. This status continues to be non-authorizing (`NOT_QUALIFIED`); cache is never promoted to a new live provider response.
- Corrupt, incomplete, missing or mismatched claimed native evidence fails closed with explicit `invalid_native_cache_evidence` rather than silently falling back to cache. Repeated cold serialization may show `PROVENANCE_VERIFIED_CACHE` and is revalidated on every return.
- Preserve legacy scenes without acquisition IDs as `UNATTESTED` and without invented serialized evidence fields.

**Capture policy decision:** `AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE=true` means all **new backend HTTP acquisitions** require capture. It does not retroactively require all old cached scenes to have provenance receipts. Legacy cache is visible as `UNATTESTED`. A claimed captured scene whose evidence root cannot be verified is never marked `PROVENANCE_VERIFIED_CACHE`; under required-capture mode, a missing evidence root hard-fails. A future all-cache-return admission policy would be a separate, explicit setting, not a hidden reinterpretation.

**Limits:** This verifies the local captured response trace, not independent provider authenticity, plot ownership, raster masks, physical spatial footprint, provider signature, trusted issuer, durable multiworker WORM or the scientific Pilot gate.

## 3. Adjacent strict geometry version typing (L0-SCOPE-TYPE-01)

- The canonical packet-scope check rejects a packet version unless it is exactly `int` when the caller specifies a geometry version.
- `PositiveObservationAdmissionVerifier.verify()` now also requires **both** the signed grant's version and the packet's version to be exact nonnegative builtin `int`, before numerical equality.
- A *validly signed* `True`, `False`, `1.0` or `"1"` cannot become version `1`. Existing valid signed integer versions remain accepted. This is contract hardening, not evidence of a prior unsigned bypass.

## 4. Required exact-SHA acceptance

Run on the eventual new candidate SHA in a clean development environment:

```powershell
git fetch origin
git switch fix/layer0-consumed-lineage-cache-continuity-20261103
git pull --ff-only
git rev-parse HEAD

py -m pytest -q services/agribrain/layer0/tests/test_consumed_observation_lineage.py
py -m pytest -q services/agribrain/layer0/tests/test_native_scene_cache_lineage.py
py -m pytest -q services/agribrain/layer0/tests/test_native_acquisition_evidence.py
py -m pytest -q services/agribrain/layer0/tests/test_positive_observation_admission.py
py -m pytest -q services/agribrain/layer0/tests/test_signed_state_input_manifest.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

### Exact scientific exit checks
1. One valid signed NDVI packet vs the same exact packet twice: identical full 9-state numerical trajectory, full covariance and v2 scientific input manifest/root; duplicate count visible but no double-assimilation.
2. Two distinct valid signed NDVI packets in opposite transport order: identical deterministic Kalman execution, state, covariance and input root; both remain independent. Ordering is by normalized UTC not local offset strings.
3. Same immutable `qualification_decision_id` assigned different content for the same source/variable: hard conflict, no state package.
4. Correct signed zero-QA remains excluded; genuine physical zero remains usable. Existing foreign geometry/zone negatives, Joseph covariance and photo-shutdown controls remain unchanged.
5. Fresh Catalog+Process capture → persisted scene → cold S1/S2 reconstruction returns original validated IDs with `PROVENANCE_VERIFIED_CACHE` and no state-input grant.
6. Corrupt/missing CAS object, missing manifest, wrong source/product or partial IDs: explicit negative. Legacy metadata stays `UNATTESTED`. Re-cold serialization verifies, not merely copies, IDs.
7. Signed bool/float/string geometry versions reject; exact positive integer remains admitted.
8. Layer 0, Layer 1, full 84 ASMAE tests rerun at exact new head. Real Sentinel Hub, pilot browser/DB, deployment WORM and physical trials **not** claimed by these fixtures.

## 5. Release decision

**Cohort A: IMPLEMENTED / UNQUALIFIED.** Keep stacked PR in draft and hold promotion until the bounded tests pass. Do not rerun the 469-finding audit. Do not reopen the independently closed numerical Jacobian or zero-QA software repairs absent a new reproduced regression.

**Continue Cohort B in parallel:** First real Sentinel-2 source→product/mask QA→trusted plot support→issuer→native state vertical slice. Provider credential provenance, KMS v3 signing, distributed signed revocation, MESIA geometric support, L0-02C3/C4 infiltration/Q and pilot publication integration remain independently open.

**Track boundary:** PR #9 Scientific Pilot, master architecture monograph, frozen historical audit and main remain untouched.

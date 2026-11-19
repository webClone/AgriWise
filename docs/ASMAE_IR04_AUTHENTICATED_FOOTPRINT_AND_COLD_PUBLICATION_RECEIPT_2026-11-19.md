# ASMAE IR-04 / IR-08 — Authenticated Footprint, Bitemporal Authority & Cold Publication Qualification Receipt

**Date:** 19 November 2026  
**Candidate Commit Under Qualification:** `665b94bf619dccce2adff423e57f2bde97cef21e`  
**Remediation Branch:** `feat/akaloris-asmae-ir04-r03-r04-review-20261119`  
**PR #32 Baseline:** `64a9f69945d8e3eda2bf33de9ff24e98186c9a17` (held unmerged; not fast-forwarded without user authorization)  
**Main Baseline:** `6edd3721c0defa7eed94b44cf96601ba59a49696` (strictly untouched)  
**PR #30 Baseline:** `599c4f6162c9795ad6e54b262bf8d7abfc50648d` (strictly untouched)  

---

## 1. Executive Summary & Qualification Decision

Candidate commit `665b94bf619dccce2adff423e57f2bde97cef21e` was independently qualified against adversarial vectors and rigorous multi-process durable read gates. The three blocking findings identified during the review of `665b94b` have been resolved with formal cryptographic and architectural safeguards:

1. **IR04-665-01 (P1): Positive Signed Source & Asset Admission Validation — CLOSED**
   * Syntactic SHA checks and metadata boolean bypasses (`exact_catalog_item`, string hashes without arrays) were eliminated.
   * `compute_scene_asset_sha256(scene)` computes deterministic SHA-256 over exact physical band arrays, dtypes, and shapes.
   * Detached HMAC-SHA256 admission receipts (`create_scene_admission_receipt` / `verify_scene_admission_receipt`) are verified against trusted issuer keys in `get_trusted_admission_keyring()`, cryptographically binding tenant, farm, plot, geometry SHA-256, operator digest, calibrated operator digest, observation valid time, and journal commitment time.
   * Validated against 11 adversarial negative controls in `test_c752_p1_02`: forged signature, swapped asset bytes, swapped asset hash, synthetic string arrays lacking physical rasters, foreign tenant namespace, foreign plot, foreign geometry, unbound operator, operator digest mismatch, and revision of admitted products under cutoff $K$.

2. **IR04-665-02 (P1): Verified Journal Authority for Bitemporal Cutoff $K$ — CLOSED**
   * In `engine.py`, ungrounded fallback `as_of_utc` was removed as knowledge cutoff $K$. The engine strictly requires an authenticated `bitemporal_replay_receipt` or verified durable `journal_watermark`.
   * Ungrounded queries fail closed with statewise support status `unavailable` and reason `unbound_namespace_or_bitemporal_receipt`.
   * Dual-clock separation ($T, K$) was proven end-to-end using real `CanonicalWorldlineService` hydration and engine statewise bridge: an event valid at Day 5 committed to journal at Day 20 is strictly excluded at $T=\text{Day } 10, K=\text{Day } 10$ (demoted to `none` / unsupported) and admitted at $T=\text{Day } 10, K=\text{Day } 21$ (effective resolution $11.77$ m, spatial support `local_operator`).

3. **IR04-665-03 (P1): Worker-First Cold Publication (No Prepublishing) — CLOSED**
   * Prepublishing before worker reintegration was completely eliminated from tests.
   * A true cold empty snapshot store receives worker execution; `rebuild_canonical_plot_snapshot` performs first-time publication and returns `publication_reused: False` with canonical `worldline_event_id`.
   * An isolated child OS subprocess (separate process memory, clean cache) verifies cold exact load (`numericalBindingValid: True`, `derived_publication_status: VALID_NORMAL`, `numerical_authority_verified: True`), cold latest head read, and FastAPI `TestClient` REST endpoints (`/v2/snapshots/{snap_id}` and `/v2/plots/{plot_id}/snapshot`) returning HTTP 200.
   * Negative controls verified:
     * Tampered `node.json` fails cryptographic verification and returns HTTP 409 Conflict.
     * Corrupted `head.json` fails closed, returning `available: False`.
     * Worker result with missing/incomplete sigma publishes as diagnostic, stripping numerical authority (`claims_numerical_authority: False`, `numerical_authority_verified: False`) and suppressing posterior numerical records.

4. **IR08-665-04 (P2): Retained Safe 20 m Interim Claim — OPEN / HELD**
   * Mixed-band Sentinel-2 scenes retain the conservative 20 m PSF ($\sigma=10.0$ m, $\text{FWHM} \approx 23.55$ m, native resolution $= 20.0$ m).
   * IR-08 adaptive resolution is **not claimed**; 1 m spatial resolution certification and numerical publication authority remain strictly **ON HOLD**.

---

## 2. Test Verification Matrix

| Suite | Scope / Tests | Execution Status | Duration |
| :--- | :--- | :---: | :---: |
| **C752 Adversarial Acceptance** | `test_asmae_c752_p1_p2_source_review_remediation.py` (4 tests) | **4 / 4 PASSED** | 7.06s |
| **Full Layer 05 Backend** | `services/agribrain/layer05_asmae/tests/` (227 tests) | **226 PASSED**, 1 deselected | 95.70s |
| **Full Frontend Suite** | `tests/frontend/` (47 files, 341 tests) | **341 / 341 PASSED** | 4.72s |
| **TypeScript Type Check** | `npx tsc --noEmit` | **0 ERRORS** | ~4.5s |

---

## 3. Governance Boundaries & Invariants

* **Protected `main`:** Untouched at `6edd3721c0defa7eed94b44cf96601ba59a49696`.
* **Draft PR #30:** Untouched at `599c4f6162c9795ad6e54b262bf8d7abfc50648d`.
* **Draft PR #32:** Remotely open and unmerged at `64a9f69945d8e3eda2bf33de9ff24e98186c9a17`. Fast-forwarding PR #32 is strictly **HELD** until user explicitly authorizes.
* **Actuator Interlocks:** Strictly fail-closed (`AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`).
* **Spatial 1 m Certification:** Strictly **ON HOLD**.
* **Numerical Publication Authority:** Strictly **ON HOLD**.
* **Master Register:** All 238 findings across 3 cohorts (40 / 48 / 150) preserved; 0 closed.

# ASMAE IR-04 / IR-08 — Findings HNEW-01 through HNEW-06 Remediation Receipt

**Date:** 19 November 2026  
**Candidate Evaluated:** `b6368010fdff16875b5049d1c53609cc1595be3f`  
**Review Branch:** `feat/akaloris-asmae-ir04-r03-r04-review-20261119`  
**Parent / Base Commit:** `64a9f69945d8e3eda2bf33de9ff24e98186c9a17` (Draft PR #32 head)  
**Review Specification:** [`plan/ASMAE_H01_H12_B636801_INDEPENDENT_SOURCE_REVIEW.md`](file:///C:/Users/E-C/Desktop/agriwise/plan/ASMAE_H01_H12_B636801_INDEPENDENT_SOURCE_REVIEW.md)  
**Progress Overlay:** [`plan/ASMAE_H01_H12_B636801_PROGRESS_OVERLAY.json`](file:///C:/Users/E-C/Desktop/agriwise/plan/ASMAE_H01_H12_B636801_PROGRESS_OVERLAY.json)  

---

## 1. Executive Summary

This receipt documents the engineering remediation and independent test verification of the six critical scientific admission defects identified in the independent source review of candidate `b636801`:

1. **HNEW-01:** Mandatory operator binding in the production engine; strict rejection of operator-less footprints and fabricated source asset receipts.
2. **HNEW-02:** Strict per-scene bitemporal commitment extraction from durable journal watermarks; prohibition of naive timestamp timezone inference (never falling back to valid/acquisition time).
3. **HNEW-03:** Production $H_t$ operator construction wired to band-dependent Gaussian PSF models (Sentinel-2 20m bands B05/B11 yield $\sigma = 10.0$ m, $\text{FWHM} \approx 23.548$ m; 10m bands yield $\sigma = 5.0$ m, $\text{FWHM} \approx 11.774$ m).
4. **HNEW-04:** Cell-mask geometry strictly grounded in target graph microzone cells via CSR $H_t$ column indices (`h_mat.indices`); prohibition of raw scene-pixel coordinates polluting graph cells.
5. **HNEW-05:** Positive signed admission; rejection of `diagnostic_only=True` even when `real_provider_product=True`; strict cross-check of tenant, farm, plot, and geometry SHA-256.
6. **HNEW-06:** End-to-end worker reintegration and cross-process HTTP API cold publication path verified via FastAPI `TestClient` against `/v2/snapshots/{id}` (200 OK + `numericalBindingValid=True`), `/v2/plots/{plot_id}/snapshot`, and 409 Conflict rejection of tampered records.

---

## 2. Detailed Technical Fixes

| ID | Module / File | Change Details |
| :--- | :--- | :--- |
| **HNEW-01** | [`services/agribrain/layer05_asmae/engine.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/engine.py#L2781) | Added `require_operator_binding=True` to `adapt_scenes_to_footprints`. Unmatched scenes fail closed. Rejects fabricated source hashes when authentic operator binding is required. |
| **HNEW-02** | [`services/agribrain/layer05_asmae/resolution/observation_footprint_adapter.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/resolution/observation_footprint_adapter.py#L41-L61) | Rewrote `_ensure_utc_iso` to reject naive timestamps without timezone indicator (`Z` or offset). Extracts per-scene `committed_at`; returns `None` if missing rather than falling back to `valid_time`. |
| **HNEW-03** | [`services/agribrain/layer05_asmae/geometry/operator_builder.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/geometry/operator_builder.py#L286) | Passed `band=getattr(scene, "band", None)` to `get_psf_model(scene.sensor, band=band)` in both single and batch builder paths. S2 20m bands receive $\sigma=10.0$ m, $\text{FWHM} \approx 23.548$ m. |
| **HNEW-04** | [`services/agribrain/layer05_asmae/resolution/observation_footprint_adapter.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/resolution/observation_footprint_adapter.py#L285-L300) | Without bound operator, `valid_cell_indices` is `None`. With bound operator, `valid_cell_indices` derives strictly from $H_t$ CSR non-zero column indices. |
| **HNEW-05** | [`services/agribrain/layer05_asmae/resolution/observation_footprint_adapter.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/resolution/observation_footprint_adapter.py#L125-L148) | Rejects scenes with `diagnostic_only=True` or `test_override=True`. Strictly cross-checks `tenant_id`, `farm_id`, `plot_id`, and `geometry_sha256`. |
| **HNEW-06** | [`services/agribrain/layer05_asmae/tests/test_asmae_hnew01_hnew06_source_review_remediation.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/tests/test_asmae_hnew01_hnew06_source_review_remediation.py) | Verified full worker execution, immutable publication, and FastAPI HTTP cold reads on `/v2/snapshots/{id}` and `/v2/plots/{plot_id}/snapshot`. |

---

## 3. Test Verification Receipts

| Test Suite | Command / Target | Result | Duration |
| :--- | :--- | :---: | :---: |
| **HNEW-01 through HNEW-06 Remediation** | `pytest test_asmae_hnew01_hnew06_source_review_remediation.py` | **6 / 6 PASSED** | 3.68s |
| **H01–H12 Adversarial Gates** | `pytest test_asmae_ir04_h01_h12_adversarial_gates.py` | **12 / 12 PASSED** | 1.28s |
| **IR-04 / IR-08 Adaptive Resolution** | `pytest test_asmae_ir04*.py test_asmae_ir08*.py` | **62 / 62 PASSED** | 2.40s |
| **All IR Test Files** | `pytest test_asmae_ir*.py test_asmae_hnew*.py` | **113 / 113 PASSED** (1 warning) | 17.42s |
| **Full Layer 05 Backend Suite** | `pytest services/agribrain/layer05_asmae/ -q` | **222 PASSED**, 1 deselected, 1 warning, 3 subtests passed | 93.83s |
| **Full Frontend Suite** | `node scripts/run-frontend-tests.mjs` | **341 / 341 PASSED** (47 test files) | 4.34s |
| **TypeScript Compiler Check** | `npx tsc --noEmit` | **0 errors (clean)** | 3.50s |

---

## 4. Standing Governance Holds & Scope Commitments

* **Protected `main`:** Untouched at `6edd3721c0defa7eed94b44cf96601ba59a49696`.
* **Draft PR #30:** Remote head reconciled at `599c4f6`; untouched.
* **Draft PR #32:** Kept open and unmerged on remote at `64a9f69945d8e3eda2bf33de9ff24e98186c9a17`.
* **Review Branch:** Isolated review on `feat/akaloris-asmae-ir04-r03-r04-review-20261119`.
* **Actuator Interlocks:** Strictly fail-closed (`AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`).
* **1 m Spatial Resolution Certification:** Strictly **ON HOLD** (`certified_1m=False`).
* **Numerical Publication Authority:** Strictly **ON HOLD**.
* **Master Register:** All 238 findings across 3 cohorts (40 / 48 / 150) preserved; 0 closed.

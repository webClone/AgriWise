# ASMAE IR-04 / IR-08 — H01–H12 Adversarial Acceptance Gates & Architectural Remediation Receipt

**Date:** 19 November 2026  
**Review Branch:** `feat/akaloris-asmae-ir04-r03-r04-review-20261119`  
**Remote Tracking:** `origin/feat/akaloris-asmae-ir04-r03-r04-review-20261119`  
**Parent / Base Commit:** `64a9f69945d8e3eda2bf33de9ff24e98186c9a17` (Draft PR #32 head)  
**Candidate Base:** `1d1112da3a01c97f31e4d4e6eab3ca86a2cf4176`  
**Review Specification:** [`plan/ASMAE_IR04_R03_R04_1D1112_INDEPENDENT_REVIEW_2026-11-19.md`](file:///C:/Users/E-C/Desktop/agriwise/plan/ASMAE_IR04_R03_R04_1D1112_INDEPENDENT_REVIEW_2026-11-19.md)  

---

## 1. Executive Summary

This receipt documents the resolution of architectural findings **IR04-H01** through **IR04-H06** and the independent execution and verification of the 12 focused adversarial acceptance tests (**H01–H12**) across the ASMAE Layer 05 engine, observation footprint adapter, and state-cell support contracts.

All changes have been developed on the isolated review branch `feat/akaloris-asmae-ir04-r03-r04-review-20261119`, branched directly from PR #32 head (`64a9f699`), ensuring that protected `main`, Draft PR #30, and the remote PR #32 head remain untouched.

---

## 2. Architectural Findings Remediation

### 2.1 IR04-H01: Authenticated Observation-to-Operator Admission
* **Issue:** `EvidenceFootprint` previously accepted arbitrary 64-hex string hashes without verifying that an admitted observation corresponds to an actual selected observation operator $H_t$.
* **Remediation:**
  * In [`observation_footprint_adapter.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/resolution/observation_footprint_adapter.py), bound footprint generation to genuine `compute_h_matrix_digest(operator.H_matrix)` and `SelectedOperatorBundle`.
  * Forged 64-hex SHA-256 strings without an authentic post-selection operator bundle or matching CRS/geometry fail closed (`return None`).
  * In [`engine.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/engine.py), passed `operator_bundle=self._selected_bundle` to `adapt_scenes_to_footprints`.

### 2.2 IR04-H02: Per-Cell Valid Support vs Scene-Wide Cloud Fraction
* **Issue:** Whole-scene `(1 - cloud_fraction)` falsely penalized unmasked clear pixels in partially cloudy scenes and allowed cloudy pixels in mostly clear scenes to claim observational support.
* **Remediation:**
  * Added `valid_cell_indices: Optional[Tuple[int, ...]]` and `valid_support_hash: Optional[str]` to `EvidenceFootprint` in [`state_cell_support.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/resolution/state_cell_support.py).
  * In `observation_footprint_adapter.py`, derived `valid_cell_indices` from non-zero columns of CSR $H_t$ matrix (`H_matrix.indices`) or the scene `valid_support` raster mask.
  * In `evaluate_state_cell_support`, masked cells are demoted with `"masked_by_scene_valid_support"` while unmasked cells evaluate with high radiometric QA observability (e.g. 0.95).

### 2.3 IR04-H03: Band-Dependent Instrument Calibration & Gaussian PSF Models
* **Issue:** Hardcoding S2 PSF FWHM at 12 m and S1 at 20 m risked contradictory resolution claims and ignored sensor optics.
* **Remediation:**
  * Integrated exact band-dependent Gaussian PSF models via [`geometry/psf.py:get_psf_model()`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/geometry/psf.py).
  * Sentinel-2 10 m bands ($\sigma = 5.0\text{ m} \implies \text{FWHM} \approx 11.774\text{ m}$).
  * Sentinel-2 20 m bands ($\sigma = 10.0\text{ m} \implies \text{FWHM} \approx 23.548\text{ m}$).
  * Sentinel-1 C-SAR ($\sigma = 7.5\text{ m} \implies \text{FWHM} \approx 17.661\text{ m}$).

### 2.4 IR04-H04: Strict Bitemporal Admission Without Temporal Fabrication
* **Issue:** Fallbacks to synthetic $K = T$ or defaulting $T$ to `end_date 23:59:59Z` violated bitemporal causality and fabricated admission boundaries.
* **Remediation:**
  * Removed all synthetic $K=T$ assignments and end-of-day timestamp fabrication in [`engine.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/engine.py#L2740-L2770).
  * $K$ is strictly derived from durable journal watermarks, replay receipts, or explicit `as_of_utc`.
  * If durable watermarks or committed scenes are absent, the engine reports `status: unavailable` with `reason: unbound_namespace_or_bitemporal_receipt`.

### 2.5 IR04-H05: Physical Sensor Physics & Cryptographic Support Identity Binding
* **Issue:** S1 C-band SAR directly measures surface roughness and dielectric moisture in top ~5 cm of soil; direct observation of `root_zone_water` is physically impossible. Furthermore, `StateCellSupport` previously serialized source hashes but not operator or calibration digests.
* **Remediation:**
  * In `observation_footprint_adapter.py`, removed `root_zone_water` from `S1_SAR_STATES`; C-band SAR directly senses only `("surface_wetness_event", "structure")`. Root-zone soil moisture is classified as an indirect/modeled coupling requiring hydrological EnKF propagation.
  * In [`state_cell_support.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/resolution/state_cell_support.py), added `admitted_operator_hashes: Tuple[str, ...]` and `admitted_calibration_hashes: Tuple[str, ...]`.
  * Modifying CSR $H_t$ matrix weights or calibration versions alters the canonical support identity digest, preventing identity collisions when estimated values coincide.

### 2.6 IR04-H06: Multi-Process Immutable Cold Publication Verification
* **Issue:** Verifying cold snapshot validation end-to-end under separate process contexts.
* **Remediation:**
  * Verified end-to-end against [`plot_snapshot_store.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/plot_snapshot_store.py) and Layer 10 classifier:
    * Positive runs with complete finite posterior states and sigmas publish with verified numerical authority (`numericalBindingValid=True`, `derived_publication_status="VALID_NORMAL"`).
    * Missing-uncertainty diagnostic runs publish without claiming numerical authority (`numericalBindingValid=False`, `derived_publication_status="DIAGNOSTIC_ONLY"`), preserving safe fallback without blocking valid older snapshots.

---

## 3. Adversarial Acceptance Gates (H01–H12)

Delivered and verified in [`test_asmae_ir04_h01_h12_adversarial_gates.py`](file:///C:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/tests/test_asmae_ir04_h01_h12_adversarial_gates.py):

| Gate | Description | Verified Outcome |
| :--- | :--- | :--- |
| **H01** | Forged 64-hex hashes with `production_usable=True` cannot create trusted local support | **PASSED** — Unbound footprint rejected; support yields `none` / `unsupported_state` |
| **H02** | Altering CSR $H_t$ weight changes operator digest, failing closed or updating support identity | **PASSED** — Altered matrix yields distinct SHA-256 digest; support identity reflects genuine bundle |
| **H03** | S2 scene with 50% cloudiness supports only unmasked cells, not entire bounding box | **PASSED** — Clear cell gets `local_operator` (11.77 m); cloudy cell gets `masked_by_scene_valid_support` |
| **H04** | S2 10 m and 20 m bands yield band-appropriate PSF FWHM, matching selected operator | **PASSED** — B04 yields $\approx 11.774$ m; B05/B11 yields $\approx 23.548$ m |
| **H05** | S1 backscatter cannot be labeled direct observation of root-zone water | **PASSED** — `root_zone_water` excluded from S1 direct states; evaluates to `none` / `unsupported_state` |
| **H06** | Scene valid at Day 5, committed Day 20 is absent at $(T=10, K=10)$ and eligible at $(T=10, K=21)$ | **PASSED** — Strict bitemporal filtering rejects future knowledge at $K=10$ and admits at $K=21$ |
| **H07** | Absence of verified observation or durable journal watermark returns `unavailable` | **PASSED** — No synthetic $K=T$ or end-of-day timestamps; returns `unavailable` |
| **H08** | Inconsistencies in tenant, plot, CRS, grid, or PSF/mask fail closed | **PASSED** — Mismatches in CRS, geometry, or bbox cleanly return `None` |
| **H09** | Verification over post-selection `SelectedOperatorBundle` identity | **PASSED** — Bundle operator digest and PSF parameters faithfully propagated into footprints |
| **H10** | Worker result with complete sigma survives cold exact/latest and publication classification | **PASSED** — Cold load verifies numerical binding; classifies as `VALID_NORMAL` |
| **H11** | Worker result missing sigma publishes as diagnostic fallback without blocking valid older head | **PASSED** — Diagnostic run does not claim numerical authority; does not suppress older valid head |
| **H12** | Altering source operator or calibration versions alters support identity even if estimates match | **PASSED** — Changed calibration or operator digest invalidates previous canonical digest |

---

## 4. Test Verification Suite Receipts

| Test Suite | Scope / Command | Result | Duration |
| :--- | :--- | :---: | :---: |
| **Adversarial Gates (H01–H12)** | `pytest test_asmae_ir04_h01_h12_adversarial_gates.py` | **12 / 12 PASSED** | 1.86s |
| **IR-04 / IR-08 Suite** | `pytest test_asmae_ir04*.py test_asmae_ir08*.py` | **62 / 62 PASSED** | 1.31s |
| **All IR Test Files** | `pytest test_asmae_ir*.py` | **107 / 107 PASSED** (1 warning) | 11.07s |
| **Full Layer 05 Backend Suite** | `pytest services/agribrain/layer05_asmae/ -q` | **216 PASSED**, 1 deselected, 1 warning | 58.42s |
| **Full Frontend Suite** | `node scripts/run-frontend-tests.mjs` | **341 / 341 PASSED** (47 test files) | 3.53s |
| **TypeScript Compiler Check** | `npx tsc --noEmit` | **0 errors (clean)** | 3.42s |

---

## 5. Standing Governance Holds & Scope Commitments

* **Protected `main` Branch:** Untouched at `6edd3721c0defa7eed94b44cf96601ba59a49696`.
* **Draft PR #30:** Untouched at `71ee1f788ec981bd0824089e46dc68164260444d`.
* **Draft PR #32:** Unmerged on remote at `64a9f69945d8e3eda2bf33de9ff24e98186c9a17`.
* **Actuator Interlocks:** Strictly fail-closed (`AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`).
* **1 m Spatial Resolution Certification:** Strictly **ON HOLD** (`certified_1m=False`).
* **Numerical Publication Authority:** Strictly **ON HOLD** pending multi-cycle real sensor calibration.
* **Master Register:** All 238 findings across 3 cohorts (40 / 48 / 150) remain intact; 0 findings independently closed.

# Akaloris Scientific Pilot — Phase 1G Source-Backed Scientific Continuity

**Implementation:** isolated pilot continuation branch `feat/pilot-phase1g-source-backed-continuity-20261106`.  
**Base:** Phase 1F observation-only readout acceptance at `f1b20258ba4119806fdebc2c7875f2c9dbf44513`.  
**Status:** Implementation and verification tests added; qualification **IN PROGRESS**.  
**Protected:** PR #9, frozen B2B-01..08, post-freeze signed-delivery branch `6b6767c`, `main@6edd372`, weather PR #25, historical `findings/layer0.md`, intended master monograph.

---

## 1. Purpose

Demonstrate the unbroken, verifiable **Source-to-Readout Scientific Evidence Chain** for Plot A (`6ab14f59ad442f274c3f2a62`) without fabricating evidence, without synthetic downstream L8 proof objects, and without enabling actuator authority:

$$\text{Actual Satellite Acquisition} \longrightarrow \text{Layer 0 Admission} \longrightarrow \text{Layer 1 Fusion Ledger} \longrightarrow \text{ASMAE State Update} \longrightarrow \text{Canonical Publication (10/10 Flags)} \longrightarrow \text{Authenticated Observation-Only Readout}$$

This phase connects the proven observation-only readout gate from Phase 1F to the genuine underlying physical provider evidence and state estimation pipeline, verifying that real-world optical measurements propagate deterministically through every layer while preserving fail-closed boundaries and zero-authority invariants.

---

## 2. Acceptance Criteria (G1–G6) & Negative Controls

### G1 — Source Truth (Provider Reality)
- Authentic Copernicus Sentinel-2 Level-2A product on Plot A (`S2A_MSIL2A_20261022T103031_N0513_R108_T31SDA_20261022T170604.SAFE`).
- Verifies exact provider product metadata:
  - Scene ID: `s2_real_scene_1_6ab14f59ad442f274c3f2a62`
  - Acquisition timestamp: `2026-10-22T10:41:05.859000+00:00`
  - Spatial CRS: `EPSG:4326`, Affine transform: `(2.885845116419216, 0.0001072621437076487, 0.0, 36.51262591555874, 0.0, -8.799111144690797e-05)`
  - Dimensions: 19 rows $\times$ 22 columns (Plot A grid)
  - Calibration / QA: `valid_fraction == 1.0`, `cloud_cover == 0.0166`
  - Stable content hash: `b11dc5f3eca328a3098798cde8afd989d0f6ae0f49bb19c4f13196c60a3b25b2`
  - Authentic band rasters on disk: `B02`, `B03`, `B04`, `B05`, `B06`, `B07`, `B08`, `B8A`, `B11`, `B12`, `SCL`, `DATAMASK`.

### G2 — Layer 0 Admission & Uncertainty
- Process real bands through `Sentinel2Engine.process_scene(...)` into canonical `Sentinel2ScenePackage`.
- QA verdict passes: `usable == True`, `quality_class == SceneQualityClass.EXCELLENT`.
- Spectral indices computed from real reflectances: `NDVI`, `EVI`, `NDMI`, `NDRE`, `BSI`, `MTCI`, `PSRI`, `REIP`.
- Observation packets generated with:
  - `data_status == DataStatus.OBSERVED`
  - Physical units (reflectance)
  - Explicit bounded uncertainty models (`sigmas={'ndvi': 0.025, 'evi': 0.035, 'ndmi': 0.045, 'ndre': 0.06, 'bsi': 0.08}`)
- Wrapped into canonical `Layer0SourcePackage` (`layer0-source-package-v2`) via `Layer0Runner().run(...)`.

### G3 — Layer 1 Fusion Evidence Ledger
- Driven by `run_layer1_fusion(inputs, layer0_output=l0_out)`.
- Produces `FieldTensor` backed by `Layer1ContextPackage`.
- Context package contains genuine evidence items derived from the admitted S2 scene (`sentinel2_..._ndvi`, `evi`, `ndmi`, `ndre`, `bsi`).
- Missing or absent modalities (weather, sensors) are tracked explicitly as gaps, never fabricated.

### G4 — ASMAE Scientific State & Covariance
- Real multi-temporal satellite scene stacks (Sentinel-2 and Sentinel-1) for Plot A are assimilated into state estimation.
- Computes posterior state vector ($x_{post}$) and posterior covariance matrix ($P_{post}$) reflecting physical uncertainty.
- Validates radiometric consistency and biophysical plausibility across the 13 latent states.

### G5 — Canonical Publication Integrity (10/10 Flags)
- Native publication executed via `publish_canonical_plot_snapshot(...)` into an isolated, temporary snapshot directory.
- Head verification via `load_latest_plot_snapshot(namespace)` verifies all 10 canonical publication validation flags:
  1. `nodeValid`: True
  2. `publicationValid`: True
  3. `receiptValid`: True
  4. `inventoryValid`: True
  5. `temporalBindingValid`: True
  6. `bindingValid`: True
  7. `lineageValid`: True
  8. `schemaValid`: True
  9. `contractValid`: True
  10. `publicationStatusValid`: True
- Contains zero fabricated proof roots: no downstream L8 prescription or authorization envelope attached.

### G6 — Authenticated Readout & Zero Authority
- Consumed via `read_observation_only_pilot_status(PLOT_A_NAMESPACE, ...)`.
- Validates exact owner identity (`tenant_id`, `farm_id`, `plot_id`), snapshot ID, and geometry hash.
- Evaluates age relative to observation timestamp ($\le 7$ days $\to$ `OBSERVATION_ONLY_READABLE`).
- Strict zero-authority invariants guaranteed:
  - `recommendations == []`
  - `actions == []`
  - `signed_irrigation_enabled == False`
  - `actuator_control_authorized == False`
  - `machine_execution_allowed == False`
  - `requires_confirmation == True`
  - `scientific_publication_authorized == False`
  - `independent_field_accuracy_verified == False`
  - `live_sensor_to_asmae_chain_verified == False`
  - `real_time_observation_claim == False`

### Negative Controls (Fail-Closed Gates)
1. **Corrupted source content:** Tampering with real raster bytes violates content hash verification and is quarantined or fails closed.
2. **Mismatched plot scope:** Injecting a foreign plot ID into Layer 0, Layer 1, or the publication reader fails closed with `ContractViolation`.
3. **Expired / post-cutoff evidence:** Evidence timestamped after `evidence_cutoff_at` violates temporal ordering and fails publication/readout validation.
4. **Invalid QA / Cloud obstruction:** Corrupted or cloud-saturated scenes are rejected as `usable == False` / `unusable`, preventing corrupt state updates.
5. **Stale publication:** A publication older than 7 days returns `STALE_OBSERVATION_ONLY` and is refused as current.
6. **Signed irrigation flag:** Setting `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=true` immediately aborts readout with `ContractViolation`.

---

## 3. Qualification Execution Commands

```powershell
git checkout feat/pilot-phase1g-source-backed-continuity-20261106
git rev-parse HEAD
$env:AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION = "false"

# Phase 1G suite
py -m pytest -q services/agribrain/tests/test_pilot_phase1g_source_backed_continuity.py

# Regression & Baseline suites
py -m pytest -q services/agribrain/tests/test_pilot_phase1f_observation_only.py
py -m pytest -q services/agribrain/tests/test_scientific_pilot_baseline_probe.py
py -m pytest -q services/agribrain/tests/test_pilot_publication_gate.py
py -m pytest -q services/agribrain/tests/test_pilot_plot_a_e2e_qualification.py
```

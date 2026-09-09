# Work Package 06: Rebuild MESIA Ingestion Around Immutable Captures

## 1. Executive Summary & Objective
MESIA (Multiplexed Environmental Sensing & In-situ Assimilation) provides opportunistic RF sensing using ambient Wi-Fi CSI and GNSS SNR signals. While the signal processing foundations are sound, the ingestion pipeline contains structural vulnerabilities and truth-class conflations:
1. **Separation of Raw Data & Metadata (Finding #17)**: `ingest_sigmf_csi()` writes content-addressed raw `.sigmf-data` files, but places `.sigmf-meta` alongside legacy plot-based files. The reader (`NativeWifiCsiExtractor.read_sigmf()`) searches for metadata matching the data file's basename, fails to find it, and silently substitutes default hardware, AGC, frequency, and **current-time timestamps**.
2. **Conflated Truth Classes (Finding #16)**: Derived biological estimates (such as inverted canopy moisture or foliage attenuation) are labeled `MEASURED_NATIVE`, disguising inverted model outputs as raw physical observations.
3. **Superficial Cryptographic Governance (Finding #18)**: Capability certificates accept empty string signatures (`validation_signature is not None`), and artifact existence checks verify string length rather than actual byte hashes.
4. **Synthetic Microzone Variations (Finding #19)**: The scan path generates spatial variations across microzones using coordinate-offset arithmetic rather than true multi-link RF tomographic sensitivities.
5. **Unscoped File Fallbacks (Finding #21)**: Capture lookups fall back to unscoped global filesystem paths using shortened plot IDs.

Work Package 06 re-architects MESIA ingestion around atomic, immutable, content-addressed capture manifests that bind raw bytes and metadata together, with strict truth-class categorization.

---

## 2. Affected Subsystems & Source References
- **MESIA Service**: [`services/agribrain/mesia/service.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/service.py#L2500-L2550).
- **SigMF Ingestion**: [`services/agribrain/mesia/ingestion/sigmf_ingest.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/ingestion/sigmf_ingest.py).
- **Native Wi-Fi CSI Extractor**: [`services/agribrain/mesia/extractors/wifi_csi_native.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/extractors/wifi_csi_native.py).
- **Capability Governance**: [`services/agribrain/mesia/capability_governance.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/capability_governance.py).

---

## 3. Root Cause & Defect Analysis

### 3.1 SigMF Metadata Disconnection and Fake Timestamping (Finding #17)
In `sigmf_ingest.py`, incoming Wi-Fi CSI captures are ingested into storage. The raw binary stream is stored under a content-addressed SHA-256 path (e.g. `data/tenant_1/plot_A/csi_<hash>.sigmf-data`), while the companion JSON metadata is stored under a mutable legacy path (e.g. `plot_A_latest.sigmf-meta`).
When `NativeWifiCsiExtractor.read_sigmf()` reads the scoped binary file, it looks for `<hash>.sigmf-meta` in the same directory. Finding nothing, it logs a warning and populates all radio metadata from defaults:
- `timestamp`: defaults to `datetime.now(timezone.utc)`.
- `center_freq`: defaults to `5.18 GHz`.
- `noise_floor`: defaults to `-95 dBm`.
This destroys temporal provenance: an archived capture from 6 months ago appears to have been acquired seconds ago, corrupting ASMAE's Kalman filter timing.

### 3.2 Mislabeling Derived Estimates as Native Evidence (Finding #16)
In `mesia/service.py`, derived canopy water content and root-zone water proposals are generated via empirical inversion formulas ($f(\Delta \text{SNR})$). These proposals are tagged with `TruthClass.MEASURED_NATIVE`. True native evidence consists solely of raw complex CSI subcarrier matrices or raw NMEA/RINEX SNR observations. Derived values inherit model error and must be classified as `TruthClass.DERIVED_MODEL_INFERRED` or `TruthClass.CALIBRATED_FEATURE`.

### 3.3 Synthetic Microzone Gradients (Finding #19)
When MESIA cannot resolve spatial tomographic links, `service.py` applies a synthetic gradient:
$$\text{val}_{\text{microzone}} = \text{base\_val} + (x_{\text{coord}} \times 0.01) - (y_{\text{coord}} \times 0.005)$$
This manufactures spatial heterogeneity out of coordinate numbers, deceiving downstream spatial planners into believing microzone moisture differences were physically measured.

---

## 4. Implementation Specification

### 4.1 Step 1: Implement Atomic Capture Manifests
1. Define `SigMFCaptureManifest` in `services/agribrain/mesia/contracts.py`:
   ```python
   @dataclass(frozen=True)
   class SigMFCaptureManifest:
       capture_id: str                   # SHA-256 of combined data + meta bytes
       tenant_id: str
       plot_id: str
       capture_timestamp_utc: datetime   # Exact radio acquisition timestamp
       data_sha256: str
       meta_sha256: str
       radio_profile: RadioProfile       # (frequency, bandwidth, antenna_array, rx_gain)
       packet_count: int
       storage_prefix: str               # Absolute scoped directory
   ```
2. In `sigmf_ingest.py`, write both `.sigmf-data` and `.sigmf-meta` using the exact same base hash identifier (`<capture_id>.sigmf-data` and `<capture_id>.sigmf-meta`) in an atomic transaction.
3. Forbid timestamp and radio defaults in `wifi_csi_native.py`: if the metadata file is missing or invalid, fail closed with `QuarantinedCaptureException`.

### 4.2 Step 2: Disentangle Evidence Hierarchy & Truth Classes
1. Implement a four-tier evidence typing model:
   - Tier 0: `NativeRFCapture` (Raw I/Q bytes, raw CSI matrix, uncalibrated SNR).
   - Tier 1: `CalibratedRFFeature` (Phase-sanitized CSI, multipath metric, excess attenuation in dB).
   - Tier 2: `BiologicalInference` (Canopy water index, dielectric permittivity with ISO GUM uncertainty budget).
   - Tier 3: `ASMAEInnovationProposal` (State innovation proposal targeted to a specific ASMAE variable).
2. Forbid labeling Tier 2 or Tier 3 objects as `MEASURED_NATIVE`.

### 4.3 Step 3: Eliminate Synthetic Microzone Gradients
1. If the radio network geometry does not provide multi-link intersecting coverage over microzones:
   - MESIA must emit a single plot-level lumped observation or return `is_observable=False`.
   - Never apply deterministic coordinate math to manufacture spatial variance.

### 4.4 Step 4: Strict Ownership & Qualification Enforcement
1. Remove all unscoped fallback paths in `sigmf_ingest.py` and `service.py`. Every file access must specify `tenant_id`, `farm_id`, and `plot_id`.
2. In `capability_governance.py`, verify cryptographic signatures against stored public keys:
   ```python
   if not validation_signature or len(validation_signature.strip()) < 64:
       raise InvalidQualificationCertificate("Signature is missing or invalid")
   ```

---

## 5. Verification & Completion Criteria
- **Metadata Binding Invariant**: Every processed CSI frame has an identical capture hash binding its binary payload to its SigMF metadata.
- **Zero Synthetic Timestamps**: Ingestion never calls `datetime.now()` for capture timestamps; missing capture times cause immediate quarantine.
- **Truth Class Verification**: 100% of biological proposals emitted by MESIA are tagged with `TruthClass.DERIVED_MODEL_INFERRED` and include complete GUM uncertainty budgets.
- **Namespace Isolation**: Captures from Tenant A can never be retrieved or resolved by Tenant B.

---

## 6. Monograph & Defect Task Traceability
- **Monograph Findings**: Finding #16 (Native vs derived evidence mislabeling), Finding #17 (SigMF ingestion metadata disconnection), Finding #18 (Qualification checks), Finding #19 (Canonical spatial lattice vs synthetic gradients), Finding #21 (Namespace isolation).
- **Defect Tasks**: [A08-mesia-rf-snr-vwc-assimilation.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A08-mesia-rf-snr-vwc-assimilation.md), [A09-mesia-qualification-and-evidence-verification.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A09-mesia-qualification-and-evidence-verification.md).
- **Phase Tasks**: [P03.1-specify-native-rf-measurements-and-models.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P03.1-specify-native-rf-measurements-and-models.md), [P03.2-enforce-cryptographic-qualification-at-use-time.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P03.2-enforce-cryptographic-qualification-at-use-time.md).

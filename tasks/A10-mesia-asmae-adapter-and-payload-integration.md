# Task A10: MESIA-ASMAE Adapter Disconnection & String Encoding

## 1. Finding Overview
* **Finding ID:** A10
* **Severity:** **P0 — Architectural Disconnection & Incomplete Ingestion Chain**
* **Component:** MESIA Integration Spine & ASMAE Observation Adapters
* **Primary Target Files:**
  - [`services/agribrain/layer05_asmae/adapters/mesia_adapter.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/adapters/mesia_adapter.py)
  - [`services/agribrain/mesia/integration.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/integration.py)
  - [`services/agribrain/layer05_asmae/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/runner.py)

---

## 2. Technical Analysis & Code Audit

### The Architectural Disconnect
1. **Orphaned Adapter:**
   `grep_search` reveals that `MesiaAsmaeAdapter` is called exclusively inside `mesia/integration.py`. Neither the Layer 0 Evidence Spine nor ASMAE's main execution engine (`layer05_asmae/runner.py`) imports or executes this adapter.
2. **Loss of Numerical Data via String Formatting:**
   In `services/agribrain/layer05_asmae/adapters/mesia_adapter.py`, lines 75–76:
   ```python
   return ObservationEvent(
       observation_id=f"asmae-mesia-{proposal.proposal_id}",
       ...
       spatial_support_ref=f"microzone:{proposal.microzone_id}:{proposal.depth_stratum}",
       quality_ref=f"support:{proposal.confidence_support:.2f}:var:{proposal.observation_variance:.3f}",
       ...
   )
   ```
   The quantitative observation value, innovation delta, and covariance matrix are formatted into human-readable string references!
   The `ObservationEvent` contains **no numerical array, tensor, or scalar field** containing the measured quantity. An assimilation operator receiving this event would have to parse strings with regex to extract variance!
3. **Lattice Mismatch:**
   MESIA constructs a separate fixed grid (`{plot_id}_MZ_1_1`) that is independent of the canonical spatial coordinate frame and depth stratifications used by ASMAE and SIRE.

---

## 3. Agronomical & Systemic Impact
- **False Claim of Radio Assimilation:** The documentation asserts that AgriBrain performs real-time radio-frequency environmental assimilation via ASMAE. In reality, the integration stops at the creation of disconnected mock events.
- **Precision Loss:** Encoding float variances into `:.3f` strings truncates numerical precision required for Kalman matrix inversions.

---

## 4. Implementation Plan

### Step 1: Add Structured Numerical Fields to `ObservationEvent`
In `services/agribrain/layer05_asmae/observation/contracts.py`:
- Ensure `ObservationEvent` includes typed numerical payloads:
```python
@dataclass
class ObservationEvent:
    ...
    # Typed numerical observation payload
    observation_vector: Optional[List[float]] = None
    observation_covariance: Optional[List[List[float]]] = None
    spatial_coords: Optional[Dict[str, Any]] = None  # GeoJSON / UTM polygon
```

### Step 2: Populate True Numerical Tensors in `MesiaAsmaeAdapter`
In `services/agribrain/layer05_asmae/adapters/mesia_adapter.py`:
- Map the actual innovation value and variance matrix into typed fields, rather than string references.
- Link the spatial support to the plot's canonical microzone polygon geometry.

### Step 3: Wire into ASMAE Evidence Pipeline (With Strict Authority Containment)
In `services/agribrain/layer05_asmae/runner.py`:
- Add a ingestion step for admitted radio events.
- Strictly enforce that unless a capability has completed external field calibration, `AuthorityVector(state_update_allowed=False, diagnosis_allowed=False, visualization_allowed=True)` is enforced (Research/Diagnostic Support Only).

---

## 5. Verification & Test Plan

### Automated Integration Tests
1. **Contract Integrity Test:**
   - Convert a valid Layer 0 MESIA record using `MesiaAsmaeAdapter.to_asmae_observation_event`.
   - Assert `isinstance(event.observation_vector, list)` and `len(event.observation_vector) > 0`.
   - Assert `event.observation_covariance[0][0] == proposal.observation_variance`.
2. **End-to-End Pipeline Ingestion Test:**
   - Pass an admitted MESIA event into `run_asmae_pipeline`.
   - Verify it is admitted into the evidence store and visible in the diagnostic trace without corrupting soil water content.

---

## 6. Progress Tracking Checklist
- [ ] `ObservationEvent` expanded to include typed numerical vector and covariance.
- [ ] `MesiaAsmaeAdapter` updated to populate numerical payloads.
- [ ] Fixed dummy grid replaced with plot canonical microzone support.
- [ ] End-to-end ingestion tested with strict authority gating.

# Task A14: Layer 10 Water Surfaces Signature Mismatch & Undefined Helpers

## 1. Finding Overview
* **Finding ID:** A14
* **Severity:** **P1 — Spatial Publication Failure & Swallowed Exception**
* **Component:** Layer 10 SIRE (Spatial Intelligence & Representation Engine)
* **Primary Target Files:**
  - [`services/agribrain/layer10_sire/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/runner.py) (line 2256)
  - [`services/agribrain/layer10_sire/surfaces/water.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/surfaces/water.py)

---

## 2. Technical Analysis & Code Audit

### Defect 1: Positional & Keyword Argument Collision
In `services/agribrain/layer10_sire/surfaces/water.py`, line 18:
```python
def generate_water_surfaces(
    l1_data: Any,
    l3_data: Any,
    H: int,
    W: int,
    ...
) -> Dict[str, np.ndarray]:
```
In `services/agribrain/layer10_sire/runner.py`, line 2256:
```python
# DEFECT: H and W are passed positionally first, followed by keyword l1_data and l3_data!
surfaces = generate_water_surfaces(
    H, W,
    l1_data=l1_res.output if l1_res else None,
    l3_data=l3_res.output if l3_res else None,
    ...
)
```
- Argument 1 (`H`) maps positionally to `l1_data`.
- Argument 2 (`W`) maps positionally to `l3_data`.
- The keyword arguments `l1_data=...` and `l3_data=...` then attempt to bind the same parameters.
- **Python Runtime Error:** `TypeError: generate_water_surfaces() got multiple values for argument 'l1_data'`.

---

### Defect 2: Undefined Helper Functions Inside `water.py`
Even if the argument order is corrected, `layer10_sire/surfaces/water.py` invokes:
```python
water_stress_map = _compute_water_stress_prob(...)
drainage_map = _compute_drainage_deficit(...)
```
Neither `_compute_water_stress_prob` nor `_compute_drainage_deficit` is defined in `water.py`, nor are they imported from any submodule. A direct call raises `NameError: name '_compute_water_stress_prob' is not defined`.

---

### Defect 3: Swallowed Exception
In `services/agribrain/layer10_sire/runner.py`, the call is enclosed in a broad `try/except Exception:` block that logs a debug line and increments `skipped += 2`.
The layer completes and returns status `OK`, but **no water or drainage raster surfaces are ever published to the frontend or spatial database**.

---

## 3. Agronomical & Systemic Impact
- **Missing Heatmaps in UI:** Farm operators viewing the spatial map see NDVI and thermal surfaces, but the "Root Zone Water Stress" and "Soil Drainage Risk" surface layers are permanently blank or missing.
- **False Green Execution:** The orchestrator reports Layer 10 as healthy despite core hydrological surfaces failing.

---

## 4. Implementation Plan

### Step 1: Align Function Call Signatures
In `services/agribrain/layer10_sire/runner.py`, call `generate_water_surfaces` with explicit keyword arguments for all parameters:
```python
surfaces = generate_water_surfaces(
    l1_data=l1_res.output if l1_res else None,
    l3_data=l3_res.output if l3_res else None,
    H=H,
    W=W,
    ...
)
```

### Step 2: Implement or Wire the Required Hydrological Surface Helpers
In `services/agribrain/layer10_sire/surfaces/water.py`:
- Implement clean, vectorized NumPy functions for water stress and drainage maps:
```python
def _compute_water_stress_prob(l1_data: Any, l3_data: Any, H: int, W: int) -> np.ndarray:
    """Generate normalized root zone water stress probability grid [0, 1]."""
    grid = np.zeros((H, W), dtype=np.float32)
    # If L3 water data provides spatial moisture / stress
    if l3_data and hasattr(l3_data, "root_zone"):
        ks = float(getattr(l3_data.root_zone, "stress_factor_ks", 1.0))
        # ks=1 is no stress; stress = 1.0 - ks
        base_stress = max(0.0, min(1.0, 1.0 - ks))
        grid.fill(base_stress)
    return grid

def _compute_drainage_deficit(l1_data: Any, l3_data: Any, H: int, W: int) -> np.ndarray:
    """Generate deep drainage deficit grid (mm)."""
    grid = np.zeros((H, W), dtype=np.float32)
    if l3_data and hasattr(l3_data, "fluxes"):
        drainage = float(getattr(l3_data.fluxes, "deep_drainage_mm", 0.0))
        grid.fill(drainage)
    return grid
```

### Step 3: Remove Blanket Swallowing of Surface Generation Failures
If water surfaces cannot be generated, record `skipped_surfaces.append("water_stress")` with an explicit reason in Layer 10 quality metrics, rather than silently hiding runtime crashes.

---

## 5. Verification & Test Plan

### Automated Regression Tests
Create `tests/test_a14_l10_water_surfaces.py`:
1. **Signature Invocation Test:**
   - Execute `generate_water_surfaces(l1_data=None, l3_data=mock_l3, H=50, W=50)`.
   - Assert returns dictionary containing keys `"water_stress"` and `"drainage_deficit"`.
   - Assert shape of both arrays is `(50, 50)`.
2. **Layer 10 Runner Test:**
   - Execute `run_layer10_sire` with mock inputs.
   - Assert `output.surfaces["water_stress"]` exists and has valid shape.
   - Assert `skipped` count is 0.

---

## 6. Progress Tracking Checklist
- [ ] Call in `layer10_sire/runner.py` updated to keyword arguments matching signature.
- [ ] `_compute_water_stress_prob` and `_compute_drainage_deficit` implemented in `water.py`.
- [ ] Swallowed exceptions replaced with structured surface quality reporting.
- [ ] Automated regression tests written and passing.

# Task A17: L2 Growth Engine Missing Import & Time Basis

## 1. Finding Overview
* **Finding ID:** A17
* **Severity:** **P1 — Runtime NameError Crash & Temporal Scaling Defect**
* **Component:** Layer 2 Vegetation (Growth Curve & Velocity Engine)
* **Primary Target File:** [`services/agribrain/layer2_veg_int/growth_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer2_veg_int/growth_engine.py) (line 296)

---

## 2. Technical Analysis & Code Audit

### Defect 1: Unhandled `NameError` on Irregular Time Steps
In `services/agribrain/layer2_veg_int/growth_engine.py`, line 296:
```python
# In Savitzky-Golay derivative window scaling:
if len(valid_dts) > 0:
    dt_days = statistics.mean(valid_dts)  # <-- NameError: name 'statistics' is not defined!
```
- Module `statistics` is called directly without being imported at the top of the file.
- When an irregular satellite observation series (e.g. Sentinel-2 passes interrupted by clouds) is processed, the derivative calculation raises `NameError: name 'statistics' is not defined` and aborts Layer 2 execution.

---

### Defect 2: Temporal Derivative Calculation Assumes Unit Sample Indices
In `_fit_whittaker`, `_fit_spline_scipy`, and `_savgol_derivatives`:
- The smoothing algorithms and derivatives frequently assume uniform unit sample intervals ($i, i+1$), rather than scaling by actual elapsed days between calendar observations ($t_{i+1} - t_i$).
- An observation series with points at Day 0, Day 5, and Day 25 produces distorted slope and acceleration values ($d(\text{NDVI})/dt$), artificially compressing or stretching the inferred crop growth velocity.

---

## 3. Agronomical & Systemic Impact
- **Vegetative Stress Diagnosis Failure:** Growth rate slowdown is the earliest indicator of nitrogen deficiency or root disease. If derivative calculations crash or use unit spacing, the onset of crop stagnation is missed.
- **Pipeline Abort:** A farm with cloud-filtered satellite observations crashes during Layer 2 execution.

---

## 4. Implementation Plan

### Step 1: Add Missing Import / Use NumPy Mean
In `services/agribrain/layer2_veg_int/growth_engine.py`:
- Add `import statistics` to top-level imports or use NumPy:
```python
import numpy as np
...
# In line 296:
dt_days = float(np.mean(valid_dts)) if len(valid_dts) > 0 else 1.0
```

### Step 2: Enforce Explicit Calendar Time Basis for Derivatives
Refactor derivative calculation to take an explicit array of cumulative days ($t_0, t_1, \dots, t_n$):
```python
def compute_temporal_derivatives(values: np.ndarray, dates_in_days: np.ndarray) -> np.ndarray:
    """Calculate d(NDVI)/dt in units of [NDVI / day] respecting irregular sampling."""
    if len(values) < 2:
        return np.zeros_like(values)
    
    # Use non-uniform numerical gradient
    velocity = np.gradient(values, dates_in_days)
    return velocity
```

---

## 5. Verification & Test Plan

### Automated Regression Tests
Create `tests/test_a17_l2_growth_engine.py`:
1. **NameError Reproduction Test:**
   - Call `fit_growth_curve` with irregular observation timestamps: `["2026-05-01", "2026-05-06", "2026-05-20"]`.
   - Assert function completes successfully without raising `NameError`.
2. **Derivative Scaling Test:**
   - Create linear ramp with $\text{NDVI}_0 = 0.20$ at Day 0 and $\text{NDVI}_1 = 0.40$ at Day 10.
   - True slope is $(0.40 - 0.20) / 10 = 0.02\ \text{NDVI/day}$.
   - Assert returned velocity equals $0.02$ (NOT $0.20$).

---

## 6. Progress Tracking Checklist
- [ ] Missing `statistics` import / `np.mean` replacement implemented.
- [ ] Calendar day time basis enforced on all numerical derivative routines.
- [ ] Irregular observation series tested without exceptions.
- [ ] Automated unit tests passing.

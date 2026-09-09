# Task A18: Layer 6 Outcome Metrics Time Spacing & Causal Labeling

## 1. Finding Overview
* **Finding ID:** A18
* **Severity:** **P1 — Numerical Metric Distortion & Pseudo-Causal Labeling**
* **Component:** Layer 6 Execution (Outcome Evaluation Engine)
* **Primary Target Files:**
  - [`services/agribrain/layer6_exec/outcomes/metrics.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/outcomes/metrics.py) (lines 29–41, 78)
  - [`services/agribrain/layer6_exec/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/runner.py)

---

## 2. Technical Analysis & Code Audit

### Defect 1: Unit-Less Sample Index Slopes and Integrals
In `services/agribrain/layer6_exec/outcomes/metrics.py`, lines 29–41:
```python
def _slope(vals: List[float]) -> float:
    """Linear slope estimate: (last - first) / (n-1)."""
    if len(vals) < 2:
        return 0.0
    return (vals[-1] - vals[0]) / (len(vals) - 1)  # <-- Divides by sample count, NOT elapsed days!

def _integral(vals: List[float]) -> float:
    """Trapezoidal integration proxy."""
    if len(vals) < 2:
        return 0.0
    return sum((vals[i] + vals[i + 1]) / 2.0 for i in range(len(vals) - 1)) # <-- Assumes dt=1 sample!
```
- In an observational 14-day window:
  - If 14 daily samples are present: slope divides by 13.
  - If only 2 satellite observations exist: slope divides by 1.
- The resulting "velocity" is in units of $[\Delta\text{NDVI} / \text{sample}]$, rendering comparisons between plots with different revisit cadences meaningless.
- The integral calculates cumulative vegetative mass assuming $\Delta t = 1$, misrepresenting cumulative biomass.

---

### Defect 2: Truthiness Fallback Drops Valid Zero NDVI
In `services/agribrain/layer6_exec/outcomes/metrics.py`, line 78:
```python
ndvi = rec.get("ndvi_smoothed") or rec.get("ndvi_interpolated")
```
- In Python, `0.0` is falsy (`bool(0.0) is False`).
- If bare ground, fallow tillage, or total crop termination results in `ndvi_smoothed = 0.0`, the `or` operator discards the zero and takes `ndvi_interpolated`.
- A valid zero measurement cannot be recorded.

---

### Defect 3: Observational Pre/Post Tagged as "Difference-in-Differences"
In line 14 and throughout the outcomes engine:
- Simple observational pre-intervention (14 days prior) vs post-intervention (14 days after) deltas are assigned method enum `CausalMethod.DIFF_IN_DIFF`.
- A genuine Difference-in-Differences (DiD) requires an un-treated control plot or untreated zone within the same field to subtract the ambient weather/phenology trend:
  $$\tau_{\text{DiD}} = (\bar{Y}_{\text{treated, post}} - \bar{Y}_{\text{treated, pre}}) - (\bar{Y}_{\text{control, post}} - \bar{Y}_{\text{control, pre}})$$
- Calling an uncontrolled pre/post comparison "causal" misleads downstream reinforcement learning agents (such as Omega).

---

## 3. Agronomical & Systemic Impact
- **Omega Learning Contamination:** If the future learned world model trains on these outcome records as "causal treatment effects", it will learn spurious associations (e.g. attributing rain-driven green-up to a fertilizer application that occurred 2 days before a storm).
- **Distorted Recovery Metrics:** High-cadence fields appear to have slower growth recovery than low-cadence fields due to the division by $(n-1)$ samples.

---

## 4. Implementation Plan

### Step 1: Explicit Calendar Day Basis for Slopes & Integrals
In `services/agribrain/layer6_exec/outcomes/metrics.py`:
- Pass explicit dates alongside values:
```python
def _slope_per_day(vals: List[float], dates_days: List[float]) -> float:
    """Compute true rate of change: delta_val / delta_days."""
    if len(vals) < 2 or len(dates_days) < 2:
        return 0.0
    total_days = dates_days[-1] - dates_days[0]
    if total_days <= 0.0:
        return 0.0
    return (vals[-1] - vals[0]) / total_days

def _trapezoid_integral(vals: List[float], dates_days: List[float]) -> float:
    """Trapezoidal integration: sum( (y_i + y_{i+1})/2 * dt_days )."""
    if len(vals) < 2 or len(dates_days) < 2:
        return 0.0
    total_area = 0.0
    for i in range(len(vals) - 1):
        dt = dates_days[i + 1] - dates_days[i]
        total_area += (vals[i] + vals[i + 1]) / 2.0 * dt
    return total_area
```

### Step 2: Fix Falsy Zero NDVI Check
```python
# Check explicit None, preserving valid 0.0
val = rec.get("ndvi_smoothed")
if val is None:
    val = rec.get("ndvi_interpolated")
ndvi = float(val) if val is not None else None
```

### Step 3: Honest Causal Labeling
- Label single-field pre/post calculations honestly as `CausalMethod.OBSERVATIONAL_PRE_POST`.
- Reserve `CausalMethod.DIFF_IN_DIFF` or `SYNTHETIC_CONTROL` strictly for runs where an untreated reference zone / plot is provided.

---

## 5. Verification & Test Plan

### Automated Tests
1. **Zero NDVI Preservation:**
   - Pass record with `ndvi_smoothed = 0.0` and `ndvi_interpolated = 0.45`.
   - Assert extracted `ndvi == 0.0`.
2. **Sampling Rate Invariance Test:**
   - Timeseries A: 2 points over 10 days ($0.20 \to 0.40$).
   - Timeseries B: 11 daily points over 10 days ($0.20 \to 0.40$ linearly).
   - Assert `_slope_per_day(A) == _slope_per_day(B) == 0.02`.

---

## 6. Progress Tracking Checklist
- [ ] Slope and integral refactored to consume explicit day deltas.
- [ ] Falsy `0.0` check replaced with `val is not None`.
- [ ] `OBSERVATIONAL_PRE_POST` enum introduced and applied honestly.
- [ ] Confounder flag gating checked before emitting causal claims.
- [ ] Automated regression tests passing.

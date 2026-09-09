# Task A21: Layer 1 Zone Engine All-NaN Cloud Slice Runtime Warning

## 1. Finding Overview
* **Finding ID:** A21
* **Severity:** **P2 — Numerical Runtime Warning & Spatial Fallback Defect**
* **Component:** Layer 1 Fusion (Zone Engine)
* **Primary Target File:** [`services/agribrain/layer1_fusion/zone_engine.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer1_fusion/zone_engine.py) (line 54)

---

## 2. Technical Analysis & Code Audit

### The Numerical Issue
In `services/agribrain/layer1_fusion/zone_engine.py` line 54:
```python
ndvi_median_map = np.nanmedian(ndvi_np, axis=0)
```
When a parcel suffers 100% persistent cloud or shadow cover across all candidate scene acquisitions, every element along `axis=0` is `np.nan`.
NumPy executes:
`RuntimeWarning: All-NaN slice encountered`
and populates `ndvi_median_map` with an all-NaN matrix.
Downstream operations attempting to compute zone percentiles, clustering, or zonal statistics fail or produce degraded empty dictionaries without explicit notification of 100% cloud obscuration.

---

## 3. Implementation Plan

### Step 1: Add Pre-Check for All-NaN Slices
In `services/agribrain/layer1_fusion/zone_engine.py`:
```python
# Check if entire stack is NaN
valid_mask = np.isfinite(ndvi_np)
if not np.any(valid_mask):
    # 100% cloud cover fallback: use prior or flag as completely obscured
    logger.warning("All NDVI scenes are 100% NaN/cloud-masked. Utilizing synthetic/historical prior map.")
    ndvi_median_map = np.full(ndvi_np.shape[1:], fill_value=0.25, dtype=np.float32) # Baseline bare soil
    is_cloud_obscured = True
else:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        ndvi_median_map = np.nanmedian(ndvi_np, axis=0)
    is_cloud_obscured = False
```

### Step 2: Record Spatial Observability State
Ensure the returned zone packet explicitly records:
```python
"optical_cloud_obscuration": "TOTAL_100_PERCENT" if is_cloud_obscured else "CLEAR_OR_PARTIAL"
```

---

## 4. Verification & Acceptance Criteria

1. **Warning Elimination:**
   - Execute `services/agribrain/layer1_fusion/tests/test_zone_engine.py::test_fallback_on_all_clouds`.
   - Assert zero `RuntimeWarning: All-NaN slice encountered`.
2. **Safe Fallback Array:**
   - Verify returned `ndvi_median_map` has finite values and valid shape.

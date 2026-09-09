# Task A24: Layer 10 SIRE Display Trace Metrics Initialization

## 1. Finding Overview
* **Finding ID:** A24
* **Severity:** **P1 — Conditional Runtime Crash (NameError)**
* **Component:** Layer 10 SIRE (Runner & Display Trace)
* **Primary Target File:** [`services/agribrain/layer10_sire/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/runner.py) (lines 5317–5318)

---

## 2. Technical Analysis & Code Audit

### The Defect
In `services/agribrain/layer10_sire/runner.py`, lines 5304–5322:
```python
experimental_policy_active = (
    requested_policy in ("experimental", "hybrid")
    and "satellite" not in str(resolved_policy).lower()
)
display_trace = {
    ...
    "visual_detail_mask_pct": one_meter_visual_coverage_pct if experimental_policy_active else None,
    "strict_candidate_pct": strict_one_meter_candidate_pct if experimental_policy_active else None,
    ...
}
```
If `experimental_policy_active` is True, Python attempts to evaluate `one_meter_visual_coverage_pct` and `strict_one_meter_candidate_pct`.
Neither variable was declared or assigned earlier in the function scope!
**Result:** `NameError: name 'one_meter_visual_coverage_pct' is not defined`.
Whenever experimental high-resolution canopy policy is activated, the entire SIRE pipeline crashes.

---

## 3. Implementation Plan

### Step 1: Pre-initialize Display Trace Coverage Variables
In `services/agribrain/layer10_sire/runner.py`:
Directly before building `display_trace`, initialize the metrics safely:
```python
one_meter_visual_coverage_pct: Optional[float] = None
strict_one_meter_candidate_pct: Optional[float] = None

if active_surface and hasattr(active_surface, "provenance") and isinstance(active_surface.provenance, dict):
    one_meter_visual_coverage_pct = active_surface.provenance.get("one_meter_coverage_pct", 0.0)
    strict_one_meter_candidate_pct = active_surface.provenance.get("strict_candidate_pct", 0.0)
else:
    one_meter_visual_coverage_pct = 0.0
    strict_one_meter_candidate_pct = 0.0
```

---

## 4. Verification & Acceptance Criteria

1. **Experimental Policy Execution Test:**
   - Execute SIRE with `requested_policy="experimental"` on mock parcel.
   - Assert pipeline finishes with `status=LayerStatus.OK`.
   - Assert `output.display_trace["visual_detail_mask_pct"]` is a valid numeric float (e.g. 0.0).

---

## 5. Resolution & Verification Status
- **Status:** **RESOLVED** via Work Package 10 (WP10).
- **Implementation:** Pre-initialized `one_meter_visual_coverage_pct` and `strict_one_meter_candidate_pct` prior to `display_trace` building in `services/agribrain/layer10_sire/runner.py`.
- **Verification:** Verified by `test_defect_a24_experimental_policy_no_name_error` in `services/agribrain/tests/test_wp10_l9_l10_publication.py`.


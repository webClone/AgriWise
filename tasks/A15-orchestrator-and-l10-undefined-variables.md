# Task A15: Orchestrator & Layer 10 Conditional Undefined Variables

## 1. Finding Overview
* **Finding ID:** A15
* **Severity:** **P1 — Conditional Runtime Crash (NameError)**
* **Component:** Orchestrator V2 & Layer 10 SIRE Runner
* **Primary Target Files:**
  - [`services/agribrain/orchestrator_v2/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/runner.py) (line 2925)
  - [`services/agribrain/layer10_sire/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer10_sire/runner.py) (lines 5317–5318)

---

## 2. Technical Analysis & Code Audit

### Defect 1: Undefined `ts` in Terminal Publication Branch
In `services/agribrain/orchestrator_v2/runner.py`, line 2925:
```python
# In fallback terminal Layer 10 result construction
l10_fallback = Layer10Output(
    plot_id=inputs.plot_id,
    timestamp=ts,  # <-- NameError: name 'ts' is not defined!
    ...
)
```
- In this execution branch (e.g. when SIRE surfaces are skipped or fail upstream), the fallback output attempts to pass `timestamp=ts`.
- `ts` is not defined in this function scope (`ts_start` was instantiated at the top of the function).
- When hit, this raises an unhandled `NameError` and crashes the orchestrator pipeline.

---

### Defect 2: Undefined Resolution Coverage Variables in Layer 10 SIRE
In `services/agribrain/layer10_sire/runner.py`, lines 5316–5319:
```python
# Experimental display trace logging
if enable_display_trace:
    trace["one_meter_visual_coverage"] = one_meter_visual_coverage_pct  # <-- NameError!
    trace["strict_candidate_pct"] = strict_one_meter_candidate_pct      # <-- NameError!
```
- The variables `one_meter_visual_coverage_pct` and `strict_one_meter_candidate_pct` are referenced without being declared or computed in this function scope.
- Whenever experimental display tracing or high-resolution inspection mode is enabled, the pipeline crashes with a `NameError`.

---

## 3. Agronomical & Systemic Impact
- **Intermittent Production Outages:** These defects sit on edge paths (error fallbacks and experimental tracing). During ordinary sunny-day runs they remain dormant, but the moment a fallback is needed or a feature flag is toggled, they trigger fatal runtime crashes.

---

## 4. Implementation Plan

### Step 1: Fix Undefined Timestamp in `orchestrator_v2/runner.py`
In line 2925:
```python
# Replace undefined 'ts' with canonical execution timestamp
timestamp = ts_start.isoformat() if hasattr(ts_start, "isoformat") else str(ts_start)
```

### Step 2: Initialize Resolution Metrics in `layer10_sire/runner.py`
In `services/agribrain/layer10_sire/runner.py`:
- Initialize resolution coverage variables at the start of the function:
```python
one_meter_visual_coverage_pct = 0.0
strict_one_meter_candidate_pct = 0.0

# Compute from spatial metadata if available
if hasattr(l1_data, "spatial_resolution") and l1_data.spatial_resolution:
    if l1_data.spatial_resolution <= 1.5:
        one_meter_visual_coverage_pct = 100.0
        strict_one_meter_candidate_pct = 100.0
```

---

## 5. Verification & Test Plan

### Automated Tests
1. **Fallback Path Test:**
   - Force orchestrator terminal fallback branch in `orchestrator_v2/runner.py`.
   - Assert `NameError` is NOT raised.
   - Assert fallback output has valid ISO timestamp.
2. **Experimental Display Trace Test:**
   - Invoke `run_layer10_sire` with `enable_display_trace=True`.
   - Assert execution completes without raising `NameError`.

---

## 6. Progress Tracking Checklist
- [ ] Undefined `ts` fixed in `orchestrator_v2/runner.py`.
- [ ] Undefined `one_meter_visual_coverage_pct` and `strict_one_meter_candidate_pct` fixed in `layer10_sire/runner.py`.
- [ ] AST static validation confirms 0 remaining NameErrors in both files.
- [ ] Regression tests written and passing.

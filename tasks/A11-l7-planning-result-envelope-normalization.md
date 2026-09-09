# Task A11: Layer 7 Double-Result Wrapping Envelope Mismatch

## 1. Finding Overview
* **Finding ID:** A11
* **Severity:** **P1 — Contract Envelope Mismatch & Downstream Crash Risk**
* **Component:** Layer 7 Planning Runner & Orchestrator Runner
* **Primary Target Files:**
  - [`services/agribrain/layer7_planning/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/runner.py) (lines 794–800)
  - [`services/agribrain/orchestrator_v2/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/runner.py) (lines 3201–3218)

---

## 2. Technical Analysis & Code Audit

### The Code Flaw
In `services/agribrain/layer7_planning/runner.py`, lines 794–799:
```python
return LayerResult(
    layer_id="L7",
    status="SUCCESS",  # Non-standard string status!
    output=l7_output,
    run_id=run_id,
)
```
In `services/agribrain/orchestrator_v2/runner.py`, `_safe_run` wraps all runner calls in a `LayerResult`:
```python
output = spec.runner(*args)
status, structured_errors = _structured_output_status(output)
...
return LayerResult(
    layer_id=lid.value,
    status=status,
    output=output,     # <-- DEFECT: output is ALREADY a LayerResult!
    run_id=...,
    errors=structured_errors,
)
```

### Reproducing Probe:
1. `_safe_run(LayerId.L7, ...)` executes `run_layer7_planning`.
2. `run_layer7_planning` returns a `LayerResult` containing `l7_output`.
3. `_safe_run` wraps that return value into an outer `LayerResult`:
   ```python
   l7_res = LayerResult(
       layer_id="L7",
       status=LayerStatus.OK,
       output=LayerResult(          # <-- NESTED INNER WRAPPER!
           layer_id="L7",
           status="SUCCESS",
           output=Layer7Output(...) # Actual data buried 2 levels deep
       )
   )
   ```
4. Any orchestrator or downstream caller attempting `l7_res.output.chosen_plan` or `l7_res.output.execution_plan` raises:
   `AttributeError: 'LayerResult' object has no attribute 'chosen_plan'`.
5. If an error occurs inside L7 and returns degraded status, `_safe_run` unwraps the type incorrectly, reducing the rich failure description to a generic message.

---

## 3. Agronomical & Systemic Impact
- **Orchestration Failure in Planning Profile:** Calling the orchestrator with `intent="PLANNING"` crashes or fails to expose the calculated crop rotation DAG and economic risk cards.
- **Contract Ambiguity:** Mixing string `"SUCCESS"` with Enum `LayerStatus.OK` breaks status normalization across the system.

---

## 4. Implementation Plan

### Step 1: Normalize Layer 7 Runner Return Type
Align Layer 7 with the standard contract followed by L1, L2, L3, L4, L5, L6, L8:
**A layer runner must return its typed domain output payload (`Layer7Output`), NOT a `LayerResult` envelope.**
In `services/agribrain/layer7_planning/runner.py`, lines 794–800:
```python
# REMOVE the outer LayerResult wrapping
# Return Layer7Output directly to caller
return l7_output
```

### Step 2: Handle Defensive Unwrapping in `_safe_run`
In `services/agribrain/orchestrator_v2/runner.py::_safe_run`:
Add a defensive normalization guard so that if any legacy runner returns a `LayerResult`, it unwraps it cleanly rather than double-nesting:
```python
output = spec.runner(*args)

# Defensive unwrap if runner erroneously returned a LayerResult
inner_status = None
inner_errors = []
if isinstance(output, LayerResult):
    inner_status = output.status
    inner_errors = output.errors
    output = output.output

status, structured_errors = _structured_output_status(output)
if inner_status and inner_status != LayerStatus.OK:
    status = inner_status
structured_errors.extend(inner_errors)
```

---

## 5. Verification & Test Plan

### Automated Regression Tests
Create `tests/test_a11_l7_envelope.py`:
1. **Direct Runner Test:**
   - Execute `run_layer7_planning(...)`.
   - Assert `isinstance(result, Layer7Output)`.
   - Assert `hasattr(result, "chosen_plan")`.
2. **Orchestrator `_safe_run` Test:**
   - Execute `_safe_run(LayerId.L7, ...)`.
   - Assert `isinstance(l7_res, LayerResult)`.
   - Assert `isinstance(l7_res.output, Layer7Output)` (NOT `LayerResult`).
   - Assert `l7_res.output.chosen_plan is not None`.

---

## 6. Progress Tracking Checklist
- [ ] `run_layer7_planning` modified to return `Layer7Output` directly.
- [ ] String `"SUCCESS"` replaced with canonical status handling.
- [ ] Defensive unwrapping added to `_safe_run` in `orchestrator_v2/runner.py`.
- [ ] Planning intent pipeline tested end-to-end.
- [ ] Automated tests passing.

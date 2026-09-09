# Task A12: Global Health Metric Masks Scientific Degradation

## 1. Finding Overview
* **Finding ID:** A12
* **Severity:** **P0 — Health Falsification & Silent Failure Masking**
* **Component:** Orchestrator V2 (Status Extractor & Global Gating)
* **Primary Target Files:**
  - [`services/agribrain/orchestrator_v2/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/runner.py) (lines 3150–3186)
  - [`services/agribrain/orchestrator_v2/gating.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/gating.py) (lines 125–158)

---

## 2. Technical Analysis & Code Audit

### Defect 1: `_structured_output_status` Blind to `quality_metrics`
In `services/agribrain/orchestrator_v2/runner.py`, lines 3150–3175:
```python
def _structured_output_status(output) -> tuple[LayerStatus, list[str]]:
    candidates = [
        getattr(output, "status", None),
        getattr(output, "degradation_mode", None),
        provenance.get("status"),
        provenance.get("degradation_mode"),
    ]
    quality = getattr(output, "quality_report", None) # <-- Only looks for quality_report!
```
- Most modern layers (L7, L3, L4, L8) do not name their container `quality_report`; they use `quality_metrics` (e.g. `QualityMetricsL7`).
- If an engine sets `decision_reliability = 0.0`, `degradation_mode = "DATA_GAP"`, or `missing_drivers = ["NO_WEATHER", "NO_SAR"]` inside `quality_metrics`, `_structured_output_status` completely ignores it.
- **Probe Result:** An output with zero decision reliability and unusable diagnostics was classified by `_safe_run` as **`LayerStatus.OK`**.

---

### Defect 2: Global Quality Evaluator Ignores Missing Expected Layers
In `services/agribrain/orchestrator_v2/gating.py`, lines 125–144:
```python
kw = {
    LayerId.L1: 0.25, LayerId.L2: 0.20, LayerId.L3: 0.25,
    LayerId.L4: 0.15, LayerId.L5: 0.10, LayerId.L6: 0.05
    # L7, L8, L9, L10 are NOT in the weights dictionary at all!
}
for lid, weight in kw.items():
    if lid not in results:
        continue # <-- Silently drops missing layers from denominator!
    ...
```
1. **Downstream Layers Excluded:** If the user requested full prescriptive planning (`intent="PLANNING"` or `"FULL"`), failure or absence of L7, L8, L9, or L10 has **zero impact** on the global quality score.
2. **Dynamic Denominator Re-normalization:** If L3, L4, and L5 completely fail to run or are omitted, `continue` simply skips their weights. If only L1 ran and returned `OK`, the global quality score evaluates to:
   $$\text{Score} = \frac{0.25 \times 1.0}{0.25} = \mathbf{1.0\ (100\%\ Healthy)}$$
   An execution that failed to run 80% of required layers is marked completely healthy.

---

## 3. Agronomical & Systemic Impact
- **False Green Dashboard:** Farm managers see an overall "Platform Health: 100% OK" badge, while in reality the prescriptive optimizer crashed and the diagnostic layer failed to run.
- **Unreliable Autonomous Decisions:** Action governance gates check `global_quality > 0.70` before executing autonomous sprays or irrigation. Flawed scoring allows ungrounded actions to pass through safety barriers.

---

## 4. Implementation Plan

### Step 1: Inspect `quality_metrics` and Object-Form Provenance
In `services/agribrain/orchestrator_v2/runner.py`:
- Check both `quality_report` and `quality_metrics`.
- Handle object-form provenance (dataclasses and Pydantic models):
```python
def _structured_output_status(output) -> tuple[LayerStatus, list[str]]:
    if output is None:
        return LayerStatus.DEGRADED, ["structured_output_missing"]

    candidates = [
        getattr(output, "status", None),
        getattr(output, "degradation_mode", None),
    ]

    # Handle provenance whether dict or object
    prov = getattr(output, "provenance", None)
    if prov:
        if isinstance(prov, dict):
            candidates.extend([prov.get("status"), prov.get("degradation_mode")])
        else:
            candidates.extend([getattr(prov, "status", None), getattr(prov, "degradation_mode", None)])

    # Check both quality_report and quality_metrics
    qm = getattr(output, "quality_metrics", None) or getattr(output, "quality_report", None)
    if qm is not None:
        candidates.extend([
            getattr(qm, "status", None),
            getattr(qm, "degradation_mode", None),
        ])
        reliability = getattr(qm, "decision_reliability", None)
        if reliability is not None and isinstance(reliability, (int, float)) and reliability < 0.50:
            return LayerStatus.DEGRADED, [f"low_decision_reliability_{reliability:.2f}"]

    # Standard normalization checks ...
```

### Step 2: Bind Global Quality to Expected Execution Profile
In `services/agribrain/orchestrator_v2/gating.py`:
- Update `evaluate_global_quality` to take `expected_profile: List[LayerId]`:
```python
def evaluate_global_quality(
    results: Dict[LayerId, LayerResult],
    expected_profile: Optional[List[LayerId]] = None,
    ...
) -> tuple[float, Set[GlobalDegradation], List[str]]:
    # Define comprehensive weights based on profile
    profile = expected_profile or [LayerId.L1, LayerId.L2, LayerId.L3, LayerId.L4, LayerId.L5, LayerId.L6]
    
    total_expected_weight = 0.0
    weighted_score = 0.0

    for lid in profile:
        weight = LAYER_WEIGHTS.get(lid, 0.10)
        total_expected_weight += weight
        
        if lid not in results or results[lid].status == LayerStatus.FAILED:
            # Missing or failed expected layer gets 0 score
            errors.append(f"Expected layer {lid.value} failed or missing")
            modes.add(GlobalDegradation.CRITICAL_FAILURE)
            continue
            
        res = results[lid]
        # Evaluate layer score taking into account internal reliability
        ...
        weighted_score += layer_score * weight

    final_score = weighted_score / max(1e-5, total_expected_weight)
    return final_score, modes, errors
```

---

## 5. Verification & Test Plan

### Automated Tests
1. **Low Reliability Degradation Test:**
   - Create mock output with `quality_metrics.decision_reliability = 0.30`.
   - Call `_structured_output_status(output)`.
   - Assert returns `(LayerStatus.DEGRADED, ["low_decision_reliability_0.30"])`.
2. **Missing Layer Penalty Test:**
   - Expected profile `[L1, L2, L3, L4]`.
   - Pass `results = {L1: LayerResult(status=LayerStatus.OK)}`.
   - Assert `final_score < 0.35` (NOT 1.0).
   - Assert `GlobalDegradation.CRITICAL_FAILURE` in modes.

---

## 6. Progress Tracking Checklist
- [ ] `_structured_output_status` updated to inspect `quality_metrics` and `decision_reliability`.
- [ ] Object-form provenance inspection supported.
- [ ] `evaluate_global_quality` updated to accept `expected_profile`.
- [ ] Omission of expected layers penalized in global score.
- [ ] Automated quality gating tests written and passing.

# Layer 3 Audit: Decision Intelligence (layer3_decision)

## 1. Executive Summary & Verification Status
Layer 3 (Decision) is responsible for interpreting vegetation and environmental stress inputs to synthesize diagnostic recommendations and build acyclic execution DAG plans.
* **Code Integrity:** High. Zero-defect decision and policy gating.
* **Test Status:** Verified. Acyclicity and policy gates verified through regression testing.
* **Typing Checks:** Clean compile. Valid schemas for the DAG structure.

---

## 2. Granular Engine Inventory & Mapping
1. **DecisionIntelligenceEngine** ([runner.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)): Coordinates execution of inputs, diagnoses, policies, DAG building, and invariants checks.
2. **DiagnosisEngine** ([diagnosis/inference.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/diagnosis/inference.py)): Translates biophysical states into candidate diagnoses using log-odds scoring.
3. **PolicyEngine** ([policy/policies.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/policy/policies.py)): Applies regional, seasonal, and environmental compliance gates.
4. **ExecutionPlan Builder** (within [runner.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_decision/runner.py)): Assembles verification and intervention tasks into a deterministic DAG.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - `Layer3InputContext` from Layer 2.
  - `PlotContext` detailing crop and soil properties.
  - Weather forecast data envelopes.
* **Outputs Generated:**
  - `DecisionOutput` detailing active diagnoses, recommendations, DAG execution plans, and quality scores.

---

## 4. Key Mathematical Formulations & Rules

### A. Multi-Hypothesis Log-Odds Diagnostics
Diagnoses are evaluated using a log-odds scoring mechanism over active biophysical evidence features:
$$\ln O(\text{Diagnosis}) = \ln O_{prior} + \sum_i w_i \cdot \text{Score}(E_i)$$
Where $w_i$ represents evidence contribution weights.

### B. The 10 Hard Prohibitions
Execution checks strictly enforce 10 rules before outputs are released:
1. `no_diagnosis_without_evidence`: Diagnosis probability requires $>0.1$ trace representation.
2. `no_intervention_without_diagnosis`: Intervene tasks must link to an active diagnosis.
3. `no_action_above_confidence_ceiling`: Recommendation confidence is bounded by data health ceilings.
4. `no_blocked_action_allowed`: Allowed recommendations cannot carry a blocked reason.
5. `probability_bounds`: All diagnosis probabilities must belong to $[0.0, 1.0]$.
6. `severity_bounds`: All diagnosis severities must belong to $[0.0, 1.0]$.
7. `confidence_bounds`: All diagnosis confidences must belong to $[0.0, 1.0]$.
8. `execution_plan_acyclic`: Validates that the task execution plan contains zero cycles.
9. `lineage_complete`: Asserts the presence of parent `l2_run_id` references.
10. `content_hash_deterministic`: Ensures deterministic execution reproducibility.

### C. Execution Plan DAG Ordering
Task nodes are mapped such that diagnostic validation occurs prior to action:
$$\text{Task}_{\text{VERIFY}} \to \text{Task}_{\text{INTERVENE}}$$

---

## 5. Audit Recommendations
1. **Dynamic Policy Updates:** Regularly synchronize local compliance policies in `PolicyEngine` with regional conservation updates.
2. **Proactive Frost Warnings:** Refine thermal diagnosis logic to raise alert urgencies earlier in the forecast timeline.

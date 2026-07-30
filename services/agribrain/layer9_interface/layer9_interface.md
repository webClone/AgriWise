# Layer 9 Audit: Cognitive Interface (layer9_interface)

## 1. Executive Summary & Verification Status
Layer 9 (Interface) is the cognitive LLM gateway and user-facing dialog manager of the AgriBrain system. It handles intent routing, contextual pronoun resolution, hallucination validation, task manager synchronization, and prospect-framed messaging.
* **Code Integrity:** High. Implements a robust 15-engine pipeline.
* **Test Status:** Context assembly, memory threads, and LLM intents are fully validated.
* **Safety Gate:** Enforced by the `HallucinationGuard` and policy-invariant compliances.

---

## 2. Granular Engine Inventory & Mapping (15 Engines)
The cognitive pipeline routes queries through 15 active engines:

### A. Context & Memory Assembly
1. **ContextAssembly** ([engines/context_assembly.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/context_assembly.py)): Aggregates outputs from Layers 1 to 8 into unified text contexts.
2. **IntentRouter** ([engines/intent_router.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/intent_router.py)): Classifies user query intents (overview, diagnose, report, compare, etc.).
3. **ConversationMemory** ([engines/conversation_memory.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/conversation_memory.py)): Restores past turns to resolve pronouns (anaphora grounding).

### B. Parallel Background Workers
4. **AlertEngine** ([engines/alert_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/alert_engine.py)): Generates prioritized alerts.
5. **TaskManager** ([engines/task_manager.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/task_manager.py)): Synchronizes execution checklists.
6. **DataRequestEngine** ([engines/data_request.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/data_request.py)): Identifies telemetry gaps that need manual measurements.
7. **ReminderEngine** ([engines/reminder_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/reminder_engine.py)): Tracks task deadlines.

### C. Intent-Based Content Generators
8. **AdvisoryEngine** ([engines/advisory_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/advisory_engine.py)): Formulates crop management summaries.
9. **ReportEngine** ([engines/report_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/report_engine.py)): Generates seasonal summaries.
10. **SpatialNarrator** ([engines/spatial_narrator.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/spatial_narrator.py)): Translates raster maps into spatial text cards.
11. **CoachEngine** ([engines/coach_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/coach_engine.py)): Formulates farming tips.
12. **QAEngine** ([engines/qa_engine.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/qa_engine.py)): Resolves generic agronomic questions.
13. **WhatIfSandbox** ([engines/what_if_sandbox.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/what_if_sandbox.py)): Simulates management scenarios when users ask "what if".

### D. Governance & Quality Gates
14. **HallucinationGuard** ([hallucination_guard.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/hallucination_guard.py)): Screens LLM statements against actual upstream layer data.
15. **PolicyEnforcer** ([engines/policy_enforcer.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/policy_enforcer.py)): Validates safety limits and outputs.
16. **ResponseQualityEngine** ([engines/response_quality.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/response_quality.py)): Scores responses for clarity, safety, and correctness.
17. **TelemetryCollector** ([engines/telemetry_collector.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/telemetry_collector.py)): Records API latencies.
18. **FeedbackLearningEngine** ([engines/feedback_learning.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer9_interface/engines/feedback_learning.py)): Analyzes conversation histories to calibrate user expertise profiles.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - Heterogeneous layer responses (L1 to L8, L10).
  - User query strings.
  - Persona configs (Farmer, Agronomist, Manager) and experience levels (Novice, Intermediate, Expert).
* **Outputs Generated:**
  - `InterfaceOutput` containing summarized responses, active task lists, data requests, and alerts.

---

## 4. Key Mathematical Formulations

### A. Contextual Pronoun Resolution
Resolves vague references using conversation histories before intent routing:
$$\text{Resolved Query} = f_{\text{MemoryGrounding}}(\text{Query}_{current}, \text{SessionHistory})$$

### B. Hallucination Screening & Validation Rules
The `HallucinationGuard` extracts generated claims from the text and performs five validations:
1. **Numeric Values Proximity check:**
   Every number matching agricultural units (`kg`, `mm`, `L`, `t`, `ha`, `%`, `°`) must correspond to a number in the upstream layer output or satisfy a $10\%$ relative tolerance constraint:
   $$\min_{u \in \mathcal{U}_{numbers}} \frac{|v - u|}{\max(|u|, 0.01)} < 0.10$$
   If this is violated, the claim is flagged as a hallucination.
2. **Scheduled Dates Validation:**
   Dates mentioned in the response must exist in the scheduled list of intervention events:
   $$\text{Date} \in \mathcal{U}_{dates}$$
3. **Management Zones Validation:**
   Zone IDs referenced in the generated text must match active zones in the zone plan:
   $$\text{Zone} \in \mathcal{U}_{zones}$$
4. **Action Gating Check:**
   Actions that have been blocked due to safety/environmental reasons must not be suggested or recommended:
   $$\text{Action} \notin \mathcal{U}_{blocked\_actions}$$
5. **Physical / Biophysical Safety Constraints:**
   - **Urea Limit Check:** Fertilizer rates matching `urea` / `nitrogen` must not exceed $200.0\text{ kg/ha}$. If violated, the rate is replaced with `200 kg/ha`.
   - **Irrigation Anoxia Warning Check:** If soil moisture is high ($\ge 38.0\%$, field capacity saturation) and the response recommends an irrigation event $> 25.0\text{ mm}$, it is flagged and replaced with `15 mm` to protect root systems from suffocation.

### C. Knowledge Graph Fallback (Offline Mode)
When third-party LLM APIs are offline, Layer 9 degrades gracefully to a local rule-based system using structured diagnostic lookup maps:
$$\text{Response}_{fallback} = \text{Lookup}(\text{Crop}) \cup \text{Rule}(\text{Stress}) \cup \mathcal{A}_{fallback}$$
Where $\mathcal{A}_{fallback}$ provides crop-specific safety cards for irrigation and nutrient management based on GDD/BBCH stage.

---

## 5. Audit Recommendations
1. **Dynamic Hallucination Bounds:** Allow the HallucinationGuard to scale error margins ($\epsilon$) based on sensor reliability.
2. **Offline Mode Expansion:** Enrich the local fallback knowledge graph with pest/disease diagnostics.

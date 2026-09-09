# Work Package 12: Make System Ready for Omega and the World Model

## 1. Executive Summary & Objective
The long-term vision of AgriBrain encompasses an autonomous world model (learned latent transitions, prospective counterfactual simulation) and an active scientific discovery engine (Omega: hypothesis generation, surprise tracking, automated experiment design).
Currently, the codebase contains valuable early scaffolding:
- `services/agribrain/world_model/`: Contains dataclass definitions for `BeliefStateSnapshot`, `ForecastArtifact`, and `ForecastEvaluation`, but they do not function as the operational shared state and forecast archive.
- `services/agribrain/mesia/omega/experiment_proposer.py`: Implements heuristic surprise calculations, multiplies surprise by arbitrary constants to compute "information gain", and hardcodes `regulatory_safety_approved = True` without a governance decision.

Attempting to build a full learned world model or active Omega engine on top of these unanchored interfaces would inherit all upstream contradictions (unit errors, false timestamps, missing bitemporality).
Work Package 12 implements the essential operational prerequisites: bitemporal history extraction, an immutable forecast archive, separated intervention histories, and strict isolation between research hypotheses and operational permissions.

---

## 2. Affected Subsystems & Source References
- **World Model Contracts**: [`services/agribrain/world_model/contracts.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/contracts.py).
- **Canonical Worldline**: [`services/agribrain/world_model/canonical_worldline.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/canonical_worldline.py).
- **Omega Research Scaffolding**: [`services/agribrain/mesia/omega/experiment_proposer.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/omega/experiment_proposer.py).
- **Forecast Evaluation Archive**: [`services/agribrain/world_model/forecast_archive.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/world_model/forecast_archive.py).

---

## 3. The 10 Foundational World-Model Prerequisites

| Foundation | Concrete Implementation Requirement |
| :--- | :--- |
| **1. Immutable Evidence** | Native artifact identity, transformation lineage, SI units, spatial support, GUM uncertainty, and admissible roles. |
| **2. Canonical Belief** | Exact ASMAE state snapshot, hypothesis distribution, posterior covariance, geometry/lattice version, and knowledge cutoff. |
| **3. Three Distinct Graphs** | 1. Transformation dependency graph (computational DAG).<br>2. Scientific evidence graph (observational support).<br>3. Worldline event graph (temporal state progression). |
| **4. Bitemporal History** | Explicit distinction between **Event Time** (when the physical phenomenon occurred) and **Knowledge Time** (when the system recorded it). |
| **5. Shared Spatial Lattice** | Persistent cell/zone/stratum identities and versioned spatial coordinate mappings across ASMAE, MESIA, and SIRE. |
| **6. Intervention Separation** | Proposed interventions (L7), authorized prescriptions (L8), applied actions (telemetry), and verified outcomes (sensors) stored as distinct events. |
| **7. Forecast Archive** | Immutable issue-time predictions stored at $t_{\text{issue}}$ and evaluated against future observations at $t_{\text{target}}$ without rewriting historical forecasts. |
| **8. Measurement Policy** | Audit records detailing why an observation was acquired (scheduled routine, farmer manual entry, or model-induced exploration trigger). |
| **9. Model/Operator Registry**| Immutable tracking of model weights, forward operator calibrations, validity domains, and cryptographic revocation status. |
| **10. Promotion Service** | Independent governance layer controlling authority transitions from research/shadow outputs to operational decisions. |

---

## 4. Implementation Specification

### 4.1 Step 1: Bitemporal Historical Window Extraction
Create `services/agribrain/world_model/historical_extractor.py`:
```python
class BitemporalWorldlineExtractor:
    """Extracts training windows as they existed at a specific historical point in knowledge time.

    Guarantees zero data leakage from future observations into historical training sets.
    """
    def extract_training_window(
        self,
        plot_id: str,
        start_event_time: datetime,
        end_event_time: datetime,
        as_of_knowledge_time: datetime,
    ) -> TrainingTrajectoryWindow:
        # 1. Load all worldline events where event_timestamp is in [start, end]
        # 2. Filter out any event whose committed_at > as_of_knowledge_time
        # 3. For any superseded evidence, restore the version active at as_of_knowledge_time
        return window
```

### 4.2 Step 2: Implement the Immutable Forecast Archive
Create `services/agribrain/world_model/forecast_archive.py`:
1. When L3, ASMAE, or L7 generates a forward prediction (e.g. 7-day soil moisture or crop yield), publish an immutable `ForecastRecord`:
   - `forecast_id`: Content hash of issue time, target horizon, model version, and predicted distribution.
   - `issued_at_knowledge_time`: Exact timestamp when forecast was committed.
   - `target_epoch`: Exact future timestamp.
   - `predicted_quantiles`: $(p_{10}, p_{50}, p_{90})$ or mean + covariance.
2. In background evaluation, when the actual observation for `target_epoch` arrives, compute and store a `ForecastEvaluationRecord` (Continuous Ranked Probability Score, RMSE, sharpness) linking the forecast to the verifying evidence.

### 4.3 Step 3: Contain Omega Experiment Proposals
1. In `services/agribrain/mesia/omega/experiment_proposer.py`:
   - Remove `regulatory_safety_approved = True`.
   - Reclassify experiment proposals as `AuthorityScope.RESEARCH_ONLY`.
   - Prohibit Omega proposals from triggering automated RF chirps or machinery actions without explicit human agronomist approval and safety court verification.

---

## 5. Verification & Completion Criteria
- **Zero Future Leakage Test**: Extracting a worldline window `as_of_knowledge_time = 2026-06-01` completely excludes satellite scenes or probe readings acquired on 2026-06-02, even if they describe events that occurred on 2026-05-30.
- **Shadow Forecast Invariant**: A shadow world-model forecast can be evaluated and stored in the forecast archive without altering the operational belief state or affecting L8 prescriptions.
- **Omega Boundary Invariant**: Omega experiment proposals never receive `PRESCRIPTION_DRIVER` or `MACHINE_EXECUTION` authority receipts.

---

## 6. Monograph & Defect Task Traceability
- **Monograph Findings**: Finding #22 (Canonical evidence graph), Finding #24 (World state binding), Finding #33 (Worldline persistence), Finding #34 (Background jobs), Monograph Section "Omega helpers and World-model package".
- **Phase Tasks**: [P05.1-omega-readonly-surprise-and-experiment-proposals.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P05.1-omega-readonly-surprise-and-experiment-proposals.md), [P05.2-omega-offline-evaluation-and-model-registry.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P05.2-omega-offline-evaluation-and-model-registry.md), [P06.1-world-model-state-observation-action-contracts.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P06.1-world-model-state-observation-action-contracts.md), [P06.2-world-model-calibrated-forecasts-evaluation.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P06.2-world-model-calibrated-forecasts-evaluation.md).

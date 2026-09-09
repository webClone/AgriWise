# Work Package 09: Rebuild Diagnostic Promotion and Action Flow

## 1. Executive Summary & Objective
The operational governance and action decision pipeline contains the most severe architectural block in AgriBrain:
1. **Deterministic Prescription Deadlock (Finding #1)**: In `orchestrator_v2/runner.py`, `_build_diagnostic_integration()` creates an `AuthorityVector` permitting only `visualization_allowed` and `diagnosis_allowed`. `diagnostic_integration/adapters.py` deliberately strips all other permissions. However, the orchestrator requests `InfluenceUse.PRESCRIPTION_DRIVER` before allowing L6, L7, and L8 to proceed. `influence.py` excludes every contribution lacking this permission. The manifest is deterministically empty, and downstream action planning is permanently blocked.
2. **Permission Reconstruction from Output Presence (Finding #2)**: Diagnosis permission is checked via `evidence_count != 0` and `health_status != "unusable"`, which evaluate to `True` when metadata is `None`, granting diagnostic permission to ungrounded data.
3. **Intent Branch Contradictions (Finding #3)**: The `DECISION` route skips L7 and L8, returning an empty plan. The `PLANNING` route stops after L7 without L8 policy evaluation.
4. **Decision Sequence Inversion (Finding #4)**: L6 (outcomes/feasibility) is executed before L7 (planning) and L8 (prescription), and `Layer8Input` has no parameter to accept L7 candidate scenarios.

Work Package 09 designs and installs an explicit `DiagnosticPromotionService` between diagnostic tribunal acceptance and action eligibility, fixes intent routing, and re-sequences L6, L7, and L8 into the monograph's canonical decision flow.

---

## 2. Affected Subsystems & Source References
- **Orchestrator v2 Runner**: [`services/agribrain/orchestrator_v2/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/runner.py#L2540-L2685, #L3640-L3720).
- **Diagnostic Adapters**: [`services/agribrain/diagnostic_integration/adapters.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/diagnostic_integration/adapters.py#L75-L84).
- **Influence Builder**: [`services/agribrain/diagnostic_integration/influence.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/diagnostic_integration/influence.py#L125-L135).
- **Layer 6 Feasibility**: [`services/agribrain/layer6_outcomes/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_outcomes/).
- **Layer 7 Planning**: [`services/agribrain/layer7_planning/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer7_planning/runner.py).
- **Layer 8 Prescription Schema**: [`services/agribrain/layer8_prescriptive/schema.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/schema.py#L353-L395).

---

## 3. Root Cause & Architectural Breakdown

### 3.1 The Deterministic Authority Deadlock (Finding #1)
1. In `orchestrator_v2/runner.py:3695`:
   ```python
   authority = AuthorityVector(
       visualization_allowed=bool(l1_output),
       diagnosis_allowed=l1_usable,
   )
   # prescription_driver_allowed defaults to False
   ```
2. In `diagnostic_integration/adapters.py:75-84`:
   ```python
   def _diagnostic_authority(source: AuthorityVector) -> AuthorityVector:
       return AuthorityVector(
           visualization_allowed=source.visualization_allowed,
           diagnosis_allowed=source.diagnosis_allowed,
       )
   ```
3. In `orchestrator_v2/runner.py:2662`:
   ```python
   pre_action_diagnostic = _build_diagnostic_integration(
       results, run_id, ts_now, InfluenceUse.PRESCRIPTION_DRIVER
   )
   pre_action_manifest = pre_action_diagnostic.get("influence_manifest", {})
   pre_action_entries = pre_action_manifest.get("entries", [])
   action_manifest_allowed = bool(...)
   ```
4. In `diagnostic_integration/influence.py:128`:
   ```python
   if not authority_allows(contribution.authority, requested_use):
       continue
   ```
Because `_diagnostic_authority` deliberately ensures diagnostic layers cannot self-authorize prescription use, every contribution has `prescription_driver_allowed = False`. When `InfluenceUse.PRESCRIPTION_DRIVER` is requested, all entries are skipped. `pre_action_entries` is always `[]`. `action_manifest_allowed` evaluates to `False`. The pipeline aborts action generation!

*Why a naive fix fails*: Simply setting `prescription_driver_allowed = True` inside `runner.py:3695` destroys the scientific boundary, allowing raw, uncalibrated diagnostic hunches to command physical machinery.

### 3.2 Canonical Decision Sequence Inversion (Finding #4)
The monograph establishes the sequence:
1. **State Estimation & Diagnostic Tribunal (L0-L5)**: Form unified belief state.
2. **Resource & Equipment Feasibility (L6 Constraints)**: Determine what machinery, windows, and materials are available.
3. **Scenario Planning (L7)**: Generate candidate action scenarios conditioned on feasibility.
4. **Prescription Policy Evaluation (L8)**: Evaluate candidate scenarios under policy, safety, and economic criteria to select or abstain.
5. **Execution Serialization**: Prepare authorized machine instructions.

In the current code:
- L6 runs before L7, consuming an empty execution plan.
- L7 generates heuristics, but `Layer8Input` has no field for L7 candidate scenarios.
- L8 evaluates raw diagnoses rather than L7's candidate interventions.

---

## 4. Implementation Specification

### 4.1 Step 1: Implement `DiagnosticPromotionService`
Create `services/agribrain/diagnostic_integration/promotion_service.py`:
```python
class DiagnosticPromotionService:
    """Evaluates accepted diagnostic tribunal contributions and policy rules

    to promote eligible diagnoses to PRESCRIPTION_DRIVER capability receipts.
    Diagnostic adapters themselves remain unable to self-authorize.
    """
    def promote_to_prescription_eligibility(
        self,
        tribunal_result: Dict[str, Any],
        policy_snapshot: Dict[str, Any],
        evidence_receipts: Dict[str, Any],
    ) -> List[PromotedContribution]:
        promoted = []
        for contrib in tribunal_result.get("accepted_contributions", []):
            # Check 1: Target variable is within policy-approved prescriptive scope
            if not self._variable_in_policy_scope(contrib.target_variable, policy_snapshot):
                continue
            # Check 2: Minimum epistemic confidence and evidence support
            if contrib.confidence < policy_snapshot.get("min_prescription_confidence", 0.75):
                continue
            # Check 3: State variable identifiability class is IDENTIFIED
            if contrib.identifiability != "IDENTIFIED":
                continue
            # Check 4: Valid, unexpired calibration certificate exists
            if not self._has_valid_calibration(contrib):
                continue

            # Grant elevated AuthorityVector through promotion authority
            elevated_authority = AuthorityVector(
                visualization_allowed=True,
                diagnosis_allowed=True,
                prescription_driver_allowed=True,
            )
            promoted.append(contrib.with_authority(elevated_authority))
        return promoted
```

### 4.2 Step 2: Re-Sequence L6, L7, and L8 Execution
1. In `orchestrator_v2/runner.py`, update the main pipeline sequence:
   - **Step A**: Run L0 through L5.
   - **Step B**: Run diagnostic integration tribunal (`InfluenceUse.DIAGNOSIS`).
   - **Step C**: Execute `DiagnosticPromotionService.promote_to_prescription_eligibility(...)` to construct the authorized `PRESCRIPTION_DRIVER` manifest.
   - **Step D**: Run L6 in **Feasibility Mode**: generates machine/labor/weather constraints.
   - **Step E**: Run L7 **Planning**: accepts diagnostic belief + L6 feasibility constraints, outputting `List[ScenarioRef]`.
   - **Step F**: Run L8 **Prescription**: accepts L7's `candidate_scenarios` and selects the optimal policy-compliant action, returning `ActionAuthorization`.
2. Update `Layer8Input` in `layer8_prescriptive/schema.py` to add:
   ```python
   candidate_scenarios: List[ScenarioRef] = field(default_factory=list)
   feasibility_constraints: Dict[str, Any] = field(default_factory=dict)
   ```

### 4.3 Step 3: Align Intent Routing Capabilities
1. Define clear capabilities per intent:
   - `Intent.DIAGNOSIS`: Runs L0-L5 + Diagnostic Tribunal. Returns structured explanations; execution plan is explicitly declared omitted (`intent_scope="diagnostic_only"`).
   - `Intent.PLANNING`: Runs L0-L5 + Tribunal + L6 Feasibility + L7 Planning. Returns candidate scenarios without committing to an authorized prescription.
   - `Intent.DECISION` / `Intent.PRESCRIPTION`: Runs the full pipeline through L8, producing authorized actions or explicit actionable abstention receipts.

---

## 5. Verification & Completion Criteria
- **Deadlock Resolution Test**: A test scenario with valid diagnostic inputs and high confidence successfully promotes contributions, produces non-empty manifest entries, and generates an authorized L8 action.
- **Fail-Closed Uncalibrated Test**: When diagnostic confidence is low ($0.4$) or calibration is unverified, `DiagnosticPromotionService` rejects promotion, manifest entries remain empty, and L8 returns an explicit `PrescriptionAbstentionReceipt`.
- **Decision Sequence Invariant**: L7 scenarios are directly inspected and chosen by L8; L6 feasibility constraints strictly bound L7 plan generation.

---

## 6. Monograph & Defect Task Traceability
- **Monograph Findings**: Finding #1 (Prescription authority deadlock), Finding #2 (Diagnosis permission from receipts), Finding #3 (Intent branch consistency), Finding #4 (Decision sequence inversion), Finding #31 (L7 scenario estimation).
- **Defect Tasks**: [A11-l7-planning-result-envelope-normalization.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A11-l7-planning-result-envelope-normalization.md), [A13-l8-prescriptive-weather-constraints.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A13-l8-prescriptive-weather-constraints.md).
- **Phase Tasks**: [P04.1-enforce-per-action-weather-constraints.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P04.1-enforce-per-action-weather-constraints.md), [P04.3-demonstrate-operational-readiness.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P04.3-demonstrate-operational-readiness.md).

---

## 7. Execution Status & Verification Report

### 7.1 Implemented Changes
1. **Diagnostic Promotion Service (Finding #1)**:
   - File: [`services/agribrain/diagnostic_integration/promotion_service.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/diagnostic_integration/promotion_service.py)
   - Created `DiagnosticPromotionService` and `PromotionResult` to act as the explicit, policy-governed bridge between diagnostic tribunal acceptance and prescriptive execution.
   - Enforces 4 promotion gates: minimum epistemic confidence ($\ge 0.70$ or policy-defined), identifiability class (`IDENTIFIED` or `PARTIALLY_IDENTIFIED`), clean lineage without blocking reasons, and policy scope compliance.
   - For eligible contributions, derives elevated copies with `AuthorityVector(visualization_allowed=True, diagnosis_allowed=True, prescription_driver_allowed=True)`.
   - Exported in [`services/agribrain/diagnostic_integration/__init__.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/diagnostic_integration/__init__.py).

2. **Permission Reconstruction from Output Presence Fixed (Finding #2)**:
   - File: [`services/agribrain/orchestrator_v2/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/runner.py#L3744-L3755)
   - Replaced loose truthiness check with explicit type-checked validation: `evidence_count` requires `isinstance(evidence_count, (int, float)) and evidence_count > 0`, and `health_status` requires string presence not in `("unusable", "unknown", "none", "")`.
   - Missing, `None`, or ungrounded metadata strictly evaluates to `l1_usable = False` (fail-closed).

3. **Intent Branch Contradictions Aligned (Finding #3)**:
   - File: [`services/agribrain/orchestrator_v2/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/runner.py#L2542-L2630)
   - `Intent.DIAGNOSIS`: runs L1 through L5 + Diagnostic Tribunal with `InfluenceUse.DIAGNOSIS`; skips L6, L7, and L8; returns structured artifact with `intent_scope="diagnostic_only"`.
   - `Intent.PLANNING`: runs L1 through L5 + L6 Feasibility + L7 Planning conditioned on L6 feasibility; skips L8; returns structured artifact with `intent_scope="planning_only"`.
   - `Intent.DECISION` (and default): runs the complete canonical pipeline through L8 prescriptive authorization.
   - Schema updated in [`services/agribrain/orchestrator_v2/schema.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/schema.py) with `intent_scope` on `RunMeta` and `RunArtifact`.

4. **Canonical Decision Sequence & Scenario Propagation (Finding #4)**:
   - Files: [`services/agribrain/layer8_prescriptive/schema.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer8_prescriptive/schema.py#L391-L392), [`services/agribrain/orchestrator_v2/runner.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/orchestrator_v2/runner.py#L2670-L2835)
   - Re-sequenced main pipeline: (1) L1–L5 Diagnostic Tribunal $\to$ (2) Diagnostic Promotion Service $\to$ (3) L6 Feasibility Assessment $\to$ (4) L7 Season Planning (conditioned on L6) $\to$ (5) L8 Prescriptive Intelligence.
   - Added `candidate_scenarios: List[Any]` and `feasibility_constraints: Dict[str, Any]` to `Layer8Input`.
   - In `runner.py`, candidate scenarios from `l7_res.output.options` and operational feasibility constraints from `l6_res.output` are explicitly extracted and passed into `Layer8Input`.

### 7.2 Verification Results
- **Dedicated WP09 Test Suite**: `services/agribrain/tests/test_wp09_diagnostic_promotion_and_action_flow.py` (6/6 tests passed):
  - `test_deadlock_resolution_via_promotion`: Verified that `DiagnosticPromotionService` promotes eligible diagnoses, producing non-empty manifest entries for `InfluenceUse.PRESCRIPTION_DRIVER` and unblocking action planning.
  - `test_build_diagnostic_integration_end_to_end_promotion`: Verified end-to-end promotion pipeline inside `_build_diagnostic_integration()` with audit generation.
  - `test_fail_closed_low_confidence_or_uncalibrated`: Verified fail-closed rejection and explicit exclusion reasons for low confidence, heuristic identifiability, confounded variables, and active block reasons.
  - `test_permission_reconstruction_from_none_metadata`: Verified that `None`, 0, negative, or unusable metadata does not grant diagnosis permission.
  - `test_decision_sequence_and_scenario_propagation`: Verified `Layer8Input` acceptance of L7 candidate scenarios and L6 feasibility constraints.
  - `test_intent_routing_capabilities`: Verified intent scopes (`diagnostic_only`, `planning_only`) on `RunMeta` and `RunArtifact`.
- **Subsystem Test Suites**:
  - `layer6_exec/tests`: 10/10 passed.
  - `layer7_planning/tests`: 16/16 passed.
  - `layer8_prescriptive/tests`: 13/13 passed.
  - `agribrain/tests`: 192/192 passed.
  - **Full Regression Suite**: 790/790 passed, 0 failures across all 13 subsystems.


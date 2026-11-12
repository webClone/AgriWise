# Implementation Pass Receipt & Progress Ledger Template (copy for each Pxx)
**Purpose:** prevent unjustified completion percentages and self-certified releases.

## Per-pass front matter
```yaml
pass_id: Pxx
status: NOT_STARTED # NOT_STARTED|DESIGNED|IMPLEMENTED|LOCALLY_TESTED|INDEPENDENTLY_VERIFIED|STAGED|RELEASED|HOLD
baseline_sha: null
implementation_branch: null
candidate_sha: null
pr: null
owners: []
reviewers: []
source_drift_checked_at: null
files_changed: []
scope_exclusions: []
science_interlock: "AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false"
privacy_gate: pending
scientific_gate: pending
hardware_gate: not_applicable_or_hold
ux_gate: pending
integration_gate: pending
risk_ids: []
decision: HOLD
```
## Reviewer and evidence table
| Round | Reviewer / role | Artifact | Status | Evidence SHA / file | Blocking finding |
|---|---|---|---|---|---|
| R0 Baseline | A0/owner | path inventory & verified source | pending | | |
| R1 Proposal | owner | design/ADR/patch rationale | pending | | |
| R1 Independent alternative | independent specialist | alternate proposal | pending | | |
| R2 Scientific & security | A4/A6 | role-based challenge and risk | pending | | |
| R3 Negative tests | A7 | fail-old/pass-new exact run | pending | | |
| R4 Integration/browser | A2/A8 | screenshots, traces, contracts | pending | | |
| R5 Closure | A0 | GO/HOLD signed review | pending | | |
## Percentages (separate denominators)
- **Files inventoried** = inspected files / explicit in-scope source files. Separate structural scan from deep control-flow inspection.
- **Requirements implemented** = verified requirements / all in-scope requirements (do not count 'coded' as verified).
- **Qualification checks** = independently passed acceptance gates / applicable gates; blocked/not-run counted as not passed.
- **Tool coverage** = discoverable catalog concepts (including aliases) / 94 proposed concepts.
- **Scientifically released** = validated scientific maps / candidate maps with source evidence, with counterexamples and field limitations.
No averaged overall percentage for UI/science/hardware unless a transparent weighted rubric is approved.
## Review-ready report structure
1. Exact baseline and diff with no secrets.
2. Purpose & source contracts preserved.
3. Implementation file-by-file changes, not giant unsourced claims.
4. Architecture/rationale and alternatives rejected.
5. Before/after screenshots or expected contract responses.
6. Tests and negative cases with exact commands/logs.
7. 13-state, Layer10 publication, temporal/source integrity implications.
8. Tenant/privacy and physical actuation implications.
9. Runtime performance/a11y checks.
10. Residual issues, risks, independent signoffs, GO/HOLD/rollback.
## Blocking issue example
```text
Pxx-F01 | Severity P0/P1/P2 | observed in exact SHA | reproduction
Expected contract:
Actual behavior:
Root cause verified:
Patch:
Independent negative test:
Review source:
Closure:
```
## Approval/reconciliation
Agent roles do not imply actual independent reviewers unless distinct reviewers executed their assigned work. Mark tests and signoffs NOT_RUN until real evidence exists. If user changes direction, revise design documents while keeping accepted architecture/monograph unchanged; implementation deviations require ADR and test updates.

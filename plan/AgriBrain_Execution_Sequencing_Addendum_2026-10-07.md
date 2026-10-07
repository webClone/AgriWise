# Dependency-complete execution addendum

Date: 7 October 2026. Applies to the exact 52-package repair plan delivered on 6 October, baseline `26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`. Package IDs, source targets, R3 mappings, completion criteria and estimates are unchanged. This addendum corrects delivery scheduling; it does not report completed repository fixes.

## 1. How to use the schedule

The rows below form one valid full-acceptance order. Within a row, the listed order respects prerequisites. Independent implementation can overlap as soon as its own prerequisites are satisfied; these rows are not a requirement to serialize every engineer or delay urgent actuator protections until all earlier rows finish. F16-F19 should begin after the relevant F01 boundary and proceed in their own execution lane.

A package is complete only when its full criteria and integrations pass. An early slice is a smaller ticket within its parent package, receives its own limited acceptance, and is counted once in the parent's effort. Early imports or local-name fixes do not close the full package.

## 2. Early slices before full acceptance

| Parent | Early scope | Full acceptance prerequisite and placement |
|---|---|---|
| F35 | Isolate missing optional driver import; make driver availability explicit | Durable job lifecycle after F09; full reliability stage 11 |
| F37 | Correct GaussianMixture import and establish supported startup | Full package stage 0; namespace/identity migration must also pass |
| F38 | Fix local undefined names using real input/context; reject fabricated namespace; repair exact snapshot relation | F01/F02/F09/F31/F37; full integration stage 10 |
| F39 | Reproduce and remove nonce lost updates at the actual admission boundary | F01/F09; full shared replay and telemetry persistence stage 3 |
| F40 | Resolve annotation names needed by actual schema/introspection consumers | F37/F38; complete runtime/manifest verification stage 10 |
| F32 | Dashboard errors return unavailable, preserving legitimate account zeros | Full records/calendar/scoped integration after F09 at stage 10 |

For nonce admission, a process-local lock or atomic file replacement alone cannot demonstrate multi-worker safety. If an early slice establishes only a single-process guarantee, label it accordingly and retain the distributed acceptance item. For driver restoration, do not silently promote simulation into real acquisition/execution.

## 3. Full-package acceptance order

| Stage | Packages, in prerequisite order within the row | Whole-package hours |
|---|---|---|
| 0 | F37 | 24-48 |
| 1 | F01, F02 | 48-80 |
| 2 | F03, F04 | 36-60 |
| 3 | F06, F07, F08, F09, F39 | 148-252 |
| 4 | F05, F10, F11, F12 | 100-176 |
| 5 | F13, F14, F15 | 68-124 |
| 6 | F16, F17, F18, F19 | 88-148 |
| 7 | F20, F34 | 64-104 |
| 8 | F21, F22, F23, F24 | 88-144 |
| 9 | F25, F26, F27, F28, F29 | 140-232 |
| 10 | F30, F31, F32, F33, F38, F40 | 172-296 |
| 11 | F35, F36, T11 | 168-296 |
| 12 | T01, T02, T12 | 240-420 |
| 13 | T03, T06 | 280-520 |
| 14 | T04, T05 | 240-440 |
| 15 | T08, T09 | 300-540 |
| 16 | T07, T10 | 360-660 |

Every one of the 52 packages occurs exactly once. Every declared prerequisite precedes its dependent package in this full order. No hours are added for early slices. The totals remain 1,044-1,780 correction hours and 1,520-2,760 extension hours.

F12 now completes before F13. F39 has an explicit full completion after F09. F38 and F40 have explicit full completion after F31 and F38, respectively. F32's initial dashboard slice does not imply early completion of the entire calendar/records package. T03-T10 are all placed explicitly, rather than being inferred solely from release-gate prose.

Product packages T08/T09 may advance after their own prerequisites without waiting for learned-world-model work. Reference-site recruitment, native acquisition feasibility, research protocols and Omega interface design may start early; their complete capability claims require the stated independent evidence. T12's full acceptance is not a reason to postpone data collection until the final stage.

## 4. Acceptance evidence by lane

- **Evidence lane:** F01/F02/F38 require qualified finite components, legitimate zeros, measured/scenario roles, knowledge cutoffs, real namespace and observable failure receipts.
- **Trajectory lane:** F03-F11/F39 require actual transition/analysis receipts, consistent depth support, daily-versus-sparse replay, parameter changes, cold restart, tenant scope and concurrent-writer behavior.
- **Execution lane:** F15-F20/F34 require immutable hard caps, quota checks independent of telemetry, operation ownership through physical completion, admissible stop, safe reconciliation and qualified actual exposures.
- **Learning lane:** F21-F29/F36 require frozen payloads, role-aware availability, committed forecast retrieval, no observation-filled forecast medians, explicit score missingness and independent objective/label support.
- **Application lane:** F30-F33/F38/F40 require canonical advice, context-preserving routing, actual tasks, scoped writes, exact publication relations and supported schema/startup consumers.
- **Target lane:** T01-T12 require the R3 trajectory, dataset, representation, rollout, economics, instruments, experiment, product and institutional criteria. Scientific capability does not inherit validity from a software package's passing import.

## 5. Release and merge boundaries

R0 through R4 retain their outcome-based definitions from the main plan. The stage numbers above are scheduling aids, not renamed release gates. Verify the relevant gates independently for each published capability.

PR #1 remains a partial draft proposal for F01/F02/F32. Review its exact diff and downstream behavior; no merge or cherry-pick is executed or authorized by this document. Keep the original main baseline, proposed PR and accepted implementation distinct.

For each change, record baseline, exact input fixture, expected behavior, actual downstream receipt, focused compatibility evidence and rollback approach. Before training a new target model, freeze the corrected input/target eligibility, splits, versions and independent reference criteria. Before live control, verify the operational commissioning boundary with the actual supported controller.

## 6. Sizing and responsibility

Allocate owners and slice-specific hours before calling a group a sprint. Full-package ranges cannot be silently reduced merely because an initial import fix is small. Convert engineering effort to dates only with explicit capacity and data/hardware availability; seasonal research and replication remain separate.

The schedule preserves all R3 mappings and the monograph's scientific target. It makes the implementation plan more executable without declaring current capabilities complete or rewriting the target monograph to include implementation status.

# AgriWise delivery interpretation and faster execution

Candidate: `563c6fa8a2fde2e350b4e800313d726ca5879893`, branch `feat/f36-t09-asmae-13-state-publication`. This lane reviews the plan and register, not the candidate's code acceptance. The root review owns that gate.

## What the reported progress can support

The user's “about 30%” is a useful planning estimate, but the available records do not independently verify a completion percentage. Equally, 52 open full-acceptance milestones do not mean there is no implementation. The current register is still an unpopulated tracking baseline: all 285 ticket checkboxes are open, none are done or in progress, and its proof ledger has Pending commit/reviewer/sign-off fields. Register status must be reconciled with accepted current production evidence before it measures delivery.

| Current register ticket type | Done | In progress | Open | Total |
|---|---:|---:|---:|---:|
| Numeric delivery tickets | 0 | 0 | 225 | 225 |
| Early slices | 0 | 0 | 8 | 8 |
| Full package acceptance | 0 | 0 | 52 | 52 |
| All ticket checkboxes | 0 | 0 | 285 | 285 |

The README's “285 atomic engineering tickets” should be interpreted carefully: this total already includes 52 acceptance milestones and 8 early slices; there are 225 numeric delivery tickets. The 17 dashboard cells and the lifecycle legend are not delivery tickets. Early-slice estimates are allocated from their parent packages and must not be added a second time.

The package status file present in the current tree is `plan/AgriBrain_WIP_Package_Register_52_2e1fbcb_2026-10-18.json` (blob `493bb0b142230bf3ffe6a16838e7d36d80ea110e`). Its declared reviewed commit is `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`, completed 18 October. It says 52 open / 0 closed full acceptances and explicitly disclaims an inferred completion percentage or field acceptance. Its many partial statuses are historical reporting, not a current code assessment. No newer dedicated package-status register was found in the candidate's recursive tree; the current task register is the current checkbox source.

The estimates remain 1,044–1,780 correction hours plus 1,520–2,760 extension hours = 2,564–4,540 planned engineering hours. Extension packages account for roughly 59–61% of that planned effort, so counting packages or files would distort progress. There is no accepted current effort log or reliable completed-ticket numerator. An effort-weighted completion percentage would therefore be invented. These estimates also exclude the listed compute, hardware, reference-data, seasonal-outcome and replication work, and are not remaining-hour estimates.

## Why progress feels slow, and what to change

The accepted scheduling authority already allows overlapping implementation by actual dependencies. Its 17 stages are one full-acceptance ordering, not 17 mandatory serial work queues. The task dashboard's broad “blocked on previous stage” wording is too coarse for daily scheduling: use the addendum and package prerequisites. For example F16 starts after F01; F25 starts after F01; T08 starts after F09/F32/F33/F34; T09 starts after F30/F31/F32/T01. Neither product package must wait for T03/T04/T05.

A practical speed improvement is to stop cycling a global review after every small fix. Freeze one candidate per coherent cohort, implement independent owners in parallel, integrate once, then run one bounded exit review. Preserve the existing F01–F40/T01–T12 scope, criteria and effort accounting. The cohort names below group work; they do not create new requirements or replace the plan.

## Immediate next cohort

First finish the current 563c6fa code gate. Carry forward accepted evidence with its exact commit and scope. Reopen only facts invalidated by changed production paths or new counterexamples. Do not reimplement an accepted boundary because its old checkbox is still empty.

Use the next cohort for the **remaining foundation, durable trajectory and independent execution work**, with these owners:

| Proposed owner | Existing packages / tickets | Dependency and concrete boundary |
|---|---|---|
| Foundation and integration lead | F37; F01; F02 | Reuse or close startup/identity and admission/cutoff evidence. F02 follows F01. These are ingress gates for the other owners, not a request to redo accepted work. |
| Trajectory and storage owner | F03/F04 → F06 → F07/F08 → F09 → F39 | F03/F04 need F01; F06 needs F02. F07 and F08 can overlap after F03/F04/F06. F09 needs F02/F03/F08, not a blanket wait for all other lanes. Close actual integrated receipts, scoped durable predecessor state and shared admission. Concrete existing tickets: ST03-F09-01…04 and ST03-F39-01…06, plus their FAs. |
| Execution owner | F16 → F17 → F18 and F19 | Start once F01 is accepted. F18 follows F17; F19 follows F16/F17. Close watchdog/quota, physical operation ownership and reconciled retry. Do not wait for the scientific stages preceding stage 6 in the displayed table. |
| Acquisition and learning-boundary owner | F25 → F26 | Start after F01. Close actual backend/input contract and complete support identity; prepare F27/F28 without claiming downstream biological validity. |

This maps to 16 existing packages, not 16 new projects. Their original full-package budgets total 388–660 hours, including already implemented scope. Assign and re-estimate only the evidence-backed remainder before converting this into a sprint or date. One integrator owns shared admission/schema files; other owners consume a frozen contract and avoid concurrent edits to that boundary.

Exit once, on the frozen integrated SHA: production behavior and actual downstream receipts establish the cohort's named invariants; changes have appropriate compatibility/build checks; accepted package/ticket scope and remaining empirical obligations are recorded. Runtime checks are evidence about the software behavior exercised, and are not an oracle for biological, causal or prospective validity. Do not declare all R0/R1 or the whole application accepted from this narrower cohort.

## Fewer integration cohorts for the remaining program

Every package appears exactly once below. The reproducible parser checks that the listed package order respects all declared prerequisites; owners within each cohort still overlap when their actual prerequisites are ready. A later product owner can start immediately on its ready prerequisites rather than wait for unrelated cohort closeout. The hour ranges are the original total budgets, not work remaining or date promises.

| Cohort | Existing packages, in a valid internal dependency order | Original hours | Exit scope |
|---|---|---:|---|
| A: foundation / trajectory / execution | F37, F01, F02, F03, F04, F06, F07, F08, F09, F39, F16, F17, F18, F19, F25, F26 | 388–660 | The immediate cohort described above; scoped software boundaries. |
| B: correction integrations / reliability | F05, F10, F11, F12, F13, F14, F15, F20, F34, F21, F22, F23, F24, F27, F28, F29, F30, F31, F32, F33, F35, F36, F38, F40, T11 | 756–1,300 | Run water/nutrient/scenario, learning, application and reliability owners concurrently by dependencies. Close scoped software defects and publication integrity; preserve F29/F36 empirical obligations. |
| C: coupled baseline / product / corpus / references | T01, T02, T08, T09, T12 | 540–960 | T01 enables read-only canonical projections and objective corpus. T08 can proceed from its F dependencies; T09 follows T01 and its F dependencies. T12 protocol/recruitment starts early; its full scientific acceptance waits for independent outcomes. |
| D: representation / instruments / rollout / economics | T03, T06, T04, T05 | 520–960 | T03 and T06 can overlap after T02 and their F prerequisites. T04 follows T03; T05 follows T04. Engineering artifacts and empirical promotions remain separately visible. |
| E: investigation / institutions | T07, T10 | 360–660 | Omega can start on its actual T04/T02/F prerequisites; T10 needs T04/T05/T08/T09. Close investigation/replication and territorial criteria on their own evidence. |

These are integration/review cohorts, not a demand for a single giant PR per cohort or one global field-acceptance bottleneck. Keep owner changes small enough to integrate safely; aggregate their review and evidence at the agreed exit point. Maintain the plan's actual prerequisite order for full package acceptance. If the current gate finds prerequisites already satisfied, consume that evidence immediately and shrink the corresponding cohort remainder.

## One exit gate and a bounded blocker rule

Before implementation, freeze scope, expected production outcomes, owner files and the candidate pin. The same exit reviewer checks all agreed criteria once on the integrated candidate. Any failed named acceptance criterion remains open; a nonblocking backlog must never hide such a failure or grant full package acceptance prematurely.

Block a cohort only for a reproducible defect in its changed or prerequisite production path that violates the agreed boundary: wrong scientific value/role/support; tenant or authorization escape; corrupt/non-durable state; unsafe execution; broken supported startup/publication; or incompatibility preventing its intended downstream consumer. Each blocker needs exact input, actual production path, expected/actual receipt, affected package, and one owner. A newly observed unrelated issue goes to the existing package's backlog unless it meets that threshold. A confirmed upstream blocker is repaired within that owner lane rather than triggering another whole-repository review.

Ordinary defects such as an omitted response field, stale map projection, lost parent key or import failure should be fixed and rechecked as software defects. Missing independent per-variable sensitivity, prospective calibration, native-instrument commissioning or seasonal field references are empirical acceptance work. Record the latter in F29/F36/T06/T12 and relevant target criteria; do not keep reopening completed code corrections while waiting for the growing season, and do not close those empirical packages on software evidence.

This distinction is required by R3, not a relaxation of its target: section 165 evaluates observability per variable and support; section 167 separates prospective weather-at-issuance performance from retrospective reconstruction; section 169 requires independent biological references and discriminating experiments. Source text reviewed: `sr-team-review/R3-full-text.txt`, lines 8898–8902, 8973–8996 and 9034–9066. A working 13-state map can satisfy a publication slice while leaving those capability claims open.

## Current-source provenance and limits

The parser verifies exact Git blob identity against `review-ab-563c6fa/git-tree.json`. The master deep repair plan (blob `08d378a65992de859369950599df198e64244f01`) and sequencing addendum (`40751038dc8760e91bc3ab115e30c5e28395953a`) were reused only after their local bytes matched the current tree. Current README (`282bd26535acb62d0e617c7108aa361592e1e217`), implementation blueprint (`472ff1805590bcbc44818e46f0779a02cd7c5d4e`), task register (`8a564647af7e588802537817159117b349ff606b`) and historical WIP register were fetched at the exact candidate SHA. Historical audits were not used as current correctness truth. No source files, repository docs, Git state or task checkboxes were modified.

`results.json` contains every ticket, the complete per-package done/open breakdown, estimates, prerequisites, source hashes and cohort membership. `progress_check.py` verifies the exact plan bytes and reproduces the counts and prerequisite-order checks. Use the source materializer or pass --repo to read those pinned documents from an existing clone. There is no current code completion assessment or verified overall percentage in these results.


## Per-package register checkbox counts

Each cell is done / in progress / open. These are register-reported states, not independently verified implementation states.

| Package | Numeric | Early slice | Full acceptance |
|---|---:|---:|---:|
| F01 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F02 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F03 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F04 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F05 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F06 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F07 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F08 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F09 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F10 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F11 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F12 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F13 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F14 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F15 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F16 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F17 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F18 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F19 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F20 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F21 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F22 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F23 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F24 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F25 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F26 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F27 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F28 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F29 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F30 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F31 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F32 | 0 / 0 / 4 | 0 / 0 / 1 | 0 / 0 / 1 |
| F33 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F34 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F35 | 0 / 0 / 4 | 0 / 0 / 1 | 0 / 0 / 1 |
| F36 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| F37 | 0 / 0 / 4 | 0 / 0 / 1 | 0 / 0 / 1 |
| F38 | 0 / 0 / 9 | 0 / 0 / 3 | 0 / 0 / 1 |
| F39 | 0 / 0 / 6 | 0 / 0 / 1 | 0 / 0 / 1 |
| F40 | 0 / 0 / 7 | 0 / 0 / 1 | 0 / 0 / 1 |
| T01 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| T02 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| T03 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| T04 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| T05 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| T06 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| T07 | 0 / 0 / 11 | 0 / 0 / 0 | 0 / 0 / 1 |
| T08 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| T09 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| T10 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| T11 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |
| T12 | 0 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 1 |

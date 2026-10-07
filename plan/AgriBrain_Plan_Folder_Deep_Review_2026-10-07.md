# Deep review of the complete AgriBrain plan folder

Review date: 7 October 2026. Repository: webClone/AgriWise.

**Decision: retain the master repair plan and the dependency-complete addendum as the planning basis. Correct the new implementation blueprint and task register before treating them as an execution-ready source.** Their package coverage is sound, but their task routing, acceptance parsing, readiness, verification and scientific decomposition contain material defects.

This review concerns the five documents actually present in `plan/` at **`96e515d6b1593f4b38756e79000313302971b936`**. The production baseline remains **`26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`**: the intervening commit adds the five plan documents and changes no production files. The three previously reviewed documents are byte-for-byte unchanged from the delivered versions. The two new documents therefore introduce a new review surface; a valid earlier three-document review does not certify them.

## 1. Scope, evidence and limits

The review retrieved the current GitHub folder and commit comparison, verified each plan file against its Git blob SHA-1, parsed all package cards and task entries, recalculated dependencies and effort, checked the 94 pinned production references against locally retrieved production blobs, and inspected the production symbols behind the clearest task-routing errors. Existing test files and earlier audit assertions were not used to establish production behavior.

The scientific comparison used the current French Master Monograph R3, dated 30 September 2026, including volumes XI–XVII and its 153-requirement register. The register identifiers match the package union exactly. Detailed target design was assessed against the monograph's scientific contracts, rather than against requirement-ID coverage alone.

This is a folder and execution-contract review. It does not claim a fresh complete production-code audit, a new execution of the quoted MESIA/ASMAE suites, a hardware commissioning result, or empirical proof of biological capability. No repository code or plan document was changed; no PR was merged or cherry-picked.

## 2. Exact folder inventory

| Document | Lines | Bytes | Verified Git blob |
|---|---:|---:|---|
| AgriBrain_Detailed_Implementation_Plan_2026-10-07.md | 2,137 | 161,892 | `1fa3c87832983e556eda5c8aa9f8eeb3f87280f5` |
| AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md | 73 | 6,940 | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| AgriBrain_Repair_Plan_Audit_Verification_2026-10-07.md | 229 | 20,158 | `97191eb07382efcd6d67b6fed652dcc18d8b921f` |
| AgriBrain_Work_Packages_Task_List_2026-10-07.md | 2,170 | 190,170 | `34db0d10c70a7398e809239bf40bdeb392124b77` |
| AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md | 2,063 | 124,752 | `08d378a65992de859369950599df198e64244f01` |

Main at review: `96e515d6b1593f4b38756e79000313302971b936`. PR #1 was observed open, draft and unmerged at head `bcb9eda6b8ef1aa6425f5828669f753a191227bc`. The old production baseline is still appropriate for the source references, but statements that main is currently at `26d5c3f` must be expressed as historical baseline statements.

## 3. Recomputed scorecard

| Check | Result | Meaning |
|---|---|---|
| Actual folder contents | Five Markdown documents | The new detailed plan and task list require their own review |
| Plan blob verification | 5/5 exact | Review uses the committed contents |
| Package coverage | 52/52 | F01–F40 and T01–T12 retained |
| R3 register | 153 unique IDs; no missing or extra IDs | Structural coverage, not demonstrated capability |
| Pinned production references | 94 distinct paths; 94 exact blob matches | Includes the bracketed `[id]` API path |
| Full-acceptance sequence | 17 stages; each package once; zero declared prerequisite inversions | F12 precedes F13; late full acceptances remain explicit |
| Package estimate total | 2,564–4,540 engineering hours | Excludes additional compute, hardware, field and seasonal effort explicitly noted in package cards |
| Task inventory | 218 numeric tasks + 52 acceptance tasks = 270 | No separately defined early-slice task |
| Numeric task target pattern | All 52 packages match cyclic selection from their target list | Specific incorrect mappings confirmed against production symbols |
| Numeric verification instructions | The same sentence appears 218 times | Includes 22 tasks assigned to TypeScript, TSX or Prisma files |
| New detailed-plan instructions | All 52 packages repeat master steps | Three purportedly detailed supporting blocks are identical across all 52 packages |
| Acceptance criteria copying | 51 packages copied cleanly; T12 has 94 extra source-reference bullets | A parsing boundary defect contaminates both new documents |
| Task-hour total | 2,554–4,526 hours | Understates package total by 10–14 hours |
| Portable file links | 152 local Windows URLs in detailed plan; 220 in task list | 372 links require replacement |

The R3 domain counts are AB-AGR 14, AB-ARC 12, AB-ASM 16, AB-DAT 14, AB-DEC 3, AB-ECO 5, AB-EXE 5, AB-L10 1, AB-L9 10, AB-MES 15, AB-ML 15, AB-OMG 18, AB-WM 7 and AW-PRO 18: total 153.

## 4. Prioritized findings

There are **11 folder-level findings: seven P1 execution/scientific contract problems and four P2 consistency/reproducibility problems.** These are review findings, not eleven newly discovered production defects. Recommendations concerning scientific decomposition and rollout are design judgments; counts, malformed entries and symbol locations are directly reproduced facts.

### P1-01 — Numeric tasks use mechanical file assignment, including wrong production owners

Every package's numeric task targets follow `paths[task_index % len(paths)]`. That pattern alone does not make every target wrong. The following direct mismatches show why the generated assignment cannot serve as a dependable implementation map:

| Ticket | Assigned target | Actual production owner / required correction |
|---|---|---|
| ST03-F39-04 | `visual_sources/tile_proxy.py` | Lock lifecycle concerns `_plot_cache_locks` in `app/main.py:3803–3830` |
| ST03-F39-06 | `sensor_runtime/storage.py` | Bounding-box cache is `_plot_bbox_cache` in `visual_sources/tile_proxy.py:66–71` |
| ST08-F24-04 | `layer6_yield/yield_forecast.py` | Sparse quantile scoring is `compute_crps_quantiles` in `world_model/forecast_archive.py:163–199` |
| ST10-F38-07 | `layer2_veg_int/growth_engine.py` only | `statistics` belongs there; `IrrigationSystemType` belongs in `irrigation_runtime/dispatcher.py:272`; split or name both |
| ST10-F38-02 | `orchestrator_v2/chat_adapter.py` only | Full-mode user-mode propagation also involves `orchestrator_v2/run_entrypoint.py:444,471` |
| ST00-F37-02/03 | L1 engine / drone dispatcher respectively | Optional-driver isolation and namespace migration need the actual driver and all supported entrypoint consumers, not one rotating file |

Ticket evidence: [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:384](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L384-L420), [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:1037](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L1037-L1068), [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:1413](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L1413-L1476). Production evidence: [services/agribrain/app/main.py:3803](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/app/main.py#L3803-L3830), [services/agribrain/visual_sources/tile_proxy.py:66](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/visual_sources/tile_proxy.py#L66-L71), [services/agribrain/world_model/forecast_archive.py:163](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/forecast_archive.py#L163-L199).

The same pattern assigns entire new scientific/product subsystems to existing integration files. T07's Bayesian comparison, simulation/BEL and causal identification are assigned to a worldline persistence service; its experiment design is assigned to a diagnostic promotion service. T08's livestock, market, quality, storage and transport workflows are assigned to a cycle-task API route. Those files can be integration points; they are not a sufficient implementation surface for all those capabilities.

**Correction:** author a symbol-to-task map for every numeric task. Distinguish existing files to edit, consumers to reconcile and proposed new modules. Require a source justification for each mapping. Re-evaluate all 218 assignments, without declaring all 218 demonstrably wrong.

### P1-02 — T12 acceptance contains the entire pinned-reference section

The detailed plan places **94 GitHub path/blob bullets** after T12's three genuine acceptance criteria. The task list copies the same 94 bullets into `ST12-T12-FA`. They are references, not conditions for independent agronomic validation.

Evidence: [plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md:1715](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md#L1715-L1812) and [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:1754](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L1754-L1855). The beginning is unmistakable: reference-label independence, prospective sample size and evidence review are followed by `prisma/schema.prisma` and the rest of the repository reference catalog.

**Consequence:** checklist automation and reviewers can treat file existence as scientific completion; T12 criteria counts are inflated and its intended conditions are obscured.

**Correction:** move the 94 entries into one reference appendix. Stop package parsing at the next top-level section as well as the next package. Restore exactly the three existing T12 criteria, then attach separately designed field-program milestones. Verify that acceptance arrays contain predicates, not source catalogs. A named registry field or a JSON schema would avoid relying on Markdown adjacency.

### P1-03 — Promised early slices are missing, and F37's early-slice entry is corrupted

The task-list naming convention advertises `ST00-F35-ES01` and `ST00-F39-ES01`, but **no ES task is defined**. Early-slice notes appear only beside the parent's later full-delivery package. Thus Stage 0 lacks actionable entries for the other startup/local-boundary slices described by the addendum.

The detailed plan's early-slice table says `F37 | 24-48 | [empty]`. The task list repeats “Early scope `24-48`. Full acceptance requires ``.” The correct addendum describes the GaussianMixture import and supported startup, with namespace/identity migration required for full acceptance. The detailed introduction also says five critical packages while listing six rows.

Evidence: [plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md:6](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md#L6-L18), [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:7](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L7-L9), [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:39](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L39-L42), [plan/AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md:9](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md#L9-L24).

**Correction:** define explicit early-slice tickets for F35/F38/F39/F40 and the Stage 1 F32 slice, and identify F37's startup subset within its Stage 0 package. Record limited acceptance, downstream full-acceptance dependencies and effort already included in the parent. A local nonce guarantee must not be marked as distributed replay safety. An unavailable real driver must not become a real driver through a simulation fallback.

### P1-04 — Readiness and ticket dependencies do not encode the execution contract

All 17 dashboard stages are labelled `Ready`, including future scientific extensions with unresolved upstream prerequisites. The legend combines `Pending / Ready` into one checkbox state. Numeric tasks repeat package-level prerequisites, but define no ticket-to-ticket prerequisite edges. Acceptance tasks lack explicit edges to all mandatory implementation, early-slice and evidence items.

Evidence: [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:7](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L7-L31), [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:43](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L43-L73) and the parsed register of 270 entries.

This does not invalidate the addendum's package DAG. It means that a valid package order has not been translated into an executable task DAG. A contract task, its producer, its consumers and its acceptance can all appear independently ready.

**Correction:** separate `Draft`, `Blocked`, `Ready`, `In progress`, `Validation` and `Done`. Derive readiness from accepted prerequisite artifacts and actual resource availability. Add ticket edges where dataflow or migration order requires them; allow genuine independent tasks to overlap. Require acceptance evidence before a package is Done. Preserve the addendum's permission to begin F16–F19 after their relevant F01 boundary rather than waiting mechanically for every earlier stage.

### P1-05 — The new “detailed” plan adds generic text rather than task-specific verification

All 52 implementation-step lists reproduce the master plan. All 52 invariant blocks are identical; all 52 consumer-reconciliation blocks are identical; all 52 verification/rollback blocks are identical. Every numeric task says “Code compiles cleanly under Python 3.12/3.13; contract assertions pass,” including frontend/database, RF instrumentation, training and experiment tasks.

Compilation cannot demonstrate probability calibration, immutable dataset replay, multi-replica atomicity, native CSI axis semantics, actual controller delivery, an economic objective or biological replication. The acceptance tasks do retain meaningful parent criteria, except the contaminated T12 entry. They need concrete evidence procedures and links to task outcomes.

Evidence: [plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md:48](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md#L48-L75), [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:43](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L43-L65), [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:2091](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L2091-L2123). The wording promising exact architectural invariants and verification fixtures appears at [plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md:4](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md#L4-L5), but the repeated additions do not supply those fixtures.

**Correction:** define verification appropriate to each change, including expected results and tolerances, observable consumer receipts, process topology, runtime and applicability. Establish a supported runtime matrix rather than asserting that every optional backend has already been validated on both Python versions. A controlled numerical fixture is suitable for a deterministic correction; empirical capability needs independent data and an appropriate protocol. Keep synthetic/exploratory evidence eligible for compatible research objectives, without granting it empirical field authority.

### P1-06 — Generic rollback is inadequate for persistent state and physical operations

Every package has the same rollback instruction: revert the Git branch and preserve delivered actions in logs. That does not define what happens after a schema migration, a new worldline event format, a partially written dataset snapshot, a changed head pointer, a learned-model deployment or a controller command already in flight.

F09/F39 need conditional writes, durability and restart behavior. F17/F18 need actuator ownership and reconciliation across uncertainty. F21–F23 need immutable payload/version behavior. A code revert cannot undo a delivered irrigation or recover incompatible persisted content by itself. The new final commissioning paragraph names simulated controllers but provides no actual supported-controller acceptance plan. Its blanket instruction that changes must be additive also needs qualification: removing fabricated fallback outputs changes behavior and requires explicit consumer migration, rather than preserving the erroneous output for compatibility.

Evidence: identical verification blocks throughout [plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md); additional commissioning language at [plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md:2132](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Detailed_Implementation_Plan_2026-10-07.md#L2132-L2137); the more precise parent boundary remains [plan/AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md:59](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md#L59-L66).

**Correction:** add package-specific schema compatibility, migration/backfill, read-version behavior, recovery, model demotion and in-flight operation procedures. Never erase historical action records or replay a command merely because an acknowledgement is uncertain. Specify the actual controller's stop/status/lease semantics and commissioning evidence. These are design requirements, not claims that a new field incident occurred during this review.

### P1-07 — R3 requirement coverage has not been decomposed into scientific delivery

All 153 IDs are covered; the monograph's scientific objectives are retained at package level. The task register still compresses large capability programs into four broad actions apiece. T07 alone carries all 18 Omega requirements. Its four tickets do not separately specify causal discovery versus identification, model-space inadequacy, BEL simulator adequacy, latent equivalence, equation discovery, measurement selection, performative causality or discovery metrics.

T03 lacks executable encoder/data/optimizer/calibration milestones; T04 lacks a rollout and memory-sufficiency protocol; T06 lacks an instrument lifecycle and biological-reference work breakdown; T08 merges several distinct product modules into one route task. This is a decomposition gap, not evidence that those capabilities are absent from R3 or that a different fixed neural architecture is mandatory.

Evidence: [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:1863](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L1863-L1932), [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:2015](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L2015-L2044), [plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:2087](https://github.com/webClone/AgriWise/blob/96e515d6b1593f4b38756e79000313302971b936/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md#L2087-L2123). Monograph anchors: volumes XII §§168–169, XIII §§170–177, XIV §§178–183 and XVI §§189–200; requirement register AB-MES, AB-ML, AB-WM, AB-DEC, AB-ECO and AB-OMG.

**Correction:** retain the existing production engines and typed objects as the target's basis, then split research/product packages into independently reviewable contracts, implementations and empirical milestones. Omega must remain a discovery system built around ScientificCase, competing explanations, discriminating predictions, experiments, falsification and replication. Promotion is one interface after evidence; it is not Omega's central scientific purpose.

## 5. Consistency and reproducibility findings

### P2-08 — Ticket estimates lose 10–14 hours

| Package | Parent range | Sum of numeric tasks | Deficit |
|---|---:|---:|---:|
| F38 | 48–80 | 45–72 | 3–8 |
| F39 | 40–72 | 36–72 | 4–0 |
| F40 | 24–48 | 21–42 | 3–6 |
| Whole program | 2,564–4,540 | 2,554–4,526 | 10–14 |

The arithmetic is consistent with rounding equal task allocations down. The dashboard retains parent sums while task totals differ. Acceptance and early-slice effort are not explicitly allocated. Additional resources are already excluded by parent descriptors such as “plus experiments” and “plus hardware/field work”; they must remain separate rather than being silently absorbed into Python task hours.

**Correction:** allocate integers or explicit fractions that sum to each parent, including acceptance and early slices within the same budget. Separate engineer effort, calendar constraints, compute and field cost. Do not add the earlier 90-package roadmap to the 52-package total: the master says these regroup that roadmap.

### P2-09 — 372 links depend on a private Windows checkout

The detailed plan contains 152 `file:///c:/Users/E-C/Desktop/agriwise/...` links and the task list 220. They include links between the plan documents and to production targets. They cannot serve as portable GitHub navigation.

**Correction:** use sibling links for plan documents and `../services/...`, `../src/...` and `../prisma/...` for current repository files; use pinned GitHub links when historical source identity matters. Verify bracketed route paths and anchors with a proper link parser. New modules should be explicitly proposed paths, without pretending that they already exist.

### P2-10 — The folder is not self-contained for monograph traceability

The master refers to a companion traceability register carrying all 153 requirements and original roadmap ownership. The repository tree contains the R2 DOCX, but not the current R3 monograph or the delivered companion traceability/backlog registers. `plan/` has only the five Markdown files and no manifest that resolves those dependencies.

The current R3 was available for this review through the supplied project documents; someone checking out only GitHub cannot reproduce the same target comparison from package IDs alone.

**Correction:** add an authoritative target manifest with R3 identity, date, accessible location and content digest; include the exact requirement register or a stable, accessible reference. Keep requirement text, acceptance, primary/supporting ownership and source baseline distinct. Do not substitute R2 for R3 merely because R2 is committed. Do not turn an external financial or scientific illustration into a measured acceptance threshold.

### P2-11 — Baseline, document precedence and “approved” state are ambiguous

The new detailed plan labels itself `Approved Execution Roadmap` and says `Main at 26d5c3f`. Main is now `96e515d`; production is unchanged, so this is a labeling/provenance problem rather than source drift. The five documents overlap without a folder-level authority map. The original audit remains historical evidence, not a proof that the subsequently generated task list passed review.

**Correction:** record `production_baseline`, `plan_revision`, `target_monograph` and `review_state` separately. Reference a genuine approval record if approval is claimed; otherwise use “proposed” or “reviewed with corrections.” State precedence: R3 target contracts; master package meaning; addendum full-acceptance scheduling; generated detailed/task views; historical verification report. Any semantic change to a generated view must be reconciled upstream.

## 6. Scientific contracts that the corrected task register must preserve

| Target | Required executable specification | Evidence that cannot be replaced by compilation |
|---|---|---|
| Coupled agronomy T01 | State variables, units, layer/depth support, flux order, assimilation increment ledger, actual-event timing and versioned crop/soil parameters | Closed water/nutrient balances; sparse/daily and restart equivalence; independent agronomic reference comparisons |
| Dataset T02 | Objective-specific eligibility, temporal availability, target ancestry, splits, native support/masks and immutable projection versions | Rebuild equality; ancestry leakage checks; measured/weak/synthetic role separation; evaluation partitions independent of teachers |
| Foundation model T03 | Modality encoders and axis schemas, physical X/latent Z interfaces, objectives, optimization and artifact manifests | Baselines, ablations, calibration, modality dropout, unseen farm/season/instrument transfer and distillation results |
| World model T04 | Hybrid transition, action/forcing semantics, memory, belief uncertainty, rollout origin/horizon and conditional versus identified causal claim types | Multi-horizon proper scores; memory-sufficiency comparisons; out-of-domain and intervention support; archived prospective evaluation |
| Decision/economics T05 | Feasible action set, belief-state objective, contextual units/prices/costs, dependence and downside risk, information-acquisition options | Feasibility, no duplicated exposure/cost, coherent currency/area/time accounting and evaluation against realized outcomes |
| MESIA T06 | Native complex signal axes, clocks, instrument identity/configuration, pose/calibration epochs, nuisance covariance, lattice support and capability lifecycle | Independent calibration and nuisance perturbations; missingness; support alignment; biological references and drift evaluation |
| Omega T07 | ScientificCase; alternatives and inadequacy; inference, identification, latent/equation candidates; experimental design and scientific memory | Predeclared discriminating predictions, negative/inconclusive results, falsification, independent replication and scoped transport |
| Product T08/T09 | Explicit domain schemas/routes/UI flows; actual versus proposed operations; records, stocks, calendars, language, offline reconciliation and canonical response | Authorized scoped workflows, accounting reconciliation and conflict behavior; no scientific values invented in rendering |
| Territorial T10 | Cohorts, coverage, cross-plot dependence, hierarchy and policy scenario assumptions | Independent territorial validation; privacy/coverage limits; observed effects separated from policy simulations |
| Reference program T12 | Sites/cohorts, independent instruments/labels, horizons, clustering, protocol, measurements and seasonal milestones | Field results with uncertainty and applicability, not a local regression receipt alone |

The monograph permits imperfect, sparse and synthetic evidence for compatible objectives. Correcting admission must retain that distinction: an absent empirical target can mask one supervised loss while a sample remains eligible for self-supervision. A simulator result can check a model assumption without becoming biological replication. Strong model agreement does not identify a cause. An RF latent is not given a biological name solely because it improves prediction.

For probabilistic forecasts, distinguish distribution availability from scoring. For a fully specified quantile function, CRPS is `2 ∫₀¹ ρτ(y − Qτ) dτ`. A sparse quantile average needs documented integration/weighting or a precise finite-quantile score name. Missing median must never be filled from the observed outcome. Gaussian P10/P90 use approximately ±1.28155σ, not ±1.645σ. Those are existing parent-plan correction targets; the task register must route them to the correct implementation and observable consumers.

For physical trajectories, a verification fixture should account for physical storage changes, inputs/outputs and any assimilation/clipping adjustments separately. Equal endpoint values alone can hide wrong intermediate forcing. For actual actions, planned dose, commanded dose, controller acknowledgement and measured delivery must remain distinct in both training targets and decision economics.

## 7. Recommended disposition

1. Preserve the 52 parent packages, exact R3 mappings and valid 17-stage full-acceptance schedule.
2. Correct generator/parser boundaries: remove T12's 94 false criteria, repair F37 and replace nonportable links.
3. Re-author task targets against production symbols, add missing early slices and construct the task prerequisite/evidence graph.
4. Replace generic verification and rollback with task-specific contracts, runtime checks and recovery procedures.
5. Split T01–T12 into engineering and empirical milestones while retaining the monograph's research purpose.
6. Reconcile hours, document precedence and the external R3/register references. Only mark individual slices Ready when their own prerequisites are established.

Narrow, independently reviewed foundation corrections can proceed using the master and addendum after their task contracts are made explicit. The new register should not be used wholesale as proof of execution readiness. Its checkboxes do not establish scientific capability, production fixes or completion of the monograph target.

The companion correction specification provides precise edits, example rewritten tickets and an Omega milestone map. These are proposed document corrections; they have not been applied to GitHub.

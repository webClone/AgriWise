# Correction specification for the AgriBrain plan suite

Prepared 7 October 2026 against plan revision `96e515d6b1593f4b38756e79000313302971b936` and unchanged production baseline `26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`. This document specifies review amendments; it is not an implemented repository change and does not authorize a merge or live operation.

## 1. Document roles and exact amendments

| Document | Retain | Amend |
|---|---|---|
| Master deep repair plan | 52 package meanings, production references, scientific criteria and engineering ranges | Resolve accessible R3/register references; label the historical production baseline explicitly |
| Execution addendum | Valid 17-stage full acceptance; lane concurrency and early/full distinction | Add stable early-slice IDs and accepted artifact prerequisites once their task definitions exist |
| Audit verification | Historical qualified evidence and precision corrections | Identify reviewed scope/version; do not imply it covers later documents |
| Detailed implementation plan | Package allocation to the valid schedule | Repair F37; remove 94 T12 reference criteria; replace generic invariant/consumer/verification/recovery blocks with actual contracts |
| Task list | Parent package IDs and stage membership | Replace round-robin targets; add early tasks and graph; repair readiness, criteria, evidence and effort |

Add a small folder manifest/README recording the five roles, production baseline, plan revision, monograph identity and precedence. Keep historical reviews distinguishable from current review state. Relative links should work from a Git checkout and GitHub.

## 2. Required ticket fields

Each actionable ticket needs the following information. Use a machine-readable registry as the source and render Markdown from it; Markdown should remain readable without the generator.

| Field | Contract |
|---|---|
| ID / parent / kind | Stable task ID; parent package; full, early, acceptance or empirical milestone |
| Scope | One reviewable behavior, with explicit exclusions and boundaries where necessary |
| Source map | Existing paths and symbols, consumers, migrations, proposed new modules; source justification |
| Prerequisites | Package and ticket/artifact dependencies, plus actual field/data/hardware constraints |
| R3 mapping | Exact requirements and relevant scientific objective; no inferred extra domain association |
| Interfaces | Typed input/output, units, support, timing, masks, authority and failure records |
| Expected behavior | Before/after fixture, observable outcomes and appropriate numerical tolerance |
| Verification | Runtime/process topology or empirical protocol; comparator, evidence receipt and applicability |
| Recovery | Persisted version compatibility, interruption/restart behavior, operational reconciliation where applicable |
| Effort | Allocated parent hours; empirical/compute/hardware costs separately stated |
| Status / ownership | Owner and reviewer; Draft, Blocked, Ready, In progress, Validation or Done; linked acceptance evidence |

A proposed new module path is a design choice pending review. Existing integration targets must not be silently treated as implementations of a new research engine.

## 3. Immediate parser and register corrections

1. **T12:** its acceptance list consists of the three scientific predicates already in the master. Move all 94 source entries out of both acceptance lists. Preserve references once in the reference catalog.
2. **F37:** replace `24-48` in the early-scope column with “Correct GaussianMixture import and establish supported startup.” Restore “Full package Stage 0; namespace/identity migration must also pass.” Describe six staged rows, with F37's subset distinguished from later-parent early slices.
3. **Readiness:** remove unconditional `Ready` for all stages. Mark the initial inventory Planned/Blocked until ticket prerequisites are assessed. Only a particular task may become Ready; a stage summary is computed from its task states.
4. **Prerequisite graph:** add edges for contract → producer → required consumer reconciliation → integration acceptance where applicable. Acceptance depends on all required tasks/evidence. Do not add artificial serial edges between genuinely independent work.
5. **Links:** replace all 372 personal Windows URLs with valid relative or pinned links. Preserve `[id]` route paths in parsing.
6. **Traceability:** include or resolve the current R3 register and monograph with immutable identity. Verify 153 unique requirements, exact package mapping and no unsupported extra ownership.
7. **Sizing:** reconcile F38, F39 and F40 without altering parent ranges by accident. Allocate verification and early work inside the parent instead of adding duplicate hours.
8. **Validation quality:** verify no acceptance predicate contains only a path/blob reference; no task is assigned by array position; no empirical task is certified by Python compilation alone.

## 4. Rewritten production-task examples

These examples demonstrate the necessary precision. They do not replace a review of the remaining target mappings.

### ST03-F39-04 — Bound plot-lock lifecycle without losing mutual exclusion

**Production target:** `services/agribrain/app/main.py`, `_plot_cache_locks`, `_plot_cache_locks_lock` and the lock lookup around lines 3803–3830. `tile_proxy.py` is not the owner of this lock map.

**Behavior:** choose fixed lock striping or a lifecycle-managed keyed lock mechanism. If keyed locks are reclaimed, no held lock or waiting lock may be replaced by a different lock for the same active key. Include tenant/namespace in the scope when the guarded resource requires it; preserve safe serialization through any migration from old plot-only keys.

**Verification:** orchestrate concurrent same-key holders/waiters and eviction pressure; instrument the protected critical section and verify no simultaneous owners. Verify different valid scopes can make progress and that configured lock memory stays bounded under high-cardinality keys. Repeat in the supported process topology. A process-local guarantee is reported as process-local; shared-storage safety comes from the actual conditional-write contract.

**Acceptance:** no lost mutual exclusion, no evict-while-held/waited race, bounded memory and an explicit separation between local locking and durable distributed correctness. Coordinate this ticket with F09/F39's persistence work.

### ST03-F39-06 — Scope and invalidate bounding-box cache entries

**Production target:** `services/agribrain/visual_sources/tile_proxy.py`, `_plot_bbox_cache` around lines 66–71 and its read/write consumers. Coordinate geometry identity/version producers; `sensor_runtime/storage.py` is not the bbox cache owner.

**Contract:** key by qualified tenant/namespace/plot plus geometry epoch or digest. Persisted geometry changes must not reuse cached bounds for an earlier geometry. Define whether caches are process-local, their lifetime and cardinality bounds.

**Verification:** the same plot label under two tenants with different polygons produces distinct bounds; changing geometry produces fresh bounds; a late request for an earlier explicit epoch uses the appropriate historical geometry. Exercise cold start and eviction without inventing a fallback polygon.

### ST08-F24-04 — Give sparse quantile scores an accurate definition

**Production target:** `services/agribrain/world_model/forecast_archive.py`, `compute_crps_quantiles` and evaluation consumers. `layer6_yield/yield_forecast.py` may supply distributions but does not own this scoring helper.

**Contract:** finite, ordered quantile levels/values with documented distribution support. Empty or invalid forecasts produce an unavailable score with a reason, never perfect score zero. Do not infer p50 from the realized observation. Choose either a clearly named finite-quantile pinball score, or a documented CRPS approximation with interpolation, weights and tail policy. Version the metric name/definition in archived evaluations.

**Verification:** cover a deterministic distribution, a known full Gaussian comparator, irregularly spaced quantiles, duplicate/invalid levels, crossing quantiles, nonfinite input and a valid nonempty distribution lacking p50. The finite-score result and any approximation error must be reported under their actual metric name; missing median does not create artificial RMSE=0.

**Recovery:** historical scores remain attached to their scoring version. Rescoring creates a new record rather than overwriting the old result or editing the original forecast.

### Split ST10-F38-07 into two explicit runtime corrections

**F38 statistics slice:** `layer2_veg_int/growth_engine.py`, the branch invoking `statistics.mean(valid_dts)` near line 296. Import the actual required symbol and exercise valid/empty/malformed time intervals with defined behavior.

**F38 irrigation enum slice:** `irrigation_runtime/dispatcher.py`, the branch constructing a device with `IrrigationSystemType.DRIP` near line 272. Import the canonical enum, exercise the actual branch and verify class identity under supported startup. Keep command eligibility and physical-delivery authority unchanged by an import fix.

Both slices require their own expected outcomes. A combined parent task may list both paths, but must not certify the second branch solely by running the first.

### Correct ST10-F38-02's consumer scope

Thread intent and user mode through both the adapter and `orchestrator_v2/run_entrypoint.py` full/quick/degraded branches. Verify supported user modes and intents from typed input to canonical visible output; absent context follows the declared policy, not an incidental `locals()` fallback. Completion includes upstream acquisition of the actual fields and downstream response-policy consumers.

## 5. Early-slice register to add

The following are proposed IDs/scopes, not completed work. Allocate their hours from existing parent ranges.

| Slice | Earliest placement | Limited acceptance | Full parent remains open until |
|---|---|---|---|
| F37 startup subset | Stage 0 | Correct sklearn import; declared startup/capability behavior in clean processes | Namespace identities and every supported entrypoint pass |
| ST00-F35-ES01 | Stage 0 | Missing optional real driver disables only that capability; simulation remains labelled | F09-dependent durable job lifecycle, cleanup and restart acceptance |
| ST00-F38-ES01… | Stage 0, by branch prerequisites | Actual local/context names repaired; unavailable/failure output remains truthful | F01/F02/F09/F31/F37 integration and publication relations pass |
| ST00-F39-ES01 | Stage 0 | Reproduce nonce admission race and remove it under an explicitly declared topology | Shared atomic admission, durable telemetry and distributed retention pass after F01/F09 |
| ST00-F40-ES01… | Stage 0, after needed name definitions | Actual runtime schema/introspection consumers resolve required annotations | Full supported runtime/manifest consumers pass after F37/F38 |
| ST01-F32-ES01 | Stage 1 | Database failure is unavailable; real account zeros remain zero | Scoped records/calendar/task integration passes after F09 |

The naming scheme should record limited slice completion independently of parent completion. A note beside a Stage 11 parent is not a Stage 0 execution ticket. Full prerequisite completion is unnecessary for a narrow independent import fix, but required for full scientific/persistence claims.

## 6. Replace generic verification with evidence by lane

| Lane | Concrete evidence to specify |
|---|---|
| Observation admission | Finite numeric handling, legitimate zero, role/authority retention, observation and availability clocks; rejected-component receipts |
| Hydrology and nutrients | Flux and assimilation ledgers, units/depth, irregular forcing, restart and daily/sparse equivalence, applied-event eligibility and residual nutrient accounting |
| Persistence/concurrency | Conditional writes, idempotency, interrupted writer/read recovery, multi-worker conflicting operations, retention boundaries and historical versions |
| Actuator execution | No-telemetry watchdog, non-bypassable quota/caps, lease ownership through completion, admissible stop, acknowledgement uncertainty and actual delivery |
| ASMAE | CRS/support masks, per-scene operator timing, primary versus auxiliary effects, held-out issuance provenance and state-specific weak-label weights |
| MESIA | Native complex axes/phase semantics, clocks/calibration identity, geometric support, missing SNR/nuisance uncertainty, masked-target independence and external references |
| Learning/world model | Frozen lineage, eligible objectives, blocked splits, baselines/ablations, calibrated proper scores by horizon/domain, conditional versus identified effects |
| Product | TypeScript/Prisma build and domain behavior, scoped writes, canonical response consistency, real calendar/stock reconciliation, offline conflict semantics |
| Research/economics | Predeclared protocol/estimand, uncertainty and sample dependence, independent outcomes, cost/value units and explicit experimental conclusions |

Specify supported runtimes and optional dependency extras per capability. An unsupported optional backend may be unavailable without disabling unrelated functions; that is distinct from declaring all backends validated on Python 3.12 and 3.13.

## 7. Minimum Omega work breakdown aligned to R3

Proposed scientific modules below are new implementation surfaces, not existing production files. Existing worldline and diagnostic integration services remain adapters and consumers.

| Milestone | R3 requirements | Concrete deliverable / acceptance |
|---|---|---|
| O1 Case and epistemic history | AB-OMG-001/002 | ScientificCase schema, immutable evidence cutoffs, branching alternatives and replayable theory versions |
| O2 Surprise and inadequacy | AB-OMG-003/004 | Compare instrument faults, missing management, domain/parameter shifts and structure; preserve unknown mass and candidate-space inadequacy |
| O3 Bayesian inference laboratory | AB-OMG-005 | Priors, likelihoods and inference adapters; convergence, posterior-predictive and prior-sensitivity evidence for each selected method |
| O4 BEL and simulation | AB-OMG-006 | Simulator prior, observation model, compression and QoI; simulator adequacy and calibration; simulation outputs retain their role |
| O5 Causal discovery and identification | AB-OMG-007/008 | Candidate graphs/lags and confounders separately from estimands, identification assumptions, positivity, support and sensitivity |
| O6 Latents and equations | AB-OMG-009/012 | Compare equivalent representations and nuisances; candidate equations with dimensions/conservation/complexity and independent holdouts |
| O7 Measurement and performative policy | AB-OMG-010/011 | Candidate measurement set, inclusion rule, cost and information value; recommendation exposure, compliance and collection-policy history |
| O8 Discriminating experiments | AB-OMG-013 | Predicted differences among alternatives, comparators, power/clustering/interference, permitted actions, stopping and outcome collection |
| O9 Falsification and replication | AB-OMG-014/015 | Predeclared falsifiers, negative/inconclusive outcomes, independent replication and scoped transport assumptions |
| O10 Scientific memory and value | AB-OMG-016/017 | Versioned knowledge including revocation and domains; ambiguity reduction, replication, information gain and cost reported separately from prediction gains |
| O11 Capability integration | AB-OMG-018 | Scientific conclusions and operational permission assessed independently; promotion does not replace the investigation |

Begin with one discriminating agricultural case from R3: vegetation decline with water shortage, saline/osmotic stress, hypoxia, delivery heterogeneity and hydraulic memory as competing explanations. Define expected independent water-depth, EC, plant-response and available RF/SAR measurements. Preserve coexistence of mechanisms and inadequate model space. Select candidate methods from the problem's identifiability and data, rather than promising a universal Bayesian or causal algorithm.

Scientific protocol/interface design can start before every upstream full capability is complete. Empirical conclusions and operational use retain their own evidence prerequisites. Do not force data collection or exploratory learning to wait until Stage 16 merely because that stage contains full Omega acceptance.

## 8. Other target-package expansions required

**T01/T02:** create explicit state-transition and longitudinal sample contracts before tensor projections. Document native versus broadcast support, physical memory, actual actions, target dependencies, clocks, masks and objective eligibility. Version parameter/model changes and preserve as-issued histories separately from revised reconstruction.

**T03:** separate baseline experiments, modality axis/schema adapters, masked training, probabilistic heads, X/Z alignment, calibration/OOD, local adapters, distillation and federated prerequisites. Include fitted-normalization partitions, compute budget, optimizer/run identity and blocked transfer cohorts. Model-registry metadata is a consumer of these results, not the neural implementation.

**T04/T05:** specify hybrid transition, weather issuance provenance, memory-sufficiency comparisons, rollout errors by horizon, feasible actions, actual-dose semantics, contextual costs and risk. Separate conditional simulation from an identified causal effect; use archived prospective targets and independent realized outcomes for the corresponding claims.

**T06/T12:** split acquisition, instrument metadata/pose/configuration epochs, calibration and nuisance analysis, lattice/operator integration, maintenance/drift and independent biological evaluation. Budget field sites, sensors, calibration and seasonal reference collection separately. T12's engineering registry work and its completed field-validation claims are distinct milestones.

**T08/T09/T10:** create separate schemas/services/UI for stocks, equipment, livestock, market/orders/quality/logistics, finance and territorial aggregation. Keep proposed operations separate from actual exposure, realized revenue and costs. Specify permissions, offline conflicts, cohort coverage and cross-plot dependence at their actual consumers.

## 9. Recovery and effort reconciliation

For each persisted change, name the supported schema versions, forward/backward read behavior, migration/backfill, interruption recovery and rollback/demotion behavior. Preserve old events and forecasts. For actions already sent, require safe status reconciliation and idempotent operation ownership; a code revert must never imply resending an uncertain command or deleting evidence of delivered water.

One arithmetic-only correction is to allocate F38's missing 3–8 hours, F39's missing 4–0 hours and F40's missing 3–6 hours explicitly across their tickets. This restores 2,564–4,540 hours, but it is not a substitute for estimating the redesigned work. Acceptance and early slices need explicit allocations within their parents. If decomposition reveals genuinely new scope, change estimates transparently rather than preserving them for appearance. Calendar duration depends on capacity, field season, data and equipment availability.

## 10. Completion criterion for the plan repair

The suite can be called execution-ready when: all actionable targets have source justification; early/full tasks and evidence dependencies are explicit; T12 contains no reference predicates; status is prerequisite-based; hours reconcile; links and current R3 references are portable; verification/recovery is capability-specific; and the scientific extensions have separate engineering and empirical milestones with appropriately independent outcomes.

This criterion concerns the quality of the plan. Passing it does not certify the production code, biological hypotheses or completion of AgriBrain's target capabilities.

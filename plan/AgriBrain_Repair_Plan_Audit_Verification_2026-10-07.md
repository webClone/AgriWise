# Independent verification of the repair-plan audit

Date: 7 October 2026. Uploaded source: Texte collé(3).txt, “AgriBrain Deep Repair Plan Forensic Verification Report”. Plan assessed: AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md, the 2,063-line version delivered on 6 October. Production baseline: `26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`.

## 1. Decision

The report correctly confirms the package inventory, priority counts, engineering-hour sums, requirement counts, shared-requirement count and acyclic dependency graph. Its main scientific/operational concerns remain actionable. It does not support its unconditional “every code defect 100% verified” conclusion: there are errors in the reference count, a sample blob identity, the empty-forecast trigger, the watchdog mechanism, several requirement-to-package associations and the suggested sprint budgets.

The F13/F12 batch ordering defect is real in the original plan. The original plan also leaves full F38-F40 completion implicit after their early slices. These are planning gaps to correct, even though the package DAG itself has no cycle. The companion execution addendum supplies a complete dependency-compatible acceptance order for all 52 packages, explicit early-slice boundaries and unchanged effort totals.

Begin the verified foundation repairs. Do not interpret this report as empirical certification, completed remediation, approval to merge PR #1, or readiness to train/deploy the target world model and Omega. No repository changes, merges, deployments or hardware actions were made in this verification.

## 2. Method and source scope

GitHub main was freshly checked on 7 October and still matches the pinned baseline. PR #1 remains open, draft and unmerged, with head `bcb9eda6b8ef1aa6425f5828669f753a191227bc`. No proposed PR behavior is credited to main.

The uploaded report was read from its supplied scratch copy. The previously saved exact plan was used for structural checks. All 94 target/reference identities were recomputed from pinned production bytes and compared with the plan and tree manifest. A fresh pinned GitHub retrieval of the water-balance source supports the source-identity check. The 510-file verified source corpus is retained; this pass does not claim a new complete repository scan.

The controlled production probe collection, irrigation/forecast continuation probes and dated-water adapter probe were rerun successfully. The broad collection contains 23 cases, including a successful control rather than 23 defects. New targeted probes distinguish empty from median-missing forecasts and direct monitor evaluation from dispatcher admission. Existing repository tests, audit artifacts and claimed suite logs were not used as production correctness evidence. The supplied report is the object of verification, not the ground truth for its claims.

The runtime remains Python 3.12.14. No live database/provider/device or independent field program was exercised. Earlier scientific source findings and controlled fixtures are software evidence, not independent agronomic validation. Requirement coverage here checks the exact R3 register mapping; it does not reclassify each scientific requirement as implemented.

## 3. Corrected scorecard

| Claim | Result of independent check |
|---|---|
| 2,063 lines | Confirmed for the exact original plan version. |
| Fourteen top-level sections | Fourteen numbered main sections plus Section 3a: 15 headings at Markdown level two. The supplemental heading should be stated explicitly. |
| 52 complete packages | Confirmed: F01-F40 and T01-T12; required delivery fields present. |
| P0 23, P1 17, Target 12 | Confirmed. |
| 94 unique production targets | Confirmed; all exist in the pinned tree and have corresponding references. |
| 93 pinned references | Incorrect: 94 distinct references. The path containing [id] is missed by a parser that stops at the first closing bracket in a label. |
| All sample blob hashes agree | One example is incorrect: water-balance source is e445703e..., not a0adcde.... App main is correctly 9ea06f.... |
| Fifteen counterexamples 100% verified | Fifteen rows are present; seven narrative examples are supplied. Several explanations are inaccurate. Fresh production probes support the actionable defects, with the trigger qualifications below. |
| Nine batch inversions | Reproduced under a first-occurrence assignment. This mixes early slices with full packages, so it is not nine independent DAG defects. |
| Zero cycles/dangling package dependencies | Confirmed. |
| 153 unique R3 requirements across 14 domains | Confirmed as register coverage. |
| 65 requirements shared across packages | Confirmed. |
| Domain package examples faithfully reflect the register | Incorrect: eleven listed package/domain memberships are absent from the actual mapping; the list also omits mapped packages. |
| 2,564-4,540 total engineering hours | Correct sum of planning ranges. Does not independently validate the ranges. |
| Four proposed sprint budgets sufficient | Not established; some listed budgets are below the unchanged package totals and slice allocation is unspecified. |
| Ready for execution | Qualified: begin scoped repairs using explicit dependencies and acceptance; full program feasibility/empirical readiness is not certified. |

## 4. Exact reference and blob findings

Section 13 contains 94 reference lines and 94 distinct paths. Package targets and pinned references have identical path sets. All 94 locally recomputed Git blob identities match both the plan and the pinned tree.

The overlooked path is `src/app/api/cycles/[id]/tasks/route.ts`, blob `f2d3ad12260b355afe246dd8e80e8562ae5082b0`. A bracket-sensitive regular expression returns 93 despite the actual 94 valid references. This is an audit-parser issue, not a missing plan target.

The report’s sample `a0adcde...` for the water-balance file does not match the baseline. The actual identity is `e445703e0640c77df072b7fe72b2933352ebdfb6`. The claimed App Main prefix is correct: `9ea06f5f706e767491bd28653cc817823d300a6f`. The wrong sample does not invalidate the plan’s references, but the report must correct it before claiming exact agreement for its examples.

## 5. Scientific and runtime claim corrections

### 5.1 Nitrogen: confirmed within the stated model convention

[`layer4_nutrients/photosynthesis_nue/engine.py:126`](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py#L126) computes recovered plant N from `(applied_N + soil_supply) * 0.60`. The residual dose is then reduced again by applied N at [`layer4_nutrients/photosynthesis_nue/engine.py:161`](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer4_nutrients/photosynthesis_nue/engine.py#L161).

For biomass 5 t/ha and critical concentration 2%, target plant N is 100 kg/ha. Existing recovered N is 48 kg/ha. The additional application under the same assumed 0.60 recovery is `(100-48)/0.60 = 86.6667`, while the code returns 36.67. F11 is correctly justified. This does not validate 0.60 as a universal recovery efficiency or establish a field fertilizer prescription.

### 5.2 Gaussian quantiles: confirmed, branch comparability also matters

[`world_model/forecast_archive.py:488`](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/forecast_archive.py#L488) uses 1.645 sigma in its Gaussian interval branch. These bounds are approximately P5/P95, not P10/P90. The quantile branch takes P10/P90. The branches therefore calculate coverage and sharpness over different nominal intervals. The constant is legitimate for a 90% central interval; the defect is mislabelling/inconsistent interval support, not the mere presence of a constant.

Fix F13/F24 by storing interval levels and computing consistent quantiles from the declared distribution. Median, mean and interval level must remain separate. The same error exists in the L6 Gaussian labelling addressed by F13.

### 5.3 Empty forecast and missing median are different failures

The report says an empty quantile dictionary enters the branch that defaults p50 to the observation. It does not. The branch begins with `if forecast.predicted_quantiles`, so an empty dictionary is false.

Fresh actual archive results, with observed value 1:

| Input | Actual evaluation |
|---|---|
| Empty quantiles; no Gaussian mean/std | ContractViolation: no predictive distribution. |
| Empty quantiles; Gaussian mean 0/std 1 | Gaussian branch; RMSE 1.0, not 0.0. |
| Nonempty quantiles {p10: 0, p90: 2}; median absent | RMSE 0.0 because p50 falls back to observed value; CRPS about 0.20. |
| Direct compute_crps_quantiles({}, 1) | Returns 0.0; separate standalone scoring-helper defect. |

F24 remains necessary. The report conflates the original plan’s empty-CRPS helper counterexample with a different missing-median RMSE defect. Correct both: missing distributions receive unavailable scores, and observations cannot supply a missing forecast statistic. An archive rejection must also leave retrieval and evaluation on the committed record, as required by F23.

Source: [`world_model/forecast_archive.py:477`](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/world_model/forecast_archive.py#L477).

### 5.4 Watchdog and quota: confirmed defects, incorrect function attribution

The actual monitor method is `SafetyMonitor.evaluate`, not `evaluate_telemetry`. Its duration watchdog runs even when evaluate is directly called with an empty dictionary. A controlled expired event returned DURATION_EXCEEDED for `evaluate(device,{})`.

The dispatcher skips that call under `if sensor_readings` at [`irrigation_runtime/dispatcher.py:293`](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/irrigation_runtime/dispatcher.py#L293). Its preflight check, including quota, is similarly gated at [`irrigation_runtime/dispatcher.py:128`](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/irrigation_runtime/dispatcher.py#L128). Rerun local-driver results: zero budget sent one start with None or empty telemetry, but no start with a nonempty reading; an expired event had zero stop calls with absent readings and one emergency stop after readings arrived.

Thus the system integration bug is confirmed, but the report’s stated mechanism is incomplete. A safe repair runs quota before every submission and a monotonic duration watchdog independently of new telemetry. “Indefinitely” is not an independently verified property of every real controller, which may have separate firmware limits.

### 5.5 Crop adapter and leaching: confirmed under their supplied contracts

[`layer8_prescriptive/scenario_contract.py:56`](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/scenario_contract.py#L56) reads crop_type/expected_yield/expected_profit, whereas actual CropOptionEvaluation has crop/yield_dist/econ. A representative actual-schema option still becomes unknown with relative yield 1.0. Do not claim every conceivable duck-typed object fails; qualified legacy objects with the expected attributes can follow another path. F14 must accept the actual upstream contract and reject incompatible objects without fabricating scientific values.

[`layer8_prescriptive/engines/salinity_leaching.py:67`](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer8_prescriptive/engines/salinity_leaching.py#L67) can raise the supplied max_safe. The controlled case remains recommended 23.1 and new max 27.7 from an original cap 21. This violates the stated hard-cap interpretation. F15 needs an immutable final feasibility ceiling, with dose modifiers unable to raise it.

### 5.6 Causal attribution: confirmed, exposure predicate needs exact wording

[`layer6_exec/outcomes/metrics.py:68`](https://github.com/webClone/AgriWise/blob/26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4/services/agribrain/layer6_exec/outcomes/metrics.py#L68) requires both COMPLETED_VERIFIED status and a non-None execution timestamp before assigning CAUSAL_ATTRIBUTED. It is not solely a timestamp-present predicate. It still supplies no causal identification design; verified exposure and uncontrolled pre/post are insufficient. The rerun produced CAUSAL_ATTRIBUTED with method pre_post and NDVI change 0.1. Move F12 before F13 acceptance and retain exposure verification as a distinct field.

### 5.7 Earlier forensic findings remain precisely scoped

There are nine genuine undefined-name rows in the earlier attachment, not an ambiguous 9-11 immediate NameError count. The guarded args expression does not raise that claimed error; postponed np annotations have a type-hint resolution problem rather than an immediate definition failure. Successful cold imports of the two packages do not make all deployment configurations portable. Duplicate class identity arises from loading the same source under different module names, not from successful circular imports causing identity duplication by themselves.

These distinctions matter during repair: restore lost ledgers/scenes and real scope rather than merely making exceptions disappear. F37-F40 already describe the proper scopes; the new report should preserve them without replacing them with blanket approval.

## 6. R3 traceability: correct counts, incorrect package examples

All 153 unique requirement IDs and all 14 domain counts match the companion register. The 65 multi-package requirements also match. However, the report’s domain-parenthesis examples do not faithfully copy the mapping:

| Domain | Listed package associations absent from the actual register |
|---|---|

| AB-ASM | F02, F05, F07, F20 |

| AB-DAT | F31 |

| AB-L10 | T10 |

| AB-ML | F23, T04 |

| AB-WM | F08, F21, F23 |

These eleven discrepancies do not mean the packages are irrelevant to those scientific domains; they mean the report misstates the explicit mapping it claims to verify. Generate the domain/package summary from the actual register rather than hand-copying broad related topics. AB-L10-001 is “Projection spatiale qualifiée”, with canonical geometry, resolution and authority criteria; the “institutional” shorthand is not its actual requirement title. Coverage is a planning relationship, not implementation or empirical validation.

## 7. Delivery order: all nine apparent inversions

The nine first-occurrence edges are:

| Package | First listed batch | Dependency | Dependency first batch |
|---|---:|---|---:|

| F35 | 0 | F09 | 3 |

| F38 | 0 | F01 | 1 |

| F38 | 0 | F02 | 1 |

| F38 | 0 | F09 | 3 |

| F38 | 0 | F31 | 10 |

| F39 | 0 | F01 | 1 |

| F39 | 0 | F09 | 3 |

| F32 | 1 | F09 | 3 |

| F13 | 5 | F12 | 7 |

Seven edges involve Batch 0 slices. The F32/F09 edge involves the explicitly partial dashboard slice in Batch 1. The F13/F12 edge is the genuine unsliced ordering conflict. Advancing F12 into scenario preparation resolves that edge.

However, moving F12 alone is not a complete execution schedule: the original table does not identify where full F38/F39/F40 acceptance occurs. F38 needs F31; F40 needs F38. F39 needs F09. Assign F39 completion after the durable trajectory boundary, and F38/F40 completion after canonical application integration. F35 already has its complete reliability-stage placement.

The report also assigns particular T packages to R gates as though these were explicit original package assignments. Gates describe outcomes and were not a complete package-to-release map. Make that interpretation a proposed schedule, not a verified quotation. Native instrument acquisition and research design can begin before complete capability acceptance. The addendum lists every target package and preserves these early-start distinctions.

## 8. Effort totals and sprint problems

The sums are correct:

| Scope | Low hours | High hours | Eight-hour engineer-days |
|---|---:|---:|---|
| F01-F40 | 1,044 | 1,780 | 130.5-222.5 |
| T01-T12 | 1,520 | 2,760 | 190-345 |
| Total | 2,564 | 4,540 | 320.5-567.5 |

These are the original planning ranges, not measured implementation times. They exclude the explicitly marked compute, hardware/field work, seasonal data and experimental replication. They regroup the earlier roadmap; do not add them a second time to that roadmap.

The proposed sprint synthesis is not consistent enough to schedule a team:

- Sprint 1 lists partial packages without assigning slice effort. Its 100-160 hours cannot be verified from full-package cards alone.
- Full Batches 3-6 sum to 344-596 hours before moving F12, rather than 200-350. After moving F12 into scenario preparation, that scope becomes 364-628 hours.
- Sprint 3 names F20-F29 and F30-F34, omitting F12 despite naming Batches 7-10. F12 must be assigned explicitly elsewhere. Partial/shared package boundaries must prevent double counting.
- The explicitly listed Sprint 4 packages F35/F36/T01/T02/T11/T12 sum to 408-716 hours, rather than 300-500.
- The four sprint ranges sum to 880-1,490 hours and do not describe the entire 2,564-4,540-hour program. T03-T10 are not included. Calling them sprints gives no duration, individual capacity, dependency acceptance or field-data availability.

Replace this with owner/capacity assignments and slice-specific budgets when work is allocated. Do not present the total sum as an independently validated cost or completion-date forecast.

## 9. Execution recommendation

Use the companion addendum to start small, reviewable changes. Repair the reproduced P0 evidence, timing, physical-accounting, execution and archive errors before allowing new capabilities to depend on their outputs. Keep existing ASMAE/MESIA improvements as regression requirements. Review PR #1 against consumers before any merge; open/draft status is not evidence of accepted remediation.

Close each package on its actual downstream criteria, not on a successful import or a generic suite status. Preserve the distinction between scientific priors, observations, synthetic modes and qualified unavailable results. The R3 target monograph remains unchanged and status-free. World-model rollout and Omega scientific knowledge require their stated independent data and experiment gates.

The uploaded report can be revised into a useful verification record once these corrections are made. Its blanket approval should be replaced with a scoped statement: structural counts and planning totals verified; selected software counterexamples reproduced; acceptance schedule corrected; empirical and complete-runtime readiness pending.

## 10. Fresh targeted receipts

```json
{
  "empty_no_gaussian": {
    "exception": "ContractViolation",
    "message": "Forecast empty_no_gaussian has neither predictive quantiles nor valid mean/std distribution"
  },
  "nonempty_missing_median": {
    "rmse": 0.0,
    "crps": 0.19999999999999998,
    "sharpness": 2,
    "coverage_hit": true
  },
  "empty_with_gaussian": {
    "rmse": 1.0,
    "crps": 0.6024413576276163,
    "sharpness": 3.29,
    "coverage_hit": true
  },
  "gaussian_center": {
    "rmse": 1.0,
    "crps": 0.6024413576276163,
    "sharpness": 3.29,
    "coverage_hit": true
  },
  "standalone_empty_quantile_crps": 0.0,
  "direct_monitor_empty_telemetry": {
    "violations": [
      "DURATION_EXCEEDED"
    ]
  },
  "pinned_reference_checks": {
    "references": 94,
    "targets": 94,
    "all94match": true,
    "targets_without_reference": [],
    "water_balance_blob": "e445703e0640c77df072b7fe72b2933352ebdfb6"
  }
}
```

The complete earlier probe collections were rerun locally on the pinned source overlay. No external requests, irrigation hardware, drone flight or field treatment formed part of those probes. Their fixtures exercise code behavior; the nitrogen number follows the production residual equation under fixed declared submodels.

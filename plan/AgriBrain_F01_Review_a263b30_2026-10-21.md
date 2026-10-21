# Independent F01 downstream-integration review — a263b30

Review date: 21 October 2026. Candidate: `a263b3033d6e637bef73ddf789d77659cd44e8f7`. Exact parent and observed main: `5344930dfc7fbab7f7277bf61f99fc252dd88bc6`. Branch: `feat/f01-downstream-integration-evidence`.

**The shared packet-path repair is verified, but the claimed downstream zero-influence work is not complete. Two reproducible residuals remain: A263-02 (P1), a native structural-adapter quality bypass that changes fused weed values and real L3 signals; and A263-01 (P2), an indirect conflict penalty from zero-quality diagnostics.** Both also reproduce on the exact parent. They are existing gaps exposed by the wider integration check, not regressions introduced by this commit.

I recommend completing these two bounded repairs before closing this batch or presenting it as end-to-end zero-influence coverage. The branch contains useful hardening; if merged as an incremental improvement, these findings must remain explicitly open. All 52 package FA milestones remain open. Other ready plan work can continue alongside these repairs.

## What was independently established

GitHub confirms main advanced to 5344930 and the new branch points to a263b30, whose first parent is exactly 5344930. The prior merge is therefore confirmed. Local source/Git state and remote branches were not changed by this review.

Five production Python modules changed. Their exact candidate blobs were fetched and syntax-compiled. Initial review staging contained 876 production/configuration files. Running actual fusion and L2 required nine additional existing production dependencies from rollout and layer2_uncertainty. These were fetched from the exact trees for both revisions: their blobs match on candidate and parent, and all original bytes remain unchanged. The final candidate and parent staging each contain 885 exact files. This was a review-export omission, not a missing file in the repository or a reason to stub production behavior.

Six lanes executed fresh authored production-consumer probes. Full fusion and downstream checks execute real Layer1FusionEngine.fuse(), real Layer2IntelligenceEngine processing, actual L3 output adapters and native feature construction where specified. Other retained lanes transparently isolate exact admission/history helper bodies. No repository test/audit assertions, earlier result files or reported test totals establish correctness here.

The reported 684 passing repository tests are not independently rerun in this review. The evidence consists of fresh source-level consumers, exact-parent controls and the normative F01/R3 contracts. Successful probe-driver exits mean both working repairs and documented counterexamples reproduced; they are not software all-clear counts.

## A263-02 — P1: native structural ingestion bypasses output reliability

The registered DroneStructuralAdapter accepts the native DroneRGBOutput through Layer1InputBundle.drone_structural_packages. That native output inherits reliability_weight from the common PerceptionEngineOutput contract. The adapter uses qa_score to assign confidence, reliability and update permission, but does not qualify or apply the inherited reliability_weight. See [layer1_fusion/adapters/drone.py:L39-L121](https://github.com/webClone/AgriWise/blob/a263b3033d6e637bef73ddf789d77659cd44e8f7/services/agribrain/layer1_fusion/adapters/drone.py#L39-L121) and the actual package route in [layer1_fusion/engine.py:L460-L500](https://github.com/webClone/AgriWise/blob/a263b3033d6e637bef73ddf789d77659cd44e8f7/services/agribrain/layer1_fusion/engine.py#L460-L500).

Consequently, fixing only the shared to_observation_packets bridge leaves this registered route open. The native fixture is a DroneRGBOutput with qa_score=1, canopy_cover_fraction=0.7 and weed_pressure_index=0.6. No evidence objects, model outputs or production methods are replaced.

| Native output quality | Actual L1 actionable values | Actual L1 evidence | Real L2/L3 result |
|---|---|---|---|
| reliability_weight=1 | canopy 0.7; weed 0.6 | reliability 1; positive confidence; state permission true | weed severity 0.48; has_drone_structural=true |
| reliability_weight=0 | **Same values** | **Same positive qualification** | **Same severity 0.48 and availability=true** |
| reliability_weight=NaN | **Same values** | **Same positive qualification** | **Same severity 0.48 and availability=true** |
| qa_score=0 | No actionable structural values | Contained | weed severity 0; availability=false |

In this native fixture, final L1 evidence/fused confidence is 0.5; the missing capture-time/freshness default bounds it. The problem is the positive qualification and contribution despite explicit zero/nonfinite output reliability, not the exact positive ceiling.

A second actual-engine control demonstrates contamination of independently qualified support:

| Real registered input | Fused weed index | Actual L3 weed severity |
|---|---:|---:|
| Qualified sibling alone, weed=0.3 | 0.30 | 0.24 |
| Add weed=0.6 sibling with reliability_weight=0 | **0.45** | **0.36** |
| Add weed=0.6 sibling with reliability_weight=NaN | **0.45** | **0.36** |

The invalid sibling is assigned reliability 1 by the adapter and participates in numerical fusion. This changes the actual derived value, then real L2 attribution and L3 operational signals. Native feature construction copies those signals. This is stronger evidence than merely observing an eligibility flag.

Candidate and exact parent reproduce the same results. The shared packet-path changes do not introduce this bypass; they do not reach it. In this sparse fixture the actual L3 context is diagnostic-usable, but usable_for_layer3=false; data health is degraded (overall0.38, confidence ceiling0.5). The result establishes contaminated admitted/fused values and real downstream diagnostic/decision-feature content. It does not establish a fully usable final decision, dispatched prescription, field action, trained-model change or physical crop damage.

**Bounded repair:** qualify mission QA and output reliability before any float coercion or evidence construction in the registered structural adapter. Explicit zero must remain zero; malformed/nonfinite/boolean quality must not become default positive support. Carry the effective bound into source health, evidence confidence/reliability, diagnostic status and update permission. Apply equivalent handling to typed and dictionary forms. Reuse a shared qualifier where appropriate so native and packet paths cannot disagree.

**Acceptance criteria:** zero/NaN-quality native outputs add no actionable contribution; the mixed sibling remains weed=0.30/severity=0.24; valid finite quality and valid zero numeric values survive. Preserve diagnostic provenance. Do not obtain a passing result by dropping all native structural inputs, including the positive control.

## A263-01 — P2: diagnostic conflicts still reduce qualified confidence

The shared bridge now correctly produces diagnostic-only evidence with confidence=reliability=0 and state_update_allowed=false. However, the full engine sends all ledger evidence through conflict detection before computing final confidence. Scope-conflict selection does not filter diagnostic, zero-quality or state-ineligible evidence. The confidence model applies the resulting penalty to the qualified counterpart.

The exact code path is [layer1_fusion/engine.py:L236-L249](https://github.com/webClone/AgriWise/blob/a263b3033d6e637bef73ddf789d77659cd44e8f7/services/agribrain/layer1_fusion/engine.py#L236-L249), [layer1_fusion/conflict_resolver.py:L356-L395](https://github.com/webClone/AgriWise/blob/a263b3033d6e637bef73ddf789d77659cd44e8f7/services/agribrain/layer1_fusion/conflict_resolver.py#L356-L395), [layer1_fusion/confidence_model.py:L69-L105](https://github.com/webClone/AgriWise/blob/a263b3033d6e637bef73ddf789d77659cd44e8f7/services/agribrain/layer1_fusion/confidence_model.py#L69-L105) and [layer1_fusion/fusion_rules.py:L291-L327](https://github.com/webClone/AgriWise/blob/a263b3033d6e637bef73ddf789d77659cd44e8f7/services/agribrain/layer1_fusion/fusion_rules.py#L291-L327).

| Actual supported input pair | Qualified sensor evidence confidence | Qualified fused confidence | Qualified fused value |
|---|---:|---:|---:|
| Valid point SENSOR_IOT vegetation_fraction=0.20 alone | 0.95 | 0.95 | 0.20 |
| Add disagreeing plot DRONE value=0.95, output reliability=0 | **0.85** | **0.85** | 0.20 |
| Same added DRONE with NaN or ±Inf quality | **0.85** | **0.85** | 0.20 |
| Add agreeing zero-quality DRONE value=0.20 | 0.95 | 0.95 | 0.20 |
| Add qualified disagreeing DRONE | 0.85 | 0.85 | 0.20 |

Eight zero/nonfinite output-reliability or variable-confidence variants reproduce this residual. In every invalid candidate case the DRONE item itself remains confidence/reliability=0, diagnostic-only and state-ineligible. The disagreement still creates SCOPE_MISMATCH and the minor-conflict ceiling lowers the valid sensor's non-diagnostic fused confidence.

The unchanged numeric value is explicitly retained in the evidence. The measured defect is value-dependent confidence influence on qualified evidence, not direct numeric contribution or a claimed physical-state change. An ordinary S2-only baseline can mask this effect because its own fresh-evidence ceiling is already 0.85; the supported point-sensor baseline provides the necessary positive control.

The exact parent reproduces the same indirect penalty as well as its old direct zero-quality promotion. Thus this is a partial-fix residual.

**Bounded repair:** separate explanatory diagnostic conflict reporting from conflicts allowed to affect qualified state confidence. Keep the diagnostic ledger and disagreement visible. Require qualified contributing support before applying confidence penalties or other scientific influence to a valid counterpart. Preserve the actual qualified-disagreement penalty.

**Acceptance criteria:** adding zero/nonfinite-quality DRONE to the valid sensor leaves its value=0.20 and confidence=0.95; agreeing and absent controls remain equal; qualified disagreeing evidence still produces the intended penalty. Compare the final non-diagnostic fused outputs, not just the bad item's weight.

## Working parts of this commit

The actual shared native route is PerceptionEngineOutput → shared packetizer → canonical source package → registered perception adapter → evidence bridge → real fusion engine → output adapters.

| Change claimed | Independent disposition |
|---|---|
| Native shared adapter sets scene QA to zero when effective quality is zero/invalid | Verified in exercised inputs. |
| Bridge bounds reliability by scene score and packet reliability | Verified. |
| Zero confidence/reliability denies state updates and becomes diagnostic | Verified at the bridge and final validation boundary. |
| Validator rejects a forged zero-quality update claim | Verified with the exact ZERO_CONFIDENCE_OR_RELIABILITY_CANNOT_UPDATE_STATE reason. |
| Confidence/reliability floors preserve authentic zero | Verified. |
| Zero-weight fallback no longer assigns confidence 0.10 | Verified: direct arithmetic boundary returns confidence 0 and source weights 0. |
| Same-scope invalid packet does not change qualified state-like projections | Verified for value, confidence, uncertainty, freshness and numeric source weights in the paired fixtures. |
| Full zero influence across every downstream ingestion path | **Partial: A263-01 and A263-02 remain.** |

The deliberately forced all-zero-weight arithmetic fixture bypasses validation to exercise the fallback branch. Its unweighted numeric mean is diagnostic coverage of that helper, not proof of an accepted physical state update. The real shared route denies update permission upstream.

Fresh exact-parent execution shows why the changes matter: the parent promotes zero-quality evidence to state eligibility, floors it to confidence 0.01, and can emit a zero-weight fused feature at confidence 0.10. In the same-scope baseline pair, it can also tighten uncertainty from 0.05 to 0.0354 despite zero raw weight. The candidate closes those direct paths.

Legitimate numeric zero with positive quality remains valid, as do finite quality 0.4 and independently qualified per-variable siblings. These positive controls prevent confusing a zero measurement with missing information.

## Structural transport qualifications

The decision lane distinguishes three paths:

1. Shared packets using the literal canopy_cover_fraction/weed_pressure_index variable names are not recognized as evidence by the current generic payload mapping, even with positive quality.
2. The specialized DronePacketizer emits summary_metrics, which the exercised generic packet bridge also does not consume into evidence, including its positive control.
3. The direct registered DroneStructuralAdapter route does produce nonvacuous real L2 weed attribution and actual L3 signals—and exposes A263-02.

Therefore, a negative result from the first two paths alone cannot demonstrate downstream isolation. The audit uses the third path for the actual defect and positive control. Separate typed-L2 boundary projections are clearly labeled adapter-only fixtures; they are not presented as real L2 transport.

Likewise, actual L2 processing does not transport the named canopy value into a same-named VegetationFeature in the exercised route. Canopy projection tests validate a typed boundary, while actual weed attribution supplies the full-chain positive evidence. This is an existing integration qualification for future work, not an additional blocker invented from a negative fixture.

## Retained repairs and monograph alignment

Fresh lanes retain the seven named R415 software boundaries and all three R39 closures. Water candidate and exact parent each pass the 45-variant/52-check matrix: generic EXCLUDED beside TDR in either order admits no rows, has zero analysis increment and MODELLED authority; independent satellite restrictions do not suppress qualified TDR. Training retains 22 closure controls, the real legacy415-writer/39-reader/candidate-reader contrast on identical ledger bytes, and four bounded training-item consumers. R51901/R51902 target files remain byte-identical; those prior software closures are retained without claiming a new whole-irrigation-suite execution.

F01 in the master plan, lines 151–177, maps to AB-DAT-005, AB-DAT-006, AB-ARC-005 and AB-ARC-006. The three normative plan files match candidate blobs. The supplied R3 PDF, full-text extraction and scientific extract identities are checked; the PDF SHA-256 is `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`.

| Contract | Current assessment |
|---|---|
| Numeric admission and zero/missingness | Shared route improved; native structural reliability bypass violates the same requirement. |
| Provenance per component | Retained role/scoping repairs pass; direct structural quality must govern the actual source contribution. |
| Authority from admitted support | Direct structural and indirect conflict influence still exceed their qualified support. |
| Bounded degradation without fallback promotion | Packet/floor/fallback fixes work; the two remaining routes require closure. |

All 52 FA milestones, including F01, remain unchecked. This preserves the register correctly; unchecked rows do not mean every implementation is absent. This review does not infer a universal hardware prerequisite for all packages or establish Omega/world-model production readiness.

## Evidence scale and next work

The six appendices provide exact inputs, source ranges, manifests and limits. Some initial lane receipts record876 staged files; the later full-engine work and final separate-layout replay use885 after the nine exact dependencies were added. Historical39/415 controls retain876. Imported/staged counts establish source identity, not branch coverage. Counts measure different things and are not added into a synthetic test-suite total.

| Lane | Fresh evidence |
|---|---|
| Native producers | 18 expanded checks; retained prior controls and exact-parent leak fingerprints |
| Component ledger/full fusion | 112 component fixtures and 56 real full-engine cases per revision; A263-01 reproduced |
| Water/decisions | 45 water variants; 16 paired shared/canonical structural fixtures plus 15 specialized-route variants per revision (47 real L1/L2 runs); A263-02 reproduced |
| Weather/crop | 43 cases; 241 checks; actual engineered crop inputs |
| Training | 22 closure controls, four bounded L1 consumer controls, actual freshly generated historical ledgers |
| RF | 80 cases; 18 controls; actual private queue admission, no posterior commit |

Finish the native structural reliability repair first, then the conflict-penalty qualification. Repeat the same positive/negative/mixed source matrix and retain the earlier closures. No broader feature implementation is needed to make these two decisions concrete. Independent ready plan packages can proceed in parallel.

No production/Git edits, repository audit/test correctness proof, live providers, services, controllers, radio transmissions, drones, field actuators, optimizer fitting or prescription execution occurred. The actual full-engine checks run offline on private software fixtures. The portable evidence bundle excludes production-source copies, repository tests/audits and raw private ledger/queue stores. It includes the authored harnesses, result receipts, exact source manifests, normative references and reconstruction instructions. Source-object reconstruction is read-only; separate-layout replay verifies both corrected behavior and the residual failures.


---

# Specialist appendix: Actual full fusion, conflict influence and component controls

# Independent bounded F01 fusion and ledger review

Candidate: `a263b3033d6e637bef73ddf789d77659cd44e8f7`  
Exact parent: `5344930dfc7fbab7f7277bf61f99fc252dd88bc6`

**The direct perception-quality repair works in the exercised native route, but the full zero-influence claim remains partial. A263-01 (P2) is an open, pre-existing indirect-confidence residual: a zero-quality DRONE diagnostic still lowers qualified sensor evidence and non-diagnostic fused confidence from 0.95 to 0.85 through a scope-conflict penalty.** The qualified sensor's value remains 0.20. Hold acceptance of this bounded zero-influence claim until that seam is repaired. This is not a whole-project or all-F01 completion determination.

## A263-01 — zero-quality diagnostics still penalize qualified evidence

The fresh actual-engine baseline contains one canonical `SENSOR_IOT` point observation, `vegetation_fraction=0.20`, with packet scene score and reliability 1.0. The registered sensor adapter, actual confidence model, actual fusion rules, context invariants, and real Layer 2/10 output construction all run. Baseline sensor evidence confidence and the point-scoped, non-diagnostic fused feature confidence are both 0.95.

Add a native `PerceptionEngineOutput(engine_family=DRONE)` containing `vegetation_fraction=0.95` with output `reliability_weight=0.0`. The native shared packetizer produces the packet; its plot scope is unchanged. It is wrapped in a canonical `Layer0SourcePackage(source_family="perception")` and passed through the registered perception adapter to `Layer1FusionEngine.fuse()`. Packet source DRONE maps to evidence source family `drone_structural`. No evidence objects or production functions are replaced.

| Actual engine fixture | DRONE confidence / reliability | DRONE diagnostic / state permission | Valid sensor evidence confidence | Non-diagnostic sensor fused confidence | Sensor fused value |
|---|---|---|---:|---:|---:|
| Valid sensor only | Absent | Absent | 0.95 | 0.95 | 0.20 |
| Add disagreeing DRONE with reliability 0 | 0 / 0 | true / false | **0.85** | **0.85** | 0.20 |
| Add disagreeing DRONE with reliability NaN, +Inf, or −Inf | 0 / 0 | true / false | **0.85** | **0.85** | 0.20 |
| Add disagreeing DRONE with variable confidence 0, NaN, +Inf, or −Inf | 0 / 0 | true / false | **0.85** | **0.85** | 0.20 |
| Add agreeing DRONE value 0.20 with reliability 0 | 0 / 0 | true / false | 0.95 | 0.95 | 0.20 |
| Add qualified disagreeing DRONE | 0.72 / 0.80 | false / true | 0.85 | 0.85 | 0.20 |

Eight zero/nonfinite-quality disagreement cases reproduce the confidence change. The absent and agreeing controls show that this is value-dependent indirect influence, rather than a diagnostic count changing. The qualified disagreement control preserves the intended penalty for sound evidence. Sensor source weight remains 1.0 and its value remains 0.20; the measured defect is qualified confidence alteration. No physical posterior, training weight, solver or prescription effect is inferred.

The production chain is precise:

- `services/agribrain/layer1_fusion/engine.py:236–249` sends **all** ledger evidence to conflict detection, then applies the resulting conflicts to confidence before fusion.
- `services/agribrain/layer1_fusion/conflict_resolver.py:356–395` selects point and broad numeric evidence, compares variable groups across source families, and emits minor `SCOPE_MISMATCH` conflicts. Selection at `:364–365` does not check positive quality, diagnostic status, or state permission.
- `services/agribrain/layer1_fusion/confidence_model.py:69–96` applies a minor conflict ceiling of 0.85 to either referenced evidence item; `:99–105` mutates the evidence confidence in place.
- `services/agribrain/layer1_fusion/fusion_rules.py:291–327` then uses the valid sensor's reduced confidence in its non-diagnostic fused feature.

The exact parent reproduces the same sensor 0.95→0.85 penalty and also retains the former direct DRONE promotion. Thus this is a residual in the repair's claimed zero-influence boundary, not a newly introduced confidence penalty. An S2-only positive control would mask this particular effect because its fresh-evidence ceiling is already 0.85 (`freshness.py:24–28`); the valid point sensor establishes the effect with supported production types.

Recommended bounded correction: retain zero-quality diagnostics and their explanatory conflicts for the ledger/audit, while preventing conflicts supported solely by non-authoritative, zero-quality components from reducing qualified state-evidence confidence. Keep the qualified disagreement control. Distinguish diagnostic conflict reporting from authority-affecting penalties rather than suppressing the diagnostic record.

Fresh proof: `full-fusion-candidate-results.json` → `scope_residual`, and named cases `scope_sensor_baseline`, `scope_sensor_plus_drone_reliability_zero`, the seven sibling disagreement cases, `scope_sensor_plus_drone_zero_agrees`, and `scope_sensor_plus_qualified_drone_disagrees`. `full-fusion-comparison.json` explicitly records `candidate_indirect_zero_influence_claim=false`; successful harness execution does not label that claim as passing.

## Direct repair and fresh exact-parent controls

`full_fusion_probes.py` executes 56 actual `Layer1FusionEngine.fuse()` cases for each snapshot in fresh interpreter processes. The native route is `PerceptionEngineOutput` → native shared `to_observation_packets()` → canonical `Layer0SourcePackage` → registered `PerceptionAdapter` canonical dispatch → packet bridge → actual engine validation/ledger/alignment/freshness/conflicts/confidence/fusion/invariants → actual Layer 2/10 output adapters. No raster inputs, ASMAE output, provider inference or acquisition are supplied. The DRONE canonical envelope uses the perception package slot because the separate `DroneStructuralAdapter` expects native structural outputs and does not implement canonical-envelope dispatch. This is an explicit route limit.

| Named boundary or fixture | Candidate result | Fresh parent result |
|---|---|---|
| Zero/nonfinite output reliability or variable confidence, bad-only native DRONE | Confidence/reliability remain 0; diagnostic only; no state-updatable feature | Evidence becomes state eligible; confidence floor raises evidence to 0.01 and fused zero-weight fallback yields confidence 0.10 |
| Same-scope positive baseline + bad native DRONE | Value, confidence, uncertainty, freshness and numeric source weight unchanged | Value stays 0.20, but uncertainty tightens from 0.05 to 0.0354 even though bad raw weight is zero |
| Mixed per-variable quality in one native output | Invalid `vegetation_fraction` is diagnostic; valid `bare_soil_fraction=0.40` survives at confidence 0.72 | Invalid vegetation becomes a non-diagnostic feature at confidence 0.10 |
| Legitimate value 0 with positive quality | Preserved as non-diagnostic numeric 0 at confidence 0.72 | Also preserved |
| Validator: state-eligible zero confidence or zero reliability | Explicit `ZERO_CONFIDENCE_OR_RELIABILITY_CANNOT_UPDATE_STATE` rejection | No zero-quality guard |
| Validator: nonfinite confidence or reliability | Rejected by bounds | Rejected by bounds |
| Context floor on diagnostic confidence/reliability 0 | Exact zero preserved; no floor violation | Raised to confidence 0.01 / reliability 0.05 |
| Deliberately bypassed validator: all-zero-weight numeric fusion | Arithmetic mean 0.50, confidence 0, source weight 0, `ZERO_WEIGHT_UNWEIGHTED_AVERAGE` | Arithmetic mean 0.50, fabricated confidence 0.10 |

The bad-only and paired same-scope cases cover zero, NaN, ±Inf, negative, boolean, numeric-string and malformed-string reliability/confidence separately. Mixed-variable controls use those same eight variable-confidence values. These state comparisons exclude diagnostic features and data-quality summaries, and compare value, confidence, uncertainty, freshness, and numeric source weights; full provenance and diagnostics are retained in JSON. Diagnostic source membership or feature availability alone is not interpreted as state influence.

Candidate source support is `layer0/perception/common/packet_adapter.py:165–181`, `layer1_fusion/adapters/observation_packet.py:127–137,190–209`, `evidence_validation.py:61–67,103–104`, `context_invariants.py:197–223`, and `fusion_rules.py:267–288,291–327`, all under `services/agribrain/`. The exact new validator string is `ZERO_CONFIDENCE_OR_RELIABILITY_CANNOT_UPDATE_STATE`. The direct fallback probes intentionally bypass component validation and force state flags for arithmetic coverage; they are not accepted engine paths or proof of physical state assimilation. The full native route rejects such state permission upstream while retaining zero-quality diagnostics.

## Retained R415-02 and R415-05 controls

`probes.py` adapts only the earlier authored harness code and executes **112 fresh component/ledger fixtures in seven groups per snapshot**. It does not read old results, reports, tests, audits or claimed completion artifacts. Both candidate and exact parent retain the named closures:

- **R415-02, bounded closed:** typed/dictionary RECONSTRUCTION declarations, restrictive alias conflicts, and a pre-existing typed reconstruction status remain reconstruction, diagnostic only, and state-ineligible after registered Sentinel2 adapter and source-context truth normalization. Default confidence 1.0 is conservatively quarantined at the reconstruction ceiling; valid confidence 0.25 retains only diagnostic `ndvi_evidence=0.0`.
- **R415-05, bounded closed:** actual SOILGRIDS/environment canonical routing rejects numeric/malformed strings, booleans and infinity for known quantitative clay before ledger/fused soil feature admission, while retaining valid sand. Missing clay is omitted; clay 0 and finite 30 remain admitted. Packet-level mixed-row availability does not admit the invalid component.

The remaining groups retain finite/zero NDVI and EVI, role/status restrictions, invalid-only and all-missing row rejection, component-specific admission, and strong typed zero serialization/variance controls. Source references are stored in `results.json` and `parent-results.json` and bound by the component manifests. These tests observe component/ledger/fused-feature boundaries; the actual full orchestration above supplies the additional confidence and invariant coverage.

## Identity, execution and limits

Normative basis was read directly from `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:151–177` (F01 explicit admitted/rejected components, restrictive roles, zero preservation and actual influence) and `current-plan-review/R3_current_scientific_sections.txt:675–681,738–744` (AB-DAT-005/006 and AB-ARC-005/006). Those files are separate from candidate correctness claims; their hashes are in the full manifests.

The exact fetched Git trees and commit metadata establish candidate and first-parent identities. Each full worker checks all **885 staged source files against exact Git blob hashes both before and after execution**, including the nine exact missing rollout/uncertainty dependencies staged by the parent reviewer. The previous 876 staged files are unchanged. All 82 imported repository file paths are individually bound by Git blob, SHA-256, byte count and module name in each full manifest. Component runs bind 49 imported repository files each. There are no production/Git edits, AST-replaced functions, repository-module stubs, test/audit correctness evidence, service/provider/hardware calls, or live inference. Socket connect entry points fail closed. Only this lane's harnesses and outputs are written here.

Full worker outputs include actual evidence, fused features, state summaries, diagnostics, conflicts, provenance, audit records, and real Layer 2/10 payloads for each case. Layer 3 decisions are outside this lane. Fixed eligible fixture timestamps do not establish F02 temporal correctness. No conclusions about physical posteriors, training, prescribing, execution, unexercised variables, all perception engines, or whole-F01 completion follow from these results.

Reproduce from the provided sibling snapshots:

```bash
python review-a263b30-f01/ledger/probes.py
python review-a263b30-f01/ledger/probes.py --parent
python review-a263b30-f01/ledger/full_fusion_probes.py
```

The comparison driver succeeds only when the direct candidate repairs, exact-parent regressions, and the measured open indirect-confidence residual reproduce. Strict JSON uses explicit markers for nonfinite fixture values. Reproducible deliverables comprise both harnesses, candidate/parent results and executed-file manifests, full worker stdout/stderr, and `full-fusion-comparison.json`.


---

# Specialist appendix: Native producers and source-aware role preservation

# Bounded native producer / packet / bridge F01 verification — a263b30

Candidate: `a263b3033d6e637bef73ddf789d77659cd44e8f7`. Exact first parent: `5344930dfc7fbab7f7277bf61f99fc252dd88bc6`.

The native perception quality correction is reproduced at the packet, direct bridge, registered adapter and package-aware admission boundaries. All **18 expanded checks pass** on the candidate. All **21 prior controls were rerun**: 20 keep their prior expected outcome; the final-defense control that deliberately puts zero quality on an item still requesting updates now correctly quarantines. That historical assertion is recorded as false rather than omitted. The identical script freshly executed against the exact parent reproduces all 21 old expectations and the former zero-quality/update-permission leak. No new state-admission blocker was reproduced in this bounded lane. An unchanged malformed/default-QA availability limitation is separately recorded below.

This establishes evidence values, quality and permissions at admission. It does **not** measure posterior influence, physical state deltas, solver rows, training weights or full F01 completion.

## Actual route and execution boundary

The probe constructs production `PerceptionEngineOutput` and `PerceptionVariable` dataclasses with DRONE family and mapped `vegetation_fraction`. It calls the actual `to_observation_packets`, the default `wrap_perception` call used by the actual runner, registers a real `PerceptionAdapter` in `SourceRegistry`, retrieves it through `get_adapter('perception')`, follows its canonical `Layer0SourcePackageAdapter` delegation and admits the resulting items with the real package as `source_context` to an actual `EvidenceLedger`. No reviewer-created evidence substitutes for these native routes. The separate final-defense controls deliberately mutate a genuine adapter item and are labeled separately.

The direct bridge is also executed independently on each native packet, before the registered adapter route. Results preserve all three stages: `direct_bridge`, `before_source_context_admission` and final `accepted`.

The whole fusion engine is not initialized or run. The probe extracts and compiles the exact, unmodified AST definition of `Layer1FusionEngine._admit_evidence_or_quarantine`, including its production relative imports, and calls it. Candidate and parent method extent is `engine.py:807–824`; source SHA-256 is `6f91fd5d59bb4273941d6e6c6512c2da028f070320a61df91f7a95dc42fab23c`. The normal engine run source-normalizes with each package at lines 154–159, validates at 163–172, and adds to ledger at 174–180; the bounded admission method applies the same source normalization/validation/ledger boundary. Temporal alignment, fusion rules and numerical solvers are outside execution scope.

## Native quality matrix and exact parent contrast

Each of output reliability, variable confidence and scene QA is independently set to **0, 0.4, Inf, NaN, True, False, malformed `bad`, null and -0.1**: 27 native cases per revision. The other quality fields remain 1. Explicit native `qa_flags=['CLEAN']` reaches the changed sanitizer in every case. Every candidate case produces one packet, accepts one evidence item and quarantines none. Every source envelope validates without violations.

| Native input | Candidate packet | Candidate direct bridge, registered adapter and admission | Exact parent admitted result |
| --- | --- | --- | --- |
| Reliability or variable confidence 0 / invalid | reliability weight 0; scene score 0; valid-pixel fraction 0 | confidence 0; reliability 0; diagnostic true; update false | confidence 0; reliability 1; diagnostic false; update true |
| Scene QA 0 / invalid | scene score 0; valid-pixel fraction 0 | confidence 0; reliability 0; diagnostic true; update false | confidence 0; reliability 0; diagnostic false; update true |
| Reliability or variable confidence 0.4 | reliability weight 0.4; scene score 1 | confidence 0.4; reliability 0.4; diagnostic false; update true | confidence 0.4; reliability 1; diagnostic false; update true |
| Scene QA 0.4 | reliability weight 1; scene score 0.4 | confidence 0.4; reliability 0.4; diagnostic false; update true | same admitted values/permissions |

“Invalid” above includes Inf, NaN, both booleans, malformed, null and negative input. On the parent, invalid scene QA is constructor-sanitized to scene score 0, but `valid_pixel_fraction` retains the invalid original; candidate sanitizes both. Results encode nonfinite receipts as `nonfinite_repr` and are strict JSON (`allow_nan=False`).

A **legitimate physical value 0.0** with quality 1 remains value 0, confidence/reliability 1, nondiagnostic and update-allowed. With reliability 0.4 it remains value 0, confidence/reliability 0.4 and update-allowed. Both preserve the numeric value through dataclass-to-JSON serialization/deserialization and all three evidence stages. Zero quality is therefore distinguished from zero physical value.

Eight two-variable native outputs test per-variable isolation: `vegetation_fraction=0.2` receives zero or invalid confidence while the independent `bare_soil_fraction=0.0` sibling has confidence 0.4. Both packets and both ledger items survive. The bad-quality item becomes confidence/reliability 0, diagnostic and update-denied; the zero-value sibling remains confidence/reliability 0.4, nondiagnostic and update-allowed. The parent keeps reliability 1 and update permission on the bad-quality item.

## Retained controls and final defense

All prior typed/dictionary controls were freshly executed: 40 role-alias cases across five aliases; four restrictive/conflicting roles; explicit dictionary reliability qualification and absence/default behavior; invalid and zero primary quality without fallback substitution; typed invalid weight/QA; valid zero NDVI JSON round trip; invalid numeric NDVI quarantine; native DRONE status roles; native sensor QA and explicit update denial; and final quality validator controls.

With positive native quality, DRONE observed is accepted with confidence 1 and update permission; simulated, estimated, fallback and unavailable remain respectively 0.20 / 0.75 / 0.35 / 0.00, diagnostic and update-denied at package-aware admission. They do not acquire real-provider-product, scientific-surface, prescription or current-1m permission. The same five roles with zero quality remain zero-confidence/reliability, diagnostic and update-denied. Unavailable remains production-usable false.

The native sensor route still constructs actual normalized reading, QA and context-package dataclasses, retrieves the registered `SensorAdapter` and uses package-aware admission. Inf, NaN, True, malformed and zero reliability yield confidence/reliability 0, diagnostic true and update false; 0.4 remains 0.4 with update permission; explicit denial remains denied.

Final-defense mutations set only confidence or reliability on a genuine adapter item. True and NaN still quarantine. Positive 0.4 still survives. **Zero quality plus an unchanged update request now quarantines** with `ZERO_CONFIDENCE_OR_RELIABILITY_CANNOT_UPDATE_STATE`, where the exact parent accepted it. This is why the old `R415_04_final_quality_zero_and_finite_survive` combined check is false on candidate and true on parent. All 21 old results remain visible in `inherited_checks`; the 20 unchanged checks and explicit replacement expectations are asserted.

## Default QA flags neighbor

A second 27-case native matrix omits explicit QA flags, exercising `_collect_flags`. Twenty-five candidate cases complete; all completed zero/invalid-quality routes are zero-gated. Malformed `bad` and null **scene QA** raise `TypeError` at the automatic comparisons in `packet_adapter.py:258–260`, before any packet is returned or adapter/ledger runs. The exact parent has the same two exceptions. These are recorded as unchanged fail-closed availability limitations, not as sanitizer-produced diagnostic evidence, and do not demonstrate state leakage. Native malformed/null QA handling with supplied flags is verified above. The report makes no general claim that every malformed producer output returns a diagnostic item.

## Exact candidate source references

All paths below are beneath supplied `source/`.

| Behavior | File and exact lines |
| --- | --- |
| Actual native DRONE source mapping | `services/agribrain/layer0/perception/common/packet_adapter.py:48` |
| Native finite/nonboolean reliability/confidence and per-packet QA | `services/agribrain/layer0/perception/common/packet_adapter.py:165–182` |
| Automatic QA flags called before sanitizer; unchanged comparisons | `services/agribrain/layer0/perception/common/packet_adapter.py:152–155,250–262` |
| Default wrapper / actual runner call | `services/agribrain/layer0/wrappers.py:710–743`; `services/agribrain/layer0/runner.py:170–179` |
| Actual registry registration/retrieval / adapter delegation | `services/agribrain/layer1_fusion/source_registry.py:60–72`; `services/agribrain/layer1_fusion/adapters/perception.py:23–31` |
| Direct bridge intersects scene score with packet reliability | `services/agribrain/layer1_fusion/adapters/observation_packet.py:127–137` |
| Direct bridge zero-quality diagnostic/update gates | `services/agribrain/layer1_fusion/adapters/observation_packet.py:207–209` |
| DRONE source-aware status and permission preservation | `services/agribrain/layer1_fusion/truth_bridge.py:399–422` |
| Native sensor finite quality and update gate | `services/agribrain/layer1_fusion/adapters/sensors.py:73–105` |
| Final strict numeric quality / zero-quality update refusal | `services/agribrain/layer1_fusion/evidence_validation.py:61–67,103–104` |
| Actual isolated admission method / static normal run | `services/agribrain/layer1_fusion/engine.py:807–824,154–180` |

There are 56 actual imported source files and two static references. Four of those 58 files differ from exact parent: packet adapter, observation-packet bridge, evidence validator and `fusion_rules.py`. The latter is imported but its solver behavior was not executed or established by this lane. Exact hashes and blobs are recorded in `parent-boundary-comparison.json`.

## Normative scope and identity

The selected normative repair plans are exactly the master, work-package task list and sequencing addendum under `sr-team-review/plan/`. Their bytes freshly match candidate and parent Git blobs. Master F01 is lines 151–177: source roles survive typed/dictionary adapters (170); invalid numeric values cannot alter state/training weight (175); legitimate zero survives round trips (176); authority/counts follow admitted components (177). This lane covers the native producer/adapter/admission subset of those criteria. Five F01 rows and all **52 FA rows** are unchecked. These checkbox facts are explicitly asserted as register status, not implementation proof.

R3 AB-DAT-005 is extract lines 675–677; AB-DAT-006 679–681; AB-ARC-005 738–740; AB-ARC-006 742–744. PDF, full-text extraction and supplied scientific-extract bytes were freshly checked against pinned SHA-256 values:

| Supplied reference | SHA-256 |
| --- | --- |
| `sr-team-review/monograph-source/AgriWise_AgriBrain_Monographie_Maitre_FR_R3.pdf` | `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f` |
| `sr-team-review/R3-full-text.txt` | `472d8f890098c5470b674ca468fb3e456a14bfd86c10935770fd7fb796a9c66d` |
| `current-plan-review/R3_current_scientific_sections.txt` | `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c` |

These are supplied normative references, not tracked candidate production files. The optional detailed implementation plan is excluded from normative/correctness evidence.

`verify_metadata.py` freshly verifies candidate/first-parent identity and untruncated trees, **876/876 candidate and 876/876 parent** production/config files by Git blob/SHA-256/byte count, the actually imported files against those manifests, the three selected plans, R3 identities, F01/FA register counts and fresh result expectations.

## Reproduction and scope limits

From `review-a263b30-f01/`, preserving the supplied sibling source/reference layout:

```sh
PYTHONDONTWRITEBYTECODE=1 python platform/wrapper_probes.py
PYTHONDONTWRITEBYTECODE=1 python platform/wrapper_probes.py --source ../review-5344930-f01/source --output parent-results.json --parent-control
PYTHONDONTWRITEBYTECODE=1 python platform/verify_metadata.py
```

Scripts are self-contained and do not import prior reviewer scripts. Fresh receipts are `results.json`, `parent-results.json`, `source-manifest.json`, `parent-source-manifest.json`, `import-manifest.json`, `plan-results.json`, `parent-boundary-comparison.json` and console captures. `authored-manifest.json` pins both reviewer scripts. Prior script logic was adapted and all results freshly executed.

Only reviewer-authored `platform/` files were written. Production source and Git were not edited. Repository tests, audits, historical outputs and generated repository artifacts were not used as correctness proof. No service, provider, network, controller, radio, drone hardware, full fusion run, optimizer, model fitting, training path or durable state mutation ran. Ledger counts here count admitted evidence items; they do not establish observations assimilated, zero posterior influence or zero training influence. Other F01 lanes and full qualification remain for the consolidated review.


---

# Specialist appendix: Downstream structural signals and retained native water controls

# Downstream structural and retained water F01 review

Candidate: `a263b3033d6e637bef73ddf789d77659cd44e8f7`. Exact parent: `5344930dfc7fbab7f7277bf61f99fc252dd88bc6`. Executed 2026-10-21.

The corrected canonical packet boundary prevents zero/NaN-quality canopy and weed fixtures from becoming actionable L1 features or positive actual L3 weed signals. A separate native structural route remains open: the registered `DroneStructuralAdapter` ignores the `reliability_weight` inherited by native `DroneRGBOutput`. Zero and NaN reliability therefore produce the same actionable canopy/weed and actual L3 weed severity as reliability one. Fresh exact-parent execution reproduces this residual identically; it is an unclosed F01 boundary, not a newly introduced regression.

The retained water lane passes all 52 checks over 45 variants on both versions, including the corrected R39-01 generic EXCLUDED behavior. It does not reproduce the obsolete 39b94d8 failure against parent 5344930.

## A263-02 — P1: Native structural adapter promotes zero/NaN reliability

The input is an actual `DroneRGBOutput` instance with `is_valid=True`, `qa_score=1`, `canopy_cover_fraction=.7`, `weed_pressure_index=.6`, and inherited `reliability_weight=0` or NaN. The harness supplies it through `Layer1InputBundle.drone_structural_packages`; it then executes the real registered adapter, full `Layer1FusionEngine.fuse`, real `Layer2IntelligenceEngine.analyze`, actual `_extract_drone_structural_signals` / `build_layer3_context`, and native `build_decision_features`. No typed L2 projection is used for this finding.

`layer0/perception/common/contracts.py:125–130` declares the inherited quality fields; `drone_rgb/schemas.py:73–86` establishes `DroneRGBOutput` inheritance and structural fields. `layer1_fusion/engine.py:475` gathers the native structural packages. In `adapters/drone.py:69–78`, confidence, reliability and update permission depend only on `qa_score`. Lines 99–104 emit these capabilities, and lines 111–121 emit canopy and weed. There is no read of the inherited reliability weight. With mission QA one, the adapter initially emits confidence .8, reliability 1 and update permission true even when the native output explicitly reports reliability zero or NaN. The real freshness/confidence pipeline leaves confidence .5 in this fixture; it does not repair the lost quality restriction.

| Native direct input, both candidate and parent | Actionable canopy | Actionable weed | Real L3 `has_drone_structural` | Real L3 weed severity |
|---|---:|---:|---|---:|
| QA 1 / reliability 1 | .70 | .60 | true | .48 |
| QA 1 / reliability 0 | .70 | .60 | true | .48 |
| QA 1 / reliability NaN | .70 | .60 | true | .48 |
| QA 0 / reliability 1 | absent | absent | false | 0 |
| QA NaN / reliability 1 | absent | absent | false | 0 |
| QA 1 / reliability 1 / legitimate zero values | 0 | 0 | false | 0 |

Real L2 attributes the influential weed as `BIOTIC` / `weed_pressure_detected` (`stress_attributor.py:860–873,980–996`). The actual L3 adapter copies this severity and sets availability (`outputs/layer3_adapter.py:301–320`). The native decision feature builder copies availability and severity (`features/builder.py:420–429`). In the zero/NaN-reliability cases the resulting `DecisionFeatures` therefore has `has_drone_structural=True` and `weed_pressure_severity=.48`. These native direct fixtures have actual data health .38, confidence ceiling .5, status degraded, `diagnostic_usable=True` and `usable_for_layer3=False`; the demonstrated consequence is admission, interpretation and decision-feature content, not a fully usable final decision.

The actual L2 engine does not create named canopy/weed `VegetationFeature` records, so this actual route has `canopy_cover_ratio=0` and `weed_pressure_index=0` in the decision features. The finding establishes actionable canopy at L1 and positive actual weed severity/availability downstream; it does not claim an actual .7 canopy decision feature.

The mixed-sibling control establishes influence beyond a presence flag. A separately qualified native weed value .3 produces fused weed .3 and actual L3 weed severity .24. Adding a native weed .6 sibling with reliability zero or NaN changes the fused value to .45 and actual L3 severity to .36. Both siblings are admitted at reliability 1 and confidence .5. The exact parent behaves identically. These are two manifestations of the same missing quality gate, not separate findings.

The bounded correction should qualify the native structural output's inherited quality before granting reliability/update capability, retain zero/invalid-quality outputs as non-influential diagnostics or reject them with receipts, and preserve positive-quality zero values and qualified siblings. This review makes no production edits and claims no whole-season decision, prescription, actuator or durable state consequence.

## Four routes and the positive-control limits

The harness keeps these routes explicit because an absent positive path cannot prove a quality gate:

| Route | Actual producer/consumer work | Interpretation |
|---|---|---|
| Native shared perception output → shared packet adapter → canonical package → real L1/L2/L3 | Uses native `PerceptionEngineOutput`, `PerceptionVariable` and unmodified packets | Both named structural keys are ignored by the packet bridge, even for positive quality. No successful structural end-to-end claim. |
| Canonical generic packet boundary → real L1/L2/L3 | Creates a separate native packet fixture with documented `variable` / `value` payload and the producer packet's actual QA/reliability | Nonvacuous packet-boundary quality controls; this is explicitly not a production transformation of the shared adapter's payload. |
| Native `DroneRGBOutput` → actual `DronePacketizer` → canonical package → real L1/L2/L3 | Executes the specialized packetizer without payload alteration | Its nested `summary_metrics` is also ignored by the canonical bridge even in the positive control. Architectural limitation on both versions. |
| Native `DroneRGBOutput` → registered `DroneStructuralAdapter` → real L1/L2/L3 | Actual direct structural registration and consumers | Positive control reaches L3 weed severity .48; zero/NaN inherited reliability reproduces A263-02. |

The bridge's recognized-key loop and generic fallback are at `adapters/observation_packet.py:220–227,270–299`. The shared producer writes per-variable top-level names (`packet_adapter.py:193–199`); the specialized producer writes `summary_metrics` (`drone_rgb/packetizer.py:25–41`). Their omitted positive paths are established on both exact versions and recorded as capability limitations; they are not counted as newly introduced defects.

For canopy adapter coverage only, each real L1 actionable context is additionally projected into native `Layer2Output` / `VegetationFeature` carriers and passed through the actual L3 adapter and feature builder. This projection is stored under `typed_boundary_projection` and is never substituted for the real L2 output. It verifies zero-value preservation and lack of revived invalid fields at that typed boundary, without proving real L2 canopy transport. `zone_intelligence.py:25–85` explains the real transport limit: the engine emits vigor/canopy-proxy features instead of the named structural features.

## Fresh quality controls and exact-parent contrast

Each version executes 16 shared-output definitions in both the unmodified native-payload route and the separate generic-packet-boundary route, plus 15 specialized route variants. That is 47 full real L1/L2 executions per version. Read-only profiling records 47 `fuse`, 47 `analyze`, 94 `build_layer3_context`, 94 `build_decision_features`, 188 structural-extractor calls, 18 shared packet-adapter calls, 10 direct structural adapter extractions and six specialized packetizer calls. The extra L3 calls are the explicitly separate typed-boundary controls.

Candidate generic-packet-boundary controls pass 32/32; exact parent passes 8/32. Parent's 24 assertion failures are repeated quality-admission manifestations across the layers and mixed controls. With zero output weight, for example, parent admits canopy .7 / weed .6 with the zero-weight-average flag and floor confidence .1, emits actual L3 structural availability true and weed severity .1; candidate has no actionable structural fields, availability false and severity zero. Both positive controls emit actual weed severity .48.

All candidate zero/NaN output reliability, zero/NaN QA, and zero/NaN variable-confidence controls reject influence at this canonical packet boundary. Positive-quality zero canopy and weed values survive L1 admission and the separate typed adapter projection. Mixed invalid-canopy/valid-weed and valid-canopy/invalid-weed controls preserve only the qualified field. A separately qualified positive or zero-valued sibling survives an invalid package. All these inputs and results are retained in `structural-results.json`; the exact parent results are freshly generated in `parent-compatibility-structural-results.json`.

The specialized native lane passes five of nine checks on both versions. The four failures are zero/NaN reliability without a sibling and zero/NaN reliability with a qualified sibling, all covered by A263-02. Zero/NaN mission QA controls, the positive native control, legitimate zero values, and the specialized packet positive-path omission characterization pass. There are no execution errors.

## Retained water and history controls

`probes.py` adapts prior independent authored probe code and reruns actual production calls against candidate a263b30 and exact parent 5344930. It executes the native `SoilObservationVector`, actual `WaterStateAssimilator`, and full `WaterIntelligenceEngine`. Read-only tracing captures each successful native `add_observation` return and checks agreement with diagnostics and full pipeline admission. Every supplied direct prior remains unchanged; zero admitted rows have zero direct and full analysis increment.

Both versions freshly pass 45 variants / 52 checks. The controls cover finite and legitimate-zero values, NaN/Infinity/bool/malformed rows, positive and invalid uncertainty, OBSERVED/SIMULATED/FORECAST/EXCLUDED roles, typed global/component restrictions, satellite and thermal branches, zero/NaN global/component quality, and actual strict-JSON history round trips. The two unchanged production history helper AST definitions are executed exactly; decision-module initialization and durable history persistence are not executed.

Generic EXCLUDED before or after TDR identity, standalone EXCLUDED and source-scoped excluded TDR each produce zero rows, zero direct/full analysis increment and MODELLED authority on both versions. Satellite-scoped exclusion still preserves three qualified TDR rows and OBSERVED authority. The positive moisture control admits three rows and +82.05 mm direct / +89.70 mm full analysis with OBSERVED authority. Reading reliability zero and NaN weight plus zero reading reliability each admit zero rows and zero analysis on both. This preserves the already corrected R39-01 behavior and does not attribute the older 39b94d8 failure to parent 5344930.

## Normative basis, evidence and reproduction

The F01 master plan is `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:151–177`, particularly admission before authority, role preservation through adapters, finite numeric qualification and legitimate-zero preservation. The R3 basis is `current-plan-review/R3_current_scientific_sections.txt`: AB-DAT-005 at 675–677, AB-DAT-006 at 679–681, AB-ARC-005 at 738–740 and AB-ARC-006 at 742–744. These support quality/capability restriction preservation; they do not require rejecting legitimate zero values.

`line-evidence.json` records exact candidate/parent source ranges, Git blobs, full-file and excerpt SHA-256, normative excerpts and harness ranges. The structural executed-source manifests verify 137 imported production Python files against each exact Git tree before execution; the retained water manifests verify 64. Missing rollout/uncertainty dependencies encountered during initial setup were staged by the review owner from exact tree blobs on both versions; no substitutes were installed. `comparison.json` retains compact fresh comparisons; `manifest.json` hashes the lane artifacts. Source and Git state were not edited by this lane. Repository tests, audits and implementation-authored acceptance artifacts were not used as correctness evidence.

From the workspace root:

```bash
python review-a263b30-f01/decision/probes.py
python review-a263b30-f01/decision/probes.py --parent-compatibility
python review-a263b30-f01/decision/structural_probes.py
python review-a263b30-f01/decision/structural_probes.py --parent-compatibility
python review-a263b30-f01/decision/build_evidence.py
```

The scripts return successful execution even when a named expected-behavior check fails; their strict JSON summaries enumerate all failures. Native NaN/Infinity inputs are exercised numerically and stringified only while saving JSON. No provider, inference image, external service, network, hardware, durable canonical L3 persistence, whole-season decision or actuator path is claimed.


---

# Specialist appendix: Canonical weather to crop features

# F01 weather/crop qualification: retained R41502 closure at a263b30

**Verdict: retained closure for the named daily-dictionary weather provenance seam at `a263b3033d6e637bef73ddf789d77659cd44e8f7`, parent `5344930dfc7fbab7f7277bf61f99fc252dd88bc6`.** A fresh offline Python process on 2026-10-21 executed 43 cases and 241 strict boolean checks; all 241 passed. No blocking finding remains in this bounded lane. The earlier crop numeric/support and Sentinel-2 source-role protections also pass on this candidate.

The named unavailable/excluded declarations retain `unavailable` through `wrap_environment` packet and canonical evidence transport, supply no thermal coordinate to canonical crop observations or ledger-derived model tokens, and produce missing engineered GDD features. The controls cover unavailable status alone, observation role plus unavailable status, and observation role plus excluded `source_role`. The observed 20 °C control still supplies GDD10=10 per supplied weather day. Six-scene inputs preserve six eligible optical observations throughout.

## Normative basis and bounded scope

The master F01 section is `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`, lines 151–177. It requires valid zero and missingness to survive, components to be qualified before authority, source roles to survive typed/dictionary adapters without caller promotion, and qualification to extend to weather and crop consumers. The corresponding R3 basis is `current-plan-review/R3_current_scientific_sections.txt`: lines 675–681, AB-DAT-005 (zero/missingness) and AB-DAT-006 (field provenance), and lines 738–744, AB-ARC-005 (factored authority) and AB-ARC-006 (bounded degradation without fallback promotion). Both normative files and their relevant line ranges are SHA-256 recorded in the source-import manifest.

The executed production path is `wrap_environment` → returned `evidence_records` → `build_canonical_crop_observations` → `build_crop_evidence_ledger` → `observation_tokens_from_ledger` → `build_ledger_crop_feature_input`. Inputs are authored in-memory daily weather dictionaries and complete local 4×4 Sentinel-2 arrays. The six-scene control has six physical acquisitions on 2026-10-01, 04, 07, 10, 13 and 19, each with its own product identity. These dates precede the 2026-10-21 review date; no future-date/cutoff experiment is involved.

The full orchestrator, crop classifier, classifier dispatch, classifier accuracy, training, prescription/publication execution, providers, hardware, services, and persistence were not exercised. This lane establishes input qualification and observed receipt gates, not full F01 acceptance. Repository tests, audits, generated repository artifacts, and previous result files are not proof. Previous authored probe code was reused only as harness material; the reported outcomes below were regenerated against the exact candidate export. Only files in `review-a263b30-f01/ownership/` were written by this lane, with no source or Git mutation.

## Fresh execution and result matrix

The fresh process started at `2026-10-21T11:16:12.187764+00:00` and completed probe execution at `2026-10-21T11:16:14.960582+00:00`, under Python 3.12.14. It exited 0. `results.json` includes the execution timestamps and Python version, all per-case outputs, and every named strict boolean outcome.

| Group | Cases | Passing checks | Result |
|---|---:|---:|---|
| Crop dtype and support | 10 | 33/33 | Finite bands, bool DATAMASK, categorical integer SCL, zero NDVI and partial support remain usable. Boolean, numeric-string, object and complex reflectance, plus absence of finite support, are rejected. One infinite pixel is excluded while 15 finite pixels remain. |
| Sentinel-2 scene roles | 7 | 35/35 | Observed physical input supplies one actual model token. Excluded, synthetic, prior, forecast, fallback and conflicting role aliases supply no token or state-update authority. |
| Weather numeric controls | 11 | 25/25 | Valid zero and 20 °C survive; boolean, numeric string, NaN, infinity and absent temperature produce no GDD. Missing weather does not reject valid optical evidence. Finite min/max and explicit zero GDD controls preserve their intended semantics. |
| Daily weather provenance seam | 7 | 44/44 | Packet and canonical statuses agree for the named declarations. Unavailable/excluded weather cannot enter actual token thermal coordinates. All canonical weather remains process-forcing-only with no state-update authority. |
| Six-scene engineered input | 8 | 104/104 | The four unavailable/excluded declarations match the absent-weather thermal tensor while retaining all six optical tokens. Actual tensor values, hashes, missingness and quality masks are checked. |
| **Total** | **43** | **241/241** | **No failures.** |

Numeric qualification is explicit: `finite_real` rejects booleans, strings and non-finite values rather than coercing them. Reflectance accepts integer/float dtypes; boolean DATAMASK and integer categorical SCL are legitimate support controls. The valid zero temperature yields all four thermal coordinates at zero; explicit zero `gdd` yields only the historical base-10 axis at zero. The finite 20 °C control yields GDD0=20, GDD5=15, GDD10=10 and GDD12=8 for one supplied day.

| Six-scene weather declaration | Canonical status | Actual token GDD10 values | Engineered thermal features |
|---|---|---|---|
| `role=OBSERVATION`, `data_status=observed` | observed × 6 | 10, 20, 30, 40, 50, 60 | All five present |
| `role=EXCLUDED`, unavailable status | unavailable × 6 | All absent | All five missing |
| Unavailable status alone | unavailable × 6 | All absent | All five missing |
| Observation role + unavailable status | unavailable × 6 | All absent | All five missing |
| Observation role + `source_role=EXCLUDED` | unavailable × 6 | All absent | All five missing |
| Synthetic role + simulated status | simulated × 6 | 10, 20, 30, 40, 50, 60 | Present as process forcing |
| Forecast role + estimated status | estimated × 6 | 10, 20, 30, 40, 50, 60 | Present as process forcing |
| No weather | Empty | All absent | All five missing |

Forecast and synthetic thermal forcing are permitted in this bounded review. Their canonical statuses remain estimated/simulated, with `authority=process_forcing_only` and `state_update_allowed=false`. Their numeric tensors equal the observed 20 °C control; that equality is not a failure criterion. This transport/admission result does not establish complete per-field lineage in every downstream artifact. No additional broad alias or unit search was performed.

## Actual engineered input and execution gates

| Engineered feature | Observed weather | Each unavailable/excluded declaration and no-weather control |
|---|---:|---|
| `sos_gdd` | 20.0 | missing |
| `pos_gdd` | 40.0 | missing |
| `eos_gdd` | 50.0 | missing |
| `growth_rate_per_gdd` | 0.0147857143 | missing |
| `senescence_rate_per_gdd` | -0.0135714286 | missing |

These are exactly the five changed tensor features. Every other engineered feature remains equal to the observed control. All six-scene cases retain six optical tokens, six eligible ledger items, and six true quality-mask entries. The results contain the full feature order, input values, missingness mask, tensor hash, receipt hash, ledger outputs, token coordinates, canonical weather rows and gate reasons.

The observed thermal tensor hash is `13e29898129245b63cad3f4dd9a547c57ac7adc9f716cc6e37cef8bef85c5f30`; all unavailable/excluded and no-weather tensors hash to `7973551439d905552bee8b6a3545c55a41c8d6dab4ec692f98d49a4204b4f42f`. Their respective receipt hashes are `dfabade60453db5ef44debc5fd8fe4e25e34b5ca2b5fd936262a8818fcc3daa6` and `0f5e2fb2d09ba55d80a6e60e4d9c53fe15607f5104816b2cb8029164686c9931`.

Feature completeness is 22/66 (0.3333333333) for the observed thermal control and 17/66 (0.2575757576) without the five thermal features. Every six-scene receipt has `model_execution_eligible=false` and `publication_eligible=false`, with `crop_cycle_phase_coverage_insufficient`, `feature_tensor_incomplete`, `model_domain_not_verified`, and `probability_calibration_not_validated` blockers. Every nonobserved single-scene Sentinel-2 role case is blocked earlier because crop-cycle segmentation requires admitted physical evidence. These are actual input-receipt outcomes; no classifier or publication pipeline ran.

## Exact source behavior and function locations

All production paths below are relative to `review-a263b30-f01/source/services/agribrain/`. Every listed file is hash verified in `source-import-manifest.json`.

- `scientific_contracts/numeric.py:10–22` preserves finite real zero and rejects boolean, numeric-string and non-finite inputs.
- `layer0/wrappers.py:28–51` reads native/dictionary consensus and flat daily dictionary values while preserving zero. Lines 106–129 give unavailable/excluded declarations precedence across the named aliases. Lines 137–143 emit canonical status, process-forcing-only authority, no state-update authority and temperature. Packet status inference collects role aliases and applies monotone demotion at lines 174–229.
- `layer2_veg_int/crop_observations.py:874–929` excludes unavailable/excluded weather before finite-real GDD arithmetic. Lines 1120–1128 compute the coordinates attached to the actual crop observation; lines 1244–1251 retain them in environmental context. Lines 1149–1197 and 1253 determine scene role/status and direct state authority.
- `scientific_contracts/crop_model_input.py:577–686` selects admitted physical ledger representatives and reads environmental thermal coordinates. `layer2_veg_int/features/ledger_crop_features.py:42–79,129–217` converts those tokens into engineered feature inputs. `crop_model_input.py:689–780` writes tensor values, missingness and execution/publication gates.
- Static only: `orchestrator_v2/runner.py:915–930` prefers canonical `evidence_records`, including an empty collection, and lines 98–123 forward weather to the canonical crop builder. `layer2_veg_int/crop_posterior.py:720–755` invokes the ledger feature adapter. The four static call-path files are hash verified; the full orchestrator and posterior functions were not invoked.

| Candidate source under `services/agribrain/` | Invoked function | Exact definition lines |
|---|---|---|
| `scientific_contracts/numeric.py` | `finite_real` | 10–22 |
| `layer0/wrappers.py` | `_selected_consensus_value` | 28–42 |
| `layer0/wrappers.py` | `_weather_record_value` | 45–51 |
| `layer0/wrappers.py` | `_canonical_weather_records` | 54–153 |
| `layer0/wrappers.py` | `_infer_data_status` | 174–229 |
| `layer0/wrappers.py` | `wrap_environment` | 560–612 |
| `layer2_veg_int/crop_observations.py` | `_gdd_coordinates_until` | 874–929 |
| `layer2_veg_int/crop_observations.py` | `build_sentinel2_crop_observation` | 932–1264 |
| `layer2_veg_int/crop_observations.py` | `build_canonical_crop_observations` | 1825–1869 |
| `layer2_veg_int/crop_observations.py` | `build_crop_evidence_ledger` | 1872–1881 |
| `scientific_contracts/crop_model_input.py` | `observation_tokens_from_ledger` | 577–686 |
| `scientific_contracts/crop_model_input.py` | `build_crop_model_input_receipt` | 689–780 |
| `layer2_veg_int/features/ledger_crop_features.py` | `_token_row` | 42–79 |
| `layer2_veg_int/features/ledger_crop_features.py` | `build_ledger_crop_feature_input` | 129–217 |

These ranges locate invoked function definitions, not line or branch coverage measurements.

## Reproduction and integrity

From the directory containing `review-a263b30-f01`, run:

```bash
python review-a263b30-f01/ownership/probes.py
```

The script writes fresh `results.json` and `source-import-manifest.json`, verifies every check has a strict Python boolean result, emits JSON with `allow_nan=false`, and exits nonzero if any check fails. Non-finite authored inputs are described explicitly in JSON rather than emitting invalid JSON values. Bytecode writes are disabled.

The script verifies candidate and one-parent metadata, the exact 876-file export path set, every exported file against its exact candidate Git blob and staged SHA-256, every imported production source file, and the four static call-path files. The fresh process imported 66 candidate module identities covering 43 distinct production files; module aliases remain recorded. The manifest includes all imported paths, local paths, Git blobs, SHA-256 hashes, byte/line counts, exact invoked definition ranges, normative-file hashes, and the probe SHA-256 (`03bdbcbc4cf9fef398673533afcc02f384fe97f2909ce920c5564f27cb66cf91`).

Deliverables are `probes.py`, `results.json`, `source-import-manifest.json`, `report.md`, and `execution-receipt.json`. The receipt records the fresh command/exit status and hashes the final lane artifacts. The prior `5344930` ownership harness was reused as implementation material only; its result files are not evidence for this candidate.


---

# Specialist appendix: Actual label consumption, training decisions and legacy read parity

# Retained F01 training admission review — a263b30

Candidate: `a263b3033d6e637bef73ddf789d77659cd44e8f7`. Its actual parent is `5344930dfc7fbab7f7277bf61f99fc252dd88bc6`, verified from the candidate commit metadata. Historical `39b94d8de2911cdbaa9e86d24a46f40464cba101` is the intentionally defective comparison, and older `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe` supplies genuine legacy writer approvals. Neither historical commit is presented as this candidate's actual parent.

**The retained R39-02/R39-03 and R415-01/R415-06 training controls pass in the exercised paths. No new blocker was reproduced in this bounded training lane.** All 22 candidate closure/preservation checks, five expected-result assertions, three harness checks and four additional bounded L1 training-consumer checks pass. This is a retained-path result, not full F01 acceptance or evidence of field/model performance.

## Normative basis

The normative F01 master is `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:151–177`: training admission and ambiguous-legacy migration at 171; exclusion of NaN, infinity, Boolean and malformed numeric influence at 175; valid zero at 176; authority/counts following actual admitted components at 177. R3 maps to `current-plan-review/R3_current_scientific_sections.txt:675–681` (AB-DAT-005/006, zero/missingness and provenance) and `738–744` (AB-ARC-005/006, separate authorities and bounded fallback). `normative-manifest.json` records exact source bytes and these line-numbered excerpts.

## Fresh reproduction and integrity

Run from the workspace containing the candidate and two historical source roots:

```bash
python review-a263b30-f01/trajectory/probes.py --comparison-parent-root review-39b94d8-f01 --legacy-parent-root review-4157ac1-f01
```

This command completed with exit **0** under Python 3.12.14. Candidate and both subprocess stderr files are empty. `results.json.execution` records the actual interpreter, argv and exact child argv. The script first freshly executes the exact older415 writer, then freshly executes historical39 (including reading the same older415 ledgers), then executes this candidate. Each run recreates its private ledgers. No pre-existing behavioral results are used as inputs. The reused prior probe is authored harness material only.

Each interpreter verifies all **876 staged production files** against its exact commit-tree Git blobs, exact staged path inventory, and staged SHA-256/byte manifest after execution. Candidate and historical39 import 55 production files; older415 imports 51. Their individual `source-manifest.json` files enumerate staged bytes, imports, static evidence and metadata hashes. This establishes staged-byte integrity, not branch coverage. A separate fresh bounded byte comparison in `retained-parent-source-comparison.json` confirms that nine retained training modules match actual parent534; actual parent534 behavioral outputs are not read or treated as proof.

| Fresh run | Closure checks | Intended result assertions | Harness checks | Bounded L1 checks |
| --- | --- | --- | --- | --- |
| Candidate a263b30 | 22/22 | 5/5 | 3/3 | 4/4 |
| Historical39 defective comparison | 18/20; exactly two named residual failures | 5/5 | 3/3 | 4/4 |
| Older415 actual legacy writer | 11/20; retained historical defects reproduced | 3/3 | 3/3 | Not asserted; missing-helper defect reproduced |

The candidate has eight probe groups: 11 exporter/consumer cases; 59 current-writer cases; 28 current-writer gate/comparator cases; nine event-only read-defense cases plus two actual generated approved seeds; one registry/static declared-call-site group; three genuine older415-ledger reads; four genuine historical39-resolution-ledger reads; and eight shared-classifier cases. These are independent authored probes, not repository tests.

## R39-02: explicit selected resolution cannot fall through

Candidate admission is `services/agribrain/asmae_learn/candidate_builder.py:78–94`; replay is `asmae_learn/dataset_builder.py:115–124` (all abbreviated source paths here are beneath `services/agribrain/`). Both qualify a present non-None selected resolution before considering fallback.

| Selected diagnostic; run resolution 10m | Historical39 actual writer/replay | Candidate actual writer/replay | Candidate replay of unchanged historical39 approval |
| --- | --- | --- | --- |
| `False` | Approved, one sample | Pending, `invalid_resolution`, zero samples | Zero samples |
| `0.0` | Approved, one sample | Pending, `invalid_resolution`, zero samples | Zero samples |
| Key absent | Approved, one sample | Approved, one sample | One sample |
| `None` | Approved, one sample | Approved, one sample | One sample |

`P3_actual_candidate_gate_scalars` uses actual `record_asmae_run` → validation schema/writer → disagreement → candidate → production-emitted `candidate_update` → replay → `build_validated_training_view`. All four rows in each False/zero run are normal production output; the candidate update is genuinely ineligible. `P7_actual_parent39_selected_resolution_current_reader` independently replays fresh historical39-approved ledgers without changing any row or byte. Matching before/after SHA-256 values are recorded for every read.

## R39-03: shared fractional-biotic qualification and genuine migration contrast

The classifier is `asmae_learn/schemas.py:66–88`, writer qualification `113–126`; disagreement imports/calls it at `disagreement.py:8–11,214–224`; dataset imports/qualifies at `dataset_builder.py:6–9,184–188`. Candidate construction materializes `ValidationEvent` before disagreement (`candidate_builder.py:38–48`). `P8_shared_classifier_identity_and_results` confirms one shared function object across schema, disagreement and dataset.

Actual candidate writes of fractional-biotic NaN, Boolean, numeric-string and malformed-string values raise `ValueError` before validation-event append; only the run row exists and no sample is emitted. `P4_legacy_read_schema_parity` separately changes only event fields of actual valid approved seeds, retaining the generated approvals. Those fixtures verify read defense and are explicitly not evidence that the current writer accepts the mutated values.

For the stronger migration control, the exact older415 production writer freshly approves these legacy values through the actual writer/candidate/replay path. Both readers subsequently read the **same physical files**, unchanged:

| Same older415-approved fractional-biotic ledger | Older415 writer samples | Historical39 reader samples | Candidate reader samples |
| --- | --- | --- | --- |
| `"0.5"` | 1 | 1 | 0 |
| `"not-a-number"` | 1 | 1 | 0 |
| NaN control | 1 | 0 | 0 |

The final fresh ledger SHA-256 values shared by both readers are:

- Numeric string: `ad82cdcc4ffb5c548d65f784a9cfab52901276a4c1df9e7d7f799aaa952a518c`.
- Malformed string: `e181e6468c3265fc57185618dc49d2cf097d0b01a603dcab4904b404a1f4e3c8`.
- NaN control: `1864f508a6a3f399ee64fd94c359ad89cec1ca4f152a8e915f3534839e50e3da`.

Every before/after hash matches. No approval, event or other row is fabricated or rewritten for these genuine-writer comparisons. Evidence is candidate/historical39 `P6_actual_old_writer_current_reader` plus older415 `P2_actual_validation_writer_training_view`.

Valid fractional `0.5` and `0.0` remain approved. Ordinary `low`, `medium`, `high`, `aphids` categories remain approved; the established qualitative `low/medium/high` exception with fractional units remains usable. This bounded review does not define a new arbitrary target/unit matrix.

## Retained R415-01/R415-06 and bounded L1 consumption

Actual `export_weak_labels` output goes unchanged to actual `ASMAEAdapter.extract_evidence` in `P1`. Valid estimates `0.0` and `0.5` preserve exporter and L1 training weight **0.30**. NaN, infinity, Boolean and numeric-string estimates produce weight **0** at both boundaries. Zero scene count, radiometric failure and uncertified 1m produce L1 training-weight value zero; shadow/no-scene controls produce no training-weight evidence. The older415 valid-exporter → L1 missing-helper `NameError` is freshly reproduced as an intended historical contrast. Source: exporter `layer05_asmae/training/exporter.py:153–194`; L1 adapter `layer1_fusion/adapters/asmae_adapter.py:20–23,414–449`. The declared engine exporter call is statically traced, not executed.

Because this candidate changes downstream L1 behavior, the nine emitted actual training-weight items also enter actual `validate_evidence`, `check_confidence_floor`, and `fuse_features` directly. Validation produces no violation, the floor routine does not change the items, their numeric weight values remain exactly 0 or 0.30, and all remain `diagnostic_only=True`, `state_update_allowed=False`. Fusion produces no water/vegetation/phenology/stress/soil/operational feature from these training items, and all four source-completeness values are zero. This is recorded inside each `P1` case and asserted by `bounded_training_consumer_checks`.

The zero **training-weight value** carries diagnostic confidence 0.8 and reliability 1.0; those are confidence in the diagnostic, not positive training weight. This path does not exercise zero-confidence perception assimilation or the changed all-zero-updatable-evidence fusion branch. Source: validation `layer1_fusion/evidence_validation.py:59–68,100–104`; floor `context_invariants.py:190–235`; actual fusion entry `fusion_rules.py:181–194`, diagnostic-only completeness exclusion `380–387`. No broader L1 engine or optimizer is invoked.

Four original continuous targets (`vigor`, `canopy_water`, `salinity_stress`, `yield_observed`) preserve finite 0.5 and legitimate zero through actual approved samples. NaN/infinity/Boolean/numeric-string/malformed-string targets fail before event append; malformed/out-of-range confidence remains blocked. Crop-stage/irrigation/harvest categorical controls remain usable. Zero confidence, finite contradiction, synthetic source, uncertified 1m, visual-only, diagnostic-only and weak-label-as-truth controls yield no dataset sample (`P2`).

Malformed/out-of-range uncertainty, retro and resolution scalars remain ineligible; zero uncertainty and retro boundary 0.7 remain eligible (`P3`; `candidate_builder.py:123–158`). A nonfinite model comparator rejects the finite target (`disagreement.py:83–104,195–206`). Legacy confidence Boolean/above-one and malformed original continuous labels remain excluded (`P4`; `dataset_builder.py:180–188`).

## Boundaries and artifacts

Only this new `trajectory/` lane is written. Production source and Git state are untouched. No repository tests, audits, generated repository correctness artifacts, or prior behavioral outputs are proof. No network, services, providers, hardware, full engine, optimizer, model fitting/training, or empirical field validation is executed. `AGRIWISE_ARCHIVE_PILOT_MODE=false` is set before imports. Runtime ledgers stay under this lane. Every approval used as genuine approval evidence is emitted by production code; the separately labeled read-defense mutations retain actual seed approvals.

`results.json` and all manifests are strict JSON. Nonfinite runtime inputs appear as descriptive objects in those reports; production JSONL bytes retain the older writer's literal NaN serialization because unchanged replay is the evidence. `artifact-manifest.json` identifies all lane artifacts except itself; the two historical source roots and candidate source/metadata remain explicit reproduction inputs.


---

# Specialist appendix: Contained RF covariance admission

# F01 RF covariance qualification retained at a263b30

**Disposition: bounded software closure retained at candidate `a263b3033d6e637bef73ddf789d77659cd44e8f7`, parent `5344930dfc7fbab7f7277bf61f99fc252dd88bc6`.** Explicit invalid covariance is not promoted to the model default along the real typed likelihood → MESIA operator → Layer 0 spine → ASMAE adapter → private dispatcher composition. The nine named bad values become proposal variance `None`, status `ABSENT`, unusable for assimilation, no event, and no private queue entry. No new RF finding is counted. This is not full F01 acceptance or a posterior-commit claim.

A fresh authored process executed **80 cases and 18 strict controls, all passing** at `2026-10-21T11:35:54.575500+00:00`. Groups comprise 15 packet numeric cases, 42 typed operator/spine/adapter cases, and 23 role/gate/capability cases. Every target control asserts its result without exemptions. The process checked all **885 staged source files** against candidate Git blobs and SHA-256 before and after execution, including the full **176-file production MESIA Python tree**. Real imports loaded 202 candidate module entries representing 179 unique source files; all hashes match the candidate. There were no source edits, package stubs, repository test/audit executions, or reused prior output assertions. The runnable script adapts prior authored probe code, but imports only the current staged source and freshly produces its own results.

## Normative basis and source locations

| Basis | Exact local location | Use |
|---|---|---|
| F01 | `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:151–177` | Numeric qualification, valid zero, missingness, roles and RF admission requirements |
| AB-DAT-005 / AB-DAT-006 | `current-plan-review/R3_current_scientific_sections.txt:675–681` | Preserve zero/absence and distinguish field provenance |
| AB-ARC-005 / AB-ARC-006 | `current-plan-review/R3_current_scientific_sections.txt:738–744` | Factor authority and prevent promotion by fallback |

These documents are normative inputs, not runtime evidence. Their byte counts, SHA-256 values and line ranges are recorded in `normative-manifest.json`. The candidate source locations below are relative to sibling `source/`; `static-source-manifest.json` records exact Git blobs, SHA-256, function names, definition spans and inspected line ranges.

| Candidate source | Function / exact inspected lines | Relevant behavior |
|---|---|---|
| `services/agribrain/scientific_contracts/numeric.py` | `finite_real`, 10–22 | Finite real guard rejects bool/string/nonfinite inputs and preserves zero |
| `services/agribrain/mesia/contracts/behaviour.py` | `BehaviourLikelihood`, 89–118 | Covariance defaults to `None`; evidence proposal authority |
| `services/agribrain/mesia/assimilation/asmae_operator.py` | `ASMAEObservationOperator.create_innovation`, 75–86 | Only raw `None` selects documented `0.25`; invalid explicit values become variance `None` |
| `services/agribrain/mesia/assimilation/layer0_spine.py` | `Layer0EvidenceSpine.evaluate_admission`, 45–100 | False calibration/epoch gates precede numeric absence; unusable covariance becomes `ABSENT` |
| `services/agribrain/layer05_asmae/adapters/mesia_adapter.py` | `MesiaAsmaeAdapter.to_asmae_observation_event`, 30–85 | Unusable record returns no event; qualified versus contained authority is explicit |
| `services/agribrain/mesia/integration.py` | `MesiaAgriBrainBridge.process_and_admit_observation`, 93–118, 186–242 | False default gates, real composition, role and capability restrictions |
| `services/agribrain/layer05_asmae/observation/dispatcher.py` | `ASMAEObservationDispatcher.dispatch_event`, 165–300 | Actual private queue persistence and authority abstention |
| `services/agribrain/mesia/service.py` | `MesiaProductionService.scan_plot_spectrum` call site, 2629–2635 | Static-only caller retains explicit calibration `False` and epoch `False` |

## Covariance controls

The typed fixture supplies finite innovation `0.0`, positive support `1.0`, native lineage hash, explicit internal calibration/epoch `True`, and adapter qualification `True`. These are controlled internal admission conditions.

| Fresh authored label | Raw covariance | Proposal variance | Spine / adapter | Actual private dispatcher |
|---|---|---|---|---|
| `covariance_nan` | NaN | `None` | `ABSENT`, no event | Not called; absent from queue |
| `covariance_positive_infinite` | +Inf | `None` | `ABSENT`, no event | Not called; absent from queue |
| `covariance_negative_infinite` | −Inf | `None` | `ABSENT`, no event | Not called; absent from queue |
| `covariance_boolean_true` | `True` | `None` | `ABSENT`, no event | Not called; absent from queue |
| `covariance_boolean_false` | `False` | `None` | `ABSENT`, no event | Not called; absent from queue |
| `covariance_numeric_string` | `"0.1"` | `None` | `ABSENT`, no event | Not called; absent from queue |
| `covariance_malformed_string` | `"invalid"` | `None` | `ABSENT`, no event | Not called; absent from queue |
| `covariance_zero` | `0.0` | `None` | `ABSENT`, no event | Not called; absent from queue |
| `covariance_negative` | `-0.1` | `None` | `ABSENT`, no event | Not called; absent from queue |
| `covariance_constructor_omitted` | Constructor keyword actually omitted | `0.25` | `ADMITTED`, state-authorized event | `admitted_for_assimilation`; durable `QUEUED` |
| `covariance_missing` | Explicit `None` | `0.25` | `ADMITTED`, state-authorized event | `admitted_for_assimilation`; durable `QUEUED` |

The API represents both explicit `None` and an omitted constructor covariance as the same dataclass value `None`; the source treats both as absence. This review does not describe explicit `None` as malformed covariance. The actual omission is separately recorded in `constructor_covariance_argument_omitted`, so the valid default control is not inferred merely from passing a helper's `None` argument.

Both absence controls preserve likelihood/native lineage plus queue quality, operator and uncertainty-model references. `covariance_origin` in the results is an **authored interpretation of the input and exact source branch**, not a newly asserted production field or measured physical covariance. The source-documented `0.25` is an internal model assumption under the qualified fixture. Nine `direct_spine_covariance_*` cases retain raw bad variance and independently confirm the spine blocks each before the adapter.

## Positive and containment controls

| Named controls | Fresh observed result |
|---|---|
| `typed_zero_innovation`, `typed_finite_positive_innovation`, `innovation_zero`, `innovation_negative` | Finite variance `0.1`; admitted, state-authorized and durably queued. Zero and finite negative innovations remain valid. |
| `finite_zero_innovation`, `legitimate_zero_snr`, `finite_negative_snr` | Full packet/likelihood/bridge path yields innovation `0.0`, `-22.0`, `-23.0`; admitted and queued under explicit internal qualification. |
| Invalid/missing/bool/string SNR and derived NaN/bool SNR | `ABSENT`, no event or dispatcher call. The derived malformed-string case raises `ValueError` before event/dispatch; this is containment, not a clean absence receipt. |
| Missing, zero, negative, nonfinite, bool and string support; malformed/nonfinite/bool/missing innovation | No state-authorized event. Missing/zero support cannot synthesize an observation. |
| Documented `TRANSPORT`, `CONTEXT`, `TEACHER`, `SENTINEL`, `NEGATIVE_CONTROL`, `GEOMETRY_AUTHORITY`, `EVENT_LEDGER` | `ABSENT`, no event despite usable numeric inputs and matching capability. Enum `CONTEXT` is also blocked. |
| `defaults_omitted`, `unverified_calibration_and_epoch`, `unverified_calibration` | `INVALIDATED`, no event. |
| `unverified_epoch` | `QUARANTINED`, no event. |
| `sensing_without_qualified_capability` | Layer 0 remains usable/`ADMITTED`, but adapter state authority is `False`; dispatcher persists `ABSTAINED` and returns `abstained_uncalibrated`. |
| `visible_service_false_gates_retained` | Static AST inspection confirms the service call at lines 2629–2635 still supplies both gates `False`; the service was not imported or run. |

The earlier bounded `CONTEXT.SENSING` compatibility observation remains noncounted: it normalizes to SENSING under the same internal fixture, but no documented valid producer/schema for this malformed tag was established. No new role finding is inferred from it.

## Consumer evidence and limits

The real dispatcher persisted **14 private records: 13 `QUEUED`, 1 `ABSTAINED`, 0 `COMMITTED`**. Every record has a matching fresh summarized receipt, identifier and hash; every named bad covariance label is absent from the actual queue inventory. Results preserve the relevant operator, uncertainty and quality references without embedding raw private queue records or capture bytes.

The SigMF artifact contains synthetic integrity bytes. The fixture uses a built-in calibration ID, explicit calibration/epoch booleans, and a matching all-gates capability registration. These establish internal software admission conditions and artifact consistency only. They do not demonstrate RF physical calibration, measured uncertainty, field observability, radio acquisition, deployed capability, or a public posterior path.

Only dispatcher enqueue/abstention was exercised. There was no queue processing, EnKF call, canonical assimilation commit, training, external provider execution, deployed service execution, controller/radio/hardware action, or Git mutation. Import hashes establish loaded source identity, not statement coverage or scientific validity of every imported algorithm.

## Reproduction and artifacts

From the workspace root:

```bash
PYTHONDONTWRITEBYTECODE=1 python review-a263b30-f01/protocol/qualification_probes.py > review-a263b30-f01/protocol/run-stdout.json 2> review-a263b30-f01/protocol/run-stderr.txt
PYTHONDONTWRITEBYTECODE=1 python review-a263b30-f01/protocol/build_report.py
```

The script uses sibling `source/`, `git-tree.json`, `source-manifest.json`, and `commit-metadata.json`; it has no dependency on old RF outputs. It writes only inside this protocol directory, refreshes its private queue, verifies source integrity again after execution, and raises for any failed control. Nonfinite inputs serialize as tagged objects with strict JSON, `allow_nan=False`.

- `build_report.py`: self-contained current-results validation, report generation and artifact hashing.
- `qualification_probes.py`: self-contained authored boundary probe relative to the sibling pinned source; fresh real imports.
- `results.json`: all case inputs, proposals, records, events, summarized consumer receipts, 18 strict controls and explicit scope.
- `run-stdout.json`: compact fresh execution summary.
- `source-import-manifest.json`: actual loaded source/external-file hashes.
- `static-source-manifest.json`: inspected exact source identities and line ranges.
- `normative-manifest.json`: normative input identities and line ranges.
- `artifact-manifest.json`: hashes of this lane's deliverables and private fixture evidence.

R415-07 closure is retained for the named explicit-invalid covariance fallback mechanism through the reviewed internal consumer composition. Valid zero/missingness controls, the documented absent-covariance model assumption, role restrictions, false calibration/epoch gates and capability containment remain intact. No broader F01 completion or RF physical calibration conclusion follows.

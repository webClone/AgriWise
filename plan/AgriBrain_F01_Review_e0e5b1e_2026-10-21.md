# Independent F01 closure verification — e0e5b1e

Review date: 21 October 2026. Candidate: `e0e5b1eabee73e8b17ce6849f4a23c05b302501a`. Exact parent: `a263b3033d6e637bef73ddf789d77659cd44e8f7`. Branch: `feat/f01-downstream-integration-evidence`. Observed main: `5344930dfc7fbab7f7277bf61f99fc252dd88bc6`.

**Recommendation: proceed with merging this bounded corrective batch. A263-02 and A263-01 are closed at their named software boundaries.** Fresh exact-parent runs reproduce both former failures; the candidate preserves the qualified numerical outputs and positive controls. No additional blocker was established within this review's bounded scope.

This recommendation closes the two reviewed software findings. It does not sign full F01 acceptance or certify complete absence of influence in every aggregate diagnostic. All 52 FA milestones remain open. No production source, Git state, remote branch, task checkbox or PR discussion was changed by this review.

## Closure decisions

| Finding | Fresh exact parent a263b30 | Fresh candidate e0e5b1e | Disposition |
|---|---|---|---|
| A263-02: native output reliability ignored | Invalid weed sibling changes fused weed 0.30→0.45 and real L3 severity 0.24→0.36 | Fused weed remains 0.30; severity remains 0.24 | Closed, bounded |
| A263-01: diagnostic conflict penalizes qualified source | Valid sensor evidence/fused confidence falls 0.95→0.85 | Evidence/fused confidence stays 0.95; value remains 0.20 | Closed, bounded |
| Qualified disagreement control | Sensor penalty to 0.85 | Sensor penalty to 0.85 | Intended behavior retained |
| Actual Layer2 sensor feature / global confidence ceiling | Parent feature penalty and zero diagnostic ceiling reproduced | Qualified feature and 0.95 global ceiling preserved | Verified at the exercised output boundary |

The six review lanes freshly executed production consumers. The reported 686 repository tests were not rerun or used as independent correctness proof. Repository tests and historical audit assertions were excluded. Authored probes use exact production source, actual software consumers and the selected plan/R3 requirements.

All 885 staged production/configuration files match candidate Git blobs. Three changed production modules compile; compilation is only a syntax check. Actual behavior is established by fresh execution. Source/import hashes establish identity, not branch coverage.

## A263-02 — native structural quality now governs contribution

The native DroneStructuralAdapter now qualifies mission QA and inherited output reliability before constructing evidence. Its source-health envelope and evidence use the effective bound. Invalid or explicit zero support is retained as diagnostic information with zero confidence/reliability and denied update permission. Core numeric fields are separately qualified before conversion. See [layer1_fusion/adapters/drone.py:L39-L104](https://github.com/webClone/AgriWise/blob/e0e5b1eabee73e8b17ce6849f4a23c05b302501a/services/agribrain/layer1_fusion/adapters/drone.py#L39-L104), [layer1_fusion/adapters/drone.py:L130-L197](https://github.com/webClone/AgriWise/blob/e0e5b1eabee73e8b17ce6849f4a23c05b302501a/services/agribrain/layer1_fusion/adapters/drone.py#L130-L197) and [layer1_fusion/adapters/drone.py:L263-L307](https://github.com/webClone/AgriWise/blob/e0e5b1eabee73e8b17ce6849f4a23c05b302501a/services/agribrain/layer1_fusion/adapters/drone.py#L263-L307).

The central route is the actual native DroneRGBOutput → registered structural adapter → real Layer1FusionEngine.fuse() → real L2 attribution → actual L3 context/feature construction. It does not rely on a manually manufactured L2 output.

| Actual native fixture | Candidate result | Exact-parent contrast |
|---|---|---|
| Invalid standalone weight 0 or NaN, weed=0.6 | No actionable structural contribution; weed severity 0; has_drone_structural=false | Positive contribution and severity 0.48 |
| Qualified weed=0.3 alone | Fused 0.30; severity 0.24 | Same positive baseline |
| Add weed=0.6 with weight 0 | Fused 0.30; severity 0.24 | Fused 0.45; severity 0.36 |
| Add weed=0.6 with weight NaN | Fused 0.30; severity 0.24 | Fused 0.45; severity 0.36 |
| Valid finite support, including 0.85 and 1.0 | Effective finite support and positive-control contribution preserved | Confirms preservation rather than blanket rejection |
| Legitimate zero physical values with positive quality | Numeric zero retained at the actual admitted/typed boundary | Missingness is not substituted for zero |

The expanded native quality matrix passes 138/138 checks across 44 typed/dictionary variants. The original specialized-route checks pass 9/9, versus 5/9 on the exact parent. The canonical packet controls pass 32/32 on both snapshots, preserving the earlier shared-path repair.

Scientific comparison excludes intentional changes in diagnostic membership and source lineage. One inherited assertion compared entire context dictionaries; it was refined to compare qualified value/confidence and downstream severity while allowing diagnostic provenance to remain. Full dictionary equality is not a valid zero-influence criterion when the design preserves rejected-source diagnostics.

The sparse native fixture remains degraded, with overall health 0.38, confidence ceiling 0.5, diagnostic usability and usable_for_layer3=false. The measured result is corrected admitted/fused and downstream feature content. It is not a claim of a fully usable final recommendation, prescription dispatch, optimizer outcome or physical crop response.

## A263-01 — scientific penalties require qualified counterpart support

The actual batch confidence call now passes the evidence-ID map. Conflict penalties inspect the concrete counterpart's diagnostic status, update permission, production eligibility and finite positive quality. Explanatory conflicts remain visible in the conflict ledger. See [layer1_fusion/confidence_model.py:L49-L147](https://github.com/webClone/AgriWise/blob/e0e5b1eabee73e8b17ce6849f4a23c05b302501a/services/agribrain/layer1_fusion/confidence_model.py#L49-L147).

Diagnostics confidence distribution now prioritizes usable, non-diagnostic evidence when available. In the exercised fixture, a diagnostic zero no longer collapses the global confidence ceiling. See [layer1_fusion/diagnostics.py:L382-L454](https://github.com/webClone/AgriWise/blob/e0e5b1eabee73e8b17ce6849f4a23c05b302501a/services/agribrain/layer1_fusion/diagnostics.py#L382-L454).

| Real full-fusion input | Candidate sensor confidence / value | Exact parent |
|---|---|---|
| Qualified point sensor alone | 0.95 / 0.20 | 0.95 / 0.20 |
| Add disagreeing zero-quality DRONE | 0.95 / 0.20 | 0.85 / 0.20 |
| Add disagreeing NaN/±Inf output quality or variable confidence | 0.95 / 0.20 in all eight original contrasts | 0.85 / 0.20 |
| Add agreeing zero-quality DRONE | 0.95 / 0.20 | Positive control retained |
| Add qualified disagreeing DRONE | 0.85 / 0.20 | Intended conflict penalty retained |

SCOPE_MISMATCH remains detected and present in the diagnostic/conflict record. The fix protects the qualified feature without hiding the disagreement. Actual Layer2 output retains that sensor feature at its baseline value, confidence, uncertainty, freshness and source weight. The global confidence ceiling remains 0.95.

The full-fusion lane runs 58 actual engine fixtures per snapshot, including two reachable ingestion-order controls. Thirteen working-control assertions pass. Direct confidence-call compatibility is also exercised by the training lane: the optional map argument does not break legacy no-conflict callers. These controls do not claim immutable counterpart snapshots or correctness for arbitrary synthetic/unbound conflict references.

## Remaining integration observations

These observations are disclosed to keep the closure precise. None establishes an additional blocker for the two repaired mechanisms.

- **Aggregate confidence and health are not identical to the absent-input baseline.** The Layer2 vegetation group-confidence map averages diagnostic features too: it changes from 0.95 to 0.475 when a zero diagnostic is present, including an agreeing diagnostic. The retained disagreement also changes health from 0.538 for agreeing to 0.518 for disagreeing diagnostics; status remains ok. The actual qualified sensor feature and global 0.95 ceiling are unchanged. No additional qualified L3 scientific effect was established from these aggregate differences.
- **Structural transport is path-specific.** Generic shared payloads with the literal structural names and the specialized summary_metrics packet route still omit even positive evidence in the exercised generic bridge. Actual registered native structural ingestion supplies the nonvacuous positive and negative controls. Typed L2 canopy projections are adapter-only checks and are not presented as real L2 transport.
- **Inherited availability exceptions remain.** A row_count=Infinity fixture still raises OverflowError in full structural ingestion on both exact revisions. This is an inherited availability limit, not a false numerical contribution or introduced regression. The pre-existing default-QA malformed/null exceptions are likewise recorded separately.

Track these separately in the remaining integration work. Do not describe this batch as universal equality of every downstream summary, or use an unsupported positive route as proof of zero influence.

## Retained controls and evidence scale

| Lane | Fresh verification |
|---|---|
| Native common producers | 18 corrected controls and 20 retained controls on both revisions; deliberate zero-update requests quarantine |
| Component ledger / full fusion | 112 component fixtures and 58 actual fusion fixtures per snapshot; named A263-01 contrast closes |
| Native structural / water | 138 native quality checks, 9 specialized checks, 32 canonical packet checks; retained water 45 variants/52 checks |
| Weather / crop | 43 cases, 241 checks; actual engineered crop inputs |
| Training | 22 closure controls, 4 bounded L1 checks, 3 confidence API compatibility checks; genuine historical approved-ledger replay |
| RF | 80 cases, 18 controls; 13 QUEUED and 1 ABSTAINED private receipts, no posterior commits |

Rows, cases, assertions, imports and queue receipts measure different things; they are not summed into a synthetic repository-test total. The final separate-layout replay and root observation checks reproduce the closures and exact-parent failures. No old behavioral output is used as correctness proof.

The earlier R415/R39 named boundaries remain intact in the exercised paths. Prior R51901 unsent-contender cleanup/quota and R51902 invalid-root-support software closures are retained; their relevant target files are unchanged. No new whole-irrigation runtime guarantee is inferred from that source continuity.

## Plan and R3 assessment

The normative F01 card is the master repair plan, lines151–177. It maps to AB-DAT-005, AB-DAT-006, AB-ARC-005 and AB-ARC-006. The master, sequencing addendum and task list match candidate Git blobs. The supplied R3 PDF/full-text/scientific extract identities are verified; PDF SHA-256 is `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`.

The repaired behavior supports F01's numerical requirements: malformed/zero quality no longer creates the reviewed native state contribution; valid physical zero survives; authority and contribution follow qualified support; diagnostic disagreement remains traceable without imposing the original penalty on the valid source.

All 52 FA rows, including F01, remain unchecked, with zero acceptance rows changed. This records pending formal package acceptance; it does not imply the implemented work is absent.

**Proceed with the bounded merge and continue the plan.** F02 is the next Stage1 package: observation time and availability at issuance, targeting resilient_posterior.py, temporal_evidence.py and historical_extractor.py. Its card declares F01 as a prerequisite. The sequencing addendum permits independent implementation to overlap once the relevant boundary is available; this review supports using the repaired admission boundary for that work. Full acceptance must still satisfy each package's declared criteria. No universal all52-package or hardware gate is imposed here.

The detailed appendices provide reproduction commands and exact source evidence. The bundle reconstructs current, exact-parent and historical training source from Git objects, then runs private offline fixtures. No production/Git edits, repository-test/audit correctness evidence, live providers/services/controllers/radio/drone/hardware, optimizer fitting, or prescription execution occurred.


---

# Specialist appendix: Actual full fusion, conflict influence and component controls

# Bounded independent F01 fusion and ledger re-verification

Candidate: `e0e5b1eabee73e8b17ce6849f4a23c05b302501a`  
Exact first parent: `a263b3033d6e637bef73ddf789d77659cd44e8f7`

**A263-01 is closed in its original bounded item/fused-confidence route.** A valid point sensor remains at confidence **0.95** after adding a disagreeing native DRONE diagnostic with confidence/reliability **0/0**. Eight zero/nonfinite-quality disagreement variants retain the same qualified feature, uncertainty, freshness, numeric source weights and actual Layer 2 scientific feature. The scope conflict and both source evidence IDs remain visible. The exact parent freshly reproduces **0.95 → 0.85**; a qualified disagreeing DRONE still imposes the intended **0.85** penalty in candidate and parent.

The repaired candidate also keeps the diagnostic-independent global confidence ceiling at **0.95**, where the exact parent drops to **0.0**. Broader health and Layer 2 group-confidence summaries still differ when diagnostics are added. They are disclosed below as integration observations, not a new blocker or a demonstrated Layer 3 decision/posterior effect. This review does not close whole F01 or the project.

## Fresh actual-engine result

The fixture uses an actual `ObservationPacket(source=SENSOR_IOT)` with `vegetation_fraction=0.20`, point scope, QA/reliability 1.0, in the canonical sensor source package. Native `PerceptionEngineOutput(engine_family=DRONE)` fixtures go through the native shared packetizer, canonical `Layer0SourcePackage`, registered perception adapter and the actual `Layer1FusionEngine.fuse()` orchestration. No production function or evidence object is replaced. Confidence scoring, fusion, invariants and the real Layer 2/10 output adapters run.

| Actual fixture | Candidate sensor evidence / fused confidence | Fresh exact-parent evidence / fused confidence | Candidate global confidence ceiling | Candidate retained scope conflict |
|---|---:|---:|---:|---|
| Qualified sensor alone | 0.95 / 0.95 | 0.95 / 0.95 | 0.95 | Absent |
| Add disagreeing DRONE, output reliability 0 | **0.95 / 0.95** | **0.85 / 0.85** | **0.95** | Present, both evidence IDs |
| Add disagreeing DRONE, reliability NaN, +Inf or −Inf | **0.95 / 0.95** | **0.85 / 0.85** | **0.95** | Present, both evidence IDs |
| Add disagreeing DRONE, variable confidence 0, NaN, +Inf or −Inf | **0.95 / 0.95** | **0.85 / 0.85** | **0.95** | Present, both evidence IDs |
| Add agreeing DRONE, reliability 0 | 0.95 / 0.95 | 0.95 / 0.95 | 0.95 | Absent |
| Add qualified disagreeing DRONE | **0.85 / 0.85** | **0.85 / 0.85** | 0.72 | Present |

All eight bad disagreement variants remain diagnostic, state-ineligible and exactly confidence/reliability 0/0. The valid sensor's non-diagnostic feature stays `value=0.20`, `uncertainty=0.05`, `freshness=0.95`, `source_weights={"sensor": 1.0}`, `spatial_scope="point"`, `scope_id="INERT-SENSOR"`, `temporal_scope="instant"`. The actual Layer 2 `vegetation_context["vegetation_fraction"]` field, including its source evidence ID, is identical to the sensor-only baseline. The candidate `confidence_distribution` excludes the diagnostic DRONE when usable evidence exists, and both state-summary and Layer 2 data-health confidence ceilings remain 0.95. No context invariant violations occur in these named baseline/zero-quality controls.

The fresh proof is in `full-fusion-candidate-results.json` and `full-fusion-parent-results.json`, under `scope_residual.disagreement_cases`, `integration.case_summaries`, and the full named `cases`. The comparison's explicit closure field is `A263_01_original_individual_feature_boundary_closed=true`. The individual-feature projection compares value, final confidence, uncertainty, freshness, source weights, unit, spatial scope, scope ID and temporal scope; diagnostic/data-quality feature differences do not masquerade as state changes.

The production chain is bounded and exact:

- `services/agribrain/layer1_fusion/engine.py:236–249` retains all ledger evidence for conflict detection, then applies confidence scoring before fusion.
- `services/agribrain/layer1_fusion/conflict_resolver.py:356–397` retains the minor scope conflict with point and broad evidence IDs, including a diagnostic counterpart.
- `services/agribrain/layer1_fusion/confidence_model.py:52–73` qualifies a counterpart's authority, finite positive confidence and finite positive reliability. At `:103–119`, an unqualified counterpart cannot impose the conflict ceiling. Qualified disagreement retains the minor ceiling 0.85.
- `services/agribrain/layer1_fusion/diagnostics.py:383–391,441–450` derives confidence distribution from non-diagnostic, state-updating evidence when available, keeping the 0.95 global ceiling in the sensor-plus-diagnostic fixture.
- `services/agribrain/layer1_fusion/outputs/layer2_adapter.py:165–185,189–214` constructs the real downstream payload and separates diagnostic values from scientific feature dictionaries.

## Narrow integration observations and order control

These values come from actual `fuse()` outputs. They are not inferred from source alone.

| Candidate output metric | Sensor only | Add agreeing zero diagnostic | Add disagreeing zero diagnostic | Qualified disagreement control |
|---|---:|---:|---:|---:|
| Scientific sensor feature confidence in real Layer 2 output | 0.95 | 0.95 | 0.95 | 0.85 |
| Scientific sensor uncertainty | 0.05 | 0.05 | 0.05 | 0.05 |
| Layer 2 group `confidence["vegetation"]` | 0.95 | 0.475 | 0.475 | 0.785 |
| Data-health confidence ceiling | 0.95 | 0.95 | 0.95 | 0.72 |
| Data-health `overall` | 0.515 | 0.538 | 0.518 | 0.518 |
| Data-health conflict penalty | 0 | 0 | 0.1 | 0.1 |
| Health status / Layer 2 usability | ok / true | ok / true | ok / true | ok / true |

The retained conflict changes the reported health score by 0.02 between the agreeing and disagreeing zero-quality controls. `diagnostics.py:422–450` averages all evidence freshness and counts all conflicts in that score. Adding the diagnostic source also changes source-completeness summaries. The scientific feature, global confidence ceiling, status and usability remain unchanged in the zero-quality controls. Such diagnostic/global-health differences alone are not treated as a new failure.

The Layer 2 group-confidence map averages both state and diagnostic features (`outputs/layer2_adapter.py:218–236`), so its vegetation confidence becomes `(0.95 + 0)/2 = 0.475` with either agreeing or disagreeing diagnostic. The exact parent also has this aggregate dilution (0.475 for agreeing zero, 0.425 for disagreeing zero because its sensor was penalized). The actual scientific feature dictionary retains the qualified sensor's 0.95 confidence in the candidate. This lane did not execute a Layer 3 consumer or establish that the group-summary change alters a qualified scientific state, posterior, training weight or decision; no new blocker is asserted from that difference.

The new confidence batch lookup at `confidence_model.py:139–146` contains live evidence references, not immutable copies. Two additional actual canonical ingestion-order controls reverse sensor/DRONE ledger order without fabricated conflicts. Both retain the same scope-canonical qualified-feature results: zero diagnostic leaves sensor confidence 0.95, and qualified disagreement leaves it 0.85. These are reachable-route controls, not a universal order-independence proof. Feature list order is canonicalized by feature/scope only for comparison; production ordering is preserved in raw results.

## Retained component, numeric and reconstruction controls

The adapted authored `probes.py` runs **112 fresh fixtures in seven groups for each snapshot**. Candidate and exact parent both pass all assertions. This run consumes source and newly authored fixtures, not old results, repository tests, audits or completion claims.

| Group | Fresh fixtures per snapshot | Retained boundary |
|---|---:|---|
| G01 | 9 | Finite scalar temporal admission, zero and missingness |
| G02 | 25 | Registered source adapter → source-context truth → validator → ledger → fused component selection |
| G03 | 14 | Typed/dictionary role restrictions |
| G04 | 18 | Restrictive aliases and existing typed statuses |
| G05 | 14 | R415-02 reconstruction declarations, alias conflicts and diagnostic retention |
| G06 | 14 | R415-05 natural SOILGRIDS/environment quantitative admission |
| G07 | 18 | Strong typed observation values/variance and valid-zero round trip |

**R415-02 remains bounded closed:** RECONSTRUCTION is not promoted to observed or state-updatable through the registered Sentinel2 route. Default confidence 1.0 is quarantined at the reconstruction ceiling; valid confidence 0.25 retains only diagnostic `ndvi_evidence=0.0`.

**R415-05 remains bounded closed:** SOILGRIDS clay numeric/malformed strings, booleans and infinity are rejected before ledger/fused soil-feature admission. Missing clay is omitted. Legitimate clay 0, finite clay 30 and valid sand survive. Mixed-row availability does not admit invalid components.

The actual-engine harness additionally retains the previous direct zero-quality repair controls: bad-only zero/nonfinite/malformed quality, baseline-plus-bad same-scope fixtures, mixed-variable valid siblings, legitimate zero values, validator rejection of zero-quality state permission, zero-preserving context floors and deliberately bypassed zero-weight fallback arithmetic. The bypass cases are explicitly not accepted engine transitions. Both snapshots pass these pre-existing direct controls.

## Identity, execution and reproducibility

Normative evidence was read directly from `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:151–177` and `current-plan-review/R3_current_scientific_sections.txt:675–681,738–744` (AB-DAT-005/006, AB-ARC-005/006). Their SHA-256 receipts are in each full manifest. These sources require component qualification before authority, preservation of valid zero, restrictive provenance roles and bounded degradation; they are distinct from candidate claims.

The full harness runs **58 actual-engine cases per snapshot in separate fresh interpreter processes**. All **885 staged source files** match their exact Git-tree blob hashes before and after each worker. Each worker records **82 imported repository files**, with module names, Git blob, SHA-256 and byte count. The component harness independently binds **49 imported repository files** per snapshot. Source trees and parent metadata are read-only; only this lane directory is written. Socket connection entry points fail closed. No production/Git edits, repository-module stubs, AST substitutions, repository tests/audit correctness proof, live provider/service calls, hardware, inference, optimizer, physical posterior, training or execution run.

The DRONE canonical envelope is intentionally routed through the perception package slot: the separate native structural adapter lacks canonical-envelope dispatch. Packet source DRONE still maps to evidence family `drone_structural`. This limits the result to the named native-perception route; native structural quality is another review lane. All fixture times are eligible and fixed, so these results do not establish F02 cutoff behavior. Real Layer 2/10 payloads are retained; no Layer 3 scientific effect is inferred.

Reproduce with the provided sibling source snapshots:

```bash
python review-e0e5b1e-f01/ledger/probes.py
python review-e0e5b1e-f01/ledger/probes.py --parent
python review-e0e5b1e-f01/ledger/full_fusion_probes.py
```

The driver asserts candidate repair, the freshly reproduced exact-parent failure, retained conflict lineage, the qualified disagreement penalty and narrow integration measurements. It no longer expects the old A263-01 residual to remain open. Every JSON file is strict JSON, with explicit markers for nonfinite fixture values. `artifact-manifest.json` binds the delivered scripts, fresh results, manifests, worker logs and this report.


---

# Specialist appendix: Native producers and source-aware role preservation

# Retained native producer / packet / bridge F01 verification — e0e5b1e

Candidate: `e0e5b1eabee73e8b17ce6849f4a23c05b302501a`.
Exact first parent: `a263b3033d6e637bef73ddf789d77659cd44e8f7`.
That parent's first parent: `5344930dfc7fbab7f7277bf61f99fc252dd88bc6`.

All **18 corrected producer checks pass on both exact revisions**. All 20 unchanged historical wrapper/quality controls also pass on both. The historical combined assertion that deliberate zero-quality and positive-quality mutations both survive is false on both, as expected: zero quality while still requesting a state update quarantines; positive finite quality survives. Fresh candidate and parent result groups and every check outcome are identical. This is retention evidence for the already corrected shared packet route, rather than evidence of a new producer repair in e0e5b1e. No new admission blocker was reproduced in this bounded lane.

The complete supplied production/config exports are exact: **885/885 candidate files and 885/885 parent files** pass Git-blob, SHA-256 and byte-count checks. The probe imports 56 distinct source files (85 module names); its two additional static references are the runner and engine. All 58 boundary files are byte-identical between candidate and parent. Candidate changes to native structural-drone extraction, confidence conflict handling and diagnostics are outside this retained shared-packet lane and need separate evidence.

## Actual route and execution boundary

The native route constructs production `PerceptionEngineOutput` and `PerceptionVariable` dataclasses with `PerceptionEngineFamily.DRONE`, the mapped `vegetation_fraction` variable, explicit QA flags and the documented `data_status` argument. It executes:

1. Actual `to_observation_packets` to emit native observation packets.
2. Actual `wrap_perception` with the same default wrapper route used by `Layer0Runner.run`.
3. A real `SourceRegistry`, registration of `PerceptionAdapter`, and retrieval through `get_adapter('perception')`.
4. The adapter's canonical `Layer0SourcePackageAdapter` delegation to the observation-packet bridge.
5. Package-aware normalization, validation and admission into an actual `EvidenceLedger`.

The direct packet-to-evidence bridge also runs independently on each packet. Results preserve the direct output, registered-adapter output before source-context admission, and admitted output as `direct_bridge`, `before_source_context_admission` and `accepted`. The separate final-defense controls deliberately mutate a genuine adapter item; they are not presented as a native producer route.

The whole fusion engine is not initialized or run. The script parses `Layer1FusionEngine._admit_evidence_or_quarantine` from the supplied engine, compiles its exact unmodified AST definition with production relative imports, and calls it with the actual package as `source_context`. Both revisions have method extent `engine.py:807–824` and method-body SHA-256 `6f91fd5d59bb4273941d6e6c6512c2da028f070320a61df91f7a95dc42fab23c`. The normal engine run extracts and source-normalizes at lines 154–159, validates at 163–172, and adds to the ledger at 174–180. Those normal-run lines are static references, not an executed full-run claim.

## Fresh retained quality and role results

Each of native output reliability, variable confidence and scene QA is independently set to **0, 0.4, Inf, NaN, True, False, malformed `bad`, null and -0.1**: 27 primary matrix cases per revision. Explicit `qa_flags=['CLEAN']` ensures every primary case reaches the quality qualifier. Each returns one packet and admits one evidence item without quarantine; all source envelopes validate without violations.

| Native input | Packet on both revisions | Direct bridge, registered adapter and admission on both revisions |
| --- | --- | --- |
| Reliability or variable confidence 0 / invalid | Reliability weight 0; scene score 0; valid-pixel fraction 0 | Confidence 0; reliability 0; diagnostic true; update false |
| Scene QA 0 / invalid | Scene score 0; valid-pixel fraction 0 | Confidence 0; reliability 0; diagnostic true; update false |
| Reliability or variable confidence 0.4 | Reliability weight 0.4; scene score 1 | Confidence 0.4; reliability 0.4; diagnostic false; update true |
| Scene QA 0.4 | Reliability weight 1; scene score 0.4 | Confidence 0.4; reliability 0.4; diagnostic false; update true |

“Invalid” in this table means Inf, NaN, both booleans, malformed, null or negative. A legitimate physical value **0.0** remains numeric zero through dataclass-to-JSON round trip and all evidence stages. With quality 1 it retains confidence/reliability 1 and update permission; with reliability 0.4 it retains confidence/reliability 0.4 and update permission. Zero quality is distinct from zero physical value.

Eight two-variable native outputs independently put zero or invalid confidence on `vegetation_fraction=0.2` while retaining `bare_soil_fraction=0.0` with confidence 0.4. Both packets and both ledger items survive on both revisions. The bad-quality variable becomes confidence/reliability 0, diagnostic and update-denied; the independent zero-value sibling remains confidence/reliability 0.4, nondiagnostic and update-allowed.

At positive native quality, observed DRONE evidence is accepted with confidence 1 and update permission. Simulated, estimated, fallback and unavailable retain their statuses, confidence ceilings 0.20 / 0.75 / 0.35 / 0.00, diagnostic status and update denial. Restricted roles do not gain real-provider-product, scientific-surface, prescription-driver or current-1m permission. The five roles at zero quality all retain confidence/reliability 0, diagnostic status and update denial; unavailable remains production-usable false.

Retained dictionary/typed controls freshly cover 40 role-alias cases across five aliases, four restrictive/conflicting-role cases, explicit dictionary reliability qualification and absent/default semantics, invalid or zero primary quality without positive fallback substitution, typed invalid weight/QA, valid zero NDVI serialization/admission, and invalid numeric NDVI quarantine. Native sensor controls construct actual normalized readings, QA and context packages, retrieve the registered `SensorAdapter`, and use package-aware admission. Inf, NaN, True, malformed and zero reliability yield confidence/reliability 0 and update denial; finite 0.4 survives with update permission; explicit update denial stays denied.

Final-defense mutations independently set `confidence` or `reliability` on a genuine adapter output. True and NaN quarantine; positive 0.4 survives. **Zero quality plus an unchanged state-update request quarantines on both revisions** with `ZERO_CONFIDENCE_OR_RELIABILITY_CANNOT_UPDATE_STATE`. Thus `R415_04_final_quality_zero_and_finite_survive` is deliberately retained as a historical false assertion in both `inherited_checks` blocks, while explicit replacement expectations pass. There is no expectation that the exact a263b30 parent reproduces the older 5344930 leak.

## Carried-forward default-QA availability receipt

The existing 27-case matrix without explicit QA flags is retained for parity, without expanding that inquiry. Twenty-five cases complete per revision and completed zero/invalid-quality cases are zero-gated. Malformed `bad` and null scene QA raise `TypeError` during automatic flag comparisons before any packet returns or adapter/ledger runs. The two exceptions are identical between candidate and exact parent. This is the already documented fail-closed availability limitation, not a new finding or sanitized diagnostic evidence. Primary malformed/null QA cases with supplied flags do reach and pass the qualifier.

## Exact source references

All references below are beneath the supplied `source/` root and are identical on the exact parent.

| Behavior | File and exact lines |
| --- | --- |
| Native DRONE source mapping | `services/agribrain/layer0/perception/common/packet_adapter.py:48` |
| Finite/nonboolean reliability/confidence; per-packet scene and valid-pixel quality | `services/agribrain/layer0/perception/common/packet_adapter.py:165–182` |
| Carried-forward automatic QA flag comparisons | `services/agribrain/layer0/perception/common/packet_adapter.py:152–155,250–262` |
| Default wrapper / actual runner call | `services/agribrain/layer0/wrappers.py:710–743`; `services/agribrain/layer0/runner.py:170–179` |
| Registry registration/retrieval; typed wrapper delegation | `services/agribrain/layer1_fusion/source_registry.py:60–72`; `services/agribrain/layer1_fusion/adapters/perception.py:23–31,79–82` |
| Package adapter bridge and source-package context | `services/agribrain/layer1_fusion/adapters/layer0_source_package.py:39–55` |
| Bridge intersection of scene score and reliability | `services/agribrain/layer1_fusion/adapters/observation_packet.py:127–137` |
| Bridge zero-quality diagnostic/update gates | `services/agribrain/layer1_fusion/adapters/observation_packet.py:207–209` |
| DRONE restricted-status and permission preservation | `services/agribrain/layer1_fusion/truth_bridge.py:399–422` |
| Native sensor finite-quality and update gates | `services/agribrain/layer1_fusion/adapters/sensors.py:73–105` |
| Final strict finite/nonboolean quality; zero-quality update refusal | `services/agribrain/layer1_fusion/evidence_validation.py:61–67,103–104` |
| Executed isolated admission method / static normal run | `services/agribrain/layer1_fusion/engine.py:807–824,154–180` |

## Normative identities and scope

The selected normative plans are the master repair plan, work-package task list and sequencing addendum under `sr-team-review/plan/`. Fresh local Git-blob identities match both candidate and parent trees. The optional detailed implementation plan is excluded from normative/correctness evidence.

Master F01 is exactly **lines 151–177** of `AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`. It identifies AB-DAT-005, AB-DAT-006, AB-ARC-005 and AB-ARC-006 (155), role preservation through typed/dictionary adapters (170), invalid numeric state/training exclusion (175), legitimate-zero round trips (176), and authority/counts following admitted components (177). This lane establishes producer/packet/admission behavior and accepted evidence-item counts only. It does not establish solver assimilation, posterior/state deltas, training influence or full F01 completion.

All **52 FA rows** and the five F01 rows in the selected task register are unchecked. Those register states are freshly asserted and describe checkboxes, not proof of implemented or absent behavior. F01 task rows are within task-list lines 156–186.

The supplied scientific extract identifies R3 AB-DAT-005 at lines 675–677, AB-DAT-006 at 679–681, AB-ARC-005 at 738–740 and AB-ARC-006 at 742–744. The supplied R3 PDF, full-text extraction and standalone scientific extract are pinned by fresh SHA-256 checks:

| Supplied reference | SHA-256 |
| --- | --- |
| `sr-team-review/monograph-source/AgriWise_AgriBrain_Monographie_Maitre_FR_R3.pdf` | `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f` |
| `sr-team-review/R3-full-text.txt` | `472d8f890098c5470b674ca468fb3e456a14bfd86c10935770fd7fb796a9c66d` |
| `current-plan-review/R3_current_scientific_sections.txt` | `b3e541a1258ee296d5551e7ac88bfbf2bfedc339f0345c02c9166dbf02701e7c` |

These reference files are supplied normative material, not candidate production files. `plan-results.json` records identities, exact requirement lines, plan blobs and register counts.

## Reproduction and artifacts

From `review-e0e5b1e-f01/`, preserving the supplied sibling source/reference layout:

```sh
PYTHONDONTWRITEBYTECODE=1 python platform/wrapper_probes.py
PYTHONDONTWRITEBYTECODE=1 python platform/wrapper_probes.py --source ../review-a263b30-f01/source --output parent-results.json --parent-control
PYTHONDONTWRITEBYTECODE=1 python platform/verify_metadata.py
```

The scripts are self-contained and import no previous reviewer code. Their expected arguments and SHA-256 identities are in `authored-manifest.json`. Both runs freshly execute the same native routes. Historical reviewer outputs and repository tests/audits are not correctness evidence. Strict JSON results encode nonfinite fixture values as `nonfinite_repr`; JSON serialization sets `allow_nan=False`.

| Artifact | Purpose |
| --- | --- |
| `results.json`, `parent-results.json` | Fresh native/typed/dictionary routes, three-stage evidence receipts and checks |
| `source-manifest.json`, `parent-source-manifest.json` | Complete 885-file corpus identities for each revision |
| `import-manifest.json` | Actual imported modules/files and static reference flags |
| `parent-boundary-comparison.json` | 58/58 identical boundary files and fresh result parity |
| `plan-results.json` | Normative plan identities, R3 pins and 52-FA/F01 register status |
| `candidate-console.txt`, `parent-console.txt`, `metadata-console.txt` | Fresh command console captures |
| `authored-manifest.json` | Reviewer script hashes and expected reproduction commands |

Only reviewer-authored files under this new `platform/` directory were written. Production source and Git were not changed. No repository tests, services, providers, full fusion run, optimizer, training, controllers, radios or drone hardware ran. Ledger counts are admitted evidence-item counts. Full engine, downstream influence, other F01 lanes and overall completion remain outside this report.


---

# Specialist appendix: Downstream structural signals and retained native water controls

# Native A263-02 repair and retained water verification

Candidate `e0e5b1eabee73e8b17ce6849f4a23c05b302501a`; exact parent `a263b3033d6e637bef73ddf789d77659cd44e8f7`. Fresh execution: 2026-10-21. Scope: independent native structural quality repair, retained canonical-packet controls, and the existing water/history lane.

**A263-02 is CLOSED_BOUNDED.** Native zero/NaN-reliability outputs no longer acquire actionable structural values or downstream weed severity. A separately qualified weed sibling remains .30 with actual L3 weed severity .24; exact parent admits the invalid .60 sibling and changes those results to .45/.36. Typed and dictionary quality cases pass all 138 checks. Retained water passes 52/52 checks over 45 variants on both versions. These outcomes close the named bypass within this tested route; they do not close F01 full acceptance or authorize a final decision.

## Actual route and corrected outcomes

The primary input is an actual `DroneRGBOutput`, or the supported plain dictionary representation of the same native carrier, supplied through `Layer1InputBundle.drone_structural_packages`. The registered `DroneStructuralAdapter` runs inside the real `Layer1FusionEngine.fuse`; the harness then runs the real `Layer2IntelligenceEngine.analyze`, actual structural extractor and `build_layer3_context`, and native `build_decision_features`. It never substitutes the separately projected typed-boundary fixture for real L2 output.

| Native direct input | Candidate actionable canopy / weed | Candidate actual L3 weed severity | Exact-parent actionable canopy / weed | Exact-parent actual L3 weed severity |
|---|---|---:|---|---:|
| QA 1, reliability 1, values .70/.60 | .70 / .60 | .48 | .70 / .60 | .48 |
| QA 1, reliability 0 | absent / absent | 0 | .70 / .60 | .48 |
| QA 1, reliability NaN | absent / absent | 0 | .70 / .60 | .48 |
| QA 0, reliability 1 | absent / absent | 0 | absent / absent | 0 |
| QA NaN, reliability 1 | absent / absent | 0 | absent / absent | 0 |
| Qualified .30 weed alone | absent / .30 | .24 | absent / .30 | .24 |
| Qualified .30 weed + zero-quality .60 sibling | absent / .30 | .24 | absent / .45 | .36 |
| Qualified .30 weed + NaN-quality .60 sibling | absent / .30 | .24 | absent / .45 | .36 |
| QA .85 / reliability 1, or QA 1 / reliability .85 | .70 / .60 | .48 | .70 / .60 | .48 |
| Qualified legitimate zero canopy / weed | 0 / 0 | 0 | 0 / 0 | 0 |

The positive controls make the closure nonvacuous: real L2 attributes weed as `BIOTIC` / `weed_pressure_detected`, the actual L3 adapter emits weed severity .48, and the decision feature builder copies that availability/severity. In the corrected standalone invalid-quality controls, both actual L3 and decision features have `has_drone_structural=False` and weed severity zero. In the corrected mixed cases they retain `has_drone_structural=True`, with severity .24 supplied by the qualified sibling. The original specialized lane now passes 9/9 checks versus exact parent's 5/9. Both exact versions pass the retained canonical generic packet boundary's 32/32 checks.

## Quality, diagnostic retention and provenance

Candidate `layer1_fusion/adapters/drone.py:44–100` qualifies QA and inherited reliability using `finite_real`, combines them as their minimum, and assigns zero effective quality to unqualified explicit values. `scientific_contracts/numeric.py:10–23` rejects booleans, numeric strings, malformed values and nonfinite scalars while preserving physical zero. `drone.py:133–176` converts zero effective quality to confidence/reliability zero, `diagnostic_only=True`, `state_update_allowed=False`, and a `DIAGNOSTIC_ONLY` flag. `drone.py:282–306` gives such a source an explicit `unusable` envelope and zero trust. The parent adapter instead derives its capabilities only from QA (`drone.py:69–104`) and loses the reliability restriction.

All 44 fresh typed/dictionary quality variants execute without errors on candidate and pass 138/138 checks. They cover finite QA/reliability .85 and 1, legitimate zero canopy/weed/bare-soil values, explicit rejected missions, and zero, NaN, positive infinity, boolean, numeric-string, malformed-string and explicit-None QA or reliability. Mixed zero/NaN/infinite-reliability siblings preserve qualified weed .30 and L3 severity .24 in both carrier forms. Exact parent passes 44/126 assertions; four malformed/None-QA variants raise during full fusion, and the remaining failures reflect the old admission, envelope and diagnostic behavior. Assertion counts differ because an execution error replaces that case's four detailed checks with one execution check.

QA zero is readable native diagnostic input on candidate, with an unusable source envelope and retained diagnostic evidence. It is distinct from `is_valid=False`, which remains unreadable and yields no native structural extraction. This distinction is preserved in results; diagnostic retention is not described as whole-input rejection. Native diagnostic records retain their source identity, mission-derived evidence IDs and generated provenance references. The mixed fused context deliberately still lists diagnostic source IDs and has source count two. Its scientific value, confidence and downstream severity match the qualified-only control. This retained lineage is not counted as scientific influence or as a failed A263-02 repair; no claim is made that those metadata counts identify only influential sources.

Four additional malformed-core controls—numeric-string canopy and boolean weed, in typed and dictionary form—now omit the malformed field while preserving the independently valid core field. Parent coerces those values. These are bounded checks of the same changed scalar qualification, not a new survey of structural metrics.

## L3 usability and existing transport limits

The qualified positive, qualified-zero and mixed-sibling fixtures have actual L3 `usable_for_layer3=False`, `diagnostic_usable=True`, data health .38, confidence ceiling .5 and status `degraded`. Candidate standalone zero/NaN-quality cases have `usable_for_layer3=False`, `diagnostic_usable=False`, data health .35 and confidence ceiling zero. The actual feature builder still executes, so this review proves its content and the intervening admission/interpretation behavior. It does not prove an authorized decision, prescription, actuator action, durable decision-state update, or whole-season outcome. Complete usability fields are retained for every compact comparison.

Actual L2 still does not transport named canopy/weed `VegetationFeature` values: actual decision features have `canopy_cover_ratio=0`, `bare_soil_ratio=0` and `weed_pressure_index=0` even for the qualified positive native fixture. The positive actual signal established here is weed severity/availability, plus canopy admission at L1. `zone_intelligence.py:25–85` and `outputs/layer3_adapter.py:251–320` explain this existing transport limit. Each successful route also has a separately labeled native `Layer2Output` / `VegetationFeature` projection to exercise typed L3 handling, including legitimate zeros. That projection is never evidence of actual L2 transport.

The retained four routes remain separate: native shared perception payload, separate generic canonical packet fixture, specialized native `DronePacketizer` payload, and direct registered native structural adapter. Shared top-level variable payloads and specialized nested `summary_metrics` remain omitted by the canonical bridge, including their positive controls (`packet_adapter.py:193–199`; `drone_rgb/packetizer.py:25–41`; `adapters/observation_packet.py:220–227,278–299`). These previously characterized omissions and the typed canopy transport limitation are capability limits, not newly counted defects in this review.

## Adjacent inherited availability qualification

The already bounded `row_count=+Infinity` case raises `OverflowError: cannot convert float infinity to integer` in both carrier forms and both exact versions, even alongside a qualified .30 weed sibling. The fresh stack traverses actual `Layer1FusionEngine.fuse` (`engine.py:156`) into candidate `drone.py:208`; parent fails at `drone.py:134`. Candidate catches `ValueError` and `TypeError` at lines 211–212 but leaves `OverflowError` uncaught. This prevents fusion/L2/L3 completion for that bundle; it demonstrates availability failure, not nonfinite state contribution or quality-based promotion. It is an inherited adjacent limitation, nonblocking for the named A263-02 closure and not a newly introduced regression. No further count, geometry, orchard, service or hardware search was performed. The scalar-boundary appendix is 4/6 on candidate and 0/6 on parent, with two count-infinity execution errors on each; it is kept separate from native quality closure.

## Retained water and history checks

`probes.py` adapts the prior independent authored harness and reruns native `SoilObservationVector`, actual `WaterStateAssimilator` and full `WaterIntelligenceEngine` on both exact versions. Both pass all 52 checks across 45 variants. Native read-only tracing verifies the admitted-row identities and counts agree with direct diagnostics and full water pipeline admission. Direct prior objects remain unchanged; every zero-row case has zero direct and full analysis increment.

The controls retain finite and legitimate-zero values, NaN/infinity/bool/malformed rows, valid/invalid uncertainty, OBSERVED/SIMULATED/FORECAST/EXCLUDED roles, global/component restrictions, satellite/thermal branches, and zero/nonfinite quality. The unchanged production serializer/deserializer AST definitions execute exactly, followed by strict JSON dump/load and native downstream consumption; the decision module, durable persistence and full decision runner do not execute. Generic EXCLUDED before/after TDR identity, standalone EXCLUDED and source-scoped excluded TDR all remain zero-row, zero-increment, MODELLED cases. Satellite-specific exclusion preserves three qualified TDR rows and OBSERVED authority. Positive moisture admits three rows with +82.05 mm direct and +89.70 mm full analysis increment. The previously corrected R39-01 behavior remains intact.

## Normative basis and reproduction

F01 master plan: `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:151–177`; R3: `current-plan-review/R3_current_scientific_sections.txt:675–681` (AB-DAT-005/006) and `738–744` (AB-ARC-005/006). These require numeric qualification, preservation of legitimate zero and per-field restrictions, separation of diagnostic/update capabilities, and bounded degradation. The conclusions above are limited to fresh observed outcomes at these boundaries, not a declaration that all F01 completion criteria hold.

The structural manifests verify 137 imported production Python files against each exact Git tree; retained water manifests verify 64 each. Source was verified before execution and rechecked after import; no production functions, dependencies, clocks or engines were substituted. Read-only profiling records candidate 97 full `fuse` invocations / 95 `analyze`, and parent 97 / 91, with the differences explained by recorded malformed-QA and count-infinity exceptions. Candidate executes 190 actual `build_layer3_context` and feature-builder calls: 95 real-L2 routes plus 95 separately labeled typed projections. Parent executes 182 of each. Full native call counts, raw inputs, initial adapter capabilities, diagnostics, provenance, actual L2 output, actual L3 contexts/features, projected fixtures and failures are preserved in the strict JSON results.

`comparison.json` retains compact fresh contrasts and actual usability flags. `line-evidence.json` provides exact candidate/parent/normative/harness ranges, Git blobs, file SHA-256 and excerpt SHA-256; it also verifies the two history helper AST hashes are unchanged. `manifest.json` hashes lane artifacts. This lane writes only its new `decision` directory and makes no production or Git changes. Repository tests, audits and implementation-authored acceptance documents are not correctness proof. No provider, inference image, external service, hardware, training, durable history/decision persistence or actuator execution is claimed.

Run from the workspace root:

```bash
python review-e0e5b1e-f01/decision/probes.py
python review-e0e5b1e-f01/decision/probes.py --parent-compatibility
python review-e0e5b1e-f01/decision/structural_probes.py
python review-e0e5b1e-f01/decision/structural_probes.py --parent-compatibility
python review-e0e5b1e-f01/decision/build_evidence.py
```

Scripts save strict JSON summaries even for failed expected-behavior checks; a zero process exit means execution completed, not that every expectation passed. Nonfinite inputs remain native numerical values during execution and are stringified only while saving JSON. F01 full acceptance remains open.


---

# Specialist appendix: Canonical weather to crop features

# F01 weather/crop retained qualification at e0e5b1e

**Verdict: the prior named daily-dictionary weather qualification claim is retained at `e0e5b1eabee73e8b17ce6849f4a23c05b302501a`, parent `a263b3033d6e637bef73ddf789d77659cd44e8f7`.** A fresh offline production-source process completed 43 cases and 241 strict boolean controls with 241 passes, no failed checks, and exit 0. No blocking finding was reproduced in this bounded lane. This is a retention result for the named weather/crop admission seam, not acceptance of all F01 requirements.

## Normative basis and scope

The normative master is `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`, lines 151–177, F01: preserve zero and missingness, qualify components before authority, carry source roles through typed/dictionary adapters without promotion, and extend qualification to weather/crop consumers. The current R3 basis is `current-plan-review/R3_current_scientific_sections.txt`, lines 675–681 (AB-DAT-005 zero/missingness and AB-DAT-006 field provenance) and 738–744 (AB-ARC-005 factored authority and AB-ARC-006 bounded degradation). Their hashes and exact normative ranges are recorded in `source-import-manifest.json`.

The executed path is `wrap_environment` → its actual `evidence_records` → `build_canonical_crop_observations` → `build_crop_evidence_ledger` → `observation_tokens_from_ledger` → `build_ledger_crop_feature_input`. The fixtures are in-memory daily weather dictionaries and complete local 4×4 Sentinel-2 arrays. The six-scene fixture uses distinct physical product identities dated 2026-10-01, 04, 07, 10, 13 and 19, before the review date of 2026-10-21. No future/cutoff experiment was added.

Only the parent authored `ownership/probes.py` code was reused as harness material; candidate/parent pins and the reproduction path were updated. All outputs below were regenerated against this candidate. Previous results, repository tests, repository audits and generated repository artifacts are excluded as proof. No broad alias/unit hunt was performed. No source/Git writes, provider requests, services, hardware, classifier/model execution, training or prescription/publication execution occurred. The orchestrator and posterior call paths listed in the manifest were inspected statically only. Only `review-e0e5b1e-f01/ownership/` was written by this lane.

## Fresh result matrix

Execution started at `2026-10-21T12:23:57.062520+00:00` and finished at `2026-10-21T12:23:59.020095+00:00`, under Python `3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]`. The command was `python review-e0e5b1e-f01/ownership/probes.py` from `/workspace/scratch/de6bc2428cec`.

| Executed group | Cases | Passing strict controls |
|---|---:|---:|
| Crop dtype and support | 10 | 33/33 |
| Sentinel-2 scene roles | 7 | 35/35 |
| Weather numeric controls | 11 | 25/25 |
| Canonical weather role seam | 7 | 44/44 |
| Six-scene engineered inputs | 8 | 104/104 |
| **Total** | **43** | **241/241** |

The crop numeric/support controls retain finite arrays, legitimate zero NDVI, boolean DATAMASK, integer categorical SCL and partial finite support. Boolean, numeric-string, object and complex reflectance are rejected; an all-nonfinite band has no admitted optical token. With one infinite core pixel, the remaining 15 finite pixels remain eligible. A partial boolean mask retains eight eligible pixels.

The seven scene-role controls cover observed, excluded, synthetic, prior, forecast, fallback, and observation-role/excluded-`source_role` conflict. Only observed physical scene evidence supplies an actual model token and state-update authority. Every nonobserved scene-role case blocks the engineered adapter because crop-cycle segmentation requires admitted physical evidence.

The weather numeric controls preserve zero and finite 20 °C. Zero yields GDD0/GDD5/GDD10/GDD12 all at 0; 20 °C yields 20/15/10/8. Boolean, numeric string, NaN, infinity and absent temperature yield no thermal coordinates. Finite min/max fallback remains valid, boolean min/max and boolean explicit GDD are rejected, and explicit zero `gdd` yields only the historical GDD10=0 axis. Missing or rejected weather does not reject valid optical evidence.

## Actual canonical roles and downstream inputs

| Weather declaration in each supplied daily dictionary | Canonical status | Actual six-token GDD10 | Engineered thermal values |
|---|---|---|---|
| `role=OBSERVATION`, observed status | observed × 6 | 10, 20, 30, 40, 50, 60 | All five present |
| `role=EXCLUDED`, unavailable status | unavailable × 6 | All absent | All five missing |
| Unavailable status only | unavailable × 6 | All absent | All five missing |
| Observation role + unavailable status | unavailable × 6 | All absent | All five missing |
| Observation role + `source_role=EXCLUDED` | unavailable × 6 | All absent | All five missing |
| Synthetic role + simulated status | simulated × 6 | 10, 20, 30, 40, 50, 60 | Present as process forcing |
| Forecast role + estimated status | estimated × 6 | 10, 20, 30, 40, 50, 60 | Present as process forcing |
| No weather | Empty | All absent | All five missing |

Packet status and canonical weather status preserve all seven named declarations. Every returned canonical weather row has `authority=process_forcing_only` and `state_update_allowed=false`. The four unavailable/excluded declarations cannot enter canonical crop thermal coordinates or actual ledger-derived token thermal coordinates. Direct consumer controls also reject unavailable status alone and observation role plus unavailable status.

Forecast and synthetic thermal forcing are permitted in this retained claim. Their canonical statuses remain estimated/simulated, with process-forcing authority and no state-update authority. Their numeric inputs equal the observed 20 °C control; that equality is not treated as a failure. This result establishes the named transport/admission behavior, not complete per-field lineage in every downstream artifact.

The engineered receipt is built from six actual eligible optical tokens. All eight weather cases retain six model-use-eligible ledger items, six optical tokens and a quality mask of six `true` entries. The five and only five input features that change for the unavailable/excluded and absent-weather cases are:

| Engineered feature | Observed/synthetic/forecast forcing | Unavailable/excluded/absent weather |
|---|---:|---|
| `sos_gdd` | 20.0 | missing |
| `pos_gdd` | 40.0 | missing |
| `eos_gdd` | 50.0 | missing |
| `growth_rate_per_gdd` | 0.0147857143 | missing |
| `senescence_rate_per_gdd` | -0.0135714286 | missing |

All other tensor features remain equal to the observed control. Actual tensor values, feature order, missingness mask, quality mask, tensor and receipt hashes, canonical weather, ledger items and token coordinates are retained per case in `results.json`.

The observed thermal tensor hash is `13e29898129245b63cad3f4dd9a547c57ac7adc9f716cc6e37cef8bef85c5f30`. The four unavailable/excluded cases and missing-weather control share `7973551439d905552bee8b6a3545c55a41c8d6dab4ec692f98d49a4204b4f42f`. Their respective receipt hashes are `dfabade60453db5ef44debc5fd8fe4e25e34b5ca2b5fd936262a8818fcc3daa6` and `0f5e2fb2d09ba55d80a6e60e4d9c53fe15607f5104816b2cb8029164686c9931`. Feature completeness is 22/66 with the five thermal features and 17/66 without them.

Every six-scene receipt has `model_execution_eligible=false` and `publication_eligible=false`. The actual blockers are `crop_cycle_phase_coverage_insufficient`, `feature_tensor_incomplete`, `model_domain_not_verified`, and `probability_calibration_not_validated`. These are observed input-receipt gates; no model or publication pipeline ran.

## Exact source/function manifest

All paths in this table are relative to `review-e0e5b1e-f01/source/services/agribrain/`. The listed function definitions are invoked directly or transitively by the probes and located from the exact candidate AST. Definition ranges locate source, not line/branch coverage.

| Candidate source file | Invoked function | Definition lines |
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

The separate source-import manifest records 66 imported candidate module identities spanning 43 distinct production files, with aliases retained; every imported file has its local path, Git blob, SHA-256, byte and line counts. It also records the four static-only call-path files, normative sources, and probe SHA-256 `646b91dfcb2997c18c75abc55112054d8df9a176c0befa94f7622897b4784332`.

## Reproduction and integrity

```bash
python review-e0e5b1e-f01/ownership/probes.py
```

The process checks the exact candidate and sole-parent metadata, verifies the exact 885-file exported path set, and verifies every export against its candidate Git-tree blob and staged SHA-256. All checks must be strict Python booleans. JSON is emitted with `allow_nan=false`; authored nonfinite inputs are represented explicitly rather than written as invalid JSON. Bytecode writes are disabled. Failure of any named control produces a nonzero exit.

Deliverables are `probes.py`, fresh `results.json`, `source-import-manifest.json`, `report.md`, and `execution-receipt.json`. The receipt verifies strict JSON, fresh results, source snapshot integrity and artifact hashes. No full F01, classifier accuracy, training, provider, hardware or production-service conclusion is asserted.


---

# Specialist appendix: Actual label consumption, training decisions and legacy read parity

# Retained F01 training admission — e0e5b1e

**Disposition: retained bounded training claims pass. No new finding in this lane. Full F01 acceptance remains outside this evidence.**

Candidate: `e0e5b1eabee73e8b17ce6849f4a23c05b302501a`. Actual immediate parent: `a263b3033d6e637bef73ddf789d77659cd44e8f7`. The exact39 comparator `39b94d8de2911cdbaa9e86d24a46f40464cba101` and older415 writer `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe` are historical defect controls, not the immediate parent.

Fresh execution: `2026-10-21T16:18:09.530594+00:00` through `2026-10-21T16:18:16.759172+00:00`. The authored harness was adapted from parent probe code only. Previous reports, previous generated outputs, repository tests, audit files, and commit claims are not correctness evidence.

## Governing scope

The master F01 card (`sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:151–177`) requires finite admission, zero preservation, role propagation and qualified training admission. The relevant R3 mappings are AB-DAT-005 (zero/missingness), AB-DAT-006 (field provenance), AB-ARC-005 (separate authority), and AB-ARC-006 (bounded degradation); the R3 crosswalk is `output/implementation-plan/AgriWise_AgriBrain_Detailed_Implementation_Plan_R3.md:3111–3112,3130–3131`.

This lane exercises actual weak-label exporter → ASMAE adapter → validation/floor/fusion of the adapter’s training-weight items, and actual run ledger → validation schema/writer → disagreement → candidate update → replay → dataset reader. The new optional confidence map is exercised with actual adapter evidence. Engine callers are statically traced. There is no full ASMAE/L1 engine execution, optimizer, model fitting, service/provider/hardware access, or empirical field validation. Only this new trajectory directory is written; production source and Git are untouched.

## Results

| Evidence | Result |
|---|---|
| Retained closure and preservation checks | 22 / 22 pass |
| Bounded actual L1 training consumers | 4 / 4 pass |
| Optional confidence API compatibility | 3 / 3 pass |
| Fresh control/replay assertions | 6 / 6 pass |
| Probe execution / approval-origin checks | 3 / 3 pass |
| Probe groups | 8, with 122 named dynamic cases and a static registry/caller group |

All three executions completed successfully. Candidate results and all JSON manifests use strict JSON; nonfinite fixture values are represented as tagged objects in results. Private JSONL ledgers intentionally retain the production serialization of malformed legacy fixture values.

| Actual weak-label input | Exporter weight | Adapter training value | Role |
|---|---:|---:|---|
| `valid_zero` | 0.3 | 0.3 | diagnostic; state update blocked |
| `valid_finite` | 0.3 | 0.3 | diagnostic; state update blocked |
| `nan_estimate` | 0.0 | 0.0 | diagnostic; state update blocked |
| `infinite_estimate` | 0.0 | 0.0 | diagnostic; state update blocked |
| `boolean_estimate` | 0.0 | 0.0 | diagnostic; state update blocked |
| `string_estimate` | 0.0 | 0.0 | diagnostic; state update blocked |

The actual training items pass `validate_evidence` and `check_confidence_floor` unchanged. `fuse_features` adds no state-context feature and gives no source-completeness credit. Shadow/no-scene exports emit no training evidence. Zero-scene, failed-radiometric and one-metre controls retain zero weight. For four continuous validation targets, finite 0.5 and legitimate zero each yield one approved sample; NaN, infinity, booleans and strings fail before event append. Malformed confidence and named fractional-biotic values are blocked, categorical/event controls survive, and excluded source/role/resolution and contradictory observations yield no sample.

The current `compute_confidence(item, conflicts, items_by_id=None)` accepts the existing two-argument call. The optional map call and two-argument batch call return the same no-conflict confidence (0.5 for these diagnostic items). That score is API compatibility evidence, not training weight: the actual 0.3/0.0 training values and diagnostic/no-state flags remain unchanged. Batch receives deep copies because production batch confidence computation mutates confidence.

## Unchanged production-approved legacy ledgers

Fresh exact415 production writer calls generate the approvals. Both candidate and exact39 then read the same private ledger bytes without editing any row. Hashes below are checked before and after both reads; `same-bytes-replay.json` records the comparison.

| Fractional-biotic observed value | 415 approved samples | Exact39 reader | Candidate reader | Same bytes SHA-256 |
|---|---:|---:|---:|---|
| `biotic_fraction_numeric_string` | 1 | 1 | 0 | `c6768bdca2c864eac55486c41965ea77b88389bbf25d2c4cac76bd1a4b518134` |
| `biotic_fraction_bad_string` | 1 | 1 | 0 | `47357a2827e9e607cf9535564e307897124473bd0fa7f38c379fc539ca9e0b7e` |
| `biotic_fraction_nan` | 1 | 0 | 0 | `e78c18add36fcd655bc909373fe18da52d5ed02c4550d6e328232db1559f5d8d` |

The numeric-string and malformed-string controls reproduce the named exact39 reader defect (one sample) while candidate rejects both (zero). Both readers reject the older approved NaN ledger. Current writer schema also rejects these same malformed fractional-biotic events. Separate P4 fixtures mutate only an event in a newly production-approved valid seed; their generated approval is retained unchanged. P4 demonstrates reader defense only and is not presented as current-writer acceptance.

| Selected resolution in freshly exact39-approved ledger | Exact39 writer samples | Candidate writer status / samples | Candidate reads unchanged exact39 bytes |
|---|---:|---|---:|
| `resolution_boolean_false` | 1 | pending / 0 | 0 |
| `resolution_zero` | 1 | pending / 0 | 0 |
| `resolution_missing_selected_valid_fallback` | 1 | approved / 1 | 1 |
| `resolution_none_selected_valid_fallback` | 1 | approved / 1 | 1 |

False and zero are explicitly present invalid selections; candidate records `invalid_resolution` and rejects their unchanged exact39-approved ledgers. Absent and None selected resolution use the valid 10 m run fallback and preserve one sample in both writer and reader. No hand-authored approval or candidate row is used for these contrasts.

Exact39 has the two expected failed historical closure checks (selected resolution and fractional-biotic legacy-reader parity); all its observed contrast assertions pass. Exact415 additionally reproduces its missing L1 helper and malformed gate/comparator/reader behavior; those are expected controls, not candidate failures.

## Check register

| Candidate closure check | Result |
|---|---|
| `valid_weak_zero_and_point5_preserve_point30_at_exporter` | PASS |
| `valid_weak_zero_and_point5_reach_l1_point30_without_error` | PASS |
| `malformed_weak_estimates_zero_at_exporter_and_l1` | PASS |
| `four_continuous_finite_and_zero_preserved` | PASS |
| `four_continuous_malformed_targets_blocked_before_event_append` | PASS |
| `malformed_and_out_of_range_confidence_blocked_before_event_append` | PASS |
| `categorical_and_event_controls_preserved` | PASS |
| `named_fractional_biotic_malformed_types_blocked_at_writer` | PASS |
| `explicit_exclusions_and_finite_contradiction_produce_no_sample` | PASS |
| `uncertainty_nonfinite_boolean_and_out_of_range_gates_reject` | PASS |
| `retro_nonfinite_boolean_and_out_of_range_gates_reject` | PASS |
| `resolution_nonfinite_boolean_and_out_of_range_gates_reject` | PASS |
| `nan_model_comparator_rejects_finite_target` | PASS |
| `valid_uncertainty_zero_and_retro_boundary_preserved` | PASS |
| `legacy_continuous_and_confidence_above_one_reader_reject` | PASS |
| `legacy_fractional_biotic_writer_reader_parity` | PASS |
| `selected_resolution_missing_and_none_use_valid10_fallback` | PASS |
| `biotic_float_and_zero_preserved` | PASS |
| `biotic_low_medium_high_aphids_categories_preserved` | PASS |
| `biotic_fraction_low_medium_high_qualitative_controls_preserved` | PASS |
| `schema_disagreement_dataset_share_one_classifier` | PASS |
| `shared_classifier_continuous_and_qualitative_categories_match_scope` | PASS |

| Additional bounded / compatibility check | Result |
|---|---|
| `actual_training_weight_values_and_diagnostic_no_state_flags_preserved` | PASS |
| `validation_and_floor_do_not_reject_or_change_actual_training_items` | PASS |
| `actual_training_items_add_no_state_context_or_source_completeness_credit` | PASS |
| `shadow_and_no_scene_training_evidence_remains_absent` | PASS |
| `new_items_map_argument_is_optional_with_none_default` | PASS |
| `legacy_direct_and_batch_callers_complete_with_same_no_conflict_scores` | PASS |
| `actual_training_values_and_diagnostic_state_flags_preserved_by_confidence_calls` | PASS |

## Source anchors and integrity

All paths below are relative to the candidate `source/` directory. `source-evidence.json` preserves the exact numbered source excerpts and whole-file SHA-256 values.

| Purpose | Exact source anchor |
|---|---|
| Finite numeric qualifier | `services/agribrain/scientific_contracts/numeric.py:10–22` |
| Weak-label estimate admission and weight | `services/agribrain/layer05_asmae/training/exporter.py:145–209` |
| Actual ASMAE training evidence and role flags | `services/agribrain/layer1_fusion/adapters/asmae_adapter.py:414–449` |
| Shared target classifier and writer numeric admission | `services/agribrain/asmae_learn/schemas.py:59–126` |
| Production event append and candidate approval generation | `services/agribrain/asmae_learn/validation_events.py:29–119` |
| Selected resolution qualification before candidacy | `services/agribrain/asmae_learn/candidate_builder.py:80–94` |
| Uncertainty and retro gate qualification | `services/agribrain/asmae_learn/candidate_builder.py:128–158` |
| Finite comparator and target disagreement | `services/agribrain/asmae_learn/disagreement.py:190–230` |
| Reader approval, role, and selected-resolution defenses | `services/agribrain/asmae_learn/dataset_builder.py:93–127` |
| Reader confidence and continuous target qualification | `services/agribrain/asmae_learn/dataset_builder.py:169–190` |
| Evidence validation | `services/agribrain/layer1_fusion/evidence_validation.py:40–123` |
| Bounded confidence floor | `services/agribrain/layer1_fusion/context_invariants.py:187–231` |
| Fused state and completeness eligibility | `services/agribrain/layer1_fusion/fusion_rules.py:239–288` |
| Completeness excludes diagnostic and state-ineligible evidence | `services/agribrain/layer1_fusion/fusion_rules.py:370–438` |
| Optional confidence argument and batch caller | `services/agribrain/layer1_fusion/confidence_model.py:76–147` |
| Declared L1 batch caller, statically traced only | `services/agribrain/layer1_fusion/engine.py:244–247` |

The post-execution manifests verify every staged production byte against its Git blob and staging record: candidate 885 files (59 imported), exact39 876 files (56 imported), exact415 876 files (51 imported). Metadata SHA-256 values, imported production paths, explicit static paths and every staged file hash are included. Byte integrity is not function/branch coverage.

## Reproduction

From the directory containing all three review roots:

```bash
python review-e0e5b1e-f01/trajectory/probes.py --comparison-parent-root review-39b94d8-f01 --legacy-parent-root review-4157ac1-f01
python review-e0e5b1e-f01/trajectory/write_report.py
```

`replay-manifest.json` records intended and actual argument vectors, source roots, source counts, metadata dependencies, runtime and environment. `results.json` and the two control result files contain inputs, actual statuses, sample outputs, named assertions and ledger provenance. The harness reruns historical production writers in isolated interpreters before the candidate reads their fresh ledgers. All writes and private ledgers stay below this trajectory directory. No production/Git mutation is required.

Retained training closure is supported for these named boundaries and controls. Arbitrary target/unit matrices, complete engine execution, model quality, and whole-package F01 acceptance are not established.


---

# Specialist appendix: Contained RF covariance admission

# F01 RF covariance qualification retained at e0e5b1e

**Disposition: bounded software closure retained at candidate `e0e5b1eabee73e8b17ce6849f4a23c05b302501a`, parent `a263b3033d6e637bef73ddf789d77659cd44e8f7`.** Explicit invalid covariance is not promoted to the model default along the real typed likelihood → MESIA operator → Layer 0 spine → ASMAE adapter → private dispatcher composition. The nine named bad values become proposal variance `None`, status `ABSENT`, unusable for assimilation, no event, and no private queue entry. No new RF finding is counted. This is not full F01 acceptance or a posterior-commit claim.

A fresh authored process executed **80 cases and 18 strict controls, all passing** at `2026-10-21T16:28:30.168833+00:00`. Groups comprise 15 packet numeric cases, 42 typed operator/spine/adapter cases, and 23 role/gate/capability cases. Every target control asserts its result without exemptions. The process checked all **885 staged source files** against candidate Git blobs and SHA-256 before and after execution, including the full **176-file production MESIA Python tree**. Real imports loaded 202 candidate module entries representing 179 unique source files; all hashes match the candidate. There were no source edits, package stubs, repository test/audit executions, or reused prior output assertions. The runnable script adapts prior authored probe code, but imports only the current staged source and freshly produces its own results.

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
PYTHONDONTWRITEBYTECODE=1 python review-e0e5b1e-f01/protocol/qualification_probes.py > review-e0e5b1e-f01/protocol/run-stdout.json 2> review-e0e5b1e-f01/protocol/run-stderr.txt
PYTHONDONTWRITEBYTECODE=1 python review-e0e5b1e-f01/protocol/build_report.py
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

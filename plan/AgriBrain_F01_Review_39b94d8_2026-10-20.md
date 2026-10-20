# AgriBrain F01 review-branch verification — 39b94d8

Review date: 20 October 2026. Repository: webClone/AgriWise. Review branch: review/f01-r415-residuals. Candidate: `39b94d8de2911cdbaa9e86d24a46f40464cba101`. Parent and main at initial collection: `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`.

## Decision

**Five of the seven R415 groups close within the named software boundaries. Two remain partial. Hold merge for three precise follow-ups; do not restart the whole F01 repair effort.**

The branch repairs the missing import, source-aware DRONE promotion, RECONSTRUCTION handling, canonical weather restriction loss, native quality coercion, soil-string admission and RF covariance defaulting. It also repairs the named water component/quality cases and most training gates. Those fixes receive explicit credit.

The remaining work is narrower: one introduced legacy water-exclusion regression, one preexisting invalid-resolution fallback, and one fractional legacy-target read/write mismatch. These are three consolidated follow-ups, not counts of every scalar or repeated fixture. Their actual source/consumer reproductions are below.

All 52 package-FA rows remain open, zero checked. This review changes no repository register or code. Five production targets relevant to R51901/R51902 remain identical to the parent; previous reviewed software closures are retained. Source continuity and the user's reported regression totals are not a new independent whole-suite guarantee.

## Scope and method

Six reviewers completed the same bounded lanes: components, native producers, water, weather/crop, training and internal RF. Root replays their authored commands in a separate exact-source layout and checks selected corrections and counterexamples. This is a source-based review against the normative F01 card and supplied R3, not adoption of repository test/audit claims.

The commit contains20 changed paths:17 production modules, one repository test and two review documents. Only the17 production changes were compiled/inspected as implementation. Tests and historical/generated reports were excluded as correctness proof. Every staged candidate and parent file matches its pinned Git blob:876 production/configuration files per corpus. Imported-source manifests distinguish executed modules from the larger staged corpus; these counts are not branch coverage.

Earlier authored probe code was restored from the saved evidence bundle and adapted; its earlier results were not used as correctness evidence. Current/private writer and queue outputs are generated fresh. The source snapshots are independent of the user's working tree. No source/Git mutation, merge, live service/provider/controller/radio/drone action, physical calibration or optimizer/model fitting occurred.

Full native WaterIntelligenceEngine execution is covered. Other lanes execute actual production adapters, validators, ledgers, feature builders, validation writers/candidates, training views and the RF dispatcher. Exact unchanged AST isolation is disclosed for the Layer1 admission method and two pure water-history helpers. Full fusion orchestration, durable canonical L3 history, upstream ASMAE EnKF and a committed RF posterior are not implied.

The replay uses eight top-level commands across six lanes. The training command also runs an exact-parent writer subprocess to regenerate immutable legacy inputs, and the water lane runs its explicit exact-parent compatibility command. A zero process exit means documented observations reproduced; some authored checks intentionally record remaining contract failures. It is not an all-clear production-suite count.

## R415 disposition

| Group | Bounded disposition | Fresh evidence |
| --- | --- | --- |
| R415-01, undefined finite_real | **Closed** | Actual exporter→ASMAEAdapter returns training-weight evidence.30 for valid0/.5. Exact parent reproduces NameError. |
| R415-02, role/canonical-weather promotion | **Closed** | DRONE restrictions survive source-aware admission; RECONSTRUCTION remains diagnostic; unavailable/conflicting-alias weather loses thermal input before crop features. |
| R415-03, water component roles/quality | **Partial** | All named component/global quality and role cases pass; new standalone legacy-exclusion regression remains, R39-01. |
| R415-04, native quality fabrication | **Closed at producer/admission seam** | Invalid perception quality becomes0; zero stays0; finite.4 survives. Invalid/zero sensor QA is diagnostic and denies update. |
| R415-05, quantitative soil strings | **Closed** | Actual natural SOILGRIDS route quarantines both string forms/bool/Inf while zero, finite and independent sand survive. |
| R415-06, training decisions/replay | **Partial** | Missing import, named nonfinite gates, comparator and confidence-range controls improve; invalid selected0/False resolution and fractional legacy read parity remain, R39-02/03. |
| R415-07, RF covariance | **Closed in contained internal scope** | Explicit invalid covariance produces varianceNone/ABSENT/noevent/noqueue; missing covariance retains its separate documented.25 default. |

Closed means the identified reproduction and its controls close at the stated boundary. It does not accept the whole F01 package or every R3 capability.

## Corrections and retained controls

### Components, roles and weather

Registered Sentinel2→package-aware normalization→validation→ledger→feature calls now preserve RECONSTRUCTION and block state/scientific/prescription/current1m permissions. Default high confidence is conservatively quarantined against the.50 ceiling. Two valid-confidence controls enter the ledger only as diagnostic ndvi_evidence. The conclusion is not based solely on quarantine hiding a role failure.

On the natural SOILGRIDS/environment route, soil_clay_pct string values are rejected before a nondiagnostic soil feature is selected. Finite0 and30 remain, missing clay emits no clay component, and sand40 survives independently. Known NDVI malformed-component and strong typed zero controls also pass.

The actual DRONE producer→wrapper→registered perception adapter→source-aware admission chain keeps simulated/estimated/fallback/unavailable restrictive. Their accepted confidences are.20/.75/.35/0, diagnostictrue and state-updatefalse. This directly covers the later normalizer that previously undid the immediate adapter.

For canonical weather, the same unavailable dict and alias conflicts now remain unavailable in evidence_records. Actual tokens and the six-scene engineered input omit all five GDD features and match the missing-weather tensor; observed weather retains its distinct thermal input. All six optical tokens remain, so independent optical support is preserved. The example still fails later model-execution/publication gates; no classifier result is claimed. Qualified synthetic/forecast forcing remains allowed under its declared role.

### Native reliability

The supported perception producer maps invalid Inf/NaN/True quality to0, keeps explicit0 and preserves finite.4. Evidence confidence follows0/.4. Its observed zero-confidence item still carries QA-scene reliability1 and state_update_allowedtrue: this review closes the demonstrated fabricated producer/confidence value, not a demonstrated posterior influence claim. No downstream zero-weight assimilation guarantee is inferred from that ledger item alone.

Native sensor QA True/Inf/NaN/malformed values become reliability/confidence0, diagnostictrue, updatefalse; zero also stays non-updating. Finite.4 and explicit update denial preserve their intended behavior. Final EvidenceItem confidence/reliability checks reject boolean/nonfinite positive metadata independently of producer normalization.

### Water named cases

The new Optional quality defaults no longer shadow reading0. Component SIMULATED admits a legitimate model update but receives ASSIMILATED, not OBSERVED. Global exclusion/zero cannot be overridden by positive component metadata. A satellite-scoped exclusion preserves independent valid TDR rows. Reading0, NaN quality, component0 and the bounded history round trips contribute zero analysis where required.

Finite observed probes, finite-zero moisture, valid satellite/thermal constraints, invalid-value/uncertainty rejection and forecastASSIMILATED controls remain. Physical projection of zero moisture and a thermal differential threshold are not missingness defects. Rows count OI components, not independent sensors. History proof uses two exact helpers, not a full durable restart workflow.

### Training and RF

Actual weak-label consumption works again; malformed targets retain zero exporter weight. The current writer rejects named malformed continuous targets/confidence, preserves four continuous zero targets and legitimate categories, and blocks nonfinite/bool/out-of-range uncertainty/retro, NaN resolution and nonfinite model comparisons. Finite contradiction, confidence0, synthetic-source, visual-only,1m and weak-label-as-truth exclusions remain.

RF explicit invalid covariance forms now stop at ABSENT and never call the actual queue. CovarianceNone follows the distinct.25 model-default branch, with likelihood/native lineage; it is not claimed to be a measured covariance. Good finite/zero signal controls survive. Calibration/epoch false and absent capability still contain use. Internal qualified fixtures are not physically earned calibration. Queue records are QUEUED/ABSTAINED, zero COMMITTED; no EnKF, training or field action occurred.

## Three follow-ups

### R39-01 — P1, introduced: standalone legacy EXCLUDED is lost beside TDR identity

Supply the actual carrier with profile.35 at three layers, valid sigma.015 and:

`provenance_sources=["IN_SITU_PROBE_TDR","EXCLUDED"]`

| Exact native execution | Accepted OI rows | Rejections | Direct / full analysis increment | Full authority |
| --- | ---: | ---: | ---: | --- |
| Parent4157ac1 | 0 | 3explicit exclusions | 0 /0mm | MODELLED |
| Candidate39b94d8 | 3 | 0 | +82.05 /+89.70mm | ASSIMILATED |

Both source-list orders reproduce the difference. Standalone EXCLUDED alone, explicitly typed global EXCLUDED and EXCLUDED_IN_SITU_PROBE_TDR still reject; valid TDR plus satellite-specific exclusion remains a working scoped-isolation control.

The new filter at [layer3_water/assimilation/water_state_assimilator.py:L183-L199](https://github.com/webClone/AgriWise/blob/39b94d8de2911cdbaa9e86d24a46f40464cba101/services/agribrain/layer3_water/assimilation/water_state_assimilator.py#L183-L199) retains recognized probe identities first. Once TDR is found, the standalone restriction no longer participates in role resolution. The runner still notices the marker and downgrades authority, but that does not undo the accepted rows or numerical update. This is excluded influence, not a renewed OBSERVED promotion.

**Repair:** preserve recognized vector-wide legacy restrictions alongside component identity, or explicitly migrate/quarantine that convention before admission. Keep satellite-specific restrictions scoped. Repeat both orderings and the paired explicit-global/qualified-source/valid-satellite controls. Do not remove the working monotone role/quality repair.

### R39-02 — P1, remaining: explicit selected resolution0/False becomes a valid fallback

The real run writer→validation→candidate→replay→training-view path still approves a candidate and emits a sample when diagnostics.resolution_selected_m is0.0 orFalse and the run's fallback resolution_m is10. The same behavior exists on the exact parent. Current NaN/Inf/True/negative resolution controls reject, so this is a narrow falsey-value hole in the repair.

At [asmae_learn/candidate_builder.py:L77-L89](https://github.com/webClone/AgriWise/blob/39b94d8de2911cdbaa9e86d24a46f40464cba101/services/agribrain/asmae_learn/candidate_builder.py#L77-L89), boolean `or` chooses the fallback before finite_real or the positive-resolution test sees the supplied invalid value. The dataset reader repeats the same selection pattern at [asmae_learn/dataset_builder.py:L108-L114](https://github.com/webClone/AgriWise/blob/39b94d8de2911cdbaa9e86d24a46f40464cba101/services/agribrain/asmae_learn/dataset_builder.py#L108-L114).

**Repair:** distinguish absent metadata from an explicit invalid value. Apply finite/nonboolean/>0 validation to the selected field when present; only an actually absent value may use a qualified fallback. Use the same rule in candidate creation and replay. Keep legitimate zero *targets* valid; resolution0 is a different physical-domain contract. Verify no approved sample for0/False while valid10 and the stated absence policy behave consistently.

### R39-03 — P2, legacy-read parity: fractional biotic strings still enter current training views

This is stronger than a handcrafted legacy approval fixture. The harness freshly executes the exact parent's real validation writer/candidate pipeline. It produces approved ledgers for target biotic_confounder, unitfraction, with observed_value"0.5" or"not-a-number". The current reader consumes those producer-generated ledgers unchanged, verifies their bytes are unchanged, and emits the string target as a sample. The current ValidationEvent rejects the very same event. The parent's NaN approved ledger is correctly excluded by the current reader.

The writer recognizes a numeric form using the declared unit at [asmae_learn/schemas.py:L89-L108](https://github.com/webClone/AgriWise/blob/39b94d8de2911cdbaa9e86d24a46f40464cba101/services/agribrain/asmae_learn/schemas.py#L89-L108). The reader uses the Python value type at [asmae_learn/dataset_builder.py:L167-L183](https://github.com/webClone/AgriWise/blob/39b94d8de2911cdbaa9e86d24a46f40464cba101/services/agribrain/asmae_learn/dataset_builder.py#L167-L183). A string therefore escapes the numeric branch and is treated as categorical even though the event declares a fractional quantity.

**Repair:** use a shared target/form/unit qualifier at write and replay. Fractional legacy values must satisfy the same numeric contract or be explicitly normalized/quarantined under a recorded migration policy. Retain legitimate qualitative biotic categories in their own form. No new unit-conversion requirement is imposed.

Boolean legacy parity is recorded separately using an event-only modified valid seed; it is not used to claim a current-writer bypass. The primary string cases use unmodified real parent-produced approvals. No optimizer or trained-model outcome was executed.

## Plan, R3 and readiness

F01's master card is lines151–177 in AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md. Its criteria require invalid values not to acquire influence/training weight, legitimate zero preservation, roles through typed/dictionary adapters, explicit admitted components and parity across weather/RF/crop/training including ambiguous legacy records.

| R3 requirement | Verified progress | Remaining concern |
| --- | --- | --- |
| AB-DAT-005 zero/missingness | Measurement/target zero and corrected quality0 controls survive | Explicit invalid resolution erased by default; fractional malformed legacy targets |
| AB-DAT-006 field provenance | RECONSTRUCTION and source-aware/canonical role restrictions improve | Legacy vector-wide exclusion lost |
| AB-ARC-005 factorized authority | Diagnostic roles, truthful ASSIMILATED controls and RF containment survive | Excluded water still influences modeled state; invalid training-view eligibility |
| AB-ARC-006 bounded degradation | Named invalid/default guards largely work | R39-01–03 permit promotion or influence through filtering/fallback/read classification |

The three selected normative plans match candidate Git blobs; all 52FA rows are open. The supplied R3 PDF SHA256 remains `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; its extracted scientific requirements are at675–681 and738–744. Neither an old report nor checkbox status proves implementation.

**Next implementation order:** fix R39-01's legacy exclusion filter; replace falsey resolution fallback with explicit absence handling in both writers/readers; share fractional target qualification across writer/replay. These are bounded follow-ups. Then rerun the same six-lane matrix and retain its controls. No new whole-repository review or blanket hardware prerequisite is being imposed.

Do not describe this branch as all-seven closed or merge-ready yet. Five groups close at their named boundaries; R415-03 andR415-06 remain partial for the precise reasons above. Independent tasks and qualified research may continue. F01 full acceptance still requires its actual end-to-end producer/consumer criteria; this bounded review does not silently close that milestone or any other package.

## Deliverables and replay

The claim-disposition JSON records each R415 closure, the three follow-ups, scope and retained controls. The evidence bundle includes authored probes, fresh results, exact-source/plan identities, parent comparisons and a read-only Git-object materializer. It excludes production-source copies, repository tests/audits, private radio bytes, queue stores and training ledgers; these are regenerated privately on replay.

Root's common-layout receipt and selected observation checks document what was reproduced. Parent sources and freshly generated parent ledgers are verification controls, not adopted historic results. The materializer is syntax/layout checked here rather than executed against a second full Git checkout.



---

# Specialist appendix: Registered quantitative fields and reconstruction

# Bounded F01 component and role closure verification

Candidate: `39b94d8de2911cdbaa9e86d24a46f40464cba101`  
Parent: `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`

**R415-02 and R415-05 close in the named production-consumer routes.** The rerun completed 111 fixture rows in seven groups, using 49 imported repository files whose complete bytes match the candidate Git-tree blobs. This is bounded evidence-admission and fused-feature verification, not a statement that F01 or its other consumers are complete.

## Normative basis and method

The governing requirements are master F01 at `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:151–177`, with supplied `current-plan-review/R3_current_scientific_sections.txt` AB-DAT-005/006 and AB-ARC-005/006. They require preservation of valid zero and missingness, distinct source roles without caller promotion, explicit admitted components, and separate permissions. The canonical master was read directly; root preserves and verifies the normative plans.

`probes.py` adapts only the prior authored probe code as a starting point. It does not read prior results, reports, repository tests, historical audits or generated correctness artifacts. All observations reported here are fresh executions against this candidate. Candidate and parent identities are asserted from the fetched metadata and Git tree. `executed-file-manifest.json` lists every imported repository file, module name, Git blob SHA, SHA-256 and byte length; all are verified before results are written. No AST-isolated functions, replacement consumers or repository stubs are used.

The executed route is dictionary or typed `ObservationPacket` → `ensure_observation_packet` → canonical `Layer0SourcePackage` → an actual `Sentinel2Adapter` or `EnvironmentAdapter` registered and retrieved through `SourceRegistry` → packet bridge → `normalize_evidence_truth(item, source_context=pkg)` → `validate_evidence` and quarantine → `EvidenceLedger.add` → `fuse_features`. This is the pertinent adapter/normalization/validation/ledger ordering in `engine.py`, exercised directly without calling the full engine. Inputs are inert, in-memory fixtures with eligible fixed timestamps, identities, provenance and a valid sibling component where specified. Socket connection entry points fail closed. No service, provider, runtime network, physical hardware or production mutation is used.

## R415-02 — RECONSTRUCTION

The original direct declaration and `role=OBSERVATION` / `source_role=RECONSTRUCTION` conflict are rerun as typed and dictionary packets through the registered Sentinel-2 route. The same bounded named role check also covers reversed role/source-role declarations and the declared `data_role`, `status_role` and `truth_class` aliases. All 12 default-QA cases preserve `packet_status=reconstruction`, truth status `reconstruction`, component `truth_class=reconstruction_proxy`, `diagnostic_only=True` and `state_update_allowed=False` after source-context normalization. Scientific surface, prescription-driver and current-1m approval permissions are all false. None becomes an observed, state-eligible component.

There is a conservative admission detail: default confidence remains 1.0, above the reconstruction ceiling 0.50, so these 12 cases are quarantined with `RECONSTRUCTION_CONFIDENCE_EXCEEDS_CEILING:1.0`. They have ledger count zero and no vegetation feature. This is not mislabeled as diagnostic feature retention.

Two explicit valid-QA controls use scene score and reliability weight 0.5, producing confidence 0.25. Both typed and dictionary reconstruction packets pass validation, enter the ledger once, remain excluded from `state_updatable()`, and produce exactly `ndvi_evidence=0.0` with `diagnostic_only=True`. No ordinary `ndvi` state feature is produced. Thus the closure is not dependent solely on the default-confidence quarantine. The ordinary OBSERVATION and other canonical-role/alias controls also pass.

## R415-05 — quantitative soil strings

Fourteen rows use the natural `ObservationSource.SOILGRIDS` → registered environment adapter route, with known quantitative `soil_clay_pct` and a valid `soil_sand_pct=40.0` sibling in every fixture. Each value is exercised as typed and dictionary input.

| Clay input | Clay validation/admission | Soil-site fused output |
|---|---|---|
| `0.0`, `30.0` | Admitted; ledger count 2 | Numeric clay plus sand; both non-diagnostic |
| `True` | `BOOLEAN_VALUE_DISALLOWED`; quarantined | Sand only; ledger count 1 |
| positive infinity | `NON_FINITE_OR_MALFORMED_VALUE`; quarantined | Sand only; ledger count 1 |
| numeric string `"30.0"` | `NON_FINITE_OR_MALFORMED_VALUE`; quarantined | Sand only; ledger count 1 |
| malformed string `"not-a-value"` | `NON_FINITE_OR_MALFORMED_VALUE`; quarantined | Sand only; ledger count 1 |
| missing `None` | No clay component emitted | Sand only; ledger count 1 |

The packet remains observed in the invalid-clay/sound-sand cases; actual component admission is what excludes clay. The original two string counterexamples no longer become non-diagnostic fused soil features. The valid sibling survives each rejection. Candidate `evidence_validation.py` explicitly includes known quantitative soil variables and canonical quantitative units in strict finite-real qualification.

## Controls, actual permissions and limits

G01/G02 retain the existing numeric behavior: finite NDVI and zero are admitted; infinity, negative infinity, NaN, booleans, numeric/malformed strings and missing NDVI are excluded while valid EVI survives; the out-of-bounds NDVI control is rejected. Invalid-only and all-missing rows have no admitted components. A record-level ledger control admits the mixed valid/invalid record once and rejects the wholly invalid record. G07 preserves strong typed observation zero through JSON round-trip and rejects invalid numeric values and non-positive/invalid variances. These controls do not substitute for the named registered-route results above.

Actual reconstruction permissions allow visualization, experimental visualization and composite advisory; they forbid state update, scientific surface, prescription driver and current-1m approval. Actual valid soil evidence after context normalization is `geo_provider_context`, allows visualization and state eligibility, and is non-diagnostic; experimental visualization, composite advisory, scientific surface, prescription driver and current-1m approval are false. These flags are recorded directly in the strict results. The tested EvidenceItem/EvidenceTruth fields do not encode training or execution permissions, and neither consumer was invoked.

State eligibility and non-diagnostic feature selection are observed here. No posterior, Kalman update, physical-state alteration, solver/training weight, prescription or execution consequence is claimed. The full engine's temporal/spatial alignment and downstream publication path are outside this lane. The fixed timestamps avoid making an F02 availability conclusion. No additional adjacent declared-channel exploration was needed after the named closures and controls passed; arbitrary aliases, unrelated variables and all remaining F01 boundaries are not certified by this report.

Reproduce from the review snapshot with:

```bash
python /workspace/scratch/de6bc2428cec/review-39b94d8-f01/ledger/probes.py
```

Deliverables are `probes.py`, `results.json`, and `executed-file-manifest.json` beside this report. Results use strict JSON; non-finite test inputs are represented with explicit textual markers rather than invalid JSON numeric tokens.


---

# Specialist appendix: Native producers and source-aware role preservation

# R415-02 DRONE role promotion and R415-04 native quality — 39b94d8

Candidate `39b94d8de2911cdbaa9e86d24a46f40464cba101`; exact parent identity `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`. This lane reads the supplied candidate source and writes only reviewer-authored files in `platform/`.

## Named closure

| Finding slice | Closed at the named boundary? | Fresh candidate result |
| --- | --- | --- |
| R415-02, source-aware DRONE promotion | **Yes** | All four original nonobserved statuses remain restrictive after package-aware normalization, validation and actual ledger insertion. |
| R415-04, native perception reliability | **Yes** | Inf, NaN and True become packet weight 0 and admitted evidence confidence 0. Explicit 0 remains 0; finite 0.4 remains 0.4. |
| R415-04, native sensor QA boolean | **Yes** | True becomes finite numeric reliability/confidence 0, diagnostic true and state-update false. |

These are bounded software closures. R415-02 also names weather and reconstruction paths owned by other lanes; this report does not decide that entire consolidated group or all of F01. Counts below are **EvidenceLedger items**, not physical state updates, assimilation rows or training samples.

## Actual supported producer and consumer

`PerceptionEngineOutput(engine_family=DRONE, vegetation_fraction=0.2)` → `to_observation_packets(..., data_status=...)` → default `wrap_perception` → `SourceRegistry.register(PerceptionAdapter())` and `get_adapter('perception')` → canonical `Layer0SourcePackageAdapter` / `observation_packet_to_evidence` → package-aware normalization/admission → actual `EvidenceLedger`.

The typed packet retains source DRONE despite the wrapper's default source. Its mapped evidence family is `drone_structural`. The source-envelope validator returns no violations for all five status cases; unavailable has a missing envelope and unavailable package, while `can_read` remains true. This is the same default wrapper call used by `layer0/runner.py:170–179`, followed by the registered perception consumer. The normal fusion path's source-aware normalization is statically traced at `layer1_fusion/engine.py:156–159`, with validation/ledger insertion at 163–183.

The full engine is not initialized or run. The probe executes the exact unmodified AST definition of `Layer1FusionEngine._admit_evidence_or_quarantine`, using its real relative imports and passing the actual package as `source_context`. The method normalizes truth, validates evidence, quarantines violations, and adds accepted items to the actual ledger. This isolates unrelated initialization; it does not substitute reviewer normalization logic. Method extent and source SHA-256 are recorded in `results.json.admission_isolation`.

## R415-02 results

Each case accepts one ledger item with zero quarantine; the admitted fields are:

| Input / admitted status | Confidence | Diagnostic | State update | Real provider product | Scientific surface / prescription / current 1m |
| --- | ---: | --- | --- | --- | --- |
| observed | 1.00 | false | true | true | false / false / false |
| simulated | 0.20 | true | false | false | false / false / false |
| estimated | 0.75 | true | false | false | false / false / false |
| fallback | 0.35 | true | false | false | false / false / false |
| unavailable | 0.00 | true | false | false | false / false / false |

The four original restricted cases no longer become observed, nondiagnostic, updating evidence. Their confidence ceilings also survive. Unavailable remains production-usable false; its item is retained diagnostically. Results record both the immediate adapter item and final accepted item, so the claim covers the later package-aware consumer rather than just the wrapper.

Candidate source `layer1_fusion/truth_bridge.py:399–422` preserves the restricted DRONE statuses and permissions, and intersects the existing diagnostic/state permissions on the observed branch.

## R415-04 results

The perception producer uses the real shared contracts and existing mapped variable with QA score 1 / variable confidence 1:

| Native output reliability input | Produced packet weight | Accepted evidence confidence | Accepted count |
| --- | ---: | ---: | ---: |
| Inf | 0 | 0 | 1 |
| NaN | 0 | 0 | 1 |
| True | 0 | 0 | 1 |
| 0 | 0 | 0 | 1 |
| 0.4 | 0.4 | 0.4 | 1 |

This verifies removal of the earlier fabricated 1 / 0.05 weights. The observed perception item still carries QA-scene reliability 1 and `state_update_allowed=true` even when confidence is 0. The tested correction is the producer/evidence confidence value; this report makes no claim about posterior or training influence. A bounded neighbor at the same `min(weight, confidence)` operation also verifies variable confidence True → 0, 0 → 0 and 0.4 → 0.4. Source `layer0/perception/common/packet_adapter.py:165–173` qualifies native values before clamping.

The separate native sensor route instantiates actual `NormalizedSensorReading`, `SensorQAResult` and `SensorContextPackage`, then uses a registered `SensorAdapter` and package-aware admission. All rows below accept one diagnostic/observational ledger item with no quarantine:

| Sensor reading_reliability input | Admitted confidence / reliability | Diagnostic | State update |
| --- | --- | --- | --- |
| True, Inf, NaN, malformed `bad` | 0 / 0 | true | false |
| 0 | 0 / 0 | true | false |
| 0.4 | 0.4 / 0.4 | false | true |
| 0.4 with update_allowed false | 0.4 / 0.4 | true | false |

The invalid values are sanitized into diagnostic zero quality rather than admitted as boolean/nonfinite positive quality. Sensor source `layer1_fusion/adapters/sensors.py:73–80` applies `finite_real` and denies updates when quality is invalid or nonpositive.

A separate final-defense control changes only confidence or reliability on a genuine immediate adapter result. True and NaN are each quarantined (zero accepted) for both fields; zero and finite 0.4 survive. These are final-admission robustness controls, explicitly separate from the native producer path. They exercise the new strict finite/nonboolean checks in `layer1_fusion/evidence_validation.py:61–67`.

## Retained immediate controls

- All 40 typed/dictionary role-alias cases preserve SIMULATED, FORECAST→estimated, PROXY→fallback and UNAVAILABLE restrictions; immediate evidence has state-update false. Four conflicting / existing-status cases remain restrictive.
- Dictionary explicit Inf, NaN, boolean, malformed, null, negative and above-one reliability becomes zero. Absent weight remains 1; explicit zero remains zero. An invalid/zero primary does not acquire a positive fallback weight.
- Typed `ObservationPacket` weight and QA scene score Inf/NaN/True/malformed become zero effective weight.
- Numeric NDVI zero survives dataclass JSON round trip and admission. Inf/NaN/False/True/malformed NDVI values quarantine.

## Normative and identity evidence

The normative inputs are exactly the three selected plans in `sr-team-review/plan/`: the master deep repair plan, task list and execution sequencing addendum, plus the supplied `current-plan-review/R3_current_scientific_sections.txt`. Each selected plan's Git blob matches the candidate tree. Master F01 lines 151–177 requires typed/dictionary role transport and finite/nonboolean numeric admission while preserving valid zero. This lane maps to AB-DAT-005 (valid zero/missingness), AB-DAT-006 (field provenance), AB-ARC-005 (factorized permissions) and AB-ARC-006 (bounded degradation). R3 requirement locations and the extract SHA-256 are in `plan-results.json`.

F01 has five unchecked task/FA rows; the full register has 52 unchecked FA rows. These are tracked register status, not proof implementation is absent.

`verify_metadata.py` freshly verifies all **876/876** supplied production/config files against candidate Git blobs, SHA-256 and byte count; all **56** actually imported source files are in that exact manifest. `import-manifest.json` lists module names and paths, imported-file identities and the two static source references. Candidate/parent identities and an untruncated candidate tree are checked. No production source was edited. Repository tests, historical audit conclusions, generated repository artifacts and old run outputs are excluded as correctness proof; only reusable reviewer code was adapted and re-executed.

## Reproduce

From the review directory with its sibling source and the reference layout:

```sh
PYTHONDONTWRITEBYTECODE=1 python platform/wrapper_probes.py
PYTHONDONTWRITEBYTECODE=1 python platform/verify_metadata.py
```

All **21 checks pass**. `results.json` is strict JSON (`allow_nan=False`); nonfinite input receipts use explicit `nonfinite_repr` objects. Fresh outputs: `results.json`, `source-manifest.json`, `import-manifest.json`, `plan-results.json`. No network, provider, service, controller, radio, drone, hardware, full fusion, optimizer, model fitting or durable state mutation was run.


---

# Specialist appendix: Water component qualification and legacy compatibility

# R415-03 — water component qualification and authority

Candidate: `39b94d8de2911cdbaa9e86d24a46f40464cba101`. Parent: `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`. Verification date: 2026-10-20.

The named R415-03 repairs work in the executed native OI and full `WaterIntelligenceEngine` paths. Component SIMULATED no longer confers OBSERVED authority; explicit zero/invalid quality blocks influence; global exclusion/zero survives a positive component declaration; and satellite-specific exclusion preserves an independently valid TDR profile. One legacy provenance compatibility regression remains: a standalone `EXCLUDED` source marker is discarded when a recognized TDR identity is also present. This newly restores observational influence to data rejected by the exact parent.

The candidate run executed 41 input variants and 45 checks: 43 passed and two failed checks describe that single residual. There were no execution errors. The narrowly scoped exact-parent comparison executed four variants and four passing checks. These are bounded software observations, not a complete F01 or durable L3 acceptance claim.

## Contract and execution basis

The normative basis is F01 in `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`, lines 151–178, plus `current-plan-review/R3_current_scientific_sections.txt`: AB-DAT-005 preserves valid zero, AB-DAT-006 distinguishes provenance per field, AB-ARC-005 separates authority by capability, and AB-ARC-006 forbids promotion through fallback. F01 requires accepted/rejected components before authority selection, role preservation through typed/dictionary adapters, and admitted counts/authority that follow actual components. Synthetic/forecast research or model updates are allowed here with ASSIMILATED authority; their nonzero increments alone are not failures.

`probes.py` imports the exact candidate `SoilObservationVector`, `WaterStateFactory`, `WaterStateAssimilator`, and full `WaterIntelligenceEngine`. A verification finder checks each production Python source against its Git blob before import. The candidate run covers 64 production files; the parent comparison covers 63. Source files were not edited. The source manifests identify all executed/imported files with blob IDs, SHA-256, and byte counts.

A read-only Python trace records successful native `add_observation` returns, including layer, value, uncertainty, source, resolved role, and resolved quality. It does not substitute an assimilator or mutate production state. Each direct and full-pipeline diagnostic count/source list agrees with the captured admitted rows. Every case confirms that the supplied prior remains unchanged. Every zero-row case also asserts zero direct and full-pipeline analysis increment. Full-pipeline analysis increments are taken from `analysis_receipt`, separate from the physical balance transition.

The exact `_serialize_soil_observation` and `_deserialize_soil_observation` AST definitions from `layer3_decision/runner.py` are executed unchanged with the native carrier, OI, and full water runner. Full decision-module initialization, durable persistence, canonical restart/recovery, wrappers/providers, production services, external network operations, and hardware were not executed. Repository tests, audits, artifacts, and old probe outputs are not correctness evidence; prior probe code was adapted and rerun.

## Named repair results

All storage increments below are mm. `direct / full` means standalone native OI increment / full runner analysis receipt increment. A profile test uses three layers at depths 10, 30, and 60 cm, prior theta 0.20, candidate readings 0.35, and probe sigma 0.015 unless stated otherwise.

| Named case | Actual admitted rows / sources | Direct / full increment | Full authority | Disposition |
|---|---|---:|---|---|
| `component_simulated_probe` | 3 TDR rows, resolved role SIMULATED | +82.05 / +89.70 | ASSIMILATED | Closed: no OBSERVED promotion; model update allowed |
| `reading_zero_only` | 0; three zero-quality rejections | 0 / 0 | MODELLED | Closed: optional weight default no longer shadows reading zero |
| `nonfinite_weight` (NaN weight + reading 0) | 0 | 0 / 0 | MODELLED | Closed: no admitted influence |
| `global_excluded_component_observed` | 0; three excluded-role rejections | 0 / 0 | MODELLED | Closed: component OBSERVED cannot override global EXCLUDED |
| `global_zero_component_positive` | 0 | 0 / 0 | MODELLED | Closed: component quality 1 cannot override global weight 0 |
| `satellite_exclusion_source_with_observed_probe` | 3 TDR rows; satellite contributes no row | +82.05 / +89.70 | OBSERVED | Closed: source-scoped satellite exclusion preserves TDR |
| `satellite_exclusion_metadata_with_observed_probe` | 3 TDR rows; satellite contributes no row | +82.05 / +89.70 | OBSERVED | Typed metadata anchor preserved |

The Optional quality defaults are both exactly `None`. `_resolve_quality` considers all specified global/component values; `_resolve_role` applies exclusion before simulated restrictions. The actual component-SIMULATED rows in both native paths carry SIMULATED. Positive component/global declarations do not bypass the named restrictions.

Retained controls pass:

| Control | Rows | Direct / full increment | Full authority |
|---|---:|---:|---|
| Finite observed probe `[0.30,0.31,0.32]` | 3 | +61.73 / +68.98 | OBSERVED |
| Finite zero probe `[0,0,0]` | 3 | −95.94 / −90.24 | OBSERVED |
| NaN/Infinity/bool profile | 0 | 0 / 0 | MODELLED |
| Forecast-tagged probe | 3 | +82.05 / +89.70 | ASSIMILATED |
| Excluded satellite | 0 | 0 / 0 | MODELLED |
| Valid satellite fallback | 1 satellite | +21.19 / +33.43 | ASSIMILATED |
| Valid thermal fallback | 1 thermal | −2.71 / −3.07 | ASSIMILATED |
| Original SIMULATED/both-zero dictionary through exact history helpers | 0 | 0 / 0 | MODELLED |

Zero moisture is present and admitted; the physical posterior projection is separate. Thermal zero is retained as input and produces no constraint under the current `dt > 2` algorithm. Invalid/zero uncertainties reject. An invalid probe can fall back to a valid satellite, while rejected probes do not prevent an independent qualified satellite constraint. Replayed component SIMULATED remains ASSIMILATED and replayed reading zero remains zero-influence.

## Single residual: standalone legacy exclusion is lost when TDR identity is present

Input:

```python
SoilObservationVector(
    timestamp=T,
    soil_probe_moisture_profile=[0.35, 0.35, 0.35],
    observation_uncertainties={"soil_probe": 0.015, "satellite_smap": 0.04},
    provenance_sources=["IN_SITU_PROBE_TDR", "EXCLUDED"],
)
```

| Exact production execution | Admitted rows / sources | Rejections | Direct / full increment | Full authority |
|---|---|---:|---:|---|
| Parent 4157ac1 | 0 / none | 3 `explicitly_excluded_role` | 0 / 0 | MODELLED |
| Candidate 39b94d8 | 3 / `IN_SITU_PROBE_TDR` | 0 | +82.05 / +89.70 | ASSIMILATED |

The candidate's three admitted rows have layer indices `[0,1,2]`, values `[0.35,0.35,0.35]`, sigma 0.015, resolved role OBSERVED, and resolved reliability 1.0. The full runner admits the same three rows. Reversing the two source entries produces the same candidate failure and the same parent rejection. `sources=["EXCLUDED"]` alone still rejects on both versions, as does `sources=["EXCLUDED_IN_SITU_PROBE_TDR"]`. Explicit typed global EXCLUDED also rejects, while the valid TDR plus satellite-specific EXCLUDED control remains admitted/OBSERVED on the candidate. These controls distinguish the compatibility defect from the intended satellite isolation repair.

The cause is the candidate filter in `water_state_assimilator.py`, lines 183–191. Once it finds a recognized probe source, it removes standalone `EXCLUDED` from the list consulted for restriction at lines 195–199. The exact parent checks every provenance entry for generic exclusion at its lines 144–146. The runner still notices the generic restriction in its separate source scan, so it downgrades authority to ASSIMILATED, but this does not remove the admitted rows or the +89.70 mm analysis update. This residual concerns prohibited influence, not an OBSERVED label.

Keep the working source-scoped isolation and monotone typed role/quality repairs. Preserve standalone legacy restriction markers alongside the relevant probe identity, or explicitly migrate/reject the legacy convention before admission. A migration is not demonstrated by this candidate: the native carrier still accepts the form, and adding a positive identity changes an excluded profile into an influential one. No additional residual is asserted from this bounded lane.

## Reproduction and evidence

From `/workspace/scratch/de6bc2428cec`:

```bash
python review-39b94d8-f01/decision/probes.py
python review-39b94d8-f01/decision/probes.py --parent-compatibility
```

`results.json` contains the candidate inputs, admitted rows, posterior values, deltas, rejection receipts, full analysis/transition receipts, history round trips, and all check results. `parent-compatibility-results.json` contains fresh exact-parent production-call results for the four legacy-source controls. `executed-source-manifest.json`, its parent counterpart, and `manifest.json` record source and authored-artifact identity. JSON output is strict: nonfinite inputs are stringified only for saving after native execution, and `allow_nan=False` forbids nonstandard JSON literals.


---

# Specialist appendix: Canonical weather to crop features

# R415-02 canonical weather → crop closure review

**Verdict: closed for the named daily-dictionary provenance seam at `39b94d8de2911cdbaa9e86d24a46f40464cba101` (parent `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`).** A fresh offline run executed 43 cases and 241 strict boolean checks; all passed. No blocking finding remains in this bounded lane. The original crop numeric/support and Sentinel-2 source-role guards still pass.

The formerly problematic daily dictionaries now retain `unavailable` across `wrap_environment` packet and canonical evidence transport, contribute no thermal coordinate to the canonical crop observation or ledger-derived model token, and produce missing engineered GDD features. This holds for status alone, `role=OBSERVATION` plus unavailable status, and `role=OBSERVATION` plus `source_role=EXCLUDED`. A valid 20 °C observed control still supplies GDD10=10 for one weather day.

## Basis and scope

Normative basis is the master F01 section in `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`, lines 151–177: preserve zero and missingness, qualify components before authority, carry roles through dictionary/typed adapters without promotion, and apply qualification to weather and crop consumers. The corresponding R3 requirements are `current-plan-review/R3_current_scientific_sections.txt` lines 675–681 (AB-DAT-005 zero/missingness and AB-DAT-006 field provenance) and 738–744 (AB-ARC-005 factored authority and AB-ARC-006 bounded degradation without fallback promotion).

The executable path is the actual production `wrap_environment` → returned `evidence_records` → `build_canonical_crop_observations` → `build_crop_evidence_ledger` → `observation_tokens_from_ledger` → `build_ledger_crop_feature_input`. Inputs are in-memory authored daily weather dictionaries and complete local 4×4 Sentinel-2 arrays. The six-scene engineered control uses six physical acquisitions, with sensing/processing dates 2026-10-01 through 2026-10-19, before the 2026-10-20 review date. No future/cutoff experiment is involved.

The full orchestrator and classifier were not executed. The report makes no full F01, classifier, training, prescription, publication, provider, persistence, or service acceptance claim. No repository test, audit, generated artifact, or prior probe result is used as proof. The previous authored probe implementation was reused only as harness material; all reported outcomes were regenerated against this candidate source. Only files under this review's `ownership/` directory were authored.

## Fresh result matrix

| Group | Cases | Passing checks | Observation |
|---|---:|---:|---|
| Crop dtype and support | 10 | 33/33 | Real finite bands, bool DATAMASK, integer SCL, zero NDVI and partial support remain usable; boolean/string/object/complex reflectance and absent finite support are rejected. One infinite pixel is removed while 15 valid pixels remain. |
| Sentinel-2 scene roles | 7 | 35/35 | Observed physical scene supplies one token; excluded, synthetic, prior, forecast, fallback and conflicting role aliases supply no model token or state authority. |
| Weather numeric controls | 11 | 25/25 | Finite zero and 20 °C survive. Boolean, string, NaN, infinity and missing temperature do not produce GDD. Valid optical admission survives missing weather. Finite min/max and explicit zero GDD controls retain their intended semantics. |
| Daily weather provenance seam | 7 | 44/44 | Packet and canonical statuses agree for the named declarations; unavailable/excluded inputs cannot enter token thermal axes. All weather remains process-forcing-only with no state-update authority. |
| Six-scene engineered input | 8 | 104/104 | Four unavailable/excluded declarations produce the same thermal-missing tensor as absent weather, while retaining six optical tokens. Actual input tensor values and masks are checked. |
| **Total** | **43** | **241/241** | **No failing checks.** |

The single-scene seam declarations are observed, excluded role, unavailable status alone, unavailable status plus observation role, observation role plus excluded source role, synthetic, and forecast. The six-scene matrix repeats those seven and adds a missing-weather control.

| Six-scene weather declaration | Canonical status | Token GDD10 values | Engineered GDD features |
|---|---|---|---|
| `role=OBSERVATION`, `data_status=observed` | observed × 6 | 10, 20, 30, 40, 50, 60 | Present |
| `role=EXCLUDED`, unavailable status | unavailable × 6 | All absent | All five missing |
| Unavailable status alone | unavailable × 6 | All absent | All five missing |
| Observation role + unavailable status | unavailable × 6 | All absent | All five missing |
| Observation role + `source_role=EXCLUDED` | unavailable × 6 | All absent | All five missing |
| Synthetic role + simulated status | simulated × 6 | 10, 20, 30, 40, 50, 60 | Present as process forcing |
| Forecast role + estimated status | estimated × 6 | 10, 20, 30, 40, 50, 60 | Present as process forcing |
| No weather | Empty | All absent | All five missing |

Forecast and synthetic thermal forcing are not prohibited by this review. Their canonical statuses remain estimated/simulated, with `authority=process_forcing_only` and `state_update_allowed=false`; equality of their numerical tensor with the observed 20 °C control is not a failure criterion. This is a bounded transport/admission check, not proof of complete per-field weather lineage in every downstream artifact.

## Actual model-input effect and gates

For the six-scene observed control the engineered input contains:

| Feature | Observed weather | Each unavailable/excluded declaration and no-weather control |
|---|---:|---|
| `sos_gdd` | 20.0 | missing |
| `pos_gdd` | 40.0 | missing |
| `eos_gdd` | 50.0 | missing |
| `growth_rate_per_gdd` | 0.0147857143 | missing |
| `senescence_rate_per_gdd` | -0.0135714286 | missing |

These are exactly the five changed tensor features; all other engineered feature values remain equal. Six optical tokens, six eligible ledger items, and six true quality-mask entries are retained throughout. The strict results include the full feature order, actual input values, missingness mask, tensor hash, receipt hash, ledger outputs, token thermal coordinates, canonical weather rows, and gate reasons.

The observed input tensor hash is `13e29898129245b63cad3f4dd9a547c57ac7adc9f716cc6e37cef8bef85c5f30`; every unavailable/excluded and no-weather tensor is `7973551439d905552bee8b6a3545c55a41c8d6dab4ec692f98d49a4204b4f42f`. Their input receipt hashes are respectively `dfabade60453db5ef44debc5fd8fe4e25e34b5ca2b5fd936262a8818fcc3daa6` and `0f5e2fb2d09ba55d80a6e60e4d9c53fe15607f5104816b2cb8029164686c9931`. Thus unavailable weather no longer yields the observed-weather engineered input in these controls.

Feature completeness is 22/66 (0.3333333333) for the observed thermal control and 17/66 (0.2575757576) when thermal features are missing. `model_execution_eligible=false` and `publication_eligible=false` in all six-scene cases. The explicit blockers are `feature_tensor_incomplete`, `crop_cycle_phase_coverage_insufficient`, `model_domain_not_verified`, and `probability_calibration_not_validated`. Each nonobserved single-scene source-role case is blocked earlier because crop-cycle segmentation requires admitted physical evidence. These are observed downstream gate outcomes, not a claim that any classifier or publication pipeline ran.

## Source explanation and call-path evidence

All line references below are to the candidate export under `source/`.

- `services/agribrain/layer0/wrappers.py:28–51` reads native/dictionary consensus values and flat daily dictionary values while preserving zero. Lines 82–104 read daily dictionary shape and declarations. Lines 106–129 give unavailable/excluded declarations precedence over observation, synthetic, fallback, and estimated alternatives. Lines 137–143 emit the canonical status, forcing-only authority, no state-update authority, and temperature value. The packet status inference also gathers all declared role fields before monotone status selection at lines 174–228.
- `services/agribrain/layer2_veg_int/crop_observations.py:874–931` drops unavailable/excluded weather before finite-real arithmetic. Lines 1120–1128 attach the actual GDD coordinates to the crop record and lines 1244–1251 retain them in environmental context. Scene admission and direct state authority follow the declared Sentinel-2 status/roles at lines 1149–1197 and 1253.
- `services/agribrain/scientific_contracts/crop_model_input.py:577–607` selects admitted physical ledger representatives and reads their environmental thermal axes. `services/agribrain/layer2_veg_int/features/ledger_crop_features.py:44–74,141–187` builds feature rows and the engineered input from these ledger tokens. `crop_model_input.py:703–779` builds tensor/missingness values and computes execution/publication gates.
- Static call-path inspection only: `services/agribrain/orchestrator_v2/runner.py:915–930` prefers canonical `evidence_records` without falling through when that collection is empty; lines 98–123 forward weather to the canonical crop builder. `services/agribrain/layer2_veg_int/crop_posterior.py:720–755` invokes the same engineered ledger feature adapter. These functions/files were hash-verified; the orchestrator and posterior were not invoked by this lane.

## Reproduction and integrity

From the directory containing `review-39b94d8-f01`, run:

```bash
python review-39b94d8-f01/ownership/probes.py
```

The script writes `results.json` and `source-import-manifest.json`, rejects non-boolean check outcomes, emits strict JSON with `allow_nan=false`, and exits nonzero if a check fails. It checks the exact candidate and one-parent metadata, verifies the exported 876-file path set, and verifies every exported file against the candidate git-tree blob plus the staged SHA-256 manifest. No source file is modified and bytecode writes are disabled.

The final fresh process imported 66 candidate module identities covering 43 distinct production files; each imported source file and four static call-path files is recorded with path, git blob, SHA-256, byte count, line count and successful verification. Module aliases are retained so the manifest describes the actual runtime imports. `probes.py` itself is hashed in that manifest.

Deliverables: `report.md`, `probes.py`, `results.json`, `source-import-manifest.json`.


---

# Specialist appendix: Actual label consumption, training decisions and legacy read parity

# R415-01 / R415-06 closure verification

Candidate: `39b94d8de2911cdbaa9e86d24a46f40464cba101`. Exact parent: `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`.

R415-01 closes in the exercised declared consumer. R415-06 substantially improves admission and replay, but remains partially open for two bounded residuals: explicit selected resolution `False`/`0.0` falls back to a valid run resolution and produces approved training samples; fractional-biotic strings from an actual parent writer still reach the current dataset reader. These are continuations of the named closure scope, not a new target/unit matrix.

Mapping supplied for this lane: F01 master lines 151–177; R3 DAT-005/DAT-006 and ARC-005/ARC-006. This report makes source/consumer claims only.

## Reproduction and evidence

From the workspace containing the two staged review directories, run:

```bash
python review-39b94d8-f01/trajectory/probes.py --legacy-parent-root review-4157ac1-f01
```

This single command first executes the exact parent in a separate interpreter, recreates its private ledgers, then executes the candidate and replays the fresh parent-produced legacy inputs. No preexisting ledger or prior review output is needed. It creates `parent-reproduction/results.json`, `parent-reproduction/source-manifest.json`, candidate `results.json`/`source-manifest.json`, and private runtime ledgers under this lane. For candidate-only execution, omit `--legacy-parent-root`. The independent parent command is `python review-39b94d8-f01/trajectory/probes.py --parent-root review-4157ac1-f01`.

The official command completed with exit code 0; both stderr files are empty. Candidate and parent each verified all **876 staged production files** against their exact Git blob IDs after execution. Both imported 51 production files. `source-manifest.json` lists every staged file with Git blob, SHA-256 and byte length, the imported production files, and explicitly read static source. Byte integrity is not function/branch coverage.

The candidate ran 11 exporter/consumer cases, 52 current-writer target/confidence/control cases, 26 current-writer gate/comparator cases, nine explicitly separated event-only legacy mutations, and three unmodified parent-writer/current-reader cases. The two legacy seeds also come from the actual current pipeline. Results use strict JSON (`allow_nan=False`); non-finite values are represented as descriptive objects. Private JSONL retains the actual production writer's serialization behavior for malformed fixtures. No production source was changed.

All current-writer candidate approval rows were emitted by `add_validation_event_to_ledger`, not invented by the harness. The exercised chain is `record_asmae_run` → `ValidationEvent`/writer → disagreement → candidate → emitted `candidate_update` → replay → `build_validated_training_view`. `AGRIWISE_ARCHIVE_PILOT_MODE=false` is set before imports, and every ledger path is private to this lane.

## R415-01: closed in actual exporter → L1 adapter

Candidate `layer1_fusion/adapters/asmae_adapter.py:20–23` now imports `finite_real`. The actual `export_weak_labels` output is passed unchanged to actual `ASMAEAdapter.extract_evidence`.

| Input estimate | Exact parent | Candidate exporter | Candidate L1 `ASMAE_TRAINING_WEIGHT` |
| --- | --- | --- | --- |
| `0.0` | Export weight 0.30; L1 `NameError` | 0.30 | 0.30, no error |
| `0.5` | Export weight 0.30; L1 `NameError` | 0.30 | 0.30, no error |
| NaN, infinity, Boolean, numeric string | Export weight 0; L1 `NameError` | 0 | 0, no error |

Evidence: `P1_weak_export_declared_callers` in candidate and parent results. Shadow mode, no scenes, zero scene count, radiometric failure and uncertified 1m exporter controls retain zero weight. The production engine call is statically traced at `layer05_asmae/engine.py:326`, `1576–1605`; the full engine and upstream producers were not imported or executed. This proves the declared exporter/consumer path, not end-to-end upstream assimilation.

## R415-06: repaired cases and preserved controls

| Named gate/reader concern | Exact-parent reproduction | Candidate result |
| --- | --- | --- |
| Uncertainty NaN, negative infinity, `False`, numeric string, negative value | Actual approved candidate and sample | Pending/ineligible, no sample |
| Retro NaN, infinity, `True`, numeric string, above 1 | Actual approved candidate and sample | Pending/ineligible, no sample |
| Selected resolution NaN/infinity | Actual approved candidate and sample | `invalid_resolution`, no sample |
| Selected resolution `True`, negative, numeric string | Old blocker or error | `invalid_resolution`, no sample |
| NaN model raster comparator against finite observed 1.0 | Actual approved candidate and sample | Critical `unqualified_model_comparator`, `contradiction_detected`, no sample |
| Legacy confidence 2.0 | Reader emits a sample from event-only legacy fixture | Reader excludes it |
| Actual parent-approved fractional biotic NaN | Parent emits sample | Current reader excludes unmodified parent ledger |

The candidate uses `finite_real` and explicit ranges for uncertainty/retro in `asmae_learn/candidate_builder.py:118–153`. The comparator now rejects an all-nonfinite raster mean and records a critical contradiction in `asmae_learn/disagreement.py:83–102`, `192–204`. The legacy confidence upper bound is enforced by `asmae_learn/dataset_builder.py:169–171`.

All four original continuous targets (`vigor`, `canopy_water`, `salinity_stress`, `yield_observed`) preserve finite and zero values through approved samples. NaN, infinity, Boolean, numeric-string and malformed-string values are rejected before event append. NaN/infinite/Boolean/string/out-of-range confidence is likewise rejected before event append. Valid confidence and zero-valued targets remain usable. Categorical crop stage/biotic controls and irrigation/harvest events still produce legitimate approved samples. Zero confidence, finite contradiction, synthetic source, uncertified 1m, visual-only, diagnostic-only and weak-label-as-truth exclusions produce no dataset sample. Zero uncertainty and the 0.7 retro boundary remain eligible.

## Residual 1: explicit invalid selected resolution is replaced before qualification

Location: `asmae_learn/candidate_builder.py:80–84`; mirrored replay fallback at `asmae_learn/dataset_builder.py:111–113`.

With `diagnostics.resolution_selected_m=False` or `0.0`, and `run_record.resolution_m=10.0`, the `or` expression replaces the supplied selected value with 10.0 before `finite_real` and the positive-resolution check. In both candidate cases, actual production code writes:

- Record sequence: `asmae_run`, `validation_event`, `disagreement_report`, `candidate_update`.
- `learning_candidate_status="approved"`, `eligible_for_asmae_learn=true`, empty blocked reasons.
- One training sample after replay.

The exact parent behaves the same way. This is a remaining current-writer admission path, not a forged approval or legacy-only mutation. NaN, infinity, `True`, negative values and numeric strings are now blocked, so the new qualification materially helps; it does not see the falsy selected values. Keep an explicit present value and qualify it, using fallback only for the intended missing-value case.

Evidence: `P3_actual_candidate_gate_scalars.cases.resolution_boolean_false` and `.resolution_zero`; private runtime files `gate_resolution_boolean_false.jsonl` and `gate_resolution_zero.jsonl`.

## Residual 2: fractional-biotic reader type parity remains incomplete

Locations: writer `asmae_learn/schemas.py:95–109`; reader `asmae_learn/dataset_builder.py:173–181`.

The current writer recognizes `biotic_confounder` with `observed_unit="fraction"` as continuous and rejects Boolean/string observed values. The reader only treats fractional biotic values as continuous when their existing Python type is numeric and non-Boolean, ignoring the fractional unit for this decision. A string therefore bypasses the finite-real check and is returned as `target_value`.

`P6_actual_old_writer_current_reader` freshly executes the exact parent actual writer. Parent `biotic_fraction_numeric_string` (`"0.5"`) and `biotic_fraction_bad_string` (`"not-a-number"`) both produce real approved candidate rows and samples. The candidate dataset reader then consumes those parent ledgers **without modifying any row** and emits one sample for each, preserving the string target. Current `ValidationEvent` rejects the same events. Per-ledger SHA-256 before and after reading is recorded. Parent-approved NaN is the blocked control.

`P4_legacy_read_schema_parity` separately changes only event values in current valid writer-generated seed ledgers, retaining generated approvals unchanged. It confirms the same reader gap for Boolean and string fractional biotic values; Boolean is a read-defense fixture, not proof of current-writer acceptance. NaN is excluded. The original four continuous targets and legacy confidence checks now reject their malformed event-only counterparts. Align the reader with the existing named fractional-biotic writer qualification; no broader alias/unit policy is asserted here.

## Boundaries

No repository tests, audits, generated repository artifacts, prior review outputs, production Git operations, network, services, providers, hardware or optimizer/model fitting were used as correctness evidence. Prior probe code was reused as harness material only. All behavioral evidence was regenerated from exact staged production source. No optimizer or field-performance claim follows from admission/replay results. The two open assessment checks in `closure_checks` describe the measured residuals; all `harness_checks` and `observed_result_assertions` pass.


---

# Specialist appendix: Contained RF covariance admission

# R415-07 RF covariance closure verification

**Disposition: bounded software closure verified at `39b94d8de2911cdbaa9e86d24a46f40464cba101`**, parent `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`. Explicit invalid covariance no longer becomes the `0.25` model default on the reviewed typed likelihood → operator → Layer 0 spine → adapter path. Each named invalid input becomes proposal variance `None`, `ABSENT`, unusable for assimilation, no event, and no actual private queue entry. This closes the named R415-07 fallback mechanism; it is not F01 full acceptance.

A fresh authored process ran **79 cases and 16 strict controls with no failed controls**. The process checked all **876 staged files** against the candidate tree and SHA-256 manifest before and after calls, including the entire **176-file production MESIA Python tree**. It used real production imports without edited source or package stubs. The actual imported-file manifest records 202 module entries representing 179 unique candidate source files, plus hashed external imports. Importing a module is not statement coverage.

The normative basis is `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`, F01 lines 151–177, and `current-plan-review/R3_current_scientific_sections.txt`: AB-DAT-005 (missingness/zero), AB-DAT-006 (field provenance), AB-ARC-005 (factorized authority), AB-ARC-006 (bounded degradation without promotion by fallback). `normative-manifest.json` identifies those local normative inputs. The root review independently verifies their candidate blobs. Repository tests, audits, old run outputs, plan status claims, and generated repository artifacts were not runtime proof.

## Named covariance controls

Every row below used a real `BehaviourLikelihood` with finite innovation `0.0`, support `1.0`, a native lineage hash, and explicit internal calibration/epoch `True`. The real adapter received an explicit qualification `True` for this typed boundary fixture.

| Authored label | Raw covariance | Candidate proposal variance | Spine / event | Actual dispatcher outcome |
|---|---|---:|---|---|
| `covariance_nan` | NaN | `None` | `ABSENT`; no event | No call; absent from queue inventory |
| `covariance_positive_infinite` | +Inf | `None` | `ABSENT`; no event | No call; absent from queue inventory |
| `covariance_negative_infinite` | −Inf | `None` | `ABSENT`; no event | No call; absent from queue inventory |
| `covariance_boolean_true` | `True` | `None` | `ABSENT`; no event | No call; absent from queue inventory |
| `covariance_boolean_false` | `False` | `None` | `ABSENT`; no event | No call; absent from queue inventory |
| `covariance_numeric_string` | `"0.1"` | `None` | `ABSENT`; no event | No call; absent from queue inventory |
| `covariance_malformed_string` | `"invalid"` | `None` | `ABSENT`; no event | No call; absent from queue inventory |
| `covariance_zero` | `0.0` | `None` | `ABSENT`; no event | No call; absent from queue inventory |
| `covariance_negative` | `-0.1` | `None` | `ABSENT`; no event | No call; absent from queue inventory |
| `covariance_missing` | `None` | `0.25` | `ADMITTED`; state-authorized event | `admitted_for_assimilation`; persisted `QUEUED` |

The production distinction is explicit in `services/agribrain/mesia/assimilation/asmae_operator.py:80–85`: only raw covariance `None` selects the source-documented model default; a valid strictly positive finite real retains its value; any other explicit covariance produces `None`. `layer0_spine.py:74–92` then rejects missing/nonfinite/nonpositive variance before the adapter. `MesiaAsmaeAdapter.to_asmae_observation_event` returns `None` for unusable records. Nine additional `direct_spine_covariance_*` cases preserve the raw bad covariance and confirm that the spine gate also blocks these values independently of the operator correction.

The separate `covariance_missing` control establishes legitimate default behavior and its provenance: the recorded authored input has raw covariance `None`; the candidate source branch identifies `0.25` as a model default; proposal `likelihood_ref` and `native_lineage_hash` match the input; the event and actual queue summary retain the uncertainty-model/operator references and variance quality reference. The result's `covariance_origin` is an explicitly labeled **review interpretation of the authored input plus source branch**, not a new production provenance field or a claim that `0.25` was physically measured.

## Preservation and containment controls

| Named controls | Observed result |
|---|---|
| `typed_zero_innovation`, `typed_finite_positive_innovation`, `innovation_zero`, `innovation_negative` | Finite variance `0.1` retained; `ADMITTED`, state-authorized event, actual `QUEUED`. Zero and finite negative innovation remain valid. |
| `finite_zero_innovation`, `legitimate_zero_snr`, `finite_negative_snr` | Real packet → likelihood → bridge → spine → adapter → private dispatcher: innovation `0.0`, `-22.0`, `-23.0` respectively; admitted and queued under explicit internal fixture qualification. |
| Invalid/missing/bool/string SNR; WiFi derived NaN/bool SNR | `ABSENT`, no event and no dispatcher call. The derived malformed-string SNR case raises `ValueError` before event/dispatch; containment is preserved, not described as a clean absence receipt. |
| Missing, zero, negative, nonfinite, bool and string support; malformed/nonfinite/bool/missing innovation | No state-authorized event. Support cases are `ABSENT`; missing/zero support does not synthesize an observation. |
| Documented `TRANSPORT`, `CONTEXT`, `TEACHER`, `SENTINEL`, `NEGATIVE_CONTROL`, `GEOMETRY_AUTHORITY`, `EVENT_LEDGER` | Each remains `ABSENT` with no event despite otherwise usable numeric values and registered matching capability. Enum `CONTEXT` is also blocked. |
| `defaults_omitted`, `unverified_calibration_and_epoch`, `unverified_calibration` | `INVALIDATED`, no event. |
| `unverified_epoch` | `QUARANTINED`, no event. |
| `sensing_without_qualified_capability` | Usable Layer 0 record remains `ADMITTED`, but adapter event has state authority `False`; the actual dispatcher returns `abstained_uncalibrated` and persists `ABSTAINED`. |
| `visible_service_false_gates_retained` | Static AST inspection finds the visible MESIA service caller still passing explicit calibration `False` and epoch `False` at `mesia/service.py:2629–2635`. The service was neither imported nor executed. |

The bridge also retains default calibration/epoch `False` in `mesia/integration.py:93–113`. The internal positive fixture registers an explicit matching all-gates capability and passes calibration/epoch `True`; these are controlled API conditions, not independently verified physical calibration. The SigMF capture uses synthetic private integrity bytes. Its stored hash/integrity check establishes artifact consistency only.

The prior adjacent `CONTEXT.SENSING` compatibility case still normalizes to SENSING and queues under the same explicit fixture. It remains **not counted as a finding**: no documented valid producer/schema for that malformed tag was established. This verification does not expand R415-07 into a role-normalization finding.

## Consumer evidence and limits

The real `ASMAEObservationDispatcher.dispatch_event` produced **13 durable private records: 12 `QUEUED`, 1 `ABSTAINED`, 0 `COMMITTED`**. Every record is accounted for by a summarized receipt and its hash; explicit-invalid covariance labels are absent from the actual queue inventory. The 12 queued cases include finite/zero positive controls, the legitimate covariance-absence default, SENSING/enum/default-role controls, and the noncounted dotted-role compatibility case. Queue creation is the downstream consumer evidence for this review.

`results.json` includes summarized queue receipts, record status, identifiers, hashes and operator/uncertainty references; it does not embed raw private queue records or raw capture bytes. The private files exist solely to verify actual persistence. No queue processing, EnKF update, canonical assimilation commit, training, radio acquisition, hardware, network, deployed service, machine action, or Git mutation was performed. No public posterior or deployed calibration reachability is claimed.

## Reproduction and strict artifacts

From the workspace root, run:

```bash
PYTHONDONTWRITEBYTECODE=1 python review-39b94d8-f01/protocol/qualification_probes.py
```

The runnable probe resolves the sibling `source`, `git-tree.json` and `source-manifest.json`, writes only within its protocol directory, refreshes its private queue, verifies source integrity again after execution, and raises on **every** failed named check, including the R415-07 target. There is no prior target-check exemption. Results serialize nonfinite inputs as explicit tagged objects with strict JSON (`allow_nan=False`).

- `qualification_probes.py`: authored runnable real-import boundary probe, adapted from prior authored code; prior outputs were not reused as evidence.
- `results.json`: fresh full case inputs, proposals/records/events, summarized consumer receipts, strict controls and bounded scope.
- `run-stdout.json`: compact execution summary from this run.
- `source-import-manifest.json`: actual source/external file imports and hashes after execution.
- `normative-manifest.json`: local normative input hashes.

**Closure conclusion:** R415-07 is closed for the named explicit-invalid covariance fallback through the reviewed internal typed consumer composition. Legitimate absent-covariance default, finite/zero controls, documented role restrictions, false calibration/epoch gates and unqualified-capability consumer containment remain intact. This conclusion does not promote F01 or any other package to full acceptance.

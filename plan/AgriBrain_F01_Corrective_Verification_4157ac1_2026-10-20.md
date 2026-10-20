# AgriBrain F01 corrective verification — 4157ac1

Reviewed 20 October 2026. Repository webClone/AgriWise. Candidate/main verified at `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`; parent `b51616da5a6f67a7a194439485c7aac71c7396ed`.

## Decision

**Credit the repaired original cases and continue the bounded F01 integration work. Do not accept F01 yet.** The candidate contains substantial, verified corrections. It also introduces a concrete runtime regression in the Layer1 ASMAE weak-label consumer, and actual supported producer/consumer paths still bypass parts of numeric, role and quality qualification.

This is not a declaration that the previous batch accomplished nothing. The original NDVI/crop boolean cases, immediate packet-role conflicts, wrapper invalid reliability, forecast/excluded-satellite reproductions, bounded water-history field loss, weak-export malformed estimates and four continuous target/confidence writer failures now have working corrections. The remaining groups below distinguish those completed slices from other active consumers.

The consolidated priorities below govern; appendices retain their lane-specific assessments. The seven consolidated residual groups are not seven newly introduced bugs. One is demonstrated to be introduced: R415-01. The other groups include preexisting consumers and integration gaps in the new carrier/normalization work. Scalar variants, repeated histories and overlapping reviewers are not counted as additional groups.

All 52 package-FA rows remain open, zero checked; F01's four task rows and FA are also unchecked. The five production targets relevant to R51901/R51902 remain Git-blob identical to both prior reviewed commits. Their prior software closures are preserved. This source-continuity result is not a fresh whole-suite or hardware no-regression claim.

## Evidence and review coverage

Six reviewers completed fresh bounded workstreams: temporal/Layer1 components, wrappers/typed producers, water assimilation/history, crop/weather features, training, and contained RF admission. Their full reports appear as appendices. Root independently replays the authored commands in a separate exact-source layout and checks selected observations and controls; the replay receipts are bundled.

Twenty production modules changed in this commit. All twenty compile without imports. That check does not establish runtime correctness: the actual missing-name case below passes compilation. The staged candidate corpus contains876 exact production/configuration files; one exact dependency was added to the initial875. Every byte matches its candidate Git blob. The exact-parent training controls use875 parent files and produce fresh outputs rather than adopting earlier report results. Staged/imported counts are not branch coverage.

Only candidate and exact-parent production source, the three normative plans and the supplied R3 were correctness inputs. Repository tests, new or historical audit documents, generated repository artifacts and reported pass totals were excluded as proof. The user's547/124 results are recorded as reported results, not independently rerun suite totals. No code/Git mutation, live provider/service/controller/radio/drone operation, physical calibration or model fitting occurred.

Actual water execution includes the full WaterIntelligenceEngine. Other seams invoke actual adapters, validators, ledgers, feature builders, writers, candidate builders and dataset views as documented. The Layer1 admission method and two pure history helpers are unchanged production AST definitions isolated from unrelated initialization. Full fusion orchestration, durable L3 storage, upstream ASMAE EnKF, RF posterior commit and optimizers are not implied. RF events reach an actual private dispatcher queue; QUEUED is not COMMITTED.

## Original repair disposition

| Original group | Verified repair credit | Remaining acceptance limit |
| --- | --- | --- |
| B01 quantitative components | Known NDVI boolean/malformed/nonfinite components quarantine; EVI0 survives. Reflectance dtype checks reject malformed arrays; boolean QA masks remain valid. Invalid thermal scalars do not create GDD. | Other registered quantitative fields can still admit strings: R415-05. |
| B02 roles | Immediate typed/dictionary aliases and daily/user fast paths preserve tested restrictions. Non-observed S2 scenes produce no physical model tokens. | Source-aware normalization, canonical weather and RECONSTRUCTION handling remain inconsistent: R415-02. |
| B03 reliability | Direct wrappers distinguish absent from invalid supplied quality; explicit0 survives. Typed packet constructor rejects invalid quality. | Earlier perception producer and separate sensor adapter bypass the corrected wrapper: R415-04. |
| B04 water/history | Forecast source now ASSIMILATED; excluded satellite haszero rows / zero analysis increment; actual history helpers preserve all new fields and both-zero quality blocks influence. | Component authority and quality precedence do not follow all qualified inputs: R415-03. |
| B05 weak labels | NaN/Inf/bool estimates and malformed quality gates get zero exporter weight/reasons. | Valid labels now raise NameError in actual Layer1 consumption: R415-01. |
| B06 supervised targets | Original invalid continuous target/confidence writer cases reject before event append. Four continuous zero targets and legitimate categories survive. Read guard rejects the tested malformed continuous legacy targets. | Candidate diagnostics and model comparator remain numerically unqualified: R415-06. |
| B07 RF | Invalid SNR/innovation/support and valid documented non-SENSING roles block; finite zero and containment controls survive. | Invalid covariance becomes a healthy default before the spine: R415-07. |

## Residual groups and implementation actions

### R415-01 — P1, introduced: valid weak labels crash the Layer1 ASMAE consumer

For both estimate0 and.5, the real exporter returns training weight.30. The actual ASMAEAdapter then raises `NameError: name 'finite_real' is not defined`. Fresh exact-parent controls return training-weight evidence.30 for both inputs.

The new calls at [layer1_fusion/adapters/asmae_adapter.py:L409-L421](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer1_fusion/adapters/asmae_adapter.py#L409-L421) have no corresponding import or definition in the module. Nonempty weak labels enter this branch whenever training permission passes; the method aborts before returning its evidence list. A malformed label with correctly zeroed export weight also encounters the exception. This is a runtime integration failure, not successful numeric rejection.

**Repair:** import the shared helper through the module's real package convention; re-run actual exporter→adapter on valid0/.5 and malformed/blocked labels. Keep state-update-false diagnostic authority. The upstream engine/export call is source-traced, not executed as a full EnKF. Do not claim that adding an import alone validates the whole training pipeline.

### R415-02 — P1: later role normalization reverses restrictions

Three related active seams show that immediate wrapper correctness is not yet monotone across consumers.

- **Typed perception→Layer1:** actual DRONE PerceptionEngineOutput with simulated, estimated, fallback or unavailable status passes through the shared packet producer, default wrap_perception and PerceptionAdapter. The immediate packet adapter has the correct restrictive status/permissions. Source-aware normalization then reclassifies it observed, diagnosticfalse, state-update-allowedtrue and actual ledger admission accepts it. Confidence ceilings survive (.20 for simulated,0 for unavailable). No solver state mutation is claimed.
- **Canonical weather→crop:** a weather row with `temp_mean_c=20` and explicit data_status unavailable yields an unavailable packet but observed canonical evidence_record. The actual crop token gets GDD10=10. A conflict roleOBSERVATION/source_roleEXCLUDED repeats the seam. Six-scene feature input produces the same thermal values and input receipt hash as observed weather; direct unavailable-weather and explicit excluded-role controls yield no thermal features. The exercised model-input receipt remains below completeness threshold, so classifier execution/publication are still gated.
- **RECONSTRUCTION:** R3 explicitly distinguishes this field role. The accepted canonical packet/Sentinel2 path does not recognize it as non-observed; actual validation, ledger and fusion output treat reconstructed NDVI as observed, nondiagnostic evidence. This is feature/admission proof, not a full final posterior.

The active fusion run normalizes with package context at [layer1_fusion/engine.py:L156-L170](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer1_fusion/engine.py#L156-L170). The DRONE branch overwrites restrictions at [layer1_fusion/truth_bridge.py:L374-L388](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer1_fusion/truth_bridge.py#L374-L388). Canonical weather independently selects the first role alias and ignores explicit daily status at [layer0/wrappers.py:L89-L109](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer0/wrappers.py#L89-L109).

**Repair:** make role/status/permission merging monotone in the actual final normalizer, not only the immediate packet adapter. Use the same qualification result for packets and canonical weather records. Add the normative RECONSTRUCTION role without renaming it observed. Preserve legitimate qualified forecast/scenario forcing; its arithmetic is not itself a defect. Validate the actual source-aware route and token/feature receipt, retaining the independent optical evidence controls.

### R415-03 — P1: water authority and influence do not follow qualified component metadata

All three original water counterexamples are corrected. The new carrier introduces valid typed component metadata, but two resolution mechanisms remain.

1. With global observed role and `component_roles={'soil_probe': 'SIMULATED'}`, actual OI legitimately admits3 model rows. The full water runner nevertheless grants **OBSERVED**, with analysis increment **+89.70mm**. The matching source-tagged simulated control gets ASSIMILATED. The role reaches the assimilator but not its admitted-source authority receipt.
2. `reading_reliability=0` alone is shadowed by the new default `reliability_weight=1`:3rows, no rejection, **+89.70mm/OBSERVED**. WeightNone plus reading0 correctly rejects, while present weight NaN plus reading zero again admits3rows with the same influence. Invalid quality is not merely retained in an envelope; it changes actual admitted influence relative to the zero/absent controls.

A global EXCLUDED/zero restriction can also be overridden by component OBSERVED/quality1. Conversely, a satellite-specific exclusion source string suppresses independent valid TDR rows, whereas the typed satellite-component exclusion preserves them. These are scoped role/quality resolution variants, not separate counted findings.

See [layer3_water/assimilation/water_state_assimilator.py:L97-L156](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer3_water/assimilation/water_state_assimilator.py#L97-L156), [layer3_water/contracts/assimilation_state.py:L22-L36](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer3_water/contracts/assimilation_state.py#L22-L36) and [layer3_water/runner.py:L386-L406](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer3_water/runner.py#L386-L406). Exact history helper round trips preserve the new fields; the residual is no longer serializer loss. Full durable orchestration was not executed.

**Repair:** propagate admitted component receipts containing role, quality, scope and source to authority selection. Define absent/invalid/zero quality semantics before applying defaults, and do not let a default erase explicit0. Compose global hard restrictions and component restrictions explicitly; isolate unrelated source restrictions. Synthetic/forecast model updates may remain valid under truthful ASSIMILATED authority. Counts describe OI rows, not independent field sensors.

### R415-04 — P2: supported typed producers bypass the corrected reliability wrapper

The direct wrapper and typed ObservationPacket constructor fixes work. On the actual shared perception producer path, earlier min/max coercion changes Inf,NaN orTrue reliability to1 and raises legitimate0 to.05. The constructor then sees an already valid-looking number. Actual DRONE evidence is accepted with confidence1 or.05 and state-update permission.

A separate actual NormalizedSensorReading/SensorQAResult→SensorAdapter path accepts reading_reliabilityTrue as a boolean reliability with confidence.95/state-update permission. NaN/Inf there quarantine and explicit update denial stays diagnostic.

See [layer0/perception/common/packet_adapter.py:L153-L166](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer0/perception/common/packet_adapter.py#L153-L166), [layer1_fusion/adapters/sensors.py:L68-L92](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer1_fusion/adapters/sensors.py#L68-L92) and [layer1_fusion/evidence_validation.py:L59-L65](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer1_fusion/evidence_validation.py#L59-L65).

**Repair:** qualify native quality before clamping/flooring. Keep0 as0. Centralize finite/nonboolean quality admission in the final EvidenceItem validator too, so a separate native adapter cannot bypass it. These reproductions prove actual producer/ledger eligibility, not posterior or training effect. They do not reopen the corrected direct-wrapper defect.

### R415-05 — P1: strict numeric checks depend on the bounds table

Registered soil_clay_pct, emitted on the natural SOILGRIDS→canonical environment-package route and consumed by fusion, accepts both a numeric string and a malformed string alongside valid sand40. Actual packet→registered environment adapter→source-aware normalization→validator→ledger→fuse_features retains the soil field as a nondiagnostic fused feature. Known NDVI malformed controls now reject; soil bool/Inf controls reject; missing soil is omitted and finite/zero survives.

The new strict finite_real check applies only to fields in _BOUNDS. The fallback branch checks booleans/nonfinite floats, allowing strings for quantitative variables absent from that bounds table: [layer1_fusion/evidence_validation.py:L124-L170](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer1_fusion/evidence_validation.py#L124-L170). This is not an arbitrary unknown categorical key.

**Repair:** separate quantitative type qualification from optional physical bounds. Register target types independently; apply finite-real admission to all declared quantitative fields before weighting/feature construction. Preserve categorical vocabularies and boolean flags. If numeric strings are supported, normalize them explicitly before admission with provenance; do not pass malformed strings as physical features. This lane does not execute the full fusion engine or claim a final soil-state mutation.

### R415-06 — P1: training eligibility still accepts malformed numeric diagnostics

The continuous external target/confidence writer fixes work. With valid finite target/confidence and complete lineage, the actual writer→schema→disagreement/candidate→candidate_update→replay→validated view still approves samples for uncertaintyNaN/negativeInf/False, retroNaN/positiveInf/True, or selected resolutionNaN. These are actual production-generated approvals, not fabricated approval rows.

A finite target1 against finite model vigor0 correctly yields a contradiction and no sample. Changing only the model comparator toNaN suppresses the contradiction and creates approval plus a sample. Candidate thresholds convert with float and compare without finite/nonboolean qualification; disagreement qualifies the external target but not the model mean. See [asmae_learn/candidate_builder.py:L75-L143](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/asmae_learn/candidate_builder.py#L75-L143) and [asmae_learn/disagreement.py:L81-L96](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/asmae_learn/disagreement.py#L81-L96).

**Repair:** qualify every numeric input that controls eligibility, not only the final target: resolution, uncertainty, retro score and model comparator. Invalid comparison is unavailable/blocked, not agreement. Retain four valid zero targets, finite contradiction, confidence0, synthetic-source, visual-only,1m and weak-label-as-truth exclusions. Numeric strings are observed normalization behavior, not independently prohibited without policy.

The appendix separately bounds target-registry and legacy-read parity: a declared fraction form of an allowed mixed categorical/numeric biotic target admits malformed numeric content, and a legacy confidence2 fixture passes read defense although the current writer rejects it. These are not claimed as fresh current-writer confidence bypasses, new unit-conversion requirements or additional counted groups. Use one target/type/quality contract at write and read. No optimizer or trained-model effect was executed.

### R415-07 — P2, contained: invalid RF covariance is replaced before qualification

The full bridge now blocks tested bad SNR/support and documented non-SENSING roles. But typed covarianceNaN/±Inf/bool/malformed string is converted by the operator to0.25. The actual spine sees a healthy finite replacement, admits it, the adapter grants state-update authority under explicit internal qualification, and the actual private dispatcher persists it QUEUED. Direct-spine raw invalid-covariance controls reject.

See [mesia/assimilation/asmae_operator.py:L75-L81](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/mesia/assimilation/asmae_operator.py#L75-L81), [mesia/assimilation/layer0_spine.py:L74-L99](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/mesia/assimilation/layer0_spine.py#L74-L99) and [layer05_asmae/observation/dispatcher.py:L232-L299](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/layer05_asmae/observation/dispatcher.py#L232-L299).

**Repair:** distinguish truly absent covariance with a documented model default from explicitly invalid covariance. Retain invalidity/provenance through operator→spine→adapter→queue; do not silently manufacture admissible quality.

The service still passes calibrationfalse/epochfalse at [mesia/service.py:L2628-L2642](https://github.com/webClone/AgriWise/blob/4157ac1d51d83f75f3379c13741fc9bc77b4f4fe/services/agribrain/mesia/service.py#L2628-L2642). Negative calibration/epoch and absent capability controls contain admission. Qualified-capability/calibrationtrue fixtures are internal API conditions, not physical metrology proof. Training/machine permissions stay false. No filter commit or posterior movement was executed. A malformed dotted role tag is an adjacent compatibility observation only, not a separately counted finding or proven public path.

## Plan and R3 traceability

The master F01 card (lines151–177) requires per-component accepted/rejected qualification before authority/solver, roles through typed/dictionary carriers, and parity across weather/RF/crop/training. The task register is ST01-F01-01 through04 and ST01-F01-FA. R3 uses scientific requirement IDs; F/T IDs belong to the plan.

| Requirement | Working controls | Remaining groups |
| --- | --- | --- |
| AB-DAT-005 zero/missingness | Known quantitative zero, explicit wrapper quality0, four continuous target zeros, SNR/innovation0 survive | R03,R04,R05,R06,R07 numeric/quality qualification and R01 valid-zero consumption |
| AB-DAT-006 per-field observation/prior/reconstruction/forecast/synthetic provenance | Immediate aliases, daily/user and S2 scene-role guards improve | R02,R03 scoped role transport/authority |
| AB-ARC-005 factorized authority | Diagnostic weak labels, simulated water ASSIMILATED controls, RF training/machine restrictions survive | R02,R03,R06,R07; R01 prevents valid consumer completion |
| AB-ARC-006 bounded degradation | Invalid target/wrapper and calibration controls fail closed | Invalid defaults/coercions and later promotion in R02–R07 |

The supplied R3 requirement excerpt is at675–681 and738–744; PDF SHA256 `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`. The three selected normative plan files match candidate Git blobs. Supplemental local plan/audit artifacts are not implementation proof. Unchecked register rows are status, not evidence that no work exists.

## Bounded next implementation order

1. **Restore valid ASMAE consumption immediately:** fix R415-01 and verify actual exporter→adapter valid0/.5 plus malformed/blocked cases. This small integration correction can proceed independently.
2. **Unify actual final qualification:** use target types separately from bounds; qualify source quality before coercion; enforce quality at final EvidenceItem admission. Close R04/R05 while preserving flags/categories and zero.
3. **Close monotone propagation at real callers:** use one packet/canonical-record qualification result, preserve restrictions through source-aware normalization, and recognize RECONSTRUCTION. Verify actual DRONE/S2/soil/weather routes and receipt changes for R02.
4. **Finish water component receipts:** role, source scope and composed quality must survive admission and govern authority. Close R03 with the finite/zero/source/component controls, followed by a bounded actual durable history integration run before claiming persistence closure.
5. **Qualify training decisions and replay:** repair R06 threshold/comparator checks and share target/quality rules across current writer and legacy view. Keep existing source/lineage and objective-specific gates.
6. **Fix the contained RF default:** close R07 with the actual operator/spine/adapter/queue cases; retain default service containment and distinguish admission from posterior commit.
7. **Run the same finite acceptance matrix:** corrected original cases plus these named residuals at actual consumers. Do not expand into a new unlimited whole-repository audit. Choose regression checks for changed paths and broaden only for new code/failures.

F01 is ready for this implementation sequence now; it is not ready for full acceptance. Independent package preparation and objective-qualified research may continue in parallel. Dependent acceptance cannot assume universal F01 qualification, and unrelated packages do not acquire a new blanket hardware prerequisite from this review.

## Deliverables

The claim-disposition JSON preserves original repair credit, maps residuals to source/evidence/requirements and records all 52FA rows unchanged. The evidence bundle includes authored probes, fresh candidate and exact-parent observations, source identities, replay receipts and a read-only Git-object materializer. Production-source copies, repository tests/audits and private raw captures/queues/training ledgers are excluded.

Eight replay commands cover six lanes, including platform metadata and the exact-parent training control. Exit0 means documented behavior reproduced, including remaining contract expectation failures; it is not an all-clear or production test-pass count. The separate Git-object materializer is syntax/layout checked, not executed against a second full Git checkout.



---

# Specialist appendix: Temporal/typed evidence and downstream component validation

# F01 temporal/packet/component verification — 4157ac1

Candidate: `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`. Parent: `b51616da5a6f67a7a194439485c7aac71c7396ed`.

**Verdict: the original direct B01/B02 examples are corrected; F01 remains partially satisfied in this lane.** Known NDVI components now reject booleans, numeric strings, malformed strings and nonfinite values before ledger admission. Existing canonical source roles and their alias conflicts no longer become state-eligible observations in the direct packet bridge. Two bounded current counterexamples remain: the normative `RECONSTRUCTION` role becomes observed, and strings in a known quantitative soil channel survive the actual registered source route into a non-diagnostic fused feature. These are current-source counterexamples, not a claim that this commit introduced them.

## Basis and boundaries

Normative inputs are the workspace-root `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:151–177`, `sr-team-review/plan/AgriBrain_Work_Packages_Task_List_2026-10-07.md:153–180`, and supplied `current-plan-review/R3_current_scientific_sections.txt:675–681,738–744`. F01 requires explicit admitted/rejected components before authority/solver selection, role preservation through typed/dictionary adapters, legitimate zero preservation, and accepted counts following qualified components. AB-DAT-006 explicitly distinguishes OBSERVATION, PRIOR, RECONSTRUCTION, FORECAST and SYNTHETIC; AB-ARC-005/006 separate capabilities and prohibit fallback promotion.

`probes.py` imports candidate production modules directly. Every imported source file is independently matched to the candidate Git-tree blob SHA and recorded with SHA-256 in `executed-file-manifest.json` (49 unique production files). The static inspection receipt list is separate. There is no AST isolation, replacement production implementation, repository test execution, prior-report/result evidence, network execution, provider/service invocation, hardware, training run or production/Git modification. The previous harness supplied reusable fixture/code structure only; its old outcome assertions were replaced.

The source-aware probes invoke actual `SourceRegistry.register/get_adapter`, `source_health/validate_envelope`, `can_read/extract_evidence`, `normalize_evidence_truth(item, source_context=package)`, `validate_evidence`, `quarantine_evidence`, `EvidenceLedger.add/state_updatable`, and `fuse_features`. This mirrors the relevant call order in `layer1_fusion/engine.py:138–176,249`. The candidate full engine is inspected but not executed; freshness, conflict handling and other intervening full-run stages are outside this lane. Envelope validation is a prerequisite control, not evidence of a physical state update. The reported outcomes are actual evidence-ledger eligibility and fused-feature selection, not Kalman/soil-state transitions, training-weight changes, prescription or execution.

All fixtures have complete inert identities and eligible observation/availability/ingestion/cutoff timestamps. No F02 cutoff conclusion is inferred. The static soil source is tested as `ObservationSource.SOILGRIDS` with a canonical environment package, not as an arbitrary unknown/categorical field.

## Corrected behavior

| Group | Actual bounded checks | Result |
|---|---|---|
| G01 | Temporal scalar predicate: finite/zero versus ±Inf, NaN, bool, numeric/malformed string, missing | Only finite real zero/finite controls admitted |
| G02 | Typed/dictionary mixed NDVI + valid EVI zero through registered Sentinel2 source adapter, source-aware normalization, validator, ledger and feature selection; NDVI physical endpoints and just outside endpoint; invalid-only and all-missing records | Invalid NDVI components quarantine; valid EVI zero survives; NDVI −1 and +1 survive; 1.0001 rejects; invalid-only/all-missing contribute no admitted component |
| G03 | OBSERVATION, SIMULATED, SYNTHETIC, PRIOR, FORECAST, EXCLUDED, REJECTED through typed/dictionary direct packet→truth→validator→ledger | Only OBSERVATION is state eligible; explicit status and confidence restrictions survive |
| G04 | Individual source_role/data_role/status_role/truth_class aliases; OBSERVATION vs SYNTHETIC, PRIOR vs EXCLUDED, SYNTHETIC vs REJECTED conflicts; existing typed simulated/unavailable/estimated status | Restrictive role wins; no state-eligible component |
| G07 | Strong ASMAE observation values and strictly positive variances across the same scalar controls; legitimate zero JSON round trip | Invalid values/variance reject; zero observation survives; zero variance rejects |

This is positive repair evidence. `layer1_fusion/evidence_validation.py:145–157` now applies `finite_real` and explicit boolean rejection to known bounded variables. `layer0/wrappers.py:144–193,243–267`, `layer1_fusion/truth_bridge.py:543–624`, and `adapters/observation_packet.py:165–195,235–248` add role demotion and capability intersection before the tested direct components reach the ledger.

The temporal ledger intentionally admits an entire mixed row when one requested channel is finite (`layer0/temporal_evidence.py:26–30,54–73,80–90`). G02 retains the invalid raw NDVI in such an admitted row but then proves that the per-component validator quarantines it. **Any-finite row admission or a packet truth label alone is not reported as a defect.** Likewise, a failed daily record may fall through to generic packet truth classification; G02 invalid-only/missing controls still produce no eligible component after the tested source-aware consumer path. Qualified synthetic diagnostic/experimental visualization remains allowed in G03 and is not treated as improper research use.

## F01-L01 — RECONSTRUCTION is promoted to observed evidence

**Status: current B02 coverage gap; original tested canonical roles repaired, broader role preservation partial.** Normative connection: F01 step 3; AB-DAT-006; AB-ARC-005/006.

G05 uses a fully qualified daily provider row with `ndvi=0.0` and either `role="RECONSTRUCTION"` or `role="OBSERVATION", source_role="RECONSTRUCTION"`. Each is tested through both typed and dictionary adapters and the registered Sentinel2 source route, including source-aware normalization, component validation, ledger insertion and fused feature selection.

All four cases produce packet `observed`, component `observed`, truth `provider_plot_timeseries`, no validation/ledger violations, `state_update_allowed=True`, `diagnostic_only=False`, ledger count 1 and `state_updatable()==[ndvi]`. The actual vegetation feature is `ndvi=0.0`, `diagnostic_only=False`. The original restrictive roles/alias conflicts in G03/G04 supply controls.

The failure is specific: wrappers and packet truth collect the aliases but omit `RECONSTRUCTION` from every demotion set (`layer0/wrappers.py:146–193`; `layer1_fusion/truth_bridge.py:543–571`). The daily branch consequently returns observed provider timeseries (`truth_bridge.py:626–648`). Source-aware evidence normalization also promotes that daily item to observed (`truth_bridge.py:94–118`), and the validator contains no field-level reconstruction invariant. The requirement is to preserve reconstruction as a distinct source role and prevent observational promotion; this result does not assume that all separately qualified reconstruction use must be prohibited.

## F01-L02 — a known quantitative soil string becomes a fused soil feature

**Status: current B01 coverage gap; original bounded-index scalar cases repaired, qualification across quantitative channels partial.** Normative connection: F01 steps 2/4 and accepted-component completion criteria; AB-DAT-005/006; AB-ARC-005/006.

G06 supplies a canonical `SOILGRIDS` packet with valid provider provenance, `soil_sand_pct=40.0` and `soil_clay_pct` varied across zero, finite 30.0, bool, Inf, numeric string, malformed string and missing. It uses the production environment source adapter, not an arbitrary EvidenceItem constructed by the harness. `EnvironmentAdapter.extract_evidence` delegates canonical packages at `adapters/environment.py:26–31`; the shared bridge explicitly maps `soil_clay_pct` and `soil_sand_pct` (`adapters/observation_packet.py:119–122`) and the `SOILGRIDS` source (`:40`).

| Clay input | Component outcome | Actual soil feature |
|---|---|---|
| `0.0`, `30.0` | Admitted, state eligible | Same numeric value, non-diagnostic |
| `True`, `Inf` | Quarantined | Clay absent; valid sand survives |
| `"30.0"`, `"not-a-value"` | Admitted, state eligible, no violations | Same string value, non-diagnostic |
| Missing (`None`) | No clay component emitted | Clay absent; valid sand survives |

Both string cases have ledger count 2, state-eligible clay and sand, `truth_class=geo_provider_context`, and `soil_site_context` containing a non-diagnostic `soil_clay_pct` feature with the original string. Thus this is beyond a transport envelope or truth label: the current numeric admission and selection functions actually accept the component and select a fused quantitative soil feature.

Cause: strict finite qualification is confined to `_BOUNDS`; `soil_clay_pct` is absent (`evidence_validation.py:124–164`). The general branch rejects booleans/nonfinite floats but accepts strings. The source-aware environment branch allows stable soil context (`truth_bridge.py:264–280`); the ledger's structural checks do not reject the string (`evidence_ledger.py:119–139,206–208`). This is a known registered quantitative field (`fusion_rules.py:91–104`), and feature selection takes the highest-confidence value when it is nonnumeric (`:351–365`), yielding the observed non-diagnostic feature. Neither string is coerced to a legitimate numeric scalar; malformed quantitative evidence simply bypasses qualification.

The fix should apply explicit numeric schema/qualification to registered quantitative channels without rejecting legitimate categorical evidence or losing valid sibling components. No additional SAR finding is counted: soil is the stronger registered-field counterexample and keeps the check bounded.

## Reproduction and completion assessment

Run `python /workspace/scratch/de6bc2428cec/review-4157ac1-f01/ledger/probes.py`. It writes only this lane's strict JSON results and manifest. Nonfinite fixture values are encoded as explicit representation objects rather than nonstandard JSON numbers; `allow_nan=False` is enforced. Seven bounded groups complete successfully, including assertions for the corrected controls and the observed counterexamples.

Artifacts: `probes.py`, `results.json`, `executed-file-manifest.json`, this report. Downstream source-context role promotion and reliability cases are owned by the wrapper lane; this report does not duplicate their matrices. This lane supports crediting the direct B01/B02 corrections while withholding full F01 closure because reconstruction provenance and a registered quantitative soil component still reach unqualified observational/feature authority.


---

# Specialist appendix: Wrapper and actual Layer1 admission

# F01 wrapper / typed reliability review — 4157ac1

Candidate `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`, parent `b51616da5a6f67a7a194439485c7aac71c7396ed`. This bounded recheck credits the direct F01-B02/B03 corrections, but reproduces three residual mechanisms at actual supported producer / Layer 1 admission boundaries. All counts below are **EvidenceLedger items**, not state updates, solver observations, optimizer actions, or training samples.

## Corrections demonstrated

- All 40 dictionary/typed cases across `role`, `source_role`, `data_role`, `status_role`, and `truth_class` correctly demote SIMULATED / FORECAST / PROXY / UNAVAILABLE in `ensure_observation_packet` and its immediate ObservationPacket→EvidenceItem adapter. Conflicting aliases and pre-existing typed simulated/fallback status remain restrictive.
- Dictionary explicit reliability infinity, NaN, boolean, malformed, null, negative, and above-one become zero; absence remains the default one. An invalid primary no longer acquires a valid fallback weight. Explicit zero is preserved.
- The typed `ObservationPacket` constructor makes infinity, NaN, boolean, and malformed `reliability_weight` and `qa.scene_score` zero. These constructor fixes are real.
- A real numeric zero survives dataclass JSON serialization and actual evidence admission. Non-finite, boolean, and malformed NDVI values are quarantined in the bounded numeric cases.

These are fresh candidate executions, not results copied from the parent review.

## Residual 1 — source-aware Layer 1 normalization reverses the repaired role/permission intersection (P1; F01-B02)

Actual accepted path: `PerceptionEngineOutput(engine_family=DRONE)` + documented `to_observation_packets(..., data_status=...)` → `wrap_perception` → `PerceptionAdapter` canonical delegation → ObservationPacket adapter → source-aware normalization and admission. This uses an existing mapped numeric variable, `vegetation_fraction=0.2`, real production dataclasses, and no invented metadata keys. Layer 0 runner lines 170–179 use the same default perception wrapper route; the wrapper preserves the typed packet's DRONE source, so the packet adapter maps the evidence family to `drone_structural`.

The immediate adapter correctly emits simulated/estimated/fallback/unavailable with diagnostic=true and state-update=false. Supplying the actual package to the production admission method then runs `normalize_evidence_truth`; its drone branch (`layer1_fusion/truth_bridge.py:374–388`) unconditionally sets observed, production-usable=true, provider-product=true, diagnostic=false, state-update=true. Each case is accepted (1 item, 0 quarantined). For simulated, confidence remains 0.20; for unavailable it remains zero. This proves role/permission promotion, not a physical state change. The unavailable package is unavailable and its envelope is missing; its adapter still accepts it, and the source envelope has no validation violations. The observed control also passes.

The actual fusion run source-normalizes extracted adapter evidence with `source_context=pkg` at `layer1_fusion/engine.py:156–159`, before validation and ledger insertion. Thus the repaired immediate adapter intersection is not preserved through the actual source-aware consumer. Receipt: `results.json.groups.residual_actual_perception_role_consumer`.

## Residual 2 — typed perception producer converts invalid reliability into a qualified positive weight (P1; F01-B03 adjacent boundary)

On that same supported path, `perception/common/packet_adapter.py:160–165` performs `min` / `max` before the repaired ObservationPacket constructor receives the weight. With fixed QA=1 and variable confidence=1, typed output `reliability_weight=inf`, NaN, or `True` becomes packet reliability **1.0**, effective weight **1.0**, and accepted evidence confidence **1.0**. The later constructor only sees an already finite value. Each case is accepted as observed with state-update permission=true. Explicit zero becomes **0.05** and accepted confidence 0.05; the finite 0.4 control remains 0.4. This isolates numeric qualification before clamping/flooring and shows explicit zero inflation at an actual typed producer. Receipt: `results.json.groups.residual_actual_perception_numeric_weight`.

## Residual 3 — native typed sensor QA admits a boolean reliability weight (P1; F01-B03 adjacent boundary)

Actual `NormalizedSensorReading` + `SensorQAResult` inside `SensorContextPackage` → `SensorAdapter` → actual admission method. The existing typed field `reading_reliability=True` becomes evidence reliability `true`, confidence **0.95**, and is accepted (1 item, no quarantine, state-update permission=true). `adapters/sensors.py:68–92` uses it arithmetically, while `evidence_validation.py:62–65` and ledger bounds permit booleans as numbers. Infinity and NaN QA reliability are quarantined, finite/zero controls survive, and an explicit `update_allowed=False` remains diagnostic with state-update=false. Receipt: `results.json.groups.adjacent_actual_sensor_QA`.

## Reproduction and identity

Run from the review directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python platform/wrapper_probes.py
PYTHONDONTWRITEBYTECODE=1 python platform/verify_metadata.py
```

The probe uses the unchanged AST body of `Layer1FusionEngine._admit_evidence_or_quarantine` (`engine.py:807–824`) with production relative imports. Isolation and method source SHA-256 are explicit in `results.json.admission_isolation`. It does not import/start the whole engine. All 12 assertions pass; they assert the stated corrections **and successful reproduction of residuals**, not complete F01 acceptance. Results use strict JSON, with non-finite input receipts represented as strings in objects.

All 56 actually imported candidate source files match Git blobs. The source identity receipt verifies the root review's current **876** file production/config corpus: the original 875 plus exact tracked `layer05_asmae/provenance.py`, staged by the root for a separate dependency. No production file was edited by this lane. The three selected normative plan files (master, execution addendum, task register) match the candidate tree. Master F01 lines 151–177 maps to AB-DAT-005/006 and AB-ARC-005/006 in the supplied R3 extract. F01 has 5 unchecked rows; the full acceptance register has 52 unchecked FA rows. These are register status, not proof implementations are absent. A supplemental local detailed-plan identity mismatch was inspected and excluded from the verdict; it is not a repository defect.

No repository tests, historical implementation audits, or generated production outputs were used as correctness evidence. No provider, service, network, controller, hardware, whole solver, optimizer, or training execution occurred. Normative identities and register receipts are in `plan-results.json`; exact corpus/import identities are in `source-manifest.json`.


---

# Specialist appendix: Water assimilation and history qualification

# F01-B04 water carrier, admission, authority and history verification

Candidate `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`; parent `b51616da5a6f67a7a194439485c7aac71c7396ed`. Executed 20 October 2026.

**The three original counterexamples are repaired within the executed scope. F01-B04 is still incomplete: the newly supported component role does not govern observed authority, and the new reliability fields have fail-open/override behavior.** Component and vector restrictions also have inconsistent scope.

Synthetic, forecast and research model updates are not inherently forbidden. The checks require truthful role/authority and actual admitted-component counts. A modeled update marked ASSIMILATED earns credit; changing several layers from one admitted constraint is expected under correlated optimal interpolation (OI).

## Execution and limits

Run from the bundle/workspace root:

```bash
python review-4157ac1-f01/decision/probes.py
```

The runnable probe uses the actual new `SoilObservationVector`, actual `WaterStateAssimilator`, and actual full `WaterIntelligenceEngine.execute_pipeline` on every variant. Four coherent groups and one bounded history-helper composition executed **38 input variants**, **41 explicit checks**, **33 passing contract checks**, **8 failed contract expectations** (including two replay repetitions of already demonstrated defects), and **0 execution errors**. These are two residual mechanisms with bounded fixtures, not eight independent findings or broad numerical/scientific certification.

`results.json` is strict JSON containing exact inputs, direct prior/posterior/deltas, actual direct and full diagnostics, source lists, counts, full analysis/transition receipts, solver fidelity, authority and untouched-prior checks. Nonfinite input values are converted to descriptive strings only when writing JSON after the native calls.

`executed-source-manifest.json` records **64 exact candidate production source files**, whose Git blob hashes were checked against the pinned staged tree before native execution and rechecked afterward. The two history functions are the **exact unchanged production AST function definitions**, isolated from unrelated decision-module initialization; no body/statement rewriting or mocked carrier/assimilation/runner was used. The helper executes a native import of the actual carrier.

No repository tests, candidate audit reports or candidate generated artifacts were used as correctness evidence. No production-source/Git mutation, network, provider, service, controller or hardware operation occurred. Only authored files in this `decision` directory were written. This is a full **water runner** execution and an isolated history adapter composition, **not a complete durable canonical L3 orchestration**, public-route reproduction, wrapper-to-water proof, independent field observation, training-admission certification or physical action.

The common prior has three layers ending 10/30/60 cm, theta `[.2,.2,.2]`, FC `.3`, WP `.15`, saturation `.45`, residual `.04`, with the same explicit finite weather for every case and no vegetation object. The water runner legitimately advances storage from 120.00 to 114.30 mm before analysis. Reported analysis increments are the actual receipt's post-analysis minus pre-analysis storage; they do not misattribute that weather-driven transition to an observation.

## Original cases: repaired and credited

| Original case and paired control | Actual result on candidate |
|---|---|
| TDR `[.35,.35,.35]`, provenance `['IN_SITU_PROBE_TDR','FORECAST']` | 3 admitted rows; direct posterior `[.3359,.341,.3342]`; full analysis **+89.70 mm**, authority **ASSIMILATED**. It no longer receives OBSERVED. SIMULATED-tagged control has the same model update and ASSIMILATED authority. |
| Satellite `.35`, provenance `['EXCLUDED_SATELLITE_SMAP_SENTINEL1']` | **0** admitted; 1 explicit exclusion rejection; direct returns the unchanged prior; full analysis **0.00 mm**, authority **MODELLED**. Valid satellite control admits 1 and gives `[.265,.2424,.2207]`, **+33.43 mm**, ASSIMILATED. |
| Actual history dictionary with `role='SIMULATED'`, `reading_reliability=0.0`, `reliability_weight=0.0` | Both exact helpers preserve all fields. The actual typed carrier now represents them. Direct and full counts **0**, 3 zero-reliability rejections, unchanged direct prior, **0.00 mm**, MODELLED. The previous metadata-loss finding closes for this composition. |

The carrier genuinely adds role, reading reliability, weight, component roles and component reliabilities (`layer3_water/contracts/assimilation_state.py:32–36`). The helper's `known_fields` genuinely carries all five (`layer3_decision/runner.py:970–990`). The original repair is not being withheld because adjacent cases remain.

## Numeric, zero, fallback and source controls

| Control | Direct result / actual full analysis result |
|---|---|
| Finite observed probe `[.30,.31,.32]` | 3 admitted; posterior `[.292,.3029,.3065]`; **+68.98 mm**, OBSERVED. |
| Legitimate finite zero probe values `[0,0,0]` | 3 admitted; posterior physically projected to `[.0401,.0401,.0401]`, 3 bound corrections; **−90.24 mm**, OBSERVED. Input zero remains present; physical projection is separate from missingness. |
| Probe `[+Inf,NaN,True]` | 0 admitted/3 rejected; unchanged direct prior; **0.00 mm**, MODELLED. |
| Probe `[+Inf,.31,'malformed']` | Exactly 1 admitted/2 rejected; posterior `[.2605,.2929,.2455]`; **+40.05 mm**, OBSERVED. Correlated changes to other layers do not mean the rejected rows were admitted. |
| Finite probe with sigma `0` or `+Inf` | Each has 0 admitted/3 uncertainty rejections; unchanged direct prior; **0.00 mm**, MODELLED. |
| Three invalid probes plus finite satellite `.35` | Probe rejections retained, exactly 1 satellite admitted with actual satellite source; posterior `[.265,.2424,.2207]`; **+33.43 mm**, ASSIMILATED. |
| Thermal `4 C` / forecast thermal `4 C` | Each admits 1 surrogate constraint, posterior `[.1957,.1934,.1968]`; **−3.07 mm**, ASSIMILATED. The forecast source label is retained. |
| Excluded thermal `4 C` | 0 admitted/1 exclusion rejection; unchanged direct prior; **0.00 mm**, MODELLED. |
| Finite zero thermal input | Value survives the carrier. No surrogate constraint because this algorithm constructs one only for differential `>2 C`; 0 rows, **0.00 mm**, MODELLED. This algorithmic threshold is not reported as zero/missingness loss. |
| Forecast satellite `.35` | Source retained as `FORECAST_SATELLITE_SMAP_SENTINEL1`; 1 admitted, **+33.43 mm**, ASSIMILATED. |
| Explicit component reliability zero for probe, satellite or thermal | Each rejects its own supplied rows; counts 0, unchanged direct prior, **0.00 mm**, MODELLED. |
| `reliability_weight=0` alone or both quality fields zero | Each rejects all 3 probe rows; unchanged prior, **0.00 mm**, MODELLED. |

These observations preserve the previously established numeric and finite-zero protections. This lane supplies no evidence warranting reopening the existing R51901/R51902 closures; it does not claim to have re-executed their separate nutrition/support boundaries.

## Remaining mechanism W1: component/global role resolution and authority

**Priority P1; actual typed API and replay-helper composition.** Use the real carrier with default global `role='OBSERVED'`, source `IN_SITU_PROBE_TDR`, profile `[.35]*3`, and **`component_roles={'soil_probe':'SIMULATED'}`**. The component declaration exists in the actual new dataclass; it is not an invented attached field.

The assimilator recognizes this component as simulated (`water_state_assimilator.py:141,148–156`) and legitimately admits 3 model rows. Direct posterior is **`[.3359,.341,.3342]`**. The actual full water runner produces **`[.3288,.3486,.338]`**, analysis **+89.70 mm**, variance reduction **0.885**, accepted source TDR, and **OBSERVED authority**. The explicit OBSERVED component control gives the same numbers. A source-level SIMULATED marker with the same values instead gives ASSIMILATED authority.

The runner (`layer3_water/runner.py:391–400`) checks source strings and global role but **never checks component roles**. Accepted diagnostics retain source labels/counts, not the admitted component's role, so the newly qualified role does not reach the authority decision. Exact helper roundtrip preserves `{'soil_probe':'SIMULATED'}` yet reproduces the same OBSERVED promotion downstream. This is **not** a renewed serializer-loss defect.

**Acceptance:** assign authority from the admitted component's qualified role, or carry qualified admission receipts to the authority selector. This fixture may retain its modeled update/count but must not gain OBSERVED. The true observed component and existing forecast/simulated source controls must keep their truthful behavior.

## Remaining mechanism W2: zero and invalid reliability resolution

**Priority P1 for the demonstrated positive influence from zero/unqualified quality.** All values and sigmas are finite and valid; only the named quality field changes.

| Quality fixture | Actual admitted count / direct posterior / full increment / authority |
|---|---|
| Positive control: both fields `1` | 3 / `[.3359,.341,.3342]` / **+89.70 mm** / OBSERVED |
| **`reading_reliability=0` only**, default weight `1` | **3**, no rejection / same posterior / **+89.70 mm** / **OBSERVED** |
| `reliability_weight=0` only | 0 / unchanged `[.2,.2,.2]` / **0.00 mm** / MODELLED |
| Both fields `0` | 0 / unchanged / **0.00 mm** / MODELLED |
| `component_reliabilities={'soil_probe':0}` | 0 / unchanged / **0.00 mm** / MODELLED |
| Absent weight (`None`), explicit reading reliability `0` | 0 / unchanged / **0.00 mm** / MODELLED |
| **`reliability_weight=NaN`**, explicit reading reliability `0` | **3**, no rejection / positive-control posterior / **+89.70 mm** / **OBSERVED** |

The real carrier defaults both quality fields to `1.0`. The assimilator selects `reliability_weight` whenever it is not `None`; it consults `reading_reliability` only when the weight is explicitly `None` (`water_state_assimilator.py:131–133`). Therefore an explicitly zero reading value is shadowed by the other field's default. The serializer correctly preserves this zero, and the exact typed-history roundtrip repeats the ignored-zero result downstream.

Separately, an actually absent weight (`None`) correctly falls back to explicit reading zero and rejects all rows. A present NaN weight does not take that fallback: `finite_real(NaN)` returns `None` later, but the rejection condition is **`rel is not None and rel <= 0`** (`97–114`). The present invalid quality passes the gate, overriding the effect the missing-weight case correctly preserves. This does not inject a NaN into theta; it permits the same positive gain and influence as qualified reliability 1. There is no rejection receipt and no quality reduction. The invalid-value and invalid-sigma controls show this is specifically the quality path.

**Acceptance:** define one explicit quality precedence/composition contract; preserve either field's explicit zero rather than allowing a default to erase its force, and fail closed for an explicitly nonfinite quality. If one field is intentionally nonbinding annotation, name/document that semantics in the carrier and adapter contract. Keep finite zero *measurements* admissible and retain the successful zero-weight/component-zero controls.

## Additional bounded scope/precedence fixtures for W1 and W2

These are adjacent fixtures of the same **role-resolution (W1)** and **reliability-resolution (W2)** mechanisms, not a third independent finding. Their policy expectation is explicit: a vector-wide hard exclusion/zero cannot be promoted by a component declaration, while a satellite-specific exclusion must not remove a separately qualified TDR profile. This follows F01's no-caller-promotion and per-field qualification requirements; the current carrier does not document an alternative override contract.

| Paired fixture | Actual result |
|---|---|
| Global `role='EXCLUDED'`, no component override | 0 rows/3 exclusions; unchanged direct prior; **0.00 mm**, MODELLED. |
| Same global EXCLUDED plus `component_roles={'soil_probe':'OBSERVED'}` | **3 rows/no rejection**, direct `[.3359,.341,.3342]`, **+89.70 mm**, ASSIMILATED. Global authority check prevents OBSERVED, but the excluded vector's observation rows enter state/covariance. |
| Global weight `0`, component reliability `1` | **3 rows/no rejection**, same posterior, **+89.70 mm**, OBSERVED; paired global-weight-zero control has no influence. |
| Finite TDR `[.35]*3` plus satellite `.35`, sources `[TDR,'EXCLUDED_SATELLITE_SMAP_SENTINEL1']` | **0 rows/4 exclusions**, unchanged direct prior; **0.00 mm**, MODELLED. The satellite-specific restriction removes all 3 unrelated TDR rows. |
| Same physical inputs, sources `[TDR,'SATELLITE_SMAP_SENTINEL1']`, typed `component_roles={'satellite':'EXCLUDED'}` | **3 TDR rows**, direct `[.3359,.341,.3342]`, **+89.70 mm**, OBSERVED. |
| Typed excluded probe plus valid satellite | Exactly **1 satellite row**, 3 probe rejections; `[.265,.2424,.2207]`, **+33.43 mm**, ASSIMILATED. Independent fallback works in this direction. |

`probe_role_override` and `probe_rel` replace vector metadata (`141–142`); global hard restrictions are not composed afterward. Conversely, the probe source scan reads restrictions from **every** provenance string (`144–151`), while satellite/thermal scans filter source families (`174–182,206–214`). Thus component source markers and typed component metadata have different scope. The differing admitted counts and increments are executed results, not deductions from flags alone.

**Acceptance:** define scoped qualified-component records and combine global/component restrictions monotonically at admission. Scope source markers to their actual component before fallback and authority selection. Preserve the paired finite observed controls. If an intended global value is only a default, encode and document that distinct default semantics rather than using an explicit EXCLUDED/zero as an overridable gate.

## History, counts, solver and normative interpretation

Both exact history helpers preserve all new fields through dictionary and dataclass paths; all 3 metadata-preservation checks pass. Only the two pure functions at `layer3_decision/runner.py:942–994` were isolated. Existing durable-history call sites at `1385,1524,2603,2671,2695` were source-traced, not executed through storage. The original history fix is credited at the executed composition boundary; durable reader/writer closure requires a separate actual integration run.

Counts describe actual admitted OI rows, not independent sensors or native measured truths. Count 3 is three layer components; simulated rows can legitimately be counted as model assimilation. `component_excluded_probe_valid_satellite` changes multiple layers because of covariance from the single admitted satellite row, not because rejected probe rows reentered. Every direct prior remains unchanged.

Solver selection still precedes component admission (`layer3_water/runner.py:145–151`), and `solver/solver_selector.py:48–54` uses raw probe-profile presence. Both branches currently execute EMPIRICAL_BUCKET, which every runtime result confirms. This is a static remaining ordering limitation, not a demonstrated different solver or a new numerical-fidelity finding.

Normative basis: master F01 lines **151–177**, particularly step 2 (explicit admitted/rejected components before authority/solver), step 3 (role preservation without caller promotion), and the completion criteria (finite numeric evidence, legitimate zero, authority/counts following actual admitted components). R3 sections **AB-DAT-005 675–677** preserve zero/missingness; **AB-DAT-006 679–681** distinguish observation/prior/reconstruction/forecast/synthetic per field; **AB-ARC-005 738–740** separates diagnostic/update/other authority; **AB-ARC-006 742–744** requires bounded degradation without promotion by fallback.

The candidate repairs all three original repros: forecast promotion, excluded-satellite assimilation and bounded history metadata loss. The two residual mechanisms W1/W2 prevent full F01-B04 closure; broader F01 weather/packet/crop/training boundaries belong to their independent verification lanes.


---

# Specialist appendix: Weather/crop feature consumers

# F01-B01/B02 weather and crop admission verification

Candidate: `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`  
Parent: `b51616da5a6f67a7a194439485c7aac71c7396ed`  
Review date: 2026-10-20  
Disposition: **original numeric and Sentinel-2 scene-role reproductions are repaired; one canonical-weather provenance seam remains open.** This bounded verification does not close the whole F01 family.

## Scope and method

Fresh execution used the candidate's exported production modules through `wrap_environment` → `build_canonical_crop_observations` → `build_crop_evidence_ledger` → `observation_tokens_from_ledger`. The multi-scene case also executed `build_ledger_crop_feature_input`, including cycle selection, engineered feature extraction, and the governed model-input receipt. No production function was monkeypatched.

`probes.py` contains 5 coherent groups, 38 cases and 118 explicit checks. The run completed normally: **111 checks passed, 7 checks failed**. All failures are variants or downstream consequences of the same canonical-weather declaration-loss seam described below. A check count is not a count of independent defects. `results.json` is strict JSON; non-finite input values are represented explicitly for reporting rather than emitted as invalid JSON numbers.

The complete in-memory optical fixture includes a parseable Sentinel-2 provider product identity, sensing and processing dates, namespace, CRS, affine transform, plot polygon, reflectance units, B04/B08, SCL and DATAMASK. Sensing/processing dates are 2026-10-01 through 2026-10-19, all before the review date. Missing raster identity, absent provider fixtures, future cutoffs and F02 eligibility do not explain these results. The environmental fixture supplies exactly the object attributes consumed by the real wrapper. Weather rows and packets carry the same top-level declaration; nested arbitrary role/field-metadata fixtures were not used.

The full Layer-0/orchestrator and `crop_posterior` were inspected only for call-path reachability. Their source forwards the wrapped `evidence_records` into the same canonical crop builder and subsequently uses the same ledger feature-input adapter; the full orchestration, classifier, prescriptions and provider acquisition were not executed. No repository test suite, historical audit report or generated artifact was used as correctness evidence. Earlier authored probe code was adapted, but all results here were produced anew.

`source-import-manifest.json` records all **66 imported production module names / 43 distinct source files**, with exact git-blob and SHA-256 matches to both the candidate git tree and the staged source manifest. Four static-only caller files are separately marked. It also records the probe hash, so an import manifest cannot silently describe a different probe revision.

## Credit for the repaired behavior

| Boundary/cases | Fresh production result |
| --- | --- |
| Boolean B04/B08 reflectance | Rejected as malformed reflectance dtype; zero ledger model-eligible items and zero actual model tokens. |
| Numeric-string, object and complex core reflectance | Rejected; none reaches an admitted ledger token. The source intentionally admits only integer/float reflectance dtypes. |
| Optional boolean B05 reflectance | Entire scene rejected and zero model tokens, despite 16 otherwise valid core pixels. This is conservative whole-scene admission, not successful component salvage. |
| Legitimate boolean DATAMASK / integer categorical SCL | Accepted with 16 valid pixels and one actual token. Boolean support masks are not being confused with physical reflectance. |
| Valid zero NDVI | Preserved as `0.0`, with one eligible ledger item and one actual token. |
| One infinite core pixel / all non-finite core pixels | One bad pixel removes only that pixel (15 remain, one token); all bad core support rejects the scene (zero tokens). |
| Half of boolean DATAMASK false | Correctly leaves 8 valid pixels and one admitted token. |
| Sentinel-2 `EXCLUDED`, `SYNTHETIC`, `PRIOR`, `FORECAST`, `PROXY`, and conflicting `role=OBSERVATION` / `source_role=EXCLUDED` | State update/direct-observation authority follows the restrictive declaration. No actual model token survives. The feature-input caller blocks on no admitted physical evidence. Quality may remain admitted for a simulated/prior raster, but the actual physical evidence/model path remains closed. |
| Weather mean `True`, numeric string, NaN, infinity, absent value | Through the real environmental wrapper and canonical crop builder, all yield empty thermal coordinates in the actual token. The valid optical token remains present; missing weather does not falsely reject the independent optical observation. |
| Weather finite 20 °C / legitimate zero | 20 °C produces `GDD0=20`, `GDD5=15`, `GDD10=10`, `GDD12=8`; zero produces explicit zeros on all four axes, preserved in actual tokens. |
| Direct canonical caller: low/high and explicit GDD | Finite low/high works; boolean low/high and boolean GDD do not contribute; explicit GDD zero remains `GDD10=0`. |
| Wrapped weather `role=EXCLUDED` | Canonical `unavailable` status survives, GDD is absent from tokens and from all five engineered thermal features. |

Source basis: `layer2_veg_int/crop_observations.py:984-998` rejects malformed reflectance dtype; `:1013-1048` computes supported pixels; `:890-919` qualifies thermal scalars; `:1145-1162`, `:1189-1198`, `:1226` and `:1249` demote Sentinel-2 scene authority. `scientific_contracts/numeric.py:10-25` explicitly rejects boolean and numeric-string scalars while retaining legitimate zero. The ledger's physical evidence gate and the token/feature consumers were exercised, so these conclusions do not rest only on output flags.

## Remaining blocker: canonical weather re-promotes unavailable input

**One provenance-normalization seam remains at `layer0/wrappers.py:89-107`.** The newly added canonical-weather status derivation ignores the daily record's explicit `data_status`; it also selects the first nonempty role alias. This differs from the packet normalizer in the same file, which honors explicit status and inspects all role aliases (`:144-160`). An unavailable packet can therefore be paired with an observed canonical record that still carries the unavailable packet's evidence identity.

The minimal production-wrapper reproduction supplies:

```python
{"date": "2026-10-19", "temp_mean_c": 20.0, "data_status": "unavailable"}
```

The matching packet is normalized to `unavailable`, but the wrapper's `evidence_records[0].data_status` is `observed`. The crop consumer then computes `GDD10=10` (and the other three thermal axes), and the admitted optical model token contains those values. Adding `role=OBSERVATION` does not repair the ignored explicit status. A same-seam conflict, `role=OBSERVATION, source_role=EXCLUDED`, likewise yields an unavailable packet alongside an observed canonical weather record and nonempty token thermal coordinates.

The direct consumer control receives the same unavailable-status-only row without wrapper conversion: `crop_observations._gdd_coordinates_until` rejects it and the actual token has `{}` thermal coordinates. The repaired `role=EXCLUDED` wrapper control also yields `{}`. This isolates the failure to declaration loss during canonical weather transport, rather than to the direct consumer's explicit unavailable-status check or to optical eligibility.

The actual downstream feature-input effect was verified on six distinct, admitted optical scenes and six daily weather rows:

| Weather declaration supplied to wrapper | Packet statuses | Canonical weather statuses | `sos_gdd` | `pos_gdd` | `eos_gdd` | `growth_rate_per_gdd` | `senescence_rate_per_gdd` |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Observed | All observed | All observed | 20 | 40 | 50 | 0.0147857143 | -0.0135714286 |
| `role=EXCLUDED, data_status=unavailable` | All unavailable | All unavailable | null | null | null | null | null |
| Only `data_status=unavailable` | All unavailable | **All observed** | **20** | **40** | **50** | **0.0147857143** | **-0.0135714286** |

The observed and unavailable-status-only variants produce the **same model-input receipt hash**: `dfabade60453db5ef44debc5fd8fe4e25e34b5ca2b5fd936262a8818fcc3daa6`. Each variant has six eligible optical tokens, so their physical scene count is held fixed. The excluded-role variant has a different receipt and no thermal values. The failure therefore affects the actual ledger-bound engineered input, beyond a mislabeled weather record.

Reachable production chain, with the full orchestrator static-only: `orchestrator_v2/runner.py:915-930` prefers canonical `evidence_records`; `:1468-1472` obtains coarse weather; `:112-123` forwards weather to the canonical builder. The exercised consumer at `crop_observations.py:890-919` sees the promoted status; environmental coordinates enter tokens at `scientific_contracts/crop_model_input.py:592-617`; `features/ledger_crop_features.py:152-176` consumes selected tokens and extracts the engineered vector. `crop_posterior.py:719-755` invokes that governed adapter in production.

This conflicts with F01 implementation step 3 (roles survive typed/dictionary adapters without caller promotion), step 4 (weather/crop qualification), and R3 AB-DAT-006 provenance distinction / AB-ARC-006 bounded degradation. AB-DAT-005 zero/missingness and AB-ARC-005 authority separation remain part of the scope and receive the positive credits above. The residual seam prevents claiming closure of B02 across canonical weather transport.

**Impact bound:** the six-scene receipt's completeness is `0.3333333333333333`, so `model_execution_eligible` is still false. `publication_eligible` is false in all three cases, with domain/calibration/coverage and completeness blockers. No species classifier output, training update, prescription or physical state assimilation was observed or claimed. The demonstrated defect is unavailable weather re-entering actual model tokens and engineered input values; the later gates still constrain the particular fixture.

Synthetic/forecast weather-role controls were also recorded. Their status survives the wrapper as simulated/estimated and they can contribute thermal context. Arithmetic using forecast or scenario forcing is not by itself a defect, so those controls are not counted as additional blockers or as proof of observed authority promotion.

## Reproduction and completion boundary

From `/workspace/scratch/de6bc2428cec`:

```bash
python review-4157ac1-f01/ownership/probes.py
```

The script writes `results.json` and `source-import-manifest.json` only under this review's `ownership` directory and prints the compact check totals. It deliberately returns a normal exit status when an expected review check fails; the seven failures are explicit in strict JSON rather than hidden by an exception. Unexpected production exceptions stop execution. The expected no-evidence `ValueError` from the real feature-input caller is captured only when its exact message matches.

No production source, git state, repository suite, network, external service, provider or hardware operation was performed. This completes the assigned bounded weather/crop verification; unproved metadata conventions, every possible alias, training systems and full end-to-end prescriptions remain outside the claim.


---

# Specialist appendix: Weak and validated supervised training admission

# F01 training admission review — candidate 4157ac1

Candidate: `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`; exact parent: `b51616da5a6f67a7a194439485c7aac71c7396ed`.

The original B05 malformed-estimate weight defect and B06 four-continuous-target/confidence writer defects are repaired in the exercised boundaries. Training admission is still incomplete: the changed Layer 1 consumer raises `NameError` on valid weak labels, and actual writer-generated validated candidates still accept malformed numeric eligibility diagnostics. These are separate conclusions: successful exporter qualification does not establish successful downstream consumption.

## Reproduction and evidence

From `/workspace/scratch/de6bc2428cec`:

```bash
python review-4157ac1-f01/trajectory/probes.py
python review-4157ac1-f01/trajectory/probes.py --parent
```

Both commands completed with exit status 0 and no harness errors. The candidate run executes 19 exporter/consumer cases, 36 validation-writer cases, 13 candidate-gate/comparator cases, and 5 bounded legacy read cases plus their genuine approved seed. The parent control freshly executes six exporter/consumer and six writer cases using exact-parent source; previous reports/results are not evidence.

`results.json` and the fresh `parent-reproduction/results.json` contain the observations. Nonfinite values are tagged in these strictly serialized JSON documents. Private JSONL ledgers preserve the actual production writers' output, including their permissive nonfinite JSON representation where applicable. Every normal writer-chain approval is emitted by production code.

`source-manifest.json` verifies every staged candidate production file (876 after the parent reviewer supplied an exact production dependency) against its Git-tree blob, records SHA-256 and sizes, and distinguishes imported source from explicit static evidence. The parent reproduction independently verifies its 875 staged files. This establishes exact bytes, not complete function or branch coverage. The script does not modify source, use production ledger paths, or call services, providers, networks, or hardware. `AGRIWISE_ARCHIVE_PILOT_MODE=false` is set in the probe process. No repository tests, historical audits, or generated repository artifacts are used as correctness evidence.

Normative basis is the F01 master plan, lines 151–177: qualify provenance/numeric evidence at admission, apply the same rule to training, prevent NaN/infinity/bool/malformed values from changing state or training weight, and retain legitimate zero. The referenced R3 requirements are AB-DAT-005/006 and AB-ARC-005/006. `normative-manifest.json` identifies and hashes those two normative inputs. Unit observations below identify qualification scope; they do not add AB-DAT-007 as a new F01 acceptance criterion.

## Repairs credited

| Boundary | Fresh exact-parent result | Candidate result |
|---|---|---|
| Exporter NaN, infinity, boolean weak state estimates | Each label has weight `0.30`; actual L1 evidence also has value `0.30` | Each label has weight `0.0`, confidence `0.0`, and an invalid-state reason |
| Actual writer chain: NaN/bool/malformed-string vigor | Production approval and one validated sample | `ValueError` before a validation-event row is appended; no sample |
| Actual writer chain: boolean confidence | Production approval and one validated sample | `ValueError` before a validation-event row is appended; no sample |
| Legitimate zero target | Approved zero vigor sample | Approved zero samples for vigor, canopy_water, salinity_stress, and yield_observed |

`exporter.py:153–194` qualifies state estimate, uncertainty, retro score, and BMA disagreement through `finite_real`. Supplementary NaN/bool uncertainty, string retro score, infinite BMA disagreement, and numeric-string estimate fixtures all receive zero exporter weight. The helper rejects bool and nonfinite values without treating zero as missing.

`schemas.py:83–101` rejects malformed confidence and the four declared continuous targets. `dataset_builder.py:169–180` independently requalifies confidence and those targets on replay. The bounded legacy controls confirm that malformed continuous values and boolean confidence are excluded by the read side too.

Legitimate categorical/event targets are preserved: `crop_stage='flowering'`, `irrigation_event=True` with a matching model comparator, `harvest_event='harvested'`, and `biotic_confounder='high'` all traverse the actual writer/candidate/replay path to samples. Zero confidence, finite contradiction, synthetic-source, 1m, visual-only, and weak-label-as-truth controls produce no training samples. This review does not require categorical events to become finite continuous measurements.

## R1 — Introduced actual consumer regression: undefined numeric helper

**High confidence; introduced by this candidate.** `layer1_fusion/adapters/asmae_adapter.py:414,416` calls `finite_real` without any import or definition in that module. For both legitimate weak estimate `0.0` and `0.5`, the actual exporter returns weight `0.30`, but the actual `ASMAEAdapter.extract_evidence` raises `NameError: name 'finite_real' is not defined`. The same fresh parent composition returns L1 training-weight evidence of `0.30` for both controls.

This is an integration failure, not successful rejection of malformed data. The exception occurs for nonempty weak labels whenever `asmae_training_allowed` passes; the method aborts before returning its evidence list. Malformed labels also encounter the exception, even when the exporter correctly zeroes their weights. The shadow-mode and no-scenes controls do not enter the consumer's training branch.

The runtime composition is actual exporter → actual L1 adapter. The real engine caller at `engine.py:1576–1600`, invoked from `engine.py:326`, is statically traced and recorded in P5. The full upstream ASMAE engine is not executed; no missing-dependency stub or copied production function is substituted. No claim is made that these fixtures were generated by the full engine.

Repair direction: provide the shared helper through a real module import, then repeat the valid-zero/finite consumer controls along with malformed labels. Exporter-only success cannot close this regression.

## R2 — Residual numeric qualification gap in actual training eligibility

**High confidence; remaining preexisting mechanism, not a new B06 target-schema regression.** With a valid finite external target/confidence and complete lineage, the actual chain

`record_asmae_run → add_validation_event_to_ledger → ValidationEvent → check_disagreement/build_learning_candidate → production candidate_update → replay → build_validated_training_view`

emits an approved candidate and one sample for each of these diagnostic inputs:

- Uncertainty `NaN`, negative infinity, or `False`.
- Retro mean score `NaN`, positive infinity, or `True`.
- Selected resolution `NaN`.

The generated record sequence is `asmae_run, validation_event, disagreement_report, candidate_update`; the final candidate row says `learning_candidate_status='approved'` and `eligible_for_asmae_learn=true`. These approval rows are not handmade. Candidate uncertainty/retro values are retained in `results.json`, including boolean conversion to numeric 0/1 and nonfinite tags.

`candidate_builder.py:75–76` compares resolution without qualification. At lines 110–143 it converts uncertainty/retro with `float`, then applies only an upper uncertainty threshold or lower retro threshold. NaN comparisons do not block; negative-infinite uncertainty passes; booleans become valid-looking numbers. Numeric strings also normalize and pass in the observation fixtures; that is reported as behavior rather than treated as a defect without an explicit policy banning such normalization.

The same numeric-gate mechanism includes the comparator side of disagreement. A finite target `1.0` against finite model vigor `0.0` correctly yields a contradiction and no sample. Changing only the model raster value to NaN produces no contradiction, production approval, and a sample. `disagreement.py:81–96` computes the model mean without finite qualification; lines 188–205 qualify only the external target before `abs(asmae_val - validated_val) > threshold`. This shows a malformed comparison input changing training admission even after B06 repairs the external target.

The boundary demonstrated is admission to the validated training view. No optimizer is run and no claim is made about a fitted model, parameter update, or empirical crop outcome.

## Target registry and read-defense scope

P5 records all eight schema-allowed targets and the three duplicated continuous sets in schema, disagreement, and dataset builder. All three list exactly `{vigor, canopy_water, salinity_stress, yield_observed}`. They agree with one another but do not form a shared type/unit registry. `observed_unit` is stored by the writer, is not used for these admission decisions, and is not included in the resulting sample.

The allowed `biotic_confounder` target has an explicit numeric difference threshold in `disagreement.py:15`; the ASMAE state descriptors describe `biotic_confounder_risk` as unitless `[0,1]`. Its qualitative `high` control remains legitimate. However, a `biotic_confounder` validation supplied with numeric unit `fraction` and observed value NaN or `'not-a-number'` is also approved by the actual writer chain and appears unchanged in a sample. This is evidence that the accepted target's numeric versus categorical form is not qualified by a typed/unit-aware registry. It is not a claim that every biotic category should be continuous, nor that arbitrary target aliases are accepted by the current writer. Wrong-unit vigor (`kg/ha`) and missing-unit yield controls are accepted too; they bound the scope of the finite-number fix without establishing a new F01 unit-conversion requirement.

The five legacy cases clone the valid seed ledger produced by the actual writer chain and mutate only the validation-event target/confidence fields. Approval rows are asserted byte-for-value unchanged. They test read-defense parity, not current-writer acceptance. Four malformed continuous/bool-confidence fixtures are excluded. A confidence `2.0` fixture is rejected by current `ValidationEvent` but passes the replay builder because its new guard checks only finite and positive, without the writer's upper bound of 1. This is a bounded remaining migration/read-defense gap. No handmade approval is used to claim writer bypass.

## Assessment

B05 has a verified exporter repair plus an introduced consumer regression. B06's original four-target/confidence acceptance defect is repaired, with valid zero and categorical controls preserved. F01 training admission cannot yet be considered complete because remaining candidate/comparison numeric inputs can generate approved validated samples. Registry/type/unit and legacy-range observations delimit the repair's coverage; they do not establish optimizer or trained-model effects.


---

# Specialist appendix: Contained RF/MESIA internal qualification

# F01-B07 RF/MESIA qualification — candidate 4157ac1

**Verdict: partially repaired; one numeric admission residual remains.** The candidate closes the original full-bridge NaN/Inf/bool SNR and documented non-SENSING role cases, and rejects invalid typed innovation/support. However, `ASMAEObservationOperator.create_innovation` converts an explicitly invalid typed covariance into `0.25`; the actual spine admits that replacement, the adapter grants state authority under the explicit internal qualification fixture, and the actual dispatcher persists it as `QUEUED`.

Candidate: `4157ac1d51d83f75f3379c13741fc9bc77b4f4fe`. Parent: `b51616da5a6f67a7a194439485c7aac71c7396ed`.

## Evidence and reproduction

Run from the review directory:

```sh
python protocol/qualification_probes.py
```

The authored runner uses the staged candidate source and `git-tree.json`; it verifies every one of the 876 staged files against both the candidate Git blob and SHA-256. All 176 production MESIA Python files in the candidate tree are present. The nine repository MESIA test files are intentionally excluded. The run loads 202 real candidate modules with files and records each actual import's path, Git blob and SHA-256 in `source-import-manifest.json`; it also hashes 172 external file-backed imports. There are no package stubs or production source modifications. A post-execution check confirmed all 876 source file hashes unchanged and no extra source files. Import inventory is not statement coverage.

Fresh evidence comprises `results.json`, `execution-output.txt`, `source-import-manifest.json`, the generated `private_captures/` integrity fixture, and the actual `private_queue/` receipts. No repository tests, audits, generated artifacts or prior review outputs were used as behavioral proof. The earlier qualification runner supplied code structure only.

The 74 bounded cases form three compositions:

| Composition | Cases | Actual path |
|---|---:|---|
| Packet numeric admission | 15 | `RadioObservationPacket → NativeFeatureExtractor → BehaviourLikelihoodEngine → MesiaAgriBrainBridge → operator → spine → adapter → dispatcher` when an event exists |
| Typed innovation/support/covariance | 36 | `BehaviourLikelihood → ASMAEObservationOperator → Layer0EvidenceSpine → MesiaAsmaeAdapter → dispatcher` when an event exists; four direct-spine controls preserve raw covariance |
| Roles and containment | 23 | Full packet bridge with enum/string roles, calibration/epoch combinations, and qualified/unqualified capability controls |

Strict JSON encodes nonfinite inputs as explicit `{ "nonfinite": ... }` objects. Ten recorded invariant checks yield nine passes and one failure, `invalid_covariance_contained`. The runner exits successfully when its stable repair/containment controls hold, while retaining this failed qualification invariant in `results.json`; process success is not an all-clear verdict.

Normative basis: master F01 in `sr-team-review/plan/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md` lines 151–177, especially qualification at every admission boundary, preserving zero/missingness, source roles, and no NaN/Inf/bool effect on state or training weight. `current-plan-review/R3_current_scientific_sections.txt` supplies AB-DAT-005 (zero/missingness), AB-DAT-006 (field provenance), AB-ARC-005 (factorized authority), and AB-ARC-006 (bounded degradation without fallback promotion).

## Canonical residual: invalid covariance becomes an admissible default

**Finding F01-B07-R1 — open, P2 contained admission contract residual.** With a real `BehaviourLikelihood` carrying `innovation=0.0`, `support=1.0`, and `covariance=NaN`, the production operator produces `observation_variance=0.25`. It does the same for positive/negative infinity, booleans, a numeric string and a malformed string. All seven receive the same downstream outcome.

| Case label in `groups.typed_operator_spine_adapter` | Operator variance | Spine | Adapter state authority | Actual consumer |
|---|---:|---|---|---|
| `covariance_nan` | 0.25 | ADMITTED; usable | true | `admitted_for_assimilation`; persisted QUEUED |
| `covariance_positive_infinite`, `covariance_negative_infinite` | 0.25 | ADMITTED; usable | true | `admitted_for_assimilation`; persisted QUEUED |
| `covariance_boolean_true`, `covariance_boolean_false` | 0.25 | ADMITTED; usable | true | `admitted_for_assimilation`; persisted QUEUED |
| `covariance_numeric_string`, `covariance_malformed_string` | 0.25 | ADMITTED; usable | true | `admitted_for_assimilation`; persisted QUEUED |
| `direct_spine_covariance_nan`, `direct_spine_covariance_positive_infinite`, `direct_spine_covariance_boolean` | Raw invalid input retained | ABSENT; unusable | no event | dispatcher not called |

The relevant exact-source chain is:

- `services/agribrain/mesia/assimilation/asmae_operator.py:75–81`: `finite_real` correctly returns `None` for the invalid input, but the ternary at line 80 maps every `fin_cov is None` to `0.25`, conflating explicit invalid evidence with the optional missing-covariance default.
- `services/agribrain/mesia/assimilation/layer0_spine.py:74–99`: finite, positive proposal covariance passes. The direct-spine controls show this gate itself rejects the raw bad values.
- `services/agribrain/layer05_asmae/adapters/mesia_adapter.py:37–59`: a usable proposal plus the explicit internal qualification flag yields `state_update_allowed=True`.
- `services/agribrain/layer05_asmae/observation/dispatcher.py:232–299`: the actual consumer checks event authority, adds the event to pending admission and persists `status=QUEUED`. Each row's `consumer.receipt` and `consumer.persisted_queue_record` contains the actual return and on-disk record.

This is an invalid-input fallback admission defect. The positive finite model parameter `0.25` is not inherently invalid; the problem is the unmarked replacement of explicitly invalid covariance before qualification and authority. Absent covariance also receives `0.25` in `covariance_missing`, recorded separately rather than used alone as proof of this defect. Zero/negative covariance are rejected by this implementation's explicitly declared strictly-positive-variance gate; this report does not impose that restriction on all covariance/noise models.

A targeted repair should retain explicit invalid-covariance rejection through operator, spine and adapter. If a missing covariance legitimately uses an established model default, distinguish that case from malformed/nonfinite/bool evidence and preserve its default/model provenance. Re-run this exact composed path; fixing the spine alone is insufficient because it sees the sanitized replacement.

## Repairs and controls credited

| Boundary/control | Fresh candidate outcome |
|---|---|
| Full-bridge SNR NaN, ±Inf, true/false, missing, numeric/malformed string, list | No state-authorized event. Standard cases are ABSENT with innovation `None`, support `0.0`. A malformed Wi-Fi SNR combined with a noise-floor feature raises `ValueError` before event generation. |
| Legitimate zero SNR | ADMITTED, innovation `-22.0`, state authority true and private queue receipt under explicit internal qualification. Zero is not treated as missing. |
| Legitimate zero innovation | `finite_zero_innovation` and typed controls preserve `0.0`, admit it and serialize it as zero in strict results. |
| Typed invalid/missing innovation | ABSENT, no event; finite negative innovation remains admissible. |
| Typed missing/zero/negative/nonfinite/bool/string support | ABSENT, no event. Missing/zero support is not promoted into synthetic observation support. |
| Explicit documented CONTEXT, TRANSPORT, NEGATIVE_CONTROL, TEACHER, SENTINEL, GEOMETRY_AUTHORITY, EVENT_LEDGER | ABSENT, unusable, no event, despite the same finite signal, explicit valid calibration/epoch and matching qualified capability used by SENSING. This closes the original role reproduction. |
| Enum SENSING and CONTEXT | Same results as their string values. |
| Omitted calibration/epoch or calibration false | INVALIDATED, no event. |
| Calibration true, epoch false | QUARANTINED, no event. |
| Valid SENSING without registered capability | Spine ADMITTED, but contained event has `state_update_allowed=False`; actual dispatcher returns `abstained_uncalibrated` and persists ABSTAINED. |
| CONTEXT combined with invalid calibration/epoch or absent capability | Remains blocked; calibration/epoch failure status is retained where applicable. |

The private dispatcher recorded 20 files: 19 QUEUED and one ABSTAINED; zero COMMITTED. This comprises legitimate positive controls, the seven invalid-covariance cases, the optional missing-covariance case, and the adjacent role compatibility observation.

`role_arbitrary_dotted_suffix` records that malformed `CONTEXT.SENSING` is accepted as SENSING because normalization uses the final dotted token. Comma/pipe combinations and UNKNOWN are blocked, and an empty Wi-Fi role uses the registry's SENSING default. The dotted suffix result is an **adjacent compatibility observation only**, not a separate counted finding: this review did not establish a documented producer/schema for that malformed tag. It does not diminish the clear repair credit for every valid documented excluded role.

## Limits and scientific meaning

The only acquisition artifact is a private generated SigMF byte fixture with metadata and data digests verified by the real ingest/integrity implementation. The runner uses a built-in calibration ID and explicit `is_calibration_valid=True`, `is_epoch_active=True`, and an all-gates matching QUALIFIED capability to exercise an internal admissible path. Those are API fixture conditions, not independent physical calibration or metrology evidence. No live radio, hardware, network or production service operation occurs. No blanket restriction on synthetic research evidence is inferred.

The visible service call in `services/agribrain/mesia/service.py:2628–2642` explicitly passes calibration and epoch false; the bridge and spine also default both false. The fresh defaults controls confirm that containment. The residual therefore demonstrates a reachable trusted internal typed boundary and actual private dispatcher admission, not that the visible service has deployed authority or that an external user can access this path. P2 reflects this observed containment and the absence of demonstrated posterior/training impact; the master F01 workstream remains designated P0 in the normative plan.

An `ObservationEvent` with state-update authority and a persisted QUEUED receipt are evidence of admission only. The event does not contain a numeric innovation vector/covariance for an EnKF update. No ensemble filter, lease worker, `commit_assimilation`, canonical posterior mutation, or training exporter was invoked. Training authority stays false in these events. The report makes no claim of actual posterior movement or positive training weight.

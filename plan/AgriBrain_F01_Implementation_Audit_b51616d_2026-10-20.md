# AgriBrain F01 implementation audit — b51616d

Review date: 20 October 2026. Repository: webClone/AgriWise. Candidate and main at verification: `b51616da5a6f67a7a194439485c7aac71c7396ed`. Parent: `40315d95ff875914bd2f83cd1e75d88fdae859ff`.

## Decision

**Continue implementation within F01. Credit the completed slices, but keep F01 full acceptance open.** The patch correctly strengthens the temporal numeric gate, preserves tested explicit zero reliability, and prevents tested simulated/synthetic probes from receiving OBSERVED water authority. Those changes do not yet establish the master plan's universal admission contract across weather, crop, RF and training consumers.

This review consolidates the remaining evidence into **seven groups**, rather than counting overlapping counterexamples from different reviewers as separate defects. Several involve unchanged consumers; they are remaining F01 work, not seven regressions introduced by this commit. The user's delivery described implementation progress and retained open acceptance; this report does not attribute a claim of completed package acceptance to that delivery.

The previous R51901/R51902 closures are retained in their reviewed software scope. Five relevant production files remain Git-blob identical to the parent; this is a source-continuity check, not a fresh rerun of those runtime/hydraulic cases. All **52** package full-acceptance rows remain open, with zero checked. No package register or production file was changed.

## Evidence, method and limits

The review used the candidate's production source, the three normative plan documents and the supplied R3 monograph. Repository tests, historic audit reports, generated stores and reported pass counts were excluded as correctness evidence. The reported 532-test result is a user-provided claim, not a result independently rerun here.

The commit changes four production modules, one repository test and two prior review documents. The four production modules compile cleanly. An exact-source working corpus contains **875 production/configuration files**; each file matches its candidate Git blob. This count describes staged dependencies and inspection coverage, not 875 fully exercised files.

Six workstreams were assigned. Three reviewers completed their final reports independently; root finalized three narratives from their existing source-verified scripts and results after final-summary interruptions. Six appendices retain lane-specific scope and controls. A fresh reconstructed-layout replay ran seven authored commands across those six lanes; the accompanying replay receipt and observation checks identify exactly what reproduced. The separate Git-object materializer was syntax/layout checked, not run against a second complete Git checkout.

Most compositions import actual modules normally. Two bounded seams execute unchanged production AST definitions to isolate unrelated application initialization: Layer1's admission method and the water-history serialization helpers. This is explicitly narrower than starting the full fusion service or executing a durable end-to-end L3 history run. The water lane also executes the actual full WaterIntelligenceEngine. The supervised-training lane executes real event/schema/writer/candidate/view code in private ledgers; it never trains a model. RF fixtures satisfy explicit internal capability/calibration conditions, not physical calibration.

All execution used local inert fixtures. No production source or Git mutation, live service/provider call, controller, radio, drone or field hardware operation occurred. GitHub connector reads retrieved source metadata only. Finite eligible timestamps, scope and provenance controls keep the focus on F01; no F02 temporal-cutoff finding is inferred.

## Repair credit and claim disposition

| Delivery claim | Independent result | Disposition |
| --- | --- | --- |
| Temporal numeric qualification uses finite_real | Invalid-only NaN/Inf/bool/string records reject; finite zero and .45 admit with complete provider metadata | Verified bounded repair |
| Wrapper role aliases recognize simulated/synthetic/estimated/excluded roles | Individual role/source_role/data_role cases demote as intended, including typed controls | Verified; conflicting aliases and later consumers remain incomplete |
| Explicit zero reliability survives | Reading reliability0 and weight0 produce effective weight0; zero measurement survives round trip | Verified |
| Excluded probe observations reject | Three excluded probe components reject without analysis increment | Verified for this probe path |
| Synthetic/simulated water probes do not confer OBSERVED | They can update modeled state but yield ASSIMILATED authority | Verified; legitimate research/model updates are not inherently forbidden |
| Universal F01 admission and authority | Quantitative components, truth fast paths, water carriers, crop/weather, training and internal RF retain gaps below | Partial |
| Existing strong typed observation guard | Invalid quantitative value/variance rejects; valid zero round trips | Working control; not universal coverage |
| F01 / all package full acceptance | F01 task rows and all52 package-FA rows remain open | Correct register state |

A mixed record with valid EVI=0 and invalid NDVI can legitimately pass a record-level any-finite predicate. The required repair is component qualification and truthful permissions, not discarding every valid sibling. Similarly, storing a raw value in an envelope is not itself proof that a solver or training consumer accepted it.

## Consolidated findings

### F01-B01 — P1: quantitative component qualification is incomplete

**Observed behavior.** Actual packet-to-evidence admission accepts NDVI booleans and a malformed NDVI string as observed, confidence1 and state-update eligible. With a valid EVI sibling, the temporal record predicate is legitimately satisfied, but the bad NDVI receives no validator violation. Separate actual weather admission accepts boolean precipitation. The crop observation builder casts boolean B04/B08 reflectance arrays into floats, creates observed NDVI0 at reliability.95, and exports one model token. Boolean temperature also produces a crop thermal/GDD contribution.

**Boundary.** This proves actual Layer1 admission and actual crop-feature/token production. It does not demonstrate a full fusion posterior, crop classifier decision or prescription. NaN/Inf Layer1 controls correctly quarantine; all-nonfinite crop arrays correctly yield unavailable output. Boolean QA masks and categorical fields may be legitimate and must not be rejected globally.

**Cause.** The component validator checks floating nonfinites and numeric bounds without a target-specific finite-real contract; malformed strings can skip numeric checks. Crop reflectance and thermal code coerce before qualifying the physical quantity. See [layer1_fusion/evidence_validation.py:L119-L148](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer1_fusion/evidence_validation.py#L119-L148), [layer1_fusion/adapters/observation_packet.py:L171-L218](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer1_fusion/adapters/observation_packet.py#L171-L218), [layer2_veg_int/crop_observations.py:L869-L905](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer2_veg_int/crop_observations.py#L869-L905) and [layer2_veg_int/crop_observations.py:L960-L972](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer2_veg_int/crop_observations.py#L960-L972).

**Acceptance.** Qualify each quantitative component before permissions, feature construction and ledger admission. Retain valid sibling zeros, reject malformed numeric components with explicit reasons, and preserve schema-defined flags/categories. Numeric-string conversion requires an explicit provider normalization policy, not incidental Python coercion.

### F01-B02 — P1: restrictive roles can be promoted across adapters and truth fast paths

**Observed behavior.** Conflicting aliases such as role=OBSERVED plus source_role=SIMULATED or data_role=UNAVAILABLE remain observed and pass actual Layer1 admission with state-update permission. In the complete daily-provider fixture, individually correct wrapper outputs for SIMULATED, SYNTHETIC, PRIOR, FORECAST, EXCLUDED and REJECTED are subsequently classified as observed/state-update eligible by the actual truth helper and packet adapter. Validation reports no violations. A USER_OBSERVATION prior/forecast truth path also renames status observed, although its state-update permission remains false.

Canonical weather records set observed-current classification even for explicit non-observation roles; that path retains forcing-only/state-update-false limits. Actual weather-to-crop thermal extraction then consumes excluded weather. The Sentinel2 crop builder similarly labels explicitly synthetic/excluded scene fixtures observed and produces observation/model tokens.

**Boundary.** Daily-statistic confidence ceilings survive: simulated.2, estimated.75, excluded0. Prescription/scientific-surface authority remains false there. Weather forcing-only limits also survive. These are role/admission failures, not proof that every downstream use gains full authority. Complete-provider contradictory fixtures test accepted compatibility shapes; they are not evidence that a public or native provider naturally emits that combination. Nested/per-band metadata cases without a demonstrated schema are not extra findings.

**Cause.** First-truthy alias selection ignores other restrictions; special-case source truth runs before role exclusions; generated crop records overwrite rather than carry input qualification. See [layer0/wrappers.py:L54-L111](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer0/wrappers.py#L54-L111), [layer0/wrappers.py:L132-L178](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer0/wrappers.py#L132-L178), [layer1_fusion/truth_bridge.py:L542-L564](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer1_fusion/truth_bridge.py#L542-L564), [layer1_fusion/adapters/observation_packet.py:L132-L160](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer1_fusion/adapters/observation_packet.py#L132-L160) and [layer2_veg_int/crop_observations.py:L1147-L1184](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer2_veg_int/crop_observations.py#L1147-L1184).

**Acceptance.** Resolve conflicting metadata monotonically or reject it. Source identity, provider flags and calibration must not promote restrictive component roles. Carry OBSERVATION/PRIOR/RECONSTRUCTION/FORECAST/SYNTHETIC qualification into generated features and objective-specific permissions. Qualified forecasts may serve scenario forcing; they must not become observed evidence.

### F01-B03 — P2: malformed explicit reliability becomes full reliability

**Observed behavior.** Wrapper reading reliability NaN, Infinity, True or a malformed string is treated as absent and defaults to1. Actual Layer1 cases with invalid explicit reliability admit observed confidence1/state-update-enabled evidence. Separate wrapper/training/weather probes reproduce the same mechanism.

**Boundary.** Legitimate explicit0 is preserved correctly. Typed infinite reliability can be quarantined by the later validator. The failure is the dictionary normalization path laundering an invalid supplied value into a healthy default. Effective weighting's existing multiplication of QA and reliability is not separately classified as a defect.

See [layer0/wrappers.py:L297-L333](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer0/wrappers.py#L297-L333) and [layer0/observation_packet.py:L311-L315](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer0/observation_packet.py#L311-L315).

**Acceptance.** Distinguish absent, invalid and finite-zero quality. A missing default may be policy-qualified; malformed supplied reliability must reject or contribute zero with a diagnostic receipt. Do not silently convert it to1.

### F01-B04 — P1: water component provenance and history qualification are incomplete

Three actual reproductions establish this group:

| Fixture / actual consumer | Result | Limit |
| --- | --- | --- |
| Probe .35 with IN_SITU_PROBE_TDR plus FORECAST provenance; full water engine | Three admitted components, OBSERVED authority, approximately +89.70mm analysis increment | Forecast contribution itself is not forbidden; observed promotion is wrong |
| Explicit EXCLUDED_SATELLITE_SMAP_SENTINEL1 source, .35 value/.04 uncertainty; actual assimilator and full water engine | One accepted component, no rejection, approximately +33.43mm analysis increment, ASSIMILATED | Actual state mutation from excluded component |
| History dictionary with three .35 probes, roleSIMULATED and reliability/weight0; actual history helpers then full water engine | Serialization retains extras; deserialization loses them; three accepted/OBSERVED, approximately +89.70mm increment | Isolated helper composition, not a full durable history/wrapper-to-water run |

The changed probe role gate works for tested EXCLUDED/SIMULATED/SYNTHETIC source tags. It does not qualify the satellite branch equivalently, and heuristic source lists omit forecast provenance. The typed SoilObservationVector lacks the carrier fields needed to retain the third fixture's restrictions. See [layer3_water/assimilation/water_state_assimilator.py:L127-L148](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer3_water/assimilation/water_state_assimilator.py#L127-L148), [layer3_water/runner.py:L386-L397](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer3_water/runner.py#L386-L397), [layer3_decision/runner.py:L942-L986](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer3_decision/runner.py#L942-L986) and [layer3_water/contracts/assimilation_state.py:L22-L31](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer3_water/contracts/assimilation_state.py#L22-L31).

**Acceptance.** Use per-component role/reliability/uncertainty/support receipts for probes, satellite and thermal inputs. Preserve them through typed and dictionary history, with explicit qualification or quarantine of ambiguous legacy records. Compute authority and accepted counts from admitted components, not raw source names or object presence. Keep actual synthetic model assimilation distinct from independent observed authority.

### F01-B05 — P1: weak-label export assigns positive weight to malformed targets

**Observed behavior.** The actual exporter gives vigor NaN, Infinity and booleanTrue a training weight.30 in an otherwise eligible fixture; True is converted to1. The actual Layer1 ASMAE adapter retains the diagnostic mean-weight receipt. Finite zero and .5 work; shadow mode and unusable source controls correctly give zero weight.

**Boundary.** The fixture declares eligible diagnostics, uncertainties and retro/BMA metadata; it does not generate empirical holdout evidence. The actual Layer1 output remains diagnostic-only/state-update-false. No optimizer or trained model was run, and these weak labels are not equated with ground truth.

See [layer05_asmae/training/exporter.py:L141-L190](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer05_asmae/training/exporter.py#L141-L190) and [layer1_fusion/adapters/asmae_adapter.py:L409-L429](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/layer1_fusion/adapters/asmae_adapter.py#L409-L429).

**Acceptance.** Reject invalid target values before label rounding and weighting; record an explicit reason and weight0. Enforce target schema at export and again at training consumption. Preserve existing mode/authority gates and legitimate zero targets.

### F01-B06 — P1: validated supervised-training views accept invalid continuous targets

**Observed behavior.** The actual record_asmae_run → validation-event schema/writer → disagreement/candidate → private-ledger replay → build_validated_training_view chain produces approved eligible samples for vigor NaN, booleanTrue and a malformed string. Boolean validation confidence also yields an approved sample. The pipeline creates its own approval/candidate records; the harness does not handcraft an approved ledger row.

Finite-zero and finite.5 targets work. Explicit confidence0 and finite contradictory evidence produce no sample, and synthetic source_type is rejected.

**Boundary.** This is actual supervised-view eligibility, not completed training or model degradation. Private Python/JSONL calls expose the nonfinite case; HTTP reachability is not claimed. The source/target fixture is allowed by the current declared schema, not a claim of real lab verification. Categorical targets can legitimately be strings; this finding concerns a continuous vigor target and malformed confidence.

See [asmae_learn/schemas.py:L59-L81](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/asmae_learn/schemas.py#L59-L81), [asmae_learn/disagreement.py:L178-L199](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/asmae_learn/disagreement.py#L178-L199) and [asmae_learn/dataset_builder.py:L154-L201](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/asmae_learn/dataset_builder.py#L154-L201).

**Acceptance.** Add a target/unit-aware observation schema before event persistence, disagreement arithmetic, candidate approval and dataset emission. Confidence must be finite and within its declared range, excluding bool. Quarantine invalid legacy events/views with correction lineage; do not rewrite immutable histories or certify nonstandard NaN JSON. Keep qualified categorical vocabularies and zero-confidence exclusion.

### F01-B07 — P2, contained: RF internal admission omits scalar and evidence-role qualification

**Observed behavior.** Under an explicitly supplied matching QUALIFIED capability and calibration/epochtrue, the full MESIA bridge admits NaN/Inf/bool SNR as usable and emits state-update-enabled events. Actual likelihood → operator → spine → adapter also admits NaN support or covariance. CONTEXT, TRANSPORT and NEGATIVE_CONTROL packets produce the same state-eligible admission as SENSING, despite the repository's ASMAE_ELIGIBLE_ROLES containing only SENSING.

**Containment.** The visible service caller explicitly passes calibrationfalse and epochfalse; both negative controls prevent event emission. Training, prescription, insurance and machine authority stay false in admitted fixtures. The generated SigMF bytes verify artifact integrity only, not physical calibration. No deployed ASMAE posterior, field radio operation or public exploit was established. Zero covariance was observed but is not independently declared invalid without the noise-model policy; the finding relies on nonfinite cases.

See [mesia/behaviour/feature_extraction.py:L240-L247](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/mesia/behaviour/feature_extraction.py#L240-L247), [mesia/behaviour/likelihood_engine.py:L47-L67](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/mesia/behaviour/likelihood_engine.py#L47-L67), [mesia/assimilation/asmae_operator.py:L65-L89](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/mesia/assimilation/asmae_operator.py#L65-L89), [mesia/assimilation/layer0_spine.py:L39-L86](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/mesia/assimilation/layer0_spine.py#L39-L86), [mesia/ontology/evidence_roles.py:L65-L68](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/mesia/ontology/evidence_roles.py#L65-L68) and [mesia/service.py:L2629-L2635](https://github.com/webClone/AgriWise/blob/b51616da5a6f67a7a194439485c7aac71c7396ed/services/agribrain/mesia/service.py#L2629-L2635).

**Acceptance.** Validate scalar, support and covariance contracts before ADMITTED/state-eligible events; enforce evidence-role eligibility separately from capability/calibration. Keep useful context/nuisance diagnostics and current service containment. Verify downstream state entry separately before claiming end-to-end closure.

## Plan and monograph traceability

The normative master card is F01 at lines151–177; the task register is ST01-F01-01 through04 and FA at lines156–186. These are package task IDs. R3 provides scientific requirement IDs, not F/T package identities.

| Normative requirement | Verified progress | Remaining gap groups |
| --- | --- | --- |
| AB-DAT-005: zero differs from missing | Temporal finite-zero, wrapper reliability0, typed payload0, water probe0 and SNR0 controls pass | B01,B03,B05,B06,B07: invalid/coerced values or quality remain eligible |
| AB-DAT-006: per-field provenance | Individual wrapper roles and probe simulation/exclusion improve | B02,B04,B07: role loss/promotion and inconsistent source branches |
| AB-ARC-005: factorized authority | Diagnostic-only weak labels; synthetic water ASSIMILATED; RF training/execution limits survive | B02,B04,B05,B06,B07: status, state, training or admission qualifications disagree |
| AB-ARC-006: bounded degradation | Several missing/nonfinite/zero-confidence controls fail closed | B01–B07: other malformed or restricted inputs gain healthy defaults/eligibility |

The supplied R3 scientific excerpt locates these requirements at675–681 and738–744. PDF SHA256: `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`. The three plan Git identities and file-level receipts are in normative-verification.json. No monograph rewrite or status assertion was used to prove implementation.

| F01 task | Disposition | Needed before acceptance |
| --- | --- | --- |
| ST01-F01-01, numeric/zero continuity | Partial, meaningful verified slices | Target-aware components and invalid quality/target handling |
| ST01-F01-02, admitted/rejected components before authority | Partial | Component receipts and selected-source authority at actual consumers |
| ST01-F01-03, typed/dictionary roles | Partial | Monotone role propagation and history carrier/migration |
| ST01-F01-04, weather/RF/crop/training parity | Incomplete on actual compositions | Repair B01–B07 through common contract and adapters |
| ST01-F01-FA | Open | Bounded cross-consumer acceptance with retained positive controls |

## Detailed next implementation batch

Implement one admission contract and its migrations, then close these seven groups together. Avoid a separate permissive fix for each reproduced scalar.

1. **Define a target-aware component admission result.** Carry normalized value, declared type/unit, support, role, reliability, uncertainty, accepted/rejected reason and objective-specific authority. Preserve the original source record. Make rejected components explicit; valid siblings may proceed. Register continuous targets, categorical targets and boolean flags separately. Validate before any solver selection, feature arithmetic, truth override or training weighting.
2. **Make normalization explicit.** Accept finite real quantitative scalars excluding bool. Preserve finite0. Provider-specific numeric-string parsing, if supported, must be named and recorded before admission. Preserve absent versus invalid. Invalid supplied reliability contributes no usable weight; absent default quality carries its policy/provenance.
3. **Make role and permission merging monotone.** Resolve alias conflicts by qualification rules or reject ambiguity. Apply role restrictions before daily/user/provider shortcuts. Intersect permissions through adapters; generated crop/weather features inherit component qualification. Do not treat provider identity or capability as observed biological evidence.
4. **Migrate the water carrier and history seam.** Attach qualification to each probe/satellite/thermal component; retain it through serialization/deserialization. Version the stored schema. Legacy records without recoverable role/quality need explicit prior/unknown/quarantine policy. Derive OBSERVED/ASSIMILATED/MODELLED and accepted counts from actual qualified components. Preserve zero, finite variance guards and synthetic research-model controls.
5. **Repair weather/crop consumption.** Qualify reflectance arrays before float coercion while retaining valid boolean QA masks. Qualify thermal weather before GDD. Carry exclusion/forecast/synthetic status through canonical forcing records, crop observation ledger and token builder. Do not fabricate zero GDD for an invalid component; retain missingness. Scenario forecasts may remain usable in their qualified objective.
6. **Guard both training paths.** Apply the target registry at weak export and validated external-event creation, then recheck on ledger replay/view construction. Validate confidence independently. Emit zero-weight/rejected receipts for invalid labels and quarantine legacy malformed records through append-only corrections. Retain synthetic-source exclusion and weak-label/ground-truth separation.
7. **Close the contained RF contract.** Check quantitative features, support/covariance and packet role before likelihood/admission/event creation. Preserve diagnostics for context/transport/negative controls. Leave service calibration/epoch defaults unchanged. Treat downstream posterior eligibility as a separate actual consumer receipt.
8. **Run one bounded acceptance matrix at real consumers.** For every target class, cover finite0, ordinary finite, absent, NaN/Inf, bool, malformed string, invalid quality, explicit0quality, observation/prior/forecast/synthetic/excluded roles and conflicting aliases. Check actual admitted/rejected components, emitted permissions, numerical increment where executed, and training-view membership. Retain all working controls documented above. Add round-trip and legacy-migration cases.

Evidence needed to close F01 is a component receipt plus its actual consumer result, not only a helper returning false or a large passing test total. The authored replay bundle supplies a finite starting matrix; it is not an obligation to launch another unlimited whole-repository hunt. Run checks appropriate to the resulting edits and expand only for new changes or unresolved failures.

Independent package preparation and objective-qualified research can continue in parallel. Dependent package acceptance must not assume universal F01 qualification until this matrix closes. These software findings do not establish a new blanket field-hardware prerequisite for every unrelated package. Preserve the existing package-specific operational gates and all52 open FA rows.

## Deliverables and reproducibility

The claim/gap register maps the seven canonical groups to evidence, requirements, scope, controls and acceptance actions. Reviewer-local IDs in appendices map into these seven groups and are not additional counted findings.

The evidence bundle includes authored probes, strict-JSON observations, source/plan identities, fresh replay receipts and a read-only Git-object materializer. It excludes production-source copies, repository tests/audits, private raw captures and generated private ledgers. Reproduction needs a local checkout containing the pinned commit and a compatible Python environment. Exit0 means the declared observations, including counterexamples, reproduced; it is not a production test-pass claim.



---

# Specialist appendix: Temporal/typed evidence and downstream component validation

# F01 numeric and provenance admission — b51616d

Candidate: `b51616da5a6f67a7a194439485c7aac71c7396ed`; parent: `40315d95ff875914bd2f83cd1e75d88fdae859ff`. **The changed temporal scalar gate passes this bounded verification. F01 remains partial because two downstream admission contracts still lose qualification.** This lane executed five coherent groups and one adjacent production consumer chain, using inert in-memory fixtures. It did not run repository tests, audit scripts, a full fusion/assimilation job, services, HTTP, hardware or external jobs.

All 42 imported repository files matched their exact candidate Git blobs; the 14 statically inspected production files also matched. See `executed-file-manifest.json` for paths, module identities, SHA-256 and Git-blob receipts. No production source was edited. `results.json` records actual outputs; non-finite fixture values are represented by explicit `nonfinite_repr` objects so the result file itself is strict JSON.

## Verified slices

| Probe | Actual behavior | Qualification |
|---|---|---|
| G01: temporal scalar admission | Finite 0 and 0.45 admitted; Inf, -Inf, NaN, boolean, numeric string, malformed string and missing rejected | Credits `_has_numeric` change at `layer0/temporal_evidence.py:20–30`, using `scientific_contracts/numeric.py:10–22`. All other provider/provenance gates were satisfied. |
| G02: mixed components | One row containing invalid NDVI and valid EVI=0 admitted; invalid-only row rejected; ledger counts 1 admitted/1 rejected | Record-scope admission can legitimately retain a valid channel. This behavior alone is **not a defect**. Ledger has no per-component rejection receipt (`temporal_evidence.py:76–91`). |
| G03: legacy packet envelopes | Both typed and dictionary adapters retain raw numeric content and the valid timestamp/geometry; zero survives a JSON payload round trip | `ObservationPacket` is an envelope, not proof of numeric acceptance. Raw invalid values remain observed with positive envelope weight, but downstream qualification can reject them. No state-change conclusion follows from envelope storage. |
| G04: strong typed observation | `ASMAEObservationPayload` rejects invalid/non-finite/boolean/string values and non-positive or invalid variances; valid zero round trips | Existing production contract at `scientific_contracts/observation.py:36–57`, `59–73`; valid root-zone units, support, calibration reference and cutoff supplied. |
| G05: source-role adapters | Typed and dictionary forms map simulated/synthetic→simulated; prior/forecast→estimated; excluded/rejected→unavailable | Credits role preservation at `layer0/wrappers.py:132–178`, `216–257`, `315–334`. This does not establish per-field authority throughout the graph. |
| C01: actual Layer 1 packet consumer | Valid zero preserved; invalid-only Inf blocked; mixed Inf component receives `NAN_INF_VALUE` and range violations while valid EVI remains valid | Actual `observation_packet_to_evidence` → truth helper → `validate_evidence` chain; no fabricated replacement implementation. Also reproduces the two residual cases below. |

## Residual findings

### F01-R1 — daily-statistic truth classification promotes non-observation roles

With the complete eligible daily-provider fixture and finite NDVI=0, the wrapper correctly produces `simulated`, `estimated` or `unavailable` according to the supplied source role. `truth_for_observation_packet` checks the daily-statistic fast path **before** the packet-status exclusions: `layer1_fusion/truth_bridge.py:542–564` calls temporal admission, which checks provenance/quality/numeric presence but no role/status (`layer0/temporal_evidence.py:43–73`). The helper then returns `data_status="observed"`, `diagnostic_only=False`, `state_update_allowed=True` for all six tested non-observation roles: SIMULATED, SYNTHETIC, PRIOR, FORECAST, EXCLUDED, REJECTED.

The actual adapter first establishes status-specific diagnostic restrictions (`layer1_fusion/adapters/observation_packet.py:132–156`), but writes the truth helper's permissive fields into every emitted component (`158–160`, `182–218`). Each finite-zero evidence item then has `data_status="observed"`, `state_update_allowed=True` and **no validation violations**, despite its original simulated/unavailable flag; the validator keys behavior to the overwritten status (`layer1_fusion/evidence_validation.py:62–109`). Confidence ceilings remain in the adapter: simulated is 0.2, estimated 0.75, excluded/rejected 0.0. Those surviving ceilings do not restore the lost role or permission semantics. Prescription and scientific-surface permissions remain false in this daily-statistic branch; this probe does not demonstrate prescription or execution authority.

This is a confirmed production adapter/classification defect with an actual caller, not a claim that a field state changed. The path is used by `Layer0SourcePackageAdapter.extract_evidence` (`layer1_fusion/adapters/layer0_source_package.py:32–55`). The fusion engine subsequently validates before ledger admission (`layer1_fusion/engine.py:161–180`), but this exact validator accepts the reproduced items. Full fusion and final solver selection were not executed. Separately, Layer 0's state-engine packet path excludes simulated/unavailable/fallback packets before its temporal special case (`layer0/state_engine.py:263–299`); the defect is not asserted to bypass that separate path.

Acceptance: retain observation/prior/forecast/synthetic/excluded roles monotonically through the daily-statistic special case and emitted components. Excluded/rejected data must remain ineligible; simulated/synthetic data must remain diagnostic and unable to update operational state. Any permitted prior/forecast contribution needs explicit role-appropriate authority rather than being renamed observed. Re-run the same valid-zero controls with actual adapter validation, then verify admitted ledger counts/selected state components reflect these restrictions.

### F01-R2 — sibling finite channel permits boolean or malformed components through the Layer 1 validator

The fixture `{ndvi: true, evi: 0.0}` and the fixture `{ndvi: "not-a-value", evi: 0.0}` each legitimately satisfy the record's any-finite-channel predicate through EVI. The actual packet adapter then emits both NDVI and EVI without per-component numeric qualification (`layer1_fusion/adapters/observation_packet.py:171–218`). NDVI inherits `data_status="observed"`, `state_update_allowed=True`. The exact component validator returns an empty violation list for both bad NDVI values: its non-finite check covers floats, and its physical-bounds check covers int/float without rejecting booleans; malformed strings skip both checks (`layer1_fusion/evidence_validation.py:119–148`).

The mixed-Inf control is important: the invalid Inf NDVI **is** rejected by that component validator, while valid zero EVI remains acceptable. The residual is therefore the adapter/validator's incomplete numeric contract, not the use of `any` to admit a multi-channel record. No actual state update, model training or training-weight change was executed. Later consumers may reject or fail on these values; that cannot be substituted for explicit per-component acceptance before authority selection.

Acceptance: qualify each quantitative `EvidenceItem` against a finite real scalar contract before assigning its state/training permissions or admitting it to the ledger. Preserve a valid sibling zero and issue a component-specific rejection receipt for boolean/malformed NDVI. Validate the production ledger/selected-component result, not only the record-level predicate.

## F01 requirement coverage and boundaries

The normative master plan's F01 card is `AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:151–177`; task IDs are `ST01-F01-01` through `ST01-F01-04`, and `ST01-F01-FA` (`AgriBrain_Work_Packages_Task_List_2026-10-07.md:153–187`). The supplied R3 requires zero/missingness separation (AB-DAT-005, supplied scientific excerpt `675–677`), per-field OBSERVATION/PRIOR/RECONSTRUCTION/FORECAST/SYNTHETIC provenance (AB-DAT-006, `679–681`), factorized visualization/diagnosis/state/training/prescription/execution authority (AB-ARC-005, `738–740`) and bounded degradation without fallback promotion (AB-ARC-006, `742–744`).

`ST01-F01-01` has verified finite numeric and legitimate-zero slices; `ST01-F01-02` remains partial due to component acceptance/authority receipts; `ST01-F01-03` has improved wrapper role handling but the actual truth/adapter promotion remains; `ST01-F01-04` is not accepted by this bounded lane. Weather, RF, training admission and a full crop/soil solver run were not dynamically verified. Static crop admission uses this helper and independently derives finite signals (`layer2_veg_int/crop_posterior.py:452–521`, helper `181–188`), so a mixed row alone is not evidence that crop calculations consume its invalid channel. Orchestrator Sentinel-2 qualification calls the common temporal helper (`orchestrator_v2/runner.py:227–232`, `384–400`); that orchestration path was not dynamically executed.

All fixtures have an observed/acquired timestamp of `2026-10-10T10:00:00+00:00`, availability at 11:00, ingestion at 12:00 and an eligible cutoff/run timestamp of `2026-10-11T00:00:00+00:00`. Complete provider identity, content identity, geometry, quality admission, valid pixels, usability and production metadata are supplied. No late-arrival/future/cutoff failure is used to explain an F01 outcome. The temporal predicate itself has no cutoff parameter; this report makes no F02 acceptance or defect finding. Typed `knowledge_cutoff` validity beyond the supplied valid control was not probed.

Reproduce from the workspace root:

```sh
python review-b51616d-f01/ledger/probes.py
```

Portable layout: retain this review's `git-tree.json`, `commit-metadata.json`, `source/services/agribrain/` dependencies listed in `executed-file-manifest.json`, and this lane's script. No previous review result is correctness evidence for this candidate.


---

# Specialist appendix: Wrapper and actual Layer1 admission

# F01 wrapper and Layer1 admission verification

Candidate `b51616da5a6f67a7a194439485c7aac71c7396ed`, parent40315d9. This lane's five core groups and one actual Layer1 admission group were executed by its reviewer; root completed this narrative after the final-summary stage was interrupted. No claim of an independently completed sixth final review is made.

## Repair credit

The changed wrapper recognizes the individual role/source_role/data_role aliases for the tested SIMULATED, FORECAST, PROXY and UNAVAILABLE values, in both dictionary and typed packet cases. Explicit reading_reliability0 and reliability_weight0 survive and actual effective_weight is0. A finite.5 reliability produces.25 effective weight because the implementation applies both QA and reliability factors; this existing weighting design is not classified as a defect by this review.

Missing timestamps degrade to fallback, unknown declared status is unavailable, typed simulation remains simulation, and a wrapped sensor zero value survives serialization. In the actual Layer1 consumer, nonfinite measurement values and typed infinite reliability are quarantined; simulated input remains diagnostic and unable to update state. These controls establish useful checked corrections, not universal admission closure.

## Actual composition and scope

Run `python review-b51616d-f01/platform/wrapper_probes.py`, then `python review-b51616d-f01/platform/verify_metadata.py`. The first invokes actual wrappers, ObservationPacket, actual packet-to-evidence adapter and actual EvidenceLedger. It executes the exact `_admit_evidence_or_quarantine` production method via unchanged AST extraction to avoid starting the full fusion service. Its20consumer variants are not20full assimilation jobs.44actual imported files plus explicit static references are candidate-blob verified; source-manifest.json distinguishes them.

Complete finite timestamp/scope/provider/provenance controls are supplied in the fixture. Dictionary compatibility cases deliberately include conflicting roles or invalid scalar metadata. They are accepted API shapes, not observed public-provider traffic. The actual native sensor schemas/packetizer were inspected after exact staging; their emitted value packets do not establish that all conflicting/nested metadata fixtures naturally originate in that producer. No wrapper→water-vector, full fusion, training job or public-route exploit is asserted.

## Confirmed remaining cases

1. **Role conflict:** `role=OBSERVED,source_role=SIMULATED`, or `role=OBSERVED,data_role=UNAVAILABLE`, remains observed with effectiveweight1. Actual Layer1 admission accepts1item at confidence1 with state_update_allowedtrue. `_infer_data_status` selects only the first truthy alias atwrappers134, so later restrictive role metadata is ignored. The typed complete-provenance conflict repeats this result. This does not prove malicious external caller reachability; it proves the accepted adapter cannot enforce monotone source qualification in conflicting metadata.
2. **Invalid supplied reliability:** NaN, Infinity, True and malformed stringbad are treated as missing and default to1 rather than reject/degrade. Infinity/boolean actual consumer cases are accepted observed with confidence1/state_update_allowedtrue. This is duplicated by weather/training lanes and is one shared finding, not several new defects. Sourcewrappers297–310 and328–333; effective_weight atobservation_packet311–315. Legitimate0 remains0.
3. **Invalid quantitative components:** NDVITrue, False orbad passes the actual Layer1 admission with observed/confidence1/state_update_allowedtrue. The validator catches NaN/Infinity but not boolean-as-number or malformed string for this known numeric variable (`evidence_validation.py:119–148`). It is the same core numeric gap independently reproduced by the temporal/weather lanes; no posterior mutation is claimed here.

The nested-payload role fixture remains a compatibility-shape observation without demonstrated native producer exposure; it is not promoted into another canonical finding. The basic individual role-alias correction is not called broken merely because conflicting aliases need a stronger merge policy.

## Required acceptance

Use one target-aware component qualification contract before assigning update/training authority. Preserve roles monotonically, distinguish invalid supplied reliability from absent reliability, and quarantine invalid quantitative fields while retaining valid sibling channels. Preserve boolean metadata/categorical variables where their target schema legitimately allows them. Keep zero values, zero reliability, typed simulation, missing timestamp and nonfinite quarantine controls.

Actual ledgers count accepted EvidenceItems, not independent physical sensors or actual posterior updates. These receipts demonstrate admission/authority inconsistencies; they do not certify prescription/execution or supervised training effects. All three normative plans match the candidate, F01 requirements are DAT005/006 andARC005/006, and52package-FArows remain open. Current tests/audit documents are not correctness evidence; no production/Git edits, services, network, providers or hardware operated.


---

# Specialist appendix: Water assimilation and history qualification

# F01 water-assimilation admission and authority review

Candidate `b51616da5a6f67a7a194439485c7aac71c7396ed`, parent `40315d95ff875914bd2f83cd1e75d88fdae859ff`. Reviewed20October2026.

**Finite numeric/component admission and the tested simulated/excluded probe protections work. F01 remains incomplete in provenance propagation and authority qualification.** A forecast-tagged probe receives OBSERVED authority, an explicitly excluded satellite component still changes state, and the bounded history-dictionary adapter composition loses explicit simulation/reliability metadata before invoking the water runner.

Synthetic assimilation is **not inherently erroneous**: a diagnostic or research model update can legitimately use simulated values. The relevant checks are truthful source role, admissibility, actual accepted-component count and authority. This report credits synthetic updates that remain ASSIMILATED and does not treat them as forbidden merely because they alter modeled soil state.

## Reproduction and source scope

Command executed from `/workspace/scratch/de6bc2428cec`:

```bash
python review-b51616d-f01/decision/probes.py
```

Four coherent groups plus one bounded caller seam completed with their assertions. They comprise13 input variants, each invoking the actual assimilator and actual full `WaterIntelligenceEngine.execute_pipeline`; no full nutrition pipeline was needed. `results.json` contains exact inputs, direct and full-run diagnostics, actual source lists/counts, analysis increments, authority and unchanged-prior checks.

`executed-source-manifest.json` records **64 exact candidate production sources**, verified against the pinned tree before execution and rechecked afterward. The two pure history helpers are exact unchanged production AST function definitions, isolated from unrelated application module initialization; the actual typed vector and full water engine are imported normally. No target-body rewriting, mocked assimilation, repository-test/audit correctness proof, production/Git edits, network/service/controller/hardware call occurred.

The scope is actual scientific-function and full-water-runner execution plus an isolated history-helper composition. It does not establish a wrapper→water integration, a complete durable L3 run, public-route exploit, independent field observation or physical action. Wrappers and temporal/typed packets are independently owned by the platform/ledger lanes. Their packet carrier differs from this `SoilObservationVector`; no nonexistent typed-vector role/reliability field was invented.

## Verified controls

The prior has three layers ending10/30/60cm, uniform theta.20, FC.30, WP.15, saturation.45 and residual.04. All runs use the same explicit finite weather and no vegetation object, so OBSERVED/ASSIMILATED authority cannot be attributed simply to vegetation-object presence.

| Group/control | Actual result |
|---|---|
| G1 finite probe `[.30,.31,.32]`, sigma.015, `IN_SITU_PROBE_TDR` |3admitted; direct posterior `[.292,.3029,.3065]`; full count3, sourceTDR, authorityOBSERVED. |
| G1 legitimate numeric zeros `[0,0,0]` |3admitted, not discarded as missing; posterior is projected to residual-bound`.0401` in each layer and reports3bound corrections. This is modeled state clipping, not erasure of the input's zero/missingness distinction. |
| G1 `[+Inf,NaN,True]` |All3rejected before assimilation; direct same prior object/unchanged theta; admitted0; full analysis increment0 and authorityMODELLED. Weather-driven transition still legitimately changes water storage before assimilation. |
| G1 `[+Inf,.31,'malformed']` |Exactly1admitted and2component rejections. Correlated OI changes multiple state layers from the single admitted component; that is not evidence the rejected components were used. |
| G2 finite values with sigma0 or sigma+Inf |Each component rejects with `invalid_observation_uncertainty`; direct prior unchanged, admitted0, full authorityMODELLED. Zero uncertainty is invalid here; it is distinct from a legitimate zero observation or a zero reliability field. |
| G3 SIMULATED and SYNTHETIC probe controls |3admitted model updates; direct posterior `[.3359,.341,.3342]`; full authorityASSIMILATED, **notOBSERVED**. This earns the intended limited role/authority credit. |
| G3 explicit EXCLUDED probe |3component rejection receipts, admitted0, direct prior unchanged, full analysis increment0/MODELLED. |
| G4 invalid probes plus valid satellite.35 |All3probe values reject; exactly1satellite admitted; actual accepted sourceSATELLITE_SMAP_SENTINEL1; full authorityASSIMILATED. Raw rejected probe presence does not confer OBSERVED. |

Source: `services/agribrain/layer3_water/assimilation/water_state_assimilator.py:97–125` validates values/uncertainties/range/exclusion before building the observation operator; **127–142** determines probe role; **166–178,219–231** emits actual accepted counts/rejection diagnostics. The full water runner uses accepted source/count information at **386–397** to assign authority. The direct prior is not mutated in any control.

## Reproduced provenance gaps

### D1 — forecast-tagged probe is promoted to OBSERVED

**Evidence:** G3 actual typed vector→assimilator→full water runner; review priorityP1. Under the candidate's own provenance-marker convention, the input is a finite probe profile `[.35,.35,.35]`, sigma.015, `provenance_sources=['IN_SITU_PROBE_TDR','FORECAST']`.

The direct update admits3components, has no rejection, records only `IN_SITU_PROBE_TDR`, and produces `[.3359,.341,.3342]`. Full execution gives `[.3288,.3486,.338]`, analysis increment**89.70mm**, accepted count3 and **physics_authorityOBSERVED**. Its paired SIMULATED-tag control produces the same modeled update but correctly receives ASSIMILATED authority. Updating a research model from a forecast is not the defect; classifying that forecast basis as observed evidence is.

`water_state_assimilator.py:132–140` recognizes SIMULATED/SYNTHETIC/SCENARIO/PRIOR/MODELLED markers, but not FORECAST. `runner.py:387–391` repeats that limited exclusion list and requires only the admitted source labelTDR. The typed carrier has no explicit per-component role enum, so this free-form marker convention is currently the only role signal used here. The demonstrated claim is limited to this accepted convention/API; no upstream provider's production record was sampled.

**Fix/acceptance:** use an explicit per-component evidence role throughout the typed boundary; assign OBSERVED only from actually admitted components qualified for that role. Preserve legitimate forecast/synthetic diagnostic updates under separate authority. This exact FORECAST fixture must never gain OBSERVED; the finite observed control, zero values and simulated control must retain their intended behavior.

### D2 — satellite branch ignores explicit exclusion provenance

**Evidence:** G4 actual typed vector→assimilator→full water runner; review priorityP1. Input has no probe profile, satellite surface moisture.35, sigma.04, and `provenance_sources=['EXCLUDED_SATELLITE_SMAP_SENTINEL1']`.

Actual direct posterior changes from `[.2,.2,.2]` to **`[.265,.2424,.2207]`**, accepted count**1**, rejected list**empty**, and source rewritten to`SATELLITE_SMAP_SENTINEL1`. Full execution similarly admits1, assigns ASSIMILATED authority and records **+33.43mm** analysis increment. This is not falsely labeled OBSERVED, but an explicitly excluded component still enters the state update and accepted count.

The same EXCLUDED provenance convention correctly rejects probes. Exclusion classification is performed only inside the probe-profile block at **127–142**; the satellite call at **144–148** uses `add_observation`'s default OBSERVED role and a fabricated fixed source label instead of qualifying that component's provided provenance. The thermal surrogate call is similarly unqualified in source, but was not an additional executed counterexample.

**Fix/acceptance:** perform role/admissibility classification for every component before any fallback selection or update. An excluded satellite component must contribute no observation row, accepted count, covariance reduction or analysis increment; record its rejection reason. Preserve the positive invalid-probe/valid-satellite fallback control and allow qualified satellite model updates under their actual authority.

### D3 — history dictionary loses explicit role and zero reliability at typed conversion

**Evidence:** one bounded caller seam, review priorityP2; exact pure production helpers followed by the full actual water runner.

The input dictionary contains profile`[.35,.35,.35]`, sourceTDR, sigma.015, `role='SIMULATED'`, `reading_reliability=0.0` and `reliability_weight=0.0`. Actual `_serialize_soil_observation` preserves all three metadata values. Actual `_deserialize_soil_observation` discards them because they are outside its `known_fields`; the resulting actual `SoilObservationVector` has no role or reliability fields. Full water execution then admits3components with positive gain/variance reduction and **OBSERVED** authority, yielding the same+89.70mm analysis increment as the observation-weighted TDR update.

This is an executed serializer/dictionary→typed-vector→water composition, **not** a claim that the current wrapper automatically produces this water record or that a complete durable writer/reader cycle was run. The dictionary producer accepts/preserves the explicit metadata; the actual receiving helper loses it. The missing typed carrier is therefore demonstrated at this seam, rather than assumed by attaching invented fields to a typed vector.

Sources: `layer3_decision/runner.py:942–959` dictionary serialization, **962–986** filtered deserialization; `layer3_water/contracts/assimilation_state.py:22–31` actual vector fields. The complete decision runner module initialization and persistence were isolated; only these unchanged pure helper bodies executed. Existing history hydration calls to this helper at **1376,1515,2594** were source-traced, not executed as a full canonical workflow.

**Fix/acceptance:** extend the real carrier/adapters with field-level role/reliability and preserve explicit zero on replay, or reject/qualify metadata that cannot be represented. Do not infer observed authority from a source name after silently dropping a simulation role. Zero reliability must remain explicit and must not regain positive observational influence solely because an adapter removed it; any diagnostic-use policy must remain separate from observed authority. Re-run this seam together with the existing typed observed/simulated/zero controls, then verify the actual durable producer/consumer integration before claiming broader closure.

## Counts, solver selection and scientific scope

The numeric controls' accepted counts follow actual admitted observation rows, not the number of supplied probe values. Sources are unique labels; count3 means3admitted layer components, **not3independent sensors or3native measured truths**. Simulated rows may legitimately contribute to modeled assimilation counts. The unresolved issue is carrying their role and exclusion qualification so downstream consumers do not reinterpret those counts as observed evidence.

Solver selection still precedes component admission (`layer3_water/runner.py:145–150`), and `solver/solver_selector.py:48–54` tests raw probe-profile presence. This is a static remaining F01 ordering limitation. Both paths currently execute the same EMPIRICAL_BUCKET solver, so no different numerical solver or state change caused by that raw-presence decision was demonstrated here.

Master F01 **151–177**, steps2–4 and completion criteria, requires per-component accepted/rejected qualification, role preservation and authority/counts from actual admissible components. R3 supplied scientific sections: **AB-DAT-005675–677**, **AB-DAT-006679–681**, **AB-ARC-005738–740**, **AB-ARC-006742–744**. Numeric/probe-role repairs earn their checked credit; whole F01 remains open across the documented provenance seams and independently owned weather/packet/training boundaries. No field calibration, training eligibility, broad numeric matrix or physical control capability was certified by these groups.


---

# Specialist appendix: Weather/crop feature consumers

# F01 weather and crop admission consumers

Candidate `b51616da5a6f67a7a194439485c7aac71c7396ed`, parent40315d9. Four authored production compositions completed before the reviewer's final-summary interruption; root completed this narrative from the actual scripts/results/source receipts. The scope is F01 numeric/provenance behavior, not F02future availability or a complete crop/hydrology pipeline.

Run `python review-b51616d-f01/ownership/probes.py`. Actual wrappers, Layer1 adapter/truth normalization/validator/ledger, environment canonical transport, Sentinel2 crop builder, crop evidence ledger and model-input-token builder execute. Input raster arrays/geometry/provider envelopes are explicit synthetic fixtures; no provider acquisition, inference fitting or field data claim is made. Private object-shaped environment inputs satisfy the production duck-typed wrapper; no missing module or implementation was replaced.

## Numeric controls and gaps

Valid zero weather/NDVI and finite values survive. NaN/Infinity Layer1 measurements are quarantined, all-nonfinite crop reflectance produces unavailable/no model token, and nonfinite thermal input gives no thermal coordinate. Explicit reliability0 remains0. These are passing controls.

Boolean precipitation passes the actual validator and EvidenceLedger as observed/state-eligible/confidence1. The same shared Layer1 numeric-contract gap accepts booleans in quantitative crop channels. This is not a claim of full hydrological state mutation. Invalid reliability NaN/Inf/bool defaults to full1 rather than rejection, duplicating the wrapper finding.

The actual Sentinel2 builder casts boolean reflectance bands B04/B08 into float arrays (`layer2_veg_int/crop_observations.py:960–972`). It produces NDVI0 with observed status, reliability.95, independent count1 and a model-input token. Boolean QA masks legitimately exist; the issue is boolean *quantitative reflectance bands*, not a blanket ban on boolean arrays. Independent finite0-index and all-nonfinite controls distinguish valid-zero from malformed spectral input.

The actual thermal-coordinate path (`crop_observations.py:869–905`) turns temperatureTrue into GDD0=1. Excluded20°C weather still contributes GDD10=10; excluded precomputedGDD100 contributes100. The actual crop evidence/token chain carries those coordinates. No crop classifier prediction, training optimizer or prescription was executed.

## Provenance controls and gaps

Individual packet roles are correctly normalized. But `_canonical_weather_records` (`layer0/wrappers.py:54–111`) hardcodes current consensus records observed while the corresponding packet/package can remain simulated/unavailable/estimated. Explicit SYNTHETIC, EXCLUDED and PRIOR input qualification is lost from that record. Important retained boundary: its authority remains process_forcing_only and state_update_allowedfalse. It does not become a direct assimilation observation in this probe; it can still be consumed as weather/GDD forcing, where exclusion matters.

For crop rasters, declared `role=SYNTHETIC,data_status=simulated` or `role=EXCLUDED,data_status=unavailable` is ignored by the crop builder. With the independent complete provider/geometry/quality envelope supplied, both yield observed/reliability.95/independentcount1/model-tokeneligible output (`crop_observations.py:908–1218`, status fields1147–1184). Those flags intentionally make the envelope contradictory: the receiving contract must preserve/resolve the restrictive source role rather than silently trusting another positive flag. This is an accepted internal input-shape result, not proof a deployed provider produced those contradictory records.

Ad-hoc per-field/per-band excluded metadata and nested metadata were included as exploratory observations, but their accepted production schema/caller scope is not established. They are not extra findings or claims of a universal per-field public API. The canonical main findings use the documented top-level accepted carrier and directly consumed weather fields.

## Remediation and completion checks

Preserve source/data role, exclusion, confidence and support through canonical weather records and crop-derived features. Source family/provider identity must not overrule a restriction. Forecast/prior weather can legitimately drive qualified scenario models; it must not be renamed observed or lose exclusion in transport. Define field-level objective eligibility instead of banning all modeled weather.

Qualify numeric quantitative values and band dtypes before float coercion. Keep allowed QA/categorical booleans distinct from quantitative reflectance/temperature. Reject/quarantine excluded or invalid thermal contributions with an explicit receipt; do not fabricate a zero growing-degree day where an input is unavailable. Re-run the finite/zero/nonfinite controls and the actual record→crop token chain. Static orchestrator/layer0caller traces are in the source manifest; full operational route/phenology state/training exposure is not claimed.

This lane reproduces consumer gaps in F01step4 and shares numeric/reliability mechanisms with other lanes. The main register deduplicates them instead of counting every field variant as another defect. No repository tests/audits were proof, and no production/Git edits, services, network, hardware or runtime dispatch occurred.


---

# Specialist appendix: Weak and validated supervised training admission

# F01 training and scalar-consumer review — b51616d

Pinned source: `b51616da5a6f67a7a194439485c7aac71c7396ed`, parent `40315d95ff875914bd2f83cd1e75d88fdae859ff`. Scope is F01 step4 training admission plus actual reliability/provenance consumers. **F01 is not closed across these consumers:** two numeric training-admission defects and two related scalar/provenance boundaries were reproduced. The wrapper's explicit-zero and declared-role repairs retain credit.

## Scope, method and reproduction

Literal F01 requires that malformed numeric values cannot alter training weight, legitimate zero survives, and authority/accepted counts follow admitted components. Step4 extends qualification to training admission and ambiguous legacy records. R3 AB-DAT-005/006 requires valid-zero/missingness and distinct observation/prior/reconstruction/forecast/synthetic roles; AB-ARC-005/006 requires separate training/update/diagnostic authority and bounded degradation.

Exactly three authored offline compositions were executed:

1. Actual ASMAE weak-label exporter → actual Layer1 ASMAE training-weight diagnostic consumer.
2. Actual run ledger writer → actual validation-event schema/writer → disagreement/candidate builder → ledger replay → validated training-view builder.
3. Actual dictionary wrapper → packet effective-weight consumer → Layer1 packet truth bridge.

The fixtures use private local ledgers and inert declared inputs. No repository tests/audits, source/Git modifications, hardware, external services, network calls, optimizer fitting or model training were used. The ledger's archive-pilot override is disabled inside the probe process so supplied private paths are honored. No approvals were hand-written into the ledger: the candidate pipeline generates them. NaN is exercised through native Python production APIs and their JSONL writer/reader; no claim is made about an HTTP parser accepting nonstandard JSON.

Official command:

```bash
PYTHONDONTWRITEBYTECODE=1 python review-b51616d-f01/trajectory/probes.py
```

All51 imported production files match the candidate Git tree (`source-manifest.json`). Static read receipts and normative document hashes are separate. `results.json` preserves all outcomes, using explicit nonfinite representations so the report JSON itself is strict JSON. The private producer-written ledgers retain the actual serialized records. An initial fixture omitted required `Layer1InputBundle` fields; the harness was corrected to use the real complete schema before final execution. No unresolved harness error remains; the synthetic-source ValueError below is an expected control.

## F01-T01 — Nonfinite and boolean weak targets receive positive training weight

**Priority P1; executed exporter/adaptor boundary; F01, AB-DAT-005, AB-ARC-005/006.**

For one `vigor` coordinate, provide sigma.10, retro score.90 with `success_with_holdouts`, BMA disagreement.01/status success, radiometric pass, real scene-stack mode,3 scenes,10m resolution, production usable and `training_export` mode. These are inert declarations isolating the scalar gate; this probe does not establish empirical holdout quality or run the full upstream EnKF.

| Exported estimate | Training weight | Rejection reasons | Layer1 mean-weight diagnostic |
|---|---:|---|---:|
| Legitimate0 | .30 | none | .30 |
| Finite.50 | .30 | none | .30 |
| **NaN** | **.30** | **none** | **.30** |
| **Infinity** | **.30** | **none** | **.30** |
| **Boolean True** | **.30**, estimate becomes1 | **none** | **.30** |
| Shadow-mode control | 0 | mode not exportable | no training diagnostic |
| Production-unusable control | 0 | production not usable | 0 |

`layer05_asmae/training/exporter.py:141–190` rounds the estimate without finite/nonboolean admission, then derives weight from unrelated retro/sigma gates. `layer1_fusion/adapters/asmae_adapter.py:409–429` consumes the returned weights and reports their average; it does not reject the invalid target.

Important retained boundary: the label remains `weak_assimilated_reference`, never ground truth; the actual Layer1 consumer keeps the weight evidence `diagnostic_only=true`, `state_update_allowed=false`. Weak/model-derived research labels are permitted by this explicit mode/gating policy. The defect is **malformed target values with positive weak training weight**, not the existence of model-derived training data. No optimizer consumed these labels in this probe.

Remediation: perform target-specific finite/nonboolean qualification before export; reject or zero-weight the component with a reason. Apply the same explicit checks to sigma/retro/disagreement gate scalars. Preserve the legitimate-zero and mode/production controls. Acceptance requires these malformed targets to have no positive training weight and no falsely admitted target count; finite0 remains eligible under the declared policy.

## F01-T02 — Production validation pipeline approves malformed supervised targets

**Priority P1; executed producer-to-training-view composition; F01, AB-DAT-005, AB-ARC-005/006.**

The private fixture records an ordinary10m ASMAE run with complete lineage hashes, successful BMA/retro statuses, uncertainty.10 and retro score.90. It then calls `add_validation_event_to_ledger` for a `soil_lab`, plot/daily `vigor` validation event with fraction units, lab validator, nonempty evidence hash and confidence1. The model value matches the finite control. The actual schema generates trust, the actual disagreement/candidate logic generates eligibility, and the actual dataset builder emits samples.

| Validation input | Candidate status | Trust/agreement | Training-view output |
|---|---|---:|---|
| Target0, model0, confidence1 | approved | .90 /1 | target0, confidence1 |
| Target.5, model.5, confidence1 | approved | .90 /1 | target.5, confidence1 |
| **Target NaN**, model.5 | **approved** | **.90 /1** | **NaN target**, confidence1 |
| **Target True**, model1 | **approved** | **.90 /1** | **boolean target**, confidence1 |
| **Target `not-a-number`**, model.5 | **approved** | **.90 /1** | **malformed vigor target**, confidence1 |
| Target.5, **confidence True** | **approved** | **.90 /1** | target.5, **boolean confidence** |
| Confidence0 control | pending/ineligible | 0 /1 | no sample |
| Finite contradiction target1/model0 | pending/ineligible | .90 /.60 | no sample |
| Source type `synthetic` | schema rejects | — | no sample |

The failure is target-aware admission, not missing lineage. `asmae_learn/schemas.py:59–81` declares `observed_value: Any` without a per-target validator and accepts boolean confidence through numeric range comparisons. `disagreement.py:178–199` lets NaN comparisons and unrecognized strings yield no mismatch. `candidate_builder.py` then uses source-derived trust and diagnostics to approve; `dataset_builder.py:154–163,185–201` only checks target/confidence against None before returning them.

This is a concrete approved-training-view result with positive target confidence, not evidence that a fitting job or deployed model was affected. Categorical targets may legitimately use strings, so the remedy is a target/units/type contract: continuous `vigor` must use finite nonboolean values, while categorical objectives need an explicit vocabulary and appropriate validation. Reject boolean confidence and enforce finite[0,1] confidence. Revalidate on dataset read as well as write to cover older records. The good zero, zero-confidence exclusion, real contradiction and synthetic-source rejection must remain intact.

## F01-T03 — Invalid reliability defaults to full effective weight

**Priority P2; executed scalar consumer; AB-DAT-005 and AB-ARC-006. This is assimilation reliability, not supervised training weight.**

Wrap a timestamped `USER_OBSERVATION` packet with a valid.30 soil value and explicit reading reliability. The patched wrapper preserves reliability0, yielding effective weight0. Finite reliability.5 yields effective weight.25 because both QA scene score and reliability receive.5. But NaN, True and malformed string`bad` each become reliability1/QA1 and actual `effective_weight()`1.

Cause: `layer0/wrappers.py:297–304` makes invalid present fields indistinguishable from absent fields and defaults to1. The actual consumer multiplies them at `layer0/observation_packet.py:311–315`. This does not show an altered supervised label or authorized state update in this user-observation fixture. It does show that malformed confidence metadata is promoted to full scalar weight rather than explicitly excluded/degraded.

Remediation: distinguish absent reliability (documented default policy) from invalid supplied reliability (reject or zero with a reason). Retain the new explicit-zero handling and do not silently recover invalid input by a second default field without a defined provenance policy.

## F01-T04 — User-packet truth bridge loses PRIOR/FORECAST status

**Priority P2; executed provenance consumer; AB-DAT-006, AB-ARC-005/006. No supervised-training authorization was demonstrated.**

The wrapper now correctly returns `estimated` for PRIOR and FORECAST roles (`wrappers.py:133–146`). Passing those actual packets into `truth_for_observation_packet` returns `observed`/`observed_user` because its `USER_OBSERVATION` source branch unconditionally assigns that truth (`layer1_fusion/truth_bridge.py:589–600`). The actual bridge still sets `state_update_allowed=false`; the synthetic role is demoted through the proxy branch and does not become observed. Those restrictions deserve credit.

Remediation: preserve the packet's non-observed role before applying user-source classification, and keep objective-specific authority independent of source identity. Acceptance requires estimated PRIOR/FORECAST packets to remain non-observed through this bridge while ordinary user observations and synthetic diagnostic behavior retain their declared policy.

## Layer10/target eligibility and static limits

Selected Layer10 SIRE source was checked statically: default proof explicitly sets ML production weight0 and `ml_used_for_approval=false` (`layer10_sire/surface_contract.py:403–439`). The ASMAE engine separately gates weak export by mode/permissions (`layer05_asmae/engine.py:1576–1601,3213–3218`). Neither display authorization nor a non-observed research representation is treated here as independent biological supervision.

The validated-training view explicitly excludes weak labels as ground truth and requires an allowed external source. Its synthetic-source rejection and zero-confidence control pass. Its contract does not carry a general per-objective OBSERVATION/PRIOR/FORECAST/SYNTHETIC eligibility field; no additional role-smuggling or calibration-policy bypass was dynamically tested. Crop training has separate authority/snapshot gates in the selected production builder; that path was scanned, not executed in these three compositions. These static observations are not extra reproduced defects.

**Disposition:** credit current wrapper role/zero repairs and working weak-label/diagnostic/synthetic-source restrictions. Keep F01's training-numeric and cross-consumer qualification acceptance open on the reproduced cases above. Three compositions, no broad suite or hydrology/runtime reruns, and no claim of complete F01 or R3 certification.


---

# Specialist appendix: Contained RF/MESIA internal qualification

# F01 RF/MESIA internal admission contracts

Candidate `b51616da5a6f67a7a194439485c7aac71c7396ed`, parent40315d9. Three bounded compositions completed with179actual imported candidate modules verified. Root completed the narrative after the final-summary interruption. Current RF/MESIA production files did not change in this commit; they are reviewed because F01step4 explicitly includes RF admission.

## Scope and reproduction

Run `python review-b51616d-f01/protocol/qualification_probes.py`. The actual MESIA package initializer and all required production dependencies import normally; no fake namespace, source rewrite or dependency stub bypasses cold startup. A private generated SigMF byte fixture passes actual production ingest/manifest integrity checks. That proves artifact integrity only, not physical calibration or useful radio observations.

The full bridge fixtures explicitly register a matching all-gates QUALIFIED internal capability and pass calibration/epochtrue. Those are declared trusted internal API conditions, not observed deployment qualifications. The public/service caller remains contained: `mesia/service.py:2629–2635` explicitly passes calibrationfalse and epochfalse. This review does not claim a deployed posterior update, training mutation or public exploit.

## Composition1: packet→full bridge→record/event

With matched finite fixture conditions, SNR22 gives a legitimate zero innovation; SNR0 gives−22 without being discarded. Missing SNR gives ABSENT/no event and malformed string raisesValueError. However, SNRNaN andInfinity pass actual feature/likelihood/operator admission as ADMITTED/usable and produce an event with state_update_allowedtrue. SNRbooleanTrue is coerced to1, giving innovation−21 and the same authority.

Source `mesia/behaviour/feature_extraction.py:240–247` casts raw scalars withfloat; `behaviour/likelihood_engine.py:47–67` computes innovation/support without a finite/nonboolean contract. Raw capture identity and calibration metadata do not establish numerical validity of those scalars.

## Composition2: typed likelihood→operator→spine→adapter

Valid zero innovation remains admitted; zero support correctly yields ABSENT/no event. NaN support and NaN covariance are admitted and forwarded with state-update authority. Zero covariance is also accepted in the observed current path; the canonical main finding relies on the indisputable nonfinite cases rather than assuming a particular positive noise-floor policy without qualification.

`ASMAEObservationOperator.create_innovation` enforces evidence_proposal authority but directly converts innovation/support and forwards covariance (`assimilation/asmae_operator.py:65–89`). The spine checks only missinginnovation or support≤0 after calibration/epoch checks (`assimilation/layer0_spine.py:39–86`); comparisons withNaN do not reject it. The actual ASMAE adapter emits the event. No EnKF/posterior propagation or training job was executed, and later independently guarded strong typed payloads may reject invalid data; that does not repair this admission/authority contract.

## Composition3: documented roles and containment

The repository's own `ASMAE_ELIGIBLE_ROLES` contains onlySENSING (`mesia/ontology/evidence_roles.py:65–68`). Yet documented CONTEXT, TRANSPORT and NEGATIVE_CONTROL packets produce the same ADMITTED record/state-update-enabled event asSENSING under the explicit internal qualification fixture. Calibration capability does not by itself make connectivity/context/negative controls environmental sensing evidence. Such roles legitimately contribute to nuisance attribution or diagnostics, which should be kept separate.

The negative controls work: calibrationfalse gives INVALIDATED/no event; epochfalse gives QUARANTINED/no event; machine execution, training and prescription authority remain false even in admitted fixture events. The default visible service retains those fail-closed calibration/epoch inputs. Thus this is a **contained internal admission gap**, not current field activation or universal execution permission.

## Required F01 completion

Before admission, validate finite nonboolean innovation/source scalars, finite support in its declared range, and valid covariance under the declared noise model. Preserve legitimate zeroSNR/innovation; preserve missingness and zero-supportabsence distinctly from malformed input. Enforce per-packet evidence roles before generating sensing likelihood/state proposals; a qualified capability may constrain use but cannot promote a forbidden packet role. Keep the existing calibration/epoch default containment unchanged until its independent requirements are satisfied.

Re-run these three compositions with the passing controls. Invalid scalars must receive explicit rejected/invalid records with no state-eligible event; context/transport/negative controls must retain their own legitimate diagnostic/nuisance use. Verify actual downstream state entry separately before claiming end-to-end posterior closure. No repository tests/audits, live services, networks, radios, controllers, hardware, production/Git edits or real calibration are involved.

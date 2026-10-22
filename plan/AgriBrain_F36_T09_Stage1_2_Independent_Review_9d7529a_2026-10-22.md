# Independent verification: F36/T09 Stage 1–2

Review date: 22 October 2026. Branch: `feat/f36-t09-asmae-13-state-publication`. Actual GitHub head: **9d7529afb411ddabb5fc8f46931cf098e10d9240**. Base: **90ab701714554c7b786bba4ac6b19259e77279ce**. The supplied long SHA `9d7529a7d3c01bf64850bda481fa7ff055f661a1` does not resolve; its short prefix and the named branch identify the actual reviewed candidate. GitHub confirms two commits above the base: the documentation commit and the three-file production repair. The immediate Git parent is c6674e846209c50b9aeb6750ae8653d65641566d, which adds only the two review documents. All production controls use 90ab701, whose code is identical to that immediate parent; references to exact-parent controls below and in the appendices mean this exact production-parent/base equivalence. Main remains at 90ab701; F02 remains at 075f19d318db6fa86d5988c2cabcb680dc17702e.

**Verdict: retain the confirmed fixes, but hold merge and the Stage 1–2 completion claim for a focused corrective follow-up.** Five residual groups remain. Most reproduce on the exact parent and are inherited boundaries exposed by this review. The new optional-count comparison also introduces a malformed-metadata availability regression; the new prior fallback accepts invalid variance as prior evidence. None of the findings is presented as an executed prescription, physical state update, or field-hardware escalation.

No production code, Git branch, remote PR discussion, or acceptance checkbox was changed. Repository tests/audits and the reported 698-test result were excluded as independent correctness evidence. Three specialist lanes executed fresh production components, exact-parent controls, the exact isolated authorization statements, and the actual pure frontend resolver. All 52 FA milestones remain open.

## 1. Repairs independently confirmed

| Claimed repair | Fresh candidate result | Exact-parent control | Disposition |
|---|---|---|---|
| Plain missing ledger plus real raster | Unsupported; direct/scouting/management/statistics denied | Observed/direct status reproduced | Closed at this named classifier/native-generator boundary |
| Canopy-water own-variable lookup | Own canopy support passes; vigor-only support denied | Vigor-only incorrectly passed | Closed for the raw state and its canonical water alias |
| Root-zone own-variable lookup | Own root-zone support passes; canopy-only denied | Canopy-only incorrectly passed | Closed for the raw state and canonical alias |
| Five unmapped raw states | LAI, structure, bare soil, thermal and surface wetness have explicit gates | All five unmapped | Closed in the exercised positive-support fixture |
| Positive registered-state fixture | 11/11 diagnostic raw-state authorizations | 6/11 | Corrected fixture behavior; no universal field-run map count |
| Static descriptor management cap | Only vigor and bare-soil fraction qualify in the all-direct fixture | All eleven qualify | Static maximum restriction works; current per-run restrictions remain separate |
| Existing rendering/alias compatibility | Existing alias resolution, physical zero and native composite image bytes retained | Positive controls agree | No compatibility regression found in these controls |

These improvements should not be discarded. They do not establish that restrictions compose through every downstream alias or canonical permission field. Dedicated phenology and memory products, the thirteen-row expert selector, nodata conversion and GIS delivery remain subsequent planned work; their absence is not counted as a Stage 1–2 defect here.

## 2. Findings requiring follow-up

| ID | Priority | Confirmed boundary | Origin and practical limit |
|---|---|---|---|
| S12-01 | P1 | Unsupported raw states still influence an authorized risk composite selected by the actual frontend resolver | Inherited composite-support gap; diagnostic content/selection, no browser or action execution |
| S12-02 | P1 | Historical accepted counts and static descriptor maxima override current ledger denials/ceilings in separate consumers | Inherited monotonicity gap; typed native ledger/generator/authorization fixtures |
| S12-03 | P1 | Canonical serialization emits update/prescription flags true despite native ASMAE provenance denying both | Inherited permission-parity defect; actual native generator→alias→serializer, no executed action |
| S12-04 | P2 | Strict actual-prior qualification is incomplete; labels and invalid variance still establish Prior-Constrained | Retained label bypass plus newly permissive presence-based fallback |
| S12-05 | P2 | Direct-proof metadata accepts boolean/Infinity, while explicit null/string counts newly abort native generation | Residual proof qualification plus introduced malformed-metadata availability regression |

Priorities concern software/publication correctness within this review. They are not a claim that a live plot encounters every fixture or that an external party can reach every metadata boundary.

### S12-01 — unsupported values survive through the risk lens

The native generator receives aligned nonconstant grids without a per-state ledger. Candidate correctly marks raw biotic risk Unsupported. The new raw-state gate denies it. The actual `generate_asmae_aliases()` nevertheless admits biotic, thermal and salinity ingredients based on finite-content/geographic pixel eligibility. Its weighted risk composite does not inherit each ingredient's state-support denial. The generic RISK authorization branch then accepts global BMA/retro proof, and the actual frontend policy resolver selects `RISK_ASMAE_DIAGNOSTIC` as `available_overlay`.

Changing only the unsupported biotic input scale from 0.1 to 1.0 changes the selected first pixel **0.0418 → 0.068**, and the last pixel **0.3759 → 0.612**. The raw biotic surface remains Unsupported and denied in both cases. The composite's provenance remains diagnostic and denies state/prescription use. The result proves diagnostic content and selection leakage, not physical action authority.

This is a native generator→native alias constructor→exact production authorization block→actual pure frontend resolver composition. No React/DeckGL/browser materialization or real field execution was run. The parent reproduces the composite behavior; the new raw-state denial does not yet compose through it.

Relevant source: [services/agribrain/layer10_sire/surfaces/asmae.py:L1750-L1849](https://github.com/webClone/AgriWise/blob/9d7529afb411ddabb5fc8f46931cf098e10d9240/services/agribrain/layer10_sire/surfaces/asmae.py#L1750-L1849), [services/agribrain/layer10_sire/runner.py:L5186-L5217](https://github.com/webClone/AgriWise/blob/9d7529afb411ddabb5fc8f46931cf098e10d9240/services/agribrain/layer10_sire/runner.py#L5186-L5217), and the actual frontend resolver's selection code. The fix belongs to the current support/publication slice, rather than being deferred solely to a future state picker. Filter ingredients by qualified current support before composition, preserve exclusions, and derive aggregate permission from eligible ingredients. Justified derived diagnostics can remain available without requiring direct physical observations of every coordinate.

### S12-02 — current restrictions are not monotone

Two actual consumer paths disagree about current restrictions:

1. A native typed vigor record with `support_status=unsupported`, `accepted_update_count=1`, and `block_reasons=[local_support_revoked]` passes ledger normalization. The historical update count is valid. Native surface classification correctly returns Unsupported, but the complete authorization statements permit its diagnostic overlay because the count overrides the present restriction.
2. A production-built accepted direct-report ledger has a current `authority_ceiling=DIAGNOSTIC`. The new classifier consults only the descriptor's static maximum. Vigor's raw `management_zone_eligible` remains true under current DIAGNOSTIC/VISUALIZATION ceilings and explicit block reasons. The alias independently carries stricter diagnostic provenance, but that does not repair the raw eligibility field.

Both also reproduce on the parent. The static descriptor cap itself is confirmed; the remaining defect is failure to intersect it with the current qualified ledger restriction. The fixtures do not establish that an ordinary field run produces the particular revocation record or that a management action is performed.

The complete gate does reject malformed accepted counts through the normalizer. Boolean, negative, NaN and fractional accepted counts are not treated here as successful authorization counterexamples. Restrictive current status alongside a valid historical count is a distinct contract case.

Relevant source: [services/agribrain/layer10_sire/runner.py:L5141-L5180](https://github.com/webClone/AgriWise/blob/9d7529afb411ddabb5fc8f46931cf098e10d9240/services/agribrain/layer10_sire/runner.py#L5141-L5180) and [services/agribrain/layer10_sire/surfaces/asmae.py:L554-L579](https://github.com/webClone/AgriWise/blob/9d7529afb411ddabb5fc8f46931cf098e10d9240/services/agribrain/layer10_sire/surfaces/asmae.py#L554-L579). Apply current deny/block precedence before positive historical evidence, and compute effective eligibility as the intersection of descriptor ceiling, current per-state ceiling, objective-specific proof and current exclusions.

### S12-03 — canonical flags contradict native denial

Actual native ASMAE surfaces and ordinary aliases place `state_update_allowed=false` and `prescription_driver_allowed=false` in provenance. Their `SurfaceArtifact` fields are left at default true. The canonical serializer's attribute-first lookup selects those true fields ahead of the explicit provenance denial.

| Native/canonical field | Candidate observation |
|---|---|
| Raw or alias provenance state-update permission | false |
| Canonical top-level state-update permission | **true** |
| Alias provenance prescription-driver permission | false |
| Canonical top-level prescription-driver permission | **true** |
| Missing-ledger raw support classification | Unsupported |

The contradiction occurs even in the candidate's correctly Unsupported missing-ledger case and also reproduces on the parent. This does not establish that a downstream actuator or state updater accepts the contradictory payload. It establishes an actual published-contract serializer defect at the exercised boundary.

Sources: [services/agribrain/layer10_sire/schema.py:L490-L495](https://github.com/webClone/AgriWise/blob/9d7529afb411ddabb5fc8f46931cf098e10d9240/services/agribrain/layer10_sire/schema.py#L490-L495), [services/agribrain/layer10_sire/surface_contract.py:L85-L96](https://github.com/webClone/AgriWise/blob/9d7529afb411ddabb5fc8f46931cf098e10d9240/services/agribrain/layer10_sire/surface_contract.py#L85-L96), [services/agribrain/layer10_sire/surface_contract.py:L125-L170](https://github.com/webClone/AgriWise/blob/9d7529afb411ddabb5fc8f46931cf098e10d9240/services/agribrain/layer10_sire/surface_contract.py#L125-L170). The serializer has a separate INTERPOLATED_PROXY override; the tested native ASMAE raster/alias does not take that override.

Set authoritative permission fields explicitly in ASMAE constructors and make canonical serialization enforce restrictive consistency, including legacy objects with contradictory attributes/provenance. A false restriction must survive serialization and reload; changing only a display badge cannot close this contract.

### S12-04 — prior existence is still inferred from assertions/presence

The implementation report claims a strict `has_actual_prior=True` guard. No such guard appears in the reviewed function. A bare `prior_constrained` ledger or metadata label is accepted, and a new branch accepts any non-None `prior_variance`. Direct helper cases admit NaN, negative variance, False and strings. Actual native generation with unknown source and NaN variance produces Prior-Constrained/scouting=true; the parent returns Unsupported/scouting=false for that same carrier.

With real-raster metadata, the parent's erroneous Observed label becomes Prior-Constrained, so that variant improves in degree while still failing the claimed qualification. A native empty-update ledger also supplies a prior label without enough prior lineage/variance for this consumer to verify its existence. That does not prove the underlying model has no prior: a valid model prior must be retained by carrying explicit support, rather than by relabeling every prior-only state Unsupported.

A finite nonnegative zero prior-variance control remains legitimate. Correct qualification must preserve zero, reject non-finite/boolean/negative variance and truthy malformed flags, and bind prior status to actual per-state prior lineage/distribution. A newly introduced boolean alone would not be scientific proof either. See [services/agribrain/layer10_sire/surfaces/asmae.py:L528-L552](https://github.com/webClone/AgriWise/blob/9d7529afb411ddabb5fc8f46931cf098e10d9240/services/agribrain/layer10_sire/surfaces/asmae.py#L528-L552).

### S12-05 — direct-proof metadata is not numerically qualified

The new metadata comparison evaluates `direct_observation_count > 0` without strict qualification. A boolean True or positive Infinity satisfies it. Native generator cases retain Observed/direct=true/management=true for vigor. Both revisions label those cases Observed, so this is a residual proof-qualification gap rather than a new Observed regression.

Explicit null or string `'1'` now raises TypeError and aborts the actual surface generator; the parent generates eleven surfaces for the same carrier, although its Observed labeling was unsafe. The comparison establishes a new uncaught malformed-metadata availability failure, not that the parent's unsafe output should be restored.

These are admitted raster-metadata dictionary fixtures. The review does not claim normal producers emit these fields, that an external adversary can provide them, or that production currently experiences the exception. The declared admission boundary should nevertheless return a typed unsupported/invalid-proof reason instead of accepting malformed proof or aborting unrelated surfaces. See [services/agribrain/layer10_sire/surfaces/asmae.py:L528-L537](https://github.com/webClone/AgriWise/blob/9d7529afb411ddabb5fc8f46931cf098e10d9240/services/agribrain/layer10_sire/surfaces/asmae.py#L528-L537).

Qualify proof counts as finite non-boolean nonnegative integers, preserve absence separately from invalidity, and verify observational relationship/lineage consistently. A direct/proxy/indirect label asserted in free metadata is not itself independent measurement evidence.

## 3. Bounded follow-up and acceptance evidence

Keep this branch and the confirmed fixes. Correct the following seams before recommending merge or declaring Stage 1–2 complete:

| Repair seam | Meaningful acceptance |
|---|---|
| Current support and alias inheritance | Altering a rejected ingredient cannot alter a selected diagnostic composite. If no qualified ingredients remain, emit no finite composite and record why. Legitimate model/hypothesis diagnostics still work. |
| Denial/ceiling precedence | Current Unsupported/revoked/blocked state remains denied despite a historical positive count. A current DIAGNOSTIC/VISUALIZATION ceiling cannot become management eligible through a descriptor's higher maximum. |
| Canonical permission parity | Raw, alias, serialized and reloaded permissions agree; explicit false remains false even with legacy true defaults. Retain qualified products' intended permissions. |
| Prior proof | Explicit valid prior lineage/distribution survives, including qualified zero. Bare assertions, NaN/negative/boolean/string variance and malformed truthy flags do not establish prior support. |
| Direct proof | Boolean/Infinity are rejected; null and malformed counts do not crash the whole generator. Accepted indirect support remains indirect; valid direct-reference controls remain correctly classified. |

One shared current-support predicate should feed raw-state authorization and alias ingredient eligibility. Do not rewrite the entire SIRE runner to achieve that. Constructor/serializer parity may require a small F38/T11 boundary correction alongside F36/T09. Full F36 calibration remains distinct from fixing these software contracts.

Future-product caution: the new stress-memory helper accepts relationship `none` as an alternative to positive memory/process status, even for a restrictive zero-count record. Memory is not registered as a dedicated product in this batch, so this is not counted as a current rendered-memory blocker. Correct that predicate and reconcile the descriptor/update-map policy before Stage 3. Several newly named status aliases are also not members of the strict canonical status normalizer; use established status semantics or version the contract deliberately.

Continue independent F02 work. Main and F02 identity checks show no remote changes by this review. Do not merge F02 into this branch merely to repair the above support/publication seams. All 52 FA milestones remain open; neither this review nor a targeted software correction signs package acceptance.

## 4. Method, evidence and limitations

Fresh exact-parent runs use actual native classification/generation, producer-ledger construction, alias construction, canonical serialization and rendering components where stated. Runner authorization is the exact unmodified AST statement block with controlled surrounding carriers; the integrated runner/provider/job system is not run. The frontend probe imports the actual pure TypeScript policy resolver; no browser materialization is claimed.

Classification has 40 helper and 15 native-generator cases per snapshot, an eleven-state descriptor matrix and nine retained positive controls. Gating records twelve candidate and ten parent observation checks, plus three actual frontend composition checks. Integration records fourteen cases and nineteen observation checks per snapshot. Counts include expected counterexamples and are not summed into a repository-test total. A zero replay exit means documented fixes and residuals reproduced, not that every desired production contract passes.

All 1,086 staged source/configuration/document files match pinned Git blobs, with source bytes unchanged. Three modified production modules compile. Source/import identity is not line or branch coverage. Exact-parent controls separate inherited gaps from the new malformed-proof exception and newly permissive variance branch. The three governing plan documents match the candidate tree and retain 52 open FA rows; supplied R3 identities are verified. Relevant requirements remain per-variable qualification, faithful projection and preservation of restrictions across serialization.

The evidence bundle includes authored scripts, fresh results, exact source/AST/import manifests, selected plan/R3 references and a read-only source reconstruction helper. Production source, repository tests/audits and private runtime stores are excluded. No field accuracy, real plot diagnosis, whole-repository regression, external reachability or physical-action escalation is inferred.


---

# Specialist appendix: Scientific support classification

# Support classification verification — Stage 1 candidate 9d7529a

Candidate: **9d7529afb411ddabb5fc8f46931cf098e10d9240**. Exact parent control: **90ab701714554c7b786bba4ac6b19259e77279ce**. This lane uses production source and fresh native calls; repository tests, implementation reports and audit assertions are not correctness evidence. The user's longer candidate SHA does not identify the actual reviewed branch commit; the coordinator verified the branch identity separately.

**The original missing-ledger plus real-raster Observed fallback is closed at the exercised native generator boundary.** Ordinary missing proof now yields Unsupported with direct-observation, scouting, management and statistics eligibility false. However, the claimed strict prior-proof requirement is not implemented across accepted inputs, and the new direct-proof scalar checks remain insufficient. Management-ceiling restrictions require the integration lane's additional per-run analysis.

## Fresh execution and preserved positive controls

`probes.py` executes candidate and parent in separate Python subprocesses with separate import paths, preserving exact production bodies. Each snapshot receives forty direct classifier cases, fifteen actual native surface-generator cases, and the eleven-state management-positive matrix. Nine comparison/retention controls pass. Counts describe different probe groups rather than repository test totals.

| Native boundary/control | Exact parent | Candidate |
|---|---|---|
| Real-raster carrier, no state ledger or qualification metadata | Observed; direct=true; management=true for vigor | **Unsupported; direct/scouting/management/statistics=false** |
| Explicit accepted indirect dictionary ledger | Indirectly-Constrained | Indirectly-Constrained |
| Explicit prior-only dictionary ledger | Prior-Constrained | Prior-Constrained |
| Diagnostic uncertainty surface, missing support | Derived diagnostic | Derived diagnostic |
| Explicit finite direct-count metadata across eleven states | Management eligible for all eleven | Management eligible only for vigor and bare-soil fraction, the two current prescription-eligible descriptor maxima |
| Finite prior-variance zero, unknown source | Unsupported | Prior-Constrained; legitimate numerical zero is preserved |

The native generator receives aligned 3×3 varying grids, native Layer10Input/L1SpatialData carriers, and the documented visual-shadow rollout flags. No generator, classifier, resolver or rollout function is replaced. All eleven registered state types generate in the positive fixtures. The ordinary missing-ledger closure is therefore not inferred solely from helper execution.

## C-S1: prior existence is still inferred from unqualified labels and invalid scalars

The implementation report describes an actual-prior proof requirement and a `has_actual_prior=True` guard. There is **no such guard** in the classifier. Supplying only that reported flag returns Unsupported; it is not a recognized qualification.

The actual candidate accepts `support_status='prior_constrained'` directly at `surfaces/asmae.py:490–499`, and raw metadata `support_class='prior_constrained'` at `:529–539`. Neither branch verifies a prior record or checks whether a prior exists. The new fallback at `:540–547` additionally accepts any non-None `prior_variance`, or truthy prior/fallback flags.

| Controlled input | Candidate outcome | What this establishes |
|---|---|---|
| Bare ledger prior label, no prior value/variance/reference | Prior-Constrained, scouting=true | Assertion is accepted without independent proof; retained parent behavior |
| Bare metadata prior label, no prior evidence | Prior-Constrained, scouting=true | Same bypass through raster metadata |
| `prior_variance=NaN`, unknown source, no ledger | **Prior-Constrained, scouting=true** | New fallback uses presence rather than finite-real qualification |
| `prior_variance=-1`, `False`, numeric or malformed string | Prior-Constrained in direct helper calls | Invalid variance types/domains are not checked |
| `has_prior_evidence='false'` | Prior-Constrained | Truthy malformed string is treated as a positive flag |
| Finite nonnegative variance fixture, including 0.0 | Prior-Constrained | A fix must preserve qualified zero rather than use truthiness |

The NaN result is also reproduced through actual `generate_asmae_surfaces()`: unknown source plus no ledger gives candidate Prior-Constrained/scouting=true, whereas the exact parent gives Unsupported/scouting=false. With a real-raster carrier the parent was Observed and the candidate is Prior-Constrained, so that version is an improvement in degree while still failing the claimed prior qualification.

The native `build_state_support_ledger([])` producer also returns prior-constrained entries without a prior-reference/variance qualification, and the generator accepts them. This does **not** prove its underlying model has no prior. It proves that this boundary cannot validate prior existence from the accepted record and that the report's claimed guard is absent. The valid native prior-only path should be preserved by carrying explicit provenance rather than by retroactively labeling all prior-only states Unsupported.

Corrective direction: define or carry the actual per-state prior evidence/lineage and numeric contract, then evaluate it consistently across ledger and metadata paths. A standalone boolean is not scientific prior proof. Require finite non-boolean nonnegative variance when a variance is supplied; do not turn an invalid scalar or a truthy string into scouting eligibility.

## C-S2: direct-measurement proof scalars remain unqualified and nullable metadata newly aborts generation

The candidate's metadata branch at `surfaces/asmae.py:532–537` evaluates `direct_observation_count > 0` without strict scalar qualification. With `support_class='directly_assimilated'`, both a boolean True and positive Infinity satisfy that predicate.

Actual generator fixtures for True and Infinity produce an **Observed** vigor surface with `direct_observation=true`, `management_zone_eligible=true`, `scouting_zone_eligible=true` and `zone_statistics_eligible=true`. Both snapshots produce that label, so this is a **residual proof-qualification gap**, not a newly introduced Observed regression. Candidate provenance still has `diagnostic_only=true` and `state_update_allowed=false`; the review does not claim physical state, prescription, or hardware authority was exercised.

The same new comparison has an availability regression: explicit `direct_observation_count=None` or string `'1'` raises TypeError and aborts the actual generator. The parent returns eleven surfaces for the same carrier, although its Observed classification was unsafe. This comparison therefore proves a newly uncaught malformed-metadata exception; it does not make the parent's unsafe label an acceptable positive control.

These are accepted native raster-metadata dictionary boundaries using controlled malformed proof fields. The review has not demonstrated that ordinary fresh engine outputs contain these values, that an external adversary can supply them, or that current production encounters this exception. The implementation must nonetheless fail closed within its declared numeric/provenance boundary instead of admitting a boolean/Infinity as proof or terminating the whole surface generator on an optional null field.

Corrective direction: qualify count evidence as finite, non-boolean, nonnegative integers and qualify direct-reference provenance. Preserve absence separately from invalidity; explicit invalid proof should produce Unsupported/typed reason rather than an unhandled TypeError. Check accepted-update/relationship consistency through the shared normalizer. Do not treat a self-asserted direct flag or classification string as sufficient independent measurement evidence.

## Additional compatibility observation, not a full-route blocker

A direct helper call with native `StateSupportRecord(ASSIMILATED, INDIRECT, accepted_update_count=1)` produces Proxy-Assimilated, while its `.to_dict()` representation produces Indirectly-Constrained. The shared resolver converts enum relationships with `str(...)`; the new wrapper normalizes the status enum but not all related fields. The exact parent used its real-raster fallback and labeled the native object Observed, so the candidate is less permissive while retaining a type-parity mismatch.

The ordinary native generator first normalizes dictionary ledger entries with `index_state_support_ledger`, and the full route mismatch is not established here. Treat this helper object/serialization parity as a low-priority qualification, not an additional claim of a live map failure. Malformed raw ledger status/count cases rejected by that normalizer remain correctly fail closed and are not counted as generator defects.

## Exactness, provenance and limits

Both snapshots verify all **1,086 staged files** against their pinned Git blobs before execution and unchanged bytes afterwards. Candidate imports 46 exact repository source files. Imported-file manifests and strict JSON results preserve the proof fields and each production exception. Non-finite fixture values are tagged only in saved JSON; actual production calls receive native float NaN/Infinity.

This lane does not execute the full integrated runner, providers, HTTP/browser rendering, job scheduling, training, prescriptions, or hardware. It does not assess whether classification metadata ultimately authorizes an action. Descriptor-maximum management restrictions are confirmed here; stricter current ledger ceilings/block reasons are independently reviewed in the integration lane.

All 52 FA milestones remain open. The ordinary missing-ledger software closure should be retained, while the strict-prior claim and direct-proof numeric boundary should be corrected before claiming complete Stage 1 hardening.

## Reproduce

```sh
python3 review-f36-t09-9d7529a/classification/probes.py
```

The driver launches fresh candidate and exact-parent workers, writes strict JSON and stdout/stderr captures, then verifies nine bounded positive controls. Expected production exceptions and residual counterexamples are observations inside a successful review harness, not failed harness execution or a repository test-suite result.


---

# Specialist appendix: Raw gates, composites and actual frontend selection

# Stage 1–2 mapping and authorization — independent verification

Candidate: `9d7529afb411ddabb5fc8f46931cf098e10d9240`. Exact parent control: `90ab701714554c7b786bba4ac6b19259e77279ce`. The candidate is the actual GitHub branch head supplied by the coordinating review. The report's alternative long SHA is not used here. All source is pinned by Git blob and SHA-256; repository tests/audits are excluded as correctness evidence.

**The original water-linkage and five unmapped-state defects are corrected at the raw-state boundary. The reviewed contract remains incomplete through the native risk composite and frontend selection.** The current native classification can mark an ingredient Unsupported, and the new raw biotic gate can deny it, while the existing risk alias still incorporates that ingredient and is selected by the actual frontend policy resolver. A second residual allows a present explicit unsupported status to be overridden by a positive historical accepted-update count. Both mechanisms also reproduce on the exact parent; they are residual boundaries, not newly introduced regressions.

All 52 FA milestones remain open. No production changes, full integrated runner, provider, job, HTTP service, browser, optimizer, controller, drone or physical prescription is run. Fresh probes use ordinary production generator/alias calls, exact isolated authorization statements, and the actual pure frontend resolver.

## Original mapping closures

The native `generate_asmae_surfaces()` produces eleven registered state surfaces from aligned nonconstant fixtures. The exact candidate authorization block grants all eleven diagnostic overlay authorizations when their own indirect support and all relevant global/family/lifecycle controls are supplied. The exact parent grants six. This is a deliberately positive software fixture, not a guarantee about the number of maps in a real plot.

| Focused control | Candidate | Exact parent |
|---|---|---|
| Canopy-water ledger only | Allowed | Denied: missing vigor |
| Vigor ledger only, checking canopy water | Denied: `missing_state_support:canopy_water` | Allowed |
| Root-zone-water ledger only | Allowed | Allowed |
| Canopy-water ledger only, checking root-zone water | Denied: `missing_state_support:root_zone_water` | Allowed |
| Supported LAI, structure, bare soil, thermal stress and wetness | All five mapped and allowed in the positive fixture | All five unmapped |
| No biotic state ledger, positive BMA/retro proof | Raw biotic denied | Raw biotic allowed |

The new canonical dictionary resolves the raw state types and the six relevant state aliases without a canopy/water substring collision. The family gate now recognizes WETNESS, CHLOROPHYLL and BIOTIC names. These repairs are real and should be retained.

Current source: `services/agribrain/scientific_contracts/state_schema_ref.py:47–83`; runner state/family logic at `services/agribrain/layer10_sire/runner.py:5115–5194`. The full isolated authorization statements are `runner.py:4989–5579`; their AST digest and native helper source spans are recorded in `source-receipts.json`. The block was located by AST structure rather than by old line numbers, and no predicate/body/loop was edited.

## Residual G01 — rejected ingredients still influence the actual risk lens

This is an ordinary composition of current production boundaries, not only a direct call to an internal state predicate:

1. The actual native generator receives eleven aligned nonconstant grids and no per-state ledger, with reviewer-supplied current-spatial/real-raster metadata.
2. On candidate, the generated raw biotic state is correctly `unsupported`. It is not direct observation and is not scouting/management qualified.
3. The actual `generate_asmae_aliases()` includes biotic, thermal and salinity arrays because its ingredient predicate tests **pixel geometry/finite-content eligibility**, rather than each ingredient's scientific support or final raw-state authorization.
4. The actual runner authorization statements deny `ASMAE_BIOTIC_CONFOUNDER_RISK` with `missing_state_support:biotic_confounder_risk`, but permit `RISK_ASMAE_DIAGNOSTIC` using the generic non-state RISK branch and global BMA/retro proof.
5. The actual pure TypeScript `resolveAuthorizedSurfaceForMode()` selects the generated risk alias for `composite_risk` as `available_overlay`.

Holding all other data/proof fixed and changing only the unsupported biotic input scale from 0.1 to 1.0 changes the selected first risk pixel **0.0418 → 0.068**, and the last pixel **0.3759 → 0.612**. The risk provenance records all three state ingredients; it does not list their unsupported support as an exclusion. The raw biotic surface remains denied in both cases.

| Boundary receipt | Candidate result |
|---|---|
| Raw biotic `support_class` | `unsupported` |
| Raw biotic base/overlay authorization | false |
| Risk alias base/overlay authorization | true, `diagnostic_overlay` |
| Actual frontend selected surface | `RISK_ASMAE_DIAGNOSTIC` |
| Frontend availability | `available_overlay` |
| Ingredient-only counterfactual | Selected grid changes |
| Composite `diagnostic_only` | true |
| Composite `state_update_allowed` / `prescription_driver_allowed` | false / false |

This is **diagnostic selection and content leakage**, not a demonstrated physical-authority or prescription escalation. No React/DeckGL/browser materialization was executed, and the fixture does not establish normal field-run frequency. It nevertheless reaches the real scientific input, composite constructor, full policy/role authorization block and live UI's pure resolver. It therefore belongs to the bounded support/publication repair, rather than being explained solely by a future missing state picker.

The exact parent also authorizes the risk composite and responds to the ingredient counterfactual. Candidate improves raw biotic denial but does not compose that denial through its existing alias path.

Source chain: `surfaces/asmae.py:1360–1426` (pixel eligibility); `:1750–1849` (risk ingredients/composite); `runner.py:5186–5194` (generic RISK proof fallback), `:5196–5217` (surface gate); actual frontend `src/lib/agribrain/source-policy-display-resolver.ts:228–282,380–385` (priority/selection). The frontend's real-ASMAE switch is read from the same outer evidence-state fixture, rather than independently forced. Exact file identities are recorded rather than relying on these descriptive spans alone.

Recommended repair: use one qualified ingredient/publication predicate before composing risk, preserve each ingredient's support and exclusions, renormalize only eligible ingredient weights, and emit no finite risk grid when no eligible ingredients remain. Permit justified derived diagnostics under their declared role; do not demand direct observation of every diagnostic. The aggregate's permission must follow its qualified ingredients, not merely its RISK name plus global model proof.

## Residual G02 — restrictive status loses to historical update count

The probe constructs an actual native `StateSupportRecord` with:

```text
state=vigor
support_status=unsupported
observation_relationship=indirect
accepted_update_count=1
block_reasons=[local_support_revoked]
authority_ceiling=DIAGNOSTIC
```

The public ledger normalizer accepts this typed record. A historical accepted count alongside a present restrictive status is different from a malformed scalar. The native surface generator classifies its state **Unsupported**, with scouting/management/statistics denied. The exact current authorization block nonetheless allows its base/overlay as a diagnostic raster because the state predicate tests positive count before honoring the explicit restrictive status. It also ignores the explicit block reason.

The exact parent reproduces the same residual. No current normal engine path producing this particular revocation record is claimed; this is an admitted typed-contract boundary with a valid historical count. It warrants a monotone restriction rule so current exclusion cannot be undone by a previous accepted update.

The counterexample should be corrected before asserting that all accepted SIRE carriers fail closed to their per-state support. Define explicit current denial precedence before accepted counts and positive status aliases. Keep legitimate model/temporal/memory diagnostic roles separate from a rejected state.

Relevant source: `scientific_contracts/state_support.py:35–72`; `scientific_contracts/ledger_adapter.py:23–91`; `surfaces/asmae.py:482–505`; `runner.py:5143–5180`. Candidate/parent native provenance, normalized records and role authorization receipts are retained in `restrictive_status_case`.

## Negative controls and bounded future-state caution

The complete authorization block invokes the strict ledger adapter. Boolean, negative, NaN and fractional accepted counts all fail before a pixel authorization is produced. A local `int()` expression must not be used to claim that those malformed values pass the actual production composition. A legacy integer string is accepted by that existing compatibility normalizer; this review does not call that newly introduced behavior.

Current-spatial=false, spatial-raster=false, visualization=false and invalid pipeline-grid controls remain denied. A normally supported positive vigor fixture remains allowed. This confirms the residuals are not the consequence of disabling the outer gates.

The new stress-memory helper returns true for a normalized `unsupported`/zero-count record with relationship `none`, because the relationship alternative is not conditioned on an active memory/process status. Prior-only `none` passes too; model-propagated `none` also passes as a legitimate positive control. This is recorded as a **future-product/helper caution**: stress memory still has no dedicated SurfaceType/product in this batch, so the probe does not turn that helper result into a current rendered memory map or an independent Stage 3 omission blocker. Fix denial precedence and explicit accumulated-memory support before adding the future product.

Statuses such as `hypothesis_active`, `memory_accumulated`, `supported` and `active` appear in the new helper, but the existing strict canonical status normalizer does not accept those names. This lane uses canonical `assimilated`, `model_propagated`, `temporally_conditioned`, `prior_constrained` and `unsupported` controls and does not invent a new status schema to make a test pass.

## Evidence and reproduction

Candidate probe: **12/12** documented checks. Exact-parent probe: **10/10** checks, including the expected parent failures and inherited residuals. Actual frontend composition: **3/3** checks. These are different bounded probe counts, not a repository-suite total.

```sh
python3 review-f36-t09-9d7529a/gating/probes.py
python3 review-f36-t09-9d7529a/gating/probes.py --parent
node review-f36-t09-9d7529a/gating/frontend-risk.mjs
```

Both Python processes verify all 1,086 staged files before/after and bind native imports and isolated AST segments to Git blobs/SHA-256. The frontend script imports the actual unchanged production TypeScript resolver; the runner AST statement block executes without modifications. Synthetic carriers supply current lifecycle flags and global proof. Network connections are disabled by the Python harness. No repository tests/audits, full integrated runner, field measurements, HTTP/browser run, optimizer or physical execution are correctness proof.

Deliverables: `probes.py`, candidate and parent results/source receipts, `frontend-risk.mjs`, its fresh results, this report and the artifact manifest. Full F36/T09 calibration/acceptance and all 52 FA milestones remain open.


---

# Specialist appendix: Current ceilings and canonical permission parity

# Stage 1–2 integration and normative boundary review

Actual candidate: `9d7529afb411ddabb5fc8f46931cf098e10d9240`. Exact parent: `90ab701714554c7b786bba4ac6b19259e77279ce`. Repository tests, implementation reports and earlier audits are excluded as correctness evidence. This lane uses fresh production calls and source receipts. All 52 FA milestones remain open.

**The descriptor-level management cap is implemented and the original missing-ledger label fallback closes in the exercised native path. Two inherited permission-parity limits remain at downstream boundaries.** These are not newly introduced by this commit, and no physical action or full-runner authority escalation was executed.

## Original closures and compatibility

With actual native surface generation and an empty canonical per-state ledger, the candidate emits `support_class=unsupported` and `management_zone_eligible=false`. The exact parent emits `directly_assimilated` and management eligibility true for the same real-raster metadata. This independently confirms closure of the named global-real-raster label fallback; the classification lane separately reviews alternate proof paths and prior claims.

An explicit direct-proof fixture covering the eleven currently registered state types exercises the static descriptor cap. Candidate management eligibility is true only for `vigor` and `bare_soil_fraction`, exactly the two descriptors whose ceiling is `PRESCRIPTION_ELIGIBLE`; the parent grants it to all eleven. This is a well-formed classification carrier, not a claim that those state quantities were independently measured or calibrated in a field.

The changed `canonical_state_key` is used outside the authorization helper by native `get_var` in the composite renderer and by feature-bus compatibility aliases. Five existing legitimate aliases (`bare_soil`, `salinity`, `thermal`, `biotic_risk`, `phenology`) continue to retrieve their corresponding qualified numeric grids; legitimate zero remains zero. An actual native composite render produces byte-identical image output on both revisions for the same complete scientific fixture. Added surface aliases resolve to their expected states on candidate. No new compatibility regression was reproduced in these exercised paths.

## I1 — Diagnostic denial differs between provenance and canonical fields

Fresh ordinary production execution runs:

`build_state_support_ledger` → `index_state_support_ledger` → `generate_asmae_surfaces` → `generate_asmae_aliases` → `serialize_surface_artifact`.

The update report is an authored accepted-report carrier with a real-source/direct relationship, not an executed observation/filter update. It avoids hand-constructing an allegedly canonical ledger: the actual producer and canonical normalizer create that object. Geometry and arrays are valid, aligned 3×3 fixtures. Metadata deliberately states diagnostic use and `state_update_allowed=false`.

| Native ordinary canopy alias | Candidate | Exact parent |
|---|---|---|
| Provenance `diagnostic_only` | true | true |
| Provenance `state_update_allowed` | false | false |
| Provenance `prescription_driver_allowed` | false | false |
| Serialized top-level `state_update_allowed` | **true** | **true** |
| Serialized top-level `prescription_driver_allowed` | **true** | **true** |

The same contradiction appears after the candidate correctly classifies an empty-ledger raw state as Unsupported. Thus the repaired label does not by itself provide denial parity in the canonical output fields.

The cause is exact and narrow. `SurfaceArtifact` declares both permission fields with True defaults (`layer10_sire/schema.py:494–495`). Native state and alias constructors do not populate those dataclass fields (`surfaces/asmae.py:1310–1327,1664–1680`), even though they set denials inside provenance (`:1624–1633`). `_surface_value` selects a non-None attribute before provenance (`surface_contract.py:86–96`), and the canonical serializer publishes the resulting True values (`:125–170`). Both constructors and the serializer are ordinary production calls in the probe, without substituted code.

This serializer is also the function actually called by the orchestrator surfaces response (`orchestrator_v2/run_entrypoint.py:645–646`) and the standalone frontend bridge (`l10_frontend_bridge.py:187–191`). These call sites are source-traced, not executed as HTTP services. The inspected SIRE runner and invariant modules contain no assignments rebinding the two attributes after these constructors. The full integrated runner, current publication head and browser were not run, so the result is a demonstrated contradictory scientific envelope at a real consumer component, not a demonstrated accepted prescription or field actuation.

The ordinary alias retains `management_zone_eligible=false`, `direct_observation=false` and its diagnostic/no-prescription warning in provenance. Those additional restrictions should not be erased from the analysis. They qualify the downstream risk; they do not reconcile two canonical boolean fields with their own explicit denial.

**Bounded correction:** construct raw/alias artifacts with their actual allowed-use fields, and make canonical permission resolution preserve an explicit denial when multiple representations disagree. Verify raw Unsupported and supported diagnostic states as well as ordinary aliases. Keep legitimate permitted controls; do not create authorization from a field default. This can be a narrow publication-parity correction without implementing future state products or an action engine.

## I2 — Static descriptor ceiling is not the current per-state ceiling

The native ledger builder sets `authority_ceiling="DIAGNOSTIC"` (`layer05_asmae/feature_export.py:87`), including the accepted direct-report fixture. The canonical normalizer preserves that field and any block reasons (`scientific_contracts/ledger_adapter.py:55–78`). Candidate classification then derives management eligibility only from the descriptor maximum (`surfaces/asmae.py:555–572`) and ignores the current ledger ceiling and restriction reasons.

| Native vigor support carrier | Returned raw management eligibility, both revisions |
|---|---|
| Actual producer ledger, current ceiling DIAGNOSTIC | true |
| Same canonical record, current ceiling VISUALIZATION | true |
| Same record with VISUALIZATION and an explicit qualification block reason | true |
| Explicit lifecycle `support_status=unsupported` | false |

The first row uses an ordinary production-produced ledger. The stricter rows are controlled canonical restriction variants whose normalization succeeds; they are not claims about a currently observed field execution. An explicit Unsupported lifecycle continues to block the classification, providing a nonvacuous negative control.

This is an inherited per-state metadata limit. The new code correctly adds the static descriptor maximum, but a static maximum cannot supersede a lower current-state ceiling. Candidate and parent produce identical true eligibility under those lower ceilings. Native alias generation independently sets its management eligibility false, so the finding does not prove that the farmer alias authorizes management or any prescription.

**Bounded correction:** intersect the descriptor maximum with the current qualified support ceiling and applicable restrictions. Treat the ledger's runtime capability as a restriction, not an optional label. Define how block reasons affect display/statistics/management rather than promoting solely from a generic direct class.

## Plan/R3 relationship

F36 is a bounded slice of per-variable observability/support work (master plan:1072–1098); its full package still depends on F01/F02/F24/F29. T09 requires map, numeric and explanatory projections to retain one canonical state/support identity (master:1459–1485). R3 AB-L10-001 explicitly requires mask, geometry, resolution and authority to match the canonical state (full-text:10591–10593), while AB-ASM-016 says local certification does not grant global permission over every variable (10237–10241). The native current-ceiling field and permission booleans provide concrete contracts for this review; no hypothetical hardware checklist is introduced.

The desired next implementation can correct these component contracts without waiting for all full-package dependencies. Adding phenology/memory SurfaceTypes, expanding the expert inventory and GIS export remain later stages and are not treated as regressions in this review.

## Fresh evidence and limits

The scripts execute **14 cases and 19 observation checks on each exact revision**. All documented observations reproduce. The checks intentionally include confirmed limitations; their successful exit does not certify every desired scientific contract. Candidate imports 47 repository module identities; parent imports 45. All 1,086 staged files on each snapshot match the corresponding Git blobs and remain unchanged. Image equality, descriptor-cap differences and four restricted/empty-ledger comparisons are in `comparison.json`.

No production source or Git state was edited; no provider, full runner, HTTP service, browser, hardware, optimizer, training or action execution ran. No repository test total is claimed. The review does not independently validate F02 commit 075f19d; separation and branch ancestry belong to the coordinating review.

```sh
python3 review-f36-t09-9d7529a/integration/probes.py
python3 review-f36-t09-9d7529a/integration/probes.py --parent
```

`results.json`, `parent-results.json`, `comparison.json`, per-revision source manifests, line receipts and the artifact manifest retain the exact evidence.

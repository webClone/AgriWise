# AgriBrain F36/T09 independent corrective verification — 653da46

**Candidate:** `653da462360bf90a9ec0c05ce6d2c7fbea180520`  
**Exact immediate parent:** `8d9bd4a073e09a5081a85b8fd2f2b7654152e37a`  
**Branch:** `feat/f36-t09-asmae-13-state-publication`  
**Review date:** 22 October 2026, Africa/Algiers  
**Disposition:** S8D-01's full reported covariance group is verified repaired. One distinct, introduced P2 numerical exception remains. Keep the original closure recorded; fix checked standard-deviation squaring before an unconditional Stage 1–2 merge recommendation. All 52 FA rows remain open.

## 1. Decision

The reported covariance repair works. Empty nested rows, non-square/ragged/asymmetric/indefinite matrices and conflicting covariance/variance declarations now fail closed on both native routes. The five valid controls remain accepted, including genuine zero and singular positive semidefinite covariance. Earlier S81, S673 and S12 publication controls remain intact.

A separate new arithmetic path creates one bounded availability defect:

```python
prior_distribution = {"std": 1e200}
# The registered sigma alias has the same behavior.
```

The supplied value is finite, but its squared variance is not representable as a finite Python float. The new `resolved_var = resolved_std ** 2` raises `OverflowError` rather than returning malformed/unavailable proof. Both native ledger and metadata routes reproduce the exception. A fixture with a bad vigor prior and an independently qualified chlorophyll sibling aborts the entire native generator call. This is **S653-01, P2**.

The input is deliberately extreme. Normal field occurrence was not established. The finding concerns exception resilience at an admitted numerical boundary, not a demonstrated real-plot outage, incorrect prescription or hardware event. The parent returns for the identical std-only input; its prior acceptance is not endorsed as scientifically correct. The desired behavior is local rejection of unrepresentable derived variance, with valid siblings preserved.

**Recommendation:** add checked, finite variance derivation for `std` and `sigma`, cover the same arithmetic where variance is separately supplied, and replay the bounded matrix and sibling controls. Then reconsider the Stage 1–2 merge. Independent Stage 3 registry preparation can proceed; deferred capabilities and full-package acceptance remain separate.

## 2. Exact source, method and coverage

The refreshed GitHub ref points to the stated candidate, directly after `8d9bd4a`. The production commit delta is one file: `layer10_sire/surfaces/asmae.py`. It compiles. The attachment's discussions of `surface_contract.py` and `runner.py` describe cumulative retained work; those files are unchanged in this commit. Each of the two 1,086-file production/frontend snapshots matches its pinned Git blobs and SHA-256 manifest and remains unchanged after execution.

Three parallel lanes reviewed covariance/numerical behavior, retained map/alias authorization, and canonical permission/alias compatibility. The primary reviewer replayed the final harnesses and checked their observations. The supplied implementation report and repository test counts were treated as claims, not independent correctness proof. Repository tests and historical audits were not used as proof.

| Fresh component | Coverage |
|---|---|
| Classification and native generation | 94 helper +114 native cases per snapshot;42 grouped observations across the exact comparison |
| Native authorization/composites | 27 observation assertions per snapshot |
| Actual pure TypeScript selection | Nine checks per snapshot |
| Native integration | 26 case groups and48 assertions per snapshot |
| Consolidated root verification | Seven top-level replay commands and39 observation assertions |

All recorded observations reproduce. Zero process exits mean both repairs and the remaining exception reproduce; they do not mean every production contract passes or that the reported repository suite was independently rerun.

The Python harnesses deny socket connections and use inert authored grids/carriers. Production normalizers, generators, constructors, aliases and serializers execute. The complete SIRE authorization construction block and its required helpers are isolated by AST and executed unchanged, with source/AST receipts. Frontend checks execute actual pure TypeScript functions. Full runner/provider jobs, API/browser sessions, pixel materialization, optimization, prescriptions and hardware do not execute.

## 3. S8D-01 — original covariance group closed

**Production:** [services/agribrain/layer10_sire/surfaces/asmae.py:L64-L162](https://github.com/webClone/AgriWise/blob/653da462360bf90a9ec0c05ce6d2c7fbea180520/services/agribrain/layer10_sire/surfaces/asmae.py#L64-L162), [services/agribrain/layer10_sire/surfaces/asmae.py:L236-L278](https://github.com/webClone/AgriWise/blob/653da462360bf90a9ec0c05ce6d2c7fbea180520/services/agribrain/layer10_sire/surfaces/asmae.py#L236-L278).

Both native ledger normalization → generation and L1 raster metadata → generation were exercised. Candidate outcomes match the reported acceptance matrix:

| Reported invalid cases | Candidate outcome |
|---|---|
| Covariance-only `[[]]`, `[[], []]` | Unsupported; scouting False |
| Empty rows with otherwise finite parameters | Unsupported |
| Non-square and ragged matrices | Unsupported |
| Asymmetric matrix beyond declared symmetry tolerance | Unsupported |
| Indefinite `[[1,2],[2,1]]` | Unsupported |
| Conflicting `covariance` / `cov` | Unsupported |
| Conflicting scalar variance / covariance | Unsupported |

The exact parent reproduces these nine original failures. The candidate retains the five valid controls: covariance-only `[[0.0]]`, symmetric PSD matrix, singular zero matrix, scalar zero and a nonnegative diagonal vector. Invalid covariance does not abort siblings in these original fixtures.

The checks respect the implementation's declared absolute symmetry tolerance `1e-4` and eigenvalue tolerance `-1e-5`. Small negative eigenvalues within that declared tolerance are not manufactured into new findings. This report closes the concrete shape, symmetry, PSD and alias-consistency failures rather than reopening them under a different label.

All17 earlier malformed/incomplete distributions remain Unsupported on both routes; the four valid prior forms survive. Missing-ledger, bare-prior-label, scalar-variance, direct-count, direct/indirect support, verified-prior-flag and native `microzone_grid` controls retain earlier outcomes.

## 4. S653-01 — unrepresentable derived variance aborts generation

**Priority:** P2. **Status:** Open, introduced std-only numerical path.  
**Production:** [services/agribrain/layer10_sire/surfaces/asmae.py:L226-L234](https://github.com/webClone/AgriWise/blob/653da462360bf90a9ec0c05ce6d2c7fbea180520/services/agribrain/layer10_sire/surfaces/asmae.py#L226-L234).

### 4.1 Root cause

The new branch derives variance when only standard deviation is supplied:

```python
elif resolved_var is None and resolved_std is not None:
    resolved_var = resolved_std ** 2
```

The finite-real qualifier accepts `1e200`. Input finiteness does not imply the squared result is representable. Python raises `OverflowError` at line234. This is not converted into the validator's malformed result, so it propagates through `compute_asmae_support_classification` and `generate_asmae_surfaces`.

The largest finite double is about `1.798e308`; a finite standard deviation above its square root, about `1.341e154`, cannot yield a finite squared variance in this representation. The independent arithmetic receipt records this diagnosis; the actual impact is established by native calls, not by the arithmetic calculation alone.

### 4.2 Exact-parent native results

| Distribution | Exact parent | Candidate |
|---|---|---|
| `{"std": 0.5}` | Returns | Returns |
| `{"std": 1e150}` | Returns | Returns; squared variance remains representable |
| `{"std": 1e200}` | Returns prior classification | **OverflowError** |
| `{"sigma": 1e200}` | Returns prior classification | **OverflowError** |
| `{"std": 1e200, "variance": 1.0}` | OverflowError | OverflowError |

The first two exception rows are introduced on both native ledger and metadata routes. The last row is an inherited related squaring failure when explicit variance was already present. It is documented within the same numerical group, not counted as another regression. Fixing a shared checked-square operation should cover both branches.

The parent accepting std-only `1e200` does not prove that this is a scientifically valid prior. It shows that this commit newly turns the carrier into an unhandled native exception. Expected repaired behavior is Unsupported or an explicit unavailable diagnostic for the affected proof, not restoration of the parent's unqualified acceptance.

### 4.3 Sibling impact

A focused fixture includes an independently accepted indirect chlorophyll ledger and a vigor prior. With normal vigor standard deviation, native generation returns11 products and preserves chlorophyll's supported classification. Replacing only the vigor standard deviation with `1e200` raises before a surface list is returned. The parent returns for that same std-only fixture.

This proves a native batch-availability boundary: one unrepresentable prior prevents the otherwise valid sibling from being returned by this call. It does not establish an HTTP500, a full-runner failure mode, field incidence or physical effects. A higher-level caller may catch the exception; this review intentionally did not execute that full pipeline or infer its resulting status.

### 4.4 Bounded correction

Derive variance through checked arithmetic. Reject a standard deviation whose variance cannot be represented finitely, and convert arithmetic/conversion failures into the normal malformed-proof result. Do not merely replace exponentiation with unchecked multiplication: multiplication can silently produce Infinity, which would require an explicit finite-result check too.

Use the same checked derivation whether variance is absent or separately supplied, and for both `std` and `sigma`. Preserve valid zero, ordinary positive standard deviation and representable finite controls. An invalid coordinate should become Unsupported/unavailable with a reason, while unrelated qualified surfaces continue to be returned. Existing per-surface classification already supports malformed results; the numerical helper should reach that path rather than throwing.

| Required acceptance | Expected result |
|---|---|
| Std-only and sigma-only square overflow, both native routes | Local malformed/Unsupported result; no unhandled exception |
| Square overflow with explicit scalar variance | Same safe rejection |
| Valid zero and ordinary finite std | Existing valid outcome |
| Large but representable squared variance | Existing numerical admission policy preserved |
| Bad vigor plus qualified chlorophyll | Chlorophyll returned and retains qualified support |
| Original nine invalid/five valid covariance cases | S8D-01 closure preserved |
| Earlier S12/S673/S81 publication controls | Existing outcomes preserved |

**Receipts:** `classification/candidate-results.json` and parent counterpart: `native_cases.numeric_ledger_std_square_overflow`, `numeric_metadata_std_square_overflow`, corresponding `sigma_square_overflow`, `numeric_sibling_control` and `numeric_sibling_overflow`. Tracebacks identify the actual production path and line. `numeric-representability.json` contains the separate arithmetic diagnosis.

## 5. Retained publication controls

The five revoked dual-carrier cases remain denied through raw surface, ordinary alias and actual TypeScript selection. Complete restriction unions survive. Benign warnings remain selectable. All16 canonical restriction combinations remain correct. Native/canonical boolean permissions remain False across the diagnostic fixture's47 raw products and10 aliases, and the nine boolean-carrier combinations retain restrictive precedence.

The14 explicit authority/spelling controls and unknown-token controls retain their earlier repair. Physical zero and the actual diagnostic renderer image remain unchanged. Earlier risk/vegetation-attention value isolation, current ledger denial, own-variable water linkage and lifecycle blockers remain intact.

The positive registry fixture still contains13 helper names and11 actual registered state products. Phenology and stress memory remain deferred dedicated products. They are not treated as regressions of this covariance-only commit.

## 6. Qualifications, not additional blockers

### 6.1 Mixed covariance encodings

The new equivalence helper compares matching shapes, with an exception for single-element encodings. A multidimensional diagonal vector and an equivalent diagonal matrix are rejected when supplied redundantly as aliases, although each encoding is independently valid. This is conservative representation compatibility, not acceptance of contradictory covariance.

No ordinary producer emitting mixed-format aliases was established, and an intended cross-format alias-normalization contract was not specified. Document a same-encoding requirement, or normalize vectors to diagonal matrices if mixed formats are intended. This qualification is not another merge blocker and does not reopen the original scalar covariance-alias conflict closure.

### 6.2 Earlier inherited qualifications

Q8D-01 remains: the shared restriction resolver recognizes more mapping/provenance spellings than some admission, raw authorization and serialization callers consume. The exact inherited observations and their scope limits remain in the projection/integration appendices. No ordinary camel-case restriction emitter was established. Original canonical dual-carrier cases remain verified closed.

The metadata-only direct-proof path with no runtime ceiling still uses an inherited descriptor-based eligibility default, with action permissions False in the fixture. Normalized absent ledger authority defaults to DIAGNOSTIC. This remains a separate legacy-policy qualification, not a new blocker of the explicit authority-matrix repair.

## 7. Plan, R3 and proceed criteria

The master repair plan, execution addendum and task list match the candidate tree's Git blobs. Supplied R3 reference identities remain unchanged, including PDF SHA-256 `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`. Relevant requirements are AB-ARC-006 bounded degradation, AB-L10-001 faithful canonical projection, AB-ASM-003 per-state support, and the factorized authority/prohibition requirements AB-ARC-005, AB-ASM-011 and AB-ASM-016.

S653-01 concerns F36 prior-admission arithmetic and the F38/T11 boundary that preserves valid publication under local degradation. It does not imply those full packages or their calibration/operational requirements are complete. The narrower S8D-01 covariance closure is retained.

The normative register has exactly **52 open FA milestones and zero checked FA milestones**. Refreshed refs show main at `90ab701714554c7b786bba4ac6b19259e77279ce` and independent F02 at `075f19d318db6fa86d5988c2cabcb680dc17702e`. No production or remote Git changes were made during review.

For precise receipts, the candidate's immediate Git parent is `8d9bd4a`; `81cf8bb` and `67375aa` are earlier ancestors. The implementation report's cumulative lineage should use those labels consistently.

Fix the checked-square/sibling behavior and rerun the bounded controls before an unconditional Stage 1–2 merge recommendation. Independent Stage 3 registry preparation may continue. Stages3–6 remain otherwise deferred: dedicated products/catalog, expert selection, nodata versus physical zero, and integrated GIS/real-plot/browser receipts. No deferred capability is counted as a new defect here.

The claim register separates verified closures, one introduced numerical group and nonblocking qualifications. The evidence bundle includes fresh harnesses, observations, source/AST identities, normative material and a read-only source materializer. A new complete Git-object materialization was not executed; the seven lane commands and39 consolidated assertions were executed against byte-verified snapshots.


---

# Specialist appendix: Support classification

# Covariance and native numerical qualification review

Candidate `653da462360bf90a9ec0c05ce6d2c7fbea180520`; exact immediate parent `8d9bd4a073e09a5081a85b8fd2f2b7654152e37a`.

## Verdict

The full original S8D-01 covariance group is repaired. All nine invalid covariance fixtures now return Unsupported/scouting False on both native routes without aborting sibling surface generation. All five valid controls remain Prior-Constrained. The 17 earlier malformed distributions are rejected and four valid forms remain accepted. Earlier S12/S673 protections and positive controls remain intact.

A distinct introduced numerical availability boundary remains: a finite standard-deviation-only distribution such as `{"std":1e200}` raises OverflowError during its newly added conversion to variance. The same happens through the registered `sigma` alias. A malformed/unrepresentable derived variance should be rejected locally rather than aborting the native generator. This is recommended as one bounded P2 exception-resilience group, not a reopening of the verified covariance-shape/PSD closure.

## Method and fresh coverage

Run `python classification/probes.py` from the review root. It launches isolated candidate and exact-parent workers with socket connections denied, verifies all 1,086 source files against their pinned Git blobs before and after calls, and records imported-module identities. The source corpora remain unchanged.

Fresh coverage is **94 helper cases and 114 native cases per snapshot**. All **42 grouped observation assertions** reproduce. Successful replay includes repaired controls and a separately named numerical exception, not universal production acceptance.

The native cases use the actual support-ledger normalizer and/or L1SpatialData metadata carrier into unmodified `generate_asmae_surfaces`, with inert aligned 3×3 grids. Repository tests/audit reports are not correctness proof. No full runner/provider job, API/browser, optimizer, prescription or physical device executes. The extreme numerical fixture is deliberately authored and well outside ordinary agronomic uncertainty scales; normal field occurrence is not established.

## Original covariance closure independently verified

| Native fixture group | Exact parent | Candidate |
|---|---|---|
| Covariance-only `[[]]`, `[[],[]]` | Prior-Constrained | Unsupported/scouting False |
| Empty nested rows with finite mean | Prior-Constrained | Unsupported/scouting False |
| Non-square and ragged matrix | Prior-Constrained | Unsupported/scouting False |
| Asymmetric matrix | Prior-Constrained | Unsupported/scouting False |
| Indefinite `[[1,2],[2,1]]` | Prior-Constrained | Unsupported/scouting False |
| Conflicting covariance/cov aliases | Prior-Constrained | Unsupported/scouting False |
| Conflicting scalar variance/covariance | Prior-Constrained | Unsupported/scouting False |
| Covariance-only `[[0.0]]`, finite PSD, singular zero, scalar zero, diagonal vector | Valid prior controls | Valid prior controls |

Both ledger and metadata routes have the same candidate outcomes. All nine invalid native cases return the complete 11-surface collection with the malformed proof locally marked Unsupported, instead of throwing. There is no management or native state-update/prescription eligibility in the rejected diagnostic fixtures.

Declared tolerances are respected. This review does not report tiny negative eigenvalues within the implementation's declared PSD tolerance as a defect, nor require exact bitwise matrix symmetry in place of the documented symmetry tolerance. The counterexamples are the original unambiguous empty/shape/indefinite/conflict forms.

## Earlier closures and positive controls retained

- All 17 reported earlier malformed/incomplete alternate distribution forms now reject on both routes.
- All four finite/zero/alias alternate-prior controls remain accepted.
- Missing ledger plus real raster, bare prior labels and malformed scalar variance fail closed.
- Boolean/infinite count-only direct proof does not confer Observed; None/string counts return without aborting.
- Valid direct/indirect support, finite zero variance, literal actual-prior flags and native empty-producer `microzone_grid` support remain accepted.

## Introduced standard-deviation overflow

The current prior validator contains:

```python
elif resolved_var is None and resolved_std is not None:
    resolved_var = resolved_std ** 2
```

The finite-real qualifier accepts `1e200`. Its square exceeds finite float range, and Python raises OverflowError. The conversion at `surfaces/asmae.py:233–234` is not caught at the distribution or native generation boundary.

| Native authored input | Exact parent | Candidate |
|---|---|---|
| `prior_distribution={"std":0.5}` | Returns prior | Returns prior |
| `prior_distribution={"std":1e150}` | Returns prior | Returns prior; square is finite |
| `prior_distribution={"std":1e200}` | Returns prior | **OverflowError** |
| `prior_distribution={"sigma":1e200}` | Returns prior | **OverflowError** |
| `prior_distribution={"std":1e200,"variance":1.0}` | OverflowError | OverflowError |

The two standard-deviation-only exceptions are introduced by the new variance derivation on both native ledger and metadata routes. Overflow with a separately declared scalar variance was already present in the parent cross-check; it is recorded as inherited and not counted as another introduced failure. The desired repair should not preserve the parent's permissive prior label when the derived variance cannot be represented; it should reject the malformed/unrepresentable proof locally.

A stronger native sibling fixture isolates the effect. The ledger provides the extreme standard deviation only for vigor, while chlorophyll has valid accepted indirect support. With `std=0.5`, the native generator returns all 11 surfaces and the chlorophyll surface remains Indirectly-Constrained. Replacing only vigor's standard deviation with `1e200` raises OverflowError and prevents the generator from returning the surface collection. The parent returns the collection for the same extreme fixture. This proves bounded software availability impact on an otherwise qualified sibling, not merely an internal helper exception.

Receipts: `native_cases.numeric_ledger_std_square_overflow`, `numeric_metadata_std_square_overflow`, corresponding `sigma_square_overflow`, `numeric_sibling_control` and `numeric_sibling_overflow`, with exact-parent counterparts. The traceback ends at the new `resolved_std ** 2` line. Normal production occurrence, browser outage or physical action is not established.

## Bounded correction

Guard derived variance against arithmetic overflow and nonfinite results, returning `(False, True)` for unrepresentable supplied proof. Apply the same check to existing variance/std cross-validation so this numeric family is consistent. Do not clamp it to zero, invent uncertainty or relabel it as a valid prior. Preserve normal and large-but-representable finite controls, true zero, the original covariance matrix acceptance/rejection matrix and qualified sibling surfaces.

The source/import/observation receipts and artifact hash manifest accompany this lane. All FA rows remain open, and deferred product registration, expert selection, nodata and GIS work were neither assessed as completed nor modified here.


---

# Specialist appendix: Composites and exact authorization

# Retained projection, alias and frontend closures — 653da46

Candidate `653da462360bf90a9ec0c05ce6d2c7fbea180520`; exact immediate parent `8d9bd4a073e09a5081a85b8fd2f2b7654152e37a`.

## Verdict

The retained S81/S673/S12 publication controls pass fresh production-symbol probes in both snapshots. No new alias, authorization or pure frontend-selection regression was reproduced in this lane. The candidate changes only the ASMAE surface module's covariance qualification; the runner, surface schema, serializer and frontend resolver retain their prior source identities.

This is a bounded projection verdict, not a covariance sign-off or full F36/T09 acceptance. The covariance review is owned separately. The inherited restriction-vocabulary qualification remains documented and nonblocking; it is not reopened as a new defect.

## Method

The authored offline harness executes native L1SpatialData carriers, ASMAE surface generation, production SurfaceArtifact construction, alias generation and the actual pure TypeScript selection resolver. The complete production render-authorization construction statements and needed top-level helpers are extracted by AST and executed unchanged. No custom predicate replaces the production gates.

Fresh source checks verify every one of the 1,086 corpus files against pinned Git blob identities before and after execution. Native imports are recorded (49 source files in this lane), and source/AST receipts accompany each snapshot. Python socket connections are banned. The actual TypeScript invocation executes pure selection functions; no React/browser/HTTP, pixel materialization, full runner/provider job, optimization, prescription or hardware executes. Carriers and 3×3 numerical grids are inert authored inputs, not field observations. Normal production occurrence of malformed or alternate-key inputs is not established.

Replay:

```bash
python gating/probes.py
python gating/probes.py --parent
node gating/frontend-risk.mjs
node gating/frontend-risk.mjs --parent
```

Each snapshot reproduces 27 Python observation assertions and 9 actual frontend checks. Exit zero means these bounded controls and separately named inherited qualifications reproduce; it does not mean every production contract passes. Repository tests and historical audits are not used as correctness proof.

## Original dual-carrier closure retained

| Attribute restriction | Provenance restriction | Candidate raw / alias gate | Actual frontend |
|---|---|---|---|
| None | local_support_revoked | Denied / denied | Unselected |
| Empty list | local_support_revoked | Denied / denied | Unselected |
| reference_warning | local_support_revoked | Denied / denied | Unselected |
| local_support_revoked | reference_warning | Denied / denied | Unselected |
| support_revoked | local_support_revoked | Denied / denied | Unselected |
| reference_warning | Empty list | Authorized / authorized | Selected |

Both snapshots behave identically in this table. The ordinary canopy alias retains the complete restriction union, including distinct revocations, so the former benign-attribute masking failure stays closed. The benign warning control still produces an available overlay. Native state-update and prescription-driver permissions remain False in the diagnostic fixtures.

## Earlier publication controls retained

- An unsupported biotic ingredient has zero influence on the mixed qualified risk grid when its scale changes from 0.1 to 1.0. Qualified ingredients remain influential.
- With no qualified risk ingredients, no risk alias is emitted.
- Revoked typed conflict and incoming snake-case metadata restrictions yield zero influence on both risk and vegetation-attention composites.
- `restriction_reasons` metadata is preserved and isolated like canonical `block_reasons`.
- Current ledger unsupported/revoked declarations defeat historical accepted-update counts; a genuinely qualified indirect control remains allowed.
- Canopy water requires its own state support; vigor cannot qualify it. Root-zone water requires its own support; canopy water cannot certify it.
- The formerly unmapped state gates and surface-wetness family controls retain their fixes.
- The positive native fixture authorizes 11 actually registered state products. The matrix lists 13 helper-state names, but phenology and stress memory remain deferred dedicated products; they are not counted as present products or new regressions.
- Current-state, spatial-raster, visualization-permission and grid validity blockers remain enforced.
- Explicit empty risk ingredient lists remain denied.

## Inherited vocabulary qualification retained without expansion

The canonical helper recognizes more restriction spellings than some admission/gate callers consume. Incoming metadata `exclusion_reason` and camel-case restriction keys remain dropped by native generation; authored inputs using those fields can become authorized selected canopy aliases in both snapshots. For constructed camel-case provenance, the raw gate remains permissive but the ordinary alias canonicalizes the restriction and is denied. The canopy priority does not directly select raw ASMAE_VIGOR, so raw authorization alone is not reported as a displayed raw canopy map.

No ordinary production emitter of the additional camel-case restriction keys was found in the inspected production corpus. These are authored recognized-key carrier checks already documented as Q8D-01. This inherited compatibility limitation neither regresses in 653da46 nor reopens the verified canonical dual-carrier repair. It remains a qualification to universal all-carrier claims, not an additional merge blocker here.

## Receipts

`results.json` / `parent-results.json` contain state/product matrices, original dual carriers, lifecycle controls, composite counterfactuals and inherited vocabulary observations. `frontend-risk-results.json` and parent counterpart contain actual TypeScript selection results. Source receipts include before/after blob identities, imports, and the unchanged authorization AST block at runner.py lines 4989–5634, AST SHA-256 `3f76a593543157d6e82b921c91040e9f0270d065445fec488bf6ebd55c4138d0`.

All 52 FA milestones remain open. Dedicated product registration, expert selection, nodata and GIS/real-plot publication remain deferred; this lane does not implement them or confer full-package acceptance.


---

# Specialist appendix: Constructor, serialization and current ceilings

# Native covariance equivalence and canonical integration review

Candidate `653da462360bf90a9ec0c05ce6d2c7fbea180520`; exact immediate parent `8d9bd4a073e09a5081a85b8fd2f2b7654152e37a`.

## Verdict and method

The original covariance-alias and scalar-variance conflict fixtures are repaired. Fresh native ledger and metadata calls reject conflicting scalar covariance aliases and contradictory scalar variance/covariance values. Same-format valid scalar, vector and matrix aliases, equivalent single-element scalar/matrix representations, and matching variance/std declarations remain qualified.

Earlier S81 canonical restriction unions and S12 constructor/serializer permission denials remain intact. No additional blocking regression was established by this lane. A narrow representation-compatibility observation is recorded separately: equivalent multidimensional diagonal-vector and matrix encodings are not normalized across aliases. That qualification does not establish a requirement to support mixed encodings or a normal producer failure.

Run `python integration/probes.py` and `python integration/probes.py --parent`. Each snapshot records **26 case groups and 48 observation assertions**, all reproduced in fresh offline runs. The actual production support builder, canonical normalizer, native surface/alias generators and canonical serializer execute. The accepted-update report, aligned 3×3 grid and metadata are authored inert carriers, not verified field observations. Socket connection entry points are denied. No repository tests/audits serve as correctness proof; no full runner/provider, API/browser, optimizer, prescription or hardware executes.

All 1,086 source files per corpus match pinned Git blob identities before and after execution. Imported native module paths/hashes are recorded. Successful replay includes separately named qualifications and does not mean every production contract passes.

## Covariance/variance controls

The native matrix passes each distribution through both a canonical support ledger and L1SpatialData metadata into the unmodified generator:

| Distribution relationship | Parent | Candidate |
|---|---|---|
| `covariance=0.25`, `cov=0.25` | Prior | Prior |
| Scalar `0.25` and singleton matrix `[[0.25]]` | Prior | Prior |
| Identical `[0.25,0.5]` diagonal vectors | Prior | Prior |
| Identical `[[0.25,0],[0,0.5]]` matrices | Prior | Prior |
| `covariance=0.25`, `cov=1.0` | Prior | **Unsupported** |
| `variance=0.25`, `covariance=1.0` | Prior | **Unsupported** |
| Matching scalar variance/covariance | Prior | Prior |
| `std=0.5`, `covariance=0.25` | Prior | Prior |

The original mismatches therefore fail closed, and genuine positive controls remain accepted. In all tested diagnostic native outputs, management eligibility and state-update/prescription permissions remain False. These calls classify publication support; they do not demonstrate use of the supplied matrices in the EnKF or any physical execution.

### Representation qualification

Both `[0.25,0.5]` (the validator's declared diagonal-vector form) and `[[0.25,0],[0,0.5]]` describe the same covariance. When one is supplied under `covariance` and the other under `cov`, the new helper returns False because raw ndarray shapes differ and neither has size one. Both native routes consequently return Unsupported. The exact parent accepts the pair because it did not compare covariance aliases at all.

This is stricter representation compatibility, not proof that contradictory covariance is accepted. No ordinary producer emitting mixed-format aliases was established. If the intended alias contract requires the same encoding, document that constraint; if mathematically equivalent cross-format aliases are intended, canonicalize vectors as diagonal matrices before comparison. This lane does not add a merge blocker for an unspecified mixed-format capability.

Source: `layer10_sire/surfaces/asmae.py:126–153` defines covariance equivalence and scalar compatibility; lines 245–265 apply those comparisons. The helper's scalar-variance compatibility uses the first vector/matrix coordinate. No separate mismatch finding is asserted without a declared component/state binding for multidimensional prior structures.

## Retained canonical integration controls

- All 16 attribute/provenance restriction combinations preserve the ordered deduplicated union, including empty attribute plus revoked provenance and benign attribute plus distinct revocation. The original serializer masking closure remains closed.
- The native product fixture generates 47 raw products and 10 aliases. Constructor and canonical state-update/prescription-driver permissions remain False. These are not 47 latent coordinates or 47 authorized overlays.
- All nine absent/False/True boolean-carrier combinations retain explicit False precedence. A genuinely generic True dataclass with no denying provenance remains True; explicit object False remains False despite positive provenance.
- All 14 spellings of the seven declared authority enum values retain earlier behavior: only explicit prescription-capable runtime values allow management eligibility within descriptor maximum/current restrictions. Unknown nonempty tokens deny; normalized absent ledger authority defaults to DIAGNOSTIC.
- Static descriptor controls retain only vigor and bare-soil fraction as management-capable maxima in the positive fixture.
- Existing alias extraction retains physical zeros, and the actual diagnostic renderer image SHA-256 remains identical across snapshots: `3e4771d10670dfd8c486b1ac30b4580ef1833f52dad15f309adb541cae0e2264`.

## Inherited qualifications preserved

The shared restriction helper recognizes all six mapping spellings at root/provenance. Its serializer caller still forwards only root block_reasons/blockReasons plus provenance, omitting four additional root aliases. This remains the prior Q8D-01 caller-coverage qualification, not a new standalone authorization/display/execution finding. The other lane records exact authorization/frontend effects and their limits.

Metadata-only direct-proof records with absent runtime ceiling retain descriptor-based management eligibility in both snapshots, with action permissions False. Normalized missing ledger authority denies via DIAGNOSTIC. This inherited compatibility policy is not reopened as a new failure of the explicit authority-enum repair.

The root covariance lane separately owns the full S8D matrix/PSD/empty-row and numerical exception review. This integration verdict must be combined with that lane before declaring the entire candidate ready. All 52 FA milestones remain open; stages 3–6 remain deferred and are not treated as regressions here.

## Receipts

`results.json`/`parent-results.json` contain native `covariance_alias_native_matrix`, authority, restriction, permission and renderer cases. Source manifests include the complete before/after file identity lists and imported modules. `source-evidence.json` records relevant changed helper ranges and hashes. `artifact-manifest.json` binds the authored lane deliverables after the fresh replay. Production source bytes were not modified.

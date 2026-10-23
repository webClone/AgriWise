# AgriBrain F36/T09 independent corrective verification — 81cf8bb

**Candidate:** `81cf8bb351a640964a03d7f63d64e79b93344449`  
**Exact immediate parent:** `67375aa9ca0dfdc41c36d32e4105794b07e6b770`  
**Branch:** `feat/f36-t09-asmae-13-state-publication`  
**Review date:** 22 October 2026, Africa/Algiers  
**Decision:** The three original S673 counterexamples are repaired. Two adjacent P2 contract groups remain, including newly introduced projection/promotion paths. Hold unconditional Stage 1–2 closure pending these bounded corrections. All 52 FA rows remain open.

## 1. Findings and implementation decision

This batch successfully fixes the specifically reported failures. STATE_UPDATE and TRAINING_EXPORT no longer confer management eligibility in the explicit runtime-ceiling matrix. Incoming revocation survives the original raster-metadata path, and revoked ingredients have zero influence on both composites. The original malformed prior distributions and arbitrary spatial tag fail closed. Earlier S12 permission, missing-ledger, count and value-isolation controls remain intact.

Two gaps become visible when the newly added carriers and validator are exercised beyond the exact original fixtures:

| ID | Priority | Remaining defect | Verified downstream consequence |
|---|---|---|---|
| S81-01 | P2 | Standard alias construction selects one restriction carrier instead of combining them | A raw surface denied for revocation becomes an authorized, frontend-selected canopy alias when a separate benign attribute list overwrites its revoked provenance |
| S81-02 | P2 | Alternate prior validator accepts content-free family declarations and unchecked covariance contents | New metadata fallback labels these inputs Prior-Constrained/scouting eligible where the exact parent returned Unsupported |

These are bounded software-contract findings. The alias fixture retains False state-update and prescription-driver permissions. The malformed-prior fixtures retain False action permissions and management eligibility. The review demonstrates diagnostic publication/classification failures, not a prescription, optimizer result or physical execution.

**Proceed recommendation:** correct S81-01 and S81-02 on this review branch, repeat the original controls and the new boundary matrix, then reconsider the Stage 1–2 merge. Independent Stage 3 inventory preparation can proceed on its own scope, but should not be used to declare these support contracts complete. No full-package milestone is ready for sign-off from this review alone.

## 2. Evidence basis and scope

The branch ref and commit metadata were retrieved from GitHub. The candidate directly follows `67375aa`; four production modules changed: `layer10_sire/schema.py`, `surfaces/asmae.py`, `runner.py`, and `surface_contract.py`. All four compile. Each of the two 1,086-file production/frontend corpora matches its pinned Git blob/SHA-256 manifest and remains unchanged after the probes.

Three parallel review lanes inspected prior qualification, restriction/composite authorization, and runtime authority/canonical serialization. The primary reviewer replayed their final harnesses against both exact snapshots and checked the consolidated observations. Repository tests, historical audit reports and the supplied green test totals were not used as correctness proof. The attached implementation report was read as a set of claims to verify.

| Component | Fresh candidate / parent coverage | Result |
|---|---|---|
| Prior/direct-proof classification | 75 helper + 74 native cases in each snapshot | Original S12 and S673 controls pass; incomplete-distribution residuals reproduce |
| Native composites and exact authorization | 22 / 20 observation assertions | Original revocation paths repaired; competing restriction carriers expose alias loss |
| Actual pure TypeScript selection | 6 / 4 checks | Original selected risk grid becomes invariant; revoked-source canopy alias is still selectable in the new carrier fixture |
| Runtime authority and native serialization | 23 case groups per snapshot; 42 / 39 assertions | Explicit ceiling repair and permission parity retained; restriction-list projection inconsistency corroborated |
| Consolidated replay | Seven top-level commands, then 47 root observation assertions | Every documented repair/control/residual observation reproduces |

A zero-exit review replay reproduces repairs **and** the named defects. These figures are authored review observations, not a rerun or endorsement of the reported repository test suite.

Python harnesses deny socket connections. Native ledger builders/normalizers, surface and alias constructors, canonical serializers and pure frontend resolver functions execute. The SIRE authorization construction block and its required helpers are isolated by AST and executed unchanged; their source and AST identities are recorded. Full runner/provider jobs, live API/browser sessions, pixel materialization, optimizers, prescriptions and hardware do not execute. All numerical grids and restriction carriers are inert authored inputs. Normal field occurrence of malformed or competing-carrier inputs is not established.

## 3. Disposition of the reported S673 fixes

| Original finding | Independent result | Scope qualification |
|---|---|---|
| S673-01 | Repaired: all 14 declared enum/spelling cases now match explicit prescription capability; unknown nonempty tokens deny eligibility | Metadata-only direct proof with no runtime ceiling retains an inherited legacy default; documented separately below |
| S673-02 | Repaired for original single-carrier and incoming-metadata cases: restrictions survive, both composites isolate revoked inputs, valid siblings remain influential | A new dual-carrier alias/serializer projection gap remains as S81-01 |
| S673-03 | Repaired for the original string, NaN-mean/negative-variance and arbitrary spatial-token fixtures; valid zero/flags/native support retained | Incomplete family declarations, unchecked covariance and shadowed aliases remain as S81-02 |

Earlier S12 closures remain preserved: missing ledgers do not become observed merely because a scene is real; current ledger denials defeat historical accepted counts; own-state water support remains separate; constructor and canonical action permissions agree; invalid count-only proof does not confer Observed; None/string counts do not abort generation; bare prior labels and invalid scalar variances fail closed.

The native positive gate fixture still has 11 registered state products, despite 13 canonical helper names. Phenology and stress memory remain deferred dedicated products. No helper-only observation about those future products is promoted to a current publication failure.

## 4. S81-01 — competing restriction carriers lose revocation

**Relevant production:** [services/agribrain/layer10_sire/schema.py:L486-L498](https://github.com/webClone/AgriWise/blob/81cf8bb351a640964a03d7f63d64e79b93344449/services/agribrain/layer10_sire/schema.py#L486-L498), [services/agribrain/layer10_sire/surfaces/asmae.py:L1934-L1956](https://github.com/webClone/AgriWise/blob/81cf8bb351a640964a03d7f63d64e79b93344449/services/agribrain/layer10_sire/surfaces/asmae.py#L1934-L1956), [services/agribrain/layer10_sire/runner.py:L5242-L5262](https://github.com/webClone/AgriWise/blob/81cf8bb351a640964a03d7f63d64e79b93344449/services/agribrain/layer10_sire/runner.py#L5242-L5262), [services/agribrain/layer10_sire/surface_contract.py:L201-L205](https://github.com/webClone/AgriWise/blob/81cf8bb351a640964a03d7f63d64e79b93344449/services/agribrain/layer10_sire/surface_contract.py#L201-L205).

### 4.1 Original repair confirmed

The generator now carries incoming raster and ledger restriction reasons into provenance and the new SurfaceArtifact field. Both composite ingredient loops use the same revocation-aware predicate. In the original typed revoked-conflict fixture, scale 0.1 versus 1.0 yields the same risk and vegetation-attention grids. In the original incoming-metadata fixture, the emitted source preserves `local_support_revoked`, and the selected risk grid is invariant. Qualified siblings remain influential. The additional `restriction_reasons` metadata carrier is also tested.

### 4.2 New dual-carrier alias failure

The new dataclass field introduces a second declared place for restrictions. A well-formed SurfaceArtifact is constructed from an otherwise native vigor product with:

```python
block_reasons = ["reference_warning"]
provenance["block_reasons"] = ["local_support_revoked"]
```

The source passes through the unmodified alias constructor and exact authorization block. The raw gate combines both carriers and correctly denies the source. Standard alias construction instead uses:

```python
src_blocks = getattr(src_surf, "block_reasons", None) or prov.get("block_reasons")
```

Because the attribute list is nonempty, it replaces the distinct revoked provenance list. The alias now contains only `reference_warning` in both locations. The current gate no longer sees revocation and authorizes the alias.

| Stage | Observed result |
|---|---|
| Raw `ASMAE_VIGOR` source | Denied: `surface_blocked:local_support_revoked` |
| Alias restriction attributes and provenance | Only `reference_warning`; revocation lost |
| `CANOPY_ASMAE_VIGOR` authorization | Authorized diagnostic base/overlay |
| Actual TypeScript resolver | Selects the alias, `available_overlay`, preserving its 0.1–0.9 grid |
| Native action flags | `state_update_allowed=False`, `prescription_driver_allowed=False` |

Five carrier combinations distinguish this defect from general denial handling:

| Attribute restriction list | Provenance restriction list | Alias result |
|---|---|---|
| None | Revoked | Denied |
| Empty | Revoked | Denied |
| Benign nonempty | Revoked | **Authorized and selected** |
| Revoked | Benign nonempty | Denied |
| A revocation | A different revocation | Denied, though restrictive union still needs preservation |

This is an authored typed consumer-boundary fixture, not proof that ordinary native generation currently emits divergent lists. The full native generator normally writes matching lists, which is why the original test passes. The new attribute is absent from the exact parent's declared dataclass constructor, so the review does not fabricate an equivalent ordinary parent object to claim an exact before/after field execution. The field and alias precedence mechanism are introduced in this commit; the current native constructor → alias → authorization → pure frontend failure is established.

### 4.3 Canonical serializer corroboration

The canonical serializer uses attribute-first `_surface_value` for restriction lists. In its 16-case carrier matrix:

- Attribute `[]` masks provenance `['local_support_revoked']`, omitting the top-level block list.
- Attribute `['reference_warning']` masks that provenance in the top-level list.
- Nested serialized provenance still retains the revocation.

Serialization alone therefore establishes inconsistent projection, not total erasure of all restriction information. The standard alias is the stronger defect because it overwrites the revoked provenance as well and receives an actual positive authorization. Both belong to one restriction-continuity finding, not two independent severity counts. This does not reopen the earlier boolean False permission fix, which remains verified.

### 4.4 Bounded correction and acceptance

Resolve restriction carriers using one canonical, deduplicated union. Apply it consistently to raw surfaces, ordinary aliases, composites, canonical serialization and authorization. An empty or benign carrier must not erase another carrier's active revocation. Preserve different reasons and their lineage; do not select one list with `or` or attribute precedence.

Repeat the five alias carrier controls and all 16 serializer combinations. A revocation in any declared carrier must deny raw and alias authorization and prevent frontend selection. Keep valid non-revoked sibling controls selectable, and retain zero influence of revoked ingredients in both composites. Preserve existing False action permissions.

**Receipts:** `gating/results.json → dual_carrier_cases`; `gating/frontend-risk-results.json → dualCarrierSelection`; `integration/results.json → cases.constructor_serializer_block_carrier_matrix`.

## 5. S81-02 — alternate distribution validation remains incomplete

**Relevant production:** [services/agribrain/layer10_sire/surfaces/asmae.py:L63-L104](https://github.com/webClone/AgriWise/blob/81cf8bb351a640964a03d7f63d64e79b93344449/services/agribrain/layer10_sire/surfaces/asmae.py#L63-L104), [services/agribrain/layer10_sire/surfaces/asmae.py:L674-L717](https://github.com/webClone/AgriWise/blob/81cf8bb351a640964a03d7f63d64e79b93344449/services/agribrain/layer10_sire/surfaces/asmae.py#L674-L717), [services/agribrain/layer10_sire/surfaces/asmae.py:L735-L774](https://github.com/webClone/AgriWise/blob/81cf8bb351a640964a03d7f63d64e79b93344449/services/agribrain/layer10_sire/surfaces/asmae.py#L735-L774), [services/agribrain/scientific_contracts/ledger_adapter.py:L68-L85](https://github.com/webClone/AgriWise/blob/81cf8bb351a640964a03d7f63d64e79b93344449/services/agribrain/scientific_contracts/ledger_adapter.py#L68-L85).

### 5.1 Original repair confirmed

The reported string `not-a-distribution`, distribution with NaN mean/negative variance, and arbitrary spatial tag now yield Unsupported through the native ledger/normalizer/generator route. Invalid alternate proof also overrides a true prior flag or valid variance in the tested contradictory cases. Finite zero variance, valid finite distributions, zero standard deviation, supported numeric aliases, literal verified flags and native `microzone_grid` prior compatibility survive.

### 5.2 Current malformed inputs still qualify

The validator accepts a distribution if a `family` or `distribution` key merely exists, even with no content or numerical parameters. It also checks only the outer type of covariance lists and chooses numeric aliases by precedence without validating a conflicting supplied alias. Fresh native calls produce:

| Authored `prior_distribution` | Candidate metadata path | Exact-parent metadata path |
|---|---|---|
| `{"family": None}` | Prior-Constrained; scouting True | Unsupported |
| `{"family": False}` | Prior-Constrained; scouting True | Unsupported |
| `{"distribution": None}` | Prior-Constrained; scouting True | Unsupported |
| `{"mean": 0.2, "covariance": [[NaN]]}` | Prior-Constrained; scouting True | Unsupported |
| `{"mean": 0.2, "covariance": [[-1.0]]}` | Prior-Constrained; scouting True | Unsupported |
| Valid `variance` plus explicit invalid `var=NaN` | Prior-Constrained; scouting True | Unsupported |

These inputs supply no top-level prior variance, verified prior flag or qualified spatial support to independently justify the metadata prior label. The table's metadata rows are **introduced promotions**: the new alternate-proof metadata fallback accepts them where the exact parent returned Unsupported. Corresponding malformed ledger entries are accepted by both snapshots, so their continued acceptance is inherited. The review keeps these distinctions separate.

Native outputs remain diagnostic. Management eligibility and constructor state-update/prescription permissions are False. No browser observation or normal producer occurrence was established. The result is an epistemic classification error at a real accepted boundary, not an execution claim.

### 5.3 Root cause and bounded correction

`has_param` is an OR across mean, variance/std, or the existence of a family/distribution key. No meaningful family declaration or complete parameterization is required. List covariance contents are not checked for finite values or admissible variance. Where both canonical and alias keys are present, only the preferred one is checked; an explicitly invalid alternate can be ignored.

Define the supported prior-distribution forms explicitly. Require their actual parameters, validate every supplied numeric field, and reject contradictory or malformed aliases rather than allowing precedence to hide them. Either support covariance arrays with shape/numerical validity appropriate to the state, or reject that unsupported form. Content-free keys cannot prove a prior. Valid deterministic/zero-variance representations must remain supported through an explicit valid form; this review does not demand one universal distribution family or reject genuine model priors.

Retest both ledger and metadata routes with valid zero/finite controls, empty family declarations, nonfinite/negative covariance entries, conflicting aliases and malformed proof alongside otherwise valid flags. The expected result is Unsupported or a typed unavailable diagnostic, without aborting other valid surfaces. Preserve earlier S12 count/exception behavior and native empty-producer compatibility.

**Receipts:** `classification/candidate-results.json → native_cases.alternate_metadata_*`, with exact-parent controls; `classification/results.json → s673_repair_checks`, `s673_positive_controls` and `residual_observations`. Actual production calls receive native NaN floats; reported JSON uses tagged input representations so the evidence files remain strict JSON.

## 6. Runtime authority qualification outside the new blockers

All 14 explicit enum/spelling cases and unknown-token controls now behave correctly. Normalized ledger entries with absent authority receive DIAGNOSTIC and deny management eligibility. This closes the concrete S673-01 matrix failure.

A metadata-only direct-proof route without an explicit runtime ceiling still falls back to descriptor-based management eligibility in both snapshots. The positive restriction test is guarded by `if state_ceiling`; the missing/None/empty cases do not enter it. The review records this inherited compatibility behavior rather than presenting it as a newly introduced failure of the repaired enum cases. Therefore the phrase “only explicit positive current authority can ever grant eligibility” would still be broader than the implementation.

This legacy policy should be documented and addressed when unifying admission/authority defaults. It does not add a third new blocking group to this bounded review. The relevant native fixtures retain False action permissions. Explicit PRESCRIPTION_ELIGIBLE controls remain positive under their descriptor maximum.

## 7. Plan, R3 and governance

The master repair plan, execution addendum and task list match the candidate tree's exact Git blobs. The supplied R3 PDF remains SHA-256 `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; its scientific register and the copied plan cards govern the review. The bundle includes corrected literal-newline excerpts of the relevant requirements alongside the full supplied reference text.

| Requirement | Application |
|---|---|
| AB-L10-001 | Map/alias projection must preserve canonical authority, masks, geometry and resolution |
| AB-ARC-005 | Diagnostic inspection, state update, training, prescription and execution are separate capabilities |
| AB-ARC-006 | Degradation/restriction cannot be promoted by fallback |
| AB-ASM-003 | Per-state evidence and observability justify state influence |
| AB-ASM-011 | Per-variable prohibitions survive downstream use |
| AB-ASM-016 | Local certification cannot authorize all coordinates globally |

F36 owns support/prior/authority semantics; T09 owns faithful map projection and explanation. Restriction continuity through canonical publication also touches F38/T11. These are bounded implementation slices, not completion of those packages or their independent calibration/operational requirements.

The task register has exactly **52 open FA rows and zero checked FA rows**. Refreshed GitHub refs show main at `90ab701714554c7b786bba4ac6b19259e77279ce` and F02 at `075f19d318db6fa86d5988c2cabcb680dc17702e`. This review made no production or remote Git changes.

The attached report's heading still identifies candidate `67375aa` and parent `9d7529a`, although its body describes the S673 closure batch. Update those headings to candidate `81cf8bb` and parent `67375aa` before using it as the new implementation receipt. This is a traceability correction, not an additional code-defect group.

## 8. Next bounded work and deferred stages

1. Fix restriction union and projection once across alias/serializer boundaries; prove raw denial survives alias authorization and actual pure frontend selection.
2. Complete the supported alternate-prior schema; reject content-free, nonfinite and conflicting proof on both metadata and ledger paths without fallback promotion.
3. Repeat the original S673 and S12 controls, all declared current ceilings, valid physical zeros, positive siblings, constructor/canonical permission parity and current lifecycle blockers.
4. Refresh the report's commit identities and retain all 52 FA rows open. Then request or perform the final source review for the bounded Stage 1–2 merge decision.

Stages 3–6 remain deferred as agreed: two dedicated state products/catalog unification, expert 13-state selection, nodata preservation and integrated GeoTIFF/COG/real-plot/browser receipts. This report does not count those deferred features as new regressions or demand their implementation to close the two bounded groups above.

The claim register separates concrete original closures, the two remaining groups, inherited policy qualifications and deferred work. The evidence bundle contains fresh harnesses, exact observations, Git/source/AST identities, governing references and a read-only source materializer. A new full Git-object materialization was not executed here; the seven lane commands and 47 consolidated assertions were executed against independently staged, byte-verified snapshots.


---

# Specialist appendix: Support classification

# Independent alternate-prior and support-classification verification

Candidate: `81cf8bb351a640964a03d7f63d64e79b93344449`. Exact immediate parent: `67375aa9ca0dfdc41c36d32e4105794b07e6b770`.

## Bounded verdict

The three original S673-03 counterexamples are repaired: native ledgers with a string distribution, a distribution containing NaN mean/negative variance, or `spatial_support="not-a-raster"` now produce Unsupported rather than Prior-Constrained. The earlier S12 scalar/count/exception repairs and valid controls survive.

The broader distribution-qualification claim remains incomplete. The new validator still accepts content-free family/distribution declarations and non-finite or negative matrix covariance. These survive actual native normalization and surface generation. The newly added metadata fallback introduces an Unsupported → Prior-Constrained promotion for these malformed carriers; their ledger-path acceptance is inherited.

This is a P2 scientific metadata/qualification defect, not a demonstrated field occurrence or action execution. In the diagnostic native fixtures the result grants scouting eligibility, but management eligibility and native state-update/prescription-driver permissions remain False.

## Fresh method and receipts

Run `python classification/probes.py` from the review root. It starts isolated candidate and parent subprocesses, prohibits socket connections, verifies all 1,086 source files against Git blob identities before and after execution, and records imported module hashes. The native fixture uses actual L1SpatialData, production ledger canonicalization, and `generate_asmae_surfaces`; no production function is replaced.

Each snapshot records **75 helper cases and 74 native generator cases**. The overall observation register verifies:

- Nine retained earlier positive controls.
- Thirteen earlier S12 repair checks.
- Seven S673 repair/denial checks, including exact-parent reproduction.
- Three S673 positive-control groups.
- Three separately identified residual-observation groups.

All 35 grouped observations reproduce. A zero harness exit reproduces repairs **and** remaining defects; it is not a production all-pass verdict. Repository tests/audit reports and their reported passing counts are not used as correctness proof.

## Original closure controls

| Native case | Parent | Candidate |
|---|---|---|
| `prior_distribution="not-a-distribution"` in prior ledger | Prior-Constrained | Unsupported |
| Prior ledger with NaN mean and negative variance | Prior-Constrained | Unsupported |
| Prior ledger with `spatial_support="not-a-raster"` | Prior-Constrained | Unsupported |
| Invalid string distribution plus literal verified prior flag | Prior-Constrained | Unsupported |
| Invalid spatial proof plus valid zero variance | Prior-Constrained | Unsupported |
| Invalid spatial proof plus otherwise valid distribution | Prior-Constrained | Unsupported |
| Finite zero variance | Prior-Constrained | Prior-Constrained |
| Actual production empty-update ledger, microzone-grid support | Prior-Constrained | Prior-Constrained |
| Complete finite mean/variance distribution, including variance zero | Prior-Constrained | Prior-Constrained |
| Complete finite mean/std distribution, including std zero | Prior-Constrained | Prior-Constrained |
| Literal verified prior flag | Prior-Constrained | Prior-Constrained |

Complete `mu`/`sigma` aliases also remain supported. Valid alternate distributions supplied only through metadata newly qualify on the candidate, as intended. Bare labels, invalid top-level prior variance, malformed direct-count-only proof, and None/string count resilience remain repaired.

The review does not treat a recognized `microzone_grid` support tag as proof that an ordinary engine lacked a prior. Native prior compatibility is explicitly retained. The residual cases below use invalid numerical or content-free proof, not a rejection of legitimate unobserved model priors.

## Remaining P2: incomplete distribution validation and new fallback promotion

### A. Content-free family/distribution keys count as proof

These native metadata carriers provide no top-level prior variance, no verified prior flag, no spatial proof and no state ledger:

```python
{"prior_distribution": {"family": None}}
{"prior_distribution": {"family": False}}
{"prior_distribution": {"distribution": None}}
```

Each produces `ASMAE_VIGOR` with `support_class="prior_constrained"`, `evidence_class="Prior-Constrained"` and `scouting_zone_eligible=True` on the candidate. The exact parent returns Unsupported for the identical metadata-only inputs. A key existing in a dictionary is not a qualified distribution.

### B. Covariance-list contents are not checked

These malformed distributions also pass:

```python
{"prior_distribution": {"mean": 0.2, "covariance": [[float("nan")]]}}
{"prior_distribution": {"mean": 0.2, "covariance": [[-1.0]]}}
```

The candidate returns Prior-Constrained/scouting eligible through native metadata generation; the exact parent metadata path is Unsupported. The canonical ledger path retains the same malformed covariance and is accepted in both snapshots. A negative one-by-one covariance cannot represent valid variance; NaN covariance is not finite. Boolean and string covariance-list members also pass the current validator.

### C. Aliases and redundant parameters are not reconciled

Additional native observations show that `{"mean":0.2,"variance":0.25,"var":NaN}` ignores the invalid alias, and `{"mean":0.2,"variance":0.0,"std":1.0}` accepts mutually inconsistent dispersion claims. These support the same structural qualification issue, rather than a separate finding or a claim that such packets occur normally.

All these fixtures are authored boundary carriers. No normal field emitter or externally reachable mutation path was established. The metadata-only promotion is specifically an introduced regression relative to the exact parent; the analogous prior-ledger acceptance is inherited. Legitimate metadata-only alternate distributions are a valid extension, but malformed inputs must not acquire its authority.

## Source mechanics and bounded repair

`surfaces/asmae.py:63–103` checks covariance list **type**, without examining entries. `has_param` becomes true if any mean, variance, std, family or distribution key exists; family/distribution values are not validated. It can therefore return valid for a key whose value is None or False, or for mean plus invalid covariance.

`surfaces/asmae.py:735–774` newly consumes `has_valid_dist` in the metadata fallback, which explains the exact-parent Unsupported → Prior-Constrained change. The ledger branch at lines 674–717 uses the same validator. `scientific_contracts/ledger_adapter.py:68–84` preserves extra dictionary fields through normalization; the native receipts include the canonical ledger so this is not only a direct helper call.

Use a defined alternate-prior schema: validate every supplied numerical scalar/list element, covariance shape and valid variance; require sufficient qualified distribution content rather than any key's presence. Reject malformed supplied aliases or contradictory redundant parameters without promoting through another fallback. Preserve complete finite zero-variance distributions, verified flags, recognized genuine spatial support and valid model priors. No new stage-3 products or frontend feature is needed for this correction.

Relevant reproduction keys are `alternate_metadata_family_none`, `alternate_metadata_distribution_none`, `alternate_metadata_covariance_nan`, `alternate_metadata_covariance_negative`, and their `alternate_ledger_*` counterparts in candidate/parent result files. `source-evidence.json` records exact production function ranges and hashes; import/source receipts and tagged non-finite input representations are included. Actual production calls receive native NaN floats; strict JSON uses explicit tags only for recording.

All 52 FA milestones remain open. This lane does not assess or implement deferred stages 3–6.


---

# Specialist appendix: Composites and exact authorization

# Independent revocation/composite/publication lane

Candidate `81cf8bb351a640964a03d7f63d64e79b93344449`; exact immediate parent `67375aa9ca0dfdc41c36d32e4105794b07e6b770`.

## Verdict

The original S673-02 counterexamples are repaired. Current revocation survives native generation, and changing a revoked ingredient no longer changes either composite. The earlier S12 unsupported-input isolation and current-ledger denial controls remain repaired. A bounded adjacent restriction-merging failure remains in ordinary alias construction: a nonempty benign attribute list can overwrite a revoked provenance list. The raw surface is denied while its alias is authorized and selected by the actual pure frontend resolver.

The residual concerns conflicting supported restriction carriers on a freshly constructed native schema object. It is not evidence that a normal current producer emits such a conflict, that browser pixels were rendered, or that prescriptions or hardware executed. Diagnostic aliases retain False action permissions. The exact parent lacks the newly declared dataclass field, so the dual-carrier constructor case is recorded only on the candidate rather than manufacturing an equivalent parent capability.

## Fresh method and reproduction

Run these commands from the review root:

```bash
python gating/probes.py
python gating/probes.py --parent
node gating/frontend-risk.mjs
node gating/frontend-risk.mjs --parent
```

The Python runs have 22 candidate assertions and 20 parent assertions. The frontend runs have six candidate checks and four parent checks. All recorded observations reproduce. Successful exit means both the original closures and the residual counterexample reproduce; it is not a production all-pass result.

The harness executes the actual Layer10 L1SpatialData carrier, native surface generator, dataclass constructor, alias builder, and terminal publication/schema helpers. The production runner's complete authorization construction statements and required helpers are selected by AST and executed unchanged; all predicates and loops remain native. This avoids full runner/provider side effects. Source and AST identities, native module imports, source-before/after receipts and strict JSON observations accompany the report. Both corpora contain 1,086 source files verified against pinned Git blobs. Python socket connections are denied. The TypeScript call runs actual pure selection functions, with no React, browser, HTTP or pixel materialization.

## Original repairs and controls retained

| Counterexample / control | Parent | Candidate |
|---|---|---|
| Explicit revoked constructed CROSS_LAYER_CONFLICT; scale 0.1 vs 1.0 | Risk isolated; vegetation attention changes | Both composites invariant |
| Incoming raster metadata block_reasons; scale 0.1 vs 1.0 | Revocation dropped; risk and vegetation change | Revocation preserved; both invariant |
| Incoming restriction_reasons metadata alias | Both composites change | Both invariant |
| Unsupported biotic sibling alongside qualified thermal state | Risk invariant | Risk invariant |
| No qualified risk ingredient | No risk composite | No risk composite |
| Qualified ingredient changes | Composite changes | Composite changes |
| Current unsupported/named revoked ledger with accepted count 1 | Denied | Denied |
| Eleven supported, registered state products | Authorized | Authorized |
| Water own-state support and five formerly unmapped state gates | Retained | Retained |
| Current/raster/visual/grid lifecycle blockers | Denied | Denied |

For the repaired typed revocation and incoming metadata cases, both candidate scales produce risk first/last pixels 0.068/0.612 and vegetation attention first/last pixels 0.1000/0.9000. Changing the revoked source has zero effect. The actual frontend resolver selects the same diagnostic risk grid in both metadata runs. The parent instead changes risk from 0.0588/0.5294 to 0.0680/0.6120, reproducing the old counterexample.

This is still 11 actual dedicated products plus 13 helper identities. Phenology and stress memory products remain deferred; helper acceptance is not reported as an existing map product or a new blocker.

## Remaining P2: alias projection can erase one restriction carrier

The candidate schema declares SurfaceArtifact.block_reasons in addition to provenance block reasons. A fresh production dataclass instance is created from an otherwise native supported vigor surface with:

```python
block_reasons = ["reference_warning"]
provenance["block_reasons"] = ["local_support_revoked"]
```

Both fields are well-shaped lists. The attribute contains an advisory warning; provenance explicitly revokes support. The raw gate correctly unions both locations and rejects ASMAE_VIGOR with `surface_blocked:local_support_revoked`.

Ordinary alias construction at `surfaces/asmae.py:1934–1955` uses:

```python
src_blocks = getattr(src_surf, "block_reasons", None) or prov.get("block_reasons")
```

The nonempty attribute wins. The code replaces the copied provenance list with `list(src_blocks)` and supplies the same list to the alias constructor. The resulting CANOPY_ASMAE_VIGOR carries only `["reference_warning"]` in both locations. Native authorization now grants diagnostic base/overlay access. The actual TypeScript canopy resolver selects that alias as `available_overlay`, retaining its 0.1–0.9 grid.

| Carrier control | Raw gate | Alias gate | Actual frontend selection |
|---|---|---|---|
| Attribute None, provenance revoked | Denied | Denied | No surface |
| Attribute empty list, provenance revoked | Denied | Denied | No surface |
| Attribute benign nonempty, provenance revoked | **Denied** | **Allowed** | **Alias selected** |
| Attribute revoked, provenance benign | Denied | Denied | No surface |
| Distinct revoked reasons in both lists | Denied | Denied, but one reason is lost | No surface |

The two-revocation control also demonstrates lineage loss even where access remains denied. The main finding is the third row's permission reversal across the alias projection. It does not depend on a malformed scalar, arbitrary unknown field, reimplemented gate, or a fabricated current product.

This boundary is deliberately authored. Normal native generation now writes matching carrier lists and therefore does not trigger this conflict in the ordinary output fixtures. That limitation is material: the finding concerns the declared consumer contract and monotone restriction projection, not a verified normal field incident. The parent does not expose the new declared constructor field, and its older gates did not enforce the same carrier checks; this lane makes no unsupported introduced-regression claim.

The raw gate at `runner.py:5242–5262` already demonstrates the correct union behavior. The shared composite ingredient predicate at `surfaces/asmae.py:137–172` also combines both lists. Ordinary aliases need the same monotone union rather than a fallback choice. The separate integration lane checks canonical serializer handling of this dual-carrier contract; both seams should use a shared normalized restriction set.

## Bounded correction and acceptance

Union/deduplicate source attribute and provenance restriction lists before alias projection and serialization; preserve every explicit denial and its lineage. Never allow benign entries in one carrier to replace revocation in another. Keep genuine warning-only controls available and retain False state-update/prescription permissions.

Rerun the five dual-carrier controls above through native constructor → alias builder → exact authorization → actual frontend selection. The third row must remain denied, while a new warning-only positive control should stay available. Retain the original scale-invariance, valid-sibling influence and metadata-alias controls. No deferred product registration, expert UI, nodata or GIS export work is necessary for this correction.

Evidence locations: `results.json.consumer_boundary_cases`, `.restriction_alias_cases`, `.dual_carrier_cases`; `frontend-risk-results.json.metadataRevocation` and `.dualCarrierSelection`; exact-parent counterparts; source/AST receipts. All 52 FA milestones remain open; no production or remote Git changes were made.


---

# Specialist appendix: Constructor, serialization and current ceilings

# Authority, constructor and canonical serialization review

Candidate `81cf8bb351a640964a03d7f63d64e79b93344449`; exact immediate parent `67375aa9ca0dfdc41c36d32e4105794b07e6b770`.

## Scope and reproducibility

This lane ran fresh offline production ledger-builder → canonical normalizer → native ASMAE surface generator → native aliases → canonical serializer calls. The accepted direct report and 3×3 rasters are deliberately authored inert carriers, not new physical observations. Socket connections are rejected. No repository tests, old audit conclusions, provider jobs, full runner, API, browser or physical dispatch are used as correctness proof.

Run `python integration/probes.py` and `python integration/probes.py --parent`. The candidate has 23 case groups and 42 assertions; the exact parent has the same 23 case groups and 39 assertions. The additional three candidate assertions concern the newly declared block-reasons constructor field. All recorded observations reproduce. Successful replay includes separately named residual observations and does not mean all contracts pass.

Both 1,086-file corpora are Git-blob/SHA verified before and after execution; 47 imported native module identities are recorded. `source-evidence.json` pins the relevant production symbols and line ranges.

## S673-01: original runtime authority repair verified

The seven actual `AuthorityCeiling` values are exercised using both their lowercase values and uppercase names, for 14 variations. The native accepted direct-report ledger is normalized before generation, and raw vigor eligibility is read from generated provenance and canonical output.

| Current runtime ceiling | Parent raw management eligible | Candidate raw management eligible |
|---|---|---|
| VISUALIZATION | False | False |
| MONITORING_ONLY | False | False |
| DIAGNOSTIC | False | False |
| STATE_UPDATE | True | **False** |
| TRAINING_EXPORT | True | **False** |
| PRESCRIPTION_ELIGIBLE | True | True |
| PRESCRIPTION_DRIVER | True | True |

Unknown nonempty strings (`UNKNOWN_CAPABILITY`, `prescription`, `state-update`) are also denied on the candidate rather than falling through to the descriptor maximum. The parent's corresponding unknown-token fallback permits raw eligibility. The native normalizer supplies DIAGNOSTIC for absent or empty current ceiling in ledger records, and both snapshots deny these normalized cases.

Existing descriptor maxima remain intact: only vigor and bare-soil fraction can reach management eligibility in the explicit prescription-capable direct-support fixture. Current DIAGNOSTIC, VISUALIZATION and reference-cohort block controls remain denied. These observations close the reported S673-01 enum/unknown-token counterexamples. Canonical state-update and prescription-driver permissions remain False throughout the diagnostic native fixtures; raw eligibility does not establish actual prescription execution.

### Compatibility qualification: metadata-only direct proof without a ceiling

The supported metadata-only branch can declare `support_class="directly_assimilated"` and `direct_observation_count=1` with no ledger and no current authority ceiling. With missing, None or empty ceiling metadata, both snapshots still emit raw management eligibility True for vigor. Explicit STATE_UPDATE is now denied and explicit PRESCRIPTION_ELIGIBLE remains eligible.

This is inherited compatibility behavior, not one of the original enum counterexamples. Prior positive fixtures allowed descriptor-based eligibility on this path. It qualifies the universal wording that *only an explicit prescription-capable runtime token can ever grant eligibility*, but it is not classified here as a new merge-blocking defect. A future policy change should decide whether legacy absence must receive an explicit typed default; it should retain genuine direct classification independently from prescription permission. Action flags remain False in all these metadata fixtures.

## S12-03 permission parity remains repaired

The original native raw/alias constructor and canonical serializer contradiction does not recur. A fixture supplying current state and diagnostic grids produces 47 raw products and 10 aliases; all retain explicit constructor and canonical state-update/prescription-driver denials. These 47 products are not misrepresented as 47 latent states or authorized overlays.

All nine absent/False/True mapping-carrier combinations preserve restrictive boolean precedence. Generic constructor True permissions remain True when neither carrier denies them, and explicit False in either object attributes or provenance wins. Native missing-ledger states remain Unsupported. Existing scientific alias extraction preserves legitimate physical zero and its ordinary arrays.

The actual pre-existing diagnostic renderer image hash remains identical between snapshots: `3e4771d10670dfd8c486b1ac30b4580ef1833f52dad15f309adb541cae0e2264`. These are bounded compatibility controls, not a full browser or end-to-end product acceptance.

## New block-field serialization does not merge both restriction carriers

`SurfaceArtifact.block_reasons` is now a declared optional list. The canonical serializer supports both this new attribute and the existing provenance list but obtains the value using attribute-first `_surface_value`. It does not combine both. The 16-case carrier matrix uses production dataclass construction with None, empty lists, a benign reason and a revocation reason:

| New attribute | Existing provenance | Serialized top-level block reasons | Nested provenance |
|---|---|---|---|
| None | `["local_support_revoked"]` | Revocation retained | Revocation retained |
| `["local_support_revoked"]` | None | Revocation retained | Absent |
| `[]` | `["local_support_revoked"]` | **Omitted** | Revocation retained |
| `["reference_warning"]` | `["local_support_revoked"]` | **Benign reason only** | Revocation retained |

The simple one-carrier cases are repaired. The conflicting/empty attribute cases show that the new canonical top-level field is not a monotone union of current restrictions. This alone establishes metadata parity/lineage loss, not action escalation, because the nested provenance still holds the restriction. The separate gating lane follows the stronger related alias-construction case: a nonempty benign attribute can overwrite revocation in copied alias provenance, after which the alias can pass exact authorization. These should be treated as one bounded restriction-continuity finding rather than duplicate unrelated defects.

The parent had no declared block-reasons constructor field and did not serialize the top-level block field. Parent matrix observations with an attached Python attribute are identified in JSON by `constructor_field_declared=False`; they are not presented as an ordinary parent constructor path or proof of a newly introduced field occurrence in production.

## Relevant current source and bounded follow-up

- `layer10_sire/surfaces/asmae.py:790–820`: positive runtime capability membership; absence retains descriptor fallback.
- `layer10_sire/schema.py:496`: newly declared constructor block list.
- `layer10_sire/surface_contract.py:201–203`: attribute-first block list serialization.
- `layer10_sire/surfaces/asmae.py:1934–1936`: ordinary alias chooses a nonempty attribute before provenance and rewrites copied provenance.
- `layer05_asmae/state/descriptors.py:77–85`: actual authority enum used in the matrix.

Keep the verified enum and boolean-permission repairs. For restrictions, normalize and union both declared carriers before alias construction and canonical serialization; an empty or unrelated attribute cannot erase restrictive provenance. Retain reason identities and deduplicate deterministically. Re-run the conflict matrix, the alias authorization counterexample and qualified/empty-list positive controls. No deferred state registry, frontend selector, nodata or GIS implementation is needed for this bounded repair.

All 52 FA milestones remain open. This lane does not claim full F36/T09 acceptance or authorize a Git merge.

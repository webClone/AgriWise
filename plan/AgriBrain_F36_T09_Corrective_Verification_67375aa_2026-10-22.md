# AgriBrain F36/T09 Stage 1–2 corrective verification

**Candidate:** `67375aa9ca0dfdc41c36d32e4105794b07e6b770`  
**Exact immediate parent:** `9d7529afb411ddabb5fc8f46931cf098e10d9240`  
**Branch:** `feat/f36-t09-asmae-13-state-publication`  
**Review date:** 22 October 2026, Africa/Algiers  
**Disposition:** Original S12 counterexamples repaired; three bounded residual groups remain. Hold unconditional Stage 1–2 closure and merge recommendation pending those corrections. This is not a whole-repository or full-package acceptance report.

## 1. Decision and material findings

The corrective batch makes substantive, independently reproduced improvements. Unsupported ingredients no longer contaminate the original risk fixture; current ledger denials now override historical counts; native constructor and canonical serializer permissions agree; the original malformed prior/count cases fail closed without aborting generation. Valid support, real zeros, legitimate priors and qualified diagnostic surfaces survive.

The statement that all broader contracts are complete is premature. The remaining defects are:

| ID | Priority | Remaining boundary | Reproduced effect | Operational limit of the evidence |
|---|---|---|---|---|
| S673-01 | P2 | Runtime authority intersection | Declared `STATE_UPDATE` and `TRAINING_EXPORT` ceilings still yield raw `management_zone_eligible=True` | Canonical action permissions remain False; no prescription executed |
| S673-02 | P2 | Revocation continuity through native generation and both composites | Incoming raster metadata loses revocation; a revoked diagnostic source changes an authorized, frontend-selected risk grid. Explicit surface revocation also changes vegetation-attention values | Authored boundary carriers; normal producer incidence unestablished. Vegetation-attention overlay itself is denied |
| S673-03 | P2 | Alternate actual-prior proof | Malformed distributions and arbitrary nonempty spatial tags still become Prior-Constrained with scouting eligibility | Diagnostic/prior classification only; no management or state-update authority in the fixture |

All three behaviors are also accepted by the exact parent. They are incomplete repairs or overbroad closure claims, not newly introduced regressions. No demonstrated P1 physical execution failure was found within this bounded review.

**Recommended next step:** complete these three small contract repairs on the same review branch, rerun the original controls and the residual counterexamples, then reconsider the Stage 1–2 merge. Independent Stage 3 registry preparation can proceed separately if useful; it should not obscure the remaining support-contract work or close an FA milestone.

## 2. What was actually verified

GitHub's branch ref and commit metadata were retrieved directly. The candidate is a direct child of the reviewed parent. Four production Python files change: `layer10_sire/runner.py`, `layer10_sire/surface_contract.py`, `layer10_sire/surfaces/asmae.py`, and `scientific_contracts/state_support.py`. They compile successfully. All 1,086 files in each review corpus match their pinned Git blobs and SHA-256 manifests and remain unchanged after execution.

Three parallel review lanes checked classification, composites/authorization, and native permission integration. The primary reviewer completed the composite follow-through and replayed every lane from the consolidated snapshot. Evidence comes from fresh calls to production symbols and exact-parent controls. Existing repository tests, historical audit documents, the supplied implementation report and its reported green totals were not used as correctness proof.

| Review component | Fresh coverage | Result |
|---|---|---|
| Classification | 54 helper cases + 29 native generator cases in each snapshot | 13 original repair checks and nine positive controls pass; alternate-prior residuals reproduce |
| Native gates and composites | 19 assertions per snapshot; 13 helper-state rows, 11 actual registered products | Original risk leakage and current-ledger denial fixed; revocation residuals reproduce |
| Actual frontend selection | Four checks per snapshot using production TypeScript resolver | Original risk value isolation preserved; metadata-revoked source still changes selected risk values |
| Native integration | 20 case groups and 34 assertions per snapshot | Constructor/serializer parity and cited lower ceilings fixed; broader enum ceiling defect reproduces |
| Consolidated replay | Seven top-level commands, followed by 35 root observation assertions | All recorded observations reproduce, including the named defects |

A successful harness replay means both repairs and remaining counterexamples reproduce. These are authored review probes, not an independent rerun of the claimed repository test suite.

The Python harnesses reject socket connections. Native generators, alias builders, canonical normalizers/serializers and pure frontend functions execute. For the large SIRE runner, its full authorization construction statements and required helper definitions are selected by AST and executed unchanged; source and AST hashes record the isolation. The full runner, remote providers, API, browser, optimizer, prescription dispatch and physical devices do not execute.

## 3. Disposition of the five reported repairs

| Reported group | Independently verified closure | Remaining qualification |
|---|---|---|
| S12-01 | Unsupported labels are excluded; changing unsupported biotic values has zero effect; no risk composite when no ingredient qualifies; explicit empty ingredient list denied | Revocation is not uniformly preserved and consumed; S673-02 |
| S12-02 | Current unsupported/named revocation ledger entries override count=1; DIAGNOSTIC/VISUALIZATION/current blocks deny raw management eligibility | STATE_UPDATE/TRAINING_EXPORT omitted from restrictive ceiling handling; S673-01. Metadata restriction continuity also remains incomplete |
| S12-03 | Native raw and alias constructors preserve False; canonical serializer honors explicit False from either tested carrier | Closed for tested constructor and canonical boolean permission paths |
| S12-04 | Bare labels and invalid supplied scalar variances fail closed; explicit false prior flags win; finite zero variance remains valid | Alternate proof fields are not validated; S673-03 |
| S12-05 | Boolean/infinite count-only proof no longer produces Observed; None/string counts do not abort native generation; positive numeric counts still work | Closed for the reported numerical and exception counterexamples |

The legitimate independence of proof channels matters. A normalized accepted direct observation relationship is distinct from a malformed count supplied as the only proof. The review does not treat every zero-count record with an explicit direct relationship or literal direct-observation flag as a numerical bypass. Similarly, genuine model prior grids must remain inspectable as priors even when they are not observed.

## 4. S673-01 — incomplete runtime authority intersection

**Source:** [services/agribrain/layer05_asmae/state/descriptors.py:L77-L85](https://github.com/webClone/AgriWise/blob/67375aa9ca0dfdc41c36d32e4105794b07e6b770/services/agribrain/layer05_asmae/state/descriptors.py#L77-L85); [services/agribrain/layer10_sire/surfaces/asmae.py:L648-L684](https://github.com/webClone/AgriWise/blob/67375aa9ca0dfdc41c36d32e4105794b07e6b770/services/agribrain/layer10_sire/surfaces/asmae.py#L648-L684).

The descriptor's maximum and the currently supported permission are separate constraints. A state whose static maximum is PRESCRIPTION_ELIGIBLE may currently be limited to STATE_UPDATE or TRAINING_EXPORT. The repaired function only recognizes a short negative list of lower ceilings. The project's own valid enum contains two additional non-prescription values that the list omits.

The reproduction starts with the actual production ledger builder and an inert accepted direct-report fixture, substitutes only the current ceiling, and passes the record through the native normalizer, surface generator and canonical serializer. Both declared enum values and uppercase names are exercised:

| Current ceiling | Candidate raw vigor management eligibility |
|---|---|
| VISUALIZATION | False |
| MONITORING_ONLY | False |
| DIAGNOSTIC | False |
| STATE_UPDATE | **True** |
| TRAINING_EXPORT | **True** |
| PRESCRIPTION_ELIGIBLE | True |
| PRESCRIPTION_DRIVER | True |

The two highlighted outcomes contradict factorized runtime authority. This is a metadata eligibility defect; the same diagnostic fixtures retain False state-update and prescription-driver permissions in the native constructor and canonical output. No downstream command was issued or inferred.

**Bounded correction:** use a typed, positive capability predicate for prescription-capable runtime authority, intersected with the descriptor maximum and active restrictions. Deny unknown ceilings. Preserve explicit boolean permission denials and positive PRESCRIPTION_ELIGIBLE controls. Do not infer a universal ordering of unrelated capabilities merely from enum declaration order.

**Reproduction:** `integration/results.json → cases.runtime_enum_ceiling_matrix`. The parent matrix documents the inherited acceptance. Acceptance should cover every declared enum value in both supported spellings and ensure only explicitly prescription-capable current authority can grant management eligibility.

## 5. S673-02 — revocation is lost or inconsistently consumed

**Source:** [services/agribrain/layer10_sire/surfaces/asmae.py:L1231-L1303](https://github.com/webClone/AgriWise/blob/67375aa9ca0dfdc41c36d32e4105794b07e6b770/services/agribrain/layer10_sire/surfaces/asmae.py#L1231-L1303), [services/agribrain/layer10_sire/surfaces/asmae.py:L1801-L1814](https://github.com/webClone/AgriWise/blob/67375aa9ca0dfdc41c36d32e4105794b07e6b770/services/agribrain/layer10_sire/surfaces/asmae.py#L1801-L1814), [services/agribrain/layer10_sire/surfaces/asmae.py:L1885-L1905](https://github.com/webClone/AgriWise/blob/67375aa9ca0dfdc41c36d32e4105794b07e6b770/services/agribrain/layer10_sire/surfaces/asmae.py#L1885-L1905).

### 5.1 Original unsupported-value leakage is repaired

With qualified thermal support and unsupported biotic risk, varying biotic scale from 0.1 to 1.0 produces identical candidate risk grids, first/last pixels 0.068/0.612. The parent changes from 0.0418/0.3759 to 0.068/0.612. The actual frontend resolver confirms the candidate's selected grid is unchanged. Qualified ingredient changes remain influential, so the fix is not achieved by disabling all composites.

### 5.2 Constructed-surface revocation differs between composites

A fresh production SurfaceArtifact instance is constructed from a native diagnostic surface, preserving its geometry and other fields while explicitly declaring `block_reasons=["local_support_revoked"]`. Risk correctly excludes it. Vegetation attention only checks Unsupported labels and pixel eligibility, so the revoked source still contributes.

| Revoked cross-layer-conflict scale | Risk first / last pixel | Vegetation attention first / last pixel |
|---|---|---|
| 0.1 | 0.068 / 0.612 | 0.0595 / 0.5355 |
| 1.0 | 0.068 / 0.612 | 0.1000 / 0.9000 |

The exact current authorization code denies the vegetation-attention overlay with `surface_state_requirement_unmapped`. This subcase proves a generated composite/value and claim-parity defect; it does not prove that vegetation attention is currently displayed.

### 5.3 Incoming raster metadata loses revocation before the risk filter

The stronger boundary probe supplies the local revocation in the raw `L1SpatialData.raster_metadata` carrier before native surface construction. The generator rebuilds provenance without copying that restriction. The risk qualifier therefore sees a derived diagnostic ingredient without the block.

| Scale of the metadata-revoked source | Risk first / last pixel | Production authorization receipt | Actual pure frontend resolver |
|---|---|---|---|
| 0.1 | 0.0588 / 0.5294 | Authorized diagnostic overlay | Selects resulting risk grid |
| 1.0 | 0.0680 / 0.6120 | Authorized diagnostic overlay | Selects changed risk grid |

This trace runs native generation → native composite → exact complete authorization block → actual TypeScript selection. It establishes a consumer-boundary restriction leak. The raw metadata carrier was deliberately authored; a normal production emitter, live plot occurrence, browser pixels and operational actions were not established. The parent has the same leak.

**Bounded correction:** preserve current restrictions from incoming metadata into canonical surface provenance, and use a common ingredient support/revocation predicate for both composites. Retain reasoned exclusions. Test scale invariance for unsupported and revoked inputs independently, with valid siblings, through canonical serialization and pure frontend selection. Keep ordinary qualified diagnostic contributions available.

**Reproduction:** `gating/results.json → consumer_boundary_cases.typed_surface` and `.metadata`; `gating/frontend-risk-results.json → metadataRevocation`. Do not conflate the denied vegetation surface with the authorized risk surface.

## 6. S673-03 — alternate prior fields remain unqualified

**Source:** [services/agribrain/layer10_sire/surfaces/asmae.py:L550-L579](https://github.com/webClone/AgriWise/blob/67375aa9ca0dfdc41c36d32e4105794b07e6b770/services/agribrain/layer10_sire/surfaces/asmae.py#L550-L579); [services/agribrain/scientific_contracts/ledger_adapter.py:L68-L85](https://github.com/webClone/AgriWise/blob/67375aa9ca0dfdc41c36d32e4105794b07e6b770/services/agribrain/scientific_contracts/ledger_adapter.py#L68-L85).

The new strict scalar predicates correctly reject bare prior labels and malformed top-level variance. However, the ledger prior branch accepts `bool(prior_distribution)` or any nonempty spatial-support tag except a few strings as alternative actual-prior proof.

Fresh native normalization and generation accept this record without top-level variance or verified prior flag:

```python
{"vigor": {
    "state": "vigor",
    "support_status": "prior_constrained",
    "prior_distribution": {"mean": float("nan"), "variance": -1.0},
}}
```

The result is `support_class="prior_constrained"`, `evidence_class="Prior-Constrained"`, `scouting_zone_eligible=True`. A string `prior_distribution="not-a-distribution"` or `spatial_support="not-a-raster"` is also accepted. No management eligibility or state-update permission is granted in these probes.

The adapter preserves extra dictionary fields, while spatial support is stringified; neither validates the asserted proof. Thus malformed data survives the native boundary before the classifier treats nonemptiness as proof. The parent also accepts it under its broader prior-label rule. This is a residual qualification gap in the broad strict-prior claim, not an introduced regression.

The real empty-update ledger builder initializes `spatial_support="microzone_grid"` for all states. That compatibility control remains accepted. Its existence is not proof that an actual engine run had no model prior; nor should ordinary raster geometry alone be advertised as a verified prior reference.

**Bounded correction:** validate alternate distributions structurally and numerically, reject malformed supplied proof without switching to another permissive fallback, and tie spatial-prior proof to a recognized state/grid artifact or explicit verified prior receipt. Preserve finite nonnegative variance including 0.0, genuine flags and legitimate model/raster priors. Do not relabel valid unobserved priors as direct observations.

**Reproduction:** `classification/candidate-results.json → native_cases.native_ledger_prior_distribution_nan`, `_distribution_string`, and `_spatial_nonraster`, with exact-parent counterparts. Extend the acceptance matrix to contradictory/malformed alternate proof, not only `prior_variance`.

## 7. Governing plan and R3 monograph

The three governing plan files match the candidate's Git tree exactly. The supplied R3 PDF retains SHA-256 `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; its extracted requirement register was read alongside the master plan and task list. Review artifacts are supporting records, not normative substitutes.

| Governing requirement | Relevance to this bounded batch |
|---|---|
| AB-ASM-003 | State-specific influence must be supported by operators, covariance and observability |
| AB-ASM-011 | State-specific weights and prohibitions survive downstream use |
| AB-ASM-016 | Local certification does not grant global permission across variables |
| AB-ARC-005 | Visualization, diagnosis, state update, training, prescription and execution remain distinct |
| AB-ARC-006 | Degraded capability cannot be promoted by a fallback |
| AB-L10-001 | Projection retains canonical masks, geometry, resolution and authority |

F36 owns the per-state support/calibration semantics; T09 owns consistent map projection and explanation. Constructor/serializer restriction continuity also touches the F38/T11 integration boundary. This review concerns a bounded F36/T09 implementation slice. Full F36 additionally depends on F01, F02, F24 and F29, and full T09 has its own plan dependencies. Those package obligations are not closed by these probes.

The normative register contains exactly **52 open FA rows and zero checked FA rows**. Main remains `90ab701714554c7b786bba4ac6b19259e77279ce`; the independently scoped F02 branch remains `075f19d318db6fa86d5988c2cabcb680dc17702e` in the refreshed refs. This verification made no production or remote Git changes.

## 8. Deferred work and proceed criteria

Stages 3–6 remain deferred as agreed: register dedicated phenology/stress-memory products and unify the inventory; implement expert state selection; preserve nodata independently from physical zero; integrate GIS publication and real-plot/browser receipts. The 11-product current registry is not misreported as complete 13-state publication. Future stress-memory helper behavior is documented separately from actual current products.

Before an unconditional Stage 1–2 merge recommendation:

1. Close S673-01 using the entire declared authority enum and valid positive controls.
2. Close S673-02 at both incoming metadata and constructed-surface boundaries; prove zero influence from revoked ingredients while retaining qualified siblings.
3. Close S673-03 with typed alternate-prior proof and no invalid-input fallback promotion.
4. Replay original S12 closures, own-state gates, canonical permission parity, physical-zero controls and current lifecycle blockers.
5. Preserve all 52 FA rows open. Full package or field acceptance remains a separate plan decision.

The accompanying claim register separates original closures, residual groups, scope limits and deferred items. The evidence bundle contains reproducible authored harnesses, exact observations, source/AST identities, pinned plan material and a read-only Git object materializer. Source bytes can be reconstructed from the pinned commits without checking out or modifying the source repository. The materializer is supplied for reproducibility; a fresh full Git-object materialization was not executed in this review environment.


---

# Specialist appendix: Support classification

# Independent classification / prior / direct-proof lane

Candidate: `67375aa9ca0dfdc41c36d32e4105794b07e6b770`. Exact immediate parent: `9d7529afb411ddabb5fc8f46931cf098e10d9240`.

## Verdict

The original S12-04 label/scalar counterexamples and S12-05 count/exception counterexamples are repaired. Fresh calls preserve valid positive controls. S12-05 can be closed for its bounded claims. S12-04's broader claim of strict actual-prior qualification still needs qualification: alternate purported proof fields are accepted without validating their content. This remaining acceptance is inherited rather than a new regression.

This lane used production classifier and native `generate_asmae_surfaces` calls; it did not run repository tests, full runner/provider workflows, browser sessions, or physical devices. User-reported regression counts are not independent evidence here.

## Method and receipts

Run `python classification/probes.py` from the review root. It starts isolated candidate and exact-parent subprocesses, rejects network connections, verifies all 1,086 snapshot files against pinned Git blob identities before and after calls, and records imported-module identities. The scripted run has 54 helper cases and 29 native generator cases in each snapshot: 166 boundary observations total, plus 11-state descriptor ceiling matrices. JSON uses explicit tagged representations for NaN/Infinity in reported inputs; actual production calls receive native float values.

`results.json` contains 13 original repair/monotonicity checks and nine retained controls, all true. A successful replay means the recorded observations are reproduced; it does not establish all scientific contracts or full package acceptance.

## Verified repair matrix

| Input or control | Parent | Candidate | Disposition |
|---|---|---|---|
| Native metadata with bare `support_class=prior_constrained` | Prior-Constrained; scouting true | Unsupported; scouting false | Repaired |
| Native ledger with bare `support_status=prior_constrained` | Prior-Constrained; scouting true | Unsupported; scouting false | Repaired |
| Native prior variance NaN, negative, positive infinity, boolean false, or numeric string | Invalid values accepted as prior in affected paths | Unsupported | Repaired |
| Valid prior variance `0.0` | Prior-Constrained | Prior-Constrained | Zero preserved |
| Valid positive variance / explicit `has_actual_prior=True` | Prior-Constrained | Prior-Constrained | Positive controls preserved |
| Explicit `has_actual_prior=False` alongside valid variance | Prior-Constrained | Unsupported | Restriction now wins |
| Explicit NaN variance alongside true prior flag | Prior-Constrained | Unsupported | Invalid supplied scalar now wins |
| Native metadata direct count `True` or positive infinity | Observed/direct true | Indirectly-Constrained/direct false | Repaired |
| Native metadata direct count `None` or string `"1"` | TypeError aborts generation | Returns all 11 state surfaces, direct false | Repaired |
| Native metadata direct count `1` | Observed/direct true | Observed/direct true | Positive control preserved |
| Missing ledger plus real raster | Unsupported in this immediate parent | Unsupported | Earlier repair retained |
| Valid accepted indirect ledger | Indirectly-Constrained | Indirectly-Constrained | Positive control preserved |
| Typed enum helper indirect relationship | Prior misclassification at helper boundary | Indirectly-Constrained | Additional improvement |

The native generator normalizes input ledgers before classifying. `canonicalize_state_support_record` initializes canonical direct count to zero while preserving the explicit observation relationship; therefore a valid `assimilated` ledger with one accepted update and relationship `direct` remains direct even with canonical count zero. Metadata can also declare an independent literal `direct_observation=True`. These semantic-proof paths are distinguished from count-only numerical qualification; their existence alone is not reported as a S12-05 regression or count-only bypass.

## Remaining actual-prior proof qualification

### P2 — Alternate prior proof fields are not validated

Native reproduction `native_ledger_prior_distribution_nan` supplies an inert aligned 3×3 state raster with this ledger:

```python
{
    "vigor": {
        "state": "vigor",
        "support_status": "prior_constrained",
        "prior_distribution": {"mean": float("nan"), "variance": -1.0},
    }
}
```

The actual production normalizer accepts and retains the extra `prior_distribution` field. The native surface generator returns `ASMAE_VIGOR` with `support_class="prior_constrained"`, `evidence_class="Prior-Constrained"`, `scouting_zone_eligible=True`, and `management_zone_eligible=False`. Replacing the distribution with the string `"not-a-distribution"` has the same result. No top-level `prior_variance`, true actual-prior flag, or qualified prior reference is supplied.

The relevant current source is `surfaces/asmae.py:563–576`: the predicate accepts `bool(prior_distribution)` as proof and accepts any nonempty `spatial_support` string other than `none` or `unsupported`. `native_ledger_prior_spatial_nonraster`, containing `spatial_support="not-a-raster"`, is likewise accepted as prior. The normalization adapter's `ledger_adapter.py:77,82–84` stringifies spatial support and preserves unknown extra fields rather than validating a distribution.

These cases were also accepted by the exact parent, whose prior-label acceptance was broader. They are residual acceptance under the strengthened strict-prior claim, not an introduced regression, an observed normal field payload, or evidence of prescription authorization. The native outputs remain diagnostic with state-update permission false and management eligibility false.

The genuine native producer's empty ledger initializes `spatial_support="microzone_grid"` for every state (`feature_export.py:73–91`). Its output remains accepted as Prior-Constrained by both snapshots. This documents compatibility; the generic tag alone cannot distinguish verified prior provenance from geometry vocabulary. It is not evidence that the actual engine lacked a prior in a field run.

Suggested bounded follow-up: validate alternate prior distributions numerically and structurally, reject malformed supplied proof without fallback, and bind a spatial-prior proof to a recognized state/grid artifact or explicit verified prior receipt. Preserve zero variance, verified prior flags, and legitimate model/raster priors. Until then, qualify the report's universal strict-actual-prior claim even though its original bare-label and variance probes now pass.

## Relevant pinned source

- `services/agribrain/layer10_sire/surfaces/asmae.py`: scalar qualifiers 24–47; prior proof 550–579; direct evidence 590–623; management ceilings 635 onward.
- `services/agribrain/scientific_contracts/ledger_adapter.py`: native canonicalization 20–85.
- `services/agribrain/layer05_asmae/feature_export.py`: native empty/default support producer 73–93.
- `services/agribrain/scientific_contracts/state_support.py`: shared resolver and enum normalization 74 onward.

Exact blobs, SHA-256 hashes, imported modules, call results, stdout/stderr and source immutability receipts accompany this report. All 52 FA milestones remain open. This lane does not assess or implement deferred stages 3–6.


---

# Specialist appendix: Composites and exact authorization

# Composite and authorization review

Candidate `67375aa9ca0dfdc41c36d32e4105794b07e6b770`; exact immediate parent `9d7529afb411ddabb5fc8f46931cf098e10d9240`.

## Scope and method

Fresh offline probes run the native L1SpatialData carrier, ASMAE surface generator, SurfaceArtifact constructor, alias generator and actual pure TypeScript display resolver. The complete production render-authorization statement block is extracted by AST and executed unchanged with inert authored inputs. This preserves its predicates, loops and receipt construction while avoiding the full runner and provider/job side effects. AST/source hashes and import identities are recorded. Neither a browser display nor an ordinary field execution is claimed.

Run `python gating/probes.py`, `python gating/probes.py --parent`, `node gating/frontend-risk.mjs`, and `node gating/frontend-risk.mjs --parent`. Each Python replay records 19 assertions, including separately named residual observations. Each frontend replay records four checks. Exit zero means the observations, including defects, reproduce.

## Original repairs independently confirmed

The original unsupported-biotic counterfactual is repaired. With thermal stress qualified and biotic risk unsupported, changing only the biotic input scale from 0.1 to 1.0 leaves the entire native risk composite unchanged. Its first and last pixels are 0.068 and 0.612 in both runs. The exact parent changes from 0.0418/0.3759 to 0.068/0.612. The actual TypeScript resolver selects the same candidate risk grid for both scales using exact production authorization receipts.

When all risk ingredients lack qualified support, the candidate does not emit the risk composite. The parent does. When a genuinely qualified ingredient changes, the candidate composite changes, preserving a necessary positive control. Qualified diagnostic ingredients can still produce a diagnostic risk composite. An explicitly empty risk ingredient list is denied by the candidate surface gate.

Current ledger restrictions now defeat historical accepted-update counts. A typed record with `accepted_update_count=1` and either current `unsupported` status or one of `local_support_revoked`, `support_revoked`, `evidence_revoked`, and `blocked` fails authorization. A qualified indirect control remains authorized. The exact parent incorrectly authorizes these restricted records.

All 11 currently registered supported state products remain authorized in the positive fixture. The 13 helper names are not confused with the 11 actual product registrations: phenology and stress memory remain absent as dedicated products. Own-variable water separation, the five formerly unmapped states, and global current/raster/visual/grid blockers survive.

## Remaining revocation boundary: two distinct effects

### 1. Revocation on an already constructed surface

The authored input starts with a genuinely native generated diagnostic surface. A new production dataclass instance is constructed with its original geometry, values and diagnostic metadata, plus `block_reasons=["local_support_revoked"]`. This exercises the public `generate_asmae_aliases` consumer boundary; it is not an in-place production patch or a claim that a normal producer currently emits this combination.

The risk builder excludes the revoked cross-layer-conflict ingredient, as intended. Its grid remains 0.068–0.612 when that ingredient's scale changes. The vegetation-attention builder checks Unsupported labels but has no corresponding revocation-block predicate. It includes the same revoked ingredient:

| Cross-layer-conflict scale | Risk first / last pixel | Vegetation attention first / last pixel |
|---|---|---|
| 0.1 | 0.068 / 0.612 | 0.0595 / 0.5355 |
| 1.0 | 0.068 / 0.612 | 0.1000 / 0.9000 |

The exact authorization block denies this vegetation-attention product with `surface_state_requirement_unmapped`. Therefore this subcase establishes generated-value contamination and contradicts the claim that both ingredient builders honor revocation; it does **not** establish a displayed vegetation overlay or action escalation. Relabeling the ingredient Unsupported is correctly isolated by both builders on the candidate, which is a useful control.

### 2. Revocation in incoming raster metadata

An authored L1SpatialData carrier provides `raster_metadata["asmae_cross_layer_conflict"]["block_reasons"]=["local_support_revoked"]` before calling the unmodified native surface generator. The generator constructs fresh output provenance and drops this field. Its diagnostic support remains `derived_diagnostic`. The downstream risk exclusion consequently sees no revocation.

With all sibling inputs held fixed, changing only that revoked source's scale yields:

| Scale | Native risk first / last pixel | Exact runner receipt | Actual pure frontend resolver |
|---|---|---|---|
| 0.1 | 0.0588 / 0.5294 | Authorized diagnostic overlay | Selects risk grid |
| 1.0 | 0.0680 / 0.6120 | Authorized diagnostic overlay | Selects changed risk grid |

This is stronger downstream evidence than the vegetation subcase: native generator → alias generator → complete exact authorization block → actual TypeScript resolver. The carrier is deliberately authored to test a declared boundary. Normal producer occurrence, browser materialization and operational actions were not established. The exact parent reproduces both residual effects, so neither is described as an introduced regression.

## Source and bounded repair

`surfaces/asmae.py:1231–1303` rebuilds provenance without retaining incoming block reasons. Lines 1801–1814 qualify vegetation ingredients by label and pixel eligibility only; lines 1885–1905 also inspect revocation for risk ingredients. `runner.py:5240–5250` performs the current risk-ingredient guard and delegates to the state gate. Exact source/AST receipts accompany the observations.

Preserve typed restriction metadata through native generation, and use one revocation-aware ingredient qualifier for both composites. Keep ingredient exclusions and their reasons in provenance. Verify that changing any revoked ingredient yields zero change in both composites, while changing a qualified sibling remains influential. This is a bounded continuation of S12-01/S12-02; it does not require implementing deferred state products, frontend expert selection, nodata or GIS export.


---

# Specialist appendix: Constructor, serialization and current ceilings

# Native permission and runtime-ceiling integration review

Candidate `67375aa9ca0dfdc41c36d32e4105794b07e6b770`; immediate parent `9d7529afb411ddabb5fc8f46931cf098e10d9240`.

## Method and verdict

Fresh offline native calls run the production support-ledger builder, canonical normalizer, surface generator, alias generator and canonical serializer. The authored accepted-update report is a controlled input, not a newly verified physical measurement. Every one of the 1,086 files in each source corpus is verified against Git blob identities before and after execution; imported modules are recorded.

Run `python integration/probes.py` and `python integration/probes.py --parent`. Each snapshot records 20 case groups and 34 assertions. Original S12-03 permission parity and the originally cited DIAGNOSTIC/VISUALIZATION/block-reason S12-02 cases are repaired. A wider matrix of the project's own authority enum exposes a remaining incomplete ceiling intersection.

## Original constructor/serializer defect closed

On the candidate, raw and ordinary alias SurfaceArtifact instances receive explicit boolean permissions from provenance. In the diagnostic fixtures, constructor permissions, provenance permissions and canonical top-level permissions are all false. The parent retains True dataclass defaults and serializes those defaults over explicit provenance denials.

The broad native product fixture returns 47 raw products and 10 aliases. Its permissions remain denied in both the native constructors and canonical serialized outputs on the candidate. This includes unsupported state products and diagnostic composites; it does not assert those 47 products are all latent-state maps or eligible overlays.

The mapping-carrier matrix exercises all nine combinations of absent, False and True object/provenance permissions. Any explicit boolean False wins on the candidate. A generic dataclass with True permissions and no denying provenance remains True; explicit False object permissions remain False even if provenance says True. Thus the repair preserves real denial and positive controls rather than indiscriminately zeroing every artifact.

Actual scientific alias extraction preserves physical zeros and existing alias arrays. The existing composite diagnostic renderer produces the same image SHA-256 in both snapshots: `3e4771d10670dfd8c486b1ac30b4580ef1833f52dad15f309adb541cae0e2264`.

These receipts close the tested native constructor → alias → canonical serializer S12-03 failures. They do not claim every legacy naming variant, public API, browser renderer, state consumer or prescription executor was exercised.

## Original runtime restrictions repaired

A real production ledger builder initializes accepted direct-report support at current `DIAGNOSTIC` authority. The candidate correctly retains that lower ceiling: raw vigor has `management_zone_eligible=False`. The parent's raw vigor metadata incorrectly reports True. A stricter VISUALIZATION ledger and an explicit `reference_cohort_not_validated` block reason likewise remain ineligible on the candidate. Existing diagnostic aliases stay ineligible independently.

Descriptor maxima still apply. A direct-support fixture for all 11 registered state products never elevates a state above its descriptor maximum; vigor and bare-soil fraction are the two maxima that can qualify management under otherwise eligible runtime conditions.

## Remaining P2: valid runtime enum ceilings omitted

`AuthorityCeiling` declares seven values: visualization, monitoring_only, diagnostic, state_update, training_export, prescription_eligible and prescription_driver. The current classification function recognizes a negative list of only visualization, monitoring_only, diagnostic, none, blocked and unsupported. It consequently treats the valid `STATE_UPDATE` and `TRAINING_EXPORT` ceilings as permitting management.

The fresh fixture begins with the production accepted direct-report ledger, replaces only its current ceiling with an actual declared enum value, normalizes it through `index_state_support_ledger`, and calls native generation and canonical serialization. Both lowercase enum values and uppercase names are tested:

| Runtime ceiling | Candidate raw management eligibility | Candidate serialized action permissions |
|---|---|---|
| VISUALIZATION | False | Both False |
| MONITORING_ONLY | False | Both False |
| DIAGNOSTIC | False | Both False |
| STATE_UPDATE | **True** | Both False |
| TRAINING_EXPORT | **True** | Both False |
| PRESCRIPTION_ELIGIBLE | True | Both False in this diagnostic fixture |
| PRESCRIPTION_DRIVER | True | Both False in this diagnostic fixture |

The two highlighted values do not grant prescription authority under the project's factorized authority contract. They must not be upgraded merely because the state descriptor's maximum is PRESCRIPTION_ELIGIBLE. The exact parent also emits management eligibility for these values, making this an incompletely repaired inherited metadata defect, not a new regression.

The canonical action permissions remain False. The result establishes an inconsistency in published raw management eligibility, not a fertilizer/irrigation command, a variable-rate prescription or a physical execution.

## Source and bounded follow-up

`layer05_asmae/state/descriptors.py:77–85` defines the valid enum. `layer10_sire/surfaces/asmae.py:648–681` performs the incomplete runtime-ceiling intersection; `scientific_contracts/ledger_adapter.py:68–84` preserves the canonical ceiling into the native path. The repaired constructors and serializer are in `surfaces/asmae.py:1422–1436,1773–1788` and `surface_contract.py:124–153`.

Use an explicit set of prescription-capable runtime permissions or a shared typed authority predicate, intersected with the static descriptor maximum and current restrictions. Fail closed for unknown ceilings. Preserve diagnostic aliases and explicit constructor/serializer denials. Repeat the enum matrix and retain positive PRESCRIPTION_ELIGIBLE controls; no deferred stage is needed for this fix.

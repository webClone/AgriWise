# AgriBrain F36/T09: independent corrective verification of a31a65e

Completed 23 October 2026, following the review begun on 22 October. Candidate `a31a65e631daa7cdc1860861c9184cf05225cb82`; exact immediate parent `653da462360bf90a9ec0c05ce6d2c7fbea180520`. Three parallel specialist lanes review numerical classification, publication/projection and native contracts.

## 1. Decision

**S653-01 is verified repaired. No introduced blocker was found in the reviewed Stage 1–2 scope. Proceed to bounded Stage 3 implementation.** The branch is suitable for integration from the perspective of these checked software contracts. No merge or production edit was performed.

Oversized finite dispersion now fails locally as malformed prior proof. The affected state is Unsupported, without scouting or management eligibility. Independently qualified sibling states survive native surface construction. Original S8D covariance rejection and valid controls remain intact, as do the earlier restriction and permission checks.

This is a bounded software closure. It does not complete F36/T09, establish field calibration, or deliver thirteen selectable maps. All 52 package FA milestones remain open.

## 2. Verified source identity

| Item | Independently observed value |
|---|---|
| Review branch | `feat/f36-t09-asmae-13-state-publication` |
| Candidate/head | `a31a65e631daa7cdc1860861c9184cf05225cb82` |
| Exact parent | `653da462360bf90a9ec0c05ce6d2c7fbea180520` |
| Main | `90ab701714554c7b786bba4ac6b19259e77279ce` |
| Independent F02 branch | `075f19d318db6fa86d5988c2cabcb680dc17702e` |
| Changed production file | `services/agribrain/layer10_sire/surfaces/asmae.py` |
| Candidate production blob | `b810d86159ccb06755f140b340afbda22f3f7c82` |
| Parent production blob | `3138c137bc334a6475a58a51fbaf3850ed7535d7` |
| Commit scope | Production module plus its regression test; two tracked files |
| Production diff | 19 additions, four deletions |

GitHub commit, branch references and full recursive tree were fetched independently. The tree is not truncated. Each of the 1,086 selected source files in each snapshot is checked against its Git blob and SHA-256 digest. Selected source bytes remain unchanged after probes. This inventory verification does not imply that every module was forensically reviewed.

The user-supplied implementation report and repository test counts are claim receipts, separate from this review's fresh offline probes. Its cumulative historical source descriptions must not be interpreted as additional production files changed by a31a65e. The updated report artifact is not a third tracked file in this commit.

## 3. Numerical correction

The parent qualified `std`/`sigma` as finite before computing its square. That does not guarantee representable variance: `1e200` is finite while its square exceeds the float range. Both variance derivation and std/variance consistency checking could raise `OverflowError`, escaping classification and aborting generation of valid siblings.

The candidate introduces `_safe_square` at [services/agribrain/layer10_sire/surfaces/asmae.py:L155-L163](https://github.com/webClone/AgriWise/blob/a31a65e631daa7cdc1860861c9184cf05225cb82/services/agribrain/layer10_sire/surfaces/asmae.py#L155-L163). It catches arithmetic failure and checks the result with `math.isfinite`. The call site at [services/agribrain/layer10_sire/surfaces/asmae.py:L241-L249](https://github.com/webClone/AgriWise/blob/a31a65e631daa7cdc1860861c9184cf05225cb82/services/agribrain/layer10_sire/surfaces/asmae.py#L241-L249) rejects a failed square as `(False, True)` before deriving or comparing variance. The existing classification path then marks the proof Unsupported locally.

The consistency subtraction uses two already finite nonnegative variances. Its magnitude cannot exceed the larger operand. The important protection is therefore validating the square before either use, rather than a broad exception handler around the whole batch.

### Verified behavioral matrix

| Input/control | Candidate behavior | Exact-parent behavior |
|---|---|---|
| `std=0.5` | Valid prior | Valid prior |
| `std=1e150` | Valid representable squared variance | Valid prior |
| Zero dispersion | Valid zero prior | Valid prior |
| Matching scalar dispersion aliases | Valid prior | Valid prior |
| `std=1e200` | Local Unsupported; no exception | OverflowError |
| `sigma=1e200` | Local Unsupported; no exception | OverflowError |
| Oversized std plus explicit variance | Local Unsupported; no exception | OverflowError |
| Malformed vigor plus valid chlorophyll | Generation returns; chlorophyll retains qualified indirect support | Generation aborts |

The matrix is exercised through the native ledger and metadata input routes. Input `1e200` is deliberately extreme; normal field occurrence was not established. The report does not infer an API outage or actual field incident from this controlled fixture.

Sibling survival is verified by executing the native generator. Malformed vigor remains visible as Unsupported with no scouting; valid chlorophyll remains `indirectly_constrained` and scouting eligible. The candidate returns eleven existing registered state surfaces. That count represents current structural products, not a claim that all thirteen states are registered.

## 4. Earlier closures retained

| Scientific/publication boundary | Result |
|---|---|
| S8D nine malformed covariance cases | All remain Unsupported on ledger and metadata routes |
| S8D five valid covariance controls | Zero, diagonal, singular and PSD controls remain valid |
| S81 alternate prior validation | Malformed/content-free proofs rejected; genuine finite controls retained |
| S81 dual restriction carriers | Original five revocation combinations deny raw and alias display; benign control remains available |
| Composite isolation | Unsupported/revoked ingredient scaling cannot alter qualified composite values |
| State-specific water support | Vigor cannot qualify canopy water; canopy water cannot certify root-zone water |
| Runtime authority | Non-prescription ceilings cannot confer management eligibility |
| Constructor/serialization | Explicit False action permissions remain False |
| Direct proof | Boolean, infinite and malformed counts cannot manufacture direct observation |
| Missing ledger plus real raster | Cannot manufacture Observed status |
| Physical zero | Remains valid in renderer/alias consumers |

The projection lane executes the exact isolated runner authorization AST and actual pure TypeScript resolver. It does not invoke the full runner or a browser. The native integration lane checks producer ledger normalization, generation, aliases, serialization, permission matrices and renderer consumers. Results preserve the parent behavior at these unchanged boundaries.

## 5. Independent evidence and scope

Three specialist appendices document precise fixture counts, source receipts, results and limitations. The counts overlap; do not add them into an independent repository-test total. Repository tests and earlier audit claims are not the correctness oracle.

The coordinated replay executes authored offline probes on exact snapshots. Root validation checks closure, valid controls, sibling survival, source immutability and FA identity. A successful observation assertion may reproduce an exact-parent failure or inherited qualification; it is not universal operational acceptance.

The bundle includes scripts, strict JSON receipts, comparisons, hashes, plan/R3 references and an exact-source materializer for an already available Git repository. Production source, repository tests and private runtime stores are excluded. The staged sources and review scripts were executed; a full fresh reconstruction from local Git objects was not. Artifact syntax, JSON and ZIP/member hashes are validated separately.

## 6. Qualifications retained

**Q653-01 — mixed covariance encodings.** Redundant aliases expressed as a diagonal vector and mathematically equivalent diagonal matrix are conservatively rejected because their shapes differ. No reviewed producer or specified contract requires cross-encoding equivalence. This is an inherited availability/documentation qualification, not acceptance of contradictory covariance and not a new blocker. Establish canonical representation before adding normalization.

**Q8D-01 — restriction vocabulary coverage.** The shared union helper recognizes more spellings than some callers gather. Existing probes retain the previously disclosed alternative-carrier limitation. Original S81 dual-carrier closures remain intact. Broad helper vocabulary should not be advertised as proven end-to-end support for every spelling. Carry canonical restriction field selection and producer/consumer parity into catalog work.

**Metadata-only authority.** The inherited descriptor-based eligibility qualification remains separate from action authority. The checked native action permissions remain False. A support label or scouting eligibility does not establish prescription authority.

No newly introduced required repair is raised by this candidate review.

## 7. Monograph and governing plan

The master repair plan, execution sequencing addendum and work-package task list are matched to the candidate tree. The supplied R3 PDF identity remains SHA-256 `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`; extracted scientific requirements and source identities accompany the evidence.

| R3 requirement | Established here | Scope still open |
|---|---|---|
| AB-ARC-006, bounded degradation | Bad dispersion no longer aborts valid native siblings | Wider runtime/provider resilience |
| AB-ASM-003, specific state support | Invalid proof cannot qualify the affected state | Full per-variable observability and calibration |
| AB-ARC-005, factored authority | Existing ceiling and False action boundaries retained | Package-wide operational acceptance |
| AB-ASM-011/016, restrictions and local validity | Checked restriction/serialization paths retained | Every producer, training and export path |
| AB-L10-001, qualified projection | Checked raw/alias/consumer parity retained | Complete thirteen-state publication, masks and GIS delivery |

F36 owns scientific support admission; F38/T11 cover bounded degradation/publication resilience; T09 owns product/catalog/expert projection. The sequencing addendum permits bounded product work to advance on its own prerequisites. This closure neither bypasses full-package dependencies nor treats all 52 open FA rows as a universal prohibition on independent slices.

## 8. Stage 3 next steps and acceptance boundary

Proceed with the registry/catalog slice from the reviewed ancestry. No additional Stage 1–2 repair is required by this review.

1. Add dedicated `ASMAE_PHENOLOGY_PROGRESS` and `ASMAE_STRESS_MEMORY` products to the canonical backend registry, surface/render types and manifest, preserving all eleven existing products.
2. Establish one exact mapping from thirteen canonical coordinates to thirteen product identities, including units, uncertainty association and authority ceiling.
3. Return an inventory entry for every state with explicit availability and reasons. Registration must never manufacture observations, accepted updates, priors or spatial support.
4. Align frontend inventory with the canonical catalog while retaining existing farmer lenses. Independent expert selection remains Stage 4 work.
5. Retain malformed-vigor/valid-chlorophyll isolation and restriction/permission parity controls as registry-expansion acceptance criteria.

Stage 5 must preserve unassigned-cell nodata separately from physical zero. Stage 6 must integrate scientific GIS export and real-plot/browser receipts. Those deliverables are still unimplemented/deferred in this bounded review; closing S653-01 does not make thirteen independent maps available today.

## 9. Governance and operational limits

Exactly 52 FA milestones remain open, zero checked. Main and F02 references are independently observed and untouched. No production source edits, merge, push, remote comments, full orchestrator/provider run, API/browser session, field controller operation, drone mission, optimizer or prescription dispatch occurred. User-reported full-suite counts were not rerun or presented as independent evidence.

**Disposition: close S653-01, preserve earlier verified closures, and proceed to bounded Stage 3 publication registry implementation.**


---

# Specialist appendix: Numerical support and sibling isolation

## Recovered numerical lane: fresh final replay, 23 October 2026

S653-01 is independently verified repaired in candidate `a31a65e631daa7cdc1860861c9184cf05225cb82` against exact parent `653da462360bf90a9ec0c05ce6d2c7fbea180520`. No introduced numerical blocker was found in the checked squaring change.

The finalization replay reconstructed the exact selected source corpora and reran the authored native probes. Counts in this receipt supersede any intermediate assertion count: **117 classifier cases, 135 native generator cases and 14 direct numerical validator cases per snapshot; 66 grouped observation assertions**, all reproduced. Counts overlap and are not a repository test-suite total. The selected 1,086 files in each snapshot were verified against Git blobs and SHA256 and remained unchanged. Forty-six native imported modules were verified.

### Closure and controls

| Fixture | Candidate | Exact parent |
|---|---|---|
| std/sigma `1e200` | Validator `(False, True)`; native Unsupported, scouting False | OverflowError |
| std `1e200` plus variance `1.0` | Local Unsupported | OverflowError |
| sigma `1e200` plus var `1.0` | Local Unsupported | OverflowError |
| Equal oversized std/sigma | Local Unsupported | OverflowError |
| Adjacent float just above square boundary | Local Unsupported | OverflowError |
| std `0.5`, std `1e150`, zero std/sigma | Valid prior | Valid prior |
| Matching std/variance, sigma/var | Valid prior | Valid prior |
| Mismatching finite dispersion | Unsupported | Unsupported |
| Adjacent float just below square boundary | Valid prior | Valid prior |

Every numeric fixture traversed both ledger and metadata routes. Four mixed native generator fixtures cover both routes, each with and without explicit variance. All four candidate calls return eleven surfaces: malformed vigor is Unsupported with scouting disabled, while independently qualified chlorophyll remains indirectly_constrained and scouting eligible. All four parent controls abort with OverflowError. The ordinary sibling control remains valid.

All original S8D covariance checks remain intact: nine invalid cases reject on both routes, while all five valid controls qualify, including finite zero/singular covariance. Earlier S81 seventeen-invalid/four-valid alternate distributions and S673/S12 provenance/direct-proof controls are retained. Existing missing-ledger, bogus-prior, boolean/infinite direct-count denials remain; valid direct/indirect/prior controls remain admitted under their existing ceilings.

### Mechanism and scientific scope

Production `_safe_square` at `services/agribrain/layer10_sire/surfaces/asmae.py:155–163` catches arithmetic overflow and rejects non-finite squared results. Its validator use at lines 241–249 covers both derivation and explicit-variance consistency. The candidate blob is `b810d86159ccb06755f140b340afbda22f3f7c82`; the parent blob is `3138c137bc334a6475a58a51fbaf3850ed7535d7`.

This demonstrates bounded native publication resilience, not physical observation validity or field occurrence of extreme dispersion. The fixtures deliberately use authored offline carriers; socket connections are disabled. No repository tests are used as correctness proof. No full runner, provider, API, browser, hardware or action path executed. No source edits occurred. All 52 FA milestones remain open.


---

# Specialist appendix: Publication and consumer projection

# Retained projection, alias and frontend closures — a31a65e

Candidate `a31a65e631daa7cdc1860861c9184cf05225cb82`; exact immediate parent `653da462360bf90a9ec0c05ce6d2c7fbea180520`.

## Verdict

The retained S81/S673/S12 publication controls pass fresh production-symbol probes in both snapshots. No new alias, authorization or pure frontend-selection regression was reproduced in this lane. The candidate changes only the ASMAE surface module's checked finite variance derivation; the runner, surface schema, serializer and frontend resolver retain their prior source identities.

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

No ordinary production emitter of the additional camel-case restriction keys was found in the inspected production corpus. These are authored recognized-key carrier checks already documented as Q8D-01. This inherited compatibility limitation neither regresses in a31a65e nor reopens the verified canonical dual-carrier repair. It remains a qualification to universal all-carrier claims, not an additional merge blocker here.

## Receipts

`results.json` / `parent-results.json` contain state/product matrices, original dual carriers, lifecycle controls, composite counterfactuals and inherited vocabulary observations. `frontend-risk-results.json` and parent counterpart contain actual TypeScript selection results. Source receipts include before/after blob identities, imports, and the unchanged authorization AST block at runner.py lines 4989–5634, AST SHA-256 `3f76a593543157d6e82b921c91040e9f0270d065445fec488bf6ebd55c4138d0`.

All 52 FA milestones remain open. Dedicated product registration, expert selection, nodata and GIS/real-plot publication remain deferred; this lane does not implement them or confer full-package acceptance.

## Fresh candidate/parent equality

`compare_results.py` verifies all Python and TypeScript output fields match exactly after excluding only commit/control identities. The fresh coordinated work resumed on 23 October 2026; no source was modified. No introduced projection blocker was found.


---

# Specialist appendix: Native contracts and authority parity

## Native integration and contract parity lane

Candidate `a31a65e631daa7cdc1860861c9184cf05225cb82` was replayed against its exact parent `653da462360bf90a9ec0c05ce6d2c7fbea180520` using independently authored offline carriers. No repository test or audit file supplies the expected outcome. The native producer, normalization, surface and alias constructors, canonical serializer and renderer consumers run directly; the full runner, external providers, API/browser, actuators and prescription dispatch do not run.

**Verdict: no introduced native integration or permission regression found.** Both fresh snapshots reproduce all 49 observation assertions across 27 case groups. All 27 case groups compare equal after normalizing only set-derived product order by semantic type. These observation assertions include inherited qualifications; their success is not full operational acceptance.

The following controls remain intact:

- A native `build_state_support_ledger` fixture produces the existing DIAGNOSTIC ceiling. Canonical normalization, raw construction, alias construction and serialization preserve diagnostic/no-action boundaries.
- Fourteen declared authority-ceiling spellings retain their existing eligibility behavior. STATE_UPDATE and TRAINING_EXPORT do not become management eligibility. Static descriptor ceilings remain intersected with current explicit authority.
- All 47 raw state/diagnostic products and ten aliases in the comprehensive fixture carry False state-update and prescription-driver permissions at constructor and canonical serialization boundaries. These counts include diagnostics and are not latent-coordinate counts.
- All nine absent/False/True permission combinations preserve restrictive False precedence, including dataclass defaults versus explicit provenance denial. Generic positive controls remain positive when no denial exists.
- Sixteen constructor/provenance restriction combinations retain deduplicated union, including empty or benign attribute carriers paired with revoked provenance. Helper nested mapping/order controls remain stable.
- All previously reported covariance-alias and variance/covariance contradictions remain Unsupported on native ledger and metadata routes in both snapshots. Six matching covariance/variance controls remain prior-constrained.
- Existing alias renderer values and legitimate physical zero are preserved.
- The inventory remains thirteen canonical coordinates versus eleven dedicated registered state products. Phenology-progress and stress-memory products remain Stage 3 work.

Inherited qualifications stay explicit rather than becoming new findings. Equivalent diagonal-vector/matrix declarations supplied as redundant covariance aliases are conservatively rejected; no reviewed producer or contract requires that mixed-encoding equivalence. The shared restriction helper recognizes some root spellings not forwarded by serializer callers; original S81 dual-carrier cases remain closed, and broader vocabulary support is not claimed. Metadata-only direct proof without a runtime ceiling retains descriptor-based eligibility, while actual checked action permissions remain False.

Both selected corpora verify 1,086 exact Git blob/SHA-256 identities before and after execution; no source byte changed. Forty-seven imported module identities were recorded for each run. `results.json`, `parent-results.json`, `comparison.json`, the two source manifests and the authored replay/comparison scripts provide the receipts. All 52 FA milestones remain open; this lane neither edits them nor confers package acceptance.

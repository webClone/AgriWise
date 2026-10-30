# ASMAE Batch A+B independent completion gate — ded7252

Completed 25 October 2026. Candidate `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`; exact parent `e85cfd224f8a731e2959648ce28450e27782188f`; branch `feat/f36-t09-asmae-13-state-publication` independently confirmed at the candidate.

## Decision

**Hold the merge. The completion revision contains substantial verified repairs, but the integrated A+B gate remains incomplete.** The most immediate blocker is an ordinary native output-assembly exception: the NumPy converter fix works, while `_assemble_output()` now fails on a locally shadowed `math` binding. Scientific support and publication receipts also retain connected inconsistencies.

This review keeps the same five completion groups, AB-R01 through AB-R05. It does not turn each representation case into a separate project. Finish the remaining native paths together, retain the proven fixes, and use one connected producer-to-cold-consumer gate. Independent expert-interface/GIS work can proceed separately against a stable contract; it does not supply acceptance for these defects.

All **52 package FA sign-offs remain open, zero checked** in the pinned task register. Bounded software repairs and complete package/field acceptance are distinct decisions. This report closes no package and authorizes no merge or hardware operation.

## 1. Evidence and limits

GitHub confirms the candidate's sole parent and review-branch head. The candidate changes eleven production Python modules and one TypeScript module; plan documents and repository test changes were excluded as correctness evidence. Both selected source corpora contain 1,087 files, verified against the pinned Git tree and SHA-256. This is source identity coverage, not an exhaustive audit of all 4,120 tree entries.

Six independent specialist lanes reviewed scientific support, capability restrictions, cache durability, spatial alignment, availability/domains, and scientific export. The root additionally executed a native validated publication → save → cold read → serialize/re-export control. Fourteen top-level replay commands completed with exit zero. Their assertions deliberately reproduce both repairs and counterexamples; **exit zero here does not mean cohort acceptance**. Source syntax checks cover all eleven changed Python modules.

Most checks execute native production component functions, including the unmodified failing assembler and actual L10 publication validator/writer/reader. Nested runner inventory/gates/state-selection and pure frontend helpers are isolated exactly and labeled as such. Fixtures are authored offline inputs, not field observations. No repository pytest/frontend suite was rerun, and user-reported passing test totals remain author-reported receipts. The review used Python 3.12.14 and Node 24.22.1; it does not reproduce the author's Python 3.13 environment or browser runner.

No complete provider/engine/HTTP/browser/GDAL/hardware execution, fresh field calibration, power-loss test or new multiprocess concurrency experiment occurred. No production source, Git branch or milestone was changed. Malformed-carrier tests and injected filesystem failures are explicitly distinguished from ordinary finite native paths.

## 2. Completion scorecard

| Completion group | Verified progress | Remaining integrated disposition |
|---|---|---|
| AB-R01: native assembly and spatial continuity | Converter executes; all-state/scalar holes remain missing; negative indices guarded; valid zero interpolation preserved; frontend dimensions/all-null/geographic-bound checks work | **P1 blocker:** native assembly still crashes on local `math`. **P2 regression:** valid nearest-shared-bounds masks are rejected; exact-grid affine proof remains incomplete |
| AB-R02: per-state scientific influence | HT/proxy unchanged-sibling counts fixed; positive siblings retained; observation updates protect memory; process evolution and counters retained | **P2:** opposite local changes can disappear from the global influence receipt; graph selection and malformed-receipt handling remain inconsistent |
| AB-R03: typed capabilities and restrictions | Ordinary strict booleans, enum ceilings, unknown-ceiling denial, serializer carrier unions and raw unsupported/diagnostic denials verified | **P2:** native producer discards some restrictive metadata before serialization and omits static descriptor ceilings from action intersection |
| AB-R04: scientific availability and domains | Raw nonfinite/string/boolean pixels denied; safe INV-2 checks; all thirteen pixel domains; LAI legend; genuine zero controls | **P2:** scalar flags/domain/status are not equivalent to pixel rules; save-time sanitizer coerces denied types; temporal-role predicate convergence remains |
| AB-R05: scientific receipts and durable artifacts | ASMAE policy-key migration, nomask handling, shape rejection, normal generation publication, L10 precommit preservation, all-thirteen confidence export and canonical permission projection | **P2:** own-state uncertainty binding, cold reconstruction, transaction commit-point cleanup, L10 integrity/policy and residual export representations remain incomplete |

## 3. Blocking native reproduction

The following calls the actual unmodified assembler with ordinary finite state/uncertainty grids:

```python
from types import SimpleNamespace
from services.agribrain.layer05_asmae.engine import ASMAEEngine
engine = ASMAEEngine.__new__(ASMAEEngine)
engine._assemble_output(
    SimpleNamespace(mode='standard'), None,
    {'raster_maps': {'vigor': [[0.0]]},
     'uncertainty_maps': {'vigor': [[0.2]]}},
    {}, {}, [], None, {},
)
```

Candidate: `UnboundLocalError: cannot access local variable 'math' where it is not associated with a value`, at `engine.py:1994`. A later conditional `import math` at line 2442 makes `math` local throughout the method. The global module import cannot satisfy that local binding. The error occurs before later fields omitted from this minimal fixture are read. Exact parent fails on `np`; the candidate repairs that symbol but leaves the same lexical error family through `math`.

Native `_microzone_to_grid({'mz_000_000': [0.0] * 13}, None)` does succeed in candidate. This distinguishes the verified converter repair from the still-failing integrated assembler. Do not accept compilation or an isolated replacement arithmetic block as the assembly gate.

The new TypeScript affine check also runs before the policy allowing nearest projection. A valid 2×2 mask and 4×4 target with common geographic extent and consistent differing pixel sizes return False even when `nearest_shared_bounds=True`; exact parent returns True. Conversely missing/empty affine declarations and certain two-pixel shifts still pass exact-grid controls. Qualify affine/bounds consistency, then apply distinct exact-grid and nearest-shared-footprint predicates. These are exact pure helper outcomes plus active caller tracing, not an actual browser failure capture.

## 4. Scientific state/support consistency

The ordinary named AB-R02 repairs are confirmed. Unchanged LAI receives zero accepted updates in both HT and proxy controls, varying LAI remains accepted, proxy stress-memory observation change is zero, and forecast memory still evolves. Direct/indirect/proxy counters remain separate.

A finite two-zone fixture exposes the remaining spatial receipt problem: opposite NDVI innovations change vigor means by approximately **+0.000256989 and −0.000256989**, both exceeding the mean-change tolerance. Their field-wide mean cancels. Average variance reduction is approximately `1.03e-9`, below its threshold. The report consequently says `excluded_negligible_influence`, `update_applied=False`, ledger count zero, while returning the changed ensemble. Parent and candidate both reproduce this. Evaluate actual per-node influence before spatial reduction; receipt and numerical state must describe the same event.

The runner's graph selector still consumes the full target list. A genuinely accepted vigor update plus excluded node-constant LAI causes native graph regularization to change LAI by 0.14; consuming the qualified accepted list leaves LAI unchanged. Independent graph-prior evolution can be legitimate. Choose its policy explicitly and give it a model-prior receipt, or restrict this observation-conditioned regularization to affected states. This result is not proof of fabricated Observed authority or prescription execution.

Missing or malformed influence proof also defaults to acceptance or aborts aggregation. These are authored boundary cases; ordinary new filter receipts are well formed. Make the current policy explicit, strict and locally recoverable while keeping legitimate legacy/research roles separately qualified.

## 5. Scientific receipt continuity through SIRE and cold publication

Native ASMAE-output → `adapt_l1` → `generate_asmae_surfaces` → export retains vigor's own uncertainty grid internally as `[[.01,.02],[.03,.04]]`, but the published vigor receipt reports aggregate uncertainty **0.35** and aggregate concentration **0.65**. The own-state grid is preserved in L1's suffixed raster map and never attached to its state product. This is an existing connected completeness gap, not a failure of the newly repaired direct confidence fallback. All thirteen native surfaces now preserve their supplied confidence in direct export controls.

The root's native admitted publication → save/load → canonical serialization/re-export control independently demonstrates cold receipt divergence:

| Receipt field | Before save | Cold reconstructed surface |
|---|---|---|
| Observed/inferred masks | Explicit 2×2 masks | None / None |
| Display/effective resolution | 2 m / 20 m | 1 m / 10 m defaults |
| Explicit state/prescription flags | True / True | False / False defaults |
| Retained compatibility permission | True | Still True while fresh re-export is False |

Both versions reproduce this incomplete reconstruction. Numeric values/confidence agree within expected float32 encoding tolerance; that rounding is not a defect. Provenance-held uncertainty in this specific roundtrip survives. Fix the typed decoder for every scientific schema field and derive compatibility products from the rehydrated canonical receipt. Also bind each state to its own uncertainty/confidence/support maps, keeping aggregate diagnostics separately named.

Native export now correctly projects canonical permission denials/revocations and several fallback fields. Remaining source/display-grid fallback and sigma-only discrepancies show that it still maintains independent fallback logic rather than a single canonical projection. Supported alternative representations are controlled fixtures; their ordinary producer incidence is not established.

## 6. Restrictions, domains and availability

The improved terminal serializer intersects surviving restriction and ceiling carriers. The native producer can still discard a restrictive metadata ceiling when a permissive ledger ceiling exists, so the serializer never sees the denial. An authored native vigor case with metadata DIAGNOSTIC and ledger PRESCRIPTION_DRIVER yields raw and canonical state-update True. LAI's static descriptor DIAGNOSTIC maximum is also absent from the action capability intersection: runtime STATE_UPDATE plus an explicit grant yields True. Management eligibility remains False in that control. These are native metadata-boundary contradictions, without an observed live contradictory acquisition or executed action.

Keep static descriptor, runtime ledger and raster metadata ceilings until one shared capability resolver intersects them. Preserve all explicit snake/camel denials before any typed projection. Normal binary scalar and enum repairs are real and have valid positive controls; the remedy must not indiscriminately deny all qualified products.

Availability now rejects raw invalid pixel types, but numeric scalar declaration flags 0/0.0 still permit a valid scalar, scalar-only objects can be labeled `available_raster`, and scalar upper-bound violations bypass the pixel domain checks for all thirteen states. Use the same typed scientific qualifier for scalar and pixel values, and derive plot/raster status from actual support. Structural availability must remain distinct from action authorization.

The persistence sanitizer still changes True into 1.0 and numeric strings into floats, after which the new raw validators accept them. Its actual call is at cache-save time after publication-envelope validation, not before the normal live manifest. This is a connected save-boundary admission gap; a complete live malformed-input execution was not demonstrated. Invalid types should become missing or typed rejection with reasons rather than silently acquire scientific numeric identity.

## 7. Complete artifact transaction and reader contract

ASMAE policy versioning and ordinary generation storage are verified. The unmasked MaskedArray case succeeds, undersized masks reject, and precommit failure preserves the old committed result. L10's normal precommit replacement now also preserves prior data, unlike its parent.

Complete the remaining artifact contract together:

1. Initialize cleanup state before any conversion; restore every detached live field even if a later grid conversion fails. Candidate currently raises an introduced `UnboundLocalError` for uninitialized `npz_candidate_path` on an authored malformed grid. Earlier sibling data remains detached in both versions.
2. Treat successful JSON publication as a commit point. An injected real postcommit stat failure currently removes the NPZ already referenced by that JSON, making the native reader miss. Accounting/logging failure after commit must not delete committed data.
3. Bind L10 generations to checksums and per-member shapes/dtypes/IDs. Same-shape altered NPZ values are currently accepted. This is a controlled local corrupt-artifact case, not a demonstrated network exploit.
4. Validate mask dtype before conversion to bool. Exact spatial shape checks are repaired; original wrong dtype currently survives via coercion. Normal current writers emit booleans, so the tested float/NaN mask is a defensive reader fixture.
5. Qualify retained L10 scientific policy separately. A parent-written stale Observed receipt is accepted by the current reader under unchanged retained-input keys. New complete ASMAE execution may change upstream hashes/run IDs and miss this cache; this experiment does not establish that every fresh run reuses an old result. Preserve archival policy identity without returning an old scientific assertion as current qualification.

## 8. One completion revision and one integrated gate

| Parallel ownership | Completion scope | Required gate |
|---|---|---|
| Native execution/spatial | Eliminate local binding errors; finish affine/bounds and nearest-policy semantics | Native keyed/microzone/sparse assembly; exact and legitimate nearest mask positives and denial controls |
| Scientific inference | Local influence receipt, accepted-state graph policy, strict receipt admission | Opposite local innovations, covariance-only information, unchanged siblings, HT/proxy policy and process evolution |
| Capabilities/availability | Descriptor × ledger × metadata intersection; shared scalar/pixel/domain/status qualifier | Contradictory carriers survive denial; valid grants/physical zeros retained; all thirteen domains and temporal roles |
| Publication artifacts | Own-state uncertainty binding, complete cold decoder, canonical export, commit-point cleanup, integrity and policy | Warm → committed cache → fresh process → serializer/export equivalence; precommit and postcommit fault controls; qualified legacy reads |

These lanes can run concurrently against one canonical receipt definition. Acceptance should compare scientific contents, masks, geometry, all resolutions, support, uncertainty, confidence and capabilities—not merely enabled-mode counts or dataclass member presence. Once the native runtime blocker and these agreed A+B contracts pass together, reassess merge readiness once for the entire revision. Keep separate future expert/GIS delivery and field qualification milestones outside the bounded software verdict.

## 9. Pinned source references

- [ASMAE engine](https://github.com/webClone/AgriWise/blob/ded72528ce12a2f1cb4ca6a208ddcc2accc3802a/services/agribrain/layer05_asmae/engine.py)
- [Assimilation filter](https://github.com/webClone/AgriWise/blob/ded72528ce12a2f1cb4ca6a208ddcc2accc3802a/services/agribrain/layer05_asmae/assimilation/filter.py)
- [State support export](https://github.com/webClone/AgriWise/blob/ded72528ce12a2f1cb4ca6a208ddcc2accc3802a/services/agribrain/layer05_asmae/feature_export.py)
- [ASMAE cache](https://github.com/webClone/AgriWise/blob/ded72528ce12a2f1cb4ca6a208ddcc2accc3802a/services/agribrain/layer05_asmae/cache.py)
- [SIRE native surfaces](https://github.com/webClone/AgriWise/blob/ded72528ce12a2f1cb4ca6a208ddcc2accc3802a/services/agribrain/layer10_sire/surfaces/asmae.py)
- [L1 spatial adapter](https://github.com/webClone/AgriWise/blob/ded72528ce12a2f1cb4ca6a208ddcc2accc3802a/services/agribrain/layer10_sire/adapters/l1_adapter.py)
- [Canonical surface contract](https://github.com/webClone/AgriWise/blob/ded72528ce12a2f1cb4ca6a208ddcc2accc3802a/services/agribrain/layer10_sire/surface_contract.py)
- [SIRE runner and cache](https://github.com/webClone/AgriWise/blob/ded72528ce12a2f1cb4ca6a208ddcc2accc3802a/services/agribrain/layer10_sire/runner.py)
- [Raster export](https://github.com/webClone/AgriWise/blob/ded72528ce12a2f1cb4ca6a208ddcc2accc3802a/services/agribrain/layer10_sire/products/export.py)
- [Frontend materialization](https://github.com/webClone/AgriWise/blob/ded72528ce12a2f1cb4ca6a208ddcc2accc3802a/src/lib/agribrain/render-materialization.ts)

Normative sources are the pinned R3 requirement text and the master repair plan, sequencing addendum and task register. R3 AB-ASM-003 addresses per-variable operator/covariance influence; AB-ASM-011 and AB-ASM-016 constrain propagated per-state evidence and validity; AB-ARC-005/006/007 separate capability, bounded degradation and atomic publication; AB-L10-001 requires masks, geometry, resolution and authority to match canonical state. These requirements qualify this review without redefining the monograph around a single concern.

The following six appendices preserve each lane's exact evidence, controls, paths, reproduction commands and reachability limitations.


---

# Appendix 1 — spatial lane

# AB-R01 spatial continuity independent review — ded7252

Candidate `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`; exact parent `e85cfd224f8a731e2959648ce28450e27782188f`. Read-only production review, 25 October 2026. No repository tests or audit narratives used as the oracle. No provider execution, full engine run, live browser/DeckGL render, hardware or production source changes.

## Decision

**AB-R01 remains incomplete: hold the integrated gate.** The ordinary converter repair is real, as are scalar missingness, negative-index protection and endpoint-preserving interpolation. However, the ordinary native output assembler still fails: the patch replaces the first unresolved local `np` reference with an unresolved local `math` reference. A new frontend affine-equality check also rejects the expressly supported different-resolution `nearest_shared_bounds` mask policy while leaving exact-grid affine qualification incomplete. Finish these as one spatial-continuity correction inside the existing A+B cohort.

## Verified changes

- Native `ASMAEEngine._microzone_to_grid({'mz_000_000':[0.0]*13}, None)` now returns thirteen legitimate zero grids. Exact parent raises `NameError: np`.
- The native sparse converter preserves all thirteen state mean and sigma holes as `None`, while physical zero remains `0.0`.
- `_microzone_scalar_to_grid` now produces `[[0.0, None], [None, 0.8]]` for two diagonal samples; parent fills missing scalar support with zero.
- Negative IDs no longer overwrite a valid cell. The candidate returns vigor `[[0.2]]` for a valid cell plus an authored `mz_-1_-1` record.
- Native `_bilinear_resample([[0.0,None],[None,None]], 3, 3)` preserves the supported endpoint as `0.0`; parent produces non-finite values there. All-missing and fully finite interpolation controls also execute.
- Native SIRE identity alignment still normalizes the `-9999.0` sentinel to `None` and preserves legitimate zero.
- Exact pure frontend helper execution verifies new dimension mismatch, all-null support, geographic metric-bound and large affine-shift denials; genuine finite zero grids and same-grid masks remain usable.

## SP-01 — P1: native `_assemble_output` still raises `UnboundLocalError`, now for math

**Production paths:** `services/agribrain/layer05_asmae/engine.py:1994`, `:2010`, `:2442`.

The module has a global `import math`, but the original `_assemble_output` method still contains a conditional `import math` at line 2442. Python consequently treats `math` as a local variable throughout that method. The new `math.isfinite(fval)` at line 1994 executes before that conditional import is assigned. The `except (ValueError, TypeError)` does not catch `UnboundLocalError`.

This reproduces with the **unmodified native method**, without extracting or patching any function:

```python
from types import SimpleNamespace
from services.agribrain.layer05_asmae.engine import ASMAEEngine
engine = ASMAEEngine.__new__(ASMAEEngine)
engine._assemble_output(
    SimpleNamespace(mode='standard'), None,
    {'raster_maps': {'vigor': [[0.0]]},
     'uncertainty_maps': {'vigor': [[0.2]]}},
    {}, {}, [], None, {},
)
```

Candidate traceback terminates at line 1994 with `UnboundLocalError: cannot access local variable 'math' where it is not associated with a value`. The exact parent native call terminates at its earlier `np.isfinite` for the same lexical-binding family. The method encounters the failure before any later fields omitted from the minimal input are accessed. Finite keyed uncertainty is the ordinary producer shape; this is not a malformed-payload test.

An independent exact lexical-prefix probe inserts only an early result return before `retro_pm`, retaining the whole original method's later imports to preserve Python's scope rules. It confirms the same candidate `math` and parent `np` failures. Sparse ordinary microzone inputs likewise fail in candidate assembly after conversion, now at the same `math` reference. This additional extracted control is not needed for the native proof.

**Required completion:** remove all function-local shadowing of globals used earlier, then execute the native assembler on keyed and microzone mean/sigma shapes, including sparse holes and physical zero. Verify posterior concentration holes remain missing after the assembler actually executes. Do not accept compilation or a separately reimplemented arithmetic block as the runtime gate.

## SP-02 — P2: mask alignment now over-restricts supported nearest projection and under-qualifies exact grids

**Production paths:** `src/lib/agribrain/render-materialization.ts:202–224`; active calls at `:298–312`; `src/components/farm/map/layers/SemanticSurfaceLayer.ts:581–598`. Backend `services/agribrain/layer10_sire/runner.py:5689` expressly emits `nearest_shared_bounds` for experimental surfaces.

### Introduced regression: valid different-resolution mask denied

Use one 2×2 binary mask and one 4×4 finite target with identical WGS84 bounds `[3,35,3.0002,35.0002]`. Their GDAL affine transforms correctly reflect their different pixel sizes:

```text
mask   [3, 0.0001,  0, 35.0002, 0, -0.0001]
target [3, 0.00005, 0, 35.0002, 0, -0.00005]
```

`canMaterializeMask(mask, target, true)` returns **False in candidate and True in exact parent**. The new transform equality check runs before the `allowNearestSharedBounds` decision and compares pixel scales, making expressly allowed nearest-neighbour mask projection impossible for these valid grids. `allowNearestSharedBounds=False` correctly denies different dimensions in both versions; identical-grid controls remain True.

The active frontend forwards `auth.maskAlignmentPolicy === 'nearest_shared_bounds'` into this helper, and returns a blocked/missing mask result or no layer on False. The case demonstrates the pure preflight outcome and source-reachable consequence; an actual affected plot/browser execution was not run.

### Exact-grid proof remains incomplete

Candidate authored controls still return True when one affine is absent, both affine lists are empty, or a target-consistent extent is paired with a shifted mask affine. In a 2×2 grid with 0.00001-degree cells and top northing 35.00002, shifting the mask's affine origin northward by 0.00002 degrees (two full pixels) is accepted: tolerance is scaled by the absolute geographic origin (`35 × 1e-6`) rather than cell resolution. Bounds are held equal, making the supplied mask grid internally contradictory; `validateSurfaceGrid` does not cross-check affine and bounds. The new large-shift denial is real but does not establish exact-grid alignment.

**Required completion:** validate each grid's six finite affine coefficients against dimensions and bounds; use exact-grid tolerance relative to cell scale or an explicit absolute geospatial tolerance. Then distinguish exact-grid parity from qualified `nearest_shared_bounds` projection: the latter should require a common physical footprint/CRS and compatible orientation, and deliberately allow the different pixel-size coefficients needed for nearest resampling. Test both permissiveness and legitimate availability.

### Additional display-coordinate qualification

`validateSurfaceGrid` rejects metric values labeled EPSG:4326, but still returns valid for `[500000,4000000,500020,4000020]` labeled EPSG:32631. `resolveSurfaceBounds` forwards accepted bounds unchanged and `getSemanticSurfaceLayerLayer` passes them to `new BitmapLayer({bounds,...})` without coordinate conversion. The SIRE ASMAE path normally constructs a geographic display grid, so this authored case establishes a missing defensive consumer contract, not incidence of a current normal ASMAE run. Require geographic display coordinates or an explicit validated reprojection before forwarding to the map renderer. Do not confuse native scientific CRS with browser display CRS.

## SP-03 — qualified lower-priority typed-input residual

The native scalar converter still converts `True` into `1.0` and numeric string `'0.5'` into `0.5`; keyed state-grid input bypasses conversion/qualification entirely. These controls reproduce in candidate and parent, and show that using `math.isfinite(float(v))` alone does not establish the broader F01 finite-real/non-boolean admission contract. This lane did not establish that malformed values reach the ordinary filter producer; retain it as a typed boundary qualification item instead of inflating it into a fresh ordinary-runtime blocker. Coordinate with the scientific/availability lanes so its disposition is not double counted.

## Normative and verification qualification

R3 `ScientificEvidence` §48 includes spatial support, native/effective resolution, observed/gap-fill masks, validity domain and uncertainty distribution. The existing F38/T09/T11 scope requires those distinctions to survive publication and reproducible failure handling; the current A+B spatial completion explicitly committed to grid and missingness continuity. The mask predicate's contract must preserve both fail-closed exact support and legitimate nearest shared-footprint projection.

`probes.py` uses 15 named observations/control groups per snapshot, including unmodified native methods, native SIRE identity helper, and a separately identified exact lexical prefix. `frontend-probes.mjs` uses 12 exact pure helper cases per snapshot under Node's TypeScript type erasure, with no implementation rewriting. There are 10 Python and 11 frontend summarized observation assertions. These counts overlap and record both working repairs and reproduced remaining failures; they are not a claim of 21 passing acceptance tests. Source SHA-256/Git-blob receipts are embedded in results. Both scripts exit zero only if the documented observations reproduce.

Reproduce:

```bash
python review-ab-ded7252/spatial/probes.py
node review-ab-ded7252/spatial/frontend-probes.mjs
```

All FA milestones remain open; no stage or package acceptance is claimed.


---

# Appendix 2 — semantics lane

# AB-R02 — independent scientific support and entrypoint review

Candidate `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`; exact parent `e85cfd224f8a731e2959648ce28450e27782188f`. Read-only production review, 25 October 2026.

## Verdict and coverage

**The named ordinary AB-R02 sibling and memory corrections are verified. The broader support receipt contract remains partial.** Native candidate HT and proxy component updates now reject unchanged LAI from accepted counts, while retaining genuinely affected LAI. The proxy update no longer changes `stress_memory`; the native process forecast still evolves it. Direct/proxy/indirect counters survive canonical normalization.

Additional native and exact-fragment controls find a finite local-update receipt inconsistency, a remaining graph-selector mismatch, and fail-open/malformed per-state receipt handling. Keep these in the existing scientific completion group; there is no justification for separate new repair projects.

`probes.py` runs two isolated Python processes loading exact candidate and parent source. Its result records both repaired controls and counterexamples. All inputs are authored offline scenes/ensembles, not acquired field evidence. Native production functions run: `update_step_ht`, `update_step_proxy`, native extraction/support construction, ledger builder, canonical ledger normalization, feature pack export, graph regularization and process forecast. The runner's exact `accepted_target_states` assignment is compiled from its AST without changing its expression, then passed to the native graph function. No full engine/provider/runner/API/browser/hardware execution occurs. The current `assert_scene_operator_binding` rejects `H_matrix=None` before the `run_enkf` loop; proxy parity here is a public component verification, not proof of an ordinary no-H full-run route.

No repository test or supplied audit assertion is used as correctness proof. Production files remain unchanged. Source receipts are in `results.json`. Run with `python review-ab-ded7252/semantics/probes.py`.

## Verified corrections

| Contract | Candidate | Parent control |
|---|---|---|
| HT unchanged-LAI sibling | max observation delta 0; accepted count 0 | delta 0; accepted count 1 |
| Proxy unchanged-LAI sibling | delta 0; accepted count 0 | delta 0; accepted count 1 |
| Positive varying-LAI HT/proxy | affected state accepted | accepted |
| HT NOT_ASSIMILATED memory | observation delta 0 | 0; retained earlier correction |
| Proxy NOT_ASSIMILATED memory | observation delta 0 | 0.23749674602160709 |
| Forecast memory evolution | nonzero process delta, retained | retained |
| Counter canonicalization | direct/indirect/proxy identities retained separately | retained |

These are meaningful fixes: the ordinary producer now emits and consumes `accepted_target_states` and `per_state_influence`, and observation policy is applied before numerical mutation in both component paths. `stress_memory` is protected from observations without freezing process evolution.

## SEM-01 — P2: local nonnegligible updates disappear from the influence ledger

**Status:** pre-existing in parent; still inside the intended per-state influence completion contract.

**Source:** `services/agribrain/layer05_asmae/assimilation/filter.py:998–1053`, `1752–1785` and equivalent proxy summary logic `1931–1964`.

The influence criterion takes the absolute **field-wide average mean** change, not a spatial norm of each node's change. Opposite local innovations can cancel the mean exactly. The remaining variance criterion is the field average within-node variance reduction. With a narrow ensemble this can remain below its fixed tolerance even though individual node mean changes exceed the stated mean tolerance.

Fresh native finite fixture:

- Two zones, each with eight members, vigor ranging from 0.398 to 0.402; LAI constant 2, chlorophyll 30; other coordinates valid.
- `H = I_2`, one independent pixel per zone, NDVI observations equal each zone's predicted mean plus 0.3 and minus 0.3.
- Native update changes node vigor means by **+0.0002569886639444685** and **−0.0002569886639444685**; max member delta **0.00025758839407941103**.
- Native report computes `delta_mean = 0.0`, variance reduction **1.0279546558011175e−9**, `state_influenced=False`, `mode=excluded_negligible_influence`, `update_applied=False`.
- Ledger vigor accepted count remains **0**. The returned ensemble **retains the changed values**.
- Exact parent produces the same mismatch.

This does not establish unearned management authority; it establishes that a real numerical observation influence is described as excluded and absent from the support receipt. That affects faithful state/support accounting and spatial inspection. F36 requires actual operator influence per state, and R3's execution/influence distinction requires the receipt to describe what changed. A field-wide mean is insufficient for spatial support attribution.

**Completion:** use per-node mean changes (or a valid spatial norm/max) and per-node uncertainty changes before reduction. If an update is deliberately classified negligible, either restore its numerical candidate or explicitly record bounded subthreshold influence; avoid returning altered state with a categorical no-update receipt. Preserve covariance-only informative controls and scale tolerances by state bounds.

## SEM-02 — P2 consistency: graph regularization still selects the full target list

**Status:** selector is unchanged from parent; newly accurate candidate exclusion receipts expose the remaining integration mismatch. This is a qualification/provenance gap, not proof that modelled states may never evolve.

**Source:** `services/agribrain/layer05_asmae/assimilation/filter.py:359–371`; `services/agribrain/layer05_asmae/graph/spatial_regularization.py:19–32,41–48,133–169`.

The exact runner selector iterates `report['target_states']` for any accepted report, ignoring the newly published `accepted_target_states` and `per_state_influence`. The graph function describes itself as smoothing only observation-updated states.

Native update + exact selector + native graph fixture:

- Two zones with node-constant LAI **0.5** and **4.0**, both zero within-node LAI covariance with NDVI; varying vigor is valid and genuinely accepted.
- Actual observation update changes LAI by **0.0**, and candidate ledger LAI accepted count is **0**.
- Exact runner selector selects `['lai','vigor']`; qualified per-state list is `['vigor']`.
- Real graph regularization changes LAI by **0.14** per member (0.5→0.64, 4.0→3.86).
- Same ensemble/graph with the qualified list changes LAI by **0.0**.

A graph prior can legitimately change an unobserved modelled state. Therefore this result must not be described as fabricated direct observation, or as a prescription breach. The defect is that the observation-conditioned eligibility selector contradicts the exclusion receipt and the function's own eligibility contract. It also means the presence of an unrelated accepted sibling controls whether this prior changes LAI.

**Completion:** choose and implement one explicit scientific policy. If graph smoothing is restricted to observation-affected states, consume the authoritative accepted state list. If independent graph evolution is allowed, invoke it under a separate model-prior receipt with its own scope and influence accounting, without assigning observation support. Maintain the cross-node mean-conservation control.

## SEM-03 — P2 boundary robustness: per-state proof defaults to approval and malformed proof aborts aggregation

**Status:** permissive missing proof is pre-existing; the new malformed-object exception is introduced by candidate proof consumption. Authored malformed receipts do not establish normal producer incidence.

**Source:** `services/agribrain/layer05_asmae/feature_export.py:118–140`.

The candidate initializes `is_state_influenced = True`. Missing or empty proof plus missing accepted target list grants support. It uses Python `bool(...)` on the claimed proof field; the string `"false"` grants support. An explicit positive proof overrides `accepted_target_states=[]` and `excluded_target_states=['vigor']`. A non-dict per-state proof `False` raises `AttributeError` when `.get` is called, aborting the builder and sibling aggregation.

Native builder observations for an otherwise accepted real-source indirect report targeting vigor:

| Proof | Candidate |
|---|---|
| Missing both per-state and accepted-target proof | accepted count 1, assimilated |
| Empty `per_state_influence={}` | accepted count 1, assimilated |
| `{'state_influenced':'false'}` | accepted count 1, assimilated |
| `{'state_influenced':True}` plus accepted list empty/excluded list vigor | accepted count 1, assimilated |
| Per-state entry `False` | AttributeError, builder aborts |
| Genuine explicit boolean False | accepted count 0 |

The ordinary new filter emits valid booleans and lists; these controls are boundary qualification tests. The new cache policy version can prevent legacy cache replay but does not make the receipt builder itself strict. A direct caller or restored report path must not manufacture actual influence from absence. No external exploit path is asserted.

**Completion:** validate report/per-state shapes and strict boolean influence, intersect restrictive carriers, require explicit accepted proof for the current policy, and define an explicit legacy requalification route if compatibility is needed. Record a local exclusion for an invalid state receipt so valid siblings can survive. Check accepted and excluded target lists for contradictions. Preserve legitimate finite physical zero values and valid positive accepted receipts.

## Plan and monograph alignment

F36's concrete step is a per-state support ledger connecting actual operator sensitivity and references to each label; cohort proof must distinguish numerical influence, indirect/proxy constraint, graph prior, and process evolution. R3 describes observation→belief influence and an execution manifest distinguishing available capability from actual influence. The above results support correcting receipt completeness, while keeping independent calibration/field qualification outside this software-only review. Nothing here closes an FA package milestone; all 52 remain open.


---

# Appendix 3 — authority lane

# Authority lane — ded7252 independent completion verification

Candidate: `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`. Exact parent: `e85cfd224f8a731e2959648ce28450e27782188f`. Read-only production-source review, 25 October 2026.

**Disposition: AB-R03 materially repaired, incomplete at the native producer intersection.** Keep the verified fixes. Complete the same authority contract as part of the existing A+B gate; this lane does not recommend another sequence of small residual projects.

## Reproduction and scope

```bash
python review-ab-ded7252/authority/probes.py
python review-ab-ded7252/authority/probes.py --parent
```

Both commands completed with exit 0. They run native `generate_asmae_surfaces`, native schema/ledger normalization, and native `serialize_surface_artifact`, with the documented visual-shadow rollout environment enabled and socket connection attempts denied. These are authored component fixtures using real production functions. They do not launch a full engine, provider, HTTP API, browser, model training or physical operation. No repository tests or audit claims are the correctness oracle. Source receipts in each result pin three executable source targets. Parent/candidate fixtures are identical.

The two runs contain 12 native-generation cases, 15 canonical serializer cases, 21 enum/value/name ceiling encodings and nine scalar permission cases each. Counts overlap and are observations, not end-to-end passing tests. The candidate records 19 assertions including verified repairs and reproduced residuals; the parent records 13 controls. Strict JSON excludes NaN literals. Authored invalid values are represented by descriptive strings in outputs.

R3 §9 separates state, diagnostic, prescription and visual authorities. The canonical-projection section states that adapters cannot promote authority. The F36 per-variable support and T09 map-projection contracts therefore require preservation of the most restrictive valid carrier through reconstruction and serialization. This finding concerns that existing contract, not a new stage requirement.

## Independently verified repairs

- Unsupported and runtime-DIAGNOSTIC ASMAE raw surfaces now have `state_update_allowed=False`, and the canonical serialized flag remains False. Exact parent exposed True in the same authored explicit-grant fixtures.
- Binary and finite scalar qualification repairs the original `NaN`, `Inf`, `-1` and `2` permission truthiness defects. Legitimate numeric 0 denies and 1 grants; string `false` denies.
- All 21 enum/name/value encodings now normalize consistently: VISUALIZATION, MONITORING_ONLY, DIAGNOSTIC and TRAINING_EXPORT deny both action flags; STATE_UPDATE permits an explicit state grant and denies prescription; explicit prescription-capable controls retain both grants.
- Canonical serializer intersects attribute/provenance and snake/camel ceiling carriers. An attribute `PRESCRIPTION_DRIVER` with provenance `DIAGNOSTIC` now denies; exact parent granted.
- Canonical serializer restriction union now denies action when empty attribute or snake lists coexist with provenance or camel revocation. It preserves the revocation reason.
- An unknown nonempty ceiling denies both action flags.
- Native canonical snake revocation still forces unsupported and denies; an explicitly qualified vigor STATE_UPDATE grant with `diagnostic_only=False` still grants state update. A separate explicit canonical prescription grant survives. The implementation has not merely denied all positives.

## Remaining P2 — intersect before producer normalization discards restrictions

The terminal serializer can only intersect carriers it receives. `compute_asmae_support_classification` in `surfaces/asmae.py:997–1014` chooses the ledger ceiling first, falling back to metadata only if absent. `generate_asmae_surfaces:1618–1623` emits only that selected ceiling into new provenance. Its action checks at `1833–1851` then inspect this single result. The original metadata ceiling is lost before the improved canonical serializer runs.

Native reproduction (`results.json → native.restrictive_meta_ceiling_masked`):

```python
# Canonical vigor ledger supplies accepted indirect support.
ledger['vigor']['authority_ceiling'] = 'PRESCRIPTION_DRIVER'
raster_metadata['asmae_vigor'].update({
    'state_update_allowed': True,
    'authority_ceiling': 'DIAGNOSTIC',
})
```

Observed candidate: raw `state_update_allowed=True`; serialized `state_update_allowed=True`; resulting provenance ceiling `PRESCRIPTION_DRIVER`. Metadata's `authorityCeiling='DIAGNOSTIC'` camel spelling produces the same outcome. A conflicting metadata `stateUpdateAllowed=False` beside snake True is also discarded by native construction; raw and serialized flags remain True. These cases existed in the exact parent and remain completion gaps, not new regressions. The repaired direct serializer **does** deny equivalent surviving canonical ceiling conflicts; this local positive control isolates the loss to producer normalization.

The route is a real metadata interface: SIRE receives `L1SpatialData.raster_metadata`; `adapters/l1_adapter.py:305–337` installs extracted FieldTensor raster metadata, and `store_native_asmae_grid:906–952` carries existing metadata into native-grid metadata. The generator reads that dictionary at `asmae.py:1297–1305`. This lane directly supplies an admitted L1SpatialData fixture and runs native construction; it has not demonstrated that every contradictory carrier is emitted in a normal live acquisition. That incidence remains unestablished. Once supplied, the contradictory final permission is reproduced without function substitution.

### Static descriptor ceiling is also absent from action intersection

LAI's descriptor maximum is DIAGNOSTIC (`state/descriptors.py:165–177`). `compute_asmae_support_classification:991–995` consults it for the management-zone eligibility boolean only. The action permission resolver at `1833–1851` does not intersect it.

Native reproduction (`native.static_lai_diagnostic_runtime_state`): LAI accepted indirect ledger with runtime `STATE_UPDATE` and raster metadata state grant True. Result: descriptor ceiling `diagnostic`, management eligibility False, **raw and canonical state-update permission True**. Runtime `PRESCRIPTION_DRIVER` gives the same state-update inconsistency. The valid vigor STATE_UPDATE control remains True. This is a per-variable maximum-capability conflict, not a request to grant LAI any additional power. Prescription remains False in these native fixtures, and this lane does not claim an executed state update or hardware command.

### Secondary representations of the same monotonicity gap

- Canonical `surface_contract.py:260–275` checks top-level snake permission attributes and provenance snake/camel keys, but omits top-level camel permission fields. A canonical mapping carrying snake True and `stateUpdateAllowed=False` / `prescriptionDriverAllowed=False` returns both True. Equivalent provenance camel False denies, proving representation asymmetry.
- `surface_contract.py:284–289` chooses provenance support class before attribute support, rather than intersecting both. Attribute `support_class='unsupported'` is masked by provenance `indirectly_constrained` and an explicit grant. A whitespace-padded ` unsupported ` token is also unrecognized. These are authored dual-carrier/schema-variant fixtures; normal producer incidence is not established.
- Native ledger camel `blockReasons` is dropped by the current normalization route, while canonical `block_reasons` control denies. This corroborates the need to qualify the carrier union at admission, before projecting into a narrower record. It is not presented as proof that the typed canonical ledger writer normally emits camel keys.

These observations belong to one remaining authority-intersection contract. Preserve the original static descriptor, ledger and raster-metadata restrictions until a shared typed capability resolver intersects them. Reuse that normalized result for constructors, aliases, provenance and serialization; any explicit denial must survive. Keep valid qualified positive grants as controls.

## Secondary robustness issue within the same scalar qualifier

`surface_contract.py:76–79` calls `math.isnan`/`math.isinf` on arbitrary Python integers before binary comparison. A permission `10**1000` now raises `OverflowError: int too large to convert to float`, instead of returning False. The exact parent returned True for this invalid nonbinary permission; the new code correctly handles usual -1/2/NaN/Inf but introduces an exception for the enormous integer. This is an authored malformed input, not demonstrated normal traffic or external exploit. Compare integer values to 0/1 without float conversion, and guarantee scalar qualification returns a denial rather than throwing. The local `_parse_strict_bool` in native generation duplicates this numeric pattern. No valid sibling-loss claim is made by this lane because the observed reproduction is direct serialization.

## Recommended integrated completion checks

1. Cross static descriptor × ledger ceiling × raster metadata ceiling, requiring capability-set intersection while retaining an explicit valid vigor positive control.
2. Run snake/camel attribute and provenance denial permutations through native construction, canonical serialization and export. Check action fields and provenance agree.
3. Run contradictory support/revocation carriers through actual admission normalization; no denial may disappear during a typed projection.
4. Add malformed scalar cases including very large integers and preserve exact zero/one controls. No qualifier may raise or convert invalid nonbinary values to a positive permission.

All package FA statuses remain outside this bounded lane; no milestone is marked accepted. No production file was edited.


---

# Appendix 4 — catalog lane

# AB-R04 catalog, typed availability and scientific domain review

Candidate `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`, exact parent `e85cfd224f8a731e2959648ce28450e27782188f`. Read-only independent component review, 25 October 2026.

**Disposition: partial repair.** The principal raw finite/non-boolean admission and type-safe INV-2 corrections are verified. Complete the remaining scalar/availability/persistence qualification together inside AB-R04; this lane does not propose an additional project or reopen deferred expert/GIS features.

## Verified repairs

Native production `build_render_manifest` now disables a raster consisting solely of True, `"0.5"`, `"bad"`, NaN or Infinity. Exact-parent controls enabled those raw representations. Native `enforce_layer10_invariants` now records INV-2 for each representation without raising TypeError; parent string cases raised. A numeric `0.0` pixel remains available and does not violate INV-2.

Flag-only scalar declarations and scalar values False, numeric string or NaN no longer manufacture availability. `has_scalar_estimate="false"` with a finite scalar now disables manifest and inventory; exact parent enabled it. Legitimate scalar `0.0` remains inspectable. An empty grid without scalar is `missing` and disabled.

All thirteen canonical states have dedicated surface/mode definitions, legends and palettes. All thirteen out-of-domain pixel controls are detected by native INV-2. The LAI legend reaches 8.0. These repairs are retained.

## Remaining coherent completion contracts

### CAT-D01 — P2: scalar declaration and availability classes still disagree

Production locations: `layer10_sire/products/manifest.py:275–287`; `layer10_sire/runner.py:3902–3956`; `layer10_sire/invariants.py:133–159`.

The new `flag_denied` predicate recognizes boolean False and string spellings but uses `flag is False`; numeric `0` and `0.0` do not match. With values `[[None]]`, provenance `{"has_scalar_estimate": 0, "scalar_value": 0.5}`, the candidate still enables the manifest and reports `available_raster` for an authored `grounding_class="SPATIAL"` carrier. Numeric zero denial is explicitly claimed in the completion summary but not implemented. NaN as the declaration flag also permits the finite scalar. Boolean False and string `"false"` controls correctly deny it.

Separately, scalar-only availability is classified from the surface's original grounding label rather than actual support. A finite scalar with all-None pixels and `SPATIAL` grounding becomes `available_raster`; it should remain scalar/plot-level inspection. The result is native manifest output plus the exact active inventory assignment/loop isolated from runner AST. No browser overlay or complete run is claimed.

Scientific scalar bounds are also omitted: for each of the thirteen states, setting only `scalar_value = canonical_upper_bound + 1.0` enables the manifest; INV-2 checks only `s.values`, so records no scalar-domain violation. For example, vigor scalar 2.0 is available while vigor pixel 2.0 is correctly flagged. This is a parity gap at the scalar inspection boundary, not proof of prescription execution.

Complete one shared qualifier that separates absent declaration, qualified True, qualified False and malformed declarations; validates the actual scalar against the same scientific domain as pixels; and derives scalar-only availability from actual support. Preserve physical zero. Reuse it in manifest and inventory rather than maintaining parallel comprehensions.

### CAT-D02 — P2: persistence sanitization launders denied numeric types

Production locations: `layer10_sire/runner.py:479–518`, cache write call `1440–1446`; manifest `3463`, invariants `3674`.

Native `sanitize_surface_values` still converts through `float(val)`. A boolean True becomes 1.0 and numeric string `"0.5"` becomes 0.5. Passing those same surfaces through the native sanitizer and then native manifest/invariants changes both cases from denied/INV-2 to available/no INV-2. The new raw type checks are bypassed once this normalizer has erased type provenance.

Execution-order qualification matters: this sanitizer is called in `save_layer10_to_cache` **after** `validate_layer10_publication`; live-run manifest and invariant checks appear earlier in the runner. This lane does not claim the ordinary live manifest receives sanitized invalid data, or that the full publication validator accepts the minimal authored fixtures. It demonstrates native cache-boundary normalization that contradicts the stated finite non-boolean contract. The parent has the same coercion, so this is an existing connected contract gap, not an introduced regression.

Sanitization should preserve legitimate numeric values and convert invalid type/non-finite values to missing or typed rejection, while retaining a reason. Do not certify boolean/string inputs by changing their type. Align validation and post-normalization validation at the persistence boundary. Another lane independently reviews full cache serialization/readback.

### CAT-D03 — existing convergence qualification: temporal roles and duplicated catalogs

Production locations: `layer05_asmae/feature_export.py:73–96`; `layer10_sire/runner.py:5279–5292`; catalog definitions in `scientific_contracts/state_schema_ref.py`, duplicated runner lists `332–372`, `3852–3890`, manifest registrations and invariant ranges.

Native `build_state_support_ledger([])` gives both `phenology_progress` and `stress_memory` status `prior_constrained`, no accepted updates, relationship `none` and `microzone_grid` support. The exact active `asmae_state_gate` AST denies the phenology entry but allows the memory entry. Explicit `model_propagated` and `temporally_conditioned` controls allow both; explicit revoked controls deny both. Behavior is unchanged in the exact parent.

This is a consistent native-producer/exact-consumer differential, but it does not by itself prove real model temporal evidence was lost during a complete run. Define the intended temporal publication predicate and producer receipt together; carry actual temporal/memory proof, rather than assuming observation counts identify model evolution. Keep missing-proof inspection distinct from pixel authority.

Catalog ranges/legends now agree for all thirteen state products, but their consumer definitions are still independently enumerated. The frontend continues to expose farmer lenses, with the expert selector/GIS delivery intentionally deferred to Batch C. This review does not count that deferred UI as a new A+B blocker. Shared typed availability/domain predicates and generated/validated inventories are the A+B convergence work.

## Additional boundary observations, not new blockers

An authored surface carrying numeric payload .5 with `valid_mask=[[False]]` in provenance/dynamic attribute still counts as available in manifest/inventory; these functions inspect values without mask intersection. The SurfaceArtifact dataclass does not declare valid_mask, and normal producers are expected to materialize masked cells as None. This lane has not established that this contradictory carrier survives the full canonical publication validator. Treat it as a shared predicate hardening case coordinated with the cache/export lanes, not a demonstrated normal live-map failure.

Out-of-range finite pixels still enable a mode structurally while INV-2 records a violation; invariant enforcement reduces reliability and records warnings. Structural inventory availability is not a grant of action authority. This lane does not claim that a separate authorization gate permits those pixels.

## Evidence and reproduction

Run:

```bash
python review-ab-ded7252/catalog/probes.py
python review-ab-ded7252/catalog/probes.py --parent
```

The candidate produces 16 documented observation checks and the parent 14. These counts record verified repairs **and** retained counterexamples; they are not passing package-acceptance tests. Each process exercises eight native pixel cases, thirteen scalar cases, thirteen pixel-domain cases, thirteen scalar-domain cases, one mask carrier and two temporal states with four support controls each. Counts overlap.

Native components: schema constructors, render manifest, invariant enforcement, sanitizer and state-ledger builder. Exact isolated AST: active runner inventory assignment/loop and `asmae_state_gate`; original predicates are unmodified, line spans retained in results. Harness correction selected the nested active inventory definition rather than the top-level duplicate. Full runner/provider execution, real plot, API/browser or hardware were not executed. Source hashes for inspected modules are retained in JSON. All 1,087 candidate source bytes were unchanged at lane verification.

Normative scientific checks: R3 AB-L10-001 requires masks, geometry, resolution and authority to match canonical state; AB-ASM-016 prohibits transferring local certification into global variable permission. No repository test or existing audit narrative was used as correctness proof. All 52 FA milestones remain open.


---

# Appendix 5 — cache lane

# Cache and durable publication lane — ded7252

Candidate `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`; exact parent `e85cfd224f8a731e2959648ce28450e27782188f`. Read-only native component review, 25 October 2026. No repository tests or audit narratives used as a correctness oracle. Source digests are in `results.json`. All writes belong to authored, isolated fixtures in this lane; the source corpus was unchanged.

## Verdict

**AB-R05 is materially repaired but remains incomplete at the connected cache/publication boundary.** ASMAE nomask serialization, exact mask shape pairing, current-policy keying, and ordinary generation publication are verified. L10 normal precommit replacement now preserves the previous generation. The native L10 roundtrip still discards scientific receipt fields; exception cleanup introduces a new escaping runtime exception and can delete a committed generation after its JSON publication. Policy-qualified ASMAE cache migration does not by itself qualify retained L10 publications.

Do not undo the verified fixes. Complete these remaining behaviors together within the existing A+B artifact/receipt cohort.

## Independently verified repairs

| Contract | Candidate | Exact parent |
|---|---|---|
| Ordinary native ASMAE zero/None raster roundtrip | Preserved | Preserved |
| Unmasked `np.ma.array([[0,.2],[.3,.4]])` storage | 2×2 boolean mask manifest; native read succeeds | Scalar `(1,)` mask causes manifest rejection |
| Manifest-consistent 1×1 mask for 2×2 data | Rejected | Accepted with clipped masking |
| Scientific support policy enters ASMAE key | Current key `b707c7adb3f76e83528fae8c9f8b445206737ff03a746ab053da331169ffbb33` | Same authored input key `491222c4e77a99a630014273d7966244ebc29bff2dc870cd78b4bcfa574d750b` |
| Current commit requires support policy version | Removing the field makes a miss | Field was absent and reader accepted |
| ASMAE replacement fails before JSON publication | Returns False and prior complete publication remains readable | Same preserved behavior |
| Native L10 publication envelope validator and ordinary save/load | Accepted, saved and loaded | Accepted, saved and loaded |
| L10 JSON replacement fails before commit | Returns 0; prior JSON and referenced NPZ remain readable | Deletes prior JSON and NPZ; subsequent load misses |

The ASMAE policy key/version change is a real fix: old ASMAE JSON is no longer accepted under the same new input key without the current policy. The L10 policy observation below concerns a separate cache and does not negate this repaired ASMAE route.

## Connected residuals

### C-DUR-01 — P2, new escaping cleanup exception; preexisting live-output mutation

`services/agribrain/layer10_sire/runner.py:1466–1508,1532–1542`.

`npz_candidate_path` and `json_candidate_path` are initialized only after array extraction and `asdict`. When an earlier conversion or serialization fails, the exception handler references an unbound local. An authored two-surface, otherwise natively admitted publication uses one ordinary finite grid, followed by `[['not-a-number',.2],[.3,.4]]`.

- Candidate `save_layer10_to_cache` raises `UnboundLocalError: cannot access local variable 'npz_candidate_path' where it is not associated with a value`.
- Exact parent returns 0 for the original conversion failure.
- Both versions leave the first live surface's `values=[]`: restoration is only inside the later `try: asdict(...) finally`, after conversion has already detached earlier surfaces.

This is native function execution with the actual publication validator. Malformed grid incidence in an ordinary completed production run is not established. The API's fail-closed cache boundary nevertheless must reject such data without escaping cleanup errors or mutating siblings.

Initialize candidate paths and a commit flag before any operation that may fail. Cover **all** detach/conversion/asdict operations with unconditional restoration, or construct detached snapshots without modifying the live output object.

### C-DUR-02 — P2, committed generation deleted during postcommit error cleanup

`runner.py:1524–1540`.

The native writer publishes JSON with `os.replace`, then computes byte counts using filesystem stat. Its broad exception handler always removes `npz_candidate_path`, even after that path is the artifact referenced by the committed JSON. With a previously valid publication, an authored `OSError` from `os.path.getsize` for the final JSON after its successful replacement produces:

- Return 0.
- Final manifest JSON exists and points to the new generation.
- The newly referenced NPZ has been deleted by cleanup.
- Native `load_layer10_from_cache` returns None.

The parent has the analogous unsafe finalization behavior on fixed names; this is an incompletely repaired transaction contract, not a claim that every normal save fails. The fault is explicitly injected at a real postcommit filesystem operation; its field incidence is unmeasured.

Separate the commit point from cleanup. Once JSON publication succeeds, do not unlink referenced committed data because of accounting/logging/stat failure. Compute byte counts before publication where possible; fsync the NPZ and publication directory if crash/power-loss durability is claimed. No actual power-loss experiment was performed.

### C-READ-01 — P2, cold publication does not preserve the complete scientific receipt

`runner.py:1127–1156` and reader `1545–1659`.

The root's separate native connected control in `../root-integration.py`/`../root-integration-results.json`, with an exact parent control, verifies actual admitted SurfaceArtifact → export → native cache save/load → canonical serialization/reexport.

Current and parent cold reconstruction omit constructor fields including explicit permission flags, observed/inferred masks and display/effective resolution. The fixture's flags True become False, masks become None, and resolutions 2/20 become 1/10. The persisted compatibility `raster_pack` still retains the old permission True, while fresh export of the rehydrated surface reports False. Values and confidence agree within expected float32 tolerance; this is receipt divergence, not a claimed numerical water/state error. Provenance-held uncertainty in that fixture survives.

Read all schema fields through the same canonical decoder and regenerate compatibility receipts from the reconstructed authoritative surface. Add warm/cold equality checks for values plus restrictions, masks, uncertainty, confidence, provenance and all resolutions. This lane does not duplicate the root evidence or present it as independent additional test coverage.

### C-POL-01 — P2 scientific migration boundary, retained L10 policy not versioned

`runner.py:1017–1124,1545–1659`.

The ASMAE cache policy version is absent from the unchanged L10 key and no corresponding L10 reader requalification/version guard was added. `l10_policy_bridge.py --parent` writes an **authored stale scientific receipt**, using the native parent writer and actual validator, under native L10 key `9640c56e18585e1b90e98881505d7fcc`. The metadata says ASMAE vigor is `Observed`, `directly_assimilated`, `direct_observation=True`, with direct count1. The current native key for the same retained L1/input-run metadata is identical, and the current native reader accepts that old publication without requalifying these claims.

This establishes a retained/replayed L10 component path. It does **not** establish that a fresh complete ASMAE execution necessarily hits the same L10 cache: new upstream run IDs, raster IDs, channel, confidence, content hashes or other hashed inputs can produce a miss. No new full pipeline was run. The bounded claim that all old Observed artifacts are invalidated is therefore too broad when referring to all publication caches.

Bind the scientific support/operator/descriptor policy into L10 identity or explicitly requalify old publications under current rules. Preserve archive readability with historical policy metadata without returning it as current qualified evidence.

### C-MASK-01 — P2 defensive contract gap, mask boolean validation occurs after coercion

`layer05_asmae/cache.py:654–665`; compatibility loader `696–705` has the same pattern.

The reader first converts any mask to bool at line656, then checks the already-coerced dtype at664. A manifest-consistent 2×2 float mask containing NaN is accepted; NaN becomes True and hides the corresponding payload value. Parent has the same behavior. The newly repaired exact spatial shape check does work.

The fabricated artifact is internally manifest-consistent; a normal current writer generates boolean masks, and no external exploit or normal wrong-dtype writer incidence is established. This probe addresses the claimed strict boolean reader contract. Validate the original mask array's dtype before conversion; reject invalid/orphan/reserved-role members before applying them.

### C-INT-01 — P2 publication artifact integrity remains weaker in L10 than ASMAE

`runner.py:1581–1634`.

L10 NPZ loading checks existence, surface count and two-dimensionality, but not a digest or bound member shape/dtype/content manifest. After a native valid commit, replacing its NPZ with a same-ID/same-shape numeric grid of0.99 is accepted as a complete valid publication. ASMAE's corresponding checksummed artifact route rejects corruption; the L10 generation migration has not carried that integrity contract over.

This is an authored local corrupt-artifact fixture, not evidence of a network attacker or real disk incident. Bind generation ID, NPZ checksum, per-member IDs, shapes and dtypes before rehydration, and treat any mismatch as a clean miss. Reader equivalence must be tested together with the new writer.

## Reproduction and qualifications

Run separately to keep candidate/parent imports isolated:

```bash
python review-ab-ded7252/cache/probes.py
python review-ab-ded7252/cache/probes.py --parent
python review-ab-ded7252/cache/l10_policy_bridge.py --parent
python review-ab-ded7252/cache/l10_policy_bridge.py
```

`results.json`, `parent-results.json`, `policy-parent-results.json`, `policy-results.json` contain actual observations. Two source digests are retained in each main result. Source identity is independently verified by the root corpus manifest.

Native full component functions are executed, not copied test implementations or AST writer substitutes. Only `runner.__file__` is rebased for its hardcoded relative artifact root; cache directories are patched to lane temporary directories. Actual publication validators run. Network calls are prohibited. No provider/full engine/HTTP/browser/GDAL/hardware execution occurred. No multiprocess race or power-failure claim is made by this lane; ordinary generation consistency and failure controls are bounded as described above.


---

# Appendix 6 — export lane

# Export lane — ded7252 integrated A+B review

Candidate `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`; exact parent `e85cfd224f8a731e2959648ce28450e27782188f`. Read-only production review and fresh native component probes, completed 25 October 2026. No repository test files or audit narratives were used as the correctness oracle. No provider, full engine, API server, browser or physical device ran.

## Disposition

**AB-R05 is materially repaired but remains partial at the connected scientific receipt boundary.** Keep the valid export repairs. Complete reconstruction and state-specific uncertainty binding in the same A+B revision, using one native warm/cold producer-to-consumer acceptance gate. No separate Stage C expert/GIS feature is made a blocker here.

R3 `AB-L10-001` requires masks, geometry, resolution and authority identical to canonical state; `AB-ARC-005` separates capabilities; `AB-ARC-007` prevents incompatible partial publication replacing validated canonical state. Source: previously pinned R3 text excerpts in `review-wide-d59c9bd/normative/R3-scientific-excerpts.txt`. The findings below concern those existing publication contracts.

## Verified improvements

`python review-ab-ded7252/export/probes.py` launches separate fresh interpreters against candidate and parent source roots, preserving independent module identities. The script has explicit assertions for key repairs/counterexamples and writes strict JSON results. Each candidate/parent run includes twelve grouped controls; counts overlap and are not a full pipeline test count.

- Native `generate_asmae_surfaces` receives actual `L1SpatialData` with all thirteen state grids, valid geographic source/target specs, confidence 0.8 and scalar uncertainty 0.1. A genuine diagnostic rollout environment flag enables generation; no rollout function is stubbed. Exactly thirteen surfaces materialize. Candidate native exporter preserves confidence 0.8 in every compatibility entry and canonical receipt; parent compatibility confidence is None in all thirteen. Both preserve scalar uncertainty.
- Explicit provenance confidence grids, two-dimensional uncertainty, observed and inferred masks now survive export with canonical parity. Parent discarded those fallback fields.
- Camel-case observed/inferred mask provenance now survives export. Valid physical zero remains a valid pixel and in statistics.
- Canonical-denied state-update/prescription permissions and provenance revocation blocks now project into `RasterEntry` correctly. Parent exported raw True permissions and lost provenance-only blocks. This is a verified repaired contradiction.
- Stats exclude nonfinite, boolean and string input cells without the parent TypeError on mixed malformed input.

The fixtures use authored scientific declarations and prove transport behavior, not field observability, calibration or actual prescription eligibility.

## E-D01 — P2: state-specific uncertainty grids survive transport but are not attached to their state product

**Existing connected A+B completeness gap, reproduced natively.**

`adapters/l1_adapter.py:850–865` computes one plot-average aggregate uncertainty and posterior concentration from the aggregate diagnostic maps. `store_native_asmae_grid` applies that shared `stage_metadata` to every state and support grid (approximately 945–960). It also separately preserves per-state uncertainty rasters under suffixed map keys (981–1000). `surfaces/asmae.py:1371–1380` reads metadata confidence/uncertainty as scalar floats; its provenance writes those scalars at 1647–1648 and the raw constructor does not attach a paired per-state grid.

Native authored ASMAE output:

```python
raster_maps = {'vigor': [[.1,.2],[.3,.4]]}
uncertainty_maps = {
    'vigor': [[.01,.02],[.03,.04]],
    'ASMAE_UNCERTAINTY': [[.2,.3],[.4,.5]],
}
confidence_maps = {
    'vigor': [[.6,.7],[.8,.9]],
    'ASMAE_POSTERIOR_CONCENTRATION': [[.5,.6],[.7,.8]],
}
```

Exact native `adapt_l1` → `generate_asmae_surfaces` → `export_raster_pack` yields:

| Observation | Candidate |
|---|---|
| `l1.raster_maps['asmae_vigor_uncertainty']` | Original `[[.01,.02],[.03,.04]]`, preserved |
| Vigor canonical uncertainty | `0.35` |
| Vigor compatibility uncertainty | `0.35` |
| Vigor compatibility confidence/concentration | `0.65` |
| Generated diagnostic products | Aggregate uncertainty and posterior concentration |

The own-state spatial sigma map is therefore retained in internal transport but absent from the published vigor receipt; a normalized global aggregate mean occupies its uncertainty field. This is not merely a scalar-vs-grid annotation issue. Engine assembly (`layer05_asmae/engine.py:1957–2002`) actually derives the aggregate from its per-state sigma grids, so these authored keys match the production output convention. Full engine/provider incidence was not run. Parent has the same missing binding (and also loses compatibility confidence).

Completion: retain aggregate concentration/uncertainty as explicitly named diagnostics, attach the matching state sigma/confidence/support grid to each coordinate's scientific receipt, preserving masks, units, resolution and scalar availability distinctions. Verify two states with different sigma patterns cannot receive each other's or the global diagnostic uncertainty.

## E-D02 — P2: cold publication reconstruction loses declared receipt fields and disagrees with retained compatibility entries

**Existing connected A+B completeness gap.** Parent/root integration independently runs the actual native publication validator, writer and reader, with an authored minimal envelope and paths rebased into isolated scratch. No validator stub is used. Evidence is `../root-integration.py`, `../root-integration-results.json`, and exact-parent control `../root-integration-parent-results.json`.

`runner.py:1130–1151` reconstructs `SurfaceArtifact` but omits `observed_mask`, `inferred_mask`, state-update/prescription flags, block reasons, display resolution and effective resolution. Defaults consequently replace explicitly persisted fields. `raster_pack` is separately retained.

Reproduced candidate outcomes:

| Field | Before save | Reconstructed surface / re-export |
|---|---|---|
| State/prescription flags | True / True | False / False |
| Observed/inferred masks | Explicit 2×2 arrays | None / None |
| Display/effective resolution | 2 m / 20 m | 1 m / 10 m |
| Retained cold `raster_pack` permission | True | Still True, contradicting reconstructed canonical/re-export False |

The native frontend bridge uses `serialize_surface_artifact` on reconstructed surface objects (`l10_frontend_bridge.py:191`), while `useLayer10.ts:1288` retains `raster_pack` independently. This establishes two active representation paths with different cold receipts. No browser behavior or physical action is claimed. Float32 value/explicit confidence rounding is ordinary cache encoding and was separately tolerance-checked; it is not the reported defect.

Completion: implement complete typed reconstruction of the canonical surface receipt, or preserve and reconstruct from one canonical document, then derive compatibility products from that reconstructed source. Test positive explicit capabilities as well as denials, masks, both resolutions, uncertainty, blocked reasons and geometry before/after cold loading.

## E-D03 — P2: export still manually reconstructs metadata rather than projecting the canonical receipt

`products/export.py:82` does invoke the canonical serializer, and permissions/blocks correctly use its results at 144–147. However confidence/uncertainty/masks/grids are still independently reconstructed at 111–142 and 160–170.

Native counterexamples:

- Provenance `source_grid_spec` and camel `displayGridSpec` are present in `canonical_metadata` through the serializer's supported fallback normalization, but compatibility `source_grid_spec`/`display_grid_spec` are None because export reads dictionary object attributes only (161–162). Exact parent is also affected.
- Objects with a legitimate `to_dict()` grid specification serialize canonically for all three grids. Export handles the primary grid, but drops source/display objects. These are authored supported serializer representations; ordinary production object incidence was not established.
- The new export-only `sigma` fallback (133–138) populates compatibility uncertainty while canonical `uncertainty` is None (`surface_contract.py:355–356` accepts only `uncertainty`). This discrepancy is introduced in this revision; it does not prove an actual native producer currently supplies sigma-only provenance.

These controlled representation cases support the same completion mechanism as E-D02: normalize one canonical receipt and project fields from it, rather than maintaining several fallback trees. They are not separate high-priority scientific failures beyond the connected receipt contract.

## Supplementary malformed-carrier observations and limits

- Explicit dynamic `valid_mask` exclusions are not consumed by either serializer or exporter; exporter recomputes validity solely from finite values. Since `SurfaceArtifact` has no declared valid-mask field and normal producers represent missingness with None, this is an authored extension-carrier qualification, not established normal incidence.
- Invalid values are excluded from statistics/valid_mask but remain in exported values/canonical values; authored NaN/Inf values still fail strict JSON serialization. Prior mixed-string export aborted earlier. Normal post-invariant pipeline incidence was not established.
- Extreme finite values 1e308 overflow quick mean/std to Infinity. They violate ASMAE vigor's physical domain and are supplementary admission/robustness controls, not an ordinary scientific case or newly introduced regression.
- No claim of thirteen complete georeferenced GIS files or browser selector acceptance is made; those belong to deferred Stage C.

## Reproduction and evidence

Run `python review-ab-ded7252/export/probes.py`; inspect `export/results.json` and `export/replay.txt`. The root native cache roundtrip script is independently replayable with and without `--parent`. This lane changes only its own authored probe/results/report files, not production source. Source identities are provided by the root review manifest. All package FA milestones remain open.

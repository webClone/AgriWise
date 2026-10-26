# ASMAE A+B completion gate — 70676a3

Completed 26 October 2026. Candidate `70676a3069715941ccefb3c2140d169389105189`; exact parent `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`; review branch `feat/f36-t09-asmae-13-state-publication`, independently confirmed at the candidate.

## Decision and progress

**Hold this merge for the remaining publication integration contracts. Close the demonstrated earlier repairs instead of restarting all five groups.** The old assembler math/os shadow failure, local-influence cancellation, excluded-sibling graph selection, several capability intersections, scalar flags/sanitization, cold receipt reconstruction, cleanup/commit handling and canonical export discrepancies are repaired in the fresh controls.

The principal current blocker is a **new P1 producer/consumer type mismatch**: native SIRE construction publishes an own-state uncertainty matrix, while its mandatory invariant consumer still compares that value with a scalar. The same connected review also establishes a canonical bare-soil receipt gap and an unchanged ASMAE policy key that can replay the actual parent result instead of the repaired current scientific calculation.

Finish two connected contracts in one revision:

1. **Typed per-state publication through all consumers:** sigma/normalized-diagnostic distinction, canonical state-name normalization, source/display support association and invariant consumption.
2. **Scientific cache-policy migration:** make previously committed parent semantics distinguishable from current semantics, while preserving truthful historical provenance.

Additional contradictory-carrier, affine-footprint and scalar-display-range observations are explicitly bounded below. They do not justify relabeling every repaired case as unresolved or multiplying the program into dozens of new projects. Independent expert-selector work can proceed against a frozen receipt contract; it does not close the current runtime failure. All **52 FA milestones remain open, zero checked**. Their field/program acceptance is separate from this bounded merge decision.

## 1. Source, method and limits

The GitHub commit and branch identities were verified directly. Eleven production Python modules and one TypeScript module changed. Repository tests and audit narratives were excluded as correctness inputs. Selected candidate and parent source snapshots each contain 1,087 files, matched to pinned Git blobs and SHA-256; this establishes identity, not an exhaustive audit of every repository file. The candidate recursive tree is nontruncated with 4,122 entries. All eleven changed Python modules parse successfully.

Six specialist lanes cover scientific inference, capabilities, spatial execution, scientific availability, cache integrity and export receipts. A subset of parallel attempts stopped because of runtime capacity; the resumed lanes persisted reports/scripts, and the root replays every delivered probe. The evidence bundle therefore identifies the actual final scripts and outcomes rather than claiming that every initial parallel attempt completed.

Most probes execute native production functions in isolated candidate/parent Python processes. The root independently runs actual publication validation → native save/load → serialization/re-export, and actual ASMAE-output → L1 adapter → SIRE generation → native invariant consumption. Nested runner selection/inventory/gating and pure frontend helpers are isolated exactly and labeled. Fixtures are authored offline inputs, not field observations or independently calibrated crop references.

No production source, Git ref, milestone or monograph was modified. No full provider/HTTP/browser/hardware or georeferenced file workflow was executed. The review environment lacks rasterio/pyproj: valid native assembly advances beyond the repaired lexical error into the projected-CRS dependency guard, so a complete valid ASMAEOutput return is not independently established here. That environment limitation is not classified as a production defect. Repository pytest/frontend/typecheck totals in the implementation summary remain author-reported; the independent component probes are the evidence for this review.

## 2. Disposition of the previous completion groups

| Group | Verified closure/progress | Current qualification |
|---|---|---|
| AB-R01 | Math/os lexical shadow removed; sparse uncertainty/concentration arithmetic retains holes and zero; legitimate nearest mask projection restored; missing-affine/projected-display cases repaired | Full valid assembly remains dependency-qualified; a supplied contradictory affine scale can still pass footprint admission |
| AB-R02 | Former SEM-01, SEM-02 and SEM-03 counterexamples close; HT/proxy per-node influence is counted; excluded LAI avoids graph mutation; malformed known receipts fail closed without dropping valid siblings; memory/process/counters retained | No meaningful additional ordinary scientific-path defect established in this lane; stale cached parent semantics remain a separate AB-R05 issue |
| AB-R03 | Static descriptor × ledger × metadata restrictions, snake/camel permission denials, revocation carriers and huge-integer qualification repaired in the demonstrated cases | Same-record conflicting ceiling aliases still select one token; supplied native prescription requests are newly consumed, with scientific qualification unestablished |
| AB-R04 | Numeric-zero/NaN declarations, scalar-only status, scientific scalar INV-2 and persistence type laundering repaired | Availability still uses display ranges for scalar validity; scalar producer/temporal receipts and malformed declaration handling remain bounded convergence qualifications |
| AB-R05 | Cold scientific fields and regenerated compatibility receipts agree; canonical export fallback cases close; mask dtype, detach restoration, postcommit preservation, NPZ tamper rejection and old-L10 policy rejection repaired | **New P1 uncertainty-array consumer crash**, canonical bare-soil own-receipt miss, and actual parent ASMAE-policy replay remain |

The twenty scientific candidate controls pass; the five old residual predicates are false where they were true in the exact parent. This supports closing those bounded scientific counterexamples. It does not prove independent predictive calibration or full field acceptance.

## 3. R706-PUB-01 — P1: native sigma matrix crashes the invariant consumer

**Introduced in this candidate.** `layer10_sire/surfaces/asmae.py:1765` now places the matching state sigma grid in provenance `uncertainty`. `layer10_sire/invariants.py:347,373` still reads that field and evaluates:

```python
if conf < 0.60 or unc > 0.40:
```

The normal runner calls this invariant function at `runner.py:3712`. When declared confidence/concentration is at least 0.60, Python attempts `list > float` and raises TypeError.

The root's independent native fixture supplies one finite vigor raster, own-state sigma, aggregate diagnostic uncertainty and concentration:

```python
raster_maps = {'vigor': [[0.0, 0.2], [0.3, 0.4]]}
uncertainty_maps = {
    'vigor': [[0.01, 0.02], [0.03, 0.04]],
    'ASMAE_UNCERTAINTY': [[0.2, 0.3], [0.4, 0.5]],
}
confidence_maps = {
    'vigor': [[0.8, 0.8], [0.8, 0.8]],
    'ASMAE_POSTERIOR_CONCENTRATION': [[0.8, 0.8], [0.8, 0.8]],
}
```

Actual native `adapt_l1` → `generate_asmae_surfaces` → `enforce_layer10_invariants` yields:

| Control | Candidate | Exact parent |
|---|---|---|
| One state, confidence 0.8 | TypeError: `'>' not supported between instances of 'list' and 'float'` | Invariant completes with scalar uncertainty 0.35 |
| Same state, confidence 0.2 | Completes because the OR expression short-circuits | Completes |
| Two different all-thirteen spatial-pattern fixtures | Same TypeError | Completes |

The export lane independently reproduces the same failure with its own all-state and one-state fixtures. Completing the invariant means returning its violation list, not certifying these authored inputs as valid field evidence. The full runner was not launched; the evidence proves a native producer-to-active-consumer incompatibility with the exact production call site identified.

**Completion:** preserve typed meanings through the producer and every consumer. Own-state sigma has the state's physical units; `ASMAE_UNCERTAINTY` is a normalized cross-state diagnostic. Merely averaging the matrix and retaining a universal 0.40 threshold would conflate units, especially for LAI and chlorophyll. Make invariants consume the intended normalized diagnostic or a scientifically justified state-specific criterion, while keeping the actual posterior sigma available. Verify high/low-confidence, missing-cell and all-thirteen cases through the native consumer.

## 4. R706-PUB-02 — P2: twelve canonical support receipts bind; bare soil does not

The frozen state vector names the coordinate `bare_soil_fraction`. The adapter correctly preserves `asmae_bare_soil_fraction` plus uncertainty/confidence support rasters. The generator recognizes the value alias, but its metadata and new support-grid lookup use `bare_soil` instead.

Both heterogeneous native STATE_ORDER fixtures produce thirteen state surfaces. Twelve candidate receipts contain their own expected sigma and auxiliary confidence grids; the parent contains none of those own-state grids. The candidate bare-soil receipt still contains uncertainty **1.0**, confidence **0.0**, and null own grids despite its preserved input sigma and confidence. Changing only the input spelling to the display alias `bare_soil` makes all thirteen match. This is a canonical-name binding failure, not missing source data or a failed raster generator.

Use the same canonical state registry to resolve **value, metadata, sigma, concentration/confidence and support**. Keep `bare_soil_fraction` as a required native control; alias-only tests cannot establish the all-thirteen contract.

Two related receipt qualifications stay in this same correction:

- A 2×2 native support grid can accompany aligned 3×3 display values. `source_grid_spec` is retained correctly, so this is not automatically corruption; the matrix-valued main uncertainty needs an explicit source/display-grid convention or deliberate support projection. No browser misindexing was demonstrated.
- The native producer can carry effective resolution 20 m in provenance while leaving SurfaceArtifact's non-null defaults at effective 10 m/display 1 m. Canonical/export projection now agrees, but agrees on those defaults. This predates the candidate and concerns producer field binding rather than the newly repaired export fallback. Explicit 2/20 m construction controls pass.

## 5. R706-CACHE-01 — P2: actual parent scientific results remain a current cache hit

The per-node influence change is correct when computed fresh. However both commits keep `STATE_SUPPORT_POLICY_VERSION = 'v2_receipt_bounded_20261025'` and the identical ASMAE key for the same input.

This bridge uses actual native scientific producers, not an invented Observed record:

1. The parent native HT update processes two finite zones with opposite NDVI innovations. It changes local vigor means but reports `excluded_negligible_influence`; its native ledger records vigor accepted count **0**, prior constrained.
2. The parent native cache writer commits its own reports and ledger.
3. The current native reader accepts that exact publication under the identical input/key and returns count **0** and the parent's exact reports.
4. A current fresh native calculation on the same fixture records count **1**, assimilated/indirect.

The shared key is `8d6e07aa2254e16f1402ece83ac7347a2a50dd38cea918d8e63df33b0b609494`. Byte integrity is correct; scientific semantics are stale.

The source entrypoint returns an ordinary ASMAE cache hit before validation/assimilation. `scientific_refresh` bypasses it, and foreground quick-visual follows an earlier route. Other scope/evidence/input changes can change the key. The native retained-input bridge and source return path are proven; no claim is made that every request or complete fresh provider run hits this cache.

**Completion:** change the support/operator/descriptor policy identity when these semantics change, or explicitly requalify prior committed results. A documented scoped deployment invalidation can mitigate existing cache data, but it must be concrete and verified; merge alone does not invalidate these artifacts. Keep historical outputs labeled with their historical policy.

Do not confuse this with the **closed L10 migration repair**: current L10 reading now rejects the unmodified parent publication without the new policy field. The ASMAE and L10 stores have distinct identity contracts.

## 6. Verified durable and cold-read repairs

The root independently repeats actual L10 publication validation → export → native save → cold load → canonical serialization/re-export for a positive receipt and an explicitly blocked receipt. Candidate roundtrips retain the tested masks, flags, block reasons, source/display specifications, uncertainty and 2/20 m resolutions. The cold compatibility pack equals fresh re-export. Parent loses masks/resolutions/flags or block reasons and retains a divergent compatibility pack. Float32 value/confidence differences are checked with a numerical tolerance and are not reported as defects.

Other native cache controls verify:

- original mask dtype is checked before conversion; float/NaN masks reject;
- early real conversion failure restores previously detached live surfaces and returns cleanly;
- precommit JSON failure preserves the previous generation;
- postcommit stat failure preserves the published generation;
- a same-ID/same-shape changed NPZ is rejected by its recorded checksum;
- old L10 policy manifests are rejected;
- canonical export now projects grid aliases, grid objects and sigma fallback consistently with the canonical serializer.

Close these demonstrated prior failures. Do not carry them forward merely because other receipt integration remains.

## 7. Bounded follow-ups and interpretation

The following are retained with their actual reachability and are not presented as new ordinary crashes:

| Boundary | Reproduced observation | Qualification |
|---|---|---|
| Same-record authority aliases | Snake STATE_UPDATE masks camel DIAGNOSTIC before native intersection | Authored contradictory metadata/ledger, predates candidate; normal live contradictory emission unestablished |
| Affine footprint | Origin is checked, but dimension×pixel-scale can contradict declared bounds and still admit exact/nearest masks | Supplied contradictory grid; no observed provider/browser incident. Valid nearest projection is repaired |
| Scalar scientific/display domains | Availability uses render_range; INV-2 uses scientific RANGE_MAP | Authored narrowed/expanded display ranges. Actual LAI/chlorophyll generator ranges are correct; scalar INV-2 omission is repaired |
| Scalar/temporal receipt convergence | Certain scalar-only producer values lack scalar receipt; empty prior ledger phenology/memory gates differ | Native minimal carriers and exact gate tracing, not full temporal/provider execution |
| Current L10 integrity metadata | Checksum is optional and written member metadata is not enforced | Authored altered manifest; normal writer checksum and tamper rejection are verified |

The native producer now consumes an explicit prescription permission request that the parent ignored. Authored ceiling-compatible controls transport that request; they do not establish independent prescription qualification or actual execution. The authority appendix records the trust-boundary limitation rather than calling a permission bit scientific proof. Generated diagnostic aliases remain action-denied.

These cases belong to shared qualifier/receipt definitions already in scope. Keep them visible in disposition tracking; distinguish them from the new P1 consumer regression and the demonstrated retained-policy migration gap. Deferred expert selection and GIS-file delivery remain separate Stage C work, not additional invented A+B failures.

## 8. One focused completion and readiness gate

| Parallel owner | Work | Required connected evidence |
|---|---|---|
| Typed publication/consumer | Separate normalized aggregate diagnostics from native state sigma; make every active invariant/consumer array-safe and unit-correct | Real native generation → invariant succeeds for all thirteen coordinates, high/low confidence and missing cells; retain expected warnings |
| Canonical state receipt | Resolve all value/support metadata with the canonical registry; bind native/display grids and resolutions explicitly | Frozen STATE_ORDER matches 13/13 distinct sigma/confidence patterns, including bare_soil_fraction; source/display receipt remains coherent |
| Policy/migration | Advance ASMAE scientific policy identity or requalify/invalidate old committed results | Actual parent-write/current-read bridge becomes a qualified miss/requalification, while current warm/cold controls retain equality |

Replay these as **one integrated gate**, retaining the verified scientific, permission, persistence and frontend controls. A syntactically valid exporter or matching canonical/compatibility dictionary is insufficient if a mandatory consumer crashes. Once this bounded gate passes and follow-ups have explicit disposition, reassess merge readiness without requiring all 52 program/field FA milestones to close first.

## 9. Normative anchors and pinned sources

The R3 monograph remains the target. AB-ASM-003 requires variable-specific operator/covariance support; AB-ASM-011/016 govern propagated per-variable evidence and validity; AB-ARC-005/006/007 distinguish capabilities, bounded degradation and atomic publication; AB-L10-001 requires masks, geometry, resolution and authority identical to canonical state. F36's ledger and T09/T11's projection/reproducibility obligations support these concrete checks. The master plan, sequencing addendum and task register bytes were verified against the candidate tree; the register has exactly 52 unique open FA rows.

- [State-surface producer](https://github.com/webClone/AgriWise/blob/70676a3069715941ccefb3c2140d169389105189/services/agribrain/layer10_sire/surfaces/asmae.py)
- [Native invariants](https://github.com/webClone/AgriWise/blob/70676a3069715941ccefb3c2140d169389105189/services/agribrain/layer10_sire/invariants.py)
- [L1 spatial adapter](https://github.com/webClone/AgriWise/blob/70676a3069715941ccefb3c2140d169389105189/services/agribrain/layer10_sire/adapters/l1_adapter.py)
- [ASMAE cache](https://github.com/webClone/AgriWise/blob/70676a3069715941ccefb3c2140d169389105189/services/agribrain/layer05_asmae/cache.py)
- [ASMAE runner](https://github.com/webClone/AgriWise/blob/70676a3069715941ccefb3c2140d169389105189/services/agribrain/layer05_asmae/runner.py)
- [Assimilation filter](https://github.com/webClone/AgriWise/blob/70676a3069715941ccefb3c2140d169389105189/services/agribrain/layer05_asmae/assimilation/filter.py)
- [L10 runner](https://github.com/webClone/AgriWise/blob/70676a3069715941ccefb3c2140d169389105189/services/agribrain/layer10_sire/runner.py)
- [Canonical serializer](https://github.com/webClone/AgriWise/blob/70676a3069715941ccefb3c2140d169389105189/services/agribrain/layer10_sire/surface_contract.py)
- [Raster exporter](https://github.com/webClone/AgriWise/blob/70676a3069715941ccefb3c2140d169389105189/services/agribrain/layer10_sire/products/export.py)
- [Frontend materialization](https://github.com/webClone/AgriWise/blob/70676a3069715941ccefb3c2140d169389105189/src/lib/agribrain/render-materialization.ts)

The six appendices retain each lane's precise controls, source locations, reproduction commands, closures and limitations. The bundled authored probes reproduce observations, including the remaining failures; their exit-zero replay is not a passing merge verdict.


---

# Appendix 1 — spatial lane

# AB-R01 spatial closure review — 70676a3

Candidate `70676a3069715941ccefb3c2140d169389105189`; exact parent `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`. Independent authored controls against the pinned production source, 26 October 2026. No production edits, Git mutations, repository tests/audit narratives as oracle, provider calls, browser/DeckGL run, or hardware measurements.

## Gate and disposition

**Close the prior SP-01 lexical-shadow defect. Close the prior SP-02 legitimate-nearest availability regression and its missing-affine/projected-display subcases. Keep one P2 completion item inside SP-02: affine/footprint consistency is still incomplete.** This is the existing spatial mask contract, not an additional workstream. Do not carry the old `UnboundLocalError` or different-resolution rejection forward as current blockers.

Native assembly no longer raises the parent `math` shadow error. Both keyed and sparse microzone controls execute the original method through the uncertainty, concentration, support and approval computations and reach its deliberate operator gate. Supplying a synthetic bound metric graph/operator fixture advances both forms to `require_projected_metric_crs` at engine.py:2697. The runtime lacks `rasterio` and `pyproj`; the former is required by that helper. Its catch-all returns false when import fails, so the authored EPSG:32631 fixture raises `SpatialReferenceError: crs_is_not_projected_metre`. **This is an environment qualification, not a production defect or evidence that EPSG:32631 is invalid. No full valid `ASMAEOutput` return or export is claimed.** Installed runtime and system locations were checked; no geospatial dependency was installed or mocked.

## Repairs verified

- The original `_assemble_output` contains no function-local `math`, `os`, or `np` imports. Exact parent retains local `math`/`os` imports and the same native sparse keyed call raises `UnboundLocalError: math`. Candidate native calls pass the former math and later os execution points.
- A separately labelled exact lexical-prefix control inserts only a return immediately before `retro_pm` while retaining the entire remainder of the original method for Python scope analysis. Keyed mean `[[0,null],[null,0.8]]` and sigma `[[0.2,null],[null,0.4]]` produce normalized uncertainty `[[0.4,null],[null,0.8]]` and concentration `[[0.6,null],[null,0.2]]` (floating-point rounding applies). Sparse microzone mean/sigma vectors preserve their holes through the same original arithmetic. Zero sigma produces real concentration `1.0`; missing sigma leaves concentration missing. This prefix is not presented as a full native-output proof.
- Native converter controls retain physical zero, missing cells across all thirteen state means/sigmas, negative-ID protection and endpoint-preserving bilinear interpolation.
- Exact frontend helper execution now allows a valid 2×2 mask over a 4×4 surface under `nearest_shared_bounds`; exact parent rejected it. Both use the same geographic bounds and proper resolution-specific affines. The candidate still denies the differing shapes when nearest is disallowed, and denies incompatible shear/orientation.
- The frontend now denies the previous two-pixel affine-origin shift, missing/empty mask affine, nonfinite affine and projected metric display CRS examples. Same-grid positive, finite-zero, dimension conflict and all-null support controls remain as expected.

## SP-02 residual — P2: a common origin is not a common footprint

**Locations:** `src/lib/agribrain/render-materialization.ts:179–196`, `:243–291`; active consumers `src/components/farm/map/layers/SemanticSurfaceLayer.ts:581–598` and `resolveRenderMaterialization`.

The new per-grid affine check only compares origins with the declared bounds. It never checks the far edges computed from dimensions and pixel scale. The nearest branch then requires matching signs, no shear and nearby origins, but never establishes that each affine covers its declared footprint.

Concrete authored source-native case:

| Field | 2×2 mask | 4×4 target |
|---|---|---|
| Declared bounds | `[3,35,3.0002,35.0002]` | `[3,35,3.0002,35.0002]` |
| GDAL affine | `[3,0.001,0,35.0002,0,-0.0001]` | `[3,0.00005,0,35.0002,0,-0.00005]` |
| Actual east edge from affine | `3.002` | `3.0002` |

`validateSurfaceGrid(mask)` returns `valid: true`, and `canMaterializeMask(mask,target,true)` returns **true**. Changing the mask vertical step to `-0.001` instead also returns true despite a tenfold north–south footprint mismatch. Two same-size grids carrying the same contradictory affine pass the exact-grid path too. The exact-parent nearest call returns false because of its over-restrictive coefficient-equality rule; same-size contradictory pairs were already accepted. Thus legitimate nearest availability is restored, while the promised per-grid footprint qualification is not complete.

The active image code samples masks by array dimension ratios (`sampleMask`, SemanticSurfaceLayer.ts:113–123), and the map layer receives the declared bounds. Accepting these contradictions lets the mask be stretched over cells that its own affine locates elsewhere. This proves a consumer-boundary admission gap and its source-reachable consequence. It does **not** establish incidence in a current provider-produced plot or an observed browser rendering.

**Completion within SP-02:** derive each affine's corner footprint from its dimensions and require agreement with its declared bounds using cell-scale or explicit coordinate tolerances. Apply that qualification before both exact-grid and nearest decisions, preserving the valid 2×2→4×4 positive case. Keep native scientific projected CRS separate from the geographic browser-display contract. R3 §48 `ScientificEvidence` requires spatial support, native/effective resolution, observed/gap-fill masks, uncertainty distribution and validity domain; silently stretching contradictory mask support does not establish those distinctions.

## Reproduction and limits

```bash
python review-ab-70676a3/spatial/probes.py
node review-ab-70676a3/spatial/frontendprobes.mjs
```

Python records seventeen named observations per snapshot and fourteen summarized checks. Frontend records nineteen exact pure-helper cases per snapshot and thirteen summarized checks. Both scripts exit zero when the documented observations reproduce; this includes known residual admissions and environment-qualified native denials, so these are not twenty-seven passing acceptance tests. `results.json` contains both snapshots, tracebacks, source SHA-256/Git-blob receipts and frontend extraction boundaries. Frontend executes the original helper bodies using only Node's TypeScript erasure and an in-memory module; no production implementation is rewritten.

Full engine/provider execution, full valid native output assembly/export, live browser receipt, hardware performance, and FA-stage acceptance remain outside this lane's evidence. Prior malformed scalar-type coercion is not re-promoted as an ordinary-runtime blocker here; its previous producer-reachability qualification remains unchanged.


---

# Appendix 2 — semantics lane

# AB-R02 scientific support verification — 70676a3

Candidate `70676a3069715941ccefb3c2140d169389105189`; exact parent `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`. Independent read-only component review, 26 October 2026.

**The bounded scientific software repairs pass.** All three scientific residuals in the exact-parent review close on fresh candidate/parent controls: opposite local numerical influences reach the support ledger; graph eligibility consumes the accepted state list; and the previously demonstrated missing, false-string, contradictory and malformed state receipts fail closed without losing a valid sibling. The earlier unchanged-sibling and observation-protected-memory corrections remain intact. No meaningful additional defect is established in this lane. This does not close full F36 calibration or any of the 52 FA packages.

## Reproduction and evidence

Run from the workspace root:

```bash
python review-ab-70676a3/semantics/probes.py
```

The authored probe starts isolated candidate and parent Python workers. It runs native `update_step_ht`, `update_step_proxy`, observation prediction/extraction and support construction, `build_state_support_ledger`, canonical ledger normalization, feature export, native graph regularization and `forecast_step`. The exact `accepted_target_states` assignment is extracted and compiled from each source AST, then its result is supplied to native graph regularization. This tests the runner's actual selector expression without claiming a full runner execution. `results.json` contains raw reports, per-state deltas, support ledgers, normalized counters, feature status, repair predicates and SHA-256/Git-blob receipts for the four directly reviewed source files. All 20 candidate repair predicates pass. The five previous-residual predicates are false in candidate and true in parent.

Fixtures are finite authored offline ensembles/scenes, never acquired field evidence. Fixture `real_raster` provenance is an authored input used to exercise the native classification contract. Repository tests and supplied audit narratives are not correctness evidence. The network is denied in the worker, bytecode writing is disabled, and production source is unmodified. No provider, hardware, API, browser, full engine or end-to-end field route runs here. Cache-policy bridge verification belongs to the separate root lane.

## Closure of prior SEM-01: local influence survives spatial cancellation

Candidate source: `services/agribrain/layer05_asmae/assimilation/filter.py:1752–1780` (HT), `1936–1964` (proxy). Both qualify the maximum absolute per-node mean change and maximum per-node variance reduction, rather than the absolute field-wide average mean change.

| Fresh native control | Candidate | Exact parent |
|---|---|---|
| HT opposite node vigor changes | +0.0002569886639444685 / −0.0002569886639444685; accepted vigor count 1 | Same numerical changes; count 0 |
| Proxy opposite node vigor changes | +0.00017989206476114183 / −0.00017989206476098918; accepted vigor count 1 | Same numerical changes; count 0 |
| Both paths, unchanged constant LAI | Observation delta 0; accepted count 0 | Same, retained earlier repair |
| Both paths, variable affected LAI | Accepted count positive | Same |
| Both paths, zero covariance and no effect | Numerical vigor delta 0; count 0 | Same |
| Both paths, zero innovation with informative covariance | Mean unchanged to 1e−12; accepted count positive | Same |

The HT scene uses independent pixels with identity H and opposite ±0.3 innovations around equal predicted means. The proxy scene uses narrow symmetric node ensembles around different vigor levels and a global observation equal to the joint predicted mean. Thus both routes genuinely produce cancelling local changes, without forging their receipts. The covariance-only controls guard against replacing the old global-mean rule with a mean-only rule that loses uncertainty information. **SEM-01 closes for the reported finite cancellation counterexamples.**

## Closure of prior SEM-02: graph eligibility agrees with the state receipt

Candidate source: `services/agribrain/layer05_asmae/assimilation/filter.py:359–365`; graph implementation `services/agribrain/layer05_asmae/graph/spatial_regularization.py:22–48,133–169`.

The native two-zone fixture has node-constant LAI 0.5 and 4.0, so LAI has zero within-node covariance with the NDVI observation, while vigor is genuinely affected. Candidate observation LAI delta and accepted ledger count are both zero. The exact candidate selector returns `['vigor']`, equal to the producer's accepted state set. Subsequent native graph regularization changes LAI by **0.0**. The exact parent selects `['lai','vigor']`, and native graph regularization changes LAI by **0.14000000000000012**, despite its zero observation delta/count. The qualified-list control also leaves LAI unchanged. **SEM-02 closes for the ordinary producer→selector integration.**

This is a receipt/eligibility result. It does not declare graph priors scientifically invalid, and it does not establish a prescription or direct-observation breach.

## Closure of prior SEM-03: demonstrated receipt boundaries

Candidate source: `services/agribrain/layer05_asmae/feature_export.py:119–149`. Exclusion vetoes are evaluated first, per-state input is type checked, false values are interpreted rather than Python-truth-tested, and absent positive proof defaults to exclusion.

| Authored accepted report targeting vigor | Candidate | Exact parent |
|---|---|---|
| Missing both positive carriers | Count 0 | Count 1 |
| Empty per-state influence map, no accepted list | Count 0 | Count 1 |
| `state_influenced='false'` | Count 0 | Count 1 |
| Positive per-state proof, accepted list empty, excluded list contains vigor | Count 0 | Count 1 |
| Per-state entry `False`, no accepted list | Count 0; no exception | `AttributeError` |
| Explicit boolean False | Count 0 | Count 0 |
| Malformed vigor entry plus valid positive LAI entry | Vigor count 0; LAI count 1 | `AttributeError`; aggregation aborts |

A malformed `False` entry together with an explicit accepted-target list containing vigor yields count 1 in candidate. That target list supplies independent positive proof under the implemented alternative-carrier policy; the malformed entry is not a valid contradictory `state_influenced=False` receipt. This control does not by itself establish a defect. Shape handling of arbitrary hostile objects is not exhaustively proved. **Incidence of malformed reports in normal native production is unestablished.** The native update producers exercised here emit boolean per-state proofs and lists. These are boundary qualification controls, not a demonstrated deployed malformed-input path. **SEM-03 closes for its previously reported counterexamples.**

## Retained process and counter distinctions

Observation-protected `stress_memory` remains unchanged in both native update paths. Its policy guards are at `services/agribrain/layer05_asmae/assimilation/filter.py:1608–1615,1869–1875,2061–2068,2100`. The native forecast still changes it by **0.008478260869565213** (`forecast_step`, lines 756 onward; memory branch 974–979). This confirms observation exclusion has not frozen legitimate process evolution.

Native ledger construction followed by `services/agribrain/scientific_contracts/ledger_adapter.py:127` normalization preserves direct, indirect and proxy counters separately: each positive control has accepted count 1 and exactly its own relationship count 1, with the other two zero. Native feature export also runs for all update fixtures; raw feature statuses are retained in the result, without inferring field authority from successful export.

## Scope and plan alignment

F36 (`current-plan-review/AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md:1072–1089`) calls for per-state support grounded in actual operator sensitivity and independent references. R3's execution/influence distinction (`current-plan-review/R3_current_scientific_sections.txt:320`) requires receipts to describe actual contributions and limitations. These controls establish a bounded software correction to influence accounting and eligibility, with positive and negative controls against the exact parent. They do not establish independently calibrated physiological labels, prospective predictive validity, full-engine deployment readiness, provider/hardware qualification, or package acceptance. **All 52 FA packages remain open; this lane supports only the separate bounded software gate.**


---

# Appendix 3 — authority lane

# Authority intersection cohort — independent completion verification

Candidate: `70676a3069715941ccefb3c2140d169389105189`. Exact parent: `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`. Read-only production-source review, 26 October 2026.

**Disposition: retain and close the demonstrated repairs in OwnAB-R03.** The earlier descriptor/ledger/raster-metadata capability-loss cases now deny correctly through native raw surfaces, generated aliases, and canonical serialization. A bounded same-record snake/camel ceiling conflict remains reproducible at the admitted metadata/ledger interface; normal live incidence is unestablished. It belongs to the existing authority-intersection cohort if completed, not a new series of small alias projects. This lane does not establish an executed state update, prescription, provider result, hardware action, or package acceptance.

## Reproduction and evidence boundary

```bash
python review-ab-70676a3/authority/probes.py
```

The command exits 0 and writes `results.json`, containing isolated candidate and exact-parent observations. Workers import the actual source snapshot in separate Python processes; socket connection attempts are denied. The workers use native `index_state_support_ledger`, `generate_asmae_surfaces`, `generate_asmae_aliases` and `serialize_surface_artifact`, with the documented ASMAE visual-shadow flags enabled. No production function is replaced. Source receipts include SHA-256 and Git blob hashes for the serializer, native generator, descriptors, and ledger adapter. This is component execution on authored admitted L1 data, not full-engine acquisition or downstream operational execution. Repository tests and audit statements are not the oracle.

Each snapshot runs one coherent set of 31 native invocations, including the entire 13-variable descriptor cohort, plus 11 direct canonical cases, 21 enum/value/name ceiling encodings and nine scalar permission cases. Candidate completes all 31 native invocations and generates 185 aliases across them. Exact parent completes 30 and generates 179 aliases; its enormous-integer native case raises `OverflowError`. Counts overlap and are observations, not independent end-to-end passing tests. The result contains 19 named comparison predicates; the sole candidate False predicate is the deliberately contradictory same-record ceiling cohort.

These fixtures set `diagnostic_only=False` when isolating ceiling/permission behavior. That prevents the new diagnostic-only denial from concealing whether the descriptor/metadata ceiling repair works. Separate True controls verify the diagnostic flag itself. The bare-soil descriptor uses its native `ASMAE_BARE_SOIL` semantic type and canonical `bare_soil_fraction` ledger name.

R3 §9 treats state, diagnostic, prescription and visual authority as separate dimensions (`R3-full-text.txt:1474–1510`). Its canonical projection contract says adapters cannot promote authority (`1262–1271`). This lane checks restrictions at that existing projection boundary; it does not infer scientific validation from permission bits.

## Repairs independently verified and eligible to close

| Existing problem / cohort | Exact parent observation | Candidate observation |
|---|---|---|
| Restrictive metadata DIAGNOSTIC with permissive ledger, snake or camel ceiling | Raw and serialized state permission True | Both actions False; resulting ceiling DIAGNOSTIC |
| Static descriptor maximum with ledger + metadata PRESCRIPTION_DRIVER | LAI and the other ten low-capability descriptor states grant state update | All eleven deny both actions; descriptor maximum reaches provenance |
| Metadata snake state grant plus camel False | Raw and serialized state permission True | Raw, provenance and canonical state permission False |
| Metadata `diagnostic_only=True` or `diagnosticOnly=True` | Raw and serialized state permission True | Both actions False |
| Ledger `blockReasons=['local_support_revoked']` | State permission True; restriction absent from output | Both actions False; revocation retained in canonical block reasons |
| Top-level canonical camel False beside snake True | Both actions True | Both actions False |
| Attribute `support_class='unsupported'` with permissive provenance, or whitespace-padded provenance unsupported | State permission True | Both actions False |
| Huge integer permission `10**1000` | Native generation and direct canonical serialization raise OverflowError | Both paths return denial without exception |

The native implementation now gathers static descriptor, ledger and metadata ceilings (`surfaces/asmae.py:1017–1065`) and unions ledger/metadata restriction carriers (`1067`). Native metadata permission parsing intersects snake/camel denials (`1409–1441`). Final construction applies support, effective ceiling, descriptor ceiling and diagnostic-only denial, then binds the resolved flags into provenance (`1932–1973`). The serializer now includes top-level camel permission carriers (`surface_contract.py:265–289`), intersects attribute/provenance support after whitespace normalization (`291–298`), and retains the repaired ceiling/restriction union (`245–263`, `300–322`). Scalar qualification handles arbitrary-size integers before any float conversion (`71–97`; native equivalent `asmae.py:64–81`).

Unsupported and runtime-DIAGNOSTIC controls continue to deny in both snapshots. Native canonical snake revocation and metadata camel revocation also continue to deny. These are preserved controls rather than new repairs.

All 185 candidate aliases retain False raw and canonical action flags, including aliases generated from raw native state grants and the authored contradictory-ceiling cases. The alias constructor explicitly overwrites diagnostic/action flags (`asmae.py:2290–2315`) and carries restriction reasons into the output (`2325–2352`). The equivalent completed parent alias invocations also deny. An alias is therefore not the reproduced promotion path in this lane.

The valid native vigor STATE_UPDATE control remains True for state and False for prescription in both snapshots. Direct canonical PRESCRIPTION_DRIVER controls retain explicit state and prescription grants in both snapshots. All 21 ceiling encodings produce the expected action-capability results. Numeric 0 denies; 1 grants; -1, 2, NaN, infinity, false string and huge integer deny in the candidate. This is not an all-deny implementation.

## Bounded remaining admission edge: select-one within a ceiling record

At `asmae.py:1046` the implementation selects `authority_ceiling or authorityCeiling or authority` from the ledger record; `1052` does the same for raster metadata. It then intersects the selected value from each source. A nonempty permissive snake token still masks a restrictive camel token **within that same source record** before the improved canonical serializer receives provenance.

Native authored reproducer, with ordinary finite raster values and accepted indirect vigor support:

```python
ledger['vigor']['authority_ceiling'] = 'STATE_UPDATE'
raster_metadata['asmae_vigor'].update({
    'diagnostic_only': False,
    'state_update_allowed': True,
    'authority_ceiling': 'STATE_UPDATE',
    'authorityCeiling': 'DIAGNOSTIC',
})
```

`results.json → candidate.native.metadata_same_record_snake_state_camel_diagnostic` records raw state True, canonical state True, output ceiling STATE_UPDATE, and prescription False. The generated CANOPY_ASMAE_VIGOR alias remains diagnostic and denies. The equivalent exact-parent fixture also grants state. Reversing the two ceiling values denies in the candidate (`metadata_same_record_snake_diagnostic_camel_state`). Native ledger records produce the same asymmetry (`ledger_same_record_*`): `index_state_support_ledger` admits the record, preserves its extra camel key, and the select-one line discards that key from effective authority. By contrast, the direct canonical `snake_camel_ceiling_union` control correctly denies when both surviving tokens reach the serializer.

This is a reproduced representation edge at an admitted dictionary interface, not a demonstrated contradictory emission by normal acquisition. The L1 adapter carries raster metadata into `L1SpatialData.raster_metadata` (`adapters/l1_adapter.py:305–337`) and carries existing metadata through native storage (`937–949`), but this lane has not shown a live producer emitting both spellings with conflicting values. The finding is consequently bounded to supplied contradictory carriers. It predates this candidate in observable permission outcome and is not a new regression. If OwnAB-R03 claims union of every valid ceiling carrier, collect each present token before the three-source intersection rather than selecting one; retain reverse-order and qualified positive controls in this same cohort.

## Explicit native prescription request is newly consumed

Candidate now consumes `prescription_driver_allowed` / `prescriptionDriverAllowed` from metadata (`asmae.py:1421–1430`), writes the request to provenance (`1776`), and permits it after the final capability checks. The exact parent did not copy that request. In `native.vigor_positive_prescription` an explicit True request with descriptor PRESCRIPTION_ELIGIBLE, runtime PRESCRIPTION_DRIVER and `diagnostic_only=False` produces raw/canonical prescription True in the candidate, False in the parent. The fixture has accepted indirect support and `management_zone_eligible=False`; operator/graph locks are False and mode/credit fields are proxy/False. Generated aliases continue to deny.

This is an observed behavior expansion, **not** evidence of independently qualified prescription authority. Metadata can be supplied through the production adapter (`l1_adapter.py:388`), but this lane has not established a normal upstream producer emitting the fixture's permissive combination, a downstream prescription consumer, or a requirement that raw flags repeat every alias spatial-eligibility gate. The broader review should judge the intended metadata permission trust boundary; this lane does not label the authored request a validated operational positive or invent a hardware incident from it.

No production source, Git object/ref, provider, or hardware was modified. Only this lane's `probes.py`, `results.json` and `report.md` were written.


---

# Appendix 4 — catalog lane

# AB-R04 catalog, typed availability and scientific domains

Candidate `70676a3069715941ccefb3c2140d169389105189`, exact parent `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`. Independent read-only component review, 26 October 2026. Merge remains held; this lane does not close any of the 52 FA milestones.

**Disposition: substantial repair, shared qualification still incomplete.** Close the verified pieces of prior CAT-D01/D02 below. Keep the remaining work inside the existing AB-R04 qualifier/producer convergence contract and its temporal evidence qualification; do not create a new collection of microprojects.

## Verified repairs and exact-parent controls

Native production manifest denies raw True, numeric string, malformed string, NaN and Infinity pixels, and native INV-2 records each safely without TypeError. Physical numeric zero stays available. This was already fixed in the parent and remains fixed.

The candidate now denies `has_scalar_estimate` numeric 0, 0.0 and NaN even when `scalar_value=.5`; exact parent admits those three. Known False and `"false"` flags continue to deny. Flag-only, boolean scalar, string scalar and NaN scalar remain unavailable. Valid scalar zero remains inspectable. The active inventory now reports an all-None grid with a finite scalar and authored SPATIAL grounding as `available_scalar`, where exact parent said `available_raster`. These prior CAT-D01 counterexamples are repaired.

All thirteen canonical states retain a mode, legend and palette. The full scientific boundary matrix exercises each state's lower bound, midpoint, upper bound, one below and one above, for pixels and scalars. Native INV-2 accepts legitimate boundaries and detects both out-of-domain sides for all thirteen scalar and pixel states. The exact parent detects pixel bounds but omits scalar-domain checking. LAI legend still reaches 8.0. The candidate therefore closes the scalar INV-2 omission, including type-safe rejection of invalid scalar payloads.

Native `sanitize_surface_values` now converts boolean and string pixels to None rather than laundering them into admissible floats. Before/after native manifest and invariant observations confirm True and `"0.5"` are no longer requalified. Native parent controls reproduce laundering. Legitimate zero survives. Close prior CAT-D02's demonstrated coercion defect; this lane does not claim complete cache read/write qualification, which belongs to the persistence lane.

## Remaining shared qualification contract — CAT-D01, P2 boundary finding

Locations: `products/manifest.py:278–300`; active nested `runner.py:3949–3971`; scientific INV-2 map and scalar checks `invariants.py:63–165`; schema display range `schema.py:476`.

Manifest and inventory qualify scalar domains using the surface's **display** `render_range`; INV-2 uses the per-state scientific map. Native and exact-AST controls reproduce two directions of disagreement:

| Authored carrier | Native manifest | Active inventory | Native INV-2 |
| --- | --- | --- | --- |
| LAI scalar 4, schema-default display range [0,1] | disabled | missing | no domain violation |
| Chlorophyll scalar 40, schema-default [0,1] | disabled | missing | no domain violation |
| LAI scalar 4, display [0,8] | enabled | available_scalar | no domain violation |
| Chlorophyll scalar 40, display [0,80] | enabled | available_scalar | no domain violation |
| Vigor scalar 2, expanded display [0,10] | enabled | available_scalar | domain violation |

The first two are a new authored-carrier differential from the parent, whose scalar availability did not consult the display range. The last is residual admission at a boundary, not evidence of prescription permission: INV-2 now catches the scientific violation. These fixtures also report other missing-provenance invariant violations; they are not complete valid publications.

**Normal-incidence limit:** the actual native `generate_asmae_surfaces` assigns LAI [0,8] and chlorophyll [0,80]. It does not produce the narrowed ranges above. A separately labeled intervention adds an authored scalar receipt to copies of those native outputs and confirms the correct native ranges admit the valid scalars. Consequently this review does **not** claim normal generator output loses LAI/chlorophyll scalars because of a [0,1] range.

The native producer does expose an existing receipt gap in the narrower scalar-fallback path: with authored L1 `last_values` containing LAI4, chlorophyll40 and vigor.5, enabled diagnostic-shadow rollout, and no rasters, it emits all-None state grids but carries neither `scalar_value` nor `has_scalar_estimate` into provenance. Manifest and inventory then say missing. Exact parent is identical. These are native producer outputs from a minimal authored L1 carrier, not a full Layer 1/provider run. Converge the intended scalar-only producer receipt and consumer qualification in the same AB-R04 work; do not infer that every ordinary run follows this fallback.

The flag parser also remains permissive for declared `"garbage"`, empty string and numeric 2; each with finite scalar .5 enables manifest/inventory in candidate and parent. Known denial repair is confirmed, but declaration absence, affirmative, denial and malformed cases still lack a single strict typed qualifier.

Complete the shared qualifier from canonical scientific domains, preserve scalar-only support and physical zero, use it in both availability consumers, and explicitly bind scalar fallback receipts at the producer. Display normalization must not expand scientific admissibility or suppress legitimate scientific inspection.

## Existing temporal/catalog convergence qualification — CAT-D03

Locations: native ledger `feature_export.py:74–96`; exact nested gate `runner.py:5290–5378`; canonical schema catalog and independent inventories/range tables.

Native `build_state_support_ledger([])` emits both phenology and stress memory as `prior_constrained`, zero accepted updates, relationship `none`, microzone-grid support, DIAGNOSTIC ceiling and `no_accepted_state_update` reason. The active exact runner gate denies phenology but accepts memory. Both candidate and parent do so. Explicit `model_propagated` and `temporally_conditioned` controls allow both; explicit revoked controls deny both.

This verifies producer/consumer asymmetry, not that prior-constrained memory is scientifically invalid or that a complete temporal run loses evidence. The intended distinction needs an explicit temporal/memory receipt contract and native producer-to-consumer proof. Keep it in the already-open convergence group; do not claim an introduced temporal regression. Catalog definitions, inventory enumerations and predicates remain duplicated. Deferred expert selector/GIS work is still Batch C, not an additional A+B blocker.

## Evidence and limits

Run `python review-ab-70676a3/catalog/probes.py`. It runs isolated candidate and parent subprocesses and writes both receipts into `results.json`. Each records 18 reproduced observation assertions, eight pixel type/sanitizer cases, sixteen scalar declaration/value cases, thirteen-state five-point scientific scalar/pixel matrices, five display/scientific controls, a native three-state scalar-fallback generator, and two temporal states with four controls. Assertions include repaired behavior and retained counterexamples; the count is not package acceptance.

Native functions: schema constructors, manifest builder, invariant enforcement, sanitizer, ledger builder and ASMAE surface generator. Exact isolated AST only: the active nested runner inventory assignment/loop (`3890–4100`) and nested `asmae_state_gate` (`5290–5378`), preserving predicates and line locations. The harness explicitly selects the active inventory nested in a Try, not the similarly named top-level duplicate. Source SHA-256 and Git blob receipts are included. No source edits, Git mutation, provider/browser run, full runner, or repository test was used. Existing tests/audit claims are not correctness proof.

Normative anchors in `sr-team-review/R3-full-text.txt`: AB-L10-001 requires masks, geometry, resolution and authority to match canonical state; AB-AGR-002 binds LAI/FVC/vigor/stress to support, units and uncertainty; AB-ASM-016 forbids treating local certification as global variable permission. Structural availability in these probes grants no action authority. The all-masked numeric carrier is retained only as an authored hardening observation; no full-validator survival is demonstrated.


---

# Appendix 5 — cache lane

# Native cache lane — 70676a3 versus ded7252

Read-only review of `review-ab-70676a3/source` against exact parent `review-ab-ded7252/source`, 26 October 2026. `probes.py` executes native ASMAE cache functions, native HT update and support-ledger producers, and native L10 writer/reader with the actual publication validator. No source edits, repository tests, audit narratives, provider/full-engine runs or hardware experiments. The source file digests and complete native receipts are in `results.json`.

## Conclusion

The cleanup, postcommit preservation, canonical boolean-mask validation, L10 checksum, and old-L10 policy rejection repairs are verified. **The semantic change still needs an ASMAE cache-policy migration:** a real parent-produced support ledger is replayed under the unchanged current key, so a cache hit can retain the exact scientific receipt that the fresh current computation repairs. This is the remaining meaningful connected issue in this lane; the separate root lane owns cold receipt/export reconstruction.

## Verified repairs and controls

| Native behavior | Candidate 70676a3 | Parent ded7252 |
|---|---|---|
| Ordinary ASMAE zero/None roundtrip and explicit nomask serialization | Preserved | Preserved |
| Manifest-consistent floating mask containing NaN, strict reader | Rejects before boolean coercion | Accepts and hides value77 |
| Undersized 1×1 mask for 2×2 data | Rejects | Rejects |
| Missing ASMAE support-policy commit field | Clean miss | Clean miss |
| ASMAE replacement fails before JSON commit | Returns False; previous publication readable | Same |
| Ordinary L10 publication, actual validator, save/load | Admitted and readable | Admitted and readable |
| L10 replacement fails before JSON commit | Returns0; old JSON and NPZ readable | Same |
| Injected failure converting second valid grid after first detachment | Returns0; first live values restored | UnboundLocalError; first live values empty |
| Stat fails after L10 JSON publication | Returns0; new generation remains readable | Returns0; committed NPZ deleted, read misses |
| Same-ID/same-shape NPZ replaced after native valid save | Checksum rejects | Corrupt values0.99 accepted |
| Native parent L10 publication, same L10 key, current reader | Rejects missing current policy | Parent writer saves it normally |

The exact previous malformed-string fixture now succeeds because current native sanitization converts the malformed element to None before cache extraction; it does not reproduce the old exception. The separate conversion failure is explicitly injected at the real second `np.asarray` call, leaving the actual validator and writer intact. This tests exception cleanup without incorrectly claiming a normal numeric producer emits invalid strings. Candidate paths and commit flag are initialized before the covered operations, all detach operations are inside the restoration `finally`, and cleanup respects the commit flag (`runner.py:1458–1562`).

## C-POL-706 — P2: unchanged ASMAE cache policy replays the repaired parent scientific receipt

`layer05_asmae/cache.py:72,328,791,865`; retained cache entrypoint `layer05_asmae/runner.py:334–365,497–500`.

The probe reproduces the prior semantics lane's **actual native opposing-zone fixture**, rather than authoring an Observed receipt that the parent would not produce. Two zones have equal priors and opposite NDVI innovations (+0.3 and −0.3), identity H, and narrow nonzero vigor ensembles. Both native versions move the two vigor means by approximately +0.000256988664 and −0.000256988664.

The parent producer reports `excluded_negligible_influence`, `update_applied=False`, vigor `state_influenced=False`, and the native ledger records accepted count0 / `prior_constrained`. The current native producer reports `ht_per_pixel_ensrf`, vigor influenced, accepted target vigor, and the native ledger records accepted count1 / `assimilated`, relationship indirect. The current fresh scientific repair is real.

The native parent cache writer saves **its own reports and ledger** for that result. A separate current process, using the identical ASMAEInput and isolated retained cache directories, reads that exact publication successfully. Its loaded vigor accepted count is0, and its loaded report list equals the actual parent's report list. There is no authored false direct-observation metadata in this bridge.

Both versions use support policy `v2_receipt_bounded_20261025` and the same native key:

`8d6e07aa2254e16f1402ece83ac7347a2a50dd38cea918d8e63df33b0b609494`

The cache reader verifies this unchanged policy string, so it cannot distinguish the parent global-summary influence semantics from the current per-node influence semantics. Correct byte hashes do not requalify the scientific meaning of those bytes.

**Retained entrypoint qualification:** native `ASMAERunner.execute` builds the input and, for modes reaching ordinary cache lookup, returns a cache hit before `_validate_contracts` and assimilation. `scientific_refresh` explicitly bypasses this cache. A foreground `quick_visual` has an earlier snapshot branch and is not the ordinary route demonstrated here. Worldline hydration, capability preparation, input changes and upstream evidence changes can change identity or route before lookup. The executed bridge proves native parent-write/current-read for an identical retained input; source inspection establishes the pre-assimilation return. It does not claim every production request or complete fresh pipeline hits this key, nor was the full runner/provider chain executed.

Complete the current scientific repair by changing the ASMAE support/descriptor/operator policy identity or explicitly requalifying prior publications. Preserve historical metadata where needed, but do not return old-policy support receipts as current qualified evidence.

## Bounded integrity observations, not independent completion blockers

The current L10 writer records a checksum and `surfaces_member_metadata`, and the checksum successfully rejects an altered NPZ. The reader, however, treats the checksum as optional (`runner.py:1612–1618`) and never consumes `surfaces_member_metadata`; it checks only value-member count, required IDs and two-dimensionality. A current native publication with only its JSON metadata changed to claim shape999×999 / dtypeint16 still loads. Deleting the checksum and member metadata from a current-policy manifest permits an altered NPZ containing values0.97 to load. These are explicitly authored manifest-integrity fixtures, not observed normal-writer output or evidence of a disk/attacker incident. They establish that the new member manifest is currently descriptive rather than enforced. A strict current-schema reader should require and validate the written checksum and member metadata together.

The ASMAE compatibility loader still coerces floating masks before checking dtype (`cache.py:698–706`) and accepts the same float/NaN fixture. Canonical deserialization uses the strict manifest reader, which is repaired and rejects it. No canonical replay through the compatibility helper is established; this observation should not be presented as undoing the verified strict-reader repair or as another blocker.

L10 policy migration is a genuine repair despite the separate ASMAE issue. Both versions' authored input gives the same L10 key `6f4834c43c114d046b4c44df83096325`, but the candidate reader rejects the unmodified native parent publication because it lacks `asmae_support_policy_v2`. It also rejects a current manifest with that field removed. The previous broad retained-L10 policy finding is therefore closed for this exact parent/current migration.

## Reproduction and limits

Run `python review-ab-70676a3/cache/probes.py`. It launches isolated exact-parent and current subprocesses, shares only authored native retained-publication fixtures, verifies all seven main assertions, writes `results.json`, and removes temporary fixtures. Only L10 `runner.__file__` is rebased to isolate its hardcoded relative artifact root; ASMAE directories are also rebased. The publication validator is neither replaced nor stubbed. The runtime is denied network access. No source mutation, full-provider execution, multiprocess race, power-loss durability claim, or repository test oracle is involved.


---

# Appendix 6 — export lane

# Scientific export receipt — candidate 70676a3

Candidate `70676a3069715941ccefb3c2140d169389105189`; exact parent `ded72528ce12a2f1cb4ca6a208ddcc2accc3802a`. Read-only review and fresh native component probes, 26 October 2026. Only this directory's authored `probes.py`, `results.json`, and `report.md` were written. No repository tests, audit narratives, provider calls, full engine, server, browser, or hardware were run.

## Disposition

**Keep the canonical export projection repair; AB-R05 remains incomplete at the connected typed state-receipt boundary.** The own-state grid repair works for twelve canonical state names, but breaks an active native invariant consumer and omits the thirteenth state's support receipt. These belong in the same A+B receipt correction and native acceptance gate, rather than separate expert/GIS feature projects.

R3 `AB-L10-001` requires masks, geometry, resolution, and authority identical to canonical state (`sr-team-review/R3-full-text.txt`, lines 10591–10594). `AB-ARC-005` separates capabilities (10124–10127), and `AB-ARC-007` forbids an incompatible partial result replacing validated canonical state (10132–10135). This lane does not establish full GIS-file or browser acceptance and does not reopen deferred Stage C work.

## Closed and retained repairs

The native path is authored ASMAE output → real `adapt_l1` → real `generate_asmae_surfaces` → canonical serializer → real raster exporter, with the genuine diagnostic rollout environment flag enabled. Candidate and parent execute in separate fresh Python interpreters, with independent module identities and no substituted production functions.

* **Prior E-D03 is closed for its reproduced counterexamples.** `products/export.py:111–119` now projects canonical source/display grids, masks, resolutions, confidence, and uncertainty. Both provenance grid aliases and legitimate `to_dict()` grid objects export identically to the serializer. The parent loses source/display grids. The sigma-only fallback now exists canonically too (`surface_contract.py:356`); parent canonical uncertainty was null while compatibility uncertainty held the grid. All six authored receipt-control cases have zero candidate canonical/export differences.
* Explicit 2×2 confidence/uncertainty grids, explicit observed/inferred masks, camel mask aliases, display/effective resolutions 2/20 m, positive capabilities, and provenance revocations retain canonical/export parity. Physical zero remains a valid pixel and enters statistics; null remains invalid. These are declaration/transport controls, not validation that a field product has measurement support or prescription authority.
* Two native fixtures independently give every one of the thirteen frozen `STATE_ORDER` states a distinct spatial sigma and confidence pattern. Twelve candidate state receipts retain exactly their own sigma matrix and auxiliary confidence matrix; parent retains zero own-state matrices. A second fixture changes all patterns, retaining the same 12/13 result. Matching against every state's own expected grid excludes aggregate substitution and cross-state substitution for those twelve coordinates.
* Canonical/export `confidence` is an own-state scalar mean, while the own confidence matrix survives in `provenance.confidence_grid`. This alone is not reported as a fresh loss: the auxiliary grid is available. The generator's classification still calls it posterior concentration and declares calibrated confidence unavailable. Its adequacy/calibration is outside these transport probes.

## E-D01 / P1 — the repaired producer now sends a sigma array into a mandatory scalar invariant

**New native producer-to-consumer regression.** `surfaces/asmae.py:1765` changes provenance `uncertainty` from a scalar diagnostic into the own-state sigma array. `invariants.py:347,373` still obtains that field and evaluates `if conf < 0.60 or unc > 0.40`. `runner.py:3712` calls this native invariant function in the normal run path.

Minimal fresh native control, with one vigor state and both own-state and aggregate confidence 0.8:

```python
raster_maps = {'vigor': [[0., .2], [.3, .4]]}
uncertainty_maps = {
    'vigor': [[.01, .011], [.013, .018]],
    'ASMAE_UNCERTAINTY': [[.7, .8], [.9, 1.]],
}
confidence_maps = {
    'vigor': [[.8, .8], [.8, .8]],
    'ASMAE_POSTERIOR_CONCENTRATION': [[.8, .8], [.8, .8]],
}
```

| Native control | Candidate | Exact parent |
|---|---|---|
| One state, confidence 0.8 | `TypeError: '>' not supported between instances of 'list' and 'float'` | Invariant completes with scalar uncertainty 0.85 |
| Same state, confidence 0.2 | Invariant completes; short-circuit bypasses sigma comparison | Invariant completes |
| Thirteen canonical states, heterogeneous fixture A | Same `TypeError` | Invariant completes |
| Thirteen canonical states, heterogeneous fixture B | Same `TypeError` | Invariant completes |
| Thirteen surface-alias state names, all grids attached | Same `TypeError` | Invariant completes |

The component call proves an active consumer incompatibility; the full runner was not launched. “Completes” means returns its violation list, not that these authored diagnostic fixtures qualify as valid scientific publications. Candidate export by itself succeeds and preserves parity, which is insufficient to close the connected contract.

Correction must preserve separate meanings: own-state posterior sigma is in the state's physical units (for example LAI or chlorophyll units), whereas `ASMAE_UNCERTAINTY` is a normalized cross-state aggregate diagnostic. Simply averaging the list and applying the generic `0.40` threshold would silence the exception while conflating those quantities. Use explicitly typed fields/semantics, keep native sigma bound to its state, and make the invariant consume the intended normalized diagnostic or a state-specific unit-aware criterion. Replay high-confidence and low-confidence native controls before declaring the receipt contract complete.

## E-D01 / P2 residual — canonical bare_soil_fraction loses its support receipt

**Existing canonical-name gap, newly relevant to the all-thirteen repair claim.** The frozen production `state/descriptors.py:128–143` names the eighth coordinate `bare_soil_fraction`. The adapter installs its state raster and support rasters as `asmae_bare_soil_fraction`, `asmae_bare_soil_fraction_uncertainty`, and `asmae_bare_soil_fraction_confidence`. The generator recognizes the value alias (`surfaces/asmae.py:1361–1362`), but metadata lookup (1343–1348) and new support-grid lookup (1450–1459) use `bare_soil` only.

Both heterogeneous canonical-name fixtures produce all thirteen surfaces. The candidate bare-soil receipt has uncertainty **1.0**, confidence **0.0**, and both auxiliary grids **null**, even though the adapter retains sigma `[[.08,.081],[.083,.088]]` and confidence `[[.48,.58],[.68,.78]]` for that state in fixture A. Those zero/default values are not missing input. The parent exhibits the same bare-state defaults. Changing only this fixture's input spelling to the display alias `bare_soil` attaches its own grids and makes the candidate match **13/13**. This positive control localizes the mismatch to state-name normalization rather than absent raster generation.

Use one canonical state-key mapping for the values, metadata, sigma, confidence, and support receipt. Keep the production frozen name as an acceptance case; a display-alias-only fixture cannot close all thirteen coordinates.

## Spatial and resolution qualifications within the same receipt contract

The generator binds support grids before it aligns the state value grid. A native 2×2 source and valid 3×3 target over the same geographic extent produce 3×3 values and a 3×3 display `grid_spec`, but canonical/compatibility `uncertainty` remains the original 2×2 matrix; auxiliary confidence also remains 2×2. `source_grid_spec` correctly remains 2×2. Thus the shape mismatch alone does not prove corruption: retaining source-native auxiliary support can be legitimate if its grid association is explicit. Here the newly matrix-valued main `uncertainty` field has no distinct `uncertainty_grid_spec` or declared array-grid convention, and the main state receipt's default grid describes the display values. No browser/pixel consumer misindexing was demonstrated. Treat this as an acceptance qualification requiring an explicit source-grid binding or deliberate support reprojection, not a separate demonstrated end-user GIS defect. Parent uncertainty is scalar 0.85, so it has no array-shape ambiguity in this fixture.

Native adapter-declared resolution is 20 m and generator provenance `effective_resolution_m` is 20 m, but canonical/export effective resolution remains the `SurfaceArtifact` default 10 m, with default display resolution 1 m. This is identical in the parent, caused by constructing the surface without explicit resolution attributes while canonical serialization prioritizes those non-null attributes. Canonical/export projection now correctly agrees; projection alone cannot repair a producer receipt already containing defaults. The explicit-surface 2/20 m control passes, distinguishing producer omission from export loss. This is a residual within qualified receipt construction, not a newly introduced export regression.

The native missingness control uses a valid physical zero and a null cell in values, sigma, and confidence. Candidate sigma preserves null, strict JSON succeeds, and `valid_mask` is `[[true,true],[false,true]]`. Generated observed/inferred masks remain null in this fixture (as in the parent); this lane does not reinterpret a derived posterior state's availability mask as direct measurement support. Explicit declared observed/inferred mask transport is separately verified.

## Reproduction and limits

Run `python review-ab-70676a3/export/probes.py`. It executes candidate and exact-parent controls, asserts the contrasts above, and writes strict JSON `results.json`. Its console output summarizes counts, invariant completion, and receipt differences; the file contains each state's actual and expected grids, metadata, masks, and geometry. No repository test suite or historical report is the correctness oracle. Cold reconstruction is independently owned by the root/cache lanes and is not certified here. All package FA milestones remain open.

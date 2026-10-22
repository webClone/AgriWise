# ASMAE: thirteen latent states and the missing map products

Independent source review completed 22 October 2026. Repository: webClone/AgriWise. Current reviewed main: **90ab701714554c7b786bba4ac6b19259e77279ce**. Baseline investigation: 5344930dfc7fbab7f7277bf61f99fc252dd88bc6. The new main contains three further commits and eight production changes in F01 perception/fusion paths. ASMAE, SIRE, the reviewed map frontend and the three governing plan documents have identical blobs across these revisions. The focused probes were replayed with current-main source and dependencies.

**Your central diagnosis is correct: thirteen model coordinates do not currently form thirteen independently inspectable, scientifically qualified map products. The arrays survive further downstream than a simple thirteen-to-eleven narrative suggests.** Dedicated product definitions, state-specific authorization, expected-product inventory, and frontend selection are the main gaps. Some absent maps are appropriate degraded behavior, and one additional scientific-labeling fallback needs correction.

This is a read-only review and a proposed repair sequence. No production source, Git branch, plan checkbox, provider, controller, drone, optimizer, or prescription was changed or executed. Repository tests, reported test totals and historical audit assertions were excluded as correctness evidence. All 52 FA milestones remain open.

## 1. Claim-by-claim verdict

| Your finding | Independent verdict | Necessary precision |
|---|---|---|
| ASMAE declares thirteen latent variables. | Confirmed. | Config and descriptors agree on a frozen thirteen-coordinate order. The coordinates have different physical, hypothesis and memory roles. |
| Dedicated SIRE products cover eleven states, omitting phenology and memory. | Confirmed. | Both lack dedicated state SurfaceType, render-mode and manifest entries. Phenology still contributes to a composite diagnostic renderer. |
| Missing scenes or mean-only mode can leave no scientific rasters. | Confirmed. | Actual fallback calls emit nonspatial posterior information. Mean-only routing keeps thirteen debug surfaces while clearing scientific raster dictionaries. This is an intentional support restriction. |
| L1 can reject grids contradicting their metadata. | Confirmed source contract. | Valid raster transport itself accepts all thirteen states. The eleven-entry scalar evidence map is a separate projection. |
| SIRE requires incoming data and rendering permission. | Confirmed by native calls and isolated authorization execution. | A registered/enabled mode does not establish pixel authorization or browser materialization. |
| Uniform or ungrounded arrays are not authorized as ASMAE pixel overlays. | Confirmed with scope. | Uniform grids can still support truthful plot-level cards/tints. Do not invent spatial variance to satisfy a pixel gate. |
| LAI, structure, bare soil and thermal stress have unmapped state gates. | Confirmed and incomplete. | **Surface wetness is a fifth unmapped state.** Its name contains WETNESS, not WATER. |
| Canopy water is checked against vigor. | Confirmed in both directions. | Canopy-water-only support is refused; vigor-only support passes the canopy-water state gate. Root-zone water also accepts canopy-water support. |
| Nine frontend modes prevent thirteen independent maps. | Product concern confirmed; mechanism corrected. | The actual UI has six base lenses and nine independent overlay toggles. Fixed priorities and absence of an expert state picker cause the independent-selection gap. |
| `_microzone_to_grid` zero initialization can confuse missing support with zero. | Confirmed conditional behavior. | Removing an interior node leaves thirteen zero placeholders. The complete native graph fixture assigns every cell; routine missing cells were not established. |
| Arrays and NPZ differ from thirteen downloadable GeoTIFF/COG products. | Confirmed for the inspected publication route. | The cache preserves all thirteen states; the canonical frontend payload already preserves geographic/quality metadata; a generic L1 GeoTIFF writer exists. No complete thirteen-state ASMAE/SIRE GIS delivery hookup was found. |
| All thirteen should appear in an expert inventory with explicit unavailability. | Supported design direction. | Presence in the catalog must not imply an observed, identified, calibrated or renderable state. |

The corresponding exact source references and fresh fixture receipts appear in the five specialist appendices. The user-facing diagnosis should therefore be: **state generation and raster transport have thirteen-state capacity; publication and independent inspection do not yet provide a complete thirteen-state contract.**

## 2. Where all thirteen arrays actually survive

The native lower-level EnKF was called with a real 3×3 graph and an empty observation list. It produced thirteen mean vectors and thirteen sigma vectors per node. The unmodified converter made **117 assignments in each collection**: thirteen coordinates times nine cells. This establishes numerical capacity and assignment behavior, not a remotely observed agricultural result.

An actual carrier chain then ran runner serialization, `run_layer1_fusion_v1`, `build_legacy_fieldtensor` and SIRE `adapt_l1`. It retained:

- thirteen state grids plus thirteen uncertainty grids;
- **26 RasterRefs** and **26 FieldTensor map keys**;
- the same 26 underlying grids in SIRE, represented by **52 upper/lower-case aliases**;
- thirteen feature-pack state/status entries, including phenology progress and stress memory.

Those fixture states were prior-constrained with zero weight. No spatial authority is inferred from their numeric survival. The separate scalar EvidenceItem mapping lists eleven states, but it does not remove the other two raster arrays. See [services/agribrain/layer1_fusion/adapters/asmae_adapter.py:L371-L412](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer1_fusion/adapters/asmae_adapter.py#L371-L412) and [services/agribrain/layer10_sire/adapters/l1_adapter.py:L892-L1022](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer10_sire/adapters/l1_adapter.py#L892-L1022).

The actual ASMAE cache writer/reader round trip also retained **thirteen states in each of three fields: 39 arrays** across state means, uncertainty and confidence. Valid zero, full-precision fixture values, nodata and the geographic envelope survived. Cache eligibility/schema failures can reject a whole entry, but no eleven-state cache whitelist exists in this path. See [services/agribrain/layer05_asmae/cache.py:L684-L690](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer05_asmae/cache.py#L684-L690).

## 3. Corrected state-by-state publication matrix

This matrix describes dedicated products and the current state gate. It does not certify any current plot. The positive authorization fixture supplies aligned nonconstant rasters, current-spatial/visualization flags, accepted indirect support, appropriate evidence families and BMA/retro proof. Production authority is false, so permitted pixels use the diagnostic tier.

| Latent coordinate | Dedicated SIRE product | Current state-gate behavior | Positive diagnostic fixture |
|---|---|---|---|
| vigor | ASMAE_VIGOR | Requires vigor support | Allowed |
| lai | ASMAE_LAI | No rule | Denied |
| chlorophyll | ASMAE_CHLOROPHYLL | Requires chlorophyll support and nutrient family | Allowed |
| canopy_water | ASMAE_CANOPY_WATER | Consults **vigor**, plus water family | Allowed through wrong-variable lookup |
| root_zone_water | ASMAE_ROOT_ZONE_WATER | Accepts canopy-water **or** root-zone support | Allowed; own-variable linkage is not enforced |
| surface_wetness_event | ASMAE_SURFACE_WETNESS_EVENT | No rule | Denied |
| structure | ASMAE_STRUCTURE | No rule | Denied |
| bare_soil_fraction | ASMAE_BARE_SOIL | No rule | Denied |
| salinity_stress | ASMAE_SALINITY_STRESS | Salinity support and salinity-specific family | Allowed within fixture; no EC calibration claim |
| thermal_stress | ASMAE_THERMAL_STRESS | No rule | Denied |
| biotic_confounder_risk | ASMAE_BIOTIC_CONFOUNDER_RISK | Global BMA plus real holdout proof; no own-state count check | Allowed within fixture; no confirmed disease claim |
| phenology_progress | Missing dedicated product | No dedicated registration | Not generated as a dedicated state surface |
| stress_memory | Missing dedicated product | No dedicated registration | Not generated as a dedicated state surface |

Native generation produced all eleven registered state surfaces. Execution of the exact authorization statements permitted diagnostic pixels for **six of eleven** in this deliberately positive fixture. Five were denied with `surface_state_requirement_unmapped`. See [services/agribrain/layer10_sire/schema.py:L148-L160](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer10_sire/schema.py#L148-L160), [services/agribrain/layer10_sire/runner.py:L5126-L5180](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer10_sire/runner.py#L5126-L5180).

The authorization statements were compiled unchanged from the pinned AST with reviewer-supplied surrounding carriers; the full integrated runner was not executed. This distinction matters because successful isolated policy execution does not prove provider acquisition, job completion, current publication, or browser rendering.

Replacing substring matching with canonical state identities is warranted. Its predicates must reflect each coordinate's scientific role: a memory accumulator or model-propagated phenology estimate cannot simply be required to have a direct observation count to become available for diagnostic inspection.

## 4. Additional confirmed concern: an upstream real raster can become an Observed state badge

The native generator was exercised with identical aligned arrays under three support conditions:

| Supplied state support | Result on all eleven generated state surfaces |
|---|---|
| Explicit accepted indirect support | Indirectly-Constrained; direct_observation=false |
| Explicit prior-only support | Prior-Constrained; direct_observation=false |
| Per-state ledger absent, real evidence and real_raster metadata retained | **Observed; directly_assimilated; direct_observation=true** |

This fallback is at [services/agribrain/layer10_sire/surfaces/asmae.py:L482-L527](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer10_sire/surfaces/asmae.py#L482-L527). It promotes the classification from global raster reality when per-state classification cannot resolve. The returned classification also marks management-zone/statistics eligibility. The exercised surface provenance still denies state updates and remains diagnostic. This is a confirmed misleading metadata fallback, **not a demonstrated prescription execution or end-to-end authority escalation**.

The normal full engine builds and exports a per-state support ledger, so the review does not claim ordinary fresh runs always take this branch. Direct, legacy, migrated or incomplete inputs must nevertheless remain truthful at the accepted SIRE boundary. Adding two product names without fixing this fallback would extend a fragile classification policy.

The scientific descriptors distinguish indirect vigor/canopy/root-zone estimates, partially identified LAI/chlorophyll/phenology, salinity and biotic hypotheses, and a visualization-only stress-memory accumulator. Stress memory is described as NOT_ASSIMILATED while the index registry registers a stress_memory_index update target. That descriptor/update-map drift also needs reconciliation before generating a canonical publication registry. Registered update targets do not prove independent identifiability. See [services/agribrain/layer05_asmae/state/descriptors.py:L269-L333](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer05_asmae/state/descriptors.py#L269-L333).

## 5. The frontend needs an expert state catalog, not merely more broad modes

The mounted Layers tab exposes six base radio choices, nine overlay checkboxes and source-policy controls. The existing expert interface displays engine analysis, broad-mode status, rejection and authority reasons. It does not provide thirteen individual state selections. See [src/components/farm/intelligence/MapLayerDock.tsx:L64-L85](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/src/components/farm/intelligence/MapLayerDock.tsx#L64-L85) and [src/hooks/useLayer10.ts:L993-L1053](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/src/hooks/useLayer10.ts#L993-L1053).

The actual pure TypeScript selection resolver was executed offline. With both water aliases authorized, it selects canopy water. When canopy water is denied or absent, root-zone water is correctly available as a fallback. It cannot be deliberately selected instead of an authorized higher-priority canopy-water product through the current broad Water lens. Raw LAI is not a candidate in any existing lens. Finite data without authorization remains blocked.

There are also two independent hardcoded inventories: **43 backend known surface types** and **22 frontend types**. They enumerate selected aliases and diagnostics rather than every latent-state product. Existing mode-level reasons therefore cannot explain every missing state's lifecycle. See [services/agribrain/layer10_sire/runner.py:L3799-L3830](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer10_sire/runner.py#L3799-L3830) and [src/lib/agribrain/plot-map-evidence-state.ts:L1165-L1175](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/src/lib/agribrain/plot-map-evidence-state.ts#L1165-L1175).

The frontend fixture called thirteen raw products is eleven registered states plus two diagnostic products, effective resolution and posterior concentration. It must not be mistaken for a test of all thirteen latent coordinates. The model-coordinate inventory is established separately by the engine and SIRE matrices.

The live API path preserves a full canonical surface list and proof/authorization fields; the hook normalizes every returned surface before lens selection. Inspection of that path did not establish a blanket nine-surface transport limit. Browser display also waits for publication validation and materialization receipts. No live HTTP or browser run was performed in this review.

## 6. Nodata, degradation and downloadable GIS files

The zero-initialization concern is valid at the converter boundary. One deliberately missing interior microzone leaves thirteen zero placeholders; a short vector leaves its omitted coordinates zero. The normal complete fixture assigns every cell, so this does not establish routine holes in production. Fix completeness/masks while preserving a valid physical zero. See [services/agribrain/layer05_asmae/engine.py:L3255-L3324](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer05_asmae/engine.py#L3255-L3324).

Missing scenes and mean-only inputs intentionally produce no scientific rasters. Native no-scene calls retained supported nonspatial information without spatial references. Mean-only assembly routing cleared scientific state/sigma maps and retained thirteen diagnostic debug grids. Those assembly calls later stopped at a grid gate because this review environment lacks Rasterio. The trace proves the routing before that gate; it does not prove completed output assembly or a field execution.

Uniform finite grids may be legitimate plot-level estimates. Current ASMAE pixel policy rejects their spatial overlay, while soft plot-level information remains possible. A registry or expert selector should report this state honestly rather than create heterogeneity to get a map.

GeoTIFF/COG is a separate delivery decision. The lightweight raster export contains arrays and metadata, while the canonical surface serializer already preserves CRS/grid specifications, masks, confidence and uncertainty. COG/tile/STAC reference fields are extension slots; they are not generated files. A generic L1 GTiff writer exists, but no complete per-state ASMAE/SIRE writer/commit/download hookup was found in the inspected route. See [services/agribrain/layer10_sire/surface_contract.py:L101-L180](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer10_sire/surface_contract.py#L101-L180) and [services/agribrain/layer1_fusion/raster_backend.py:L227-L274](https://github.com/webClone/AgriWise/blob/90ab701714554c7b786bba4ac6b19259e77279ce/services/agribrain/layer1_fusion/raster_backend.py#L227-L274).

R3 supports qualified arrays and COG/Zarr storage. It does not require thirteen separate GeoTIFF files. A versioned multiband COG or time-aware Zarr can also meet the product contract if each band's variable, units, masks, uncertainty, time, resolution and lineage are explicit. Scientific arrays and browser previews must retain the same canonical identity.

## 7. Repair sequence grounded in the existing plan

The work should be framed as a bounded **F36/T09** publication and support slice, with F38/T11 identity/degradation integration where applicable. F02 remains observation-time/availability-at-issuance work. These discoveries do not establish a regression in the earlier F01 closures or a reason to halt independent F02 work.

| Order | Concrete scope and principal targets | Acceptance evidence |
|---|---|---|
| 1 — State identity and classification | Reuse frozen config/descriptors and canonical aliases. Reconcile memory's descriptor/update policy. Replace global-raster-to-Observed fallback with per-state qualified classification. Targets: state/descriptors.py, observation/index_state_mapping.py, scientific_contracts/state_support.py, surfaces/asmae.py. | Identical arrays with accepted indirect, prior-only, hypothesis and missing proof keep their correct labels and permissions. Missing proof never creates direct-observation status. Legitimate zero survives. |
| 2 — Explicit publication predicates | Replace substring rules with state/product lookup and named family/support predicates. Correct canopy/root water and all five unmapped states. Define model/memory diagnostic predicates without manufacturing accepted observations. Target: layer10_sire/runner.py plus shared registry. | Each surface responds to its own supporting evidence. Vigor alone cannot qualify canopy water; canopy water alone cannot certify root-zone water. Hypothesis display remains labeled. Missing/invalid geometry or permission still blocks pixels. |
| 3 — Thirteen-product schema and availability catalog | Add dedicated phenology/memory product definitions, units, palettes and modes. Derive generator, manifest, backend/frontend inventory and alias mappings from one versioned contract. Preserve existing numeric state order. | Exactly thirteen stable latent-state rows exist for full, partial, prior-only and no-scene inputs. Every row reports generated/absent, scope, uncertainty availability, permission and reason. Registration alone grants no render authority. |
| 4 — Expert selection in the existing interface | Add state/product selection beside the farmer lenses. Allow deliberate canopy/root-water selection. Bind mean, native-unit uncertainty, support masks, times and source provenance to the same immutable product. | Each eligible state can be selected independently. Unavailable states remain visible with reasons. Selector, pixel inspector, histogram and legend use the same authorized artifact and actual materialization receipt. |
| 5 — Converter and persistence parity | Validate full state vectors/node coverage, apply nodata/valid masks, preserve native grids through warm/cold/cache paths. Retain the existing validated ASMAE NPZ transaction. | Omitted-node and short-vector cases fail explicitly or yield nodata, never unqualified physical zero. Full native zero remains valid. All thirteen mean/uncertainty/state-status identities survive cold reload. |
| 6 — Scientific file delivery, if selected | Implement verified scientific COG/Zarr/GeoTIFF artifacts, immutable commit and download references with CRS/affine/nodata, units, uncertainty, support and time metadata. Reuse generic raster capability where suitable. | Open the exported files independently, verify geographic extent and cell values/masks, and compare them to the canonical arrays. Publish references after successful artifact commit. No file is advertised for an unavailable state. |
| 7 — Real plot execution and integrated acceptance | Trace one exact plot/cycle/geometry/run identity through scene admission, solver, state support, cache, L1 references, SIRE products, API and browser. Include sparse/no-scene/mean-only and failure cases. | A thirteen-row receipt identifies the first blocking stage for each state. A map count is never the sole pass criterion. Pixel values, uncertainty, masks, permissions and issuance/availability time agree across consumers. |

F36 owns per-variable support/calibration and declares F01/F02/F24/F29 dependencies for full acceptance. T09 owns map projection and expert/farmer explanation, with F30/F31/F32/T01 dependencies for its full package. The execution addendum permits bounded slices when their own prerequisites exist. This is not a proposal to wait for every world-model/Omega component before fixing a mapping or truthful inventory, and it does not close full F36/T09 acceptance.

## 8. What is still needed to diagnose your particular plot

No current production plot response, execution log or browser session was examined. The observed repository gaps are real, but a specific missing LAI map can still be blocked earlier by scene support, mean-only fallback, geography, cache eligibility or publication freshness.

For one exact execution, collect the run/cycle/geometry and schema IDs; requested and selected resolution; scene admission counts; scene-stack mode; state/sigma keys and finite coverage; per-state support/uncertainty; source/display grid; cache hit/eligibility; L1 references; generated surface IDs; per-state family/gate reason; canonical publication head; policy/mode/role authorization; frontend selected surface and materialization receipt. Preserve both observation time and availability-at-issuance. These diagnostics identify the first divergence without disabling the scientifically necessary guards.

**Proceed with a bounded map-publication repair based on the corrected matrix. Do not describe the current system as delivering thirteen independent state maps, and do not solve it by forcing thirteen apparently valid rasters.** The previous F01 merge decision and independent F02 development remain separate from accepting this capability.

## 9. Evidence and practical limits

Five specialist lanes plus coordinating source review produced the analysis. Current-main replay executes six top-level commands. Engine has thirteen cases/ten checks; exporter sixteen checks; frontend selection six checks; SIRE has thirteen matrix rows, ten mapping controls, eleven lifecycle fixtures, five native geometry/content cases, three native support-label cases and terminal/contract cases. These counts measure different things and are not summed into a repository-test total.

All **1,086 staged production/configuration/document files** match current Git blobs. That count establishes identity, not coverage. Native production functions are used where reported; the integrated runner's authorization block is explicitly AST-isolated. Full assembly is environment-blocked after observed routing. No full inference-to-browser production execution, field accuracy, calibration, physical hardware operation, or FA sign-off is claimed. The evidence bundle contains the authored scripts, fresh results, exact source manifests, selected normative references and a read-only reconstruction helper; production source and repository tests/audits are excluded.

The five appendices retain detailed source spans and scope qualifications. In particular, frontend fixture names cover eleven state products plus two diagnostics, while the engine/SIRE state-order matrices cover the actual thirteen latent coordinates.


---

# Specialist appendix: State generation and native transport

# ASMAE state generation and transport — current-main replay

Reviewed commit: `90ab701714554c7b786bba4ac6b19259e77279ce`. This is a fresh replay of the bounded native probes originally prepared at `5344930`. The relevant ASMAE, raster-ingestion and SIRE-adapter source blobs are unchanged. Current dependencies are verified against the new tree.

**All thirteen state and uncertainty arrays can reach SIRE.** The scalar evidence adapter has an eleven-state mapping, but it is a separate projection from raster transport. No eleven-state raster whitelist was reproduced in the actual L1 transport chain.

## Fresh native observations

| Exercised boundary | Result | Qualification |
|---|---|---|
| Config and descriptors | Same thirteen names, indices and order | Declared model coordinates, not thirteen independently observed quantities |
| Native 3×3 graph and lower-level EnKF | Thirteen mean grids and thirteen sigma grids; 117 assignments to each collection | Empty observation list, prior-only numerical fixture; no spatial-observation certification |
| Complete native microzone collection | Every rectangular cell assigned; no initialized zero holes in this fixture | Does not establish all real field runs have complete support |
| Controlled omitted interior microzone | Thirteen initialized zero cells, one per state | Conditional converter weakness; omitted-node input is reviewer-created |
| Controlled two-element state vector | Two assignments, eleven zero placeholders | Regular native EnKF vectors have thirteen coordinates |
| Actual no-scene output, three evidence variants | No spatial state/sigma maps or L1 raster references | Plot posterior can retain supported information without fabricating spatial arrays |
| Mean-only output assembly routing | Scientific state/sigma maps empty; thirteen state debug surfaces retained | Routing was observed before an environment-blocked grid gate |
| Spatial output assembly routing | Thirteen state and thirteen uncertainty grids retained | Same assembly later encounters the environment limit below |
| Native runner serialization → `run_layer1_fusion_v1` → legacy FieldTensor → `adapt_l1` | 26 RasterRefs, 26 FieldTensor map keys, 26 underlying state/sigma grids represented by 52 case aliases | Supplied prior-only carrier; no full ASMAE inference or authorized map publication |
| Feature pack through actual L10 adapter | Thirteen `state` and `feature_status` entries retained | Fixture entries are prior-constrained with zero weight |

The actual chain is exercised using ordinary production functions. No replacement production functions, provider requests, jobs, physical dispatch, optimizer, or repository tests are used. All thirteen cases execute; all ten bounded observation checks pass. These numbers are authored probe counts rather than a repository test-suite total.

## Why the scalar mapping does not prove raster loss

`layer1_fusion/adapters/asmae_adapter.py:371–412` lists eleven state variables when producing plot-level EvidenceItems from raster means. It omits phenology progress and stress memory there. `layer1_fusion/raster_ingest.py:430` instead admits supplied raster dictionaries into RasterRefs. The actual fusion runner and FieldTensor bridge retain those references. The SIRE adapter iterates every supplied `raster_maps` member and every support-map member (`layer10_sire/adapters/l1_adapter.py:968–1001`), preserving native shape and rejecting a source specification that contradicts it (`:892–932`). It also carries the feature pack (`:805,1003–1022`).

Adding two scalar EvidenceItem names is therefore insufficient to solve independent map publication, and the scalar mapping should not be described as dropping those raster arrays. Dedicated SIRE products, state gates and frontend selection remain distinct downstream boundaries.

## Missing support versus legitimate zero

`layer05_asmae/engine.py:3255` initializes the converter's output with zero and fills the supplied microzones. The normal native fixture writes all rectangular nodes. Removing one interior microzone from that exact collection leaves thirteen zero placeholders without a corresponding converter-level missing-data mask. This confirms the narrow behavior behind the user's concern, while it does not show that a normal complete EnKF result routinely produces holes.

A repair should validate collection/vector completeness and represent unsupported cells with a validity mask/nodata, while preserving a qualified physical zero. It should also apply plot support explicitly; existence of rectangular graph nodes does not demonstrate observation support for every pixel.

## Mean-only and environment limits

The actual `_assemble_output` branch (`engine.py:1883–1908`) deliberately clears scientific raster outputs in mean-only mode. A trace of the unmodified method records that routing and the thirteen diagnostic debug grids. The equivalent spatial packaging trace retains thirteen mean and thirteen uncertainty grids.

Both assembly calls subsequently stop at a grid validation gate because the review runtime lacks Rasterio. The completion receipt records `environment_blocked`, including `crs_is_not_projected_metre`; this is not reported as a repository defect or a successful full output assembly. No dependency or grid predicate was substituted to bypass it. The independently completed native transport fixture tests a carrier boundary, not the blocked full engine.

The lower-level filter's sigma arrays are numerical ensemble uncertainty. Their existence does not establish empirical calibration, independent evidence, or a scientifically eligible layer for every coordinate. Descriptors, per-state support and the current execution's permissions must remain attached.

## Reproduce

```sh
python3 review-asmae13-90ab701/engine/probes.py
```

`results.json` records all fixtures, actual write traces, the two environment-blocked completion receipts and ten checks. `executed-source-manifest.json` binds imported production source to the pinned Git tree. All 52 FA milestones remain open; no real plot or end-to-end browser execution is claimed.


---

# Specialist appendix: SIRE generation, gates and classification

> Current-main replay: the cited production modules are byte-identical to the original specialist review. Focused execution was repeated against the current pinned source and dependencies. See current replay receipts.

# ASMAE 13-state SIRE publication review

Reviewed commit: **`90ab701714554c7b786bba4ac6b19259e77279ce`**, pinned exact Git blobs. This lane makes no production changes. **All 52 FA milestones remain open.**

**The 13-coordinate model is not a 13-map SIRE inventory.** SIRE registers and generates 11 ASMAE state surface types and 11 corresponding render modes; `phenology_progress` and `stress_memory` have neither. With valid native rasters, explicit indirect per-state support, all relevant evidence families and current-spatial visualization flags, actual generator calls produce all 11 surfaces and the exact runner authorization block permits diagnostic pixels for only **6 of 11**. Five registered states are unmapped in the state gate, including **`surface_wetness_event`**, which the four-item claim omitted. `CANOPY_WATER` consults **vigor**, not its own support.

**Per-state truthfulness is the larger repair priority.** A fresh native generator control shows that removing the per-state ledger, while retaining `real_asmae_evidence=true` and `source_reality=real_raster`, labels every generated state `directly_assimilated`, `Observed`, `direct_observation=true`. The same raster/metadata with an accepted indirect ledger stays `Indirectly-Constrained`; with a prior-only ledger it stays `Prior-Constrained`. This confirms an exposed missing-ledger fallback, not that the normal ASMAE engine routinely omits its ledger. A 13-row expert inventory should preserve those distinctions before adding two selectable map names.

## State-by-state matrix

This table uses the actual 13-state schema order. “Pixels” is the result of the exact production authorization block with all 13 accepted counts set to 1, indirect observation relationship, valid nonconstant native rasters, visualization permission, current spatial assimilation, evidence families, and BMA/retro support. `production_usable=false`, so permitted pixels have the **diagnostic_overlay** tier. Passing a gate does not establish physiological observability, calibration or prescription authority.

| Model coordinate | SIRE state surface / mode / manifest entry | Actual state-gate requirement | Diagnostic pixels in positive fixture |
|---|---|---|---|
| vigor | `ASMAE_VIGOR` | `vigor.accepted_update_count > 0` | Allowed |
| lai | `ASMAE_LAI` | **Unmapped** | Denied |
| chlorophyll | `ASMAE_CHLOROPHYLL` | `chlorophyll` count, nutrient family | Allowed |
| canopy_water | `ASMAE_CANOPY_WATER` | **`vigor` count**, water family | Allowed, wrong state lookup |
| root_zone_water | `ASMAE_ROOT_ZONE_WATER` | **Either** `canopy_water` or `root_zone_water` count, water family | Allowed |
| surface_wetness_event | `ASMAE_SURFACE_WETNESS_EVENT` | **Unmapped**; `WETNESS` selects water mode but does not match `WATER` state branch | Denied |
| structure | `ASMAE_STRUCTURE` | **Unmapped** | Denied |
| bare_soil_fraction | `ASMAE_BARE_SOIL` | **Unmapped** | Denied |
| salinity_stress | `ASMAE_SALINITY_STRESS` | `salinity_stress` count, salinity-specific family | Allowed |
| thermal_stress | `ASMAE_THERMAL_STRESS` | **Unmapped** | Denied |
| biotic_confounder_risk | `ASMAE_BIOTIC_CONFOUNDER_RISK` | Global production-BMA valid **and** real holdout count > 0; no own-state count check | Allowed |
| phenology_progress | **Absent** | Unregistered; string probe also unmapped | No generated surface or authorization entry |
| stress_memory | **Absent** | Unregistered; string probe also unmapped | No generated surface or authorization entry |

Source: `scientific_contracts/state_schema_ref.py:14–19`; `layer10_sire/schema.py:149–160,220–232,359–369`; `layer10_sire/products/manifest.py:34–44`; `layer10_sire/runner.py:5126–5157,5306–5326`. Every source path in this report is under `services/agribrain/` unless stated otherwise.

The fresh narrow mapping controls establish both directions of the canopy error: a ledger containing only accepted `canopy_water` denies `ASMAE_CANOPY_WATER` with `missing_state_support:vigor`; a ledger containing only accepted `vigor` permits it. Root-zone-water passes with only accepted canopy-water support. Surface wetness stays unmapped even with accepted surface-wetness support. Risk passes with an empty per-state ledger when global BMA/retro/family proof is present. These results are in `results.json → mapping_controls` and `per_state_matrix`; none requires live providers or posterior inference.

## Actual publication chain and lifecycle reasons

1. **Model/schema:** the scientific state schema has 13 coordinates. SIRE's `ASMAE_STATE_SURFACES` and `RenderMode` contain 11 of them. Existing generic `PHENOLOGY_ALIGNMENT` is a different surface; it is not an ASMAE phenology-progress registration.
2. **Native surface generation:** `generate_asmae_surfaces()` uses the rollout visual gate, checks ASMAE input presence, and iterates the 11 state plus diagnostic registries (`surfaces/asmae.py:565–655`). This is an ordinary imported production function in the probes. Both missing coordinates are supplied as input rasters, yet no surface is generated for them.
3. **Presence/geometry:** a state scalar is not broadcast into a physical grid. The generator emits all-None diagnostic placeholders (`:813–837`). Real raster arrays require proven source and display grid geometry (`:192–241,1135–1166`). Missing source or target grid specs produce typed alignment failures and omit the affected surfaces in this environment. The generator can also construct a geographic target from proven source geometry when its optional Rasterio path is available (`:613–645`); absence of an incoming target is not universally an invalid raster.
4. **Soft display versus pixels:** `asmae_surface_visual_eligible()` requires finite 2-D content (`:1277–1306`); `asmae_surface_pixel_visual_eligible()` additionally rejects UNIFORM/BROADCAST, degraded/no-scene/mean-only states and missing spatial/grid proof (`:1309–1375`). This gate intentionally does not require operator lock, EnKF credit or radiometric authority.
5. **Exact policy authorization:** runner `:4989–5542` computes current lifecycle, family and state gates, then policy/role entries. The ASMAE surface gate first requires current spatial assimilation, spatial raster availability and incoming visualization permission (`:5159–5180`), then native pixel eligibility, family evidence and the substring state mapping. With production proof it can authorize `full_raster`; otherwise supported surfaces can receive a labeled `diagnostic_overlay` (`:5371–5420,5465–5502`).
6. **Manifest and terminal envelope:** the native manifest builder enables modes from surface presence (`products/manifest.py:246–304`), independently of later pixel authorization. The native terminal builder publishes an authoritative empty degraded envelope when geography/materialization is unavailable (`terminal_publication.py:26–153`). `classify_surface_publication()` verifies the publication envelope, identity/schema/proof/display facts; it is not a test of all 13 state maps (`surface_contract.py:182–331`).

| Fresh lifecycle/geometry control | Actual relevant result |
|---|---|
| `state="model_estimated"` plus current-spatial/raster/visualization flags and accepted support, production false | Supported mapped states receive `diagnostic_overlay` |
| Same valid rasters, production true, real evidence/source reality and aggregate proof positive | Supported mapped states receive base `full_raster`; overlay remains diagnostic role |
| Model-estimated without current spatial assimilation | `missing_current_spatial_assimilation` |
| Raster availability false | `missing_spatial_raster` |
| Incoming visualization permission false | `diagnostic_visualization_denied` |
| Explicit uniform native raster | `grounding_class_non_spatial` for pixels |
| State scalar placeholder | Soft gate `no_finite_values`; final authorization is denied/card-only for its missing surface grid |
| Invalid pipeline grid | `invalid_geospatial_grid:missing_grid_spec` |
| Accepted counts all zero | Vigor/canopy-water denied; root water denied; risk may still pass from global BMA/retro proof |
| Risk BMA/retro/family support absent | Denied at `missing_risk_evidence_family` before state-specific risk reason |
| Water evidence family absent | `missing_water_evidence_family` |
| Rollout rendering explicitly disabled or no ASMAE inputs | Native generator returns no surfaces |

`model_estimated` is therefore not an unconditional permission or prohibition. The positive diagnostic fixture deliberately supplies the current-spatial flags; it does **not** establish that every actual model-estimated engine output supplies them. Current-spatial failure is checked before state support. `scientific_surface_allowed=false` and `production_usable=false` do not by themselves forbid a diagnostic overlay; that separation is explicit in the production gate.

A constant map is **not automatically invalid**. The native generator classifies constant values as UNIFORM and records `scope="plot_level"`, `constant_allowed=true` (`surfaces/asmae.py:1247–1259`). Uniform finite grids pass the soft visual gate and may support honest plot-level information, while ASMAE pixel authorization denies placement. The tested uniform surfaces still appear as enabled entries in the presence-based native manifest. Neither an enabled mode nor a valid publication envelope proves authorized pixels.

## Confirmed missing-ledger quality-label fallback

The actual native generator was called three times with the same 11 nonconstant aligned real-raster fixtures and diagnostic/state-update-denied metadata:

| Per-state proof supplied to native generator | Generated `support_class` | Generated evidence label | Generated `direct_observation` |
|---|---|---|---|
| Accepted count 1, indirect relationship, DIAGNOSTIC ceiling | `indirectly_constrained` | Indirectly-Constrained | false |
| Prior-only count 0 | `prior_constrained` | Prior-Constrained | false |
| Ledger missing | **`directly_assimilated`** | **Observed** | **true** |

This occurs for all 11 state surfaces, including salinity and biotic risk. The native fallback at `surfaces/asmae.py:482–518` uses `real_ev && source_reality == "real_raster"` when no per-state support classification resolves. It confuses the reality of the upstream raster with the observational status of each modeled physiological coordinate. It also marks those missing-ledger surfaces eligible for management zones/statistics in the returned classification (`:520–527`). In the tested generator outputs, provenance `diagnostic_only=true` and `state_update_allowed=false` remain; no physical update or prescription was performed. The result is a confirmed misleading metadata fallback at an accepted native SIRE boundary, not a demonstrated action-authority escalation.

The ordinary full ASMAE engine path builds `state_support_ledger` (`layer05_asmae/engine.py:2865–2867`), exports the feature pack (`:2985`), binds the ledger into proof (`:3037`) and returns the pack (`:3251`). The exporter carries its ledger at `feature_export.py:196,557`. `l1_adapter.py:805,1003–1022` carries/enriches the pack; it does not manufacture a missing per-state ledger. Thus the fresh missing-ledger test is a boundary/migration risk; this lane does not claim that normal freshly generated engine outputs usually omit proof. Legacy/imported/direct raster inputs and exact provenance need to remain fail-closed at SIRE itself.

No spatial variance should be fabricated to evade a uniform classification. The proposed expert inventory should show **13 stable rows even when no pixels exist**, with separate columns for state lifecycle, per-state support class, observation relationship, accepted updates, confidence/uncertainty availability, information/effective resolution, surface presence, diagnostic display permission, scientific/training/prescription authority and precise block reason. For salinity/biotic and other weakly identifiable coordinates, preserve hypothesis/proxy/indirect labels from per-state proof; do not convert “real satellite raster” into “Observed state.” The two missing types should initially be added at their justified diagnostic/card tier rather than promoted by registration alone. This is a review recommendation, not an implemented feature or an assertion of empirical calibration.

## Fresh proof, exactness and limits

`probes.py` is self-contained against the sibling `source` snapshot. It executes ordinary production imports/calls for schema, generator, the three eligibility gates, manifest, support classification, terminal publication and publication classification. The real visual-shadow rollout policy is enabled with in-process flags; no rollout registry is edited and no `ASMAE_TEST_OVERRIDE` is used.

The runner is deliberately **not imported or run in full** because it integrates providers, rendering jobs and additional layers. Its exact top-level grid helpers and exact authorization-construction statements `runner.py:4989–5542` are compiled directly from the pinned AST, with no branch/body/predicate edits and no production-function substitutes. Synthetic fixtures supply the surrounding output and proof. This is explicitly **AST-isolated production authorization execution**, not a full end-to-end provider/job validation. Source spans and AST hashes are recorded in `source-receipts.json`.

Fresh results include 13 matrix states, 10 targeted mapping controls, 11 lifecycle authorization fixtures, 5 native generator geometry/content cases, rollout/no-input negatives, 3 native generator per-state-label controls and 5 native terminal/publication contract cases. Native generator geometry positives produce exactly 11 surfaces. The terminal native result is `VALID_DEGRADED`, with empty surface inventory; missing render authorization, missing proof, run identity mismatch and wrong schema fail closed with named reasons.

Every staged source file matched its pinned Git blob before and after execution: **1086 files** at this completed snapshot, including additions fetched by the parent reviewer. The harness natively imported **43 repository files**, each bound by Git blob, SHA-256, byte count and module name. The runner AST source is separately bound. Strict JSON contains no NaN/Infinity tokens. Only this lane is written; sockets fail closed. No repository test/audit/claim is correctness evidence; no provider, LLM, hardware, ASMAE inference/optimizer, job, cache publication, training, prescribing or execution is invoked.

Reproduce:

```bash
python review-asmae13-90ab701/sire/probes.py
```

Deliverables: `probes.py`, `results.json`, `source-receipts.json`, and this report. These results confirm inventory/mapping/quality-label boundaries, not whole-project completion, all state physiological accuracy, live map availability for a particular plot, or any FA milestone closure.


---

# Specialist appendix: API, inventory and actual frontend selection

> Current-main replay: the cited production modules are byte-identical to the original specialist review. Focused execution was repeated against the current pinned source and dependencies. See current replay receipts.

# ASMAE 13-layer frontend/API review at 5344930

Reviewed revision: `90ab701714554c7b786bba4ac6b19259e77279ce`. The reviewed production files match that exact untruncated Git tree; 28 file identities are freshly checked in `source-receipts.json`. This report uses production source and offline executions of the actual pure TypeScript selection helper. It does not use repository tests/audits as correctness proof and does not claim a live plot has any particular state raster.

## Verdict on the presentation claim

The concern about **independent state inspection is supported**, but a count of nine `MapMode` members is not the reason. The hook has nine compatibility strings, including a `vegetation` alias for `canopy`. The actual control architecture has **six base modes and nine independent overlay toggles**. Confidence and resolution compatibility selections turn on overlays while keeping the current base. A map can therefore show more than one surface at once. Hybrid canopy also has independently authorized vigor, posterior-concentration and disagreement overlays. None of that creates thirteen independently selectable state products.

The reachable Layers panel uses a fixed list of six base radio choices and nine overlay checkboxes. Existing policies select a preferred surface from a fixed per-lens priority list. There is no generic surface-ID/state selector in this path. A valid LAI surface can be carried in the payload and in the backend manifest without becoming a candidate for any existing frontend lens. Canopy water and root-zone water share the same water lens: when both are authorized, canopy water wins and root-zone water is a fallback. That is a concrete limitation for independent scientific inspection.

**An expert interface already exists.** It shows engine data, active-surface statistics, ASMAE mode statuses, rejection and authority-block reasons. It does not expose all thirteen named products as individual map selections. The useful change is an expert state catalog and selector within that interface, while retaining the existing farmer-facing lenses.

## Actual UI → selection → render chain

| Boundary | Actual production behavior | Exact source |
| --- | --- | --- |
| Mounted map | `PlotDashboard` supplies `l10.activeSurface`, current mode, confidence/reliability surfaces and `detailMode` to `PlotMapShell` | `src/components/farm/PlotDashboard.tsx:298–324` |
| Mounted controls | Dashboard mounts `RawDataSidebar`; its Layers tab mounts `MapLayerDock` | `PlotDashboard.tsx:351`; `src/components/farm/intelligence/RawDataSidebar.tsx:189–204,403–405` |
| Layer panel | Six base radio choices; nine overlay checkboxes; source policy radios shown under selected canopy | `src/components/farm/intelligence/MapLayerDock.tsx:64–85,131–177,190–203,323–360` |
| Hook state | Six `BaseSurfaceMode` values; nine `OverlayKind` values; confidence/resolution compatibility modes enable overlays | `src/lib/agribrain/plot-map-evidence-state.ts:159–208`; `src/hooks/useLayer10.ts:993–1053` |
| Candidate resolution | Actual display uses `resolveSourcePolicyDisplay` with the full surfaces array, policy, proof and render authorizations | `useLayer10.ts:1735–1762` |
| Priority selection | Fixed candidate lists per lens; first finite authorized candidate with an allowed render kind wins; a denied earlier candidate does not hide an authorized fallback | `src/lib/agribrain/source-policy-display-resolver.ts:221–282,311–433,485–521` |
| Overlay lookup | Renderer receives all surfaces by type, rather than a nine-item whitelist | `src/components/farm/map/PlotMapShell.tsx:431–441,450–487` |
| Multiple hybrid layers | Hybrid canopy can add vigor, posterior concentration and disagreement, each independently authorized and materialized | `src/components/farm/map/buildLayerStack.ts:710–796` |
| Actual raster mechanism | Values become a browser canvas image; authorized image becomes a DeckGL `BitmapLayer`, clipped to the plot | `src/components/farm/map/layers/SemanticSurfaceLayer.ts:129–134,567–623,649–665` |
| Rendered claim | `DeckGL.onAfterRender` creates publication-bound committed-layer receipts; hook withholds committed surface/histogram claims until materialized | `PlotMapShell.tsx:824–889`; `useLayer10.ts:1853–1884` |

`MODE_SURFACE_MAP` in `useLayer10.ts:439–449` and the evidence resolver at `plot-map-evidence-state.ts:497–514` are broad compatibility mappings, not a complete layer register. The latter can read a backend `mode_surface_plan` selected type, but actual display selection is still policy/proof/authorization aware. `MapModeSwitcher.tsx` defines eight old-style buttons; the reviewed mounted dashboard path does not import it. `ModeLens.tsx` also defines six base choices and nine overlays, but is not mounted by the reviewed dashboard/intelligence components. The mounted `MapLayerDock` supplies the direct control evidence above.

## Conditional access to the thirteen named products

This is a **presentation-access matrix**, not a claim that the underlying model generated or qualified these products for a live plot. The Layer 10 schema classifies eleven listed items as `ASMAE_STATE_SURFACES` and effective resolution/posterior concentration as diagnostic surfaces (`schema.py:220–245`). That grouping does not establish the dimensionality of the upstream scientific model.

| Raw Layer 10 product | Existing browser route when a qualified corresponding surface exists | Independent state selector in current path |
| --- | --- | --- |
| `ASMAE_VIGOR` | `CANOPY_ASMAE_VIGOR` in canopy; raw vigor is also a late vegetation-attention candidate | No; chosen by lens/policy priority |
| `ASMAE_LAI` | No current lens priority or overlay kind names LAI | No |
| `ASMAE_CHLOROPHYLL` | `NUTRIENT_ASMAE_CHLOROPHYLL_PROXY` in nutrients | No; presented as a qualified diagnostic nutrient proxy |
| `ASMAE_CANOPY_WATER` | `WATER_ASMAE_CANOPY_WATER`, first ASMAE candidate for water | No |
| `ASMAE_ROOT_ZONE_WATER` | `WATER_ASMAE_ROOT_ZONE_WATER`, later water fallback | No; cannot choose it instead of an authorized higher-priority canopy-water item |
| `ASMAE_SURFACE_WETNESS_EVENT` | No current lens priority or overlay kind names it | No |
| `ASMAE_STRUCTURE` | No current lens priority or overlay kind names it | No |
| `ASMAE_BARE_SOIL` | No current lens priority or overlay kind names it | No |
| `ASMAE_SALINITY_STRESS` | `SALINITY_ASMAE_STRESS` in salinity | No; chosen by lens/policy priority |
| `ASMAE_THERMAL_STRESS` | No current lens priority or overlay kind names it | No; the visual “thermal” palette is not a thermal-state selector |
| `ASMAE_BIOTIC_CONFOUNDER_RISK` | No current lens priority or overlay kind names it | No; broad composite risk is a different product |
| `ASMAE_EFFECTIVE_RESOLUTION` | `RESOLUTION_ASMAE_EFFECTIVE` through resolution overlay | No; selected resolution representative |
| `ASMAE_POSTERIOR_CONCENTRATION` | Confidence overlay; also an independently authorized hybrid canopy overlay | No generic state selector, but this named diagnostic can be displayed |

The corresponding alias definitions are explicit at `surfaces/asmae.py:1478–1532`; chlorophyll's alias warns that it is not confirmed nutrient stress and may be confounded by water, salinity, biotic stress and crop stage. The frontend priorities are `source-policy-display-resolver.ts:311–433`. Absence from those candidate lists is a presentation limitation; it does not prove the numeric product is absent from the upstream payload. Alias creation and backend qualification can separately prevent an otherwise named route from being available.

## Availability inventory and reasons

There are useful existing reasons and permission distinctions:

- `getRenderAuthorization` denies by default with `missing_render_authorization` when there is no policy/mode/role/surface authorization (`source-policy-display-resolver.ts:166–189`). The selector reports the blocked candidate and fallback reason (`221–282`). Finite data alone does not grant map permission.
- Mode availability carries ASMAE status, rejection reason, selected ASMAE surface, core status and authority-block reason (`plot-map-evidence-state.ts:861–974`). The current expert sidebar displays those fields for eight broad modes and the active mode (`SidebarExpertView.tsx:371–441`).
- The Layers panel shows current source and ASMAE utilization details/reasons (`MapLayerDock.tsx:365–467`). It sometimes replaces a specific unavailable-overlay reason with the generic text “Experimental unavailable” (`323–355`).
- A card-only ASMAE plot state remains available separately from map materialization, and distinguishes directly/proxy assimilated, indirectly constrained and prior-only states (`RawDataSidebar.tsx:209–278`). Thus “not rendered” cannot be equated with “no ASMAE state.”

The inventory is incomplete for the thirteen raw names. Backend `runner.py:3799–3936` iterates a **hardcoded 43-type** `ALL_BACKEND_KNOWN_SURFACES` list. Frontend `plot-map-evidence-state.ts:1165–1175,1181–1307` builds local rows for **22 hardcoded types**; the hook merges backend rows at `useLayer10.ts:2223–2242`. Among the thirteen raw names, only `ASMAE_POSTERIOR_CONCENTRATION` is directly enumerated in both inventories. Selected aliases are enumerated, but LAI, structure, bare soil, wetness event, thermal stress and biotic confounder risk have no direct expected/generated/missing inventory row there. The backend manifest may still name their actual generated surfaces. `selection-matrix.json` records exact membership for all thirteen.

This makes a full thirteen-state audit difficult: existing mode-level reasons cannot replace a per-state record explaining whether a product was generated, spatially valid, only a prior, rejected, unavailable, authorized for scouting or blocked for another action. The review does not infer what any missing row's true scientific status is.

## API and bridge: where information survives and where it is gated

The live browser path is canonical-publication based:

1. Hook first POSTs to `/api/agribrain/surfaces/latest`; on a miss it triggers `/api/agribrain/run` with `mode: 'surfaces'`, then polls `/surfaces/latest`. It accepts scientific data only from a fresh validated canonical publication head (`useLayer10.ts:1111–1146,1160–1244`).
2. Next `/run` signs and proxies to Python `/v2/run` with `source_policy: 'canonical'` (`src/app/api/agribrain/run/route.ts:463–506`). Its successful surfaces response is a publication-pending/job acknowledgment, not the scientific raster payload (`152–173`). Source policies select views of one inventory instead of defining a separate scientific request (`177–206`).
3. Python `/v2/run` calls `orchestrator_v2.run_entrypoint.run_surfaces_mode`; surfaces-mode authority validation requires render authorizations, proof, mode display state and source-policy display state (`services/agribrain/app/main.py:3870–3883,3921–4034`).
4. `_serialize_l10_output` and surfaces-mode enrichment retain surfaces, raster/vector packs, tile manifest, inventory, mode plan, mode display state, ASMAE evidence/feature information, proof and render authorizations (`services/agribrain/orchestrator_v2/run_entrypoint.py:802–851,947–995`).
5. Next `/surfaces/latest` requests the signed Python `/v2/plots/{plotId}/snapshot`; integrity failure returns 409, stale contracts return unavailable/refresh-required, valid heads spread the frontend payload, and missing heads return worker status rather than a scientific fallback (`src/app/api/agribrain/surfaces/latest/route.ts:48–124,129–176`).
6. The hook normalizes **every returned surface**, retains the inventory/policy/proof/authorization fields, and builds a full by-type map (`useLayer10.ts:579–623,1248–1250,1288–1290,1331–1347,1419–1425`). Presentation selection then restricts what the current lens shows. Grids and metadata surviving transport do not mean every state is selectable or rendered.

The standalone `l10_frontend_bridge.py` similarly serializes the full surface pack and inventory/mode/proof/authorization fields (`187–191,374–417`). However, its `build_input_from_context` constructs an 8×8 synthetic field tensor (`44–64`), and the reviewed live Next API route calls the orchestrator service rather than this standalone script. It should not be used as evidence that a live plot's thirteen maps exist or that the browser consumes its synthetic output.

## Backend manifests and GIS export claim

The backend is richer than the frontend selector. `products/manifest.py:32–50` maps the thirteen raw names to distinct ASMAE `RenderMode` values. `build_render_manifest` creates mode definitions with surface IDs and enables them if corresponding products exist (`247–300`). Disabled entries are also emitted when no corresponding data exists. That metadata is conditional product description, not proof of a created raster or a browser selector.

The inspected export helpers produce **serializable arrays and metadata**:

| Helper | Actual return content | What it does not establish |
| --- | --- | --- |
| `export_raster_pack` | `RasterEntry` per surface with nested `values`, `grid_ref`, units, resolution, render range, palette and summary stats | A written GeoTIFF/COG file, storage URL, overview pyramid or downloadable GIS artifact |
| `export_tile_manifest` | Grid dimensions/resolution, layer names, mode metadata, style and quality | A served tile pyramid or COG service |
| `export_full_product` | JSON-safe raster entries, vector entries and tile manifest | A real file-format export job |
| Browser semantic layer | Canvas image from values, then DeckGL `BitmapLayer` | COG-native browser loading |

Exact export sources: `products/export.py:19–32,46–56,59–97,140–170,176–203`; actual browser source: `SemanticSurfaceLayer.ts:129–134,600–623,649–665`. The hook retains `raster_pack` and `tile_manifest`, but the traced map/selector path uses `surfaces` and policy/authorization resolvers; it does not turn backend `available_modes` into state controls. This supports the narrow claim that **these particular manifest/export functions are not COG production**, without claiming no other subsystem in the repository can ever write GIS rasters.

## Offline counterexamples and limits

`probe_selection.mjs` imports the exact production `source-policy-display-resolver.ts` using Node 24's TypeScript stripping. It runs the real `getPriorityList`, `normalizeMode` and `resolveAuthorizedSurfaceForMode` against reviewer-created finite grids and explicit authorization fixtures. It does not run React, a browser, DeckGL, providers, ASMAE inference or a render job.

All six probe checks passed:

| Counterexample/control | Actual helper result |
| --- | --- |
| Both water aliases exist and are authorized | Canopy-water is selected; root-zone water is not independently selected |
| Canopy-water is denied, root-zone water authorized | Root-zone water is selected as fallback with the denied reason retained |
| Only root-zone-water exists and is authorized | Root-zone water can be selected through the water lens; it is not categorically hidden |
| Finite water arrays but no render authorizations | No surface is selected; `missing_render_authorization` |
| LAI included with the thirteen raw names and authorization fixtures | LAI is absent from every existing lens priority list |
| Satellite policy priorities | No ASMAE product is a priority |

A further receipt runs all eight lens priority lists with all thirteen raw products, then with the six current state aliases added. Raw-only fixtures select only raw vigor in vegetation attention and posterior concentration in confidence; adding aliases exposes their mapped representatives, but still does not create LAI/structure/etc. selectors. These are controlled selection counterexamples, not scientific generation/availability receipts. Missing aliases, production authorization, per-cell support, geometry and materialization may impose additional restrictions not measured by these helper cases.

## Focused product changes supported by the review

1. Extend the existing expert view with an authoritative thirteen-product catalog and explicit state/surface selection. Keep the six farmer-facing lenses and compound overlays.
2. Add individual expected/generated/missing entries, provenance, observation/prior class, uncertainty/support and rejection/authority reasons for every catalog item. Derive inventory from the same catalog rather than separate hardcoded lists.
3. Let an expert deliberately choose canopy water versus root-zone water and see exact units/meaning. Keep the fallback chain for the broad Water lens.
4. Keep render visibility, pixel sampling, scientific interpretation and prescription permission separate. A new selector must not bypass current authority/materialization gates.
5. If GIS delivery is required, define actual per-state GeoTIFF/COG artifacts and an export endpoint with CRS/affine/nodata/provenance/validation receipts; the existing JSON pack is not that delivery contract.

These are review recommendations, not implemented changes or claims of full acceptance. The parent review retains all 52 FA milestones open.

## Reproduction and authored artifacts

From `review-asmae13-90ab701/` with the supplied source/tree layout:

```sh
node frontend/probe_selection.mjs
PYTHONDONTWRITEBYTECODE=1 python frontend/verify_sources.py
```

`selection-results.json` preserves priorities, fixture results, execution boundary and checks. `selection-matrix.json` preserves all thirteen inventory/priority memberships. `source-receipts.json` verifies 28 exact production blobs and SHA-256 identities. Console captures preserve both fresh runs. `authored-manifest.json` pins this report, both scripts and JSON receipts. No production source or Git was edited; no external browser/session, service, hardware, render job or durable scientific execution ran.


---

# Specialist appendix: Cache, serialization and scientific artifacts

> Current-main replay: the cited production modules are byte-identical to the original specialist review. Focused execution was repeated against the current pinned source and dependencies. See current replay receipts.

# Export and persistence lane — ASMAE thirteen-state maps

Candidate: `90ab701714554c7b786bba4ac6b19259e77279ce`, the current main identity supplied by the coordinating review. This lane examines exact production cache/export code. Repository tests and audit reports were not used as correctness evidence.

**Finding:** the inspected ASMAE/SIRE publication route does not implement a complete thirteen-state georeferenced GeoTIFF/COG delivery workflow. However, NPZ persistence is not the eleven-state bottleneck, and the canonical frontend surface envelope already carries substantially more scientific/geographic metadata than the compatibility raster pack.

## What fresh execution established

The authored `probes.py` ran actual production ASMAE cache and SIRE serialization functions in a temporary private directory. All **16 component checks pass**. These arrays are authored serializer fixtures, not output from a field execution or proof of scientific publication eligibility.

| Component | Exercised result | Meaning |
|---|---|---|
| `serialize_and_cache_asmae` → `deserialize_cached_asmae` | All 13 state names survive in each of `raster_maps`, `uncertainty_maps`, and `confidence_maps` | 39 arrays persist; there is no eleven-state cache whitelist |
| Current-schema NPZ manifest | Binds all 39 arrays | Shape, dtype, content hash, file size, and checksum are part of the validated transaction |
| Zero and precision controls | `0.0`, `0.123456789`, and `0.987654321` return exactly in the fixture | Valid zero is preserved; no downsampling or four-decimal pixel rounding occurs in this ASMAE path |
| Missing-cell controls | Explicit `None` and numeric NaN return as `None` | Missing cells are not converted into physical zero by this cache reader |
| Grid metadata | CRS, transform, dimensions, bounds, and resolution survive in the payload | NPZ array data can remain associated with a JSON geographic envelope; NPZ is not inherently georeferenced on its own |
| Current fixture with commit marker removed | Reader returns a clean cache miss | Old/uncommitted entries are intentionally rejected, not selectively reduced to eleven states |
| SIRE `export_raster_pack` | All 11 registered ASMAE state surface types export | The exporter iterates supplied surfaces without a second state whitelist |
| Pixel vs. statistics control | Exact pixel `0.987654321` remains, summary maximum becomes `0.9877` | Four-decimal rounding applies to statistics, not this raster entry's pixel grid |
| Canonical `serialize_surface_artifact` | Preserves grid specs, masks, confidence, uncertainty and pixel values | The real canonical surface envelope is richer than `RasterEntry` |
| Unassigned GIS refs | `cog_ref`, `tile_ref`, and `stac_item_ref` remain `None` | A schema slot is not a generated geospatial artifact |

The run verified **1,086 staged files** against their Git blobs before execution and unchanged bytes afterwards; twenty imported source-module identities are recorded. This count describes the source snapshot available at that instant, not executed line or branch coverage. The parent coordinator may stage further exact files for other lanes.

## ASMAE cache has capacity for all thirteen states

`layer05_asmae/cache.py:98–101` lists raster *field categories*, not state names. At lines 684–690, every member of each supplied raster dictionary becomes an NPZ member named `field__variable`. `save_rasters_artifact` at lines 503–543 accepts numeric two-dimensional arrays and writes their dtype without selecting or reducing state names.

The manifest and loader at lines 546–621 validate member sets, shapes, dtypes, per-array hashes, and whole-file identity. Lines 788–801 restore each validated member into its declared raster field. The actual thirteen-state fixture exercises this machinery through the public cache writer/reader, rather than calling only an array helper.

Therefore, adding two publication definitions does not require replacing the existing ASMAE NPZ format just to retain those state arrays. Cache eligibility can still reject a failed/rejected spatial result (`643–678`, `725–776`), or reject an old schema, corrupt artifact, or broken manifest. Those are whole-entry eligibility/integrity decisions; none proves the user's particular plot has a cache failure.

The input fixture uses an authored completed status solely to exercise serialization. It does not establish that a real run may authorize or display any of these thirteen arrays. A cache hit preserves producer metadata; it does not itself create observational support.

## SIRE exposes two distinct export contracts

The lightweight `layer10_sire/products/export.py:18–31` `RasterEntry` contains identity/type, grid reference, units, native resolution, display range/palette, source layers, values, and statistics. It does **not** contain a full CRS/affine grid specification, observed/inferred masks, confidence, uncertainty, or COG reference. `export_full_product` (`176–199`) wraps this compatibility projection with vector and tile manifests; it does not create a TIFF file.

That omission should not be generalized to all frontend publication. The canonical `layer10_sire/surface_contract.py:101–180` serializer preserves:

- `grid_spec`, `source_grid_spec`, and `display_grid_spec`;
- observed and inferred masks;
- native, effective, and display resolution;
- confidence, uncertainty, provenance, authority restrictions and diagnostic status;
- COG, tile, and STAC references when provided by a producer.

The canonical frontend bridge actually calls that serializer for each surface (`l10_frontend_bridge.py:187–191`), while also passing the separate compatibility `raster_pack` through (`388`). Thus the user is right to distinguish arrays from downloadable geospatial files, but it would be inaccurate to conclude that the frontend envelope universally lacks georeferencing or uncertainty.

`export_raster_pack` preserves every supplied pixel, including valid zero and nodata; only quick statistics are rounded (`58–94`). It does not downsample. Separately, SIRE's cache writer casts surface values/confidence to **float32** (`runner.py:1413–1429`), and the loader restores nodata as `None` and rebinds the compatibility pack by surface ID (`1542–1584`). This storage precision choice is distinct from the direct export's pixel precision and is not established as a cause of missing state layers.

SIRE serialization/export remains conditional on spatial rendering, and export exceptions are currently nonfatal (`runner.py:3591–3600`). Cache reload can also return a miss for disabled ASMAE rendering, absent artifacts, or inconsistent surface/member counts (`1495–1604`). These are source-level runtime possibilities; no current production logs were examined here.

## GeoTIFF/COG qualification

`SurfaceArtifact` already declares `grid_spec`, `source_grid_spec`, `display_grid_spec`, `raster_ref`, `cog_ref`, `tile_ref`, and `stac_item_ref` (`schema.py:499–507`). Those are useful extension points, not proof of a writer/upload/tile-serving pipeline. The inspected complete Layer 10 production tree has no per-state GeoTIFF/COG writer or assignment pipeline populating the COG references for all ASMAE latent states.

There **is** a generic georeferenced TIFF writer elsewhere: `layer1_fusion/raster_backend.py:227–274`, `RasterioBackend.write_raster`, writes `driver='GTiff'` using CRS and transform. Consequently, “AgriWise contains no GeoTIFF support” would be false. The narrower verified statement is that this generic L1 writer is not hooked up as a complete ASMAE/SIRE thirteen-state scientific artifact publisher in the inspected route.

This lane did not execute a generic TIFF writer, full SIRE pipeline, HTTP download endpoint, browser, provider request, tile service, optimizer, or physical hardware. It does not claim that no unrelated export infrastructure exists outside the inspected route.

## Implementation implications

1. Preserve the current validated NPZ transaction for internal scientific persistence; do not treat it as the eleven-state registry defect.
2. Complete state identity and availability inventory upstream of file formats. An unavailable state must retain an explicit reason instead of receiving fabricated pixels.
3. If GeoTIFF/COG is an agreed target, add a dedicated scientific artifact product that binds each eligible state mean, uncertainty, nodata/support mask, units, time, exact geographic grid, resolution and provenance. Populate artifact references only after the files are successfully committed and verified.
4. Keep browser compatibility arrays and scientific downloads as separate documented projections of the same immutable state identity. A preview resampling or float32 cache must not silently redefine the canonical scientific field.
5. Verify cold reload and consumer parity at each actual contract. Direct serializer fixtures establish capacity and projection behavior; they do not prove estimator correctness, rendering authorization, or field-level geospatial accuracy.

All 52 FA milestones remain open. This export review establishes bounded code behavior and a product gap; it does not authorize full ASMAE/SIRE acceptance.

## Reproduce

From the coordinated review workspace with the exact pinned source staged:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 review-asmae13-90ab701/export/probes.py
```

Outputs are strict `results.json` and `source-import-manifest.json`. The temporary cache files are removed after the run. The deliberate uncommitted-cache miss emits a rejection log by design; it is a passing fail-closed control.


---

# Specialist appendix: Plan and R3 scientific requirements

# ASMAE 13-state map review — normative and epistemic mapping

**The 13-coordinate state vector is a reasonable declared model structure. It does not establish 13 independently observed, calibrated or publishable maps.** The governing correction is per-variable scientific support and truthful projection, not unconditional map completion.

Source pin: `90ab701714554c7b786bba4ac6b19259e77279ce`. This lane reads exact production source and the three tracked normative plans; their bytes are checked against that commit tree. R3 is the supplied master monograph and its full text. This is discovery before implementation: no production changes, production imports, services, model training or hardware. Repository tests, audit claims and previously generated review reports are not correctness evidence. All 52 package full-acceptance milestones remain open.

## What the plans actually require

| Requirement | Required result | Exact references |
|---|---|---|
| Per-variable state support | Correct dynamics/observation operator, matched native support, covariance and observability; scene evaluated at its acquisition state; no independent evidence invented by interpolation. | R3 full text:8898–8943,10166–10200; AB-ASM-001…008 |
| Distribution and calibrated uncertainty | Support and uncertainty by variable; primary evidence, exclusions, dependence, domain, held-out forecasting and prospective/hindcast distinctions preserved. A local pass never certifies all states. | R3:8946–8996,10202–10241; AB-ASM-009…016 |
| SIRE publication | Same canonical value/mask/geometry/resolution/authority through serialization, cache and rendering; unsupported pixels transparent; no inspector without pixel authority. | R3:2379–2428,10591–10593; AB-L10-001 |
| Time-dependent maps | Observation time and availability time, archived issuance cutoff and forecast/reconstruction role survive the chain. | Master:179–204; R3:8973–8989; F02 |
| Farmer and expert explanation | A novice view may simplify language; expert view may expose covariance/support. Neither changes certainty, values, permissions or source. | R3:9482–9486,9557–9568; AB-L9-010 |
| Raster formats | FieldCube may use qualified geospatial arrays or COG/Zarr; raster storage design explicitly names COG/Zarr. | R3:3739–3758 |

R3 distinguishes actual sensor measurements from reconstructed ASMAE states (R3:1158–1179), and explicitly states spectral LAI/chlorophyll are reconstructed, not direct measurements (2041–2044). SAR does not directly observe root-zone moisture without local calibration and a valid observation model (4083–4084). An inferred 1 m mesh remains inferred, even with certification (1822–1858). These are scientific requirements, not labels that a frontend can choose.

## All 13 declared states

The table below reports descriptor declarations, not a current-run certificate. The descriptor file freezes 13 names and order (128–145); config agrees (59–75). No exact thirteen-variable list was found as an R3 normative mandate: R3 requires variable/support qualification and may accommodate evolving models. Registered update targets only declare permitted software mappings; they do not prove the channel identifies the named physical quantity.

| State | Descriptor identifiability / maximum ceiling | Scientific interpretation | Dedicated SIRE product |
|---|---|---|---|
| `vigor` | `indirectly_constrained` / `prescription_eligible` | Indirect observation-constrained canopy reconstruction; no direct photosynthesis measurement is established. | `ASMAE_VIGOR` |
| `lai` | `partially_identified` / `diagnostic` | Partially identified reconstruction; saturation and crop-model/domain dependence remain relevant. | `ASMAE_LAI` |
| `chlorophyll` | `partially_identified` / `diagnostic` | Partially identified spectral reconstruction; not direct leaf chemical measurement. | `ASMAE_CHLOROPHYLL` |
| `canopy_water` | `indirectly_constrained` / `diagnostic` | Indirect optical/process constraint on canopy water; not a root-zone observation. | `ASMAE_CANOPY_WATER` |
| `root_zone_water` | `indirectly_constrained` / `diagnostic` | Indirect process estimate requiring depth-aware hydraulic/forcing support; surface SAR alone is insufficient. | `ASMAE_ROOT_ZONE_WATER` |
| `surface_wetness_event` | `indirectly_constrained` / `diagnostic` | Indirect transient event indicator; not measured soil-water storage or irrigation delivery. | `ASMAE_SURFACE_WETNESS_EVENT` |
| `structure` | `indirectly_constrained` / `diagnostic` | Latent, spatially reconstructed canopy structure constrained by SAR; not direct biomass measurement. | `ASMAE_STRUCTURE` |
| `bare_soil_fraction` | `indirectly_constrained` / `prescription_eligible` | Observation-derived proxy reconstruction; descriptor does not declare direct identification. | `ASMAE_BARE_SOIL` |
| `salinity_stress` | `hypothesis_only` / `monitoring_only` | Diagnostic hypothesis; independent EC/local evidence is needed before a stronger interpretation. | `ASMAE_SALINITY_STRESS` |
| `thermal_stress` | `indirectly_constrained` / `diagnostic` | Diagnostic hypothesis with indirect weather constraint; not direct canopy-temperature measurement. | `ASMAE_THERMAL_STRESS` |
| `biotic_confounder_risk` | `hypothesis_only` / `monitoring_only` | Diagnostic risk hypothesis; not confirmed pest/disease presence. | `ASMAE_BIOTIC_CONFOUNDER_RISK` |
| `phenology_progress` | `partially_identified` / `diagnostic` | Process-model/seasonal reconstruction, partially identified; external stage evidence may constrain it. | No dedicated entry |
| `stress_memory` | `not_identified` / `visualization` | Derived memory accumulator; descriptor says not assimilated/not identified and visualization ceiling. Registry also declares an update target, so policy drift must be reconciled. | No dedicated entry |

Descriptor source anchors: vigor 151–163; LAI 164–176; chlorophyll 177–189; canopy water 190–202; root-zone water 203–218; surface wetness 219–235; structure 236–252; bare soil 253–268; salinity 269–281; thermal 282–294; biotic 295–307; phenology 308–320; memory 321–333. Path: `services/agribrain/layer05_asmae/state/descriptors.py`.

There are eleven dedicated SIRE state types (`layer10_sire/schema.py:148–158,220–232`). Phenology and stress memory lack dedicated entries. Phenology is nevertheless read by the composite diagnostic renderer (`renderers/asmae_diagnostic.py:60,75`), so “never visualized” would overstate the gap. A complete expert inventory of all 13 is a sensible proposal; each row may validly say unavailable, prior-only or restricted and explain why. It must not fabricate a map to fill a slot.

## Preserve the actual epistemic axes

`StateSupportStatus` is `unsupported`, `prior_constrained`, `temporally_conditioned`, `spatially_conditioned`, `model_propagated`, `assimilated` (`scientific_contracts/state_status.py:17–24`). `StateEvidenceClass` is a separate classification: `directly_assimilated`, `proxy_assimilated`, `indirectly_constrained`, `prior_constrained`, `unsupported` (`state_support.py:26–31,79–134`). SIRE adds `derived_diagnostic` for inference diagnostics (`surfaces/asmae.py:445–479`). Product `EpistemicReality` is another axis (`authority.py:26–30`). Do not invent a single serialized enum by mixing these names.

The runtime engine builds support from accepted/excluded update reports (`engine.py:2859–2867` → `feature_export.py:73–174`), including per-state direct, indirect and proxy counts. A feature-export `status="real"` may come from an indirect accepted update (`feature_export.py:369–375`); it is not synonymous with a direct physical measurement. Its no-accepted-update branch is `prior_constrained`, zero confidence/weight and visual-only (`344–360`). The older typed `PerVariableSupportLedger` also carries units, posterior standard deviation and intervals (`state/support_ledger.py:23–59,101–124`); its existence alone does not prove every runtime artifact populates it.

Two contract details need explicit reconciliation before an all-state publication registry is derived. First, stress memory is declared NOT_ASSIMILATED in descriptors but targeted by `stress_memory_index` (`observation/index_state_mapping.py:219–228`). Second, missing state support can fall through to an Observed badge for a real raster (`surfaces/asmae.py:501–521`); this lane records the latter as a static concern for runtime reachability checking, not a proved end-to-end authority escalation.

A global `ASMAE_UNCERTAINTY` summary is calculated from normalized state sigmas (`engine.py:1931–1974`). A dimensionless display summary does not replace each state’s uncertainty in its own units, support and calibrated validity. An expert view should preserve the per-state values/masks alongside any summary.

## Claim checks and corrections

These rows assess reported code observations and design implications separately; they do not attribute a demand to bypass guardrails or label every state observed to the user.

| Reported observation or design check | Assessment |
|---|---|
| Thirteen latent-state definitions exist. | **corroborated static.** Config N_STATES/STATE_NAMES and descriptors match all 13; this establishes structural inventory only. |
| There are eleven dedicated SIRE state products; phenology and stress-memory products are missing. | **corroborated with scope.** The dedicated state-surface registry has 11 entries. Phenology is nevertheless consumed by a composite diagnostic renderer, so never visualized anywhere would be too broad. |
| No-scene/mean-only outputs clear scientific rasters. | **mean only source corroborated guard is normatively appropriate.** The inspected mean-only branch clears scientific rasters. Other no-scene executions belong to the runtime lane. R3 requires supported, authorized projections; an expert inventory should show unavailability reasons rather than force 13 maps. |
| Dimensional rejection, incoming render permission, and uniform ungrounded non-pixel behavior limit map availability. | **normatively required guards.** R3 requires geometry/mask/authority preservation and disables pixel inspection without pixel authority. The actual reported guard executions are reviewed in other lanes; this lane does not rerun them. |
| Nine broad frontend modes do not provide an expert 13-state inventory. | **reasonable product gap not exact R3 UI mandate.** Expert/farmer detail adaptation is supported by R3. An all-13 inventory with status/units/support/uncertainty/reasons is a proposed T09 design; exact mode count or tab count is not mandated. |
| State gates omit LAI/structure/bare soil/thermal and surface wetness; canopy-water uses vigor. | **corroborated static mapping.** Substring gate maps CANOPY/VIGOR before WATER and has no branches for the named unmapped states. ASMAE_SURFACE_WETNESS_EVENT is unmapped, not matched by WATER. Missing branches fail closed, so preserve guard intent when replacing with explicit canonical IDs. |
| Microzone-to-grid zero behavior is a suspected map gap. | **not determined in normative lane.** A zero may be legitimate state, a neutral prior, a fill value or an unsupported pixel depending on mask and provenance. Runtime evidence must determine which; R3 AB-DAT-005/008 forbids guessing from the numeral. |
| Arrays/NPZ do not establish per-state GeoTIFF/COG exports. | **array schema corroborated writer search belongs to storage lane.** R3 explicitly chooses qualified FieldCube arrays or COG/Zarr and geospatial raster storage COG/Zarr. It does not demand one GeoTIFF/COG per state at every endpoint or promise an existing exporter. Optional cog_ref is not proof of a writer. |
| A 13-state inventory needs observed/inferred/hypothesis distinctions. | **supported while preserving existing serialized axes.** ASMAE is reconstructed belief; observation relationship and accepted counts are per variable. Registered observation targets, real feature status, EnKF pass and SIRE Observed badge are not equivalent to a direct field measurement. |
| A canonical 13-state registry, explicit gates, valid masks and an expert inventory are warranted. | **supported proposal with dependencies.** Reuse existing frozen registry instead of creating a competing truth store. Reconcile descriptor/update-map/alias/gate/export/units/support contracts, and keep unavailable or hypothesis coordinates explicit. This is a bounded F36/T09 slice; complete F02 and package FA remain separate. |

The mean-only branch clears scientific rasters and keeps debug surfaces diagnostic (`engine.py:1883–1908`). This fits truthful degraded operation. Similarly, dimensions/CRS rejection, incoming render permission and plot-level ungrounded fallback are guardrails required by R3, not obstacles to remove for map count. Their actual reported executions are reviewed by other lanes; this normative lane does not claim to have repeated them.

The state gate uses substring rules (`layer10_sire/runner.py:5126–5157`): CANOPY/VIGOR selects vigor before the WATER branch; WATER selects canopy/root-zone support. LAI/structure/bare-soil/thermal/surface-wetness have no corresponding branch and fall to `surface_state_requirement_unmapped`. In particular, SURFACE_WETNESS_EVENT is unmapped, not matched by WATER. These omissions principally suppress availability; replacing them must retain state-specific support and incoming publication permission. A canopy-water surface checked against vigor is a linkage error even when separate scientific/diagnostic restrictions limit its downstream authority.

## Temporal state-map exports

The ASMAE output carries state-name-to-2D-array maps and a `state_timeline_ref` (`layer05_asmae/schema.py:485–497`); the engine copies that reference from `state_result.timeline_ref` (`engine.py:2972–2978`). SIRE also declares temporal products for NDVI change, growth/stress/risk momentum, yield and weather (`surfaces/temporal.py:8–21`), with a temporal-input presence check at line 51. Those products and a timeline identifier do not by themselves establish a replayable raster cube for every one of the 13 state variables.

For a proposed state-by-time view/export, preserve each coordinate’s value, units, uncertainty, support/masks, validity time, issuance/availability cutoff and lineage at each time slice. Distinguish hindcast reconstruction, currently assimilated belief and an archived issued forecast. This joins F02’s two-clock eligibility and F36’s per-variable/horizon qualification with T09’s canonical projection; it does not redefine all temporal UI as F02. No temporal cube or all-state exporter is implemented or claimed by this static review.

## GeoTIFF/COG: requirement versus implementation proposal

R3 explicitly calls for qualified FieldCube channels and geospatial storage suitable for COG/Zarr. It does not require thirteen separate GeoTIFF files, a COG for every current API response, or displaying all coordinates regardless of data. The existing ASMAE schema stores state/uncertainty/confidence as 2D arrays and includes a timeline reference (`schema.py:474–498`); SIRE has an optional `cog_ref` (`layer10_sire/schema.py:502`), which is not evidence that a COG writer exists. The separate storage lane determines whether inspected writers produce only arrays/NPZ.

A versioned multi-band COG or time-aware Zarr may be an appropriate implementation choice after selecting the product contract. Whichever format is chosen must bind variable identity, units, geometry/CRS/affine, valid/observed/reconstructed masks, uncertainty, native/effective/display resolution, acquisition/valid/issuance/availability times, parent lineage and permissions. Format conversion alone cannot supply missing support or convert a posterior to observation.

## Actionable ownership and sequencing

| Bounded next work | Existing owner / exact task | Dependencies and acceptance boundary |
|---|---|---|
| Reconcile the canonical state identity across descriptor, update target, source alias, SIRE product and explicit gate; correct wrong-variable gates while preserving fail-closed behavior. | F36 support semantics + T09 map projection; ST11-F36-01 and ST15-T09-02. Use current schema as the source, not a second registry of truth. | Per-state accepted support and actual publication permission are required. This can be a limited correction slice; it does not close either package. |
| Add an expert inventory of all 13 with declared units, current support class/age, posterior uncertainty, valid masks, effective resolution, source/dependence and unavailable/block reason. Offer concise farmer wording over the same artifact. | T09, especially ST15-T09-02/03; master:1459–1485; task list:2030–2059. | Full T09 depends F30/F31/F32/T01. The addendum permits slices when their own actual prerequisites exist; do not require or imply full world-model completion for a bounded truthful UI correction. |
| Calibrate sensitivity and objective eligibility by variable, including hypotheses and dependent teacher indices; preserve prospective/hindcast distinction. | F36 (tracked P1), ST11-F36-01…04; master:1072–1098; task list:1651–1681. | F01/F02/F24/F29 for full package; independent reference data/domain evidence remain necessary. T12 carries field validation. |
| Preserve times/cutoffs through temporal map requests, historical snapshots and exports. | F02 (tracked P0), ST01-F02-01…04; master:179–204. | Depends F01; whole F02 concerns two-clock issuance/replay across its three targets, not thirteen-map completeness. A map correction must not redefine its FA. |
| Bind current/scoped/committed product identity and degraded failure receipts; specify production geospatial storage/export contract. | F38 scoped/degraded publication; T11 publication convergence; T09 product projection. | F38 full deps F01/F02/F09/F31/F37; T11 full deps F09/F23/F25/F31/F35. A chosen COG/Zarr writer needs its own bounded implementation acceptance. |

The existing priorities above come from the plans. This report assigns no new arbitrary P0 label to “13 maps.” The plan’s execution addendum explicitly permits independent implementation after actual prerequisites and reserves full acceptance for full criteria/integration (`AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md:7–10,48–59`). F32 remains dashboard/calendar/empty-error semantics (`master:963–989`), not the generic owner of every SIRE map. F01 merge recommendations remain a separate review decision; this discovery does not reopen, accept or merge it.

The proposed acceptance example is concrete: one supported canopy-water raster cannot pass because vigor alone is supported; an unsupported coordinate stays visible in the expert inventory with its reason and emits no fabricated physical zero/map; the same source artifact, masks and permissions survive expert/farmer view and export; time/cutoff fields reproduce the issuance view. These examples are proposed future checks, not executed results in this lane.

## Evidence files and limits

`mapping.json` contains the 13 descriptor records, their actual registered observation targets, dedicated SIRE inventory, R3 mapping, claim checks, package dependencies and separate serialized axes. `source-manifest.json` hashes every inspected source/normative input, verifies production and all three plan blobs against the pinned tree, and records the supplied R3 PDF/text provenance. `normative-excerpts.txt` preserves the cited governing passages. `build_report.py` reproduces these static artifacts from the staged source and supplied normative files.

No runtime coverage, crop-domain empirical validity, service publication health, GeoTIFF writer existence, or full-package acceptance follows from this static lane. The zero/microzone claim and fallback-observation reachability require runtime evidence from the companion lanes.

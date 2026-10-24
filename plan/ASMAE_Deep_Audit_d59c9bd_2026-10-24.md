# ASMAE publication: deeper connected audit at d59c9bd

Date: 24 October 2026. Pinned candidate: `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`, branch `feat/f36-t09-asmae-13-state-publication`. Immediate parent: `a31a65e631daa7cdc1860861c9184cf05225cb82`. Main was independently observed at `90ab701714554c7b786bba4ac6b19259e77279ce`.

## Decision

**Move from individual residual fixes to three integrated deliveries.** The latest Stage 3 work registers all thirteen state products correctly at the structural level. The deeper review finds six connected correctness groups across estimation, scientific receipts, catalog/availability, masks/grids, persistence/export and consumer presentation. They should be repaired together along those interfaces, rather than producing another sequence of one-defect commits and reviews.

The next implementation cohort should cover **A: scientific publication contract**, **B: spatial artifacts and durable publication**, and **C: complete expert consumer/GIS delivery**. A and B can start in parallel after a short shared-contract agreement; C can develop against those fixtures while its final integration waits for their stable receipts. Each is a substantial, independently reviewable unit. The companion implementation plan gives concrete tasks, ownership and acceptance gates.

This is a source-backed current-code review of the ASMAE publication vertical slice, not a complete audit of every AgriBrain subsystem. The 1,087-file source inventory is verified for identity; it is not a claim of exhaustive review of all those files. No production source, branch, FA row or hardware was modified.

## 1. What is now implemented

Native checks confirm thirteen dedicated SurfaceTypes, state products, render modes, palettes and terminal inventory identities, including `ASMAE_PHENOLOGY_PROGRESS` and `ASMAE_STRESS_MEMORY`. Aligned authored inputs generate thirteen native surfaces. Existing explicit False permissions remain represented in the checked positive fixtures. Both new states have frontend inventory/stack recognition and exact legend entries.

That closes the previous two-product structural omission. It does not establish thirteen independently observable states, thirteen independently selectable browser products, or thirteen GIS artifacts. The expert selector remains Stage 4 target work; nodata propagation is Stage 5 work with concrete current defects; integrated GIS publication/download remains Stage 6 target work.

The review does not reopen the resolved S653 checked-square or S8D covariance finding groups. It expands scope to connected producer/consumer boundaries that the earlier narrowly bounded reviews did not establish.

## 2. Six consolidated finding groups

| Group | Priority and boundary | Reproduced behavior | Repair delivery |
|---|---|---|---|
| WB01 | P1 scientific support identity; P2 normalization | Real NDVI-derived latent states receive direct/Observed labels; zero-support/zero-gain targets gain accepted counts/field-approval flags; direct/proxy counters are erased during normalization | A |
| WB02 | P2 capability/restriction contract | Raw metadata can retain True state-update permission beside Unsupported/diagnostic support; string `false` becomes True; alternate restriction carriers are inconsistently gathered | A |
| WB03 | P2 catalog and availability | New catalog is not consumed by runtime tables; eight state bounds are missing from invariants; LAI legend stops at 6 although valid range reaches 8; all-None surfaces can be called plot-level products without a scalar artifact | A, then C consumer |
| WB04 | P1 missing-support integrity, plus P2 grid/mask boundaries | Missing cells become zero means and sigmas, then concentration 1.0; same-grid nodata bypass can create apparent spatial variation; cache masks and browser geometry proof are not preserved consistently | B |
| WB05 | P2 durability and scientific export | Failed replacement can make the last committed cache unreadable; raster compatibility export loses nine scientific metadata fields; generic GIS helper has CRS/nodata prerequisites | B, then C GIS |
| WB06 | P2 current precision label; deferred selector plus interpretation debt | Dock says 10 m for authored 1,000 m support; fixed lenses do not independently select the thirteen raw coordinates; routing/legend/missing-reason definitions disagree | C |

These are root repair groups, not six isolated patches. Some contain several related observations. Most mechanisms are inherited current gaps, not demonstrated regressions caused by the two new product definitions. Explicitly deferred capabilities are distinguished from correctness defects throughout the specialist appendices.

### WB01 — measured sensor reality is confused with latent-state directness

The native H_t update emits `evidence_kind='direct_observation'` for all mapped targets. The ledger and feature export use that shared label to confer state-level directness and field-approval flags. In a native NDVI fixture, vigor and LAI become Observed even though their descriptors require indirect constraint. Actual optical B04/B08/B11 extraction also creates a stress-memory proxy; assimilation changes the accumulator by **0.2374967460**, then publication calls it Observed while its descriptor says NOT_ASSIMILATED/NOT_IDENTIFIED.

The same producer records an accepted target when a zero-overlap operator produces no localized update, and when a positive-support NDVI update changes vigor but the constant LAI coordinate has zero numerical/information effect. A varying-LAI positive control does update. A zero mean innovation is not sufficient grounds for rejection: uncertainty contraction may be informative. The repair must evaluate per-state support/gain/information, not simply require nonzero mean change.

Canonical ledger adaptation independently resets direct count 1 to 0 and proxy count 1 to 0 while preserving their asserted relationships. Thus callers see contradictory raw versus normalized receipts, and SIRE still labels the direct-relationship state Observed.

Primary evidence: [services/agribrain/layer05_asmae/assimilation/filter.py:L1701-L1724](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/layer05_asmae/assimilation/filter.py#L1701-L1724), [services/agribrain/layer05_asmae/feature_export.py:L103-L160](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/layer05_asmae/feature_export.py#L103-L160), [services/agribrain/scientific_contracts/ledger_adapter.py:L68-L84](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/scientific_contracts/ledger_adapter.py#L68-L84). This proves scientific-label and feature-pack eligibility defects. Tested runtime ceilings remain DIAGNOSTIC and management eligibility False; no prescription or actuator consequence is claimed.

### WB02 — restrictions and capabilities do not have one typed projection

Fresh native surface construction accepts metadata `state_update_allowed=True` beside Unsupported or diagnostic state support. A string `false` is also converted to True by truthiness. Alias paths retain stricter False, leaving inconsistent raw/alias/serialized views. Serializer carrier conflicts, malformed booleans and missing defaults need the same normalization rather than separate patches.

The shared restriction union helper recognizes more field spellings than some ingress/caller paths collect. Canonical snake-case positive/negative controls behave correctly, but alternative camel/snake exclusion carriers can lose revocation. The previous S81 dual-carrier closure is not invalidated: the expanded vocabulary gap is a broader, already disclosed qualification that now belongs in the integrated contract repair.

This is an artifact-contract inconsistency. The display gate still blocks the tested Unsupported raw surface, and no downstream state update, permission exploitation or physical action was demonstrated. Authoritative-carrier precedence must be specified explicitly before interpreting every arbitrary metadata role string as a revocation.

### WB03 — structural registration is ahead of catalog convergence

The canonical catalog is defined/exported but not consumed by the actual runtime generator, invariant and legend tables. Controlled out-of-bound inputs pass through native generation and miss invariant INV-2 for eight fraction states: canopy water, root-zone water, wetness event, structure, bare soil, salinity, thermal and biotic risk. Vigor, LAI, chlorophyll, phenology and memory controls are detected. Normal ASMAE state clipping is present; this is a native-boundary integrity counterexample, not evidence that normal field states exceed their bounds.

A valid LAI 7.0–7.8 surface passes its invariant but has no server legend interval because the legend ends at 6. Metadata-only prior inputs containing neither raster values nor scalar estimates create thirteen all-None objects; inventory calls them `plot_level_only`, while manifests enable their modes from object presence. A terminal no-data control correctly reports missing. No unauthorized overlay is inferred, but availability is not a coherent scientific contract.

An additional temporal seam is reproduced with the real empty-ledger producer and authored varying temporal grids: both states are prior-constrained, yet the isolated gate rejects phenology and permits memory. Explicit model-propagated/temporally-conditioned status controls authorize both. This is a producer/status integration fixture, not a complete weather-driven forecast execution.

Primary evidence: [services/agribrain/scientific_contracts/state_schema_ref.py:L87-L230](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/scientific_contracts/state_schema_ref.py#L87-L230), [services/agribrain/layer10_sire/invariants.py:L62-L119](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/layer10_sire/invariants.py#L62-L119), [services/agribrain/layer10_sire/products/manifest.py:L126-L129](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/layer10_sire/products/manifest.py#L126-L129). Deliver one catalog-driven domain, legend and availability builder, including a genuine plot-state artifact reference separate from pixel availability.

### WB04 — missing spatial support can acquire confident numerical meaning

The exact microzone converter initializes unassigned cells to zero for all thirteen means and sigmas. A sparse 2×2 fixture has two holes that become physical-looking zeros; the exact aggregate block then turns missing uncertainty into posterior concentration **1.0**. True supported zero remains zero as a positive control. The standard graph normally emits a rectangular lattice; ordinary sparse input incidence was not established. The missingness defect was already planned for Stage 5, and this review establishes its uncertainty consequence.

A separate native alignment defect does not require sparse IDs: identity alignment returns before normalizing explicit nodata. A `-9999` sentinel remains finite and causes a fixture to be classified RASTER_GROUNDED, whereas the all-zero physical control is UNIFORM. A valid resampling control removes the sentinel. Cache persistence also strips accepted MaskedArray masks, exposing hidden payload 77 as a measurement; actual field frequency of that input form is unestablished.

Pure frontend preflight functions accept contradictory declared dimensions, unsupported metric display bounds, all-null support and masks with mismatched affines. These are preflight outputs, not evidence of actual browser rendering or backend acceptance.

Primary evidence: [services/agribrain/layer05_asmae/engine.py:L3255-L3305](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/layer05_asmae/engine.py#L3255-L3305), [services/agribrain/layer10_sire/surfaces/asmae.py:L540-L574](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/layer10_sire/surfaces/asmae.py#L540-L574). Fix creation, uncertainty aggregation, alignment, cache and display-grid identity together; otherwise a correct mask at one layer disappears at the next.

### WB05 — scientific artifact transactions and export receipts are incomplete

A native full-cache positive save/read succeeds. A subsequent candidate overwrites the fixed NPZ path before the JSON commit. Injecting JSON commit failure leaves the old JSON but a different NPZ; the last committed generation becomes unreadable. Checksums correctly reject the mismatch. This is loss of prior committed availability, not silent acceptance of mixed scientific values.

The active `export_raster_pack` path preserves basic values/style but drops nine tested canonical scientific receipt fields, including grid/CRS, masks, uncertainty, provenance/restrictions and explicit False permissions. Canonical surfaces elsewhere still retain those fields; that does not restore them to each standalone compatibility entry. No consuming privilege escalation was established.

The generic GIS reader also multiplies projected 10 m spacing by 111320, reporting **1,113,200 m**, and returns a nodata sentinel numerically. This used the exact method with an inert dataset because Rasterio/GDAL is absent; it is not a real GeoTIFF roundtrip or a deployed thirteen-state GIS failure. Generic writer support does not itself establish COG compliance or integrated downloads.

Primary evidence: [services/agribrain/layer05_asmae/cache.py:L508-L533](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/layer05_asmae/cache.py#L508-L533), [services/agribrain/layer05_asmae/cache.py:L683-L717](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/layer05_asmae/cache.py#L683-L717), [services/agribrain/layer10_sire/products/export.py:L18-L94](https://github.com/webClone/AgriWise/blob/d59c9bdc85a64469a9424d4c7757a2d2c4da3041/services/agribrain/layer10_sire/products/export.py#L18-L94). Publish immutable artifact generations and atomically switch one manifest, and derive all export projections from a shared scientific receipt.

### WB06 — consumer recognition is not independent scientific selection

All thirteen raw states are now recognized by the frontend inventory and stack mappings. Only raw ASMAE_VIGOR appears in current broad-lens priorities. A direct-priority control selects every state through the same actual pure resolver, proving a selection-model limitation rather than a transport limit. The expert selector is explicitly deferred Stage 4 work, not a Stage 3 regression.

The current dock independently says `evidence basis 10m` for a controlled 1,000 m root-zone product and a 30 m temporal product. This overstates scientific support resolution. Current grid pixel size must not be substituted for effective resolving power.

Routing and interpretation debt should be fixed before exposing all raw states: canopy-water inverse substring routing yields canopy, raw chlorophyll can inherit high=Deficient rather than High chlorophyll, and local ASMAE missing-reason fallback blames L5. The inverse route is partly masked by normal known-mode fallback; raw chlorophyll is not normally lens-selectable; authoritative backend inventory can override local reasons. These are documented helper/integration hazards, not claimed current user incidents.

## 3. Evidence, reproducibility and limits

| Lane | Fresh observation assertions |
|---|---:|
| Scientific semantics | 11 |
| Catalog and availability | 26 |
| Authority/restrictions | 32 |
| Frontend projection | 18 |
| Spatial validity | 10 Python + 6 TypeScript |
| Persistence/export | 12 |

The coordinated replay reproduced **115 observations**, including defects and positive controls. These counts overlap in boundary coverage and are not 115 passing scientific contracts. Seven top-level offline commands exit zero. Nine changed production Python modules compile. All 1,087 selected source identities remain unchanged.

Native pure functions are used where practical; exact isolated engine/runner/TypeScript fragments are explicitly identified in the appendices. No repository tests or earlier audit documents serve as correctness proof. No full runner, provider, authenticated API, browser, GDAL file roundtrip, optimizer, prescription, drone or field controller was executed. The report does not establish normal incidence for every malformed/sparse input.

The evidence archive contains six lane reports, scripts, strict JSON results, source receipts, replay logs, normative references and exact-source reconstruction instructions. Production source, repository test files and private runtime stores are excluded. A reconstructed source environment can replay the evidence using the pinned Git objects. The staged exact sources were executed; full Git-object reconstruction was not freshly executed.

## 4. Governing plan and readiness

The master repair plan, sequencing addendum and task register match the pinned candidate tree. R3 identity is verified against the supplied PDF. The work chiefly serves F36, F38, T09 and T11, with AB-ASM-003/011/016, AB-ARC-005/006/007 and AB-L10-001. No status text is inserted into the target monograph, and no requirement is waived.

Exactly **52 FA milestones remain open, zero checked**. That does not require postponing all bounded implementation until every package is accepted. It does require separating software completion from independent per-state calibration, real-plot/browser qualification and complete package acceptance.

**Proceed now with larger coherent repairs.** Preserve the Stage 3 structural registration, freeze the candidate as the review baseline, and implement the three companion batches against one versioned scientific product/raster contract. Review each integrated batch once after its complete acceptance matrix, then run one combined regression/release gate. Do not repeat the entire old covariance review for every unrelated catalog or mask edit.


---

# Specialist appendix: Scientific support

# Scientific state semantics and producer-to-publication support

Candidate: `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`. This is a broad current-code review, not an assertion that Stage 3 introduced the mechanisms below. The inspected numerical/ledger paths are substantially inherited. No earlier S653/S8D/S81 numerical closure is reopened.

## One coherent repair batch: WB01 — state-specific scientific support receipts

**Finding group: confirmed, P1 scientific-truth boundary, with P2 lossless-normalization work in the same batch.** Physical pixel provenance, latent-state inference relationship, numerical influence and operational authority are currently collapsed into one report-level `direct_observation` flag. Repair them as one producer-to-consumer contract rather than separate small patches.

### A. A real per-pixel index is incorrectly promoted to a direct observation of every targeted latent state

`assimilation/filter.py:1701–1724` unconditionally emits `update_applied=True` and `evidence_kind='direct_observation'` for every mapped target in a native H_t update. `feature_export.py:103–118,147–160` converts this into state-level direct counts and `field_approval_eligible=True`. `feature_export.py:365–402` then exports real/direct state confidence and weight `0.90`, including `usable_for_field_approval=True`.

Native authored NDVI input updates vigor and LAI. Their descriptors explicitly say `INDIRECT_CONSTRAINT` (`state/descriptors.py:163–189`). Yet the actual ledger→canonicalization→SIRE classification path labels both `Observed`, `direct_observation=True`. The independently supplied scene provenance flags are declarations used to exercise the real-raster code branch, not a claim of acquired field data.

The stress-memory inconsistency is more severe semantically: the descriptor declares `NOT_ASSIMILATED` and `NOT_IDENTIFIED` (`descriptors.py:321–333`), while `observation/index_state_mapping.py:219–228` maps `stress_memory_index` to the accumulator. Native pixel extraction derives this index from the same optical bands/indices (`pixel_extraction.py:177–195`), then native assimilation changes stress-memory and the same ledger/SIRE path labels it Observed. The controlled B04/B08/B11 fixture changed stress-memory by **0.2374967460** while its descriptor still says not assimilated. A constructed direct-memory-band control also reproduces the inference route; the optical-band derivation is the stronger normal-algorithm proof.

This is not an automatic prescription or actuator finding. Runtime ledger ceiling is DIAGNOSTIC, and the tested SIRE `management_zone_eligible` is False. The defect is incorrect scientific identity and the separately verified feature-pack field-approval flag; actual final prescription dispatch was neither invoked nor established.

### B. Target admission records numerical influence that did not occur

The report is marked applied even when no H_t zone has positive local support. A zero-overlap authored operator produced `localized_zone_updates=0`, maximum analysis delta **0.0** over the entire ensemble, yet every mapped target received an accepted/direct count and feature-pack field-approval eligibility.

A less synthetic support boundary uses a positive H_t operator and ordinary NDVI, with nonzero vigor ensemble variation and a constant LAI coordinate. Vigor updates; LAI remains exactly unchanged with zero information gain, but LAI still receives `accepted_update_count=1`, a direct-state identity and field-approval eligibility. The positive control with varying/correlated LAI does change LAI, proving the probe does not disable the algorithm globally.

A zero **mean** innovation alone is not a reason to reject a valid update: covariance contraction may provide information. The missing contract is qualified per-state numerical/support influence, not a simplistic `abs(mean_delta)>0` gate. Likewise, this zero-H fixture proves admission behavior at the native update boundary; it does not claim the normal geometry constructor routinely emits a completely zero operator.

### C. Canonical normalization silently erases counters while preserving the asserted relationship

`scientific_contracts/ledger_adapter.py:68–84` constructs `StateSupportRecord` without copying `direct_observation_count` or `proxy_observation_count`. The dataclass defaults both to zero, and the later raw-key loop does not restore any key already present in the canonical dict.

Fresh producer-ledger→canonical-adapter controls show:

| Kind | Raw count | Canonical count | Other retained field |
|---|---:|---:|---|
| Direct observation | 1 | 0 | `observation_relationship='direct'` |
| Proxy observation | 1 | 0 | `observation_relationship='proxy'` |
| Indirect observation | 1 | 1 | Retained only as a non-dataclass extra |

SIRE still returns Observed for the direct relationship despite the zero direct count, so erasing the counter is not an effective restriction. It creates contradictory contract views and makes scientific diagnostics depend on whether a caller reads the raw producer ledger or the normalized one.

Per-update prior/posterior/information-gain values are retained inside `accepted_updates`, but the producer leaves corresponding state-level summaries unset. The probe records this as a coverage/aggregation limitation, not a second proof that the nested evidence was lost. The consequential counter-loss finding is independent of the intended summary aggregation policy.

## Evidence and repeatability

`probes.py` freshly executes native pixel extraction, `update_step_ht`, the actual ledger builder, canonical ledger adapter, native feature export and native SIRE classifier. It uses authored scenes and in-memory operators; network access is blocked. No repository test file, full runner, provider request, API, browser, optimizer, prescription or hardware path is executed.

**11 observation assertions reproduce**, including positive variable-state update, real-band derived memory, constant-target and zero-overlap boundaries, direct/proxy/indirect normalization controls, and immutable source. Full numeric results are in `results.json`; exact production blobs and SHA-256 hashes are in `source-receipts.json`. Successful assertions document present defects and controls; they do not mean those scientific contracts pass.

## WB01 implementation scope — one integrated delivery

1. Define a canonical per-state update receipt with separate fields for observation reality/role, measured variable, state inference relationship, spatial support, analysis effect, uncertainty change, descriptor policy and explicit exclusions. Keep shared observation IDs so derived indices do not masquerade as independent evidence.
2. Make both native H_t report producers emit those per-state receipts. No positive support means no accepted update. Zero target covariance/gain must not confer measurement authority; preserve valid uncertainty-only information and ordinary finite physical zero values.
3. Reconcile stress-memory policy explicitly: either preserve its model/accumulator role and forbid observation analysis, or deliberately authorize a derived constraint with matching descriptor, source role and validation. Never badge an optical stress proxy as a directly measured temporal accumulator. Apply the same measured-versus-inferred distinction to vigor, LAI, phenology, root-zone water and hypothesis states.
4. Make `build_state_support_ledger` consume the canonical receipt. Separate accepted numerical update from direct physical measurement and from field-approval eligibility. Carry forecast/model/accumulator transitions as genuine model receipts rather than fabricating observations.
5. Make the normalization adapter lossless and typed for direct/proxy/indirect counters, relationships, numerical summaries and nested receipts. Reject contradictory combinations or normalize them monotonically downward with explicit diagnostics; do not reset counts silently.
6. Derive feature-pack and SIRE support classifications from this one canonical result. Retain descriptor/runtime authority intersections and False action permissions. Every catalog product should consume the same state support instead of recreating competing directness rules.
7. Verify the integrated boundary once with a matrix that includes native extraction→analysis→ledger→normalization→feature export→raw surface/alias provenance. Keep earlier numeric/restriction closures as controls, without re-auditing unchanged helper edge cases in separate review cycles.

## Acceptance criteria

- Real NDVI/NDRE/SAR pixels remain measured sensor evidence; corresponding latent states carry their independently justified indirect/model/hypothesis relationship.
- A derived optical memory proxy cannot produce a directly observed accumulator, and descriptor/runtime behavior agree.
- Zero local H_t support creates an excluded receipt and no accepted-state count.
- A zero-gain constant target cannot gain field-approval authority; a valid uncertainty-reducing analysis remains qualified even when the mean is unchanged.
- Direct, indirect and proxy counts survive canonical round-trip exactly; relationship/count/policy contradictions are explicit.
- Per-state support decisions agree between feature pack and SIRE, while diagnostic/scouting/field-approval/action permissions remain separate.
- Positive varying-state updates and physical zeros still work. S653/S8D/S81 closures remain retained.

Relevant governing requirements: **AB-ASM-003** state-specific sensitivity/observability; **AB-ASM-011** per-variable label/permission propagation; **AB-ASM-016** local validity is not blanket certification; **AB-ARC-005** factored authority; **AB-L10-001** qualified canonical spatial projection. Package ownership is chiefly **F36**, with shared scientific-contract normalization and downstream **T09/F38/T11** parity. This bounded batch does not close any full package; all FA gates remain open.


---

# Specialist appendix: Product/catalog and availability

# Catalog, availability and publication contract review

Pinned source: `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`. Read-only native offline probes; exact isolated inventory statements from `runner.py:3855–4024` are executed without importing or running the full runner. No repository test or audit file is a correctness oracle. Command: `python review-wide-d59c9bd/catalog/probes.py`.

## Verified Stage 3 work

The newly dedicated `ASMAE_PHENOLOGY_PROGRESS` and `ASMAE_STRESS_MEMORY` are present in SurfaceType, the 13-member ASMAE state set, RenderMode, surface-to-mode mapping, palette/legend maps, no-data inventory, native generator unit/range/feature/creator maps and invariant maps. The canonical thirteen-entry state catalog preserves the frozen state order. Native generation produces all thirteen when given aligned authored raster inputs, with catalog/native unit and render-range parity. Explicit False action permissions survive canonical serialization. The terminal no-data producer exposes all thirteen state keys as missing.

These are structural/software checks, not evidence that every latent coordinate is independently identified or pixel authorized. No expert picker, GIS download or real-plot execution is claimed; those remain later stages.

## CAT01 — P2: availability describes object presence instead of usable product content

Current connected gap, not evidence of a new unauthorized overlay. `build_render_manifest` marks a mode enabled whenever a matching surface object exists (`products/manifest.py:269–275,291–299`). The runner inventory derives availability from grounding class and support label (`runner.py:3904–3938`), without checking valid values or a separately qualified plot-state artifact.

Fresh native counterexample: thirteen state metadata entries with valid prior variance, **no raster and no scalar values**, generate thirteen quarantined all-None surface objects. The exact inventory block labels all thirteen `plot_level_only`, while the manifest enables all thirteen modes. The fixture does not contain a plot-state artifact. Tile metadata lists these products as available layers. The terminal no-data control, by contrast, labels all thirteen missing. The native and serialized surfaces remain non-actionable; no full-runner authorization or browser visibility bypass is inferred.

An independent raster fixture with missing scientific support correctly obtains inventory status `unsupported`, yet its manifest modes are still enabled because the same presence rule applies. This shows the `enabled` field expresses structural presence, not scientific eligibility. Consumers should receive those separate facts explicitly instead of inferring their meaning.

Repair in one contract change: generate thirteen inventory entries from one shared builder that computes `registered`, `materialized`, `valid_pixel_count/fraction`, `plot_state_available`, `support_status`, `display_authorized`, `action_authorized` and exact reasons. All-None rasters must not become plot estimates just because grounding is UNIFORM. A separately available plot-state artifact may support a card and must stay separate from raster availability. Manifest and tile metadata must consume the same availability receipt; retain diagnostic inspection without implying valid pixel coverage.

## CAT02 — P2: the new canonical catalog is not the runtime source of truth

`CANONICAL_13_STATE_CATALOG`, its map and accessor are referenced only in their defining `scientific_contracts/state_schema_ref.py` and package exports. Native generation, manifest legends and invariant rules continue to maintain independent tables. That is a concrete maintenance/integration gap with two demonstrated consequences:

1. **Eight physical state ranges are absent from runtime invariant validation.** Feed aligned out-of-range authored raster inputs through native `generate_asmae_surfaces`, then call actual `enforce_layer10_invariants`. Values exceeding each catalog upper bound trigger INV-2 for vigor, LAI, chlorophyll, phenology progress and stress memory. They do not trigger INV-2 for canopy water, root-zone water, surface wetness event, structure, bare-soil fraction, salinity stress, thermal stress or biotic confounder risk. All eight have catalog render domain `[0,1]`, but `invariants.py:62–119` omits them. The newly added phenology and memory entries are positive controls: the validator executes and detects their excess correctly. This is an adversarial native-boundary integrity counterexample; the normal ASMAE engine clips its states, and normal field occurrence of these invalid values is not established.
2. **Valid LAI 6–8 has no server legend interval.** The catalog, generator and invariants support LAI `[0,8]`. The server manifest legend ends at 6 (`products/manifest.py:126–129`). A controlled 3×3 surface containing LAI 7.0–7.8 passes the actual numerical invariant, but no legend interval covers its values. This establishes an incomplete published server legend, not a claim about a browser's particular color fallback.

Repair as the same catalog contract slice: define scientific admissible domain separately from visualization range when necessary; make the canonical spec drive all thirteen range rules, generator metadata and mode legend/palette specifications; eliminate duplicated hardcoded state sets where the canonical mapping can be used. Never silently clamp corrupt scientific values just to fit display bounds: fail locally, preserve explicit diagnostics and retain independently valid siblings. Add a table-derived finite/nonboolean/boundary qualification matrix, rather than one hand-maintained case for each latest defect.

## One cohesive larger batch

**WB03: canonical product and availability contract**, coordinated with the parent's authority/temporal-support subfinding. Suggested touchpoints: scientific state schema/registry, ASMAE native surface builder, invariant validator, render manifest builder, normal and terminal inventory builders, canonical serializer and frontend catalog receipt. This replaces repeated per-state table patches with one complete thirteen-state matrix.

| Acceptance fixture | Required result |
|---|---|
| All thirteen supported aligned raster inputs | Thirteen exact state/product identities, correct units/ranges/uncertainty identity, retained permission ceilings |
| Missing one raster and scalar, metadata only | Explicit no materialized pixels; no invented plot-state estimate; other twelve remain available |
| All-None raster | Zero valid pixels; no available-raster claim; exact reason retained through inventory/manifest/serialization |
| Separate real plot-state artifact but no raster | Card available under its own scope; pixel overlay unavailable |
| Unsupported or revoked state | Inventory and manifest express the restriction; no value influence on valid siblings/composites |
| Each of thirteen states at valid limits and just outside | Shared domain validator recognizes valid physical zero and rejects out-of-domain values locally |
| LAI 7.0–7.8 control | Retains scientific value and has a complete legend/display specification |
| No-data/terminal publication | Same thirteen identities and restriction vocabulary as successful publication, all explicit missing/degraded reasons |
| Existing qualified products | No accidental loss of units, range, permission False or aligned grid identity |

Keep expert independent selection (Stage 4), nodata creation/routing (Stage 5) and integrated GIS export (Stage 6) separately identified, but they can be developed alongside WB03 against the frozen receipt. This lane does not call those deferred capabilities regressions in d59c9bd.

## Scientific plan trace and evidence

The findings concern qualified canonical spatial projection (AB-L10-001), bounded degradation without invented capability (AB-ARC-006), and factorized authority (AB-ARC-005). They map to T09 with F38/T11 publication parity and F36 state semantics, without closing any full package FA milestone.

Fresh evidence: **26 observation assertions**, all reproduced, including positive controls and current counterexamples. The source manifest verifies **1,087 selected files** against the pinned Git tree. This source inventory is not a claim that all 1,087 files were independently reviewed. The script blocks network connections; only pure builders, validators and the isolated inventory AST execute. No production file changed.


---

# Specialist appendix: Restrictions and capabilities

# Scientific restrictions and capability continuity: broader review

Candidate: `d59c9bdc85a64469a9424d4c7757a2d2c4da3041` (24 October 2026).

## Result

The prior literal-False and canonical dual-carrier closures remain intact. Two connected current contract gaps should be repaired together in a single canonical restriction/capability batch. They are inherited/current seams, not regressions caused by registering the two Stage 3 products. Fresh probes execute native surface/alias generation, the canonical serializer and the exact isolated runner authorization AST; they do not execute the complete runner or any physical action.

Coverage: fourteen native carrier cases, five serializer cases, three temporal producer controls and thirty-two grouped observations. All observations reproduce. The 1,087 selected source files retain exact Git/SHA-256 identity. Surface inputs in the probes are authored carriers; normal live-producer occurrence is not established merely by their acceptance.

## A-AUTH-01 — Capability admission is not intersected with scientific support

Priority P2: inconsistent exported authority contract. No operational state update or actuator execution is claimed.

`surfaces/asmae.py:1334–1335` reads diagnostic/state-update permission directly from raster metadata. Classification later establishes per-state support, but `1777–1791` converts the earlier value with ordinary `bool(...)` and constructs the raw surface without intersecting Unsupported status, runtime DIAGNOSTIC ceiling, diagnostic-only role or `asmae_surface_spatially_eligible`.

Fresh native results:

| Fixture | Raw support / authority gate | Raw serialized state-update permission | Alias permission / diagnostic display |
|---|---|---|---|
| Qualified indirect control, False metadata | Indirect; stronger authority gate denies | False | False; display authorized |
| Same DIAGNOSTIC support, metadata True | Indirect; stronger authority gate denies | True | False; display authorized |
| Same DIAGNOSTIC support, metadata string `"false"` | Indirect; stronger authority gate denies | True | False; display authorized |
| Missing ledger, metadata True | Unsupported; stronger authority gate denies | True | False; display denied |
| Missing ledger, metadata string `"false"` | Unsupported; stronger authority gate denies | True | False; display denied |

The display gate correctly denies Unsupported surfaces and aliases correctly force action False. Those controls bound the finding: the demonstrated error is a contradictory raw exported capability, not a proven downstream physical influence.

A second side of the same typed-capability gap exists in `surface_contract.py:202–222`. A provenance mapping with snake-case True and camel-case False retains True because `dict.get(snake, camel)` does not intersect both declarations. Invalid strings `"false"` become True. A mapping without permission declarations defaults both state-update and prescription-driver permission to True. Literal canonical False and camel-False-only controls do correctly deny.

The serializer is a supported generic mapping/object boundary; the alias contradiction is reproduced directly through its real function. It is not proof that every normal producer currently emits conflicting camel/snake aliases.

## A-AUTH-02 — Shared restriction vocabulary is not collected uniformly

Priority P2: inherited Q8D-01 now suitable for a complete batch instead of repeated individual alias fixes.

The shared `resolve_surface_block_reasons` helper recognizes all six spellings below, but the native metadata ingress loop at `surfaces/asmae.py:1569–1582` only reads canonical snake-case block/restriction lists. The omitted declaration is lost before aliases and the final gate can enforce it.

| Metadata key carrying `local_support_revoked` | Native raw gate | Native canopy-alias gate | Shared helper recognizes input |
|---|---|---|---|
| `block_reasons` | Denied | Denied | Yes |
| `restriction_reasons` | Denied | Denied | Yes |
| `blockReasons` | Authorized | Authorized | Yes |
| `restrictionReasons` | Authorized | Authorized | Yes |
| `exclusion_reason` | Authorized | Authorized | Yes |
| `exclusionReason` | Authorized | Authorized | Yes |

The stronger original canonical controls remain repaired. This broad review does not reopen their closed finding; it establishes the remaining vocabulary boundary under explicit authored carriers.

Additional carrier qualification: with a qualified ledger, metadata `support_status="revoked"`, `support_class="unsupported"` or `source_role="EXCLUDED"` is ignored by the checked native classification/gate path. The metadata schema does not establish that all three declarations are currently emitted as authoritative revocations. Treat this as a specification/normalization decision to resolve in the same batch rather than three separately asserted new regressions.

The runner's final surface gate (`runner.py:5304–5361`) duplicates restriction parsing, and serialization (`surface_contract.py:276–280`) collects a third subset. Fixing only one loop will therefore leave future parity gaps.

## Temporal producer seam: evidence for the catalog/semantics batch

The real `build_state_support_ledger([])` producer emits all states as `prior_constrained` with `spatial_support="microzone_grid"`, zero accepted updates and reason `no_accepted_state_update`. Supplying its untouched ledger alongside authored varying phenology/memory grids produces both native surfaces as Prior-Constrained. The exact runner gate denies phenology (`missing_state_support:phenology_progress`) but authorizes stress memory. Changing only the two statuses to explicit `model_propagated` or `temporally_conditioned` authorizes both.

This probe establishes a producer/consumer status seam and positive controls. It does not execute temporal integration or prove that a legitimate forecast failed on a live plot. Combine it with the scientific lane's forecast producer trace; the durable fix is an explicit model-evolution receipt and catalog policy, not incrementing accepted sensor counts or fabricating assimilated status.

## One larger repair batch: canonical restriction and capability projection

Owner packages: F36 / T09, with F38/T11 boundary parity. Governing requirements: AB-ARC-005 factored authority, AB-ARC-006 bounded degradation, AB-ASM-016 local validity and AB-L10-001 qualified projection.

1. Define one typed carrier normalizer for current support, source role, restrictions and capabilities. Admit only actual boolean True for positive action permissions; absence/malformed declarations do not grant authority. Specify allowed legacy spellings, canonical storage and diagnostics for rejected inputs.
2. Union active restrictions across metadata, typed surface attributes, ledger and nested provenance before classification. Establish which carrier can issue a current denial. Restrictive values win; warnings remain nonblocking and cannot mask revocation.
3. Compute each raw capability from the intersection of per-state support, static descriptor ceiling, runtime ceiling, diagnostic role, source qualification, spatial/physical proof and all current denials. The calculation must be per-capability: visualization/scouting is not a state-update or prescription grant.
4. Use that normalized receipt in native generation, aliases/composites, canonical serialization, terminal inventory, runner authorization and API/UI consumption. Remove hand-written subsets. Preserve unsupported inventory entries and qualified siblings without fake maps.
5. Verify the whole carrier-by-capability matrix in one native integration suite, then freeze the interface for the remaining explorer/nodata/export work.

Acceptance matrix: every accepted spelling at every supported carrier location; conflicting snake/camel True/False in both orders; missing, None, malformed string, zero and literal booleans; explicit Unsupported/revoked support; all runtime authority enum members; qualified indirect display positive control; literal True only when all independent grants are present; benign warning control; one revoked composite ingredient with changing magnitude; qualified sibling preservation; serializer and consumer exact parity. No raw exported action permission may be True while its declared scientific capability receipt denies that capability.

This batch should deliver both A-AUTH groups together. A point repair for a single spelling or one boolean path is insufficient. Keep earlier S12/S673/S81 and S653 closures as regression controls, all package FA rows open, and operational/hardware acceptance separate.


---

# Specialist appendix: Spatial validity

# Spatial validity review — d59c9bd

## Outcome

Three connected current boundary gaps are reproduced. They should be repaired as **one spatial-validity batch**, spanning conversion, uncertainty, alignment, transport and browser preflight; they are not reasons to restart the prior covariance-only review. These paths are unchanged Stage-3-adjacent code, so this report does not label them Stage 3 regressions. The missing-cell conversion defect was already deferred as Stage 5; the reproduced uncertainty consequence and identity-alignment/consumer asymmetry enlarge that work into a meaningful integrated delivery.

Fresh authored probes execute ten Python observation assertions and six TypeScript observation assertions, all reproduced. No repository tests or audit claims are used as correctness proof. No full engine, runner, provider, API, browser or hardware execution occurs. Engine methods and the aggregate block are extracted exactly from production AST; SIRE alignment and generation functions are called natively. The TypeScript probes copy exact pure function bodies to an isolated module, omitting imports and UI/runtime execution.

## SP-01 — Missing microzones become physical zero and zero uncertainty

**Priority:** P1 scientific integrity before wider pixel publication; previously known Stage-5 missingness defect with a freshly demonstrated concentration consequence.

`layer05_asmae/engine.py:3255–3305` sizes arrays from parsed IDs and initializes every state cell to `0.0`. A sparse 2×2 input containing only `mz_000_000` and `mz_001_001` therefore yields two missing cells with finite zero in all 13 mean maps and all 13 sigma maps. The same routine converts means and sigmas at lines 1903–1907. The exact aggregate block at lines 1932–1974 normalizes these invented zero sigmas into aggregate uncertainty `0.0`, then posterior concentration `1.0` at the missing location.

Positive controls preserve a legitimate physical zero at the supported top-left cell and retain the positive supported values. The missing-cell output is numerically indistinguishable from the physical-zero control. Two auxiliary boundary checks demonstrate that all-malformed IDs return thirteen `[[0.0]]` maps and a negative row/column ID can overwrite a valid cell through Python negative indexing. These auxiliary checks are malformed authored carriers, not evidence that the normal graph producer emits invalid IDs. The standard graph builder emits a complete rectangular lattice; sparse/recovery/partial input occurrence in normal execution was not established here.

`_microzone_scalar_to_grid` at lines 1801–1841 repeats zero initialization and converts explicit None to zero for support diagnostics. This belongs to the same fix rather than a separate ticket.

**Repair:** Use the canonical graph grid dimensions and explicit valid/support mask; validate IDs and bounds; initialize unassigned cells to null/nodata, not zero; use identical shape/validity contracts for mean, sigma and scalar support products. Aggregate concentration must be unavailable where eligible uncertainty support is absent. Do not interpret missing uncertainty as a zero-width posterior. Reject/diagnose malformed IDs before indexing and avoid shrinking shape to the last observed ID.

## SP-02 — Same-grid fast path bypasses nodata normalization

**Priority:** P2 current normalization inconsistency; independent of new phenology/memory registration.

`layer10_sire/surfaces/asmae.py:540–565` returns original rows when source and target shapes/CRS/affine match. Source nodata replacement at lines 567–574 occurs only after that early return. Native alignment of `[[0.0,-9999.0],[0.0,0.0]]` with `nodata=-9999.0` therefore retains the sentinel on the identity path. A legitimate nearest-neighbor resample of the same source to a 2×3 target removes the sentinel to None. Physical zero survives both controls.

The native generator reproduces a downstream consequence: the identity-aligned sentinel fixture is classified `RASTER_GROUNDED`, while a real all-zero control is `UNIFORM` (`flat_vals`/grounding at lines 1764–1776). Thus the nodata value can create apparent spatial variation; this is more than a serializer formatting difference. The probe does not claim that the full runner subsequently authorizes an actual browser overlay or that current providers routinely emit this sentinel. Explicit nodata is a supported source-grid field, and the resampling branch already establishes the intended normalization.

**Repair:** Normalize numerical validity and explicit nodata before any identity return. Preserve true zero; reject or mask non-finite/boolean/malformed raster scalars. Make identity, same-CRS resampling and cross-CRS reprojection obey one validity policy. Derive grounding, coverage and statistics only from valid cells. Align data and validity together and retain both source and display grid identity.

## SP-03 — Browser preflight does not bind geometry or masks strongly enough

**Priority:** P2 current defense gap; not a claim that malformed surfaces passed the backend.

Exact pure function bodies from `src/lib/agribrain/render-materialization.ts:109–183` reproduce these acceptance results:

| Controlled input | Result |
|---|---|
| Complete valid geographic 2×2 control | `grid_valid` |
| Metric EPSG:32631 bounds `[500000,4000000,500020,4000020]` | `grid_valid`; no display-CRS qualification |
| Numeric 2×2 array with metadata dimensions 99×99 | `grid_valid` |
| All-null values and all-false explicit valid mask | `grid_valid` |
| Mask with matching bounds/CRS/shape but contradictory affine origin | `canMaterializeMask=True` |
| Ragged numeric array | Correctly rejected |

`validateSurfaceGrid` checks rectangular values and finite ascending bounds, but ignores CRS, declared dimensions, transform consistency and validity. `canMaterializeMask` compares CRS and bounds/array size but not affine/grid identity. `plotGeoJson` is not used by the extracted validation function. These results are preflight outputs only, not actual rendering or an exploit claim. Upstream SIRE affine validation already rejects many malformed source/target contracts; the browser should preserve that proof rather than accepting a weaker carrier.

**Repair:** Validate the published display grid contract, not just its bounds: known geographic display CRS, dimensions equal to numeric array, finite affine coherent with bounds, validity/support mask shape, at least one supported finite display cell, and a matching immutable grid identity. Require exact matching grid identity/affine for masks; explicit reprojection/resampling must generate a new, qualified target mask. Preserve uniform physical-zero controls.

## Integrated batch — spatial validity from engine to consumer

Complete these steps in one branch/delivery, with parallel owners and one integration owner:

1. Define one canonical raster validity representation: values, valid mask, support mask, optional nodata encoding, per-state uncertainty, source/display grid identity, supported fraction and reason codes.
2. Update both microzone converters and aggregate uncertainty/concentration together. Validate canonical shape/IDs; preserve physical zero and unknown coverage.
3. Carry validity through Layer-1 adapter and Layer-10 `adapt_l1`. Replace `~np.isnan` observedness with finite qualified support and intersect explicit masks. Keep native scientific arrays on their source grid; never IDW-fill unknown ASMAE support as new observation.
4. Normalize nodata before the SIRE identity fast path and bind values/masks across all alignment methods. Derive grounding and valid statistics from the mask, not mere non-None values.
5. Coordinate cache roundtrip mask preservation with the export lane's dedicated reproduction; no duplicate finding is counted here. Test null/nodata/explicit masks through persistence, reintegration and terminal serialization.
6. Strengthen browser preflight and mask attachment to preserve grid identity, supported-cell availability and authoritative geometry. Attach explicit blocked reasons, while keeping unsupported states in the structural inventory.
7. Then deliver the expert selector and GIS products against this stable contract, rather than building several incompatible mask conventions first.

### Acceptance matrix for the whole batch

- All 13 means and all 13 uncertainties share one canonical shape and validity mask; a two-hole lattice remains two holes after conversion, cache, L1 transport, SIRE and frontend receipt.
- A genuine zero remains valid and numerically unchanged at every boundary.
- Missing sigma never yields concentration 1.0; unsupported aggregate concentration remains unavailable with a reason.
- Malformed, duplicate, negative or out-of-range IDs do not assign any state; valid siblings retain their correct cells.
- Identity alignment, resampling and reprojection remove the same nodata sentinel and retain valid zeros.
- Pure nodata cannot manufacture `RASTER_GROUNDED` variation or valid coverage; legitimate nonuniform supported controls retain grounded display.
- Declared/actual dimension mismatch, incoherent affine, wrong display CRS, empty support and mismatched mask identity reject preflight with precise reasons.
- A native source grid and correctly reprojected display grid retain distinct, immutable identities; browser masks reference the display identity actually rendered.

### Governing scientific intent

This batch serves R3 AB-L10-001 (qualified projection retaining masks, geometry, resolution and authority), AB-ARC-006 (bounded degradation), and AB-ASM-016 (local uncertainty and validity). It is a bounded F38/T11/T09 spatial publication slice; no package FA milestone is closed. The broader per-variable observability/calibration requirements remain F36 work.

## Evidence and limits

`probes.py` calls native SIRE alignment/generation and exact extracted engine code; `frontend-probes.mjs` executes exact extracted pure TypeScript bodies. `results.json` and `frontend-results.json` contain controlled numerical inputs/outputs and source identities. The offline controls establish boundary behavior, not normal provider incidence or an end-to-end field execution. All findings are current inherited gaps; no a31 overflow or covariance closure is reopened.


---

# Specialist appendix: Persistence and scientific export

## Persistence and scientific export: connected review

Snapshot: `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`. Fresh offline native probes: **12 observation assertions, all reproduced**. No production modifications, full runner, provider, API, browser or hardware execution. Repository tests/audits are not used as correctness proof. Real Rasterio/GDAL is absent; the generic-reader finding uses the exact production method with an inert dataset and is explicitly not a file roundtrip.

### Findings and distinction from deferred features

| Local ID | Priority / disposition | Concrete current boundary | Reproduction / positive control |
|---|---|---|---|
| EX-DUR | P2, current transaction-integrity/availability defect | An existing ASMAE JSON/NPZ commit is damaged by a failed replacement transaction | First native cache save/read succeeds. On changed values, an injected JSON commit failure returns False; old JSON bytes remain, but the old NPZ has already been overwritten. Subsequent read rejects the old committed generation. Checksum validation correctly fails closed: this is loss of the last committed cache, not acceptance of mixed values. |
| EX-MASK | P2, accepted masked-input integrity defect | Saving `numpy.ma.MaskedArray` strips its mask through `np.asarray` | Source masked cell with stored payload 77 returns as valid 77 after native full-cache save/load. Legitimate physical zero remains zero. An explicit NaN alternative returns None correctly. Actual field frequency of masked-array input is unestablished; the cache accepts this input type while the stable hasher explicitly distinguishes masked arrays. |
| EX-RECEIPT | P2, current compatibility-export contract loss | `RasterEntry` drops scientific fields retained by the canonical surface serializer | A qualified authored SurfaceArtifact preserves CRS grid, confidence, uncertainty, observed/inferred masks, provenance, two explicit False permissions and revocation reasons through the canonical serializer. `export_raster_pack` retains values/IDs/basic styles but omits all nine tested fields. Values, physical zero, None and valid-pixel count remain correct. The production runner invokes this exporter and the orchestrator forwards raster_pack. No downstream privilege escalation or frontend bypass is established. |
| EX-GIS | P2 prerequisite helper defect; do not characterize as a deployed thirteen-state GIS failure | Generic Rasterio reader unconditionally multiplies resolution by 111320 and returns nodata as a numeric value; generic writer omits nodata declaration | Native read method supplied an inert projected 10 m dataset reports 1,113,200 m and returns -9999 as a valid numeric cell; physical zero and affine remain preserved. AST inspection confirms the writer supplies no nodata option. No real GeoTIFF write/reader roundtrip occurred. |

**Deferred target, not another regression:** an integrated per-state ASMAE/SIRE GeoTIFF/COG publisher, scientific download route and browser receipts remain Stage 6. Generic writing support is not an integrated thirteen-state publisher, and `driver='GTiff'` plus DEFLATE does not by itself establish COG compliance. The scanned backend has writer definitions but no direct `write_raster` call sites in the selected source. Fix EX-GIS before reusing that helper in Stage 6; this review does not claim it currently corrupts the live ASMAE map path.

### Production evidence

- `layer05_asmae/cache.py:508–533`: fixed per-cache-key NPZ path; direct `np.asarray(grid)`; replaces the artifact in place.
- `layer05_asmae/cache.py:683–717`: write the new raster before the final JSON publication. A failed JSON commit has no previous-artifact rollback or generation-specific reference.
- `layer05_asmae/cache.py:142–157`: stable hashing explicitly represents masked array data and mask, whereas the persistence writer discards the mask.
- `layer10_sire/products/export.py:18–30,58–94`: the compatibility entry schema/export omits scientific receipt fields.
- `layer10_sire/surface_contract.py:172–283`: the canonical serializer preserves those fields and restrictive permission parity.
- `layer10_sire/runner.py:3646–3654`: active export invocation; exceptions are silently nonfatal. `orchestrator_v2/run_schema.py:265` forwards raster_pack in the canonical run response. Presence of canonical surfaces elsewhere does not restore the dropped receipt to each standalone raster entry.
- `layer1_fusion/raster_backend.py:259–271,275–290`: writer omission and CRS-blind resolution conversion; reader does not request a masked read or convert nodata to None.

Hashes for all seven cited production modules are recorded in `results.json`. `probes.py` executes full native cache writer/reader in a temporary directory scoped to this lane, native canonical/compatibility export, and the exact generic reader with inert data. No provider/device activity occurs. Tampering control verifies valid artifact hashes reject changed bytes.

### One larger implementation delivery: scientific raster artifacts, not four micro-patches

Bundle these corrections with Stage 5/6 persistence work in one integration branch, with three parallel code workstreams and one shared acceptance matrix:

1. **Durable, mask-preserving storage.** Define canonical value/uncertainty/confidence/validity arrays and normalize masked-array input deliberately. Preserve physical zeros; serialize unknown cells as validity false and/or stable nodata. Use immutable content- or generation-addressed NPZ artifacts, write and fsync new artifact first, then atomically switch the JSON manifest. Never overwrite a currently referenced NPZ before publishing its replacement. Garbage collection must only remove unreferenced generations. Audit the equivalent L10 JSON/NPZ cache mechanism, which uses same-key replacement and deletes final paths after failure, within this same delivery rather than another later patch.
2. **One scientific receipt for every export projection.** Derive compatibility raster entries from the canonical serializer or share a typed scientific metadata block. Preserve schema/version, immutable surface ID, canonical state, grid/CRS/transform, units, effective/native/display resolution, uncertainty/confidence, validity and epistemic masks, provenance, authority restrictions and artifact checksums. Retain legacy style/shape aliases so the existing UI continues to work. Never interpret field absence as broader permission.
3. **GIS publication and retrieval.** Fix projected/geographic resolution handling and grid shape validation; honor `grid.nodata`, preserve source nodata on read, and define either dedicated state/uncertainty/mask assets or documented multi-band layouts. Produce actual COGs with a validated COG creation path and overviews, immutable refs/checksums and a manifest record per state. Only eligible supported spatial states receive files; all thirteen states receive availability entries, including explicit unsupported/unavailable reasons. Connect authenticated scoped download/retrieval to immutable manifest refs rather than user filesystem paths. This last route is planned work, not an independently reproduced HTTP vulnerability.

### Acceptance matrix for the complete delivery

- Every registered state: mean, uncertainty, confidence and validity survive NPZ → canonical JSON → compatibility export with identical grid support; physical zeros and masked cells remain distinct.
- MaskedArray, plain arrays with None, and explicit NaN inputs normalize consistently; a masked hidden sentinel never returns as a measurement.
- Inject failure before/after artifact write, before/after JSON commit, and during directory fsync. The last committed generation stays readable; a failed candidate is not published. Add a real two-process retry/reader scenario under the same immutable identity rules.
- Replace/tamper bytes or member names and reject the artifact; normal non-tampered roundtrip remains available.
- Restrictive permissions and revocation reasons are identical in canonical surfaces, raster_pack, cached forms, exported manifest and download metadata. This verifies parity, not authorization inferred from confidence.
- Real GDAL file tests in geographic and projected CRS, partial plot masks, unequal pixel sizes, rotated transforms, native 0 values and explicit nodata. A projected 10 m grid remains 10 m after read. Data shape must agree with declared grid.
- Validate actual COG structure/range-read behavior, reprojected bounds, uncertainty assets, checksums and tenant/plot/version lookup. No production or field publication is implied until that evidence exists.

### Plan / scientific ownership

AB-ARC-007 (atomic publication), AB-ARC-006 (bounded degradation), AB-L10-001 (qualified spatial projection), and AB-ARC-005 (authority parity) govern these boundaries. Primary package ownership is F38/T11 for durability and degraded publication, T09 for user-facing scientific projection, with F36 preserving per-variable support semantics. This delivery does not close those full packages. Stage 3 registration can be judged on its own scope; the export findings are predominantly inherited current gaps and Stage 5/6 prerequisites. All FA milestones remain open.


---

# Specialist appendix: Consumer projection

# Frontend publication-consumer lane — d59c9bd

Pinned head: `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`. Scope: map hook, lens resolver, inventory, dock/sidebar, raster stack, legend helpers and the latest-surface API projection. Production source and Git were not modified. No repository tests, React/browser, DeckGL, provider or HTTP endpoint was executed.

## Decision

Stage 3 now puts all thirteen raw coordinates into the frontend's known inventory and raster-stack mode/color dictionaries. Both new products have exact legend entries. That is real progress, but structural recognition does not provide independent scientific selection. The next frontend work should be delivered as **one complete catalog-to-expert-selection slice**, including metadata/availability semantics, rather than adding one selector field and repairing each downstream mismatch separately.

Fresh execution comprises eighteen observation assertions using the actual pure TypeScript selection resolver and actual JavaScript legend module, plus exact isolated source fragments for the hook inverse function, inventory function and dock resolution label. All eighteen observations reproduce. A zero exit means these stated observations—including remaining limitations—reproduce; it is not a universal pass verdict.

## Findings and reachability

### FE-01 — P2: dock claims 10 m evidence independently of committed resolution

`src/components/farm/intelligence/MapLayerDock.tsx:101–115` creates currentSourceInfo from a hardcoded conditional at line 106. Any nonexperimental selected surface receives `evidence basis 10m`. An experimental surface receives `visual 2.5m / evidence basis 10m`. The expression does not read native, display or effective resolution from the selected surface.

Exact-expression probes with an ASMAE root-zone product carrying effective resolution 1,000 m and a phenology product carrying 30 m both emit `evidence basis 10m`; a genuine 10 m NDVI control emits the same label. This is a current display-contract defect, inherited rather than introduced by the two Stage 3 product definitions. It can overstate spatial precision by a factor of 100 for the authored coarse-root-zone fixture. The probe does not establish a particular real plot's effective resolution.

Repair the dock with committed selected-surface native/display/effective resolution and explicit unknown support. The backend must supply the real support footprint; frontend grid pixel size alone must not become scientific resolving power. Keep optical, subsurface inferred and temporal model coordinates separately qualified.

### FE-02 — Deferred Stage 4 capability: thirteen recognized products are not thirteen selectable coordinates

The inventory now contains 35 known types, including all thirteen canonical ASMAE raw products (`plot-map-evidence-state.ts:1165–1180`). The stack maps all thirteen (`buildLayerStack.ts:415–427,455–467`). Nevertheless, `getPriorityList` in `source-policy-display-resolver.ts:313–435` supplies fixed broad-lens candidates. In authored positive-authorization fixtures, only raw `ASMAE_VIGOR` occurs in any existing lens priority, via vegetation attention. Neither phenology nor memory is selected through any of the eight nonredundant lens modes.

A direct-priority control selects every one of the thirteen through the same actual authorization resolver, proving the immediate limitation is candidate selection rather than a thirteen-layer transport limit. This is the explicitly deferred expert-selector capability; it should not be reported as an introduced Stage 3 regression or as evidence that all thirteen are rejected downstream.

The dock still exposes six base lenses and nine overlays (`MapLayerDock.tsx:68–89`). RawDataSidebar's raw tab is a source-data table, not a per-state scientific product picker. Preserve those farmer views and add an independent expert state selection keyed by immutable product identity.

### FE-03 — P2 readiness group: inverse routing and legend semantics remain duplicated

The stack has explicit per-product mode mappings, but hook `modeFromSurfaceType` uses substring matching (`useLayer10.ts:451–462`). `WATER_ASMAE_CANOPY_WATER` matches CANOPY before WATER and returns `canopy`; the root-water control returns `water_stress`. New raw phenology and stress-memory products return an empty inverse mode despite explicit stack mappings. Most raw states have the same mismatch.

Reachability qualification: the current hook uses this inverse only in `getExperimentalSurfaceType` after its known-active-mode mapping (`477–483`). The normal known-mode path can mask the defect. It is a reproduced inverse-contract inconsistency, not proof of a current water-map outage. It should be resolved before expert state selection starts supplying raw products.

The same duplicated metadata affects legends. `resolveCommittedSurfaceLegend` has an exact entry for the chlorophyll alias but no exact entry for raw `ASMAE_CHLOROPHYLL`. With the production nutrient-lens fallback, the raw state receives `highLabel: Deficient` while the alias receives `highLabel: High chlorophyll`. For a small or unstretched grid, SurfaceLegendBar does not replace these words with field-relative labels (`SurfaceLegendBar.tsx:233–243`). The positive controls for the two new states correctly show maturity and stress-memory labels.

Reachability qualification: raw chlorophyll currently lacks normal lens selection. This is a directly executed interpretation defect at the helper boundary and an expert-selector integration hazard, not an observed current browser display. Complete exact per-state labels/direction/units/palettes at the same time as direct selection; do not expose raw state selection first and patch incorrect labels afterward.

### FE-04 — P2 local-diagnostic correctness: ASMAE missing-reason fallback blames L5

The newly added raw product entries and the preceding eleven all map to `L5` in local SURFACE_ENGINE_MAP (`plot-map-evidence-state.ts:1218–1231`). With no surface, L5 OFFLINE and an ASMAE OK engine carrier, the exact inventory function claims `Engine L5 is offline — cannot generate ASMAE PHENOLOGY PROGRESS` and the corresponding memory reason. These states are ASMAE Layer 0.5 products; this is not their canonical producer identity.

The hook merges authoritative backend inventory over local entries (`useLayer10.ts:2222–2241`). Therefore this erroneous reason is relevant to local fallback/missing backend entries; it does not prove the final inventory always shows that message. Correct the producer identity and preserve backend machine block reasons rather than inferring causal availability from unrelated engine health.

The same local inventory labels an authored MODEL_ASSISTED_RASTER surface `available_raster` despite unsupported/revoked metadata. The authorization resolver remains separate and deny-by-default. Treat inventory presence, scientific support, authorization, and committed rendering as distinct statuses; this is **not** a demonstrated render-authorization bypass.

## API and permission boundary retained

`src/app/api/agribrain/surfaces/latest/route.ts` forwards the validated Python canonical frontend payload, including inventory and authorization fields, rather than manufacturing thirteen product values. It rejects corrupt/stale heads and falls back to worker-state generation information, not a Prisma scientific head. This lane did not execute the authenticated route or establish end-to-end publication availability.

The pure resolver's explicit-priority positive controls show that typed, authorized raw products can already traverse its low-level candidate loop. Do not replace that permission boundary with unconditional expert rendering. Unsupported states must stay visible as unavailable/diagnostic inventory entries without becoming pixel-authorized or prescription-capable.

## One coherent implementation batch: canonical expert-map consumer slice

1. Define a consumer-facing product catalog shared/generated from canonical backend state identity: product ID, state coordinate, units, range, palette, quantitative direction, farmer lens association, producer, uncertainty/support fields, allowed role and availability reasons.
2. Add selectedScientificProduct state independent of broad farmer activeMode. Route raw product identity directly through the existing authorization/materialization contract; keep lenses and overlays compatible.
3. Replace inverse substring matching and duplicated type/color lists with catalog lookup. Cover all thirteen plus existing aliases. Do not route phenology through vigor simply because both use a canopy palette.
4. Render exact labels and native/display/effective resolution from the committed surface and proof. Show unknown as unknown. Preserve physical zero and distinguish sigma, confidence and support coverage.
5. Merge availability monotonically: backend denial/revocation/reason wins; local missing producer or type presence cannot grant support, authority or rendering. Expose registration, support, authorization and materialization separately in the expert list.
6. Verify the full slice once: thirteen positive controls, thirteen unavailable controls, canopy/root simultaneous selection, malformed-vigor valid-chlorophyll survival, missing surface reasons, exact publication receipt identity, palette/legend parity and optical/coarse-support resolution examples.

Acceptance should include actual browser receipts after implementation; the present pure-module checks do not substitute for them. The slice can be implemented alongside backend publication/mask work with stable catalog and permission interfaces, reducing serial repair-review cycles.

## Reproduction

Run `node review-wide-d59c9bd/frontend/probes.mjs` from the reconstructed pinned workspace. Node 24 with TypeScript stripping support was used. Source receipts include nine verified files, exact Git blobs and SHA-256 digests. The script records 13 selection rows, inverse controls, legend results, resolution examples, missing-reason and local-inventory qualification, plus eighteen assertion outcomes. All 52 package FA milestones remain open.

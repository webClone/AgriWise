# ASMAE integrated repair batches — d59c9bd

24 October 2026. Baseline `d59c9bdc85a64469a9424d4c7757a2d2c4da3041`. Companion to the six-lane deep audit. This is an implementation-ready plan; no production changes or merge are performed by the review.

## Delivery strategy

The next unit of work is the **complete thirteen-state publication vertical slice**, organized into three substantial PRs/commit streams. It is larger than another isolated Stage 3 residual patch, while remaining bounded to scientific publication rather than reopening all AgriBrain modules.

| Delivery | Scope | Root groups | Can start | Completion means |
|---|---|---|---|---|
| A — Scientific publication contract | Per-state update/support receipt, typed capabilities/restrictions, catalog/domain/availability convergence | WB01–WB03 | Immediately on reviewed baseline | All thirteen products tell the same scientific/support story from analysis receipt to publication metadata |
| B — Spatial artifacts and durable publication | Validity/uncertainty, alignment and grid identity, mask-preserving cache, immutable generation commit, compatibility receipt | WB04–WB05 | Parallel with A after agreeing shared field schema | Unknown pixels remain unknown, and committed artifacts remain readable across failed retries |
| C — Expert consumer and GIS delivery | Independent state selection, exact interpretation/resolution, availability UX, scientific GeoTIFF/COG publication and retrieval | WB06 + deferred Stages 4/6 | UI/export scaffolding against frozen A/B fixtures; final integration after A/B | Thirteen products independently inspectable, only eligible maps rendered/exported, reasons explicit for every unavailable product |

Do not open a PR per subfinding. A/B/C are reviewable deliveries. Use one integration owner to combine them into a working publication release; keep normal diagnostic inspection available while unsupported products retain explicit restrictions.

## 0. Agree and freeze the shared interfaces

One short initial contract change must specify:

- Product identity: schema version, canonical state, dedicated type, source/producer, scientific unit and admissible domain, display range and legend direction.
- State support: observation/source identity and reality; measured variable; indirect/proxy/model/hypothesis relationship; positive spatial support; numerical/covariance influence; descriptor/runtime ceiling; exclusions and reason codes.
- Capability vector: inspect, diagnostic display, scouting/statistics, state update, training export, prescription use and execution remain separate typed permissions. Missing/malformed action permission never becomes True through truthiness.
- Raster receipt: source grid and display grid identity, CRS/affine/dimensions, values, validity/support mask, uncertainty/confidence, supported fraction, native/display/effective resolution, provenance and restrictions.
- Availability: registered, materialized, qualified plot-state artifact, valid pixel support, scientific eligibility, render authorization and export eligibility are distinct. Every one of thirteen products always has an inventory entry.
- Artifact reference: immutable generation/content identity, checksums, per-state assets, committed manifest, schema/version and scope.

Choose canonical field spellings and supported legacy aliases. Normalize aliases once at admission. Restriction union and permission intersection must be monotone: benign warnings, missing fields or sibling evidence cannot erase a denial. Generate frontend types/catalog from the same versioned source or enforce machine-checked parity.

## A. Scientific publication contract

### A1 — Repair observation-to-state semantics end to end

Targets: `layer05_asmae/assimilation/filter.py`, `observation/index_state_mapping.py`, `observation/pixel_extraction.py`, `state/descriptors.py`, `feature_export.py`, `scientific_contracts/state_support.py`, `ledger_adapter.py`, `layer10_sire/surfaces/asmae.py`.

1. Emit per-state update receipts instead of one blanket direct-observation flag per accepted sensor report. A measured NDVI pixel is not a direct measurement of latent vigor, LAI or temporal stress memory.
2. Record localized valid support and per-target analysis/covariance/information behavior. No eligible H_t support means no accepted target. Zero gain/covariance cannot confer observation or field-approval status. Preserve legitimate uncertainty-only information when mean innovation is zero.
3. Explicitly reconcile stress-memory policy. Either keep it a forecast/decay accumulator without observation analysis, or authorize a documented derived constraint and update descriptors, operator semantics and validation together. Never label optical proxy history as a directly measured accumulator.
4. Carry genuine model/temporal transitions for phenology and memory, with qualified issuance/forcing provenance. Do not synthesize accepted observations to make their map gates pass.
5. Preserve direct/indirect/proxy counts, relationships, exclusions and nested numerical receipts losslessly. Define aggregation rather than silently substituting zero counts or unset summaries.
6. Derive feature-pack eligibility and SIRE support labels from the normalized receipt; keep operational authority separate. Scientific calibration and independent reference collection remain explicit F36 work.

### A2 — Apply one restriction/capability policy everywhere

Targets: scientific support/role normalization, native/alias builders, `surface_contract.py`, runner publication gates, terminal publication, compatibility consumers.

1. Parse typed booleans deliberately; preserve False and zero. Handle legacy string booleans by explicit documented conversion or reject them with diagnostics. Never call `bool('false')` for permissions.
2. Intersect descriptor capability ceiling, current per-state scientific support, runtime capability grant, current restrictions and source/product role. Historical accepted counts never override current denial.
3. Normalize all supported carrier spellings before raw construction; deduplicate restriction unions across object attributes, mappings and provenance. Specify which carrier is authoritative when metadata and ledger disagree.
4. Use the same result for constructor fields, canonical serializer, aliases, composites, manifest, cache and frontend receipts. Unsupported ingredients cannot affect qualified composite values.
5. Keep present denial-by-default render behavior; do not bypass it to demonstrate thirteen visible maps.

### A3 — Make the thirteen-state catalog operational

Targets: `state_schema_ref.py`, generator metadata maps, `layer10_sire/invariants.py`, `products/manifest.py`, runner inventories and `terminal_publication.py`.

1. Make a canonical product specification drive all thirteen domain checks, units, modes, range/legend tables and producer identity. Separate scientific admissible domain from display range where they differ.
2. Complete LAI legend coverage through its supported domain; make all thirteen finite/nonboolean/domain boundaries table-derived. Do not silently clamp corrupt scientific values to pass display validation.
3. Replace object-presence availability with a shared availability receipt. All-None metadata-only surface is not a plot estimate; require an actual separately referenced scalar/plot-state artifact for plot-level availability.
4. Make successful, partial, unavailable and terminal publications share the same inventory builder and reasons. Model-propagated temporal states must retain genuine model identity without falsely becoming Observed.
5. Include small related schema maintenance such as resolving annotation names in the same delivery when supported by real introspection consumers; do not start another residual-only review cycle for it.

### A acceptance gate

One integrated native extraction→analysis→ledger→normalization→feature-pack→raw/alias/inventory matrix covers every state. Required controls: direct physical measurement versus indirect index; zero H_t; constant zero-gain target; valid varying target; valid uncertainty-only update; temporal propagation; genuine prior versus absent proof; all restriction carriers/aliases; typed False/string/malformed/missing permissions; all thirteen domain limits; LAI 7–7.8; no raster/no scalar; separate scalar-only artifact; malformed vigor with qualified chlorophyll sibling. Counts, labels, eligibility and restrictions must agree at every boundary.

## B. Spatial artifacts and durable publication

### B1 — Carry missingness and uncertainty on one grid

Targets: both microzone converters and uncertainty aggregation in `layer05_asmae/engine.py`, L1 reintegration/ASMAE adapter, SIRE L1 adapter, ASMAE alignment/grounding, `render-materialization.ts`.

1. Use canonical graph grid shape and validated zone positions. Reject or diagnose malformed, negative, duplicate and out-of-range IDs before indexing.
2. Represent unassigned mean and sigma cells with explicit validity/nodata, preserving legitimate supported zero. Scalar support diagnostics use the same mask.
3. Compute concentration/statistics/grounding only where valid uncertainty/support exists. Missing sigma must never imply uncertainty zero or concentration one.
4. Normalize nodata before every alignment branch, including identity fast paths. Carry values and masks together across same-CRS resampling and reprojection.
5. Preserve native scientific grid separately from display grid. Bind masks to exact target affine/grid identity; do not infer scientific resolution from pixel size.
6. Strengthen browser preflight for display CRS, actual versus declared dimensions, affine/bounds coherence, finite supported cells and exact mask identity. Do not reject a valid uniform physical-zero map merely because it is uniform; let the scientific display policy decide its permitted form.

### B2 — Make artifact replacement transactional and mask preserving

Targets: `layer05_asmae/cache.py`, equivalent L10 JSON/NPZ cache, artifact reference/manifest code.

1. Normalize accepted plain, masked and explicit-nodata arrays into one stable representation. Retain masks in hashing and persistence, not hashing alone.
2. Write immutable content/generation-addressed arrays. Verify all members/checksums, flush new files, then atomically publish one JSON manifest/reference. Never overwrite an artifact referenced by the current committed manifest before the replacement commits.
3. Idempotent same-content retries return the same verified generation; conflicting/different candidate content cannot mutate an already committed artifact in place.
4. Failed publication leaves the previous manifest and all of its artifacts readable. Garbage collection removes only unreferenced generations. Apply the same rule to the equivalent L10 mechanism within this batch.
5. Verify concurrent readers/two-process writers, interruption points and retry identity using offline filesystem fixtures.

### B3 — Preserve the scientific receipt in every projection

Targets: `layer10_sire/products/export.py`, `surface_contract.py`, terminal publication, orchestrator run response.

Derive compatibility raster entries from the canonical metadata block. Preserve canonical state and immutable ID, units, grid/CRS/affine, masks, confidence/uncertainty, native/display/effective resolution, provenance, restrictions and explicit False permissions. Retain legacy styling aliases for existing consumers. Do not allow metadata omission to broaden action or render eligibility.

### B acceptance gate

All thirteen means/uncertainties share shape and mask through conversion→cache→L1→SIRE→canonical/compatibility serialization→frontend preflight. Two lattice holes remain holes; true zero remains zero; missing sigma remains unavailable; identity and resampling normalize the same sentinel. Masked hidden 77 must never reappear as measured 77. Inject failures around artifact write/manifest switch/fsync and verify old generation readability. Tampered bytes reject; ordinary roundtrip succeeds. Wrong CRS/dimensions/affine/mask and empty support produce exact block reasons; valid transformed grids pass.

## C. Expert consumer and GIS delivery

### C1 — Deliver the full expert map experience, not just a picker

Targets: `useLayer10.ts`, `source-policy-display-resolver.ts`, `plot-map-evidence-state.ts`, `buildLayerStack.ts`, `surface-legend-meta.mjs`, `MapLayerDock.tsx`, `RawDataSidebar.tsx`, latest-surface API projection.

1. Add selected scientific product identity independently of farmer broad-lens mode. Keep farmer lenses/overlays intact.
2. Present all thirteen products with registered/materialized/support/authorized states and exact reasons; unavailable entries remain inspectable without fabricated pixel maps.
3. Resolve explicit product identity through existing authorization/materialization. Canopy water and root-zone water must be independently selectable even when both exist.
4. Replace substring inverse routing, duplicated type lists and producer inference with catalog lookup.
5. Provide exact per-state quantitative labels, units, direction, legend range and uncertainty/support explanation. Do not reuse nutrient-deficiency wording for raw chlorophyll.
6. Display committed native/display/effective resolution; unknown remains unknown. Remove hardcoded 10 m claims and L5-based ASMAE failure attribution.
7. Merge authoritative availability/restrictions monotonically. Local object presence or UI mode cannot create scientific support or rendering authority.

### C2 — Complete scientific GIS export and retrieval

Targets: generic raster backend, per-state artifact publisher/export manifest and scoped retrieval route.

1. Fix projected/geographic resolution handling and nodata/shape contracts before using the generic helper. Real Rasterio/GDAL file tests are required; the audit's inert dataset proof is not a file acceptance test.
2. Define per-state mean, uncertainty/confidence and validity assets or a documented multiband layout; preserve units/CRS/affine/support/provenance/authority and immutable checksums.
3. Produce and validate actual COG structure/overviews/range-read behavior. GTiff plus compression alone is not COG certification.
4. Publish files only for eligible scientific rasters, while retaining availability entries for all thirteen states.
5. Resolve downloads through scoped committed manifest references and immutable identities; do not expose arbitrary filesystem paths. This is planned route design, not an audit claim of an existing HTTP vulnerability.

### C acceptance gate

A real browser fixture demonstrates all thirteen entries, independent qualified selection, exact blocked reasons, unchanged farmer views, correct coarse-resolution labels and semantic legends, no revoked value influence, and generation-consistent API/UI receipts. Real geographic/projected GeoTIFF/COG roundtrips preserve masks/zeros/uncertainty and checksums; a projected 10 m grid stays 10 m. A real plot/provider execution should then be reviewed separately for evidence availability, without field actuation. Where references are absent, the product remains inferred/hypothesis/unavailable under its justified role.

## Ownership and parallel execution

Use six implementation roles: scientific producer/ledger, product/permission contract, grid/validity, cache/export, frontend/GIS consumer, and integration/review. Each has an isolated worktree and explicit file ownership. Shared hotspots (`surfaces/asmae.py`, runner, state registry, surface contract) have one owner; other roles supply focused patches rather than concurrently editing shared files. Agree schema first, then run A and B in parallel; C builds against committed fixtures and integrates once their receipts stabilize.

One acceptance gate per delivery; one combined relevant regression gate at integration. Run narrow probes during implementation, not the entire long suite after every line change. Reuse frozen previous covariance/overflow controls unless those modules or semantics change. Failures become additions to the current batch matrix, not automatically a new audit/PR cycle. Freeze the reviewed SHA and record later changes explicitly rather than restarting on a moving branch head.

## Completion and non-goals

This delivery makes thirteen products scientifically consistent and inspectable; it does not guarantee thirteen valid spatial maps for every plot. No missing salinity evidence, independent root-zone measurement or biotic truth is manufactured. Field calibration and per-variable/horizon evidence remain F36 requirements. Complete package FA acceptance is separate; all52 remain open until their full criteria are demonstrated. World-model/Omega exploratory work can proceed under objective-specific evidence eligibility, without waiting for unrelated UI polish or claiming these publication fixes establish model skill.

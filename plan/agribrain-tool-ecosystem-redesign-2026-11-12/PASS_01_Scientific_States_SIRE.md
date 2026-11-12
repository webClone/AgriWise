# Pass 01 — Scientific foundation, 13 states, fusion, SIRE
**Evidence:** `services/agribrain/scientific_contracts/contracts_v2.py`; `scientific_contracts/state_schema_ref.py`; `layer05_asmae/state/descriptors.py`; `layer05_asmae/history/event_detector.py`; `layer05_asmae/retrovalidation/event_retrovalidation.py`; `layer10_sire/schema.py`; `layer10_sire/zones/extractor.py`; `layer10_sire/temporal_bundle.py`; `layer10_sire/products/manifest.py`; `layer10_sire/histograms/compare.py`.
## Directly derived tool opportunities
1. **13-State Explorer**: canonical vigor, LAI, chlorophyll, canopy water, root-zone water, surface wetness event, structure, bare soil fraction, salinity stress, thermal stress, biotic confounder risk, phenology progress, stress memory. A state is a posterior coordinate, not necessarily a raster. Show value/sigma/identifiability/authority/availability, plus an authorized map if present.
2. **Scientific Layer Catalog**: all `SurfaceType` products across vegetation, water, nutrients, disease, yield, suitability, risk, uncertainty, temporal trends and action readiness. Do not equate enum registration with produced pixel values.
3. **Zone Laboratory**: selecting a zone highlights its actual polygon, source surface, severity, source confidence, uncertainty, historical changes and adjacent sensors. Layer10 extraction includes thresholds, support filtering, minimum confidence and overlap deconfliction; never invent a boundary from a mean-only result.
4. **Evidence & Fusion Inspector**: trace `EvidenceRef` (ownership, observed time, knowledge time, spatial support, roles, lineage) to `StateRef`, to diagnostic, to publisher. Show why an observation could or could not update ASMAE.
5. **Uncertainty & Identifiability Studio**: sigma maps, posterior concentration, source dominance, disagreement, data gaps and validation masks; covariance/correlation only when an actual compatible matrix exists.
6. **Temporal Time-Peel / Event Replay**: Layer10 TemporalBundle covers historical slices, T0 and forecast; event detector emits dated irrigation/rain/drought/fertilization/deficiency/biotic hypotheses. Real observations, curve-fit and forecast must remain distinguishable by source and horizon.
7. **Scientific Comparative Analysis**: zone histograms, surface correlations, temporal deltas, native resolution, masks, render receipts and provenance exports.
## Important boundaries
- A scalar field posterior must be represented as plot-level insight, not painted into arbitrary heterogeneous pixels.
- NDVI is an observation, not latent state 14; S1 backscatter, photos, drone images are observation/evidence sources.
- A backend enum entry or an emitted unqualified raster does not establish source proof, publishability, or browser render authority.
- ASMAE memory/hypothesis states have different roles from physical measurement variables.
## Panel-map correlation contract
`select(stateKey, cellOrZone, snapshotId)` -> layer selector shows authorized state surface, side panel shows its uncertainty, evidence panel lists accepted proof, timeline filters related observations. If no authorized pixels, keep same selection and show a plot-level card with reason; no fake map gradient.
## Key acceptance tests
All 13 catalog rows visible in no-data, prior-only and full-data cases; selected state never switches to another due to broad Water/Canopy lens priority; pixel inspector/sigma/legend agree on snapshot and grid cell; invalid/stale numerical lineage fails closed; source update does not silently override historical comparison.

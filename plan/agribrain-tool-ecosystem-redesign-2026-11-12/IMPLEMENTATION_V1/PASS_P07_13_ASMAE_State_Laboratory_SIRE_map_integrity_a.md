# P07 — 13-ASMAE-State Laboratory, SIRE map integrity and scientific evidence workspace
**Status:** NOT STARTED · **Prerequisite:** P01,P03,P06 · **Primary:** A4+A3+A7 · **Independent:** A7+A6/A4 as appropriate  
**Future branch:** `feat/plot-workspace-p07-asmae-sire` (not created). 

## Goal, scientifically valid scope
Present all 13 canonical ASMAE coordinates as first-class interactive scientific states, with posterior, uncertainty, temporal support, provenance and only authorized spatial maps. Link science and map without inventing measurements or changing model internals.
## Target source files and new proposed modules
- `services/agribrain/layer05_asmae/config.py`
- `services/agribrain/layer05_asmae/state/descriptors.py`
- `services/agribrain/layer10_sire/schema.py`
- `services/agribrain/layer10_sire/surfaces/asmae.py`
- `services/agribrain/app/main.py`
- `src/hooks/useLayer10.ts`
- `src/lib/agribrain/layer10-request-state.mjs`
- `src/app/api/agribrain/surfaces/latest/route.ts`
- `src/components/farm/map/PlotMapShell.tsx`
- `src/components/farm/intelligence/ (existing)`
- `src/components/farm/workspace/AsmaeStateExplorer.tsx (proposed)`
## Implementation packages — in exact order
### P07.01 — Freeze 13-state catalog and coordinates
Pull from canonical backend state registry, verify ordering/units/semantics: vigor, LAI, chlorophyll, canopy_water, root_zone_water, surface_wetness_event, structure, bare_soil_fraction, salinity_stress, thermal_stress, biotic_confounder_risk, phenology_progress, stress_memory. Existing conventions determine UI names; never introduce a fourteenth latent state.

### P07.02 — Build per-state availability resolver
Each state gets status `qualified_raster`, `plot_posterior_only`, `prior_only`, `diagnostic_hypothesis`, `unidentifiable`, `missing`; explicit source and display reason. Surface enum registration cannot itself assert available spatial pixels.

### P07.03 — Build state selection and inspector
On selecting state, show posterior mean, sigma or covariance channel, spatial support, observation support, assimilation mode, observed/knowledge windows, run ID and uncertainty interpretation. If unsupported, show truthful no-map card.

### P07.04 — Preserve SIRE publication admission
Client requests exact snapshot ID and existing backend validator. Check node/publication/receipt/inventory/schema/contract/lineage/numerical and temporal rules per authoritative backend; never loosen fail-closed gates to make interface render.

### P07.05 — Bind map pixels to truth
Surface type/grid/CRS/mask/hash/geometry, legend values, raw value/sigma, hovered coordinate and browser rendering receipt share one immutable publication ID. No rendered interpretability based on cosmetic tint or stale fallback.

### P07.06 — Covariance and cross-state comparisons
If actual valid covariance exists, show 13x13 matrix with state ordering and units; otherwise disabled/unavailable with reason. Selection of two states or snapshots yields compatible comparison, never fabricated correlation.

### P07.07 — Evidence and support chain
Build link `sensor/drone/satellite candidate`→`Layer0 admitted`→`Layer1 evidence`→`ASMAE state update`→`published SIRE`→`browser render`. Distinguish nearby/temporally adjacent from independently validated source-to-state causal edge.

### P07.08 — Scientific timeline and pixel history
Load authorized historical snapshot, respect `first_available_at` and cutoff. Distinguish L1 historical rasters, L2 fitted curves, forecast scenario, and observed snapshots; do not backfill future evidence.

### P07.09 — Expert and farmer faces, same truth
Farmer mode simple state explanations and uncertainty labels; Expert mode full prior/posterior, matrices, innovation/calibration, source dominance, reconstruction and provenance; same publication and permission.

### P07.10 — Adversarial scientific qualification
Tamper hash/geometry, remove sigma, synthetic field spatial pattern, re-label prior-only state as raster, corrupt temporal identity, wrong published-at, forged source support; all denied from authoritative raster/causal claims.
## Release / adversarial gates
- **P07-G01** Exactly 13 state entries visible and in canonical frozen order under no-data and data states.
- **P07-G02** Unqualified scalar state never paints pseudo-raster.
- **P07-G03** A valid scientific pixel can be proved to exact published snapshot and authorized grid cell.
- **P07-G04** Hash/cutoff/inventory mismatch fails scientific map closed.
- **P07-G05** Posterior mean, sigma, units, and scientific source are coherent across panels.
- **P07-G06** Real browser `canRenderPixels` and render receipt match committed layer, not merely backend JSON.
- **P07-G07** A nearby but unadmitted sensor cannot appear as contributing to ASMAE.
- **P07-G08** Plot-only state usable for farmer and expert modes without falsifying geometry.
## Required pass artifacts
- 13-state per-state eligibility matrix and scientific card/view screenshots.
- Truth/proxy/forecast/simulation language audit, scientific lineage trace.
- API/test/browser positive+negative qualification including receipt signature.
- A4 scientific signoff and A6 source trust review.
**HOLD:** any state map fabricates subfield data, numerical binding omitted or source authority mislabeled.
## Multi-agent handoff
R0 pinned source baseline/negative fixtures → R1 author vs independently prepared design critique → R2 A4 scientific + A6 security and A3 geometry where applicable → R3 A7 adversarial fail-old/pass-new tests → R4 A2/A8 integrated actual-browser check for UI → R5 A0 SHA/test receipts/GO-HOLD and rollback.

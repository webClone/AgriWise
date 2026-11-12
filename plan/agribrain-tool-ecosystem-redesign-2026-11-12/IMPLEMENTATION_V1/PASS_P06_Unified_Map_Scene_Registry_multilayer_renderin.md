# P06 — Unified Map Scene Registry, multilayer rendering and spatial interaction parity
**Status:** NOT STARTED · **Prerequisite:** P03,P05 · **Primary:** A3+A2+A4 · **Independent:** A7+A6/A4 as appropriate  
**Future branch:** `feat/plot-workspace-p06-map-scene` (not created). 

## Goal, scientifically valid scope
Evolve the existing MapLibre/DeckGL map into one authoritative spatiotemporal scene that can illustrate zones, sensors, cameras, drone plans and tracks, MESIA receivers and qualified coverage, events, tasks, evidence and experiment geometry together with SIRE surfaces. Preserve pixel-proof rendering.
## Target source files and new proposed modules
- `src/components/farm/map/PlotMapShell.tsx`
- `src/components/farm/map/buildLayerStack.ts`
- `src/components/farm/map/layers/zones/UnifiedZoneLayer.ts`
- `src/components/farm/map/utils/buildPolygonMask.ts`
- `src/components/farm/map/sceneProviders.ts`
- `src/components/farm/map/PlotScientificLegend.tsx`
- `src/hooks/useLayer10.ts`
- `src/components/farm/map/workspaceLayers/ (proposed)`
- `src/components/farm/map/MapEntityPicker.tsx (proposed)`
## Implementation packages — in exact order
### P06.01 — Layer taxonomy and scene manifest
Define baseline, plot, canonical raster, zone, image coverage, plans, real trajectories, registered devices, dated events, selected highlights. One primary and optional qualified compare raster; independently toggle all vector categories.

### P06.02 — Extend existing renderer rather than replace
Keep `PlotMapShell`, `buildLayerStack` scientific logic, Layer10 authority, post-commit render receipts. Introduce separate typed geoobject layer composition, avoid weaving operational telemetry into raster materializer.

### P06.03 — Choose coordinate and mask semantics
Normalize vector WGS84; preserve raster grids/affines/CRS. Test MultiPolygon holes, second islands, antimeridian, degenerate ring, fractional bounds and geometry version; mask cache invalidates on geometry digest and grid identity.

### P06.04 — Implement map symbol grammar
Sensor/device status icons with textual accessible legend; cameras with validated orientation; planned drone dashed with waypoint numbers; actual flown track solid; MESIA unknown no coverage polygon; scenario crosshatched. Distinct colors+patterns for observed/inferred/simulated.

### P06.05 — Build typed selection and hit-testing
Use DeckGL picks for features; overlapping objects choose disambiguation popover; keyboard entity list fallback; map click emits canonical kind/id/source/geometry version to shared P03 store. Hover never changes scientific selection or makes network heavy calls.

### P06.06 — Implement context-driven highlights
Selecting object from tool list focuses/zooms to location (if known); selected plot zone highlight and linked sensor points/mission target. Keep plotted vector visible independently of active SIRE raster mode.

### P06.07 — Add independent display controls
Toggle Sensor, Cameras, Zones, Drones Planned, Drones Actual, MESIA, Events, Samples, Tasks, Experiments, Satellite Acquisitions. Provide Show All compatible overlays with clustering, user knowledge of hidden categories and layer counts.

### P06.08 — Temporal and quality gating
Each vector fetched for relevant time and geometry epoch; live and history can coexist but separately labeled; source 'UNKNOWN' does not generate geometry. Masked nodata pixels never clickable as qualified diagnosis.

### P06.09 — Memory/perf and GPU cleanup
Viewport bbox queries; symbol aggregation/LOD; stable layer IDs; memoized data; dispose layers/listeners on plot switch; clear browser raster receipts on invalidation; inspect loss-of-GL context fallback.

### P06.10 — Visual negative comparison
Overlay old and new map, verify pixel grid/legend/hover values+render receipt unchanged while adding spatial vectors. Map screenshot tests at dense case, zero-entities case, and pending-science/valid-devices case.
## Release / adversarial gates
- **P06-G01** Hole and second island mask tests with exact expected cell membership.
- **P06-G02** Sensor and zone remain independently selectable with the raster hidden.
- **P06-G03** Switch scientific surface never drops user-enabled drone/sensor points.
- **P06-G04** Unknown MESIA location and plot-scope event produce no pinpoint icon.
- **P06-G05** Mouse, keyboard and touch select same entity; overlapping objects disambiguate.
- **P06-G06** Scientific raster browser receipt retains exact publication/geometry/grid/authorized pixels.
- **P06-G07** No stale previous plot's spatial layers after rapid plot change.
- **P06-G08** Stable frame-rate, render time and memory measurements recorded versus P00 baseline.
## Required pass artifacts
- Geospatial scene registry and distinct data-layer adapters.
- Layer legend/style system, spatial map pick tests, geometry fixtures.
- Real browser screenshot+pixel test proof; render materialization parity.
- A3+A4 signed scientific/geometry GO and A7 negative test receipts.
**HOLD:** map geometry drift, forged feature display or broken canonical pixel authorization.
## Multi-agent handoff
R0 pinned source baseline/negative fixtures → R1 author vs independently prepared design critique → R2 A4 scientific + A6 security and A3 geometry where applicable → R3 A7 adversarial fail-old/pass-new tests → R4 A2/A8 integrated actual-browser check for UI → R5 A0 SHA/test receipts/GO-HOLD and rollback.

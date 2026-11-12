# Pass 06 — Everything on the map: a governed geospatial object model
**Existing source:** `src/components/farm/map/PlotMapShell.tsx`, `buildLayerStack.ts`, `map/layers/zones/UnifiedZoneLayer.ts`, `map/utils/buildPolygonMask.ts`, `useLayer10.ts`; `layer10_sire/schema.py`; `scientific_contracts/contracts_v2.py`; `sensor_runtime/registry.py`; `drone_mission/planner.py`; `mesia/contracts/coverage.py`.
## The map is not merely a raster viewer
Introduce a **typed geospatial scene registry** with separate graphics families. The product library includes every capability, but map objects render only where meaningful spatial evidence or explicit hypothetical planning geometry exists.
| Object family | Primary geometry | Map role | Panel |
|---|---|---|---|
| Plot and geometry epochs | Polygon/MultiPolygon with holes | Grounding, selection and boundary changes | Plot identity |
| ASMAE/SIRE scientific state | Georeferenced raster, valid mask | Qualified state/uncertainty/diagnostic surfaces | ASMAE, Evidence |
| Microzones and biological/nutrient/water risk | Polygon + source-cell identities | Investigation areas | Zones, Diagnostics |
| Registered sensors | Point; optional local footprint | Device, depth, uptime, latest timestamp | Sensor network |
| IP cameras | Point + verified bearing/FOV | Camera and images | Camera inspector |
| Drone mission planned | LineString / point set / target polygon | Plan and expected coverage (dashed) | Mission planner |
| Drone mission executed | Signed time-indexed track | Real flown path vs plan | Mission telemetry |
| Drone imagery | Tile/raster + footprint | RGB/orthomosaic evidence | Drone Imagery |
| MESIA receivers | Registered point + coverage qualification | Receiver node, coverage and gaps | MESIA |
| Weather | Point or provider area | Weather station, rain polygon if real | Weather |
| Irrigation/fertilization field events | Sensor/operation point, zone or plot polygon | Dated evidence, not automatic authority | Event timeline |
| Crop growth/yield/economics | Raster or plot/zone summary | Suitability, loss/variance map only if qualified | Analytics |
| Experiments | Distinct hypothetical/controlled geometry | Lab simulation footprint vs observed trial | Experiment Studio |
| Scouting tasks/photos/samples | Field-geotagged point, path or zone | To-do/complete/validated overlay | Operations |
| Satellite scenes | Acquisition footprint | Coverage and revisit | Satellite Explorer |
| Nonspatial measurements and global trends | None | Timeline/panels only | Historical analysis |
## Three axis-of-truth attributes
**(1) Space:** WGS84 source geometry + CRS/grids + geometry epoch + spatial support + validity mask + spatial uncertainty.
**(2) Time:** observed_at, first_available_at, published_at, valid_from/to, replay time, scene snapshot ID.
**(3) Authority:** observed / inferred / prior-only / proxy / simulated / planned; scope, issuer, identity, trust ceiling, proof and materialization receipt.
## Map layers and visual priority
Base imagery remains selectable. Scientific raster stack limited to one primary layer + one optional comparison; independent vector overlays for sensors, cameras, drone plans/tracks, MESIA, zones, events and tasks. User may enable multiple vectors, with clustering and importance-based decluttering. Contextual styling must not mislabel optical color lens as measured thermal imagery.
At the viewport shown in the audit (1600×900), persistent left dock + full map + right inspector + bottom time rail; overlays and pins toggle independently; 360px mobile uses drawers.
## Shared selection and event bus — non-negotiable
All tools read/write the same immutable scoped `Selection`:
`{plotId, geometryEpoch, publicationId?, timeCursor, selectedEntity:{kind,id}?, mapCamera, activeRasterId?, overlayIds, experimentId?}`.
Select entity anywhere -> map focus/selection; related panels update; timeline filters; 'open in' lists compatible tools. Map event carries **IDs**, not unverified object-shaped data. Selection of stale/wrong tenant/plot/geometry must be cleared or flagged.
## No false map claims
A device without registered coordinate appears in list with 'location unavailable', never at plot centroid. A plot-level event highlights plot/panel rather than making a pinpoint marker. A prior-only scalar ASMAE estimate has a plot-wide card, not synthetic pixel heterogeneity. A planned drone route is visibly dashed and cannot look like a real flight.
## Existing geospatial defect to resolve
`buildPolygonMask.ts` currently reads only first outer ring for MultiPolygon, excluding holes/other parts, and cache key omits geometry digest. Fix proper polygon topology, CRS and epoch invalidation before using new map objects to support field decisions.
## Test matrix
Point selection (sensor/camera) cross-highlights everywhere; zone selection auto-filters supporting evidence; invalid coords skipped; geometry epoch resets selections; concurrent temporal playback never replaces canonical head; polygon holes and islands correct; raster mask/legend/inspector bound to exact publication/geometry; planned vs executed flight distinct; no phantom icons for nonspatial events; browser render receipt reflects actual layer commit.

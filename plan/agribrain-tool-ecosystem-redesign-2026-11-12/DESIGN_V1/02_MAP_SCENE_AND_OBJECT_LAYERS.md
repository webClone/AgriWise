# Design Pass 02 — Unified Geospatial Scene / Map Object Ontology / Rendering
## Architecture principle
**Everything spatially meaningful is visualizable, not everything is a raster.** The scene includes native raster, tile, point, line and polygon layers as independent object families. All 94 tool concepts remain in the Library; map object adapters activate only with trustworthy geometry, time and scope.
## Scene stack (bottom -> top)
1. **Basemap:** actual satellite imagery / cartography, acquisition date and attribution. Cosmetic palettes may not claim measured stress.
2. **Plot geometry:** valid Polygon/MultiPolygon with holes, geometry epoch; explicit historic geometry if replaying.
3. **Scientific raster:** 0 or 1 primary SIRE authorized raster, plus 0 or 1 separately qualified compare raster. Pixel/no-data/legend/sigma must belong to committed publication.
4. **Field zones:** vector polygons from committed SIRE zone packs; hazard/confidence semantically styled and identity bound to originating state/surface.
5. **Image/coverage overlays:** drone orthomosaics, satellite footprints, actual MESIA coverage, experiment footprint, weather coverage. Semitransparent with controls and source details.
6. **Mission geometry:** planned waypoints and path, authenticated flown track, camera/image capture footprint, ground operations routes. Render planned and flown together for comparison with visual distinction.
7. **Objects:** registered sensors at declared geolocations, camera devices with supported direction/FOV, MESIA receiver nodes with supported coverage, field observations/samples/scouting tasks.
8. **Events:** actual/qualified rain, sensor alert, irrigation observation, drone capture, crop stage event, ASMAE update, task completion. With meaningful spatial support; plot-wide event highlights plot boundary, not an invented pin.
9. **Selection/highlight + interaction affordances** and separate UI legend/activity controls.
## Object classes and their semantics
| Class | Geometry | Identity source | Interaction | Trust limit |
|---|---|---|---|---|
| sensor_device | WGS84 registered point | sensor registry / owner-scoped API | click->readings, calibration, linked events | reading alone is not admitted science |
| camera | registered point, validated bearing | camera registry | video, image, observation history | PTZ simulator isn't physical movement |
| drone_plan | waypoint points/LineString, target polygon | mission planner | edit path, pattern, GSD | not a flown mission |
| drone_track | timed LineString/points | authenticated flight telemetry | scrub exact trajectory | not inferred from plan |
| drone_orthomosaic | raster+footprint | photogrammetry QA and ingest | split compare / inspect | no automatic elevation to state |
| mesia_receiver | registered receiver point | receiver/antenna manifests | spectrum, health, setup | no claimed coverage without graph |
| mesia_coverage | region/ray, optional geometry | coverage graph with epochs | choose frequency/time/path | no geometric invention from band alone |
| scientific_surface | georeferenced raster | L10 qualified publication | query pixel, sigma, state inspector | no pixels for scalar-only prior |
| zone | polygon+surface ID | L10 zone compiler | inspect and cross-launch | no unsupported treatment text |
| field_event | point/zone/plot geometry or None | event ledger | timeline and causality review | only located if source provides geometry |
| experiment | explicit trial/sandbox geometry or None | controlled experiment registry | compare scenario vs observed | simulation never overwrites canonical |
| scouting_task | point/route/zone | owner-scoped task registry | assign and confirm | action status not physical receipt |
## Proposed layer-manifest shape (design only)
```json
{
  "layerId": "registered-sensor-points",
  "sourceKind": "sensor_device",
  "ownerScope": {"tenantId":"t","farmId":"f","plotId":"p"},
  "geometryEpoch": "g1",
  "timeBasis": "current",
  "visibility": "on",
  "interactive": true,
  "style": "sensor-point-v1",
  "maturity": "engine",
  "featuresEndpoint": "proposed-owner-scoped-adapter"
}
```
### Geometry rules
- Canonical source geometry with CRS, transform, grid version, epoch/digest. Normalize to WGS84 for vector presentation; preserve raster native grid/transform and pixel bounds.
- Polygon holes, MultiPolygon islands, antimeridian and partial-coverage masks are first-class. **Fix existing `buildPolygonMask.ts` which uses first outer ring and a cache key without geometry digest.** Add geometry epoch to surface/mask identity.
- Unknown device location -> searchable list entry with 'Location unavailable'; invalid coordinate -> reject map feature; never silently fall back to plot centroid.
- For sensors, location is physical installation, not sample support extent. Show depth in inspector, not as an invented horizontal coverage circle.
- For RF, frequency coverage ≠ geographic polygon. Only actual modeled/measured area with geometry, outcome, configuration and uncertainty can be mapped.
- For photos, require explicit GPS/site registration; avoid creating apparent precise object point for a plot-scoped photo.
## Interaction/picking rules
Map and lists select a *stable feature ID*, not a whole potentially stale payload. Prefer DeckGL layer picking of zones/points; disambiguation when multiple close markers, plus keyboard list alternative. Hover gives compact transient summary, click fixes selection. Clicking empty map clears only object selection, not chosen scientific state, user-enabled overlays or time. `onAfterRender` receipts remain tied to authorized scientific raster only, not a sensor pin or basemap.
## Rendering & density
Viewport spatial query, pin clustering, level-of-detail, dynamic decluttering, select-highlight on top. User controls independent visibility of each vector group. Never silently hide a requested group due to a selected scientific mode; explain when no items are available. A 'Show all' preset toggles all compatible families but may cluster/declutter and cannot bypass scientific raster eligibility.
## Map legend
One scientific raster legend with real units, timestamps, uncertainty and source; plus a vector-symbol legend (Sensor, Camera, Planned Flight, Executed Flight, MESIA, Event, Task). Plotted hypothetical layers have unmistakable simulation/preview banners.

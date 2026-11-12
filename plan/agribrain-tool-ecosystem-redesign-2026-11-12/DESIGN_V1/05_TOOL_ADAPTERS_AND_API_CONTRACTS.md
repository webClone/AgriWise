# Design Pass 05 — Capability/Tool Registry, Backend Adapters and Proposed API Contracts
**Status:** architecture proposal. Endpoint paths, JSON examples and interfaces below are **NOT current implemented APIs**.
## Rationale
AgriBrain owns scientific truth, evidence authority and computational products. Device/mission/MESIA operational systems own their respective telemetry and hardware state. The frontend should request a read-only spatial projection of already authorized data, not synthesize positions or change evidence authority.
Preserve existing `/v2/plots/{plot_id}/snapshot`, `src/app/api/agribrain/surfaces/latest/route.ts` and existing owner-authenticated sensor/drone/MESIA API behavior. New workspace endpoints are separate, narrow adapters and must not bypass source admission.
## Registry contract
```js
// Proposed manifest, not deployed.
const exampleTool = {
  id: "drone.mission.planner.v1",
  label: {en: "Drone Mission Planner", ar: "تخطيط مهمة الطائرة"},
  category: "aerial",
  maturity: "built_ui", // built_ui | engine | prototype | hardware | future
  actions: [
    {id: "plan", mode: "simulation_or_plan", minAuthority: "plot_read"},
    {id: "dispatch_physical", mode: "physical_action", minAuthority: "hardware_approved"}
  ],
  launch: ["dock", "library", "map_context", "related_tools"],
  host: ["side_panel", "full_workbench"],
  accepts: ["plot", "zone", "drone_plan", "drone_track"],
  emits: ["drone_plan", "mission_event"],
  requiredInputs: ["plot_geometry", "vehicle_capability"],
  mapLayers: ["drone_plans", "drone_tracks", "drone_footprints"],
  limitations: ["existing_ui_dispatches_mock_driver"],
  sourcePaths: ["src/hooks/useDroneMission.ts", "services/agribrain/drone_mission/planner.py"]
};
```
Registry is canonical, versioned and queryable, not an unbounded list in `PlotDashboard.tsx`. 94 concept entries from prior pass 08 are **catalog seed**, not 94 distinct completed integrations; deduplicate canonical tool IDs with aliases while preserving discoverability/search.
### Tool availability = two independent axes
- Maturity: built UI / engine present / prototype / hardware-dependent / future.
- Current capability state: available / available_read_only / simulation_only / configuration_required / missing_data / unsupported_permission / disabled_by_safety / service_unreachable.
The library **always shows** the tool. A planned tool can show an interactive explanation/setup/flow preview, but unavailable physical actions must be disabled with exact reason.
## Proposed API projection
Suggested endpoints (not existing):
```
GET /api/plots/{plotId}/workspace/tool-catalog
GET /api/plots/{plotId}/workspace/features?groups=sensors,zones,drone_plans,drone_tracks,mesia_receivers,field_events&bbox=...&asOf=...
GET /api/plots/{plotId}/workspace/features/{kind}/{id}
GET /api/plots/{plotId}/workspace/relationships?kind=zone&id=...&snapshotId=...
GET /api/plots/{plotId}/workspace/event-timeline?from=...&to=...&knowledgeCutoff=...
GET /api/plots/{plotId}/workspace/available-publications?from=...&to=...
```
Proposed features endpoint is **read-only** and must enforce server-side tenant/farm/plot identity, crop cycle, valid spatial support and temporal knowledge cutoff. Never proxy arbitrary user-constructed backend paths.
### Feature envelope
```json
{
  "contractVersion":"plot-map-feature-v1",
  "featureId":"sensor:device-07:registry-epoch-4",
  "kind":"sensor_device",
  "sourceId":"device-07",
  "ownerScope":{"tenantId":"t","farmId":"f","plotId":"p"},
  "geometryEpoch":"plot-geometry-digest",
  "deviceGeometryVersion":"registry-epoch-4",
  "geometry":{"type":"Point","coordinates":[3.0,36.0]},
  "geometryCrs":"EPSG:4326",
  "spatialSupport":"physical_device_location",
  "locationQuality":"registered_not_survey_verified",
  "observedAt":"2026-11-12T12:00:00Z",
  "firstAvailableAt":"2026-11-12T12:00:04Z",
  "validFrom":null,
  "validTo":null,
  "sourceRefs":["registry:device-07"],
  "publicationId":null,
  "epistemicClass":"operational_registration",
  "capability":"read_only",
  "quality":{"deviceHealth":"unknown","readingAdmittedToAsmae":false},
  "relatedToolIds":["sensor.network","sensor.calibration"]
}
```
This JSON is illustrative; coordinates and IDs are invented **example schema values only**, not a real plot or device location.
## Adapter map
| Adapter | Truth owner | Payload to map | Must not fabricate |
|---|---|---|---|
| L10 SIRE | immutable published snapshot + receipt | raster, zone polygons, masks, sigma, lineage | unauthorized pixels and precision |
| Sensor | registered device + operational readings | device point; health; time series; calibration | implicit admission |
| Drone | plan store / live telemetry / photogrammetry | planned path; flown track; image footprint | mock takeoff or fake drone status |
| MESIA | receiver/capability manifests + coverage graph | verified receiver point, qualified coverage, status | universal RF coverage |
| Observation & samples | field photo/ground truth ledger | provided geotagged point/zone/plot scope | precise location for unknown |
| Weather & events | source weather + event store | real station/coverage/dated event scope | invented event site |
| Experiments | versioned sandbox/trial ledger | explicit scenario/trial geometry and label | simulated data as measured |
| Tasks/operations | owner-scoped task store | work order geography and status | physical success without receipt |
## Integrity and policy at every boundary
- **Authentication/authorization:** every collection, detail and subscription rechecks verified authenticated owner scope. Never accept `tenantId` from client as authority.
- **Scientific scope:** surface/pixel/zone uses publication ID, numerical binding proof and rendering authorization. A mere feature endpoint can't override browser SIRE gates.
- **Spatial scope:** validate WGS84 longitude/latitude or CRS transform, geometry epoch, raster grid, mask; reject foreign polygons and invalid coordinates rather than "fix" silently.
- **Temporal scope:** both `observedAt` and `firstAvailableAt` required for historical-authoritative inclusion. Current telemetry still marked uncertified until accepted.
- **Provenance and classification:** source IDs + content hashes/receipts when applicable. Map category vs causal links are independent; source fusion authority and rendering permission remain separate.
- **Action safety:** physical drone/irrigation/chemical controls have separate backend authorization and hardware identity. Tool registry flags never grant authority. Actuation remains disabled during observation-only pilot.
- **Error states:** distinguish unavailable source, data gap, stale response, integrity failure, active scientific job, publication waiting, and terminal worker failure. No generic 'ASMAE FAILED' from client timeout.
## Performance & streaming
- Partition vector features by plot and spatial bbox/time; incremental authenticated polling or scoped subscription only when supported, with sequence number and reconciliation. Device freshness timestamp and receiver geometry epoch are explicit.
- Immutable scientific publication can be cached keyed by owner/plot/cropCycle/geometry/snapshot/contract hash; live telemetry uses independent bounded buffer. Revalidation never mutates the old publication.
- Expensive rasters lazy loaded on request; vector layers clustered by zoom. Large imagery via tiles/artifacts with validated URLs and scoped access.
- On plot switch, abort all outstanding requests and clear old scene immediately. A response carrying older request generation cannot overwrite the new scene.
## Proposed client modules
`PlotWorkspaceProvider`, `GeospatialSceneRegistry`, `ToolManifestRegistry`, `TimeController`, `SelectionController`, `MapFeatureAdapter`, `RelatedEvidenceGraph`, `ToolHost`, `ActivityCenter`. Implement incrementally, preserving `PlotMapShell` and render receipt behavior, reducing coupling rather than rewriting everything at once.
## Contract compatibility tests
Every adapter uses explicit identity; a mock stream cannot claim certified status; invalid geometry rejected; foreign-plot data excluded; incomplete registry fields yield list-only; cross-panel selection uses same canonical ID; new features endpoint cannot change L10 hash or actual physical actuator state.

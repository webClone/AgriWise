# Design Pass 03 — Shared Selection, Temporal Consistency and Interaction Protocol
**Status:** proposed client and backend contracts; not implemented.
## Why this is the architecture's center
All panels, map layers and tools consume one scoped workspace controller. A tool cannot invent a new plot/time/snapshot scope locally. Canonical science remains immutable; changes to the viewport and experiment assumptions are UI state or new sandbox data only.

## State model
```js
// SHAPE ONLY: planned application protocol, not an existing implementation.
const workspaceState = {
  scope: {
    tenantId: "tenant-id", farmId: "farm-id", plotId: "plot-id",
    cropCycleId: "cycle-id-or-null", geometryEpoch: "geometry-digest"
  },
  temporal: {
    mode: "live", // live | historical | forecast | simulation
    cursorAt: null, // ISO time for fixed-time modes
    knowledgeCutoffAt: null, // explicit historical replay cutoff
    scientificPublicationId: null,
    experimentRunId: null
  },
  map: {
    camera: {longitude: null, latitude: null, zoom: null},
    primaryRasterId: null, compareRasterId: null,
    activeVectorLayerIds: ["zones", "sensors", "field-events"],
    selectedLocation: null
  },
  selection: {
    kind: null, id: null, sourceVersion: null,
    parentPublicationId: null, geometryEpoch: null
  },
  ui: {
    activeToolId: null, toolHostMode: "inspector", pinnedToolIds: [],
    inspectorTab: "summary"
  },
  requestGeneration: 0
};
```
Persist only harmless preferences (pinned tools, optional layer visibility), scoped by user and plot. **Do not persist a stale tenant/snapshot identity as if it were current.**

## Selection API (design)
- `selectEntity({kind, id, scope, sourceVersion})`: validates plot/geometry/source, resolves typed details and related relationships. Updates map focus and inspector only. Does **not** automatically change time mode, trigger a new scientific run, authorize a physical action or set a false publication status.
- `selectPixel({surfaceId, publicationId, row, col})`: checked against committed raster grid, mask, resolution and render authorizations. Zoom/hover sampling is separate from an authorized scientific diagnosis.
- `selectZone({zoneId, publicationId})`: object must originate from a matching published SIRE pack. Highlight exact geometry; show source surface and uncertainty; expose related tool actions with explicit eligibility.
- `openTool({toolId, selectionRef})`: retains selected entity and plot/time; opens contextual panel or workbench.
- `setTime({mode, at, knowledgeCutoffAt, publicationId})`: updates one temporal controller, asynchronously resolves valid snapshot and object-version sets; incompatible selection remains selected but marked outside time range or is cleared with explanation.
- `setVisibility({layerId, enabled})`: map presentation only; does not modify scientific truth or admission.
- `createExperiment({sourceSnapshotId, assumptions})`: records a distinct scenario reference. All resulting map output carries simulation provenance.
- `changePlot({scope})`: bumps request generation, cancels previous in-flight queries, revokes obsolete selections/rasters, resets sensitive state before fetching new scope.

## Event envelope
```json
{
  "eventId":"evt-unique",
  "sourceSystem":"sensor|drone|mesia|sire|task|weather|experiment",
  "kind":"observation|plan|capture|status_change|scientific_publication|warning|experiment",
  "ownerScope":{"tenantId":"t","farmId":"f","plotId":"p"},
  "subject":{"kind":"sensor_device","id":"device-07"},
  "geometryRef":null,
  "observedAt":"2026-11-12T15:00:00Z",
  "firstAvailableAt":"2026-11-12T15:00:05Z",
  "recordedAt":"2026-11-12T15:00:07Z",
  "validFrom":null,
  "validTo":null,
  "publicationId":null,
  "runId":null,
  "status":"reported",
  "epistemicClass":"observation",
  "authority":"diagnostic_only",
  "provenanceRefs":["receipt-or-source-id"],
  "replayCutoffAt":null
}
```
The above is a **shape illustration only**, not evidence of a real event. Field semantics must conform to the corresponding existing canonical backend contract on implementation (observation time, first availability, publication status, scope and issuer).

## Real-time and historical clock model
Five timestamps must not be conflated:
1. **Observed/captured**: when sensor or imagery observed reality.
2. **First available/known**: when the system could legitimately consume that information.
3. **Ingested/accepted**: when particular processing/authority transitions occurred.
4. **Published**: when a canonical scientific snapshot became available for display.
5. **Valid/forecast time**: time represented by a prediction or simulation.
"Today" in the UI is not proof that an observation is new. Scrubbing to 2026-09-08 while viewing today's sensor does not mean that sensor existed/was known at cutoff. Historical replay must exclude future-known evidence even if observed earlier. Use distinct layer labels `Historical`, `Live (not admitted)`, `Forecast`, `Simulation`.

## Correlation vs causality
Spatial overlap/distance is a **discovery relationship**; only a source/evidence ledger edge with exact content/identity/time authority can be called **contributed to state**.
```text
Sensor device --[located_within, geometry]--> Zone
Sensor reading --[admitted_by, receipt]--> Layer1 evidence
Layer1 evidence --[assimilated_into, proof]--> ASMAE state/run
ASMAE state/run --[published_as, hash]--> Layer10 snapshot
Layer10 snapshot --[rendered_in, browser receipt]--> Raster overlay
Drone mission --[targeted, plan]--> Zone
Drone flight --[observed, telemetry]--> Executed track
Drone image --[validated_as, qa receipt]--> Admissible evidence candidate
```
Lineage graph traversals must refuse imaginary edges for mere proximity.

## Conflict and stale-data behavior
- New `scientificPublicationId` and old selected zone: validate zone origin before retaining, otherwise mark prior publication and invite explicit comparison.
- Current device status while historical mode: show muted `LIVE NOW` chip outside time-peel, not use it to paint the old map.
- A timeline event without geometry shows in timeline/list and highlights plot only when its scope is plot-wide. No fabricated pin.
- Switching plot while a tool request is pending: abort/ignore response using plot token and monotonically increased generation. No cross-tenant leakage.
- Device moves after registry change: new geometry epoch/device-location version, pin moves only when verified.
- Simulation output and current publication may overlay for comparison but live run ID, simulation ID and scenario assumptions remain separate.
## State orchestration vs backend event bus
Use a single client `PlotWorkspaceProvider` / reducer or a bounded state store for presentation and selection. Authoritative events originate from backend APIs/streams, never client state setters. Presentational selection events do not get written to scientific evidence ledgers.
## Acceptance
Map->panel->tool->map selection roundtrip identity; valid-time switching with no future leakage; mixed live/historical events distinct; foreign plot/tenant selection rejected; no stale async overwrite; no unsupported cause edge; no simulation-to-canonical mutation; keyboard and touch selection parity.

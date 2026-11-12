# Pass 09 — Tool Platform architecture, synchronization, milestones, and release gates
**Status:** design / audit, no code changes except these documentation files.
## Target composition
```text
PlotRoute (strict owner + geometry/crop-cycle scope)
  PlotWorkspaceProvider
    SnapshotController (canonical Layer 10 publication identity)
    TimeController (historical/forecast/operational playback)
    SelectionController (entity/zone/cell/location)
    ToolRegistry + CapabilityPolicy + UserPinnedDock
    GeospatialSceneController
      Basemap | ScienceRaster | ZoneVectors | Sensors | Cameras
      PlannedDroneRoutes | ExecutedDroneTracks | MESIA Coverage
      Events | Tasks | GroundTruth | ExperimentOverlays
    ContextInspector (selected entity)
    ToolHost (dock, right panel, full workbench)
    EvidenceGraph / RelatedTools
    Immutable Run/Experiment Ledger
```
## Minimal contracts
```ts
type ToolMaturity = "built_ui" | "engine" | "prototype" | "hardware" | "future";
type OperationalMode = "read_only" | "simulated" | "scientific_compute" | "physical_action";
type MapGeometryType = "Point" | "MultiPoint" | "LineString" | "Polygon" | "MultiPolygon" | "Raster" | "None";
type MapEntityKind = "plot"|"zone"|"sensor"|"camera"|"drone_plan"|"drone_track"|"mesia_receiver"|"observation"|"event"|"task"|"experiment"|"state_surface";
interface MapFeatureEnvelope {
 id: string; kind: MapEntityKind;
 ownerScope: {tenantId:string;farmId:string;plotId:string};
 geometryEpoch: string; geometryType: MapGeometryType;
 geometry?: unknown; geometrySource?: string; spatialSupport?: string;
 validFrom?: string; validTo?: string; observedAt?: string;
 firstAvailableAt?: string; publicationId?: string; sourceRefs:string[];
 authorityClass: "observation"|"posterior"|"proxy"|"hypothesis"|"simulated"|"planned"|"unknown";
 status: string; uncertainty?: unknown; capabilityReceiptId?:string;
}
interface ToolDefinition {
 id:string; title:string; category:string; maturity:ToolMaturity;
 supportedModes:OperationalMode[]; requiredCapabilities:string[];
 mapEntities:MapEntityKind[]; panelModes:("context"|"workbench")[];
 permissions:string[]; sourceRefs:string[]; disabledReason?:string;
}
interface PlotWorkspaceSelection {
 ownerScope:{tenantId:string;farmId:string;plotId:string};
 geometryEpoch:string; selectedEntity?:{kind:MapEntityKind;id:string};
 selectedLocation?:{lng:number;lat:number}; activePublicationId?:string;
 activeRasterId?:string; timeCursor?:string; timeMode:"live"|"historical"|"forecast"|"simulation";
}
```
The above is a *proposed* application contract, not existing repository API.
## Correlation rules
1. **One entity ID across panels and map.** `select(sensorId)` -> map highlights its registered point; device panel focuses it; evidence inspector filters its admitted observations; timeline anchors last reading; ASMAE state correlation appears only from explicit lineage.
2. **Selected zone -> related tools.** Map zone -> ASMAE state, zone drivers, linked scenes, geospatial sensors, candidate drone coverage, ground-truth actions, scenario lab; no automatic treatment recommendation.
3. **Planned drone -> map path.** Editing overlap/GSD/pattern recomputes *preview* waypoint geometry; preflight checks require real hardware facts for actual dispatch; executed track from trustworthy telemetry is an independent layer.
4. **MESIA experiment -> overlay with scientific status.** Georeferenced receiver/antenna/coverage and trial geometry; sample/radio data events clickable; simulated FDTD output clearly watermarked. No direct soil property map without calibrated observation/assimilation.
5. **Time coherence.** Live devices, historical snapshots and forecast surfaces use different clocks. Scrubbing time must load appropriate archived events/snapshot and NOT rebind live data as historical evidence.
6. **Cross-entity selection consistency.** Changing plot/crop/geometry epoch clears all stale selection and aborts outstanding requests; different panels may never leak another plot's entity.
## Work packages
**P0 — Safety/semantic correction:** correct route scope, mask topology, published/worker states, unsupported advice, simulation and actuation labeling. Keep physical irrigation disabled.
**P1 — Canonical Tool Registry and shell:** implement comprehensive library + pinned dock + contextual tool host; all intended tools visible with accurate maturity and setup.
**P2 — Geospatial entity adapters:** owner-scoped sensors, cameras, drone plans/actual telemetry, MESIA receiver graph, persisted events, task geometry, state rasters with an immutable envelope and validation.
**P3 — Cross-panel interaction engine:** shared selection/time/map camera with stable IDs, 'Open with' links, hover/inspect, side-by-side comparisons, cross-source correlation (spatial proximity is not causality).
**P4 — Scientific deep workbenches:** 13-state explorer/covariance, drone planning, MESIA experiments, scenario lab, agronomic diagnostics with proper provenance.
**P5 — Runtime qualification:** actual publisher→FastAPI→Next→browser, no fake data in observed mode, negative controls, performance/a11y/mobile/RTL and hardware gating.
## Test gates
- G01 identical plot/geometry/publication IDs across browser layers and inspectors
- G02 13 catalog state entries even when all unavailable; no fabricated maps
- G03 correct polygon holes, MultiPolygon islands, CRS and geometry epoch caching
- G04 device coordinate fidelity, location unavailable fallback, foreign tenant rejection
- G05 sensor reading calibration/first availability cannot be bypassed by UI data
- G06 map/list selection parity; context tool switch retains selection
- G07 mission planned vs executed styling and source identity
- G08 mock dispatch cannot show drone live/airborne
- G09 MESIA receiver/coverage unknown remains unknown
- G10 experiment simulator cannot mutate or replace authoritative snapshot
- G11 source-supported zone/scouting advice but no unsupported chemical/water dose
- G12 physical irrigation stays disabled and simulator acknowledgment explicit
- G13 camera PTZ simulated state never advertised as physical confirmation
- G14 stale + retry semantics never label mere client timeout 'worker FAILED'
- G15 actual browser raster pixels, legend, mask and receipt under same snapshot ID
- G16 sensor, zone, drone, MESIA and event pin layering coherent at 1600/1024/768/360
- G17 RTL, keyboard and 200% zoom usable
- G18 polling/raster GPU/heap instrumentation across plot/time switches
- G19 every time source identifiable: observed, available, published, simulated
- G20 no evidence, no geometry, no connection -> informative empty state, never fabricated success
## Governance
Use new implementation branch, keep integration baseline auditable, protected `main` untouched, Draft PR #28 untouched, scientific monograph unchanged, 52-plan register not inflated by design tasks, observation-only interlock false. This document is architecture discussion; do not merge or implement before UX decision.

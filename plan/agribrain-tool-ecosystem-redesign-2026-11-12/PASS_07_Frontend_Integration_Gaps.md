# Pass 07 — Existing frontend and API integration gaps
**Representative source:** `src/components/farm/PlotDashboard.tsx` (847 lines), `map/PlotMapShell.tsx` (1748 lines), `src/hooks/useLayer10.ts` (2688 lines), `useDroneMission.ts`, `usePlotTelemetry.ts`, `MEsiaObservatoryWorkspace.tsx`, `SensorNetworkWorkspace.tsx`, `src/app/api/plots/[id]/sensors/status/route.ts`, `src/app/api/agribrain/drone/[...path]/route.ts`, `src/app/api/agribrain/mesia/route.ts`, `src/app/api/agribrain/sandbox/route.ts`.
## Existing strengths (preserve)
1. `PlotMapShell` already uses MapLibre and DeckGL with canonical Layer10 surfaces, zone interaction, materialization and browser render receipt pathways.
2. `PlotDashboard` dynamically imports DroneMissionPanel, SensorNetworkWorkspace, MESIA Observatory and IrrigationDashboard. The features are exposed; however, they are isolated overlays/full-screen workspaces, not map-linked interoperable tools.
3. Current `useLayer10` stores selectedZone and map mode, enabling one cross-panel zone-inspector path. It can be extended to a general typed selection rather than replaced by many disparate toggles.
4. Frontend API routes use owner-scoped access for sensors, MESIA and drone; preserve this layer and force every new geospatial query to recheck plot/tenant scope.
## Confirmed source gaps
**G01 — No global tool selection context:** multiple `showDronePanel`, `showSensorsPanel`, `showMesiaPanel` state booleans are local in PlotDashboard. There is no observed shared `selectedEntity` spine connecting all tools.
**G02 — Map not device-event-ready:** PlotMapShell's main active stack focuses scientific surfaces and zones; no first-class sensor/drone/MESIA/camera/event feature registry shown in inspected map path.
**G03 — Sensor map projection missing:** status endpoint includes readings/health but omits latitude/longitude/depth. Can't pin with authenticated coordinates from this API.
**G04 — Drone fake readiness:** useDroneMission reports hard-coded connected drone/weather and `driver_type:"mock"`. Mission estimates use `Math.random()` on UI. Must not make actual flight/tracker claims.
**G05 — MESIA live-readout ambiguity:** fallback UI numerical values in AsmaeSupervisorTab and default '8 Sats' when backend unavailable may resemble measured physics. Use `No receiver evidence` or `DEMO` and require receipts.
**G06 — Sensor alert not durable:** backend `dispatch_sensor_alert` writes stderr. Event map must distinguish computed alerts from a persisted alert feed.
**G07 — Camera control mock:** PTZ driver has simulated move, must use simulator badge and no physical acknowledgment.
**G08 — State/temporal workbench incomplete:** ASMAE thirteen product catalog exists; current base modes/lenses restrict independent state discovery and share one broad map-centric hook.
**G09 — Planning vs action status:** mock irrigation command function advertises success; refactor global action vocabulary; no signed irrigation actuation.
**G10 — Component structure too coupled:** PlotDashboard, PlotMapShell, useLayer10 and buildLayerStack are very large; prefer tools as composition around a stable map and publication context.
**G11 — Snapshot status and waiting:** client wait timeout can be rendered as producer failure; distinguish job durable terminal vs pending publication vs stale snapshot.
**G12 — Geometry correctness:** mask ignores polygon interior rings and extra MultiPolygons; cache does not include polygon epoch. Fix before richer overlays.
## Interoperability design
- Replace local tool window booleans with `activeToolId`, `panelMode`, `pinnedTools`, and a central `selectedEntity` scoped to plot, time and publication.
- Build backend projections for registered device locations, persisted drone mission geometry, MESIA receiver coverage and events.
- Map selection emits typed object IDs; panel selection calls same selection action; panels get exactly the same selected entity.
- Time scrub displays historical imagery and time-valid feature snapshots, but never rewrites today's live device status as historical.
- Distinct data providers: immutable canonical science (SIRE), admitted observation feeds, operational device status, experiment/simulation overlays, future planned sketches.
## Required acceptance gates
Close one tool and reopen another -> selection retained or deliberately cleared with reason; sensor click and list click yield same entity; zone click opens supporting evidence; simulated event cannot show as executed; capability card opens even if unavailable but action is blocked; any wrong-plot feature rejected server-side; render receipt remains specific to scientific materialization only.

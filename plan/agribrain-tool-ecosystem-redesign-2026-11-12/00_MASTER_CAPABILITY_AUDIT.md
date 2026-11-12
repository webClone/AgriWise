# Akaloris — AgriBrain Tool Ecosystem & Geospatial Workspace (Master)
**Date:** 2026-11-12  
**Source baseline:** integration code at `1ee2c20119af29dd1f0a0b46c85217d91206b744` (the subsequent integration-branch changes inspected here were documentation-only).  
**Goal:** design one *complete* future Plot Workspace exposing all working, experimental, hardware-dependent and planned AgriBrain capabilities with synchronized map, tools, panels and timeline.
**Status:** source-informed product/architecture audit, not production acceptance, no execution, no field/hardware validation.
## Scope and honest coverage
- GitHub tree: 3,532 repository files; 2,731 under `services/agribrain/`. This pass inventoried backend namespaces and traced representative code paths from source through API/UI; it did **not** line-by-line audit all 2,731 files. Coverage of the *whole* backend is not 100%.
- Explicitly inspected: frozen 13-state schema, L10 surface/zone/temporal contracts, sensor runtime + frontend endpoint, drone planning/control/frontend, photogrammetry, MESIA contracts/experiments and UI, agronomy layers, experiment sandbox, existing map and plot dashboard.
- No running Next.js browser, Python test suite, hardware, radio receiver, drone or live field study was executed. Do not infer runtime readiness from the presence of a module.
## Product decision
**INCLUDE EVERYTHING IN THE DESIGN.** Tool visibility is independent of readiness or authority. No simulated result may be labeled as observed, no model hypothesis as measured reality, no mission planning as airborne execution, no control proposal as a dispatched physical command.
## Reports
1. [Pass 01 — Scientific foundation / ASMAE / SIRE](PASS_01_Scientific_States_SIRE.md)
2. [Pass 02 — Sensors / cameras / acquisition](PASS_02_Sensors_Cameras_Observations.md)
3. [Pass 03 — Drone mission / mapping / safety](PASS_03_Drones_Missions_Photogrammetry.md)
4. [Pass 04 — MESIA / research experiments](PASS_04_MESIA_Experiments.md)
5. [Pass 05 — Agronomic and planning tool extraction](PASS_05_Agronomic_Decision_Tools.md)
6. [Pass 06 — Map geometry and synchronized interactions](PASS_06_Geospatial_Object_Ontology.md)
7. [Pass 07 — Frontend/API integration gaps](PASS_07_Frontend_Integration_Gaps.md)
8. [Pass 08 — Complete tool registry and eligibility matrix](PASS_08_Complete_Tool_Registry.md)
9. [Pass 09 — Platform contract, roadmap and test gates](PASS_09_Architecture_Roadmap_And_Gates.md)
## Core design boundaries
1. Map = primary *spatiotemporal* canvas; plot, sensors, drone paths, cameras, zones, events, rasters, experiments can coexist as independent typed layers and interact through stable IDs.
2. Panels use a shared `PlotWorkspaceContext` and `Selection` plus `TimeContext`; never share mutable estimates by ad hoc globals or silently retag an old observation with a new publication.
3. A map pin requires certified coordinates. A plot-wide event uses plot geometry or a timeline, not a fabricated centroid point.
4. Each tool declares maturity, operational environment, permissions, dependencies, map feature types, time behavior, accepted scientific outputs and zero-physical-actuation defaults.
5. Keep production mathematical/safety governance untouched during design: monograph intended architecture, protected main, PR #28, existing releases, provisional 52-plan register, irrigation disabled.
## Highest leverage findings
- `sensor_runtime.registry.SensorDeviceRegistration` contains latitude/longitude, depth, placement, zone and calibration; Next `GET /api/plots/[id]/sensors/status` currently omits coordinates. Map-linked sensors require an owner-scoped location projection.
- `useDroneMission` supplies simulated connected state/weather and passes `driver_type:"mock"` to dispatch. Drone planning/waypoints are real software surfaces; do not advertise real flying from this hook.
- `MEsIA` has receiver coverage graph, observability and experiments, while central physical campaign runner and field trial harness raise `NotImplementedError`; distinguish an interactive lab from actual completed field experiments.
- `layer10_sire.schema.SurfaceType` registers all 13 ASMAE state surface identities, but inventory existence does not prove a qualified spatial raster or browser receipt. Present all thirteen as catalog entries with availability and reason.
- Existing `PlotMapShell` already provides MapLibre/DeckGL zones, raster materialization and render receipts; use it as the migration baseline instead of discarding proven integrity checks.
## Success condition
A user can select a zone, sensor, device, event, mission, experiment or state from *any* panel and the map, timeline, other panels and AI context update consistently without changing canonical science. Every object has auditable source/scope/time/status. An unavailable object is visible in the catalog, but does not invent geometry or actions.

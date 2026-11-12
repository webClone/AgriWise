# Pass 03 — Drone missions, telemetry, imagery, geospatial planning
**Evidence:** `drone_mission/planner.py`, `anomaly_bridge.py`, `mission_history.py`; `drone_control/mission_state_machine.py`, `preflight.py`, `mission_compiler.py`; `drone_photogrammetry/engine.py`; `src/hooks/useDroneMission.ts`; `src/components/farm/drone/DroneMissionPanel.tsx`; Next `api/agribrain/drone/[...path]/route.ts`.
## Source facts
- Mission planner computes waypoints from polygon, GSD, overlap and pattern; supports search/coverage/row/contour-like planning. Backend has states `PLANNED -> UPLOADED -> READY -> ARMING -> IN_FLIGHT -> ...` and preflight battery/GPS/wind/storage/connection checks.
- `useDroneMission` initializes `connected:true` and weather values as simulated fixtures, and POSTs `driver_type:"mock"`; therefore current UI is **not evidence of a physically connected aircraft**.
- `DroneMissionPanel` estimates flight time with `Math.random()` and a simplified altitude formula; such estimates must be labeled illustrative and should defer to backend flight plan with capability/calibration.
- Photogrammetry engine has ingest, alignment, orthomosaic, georeference and QA pathways. Generated map rasters are qualified separately for temporal/spatial identity and downstream assimilation; recording a completed mission does not prove a valid raster.
- Anomaly bridge can produce mission suggestions tied to source anomaly, zone and plot. Existing mission history in `drone_mission/mission_history.py` uses an in-memory store; do not claim durable fleet timeline by module existence.
## Tool family
Mission Planner; Mission Simulator; Coverage Planner; Preflight Console; Flight Timeline; Live Drone Tracker (hardware-dependent); Reflight Planner; Targeted Hotspot Inspection; Mission Comparison; Image Review; Orthomosaic Lab; Elevation/Surface Reconstruction; RGB/Crop Row/Crown Inspection; Mission-to-ASMAE Evidence Bridge; Fleet Connectivity/Health.
## Map objects
Waypoint points, planned path lines, launch site, no-fly polygons only when verified, coverage/overlap footprints, live track when transport authenticated, actual camera exposure positions, acquired orthomosaic raster, anomaly target polygons, event pins for located mission actions.
## Cross-panel interactions
Choose ASMAE low-vigor zone -> request *proposed* targeted drone mission -> confirm intended coverage and safety constraints -> map previews path -> mission panel edits pattern -> preview updates same map -> executed track appears only from actual signed drone telemetry -> accepted orthomosaic can be inspected against prior SIRE surface, without silently becoming assimilated evidence.
## Negative tests
No plane icon showing airborne when only mock dispatch; no green preflight based on synthetic drone status; invalid coordinates don't render flight path; mission observations cannot elevate scientific state without QA/authority; selected zone and time remain stable across panel transitions.

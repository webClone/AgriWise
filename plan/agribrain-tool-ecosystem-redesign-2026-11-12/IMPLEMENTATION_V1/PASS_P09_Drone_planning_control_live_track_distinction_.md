# P09 — Drone planning control live track distinction imagery and map-linked missions
**Status:** NOT STARTED · **Prerequisites:** P04,P05,P06 · **Primary agents:** A5+A3+A6 · **Independent verification:** A7 + A6 / A4  
**Proposed code branch:** `feat/plot-workspace-p09-drone-mission` (not created).
## Product scope and safety boundary
Retain every Drone Mission tool (planner, preflight, flight plan, telemetry, mission history, orthomosaic QA, anomaly suggestion, flight comparison) in shared map. Preserve successful plan algorithm but distinguish planning/simulation from physically executed flights.
## Source targets
- `services/agribrain/drone_mission/planner.py`
- `services/agribrain/drone_mission/coverage_patterns.py`
- `services/agribrain/drone_mission/anomaly_bridge.py`
- `services/agribrain/drone_control/preflight.py`
- `services/agribrain/drone_control/telemetry_ingest.py`
- `services/agribrain/drone_control/mission_state_machine.py`
- `services/agribrain/drone_photogrammetry/engine.py`
- `src/hooks/useDroneMission.ts`
- `src/components/farm/drone/DroneMissionPanel.tsx`
- `src/app/api/agribrain/drone/[...path]/route.ts`
- `src/components/farm/map/workspaceLayers/ (proposed)`
## Ordered execution packages
### P09.01 — Mission source model
Separate proposed intent, planned path, approved dispatch request, actual execution state, flown telemetry, imagery frame set, QA orthomosaic, related zone and anomaly lineage. Stable IDs at each stage and geometry/epoch.

### P09.02 — Map-integrated planning
Click authorized SIRE zone -> choose inspection mission -> plan from exact zone polygon and profile. Edit GSD/overlap/path pattern/altitude settings; map updates dashed proposed waypoints and coverage, no actual movement.

### P09.03 — Fix misleading client-side estimates
Replace `Math.random()` estimation in planner UI with deterministic backend plan metrics or explicit example placeholder. Unsupported high precision treated as estimated and accompanied by assumptions.

### P09.04 — Mock-versus-live device truth
Current `useDroneMission` hardcodes connected drone/battery/weather and `driver_type:'mock'`. Replace the claimed live labels with explicit simulator or real driver status from authenticated source; physically enabled controls require distinct backend authorization and real preflight.

### P09.05 — Flight-state transition UI
Visualize planned/uploaded/ready/arming/in-flight/paused/returning/completed/aborted/failed from the backend state machine with source receipts; state machine transition alone is not authenticated GPS. Abort/RTL interface disabled or simulator-only until real vehicle driver.

### P09.06 — Telemetry map track
Show actual track only from authenticated timestamped telemetry and vehicle identity. Render planned vs flown simultaneously as different line patterns, with waypoint/time-hover. Lost GPS -> event/unknown segment, not interpolated fake flight.

### P09.07 — Orthomosaic ingest/quality review
Present frame QA, coverage/gaps, GSD, reprojection error, tiled mosaic, invalid and degraded modes, provenance. Overlay image footprint only if geo-registered; no automatic ASMAE assimilation without Layer0 admission and SIRE publication.

### P09.08 — Field-event and anomaly trigger
Show source-linked drone suggestion from anomaly bridge, mission target link and history; target selection should not dispatch mission. Persist mission history before advertising long-term stable records.

### P09.09 — User rights and safety controls
Read/plan/simulate privileges separate from real hardware command. Weather/geofence/vehicle telemetry must be sourced; physical action remains gated without trusted preflight and authorization.

### P09.10 — Acceptance under hardware absence
Test full map planner using mock backend and simulated execution badges. Hardware-dependent actual flight acceptance remains a separate future qualification track; no fake completion claims.
## Pass-specific adversarial acceptance
- **P09-G01** Editing drone route changes same map preview and retains zone context.
- **P09-G02** Current `driver_type:mock` never displays true airborne state or physical GPS track.
- **P09-G03** Backend plan failure/infeasible path blocks dispatch.
- **P09-G04** Real telemetry source, when supplied as fixture, produces independent flown path and event timeline.
- **P09-G05** No fake battery/weather readiness when driver not connected.
- **P09-G06** Orthomosaic QA-failed imagery cannot be passed as qualified ASMAE map.
- **P09-G07** Mission switching doesn't leave stale old-plot route.
- **P09-G08** No real drone command issued from observation-only/simulator environment.
## Deliverable/receipt list
- Mission entity lifecycle diagram and planned/actual feature adapters.
- Integrated mission planner and map screenshots; test for geometry/time/QA.
- Permissions and driver status matrix + emergency/abort simulation labeling.
- Negative device/source fixtures and explicit physical-trial HOLD status.
**HOLD condition:** simulated flight represented as real or physical dispatch possible without independent driver authorization.
## Multi-agent orchestration for this pass
R0 owner pins source SHA and current code; R1 owner & independent specialist separately prepare tests/approach; R2 scientific A4 and safety A6 challenge data authority and actual/simulated boundaries; R3 A7 executes negative gates; R4 A2/A3/A8 verify map interactions in real browser; R5 A0 records GO/HOLD with exact receipt links. These are **planned review duties**, not claims of review already performed.

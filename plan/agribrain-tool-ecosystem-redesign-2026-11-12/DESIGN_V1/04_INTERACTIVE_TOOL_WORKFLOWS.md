# Design Pass 04 — Cross-Tool User Journeys and Interaction Matrix
**Objective:** interaction between tools, not isolated full-screen dashboards. The map is the spatial hub; each tool contributes governed layers and contextual actions.

## 1 — Sensor-to-ASMAE investigation
**Trigger:** user selects physical moisture probe on map or in Sensor Network.
- Map centers on the registered point; selected icon is highlighted. Inspector shows device ID, depth cm/interval, placement class, measurement timestamp, battery and calibration/health (only when actual data present).
- Sensor tab displays latest raw/normalized readings and chart; timeline marks actual observation instant and first-availability time.
- Related ASMAE state links `root_zone_water`, `surface_wetness_event`, `canopy_water` appear as candidate comparisons; panel may show associated posterior/sigma from selected snapshot. It must not claim that the selected sensor influenced ASMAE absent a signed evidence-edge.
- If a source receipt links reading to accepted evidence and posterior, show `Contributed to selected run`, complete with provenance. If merely nearby show `Nearby, not verified as assimilated`.
- Actions: View calibration, compare nearest valid state, open sensor placement plan, schedule field sample. No actuation.

## 2 — Zone-to-drone mission
**Trigger:** user selects a qualified SIRE anomaly zone.
- Keep zone geometry selected; source surface, severity and uncertainty in inspector. "Inspect with Drone" opens drone planner seeded with exact authorized target-zone geometry.
- Map draws *planned* coverage and waypoints as dashed/outlined geometry. Editing pattern/GSD/overlap updates plan preview with a new plan version, not a fake flight.
- Drone tool retains zone, SIRE snapshot and provenance. Preflight needs actual vehicle weather/geofence data; mock status cannot pass a real-aircraft dispatch gate.
- Upon actual telemetry receipt (when hardware integrated), independently render executed track, timestamped positions and camera captures; compare planned vs actual.
- Orthomosaic QA product may be reviewed over the selected zone. It remains an observation candidate until Layer0/Layer1 admission and downstream scientific publication.

## 3 — MESIA receiver and field experiment
**Trigger:** user selects registered MESIA receiver or opens Tool Library -> MESIA.
- Map shows receiver only if manifest has verified coordinates; coverage graph shows valid area or explicit `UNKNOWN` for spatial coverage. A frequency band alone is not a geographic footprint.
- MESIA inspector shows hardware/antenna calibration epochs, observable frequencies, health and actual signal evidence if present.
- Open Experiment Studio with selected receiver/plot zone, choose controlled source, variable, baseline, hypothesis, control, time window and acquisition protocol.
- Preview a hypothetical coverage/response simulation in visually distinct overlay; execution of real E0/E2 trials remains disabled/setup-pending until physical instruments, logger imports and persisted experiment receipts exist.
- Valid result can be proposed for evidence admission but not automatically asserted as a measured state.

## 4 — ASMAE 13-state explorer / scientific cursor
**Trigger:** select any canonical state by key.
- State list shows all 13 even if all unidentifiable/not rendered. State panel includes role, units, summary posterior, uncertainty, ledger support, authority, latest related event and historical availability.
- If qualified raster exists, map loads exact surface ID + publication and legend/valid mask/sigma. If only field-wide posterior exists, map remains satellite + plot boundary and right panel shows a plot-level estimate.
- Click eligible cell, zone or draw transect; graphs update to that cell/grid-support, never a made-up sub-pixel precision. Clicking 'compare' opens synchronized state vs state or snapshot vs snapshot with independent qualification.
- A particular radar, drone or probe observation appears in Evidence panel only as `related` unless exact scientific lineage proves support.
- 13 frozen coordinates remain unchanged; new derived indices are in separate diagnostic catalog, not an invented fourteenth ASMAE coordinate.

## 5 — Event timeline / historical scientific replay
**Trigger:** scrub or click rain, irrigation observed event, camera capture, satellite acquisition, mission action, sample or publication event.
- Highlight event's actual geometry when present; otherwise show event in timeline with spatial scope known (plot/zone/no location).
- Load publication available at selected knowledge cutoff, not merely closest temporal observation. Browser must never backfill a past snapshot with data admitted later.
- Show historical/forecast/simulation ribbons and valid time; link source acquisitions and credible state change candidates, not causal conclusions based solely on time adjacency.

## 6 — Interactive What-If / Water and agronomy tools
**Trigger:** select zone, open Water Lab, nutrient, disease, yield or experiment tool.
- Snapshot scientific baseline and source identity. Adjust a sandbox assumption (rain, irrigation, temperature, nutrient, crop) with a clear label **HYPOTHETICAL**.
- Map can show scenario overlay only where the scenario engine provides valid spatial geometry; plot-level scenario displays cards/charts, not fabricated map raster.
- Side-by-side baseline vs simulation clearly identifies uncertainty, assumptions, model/version, zone and time. A scenario result never becomes actual observation or a canonical SIRE publication by UI state change.
- User may create a scouting/sampling or review task; no signed irrigation, fertigation or chemical dispatch in observation-only pilot.

## 7 — Ground truth / farmer photo / inspection
- User drags map pin or chooses registered geolocation (if allowed) to attach a photo/sample. Recorded coordinate is tagged `user_provided`, not precise geolocation from device metadata.
- Upload and QA/review create a candidate observation/evidence object. Spatial sampling and identity checks precede any scientific acceptance.
- Clicking attached photo on map opens corresponding time and evidence details. Model results (crop/disease suspicion) are predictions with confidence, not definitive field diagnosis.

## 8 — Planning / crop suitability / operations
- Choose forecast/planning surface -> select eligible zone -> inspect planting window, rotation, resource and economic assumptions.
- Create a proposal/task with immutable target geometry reference, approved-by field (if required) and status transitions.
- Planned, authorized, dispatched and confirmed completed are distinct. A task is not complete because it was displayed on the map.

## Multi-tool correlation matrix
| Selection | Map highlights | Inspector tab | Suggested tools | Relationship qualification |
|---|---|---|---|---|
| Sensor device | registered point | health+reading+depth | calibration, ASMAE, events | nearby vs assimilated |
| ASMAE state | surface or plot-level support | posterior+sigma+role | evidence, history, what-if | proof to publication |
| SIRE zone | polygon | causes? evidence/uncertainty | drone, scouting, experiments | zones from committed raster |
| Drone plan | route/target | planner+preflight | image, weather, events | plan vs actual telemetry |
| Drone live track | timed line/point | fleet telemetry | image capture, compare | authenticated hardware record |
| MESIA receiver | point/qualified coverage | RF manifest/calibration | wave, experiments, ASMAE | observational capability vs sensing |
| Field event | point/zone/plot/none | event origin and clocks | history, evidence, tasks | observation vs modeled |
| Experiment | trial boundary/hypothetical footprint | protocol/results | compare, report | sandbox vs qualified trial |
| Photo/sample | geotagged point if supplied | photo/QA | diagnosis, validation | candidate vs admitted |
| Task | validated location/area | assignment/status | field operations | proposed vs confirmed |

## Negative behavior (explicit)
No invented sensor coordinates, pretend drone flight, implied RF coverage, simulated camera PTZ acknowledgment, plot-level event pin at centroid, hardcoded treatment advice, synthetic pixel variance, statistical certainty without validation, or spatial-proximity-as-causation.

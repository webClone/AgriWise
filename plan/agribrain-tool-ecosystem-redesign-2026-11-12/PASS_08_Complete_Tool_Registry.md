# Pass 08 — Complete intended Tool Library: every capability remains discoverable
**Interpretation:** This is an *inclusive product blueprint*, not a list of operationally certified features. Code indicates some current backend/UI implementation, but every tool needs its own acceptance qualification. Readiness labels apply to individual capabilities and often to individual actions, not entire modules.
## Readiness and access badges
- **Built/UI** = an application interface exists; underlying connectors may be incomplete.
- **Engine** = backend computation/module present, frontend or field integration may be incomplete.
- **Prototype** = code/proof or simulation mode present, not production validated.
- **Hardware** = needs actual sensor/drone/receiver/instrument data and verified deployment.
- **Future** = desired tool/interaction not yet demonstrated.
All five appear in Tool Library. An unavailable tool can open a read-only explanatory workspace, mock preview or setup checklist, but must never imply successful live output. An 'All' filter returns the entire library.
## Acquisition and observation (17)
| Tool | Grounded source or intended integration | Default map representation |
|---|---|---|
| Satellite Scene Explorer | L0 S1/S2, visual_sources | Scene footprint / tile |
| Satellite Revisit & Cloud Audit | L0 satellite/quality | Coverage + time |
| Sentinel-1 SAR Inspector | L0/sentinel1 | Qualified raster |
| Vegetation Spectral Index Lab | L0 and SIRE | NDVI/NDMI indexed raster |
| Weather & Forecast Explorer | L0/environment/weather | Station/provider coverage |
| Soil/DEM/Landcover Context | L0/geo_context/environment | Grounded raster polygons |
| Sensor Network Map | sensor_runtime.registry | Registered points |
| Live Observation Stream | sensor_runtime + Next telemetry | Sensor points + time |
| Sensor Calibration & QA | sensor_runtime.calibration | Selected device |
| Sensor Health & Alerts | sensor_runtime.health/alerting | Points/events where confirmed |
| Soil Depth Profile | sensor registration depth & readings | Point + vertical panel |
| Device Placement/Gap Planner | proposed over registered points | Planned geometry |
| IP Camera Viewer | ip_camera_runtime | Registered point/FOV |
| Camera PTZ Simulator | PTZController is simulated | Simulation only |
| Farmer Photo/Report | L0 farmer_photo, ground_truth | Geotagged photo point |
| Ground Truth & Sample Manager | ground_truth | Point/zone/evidence |
| Acquisition Conflict / Reliability | L1 fusion, SIRE uncertainty | Qualified support/conflict |
## ASMAE and scientific interpretation (12)
| Tool | Output/map |
|---|---|
| 13-State Explorer | 13 catalog rows, eligible raster when available |
| State Uncertainty Inspector | Sigma/posterior plot or map |
| Cross-State Correlation | Covariance chart, geospatial selector |
| Assimilation Ledger | Evidence/time-linked diagnostics |
| Scene & Data-Lineage Viewer | Source footprints and proof |
| Zone Laboratory | Grounded zones |
| Pixel/Transect Inspector | Map probe/transect |
| Temporal Time-Peel | Committed past/forecast layers |
| Historical Events & Stress Memory | Dated plot/zone events |
| State Retrovalidation | Held-out test/diagnostic; no false certainty |
| BMA/Model Disagreement | Qualified disagreement surface |
| Scientific Provenance & Export | Map/publication identity/export manifest |
## Drones and aerial imaging (13)
Mission Planner; Coverage/Overlap Designer; Targeted Hotspot Flight; Preflight Checklist; Drone Fleet/Connectivity; Planned Waypoint Preview; Real Flight Tracker (hardware); Paused/RTL/Abort Control (hardware/permissions); Mission Event Timeline; Flight History; Orthomosaic Builder; Drone Imagery Compare; Refly/QA/Revisit Planner.
## MESIA and radio research (15)
Receiver Network; Observability/Coverage Map; Blind-Sector Analyzer; Spectrum/Signal Viewer; GNSS Reflectometry; Wi-Fi CSI; Cellular Link Analyzer; LoRa/LPWAN; RFID/Backscatter; Radar/MmWave; UWB/GPR; Dielectric Inversion Lab; Antenna Pose/Calibration; ASMAE Supervisor; Physical Experiment Campaign (hardware gated).
## Agronomy and biology (19)
Crop Identity; Phenology Calendar; Crop/Soil Profile; Water Stress; Root-Zone Hydraulic Model; Irrigation History; Irrigation What-if (simulation); Salinity Explorer; Nutrient Risk; Nutrient Demand/Loss; VRA Rate Preview (not authorized dosage); Disease/Biotic Pressure; Scouting and Sampling; Suitability Map; Planting Window; Crop Rotation; Yield Trajectory; Economic Scenario; Field Health Comparison.
## Operations, AI and research (18)
Field Event Ledger; Field Tasks; Operational Feasibility; Intervention Planning (read-only, authorization bounded); Equipment Simulator; Camera Review; Expert AI Investigator; Farmer Explanation; What-if Lab; Comparative Experiments; Controlled Field Trial Manager; Calibration Experiment; Hypothesis Notebook; Report Builder; Evidence Export; Alert & Follow-up Center; Future World-Model Studio; Future Omega Research Console.
**Total catalog concepts:** 94 named entries (17 + 12 + 13 + 15 + 19 + 18). Some overlap by tool family intentionally and must later be deduplicated into canonical tool IDs. 'Complete intended interface' means comprehensive discoverability, not 94 working independent backend services.
## UX organization
Tool dock = user-pinned 5–8 tools. Tool Library = searchable/filterable, category browsing, 'All', 'Experimental', 'Hardware', 'Future' filters. Context action = 'Open with' compatible tools from any map object. Each tool supports contextual side panel and, for complex work, full workbench reusing the same plot/time/selection.
## Strict semantics
No fake pins for missing coordinates, no random aerial flight as telemetry, no generic 'observed' for model priors, no scenario as canonical, no automatic actuation. Plan uses one consistent style and placeholders clearly labeled; planned tools can be interacted with through configuration and previews but cannot claim execution.

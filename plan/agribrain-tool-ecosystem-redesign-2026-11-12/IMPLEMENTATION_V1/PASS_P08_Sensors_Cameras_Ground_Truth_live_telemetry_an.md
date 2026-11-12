# P08 — Sensors Cameras Ground Truth live telemetry and map-first network management
**Status:** NOT STARTED · **Prerequisites:** P04,P05,P06 · **Primary agents:** A5+A3+A6 · **Independent verification:** A7 + A6 / A4  
**Proposed code branch:** `feat/plot-workspace-p08-observation-devices` (not created).
## Product scope and safety boundary
Preserve and extend the existing sensor and camera workspaces into truly map-linked observation tools. Every registered sensor can be selected on map or in list, with depth/calibration/health and observation chronology; unlocated or offline devices remain visible in lists. Do not promote operational telemetry into scientific evidence without admission.
## Source targets
- `services/agribrain/sensor_runtime/registry.py`
- `services/agribrain/sensor_runtime/ingestion.py`
- `services/agribrain/sensor_runtime/calibration.py`
- `services/agribrain/sensor_runtime/health.py`
- `services/agribrain/sensor_runtime/alerting.py`
- `services/agribrain/ground_truth/registry.py`
- `services/agribrain/ip_camera_runtime/ptz_controller.py`
- `src/app/api/plots/[id]/sensors/status/route.ts`
- `src/app/api/plots/[id]/telemetry/route.ts`
- `src/hooks/usePlotTelemetry.ts`
- `src/components/farm/intelligence/SensorNetworkWorkspace.tsx`
- `src/components/farm/workspace/SensorMapTool.tsx (proposed)`
## Ordered execution packages
### P08.01 — Device and observation identity model
Map `deviceId`/registry epoch/farm/plot/zone/depth/registered WGS84/status/calibration to feature ID; separately identify each physical reading's source timestamp, ingested time and acceptance receipt. Never use RSSI or measurement value as implicit geolocation.

### P08.02 — Sensor coverage and placement view
Render registered devices as points with type and health; show depth/interval in side inspector and chart, not invented area footprint. Distinguish measured spatial support vs indicative sensor placement. Add optional proposed placement geometry with preview label.

### P08.03 — Historical and live synchronized readings
Select device on map -> sensor panel shows normalized/raw records and calibration, timeline highlights observedAt/firstAvailableAt. Live stream status remains LIVE_UNCERTIFIED unless manifest bound; historical snapshot does not backfill later readings.

### P08.04 — Graph and local state comparison
Display time-series depth chart and plot-wide root-zone ASMAE estimate side-by-side, with confidence and spatial-support caveat. Show 'admitted to this scientific run' only with exact evidence-to-publication link; otherwise label proximity/available observation.

### P08.05 — Camera and farmer evidence integration
Camera markers only at registered coordinates; orientation/FOV only if verified; PTZ has simulated state until real driver handshake and audit. Photo and sampling points carry source geotags, separate ground-truth QA/admission.

### P08.06 — Device health and alert semantics
Use persisted status when available; existing sensor alert dispatcher only prints stderr, so design new event persistence/adapters rather than pretend timeline exists. Alert cards explain offline, degraded signal, calibration expired and ingestion quarantine separately.

### P08.07 — Unknown/missing/retired cases
No coordinate -> list-only row and locate prompt; retired stays history but no fake active pin. Unknown depth -> do not show numerical root-zone comparison at an assumed 15 cm.

### P08.08 — Bulk/touch operations and performance
Cluster 500+ devices with zoom; show counts by type/status and filtered list; no per-pin polling. Scope-scoped query and bounded 30s telemetry refresh or better event transport when actually supported.

### P08.09 — Safety and tests
Reject foreign plot, forged device coordinate, uncalibrated source, invalid observation instant, signature mismatch and replay. Map UI cannot set `state_update_allowed` by checkbox.
## Pass-specific adversarial acceptance
- **P08-G01** Map point and device list click identify exact same registered device and time scope.
- **P08-G02** Unregistered/missing coordinates produce no map pin, still visible in tools.
- **P08-G03** Sensor at 15cm and 30cm maintain correct depth in side panel/ASMAE comparison.
- **P08-G04** Uncalibrated or unverified reading is not shown as assimilated evidence.
- **P08-G05** Actual camera PTZ move cannot be claimed from simulated controller return.
- **P08-G06** Alert not persisted is labeled a runtime diagnostic, not durable field alarm.
- **P08-G07** Foreign tenant sensor never appears in map response or screenshot.
- **P08-G08** Large 500-device test with no per-pin request explosion.
## Deliverable/receipt list
- Sensor/camera/photo entity adapters, unit/coordinates/epoch validation.
- Sensor Network workspace with map↔list↔timeline parity screenshots.
- Offline/uncalibrated/missing-coordinate tests; calibration proof semantics.
- QA report, field hardware-unverified declaration and permissions review.
**HOLD condition:** sensor coordinate fabrication, hidden uncalibrated admission or camera simulated result shown as physical.
## Multi-agent orchestration for this pass
R0 owner pins source SHA and current code; R1 owner & independent specialist separately prepare tests/approach; R2 scientific A4 and safety A6 challenge data authority and actual/simulated boundaries; R3 A7 executes negative gates; R4 A2/A3/A8 verify map interactions in real browser; R5 A0 records GO/HOLD with exact receipt links. These are **planned review duties**, not claims of review already performed.

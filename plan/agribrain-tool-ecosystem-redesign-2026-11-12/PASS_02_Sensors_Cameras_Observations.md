# Pass 02 — Sensor network, IP cameras, observation ingestion and map links
**Source:** `sensor_runtime/registry.py`, `ingestion.py`, `health.py`, `security.py`, `replay.py`, `alerting.py`; `layer0/sensors/irrigation_event_detector.py`; `ip_camera_runtime/registry.py`, `ptz_controller.py`; `ground_truth/schemas.py`; Next `src/app/api/plots/[id]/sensors/status/route.ts`, `src/components/farm/intelligence/SensorNetworkWorkspace.tsx`.
## Source facts
- `SensorDeviceRegistration` has WGS84 latitude/longitude, farm/plot/zone, depth, placement_type, installation time, calibration and health metadata. **This is enough to design sensor pins, depth profiles and device coverage** without deriving fictitious positions.
- Source ingestion checks authenticated identity, rate limit, replay protection, registered variables and calibration; assigns canonical plot and zone IDs. A raw received measurement is not automatically science-authorized.
- Frontend sensor status API fetches Prisma device/status/readings but does **not** expose coordinates or altitude/depth in its response. Dedicated read-only, owner-scoped map-feature endpoint/projection is needed.
- Sensor alerts `dispatch_sensor_alert` currently writes to stderr, not a persisted interactive alert feed. Design alerts as a future durable event adapter, not as already live in-product.
- `ip_camera_runtime.ptz_controller` labels preset movement simulated. Camera inventory can be shown as a tool; live PTZ actions are hardware-dependent and must not imply movement.
- GroundTruthEvidence defines point/zone/plot/raster/event scope and optional geometry; photo evidence can be a point, but no coordinates means an unlocated item, not a fabricated pin.
## Tool family (all in intended library)
Sensor Map; Live/Latest Readings; Multi-depth Soil Profile; Device Calibration; Device Health; Placement Coverage; Offline/Drift/Replay Inspector; Sensor Conflict Viewer; Alarm Center; Sensor Replay; IP Camera Viewer; Camera Orientation/PTZ; Ground-Truth Samples; Farmer Photo Geotagging; Irrigation Flow Event Detector; Weather Station Inspector.
## Interaction example
Select soil probe pin -> map centers on registered location -> device panel opens history + depth + battery + calibration -> ASMAE root-zone chart displays nearest available admitted comparison (never claims direct causal influence without evidence linkage) -> timeline highlights observation timestamp.
## Needed contracts
Owner-scoped device feature: `{id, plotId, coordinates, locationSource:'registered', zoneId, depthCm, seenAt, lastReadingAt, health, calibrationState, evidenceRefs, locationQuality}`. Registered coordinate != sensor sample footprint; distinguish approximate support radius.
## Tests/gates
A sensor foreign to the plot is not returned; invalid/missing geometry produces list-only entry; calibration-invalid reading cannot alter scientific posterior; offline status is based on telemetry freshness; device pin moves only when registry epoch changes; sensor alerts are persistent before labeled operational.

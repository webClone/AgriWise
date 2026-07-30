"""
Layer 0 Perception Engine — Specialized image-to-observation pipelines.

Four engine families, each tuned to its source type:
  - satellite_rgb:  Sentinel-2 / Landsat plot-scale structural intelligence
  - farmer_photo:   Phone/camera close-range field observation  (planned)
  - drone:          Orthomosaic / frameset spatial analysis       (planned)
  - ip_camera:      Continuous stationary monitoring              (planned)

All engines share:
  - common/contracts.py  — PerceptionEngineInput/Output base types
  - common/packet_adapter.py — single exit point into ObservationPacket[]

No engine should emit recommendations or overwrite state directly.
Every output carries uncertainty and provenance.
"""

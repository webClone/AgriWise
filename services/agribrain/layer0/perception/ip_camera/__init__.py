"""
IP Camera Perception Engine — PLANNED.

Will handle continuous stationary monitoring:
  - Focus/exposure/timestamp drift QA
  - Temporal canopy tracking
  - Growth rate estimation from sequential frames
  - Weather event detection (frost, storm)
  - Stateful scene memory

This is the fourth engine to implement (Phase D).
It is the most stateful and benefits from the others being stable first.
"""

# TODO: Implement ip_camera engine
# Sprint order: after drone is stable
# Key difference from satellite_rgb:
#   - Continuous temporal stream (not single snapshots)
#   - Fixed viewpoint → change detection is primary signal
#   - Stateful scene memory (reference frames)
#   - Timestamp drift detection
#   - Night/weather filtering

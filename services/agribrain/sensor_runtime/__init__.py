"""
Sensor Runtime Package
Provides unified namespace bridging between sensor_runtime and services.agribrain.sensor_runtime (F37).
"""

import sys

# Ensure both sensor_runtime and services.agribrain.sensor_runtime share identical module references
for _sub in ("schemas", "device_identity", "security", "decoder", "registry", "calibration", "storage", "ingestion"):
    _full = f"services.agribrain.sensor_runtime.{_sub}"
    _short = f"sensor_runtime.{_sub}"
    if _full in sys.modules and _short not in sys.modules:
        sys.modules[_short] = sys.modules[_full]
    elif _short in sys.modules and _full not in sys.modules:
        sys.modules[_full] = sys.modules[_short]

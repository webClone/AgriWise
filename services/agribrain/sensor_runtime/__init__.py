"""
Sensor Runtime Package
Provides unified namespace bridging between sensor_runtime and services.agribrain.sensor_runtime (F37).
Enforces single canonical package identity across all submodules in every import order.
"""

import sys
import importlib
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec

try:
    import services.agribrain
except Exception:
    pass

# Ensure root package cross-aliasing
if "sensor_runtime" in sys.modules and "services.agribrain.sensor_runtime" not in sys.modules:
    sys.modules["services.agribrain.sensor_runtime"] = sys.modules["sensor_runtime"]
    if "services.agribrain" in sys.modules:
        setattr(sys.modules["services.agribrain"], "sensor_runtime", sys.modules["sensor_runtime"])
elif "services.agribrain.sensor_runtime" in sys.modules and "sensor_runtime" not in sys.modules:
    sys.modules["sensor_runtime"] = sys.modules["services.agribrain.sensor_runtime"]


class _AliasLoader(Loader):
    def __init__(self, target_module):
        self.target_module = target_module

    def create_module(self, spec):
        return self.target_module

    def exec_module(self, module):
        pass

    def load_module(self, fullname):
        sys.modules[fullname] = self.target_module
        return self.target_module


class _SensorRuntimeNamespaceBridge(MetaPathFinder):
    """Compatibility import finder ensuring one canonical class and module identity (F37)."""
    _in_progress = False

    def find_spec(self, fullname, path, target=None):
        if self._in_progress:
            return None

        # Route services.agribrain.sensor_runtime.* directly to sensor_runtime.*
        if fullname.startswith("services.agribrain.sensor_runtime."):
            sub = fullname[len("services.agribrain.sensor_runtime."):]
            short_name = f"sensor_runtime.{sub}"
            if short_name in sys.modules:
                mod = sys.modules[short_name]
                sys.modules[fullname] = mod
                parent = sys.modules.get("services.agribrain.sensor_runtime")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                return ModuleSpec(fullname, _AliasLoader(mod))
            self._in_progress = True
            try:
                mod = importlib.import_module(short_name)
                sys.modules[fullname] = mod
                parent = sys.modules.get("services.agribrain.sensor_runtime")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                return ModuleSpec(fullname, _AliasLoader(mod))
            except Exception:
                return None
            finally:
                self._in_progress = False

        # Route sensor_runtime.* to services.agribrain.sensor_runtime.*
        elif fullname.startswith("sensor_runtime."):
            sub = fullname[len("sensor_runtime."):]
            full_name = f"services.agribrain.sensor_runtime.{sub}"
            if full_name in sys.modules:
                mod = sys.modules[full_name]
                sys.modules[fullname] = mod
                parent = sys.modules.get("sensor_runtime")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                return ModuleSpec(fullname, _AliasLoader(mod))
            self._in_progress = True
            try:
                mod = importlib.import_module(full_name)
                sys.modules[fullname] = mod
                parent = sys.modules.get("sensor_runtime")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                return ModuleSpec(fullname, _AliasLoader(mod))
            except Exception:
                return None
            finally:
                self._in_progress = False

        return None


# Install finder if not already registered
if not any(isinstance(finder, _SensorRuntimeNamespaceBridge) for finder in sys.meta_path):
    sys.meta_path.insert(0, _SensorRuntimeNamespaceBridge())

# Synchronize any already loaded submodules
for _sub in ("schemas", "device_identity", "security", "decoder", "registry", "calibration", "storage", "ingestion", "normalization", "alerting", "health", "maintenance", "replay"):
    _full = f"services.agribrain.sensor_runtime.{_sub}"
    _short = f"sensor_runtime.{_sub}"
    if _full in sys.modules and _short not in sys.modules:
        sys.modules[_short] = sys.modules[_full]
    elif _short in sys.modules and _full not in sys.modules:
        sys.modules[_full] = sys.modules[_short]

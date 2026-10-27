"""
Irrigation Runtime — Hardware-Agnostic Smart Irrigation Control System

This package bridges AgriBrain's agronomic intelligence (L3 Water → L6 Execution
→ L8 Prescriptive) to physical irrigation hardware across diverse protocols
(MQTT, LoRaWAN, Modbus RTU/TCP, HTTP/REST).

Architecture:
  L8 ActionCard (IRRIGATE)
    → IrrigationScheduler (weather/quota/phenology merge)
    → CommandDispatcher (state machine)
    → ActuatorRegistry (device → driver mapping)
    → HardwareDriver (protocol-specific payload)
    → SafetyMonitor (interlocks + fail-safe)
    → IrrigationValidator (closed-loop soil moisture verification)

Supported Hardware:
  - Drip systems (solenoid valves via MQTT/LoRaWAN)
  - Center pivots (Lindsay FieldNET, Valley ICON via HTTP)
  - Sprinkler systems (Hunter, Rain Bird, Toro via MQTT/Modbus)
  - Flood/furrow (gate actuators via Modbus)
  - Micro-spray (Netafim via HTTP/MQTT)
  - Subsurface drip (SDI controllers via Modbus)

Automation Modes:
  - MANUAL: farmer triggers all irrigation events
  - SEMI_AUTO: L8 recommends, farmer confirms, L6 executes
  - FULL_AUTO: critical events execute autonomously (configurable)

Contract version: 1.0.0
"""

__version__ = "1.0.0"

import sys
import importlib
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec

try:
    import services.agribrain
except Exception:
    pass

# Ensure root package cross-aliasing
if "irrigation_runtime" in sys.modules and "services.agribrain.irrigation_runtime" not in sys.modules:
    sys.modules["services.agribrain.irrigation_runtime"] = sys.modules["irrigation_runtime"]
    if "services.agribrain" in sys.modules:
        setattr(sys.modules["services.agribrain"], "irrigation_runtime", sys.modules["irrigation_runtime"])
elif "services.agribrain.irrigation_runtime" in sys.modules and "irrigation_runtime" not in sys.modules:
    sys.modules["irrigation_runtime"] = sys.modules["services.agribrain.irrigation_runtime"]


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


class _IrrigationRuntimeNamespaceBridge(MetaPathFinder):
    """Compatibility import finder ensuring one canonical class and module identity (F37)."""
    _in_progress = False

    def find_spec(self, fullname, path, target=None):
        if self._in_progress:
            return None

        # Route services.agribrain.irrigation_runtime.* directly to irrigation_runtime.*
        if fullname.startswith("services.agribrain.irrigation_runtime."):
            sub = fullname[len("services.agribrain.irrigation_runtime."):]
            short_name = f"irrigation_runtime.{sub}"
            if short_name in sys.modules:
                mod = sys.modules[short_name]
                sys.modules[fullname] = mod
                parent = sys.modules.get("services.agribrain.irrigation_runtime")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                return ModuleSpec(fullname, _AliasLoader(mod))
            self._in_progress = True
            try:
                mod = importlib.import_module(short_name)
                sys.modules[fullname] = mod
                parent = sys.modules.get("services.agribrain.irrigation_runtime")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                return ModuleSpec(fullname, _AliasLoader(mod))
            except Exception:
                return None
            finally:
                self._in_progress = False

        # Route irrigation_runtime.* to services.agribrain.irrigation_runtime.*
        elif fullname.startswith("irrigation_runtime."):
            sub = fullname[len("irrigation_runtime."):]
            full_name = f"services.agribrain.irrigation_runtime.{sub}"
            if full_name in sys.modules:
                mod = sys.modules[full_name]
                sys.modules[fullname] = mod
                parent = sys.modules.get("irrigation_runtime")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                return ModuleSpec(fullname, _AliasLoader(mod))
            self._in_progress = True
            try:
                mod = importlib.import_module(full_name)
                sys.modules[fullname] = mod
                parent = sys.modules.get("irrigation_runtime")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                return ModuleSpec(fullname, _AliasLoader(mod))
            except Exception:
                return None
            finally:
                self._in_progress = False

        return None


# Install finder if not already registered
if not any(isinstance(finder, _IrrigationRuntimeNamespaceBridge) for finder in sys.meta_path):
    sys.meta_path.insert(0, _IrrigationRuntimeNamespaceBridge())

# Synchronize any already loaded submodules
for _sub in ("schemas", "actuator", "dispatcher", "safety", "registry", "scheduler", "validator"):
    _full = f"services.agribrain.irrigation_runtime.{_sub}"
    _short = f"irrigation_runtime.{_sub}"
    if _full in sys.modules and _short not in sys.modules:
        sys.modules[_short] = sys.modules[_full]
    elif _short in sys.modules and _full not in sys.modules:
        sys.modules[_full] = sys.modules[_short]


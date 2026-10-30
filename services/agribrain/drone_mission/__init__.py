"""
Drone Mission Package
Provides unified namespace bridging between drone_mission and services.agribrain.drone_mission (F37).
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
if "drone_mission" in sys.modules and "services.agribrain.drone_mission" not in sys.modules:
    sys.modules["services.agribrain.drone_mission"] = sys.modules["drone_mission"]
    if "services.agribrain" in sys.modules:
        setattr(sys.modules["services.agribrain"], "drone_mission", sys.modules["drone_mission"])
elif "services.agribrain.drone_mission" in sys.modules and "drone_mission" not in sys.modules:
    sys.modules["drone_mission"] = sys.modules["services.agribrain.drone_mission"]


class _AliasLoader(Loader):
    def __init__(self, target_module, fullname=None, aliasname=None):
        self.target_module = target_module
        self.fullname = fullname
        self.aliasname = aliasname

    def create_module(self, spec):
        return self.target_module

    def exec_module(self, module):
        if self.fullname:
            sys.modules[self.fullname] = self.target_module
        if self.aliasname:
            sys.modules[self.aliasname] = self.target_module

    def load_module(self, fullname):
        sys.modules[fullname] = self.target_module
        if self.aliasname:
            sys.modules[self.aliasname] = self.target_module
        return self.target_module


def _sync_drone_submodules():
    for _sub in ("schemas", "capability_profiles", "command_agent", "planner", "mission_selector", "anomaly_bridge", "refly_planner", "coverage_patterns", "safety_rules", "mission_history"):
        _full = f"services.agribrain.drone_mission.{_sub}"
        _short = f"drone_mission.{_sub}"
        _m_full = sys.modules.get(_full)
        _m_short = sys.modules.get(_short)
        if _m_full and not _m_short:
            sys.modules[_short] = _m_full
        elif _m_short and not _m_full:
            sys.modules[_full] = _m_short
        elif _m_full and _m_short and _m_full is not _m_short:
            sys.modules[_full] = _m_short


class _DroneMissionNamespaceBridge(MetaPathFinder):
    """Compatibility import finder ensuring one canonical class and module identity (F37)."""
    _in_progress = False

    def find_spec(self, fullname, path, target=None):
        if self._in_progress:
            return None

        # Route services.agribrain.drone_mission.* directly to drone_mission.*
        if fullname.startswith("services.agribrain.drone_mission."):
            sub = fullname[len("services.agribrain.drone_mission."):]
            short_name = f"drone_mission.{sub}"
            if short_name in sys.modules:
                mod = sys.modules[short_name]
                sys.modules[fullname] = mod
                parent = sys.modules.get("services.agribrain.drone_mission")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                _sync_drone_submodules()
                return ModuleSpec(fullname, _AliasLoader(mod, fullname, short_name))
            self._in_progress = True
            try:
                mod = importlib.import_module(short_name)
                sys.modules[fullname] = mod
                parent = sys.modules.get("services.agribrain.drone_mission")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                _sync_drone_submodules()
                return ModuleSpec(fullname, _AliasLoader(mod, fullname, short_name))
            except Exception:
                return None
            finally:
                self._in_progress = False

        # Route drone_mission.* to services.agribrain.drone_mission.*
        elif fullname.startswith("drone_mission."):
            sub = fullname[len("drone_mission."):]
            full_name = f"services.agribrain.drone_mission.{sub}"
            if full_name in sys.modules:
                mod = sys.modules[full_name]
                sys.modules[fullname] = mod
                parent = sys.modules.get("drone_mission")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                _sync_drone_submodules()
                return ModuleSpec(fullname, _AliasLoader(mod, fullname, full_name))
            self._in_progress = True
            try:
                mod = importlib.import_module(full_name)
                sys.modules[fullname] = mod
                parent = sys.modules.get("drone_mission")
                if parent is not None:
                    setattr(parent, sub.split(".")[0], mod)
                _sync_drone_submodules()
                return ModuleSpec(fullname, _AliasLoader(mod, fullname, full_name))
            except Exception:
                return None
            finally:
                self._in_progress = False

        return None


# Install finder if not already registered
if not any(isinstance(finder, _DroneMissionNamespaceBridge) for finder in sys.meta_path):
    sys.meta_path.insert(0, _DroneMissionNamespaceBridge())

# Synchronize any already loaded submodules
_sync_drone_submodules()

from .schemas import MissionType, FlightMode, MissionIntent, FlightPlan, DroneCapabilityProfile
from .capability_profiles import get_profile
from .command_agent import DroneCommandAgent
from .planner import DroneMissionPlanner

__all__ = [
    "MissionType",
    "FlightMode",
    "MissionIntent",
    "FlightPlan",
    "DroneCapabilityProfile",
    "get_profile",
    "DroneCommandAgent",
    "DroneMissionPlanner"
]

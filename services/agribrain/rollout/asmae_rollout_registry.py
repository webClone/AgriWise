"""
ASMAE Rollout Registry.
Manages the controlled rollout of the ASMAE engine on a per-plot basis.
Stores registry configurations in a local JSON file and logs audit decisions.
"""

from __future__ import annotations
import json
import os
import time
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY_DIR = Path(__file__).parent.resolve()
REGISTRY_FILE = REGISTRY_DIR / "asmae_rollout_registry.json"
AUDIT_LOG_FILE = REGISTRY_DIR.parent / "artifacts" / "rollout_audit.log"

PRODUCTION_ROLLOUT_REGISTRY = {
    "plot_test_001": "backend_observation",
    "oued_souf_plot": "backend_observation",
    "timimoun_plot": "backend_observation",
    "boufarik_plot": "backend_observation",
    "v50b_oued_souf_10ha": "backend_observation",
    "6a09d9e91dd0c7ed6fce7d50": "backend_observation",
}

ARCHIVE_PILOT_REGISTRY = {
    "plot_test_001": "pilot_baseline",
    "v50b_oued_souf_10ha": "pilot_internal",
    "timimoun_plot": "pilot_internal",
    "boufarik_plot": "pilot_internal",
    "oued_souf_plot": "pilot_internal",
    "sparse_plot": "pilot_fixture",
    "6a09d9e91dd0c7ed6fce7d50": "pilot_internal",
}


TEST_FIXTURE_ROLLOUT_REGISTRY = {
    "p1": "visual_test_user",
    "test_plot": "visual_test_user",
    "test_runner_plot": "visual_test_user",
    "gate_fixture_plot": "visual_test_user",
    "scen2": "visual_test_user",
    "scen3": "visual_test_user",
    "scen4": "visual_test_user",
    
    # Compatibility and defaults
    "default": "visual_test_user",
    "unknown": "visual_test_user",
    
    # Additional test plot IDs
    "gate_plot": "visual_test_user",
    "haze_plot": "visual_test_user",
    "healthy_plot": "visual_test_user",
    "narrow_strip_plot": "visual_test_user",
    
    # Unit test plot IDs
    "plot": "visual_test_user",
    "plot-1": "visual_test_user",
    "plot-2": "visual_test_user",
    "plot1": "visual_test_user",
    "plot123": "visual_test_user",
    "plot2": "visual_test_user",
    "plotA": "visual_test_user",
    "plotA_data": "visual_test_user",
    "plotB": "visual_test_user",
    "plotB_data": "visual_test_user",
    "plot_1": "visual_test_user",
    "plot_123": "visual_test_user",
    "plot_A": "visual_test_user",
    "plot_B": "visual_test_user",
    "plot_C": "visual_test_user",
    "plot_Z": "visual_test_user",
    "plot_abc": "visual_test_user",
    "test_plot_1": "visual_test_user",
    "test_plot_123": "visual_test_user",
    "test_plot_rollback_drill": "visual_test_user",
    "test_plot_state_engine": "visual_test_user",
    "test_plot_v62": "visual_test_user",
    "test_plot_v65d": "visual_test_user",
    "test_plot_v65f": "visual_test_user"
}

def is_test_context() -> bool:
    env = os.getenv("ENVIRONMENT", "").lower()
    if env == "production":
        return False
    if env == "test":
        return True
    return (
        os.getenv("AGRIWISE_TEST_MODE") == "true"
        or "PYTEST_CURRENT_TEST" in os.environ
    )

def _get_default_plots() -> Dict[str, str]:
    if is_test_context():
        merged = {}
        merged.update(PRODUCTION_ROLLOUT_REGISTRY)
        merged.update(TEST_FIXTURE_ROLLOUT_REGISTRY)
        return merged
    else:
        return dict(PRODUCTION_ROLLOUT_REGISTRY)

DEFAULT_PLOTS = _get_default_plots()

REGISTRY_SCHEMA_VERSION = "v86_rollout_registry_v2"
ROLLOUT_CONTRACT_VERSION = "bc10.20r3"
_LOCAL_LOCK = threading.RLock()
_local_initialized = False
_ephemeral_test_registry: Optional[Dict[str, Any]] = None


def _uses_ephemeral_test_registry() -> bool:
    """Keep pytest rollout mutations out of the tracked operator registry."""
    return bool(
        is_test_context()
        and Path(REGISTRY_FILE).resolve()
        == (REGISTRY_DIR / "asmae_rollout_registry.json").resolve()
    )


def _load_ephemeral_test_registry() -> Dict[str, Any]:
    global _ephemeral_test_registry
    if _ephemeral_test_registry is None:
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as handle:
                registry = json.load(handle)
        except Exception:
            registry = {"version": REGISTRY_SCHEMA_VERSION, "plots": {}}
        plots = registry.setdefault("plots", {})
        for plot_id, phase in _get_default_plots().items():
            plots.setdefault(plot_id, {
                "enabled": True,
                "backend_enabled": True,
                "l10_visuals_enabled": phase != "backend_observation",
                "phase": phase,
                "owner": "internal",
                "crop": "generic",
                "region": "internal_test",
                "created_at": "pytest-ephemeral",
                "notes": "Ephemeral test rollout fixture",
            })
        registry["version"] = REGISTRY_SCHEMA_VERSION
        _ephemeral_test_registry = registry
    return deepcopy(_ephemeral_test_registry)


def _use_persistent_store() -> bool:
    """Production rollout authority must come from the shared database."""
    configured = os.getenv("ASMAE_ROLLOUT_STORAGE", "").strip().lower()
    if configured:
        return configured == "mongo"
    if "PYTEST_CURRENT_TEST" in os.environ or os.getenv("AGRIWISE_TEST_MODE") == "true":
        return False
    if is_test_context():
        return False
    return os.getenv("ENVIRONMENT", "").strip().lower() == "production"


def _atomic_json_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)

def _initialize_registry_with_version(path: Path, version: str):
    """Create registry file with defaults if it doesn't exist."""
    plots_data = {}
    for plot_id, phase in _get_default_plots().items():
        plots_data[plot_id] = {
            "enabled": True,
            "backend_enabled": True,
            "l10_visuals_enabled": phase != "backend_observation",
            "phase": phase,
            "owner": "internal",
            "crop": "generic",
            "region": "internal_test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "notes": "Pre-registered test plot for CI/CD safety"
        }
        
    registry = {
        "version": version,
        "plots": plots_data
    }
    
    _atomic_json_write(path, registry)

def migrate_registry_to_v86(registry_file: Optional[Path] = None):
    """Safely migrates the registry file to V86 schema version, preserving operator edits."""
    path = registry_file if registry_file else REGISTRY_FILE
    if not path.exists():
        _initialize_registry_with_version(path, REGISTRY_SCHEMA_VERSION)
        return

    try:
        with open(path, "r") as f:
            registry = json.load(f)
    except Exception:
        registry = {"version": REGISTRY_SCHEMA_VERSION, "plots": {}}

    plots = registry.setdefault("plots", {})
    old_version = registry.get("version", "")

    # Clean up test fixtures in non-test context to prevent leakage
    if not is_test_context():
        for test_fixture in TEST_FIXTURE_ROLLOUT_REGISTRY.keys():
            plots.pop(test_fixture, None)

    # Populate production rollout registry plots
    for plot_id, phase in PRODUCTION_ROLLOUT_REGISTRY.items():
        if plot_id not in plots:
            plots[plot_id] = {
                "enabled": True,
                "backend_enabled": True,
                "l10_visuals_enabled": False,
                "phase": phase,
                "owner": "internal",
                "crop": "generic",
                "region": "internal_test",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "notes": "Migrated or added as production plot"
            }
        else:
            # Preserve existing user-defined phase, but if migrating from older version force l10 visuals rules
            if old_version != REGISTRY_SCHEMA_VERSION:
                plots[plot_id]["phase"] = phase
                plots[plot_id]["l10_visuals_enabled"] = False
                plots[plot_id]["enabled"] = True
                plots[plot_id]["backend_enabled"] = True

    # In test context, ensure test fixtures are present
    if is_test_context():
        for plot_id, phase in TEST_FIXTURE_ROLLOUT_REGISTRY.items():
            # If the plot was moved to production registry, preserve its production settings
            if plot_id in PRODUCTION_ROLLOUT_REGISTRY:
                continue
            if plot_id not in plots:
                plots[plot_id] = {
                    "enabled": True,
                    "backend_enabled": True,
                    "l10_visuals_enabled": True,
                    "phase": phase,
                    "owner": "internal",
                    "crop": "generic",
                    "region": "internal_test",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "notes": "Pre-registered test plot for CI/CD safety"
                }

    registry["version"] = REGISTRY_SCHEMA_VERSION
    _atomic_json_write(path, registry)

def _load_registry() -> Dict[str, Any]:
    global _local_initialized
    if _use_persistent_store():
        raise RuntimeError("local rollout registry is disabled in production")
    with _LOCAL_LOCK:
        if _uses_ephemeral_test_registry():
            return _load_ephemeral_test_registry()
        if not _local_initialized:
            migrate_registry_to_v86()
            _local_initialized = True
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"version": REGISTRY_SCHEMA_VERSION, "plots": {}}

def _save_registry(registry: Dict[str, Any]):
    global _ephemeral_test_registry
    if _use_persistent_store():
        raise RuntimeError("local rollout registry is disabled in production")
    with _LOCAL_LOCK:
        if _uses_ephemeral_test_registry():
            _ephemeral_test_registry = deepcopy(registry)
            return
        _atomic_json_write(REGISTRY_FILE, registry)


def _persistent_rollout_record(plot_id: str) -> Optional[Dict[str, Any]]:
    """Resolve rollout only when its plot/farm/tenant ownership is consistent."""
    from app.mongo_client import get_db
    from bson import ObjectId

    db = get_db()
    try:
        plot_oid = ObjectId(plot_id)
    except Exception:
        return None
    plot = db["Plot"].find_one({"_id": plot_oid}, {"farmId": 1})
    if not plot or not plot.get("farmId"):
        return None
    farm = db["Farm"].find_one({"_id": plot["farmId"]}, {"userId": 1})
    if not farm or not farm.get("userId"):
        return None
    return db["AsmaeRollout"].find_one({
        "plotId": plot_oid,
        "farmId": plot["farmId"],
        "tenantId": farm["userId"],
        "contractVersion": ROLLOUT_CONTRACT_VERSION,
    })


def _rollout_record(plot_id: str) -> Optional[Dict[str, Any]]:
    if _use_persistent_store():
        return _persistent_rollout_record(plot_id)
    return _load_registry().get("plots", {}).get(plot_id)


def get_rollout_state(plot_id: str) -> str:
    record = _rollout_record(plot_id)
    if not record:
        return "not_registered"
    backend = bool(record.get("backendEnabled", record.get("backend_enabled", False)))
    shadow = bool(record.get(
        "diagnosticShadowEnabled",
        record.get("diagnostic_shadow_enabled", record.get("phase") not in ("disabled", "backend_observation")),
    ))
    visuals = bool(record.get("visualsEnabled", record.get("l10_visuals_enabled", False)))
    if not backend:
        return "backend_disabled"
    if not shadow:
        return "diagnostic_shadow_disabled"
    if not visuals:
        return "backend_enabled_visuals_disabled"
    return "full_authority_enabled"

def is_archive_pilot_plot(plot_id: str) -> bool:
    return plot_id in ARCHIVE_PILOT_REGISTRY

def is_archive_pilot_enabled_for_plot(plot_id: str) -> bool:
    return (
        os.getenv("AGRIWISE_ARCHIVE_PILOT_MODE", "").lower() == "true"
        and is_archive_pilot_plot(plot_id)
    )

def is_asmae_backend_enabled_for_plot(plot_id: str) -> bool:
    """Check if the ASMAE backend is enabled for the given plot."""
    if not plot_id or not isinstance(plot_id, str) or plot_id.strip() == "":
        return False
        
    if is_archive_pilot_enabled_for_plot(plot_id):
        return True

    # If it is a pilot plot but pilot mode is not enabled, isolate it
    if is_archive_pilot_plot(plot_id):
        if plot_id not in PRODUCTION_ROLLOUT_REGISTRY and plot_id not in TEST_FIXTURE_ROLLOUT_REGISTRY:
            return False

    if plot_id in TEST_FIXTURE_ROLLOUT_REGISTRY:
        if not is_test_context():
            return False
            
    plot = _rollout_record(plot_id)
    if not plot:
        return False
    return bool(plot.get("enabled", True)) and bool(plot.get("backendEnabled", plot.get("backend_enabled", False)))

def is_l10_asmae_visuals_enabled_for_plot(plot_id: str) -> bool:
    """Check if Layer 10 ASMAE visual surfaces are enabled for the given plot."""
    if not plot_id or not isinstance(plot_id, str) or plot_id.strip() == "":
        return False
        
    if is_archive_pilot_enabled_for_plot(plot_id):
        return True

    # If it is a pilot plot but pilot mode is not enabled, isolate it
    if is_archive_pilot_plot(plot_id):
        if plot_id not in PRODUCTION_ROLLOUT_REGISTRY and plot_id not in TEST_FIXTURE_ROLLOUT_REGISTRY:
            return False

    if plot_id in TEST_FIXTURE_ROLLOUT_REGISTRY:
        if not is_test_context():
            return False
            
    plot = _rollout_record(plot_id)
    if not plot:
        return False
    return (
        plot.get("enabled", True)
        and plot.get("backendEnabled", plot.get("backend_enabled", False))
        and plot.get("visualsEnabled", plot.get("l10_visuals_enabled", False))
    )


def get_rollout_phase(plot_id: str) -> str:
    """Get the active rollout phase for the given plot."""
    plot = _rollout_record(plot_id)
    if not plot:
        return "disabled"
    return plot.get("phase", "disabled")

def get_registered_test_plots() -> List[str]:
    """Get the list of all registered plot IDs."""
    if _use_persistent_store():
        return []
    registry = _load_registry()
    return list(registry.get("plots", {}).keys())

def record_rollout_decision(
    plot_id: str,
    decision: str,
    reason: str,
    operator: str = "system",
    rollback_available: bool = True,
    farm_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
):
    """Update a plot's phase/status in the registry and log the decision to audit log."""
    if _use_persistent_store():
        if not farm_id or not tenant_id:
            raise ValueError("farm_id and tenant_id are required for production rollout updates")
        from app.mongo_client import get_db
        from bson import ObjectId
        from pymongo import ReturnDocument

        now = datetime.now(timezone.utc)
        backend_enabled = decision != "disabled"
        shadow_enabled = decision not in ("disabled", "backend_observation")
        visuals_enabled = decision not in ("disabled", "backend_observation", "backend_validation")
        db = get_db()
        identity = {
            "plotId": ObjectId(plot_id),
            "farmId": ObjectId(farm_id),
            "tenantId": ObjectId(tenant_id),
        }
        record = db["AsmaeRollout"].find_one_and_update(
            identity,
            {
                "$set": {
                    "backendEnabled": backend_enabled,
                    "diagnosticShadowEnabled": shadow_enabled,
                    "visualsEnabled": visuals_enabled,
                    "phase": decision,
                    "approvedBy": operator,
                    "approvedAt": now,
                    "contractVersion": ROLLOUT_CONTRACT_VERSION,
                    "reason": reason,
                    "updatedAt": now,
                },
                "$setOnInsert": {"createdAt": now, "revision": 0},
                "$inc": {"revision": 1},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        db["AsmaeRolloutAudit"].insert_one({
            **identity,
            "rolloutId": record.get("_id") if record else None,
            "timestamp": now,
            "operator": operator,
            "newPhase": decision,
            "reason": reason,
            "rollbackAvailable": rollback_available,
            "contractVersion": ROLLOUT_CONTRACT_VERSION,
        })
        return

    registry = _load_registry()
    plots = registry.setdefault("plots", {})
    
    old_plot = plots.get(plot_id, {})
    old_phase = old_plot.get("phase", "disabled")
    
    # Update the registry record
    if plot_id not in plots:
        plots[plot_id] = {
            "enabled": True,
            "backend_enabled": True,
            "l10_visuals_enabled": False,
            "phase": decision,
            "owner": operator,
            "crop": "unknown",
            "region": "unknown",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "notes": reason
        }
    else:
        plots[plot_id]["phase"] = decision
        plots[plot_id]["notes"] = reason
        # Map logical phases to enabled flags
        if decision == "disabled":
            plots[plot_id]["enabled"] = False
        else:
            plots[plot_id]["enabled"] = True
            plots[plot_id]["backend_enabled"] = True
            plots[plot_id]["l10_visuals_enabled"] = decision not in ("backend_observation", "backend_validation")
            
    _save_registry(registry)
    
    # Append to the audit log
    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operator": operator,
        "plot_id": plot_id,
        "old_phase": old_phase,
        "new_phase": decision,
        "reason": reason,
        "rollback_available": rollback_available
    }
    
    if not _uses_ephemeral_test_registry():
        AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG_FILE, "a") as f:
            f.write(json.dumps(audit_entry) + "\n")

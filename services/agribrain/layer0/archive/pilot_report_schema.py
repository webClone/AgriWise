"""
Pilot Report Schema and Validation.
Enforces fields and version tag, and calculates report hash.
"""
import json
import hashlib
from typing import Dict, Any

PILOT_REPORT_SCHEMA_VERSION = "v90_8_archive_pilot_report_v1"

def validate_pilot_report(report: Dict[str, Any]) -> bool:
    """Verifies that all required top-level keys are present in the report."""
    required_keys = [
        "pilot_schema_version",
        "plot_id",
        "archive_run_id",
        "depth_mode",
        "budget_profile",
        "runtime",
        "storage",
        "cache",
        "retrovalidation",
        "quality",
        "safety_assertions",
        "no_effect_guard",
        "limitations",
        "report_hash"
    ]
    for key in required_keys:
        if key not in report:
            raise KeyError(f"Missing required key in pilot report: {key}")
            
    if report["pilot_schema_version"] != PILOT_REPORT_SCHEMA_VERSION:
        raise ValueError(f"Invalid pilot_schema_version: {report['pilot_schema_version']}")
        
    # Check that required sections are dictionaries
    for section in ["runtime", "storage", "cache", "retrovalidation", "quality", "safety_assertions", "no_effect_guard"]:
        if not isinstance(report[section], dict):
            raise TypeError(f"Section {section} must be a dictionary")
            
    if not isinstance(report["limitations"], list):
        raise TypeError("limitations must be a list")
        
    return True

def calculate_report_hash(report: Dict[str, Any]) -> str:
    """Calculates SHA-256 hash over runtime, storage, and retrovalidation sections."""
    data_to_hash = {
        "runtime": report.get("runtime", {}),
        "storage": report.get("storage", {}),
        "retrovalidation": report.get("retrovalidation", {})
    }
    canonical_str = json.dumps(data_to_hash, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

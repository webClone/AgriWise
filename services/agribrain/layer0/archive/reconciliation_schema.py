"""
V90.9 — Reconciliation Summary Schema and Validation.
Defines required fields, validates types, and calculates summary hash.
"""
import json
import hashlib
from typing import Dict, Any

RECONCILIATION_SCHEMA_VERSION = "v90_9_archive_reconciliation_v1"

def validate_reconciliation_summary(summary: Dict[str, Any]) -> bool:
    """Verifies that all required top-level keys are present and correctly typed."""
    required_keys = [
        "schema_version",
        "run_id",
        "cohort",
        "stage_results",
        "live_api_trace",
        "storage_projection",
        "field_reconciliation",
        "promotion_decisions",
        "safety_assertions",
        "no_effect_guard",
        "limitations",
        "summary_hash"
    ]
    for key in required_keys:
        if key not in summary:
            raise KeyError(f"Missing required key in reconciliation summary: {key}")
            
    if summary["schema_version"] != RECONCILIATION_SCHEMA_VERSION:
        raise ValueError(f"Invalid schema_version: {summary['schema_version']}")
        
    # Check that required sections are dictionaries
    dict_sections = [
        "stage_results",
        "live_api_trace",
        "storage_projection",
        "field_reconciliation",
        "promotion_decisions",
        "safety_assertions",
        "no_effect_guard"
    ]
    for section in dict_sections:
        if not isinstance(summary[section], dict):
            raise TypeError(f"Section {section} must be a dictionary")
            
    if not isinstance(summary["cohort"], list):
        raise TypeError("cohort must be a list")
        
    if not isinstance(summary["limitations"], list):
        raise TypeError("limitations must be a list")
        
    return True

def calculate_summary_hash(summary: Dict[str, Any]) -> str:
    """Calculates SHA-256 hash over stage_results, storage_projection, field_reconciliation,

    promotion_decisions, and safety_assertions sections.
    """
    data_to_hash = {
        "stage_results": summary.get("stage_results", {}),
        "storage_projection": summary.get("storage_projection", {}),
        "field_reconciliation": summary.get("field_reconciliation", {}),
        "promotion_decisions": summary.get("promotion_decisions", {}),
        "safety_assertions": summary.get("safety_assertions", {})
    }
    canonical_str = json.dumps(data_to_hash, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

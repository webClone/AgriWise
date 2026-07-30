import hashlib
import json
import copy
from typing import Any, Dict, List
from layer9_interface.reporting.schemas import ClassifiedEvidence

def serialize_item(item: Any) -> Any:
    if hasattr(item, "to_dict"):
        return item.to_dict()
    elif hasattr(item, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(item)
    return item

def compute_input_hash(raw_items: List[Any]) -> str:
    """Hash of the normalized evidence packet raw items, sorted deterministically."""
    serialized_items = []
    for item in raw_items:
        serialized_items.append(serialize_item(item))
    
    sorted_items = sorted(serialized_items, key=lambda x: str(x.get("evidence_id", "")))
    serialized = json.dumps(sorted_items, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def compute_verified_evidence_hash(classified_items: List[ClassifiedEvidence]) -> str:
    """
    Hash of only verified/validated/certified evidence.
    Excludes shadow ML, visual-only 1m, uncertified 1m, weak labels, prescriptive actions, and forecasts.
    """
    verified_tiers = {"verified_observation", "validated_field_evidence", "certified_plot_memory", "certified_1m_inferred_detail"}
    filtered = []
    for item in classified_items:
        if item.tier in verified_tiers and item.institutional_admissibility in ("proof", "supporting"):
            filtered.append({
                "evidence_id": item.evidence_id,
                "tier": item.tier,
                "variable": item.variable,
                "value": item.value,
                "confidence": item.confidence,
                "uncertainty": item.uncertainty,
                "provenance_hash": item.provenance_hash
            })
    
    sorted_filtered = sorted(filtered, key=lambda x: str(x["evidence_id"]))
    serialized = json.dumps(sorted_filtered, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def compute_report_content_hash(report_dict: Dict[str, Any]) -> str:
    """Deterministic report body hash, excluding report_id, generated_at, report_content_hash, and report_instance_hash."""
    copy_data = copy.deepcopy(report_dict)
    
    # Exclude non-content specific instance-identifying fields
    copy_data.pop("report_id", None)
    copy_data.pop("generated_at", None)
    copy_data.pop("report_content_hash", None)
    copy_data.pop("report_instance_hash", None)
    
    # Normalize nested dataclasses
    def normalize(val: Any) -> Any:
        if isinstance(val, dict):
            return {k: normalize(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [normalize(v) for v in val]
        elif hasattr(val, "to_dict"):
            return normalize(val.to_dict())
        elif hasattr(val, "__dataclass_fields__"):
            from dataclasses import asdict
            return normalize(asdict(val))
        return val

    normalized_data = normalize(copy_data)
    serialized = json.dumps(normalized_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def compute_report_instance_hash(report_id: str, generated_at: str, content_hash: str) -> str:
    """Hash including report_id, generated_at, and content_hash."""
    payload = {
        "report_id": report_id,
        "generated_at": generated_at,
        "content_hash": content_hash
    }
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

"""Shared, side-effect-free scene admission rules.

Capability planning and runtime loading must make the same decision from the
same Layer 0 quality fields. Keeping this module dependency-free lets both
boundaries use it without importing geometry or worker code.
"""
from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple


SCENE_QUALITY_CONTRACT_VERSION = "asmae_scene_quality_identity_v3_semantic_status"


def _semantic_scalar(value: Any) -> Any:
    """Normalize enum-like values across the safe manifest boundary."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping) and "value" in value:
        return _semantic_scalar(value.get("value"))
    nested = getattr(value, "value", None)
    if nested is not None and nested is not value:
        return _semantic_scalar(nested)
    return value


def _public(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        data = dict(value)
        if data.get("__asmae_manifest_type__") == "object_v1" and isinstance(data.get("fields"), Mapping):
            return dict(data["fields"])
        return data
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    if hasattr(value, "__dict__"):
        return {key: item for key, item in vars(value).items() if not str(key).startswith("_")}
    return {}


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def scene_quality_identity(value: Any) -> Dict[str, Any]:
    """Freeze every quality fact that can change weighting or authority."""
    data = _public(value)
    qa = _public(data.get("qa_metrics") or data.get("qa"))
    quality = _public(data.get("quality"))
    metadata = _public(data.get("metadata"))

    def first(*items: Any) -> Any:
        return next((item for item in items if item is not None), None)

    usable = first(data.get("usable"), qa.get("usable"), quality.get("usable"))
    usable = _semantic_scalar(usable)
    if isinstance(usable, str):
        usable = usable.strip().lower() not in {"false", "0", "no", "unusable", "invalid"}
    valid_fraction = _finite(first(
        data.get("valid_fraction"), qa.get("valid_fraction"),
        qa.get("valid_pixel_fraction"), quality.get("valid_fraction"),
        metadata.get("valid_fraction"),
    ))
    cloud_fraction = _finite(first(
        data.get("cloud_fraction"), data.get("cloud_cover"),
        qa.get("cloud_fraction"), qa.get("cloud_cover"),
        quality.get("cloud_fraction"), metadata.get("cloud_fraction"),
    ))
    valid_count = _finite(first(
        data.get("valid_count"), data.get("valid_pixel_count"),
        qa.get("valid_count"), qa.get("valid_pixel_count"),
        quality.get("valid_count"),
    ))
    total_count = _finite(first(
        data.get("total_count"), data.get("total_pixel_count"),
        qa.get("total_count"), qa.get("total_pixel_count"),
        quality.get("total_count"),
    ))
    if total_count is None:
        width = _finite(data.get("width"))
        height = _finite(data.get("height"))
        if width is not None and height is not None:
            total_count = width * height
    quality_score = _finite(first(
        data.get("quality_score"), data.get("qa_score"),
        qa.get("quality_score"), qa.get("score"), quality.get("score"),
    ))
    quality_class = first(
        data.get("quality_class"), qa.get("quality_class"),
        quality.get("quality_class"), quality.get("class"),
    )
    quality_class = _semantic_scalar(quality_class)
    status = str(_semantic_scalar(first(
        data.get("data_status"), qa.get("data_status"),
        quality.get("data_status"), data.get("quality_status"),
    )) or "").strip().lower()
    return {
        "contract_version": SCENE_QUALITY_CONTRACT_VERSION,
        "usable": usable,
        "valid_fraction": valid_fraction,
        "valid_count": int(valid_count) if valid_count is not None else None,
        "total_count": int(total_count) if total_count is not None else None,
        "cloud_fraction": cloud_fraction,
        "quality_score": quality_score,
        "quality_class": str(quality_class) if quality_class is not None else None,
        "support_mask_hash": str(
            first(data.get("valid_support_hash"), data.get("support_mask_hash"),
                  qa.get("support_mask_hash"), quality.get("support_mask_hash")) or ""
        ),
        "data_status": status or None,
    }


def scene_quality_admission(value: Any) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Return whether a spatial scene has executable pixel support.

    Missing quality metadata remains admissible at this boundary; masks still
    determine final support during geometry construction. Explicit zero or
    invalid support and explicit unusable status are terminal.
    """
    data = _public(value)
    qa = _public(data.get("qa_metrics") or data.get("qa"))
    quality = _public(data.get("quality"))
    metadata = _public(data.get("metadata"))

    def first(*items: Any) -> Any:
        return next((item for item in items if item is not None), None)

    usable = first(data.get("usable"), qa.get("usable"), quality.get("usable"))
    valid_fraction_raw = first(
        data.get("valid_fraction"), qa.get("valid_fraction"),
        qa.get("valid_pixel_fraction"), quality.get("valid_fraction"),
        metadata.get("valid_fraction"),
    )
    cloud_fraction_raw = first(
        data.get("cloud_fraction"), data.get("cloud_cover"),
        qa.get("cloud_fraction"), qa.get("cloud_cover"),
        quality.get("cloud_fraction"), metadata.get("cloud_fraction"),
    )
    status = str(_semantic_scalar(first(
        data.get("data_status"), qa.get("data_status"),
        quality.get("data_status"), data.get("quality_status"),
    )) or "").strip().lower()
    usable = _semantic_scalar(usable)
    if isinstance(usable, str):
        usable = usable.strip().lower() not in {"false", "0", "no", "unusable", "invalid"}

    valid_fraction = _finite(valid_fraction_raw)
    cloud_fraction = _finite(cloud_fraction_raw)
    facts = scene_quality_identity(data)
    frozen = data.get("_asmae_frozen_quality_identity")
    if isinstance(frozen, Mapping) and dict(frozen) != facts:
        return False, "scene_quality_identity_mismatch", facts
    if usable is False:
        return False, "scene_quality_marked_unusable", facts
    if valid_fraction_raw is not None and valid_fraction is None:
        return False, "scene_valid_fraction_nonfinite", facts
    if valid_fraction is not None and valid_fraction <= 0.0:
        return False, "scene_has_no_valid_spatial_support", facts
    if cloud_fraction_raw is not None and cloud_fraction is None:
        return False, "scene_cloud_fraction_nonfinite", facts
    if cloud_fraction is not None and cloud_fraction >= 1.0:
        return False, "scene_has_no_clear_spatial_support", facts
    if status in {"unusable", "invalid", "rejected", "failed"}:
        return False, "scene_data_status_unusable", facts
    return True, None, facts

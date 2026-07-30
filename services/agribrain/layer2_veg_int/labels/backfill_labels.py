"""
Crop Intelligence v6.0B — Backfill Utility.

One-time utility to create historical_record labels from existing
CropCycle documents in MongoDB.

Rules (Adjustment #6):
  - HARVESTED CropCycle → label_confidence=MEDIUM
  - GROWING CropCycle → excluded by default (include_growing=False)
  - label_source = "historical_record"
  - geometry_hash from plot's current geoJson
  - feature_vector_snapshot = None (attached when L1 runs later)
  - dry_run = True by default

This does NOT require PyMongo at import time. The backfill function
accepts a database connection or can run against mock data for testing.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .label_schema import (
    CropLabel,
    canonicalize_geometry_hash,
    validate_crop_code,
    LABEL_SCHEMA_VERSION,
    FEATURE_VECTOR_VERSION,
)
from .label_store import LabelStoreBase

logger = logging.getLogger("agribrain.labels.backfill")

# Statuses that qualify for backfill
HARVESTED_STATUSES = frozenset({"HARVESTED"})
GROWING_STATUSES = frozenset({"GROWING", "FLOWERING", "FRUITING", "READY_TO_HARVEST"})


def _crop_cycle_to_label(
    cycle: Dict[str, Any],
    plot_geojson: Optional[Dict] = None,
) -> Optional[CropLabel]:
    """Convert a CropCycle document to a CropLabel.

    Returns None if crop_code is invalid or missing.
    """
    crop_code = cycle.get("cropCode", "")
    if not crop_code:
        return None

    # Normalize crop code
    crop_code = crop_code.lower().replace(" ", "_")

    # Validate — do NOT default to wheat
    if not validate_crop_code(crop_code):
        logger.warning(f"Unknown crop_code '{crop_code}' in cycle {cycle.get('_id')}, skipping")
        return None

    # Get crop group
    try:
        from layer2_veg_int.crop_science_data import get_crop_group
        crop_group = get_crop_group(crop_code)
    except ImportError:
        crop_group = "unknown"

    # Determine confidence from status
    status = cycle.get("status", "")
    if status in HARVESTED_STATUSES:
        confidence = "MEDIUM"
    elif status in GROWING_STATUSES:
        confidence = "LOW"
    else:
        confidence = "LOW"

    # Parse dates
    planting_date = None
    harvest_date = None

    plant = cycle.get("plantDate")
    if plant:
        if isinstance(plant, datetime):
            planting_date = plant.strftime("%Y-%m-%d")
        elif isinstance(plant, str):
            planting_date = plant[:10]  # YYYY-MM-DD

    harvest = cycle.get("actualHarvest") or cycle.get("expectedHarvest")
    if harvest:
        if isinstance(harvest, datetime):
            harvest_date = harvest.strftime("%Y-%m-%d")
        elif isinstance(harvest, str):
            harvest_date = harvest[:10]

    # Geometry hash
    geometry_hash = canonicalize_geometry_hash(plot_geojson)

    return CropLabel(
        label_id="",  # Auto-generated in __post_init__
        plot_id=str(cycle.get("plotId", "")),
        geometry_hash=geometry_hash,
        crop_code=crop_code,
        crop_group=crop_group,
        label_source="historical_record",
        label_confidence=confidence,
        planting_date=planting_date,
        harvest_date=harvest_date,
        notes=f"Backfilled from CropCycle (status={status})",
    )


def backfill_from_crop_cycles(
    store: LabelStoreBase,
    cycles: List[Dict[str, Any]],
    plot_geojsons: Optional[Dict[str, Dict]] = None,
    include_growing: bool = False,
    dry_run: bool = True,
) -> Dict:
    """Create historical_record labels from CropCycle data.

    Args:
        store: Label store to write to
        cycles: List of CropCycle documents (from MongoDB)
        plot_geojsons: Map of plot_id → geoJson for geometry hash
        include_growing: Include GROWING status cycles (default False)
        dry_run: If True, do not write to store (default True)

    Returns:
        {
            "total_cycles": N,
            "labels_created": M,
            "duplicates_skipped": K,
            "invalid_crop_codes": L,
            "growing_skipped": G,
            "errors": [...],
            "created_labels": [label_id, ...],
        }
    """
    result = {
        "total_cycles": len(cycles),
        "labels_created": 0,
        "duplicates_skipped": 0,
        "invalid_crop_codes": 0,
        "growing_skipped": 0,
        "errors": [],
        "created_labels": [],
    }

    allowed_statuses = set(HARVESTED_STATUSES)
    if include_growing:
        allowed_statuses |= GROWING_STATUSES

    for cycle in cycles:
        status = cycle.get("status", "")

        if status not in allowed_statuses:
            if status in GROWING_STATUSES:
                result["growing_skipped"] += 1
            continue

        plot_id = str(cycle.get("plotId", ""))
        geojson = (plot_geojsons or {}).get(plot_id)

        try:
            label = _crop_cycle_to_label(cycle, geojson)
        except Exception as e:
            result["errors"].append(f"Error converting cycle {cycle.get('_id')}: {e}")
            continue

        if label is None:
            result["invalid_crop_codes"] += 1
            continue

        if dry_run:
            result["labels_created"] += 1
            result["created_labels"].append(label.label_id)
            continue

        label_id, conflict = store.save_label(label)

        if conflict.action == "deduplicate":
            result["duplicates_skipped"] += 1
        else:
            result["labels_created"] += 1
            result["created_labels"].append(label_id)

    logger.info(
        f"Backfill {'(DRY RUN) ' if dry_run else ''}"
        f"complete: {result['labels_created']} labels from "
        f"{result['total_cycles']} cycles"
    )

    return result

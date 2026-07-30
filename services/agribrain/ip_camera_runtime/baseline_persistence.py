"""
MongoDB Baseline Model Persistence — save/load camera baselines across restarts.

Extends the in-memory BaselineModel with MongoDB storage so that
hour-bucketed baselines and seasonal averages survive process restarts.

Usage:
    from ip_camera_runtime.baseline_persistence import MongoBaselinePersistence

    persistence = MongoBaselinePersistence(collection=db["camera_baselines"])

    # Save current baseline state for a camera
    persistence.save(baseline_model, camera_id="cam_001")

    # Load baseline state from MongoDB into the model
    persistence.load(baseline_model, camera_id="cam_001")

    # Save all cameras
    persistence.save_all(baseline_model)

    # Load all cameras
    persistence.load_all(baseline_model)
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from layer0.perception.ip_camera.baseline_model import BaselineEntry, BaselineModel

logger = logging.getLogger(__name__)


def _entry_to_doc(entry: BaselineEntry) -> dict:
    """Serialize a BaselineEntry to a MongoDB document.

    Omits cv2-specific fields (histograms, thumbnails) since those
    are large binary arrays. They will be recomputed from frames.
    """
    return {
        "green_ratio": entry.green_ratio,
        "brightness_mean": entry.brightness_mean,
        "saturation_mean": entry.saturation_mean,
        "green_coverage_fraction": entry.green_coverage_fraction,
        "edge_density": entry.edge_density,
        "crop_fraction": entry.crop_fraction,
        "captured_at": entry.captured_at.isoformat() if entry.captured_at else None,
        "frame_ref": entry.frame_ref,
    }


def _doc_to_entry(doc: dict) -> BaselineEntry:
    """Deserialize a MongoDB document to a BaselineEntry."""
    captured_at = None
    if doc.get("captured_at"):
        try:
            captured_at = datetime.fromisoformat(doc["captured_at"])
        except (ValueError, TypeError):
            pass

    return BaselineEntry(
        green_ratio=doc.get("green_ratio", 0.33),
        brightness_mean=doc.get("brightness_mean", 128.0),
        saturation_mean=doc.get("saturation_mean", 100.0),
        green_coverage_fraction=doc.get("green_coverage_fraction", 0.3),
        edge_density=doc.get("edge_density", 0.05),
        crop_fraction=doc.get("crop_fraction", 0.3),
        captured_at=captured_at,
        frame_ref=doc.get("frame_ref", ""),
        # hsv_histogram and gray_thumbnail intentionally left None
        # — they will be recomputed from the next real frame
    )


class MongoBaselinePersistence:
    """
    MongoDB persistence layer for the camera baseline model.

    Document schema:
    {
        "camera_id": str,
        "type": "hourly" | "seasonal",
        "hour_bucket": int (0-23, only for type="hourly"),
        "entries": [BaselineEntry docs],
        "updated_at": datetime
    }
    """

    def __init__(self, collection):
        """
        Args:
            collection: pymongo Collection for baseline storage
        """
        self.collection = collection
        # Ensure indexes
        self.collection.create_index(
            [("camera_id", 1), ("type", 1), ("hour_bucket", 1)],
            unique=True,
        )

    def save(self, model: BaselineModel, camera_id: str) -> int:
        """Save baseline state for a single camera. Returns docs written."""
        docs_written = 0

        # Save hourly baselines
        camera_baselines = model._baselines.get(camera_id, {})
        for hour, entries_deque in camera_baselines.items():
            entries_docs = [_entry_to_doc(e) for e in entries_deque]
            self.collection.replace_one(
                {
                    "camera_id": camera_id,
                    "type": "hourly",
                    "hour_bucket": hour,
                },
                {
                    "camera_id": camera_id,
                    "type": "hourly",
                    "hour_bucket": hour,
                    "entries": entries_docs,
                    "updated_at": datetime.now(tz=timezone.utc),
                },
                upsert=True,
            )
            docs_written += 1

        # Save seasonal baseline
        seasonal = model._seasonal.get(camera_id)
        if seasonal:
            self.collection.replace_one(
                {
                    "camera_id": camera_id,
                    "type": "seasonal",
                    "hour_bucket": -1,
                },
                {
                    "camera_id": camera_id,
                    "type": "seasonal",
                    "hour_bucket": -1,
                    "entries": [_entry_to_doc(seasonal)],
                    "updated_at": datetime.now(tz=timezone.utc),
                },
                upsert=True,
            )
            docs_written += 1

        logger.info("Saved %d baseline docs for camera %s", docs_written, camera_id)
        return docs_written

    def load(self, model: BaselineModel, camera_id: str) -> bool:
        """Load baseline state for a single camera into the model.

        Returns True if any data was loaded.
        """
        loaded = False

        # Load hourly baselines
        hourly_docs = self.collection.find({
            "camera_id": camera_id,
            "type": "hourly",
        })

        for doc in hourly_docs:
            hour = doc["hour_bucket"]
            entries = [_doc_to_entry(e) for e in doc.get("entries", [])]
            if not entries:
                continue

            if camera_id not in model._baselines:
                model._baselines[camera_id] = {}

            model._baselines[camera_id][hour] = deque(
                entries, maxlen=BaselineModel.MAX_ENTRIES
            )
            loaded = True

        # Load seasonal baseline
        seasonal_doc = self.collection.find_one({
            "camera_id": camera_id,
            "type": "seasonal",
            "hour_bucket": -1,
        })
        if seasonal_doc:
            entries = seasonal_doc.get("entries", [])
            if entries:
                model._seasonal[camera_id] = _doc_to_entry(entries[0])
                loaded = True

        if loaded:
            logger.info("Loaded baseline for camera %s", camera_id)
        return loaded

    def save_all(self, model: BaselineModel) -> int:
        """Save baseline state for all cameras."""
        total = 0
        all_camera_ids = set(model._baselines.keys()) | set(model._seasonal.keys())
        for camera_id in all_camera_ids:
            total += self.save(model, camera_id)
        return total

    def load_all(self, model: BaselineModel) -> int:
        """Load baseline state for all cameras found in MongoDB."""
        camera_ids = self.collection.distinct("camera_id")
        loaded = 0
        for camera_id in camera_ids:
            if self.load(model, camera_id):
                loaded += 1
        logger.info("Loaded baselines for %d cameras", loaded)
        return loaded

    def delete_camera(self, camera_id: str) -> int:
        """Delete all baseline data for a camera."""
        result = self.collection.delete_many({"camera_id": camera_id})
        return result.deleted_count

    def get_camera_ids(self) -> List[str]:
        """List all camera IDs with stored baselines."""
        return self.collection.distinct("camera_id")

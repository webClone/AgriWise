"""
AgriBrain V57 Farmer Photo Ground Truth Adapter.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from ground_truth.schemas import GroundTruthEvidence


class FarmerPhotoAdapter:
    """
    Ingests and processes real farmer photos on disk and parses sidecar JSON
    simulating embedded EXIF GPS/time tags to extract point observations.
    """

    @staticmethod
    def load_from_file(
        photo_path: str,
        exif_path: str,
        source_id: str,
        timestamp: datetime
    ) -> GroundTruthEvidence:
        """
        Loads photo bytes and parses sidecar EXIF JSON.
        """
        p_path = Path(photo_path)
        e_path = Path(exif_path)
        if not p_path.exists():
            raise FileNotFoundError(f"Farmer photo file not found: {photo_path}")
        if not e_path.exists():
            raise FileNotFoundError(f"Farmer EXIF sidecar not found: {exif_path}")

        # Ingest bytes
        img_bytes = p_path.read_bytes()
        if len(img_bytes) == 0:
            raise ValueError("ground_truth_missing_source_hash")

        # Ingest EXIF sidecar
        with e_path.open("r", encoding="utf-8") as f:
            exif = json.load(f)

        gps = exif.get("gps", {"latitude": 34.2, "longitude": 6.1})
        observation = exif.get("observation", "healthy_crop")
        confidence = float(exif.get("confidence", 0.90))

        geometry = {"type": "Point", "coordinates": [gps["longitude"], gps["latitude"]]}

        return GroundTruthEvidence(
            source_id=source_id,
            source_type="farmer_photo",
            scope="point",  # Point scope strictly enforced
            timestamp=timestamp,
            geometry=geometry,
            resolution_m=None,
            confidence=confidence,
            validation_targets=["local_condition", "disease_pest", "plant_density"],
            can_boost_1m=False,  # Point sources cannot boost plot-level 1m confidence
            can_boost_3cm=False,
            can_block_certification=True,  # Point sources can block if contradiction is strong
            state_update_allowed=False,
            payload_ref=observation,
            asset_origin="persistent_fixture_file",
            asset_generation_mode="compiled_from_existing_fixture",
            direct_field_capture=False
        )

    @staticmethod
    def create_evidence(
        source_id: str,
        timestamp: datetime,
        observation: str = "healthy_crop",
        geometry: Optional[Dict[str, Any]] = None,
        confidence: float = 0.90
    ) -> GroundTruthEvidence:
        """
        Backward compatible fallback generator.
        """
        return GroundTruthEvidence(
            source_id=source_id,
            source_type="farmer_photo",
            scope="point",
            timestamp=timestamp,
            geometry=geometry or {"type": "Point", "coordinates": [6.1, 34.2]},
            resolution_m=None,
            confidence=confidence,
            validation_targets=["local_condition", "disease_pest", "plant_density"],
            can_boost_1m=False,
            can_boost_3cm=False,
            can_block_certification=True,
            state_update_allowed=False,
            payload_ref=observation,
            asset_origin="persistent_fixture_file",
            asset_generation_mode="compiled_from_existing_fixture",
            direct_field_capture=False
        )


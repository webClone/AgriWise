"""
AgriBrain V57 Farmer Input Ground Truth Adapter.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from ground_truth.schemas import GroundTruthEvidence


class FarmerInputAdapter:
    """
    Ingests and processes real farmer declarations and management events stored
    in JSON format, such as irrigation or harvest timeline logs.
    """

    @staticmethod
    def load_from_file(
        json_path: str,
        source_id: str,
        timestamp: datetime
    ) -> GroundTruthEvidence:
        """
        Loads and parses a physical JSON event log from disk.
        """
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Farmer input JSON events log not found: {json_path}")

        # Ingest JSON declarations
        event_type = "planting"
        confidence = 1.0

        with path.open("r", encoding="utf-8") as f:
            events = json.load(f)
            
        # Scan for matching source_id event
        matches = [e for e in events if e.get("source_id") == source_id]
        if matches:
            latest = matches[-1]
            event_type = latest.get("event_type", "planting")
            confidence = float(latest.get("confidence", 1.0))

        return GroundTruthEvidence(
            source_id=source_id,
            source_type="farmer_input",
            scope="event",
            timestamp=timestamp,
            geometry=None,
            resolution_m=None,
            confidence=confidence,
            validation_targets=["management_event", "crop_stage", "resolution_gating"],
            can_boost_1m=False,
            can_boost_3cm=False,
            can_block_certification=True if event_type == "harvest" else False,
            state_update_allowed=False,
            payload_ref=event_type,
            asset_origin="persistent_fixture_file",
            asset_generation_mode="compiled_from_existing_fixture",
            direct_field_capture=False
        )

    @staticmethod
    def create_evidence(
        source_id: str,
        timestamp: datetime,
        event_type: str = "planting",
        confidence: float = 1.0
    ) -> GroundTruthEvidence:
        """
        Backward compatible fallback generator.
        """
        return GroundTruthEvidence(
            source_id=source_id,
            source_type="farmer_input",
            scope="event",
            timestamp=timestamp,
            geometry=None,
            resolution_m=None,
            confidence=confidence,
            validation_targets=["management_event", "crop_stage", "resolution_gating"],
            can_boost_1m=False,
            can_boost_3cm=False,
            can_block_certification=True if event_type == "harvest" else False,
            state_update_allowed=False,
            payload_ref=event_type,
            asset_origin="persistent_fixture_file",
            asset_generation_mode="compiled_from_existing_fixture",
            direct_field_capture=False
        )


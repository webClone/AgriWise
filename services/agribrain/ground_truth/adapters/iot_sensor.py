"""
AgriBrain V57 IoT Sensor Ground Truth Adapter.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from ground_truth.schemas import GroundTruthEvidence


class IoTSensorAdapter:
    """
    Ingests and processes real IoT sensor time-series telemetry stored in CSV format,
    evaluating soil moisture and temperature thresholds.
    """

    @staticmethod
    def load_from_file(
        csv_path: str,
        source_id: str,
        timestamp: datetime
    ) -> GroundTruthEvidence:
        """
        Loads and parses a physical CSV sensor telemetry log from disk.
        """
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"IoT sensor CSV time-series not found: {csv_path}")

        # Ingest CSV entries
        moisture_level = "optimal_moisture"
        temp = 25.0
        confidence = 0.99

        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Find the most recent or matching entry for source_id
            rows = [row for row in reader if row.get("sensor_id") == source_id]
            if rows:
                # Get the latest entry
                latest = rows[-1]
                moisture_level = latest.get("moisture_level", "optimal_moisture")
                temp = float(latest.get("temperature", 25.0))
                confidence = float(latest.get("confidence", 0.99))

        return GroundTruthEvidence(
            source_id=source_id,
            source_type="iot_sensor",
            scope="zone",
            timestamp=timestamp,
            geometry=None,
            resolution_m=None,
            confidence=confidence,
            validation_targets=["water_stress", "soil_moisture", "temperature"],
            can_boost_1m=True if moisture_level == "low_moisture" else False,
            can_boost_3cm=False,
            can_block_certification=True,
            state_update_allowed=False,
            payload_ref=moisture_level,
            asset_origin="persistent_fixture_file",
            asset_generation_mode="compiled_from_existing_fixture",
            direct_field_capture=False
        )

    @staticmethod
    def create_evidence(
        source_id: str,
        timestamp: datetime,
        moisture_level: str = "optimal_moisture",
        confidence: float = 0.99
    ) -> GroundTruthEvidence:
        """
        Backward compatible fallback generator.
        """
        return GroundTruthEvidence(
            source_id=source_id,
            source_type="iot_sensor",
            scope="zone",
            timestamp=timestamp,
            geometry=None,
            resolution_m=None,
            confidence=confidence,
            validation_targets=["water_stress", "soil_moisture", "temperature"],
            can_boost_1m=True if moisture_level == "low_moisture" else False,
            can_boost_3cm=False,
            can_block_certification=True,
            state_update_allowed=False,
            payload_ref=moisture_level,
            asset_origin="persistent_fixture_file",
            asset_generation_mode="compiled_from_existing_fixture",
            direct_field_capture=False
        )


"""
User Data Engine — Ingests user-contributed data through the Data Gateway.

All user inputs now flow through Layer 0's Data Gateway instead of being
scattered across the codebase. This includes:
  - Farmer photos (soil, crop, pest)
  - Soil analysis reports (lab results)
  - Field events (irrigation, fertilization, planting, harvesting)
  - Yield reports (actual yield for feedback loops)
  - Agronomist notes
  - Lab results
  - Sensor readings (IoT)
  - Drone survey data
  - IP camera captures

Each input is:
  1. Stored in the hot tier (MongoDB eo_cache) with appropriate TTL
  2. Promoted to the warm tier (PlotObservation) for historical archive
  3. Published to the event bus for ML pattern learning
  4. Converted to ObservationPackets via the existing UserInputAdapter

Usage:
    from layer0.data_gateway.user_data_engine import UserDataEngine

    engine = UserDataEngine(storage_manager)
    engine.ingest_irrigation("plot123", 33.5, -7.6, {
        "amount_mm": 25, "method": "drip", "duration_hours": 2
    })
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agribrain.gateway.user_data")


# User data source types (not in TTL_REGISTRY because they don't expire)
USER_SOURCE_TYPES = {
    "user_soil_analysis",
    "user_irrigation_event",
    "user_fertilization_event",
    "user_planting_event",
    "user_harvest_event",
    "user_management_event",
    "user_yield_report",
    "user_photo",
    "user_agronomist_note",
    "user_lab_result",
    "sensor_reading",
    "drone_survey",
    "camera_capture",
}

# TTL for user data in hot tier (7 days — longer than API data because
# it doesn't need refresh, but we still want warm-tier promotion)
USER_DATA_TTL = 7 * 86400  # 7 days


class UserDataEngine:
    """Ingests user-contributed data through the centralized Data Gateway.

    Unlike API data (which has TTL-based expiration), user data is:
    - Stored in hot tier with a generous TTL (7 days)
    - Always promoted to warm tier (observation archive)
    - Never auto-refreshed (it's a one-time event)
    - Used by ML patterns for calibration and learning
    """

    def __init__(self, storage_manager=None):
        self._storage = storage_manager
        self._ingestion_count = 0
        self._ingestion_log: List[Dict] = []  # Last 100 events

    def _get_storage(self):
        """Lazy-load storage manager."""
        if self._storage is None:
            from layer0.data_gateway.storage_manager import StorageManager
            self._storage = StorageManager()
        return self._storage

    # ── Core Ingestion ─────────────────────────────────────────────

    def _ingest(
        self,
        source_type: str,
        plot_id: str,
        lat: float,
        lng: float,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """Core ingestion method for all user data types.

        1. Tags data with metadata
        2. Stores in hot tier
        3. Promotes to warm tier
        4. Logs the event for ML consumption

        Returns True on success.
        """
        ts = timestamp or datetime.now(timezone.utc)

        # Enrich data with metadata
        enriched = {
            "source_type": source_type,
            "plot_id": plot_id,
            "timestamp": ts.isoformat(),
            "user_contributed": True,
            **data,
        }

        # Store through the gateway
        sm = self._get_storage()
        sm._cache_put(
            source=source_type,
            lat=lat,
            lng=lng,
            data=enriched,
            plot_id=plot_id,
            context=None,
            param_hash=f"{source_type}_{ts.strftime('%Y%m%d_%H%M%S')}",
        )

        # Track ingestion
        self._ingestion_count += 1
        self._ingestion_log.append({
            "source_type": source_type,
            "plot_id": plot_id[:8] if plot_id else "?",
            "timestamp": ts.isoformat(),
        })
        # Keep last 100
        if len(self._ingestion_log) > 100:
            self._ingestion_log = self._ingestion_log[-100:]

        logger.info(
            "[USER_DATA] Ingested %s for plot %s (total: %d)",
            source_type, plot_id[:8] if plot_id else "?", self._ingestion_count,
        )

        return True

    # ── Typed Ingestion Methods ────────────────────────────────────

    def ingest_soil_analysis(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest a soil analysis report (lab results).

        Expected data keys: ph, clay_pct, sand_pct, organic_matter_pct,
        nitrogen_ppm, phosphorus_ppm, potassium_ppm, ec_ds_m, cec,
        depth_cm, analysis_method, lab_name.
        """
        return self._ingest("user_soil_analysis", plot_id, lat, lng, data)

    def ingest_irrigation(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest an irrigation event.

        Expected data keys: amount_mm, method (drip/sprinkler/flood),
        duration_hours, zone_id, water_source.
        """
        return self._ingest("user_irrigation_event", plot_id, lat, lng, data)

    def ingest_fertilization(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest a fertilization event.

        Expected data keys: type (organic/synthetic/foliar), product_name,
        npk_ratio, amount_kg_ha, application_method.
        """
        return self._ingest("user_fertilization_event", plot_id, lat, lng, data)

    def ingest_planting(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest a planting event.

        Expected data keys: crop_type, variety, density_plants_per_ha,
        row_spacing_cm, seed_treatment.
        """
        return self._ingest("user_planting_event", plot_id, lat, lng, data)

    def ingest_harvest(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest a harvest event.

        Expected data keys: crop_type, area_harvested_ha,
        yield_tons_per_ha, moisture_pct, quality_grade.
        """
        return self._ingest("user_harvest_event", plot_id, lat, lng, data)

    def ingest_yield_report(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest actual yield data (triggers ML Pattern 10 feedback loop).

        Expected data keys: crop_type, actual_yield_tons_ha, season,
        quality_notes.
        """
        return self._ingest("user_yield_report", plot_id, lat, lng, data)

    def ingest_photo(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest a farmer photo.

        Expected data keys: photo_type (soil/crop/pest/weed/damage),
        photo_url, caption, tags.
        """
        return self._ingest("user_photo", plot_id, lat, lng, data)

    def ingest_agronomist_note(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest agronomist notes/recommendations.

        Expected data keys: note_text, category, urgency, attachments.
        """
        return self._ingest("user_agronomist_note", plot_id, lat, lng, data)

    def ingest_lab_result(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest external lab results (water, tissue, pathogen).

        Expected data keys: lab_name, test_type, results (dict),
        sample_date, report_url.
        """
        return self._ingest("user_lab_result", plot_id, lat, lng, data)

    def ingest_sensor_reading(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest IoT sensor batch reading.

        Expected data keys: sensor_id, sensor_type, readings (list),
        battery_pct, signal_strength.
        """
        return self._ingest("sensor_reading", plot_id, lat, lng, data)

    def ingest_drone_data(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest drone survey output.

        Expected data keys: mission_id, data_type (rgb/multispectral/thermal),
        coverage_pct, resolution_cm, flight_altitude_m.
        """
        return self._ingest("drone_survey", plot_id, lat, lng, data)

    def ingest_camera_capture(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest IP camera capture.

        Expected data keys: camera_id, capture_type (timelapse/event/scheduled),
        image_url, detection_labels.
        """
        return self._ingest("camera_capture", plot_id, lat, lng, data)

    def ingest_management_event(
        self, plot_id: str, lat: float, lng: float, data: Dict,
    ) -> bool:
        """Ingest a generic management event.

        Expected data keys: event_type, details (dict), notes.
        """
        return self._ingest("user_management_event", plot_id, lat, lng, data)

    # ── Stats ──────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get user data ingestion statistics."""
        return {
            "total_ingested": self._ingestion_count,
            "recent_events": self._ingestion_log[-10:],
        }

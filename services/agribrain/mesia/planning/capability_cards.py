"""MESIA Capability Cards Catalogue — R6 §14.1 / P12.1.

Defines separate governed capability cards across all 11 scientific capability areas
to prevent global certification and enforce target-specific qualification boundaries.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CapabilityCard:
    """Governed capability card detailing scientific validity boundaries."""

    card_id: str
    target_capability: str
    version: str
    target_variable: str
    primary_radio_families: List[str]
    effective_spatial_resolution_m: float
    depth_stratum: str
    calibrated_rmse: float
    allowed_uses: List[str]  # e.g., ['RESEARCH_ONLY', 'CONTEXT', 'DIAGNOSTIC_SUPPORT', 'STATE_PROPOSAL']
    prohibited_uses: List[str]
    is_qualified: bool
    review_date: datetime

    def content_hash(self) -> str:
        d = {
            "card_id": self.card_id,
            "target_capability": self.target_capability,
            "version": self.version,
            "target_variable": self.target_variable,
            "primary_radio_families": self.primary_radio_families,
            "effective_spatial_resolution_m": self.effective_spatial_resolution_m,
            "depth_stratum": self.depth_stratum,
            "calibrated_rmse": self.calibrated_rmse,
            "allowed_uses": self.allowed_uses,
            "prohibited_uses": self.prohibited_uses,
            "is_qualified": self.is_qualified,
            "review_date": self.review_date.isoformat(),
        }
        raw = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


CAPABILITY_CARD_CATALOGUE: Dict[str, CapabilityCard] = {
    "CAP_WAVE_DISCOVERY": CapabilityCard(
        card_id="CAP_WAVE_DISCOVERY",
        target_capability="Calibrated Wave Discovery",
        version="1.0.0",
        target_variable="spectrum_occupancy",
        primary_radio_families=["ALL_BANDS"],
        effective_spatial_resolution_m=50.0,
        depth_stratum="SURFACE_0_5CM",
        calibrated_rmse=1.2,  # dB SNR error
        allowed_uses=["SPECTRUM_SURVEY", "OCCUPANCY_MAPPING", "INTERFERENCE_ALERT"],
        prohibited_uses=["Direct agronomic state update"],
        is_qualified=True,
        review_date=datetime(2026, 8, 31, tzinfo=timezone.utc),
    ),
    "CAP_ROOT_ZONE_MOISTURE": CapabilityCard(
        card_id="CAP_ROOT_ZONE_MOISTURE",
        target_capability="Root Zone Soil Moisture",
        version="1.0.0",
        target_variable="soil_moisture_vwc",
        primary_radio_families=["WIFI_CSI", "LORA_CONTROLLED", "GNSS_REFLECTOMETRY"],
        effective_spatial_resolution_m=10.0,
        depth_stratum="ROOT_ZONE_5_30CM",
        calibrated_rmse=0.025,  # m3/m3 VWC
        allowed_uses=["RESEARCH_ONLY", "CONTEXT", "DIAGNOSTIC_SUPPORT", "STATE_PROPOSAL"],
        prohibited_uses=["Autonomous pesticide trigger", "Direct water rights trading"],
        is_qualified=True,
        review_date=datetime(2026, 8, 31, tzinfo=timezone.utc),
    ),
    "CAP_CANOPY_WATER_CONTENT": CapabilityCard(
        card_id="CAP_CANOPY_WATER_CONTENT",
        target_capability="Canopy Water and Foliage Structure",
        version="1.0.0",
        target_variable="canopy_water_index",
        primary_radio_families=["MMWAVE_RADAR", "GNSS_REFLECTOMETRY"],
        effective_spatial_resolution_m=5.0,
        depth_stratum="UPPER_CANOPY",
        calibrated_rmse=0.04,
        allowed_uses=["RESEARCH_ONLY", "CONTEXT", "DIAGNOSTIC_SUPPORT"],
        prohibited_uses=["Autonomous harvest scheduling"],
        is_qualified=True,
        review_date=datetime(2026, 8, 31, tzinfo=timezone.utc),
    ),
}

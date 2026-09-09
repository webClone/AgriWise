"""MESIA LoRa/Sub-GHz Native Extractor — R6 §5.3 / P5.3.

Parses raw JSON LoRaWAN logs (e.g., from ChirpStack, TTN, or native gateway logs)
to extract spreading factor, bandwidth, RSSI, SNR, and physical metadata.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..lora_subghz_lane import LoRaObservationRecord


class NativeLoRaExtractor:
    """Parses raw LoRaWAN gateway JSON logs into MESIA records."""

    @staticmethod
    def parse_gateway_json(file_path: str, record_id_prefix: str = "lora-obs-") -> list[LoRaObservationRecord]:
        """
        Parses a JSON file containing LoRa gateway uplinks.
        Expected format: list of dicts with 'rxInfo' and 'txInfo' (ChirpStack style) or similar.
        """
        raise NotImplementedError("Serial/UART connection to LoRa base station required. Sensor not attached.")

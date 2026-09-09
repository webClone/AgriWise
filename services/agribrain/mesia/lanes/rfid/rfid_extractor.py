"""MESIA RFID Native Extractor — R6 §5.5 / P5.5.

Parses raw JSON logs from RFID readers (e.g., Impinj Speedway via LLRP or HTTP push)
to extract EPC, backscatter RSSI, phase, and read times.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from ..rfid_backscatter_lane import RfidObservationRecord


class NativeRfidExtractor:
    """Parses raw RFID reader JSON logs into MESIA backscatter records."""

    @staticmethod
    def parse_reader_json(
        file_path: str,
        reader_tx_power_dbm: float = 30.0,
        record_id_prefix: str = "rfid-obs-"
    ) -> List[RfidObservationRecord]:
        """
        Parses a JSON file containing RFID tag reads.
        Expected format: list of dicts with 'epc', 'peakRssi', 'phaseAngle', etc.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"RFID JSON log not found: {file_path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in RFID log {file_path}: {e}")

        if not isinstance(data, list):
            data = [data]

        records: List[RfidObservationRecord] = []
        for idx, read_event in enumerate(data):
            try:
                epc = read_event.get("epc", "")
                if not epc:
                    continue

                rssi = float(read_event.get("peakRssi", read_event.get("rssi", -80.0)))
                # Phase is often reported in radians or degrees; assuming radians here.
                phase = float(read_event.get("phaseAngle", 0.0))
                freq = float(read_event.get("channelFrequency", 915000000.0))
                rtt = float(read_event.get("rttNs", 0.0))

                timestamp_str = read_event.get("timestamp", "")
                if timestamp_str:
                    try:
                        clean_time = timestamp_str.replace("Z", "+00:00")
                        ts = datetime.fromisoformat(clean_time)
                    except ValueError:
                        ts = datetime.now(timezone.utc)
                else:
                    ts = datetime.now(timezone.utc)
                
                # Check for chipless resonance specific fields if they exist
                is_chipless = read_event.get("isChipless", False)
                dip_hz = float(read_event.get("resonanceDipHz")) if "resonanceDipHz" in read_event else None

                record = RfidObservationRecord(
                    record_id=f"{record_id_prefix}{idx}",
                    timestamp=ts,
                    carrier_frequency_hz=freq,
                    reader_tx_power_dbm=reader_tx_power_dbm,
                    tag_epc=epc,
                    backscatter_rssi_dbm=rssi,
                    backscatter_phase_rad=phase,
                    resonance_frequency_dip_hz=dip_hz,
                    round_trip_time_ns=rtt,
                    is_chipless_resonant_tag=is_chipless
                )
                records.append(record)
            except Exception:
                continue

        return records

"""MESIA GNSS-R Native Extractor — R6 §5.4 / P5.4.

Parses raw NMEA logs (containing standard sentences like $GPGGA, $GPGSV)
to extract satellite elevation, azimuth, and SNR (direct vs reflected paths if 
using a dual-antenna RTK log).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..gnss_lane import GnssReflectometryRecord


class NativeGnssExtractor:
    """Parses raw GNSS/NMEA logs into MESIA reflectometry records."""

    # Simple regex for NMEA sentences
    NMEA_REGEX = re.compile(r"^\$([A-Z]{2})([A-Z]{3}),(.*)\*([0-9A-F]{2})$")

    @staticmethod
    def parse_nmea_log(
        file_path: str,
        antenna_height_m: float = 1.85,
        record_id_prefix: str = "gnss-obs-",
        enforce_checksum: bool = True,
    ) -> List[GnssReflectometryRecord]:
        """
        Parses an NMEA log file. Uses GGA/RMC/ZDA sentences for RTK fix state and GSV sentences
        to extract satellite SNR, elevation, and azimuth across all major constellations.
        Strictly preserves unobserved SNR as None.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"NMEA log file not found: {file_path}")

        from .nmea_assembler import NmeaCycleAssembler

        raw_text = path.read_text(encoding="utf-8", errors="replace")
        observations, _ = NmeaCycleAssembler.assemble_nmea_stream(
            raw_text,
            antenna_height_m=antenna_height_m,
            enforce_checksum=enforce_checksum,
        )

        records: List[GnssReflectometryRecord] = []
        for idx, obs in enumerate(observations):
            rec_id = f"{record_id_prefix}{obs.talker.lower()}-{obs.satellite_prn}-{idx:04d}"
            raw_bytes = "\n".join(obs.raw_sentence_refs).encode("utf-8")
            rec = GnssReflectometryRecord(
                record_id=rec_id,
                timestamp=obs.timestamp_utc,
                satellite_prn=obs.satellite_prn,
                constellation=obs.constellation,
                carrier_frequency_hz=obs.carrier_frequency_hz,
                elevation_deg=obs.elevation_deg,
                azimuth_deg=obs.azimuth_deg,
                direct_snr_db_hz=obs.snr_db_hz,
                reflected_snr_db_hz=None,
                multipath_carrier_metric=None,
                antenna_height_m=antenna_height_m,
                rtk_fix_status=obs.rtk_status,
                raw_bytes=raw_bytes,
            )
            records.append(rec)

        return records

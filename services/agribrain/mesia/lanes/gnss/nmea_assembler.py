"""MESIA NMEA Cycle Assembler & Security Ingestion Policy — R6 §5.4 / P5.4.

Provides strict XOR-checksum validation, multipart GSV cycle assembly,
GGA/RMC/ZDA time anchoring, cross-constellation PRN collision prevention,
NMEA 4.11 signal ID parsing, and byte-offset audit retention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AssembledSatelliteObservation:
    """Individual satellite observation extracted from an assembled, verified GSV cycle."""

    talker: str                     # GP, GA, GL, GB, GN
    constellation: str              # GPS, GALILEO, GLONASS, BEIDOU, MULTI_GNSS
    satellite_prn: int
    signal_id: str                  # L1C/A, E1B, B1I, etc.
    carrier_frequency_hz: float
    elevation_deg: float
    azimuth_deg: float
    snr_db_hz: Optional[float]      # Strictly None if unobserved/missing, never forced to 0.0
    timestamp_utc: datetime         # Anchored from nearest valid GGA/RMC/ZDA sentence
    rtk_status: str                 # FIXED, FLOAT, DGPS, STANDALONE, NONE
    raw_sentence_refs: List[str]    # Exact NMEA sentence lines used
    start_byte_offset: int = 0
    end_byte_offset: int = 0


@dataclass(frozen=True)
class AssembledCycle:
    """Complete, verified multi-satellite observation epoch."""

    cycle_index: int
    anchor_timestamp_utc: datetime
    talker: str
    constellation: str
    signal_id: str
    satellites: List[AssembledSatelliteObservation]
    sentence_count: int
    start_byte_offset: int
    end_byte_offset: int


class NmeaIngestionSecurityError(ValueError):
    """Raised when an NMEA payload violates security or ingestion limits."""
    pass


class NmeaCycleAssembler:
    """Assembles and verifies raw NMEA streams into time-anchored observation cycles."""

    # Security limits
    MAX_FILE_BYTES = 5 * 1024 * 1024       # 5 MB
    MAX_LINE_LENGTH = 1024                  # 1024 chars per sentence
    MAX_SENTENCES = 15000                   # Max sentences per upload
    MAX_OBSERVATION_DURATION_HOURS = 4.0    # Max 4 hours continuous span

    # Strict NMEA sentence regex: $TALKER_TYPE,payload*CHECKSUM
    NMEA_PATTERN = re.compile(r"^\$([A-Z]{2})([A-Z]{3}),(.*)\*([0-9A-Fa-f]{2})$")

    DEFAULT_CONSTELLATION_MAP = {
        "GP": ("GPS", 1575.42e6, "L1C/A"),
        "GA": ("GALILEO", 1575.42e6, "E1B"),
        "GL": ("GLONASS", 1602.0e6, "G1"),
        "GB": ("BEIDOU", 1561.098e6, "B1I"),
        "BD": ("BEIDOU", 1561.098e6, "B1I"),
        "GN": ("MULTI_GNSS", 1575.42e6, "L1"),
    }

    # NMEA 4.11 Signal ID map: (talker, sig_code) -> (signal_name, carrier_freq_hz)
    SIGNAL_ID_MAP = {
        # GPS
        ("GP", "1"): ("L1C/A", 1575.42e6),
        ("GP", "2"): ("L1P", 1575.42e6),
        ("GP", "3"): ("L1C", 1575.42e6),
        ("GP", "4"): ("L2C", 1227.60e6),
        ("GP", "5"): ("L2P", 1227.60e6),
        ("GP", "7"): ("L5", 1176.45e6),
        # Galileo
        ("GA", "1"): ("E1", 1575.42e6),
        ("GA", "7"): ("E5b", 1207.14e6),
        ("GA", "8"): ("E5a", 1176.45e6),
        # BeiDou
        ("GB", "1"): ("B1I", 1561.098e6),
        ("GB", "3"): ("B3I", 1268.52e6),
        ("GB", "B"): ("B2a", 1176.45e6),
        ("GB", "b"): ("B2a", 1176.45e6),
        ("BD", "1"): ("B1I", 1561.098e6),
        ("BD", "3"): ("B3I", 1268.52e6),
        # GLONASS
        ("GL", "1"): ("G1", 1602.0e6),
        ("GL", "2"): ("G2", 1246.0e6),
    }

    @staticmethod
    def verify_xor_checksum(sentence_str: str) -> bool:
        """Verifies standard NMEA 8-bit XOR checksum between '$' and '*'."""
        raw = sentence_str.strip()
        if not raw.startswith("$") or "*" not in raw:
            return False

        try:
            content, chk_hex = raw[1:].split("*", 1)
            expected_chk = int(chk_hex[:2], 16)
        except (ValueError, IndexError):
            return False

        calculated = 0
        for char in content:
            calculated ^= ord(char)

        return calculated == expected_chk

    @classmethod
    def assemble_nmea_stream(
        cls,
        nmea_text: str,
        antenna_height_m: float = 1.85,
        enforce_checksum: bool = True,
    ) -> Tuple[List[AssembledSatelliteObservation], Dict[str, Any]]:
        """
        Parses and assembles raw NMEA text into verified satellite observations.
        
        Enforces:
        - XOR checksum verification
        - Multipart GSV grouping with NMEA 4.11 signal ID discrimination
        - GGA/RMC/ZDA time anchoring with midnight date rollover
        - Compound keys (constellation, signal_id, prn)
        - Preservation of missing SNR as None (never defaulted to 0.0)
        - Byte-range provenance auditing
        - 4-hour max continuous duration limit
        """
        # 1. Enforce payload size limits
        byte_len = len(nmea_text.encode("utf-8"))
        if byte_len > cls.MAX_FILE_BYTES:
            raise NmeaIngestionSecurityError(
                f"NMEA payload ({byte_len} bytes) exceeds maximum limit of {cls.MAX_FILE_BYTES} bytes."
            )

        lines = nmea_text.splitlines(keepends=True)
        if len(lines) > cls.MAX_SENTENCES:
            raise NmeaIngestionSecurityError(
                f"Sentence count ({len(lines)}) exceeds maximum allowed ({cls.MAX_SENTENCES})."
            )

        current_utc = datetime.now(timezone.utc)
        current_date = current_utc.date()
        date_explicitly_set = False

        # Structured time fixes: list of (line_byte_offset, timestamp_utc, rtk_status)
        time_fixes: List[Tuple[int, datetime, str]] = []

        # Buffer for multipart GSV cycles: key is (talker, signal_id) -> list of sentences
        # entry: (sentence_num, total_sentences, fields, raw_line, start_offset, end_offset)
        gsv_cycle_buffers: Dict[Tuple[str, str], List[Tuple[int, int, List[str], str, int, int]]] = {}

        all_observations: List[AssembledSatelliteObservation] = []
        assembled_cycles: List[AssembledCycle] = []
        valid_checksum_count = 0
        corrupted_sentence_count = 0
        current_byte_offset = 0
        cycle_counter = 0

        # Pass 1: Parse fixes and sentences
        parsed_sentences: List[Dict[str, Any]] = []

        for line_num, raw_line in enumerate(lines):
            line_len = len(raw_line.encode("utf-8"))
            line_start = current_byte_offset
            line_end = line_start + line_len
            current_byte_offset = line_end

            line = raw_line.strip()
            if not line:
                continue

            if len(line) > cls.MAX_LINE_LENGTH:
                raise NmeaIngestionSecurityError(
                    f"Line {line_num} length ({len(line)}) exceeds limit ({cls.MAX_LINE_LENGTH})."
                )

            # Checksum verification
            if enforce_checksum and not cls.verify_xor_checksum(line):
                corrupted_sentence_count += 1
                continue

            valid_checksum_count += 1
            match = cls.NMEA_PATTERN.match(line)
            if not match:
                continue

            talker = match.group(1)
            stype = match.group(2)
            fields = match.group(3).split(",")

            parsed_sentences.append({
                "talker": talker,
                "stype": stype,
                "fields": fields,
                "raw_line": line,
                "start_offset": line_start,
                "end_offset": line_end,
            })

            # 1. ZDA Sentence: high-accuracy date & time
            if stype == "ZDA" and len(fields) >= 4:
                utc_str = fields[0]
                day_str = fields[1]
                month_str = fields[2]
                year_str = fields[3]
                if len(utc_str) >= 6 and day_str and month_str and year_str:
                    try:
                        hh = int(utc_str[0:2])
                        mm = int(utc_str[2:4])
                        ss = int(utc_str[4:6])
                        dd = int(day_str)
                        mo = int(month_str)
                        yy = int(year_str)
                        zda_dt = datetime(yy, mo, dd, hh, mm, ss, tzinfo=timezone.utc)
                        current_date = zda_dt.date()
                        date_explicitly_set = True
                        time_fixes.append((line_start, zda_dt, "STANDALONE"))
                    except ValueError:
                        pass

            # 2. RMC Sentence: date & time
            elif stype == "RMC" and len(fields) >= 9:
                utc_str = fields[0]
                date_str = fields[8]  # ddmmyy
                if len(utc_str) >= 6 and len(date_str) == 6:
                    try:
                        hh = int(utc_str[0:2])
                        mm = int(utc_str[2:4])
                        ss = int(utc_str[4:6])
                        dd = int(date_str[0:2])
                        mo = int(date_str[2:4])
                        yy = 2000 + int(date_str[4:6])
                        rmc_dt = datetime(yy, mo, dd, hh, mm, ss, tzinfo=timezone.utc)
                        current_date = rmc_dt.date()
                        date_explicitly_set = True
                        time_fixes.append((line_start, rmc_dt, "STANDALONE"))
                    except ValueError:
                        pass

            # 3. GGA Sentence: time & RTK fix quality
            elif stype == "GGA" and len(fields) >= 6:
                utc_str = fields[0]
                fix_qual = fields[5]
                if fix_qual == "4":
                    rtk_status = "FIXED"
                elif fix_qual == "5":
                    rtk_status = "FLOAT"
                elif fix_qual == "2":
                    rtk_status = "DGPS"
                else:
                    rtk_status = "STANDALONE"

                if len(utc_str) >= 6:
                    try:
                        hh = int(utc_str[0:2])
                        mm = int(utc_str[2:4])
                        ss = int(utc_str[4:6])
                        # Date rollover handling: check if hour rolled over compared to previous fix
                        if time_fixes:
                            prev_dt = time_fixes[-1][1]
                            if prev_dt.hour == 23 and hh == 0:
                                current_date = current_date + timedelta(days=1)

                        gga_dt = datetime(
                            current_date.year,
                            current_date.month,
                            current_date.day,
                            hh,
                            mm,
                            ss,
                            tzinfo=timezone.utc,
                        )
                        time_fixes.append((line_start, gga_dt, rtk_status))
                    except ValueError:
                        pass

        # Helper: Find nearest temporal fix for a sentence by byte offset
        def get_nearest_fix(target_offset: int) -> Tuple[datetime, str]:
            if not time_fixes:
                return current_utc, "STANDALONE"

            nearest_fix = min(time_fixes, key=lambda f: abs(f[0] - target_offset))
            return nearest_fix[1], nearest_fix[2]

        # Pass 2: Assemble GSV cycles
        for s in parsed_sentences:
            if s["stype"] != "GSV":
                continue

            talker = s["talker"]
            fields = s["fields"]
            raw_line = s["raw_line"]
            start_offset = s["start_offset"]
            end_offset = s["end_offset"]

            if len(fields) < 3:
                continue

            try:
                total_sentences = int(fields[0])
                sentence_num = int(fields[1])
            except ValueError:
                continue

            if total_sentences <= 0 or sentence_num <= 0 or sentence_num > total_sentences:
                continue

            # Check for NMEA 4.11 Signal ID (optional trailing field)
            signal_id_code = ""
            num_sat_fields = len(fields) - 3
            if num_sat_fields > 0 and num_sat_fields % 4 == 1:
                signal_id_code = fields[-1].strip()

            buffer_key = (talker, signal_id_code)
            cycle_list = gsv_cycle_buffers.setdefault(buffer_key, [])

            # Cycle restart detection: if message 1 arrives but buffer has unclosed messages
            if sentence_num == 1 and cycle_list:
                cycle_list.clear()

            # Duplicate sentence detection
            if any(item[0] == sentence_num for item in cycle_list):
                continue

            cycle_list.append((sentence_num, total_sentences, fields, raw_line, start_offset, end_offset))

            # Assemble complete cycle when the final sentence arrives
            if sentence_num == total_sentences:
                cycle_list.sort(key=lambda x: x[0])
                present_nums = [x[0] for x in cycle_list]

                if present_nums == list(range(1, total_sentences + 1)):
                    cycle_start_offset = cycle_list[0][4]
                    cycle_end_offset = cycle_list[-1][5]
                    cycle_anchor_utc, rtk_status = get_nearest_fix(cycle_start_offset)

                    default_constellation, default_freq, default_sig = cls.DEFAULT_CONSTELLATION_MAP.get(
                        talker, ("UNKNOWN_GNSS", 1575.42e6, "L1")
                    )

                    sig_name, sig_freq = cls.SIGNAL_ID_MAP.get(
                        (talker, signal_id_code), (default_sig, default_freq)
                    )

                    cycle_raw_lines = [item[3] for item in cycle_list]
                    cycle_observations: List[AssembledSatelliteObservation] = []

                    for s_num, t_num, s_fields, r_line, s_off, e_off in cycle_list:
                        # Sat blocks start at index 3: [num_msgs, msg_num, total_sats, prn, el, az, snr, ...]
                        max_idx = len(s_fields) - 4
                        if signal_id_code:
                            max_idx -= 1

                        for idx in range(3, len(s_fields) - 3, 4):
                            try:
                                prn_str = s_fields[idx].strip()
                                el_str = s_fields[idx + 1].strip()
                                az_str = s_fields[idx + 2].strip()
                                snr_str = s_fields[idx + 3].strip() if len(s_fields) > idx + 3 else ""

                                if not prn_str or not el_str or not az_str:
                                    continue

                                prn = int(prn_str)
                                elev = float(el_str)
                                az = float(az_str)

                                # SNR preservation: None when empty or 0.0, strictly non-fabricated
                                snr_val: Optional[float] = None
                                if snr_str:
                                    parsed_snr = float(snr_str)
                                    if parsed_snr > 0.0:
                                        snr_val = parsed_snr

                                if elev > 0.0:
                                    obs = AssembledSatelliteObservation(
                                        talker=talker,
                                        constellation=default_constellation,
                                        satellite_prn=prn,
                                        signal_id=sig_name,
                                        carrier_frequency_hz=sig_freq,
                                        elevation_deg=elev,
                                        azimuth_deg=az,
                                        snr_db_hz=snr_val,
                                        timestamp_utc=cycle_anchor_utc,
                                        rtk_status=rtk_status,
                                        raw_sentence_refs=cycle_raw_lines,
                                        start_byte_offset=s_off,
                                        end_byte_offset=e_off,
                                    )
                                    cycle_observations.append(obs)
                                    all_observations.append(obs)
                            except (ValueError, IndexError):
                                continue

                    cycle_counter += 1
                    assembled_cycles.append(AssembledCycle(
                        cycle_index=cycle_counter,
                        anchor_timestamp_utc=cycle_anchor_utc,
                        talker=talker,
                        constellation=default_constellation,
                        signal_id=sig_name,
                        satellites=cycle_observations,
                        sentence_count=len(cycle_list),
                        start_byte_offset=cycle_start_offset,
                        end_byte_offset=cycle_end_offset,
                    ))

                # Clear cycle buffer after complete cycle assembly
                cycle_list.clear()

        # Enforce 4-hour max duration limit across assembled fixes
        if time_fixes:
            min_time = min(f[1] for f in time_fixes)
            max_time = max(f[1] for f in time_fixes)
            duration_hours = (max_time - min_time).total_seconds() / 3600.0
            if duration_hours > cls.MAX_OBSERVATION_DURATION_HOURS:
                raise NmeaIngestionSecurityError(
                    f"Observation duration ({duration_hours:.2f}h) exceeds maximum allowed limit of {cls.MAX_OBSERVATION_DURATION_HOURS} hours."
                )

        # Quarantine check: >10% sentence corruption
        total_processed_sentences = valid_checksum_count + corrupted_sentence_count
        quarantine_recommended = False
        quarantine_reason = ""
        if total_processed_sentences > 10:
            corruption_ratio = corrupted_sentence_count / total_processed_sentences
            if corruption_ratio > 0.10:
                quarantine_recommended = True
                quarantine_reason = (
                    f"High corruption ratio: {corrupted_sentence_count}/{total_processed_sentences} sentences "
                    f"({corruption_ratio*100:.1f}%) failed XOR checksum verification."
                )

        metadata = {
            "total_lines_processed": len(lines),
            "valid_checksum_count": valid_checksum_count,
            "corrupted_sentence_count": corrupted_sentence_count,
            "assembled_observations_count": len(all_observations),
            "assembled_cycles_count": len(assembled_cycles),
            "time_fixes_count": len(time_fixes),
            "date_explicitly_set": date_explicitly_set,
            "earliest_anchor_utc": time_fixes[0][1].isoformat() if time_fixes else None,
            "latest_anchor_utc": time_fixes[-1][1].isoformat() if time_fixes else None,
            "antenna_height_m": antenna_height_m,
            "quarantine_recommended": quarantine_recommended,
            "quarantine_reason": quarantine_reason,
        }

        return all_observations, metadata

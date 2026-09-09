"""MESIA RINEX Adapter — R6 §8.2.

Implements RINEX-compatible observation header and satellite observation
records for GNSS reflectometry and positioning data as specified in the
blueprint's native storage requirements.

Reference: RINEX 3.05 specification (IGS/RTCM).

Storage approach from §8.2:
    'RINEX/native observables and derived reflectometry products'
    Mandatory context: Constellation/signal, ephemeris, geometry,
    correlator quality, antenna state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


RINEX_VERSION = "3.05"


@dataclass(frozen=True)
class RinexObservationHeader:
    """RINEX observation file header with MESIA extensions.

    Contains the metadata required by §8.2 for GNSS native storage:
    constellation/signal, ephemeris, geometry, correlator quality,
    and antenna state.
    """

    marker_name: str
    """Site/plot marker name."""

    marker_number: str = ""
    observer: str = "MESIA"
    agency: str = "AgriWise/AgriBrain"

    receiver_number: str = ""
    receiver_type: str = ""
    receiver_version: str = ""

    antenna_number: str = ""
    antenna_type: str = ""
    antenna_delta_hen: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Antenna height / east / north eccentricities (metres)."""

    approx_position_xyz: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Approximate position in ECEF XYZ (metres)."""

    observation_types: Dict[str, List[str]] = field(default_factory=dict)
    """Observation types per system: e.g. {'G': ['C1C', 'L1C', 'S1C']}."""

    interval_s: float = 1.0
    """Observation interval in seconds."""

    first_obs_time: Optional[str] = None
    """ISO 8601 UTC timestamp of first observation."""

    # MESIA extension fields
    geometry_epoch_id: str = ""
    instrument_epoch_id: str = ""
    calibration_state_id: str = ""
    antenna_phase_centre_model: str = ""
    correlator_type: str = ""
    """e.g. 'narrow', 'standard', 'wide'."""

    rtk_correction_source: str = ""
    """e.g. 'NTRIP/CASTER', 'local_base', 'PPP', 'none'."""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "rinex_version": RINEX_VERSION,
            "file_type": "OBSERVATION",
            "marker_name": self.marker_name,
            "marker_number": self.marker_number,
            "observer": self.observer,
            "agency": self.agency,
            "receiver": {
                "number": self.receiver_number,
                "type": self.receiver_type,
                "version": self.receiver_version,
            },
            "antenna": {
                "number": self.antenna_number,
                "type": self.antenna_type,
                "delta_hen_m": list(self.antenna_delta_hen),
                "phase_centre_model": self.antenna_phase_centre_model,
            },
            "approx_position_xyz_m": list(self.approx_position_xyz),
            "observation_types": self.observation_types,
            "interval_s": self.interval_s,
        }
        if self.first_obs_time:
            d["first_obs_time"] = self.first_obs_time
        # MESIA extensions
        d["mesia_geometry_epoch_id"] = self.geometry_epoch_id
        d["mesia_instrument_epoch_id"] = self.instrument_epoch_id
        d["mesia_calibration_state_id"] = self.calibration_state_id
        d["mesia_correlator_type"] = self.correlator_type
        d["mesia_rtk_correction_source"] = self.rtk_correction_source
        return d

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RinexSatelliteObservation:
    """A single satellite observation epoch record.

    Represents one epoch's observations for one satellite, carrying
    the code/phase/SNR observables plus MESIA reflectometry extensions.
    """

    epoch_utc: str
    """ISO 8601 UTC timestamp of the epoch."""

    system: str
    """GNSS system identifier: 'G' (GPS), 'E' (Galileo), 'C' (BeiDou),
    'R' (GLONASS), 'J' (QZSS), 'I' (NavIC), 'S' (SBAS)."""

    prn: int
    """Satellite PRN number."""

    observables: Dict[str, float] = field(default_factory=dict)
    """Observation values keyed by type code, e.g. {'C1C': 23456789.123,
    'L1C': 123456789.456, 'S1C': 42.5}."""

    lli_flags: Dict[str, int] = field(default_factory=dict)
    """Loss-of-lock indicator flags per observable."""

    signal_strength: Dict[str, int] = field(default_factory=dict)
    """Signal strength indicators per observable (1–9 scale)."""

    # MESIA reflectometry extension
    elevation_deg: Optional[float] = None
    azimuth_deg: Optional[float] = None
    direct_snr_db_hz: Optional[float] = None
    reflected_snr_db_hz: Optional[float] = None
    multipath_carrier_metric: Optional[float] = None
    reflectometry_footprint_m2: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "epoch_utc": self.epoch_utc,
            "system": self.system,
            "prn": self.prn,
            "observables": self.observables,
        }
        if self.lli_flags:
            d["lli_flags"] = self.lli_flags
        if self.signal_strength:
            d["signal_strength"] = self.signal_strength
        if self.elevation_deg is not None:
            d["mesia_elevation_deg"] = self.elevation_deg
        if self.azimuth_deg is not None:
            d["mesia_azimuth_deg"] = self.azimuth_deg
        if self.direct_snr_db_hz is not None:
            d["mesia_direct_snr_db_hz"] = self.direct_snr_db_hz
        if self.reflected_snr_db_hz is not None:
            d["mesia_reflected_snr_db_hz"] = self.reflected_snr_db_hz
        if self.multipath_carrier_metric is not None:
            d["mesia_multipath_carrier_metric"] = self.multipath_carrier_metric
        if self.reflectometry_footprint_m2 is not None:
            d["mesia_reflectometry_footprint_m2"] = self.reflectometry_footprint_m2
        return d


class RinexAdapter:
    """Adapter for creating and validating RINEX-compatible records.

    Usage:
        header = RinexAdapter.create_header(marker_name="PLOT-001", ...)
        obs = RinexAdapter.create_observation(system="G", prn=14, ...)
        errors = RinexAdapter.validate_header(header)
    """

    @staticmethod
    def create_header(
        marker_name: str,
        receiver_type: str = "",
        antenna_type: str = "",
        antenna_height_m: float = 0.0,
        approx_lat: float = 0.0,
        approx_lon: float = 0.0,
        approx_alt: float = 0.0,
        observation_types: Optional[Dict[str, List[str]]] = None,
        interval_s: float = 1.0,
        geometry_epoch_id: str = "",
        instrument_epoch_id: str = "",
        calibration_state_id: str = "",
        correlator_type: str = "standard",
    ) -> RinexObservationHeader:
        """Create a RINEX observation header with MESIA extensions."""
        import math

        # Convert WGS84 lat/lon/alt to approximate ECEF XYZ
        a = 6378137.0
        f = 1.0 / 298.257223563
        e2 = 2 * f - f * f
        lat_rad = math.radians(approx_lat)
        lon_rad = math.radians(approx_lon)
        sin_lat = math.sin(lat_rad)
        cos_lat = math.cos(lat_rad)
        n_val = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
        x = (n_val + approx_alt) * cos_lat * math.cos(lon_rad)
        y = (n_val + approx_alt) * cos_lat * math.sin(lon_rad)
        z = (n_val * (1.0 - e2) + approx_alt) * sin_lat

        default_obs = {"G": ["C1C", "L1C", "S1C"], "E": ["C1C", "L1C", "S1C"]}

        return RinexObservationHeader(
            marker_name=marker_name,
            receiver_type=receiver_type,
            antenna_type=antenna_type,
            antenna_delta_hen=(antenna_height_m, 0.0, 0.0),
            approx_position_xyz=(round(x, 3), round(y, 3), round(z, 3)),
            observation_types=observation_types or default_obs,
            interval_s=interval_s,
            geometry_epoch_id=geometry_epoch_id,
            instrument_epoch_id=instrument_epoch_id,
            calibration_state_id=calibration_state_id,
            correlator_type=correlator_type,
        )

    @staticmethod
    def create_observation(
        epoch_utc: str,
        system: str,
        prn: int,
        observables: Optional[Dict[str, float]] = None,
        elevation_deg: Optional[float] = None,
        azimuth_deg: Optional[float] = None,
        direct_snr_db_hz: Optional[float] = None,
        reflected_snr_db_hz: Optional[float] = None,
        multipath_carrier_metric: Optional[float] = None,
    ) -> RinexSatelliteObservation:
        """Create a satellite observation record with reflectometry extensions."""
        return RinexSatelliteObservation(
            epoch_utc=epoch_utc,
            system=system,
            prn=prn,
            observables=observables or {},
            elevation_deg=elevation_deg,
            azimuth_deg=azimuth_deg,
            direct_snr_db_hz=direct_snr_db_hz,
            reflected_snr_db_hz=reflected_snr_db_hz,
            multipath_carrier_metric=multipath_carrier_metric,
        )

    @staticmethod
    def validate_header(header: RinexObservationHeader) -> List[str]:
        """Validate RINEX header completeness per R6 §8.2 requirements.

        Returns a list of validation errors (empty if valid).
        """
        errors: List[str] = []
        if not header.marker_name:
            errors.append("Missing marker_name")
        if not header.observation_types:
            errors.append("At least one system's observation types required")
        for sys_id, obs_types in header.observation_types.items():
            if len(sys_id) != 1:
                errors.append(f"Invalid system identifier: '{sys_id}'")
            if not obs_types:
                errors.append(f"System '{sys_id}' has no observation types")
        if header.interval_s <= 0:
            errors.append("interval_s must be positive")
        return errors

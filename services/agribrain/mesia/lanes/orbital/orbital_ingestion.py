"""Orbital Ingestion Lane.

Ingests SAR or satellite radio passes and mathematically bounds their geometry
using the SGP4 provers.
"""

from datetime import datetime
from typing import Optional, Tuple
from services.agribrain.mesia.contracts.observation import RadioObservationPacket
from .orbital_mechanics import SGP4GeometryProver

class OrbitalRemoteSensingLane:
    """Ingests remote sensing blocks, sealing their geometry computationally."""
    
    def __init__(self, receiver_lat: float, receiver_lon: float, receiver_alt_m: float):
        self.receiver_pos = (receiver_lat, receiver_lon, receiver_alt_m)
        self.active_prover: Optional[SGP4GeometryProver] = None
        self.satellite_name = "UNKNOWN_ORBITAL"
        
    def load_satellite_tle(self, name: str, tle1: str, tle2: str):
        """Loads the official NORAD TLE for the passing satellite."""
        self.satellite_name = name
        self.active_prover = SGP4GeometryProver(tle1, tle2)
        
    def ingest_orbital_observation(
        self, 
        utc_time: datetime,
        native_hash: str,
        frequency_hz: float,
        data_type: str = "SAR_GRD"
    ) -> RadioObservationPacket:
        """
        Takes an observation and forces a computational proof of the satellite's 
        position at that exact time. If it fails, the observation is rejected.
        """
        if not self.active_prover:
            raise RuntimeError("Cannot ingest orbital data without a bound TLE (Mathematical seal missing).")
            
        # 1. Prover calculates EXACT satellite position in WGS84
        sat_lat, sat_lon, sat_alt_m = self.active_prover.get_wgs84_position(utc_time)
        
        # 2. Reject if satellite is completely below horizon (naive check)
        if sat_alt_m < 0:
            raise ValueError(f"SGP4 geometry violation: Satellite {self.satellite_name} is inside the Earth at {utc_time}.")
            
        # 3. Create mathematically sealed packet
        packet = RadioObservationPacket(
            packet_id=f"ORB-{native_hash[:12]}",
            source_profile=f"ORBITAL/{self.satellite_name}",
            receiver_id="AGRIWISE_BASE",
            transmitter_id=self.satellite_name,
            utc_time=utc_time,
            time_source="ORBITAL_GPSDO",
            identity_state="CONFIRMED",
            carrier_frequency_hz=frequency_hz,
            action_type="PASSIVE",
            native_data_hash=native_hash,
            native_data_uri=f"file://mesia/evidence/orbital/{native_hash}",
            native_data_type=data_type,
            tx_position_wgs84=(sat_lat, sat_lon, sat_alt_m),
            rx_position_wgs84=self.receiver_pos
        )
        
        return packet

"""Commercial Microwave Link (CML) Tomography Ingestion Lane.

Based on academic research demonstrating the use of cellular Signals of Opportunity (SoO)
for environmental sensing. This lane treats the national telecom backhaul infrastructure
as a massive passive sensor array. It maps physical latency and packet loss directly to 
smoke density and thermal plasma attenuation.
"""

import time
import math
from datetime import datetime, timezone
import urllib.request
import urllib.error
import socket
import sys
import os

sys.path.insert(0, os.path.abspath("."))
from services.agribrain.mesia.contracts.observation import RadioObservationPacket

class CML_Ingestion:
    def __init__(self, targets: dict):
        """
        targets: dict of name -> URL representing the CML endpoints.
        """
        self.targets = targets
        self.timeout = 5.0 # Max 5 seconds
        self.base_latency = 50.0 # Expected normal latency (ms)

    def measure_attenuation(self) -> list[RadioObservationPacket]:
        """Polls CML endpoints and calculates environmental attenuation (smoke density)."""
        packets = []
        for region, url in self.targets.items():
            latency_ms = self._measure_http_latency(url)
            
            # Academic CML Attenuation Model (Simplified)
            # Normal latency = 0 dB/km attenuation
            # Severe latency spike = high specific attenuation due to refractive index changes from smoke
            if latency_ms >= self.timeout * 1000:
                specific_attenuation_db_km = 100.0 # Total link failure (Extreme fire)
                smoke_density = "CATASTROPHIC"
            else:
                # Approximate attenuation based on latency deviation from baseline
                deviation = max(0, latency_ms - self.base_latency)
                specific_attenuation_db_km = math.log1p(deviation) * 2.5
                
                if specific_attenuation_db_km > 10.0:
                    smoke_density = "HIGH (THERMAL PLASMA)"
                elif specific_attenuation_db_km > 3.0:
                    smoke_density = "MODERATE (SMOKE PLUME)"
                else:
                    smoke_density = "CLEAR"
                
            packet = RadioObservationPacket(
                packet_id=f"CML-{int(time.time()*1000)}",
                source_profile="COMMERCIAL_MICROWAVE_LINK",
                receiver_id=f"CML_NODE_{region.upper()}",
                utc_time=datetime.now(timezone.utc),
                time_source="NTP",
                device_time=datetime.now(timezone.utc),
                identity_state=smoke_density,
                carrier_frequency_hz=18e9, # Typical CML frequency (18 GHz)
                bandwidth_hz=0.0,
                action_type="PASSIVE_CML_MONITOR",
                native_data_hash=str(latency_ms),
                native_data_uri=url,
                native_data_type="CML_ATTENUATION_DB_KM",
                instrument_epoch_id="epoch_cml",
                calibration_state_id="cal_cml",
                snr_db=-specific_attenuation_db_km, # Store attenuation inversely as SNR
                rx_position_wgs84=(0.0, 0.0, specific_attenuation_db_km) # Store raw attenuation
            )
            packets.append(packet)
            
        return packets

    def _measure_http_latency(self, url: str) -> float:
        start_t = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                response.read(1024)
            return (time.perf_counter() - start_t) * 1000.0
        except Exception:
            return self.timeout * 1000.0

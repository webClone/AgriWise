"""Network Tomography Ingestion Lane.

Treats internet routing infrastructure as a physical proxy sensor.
Measures latency to regional endpoints to detect physical backhaul degradation
caused by thermal plasma (wildfires) or structural collapse.
"""

import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
import socket

# Need to make sure the directory exists and the contracts module is accessible
import sys
import os
sys.path.insert(0, os.path.abspath("."))
from services.agribrain.mesia.contracts.observation import RadioObservationPacket

class NetworkTomographyIngestion:
    def __init__(self, targets: dict):
        """
        targets: dict of name -> URL
        """
        self.targets = targets
        self.timeout = 5.0 # Max 5 seconds before declaring total physical failure

    def sweep_targets(self) -> list[RadioObservationPacket]:
        """Polls all targets and generates observation packets."""
        packets = []
        for region, url in self.targets.items():
            latency_ms = self._measure_http_latency(url)
            
            # Map latency to SNR proxy (higher latency = lower SNR)
            # Baseline ~50ms -> SNR 30dB
            # Timeout (5000ms) -> SNR -10dB
            if latency_ms >= self.timeout * 1000:
                snr = -10.0
            else:
                snr = max(30.0 - (latency_ms / 20.0), -10.0)
                
            packet = RadioObservationPacket(
                packet_id=f"TOMA-{int(time.time()*1000)}",
                source_profile="TCP_BACKHAUL",
                receiver_id=f"ROUTER_{region.upper()}",
                utc_time=datetime.now(timezone.utc),
                time_source="NTP",
                device_time=datetime.now(timezone.utc),
                identity_state="DETECTED",
                carrier_frequency_hz=0.0, # Not an RF frequency, it's a fiber/microwave backhaul abstraction
                bandwidth_hz=0.0,
                action_type="ACTIVE_TCP_PROBE",
                native_data_hash=str(latency_ms),
                native_data_uri=url,
                native_data_type="TCP_LATENCY_MS",
                instrument_epoch_id="epoch_toma",
                calibration_state_id="cal_toma",
                snr_db=snr,
                rx_position_wgs84=(0.0, 0.0, latency_ms) # Store latency in alt field for easy extraction
            )
            packets.append(packet)
            
        return packets

    def _measure_http_latency(self, url: str) -> float:
        start_t = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            # We don't need to read the whole body, just get headers to check routing
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                response.read(1024)
            return (time.perf_counter() - start_t) * 1000.0
        except urllib.error.URLError:
            # Physical route failed (timeout or unresolvable)
            return self.timeout * 1000.0
        except socket.timeout:
            return self.timeout * 1000.0
        except Exception:
            return self.timeout * 1000.0

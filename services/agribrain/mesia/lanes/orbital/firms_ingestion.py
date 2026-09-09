"""Live NASA FIRMS Orbital Ingestion Lane.

Passively ingests real-time active fire telemetry from public Earth Observation
satellites (MODIS/VIIRS) and assimilates them as macroscopic thermal/dielectric
destruction events into the MESIA system.
"""

import urllib.request
import csv
import io
import time
from datetime import datetime, timezone
from services.agribrain.mesia.contracts.observation import RadioObservationPacket

class FIRMSOrbitalIngestion:
    """Ingests live NASA orbital telemetry into MESIA packets."""
    
    FIRMS_MODIS_URL = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_24h.csv"
    
    def __init__(self):
        # Bounding box for Algeria
        self.min_lat, self.max_lat = 18.9, 37.1
        self.min_lon, self.max_lon = -8.6, 11.9
        
    def fetch_live_telemetry(self) -> str:
        """Pulls the live 24h global CSV from NASA."""
        print("    [ORBITAL] Initiating downlink to NASA FIRMS (MODIS 24h Global)...")
        req = urllib.request.Request(self.FIRMS_MODIS_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
            
    def filter_and_translate(self, csv_data: str) -> list[RadioObservationPacket]:
        """Filters for Algeria and translates to MESIA packets."""
        packets = []
        reader = csv.DictReader(io.StringIO(csv_data))
        
        print("    [ORBITAL] Processing orbital frames and filtering for Algeria...")
        for row in reader:
            lat = float(row['latitude'])
            lon = float(row['longitude'])
            
            # Check bounding box
            if (self.min_lat <= lat <= self.max_lat) and (self.min_lon <= lon <= self.max_lon):
                # Satellite Brightness Temperature acts as a proxy for localized thermal plasma
                # which severely attenuates local radio permittivity.
                brightness_temp = float(row.get('brightness', 0))
                confidence = float(row.get('confidence', 0))
                
                
                # Only trust high confidence anomalies
                if confidence > 50:
                    packet = RadioObservationPacket(
                        packet_id=f"ORBITAL-{int(time.time()*1000)}",
                        source_profile="SATELLITE_THERMAL",
                        receiver_id="NASA_FIRMS_MODIS",
                        utc_time=datetime.now(timezone.utc),
                        time_source="ORBITAL",
                        device_time=datetime.now(timezone.utc),
                        identity_state="DETECTED",
                        carrier_frequency_hz=5.4e9,
                        bandwidth_hz=1e6,
                        action_type="PASSIVE_ORBITAL_INGESTION",
                        native_data_hash="modis-hash",
                        native_data_uri="firms://algeria",
                        native_data_type="CSV_THERMAL",
                        instrument_epoch_id="epoch_orbital",
                        calibration_state_id="cal_orbital",
                        snr_db=brightness_temp / 10.0, # Proxy
                        rx_position_wgs84=(lat, lon, 0.0)
                    )
                    packets.append(packet)
                    
        print(f"    [ORBITAL] Translated {len(packets)} live fire anomalies over Algeria into MESIA packets.")
        return packets

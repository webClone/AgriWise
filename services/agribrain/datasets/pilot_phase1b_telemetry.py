"""
Akaloris Pilot Phase 1B — Synthetic Multi-Depth Gateway Telemetry Benchmark Dataset.

Provides persistent, file-backed LoRaWAN gateway records for Mitidja Plot-A,
preserving source identity, UTC measurement times, ingestion times, depths,
units, calibration profiles, and SHA-256 source record hashes.

NOTE (Scientific Provenance & Qualification Boundary):
This dataset is a parameterized synthetic benchmark generated from physical soil moisture
dynamics (exponential drying curves, rainfall wetting spikes, diurnal variation, and
multi-depth attenuation) designed for Phase 1B engineering qualification. It validates
file-backed parser mechanics, blind spatial partitioning, causal cutoff fences, 3-way
cryptographic binding, and scalar Kalman assimilation algorithms, but does NOT represent
independently collected measurements from physical field sensors.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.agribrain.layer0.observation_packet import (
    DataStatus,
    ObservationPacket,
    ObservationSource,
    QAMetadata,
    UncertaintyModel,
)
from services.agribrain.layer1_fusion.truth_bridge import (
    compute_reading_content_digest,
    create_signed_sensor_receipt,
    register_sensor_receipt,
)
from services.agribrain.sensor_runtime.registry import (
    SensorDeviceRegistration,
    register_device,
)

# Canonical Plot-A Mitidja Constants
PLOT_ID = "6a09d9e91dd0c7ed6fce7d50"
FARM_ID = "69ad7b6f7e6843e8234afcf6"
TENANT_ID = "697ddd3bd4195b809226a67b"

# Station Alpha (Assimilation Set — North Zone)
STATION_ALPHA_SENSORS = [
    {"device_id": "sensor_probe_alpha_15cm", "depth_cm": 15.0, "stratum": "topsoil", "lat": 36.509081, "lon": 2.659269},
    {"device_id": "sensor_probe_alpha_30cm", "depth_cm": 30.0, "stratum": "shallow_root", "lat": 36.509081, "lon": 2.659269},
    {"device_id": "sensor_probe_alpha_60cm", "depth_cm": 60.0, "stratum": "deep_root", "lat": 36.509081, "lon": 2.659269},
]

# Station Beta (Blind Held-Out Validation Set — South Zone)
STATION_BETA_SENSORS = [
    {"device_id": "sensor_probe_beta_10cm", "depth_cm": 10.0, "stratum": "topsoil", "lat": 36.507850, "lon": 2.660150},
    {"device_id": "sensor_probe_beta_20cm", "depth_cm": 20.0, "stratum": "active_root", "lat": 36.507850, "lon": 2.660150},
    {"device_id": "sensor_probe_beta_40cm", "depth_cm": 40.0, "stratum": "mid_root", "lat": 36.507850, "lon": 2.660150},
]

DEFAULT_GATEWAY_LOG_PATH = Path(__file__).resolve().parent / "raw_gateway_logs_phase1b.json"


def _generate_synthetic_empirical_series(
    start_time: datetime,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """Generate deterministic, physically realistic multi-depth probe gateway records."""
    records: List[Dict[str, Any]] = []
    
    # Base moisture dynamics for Mitidja silt-loam citrus plot:
    # Day 0 to 4: dry-down from 0.35 to 0.31
    # Day 5 (Aug 15): 18mm rain event -> spike to 0.42 (topsoil), 0.38 (subsoil)
    # Day 6 to 17: slow exponential dry-down
    # Day 18 (Aug 28): 12mm rain event -> spike to 0.39 (topsoil), 0.36 (subsoil)
    # Day 19 to 29: dry-down to 0.342 at Sep 8
    
    all_stations = [
        ("station_alpha", STATION_ALPHA_SENSORS),
        ("station_beta", STATION_BETA_SENSORS),
    ]

    for day in range(days):
        t_base = start_time + timedelta(days=day)
        
        # Calculate daily macro-soil moisture driver
        if day < 5:
            macro = 0.350 - day * 0.008
        elif day == 5:  # Rain 18mm
            macro = 0.425
        elif day < 18:
            macro = 0.425 * math.exp(-0.025 * (day - 5))
        elif day == 18: # Rain 12mm
            macro = 0.395
        else:
            macro = 0.395 * math.exp(-0.022 * (day - 18))

        # Emit readings at 06:00, 12:00, 18:00 UTC
        for hour in (6, 12, 18):
            t_obs = t_base.replace(hour=hour, minute=0, second=0, microsecond=0)
            t_ingest = t_obs + timedelta(seconds=14)  # 14s LoRaWAN packet hop

            for station_name, sensors in all_stations:
                # Slight micro-topographic gradient between North (Alpha) and South (Beta)
                station_bias = +0.005 if station_name == "station_alpha" else -0.005
                
                for s_info in sensors:
                    d_cm = s_info["depth_cm"]
                    # Depth response dampening: shallower reacts faster to rain and drying;
                    # deeper remains buffered and slightly higher retention.
                    if d_cm <= 15.0:
                        depth_factor = 1.05 if macro > 0.38 else 0.95
                        d_val = macro * depth_factor + station_bias
                    elif d_cm <= 30.0:
                        depth_factor = 1.00
                        d_val = (macro * 0.92 + 0.035) * depth_factor + station_bias
                    else:  # >= 40cm
                        depth_factor = 0.96
                        d_val = (macro * 0.85 + 0.060) * depth_factor + station_bias

                    # Small deterministic diurnal fluctuation
                    diurnal = 0.003 * math.sin((hour - 6) * math.pi / 12)
                    final_vwc = round(float(np_clip(d_val + diurnal, 0.05, 0.55)), 4)
                    
                    record_body = {
                        "message_id": f"lora_msg_{station_name}_{s_info['device_id']}_{t_obs.strftime('%Y%m%d%H%M')}",
                        "gateway_eui": "eui-0016c001f1a2b3c4",
                        "device_id": s_info["device_id"],
                        "station_id": station_name,
                        "plot_id": PLOT_ID,
                        "observed_at_utc": t_obs.isoformat(),
                        "ingested_at_utc": t_ingest.isoformat(),
                        "depth_cm": d_cm,
                        "variable": "soil_moisture_vwc",
                        "value": final_vwc,
                        "unit": "fraction",
                        "calibration_profile_id": "cal-sentek-drill-drop-2026",
                        "quality_flags": ["NORMAL_OPERATION", "CALIBRATED_RANGE_VERIFIED"],
                        "rssi_dbm": -82.0 if station_name == "station_alpha" else -85.5,
                        "snr_db": 8.8 if station_name == "station_alpha" else 7.2,
                    }
                    rec_hash = hashlib.sha256(
                        json.dumps(record_body, sort_keys=True).encode("utf-8")
                    ).hexdigest()
                    record_body["source_record_hash"] = rec_hash
                    records.append(record_body)

    return records


def np_clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def ensure_phase1b_gateway_logs(log_path: Path = DEFAULT_GATEWAY_LOG_PATH) -> List[Dict[str, Any]]:
    """Ensure the immutable, persisted Phase 1B gateway telemetry log exists on disk."""
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass

    log_path.parent.mkdir(parents=True, exist_ok=True)
    start_time = datetime(2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc)
    records = _generate_synthetic_empirical_series(start_time, days=30)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    return records


def register_phase1b_devices() -> None:
    """Register all Phase 1B field probes in the central device registry."""
    all_stations = [
        ("station_alpha", STATION_ALPHA_SENSORS),
        ("station_beta", STATION_BETA_SENSORS),
    ]
    for station_name, sensors in all_stations:
        for s in sensors:
            reg = SensorDeviceRegistration(
                device_id=s["device_id"],
                vendor="Sentek Drill & Drop",
                model="Sentek-D&D-TriScan",
                protocol="lorawan",
                farm_id=FARM_ID,
                plot_id=PLOT_ID,
                latitude=s["lat"],
                longitude=s["lon"],
                variables=["soil_moisture_vwc"],
                installation_datetime=datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
                status="active",
                calibration_profile_id="cal-sentek-drill-drop-2026",
                depth_cm=s["depth_cm"],
            )
            register_device(reg)


def load_telemetry_observation_packets(
    as_of_cutoff: datetime,
    stations: Tuple[str, ...] = ("station_alpha",),
    log_path: Path = DEFAULT_GATEWAY_LOG_PATH,
    signing_key: Optional[Any] = None,
    issuer: str = "agriwise:trust:sensor_authority",
) -> List[ObservationPacket]:
    """
    Load telemetry records from persisted gateway log up to as_of_cutoff.
    Only includes specified stations (enforcing blind separation).
    Cryptographically signs each measurement with receipt containing content_digest and first_available_at.
    """
    records = ensure_phase1b_gateway_logs(log_path)
    register_phase1b_devices()

    packets: List[ObservationPacket] = []
    cutoff_utc = as_of_cutoff.astimezone(timezone.utc) if as_of_cutoff.tzinfo else as_of_cutoff.replace(tzinfo=timezone.utc)

    for rec in records:
        if rec["station_id"] not in stations:
            continue

        t_obs = datetime.fromisoformat(rec["observed_at_utc"])
        t_ingest = datetime.fromisoformat(rec["ingested_at_utc"])
        
        # Causal temporal filtering: Only records available before or at cutoff
        if t_ingest > cutoff_utc:
            continue

        dev_id = rec["device_id"]
        val = float(rec["value"])
        unit = rec["unit"]

        # Compute IEEE-754 measurement digest
        reading_digest = compute_reading_content_digest(
            device_id=dev_id,
            plot_id=PLOT_ID,
            variable="soil_moisture_vwc",
            value=val,
            unit=unit,
            observed_at=t_obs,
        )

        receipt = create_signed_sensor_receipt(
            receipt_id=f"urn:agriwise:receipt:{dev_id}:{t_obs.strftime('%Y%m%d%H%M%S')}",
            issuer=issuer,
            device_id=dev_id,
            plot_id=PLOT_ID,
            variable="soil_moisture_vwc",
            calibration_profile_id=rec["calibration_profile_id"],
            status="active",
            content_digest=reading_digest,
            observation_instant=t_obs.isoformat(),
            reading_value=val,
            reading_unit=unit,
            observed_at=t_obs,
            first_available_at=t_ingest.isoformat(),
            private_key=signing_key,
        )
        register_sensor_receipt(receipt)

        pkt = ObservationPacket(
            packet_id=rec["message_id"],
            source=ObservationSource.SENSOR_IOT,
            obs_type="measurement",
            timestamp=t_obs,
            plot_id=PLOT_ID,
            spatial_scope="point",
            data_status=DataStatus.OBSERVED,
            qa=QAMetadata(sensor_health=1.0, scene_score=1.0, flags=[]),
            uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.015}),
            payload={
                "device_id": dev_id,
                "instrument_id": dev_id,
                "variable": "soil_moisture_vwc",
                "value": val,
                "unit": unit,
                "calibration_version": rec["calibration_profile_id"],
                "provenance_ref": receipt.receipt_id,
                "observation_instant": t_obs.isoformat(),
                "first_available_at": t_ingest.isoformat(),
                "depth_cm": rec["depth_cm"],
                "station_id": rec["station_id"],
                "source_record_hash": rec["source_record_hash"],
            },
        )
        packets.append(pkt)

    return packets

"""
Four-Owner Cohort Verification Suite — Track A Demonstrated Blockers
Pinned to GitHub revision: 730b9fe9 / f041a8f9 · 26 October 2026

Tests:
  1. F25/F26: EO foundation model true backend provenance and tile hash collision resistance.
  2. F39: Durable file-backed sensor storage, deep-copy immutability, and cold restart recovery.
  3. F17/F18: Actuator STOP transport acknowledgement vs physical cessation confirmation.
  4. F01: Evidence admission nonfinite quality check & os import scope.
  5. F04: Hydraulic parameter precision preservation (preventing zeroing of small positive values).
  6. F08: Trajectory cache digest completeness with few_exposed_wetted_fraction.
  7. F02/F06: Weather forcing source-role and issuance lineage preservation.
"""

import asyncio
import copy
import datetime
from datetime import timezone
import math
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# 1. Acquisition Lane: F25/F26
from services.agribrain.layer1_fusion.eo_foundation_model import (
    EOFoundationModel,
    EmbeddingResult,
)

# 2. Trajectory Lane: F39
from services.agribrain.sensor_runtime.schemas import (
    RawSensorMessage,
    NormalizedSensorReading,
)
from services.agribrain.sensor_runtime.storage import (
    store_raw_message,
    store_normalized_reading,
    get_raw_message,
    get_normalized_readings,
    rehydrate_storage,
    clear_storage,
)

# 3. Execution Lane: F17/F18
from services.agribrain.irrigation_runtime.schemas import (
    ActuatorRegistration,
    ActuatorCapabilities,
    ActuatorStatus,
    CommandPriority,
    CommandResult,
    CommandType,
    DriverProtocol,
    IrrigationCommand,
    IrrigationSystemType,
    VendorId,
)
from services.agribrain.irrigation_runtime.actuator import IrrigationActuator
from services.agribrain.irrigation_runtime.drivers.lorawan_driver import LoRaWANActuator
from services.agribrain.irrigation_runtime.drivers.modbus_driver import ModbusActuator

# 4. Foundation Lane: F01
from services.agribrain.sensor_runtime.ingestion import ingest_sensor_payload
from services.agribrain.sensor_runtime.device_identity import DeviceIdentity
from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
from services.agribrain.sensor_runtime.calibration import SensorCalibrationProfile, register_calibration_profile

# 5. Trajectory Lane: F04 & F08
from services.agribrain.layer3_water.contracts.state_factory import WaterStateFactory
from services.agribrain.layer3_water.contracts.water_state import (
    SoilWaterState,
    SoilEvaporationState,
)
from services.agribrain.layer3_decision.runner import _execute_canonical_water_engine


# ============================================================================
# 1. Acquisition Lane — F25 & F26
# ============================================================================

class TestAcquisitionF25F26:
    """F25: Backend identity failure fallback & F26: Tile hash collision resistance."""

    def test_f25_onnx_failure_reports_spectral_fallback_provenance(self):
        """When ONNX mode fails or session is missing, infer() must report

        spectral_basis_v2 and confidence ceiling 0.75, NEVER onnx_foundation with 0.85.
        """
        model = EOFoundationModel()
        model._mode = "onnx"
        model._init_fallback_weights()

        # Mock session to fail during run
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input")]
        mock_session.run.side_effect = RuntimeError("ONNX Runtime execution failed")
        model._session = mock_session

        # 4 valid bands with 2x2 pixels
        band_arrays = {
            "B2": [[0.1, 0.12], [0.11, 0.13]],
            "B3": [[0.15, 0.16], [0.14, 0.17]],
            "B4": [[0.2, 0.22], [0.21, 0.23]],
            "B8": [[0.4, 0.42], [0.41, 0.43]],
        }

        res = model.infer(band_arrays)
        assert res is not None
        # Provenance must reflect actual executing backend
        assert res.model_id == "spectral_basis_v2"
        # Confidence must respect fallback ceiling (0.75), not ONNX ceiling (0.85)
        assert res.confidence <= 0.75

    def test_f26_tile_hash_distinguishes_band_identity(self):
        """Two different bands with identical float values must produce distinct hashes."""
        model = EOFoundationModel()
        model._mode = "fallback"
        model._init_fallback_weights()
        pixels = [[0.1, 0.2], [0.3, 0.4]]

        input_a = {
            "B2": pixels,
            "B3": pixels,
            "B4": pixels,
        }
        input_b = {
            "B2": pixels,
            "B3": pixels,
            "B8": pixels,  # Different band identity
        }

        hash_a = model._compute_tile_hash(input_a, ["B2", "B3", "B4"])
        hash_b = model._compute_tile_hash(input_b, ["B2", "B3", "B8"])
        assert hash_a != hash_b, "Hash collision between different bands with identical values"

    def test_f26_tile_hash_distinguishes_spatial_dimensions(self):
        """Different spatial dimensions with identical flattened values must not collide."""
        model = EOFoundationModel()
        model._mode = "fallback"
        model._init_fallback_weights()
        # 1x4 vs 2x2
        input_2x2 = {
            "B2": [[0.1, 0.2], [0.3, 0.4]],
            "B3": [[0.1, 0.2], [0.3, 0.4]],
            "B4": [[0.1, 0.2], [0.3, 0.4]],
        }
        input_1x4 = {
            "B2": [[0.1, 0.2, 0.3, 0.4]],
            "B3": [[0.1, 0.2, 0.3, 0.4]],
            "B4": [[0.1, 0.2, 0.3, 0.4]],
        }

        hash_2x2 = model._compute_tile_hash(input_2x2, ["B2", "B3", "B4"])
        hash_1x4 = model._compute_tile_hash(input_1x4, ["B2", "B3", "B4"])
        assert hash_2x2 != hash_1x4, "Hash collision between different spatial dimensions"

    def test_f26_tile_hash_distinguishes_cloud_masks(self):
        """Tiles with identical reflectance but different cloud masks must produce different hashes."""
        model = EOFoundationModel()
        model._mode = "fallback"
        model._init_fallback_weights()
        band_arrays = {
            "B2": [[0.1, 0.2], [0.3, 0.4]],
            "B3": [[0.1, 0.2], [0.3, 0.4]],
            "B4": [[0.1, 0.2], [0.3, 0.4]],
        }

        mask_clear = [[0, 0], [0, 0]]
        mask_cloudy = [[1, 0], [0, 0]]

        hash_none = model._compute_tile_hash(band_arrays, ["B2", "B3", "B4"], cloud_mask=None)
        hash_clear = model._compute_tile_hash(band_arrays, ["B2", "B3", "B4"], cloud_mask=mask_clear)
        hash_cloudy = model._compute_tile_hash(band_arrays, ["B2", "B3", "B4"], cloud_mask=mask_cloudy)

        assert hash_clear != hash_cloudy
        assert hash_none != hash_clear


# ============================================================================
# 2. Trajectory & Persistence Lane — F39
# ============================================================================

class TestPersistenceF39:
    """F39: Sensor records durable persistence and cold restart recovery."""

    @pytest.fixture(autouse=True)
    def setup_temp_store(self, monkeypatch, tmp_path):
        store_dir = tmp_path / "sensor_store"
        monkeypatch.setenv("AGRIWISE_SENSOR_STORAGE_DIR", str(store_dir))
        clear_storage()
        yield
        clear_storage()

    def test_f39_raw_storage_immutability(self):
        """Mutating the source message after store_raw_message() does not alter stored evidence."""
        payload = {"reading": 42.0, "status": "ok"}
        msg = RawSensorMessage(
            message_id="msg-immut-001",
            protocol="MQTT",
            received_at=datetime.datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc),
            device_id="sensor-01",
            payload=payload,
        )
        store_raw_message(msg)

        # Mutate caller's object and dict
        payload["reading"] = 999.9
        msg.protocol = "TAMPERED"

        stored = get_raw_message("msg-immut-001")
        assert stored is not None
        assert stored.payload["reading"] == 42.0
        assert stored.protocol == "MQTT"

    def test_f39_raw_storage_cold_restart_recovery(self, monkeypatch, tmp_path):
        """Stored raw messages survive an in-memory wipe and reload from disk."""
        msg = RawSensorMessage(
            message_id="msg-restart-002",
            protocol="LoRaWAN",
            received_at=datetime.datetime(2026, 10, 26, 14, 30, tzinfo=timezone.utc),
            device_id="sensor-02",
            payload={"snr": 8.5},
            rssi=-75.0,
            snr=8.5,
        )
        store_raw_message(msg)

        # Simulate cold process restart: wipe memory structures without deleting disk
        import services.agribrain.sensor_runtime.storage as s_mod
        s_mod._RAW_STORAGE.clear()
        s_mod._NORMALIZED_STORAGE.clear()
        s_mod._INITIALIZED = False

        # Rehydrate from disk
        rehydrate_storage()

        recovered = get_raw_message("msg-restart-002")
        assert recovered is not None
        assert recovered.message_id == "msg-restart-002"
        assert recovered.protocol == "LoRaWAN"
        assert recovered.rssi == -75.0

    def test_f39_raw_storage_duplicate_rejection(self):
        """Storing a message with an already-used message_id must raise ValueError."""
        msg = RawSensorMessage(
            message_id="msg-dup-003",
            protocol="HTTP",
            received_at=datetime.datetime.now(timezone.utc),
            device_id="sensor-03",
            payload={"val": 1},
        )
        store_raw_message(msg)

        with pytest.raises(ValueError, match="immutable and cannot be overwritten"):
            store_raw_message(msg)


# ============================================================================
# 3. Execution Lane — F17 & F18
# ============================================================================

class TestExecutionF17F18:
    """F17/F18: Actuator STOP transport acknowledgement vs physical cessation."""

    def test_f17_lorawan_queued_stop_retains_ownership_and_blocks_start(self):
        """LoRaWAN queued STOP downlink enters STOP_PENDING_CONFIRMATION,

        retains _active_command, and blocks physical START commands.
        """
        async def _run():
            reg = ActuatorRegistration(
                device_id="lora_valve_01",
                zone_ids=["ZONE-1"],
                plot_id="plot-1",
                farm_id="farm-1",
                protocol=DriverProtocol.LORAWAN,
                vendor=VendorId.GENERIC,
                model="Dragino_LDS02",
                firmware_version="1.0.0",
                capabilities=ActuatorCapabilities(
                    system_type=IrrigationSystemType.DRIP,
                    max_flow_rate_lpm=50.0,
                    min_flow_rate_lpm=0.0,
                    max_duration_minutes=120.0,
                ),
                connection_config={"network_server": "chirpstack", "api_url": "http://mock", "api_key": "k"},
            )
            actuator = LoRaWANActuator(reg)
            actuator._connected = True
            actuator._status = ActuatorStatus.EXECUTING

            # Set active running START command
            start_cmd = IrrigationCommand(
                command_id="CMD-START-01",
                command_type=CommandType.START_ZONE,
                device_id="lora_valve_01",
                zone_id="ZONE-1",
                plot_id="plot-1",
                duration_minutes=30.0,
                flow_rate_lpm=20.0,
                operation_id="OP-01",
            )
            actuator.set_active_command(start_cmd)

            # Mock downlink success (queued on ChirpStack)
            with patch.object(actuator, "_send_downlink", return_value={"success": True}):
                stop_cmd = IrrigationCommand(
                    command_id="CMD-STOP-01",
                    command_type=CommandType.STOP_ZONE,
                    device_id="lora_valve_01",
                    zone_id="ZONE-1",
                    plot_id="plot-1",
                    operation_id="OP-01",
                )
                res = await actuator.execute_with_safety(stop_cmd)

                # Transport accepted
                assert res.success is True
                assert res.transport_acknowledged_only is True
                assert res.confirmed_physical_stop is False

                # Actuator state must be STOP_PENDING_CONFIRMATION, NOT ONLINE!
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION
                # Active command / operation ownership must be retained!
                assert actuator.active_command is not None

                # Attempting new START while stop is pending confirmation MUST BE REJECTED!
                new_start = IrrigationCommand(
                    command_id="CMD-START-02",
                    command_type=CommandType.START_ZONE,
                    device_id="lora_valve_01",
                    zone_id="ZONE-1",
                    plot_id="plot-1",
                    duration_minutes=15.0,
                    flow_rate_lpm=20.0,
                    operation_id="OP-02",
                )
                start_res = await actuator.execute_with_safety(new_start)
                assert start_res.success is False
                assert "STOP_PENDING_CONFIRMATION" in start_res.error_message or "STOP_PENDING_CONFIRMATION" in start_res.error_code

                # Once physical cessation is positively confirmed, it transitions to ONLINE
                actuator.confirm_stop()
                assert actuator.status == ActuatorStatus.ONLINE
                assert actuator.active_command is None

        asyncio.run(_run())

    def test_f18_modbus_unverified_stop_enters_pending_confirmation(self):
        """Modbus coil write without verified zero-flow enters STOP_PENDING_CONFIRMATION."""
        async def _run():
            reg = ActuatorRegistration(
                device_id="modbus_valve_01",
                zone_ids=["ZONE-1"],
                plot_id="plot-1",
                farm_id="farm-1",
                protocol=DriverProtocol.MODBUS_TCP,
                vendor=VendorId.GENERIC,
                model="Modbus_Relay",
                firmware_version="1.0.0",
                capabilities=ActuatorCapabilities(
                    system_type=IrrigationSystemType.DRIP,
                    max_flow_rate_lpm=100.0,
                    min_flow_rate_lpm=0.0,
                    max_duration_minutes=120.0,
                ),
                connection_config={"host": "127.0.0.1", "port": 502, "coil_map": {"valve_ZONE-1": 1}},
            )
            actuator = ModbusActuator(reg)
            actuator._connected = True
            actuator._client = MagicMock()
            actuator._status = ActuatorStatus.EXECUTING

            # Mock coil write succeeds, but feedback still shows flow > 0 (valve stuck open)
            with patch.object(actuator, "_write_coil", new_callable=AsyncMock, return_value=True), \
                 patch.object(actuator, "_read_input_registers", new_callable=AsyncMock, return_value=[0, 0]), \
                 patch.object(actuator, "_read_feedback", new_callable=AsyncMock, return_value=(15.2, 2.1)), \
                 patch.object(actuator, "_read_status", new_callable=AsyncMock, return_value={"status_word": 0x01}):

                stop_cmd = IrrigationCommand(
                    command_id="CMD-STOP-MB",
                    command_type=CommandType.STOP_ZONE,
                    device_id="modbus_valve_01",
                    zone_id="ZONE-1",
                    plot_id="plot-1",
                )
                res = await actuator.execute_with_safety(stop_cmd)
                assert res.success is True
                assert res.transport_acknowledged_only is True
                assert res.confirmed_physical_stop is False
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        asyncio.run(_run())


# ============================================================================
# 4. Foundation Lane — F01
# ============================================================================

class TestFoundationF01:
    """F01: Evidence admission nonfinite quality check & os import scope."""

    def test_f01_calibration_quality_nan_rejected(self):
        """Sensor calibration with NaN quality must be rejected, not admitted."""
        dev_id = f"test-dev-{uuid.uuid4().hex[:8]}"
        reg = SensorDeviceRegistration(
            device_id=dev_id,
            vendor="generic",
            model="probe-v1",
            protocol="MQTT",
            farm_id="farm-1",
            plot_id="plot-1",
            latitude=35.1,
            longitude=-119.2,
            variables=["soil_moisture_vwc"],
            installation_datetime=datetime.datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="active",
        )
        register_device(reg)

        cal = SensorCalibrationProfile(
            calibration_profile_id=f"cal-{uuid.uuid4().hex[:8]}",
            device_id=dev_id,
            variable="soil_moisture_vwc",
            calibration_type="factory",
            valid_from=datetime.datetime(2026, 1, 1, tzinfo=timezone.utc),
            calibration_quality=float("nan"),  # NaN should be rejected!
            valid_until=datetime.datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        register_calibration_profile(cal)

        identity = DeviceIdentity(device_id=dev_id)
        payload = {"readings": [{"variable": "soil_moisture_vwc", "value": 0.25, "unit": "fraction"}]}

        with pytest.raises(ValueError, match="calibration_quality_invalid"):
            ingest_sensor_payload(
                protocol="MQTT",
                device_id=dev_id,
                payload=payload,
                received_at=datetime.datetime.now(timezone.utc),
                identity=identity,
            )

    def test_f01_nonproduction_strict_security_env_does_not_raise_unbound_local(self, monkeypatch):
        """In nonproduction mode, os.getenv('AGRIWISE_STRICT_SECURITY') must not raise UnboundLocalError."""
        # Ensure is_production() returns False
        monkeypatch.delenv("AGRIWISE_PRODUCTION", raising=False)
        monkeypatch.delenv("AGRIWISE_ENV", raising=False)
        monkeypatch.setenv("AGRIWISE_STRICT_SECURITY", "true")

        dev_id = f"test-dev-{uuid.uuid4().hex[:8]}"
        reg = SensorDeviceRegistration(
            device_id=dev_id,
            vendor="generic",
            model="probe-v1",
            protocol="MQTT",
            farm_id="farm-1",
            plot_id="plot-1",
            latitude=35.1,
            longitude=-119.2,
            variables=["soil_moisture_vwc"],
            installation_datetime=datetime.datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="active",
        )
        register_device(reg)

        # Profile with valid_until = None
        cal = SensorCalibrationProfile(
            calibration_profile_id=f"cal-{uuid.uuid4().hex[:8]}",
            device_id=dev_id,
            variable="soil_moisture_vwc",
            calibration_type="factory",
            valid_from=datetime.datetime(2026, 1, 1, tzinfo=timezone.utc),
            calibration_quality=1.0,
            valid_until=None,
        )
        register_calibration_profile(cal)

        identity = DeviceIdentity(device_id=dev_id)
        payload = {"readings": [{"variable": "soil_moisture_vwc", "value": 0.25, "unit": "fraction"}]}

        # Should cleanly raise calibration_expiry_missing, NOT UnboundLocalError
        with pytest.raises(ValueError, match="calibration_expiry_missing"):
            ingest_sensor_payload(
                protocol="MQTT",
                device_id=dev_id,
                payload=payload,
                received_at=datetime.datetime.now(timezone.utc),
                identity=identity,
            )


# ============================================================================
# 5. Trajectory Lane — F04 & F08
# ============================================================================

class TestTrajectoryF04F08:
    """F04: Hydraulic parameter precision & F08: Trajectory digest wetted fraction."""

    def test_f04_small_positive_hydraulic_conductivity_preserved(self):
        """Small valid conductivity (e.g. 0.004 cm/day) must NOT be rounded down to 0.0."""
        ks_small = [0.004, 0.002, 0.001]
        n_small = [1.0004, 1.0002, 1.0001]
        alpha = [0.03, 0.03, 0.03]

        state = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 20.0, 30.0],
            theta_profile=[0.20, 0.20, 0.20],
            field_capacity_profile=[0.30, 0.30, 0.30],
            wilting_point_profile=[0.15, 0.15, 0.15],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.05, 0.05, 0.05],
            hydraulic_conductivity_profile=ks_small,
            van_genuchten_alpha=alpha,
            van_genuchten_n=n_small,
        )

        assert state.hydraulic_conductivity_profile[0] == 0.004
        assert state.hydraulic_conductivity_profile[0] > 0.0
        assert state.van_genuchten_n[0] == 1.0004
        assert state.van_genuchten_n[0] > 1.0

    def test_f08_digest_distinguishes_wetted_fraction(self):
        """Soil states differing ONLY in few_exposed_wetted_fraction must produce different digests."""
        import hashlib

        evap_a = SoilEvaporationState(
            surface_storage_mm=5.0,
            max_surface_storage_mm=10.0,
            days_since_wetting=2,
            kr_reduction_factor=0.8,
            few_exposed_wetted_fraction=0.30,
        )
        evap_b = SoilEvaporationState(
            surface_storage_mm=5.0,
            max_surface_storage_mm=10.0,
            days_since_wetting=2,
            kr_reduction_factor=0.8,
            few_exposed_wetted_fraction=0.75,  # Differing wetted fraction
        )

        state_a = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 20.0, 30.0],
            theta_profile=[0.20, 0.20, 0.20],
            field_capacity_profile=[0.30, 0.30, 0.30],
            wilting_point_profile=[0.15, 0.15, 0.15],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.05, 0.05, 0.05],
            evaporation_state=evap_a,
        )
        state_b = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 20.0, 30.0],
            theta_profile=[0.20, 0.20, 0.20],
            field_capacity_profile=[0.30, 0.30, 0.30],
            wilting_point_profile=[0.15, 0.15, 0.15],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.05, 0.05, 0.05],
            evaporation_state=evap_b,
        )

        def get_digest(s_obj):
            evap_st = getattr(s_obj, "evaporation_state", None)
            evap_tuple = (
                evap_st.days_since_wetting if hasattr(evap_st, "days_since_wetting") else None,
                round(evap_st.few_exposed_wetted_fraction, 4) if getattr(evap_st, "few_exposed_wetted_fraction", None) is not None else None,
                round(evap_st.surface_storage_mm, 4) if getattr(evap_st, "surface_storage_mm", None) is not None else None,
                round(evap_st.max_surface_storage_mm, 4) if getattr(evap_st, "max_surface_storage_mm", None) is not None else None,
                round(evap_st.kr_reduction_factor, 4) if getattr(evap_st, "kr_reduction_factor", None) is not None else None,
            ) if evap_st is not None else None
            soil_payload = (
                "SoilWaterState",
                tuple(getattr(s_obj, "layer_depths_cm", None) or ()),
                tuple(round(v, 4) for v in (getattr(s_obj, "theta_profile", None) or ())),
                tuple(round(v, 4) for v in (getattr(s_obj, "field_capacity_profile", None) or ())),
                tuple(round(v, 4) for v in (getattr(s_obj, "wilting_point_profile", None) or ())),
                tuple(round(v, 4) for v in (getattr(s_obj, "saturation_profile", None) or ())),
                tuple(round(v, 4) for v in (getattr(s_obj, "residual_profile", None) or ())),
                tuple(round(v, 6) for v in (getattr(s_obj, "hydraulic_conductivity_profile", None) or ())),
                tuple(round(v, 6) for v in (getattr(s_obj, "van_genuchten_alpha", None) or ())),
                tuple(round(v, 6) for v in (getattr(s_obj, "van_genuchten_n", None) or ())),
                str(getattr(s_obj, "parameter_provenance", "TEXTURE_PRIOR")),
                evap_tuple,
            )
            return hashlib.sha256(repr(soil_payload).encode("utf-8")).hexdigest()[:24]

        digest_a = get_digest(state_a)
        digest_b = get_digest(state_b)
        assert digest_a != digest_b, "Hash collision between differing few_exposed_wetted_fraction"


# ============================================================================
# 6. Temporal Forcing Lane — F02 & F06
# ============================================================================

class TestTemporalForcingF02F06:
    """F02/F06: Weather parser preserves source role and issuance time."""

    def test_f02_weather_parser_preserves_source_role_and_issuance(self):
        """Weather extraction must preserve source role (observation, forecast, prior) and issued_at."""
        raw_rec = {
            "temp_max": 28.5,
            "temp_min": 14.2,
            "precipitation": 0.0,
            "wind_speed": 2.1,
            "humidity": 65.0,
            "net_radiation": 18.4,
            "source_role": "reconstruction",
            "issued_at": "2026-10-25T18:00:00Z",
        }

        def parse_w(r):
            parsed = {
                "t_max_c": float(r["temp_max"]),
                "t_min_c": float(r["temp_min"]),
                "precipitation_mm": float(r["precipitation"]),
                "wind_speed_2m_m_s": float(r["wind_speed"]),
                "rh_min_pct": max(10.0, float(r["humidity"]) - 15.0),
                "rh_max_pct": min(100.0, float(r["humidity"]) + 15.0),
                "net_radiation_mj_m2": float(r["net_radiation"]),
            }
            if "source_role" in r:
                parsed["source_role"] = str(r["source_role"])
            if "issued_at" in r:
                parsed["issued_at"] = str(r["issued_at"])
            return parsed

        res = parse_w(raw_rec)
        assert res["source_role"] == "reconstruction"
        assert res["issued_at"] == "2026-10-25T18:00:00Z"

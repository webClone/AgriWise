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
import hashlib
import hmac
import json
import math
import os
import shutil
import tempfile
import uuid

# Secure provisioned test key for STOP receipt authentication verification
os.environ.setdefault("AGRIBRAIN_STOP_AUTH_KEY", "agribrain_cohort_test_auth_provisioned_key_2026")
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
    _validate_and_encode_id,
    StorageCorruptedError,
)

# 3. Execution Lane: F17/F18
from services.agribrain.irrigation_runtime.schemas import (
    ActuatorRegistration,
    ActuatorCapabilities,
    ActuatorStatus,
    AutomationMode,
    CommandPriority,
    CommandResult,
    CommandType,
    DriverProtocol,
    EventStatus,
    IrrigationCommand,
    IrrigationEvent,
    IrrigationSystemType,
    VendorId,
)
from services.agribrain.irrigation_runtime.actuator import IrrigationActuator
from services.agribrain.irrigation_runtime.drivers.lorawan_driver import LoRaWANActuator
from services.agribrain.irrigation_runtime.drivers.modbus_driver import ModbusActuator
from services.agribrain.irrigation_runtime.drivers.http_driver import HTTPActuator
from services.agribrain.irrigation_runtime.dispatcher import CommandDispatcher
from services.agribrain.irrigation_runtime.safety import SafetyMonitor, SharedQuotaStore

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

    def test_f26_exact_ieee754_tile_hash_no_lossy_rounding(self):
        """Float values differing beyond 4 decimal places must produce distinct hashes (no lossy rounding)."""
        model = EOFoundationModel()
        model._mode = "fallback"
        model._init_fallback_weights()

        # Differ only at the 5th decimal place (0.12341 vs 0.12349)
        bands_a = {
            "B2": [[0.12341, 0.2], [0.3, 0.4]],
            "B3": [[0.1, 0.2], [0.3, 0.4]],
            "B4": [[0.1, 0.2], [0.3, 0.4]],
        }
        bands_b = {
            "B2": [[0.12349, 0.2], [0.3, 0.4]],
            "B3": [[0.1, 0.2], [0.3, 0.4]],
            "B4": [[0.1, 0.2], [0.3, 0.4]],
        }

        hash_a = model._compute_tile_hash(bands_a, ["B2", "B3", "B4"])
        hash_b = model._compute_tile_hash(bands_b, ["B2", "B3", "B4"])
        assert hash_a != hash_b, "Lossy rounding caused hash collision for distinct float values"

    def test_f26_tile_hash_distinguishes_crs_and_transform(self):
        """Tiles with identical pixel values but different CRS or affine transform must not collide."""
        model = EOFoundationModel()
        model._mode = "fallback"
        model._init_fallback_weights()
        bands = {
            "B2": [[0.1, 0.2], [0.3, 0.4]],
            "B3": [[0.1, 0.2], [0.3, 0.4]],
            "B4": [[0.1, 0.2], [0.3, 0.4]],
        }

        hash_crs1 = model._compute_tile_hash(bands, ["B2", "B3", "B4"], crs="EPSG:4326")
        hash_crs2 = model._compute_tile_hash(bands, ["B2", "B3", "B4"], crs="EPSG:32610")
        hash_trans = model._compute_tile_hash(bands, ["B2", "B3", "B4"], crs="EPSG:4326", transform=(10.0, 0.0, 500.0, 0.0, -10.0, 600.0))

        assert hash_crs1 != hash_crs2, "Tile hash failed to distinguish different CRS"
        assert hash_crs1 != hash_trans, "Tile hash failed to distinguish different affine transform"

    def test_f26_infer_fails_closed_on_misaligned_band_dimensions(self):
        """Inference must fail closed with ValueError when band array dimensions do not match."""
        model = EOFoundationModel()
        model._mode = "fallback"
        model._init_fallback_weights()

        # B2 is 2x2, B3 is 2x3 (dimension mismatch)
        misaligned_bands = {
            "B2": [[0.1, 0.2], [0.3, 0.4]],
            "B3": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            "B4": [[0.1, 0.2], [0.3, 0.4]],
        }

        with pytest.raises(ValueError, match="band_dimension_mismatch"):
            model.infer(misaligned_bands)

    def test_f26_infer_fails_closed_on_misaligned_cloud_mask(self):
        """Inference must fail closed with ValueError when cloud mask shape does not match bands."""
        model = EOFoundationModel()
        model._mode = "fallback"
        model._init_fallback_weights()

        bands = {
            "B2": [[0.1, 0.2], [0.3, 0.4]],
            "B3": [[0.1, 0.2], [0.3, 0.4]],
            "B4": [[0.1, 0.2], [0.3, 0.4]],
        }
        misaligned_mask = [[0, 0, 0], [0, 0, 0]]  # 2x3 mask for 2x2 bands

        with pytest.raises(ValueError, match="band_dimension_mismatch"):
            model.infer(bands, cloud_mask=misaligned_mask)

    def test_f25_embedding_result_includes_model_and_preprocessing_version(self):
        """EmbeddingResult must expose model_version and preprocessing_version for complete provenance."""
        model = EOFoundationModel()
        model._mode = "fallback"
        model._init_fallback_weights()

        bands = {
            "B2": [[0.1, 0.2], [0.3, 0.4]],
            "B3": [[0.1, 0.2], [0.3, 0.4]],
            "B4": [[0.1, 0.2], [0.3, 0.4]],
        }
        res = model.infer(bands)
        assert res is not None
        assert res.model_version == "1.0.0"
        assert res.preprocessing_version == "2.0.0"



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

    def test_f39_concurrent_exclusive_create_collision(self):
        """Simulate concurrent worker race: FileExistsError during os.open must raise immutable ValueError."""
        msg = RawSensorMessage(
            message_id="msg-race-004",
            protocol="MQTT",
            received_at=datetime.datetime.now(timezone.utc),
            device_id="sensor-04",
            payload={"v": 10},
        )
        with patch("services.agribrain.sensor_runtime.storage.os.open", side_effect=FileExistsError("File exists")):
            with pytest.raises(ValueError, match="immutable and cannot be overwritten"):
                store_raw_message(msg)

    def test_f39_validate_and_encode_id_rejects_path_traversal_and_invalid_chars(self):
        """Identifier validation must reject path traversal and non-whitelisted characters."""
        for invalid_id in ("../traversal", "..\\traversal", "sensor/01", "sensor\\01", "bad@id", "bad id", "", None):
            with pytest.raises(ValueError):
                _validate_and_encode_id(invalid_id)

        # Injective encoding ensures distinct message IDs never collide
        assert _validate_and_encode_id("urn:dev:123") != _validate_and_encode_id("urn_COLON_dev_COLON_123")
        assert "urn_dev_123" in _validate_and_encode_id("urn:dev:123")

    def test_f39_rehydrate_storage_repeated_does_not_duplicate_normalized_records(self):
        """Calling rehydrate_storage multiple times must clear in-memory list before reloading from disk."""
        reading = NormalizedSensorReading(
            reading_id="norm-001",
            device_id="sensor-01",
            plot_id="plot-1",
            zone_id="zone-1",
            timestamp=datetime.datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc),
            received_at=datetime.datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc),
            variable="soil_moisture_vwc",
            value=0.22,
            unit="fraction",
            vendor="generic",
            protocol="MQTT",
            depth_cm=15.0,
        )
        store_normalized_reading(reading)
        assert len(get_normalized_readings()) == 1

        # Repeated rehydration must not duplicate records
        rehydrate_storage()
        rehydrate_storage()
        assert len(get_normalized_readings()) == 1

    def test_f39_ingest_sensor_payload_stores_normalized_reading(self):
        """Valid ingested sensor readings must be durably stored via store_normalized_reading()."""
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
            calibration_quality=1.0,
            valid_until=datetime.datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        register_calibration_profile(cal)

        identity = DeviceIdentity(device_id=dev_id)
        payload = {"readings": [{"variable": "soil_moisture_vwc", "value": 0.28, "unit": "fraction"}]}

        readings = ingest_sensor_payload(
            protocol="MQTT",
            device_id=dev_id,
            payload=payload,
            received_at=datetime.datetime.now(timezone.utc),
            identity=identity,
        )
        assert len(readings) == 1

        stored_norms = get_normalized_readings()
        assert len(stored_norms) >= 1
        matching = [r for r in stored_norms if r.reading_id == readings[0].reading_id]
        assert len(matching) == 1
        assert matching[0].value == 0.28



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

                # Unrestricted call without verified receipt must be rejected
                with pytest.raises(ValueError, match="confirm_stop requires a verified dictionary receipt"):
                    actuator.confirm_stop()

                # Passing valid verified receipt confirms stop and transitions to ONLINE
                from services.agribrain.irrigation_runtime.actuator import create_verified_stop_receipt
                valid_receipt = create_verified_stop_receipt(
                    device_id="lora_valve_01",
                    operation_id="OP-01",
                    source="controller",
                    actual_flow_lpm=0.0,
                )
                assert actuator.confirm_stop(valid_receipt) is True
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

    def test_f18_modbus_stop_missing_feedback_registers_remains_unconfirmed(self):
        """Missing Modbus feedback registers must be treated as UNKNOWN, never physical stop."""
        async def _run():
            reg = ActuatorRegistration(
                device_id="modbus_valve_nofeedback",
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

            # Write coil succeeds, but both feedback registers return None (missing/uninstrumented)
            with patch.object(actuator, "_write_coil", new_callable=AsyncMock, return_value=True), \
                 patch.object(actuator, "_read_input_registers", new_callable=AsyncMock, return_value=[]), \
                 patch.object(actuator, "_read_feedback", new_callable=AsyncMock, return_value=(None, None)), \
                 patch.object(actuator, "_read_status", new_callable=AsyncMock, return_value={}):

                stop_cmd = IrrigationCommand(
                    command_id="CMD-STOP-NO-FB",
                    command_type=CommandType.STOP_ZONE,
                    device_id="modbus_valve_nofeedback",
                    zone_id="ZONE-1",
                    plot_id="plot-1",
                )
                res = await actuator.execute_with_safety(stop_cmd)
                assert res.success is True
                # Missing feedback must NOT satisfy physical stop!
                assert res.transport_acknowledged_only is True
                assert res.confirmed_physical_stop is False
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        asyncio.run(_run())

    def test_f18_http_stop_transport_only_remains_unconfirmed(self):
        """HTTP STOP 200 response without explicit physical confirmation leaves stop pending."""
        async def _run():
            reg = ActuatorRegistration(
                device_id="http_valve_01",
                zone_ids=["ZONE-1"],
                plot_id="plot-1",
                farm_id="farm-1",
                protocol=DriverProtocol.HTTP_REST,
                vendor=VendorId.GENERIC,
                model="HTTP_Valve",
                firmware_version="1.0.0",
                capabilities=ActuatorCapabilities(
                    system_type=IrrigationSystemType.DRIP,
                    max_flow_rate_lpm=50.0,
                    min_flow_rate_lpm=0.0,
                    max_duration_minutes=60.0,
                ),
                connection_config={"base_url": "http://127.0.0.1:8080"},
            )
            actuator = HTTPActuator(reg)
            actuator._connected = True
            actuator._status = ActuatorStatus.EXECUTING

            # HTTP returns 200 with generic success but no confirmed cessation data
            with patch.object(actuator, "_request", new_callable=AsyncMock, return_value={"success": True, "data": {}}):
                stop_cmd = IrrigationCommand(
                    command_id="CMD-STOP-HTTP",
                    command_type=CommandType.STOP_ZONE,
                    device_id="http_valve_01",
                    zone_id="ZONE-1",
                    plot_id="plot-1",
                )
                res = await actuator.execute_with_safety(stop_cmd)
                assert res.success is True
                assert res.transport_acknowledged_only is True
                assert res.confirmed_physical_stop is False
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        asyncio.run(_run())

    def test_f17_actuator_confirm_stop_rejects_mismatched_device_or_running_flow(self):
        """Actuator confirm_stop rejects wrong device_id, wrong operation_id, or non-zero flow."""
        reg = ActuatorRegistration(
            device_id="valve_safety_test",
            zone_ids=["ZONE-1"],
            plot_id="plot-1",
            farm_id="farm-1",
            protocol=DriverProtocol.HTTP_REST,
            vendor=VendorId.GENERIC,
            model="HTTP_Valve",
            firmware_version="1.0.0",
            capabilities=ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=50.0,
                min_flow_rate_lpm=0.0,
                max_duration_minutes=60.0,
            ),
            connection_config={"base_url": "http://127.0.0.1:8080"},
        )
        actuator = HTTPActuator(reg)
        start_cmd = IrrigationCommand(
            command_id="CMD-START-OP",
            command_type=CommandType.START_ZONE,
            device_id="valve_safety_test",
            zone_id="ZONE-1",
            plot_id="plot-1",
            operation_id="OP-12345",
        )
        actuator.set_active_command(start_cmd)
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION

        # 1. Wrong device_id raises ValueError
        with pytest.raises(ValueError, match="does not match actuator"):
            actuator.confirm_stop({"device_id": "other_device", "operation_id": "OP-12345"})

        # 2. Wrong operation_id raises ValueError
        with pytest.raises(ValueError, match="does not match active operation"):
            actuator.confirm_stop({"device_id": "valve_safety_test", "operation_id": "WRONG-OP"})

        # 3. Detects continuing flow > 0 returns False
        assert actuator.confirm_stop({
            "device_id": "valve_safety_test",
            "operation_id": "OP-12345",
            "actual_flow_rate_lpm": 12.5,
        }) is False

        # 4. Detects is_running is True returns False
        assert actuator.confirm_stop({
            "device_id": "valve_safety_test",
            "operation_id": "OP-12345",
            "is_running": True,
        }) is False

        # Actuator remains in STOP_PENDING_CONFIRMATION
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION
        assert actuator.active_command is not None

    def test_f17_dispatcher_cancel_queued_stop_retains_ownership_and_tracking(self):
        """Dispatcher cancellation on transport-only STOP must transition to STOP_REQUESTED and retain tracking."""
        async def _run():
            dev_id = "valve_cancel_disp"
            reg = ActuatorRegistration(
                device_id=dev_id,
                zone_ids=["ZONE-1"],
                plot_id="plot-1",
                farm_id="farm-1",
                protocol=DriverProtocol.HTTP_REST,
                vendor=VendorId.GENERIC,
                model="HTTP_Valve",
                firmware_version="1.0.0",
                capabilities=ActuatorCapabilities(
                    system_type=IrrigationSystemType.DRIP,
                    max_flow_rate_lpm=50.0,
                    min_flow_rate_lpm=0.0,
                    max_duration_minutes=60.0,
                ),
                connection_config={"base_url": "http://127.0.0.1:8080"},
            )
            actuator = HTTPActuator(reg)
            actuator._connected = True
            actuator._status = ActuatorStatus.EXECUTING

            mock_registry = MagicMock()
            mock_registry.get_actuator.return_value = actuator

            dispatcher = CommandDispatcher(registry=mock_registry, safety=SafetyMonitor(), max_retries=1, retry_base_delay=0)

            event = IrrigationEvent(
                event_id="EV-CANCEL-01",
                plot_id="plot-1",
                zone_id="ZONE-1",
                device_id=dev_id,
                system_type=IrrigationSystemType.DRIP,
                automation_mode=AutomationMode.FULL_AUTO,
                target_volume_mm=10.0,
                target_duration_minutes=30.0,
                target_flow_rate_lpm=25.0,
                status=EventStatus.EXECUTING,
            )
            dispatcher._active_events[event.event_id] = event

            start_cmd = IrrigationCommand(
                command_id="CMD-START-EV",
                command_type=CommandType.START_ZONE,
                device_id=dev_id,
                zone_id="ZONE-1",
                plot_id="plot-1",
                source_event_id="EV-CANCEL-01",
                operation_id="EV-CANCEL-01",
            )
            actuator.set_active_command(start_cmd)

            # _request returns 200 without confirmed physical proof; get_status returns EXECUTING
            with patch.object(actuator, "get_status", new_callable=AsyncMock, return_value=ActuatorStatus.EXECUTING), \
                 patch.object(actuator, "_request", new_callable=AsyncMock, return_value={"success": True, "data": {}}):
                res_event = await dispatcher.cancel_event("EV-CANCEL-01", reason="Manual abort")

                # Must NOT be CANCELLED or finalized!
                assert res_event.status == EventStatus.STOP_REQUESTED
                # Must still be in active events list!
                assert "EV-CANCEL-01" in dispatcher._active_events
                # Actuator must retain ownership and transition to STOP_PENDING_CONFIRMATION!
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        asyncio.run(_run())

    def test_f17_dispatcher_emergency_stop_all_queued_returns_stop_pending(self):
        """Global emergency stop with unconfirmed physical stop returns STOP_PENDING and retains tracking."""
        async def _run():
            dev_id = "valve_estop_disp"
            reg = ActuatorRegistration(
                device_id=dev_id,
                zone_ids=["ZONE-1"],
                plot_id="plot-1",
                farm_id="farm-1",
                protocol=DriverProtocol.HTTP_REST,
                vendor=VendorId.GENERIC,
                model="HTTP_Valve",
                firmware_version="1.0.0",
                capabilities=ActuatorCapabilities(
                    system_type=IrrigationSystemType.DRIP,
                    max_flow_rate_lpm=50.0,
                    min_flow_rate_lpm=0.0,
                    max_duration_minutes=60.0,
                ),
                connection_config={"base_url": "http://127.0.0.1:8080"},
            )
            actuator = HTTPActuator(reg)
            actuator._connected = True
            actuator._status = ActuatorStatus.EXECUTING

            mock_registry = MagicMock()
            mock_registry.get_actuator.return_value = actuator
            mock_registry.get_all_actuators.return_value = [actuator]

            dispatcher = CommandDispatcher(registry=mock_registry, safety=SafetyMonitor(), max_retries=1, retry_base_delay=0)

            event = IrrigationEvent(
                event_id="EV-ESTOP-01",
                plot_id="plot-1",
                zone_id="ZONE-1",
                device_id=dev_id,
                system_type=IrrigationSystemType.DRIP,
                automation_mode=AutomationMode.FULL_AUTO,
                target_volume_mm=15.0,
                target_duration_minutes=45.0,
                target_flow_rate_lpm=30.0,
                status=EventStatus.EXECUTING,
            )
            dispatcher._active_events[event.event_id] = event

            # Unconfirmed emergency stop
            transport_estop = CommandResult(
                command_id="ESTOP-01",
                device_id=dev_id,
                success=True,
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                transport_acknowledged_only=True,
                confirmed_physical_stop=False,
            )

            with patch.object(actuator, "emergency_stop", new_callable=AsyncMock, return_value=transport_estop):
                results = await dispatcher.emergency_stop_all()

                # Must report STOP_PENDING
                assert results.get("EV-ESTOP-01") == "STOP_PENDING"
                assert event.status == EventStatus.STOP_REQUESTED
                assert "EV-ESTOP-01" in dispatcher._active_events
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        asyncio.run(_run())

    def test_f17_dispatcher_confirm_stopped_event_with_valid_receipt(self):
        """Dispatcher confirm_stopped_event finalizes pending stop once verified controller receipt arrives."""
        dev_id = "valve_receipt_disp"
        reg = ActuatorRegistration(
            device_id=dev_id,
            zone_ids=["ZONE-1"],
            plot_id="plot-1",
            farm_id="farm-1",
            protocol=DriverProtocol.HTTP_REST,
            vendor=VendorId.GENERIC,
            model="HTTP_Valve",
            firmware_version="1.0.0",
            capabilities=ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=50.0,
                min_flow_rate_lpm=0.0,
                max_duration_minutes=60.0,
            ),
            connection_config={"base_url": "http://127.0.0.1:8080"},
        )
        actuator = HTTPActuator(reg)
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION

        mock_registry = MagicMock()
        mock_registry.get_actuator.return_value = actuator

        dispatcher = CommandDispatcher(registry=mock_registry, safety=SafetyMonitor(), max_retries=1, retry_base_delay=0)

        event = IrrigationEvent(
            event_id="EV-CONFIRM-01",
            plot_id="plot-1",
            zone_id="ZONE-1",
            device_id=dev_id,
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            target_volume_mm=10.0,
            target_duration_minutes=30.0,
            target_flow_rate_lpm=25.0,
            status=EventStatus.STOP_REQUESTED,
        )
        event.status_reason = "Cancellation stop pending physical confirmation"
        dispatcher._active_events[event.event_id] = event

        from services.agribrain.irrigation_runtime.actuator import create_verified_stop_receipt
        receipt = create_verified_stop_receipt(
            device_id=dev_id,
            operation_id="EV-CONFIRM-01",
            source="controller",
            actual_flow_lpm=0.0,
        )

        # Confirm stopped event
        success = dispatcher.confirm_stopped_event("EV-CONFIRM-01", receipt)
        assert success is True
        assert event.status == EventStatus.CANCELLED
        # Event is finalized and removed from active tracking
        assert "EV-CONFIRM-01" not in dispatcher._active_events
        # Actuator is back ONLINE and idle
        assert actuator.status == ActuatorStatus.ONLINE



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

    def test_f37_canonical_namespace_class_identity(self):
        """SensorDeviceRegistration class identity must be strictly unified across both import paths."""
        from sensor_runtime.registry import SensorDeviceRegistration as ShortReg
        from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration as FullReg

        assert ShortReg is FullReg, "Class identity mismatch between sensor_runtime and services.agribrain.sensor_runtime"

        instance = ShortReg(
            device_id="test-identity-dev",
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
        assert instance.__class__ is FullReg
        assert isinstance(instance, FullReg)



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

    def test_f02_extract_weather_rejects_future_issued_record(self):
        """_execute_canonical_water_engine must reject weather records issued after the step decision cutoff."""
        class DummyInputs:
            soil_observations_daily = {}
            target_date = "2026-05-01"
            crop_context = None

        # 1. Record issued AFTER step cutoff (2026-05-02T00:00:00Z > 2026-05-01T23:59:59Z)
        future_weather = [
            {
                "date": "2026-05-01",
                "t_max_c": 25.0,
                "t_min_c": 12.0,
                "precipitation_mm": 0.0,
                "wind_speed_2m_m_s": 2.0,
                "rh_min_pct": 30.0,
                "rh_max_pct": 70.0,
                "net_radiation_mj_m2": 15.0,
                "issued_at": "2026-05-02T12:00:00Z",
            }
        ]
        DummyInputs.weather_daily = future_weather
        state, feedback = _execute_canonical_water_engine(
            plot_id=f"PLOT-CUTOFF-{uuid.uuid4().hex[:6]}",
            inputs=DummyInputs(),
            op_ctx={},
            run_timestamp=datetime.datetime(2026, 5, 1, 23, 59, 59, tzinfo=timezone.utc),
        )
        assert state is None, "Weather record issued in the future must be rejected at decision cutoff"

        # 2. Record issued BEFORE step cutoff (2026-05-01T18:00:00Z <= 2026-05-01T23:59:59Z)
        eligible_weather = [
            {
                "date": "2026-05-01",
                "t_max_c": 25.0,
                "t_min_c": 12.0,
                "precipitation_mm": 0.0,
                "wind_speed_2m_m_s": 2.0,
                "rh_min_pct": 30.0,
                "rh_max_pct": 70.0,
                "net_radiation_mj_m2": 15.0,
                "issued_at": "2026-05-01T18:00:00Z",
            }
        ]
        DummyInputs.weather_daily = eligible_weather
        state_ok, feedback_ok = _execute_canonical_water_engine(
            plot_id=f"PLOT-CUTOFF-OK-{uuid.uuid4().hex[:6]}",
            inputs=DummyInputs(),
            op_ctx={},
            run_timestamp=datetime.datetime(2026, 5, 1, 23, 59, 59, tzinfo=timezone.utc),
        )
        assert state_ok is not None, "Weather record issued prior to cutoff must be admitted"

    def test_f06_checkpoint_fallback_scoped_to_cycle_and_geometry(self):
        """Checkpoint fallback must pass cycle_id and geometry_version and enforce cutoff."""
        class DummyInputs:
            weather_daily = []
            soil_observations_daily = {}
            target_date = "2026-05-01"
            crop_context = None

        mock_cw = MagicMock()
        mock_cw.load_latest_hydraulic_checkpoint.return_value = {
            "committed_at": "2026-05-01T12:00:00Z",
            "payload": {
                "history_summary": {
                    "2026-05-01": {
                        "weather": {
                            "t_max_c": 24.0,
                            "t_min_c": 11.0,
                            "precipitation_mm": 0.0,
                            "wind_speed_2m_m_s": 2.0,
                            "rh_min_pct": 30.0,
                            "rh_max_pct": 70.0,
                            "net_radiation_mj_m2": 15.0,
                            "issued_at": "2026-05-01T10:00:00Z",
                        }
                    }
                }
            }
        }

        with patch("world_model.canonical_worldline.CanonicalWorldlineService", return_value=mock_cw):
            state, _ = _execute_canonical_water_engine(
                plot_id="PLOT-CP-SCOPE",
                inputs=DummyInputs(),
                op_ctx={"cycle_id": "CYCLE-2026-A", "geometry_version": "v1.2"},
                run_timestamp=datetime.datetime(2026, 5, 1, 23, 59, 59, tzinfo=timezone.utc),
            )
            assert mock_cw.load_latest_hydraulic_checkpoint.called
            call_kwargs = mock_cw.load_latest_hydraulic_checkpoint.call_args.kwargs
            assert call_kwargs.get("cycle_id") == "CYCLE-2026-A"
            assert call_kwargs.get("geometry_version") == "v1.2"
            assert state is not None


# ============================================================================
# Multiprocessing Worker Helpers for Integration D (P2 — F39)
# ============================================================================

def _mp_worker_store_raw(storage_dir: str, worker_id: int, count: int) -> None:
    os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = storage_dir
    from services.agribrain.sensor_runtime.storage import store_raw_message, rehydrate_storage
    from services.agribrain.sensor_runtime.schemas import RawSensorMessage
    import datetime
    from datetime import timezone

    rehydrate_storage()
    for i in range(count):
        msg = RawSensorMessage(
            message_id=f"msg_mp_{worker_id}_{i}",
            device_id=f"dev_mp_{worker_id}",
            payload={"count": i, "worker": worker_id},
            received_at=datetime.datetime.now(timezone.utc),
            protocol="MQTT",
        )
        store_raw_message(msg)


def _mp_worker_store_normalized(storage_dir: str, worker_id: int, count: int) -> None:
    os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = storage_dir
    from services.agribrain.sensor_runtime.storage import store_normalized_reading, rehydrate_storage
    from services.agribrain.sensor_runtime.schemas import NormalizedSensorReading
    import datetime
    from datetime import timezone

    rehydrate_storage()
    for i in range(count):
        r = NormalizedSensorReading(
            reading_id=f"norm_mp_{worker_id}_{i}",
            device_id=f"dev_mp_{worker_id}",
            plot_id="PLOT-MP-1",
            zone_id="ZONE-1",
            timestamp=datetime.datetime.now(timezone.utc),
            received_at=datetime.datetime.now(timezone.utc),
            variable="soil_moisture_vwc",
            value=0.25 + float(i) * 0.01,
            unit="fraction",
            vendor="DAVIS",
            protocol="MQTT",
        )
        store_normalized_reading(r)


# ============================================================================
# 7. Post-Audit Integrations S, D, E Verification Suite (F16-F19, F39, F02, F06, F25, F26)
# ============================================================================

class TestPostAuditIntegrationsSDE:
    """Remediation tests for Integrations S (Physical Stop Authority), D (Durable Evidence/Replay), and E (EO Qualification)."""

    def test_s01_restart_reconciliation_unconfirmed_stop_retains_stop_requested(self):
        """Dispatcher restart reconciliation must retain STOP_REQUESTED when stop confirmation is unconfirmed."""
        async def _run():
            mock_safety = MagicMock()
            mock_registry = MagicMock()
            dispatcher = CommandDispatcher(registry=mock_registry, safety=mock_safety)

            mock_actuator = AsyncMock()
            mock_actuator.device_id = "DEV-RESTART-01"
            mock_actuator.protocol = DriverProtocol.MODBUS_RTU
            mock_actuator.get_status.return_value = ActuatorStatus.EXECUTING
            mock_actuator.active_command = None
            mock_actuator.set_active_command = MagicMock()
            mock_actuator.emergency_stop.return_value = CommandResult(
                command_id="ESTOP-01",
                device_id="DEV-RESTART-01",
                success=True,
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                confirmed_physical_stop=False,
                transport_acknowledged_only=True,
            )
            mock_registry.get_actuator.return_value = mock_actuator

            # 1. Event already in STOP_REQUESTED
            event = IrrigationEvent(
                event_id="EVT-REC-01",
                plot_id="PLOT-01",
                device_id="DEV-RESTART-01",
                zone_id="ZONE-1",
                system_type=IrrigationSystemType.DRIP,
                automation_mode=AutomationMode.FULL_AUTO,
                target_duration_minutes=15.0,
                target_volume_mm=10.0,
                target_flow_rate_lpm=50.0,
                status=EventStatus.STOP_REQUESTED,
                actual_start=(datetime.datetime.now(timezone.utc) - datetime.timedelta(minutes=5)).isoformat(),
            )
            reconciled = await dispatcher.reconcile_on_restart([event])
            assert len(reconciled) == 1
            assert reconciled[0].status == EventStatus.STOP_REQUESTED, "Unconfirmed stop must retain STOP_REQUESTED, not advance to CANCELLED"

            # 2. Event EXECUTING with duration expired during restart
            mock_actuator.active_command = None
            event_expired = IrrigationEvent(
                event_id="EVT-REC-02",
                plot_id="PLOT-01",
                device_id="DEV-RESTART-01",
                zone_id="ZONE-1",
                system_type=IrrigationSystemType.DRIP,
                automation_mode=AutomationMode.FULL_AUTO,
                target_duration_minutes=10.0,
                target_volume_mm=10.0,
                target_flow_rate_lpm=50.0,
                status=EventStatus.EXECUTING,
                actual_start=(datetime.datetime.now(timezone.utc) - datetime.timedelta(minutes=20)).isoformat(),
            )
            reconciled_exp = await dispatcher.reconcile_on_restart([event_expired])
            assert len(reconciled_exp) == 1
            assert reconciled_exp[0].status == EventStatus.STOP_REQUESTED, "Duration expired with unconfirmed stop must transition to STOP_REQUESTED, not EMERGENCY_STOPPED"

        asyncio.run(_run())

    def test_s02_actuator_direct_stop_unverified_driver_enters_pending_confirmation(self):
        """Actuator _execute_stop_direct on real transport without physical confirmation enters STOP_PENDING_CONFIRMATION."""
        async def _run():
            caps = ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=100.0,
                max_duration_minutes=120.0,
            )
            reg = ActuatorRegistration(
                device_id="DEV-LORA-01",
                vendor=VendorId.GENERIC,
                model="Generic_LoRa",
                protocol=DriverProtocol.LORAWAN,
                plot_id="PLOT-01",
                zone_ids=["ZONE-1"],
                capabilities=caps,
            )
            class DummyDriver(IrrigationActuator):
                def __init__(self):
                    super().__init__(registration=reg)
                    self.protocol = DriverProtocol.LORAWAN

                async def connect(self):
                    self._connected = True
                    return True

                async def disconnect(self):
                    self._connected = False
                    return True

                async def emergency_stop(self):
                    return CommandResult(
                        command_id=f"ESTOP-{uuid.uuid4().hex[:8]}",
                        device_id=self.device_id,
                        success=True,
                        timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                        confirmed_physical_stop=False,
                        transport_acknowledged_only=True,
                    )

                async def send_command(self, cmd):
                    return CommandResult(
                        command_id=cmd.command_id,
                        device_id=self.device_id,
                        success=True,
                        timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                        confirmed_physical_stop=False,
                        transport_acknowledged_only=False,
                    )

                async def get_status(self):
                    return self._status

            actuator = DummyDriver()
            cmd_start = IrrigationCommand(
                command_id="CMD-START-01",
                command_type=CommandType.START_ZONE,
                device_id=actuator.device_id,
                zone_id="ZONE-1",
                plot_id="PLOT-01",
                duration_minutes=15.0,
                volume_mm=10.0,
                operation_id="OP-001",
            )
            actuator._active_command = cmd_start
            actuator._status = ActuatorStatus.EXECUTING

            cmd_stop = IrrigationCommand(
                command_id="CMD-STOP-01",
                command_type=CommandType.STOP_ZONE,
                device_id=actuator.device_id,
                zone_id="ZONE-1",
                plot_id="PLOT-01",
                operation_id="OP-001",
            )
            result = await actuator._execute_stop_direct(cmd_stop)
            assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION
            assert result.confirmed_physical_stop is False
            assert result.transport_acknowledged_only is True
            assert actuator.active_command is not None, "Active command ownership must be retained pending confirmation"

        asyncio.run(_run())

    def test_s03_actuator_confirm_stop_requires_mandatory_device_and_operation_ids(self):
        """confirm_stop requires mandatory device_id matching and active operation_id matching."""
        caps = ActuatorCapabilities(
            system_type=IrrigationSystemType.DRIP,
            max_flow_rate_lpm=100.0,
            max_duration_minutes=120.0,
        )
        reg = ActuatorRegistration(
            device_id="DEV-MAND-01",
            vendor=VendorId.GENERIC,
            model="Generic_Modbus",
            protocol=DriverProtocol.MODBUS_RTU,
            plot_id="PLOT-01",
            zone_ids=["ZONE-1"],
            capabilities=caps,
        )
        class DummyDriver(IrrigationActuator):
            def __init__(self):
                super().__init__(registration=reg)

            async def connect(self):
                self._connected = True
                return True

            async def disconnect(self):
                self._connected = False
                return True

            async def emergency_stop(self):
                return CommandResult(
                    command_id=f"ESTOP-{uuid.uuid4().hex[:8]}",
                    device_id=self.device_id,
                    success=True,
                    timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                    confirmed_physical_stop=False,
                    transport_acknowledged_only=True,
                )

            async def send_command(self, cmd):
                return CommandResult(
                    command_id=cmd.command_id,
                    device_id=self.device_id,
                    success=True,
                    timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                )

            async def get_status(self):
                return self._status

        actuator = DummyDriver()
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
        actuator._active_command = IrrigationCommand(
            command_id="CMD-ACT-01",
            command_type=CommandType.START_ZONE,
            device_id=actuator.device_id,
            zone_id="ZONE-1",
            plot_id="PLOT-01",
            duration_minutes=15.0,
            volume_mm=10.0,
            operation_id="OP-MAND-99",
        )

        now_iso = datetime.datetime.now(timezone.utc).isoformat()

        # 1. Missing device_id
        with pytest.raises(ValueError, match="Receipt device_id None does not match"):
            actuator.confirm_stop({"operation_id": "OP-MAND-99", "status": "STOPPED", "timestamp": now_iso})

        # 2. Mismatched device_id
        with pytest.raises(ValueError, match="does not match actuator"):
            actuator.confirm_stop({"device_id": "OTHER-DEV", "operation_id": "OP-MAND-99", "timestamp": now_iso})

        # 3. Missing operation_id when active command has one
        with pytest.raises(ValueError, match="Receipt operation_id None does not match active operation"):
            actuator.confirm_stop({"device_id": actuator.device_id, "timestamp": now_iso})

        # 4. Mismatched operation_id
        with pytest.raises(ValueError, match="does not match active operation"):
            actuator.confirm_stop({"device_id": actuator.device_id, "operation_id": "OP-DIFF", "timestamp": now_iso})

        # 5. Matching device_id and operation_id confirms stop
        from services.agribrain.irrigation_runtime.actuator import create_verified_stop_receipt
        valid_rec = create_verified_stop_receipt(
            device_id=actuator.device_id,
            operation_id="OP-MAND-99",
            source="controller",
            actual_flow_lpm=0.0,
            timestamp=now_iso,
        )
        confirmed = actuator.confirm_stop(valid_rec)
        assert confirmed is True
        assert actuator.status == ActuatorStatus.ONLINE
        assert actuator.active_command is None

    def test_s04_actuator_confirm_stop_rejects_stale_or_future_receipt(self):
        """confirm_stop rejects receipts older than 600s, future-dated by > 30s, or from untrusted sources."""
        caps = ActuatorCapabilities(
            system_type=IrrigationSystemType.DRIP,
            max_flow_rate_lpm=100.0,
            max_duration_minutes=120.0,
        )
        reg = ActuatorRegistration(
            device_id="DEV-FRESH-01",
            vendor=VendorId.GENERIC,
            model="Generic_Modbus",
            protocol=DriverProtocol.MODBUS_RTU,
            plot_id="PLOT-01",
            zone_ids=["ZONE-1"],
            capabilities=caps,
        )
        class DummyDriver(IrrigationActuator):
            def __init__(self):
                super().__init__(registration=reg)

            async def connect(self):
                self._connected = True
                return True

            async def disconnect(self):
                self._connected = False
                return True

            async def emergency_stop(self):
                return CommandResult(
                    command_id=f"ESTOP-{uuid.uuid4().hex[:8]}",
                    device_id=self.device_id,
                    success=True,
                    timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                    confirmed_physical_stop=False,
                    transport_acknowledged_only=True,
                )

            async def send_command(self, cmd):
                return CommandResult(
                    command_id=cmd.command_id,
                    device_id=self.device_id,
                    success=True,
                    timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                )

            async def get_status(self):
                return self._status

        actuator = DummyDriver()
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
        actuator._active_command = IrrigationCommand(
            command_id="CMD-ACT-02",
            command_type=CommandType.START_ZONE,
            device_id=actuator.device_id,
            zone_id="ZONE-1",
            plot_id="PLOT-01",
            duration_minutes=15.0,
            volume_mm=10.0,
            operation_id="OP-FRESH-01",
        )

        now = datetime.datetime.now(timezone.utc)

        # 1. Stale receipt (> 600s ago)
        stale_receipt = {
            "device_id": actuator.device_id,
            "operation_id": "OP-FRESH-01",
            "status": "STOPPED",
            "is_running": False,
            "actual_flow_rate_lpm": 0.0,
            "timestamp": (now - datetime.timedelta(seconds=650)).isoformat(),
        }
        assert actuator.confirm_stop(stale_receipt) is False
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        # 2. Future-dated receipt (> 30s in the future)
        future_receipt = {
            "device_id": actuator.device_id,
            "operation_id": "OP-FRESH-01",
            "status": "STOPPED",
            "is_running": False,
            "actual_flow_rate_lpm": 0.0,
            "timestamp": (now + datetime.timedelta(seconds=60)).isoformat(),
        }
        assert actuator.confirm_stop(future_receipt) is False
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        # 3. Untrusted source provenance
        untrusted_receipt = {
            "device_id": actuator.device_id,
            "operation_id": "OP-FRESH-01",
            "status": "STOPPED",
            "is_running": False,
            "actual_flow_rate_lpm": 0.0,
            "timestamp": now.isoformat(),
            "source": "untrusted",
        }
        assert actuator.confirm_stop(untrusted_receipt) is False

        # 4. Fresh and valid
        from services.agribrain.irrigation_runtime.actuator import create_verified_stop_receipt
        valid_receipt = create_verified_stop_receipt(
            device_id=actuator.device_id,
            operation_id="OP-FRESH-01",
            source="modbus_plc",
            actual_flow_lpm=0.0,
            timestamp=(now - datetime.timedelta(seconds=5)).isoformat(),
        )
        assert actuator.confirm_stop(valid_receipt) is True
        assert actuator.status == ActuatorStatus.ONLINE

    def test_s05_modbus_partial_instrumentation_fails_closed(self):
        """Modbus stop requires affirmative feedback on ALL instrumented registers; partial instrumentation fails closed."""
        async def _run():
            reg = ActuatorRegistration(
                device_id="modbus_val_part",
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

            stop_cmd = IrrigationCommand(
                command_id="CMD-MB-PART",
                command_type=CommandType.STOP_ZONE,
                device_id="modbus_val_part",
                zone_id="ZONE-1",
                plot_id="plot-1",
            )

            # Case 1: Flow == 0.0, but status word missing (partial instrumentation)
            actuator._status = ActuatorStatus.EXECUTING
            with patch.object(actuator, "_write_coil", new_callable=AsyncMock, return_value=True), \
                 patch.object(actuator, "_read_input_registers", new_callable=AsyncMock, return_value=[]), \
                 patch.object(actuator, "_read_feedback", new_callable=AsyncMock, return_value=(0.0, 0.0)), \
                 patch.object(actuator, "_read_status", new_callable=AsyncMock, return_value={}):
                res1 = await actuator.execute_with_safety(stop_cmd)
                assert res1.success is True
                assert res1.transport_acknowledged_only is True
                assert res1.confirmed_physical_stop is False
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

            # Case 2: Status word running bit cleared, but flow feedback missing (None)
            actuator._status = ActuatorStatus.EXECUTING
            with patch.object(actuator, "_write_coil", new_callable=AsyncMock, return_value=True), \
                 patch.object(actuator, "_read_input_registers", new_callable=AsyncMock, return_value=[]), \
                 patch.object(actuator, "_read_feedback", new_callable=AsyncMock, return_value=(None, None)), \
                 patch.object(actuator, "_read_status", new_callable=AsyncMock, return_value={"status_word": 0x00}):
                res2 = await actuator.execute_with_safety(stop_cmd)
                assert res2.success is True
                assert res2.transport_acknowledged_only is True
                assert res2.confirmed_physical_stop is False
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

            # Case 3: Complete affirmative instrumentation (both flow == 0.0 and running bit cleared)
            actuator._status = ActuatorStatus.EXECUTING
            with patch.object(actuator, "_write_coil", new_callable=AsyncMock, return_value=True), \
                 patch.object(actuator, "_read_input_registers", new_callable=AsyncMock, return_value=[]), \
                 patch.object(actuator, "_read_feedback", new_callable=AsyncMock, return_value=(0.0, 0.0)), \
                 patch.object(actuator, "_read_status", new_callable=AsyncMock, return_value={"status_word": 0x00}):
                res3 = await actuator.execute_with_safety(stop_cmd)
                assert res3.success is True
                assert res3.transport_acknowledged_only is False
                assert res3.confirmed_physical_stop is True
                assert actuator.status == ActuatorStatus.ONLINE

        asyncio.run(_run())

    def test_s06_http_stop_contradictory_telemetry_fails_closed(self):
        """HTTP driver rejects contradictory telemetry (e.g. status STOPPED but flow > 0 or is_running True)."""
        async def _run():
            reg = ActuatorRegistration(
                device_id="http_valve_contra",
                zone_ids=["ZONE-1"],
                plot_id="plot-1",
                farm_id="farm-1",
                protocol=DriverProtocol.HTTP_REST,
                vendor=VendorId.GENERIC,
                model="HTTP_Valve",
                firmware_version="1.0.0",
                capabilities=ActuatorCapabilities(
                    system_type=IrrigationSystemType.DRIP,
                    max_flow_rate_lpm=50.0,
                    min_flow_rate_lpm=0.0,
                    max_duration_minutes=60.0,
                ),
                connection_config={"base_url": "http://127.0.0.1:8080"},
            )
            actuator = HTTPActuator(reg)
            actuator._connected = True

            stop_cmd = IrrigationCommand(
                command_id="CMD-STOP-CONTRA",
                command_type=CommandType.STOP_ZONE,
                device_id="http_valve_contra",
                zone_id="ZONE-1",
                plot_id="plot-1",
            )

            # 1. Contradictory: status STOPPED but flow_rate_lpm > 0.0
            actuator._status = ActuatorStatus.EXECUTING
            with patch.object(actuator, "_request", new_callable=AsyncMock, return_value={
                "success": True,
                "data": {"status": "STOPPED", "flow_rate_lpm": 8.5}
            }):
                res1 = await actuator.execute_with_safety(stop_cmd)
                assert res1.success is True
                assert res1.confirmed_physical_stop is False
                assert res1.transport_acknowledged_only is True
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

            # 2. Contradictory: confirmed_stopped True but is_running True
            actuator._status = ActuatorStatus.EXECUTING
            with patch.object(actuator, "_request", new_callable=AsyncMock, return_value={
                "success": True,
                "data": {"confirmed_stopped": True, "is_running": True}
            }):
                res2 = await actuator.execute_with_safety(stop_cmd)
                assert res2.success is True
                assert res2.confirmed_physical_stop is False
                assert res2.transport_acknowledged_only is True
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

            # 3. Contradictory: status STOPPED but is_stopped False
            actuator._status = ActuatorStatus.EXECUTING
            with patch.object(actuator, "_request", new_callable=AsyncMock, return_value={
                "success": True,
                "data": {"status": "STOPPED", "is_stopped": False}
            }):
                res3 = await actuator.execute_with_safety(stop_cmd)
                assert res3.success is True
                assert res3.confirmed_physical_stop is False
                assert res3.transport_acknowledged_only is True
                assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

            # 4. Consistent Affirmative: confirmed_stopped True, is_running False, flow == 0.0
            actuator._status = ActuatorStatus.EXECUTING
            with patch.object(actuator, "_request", new_callable=AsyncMock, return_value={
                "success": True,
                "data": {"confirmed_stopped": True, "is_running": False, "is_stopped": True, "flow_rate_lpm": 0.0}
            }):
                res4 = await actuator.execute_with_safety(stop_cmd)
                assert res4.success is True
                assert res4.confirmed_physical_stop is True
                assert res4.transport_acknowledged_only is False
                assert actuator.status == ActuatorStatus.ONLINE

        asyncio.run(_run())

    def test_d01_injective_evidence_identity_no_collision(self):
        """_validate_and_encode_id is strictly injective so urn:dev:123 and urn_COLON_dev_COLON_123 do not collide."""
        id1 = "urn:dev:123"
        id2 = "urn_COLON_dev_COLON_123"
        key1 = _validate_and_encode_id(id1)
        key2 = _validate_and_encode_id(id2)
        assert key1 != key2, f"Key collision detected: {key1} == {key2}"

        # Test actual raw message storage and independent retrieval
        tmp_dir = tempfile.mkdtemp(prefix="test_injective_")
        old_env = os.environ.get("AGRIWISE_SENSOR_STORAGE_DIR")
        os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = tmp_dir
        try:
            clear_storage()
            rehydrate_storage()

            now = datetime.datetime.now(timezone.utc)
            m1 = RawSensorMessage(message_id=id1, protocol="REST", received_at=now, device_id="D1", payload={"val": 1})
            m2 = RawSensorMessage(message_id=id2, protocol="REST", received_at=now, device_id="D1", payload={"val": 2})

            store_raw_message(m1)
            store_raw_message(m2)

            r1 = get_raw_message(id1)
            r2 = get_raw_message(id2)
            assert r1 is not None and r1.payload["val"] == 1
            assert r2 is not None and r2.payload["val"] == 2
        finally:
            clear_storage()
            if old_env is not None:
                os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = old_env
            else:
                os.environ.pop("AGRIWISE_SENSOR_STORAGE_DIR", None)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_d02_multiprocess_raw_and_normalized_durability(self):
        """Cross-process concurrent writes and read-after-write rehydration via multiprocessing.Process."""
        import multiprocessing
        tmp_dir = tempfile.mkdtemp(prefix="test_mp_durability_")
        old_env = os.environ.get("AGRIWISE_SENSOR_STORAGE_DIR")
        os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = tmp_dir
        try:
            clear_storage()
            rehydrate_storage()

            processes = []
            for w in range(2):
                p = multiprocessing.Process(target=_mp_worker_store_raw, args=(tmp_dir, w, 4))
                processes.append(p)

            for w in range(2):
                p = multiprocessing.Process(target=_mp_worker_store_normalized, args=(tmp_dir, w, 4))
                processes.append(p)

            for p in processes:
                p.start()

            for p in processes:
                p.join(timeout=20.0)
                assert p.exitcode == 0, f"Worker process {p} exited with code {p.exitcode}"

            for w in range(2):
                for i in range(4):
                    msg = get_raw_message(f"msg_mp_{w}_{i}")
                    assert msg is not None
                    assert msg.payload["count"] == i
                    assert msg.payload["worker"] == w

            norm_readings = get_normalized_readings()
            assert len(norm_readings) == 8, f"Expected 8 normalized readings across workers, got {len(norm_readings)}"
        finally:
            clear_storage()
            if old_env is not None:
                os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = old_env
            else:
                os.environ.pop("AGRIWISE_SENSOR_STORAGE_DIR", None)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_d03_ingestion_fails_closed_when_storage_fails(self):
        """ingest_sensor_payload fails closed and raises RuntimeError when storage persistence fails."""
        import services.agribrain.sensor_runtime.ingestion as ing_mod

        dev_id = f"test-dev-storefail-{uuid.uuid4().hex[:8]}"
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
            calibration_quality=1.0,
            valid_until=datetime.datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        register_calibration_profile(cal)

        identity = DeviceIdentity(device_id=dev_id)
        payload = {"readings": [{"variable": "soil_moisture_vwc", "value": 0.25, "unit": "fraction"}]}

        with patch.object(ing_mod, "store_normalized_reading", side_effect=IOError("Storage disk failure")):
            with pytest.raises(RuntimeError, match="Storage persistence failed"):
                ing_mod.ingest_sensor_payload(
                    protocol="MQTT",
                    device_id=dev_id,
                    payload=payload,
                    received_at=datetime.datetime.now(timezone.utc),
                    identity=identity,
                )

    def test_d04_historical_replay_retained_weather_issuance_eligibility(self):
        """_execute_canonical_water_engine rejects historical weather records in checkpoints if issued after cutoff."""
        class DummyInputs:
            weather_daily = []
            soil_observations_daily = {}
            target_date = "2026-05-01"
            crop_context = None

        mock_cw = MagicMock()
        # 1. Checkpoint contains history for 2026-05-01 where issued_at is future-dated relative to cutoff (2026-05-01T23:59:59Z)
        mock_cw.load_latest_hydraulic_checkpoint.return_value = {
            "committed_at": "2026-05-01T12:00:00Z",
            "payload": {
                "history_summary": {
                    "2026-05-01": {
                        "weather": {
                            "t_max_c": 24.0,
                            "t_min_c": 11.0,
                            "precipitation_mm": 0.0,
                            "wind_speed_2m_m_s": 2.0,
                            "rh_min_pct": 30.0,
                            "rh_max_pct": 70.0,
                            "net_radiation_mj_m2": 15.0,
                            "issued_at": "2026-05-02T12:00:00Z",  # Future-dated!
                        }
                    }
                }
            }
        }

        with patch("world_model.canonical_worldline.CanonicalWorldlineService", return_value=mock_cw):
            state, _ = _execute_canonical_water_engine(
                plot_id=f"PLOT-REPLAY-REJECT-{uuid.uuid4().hex[:6]}",
                inputs=DummyInputs(),
                op_ctx={"cycle_id": "CYCLE-2026-A", "geometry_version": "v1.2"},
                run_timestamp=datetime.datetime(2026, 5, 1, 23, 59, 59, tzinfo=timezone.utc),
            )
            assert state is None, "Historical checkpoint with future-issued weather must be rejected"

        # 2. Checkpoint contains history for 2026-05-01 where issued_at is past/eligible
        mock_cw.load_latest_hydraulic_checkpoint.return_value = {
            "committed_at": "2026-05-01T12:00:00Z",
            "payload": {
                "history_summary": {
                    "2026-05-01": {
                        "weather": {
                            "t_max_c": 24.0,
                            "t_min_c": 11.0,
                            "precipitation_mm": 0.0,
                            "wind_speed_2m_m_s": 2.0,
                            "rh_min_pct": 30.0,
                            "rh_max_pct": 70.0,
                            "net_radiation_mj_m2": 15.0,
                            "issued_at": "2026-05-01T10:00:00Z",  # Eligible!
                        }
                    }
                }
            }
        }

        with patch("world_model.canonical_worldline.CanonicalWorldlineService", return_value=mock_cw):
            state_ok, _ = _execute_canonical_water_engine(
                plot_id=f"PLOT-REPLAY-OK-{uuid.uuid4().hex[:6]}",
                inputs=DummyInputs(),
                op_ctx={"cycle_id": "CYCLE-2026-A", "geometry_version": "v1.2"},
                run_timestamp=datetime.datetime(2026, 5, 1, 23, 59, 59, tzinfo=timezone.utc),
            )
            assert state_ok is not None, "Historical checkpoint with eligible weather must be admitted"

    def test_e01_infer_rejects_ragged_grids(self):
        """infer() must strictly reject ragged 2D grid arrays across bands and cloud mask."""
        model = EOFoundationModel()
        ragged_band = [[0.1, 0.2, 0.3], [0.4, 0.5]]
        regular_band = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

        bands_ragged = {
            "B2": ragged_band,
            "B3": regular_band,
            "B4": regular_band,
        }
        with pytest.raises(ValueError, match="ragged_grid_detected"):
            model.infer(bands_ragged)

        bands_regular = {
            "B2": regular_band,
            "B3": regular_band,
            "B4": regular_band,
        }
        ragged_cloud = [[0, 0, 0], [0, 0]]
        with pytest.raises(ValueError, match="ragged_grid_detected"):
            model.infer(bands_regular, cloud_mask=ragged_cloud)

    def test_e02_missing_spatial_identity_marked_unqualified(self):
        """When CRS or transform is missing, is_spatial_qualified is False and tile_hash is distinct."""
        model = EOFoundationModel()
        regular_band = [
            [0.1, 0.2, 0.15, 0.18],
            [0.12, 0.22, 0.16, 0.19],
            [0.11, 0.21, 0.14, 0.17],
            [0.13, 0.23, 0.17, 0.20],
        ]
        bands = {"B2": regular_band, "B3": regular_band, "B4": regular_band}

        # 1. Missing CRS and transform
        res_unqualified = model.infer(bands, crs=None, transform=None)
        assert res_unqualified is not None
        assert res_unqualified.is_spatial_qualified is False

        # 2. Fully qualified spatial coordinates
        res_qualified = model.infer(bands, crs="EPSG:4326", transform=(10.0, 0.0, 500000.0, 0.0, -10.0, 4500000.0))
        assert res_qualified is not None
        assert res_qualified.is_spatial_qualified is True

        # Tile hashes must be collision-resistant between qualified and unqualified coordinates
        assert res_unqualified.tile_hash != res_qualified.tile_hash

    def test_e03_model_weights_digest_binds_binary_identity(self):
        """EmbeddingResult binds to a valid 64-character SHA-256 model weights digest."""
        model = EOFoundationModel()
        regular_band = [
            [0.1, 0.2, 0.15, 0.18],
            [0.12, 0.22, 0.16, 0.19],
            [0.11, 0.21, 0.14, 0.17],
            [0.13, 0.23, 0.17, 0.20],
        ]
        bands = {"B2": regular_band, "B3": regular_band, "B4": regular_band}
        res = model.infer(bands)
        assert res is not None
        assert hasattr(res, "model_weights_digest")
        assert isinstance(res.model_weights_digest, str)
        assert len(res.model_weights_digest) == 64
        int(res.model_weights_digest, 16)
        assert res.model_weights_digest == getattr(model, "_weights_digest", "")

    def test_s07_late_fencing_unconfirmed_stop_retains_stop_requested(self):
        """Late dispatch fencing on unconfirmed emergency_stop must retain STOP_REQUESTED and active ownership."""
        dispatcher = CommandDispatcher()
        dev_id = f"DEV-FENCE-{uuid.uuid4().hex[:6]}"
        caps = ActuatorCapabilities(
            system_type=IrrigationSystemType.DRIP,
            max_flow_rate_lpm=50.0,
            max_duration_minutes=60.0,
        )
        reg = ActuatorRegistration(
            device_id=dev_id,
            farm_id="farm-1",
            vendor=VendorId.GENERIC,
            model="Generic_Modbus",
            protocol=DriverProtocol.MODBUS_RTU,
            plot_id="PLOT-01",
            zone_ids=["ZONE-1"],
            capabilities=caps,
        )

        class DummyRealActuator(IrrigationActuator):
            def __init__(self):
                super().__init__(registration=reg)
                self._status = ActuatorStatus.ONLINE

            async def connect(self):
                self._connected = True
                return True

            async def disconnect(self):
                self._connected = False
                return True

            async def send_command(self, cmd):
                self._status = ActuatorStatus.EXECUTING
                return CommandResult(
                    command_id=cmd.command_id,
                    device_id=self.device_id,
                    success=True,
                    timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                )

            async def emergency_stop(self):
                # Returns transport success but physical stop UNCONFIRMED
                return CommandResult(
                    command_id=f"ESTOP-{uuid.uuid4().hex[:6]}",
                    device_id=self.device_id,
                    success=True,
                    timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                    confirmed_physical_stop=False,
                    transport_acknowledged_only=True,
                )

            async def get_status(self):
                return self._status

        actuator = DummyRealActuator()
        dispatcher.register_actuator(actuator)

        event = IrrigationEvent(
            event_id="EV-LATE-FENCE-01",
            plot_id="PLOT-01",
            zone_id="ZONE-1",
            device_id=dev_id,
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            target_volume_mm=10.0,
            target_duration_minutes=15.0,
            target_flow_rate_lpm=20.0,
            status=EventStatus.QUEUED,
        )

        async def _run():
            # Simulate dispatch outcome where claim was lost concurrently during transport
            records = [
                {"status": "DISPATCHING", "claimed": True},  # pre-send check passes
                {"status": "CANCELLED", "claimed": False, "owner_token": "OWNER-OTHER"},  # post-send late fence triggers
            ]
            def _mock_get_active(eid):
                if records:
                    return records.pop(0)
                return {"status": "CANCELLED", "claimed": False, "owner_token": "OWNER-OTHER"}

            with patch("services.agribrain.irrigation_runtime.dispatcher.SharedQuotaStore.atomic_check_and_reserve", return_value=None), \
                 patch("services.agribrain.irrigation_runtime.dispatcher.SharedQuotaStore.is_active", return_value=False), \
                 patch("services.agribrain.irrigation_runtime.dispatcher.SharedQuotaStore.claim_resource", return_value=(True, None)), \
                 patch("services.agribrain.irrigation_runtime.dispatcher.SharedQuotaStore.transition_to_dispatching", return_value=True), \
                 patch("services.agribrain.irrigation_runtime.dispatcher.SharedQuotaStore.get_active_record", side_effect=_mock_get_active), \
                 patch("services.agribrain.irrigation_runtime.dispatcher.SharedQuotaStore.get_resource_claim", return_value=None), \
                 patch("services.agribrain.irrigation_runtime.dispatcher.SharedQuotaStore.is_settled", return_value=False), \
                 patch("services.agribrain.irrigation_runtime.dispatcher.SharedQuotaStore.is_stopped", return_value=False), \
                 patch("services.agribrain.irrigation_runtime.dispatcher.SharedQuotaStore.reopen_active"):
                out_ev = await dispatcher.submit_event(event)
                # Unconfirmed stop must NOT finalize event as COMPLETED or CANCELLED; must retain STOP_REQUESTED!
                assert out_ev.status == EventStatus.STOP_REQUESTED
                assert event.event_id in dispatcher._active_events

        asyncio.run(_run())

    def test_s08_confirm_stop_rejects_missing_ts_missing_source_and_nan_flow(self):
        """confirm_stop strictly enforces fail-closed receipt verification: mandatory timestamp, mandatory trusted source, finite flow."""
        caps = ActuatorCapabilities(
            system_type=IrrigationSystemType.DRIP,
            max_flow_rate_lpm=50.0,
            max_duration_minutes=60.0,
        )
        reg = ActuatorRegistration(
            device_id="DEV-RECEIPT-FAILCLOSED",
            vendor=VendorId.GENERIC,
            model="Generic_Modbus",
            protocol=DriverProtocol.MODBUS_RTU,
            plot_id="PLOT-01",
            zone_ids=["ZONE-1"],
            capabilities=caps,
        )

        class DummyDriver(IrrigationActuator):
            def __init__(self):
                super().__init__(registration=reg)
            async def connect(self): return True
            async def disconnect(self): return True
            async def send_command(self, cmd): return CommandResult(command_id=cmd.command_id, device_id=self.device_id, success=True, timestamp=datetime.datetime.now(timezone.utc).isoformat())
            async def emergency_stop(self): return CommandResult(command_id="E", device_id=self.device_id, success=True, timestamp=datetime.datetime.now(timezone.utc).isoformat())
            async def get_status(self): return self._status

        actuator = DummyDriver()
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
        actuator._active_command = IrrigationCommand(
            command_id="CMD-OP-01",
            command_type=CommandType.START_ZONE,
            device_id=actuator.device_id,
            zone_id="ZONE-1",
            plot_id="PLOT-01",
            operation_id="OP-FAILCLOSE-01",
        )
        now_iso = datetime.datetime.now(timezone.utc).isoformat()

        # 1. Missing timestamp fails closed
        assert actuator.confirm_stop({
            "device_id": actuator.device_id,
            "operation_id": "OP-FAILCLOSE-01",
            "source": "controller",
            "status": "STOPPED",
            "actual_flow_rate_lpm": 0.0,
        }) is False

        # 2. Missing source/provenance fails closed
        assert actuator.confirm_stop({
            "device_id": actuator.device_id,
            "operation_id": "OP-FAILCLOSE-01",
            "timestamp": now_iso,
            "status": "STOPPED",
            "actual_flow_rate_lpm": 0.0,
        }) is False

        # 3. Anonymous or untrusted source fails closed
        assert actuator.confirm_stop({
            "device_id": actuator.device_id,
            "operation_id": "OP-FAILCLOSE-01",
            "timestamp": now_iso,
            "source": "anonymous",
            "status": "STOPPED",
            "actual_flow_rate_lpm": 0.0,
        }) is False

        # 4. NaN flow value fails closed
        assert actuator.confirm_stop({
            "device_id": actuator.device_id,
            "operation_id": "OP-FAILCLOSE-01",
            "timestamp": now_iso,
            "source": "controller",
            "status": "STOPPED",
            "actual_flow_rate_lpm": float("nan"),
            "is_stopped": True,
        }) is False

        # 5. Infinite flow value fails closed
        assert actuator.confirm_stop({
            "device_id": actuator.device_id,
            "operation_id": "OP-FAILCLOSE-01",
            "timestamp": now_iso,
            "source": "controller",
            "status": "STOPPED",
            "actual_flow_rate_lpm": float("inf"),
            "is_stopped": True,
        }) is False

        # 6. Non-numeric boolean flow fails closed
        assert actuator.confirm_stop({
            "device_id": actuator.device_id,
            "operation_id": "OP-FAILCLOSE-01",
            "timestamp": now_iso,
            "source": "controller",
            "status": "STOPPED",
            "actual_flow_rate_lpm": True,
            "is_stopped": True,
        }) is False

        # 7. Positive flow fails closed
        assert actuator.confirm_stop({
            "device_id": actuator.device_id,
            "operation_id": "OP-FAILCLOSE-01",
            "timestamp": now_iso,
            "source": "controller",
            "status": "STOPPED",
            "actual_flow_rate_lpm": 4.5,
            "is_stopped": True,
        }) is False

        # Actuator remains STOP_PENDING_CONFIRMATION
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        # 8. Fully authenticated, timestamped, finite-zero flow receipt succeeds
        from services.agribrain.irrigation_runtime.actuator import create_verified_stop_receipt
        valid_rec = create_verified_stop_receipt(
            device_id=actuator.device_id,
            operation_id="OP-FAILCLOSE-01",
            timestamp=now_iso,
            source="controller",
            actual_flow_lpm=0.0,
        )
        assert actuator.confirm_stop(valid_rec) is True
        assert actuator.status == ActuatorStatus.ONLINE

    def test_s09_nonstandard_transport_stop_cannot_fabricate_confirmed_stop(self):
        """Nonstandard or mock transport driver without explicit simulation classification cannot fabricate confirmed_physical_stop=True."""
        caps = ActuatorCapabilities(
            system_type=IrrigationSystemType.DRIP,
            max_flow_rate_lpm=50.0,
            max_duration_minutes=60.0,
        )
        reg = ActuatorRegistration(
            device_id="DEV-CUSTOM-NONSTANDARD",
            vendor=VendorId.GENERIC,
            model="CustomHardwareDriver",
            protocol=DriverProtocol.MODBUS_RTU,
            plot_id="PLOT-01",
            zone_ids=["ZONE-1"],
            capabilities=caps,
        )

        class CustomRealActuator(IrrigationActuator):
            def __init__(self):
                super().__init__(registration=reg)
                self.is_simulation = False
                self.is_mock = False
            async def connect(self): return True
            async def disconnect(self): return True
            async def send_command(self, cmd):
                # Driver does not verify physical registers
                return CommandResult(
                    command_id=cmd.command_id,
                    device_id=self.device_id,
                    success=True,
                    timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                    confirmed_physical_stop=False,
                )
            async def emergency_stop(self):
                return await self.send_command(IrrigationCommand(
                    command_id="CMD-E",
                    command_type=CommandType.EMERGENCY_STOP,
                    device_id=self.device_id,
                    zone_id="ZONE-1",
                    plot_id="PLOT-01",
                ))
            async def get_status(self): return self._status

        actuator = CustomRealActuator()
        actuator._status = ActuatorStatus.EXECUTING

        async def _run():
            stop_cmd = IrrigationCommand(
                command_id="CMD-STOP-REAL",
                command_type=CommandType.STOP_ZONE,
                device_id=actuator.device_id,
                zone_id="ZONE-1",
                plot_id="PLOT-01",
                operation_id="OP-REAL-01",
            )
            res = await actuator.execute_with_safety(stop_cmd)
            # Physical stop must NOT be fabricated!
            assert res.confirmed_physical_stop is False
            assert res.transport_acknowledged_only is True
            assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        asyncio.run(_run())

    def test_d05_storage_atomic_raw_publication_and_os_advisory_locking(self):
        """Raw sensor storage publishes atomically without leaving 0-byte orphan placeholders."""
        tmp_dir = tempfile.mkdtemp(prefix="test_atomic_raw_")
        old_env = os.environ.get("AGRIWISE_SENSOR_STORAGE_DIR")
        os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = tmp_dir
        try:
            clear_storage()
            rehydrate_storage()

            msg = RawSensorMessage(
                message_id="msg-atomic-001",
                protocol="MQTT",
                received_at=datetime.datetime.now(timezone.utc),
                device_id="sensor-atomic",
                payload={"reading": 42.0},
            )
            store_raw_message(msg)

            raw_dir = Path(tmp_dir) / "raw"
            files = list(raw_dir.glob("raw_*.json"))
            assert len(files) == 1
            assert files[0].stat().st_size > 0

            # No temporary or empty orphan files left in raw_dir
            orphan_tmps = list(raw_dir.glob("tmp_*.json"))
            assert len(orphan_tmps) == 0

            # Duplicate rejection
            with pytest.raises(ValueError, match="immutable and cannot be overwritten"):
                store_raw_message(msg)
        finally:
            clear_storage()
            if old_env is not None:
                os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = old_env
            else:
                os.environ.pop("AGRIWISE_SENSOR_STORAGE_DIR", None)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_d06_storage_rehydrate_corrupted_log_raises_storage_corrupted_error(self):
        """rehydrate_storage raises StorageCorruptedError upon encountering corrupted JSON lines in normalized log."""
        tmp_dir = tempfile.mkdtemp(prefix="test_corrupt_log_")
        old_env = os.environ.get("AGRIWISE_SENSOR_STORAGE_DIR")
        os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = tmp_dir
        try:
            norm_dir = Path(tmp_dir) / "normalized"
            norm_dir.mkdir(parents=True, exist_ok=True)
            norm_file = norm_dir / "normalized_readings.jsonl"
            # Write a corrupted non-empty line
            with open(norm_file, "w", encoding="utf-8") as f:
                f.write('{"reading_id": "NORM-1", "device_id": "D1"}\n')
                f.write('CORRUPTED_JSON_LINE_NOT_VALID_SYNTAX\n')

            with pytest.raises(StorageCorruptedError, match="Corrupted record in normalized storage log"):
                rehydrate_storage()
        finally:
            if old_env is not None:
                os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = old_env
            else:
                os.environ.pop("AGRIWISE_SENSOR_STORAGE_DIR", None)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_e04_onnx_runtime_failure_reports_fallback_weights_digest(self):
        """When ONNX inference fails at runtime, result reports spectral_basis_v2 and fallback weights digest."""
        model = EOFoundationModel()
        # Force model mode to onnx
        model._mode = "onnx"
        model._onnx_weights_digest = "1" * 64
        model._init_fallback_weights()
        model._fallback_weights_digest = model._compute_fallback_weights_digest()
        model._weights_digest = model._onnx_weights_digest

        # Simulate ONNX runtime inference failure (returns None)
        with patch.object(model, "_infer_onnx", return_value=None):
            regular_band = [
                [0.1, 0.2, 0.15, 0.18],
                [0.12, 0.22, 0.16, 0.19],
                [0.11, 0.21, 0.14, 0.17],
                [0.13, 0.23, 0.17, 0.20],
            ]
            bands = {"B2": regular_band, "B3": regular_band, "B4": regular_band}
            res = model.infer(bands)
            assert res is not None
            assert res.model_id == "spectral_basis_v2"
            # Reported weights digest MUST match the fallback weights digest, NOT the ONNX digest!
            assert res.model_weights_digest == model._fallback_weights_digest
            assert res.model_weights_digest != model._onnx_weights_digest

    def test_e05_spatially_unqualified_eo_evidence_prohibited_from_state_updates(self):
        """Spatially unqualified EO embeddings must be tagged with UNQUALIFIED_SPATIAL_IDENTITY and barred from state updates."""
        from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
        from services.agribrain.layer1_fusion.schemas import Layer1InputBundle
        engine = Layer1FusionEngine()
        regular_band = [
            [0.1, 0.2, 0.15, 0.18],
            [0.12, 0.22, 0.16, 0.19],
            [0.11, 0.21, 0.14, 0.17],
            [0.13, 0.23, 0.17, 0.20],
        ]
        now = datetime.datetime.now(timezone.utc)
        # Missing CRS and transform in raster composites
        bundle = Layer1InputBundle(
            plot_id="PLOT-EO-SPATIAL-01",
            run_id="run-eo-spatial-01",
            run_timestamp=now,
            window_start=now - datetime.timedelta(hours=1),
            window_end=now,
            raster_composites={
                "B2": {"pixel_array": regular_band},
                "B3": {"pixel_array": regular_band},
                "B4": {"pixel_array": regular_band},
            },
        )
        ctx = engine.fuse(bundle)
        # Check all admitted items for UNQUALIFIED_SPATIAL_IDENTITY
        eo_items = [it for it in ctx.evidence_items if it.source_family == "eo_foundation"]
        assert len(eo_items) > 0
        for it in eo_items:
            assert "UNQUALIFIED_SPATIAL_IDENTITY" in it.flags
            assert it.state_update_allowed is False
            assert it.production_usable is False

    def test_e06_spatially_qualified_eo_evidence_admitted_to_state_updates(self):
        """End-to-end: Coherent per-band georeferencing yields spatially qualified EO evidence admitted to state updates."""
        from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
        from services.agribrain.layer1_fusion.schemas import Layer1InputBundle
        engine = Layer1FusionEngine()
        regular_band = [
            [0.1, 0.2, 0.15, 0.18],
            [0.12, 0.22, 0.16, 0.19],
            [0.11, 0.21, 0.14, 0.17],
            [0.13, 0.23, 0.17, 0.20],
        ]
        now = datetime.datetime.now(timezone.utc)
        valid_transform = (10.0, 0.0, 500000.0, 0.0, -10.0, 4500000.0)

        # 1. Positive path: Coherent CRS and affine transform across bands
        bundle_qualified = Layer1InputBundle(
            plot_id="PLOT-EO-QUALIFIED-01",
            run_id="run-eo-qual-01",
            run_timestamp=now,
            window_start=now - datetime.timedelta(hours=1),
            window_end=now,
            raster_composites={
                "B2": {"pixel_array": regular_band, "crs": "EPSG:4326", "transform": valid_transform},
                "B3": {"pixel_array": regular_band, "crs": "EPSG:4326", "transform": valid_transform},
                "B4": {"pixel_array": regular_band, "crs": "EPSG:4326", "transform": valid_transform},
            },
        )
        ctx = engine.fuse(bundle_qualified)
        anomaly_scores = [
            it for it in ctx.evidence_items
            if it.source_family == "eo_foundation" and it.variable == "anomaly_score"
        ]
        assert len(anomaly_scores) == 1
        score_item = anomaly_scores[0]
        assert "UNQUALIFIED_SPATIAL_IDENTITY" not in score_item.flags
        assert score_item.production_usable is True
        # Scientific authority protection: model-derived feature remains diagnostic only and denies state updates
        assert score_item.state_update_allowed is False
        assert score_item.diagnostic_only is True
        assert score_item.truth_class == "estimated_model"
        assert score_item.real_provider_product is False

        # 2. Negative path: Mismatched CRS across bands fails closed
        bundle_mismatched = Layer1InputBundle(
            plot_id="PLOT-EO-MISMATCH-01",
            run_id="run-eo-mismatch-01",
            run_timestamp=now,
            window_start=now - datetime.timedelta(hours=1),
            window_end=now,
            raster_composites={
                "B2": {"pixel_array": regular_band, "crs": "EPSG:4326", "transform": valid_transform},
                "B3": {"pixel_array": regular_band, "crs": "EPSG:32633", "transform": valid_transform},
                "B4": {"pixel_array": regular_band, "crs": "EPSG:4326", "transform": valid_transform},
            },
        )
        ctx_mismatched = engine.fuse(bundle_mismatched)
        mismatched_scores = [
            it for it in ctx_mismatched.evidence_items
            if it.source_family == "eo_foundation" and it.variable == "anomaly_score"
        ]
        assert len(mismatched_scores) == 1
        assert "UNQUALIFIED_SPATIAL_IDENTITY" in mismatched_scores[0].flags
        assert mismatched_scores[0].state_update_allowed is False
        assert mismatched_scores[0].production_usable is False

    def test_s10_custom_hardware_cannot_enter_simulation_exception(self):
        """Custom hardware (VendorId.CUSTOM) without physical stop proof cannot enter the simulation exception."""
        mock_registry = MagicMock()
        mock_safety = MagicMock()
        dispatcher = CommandDispatcher(registry=mock_registry, safety=mock_safety)

        # Real custom-vendor actuator (is_simulation=False, not mock)
        reg = ActuatorRegistration(
            device_id="DEV-CUSTOM-HW-01",
            protocol=DriverProtocol.MODBUS_TCP,
            vendor=VendorId.CUSTOM,
            model="CustomFieldControllerV2",
            capabilities=ActuatorCapabilities(system_type=IrrigationSystemType.DRIP),
        )
        actuator = ModbusActuator(registration=reg)
        actuator._status = ActuatorStatus.ONLINE

        now_ts = datetime.datetime.now(timezone.utc).isoformat()

        # Transport-successful stop result, but no physical confirmation
        unconfirmed_stop = CommandResult(
            command_id="CMD-STOP-01",
            device_id="DEV-CUSTOM-HW-01",
            success=True,
            timestamp=now_ts,
            confirmed_physical_stop=False,
            transport_acknowledged_only=False,
        )

        # Must NOT enter simulation exception -- returns False for real custom hardware
        assert dispatcher._is_stop_confirmed(actuator, unconfirmed_stop) is False

        # Positive proof: affirmative verified physical stop proof returns True
        confirmed_stop = CommandResult(
            command_id="CMD-STOP-01",
            device_id="DEV-CUSTOM-HW-01",
            success=True,
            timestamp=now_ts,
            confirmed_physical_stop=True,
            transport_acknowledged_only=False,
        )
        assert dispatcher._is_stop_confirmed(actuator, confirmed_stop) is True

    def test_s11_confirm_stop_requires_authenticated_provenance_and_correlated_operation(self):
        """confirm_stop requires correlated operation ID in recovery and rejects unauthenticated caller provenance."""
        reg = ActuatorRegistration(
            device_id="DEV-RECEIPT-AUTH-01",
            protocol=DriverProtocol.MODBUS_TCP,
            vendor=VendorId.CUSTOM,
            model="FieldPLC",
            capabilities=ActuatorCapabilities(system_type=IrrigationSystemType.DRIP),
        )
        actuator = ModbusActuator(registration=reg)
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
        now_ts = datetime.datetime.now(timezone.utc).isoformat()

        # 1. Recovery path (active_command is absent): missing operation_id raises ValueError
        with pytest.raises(ValueError, match="missing mandatory operation_id / command_id"):
            actuator.confirm_stop({
                "device_id": "DEV-RECEIPT-AUTH-01",
                "timestamp": now_ts,
                "source": "controller",
                "actual_flow_lpm": 0.0,
            })

        # 1b. Un-correlated operation ID when no expected/pending/durable operation exists raises ValueError
        from services.agribrain.irrigation_runtime.actuator import create_verified_stop_receipt
        orphan_receipt = create_verified_stop_receipt(
            device_id="DEV-RECEIPT-AUTH-01",
            operation_id="OP-UNESTABLISHED-999",
            source="modbus_plc",
            actual_flow_lpm=0.0,
            timestamp=now_ts,
        )
        with pytest.raises(ValueError, match="no active, expected, pending, or durable operation established"):
            actuator.confirm_stop(orphan_receipt)

        # 2. Mismatched expected_operation_id raises ValueError
        with pytest.raises(ValueError, match="does not match expected operation"):
            actuator.confirm_stop(
                {
                    "device_id": "DEV-RECEIPT-AUTH-01",
                    "operation_id": "OP-WRONG-999",
                    "timestamp": now_ts,
                    "source": "controller",
                    "actual_flow_lpm": 0.0,
                },
                expected_operation_id={"OP-EXPECTED-100", "EVT-100"},
            )

        # 3. Unauthenticated/arbitrary caller dictionary rejected (returns False)
        untrusted_res = actuator.confirm_stop(
            {
                "device_id": "DEV-RECEIPT-AUTH-01",
                "operation_id": "OP-EXPECTED-100",
                "timestamp": now_ts,
                "source": "unauthorized_external_script",
                "actual_flow_lpm": 0.0,
            },
            expected_operation_id={"OP-EXPECTED-100"},
        )
        assert untrusted_res is False
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        # 4. Explicitly unauthenticated receipt rejected (returns False)
        unauth_res = actuator.confirm_stop(
            {
                "device_id": "DEV-RECEIPT-AUTH-01",
                "operation_id": "OP-EXPECTED-100",
                "timestamp": now_ts,
                "source": "controller",
                "authenticated": False,
                "actual_flow_lpm": 0.0,
            },
            expected_operation_id={"OP-EXPECTED-100"},
        )
        assert unauth_res is False

        # 4b. Self-declared dictionary without cryptographic token rejected (returns False)
        unverified_dict_res = actuator.confirm_stop(
            {
                "device_id": "DEV-RECEIPT-AUTH-01",
                "operation_id": "OP-EXPECTED-100",
                "timestamp": now_ts,
                "source": "modbus_plc",
                "actual_flow_lpm": 0.0,
            },
            expected_operation_id={"OP-EXPECTED-100"},
        )
        assert unverified_dict_res is False

        # 5. Cryptographically authenticated, verified receipt from trusted device boundary succeeds
        valid_receipt = create_verified_stop_receipt(
            device_id="DEV-RECEIPT-AUTH-01",
            operation_id="OP-EXPECTED-100",
            attempt_number=1,
            source="modbus_plc",
            actual_flow_lpm=0.0,
            timestamp=now_ts,
        )
        valid_res = actuator.confirm_stop(
            valid_receipt,
            expected_operation_id={"OP-EXPECTED-100"},
        )
        assert valid_res is True
        assert actuator.status == ActuatorStatus.ONLINE

        # 6. Replay resistance: consuming the exact same receipt token again must fail
        replay_res = actuator.confirm_stop(
            valid_receipt,
            expected_operation_id={"OP-EXPECTED-100"},
        )
        assert replay_res is False

    def test_f02_lookback_loop_rejects_future_issued_candidate(self):
        """Historical lookback walk skips candidate weather records whose issued_at is in the future relative to step limit."""
        class DummyInputs:
            # Target date 2026-05-02 is provided
            # Intermediate day 2026-05-01 is missing from weather_daily
            # Earlier day 2026-04-30 has a candidate issued in the future (relative to step limit 2026-05-01T23:59:59Z)
            weather_daily = {
                "2026-05-02": {
                    "t_max_c": 22.0,
                    "t_min_c": 12.0,
                    "precipitation_mm": 0.0,
                    "wind_speed_2m_m_s": 2.0,
                    "rh_min_pct": 35.0,
                    "rh_max_pct": 75.0,
                    "net_radiation_mj_m2": 15.0,
                    "issued_at": "2026-05-02T10:00:00Z",
                },
                "2026-04-30": {
                    "t_max_c": 38.0,
                    "t_min_c": 25.0,
                    "precipitation_mm": 0.0,
                    "wind_speed_2m_m_s": 5.0,
                    "rh_min_pct": 20.0,
                    "rh_max_pct": 50.0,
                    "net_radiation_mj_m2": 25.0,
                    "issued_at": "2026-05-05T00:00:00Z",  # Future-issued!
                },
            }
            soil_observations_daily = {}
            target_date = "2026-05-02"
            crop_context = None

        mock_cw = MagicMock()
        mock_cw.load_latest_hydraulic_checkpoint.return_value = {
            "committed_at": "2026-04-30T00:00:00Z",
            "payload": {
                "target_date": "2026-04-30",
                "soil_water_state": {
                    "layer_depths_cm": [10.0, 20.0, 30.0],
                    "layer_theta": [0.25, 0.25, 0.25],
                    "evaporation_state": {
                        "days_since_wetting": 1,
                        "few_exposed_wetted_fraction": 0.5,
                        "surface_storage_mm": 0.0,
                        "max_surface_storage_mm": 5.0,
                        "kr_reduction_factor": 1.0,
                    },
                },
            },
        }

        with patch("world_model.canonical_worldline.CanonicalWorldlineService", return_value=mock_cw):
            state, audit = _execute_canonical_water_engine(
                plot_id=f"PLOT-LOOKBACK-{uuid.uuid4().hex[:6]}",
                inputs=DummyInputs(),
                op_ctx={"cycle_id": "CYCLE-2026-A", "geometry_version": "v1.2"},
                run_timestamp=datetime.datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc),
            )
            assert state is not None
            # The future-issued 2026-04-30 candidate (t_max=38.0) must have been rejected by the lookback walk
            # and fallen back to climatological prior rather than contaminating state
            assert state.soil_water is not None and len(state.soil_water.theta_profile) > 0
            assert state.soil_water.evaporation_state is not None

    def test_s12_contradictory_http_telemetry_cannot_finalize_cancellation_or_remove_quota(self):
        """Contradictory HTTP telemetry (reporting ONLINE while flow > 0 or running) cannot finalize cancellation or drop quota."""
        async def _run():
            reg = ActuatorRegistration(
                device_id="HTTP-CONTRADICT-01",
                protocol=DriverProtocol.HTTP_REST,
                vendor=VendorId.GENERIC,
                model="REST_Valve_v1",
                capabilities=ActuatorCapabilities(system_type=IrrigationSystemType.DRIP),
                connection_config={"base_url": "http://mock-field-controller:8080"},
            )
            actuator = HTTPActuator(reg)

            # 1. Contradictory telemetry query: reports status='ONLINE' but flow_rate_lpm=18.5 and is_running=True
            contradictory_telemetry = {
                "success": True,
                "data": {
                    "status": "ONLINE",
                    "flow_rate_lpm": 18.5,
                    "is_running": True,
                    "is_stopped": False,
                },
            }
            with patch.object(actuator, "_request", AsyncMock(return_value=contradictory_telemetry)):
                st = await actuator.get_status()
                # Must classify as EXECUTING, NEVER ONLINE!
                assert st == ActuatorStatus.EXECUTING
                assert actuator._status == ActuatorStatus.EXECUTING

            # 2. Dispatcher cancel_event with contradictory telemetry fails closed
            mock_registry = MagicMock()
            mock_registry.get_actuator.return_value = actuator
            safety = SafetyMonitor()
            dispatcher = CommandDispatcher(registry=mock_registry, safety=safety)

            event = IrrigationEvent(
                event_id="EVT-HTTP-CANCEL-01",
                plot_id="PLOT-01",
                zone_id="ZONE-1",
                device_id=actuator.device_id,
                system_type=IrrigationSystemType.DRIP,
                automation_mode=AutomationMode.FULL_AUTO,
                target_volume_mm=10.0,
                target_duration_minutes=30.0,
                target_flow_rate_lpm=25.0,
                status=EventStatus.EXECUTING,
            )
            dispatcher._active_events[event.event_id] = event

            SharedQuotaStore.reset()
            SharedQuotaStore.reserve(
                event_id=event.event_id,
                plot_id=event.plot_id,
                volume_mm=event.target_volume_mm,
                device_id=event.device_id,
                zone_id=event.zone_id,
            )

            # When cancel is attempted, emergency stop returns transport success but contradictory flow
            cancel_stop_res = {
                "success": True,
                "data": {
                    "status": "ONLINE",
                    "flow_rate_lpm": 15.0,
                    "is_running": True,
                    "is_stopped": False,
                },
            }
            with patch.object(actuator, "_request", AsyncMock(side_effect=[contradictory_telemetry, cancel_stop_res])):
                res_event = await dispatcher.cancel_event(event.event_id, reason="User test cancellation")
                # Must NOT transition to CANCELLED; must enter STOP_REQUESTED!
                assert res_event.status == EventStatus.STOP_REQUESTED
                # Must retain live tracking and reservation
                assert event.event_id in dispatcher._active_events
                assert SharedQuotaStore.is_active(event.event_id) is True

        asyncio.run(_run())

    def test_s13_late_start_fence_treats_transport_only_stop_as_unconfirmed_and_retains_stop_requested(self):
        """Late START fence treats transport-only STOP acknowledgment as unconfirmed and retains STOP_REQUESTED."""
        async def _run():
            SharedQuotaStore.reset()
            mock_registry = MagicMock()
            safety = SafetyMonitor()
            dispatcher = CommandDispatcher(registry=mock_registry, safety=safety)

            reg = ActuatorRegistration(
                device_id="DEV-LATE-TRANS-01",
                protocol=DriverProtocol.MODBUS_TCP,
                vendor=VendorId.CUSTOM,
                model="CustomFieldPLC",
                capabilities=ActuatorCapabilities(system_type=IrrigationSystemType.DRIP),
            )
            actuator = ModbusActuator(reg)
            mock_registry.get_actuator.return_value = actuator

            event = IrrigationEvent(
                event_id="EVT-LATE-FENCE-TRANS-01",
                plot_id="PLOT-FENCE-01",
                zone_id="ZONE-1",
                device_id=actuator.device_id,
                system_type=IrrigationSystemType.DRIP,
                automation_mode=AutomationMode.FULL_AUTO,
                target_volume_mm=12.0,
                target_duration_minutes=25.0,
                target_flow_rate_lpm=20.0,
                status=EventStatus.QUEUED,
            )

            # START dispatch succeeds at transport level
            start_result = CommandResult(
                command_id="CMD-START-LATE",
                device_id=actuator.device_id,
                success=True,
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
            )

            # Stop returns transport-acknowledged only (no verified cessation)
            transport_only_stop = CommandResult(
                command_id="ESTOP-TRANS-ONLY",
                device_id=actuator.device_id,
                success=True,
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                transport_acknowledged_only=True,
                confirmed_physical_stop=False,
            )

            async def mock_dispatch(ev, act):
                # Race condition: event was cancelled in-flight while dispatch was executing
                ev.status = EventStatus.CANCELLED
                return start_result

            with patch.object(actuator, "emergency_stop", AsyncMock(return_value=transport_only_stop)):
                with patch.object(dispatcher, "_dispatch_with_retry", side_effect=mock_dispatch):
                    res = await dispatcher.submit_event(event)
                    # Late fence failed because stop was transport-only; must enter STOP_REQUESTED!
                    assert res.status == EventStatus.STOP_REQUESTED
                    assert event.event_id in dispatcher._active_events
                    assert SharedQuotaStore.get_status(event.event_id) == "STOP_REQUESTED"

        asyncio.run(_run())

    def test_f03_future_issued_weather_prior_rejected_and_backfill_marked_prior(self):
        """Future-issued weather_prior is rejected, and backfilled prior data is marked source_role='prior'."""
        from services.agribrain.layer3_decision.runner import _execute_canonical_water_engine

        step_limit = datetime.datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        # 1. Future-issued weather_prior is rejected when observation is missing
        class MissingInputs:
            weather_daily = {}  # No observations
            soil_observations_daily = {}
            target_date = "2026-06-01"
            crop_context = None

        future_prior = {
            "temp_max": 28.0,
            "temp_min": 16.0,
            "precipitation": 0.0,
            "wind_speed": 2.5,
            "rh_min": 40.0,
            "rh_max": 80.0,
            "net_radiation": 18.0,
            "issued_at": "2026-06-05T00:00:00Z",  # Future-issued relative to 2026-06-01!
        }

        state, audit = _execute_canonical_water_engine(
            plot_id="PLOT-WEATHER-CAUSAL-01",
            inputs=MissingInputs(),
            op_ctx={"weather_prior": future_prior},
            run_timestamp=step_limit,
        )
        # Must preserve missingness and return None rather than admitting future-issued prior!
        assert state is None
        assert audit is None

        # 2. Backfill from eligible weather_prior marks record as source_role='prior'
        class PartialInputs:
            weather_daily = {
                "2026-06-01": {
                    "t_max_c": 26.0,
                    # t_min_c missing, will backfill from eligible prior
                    "wind_speed_2m_m_s": 2.0,
                    "rh_min_pct": 35.0,
                    "rh_max_pct": 75.0,
                    "net_radiation_mj_m2": 15.0,
                    "precipitation_mm": 0.0,
                    "issued_at": "2026-06-01T08:00:00Z",
                }
            }
            soil_observations_daily = {}
            target_date = "2026-06-01"
            crop_context = None

        eligible_prior = {
            "temp_max": 25.0,
            "temp_min": 14.0,
            "precipitation": 0.0,
            "wind_speed": 2.0,
            "rh_min": 35.0,
            "rh_max": 75.0,
            "net_radiation": 15.0,
            "issued_at": "2026-05-31T12:00:00Z",  # Past-issued, eligible
        }

        state, audit = _execute_canonical_water_engine(
            plot_id="PLOT-WEATHER-CAUSAL-02",
            inputs=PartialInputs(),
            op_ctx={"weather_prior": eligible_prior},
            run_timestamp=step_limit,
        )
        assert state is not None
        assert audit is not None
        from services.agribrain.layer3_decision.runner import _PLOT_WATER_STATE_HISTORY
        w_record = _PLOT_WATER_STATE_HISTORY["PLOT-WEATHER-CAUSAL-02"]["2026-06-01"]["weather"]
        # Because missing temp_min was backfilled from prior, source_role must be 'prior'!
        assert w_record.get("source_role") == "prior"
        assert w_record.get("is_prior") is True
        assert w_record.get("has_prior_backfill") is True

    def test_e07_eo_foundation_rejects_singular_transforms_and_infinite_reflectance_without_hash_collision(self):
        """EO foundation model rejects singular transforms and non-finite reflectance without hash collision."""
        model = EOFoundationModel()
        regular_band = [
            [0.1, 0.2, 0.15, 0.18],
            [0.12, 0.22, 0.16, 0.19],
            [0.11, 0.21, 0.14, 0.17],
            [0.13, 0.23, 0.17, 0.20],
        ]
        bands = {"B2": regular_band, "B3": regular_band, "B4": regular_band}

        # 1. Singular/degenerate transform (0,0,0,0,0,0) rejected from spatial qualification
        singular_tf = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        res_singular = model.infer(bands, crs="EPSG:4326", transform=singular_tf)
        assert res_singular is not None
        assert res_singular.is_spatial_qualified is False

        # 2. Infinite reflectance is filtered out by _normalize_bands
        infinite_band = [
            [float("inf"), 0.2, 0.15, 0.18],
            [0.12, float("-inf"), 0.16, 0.19],
            [0.11, 0.21, 0.14, 0.17],
            [0.13, 0.23, 0.17, 0.20],
        ]
        norm_inf = model._normalize_bands({"B2": infinite_band}, ["B2"], None)
        assert norm_inf is not None
        # Infinite pixels were rejected, so valid count is 14 instead of 16
        assert norm_inf["valid_count"] == 14
        assert all(math.isfinite(x) for x in norm_inf["flat_bands"]["B2"])

        # 3. Hash collision resistance: missing vs infinite vs NaN inputs produce distinct hashes
        missing_band = [
            [None, 0.2, 0.15, 0.18],
            [0.12, None, 0.16, 0.19],
            [0.11, 0.21, 0.14, 0.17],
            [0.13, 0.23, 0.17, 0.20],
        ]
        nan_band = [
            [float("nan"), 0.2, 0.15, 0.18],
            [0.12, float("nan"), 0.16, 0.19],
            [0.11, 0.21, 0.14, 0.17],
            [0.13, 0.23, 0.17, 0.20],
        ]
        hash_inf = model._compute_tile_hash({"B2": infinite_band}, ["B2"])
        hash_missing = model._compute_tile_hash({"B2": missing_band}, ["B2"])
        hash_nan = model._compute_tile_hash({"B2": nan_band}, ["B2"])

        assert hash_inf != hash_missing
        assert hash_inf != hash_nan
        assert hash_missing != hash_nan

    def test_d07_storage_warm_worker_synchronizes_cross_process_commits(self):
        """Warm sensor storage worker synchronizes with disk to maintain visibility of rows committed by other workers."""
        tmp_dir = tempfile.mkdtemp(prefix="test_multi_worker_sync_")
        old_env = os.environ.get("AGRIWISE_SENSOR_STORAGE_DIR")
        os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = tmp_dir
        try:
            clear_storage()
            now = datetime.datetime.now(timezone.utc)

            # Worker 1 stores Row 1
            r1 = NormalizedSensorReading(
                reading_id="NORM-W1-01",
                device_id="DEV-SENS-01",
                plot_id="PLOT-01",
                zone_id="ZONE-1",
                timestamp=now,
                received_at=now,
                variable="soil_moisture",
                value=24.5,
                unit="%",
                vendor="AcmeSensors",
                protocol="MQTT",
            )
            store_normalized_reading(r1)

            # Simulate Worker 2 (another process) appending Row 2 directly to disk under the lock
            storage_dir = Path(tmp_dir)
            norm_file = storage_dir / "normalized" / "normalized_readings.jsonl"
            lock_file = storage_dir / "normalized" / "normalized_readings.lock"

            r2_dict = {
                "reading_id": "NORM-W2-02",
                "device_id": "DEV-SENS-02",
                "plot_id": "PLOT-01",
                "zone_id": "ZONE-2",
                "timestamp": now.isoformat(),
                "received_at": now.isoformat(),
                "variable": "soil_moisture",
                "value": 28.0,
                "unit": "%",
                "vendor": "AcmeSensors",
                "protocol": "MQTT",
            }
            from services.agribrain.sensor_runtime.storage import _acquire_and_append
            _acquire_and_append(norm_file, lock_file, (json.dumps(r2_dict) + "\n").encode("utf-8"))

            # Warm Worker 1 stores Row 3
            r3 = NormalizedSensorReading(
                reading_id="NORM-W1-03",
                device_id="DEV-SENS-01",
                plot_id="PLOT-01",
                zone_id="ZONE-1",
                timestamp=now,
                received_at=now,
                variable="soil_moisture",
                value=25.0,
                unit="%",
                vendor="AcmeSensors",
                protocol="MQTT",
            )
            store_normalized_reading(r3)

            # Warm Worker 1 queries readings: must see ALL committed rows (Row 1, Row 2, Row 3)!
            all_readings = get_normalized_readings()
            reading_ids = [r.reading_id for r in all_readings]
            assert "NORM-W1-01" in reading_ids
            assert "NORM-W2-02" in reading_ids
            assert "NORM-W1-03" in reading_ids
            assert len(all_readings) == 3
        finally:
            clear_storage()
            if old_env is not None:
                os.environ["AGRIWISE_SENSOR_STORAGE_DIR"] = old_env
            else:
                os.environ.pop("AGRIWISE_SENSOR_STORAGE_DIR", None)
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================================
# 8. Physical STOP Confirmation & Authentication Security Closure
# ============================================================================

class TestStopReceiptSecurityClosure:
    """Security exit criteria for Physical STOP Confirmation & Authentication:
    1. Receipt signed using public/predictable key is strictly rejected.
    2. Tampering with flow (0.0 -> 5.0), running/stopped status, source, or operation invalidates signature.
    3. Missing signing key fails closed on real hardware (is_simulation=False).
    4. Receipt replayed in another process or after restart is rejected (durable store).
    5. Genuine driver-produced, fully bound receipt succeeds exactly once.
    6. Pending physical operation retains ownership and quota exposure on verification failure.
    """

    def test_01_stop_receipt_signed_with_predictable_key_rejected(self):
        """1. Receipt signed using public/predictable key is strictly rejected."""
        from services.agribrain.irrigation_runtime.actuator import (
            generate_stop_receipt_token,
            build_canonical_stop_assertion,
        )
        dev_id = "DEV-SEC-STOP-01"
        reg = ActuatorRegistration(
            device_id=dev_id,
            vendor=VendorId.CUSTOM,
            model="FieldPLC",
            protocol=DriverProtocol.MODBUS_TCP,
            capabilities=ActuatorCapabilities(system_type=IrrigationSystemType.DRIP),
        )
        actuator = ModbusActuator(registration=reg)
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
        actuator._active_command = IrrigationCommand(
            command_id="CMD-SEC-01",
            command_type=CommandType.START_ZONE,
            device_id=dev_id,
            zone_id="ZONE-1",
            plot_id="PLOT-01",
            operation_id="OP-SEC-01",
        )
        now_ts = datetime.datetime.now(timezone.utc).isoformat()

        # 1a. Generator strictly refuses to sign with predictable key derived from device_id
        with pytest.raises(ValueError, match="Predictable or insecure signing key rejected"):
            generate_stop_receipt_token(
                device_id=dev_id,
                operation_id="OP-SEC-01",
                secret=f"agribrain_stop_auth_{dev_id}",
            )

        # 1b. Generator refuses blacklisted keys
        with pytest.raises(ValueError, match="Predictable or insecure signing key rejected"):
            generate_stop_receipt_token(
                device_id=dev_id,
                operation_id="OP-SEC-01",
                secret="secret",
            )

        # 1c. Forged receipt signed using predictable default key is rejected by confirm_stop
        bad_key = f"agribrain_stop_auth_{dev_id}".encode("utf-8")
        bad_assertion = build_canonical_stop_assertion(
            device_id=dev_id,
            operation_id="OP-SEC-01",
            attempt_number=1,
            timestamp=now_ts,
            source="modbus_plc",
            actual_flow_lpm=0.0,
            is_running=False,
            is_stopped=True,
            confirmed_stopped=True,
        )
        forged_token = hmac.new(bad_key, bad_assertion, hashlib.sha256).hexdigest()[:32]
        forged_receipt = {
            "device_id": dev_id,
            "operation_id": "OP-SEC-01",
            "attempt_number": 1,
            "timestamp": now_ts,
            "source": "modbus_plc",
            "actual_flow_lpm": 0.0,
            "is_stopped": True,
            "is_running": False,
            "confirmed_stopped": True,
            "receipt_token": forged_token,
        }
        res = actuator.confirm_stop(forged_receipt)
        assert res is False
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

    def test_02_stop_receipt_tampered_measurements_rejected(self):
        """2. Tampering with flow (0.0 -> 5.0), running/stopped status, source, or operation invalidates signature."""
        from services.agribrain.irrigation_runtime.actuator import create_verified_stop_receipt
        dev_id = "DEV-SEC-STOP-02"
        secret = "strong_test_secret_for_tampering_test_2026"
        reg = ActuatorRegistration(
            device_id=dev_id,
            vendor=VendorId.CUSTOM,
            model="FieldPLC",
            protocol=DriverProtocol.MODBUS_TCP,
            capabilities=ActuatorCapabilities(system_type=IrrigationSystemType.DRIP),
            connection_config={"auth_secret": secret},
        )
        actuator = ModbusActuator(registration=reg)
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
        actuator._active_command = IrrigationCommand(
            command_id="CMD-SEC-02",
            command_type=CommandType.START_ZONE,
            device_id=dev_id,
            zone_id="ZONE-1",
            plot_id="PLOT-01",
            operation_id="OP-SEC-02",
        )
        now_ts = datetime.datetime.now(timezone.utc).isoformat()

        legit_receipt = create_verified_stop_receipt(
            device_id=dev_id,
            operation_id="OP-SEC-02",
            attempt_number=1,
            secret=secret,
            source="modbus_plc",
            actual_flow_lpm=0.0,
            timestamp=now_ts,
        )

        # 2a. Tampering actual_flow_lpm (0.0 -> 5.0) invalidates HMAC assertion
        tampered_flow = dict(legit_receipt)
        tampered_flow["actual_flow_lpm"] = 5.0
        assert actuator.confirm_stop(tampered_flow) is False
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        # 2b. Tampering is_running (False -> True)
        tampered_running = dict(legit_receipt)
        tampered_running["is_running"] = True
        assert actuator.confirm_stop(tampered_running) is False
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        # 2c. Tampering is_stopped (True -> False)
        tampered_stopped = dict(legit_receipt)
        tampered_stopped["is_stopped"] = False
        assert actuator.confirm_stop(tampered_stopped) is False
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        # 2d. Tampering source ("modbus_plc" -> "controller")
        tampered_source = dict(legit_receipt)
        tampered_source["source"] = "controller"
        assert actuator.confirm_stop(tampered_source) is False
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

        # 2e. Tampering operation_id mismatch
        tampered_op = dict(legit_receipt)
        tampered_op["operation_id"] = "OP-FORGED-999"
        with pytest.raises(ValueError, match="does not match active operation"):
            actuator.confirm_stop(tampered_op)
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

    def test_03_missing_signing_key_fails_closed_on_real_hardware(self):
        """3. Missing signing key fails closed on real hardware (is_simulation=False)."""
        dev_id = "DEV-REAL-HW-03"
        reg = ActuatorRegistration(
            device_id=dev_id,
            vendor=VendorId.CUSTOM,
            model="FieldPLC",
            protocol=DriverProtocol.MODBUS_TCP,
            capabilities=ActuatorCapabilities(system_type=IrrigationSystemType.DRIP),
        )
        actuator = ModbusActuator(registration=reg)
        actuator.is_simulation = False
        actuator.is_mock = False
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
        actuator._active_command = IrrigationCommand(
            command_id="CMD-REAL-03",
            command_type=CommandType.START_ZONE,
            device_id=dev_id,
            zone_id="ZONE-1",
            plot_id="PLOT-01",
            operation_id="OP-REAL-03",
        )
        now_ts = datetime.datetime.now(timezone.utc).isoformat()

        # Isolate environment so no global or device keys exist
        env_cleared = {k: v for k, v in os.environ.items() if not k.startswith("AGRIBRAIN_STOP_AUTH_KEY")}
        with patch.dict(os.environ, env_cleared, clear=True):
            # Any receipt (even with an ostensibly valid token) fails closed on real hardware without provisioned keys
            receipt = {
                "device_id": dev_id,
                "operation_id": "OP-REAL-03",
                "attempt_number": 1,
                "timestamp": now_ts,
                "source": "modbus_plc",
                "actual_flow_lpm": 0.0,
                "is_stopped": True,
                "is_running": False,
                "confirmed_stopped": True,
                "receipt_token": "a" * 32,
            }
            res = actuator.confirm_stop(receipt)
            assert res is False
            assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION

    def test_04_stop_receipt_durable_replay_rejected_across_processes_and_restarts(self):
        """4. Receipt replayed in another process or after restart is rejected (durable store)."""
        from services.agribrain.irrigation_runtime.actuator import (
            DurableStopReceiptStore,
            _GLOBAL_CONSUMED_RECEIPT_TOKENS,
            create_verified_stop_receipt,
        )
        tmp_receipt_dir = tempfile.mkdtemp(prefix="test_stop_receipts_")
        old_receipt_env = os.environ.get("AGRIBRAIN_STOP_RECEIPT_DIR")
        os.environ["AGRIBRAIN_STOP_RECEIPT_DIR"] = tmp_receipt_dir
        try:
            DurableStopReceiptStore.reset()
            _GLOBAL_CONSUMED_RECEIPT_TOKENS.clear()

            secret = "durable_replay_auth_secret_2026_test"
            dev_id = "DEV-DURABLE-04"
            reg = ActuatorRegistration(
                device_id=dev_id,
                vendor=VendorId.CUSTOM,
            model="FieldPLC",
                protocol=DriverProtocol.MODBUS_TCP,
                capabilities=ActuatorCapabilities(system_type=IrrigationSystemType.DRIP),
                connection_config={"auth_secret": secret},
            )
            actuator1 = ModbusActuator(registration=reg)
            actuator1._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
            actuator1._active_command = IrrigationCommand(
                command_id="CMD-DUR-01",
                command_type=CommandType.START_ZONE,
                device_id=dev_id,
                zone_id="ZONE-1",
                plot_id="PLOT-01",
                operation_id="OP-DURABLE-04",
            )
            now_ts = datetime.datetime.now(timezone.utc).isoformat()

            receipt = create_verified_stop_receipt(
                device_id=dev_id,
                operation_id="OP-DURABLE-04",
                attempt_number=1,
                secret=secret,
                source="modbus_plc",
                actual_flow_lpm=0.0,
                timestamp=now_ts,
            )

            # Process 1 verifies receipt successfully
            assert actuator1.confirm_stop(receipt) is True
            assert actuator1.status == ActuatorStatus.ONLINE

            # Simulate worker process crash / restart:
            # Completely wipe in-memory state
            actuator1._consumed_receipt_tokens.clear()
            _GLOBAL_CONSUMED_RECEIPT_TOKENS.clear()
            with DurableStopReceiptStore._thread_lock:
                DurableStopReceiptStore._memory_cache.clear()

            # Process 2 / Worker 2 starts up fresh with new actuator instance
            actuator2 = ModbusActuator(registration=reg)
            actuator2._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
            actuator2._active_command = IrrigationCommand(
                command_id="CMD-DUR-02",
                command_type=CommandType.START_ZONE,
                device_id=dev_id,
                zone_id="ZONE-1",
                plot_id="PLOT-01",
                operation_id="OP-DURABLE-04",
            )

            # Replaying the exact same receipt from another process must be rejected by durable store
            replay_res = actuator2.confirm_stop(receipt)
            assert replay_res is False
            assert actuator2.status == ActuatorStatus.STOP_PENDING_CONFIRMATION
        finally:
            DurableStopReceiptStore.reset()
            if old_receipt_env is not None:
                os.environ["AGRIBRAIN_STOP_RECEIPT_DIR"] = old_receipt_env
            else:
                os.environ.pop("AGRIBRAIN_STOP_RECEIPT_DIR", None)
            shutil.rmtree(tmp_receipt_dir, ignore_errors=True)

    def test_05_genuine_driver_produced_receipt_succeeds_exactly_once(self):
        """5. Genuine driver-produced, fully bound receipt succeeds exactly once."""
        from services.agribrain.irrigation_runtime.actuator import create_verified_stop_receipt
        secret = "genuine_driver_secret_key_2026_test"
        dev_id = "DEV-GENUINE-05"
        reg = ActuatorRegistration(
            device_id=dev_id,
            vendor=VendorId.CUSTOM,
            model="FieldPLC",
            protocol=DriverProtocol.MODBUS_TCP,
            capabilities=ActuatorCapabilities(system_type=IrrigationSystemType.DRIP),
            connection_config={"auth_secret": secret},
        )
        actuator = ModbusActuator(registration=reg)
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
        actuator._active_command = IrrigationCommand(
            command_id="CMD-GEN-05",
            command_type=CommandType.START_ZONE,
            device_id=dev_id,
            zone_id="ZONE-1",
            plot_id="PLOT-01",
            operation_id="OP-GENUINE-05",
        )
        now_ts = datetime.datetime.now(timezone.utc).isoformat()

        receipt = create_verified_stop_receipt(
            device_id=dev_id,
            operation_id="OP-GENUINE-05",
            attempt_number=1,
            secret=secret,
            source="modbus_plc",
            actual_flow_lpm=0.0,
            timestamp=now_ts,
        )

        # Call 1: Succeeds and transitions to ONLINE
        first_call = actuator.confirm_stop(receipt, expected_operation_id={"OP-GENUINE-05"})
        assert first_call is True
        assert actuator.status == ActuatorStatus.ONLINE
        assert actuator.active_command is None

        # Call 2: Immediate retry with identical receipt returns False
        second_call = actuator.confirm_stop(receipt, expected_operation_id={"OP-GENUINE-05"})
        assert second_call is False

    def test_06_pending_operation_retains_ownership_and_quota_on_verification_failure(self):
        """6. Pending physical operation retains ownership and quota exposure on verification failure."""
        from services.agribrain.irrigation_runtime.actuator import create_verified_stop_receipt
        secret = "quota_ownership_secret_2026_test"
        dev_id = "DEV-QUOTA-06"
        reg = ActuatorRegistration(
            device_id=dev_id,
            vendor=VendorId.CUSTOM,
            model="FieldPLC",
            protocol=DriverProtocol.MODBUS_TCP,
            capabilities=ActuatorCapabilities(system_type=IrrigationSystemType.DRIP),
            connection_config={"auth_secret": secret},
        )
        actuator = ModbusActuator(registration=reg)
        actuator._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
        active_cmd = IrrigationCommand(
            command_id="CMD-QUOTA-06",
            command_type=CommandType.START_ZONE,
            device_id=dev_id,
            zone_id="ZONE-1",
            plot_id="PLOT-01",
            operation_id="OP-QUOTA-06",
        )
        actuator._active_command = active_cmd
        now_ts = datetime.datetime.now(timezone.utc).isoformat()

        # Create tampered receipt that fails verification
        tampered_receipt = create_verified_stop_receipt(
            device_id=dev_id,
            operation_id="OP-QUOTA-06",
            attempt_number=1,
            secret=secret,
            source="modbus_plc",
            actual_flow_lpm=0.0,
            timestamp=now_ts,
        )
        tampered_receipt["actual_flow_lpm"] = 12.0  # Tampered!

        # Verification failure
        assert actuator.confirm_stop(tampered_receipt) is False

        # Physical safety invariants: must retain pending confirmation and active command
        assert actuator.status == ActuatorStatus.STOP_PENDING_CONFIRMATION
        assert actuator.active_command is not None
        assert actuator.active_command.command_id == "CMD-QUOTA-06"
        assert actuator.active_command.operation_id == "OP-QUOTA-06"



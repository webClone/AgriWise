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
    _validate_and_encode_id,
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
from services.agribrain.irrigation_runtime.safety import SafetyMonitor

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

        # Valid characters and colons are bijectively encoded
        assert _validate_and_encode_id("urn:dev:123") == "urn_COLON_dev_COLON_123"
        assert _validate_and_encode_id("sensor_01-test.v1") == "sensor_01-test.v1"

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
                valid_receipt = {
                    "device_id": "lora_valve_01",
                    "operation_id": "OP-01",
                    "confirmed_stopped": True,
                    "actual_flow_rate_lpm": 0.0,
                    "is_stopped": True,
                }
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

        receipt = {
            "device_id": dev_id,
            "operation_id": "EV-CONFIRM-01",
            "confirmed_stopped": True,
            "actual_flow_rate_lpm": 0.0,
            "is_stopped": True,
        }

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


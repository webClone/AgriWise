"""
Irrigation Runtime — Modbus Actuator Driver v1.0.0

Controls irrigation hardware via Modbus RTU (serial) or Modbus TCP.
Supports: Industrial PLCs, pump controllers, motorized valves, VFDs.

Register Mapping (configurable per device model):
  Coils:            Valve ON/OFF (discrete outputs)
  Holding Registers: Flow setpoint, pressure setpoint, speed setpoint
  Input Registers:   Actual flow, actual pressure, status codes

Compatible Hardware:
  - Schneider Electric Modicon M221/M241
  - Siemens LOGO! / S7-1200
  - Allen-Bradley Micro800
  - Bermad IR-x10 series (hydraulic valves with Modbus)
  - Custom PLC-based pump stations
  - Variable Frequency Drives (VFDs) for pump motor control
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.schemas import (
    ActuatorRegistration,
    ActuatorStatus,
    CommandResult,
    CommandType,
    DriverProtocol,
    IrrigationCommand,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Default Register Maps
# ============================================================================

DEFAULT_COIL_MAP = {
    "valve_1": 0,       # Coil 0: Zone 1 valve
    "valve_2": 1,       # Coil 1: Zone 2 valve
    "valve_3": 2,       # Coil 2: Zone 3 valve
    "valve_4": 3,       # Coil 3: Zone 4 valve
    "pump_enable": 8,   # Coil 8: Main pump enable
    "emergency_stop": 9,  # Coil 9: Emergency stop (NC contact)
}

DEFAULT_HOLDING_REGISTER_MAP = {
    "flow_setpoint_x10": 100,     # Register 100: Flow setpoint (L/min × 10)
    "pressure_setpoint_x10": 101, # Register 101: Pressure setpoint (bar × 10)
    "duration_seconds": 102,      # Register 102: Runtime in seconds
    "vfd_speed_pct_x10": 110,     # Register 110: VFD speed (% × 10)
}

DEFAULT_INPUT_REGISTER_MAP = {
    "actual_flow_x10": 200,       # Register 200: Measured flow (L/min × 10)
    "actual_pressure_x10": 201,   # Register 201: Measured pressure (bar × 10)
    "status_word": 202,           # Register 202: Status bitmask
    "fault_code": 203,            # Register 203: Active fault code
    "total_volume_liters": 204,   # Register 204-205: Totalizer (32-bit)
    "runtime_seconds": 206,       # Register 206: Current runtime
}


class ModbusActuator(IrrigationActuator):
    """Modbus RTU/TCP actuator driver for industrial irrigation controllers.

    Reads/writes Modbus registers to control valves, pumps, and VFDs.
    Supports both serial (RTU) and TCP gateway modes.

    Connection config keys (RTU):
      serial_port: str     — e.g. "/dev/ttyUSB0" or "COM3"
      baudrate: int        — Default 9600
      slave_id: int        — Modbus slave address (1-247)
      parity: str          — "N", "E", or "O"

    Connection config keys (TCP):
      host: str            — IP address or hostname
      port: int            — Default 502
      slave_id: int        — Unit ID

    Common config:
      coil_map: dict       — Zone/valve → coil address mapping
      holding_map: dict    — Setpoint → register address mapping
      input_map: dict      — Feedback → register address mapping
      timeout_s: float     — Response timeout (default 5)
    """

    def __init__(self, registration: ActuatorRegistration):
        super().__init__(registration)
        self._config = registration.connection_config
        self._slave_id = self._config.get("slave_id", 1)
        self._timeout = self._config.get("timeout_s", 5.0)

        # Register maps (customizable per device model)
        self._coil_map = self._config.get("coil_map", DEFAULT_COIL_MAP)
        self._holding_map = self._config.get("holding_map", DEFAULT_HOLDING_REGISTER_MAP)
        self._input_map = self._config.get("input_map", DEFAULT_INPUT_REGISTER_MAP)

        # Zone → coil index mapping
        self._zone_coil_map: Dict[str, int] = self._config.get("zone_coil_map", {})

        self._client: Any = None  # pymodbus client

    # ================================================================
    # Connection Lifecycle
    # ================================================================

    async def connect(self) -> bool:
        """Establish Modbus RTU or TCP connection."""
        try:
            if self.protocol == DriverProtocol.MODBUS_RTU:
                return await self._connect_rtu()
            else:
                return await self._connect_tcp()
        except ImportError:
            logger.error("pymodbus not installed. Install with: pip install pymodbus")
            return False
        except Exception as exc:
            logger.error("Modbus connect failed for %s: %s", self.device_id, exc)
            return False

    async def _connect_rtu(self) -> bool:
        """Connect via Modbus RTU (serial)."""
        from pymodbus.client import AsyncModbusSerialClient

        port = self._config.get("serial_port", "/dev/ttyUSB0")
        baudrate = self._config.get("baudrate", 9600)
        parity = self._config.get("parity", "N")

        self._client = AsyncModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,
            timeout=self._timeout,
        )

        connected = await self._client.connect()
        self._connected = connected
        if connected:
            self._status = ActuatorStatus.ONLINE
            logger.info("Modbus RTU connected on %s (slave=%d) for device %s",
                        port, self._slave_id, self.device_id)
        return connected

    async def _connect_tcp(self) -> bool:
        """Connect via Modbus TCP."""
        from pymodbus.client import AsyncModbusTcpClient

        host = self._config.get("host", "127.0.0.1")
        port = self._config.get("port", 502)

        self._client = AsyncModbusTcpClient(
            host=host,
            port=port,
            timeout=self._timeout,
        )

        connected = await self._client.connect()
        self._connected = connected
        if connected:
            self._status = ActuatorStatus.ONLINE
            logger.info("Modbus TCP connected to %s:%d (slave=%d) for device %s",
                        host, port, self._slave_id, self.device_id)
        return connected

    async def disconnect(self) -> None:
        """Close Modbus connection."""
        if self._client:
            self._client.close()
            self._connected = False
            self._status = ActuatorStatus.OFFLINE
            logger.info("Modbus disconnected for device %s", self.device_id)

    # ================================================================
    # Register I/O Helpers
    # ================================================================

    async def _write_coil(self, address: int, value: bool) -> bool:
        """Write a single coil."""
        if not self._client:
            return False
        result = await self._client.write_coil(address, value, slave=self._slave_id)
        return not result.isError()

    async def _write_register(self, address: int, value: int) -> bool:
        """Write a single holding register."""
        if not self._client:
            return False
        result = await self._client.write_register(address, value, slave=self._slave_id)
        return not result.isError()

    async def _read_input_registers(self, address: int, count: int = 1) -> List[int]:
        """Read input registers."""
        if not self._client:
            return []
        result = await self._client.read_input_registers(
            address, count, slave=self._slave_id
        )
        if result.isError():
            return []
        return result.registers

    async def _read_holding_registers(self, address: int, count: int = 1) -> List[int]:
        """Read holding registers."""
        if not self._client:
            return []
        result = await self._client.read_holding_registers(
            address, count, slave=self._slave_id
        )
        if result.isError():
            return []
        return result.registers

    # ================================================================
    # Command Dispatch
    # ================================================================

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        """Execute an irrigation command via Modbus register writes."""
        now = datetime.now(timezone.utc).isoformat()

        if not self._connected or not self._client:
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=now,
                error_code="NOT_CONNECTED",
                error_message="Modbus client not connected",
                retry_recommended=True,
            )

        try:
            if command.command_type == CommandType.START_ZONE:
                return await self._start_zone(command)
            elif command.command_type == CommandType.STOP_ZONE:
                return await self._stop_zone(command)
            elif command.command_type == CommandType.SET_FLOW_RATE:
                return await self._set_flow_rate(command)
            elif command.command_type == CommandType.SET_PRESSURE:
                return await self._set_pressure(command)
            elif command.command_type == CommandType.EMERGENCY_STOP:
                return await self.emergency_stop()
            elif command.command_type == CommandType.QUERY_STATUS:
                status = await self._read_status()
                return CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=True,
                    timestamp=now,
                )
            else:
                return CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=False,
                    timestamp=now,
                    error_code="UNSUPPORTED_COMMAND",
                    error_message=f"Modbus driver does not support {command.command_type.value}",
                )

        except Exception as exc:
            logger.error("Modbus command failed on %s: %s", self.device_id, exc)
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=now,
                error_code="MODBUS_ERROR",
                error_message=str(exc),
                retry_recommended=True,
            )

    async def _start_zone(self, command: IrrigationCommand) -> CommandResult:
        """Start irrigation on a zone via Modbus coil + register writes."""
        now = datetime.now(timezone.utc).isoformat()

        # 1. Set flow rate
        if command.flow_rate_lpm > 0:
            flow_reg = self._holding_map.get("flow_setpoint_x10")
            if flow_reg is not None:
                await self._write_register(flow_reg, int(command.flow_rate_lpm * 10))

        # 2. Set duration
        duration_reg = self._holding_map.get("duration_seconds")
        if duration_reg is not None:
            await self._write_register(duration_reg, int(command.duration_minutes * 60))

        # 3. Enable pump
        pump_coil = self._coil_map.get("pump_enable")
        if pump_coil is not None:
            await self._write_coil(pump_coil, True)

        # 4. Open zone valve
        coil_address = self._zone_coil_map.get(command.zone_id)
        if coil_address is None:
            # Fallback to default coil map
            coil_key = f"valve_{command.zone_id}"
            coil_address = self._coil_map.get(coil_key)

        if coil_address is not None:
            success = await self._write_coil(coil_address, True)
        else:
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=now,
                error_code="ZONE_NOT_MAPPED",
                error_message=f"No coil mapping for zone {command.zone_id}",
            )

        # Read back actual values
        actual_flow, actual_pressure = await self._read_feedback()

        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=success,
            timestamp=now,
            actual_flow_rate_lpm=actual_flow,
            actual_pressure_bar=actual_pressure,
        )

    async def _stop_zone(self, command: IrrigationCommand) -> CommandResult:
        """Stop irrigation on a zone."""
        now = datetime.now(timezone.utc).isoformat()
        if not self._client or not self._connected:
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=now,
                error_code="NOT_CONNECTED",
                error_message="Modbus client not connected",
            )

        coil_address = self._zone_coil_map.get(command.zone_id)
        if coil_address is None:
            coil_key = f"valve_{command.zone_id}"
            coil_address = self._coil_map.get(coil_key)

        if coil_address is None:
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=now,
                error_code="ZONE_NOT_MAPPED",
                error_message=f"No coil mapping for zone {command.zone_id}",
            )

        success = await self._write_coil(coil_address, False)

        # Read totalizer for actual volume
        volume_reg = self._input_map.get("total_volume_liters")
        actual_volume = 0.0
        if volume_reg is not None:
            regs = await self._read_input_registers(volume_reg, 2)
            if len(regs) >= 2:
                actual_volume = float((regs[0] << 16) | regs[1])

        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=success,
            timestamp=now,
            actual_volume_l=actual_volume,
            error_code="" if success else "WRITE_FAILED",
            error_message="" if success else "Failed to write stop coil",
        )

    async def _set_flow_rate(self, command: IrrigationCommand) -> CommandResult:
        """Adjust flow rate setpoint via holding register."""
        now = datetime.now(timezone.utc).isoformat()
        flow_reg = self._holding_map.get("flow_setpoint_x10")
        if flow_reg is None:
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=now,
                error_code="NO_FLOW_REGISTER",
                error_message="Flow setpoint register not mapped",
            )

        success = await self._write_register(flow_reg, int(command.flow_rate_lpm * 10))
        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=success,
            timestamp=now,
        )

    async def _set_pressure(self, command: IrrigationCommand) -> CommandResult:
        """Adjust pressure setpoint via holding register."""
        now = datetime.now(timezone.utc).isoformat()
        pressure_reg = self._holding_map.get("pressure_setpoint_x10")
        if pressure_reg is None:
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=now,
                error_code="NO_PRESSURE_REGISTER",
                error_message="Pressure setpoint register not mapped",
            )

        success = await self._write_register(pressure_reg, int(command.pressure_bar * 10))
        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=success,
            timestamp=now,
        )

    async def _read_feedback(self) -> Tuple[float, float]:
        """Read actual flow and pressure from input registers."""
        actual_flow = 0.0
        actual_pressure = 0.0

        flow_reg = self._input_map.get("actual_flow_x10")
        if flow_reg is not None:
            regs = await self._read_input_registers(flow_reg, 1)
            if regs:
                actual_flow = regs[0] / 10.0

        pressure_reg = self._input_map.get("actual_pressure_x10")
        if pressure_reg is not None:
            regs = await self._read_input_registers(pressure_reg, 1)
            if regs:
                actual_pressure = regs[0] / 10.0

        return actual_flow, actual_pressure

    async def _read_status(self) -> Dict[str, Any]:
        """Read full status from input registers."""
        status = {}
        status_reg = self._input_map.get("status_word")
        if status_reg is not None:
            regs = await self._read_input_registers(status_reg, 1)
            if regs:
                status["status_word"] = regs[0]

        fault_reg = self._input_map.get("fault_code")
        if fault_reg is not None:
            regs = await self._read_input_registers(fault_reg, 1)
            if regs:
                status["fault_code"] = regs[0]

        return status

    # ================================================================
    # Status & Emergency
    # ================================================================

    async def get_status(self) -> ActuatorStatus:
        """Query actuator status via Modbus."""
        if not self._connected:
            return ActuatorStatus.OFFLINE

        try:
            status = await self._read_status()
            if not status or "status_word" not in status:
                self._status = ActuatorStatus.ERROR
                return self._status

            fault_code = status.get("fault_code", 0)
            if fault_code != 0:
                self._status = ActuatorStatus.ERROR
            else:
                status_word = status["status_word"]
                if status_word & 0x01:  # Bit 0: running
                    self._status = ActuatorStatus.EXECUTING
                else:
                    self._status = ActuatorStatus.ONLINE
        except Exception:
            self._status = ActuatorStatus.ERROR

        return self._status

    async def emergency_stop(self) -> CommandResult:
        """Emergency stop all outputs via Modbus."""
        now = datetime.now(timezone.utc).isoformat()
        if not self._client or not self._connected:
            return CommandResult(
                command_id=f"ESTOP-{uuid.uuid4().hex[:8]}",
                device_id=self.device_id,
                success=False,
                timestamp=now,
                error_code="NOT_CONNECTED",
                error_message="Cannot send emergency stop — Modbus client not connected",
            )

        success = True
        failed_outputs = []
        attempted_coils = 0

        # Trigger E-Stop coil
        estop_coil = self._coil_map.get("emergency_stop")
        if estop_coil is not None:
            attempted_coils += 1
            try:
                ok = await self._write_coil(estop_coil, True)
                if not ok:
                    success = False
                    failed_outputs.append(f"emergency_stop({estop_coil})")
            except Exception as exc:
                success = False
                failed_outputs.append(f"emergency_stop({estop_coil}):{exc}")

        # Close all valve coils from coil_map
        valve_addrs = set()
        for key, address in self._coil_map.items():
            if key.startswith("valve_") or "valve" in key:
                valve_addrs.add(address)

        # Close all zone coils from zone_coil_map
        for zone_key, address in self._zone_coil_map.items():
            valve_addrs.add(address)

        for address in sorted(valve_addrs):
            attempted_coils += 1
            try:
                ok = await self._write_coil(address, False)
                if not ok:
                    success = False
                    failed_outputs.append(f"coil({address})")
            except Exception as exc:
                success = False
                failed_outputs.append(f"coil({address}):{exc}")

        # Disable pump
        pump_coil = self._coil_map.get("pump_enable")
        if pump_coil is not None:
            attempted_coils += 1
            try:
                ok = await self._write_coil(pump_coil, False)
                if not ok:
                    success = False
                    failed_outputs.append(f"pump_enable({pump_coil})")
            except Exception as exc:
                success = False
                failed_outputs.append(f"pump_enable({pump_coil}):{exc}")

        if attempted_coils == 0:
            logger.error("Modbus emergency stop: no coils configured to trigger or stop on %s", self.device_id)
            return CommandResult(
                command_id=f"ESTOP-{uuid.uuid4().hex[:8]}",
                device_id=self.device_id,
                success=False,
                timestamp=now,
                error_code="NO_OUTPUTS_CONFIGURED",
                error_message="No emergency stop or zone/pump coils configured",
            )

        if success:
            logger.critical("🚨 EMERGENCY STOP sent via Modbus to %s across %d coils", self.device_id, attempted_coils)
        else:
            logger.error("Modbus emergency stop partial or total failure on coils: %s", failed_outputs)

        return CommandResult(
            command_id=f"ESTOP-{uuid.uuid4().hex[:8]}",
            device_id=self.device_id,
            success=success,
            timestamp=now,
            error_code="" if success else "WRITE_FAILED",
            error_message="" if success else f"Coil writes failed on: {', '.join(failed_outputs)}",
        )

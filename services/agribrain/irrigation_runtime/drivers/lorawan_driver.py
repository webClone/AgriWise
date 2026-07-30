"""
Irrigation Runtime — LoRaWAN Actuator Driver v1.0.0

Controls low-power irrigation hardware via LoRaWAN Class C downlinks.
Integrates with ChirpStack and The Things Network (TTN) APIs.

Payload Format (compact binary, 8 bytes):
  Byte 0:    Command ID (0x01=START, 0x02=STOP, 0xFF=ESTOP)
  Byte 1:    Zone index (0-15)
  Byte 2-3:  Duration (seconds, big-endian uint16)
  Byte 4-5:  Flow setpoint (L/min × 10, big-endian uint16)
  Byte 6:    Priority (0=LOW, 1=NORMAL, 2=HIGH, 3=CRITICAL)
  Byte 7:    Checksum (XOR of bytes 0-6)

fPort Routing:
  fPort 10:  Irrigation commands
  fPort 11:  Configuration updates
  fPort 20:  Status requests

Compatible Hardware: Dragino LDS02 (valve), custom LoRa valve nodes,
                     TEKTELIC Agricultural sensors with relay output
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import struct
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.schemas import (
    ActuatorRegistration,
    ActuatorStatus,
    CommandResult,
    CommandType,
    IrrigationCommand,
)

logger = logging.getLogger(__name__)


# Command byte mapping
LORA_CMD_MAP = {
    CommandType.START_ZONE: 0x01,
    CommandType.STOP_ZONE: 0x02,
    CommandType.SET_FLOW_RATE: 0x03,
    CommandType.PULSE_IRRIGATE: 0x04,
    CommandType.QUERY_STATUS: 0x05,
    CommandType.EMERGENCY_STOP: 0xFF,
}


class LoRaWANActuator(IrrigationActuator):
    """LoRaWAN Class C downlink driver for low-power field valves.

    Sends compact binary payloads via network server downlink API.
    Supports confirmed downlinks with retry logic.

    Connection config keys:
      network_server: str      — "chirpstack" or "ttn"
      api_url: str             — Network server API endpoint
      api_key: str             — API key / token
      application_id: str      — LoRaWAN application ID
      dev_eui: str             — Device EUI (DevEUI)
      confirmed: bool          — Use confirmed downlinks (default True)
      fport: int               — Default fPort for commands (default 10)
      timeout_s: int           — Downlink ACK timeout (default 60)
      max_retries: int         — Max downlink retries (default 2)
    """

    def __init__(self, registration: ActuatorRegistration):
        super().__init__(registration)
        self._config = registration.connection_config
        self._network_server = self._config.get("network_server", "chirpstack")
        self._api_url = self._config.get("api_url", "")
        self._api_key = self._config.get("api_key", "")
        self._app_id = self._config.get("application_id", "")
        self._dev_eui = self._config.get("dev_eui", registration.device_id)
        self._confirmed = self._config.get("confirmed", True)
        self._fport = self._config.get("fport", 10)
        self._timeout = self._config.get("timeout_s", 60)
        self._max_retries = self._config.get("max_retries", 2)

    # ================================================================
    # Payload Encoding
    # ================================================================

    @staticmethod
    def encode_command(
        cmd_type: CommandType,
        zone_index: int = 0,
        duration_seconds: int = 0,
        flow_rate_x10: int = 0,
        priority: int = 1,
    ) -> bytes:
        """Encode a command into compact binary LoRaWAN payload.

        Returns 8-byte payload with XOR checksum.
        """
        cmd_byte = LORA_CMD_MAP.get(cmd_type, 0x00)

        payload = struct.pack(
            ">BBHHB",
            cmd_byte,
            zone_index & 0x0F,
            duration_seconds & 0xFFFF,
            flow_rate_x10 & 0xFFFF,
            priority & 0x03,
        )

        # XOR checksum
        checksum = 0
        for b in payload:
            checksum ^= b
        payload += struct.pack("B", checksum)

        return payload

    @staticmethod
    def decode_status(payload: bytes) -> Dict[str, Any]:
        """Decode a status uplink payload from the device.

        Expected format (6 bytes):
          Byte 0:    Status (0=IDLE, 1=RUNNING, 2=ERROR, 3=OFFLINE)
          Byte 1:    Active zone (0-15, 0xFF=none)
          Byte 2-3:  Remaining seconds (big-endian uint16)
          Byte 4:    Battery % (0-100)
          Byte 5:    Fault code (0=OK)
        """
        if len(payload) < 6:
            return {"error": "Payload too short"}

        status_byte, zone, remaining_s, battery, fault = struct.unpack(
            ">BBHBB", payload[:6]
        )

        status_map = {0: "IDLE", 1: "RUNNING", 2: "ERROR", 3: "OFFLINE"}

        return {
            "status": status_map.get(status_byte, "UNKNOWN"),
            "active_zone": zone if zone != 0xFF else None,
            "remaining_seconds": remaining_s,
            "battery_pct": battery,
            "fault_code": fault,
        }

    # ================================================================
    # Network Server API
    # ================================================================

    async def _send_downlink(
        self,
        payload: bytes,
        fport: int = 10,
        confirmed: bool = True,
    ) -> Dict[str, Any]:
        """Send a downlink via the LoRaWAN network server API.

        Supports ChirpStack and TTN v3 APIs.
        """
        try:
            import aiohttp
        except ImportError:
            logger.error("aiohttp not installed. Install with: pip install aiohttp")
            return {"success": False, "error": "aiohttp not installed"}

        b64_payload = base64.b64encode(payload).decode("ascii")

        if self._network_server == "chirpstack":
            url = f"{self._api_url}/api/devices/{self._dev_eui}/queue"
            body = {
                "queueItem": {
                    "data": b64_payload,
                    "fPort": fport,
                    "confirmed": confirmed,
                }
            }
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
        elif self._network_server == "ttn":
            url = (
                f"{self._api_url}/api/v3/as/applications/"
                f"{self._app_id}/devices/{self._dev_eui}/down/push"
            )
            body = {
                "downlinks": [{
                    "frm_payload": b64_payload,
                    "f_port": fport,
                    "confirmed": confirmed,
                    "priority": "NORMAL",
                }]
            }
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
        else:
            return {"success": False, "error": f"Unknown network server: {self._network_server}"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status in (200, 201):
                        result = await resp.json()
                        return {"success": True, "response": result}
                    else:
                        error_text = await resp.text()
                        return {"success": False, "error": f"HTTP {resp.status}: {error_text}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ================================================================
    # Connection Lifecycle
    # ================================================================

    async def connect(self) -> bool:
        """Verify connectivity with the LoRaWAN network server."""
        if not self._api_url or not self._api_key:
            logger.error("LoRaWAN API URL or key not configured for %s", self.device_id)
            return False

        # Test connectivity by querying device status
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                if self._network_server == "chirpstack":
                    url = f"{self._api_url}/api/devices/{self._dev_eui}"
                    headers = {"Authorization": f"Bearer {self._api_key}"}
                else:
                    url = f"{self._api_url}/api/v3/as/applications/{self._app_id}/devices/{self._dev_eui}"
                    headers = {"Authorization": f"Bearer {self._api_key}"}

                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        self._connected = True
                        self._status = ActuatorStatus.ONLINE
                        logger.info("LoRaWAN device %s verified on %s",
                                    self._dev_eui, self._network_server)
                        return True
                    else:
                        logger.warning("LoRaWAN device %s not found (HTTP %d)",
                                       self._dev_eui, resp.status)
                        return False
        except Exception as exc:
            logger.error("LoRaWAN connectivity check failed: %s", exc)
            return False

    async def disconnect(self) -> None:
        """No persistent connection for LoRaWAN — just mark offline."""
        self._connected = False
        self._status = ActuatorStatus.OFFLINE

    # ================================================================
    # Command Dispatch
    # ================================================================

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        """Encode and send command via LoRaWAN downlink."""
        now = datetime.now(timezone.utc).isoformat()

        # Resolve zone index (zone_id → integer index for binary payload)
        zone_index = self._resolve_zone_index(command.zone_id)

        # Priority mapping
        priority_map = {"LOW": 0, "NORMAL": 1, "HIGH": 2, "CRITICAL": 3, "EMERGENCY": 3}
        priority_int = priority_map.get(command.priority.value, 1)

        # Encode binary payload
        payload = self.encode_command(
            cmd_type=command.command_type,
            zone_index=zone_index,
            duration_seconds=int(command.duration_minutes * 60),
            flow_rate_x10=int(command.flow_rate_lpm * 10),
            priority=priority_int,
        )

        # Send with retry
        last_error = ""
        for attempt in range(self._max_retries + 1):
            result = await self._send_downlink(
                payload,
                fport=self._fport,
                confirmed=self._confirmed,
            )

            if result.get("success"):
                logger.info(
                    "LoRaWAN downlink queued for %s (cmd=%s, zone=%d, attempt=%d)",
                    self._dev_eui, command.command_type.value, zone_index, attempt + 1
                )
                return CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=True,
                    timestamp=now,
                )

            last_error = result.get("error", "Unknown")
            logger.warning(
                "LoRaWAN downlink attempt %d/%d failed for %s: %s",
                attempt + 1, self._max_retries + 1, self._dev_eui, last_error
            )
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=False,
            timestamp=now,
            error_code="DOWNLINK_FAILED",
            error_message=f"All {self._max_retries + 1} attempts failed: {last_error}",
            retry_recommended=False,
        )

    def _resolve_zone_index(self, zone_id: str) -> int:
        """Map zone_id string to integer index for binary payload."""
        zone_map = self._config.get("zone_index_map", {})
        if zone_id in zone_map:
            return zone_map[zone_id]
        # Try extracting number from zone_id
        try:
            return int("".join(filter(str.isdigit, zone_id))) % 16
        except ValueError:
            return 0

    # ================================================================
    # Status & Emergency
    # ================================================================

    async def get_status(self) -> ActuatorStatus:
        """Query status — LoRaWAN is stateless, return cached status."""
        return self._status

    async def emergency_stop(self) -> CommandResult:
        """Send emergency stop downlink (0xFF command byte)."""
        payload = self.encode_command(
            cmd_type=CommandType.EMERGENCY_STOP,
            zone_index=0xFF,  # All zones
        )

        result = await self._send_downlink(payload, fport=self._fport, confirmed=False)

        logger.critical("🚨 EMERGENCY STOP sent via LoRaWAN to %s", self._dev_eui)

        return CommandResult(
            command_id=f"ESTOP-{uuid.uuid4().hex[:8]}",
            device_id=self.device_id,
            success=result.get("success", False),
            timestamp=datetime.now(timezone.utc).isoformat(),
            error_message=result.get("error", ""),
        )

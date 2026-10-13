"""
Irrigation Runtime — MQTT Actuator Driver v1.0.0

Controls irrigation hardware via MQTT publish/subscribe.
Supports: WiFi/Ethernet solenoid controllers, smart valves, pump relays.

Topic Convention:
  Command:  agriwise/{farm_id}/{device_id}/cmd
  Status:   agriwise/{farm_id}/{device_id}/status
  Telemetry: agriwise/{farm_id}/{device_id}/telemetry

Message Format (JSON):
  {
    "request_id": "...",
    "cmd": "START_ZONE",
    "zone": "zone_a",
    "duration_s": 3600,
    "flow_lpm": 12.5,
    "volume_mm": 25.0,
    "priority": "NORMAL"
  }

Compatible Vendors: Hunter HC, Rain Bird ESP-ME3, Galcon GSI,
                    Baccara G75, custom ESP32/Arduino controllers
"""

from __future__ import annotations

import asyncio
import json
import logging
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


class MQTTActuator(IrrigationActuator):
    """MQTT-based irrigation actuator driver.

    Publishes JSON commands to device-specific topics and subscribes
    to status/ACK topics for confirmation. Supports QoS 1 for
    guaranteed delivery.

    Connection config keys:
      broker: str          — MQTT broker hostname
      port: int            — Broker port (default 1883)
      username: str        — Auth username (optional)
      password: str        — Auth password (optional)
      tls: bool            — Use TLS (default False)
      qos: int             — QoS level (default 1)
      timeout_s: int       — ACK timeout in seconds (default 30)
      topic_prefix: str    — Override topic prefix (default "agriwise")
    """

    def __init__(self, registration: ActuatorRegistration):
        super().__init__(registration)
        self._config = registration.connection_config
        self._broker = self._config.get("broker", "localhost")
        self._port = self._config.get("port", 1883)
        self._username = self._config.get("username")
        self._password = self._config.get("password")
        self._use_tls = self._config.get("tls", False)
        self._qos = self._config.get("qos", 1)
        self._timeout = self._config.get("timeout_s", 30)
        self._prefix = self._config.get("topic_prefix", "agriwise")

        self._client: Any = None  # paho.mqtt.client.Client
        self._pending_acks: Dict[str, asyncio.Future] = {}
        self._last_status_payload: Dict[str, Any] = {}

    # ================================================================
    # Topic Helpers
    # ================================================================

    @property
    def _cmd_topic(self) -> str:
        return f"{self._prefix}/{self.registration.farm_id}/{self.device_id}/cmd"

    @property
    def _status_topic(self) -> str:
        return f"{self._prefix}/{self.registration.farm_id}/{self.device_id}/status"

    @property
    def _telemetry_topic(self) -> str:
        return f"{self._prefix}/{self.registration.farm_id}/{self.device_id}/telemetry"

    # ================================================================
    # Connection Lifecycle
    # ================================================================

    async def connect(self) -> bool:
        """Establish MQTT connection to the broker.

        Sets up subscriptions to status and telemetry topics.
        """
        try:
            # Import paho-mqtt lazily to avoid hard dependency
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client(
                client_id=f"agriwise-irr-{self.device_id}",
                protocol=mqtt.MQTTv5,
            )

            if self._username:
                self._client.username_pw_set(self._username, self._password)

            if self._use_tls:
                self._client.tls_set()

            # Callbacks
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect

            self._client.connect_async(self._broker, self._port, keepalive=60)
            self._client.loop_start()

            # Wait for connection
            await asyncio.sleep(2)

            if self._connected:
                self._status = ActuatorStatus.ONLINE
                logger.info("MQTT connected to %s:%d for device %s",
                            self._broker, self._port, self.device_id)
                return True
            else:
                logger.warning("MQTT connection timeout for device %s",
                               self.device_id)
                return False

        except ImportError:
            logger.error("paho-mqtt not installed. Install with: pip install paho-mqtt")
            return False
        except Exception as exc:
            logger.error("MQTT connect failed for %s: %s", self.device_id, exc)
            return False

    async def disconnect(self) -> None:
        """Gracefully disconnect from MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            self._status = ActuatorStatus.OFFLINE
            logger.info("MQTT disconnected for device %s", self.device_id)

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """MQTT on_connect callback."""
        if rc == 0:
            self._connected = True
            # Subscribe to status and telemetry
            client.subscribe(self._status_topic, qos=self._qos)
            client.subscribe(self._telemetry_topic, qos=self._qos)
            logger.debug("MQTT subscribed to %s, %s",
                         self._status_topic, self._telemetry_topic)
        else:
            self._connected = False
            logger.error("MQTT connect failed with rc=%d for %s", rc, self.device_id)

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """MQTT on_disconnect callback."""
        self._connected = False
        if rc != 0:
            self._status = ActuatorStatus.OFFLINE
            logger.warning("MQTT unexpected disconnect for %s (rc=%d)",
                           self.device_id, rc)

    def _on_message(self, client, userdata, msg):
        """MQTT message handler for status/telemetry responses."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Invalid MQTT payload from %s", msg.topic)
            return

        if msg.topic == self._status_topic:
            self._handle_status(payload)
        elif msg.topic == self._telemetry_topic:
            self._handle_telemetry(payload)

    def _handle_status(self, payload: Dict[str, Any]):
        """Process actuator status response."""
        self._last_status_payload = payload
        self._last_heartbeat = datetime.now(timezone.utc)

        # Check for ACK to pending command
        request_id = payload.get("request_id")
        if request_id and request_id in self._pending_acks:
            future = self._pending_acks.pop(request_id)
            if not future.done():
                future.set_result(payload)

    def _handle_telemetry(self, payload: Dict[str, Any]):
        """Process telemetry data from the actuator."""
        # Store latest telemetry for safety monitoring
        self._last_status_payload.update(payload)

    # ================================================================
    # Command Dispatch
    # ================================================================

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        """Publish an irrigation command via MQTT and wait for ACK."""
        if not self._connected or not self._client:
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_code="NOT_CONNECTED",
                error_message="MQTT client not connected",
                retry_recommended=True,
            )

        request_id = command.request_id or str(uuid.uuid4())

        # Build MQTT command payload
        mqtt_payload = {
            "request_id": request_id,
            "cmd": command.command_type.value,
            "zone": command.zone_id,
            "duration_s": int(command.duration_minutes * 60),
            "flow_lpm": round(command.flow_rate_lpm, 2),
            "volume_mm": round(command.volume_mm, 2),
            "pressure_bar": round(command.pressure_bar, 2),
            "priority": command.priority.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Pulse irrigation parameters
        if command.command_type == CommandType.PULSE_IRRIGATE:
            mqtt_payload["pulse_on_s"] = int(command.pulse_on_minutes * 60)
            mqtt_payload["pulse_off_s"] = int(command.pulse_off_minutes * 60)
            mqtt_payload["pulse_cycles"] = command.pulse_cycles

        # Pivot parameters
        if command.command_type in (CommandType.SET_PIVOT_SPEED, CommandType.SET_PIVOT_ANGLE):
            mqtt_payload["pivot_speed_pct"] = command.pivot_speed_pct
            mqtt_payload["pivot_start_deg"] = command.pivot_start_angle_deg
            mqtt_payload["pivot_end_deg"] = command.pivot_end_angle_deg

        # Create ACK future
        ack_future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_acks[request_id] = ack_future

        # Publish command
        payload_json = json.dumps(mqtt_payload)
        result = self._client.publish(
            self._cmd_topic, payload_json, qos=self._qos
        )

        if result.rc != 0:
            self._pending_acks.pop(request_id, None)
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_code="PUBLISH_FAILED",
                error_message=f"MQTT publish failed with rc={result.rc}",
                retry_recommended=True,
            )

        logger.debug("Published to %s: %s", self._cmd_topic, payload_json)

        # Wait for ACK with timeout
        try:
            ack_payload = await asyncio.wait_for(ack_future, timeout=self._timeout)
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=ack_payload.get("status") == "OK",
                timestamp=datetime.now(timezone.utc).isoformat(),
                actual_flow_rate_lpm=ack_payload.get("actual_flow_lpm", 0.0),
                actual_pressure_bar=ack_payload.get("actual_pressure_bar", 0.0),
                error_code=ack_payload.get("error_code", ""),
                error_message=ack_payload.get("error_message", ""),
                ack_latency_ms=ack_payload.get("ack_latency_ms", 0),
            )
        except asyncio.TimeoutError:
            self._pending_acks.pop(request_id, None)
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_code="ACK_TIMEOUT",
                error_message=f"No ACK received within {self._timeout}s",
                retry_recommended=True,
            )

    # ================================================================
    # Status & Emergency
    # ================================================================

    def _decode_status_payload(self, payload: Dict[str, Any]) -> ActuatorStatus:
        """Decode status/ACK payload from MQTT controller.

        Distinguishes operational execution, idle/stopped confirmation, and error/fault conditions.
        Contradictions or indeterminate states map to UNKNOWN or ERROR.
        """
        if not isinstance(payload, dict):
            return ActuatorStatus.UNKNOWN

        raw_status = str(payload.get("status", "")).upper()
        is_running = payload.get("running")
        is_stopped = payload.get("stopped")
        fault_code = payload.get("fault_code", 0)

        # Fault / Error check
        if raw_status in ("ERROR", "FAULT", "FAILED") or (isinstance(fault_code, (int, float)) and fault_code != 0):
            return ActuatorStatus.ERROR

        # Running flag takes precedence for active execution
        if is_running is True:
            return ActuatorStatus.EXECUTING

        # Explicit stopped confirmation without running
        if is_stopped is True and is_running is not True:
            return ActuatorStatus.ONLINE

        if raw_status in ("EXECUTING", "RUNNING", "BUSY"):
            return ActuatorStatus.EXECUTING

        if raw_status in ("STOPPED", "IDLE"):
            if is_stopped is False or is_running is True:
                return ActuatorStatus.EXECUTING if is_running is True else ActuatorStatus.UNKNOWN
            return ActuatorStatus.ONLINE

        if raw_status == "ONLINE":
            if is_running is True or is_stopped is False:
                return ActuatorStatus.EXECUTING if is_running is True else ActuatorStatus.UNKNOWN
            return ActuatorStatus.ONLINE

        # Generic OK / ACK status without explicit stopped / running
        if raw_status in ("OK", "ACK"):
            if is_running is False and is_stopped is not False:
                return ActuatorStatus.ONLINE
            return ActuatorStatus.UNKNOWN

        return ActuatorStatus.UNKNOWN

    async def get_status(self) -> ActuatorStatus:
        """Query actuator status via MQTT."""
        if not self._connected:
            return ActuatorStatus.OFFLINE

        # Publish status request
        if self._client:
            req_id = str(uuid.uuid4())
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            ack_future: asyncio.Future = loop.create_future()
            self._pending_acks[req_id] = ack_future
            self._client.publish(
                self._cmd_topic,
                json.dumps({"cmd": "QUERY_STATUS", "request_id": req_id}),
                qos=self._qos,
            )
            query_timeout = float(self._config.get("query_timeout_s", 0.1))
            try:
                ack_payload = await asyncio.wait_for(ack_future, timeout=query_timeout)
                self._status = self._decode_status_payload(ack_payload)
                return self._status
            except asyncio.TimeoutError:
                self._pending_acks.pop(req_id, None)
                self._status = ActuatorStatus.UNKNOWN
                return ActuatorStatus.UNKNOWN

        return self._status

    async def emergency_stop(self) -> CommandResult:
        """Send emergency stop command via MQTT and await controller confirmation."""
        request_id = str(uuid.uuid4())
        payload = json.dumps({
            "request_id": request_id,
            "cmd": "EMERGENCY_STOP",
            "priority": "EMERGENCY",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        if not self._client or not self._connected:
            return CommandResult(
                command_id=f"ESTOP-{request_id[:8]}",
                device_id=self.device_id,
                success=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_code="NOT_CONNECTED",
                error_message="Cannot send emergency stop — MQTT disconnected",
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        ack_future: asyncio.Future = loop.create_future()
        self._pending_acks[request_id] = ack_future

        try:
            # Fire-and-forget at QoS 0 for speed
            r0 = self._client.publish(self._cmd_topic, payload, qos=0)
            # Also send at QoS 1 for reliability
            r1 = self._client.publish(self._cmd_topic, payload, qos=1)

            rc0 = getattr(r0, "rc", -1) if r0 is not None else -1
            rc1 = getattr(r1, "rc", -1) if r1 is not None else -1
            if rc0 != 0 and rc1 != 0:
                self._pending_acks.pop(request_id, None)
                logger.error("🚨 EMERGENCY STOP publish failed on both QoS 0 (rc=%s) and QoS 1 (rc=%s)", rc0, rc1)
                return CommandResult(
                    command_id=f"ESTOP-{request_id[:8]}",
                    device_id=self.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="PUBLISH_FAILED",
                    error_message=f"MQTT publish failed: rc0={rc0}, rc1={rc1}",
                )

            logger.critical("🚨 EMERGENCY STOP published to %s via MQTT (awaiting confirmation)", self.device_id)

            stop_timeout = float(self._config.get("stop_timeout_s", 0.1))
            try:
                ack_payload = await asyncio.wait_for(ack_future, timeout=stop_timeout)
                # SR01: Qualified stop validation:
                # Contradictory check: if running=True or stopped=False, controller is NOT confirmed stopped!
                is_running = ack_payload.get("running")
                is_stopped = ack_payload.get("stopped")
                raw_status = str(ack_payload.get("status", "")).upper()

                if is_running is True or is_stopped is False:
                    logger.error(
                        "🚨 EMERGENCY STOP rejected or contradictory: running=%s, stopped=%s on %s (payload=%s)",
                        is_running, is_stopped, self.device_id, ack_payload
                    )
                    self._status = ActuatorStatus.EXECUTING if is_running is True else ActuatorStatus.UNKNOWN
                    return CommandResult(
                        command_id=f"ESTOP-{request_id[:8]}",
                        device_id=self.device_id,
                        success=False,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        error_code="CONTROLLER_STILL_RUNNING",
                        error_message=f"Controller reported still running or not stopped: {ack_payload}",
                    )

                # Positive stopped confirmation
                is_ok = (is_stopped is True) or (raw_status in ("STOPPED", "IDLE")) or (raw_status == "OK" and is_running is False)
                if not is_ok:
                    logger.error("🚨 EMERGENCY STOP not confirmed by controller on %s: payload=%s", self.device_id, ack_payload)
                    self._status = ActuatorStatus.ERROR
                    return CommandResult(
                        command_id=f"ESTOP-{request_id[:8]}",
                        device_id=self.device_id,
                        success=False,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        error_code="CONTROLLER_REJECTED",
                        error_message=f"Controller rejected STOP: {ack_payload}",
                    )

                self._status = ActuatorStatus.ONLINE
                return CommandResult(
                    command_id=f"ESTOP-{request_id[:8]}",
                    device_id=self.device_id,
                    success=True,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            except asyncio.TimeoutError:
                self._pending_acks.pop(request_id, None)
                logger.warning("🚨 EMERGENCY STOP publish accepted but no controller ACK received within %ss", stop_timeout)
                return CommandResult(
                    command_id=f"ESTOP-{request_id[:8]}",
                    device_id=self.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="ACK_TIMEOUT",
                    error_message=f"No STOP ACK received from controller within {stop_timeout}s",
                )
        except Exception as exc:
            self._pending_acks.pop(request_id, None)
            logger.error("🚨 EMERGENCY STOP exception on device %s: %s", self.device_id, exc)
            return CommandResult(
                command_id=f"ESTOP-{request_id[:8]}",
                device_id=self.device_id,
                success=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_code="EXCEPTION",
                error_message=str(exc),
            )

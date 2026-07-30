"""
DJI Cloud API — MQTT Bridge.

Protocol-level client for DJI Cloud API communication.
Handles all MQTT concerns:
  - Connect / disconnect / reconnect with backoff
  - Topic subscription (services_reply, events, osd)
  - Command publishing with transaction ID correlation
  - Request-response matching with timeouts
  - TLS support

This is a protocol layer — no DJI business logic lives here.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import json
import logging
import threading
import time
import uuid

from .dji_config import DJICloudConfig

logger = logging.getLogger(__name__)


@dataclass
class MQTTMessage:
    """A received MQTT message."""
    topic: str
    payload: Dict[str, Any]
    timestamp: float = 0.0


@dataclass
class PendingRequest:
    """A command waiting for a reply."""
    tid: str
    method: str
    sent_at: float
    timeout_s: float
    reply: Optional[Dict[str, Any]] = None
    completed: bool = False
    event: threading.Event = field(default_factory=threading.Event)


class MQTTBridge:
    """MQTT client wrapper for DJI Cloud API.
    
    Abstracts all MQTT protocol concerns. The DJI driver calls
    high-level methods like send_command() and subscribe_telemetry()
    without dealing with raw MQTT.
    
    Supports two modes:
    - Real mode: uses paho-mqtt to connect to a broker
    - Sim mode:  uses an in-process message bus (for testing)
    """
    
    def __init__(self, config: DJICloudConfig, sim_bus: Optional[Any] = None):
        self._config = config
        self._sim_bus = sim_bus
        self._connected = False
        self._pending: Dict[str, PendingRequest] = {}
        self._listeners: Dict[str, List[Callable]] = {}
        self._telemetry_callbacks: List[Callable] = []
        self._event_callbacks: List[Callable] = []
        self._client = None
        self._lock = threading.Lock()
    
    @property
    def connected(self) -> bool:
        return self._connected
    
    # ====================================================================
    # Connection
    # ====================================================================
    
    def connect(self) -> bool:
        """Connect to MQTT broker.
        
        Returns True on successful connection.
        """
        if self._sim_bus is not None:
            return self._connect_sim()
        return self._connect_real()
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self._sim_bus is not None:
            self._connected = False
            self._sim_bus.unregister_client(self._config.mqtt_client_id)
            return
        
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._connected = False
    
    def _connect_real(self) -> bool:
        """Connect using paho-mqtt."""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("[MQTTBridge] paho-mqtt not installed. Install with: pip install paho-mqtt")
            return False
        
        try:
            self._client = mqtt.Client(
                client_id=self._config.mqtt_client_id,
                protocol=mqtt.MQTTv5,
            )
            
            if self._config.mqtt_username:
                self._client.username_pw_set(
                    self._config.mqtt_username,
                    self._config.mqtt_password,
                )
            
            if self._config.mqtt_tls:
                self._client.tls_set()
            
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect
            
            self._client.connect(
                self._config.mqtt_host,
                self._config.mqtt_port,
                keepalive=60,
            )
            self._client.loop_start()
            
            # Wait for connection
            deadline = time.time() + self._config.connect_timeout_s
            while not self._connected and time.time() < deadline:
                time.sleep(0.1)
            
            return self._connected
        
        except Exception as e:
            logger.error(f"[MQTTBridge] Connection failed: {e}")
            return False
    
    def _connect_sim(self) -> bool:
        """Connect using in-process simulation bus."""
        self._sim_bus.register_client(
            self._config.mqtt_client_id,
            self._on_sim_message,
        )
        self._connected = True
        
        # Subscribe to reply/events/osd topics
        self._sim_bus.subscribe(
            self._config.mqtt_client_id,
            self._config.services_reply_topic,
        )
        self._sim_bus.subscribe(
            self._config.mqtt_client_id,
            self._config.events_topic,
        )
        self._sim_bus.subscribe(
            self._config.mqtt_client_id,
            self._config.osd_topic,
        )
        
        logger.info(f"[MQTTBridge] Connected to sim bus as {self._config.mqtt_client_id}")
        return True
    
    # ====================================================================
    # Command sending
    # ====================================================================
    
    def send_command(
        self,
        method: str,
        data: Dict[str, Any],
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Send a command and wait for the reply.
        
        Args:
            method: DJI service method (e.g., "flighttask_prepare")
            data: Command payload
            timeout_s: Reply timeout (uses config default if None)
            
        Returns:
            Reply payload dict. Contains "result" key with status code.
            Returns {"result": -1, "error": "..."} on timeout/error.
        """
        tid = uuid.uuid4().hex[:16]
        timeout = timeout_s or self._config.command_timeout_s
        
        payload = {
            "tid": tid,
            "bid": uuid.uuid4().hex[:16],
            "method": method,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        
        # Register pending request
        pending = PendingRequest(
            tid=tid,
            method=method,
            sent_at=time.time(),
            timeout_s=timeout,
        )
        with self._lock:
            self._pending[tid] = pending
        
        # Publish
        topic = self._config.services_topic
        self._publish(topic, payload)
        
        # Wait for reply
        pending.event.wait(timeout=timeout)
        
        with self._lock:
            self._pending.pop(tid, None)
        
        if pending.completed and pending.reply is not None:
            return pending.reply
        
        return {
            "result": -1,
            "error": f"Timeout waiting for reply to {method} (tid={tid})",
        }
    
    def send_fire_and_forget(self, method: str, data: Dict[str, Any]):
        """Send a command without waiting for reply."""
        payload = {
            "tid": uuid.uuid4().hex[:16],
            "bid": uuid.uuid4().hex[:16],
            "method": method,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        self._publish(self._config.services_topic, payload)
    
    # ====================================================================
    # Subscriptions
    # ====================================================================
    
    def on_telemetry(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback for OSD telemetry data."""
        self._telemetry_callbacks.append(callback)
    
    def on_event(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback for device events."""
        self._event_callbacks.append(callback)
    
    # ====================================================================
    # Internal MQTT handlers
    # ====================================================================
    
    def _publish(self, topic: str, payload: Dict[str, Any]):
        """Publish a JSON message to a topic."""
        msg = json.dumps(payload)
        
        if self._sim_bus is not None:
            self._sim_bus.publish(self._config.mqtt_client_id, topic, payload)
            return
        
        if self._client is not None:
            self._client.publish(topic, msg)
    
    def _on_connect(self, client, userdata, flags, rc, *args):
        """paho-mqtt connect callback."""
        if rc == 0:
            self._connected = True
            # Subscribe to required topics
            client.subscribe(self._config.services_reply_topic)
            client.subscribe(self._config.events_topic)
            client.subscribe(self._config.osd_topic)
            logger.info("[MQTTBridge] Connected to broker")
        else:
            logger.error(f"[MQTTBridge] Connection refused: rc={rc}")
    
    def _on_disconnect(self, client, userdata, rc, *args):
        """paho-mqtt disconnect callback."""
        self._connected = False
        if rc != 0:
            logger.warning(f"[MQTTBridge] Unexpected disconnect: rc={rc}")
    
    def _on_message(self, client, userdata, msg):
        """paho-mqtt message callback."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            self._dispatch_message(msg.topic, payload)
        except Exception as e:
            logger.error(f"[MQTTBridge] Message parse error: {e}")
    
    def _on_sim_message(self, topic: str, payload: Dict[str, Any]):
        """Simulation bus message callback."""
        self._dispatch_message(topic, payload)
    
    def _dispatch_message(self, topic: str, payload: Dict[str, Any]):
        """Route an incoming message to the right handler."""
        # Service replies (command ack)
        if topic == self._config.services_reply_topic:
            tid = payload.get("tid", "")
            with self._lock:
                pending = self._pending.get(tid)
            if pending:
                pending.reply = payload
                pending.completed = True
                pending.event.set()
            return
        
        # OSD telemetry
        if topic == self._config.osd_topic or "osd" in topic:
            for cb in self._telemetry_callbacks:
                try:
                    cb(payload)
                except Exception as e:
                    logger.error(f"[MQTTBridge] Telemetry callback error: {e}")
            return
        
        # Events
        if topic == self._config.events_topic or "events" in topic:
            for cb in self._event_callbacks:
                try:
                    cb(payload)
                except Exception as e:
                    logger.error(f"[MQTTBridge] Event callback error: {e}")

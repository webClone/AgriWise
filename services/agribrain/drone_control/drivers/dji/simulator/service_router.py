"""
DJI Cloud Gateway Simulator — Service Router.

In-process MQTT message bus that replaces a real broker for testing.
Clients register, subscribe to topics, and the bus routes messages.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Set
import logging
import threading

logger = logging.getLogger(__name__)


class SimMessageBus:
    """In-process MQTT-like message bus for DJI Cloud API testing.
    
    Replaces a real MQTT broker (Mosquitto/EMQX) for unit and
    integration testing. Supports:
    - Client registration
    - Topic subscription
    - Synchronous message delivery
    - Wildcard-free topic matching (exact match only)
    """
    
    def __init__(self):
        self._clients: Dict[str, Callable] = {}           # client_id → callback
        self._subscriptions: Dict[str, Set[str]] = {}     # topic → set of client_ids
        self._lock = threading.Lock()
    
    def register_client(self, client_id: str, callback: Callable):
        """Register a client with its message callback."""
        with self._lock:
            self._clients[client_id] = callback
    
    def unregister_client(self, client_id: str):
        """Remove a client."""
        with self._lock:
            self._clients.pop(client_id, None)
            for topic_subs in self._subscriptions.values():
                topic_subs.discard(client_id)
    
    def subscribe(self, client_id: str, topic: str):
        """Subscribe a client to a topic."""
        with self._lock:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = set()
            self._subscriptions[topic].add(client_id)
    
    def publish(self, sender_id: str, topic: str, payload: Dict[str, Any]):
        """Publish a message. Delivered to all subscribers except sender."""
        with self._lock:
            subscribers = set(self._subscriptions.get(topic, set()))
        
        for client_id in subscribers:
            if client_id == sender_id:
                continue
            with self._lock:
                callback = self._clients.get(client_id)
            if callback:
                try:
                    callback(topic, payload)
                except Exception as e:
                    logger.error(f"[SimBus] Delivery error to {client_id}: {e}")
    
    def publish_to_all(self, topic: str, payload: Dict[str, Any]):
        """Publish to all subscribers (no sender filter)."""
        with self._lock:
            subscribers = set(self._subscriptions.get(topic, set()))
        
        for client_id in subscribers:
            with self._lock:
                callback = self._clients.get(client_id)
            if callback:
                try:
                    callback(topic, payload)
                except Exception as e:
                    logger.error(f"[SimBus] Delivery error to {client_id}: {e}")

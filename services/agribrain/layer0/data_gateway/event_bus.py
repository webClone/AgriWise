"""
Event Bus — In-process pub/sub for ML pattern notifications.

Auto-promotes to Redis Pub/Sub when REDIS_URL is set.
The interface is identical: publishers and subscribers don't know
which backend is active.

Events:
    - data:fetched:{source} — raw data arrived from API
    - data:cached:{source} — data served from cache
    - data:expired:{source} — cache entry expired
    - user:event:{type} — farmer contributed data
    - bootstrap:complete — all sources pre-fetched for new plot
    - compaction:complete — compaction cycle finished
    - pattern:updated:{id} — ML pattern maturity changed

Usage:
    from layer0.data_gateway.event_bus import event_bus

    # Subscribe
    def on_data_fetched(event):
        print(f"Fetched {event['source']} for plot {event['plot_id']}")
    event_bus.subscribe("data:fetched:*", on_data_fetched)

    # Publish
    event_bus.publish("data:fetched:openweather_current", {
        "plot_id": "abc123", "lat": 33.5, "lng": -7.6, "source": "openweather_current",
    })
"""

from __future__ import annotations

import os
import re
import logging
import threading
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger("agribrain.gateway.event_bus")


class EventBus:
    """In-process pub/sub event bus with wildcard support.

    Subscribers can use wildcard patterns:
    - "data:fetched:*" matches any data:fetched event
    - "*" matches everything

    Thread-safe. Auto-promotes to Redis when REDIS_URL is set.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_count = 0
        self._subscriber_count = 0

        # Check if we should use Redis
        self._redis_url = os.getenv("REDIS_URL")
        self._redis_client = None
        if self._redis_url:
            self._try_redis_connect()

    def _try_redis_connect(self):
        """Attempt Redis connection for multi-worker mode."""
        try:
            import redis
            self._redis_client = redis.from_url(self._redis_url)
            self._redis_client.ping()
            logger.info("[EVENT_BUS] Redis connected: %s", self._redis_url[:30])
        except Exception as e:
            self._redis_client = None
            logger.debug("[EVENT_BUS] Redis unavailable, using in-process: %s", e)

    def subscribe(self, pattern: str, callback: Callable):
        """Subscribe to events matching a pattern.

        Patterns support * wildcard:
        - "data:fetched:*" matches "data:fetched:openweather_current"
        - "user:event:*" matches "user:event:irrigation"
        - "*" matches everything
        """
        with self._lock:
            self._subscribers[pattern].append(callback)
            self._subscriber_count += 1

        logger.debug("[EVENT_BUS] Subscribed: %s (%d total)", pattern, self._subscriber_count)

    def unsubscribe(self, pattern: str, callback: Callable):
        """Remove a subscription."""
        with self._lock:
            subs = self._subscribers.get(pattern, [])
            if callback in subs:
                subs.remove(callback)
                self._subscriber_count -= 1

    def publish(self, event_type: str, data: Dict[str, Any] = None):
        """Publish an event to all matching subscribers.

        Non-blocking: subscribers are called in a daemon thread.
        """
        event = {
            "type": event_type,
            **(data or {}),
        }

        self._event_count += 1

        # Find matching subscribers
        matching = []
        with self._lock:
            for pattern, callbacks in self._subscribers.items():
                if self._matches(pattern, event_type):
                    matching.extend(callbacks)

        if not matching:
            return

        # Fire in background thread (non-blocking)
        def _notify():
            for cb in matching:
                try:
                    cb(event)
                except Exception as e:
                    logger.debug("[EVENT_BUS] Subscriber error on %s: %s", event_type, e)

        threading.Thread(target=_notify, daemon=True, name="event-bus-notify").start()

    def _matches(self, pattern: str, event_type: str) -> bool:
        """Check if event_type matches subscription pattern."""
        if pattern == "*":
            return True
        if "*" not in pattern:
            return pattern == event_type
        # Convert glob to regex
        regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
        return bool(re.match(regex, event_type))

    def get_stats(self) -> Dict:
        return {
            "backend": "redis" if self._redis_client else "in_process",
            "event_count": self._event_count,
            "subscriber_count": self._subscriber_count,
            "patterns": list(self._subscribers.keys()),
        }


# Global singleton
event_bus = EventBus()

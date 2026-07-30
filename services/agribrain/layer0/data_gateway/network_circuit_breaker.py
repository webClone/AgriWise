"""Process-wide external-provider DNS/network circuit breaker.

The data gateway fans a single plot request out to several providers. During a
machine-wide DNS outage those calls are not independent failures, so one shared
cooldown suppresses repeated requests and repeated connection stacks.
"""

from __future__ import annotations

import socket
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Optional


DNS_FAILURE_MARKERS = (
    "getaddrinfo failed",
    "failed to resolve",
    "name resolution",
    "nameresolutionerror",
    "temporary failure in name resolution",
)


def _exception_chain(error: BaseException):
    current: Optional[BaseException] = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def is_dns_failure(error: BaseException) -> bool:
    for item in _exception_chain(error):
        if isinstance(item, socket.gaierror):
            return True
        message = str(item).lower()
        if any(marker in message for marker in DNS_FAILURE_MARKERS):
            return True
    return False


class ExternalProviderCircuitOpen(ConnectionError):
    def __init__(self, state: Dict[str, Any]):
        self.state = state
        super().__init__(
            "External provider circuit open: network DNS unavailable; "
            f"retry in {state['retry_after_seconds']}s"
        )


class ExternalProviderCircuitBreaker:
    def __init__(self, cooldown_seconds: int = 60, threshold: int = 2):
        self._cooldown_seconds = max(1, cooldown_seconds)
        self._threshold = max(1, threshold)
        self._lock = threading.RLock()
        self._dns_failures: Deque[float] = deque(maxlen=8)
        self._open_until = 0.0
        self._last_failure_at: Optional[float] = None
        self._last_failure_source: Optional[str] = None
        self._last_successful_provider_data_available = False

    def before_request(self, source: str) -> None:
        del source
        with self._lock:
            now = time.monotonic()
            if self._open_until > now:
                raise ExternalProviderCircuitOpen(self.state())
            if self._open_until:
                self._open_until = 0.0
                self._dns_failures.clear()

    def record_failure(self, error: BaseException, source: str) -> bool:
        if not is_dns_failure(error):
            return False
        with self._lock:
            now = time.monotonic()
            self._dns_failures.append(now)
            self._last_failure_at = time.time()
            self._last_failure_source = source
            recent = [stamp for stamp in self._dns_failures if now - stamp <= 10.0]
            if len(recent) >= self._threshold:
                self._open_until = max(self._open_until, now + self._cooldown_seconds)
            return True

    def record_success(self, source: str) -> None:
        del source
        with self._lock:
            if not self._open_until:
                self._dns_failures.clear()

    def record_cache_available(self) -> None:
        with self._lock:
            self._last_successful_provider_data_available = True

    def state(self) -> Dict[str, Any]:
        with self._lock:
            remaining = max(0, int(self._open_until - time.monotonic() + 0.999))
            return {
                "failure_class": "network_dns_unavailable" if remaining else None,
                "scope": "external_providers",
                "retry_after_seconds": remaining,
                "last_successful_provider_data_available": self._last_successful_provider_data_available,
                "last_failure_at": self._last_failure_at,
                "last_failure_source": self._last_failure_source,
                "circuit_open": remaining > 0,
            }

    def reset(self) -> None:
        """Reset process state; intended for controlled verification only."""
        with self._lock:
            self._dns_failures.clear()
            self._open_until = 0.0
            self._last_failure_at = None
            self._last_failure_source = None
            self._last_successful_provider_data_available = False


external_provider_circuit = ExternalProviderCircuitBreaker()

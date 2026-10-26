"""
Irrigation Runtime — HTTP/REST Actuator Driver v1.0.0

Controls cloud-connected irrigation hardware via vendor REST APIs.
Supports: Center pivots, linear move systems, smart controllers.

Compatible Vendors:
  - Lindsay FieldNET (center pivots)
  - Valley ICON Link (pivots + linears)
  - Netafim NetBeat (precision drip)
  - Hunter Hydrawise (residential/commercial sprinklers)
  - Rain Bird ESP-RZXe (WiFi sprinkler controllers)
  - Toro Sentinel (commercial controllers)
  - Galcon Cloud (drip/sprinkler)

Authentication: OAuth2 Bearer, API Key, Basic Auth (per vendor)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.schemas import (
    ActuatorRegistration,
    ActuatorStatus,
    CommandResult,
    CommandType,
    IrrigationCommand,
    VendorId,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Vendor API Endpoint Templates
# ============================================================================

VENDOR_API_TEMPLATES: Dict[str, Dict[str, str]] = {
    VendorId.LINDSAY.value: {
        "base_url": "https://api.fieldnet.com/v2",
        "start": "/devices/{device_id}/zones/{zone_id}/start",
        "stop": "/devices/{device_id}/zones/{zone_id}/stop",
        "status": "/devices/{device_id}/status",
        "auth_type": "oauth2",
    },
    VendorId.VALLEY.value: {
        "base_url": "https://api.valleyirrigation.com/v1",
        "start": "/pivots/{device_id}/run",
        "stop": "/pivots/{device_id}/stop",
        "status": "/pivots/{device_id}/status",
        "auth_type": "api_key",
    },
    VendorId.NETAFIM.value: {
        "base_url": "https://api.netbeat.netafim.com/v1",
        "start": "/controllers/{device_id}/programs/{zone_id}/activate",
        "stop": "/controllers/{device_id}/programs/{zone_id}/deactivate",
        "status": "/controllers/{device_id}/status",
        "auth_type": "oauth2",
    },
    VendorId.HUNTER.value: {
        "base_url": "https://api.hydrawise.com/api/v2",
        "start": "/zones/{zone_id}/run",
        "stop": "/zones/{zone_id}/stop",
        "status": "/controllers/{device_id}/status",
        "auth_type": "api_key",
    },
    VendorId.RAIN_BIRD.value: {
        "base_url": "https://api.rainbird.com/v1",
        "start": "/controllers/{device_id}/zones/{zone_id}/start",
        "stop": "/controllers/{device_id}/zones/{zone_id}/stop",
        "status": "/controllers/{device_id}",
        "auth_type": "api_key",
    },
    VendorId.TORO.value: {
        "base_url": "https://api.toro-ag.com/v1",
        "start": "/sites/{device_id}/stations/{zone_id}/run",
        "stop": "/sites/{device_id}/stations/{zone_id}/stop",
        "status": "/sites/{device_id}/status",
        "auth_type": "api_key",
    },
    VendorId.GALCON.value: {
        "base_url": "https://cloud.galcon.com/api/v2",
        "start": "/units/{device_id}/outputs/{zone_id}/on",
        "stop": "/units/{device_id}/outputs/{zone_id}/off",
        "status": "/units/{device_id}",
        "auth_type": "api_key",
    },
}


class HTTPActuator(IrrigationActuator):
    """HTTP/REST actuator driver for cloud-connected irrigation hardware.

    Routes commands through vendor-specific REST APIs with proper
    authentication and response parsing.

    Connection config keys:
      vendor: str            — VendorId (e.g. "LINDSAY", "HUNTER")
      base_url: str          — Override vendor API base URL
      api_key: str           — API key (for api_key auth)
      client_id: str         — OAuth2 client ID
      client_secret: str     — OAuth2 client secret
      token_url: str         — OAuth2 token endpoint
      access_token: str      — Pre-fetched access token
      timeout_s: int         — Request timeout (default 30)
      verify_ssl: bool       — Verify SSL certificates (default True)
      custom_headers: dict   — Additional HTTP headers
      custom_endpoints: dict — Override endpoint templates
    """

    def __init__(self, registration: ActuatorRegistration):
        super().__init__(registration)
        self._config = registration.connection_config
        self._vendor = registration.vendor.value
        self._timeout = self._config.get("timeout_s", 30)
        self._verify_ssl = self._config.get("verify_ssl", True)
        self._custom_headers = self._config.get("custom_headers", {})

        # Resolve API template
        template = VENDOR_API_TEMPLATES.get(self._vendor, {})
        custom_endpoints = self._config.get("custom_endpoints", {})
        self._base_url = self._config.get("base_url", template.get("base_url", ""))
        self._endpoints = {**template, **custom_endpoints}
        self._auth_type = self._config.get("auth_type", template.get("auth_type", "api_key"))

        # Auth credentials
        self._api_key = self._config.get("api_key", "")
        self._client_id = self._config.get("client_id", "")
        self._client_secret = self._config.get("client_secret", "")
        self._token_url = self._config.get("token_url", "")
        self._access_token = self._config.get("access_token", "")
        self._token_expires_at: Optional[datetime] = None

    # ================================================================
    # Authentication
    # ================================================================

    def _get_auth_headers(self) -> Dict[str, str]:
        """Build authentication headers based on auth type."""
        headers = dict(self._custom_headers)
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        headers["User-Agent"] = "AgriWise-IrrigationRuntime/1.0"

        if self._auth_type == "api_key":
            headers["Authorization"] = f"Bearer {self._api_key}"
        elif self._auth_type == "oauth2":
            headers["Authorization"] = f"Bearer {self._access_token}"
        elif self._auth_type == "basic":
            import base64
            creds = base64.b64encode(
                f"{self._client_id}:{self._client_secret}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {creds}"

        return headers

    async def _refresh_oauth_token(self) -> bool:
        """Refresh OAuth2 access token if expired."""
        if not self._token_url or not self._client_id:
            return False

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._access_token = data["access_token"]
                        expires_in = data.get("expires_in", 3600)
                        from datetime import timedelta
                        self._token_expires_at = (
                            datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
                        )
                        logger.info("OAuth2 token refreshed for %s", self.device_id)
                        return True
                    else:
                        logger.error("OAuth2 token refresh failed: HTTP %d", resp.status)
                        return False
        except Exception as exc:
            logger.error("OAuth2 token refresh error: %s", exc)
            return False

    async def _ensure_token(self) -> None:
        """Ensure we have a valid access token for OAuth2."""
        if self._auth_type != "oauth2":
            return
        if self._token_expires_at and datetime.now(timezone.utc) < self._token_expires_at:
            return
        await self._refresh_oauth_token()

    # ================================================================
    # HTTP Helpers
    # ================================================================

    def _build_url(self, endpoint_key: str, **kwargs) -> str:
        """Build a full URL from endpoint template and parameters."""
        template = self._endpoints.get(endpoint_key, "")
        params = {"device_id": self.device_id, "zone_id": ""}
        params.update(kwargs)
        path = template.format(**params)
        return f"{self._base_url}{path}"

    async def _request(
        self,
        method: str,
        url: str,
        body: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Execute an HTTP request with auth and error handling."""
        await self._ensure_token()

        try:
            import aiohttp
        except ImportError:
            return {"success": False, "error": "aiohttp not installed"}

        headers = self._get_auth_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    json=body,
                    headers=headers,
                    ssl=self._verify_ssl,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as resp:
                    response_text = await resp.text()
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        response_data = {"raw": response_text}

                    if resp.status in (200, 201, 202, 204):
                        return {"success": True, "status": resp.status, "data": response_data}
                    else:
                        return {
                            "success": False,
                            "status": resp.status,
                            "error": response_data.get("message", response_text[:200]),
                        }
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Request timed out after {self._timeout}s"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ================================================================
    # Connection Lifecycle
    # ================================================================

    async def connect(self) -> bool:
        """Verify API connectivity by fetching device status."""
        if not self._base_url:
            logger.error("No base URL configured for HTTP actuator %s", self.device_id)
            return False

        # Refresh token if needed
        if self._auth_type == "oauth2":
            token_ok = await self._refresh_oauth_token()
            if not token_ok and not self._access_token:
                return False

        # Test connectivity
        url = self._build_url("status", device_id=self.device_id)
        result = await self._request("GET", url)

        if result.get("success"):
            self._connected = True
            self._status = ActuatorStatus.ONLINE
            logger.info("HTTP connected to %s for device %s (%s)",
                        self._base_url, self.device_id, self._vendor)
            return True
        else:
            logger.warning("HTTP connectivity check failed for %s: %s",
                           self.device_id, result.get("error"))
            return False

    async def disconnect(self) -> None:
        """No persistent connection — mark as offline."""
        self._connected = False
        self._status = ActuatorStatus.OFFLINE

    # ================================================================
    # Command Dispatch
    # ================================================================

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        """Dispatch an irrigation command via vendor REST API."""
        now = datetime.now(timezone.utc).isoformat()

        if command.command_type == CommandType.START_ZONE:
            return await self._start_zone(command)
        elif command.command_type == CommandType.STOP_ZONE:
            return await self._stop_zone(command)
        elif command.command_type == CommandType.EMERGENCY_STOP:
            return await self.emergency_stop()
        elif command.command_type == CommandType.SET_PIVOT_SPEED:
            return await self._set_pivot_params(command)
        elif command.command_type == CommandType.QUERY_STATUS:
            await self.get_status()
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
                error_code="UNSUPPORTED",
                error_message=f"HTTP driver does not support {command.command_type.value}",
            )

    async def _start_zone(self, command: IrrigationCommand) -> CommandResult:
        """Start irrigation via REST API."""
        now = datetime.now(timezone.utc).isoformat()
        url = self._build_url("start", device_id=self.device_id, zone_id=command.zone_id)

        body = {
            "duration_minutes": command.duration_minutes,
            "volume_mm": command.volume_mm,
            "flow_rate_lpm": command.flow_rate_lpm,
            "request_id": command.request_id or str(uuid.uuid4()),
        }

        # Vendor-specific body extensions
        if self._vendor == VendorId.LINDSAY.value:
            body["application_rate_mm_hr"] = (
                command.volume_mm / (command.duration_minutes / 60.0)
                if command.duration_minutes > 0 else 0
            )
        elif self._vendor == VendorId.VALLEY.value:
            body["speed_percent"] = command.pivot_speed_pct or 50
            body["start_angle"] = command.pivot_start_angle_deg
            body["end_angle"] = command.pivot_end_angle_deg

        result = await self._request("POST", url, body)

        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=result.get("success", False),
            timestamp=now,
            error_code="" if result.get("success") else "HTTP_ERROR",
            error_message=result.get("error", ""),
            retry_recommended=not result.get("success", False),
        )

    async def _stop_zone(self, command: IrrigationCommand) -> CommandResult:
        """Stop irrigation via REST API."""
        now = datetime.now(timezone.utc).isoformat()
        url = self._build_url("stop", device_id=self.device_id, zone_id=command.zone_id)

        result = await self._request("POST", url, {"request_id": command.request_id})

        success = bool(result.get("success", False))
        data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
        confirmed_stopped = bool(
            data.get("confirmed_stopped") is True
            or (data.get("flow_rate_lpm") == 0.0 and not data.get("is_running", False) and data.get("is_stopped", True))
            or str(data.get("status", "")).upper() in ("STOPPED", "IDLE")
        )
        confirmed = success and confirmed_stopped
        transport_only = success and not confirmed

        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=success,
            timestamp=now,
            transport_acknowledged_only=transport_only,
            confirmed_physical_stop=confirmed,
            error_code="" if success else "HTTP_ERROR",
            error_message=result.get("error", ""),
        )

    async def _set_pivot_params(self, command: IrrigationCommand) -> CommandResult:
        """Set pivot speed/angle via REST API."""
        now = datetime.now(timezone.utc).isoformat()
        url = self._build_url("start", device_id=self.device_id, zone_id=command.zone_id)

        body = {
            "speed_percent": command.pivot_speed_pct,
            "start_angle": command.pivot_start_angle_deg,
            "end_angle": command.pivot_end_angle_deg,
            "request_id": command.request_id or str(uuid.uuid4()),
        }

        result = await self._request("PUT", url, body)

        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=result.get("success", False),
            timestamp=now,
            error_message=result.get("error", ""),
        )

    # ================================================================
    # Status & Emergency
    # ================================================================

    async def get_status(self) -> ActuatorStatus:
        """Query device status via REST API."""
        url = self._build_url("status", device_id=self.device_id)
        result = await self._request("GET", url)

        if not result.get("success"):
            self._status = ActuatorStatus.OFFLINE
            return self._status

        data = result.get("data", {})

        # Vendor-specific status parsing
        if self._vendor in (VendorId.LINDSAY.value, VendorId.VALLEY.value):
            if data.get("running") or data.get("is_running"):
                self._status = ActuatorStatus.EXECUTING
            elif data.get("error") or data.get("fault"):
                self._status = ActuatorStatus.ERROR
            else:
                self._status = ActuatorStatus.ONLINE
        else:
            status_str = str(data.get("status", "")).upper()
            if "RUN" in status_str or "ACTIVE" in status_str:
                self._status = ActuatorStatus.EXECUTING
            elif "ERROR" in status_str or "FAULT" in status_str:
                self._status = ActuatorStatus.ERROR
            elif "OFFLINE" in status_str:
                self._status = ActuatorStatus.OFFLINE
            else:
                self._status = ActuatorStatus.ONLINE

        self._last_heartbeat = datetime.now(timezone.utc)
        return self._status

    async def emergency_stop(self) -> CommandResult:
        """Emergency stop via REST API — stop all zones."""
        now = datetime.now(timezone.utc).isoformat()

        # Try vendor-specific emergency stop first
        url = self._build_url("stop", device_id=self.device_id, zone_id="all")
        result = await self._request("POST", url, {"emergency": True})

        if not result.get("success"):
            # Fallback: stop each zone individually
            zones = self.registration.zone_ids
            for zone_id in zones:
                url = self._build_url("stop", device_id=self.device_id, zone_id=zone_id)
                await self._request("POST", url, {"emergency": True})

        logger.critical("🚨 EMERGENCY STOP sent via HTTP to %s (%s)",
                        self.device_id, self._vendor)

        success = bool(result.get("success", False))
        data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
        confirmed_stopped = bool(
            data.get("confirmed_stopped") is True
            or (data.get("flow_rate_lpm") == 0.0 and not data.get("is_running", False) and data.get("is_stopped", True))
            or str(data.get("status", "")).upper() in ("STOPPED", "IDLE")
        )
        confirmed = success and confirmed_stopped
        transport_only = success and not confirmed

        return CommandResult(
            command_id=f"ESTOP-{uuid.uuid4().hex[:8]}",
            device_id=self.device_id,
            success=success,
            timestamp=now,
            transport_acknowledged_only=transport_only,
            confirmed_physical_stop=confirmed,
            error_message=result.get("error", ""),
        )

"""B2B-04B Native Weather Provider HTTP Capture and Content-Addressed Store.

This module captures and records raw backend HTTP GET responses from approved
weather providers (Open-Meteo, OpenWeather).

A captured HTTPS response is an acquisition trace and transport provenance receipt,
NOT an independently calibrated WMO ground weather station observation, and NOT
permission to update Kalman filter state. No signing key or state-input grant issuer
exists here.

Security invariants:
- Rejects endpoint URLs with embedded query parameters, credentials, or fragments.
- Validates the actual transmitted GET URL on the wire against declared parameters.
- Strips sensitive credentials (API keys, tokens, secrets) before hashing or persisting.
- Enforces HTTPS only and prohibits HTTP redirects.
- Content-addressed append-only filesystem store with atomic writes.
- Strict domain separation: akaloris/layer0/native-weather-acquisition-evidence/v1.
- Derivative cache verification returns PROVENANCE_VERIFIED_CACHE, never promoting to LIVE.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import parse_qsl, urlsplit
import hashlib
import json
import math
import os
import re
import tempfile

from services.agribrain.layer0.native_issuer.weather_product_registry import (
    WeatherProductId,
    WeatherProductSpec,
    WeatherRegistryError,
    get_weather_product_spec,
    identify_weather_product,
    normalize_and_validate_endpoint,
    validate_weather_product_request,
)


WEATHER_EVIDENCE_DOMAIN = "akaloris/layer0/native-weather-acquisition-evidence/v1"
WEATHER_REQUEST_REPLAY_DOMAIN = "akaloris/layer0/native-weather-request-replay/v1"

MAX_PREPARED_REQUEST_BYTES = 64 * 1024       # 64 KB for GET query parameter JSON
MAX_WEATHER_RESPONSE_BYTES = 32 * 1024 * 1024  # 32 MB for weather JSON response

_FORBIDDEN_QUERY_KEYS = frozenset({
    "appid", "api_key", "apikey", "key", "token", "access_token",
    "refresh_token", "secret", "client_secret", "password",
    "authorization", "bearer",
})

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class NativeWeatherEvidenceError(ValueError):
    """Raised when weather acquisition evidence cannot be recorded or verified without corrupting lineage."""


class OriginClass(str, Enum):
    LIVE_PROVIDER_AUTHENTICATED = "LIVE_PROVIDER_AUTHENTICATED"
    PROVENANCE_VERIFIED_CACHE = "PROVENANCE_VERIFIED_CACHE"
    REANALYSIS = "REANALYSIS"
    FORECAST = "FORECAST"
    TEST_FIXTURE = "TEST_FIXTURE"
    USER_DECLARED = "USER_DECLARED"


def _utc(value: datetime) -> str:
    """Format aware datetime to UTC ISO8601 string ending with Z."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise NativeWeatherEvidenceError("retrieval timestamp requires an aware datetime")
    utc = value.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z")


def _sha(value: bytes) -> str:
    """Compute hex SHA-256 digest of bytes."""
    return hashlib.sha256(value).hexdigest()


def _check_id(value: str) -> str:
    """Validate 64-char lowercase hex SHA-256 identifier."""
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise NativeWeatherEvidenceError(f"malformed content identifier: {value}")
    return value


def _json_bytes(value: Any) -> bytes:
    """Canonical JSON encoding: sorted keys, compact separators, UTF-8."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """JSON object_pairs_hook that fails closed on duplicate keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NativeWeatherEvidenceError(f"duplicate JSON key in acquisition record: {key}")
        result[key] = value
    return result


def _clean_query_params(params: Mapping[str, Any]) -> dict[str, Any]:
    """Scrub forbidden credential keys and validate query values.
    
    Returns a canonical, sanitized parameter dictionary safe for persistence
    and hashing. Strips keys like 'appid', 'api_key', 'key', etc.
    Fails closed if string values contain embedded credential patterns.
    """
    if not isinstance(params, Mapping):
        raise NativeWeatherEvidenceError("weather query parameters must be a key-value mapping")

    cleaned: dict[str, Any] = {}
    for key, val in params.items():
        if not isinstance(key, str) or not key.strip():
            raise NativeWeatherEvidenceError("query parameter keys must be non-empty strings")
        
        normalized_key = key.lower().strip().replace("-", "_")
        # Strip forbidden credential keys completely from canonical parameters
        if normalized_key in _FORBIDDEN_QUERY_KEYS:
            continue

        if normalized_key in cleaned:
            raise NativeWeatherEvidenceError(f"duplicate normalized query key: {key}")

        cleaned[normalized_key] = _clean_param_value(val)

    return cleaned


def _clean_param_value(val: Any) -> Any:
    """Validate and sanitize a query parameter value."""
    if isinstance(val, Mapping):
        res = {}
        for k, v in val.items():
            if not isinstance(k, str) or k.lower().replace("-", "_") in _FORBIDDEN_QUERY_KEYS:
                continue
            res[k] = _clean_param_value(v)
        return res
    if isinstance(val, (list, tuple)):
        return [_clean_param_value(x) for x in val]
    if isinstance(val, str):
        # Prevent embedded credential patterns in parameter values
        if re.search(
            r"(?i)(?:\b(?:bearer|basic)\s+\S+|"
            r"\b(?:access[_-]?token|refresh[_-]?token|client[_-]?secret|"
            r"api[_-]?key|password)\s*[:=])",
            val,
        ):
            raise NativeWeatherEvidenceError("embedded credential detected in query parameter value")
        return val
    if val is None or isinstance(val, (int, bool)):
        return val
    if isinstance(val, float):
        if not math.isfinite(val):
            raise NativeWeatherEvidenceError(f"non-finite float in query parameters: {val}")
        return val
    raise NativeWeatherEvidenceError(f"unsupported parameter value type: {type(val)}")


def _parse_query_val(v: str) -> Any:
    """Convert raw query string value to canonical type if numeric/boolean."""
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    try:
        val_int = int(v)
        return val_int
    except ValueError:
        pass
    try:
        val_float = float(v)
        if math.isfinite(val_float):
            return val_float
    except ValueError:
        pass
    return v


def _canonical_params_equal(claimed: Mapping[str, Any], transmitted: Mapping[str, Any]) -> bool:
    """Compare declared sanitized parameters with transmitted wire parameters.
    
    Handles equivalent representations such as comma-separated lists vs lists,
    and integer vs float equivalence.
    """
    claimed_clean = dict(claimed)
    trans_clean = dict(transmitted)

    if set(claimed_clean.keys()) != set(trans_clean.keys()):
        return False

    for k, val_c in claimed_clean.items():
        val_t = trans_clean[k]

        # Normalize lists vs comma-separated strings
        if isinstance(val_c, (list, tuple)) and isinstance(val_t, str):
            val_t_list = [x.strip() for x in val_t.split(",") if x.strip()]
            val_c_list = [str(x).strip() for x in val_c]
            if val_t_list != val_c_list:
                return False
            continue
        elif isinstance(val_t, (list, tuple)) and isinstance(val_c, str):
            val_c_list = [x.strip() for x in val_c.split(",") if x.strip()]
            val_t_list = [str(x).strip() for x in val_t]
            if val_c_list != val_t_list:
                return False
            continue

        # Float comparison
        if isinstance(val_c, (int, float)) and isinstance(val_t, (int, float)):
            if abs(float(val_c) - float(val_t)) > 1e-7:
                return False
            continue

        # General equality
        if val_c != val_t:
            return False

    return True


def _manifest_id(value: Mapping[str, Any]) -> str:
    """Compute the SHA-256 acquisition ID over canonical manifest material."""
    return _sha(_json_bytes({k: v for k, v in value.items() if k != "acquisition_id"}))


@dataclass(frozen=True)
class NativeWeatherAcquisitionReceipt:
    """Immutable receipt representing native HTTP GET response acquisition evidence."""
    acquisition_id: str
    origin_class: OriginClass
    provider: str
    product_id: str
    endpoint: str
    request_sha256: str
    response_sha256: str
    response_bytes: int
    object_id: str
    retrieved_at: str
    provider_request_id: str
    credential_reference: str
    http_status: int
    coordinate_requested: tuple[float, float]
    valid_interval: tuple[str | None, str | None]
    authoritative_role: str
    canonical_query_params: dict[str, Any]
    qualification_status: str = "NOT_QUALIFIED"
    provider_signature_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert receipt to dictionary matching schema domain."""
        return {
            "domain": WEATHER_EVIDENCE_DOMAIN,
            "acquisition_id": self.acquisition_id,
            "origin_class": self.origin_class.value if isinstance(self.origin_class, OriginClass) else str(self.origin_class),
            "provider": self.provider,
            "product_id": self.product_id,
            "endpoint": self.endpoint,
            "request_sha256": self.request_sha256,
            "response_sha256": self.response_sha256,
            "response_bytes": self.response_bytes,
            "object_id": self.object_id,
            "retrieved_at": self.retrieved_at,
            "provider_request_id": self.provider_request_id,
            "credential_reference": self.credential_reference,
            "http_status": self.http_status,
            "coordinate_requested": list(self.coordinate_requested),
            "valid_interval": list(self.valid_interval),
            "authoritative_role": self.authoritative_role,
            "canonical_query_params": self.canonical_query_params,
            "qualification_status": self.qualification_status,
            "provider_signature_verified": self.provider_signature_verified,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NativeWeatherAcquisitionReceipt:
        """Construct receipt from dictionary, validating structure and types."""
        if data.get("domain") != WEATHER_EVIDENCE_DOMAIN:
            raise NativeWeatherEvidenceError(f"invalid domain in manifest: {data.get('domain')}")
        
        origin_val = data.get("origin_class")
        origin = OriginClass(origin_val) if origin_val in OriginClass._value2member_map_ else OriginClass.PROVENANCE_VERIFIED_CACHE
        
        coords = data.get("coordinate_requested", [0.0, 0.0])
        coord_tuple = (float(coords[0]), float(coords[1]))
        
        interval = data.get("valid_interval", [None, None])
        interval_tuple = (
            str(interval[0]) if interval[0] is not None else None,
            str(interval[1]) if interval[1] is not None else None,
        )

        return cls(
            acquisition_id=str(data["acquisition_id"]),
            origin_class=origin,
            provider=str(data["provider"]),
            product_id=str(data["product_id"]),
            endpoint=str(data["endpoint"]),
            request_sha256=str(data["request_sha256"]),
            response_sha256=str(data["response_sha256"]),
            response_bytes=int(data["response_bytes"]),
            object_id=str(data["object_id"]),
            retrieved_at=str(data["retrieved_at"]),
            provider_request_id=str(data.get("provider_request_id", "")),
            credential_reference=str(data.get("credential_reference", "")),
            http_status=int(data.get("http_status", 200)),
            coordinate_requested=coord_tuple,
            valid_interval=interval_tuple,
            authoritative_role=str(data.get("authoritative_role", "UNVERIFIED")),
            canonical_query_params=dict(data.get("canonical_query_params", {})),
            qualification_status=str(data.get("qualification_status", "NOT_QUALIFIED")),
            provider_signature_verified=bool(data.get("provider_signature_verified", False)),
        )


class NativeWeatherEvidenceStore:
    """Content-Addressed Storage (CAS) for native weather provider responses and metadata.
    
    Append-only filesystem adapter. Does not mutate existing objects.
    """

    def __init__(self, root: str | Path):
        if not isinstance(root, (str, Path)) or not str(root):
            raise NativeWeatherEvidenceError("trusted evidence root path is required")
        self.root = Path(root).resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _path(self, kind: str, digest: str) -> Path:
        """Resolve content-addressed sharded path under evidence root."""
        digest = _check_id(digest)
        if kind not in ("objects", "manifests", "request_wire", "request_replays"):
            raise NativeWeatherEvidenceError(f"invalid evidence object kind: {kind}")
        return self.root / kind / digest[:2] / digest

    @staticmethod
    def _write_once(path: Path, content: bytes) -> None:
        """Atomically write content to path using temporary file and atomic link/replace."""
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".pending-", dir=str(path.parent), delete=False
            ) as f:
                tmp = Path(f.name)
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            try:
                os.link(tmp, path)
            except (FileExistsError, OSError):
                # On Windows or across file systems os.link may raise; fallback to atomic replace
                if path.exists():
                    if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
                        raise NativeWeatherEvidenceError("existing evidence object has different content")
                else:
                    os.replace(tmp, path)
                    tmp = None
        finally:
            if tmp is not None and tmp.exists():
                tmp.unlink(missing_ok=True)

    def capture_http_response(
        self,
        *,
        response: Any,
        endpoint: str,
        query_params: Mapping[str, Any],
        credential_reference: str = "open_access",
        retrieved_at: datetime | None = None,
    ) -> NativeWeatherAcquisitionReceipt:
        """Record real backend HTTP GET response into CAS store.
        
        Validates endpoint, transmitted URL, method, status, redirect prohibition,
        credential scrubbing, and content integrity before creating append-only manifests.
        """
        # 1. Endpoint Validation & Product Registry Identification
        try:
            normalized_endpoint = normalize_and_validate_endpoint(endpoint)
            spec = identify_weather_product(normalized_endpoint, query_params)
            validate_weather_product_request(spec, "GET", query_params)
        except WeatherRegistryError as exc:
            raise NativeWeatherEvidenceError(f"registry validation failed: {exc}") from exc

        # 2. HTTP Status and Redirects
        status_code = getattr(response, "status_code", None)
        if status_code != 200:
            raise NativeWeatherEvidenceError(
                f"weather acquisition requires HTTP 200, got status {status_code}"
            )

        # Prohibit redirects: verify response history is empty
        history = getattr(response, "history", None)
        if history and len(history) > 0:
            raise NativeWeatherEvidenceError("HTTP redirects are prohibited for native weather acquisition")

        resp_url = getattr(response, "url", None)
        if not resp_url:
            raise NativeWeatherEvidenceError("response missing valid URL")
        
        # Check that base URL of response matches target normalized endpoint
        parts_resp = urlsplit(resp_url)
        if (
            parts_resp.scheme.lower() != "https"
            or parts_resp.username is not None or parts_resp.password is not None
            or parts_resp.fragment
        ):
            raise NativeWeatherEvidenceError("weather_response_origin_mismatch")
        normalized_resp_base = f"https://{parts_resp.netloc.lower()}{parts_resp.path.rstrip('/')}"
        if normalized_resp_base != normalized_endpoint:
            raise NativeWeatherEvidenceError("weather_response_origin_mismatch")

        # 3. Transmitted Request Wire Inspection
        req = getattr(response, "request", None)
        if req is None or getattr(req, "method", "").upper() != "GET":
            raise NativeWeatherEvidenceError("response does not bind expected backend GET request")

        req_url = getattr(req, "url", None)
        if not req_url or not isinstance(req_url, str):
            raise NativeWeatherEvidenceError("prepared request missing valid URL")

        parts_req = urlsplit(req_url)
        if (
            parts_req.scheme.lower() != "https"
            or parts_req.username is not None or parts_req.password is not None
            or parts_req.fragment
        ):
            raise NativeWeatherEvidenceError("weather_prepared_request_origin_mismatch")
        normalized_req_base = f"https://{parts_req.netloc.lower()}{parts_req.path.rstrip('/')}"
        if normalized_req_base != normalized_endpoint:
            raise NativeWeatherEvidenceError("weather_prepared_request_origin_mismatch")

        # Extract and sanitize query parameters actually transmitted on the wire
        raw_transmitted_qsl = parse_qsl(parts_req.query, keep_blank_values=True)
        transmitted_dict: dict[str, Any] = {}
        for k, v in raw_transmitted_qsl:
            clean_k = k.lower().strip().replace("-", "_")
            if clean_k in _FORBIDDEN_QUERY_KEYS:
                # Strip secret keys (e.g. appid, api_key) present in wire query string
                continue
            parsed_v = _parse_query_val(v)
            if clean_k in transmitted_dict:
                existing = transmitted_dict[clean_k]
                if isinstance(existing, list):
                    existing.append(parsed_v)
                else:
                    transmitted_dict[clean_k] = [existing, parsed_v]
            else:
                transmitted_dict[clean_k] = parsed_v

        # Clean caller query_params and verify exact equivalence with transmitted parameters
        clean_params = _clean_query_params(query_params)
        if not _canonical_params_equal(clean_params, transmitted_dict):
            raise NativeWeatherEvidenceError("prepared provider request query differs from acquisition claim")

        wire_query_sha = _sha(parts_req.query.encode("utf-8"))

        # 4. Credential Reference Validation
        if not isinstance(credential_reference, str) or not credential_reference:
            raise NativeWeatherEvidenceError("valid credential reference required")
        if any(x in credential_reference.lower() for x in ("://", "bearer ", "password", "token=")):
            raise NativeWeatherEvidenceError("credential reference must not contain secret material")
        if len(credential_reference) > 128:
            raise NativeWeatherEvidenceError("credential reference exceeds maximum length")

        # 5. Coordinate and Interval Extraction
        lat_key = "latitude" if "latitude" in clean_params else ("lat" if "lat" in clean_params else None)
        lon_key = "longitude" if "longitude" in clean_params else ("lon" if "lon" in clean_params else None)
        if lat_key is None or lon_key is None:
            raise NativeWeatherEvidenceError("missing latitude or longitude in query parameters")
        
        try:
            req_lat = float(clean_params[lat_key])
            req_lon = float(clean_params[lon_key])
        except (ValueError, TypeError):
            raise NativeWeatherEvidenceError("non-numeric coordinates in query parameters")

        if not (-90.0 <= req_lat <= 90.0) or not (-180.0 <= req_lon <= 180.0):
            raise NativeWeatherEvidenceError("coordinate outside valid geographic range")

        start_date = str(clean_params["start_date"]) if "start_date" in clean_params else None
        end_date = str(clean_params["end_date"]) if "end_date" in clean_params else None
        if start_date is None and "dt" in clean_params:
            start_date = str(clean_params["dt"])
            end_date = str(clean_params["dt"])
        valid_interval = (start_date, end_date)

        # 6. Response Payload Verification
        body = getattr(response, "content", None)
        if not isinstance(body, bytes) or not body:
            raise NativeWeatherEvidenceError("empty or non-bytes response content")
        if len(body) > MAX_WEATHER_RESPONSE_BYTES:
            raise NativeWeatherEvidenceError(
                f"oversized weather response: {len(body)} > {MAX_WEATHER_RESPONSE_BYTES}"
            )

        # Ensure response is well-formed JSON without duplicate keys
        try:
            parsed_json = json.loads(body.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
            if not isinstance(parsed_json, dict):
                raise NativeWeatherEvidenceError("weather response must be a JSON object")
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise NativeWeatherEvidenceError(f"malformed weather JSON response: {exc}") from exc

        # 7. Canonical Query Parameter Digest and Replay Retention
        canonical_query_bytes = _json_bytes(clean_params)
        if len(canonical_query_bytes) > MAX_PREPARED_REQUEST_BYTES:
            raise NativeWeatherEvidenceError("oversized query parameter metadata")

        request_sha = _sha(canonical_query_bytes)
        response_sha = _sha(body)
        retrieved = _utc(retrieved_at or datetime.now(timezone.utc))
        provider_req_id = getattr(response, "headers", {}).get("x-request-id", "")
        if not isinstance(provider_req_id, str) or len(provider_req_id) > 256:
            provider_req_id = ""

        # 8. Manifest and Identity Assembly (using normalized endpoint without query strings)
        material = {
            "domain": WEATHER_EVIDENCE_DOMAIN,
            "origin_class": OriginClass.LIVE_PROVIDER_AUTHENTICATED.value,
            "provider": spec.provider.value,
            "product_id": spec.product_id.value,
            "endpoint": normalized_endpoint,
            "request_sha256": request_sha,
            "response_sha256": response_sha,
            "response_bytes": len(body),
            "object_id": response_sha,
            "retrieved_at": retrieved,
            "provider_request_id": provider_req_id,
            "credential_reference": credential_reference,
            "http_status": 200,
            "coordinate_requested": [req_lat, req_lon],
            "valid_interval": [valid_interval[0], valid_interval[1]],
            "authoritative_role": spec.authoritative_role.value,
            "canonical_query_params": clean_params,
            "qualification_status": "NOT_QUALIFIED",
            "provider_signature_verified": False,
        }
        acquisition_id = _manifest_id(material)

        # 9. Request Replay Sidecar binding wire query digest
        replay_record = {
            "domain": WEATHER_REQUEST_REPLAY_DOMAIN,
            "acquisition_id": acquisition_id,
            "request_sha256": request_sha,
            "wire_query_sha256": wire_query_sha,
            "canonical_query_params": clean_params,
        }

        # 10. Atomic Persistence
        self._write_once(self._path("objects", response_sha), body)
        self._write_once(self._path("request_replays", acquisition_id), _json_bytes(replay_record))
        full_manifest = {"acquisition_id": acquisition_id, **material}
        self._write_once(self._path("manifests", acquisition_id), _json_bytes(full_manifest))

        return NativeWeatherAcquisitionReceipt(
            acquisition_id=acquisition_id,
            origin_class=OriginClass.LIVE_PROVIDER_AUTHENTICATED,
            provider=spec.provider.value,
            product_id=spec.product_id.value,
            endpoint=normalized_endpoint,
            request_sha256=request_sha,
            response_sha256=response_sha,
            response_bytes=len(body),
            object_id=response_sha,
            retrieved_at=retrieved,
            provider_request_id=provider_req_id,
            credential_reference=credential_reference,
            http_status=200,
            coordinate_requested=(req_lat, req_lon),
            valid_interval=valid_interval,
            authoritative_role=spec.authoritative_role.value,
            canonical_query_params=clean_params,
            qualification_status="NOT_QUALIFIED",
            provider_signature_verified=False,
        )

    def verified_cache_receipt(self, acquisition_id: str) -> NativeWeatherAcquisitionReceipt:
        """Load and verify on-disk evidence manifest from CAS.
        
        Returns receipt with PROVENANCE_VERIFIED_CACHE origin, never promoting to LIVE.
        Fails closed on missing, altered, or corrupt manifests or missing objects.
        """
        acquisition_id = _check_id(acquisition_id)
        manifest_path = self._path("manifests", acquisition_id)
        if not manifest_path.exists():
            raise NativeWeatherEvidenceError(f"manifest not found for acquisition: {acquisition_id}")
        if manifest_path.is_symlink():
            raise NativeWeatherEvidenceError("symlinked evidence manifest is inadmissible")

        try:
            raw_manifest = manifest_path.read_bytes()
            data = json.loads(raw_manifest.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise NativeWeatherEvidenceError(f"unreadable evidence manifest: {exc}") from exc

        if not isinstance(data, dict) or data.get("domain") != WEATHER_EVIDENCE_DOMAIN:
            raise NativeWeatherEvidenceError("invalid or foreign evidence domain in manifest")

        if data.get("acquisition_id") != acquisition_id or _manifest_id(data) != acquisition_id:
            raise NativeWeatherEvidenceError("tampered acquisition manifest digest")

        if data.get("origin_class") != OriginClass.LIVE_PROVIDER_AUTHENTICATED.value:
            raise NativeWeatherEvidenceError("original acquisition was not LIVE_PROVIDER_AUTHENTICATED")

        if data.get("qualification_status") != "NOT_QUALIFIED" or data.get("provider_signature_verified") is not False:
            raise NativeWeatherEvidenceError("local evidence manifest cannot self-promote authority")

        # Verify associated CAS object existence and integrity
        object_id = data.get("object_id")
        if not object_id or object_id != data.get("response_sha256"):
            raise NativeWeatherEvidenceError("inconsistent object_id and response_sha256 in manifest")

        obj_path = self._path("objects", object_id)
        if not obj_path.exists() or obj_path.is_symlink():
            raise NativeWeatherEvidenceError("associated CAS object missing or symlinked")

        obj_bytes = obj_path.read_bytes()
        if _sha(obj_bytes) != object_id or len(obj_bytes) != data.get("response_bytes"):
            raise NativeWeatherEvidenceError("CAS object bytes corrupted or altered")

        # Return cached receipt with PROVENANCE_VERIFIED_CACHE
        cached = NativeWeatherAcquisitionReceipt.from_dict(data)
        object.__setattr__(cached, "origin_class", OriginClass.PROVENANCE_VERIFIED_CACHE)
        return cached

    def verified_request_params(self, acquisition_id: str) -> dict[str, Any]:
        """Replay and verify the exact captured GET query parameters."""
        receipt = self.verified_cache_receipt(acquisition_id)
        replay_path = self._path("request_replays", acquisition_id)
        if not replay_path.exists() or replay_path.is_symlink():
            raise NativeWeatherEvidenceError("missing or symlinked request replay record")

        try:
            record_bytes = replay_path.read_bytes()
            record = json.loads(record_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise NativeWeatherEvidenceError(f"unreadable request replay record: {exc}") from exc

        if (
            not isinstance(record, dict)
            or record.get("domain") != WEATHER_REQUEST_REPLAY_DOMAIN
            or record.get("acquisition_id") != receipt.acquisition_id
            or record.get("request_sha256") != receipt.request_sha256
            or not record.get("wire_query_sha256")
            or not _SHA256_PATTERN.fullmatch(str(record.get("wire_query_sha256")))
        ):
            raise NativeWeatherEvidenceError("invalid or mismatched request replay record")

        canonical_params = record.get("canonical_query_params")
        if not isinstance(canonical_params, dict):
            raise NativeWeatherEvidenceError("malformed canonical_query_params in replay record")

        if _sha(_json_bytes(canonical_params)) != receipt.request_sha256:
            raise NativeWeatherEvidenceError("replayed query parameters hash mismatch")

        return canonical_params

    def read_response_bytes(self, object_id: str) -> bytes:
        """Read and verify raw CAS response payload bytes."""
        object_id = _check_id(object_id)
        obj_path = self._path("objects", object_id)
        if not obj_path.exists() or obj_path.is_symlink():
            raise NativeWeatherEvidenceError(f"CAS object {object_id} not found or symlinked")
        data = obj_path.read_bytes()
        if _sha(data) != object_id:
            raise NativeWeatherEvidenceError(f"CAS object {object_id} hash verification failed")
        return data


def capture_backend_weather_response(
    *,
    response: Any,
    endpoint: str,
    query_params: Mapping[str, Any],
    credential_reference: str = "open_access",
) -> NativeWeatherAcquisitionReceipt | None:
    """Convenience entry point for backend weather capture using environment evidence root."""
    root = (
        os.getenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", "").strip()
        or os.getenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", "").strip()
    )
    required = os.getenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "").strip().lower() in (
        "1", "true", "yes",
    )
    if not root:
        if required:
            raise NativeWeatherEvidenceError("native weather evidence required but no evidence root configured")
        return None

    try:
        store = NativeWeatherEvidenceStore(root)
        return store.capture_http_response(
            response=response,
            endpoint=endpoint,
            query_params=query_params,
            credential_reference=credential_reference,
        )
    except OSError as exc:
        raise NativeWeatherEvidenceError(f"weather evidence storage failure: {exc}") from exc

"""B2B-01 native-provider acquisition evidence, NOT a state-input grant.

This module is called only from backend-controlled HTTP acquisition paths.
A captured HTTPS response is an acquisition trace, *not* a provider
cryptographic signature, independent scientific QA or permission to update
Kalman state. No signing key or detached-grant issuer exists here.

The filesystem CAS is a bounded, local evidence adapter. A production
immutable object store, IAM, audit/retention and cross-worker durability are
separate release gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
import hashlib
import json
import os
import re
import tempfile


EVIDENCE_DOMAIN = "akaloris/layer0/native-acquisition-evidence/v1"
REQUEST_REPLAY_DOMAIN = "akaloris/layer0/native-request-replay/v1"
MAX_PREPARED_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 256 * 1024 * 1024
ALLOWED_PROVIDER_ENDPOINTS = frozenset({
    "https://sh.dataspace.copernicus.eu/catalog/v1/search",
    "https://sh.dataspace.copernicus.eu/process/v1",
})
_FORBIDDEN_KEYS = frozenset({
    "authorization", "access_token", "refresh_token", "api_key",
    "apikey", "client_secret", "password", "secret", "bearer",
})
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class NativeEvidenceError(ValueError):
    """Evidence cannot be recorded or verified without corrupting lineage."""


class OriginClass(str, Enum):
    LIVE_PROVIDER_AUTHENTICATED = "LIVE_PROVIDER_AUTHENTICATED"
    PROVENANCE_VERIFIED_CACHE = "PROVENANCE_VERIFIED_CACHE"
    REANALYSIS = "REANALYSIS"
    FORECAST = "FORECAST"
    TEST_FIXTURE = "TEST_FIXTURE"
    USER_DECLARED = "USER_DECLARED"


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise NativeEvidenceError("retrieval timestamp requires an aware datetime")
    utc = value.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z")


def _safe_request(value: Any) -> Any:
    """Reject secrets and non-JSON scalars before serializing a request."""
    if isinstance(value, Mapping):
        result = {}
        for key, val in value.items():
            if not isinstance(key, str) or key.lower().replace("-", "_") in _FORBIDDEN_KEYS:
                raise NativeEvidenceError("forbidden or malformed acquisition request field")
            if key in result:
                raise NativeEvidenceError("duplicate acquisition request field")
            result[key] = _safe_request(val)
        return result
    if isinstance(value, (list, tuple)):
        return [_safe_request(x) for x in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        import math
        if math.isfinite(value):
            return value
    raise NativeEvidenceError("noncanonical acquisition request field")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=False).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise NativeEvidenceError("duplicate JSON request or manifest field")
        result[key] = value
    return result


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _check_id(value: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise NativeEvidenceError("malformed content identifier")
    return value


def _endpoint(value: str) -> str:
    if not isinstance(value, str) or value not in ALLOWED_PROVIDER_ENDPOINTS:
        raise NativeEvidenceError("provider endpoint is not in the trusted acquisition allowlist")
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise NativeEvidenceError("untrusted endpoint credentials or query")
    return value


@dataclass(frozen=True)
class NativeAcquisitionReceipt:
    acquisition_id: str
    origin_class: OriginClass
    provider: str
    sensor: str
    endpoint: str
    request_sha256: str
    response_sha256: str
    response_bytes: int
    object_id: str
    retrieved_at: str
    provider_product_id: str
    provider_request_id: str
    credential_reference: str
    http_status: int
    qualification_status: str = "NOT_QUALIFIED"
    provider_signature_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": EVIDENCE_DOMAIN,
            "acquisition_id": self.acquisition_id,
            "origin_class": self.origin_class.value,
            "provider": self.provider, "sensor": self.sensor,
            "endpoint": self.endpoint,
            "request_sha256": self.request_sha256,
            "response_sha256": self.response_sha256,
            "response_bytes": self.response_bytes,
            "object_id": self.object_id,
            "retrieved_at": self.retrieved_at,
            "provider_product_id": self.provider_product_id,
            "provider_request_id": self.provider_request_id,
            "credential_reference": self.credential_reference,
            "http_status": self.http_status,
            "qualification_status": self.qualification_status,
            "provider_signature_verified": self.provider_signature_verified,
        }


def _manifest_id(value: Mapping[str, Any]) -> str:
    return _sha(_json_bytes({k: v for k, v in value.items() if k != "acquisition_id"}))


class NativeEvidenceStore:
    """Append-only, content-addressed filesystem adapter, not WORM storage."""

    def __init__(self, root: str | Path):
        if not isinstance(root, (str, Path)) or not str(root):
            raise NativeEvidenceError("trusted evidence root is required")
        self.root = Path(root).resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _path(self, kind: str, digest: str) -> Path:
        digest = _check_id(digest)
        if kind not in ("objects", "manifests", "request_wire", "request_replays"):
            raise NativeEvidenceError("invalid evidence object kind")
        return self.root / kind / digest[:2] / digest

    @staticmethod
    def _write_once(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".pending-",
                                             dir=str(path.parent), delete=False) as f:
                tmp = Path(f.name)
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            try:
                # Atomic creation: the final CAS object never exposes a
                # partially written payload; concurrent equal writers agree.
                os.link(tmp, path)
            except FileExistsError:
                if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
                    raise NativeEvidenceError("existing evidence object has different content")
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)

    def capture_http_response(
        self, *, response: Any, endpoint: str, request_parameters: Mapping[str, Any],
        sensor: str, provider_product_id: str = "", credential_reference: str,
        retrieved_at: datetime | None = None,
    ) -> NativeAcquisitionReceipt:
        """Record real backend HTTP response. Caller must own provider credentials.

        A response or its URL is not a trusted proof when supplied by clients.
        Call this ONLY from the internal allowlisted requests.post boundary.
        """
        endpoint = _endpoint(endpoint)
        if sensor not in ("S1", "S2"):
            raise NativeEvidenceError("unsupported native-acquisition sensor")
        if not isinstance(credential_reference, str) or not credential_reference or any(
            x in credential_reference.lower() for x in ("://", "bearer ", "secret", "token=")
        ):
            raise NativeEvidenceError("credential reference must not be secret material")
        if not isinstance(provider_product_id, str) or len(provider_product_id) > 256:
            raise NativeEvidenceError("malformed provider product identity")
        if not isinstance(request_parameters, Mapping):
            raise NativeEvidenceError("acquisition request must be structured")
        safe_parameters = _safe_request(request_parameters)
        if (
            getattr(response, "status_code", None) != 200
            or getattr(response, "url", None) != endpoint
        ):
            raise NativeEvidenceError("response was not retrieved from expected successful HTTPS endpoint")
        req = getattr(response, "request", None)
        if (
            req is None
            or getattr(req, "method", None) != "POST"
            or getattr(req, "url", None) != endpoint
        ):
            raise NativeEvidenceError("response does not bind the expected backend POST")
        headers = getattr(req, "headers", {})
        auth = headers.get("Authorization", "") if isinstance(headers, Mapping) else ""
        if not isinstance(auth, str) or not auth.startswith("Bearer ") or len(auth) < 12:
            raise NativeEvidenceError("response lacks backend credential-bound request context")

        # The request digest must describe what was actually transmitted,
        # not merely a second JSON object passed by the acquisition caller.
        prepared_body = getattr(req, "body", None)
        if isinstance(prepared_body, str):
            prepared_body = prepared_body.encode("utf-8")
        if not isinstance(prepared_body, bytes) or len(prepared_body) > MAX_PREPARED_REQUEST_BYTES:
            raise NativeEvidenceError("missing or oversized prepared provider request")
        try:
            transmitted = _safe_request(json.loads(
                prepared_body, object_pairs_hook=_reject_duplicate_keys
            ))
            if _json_bytes(transmitted) != _json_bytes(safe_parameters):
                raise NativeEvidenceError("prepared provider request differs from acquisition claim")
        except (ValueError, TypeError, UnicodeDecodeError):
            raise NativeEvidenceError("invalid or mismatched prepared provider request") from None

        body = getattr(response, "content", None)
        if not isinstance(body, bytes) or not body or len(body) > MAX_RESPONSE_BYTES:
            raise NativeEvidenceError("invalid or oversized provider response")
        retrieved = _utc(retrieved_at or datetime.now(timezone.utc))
        response_id = getattr(response, "headers", {}).get("x-request-id", "")
        if not isinstance(response_id, str) or len(response_id) > 256:
            raise NativeEvidenceError("invalid provider response ID")
        response_sha = _sha(body)
        request_sha = _sha(_json_bytes(safe_parameters))
        wire_sha = _sha(prepared_body)
        material = {
            "domain": EVIDENCE_DOMAIN,
            "origin_class": OriginClass.LIVE_PROVIDER_AUTHENTICATED.value,
            "provider": "sentinel_hub", "sensor": sensor,
            "endpoint": endpoint,
            "request_sha256": request_sha, "response_sha256": response_sha,
            "response_bytes": len(body), "object_id": response_sha,
            "retrieved_at": retrieved, "provider_product_id": provider_product_id,
            "provider_request_id": response_id,
            "credential_reference": credential_reference,
            "http_status": 200, "qualification_status": "NOT_QUALIFIED",
            "provider_signature_verified": False,
        }
        acquisition_id = _manifest_id(material)
        # The raw PreparedRequest bytes are written before manifest exposure.
        # Keep the original v1 acquisition ID stable: a separate append-only,
        # acquisition-ID-keyed replay record links the exact wire digest to
        # the already-rooted canonical request hash.
        replay_record = {
            "domain": REQUEST_REPLAY_DOMAIN,
            "acquisition_id": acquisition_id,
            "request_sha256": request_sha,
            "wire_request_sha256": wire_sha,
            "request_bytes": len(prepared_body),
        }
        # Failure of *any* immutable write is a failed capture. Retaining a
        # response manifest without its request replay is forbidden for new
        # acquisitions (existing historical v1 captures remain readable).
        self._write_once(self._path("request_wire", wire_sha), prepared_body)
        self._write_once(self._path("request_replays", acquisition_id), _json_bytes(replay_record))
        self._write_once(self._path("objects", response_sha), body)
        full = {"acquisition_id": acquisition_id, **material}
        self._write_once(self._path("manifests", acquisition_id), _json_bytes(full))
        return NativeAcquisitionReceipt(
            acquisition_id=acquisition_id,
            origin_class=OriginClass.LIVE_PROVIDER_AUTHENTICATED,
            provider="sentinel_hub", sensor=sensor, endpoint=endpoint,
            request_sha256=request_sha, response_sha256=response_sha,
            response_bytes=len(body), object_id=response_sha,
            retrieved_at=retrieved, provider_product_id=provider_product_id,
            provider_request_id=response_id, credential_reference=credential_reference,
            http_status=200,
        )

    def verified_request_body(self, acquisition_id: str) -> dict[str, Any]:
        """Replay exact captured HTTP POST body after CAS and manifest checks.

        This cannot sign a state-input grant. Legacy v1 captures without the
        new request-replay record are *incomplete*, not retroactively verified.
        """
        receipt = self.verified_cache_receipt(acquisition_id)
        replay_path = self._path("request_replays", acquisition_id)
        if not replay_path.exists():
            raise NativeEvidenceError("captured_request_not_retained")
        try:
            if replay_path.is_symlink() or not replay_path.is_file():
                raise NativeEvidenceError("invalid_captured_request_evidence")
            record_bytes = replay_path.read_bytes()
            if len(record_bytes) > 2048:
                raise NativeEvidenceError("invalid_captured_request_evidence")
            record = json.loads(record_bytes, object_pairs_hook=_reject_duplicate_keys)
            if (
                not isinstance(record, dict)
                or set(record) != {
                    "domain", "acquisition_id", "request_sha256",
                    "wire_request_sha256", "request_bytes",
                }
                or record["domain"] != REQUEST_REPLAY_DOMAIN
                or record["acquisition_id"] != receipt.acquisition_id
                or record["request_sha256"] != receipt.request_sha256
                or type(record["request_bytes"]) is not int
                or not 0 < record["request_bytes"] <= MAX_PREPARED_REQUEST_BYTES
            ):
                raise NativeEvidenceError("invalid_captured_request_evidence")
            wire_sha = _check_id(record["wire_request_sha256"])
            wire_path = self._path("request_wire", wire_sha)
            if wire_path.is_symlink() or not wire_path.is_file():
                raise NativeEvidenceError("invalid_captured_request_evidence")
            wire = wire_path.read_bytes()
            if len(wire) != record["request_bytes"] or _sha(wire) != wire_sha:
                raise NativeEvidenceError("invalid_captured_request_evidence")
            canonical = _safe_request(
                json.loads(wire, object_pairs_hook=_reject_duplicate_keys)
            )
            if not isinstance(canonical, dict):
                raise NativeEvidenceError("invalid_captured_request_evidence")
            if _sha(_json_bytes(canonical)) != receipt.request_sha256:
                raise NativeEvidenceError("invalid_captured_request_evidence")
            return canonical
        except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError):
            raise NativeEvidenceError("invalid_captured_request_evidence") from None


    def verified_cache_receipt(self, acquisition_id: str) -> NativeAcquisitionReceipt:
        """Verify on-disk lineage, returning CACHE rather than LIVE authority."""
        manifest_path = self._path("manifests", acquisition_id)
        try:
            if manifest_path.is_symlink():
                raise NativeEvidenceError("symlink evidence is not admissible")
            material = json.loads(
                manifest_path.read_bytes(), object_pairs_hook=_reject_duplicate_keys
            )
            if not isinstance(material, dict) or material.get("domain") != EVIDENCE_DOMAIN:
                raise NativeEvidenceError("invalid native evidence manifest")
            if set(material) != set(NativeAcquisitionReceipt(
                acquisition_id="", origin_class=OriginClass.TEST_FIXTURE,
                provider="", sensor="", endpoint="", request_sha256="",
                response_sha256="", response_bytes=0, object_id="",
                retrieved_at="", provider_product_id="", provider_request_id="",
                credential_reference="", http_status=0,
            ).to_dict()):
                raise NativeEvidenceError("unexpected evidence manifest fields")
            if material["acquisition_id"] != acquisition_id or _manifest_id(material) != acquisition_id:
                raise NativeEvidenceError("tampered acquisition manifest")
            if material["origin_class"] != OriginClass.LIVE_PROVIDER_AUTHENTICATED.value:
                raise NativeEvidenceError("origin was never a trusted native live acquisition")
            _endpoint(material["endpoint"])
            if material["qualification_status"] != "NOT_QUALIFIED" or material["provider_signature_verified"] is not False:
                raise NativeEvidenceError("local manifest cannot promote scientific authority")
            obj_path = self._path("objects", material["object_id"])
            if obj_path.is_symlink():
                raise NativeEvidenceError("symlink evidence is not admissible")
            body = obj_path.read_bytes()
            if (_sha(body) != material["response_sha256"]
                    or material["object_id"] != material["response_sha256"]
                    or len(body) != material["response_bytes"]):
                raise NativeEvidenceError("cached response bytes do not match capture")
            _check_id(material["request_sha256"])
            return NativeAcquisitionReceipt(
                acquisition_id=acquisition_id,
                origin_class=OriginClass.PROVENANCE_VERIFIED_CACHE,
                provider=material["provider"], sensor=material["sensor"],
                endpoint=material["endpoint"],
                request_sha256=material["request_sha256"],
                response_sha256=material["response_sha256"],
                response_bytes=material["response_bytes"],
                object_id=material["object_id"], retrieved_at=material["retrieved_at"],
                provider_product_id=material["provider_product_id"],
                provider_request_id=material["provider_request_id"],
                credential_reference=material["credential_reference"],
                http_status=material["http_status"],
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise NativeEvidenceError("cached acquisition evidence is unavailable or invalid") from None



def restore_cached_native_references(
    metadata: Mapping[str, Any], *, sensor: str,
) -> tuple[str | None, str | None, str]:
    """Verify cold S1/S2 Catalog+Process evidence references.

    A local metadata.json is never proof of acquisition. Persisted links
    are returned only after both CAS manifests and raw objects validate,
    with an explicit non-authorizing CACHE origin. Old cache files with no
    native references remain UNATTESTED.
    """
    if sensor not in ("S1", "S2") or not isinstance(metadata, Mapping):
        raise NativeEvidenceError("invalid cached scene evidence context")
    catalog_id = metadata.get("native_catalog_acquisition_id")
    process_id = metadata.get("native_process_acquisition_id")
    if catalog_id is None and process_id is None:
        return None, None, "UNATTESTED"
    if not isinstance(catalog_id, str) or not isinstance(process_id, str):
        raise NativeEvidenceError("incomplete native acquisition references")
    _check_id(catalog_id)
    _check_id(process_id)
    root = os.getenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", "").strip()
    if not root:
        # The metadata is still allowed as a legacy scene, but must not
        # regain an unverified provenance join. Required HTTP capture is
        # distinct from an all-cache-return policy.
        if os.getenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "").strip().lower() in (
            "1", "true", "yes"
        ):
            raise NativeEvidenceError("native cache evidence root unavailable")
        return None, None, "UNATTESTED"

    store = NativeEvidenceStore(root)
    catalog = store.verified_cache_receipt(catalog_id)
    process = store.verified_cache_receipt(process_id)
    if (
        catalog.sensor != sensor or process.sensor != sensor
        or catalog.provider != "sentinel_hub"
        or process.provider != "sentinel_hub"
        or catalog.endpoint != "https://sh.dataspace.copernicus.eu/catalog/v1/search"
        or process.endpoint != "https://sh.dataspace.copernicus.eu/process/v1"
        or process.provider_product_id != metadata.get("provider_product_id")
        or process.response_sha256 != metadata.get("provider_response_hash")
        or process.request_sha256 != metadata.get("process_request_hash")
        or metadata.get("native_evidence_status") not in (
            "CAPTURED_UNQUALIFIED", "PROVENANCE_VERIFIED_CACHE",
        )
    ):
        raise NativeEvidenceError("cached scene references mismatch captured provider evidence")
    return catalog_id, process_id, "PROVENANCE_VERIFIED_CACHE"


def capture_backend_provider_response(
    *, response: Any, endpoint: str, request_parameters: Mapping[str, Any],
    sensor: str, provider_product_id: str = "",
) -> NativeAcquisitionReceipt | None:
    """Opt-in evidence recorder for *real internal* Sentinel fetch paths.

    Does not change state-entry admission, grant issuance, or source QA.
    A strict capture deployment requires an immutable-evidence destination;
    without one, historical fetchers remain legacy/unattested.
    """
    root = os.getenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", "").strip()
    required = os.getenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "").strip().lower() in (
        "1", "true", "yes",
    )
    if not root:
        if required:
            raise NativeEvidenceError("native acquisition evidence required but no trusted root is configured")
        return None
    try:
        return NativeEvidenceStore(root).capture_http_response(
            response=response, endpoint=endpoint, request_parameters=request_parameters,
            sensor=sensor, provider_product_id=provider_product_id,
            credential_reference="sentinel_hub_backend_oauth_client",
        )
    except OSError:
        # Backend permissions, disk-full or fsync failures are source
        # integrity failures, not permission to use unverified cached data.
        raise NativeEvidenceError("trusted native evidence storage unavailable") from None

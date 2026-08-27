import hmac
import hashlib
import os
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, List, Tuple, Dict, Any
from fastapi import Request, HTTPException, status
from services.agribrain.common.plot_namespace import PlotNamespace

_mongo_nonces_collection = None
_in_memory_nonces = set()


def rfc3986_encode(s: Any) -> str:
    """RFC 3986 percent-encoding: preserve ~_.- and encode spaces as %20."""
    return urllib.parse.quote(str(s if s is not None else ""), safe="~_.-")


def canonicalize_query_params(query: Union[str, List[Tuple[str, str]], Dict[str, Any], Request]) -> str:
    """
    Sort query parameters lexicographically by key then value.
    Input can be a raw query string, list of (key, val) pairs, dict, or Starlette request.query_params.
    """
    pairs: List[Tuple[str, str]] = []
    if isinstance(query, str):
        if not query.strip():
            return ""
        # Parse query string preserving duplicate keys
        parsed = urllib.parse.parse_qsl(query.lstrip("?"), keep_blank_values=True)
        pairs = [(str(k), str(v)) for k, v in parsed]
    elif hasattr(query, "multi_items"):
        # Starlette Headers / QueryParams
        pairs = [(str(k), str(v)) for k, v in query.multi_items()]
    elif isinstance(query, list):
        pairs = [(str(k), str(v if v is not None else "")) for k, v in query]
    elif isinstance(query, dict):
        for k, v in query.items():
            if isinstance(v, list):
                for item in v:
                    pairs.append((str(k), str(item if item is not None else "")))
            elif v is not None:
                pairs.append((str(k), str(v)))

    # Sort lexicographically by key then value
    pairs.sort(key=lambda item: (item[0], item[1]))
    return "&".join(f"{rfc3986_encode(k)}={rfc3986_encode(v)}" for k, v in pairs)


def _get_secret() -> str:
    secret = os.getenv("AGRIBRAIN_INTERNAL_SERVICE_SECRET", "").strip()
    env = os.getenv("NODE_ENV", os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development"))).lower()
    if not secret:
        if env in ("production", "prod", "staging"):
            raise RuntimeError("AGRIBRAIN_INTERNAL_SERVICE_SECRET must be set in non-development environments")
        return "agribrain-internal-dev-secret-key-32bytes"
    return secret


def compute_request_signature(
    method: str,
    path: str,
    query_string: Union[str, List[Tuple[str, str]], Dict[str, Any]],
    tenant_id: str,
    farm_id: str,
    plot_id: str,
    body_bytes: bytes,
    timestamp: str,
    nonce: str,
    key_version: str = "v1",
    secret: Optional[str] = None
) -> str:
    if secret is None:
        secret = _get_secret()

    canonical_query = canonicalize_query_params(query_string)
    body_hash = hashlib.sha256(body_bytes or b"").hexdigest()
    canonical_str = "\n".join([
        method.upper().strip(),
        path.strip(),
        canonical_query,
        tenant_id.strip(),
        farm_id.strip(),
        plot_id.strip(),
        body_hash,
        timestamp.strip(),
        nonce.strip(),
        key_version.strip()
    ])

    return hmac.new(secret.encode("utf-8"), canonical_str.encode("utf-8"), hashlib.sha256).hexdigest()


def init_mongo_nonce_indexes(db: Any) -> None:
    """Initialize MongoDB indexes once during startup."""
    global _mongo_nonces_collection
    try:
        coll = db["internal_service_nonces"]
        coll.create_index([("key_version", 1), ("nonce", 1)], unique=True)
        coll.create_index("expires_at", expireAfterSeconds=0)
        _mongo_nonces_collection = coll
    except Exception as exc:
        print(f"[AUTH] Could not initialize MongoDB nonce collection: {exc}")


def verify_and_store_nonce(key_version: str, nonce: str, max_age_seconds: int = 300) -> bool:
    """Stores nonce in MongoDB or in-memory fallback. Returns False if duplicate or DB fails in production."""
    global _mongo_nonces_collection
    nonce_key = f"{key_version}::{nonce}"
    environment = os.getenv(
        "NODE_ENV", os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development"))
    ).lower()
    is_prod = environment in ("production", "prod", "staging")

    # A process-local replay cache cannot enforce uniqueness across replicas.
    # Production therefore requires the shared atomic nonce store to exist.
    if is_prod and _mongo_nonces_collection is None:
        return False

    if nonce_key in _in_memory_nonces:
        return False

    now_dt = datetime.now(timezone.utc)
    expires_dt = now_dt + timedelta(seconds=max_age_seconds)

    # Try MongoDB atomic insert
    if _mongo_nonces_collection is not None:
        try:
            from pymongo.errors import DuplicateKeyError
            _mongo_nonces_collection.insert_one({
                "key_version": key_version,
                "nonce": nonce,
                "created_at": now_dt,
                "expires_at": expires_dt,
            })
        except Exception as exc:
            if "DuplicateKeyError" in type(exc).__name__ or "duplicate key" in str(exc).lower():
                return False
            if is_prod:
                # Production fails closed on DB error
                return False

    _in_memory_nonces.add(nonce_key)
    if len(_in_memory_nonces) > 10000:
        _in_memory_nonces.clear()

    return True


async def require_internal_service_request(request: Request) -> PlotNamespace:
    """
    FastAPI route dependency that validates signed internal service requests
    and returns an authenticated PlotNamespace.
    """
    sig = request.headers.get("X-AgriBrain-Signature")
    timestamp = request.headers.get("X-AgriBrain-Timestamp")
    nonce = request.headers.get("X-AgriBrain-Nonce")
    key_version = request.headers.get("X-AgriBrain-Key-Version", "v1")

    tenant_id = request.headers.get("X-Tenant-Id")
    farm_id = request.headers.get("X-Farm-Id")
    plot_id = request.headers.get("X-Plot-Id") or request.path_params.get("plot_id") or request.query_params.get("plot_id")

    allow_unauthenticated_dev = os.getenv("ALLOW_UNAUTHENTICATED_DEV", "false").lower() == "true"
    if not sig and allow_unauthenticated_dev:
        t_id = tenant_id or "dev_tenant"
        f_id = farm_id or "dev_farm"
        p_id = plot_id or "dev_plot"
        return PlotNamespace(tenant_id=t_id, farm_id=f_id, plot_id=p_id)

    if not sig or not timestamp or not nonce:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required internal service authentication headers"
        )

    if key_version != "v1":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unsupported internal service key version: {key_version}"
        )

    if not tenant_id or not farm_id or not plot_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required tenant_id, farm_id, or plot_id headers/params"
        )

    path_plot_id = request.path_params.get("plot_id")
    if path_plot_id and path_plot_id.strip() != plot_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Header X-Plot-Id does not match URL path parameter plot_id"
        )

    # Check clock skew (5-minute window)
    try:
        ts_val = float(timestamp)
        now = time.time()
        if abs(now - ts_val) > 300:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Request timestamp outside allowed clock skew window"
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request timestamp format"
        )

    # Read body for hash verification FIRST
    body_bytes = await request.body()
    expected_sig = compute_request_signature(
        method=request.method,
        path=request.url.path,
        query_string=request.query_params,
        tenant_id=tenant_id,
        farm_id=farm_id,
        plot_id=plot_id,
        body_bytes=body_bytes,
        timestamp=timestamp,
        nonce=nonce,
        key_version=key_version
    )

    if not hmac.compare_digest(sig.strip(), expected_sig.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service signature"
        )

    # Verify and reserve nonce ONLY AFTER signature is verified
    if not verify_and_store_nonce(key_version, nonce):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Replayed service request nonce detected"
        )

    return PlotNamespace(tenant_id=tenant_id, farm_id=farm_id, plot_id=plot_id)

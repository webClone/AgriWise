"""
EO Authentication Module
Handles OAuth2 authentication for Copernicus Dataspace Ecosystem (Sentinel Hub).
"""

import os
import time
import requests


# ============================================================================
# Configuration
# ============================================================================

SENTINEL_AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

# Standardised timeout for all EO HTTP requests (seconds)
EO_REQUEST_TIMEOUT = 15

# Global Token Cache
token_cache = {
    "access_token": None,
    "expires_at": 0
}

# Fast-fail guard: once auth fails, skip re-attempts in this process
_auth_failed = False
_auth_fail_reason = ""


# ============================================================================
# Authentication
# ============================================================================

def get_access_token():
    """
    Retrieves OAuth2 token from Copernicus Dataspace Ecosystem.
    Fast-fail: if auth has failed once this session, returns None immediately.
    """
    global token_cache, _auth_failed, _auth_fail_reason

    # Fast-fail guard: don't retry broken auth in the same process
    if _auth_failed:
        raise ConnectionError(f"Copernicus auth previously failed: {_auth_fail_reason}")

    if token_cache["access_token"] and time.time() < token_cache["expires_at"]:
        return token_cache["access_token"]

    client_id = os.getenv("SENTINEL_HUB_CLIENT_ID")
    client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET")

    if not client_id or not client_secret:
        _auth_failed = True
        _auth_fail_reason = "Missing credentials"
        raise ValueError("Missing SENTINEL_HUB_CLIENT_ID or SENTINEL_HUB_CLIENT_SECRET in environment")

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    # Fast-fail strategy: 1 retry, 8s timeout (not 30s x 3 retries)
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    session = requests.Session()
    retry = Retry(
        total=1,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    
    try:
        response = session.post(SENTINEL_AUTH_URL, data=payload, timeout=8)
        
        if response.status_code != 200:
            print(f"Sentinel Auth Error ({response.status_code}): {response.text}")
            _auth_failed = True
            _auth_fail_reason = f"HTTP {response.status_code}"
            raise Exception(f"Sentinel Auth Failed: {response.text}")

        data_resp = response.json()
        token_cache["access_token"] = data_resp["access_token"]
        # Expire 60 seconds early to be safe
        token_cache["expires_at"] = time.time() + data_resp["expires_in"] - 60
        return token_cache["access_token"]
        
    except Exception as e:
        _auth_failed = True
        _auth_fail_reason = str(e)
        print(f"[WARN] Sentinel Auth Failed (fast-fail enabled for this session): {e}")
        raise

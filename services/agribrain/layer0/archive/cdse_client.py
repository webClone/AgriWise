"""
CDSE OAuth2 client credentials token manager and client helpers.
Memory-only token caching. No logging of client secrets or access tokens.
"""
import os
import time
import requests
from typing import Dict, Optional, Any

class CDSEClient:
    def __init__(self):
        self.client_id = os.environ.get("CDSE_CLIENT_ID", "")
        self.client_secret = os.environ.get("CDSE_CLIENT_SECRET", "")
        self.token_url = os.environ.get(
            "CDSE_TOKEN_URL",
            "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        )
        self.auth_mode = os.environ.get("CDSE_AUTH_MODE", "client_credentials")
        self.offline = os.environ.get("AGRIWISE_ARCHIVE_OFFLINE", "true").lower() == "true"
        
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def get_access_token(self) -> str:
        """Fetches and caches the OAuth2 token in memory."""
        if self.offline or not self.client_id or not self.client_secret:
            return "offline-token"

        now = time.time()
        # Refresh token 30 seconds before it expires
        if self._access_token and now < self._token_expires_at - 30:
            return self._access_token

        # Perform OAuth2 client_credentials flow
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        try:
            # Note: Do not log data or response to avoid leaking credentials
            response = requests.post(self.token_url, data=data, timeout=30)
            response.raise_for_status()
            res_json = response.json()
            
            self._access_token = res_json["access_token"]
            expires_in = float(res_json.get("expires_in", 3600))
            self._token_expires_at = now + expires_in
            return self._access_token
        except Exception as e:
            # Keep log clean of secrets
            raise RuntimeError(f"CDSE authentication failed: {type(e).__name__}") from None

    def get_auth_header(self) -> Dict[str, str]:
        """Returns the authorization header dict."""
        token = self.get_access_token()
        if token in ("offline-token", "offline-mock-token", ""):
            return {}
        return {"Authorization": f"Bearer {token}"}

    def fetch_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Makes an authenticated GET request."""
        if self.offline:
            # In offline mode, requests should not hit the network.
            raise RuntimeError("Network requests disabled in offline mode.")
            
        headers = self.get_auth_header()
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

"""
STAC Client for querying Sentinel metadata from standard STAC catalogs (e.g. CDSE STAC).
"""
import os
import requests
from typing import Dict, List, Any, Optional
from .cdse_client import CDSEClient

class STACClient:
    def __init__(self, cdse_client: Optional[CDSEClient] = None):
        self.stac_url = os.environ.get(
            "AGRIWISE_STAC_URL",
            "https://api.dataspace.copernicus.eu/stac/search"
        )
        self.offline = os.environ.get("AGRIWISE_ARCHIVE_OFFLINE", "true").lower() == "true"
        self.cdse_client = cdse_client or CDSEClient()

    def search(
        self,
        geometry_geojson: Dict[str, Any],
        start_time: str,
        end_time: str,
        collections: List[str],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query the STAC catalog using intersects, datetime, and collections filters.
        Returns a list of GeoJSON-like Feature dicts representing STAC items.
        """
        if self.offline:
            # Under offline testing, this should not make network calls.
            # Returning empty or letting the mock provider handle it is standard.
            return []

        # Build standard STAC search payload
        payload = {
            "intersects": geometry_geojson,
            "datetime": f"{start_time}/{end_time}",
            "collections": collections,
            "limit": limit
        }

        try:
            # Query the CDSE or other STAC endpoint with authorization if CDSE
            headers = self.cdse_client.get_auth_header()
            headers["Content-Type"] = "application/json"
            
            response = requests.post(self.stac_url, json=payload, headers=headers, timeout=45)
            response.raise_for_status()
            res_json = response.json()
            
            return res_json.get("features", [])
        except Exception as e:
            raise RuntimeError(f"STAC search failed: {type(e).__name__}") from None

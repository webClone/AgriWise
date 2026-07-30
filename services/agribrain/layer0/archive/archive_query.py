"""
Partition-based STAC query translator.
Divides long time ranges into smaller partitions (e.g. monthly) to query STAC catalogue reliably.
Parses STAC items into ArchiveSearchResult dataclass.
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from .archive_types import ArchiveSearchResult
from .stac_client import STACClient

class ArchiveQueryManager:
    def __init__(self, stac_client: Optional[STACClient] = None):
        self.stac_client = stac_client or STACClient()

    def partition_date_range(self, start_date_str: str, end_date_str: str) -> List[tuple[str, str]]:
        """Divides start_date to end_date into monthly intervals."""
        start_dt = datetime.strptime(start_date_str.split("T")[0], "%Y-%m-%d")
        end_dt = datetime.strptime(end_date_str.split("T")[0], "%Y-%m-%d")
        
        partitions = []
        current_dt = start_dt
        while current_dt <= end_dt:
            # Next month start
            if current_dt.month == 12:
                next_month = datetime(current_dt.year + 1, 1, 1)
            else:
                next_month = datetime(current_dt.year, current_dt.month + 1, 1)
                
            part_end = min(next_month - timedelta(days=1), end_dt)
            # Format as ISO strings with times
            part_start_str = current_dt.strftime("%Y-%m-%dT00:00:00Z")
            part_end_str = part_end.strftime("%Y-%m-%dT23:59:59Z")
            partitions.append((part_start_str, part_end_str))
            current_dt = next_month
            
        return partitions

    def map_source_to_collections(self, source: str) -> List[str]:
        """Maps unified source name to standard STAC collection IDs."""
        if source.lower() in ("sentinel2", "s2"):
            return ["sentinel-2-l2a"]
        elif source.lower() in ("sentinel1", "s1"):
            return ["sentinel-1-grd"]
        return []

    def execute_partitioned_query(
        self,
        geometry_geojson: Dict[str, Any],
        start_date: str,
        end_date: str,
        sources: List[str]
    ) -> List[ArchiveSearchResult]:
        """
        Executes partition-based query over the entire duration for specified sources.
        """
        partitions = self.partition_date_range(start_date, end_date)
        all_results = []
        seen_scene_ids = set()

        for source in sources:
            collections = self.map_source_to_collections(source)
            if not collections:
                continue

            for part_start, part_end in partitions:
                items = self.stac_client.search(
                    geometry_geojson=geometry_geojson,
                    start_time=part_start,
                    end_time=part_end,
                    collections=collections
                )
                
                for item in items:
                    scene_id = item.get("id")
                    if not scene_id or scene_id in seen_scene_ids:
                        continue
                        
                    parsed = self._parse_stac_item(item, source)
                    if parsed:
                        all_results.append(parsed)
                        seen_scene_ids.add(scene_id)
                        
        # Sort chronologically by acquisition_time
        all_results.sort(key=lambda x: x.acquisition_time)
        return all_results

    def _parse_stac_item(self, item: Dict[str, Any], source: str) -> Optional[ArchiveSearchResult]:
        """Parses a raw STAC item GeoJSON into ArchiveSearchResult."""
        try:
            scene_id = item["id"]
            properties = item.get("properties", {})
            acquisition_time = properties.get("datetime") or properties.get("start_datetime")
            if not acquisition_time:
                return None

            product_level = properties.get("processing:level") or properties.get("product_level", "")
            if not product_level:
                if source == "sentinel2":
                    product_level = "L2A"
                elif source == "sentinel1":
                    product_level = "GRD"

            tile_id = properties.get("s2:mgrs_tile")
            cloud_score = properties.get("eo:cloud_cover")
            if cloud_score is not None:
                cloud_score = float(cloud_score)

            # Extract URLs
            asset_urls = {}
            assets = item.get("assets", {})
            for name, asset_info in assets.items():
                href = asset_info.get("href")
                if href:
                    asset_urls[name] = href

            # Compute remote hash
            hasher = hashlib.sha256()
            hasher.update(json.dumps(properties, sort_keys=True).encode("utf-8"))
            remote_hash = hasher.hexdigest()

            return ArchiveSearchResult(
                scene_id=scene_id,
                source=source,
                acquisition_time=acquisition_time,
                product_level=product_level,
                tile_id=tile_id,
                cloud_score=cloud_score,
                asset_urls=asset_urls,
                metadata=properties,
                remote_hash=remote_hash
            )
        except Exception:
            return None

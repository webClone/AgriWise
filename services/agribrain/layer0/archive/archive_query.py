"""
Partition-based STAC query translator.
Divides long time ranges into smaller partitions (e.g. monthly) to query STAC catalogue reliably.
Parses STAC items into ArchiveSearchResult dataclass.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from .archive_types import ArchiveSearchResult
from .stac_client import STACClient

class ArchiveQueryManager:
    def __init__(self, stac_client: Optional[STACClient] = None):
        self.stac_client = stac_client or STACClient()

    @staticmethod
    def _utc_instant(value: str) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("archive_query_timestamp_required")
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("archive_query_invalid_timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            if len(value.strip()) == 10:
                # Explicit date-only source input means UTC midnight.
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                raise ValueError("archive_query_requires_explicit_timezone")
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _iso_utc(instant: datetime) -> str:
        return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def partition_date_range(self, start_date_str: str, end_date_str: str) -> List[tuple[str, str]]:
        """Partition an exact [start,end) UTC interval at month boundaries.

        Catalogs may treat the end as inclusive. The caller removes such
        duplicates with exact UTC timestamp checks before admitting evidence.
        """
        start = self._utc_instant(start_date_str)
        end = self._utc_instant(end_date_str)
        if end <= start:
            raise ValueError("archive_query_empty_or_reversed_interval")
        partitions = []
        cursor = start
        while cursor < end:
            if cursor.month == 12:
                next_month = datetime(cursor.year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                next_month = datetime(cursor.year, cursor.month + 1, 1, tzinfo=timezone.utc)
            part_end = min(next_month, end)
            partitions.append((self._iso_utc(cursor), self._iso_utc(part_end)))
            cursor = part_end
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
                raise ValueError(f"unsupported_archive_source:{source}")

            for part_start, part_end in partitions:
                items = self.stac_client.search(
                    geometry_geojson=geometry_geojson,
                    start_time=part_start,
                    end_time=part_end,
                    collections=collections
                )
                
                if not isinstance(items, list):
                    raise RuntimeError("stac_incomplete_partition_result")
                left = self._utc_instant(part_start)
                right = self._utc_instant(part_end)
                for item in items:
                    if not isinstance(item, dict):
                        raise RuntimeError("stac_non_mapping_scene_item")
                    scene_id = item.get("id")
                    if not scene_id:
                        raise RuntimeError("stac_scene_id_missing")
                    parsed = self._parse_stac_item(item, source)
                    if parsed is None:
                        raise RuntimeError("stac_scene_metadata_invalid")
                    acquisition = self._utc_instant(parsed.acquisition_time)
                    if not (left <= acquisition < right):
                        # STAC interval endpoints may be inclusive. Do not
                        # leak the next window's scenes into this checkpoint.
                        continue
                    if scene_id in seen_scene_ids:
                        continue
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

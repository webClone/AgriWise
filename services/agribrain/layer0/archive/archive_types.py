"""
Archive schema type contracts.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class ArchiveSearchResult:
    scene_id: str
    source: str
    acquisition_time: str
    product_level: str
    tile_id: Optional[str]
    cloud_score: Optional[float]
    asset_urls: Dict[str, str]
    metadata: Dict[str, Any]
    remote_hash: str

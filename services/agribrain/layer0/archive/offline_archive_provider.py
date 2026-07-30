"""
Offline Archive Provider.
Generates deterministic synthetic fixtures representing different plot history profiles:
  - 8-scene unit test fixture
  - 24-scene gate test fixture (cloudy, noisy, missing bands)
  - 60+ scene benchmark fixture (multi-year timeline 2015-present)
Also mocks CDSE/STAC operations locally.
"""
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import numpy as np

from .archive_types import ArchiveSearchResult

class OfflineArchiveProvider:
    def __init__(self):
        pass

    def _generate_deterministic_hash(self, base_str: str) -> str:
        return hashlib.sha256(base_str.encode("utf-8")).hexdigest()

    def get_unit_test_fixture(self, plot_id: str, geometry_wkt: str) -> List[ArchiveSearchResult]:
        """Generates 8 high-quality Sentinel scenes representing a basic crop season."""
        results = []
        start_date = datetime(2023, 4, 1) # Spring
        
        # 5 Sentinel-2 scenes, 3 Sentinel-1 scenes
        for i in range(8):
            scene_dt = start_date + timedelta(days=i * 15)
            time_str = scene_dt.strftime("%Y-%m-%dT12:00:00Z")
            
            is_s2 = (i % 2 == 0)
            source = "sentinel2" if is_s2 else "sentinel1"
            scene_id = f"mock_{source}_unit_{scene_dt.strftime('%Y%m%d')}_{i}"
            
            cloud_score = 5.0 + float(i * 3) if is_s2 else None
            p_level = "L2A" if is_s2 else "GRD"
            
            # Simulated crop growth trajectory (NDVI peaks around July/scene 6)
            progress = i / 7.0
            ndvi = 0.15 + 0.65 * np.sin(progress * np.pi) # Peak NDVI of 0.8
            
            results.append(ArchiveSearchResult(
                scene_id=scene_id,
                source=source,
                acquisition_time=time_str,
                product_level=p_level,
                tile_id="T31SUD" if is_s2 else None,
                cloud_score=cloud_score,
                asset_urls={
                    "B02": "http://mock/b02", "B03": "http://mock/b03", 
                    "B04": "http://mock/b04", "B08": "http://mock/b08"
                } if is_s2 else {"VV": "http://mock/vv", "VH": "http://mock/vh"},
                metadata={
                    "collection": f"{source}-mock-col",
                    "proj:epsg": "EPSG:32631",
                    "ndvi_simulated": float(ndvi)
                },
                remote_hash=self._generate_deterministic_hash(scene_id)
            ))
            
        return results

    def get_gate_test_fixture(self, plot_id: str, geometry_wkt: str) -> List[ArchiveSearchResult]:
        """
        Generates 24 scenes containing high cloud cover, missing bands,
        noisy values, and extreme incidence angles to stress-test quality filtering.
        """
        results = []
        start_date = datetime(2022, 1, 1)
        
        for i in range(24):
            scene_dt = start_date + timedelta(days=i * 12)
            time_str = scene_dt.strftime("%Y-%m-%dT12:00:00Z")
            
            is_s2 = (i % 3 != 0) # 2/3 are Sentinel-2
            source = "sentinel2" if is_s2 else "sentinel1"
            scene_id = f"mock_{source}_gate_{scene_dt.strftime('%Y%m%d')}_{i}"
            
            # Induce clouds and flaws deterministically
            cloud_score = 0.0
            if is_s2:
                if i % 4 == 0:
                    cloud_score = 85.0 # High clouds (should be filtered)
                elif i % 5 == 0:
                    cloud_score = 35.0 # Moderate clouds
                else:
                    cloud_score = 12.0 # Good scene
                    
            p_level = "L2A" if is_s2 else "GRD"
            if is_s2 and i % 7 == 0:
                p_level = "L1C" # Unharmonized raw level (should score lower)
                
            # Setup asset links. Under i % 6 == 0 S2 is missing red band B04.
            assets = {}
            if is_s2:
                if i % 6 == 0:
                    assets = {"B02": "http://mock/b02", "B03": "http://mock/b03", "B08": "http://mock/b08"} # Missing B04
                else:
                    assets = {"B02": "http://mock/b02", "B03": "http://mock/b03", "B04": "http://mock/b04", "B08": "http://mock/b08"}
            else:
                assets = {"VV": "http://mock/vv", "VH": "http://mock/vh"}

            # Induce abnormal S1 incidence angles on some scenes
            s1_inc_angle = 35.0
            if not is_s2 and i % 5 == 0:
                s1_inc_angle = 15.0 # Out of configurable range (should be flagged)
            elif not is_s2 and i % 8 == 0:
                s1_inc_angle = 55.0 # Out of configurable range
                
            results.append(ArchiveSearchResult(
                scene_id=scene_id,
                source=source,
                acquisition_time=time_str,
                product_level=p_level,
                tile_id="T31SUD" if is_s2 else None,
                cloud_score=cloud_score if is_s2 else None,
                asset_urls=assets,
                metadata={
                    "collection": f"{source}-mock-col",
                    "proj:epsg": "EPSG:32631",
                    "sat:orbit_state": "ascending" if i % 2 == 0 else "descending",
                    "s1_incidence_angle": s1_inc_angle
                },
                remote_hash=self._generate_deterministic_hash(scene_id)
            ))
            
        return results

    def get_benchmark_test_fixture(self, plot_id: str, geometry_wkt: str) -> List[ArchiveSearchResult]:
        """
        Generates 70+ scenes spanning a long multi-year timeline (2015-present)
        to stress-test memory and execution performance limits.
        """
        results = []
        start_date = datetime(2015, 6, 23) # Sentinel-2A launch date roughly
        end_date = datetime(2026, 6, 16)
        
        current_dt = start_date
        index = 0
        while current_dt <= end_date:
            time_str = current_dt.strftime("%Y-%m-%dT12:00:00Z")
            
            # alternate Sentinel-2 and Sentinel-1
            is_s2 = (index % 2 == 0)
            source = "sentinel2" if is_s2 else "sentinel1"
            scene_id = f"mock_{source}_bench_{current_dt.strftime('%Y%m%d')}_{index}"
            
            results.append(ArchiveSearchResult(
                scene_id=scene_id,
                source=source,
                acquisition_time=time_str,
                product_level="L2A" if is_s2 else "GRD",
                tile_id="T31SUD" if is_s2 else None,
                cloud_score=10.0 if is_s2 else None,
                asset_urls={
                    "B02": "http://mock/b02", "B03": "http://mock/b03", 
                    "B04": "http://mock/b04", "B08": "http://mock/b08"
                } if is_s2 else {"VV": "http://mock/vv", "VH": "http://mock/vh"},
                metadata={
                    "collection": f"{source}-mock-col",
                    "proj:epsg": "EPSG:32631"
                },
                remote_hash=self._generate_deterministic_hash(scene_id)
            ))
            
            # S2 repeat cycles: 5 days. S1 repeat: 6/12 days.
            # Let's increment by an average of 15 days to get a realistic multi-year density
            current_dt += timedelta(days=20)
            index += 1
            
        return results

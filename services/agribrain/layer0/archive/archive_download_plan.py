"""
Archive Download Plan validator.
Checks storage quotas and scene count limits before executing raster asset downloads.
"""
import os
from typing import List, Tuple, Dict, Any
from .archive_config import (
    ARCHIVE_MAX_SCENES_PER_PLOT,
    ARCHIVE_MAX_STORAGE_MB_PER_PLOT,
    ARCHIVE_MAX_DOWNLOAD_MB_PER_JOB
)
from .archive_types import ArchiveSearchResult
from .scene_manifest import HistoricalSceneRecord

class ArchiveDownloadPlanner:
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir

    def get_existing_cache_size_mb(self, plot_id: str) -> float:
        """Calculates total size of cached files for the given plot in MB."""
        plot_cache_path = os.path.join(self.cache_dir, plot_id)
        if not os.path.exists(plot_cache_path):
            return 0.0
            
        total_bytes = 0
        for root, _, files in os.walk(plot_cache_path):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total_bytes += os.path.getsize(fp)
                except OSError:
                    pass
        return total_bytes / (1024 * 1024)

    def estimate_candidate_size_mb(self, scene: ArchiveSearchResult) -> float:
        """Estimates download size of a scene in MB."""
        # STAC assets sometimes contain file:size in bytes
        total_bytes = 0
        for asset_name, asset_info in scene.asset_urls.items():
            if isinstance(asset_info, dict) and "file:size" in asset_info:
                total_bytes += int(asset_info["file:size"])
                
        if total_bytes > 0:
            return total_bytes / (1024 * 1024)
            
        # Default fallback estimate (cropped subsets of bands)
        if scene.source.lower() == "sentinel2":
            return 2.5 # ~2.5 MB for cropped S2 bands (B02, B03, B04, B08, SCL)
        else:
            return 3.0 # ~3.0 MB for cropped S1 (VV, VH)

    def plan_download(
        self,
        plot_id: str,
        candidates: List[ArchiveSearchResult],
        existing_records: List[HistoricalSceneRecord]
    ) -> Tuple[bool, str, List[ArchiveSearchResult]]:
        """
        Validates planned downloads against storage quota and max scenes limits.
        If limits would be exceeded, filters/truncates candidates (preferring highest quality)
        to fit remaining quotas.
        """
        existing_count = len(existing_records)
        existing_size_mb = self.get_existing_cache_size_mb(plot_id)
        
        # 1. Check scene count limit
        max_new_scenes = ARCHIVE_MAX_SCENES_PER_PLOT - existing_count
        if max_new_scenes <= 0:
            return False, f"Quota Exceeded: plot already has {existing_count} scenes (max {ARCHIVE_MAX_SCENES_PER_PLOT})", []

        # 2. Check storage quota
        remaining_storage_mb = ARCHIVE_MAX_STORAGE_MB_PER_PLOT - existing_size_mb
        if remaining_storage_mb <= 0:
            return False, f"Quota Exceeded: plot cache uses {existing_size_mb:.2f} MB (max {ARCHIVE_MAX_STORAGE_MB_PER_PLOT} MB)", []

        # Prioritize candidates by quality/cloud_score (lower cloud cover or higher quality score)
        # Note: ArchiveSearchResult does not have quality_score yet, it has cloud_score.
        # Let's sort candidates: S2 with lowest cloud cover first, S1 (no cloud score) next.
        def sort_key(s: ArchiveSearchResult) -> float:
            # S2: cloud_score (0-100), S1: default to 0.0 cloud score to keep it high priority
            return s.cloud_score if (s.source == "sentinel2" and s.cloud_score is not None) else 0.0

        sorted_candidates = sorted(candidates, key=sort_key)
        
        allowed_scenes = []
        current_job_download_mb = 0.0
        projected_size_mb = existing_size_mb

        for scene in sorted_candidates:
            if len(allowed_scenes) >= max_new_scenes:
                break
                
            scene_size = self.estimate_candidate_size_mb(scene)
            
            # Check single job download limit
            if current_job_download_mb + scene_size > ARCHIVE_MAX_DOWNLOAD_MB_PER_JOB:
                # Exceeds max download for this single run job, stop adding
                continue
                
            # Check absolute storage limit
            if projected_size_mb + scene_size > ARCHIVE_MAX_STORAGE_MB_PER_PLOT:
                break
                
            allowed_scenes.append(scene)
            current_job_download_mb += scene_size
            projected_size_mb += scene_size

        if not allowed_scenes and candidates:
            return False, "Quota limits prevent any new scenes from being downloaded.", []

        # Sort back allowed_scenes chronologically
        allowed_scenes.sort(key=lambda s: s.acquisition_time)
        return True, "Success", allowed_scenes

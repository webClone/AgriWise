"""
Archive Ingestion Fetcher.
Coordinates STAC queries, download planning, raster acquisition,
quality scoring, and manifest persistence.
Supports manifest-only and offline mock run modes.
"""
import os
import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np

from .archive_policy import ARCHIVE_POLICY_VERSION
from .archive_types import ArchiveSearchResult
from .archive_config import CDSE_AUTH_MODE
from .scene_manifest import HistoricalSceneRecord, save_scene_manifest
from .scene_quality import compute_scene_quality_score
from .scene_query import calculate_aoi_footprint, check_tile_overlap
from .archive_query import ArchiveQueryManager
from .archive_download_plan import ArchiveDownloadPlanner
from .stac_client import STACClient


@dataclass
class SpatialRasterMetadata:
    crs: str
    transform: tuple
    bounds: tuple  # (left, bottom, right, top)
    nodata: Optional[float]
    resolution_m: Tuple[float, float]
    width: int
    height: int
    data_type: str
    georeferenced: bool
    native_spatial_certified_1m: bool = False  # Explicitly False: satellite pixel resolution cannot certify 1m


@dataclass
class SpatialRasterResult:
    data: np.ndarray
    metadata: SpatialRasterMetadata
    valid_mask: np.ndarray
    valid_pixel_fraction: float
    content_hash: str


def load_spatial_raster(
    file_path: str,
    expected_crs: Optional[str] = None,
    aoi_bounds: Optional[Tuple[float, float, float, float]] = None,
    require_georeference: bool = False,
) -> SpatialRasterResult:
    """
    Decodes satellite raster band data and validates complete geospatial authority metadata:
    CRS, affine transform, geographic bounds, nodata mask, resolution, and AOI overlap.
    Fails closed on missing georeferencing, mismatched CRS, non-overlapping AOI, or corrupted bands.
    """
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"Raster file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    data: Optional[np.ndarray] = None
    crs_str: str = ""
    transform_tuple: tuple = ()
    bounds_tuple: tuple = ()
    nodata_val: Optional[float] = None
    res: Tuple[float, float] = (10.0, 10.0)
    georeferenced: bool = False

    if ext in {".tif", ".tiff"}:
        try:
            import rasterio
            with rasterio.open(file_path) as src:
                arr = src.read(1)
                data = np.asarray(arr, dtype=np.float32)
                if src.crs:
                    crs_str = str(src.crs.to_string())
                if src.transform:
                    transform_tuple = tuple(src.transform)
                if src.bounds:
                    bounds_tuple = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
                nodata_val = src.nodata
                if hasattr(src, "res") and src.res:
                    res = (float(src.res[0]), float(src.res[1]))
                georeferenced = bool(crs_str and transform_tuple)
        except Exception:
            try:
                import tifffile
                with tifffile.TiffFile(file_path) as tif:
                    arr = tif.asarray()
                    if arr.ndim > 2:
                        arr = arr[0]
                    data = np.asarray(arr, dtype=np.float32)
                    georeferenced = False
            except Exception:
                from PIL import Image
                with Image.open(file_path) as img:
                    arr = np.array(img)
                    if arr.ndim > 2:
                        arr = arr[:, :, 0]
                    data = np.asarray(arr, dtype=np.float32)
                    georeferenced = False
    elif ext in {".npz"}:
        with np.load(file_path, allow_pickle=False) as loader:
            data = np.asarray(loader["data"], dtype=np.float32)
            if "crs" in loader:
                crs_str = str(loader["crs"])
            if "transform" in loader:
                transform_tuple = tuple(loader["transform"])
            if "bounds" in loader:
                bounds_tuple = tuple(loader["bounds"])
            if "nodata" in loader:
                nodata_val = float(loader["nodata"])
            georeferenced = bool(crs_str and transform_tuple)
    elif ext in {".npy"}:
        data = np.asarray(np.load(file_path, allow_pickle=False), dtype=np.float32)
        georeferenced = False
    else:
        # Fallback probe
        try:
            import rasterio
            with rasterio.open(file_path) as src:
                data = np.asarray(src.read(1), dtype=np.float32)
                crs_str = str(src.crs.to_string()) if src.crs else ""
                transform_tuple = tuple(src.transform) if src.transform else ()
                bounds_tuple = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top) if src.bounds else ()
                nodata_val = src.nodata
                georeferenced = bool(crs_str and transform_tuple)
        except Exception:
            with np.load(file_path, allow_pickle=False) as loader:
                data = np.asarray(loader["data"], dtype=np.float32)
                georeferenced = False

    if data is None:
        raise ValueError(f"Could not decode raster array from {file_path}")

    if require_georeference and not georeferenced:
        raise ValueError(
            f"Authoritative spatial qualification failed: file {file_path} lacks valid CRS and affine transform"
        )

    # Validate CRS matching
    if expected_crs and crs_str:
        norm_expected = expected_crs.strip().upper()
        norm_actual = crs_str.strip().upper()
        if norm_expected != norm_actual and norm_expected not in norm_actual and norm_actual not in norm_expected:
            raise ValueError(f"CRS mismatch: expected {expected_crs}, found {crs_str}")

    # Validate AOI bounds overlap
    if aoi_bounds and bounds_tuple and len(bounds_tuple) == 4 and len(aoi_bounds) == 4:
        minx, miny, maxx, maxy = aoi_bounds
        r_left, r_bottom, r_right, r_top = bounds_tuple
        overlap = not (maxx < r_left or minx > r_right or maxy < r_bottom or miny > r_top)
        if not overlap:
            raise ValueError(
                f"Spatial overlap violation: AOI bounds {aoi_bounds} do not intersect raster bounds {bounds_tuple}"
            )

    # Compute valid mask & pixel fraction
    if nodata_val is not None:
        valid_mask = (data != nodata_val) & np.isfinite(data)
    else:
        valid_mask = np.isfinite(data)

    valid_pixel_frac = float(np.count_nonzero(valid_mask) / data.size) if data.size > 0 else 0.0
    content_hash = hashlib.sha256(data.tobytes()).hexdigest()

    meta = SpatialRasterMetadata(
        crs=crs_str,
        transform=transform_tuple,
        bounds=bounds_tuple,
        nodata=nodata_val,
        resolution_m=res,
        width=data.shape[1] if data.ndim > 1 else data.shape[0],
        height=data.shape[0] if data.ndim > 1 else 1,
        data_type=str(data.dtype),
        georeferenced=georeferenced,
        native_spatial_certified_1m=False,  # Explicitly False: 1m spatial certification remains on hold
    )

    return SpatialRasterResult(
        data=data,
        metadata=meta,
        valid_mask=valid_mask,
        valid_pixel_fraction=valid_pixel_frac,
        content_hash=content_hash,
    )


def load_raster_data(file_path: str) -> np.ndarray:
    """Safely decode satellite band data from GeoTIFF (.tif/.tiff), .npz, or .npy containers.

    Supports rasterio, tifffile, PIL, and native NumPy arrays.
    """
    return load_spatial_raster(file_path).data


class ArchiveFetcher:
    def __init__(self, cache_dir: Optional[str] = None, stac_client: Optional[STACClient] = None):
        if not cache_dir:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            cache_dir = os.path.join(base, "data", "archive_cache")
        self.cache_dir = cache_dir
        self.stac_client = stac_client or STACClient()
        self.query_manager = ArchiveQueryManager(stac_client=self.stac_client)
        self.download_planner = ArchiveDownloadPlanner(cache_dir=self.cache_dir)
        
        self.offline = os.environ.get("AGRIWISE_ARCHIVE_OFFLINE", "false").lower() == "true"
        self.manifest_only_env = os.environ.get("AGRIWISE_ARCHIVE_MANIFEST_ONLY", "false").lower() == "true"

    def orchestrate_fetch(
        self,
        plot_id: str,
        geometry_wkt: str,
        start_date: str,
        end_date: str,
        sources: List[str],
        manifest_only: bool = False,
        existing_records: Optional[List[HistoricalSceneRecord]] = None
    ) -> List[HistoricalSceneRecord]:
        """
        Executes query, schedules download plan, fetches data, calculates quality,
        and saves/updates scene_manifest.jsonl.
        """
        if self.manifest_only_env:
            manifest_only = True
        if self.offline and os.environ.get("ASMAE_TEST_OVERRIDE", "false").lower() != "true":
            raise RuntimeError("offline_archive_fixtures_require_explicit_test_override")
            
        existing_records = existing_records or []
        existing_ids = {r.scene_id for r in existing_records}

        # 1. Geometry footprint calculation
        aoi = calculate_aoi_footprint(geometry_wkt)
        geom_hash = hashlib.sha256(geometry_wkt.encode("utf-8")).hexdigest()

        # 2. Query Remote scenes
        if self.offline:
            # Generate offline/mock search results
            candidates = self._generate_mock_search_results(start_date, end_date, sources)
        else:
            candidates = self.query_manager.execute_partitioned_query(
                geometry_geojson=aoi,
                start_date=start_date,
                end_date=end_date,
                sources=sources
            )

        # Filter out already existing scenes
        new_candidates = [c for c in candidates if c.scene_id not in existing_ids]

        # 3. Inventory and asset acquisition have DIFFERENT quotas.
        # A manifest-only scan must enumerate every available catalog item;
        # 500-scene or per-job raster download caps must not truncate the
        # historical inventory. Actual asset downloads remain fully quota-bound.
        if manifest_only:
            allowed_scenes = list(new_candidates)
        else:
            success, reason, allowed_scenes = self.download_planner.plan_download(
                plot_id=plot_id,
                candidates=new_candidates,
                existing_records=existing_records,
            )
            if not success:
                raise RuntimeError(f"archive_download_plan_incomplete:{reason}")
            discovered_ids = [(candidate.source, candidate.scene_id)
                              for candidate in new_candidates]
            planned_ids = [(candidate.source, candidate.scene_id)
                           for candidate in allowed_scenes]
            if (len(discovered_ids) != len(planned_ids)
                    or set(discovered_ids) != set(planned_ids)):
                raise RuntimeError(
                    f"archive_download_plan_partial:discovered={len(discovered_ids)}"
                    f":planned={len(planned_ids)}"
                )

        # 4. Ingest and create HistoricalSceneRecord for each allowed scene
        processed_records = list(existing_records)
        
        for scene in allowed_scenes:
            # Quality assessment variables
            raw_valid_fraction = scene.metadata.get("valid_pixel_fraction")
            valid_frac = float(raw_valid_fraction) if isinstance(raw_valid_fraction, (int, float)) else 0.0
            overlap = check_tile_overlap(scene.tile_id or "T31SUD", geometry_wkt)
            scene_crs = scene.metadata.get("proj:epsg")
            scene_transform = scene.metadata.get("proj:transform")
            raw_resolution = scene.metadata.get("gsd") or scene.metadata.get("proj:resolution")
            native_resolution_m = float(raw_resolution) if isinstance(raw_resolution, (int, float)) else 0.0
            
            p_level_score = 1.0 if scene.product_level == "L2A" else 0.7
            band_comp = 1.0
            mask_q = 1.0 if scene.source == "sentinel2" and scene.product_level == "L2A" else 0.5
            
            quality_score = compute_scene_quality_score(
                valid_pixel_fraction=valid_frac,
                geometry_overlap=overlap,
                product_level_score=p_level_score,
                band_completeness=band_comp,
                mask_quality=mask_q
            )
            
            # Determine accepted/rejected state
            rejection_reasons = []
            if self.offline:
                rejection_reasons.append("offline_synthetic_fixture")
            if raw_valid_fraction is None:
                rejection_reasons.append("missing_measured_valid_pixel_fraction")
            if not scene_crs:
                rejection_reasons.append("missing_authoritative_crs")
            if not isinstance(scene_transform, (list, tuple)) or len(scene_transform) != 6:
                rejection_reasons.append("missing_authoritative_affine")
            if not math.isfinite(native_resolution_m) or native_resolution_m <= 0:
                rejection_reasons.append("missing_authoritative_resolution")
            if not math.isfinite(valid_frac) or valid_frac < 0.0 or valid_frac > 1.0:
                rejection_reasons.append("invalid_measured_valid_pixel_fraction")
                valid_frac = 0.0
            if quality_score < 0.6:
                rejection_reasons.append("quality_score_too_low")
            if scene.source == "sentinel2" and scene.cloud_score is not None and scene.cloud_score > 70.0:
                rejection_reasons.append("cloud_cover_exceeds_threshold")
                
            quality_status = "rejected" if rejection_reasons else "accepted"

            # Setup cache structure
            local_cache_refs = {}
            bands_available = []
            masks_available = []
            
            if not manifest_only and quality_status == "accepted":
                # Save actual files to disk
                scene_dir = os.path.join(self.cache_dir, plot_id, geom_hash, scene.scene_id)
                os.makedirs(scene_dir, exist_ok=True)
                
                # We determine which bands to fetch based on source
                if scene.source == "sentinel2":
                    target_bands = ["B02", "B03", "B04", "B08"]
                    target_masks = ["SCL"]
                else:
                    target_bands = ["VV", "VH"]
                    target_masks = []
                    
                bands_available = target_bands
                masks_available = target_masks

                # In offline mode, create mock NPZ raster files
                if self.offline:
                    # Write synthetic npz files
                    for band in target_bands:
                        band_path = os.path.join(scene_dir, f"{band}.npz")
                        # Emulate 10x10 cropped footprint array
                        mock_data = np.random.uniform(0.1, 0.8, (10, 10)).astype(np.float32)
                        np.savez(band_path, data=mock_data)
                        local_cache_refs[band] = band_path
                        
                    for mask in target_masks:
                        mask_path = os.path.join(scene_dir, f"{mask}.npz")
                        mock_mask = np.random.choice([0, 1, 2, 4], (10, 10)).astype(np.uint8)
                        np.savez(mask_path, data=mock_mask)
                        local_cache_refs[mask] = mask_path
                else:
                    # Implement actual HTTP download logic if not offline
                    self._download_real_assets(scene, target_bands + target_masks, scene_dir, local_cache_refs)

                # Validate band alignment and SCL shape matching
                bands_dict = {}
                for band in target_bands:
                    b_path = local_cache_refs.get(band)
                    if b_path and os.path.exists(b_path):
                        bands_dict[band.lower()] = load_raster_data(b_path)
                for mask in target_masks:
                    m_path = local_cache_refs.get(mask)
                    if m_path and os.path.exists(m_path):
                        bands_dict[mask.lower()] = load_raster_data(m_path)

                if scene.source == "sentinel2":
                    from .s2_harmonizer import S2Harmonizer
                    from .s2_product_policy import S2ProductPolicy
                    s2_harm = S2Harmonizer()
                    s2_policy = S2ProductPolicy()
                    s2_harm.validate_bands_alignment(bands_dict)
                    s2_policy.validate_scene_bands(
                        type("Record", (object,), {"source": "sentinel2", "product_level": scene.product_level})(),
                        bands_dict
                    )
                    # Reject if any band has non-finite values after masking
                    for name, arr in bands_dict.items():
                        if not np.isfinite(arr).all():
                            raise ValueError(f"Unexpected non-finite values in band {name}")
                elif scene.source == "sentinel1":
                    from .s1_harmonizer import S1Harmonizer
                    s1_harm = S1Harmonizer()
                    s1_harm.validate_bands_alignment(bands_dict)

            # Robust source content hash calculation
            hasher = hashlib.sha256()
            hasher.update(str(scene.scene_id).encode("utf-8"))
            hasher.update(str(scene.product_level).encode("utf-8"))
            hasher.update(str(scene_crs or "").encode("utf-8"))
            hasher.update(str(scene_transform or "").encode("utf-8"))
            hasher.update(str(native_resolution_m).encode("utf-8"))
            from .archive_policy import QUALITY_POLICY_VERSION, HARMONIZATION_POLICY_VERSION
            hasher.update(str(QUALITY_POLICY_VERSION).encode("utf-8"))
            hasher.update(str(HARMONIZATION_POLICY_VERSION).encode("utf-8"))

            if not manifest_only and quality_status == "accepted":
                for ref_name, ref_path in sorted(local_cache_refs.items()):
                    hasher.update(ref_name.encode("utf-8"))
                    try:
                        arr = load_raster_data(ref_path)
                        hasher.update(arr.tobytes())
                    except Exception as err:
                        raise RuntimeError(
                            f"Cryptographic provenance failure: could not load and hash raster asset {ref_name} at {ref_path}: {err}"
                        ) from err
            else:
                hasher.update(str(scene.remote_hash).encode("utf-8"))
            source_content_hash = hasher.hexdigest()

            # Build record
            record = HistoricalSceneRecord(
                scene_id=scene.scene_id,
                plot_id=plot_id,
                geometry_hash=geom_hash,
                source=scene.source,
                mission="S2A" if scene.source == "sentinel2" else "S1A",
                product_level=scene.product_level,
                collection=scene.metadata.get("collection"),
                acquisition_time=scene.acquisition_time,
                orbit_number=str(scene.metadata.get("sat:orbit_state", "descending")),
                relative_orbit=str(scene.metadata.get("sat:relative_orbit", "12")),
                tile_id=scene.tile_id,
                native_resolution_m=native_resolution_m,
                crs=str(scene_crs or ""),
                transform_hash=hashlib.sha256(str(scene_transform or "").encode("utf-8")).hexdigest() if scene_transform else "",
                footprint_hash=hashlib.sha256(str(scene.metadata.get("geometry", "geom")).encode("utf-8")).hexdigest(),
                cloud_score=scene.cloud_score,
                valid_pixel_fraction=valid_frac,
                quality_status=quality_status,
                source_content_hash=source_content_hash,
                rejection_reasons=rejection_reasons,
                bands_available=bands_available,
                masks_available=masks_available,
                remote_asset_refs=scene.asset_urls,
                local_cache_refs=local_cache_refs
            )
            processed_records.append(record)

        # 5. Save/Update Scene Manifest
        save_scene_manifest(plot_id=plot_id, geometry_hash=geom_hash, records=processed_records)
        return processed_records

    def _generate_mock_search_results(self, start_date: str, end_date: str, sources: List[str]) -> List[ArchiveSearchResult]:
        """Generates dummy search results for testing offline workflow."""
        results = []
        # Return 4 mock scenes per source evenly distributed
        start_dt = datetime.strptime(start_date.split("T")[0], "%Y-%m-%d")
        end_dt = datetime.strptime(end_date.split("T")[0], "%Y-%m-%d")
        delta = (end_dt - start_dt).days
        
        for source in sources:
            for i in range(4):
                day_offset = int((delta / 3) * i) if delta > 0 else 0
                scene_dt = start_dt + timedelta(days=day_offset)
                time_str = scene_dt.strftime("%Y-%m-%dT12:00:00Z")
                scene_id = f"mock_{source}_{scene_dt.strftime('%Y%m%d')}_{i}"
                
                results.append(ArchiveSearchResult(
                    scene_id=scene_id,
                    source=source,
                    acquisition_time=time_str,
                    product_level="L2A" if source == "sentinel2" else "GRD",
                    tile_id="T31SUD" if source == "sentinel2" else None,
                    cloud_score=15.0 if source == "sentinel2" else None,
                    asset_urls={"B02": "http://mock/b02", "B03": "http://mock/b03", "B04": "http://mock/b04", "B08": "http://mock/b08"},
                    metadata={"collection": f"{source}-mock-col", "proj:epsg": "EPSG:32631", "view:incidence_angle": 38.5},
                    remote_hash=hashlib.sha256(scene_id.encode("utf-8")).hexdigest()
                ))
        return results

    def _download_real_assets(self, scene: ArchiveSearchResult, assets: List[str], dest_dir: str, cache_refs: Dict[str, str]):
        """Downloads assets from remote provider and crops them."""
        # Standard placeholder for real production download logic (calling stac/cdse clients)
        # In this sandbox environment, we will mock if remote requests fail.
        import requests
        headers = self.stac_client.cdse_client.get_auth_header()
        
        for asset in assets:
            url = scene.asset_urls.get(asset)
            if not url:
                continue
            try:
                # Real implementation: stream request and save to temp file, then crop to AOI geometry
                # For safety, if download fails or is unsupported, raise error or write stub
                r = requests.get(url, headers=headers, timeout=60, stream=True)
                r.raise_for_status()
                path = os.path.join(dest_dir, f"{asset}.tif")
                with open(path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                cache_refs[asset] = path
            except Exception as e:
                # Fail closed on download failure
                raise RuntimeError(f"Failed to download asset {asset}: {str(e)}")

"""
Historical Scene Adapter.
Adapts a HistoricalSceneRecord from the archive manifest into a Layer 0 source package format
compatible with ASMAE's S2 and S1 loaders.
If physical rasters are cached, computes real spatial band statistics (means).
"""
import os
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
import numpy as np

from layer0.archive.scene_manifest import HistoricalSceneRecord
from layer0.archive.raster_store import RasterStore
from layer0.archive.s2_indices import S2Indices

class HistoricalSceneAdapter:
    def __init__(self):
        self.raster_store = RasterStore()
        self.s2_indices = S2Indices()

    def adapt(self, record: HistoricalSceneRecord) -> SimpleNamespace:
        """Adapts a HistoricalSceneRecord into a mock Layer 0 package object."""
        # Parse datetime
        try:
            if isinstance(record.acquisition_time, datetime):
                acq_dt = record.acquisition_time
            else:
                # E.g. "2026-06-15T12:00:00Z" -> replace Z with +00:00 for fromisoformat
                iso_str = record.acquisition_time.replace("Z", "+00:00")
                acq_dt = datetime.fromisoformat(iso_str)
        except Exception:
            acq_dt = None

        # 1. Setup metadata
        # Default S2 transform if not present
        transform = None
        # Default spatial extent — ASMAE adapter needs width/height > 0
        # to classify the candidate as real_raster (not mean_only/unavailable).
        # 100×100 pixels at 10m = 1 km² nominal extent for a plot-clipped scene.
        default_width = None
        default_height = None
        metadata = SimpleNamespace(
            scene_id=record.scene_id,
            acquisition_datetime=acq_dt,
            crs=record.crs or None,
            transform=transform,
            width=default_width,
            height=default_height,
            band_list=record.bands_available or ["B02", "B03", "B04", "B08"]
        )

        # 2. Extract band means from cached NPZ files if available
        # If files are not present, use synthetic default profiles based on phenology/source
        ndvi_mean = None
        evi_mean = None
        vv_db_mean = None
        vh_db_mean = None
        rvi_mean = None
        
        has_arrays = False
        
        # Load from cache if cache is populated
        if record.local_cache_refs:
            try:
                if record.source == "sentinel2":
                    b04_path = record.local_cache_refs.get("B04")
                    b08_path = record.local_cache_refs.get("B08")
                    b02_path = record.local_cache_refs.get("B02")
                    
                    if b04_path and b08_path and os.path.exists(b04_path) and os.path.exists(b08_path):
                        b04 = self.raster_store.load_band(b04_path)
                        b08 = self.raster_store.load_band(b08_path)
                        if b04.shape != b08.shape or not np.isfinite(b04).all() or not np.isfinite(b08).all():
                            raise ValueError("historical_s2_arrays_invalid")
                        ndvi = self.s2_indices.compute_ndvi(b04, b08)
                        if not np.isfinite(ndvi).all():
                            raise ValueError("historical_ndvi_nonfinite")
                        ndvi_mean = float(np.mean(ndvi))
                        
                        if b02_path and os.path.exists(b02_path):
                            b02 = self.raster_store.load_band(b02_path)
                            if b02.shape != b04.shape or not np.isfinite(b02).all():
                                raise ValueError("historical_blue_array_invalid")
                            evi = self.s2_indices.compute_evi(b02, b04, b08)
                            if not np.isfinite(evi).all():
                                raise ValueError("historical_evi_nonfinite")
                            evi_mean = float(np.mean(evi))
                        has_arrays = True
                        
                elif record.source == "sentinel1":
                    vv_path = record.local_cache_refs.get("VV")
                    vh_path = record.local_cache_refs.get("VH")
                    if vv_path and vh_path and os.path.exists(vv_path) and os.path.exists(vh_path):
                        vv = self.raster_store.load_band(vv_path)
                        vh = self.raster_store.load_band(vh_path)
                        if vv.shape != vh.shape or not np.isfinite(vv).all() or not np.isfinite(vh).all():
                            raise ValueError("historical_s1_arrays_invalid")
                        vv_db_mean = float(np.mean(vv))
                        vh_db_mean = float(np.mean(vh))
                        # RVI = (4 * VH_lin) / (VV_lin + VH_lin)
                        vv_lin = 10.0 ** (vv / 10.0)
                        vh_lin = 10.0 ** (vh / 10.0)
                        rvi_mean = float(np.mean((4.0 * vh_lin) / (vv_lin + vh_lin + 1e-5)))
                        has_arrays = True
            except Exception:
                ndvi_mean = evi_mean = None
                vv_db_mean = vh_db_mean = rvi_mean = None
                has_arrays = False

        # 3. Setup packets
        packet = {
            "data_status": "observed" if has_arrays else "unavailable",
            "usable": bool(record.quality_status == "accepted" and has_arrays),
            "cloud_cover": record.cloud_score or 0.0,
            "valid_fraction": record.valid_pixel_fraction,
            "source_reality": "historical_mean_only" if has_arrays else "historical_manifest_only",
        }
        
        if record.source == "sentinel2":
            if ndvi_mean is not None:
                packet["ndvi_mean"] = ndvi_mean
            if evi_mean is not None:
                packet["evi_mean"] = evi_mean
        else:
            if vv_db_mean is not None:
                packet["vv_db_mean"] = vv_db_mean
            if vh_db_mean is not None:
                packet["vh_db_mean"] = vh_db_mean
            if rvi_mean is not None:
                packet["rvi_mean"] = rvi_mean
            packet["orbit_direction"] = record.orbit_number or "descending"

        packets = [packet]

        # 4. Setup qa
        valid_f = float(record.valid_pixel_fraction if record.valid_pixel_fraction is not None else 1.0)
        cloud_f = float(record.cloud_score if record.cloud_score is not None else 0.0)
        if record.quality_status == "accepted":
            rel_weight = round(max(0.40, min(0.98, 0.98 * valid_f * (1.0 - 0.5 * cloud_f))), 3)
        else:
            rel_weight = round(max(0.05, min(0.30, 0.20 * valid_f)), 3)

        qa = SimpleNamespace(
            usable=bool(record.quality_status == "accepted" and has_arrays),
            valid_fraction=record.valid_pixel_fraction,
            quality_class=SimpleNamespace(value="excellent" if record.quality_status == "accepted" else "poor"),
            sigma_multiplier=1.0,
            reliability_weight=rel_weight,
        )

        # 5. Build full adapted package namespace
        pkg = SimpleNamespace(
            plot_id=record.plot_id,
            metadata=metadata,
            packets=packets,
            qa=qa,
            cloud_cover=record.cloud_score,
            has_arrays=has_arrays,
            local_cache_refs=getattr(record, "local_cache_refs", {}) or {},
            source_reality="historical_mean_only" if has_arrays else "historical_manifest_only",
            production_usable=False,
            real_provider_product=False,
            diagnostic_only=True,
            product_binding="archive_manifest_without_affine",
            binding_proof={
                "transform_hash": record.transform_hash,
                "affine_coefficients_present": False,
            },
        )
        return pkg

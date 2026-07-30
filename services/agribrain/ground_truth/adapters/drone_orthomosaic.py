"""
AgriBrain V57 Drone Orthomosaic Ground Truth Adapter.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import rasterio
from ground_truth.schemas import GroundTruthEvidence


class DroneOrthomosaicAdapter:
    """
    Ingests and validates physical GeoTIFF drone orthomosaics on disk using rasterio,
    extracting dynamic spatial coordinates, GSD, and Coordinate Reference Systems.
    """

    @staticmethod
    def load_from_file(
        file_path: str,
        source_id: str,
        timestamp: datetime,
        georegistration_rmse_m: float = 0.12,
        plot_coverage_pct: float = 85.0
    ) -> GroundTruthEvidence:
        """
        Backward compatible fallback router calling load_from_files.
        """
        return DroneOrthomosaicAdapter.load_from_files(
            [file_path], source_id, timestamp, georegistration_rmse_m, plot_coverage_pct
        )

    @staticmethod
    def load_from_files(
        file_paths: List[str],
        source_id: str,
        timestamp: datetime,
        georegistration_rmse_m: float = 0.12,
        plot_coverage_pct: float = 85.0
    ) -> GroundTruthEvidence:
        """
        Ingests and validates a tiled list of physical GeoTIFF drone orthomosaics on disk using rasterio,
        verifying CRS consistency, GSD consistency, and non-overlapping tile bounds.
        """
        tiles_data = []
        crs_consistency = None
        gsd_consistency = None
        
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"Drone Orthomosaic GeoTIFF not found: {file_path}")

            with rasterio.open(path) as src:
                width = src.width
                height = src.height
                crs_name = src.crs.to_string() if src.crs else "unknown"
                transform = src.transform
                
                gsd_x = abs(transform[0])
                gsd_y = abs(transform[4])
                gsd_m = float((gsd_x + gsd_y) / 2.0)
                
                # Bounding box in metric UTM units
                xmin = transform[2]
                xmax = xmin + width * transform[0]
                ymax = transform[5]
                ymin = ymax + height * transform[4]
                
            # Verify basic GSD gate
            if not (0.01 <= gsd_m <= 0.10):
                raise ValueError("ground_truth_missing_geometry")
            
            # CRS consistency check
            if crs_consistency is None:
                crs_consistency = crs_name
            else:
                if crs_consistency != crs_name:
                    raise ValueError("ground_truth_missing_geometry")
                
            # GSD consistency check
            if gsd_consistency is None:
                gsd_consistency = round(gsd_m, 4)
            else:
                if gsd_consistency != round(gsd_m, 4):
                    raise ValueError("ground_truth_missing_geometry")
                
            tiles_data.append({
                "path": file_path,
                "width": width,
                "height": height,
                "gsd_m": gsd_m,
                "bounds": (xmin, ymin, xmax, ymax),
                "area_m2": width * height * gsd_m * gsd_m
            })

        # Bounding box non-overlap check
        for i in range(len(tiles_data)):
            for j in range(i + 1, len(tiles_data)):
                box_a = tiles_data[i]["bounds"]
                box_b = tiles_data[j]["bounds"]
                
                overlap_x = max(0.0, min(box_a[2], box_b[2]) - max(box_a[0], box_b[0]))
                overlap_y = max(0.0, min(box_a[3], box_b[3]) - max(box_a[1], box_b[1]))
                overlap_area = overlap_x * overlap_y
                
                if overlap_area != 0.0:
                    raise ValueError("ground_truth_missing_geometry")

        total_area_m2 = float(sum(t["area_m2"] for t in tiles_data))
        crs_name = crs_consistency or "unknown"
        gsd_m = gsd_consistency or 0.03

        return GroundTruthEvidence(
            source_id=source_id,
            source_type="drone_orthomosaic",
            scope="raster",
            timestamp=timestamp,
            geometry={
                "type": "MultiPolygon",
                "tile_bounds": [t["bounds"] for t in tiles_data],
                "crs": crs_name
            },
            resolution_m=gsd_m,
            confidence=0.98 if georegistration_rmse_m <= 0.15 else 0.85,
            validation_targets=["crop_rows", "plant_gaps", "weed_patches", "irrigation_boundaries"],
            can_boost_1m=True,
            can_boost_3cm=True,
            can_block_certification=True,
            state_update_allowed=False,  # Strictly blocked from Layer 2 updates
            payload_ref=f"cov_{plot_coverage_pct}_rmse_{georegistration_rmse_m}_tiled_{len(file_paths)}_area_{total_area_m2}_crs_{crs_name}",
            resolution_origin="external_ground_truth",
            resolution_role="validation_anchor",
            asset_origin="persistent_fixture_file",
            asset_generation_mode="compiled_from_existing_fixture",
            direct_field_capture=False
        )

    @staticmethod
    def create_evidence(
        source_id: str,
        timestamp: datetime,
        gsd_m: float = 0.03,
        georegistration_rmse_m: float = 0.12,
        plot_coverage_pct: float = 85.0
    ) -> GroundTruthEvidence:
        """
        Backward compatible fallback evidence generator.
        """
        return GroundTruthEvidence(
            source_id=source_id,
            source_type="drone_orthomosaic",
            scope="raster",
            timestamp=timestamp,
            geometry={
                "type": "MultiPolygon",
                "tile_bounds": [
                    (300000.0, 3799850.0, 300150.0, 3800000.0),
                    (300150.0, 3799850.0, 300300.0, 3800000.0),
                    (300000.0, 3799700.0, 300150.0, 3799850.0),
                    (300150.0, 3799700.0, 300300.0, 3799850.0)
                ],
                "crs": "EPSG:32632"
            },
            resolution_m=gsd_m,
            confidence=0.98 if georegistration_rmse_m <= 0.15 else 0.85,
            validation_targets=["crop_rows", "plant_gaps", "weed_patches", "irrigation_boundaries"],
            can_boost_1m=True,
            can_boost_3cm=True,
            can_block_certification=True,
            state_update_allowed=False,
            payload_ref=f"cov_{plot_coverage_pct}_rmse_{georegistration_rmse_m}_tiled_4_area_90000.0_crs_EPSG:32632",
            resolution_origin="external_ground_truth",
            resolution_role="validation_anchor",
            asset_origin="persistent_fixture_file",
            asset_generation_mode="compiled_from_existing_fixture",
            direct_field_capture=False
        )



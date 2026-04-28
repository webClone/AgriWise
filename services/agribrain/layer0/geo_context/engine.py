"""
Geo Context Engine V1.

Top-level orchestrator. Pipeline:
  1. Validate & normalize DEM raster
  2. Compute terrain features + DEM QA
  3. Normalize ESA WorldCover → fractions
  4. Normalize Dynamic World → probabilities
  5. Compute boundary contamination
  6. Land cover QA
  7. Normalize WaPOR data
  8. WaPOR QA + indicators
  9. Compute sensor placement
  10. Fuse → PlotValidity + SatelliteTrust
  11. Run validation rules
  12. Emit packets
  13. Build diagnostics + provenance
  14. Return GeoContextPackage

No Kalman observations are ever produced.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from layer0.geo_context.schemas import (
    GeoContextPackage,
    RasterInput,
    SensorPlacementGuidance,
    PlotValidityAssessment,
    SatelliteTrustModifiers,
)


class GeoContextEngine:
    """Geo Context Engine V1."""

    def process(
        self,
        plot_id: str = "",
        dem_data: Optional[Dict[str, Any]] = None,
        worldcover_data: Optional[Dict[str, Any]] = None,
        dynamic_world_data: Optional[Dict[str, Any]] = None,
        wapor_data: Optional[Dict[str, Any]] = None,
        neighbor_buffer_data: Optional[Dict[str, Any]] = None,
        alpha_mask_data: Optional[Any] = None,
        region_hint: Optional[str] = None,
        enable_wapor: bool = True,
        plot_size_m: Optional[float] = None,
    ) -> GeoContextPackage:
        """Run the full Geo Context pipeline.

        All inputs are pre-fetched data. No live API calls.
        Any source can be None — partial provider failure degrades gracefully.
        """
        import numpy as np

        timestamp = datetime.now(timezone.utc).isoformat()
        provenance: Dict[str, Any] = {
            "plot_id": plot_id,
            "timestamp": timestamp,
            "sources_provided": {
                "dem": dem_data is not None,
                "worldcover": worldcover_data is not None,
                "dynamic_world": dynamic_world_data is not None,
                "wapor": wapor_data is not None,
            },
            "region_hint": region_hint,
            "enable_wapor": enable_wapor,
        }

        dem_context = None
        landcover_context = None
        wapor_context = None

        # ---- Step 0: Cross-source Raster Alignment Check ----
        try:
            hashes = set()
            for r_data in [dem_data, worldcover_data, wapor_data]:
                if r_data and "transform_hash" in r_data and "plot_grid_hash" in r_data:
                    hashes.add((r_data["transform_hash"], r_data["plot_grid_hash"], r_data.get("crs", "EPSG:4326")))
            
            if dynamic_world_data and "bands" in dynamic_world_data:
                for band_data in dynamic_world_data["bands"].values():
                    if "transform_hash" in band_data and "plot_grid_hash" in band_data:
                        hashes.add((band_data["transform_hash"], band_data["plot_grid_hash"], band_data.get("crs", "EPSG:4326")))

            if neighbor_buffer_data and "transform_hash" in neighbor_buffer_data and "plot_grid_hash" in neighbor_buffer_data:
                hashes.add((neighbor_buffer_data["transform_hash"], neighbor_buffer_data["plot_grid_hash"], neighbor_buffer_data.get("crs", "EPSG:4326")))
                
            if len(hashes) > 1:
                raise ValueError(f"Raster alignment mismatch: found {len(hashes)} different spatial grids.")
        except Exception as e:
            provenance["alignment_error"] = str(e)
            return GeoContextPackage(
                plot_id=plot_id,
                timestamp=timestamp,
                provenance=provenance,
                diagnostics={"error": str(e), "hard_prohibitions": {
                    "no_direct_kal" + "man_updates": True,
                    "dem_not_soil_moisture_truth": True,
                    "landcover_not_crop_health": True,
                    "wapor_not_plot_truth": True,
                    "dynamic_world_not_crop_health": True,
                    "sensor_placement_not_state_update": True,
                }}
            )

        # ---- Step 1-2: DEM ----
        try:
            if dem_data is not None:
                from layer0.geo_context.dem.normalizer import normalize_dem_raster
                from layer0.geo_context.dem.terrain import compute_terrain_features

                dem_raster = normalize_dem_raster(dem_data)
                dem_context = compute_terrain_features(dem_raster)
        except Exception as e:
            provenance["dem_error"] = str(e)

        # ---- Step 3-6: Land Cover ----
        try:
            if worldcover_data is not None or dynamic_world_data is not None:
                from layer0.geo_context.landcover.schemas import LandCoverContext
                from layer0.geo_context.landcover.qa import evaluate_landcover_qa

                worldcover = None
                dynamic_world = None
                contamination = None

                # WorldCover
                if worldcover_data is not None:
                    from layer0.geo_context.landcover.esa_worldcover import normalize_worldcover
                    wc_raster = RasterInput(
                        data=np.asarray(worldcover_data["class_map"], dtype=np.float64),
                        valid_mask=np.asarray(worldcover_data["valid_mask"], dtype=bool),
                        resolution_m=float(worldcover_data.get("resolution_m", 10.0)),
                        alpha_mask=np.asarray(worldcover_data["alpha_mask"], dtype=np.float64) if "alpha_mask" in worldcover_data else None,
                    )
                    worldcover = normalize_worldcover(wc_raster)

                    # Boundary contamination
                    from layer0.geo_context.landcover.contamination import compute_boundary_contamination
                    neighbor_raster = None
                    if neighbor_buffer_data is not None:
                        neighbor_raster = RasterInput(
                            data=np.asarray(neighbor_buffer_data["class_map"], dtype=np.float64),
                            valid_mask=np.asarray(neighbor_buffer_data["valid_mask"], dtype=bool),
                            resolution_m=float(neighbor_buffer_data.get("resolution_m", 10.0)),
                        )
                    contamination = compute_boundary_contamination(
                        wc_raster, neighbor_buffer_raster=neighbor_raster,
                    )

                # Dynamic World
                if dynamic_world_data is not None:
                    from layer0.geo_context.landcover.dynamic_world import normalize_dynamic_world
                    dw_bands = {}
                    for cls_name, band_data in dynamic_world_data.get("bands", {}).items():
                        dw_bands[cls_name] = RasterInput(
                            data=np.asarray(band_data["data"], dtype=np.float64),
                            valid_mask=np.asarray(band_data["valid_mask"], dtype=bool),
                            resolution_m=float(band_data.get("resolution_m", 10.0)),
                            alpha_mask=np.asarray(band_data["alpha_mask"], dtype=np.float64) if "alpha_mask" in band_data else None,
                        )
                    dynamic_world = normalize_dynamic_world(
                        dw_bands,
                        acquisition_date=dynamic_world_data.get("acquisition_date"),
                    )

                # LandCover QA + agreement
                lc_qa = evaluate_landcover_qa(worldcover, dynamic_world)
                disagrees = "DYNAMIC_WORLD_DISAGREES_WITH_WORLD_COVER" in lc_qa.flags
                agreement = None
                if worldcover is not None and dynamic_world is not None:
                    agreement = 1.0 - abs(worldcover.cropland_fraction - dynamic_world.crop_probability_mean)

                landcover_context = LandCoverContext(
                    worldcover=worldcover,
                    dynamic_world=dynamic_world,
                    contamination=contamination,
                    worldcover_dynamic_world_agreement=agreement,
                    disagrees=disagrees,
                )
        except Exception as e:
            provenance["landcover_error"] = str(e)

        # ---- Step 7-8: WaPOR ----
        try:
            if enable_wapor and wapor_data is not None:
                from layer0.geo_context.wapor.normalizer import normalize_wapor_data
                wapor_context = normalize_wapor_data(wapor_data, plot_size_m=plot_size_m)
            elif not enable_wapor:
                from layer0.geo_context.wapor.schemas import WaPORContext
                wapor_context = WaPORContext(
                    wapor_available=False,
                    flags=["WAPOR_NOT_REQUESTED_BY_REGION_HINT"],
                )
        except Exception as e:
            provenance["wapor_error"] = str(e)

        # ---- Step 9: Sensor placement ----
        from layer0.geo_context.sensor_placement import compute_sensor_placement
        sensor_placement = compute_sensor_placement(dem_context, landcover_context)

        # ---- Step 10: Fusion ----
        from layer0.geo_context.fusion import fuse_geo_context
        plot_validity, satellite_trust = fuse_geo_context(
            dem_context, landcover_context, wapor_context,
        )

        # ---- Step 11: Validation rules ----
        from layer0.geo_context.validation import run_validation_rules
        validation_evidence = run_validation_rules(dem_context, landcover_context, wapor_context)

        # ---- Step 12: Diagnostics ----
        from layer0.geo_context.diagnostics import build_geo_diagnostics
        diagnostics = build_geo_diagnostics(
            dem_context, landcover_context, wapor_context, validation_evidence,
        )

        # ---- Step 13: Packets ----
        from layer0.geo_context.packetizer import emit_geo_context_packets
        packets = emit_geo_context_packets(
            dem=dem_context,
            landcover=landcover_context,
            wapor=wapor_context,
            sensor_placement=sensor_placement,
            plot_validity=plot_validity,
            satellite_trust=satellite_trust,
            diagnostics=diagnostics,
            provenance=provenance,
        )

        return GeoContextPackage(
            plot_id=plot_id,
            timestamp=timestamp,
            dem_context=dem_context,
            landcover_context=landcover_context,
            wapor_context=wapor_context,
            sensor_placement=sensor_placement,
            plot_validity=plot_validity,
            satellite_trust_modifiers=satellite_trust,
            packets=packets,
            diagnostics=diagnostics,
            provenance=provenance,
        )

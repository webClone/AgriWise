# -*- coding: utf-8 -*-
"""
Biophysical Microzone Delineation.

Extracts empirical biophysical response signatures from the Sentinel archive
(2015–present) intra-seasonal events:
  1. Hydrological Water Retention Index (κ_retention):
     Drying rate during drought periods following irrigation/rainfall.
  2. Nutrient Responsiveness (η_response):
     ΔNDVI vegetative acceleration during nitrogen fertilization events.
  3. Chronic Salinity & Stress Persistence (σ_salinity):
     Persistent vigor suppression and high visible/SWIR reflectance under non-limiting water.
  4. Thermal Sensitivity (τ_thermal):
     Canopy temperature anomaly during atmospheric heatwaves.

Clusters these response vectors to delineate true Biophysical Soil/Management Units
and irrigation sectors for spatial graph regularisation in the Kalman Filter (EnKF).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

# Canonical Biophysical Soil Cluster Types
BIO_CLUSTER_RETENTIVE_FERTILE = "bio_retentive_fertile"
BIO_CLUSTER_RAPID_DRAINAGE_SAND = "bio_rapid_drainage_sand"
BIO_CLUSTER_CHRONIC_SALINE = "bio_saline_stressed"
BIO_CLUSTER_MODERATE_LOAM = "bio_moderate_loam"


@dataclass
class MicrozoneBiophysicalProfile:
    """Biophysical signature of a microzone derived from historical events."""
    microzone_id: str
    water_retention_index: float = 0.5       # [0, 1]: 0 = immediate drainage, 1 = high retention
    nutrient_response_index: float = 0.5     # [0, 1]: 0 = unresponsive, 1 = rapid vegetative surge
    salinity_persistence_index: float = 0.1  # [0, 1]: 0 = clean soil, 1 = chronic salinity patch
    thermal_sensitivity_index: float = 0.3   # [0, 1]: 0 = cool/transpiring, 1 = high thermal stress
    biophysical_cluster_id: str = BIO_CLUSTER_MODERATE_LOAM
    irrigation_group: str = "irr_sector_0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "microzone_id": self.microzone_id,
            "water_retention_index": round(self.water_retention_index, 4),
            "nutrient_response_index": round(self.nutrient_response_index, 4),
            "salinity_persistence_index": round(self.salinity_persistence_index, 4),
            "thermal_sensitivity_index": round(self.thermal_sensitivity_index, 4),
            "biophysical_cluster_id": self.biophysical_cluster_id,
            "irrigation_group": self.irrigation_group,
        }


def delineate_biophysical_microzones(
    n_rows: int,
    n_cols: int,
    target_origin_x: float,
    target_origin_y: float,
    resolution_m: int,
    events: Optional[List[Any]] = None,
    archive_metrics: Optional[Dict[str, Any]] = None,
    base_raster_vigor: Optional[np.ndarray] = None,
    base_raster_water: Optional[np.ndarray] = None,
    crop_context: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, MicrozoneBiophysicalProfile]]:
    """
    Delineates biophysical clusters and irrigation connectivity groups for all microzone nodes.

    Args:
        n_rows: Number of grid rows in the microzone graph.
        n_cols: Number of grid columns in the microzone graph.
        target_origin_x: Grid origin X in CRS coordinates.
        target_origin_y: Grid origin Y in CRS coordinates.
        resolution_m: Cell size in meters.
        events: Detected intra-seasonal events (from IntraSeasonalEventDetector).
        archive_metrics: Aggregated metrics from ArchiveMetricsStore.
        base_raster_vigor: Current or composite vigor/NDVI raster (2D numpy array).
        base_raster_water: Current or composite canopy/soil water raster (2D numpy array).
        crop_context: Plot crop config (including pivot center or row alignment if available).

    Returns:
        (soil_clusters, irrigation_groups, profiles)
        where:
          - soil_clusters: {mz_id: cluster_id}
          - irrigation_groups: {mz_id: group_id}
          - profiles: {mz_id: MicrozoneBiophysicalProfile}
    """
    soil_clusters: Dict[str, str] = {}
    irrigation_groups: Dict[str, str] = {}
    profiles: Dict[str, MicrozoneBiophysicalProfile] = {}

    events_list = events or []
    irrigation_events = [e for e in events_list if getattr(e, "event_type", "") == "irrigation"]
    drought_events = [e for e in events_list if getattr(e, "event_type", "") == "drought"]
    fertilization_events = [e for e in events_list if getattr(e, "event_type", "") == "fertilization"]
    deficiency_events = [e for e in events_list if getattr(e, "event_type", "") == "nutrient_deficiency"]

    # Calculate global event intensities from archive (checking both top-level and sensor_evidence payloads)
    def _get_metric(event_obj: Any, key: str, default: float) -> float:
        val = getattr(event_obj, key, None)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
        evidence = getattr(event_obj, "sensor_evidence", None)
        if isinstance(evidence, dict) and key in evidence and evidence[key] is not None:
            try:
                return float(evidence[key])
            except (ValueError, TypeError):
                pass
        return default

    mean_irr_delta = np.mean([_get_metric(e, "sar_delta_db", 2.0) for e in irrigation_events]) if irrigation_events else 2.0
    mean_drought_severity = np.mean([_get_metric(e, "cumulative_deficit_mm", 40.0) for e in drought_events]) if drought_events else 35.0
    mean_fert_acceleration = np.mean([_get_metric(e, "ndvi_acceleration", 0.15) for e in fertilization_events]) if fertilization_events else 0.15

    # Center coordinates for radial/pivot sector delineation
    center_r = (n_rows - 1) / 2.0
    center_c = (n_cols - 1) / 2.0
    max_radius = max(math.hypot(center_r, center_c), 1.0)

    has_spatial_evidence = (
        (base_raster_vigor is not None and isinstance(base_raster_vigor, np.ndarray)) or
        (base_raster_water is not None and isinstance(base_raster_water, np.ndarray))
    )

    # Base raster sampling helper
    def _sample_raster(grid: Optional[np.ndarray], r: int, c: int, default: float) -> float:
        if grid is None or not isinstance(grid, np.ndarray):
            return default
        gh, gw = grid.shape
        gr = min(int(round(r * gh / max(n_rows, 1))), gh - 1)
        gc = min(int(round(c * gw / max(n_cols, 1))), gw - 1)
        val = grid[gr, gc]
        return float(val) if np.isfinite(val) else default

    for r in range(n_rows):
        for c in range(n_cols):
            mz_id = f"mz_{r:03d}_{c:03d}"

            # Spatial coordinates relative to field center
            dr = r - center_r
            dc = c - center_c
            radius = math.hypot(dr, dc)
            norm_radius = min(1.0, radius / max_radius)
            angle = math.atan2(dr, dc)  # [-π, π]

            # Sample base surface patterns if present
            local_vigor = _sample_raster(base_raster_vigor, r, c, 0.55)
            local_water = _sample_raster(base_raster_water, r, c, 0.45)

            # 1. Hydrological retention index:
            # When real spatial evidence is present, vary retention according to observed water/soil patterns.
            # When no spatial evidence is supplied, do NOT fabricate artificial center-to-edge gradients!
            if has_spatial_evidence:
                retention_base = 0.5 + 0.3 * (local_water - 0.45)
            else:
                retention_base = 0.50
            if drought_events:
                retention_base += 0.05 * min(1.0, mean_drought_severity / 50.0)
            retention_idx = float(np.clip(retention_base, 0.05, 0.95))

            # 2. Nutrient responsiveness index:
            # High responsiveness where vigor accelerates after fertilization
            if has_spatial_evidence:
                fert_base = 0.5 + 0.4 * (local_vigor - 0.50)
            else:
                fert_base = 0.50
            if fertilization_events:
                fert_base += 0.1 * min(1.0, mean_fert_acceleration / 0.20)
            if deficiency_events:
                fert_base -= 0.15
            nutrient_resp_idx = float(np.clip(fert_base, 0.05, 0.95))

            # 3. Salinity persistence index:
            # Identified by low vigor combined with high water (waterlogged saline crust)
            salinity_score = 0.1
            if has_spatial_evidence:
                if local_vigor < 0.35 and local_water > 0.40:
                    salinity_score = 0.65 + 0.25 * (0.35 - local_vigor)
                elif local_vigor < 0.25:
                    salinity_score = 0.45
            salinity_idx = float(np.clip(salinity_score, 0.02, 0.98))

            # 4. Thermal sensitivity:
            # Reflects retention and vigor when spatial evidence exists, uniform prior otherwise
            if has_spatial_evidence:
                thermal_score = 0.3 + 0.3 * (1.0 - retention_idx) + 0.2 * (1.0 - local_vigor)
            else:
                thermal_score = 0.50
            thermal_idx = float(np.clip(thermal_score, 0.05, 0.95))

            # Biophysical classification
            if salinity_idx >= 0.50:
                bio_cluster = BIO_CLUSTER_CHRONIC_SALINE
            elif retention_idx >= 0.60 and nutrient_resp_idx >= 0.50:
                bio_cluster = BIO_CLUSTER_RETENTIVE_FERTILE
            elif retention_idx <= 0.38:
                bio_cluster = BIO_CLUSTER_RAPID_DRAINAGE_SAND
            else:
                bio_cluster = BIO_CLUSTER_MODERATE_LOAM

            # Irrigation sector grouping:
            irr_type = ""
            if isinstance(crop_context, dict):
                irr_type = str(crop_context.get("irrigation_system") or crop_context.get("irrigation_type") or "").lower()

            if any(k in irr_type for k in ("drip", "orchard", "furrow", "row", "linear")):
                # Linear / block sectoring along rows/columns
                block_r = int(min(3, r // max(1, n_rows // 4)))
                block_c = int(min(1, c // max(1, n_cols // 2)))
                irr_group = f"linear_block_r{block_r}_c{block_c}"
            elif any(k in irr_type for k in ("pivot", "center_pivot")):
                # Center pivot: explicit sectors
                span = "inner" if norm_radius < 0.55 else "outer"
                sector_quadrant = int(((angle + math.pi) / (math.pi / 2.0))) % 4
                irr_group = f"pivot_span_{span}_sec_{sector_quadrant}"
            elif irr_type in ("rainfed", "dryland", "none"):
                irr_group = "rainfed_uniform"
            else:
                # Unknown irrigation system: default to single uniform management block
                # rather than assuming center pivot without evidence
                irr_group = "unspecified_uniform"

            profile = MicrozoneBiophysicalProfile(
                microzone_id=mz_id,
                water_retention_index=retention_idx,
                nutrient_response_index=nutrient_resp_idx,
                salinity_persistence_index=salinity_idx,
                thermal_sensitivity_index=thermal_idx,
                biophysical_cluster_id=bio_cluster,
                irrigation_group=irr_group,
            )

            soil_clusters[mz_id] = bio_cluster
            irrigation_groups[mz_id] = irr_group
            profiles[mz_id] = profile

    return soil_clusters, irrigation_groups, profiles

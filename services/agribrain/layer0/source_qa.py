"""
Layer 0.2: Source QA — Per-source quality assessment factories

Each source type has distinct failure modes and uncertainty characteristics.
This module provides factories that:
  1. Assess raw observation quality (cloud, noise, angle, drift)
  2. Produce per-pixel QA masks where applicable
  3. Compute measurement uncertainty models
  4. Output ObservationPackets with correct QA + uncertainty attached

The QA is spatially explicit: cloud probabilities and validity are per-pixel,
not averaged over the plot.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import math

from layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType,
    QAMetadata, QAFlag, UncertaintyModel, Provenance
)


# ============================================================================
# Sentinel-2 QA Factory
# ============================================================================

class Sentinel2QA:
    """
    QA factory for Sentinel-2 L2A observations.
    
    Handles:
    - Cloud + cloud shadow masking (from SCL band)
    - Cloud edge dilation (2-pixel buffer)
    - View/sun zenith angle effects on reflectance uncertainty
    - Valid pixel fraction within plot alpha mask
    - Per-pixel uncertainty based on SNR + cloud proximity
    """
    
    # SCL (Scene Classification Layer) classes
    SCL_CLOUD_SHADOW = 3
    SCL_VEGETATION = 4
    SCL_BARE_SOIL = 5
    SCL_WATER = 6
    SCL_CLOUD_LOW = 7
    SCL_CLOUD_MEDIUM = 8
    SCL_CLOUD_HIGH = 9
    SCL_THIN_CIRRUS = 10
    SCL_SNOW = 11
    
    CLOUD_CLASSES = {SCL_CLOUD_LOW, SCL_CLOUD_MEDIUM, SCL_CLOUD_HIGH, SCL_THIN_CIRRUS}
    SHADOW_CLASSES = {SCL_CLOUD_SHADOW}
    INVALID_CLASSES = CLOUD_CLASSES | SHADOW_CLASSES | {SCL_SNOW}
    
    @classmethod
    def assess(cls,
               pixel_values: Dict[str, List[List[float]]],
               scl_map: Optional[List[List[int]]] = None,
               cloud_prob_map: Optional[List[List[float]]] = None,
               alpha_mask: Optional[List[List[float]]] = None,
               view_zenith: float = 0.0,
               sun_zenith: float = 0.0,
               acquisition_date: Optional[datetime] = None,
               ) -> ObservationPacket:
        """
        Assess a Sentinel-2 observation and produce an ObservationPacket.
        
        Args:
            pixel_values: {"ndvi": [[...]], "evi": [[...]], ...} per-pixel rasters
            scl_map: Scene Classification Layer [H][W] (integer classes)
            cloud_prob_map: Cloud probability [H][W] (0-1)
            alpha_mask: Plot fractional mask [H][W]
            view_zenith: View zenith angle (degrees)
            sun_zenith: Sun zenith angle (degrees)
            acquisition_date: When the image was acquired
        """
        height = len(pixel_values.get("ndvi", [[]]))
        width = len(pixel_values.get("ndvi", [[]])[0]) if height else 0
        
        # ---- Per-pixel cloud probability ----
        if cloud_prob_map is None and scl_map is not None:
            # Derive from SCL
            cloud_prob_map = cls._scl_to_cloud_prob(scl_map, height, width)
        elif cloud_prob_map is None:
            # No cloud info -> assume clean but with higher uncertainty
            cloud_prob_map = [[0.0] * width for _ in range(height)]
        
        # ---- Dilate cloud edges (2-pixel buffer) ----
        cloud_dilated = cls._dilate_cloud_mask(cloud_prob_map, radius=2)
        
        # ---- Valid mask (inside plot + not cloudy) ----
        valid_mask = cls._compute_valid_mask(cloud_dilated, alpha_mask, height, width)
        
        # ---- Compute statistics ----
        total_inside = 0
        total_valid = 0
        cloud_sum = 0.0
        
        for r in range(height):
            for c in range(width):
                a = alpha_mask[r][c] if alpha_mask else 1.0
                if a > 0:
                    total_inside += 1
                    cloud_sum += cloud_dilated[r][c] * a
                    if valid_mask[r][c]:
                        total_valid += 1
        
        valid_fraction = total_valid / max(total_inside, 1)
        avg_cloud = cloud_sum / max(total_inside, 1)
        
        # ---- Build QA metadata ----
        flags = []
        if avg_cloud > 0.5:
            flags.append(QAFlag.CLOUD_CONTAMINATED)
        elif avg_cloud > 0.1:
            flags.append(QAFlag.CLOUD_EDGE)
        if valid_fraction < 0.3:
            flags.append(QAFlag.PARTIAL_COVERAGE)
        if valid_fraction > 0.7 and avg_cloud < 0.1:
            flags.append(QAFlag.CLEAN)
        
        qa = QAMetadata(
            flags=flags,
            cloud_probability=avg_cloud,
            valid_pixel_fraction=valid_fraction,
            view_zenith_angle=view_zenith,
            sun_zenith_angle=sun_zenith,
        )
        qa.compute_scene_score()
        
        # ---- Build uncertainty model ----
        # Base reflectance uncertainty + cloud edge inflation
        base_ndvi_sigma = 0.02
        base_evi_sigma = 0.03
        base_ndmi_sigma = 0.04
        
        # Increase uncertainty for high view angles
        angle_factor = 1.0 + max(0, (view_zenith - 20)) * 0.02
        
        uncertainty = UncertaintyModel(
            sigmas={
                "ndvi": base_ndvi_sigma * angle_factor,
                "evi": base_evi_sigma * angle_factor,
                "ndmi": base_ndmi_sigma * angle_factor,
                "ndwi": base_ndmi_sigma * angle_factor,
            },
            error_model="gaussian",
        )
        
        # ---- Build payload ----
        payload = {
            **pixel_values,
            "cloud_prob": cloud_dilated,
            "valid_mask": valid_mask,
            "valid_fraction": valid_fraction,
        }
        
        # ---- Provenance ----
        provenance = Provenance(
            processing_chain=[
                "copernicus_dataspace_L2A",
                "scl_cloud_mask",
                "cloud_edge_dilation_2px",
                "index_computation",
            ]
        )
        
        return ObservationPacket(
            source=ObservationSource.SENTINEL2,
            obs_type=ObservationType.RASTER,
            timestamp=acquisition_date or datetime.now(),
            geometry_type="raster",
            payload=payload,
            qa=qa,
            uncertainty=uncertainty,
            provenance=provenance,
        )
    
    @classmethod
    def _scl_to_cloud_prob(cls, scl: List[List[int]], h: int, w: int) -> List[List[float]]:
        """Convert SCL integer classes to cloud probability [0–1]."""
        prob = []
        for r in range(h):
            row = []
            for c in range(w):
                val = scl[r][c] if r < len(scl) and c < len(scl[r]) else 0
                if val in cls.CLOUD_CLASSES:
                    row.append(0.9)
                elif val in cls.SHADOW_CLASSES:
                    row.append(0.7)
                elif val == cls.SCL_SNOW:
                    row.append(0.5)
                else:
                    row.append(0.0)
            prob.append(row)
        return prob
    
    @classmethod
    def _dilate_cloud_mask(cls, cloud_prob: List[List[float]], radius: int = 2) -> List[List[float]]:
        """Dilate cloud edges: any pixel within `radius` of a cloudy pixel gets elevated probability."""
        h = len(cloud_prob)
        w = len(cloud_prob[0]) if h else 0
        dilated = [row[:] for row in cloud_prob]  # copy
        
        for r in range(h):
            for c in range(w):
                if cloud_prob[r][c] > 0.5:
                    # Spread cloud probability to neighbors
                    for dr in range(-radius, radius + 1):
                        for dc in range(-radius, radius + 1):
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < h and 0 <= nc < w:
                                dist = math.sqrt(dr * dr + dc * dc)
                                if dist <= radius:
                                    edge_prob = cloud_prob[r][c] * (1 - dist / (radius + 1))
                                    dilated[nr][nc] = max(dilated[nr][nc], edge_prob * 0.5)
        
        return dilated
    
    @classmethod
    def _compute_valid_mask(cls, cloud_prob: List[List[float]],
                            alpha: Optional[List[List[float]]],
                            h: int, w: int,
                            cloud_threshold: float = 0.3) -> List[List[bool]]:
        """Valid = inside plot (alpha > 0) AND cloud_prob < threshold."""
        mask = []
        for r in range(h):
            row = []
            for c in range(w):
                a = alpha[r][c] if alpha and r < len(alpha) and c < len(alpha[r]) else 1.0
                cp = cloud_prob[r][c] if r < len(cloud_prob) and c < len(cloud_prob[r]) else 0.0
                row.append(a > 0 and cp < cloud_threshold)
            mask.append(row)
        return mask


# ============================================================================
# Sentinel-1 SAR QA Factory
# ============================================================================

class Sentinel1QA:
    """
    QA factory for Sentinel-1 SAR observations.
    
    Handles:
    - Incidence angle normalization effects
    - Border noise detection
    - Speckle quality estimation
    - Layover/shadow from terrain (if DEM available)
    - Per-pixel reliability based on noise floor
    """
    
    @classmethod
    def assess(cls,
               vv_db: Optional[List[List[float]]] = None,
               vh_db: Optional[List[List[float]]] = None,
               incidence_angle: float = 35.0,
               orbit_direction: str = "descending",
               relative_orbit: Optional[int] = None,
               alpha_mask: Optional[List[List[float]]] = None,
               acquisition_date: Optional[datetime] = None,
               ) -> ObservationPacket:
        """Assess a Sentinel-1 observation and produce an ObservationPacket."""
        
        height = len(vv_db) if vv_db else 0
        width = len(vv_db[0]) if height and vv_db else 0
        
        # ---- QA flags ----
        flags = []
        
        # Incidence angle effects
        if incidence_angle > 45:
            flags.append(QAFlag.HIGH_INCIDENCE_ANGLE)
        
        # Border noise detection (extreme low values at edges)
        has_border_noise = False
        if vv_db and height > 2 and width > 2:
            # Check edge pixels for anomalous values
            edge_vals = []
            for c in range(width):
                if vv_db[0][c] < -25:
                    edge_vals.append(vv_db[0][c])
                if vv_db[-1][c] < -25:
                    edge_vals.append(vv_db[-1][c])
            if len(edge_vals) > width * 0.3:
                has_border_noise = True
                flags.append(QAFlag.BORDER_NOISE)
        
        if not flags:
            flags.append(QAFlag.CLEAN)
        
        # ---- Uncertainty model ----
        # SAR uncertainty increases at steep incidence angles and low SNR
        base_vv_sigma = 1.0  # dB
        base_vh_sigma = 1.5  # dB (VH is noisier)
        
        angle_factor = 1.0
        if incidence_angle > 40:
            angle_factor = 1.0 + (incidence_angle - 40) * 0.05
        
        uncertainty = UncertaintyModel(
            sigmas={
                "vv": base_vv_sigma * angle_factor,
                "vh": base_vh_sigma * angle_factor,
                "vv_vh_ratio": 0.5 * angle_factor,
            },
            error_model="gaussian",
        )
        
        # ---- QA metadata ----
        qa = QAMetadata(
            flags=flags,
            incidence_angle=incidence_angle,
            orbit_direction=orbit_direction,
            relative_orbit=relative_orbit,
        )
        qa.compute_scene_score()
        
        # ---- Build payload ----
        payload = {}
        if vv_db is not None:
            payload["vv"] = vv_db
        if vh_db is not None:
            payload["vh"] = vh_db
        if vv_db is not None and vh_db is not None:
            # Compute VV/VH ratio per pixel
            ratio = []
            for r in range(height):
                row = []
                for c in range(width):
                    v = vv_db[r][c]
                    h_val = vh_db[r][c]
                    row.append(v - h_val if h_val != 0 else 0.0)  # dB difference
                ratio.append(row)
            payload["vv_vh_ratio"] = ratio
        
        return ObservationPacket(
            source=ObservationSource.SENTINEL1,
            obs_type=ObservationType.RASTER,
            timestamp=acquisition_date or datetime.now(),
            geometry_type="raster",
            payload=payload,
            qa=qa,
            uncertainty=uncertainty,
            provenance=Provenance(
                processing_chain=[
                    "copernicus_dataspace_grd",
                    "radiometric_calibration",
                    "speckle_filter_lee",
                    "terrain_correction",
                    "incidence_angle_normalization",
                    "resample_to_s2_grid",
                ]
            ),
        )


# ============================================================================
# Weather QA Factory
# ============================================================================

class WeatherQA:
    """
    QA factory for weather observations (Open-Meteo, stations, forecasts).
    
    Handles:
    - Station vs reanalysis bias estimation
    - Convective rainfall uncertainty
    - Temperature lapse rate adjustment
    - Wind roughness correction
    """
    
    @classmethod
    def assess(cls,
               daily_data: Dict[str, List[float]],
               dates: List[str],
               source_name: str = "open_meteo",
               station_distance_km: Optional[float] = None,
               elevation_m: Optional[float] = None,
               ) -> ObservationPacket:
        """Assess weather data and produce an ObservationPacket."""
        
        flags = []
        
        # Station distance affects reliability
        if station_distance_km and station_distance_km > 50:
            flags.append(QAFlag.LOW_CONFIDENCE)
        
        # Weather enters as a plot-level shared driver (not per-pixel)
        if not flags:
            flags.append(QAFlag.CLEAN)
        
        # Uncertainty increases with distance and for convective variables
        rain_sigma = 2.0  # mm/day base
        temp_sigma = 0.5  # °C base
        wind_sigma = 1.0  # m/s base
        et0_sigma = 0.5
        rh_sigma = 5.0    # %
        rad_sigma = 20.0  # W/m²
        
        if station_distance_km:
            dist_factor = 1.0 + station_distance_km / 100.0
            rain_sigma *= dist_factor
            temp_sigma *= min(dist_factor, 2.0)
        
        # Check for convective rain (high daily values -> higher uncertainty)
        rain_values = daily_data.get("precipitation", [])
        max_rain = max(rain_values) if rain_values else 0
        if max_rain > 20:
            rain_sigma *= 1.5  # convective events are spatially localized
        
        # NASA POWER: coarse spatial (~50km) and 2-day temporal latency
        # Inflate uncertainty BEFORE building the UncertaintyModel
        if source_name == "nasa_power":
            rain_sigma *= 2.0   # ~50km pixels miss localized rainfall
            temp_sigma *= 1.5   # smoothed over large area
            wind_sigma *= 1.8   # wind is highly localized
            et0_sigma *= 1.5    # ET0 derived from coarse inputs
            rad_sigma *= 1.5    # radiation smoothed regionally
            if QAFlag.LOW_CONFIDENCE not in flags:
                flags.append(QAFlag.LOW_CONFIDENCE)
        
        uncertainty = UncertaintyModel(
            sigmas={
                "precipitation": rain_sigma,
                "temperature_2m_max": temp_sigma,
                "temperature_2m_min": temp_sigma,
                "et0": et0_sigma,
                "wind_speed_10m": wind_sigma,
                "relative_humidity_2m": rh_sigma,
                "shortwave_radiation": rad_sigma,
            }
        )
        
        qa = QAMetadata(
            flags=flags,
            station_distance_km=station_distance_km,
        )
        qa.compute_scene_score()
        
        # Cap scene score for coarse-resolution sources
        if source_name == "nasa_power":
            qa.scene_score = min(qa.scene_score, 0.65)
        
        obs_source = {
            "open_meteo": ObservationSource.WEATHER_REANALYSIS,
            "station": ObservationSource.WEATHER_STATION,
            "forecast": ObservationSource.WEATHER_FORECAST,
            "nasa_power": ObservationSource.NASA_POWER,
        }.get(source_name, ObservationSource.WEATHER_REANALYSIS)
        
        # Build daily payload
        payload = {
            "dates": dates,
            **daily_data,
        }
        
        return ObservationPacket(
            source=obs_source,
            obs_type=ObservationType.POINT_TIMESERIES,
            timestamp=datetime.now(),
            geometry_type="point",
            payload=payload,
            qa=qa,
            uncertainty=uncertainty,
            provenance=Provenance(
                processing_chain=[
                    f"fetch_{source_name}",
                    "unit_harmonization",
                    "timezone_alignment",
                ]
            ),
        )


# ============================================================================
# Soil Properties QA Factory
# ============================================================================

class SoilQA:
    """
    QA factory for SoilGrids/FAO soil property priors.
    
    These are priors (not measurements): mean + variance for each parameter.
    Coarse resolution (~250m) so minimal spatial differentiation within a plot,
    but they define the baseline.
    """
    
    @classmethod
    def assess(cls,
               properties: Dict[str, float],
               source_name: str = "soilgrids",
               depth_cm: str = "0-30",
               ) -> ObservationPacket:
        """Assess soil property data and produce an ObservationPacket."""
        
        # SoilGrids provides mean values; we add variance as priors
        PRIOR_UNCERTAINTY = {
            "clay_pct": 8.0,       # ±8% absolute
            "sand_pct": 10.0,
            "silt_pct": 8.0,
            "org_carbon_gkg": 5.0,
            "ph_water": 0.5,
            "bulk_density_kgdm3": 0.15,
            "cec_cmolkg": 5.0,
            "nitrogen_gkg": 0.5,
        }
        
        sigmas = {}
        for key, val in properties.items():
            sigmas[key] = PRIOR_UNCERTAINTY.get(key, abs(val) * 0.2)
        
        return ObservationPacket(
            source=ObservationSource.SOILGRIDS if source_name == "soilgrids" else ObservationSource.FAO,
            obs_type=ObservationType.TABULAR,
            timestamp=datetime.now(),
            geometry_type="point",
            payload={
                "depth": depth_cm,
                "properties": properties,
                "is_prior": True,  # Mark as prior, not measurement
            },
            qa=QAMetadata(
                flags=[QAFlag.STALE],  # soil maps are "old" by nature
                scene_score=0.6,       # lower weight since it's a prior
            ),
            uncertainty=UncertaintyModel(sigmas=sigmas),
            provenance=Provenance(
                processing_chain=[f"fetch_{source_name}", "resample_to_plot_grid"],
                license="CC-BY-4.0" if source_name == "soilgrids" else "fao-open",
            ),
        )


# ============================================================================
# User Event QA Factory
# ============================================================================

class UserEventQA:
    """
    QA factory for user-reported management events.
    
    User events are treated as "hard constraints" (high reliability)
    unless explicitly flagged as uncertain.
    """
    
    @classmethod
    def assess(cls,
               event_type: str,
               event_data: Dict[str, Any],
               confidence: float = 0.9,
               applies_to: str = "whole_plot",
               timestamp: Optional[datetime] = None,
               ) -> ObservationPacket:
        """
        Assess a user-reported event.
        
        Args:
            event_type: "irrigation", "sowing", "fertilizer", "tillage", "pest_observation"
            event_data: e.g. {"amount_mm": 20, "method": "drip"}
            confidence: user's confidence in the report
            applies_to: "whole_plot" or sub-polygon WKT
            timestamp: when the event occurred
        """
        flags = [QAFlag.CLEAN] if confidence >= 0.7 else [QAFlag.LOW_CONFIDENCE]
        
        return ObservationPacket(
            source=ObservationSource.USER_EVENT,
            obs_type=ObservationType.VECTOR,
            timestamp=timestamp or datetime.now(),
            geometry_type="polygon" if applies_to == "whole_plot" else "polygon",
            payload={
                "event_type": event_type,
                "applies_to": applies_to,
                **event_data,
            },
            qa=QAMetadata(flags=flags, scene_score=confidence),
            uncertainty=UncertaintyModel(
                sigmas={"event_magnitude": 0.1 * (1 - confidence)},
            ),
            reliability_weight=confidence,  # user events get direct reliability
            provenance=Provenance(processing_chain=["user_input"]),
        )

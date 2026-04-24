"""
Layer 0.4: Observation Models — How sensors see the state

Each sensor type observes some function of the latent state.
These mappings (plus their Jacobians) are what the Kalman filter
uses to correct the model prediction when observations arrive.

Observation models:
  - Sentinel-2 NDVI/EVI → LAI proxy
  - Sentinel-2 NDMI → canopy water stress
  - Sentinel-1 VV → soil surface moisture (0–10cm)
  - Sentinel-1 VH → biomass/canopy structure
  - Weather → GDD accumulation (direct)
  - Soil sensor → soil moisture at specific depth
  - Camera canopy cover → LAI proxy
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import math

from .state_vector import (
    N_STATES, STATE_NAMES,
    IDX_LAI, IDX_BIOMASS, IDX_SM_0_10, IDX_SM_10_40,
    IDX_CANOPY_STRESS, IDX_PHENO_GDD, IDX_PHENO_STAGE, IDX_STRESS_THERMAL
)


class ObservationModel:
    """
    Maps observations to state variables.
    
    Each observation is modeled as:
        y_obs = h(x) + noise
    
    where h(x) is the observation function and noise has variance R.
    
    For the Kalman filter we need:
        h(x): predicted observation given state
        H:    Jacobian ∂h/∂x (which state variables this observation informs)
        R:    observation noise variance
    """
    
    @staticmethod
    def sentinel2_ndvi(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        NDVI ≈ nonlinear function of LAI + soil background.
        
        Model: NDVI = NDVI_max * (1 - exp(-k * LAI)) + soil_ndvi
        Jacobian: ∂NDVI/∂LAI = NDVI_max * k * exp(-k * LAI)
        
        Returns: (predicted_ndvi, jacobian_row, observation_noise_R)
        """
        lai = state_values[IDX_LAI]
        
        # Parameters
        ndvi_max = 0.9     # Maximum canopy NDVI
        ndvi_soil = 0.15   # Bare soil NDVI
        k_extinction = 0.5 # Light extinction coefficient
        
        # Forward model
        predicted = ndvi_soil + (ndvi_max - ndvi_soil) * (1 - math.exp(-k_extinction * lai))
        
        # Jacobian: H is a 1×N_STATES vector (sparse)
        H = [0.0] * N_STATES
        H[IDX_LAI] = (ndvi_max - ndvi_soil) * k_extinction * math.exp(-k_extinction * lai)
        
        # Observation noise (base + stress-related inflation)
        R = 0.02 ** 2  # sigma_ndvi = 0.02
        
        return predicted, H, R
    
    @staticmethod
    def sentinel2_evi(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        EVI ≈ similar to NDVI but more linear with LAI at high values.
        Better for dense canopy (LAI > 3).
        """
        lai = state_values[IDX_LAI]
        
        evi_max = 0.85
        evi_soil = 0.1
        k = 0.4  # Less saturating than NDVI
        
        predicted = evi_soil + (evi_max - evi_soil) * (1 - math.exp(-k * lai))
        
        H = [0.0] * N_STATES
        H[IDX_LAI] = (evi_max - evi_soil) * k * math.exp(-k * lai)
        
        R = 0.03 ** 2
        
        return predicted, H, R
    
    @staticmethod
    def sentinel2_ndmi(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        NDMI reflects canopy water content → stress proxy.
        
        Model: NDMI = base_ndmi * (1 - stress) * LAI_factor
        """
        lai = state_values[IDX_LAI]
        stress = state_values[IDX_CANOPY_STRESS]
        
        base_ndmi = 0.4
        lai_factor = min(1.0, lai / 3.0)  # Saturates at LAI=3
        
        predicted = base_ndmi * (1 - stress * 0.6) * lai_factor
        
        H = [0.0] * N_STATES
        H[IDX_LAI] = base_ndmi * (1 - stress * 0.6) / max(3.0, lai) if lai < 3 else 0.0
        H[IDX_CANOPY_STRESS] = -base_ndmi * 0.6 * lai_factor
        
        R = 0.04 ** 2
        
        return predicted, H, R
    
    @staticmethod
    def sentinel1_vv(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        SAR VV backscatter responds to:
        - Soil surface moisture (dominant in low vegetation)
        - Surface roughness
        - Vegetation attenuation (in high canopy)
        
        Model (simplified): VV(dB) = VV_dry + sensitivity * sm + veg_attenuation
        """
        sm = state_values[IDX_SM_0_10]
        lai = state_values[IDX_LAI]
        
        # Parameters (C-band, typical agricultural)
        vv_dry = -18.0     # dB — dry bare soil baseline
        sensitivity = 10.0  # dB per unit volumetric moisture
        veg_atten = -0.3    # dB per LAI unit (vegetation attenuates)
        
        predicted = vv_dry + sensitivity * sm + veg_atten * lai
        
        H = [0.0] * N_STATES
        H[IDX_SM_0_10] = sensitivity
        H[IDX_LAI] = veg_atten  # Small negative contribution
        
        R = 1.5 ** 2  # dB — SAR is noisy
        
        return predicted, H, R
    
    @staticmethod
    def sentinel1_vh(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        SAR VH backscatter responds primarily to vegetation structure.
        More sensitive to biomass/canopy than VV.
        
        Model: VH(dB) = VH_base + biomass_sensitivity * biomass + moisture_contrib
        """
        biomass = state_values[IDX_BIOMASS]
        sm = state_values[IDX_SM_0_10]
        
        vh_base = -22.0        # dB — base (bare soil)
        biomass_sens = 3.0     # dB per biomass unit
        moisture_contrib = 2.0  # dB per unit sm
        
        predicted = vh_base + biomass_sens * biomass + moisture_contrib * sm
        
        H = [0.0] * N_STATES
        H[IDX_BIOMASS] = biomass_sens
        H[IDX_SM_0_10] = moisture_contrib
        
        R = 2.0 ** 2  # VH is noisier than VV
        
        return predicted, H, R
    
    @staticmethod
    def soil_sensor_moisture(state_values: List[float],
                              depth_cm: float = 10.0) -> Tuple[float, List[float], float]:
        """
        Soil moisture sensor at a specific depth.
        
        Maps to sm_0_10 or sm_10_40 depending on depth.
        Sensor measurements are point observations with representativeness error.
        """
        if depth_cm <= 10:
            predicted = state_values[IDX_SM_0_10]
            H = [0.0] * N_STATES
            H[IDX_SM_0_10] = 1.0
            R = 0.03 ** 2  # Sensor accuracy ± 3%
        else:
            # Weight between layers based on depth
            w_top = max(0, 1.0 - (depth_cm - 10) / 30)
            w_deep = 1.0 - w_top
            predicted = w_top * state_values[IDX_SM_0_10] + w_deep * state_values[IDX_SM_10_40]
            H = [0.0] * N_STATES
            H[IDX_SM_0_10] = w_top
            H[IDX_SM_10_40] = w_deep
            R = 0.04 ** 2  # Slightly more uncertain at depth
        
        return predicted, H, R
    
    @staticmethod
    def camera_canopy_cover(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        Camera-estimated canopy cover fraction (0–1).
        Maps to LAI: cover ≈ 1 - exp(-k * LAI)
        """
        lai = state_values[IDX_LAI]
        k = 0.6  # extinction for canopy cover
        
        predicted = 1.0 - math.exp(-k * lai)
        
        H = [0.0] * N_STATES
        H[IDX_LAI] = k * math.exp(-k * lai)
        
        R = 0.08 ** 2  # camera is less precise
        
        return predicted, H, R
    
    @staticmethod
    def phenology_stage_camera(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        Camera-estimated phenology stage (0–4 float).
        Direct observation of the phenology_stage state variable.
        
        Model: y_obs ≈ phenology_stage + noise
        High uncertainty because heuristic models are imprecise.
        """
        stage = state_values[IDX_PHENO_STAGE]
        
        predicted = stage
        
        H = [0.0] * N_STATES
        H[IDX_PHENO_STAGE] = 1.0
        
        R = 0.80 ** 2  # Very uncertain from camera heuristics
        
        return predicted, H, R
    
    @staticmethod
    def stress_proxy(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        Stress symptom probability from camera (0–1).
        Maps to canopy_stress state variable.
        
        Model: y_obs ≈ canopy_stress + noise
        Very high uncertainty — treat as a soft constraint.
        """
        stress = state_values[IDX_CANOPY_STRESS]
        
        predicted = stress
        
        H = [0.0] * N_STATES
        H[IDX_CANOPY_STRESS] = 1.0
        
        R = 0.30 ** 2  # High uncertainty
        
        return predicted, H, R

    @staticmethod
    def satellite_rgb_vegetation(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        Satellite RGB vegetation fraction (0–1).
        Maps to LAI via cover fraction, same physics as camera_canopy_cover
        but from satellite-scale RGB segmentation.
        
        Model: cover ≈ 1 - exp(-k * LAI)
        Slightly higher uncertainty than camera (coarser resolution).
        """
        lai = state_values[IDX_LAI]
        k = 0.5  # extinction coefficient for satellite scale
        
        predicted = 1.0 - math.exp(-k * lai)
        
        H = [0.0] * N_STATES
        H[IDX_LAI] = k * math.exp(-k * lai)
        
        R = 0.10 ** 2  # Slightly higher than camera (coarser pixels)
        
        return predicted, H, R

    @staticmethod
    def rgb_anomaly_score(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        RGB anomaly score (0–1) — weak structural-stress proxy.
        
        Maps to canopy_stress but with HIGHER sigma and MODERATE
        reliability ceiling. This is NOT a disease or water-specific
        signal — it is a structural heterogeneity indicator from RGB.
        
        The ValidationGraph will arbitrate against NDVI/NDMI/SAR/weather.
        
        Model: y_obs ≈ canopy_stress + noise (large)
        """
        stress = state_values[IDX_CANOPY_STRESS]
        
        predicted = stress
        
        H = [0.0] * N_STATES
        H[IDX_CANOPY_STRESS] = 1.0
        
        # HIGH uncertainty — this is a weak proxy, not a direct measurement
        R = 0.40 ** 2  # Higher than camera stress_proxy (0.30)
        
        return predicted, H, R

    # ================================================================
    # Farmer Photo engine V1 observation models
    # ================================================================

    @staticmethod
    def farmer_photo_canopy(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        Farmer Photo local canopy cover (0–1).

        Same physics as camera_canopy_cover (LAI via cover fraction)
        but from a single close-range photo — point scope, not plot.

        Higher sigma than camera-on-tripod (0.12 vs 0.08) because
        phone photos have variable framing and represent ~1-10 m².

        Reliability ceiling: 0.75 (lower than camera).
        """
        lai = state_values[IDX_LAI]
        k = 0.5

        predicted = 1.0 - math.exp(-k * lai)

        H = [0.0] * N_STATES
        H[IDX_LAI] = k * math.exp(-k * lai)

        R = 0.12 ** 2  # Higher than camera (0.08)

        return predicted, H, R

    @staticmethod
    def farmer_photo_symptom(state_values: List[float]) -> Tuple[float, List[float], float]:
        """
        Farmer Photo symptom probability → canopy_stress proxy.

        Maps visible symptom evidence to the canopy_stress state variable.
        This is symptom-first, not disease-first:
          - High value = visible stress symptoms
          - NOT a specific disease diagnosis

        Higher sigma than satellite rgb_anomaly_score (0.40) because
        close-range symptom detection is more targeted but represents
        only a single point observation.

        Reliability ceiling: 0.50 (moderate — not a diagnosis).
        """
        stress = state_values[IDX_CANOPY_STRESS]

        predicted = stress

        H = [0.0] * N_STATES
        H[IDX_CANOPY_STRESS] = 1.0

        # Moderate-high uncertainty — symptom proxy, not biophysical measurement
        R = 0.35 ** 2

        return predicted, H, R


# ============================================================================
# Observation Dispatcher — routes observation type to the right model
# ============================================================================

def get_observation_model(obs_type: str, **kwargs):
    """
    Given an observation type string, return the appropriate model function.
    
    Returns: callable(state_values) -> (predicted, H, R)
    """
    MODELS = {
        "ndvi": ObservationModel.sentinel2_ndvi,
        "evi": ObservationModel.sentinel2_evi,
        "ndmi": ObservationModel.sentinel2_ndmi,
        "vv": ObservationModel.sentinel1_vv,
        "vh": ObservationModel.sentinel1_vh,
        "canopy_cover": ObservationModel.camera_canopy_cover,
        "phenology_stage": ObservationModel.phenology_stage_camera,
        "stress_proxy": ObservationModel.stress_proxy,
        # Satellite RGB engine V1 observation types
        "vegetation_fraction": ObservationModel.satellite_rgb_vegetation,
        "rgb_anomaly_score": ObservationModel.rgb_anomaly_score,
        # Farmer Photo engine V1 observation types
        "farmer_photo_canopy": ObservationModel.farmer_photo_canopy,
        "farmer_photo_symptom": ObservationModel.farmer_photo_symptom,
    }
    
    if obs_type == "soil_moisture":
        depth = kwargs.get("depth_cm", 10.0)
        return lambda sv: ObservationModel.soil_sensor_moisture(sv, depth)
    
    model = MODELS.get(obs_type)
    if model is None:
        raise ValueError(f"Unknown observation type: {obs_type}")
    
    return model


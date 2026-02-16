
from dataclasses import dataclass, field
from typing import Dict, Any, List

from services.agribrain.layer1_fusion.schema import FieldTensor, FieldTensorChannels
from services.agribrain.layer2_veg_int.schema import VegIntOutput, PhenologyStage
    # ... (imports)
from services.agribrain.layer3_decision.schema import PlotContext, Driver

@dataclass
class DecisionFeatures:
    """
    Frozen snapshot of features for Decision Audit.
    """
    # Water Context (L1 Raw)
    rain_sum_7d: float
    rain_sum_14d: float
    days_since_rain: int
    soil_moisture_proxy: float 
    
    # Crop State (L2 Derived)
    current_stage: str
    days_in_stage: int
    stage_confidence: float
    growth_adequacy: float 
    growth_velocity_7d: float 
    
    # Anomalies (L2 Derived)
    has_anomaly: bool
    anomaly_severity: float
    anomaly_type: str
    anomaly_duration: int
    
    # Structure (L1 Raw SAR + L2 Stability)
    sar_vv_trend_7d: float 
    sar_roughness_change: float 
    
    # Stability (L2)
    spatial_stability: str 
    spatial_confidence: float
    
    # Data Quality / Availability (L1 Meta)
    sar_available: bool
    rain_available: bool
    temp_available: bool
    optical_available: bool
    missing_inputs: List[Driver]
    sar_obs_count: int
    optical_obs_count: int
    
    # Thermal & Saturation (L1 Raw)
    heat_stress_days: int 
    cold_stress_days: int 
    saturation_days: int 

def build_decision_features(
    tensor: FieldTensor, 
    veg: VegIntOutput, 
    context: PlotContext
) -> DecisionFeatures:
    """
    Pure function: L1 (Ground Truth) + L2 (Interpretation) -> Decision Features.
    Strictly checks tensor.channels before using L1 data.
    """
    n = len(tensor.time_index)
    missing: List[Driver] = []
    
    if n == 0:
        return _empty_features()
        
    # --- 1. Channel Availability Check ---
    # We use string values from the Enum to check against tensor.channels list (which are strings)
    has_rain = FieldTensorChannels.PRECIPITATION.value in tensor.channels
    has_tmax = FieldTensorChannels.TEMP_MAX.value in tensor.channels
    has_tmin = FieldTensorChannels.TEMP_MIN.value in tensor.channels
    has_vv = FieldTensorChannels.VV.value in tensor.channels
    has_ndvi = FieldTensorChannels.NDVI.value in tensor.channels
    
    # --- 2. Weather Features (Source: Layer 1 plot_timeseries) ---
    rain_series = []
    tmax_series = []
    tmin_series = []
    
    if has_rain:
        rain_series = [r.get(FieldTensorChannels.PRECIPITATION.value) for r in tensor.plot_timeseries]
    else:
        missing.append(Driver.RAIN)
        
    if has_tmax:
        tmax_series = [r.get(FieldTensorChannels.TEMP_MAX.value) for r in tensor.plot_timeseries]
    if has_tmin:
        tmin_series = [r.get(FieldTensorChannels.TEMP_MIN.value) for r in tensor.plot_timeseries]
        
    if not has_tmax or not has_tmin:
        missing.append(Driver.TEMP)

    # Metric Calculation
    # Filter Nones (L1 might have gaps even if channel exists)
    valid_rain = [r for r in rain_series if r is not None]
    rain_available = len(valid_rain) > (n * 0.5) and has_rain
    if has_rain and not rain_available: missing.append(Driver.RAIN) # Gap even if channel present

    rain_7d = sum(valid_rain[-7:]) if len(valid_rain) >= 7 else sum(valid_rain)
    rain_14d = sum(valid_rain[-14:]) if len(valid_rain) >= 14 else sum(valid_rain)
    
    # Days dry
    days_dry = 0
    clean_rain = [r if r is not None else 0.0 for r in rain_series]
    for r in reversed(clean_rain):
        if r > 2.0: break
        days_dry += 1
        
    # Thermal
    valid_tmax = [t for t in tmax_series if t is not None]
    valid_tmin = [t for t in tmin_series if t is not None]
    temp_available = (len(valid_tmax) > 5) and has_tmax
    
    heat_days = 0
    cold_days = 0
    if temp_available:
        heat_days = sum(1 for t in valid_tmax[-7:] if t > 30.0) if len(valid_tmax) >= 7 else 0
        cold_days = sum(1 for t in valid_tmin[-7:] if t < 10.0) if len(valid_tmin) >= 7 else 0
        
    saturation_days = sum(1 for r in valid_rain[-7:] if r > 15.0) if len(valid_rain) >= 7 else 0

    # --- 3. Crop State (Source: Layer 2) ---
    curr_stage = veg.phenology.stage_by_day[-1] if veg.phenology.stage_by_day else "BARE_SOIL"
    stage_conf = veg.phenology.confidence_by_day[-1] if veg.phenology.confidence_by_day else 0.5
    
    days_in = 0
    stages = veg.phenology.stage_by_day
    if stages:
        for s in reversed(stages):
            if s != curr_stage: break
            days_in += 1
            
    velocity = 0.0
    if hasattr(veg.curve, 'ndvi_fit_d1') and veg.curve.ndvi_fit_d1:
        velocity = veg.curve.ndvi_fit_d1[-1]
    
    # Counts
    optical_obs_count = 0
    if has_ndvi:
        optical_obs_count = len([x for x in tensor.plot_timeseries if x.get(FieldTensorChannels.NDVI.value) is not None])
    
    # Strict Threshold from v4.0 Spec: WEATHER_ONLY if count < 2
    optical_available = optical_obs_count >= 2
    if not optical_available:
        missing.append(Driver.NDVI)

    # --- 4. Anomalies (Source: Layer 2) ---
    active_anomaly = None
    last_date = tensor.time_index[-1]
    for a in veg.anomalies:
        if a.date_range[0] <= last_date <= a.date_range[1] or a.date_range[1] == last_date:
            active_anomaly = a
            break

    # --- 5. SAR (Source: Layer 1 plot_timeseries) ---
    sar_available = False
    vv_trend = 0.0
    roughness_change = 0.0
    valid_vv = []
    sar_obs_count = 0
    
    if has_vv:
        vv_series = [r.get(FieldTensorChannels.VV.value) for r in tensor.plot_timeseries]
        valid_vv = [v for v in vv_series if v is not None]
        sar_obs_count = len(valid_vv)
        
        # Strict Threshold from v4.0 Spec: NO_SAR if count <= 5
        sar_available = sar_obs_count > 5
    else:
        missing.append(Driver.SAR_VV)
        sar_available = False
    
    if sar_available and len(valid_vv) >= 7:
        recent_vv = valid_vv[-3:]
        past_vv = valid_vv[-7:-4]
        vv_trend = (sum(recent_vv)/3) - (sum(past_vv)/3)
        
        # Roughness proxy: Variance change
        def var(data): return sum((x - (sum(data)/len(data)))**2 for x in data) / len(data)
        var_recent = var(recent_vv)
        var_past = var(past_vv)
        roughness_change = var_recent - var_past 
    elif not sar_available:
        # If available but low count, explicit missing
        if Driver.SAR_VV not in missing: missing.append(Driver.SAR_VV)

    return DecisionFeatures(
        rain_sum_7d=rain_7d,
        rain_sum_14d=rain_14d,
        days_since_rain=days_dry,
        soil_moisture_proxy=0.5, 
        
        current_stage=curr_stage,
        days_in_stage=days_in,
        stage_confidence=stage_conf,
        growth_adequacy=1.0 - (active_anomaly.severity if active_anomaly else 0.0),
        growth_velocity_7d=velocity,
        
        has_anomaly=active_anomaly is not None,
        anomaly_severity=active_anomaly.severity if active_anomaly else 0.0,
        anomaly_type=active_anomaly.type.value if active_anomaly else "NONE",
        anomaly_duration=0, 
        
        sar_vv_trend_7d=vv_trend,
        sar_roughness_change=roughness_change,
        
        spatial_stability=veg.stability.stability_class,
        spatial_confidence=veg.stability.confidence,
        
        sar_available=sar_available,
        rain_available=rain_available,
        temp_available=temp_available,
        optical_available=optical_available,
        missing_inputs=list(set(missing)), # Dedup
        sar_obs_count=sar_obs_count,
        optical_obs_count=optical_obs_count,
        
        heat_stress_days=heat_days,
        cold_stress_days=cold_days,
        saturation_days=saturation_days
    )

def _empty_features():
    # Use empty list for missing inputs
    return DecisionFeatures(0,0,0,0,"UNKNOWN",0,0,0,0,False,0,"NONE",0,0,0,"UNKNOWN",0, False, False, False, False, [], 0, 0, 0, 0, 0)

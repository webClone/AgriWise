
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
    sar_available: bool # True if count > 0
    low_sar_cadence: bool # True if 0 < count <= 5
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
    channel_values = [c.value if hasattr(c, "value") else c for c in tensor.channels]
    ts_keys = set(tensor.plot_timeseries[-1].keys()) if tensor.plot_timeseries else set()
    
    has_rain = "precipitation" in channel_values or "rain" in ts_keys
    has_tmax = "temp_max" in channel_values or "tmax" in ts_keys or "tmean" in ts_keys
    has_tmin = "temp_min" in channel_values or "tmin" in ts_keys or "tmean" in ts_keys
    has_vv = "vv" in channel_values or "vv_db" in ts_keys
    has_ndvi = "ndvi" in channel_values or "ndvi" in ts_keys
    
    # --- 2. Weather Features (Source: Layer 1 plot_timeseries) ---
    rain_series = []
    tmax_series = []
    tmin_series = []
    
    if has_rain:
        rain_series = [r.get("rain", 0.0) for r in tensor.plot_timeseries]
    else:
        missing.append(Driver.RAIN)
        
    if has_tmax:
        tmax_series = [r.get("tmax", r.get("tmean", 0.0)) for r in tensor.plot_timeseries]
    if has_tmin:
        tmin_series = [r.get("tmin", r.get("tmean", 0.0)) for r in tensor.plot_timeseries]
        
    if not has_tmax or not has_tmin:
        missing.append(Driver.TEMP)

    # Metric Calculation
    # We must operate on the aligned time series (last N days), treating None as 0.0 or ignored within the window.
    # Using 'valid_rain' collapses time gaps, which is wrong for "last 14 days".
    
    clean_rain = [r if r is not None else 0.0 for r in rain_series]
    
    # Check availability on the raw SERIES (if too many Nones in last 14 days, it's missing)
    # But for calculation, we use clean_rain.
    
    # Availability Logic (Global or Window based?)
    # User spec: DATA_GAP if critical data missing.
    # Let's say if > 50% of total series is valid? Or recent?
    # Existing logic: len(valid_rain) > n * 0.5. Keeping it for now.
    valid_rain = [r for r in rain_series if r is not None]
    rain_available = len(valid_rain) > (n * 0.5) and has_rain
    if has_rain and not rain_available: missing.append(Driver.RAIN)

    # Sums on TEMPORAL window (last 7/14 indices)
    rain_7d = sum(clean_rain[-7:]) if n >= 7 else sum(clean_rain)
    rain_14d = sum(clean_rain[-14:]) if n >= 14 else sum(clean_rain)
    
    # Days dry
    days_dry = 0
    # Clean rain is already 0.0 for Nones
    for r in reversed(clean_rain):
        if r > 2.0: break
        days_dry += 1
        
    # Thermal
    # For temperature, we can't assume 0.0. We should filter Nones within the window.
    tmax_window_7d = tmax_series[-7:] if n >= 7 else tmax_series
    tmin_window_7d = tmin_series[-7:] if n >= 7 else tmin_series
    
    valid_tmax_7d = [t for t in tmax_window_7d if t is not None]
    valid_tmin_7d = [t for t in tmin_window_7d if t is not None]
    
    # Availability check (global)
    valid_tmax_all = [t for t in tmax_series if t is not None]
    temp_available = (len(valid_tmax_all) > 5) and has_tmax
    
    heat_days = 0
    cold_days = 0
    if temp_available:
        heat_days = sum(1 for t in valid_tmax_7d if t > 30.0)
        cold_days = sum(1 for t in valid_tmin_7d if t < 10.0)
        
    saturation_days = sum(1 for r in clean_rain[-7:] if r > 15.0) if n >= 7 else 0

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
        optical_obs_count = len([x for x in tensor.plot_timeseries if x.get("ndvi") is not None])
    
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
    low_sar_cadence = False
    vv_trend = 0.0
    roughness_change = 0.0
    valid_vv = []
    sar_obs_count = 0
    
    if has_vv:
        vv_series = [r.get("vv_db", r.get("vv", r.get("vv_interpolated"))) for r in tensor.plot_timeseries]
        valid_vv = [v for v in vv_series if v is not None]
        sar_obs_count = len(valid_vv)
        
        sar_available = sar_obs_count > 0
        low_sar_cadence = 0 < sar_obs_count <= 5
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
        low_sar_cadence=low_sar_cadence,
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
    return DecisionFeatures(0,0,0,0,"UNKNOWN",0,0,0,0,False,0,"NONE",0,0,0,"UNKNOWN",0, False, False, False, False, False, [], 0, 0, 0, 0, 0)

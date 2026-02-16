

from typing import Dict, Any, List, Optional
from services.agribrain.layer1_fusion.schema import FieldTensor, FieldTensorChannels
from services.agribrain.layer3_decision.schema import PlotContext

class SoilWaterBalanceEngine:
    """
    Layer 4.1: Soil & Water Balance Engine (SWB)
    Objective: Estimate root-zone water content to separate "true nutrient stress"
    from "water-limited growth".
    """
    
    def __init__(self):
        # Default Soil Parameters (Loam-like)
        self.default_theta_fc = 0.35 # Field Capacity (volumetric)
        self.default_theta_wp = 0.15 # Wilting Point
        self.default_root_depth = 1000 # mm
        
    def run(self, tensor: FieldTensor, context: PlotContext) -> Dict[str, Any]:
        """
        Run the bucket model daily.
        
        Outputs:
        - daily_theta: Time series of soil moisture
        - water_stress_index: mean stress over last window
        - leaching_risk: daily risk 0-1
        - drainage_mm: total drainage
        """
        # 1. Extract Soil Props from Context
        # TODO: Parse context.soil_properties if available
        fc = self.default_theta_fc
        wp = self.default_theta_wp
        rd = self.default_root_depth # mm
        
        taw_mm = (fc - wp) * rd # Total Available Water in Root Zone
        
        # 2. Extract Weather Series
        # We need sequential access.
        # tensor.plot_timeseries is List[Dict] usually.
        # We need to ensure we map correct channels.
        
        ts = tensor.plot_timeseries
        n_days = len(ts)
        
        theta_curr_mm = taw_mm * 0.7 + (wp * rd) # Start at 70% TAW + WP
        
        daily_stress = []
        daily_leaching_risk = []
        total_drainage = 0.0
        
        for day_data in ts:
            # Inputs
            rain = day_data.get(FieldTensorChannels.PRECIPITATION.value) or 0.0
            # TODO: Add Irrigation channel if exists in L1 or Context Events
            irr = 0.0 
            
            # ET0 (Reference Evapotranspiration)
            # If not in tensor, estimate from Tmax/Tmin (Hargreaves simplified or just dummy)
            # Using simple approx if missing: 4mm mean adjusted by Temp
            tmax = day_data.get(FieldTensorChannels.TEMP_MAX.value) or 30.0
            et0 = 4.0 * (tmax / 30.0) # Very rough proxy if missing
            
            # Kc (Crop Coefficient) - should depend on Phenology but simplified here
            # Assuming mid-season
            kc = 1.0 
            etc = et0 * kc
            
            # Bucket Balance
            # Inflow
            inflow = rain + irr
            
            # Outflow
            outflow = etc
            
            # Update
            theta_next_mm = theta_curr_mm + inflow - outflow
            
            # Drainage (Saturation excess)
            fc_mm = fc * rd
            drainage = 0.0
            if theta_next_mm > fc_mm:
                drainage = theta_next_mm - fc_mm
                theta_next_mm = fc_mm
            
            total_drainage += drainage
            
            # Leaching Risk
            # High if drainage > 0 and (Rain > 20mm or Irr > 20mm)
            l_risk = 0.0
            if drainage > 5.0: 
                l_risk = 0.5 + min(drainage/20.0, 0.5) # Max 1.0
            daily_leaching_risk.append(l_risk)
            
            # Water Stress (KS)
            # Stress starts when depletion fraction p is reached (usually 0.5 of TAW)
            wp_mm = wp * rd
            raw_mm = (fc_mm - wp_mm) # Readily available? No, TAW.
            
            # Current available
            paw_curr = max(0, theta_curr_mm - wp_mm)
            
            # Stress factor ks (0=Full Stress, 1=No Stress)
            # Simple linear ramp: if PAW < 50% TAW -> decline
            p_fraction = 0.5
            threshold = taw_mm * (1 - p_fraction) 
            
            ks = 1.0
            if paw_curr < threshold:
                ks = paw_curr / threshold
            
            # We want "Stress Index" where 1.0 = High Stress
            wsi = 1.0 - ks
            daily_stress.append(wsi)
            
            theta_curr_mm = theta_next_mm
            
        # 3. Aggregate Metrics (Last 14 days)
        recent_stress = 0.0
        recent_leaching = 0.0
        if n_days > 0:
            window = min(n_days, 14)
            data_window_stress = daily_stress[-window:]
            data_window_leaching = daily_leaching_risk[-window:]
            
            recent_stress = sum(data_window_stress) / len(data_window_stress) if data_window_stress else 0.0
            recent_leaching = max(data_window_leaching) if data_window_leaching else 0.0
            
        return {
            "water_stress_index": recent_stress,
            "leaching_risk_index": recent_leaching,
            "drainage_accum_mm": total_drainage,
            "is_water_limiting": recent_stress > 0.4,
            "soil_moisture_mm": theta_curr_mm # Final state
        }

"""
Layer 1.2: Cloud & Noise Correction Engine (Refined)
Aligns with the 8-Step Fusion Pipeline.
Supports degradation to Pure Python if dependencies are missing.
"""

from typing import Dict, List, Any, Optional
import math

# Try imports
try:
    import numpy as np
    import pandas as pd
    from scipy.signal import savgol_filter
    HAS_SCI = True
except ImportError:
    HAS_SCI = False
    np = None
    pd = None
    savgol_filter = None

class CorrectionPipeline:
    """
    Handles temporal smoothing and outlier removal.
    """
    
    def apply_smoothing(self, timeseries: List[Dict], feature: str = "ndvi_mean") -> List[Dict]:
        """
        Apply smoothing to a timeseries list of dicts.
        Uses Savitzky-Golay if available, else Moving Average.
        """
        if not timeseries:
            return []
            
        if HAS_SCI:
            return self._apply_sg_smoothing(timeseries, feature)
        else:
            return self._apply_moving_average_pure_python(timeseries, feature)

    def _apply_sg_smoothing(self, timeseries: List[Dict], feature: str) -> List[Dict]:
        """Original SciPy Logic"""
        # Extract series
        df = pd.DataFrame(timeseries)
        if feature not in df.columns:
            return timeseries
            
        # Ensure numeric
        raw_data = pd.to_numeric(df[feature], errors='coerce')
        
        # Interpolate
        dense_data = raw_data.interpolate(method='linear').bfill().ffill()
        
        if len(dense_data) > 7:
            try:
                smoothed = savgol_filter(dense_data, window_length=7, polyorder=2)
                df[f"{feature}_smoothed"] = smoothed
            except Exception as e:
                print(f"[Corrections] SG Filter failed: {e}")
                df[f"{feature}_smoothed"] = dense_data
        else:
            df[f"{feature}_smoothed"] = dense_data
            
        return df.to_dict('records')

    def _apply_moving_average_pure_python(self, timeseries: List[Dict], feature: str) -> List[Dict]:
        """Fallback Logic"""
        print(f"[Corrections] Scientific stack missing. Using Pure Python Moving Average for {feature}.")
        
        # Extract values
        values = []
        for row in timeseries:
            val = row.get(feature)
            # Handle Nan/None
            if val is None or (isinstance(val, float) and math.isnan(val)):
                values.append(None)
            else:
                values.append(float(val))
        
        # Simple Linear Fill first
        filled = self._fill_gaps_linear(values)
        
        # Moving Average (Window 3)
        smoothed = []
        window = 3
        for i in range(len(filled)):
            start = max(0, i - window // 2)
            end = min(len(filled), i + window // 2 + 1)
            chunk = filled[start:end]
            if chunk:
                smoothed.append(sum(chunk) / len(chunk))
            else:
                smoothed.append(filled[i])
                
        # Inject back
        new_series = []
        for i, row in enumerate(timeseries):
             new_row = row.copy()
             new_row[f"{feature}_smoothed"] = smoothed[i]
             new_series.append(new_row)
             
        return new_series

    def _fill_gaps_linear(self, values: List[Optional[float]]) -> List[float]:
        """Simple Pure Python Linear Interpolation"""
        n = len(values)
        if n == 0: return []
        
        # Find verified indices
        valid_indices = [i for i, v in enumerate(values) if v is not None]
        
        if not valid_indices:
            return [0.0] * n # No data at all
            
        out = list(values)
        
        # Fill ends (Forward/Back fill)
        first_valid = valid_indices[0]
        for i in range(first_valid):
            out[i] = values[first_valid]
            
        last_valid = valid_indices[-1]
        for i in range(last_valid + 1, n):
            out[i] = values[last_valid]
            
        # Linear Interp between valid points
        for k in range(len(valid_indices) - 1):
            i_start = valid_indices[k]
            i_end = valid_indices[k+1]
            v_start = values[i_start]
            v_end = values[i_end]
            
            gap_size = i_end - i_start
            step = (v_end - v_start) / gap_size
            
            for j in range(1, gap_size):
                out[i_start + j] = v_start + (step * j)
                
        return out

# Singleton
correction_engine = CorrectionPipeline()

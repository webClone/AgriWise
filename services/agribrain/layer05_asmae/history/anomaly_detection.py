"""
Historical Anomaly Detection.
Tracks deviations of recent states from calculated historical seasonal profiles
using standard deviations (z-scores).
"""
import math
from typing import Dict, Any, List, Optional
from datetime import datetime

class HistoricalAnomalyDetector:
    def __init__(self, z_threshold: float = 2.0):
        self.z_threshold = z_threshold

    def detect_anomalies(
        self,
        current_date: datetime,
        current_value: float,
        seasonal_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculates standard deviation (z-score) of current value against DOY historical mean and std.
        Flags positive/negative anomalies when z-score exceeds the threshold.
        """
        doy = current_date.timetuple().tm_yday
        mean_map = seasonal_profile.get("mean", {})
        std_map = seasonal_profile.get("std", {})
        
        # Check if baseline data exists for this DOY
        if doy not in mean_map:
            return {"is_anomaly": False, "z_score": 0.0, "reason": "no_baseline_data"}
            
        mean_val = mean_map[doy]
        std_val = std_map[doy]
        
        # Avoid division by zero
        if std_val < 1e-5:
            # If standard deviation is 0, we can compare absolute difference
            diff = current_value - mean_val
            is_anomaly = abs(diff) > 0.25 # arbitrary absolute limit fallback
            return {
                "is_anomaly": is_anomaly,
                "z_score": 99.0 if diff > 0 else -99.0 if diff < 0 else 0.0,
                "deviation": float(diff),
                "reason": "zero_historical_variance"
            }
            
        z_score = (current_value - mean_val) / std_val
        is_anomaly = abs(z_score) > self.z_threshold
        
        return {
            "is_anomaly": is_anomaly,
            "z_score": float(z_score),
            "deviation": float(current_value - mean_val),
            "reason": f"z_score_exceeds_{self.z_threshold}" if is_anomaly else "normal"
        }

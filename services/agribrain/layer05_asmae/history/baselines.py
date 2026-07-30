"""
Historical Baselines.
Calculates historical percentiles (10th, 50th, 90th) by day-of-year (DOY)
over multi-year smoothed state timelines.
"""
from typing import List, Dict, Any, Tuple
import numpy as np
from datetime import datetime

class HistoricalBaselines:
    def __init__(self):
        pass

    def compute_doy_percentiles(
        self,
        timestamps: List[datetime],
        states: List[np.ndarray],
        state_idx: int
    ) -> Dict[int, Tuple[float, float, float]]:
        """
        Groups state values by day-of-year (1-366) and calculates the 10th, 50th, and 90th percentiles.
        Returns a dictionary mapping DOY to (p10, p50, p90) tuples.
        """
        doy_values: Dict[int, List[float]] = {}
        for t, x in zip(timestamps, states):
            doy = t.timetuple().tm_yday
            val = float(x[state_idx])
            doy_values.setdefault(doy, []).append(val)

        baselines = {}
        for doy, vals in doy_values.items():
            arr = np.array(vals)
            p10 = float(np.percentile(arr, 10))
            p50 = float(np.percentile(arr, 50))
            p90 = float(np.percentile(arr, 90))
            baselines[doy] = (p10, p50, p90)
            
        return baselines

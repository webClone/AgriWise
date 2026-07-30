"""
Seasonal Profiles.
Groups states by calendar year and day-of-year to build seasonal envelopes
containing mean, standard deviation, min, and max.
"""
from typing import List, Dict, Any
import numpy as np
from datetime import datetime

class SeasonalProfiles:
    def __init__(self):
        pass

    def build_envelope(
        self,
        timestamps: List[datetime],
        states: List[np.ndarray],
        state_idx: int
    ) -> Dict[str, Any]:
        """
        Builds a seasonal envelope for a single state variable.
        Returns aggregated stats (mean, std, min, max) keyed by day-of-year (DOY).
        """
        doy_values: Dict[int, List[float]] = {}
        for t, x in zip(timestamps, states):
            doy = t.timetuple().tm_yday
            val = float(x[state_idx])
            doy_values.setdefault(doy, []).append(val)

        mean_profile = {}
        std_profile = {}
        min_profile = {}
        max_profile = {}

        for doy, vals in doy_values.items():
            arr = np.array(vals)
            mean_profile[doy] = float(np.mean(arr))
            std_profile[doy] = float(np.std(arr)) if len(arr) > 1 else 0.0
            min_profile[doy] = float(np.min(arr))
            max_profile[doy] = float(np.max(arr))

        return {
            "mean": mean_profile,
            "std": std_profile,
            "min": min_profile,
            "max": max_profile
        }


"""
Layer 2.3: Temporal Anomaly Engine
Detects deviations between observed data and the biological growth model.
Types: STALL (Slow growth), DROP (Sudden loss), EARLY_SENESCENCE.
"""

import statistics
from typing import List, Dict, Tuple
from layer2_veg_int.schema import VegetationAnomaly, AnomalyType

class TemporalAnomalyEngine:
    
    def __init__(self, z_threshold: float = 2.0, persistence_days: int = 3):
        self.z_threshold = z_threshold
        self.persistence_days = persistence_days

    def detect_anomalies(
        self,
        dates: List[str],
        observed_ndvi: List[float],
        modeled_ndvi: List[float],
        uncertainties: List[float],
        rainfall: List[float] = None,
        sar_vv: List[float] = None,
        sar_vh: List[float] = None
    ) -> List[VegetationAnomaly]:
        """
        Compares observed vs modeled to find significant negative deviations.
        Attribution uses Rain, SAR, and Context.
        """
        anomalies = []
        n = len(dates)
        if n == 0: return []
        
        # Pure Python Residuals & Z-Score
        # Residual = Observed - Modeled
        z_scores = []
        
        for i in range(n):
            obs_val = observed_ndvi[i]
            mod_val = modeled_ndvi[i]
            unc_val = uncertainties[i] + 0.02 # Add baseline noise floor
            
            # If obs is None (missing data), z-score is 0
            if obs_val is None:
                z_scores.append(0.0)
                continue

            res = obs_val - mod_val
            z = res / unc_val
            z_scores.append(z)
        
        # 2. Scanning for persistent negative deviations
        # We look for runs where z_score < -Threshold
        
        in_anomaly = False
        start_idx = 0
        
        for i in range(n):
            z = z_scores[i]
            is_bad = z < -self.z_threshold
            
            if is_bad and not in_anomaly:
                in_anomaly = True
                start_idx = i
                
            elif not is_bad and in_anomaly:
                duration = i - start_idx
                if duration >= self.persistence_days:
                    self._create_anomaly(
                        anomalies, dates, observed_ndvi, modeled_ndvi, start_idx, i, z_scores, 
                        rainfall, sar_vv
                    )
                in_anomaly = False
                
        if in_anomaly:
            duration = n - start_idx
            if duration >= self.persistence_days:
                 self._create_anomaly(
                        anomalies, dates, observed_ndvi, modeled_ndvi, start_idx, n, z_scores, 
                        rainfall, sar_vv
                    )
                    
        return anomalies

    def _create_anomaly(self, list_ref, dates, obs, mod, start, end, z_scores, rainfall=None, sar_vv=None):
        """Helper to classify and package the anomaly"""
        segment_z = z_scores[start:end]
        mean_z = statistics.mean(segment_z)
        severity = min(abs(mean_z) / 5.0, 1.0)
        
        a_type = AnomalyType.STALL if abs(mean_z) < 3.0 else AnomalyType.DROP
        a_id = f"{dates[start]}_{a_type.value}"
        
        valid_diffs = []
        for i in range(start, end):
             if obs[i] is not None:
                 valid_diffs.append(obs[i] - mod[i])
        avg_diff = abs(statistics.mean(valid_diffs)) if valid_diffs else 0.0

        # --- Enhanced Causal Attribution (User Request) ---
        cause = "UNKNOWN_STRESS"
        
        # 1. Rain Context
        rain_sum = 0.0
        if rainfall:
            ctx_start = max(0, start - 14)
            # Sum rain
            rain_sum = sum(filter(None, rainfall[ctx_start:end]))
            
        # 2. SAR Context (Structure Loss)
        # If VV increases significantly while NDVI drops -> Structure change (Logging/Lodging)
        vv_trend = 0.0
        if sar_vv:
            # Compare mean VV during anomaly vs mean VV before
            before_start = max(0, start - 7)
            vv_before = [v for v in sar_vv[before_start:start] if v is not None]
            vv_during = [v for v in sar_vv[start:end] if v is not None]
            
            if vv_before and vv_during:
                mean_before = sum(vv_before)/len(vv_before)
                mean_during = sum(vv_during)/len(vv_during)
                # If VV increases by > 1.0 dB (approx, assuming linear units or dB? Input is usually dB)
                # Input is likely linear if not converted. Assuming linear for now or small dB diff.
                # Let's assume input is dB. 0.5dB increase is significant.
                delta_vv = mean_during - mean_before
                if delta_vv > 0.5:
                    vv_trend = 1.0
        
        # Decision Logic
        if rain_sum < 5.0:
            cause = "LIKELY_WATER_STRESS"
        elif vv_trend > 0:
            cause = "POSSIBLE_STRUCTURE_LOSS" # Logging / Wind damage
        elif rain_sum > 50.0:
            cause = "POSSIBLE_DISEASE_OR_LOGGING"
        else:
            cause = "GROWTH_STALL"

        list_ref.append(VegetationAnomaly(
            anomaly_id=a_id,
            type=a_type,
            date_range=[dates[start], dates[end-1]],
            severity=float(severity),
            confidence=float(min(abs(mean_z)/3.0, 1.0)),
            description=f"Observed NDVI dropped {avg_diff:.2f} below model.",
            likely_cause=cause
        ))

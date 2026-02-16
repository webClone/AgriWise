
"""
Layer 2.1: Growth Curve Modeling Engine
Converts noisy Layer 1 NDVI into a biologically plausible growth curve.
Algorithm: Weighted Robust Spline / Whittaker Smoother with Constraints.
"""

import math
from typing import List, Dict, Tuple, Optional

try:
    import numpy as np
    from scipy.interpolate import UnivariateSpline
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    np = None

DOY_WINDOW = 3 

class GrowthCurveEngine:
    
    def __init__(self, smoothing_factor: float = 0.5):
        self.s = smoothing_factor

    def fit_growth_curve(
        self, 
        dates: List[str], 
        ndvi_values: List[float], 
        uncertainties: List[float]
    ) -> Tuple[List[float], Dict[str, List[float]], List[float]]:
        """
        Fits a robust curve to the NDVI time series.
        Returns:
            - modeled_curve: Smoothed NDVI per day
            - derivatives: {velocity, acceleration}
            - uncertainty: Standard error of the fit per day
        """
        n = len(ndvi_values)
        if n < 5:
            return ndvi_values, {"velocity": [0.0]*n, "acceleration": [0.0]*n}, uncertainties

        # --- Scientific Mode ---
        if HAS_SCIPY:
            return self._fit_spline_scipy(dates, ndvi_values, uncertainties)
        
        # --- Pure Python Fallback ---
        return self._fit_moving_average_pure(dates, ndvi_values, uncertainties)

    def _fit_spline_scipy(self, dates, ndvi_values, uncertainties):
        x = np.arange(len(ndvi_values))
        y = np.array(ndvi_values)
        w = 1.0 / (np.array(uncertainties) + 0.01)
        
        try:
            # Pass 1
            spline = UnivariateSpline(x, y, w=w, k=3, s=self.s * len(y))
            y_pass1 = spline(x)
            
            # Robust Weights (Huber-like)
            residuals = np.abs(y - y_pass1)
            sigma = np.std(residuals)
            mask = residuals > (1.5 * sigma + 1e-6)
            w_robust = w.copy()
            w_robust[mask] *= 0.1
            
            # Pass 2
            spline_robust = UnivariateSpline(x, y, w=w_robust, k=3, s=self.s * len(y))
            modeled_y = spline_robust(x)
            
            # Derivatives
            d1 = spline_robust.derivative(n=1)(x)
            d2 = spline_robust.derivative(n=2)(x)
            
            # Constraints
            modeled_y = np.clip(modeled_y, -0.2, 1.0)
            
            # Approximate Fit Uncertainty
            # Using moving average of inverse variance (information density)
            # Propagated SE = 1 / sqrt(Sum(weights)) roughly
            n_points = len(y)
            fit_unc = []
            
            # Vectorized approximation for speed 
            # (Assuming window ~ 15 days like pure python)
            # Convolve weights with window
            window_size = 15
            kernel = np.ones(window_size)
            
            # Using inverse-variance weights (approx w_robust^2 since w was 1/sigma)
            # Wait, w was 1/sigma, so precision = w^2.
            # Local precision sum = convolve(w^2, kernel)
            # Local sigma = 1 / sqrt(sum)
            
            precisions = w_robust ** 2
            sum_precisions = np.convolve(precisions, kernel, mode='same')
            fit_unc_arr = 1.0 / np.sqrt(sum_precisions + 1e-6)
            
            return modeled_y.tolist(), {
                "velocity": d1.tolist(),
                "acceleration": d2.tolist()
            }, fit_unc_arr.tolist()
            
        except Exception as e:
            print(f"⚠️ [GrowthEngine] Spline failed: {e}. Fallback to linear.")
            return ndvi_values, {"velocity": [0.0]*len(y), "acceleration": [0.0]*len(y)}, uncertainties

    def _fit_moving_average_pure(self, dates, ndvi_values, uncertainties):
        """Pure Python Weighted Moving Average with Outlier Rejection"""
        print(f"⚠️ [GrowthEngine] Running in Pure Python Fallback Mode")
        n = len(ndvi_values)
        
        # Dynamic Window Strategy (User Request)
        # 10% of season length, min 7, max 30
        window = max(7, min(30, int(n * 0.1)))
        half = window // 2
        
        # Initial weights (1/sigma)
        w_current = [1.0/(u+0.01) for u in uncertainties]
        
        # Function to smooth
        def smooth(weights):
            res = []
            unc_out = []
            for i in range(n):
                start = max(0, i - half)
                end = min(n, i + half + 1)
                chunk = ndvi_values[start:end]
                w_chunk = weights[start:end]
                
                # Value
                num = sum(c*w for c, w in zip(chunk, w_chunk))
                den = sum(w_chunk)
                val = num / den if den > 0 else 0.0
                res.append(max(-0.2, min(1.0, val)))
                
                # Uncertainty
                sum_precision = sum(w*w for w in w_chunk)
                sigma_fit = 1.0 / math.sqrt(sum_precision + 1e-9)
                unc_out.append(sigma_fit)
                
            return res, unc_out

        # Pass 1
        pass1, _ = smooth(w_current)
        
        # Re-weighting (Robustness)
        w_robust = list(w_current)
        residuals = [abs(o - m) for o, m in zip(ndvi_values, pass1)]
        
        # Calculate sigma (approximate)
        if len(residuals) > 1:
            mean_res = sum(residuals) / len(residuals)
            variance = sum((r - mean_res)**2 for r in residuals) / (len(residuals)-1)
            sigma = math.sqrt(variance)
        else:
            sigma = 0.1
            
        threshold = 1.5 * sigma + 1e-6
        
        outlier_count = 0
        for i in range(n):
            if residuals[i] > threshold:
                w_robust[i] *= 0.1 # Downweight outlier
                outlier_count += 1
                
        # Saturation Check (User Request)
        outlier_frac = outlier_count / n if n > 0 else 0.0
        if outlier_frac > 0.3:
            print(f"⚠️ [GrowthEngine] High Outlier Fraction: {outlier_frac:.2%}. Model quality degraded.")
            # In future, we might return a flag, but for now we proceed with best effort.
            
        # Pass 2
        final_curve, final_unc = smooth(w_robust)
            
        # numerical derivatives
        velocity = [0.0] * n
        for i in range(1, n):
            velocity[i] = final_curve[i] - final_curve[i-1]
            
        return final_curve, {"velocity": velocity, "acceleration": [0.0]*n}, final_unc

    def compute_integrals(self, curve: List[float]) -> Dict[str, float]:
        """Computes AUC and Peak."""
        if not curve:
            return {"auc_season": 0.0, "peak_value": 0.0, "peak_day_index": 0}
            
        if HAS_SCIPY:
            arr = np.array(curve)
            auc = np.sum(arr[arr > 0])
            return {
                "auc_season": float(auc),
                "peak_value": float(np.max(arr)),
                "peak_day_index": int(np.argmax(arr))
            }
        else:
            auc = sum(c for c in curve if c > 0)
            peak_val = max(curve)
            peak_idx = curve.index(peak_val)
            return {
                "auc_season": float(auc),
                "peak_value": float(peak_val),
                "peak_day_index": peak_idx
            }

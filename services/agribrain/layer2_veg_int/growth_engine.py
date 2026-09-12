
"""
Layer 2.1: Growth Curve Modeling Engine (v3.1)

Converts noisy Layer 1 NDVI into a biologically plausible growth curve.

Algorithms (in priority order):
  1. Whittaker-Henderson smoother with GCV-adaptive lambda selection
     and upper-envelope bias correction (Eilers 2003, Chen et al. 2004)
  2. Double Logistic fitting (TIMESAT method) for phenological parameters
  3. Savitzky-Golay derivative filtering (noise-robust d1/d2)
  4. Pure Python weighted moving average (fallback)

Derived Products:
  - LAI estimation via Beer-Lambert / Myneni (1997)
  - fPAR series (fraction of absorbed photosynthetically active radiation)
  - FVC — Fractional Vegetation Cover (Carlson & Ripley 1997)
  - NPP proxy via Monteith (1977) light-use efficiency
  - CWSI (Crop Water Stress Index) from NDVI-NDWI relationship
  - SOS/EOS/LOS phenological metrics from fitted curve
"""

import math
from typing import List, Dict, Tuple, Optional, Any

try:
    import numpy as np
    from scipy.interpolate import UnivariateSpline
    from scipy.optimize import curve_fit
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    np = None

DOY_WINDOW = 3


def _align_length(values, target_len, fill_value=None):
    """Align a list to a target length by padding or truncating.

    V922.2A: Centralized helper to prevent ndvi_fit/ndvi_fit_unc
    length mismatches across all growth engine outputs.

    Args:
        values: The list to align. If None, returns [fill_value] * target_len.
        target_len: The required length.
        fill_value: Value to use when padding. If None, uses the last
                    element of values (or 0.0 if values is empty).

    Returns:
        List of exactly target_len elements.
    """
    if values is None:
        pad = fill_value if fill_value is not None else 0.0
        return [pad] * target_len
    values = list(values)
    if len(values) == target_len:
        return values
    if len(values) > target_len:
        return values[:target_len]
    # Pad with last value or fill_value
    pad = fill_value if fill_value is not None else (values[-1] if values else 0.0)
    return values + [pad] * (target_len - len(values))


class GrowthCurveEngine:

    def __init__(self, smoothing_factor: float = 0.5):
        self.s = smoothing_factor

    # =====================================================================
    # Main Entry Point
    # =====================================================================

    def fit_growth_curve(
        self,
        dates: List[str],
        ndvi_values: List[float],
        uncertainties: List[float],
        cloud_qa: Optional[List[float]] = None,
        delta_days: Optional[List[float]] = None,
    ) -> Tuple[List[float], Dict[str, List[float]], List[float]]:
        """
        Fits a robust curve to the NDVI time series.

        Returns:
            - modeled_curve: Smoothed NDVI per day
            - derivatives: {velocity, acceleration}
            - uncertainty: Standard error of the fit per day (fit_support_score)
        """
        n = len(ndvi_values)
        if n < 5:
            return ndvi_values, {"velocity": [0.0]*n, "acceleration": [0.0]*n}, uncertainties

        # --- Scientific Mode ---
        if HAS_SCIPY:
            modeled, derivs, unc = self._fit_whittaker(
                ndvi_values, uncertainties, cloud_qa=cloud_qa, delta_days=delta_days
            )
        else:
            # --- Pure Python Fallback ---
            modeled, derivs, unc = self._fit_moving_average_pure(dates, ndvi_values, uncertainties)

        # V922.2A: Enforce length consistency post-condition
        target_len = len(modeled)
        unc = _align_length(unc, target_len)
        if "velocity" in derivs:
            derivs["velocity"] = _align_length(derivs["velocity"], target_len, fill_value=0.0)
        if "acceleration" in derivs:
            derivs["acceleration"] = _align_length(derivs["acceleration"], target_len, fill_value=0.0)

        return modeled, derivs, unc

    # =====================================================================
    # Whittaker-Henderson Smoother with GCV-Adaptive Lambda (Eilers 2003)
    # =====================================================================

    def _fit_whittaker(
        self,
        ndvi_values: List[float],
        uncertainties: List[float],
        d: int = 2,
        n_envelope_passes: int = 3,
        cloud_qa: Optional[List[float]] = None,
        delta_days: Optional[List[float]] = None,
    ) -> Tuple[List[float], Dict[str, List[float]], List[float]]:
        """
        Whittaker smoother with GCV-adaptive lambda and upper-envelope
        bias correction.

        GCV (Generalized Cross-Validation) selects the optimal smoothing
        parameter λ by minimizing:
            GCV(λ) = n × ||y - z||² / (n - tr(H))²
        where H is the hat matrix.

        P1 FIX:
          - Inverse-variance weighting uses w = 1 / (σ² + σ_min²)
          - Upper-envelope downweighting is gated by cloud QA mask when available
            to prevent erasing real, sustained crop stress drops.
        """
        y = np.array(ndvi_values, dtype=np.float64)
        n = len(y)

        # P1 FIX: Inverse-variance weighting w = 1 / (σ² + σ_min²) with σ_min = 0.01
        sigmas = np.array(uncertainties, dtype=np.float64)
        sigma_min = 0.01
        w = 1.0 / (sigmas ** 2 + sigma_min ** 2)
        w = w / max(1e-6, float(w.max()))  # Normalize to [0, 1]

        # GCV-adaptive lambda selection
        lam = self._select_lambda_approximate_gcv(y, w, d)

        try:
            z = self._whittaker_solve(y, w, lam, d)

            # Upper-envelope bias correction (Chen et al. 2004)
            w_new = w.copy()
            for _ in range(n_envelope_passes):
                residuals = y - z
                below = residuals < 0

                if cloud_qa is not None and len(cloud_qa) == n:
                    # Cloud QA is available: downweight below points proportionally to cloud probability
                    qa_arr = np.clip(np.array(cloud_qa, dtype=np.float64), 0.0, 1.0)
                    w_new[below] *= np.maximum(0.1, 1.0 - qa_arr[below])
                    w_new[~below] *= (1.0 + 0.2 * (1.0 - qa_arr[~below]))
                else:
                    # Without explicit cloud mask, apply conservative downweighting (0.7x instead of 0.5x)
                    # to avoid erasing genuine rapid senescence or acute stress
                    w_new[below] *= 0.7
                    w_new[~below] *= 1.1

                w_new = np.clip(w_new, 0.01, 5.0)
                z = self._whittaker_solve(y, w_new, lam, d)

            # Clip to valid NDVI range
            z = np.clip(z, -0.2, 1.0)

            # Savitzky-Golay derivatives (noise-robust, preserves peak timing)
            velocity, acceleration = self._savgol_derivatives(z)

            # Uncertainty of fit (fit support score)
            fit_unc = self._compute_fit_uncertainty(w_new, lam, n)

            return (
                z.tolist(),
                {"velocity": velocity.tolist(), "acceleration": acceleration.tolist()},
                fit_unc.tolist(),
            )

        except Exception as e:
            print(f"⚠️ [GrowthEngine] Whittaker failed: {e}. Falling back to spline.")
            return self._fit_spline_scipy([], ndvi_values, uncertainties)

    def _select_lambda_approximate_gcv(
        self, y: "np.ndarray", w: "np.ndarray", d: int,
        candidates: List[float] = None,
    ) -> float:
        """Select optimal Whittaker smoothing parameter via GCV.

        GCV(λ) = n × RSS / (n - df)²
        where df ≈ trace of hat matrix (approximated for O(n) computational efficiency).

        Note: tr(H) is approximated via df ≈ Σ wᵢ / (wᵢ + 4λ) for d=2.
        Reference: Eilers (2003) Section 3.1
        """
        if candidates is None:
            candidates = [0.1, 1.0, 5.0, 10.0, 50.0, 100.0, 500.0, 1000.0]

        n = len(y)
        best_lam = 10.0
        best_gcv = float('inf')

        for lam in candidates:
            try:
                z = self._whittaker_solve(y, w, lam, d)
                # RSS (weighted)
                rss = float(np.sum(w * (y - z) ** 2))

                # Approximate degrees of freedom
                penalty_approx = lam * 4.0  # Typical for d=2
                df = float(np.sum(w / (w + penalty_approx)))
                df = max(1.0, min(n - 1, df))

                # GCV score
                gcv = n * rss / max(1.0, (n - df)) ** 2

                if gcv < best_gcv:
                    best_gcv = gcv
                    best_lam = lam

            except Exception:
                continue

        return best_lam

    # Backward-compatible alias
    _select_lambda_gcv = _select_lambda_approximate_gcv

    def _whittaker_solve(
        self, y: "np.ndarray", w: "np.ndarray", lam: float, d: int
    ) -> "np.ndarray":
        """Solve the Whittaker system using sparse banded Cholesky.

        Solves: (W + λ D'D) z = W y
        where W = diag(w), D = d-th order difference matrix.
        """
        n = len(y)

        # Build D'D as a banded matrix (2d+1 diagonals)
        from scipy.sparse import diags, eye
        from scipy.sparse.linalg import spsolve

        # Difference operator via convolution coefficients
        coeffs = [1]
        for _ in range(d):
            coeffs = np.convolve(coeffs, [1, -1]).tolist()

        # Build D as sparse matrix
        m = n - d
        diag_data = []
        diag_offsets = []
        for k, c in enumerate(coeffs):
            diag_data.append(np.full(m, float(c)))
            diag_offsets.append(k)

        D = diags(diag_data, diag_offsets, shape=(m, n)).tocsc()
        W = diags(w, 0, shape=(n, n)).tocsc()

        # Solve the system
        A = W + lam * (D.T @ D)
        z = spsolve(A, W @ y)

        return z

    # =====================================================================
    # Savitzky-Golay Derivatives (noise-robust, preserves peak timing)
    # =====================================================================

    def _savgol_derivatives(
        self, z: "np.ndarray", window: int = 7, polyorder: int = 3,
        delta_days: Optional[List[float]] = None,
    ) -> Tuple["np.ndarray", "np.ndarray"]:
        """Compute velocity and acceleration via Savitzky-Golay filter with physical Δt scaling.

        SG derivatives are superior to finite differences because they
        smooth noise while preserving the underlying signal shape, especially
        peak timing and amplitude (Schafer 2011).
        """
        n = len(z)
        # Average time spacing for derivative unit scaling (units/day)
        mean_dt = 1.0
        if delta_days and len(delta_days) > 0:
            valid_dts = [float(d) for d in delta_days if float(d) > 0.0]
            if valid_dts:
                mean_dt = max(0.1, statistics.mean(valid_dts))

        # Adjust window for short series (must be odd and > polyorder)
        win = min(window, n)
        if win % 2 == 0:
            win -= 1
        if win <= polyorder:
            # Fallback to simple gradient
            velocity = np.gradient(z) / mean_dt
            acceleration = np.gradient(velocity) / mean_dt
            return velocity, acceleration

        try:
            from scipy.signal import savgol_filter
            velocity = (savgol_filter(z, window_length=win, polyorder=polyorder, deriv=1)) / mean_dt
            acceleration = (savgol_filter(z, window_length=win, polyorder=polyorder, deriv=2)) / (mean_dt ** 2)
            return velocity, acceleration
        except Exception:
            velocity = np.gradient(z) / mean_dt
            acceleration = np.gradient(velocity) / mean_dt
            return velocity, acceleration

    def _compute_fit_uncertainty(
        self, w: "np.ndarray", lam: float, n: int
    ) -> "np.ndarray":
        """Approximate uncertainty of the Whittaker fit.

        Uses windowed inverse-variance summation as a fast approximation
        of the diagonal of (W + λD'D)⁻¹.
        """
        window_size = 15
        kernel = np.ones(window_size)
        precisions = w ** 2
        sum_precisions = np.convolve(precisions, kernel, mode="same")
        # Add lambda regularization term contribution
        sum_precisions += lam * 0.1
        return 1.0 / np.sqrt(sum_precisions + 1e-6)

    # =====================================================================
    # Double Logistic Fitting (TIMESAT method)
    # =====================================================================

    def fit_double_logistic(
        self, ndvi_values: List[float], dates: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """Fit an asymmetric double logistic curve using physical elapsed time.

        NDVI(t) = base + amp * [ 1/(1+exp(-a1*(t-t1))) - 1/(1+exp(-a2*(t-t2))) ]

        Returns dict with fitted parameters and derived phenological metrics.
        Returns None if fitting fails.
        """
        if not HAS_SCIPY or len(ndvi_values) < 8:
            return None

        y = np.array(ndvi_values, dtype=np.float64)
        n = len(y)

        # Use elapsed physical days if parseable dates are available
        x = None
        if dates and len(dates) == n:
            try:
                from datetime import datetime
                d0 = datetime.strptime(str(dates[0])[:10], "%Y-%m-%d")
                x = np.array([
                    float((datetime.strptime(str(d)[:10], "%Y-%m-%d") - d0).days)
                    for d in dates
                ], dtype=np.float64)
            except Exception:
                x = None

        if x is None:
            x = np.arange(len(y), dtype=np.float64)

        def double_logistic(t, base, amp, a1, t1, a2, t2):
            """Asymmetric double sigmoid."""
            g1 = 1.0 / (1.0 + np.exp(-a1 * (t - t1)))
            g2 = 1.0 / (1.0 + np.exp(-a2 * (t - t2)))
            return base + amp * (g1 - g2)

        # Initial parameter estimates from data
        y_min = float(np.percentile(y, 10))
        y_max = float(np.percentile(y, 90))
        amp_est = y_max - y_min
        peak_idx = int(np.argmax(y))
        peak_x = float(x[peak_idx])
        max_x = float(x[-1]) if len(x) > 0 else float(n)

        p0 = [
            y_min,           # base
            amp_est,         # amplitude
            0.1,             # a1 (greenup steepness)
            peak_x * 0.5,    # t1 (greenup midpoint)
            0.1,             # a2 (senescence steepness)
            peak_x * 1.3,    # t2 (senescence midpoint)
        ]

        bounds = (
            [0.0, 0.01, 0.001, 0, 0.001, 0],
            [0.5, 1.0,  2.0,   max_x * 1.5 + 1.0, 2.0, max_x * 2.0 + 1.0],
        )

        try:
            popt, _ = curve_fit(
                double_logistic, x, y, p0=p0, bounds=bounds,
                maxfev=5000, method="trf",
            )
            base, amp, a1, t1, a2, t2 = popt

            # True argmax of fitted curve on sampled points
            fitted_vals = double_logistic(x, *popt)
            pos_idx = float(np.argmax(fitted_vals))

            # Derived phenological parameters
            sos_x = t1 - np.log(4) / a1   # ~20% rise
            eos_x = t2 + np.log(4) / a2   # ~80% decline

            # Convert x back to closest sample indices
            sos_idx = int(np.argmin(np.abs(x - sos_x)))
            eos_idx = int(np.argmin(np.abs(x - eos_x)))

            return {
                "base": float(base),
                "amplitude": float(amp),
                "greenup_rate": float(a1),
                "senescence_rate": float(a2),
                "sos_idx": max(0, float(sos_idx)),
                "eos_idx": min(n - 1, float(eos_idx)),
                "pos_idx": float(pos_idx),
                "los": max(0, float(eos_idx - sos_idx)),
                "fitted_curve": fitted_vals.tolist(),
            }

        except Exception:
            return None

    # =====================================================================
    # Scipy Spline (fallback for Whittaker)
    # =====================================================================

    def _fit_spline_scipy(self, dates, ndvi_values, uncertainties):
        """Robust spline fallback when Whittaker fails."""
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

            modeled_y = np.clip(modeled_y, -0.2, 1.0)

            # Savitzky-Golay derivatives
            velocity, acceleration = self._savgol_derivatives(modeled_y)

            # Fit uncertainty
            window_size = 15
            kernel = np.ones(window_size)
            precisions = w_robust ** 2
            sum_precisions = np.convolve(precisions, kernel, mode="same")
            fit_unc_arr = 1.0 / np.sqrt(sum_precisions + 1e-6)

            result_curve = modeled_y.tolist()
            result_deriv = {"velocity": velocity.tolist(), "acceleration": acceleration.tolist()}
            result_unc = _align_length(fit_unc_arr.tolist(), len(result_curve))

            return (result_curve, result_deriv, result_unc)

        except Exception as e:
            print(f"⚠️ [GrowthEngine] Spline failed: {e}. Fallback to linear.")
            return ndvi_values, {"velocity": [0.0]*len(y), "acceleration": [0.0]*len(y)}, uncertainties

    # =====================================================================
    # Pure Python Fallback
    # =====================================================================

    def _fit_moving_average_pure(self, dates, ndvi_values, uncertainties):
        """Pure Python Weighted Moving Average with Outlier Rejection."""
        print("⚠️ [GrowthEngine] Running in Pure Python Fallback Mode")
        n = len(ndvi_values)

        # Dynamic Window Strategy
        window = max(7, min(30, int(n * 0.1)))
        half = window // 2

        w_current = [1.0/(u+0.01) for u in uncertainties]

        def smooth(weights):
            res = []
            unc_out = []
            for i in range(n):
                start = max(0, i - half)
                end = min(n, i + half + 1)
                chunk = ndvi_values[start:end]
                w_chunk = weights[start:end]

                num = sum(c*w for c, w in zip(chunk, w_chunk))
                den = sum(w_chunk)
                val = num / den if den > 0 else 0.0
                res.append(max(-0.2, min(1.0, val)))

                sum_precision = sum(w*w for w in w_chunk)
                sigma_fit = 1.0 / math.sqrt(sum_precision + 1e-9)
                unc_out.append(sigma_fit)

            return res, unc_out

        # Pass 1
        pass1, _ = smooth(w_current)

        # Re-weighting (Robustness)
        w_robust = list(w_current)
        residuals = [abs(o - m) for o, m in zip(ndvi_values, pass1)]

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
                w_robust[i] *= 0.1
                outlier_count += 1

        outlier_frac = outlier_count / n if n > 0 else 0.0
        if outlier_frac > 0.3:
            print(f"⚠️ [GrowthEngine] High Outlier Fraction: {outlier_frac:.2%}. Model quality degraded.")

        # Pass 2
        final_curve, final_unc = smooth(w_robust)

        # Numerical derivatives
        velocity = [0.0] * n
        for i in range(1, n):
            velocity[i] = final_curve[i] - final_curve[i-1]

        acceleration = [0.0] * n
        for i in range(1, n):
            acceleration[i] = velocity[i] - velocity[i-1]

        return final_curve, {"velocity": velocity, "acceleration": acceleration}, final_unc

    # =====================================================================
    # Integrals (Trapezoidal)
    # =====================================================================

    def compute_integrals(
        self,
        curve: List[float],
        delta_days: Optional[List[float]] = None,
    ) -> Dict[str, float]:
        """Computes AUC (trapezoidal), peak, and small integral.

        Args:
            curve: Smoothed VI time series.
            delta_days: Optional time increments Δt between points (defaults to Δt=1.0).
        """
        if not curve:
            return {"auc_season": 0.0, "auc_small": 0.0, "peak_value": 0.0, "peak_day_index": 0}

        if HAS_SCIPY:
            arr = np.array(curve)
            peak_val = float(np.max(arr))
            peak_idx = int(np.argmax(arr))
            base = float(np.percentile(arr, 10))

            if delta_days is not None and len(delta_days) == len(arr) - 1:
                dt = np.array(delta_days, dtype=np.float64)
                auc = float(np.sum(0.5 * (np.maximum(arr[:-1], 0) + np.maximum(arr[1:], 0)) * dt))
                auc_small = float(np.sum(0.5 * (np.maximum(arr[:-1] - base, 0) + np.maximum(arr[1:] - base, 0)) * dt))
            else:
                _trapz = getattr(np, 'trapezoid', getattr(np, 'trapz', None))
                auc = float(_trapz(np.maximum(arr, 0)))
                auc_small = float(_trapz(np.maximum(arr - base, 0)))

            return {
                "auc_season": auc,
                "auc_small": auc_small,
                "peak_value": peak_val,
                "peak_day_index": peak_idx,
            }
        else:
            # Pure Python trapezoidal rule
            auc = 0.0
            auc_small = 0.0
            base = sorted(curve)[max(0, int(len(curve) * 0.10))]

            for i in range(1, len(curve)):
                dt = delta_days[i-1] if (delta_days and i-1 < len(delta_days)) else 1.0
                v0 = max(0.0, curve[i - 1])
                v1 = max(0.0, curve[i])
                auc += 0.5 * (v0 + v1) * dt
                auc_small += 0.5 * (max(0.0, v0 - base) + max(0.0, v1 - base)) * dt

            peak_val = max(curve)
            peak_idx = curve.index(peak_val)
            return {
                "auc_season": auc,
                "auc_small": auc_small,
                "peak_value": peak_val,
                "peak_day_index": peak_idx,
            }

    # =====================================================================
    # LAI Estimation (Myneni et al. 1997)
    # =====================================================================

    @staticmethod
    def estimate_lai(
        ndvi_series: List[float],
        k: float = 0.5,
        lai_max: float = 6.0,
    ) -> List[float]:
        """Estimate Leaf Area Index from NDVI using Beer-Lambert law.

        LAI = -ln(1 - fPAR) / k
        where fPAR ≈ 1.25 * NDVI - 0.025  (Myneni et al. 1997)
        and k = light extinction coefficient (~0.5 for erectophile canopies).

        Args:
            ndvi_series: Smoothed NDVI values.
            k: Extinction coefficient (0.4-0.6 typical).
            lai_max: Peak healthy canopy LAI prior.

        Returns:
            LAI estimates per timestep, clamped to [0, lai_max].
        """
        lai = []
        k_safe = max(0.2, min(1.5, k))
        for ndvi in ndvi_series:
            fpar = max(0.01, min(0.95, 1.25 * ndvi - 0.025))
            if fpar >= 0.95:
                lai_val = lai_max  # Saturated canopy
            else:
                lai_val = -math.log(1.0 - fpar) / k_safe
            lai.append(min(lai_max, max(0.0, round(lai_val, 2))))
        return lai

    # =====================================================================
    # fPAR Series (Fraction of Absorbed PAR)
    # =====================================================================

    @staticmethod
    def compute_fpar(ndvi_series: List[float]) -> List[float]:
        """Compute fPAR from NDVI using Myneni (1997) linear relationship.

        fPAR ≈ 1.25 * NDVI - 0.025, clamped to [0, 0.95].
        """
        return [max(0.0, min(0.95, 1.25 * ndvi - 0.025)) for ndvi in ndvi_series]

    # =====================================================================
    # FVC — Fractional Vegetation Cover (Carlson & Ripley 1997)
    # =====================================================================

    @staticmethod
    def compute_fvc(
        ndvi_series: List[float],
        ndvi_soil: Optional[float] = None,
        ndvi_veg: Optional[float] = None,
    ) -> List[float]:
        """Compute fractional vegetation cover with dynamic endpoints.

        FVC = ((NDVI - NDVI_soil) / (NDVI_veg - NDVI_soil))²

        Reference: Carlson & Ripley (1997), Gutman & Ignatov (1998)

        P1 FIX:
          - Endpoints can be dynamically estimated from data distribution
            (5th percentile for soil, 95th percentile for dense vegetation)
            rather than static poorly-transferable constants.

        Args:
            ndvi_series: Smoothed NDVI values.
            ndvi_soil: NDVI of bare soil (default: dynamic 5th percentile, ~0.10).
            ndvi_veg: NDVI of fully vegetated pixel (default: dynamic 95th percentile, ~0.85).

        Returns:
            FVC per timestep, clamped to [0, 1].
        """
        if not ndvi_series:
            return []

        if ndvi_soil is None:
            # Dynamic bare soil baseline from lower envelope
            if HAS_SCIPY:
                ndvi_soil = float(np.clip(np.percentile(ndvi_series, 5), 0.05, 0.20))
            else:
                sorted_vals = sorted(ndvi_series)
                ndvi_soil = max(0.05, min(0.20, sorted_vals[max(0, int(len(sorted_vals) * 0.05))]))

        if ndvi_veg is None:
            # Dynamic full canopy asymptote from upper envelope
            if HAS_SCIPY:
                ndvi_veg = float(np.clip(np.percentile(ndvi_series, 95), 0.65, 0.92))
            else:
                sorted_vals = sorted(ndvi_series)
                ndvi_veg = max(0.65, min(0.92, sorted_vals[min(len(sorted_vals) - 1, int(len(sorted_vals) * 0.95))]))

        rng = ndvi_veg - ndvi_soil
        if rng < 0.05:
            rng = 0.05

        fvc = []
        for ndvi in ndvi_series:
            ratio = (ndvi - ndvi_soil) / rng
            ratio = max(0.0, min(1.0, ratio))
            fvc.append(round(ratio ** 2, 4))  # Squared per Carlson & Ripley
        return fvc

    # =====================================================================
    # NPP Proxy (Monteith 1977 Light-Use Efficiency)
    # =====================================================================

    @staticmethod
    def compute_npp_proxy(
        fpar_series: List[float],
        latitude: Optional[float] = None,
        start_doy: int = 1,
        rs_observed_series: Optional[List[Optional[float]]] = None,
    ) -> List[float]:
        """Estimate Net Primary Productivity proxy.

        NPP ≈ fPAR × PAR × LUE

        P0 FIX: Replaced naive constant-irradiance assumption with FAO-56
        astronomical extraterrestrial radiation (Ra) formulation:
        Ra = (24*60/π) * Gsc * dr * [ωs*sin(φ)*sin(δ) + cos(φ)*cos(δ)*sin(ωs)]

        Args:
            fpar_series: fPAR values per timestep.
            latitude: Field latitude in degrees (e.g. 36.0 for Algeria).
            start_doy: Starting day-of-year for the time series.
            rs_observed_series: Optional measured surface solar radiation (MJ/m²/day).

        Returns:
            NPP proxy in gC/m²/day per timestep.
        """
        if latitude is None:
            return []
        LUE = 1.5  # Light Use Efficiency (gC/MJ) — generic C3 crops
        GSC = 0.0820  # Solar constant (MJ/m²/min)
        lat_rad = math.radians(latitude)
        npp = []

        for i, fpar in enumerate(fpar_series):
            doy = (start_doy + i - 1) % 365 + 1

            # Check if observed Rs is provided
            if rs_observed_series and i < len(rs_observed_series) and rs_observed_series[i] is not None:
                par = 0.48 * rs_observed_series[i]
            else:
                # FAO-56 Astronomical Solar Radiation Model
                # Inverse relative distance Earth-Sun
                dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * doy / 365.0)
                # Solar declination (radians)
                decl = 0.409 * math.sin(2.0 * math.pi * doy / 365.0 - 1.39)
                # Sunset hour angle (radians)
                tan_prod = -math.tan(lat_rad) * math.tan(decl)
                tan_prod = max(-1.0, min(1.0, tan_prod))
                omega_s = math.acos(tan_prod)

                # Extraterrestrial radiation Ra (MJ/m²/day)
                ra = (24.0 * 60.0 / math.pi) * GSC * dr * (
                    omega_s * math.sin(lat_rad) * math.sin(decl) +
                    math.cos(lat_rad) * math.cos(decl) * math.sin(omega_s)
                )
                ra = max(0.0, ra)
                # Surface solar radiation under clear-sky (Rs ≈ 0.75 Ra), PAR ≈ 48% of Rs
                par = 0.75 * ra * 0.48

            # NPP = fPAR × PAR × LUE
            npp_val = fpar * par * LUE
            npp.append(max(0.0, round(npp_val, 3)))

        return npp

    # =====================================================================
    # SCWA — Spectral Canopy Water Anomaly / Proxy (Jackson / Gao 1996)
    # =====================================================================

    @staticmethod
    def compute_spectral_canopy_water_anomaly(
        ndwi_series: Optional[List[Optional[float]]],
        ndvi_series: List[float],
    ) -> List[Optional[float]]:
        """Compute Spectral Canopy Water Anomaly (SCWA) / Water Stress Proxy.

        SCWA = 1 - (NDWI - NDWI_dry) / (NDWI_wet - NDWI_dry)
        where NDWI_dry = -0.25 and NDWI_wet = 0.35.

        Missingness Rule:
          - When NDWI is None, returns None (UNKNOWN).
          - Missing canopy water evidence is NEVER converted into 0.0 (water adequacy).
        """
        n = len(ndvi_series)
        if not ndwi_series:
            return [None] * n

        NDWI_DRY_REF = -0.25
        NDWI_WET_REF = 0.35
        ndwi_range = NDWI_WET_REF - NDWI_DRY_REF

        scwa = []
        for i in range(n):
            ndwi_val = ndwi_series[i] if i < len(ndwi_series) else None
            if ndwi_val is not None and not math.isnan(ndwi_val):
                normalized = (ndwi_val - NDWI_DRY_REF) / ndwi_range
                normalized = max(0.0, min(1.0, normalized))
                scwa.append(round(1.0 - normalized, 3))
            else:
                scwa.append(None)
        return scwa

    # Backward compatibility alias
    compute_cwsi = compute_spectral_canopy_water_anomaly

    # =====================================================================
    # FAO-56 ETc Water Balance
    # =====================================================================

    @staticmethod
    def compute_water_balance(
        et0_series: List[Optional[float]],
        rainfall_series: List[float],
        kc_series: List[float],
    ) -> Tuple[List[float], List[float]]:
        """Compute crop water demand and deficit using FAO-56.

        ETc = Kc × ET0 (crop evapotranspiration demand)
        ET_deficit = ETc - rain (positive = water deficit)

        Args:
            et0_series: Reference ET (mm/day) from weather data.
            rainfall_series: Daily rainfall (mm).
            kc_series: Crop coefficient per timestep (stage-dependent).

        Returns:
            (et_actual, et_deficit) lists per timestep.
        """
        n = len(et0_series)
        et_actual: List[Optional[float]] = []
        et_deficit: List[Optional[float]] = []

        for i in range(n):
            if et0_series[i] is None:
                et_actual.append(None)
                et_deficit.append(None)
                continue
            et0 = et0_series[i]
            kc = kc_series[i] if i < len(kc_series) and kc_series[i] is not None else 1.0
            rain = rainfall_series[i] if i < len(rainfall_series) and rainfall_series[i] is not None else 0.0

            etc = kc * et0  # Crop water demand
            # Simple water balance: deficit = demand - supply
            deficit = max(0.0, etc - rain)
            # Actual ET is minimum of demand and available water
            actual = min(etc, rain + 2.0)  # +2mm for soil moisture buffer

            et_actual.append(round(actual, 2))
            et_deficit.append(round(deficit, 2))

        return et_actual, et_deficit

    # =====================================================================
    # SOS/EOS/LOS from Fitted Curve
    # =====================================================================

    @staticmethod
    def extract_season_dates(
        ndvi_fit: List[float],
        dates: List[str],
        threshold_frac: float = 0.2,
    ) -> Dict[str, Any]:
        """Extract Start/End/Length of Season from the fitted NDVI curve.

        Uses the amplitude threshold method (TIMESAT convention).
        """
        if not ndvi_fit or not dates or len(ndvi_fit) != len(dates):
            return {"sos_date": "", "eos_date": "", "los_days": 0, "peak_date": "", "peak_ndvi": 0.0}

        n = len(ndvi_fit)
        base = min(ndvi_fit)
        peak = max(ndvi_fit)
        peak_idx = ndvi_fit.index(peak)
        amp = peak - base
        thresh = base + threshold_frac * amp

        # SOS: first crossing above threshold (before peak)
        sos_idx = 0
        for i in range(peak_idx):
            if ndvi_fit[i] >= thresh:
                sos_idx = i
                break

        # EOS: last crossing below threshold (after peak)
        eos_idx = n - 1
        for i in range(n - 1, peak_idx, -1):
            if ndvi_fit[i] >= thresh:
                eos_idx = i
                break

        try:
            from datetime import datetime
            sos_stamp = datetime.strptime(str(dates[sos_idx])[:10], "%Y-%m-%d")
            eos_stamp = datetime.strptime(str(dates[eos_idx])[:10], "%Y-%m-%d")
            los = max(0, (eos_stamp - sos_stamp).days)
        except (TypeError, ValueError, IndexError):
            # Undated inputs cannot support a scientific day count.
            los = 0

        return {
            "sos_date": dates[sos_idx] if sos_idx < len(dates) else "",
            "eos_date": dates[eos_idx] if eos_idx < len(dates) else "",
            "los_days": max(0, los),
            "peak_date": dates[peak_idx] if peak_idx < len(dates) else "",
            "peak_ndvi": float(peak),
        }

    # =====================================================================
    # v3.2: CASA NPP Model (Potter et al. 1993)
    # =====================================================================

    @classmethod
    def compute_npp_casa_detailed(
        cls,
        fpar_series: List[float],
        latitude: Optional[float] = None,
        start_doy: int = 1,
        temperature_series: Optional[List[float]] = None,
        cwsi_series: Optional[List[Optional[float]]] = None,
        t_opt: float = 25.0,
        t_min: float = 5.0,
        t_max: float = 45.0,
        epsilon_max: float = 0.604,
        rs_observed_series: Optional[List[Optional[float]]] = None,
    ) -> Dict[str, Any]:
        """CASA-model Net Primary Productivity with detailed light-temperature and water components.

        NPP*_LT = fPAR × PAR × ε_max × T_scalar
        NPP_water_adjusted = NPP*_LT × W_scalar
        """
        if latitude is None:
            return {
                "npp_light_temperature": [],
                "npp_spectral_water_adjusted": [],
                "water_constraint_applied": False,
                "water_constraint_source": "NONE",
                "radiation_source": "NONE",
            }
        GSC = 0.0820  # Solar constant (MJ/m²/min)
        lat_rad = math.radians(latitude)
        npp_lt = []
        npp_water = []
        water_applied = False
        rad_source = "MEASURED_SURFACE_SOLAR" if rs_observed_series and any(r is not None for r in rs_observed_series) else "FAO56_CLEAR_SKY_EXTRATERRESTRIAL"

        for i, fpar in enumerate(fpar_series):
            doy = (start_doy + i - 1) % 365 + 1

            if rs_observed_series and i < len(rs_observed_series) and rs_observed_series[i] is not None:
                par = 0.48 * rs_observed_series[i]
            else:
                # FAO-56 Ra formulation
                dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * doy / 365.0)
                decl = 0.409 * math.sin(2.0 * math.pi * doy / 365.0 - 1.39)
                tan_prod = -math.tan(lat_rad) * math.tan(decl)
                tan_prod = max(-1.0, min(1.0, tan_prod))
                omega_s = math.acos(tan_prod)

                ra = (24.0 * 60.0 / math.pi) * GSC * dr * (
                    omega_s * math.sin(lat_rad) * math.sin(decl) +
                    math.cos(lat_rad) * math.cos(decl) * math.sin(omega_s)
                )
                ra = max(0.0, ra)
                par = 0.75 * ra * 0.48

            # T_scalar (photosynthetic temperature acclimation)
            t_scalar = 1.0
            if temperature_series and i < len(temperature_series):
                t = temperature_series[i]
                if t is not None:
                    if t <= t_min or t >= t_max:
                        t_scalar = 0.0
                    else:
                        t_up = (t - t_min) / max(0.1, t_opt - t_min)
                        t_down = (t_max - t) / max(0.1, t_max - t_opt)
                        t_scalar = max(0.0, min(1.0, min(t_up, t_down)))

            # Light-temperature potential NPP*_LT
            npp_lt_val = fpar * par * epsilon_max * t_scalar
            npp_lt.append(max(0.0, round(npp_lt_val, 3)))

            # W_scalar (when water proxy is missing, W_scalar = 1.0)
            w_scalar = 1.0
            if cwsi_series and i < len(cwsi_series) and cwsi_series[i] is not None:
                cwsi = float(cwsi_series[i])
                w_scalar = 0.5 + 0.5 * (1.0 - cwsi)
                water_applied = True

            npp_water_val = npp_lt_val * w_scalar
            npp_water.append(max(0.0, round(npp_water_val, 3)))

        return {
            "npp_light_temperature": npp_lt,
            "npp_spectral_water_adjusted": npp_water,
            "water_constraint_applied": water_applied,
            "water_constraint_source": "SPECTRAL_PROXY" if water_applied else "NONE",
            "radiation_source": rad_source,
        }

    @classmethod
    def compute_npp_casa(
        cls,
        fpar_series: List[float],
        latitude: Optional[float] = None,
        start_doy: int = 1,
        temperature_series: Optional[List[float]] = None,
        cwsi_series: Optional[List[Optional[float]]] = None,
        t_opt: float = 25.0,
        t_min: float = 5.0,
        t_max: float = 45.0,
        epsilon_max: float = 0.604,
        rs_observed_series: Optional[List[Optional[float]]] = None,
    ) -> List[float]:
        """Backward-compatible wrapper returning water-adjusted NPP series."""
        res = cls.compute_npp_casa_detailed(
            fpar_series=fpar_series,
            latitude=latitude,
            start_doy=start_doy,
            temperature_series=temperature_series,
            cwsi_series=cwsi_series,
            t_opt=t_opt,
            t_min=t_min,
            t_max=t_max,
            epsilon_max=epsilon_max,
            rs_observed_series=rs_observed_series,
        )
        return res.get("npp_spectral_water_adjusted", [])

    # =====================================================================
    # v3.2: Water Use Efficiency (Steduto et al. 2009 — AquaCrop)
    # =====================================================================

    @staticmethod
    def compute_water_use_efficiency(
        biomass_series: List[float],
        et_actual_series: List[float],
        window: int = 14,
    ) -> Dict[str, float]:
        """Compute Water Use Efficiency and Carbon Water Productivity.

        WUE = ΔBiomass / ETa (gC/m²/mm)
        CWP = Total Carbon Biomass / ET_total (kgC/m³)

        Uses trailing window to compute recent WUE.
        """
        if not biomass_series or not et_actual_series:
            return {"wue": 0.0, "carbon_water_productivity": 0.0, "crop_water_productivity": 0.0, "et_total": 0.0}

        n = min(len(biomass_series), len(et_actual_series))
        w = min(window, n)

        # Recent biomass change
        recent_bio = biomass_series[-w:]
        recent_et = [e for e in et_actual_series[-w:] if e is not None]

        delta_biomass = max(0.0, recent_bio[-1] - recent_bio[0]) if len(recent_bio) >= 2 else 0.0
        et_sum = sum(recent_et)

        wue = delta_biomass / max(0.01, et_sum) if et_sum > 0 else 0.0

        # Total season ET and Carbon Water Productivity (kgC/m3)
        valid_season_et = [e for e in et_actual_series[:n] if e is not None]
        et_total = sum(valid_season_et)
        total_biomass = max(biomass_series) if biomass_series else 0.0
        cwp = (total_biomass / max(0.01, et_total)) if et_total > 0 else 0.0

        return {
            "wue": round(wue, 4),
            "carbon_water_productivity": round(cwp, 3),
            "crop_water_productivity": round(cwp, 3),  # Alias for backward compatibility
            "et_total": round(et_total, 2),
        }

    # =====================================================================
    # v3.2: Adaptive Ensemble Smoother
    # =====================================================================

    def _fit_ensemble(
        self,
        ndvi_values: List[float],
        uncertainties: List[float],
        dates: Optional[List[str]] = None,
        cloud_qa: Optional[List[float]] = None,
        delta_days: Optional[List[float]] = None,
    ) -> Tuple[List[float], Dict[str, List[float]], List[float]]:
        """Blend Whittaker + Savitzky-Golay with data-quality-adaptive weights.

        Passes cloud_qa and delta_days to Whittaker and SG derivatives.
        """
        if not HAS_SCIPY or len(ndvi_values) < 10:
            return self._fit_whittaker(
                ndvi_values, uncertainties, cloud_qa=cloud_qa, delta_days=delta_days
            )

        # Run Whittaker with QA gating & delta_days
        whit_curve, whit_deriv, whit_unc = self._fit_whittaker(
            ndvi_values, uncertainties, cloud_qa=cloud_qa, delta_days=delta_days
        )

        # Run SG smoother
        try:
            from scipy.signal import savgol_filter
            window = min(11, len(ndvi_values) // 2 * 2 + 1)
            if window < 5:
                return whit_curve, whit_deriv, whit_unc
            sg_curve = list(savgol_filter(ndvi_values, window, 3))
        except Exception:
            return whit_curve, whit_deriv, whit_unc

        # Compute per-point residuals against raw
        n = len(ndvi_values)
        ensemble = [0.0] * n
        for t in range(n):
            res_w = (ndvi_values[t] - whit_curve[t]) ** 2
            res_s = (ndvi_values[t] - sg_curve[t]) ** 2

            # Inverse residual weights (add epsilon to avoid division by zero)
            w_w = 1.0 / (res_w + 0.001)
            w_s = 1.0 / (res_s + 0.001)
            total_w = w_w + w_s

            ensemble[t] = (w_w * whit_curve[t] + w_s * sg_curve[t]) / total_w

        # Recompute derivatives on ensemble using delta_days
        velocity, acceleration = self._savgol_derivatives(ensemble, delta_days=delta_days)

        deriv = {
            "velocity": list(velocity) if hasattr(velocity, "tolist") else list(velocity),
            "acceleration": list(acceleration) if hasattr(acceleration, "tolist") else list(acceleration),
        }

        ens_unc = [
            round((whit_unc[i] + abs(whit_curve[i] - sg_curve[i])) / 2, 4)
            for i in range(n)
        ]

        return ensemble, deriv, ens_unc


# =========================================================================
# Radiative Transfer Model (RTM / PROSAIL) Hybrid Inversion Interface
# =========================================================================

class RadiativeTransferModelStub:
    """Architectural interface for Canopy Radiative Transfer Model (RTM).

    Designed for lookup table (LUT) or neural network hybrid inversion of
    PROSAIL (PROSPECT-D + 4SAIL) to estimate biophysical variables:
      - LAI (Leaf Area Index, m²/m²)
      - Cab (Leaf chlorophyll content, μg/cm²)
      - Cw (Leaf water content / EWT, g/cm²)
      - FCOVER / FVC (Fractional Vegetation Cover)

    Reference: Jacquemoud et al. (2009), Verrelst et al. (2015).
    """

    @staticmethod
    def invert_prosail_lut(
        reflectance_bands: Dict[str, float],
        view_angles: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Invert canopy surface reflectance to biophysical quantities.

        Fallback proxy mode when neural network LUT weights are absent.
        """
        # Multi-spectral empirical inversion fallback
        b8 = reflectance_bands.get("B08", reflectance_bands.get("nir", 0.40))
        b4 = reflectance_bands.get("B04", reflectance_bands.get("red", 0.08))
        ndvi = (b8 - b4) / max(1e-4, b8 + b4)
        
        lai_est = GrowthCurveEngine.estimate_lai([ndvi])[0]
        fvc_est = GrowthCurveEngine.compute_fvc([ndvi])[0]
        
        return {
            "lai": lai_est,
            "fvc": fvc_est,
            "cab_proxy": round(min(80.0, max(10.0, ndvi * 65.0)), 2),
            "retrieval_method": "empirical_proxy_fallback",
        }

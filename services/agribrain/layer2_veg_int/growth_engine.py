
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
            modeled, derivs, unc = self._fit_whittaker(ndvi_values, uncertainties)
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
    ) -> Tuple[List[float], Dict[str, List[float]], List[float]]:
        """
        Whittaker smoother with GCV-adaptive lambda and upper-envelope
        bias correction.

        GCV (Generalized Cross-Validation) selects the optimal smoothing
        parameter λ by minimizing:
            GCV(λ) = n × ||y - z||² / (n - tr(H))²
        where H is the hat matrix.

        Upper-envelope correction (Chen et al. 2004): iteratively increases
        weights for points above the fit (cloud-free) and decreases weights
        for points below (cloud-contaminated).
        """
        y = np.array(ndvi_values, dtype=np.float64)
        n = len(y)

        # Weights from uncertainty (inverse variance)
        w = 1.0 / (np.array(uncertainties, dtype=np.float64) + 0.01)
        w = w / w.max()  # Normalize to [0, 1]

        # GCV-adaptive lambda selection
        lam = self._select_lambda_gcv(y, w, d)

        try:
            z = self._whittaker_solve(y, w, lam, d)

            # Upper-envelope bias correction (Chen et al. 2004)
            w_new = w.copy()
            for _ in range(n_envelope_passes):
                residuals = y - z
                # Points above the fit are more likely cloud-free
                below = residuals < 0
                # Decrease weight of below-fit points (likely cloud-contaminated)
                w_new[below] *= 0.5
                # Increase weight of above-fit points (likely true signal)
                w_new[~below] *= 1.2
                w_new = np.clip(w_new, 0.01, 5.0)
                z = self._whittaker_solve(y, w_new, lam, d)

            # Clip to valid NDVI range
            z = np.clip(z, -0.2, 1.0)

            # Savitzky-Golay derivatives (noise-robust, preserves peak timing)
            velocity, acceleration = self._savgol_derivatives(z)

            # Uncertainty of fit
            fit_unc = self._compute_fit_uncertainty(w_new, lam, n)

            return (
                z.tolist(),
                {"velocity": velocity.tolist(), "acceleration": acceleration.tolist()},
                fit_unc.tolist(),
            )

        except Exception as e:
            print(f"⚠️ [GrowthEngine] Whittaker failed: {e}. Falling back to spline.")
            return self._fit_spline_scipy([], ndvi_values, uncertainties)

    def _select_lambda_gcv(
        self, y: "np.ndarray", w: "np.ndarray", d: int,
        candidates: List[float] = None,
    ) -> float:
        """Select optimal Whittaker smoothing parameter via GCV.

        GCV(λ) = n × RSS / (n - df)²
        where df ≈ trace of hat matrix (approximated for efficiency).

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

                # Approximate degrees of freedom:
                # df ≈ trace(H) ≈ Σ wᵢ / (wᵢ + λ * penalty_i)
                # For simplicity, use uniform penalty approximation
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
    ) -> Tuple["np.ndarray", "np.ndarray"]:
        """Compute velocity and acceleration via Savitzky-Golay filter.

        SG derivatives are superior to finite differences because they
        smooth noise while preserving the underlying signal shape, especially
        peak timing and amplitude (Schafer 2011).

        Falls back to np.gradient if the series is too short for SG.
        """
        n = len(z)

        # Adjust window for short series (must be odd and > polyorder)
        win = min(window, n)
        if win % 2 == 0:
            win -= 1
        if win <= polyorder:
            # Fallback to simple gradient
            velocity = np.gradient(z)
            acceleration = np.gradient(velocity)
            return velocity, acceleration

        try:
            from scipy.signal import savgol_filter
            velocity = savgol_filter(z, window_length=win, polyorder=polyorder, deriv=1)
            acceleration = savgol_filter(z, window_length=win, polyorder=polyorder, deriv=2)
            return velocity, acceleration
        except Exception:
            velocity = np.gradient(z)
            acceleration = np.gradient(velocity)
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
        self,
        ndvi_values: List[float],
        dates: Optional[List[str]] = None,
    ) -> Optional[Dict[str, float]]:
        """
        Fit an asymmetric double logistic function to the NDVI time series.

        NDVI(t) = base + amp * [ 1/(1+exp(-a1*(t-t1))) - 1/(1+exp(-a2*(t-t2))) ]

        Returns dict with fitted parameters and derived phenological metrics.
        Returns None if fitting fails.
        """
        if not HAS_SCIPY or len(ndvi_values) < 8:
            return None

        y = np.array(ndvi_values, dtype=np.float64)
        x = np.arange(len(y), dtype=np.float64)
        n = len(y)

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

        p0 = [
            y_min,           # base
            amp_est,         # amplitude
            0.3,             # a1 (greenup steepness)
            peak_idx * 0.4,  # t1 (greenup midpoint)
            0.3,             # a2 (senescence steepness)
            peak_idx * 1.5,  # t2 (senescence midpoint)
        ]

        bounds = (
            [0.0, 0.01, 0.01, 0, 0.01, 0],
            [0.5, 1.0,  2.0,  n, 2.0,  n * 1.5],
        )

        try:
            popt, _ = curve_fit(
                double_logistic, x, y, p0=p0, bounds=bounds,
                maxfev=5000, method="trf",
            )
            base, amp, a1, t1, a2, t2 = popt

            # Derived phenological parameters
            sos_idx = t1 - np.log(4) / a1   # ~20% rise
            eos_idx = t2 + np.log(4) / a2   # ~80% decline
            pos_idx = (t1 + t2) / 2          # Peak of season

            return {
                "base": float(base),
                "amplitude": float(amp),
                "greenup_rate": float(a1),
                "senescence_rate": float(a2),
                "sos_idx": max(0, float(sos_idx)),
                "eos_idx": min(n - 1, float(eos_idx)),
                "pos_idx": float(pos_idx),
                "los": max(0, float(eos_idx - sos_idx)),
                "fitted_curve": double_logistic(x, *popt).tolist(),
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

    def compute_integrals(self, curve: List[float]) -> Dict[str, float]:
        """Computes AUC (trapezoidal), peak, and small integral."""
        if not curve:
            return {"auc_season": 0.0, "auc_small": 0.0, "peak_value": 0.0, "peak_day_index": 0}

        if HAS_SCIPY:
            arr = np.array(curve)
            _trapz = getattr(np, 'trapezoid', getattr(np, 'trapz', None))
            auc = float(_trapz(np.maximum(arr, 0)))
            peak_val = float(np.max(arr))
            peak_idx = int(np.argmax(arr))

            # Small integral: area above base NDVI (10th percentile)
            base = float(np.percentile(arr, 10))
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
            for i in range(1, len(curve)):
                v0 = max(0.0, curve[i - 1])
                v1 = max(0.0, curve[i])
                auc += (v0 + v1) / 2.0

            peak_val = max(curve)
            peak_idx = curve.index(peak_val)
            return {
                "auc_season": auc,
                "auc_small": auc * 0.8,  # Approximate
                "peak_value": peak_val,
                "peak_day_index": peak_idx,
            }

    # =====================================================================
    # LAI Estimation (Myneni et al. 1997)
    # =====================================================================

    @staticmethod
    def estimate_lai(ndvi_series: List[float], k: float = 0.5) -> List[float]:
        """Estimate Leaf Area Index from NDVI using Beer-Lambert law.

        LAI = -ln(1 - fPAR) / k
        where fPAR ≈ 1.25 * NDVI - 0.025  (Myneni et al. 1997)
        and k = light extinction coefficient (~0.5 for erectophile canopies).

        Args:
            ndvi_series: Smoothed NDVI values.
            k: Extinction coefficient (0.4-0.6 typical).

        Returns:
            LAI estimates per timestep, clamped to [0, 8].
        """
        lai = []
        for ndvi in ndvi_series:
            fpar = max(0.0, min(0.95, 1.25 * ndvi - 0.025))
            if fpar >= 0.95:
                lai_val = 6.0  # Saturated canopy
            elif fpar <= 0.0:
                lai_val = 0.0
            else:
                lai_val = -math.log(1.0 - fpar) / k
            lai.append(min(8.0, max(0.0, lai_val)))
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
        ndvi_soil: float = 0.10,
        ndvi_veg: float = 0.85,
    ) -> List[float]:
        """Compute fractional vegetation cover.

        FVC = ((NDVI - NDVI_soil) / (NDVI_veg - NDVI_soil))²

        Reference: Carlson & Ripley (1997), Gutman & Ignatov (1998)

        Args:
            ndvi_series: Smoothed NDVI values.
            ndvi_soil: NDVI of bare soil (default 0.10).
            ndvi_veg: NDVI of fully vegetated pixel (default 0.85).

        Returns:
            FVC per timestep, clamped to [0, 1].
        """
        rng = ndvi_veg - ndvi_soil
        if rng < 0.01:
            return [0.0] * len(ndvi_series)

        fvc = []
        for ndvi in ndvi_series:
            ratio = (ndvi - ndvi_soil) / rng
            ratio = max(0.0, min(1.0, ratio))
            fvc.append(ratio ** 2)  # Squared per Carlson & Ripley
        return fvc

    # =====================================================================
    # NPP Proxy (Monteith 1977 Light-Use Efficiency)
    # =====================================================================

    @staticmethod
    def compute_npp_proxy(
        fpar_series: List[float],
        latitude: Optional[float] = None,
        start_doy: int = 1,
    ) -> List[float]:
        """Estimate Net Primary Productivity proxy.

        NPP ≈ fPAR × PAR × LUE

        PAR is approximated from latitude and day of year using a
        simplified solar radiation model.

        Args:
            fpar_series: fPAR values per timestep.
            latitude: Field latitude in degrees (default 36° for Algeria).
            start_doy: Starting day-of-year for the time series.

        Returns:
            NPP proxy in gC/m²/day per timestep.
        """
        if latitude is None:
            return []
        LUE = 1.5  # Light Use Efficiency (gC/MJ) — generic C3 crops
        SOLAR_CONSTANT = 1361  # W/m² (top of atmosphere)

        npp = []
        lat_rad = math.radians(latitude)

        for i, fpar in enumerate(fpar_series):
            doy = (start_doy + i - 1) % 365 + 1

            # Solar declination (Spencer 1971)
            decl = 0.4093 * math.sin(2 * math.pi * (284 + doy) / 365)

            # Day length (hours)
            cos_ha = -math.tan(lat_rad) * math.tan(decl)
            cos_ha = max(-1.0, min(1.0, cos_ha))
            day_length = 24.0 * math.acos(cos_ha) / math.pi

            # Daily extraterrestrial radiation (MJ/m²/day)
            # Simplified: Rs ≈ 0.75 × Ra (clear sky transmissivity)
            ra = SOLAR_CONSTANT * 3600 * day_length / 1e6  # Convert W to MJ
            rs = 0.75 * ra * 0.48  # PAR = 48% of total solar

            # NPP = fPAR × PAR × LUE
            npp_val = fpar * rs * LUE
            npp.append(max(0.0, round(npp_val, 3)))

        return npp

    # =====================================================================
    # CWSI — Crop Water Stress Index (Jackson et al. 1981)
    # =====================================================================

    @staticmethod
    def compute_cwsi(
        ndwi_series: Optional[List[Optional[float]]],
        ndvi_series: List[float],
    ) -> List[float]:
        """Compute Crop Water Stress Index from NDVI-NDWI relationship.

        CWSI = 1 - (NDWI_normalized)
        where NDWI_normalized = (NDWI - NDWI_min) / (NDWI_max - NDWI_min)

        When NDWI is unavailable, falls back to NDVI-only proxy:
        CWSI ≈ 1 - (NDVI / NDVI_max)
        """
        n = len(ndvi_series)

        # Try NDWI-based CWSI
        if ndwi_series and any(v is not None for v in ndwi_series):
            valid = [v for v in ndwi_series if v is not None]
            ndwi_min = min(valid)
            ndwi_max = max(valid)
            ndwi_range = ndwi_max - ndwi_min if ndwi_max > ndwi_min else 0.1

            cwsi = []
            for i in range(n):
                ndwi_val = ndwi_series[i] if i < len(ndwi_series) else None
                if ndwi_val is not None:
                    normalized = (ndwi_val - ndwi_min) / ndwi_range
                    cwsi.append(max(0.0, min(1.0, 1.0 - normalized)))
                else:
                    ndvi_max = max(ndvi_series) if ndvi_series else 1.0
                    cwsi.append(max(0.0, min(1.0, 1.0 - ndvi_series[i] / max(0.1, ndvi_max))))
            return cwsi

        # NDVI-only fallback
        ndvi_max = max(ndvi_series) if ndvi_series else 1.0
        return [max(0.0, min(1.0, 1.0 - v / max(0.1, ndvi_max))) for v in ndvi_series]

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
        et_actual = []
        et_deficit = []

        for i in range(n):
            et0 = et0_series[i] if et0_series[i] is not None else 3.0  # Default 3mm/day
            kc = kc_series[i] if i < len(kc_series) else 1.0
            rain = rainfall_series[i] if i < len(rainfall_series) else 0.0

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

    @staticmethod
    def compute_npp_casa(
        fpar_series: List[float],
        latitude: Optional[float] = None,
        start_doy: int = 1,
        temperature_series: Optional[List[float]] = None,
        cwsi_series: Optional[List[float]] = None,
        t_opt: float = 25.0,
        t_min: float = 5.0,
        t_max: float = 45.0,
        epsilon_max: float = 0.604,
    ) -> List[float]:
        """CASA-model Net Primary Productivity with stress scalars.

        NPP = fPAR × PAR × ε_max × T_scalar × W_scalar

        T_scalar (temperature stress factor):
            T_scalar = min( (T - T_min)/(T_opt - T_min),
                            (T_max - T)/(T_max - T_opt) )
            Bounded [0, 1]. Peaks at T_opt.

        W_scalar (water stress factor):
            W_scalar = 0.5 + 0.5 × (1 - CWSI)
            CWSI=0 → W_scalar=1.0, CWSI=1 → W_scalar=0.5

        Reference: Potter et al. (1993) "Terrestrial ecosystem production:
        A process model based on global satellite and surface data",
        Global Biogeochemical Cycles 7(4): 811-841.

        Falls back to simple fPAR × PAR × ε when temperature/CWSI unavailable.
        """
        if latitude is None:
            return []
        SOLAR_CONSTANT = 1361  # W/m²
        lat_rad = math.radians(latitude)
        npp = []

        for i, fpar in enumerate(fpar_series):
            doy = (start_doy + i - 1) % 365 + 1

            # Solar declination
            decl = 0.4093 * math.sin(2 * math.pi * (284 + doy) / 365)
            cos_ha = -math.tan(lat_rad) * math.tan(decl)
            cos_ha = max(-1.0, min(1.0, cos_ha))
            day_length = 24.0 * math.acos(cos_ha) / math.pi

            # PAR (MJ/m²/day)
            ra = SOLAR_CONSTANT * 3600 * day_length / 1e6
            par = 0.75 * ra * 0.48  # Clear sky × PAR fraction

            # T_scalar
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

            # W_scalar
            w_scalar = 1.0
            if cwsi_series and i < len(cwsi_series):
                cwsi = cwsi_series[i]
                w_scalar = 0.5 + 0.5 * (1.0 - cwsi)

            npp_val = fpar * par * epsilon_max * t_scalar * w_scalar
            npp.append(max(0.0, round(npp_val, 3)))

        return npp

    # =====================================================================
    # v3.2: Water Use Efficiency (Steduto et al. 2009 — AquaCrop)
    # =====================================================================

    @staticmethod
    def compute_water_use_efficiency(
        biomass_series: List[float],
        et_actual_series: List[float],
        window: int = 14,
    ) -> Dict[str, float]:
        """Compute Water Use Efficiency and Crop Water Productivity.

        WUE = ΔBiomass / ETa (gC/m²/mm)
        CWP = Yield / ET_total (kg/m³)

        Uses trailing window to compute recent WUE.

        Reference: Steduto et al. (2009) "AquaCrop — The FAO crop model
        to simulate yield response to water", Agronomy Journal.
        """
        if not biomass_series or not et_actual_series:
            return {"wue": 0.0, "crop_water_productivity": 0.0, "et_total": 0.0}

        n = min(len(biomass_series), len(et_actual_series))
        w = min(window, n)

        # Recent biomass change
        recent_bio = biomass_series[-w:]
        recent_et = et_actual_series[-w:]

        delta_biomass = max(0.0, recent_bio[-1] - recent_bio[0]) if len(recent_bio) >= 2 else 0.0
        et_sum = sum(recent_et)

        wue = delta_biomass / max(0.01, et_sum) if et_sum > 0 else 0.0

        # Total season ET and CWP
        et_total = sum(et_actual_series[:n])
        total_biomass = max(biomass_series) if biomass_series else 0.0

        # CWP in kg/m³ (biomass in gC/m², ET in mm → multiply by 10 for kg/ha per mm)
        cwp = (total_biomass / max(0.01, et_total)) * 10.0 if et_total > 0 else 0.0

        return {
            "wue": round(wue, 4),
            "crop_water_productivity": round(cwp, 3),
            "et_total": round(et_total, 2),
        }

    # =====================================================================
    # v3.2: Adaptive Ensemble Smoother
    # =====================================================================

    def _fit_ensemble(
        self,
        ndvi_values: List[float],
        uncertainties: List[float],
    ) -> Tuple[List[float], Dict[str, List[float]], List[float]]:
        """Blend Whittaker + Savitzky-Golay with data-quality-adaptive weights.

        For each point, weights are inversely proportional to each smoother's
        local residual against the raw observations.

        ensemble[t] = Σ(w_i × smoother_i[t]) / Σ(w_i)

        Falls back to Whittaker alone if blending fails.
        """
        if not HAS_SCIPY or len(ndvi_values) < 10:
            return self._fit_whittaker(ndvi_values, uncertainties)

        # Run Whittaker
        whit_curve, whit_deriv, whit_unc = self._fit_whittaker(ndvi_values, uncertainties)

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

        # Recompute derivatives on ensemble
        velocity, acceleration = self._savgol_derivatives(ensemble)

        # Convert to dict format (V922.2A: fix tuple/dict inconsistency)
        deriv = {
            "velocity": list(velocity) if hasattr(velocity, "tolist") else list(velocity),
            "acceleration": list(acceleration) if hasattr(acceleration, "tolist") else list(acceleration),
        }

        # Uncertainty: average of both
        ens_unc = [
            round((whit_unc[i] + abs(whit_curve[i] - sg_curve[i])) / 2, 4)
            for i in range(n)
        ]

        # V922.2A: Enforce length alignment
        ens_unc = _align_length(ens_unc, n)

        return ensemble, deriv, ens_unc

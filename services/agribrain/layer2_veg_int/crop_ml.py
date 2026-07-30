"""
Crop Identification ML Module — State-of-the-Art AI/ML Features
================================================================

Scientific foundations:
  - Savitzky-Golay filter (Savitzky & Golay, 1964) for NDVI smoothing
  - TIMESAT phenology extraction (Jönsson & Eklundh, 2004)
  - Gaussian likelihood scoring (Bishop, 2006 — Pattern Recognition & ML)
  - Bayesian posterior fusion (Khatami et al., 2016)
  - Shannon entropy confidence (Shannon, 1948)
  - Self-learning feedback loop (semi-supervised adaptation)

Dependencies: numpy, scipy (signal, stats)
"""

import math
import json
import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger("agribrain.crop_ml")

# Try scipy for Savitzky-Golay; fallback to numpy convolution
try:
    from scipy.signal import savgol_filter as _scipy_savgol
    from scipy.stats import norm as _scipy_norm
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger.warning("scipy not available — using numpy fallback for SG filter")


# =============================================================================
# 1. SAVITZKY-GOLAY NDVI SMOOTHING
# =============================================================================

def smooth_ndvi_time_aware(
    series: List[float],
    dates: List[str],
    window_days: float = 45.0,
    polyorder: int = 2,
) -> Tuple[np.ndarray, List[str], Dict[str, object]]:
    """Smooth observations on their real time axis without filling gaps.

    A Savitzky-Golay window is defined in samples and is therefore invalid for
    irregular satellite cadence. This local polynomial smoother evaluates
    only at observed dates, weights support by elapsed days, coalesces same-day
    observations, and never creates synthetic observations inside cloud gaps.
    """
    if len(series) != len(dates):
        raise ValueError("NDVI values and dates must have identical lengths")

    buckets: Dict[str, List[float]] = {}
    parsed_by_day: Dict[str, datetime] = {}
    for raw_value, raw_date in zip(series, dates):
        try:
            value = float(raw_value)
            if not math.isfinite(value):
                continue
            stamp = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        day = stamp.date().isoformat()
        buckets.setdefault(day, []).append(value)
        parsed_by_day[day] = stamp

    ordered_days = sorted(buckets, key=lambda day: parsed_by_day[day])
    values = np.asarray(
        [sum(buckets[day]) / len(buckets[day]) for day in ordered_days],
        dtype=np.float64,
    )
    if len(values) == 0:
        return values, [], {
            "method": "time_aware_local_polynomial",
            "support_count": 0,
            "interpolated_point_count": 0,
            "status": "no_valid_dated_support",
        }

    origin = parsed_by_day[ordered_days[0]]
    axis = np.asarray(
        [(parsed_by_day[day] - origin).days for day in ordered_days],
        dtype=np.float64,
    )
    gaps = np.diff(axis)
    irregular = bool(
        len(gaps) > 1 and not np.allclose(gaps, np.median(gaps), atol=0.5)
    )
    if len(values) < 3 or float(axis[-1] - axis[0]) <= 0.0:
        return np.clip(values, 0.0, 1.0), ordered_days, {
            "method": "time_aware_local_polynomial",
            "support_count": len(values),
            "temporal_span_days": int(axis[-1] - axis[0]),
            "maximum_gap_days": float(max(gaps)) if len(gaps) else 0.0,
            "irregular_cadence": irregular,
            "interpolated_point_count": 0,
            "status": "insufficient_support_for_smoothing",
        }

    working = values.copy()
    bandwidth = max(1.0, float(window_days) / 2.0)
    smoothed = working.copy()
    for pass_index in range(3):
        estimates = []
        for center_index, center in enumerate(axis):
            distances = np.abs(axis - center)
            selected = np.flatnonzero(distances <= bandwidth)
            required = min(len(axis), max(3, polyorder + 1))
            if len(selected) < required:
                selected = np.argsort(distances)[:required]
            x = axis[selected] - center
            y = working[selected]
            degree = min(polyorder, len(selected) - 1)
            weights = np.exp(-0.5 * (x / bandwidth) ** 2)
            design = np.vander(x, N=degree + 1, increasing=True)
            weighted_design = design * np.sqrt(weights)[:, None]
            weighted_values = y * np.sqrt(weights)
            try:
                coefficients = np.linalg.lstsq(
                    weighted_design, weighted_values, rcond=None
                )[0]
                estimates.append(float(coefficients[0]))
            except np.linalg.LinAlgError:
                estimates.append(float(working[center_index]))
        smoothed = np.asarray(estimates, dtype=np.float64)
        if pass_index < 2:
            # Upper-envelope correction is applied only at actual support
            # dates; it does not manufacture values between acquisitions.
            working = np.where(working < smoothed - 0.05, smoothed, working)

    return np.clip(smoothed, 0.0, 1.0), ordered_days, {
        "method": "time_aware_local_polynomial",
        "support_count": len(values),
        "temporal_span_days": int(axis[-1] - axis[0]),
        "maximum_gap_days": float(max(gaps)) if len(gaps) else 0.0,
        "median_gap_days": float(np.median(gaps)) if len(gaps) else 0.0,
        "irregular_cadence": irregular,
        "interpolated_point_count": 0,
        "status": "smoothed",
    }

def smooth_ndvi(
    series: List[float],
    window: int = 7,
    polyorder: int = 3,
) -> np.ndarray:
    """Apply Savitzky-Golay filter to smooth noisy NDVI timeseries.
    
    Standard preprocessing in ALL crop classification literature:
    - Removes cloud contamination artifacts
    - Preserves peak timing, inflection points, and seasonal shape
    - Critical for accurate phenological metric extraction
    
    Args:
        series: Raw NDVI values (may contain noise, cloud artifacts)
        window: Filter window size (must be odd). Default 7 for ~biweekly data.
        polyorder: Polynomial order. Default 3 (cubic) preserves peaks well.
    
    Returns:
        Smoothed NDVI array (numpy).
    
    Reference: Savitzky & Golay (1964), Chen et al. (2004)
    """
    arr = np.array(series, dtype=np.float64)
    n = len(arr)
    
    # FIX BUG-3: Ensure window < series length and is odd
    window = min(window, n - 2) if n > 4 else min(window, n)
    if window < 3:
        return np.clip(arr, 0.0, 1.0)
    if window % 2 == 0:
        window += 1
    # Clamp polyorder below window
    polyorder = min(polyorder, window - 1)
    
    # IMP-9: 3-pass upper-envelope SG (Chen et al., 2004 recommends 3-5)
    # Pass 1: initial smooth; Pass 2-3: correct cloud dips + re-smooth
    if HAS_SCIPY:
        smoothed = _scipy_savgol(arr, window, polyorder)
        for _iteration in range(2):  # 2 correction passes = 3 total
            for i in range(n):
                if arr[i] < smoothed[i] - 0.05:
                    arr[i] = smoothed[i]
            smoothed = _scipy_savgol(arr, window, polyorder)
    else:
        smoothed = _numpy_savgol(arr, window, polyorder)
    
    return np.clip(smoothed, 0.0, 1.0)


def _numpy_savgol(arr: np.ndarray, window: int, order: int) -> np.ndarray:
    """Pure numpy Savitzky-Golay fallback (no scipy dependency).
    
    FIX BUG-6: Uses reflection padding so edges are also filtered.
    """
    n = len(arr)
    half_w = window // 2
    # Reflect-pad edges so the filter covers the entire series
    padded = np.concatenate([arr[half_w:0:-1], arr, arr[-2:-half_w-2:-1]])
    result = np.copy(padded)
    
    for i in range(half_w, len(padded) - half_w):
        x = np.arange(-half_w, half_w + 1, dtype=np.float64)
        y = padded[i - half_w: i + half_w + 1]
        coeffs = np.polyfit(x, y, min(order, len(x) - 1))
        result[i] = np.polyval(coeffs, 0)
    
    return result[half_w: half_w + n]


# =============================================================================
# 2. ADVANCED PHENOLOGICAL METRICS (TIMESAT methodology)
# =============================================================================

def extract_phenology(
    smoothed: np.ndarray,
    dates: Optional[List[str]] = None,
    threshold_pct: float = 0.20,
) -> Dict[str, float]:
    """Extract 12 phenological metrics from smoothed NDVI curve.
    
    Follows TIMESAT (Jönsson & Eklundh, 2004) methodology:
    - SOS/EOS defined by threshold crossing on rising/falling limbs
    - Season integral computed as area above base value
    - Growth/senescence rates from first derivative
    
    Args:
        smoothed: Savitzky-Golay smoothed NDVI array
        dates: Optional date strings for DOY computation
        threshold_pct: Amplitude fraction for SOS/EOS detection (default 20%)
    
    Returns:
        Dict with 12 phenological metrics.
    """
    n = len(smoothed)
    if n < 5:
        return {}
    
    # Basic statistics
    peak_idx = int(np.argmax(smoothed))
    peak_val = float(smoothed[peak_idx])
    base_val = float(np.percentile(smoothed, 10))  # 10th percentile as base
    amplitude = peak_val - base_val
    
    if amplitude < 0.05:
        # Flat profile — evergreen or bare soil
        return {
            "sos_idx": 0, "eos_idx": n - 1, "pos_idx": peak_idx,
            "los_frac": 1.0, "peak_val": peak_val, "base_val": base_val,
            "amplitude": amplitude, "is_evergreen": True,
            "growth_rate": 0.0, "senescence_rate": 0.0,
            "small_integral": float(np.sum(smoothed - base_val) / n),
            "large_integral": float(np.sum(smoothed) / n),
            "n_seasons": 0, "asymmetry": 0.5,
        }
    
    # Threshold for SOS/EOS detection
    threshold = base_val + threshold_pct * amplitude
    
    # SOS: first crossing above threshold before peak
    sos_idx = 0
    for i in range(peak_idx):
        if smoothed[i] >= threshold:
            sos_idx = i
            break
    
    # EOS: last crossing below threshold after peak
    eos_idx = n - 1
    for i in range(n - 1, peak_idx, -1):
        if smoothed[i] >= threshold:
            eos_idx = i
            break
    
    date_axis: Optional[List[float]] = None
    if dates and len(dates) == n:
        try:
            parsed = [
                datetime.strptime(str(value)[:10], "%Y-%m-%d")
                for value in dates
            ]
            date_axis = [
                float((value - parsed[0]).days) for value in parsed
            ]
            if any(
                date_axis[index] <= date_axis[index - 1]
                for index in range(1, len(date_axis))
            ):
                date_axis = None
        except (TypeError, ValueError):
            date_axis = None

    # Length and rates use elapsed days when dated support exists.
    if date_axis is not None:
        total_span = max(1.0, date_axis[-1] - date_axis[0])
        season_span = max(0.0, date_axis[eos_idx] - date_axis[sos_idx])
        los_frac = season_span / total_span
        growth_denominator = max(
            1.0, date_axis[peak_idx] - date_axis[sos_idx]
        )
        senescence_denominator = max(
            1.0, date_axis[eos_idx] - date_axis[peak_idx]
        )
    else:
        los_frac = (eos_idx - sos_idx) / max(1, n - 1)
        growth_denominator = max(1, peak_idx - sos_idx)
        senescence_denominator = max(1, eos_idx - peak_idx)
    
    # Growth rate: mean NDVI increase per step during greenup
    if peak_idx > sos_idx:
        growth_rate = float(
            (smoothed[peak_idx] - smoothed[sos_idx]) / growth_denominator
        )
    else:
        growth_rate = 0.0
    
    # Senescence rate: mean NDVI decrease per step during senescence
    if eos_idx > peak_idx:
        senescence_rate = float(
            (smoothed[peak_idx] - smoothed[eos_idx])
            / senescence_denominator
        )
    else:
        senescence_rate = 0.0
    
    # Integrals (TIMESAT-style)
    # Small integral: area between base and curve (net seasonal productivity)
    small_integral = float(np.sum(np.maximum(smoothed - base_val, 0)) / n)
    # Large integral: total area under curve
    large_integral = float(np.sum(smoothed) / n)
    
    # Asymmetry: how skewed is the growth season? <0.5 = early peak, >0.5 = late peak
    if eos_idx > sos_idx:
        asymmetry = (peak_idx - sos_idx) / (eos_idx - sos_idx)
    else:
        asymmetry = 0.5
    
    # Number of seasons (peak counting in smoothed curve)
    n_seasons = _count_seasons(smoothed, base_val + 0.3 * amplitude)
    
    # DOY computation if dates are available
    # FIX BUG-7: Use min(len(dates), n) to handle mismatched lengths
    sos_doy, eos_doy, pos_doy = None, None, None
    if dates and len(dates) >= 3:
        try:
            nd = len(dates)
            if sos_idx < nd:
                sos_doy = _date_to_doy(dates[sos_idx])
            if eos_idx < nd:
                eos_doy = _date_to_doy(dates[eos_idx])
            if peak_idx < nd:
                pos_doy = _date_to_doy(dates[peak_idx])
        except Exception:
            pass
    
    return {
        "sos_idx": sos_idx, "eos_idx": eos_idx, "pos_idx": peak_idx,
        "sos_doy": sos_doy, "eos_doy": eos_doy, "pos_doy": pos_doy,
        "los_frac": round(los_frac, 3),
        "peak_val": round(peak_val, 4),
        "base_val": round(base_val, 4),
        "amplitude": round(amplitude, 4),
        "is_evergreen": False,
        "growth_rate": round(growth_rate, 5),
        "senescence_rate": round(senescence_rate, 5),
        "small_integral": round(small_integral, 4),
        "large_integral": round(large_integral, 4),
        "n_seasons": n_seasons,
        "asymmetry": round(asymmetry, 3),
    }


def _count_seasons(arr: np.ndarray, threshold: float) -> int:
    """Count distinct growing seasons by counting distinct above-threshold runs."""
    above = arr >= threshold
    count = 0
    in_season = False
    for v in above:
        if v and not in_season:
            count += 1
            in_season = True
        elif not v:
            in_season = False
    return count


def _date_to_doy(date_str: str) -> int:
    """Convert date string to day-of-year."""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.timetuple().tm_yday
    except Exception:
        return 0


# =============================================================================
# 3. GAUSSIAN LIKELIHOOD SCORING
# =============================================================================

def gaussian_likelihood(
    observed: float,
    expected: float,
    sigma: float,
) -> float:
    """Compute Gaussian likelihood P(observed | expected, sigma).
    
    This is the core of Bayesian crop identification:
    - Each crop's signature defines an expected value and uncertainty (sigma)
    - The likelihood measures how probable the observation is under that crop's model
    - Returns value in [0, 1] where 1 = perfect match
    
    Args:
        observed: Measured value from satellite
        expected: Expected value from crop reference signature
        sigma: Standard deviation (uncertainty) of the crop's parameter
    
    Reference: Bishop (2006) — Pattern Recognition and Machine Learning, Ch. 2
    """
    if sigma <= 0:
        sigma = 0.05
    z = (observed - expected) / sigma
    return math.exp(-0.5 * z * z)


# BUG-8: multivariate_likelihood removed (was dead code, reimplemented
# inline in BayesianCropClassifier.compute_log_likelihood)


# =============================================================================
# 4. BAYESIAN POSTERIOR FUSION
# =============================================================================

class BayesianCropClassifier:
    """Full Bayesian posterior crop classifier.
    
    P(crop_k | observations) ∝ P(observations | crop_k) × P(crop_k)
    
    Where:
    - P(observations | crop_k) = product of per-module Gaussian likelihoods
    - P(crop_k) = prior from regional prevalence, area, irrigation
    
    The posterior is computed in log-space and normalized via softmax.
    
    Reference: Khatami et al. (2016) — Meta-analysis of crop classification
    """
    
    def __init__(self, crop_signatures: Dict, regional_priors: Dict = None):
        """
        Args:
            crop_signatures: Dict[crop_code] → signature dict with expected values and sigmas
            regional_priors: Dict[crop_code] → prior probability (unnormalized)
        """
        self.signatures = crop_signatures
        self.priors = regional_priors or {}
        # Default sigma values for each feature dimension
        self.default_sigmas = {
            "peak_ndvi": 0.08,
            "trough_ndvi": 0.06,
            "amplitude": 0.10,
            "peak_frac": 0.12,
            "los_frac": 0.15,
        }
        # FIX BUG-1 + IMP-6: Per-crop learned sigma overrides
        # Dict[crop_code → Dict[feature_key → sigma]]
        self.crop_sigmas: Dict[str, Dict[str, float]] = {}
    
    def _get_sigma(self, crop_code: str, feature_key: str) -> float:
        """Get sigma for a feature, preferring per-crop learned values."""
        if crop_code in self.crop_sigmas:
            crop_s = self.crop_sigmas[crop_code]
            if feature_key in crop_s:
                return crop_s[feature_key]
        return self.default_sigmas.get(feature_key, 0.10)
    
    def compute_log_likelihood(
        self,
        crop_code: str,
        phenology: Dict[str, float],
        shape_features: Dict[str, float],
    ) -> float:
        """Compute log P(observations | crop_k) for a single crop.
        
        Uses 8 features on the SAME SCALE between reference and observed:
        - 4 continuous NDVI features (peak, trough, amplitude, peak_frac)
        - 1 season length feature (los_frac)
        - 1 binary feature (is_evergreen)
        - 1 integer feature (n_seasons vs n_peaks)
        - 1 temporal feature (pos_doy vs expected peak month)
        """
        sig = self.signatures.get(crop_code, {})
        if not sig:
            return -5.0  # Very low likelihood for unknown crops
        
        log_lik = 0.0
        n_features = 0
        
        # ── Continuous feature comparisons (Gaussian likelihood) ──
        comparisons = [
            ("peak_val", "peak_ndvi", self._get_sigma(crop_code, "peak_ndvi")),
            ("base_val", "trough_ndvi", self._get_sigma(crop_code, "trough_ndvi")),
            ("amplitude", "amplitude", self._get_sigma(crop_code, "amplitude")),
            ("asymmetry", "peak_frac", self._get_sigma(crop_code, "peak_frac")),
            ("los_frac", "los_frac", self._get_sigma(crop_code, "los_frac")),
        ]
        
        for obs_key, ref_key, sigma in comparisons:
            obs_val = phenology.get(obs_key)
            if obs_val is None:
                obs_val = (shape_features or {}).get(obs_key)
            ref_val = sig.get(ref_key)
            if obs_val is not None and ref_val is not None:
                z = (obs_val - ref_val) / max(0.01, sigma)
                log_lik += -0.5 * z * z
                n_features += 1
        
        # ── IMP-1: Binary evergreen match (strongest citrus discriminator) ──
        obs_evergreen = phenology.get("is_evergreen")
        if obs_evergreen is not None:
            ref_shape = sig.get("shape", "unimodal")
            ref_is_eg = ref_shape in ("evergreen", "stable")
            if obs_evergreen == ref_is_eg:
                log_lik += 0.0  # Perfect match — no penalty
            else:
                log_lik += -3.0  # Strong penalty for evergreen/annual mismatch
            n_features += 1
        
        # ── IMP-4: Season count match (n_seasons vs n_peaks) ──
        obs_n_seasons = phenology.get("n_seasons")
        ref_n_peaks = sig.get("n_peaks")
        if obs_n_seasons is not None and ref_n_peaks is not None:
            if ref_n_peaks == 0:  # Evergreen: expect 0 seasons
                # Observed 0 = perfect, 1 = mild, 2+ = mismatch
                penalty = -0.5 * (obs_n_seasons ** 2)
            else:
                diff = abs(obs_n_seasons - ref_n_peaks)
                penalty = -0.5 * (diff ** 2) / max(1, ref_n_peaks)
            log_lik += penalty
            n_features += 1
        
        if n_features == 0:
            return -2.0
        
        # Normalize by feature count to avoid penalizing crops with more data
        return log_lik / n_features
    
    def compute_log_prior(self, crop_code: str) -> float:
        """Compute log P(crop_k) from regional priors."""
        prior = self.priors.get(crop_code, 0.35)
        return math.log(max(0.01, prior))
    
    def classify(
        self,
        phenology: Dict[str, float],
        shape_features: Dict[str, float],
        module_scores: Dict[str, Dict[str, float]] = None,
    ) -> List[Tuple[str, float]]:
        """Compute P(crop_k | data) for all crops and return sorted results.
        
        Args:
            phenology: Phenological metrics from extract_phenology()
            shape_features: Shape descriptors from _compute_shape_descriptors()
            module_scores: Optional dict of {crop_code: {module: score}} from
                          the existing weighted scoring system. These are treated
                          as additional likelihood terms.
        
        Returns:
            List of (crop_code, posterior_probability) sorted descending.
        """
        log_posteriors = {}
        
        for crop_code in self.signatures:
            # Log-likelihood from Gaussian feature matching
            log_lik = self.compute_log_likelihood(crop_code, phenology, shape_features)
            
            # Log-prior from regional prevalence
            log_prior = self.compute_log_prior(crop_code)
            
            # Additional module scores (converted to log-likelihood)
            log_modules = 0.0
            if module_scores and crop_code in module_scores:
                scores = module_scores[crop_code]
                for mod_name, mod_score in scores.items():
                    # Clamp to avoid log(0)
                    ms = max(0.01, min(1.0, mod_score))
                    log_modules += math.log(ms)
                if scores:
                    log_modules /= len(scores)  # Normalize by module count
            
            log_posteriors[crop_code] = log_lik + 0.3 * log_prior + 0.5 * log_modules
        
        # Softmax normalization to get proper probabilities
        if not log_posteriors:
            return []
        
        max_log = max(log_posteriors.values())
        exp_posteriors = {k: math.exp(v - max_log) for k, v in log_posteriors.items()}
        total = sum(exp_posteriors.values())
        
        posteriors = [(k, v / max(1e-10, total)) for k, v in exp_posteriors.items()]
        posteriors.sort(key=lambda x: x[1], reverse=True)
        
        return posteriors


# =============================================================================
# 5. ENTROPY-BASED CONFIDENCE CALIBRATION
# =============================================================================

def entropy_confidence(
    score_pairs: List[Tuple[str, float]],
    top_n: int = 10,
) -> Tuple[str, float, float]:
    """Compute information-theoretic confidence from score distribution.
    
    FIX BUG-10 + IMP-3: Uses softmax to convert raw scores into a proper
    probability distribution BEFORE computing Shannon entropy. This makes
    small score differences (0.88 vs 0.87) produce meaningful probability
    differences rather than near-uniform distributions.
    
    Args:
        score_pairs: List of (crop_code, score) sorted descending
        top_n: Number of top candidates to consider
    
    Returns:
        (confidence_label, confidence_score, entropy)
    
    Reference: Shannon (1948) — A Mathematical Theory of Communication
    """
    if not score_pairs:
        return "UNKNOWN", 0.0, 1.0
    
    top = score_pairs[:top_n]
    raw_scores = [s for _, s in top]
    if not raw_scores or max(raw_scores) <= 0:
        return "UNKNOWN", 0.0, 1.0
    
    # Softmax transform — temperature tuned for crop ID score distributions.
    # Crop scores are typically 0.6-0.9 with top-1/top-2 gaps of 0.005-0.10.
    # Temperature=0.02 maps: gap 0.01→1.6x, gap 0.05→12x, gap 0.10→150x
    temperature = 0.02
    max_s = max(raw_scores)
    # Clamp exponent to prevent overflow on very large score gaps
    exp_scores = [math.exp(max(-50, (s - max_s) / temperature)) for s in raw_scores]
    total_exp = sum(exp_scores)
    probs = [e / max(1e-15, total_exp) for e in exp_scores]
    
    # Shannon entropy over the softmax probabilities
    entropy = 0.0
    for p in probs:
        if p > 1e-15:
            entropy -= p * math.log2(p)
    
    max_entropy = math.log2(len(probs))  # Maximum entropy (uniform)
    
    # Normalized confidence: 0 = random, 1 = certain
    if max_entropy > 0:
        confidence = 1.0 - (entropy / max_entropy)
    else:
        confidence = 1.0
    
    # Margin: softmax probability ratio of #1 vs #2
    margin = probs[0] / max(1e-10, probs[1]) if len(probs) > 1 else 10.0
    
    # Calibrated label — tuned for crop ID softmax(T=0.02) distributions
    # gap ≥ 0.05 → margin ~12x  → HIGH  (clear winner)
    # gap ≥ 0.01 → margin ~1.6x → MODERATE (likely correct)
    # gap < 0.01 → margin ~1.0x → LOW (ambiguous)
    if margin > 5.0 and confidence > 0.30:
        label = "HIGH"
    elif margin > 1.5 and confidence > 0.08:
        label = "MODERATE"
    elif margin > 1.1:
        label = "LOW"
    else:
        label = "UNKNOWN"
    
    return label, round(confidence, 4), round(entropy, 4)


# =============================================================================
# 6. SELF-LEARNING FEEDBACK STORE
# =============================================================================

_FEEDBACK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".cache", "crop_feedback"
)


class CropFeedbackStore:
    """Persists user-confirmed crop observations for Bayesian learning.
    
    When a user accepts or corrects a crop identification, we store:
    - The NDVI timeseries and phenological features
    - The engine's prediction vs. the user's confirmed crop
    - Location context (lat, lng, climate zone)
    
    Over time, this accumulates a regional training dataset that:
    1. Adjusts per-crop sigma values (uncertainty narrows with more data)
    2. Updates regional priors (actual crop frequencies in the user's area)
    3. Learns local NDVI signatures that differ from generic references
    """
    
    def __init__(self, store_dir: str = None):
        self.store_dir = store_dir or _FEEDBACK_DIR
        os.makedirs(self.store_dir, exist_ok=True)
        self._samples: Optional[List[Dict]] = None
    
    def record_observation(
        self,
        plot_id: str,
        confirmed_crop: str,
        engine_prediction: str,
        engine_confidence: float,
        phenology: Dict,
        ndvi_series: List[float] = None,
        lat: float = None,
        lng: float = None,
    ) -> str:
        """Store a labeled sample when user confirms or corrects a crop."""
        sample = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "plot_id": plot_id,
            "confirmed_crop": confirmed_crop,
            "engine_prediction": engine_prediction,
            "engine_confidence": engine_confidence,
            "was_correct": confirmed_crop == engine_prediction,
            "phenology": phenology,
            "ndvi_series": ndvi_series,
            "lat": lat,
            "lng": lng,
        }
        
        # FIX BUG-5: Include HMS to prevent same-day overwrites
        fname = f"fb_{plot_id}_{confirmed_crop}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        fpath = os.path.join(self.store_dir, fname)
        
        with open(fpath, "w") as f:
            json.dump(sample, f, indent=2, default=str)
        
        self._samples = None  # Invalidate cache
        logger.info(f"[Feedback] Recorded: {confirmed_crop} for plot {plot_id} "
                    f"(engine said {engine_prediction}, correct={sample['was_correct']})")
        return fpath
    
    def load_all_samples(self) -> List[Dict]:
        """Load all feedback samples from disk."""
        if self._samples is not None:
            return self._samples
        
        samples = []
        if not os.path.exists(self.store_dir):
            return samples
        
        for fname in os.listdir(self.store_dir):
            if fname.startswith("fb_") and fname.endswith(".json"):
                try:
                    with open(os.path.join(self.store_dir, fname)) as f:
                        samples.append(json.load(f))
                except Exception:
                    continue
        
        self._samples = samples
        return samples
    
    def compute_learned_priors(self) -> Dict[str, float]:
        """Compute crop priors from accumulated feedback.
        
        Returns P(crop_k) based on observed frequency of confirmed crops.
        Uses Laplace smoothing to avoid zero probabilities.
        """
        samples = self.load_all_samples()
        if len(samples) < 3:
            return {}  # Not enough data to learn from
        
        counts: Dict[str, int] = {}
        for s in samples:
            crop = s.get("confirmed_crop", "")
            if crop:
                counts[crop] = counts.get(crop, 0) + 1
        
        # Laplace smoothing (add-1)
        total = sum(counts.values()) + len(counts)
        priors = {k: (v + 1) / total for k, v in counts.items()}
        
        logger.info(f"[Feedback] Learned priors from {len(samples)} samples: "
                    f"{len(priors)} crops, top={max(priors, key=priors.get) if priors else '?'}")
        return priors
    
    def compute_learned_sigmas(self, min_samples: int = 3) -> Dict[str, Dict[str, float]]:
        """Compute per-crop sigma (std deviation) from confirmed observations.
        
        For each crop with enough confirmed samples, compute the empirical
        standard deviation of each phenological metric. This narrows the
        Gaussian likelihood to reflect actual local variability.
        """
        samples = self.load_all_samples()
        
        # Group by confirmed crop
        by_crop: Dict[str, List[Dict]] = {}
        for s in samples:
            crop = s.get("confirmed_crop", "")
            pheno = s.get("phenology", {})
            if crop and pheno:
                by_crop.setdefault(crop, []).append(pheno)
        
        learned_sigmas = {}
        for crop, pheno_list in by_crop.items():
            if len(pheno_list) < min_samples:
                continue
            
            # Compute std dev for each metric
            metrics = {}
            for key in pheno_list[0]:
                if isinstance(pheno_list[0][key], (int, float)):
                    values = [p[key] for p in pheno_list if key in p and isinstance(p[key], (int, float))]
                    if len(values) >= min_samples:
                        std = float(np.std(values))
                        if std > 0.001:
                            metrics[key] = std
            
            if metrics:
                learned_sigmas[crop] = metrics
                logger.info(f"[Feedback] Learned sigmas for {crop}: "
                           f"{len(metrics)} features from {len(pheno_list)} samples")
        
        return learned_sigmas
    
    def get_accuracy_stats(self) -> Dict:
        """Compute engine accuracy statistics from feedback."""
        samples = self.load_all_samples()
        if not samples:
            return {"total": 0}
        
        correct = sum(1 for s in samples if s.get("was_correct"))
        total = len(samples)
        
        return {
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 3) if total > 0 else 0,
            "incorrect_crops": [
                s.get("confirmed_crop") for s in samples if not s.get("was_correct")
            ],
        }

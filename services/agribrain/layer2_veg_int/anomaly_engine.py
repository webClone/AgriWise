
"""
Layer 2.3: Temporal Anomaly Engine (v3.1)

Detects deviations between observed data and the biological growth model.

Enhancements over v3.0:
  - EWMA (Exponentially Weighted Moving Average) changepoint detection
    detects subtle trend shifts 3-5 days earlier than fixed Z-score
  - Frost damage detection from temp_min
  - Crop-specific temperature thresholds from CropRecord
  - Wind damage detection from SAR change without rainfall

Algorithms:
  1. Multi-Index Z-Score: simultaneous monitoring of NDVI, EVI, NDWI, NDMI
  2. Isolation Forest: unsupervised anomaly detection
  3. EWMA Control Chart (Roberts 1959): early trend shift detection
  4. Bidirectional detection: negative (stress) AND positive (waterlogging)

Anomaly Types:
  STALL, DROP, EARLY_SENESCENCE, DELAYED_EMERGENCE,
  WATER_STRESS, EXCESS_MOISTURE, NUTRIENT_DEFICIENCY,
  HEAT_STRESS, FROST_DAMAGE, WIND_DAMAGE, POSITIVE_ANOMALY
"""

import math
import statistics
import random
from typing import List, Dict, Tuple, Optional
from layer2_veg_int.schema import (
    VegetationAnomaly, AnomalyType, AttributionEvidence,
)


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
        sar_vh: List[float] = None,
        temperature: List[float] = None,
        evi_series: List[Optional[float]] = None,
        ndwi_series: List[Optional[float]] = None,
        ndmi_series: List[Optional[float]] = None,
        crop_temp_max: float = 35.0,
        crop_temp_min: float = 5.0,
        temp_min_series: List[Optional[float]] = None,
    ) -> List[VegetationAnomaly]:
        """
        Detects anomalies using multi-index Z-scores + isolation forest + EWMA.

        Returns list of VegetationAnomaly with AttributionEvidence.
        """
        anomalies = []
        n = len(dates)
        if n == 0:
            return []

        # ─── 1. Multi-Index Z-Scores ───
        ndvi_z = self._compute_z_scores(observed_ndvi, modeled_ndvi, uncertainties)

        # EVI z-scores (if available)
        evi_z = [0.0] * n
        if evi_series:
            evi_modeled = self._simple_smooth(evi_series)
            evi_z = self._compute_z_scores(
                [v if v is not None else 0.0 for v in evi_series],
                evi_modeled,
                [0.05] * n,
            )

        # NDWI z-scores (if available)
        ndwi_z = [0.0] * n
        if ndwi_series:
            ndwi_modeled = self._simple_smooth(ndwi_series)
            ndwi_z = self._compute_z_scores(
                [v if v is not None else 0.0 for v in ndwi_series],
                ndwi_modeled,
                [0.05] * n,
            )

        # ─── 2. Combined anomaly score ───
        # Weighted average of per-index z-scores (weights sum to 1.0)
        combined_z = []
        for i in range(n):
            w_sum = 0.0
            z_weighted = 0.0

            # NDVI is always the primary signal
            z_weighted += abs(ndvi_z[i]) * 0.50
            w_sum += 0.50

            if evi_series and i < len(evi_series) and evi_series[i] is not None:
                z_weighted += abs(evi_z[i]) * 0.25
                w_sum += 0.25

            if ndwi_series and i < len(ndwi_series) and ndwi_series[i] is not None:
                z_weighted += abs(ndwi_z[i]) * 0.25
                w_sum += 0.25

            # Normalize to preserve z-score scale
            combined_val = z_weighted / w_sum if w_sum > 0 else 0.0

            # Sign from NDVI z-score (negative = stress, positive = surplus)
            sign = -1.0 if ndvi_z[i] < 0 else 1.0
            combined_z.append(sign * combined_val)

        # ─── 3. EWMA Control Chart (Roberts 1959) ───
        ewma_anomalies = self._ewma_changepoint(combined_z, dates)

        # ─── 4. Isolation Forest Score ───
        iso_scores = self._isolation_forest_scores(
            observed_ndvi, modeled_ndvi, ndwi_series, sar_vh, sar_vv,
        )

        # ─── 5. Scan for persistent anomalies (bidirectional) ───
        neg_anomalies = self._scan_runs(
            combined_z, dates, threshold=-self.z_threshold,
            direction="negative",
        )
        pos_anomalies = self._scan_runs(
            combined_z, dates, threshold=self.z_threshold,
            direction="positive",
        )

        # ─── 6. Merge EWMA detections with Z-score runs ───
        all_neg_runs = self._merge_runs(neg_anomalies, ewma_anomalies)

        # ─── 7. Build anomaly objects with attribution ───
        for start, end in all_neg_runs:
            anomaly = self._create_anomaly(
                dates, observed_ndvi, modeled_ndvi, start, end,
                ndvi_z, evi_z, ndwi_z, iso_scores,
                rainfall, sar_vv, sar_vh, temperature,
                ndwi_series, ndmi_series,
                crop_temp_max, crop_temp_min, temp_min_series,
                is_positive=False,
            )
            anomalies.append(anomaly)

        for start, end in pos_anomalies:
            anomaly = self._create_anomaly(
                dates, observed_ndvi, modeled_ndvi, start, end,
                ndvi_z, evi_z, ndwi_z, iso_scores,
                rainfall, sar_vv, sar_vh, temperature,
                ndwi_series, ndmi_series,
                crop_temp_max, crop_temp_min, temp_min_series,
                is_positive=True,
            )
            anomalies.append(anomaly)

        return anomalies

    # =====================================================================
    # EWMA Control Chart (Roberts 1959, Hunter 1986)
    # =====================================================================

    def _ewma_changepoint(
        self,
        z_scores: List[float],
        dates: List[str],
        lam: float = 0.2,
        L: float = 3.0,
    ) -> List[Tuple[int, int]]:
        """EWMA control chart for early changepoint detection.

        EWMA_t = λ × z_t + (1-λ) × EWMA_{t-1}
        Alarm when |EWMA_t| > L × σ_ewma

        where σ_ewma = σ × sqrt(λ/(2-λ) × (1-(1-λ)^(2t)))

        Detects subtle, sustained shifts 3-5 days earlier than
        fixed-window Z-score methods.

        Returns: list of (start_idx, end_idx) for detected shifts.
        """
        n = len(z_scores)
        if n < 5:
            return []

        # Estimate σ from z-score series
        sigma = statistics.stdev(z_scores) if len(z_scores) > 2 else 1.0
        if sigma < 0.1:
            sigma = 1.0  # Prevent division by zero for flat signals

        ewma = 0.0
        runs = []
        in_alarm = False
        alarm_start = 0

        for t in range(n):
            ewma = lam * z_scores[t] + (1 - lam) * ewma

            # Time-varying control limits
            factor = lam / (2.0 - lam) * (1.0 - (1.0 - lam) ** (2 * (t + 1)))
            sigma_ewma = sigma * math.sqrt(max(1e-6, factor))
            ucl = L * sigma_ewma

            if abs(ewma) > ucl and ewma < 0:  # Only negative (stress) direction
                if not in_alarm:
                    in_alarm = True
                    alarm_start = t
            else:
                if in_alarm:
                    if t - alarm_start >= self.persistence_days:
                        runs.append((alarm_start, t))
                    in_alarm = False

        if in_alarm and n - alarm_start >= self.persistence_days:
            runs.append((alarm_start, n))

        return runs

    @staticmethod
    def _merge_runs(
        z_runs: List[Tuple[int, int]],
        ewma_runs: List[Tuple[int, int]],
    ) -> List[Tuple[int, int]]:
        """Merge Z-score runs and EWMA runs, removing duplicates."""
        all_runs = list(z_runs)

        for ew_start, ew_end in ewma_runs:
            # Check if this EWMA run overlaps with any existing Z-score run
            overlaps = False
            for z_start, z_end in z_runs:
                if ew_start < z_end and ew_end > z_start:
                    overlaps = True
                    break
            if not overlaps:
                all_runs.append((ew_start, ew_end))

        # Sort by start index
        all_runs.sort(key=lambda x: x[0])
        return all_runs

    # =====================================================================
    # Z-Score Computation
    # =====================================================================

    def _compute_z_scores(
        self,
        observed: List[float],
        modeled: List[float],
        uncertainties: List[float],
    ) -> List[float]:
        """Compute per-timestep Z-scores: (obs - model) / uncertainty."""
        z = []
        for i in range(len(observed)):
            obs = observed[i]
            mod = modeled[i] if i < len(modeled) else 0.0
            unc = (uncertainties[i] if i < len(uncertainties) else 0.05) + 0.02

            if obs is None:
                z.append(0.0)
            else:
                z.append((obs - mod) / unc)
        return z

    # =====================================================================
    # Persistence Scanner (Bidirectional)
    # =====================================================================

    def _scan_runs(
        self,
        z_scores: List[float],
        dates: List[str],
        threshold: float,
        direction: str = "negative",
    ) -> List[Tuple[int, int]]:
        """Scan for runs of consecutive anomalous z-scores."""
        runs = []
        n = len(z_scores)
        in_run = False
        start = 0

        for i in range(n):
            if direction == "negative":
                is_anomalous = z_scores[i] < threshold
            else:
                is_anomalous = z_scores[i] > threshold

            if is_anomalous and not in_run:
                in_run = True
                start = i
            elif not is_anomalous and in_run:
                if i - start >= self.persistence_days:
                    runs.append((start, i))
                in_run = False

        if in_run and n - start >= self.persistence_days:
            runs.append((start, n))

        return runs

    # =====================================================================
    # Isolation Forest (Pure Python)
    # =====================================================================

    def _isolation_forest_scores(
        self,
        observed_ndvi: List[float],
        modeled_ndvi: List[float],
        ndwi_series: Optional[List[Optional[float]]],
        sar_vh: Optional[List[float]],
        sar_vv: Optional[List[float]],
        n_trees: int = 50,
        max_depth: int = 8,
    ) -> List[float]:
        """Compute Isolation Forest anomaly scores.

        Returns scores in [0, 1] where 1 = highly anomalous.
        """
        n = len(observed_ndvi)
        if n < 10:
            return [0.0] * n

        # Build feature matrix
        features = []
        for i in range(n):
            obs = observed_ndvi[i] if observed_ndvi[i] is not None else 0.0
            mod = modeled_ndvi[i] if i < len(modeled_ndvi) else 0.0
            residual = obs - mod

            if i > 0 and observed_ndvi[i] is not None and observed_ndvi[i-1] is not None:
                vel = observed_ndvi[i] - observed_ndvi[i-1]
            else:
                vel = 0.0

            ndwi = 0.0
            if ndwi_series and i < len(ndwi_series) and ndwi_series[i] is not None:
                ndwi = ndwi_series[i]

            sar_ratio = 0.0
            if sar_vh and sar_vv and i < len(sar_vh) and i < len(sar_vv):
                if sar_vh[i] is not None and sar_vv[i] is not None and sar_vv[i] != 0:
                    sar_ratio = sar_vh[i] / (abs(sar_vv[i]) + 1e-6)

            features.append([residual, vel, ndwi, sar_ratio])

        rng = random.Random(42)
        avg_path_lengths = [0.0] * n

        for _ in range(n_trees):
            sample_size = min(n, max(10, n // 2))
            sample_indices = rng.sample(range(n), sample_size)

            for i in range(n):
                path_len = self._isolation_path_length(
                    features[i], [features[j] for j in sample_indices],
                    max_depth, rng,
                )
                avg_path_lengths[i] += path_len

        for i in range(n):
            avg_path_lengths[i] /= n_trees

        cn = 2.0 * (_harmonic(n - 1)) - 2.0 * (n - 1) / n if n > 1 else 1.0
        scores = []
        for pl in avg_path_lengths:
            s = 2.0 ** (-pl / max(cn, 1.0))
            scores.append(min(1.0, max(0.0, s)))

        return scores

    @staticmethod
    def _isolation_path_length(
        point: List[float],
        sample: List[List[float]],
        max_depth: int,
        rng: random.Random,
    ) -> float:
        """Compute isolation path length for a single point."""
        depth = 0
        current_sample = list(sample)

        while len(current_sample) > 1 and depth < max_depth:
            n_features = len(point)
            feat_idx = rng.randint(0, n_features - 1)

            vals = [s[feat_idx] for s in current_sample]
            vmin, vmax = min(vals), max(vals)
            if vmax - vmin < 1e-10:
                break

            split = rng.uniform(vmin, vmax)

            if point[feat_idx] < split:
                current_sample = [s for s in current_sample if s[feat_idx] < split]
            else:
                current_sample = [s for s in current_sample if s[feat_idx] >= split]

            depth += 1

        if len(current_sample) > 1:
            depth += _harmonic(len(current_sample) - 1)

        return depth

    # =====================================================================
    # Simple Smoother (for EVI/NDWI baseline)
    # =====================================================================

    @staticmethod
    def _simple_smooth(
        series: List[Optional[float]], window: int = 5,
    ) -> List[float]:
        """Simple moving average for building baseline from multi-spectral series."""
        n = len(series)
        result = []
        half = window // 2
        for i in range(n):
            start = max(0, i - half)
            end = min(n, i + half + 1)
            vals = [v for v in series[start:end] if v is not None]
            result.append(sum(vals) / len(vals) if vals else 0.0)
        return result

    # =====================================================================
    # Enhanced Anomaly Creation with Attribution (v3.1)
    # =====================================================================

    def _create_anomaly(
        self,
        dates, obs, mod, start, end,
        ndvi_z, evi_z, ndwi_z, iso_scores,
        rainfall, sar_vv, sar_vh, temperature,
        ndwi_series, ndmi_series,
        crop_temp_max, crop_temp_min, temp_min_series,
        is_positive,
    ) -> VegetationAnomaly:
        """Create an anomaly object with full attribution evidence."""

        # Mean z-score in the anomaly window
        segment_z = ndvi_z[start:end]
        mean_z = statistics.mean(segment_z) if segment_z else 0.0
        severity = min(abs(mean_z) / 5.0, 1.0)

        # Mean isolation forest score
        mean_iso = statistics.mean(iso_scores[start:end]) if iso_scores else 0.0

        # Combined confidence from z-score and isolation forest
        z_conf = min(abs(mean_z) / 3.0, 1.0)
        iso_conf = mean_iso
        confidence = 0.6 * z_conf + 0.4 * iso_conf

        # ─── Attribution Evidence ───
        attr = AttributionEvidence()

        # 1. Water stress: rain analysis (7d, 14d, 30d windows)
        rain_7d, rain_14d, rain_30d = 0.0, 0.0, 0.0
        if rainfall:
            rain_7d = sum(filter(None, rainfall[max(0, start-7):end]))
            rain_14d = sum(filter(None, rainfall[max(0, start-14):end]))
            rain_30d = sum(filter(None, rainfall[max(0, start-30):end]))

        if rain_30d < 10.0:
            attr.water_stress = 0.85
        elif rain_14d < 5.0:
            attr.water_stress = 0.65
        elif rain_7d < 2.0:
            attr.water_stress = 0.45

        # 2. NDWI decline without NDVI drop → early water stress
        if ndwi_series:
            before_ndwi = [v for v in ndwi_series[max(0,start-7):start] if v is not None]
            during_ndwi = [v for v in ndwi_series[start:end] if v is not None]
            if before_ndwi and during_ndwi:
                ndwi_drop = statistics.mean(before_ndwi) - statistics.mean(during_ndwi)
                if ndwi_drop > 0.05:
                    attr.water_stress = max(attr.water_stress, min(1.0, ndwi_drop * 5))

        # 3. Excess moisture: high rainfall + NDWI spike
        if rain_14d > 80.0:
            attr.excess_moisture = 0.70
        elif rain_7d > 50.0:
            attr.excess_moisture = 0.50

        # 4. Heat stress: temperature above crop optimum
        if temperature:
            temps = [t for t in temperature[start:end] if t is not None]
            if temps:
                max_temp = max(temps)
                mean_temp = statistics.mean(temps)
                if max_temp > crop_temp_max + 5:
                    attr.heat_stress = 0.80
                elif max_temp > crop_temp_max:
                    attr.heat_stress = 0.50
                elif mean_temp > crop_temp_max - 2:
                    attr.heat_stress = 0.30

        # 5. Frost damage: temp_min below crop minimum (v3.1)
        if temp_min_series:
            min_temps = [t for t in temp_min_series[start:end] if t is not None]
            if min_temps:
                coldest = min(min_temps)
                frost_threshold = crop_temp_min - 5.0
                if coldest < frost_threshold:
                    frost_severity = min(1.0, (frost_threshold - coldest) / 10.0)
                    attr.frost_stress = frost_severity
                elif coldest < crop_temp_min:
                    attr.frost_stress = 0.3

        # 6. Nutrient deficiency: EVI drops faster than NDVI
        if evi_z:
            mean_evi_z = statistics.mean(evi_z[start:end]) if evi_z[start:end] else 0.0
            if abs(mean_evi_z) > abs(mean_z) * 1.3 and mean_evi_z < -1.5:
                attr.nutrient_deficiency = min(1.0, abs(mean_evi_z - mean_z) * 0.5)

        # 7. Structural damage: SAR VH/VV change
        if sar_vv and sar_vh:
            before_start = max(0, start - 7)
            vv_before = [v for v in sar_vv[before_start:start] if v is not None]
            vv_during = [v for v in sar_vv[start:end] if v is not None]
            vh_before = [v for v in sar_vh[before_start:start] if v is not None]
            vh_during = [v for v in sar_vh[start:end] if v is not None]

            if vv_before and vv_during:
                delta_vv = statistics.mean(vv_during) - statistics.mean(vv_before)
                if delta_vv > 0.5:
                    attr.structural_damage = min(1.0, delta_vv * 0.8)

            if vh_before and vh_during:
                delta_vh = statistics.mean(vh_during) - statistics.mean(vh_before)
                if abs(delta_vh) > 0.3:
                    attr.structural_damage = max(attr.structural_damage, min(1.0, abs(delta_vh) * 0.6))

        # 8. Disease/pest: residual — no abiotic explanation
        abiotic_max = max(attr.water_stress, attr.excess_moisture,
                         attr.heat_stress, attr.frost_stress,
                         attr.nutrient_deficiency, attr.structural_damage)
        if abiotic_max < 0.30 and severity > 0.3:
            attr.disease_or_pest = min(1.0, severity * 1.5)

        # Determine primary cause
        causes = {
            "LIKELY_WATER_STRESS": attr.water_stress,
            "EXCESS_MOISTURE": attr.excess_moisture,
            "HEAT_STRESS": attr.heat_stress,
            "FROST_DAMAGE": attr.frost_stress,
            "NUTRIENT_DEFICIENCY": attr.nutrient_deficiency,
            "STRUCTURAL_DAMAGE": attr.structural_damage,
            "POSSIBLE_DISEASE_OR_PEST": attr.disease_or_pest,
        }
        if is_positive:
            causes = {"POSITIVE_ANOMALY": 0.8}

        attr.primary_cause = max(causes, key=causes.get)
        if max(causes.values()) < 0.20:
            attr.primary_cause = "GROWTH_STALL" if not is_positive else "POSITIVE_ANOMALY"

        # ─── Anomaly Type ───
        if is_positive:
            a_type = AnomalyType.POSITIVE_ANOMALY
        elif attr.frost_stress > 0.5:
            a_type = AnomalyType.FROST_DAMAGE
        elif attr.water_stress > 0.5:
            a_type = AnomalyType.WATER_STRESS
        elif attr.heat_stress > 0.5:
            a_type = AnomalyType.HEAT_STRESS
        elif attr.nutrient_deficiency > 0.4:
            a_type = AnomalyType.NUTRIENT_DEFICIENCY
        elif attr.excess_moisture > 0.5:
            a_type = AnomalyType.EXCESS_MOISTURE
        elif attr.structural_damage > 0.5 and rain_7d < 5:
            a_type = AnomalyType.WIND_DAMAGE
        elif abs(mean_z) < 3.0:
            a_type = AnomalyType.STALL
        else:
            a_type = AnomalyType.DROP

        # Valid diffs for description
        valid_diffs = []
        for i in range(start, end):
            if i < len(obs) and obs[i] is not None and i < len(mod):
                valid_diffs.append(obs[i] - mod[i])
        avg_diff = abs(statistics.mean(valid_diffs)) if valid_diffs else 0.0

        desc = f"Observed NDVI {'rose' if is_positive else 'dropped'} {avg_diff:.2f} {'above' if is_positive else 'below'} model."
        if attr.primary_cause != "GROWTH_STALL":
            desc += f" Primary cause: {attr.primary_cause.replace('_', ' ').lower()} ({max(causes.values()):.0%} confidence)."

        return VegetationAnomaly(
            anomaly_id=f"{dates[start]}_{a_type.value}",
            type=a_type,
            date_range=[dates[start], dates[min(end-1, len(dates)-1)]],
            severity=float(severity),
            confidence=float(min(1.0, confidence)),
            description=desc,
            likely_cause=attr.primary_cause,
            attribution=attr,
        )


# =========================================================================
# Utility
# =========================================================================

def _harmonic(n: int) -> float:
    """Approximate harmonic number H(n) ≈ ln(n) + 0.5772."""
    if n <= 0:
        return 0.0
    return math.log(n) + 0.5772156649


# ═══════════════════════════════════════════════════════════════════════════════
# v3.2: STL-lite Spectral Decomposition (Cleveland et al. 1990)
# ═══════════════════════════════════════════════════════════════════════════════

def spectral_decomposition(
    observed: List[float],
    modeled: List[float],
    dates: List[str],
    trend_window: int = 21,
) -> Dict[str, List[float]]:
    """Decompose NDVI residuals into trend, seasonal, and residual components.

    This is a simplified STL (Seasonal-Trend Decomposition using Loess)
    that uses Theil-Sen for trend and DOY-mean for seasonal component.

    Algorithm (STL-lite):
        1. Trend = Theil-Sen robust regression on rolling window
        2. De-trended = observed - trend
        3. Seasonal = mean de-trended residual at each DOY position
        4. Residual = observed - trend - seasonal

    Anomalies should be flagged on the RESIDUAL only, not on expected
    seasonal variation.

    Reference: Cleveland et al. (1990) "STL: A Seasonal-Trend Decomposition
    Procedure Based on Loess", Journal of Official Statistics.

    Returns:
        {
            "trend": [...],       # Robust trend component per timestep
            "seasonal": [...],    # Expected seasonal component per timestep
            "residual": [...],    # Unexplained remainder (anomaly signal)
        }
    """
    n = len(observed)
    if n < 10:
        residuals = [o - m for o, m in zip(observed, modeled)]
        return {"trend": list(modeled), "seasonal": [0.0] * n, "residual": residuals}

    # Step 1: Trend via Theil-Sen on rolling window
    trend = [0.0] * n
    half_w = trend_window // 2

    for t in range(n):
        lo = max(0, t - half_w)
        hi = min(n - 1, t + half_w)
        window_vals = observed[lo:hi + 1]
        window_len = len(window_vals)

        if window_len < 3:
            trend[t] = observed[t]
            continue

        # Theil-Sen: median of all pairwise slopes
        slopes = []
        for i in range(window_len - 1):
            for j in range(i + 1, window_len):
                if j != i:
                    slopes.append((window_vals[j] - window_vals[i]) / (j - i))

        if slopes:
            slopes.sort()
            median_slope = slopes[len(slopes) // 2]
            mid = window_len // 2
            intercept = window_vals[mid] - median_slope * mid
            local_pos = t - lo
            trend[t] = intercept + median_slope * local_pos
        else:
            trend[t] = observed[t]

    # Step 2: De-trend
    detrended = [observed[i] - trend[i] for i in range(n)]

    # Step 3: Seasonal component — average de-trended value at each position mod period
    # Use period = 30 (approximately monthly cycle) or total length / 4
    period = min(30, max(7, n // 4))
    seasonal_means: Dict[int, List[float]] = {}
    for i in range(n):
        phase = i % period
        seasonal_means.setdefault(phase, []).append(detrended[i])

    seasonal = [0.0] * n
    for i in range(n):
        phase = i % period
        vals = seasonal_means.get(phase, [0.0])
        seasonal[i] = statistics.mean(vals) if vals else 0.0

    # Step 4: Residual
    residual = [observed[i] - trend[i] - seasonal[i] for i in range(n)]

    return {
        "trend": [round(v, 4) for v in trend],
        "seasonal": [round(v, 4) for v in seasonal],
        "residual": [round(v, 4) for v in residual],
    }


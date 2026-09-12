
"""
Layer 2.4: Spatial Analysis Engine (v3.1)

Analyzes spatial patterns in vegetation across plot zones.

Enhancements over v3.0:
  - CUSUM control chart for persistent spatial deterioration detection
  - Theil-Sen slope per zone for robust trend estimation
  - Improved zone health ranking with trend-awareness

Algorithms:
  1. Moran's I — global spatial autocorrelation
     (High I → correlated stress = abiotic; Low I → random = biotic)
  2. Mann-Kendall — trend test on spatial variance time series
     (Detects increasing heterogeneity = spreading stress)
  3. CUSUM — Cumulative Sum control chart (Page 1954)
     (Detects persistent shifts in spatial variance)
  4. Zone Health Ranking — identifies best/worst zones with Theil-Sen trend
  5. Theil-Sen slope — robust median-of-pairwise-slopes trend estimator

References:
  - Moran (1950) "Notes on continuous stochastic phenomena"
  - Mann (1945) / Kendall (1975) non-parametric trend test
  - Page (1954) "Continuous inspection schemes"
  - Theil (1950), Sen (1968) — Robust trend estimation
"""

import math
import statistics
from typing import List, Dict, Tuple, Optional
from layer2_veg_int.schema import SpatialMetrics


class SpatialAnalysisEngine:

    def __init__(
        self,
        heterogeneity_threshold: float = 0.15,
        transient_threshold: float = 0.05,
    ):
        self.heterogeneity_threshold = heterogeneity_threshold
        self.transient_threshold = transient_threshold

    def analyze_stability(
        self,
        dates: List[str],
        spatial_std_series: List[float],
        zone_means: Optional[Dict[str, List[float]]] = None,
        phase_variability: float = 0.0,
        n_season_observations: int = 0,
        zone_centroids: Optional[Dict[str, Tuple[float, float]]] = None,
        zone_adjacency: Optional[Dict[str, List[str]]] = None,
    ) -> SpatialMetrics:
        """
        Full spatial analysis: stability class + Moran's I + trend + CUSUM + zone ranking.
        Calculates field stability and spatial variance metrics.

        Spatial Invariant:
          - Moran's I is computed ONLY when explicit zone_adjacency or physical
            zone_centroids (x, y) are provided. If geometry is absent, Moran's I
            returns (0.0, 1.0) with authority UNAVAILABLE.

        Returns SpatialMetrics dataclass.
        """
        if not spatial_std_series or len(spatial_std_series) == 0:
            return SpatialMetrics(
                mean_spatial_var=0.0,
                std_spatial_var=0.0,
                stability_class="UNKNOWN",
                confidence=0.0,
                spatial_trend="STABLE",
            )

        # ─── 1. Spatial Variance Summary ───
        mean_var = float(statistics.mean(spatial_std_series))
        std_var = float(statistics.stdev(spatial_std_series)) if len(spatial_std_series) > 1 else 0.0

        # ─── 2. Classification ───
        if mean_var > self.heterogeneity_threshold:
            stability_class = "HETEROGENEOUS"
            dist = mean_var - self.heterogeneity_threshold
            conf = 0.5 + min(0.5, dist * 10.0)
        else:
            stability_class = "STABLE"
            dist = self.heterogeneity_threshold - mean_var
            conf = 0.5 + min(0.5, dist * 10.0)

        # ─── 3. Moran's I (spatial autocorrelation with geometry gating) ───
        morans_i = 0.0
        morans_p = 1.0
        morans_status = "UNAVAILABLE"
        if zone_means and len(zone_means) >= 3:
            res = self._compute_morans_i(
                zone_means,
                zone_adjacency=zone_adjacency,
                zone_centroids=zone_centroids,
            )
            if len(res) == 3:
                morans_i, morans_p, morans_status = res
            else:
                morans_i, morans_p = res
                morans_status = "AVAILABLE" if (zone_adjacency or zone_centroids) else "UNAVAILABLE"

        # ─── 4. Mann-Kendall Trend Test ───
        spatial_trend = "STABLE"
        spatial_trend_p = 1.0
        if len(spatial_std_series) >= 5:
            mk_s, mk_p, trend_dir = self._mann_kendall(spatial_std_series)
            spatial_trend = trend_dir
            spatial_trend_p = mk_p

        # ─── 5. CUSUM Control Chart (Page 1954, v3.2: adaptive) ───
        cusum_alarm, cusum_value = self._cusum_chart(
            spatial_std_series,
            phase_variability=phase_variability,
            n_season_observations=n_season_observations,
        )

        # ─── 6. Zone Health Ranking with Theil-Sen Trend ───
        worst_zone = ""
        best_zone = ""
        zone_health = {}
        zone_trends = {}
        if zone_means:
            zone_health, worst_zone, best_zone, zone_trends = self._rank_zones_with_trend(zone_means)

        return SpatialMetrics(
            mean_spatial_var=mean_var,
            std_spatial_var=std_var,
            stability_class=stability_class,
            confidence=float(conf),
            morans_i=float(morans_i),
            morans_p=float(morans_p),
            morans_status=morans_status,
            spatial_trend=spatial_trend,
            spatial_trend_p=float(spatial_trend_p),
            worst_zone_id=worst_zone,
            best_zone_id=best_zone,
            zone_health_scores=zone_health,
            cusum_alarm=cusum_alarm,
            cusum_value=float(cusum_value),
            zone_trends=zone_trends,
        )

    # =====================================================================
    # CUSUM Control Chart (Page 1954)
    # =====================================================================

    @staticmethod
    def _cusum_chart(
        series: List[float],
        k: float = 0.5,
        h: float = 5.0,
        phase_variability: float = 0.0,
        n_season_observations: int = 0,
    ) -> Tuple[bool, float]:
        """Cumulative Sum (CUSUM) control chart for detecting persistent shifts.

        C⁺ₜ = max(0, C⁺ₜ₋₁ + (xₜ - μ) / σ - k_adaptive)
        Alarm when C⁺ₜ > h_adaptive

        v3.2 adaptive parameters:
            k_adaptive = k × (1 + 0.5 × phase_variability)
                → Higher variability phases (early season) get more slack
            h_adaptive = h × sqrt(n_observations / 30)
                → More data tightens the control limits

        phase_variability: 0.0-1.0 measure of HMM transition frequency
        n_season_observations: total observations this season for limit scaling

        Reference: Page (1954) "Continuous Inspection Schemes",
        Montgomery (2009) "Introduction to Statistical Quality Control"

        Returns:
            (alarm_triggered, final_cusum_value)
        """
        n = len(series)
        if n < 5:
            return False, 0.0

        mu = statistics.mean(series)
        sigma = statistics.stdev(series) if n > 2 else 0.01
        if sigma < 1e-6:
            return False, 0.0

        # v3.2: Adaptive parameters
        k_adaptive = k * (1.0 + 0.5 * phase_variability)
        if n_season_observations > 0:
            h_adaptive = h * math.sqrt(n_season_observations / 30.0)
        else:
            h_adaptive = h

        # Clamp to reasonable bounds
        k_adaptive = max(0.1, min(2.0, k_adaptive))
        h_adaptive = max(2.0, min(15.0, h_adaptive))

        # One-sided upper CUSUM (detects increases in spatial variance)
        c_plus = 0.0
        alarm = False

        for t in range(n):
            z = (series[t] - mu) / sigma
            c_plus = max(0.0, c_plus + z - k_adaptive)
            if c_plus > h_adaptive:
                alarm = True

        return alarm, c_plus

    @staticmethod
    def estimate_phase_variability(
        stage_sequence: List[str],
    ) -> float:
        """Estimate phase variability from HMM stage transitions.

        Counts the number of stage transitions relative to total timesteps.
        High transition frequency = high variability = early/unstable season.

        Returns:
            Float in [0.0, 1.0] where 1.0 = maximum variability.
        """
        if len(stage_sequence) < 2:
            return 0.0

        transitions = sum(
            1 for i in range(1, len(stage_sequence))
            if stage_sequence[i] != stage_sequence[i - 1]
        )

        # Normalize: >5 transitions in 30 timesteps = high variability
        return min(1.0, transitions / max(1, len(stage_sequence) * 0.15))

    # =====================================================================
    # Moran's I (Global Spatial Autocorrelation)
    # =====================================================================

    def _compute_morans_i(
        self,
        zone_means: Dict[str, List[float]],
        n_permutations: int = 99,
        zone_adjacency: Optional[Dict[str, List[str]]] = None,
        zone_centroids: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> Tuple[float, float, str]:
        """Compute Global Moran's I for the latest timestep.

        I = (n / W) × Σᵢ Σⱼ wᵢⱼ(xᵢ - x̄)(xⱼ - x̄) / Σᵢ(xᵢ - x̄)²

        Scientific Invariant:
          - Requires explicit zone_adjacency or physical zone_centroids (x, y).
          - If spatial geometry is unavailable, returns (0.0, 1.0, "UNAVAILABLE") rather than
            fabricating pseudo-topology from list/dictionary insertion order.
        """
        zone_ids = list(zone_means.keys())
        n = len(zone_ids)
        if n < 3 or (not zone_adjacency and not zone_centroids):
            return 0.0, 1.0, "UNAVAILABLE"

        # Get latest timestep values
        values = []
        for zid in zone_ids:
            ts = zone_means[zid]
            if ts:
                last_vals = [v for v in ts[-5:] if v is not None and not math.isnan(v)]
                values.append(statistics.mean(last_vals) if last_vals else 0.0)
            else:
                values.append(0.0)

        x_mean = statistics.mean(values)
        deviations = [v - x_mean for v in values]
        ss = sum(d * d for d in deviations)

        if ss < 1e-10:
            return 0.0, 1.0, "UNAVAILABLE"

        zone_id_to_idx = {zid: idx for idx, zid in enumerate(zone_ids)}
        w_matrix = [[0.0] * n for _ in range(n)]

        if zone_adjacency:
            # Use explicit adjacency graph
            for zid, neighbors in zone_adjacency.items():
                i = zone_id_to_idx.get(zid)
                if i is None:
                    continue
                for nid in neighbors:
                    j = zone_id_to_idx.get(nid)
                    if j is not None and i != j:
                        w_matrix[i][j] = 1.0
                        w_matrix[j][i] = 1.0
        elif zone_centroids:
            # Check that all zones have real physical geometry (no fabricated (0,0) default origin)
            missing_geom = [zid for zid in zone_ids if zid not in zone_centroids]
            if missing_geom:
                valid_zids = [zid for zid in zone_ids if zid in zone_centroids]
                if len(valid_zids) < 3:
                    return 0.0, 1.0, "UNAVAILABLE"
                zone_ids = valid_zids
                n = len(zone_ids)
                zone_id_to_idx = {zid: idx for idx, zid in enumerate(zone_ids)}
                w_matrix = [[0.0] * n for _ in range(n)]
                values = []
                for zid in zone_ids:
                    ts = zone_means[zid]
                    if ts:
                        last_vals = [v for v in ts[-5:] if v is not None and not math.isnan(v)]
                        values.append(statistics.mean(last_vals) if last_vals else 0.0)
                    else:
                        values.append(0.0)
                x_mean = statistics.mean(values)
                deviations = [v - x_mean for v in values]
                ss = sum(d * d for d in deviations)
                if ss < 1e-10:
                    return 0.0, 1.0, "UNAVAILABLE"

            coords = [
                (float(zone_centroids[zid][0]), float(zone_centroids[zid][1]))
                for zid in zone_ids
            ]
            k = min(2, n - 1)
            for i in range(n):
                dists = []
                for j in range(n):
                    if i != j:
                        d = math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])
                        dists.append((d, j))
                dists.sort()
                for _, j in dists[:k]:
                    w_matrix[i][j] = 1.0
                    w_matrix[j][i] = 1.0
        else:
            # Spatial geometry unavailable: forbid fabricating topology from container order
            return 0.0, 1.0, "UNAVAILABLE"

        # Compute total weight W
        W = sum(w_matrix[i][j] for i in range(n) for j in range(n))
        if W < 1e-10:
            return 0.0, 1.0, "UNAVAILABLE"

        # Compute Moran's I with proper weights
        cross_sum = 0.0
        for i in range(n):
            for j in range(n):
                if w_matrix[i][j] > 0:
                    cross_sum += w_matrix[i][j] * deviations[i] * deviations[j]

        observed_i = (n / W) * cross_sum / ss

        # Pseudo-significance via permutation
        import random as _rng
        rng = _rng.Random(42)
        count_extreme = 0
        for _ in range(n_permutations):
            perm = list(deviations)
            rng.shuffle(perm)
            perm_cross = 0.0
            for i in range(n):
                for j in range(n):
                    if w_matrix[i][j] > 0:
                        perm_cross += w_matrix[i][j] * perm[i] * perm[j]
            perm_i = (n / W) * perm_cross / ss
            if abs(perm_i) >= abs(observed_i):
                count_extreme += 1

        p_value = (count_extreme + 1) / (n_permutations + 1)

        return observed_i, p_value, "AVAILABLE"

    # =====================================================================
    # Mann-Kendall Trend Test
    # =====================================================================

    @staticmethod
    def _mann_kendall(series: List[float]) -> Tuple[float, float, str]:
        """Non-parametric Mann-Kendall trend test.

        Returns:
            (S statistic, p-value, trend direction: INCREASING/STABLE/DECREASING)
        """
        n = len(series)
        if n < 4:
            return 0.0, 1.0, "STABLE"

        # Compute S statistic
        S = 0
        for i in range(n - 1):
            for j in range(i + 1, n):
                diff = series[j] - series[i]
                if diff > 0:
                    S += 1
                elif diff < 0:
                    S -= 1

        # Variance of S (without ties for simplicity)
        var_s = n * (n - 1) * (2 * n + 5) / 18.0

        # Z-score (normal approximation)
        if S > 0:
            z = (S - 1) / math.sqrt(var_s) if var_s > 0 else 0.0
        elif S < 0:
            z = (S + 1) / math.sqrt(var_s) if var_s > 0 else 0.0
        else:
            z = 0.0

        # Two-tailed p-value (normal approximation)
        p_value = 2.0 * (1.0 - _normal_cdf(abs(z)))

        # Direction
        if p_value < 0.10:
            trend = "INCREASING" if S > 0 else "DECREASING"
        else:
            trend = "STABLE"

        return float(S), float(p_value), trend

    # =====================================================================
    # Theil-Sen Slope Estimator
    # =====================================================================

    @staticmethod
    def _theil_sen_slope(series: List[float]) -> float:
        """Robust slope estimator: median of all pairwise slopes.

        Theil (1950), Sen (1968). Breakdown point = 29.3%.
        Much more robust to outliers than OLS.
        """
        n = len(series)
        if n < 3:
            return 0.0

        slopes = []
        for i in range(n - 1):
            for j in range(i + 1, n):
                if j != i:
                    slopes.append((series[j] - series[i]) / (j - i))

        if not slopes:
            return 0.0

        slopes.sort()
        return slopes[len(slopes) // 2]

    # =====================================================================
    # Zone Health Ranking with Theil-Sen Trend (v3.1)
    # =====================================================================

    @staticmethod
    def _rank_zones_with_trend(
        zone_means: Dict[str, List[float]],
    ) -> Tuple[Dict[str, float], str, str, Dict[str, str]]:
        """Rank zones by recent NDVI health + trend direction.

        Uses Theil-Sen slope to identify zones that are deteriorating
        vs improving over time.

        Returns:
            (zone_health_scores, worst_zone_id, best_zone_id, zone_trends)
        """
        zone_scores = {}
        zone_trends = {}

        for zid, ts in zone_means.items():
            if not ts:
                zone_scores[zid] = 0.0
                zone_trends[zid] = "STABLE"
                continue

            # Use last 10 timesteps for health
            recent = [v for v in ts[-10:] if v is not None and not math.isnan(v)]
            zone_scores[zid] = statistics.mean(recent) if recent else 0.0

            # Theil-Sen slope for trend
            if len(recent) >= 3:
                slopes = []
                for i in range(len(recent) - 1):
                    for j in range(i + 1, len(recent)):
                        slopes.append((recent[j] - recent[i]) / (j - i))
                if slopes:
                    slopes.sort()
                    median_slope = slopes[len(slopes) // 2]
                    if median_slope > 0.003:
                        zone_trends[zid] = "IMPROVING"
                    elif median_slope < -0.003:
                        zone_trends[zid] = "DECLINING"
                    else:
                        zone_trends[zid] = "STABLE"
                else:
                    zone_trends[zid] = "STABLE"
            else:
                zone_trends[zid] = "STABLE"

        if not zone_scores:
            return {}, "", "", {}

        # Normalize to [0, 1] relative to best/worst zone
        vals = list(zone_scores.values())
        v_min = min(vals)
        v_max = max(vals)
        v_range = v_max - v_min if v_max > v_min else 0.1

        normalized = {}
        for zid, score in zone_scores.items():
            normalized[zid] = round((score - v_min) / v_range, 3)

        worst = min(zone_scores, key=zone_scores.get)
        best = max(zone_scores, key=zone_scores.get)

        return normalized, worst, best, zone_trends


# Backward-compatible alias
SpatialProxyStabilityEngine = SpatialAnalysisEngine


# =========================================================================
# Utility
# =========================================================================

def _normal_cdf(x: float) -> float:
    """Approximate CDF of standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

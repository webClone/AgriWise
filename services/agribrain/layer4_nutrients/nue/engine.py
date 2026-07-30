"""
Layer 4.11: Nutrient Use Efficiency (NUE) Tracking Engine.

Tracks and computes NUE metrics for season-over-season feedback:
  - AE (Agronomic Efficiency): ΔYield / ΔN_applied
  - RE (Recovery Efficiency): ΔN_uptake / ΔN_applied
  - PFP (Partial Factor Productivity): Yield / N_applied
  - IE (Internal Efficiency): Yield / N_uptake

These metrics enable calibration of response curves and identification
of diminishing returns from fertilizer investment.

All NUE benchmarks and grain N% are sourced from the centralized
crop_database (209+ crops).  Per-crop values exist for corn, wheat,
rice, soybean, potato, tomato, citrus, olive, cotton.  All other crops
inherit from their architecture class (cereal, legume, vegetable, etc.).

Science:
  - NUE improvement is the #1 lever for sustainable intensification
  - Low NUE = waste, environmental loss, profit erosion
  - High NUE requires: right rate, right timing, right source, right place (4R)

Season feedback loop:
  1. Pre-season: recommend N rate based on response curve
  2. In-season: monitor NDVI response to application
  3. Post-season: actual yield + N applied → compute NUE
  4. Update: Bayesian update of response curve parameters

References:
  - Dobermann (2007): Nutrient use efficiency - measurement and management,
    IFA Workshop on Fertilizer Best Management Practices
  - Cassman et al. (2002): Agroecosystems, nitrogen-use efficiency,
    and nitrogen management, AMBIO
  - Snyder et al. (2014): 4R Nutrient Stewardship for Improved
    Nutrient Use Efficiency, Agronomy Journal
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from crop_database import get_crop


@dataclass
class NUEMetrics:
    """Nutrient Use Efficiency metrics for one season."""
    # Computed metrics
    ae_kg_per_kg: float = 0.0      # Agronomic Efficiency
    re_fraction: float = 0.0       # Recovery Efficiency
    pfp_kg_per_kg: float = 0.0     # Partial Factor Productivity
    ie_kg_per_kg: float = 0.0      # Internal Efficiency

    # Inputs used for computation
    actual_yield_t_ha: float = 0.0
    control_yield_t_ha: float = 0.0  # Unfertilized control (estimated)
    n_applied_kg_ha: float = 0.0
    n_uptake_kg_ha: float = 0.0      # Estimated from yield × grain N%

    # Quality
    data_quality: str = "estimated"  # "measured", "estimated", "projected"
    confidence: float = 0.5

    # Benchmarks
    ae_benchmark_min: float = 0.0
    ae_benchmark_max: float = 0.0
    pfp_benchmark_min: float = 0.0
    pfp_benchmark_max: float = 0.0
    rating: str = ""  # "excellent", "good", "fair", "poor"

    notes: str = ""


@dataclass
class ResponseCurveUpdate:
    """Bayesian update for response curve parameters."""
    original_ymax: float = 0.0
    updated_ymax: float = 0.0
    original_c: float = 0.0
    updated_c: float = 0.0
    learning_rate: float = 0.10
    n_seasons: int = 0
    notes: str = ""


@dataclass
class NUEOutput:
    """Full NUE tracking output."""
    current_season: NUEMetrics = field(default_factory=NUEMetrics)
    historical: List[NUEMetrics] = field(default_factory=list)
    trend: str = ""  # "improving", "stable", "declining"
    response_update: Optional[ResponseCurveUpdate] = None
    recommendations: List[str] = field(default_factory=list)


class NUEEngine:
    """Tracks nutrient use efficiency and provides season feedback.

    This engine closes the feedback loop between recommendations and
    outcomes. Without NUE tracking, response curves can drift from
    reality, leading to systematic over- or under-application.

    All benchmarks sourced from crop_database (209+ crops).
    """

    def compute_nue(
        self,
        crop_type: str,
        actual_yield_t_ha: float,
        n_applied_kg_ha: float,
        n_uptake_kg_ha: Optional[float] = None,
        control_yield_t_ha: Optional[float] = None,
        historical: Optional[List[Dict]] = None,
    ) -> NUEOutput:
        """Compute NUE metrics for the current season.

        Args:
            crop_type: Crop type for benchmark lookup (any of 209+ crops)
            actual_yield_t_ha: Actual harvested yield (t/ha)
            n_applied_kg_ha: Total N applied (kg/ha)
            n_uptake_kg_ha: N uptake (kg/ha), estimated from yield if None
            control_yield_t_ha: Unfertilized control yield (estimated if None)
            historical: Past season NUE records [{ae, pfp, re, yield, n_applied}]
        """
        spec = get_crop(crop_type)

        # Read benchmarks from crop_database
        ae_range = spec.nue_ae_range        # (min, max) kg grain / kg N
        pfp_range = spec.nue_pfp_range      # (min, max) kg grain / kg N
        grain_n_pct = spec.grain_n_pct      # % N in grain/product

        # Estimate N uptake from yield if not provided
        if n_uptake_kg_ha is None:
            # N uptake ≈ yield × 1000 × grain_N%/100
            n_uptake_kg_ha = actual_yield_t_ha * 1000.0 * grain_n_pct / 100.0
            data_quality = "estimated"
        else:
            data_quality = "measured"

        # Estimate control yield (unfertilized) if not provided
        if control_yield_t_ha is None:
            # Rough estimate: 40-60% of fertilized yield depending on soil
            control_yield_t_ha = actual_yield_t_ha * 0.50
            data_quality = "estimated"

        # Compute metrics
        yield_kg_ha = actual_yield_t_ha * 1000.0
        control_kg_ha = control_yield_t_ha * 1000.0

        # AE = (Yield_f - Yield_0) / N_applied
        ae = 0.0
        if n_applied_kg_ha > 0:
            ae = (yield_kg_ha - control_kg_ha) / n_applied_kg_ha

        # RE = (N_uptake_f - N_uptake_0) / N_applied
        re = 0.0
        if n_applied_kg_ha > 0:
            n_uptake_control = control_yield_t_ha * 1000.0 * grain_n_pct / 100.0
            re = (n_uptake_kg_ha - n_uptake_control) / n_applied_kg_ha
            re = max(0.0, min(1.0, re))

        # PFP = Yield / N_applied
        pfp = yield_kg_ha / max(1.0, n_applied_kg_ha)

        # IE = Yield / N_uptake
        ie = yield_kg_ha / max(1.0, n_uptake_kg_ha)

        # Rating
        ae_min, ae_max = ae_range
        pfp_min, pfp_max = pfp_range
        if ae >= ae_max and pfp >= pfp_max:
            rating = "excellent"
        elif ae >= ae_min and pfp >= pfp_min:
            rating = "good"
        elif ae >= ae_min * 0.7:
            rating = "fair"
        else:
            rating = "poor"

        # Confidence
        conf = 0.70 if data_quality == "estimated" else 0.90

        metrics = NUEMetrics(
            ae_kg_per_kg=round(ae, 1),
            re_fraction=round(re, 3),
            pfp_kg_per_kg=round(pfp, 1),
            ie_kg_per_kg=round(ie, 1),
            actual_yield_t_ha=round(actual_yield_t_ha, 2),
            control_yield_t_ha=round(control_yield_t_ha, 2),
            n_applied_kg_ha=round(n_applied_kg_ha, 1),
            n_uptake_kg_ha=round(n_uptake_kg_ha, 1),
            data_quality=data_quality,
            confidence=conf,
            ae_benchmark_min=ae_min,
            ae_benchmark_max=ae_max,
            pfp_benchmark_min=pfp_min,
            pfp_benchmark_max=pfp_max,
            rating=rating,
            notes=f"AE={ae:.1f} (benchmark {ae_min}-{ae_max}), "
                  f"PFP={pfp:.1f} (benchmark {pfp_min}-{pfp_max}), "
                  f"Rating: {rating}",
        )

        # Process historical data
        hist_metrics = []
        if historical:
            for h in historical:
                hist_metrics.append(NUEMetrics(
                    ae_kg_per_kg=h.get("ae", 0),
                    pfp_kg_per_kg=h.get("pfp", 0),
                    re_fraction=h.get("re", 0),
                    actual_yield_t_ha=h.get("yield", 0),
                    n_applied_kg_ha=h.get("n_applied", 0),
                ))

        # Trend analysis
        trend = "stable"
        if hist_metrics and len(hist_metrics) >= 2:
            recent_ae = [m.ae_kg_per_kg for m in hist_metrics[-3:]]
            if all(recent_ae[i] < recent_ae[i+1] for i in range(len(recent_ae)-1)):
                trend = "improving"
            elif all(recent_ae[i] > recent_ae[i+1] for i in range(len(recent_ae)-1)):
                trend = "declining"

        # Response curve update (Bayesian)
        response_update = self._update_response_curve(
            spec, actual_yield_t_ha, n_applied_kg_ha, hist_metrics)

        # Recommendations
        recs = self._generate_recommendations(metrics, trend, spec.code)

        return NUEOutput(
            current_season=metrics,
            historical=hist_metrics,
            trend=trend,
            response_update=response_update,
            recommendations=recs,
        )

    def _update_response_curve(
        self,
        spec,
        yield_t_ha: float,
        n_applied: float,
        historical: List[NUEMetrics],
    ) -> Optional[ResponseCurveUpdate]:
        """Bayesian update of Mitscherlich response curve parameters.

        Uses the most recent observed (N_applied, Yield) point to
        nudge Ymax and curvature parameter c toward reality.

        Update rule (exponential smoothing):
          Ymax_new = (1-α) × Ymax_old + α × Ymax_observed
          c_new = (1-α) × c_old + α × c_observed
        """
        if n_applied <= 0 or yield_t_ha <= 0:
            return None

        # Get default response params from crop spec
        old_ymax = spec.response_a_max
        old_c = spec.response_c_rate
        old_b = spec.response_n_soil_default

        # Observed Ymax estimate (extrapolate from single point)
        # If yield = Ymax × (1-exp(-c×(N+b))), then at observed N:
        # Ymax_obs ≈ yield / (1-exp(-c×(N+b)))
        exponent = old_c * (n_applied + old_b)
        if exponent > 20:
            ymax_obs = yield_t_ha  # Already at plateau
        else:
            frac = 1.0 - math.exp(-exponent)
            ymax_obs = yield_t_ha / max(0.1, frac)

        # Learning rate decreases with more data points
        n_seasons = len(historical) + 1
        alpha = max(0.05, 0.30 / (1 + 0.2 * n_seasons))

        # Bayesian update
        new_ymax = (1.0 - alpha) * old_ymax + alpha * ymax_obs
        new_ymax = max(old_ymax * 0.7, min(old_ymax * 1.3, new_ymax))  # Clamp ±30%

        # C parameter: harder to estimate from single point
        # Use yield/N ratio as proxy
        if n_applied > 30:
            observed_efficiency = yield_t_ha / n_applied
            expected_efficiency = old_ymax / max(1, n_applied)
            efficiency_ratio = observed_efficiency / max(0.01, expected_efficiency)
            # If actual efficiency < expected, c might be lower
            new_c = old_c * max(0.8, min(1.2, efficiency_ratio))
        else:
            new_c = old_c

        return ResponseCurveUpdate(
            original_ymax=round(old_ymax, 2),
            updated_ymax=round(new_ymax, 2),
            original_c=round(old_c, 5),
            updated_c=round(new_c, 5),
            learning_rate=round(alpha, 3),
            n_seasons=n_seasons,
            notes=f"Ymax: {old_ymax:.1f} → {new_ymax:.1f} (α={alpha:.3f}), "
                  f"c: {old_c:.4f} → {new_c:.4f}",
        )

    def _generate_recommendations(
        self, metrics: NUEMetrics, trend: str, crop_type: str,
    ) -> List[str]:
        """Generate NUE improvement recommendations."""
        recs = []

        if metrics.rating == "poor":
            if metrics.ae_kg_per_kg < metrics.ae_benchmark_min * 0.5:
                recs.append(
                    "Agronomic Efficiency is very low. Consider: "
                    "(1) Split application to match crop demand timing, "
                    "(2) Switch from broadcast to banded/side-dress, "
                    "(3) Use enhanced-efficiency fertilizers (polymer-coated urea)."
                )
            if metrics.pfp_kg_per_kg < metrics.pfp_benchmark_min:
                recs.append(
                    "Partial Factor Productivity below benchmark. "
                    "Consider reducing total N rate — diminishing returns likely."
                )

        if metrics.re_fraction < 0.25:
            recs.append(
                "N recovery < 25%: significant N loss occurring. "
                "Check for: excessive leaching (sandy soils), denitrification "
                "(waterlogged), or volatilization (surface urea on alkaline soils)."
            )

        if trend == "declining":
            recs.append(
                "NUE trend is declining over recent seasons. "
                "Possible causes: soil degradation, increasing pest pressure, "
                "or response curve saturation."
            )

        if metrics.rating in ("excellent", "good") and trend != "declining":
            recs.append(
                f"NUE is {metrics.rating} (AE={metrics.ae_kg_per_kg:.0f}, "
                f"PFP={metrics.pfp_kg_per_kg:.0f}). "
                f"Current management is efficient."
            )

        return recs

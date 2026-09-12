"""
Adaptive TTL Engine — Context-aware dynamic TTL adjustment.

Replaces hardcoded per-plot TTL overrides with a smart algorithm:

    TTL = base_ttl × volatility × activity × season × anomaly

All factors are clamped to [0.3, 3.0] to prevent extreme values.
The final TTL is clamped to [source.min, source.max].

Usage:
    from services.agribrain.layer0.data_gateway.adaptive_ttl import AdaptiveTTLEngine
    
    engine = AdaptiveTTLEngine()
    ttl = engine.compute_ttl("openweather_current", plot_id="abc", context={
        "phenology_stage": "flowering",
        "anomaly_score": 0.72,
        "anomaly_detected_at": datetime(2026, 5, 25, 12, 0),
    })
"""

from __future__ import annotations

import math
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from collections import defaultdict

from services.agribrain.layer0.data_gateway.ttl_registry import get_source_config, SourceTTLConfig

logger = logging.getLogger("agribrain.adaptive_ttl")

# ── Factor Bounds ──────────────────────────────────────────────────────
FACTOR_MIN = 0.3
FACTOR_MAX = 3.0


def _clamp_factor(value: float) -> float:
    """Clamp a factor to [FACTOR_MIN, FACTOR_MAX]."""
    return max(FACTOR_MIN, min(FACTOR_MAX, value))


# ── Phenology Stage → Season Factor ───────────────────────────────────
# Critical growth stages get shorter TTLs (more frequent refresh)
PHENOLOGY_SEASON_FACTORS = {
    "dormant":      2.0,   # Relaxed — plant is inactive
    "germination":  0.8,   # Important — monitoring emergence
    "vegetative":   1.0,   # Normal
    "tillering":    0.9,   # Slightly elevated for cereals
    "flowering":    0.5,   # Critical — most sensitive stage
    "grain_fill":   0.6,   # Important — yield determination
    "ripening":     0.7,   # Moderate — monitoring maturity
    "senescence":   1.5,   # Relaxed — plant winding down
    "harvest":      1.2,   # Moderate
    "fallow":       2.5,   # Very relaxed — no active crop
    "unknown":      1.0,   # Default
}


class AdaptiveTTLEngine:
    """Context-aware dynamic TTL adjustment.

    Computes effective TTL by multiplying the base TTL from the registry
    with four context-dependent factors:

    1. Volatility Factor — how fast the variable is changing recently
    2. Activity Factor  — how often the user is accessing this plot
    3. Season Factor    — critical phenological windows need fresher data
    4. Anomaly Factor   — recent anomaly detection → aggressive refresh

    All factors are computed lazily and cached briefly to avoid
    re-computation on every cache check.
    """

    def __init__(self):
        # Access counters: {plot_id: [(timestamp, source), ...]}
        self._access_log: Dict[str, list] = defaultdict(list)
        # Volatility cache: {(plot_id, source): (timestamp, std, mean)}
        self._volatility_cache: Dict[tuple, tuple] = {}
        # Anomaly state: {plot_id: (score, detected_at)}
        self._anomaly_state: Dict[str, tuple] = {}
        # Plot overrides: {plot_id: {source: override_config}}
        self._plot_overrides: Dict[str, Dict[str, Dict]] = {}
        # Crop profile overrides: {crop_type: {param: value}}
        self._crop_profiles: Dict[str, Dict] = {}

    # ── Main Computation ───────────────────────────────────────────

    def compute_ttl(
        self,
        source: str,
        plot_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Compute the effective TTL for a source + plot combination.

        Args:
            source: Source identifier (e.g., "openweather_current")
            plot_id: Plot identifier (optional, for per-plot adaptation)
            context: Additional context signals:
                - phenology_stage: str (e.g., "flowering")
                - anomaly_score: float (0.0 - 1.0)
                - anomaly_detected_at: datetime
                - recent_values: list[float] (last 7 values for volatility)
                - crop_type: str (for crop-specific profiles)

        Returns:
            Effective TTL in seconds, clamped to [source.min, source.max]
        """
        config = get_source_config(source)
        ctx = context or {}

        # Check for per-plot override
        if plot_id and plot_id in self._plot_overrides:
            override = self._plot_overrides[plot_id].get(source)
            if override and "fixed_ttl" in override:
                return max(config.min, min(config.max, override["fixed_ttl"]))

        base = config.default

        # Compute factors
        f_volatility = self._volatility_factor(source, plot_id, ctx, config)
        f_activity = self._activity_factor(source, plot_id)
        f_season = self._season_factor(ctx)
        f_anomaly = self._anomaly_factor(plot_id, ctx)

        # Multiply
        effective = base * f_volatility * f_activity * f_season * f_anomaly

        # Clamp to source bounds
        result = max(config.min, min(config.max, int(effective)))

        logger.debug(
            "TTL %s/%s: base=%ds × vol=%.2f × act=%.2f × season=%.2f × anom=%.2f = %ds",
            source, plot_id or "global", base,
            f_volatility, f_activity, f_season, f_anomaly, result,
        )

        return result

    # ── Factor 1: Volatility ───────────────────────────────────────

    def _volatility_factor(
        self,
        source: str,
        plot_id: Optional[str],
        ctx: Dict,
        config: SourceTTLConfig,
    ) -> float:
        """Measure how fast the data is changing.

        High variance → shorter TTL (refresh more often).
        Computed from the last 7 values of the primary variable.

        For static sources (soil, elevation), always returns 1.0.
        """
        if config.volatility == "static":
            return 1.0

        recent = ctx.get("recent_values")
        if not recent or len(recent) < 3:
            # Not enough data — use volatility class defaults
            return {
                "high": 0.7,
                "medium": 1.0,
                "low": 1.3,
            }.get(config.volatility, 1.0)

        mean = sum(recent) / len(recent)
        if abs(mean) < 1e-6:
            return 1.0

        std = (sum((v - mean) ** 2 for v in recent) / len(recent)) ** 0.5
        cv = std / abs(mean)  # Coefficient of variation

        # Map CV to factor: high CV → lower factor (shorter TTL)
        # CV = 0.0 → factor 1.5 (very stable)
        # CV = 0.3 → factor 1.0 (normal)
        # CV = 1.0 → factor 0.5 (very volatile)
        factor = max(0.5, 1.5 - cv * 1.67)
        return _clamp_factor(factor)

    # ── Factor 2: Activity ─────────────────────────────────────────

    def _activity_factor(self, source: str, plot_id: Optional[str]) -> float:
        """How often the user accesses this plot.

        High activity → shorter TTL (user is watching).

        Based on access count in last 24 hours vs. historical average.
        """
        if not plot_id:
            return 1.0

        now = time.time()
        cutoff_24h = now - 86400
        cutoff_7d = now - 7 * 86400

        log = self._access_log.get(plot_id, [])

        # Count recent accesses
        recent_24h = sum(1 for ts, _ in log if ts > cutoff_24h)
        recent_7d = sum(1 for ts, _ in log if ts > cutoff_7d)

        if recent_7d < 7:
            # Not enough history — default factor
            return 1.0

        avg_daily = recent_7d / 7.0
        if avg_daily < 1:
            return 1.2  # Low activity — slightly longer TTL

        ratio = recent_24h / avg_daily

        # Map ratio to factor:
        # ratio = 0.5 → factor 1.3 (below average, relax)
        # ratio = 1.0 → factor 1.0 (normal)
        # ratio = 3.0 → factor 0.6 (3x average, user is watching)
        # ratio = 5.0 → factor 0.4 (very active)
        factor = max(0.4, 1.3 - 0.3 * math.log2(max(1, ratio)))
        return _clamp_factor(factor)

    # ── Factor 3: Season ───────────────────────────────────────────

    def _season_factor(self, ctx: Dict) -> float:
        """Critical phenological windows need fresher data.

        Flowering gets shortest TTL (most sensitive stage).
        Dormant/fallow gets longest (plant is inactive).
        """
        stage = ctx.get("phenology_stage", "unknown")

        # Check crop profile overrides
        crop_type = ctx.get("crop_type")
        if crop_type and crop_type in self._crop_profiles:
            profile = self._crop_profiles[crop_type]
            season_overrides = profile.get("season_factors", {})
            if stage in season_overrides:
                return _clamp_factor(season_overrides[stage])

        factor = PHENOLOGY_SEASON_FACTORS.get(stage, 1.0)
        return _clamp_factor(factor)

    # ── Factor 4: Anomaly ──────────────────────────────────────────

    def _anomaly_factor(self, plot_id: Optional[str], ctx: Dict) -> float:
        """Recent anomaly → aggressive refresh for 24 hours.

        If anomaly_score > 0.6 was detected in the last 24h:
          factor = 0.3 (decaying back to 1.0 over 24 hours)

        This ensures that during critical events (frost, flooding,
        pest outbreak), the system refreshes data aggressively.
        """
        # Check context for new anomaly
        anomaly_score = ctx.get("anomaly_score", 0.0)
        anomaly_at = ctx.get("anomaly_detected_at")

        if anomaly_score > 0.6 and anomaly_at:
            if plot_id:
                self._anomaly_state[plot_id] = (anomaly_score, anomaly_at)

        # Check stored anomaly state
        if not plot_id or plot_id not in self._anomaly_state:
            return 1.0

        score, detected_at = self._anomaly_state[plot_id]
        if score <= 0.6:
            return 1.0

        # Calculate time since anomaly
        now = datetime.now(timezone.utc)
        if isinstance(detected_at, datetime):
            if detected_at.tzinfo is None:
                detected_at = detected_at.replace(tzinfo=timezone.utc)
            elapsed = (now - detected_at).total_seconds()
        else:
            return 1.0

        if elapsed > 86400:
            # Anomaly expired (>24 hours ago) — clean up
            del self._anomaly_state[plot_id]
            return 1.0

        # Decay from 0.3 back to 1.0 over 24 hours
        # factor(t) = 0.3 + 0.7 × (t / 86400)
        decay_progress = elapsed / 86400.0
        factor = 0.3 + 0.7 * decay_progress

        return _clamp_factor(factor)

    # ── Access Tracking ────────────────────────────────────────────

    def record_access(self, plot_id: str, source: str):
        """Record a data access for activity factor computation."""
        now = time.time()
        log = self._access_log[plot_id]
        log.append((now, source))

        # Trim old entries (keep last 7 days)
        cutoff = now - 7 * 86400
        self._access_log[plot_id] = [(ts, s) for ts, s in log if ts > cutoff]

    # ── Anomaly Reporting ──────────────────────────────────────────

    def report_anomaly(self, plot_id: str, score: float):
        """Report an anomaly detection for a plot.

        Called by Pattern 2 (Anomaly-Gated Refresh) when the EO
        Foundation Model detects anomaly_score > 0.6.
        """
        if score > 0.6:
            self._anomaly_state[plot_id] = (score, datetime.now(timezone.utc))
            logger.info(
                "Anomaly reported for plot %s (score=%.2f) — TTL factor set to 0.3 for 24h",
                plot_id[:8] if plot_id else "?", score,
            )

    # ── Admin: Override Management ─────────────────────────────────

    def set_plot_override(self, plot_id: str, source: str, overrides: Dict):
        """Set per-plot TTL override.

        Example: greenhouse with 5-min sensor data:
            engine.set_plot_override("abc", "openweather_current", {"fixed_ttl": 300})
        """
        if plot_id not in self._plot_overrides:
            self._plot_overrides[plot_id] = {}
        self._plot_overrides[plot_id][source] = overrides
        logger.info("Plot override set: %s/%s → %s", plot_id[:8], source, overrides)

    def set_crop_profile(self, crop_type: str, profile: Dict):
        """Set per-crop-type TTL profile.

        Example: citrus needs more monitoring during fruit set:
            engine.set_crop_profile("citrus", {
                "season_factors": {"flowering": 0.3, "fruit_set": 0.4}
            })
        """
        self._crop_profiles[crop_type] = profile
        logger.info("Crop profile set: %s → %s", crop_type, list(profile.keys()))

    def clear_anomaly(self, plot_id: str):
        """Manually clear anomaly state for a plot."""
        self._anomaly_state.pop(plot_id, None)

    # ── Diagnostics ────────────────────────────────────────────────

    def get_factor_breakdown(
        self,
        source: str,
        plot_id: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Return detailed factor breakdown for debugging/admin dashboard."""
        config = get_source_config(source)
        ctx = context or {}

        f_vol = self._volatility_factor(source, plot_id, ctx, config)
        f_act = self._activity_factor(source, plot_id)
        f_sea = self._season_factor(ctx)
        f_ano = self._anomaly_factor(plot_id, ctx)
        effective = self.compute_ttl(source, plot_id, ctx)

        return {
            "source": source,
            "plot_id": plot_id,
            "base_ttl_seconds": config.default,
            "base_ttl_human": _human_ttl(config.default),
            "factors": {
                "volatility": round(f_vol, 3),
                "activity": round(f_act, 3),
                "season": round(f_sea, 3),
                "anomaly": round(f_ano, 3),
                "product": round(f_vol * f_act * f_sea * f_ano, 3),
            },
            "effective_ttl_seconds": effective,
            "effective_ttl_human": _human_ttl(effective),
            "bounds": {
                "min": config.min,
                "max": config.max,
                "min_human": _human_ttl(config.min),
                "max_human": _human_ttl(config.max),
            },
            "context": {
                "phenology_stage": ctx.get("phenology_stage", "unknown"),
                "anomaly_score": ctx.get("anomaly_score", 0.0),
                "crop_type": ctx.get("crop_type"),
            },
        }


def _human_ttl(seconds: int) -> str:
    """Convert seconds to human-readable string."""
    if seconds >= 86400:
        days = seconds / 86400
        return f"{days:.0f}d" if days == int(days) else f"{days:.1f}d"
    if seconds >= 3600:
        hours = seconds / 3600
        return f"{hours:.0f}h" if hours == int(hours) else f"{hours:.1f}h"
    return f"{seconds // 60}min"

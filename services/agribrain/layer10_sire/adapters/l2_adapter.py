"""
L2 Adapter — Extract vegetation intelligence from VegIntOutput (v2 Temporal)
==============================================================================

Now extracts curve windowing (7-day back/forward), velocity trend classification,
and enhanced anomaly temporal context for 14-day awareness.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from services.agribrain.scientific_contracts.crop_phenology import (
    consume_canonical_phenology_output,
)


@dataclass
class L2VegData:
    """Normalized L2 vegetation extraction for Layer 10 (v2 — Temporal)."""
    # Curve data
    ndvi_fit: List[float] = field(default_factory=list)
    ndvi_fit_d1: List[float] = field(default_factory=list)   # velocity
    ndvi_fit_unc: List[float] = field(default_factory=list)   # uncertainty
    curve_rmse: float = 0.0
    obs_coverage: float = 0.0

    # === TEMPORAL CURVE WINDOW (14-day) ===
    ndvi_7d_back: List[float] = field(default_factory=list)      # Last 7 fitted NDVI values
    ndvi_7d_forward: List[float] = field(default_factory=list)   # Next 7 projected NDVI values
    velocity_7d_back: List[float] = field(default_factory=list)  # Last 7 velocity values
    velocity_7d_forward: List[float] = field(default_factory=list)  # Next 7 velocity values
    velocity_trend: str = "STABLE"                                # ACCELERATING / DECELERATING / STABLE
    ndvi_delta_7d: float = 0.0                                    # NDVI change over last 7 days
    ndvi_forecast_delta_7d: float = 0.0                           # Projected NDVI change next 7 days
    growth_momentum: float = 0.0                                  # Acceleration of growth rate

    # Phenology
    current_stage: str = "UNKNOWN"
    key_dates: Dict[str, str] = field(default_factory=dict)
    stage_progression: List[str] = field(default_factory=list)    # Last N stages observed
    phenology_authority: str = "unavailable"
    phenology_posterior_hash: str = ""
    phenology_receipt_valid: bool = False
    phenology_evidence_needed_reason: str = "canonical_layer2_phenology_receipt_required"

    # Spatial stability
    stability_class: str = "UNKNOWN"
    stability_confidence: float = 0.5
    mean_spatial_var: float = 0.0
    std_spatial_var: float = 0.0

    # Anomalies
    anomalies: List[Dict[str, Any]] = field(default_factory=list)

    # Zone-level metrics (if available)
    zone_metrics: Dict[str, Any] = field(default_factory=dict)

    run_id: str = ""


def _classify_velocity_trend(velocities: List[float]) -> str:
    """Classify velocity trend from a sequence of d1 values.

    Returns: ACCELERATING, DECELERATING, STABLE, or UNKNOWN.
    """
    if len(velocities) < 3:
        return "UNKNOWN"

    # Compute acceleration (d2) from velocity
    accels = [velocities[i+1] - velocities[i] for i in range(len(velocities)-1)]
    mean_accel = sum(accels) / len(accels) if accels else 0.0

    if mean_accel > 0.002:
        return "ACCELERATING"
    elif mean_accel < -0.002:
        return "DECELERATING"
    return "STABLE"


def _extrapolate_forward(ndvi_fit: List[float], d1: List[float], n: int = 7) -> List[float]:
    """Extrapolate NDVI forward N days using last fitted value and velocity.

    Uses a linear extrapolation with velocity decay to avoid unrealistic values.
    """
    if not ndvi_fit:
        return []

    last_val = ndvi_fit[-1]
    last_vel = d1[-1] if d1 else 0.0
    forward = []
    decay = 0.85  # Velocity decays each day to stay conservative

    for i in range(n):
        effective_vel = last_vel * (decay ** i)
        projected = last_val + effective_vel * (i + 1)
        # Clamp to valid NDVI range
        projected = max(-0.2, min(1.0, projected))
        forward.append(round(projected, 6))

    return forward


def adapt_l2(veg_int: Any) -> L2VegData:
    """Extract vegetation intelligence from VegIntOutput (v2 — Full Temporal)."""
    if veg_int is None:
        return L2VegData()

    if hasattr(veg_int, "veg_temporal"):
        temporal = veg_int.veg_temporal
    else:
        temporal = veg_int

    if temporal is None:
        return L2VegData()

    # Re-bind to veg_int to reuse downstream properties directly
    veg_int = temporal

    result = L2VegData(run_id=getattr(veg_int, 'run_id', ''))

    # Curve
    curve = getattr(veg_int, 'curve', None)
    if curve is not None:
        result.ndvi_fit = getattr(curve, 'ndvi_fit', [])
        result.ndvi_fit_d1 = getattr(curve, 'ndvi_fit_d1', [])
        result.ndvi_fit_unc = getattr(curve, 'ndvi_fit_unc', [])
        q = getattr(curve, 'quality', None)
        if q:
            result.curve_rmse = getattr(q, 'rmse', 0.0)
            result.obs_coverage = getattr(q, 'obs_coverage', 0.0)

        # --- Temporal Curve Windowing ---
        fit = result.ndvi_fit
        d1 = result.ndvi_fit_d1

        # Retrospective: last 7 values
        if fit:
            result.ndvi_7d_back = fit[-7:] if len(fit) >= 7 else list(fit)
            if len(result.ndvi_7d_back) >= 2:
                result.ndvi_delta_7d = round(
                    result.ndvi_7d_back[-1] - result.ndvi_7d_back[0], 6
                )

        if d1:
            result.velocity_7d_back = d1[-7:] if len(d1) >= 7 else list(d1)
            result.velocity_trend = _classify_velocity_trend(result.velocity_7d_back)

            # Growth momentum: acceleration of the acceleration
            if len(result.velocity_7d_back) >= 3:
                accels = [
                    result.velocity_7d_back[i+1] - result.velocity_7d_back[i]
                    for i in range(len(result.velocity_7d_back)-1)
                ]
                result.growth_momentum = round(sum(accels) / len(accels), 6)

        # Forward projection: extrapolate 7 days
        result.ndvi_7d_forward = _extrapolate_forward(fit, d1, n=7)
        if result.ndvi_7d_forward and fit:
            result.ndvi_forecast_delta_7d = round(
                result.ndvi_7d_forward[-1] - fit[-1], 6
            )

        # Forward velocity projection
        if d1:
            last_vel = d1[-1]
            decay = 0.85
            result.velocity_7d_forward = [
                round(last_vel * (decay ** i), 6) for i in range(7)
            ]

    # Phenology is single-owner: consume only the validated Layer-2 receipt.
    # Raw stage_by_day arrays are diagnostic internals, not publication authority.
    canonical_phenology = consume_canonical_phenology_output(veg_int)
    result.current_stage = canonical_phenology["resolved_crop_stage"]
    result.phenology_authority = canonical_phenology["phenology_authority"]
    result.phenology_posterior_hash = canonical_phenology["phenology_posterior_hash"]
    result.phenology_receipt_valid = canonical_phenology["phenology_receipt_valid"]
    result.phenology_evidence_needed_reason = canonical_phenology[
        "phenology_evidence_needed_reason"
    ]

    # Stability
    stab = getattr(veg_int, 'stability', None)
    if stab is not None:
        result.stability_class = getattr(stab, 'stability_class', 'UNKNOWN')
        result.stability_confidence = getattr(stab, 'confidence', 0.5)
        result.mean_spatial_var = getattr(stab, 'mean_spatial_var', 0.0)
        result.std_spatial_var = getattr(stab, 'std_spatial_var', 0.0)

    # Anomalies
    for anom in getattr(veg_int, 'anomalies', []):
        result.anomalies.append({
            'type': getattr(anom, 'type', 'UNKNOWN'),
            'severity': getattr(anom, 'severity', 0.0),
            'confidence': getattr(anom, 'confidence', 0.0),
            'description': getattr(anom, 'description', ''),
            'likely_cause': getattr(anom, 'likely_cause', 'UNKNOWN'),
        })

    # Zone metrics
    result.zone_metrics = getattr(veg_int, 'zone_metrics', {})

    return result

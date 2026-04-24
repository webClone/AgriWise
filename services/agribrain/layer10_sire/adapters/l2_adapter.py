"""
L2 Adapter — Extract vegetation intelligence from VegIntOutput
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class L2VegData:
    """Normalized L2 vegetation extraction for Layer 10."""
    # Curve data
    ndvi_fit: List[float] = field(default_factory=list)
    ndvi_fit_d1: List[float] = field(default_factory=list)   # velocity
    ndvi_fit_unc: List[float] = field(default_factory=list)   # uncertainty
    curve_rmse: float = 0.0
    obs_coverage: float = 0.0

    # Phenology
    current_stage: str = "UNKNOWN"
    key_dates: Dict[str, str] = field(default_factory=dict)

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


def adapt_l2(veg_int: Any) -> L2VegData:
    """Extract vegetation intelligence from VegIntOutput."""
    if veg_int is None:
        return L2VegData()

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

    # Phenology
    pheno = getattr(veg_int, 'phenology', None)
    if pheno is not None:
        stages = getattr(pheno, 'stage_by_day', [])
        if stages:
            result.current_stage = stages[-1]
        result.key_dates = getattr(pheno, 'key_dates', {})

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

"""
L3 Adapter — Extract diagnostic intelligence from DecisionOutput (v2 Temporal)
================================================================================

Now tracks diagnosis trend history (7-day severity progression), temporal
classification (WORSENING/IMPROVING/STABLE), and spatial hotspot evolution.
"""
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class L3DiagnosticData:
    """Normalized L3 diagnostic extraction for Layer 10 (v2 — Temporal)."""
    diagnoses: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    target_zones: List[str] = field(default_factory=list)
    degradation_mode: str = "NORMAL"
    decision_reliability: float = 1.0

    # === TEMPORAL DIAGNOSTIC CONTEXT ===
    # Diagnosis trend: problem_id → "WORSENING" / "IMPROVING" / "STABLE"
    diagnosis_trend: Dict[str, str] = field(default_factory=dict)
    # Severity history: problem_id → last N severity values (newest last)
    severity_history: Dict[str, List[float]] = field(default_factory=dict)
    # Hotspot evolution: problem_id → list of zone_id sets over time
    hotspot_evolution: Dict[str, List[List[str]]] = field(default_factory=dict)
    # Confidence trajectory: problem_id → confidence trend
    confidence_trajectory: Dict[str, str] = field(default_factory=dict)

    run_id: str = ""


def _classify_trend(values: List[float]) -> str:
    """Classify a time-ordered sequence of severity values as a trend."""
    if len(values) < 2:
        return "STABLE"

    # Simple linear trend from first-half mean to second-half mean
    mid = len(values) // 2
    first_mean = sum(values[:mid]) / mid if mid > 0 else 0
    second_mean = sum(values[mid:]) / (len(values) - mid) if (len(values) - mid) > 0 else 0
    delta = second_mean - first_mean

    if delta > 0.05:
        return "WORSENING"
    elif delta < -0.05:
        return "IMPROVING"
    return "STABLE"


def adapt_l3(decision: Any) -> L3DiagnosticData:
    """Extract diagnostic intelligence from DecisionOutput (v2 — Full Temporal)."""
    if decision is None:
        return L3DiagnosticData()

    result = L3DiagnosticData(run_id=getattr(decision, 'run_id_l3', ''))

    # Diagnoses with spatial fields
    for dx in getattr(decision, 'diagnoses', []):
        problem_id = getattr(dx, 'problem_id', '')
        severity = getattr(dx, 'severity', 0.0)
        confidence = getattr(dx, 'confidence', 0.0)
        hotspots = getattr(dx, 'hotspot_zone_ids', [])

        result.diagnoses.append({
            'problem_id': problem_id,
            'probability': getattr(dx, 'probability', 0.0),
            'severity': severity,
            'confidence': confidence,
            'affected_area_pct': getattr(dx, 'affected_area_pct', 100.0),
            'hotspot_zone_ids': hotspots,
            'drivers_used': [
                d.value if hasattr(d, 'value') else str(d)
                for d in getattr(dx, 'drivers_used', [])
            ],
        })

        # Build severity history from historical snapshots if available
        hist = getattr(dx, 'severity_history', None)
        if hist and isinstance(hist, list):
            result.severity_history[problem_id] = [
                float(v) for v in hist if isinstance(v, (int, float))
            ]
        else:
            # Single point — use current severity as the sole data point
            result.severity_history[problem_id] = [severity]

        # Trend classification
        if problem_id in result.severity_history:
            result.diagnosis_trend[problem_id] = _classify_trend(
                result.severity_history[problem_id]
            )
        else:
            result.diagnosis_trend[problem_id] = "STABLE"

        # Hotspot evolution
        hotspot_hist = getattr(dx, 'hotspot_history', None)
        if hotspot_hist and isinstance(hotspot_hist, list):
            result.hotspot_evolution[problem_id] = hotspot_hist
        elif hotspots:
            result.hotspot_evolution[problem_id] = [hotspots]

        # Confidence trajectory
        conf_hist = getattr(dx, 'confidence_history', None)
        if conf_hist and isinstance(conf_hist, list) and len(conf_hist) >= 2:
            result.confidence_trajectory[problem_id] = _classify_trend(conf_hist)
        else:
            result.confidence_trajectory[problem_id] = "STABLE"

    # Recommendations
    for rec in getattr(decision, 'recommendations', []):
        result.recommendations.append({
            'action_id': getattr(rec, 'action_id', ''),
            'action_type': getattr(rec, 'action_type', ''),
            'priority_score': getattr(rec, 'priority_score', 0.0),
            'urgency': getattr(rec, 'urgency', 0.0),
            'confidence': getattr(rec, 'confidence', 0.0),
            'is_allowed': getattr(rec, 'is_allowed', True),
        })

    # Execution plan target zones
    plan = getattr(decision, 'execution_plan', None)
    if plan:
        for task in getattr(plan, 'tasks', []):
            result.target_zones.extend(getattr(task, 'target_zones', []))

    # Quality
    qm = getattr(decision, 'quality_metrics', None)
    if qm:
        result.degradation_mode = getattr(
            getattr(qm, 'degradation_mode', None), 'value', 'NORMAL'
        )
        result.decision_reliability = getattr(qm, 'decision_reliability', 1.0)

    return result

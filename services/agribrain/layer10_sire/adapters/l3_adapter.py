"""
L3 Adapter — Extract diagnostic intelligence from DecisionOutput
"""
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class L3DiagnosticData:
    """Normalized L3 diagnostic extraction for Layer 10."""
    diagnoses: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    target_zones: List[str] = field(default_factory=list)
    degradation_mode: str = "NORMAL"
    decision_reliability: float = 1.0
    run_id: str = ""


def adapt_l3(decision: Any) -> L3DiagnosticData:
    """Extract diagnostic intelligence from DecisionOutput."""
    if decision is None:
        return L3DiagnosticData()

    result = L3DiagnosticData(run_id=getattr(decision, 'run_id_l3', ''))

    # Diagnoses with spatial fields
    for dx in getattr(decision, 'diagnoses', []):
        result.diagnoses.append({
            'problem_id': getattr(dx, 'problem_id', ''),
            'probability': getattr(dx, 'probability', 0.0),
            'severity': getattr(dx, 'severity', 0.0),
            'confidence': getattr(dx, 'confidence', 0.0),
            'affected_area_pct': getattr(dx, 'affected_area_pct', 100.0),
            'hotspot_zone_ids': getattr(dx, 'hotspot_zone_ids', []),
            'drivers_used': [
                d.value if hasattr(d, 'value') else str(d)
                for d in getattr(dx, 'drivers_used', [])
            ],
        })

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

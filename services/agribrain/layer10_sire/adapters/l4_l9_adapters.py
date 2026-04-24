"""
L4-L9 Adapters — Extract upstream layer outputs for Layer 10
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


# ===== L4 ADAPTER =====
@dataclass
class L4NutrientData:
    nutrient_states: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # {nutrient: {probability_deficient, confidence, ...}}
    zone_metrics: Dict[str, Any] = field(default_factory=dict)
    run_id: str = ""


def adapt_l4(nutrients: Any) -> L4NutrientData:
    if nutrients is None:
        return L4NutrientData()
    result = L4NutrientData()
    result.run_id = getattr(getattr(nutrients, 'run_meta', None), 'run_id', '')
    for key, state in getattr(nutrients, 'nutrient_states', {}).items():
        k = key.value if hasattr(key, 'value') else str(key)
        result.nutrient_states[k] = {
            'probability_deficient': getattr(state, 'probability_deficient', 0.0),
            'confidence': getattr(state, 'confidence', 1.0),
            'severity': getattr(state, 'severity', 'LOW'),
        }
    result.zone_metrics = getattr(nutrients, 'zone_metrics', {})
    return result


# ===== L5 ADAPTER =====
@dataclass
class L5BioData:
    threat_probs: Dict[str, float] = field(default_factory=dict)
    threat_spreads: Dict[str, str] = field(default_factory=dict)
    weather_pressure_score: float = 0.0
    run_id: str = ""


def adapt_l5(bio: Any) -> L5BioData:
    if bio is None:
        return L5BioData()
    result = L5BioData()
    result.run_id = getattr(getattr(bio, 'run_meta', None), 'run_id', '')
    for key, state in getattr(bio, 'threat_states', {}).items():
        result.threat_probs[key] = getattr(state, 'probability', 0.0)
        sp = getattr(state, 'spread_pattern', None)
        result.threat_spreads[key] = sp.value if hasattr(sp, 'value') else str(sp)
    wp = getattr(bio, 'weather_pressure', None)
    if wp:
        result.weather_pressure_score = getattr(
            wp, 'composite_score', getattr(wp, 'pressure', 0.0)
        )
    return result


# ===== L6 ADAPTER =====
@dataclass
class L6ExecData:
    execution_confidence: float = 1.0
    task_completion_rate: float = 0.0
    calibration_proposals: int = 0
    run_id: str = ""


def adapt_l6(exec_state: Any) -> L6ExecData:
    if exec_state is None:
        return L6ExecData()
    result = L6ExecData()
    result.run_id = getattr(getattr(exec_state, 'run_meta', None), 'run_id', '')
    qm = getattr(exec_state, 'quality_metrics', None)
    if qm:
        result.execution_confidence = getattr(qm, 'decision_reliability', 1.0)
        result.task_completion_rate = getattr(qm, 'task_completion_rate', 0.0)
    result.calibration_proposals = len(getattr(exec_state, 'calibration_proposals', []))
    return result


# ===== L7 ADAPTER =====
@dataclass
class L7PlanningData:
    crop: str = ""
    suitability_pct: float = 0.0
    yield_p10: float = 0.0
    yield_p50: float = 0.0
    yield_p90: float = 0.0
    profit_p50: float = 0.0
    run_id: str = ""


def adapt_l7(planning: Any) -> L7PlanningData:
    if planning is None:
        return L7PlanningData()
    result = L7PlanningData()
    result.run_id = getattr(planning, 'run_meta', {}).get('run_id', '') if isinstance(
        getattr(planning, 'run_meta', None), dict
    ) else ''
    options = getattr(planning, 'options', [])
    if options:
        best = options[0]
        result.crop = getattr(best, 'crop', '')
        result.suitability_pct = getattr(best, 'suitability_percentage', 0.0)
        yd = getattr(best, 'yield_dist', None)
        if yd:
            result.yield_p10 = getattr(yd, 'p10', 0.0)
            result.yield_p50 = getattr(yd, 'p50', 0.0)
            result.yield_p90 = getattr(yd, 'p90', 0.0)
        ec = getattr(best, 'econ', None)
        if ec:
            result.profit_p50 = getattr(ec, 'profit_p50', 0.0)
    return result


# ===== L8 ADAPTER =====
@dataclass
class L8ActionData:
    actions: List[Dict[str, Any]] = field(default_factory=list)
    zone_plan: List[Dict[str, Any]] = field(default_factory=list)
    yield_delta_pct: float = 0.0
    risk_reduction_pct: float = 0.0
    degradation_mode: str = "NORMAL"
    run_id: str = ""


def adapt_l8(prescriptive: Any) -> L8ActionData:
    if prescriptive is None:
        return L8ActionData()
    result = L8ActionData(run_id=getattr(prescriptive, 'run_id', ''))
    for act in getattr(prescriptive, 'actions', []):
        at = getattr(act, 'action_type', None)
        result.actions.append({
            'action_id': getattr(act, 'action_id', ''),
            'action_type': at.value if hasattr(at, 'value') else str(at),
            'priority_score': getattr(act, 'priority_score', 0.0),
            'is_allowed': getattr(act, 'is_allowed', True),
            'zone_targets': getattr(act, 'zone_targets', []),
            'confidence': getattr(
                getattr(act, 'confidence', None), 'value',
                str(getattr(act, 'confidence', 'MODERATE'))
            ),
        })
    for zp in getattr(prescriptive, 'zone_plan', []):
        result.zone_plan.append({
            'zone_id': getattr(zp, 'zone_id', ''),
            'actions': getattr(zp, 'actions', []),
            'allocation_fraction': getattr(zp, 'allocation_fraction', 0.0),
            'priority': getattr(zp, 'priority', ''),
        })
    oc = getattr(prescriptive, 'outcome_forecast', None)
    if oc:
        result.yield_delta_pct = getattr(oc, 'yield_delta_pct', 0.0)
        result.risk_reduction_pct = getattr(oc, 'risk_reduction_pct', 0.0)
    q = getattr(prescriptive, 'quality', None)
    if q:
        dm = getattr(q, 'degradation_mode', None)
        result.degradation_mode = dm.value if hasattr(dm, 'value') else str(dm)
    return result


# ===== L9 ADAPTER =====
@dataclass
class L9RenderData:
    badge_color: str = "GRAY"
    show_uncertainty: bool = False
    highlight_zones: List[str] = field(default_factory=list)
    phrasing_mode: str = "CONFIDENT"


def adapt_l9(interface: Any) -> L9RenderData:
    if interface is None:
        return L9RenderData()
    result = L9RenderData()
    rh = getattr(interface, 'render_hints', None)
    if rh:
        bc = getattr(rh, 'badge_color', None)
        result.badge_color = bc.value if hasattr(bc, 'value') else str(bc)
        result.show_uncertainty = getattr(rh, 'show_uncertainty_overlay', False)
        result.highlight_zones = getattr(rh, 'highlight_zones', [])
    pm = getattr(interface, 'phrasing_mode', None)
    result.phrasing_mode = pm.value if hasattr(pm, 'value') else str(pm)
    return result

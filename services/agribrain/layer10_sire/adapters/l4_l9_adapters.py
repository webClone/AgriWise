"""
L4-L9 Adapters — Extract upstream layer outputs for Layer 10 (v2 Temporal)
============================================================================

Enhanced with:
  - L6: Full intervention portfolio, conflict log, outcome projections
  - L7: Suitability states, planting window dates, yield trajectory
  - L8: Schedule extraction, intervention timing, zone allocation
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


# ===== L4 ADAPTER =====
@dataclass
class L4NutrientData:
    nutrient_states: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # {nutrient: {probability_deficient, confidence, ...}}
    zone_metrics: Dict[str, Any] = field(default_factory=dict)

    # === TEMPORAL NUTRIENT CONTEXT ===
    depletion_rates: Dict[str, float] = field(default_factory=dict)
    # nutrient → estimated daily depletion rate
    application_history: List[Dict[str, Any]] = field(default_factory=list)
    # Recent fertilizer applications with dates + amounts
    nutrient_trajectory: Dict[str, str] = field(default_factory=dict)
    # nutrient → "DEPLETING" / "STABLE" / "RECOVERING"

    run_id: str = ""


def adapt_l4(nutrients: Any) -> L4NutrientData:
    if nutrients is None:
        return L4NutrientData()
    result = L4NutrientData()
    result.run_id = getattr(getattr(nutrients, 'run_meta', None), 'run_id', '')
    for key, state in getattr(nutrients, 'nutrient_states', {}).items():
        k = key.value if hasattr(key, 'value') else str(key)
        prob_def = getattr(state, 'probability_deficient', 0.0)
        result.nutrient_states[k] = {
            'probability_deficient': prob_def,
            'confidence': getattr(state, 'confidence', 1.0),
            'severity': getattr(state, 'severity', 'LOW'),
        }
        # Derive trajectory from probability level
        if prob_def > 0.6:
            result.nutrient_trajectory[k] = "DEPLETING"
        elif prob_def > 0.3:
            result.nutrient_trajectory[k] = "STABLE"
        else:
            result.nutrient_trajectory[k] = "RECOVERING"

        # Extract depletion rate if available
        dep_rate = getattr(state, 'depletion_rate', None)
        if dep_rate and isinstance(dep_rate, (int, float)):
            result.depletion_rates[k] = float(dep_rate)

    result.zone_metrics = getattr(nutrients, 'zone_metrics', {})

    # Application history
    for app in getattr(nutrients, 'application_history', []):
        result.application_history.append({
            'date': getattr(app, 'date', ''),
            'nutrient': getattr(app, 'nutrient', ''),
            'amount_kg_ha': getattr(app, 'amount_kg_ha', 0.0),
        })

    return result


# ===== L5 ADAPTER =====
@dataclass
class L5BioData:
    threat_probs: Dict[str, float] = field(default_factory=dict)
    threat_spreads: Dict[str, str] = field(default_factory=dict)
    weather_pressure_score: float = 0.0

    # === TEMPORAL BIO CONTEXT ===
    threat_trajectory: Dict[str, str] = field(default_factory=dict)
    # threat_id → "EXPANDING" / "STABLE" / "CONTRACTING"
    spread_velocity: Dict[str, float] = field(default_factory=dict)
    # threat_id → estimated spread rate (% area/day)
    leaf_wetness_hours: float = 0.0
    disease_pressure_trend: str = "STABLE"
    # "INCREASING" / "STABLE" / "DECREASING"

    run_id: str = ""


def adapt_l5(bio: Any) -> L5BioData:
    if bio is None:
        return L5BioData()
    result = L5BioData()
    result.run_id = getattr(getattr(bio, 'run_meta', None), 'run_id', '')

    pressure_total = 0.0
    n_threats = 0
    for key, state in getattr(bio, 'threat_states', {}).items():
        prob = getattr(state, 'probability', 0.0)
        result.threat_probs[key] = prob
        sp = getattr(state, 'spread_pattern', None)
        spread_str = sp.value if hasattr(sp, 'value') else str(sp)
        result.threat_spreads[key] = spread_str

        # Classify trajectory from spread pattern
        if spread_str in ('EXPANDING', 'ACCELERATING'):
            result.threat_trajectory[key] = "EXPANDING"
        elif spread_str in ('CONTRACTING', 'RECEDING'):
            result.threat_trajectory[key] = "CONTRACTING"
        else:
            result.threat_trajectory[key] = "STABLE"

        # Extract spread velocity
        sv = getattr(state, 'spread_velocity', None)
        if sv and isinstance(sv, (int, float)):
            result.spread_velocity[key] = float(sv)

        pressure_total += prob
        n_threats += 1

    wp = getattr(bio, 'weather_pressure', None)
    if wp:
        result.weather_pressure_score = getattr(
            wp, 'composite_score', getattr(wp, 'pressure', 0.0)
        )
        result.leaf_wetness_hours = getattr(wp, 'leaf_wetness_hours', 0.0)

    # Disease pressure trend from overall threat level
    if n_threats > 0:
        avg_pressure = pressure_total / n_threats
        if avg_pressure > 0.5:
            result.disease_pressure_trend = "INCREASING"
        elif avg_pressure > 0.2:
            result.disease_pressure_trend = "STABLE"
        else:
            result.disease_pressure_trend = "DECREASING"

    return result


# ===== L6 ADAPTER (Enhanced) =====
@dataclass
class L6ExecData:
    """Normalized L6 execution intelligence for Layer 10 (v2 — Full)."""
    execution_confidence: float = 1.0
    task_completion_rate: float = 0.0
    calibration_proposals: int = 0

    # === FULL INTERVENTION PORTFOLIO ===
    interventions: List[Dict[str, Any]] = field(default_factory=list)
    # [{intervention_id, type, feasibility_grade, utility_score, zone_targets, ...}]
    conflict_log: List[Dict[str, Any]] = field(default_factory=list)
    # [{conflict_id, type, resolution, affected_zones}]
    outcome_projections: Dict[str, float] = field(default_factory=dict)
    # {metric: projected_value} e.g. {"yield_delta": +5.2, "risk_reduction": 12.0}
    blocked_zones: List[str] = field(default_factory=list)
    # Zone IDs where execution is blocked

    # Timing
    intervention_schedule: List[Dict[str, Any]] = field(default_factory=list)
    # [{intervention_id, start_date, end_date, zone_id, priority}]

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

    # Full intervention portfolio extraction
    portfolio = getattr(exec_state, 'intervention_portfolio', [])
    if not portfolio:
        portfolio = getattr(exec_state, 'interventions', [])
    for intv in portfolio:
        result.interventions.append({
            'intervention_id': getattr(intv, 'intervention_id', getattr(intv, 'id', '')),
            'type': getattr(intv, 'intervention_type', getattr(intv, 'type', '')),
            'feasibility_grade': getattr(intv, 'feasibility_grade', 'UNKNOWN'),
            'utility_score': getattr(intv, 'utility_score', 0.0),
            'zone_targets': getattr(intv, 'zone_targets', []),
            'priority': getattr(intv, 'priority', 'MEDIUM'),
            'timing_window': getattr(intv, 'timing_window', {}),
        })

    # Conflict log
    for conflict in getattr(exec_state, 'conflict_log', []):
        result.conflict_log.append({
            'conflict_id': getattr(conflict, 'conflict_id', ''),
            'type': getattr(conflict, 'conflict_type', ''),
            'resolution': getattr(conflict, 'resolution', 'UNRESOLVED'),
            'affected_zones': getattr(conflict, 'affected_zones', []),
        })

    # Outcome projections
    outcomes = getattr(exec_state, 'outcome_projections', None)
    if outcomes:
        if isinstance(outcomes, dict):
            result.outcome_projections = outcomes
        else:
            result.outcome_projections = {
                'yield_delta': getattr(outcomes, 'yield_delta', 0.0),
                'risk_reduction': getattr(outcomes, 'risk_reduction', 0.0),
                'cost_estimate': getattr(outcomes, 'cost_estimate', 0.0),
            }

    # Blocked zones
    result.blocked_zones = getattr(exec_state, 'blocked_zones', [])

    # Schedule
    schedule = getattr(exec_state, 'schedule', [])
    for entry in schedule:
        result.intervention_schedule.append({
            'intervention_id': getattr(entry, 'intervention_id', ''),
            'start_date': getattr(entry, 'start_date', ''),
            'end_date': getattr(entry, 'end_date', ''),
            'zone_id': getattr(entry, 'zone_id', ''),
            'priority': getattr(entry, 'priority', 'MEDIUM'),
        })

    return result


# ===== L7 ADAPTER (Enhanced) =====
@dataclass
class L7PlanningData:
    """Normalized L7 planning intelligence for Layer 10 (v2 — Temporal)."""
    crop: str = ""
    suitability_pct: float = 0.0
    yield_p10: float = 0.0
    yield_p50: float = 0.0
    yield_p90: float = 0.0
    profit_p50: float = 0.0

    # === TEMPORAL PLANNING CONTEXT ===
    suitability_states: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # {suitability_type: {state, score, limiting_factors}}
    planting_window: Dict[str, str] = field(default_factory=dict)
    # {"optimal_start": "2025-06-15", "optimal_end": "2025-07-01", "days_remaining": "12"}
    yield_trajectory: List[float] = field(default_factory=list)
    # Historical yield estimates over time (from scenario runs)
    season_progress_pct: float = 0.0
    # How far into the growing season we are (0-100%)
    scenario_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    # [{scenario_id, yield_p50, risk_score, description}]

    run_id: str = ""


def adapt_l7(planning: Any) -> L7PlanningData:
    if planning is None:
        return L7PlanningData()
    result = L7PlanningData()
    rm = getattr(planning, 'run_meta', None)
    if rm:
        result.run_id = getattr(rm, 'run_id', '') if not isinstance(rm, dict) else rm.get('run_id', '')
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

        # Suitability states — extract from individual fields
        for field_name in ('window', 'soil', 'water', 'biotic'):
            ss = getattr(best, field_name, None)
            if ss and hasattr(ss, 'probability_ok'):
                result.suitability_states[field_name.upper()] = {
                    'probability_ok': getattr(ss, 'probability_ok', 0.0),
                    'confidence': getattr(ss, 'confidence', 0.0),
                    'severity': getattr(ss, 'severity', 'LOW'),
                    'drivers_used': [
                        d.value if hasattr(d, 'value') else str(d)
                        for d in getattr(ss, 'drivers_used', [])
                    ],
                }

        # Planting window — extract from window SuitabilityState notes
        window_state = getattr(best, 'window', None)
        if window_state:
            result.planting_window = {
                'probability_ok': str(getattr(window_state, 'probability_ok', 0.0)),
                'confidence': str(getattr(window_state, 'confidence', 0.0)),
                'severity': getattr(window_state, 'severity', ''),
            }

    # Season progress
    result.season_progress_pct = getattr(planning, 'season_progress', 0.0)

    # Yield trajectory from historical scenario runs
    trajectory = getattr(planning, 'yield_trajectory', [])
    if trajectory and isinstance(trajectory, list):
        result.yield_trajectory = [float(v) for v in trajectory if isinstance(v, (int, float))]

    # Scenario outcomes
    for sc in getattr(planning, 'scenarios', []):
        result.scenario_outcomes.append({
            'scenario_id': getattr(sc, 'scenario_id', ''),
            'yield_p50': getattr(sc, 'yield_p50', 0.0),
            'risk_score': getattr(sc, 'risk_score', 0.0),
            'description': getattr(sc, 'description', ''),
        })

    return result


# ===== L8 ADAPTER (Enhanced) =====
@dataclass
class L8ActionData:
    """Normalized L8 prescriptive intelligence for Layer 10 (v2 — Temporal)."""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    zone_plan: List[Dict[str, Any]] = field(default_factory=list)
    yield_delta_pct: float = 0.0
    risk_reduction_pct: float = 0.0
    degradation_mode: str = "NORMAL"

    # === TEMPORAL PRESCRIPTIVE CONTEXT ===
    schedule: List[Dict[str, Any]] = field(default_factory=list)
    # [{action_id, start_date, end_date, zone_id, timing_critical}]
    timing_critical_actions: List[str] = field(default_factory=list)
    # Action IDs with narrow execution windows
    intervention_cost_total: float = 0.0
    expected_roi: float = 0.0

    run_id: str = ""


def adapt_l8(prescriptive: Any) -> L8ActionData:
    if prescriptive is None:
        return L8ActionData()
    result = L8ActionData(run_id=getattr(prescriptive, 'run_id', ''))
    for act in getattr(prescriptive, 'actions', []):
        at = getattr(act, 'action_type', None)
        action_id = getattr(act, 'action_id', '')
        result.actions.append({
            'action_id': action_id,
            'action_type': at.value if hasattr(at, 'value') else str(at),
            'priority_score': getattr(act, 'priority_score', 0.0),
            'is_allowed': getattr(act, 'is_allowed', True),
            'zone_targets': getattr(act, 'zone_targets', []),
            'confidence': getattr(
                getattr(act, 'confidence', None), 'value',
                str(getattr(act, 'confidence', 'MODERATE'))
            ),
        })

        # Check for timing criticality
        timing = getattr(act, 'timing_window', None)
        if timing and getattr(timing, 'is_critical', False):
            result.timing_critical_actions.append(action_id)

    raw_zone_plan = getattr(prescriptive, 'zone_plan', {})
    if isinstance(raw_zone_plan, dict):
        for zone_id, zp in raw_zone_plan.items():
            result.zone_plan.append({
                'zone_id': getattr(zp, 'zone_id', zone_id),
                'actions': getattr(zp, 'actions', []),
                'allocation_fraction': getattr(zp, 'allocation_fraction', 0.0),
                'priority': getattr(zp, 'priority', ''),
            })
    elif isinstance(raw_zone_plan, list):
        for zp in raw_zone_plan:
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

    # Schedule extraction
    for sched in getattr(prescriptive, 'schedule', []):
        status = getattr(sched, 'status', None)
        result.schedule.append({
            'action_id': getattr(sched, 'action_id', ''),
            'scheduled_date': getattr(sched, 'scheduled_date', ''),
            'status': status.value if hasattr(status, 'value') else str(status or ''),
            'zone_id': '',  # ScheduledAction doesn't carry zone_id; sourced from zone_plan
            'timing_critical': not getattr(sched, 'weather_ok', True),
        })

    # Cost and ROI
    cost = getattr(prescriptive, 'total_cost', None)
    if cost and isinstance(cost, (int, float)):
        result.intervention_cost_total = float(cost)
    roi = getattr(prescriptive, 'expected_roi', None)
    if roi and isinstance(roi, (int, float)):
        result.expected_roi = float(roi)

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

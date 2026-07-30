"""
Layer 0.7: Continuous Self-Audit — Trust Reports, Drift Detection, Silent Failure Prevention

Provides:
  1. TrustReport: per-plot data availability, reliability trends, conflict log, innovation stats
  2. SensorDriftDetector: rolling bias, step changes, stuck-at faults
  3. AssimilationAuditor: error budgets, schema completeness, uncertainty monotonicity
  4. Integration with FieldTensor: writes audit output into tensor.provenance

This module runs AFTER Kalman assimilation and provides:
  - "Is this plot's data trustworthy today?"
  - "Which sources are degrading?"
  - "Did the pipeline silently break?"
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math


# ============================================================================
# 1) Trust Report
# ============================================================================

@dataclass
class SourceAvailability:
    """Data availability for one source."""
    source: str
    total_possible_days: int = 0
    days_with_data: int = 0
    days_with_valid_data: int = 0  # After QA filtering
    coverage_pct: float = 0.0      # days_with_valid / total
    avg_reliability: float = 1.0
    reliability_trend: str = "stable"  # "improving", "stable", "degrading"


@dataclass
class InnovationStats:
    """
    Innovation = observation - model_prediction (Kalman residual).
    Healthy filter: mean ≈ 0, variance ≈ observation_noise.
    If mean drifts -> model bias. If variance explodes -> model/obs mismatch.
    """
    obs_type: str
    mean: float = 0.0
    std: float = 0.0
    n_observations: int = 0
    bias_flag: bool = False      # |mean| > 2*std -> systematic bias
    variance_flag: bool = False   # std > 3*expected -> obs/model mismatch


@dataclass
class TrustReport:
    """
    Per-plot trust report. The canonical output of the self-audit system.
    
    Written to: tensor.provenance["audit"]
    """
    plot_id: str
    report_date: str
    period_start: str
    period_end: str
    
    # Overall health
    health_score: float = 1.0        # 0–1 composite score
    health_grade: str = "A"           # A/B/C/D/F
    degraded: bool = False
    alerts: List[str] = field(default_factory=list)
    
    # Data availability per source
    availability: List[Dict] = field(default_factory=list)
    
    # Reliability from ValidationGraph
    source_reliability: Dict[str, float] = field(default_factory=dict)
    reliability_trends: Dict[str, str] = field(default_factory=dict)
    
    # Conflict log
    conflicts: List[Dict] = field(default_factory=list)
    conflict_count: int = 0
    
    # Innovation statistics per obs type
    innovation_stats: List[Dict] = field(default_factory=list)
    
    # Uncertainty health
    uncertainty_growth_rate: float = 0.0  # avg daily σ growth during gaps
    uncertainty_shrink_on_obs: float = 0.0  # avg σ reduction on obs days
    max_gap_days: int = 0
    
    # Boundary health
    boundary_confidence: float = 0.8
    boundary_warnings: List[str] = field(default_factory=list)
    
    # Sensor health (if applicable)
    sensor_health: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plot_id": self.plot_id,
            "report_date": self.report_date,
            "period": f"{self.period_start} to {self.period_end}",
            "health_score": round(self.health_score, 2),
            "health_grade": self.health_grade,
            "degraded": self.degraded,
            "alerts": self.alerts,
            "availability": self.availability,
            "source_reliability": self.source_reliability,
            "reliability_trends": self.reliability_trends,
            "conflict_count": self.conflict_count,
            "conflicts": self.conflicts[:10],  # Cap for readability
            "innovation_stats": self.innovation_stats,
            "uncertainty_growth_rate": round(self.uncertainty_growth_rate, 4),
            "uncertainty_shrink_on_obs": round(self.uncertainty_shrink_on_obs, 4),
            "max_gap_days": self.max_gap_days,
            "boundary_confidence": self.boundary_confidence,
            "boundary_warnings": self.boundary_warnings,
            "sensor_health": self.sensor_health,
        }


class TrustReportBuilder:
    """
    Builds a TrustReport from FieldTensor outputs.
    
    Reads: daily_state, state_uncertainty, provenance_log, boundary_info.
    """
    
    @staticmethod
    def build(
        plot_id: str,
        daily_state: Dict[str, List[Dict]],
        state_uncertainty: Dict[str, List[Dict]],
        provenance_log: List[Dict],
        boundary_info: Dict[str, Any],
        source_reliability: Optional[Dict[str, float]] = None,
        conflicts: Optional[List[Dict]] = None,
    ) -> TrustReport:
        """Build a full trust report from Layer 0 outputs."""
        
        # Determine date range
        all_days = []
        for zone_states in daily_state.values():
            for s in zone_states:
                d = s.get("day", "")
                if d:
                    all_days.append(d)
        all_days = sorted(set(all_days))
        
        report = TrustReport(
            plot_id=plot_id,
            report_date=all_days[-1] if all_days else "",
            period_start=all_days[0] if all_days else "",
            period_end=all_days[-1] if all_days else "",
        )
        
        # --- Availability ---
        report.availability = TrustReportBuilder._compute_availability(
            provenance_log, len(all_days)
        )
        
        # --- Reliability ---
        if source_reliability:
            report.source_reliability = source_reliability
            for src, rel in source_reliability.items():
                if rel < 0.5:
                    report.reliability_trends[src] = "degrading"
                elif rel < 0.8:
                    report.reliability_trends[src] = "marginal"
                else:
                    report.reliability_trends[src] = "stable"
        
        # --- Conflicts ---
        report.conflicts = conflicts or []
        report.conflict_count = len(report.conflicts)
        
        # --- Innovation stats ---
        report.innovation_stats = TrustReportBuilder._compute_innovation_stats(
            provenance_log
        )
        
        # --- Uncertainty health ---
        unc_metrics = TrustReportBuilder._compute_uncertainty_health(
            state_uncertainty, provenance_log
        )
        report.uncertainty_growth_rate = unc_metrics.get("growth_rate", 0)
        report.uncertainty_shrink_on_obs = unc_metrics.get("shrink_on_obs", 0)
        report.max_gap_days = unc_metrics.get("max_gap", 0)
        
        # --- Boundary ---
        report.boundary_confidence = boundary_info.get("confidence", 0.8)
        if report.boundary_confidence < 0.5:
            report.boundary_warnings.append("Low boundary confidence — consider re-drawing plot")
        
        # --- Compute overall health score ---
        report.health_score = TrustReportBuilder._compute_health_score(report)
        report.health_grade = TrustReportBuilder._score_to_grade(report.health_score)
        report.degraded = report.health_score < 0.5
        
        # --- Generate alerts ---
        report.alerts = TrustReportBuilder._generate_alerts(report)
        
        return report
    
    @staticmethod
    def _compute_availability(
        provenance_log: List[Dict], total_days: int
    ) -> List[Dict]:
        """Count how many days each source contributed."""
        source_days: Dict[str, int] = {}
        
        for day_rec in provenance_log:
            for zone_data in day_rec.get("zones", {}).values():
                prov = zone_data.get("provenance", {})
                sources = prov.get("sources", {})
                for src in sources:
                    source_days[src] = source_days.get(src, 0) + 1
        
        result = []
        for src, days in source_days.items():
            coverage = days / max(total_days, 1)
            result.append({
                "source": src,
                "days_with_data": days,
                "total_days": total_days,
                "coverage_pct": round(coverage * 100, 1),
            })
        return result
    
    @staticmethod
    def _compute_innovation_stats(provenance_log: List[Dict]) -> List[Dict]:
        """
        Compute innovation statistics from provenance.
        Innovation = obs_value - predicted_value (tracked via source weights).
        """
        # We approximate from provenance — in a full system we'd store
        # explicit innovations. Here we use source contribution magnitude.
        source_contributions: Dict[str, List[float]] = {}
        
        for day_rec in provenance_log:
            for zone_data in day_rec.get("zones", {}).values():
                prov = zone_data.get("provenance", {})
                sources = prov.get("sources", {})
                for src, weight in sources.items():
                    if src not in source_contributions:
                        source_contributions[src] = []
                    source_contributions[src].append(weight)
        
        stats = []
        for src, weights in source_contributions.items():
            n = len(weights)
            if n == 0:
                continue
            mean_w = sum(weights) / n
            var_w = sum((w - mean_w) ** 2 for w in weights) / max(n - 1, 1)
            std_w = math.sqrt(var_w)
            
            stats.append({
                "source": src,
                "n_obs_days": n,
                "mean_contribution": round(mean_w, 4),
                "std_contribution": round(std_w, 4),
                "bias_flag": abs(mean_w) > 2 * max(std_w, 0.01),
                "variance_flag": std_w > 0.5,
            })
        return stats
    
    @staticmethod
    def _compute_uncertainty_health(
        state_uncertainty: Dict[str, List[Dict]],
        provenance_log: List[Dict],
    ) -> Dict[str, float]:
        """Analyze uncertainty behavior across the period."""
        
        growth_rates = []
        shrink_rates = []
        max_gap = 0
        current_gap = 0
        
        for zone_id, unc_list in state_uncertainty.items():
            prev_mean_sigma = None
            
            for i, unc in enumerate(unc_list):
                # Average sigma across all variables
                sigmas = [v for k, v in unc.items() if k != "day" and isinstance(v, (int, float))]
                if not sigmas:
                    continue
                mean_sigma = sum(sigmas) / len(sigmas)
                
                # Check if this was an observation day
                is_obs_day = False
                day = unc.get("day", "")
                for drec in provenance_log:
                    if drec.get("day") == day:
                        for zdata in drec.get("zones", {}).values():
                            if zdata.get("provenance", {}).get("n_obs", 0) > 0:
                                is_obs_day = True
                                break
                
                if prev_mean_sigma is not None:
                    delta = mean_sigma - prev_mean_sigma
                    if is_obs_day:
                        shrink_rates.append(delta)  # Should be negative
                        current_gap = 0
                    else:
                        growth_rates.append(delta)  # Should be positive
                        current_gap += 1
                        max_gap = max(max_gap, current_gap)
                
                prev_mean_sigma = mean_sigma
        
        return {
            "growth_rate": sum(growth_rates) / max(len(growth_rates), 1) if growth_rates else 0,
            "shrink_on_obs": sum(shrink_rates) / max(len(shrink_rates), 1) if shrink_rates else 0,
            "max_gap": max_gap,
        }
    
    @staticmethod
    def _compute_health_score(report: TrustReport) -> float:
        """
        Composite health score 0–1.
        
        Factors:
        - Data availability (30% weight)
        - Source reliability (25%)
        - Conflict rate (20%)
        - Uncertainty behavior (15%)
        - Boundary confidence (10%)
        """
        score = 0.0
        
        # Availability: average coverage across sources
        if report.availability:
            avg_coverage = sum(
                a.get("coverage_pct", 0) for a in report.availability
            ) / len(report.availability) / 100.0
            score += 0.30 * min(1.0, avg_coverage * 2)  # 50%+ coverage -> full score
        else:
            score += 0.15  # Partial score even with no data (still ran model)
        
        # Reliability: average across sources
        if report.source_reliability:
            avg_rel = sum(report.source_reliability.values()) / len(report.source_reliability)
            score += 0.25 * avg_rel
        else:
            score += 0.25  # Default full if no reliability tracking
        
        # Conflicts: penalize high conflict rate
        total_days = max(1, len(set(
            c.get("day", "") for c in report.conflicts
        )))
        period_days = 1
        if report.period_start and report.period_end:
            try:
                from datetime import datetime
                d1 = datetime.strptime(report.period_start, "%Y-%m-%d")
                d2 = datetime.strptime(report.period_end, "%Y-%m-%d")
                period_days = max(1, (d2 - d1).days + 1)
            except (ValueError, TypeError):
                period_days = 30
        conflict_rate = total_days / period_days
        score += 0.20 * max(0, 1.0 - conflict_rate * 5)  # >20% conflict days -> 0
        
        # Uncertainty: should grow in gaps, shrink on obs
        unc_healthy = 1.0
        if report.uncertainty_growth_rate < 0:
            unc_healthy -= 0.3  # Uncertainty DECREASING without obs -> suspicious
        if report.uncertainty_shrink_on_obs > 0:
            unc_healthy -= 0.3  # Uncertainty INCREASING on obs days -> Kalman broken
        if report.max_gap_days > 20:
            unc_healthy -= 0.2  # Very long data gap
        score += 0.15 * max(0, unc_healthy)
        
        # Boundary
        score += 0.10 * report.boundary_confidence
        
        return min(1.0, max(0.0, score))
    
    @staticmethod
    def _score_to_grade(score: float) -> str:
        if score >= 0.85:
            return "A"
        elif score >= 0.70:
            return "B"
        elif score >= 0.55:
            return "C"
        elif score >= 0.40:
            return "D"
        return "F"
    
    @staticmethod
    def _generate_alerts(report: TrustReport) -> List[str]:
        """Generate human-readable alerts."""
        alerts = []
        
        if report.health_score < 0.5:
            alerts.append(" DEGRADED: Plot data quality is below threshold")
        
        # Check each source reliability
        for src, rel in report.source_reliability.items():
            if rel < 0.3:
                alerts.append(f" {src} reliability critically low ({rel:.0%})")
            elif rel < 0.6:
                alerts.append(f" {src} reliability degraded ({rel:.0%})")
        
        # Check availability
        for avail in report.availability:
            if avail.get("coverage_pct", 0) < 10:
                alerts.append(f" {avail['source']} coverage very low ({avail['coverage_pct']}%)")
        
        # Check uncertainty
        if report.max_gap_days > 14:
            alerts.append(f" Long data gap detected ({report.max_gap_days} days)")
        
        if report.uncertainty_shrink_on_obs > 0:
            alerts.append(" Kalman update not reducing uncertainty — check observation models")
        
        # Check conflicts
        if report.conflict_count > 10:
            alerts.append(f" High conflict count ({report.conflict_count}) — review source quality")
        
        # Boundary
        for w in report.boundary_warnings:
            alerts.append(f" Boundary: {w}")
        
        # Innovation bias
        for stat in report.innovation_stats:
            if stat.get("bias_flag"):
                alerts.append(f" {stat['source']} shows systematic bias in contributions")
        
        return alerts


# ============================================================================
# 2) Sensor Drift Detector
# ============================================================================

class SensorDriftDetector:
    """
    Detects sensor anomalies for in-situ sensors (soil moisture probes, etc).
    
    Checks:
      - Rolling bias vs model prediction
      - Step changes (device moved / recalibrated)
      - Stuck-at faults (flatline values)
    
    Outputs: sensor_health_score + recommended reliability adjustments.
    """
    
    def __init__(self, window_size: int = 14):
        self.window_size = window_size
        self.readings: Dict[str, List[Tuple[str, float]]] = {}  # sensor_id -> [(day, value)]
        self.model_predictions: Dict[str, List[Tuple[str, float]]] = {}
    
    def add_reading(self, sensor_id: str, day: str, value: float) -> None:
        if sensor_id not in self.readings:
            self.readings[sensor_id] = []
        self.readings[sensor_id].append((day, value))
    
    def add_model_prediction(self, sensor_id: str, day: str, predicted: float) -> None:
        if sensor_id not in self.model_predictions:
            self.model_predictions[sensor_id] = []
        self.model_predictions[sensor_id].append((day, predicted))
    
    def diagnose(self, sensor_id: str) -> Dict[str, Any]:
        """Run all diagnostics for a sensor."""
        readings = self.readings.get(sensor_id, [])
        predictions = self.model_predictions.get(sensor_id, [])
        
        if len(readings) < 3:
            return {
                "sensor_id": sensor_id,
                "health_score": 1.0,
                "status": "insufficient_data",
                "issues": [],
                "recommended_reliability": 1.0,
            }
        
        issues = []
        health = 1.0
        
        # --- Stuck-at fault ---
        values = [v for _, v in readings[-self.window_size:]]
        if len(values) >= 3:
            unique = len(set(round(v, 4) for v in values))
            if unique == 1:
                issues.append({
                    "type": "stuck_at",
                    "severity": 1.0,
                    "detail": f"Sensor stuck at {values[0]:.4f} for {len(values)} readings",
                })
                health -= 0.5
            elif unique <= 2 and len(values) > 5:
                issues.append({
                    "type": "near_stuck",
                    "severity": 0.5,
                    "detail": f"Only {unique} unique values in {len(values)} readings",
                })
                health -= 0.2
        
        # --- Step change ---
        if len(values) >= 4:
            mid = len(values) // 2
            mean_first = sum(values[:mid]) / mid
            mean_second = sum(values[mid:]) / (len(values) - mid)
            jump = abs(mean_second - mean_first)
            typical_range = max(values) - min(values) if max(values) != min(values) else 0.1
            
            if jump > 0.5 * typical_range and typical_range > 0.01:
                issues.append({
                    "type": "step_change",
                    "severity": min(1.0, jump / typical_range),
                    "detail": f"Step change detected: {mean_first:.3f} -> {mean_second:.3f}",
                })
                health -= 0.3
        
        # --- Rolling bias vs model ---
        if predictions:
            pred_map = {d: v for d, v in predictions}
            paired = []
            for day, obs_val in readings[-self.window_size:]:
                if day in pred_map:
                    paired.append(obs_val - pred_map[day])
            
            if len(paired) >= 3:
                bias = sum(paired) / len(paired)
                bias_std = math.sqrt(
                    sum((r - bias) ** 2 for r in paired) / max(len(paired) - 1, 1)
                )
                
                if abs(bias) > 0.1:
                    issues.append({
                        "type": "bias",
                        "severity": min(1.0, abs(bias) / 0.3),
                        "detail": f"Rolling bias = {bias:+.3f} ± {bias_std:.3f}",
                    })
                    health -= min(0.3, abs(bias))
        
        health = max(0.0, health)
        
        # Recommended reliability
        if health > 0.8:
            rec_reliability = 1.0
        elif health > 0.5:
            rec_reliability = 0.6
        elif health > 0.2:
            rec_reliability = 0.3
        else:
            rec_reliability = 0.1
        
        return {
            "sensor_id": sensor_id,
            "health_score": round(health, 2),
            "status": "healthy" if health > 0.7 else "degraded" if health > 0.3 else "failing",
            "issues": issues,
            "recommended_reliability": rec_reliability,
        }
    
    def diagnose_all(self) -> List[Dict]:
        return [self.diagnose(sid) for sid in self.readings]


# ============================================================================
# 3) Assimilation Auditor — Error Budgets & Schema Checks
# ============================================================================

class AssimilationAuditor:
    """
    Validates that Layer 0 output is structurally correct and internally consistent.
    
    Checks:
      - Schema completeness (daily_state length matches date range)
      - Uncertainty monotonicity during gaps
      - NaN/Inf/out-of-bounds values
      - Error budget (failure count tracking)
    """
    
    def __init__(self):
        self.error_budget: Dict[str, int] = {}  # plot_id -> failure count (rolling 7d)
        self.error_threshold = 3  # Max failures per 7 days before alert
    
    def audit(
        self,
        plot_id: str,
        daily_state: Dict[str, List[Dict]],
        state_uncertainty: Dict[str, List[Dict]],
        provenance_log: List[Dict],
        expected_days: int = 0,
    ) -> Dict[str, Any]:
        """
        Run all structural & consistency checks.
        
        Returns audit result with pass/fail per check and overall status.
        """
        checks = []
        
        # --- 1. Schema completeness ---
        for zone_id, states in daily_state.items():
            actual = len(states)
            if expected_days > 0 and actual != expected_days + 1:
                # +1 because we include initial state
                checks.append({
                    "check": "schema_completeness",
                    "zone": zone_id,
                    "passed": False,
                    "detail": f"Expected {expected_days + 1} states, got {actual}",
                })
            else:
                checks.append({
                    "check": "schema_completeness",
                    "zone": zone_id,
                    "passed": True,
                })
        
        # --- 2. Value bounds ---
        for zone_id, states in daily_state.items():
            for s in states:
                issues = []
                lai = s.get("lai_proxy", 0)
                if not (0 <= lai <= 10):
                    issues.append(f"lai_proxy={lai} out of bounds [0, 10]")
                sm = s.get("sm_0_10", 0)
                if not (0 <= sm <= 1):
                    issues.append(f"sm_0_10={sm} out of bounds [0, 1]")
                stress = s.get("canopy_stress", 0)
                if not (0 <= stress <= 1):
                    issues.append(f"canopy_stress={stress} out of bounds [0, 1]")
                
                # Check for NaN/Inf
                for k, v in s.items():
                    if k == "day":
                        continue
                    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                        issues.append(f"{k}={v} is NaN/Inf")
                
                if issues:
                    checks.append({
                        "check": "value_bounds",
                        "zone": zone_id,
                        "day": s.get("day", ""),
                        "passed": False,
                        "detail": "; ".join(issues),
                    })
        
        # --- 3. Uncertainty monotonicity during gaps ---
        for zone_id, unc_list in state_uncertainty.items():
            prev_mean = None
            gap_streak = 0
            monotonicity_violations = 0
            
            for i, unc in enumerate(unc_list):
                sigmas = [v for k, v in unc.items() if k != "day" and isinstance(v, (int, float))]
                if not sigmas:
                    continue
                mean_sigma = sum(sigmas) / len(sigmas)
                
                # Check if observation day
                day = unc.get("day", "")
                is_obs = False
                for drec in provenance_log:
                    if drec.get("day") == day:
                        for zd in drec.get("zones", {}).values():
                            if zd.get("provenance", {}).get("n_obs", 0) > 0:
                                is_obs = True
                
                if not is_obs and prev_mean is not None:
                    gap_streak += 1
                    if gap_streak > 1 and mean_sigma < prev_mean - 0.001:
                        monotonicity_violations += 1
                else:
                    gap_streak = 0
                
                prev_mean = mean_sigma
            
            if monotonicity_violations > 0:
                checks.append({
                    "check": "uncertainty_monotonicity",
                    "zone": zone_id,
                    "passed": False,
                    "detail": f"{monotonicity_violations} violations: uncertainty decreased during data gaps",
                })
            else:
                checks.append({
                    "check": "uncertainty_monotonicity",
                    "zone": zone_id,
                    "passed": True,
                })
        
        # --- 4. Provenance consistency ---
        if provenance_log:
            days_without_entries = 0
            for drec in provenance_log:
                if not drec.get("zones"):
                    days_without_entries += 1
            
            if days_without_entries > 0:
                checks.append({
                    "check": "provenance_completeness",
                    "passed": False,
                    "detail": f"{days_without_entries} days missing zone provenance",
                })
            else:
                checks.append({
                    "check": "provenance_completeness",
                    "passed": True,
                })
        
        # --- Error budget ---
        n_failures = sum(1 for c in checks if not c.get("passed", True))
        self.error_budget[plot_id] = self.error_budget.get(plot_id, 0) + n_failures
        
        budget_exceeded = self.error_budget[plot_id] > self.error_threshold
        
        return {
            "plot_id": plot_id,
            "status": "PASS" if n_failures == 0 else "DEGRADED" if not budget_exceeded else "ALERT",
            "checks_run": len(checks),
            "checks_passed": sum(1 for c in checks if c.get("passed", True)),
            "checks_failed": n_failures,
            "checks": checks,
            "error_budget_used": self.error_budget[plot_id],
            "error_budget_exceeded": budget_exceeded,
        }
    
    def reset_budget(self, plot_id: str) -> None:
        """Reset error budget (e.g., weekly reset)."""
        self.error_budget[plot_id] = 0


# ============================================================================
# 4) Integration: run_audit() convenience function
# ============================================================================

def run_audit(
    plot_id: str,
    tensor_daily_state: Dict[str, List[Dict]],
    tensor_state_uncertainty: Dict[str, List[Dict]],
    tensor_provenance_log: List[Dict],
    tensor_boundary_info: Dict[str, Any],
    source_reliability: Optional[Dict[str, float]] = None,
    conflicts: Optional[List[Dict]] = None,
    expected_days: int = 0,
) -> Dict[str, Any]:
    """
    Convenience function: run full audit and return combined report.
    
    Returns dict with:
      - trust_report: human-readable health report
      - structural_audit: pass/fail checks
      
    Call this from data_fusion.py after Kalman engine.
    """
    # Trust report
    trust_report = TrustReportBuilder.build(
        plot_id=plot_id,
        daily_state=tensor_daily_state,
        state_uncertainty=tensor_state_uncertainty,
        provenance_log=tensor_provenance_log,
        boundary_info=tensor_boundary_info,
        source_reliability=source_reliability,
        conflicts=conflicts,
    )
    
    # Structural audit
    auditor = AssimilationAuditor()
    structural = auditor.audit(
        plot_id=plot_id,
        daily_state=tensor_daily_state,
        state_uncertainty=tensor_state_uncertainty,
        provenance_log=tensor_provenance_log,
        expected_days=expected_days,
    )
    
    return {
        "trust_report": trust_report.to_dict(),
        "structural_audit": structural,
    }

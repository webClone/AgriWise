"""
ASMAE Resolution Report.

Generates a human-readable and machine-parsable report of
the resolution evaluation, policy decisions, and final selection.

Used for:
  - Provenance audit trails
  - Diagnostics in the ASMAE output
  - Debugging resolution demotion issues
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..schema import ResolutionDecision
from .evaluator import EvaluationResult
from .policy import PolicyResult
from .reason_codes import classify_code


@dataclass
class ResolutionReport:
    """Complete resolution evaluation report."""
    generated_at: str = ""
    plot_id: str = ""
    run_id: str = ""

    # Summary
    n_candidates: int = 0
    n_eligible: int = 0
    n_demoted: int = 0

    # Final selection
    effective_resolution_m: int = 10
    visual_resolution_m: int = 10
    state_update_resolution_m: int = 10
    training_resolution_m: int = 10
    research_resolution_m: int = 1
    safe_for_1m: bool = False

    # Per-candidate detail
    candidate_details: List[Dict[str, Any]] = field(default_factory=list)

    # Policy actions
    policy_actions: List[Dict[str, Any]] = field(default_factory=list)

    # Promotion/demotion summary
    promotions: List[Dict[str, Any]] = field(default_factory=list)
    demotions: List[Dict[str, Any]] = field(default_factory=list)
    gates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "plot_id": self.plot_id,
            "run_id": self.run_id,
            "summary": {
                "n_candidates": self.n_candidates,
                "n_eligible": self.n_eligible,
                "n_demoted": self.n_demoted,
                "effective_resolution_m": self.effective_resolution_m,
                "visual_resolution_m": self.visual_resolution_m,
                "safe_for_1m": self.safe_for_1m,
            },
            "candidates": self.candidate_details,
            "policy_actions": self.policy_actions,
            "promotions": self.promotions,
            "demotions": self.demotions,
            "gates": self.gates,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_text(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "═══════════════════════════════════════════════════════════════",
            "  ASMAE Resolution Evaluation Report",
            f"  Plot: {self.plot_id}  |  Run: {self.run_id}",
            f"  Generated: {self.generated_at}",
            "═══════════════════════════════════════════════════════════════",
            "",
            f"  Candidates: {self.n_candidates} total, "
            f"{self.n_eligible} eligible, {self.n_demoted} demoted",
            "",
            "  ── Final Selection ──────────────────────────────────────────",
            f"  Effective:    {self.effective_resolution_m}m",
            f"  Visual:       {self.visual_resolution_m}m",
            f"  State Update: {self.state_update_resolution_m}m",
            f"  Training:     {self.training_resolution_m}m",
            f"  Research:     {self.research_resolution_m}m",
            f"  1m Certified: {'YES' if self.safe_for_1m else 'NO'}",
            "",
            "  ── Candidate Scores ─────────────────────────────────────────",
        ]

        for cd in sorted(self.candidate_details, key=lambda x: x.get("resolution_m", 0)):
            res = cd.get("resolution_m", "?")
            score = cd.get("composite_score", 0.0)
            status = "✓" if not cd.get("rejected", False) else "✗"
            marker = " ◀ SELECTED" if res == self.effective_resolution_m else ""
            lines.append(
                f"  {status} {res:>3}m  score={score:.3f}  "
                f"op={cd.get('operator_quality', 0.0):.2f}  "
                f"div={cd.get('scene_diversity', 0.0):.2f}  "
                f"id={cd.get('identifiability', 0.0):.2f}  "
                f"pr={cd.get('prior_confidence', 0.0):.2f}"
                f"{marker}"
            )

        if self.promotions:
            lines.append("")
            lines.append("  ── Promotions ───────────────────────────────────────────────")
            for p in self.promotions:
                lines.append(f"  + {p.get('resolution_m', '?')}m: {p.get('code', '?')}")

        if self.demotions:
            lines.append("")
            lines.append("  ── Demotions ────────────────────────────────────────────────")
            for d in self.demotions:
                lines.append(f"  - {d.get('resolution_m', '?')}m: {d.get('code', '?')}")

        if self.gates:
            lines.append("")
            lines.append("  ── Gates ────────────────────────────────────────────────────")
            for g in self.gates:
                lines.append(f"  ⊞ {g.get('resolution_m', '?')}m: {g.get('code', '?')}")

        lines.append("")
        lines.append("═══════════════════════════════════════════════════════════════")

        return "\n".join(lines)


def generate_report(
    decision: ResolutionDecision,
    evaluation_results: Dict[int, EvaluationResult],
    policy_result: PolicyResult,
    plot_id: str = "",
    run_id: str = "",
) -> ResolutionReport:
    """Generate a complete resolution evaluation report.

    Args:
        decision: Final ResolutionDecision.
        evaluation_results: Per-resolution evaluation scores.
        policy_result: Policy application result.
        plot_id: Plot identifier.
        run_id: Run identifier.

    Returns:
        ResolutionReport with full detail.
    """
    report = ResolutionReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        plot_id=plot_id,
        run_id=run_id,
        effective_resolution_m=decision.selected_effective_resolution_m,
        visual_resolution_m=decision.selected_visual_resolution_m,
        state_update_resolution_m=decision.selected_state_update_resolution_m,
        training_resolution_m=decision.selected_training_resolution_m,
        research_resolution_m=decision.research_resolution_m,
        safe_for_1m=decision.safe_for_1m_claim,
    )

    # Per-candidate detail
    for res_m, ev in sorted(evaluation_results.items()):
        detail: Dict[str, Any] = {
            "resolution_m": res_m,
            "composite_score": round(ev.composite_score, 4),
            "operator_quality": round(ev.operator_quality, 4),
            "scene_diversity": round(ev.scene_diversity, 4),
            "identifiability": round(ev.identifiability, 4),
            "prior_confidence": round(ev.prior_confidence, 4),
            "rejected": ev.rejected,
        }
        if ev.rejection_reason:
            detail["rejection_reason"] = ev.rejection_reason

        report.candidate_details.append(detail)
        report.n_candidates += 1
        if not ev.rejected:
            report.n_eligible += 1

        # Classify reasons
        for r in ev.reasons:
            entry = {
                "resolution_m": res_m,
                "code": r.code,
                "value": r.value,
                "threshold": r.threshold,
                "message": r.message,
            }
            category = classify_code(r.code)
            if category == "promote":
                report.promotions.append(entry)
            elif category == "demote":
                report.demotions.append(entry)
            elif category == "gate":
                report.gates.append(entry)

    # Policy actions
    report.n_demoted = len(policy_result.demoted_candidates)
    for dc in policy_result.demoted_candidates:
        report.policy_actions.append({
            "type": "demotion",
            **dc,
        })

    for res_m, reasons in policy_result.policy_reasons.items():
        for r in reasons:
            category = classify_code(r.code)
            if category == "gate":
                report.gates.append({
                    "resolution_m": res_m,
                    "code": r.code,
                    "value": r.value,
                    "threshold": r.threshold,
                    "message": r.message,
                })
            report.policy_actions.append({
                "type": "policy",
                "resolution_m": res_m,
                "code": r.code,
                "message": r.message,
            })

    return report

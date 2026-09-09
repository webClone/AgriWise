"""MESIA Scan-Plan Compiler & Resource Arbiter — R6 §2.6 & §4.

Translates high-level survey objectives, priority queues, and coverage bounds
into executable, conflict-free WaveSurveyPlan configurations.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.receiver import ReceiverCapabilityManifest
from ..contracts.wave import WaveSurveyPlan


@dataclass(order=True)
class PrioritizedScanObjective:
    """A prioritized measurement request."""
    priority: int
    """Lower number = higher priority (0 is highest)."""

    objective_name: str = field(compare=False)
    target_bands: List[Tuple[float, float]] = field(compare=False)
    focused_frequencies_hz: List[float] = field(default_factory=list, compare=False)
    max_duration_s: float = field(default=60.0, compare=False)
    storage_budget_mb: float = field(default=500.0, compare=False)


class ScanPlanCompiler:
    """Compiles observation requests into a WaveSurveyPlan while enforcing hardware constraints."""

    def __init__(self, available_receivers: List[ReceiverCapabilityManifest]) -> None:
        self.receivers = {rx.receiver_id: rx for rx in available_receivers}
        self.priority_queue: List[PrioritizedScanObjective] = []

    def submit_objective(self, objective: PrioritizedScanObjective) -> None:
        """Enqueue a prioritized scan objective."""
        heapq.heappush(self.priority_queue, objective)

    def compile_next_survey_plan(
        self,
        plan_id: str,
        jurisdiction_ref: str = "ALGERIA_ARPT_ANF",
    ) -> Optional[WaveSurveyPlan]:
        """Pop the highest priority objective and compile it into an executable WaveSurveyPlan."""
        if not self.priority_queue:
            return None

        top_obj = heapq.heappop(self.priority_queue)

        # Build feasible coarse sweep bands clipped to available hardware tuning limits
        feasible_sweeps: List[Tuple[float, float]] = []
        for req_start, req_end in top_obj.target_bands:
            for rx in self.receivers.values():
                if rx.tuning_range_hz and rx.health_status == "HEALTHY":
                    s = max(req_start, rx.tuning_range_hz[0])
                    e = min(req_end, rx.tuning_range_hz[1])
                    if s < e:
                        feasible_sweeps.append((s, e))

        # Deduplicate sweep spans
        feasible_sweeps = list(set(feasible_sweeps))

        # Check native listeners
        native_listeners = [
            rx.receiver_id
            for rx in self.receivers.values()
            if rx.front_end_class == "F1_NATIVE_RADIO" and rx.health_status == "HEALTHY"
        ]

        return WaveSurveyPlan(
            plan_id=plan_id,
            objective=top_obj.objective_name,
            coarse_sweep_bands=feasible_sweeps,
            focused_dwell_frequencies=list(top_obj.focused_frequencies_hz),
            native_device_listeners=native_listeners,
            trigger_conditions=["ENERGY_ABOVE_THRESHOLD", "CHIRP_DETECTED", "BURST_DETECTED"],
            scan_cadence_s=5.0,
            storage_budget_mb=top_obj.storage_budget_mb,
            max_duration_s=top_obj.max_duration_s,
            priority=top_obj.priority,
            jurisdiction_ref=jurisdiction_ref,
            spectrum_policy_ref=f"policy-{jurisdiction_ref}",
        )

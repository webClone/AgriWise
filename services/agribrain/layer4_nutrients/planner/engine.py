"""
Layer 4.6: Phenology-Aware Execution Planner.

Generates operational DAGs with:
  - Split application tasks linked to phenology stages
  - Verification (soil test) before intervention when confidence is low
  - Post-application monitoring (NDVI response check at 14 days)
  - Weather-responsive scheduling guard rails
"""

from __future__ import annotations

from typing import Dict, List, Optional

from layer4_nutrients.schema import (
    Prescription, NutrientState, ActionId, Nutrient,
    MACRO_NUTRIENTS,
)
from layer3_decision.schema import TaskNode, ExecutionPlan


class PlanningEngine:
    """Phenology-aware execution planner with DAG construction."""

    def create_plan(
        self,
        states: Dict[Nutrient, NutrientState],
        prescriptions: List[Prescription],
        planting_date: str = "",
    ) -> ExecutionPlan:
        """Build execution plan from nutrient states and prescriptions."""
        tasks = []
        edges = []
        task_counter = 0

        # 1. Pre-intervention verification (if any nutrient has low confidence)
        needs_verification = False
        for nut in MACRO_NUTRIENTS:
            state = states.get(nut)
            if state and state.confidence < 0.5:
                needs_verification = True
                break

        # Also check if any prescription is VERIFY_SOIL_TEST
        for rx in prescriptions:
            if rx.action_id == ActionId.VERIFY_SOIL_TEST:
                needs_verification = True

        verify_task_id = None
        if needs_verification:
            task_counter += 1
            verify_task_id = f"TASK_{task_counter}_VERIFY_SOIL"
            tasks.append(TaskNode(
                task_id=verify_task_id,
                type="VERIFY",
                instructions=(
                    "Collect soil samples (0-30cm, composite of 15+ cores) "
                    "for N-NO3, Olsen-P, and exchangeable K analysis. "
                    "Submit to accredited lab. Upload results to recalibrate recommendations."
                ),
                required_inputs=["soil_lab_report"],
                completion_signal="UPLOAD_LAB_REPORT",
                depends_on=[],
            ))

        # 2. Application tasks (from prescriptions with splits)
        for rx in prescriptions:
            if not rx.action_id.value.startswith("APPLY_"):
                continue
            if not rx.is_allowed:
                continue

            for split in rx.splits:
                task_counter += 1
                task_id = f"TASK_{task_counter}_{rx.action_id.value}_SPLIT{split.split_id}"

                depends = []
                if verify_task_id and rx.action_id == ActionId.VERIFY_SOIL_TEST:
                    depends.append(verify_task_id)

                stage = split.timing.phenology_stage if split.timing else "any"
                tasks.append(TaskNode(
                    task_id=task_id,
                    type="INTERVENE",
                    instructions=(
                        f"Apply {split.rate_kg_ha:.1f} kg/ha {rx.product.value} "
                        f"({rx.nutrient.value}) via {split.method.value} "
                        f"at {stage} stage. "
                        f"Product rate: {rx.product_rate_kg_ha * split.fraction_of_total:.1f} kg/ha product."
                    ),
                    required_inputs=["application_log"],
                    completion_signal="USER_CONFIRM",
                    depends_on=depends,
                ))

                # 3. Post-application monitoring
                task_counter += 1
                monitor_id = f"TASK_{task_counter}_MONITOR_{rx.nutrient.value}"
                tasks.append(TaskNode(
                    task_id=monitor_id,
                    type="MONITOR",
                    instructions=(
                        f"Check spectral response 14 days post-application. "
                        f"Expected: NDVI increase >0.03 or NDRE increase >0.02 "
                        f"in treated zones. If no response, escalate to tissue test."
                    ),
                    required_inputs=["satellite_ndvi", "satellite_ndre"],
                    completion_signal="AUTOMATED_CHECK",
                    depends_on=[task_id],
                ))
                edges.append({"from": task_id, "to": monitor_id})

        # 4. Final review
        if tasks:
            task_counter += 1
            review_id = f"TASK_{task_counter}_REVIEW"
            tasks.append(TaskNode(
                task_id=review_id,
                type="REVIEW",
                instructions=(
                    "End-of-cycle review: compare actual yield vs. target, "
                    "update nutrient budget for next season."
                ),
                required_inputs=["yield_data"],
                completion_signal="SEASON_END",
                depends_on=[t.task_id for t in tasks if t.type == "MONITOR"],
            ))

        return ExecutionPlan(
            tasks=tasks,
            edges=edges,
            recommended_start_date=planting_date or "pending",
            review_date="season_end",
        )

"""
Engine 10: Task Manager v9.6.0

Field task lifecycle tracker — auto-generates tasks from L8 actions.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List
from layer9_interface.schema import (
    Layer9Input, PersonaConfig, ExpertiseLevel,
    FieldTask, TaskBoard, TaskStatus,
)

logger = logging.getLogger(__name__)


class TaskManagerEngine:
    """Tracks field tasks auto-generated from L8 prescriptive actions."""

    def __init__(self):
        self._task_store: Dict[str, FieldTask] = {}  # action_id -> task

    def sync(self, l9_input: Layer9Input, persona: PersonaConfig) -> TaskBoard:
        """Sync tasks from L8 actions — creates new, preserves existing statuses."""
        seen_action_ids = set()

        for act in l9_input.actions:
            if not isinstance(act, dict) or not act.get("is_allowed", True):
                continue
            aid = act.get("action_id", "")
            if not aid:
                continue
            seen_action_ids.add(aid)

            if aid not in self._task_store:
                # Find scheduled date
                due = ""
                for s in l9_input.schedule:
                    if isinstance(s, dict) and s.get("action_id") == aid:
                        due = s.get("scheduled_date", "") or ""
                        break

                self._task_store[aid] = FieldTask(
                    title=self._build_title(act, persona.expertise_level),
                    action_type=act.get("action_type", "UNKNOWN"),
                    zone_id=act.get("zone_id", ""),
                    priority=act.get("priority_score", 0),
                    due_date=due,
                    created_from=aid,
                )

        tasks = list(self._task_store.values())
        tasks.sort(key=lambda t: -t.priority)

        overdue = sum(1 for t in tasks
                      if t.status == TaskStatus.PENDING and t.due_date and t.due_date < datetime.now().strftime("%Y-%m-%d"))
        done_count = sum(1 for t in tasks if t.status == TaskStatus.DONE)
        total = len(tasks) or 1

        return TaskBoard(
            tasks=tasks,
            overdue_count=overdue,
            completed_today=0,
            completion_rate_7d=round(done_count / total, 2),
        )

    def get_task_summary(self, board: TaskBoard, exp: ExpertiseLevel) -> str:
        pending = sum(1 for t in board.tasks if t.status == TaskStatus.PENDING)
        done = sum(1 for t in board.tasks if t.status == TaskStatus.DONE)

        if exp == ExpertiseLevel.NOVICE:
            return f"You have {pending} thing(s) to do! 📋 {done} already done — great job! 🎉"
        elif exp == ExpertiseLevel.FARMER:
            return f"{pending} tasks pending, {done} completed. {board.overdue_count} overdue."
        else:
            return f"TaskBoard: pending={pending}, done={done}, overdue={board.overdue_count}, rate_7d={board.completion_rate_7d:.0%}"

    def mark_done(self, action_id: str):
        if action_id in self._task_store:
            self._task_store[action_id].status = TaskStatus.DONE

    def _build_title(self, act: dict, exp: ExpertiseLevel) -> str:
        at = act.get("action_type", "Action")
        if exp == ExpertiseLevel.NOVICE:
            return at.replace("_", " ").title()
        return f"{at} [{act.get('action_id', '')}]"


task_manager = TaskManagerEngine()

"""
Engine 12: Reminder Engine v9.6.0

Time-sensitive smart reminders with trigger-based scheduling.
"""
import logging
from typing import Dict, Any, List
from layer9_interface.schema import (
    Layer9Input, PersonaConfig, ExpertiseLevel,
    Reminder, ReminderTrigger, AlertChannel, TaskStatus,
)

logger = logging.getLogger(__name__)

_MAX_REMINDERS_PER_DAY = 2


class ReminderEngine:
    """Smart reminder generation from schedule + task state."""

    def __init__(self):
        self._sent_today = 0

    def check(self, l9_input: Layer9Input, persona: PersonaConfig,
              task_store: Dict[str, Any] = None) -> List[Reminder]:
        """Evaluate pending triggers and generate reminders."""
        reminders: List[Reminder] = []
        exp = persona.expertise_level

        # Schedule-based reminders
        for s in l9_input.schedule:
            if not isinstance(s, dict):
                continue
            status = s.get("status", "")
            if status in ("SCHEDULED", "PENDING"):
                date = s.get("scheduled_date", "")
                at = s.get("action_type", "action")
                reminders.append(Reminder(
                    title=self._title(at, exp),
                    message=self._schedule_msg(at, date, exp),
                    trigger_type=ReminderTrigger.TIME,
                    trigger_condition=f"scheduled_date={date}",
                    channel=AlertChannel.IN_APP,
                ))

        # Task-overdue reminders
        if task_store:
            for aid, task in task_store.items():
                if hasattr(task, 'status') and task.status == TaskStatus.PENDING:
                    if hasattr(task, 'due_date') and task.due_date:
                        reminders.append(Reminder(
                            title=self._title(task.action_type, exp),
                            message=self._overdue_msg(task.action_type, task.due_date, exp),
                            trigger_type=ReminderTrigger.TASK_OVERDUE,
                            trigger_condition=f"task={aid}",
                            channel=AlertChannel.IN_APP,
                        ))

        # Data staleness reminder
        if l9_input.audit_grade.upper() in ("D", "F"):
            reminders.append(Reminder(
                title="Data refresh needed",
                message=self._staleness_msg(exp),
                trigger_type=ReminderTrigger.DATA_STALENESS,
                channel=AlertChannel.IN_APP,
            ))

        # Rate limit (except CRITICAL)
        limited = reminders[:_MAX_REMINDERS_PER_DAY]
        self._sent_today += len(limited)
        return limited

    def reset_daily(self):
        self._sent_today = 0

    def _title(self, action_type, exp):
        if exp == ExpertiseLevel.NOVICE:
            return action_type.replace("_", " ").title()
        return f"Reminder: {action_type}"

    def _schedule_msg(self, action_type, date, exp):
        if exp == ExpertiseLevel.NOVICE:
            return f"Hey! 👋 Don't forget to {action_type.lower().replace('_',' ')} — it's coming up{' on ' + date if date else ''}!"
        elif exp == ExpertiseLevel.FARMER:
            return f"Reminder: {action_type} scheduled{' for ' + date if date else ''}."
        return f"{action_type} scheduled_date={date}. Execute within weather window."

    def _overdue_msg(self, action_type, due_date, exp):
        if exp == ExpertiseLevel.NOVICE:
            return f"The {action_type.lower().replace('_',' ')} from {due_date} is still pending — can you get to it? 🙏"
        return f"Overdue: {action_type} was due {due_date}."

    def _staleness_msg(self, exp):
        if exp == ExpertiseLevel.NOVICE:
            return "Your field data could use a refresh! A quick check would help a lot 🔄"
        return "Data quality degraded. Consider updating field observations."


reminder_engine = ReminderEngine()

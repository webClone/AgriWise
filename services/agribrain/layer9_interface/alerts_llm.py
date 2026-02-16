"""
Layer 9.4: Alert Composer.
Generates concise, actionable notifications.
"""

from typing import Dict, Any

class AlertComposer:
    
    def compose_alert(self, 
                      trigger_event: str, 
                      action: Dict[str, Any], 
                      trust_tier: str) -> Dict[str, str]:
        """
        create Push/SMS content.
        Pattern: Trigger + Action + Deadline + Confidence.
        """
        action_name = action.get("action", "Check Field")
        window = action.get("scheduled_date", "Today")
        
        # Templates based on trigger
        if "Heatwave" in trigger_event:
            push = f"🔥 Heatwave Alert. {action_name} by {window} to save crop."
        elif "Disease" in trigger_event:
            push = f"🦠 Disease Risk Rising. {action_name} recommended."
        elif "Wind" in trigger_event:
            push = f"💨 High Wind Alert. Postpone spraying."
        else:
            push = f"Alert: {trigger_event}. Action: {action_name}."
            
        # Add Confidence if low
        if trust_tier == "Low":
            push += " (Low Confidence - Verify first)"
            
        return {
            "push_notification": push,
            "sms": push, # SMS usually same or shorter
            "email_subject": f"Action Required: {trigger_event} detected",
            "email_body": f"Event: {trigger_event}\nRecommendation: {action_name}\nTiming: {window}\nConfidence: {trust_tier}"
        }

# Singleton
alert_composer = AlertComposer()

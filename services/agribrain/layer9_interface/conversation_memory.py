from typing import List, Dict, Any, Optional
import json

class ConversationMemoryManager:
    """
    Handles structured conversation history, summarizing past turns,
    and managing the Farmer Profile memory for multi-turn awareness.
    """

    @staticmethod
    def build_history_summary(history: Optional[List[Dict[str, str]]]) -> str:
        """
        Compresses the raw chat history into a structured summary for the LLM context.
        Instead of just truncating, it highlights the flow of the conversation.
        """
        if not history or len(history) == 0:
            return "- No recent history."

        lines = []
        
        # Keep full context for the very last turn, but summarize older turns
        for i, msg in enumerate(history):
            role = msg.get("role", "user").upper()
            content = msg.get("content", "").replace("\n", " ").strip()
            
            is_last_turn = (i == len(history) - 1)
            
            if is_last_turn:
                lines.append(f"- {role} (Latest): {content}")
            else:
                # Truncate older turns but keep them recognizable
                if len(content) > 100:
                    content = content[:97] + "..."
                lines.append(f"- {role} (Previous): {content}")
                
        return "\n".join(lines)

    @staticmethod
    def format_farmer_profile(memory_obj: Any) -> str:
        """
        Formats the persistent Farmer Profile (experience level, known traits).
        """
        if not memory_obj:
            return "[FARMER PROFILE]: No profile available."
            
        try:
            exp_level = getattr(memory_obj, "experience_level", "farmer")
            known_context = getattr(memory_obj, "known_context", {})
            open_loops = getattr(memory_obj, "open_loops", [])
            asked_fups = getattr(memory_obj, "asked_followups", [])
            
            profile_lines = [
                "[FARMER PROFILE / LONG-TERM MEMORY]",
                f"- Assumed Experience Level: {exp_level.upper()}",
                f"- Known Field Traits & User Context: {json.dumps(known_context)}",
            ]
            
            if open_loops:
                profile_lines.append(f"- Open Loops (Tasks pending user confirmation): {json.dumps(open_loops)}")
            if asked_fups:
                recent_fups = asked_fups[-3:] if isinstance(asked_fups, list) else []
                profile_lines.append(f"- Recently Asked Follow-ups (Do not repeat these): {json.dumps(recent_fups)}")
                
            return "\n".join(profile_lines)
            
        except Exception as e:
            return f"[FARMER PROFILE] Error formatting profile: {e}"

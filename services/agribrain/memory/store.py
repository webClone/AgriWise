
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

MEMORY_DIR = "data/memory"
PROFILES_DIR = os.path.join(MEMORY_DIR, "plots")
SESSIONS_DIR = os.path.join(MEMORY_DIR, "sessions")

class MemoryStore:
    def __init__(self):
        os.makedirs(PROFILES_DIR, exist_ok=True)
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        
    def _get_profile_path(self, plot_id: str) -> str:
        return os.path.join(PROFILES_DIR, f"{plot_id}.json")
        
    def _get_session_path(self, conversation_id: str) -> str:
        return os.path.join(SESSIONS_DIR, f"{conversation_id}.json")

    def get_profile(self, plot_id: str) -> Dict[str, Any]:
        """
        Load or initialize a plot profile.
        """
        path = self._get_profile_path(plot_id)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
                
        # Default Profile
        return {
            "plot_id": plot_id,
            "crop": {"type": "Unknown", "variety": "Unknown", "planting_date": None},
            "soil": {"texture": "Unknown", "drainage": "Unknown"},
            "irrigation": {"system": "Unknown", "flow_known": False},
            "farmer_prefs": {"style": "tutor", "units": "metric"},
            "observations": [], # List of {date, observation}
            "last_updated": datetime.utcnow().isoformat()
        }
        
    def update_profile(self, plot_id: str, updates: Dict[str, Any]):
        """
        Merge updates into profile. Deep merge logic for crop/soil/irrigation.
        """
        profile = self.get_profile(plot_id)
        
        # Simple Merge (improve if needed)
        if "crop" in updates: profile["crop"].update(updates["crop"])
        if "soil" in updates: profile["soil"].update(updates["soil"])
        if "irrigation" in updates: profile["irrigation"].update(updates["irrigation"])
        if "farmer_prefs" in updates: profile["farmer_prefs"].update(updates["farmer_prefs"])
        if "observations" in updates:
             # Append or Replace? Append is safer for history.
             # Assume updates["observations"] is a list of NEW observations
             profile["observations"].extend(updates["observations"])
             
        profile["last_updated"] = datetime.utcnow().isoformat()
        
        with open(self._get_profile_path(plot_id), "w") as f:
            json.dump(profile, f, indent=2)
            
    def get_session(self, conversation_id: str) -> Dict[str, Any]:
        """
        Load or initialize a session.
        """
        path = self._get_session_path(conversation_id)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
                
        return {
            "conversation_id": conversation_id,
            "turns": [], # List of {user, assistant, timestamp}
            "summary": "",
            "started_at": datetime.utcnow().isoformat()
        }
        
    def append_turn(self, conversation_id: str, user_query: str, assistant_response: Dict[str, Any]):
        """
        Add a turn to the session history.
        Assistant response is stored as full JSON object (ARF-v1 structure).
        """
        session = self.get_session(conversation_id)
        turn = {
            "timestamp": datetime.utcnow().isoformat(),
            "user": user_query,
            "assistant": assistant_response # Structured
        }
        session["turns"].append(turn)
        
        # Trim history if too long? For now keep last 20.
        if len(session["turns"]) > 20:
             session["turns"] = session["turns"][-20:]
             
        with open(self._get_session_path(conversation_id), "w") as f:
            json.dump(session, f, indent=2)


import json
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from layer0.data_gateway.storage_manager import _get_db

logger = logging.getLogger("agribrain.memory.store")

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
        Load a plot profile. Integrates with the MongoDB PlotDNA and PlotObservation archives.
        Falls back to local file store if MongoDB is down.
        """
        profile = {
            "plot_id": plot_id,
            "crop": {"type": "Unknown", "variety": "Unknown", "planting_date": None},
            "soil": {"texture": "Unknown", "drainage": "Unknown"},
            "irrigation": {"system": "Unknown", "flow_known": False},
            "farmer_prefs": {"style": "tutor", "units": "metric"},
            "observations": [], 
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

        # 1. Load from local file store if exists
        path = self._get_profile_path(plot_id)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    local_profile = json.load(f)
                    # Merge local data
                    for key in ["crop", "soil", "irrigation", "farmer_prefs"]:
                        if key in local_profile:
                            profile[key].update(local_profile[key])
                    if "observations" in local_profile:
                        profile["observations"] = local_profile["observations"]
            except Exception as e:
                logger.debug("[MEMORY_STORE] Local read failed: %s", e)

        # 2. Enrich from MongoDB PlotDNA & PlotObservation
        db = _get_db()
        if db is not None:
            try:
                # Query PlotDNA for crop & soil traits
                dna = db.PlotDNA.find_one({"plotId": plot_id})
                if dna:
                    crop_type = dna.get("cropType")
                    if crop_type:
                        profile["crop"]["type"] = crop_type
                    
                    created_at = dna.get("createdAt")
                    if created_at:
                        if isinstance(created_at, datetime):
                            profile["crop"]["planting_date"] = created_at.isoformat()
                        else:
                            profile["crop"]["planting_date"] = str(created_at)

                    # Get soil texture from pedogenic memory if calculated
                    advanced = dna.get("advanced_phenometrics", {})
                    texture = advanced.get("pedogenic_memory", {}).get("texture_class")
                    if texture:
                        profile["soil"]["texture"] = texture

                # Query recent observations from warm tier (PlotObservation)
                recent_obs = list(db.PlotObservation.find(
                    {"plotId": plot_id, "isReliable": True}
                ).sort("obsDate", -1).limit(10))
                
                if recent_obs:
                    profile["observations"] = []
                    for obs in recent_obs:
                        obs_date = obs.get("obsDate")
                        date_str = obs_date.isoformat() if isinstance(obs_date, datetime) else str(obs_date)
                        profile["observations"].append({
                            "date": date_str,
                            "source": obs.get("source"),
                            "obs_type": obs.get("obsType"),
                            "features": {
                                "ndvi": obs.get("ndvi"),
                                "vv": obs.get("vv"),
                                "soilMoisture": obs.get("soilMoisture")
                            }
                        })
            except Exception as e:
                logger.debug("[MEMORY_STORE] MongoDB enrichment failed: %s", e)

        return profile
        
    def update_profile(self, plot_id: str, updates: Dict[str, Any]):
        """
        Merge updates into profile. Persists to local file and updates MongoDB.
        """
        profile = self.get_profile(plot_id)
        
        # Merge local fields
        if "crop" in updates: 
            profile["crop"].update(updates["crop"])
        if "soil" in updates: 
            profile["soil"].update(updates["soil"])
        if "irrigation" in updates: 
            profile["irrigation"].update(updates["irrigation"])
        if "farmer_prefs" in updates: 
            profile["farmer_prefs"].update(updates["farmer_prefs"])
        if "observations" in updates:
            profile["observations"].extend(updates["observations"])
             
        profile["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        # Save to local file
        try:
            with open(self._get_profile_path(plot_id), "w") as f:
                json.dump(profile, f, indent=2)
        except Exception as e:
            logger.warning("[MEMORY_STORE] Local write failed: %s", e)
            
        # Update in MongoDB (PlotDNA)
        db = _get_db()
        if db is not None:
            try:
                db.PlotDNA.update_one(
                    {"plotId": plot_id},
                    {
                        "$set": {
                            "cropType": profile["crop"]["type"],
                            "lastUpdated": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True
                )
            except Exception as e:
                logger.debug("[MEMORY_STORE] MongoDB sync failed: %s", e)
            
    def get_session(self, conversation_id: str) -> Dict[str, Any]:
        """
        Load or initialize a session from local storage.
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
            "turns": [], 
            "summary": "",
            "started_at": datetime.now(timezone.utc).isoformat()
        }
        
    def append_turn(self, conversation_id: str, user_query: str, assistant_response: Dict[str, Any]):
        """
        Add a turn to the session history.
        """
        session = self.get_session(conversation_id)
        turn = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user_query,
            "assistant": assistant_response
        }
        session["turns"].append(turn)
        
        if len(session["turns"]) > 20:
            session["turns"] = session["turns"][-20:]
             
        try:
            with open(self._get_session_path(conversation_id), "w") as f:
                json.dump(session, f, indent=2)
        except Exception as e:
            logger.warning("[MEMORY_STORE] Local session write failed: %s", e)

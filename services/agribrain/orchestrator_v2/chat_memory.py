import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any

MEMORY_DIR = os.path.join(os.getcwd(), "data", "chat_memory")

@dataclass
class ChatMemory:
    # Farmer Profile
    experience_level: str = "INTERMEDIATE" # BEGINNER | INTERMEDIATE | EXPERT
    language_preference: str = "EN"
    units: str = "metric"
    
    # Plot Context (learned via chat)
    known_context: Dict[str, Any] = field(default_factory=dict) # e.g. irrigation_type, soil_type, planting_date
    
    # Conversation State
    last_questions: List[str] = field(default_factory=list) # summarize last few
    last_diagnoses_shown: List[str] = field(default_factory=list)
    asked_followups: List[str] = field(default_factory=list)
    
    # Open Loops (Pending Verifications)
    open_loops: List[str] = field(default_factory=list)

def _ensure_dir():
    os.makedirs(MEMORY_DIR, exist_ok=True)

def load_memory(plot_id: str) -> ChatMemory:
    _ensure_dir()
    filepath = os.path.join(MEMORY_DIR, f"{plot_id}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ChatMemory(**data)
        except Exception as e:
            print(f"Error loading ChatMemory for {plot_id}: {e}")
    
    # Fallback to defaults
    return ChatMemory()

def save_memory(plot_id: str, memory: ChatMemory):
    _ensure_dir()
    filepath = os.path.join(MEMORY_DIR, f"{plot_id}.json")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(memory), f, indent=2)
    except Exception as e:
        print(f"Error saving ChatMemory for {plot_id}: {e}")

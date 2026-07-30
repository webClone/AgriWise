"""
AI Organism Core Orchestrator
Routes user queries to specialized AIs based on intent classification.
Fallback chain: Specialized AI → AgriBrain Heuristics → LLM
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Dataset logging path
DATASET_DIR = Path(__file__).parent.parent / "datasets"
DATASET_DIR.mkdir(exist_ok=True)

class AIOrchestrator:
    """
    LLM Conductor: Routes queries to specialized AIs.
    Logs all interactions for future DL training.
    """
    
    # Intent → AI modules mapping
    INTENT_ROUTING = {
        "disease": ["disease_risk", "leaf_vision", "microclimate"],
        "pest": ["pest_dynamics", "microclimate"],
        "irrigation": ["water_stress", "soil_observation", "phenology"],
        "spray": ["spray_window", "microclimate"],
        "yield": ["yield_prediction", "ndvi_forecast", "phenology"],
        "fertilizer": ["nutrient_status", "fertilization", "soil_observation"],
        "weather": ["microclimate", "drought_risk"],
        "growth": ["phenology", "crop_observation"],
        "soil": ["soil_observation", "nutrient_status"],
        "ndvi": ["crop_observation", "ndvi_forecast"],
    }
    
    # Keywords for intent classification
    INTENT_KEYWORDS = {
        "disease": ["disease", "sick", "yellow", "spots", "blight", "fungus", "rot", "wilt", "infection"],
        "pest": ["pest", "insect", "bug", "aphid", "worm", "caterpillar", "mite"],
        "irrigation": ["water", "irrigate", "irrigation", "dry", "thirsty", "moisture"],
        "spray": ["spray", "pesticide", "fungicide", "herbicide", "application"],
        "yield": ["yield", "harvest", "production", "ton", "kg/ha"],
        "fertilizer": ["fertilizer", "nutrient", "nitrogen", "phosphorus", "potassium", "npk"],
        "weather": ["weather", "rain", "temperature", "wind", "forecast"],
        "growth": ["growth", "stage", "flowering", "maturity", "emergence"],
        "soil": ["soil", "clay", "sand", "ph", "texture"],
        "ndvi": ["ndvi", "vegetation", "health", "greenness", "satellite"],
    }
    
    def __init__(self):
        self.registered_ais: Dict[str, Any] = {}
        self.interaction_log: List[Dict] = []
    
    def register_ai(self, name: str, ai_instance: Any):
        """Register a specialized AI module."""
        self.registered_ais[name] = ai_instance
    
    def classify_intent(self, query: str) -> List[str]:
        """
        Classify user intent from natural language query.
        Returns list of matching intents sorted by confidence.
        """
        query_lower = query.lower()
        intent_scores = {}
        
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                intent_scores[intent] = score
        
        # Sort by score descending
        sorted_intents = sorted(intent_scores.items(), key=lambda x: -x[1])
        return [intent for intent, _ in sorted_intents]
    
    def route_query(self, query: str, context: Dict) -> Dict[str, Any]:
        """
        Route query to appropriate specialized AIs.
        Returns aggregated results from all relevant AIs.
        """
        intents = self.classify_intent(query)
        
        if not intents:
            # No specific intent detected, use general knowledge
            return {
                "routed_to": ["agronomic_knowledge"],
                "results": {},
                "fallback": True
            }
        
        # Get AI modules for top intent
        primary_intent = intents[0]
        ai_modules = self.INTENT_ROUTING.get(primary_intent, [])
        
        results = {}
        for ai_name in ai_modules:
            if ai_name in self.registered_ais:
                try:
                    ai = self.registered_ais[ai_name]
                    result = ai.predict(context)
                    results[ai_name] = result
                except Exception as e:
                    results[ai_name] = {"error": str(e), "fallback": True}
            else:
                results[ai_name] = {"status": "not_implemented", "fallback": True}
        
        # Log interaction for dataset building
        self._log_interaction(query, intents, context, results)
        
        return {
            "detected_intents": intents,
            "routed_to": ai_modules,
            "results": results,
            "fallback": all(r.get("fallback", False) for r in results.values())
        }
    
    def _log_interaction(self, query: str, intents: List[str], context: Dict, results: Dict):
        """Log interaction for building training datasets."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "detected_intents": intents,
            "context": context,
            "results": results
        }
        self.interaction_log.append(log_entry)
        
        # Persist to disk periodically
        if len(self.interaction_log) >= 10:
            self._flush_logs()
    
    def _flush_logs(self):
        """Flush interaction logs to disk for dataset building."""
        if not self.interaction_log:
            return
            
        log_file = DATASET_DIR / f"interactions_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a") as f:
            for entry in self.interaction_log:
                f.write(json.dumps(entry) + "\n")
        
        self.interaction_log = []


class BaseSpecializedAI:
    """
    Base class for all specialized AIs.
    Provides common functionality for prediction and dataset logging.
    Uses VersionedDataset for proper data engineering.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.model = None  # Will hold trained DL model when available
        
        # Use versioned dataset for proper data engineering
        from core.data_layer import DATASETS
        self.dataset = DATASETS.get(name)
    
    def predict(self, context: Dict) -> Dict[str, Any]:
        """
        Make prediction. Override in subclass.
        Falls back to heuristics if no trained model.
        """
        if self.model is not None:
            return self._dl_predict(context)
        else:
            return self._heuristic_predict(context)
    
    def _dl_predict(self, context: Dict) -> Dict[str, Any]:
        """Deep learning prediction. Override when model is trained."""
        raise NotImplementedError("DL model not trained yet")
    
    def _heuristic_predict(self, context: Dict) -> Dict[str, Any]:
        """Rule-based fallback. Override in subclass."""
        return {"status": "no_heuristic", "fallback": True}
    
    def log_sample(self, inputs: Dict, output: Dict, label: Optional[Dict] = None):
        """Log a sample to versioned dataset for future DL training."""
        if self.dataset:
            self.dataset.append({"inputs": inputs, "output": output}, label)
    
    def get_dataset_size(self) -> int:
        """Get current dataset size."""
        if self.dataset:
            return self.dataset.get_sample_count()
        return 0


# Global orchestrator instance
orchestrator = AIOrchestrator()

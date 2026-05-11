import json
import os
import requests
from typing import List, Dict, Any, Optional

def route_intent(query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    Fast, single-pass LLM to determine intent, target layers, and relevant engines.
    Returns a dictionary with keys: intent_type, layers, engines
    """
    if not query:
        return {"intent_type": "GENERAL", "layers": [], "engines": []}
        
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    if not OPENROUTER_API_KEY:
        # Fallback to keyword heuristics if no key
        return _fallback_routing(query)
        
    # Use a faster, cheaper model for routing to ensure <1s latency
    model = "meta-llama/llama-3.3-70b-instruct:free"
    
    prompt = f"""
    Analyze the user's query and the conversation history to determine the intent and which AgriBrain engines should be used to answer it.
    
    Query: "{query}"
    
    Return ONLY a JSON object with the following schema:
    {{
        "intent_type": "string (e.g. DIAGNOSTIC, EXPLANATION, ADVICE, GREETING)",
        "layers": ["string (e.g. L0, L1, L2, L3, L10)"],
        "engines": ["string (e.g. WaterStressEngine, NDVICalculationEngine, KalmanFilterEngine)"]
    }}
    
    Common Engines:
    - L0: ET0CalculationEngine, OpenMeteoEngine, RainGaugeEngine
    - L1: KalmanFilterEngine, Layer1FusionEngine, OpticalAssimilationEngine, SARAssimilationEngine
    - L2: VegetationIntelligenceEngine, NDVICalculationEngine, PhenologyEngine, CanopyAnalysisEngine
    - L3: WaterStressEngine, SoilWaterBalanceEngine, DiagnosisEngine
    - L4-8: CropDemandUptakeEngine, NitrogenDeficiencyEngine, NutrientInferenceEngine, RiskCompositeEngine, ClimateShockEngine, IPMCascadeEngine
    - L5: BioThreatInferenceEngine, WeatherPressureEngine, SpreadSignatureEngine, RemoteSignatureEngine, ResponsePlannerEngine
    - L10: SIREQualityGateEngine, DriverWeightEngine, DegradationModeDetector, ExplainabilityEngine
    
    Examples:
    - "How is my nitrogen deficit?" -> engines: ["NutrientInferenceEngine", "NitrogenDeficiencyEngine", "CropDemandUptakeEngine"]
    - "Nutrient analysis" -> engines: ["NutrientInferenceEngine", "NitrogenDeficiencyEngine"]
    - "Is there a risk of disease or fungus?" -> engines: ["BioThreatInferenceEngine", "WeatherPressureEngine", "RemoteSignatureEngine"]
    - "What's the water stress today?" -> engines: ["WaterStressEngine", "ET0CalculationEngine", "SoilWaterBalanceEngine"]
    - "Is the SAR data reliable?" -> engines: ["KalmanFilterEngine", "Layer1FusionEngine", "SIREQualityGateEngine"]
    """
    
    try:
        data = {}
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
        except Exception as e:
            print(f"DEBUG: IntentRouter OpenRouter error: {e}")
            
        if not data.get("choices") and os.environ.get("GEMINI_API_KEY"):
            try:
                gemini_resp = requests.post(
                    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    headers={"Authorization": f"Bearer {os.environ.get('GEMINI_API_KEY')}", "Content-Type": "application/json"},
                    json={
                        "model": "gemini-flash-latest",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    },
                    timeout=10
                )
                if gemini_resp.status_code == 200:
                    data = gemini_resp.json()
                else:
                    print(f"[LLM] Gemini fallback returned {gemini_resp.status_code}: {gemini_resp.text}")
            except Exception as e:
                print(f"[LLM] Gemini fallback failed: {e}")
                
        content = data["choices"][0]["message"]["content"]
        
        # Clean up in case of markdown wrapping
        content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        
        return {
            "intent_type": parsed.get("intent_type", "GENERAL"),
            "layers": parsed.get("layers", []),
            "engines": parsed.get("engines", [])
        }
    except Exception as e:
        print(f"DEBUG: IntentRouter failed, falling back. Error: {e}")
        return _fallback_routing(query)

def _fallback_routing(query: str) -> Dict[str, Any]:
    """Simple keyword matching fallback"""
    q = query.lower()
    engines = set()
    layers = set()
    intent = "GENERAL"
    
    if "water" in q or "et0" in q or "irrigation" in q:
        engines.update(["WaterStressEngine", "ET0CalculationEngine"])
        layers.update(["L0", "L3"])
        intent = "EXPLANATION"
    if "ndvi" in q or "vegetation" in q or "canopy" in q:
        engines.update(["VegetationIntelligenceEngine", "NDVICalculationEngine"])
        layers.update(["L2"])
        intent = "DIAGNOSTIC"
    if "fusion" in q or "kalman" in q or "sar" in q:
        engines.update(["KalmanFilterEngine", "Layer1FusionEngine"])
        layers.update(["L1"])
        intent = "EXPLANATION"
    if "nutrient" in q or "nitrogen" in q or "fertilizer" in q:
        engines.update(["NutrientInferenceEngine", "NitrogenDeficiencyEngine", "CropDemandUptakeEngine"])
        layers.update(["L4-8"])
        intent = "DIAGNOSTIC"
    if "disease" in q or "fungus" in q or "pest" in q or "weed" in q or "biotic" in q:
        engines.update(["BioThreatInferenceEngine", "WeatherPressureEngine", "SpreadSignatureEngine"])
        layers.update(["L5"])
        intent = "DIAGNOSTIC"
    if "risk" in q or "climate" in q or "shock" in q:
        engines.update(["RiskCompositeEngine", "ClimateShockEngine"])
        layers.update(["L4-8"])
        intent = "EXPLANATION"
        
    return {
        "intent_type": intent,
        "layers": list(layers),
        "engines": list(engines)
    }

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
        
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    
    if not use_local and not OPENROUTER_API_KEY and not GROQ_API_KEY and not os.environ.get("GEMINI_API_KEY"):
        # Fallback to keyword heuristics if no key and not in local mode
        return _fallback_routing(query)
        
    prompt = f"""
    Analyze the user's query and the conversation history to determine the intent and which AgriBrain engines should be used to answer it.
    
    Query: "{query}"
    
    Return ONLY a JSON object with the following schema:
    {{
        "intent_type": "string (e.g. DIAGNOSTIC, EXPLANATION, ADVICE, GREETING)",
        "layers": ["string (e.g. L0, L1, L2, L3, L10)"],
        "engines": ["string (e.g. WaterStressEngine, NDVICalculationEngine, KalmanFilterEngine)"]
    }}
    
    Common Engines by Layer:
    - L0 (Perception/Env): DailyAssimilationEngine, KalmanFilterEngine, Sentinel2QA, Sentinel1QA, ImageQAEngine, ObservationModel, EnvironmentalEngine, SourceAvailability, SensorDriftDetector, AssimilationAuditor
    - L1 (Fusion/Calib): Layer1FusionEngine, OpticalAssimilationEngine, SARAssimilationEngine, GenerativeInversionEngine, PedogenicMemory, PhenologicalFingerprint, StressChronology, HydrologicalResilience, MicroclimateSPAC
    - L2 (Veg Intelligence): VegetationIntelligenceEngine, TemporalAnomalyEngine, CropIdentificationEngine, BayesianCropClassifier, GrowthCurveEngine, PhenologyEngine
    - L3 (Decision): DecisionIntelligenceEngine, DiagnosisEngine, DecisionFeatures, WaterBudget, PolicyEngine, CropProfile
    - L4 (Nutrients): FertilizerOptimizer, NitrogenDeficiencyEngine, BiologicalFixationEngine, CropDemandUptakeEngine, EnvironmentalLossEngine, NutrientInferenceEngine, MicronutrientChemistryEngine, NUEEngine, NutrientInteractionEngine, OptimizationEngine, PhosphorusSorptionEngine, PhotosynthesisNUEEngine, PlanningEngine, ResidualCreditEngine, SalinityEngine, CECEngine, LimingEngine, ComplianceGate
    - L5 (BioThreat): OutbreakPredictionEngine, VisualDetectionEngine, WeatherRiskEngine, BiophysicalCanopyEnergyBalanceSolver, ChemicalDegradationPredictor, SprayDriftRandomForestRegressor, MultiHeadAttentionGeneticsClassifier, BioThreatInferenceEngine, RemoteSignatureBuilder, ResponsePlanner, SporeDispersalEngine
    - L6 (Execution): InterventionSynthesis, ResourceFeasibilityAnalyzer, VPDSprayWindowCalculator, CarbonSequestrationModel, NitrogenLeachingModel, OutcomesMetricsCalculator, DagRunner, CalibrationProposalEngine
    - L7 (Season Planning): ZoneSuitability, MicroclimateCalculator, BioticRiskPlanner, CultivarLibrary, ClimateResilienceModel, CropRotationPlanner, EconomicsEvaluator, PedExecutionPlanner, PlantingWindowCalculator, SoilWorkabilityCalculator, WaterFeasibilityCalculator, YieldDistributionCalculator
    - L8 (Prescriptive): ActionRankingEngine, FeedbackLoop, ConstraintScheduler, ZonePrioritizer, AdoptionModelEngine, CognitiveLoadEngine, EnvironmentalRiskEngine, FramingEngine, IPMCascadeEngine, SalinityLeachingEngine, CropCoolingEngine, SprayDriftGateEngine, TillageCompactionEngine, LodgingPGREngine, VolatilizationInhibitorEngine, FrostSprinklingEngine
    - L10 (SIRE): PremiumExplainabilityEngine, ZoneExtractor, KMeansZoneSegregation, ProductExportEngine, VegetationSurfaceGenerator, WaterStressSurfaceGenerator, SalinitySurfaceGenerator, NutrientSurfaceGenerator, YieldSurfaceGenerator, DiseaseSurfaceGenerator, TemporalSurfaceGenerator, ExecutionSurfaceGenerator, CanopyMaskEngine, RowDetectionEngine, CrownDetectionEngine

    Examples:
    - "How is my nitrogen deficit?" -> engines: ["NitrogenDeficiencyEngine", "CropDemandUptakeEngine", "NutrientInferenceEngine"]
    - "Is there a risk of disease or fungus?" -> engines: ["OutbreakPredictionEngine", "BioThreatInferenceEngine", "SporeDispersalEngine"]
    - "What's the water stress today?" -> engines: ["DiagnosisEngine", "WaterBudget", "ET0CalculationEngine"]
    - "Is the SAR data reliable?" -> engines: ["SARAssimilationEngine", "Layer1FusionEngine", "PremiumExplainabilityEngine"]
    """
    
    if use_local:
        # Avoid slow sequential VLM queries on local/CPU servers.
        # Fallback keyword matching is instant, reliable, and covers all engines.
        return _fallback_routing(query)

    try:
        data = {}
        try:
            if GROQ_API_KEY:
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant", # or compound-mini
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    },
                    timeout=10
                )
            elif OPENROUTER_API_KEY:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "meta-llama/llama-3.3-70b-instruct:free",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    },
                    timeout=10
                )
            if response and response.status_code == 200:
                data = response.json()
        except Exception as e:
            print(f"DEBUG: IntentRouter API error: {e}")
            
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
    """Simple keyword matching fallback covering all 10 layers & engines"""
    q = query.lower()
    engines = set()
    layers = set()
    intent = "GENERAL"
    
    # L0 (Environment & Perception)
    if any(k in q for k in ["sensor", "weather", "meteo", "temperature", "rain", "precipitation", "wind", "humidity", "openweather", "open-meteo"]):
        engines.update(["EnvironmentalEngine", "SourceAvailability", "SensorDriftDetector"])
        layers.add("L0")
        intent = "DATA_QUERY"
    if any(k in q for k in ["photo", "drone", "image", "blur", "exposure"]):
        engines.update(["ImageQAEngine", "ObservationModel"])
        layers.add("L0")
        intent = "DIAGNOSTIC"

    # L1 (Data Fusion & Calibration)
    if any(k in q for k in ["fusion", "kalman", "assimilation", "dna", "sequencing", "inversion", "spac", "pedogenic", "chronology", "fingerprint"]):
        engines.update(["Layer1FusionEngine", "OpticalAssimilationEngine", "SARAssimilationEngine", "GenerativeInversionEngine", "PedogenicMemory", "PhenologicalFingerprint", "StressChronology", "HydrologicalResilience", "MicroclimateSPAC"])
        layers.add("L1")
        intent = "EXPLANATION"

    # L2 (Vegetation Intelligence)
    if any(k in q for k in ["ndvi", "evi", "canopy", "vegetation", "bbch", "growth", "phenology", "logistic", "savitzky", "smooth", "vigor", "classifier"]):
        engines.update(["VegetationIntelligenceEngine", "TemporalAnomalyEngine", "CropIdentificationEngine", "BayesianCropClassifier", "GrowthCurveEngine", "PhenologyEngine"])
        layers.add("L2")
        intent = "DIAGNOSTIC"

    # L3 (Decision & Diagnostics)
    if any(k in q for k in ["diagnose", "diagnosis", "et0", "penman", "evapotranspiration", "water budget", "depletion", "esi", "bayesian belief"]):
        engines.update(["DecisionIntelligenceEngine", "DiagnosisEngine", "DecisionFeatures", "WaterBudget", "PolicyEngine"])
        layers.add("L3")
        intent = "DIAGNOSTIC"

    # L4 (Nutrient Dynamics)
    if any(k in q for k in ["nutrient", "nitrogen", "phosphorus", "potassium", "npk", "urea", "vra", "fertilizer", "deficiency", "fixation", "liming", "cec", "mitscherlich"]):
        engines.update(["FertilizerOptimizer", "NitrogenDeficiencyEngine", "BiologicalFixationEngine", "CropDemandUptakeEngine", "EnvironmentalLossEngine", "NutrientInferenceEngine", "MicronutrientChemistryEngine", "NUEEngine", "NutrientInteractionEngine", "OptimizationEngine", "PhosphorusSorptionEngine", "PhotosynthesisNUEEngine", "PlanningEngine", "ResidualCreditEngine", "SalinityEngine", "CECEngine", "LimingEngine"])
        layers.add("L4")
        intent = "DIAGNOSTIC"

    # L5 (BioThreat)
    if any(k in q for k in ["pathogen", "disease", "pest", "weed", "blight", "septoria", "spore", "dispersal", "fungicide", "spray", "drift", "resistance"]):
        engines.update(["OutbreakPredictionEngine", "VisualDetectionEngine", "WeatherRiskEngine", "BiophysicalCanopyEnergyBalanceSolver", "ChemicalDegradationPredictor", "SprayDriftRandomForestRegressor", "MultiHeadAttentionGeneticsClassifier", "BioThreatInferenceEngine", "RemoteSignatureBuilder", "ResponsePlanner", "SporeDispersalEngine"])
        layers.add("L5")
        intent = "DIAGNOSTIC"

    # L6 (Execution Feasibility)
    if any(k in q for k in ["feasibility", "machinery", "conflict", "vpd", "spray window", "leaching", "sequestration", "carbon", "tillage", "dag", "task"]):
        engines.update(["InterventionSynthesis", "ResourceFeasibilityAnalyzer", "VPDSprayWindowCalculator", "CarbonSequestrationModel", "NitrogenLeachingModel", "OutcomesMetricsCalculator", "DagRunner", "CalibrationProposalEngine"])
        layers.add("L6")
        intent = "EXECUTION"

    # L7 (Season Planning)
    if any(k in q for k in ["suitability", "rotation", "legume", "economic", "roi", "planting window", "workability", "seedbed"]):
        engines.update(["ZoneSuitability", "MicroclimateCalculator", "BioticRiskPlanner", "CultivarLibrary", "ClimateResilienceModel", "CropRotationPlanner", "EconomicsEvaluator", "PedExecutionPlanner", "PlantingWindowCalculator", "SoilWorkabilityCalculator", "WaterFeasibilityCalculator", "YieldDistributionCalculator"])
        layers.add("L7")
        intent = "PLANNING"

    # L8 (Prescriptive Actions)
    if any(k in q for k in ["prescribe", "prescription", "adoption", "fatigue", "cooling", "lodging", "pgr", "volatilization", "nbpt", "frost", "sprinkling", "buffer zone"]):
        engines.update(["ActionRankingEngine", "FeedbackLoop", "ConstraintScheduler", "ZonePrioritizer", "AdoptionModelEngine", "CognitiveLoadEngine", "EnvironmentalRiskEngine", "FramingEngine", "IPMCascadeEngine", "SalinityLeachingEngine", "CropCoolingEngine", "SprayDriftGateEngine", "TillageCompactionEngine", "LodgingPGREngine", "VolatilizationInhibitorEngine", "FrostSprinklingEngine"])
        layers.add("L8")
        intent = "DECISION"

    # L10 (SIRE Spatial Maps)
    if any(k in q for k in ["var", "value at risk", "sire", "contour", "raster", "geojson", "mapbox", "k-means", "cluster", "crown", "row detection"]):
        engines.update(["PremiumExplainabilityEngine", "ZoneExtractor", "KMeansZoneSegregation", "ProductExportEngine", "VegetationSurfaceGenerator", "WaterStressSurfaceGenerator", "SalinitySurfaceGenerator", "NutrientSurfaceGenerator", "YieldSurfaceGenerator", "DiseaseSurfaceGenerator", "TemporalSurfaceGenerator", "ExecutionSurfaceGenerator", "CanopyMaskEngine", "RowDetectionEngine", "CrownDetectionEngine"])
        layers.add("L10")
        intent = "EXPLANATION"

    return {
        "intent_type": intent,
        "layers": list(layers),
        "engines": list(engines)
    }

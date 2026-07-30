"""
adaptive_prompt_router.py - Intelligent Prompt Strategy Selection
==================================================================

Analyzes incoming queries and routes them to the optimal prompting
strategy for Gemma 4 4B:

  1. DIRECT:     Simple questions → single LLM call (fast, <15s)
  2. COT:        Complex reasoning → 3-step Extract→Reason→Respond (~45s)
  3. KNOWLEDGE:  Factual lookup → knowledge graph first, LLM for formatting
  4. CACHED:     Repeated/similar → semantic cache hit (<1s)
  5. DECOMPOSED: Multi-part queries → split, route each, fuse

Also implements:
  - Response quality gating (auto-retry on low scores)
  - Confidence calibration post-processing
  - Token budget management for 8K context window
"""

import re
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class RoutingDecision:
    """The routing strategy selected for a query."""
    strategy: str           # DIRECT, COT, KNOWLEDGE, CACHED, DECOMPOSED
    intent: str
    complexity_score: float  # 0.0 = trivial, 1.0 = very complex
    estimated_latency_ms: int
    reasoning: str
    sub_queries: Optional[List[str]] = None  # For DECOMPOSED


class AdaptivePromptRouter:
    """Routes queries to optimal prompting strategies."""

    # Simple query patterns (use DIRECT)
    SIMPLE_PATTERNS = [
        r"^(hi|hello|hey|good morning|good evening|salam|bonjour)",
        r"^what is (ndvi|ndmi|et0|sar|lai|gdd|bbch|ec|ph|cec|vpd)\b",
        r"^show me",
        r"^how much rain",
        r"^what (time|day|date|season)",
    ]

    # Complex patterns requiring COT
    COMPLEX_PATTERNS = [
        r"compare.*vs|versus|difference between",
        r"should i.*because|considering|given that",
        r"what if.*and.*then",
        r"simulate|projection|forecast.*impact",
        r"how does.*affect.*and",
        r"analyze|assessment|comprehensive|full report",
    ]

    # Knowledge-answerable patterns
    KNOWLEDGE_PATTERNS = [
        r"what is the (wilting point|field capacity|stress threshold)",
        r"what (npk|nitrogen|phosphorus|potassium) (ratio|amount|dose)",
        r"what diseases? (affect|risk|common)",
        r"what (temperature|humidity) (promotes|causes|triggers)",
        r"bbch (scale|stage|phases)",
        r"(optimal|ideal|best) (ph|temperature|moisture|planting)",
        r"symptoms of",
    ]

    def __init__(self):
        self._simple_compiled = [re.compile(p, re.IGNORECASE) for p in self.SIMPLE_PATTERNS]
        self._complex_compiled = [re.compile(p, re.IGNORECASE) for p in self.COMPLEX_PATTERNS]
        self._knowledge_compiled = [re.compile(p, re.IGNORECASE) for p in self.KNOWLEDGE_PATTERNS]

    def estimate_complexity(self, query: str, intent: str) -> float:
        """Estimate query complexity on a 0.0-1.0 scale."""
        score = 0.0
        ql = query.lower()

        # Length factor
        words = len(ql.split())
        if words > 20:
            score += 0.2
        elif words > 10:
            score += 0.1

        # Multi-part detection
        question_marks = ql.count('?')
        if question_marks > 1:
            score += 0.3
        conjunctions = len(re.findall(r'\b(and|also|plus|additionally)\b', ql))
        score += min(0.2, conjunctions * 0.1)

        # Complex reasoning needed
        for pattern in self._complex_compiled:
            if pattern.search(ql):
                score += 0.3
                break

        # Intent complexity
        intent_complexity = {
            "GREETING": 0.0, "GENERAL": 0.1, "DATA_QUERY": 0.2,
            "DIAGNOSIS": 0.4, "DECISION": 0.5, "NUTRIENT": 0.4,
            "PLANNING": 0.5, "SCENARIO": 0.6, "EXECUTION_STATUS": 0.3,
        }
        score += intent_complexity.get(intent, 0.2)

        return min(1.0, score)

    def route(self, query: str, intent: str,
              context: Optional[Dict[str, Any]] = None) -> RoutingDecision:
        """Decide the optimal prompting strategy for this query."""
        ql = query.lower().strip()

        if not ql or len(ql) < 3:
            return RoutingDecision(
                strategy="DIRECT", intent=intent, complexity_score=0.0,
                estimated_latency_ms=5000, reasoning="Empty or trivial query"
            )

        # 1. Check semantic cache first
        try:
            from layer9_interface.engines.semantic_cache import get_cache
            cache = get_cache()
            if context and cache.get(query, context):
                return RoutingDecision(
                    strategy="CACHED", intent=intent, complexity_score=0.0,
                    estimated_latency_ms=50, reasoning="Semantic cache hit"
                )
        except Exception:
            pass

        # 2. Check if knowledge graph can answer directly
        for pattern in self._knowledge_compiled:
            if pattern.search(ql):
                return RoutingDecision(
                    strategy="KNOWLEDGE", intent=intent,
                    complexity_score=0.1, estimated_latency_ms=2000,
                    reasoning="Answerable from agronomic knowledge graph"
                )

        # 3. Check if simple enough for direct prompting
        for pattern in self._simple_compiled:
            if pattern.search(ql):
                return RoutingDecision(
                    strategy="DIRECT", intent=intent,
                    complexity_score=0.1, estimated_latency_ms=15000,
                    reasoning="Simple query pattern matched"
                )

        if intent in ("GREETING",):
            return RoutingDecision(
                strategy="DIRECT", intent=intent,
                complexity_score=0.0, estimated_latency_ms=8000,
                reasoning="Greeting intent → direct response"
            )

        # 4. Check if query needs decomposition
        try:
            from layer9_interface.engines.query_decomposer import get_decomposer
            decomposer = get_decomposer()
            if decomposer.is_complex(query):
                subs = decomposer.decompose(query)
                if len(subs) > 1:
                    return RoutingDecision(
                        strategy="DECOMPOSED", intent=intent,
                        complexity_score=0.9, estimated_latency_ms=60000,
                        reasoning=f"Multi-part query decomposed into {len(subs)} sub-queries",
                        sub_queries=[s.text for s in subs]
                    )
        except Exception:
            pass

        # 5. Estimate complexity for CoT vs Direct decision
        complexity = self.estimate_complexity(query, intent)

        if complexity >= 0.5:
            return RoutingDecision(
                strategy="COT", intent=intent,
                complexity_score=complexity, estimated_latency_ms=45000,
                reasoning=f"Complex query (score={complexity:.2f}) → Chain-of-Thought"
            )
        else:
            return RoutingDecision(
                strategy="DIRECT", intent=intent,
                complexity_score=complexity, estimated_latency_ms=20000,
                reasoning=f"Moderate query (score={complexity:.2f}) → direct prompting"
            )

    def execute(self, query: str, intent: str, field_context: str,
                context_dict: Optional[Dict[str, Any]] = None,
                experience_level: str = "INTERMEDIATE") -> Dict[str, Any]:
        """Route and execute the query through the chosen strategy.
        
        Returns:
            {
                "response": str,
                "strategy": str,
                "latency_ms": float,
                "quality_score": float,
                "confidence": dict,
                "cached": bool,
            }
        """
        decision = self.route(query, intent, context_dict)
        t0 = time.time()

        result = {
            "strategy": decision.strategy,
            "intent": intent,
            "complexity": decision.complexity_score,
            "cached": False,
        }

        try:
            if decision.strategy == "CACHED":
                from layer9_interface.engines.semantic_cache import get_cache
                cached_response = get_cache().get(query, context_dict or {})
                result["response"] = cached_response or ""
                result["cached"] = True

            elif decision.strategy == "KNOWLEDGE":
                response = self._execute_knowledge(query, intent, field_context, experience_level)
                result["response"] = response

            elif decision.strategy == "COT":
                from layer9_interface.engines.chain_of_thought import get_cot_router
                cot_result = get_cot_router().run(query, field_context, experience_level)
                result["response"] = cot_result["response"]
                result["extraction"] = cot_result.get("extraction")
                result["reasoning"] = cot_result.get("reasoning")

            elif decision.strategy == "DECOMPOSED":
                response = self._execute_decomposed(query, field_context, experience_level)
                result["response"] = response

            else:  # DIRECT
                response = self._execute_direct(query, intent, field_context, experience_level)
                result["response"] = response

        except Exception as e:
            result["response"] = f"I encountered an issue processing your question. Let me try to help: {str(e)[:200]}"
            result["error"] = str(e)

        result["latency_ms"] = (time.time() - t0) * 1000

        # Post-process: quality scoring
        try:
            from layer9_interface.engines.response_ranker import score_response
            qs = score_response(result["response"], field_context, query, intent)
            result["quality_score"] = qs.overall
            result["quality_issues"] = qs.issues

            # Auto-retry if quality is too low and strategy wasn't already CoT
            if qs.should_retry and decision.strategy == "DIRECT":
                from layer9_interface.engines.chain_of_thought import get_cot_router
                cot_result = get_cot_router().run(query, field_context, experience_level)
                result["response"] = cot_result["response"]
                result["strategy"] = "COT_RETRY"
                result["latency_ms"] = (time.time() - t0) * 1000
        except Exception:
            result["quality_score"] = 0.5

        # Post-process: confidence calibration
        try:
            from layer9_interface.engines.confidence_calibrator import calibrate_confidence
            confidence = calibrate_confidence(intent, context_dict or {})
            result["confidence"] = {
                "overall": confidence.overall,
                "badge": confidence.badge,
                "reason": confidence.reason,
            }
        except Exception:
            result["confidence"] = {"overall": 0.5, "badge": "MEDIUM", "reason": "Calibration unavailable"}

        # Cache the response for future queries
        if not result.get("cached") and result.get("response") and context_dict:
            try:
                from layer9_interface.engines.semantic_cache import get_cache
                get_cache().put(query, result["response"], context_dict)
            except Exception:
                pass

        return result

    def _execute_direct(self, query: str, intent: str, field_context: str,
                        experience_level: str) -> str:
        """Execute using direct single-call prompting."""
        from layer9_interface.engines.local_vlm import local_vlm_client
        from layer9_interface.prompts.chat_advisor_prompt import get_intent_specific_prompt

        system_prompt = get_intent_specific_prompt(intent, field_context, "")
        res = local_vlm_client.query(query, system_prompt=system_prompt)
        return res.get("answer", "") if res else ""

    def _execute_knowledge(self, query: str, intent: str, field_context: str,
                           experience_level: str) -> str:
        """Execute using knowledge graph + LLM formatting.
        Pipeline-aware: extracts real crop/sensor data from context."""
        from layer9_interface.engines.agronomic_knowledge_graph import (
            lookup_crop, get_disease_risk, get_irrigation_recommendation,
            get_nutrient_recommendation, get_region_info, BBCH_STAGES,
            interpret_kalman_state, interpret_gdd_stage, calculate_pawc,
            estimate_water_balance, estimate_yield_loss, get_pipeline_layer_summary
        )
        import json, re as _re

        ql = query.lower()
        knowledge_data = {}

        # --- Extract crop from field context ---
        crop = "wheat"  # Default
        crop_match = _re.search(r"Crop Type:\s*(\w+)", field_context, _re.IGNORECASE)
        if crop_match:
            crop = crop_match.group(1).lower().replace(" ", "_")
        crop_info = lookup_crop(crop)
        if not crop_info:
            crop_info = lookup_crop("wheat")
            crop = "wheat"

        knowledge_data["crop_thresholds"] = {
            "crop": crop_info.crop,
            "wilting_point": f"{crop_info.wilting_point}%",
            "stress_threshold": f"{crop_info.stress_threshold}%",
            "field_capacity": f"{crop_info.field_capacity}%",
            "optimal_temp": f"{crop_info.optimal_growth_temp_low}-{crop_info.optimal_growth_temp_high}C",
            "heat_stress": f"{crop_info.heat_stress_temp}C",
            "frost_damage": f"{crop_info.frost_damage_temp}C",
            "optimal_ph": f"{crop_info.optimal_ph_low}-{crop_info.optimal_ph_high}",
            "potential_yield": f"{crop_info.potential_yield_t_ha[0]}-{crop_info.potential_yield_t_ha[1]} t/ha",
        }

        # --- Extract sensor values from context for knowledge functions ---
        sm_match = _re.search(r"(?:Soil Moisture|soil_moisture)[:\s]*(\d+\.?\d*)", field_context, _re.IGNORECASE)
        temp_match = _re.search(r"(?:Temperature|temp_mean|ambient_temperature)[:\s]*(\d+\.?\d*)", field_context, _re.IGNORECASE)
        hum_match = _re.search(r"(?:Humidity|humidity)[:\s]*(\d+\.?\d*)", field_context, _re.IGNORECASE)
        et0_match = _re.search(r"(?:Et0|et0_daily)[:\s]*(\d+\.?\d*)", field_context, _re.IGNORECASE)
        rain_match = _re.search(r"(?:Rain|rainfall|rain_7d)[:\s]*(\d+\.?\d*)", field_context, _re.IGNORECASE)
        stage_match = _re.search(r"(?:Growth Stage|stage)[:\s]*(\w+)", field_context, _re.IGNORECASE)

        sm = float(sm_match.group(1)) if sm_match else 28.5
        temp = float(temp_match.group(1)) if temp_match else 22.0
        hum = float(hum_match.group(1)) if hum_match else 65.0
        et0 = float(et0_match.group(1)) if et0_match else 4.5
        rain = float(rain_match.group(1)) if rain_match else 8.5
        stage = stage_match.group(1).lower() if stage_match else "tillering"

        # Disease query
        if any(k in ql for k in ["disease", "risk", "fungal", "pathogen", "blight", "rust", "mildew", "spray"]):
            risks = get_disease_risk(crop, temp, hum, rain, stage)
            knowledge_data["disease_risks"] = risks

        # Irrigation query
        if any(k in ql for k in ["irrigat", "water", "moisture", "stress", "wilting"]):
            irrig = get_irrigation_recommendation(crop, sm, rain, et0, stage)
            knowledge_data["irrigation_recommendation"] = irrig
            wb = estimate_water_balance(sm / 100.0, et0, rain / 7.0, crop)
            knowledge_data["water_balance"] = wb

        # Nutrient query
        if any(k in ql for k in ["nitrogen", "npk", "fertiliz", "nutri", "urea", "phosphorus", "potassium"]):
            nutri = get_nutrient_recommendation(crop, stage)
            knowledge_data["nutrient_recommendation"] = nutri

        # BBCH/phenology
        if any(k in ql for k in ["bbch", "stage", "phenol", "gdd", "growth"]):
            knowledge_data["bbch_stages"] = BBCH_STAGES.get(crop, BBCH_STAGES.get("wheat", {}))
            gdd_match = _re.search(r"(?:GDD|gdd|Accumulated Gdd)[:\s]*(\d+\.?\d*)", field_context, _re.IGNORECASE)
            if gdd_match:
                gdd_val = float(gdd_match.group(1))
                knowledge_data["gdd_interpretation"] = interpret_gdd_stage(gdd_val, crop)

        # Regional
        if any(k in ql for k in ["algeria", "mitidja", "region", "traditional", "variety", "wilaya"]):
            knowledge_data["region"] = get_region_info("algeria")

        # Yield / loss
        if any(k in ql for k in ["yield", "loss", "production", "harvest", "ton", "quintal"]):
            yl = estimate_yield_loss("water_stress", stage, 0.5)
            knowledge_data["yield_loss_estimate"] = yl
            knowledge_data["potential_yield"] = f"{crop_info.potential_yield_t_ha[0]}-{crop_info.potential_yield_t_ha[1]} t/ha"

        # Pipeline/system explanation
        if any(k in ql for k in ["pipeline", "system", "layer", "engine", "how does", "architecture"]):
            knowledge_data["pipeline_layers"] = get_pipeline_layer_summary()

        # Soil / PAWC
        if any(k in ql for k in ["soil", "clay", "sand", "pawc", "texture", "whc"]):
            clay_match = _re.search(r"clay[:\s]*(\d+\.?\d*)", field_context, _re.IGNORECASE)
            sand_match = _re.search(r"sand[:\s]*(\d+\.?\d*)", field_context, _re.IGNORECASE)
            if clay_match and sand_match:
                pawc = calculate_pawc(float(clay_match.group(1)), float(sand_match.group(1)))
                knowledge_data["pawc_mm_per_m"] = pawc

        # Format with LLM
        from layer9_interface.engines.local_vlm import local_vlm_client
        kg_context = json.dumps(knowledge_data, indent=2, default=str)

        system_prompt = f"""You are AgriBrain. Use the following verified agronomic data to answer.
Present it naturally as a warm colleague. Use **bold** for key values.

VERIFIED DATA:
{kg_context}

FARMER EXPERIENCE: {experience_level}
RULES: Present this data conversationally. Do NOT add data not in VERIFIED DATA."""

        res = local_vlm_client.query(query, system_prompt=system_prompt)
        return res.get("answer", "") if res else ""


    def _execute_decomposed(self, query: str, field_context: str,
                            experience_level: str) -> str:
        """Execute decomposed sub-queries."""
        from layer9_interface.engines.query_decomposer import get_decomposer

        decomposer = get_decomposer()
        sub_queries = decomposer.decompose(query)

        for sq in sub_queries:
            # Route each sub-query through direct strategy
            response = self._execute_direct(sq.text, sq.intent, field_context,
                                           experience_level)
            sq.answer = response

        return decomposer.fuse_answers(sub_queries)


# ============================================================================
# Singleton
# ============================================================================

_router = None

def get_router() -> AdaptivePromptRouter:
    global _router
    if _router is None:
        _router = AdaptivePromptRouter()
    return _router


def smart_query(query: str, intent: str, field_context: str,
                context_dict: Optional[Dict[str, Any]] = None,
                experience_level: str = "INTERMEDIATE") -> Dict[str, Any]:
    """One-call convenience function for the adaptive router."""
    return get_router().execute(query, intent, field_context, context_dict, experience_level)

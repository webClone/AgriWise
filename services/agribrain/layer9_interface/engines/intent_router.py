"""
Engine 2: Intent Router v9.6.0

ML-ready intent classifier with expertise-level detection.
Rule-based first pass with entity extraction and confidence scoring.
"""
import re, logging
from typing import Dict, Any, Optional

from layer9_interface.schema import (
    UserIntent, ExpertiseLevel, IntentClassification, PersonaConfig,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Keyword tables
# ============================================================================

_INTENT_KEYWORDS: Dict[UserIntent, list] = {
    UserIntent.GREETING: [
        r"\b(hi|hello|hey|bonjour|salut|good\s*morning|good\s*evening)\b",
        r"\bhow\s+are\s+you\b",
    ],
    UserIntent.OVERVIEW: [
        r"\b(overview|summary|status|how\s+is|what.*look)\b",
        r"\bfield\s+(status|health|condition)\b",
        r"\b(trend|monitoring)\b",
    ],
    UserIntent.DIAGNOSE: [
        r"\b(diagnos|problems?|issues?|disease|pest|deficien|symptom|what.*wrong)\b",
        r"\b(stress|wilt|chloro|necrosis|yellow|sick|infect|blight)\b",
        r"\b(posterior|confidence\s+interval)\b",
        r"\b(find|found|detect|identif)\b",
    ],
    UserIntent.ACTION_DETAIL: [
        r"what\s+should\s+i",
        r"\b(recommend|action|advice|should\s+i)\b",
        r"\b(apply|spray|irrigat|fertili|rate|dose)\b",
        r"\b(threshold|above|below|Kc|ET[o0])\b",
    ],
    UserIntent.COMPARE: [
        r"\b(compar|differ|versus|vs\.?|better)\b",
        r"\b(drip|pivot|between)\b",
        r"\bzone\s*[A-Za-z]\s+vs\b",
    ],
    UserIntent.SCHEDULE: [
        r"\b(when\s+should|schedule|timing|calendar|deadline)\b",
        r"\b(window|phenology|BBCH|stage)\b",
    ],
    UserIntent.REPORT: [
        r"\b(report|export|pdf|document|print)\b",
        r"\b(generate\s+(a|an|the)?\s*report)\b",
    ],
    UserIntent.SPATIAL: [
        r"\bzone\s+(map|plan|cards?)\b",
        r"\b(area|spatial|map|sector|corner|north|south|east|west)\b",
        r"\b(heterogen|variabil|where\s+is)\b",
    ],
    UserIntent.COACHING: [
        r"\b(coach|improv|tips?|learn|teach|help\s+me|guide)\b",
        r"\b(data\s+quality|score|better\s+(data|results))\b",
        r"\b(improv.+data|improv.+accuracy|improv.+quality)\b",
    ],
    UserIntent.TASK_MGMT: [
        r"\b(task|todo|to-?do|checklist|done|complet|finish|progress)\b",
    ],
    UserIntent.DATA_REQUEST: [
        r"\b(upload|photo|picture|sensor|reading|measur|sample)\b",
        r"\b(need\s+more\s+data|accuracy|improve\s+(data|accuracy))\b",
    ],
    UserIntent.REMINDER: [
        r"\b(remind|reminder|don.*forget|alert\s+me|notify|notification)\b",
    ],
}

_EXPERTISE_SIGNALS: Dict[ExpertiseLevel, list] = {
    ExpertiseLevel.RESEARCHER: [
        r"\b(coefficient|posterior|bayesian|CI|confidence\s+interval|p-value)\b",
        r"\b(penman|monteith|regression|R\^?2|calibrat)\b",
    ],
    ExpertiseLevel.AGRONOMIST: [
        r"\b(BBCH|phenology|absorption|Kc|ET[o0]|evapotranspir)\b",
        r"\b(split.?applic|side.?dress|IPM|escalation)\b",
    ],
    ExpertiseLevel.TECHNICIAN: [
        r"\b(NDVI|SAR|VV|VH|sentinel|GDD|LAI)\b",
        r"\b(probability|severity|threshold|index)\b",
    ],
    ExpertiseLevel.NOVICE: [
        r"\b(my\s+plants?|my\s+garden|simple|easy|what\s+is)\b",
        r"\b(beginner|new\s+to|first\s+time|sick.{0,10}help|look\s+sick)\b",
    ],
}

_CROP_NAMES = [
    "corn", "maize", "wheat", "soybean", "rice", "cotton", "potato",
    "barley", "sorghum", "sunflower", "tomato", "olive", "grape",
]

_NUTRIENT_NAMES = [
    "nitrogen", "phosphorus", "potassium", "N", "P", "K",
    "zinc", "iron", "manganese", "boron",
]


class IntentRouterEngine:
    """ML-ready intent classifier with expertise detection."""

    def classify(self, query: str) -> IntentClassification:
        """Classify a user query into intent + expertise."""
        if not query or not query.strip():
            return IntentClassification(
                primary_intent=UserIntent.OVERVIEW,
                confidence=1.0,
                fallback_intent=UserIntent.OVERVIEW,
            )

        q = query.strip()
        q_lower = q.lower()

        # --- Intent classification ---
        # Specificity bonus: narrow intents break ties against generic ones
        _SPECIFICITY_BONUS: Dict[UserIntent, float] = {
            UserIntent.REMINDER: 0.3,
            UserIntent.TASK_MGMT: 0.3,
            UserIntent.DATA_REQUEST: 0.25,
            UserIntent.REPORT: 0.2,
            UserIntent.SCHEDULE: 0.15,
            UserIntent.SPATIAL: 0.15,
            UserIntent.COACHING: 0.15,
            UserIntent.COMPARE: 0.1,
            UserIntent.GREETING: 0.4,  # Greetings are always unambiguous
        }
        scores: Dict[UserIntent, float] = {}
        for intent, patterns in _INTENT_KEYWORDS.items():
            score = 0.0
            for pat in patterns:
                if re.search(pat, q_lower):
                    score += 1.0
            if score > 0:
                scores[intent] = score + _SPECIFICITY_BONUS.get(intent, 0.0)

        if scores:
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            primary = ranked[0][0]
            confidence = min(1.0, ranked[0][1] / 2.0)
            fallback = ranked[1][0] if len(ranked) > 1 else UserIntent.OVERVIEW
        else:
            primary = UserIntent.UNKNOWN
            confidence = 0.3
            fallback = UserIntent.OVERVIEW

        # --- Expertise detection ---
        expertise = ExpertiseLevel.FARMER  # default
        for level, patterns in _EXPERTISE_SIGNALS.items():
            for pat in patterns:
                if re.search(pat, q, re.IGNORECASE):
                    expertise = level
                    break
            if expertise != ExpertiseLevel.FARMER:
                break

        # --- Entity extraction ---
        entities: Dict[str, Any] = {}
        for crop in _CROP_NAMES:
            if crop.lower() in q_lower:
                entities["crop"] = crop
                break
        for nut in _NUTRIENT_NAMES:
            if nut.lower() in q_lower:
                entities.setdefault("nutrients", []).append(nut)

        zone_match = re.search(r"\bzone[_\s-]?([A-Za-z0-9]+)\b", q)
        if zone_match:
            entities["zone"] = f"zone_{zone_match.group(1)}"

        return IntentClassification(
            primary_intent=primary,
            confidence=confidence,
            fallback_intent=fallback,
            extracted_entities=entities,
            detected_expertise=expertise,
        )

    def build_persona(self, expertise: ExpertiseLevel) -> PersonaConfig:
        """Build a PersonaConfig from detected expertise level."""
        configs = {
            ExpertiseLevel.NOVICE: PersonaConfig(
                expertise_level=ExpertiseLevel.NOVICE,
                warmth_factor=0.9, emoji_enabled=True,
                use_metaphors=True, max_explanation_depth=1,
            ),
            ExpertiseLevel.FARMER: PersonaConfig(
                expertise_level=ExpertiseLevel.FARMER,
                warmth_factor=0.7, emoji_enabled=True,
                use_metaphors=False, max_explanation_depth=2,
            ),
            ExpertiseLevel.TECHNICIAN: PersonaConfig(
                expertise_level=ExpertiseLevel.TECHNICIAN,
                warmth_factor=0.5, emoji_enabled=False,
                use_metaphors=False, max_explanation_depth=3,
            ),
            ExpertiseLevel.AGRONOMIST: PersonaConfig(
                expertise_level=ExpertiseLevel.AGRONOMIST,
                warmth_factor=0.3, emoji_enabled=False,
                use_metaphors=False, max_explanation_depth=4,
            ),
            ExpertiseLevel.RESEARCHER: PersonaConfig(
                expertise_level=ExpertiseLevel.RESEARCHER,
                warmth_factor=0.2, emoji_enabled=False,
                use_metaphors=False, max_explanation_depth=5,
            ),
        }
        return configs.get(expertise, configs[ExpertiseLevel.FARMER])

    def extract_features(self, query: str, classification: IntentClassification) -> Dict[str, float]:
        """ML-ready feature vector for model training."""
        q_lower = (query or "").lower()
        return {
            "query_length": float(len(query or "")),
            "word_count": float(len(q_lower.split())),
            "has_question_mark": float("?" in query),
            "intent_confidence": classification.confidence,
            "expertise_ordinal": float(
                [e.value for e in ExpertiseLevel].index(
                    classification.detected_expertise.value
                )
            ),
            "has_crop_entity": float(bool(classification.extracted_entities.get("crop"))),
            "has_zone_entity": float(bool(classification.extracted_entities.get("zone"))),
            "has_nutrient_entity": float(bool(classification.extracted_entities.get("nutrients"))),
        }


intent_router = IntentRouterEngine()

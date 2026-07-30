"""
multilingual_engine.py - Arabic/French/English Auto-Detection & Translation
=============================================================================

Detects the farmer's language from query text and ensures the response
matches their language. Supports:
  1. Arabic (Standard + Algerian dialect)
  2. French
  3. English (default)

Also handles mixed-language queries (code-switching) common in Algeria
where farmers mix Arabic, French, and Darija.
"""

import re
from typing import Dict, Any, Optional, Tuple


class MultilingualEngine:
    """Detects language and manages multilingual prompts."""

    # Arabic Unicode ranges
    ARABIC_RANGE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')

    # French-specific patterns
    FRENCH_PATTERNS = [
        r"\b(est-ce que|qu'est-ce|comment|pourquoi|quand|combien|quel|quelle)\b",
        r"\b(je|tu|il|elle|nous|vous|ils|elles)\b",
        r"\b(le|la|les|un|une|des|du|de la)\b",
        r"\b(champ|blé|irrigation|sol|engrais|récolte|maladie|pluie)\b",
        r"\b(bonjour|merci|s'il vous plaît|oui|non)\b",
    ]

    # Algerian Darija patterns (Romanized)
    DARIJA_PATTERNS = [
        r"\b(wesh|kifash|win|chhal|chnou|3lach|hada|hadi|bezzaf)\b",
        r"\b(labas|hamdullah|inshallah|mazel|khlass|yallah)\b",
    ]

    # Algerian Darija agricultural terms and micro-dialect translations
    DARIJA_TRANSLATIONS = {
        "salam": "hello",
        "labas": "how are you",
        "kifash": "how to",
        "wesh": "what is",
        "win": "where",
        "chhal": "how much",
        "chnou": "what",
        "3lach": "why",
        "hada": "this",
        "hadi": "this",
        "bezzaf": "very much",
        "hamdullah": "praise be to God",
        "inshallah": "God willing",
        "saha": "thanks",
        "khouya": "brother",
        "chih": "mugwort weed",
        "hab el melh": "soil salinity",
        "sirocco": "hot dry Saharan wind",
        "mitidja": "clay-loam soil",
        "sigoise": "olive crop",
        "chemlal": "olive crop",
        "ble dur": "durum wheat",
        "orge": "barley",
        "palmier": "date palm",
    }

    # Arabic agronomic terms
    ARABIC_AGRO_TERMS = {
        "قمح": "wheat", "ري": "irrigation", "تربة": "soil",
        "سماد": "fertilizer", "محصول": "crop", "حصاد": "harvest",
        "مرض": "disease", "مطر": "rain", "حرارة": "temperature",
        "رطوبة": "humidity", "نيتروجين": "nitrogen", "فسفور": "phosphorus",
    }

    # French agronomic terms
    FRENCH_AGRO_TERMS = {
        "blé": "wheat", "irrigation": "irrigation", "sol": "soil",
        "engrais": "fertilizer", "culture": "crop", "récolte": "harvest",
        "maladie": "disease", "pluie": "rain", "température": "temperature",
        "humidité": "humidity", "azote": "nitrogen", "phosphore": "phosphorus",
    }

    def detect_language(self, text: str) -> Tuple[str, float]:
        """Detect the primary language of the text.
        
        Returns:
            (language_code, confidence): e.g., ("ar", 0.9), ("fr", 0.8), ("en", 0.7)
        """
        if not text or not text.strip():
            return "en", 0.5

        text = text.strip()

        # Check for Arabic characters
        arabic_chars = len(self.ARABIC_RANGE.findall(text))
        total_chars = len(text.replace(" ", ""))

        if total_chars > 0 and arabic_chars / total_chars > 0.3:
            return "ar", min(0.95, arabic_chars / total_chars)

        # Check for French patterns
        text_lower = text.lower()
        french_score = 0
        for pattern in self.FRENCH_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                french_score += 1

        # Check for Darija (Algerian Arabic in Latin script)
        darija_score = 0
        for pattern in self.DARIJA_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                darija_score += 1

        # Also check for regional dialect agricultural terms
        for term in ["salam", "saha", "khouya", "sirocco", "mitidja", "sigoise", "chemlal", "ble dur"]:
            if term in text_lower:
                darija_score += 1

        if darija_score >= 1:
            return "ar_dz", min(0.95, 0.7 + darija_score * 0.1)

        if french_score >= 2:
            return "fr", min(0.95, 0.6 + french_score * 0.08)

        return "en", 0.7

    def compile_darija_query(self, query: str) -> str:
        """Compile Algerian Darija terms in the query into standard English/French descriptors to assist upstream routing."""
        q_compiled = query.lower()
        
        # Replace Darija micro-dialect terms
        for darija_term, translated in self.DARIJA_TRANSLATIONS.items():
            # Use regex word boundaries for precise replacement
            q_compiled = re.sub(rf'\b{darija_term}\b', translated, q_compiled)
            
        return q_compiled

    def get_language_instruction(self, lang: str) -> str:
        """Get the LLM instruction for responding in the detected language."""
        instructions = {
            "ar": """LANGUAGE INSTRUCTION: The farmer is speaking Arabic.
You MUST respond entirely in Standard Arabic (فصحى).
Use Arabic agricultural terminology. Right-to-left text.
Keep technical terms in Arabic where possible, with English in parentheses only for specialized terms.""",

            "ar_dz": """LANGUAGE INSTRUCTION: The farmer is speaking Algerian Arabic (Darija).
Respond in standard Arabic mixed with warm, neighborly Algerian phrasing.
Use standard Arabic script. Address the user respectfully as 'brother' (يا أخي) or 'esteemed farmer' (عزيزي الفلاح).
End recommendations with supportive blessings like 'Inshallah' (إن شاء الله) or 'Rabbi ybarek' (ربي يبارك) to make the dialogue feel deeply authentic and colleague-like.
Agronomic terms can be stated in their Algerian French/Arabic dialect equivalent (e.g. 'Sirocco', 'Mitidja').""",

            "fr": """LANGUAGE INSTRUCTION: The farmer is speaking French.
You MUST respond entirely in French.
Use French agricultural terminology (blé, sol, engrais, rendement, etc.).
Maintain a warm, professional tone appropriate for French-speaking Algerian farmers.""",

            "en": "",  # Default, no special instruction needed
        }
        return instructions.get(lang, "")

    def build_multilingual_prompt(self, query: str, base_prompt: str) -> str:
        """Add language-specific instructions to the system prompt.
        
        Returns the modified system prompt with language instructions.
        """
        lang, confidence = self.detect_language(query)

        if lang == "en" or confidence < 0.5:
            return base_prompt

        lang_instruction = self.get_language_instruction(lang)
        return f"{base_prompt}\n\n{lang_instruction}"

    def translate_agro_terms(self, text: str, from_lang: str, to_lang: str) -> str:
        """Simple agronomic term translation for context enrichment."""
        if from_lang == to_lang:
            return text

        if from_lang == "ar":
            for ar_term, en_term in self.ARABIC_AGRO_TERMS.items():
                text = text.replace(ar_term, f"{ar_term} ({en_term})")
        elif from_lang == "fr":
            for fr_term, en_term in self.FRENCH_AGRO_TERMS.items():
                text = re.sub(rf'\b{fr_term}\b', f"{fr_term} ({en_term})",
                             text, flags=re.IGNORECASE)
        return text


# Singleton
_engine = None

def get_multilingual_engine() -> MultilingualEngine:
    global _engine
    if _engine is None:
        _engine = MultilingualEngine()
    return _engine


def detect_language(text: str) -> Tuple[str, float]:
    """One-call convenience function."""
    return get_multilingual_engine().detect_language(text)


def build_multilingual_prompt(query: str, base_prompt: str) -> str:
    """One-call convenience function."""
    return get_multilingual_engine().build_multilingual_prompt(query, base_prompt)

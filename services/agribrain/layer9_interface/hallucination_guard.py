"""
Layer 9: Hallucination Guard

Post-generation validation of LLM output against structured upstream data.
Catches invented numbers, dates, zones, and chemical recommendations.

Usage:
    guard = HallucinationGuard(upstream_data)
    validated = guard.validate(llm_text)
"""

import re
from typing import Dict, List, Any, Set, Optional
from dataclasses import dataclass, field


@dataclass
class HallucinationFlag:
    """A detected hallucination or unverifiable claim."""
    claim_type: str          # "number", "date", "zone", "chemical", "action", "physical_constraint", "unresolved_diagnosis"
    claim_value: str         # the suspicious claim
    context: str             # surrounding text
    action: str              # "removed", "replaced", "flagged"
    replacement: str = ""


@dataclass(frozen=True)
class GroundedFact:
    """A verified factual claim from upstream layers with domain and unit scope."""
    domain: str             # e.g. "application_rate", "temperature", "soil_moisture", "precipitation", "irrigation", "yield", "score", "general"
    variable: str           # name of variable, e.g. "fertilizer_rate", "air_temp", "priority_score"
    value: float            # numeric value
    unit: str               # "kg/ha", "l/ha", "°c", "mm", "%", "t/ha", etc.
    action_type: Optional[str] = None
    tolerance: float = 0.10 # 10% relative tolerance


class HallucinationGuard:
    """
    Validates LLM-generated text against structured upstream data.
    
    Checks:
      1. Numeric claims must match grounded upstream data in compatible domains & units (Defect A19 fix)
      2. Dates must exist in schedule
      3. Zone mentions must be in zone_plan
      4. Chemical/product names must be allowed by compliance
      5. Blocked actions must not be presented as suggested
      6. Conversational certainty on UNRESOLVED diagnostic states is strictly forbidden
      7. Physical biophysical bounds (urea burn, anoxia saturation) are strictly enforced
    """
    
    def __init__(self,
                 upstream_numbers: Optional[Set[float]] = None,
                 upstream_dates: Optional[Set[str]] = None,
                 upstream_zones: Optional[Set[str]] = None,
                 allowed_actions: Optional[Set[str]] = None,
                 blocked_actions: Optional[Set[str]] = None,
                 crop: str = "",
                 soil_moisture: Optional[float] = None,
                 grounded_facts: Optional[List[GroundedFact]] = None,
                 unresolved_diagnoses: Optional[Set[str]] = None):
        self.upstream_numbers = set(upstream_numbers or set())
        self.upstream_dates = set(upstream_dates or set())
        self.upstream_zones = set(upstream_zones or set())
        self.allowed_actions = set(allowed_actions or set())
        self.blocked_actions = set(blocked_actions or set())
        self.crop = crop
        self.soil_moisture = soil_moisture
        self.grounded_facts = list(grounded_facts or [])
        self.unresolved_diagnoses = set(unresolved_diagnoses or set())
        
        # Populate upstream_numbers from grounded_facts for backward compatibility
        for fact in self.grounded_facts:
            self.upstream_numbers.add(round(float(fact.value), 2))
    
    @classmethod
    def from_layer9_input(cls, l9_input: Dict[str, Any]) -> "HallucinationGuard":
        """Build guard from Layer9Input-like dict, populating structured GroundedFacts."""
        numbers: Set[float] = set()
        dates: Set[str] = set()
        zones: Set[str] = set()
        allowed: Set[str] = set()
        blocked: Set[str] = set()
        grounded_facts: List[GroundedFact] = []
        unresolved_diagnoses: Set[str] = set()
        
        # Extract actions, rates, and blocked actions
        for action in l9_input.get("actions", []):
            if isinstance(action, dict):
                act_type = str(action.get("action_type", "") or "")
                act_id = str(action.get("action_id", "") or "")
                prod_name = str(action.get("product_name", "") or "")
                title = str(action.get("title", "") or "")
                
                is_allowed = action.get("is_allowed", True)
                if is_allowed:
                    if act_type:
                        allowed.add(act_type)
                else:
                    if act_id:
                        blocked.add(act_id)
                    if act_type:
                        blocked.add(act_type)
                    if prod_name:
                        blocked.add(prod_name)
                    if title:
                        blocked.add(title)
                
                for key in ("priority_score", "recommended", "min_safe", "max_safe"):
                    val = action.get(key)
                    if val is not None and isinstance(val, (int, float)):
                        vf = round(float(val), 2)
                        numbers.add(vf)
                        grounded_facts.append(GroundedFact(
                            domain="score" if "score" in key else "rate",
                            variable=f"{act_type}_{key}",
                            value=vf,
                            unit="",
                            action_type=act_type
                        ))
                
                rate = action.get("rate", {})
                if isinstance(rate, dict):
                    unit = str(rate.get("unit") or ("kg/ha" if "FERTILIZ" in act_type.upper() else ("L/ha" if "SPRAY" in act_type.upper() else "kg/ha")))
                    for key in ("recommended", "min_safe", "max_safe"):
                        val = rate.get(key)
                        if val is not None and isinstance(val, (int, float)):
                            vf = round(float(val), 2)
                            numbers.add(vf)
                            grounded_facts.append(GroundedFact(
                                domain="application_rate",
                                variable=f"{act_type}_{key}",
                                value=vf,
                                unit=unit,
                                action_type=act_type
                            ))
        
        # Extract dates from schedule
        for sched in l9_input.get("schedule", []):
            if isinstance(sched, dict):
                date = sched.get("scheduled_date")
                if date:
                    dates.add(str(date))
        
        # Extract zones
        zone_plan = l9_input.get("zone_plan", {})
        if isinstance(zone_plan, dict):
            zones = set(zone_plan.keys())
        
        # Extract numbers from outcome forecast
        forecast = l9_input.get("outcome_forecast", {})
        if isinstance(forecast, dict):
            for k, val in forecast.items():
                if isinstance(val, (int, float)):
                    vf = round(float(val), 2)
                    numbers.add(vf)
                    unit = "t/ha" if "yield" in k.lower() else ("%" if "pct" in k.lower() or "risk" in k.lower() else "")
                    domain = "yield" if "yield" in k.lower() else "forecast"
                    grounded_facts.append(GroundedFact(
                        domain=domain,
                        variable=k,
                        value=vf,
                        unit=unit
                    ))
        
        # Extract numbers & unresolved states from diagnoses
        for diag in l9_input.get("diagnoses", []):
            if isinstance(diag, dict):
                prob_id = str(diag.get("problem_id") or diag.get("id") or diag.get("title") or "")
                status = str(diag.get("status") or diag.get("diagnostic_status") or "").upper()
                is_resolved = diag.get("is_resolved", diag.get("resolved"))
                conf = diag.get("confidence", 1.0)
                
                # If unresolved or low confidence hypothesis, forbid certainty
                if (is_resolved is False or
                    status in ("UNRESOLVED", "INVESTIGATING", "SUSPECTED", "UNCERTAIN", "HYPOTHESIS") or
                    (conf is not None and conf < 0.6)):
                    if prob_id:
                        unresolved_diagnoses.add(prob_id)
                        unresolved_diagnoses.add(prob_id.lower().replace("_", " "))
                        
                for key in ("probability", "severity", "confidence"):
                    val = diag.get(key)
                    if val is not None and isinstance(val, (int, float)):
                        vf = round(float(val), 2)
                        numbers.add(vf)
                        grounded_facts.append(GroundedFact(
                            domain="diagnosis",
                            variable=f"{prob_id}_{key}",
                            value=vf,
                            unit=""
                        ))
        
        # Extract crop and soil moisture for physical constraints & weather telemetry
        crop = ""
        soil_moisture = None
        
        veg = l9_input.get("l2_vegetation_data")
        if isinstance(veg, dict):
            crop = veg.get("crop", "")
            if veg.get("ndvi") is not None:
                try:
                    vf = round(float(veg["ndvi"]), 2)
                    numbers.add(vf)
                    grounded_facts.append(GroundedFact(domain="vegetation", variable="ndvi", value=vf, unit=""))
                except (ValueError, TypeError):
                    pass
            
        fusion = l9_input.get("l1_fusion_data")
        if isinstance(fusion, dict):
            soil_moisture = fusion.get("soil_moisture")
            for w_key, dom, unit in [
                ("temperature", "temperature", "°C"),
                ("air_temperature", "temperature", "°C"),
                ("precipitation", "precipitation", "mm"),
                ("rainfall", "precipitation", "mm"),
                ("relative_humidity", "weather_humidity", "%"),
            ]:
                if fusion.get(w_key) is not None:
                    try:
                        vf = round(float(fusion[w_key]), 2)
                        numbers.add(vf)
                        grounded_facts.append(GroundedFact(domain=dom, variable=w_key, value=vf, unit=unit))
                    except (ValueError, TypeError):
                        pass
            
        if soil_moisture is None:
            sensors = l9_input.get("sensor_summary", {})
            if isinstance(sensors, dict):
                soil_moisture = sensors.get("soil_moisture")
                if sensors.get("temperature") is not None:
                    try:
                        vf = round(float(sensors["temperature"]), 2)
                        numbers.add(vf)
                        grounded_facts.append(GroundedFact(domain="temperature", variable="temperature", value=vf, unit="°C"))
                    except (ValueError, TypeError):
                        pass
                if sensors.get("rainfall") is not None:
                    try:
                        vf = round(float(sensors["rainfall"]), 2)
                        numbers.add(vf)
                        grounded_facts.append(GroundedFact(domain="precipitation", variable="rainfall", value=vf, unit="mm"))
                    except (ValueError, TypeError):
                        pass
        
        if soil_moisture is not None:
            try:
                sm_val = round(float(soil_moisture), 2)
                numbers.add(sm_val)
                grounded_facts.append(GroundedFact(domain="soil_moisture", variable="soil_moisture", value=sm_val, unit="%"))
            except (ValueError, TypeError):
                pass
        
        return cls(
            upstream_numbers=numbers,
            upstream_dates=dates,
            upstream_zones=zones,
            allowed_actions=allowed,
            blocked_actions=blocked,
            crop=crop,
            soil_moisture=soil_moisture,
            grounded_facts=grounded_facts,
            unresolved_diagnoses=unresolved_diagnoses,
        )
    
    def validate(self, text: str) -> tuple:
        """
        Validate LLM text against upstream data.
        
        Returns:
            (cleaned_text, flags)
        """
        flags: List[HallucinationFlag] = []
        cleaned = text
        
        # 1. Check numeric claims (unit- and domain-scoped)
        cleaned, num_flags = self._check_numbers(cleaned)
        flags.extend(num_flags)
        
        # 2. Check date claims
        cleaned, date_flags = self._check_dates(cleaned)
        flags.extend(date_flags)
        
        # 3. Check zone mentions against upstream zone_plan
        cleaned, zone_flags = self._check_zones(cleaned)
        flags.extend(zone_flags)
        
        # 4. Check blocked actions presented as suggested
        cleaned, action_flags = self._check_blocked_actions(cleaned)
        flags.extend(action_flags)

        # 5. Check conversational certainty on UNRESOLVED diagnostic states
        cleaned, diag_flags = self._check_unresolved_diagnoses(cleaned)
        flags.extend(diag_flags)

        # 6. Check physical constraints (urea rate, waterlogging)
        cleaned, physical_flags = self._check_physical_constraints(cleaned)
        flags.extend(physical_flags)
        
        return cleaned, flags

    @staticmethod
    def _classify_claim_domain(unit: str, context: str) -> str:
        """Determine claim domain from unit string and local context words."""
        u = unit.lower()
        if u in ("kg/ha", "l/ha"):
            return "application_rate"
        if u in ("kg", "l"):
            if any(w in context for w in ("fertiliz", "urea", "rate", "apply", "spray", "dose", "nitrogen", "pesticide", "herbicide", "engrais")):
                return "application_rate"
            return "mass_or_volume"
        if u in ("°c", "°") or (u == "c" and "temp" in context):
            return "temperature"
        if u == "mm":
            if any(w in context for w in ("irrigat", "water", "arrosage")):
                return "irrigation"
            if any(w in context for w in ("rain", "precip", "pluie")):
                return "precipitation"
            return "water_depth"
        if u in ("t/ha", "t"):
            return "yield"
        if u == "%":
            if any(w in context for w in ("moist", "water", "humid")):
                return "soil_moisture" if "soil" in context else "weather_humidity"
            if any(w in context for w in ("yield", "loss", "gain", "delta")):
                return "yield_delta"
            return "percentage"
        return "general"

    def _is_fact_grounded(self, val: float, unit: str, domain: str) -> bool:
        """Check if numeric value matches a GroundedFact in a compatible domain."""
        compatible_domains = {
            "application_rate": {"application_rate", "chemical_rate", "rate"},
            "temperature": {"temperature", "weather_temperature", "weather"},
            "soil_moisture": {"soil_moisture", "moisture"},
            "precipitation": {"precipitation", "rainfall", "water_depth", "weather"},
            "irrigation": {"irrigation", "water_depth"},
            "water_depth": {"water_depth", "irrigation", "precipitation"},
            "yield": {"yield", "forecast"},
            "yield_delta": {"yield_delta", "yield", "forecast", "percentage"},
            "percentage": {"percentage", "diagnosis", "forecast", "yield_delta", "score"},
            "score": {"score", "priority", "diagnosis"},
        }.get(domain, {domain, "general"})
        
        for fact in self.grounded_facts:
            if fact.domain in compatible_domains:
                # Check unit compatibility if unit is present
                unit_compat = True
                if unit and fact.unit:
                    u1 = unit.lower().replace("°", "").strip()
                    u2 = fact.unit.lower().replace("°", "").strip()
                    unit_compat = (
                        (u1 == u2)
                        or (u1 in ("c", "deg c") and u2 in ("c", "deg c"))
                        or (u1 in ("kg/ha", "kg") and u2 in ("kg/ha", "kg"))
                        or (u1 in ("l/ha", "l") and u2 in ("l/ha", "l"))
                    )
                if unit_compat:
                    denom = max(abs(fact.value), 0.01)
                    if abs(val - fact.value) / denom <= fact.tolerance:
                        return True
                        
        return False
    
    def _check_numbers(self, text: str) -> tuple:
        """
        Flag numbers not in upstream data.
        Context- and unit-aware matching prevents cross-domain validation bypass
        (e.g., weather 25°C validating a 25 kg/ha fertilizer rate — Defect A19 fix).
        """
        flags: List[HallucinationFlag] = []
        
        number_pattern = r'\b(\d+(?:\.\d+)?)\s*(kg/ha|kg|l/ha|l|mm|t/ha|t|%|°c|°|c)\b'
        matches = list(re.finditer(number_pattern, text, re.IGNORECASE))
        
        for match in matches:
            try:
                val = round(float(match.group(1)), 2)
                raw_unit = (match.group(2) or "").lower()
                if val <= 0:
                    continue
                
                sentence_start = max(0, match.start() - 60)
                sentence_end = min(len(text), match.end() + 60)
                sentence = text[sentence_start:sentence_end].lower()
                claim_domain = self._classify_claim_domain(raw_unit, sentence)
                
                if self.grounded_facts:
                    # Enforce domain- and unit-scoped matching
                    if not self._is_fact_grounded(val, raw_unit, claim_domain):
                        flags.append(HallucinationFlag(
                            claim_type="number",
                            claim_value=f"{val} {raw_unit}".strip(),
                            context=text[max(0, match.start()-20):min(len(text), match.end()+20)],
                            action="flagged",
                        ))
                else:
                    # Legacy fallback: match against upstream_numbers
                    if val not in self.upstream_numbers:
                        close = any(abs(val - u) / max(abs(u), 0.01) < 0.1
                                   for u in self.upstream_numbers if u != 0)
                        if not close:
                            flags.append(HallucinationFlag(
                                claim_type="number",
                                claim_value=str(val),
                                context=text[max(0, match.start()-20):min(len(text), match.end()+20)],
                                action="flagged",
                            ))
            except ValueError:
                continue
        
        return text, flags
    
    def _check_dates(self, text: str) -> tuple:
        """Flag dates not in schedule."""
        flags: List[HallucinationFlag] = []
        
        date_pattern = r'\b(\d{4}-\d{2}-\d{2})\b'
        matches = re.finditer(date_pattern, text)
        
        for match in matches:
            date_str = match.group(1)
            if date_str not in self.upstream_dates:
                flags.append(HallucinationFlag(
                    claim_type="date",
                    claim_value=date_str,
                    context=text[max(0, match.start()-20):match.end()+20],
                    action="flagged",
                ))
        
        return text, flags
    
    def _check_blocked_actions(self, text: str) -> tuple:
        """Flag and forbid recommending blocked or restricted actions."""
        flags: List[HallucinationFlag] = []
        if not self.blocked_actions:
            return text, flags
            
        cleaned = text
        text_lower = cleaned.lower()
        suggestion_phrases = [
            "recommend", "should", "apply", "schedule",
            "proceed with", "go ahead", "perform", "execute"
        ]
        
        for blocked_id in self.blocked_actions:
            if not blocked_id or len(blocked_id.strip()) < 2:
                continue
            b_lower = blocked_id.lower()
            if b_lower in text_lower:
                sentences = re.split(r'(?<=[.!?\n])\s+', cleaned)
                new_sentences = []
                replaced_any = False
                for s in sentences:
                    s_lower = s.lower()
                    if b_lower in s_lower and any(phrase in s_lower for phrase in suggestion_phrases):
                        replacement_note = f"[RESTRICTED] Action '{blocked_id}' is BLOCKED by safety compliance and cannot be executed."
                        flags.append(HallucinationFlag(
                            claim_type="action",
                            claim_value=blocked_id,
                            context=s.strip(),
                            action="replaced",
                            replacement=replacement_note,
                        ))
                        new_sentences.append(replacement_note)
                        replaced_any = True
                    else:
                        new_sentences.append(s)
                if replaced_any:
                    cleaned = " ".join(new_sentences)
                    text_lower = cleaned.lower()
        
        return cleaned, flags

    def _check_unresolved_diagnoses(self, text: str) -> tuple:
        """Forbid conversational certainty on UNRESOLVED diagnostic states."""
        flags: List[HallucinationFlag] = []
        if not self.unresolved_diagnoses:
            return text, flags
            
        cleaned = text
        certainty_markers = [
            "definitely", "confirmed", "certainly", "is diagnosed with",
            "diagnosed with", "diagnosed as", "conclusive", "conclusively",
            "we are certain", "proven to have", "has confirmed", "positive for",
            "suffering from"
        ]
        
        for diag in self.unresolved_diagnoses:
            if not diag or len(diag.strip()) < 3:
                continue
            diag_term = diag.lower().replace("_", " ")
            diag_raw = diag.lower()
            sentences = re.split(r'(?<=[.!?\n])\s+', cleaned)
            new_sentences = []
            replaced_any = False
            for s in sentences:
                s_lower = s.lower()
                if (diag_term in s_lower or diag_raw in s_lower) and any(m in s_lower for m in certainty_markers):
                    replacement_note = (
                        f"Preliminary indicators suggest potential {diag_term}, but this diagnosis is currently "
                        f"UNRESOLVED. In-field scouting and tissue verification are required before taking corrective action."
                    )
                    flags.append(HallucinationFlag(
                        claim_type="unresolved_diagnosis",
                        claim_value=diag,
                        context=s.strip(),
                        action="replaced",
                        replacement=replacement_note,
                    ))
                    new_sentences.append(replacement_note)
                    replaced_any = True
                else:
                    new_sentences.append(s)
            if replaced_any:
                cleaned = " ".join(new_sentences)
                
        return cleaned, flags
    
    def _check_zones(self, text: str) -> tuple:
        """Flag zone IDs mentioned in text that are not in upstream zone_plan."""
        flags: List[HallucinationFlag] = []
        if not self.upstream_zones:
            return text, flags
        
        zone_pattern = r'\bzone[_\s-]?([A-Za-z0-9]+)\b'
        matches = re.finditer(zone_pattern, text, re.IGNORECASE)
        
        for match in matches:
            zone_id = f"zone_{match.group(1)}"
            if zone_id not in self.upstream_zones:
                flags.append(HallucinationFlag(
                    claim_type="zone",
                    claim_value=zone_id,
                    context=text[max(0, match.start()-20):match.end()+20],
                    action="flagged",
                ))
        
        return text, flags

    def _check_physical_constraints(self, text: str) -> tuple:
        """Enforce biochemically/biophysically safe limits for fertilizer and irrigation."""
        flags: List[HallucinationFlag] = []
        q_lower = text.lower()

        # 1. Urea application rate check
        urea_matches = re.finditer(r'\b(\d+(?:\.\d+)?)\s*(?:kg/ha|kg)\b', q_lower)
        for match in urea_matches:
            try:
                rate = float(match.group(1))
                sentence_start = max(0, match.start() - 60)
                sentence_end = min(len(text), match.end() + 60)
                sentence = q_lower[sentence_start:sentence_end]
                
                if "urea" in sentence or "nitrogen" in sentence or "engrais" in sentence or "fertilizer" in sentence:
                    if rate > 200.0:
                        flags.append(HallucinationFlag(
                            claim_type="physical_constraint",
                            claim_value=f"{rate} kg/ha",
                            context=text[max(0, match.start()-30):match.end()+30],
                            action="flagged",
                            replacement="200 kg/ha"
                        ))
            except ValueError:
                continue

        # 2. Soil Moisture & Field Capacity Saturation (Anoxia warning)
        if self.soil_moisture and self.soil_moisture >= 38.0:
            irrigation_matches = re.finditer(r'\b(\d+(?:\.\d+)?)\s*(?:mm|millimeters)\b', q_lower)
            for match in irrigation_matches:
                try:
                    amount = float(match.group(1))
                    sentence_start = max(0, match.start() - 60)
                    sentence_end = min(len(text), match.end() + 60)
                    sentence = q_lower[sentence_start:sentence_end]
                    
                    if "irrigate" in sentence or "irrigation" in sentence or "arrosage" in sentence or "water" in sentence:
                        if amount > 25.0:
                            flags.append(HallucinationFlag(
                                claim_type="physical_constraint",
                                claim_value=f"{amount} mm",
                                context=text[max(0, match.start()-30):match.end()+30],
                                action="flagged",
                                replacement="15 mm"
                            ))
                except ValueError:
                    continue

        return text, flags
    
    def get_summary(self, flags: List[HallucinationFlag]) -> Dict[str, Any]:
        """Summarize validation results."""
        return {
            "total_flags": len(flags),
            "by_type": {
                t: sum(1 for f in flags if f.claim_type == t)
                for t in ("number", "date", "zone", "chemical", "action", "physical_constraint", "unresolved_diagnosis")
                if any(f.claim_type == t for f in flags)
            },
            "passed": len(flags) == 0,
        }

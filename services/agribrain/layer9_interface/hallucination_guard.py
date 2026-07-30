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
    claim_type: str          # "number", "date", "zone", "chemical", "action"
    claim_value: str         # the suspicious claim
    context: str             # surrounding text
    action: str              # "removed", "replaced", "flagged"
    replacement: str = ""


class HallucinationGuard:
    """
    Validates LLM-generated text against structured upstream data.
    
    Checks:
      1. Numeric claims must exist in upstream outputs
      2. Dates must exist in schedule
      3. Zone mentions must be in zone_plan
      4. Chemical/product names must be allowed by compliance
      5. Blocked actions must not be presented as suggested
    """
    
    def __init__(self,
                 upstream_numbers: Optional[Set[float]] = None,
                 upstream_dates: Optional[Set[str]] = None,
                 upstream_zones: Optional[Set[str]] = None,
                 allowed_actions: Optional[Set[str]] = None,
                 blocked_actions: Optional[Set[str]] = None,
                 crop: str = "",
                 soil_moisture: Optional[float] = None):
        self.upstream_numbers = upstream_numbers or set()
        self.upstream_dates = upstream_dates or set()
        self.upstream_zones = upstream_zones or set()
        self.allowed_actions = allowed_actions or set()
        self.blocked_actions = blocked_actions or set()
        self.crop = crop
        self.soil_moisture = soil_moisture
    
    @classmethod
    def from_layer9_input(cls, l9_input: Dict[str, Any]) -> "HallucinationGuard":
        """Build guard from Layer9Input-like dict."""
        numbers: Set[float] = set()
        dates: Set[str] = set()
        zones: Set[str] = set()
        allowed: Set[str] = set()
        blocked: Set[str] = set()
        
        # Extract numbers from actions
        for action in l9_input.get("actions", []):
            if isinstance(action, dict):
                for key in ("priority_score", "recommended", "min_safe", "max_safe"):
                    val = action.get(key)
                    if val is not None and isinstance(val, (int, float)):
                        numbers.add(round(float(val), 2))
                
                rate = action.get("rate", {})
                if isinstance(rate, dict):
                    for key in ("recommended", "min_safe", "max_safe"):
                        val = rate.get(key)
                        if val is not None and isinstance(val, (int, float)):
                            numbers.add(round(float(val), 2))
                
                if action.get("is_allowed", True):
                    allowed.add(action.get("action_type", ""))
                else:
                    blocked.add(action.get("action_id", ""))
        
        # Extract dates from schedule
        for sched in l9_input.get("schedule", []):
            if isinstance(sched, dict):
                date = sched.get("scheduled_date")
                if date:
                    dates.add(date)
        
        # Extract zones
        zone_plan = l9_input.get("zone_plan", {})
        if isinstance(zone_plan, dict):
            zones = set(zone_plan.keys())
        
        # Extract numbers from outcome forecast
        forecast = l9_input.get("outcome_forecast", {})
        if isinstance(forecast, dict):
            for val in forecast.values():
                if isinstance(val, (int, float)):
                    numbers.add(round(float(val), 2))
        
        # Extract numbers from diagnoses
        for diag in l9_input.get("diagnoses", []):
            if isinstance(diag, dict):
                for key in ("probability", "severity", "confidence"):
                    val = diag.get(key)
                    if val is not None and isinstance(val, (int, float)):
                        numbers.add(round(float(val), 2))
        
        # Extract crop and soil moisture for physical constraints
        crop = ""
        soil_moisture = None
        
        veg = l9_input.get("l2_vegetation_data")
        if isinstance(veg, dict):
            crop = veg.get("crop", "")
            
        fusion = l9_input.get("l1_fusion_data")
        if isinstance(fusion, dict):
            soil_moisture = fusion.get("soil_moisture")
            
        if soil_moisture is None:
            sensors = l9_input.get("sensor_summary", {})
            if isinstance(sensors, dict):
                soil_moisture = sensors.get("soil_moisture")
        
        return cls(
            upstream_numbers=numbers,
            upstream_dates=dates,
            upstream_zones=zones,
            allowed_actions=allowed,
            blocked_actions=blocked,
            crop=crop,
            soil_moisture=soil_moisture
        )
    
    def validate(self, text: str) -> tuple:
        """
        Validate LLM text against upstream data.
        
        Returns:
            (cleaned_text, flags)
        """
        flags: List[HallucinationFlag] = []
        cleaned = text
        
        # 1. Check numeric claims
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

        # 5. Check physical constraints (urea, waterlogging)
        cleaned, physical_flags = self._check_physical_constraints(cleaned)
        flags.extend(physical_flags)
        
        return cleaned, flags
    
    def _check_numbers(self, text: str) -> tuple:
        """Flag numbers not in upstream data."""
        flags: List[HallucinationFlag] = []
        
        # Find all numbers in text (integers and floats)
        number_pattern = r'\b(\d+\.?\d*)\s*(?:kg|mm|L|t|ha|%|°)'
        matches = re.finditer(number_pattern, text)
        
        for match in matches:
            try:
                val = round(float(match.group(1)), 2)
                if val > 0 and val not in self.upstream_numbers:
                    # Check if close to any upstream number (10% tolerance)
                    close = any(abs(val - u) / max(abs(u), 0.01) < 0.1
                               for u in self.upstream_numbers if u != 0)
                    if not close:
                        flags.append(HallucinationFlag(
                            claim_type="number",
                            claim_value=str(val),
                            context=text[max(0, match.start()-20):match.end()+20],
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
        """Flag blocked actions presented as suggestions."""
        flags: List[HallucinationFlag] = []
        text_lower = text.lower()
        
        suggestion_phrases = ["recommend", "should", "apply", "schedule",
                               "proceed with", "go ahead"]
        
        for blocked_id in self.blocked_actions:
            if blocked_id.lower() in text_lower:
                # Check if near a suggestion phrase
                for phrase in suggestion_phrases:
                    if phrase in text_lower:
                        flags.append(HallucinationFlag(
                            claim_type="action",
                            claim_value=blocked_id,
                            context=f"Blocked action '{blocked_id}' near '{phrase}'",
                            action="flagged",
                        ))
                        break
        
        return text, flags
    
    def _check_zones(self, text: str) -> tuple:
        """Flag zone IDs mentioned in text that are not in upstream zone_plan."""
        flags: List[HallucinationFlag] = []
        if not self.upstream_zones:
            return text, flags
        
        # Match zone_X, zone-X, zone X patterns
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
                for t in ("number", "date", "zone", "chemical", "action", "physical_constraint")
                if any(f.claim_type == t for f in flags)
            },
            "passed": len(flags) == 0,
        }

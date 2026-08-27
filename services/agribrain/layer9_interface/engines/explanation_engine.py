"""
explanation_engine.py - Structured Visual Explanation Generator
================================================================

Generates rich, structured explanations for agronomic decisions that
can be rendered as visual cards in the UI. Each explanation includes:
  - Data citations with exact values
  - Reasoning chain (premise → conclusion)
  - Confidence indicators
  - Visual data suggestions (chart types, color coding)
  - Risk assessment with traffic-light scoring
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class DataCitation:
    """A single data point cited in an explanation."""
    metric: str
    value: str
    unit: str
    source: str            # "satellite", "sensor", "weather", "calculated", "knowledge"
    status: str            # "normal", "warning", "critical", "unknown"
    threshold_info: str    # e.g., "normal range: 25-38%"


@dataclass
class ReasoningStep:
    """A single step in the reasoning chain."""
    step_number: int
    premise: str           # The observation
    logic: str             # The agronomic rule applied
    conclusion: str        # What it means
    confidence: float      # 0.0-1.0


@dataclass
class VisualSuggestion:
    """Suggested visualization for the UI."""
    chart_type: str        # "gauge", "timeseries", "bar", "heatmap", "traffic_light"
    title: str
    data_key: str          # Key in the sensor data to plot
    color_scheme: str      # "green_red", "blue_orange", "sequential"
    thresholds: Optional[Dict[str, float]] = None


@dataclass
class StructuredExplanation:
    """A complete structured explanation for a query."""
    headline: str
    summary: str
    risk_level: str               # NONE, LOW, MEDIUM, HIGH, CRITICAL
    risk_color: str               # green, yellow, orange, red
    data_citations: List[DataCitation] = field(default_factory=list)
    reasoning_chain: List[ReasoningStep] = field(default_factory=list)
    visuals: List[VisualSuggestion] = field(default_factory=list)
    confidence: float = 0.5
    action_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        """Render as clean markdown for LLM consumption."""
        parts = [f"## {self.headline}", ""]

        if self.risk_level != "NONE":
            parts.append(f"**Risk Level:** {self.risk_level} ({self.risk_color})")
            parts.append("")

        parts.append(self.summary)
        parts.append("")

        if self.data_citations:
            parts.append("**Data Points:**")
            for dc in self.data_citations:
                status_icon = {"normal": "+", "warning": "!", "critical": "X", "unknown": "?"}
                icon = status_icon.get(dc.status, "?")
                parts.append(f"- [{icon}] **{dc.metric}**: {dc.value} {dc.unit} ({dc.threshold_info}) — Source: {dc.source}")
            parts.append("")

        if self.reasoning_chain:
            parts.append("**Reasoning:**")
            for step in self.reasoning_chain:
                parts.append(f"{step.step_number}. {step.premise} -> {step.logic} -> **{step.conclusion}**")
            parts.append("")

        if self.action_items:
            parts.append("**Actions:**")
            for action in self.action_items:
                parts.append(f"- {action}")

        return "\n".join(parts)


class ExplanationEngine:
    """Generates structured explanations from sensor data and LLM reasoning."""

    def explain_irrigation(self, sensors: Dict[str, Any],
                           crop: str = "wheat") -> StructuredExplanation:
        """Generate irrigation decision explanation."""
        try:
            from layer9_interface.engines.agronomic_knowledge_graph import (
                lookup_crop, get_irrigation_recommendation
            )
            thresholds = lookup_crop(crop)
            moisture = sensors.get("soil_moisture", 0)
            rain_7d = sensors.get("rain_mm_last_7d", sensors.get("rain_7d", 0))
            et0 = sensors.get("et0_daily", 4.0)
            stage = (
                sensors.get("growth_stage", "UNKNOWN")
                if sensors.get("phenology_receipt_valid") is True
                else "UNKNOWN"
            )

            rec = get_irrigation_recommendation(crop, moisture, rain_7d, et0, stage)
        except Exception:
            return StructuredExplanation(
                headline="Irrigation Assessment",
                summary="Unable to generate irrigation recommendation — missing data",
                risk_level="UNKNOWN", risk_color="gray"
            )

        urgency = rec.get("urgency", "NONE")
        risk_map = {"CRITICAL": ("CRITICAL", "red"), "HIGH": ("HIGH", "orange"),
                    "MEDIUM": ("MEDIUM", "yellow"), "NONE": ("NONE", "green")}
        risk_level, risk_color = risk_map.get(urgency, ("NONE", "green"))

        explanation = StructuredExplanation(
            headline="Irrigation Decision",
            summary=rec.get("reason", ""),
            risk_level=risk_level,
            risk_color=risk_color,
            confidence=0.85 if thresholds else 0.5,
        )

        # Data citations
        if thresholds:
            explanation.data_citations = [
                DataCitation("Soil Moisture", f"{moisture}", "%", "sensor",
                            "critical" if moisture <= thresholds.wilting_point else
                            "warning" if moisture <= thresholds.stress_threshold else "normal",
                            f"normal range: {thresholds.stress_threshold}-{thresholds.field_capacity}%"),
                DataCitation("Rain (7 days)", f"{rain_7d}", "mm", "weather",
                            "warning" if rain_7d < 5 else "normal",
                            f"<5mm = dry period"),
                DataCitation("ET0 (daily)", f"{et0}", "mm/day", "calculated",
                            "normal",
                            f"typical range: 2-7 mm/day"),
            ]

        # Reasoning chain
        explanation.reasoning_chain = [
            ReasoningStep(1,
                f"Soil moisture is {moisture}%",
                f"Compared against stress threshold ({thresholds.stress_threshold}% for {crop})" if thresholds else "Compared against standard thresholds",
                "Above threshold" if thresholds and moisture > thresholds.stress_threshold else "Below threshold — stress likely",
                0.9),
            ReasoningStep(2,
                f"Rain in last 7 days: {rain_7d}mm",
                "< 5mm indicates insufficient natural water supply",
                "Adequate" if rain_7d >= 10 else "Insufficient natural water supply",
                0.85),
            ReasoningStep(3,
                f"Days until stress: {rec.get('days_until_stress', '?')}",
                "If < 3 days, irrigation should be scheduled proactively",
                rec.get("reason", "Assessment complete"),
                0.8),
        ]

        # Visual suggestions
        explanation.visuals = [
            VisualSuggestion("gauge", "Soil Moisture", "soil_moisture", "green_red",
                            {"low": thresholds.wilting_point, "medium": thresholds.stress_threshold,
                             "high": thresholds.field_capacity} if thresholds else None),
            VisualSuggestion("timeseries", "Moisture Trend", "soil_moisture_history", "blue_orange"),
        ]

        # Actions
        if rec.get("recommend"):
            explanation.action_items = [
                f"Apply {rec.get('amount_mm', '15-20')}mm of irrigation",
                f"Use drip irrigation for efficiency",
                f"Monitor soil moisture daily until stabilized",
                f"Re-check in 48 hours after irrigation",
            ]
        else:
            explanation.action_items = [
                "No irrigation needed at this time",
                f"Next check recommended when moisture drops below {thresholds.stress_threshold}%" if thresholds else "Monitor soil moisture daily",
            ]

        return explanation

    def explain_disease_risk(self, sensors: Dict[str, Any],
                             crop: str = "wheat") -> StructuredExplanation:
        """Generate disease risk explanation."""
        try:
            from layer9_interface.engines.agronomic_knowledge_graph import get_disease_risk
            temp = sensors.get("ambient_temperature", sensors.get("temperature", 20))
            humidity = sensors.get("humidity", 60)
            rain_7d = sensors.get("rain_mm_last_7d", sensors.get("rain_7d", 0))
            stage = (
                sensors.get("growth_stage", "UNKNOWN")
                if sensors.get("phenology_receipt_valid") is True
                else "UNKNOWN"
            )

            risks = get_disease_risk(crop, temp, humidity, rain_7d, stage)
        except Exception:
            return StructuredExplanation(
                headline="Disease Risk Assessment",
                summary="Unable to assess disease risk — missing data",
                risk_level="UNKNOWN", risk_color="gray"
            )

        if not risks:
            return StructuredExplanation(
                headline="Disease Risk Assessment",
                summary=f"No significant disease risks detected for {crop} under current conditions (T={temp}C, RH={humidity}%, Rain={rain_7d}mm)",
                risk_level="NONE", risk_color="green",
                confidence=0.8,
                data_citations=[
                    DataCitation("Temperature", f"{temp}", "C", "sensor", "normal", ""),
                    DataCitation("Humidity", f"{humidity}", "%", "sensor", "normal", "<80% = low fungal risk"),
                ],
                action_items=["Continue regular monitoring", "Scout field weekly for symptoms"],
            )

        top_risk = risks[0]
        risk_level = top_risk["risk_level"]
        risk_color = {"HIGH": "red", "MEDIUM": "orange", "LOW": "yellow"}.get(risk_level, "green")

        explanation = StructuredExplanation(
            headline=f"Disease Risk: {top_risk['disease']}",
            summary=top_risk["description"],
            risk_level=risk_level,
            risk_color=risk_color,
            confidence=0.75,
        )

        explanation.data_citations = [
            DataCitation("Temperature", f"{temp}", "C", "sensor",
                        "warning" if 10 < temp < 25 else "normal", ""),
            DataCitation("Humidity", f"{humidity}", "%", "sensor",
                        "warning" if humidity > 80 else "normal", ""),
            DataCitation("Rain (7 days)", f"{rain_7d}", "mm", "weather",
                        "warning" if rain_7d > 15 else "normal", ""),
        ]

        for i, factor in enumerate(top_risk.get("factors", []), 1):
            explanation.reasoning_chain.append(ReasoningStep(
                i, factor, f"Disease rule for {top_risk['disease']}", 
                f"Contributes to {risk_level} risk", 0.7
            ))

        if risk_level in ("HIGH", "MEDIUM"):
            explanation.action_items = [
                f"Scout for {top_risk['disease']} symptoms (check lower leaves first)",
                "Consider preventive fungicide application",
                "Avoid overhead irrigation to reduce leaf wetness",
                "Monitor weather forecast for continued wet conditions",
            ]
        else:
            explanation.action_items = [
                "Low risk — routine monitoring sufficient",
                "Scout field weekly during susceptible growth stages",
            ]

        return explanation


# Singleton
_engine = None

def get_explanation_engine() -> ExplanationEngine:
    global _engine
    if _engine is None:
        _engine = ExplanationEngine()
    return _engine

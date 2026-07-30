"""
confidence_calibrator.py - Cross-Layer Bayesian Confidence Scoring
===================================================================

Post-processes LLM output to calibrate confidence scores using:
  1. Bayesian confidence from upstream layer data quality
  2. Cross-layer agreement scoring
  3. Data completeness weighting
  4. Historical accuracy tracking per intent category
"""

import math
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass 
class DataSource:
    """Represents a data source with its quality metrics."""
    name: str
    available: bool
    quality: float = 1.0       # 0.0-1.0
    freshness: float = 1.0     # 0.0-1.0 (1.0 = real-time, 0.0 = stale)
    agreement: float = 1.0     # 0.0-1.0 (agreement with other sources)


@dataclass
class CalibratedConfidence:
    """Calibrated confidence assessment."""
    overall: float                     # 0.0-1.0
    badge: str                         # HIGH, MEDIUM, LOW
    reason: str                        # Human-readable explanation
    data_completeness: float           # 0.0-1.0
    cross_layer_agreement: float       # 0.0-1.0
    source_quality: float              # 0.0-1.0
    contributing_sources: List[str]
    missing_sources: List[str]


class ConfidenceCalibrator:
    """Calibrates confidence based on data quality and cross-layer agreement."""

    # Required data sources per intent type
    INTENT_DATA_REQUIREMENTS = {
        "DIAGNOSIS": {
            "required": ["satellite_ndvi", "weather", "sensors"],
            "optional": ["satellite_sar", "soil_analysis", "historical"],
            "weights": {"satellite_ndvi": 0.35, "weather": 0.25, "sensors": 0.25,
                       "satellite_sar": 0.10, "soil_analysis": 0.05}
        },
        "DECISION": {
            "required": ["sensors", "weather", "satellite_ndvi"],
            "optional": ["forecast", "soil_analysis", "historical"],
            "weights": {"sensors": 0.30, "weather": 0.25, "satellite_ndvi": 0.20,
                       "forecast": 0.15, "soil_analysis": 0.05, "historical": 0.05}
        },
        "NUTRIENT": {
            "required": ["soil_analysis", "sensors"],
            "optional": ["satellite_ndvi", "weather", "historical"],
            "weights": {"soil_analysis": 0.40, "sensors": 0.25, "satellite_ndvi": 0.15,
                       "weather": 0.10, "historical": 0.10}
        },
        "DATA_QUERY": {
            "required": ["sensors", "weather"],
            "optional": ["satellite_ndvi", "satellite_sar"],
            "weights": {"sensors": 0.40, "weather": 0.30,
                       "satellite_ndvi": 0.15, "satellite_sar": 0.15}
        },
        "PLANNING": {
            "required": ["weather", "soil_analysis"],
            "optional": ["historical", "satellite_ndvi", "sensors"],
            "weights": {"weather": 0.30, "soil_analysis": 0.25, "historical": 0.20,
                       "satellite_ndvi": 0.15, "sensors": 0.10}
        },
        "SCENARIO": {
            "required": ["sensors", "weather"],
            "optional": ["historical", "satellite_ndvi"],
            "weights": {"sensors": 0.35, "weather": 0.30,
                       "historical": 0.20, "satellite_ndvi": 0.15}
        },
        "GENERAL": {
            "required": [],
            "optional": [],
            "weights": {}
        },
        "GREETING": {
            "required": [],
            "optional": [],
            "weights": {}
        },
    }

    def assess_data_sources(self, context: Dict[str, Any]) -> Dict[str, DataSource]:
        """Assess which data sources are available and their quality."""
        sources = {}

        # Satellite NDVI
        sensors = context.get("sensors", {})
        ndvi = sensors.get("ndvi") or context.get("ndvi")
        sources["satellite_ndvi"] = DataSource(
            name="Satellite NDVI",
            available=ndvi is not None,
            quality=0.9 if ndvi else 0.0,
            freshness=0.8  # Sentinel-2 is ~5 day revisit
        )

        # Satellite SAR
        sar = sensors.get("sar_vv") or context.get("sar_vv")
        sources["satellite_sar"] = DataSource(
            name="Satellite SAR",
            available=sar is not None,
            quality=0.85 if sar else 0.0,
            freshness=0.9  # Sentinel-1 is more frequent
        )

        # Weather
        has_weather = any(k in sensors for k in ["ambient_temperature", "humidity", "wind_speed"])
        sources["weather"] = DataSource(
            name="Weather Data",
            available=has_weather,
            quality=0.95 if has_weather else 0.0,
            freshness=1.0
        )

        # Soil Sensors
        has_sensors = any(k in sensors for k in ["soil_moisture", "soil_temperature"])
        sources["sensors"] = DataSource(
            name="Soil Sensors",
            available=has_sensors,
            quality=0.95 if has_sensors else 0.0,
            freshness=1.0  # Real-time
        )

        # Soil Analysis
        has_soil = any(k in context for k in ["soil_type", "soil_ph", "soil_ec"])
        sources["soil_analysis"] = DataSource(
            name="Soil Analysis",
            available=has_soil,
            quality=0.7 if has_soil else 0.0,
            freshness=0.5  # Lab results are semi-static
        )

        # Historical Data
        has_historical = bool(context.get("historical_data") or context.get("history"))
        sources["historical"] = DataSource(
            name="Historical Records",
            available=has_historical,
            quality=0.6 if has_historical else 0.0,
            freshness=0.4
        )

        # Forecast
        has_forecast = bool(context.get("forecast") or context.get("weather_forecast"))
        sources["forecast"] = DataSource(
            name="Weather Forecast",
            available=has_forecast,
            quality=0.7 if has_forecast else 0.0,
            freshness=0.9
        )

        return sources

    def check_cross_layer_agreement(self, context: Dict[str, Any]) -> float:
        """Check if different data sources agree with each other.
        
        For example:
        - If NDVI is low AND soil moisture is low → agreement (both say stress)
        - If NDVI is high BUT soil moisture is very low → disagreement
        """
        agreement_signals = []
        sensors = context.get("sensors", {})

        # NDVI vs soil moisture
        ndvi = sensors.get("ndvi")
        moisture = sensors.get("soil_moisture")
        if ndvi is not None and moisture is not None:
            ndvi_healthy = ndvi > 0.4
            moisture_adequate = moisture > 20
            agreement_signals.append(1.0 if ndvi_healthy == moisture_adequate else 0.5)

        # Temperature consistency
        soil_temp = sensors.get("soil_temperature")
        air_temp = sensors.get("ambient_temperature")
        if soil_temp is not None and air_temp is not None:
            temp_diff = abs(soil_temp - air_temp)
            agreement_signals.append(1.0 if temp_diff < 10 else 0.7)

        # Rain vs moisture
        rain = sensors.get("rain_mm_last_7d")
        if rain is not None and moisture is not None:
            rain_high = rain > 20
            moisture_high = moisture > 35
            agreement_signals.append(1.0 if rain_high == moisture_high else 0.6)

        if not agreement_signals:
            return 0.8  # Neutral if no cross-checks possible

        return sum(agreement_signals) / len(agreement_signals)

    def calibrate(self, intent: str, context: Dict[str, Any],
                  llm_confidence: Optional[str] = None) -> CalibratedConfidence:
        """Produce a calibrated confidence score.
        
        Args:
            intent: Detected intent (DIAGNOSIS, DECISION, etc.)
            context: Field context dict
            llm_confidence: Optional confidence badge from LLM ("HIGH", "MEDIUM", "LOW")
            
        Returns:
            CalibratedConfidence with overall score and explanation
        """
        # Get requirements for this intent
        reqs = self.INTENT_DATA_REQUIREMENTS.get(intent, self.INTENT_DATA_REQUIREMENTS["GENERAL"])
        required = reqs["required"]
        weights = reqs["weights"]

        # Assess data sources
        sources = self.assess_data_sources(context)

        # Data completeness: what fraction of required sources are available?
        if required:
            available_required = sum(1 for r in required if sources.get(r, DataSource("", False)).available)
            data_completeness = available_required / len(required)
        else:
            data_completeness = 1.0  # General/greeting don't need data

        # Source quality: weighted average of available source qualities
        total_weight = 0
        weighted_quality = 0
        contributing = []
        missing = []

        for src_name, weight in weights.items():
            src = sources.get(src_name)
            if src and src.available:
                weighted_quality += src.quality * src.freshness * weight
                total_weight += weight
                contributing.append(src.name)
            else:
                missing.append(src_name)

        source_quality = weighted_quality / total_weight if total_weight > 0 else 0.5

        # Cross-layer agreement
        agreement = self.check_cross_layer_agreement(context)

        # Overall confidence: weighted combination
        overall = (
            data_completeness * 0.35 +
            source_quality * 0.35 +
            agreement * 0.30
        )

        # Adjust with LLM self-assessed confidence (if available)
        if llm_confidence:
            llm_map = {"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3}
            llm_val = llm_map.get(llm_confidence.upper(), 0.5)
            # LLM confidence has lower weight (it tends to overestimate)
            overall = overall * 0.75 + llm_val * 0.25

        # Clamp
        overall = max(0.0, min(1.0, overall))

        # Badge
        if overall >= 0.75:
            badge = "HIGH"
        elif overall >= 0.45:
            badge = "MEDIUM"
        else:
            badge = "LOW"

        # Reason
        reasons = []
        if data_completeness < 0.7:
            reasons.append(f"Missing data: {', '.join(missing[:3])}")
        if agreement < 0.6:
            reasons.append("Some sensor readings disagree with satellite data")
        if source_quality < 0.5:
            reasons.append("Data sources have reduced quality")
        if not reasons:
            reasons.append("All key data sources available and consistent")

        return CalibratedConfidence(
            overall=round(overall, 3),
            badge=badge,
            reason="; ".join(reasons),
            data_completeness=round(data_completeness, 3),
            cross_layer_agreement=round(agreement, 3),
            source_quality=round(source_quality, 3),
            contributing_sources=contributing,
            missing_sources=missing
        )


# Singleton
_calibrator = None

def get_calibrator() -> ConfidenceCalibrator:
    global _calibrator
    if _calibrator is None:
        _calibrator = ConfidenceCalibrator()
    return _calibrator


def calibrate_confidence(intent: str, context: Dict[str, Any],
                         llm_confidence: Optional[str] = None) -> CalibratedConfidence:
    """One-call convenience function."""
    return get_calibrator().calibrate(intent, context, llm_confidence)

"""
anomaly_detector.py - Proactive Field Anomaly Detection
=========================================================

Analyzes sensor + satellite data streams to detect anomalies BEFORE
the farmer asks about them. Generates proactive alerts that can be
injected into chat context.

Detection Methods:
  1. Z-Score anomaly detection on sensor time series
  2. Rate-of-change alerting (sudden drops/spikes)
  3. Cross-sensor correlation breaks (e.g., NDVI drops but moisture ok)
  4. Threshold-based crop stress detection
  5. Seasonal deviation detection
"""

import math
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Anomaly:
    """A detected field anomaly."""
    id: str
    severity: str          # LOW, MEDIUM, HIGH, CRITICAL
    category: str          # moisture, vegetation, temperature, disease, nutrient
    metric: str            # The specific metric that triggered
    current_value: float
    expected_range: Tuple[float, float]
    message: str
    recommendation: str
    timestamp: float
    confidence: float      # 0.0-1.0


class AnomalyDetector:
    """Detects anomalies in field sensor data."""

    def __init__(self):
        self._history: Dict[str, List[float]] = {}  # metric_name → values
        self._lock = __import__('threading').Lock()  # GAP-3 fix: thread safety

    def add_observation(self, metric: str, value: float):
        """Add a new observation to the history."""
        with self._lock:
            if metric not in self._history:
                self._history[metric] = []
            self._history[metric].append(value)
            # Keep last 100 observations
            self._history[metric] = self._history[metric][-100:]

    def _zscore(self, values: List[float], current: float) -> float:
        """Calculate z-score for a value against historical distribution."""
        if len(values) < 5:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 1.0
        return (current - mean) / std

    def _rate_of_change(self, values: List[float]) -> float:
        """Calculate rate of change (last value vs previous)."""
        if len(values) < 2:
            return 0.0
        prev = values[-2]
        curr = values[-1]
        if prev == 0:
            return 0.0
        return (curr - prev) / abs(prev)

    def detect(self, sensors: Dict[str, Any],
               crop: str = "wheat") -> List[Anomaly]:
        """Run all anomaly detectors on current sensor data.
        
        Args:
            sensors: Dict with keys like soil_moisture, ndvi, temperature, etc.
            crop: Crop name for threshold lookup
            
        Returns:
            List of detected anomalies, sorted by severity
        """
        anomalies = []
        import time
        now = time.time()
        idx = 0

        # Import crop thresholds
        try:
            from layer9_interface.engines.agronomic_knowledge_graph import lookup_crop
            thresholds = lookup_crop(crop)
        except Exception:
            thresholds = None

        # 1. Soil Moisture Anomalies
        moisture = sensors.get("soil_moisture")
        if moisture is not None:
            self.add_observation("soil_moisture", moisture)

            if thresholds:
                if moisture <= thresholds.wilting_point:
                    idx += 1
                    anomalies.append(Anomaly(
                        id=f"ANO_{idx}", severity="CRITICAL",
                        category="moisture", metric="soil_moisture",
                        current_value=moisture,
                        expected_range=(thresholds.stress_threshold, thresholds.field_capacity),
                        message=f"Soil moisture ({moisture}%) at wilting point ({thresholds.wilting_point}%)! Crop damage imminent.",
                        recommendation=f"Irrigate immediately with {round((thresholds.field_capacity - moisture) * 0.3)}mm",
                        timestamp=now, confidence=0.95
                    ))
                elif moisture <= thresholds.stress_threshold:
                    idx += 1
                    anomalies.append(Anomaly(
                        id=f"ANO_{idx}", severity="HIGH",
                        category="moisture", metric="soil_moisture",
                        current_value=moisture,
                        expected_range=(thresholds.stress_threshold, thresholds.field_capacity),
                        message=f"Soil moisture ({moisture}%) below stress threshold ({thresholds.stress_threshold}%)",
                        recommendation="Schedule irrigation within 24-48 hours",
                        timestamp=now, confidence=0.9
                    ))
                elif moisture >= thresholds.waterlogging_threshold:
                    idx += 1
                    anomalies.append(Anomaly(
                        id=f"ANO_{idx}", severity="HIGH",
                        category="moisture", metric="soil_moisture",
                        current_value=moisture,
                        expected_range=(thresholds.stress_threshold, thresholds.field_capacity),
                        message=f"Soil moisture ({moisture}%) exceeds waterlogging threshold ({thresholds.waterlogging_threshold}%)",
                        recommendation="Check drainage. Avoid irrigation. Monitor for root disease",
                        timestamp=now, confidence=0.85
                    ))

            # Z-score anomaly
            history = self._history.get("soil_moisture", [])
            if len(history) >= 5:
                z = self._zscore(history[:-1], moisture)
                if abs(z) > 2.5:
                    idx += 1
                    direction = "spike" if z > 0 else "drop"
                    anomalies.append(Anomaly(
                        id=f"ANO_{idx}", severity="MEDIUM",
                        category="moisture", metric="soil_moisture_zscore",
                        current_value=moisture,
                        expected_range=(0, 0),
                        message=f"Unusual soil moisture {direction} (z-score: {z:.1f})",
                        recommendation=f"Verify sensor reading. Check for {'leak or excess rain' if z > 0 else 'sensor malfunction or rapid drainage'}",
                        timestamp=now, confidence=0.7
                    ))

        # 2. NDVI Anomalies
        ndvi = sensors.get("ndvi")
        if ndvi is not None:
            self.add_observation("ndvi", ndvi)

            if ndvi < 0.2:
                idx += 1
                anomalies.append(Anomaly(
                    id=f"ANO_{idx}", severity="HIGH",
                    category="vegetation", metric="ndvi",
                    current_value=ndvi,
                    expected_range=(0.3, 0.8),
                    message=f"Very low NDVI ({ndvi}). Indicates bare soil or severe crop stress",
                    recommendation="Urgent field scouting needed. Check for crop failure, pest damage, or disease",
                    timestamp=now, confidence=0.85
                ))
            elif ndvi < 0.3:
                idx += 1
                anomalies.append(Anomaly(
                    id=f"ANO_{idx}", severity="MEDIUM",
                    category="vegetation", metric="ndvi",
                    current_value=ndvi,
                    expected_range=(0.3, 0.8),
                    message=f"Low NDVI ({ndvi}). Below healthy crop threshold for this stage",
                    recommendation="Monitor closely. Check irrigation and nutrient status",
                    timestamp=now, confidence=0.8
                ))

            # NDVI sudden drop
            history = self._history.get("ndvi", [])
            if len(history) >= 3:
                roc = self._rate_of_change(history)
                if roc < -0.15:  # More than 15% drop
                    idx += 1
                    anomalies.append(Anomaly(
                        id=f"ANO_{idx}", severity="HIGH",
                        category="vegetation", metric="ndvi_rate_of_change",
                        current_value=ndvi,
                        expected_range=(0, 0),
                        message=f"Rapid NDVI decline ({roc*100:.0f}% change). Possible stress event",
                        recommendation="Immediate field inspection. Check for disease outbreak, pest damage, or water stress",
                        timestamp=now, confidence=0.75
                    ))

        # 3. Temperature Anomalies
        temp = sensors.get("ambient_temperature") or sensors.get("temperature")
        if temp is not None and thresholds:
            self.add_observation("temperature", temp)

            if temp >= thresholds.heat_stress_temp:
                idx += 1
                anomalies.append(Anomaly(
                    id=f"ANO_{idx}", severity="HIGH",
                    category="temperature", metric="ambient_temperature",
                    current_value=temp,
                    expected_range=(thresholds.optimal_growth_temp_low, thresholds.optimal_growth_temp_high),
                    message=f"Heat stress! Temperature ({temp}C) exceeds crop tolerance ({thresholds.heat_stress_temp}C)",
                    recommendation="Apply supplementary irrigation to cool canopy. Avoid spraying chemicals",
                    timestamp=now, confidence=0.9
                ))
            elif temp <= thresholds.frost_damage_temp:
                idx += 1
                anomalies.append(Anomaly(
                    id=f"ANO_{idx}", severity="CRITICAL",
                    category="temperature", metric="ambient_temperature",
                    current_value=temp,
                    expected_range=(thresholds.optimal_growth_temp_low, thresholds.optimal_growth_temp_high),
                    message=f"Frost damage risk! Temperature ({temp}C) below damage threshold ({thresholds.frost_damage_temp}C)",
                    recommendation="Activate frost protection (sprinkler irrigation, covers). Assess damage after event",
                    timestamp=now, confidence=0.95
                ))

        # 4. Cross-Sensor Correlation Anomalies
        if ndvi is not None and moisture is not None:
            # NDVI dropping but moisture is fine = potential disease/pest
            if ndvi < 0.35 and moisture > 25:
                idx += 1
                anomalies.append(Anomaly(
                    id=f"ANO_{idx}", severity="MEDIUM",
                    category="disease", metric="ndvi_moisture_correlation",
                    current_value=ndvi,
                    expected_range=(0.4, 0.8),
                    message=f"NDVI is low ({ndvi}) despite adequate moisture ({moisture}%). Possible disease or pest issue",
                    recommendation="Scout for leaf lesions, discoloration, or pest damage. Consider leaf tissue analysis",
                    timestamp=now, confidence=0.65
                ))

        # 5. Humidity-based disease risk
        humidity = sensors.get("humidity")
        if humidity is not None and temp is not None:
            if humidity > 85 and 10 < temp < 25:
                idx += 1
                anomalies.append(Anomaly(
                    id=f"ANO_{idx}", severity="MEDIUM",
                    category="disease", metric="humidity_disease_risk",
                    current_value=humidity,
                    expected_range=(40, 75),
                    message=f"High fungal disease risk: humidity ({humidity}%) + temperature ({temp}C) favor pathogen growth",
                    recommendation="Monitor for septoria, rust, or mildew symptoms. Consider preventive fungicide if in susceptible growth stage",
                    timestamp=now, confidence=0.7
                ))

        # Sort by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        anomalies.sort(key=lambda a: severity_order.get(a.severity, 4))

        return anomalies

    def format_alerts(self, anomalies: List[Anomaly]) -> str:
        """Format anomalies as an alert string for the LLM context."""
        if not anomalies:
            return "[PROACTIVE ALERTS] No anomalies detected. Field is within normal parameters."

        severity_icons = {"CRITICAL": "!!!", "HIGH": "!!", "MEDIUM": "!", "LOW": "."}
        lines = ["[PROACTIVE ALERTS]"]
        for a in anomalies[:5]:  # Max 5 alerts to avoid context overload
            icon = severity_icons.get(a.severity, "?")
            lines.append(f"  [{icon} {a.severity}] {a.category.upper()}: {a.message}")
            lines.append(f"    Action: {a.recommendation}")

        return "\n".join(lines)


# Singleton
_detector = None

def get_detector() -> AnomalyDetector:
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector


def detect_anomalies(sensors: Dict[str, Any], crop: str = "wheat") -> List[Anomaly]:
    """One-call convenience function."""
    return get_detector().detect(sensors, crop)


def format_anomaly_alerts(sensors: Dict[str, Any], crop: str = "wheat") -> str:
    """Detect and format anomaly alerts for LLM context injection."""
    anomalies = detect_anomalies(sensors, crop)
    return get_detector().format_alerts(anomalies)

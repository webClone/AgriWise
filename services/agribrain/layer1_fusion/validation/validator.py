
"""
Layer 1.1.2: Validation & Trust System.
Implements the 'Trust System' to flag or reject data before fusion.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from ..schema import EvidenceItem, ValidationStatus, EvidenceSourceType

class ValidationRule:
    """Base class for validation logic."""
    def validate(self, item: EvidenceItem) -> Tuple[bool, Optional[str]]:
        """
        Returns (is_valid, reason).
        True = Pass
        False = Flag/Reject (depending on severity)
        """
        raise NotImplementedError

class S2CloudCheck(ValidationRule):
    """Checks Sentinel-2 scenes for excessive cloud cover."""
    def __init__(self, threshold: float = 30.0):
        self.threshold = threshold

    def validate(self, item: EvidenceItem) -> Tuple[bool, Optional[str]]:
        if item.source_type != EvidenceSourceType.SATELLITE_OPTICAL:
            return True, None
            
        cloud_pct = item.payload.get("cloud_cover", 100.0)
        if cloud_pct > self.threshold:
            return False, f"Cloud cover {cloud_pct}% exceeds {self.threshold}% threshold"
        return True, None

class ValueRangeCheck(ValidationRule):
    """Checks if numeric values are within physical limits."""
    def validate(self, item: EvidenceItem) -> Tuple[bool, Optional[str]]:
        # Example for NDVI
        if "ndvi" in item.payload:
            val = item.payload["ndvi"]
            if not (-1.0 <= val <= 1.0):
                return False, f"NDVI {val} out of range [-1, 1]"
        
        # Example for Temp
        if "temperature_mean" in item.payload:
            val = item.payload["temperature_mean"]
            if not (-50 <= val <= 60):
                return False, f"Temp {val}°C physically improbable"
                
        return True, None

class SensorSpikeCheck(ValidationRule):
    """
    Checks for impossible instantaneous jumps.
    Note: Requires history, simpler stateless version here for MVP.
    """
    def validate(self, item: EvidenceItem) -> Tuple[bool, Optional[str]]:
        if item.source_type == EvidenceSourceType.SENSOR:
            # Placeholder for spike detection
            pass
        return True, None

class BatchValidationRule:
    """Base class for validation logic requiring full context."""
    def validate_batch(self, items: List[EvidenceItem]) -> List[EvidenceItem]:
        """
        Validates a list of items together.
        Returns the modified list (with flags updated).
        """
        raise NotImplementedError

class TemporalConsistencyCheck(BatchValidationRule):
    """
    Flags items that deviate significantly from their neighbors (Z-Score).
    """
    def validate_batch(self, items: List[EvidenceItem]) -> List[EvidenceItem]:
        # Filter for NDVI-containing items
        ndvi_items = [i for i in items if i.source_type == EvidenceSourceType.SATELLITE_OPTICAL and "ndvi" in i.payload]
        if len(ndvi_items) < 3:
            return items # Not enough data for stats
            
        # Sort by time
        ndvi_items.sort(key=lambda x: x.timestamp)
        
        values = [i.payload["ndvi"] for i in ndvi_items]
        
        # Calculate Rolling Mean/Std (Leave-One-Out for sensitivity)
        for idx, item in enumerate(ndvi_items):
            # Window: previous 2 and next 2 (5-point window preferred, fallback to available)
            start_i = max(0, idx - 2)
            end_i = min(len(values), idx + 3)
            
            # Neighbors excluding self
            neighbors = [values[i] for i in range(start_i, end_i) if i != idx]
            
            if len(neighbors) < 2: continue
            
            mean = sum(neighbors) / len(neighbors)
            std = (sum([(x - mean)**2 for x in neighbors]) / len(neighbors)) ** 0.5
            
            if std < 0.01: std = 0.01 # Prevent division by zero / extreme sensitivity
            
            val = item.payload["ndvi"]
            z_score = abs((val - mean) / std)
            
            if z_score > 3.0: # 3 Sigma (very likely anomaly)
                item.status = ValidationStatus.FLAGGED
                item.flags.append("temporal_anomaly")
                item.reason_codes.append(f"NDVI Z-Score {z_score:.2f} > 3.0")
                item.confidence_score *= 0.6
                
        return items

class SensorDriftCheck(BatchValidationRule):
    """
    Checks for:
    1. Stuck Sensor (Variance ~ 0 over time)
    2. High Frequency Noise (Excessive Variance)
    """
    def validate_batch(self, items: List[EvidenceItem]) -> List[EvidenceItem]:
        # Group by sensor_id if available, else source_type
        # For MVP, we treat S2 as one sensor
        s2_items = [i for i in items if i.source_type == EvidenceSourceType.SATELLITE_OPTICAL]
        if len(s2_items) < 5: return items
        
        values = [i.payload.get("ndvi", 0) for i in s2_items]
        
        # Whole-batch variance (simplification for "Drift/Stuck" check)
        mean = sum(values) / len(values)
        variance = sum([(x - mean)**2 for x in values]) / len(values)
        
        # 1. Check for Stuck Sensor
        if variance < 1e-6:
            for item in s2_items:
                item.status = ValidationStatus.FLAGGED
                item.flags.append("sensor_stuck")
                item.reason_codes.append("Variance ~ 0 (Stuck Signal)")
                item.confidence_score *= 0.1
                
        # 2. Check for Extreme Noise (unlikely for NDVI unless clouds failed)
        if variance > 0.1: # 0.1 Variance is ~0.31 Std Dev (Very high for 5 days)
             for item in s2_items:
                item.flags.append("sensor_noise")
                item.reason_codes.append(f"High Variance {variance:.2f}")
                
        return items

class TrustSystem:
    """
    The Gatekeeper. Runs all rules on incoming Evidence.
    """
    def __init__(self):
        self.item_rules = [
            S2CloudCheck(threshold=30.0),
            ValueRangeCheck()
        ]
        self.batch_rules = [
            TemporalConsistencyCheck(),
            SensorDriftCheck()
        ]

    def validate_batch(self, items: List[EvidenceItem]) -> List[EvidenceItem]:
        # 1. Run Item checks
        for item in items:
            for rule in self.item_rules:
                is_valid, reason = rule.validate(item)
                if not is_valid:
                    item.status = ValidationStatus.FLAGGED
                    item.flags.append(reason)
                    item.reason_codes.append(reason)
                    item.confidence_score *= 0.5
                elif item.status == ValidationStatus.PENDING:
                    item.status = ValidationStatus.ACCEPTED

        # 2. Run Batch checks (Context-aware)
        for rule in self.batch_rules:
            items = rule.validate_batch(items)
            
        return items

# Singleton
trust_system = TrustSystem()

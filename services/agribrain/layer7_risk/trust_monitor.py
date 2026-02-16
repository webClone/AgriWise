"""
Layer 7.4: Drift & Trust Monitor.
Evaluates data quality and model confidence.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta

class TrustMonitor:
    
    def evaluate_trust(self, 
                       last_satellite_date: datetime, 
                       sensor_active: bool,
                       forecast_available: bool) -> Dict[str, Any]:
        """
        Compute Trust Score based on data freshness and availability.
        """
        now = datetime.now() # Mock current time in simulation usually
        days_since_sat = (now - last_satellite_date).days
        
        score = 100
        issues = []
        actions = []
        
        # 1. Satellite Freshness
        if days_since_sat > 10:
            score -= 30
            issues.append(f"No Satellite Image for {days_since_sat} days")
            actions.append("Upload drone/phone photo")
        elif days_since_sat > 5:
            score -= 10
            issues.append("Satellite Data aging")
            
        # 2. Sensor Health
        if not sensor_active:
            score -= 20
            issues.append("No active Soil Sensor (Model-only mode)")
            actions.append("Consider installing sensor for precision")
            
        # 3. Forecast
        if not forecast_available:
            score -= 20
            issues.append("Missing Weather Forecast")
            
        # Clamp
        score = max(0, score)
        
        level = "High"
        if score < 80: level = "Moderate"
        if score < 50: level = "Low"
        
        return {
            "trust_score": score,
            "trust_level": level,
            "issues": issues,
            "suggested_actions": actions
        }

# Singleton
trust_monitor = TrustMonitor()

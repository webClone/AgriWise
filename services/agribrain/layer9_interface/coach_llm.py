"""
Layer 9.5: Data-Gap Coach.
Encourages data contribution to improve model trust.
"""

from typing import Dict, Any, List

class DataCoach:
    
    def generate_coaching_tip(self, trust_report: Dict[str, Any]) -> Dict[str, str]:
        """
        Suggest 'One Thing' to improve accuracy.
        """
        issues = trust_report.get("issues", [])
        score = trust_report.get("trust_score", 100)
        
        if score > 90:
            return {
                "tip": "Great data quality! You're all set.",
                "value_prop": "Maintain high accuracy.",
                "effort": "None"
            }
            
        # Priority Logic
        # 1. Missing Satellite (Highest)
        # 2. Missing Sensor
        # 3. Missing Scout Info
        
        tip = "Update field data."
        value = "Better predictions."
        effort = "Low"
        
        for issue in issues:
            if "Satellite" in issue:
                tip = "Upload a ground photo of the crop."
                value = "Verifies canopy cover when satellite is old."
                effort = "30 seconds"
                break
            if "Sensor" in issue:
                tip = "Check your soil sensor connection."
                value = "Enables precise irrigation advice."
                effort = "5 minutes"
                break
                
        return {
            "tip": tip,
            "value_prop": value,
            "effort": effort,
            "impact_score": "High"
        }

# Singleton
coach = DataCoach()

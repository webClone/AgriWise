"""
Layer 9.6: Safe Action Policy (Guardrails).
Ensures advice is safe, compliant, and trustworthy.
"""

from typing import Dict, Any, List

class PolicyRouter:
    
    def filter_advice(self, advice_text: str, action_type: str, confidence: str) -> str:
        """
        Apply rules to sanitize advice.
        """
        filtered_text = advice_text
        
        # Rule 1: Safety Disclaimer for Chemicals
        if "spray" in action_type.lower() or "fungicide" in action_type.lower():
            filtered_text += "\n\n⚠️ SAFETY: Ensure compliance with local regulations and check product label constraints before application."
            
        # Rule 2: Low Confidence Guardrail
        if confidence == "Low":
            filtered_text = "⚠️ LOW CONFIDENCE WARNING: \n" + filtered_text
            filtered_text += "\nRecommendation: Scout the field to verify conditions before taking action."
            
        return filtered_text

    def check_compliance(self, action: Dict[str, Any]) -> bool:
        """
        Block restricted actions?
        """
        # Placeholder for regulatory blocks
        return True 

# Singleton
policy = PolicyRouter()

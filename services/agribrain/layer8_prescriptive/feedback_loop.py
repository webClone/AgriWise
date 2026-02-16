"""
Layer 8.4: Feedback Learning Loop.
Recalibrates models based on Observed vs Predicted outcomes.
"""

from typing import Dict, Any

class FeedbackLoop:
    
    def update_calibration(self, 
                           action_record: Dict[str, Any], 
                           observed_outcome: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare Prediction vs Reality.
        Update Trust Scores or Bias Factors.
        """
        pred_gain = action_record.get("predicted_yield_gain", 0)
        obs_gain = observed_outcome.get("observed_yield_gain", 0)
        
        error = obs_gain - pred_gain
        percent_error = (error / pred_gain) * 100 if pred_gain > 0 else 0
        
        # Diagnosis
        status = "Accurate"
        calibration_action = "None"
        
        if percent_error > 20:
            status = "Underestimated"
            calibration_action = "Increase Response Factor (+10%)"
        elif percent_error < -20:
            status = "Overestimated"
            calibration_action = "Decrease Response Factor (-10%)"
            
        return {
            "prediction_error_pct": round(percent_error, 1),
            "status": status,
            "calibration_recommendation": calibration_action,
            "learning_log": f"Action {action_record.get('action')} yielded {obs_gain} vs pred {pred_gain}. Error: {percent_error:.1f}%"
        }

# Singleton
feedback_engine = FeedbackLoop()

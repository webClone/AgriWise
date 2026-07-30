"""
Layer 8.4: Feedback Learning Loop.
Recalibrates models based on Observed vs Predicted outcomes.
"""

from typing import Dict, Any
import numpy as np
from layer8_prescriptive.engines.adoption_model import adoption_engine

class FeedbackLoop:
    
    def update_calibration(self, 
                           action_record: Dict[str, Any], 
                           observed_outcome: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare Prediction vs Reality.
        Update Trust Scores or Bias Factors.
        Calibrates the Neural Network adoption model if adoption feedback is present.
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
            
        learning_log = f"Action {action_record.get('action')} yielded {obs_gain} vs pred {pred_gain}. Error: {percent_error:.1f}%"
        
        # ML Online Calibration for Farmer Adoption Neural Network
        usefulness = action_record.get("perceived_usefulness", action_record.get("usefulness", 0.5))
        ease = action_record.get("perceived_ease", action_record.get("ease", 0.5))
        familiarity = action_record.get("familiarity_score", action_record.get("familiarity", 0.5))
        cost_sensitivity = action_record.get("cost_sensitivity", 0.5)
        trust_grade_score = action_record.get("trust_grade_score", action_record.get("trust_score", 0.8))
        urgency = action_record.get("urgency_score", action_record.get("urgency", 0.5))
        
        observed_adoption = None
        for key in ["observed_adoption", "accepted", "adopted", "compliance"]:
            if key in observed_outcome:
                observed_adoption = float(observed_outcome[key])
                break
                
        if observed_adoption is not None:
            # Construct input vector (batch_size=1, features=6)
            x = [[usefulness, ease, familiarity, cost_sensitivity, trust_grade_score, urgency]]
            y_true = [[observed_adoption]]
            
            # Record weight matrix norms for calibration logging
            W1_norm_before = float(np.linalg.norm(adoption_engine.W1))
            W2_norm_before = float(np.linalg.norm(adoption_engine.W2))
            
            # Run one epoch gradient descent step
            adoption_engine.train_step(x, y_true, lr=0.1)
            
            W1_norm_after = float(np.linalg.norm(adoption_engine.W1))
            W2_norm_after = float(np.linalg.norm(adoption_engine.W2))
            
            delta_w1 = abs(W1_norm_after - W1_norm_before)
            delta_w2 = abs(W2_norm_after - W2_norm_before)
            
            learning_log += (
                f" | Adoption ML trained (y_true={observed_adoption}). "
                f"W1 delta norm={delta_w1:.6f}, W2 delta norm={delta_w2:.6f}"
            )
            calibration_action = "MLP calibrated online"
            
        return {
            "prediction_error_pct": round(percent_error, 1),
            "status": status,
            "calibration_recommendation": calibration_action,
            "learning_log": learning_log
        }

# Singleton
feedback_engine = FeedbackLoop()

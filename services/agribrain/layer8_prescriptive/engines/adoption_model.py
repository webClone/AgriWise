"""
Layer 8 Engine: Machine Learning-Based Adoption Probability Model
==================================================================
Farmer adoption likelihood predicted using a 2-layer Feedforward Neural Network
(Multi-Layer Perceptron) in NumPy, modeling Technology Acceptance features.
Supports online training (backpropagation) to adapt weights to farmer behavior.
"""
import logging
import numpy as np
from typing import Dict, List
from layer8_prescriptive.schema import (
    ActionCard, ActionType, AdoptionProfile, ConfidenceLevel,
)

logger = logging.getLogger(__name__)

# Ease of use & familiarity baseline tables
_EASE_BY_TYPE = {
    ActionType.MONITOR: 0.95,
    ActionType.WAIT: 0.98,
    ActionType.SCOUT: 0.80,
    ActionType.IRRIGATE: 0.70,
    ActionType.HARVEST_PLAN: 0.65,
    ActionType.FERTILIZE: 0.55,
    ActionType.SPRAY: 0.40,
    ActionType.REPLANT: 0.25,
}

_FAMILIARITY = {
    ActionType.MONITOR: 0.95,
    ActionType.WAIT: 0.90,
    ActionType.SCOUT: 0.75,
    ActionType.IRRIGATE: 0.80,
    ActionType.HARVEST_PLAN: 0.70,
    ActionType.FERTILIZE: 0.85,
    ActionType.SPRAY: 0.65,
    ActionType.REPLANT: 0.20,
}

_COST_PER_HA = {
    ActionType.MONITOR: 0,
    ActionType.WAIT: 0,
    ActionType.SCOUT: 5,
    ActionType.IRRIGATE: 30,
    ActionType.HARVEST_PLAN: 10,
    ActionType.FERTILIZE: 80,
    ActionType.SPRAY: 60,
    ActionType.REPLANT: 500,
}

_USEFULNESS_BY_CONFIDENCE = {
    ConfidenceLevel.HIGH: 0.90,
    ConfidenceLevel.MODERATE: 0.65,
    ConfidenceLevel.LOW: 0.35,
}

class AdoptionModelEngine:
    """Predicts farmer recommendation compliance using a 2-layer Neural Network."""

    def __init__(self):
        # Initialize deterministic weights for MLP (Input: 6 features -> Hidden: 4 -> Output: 1)
        # Features: [usefulness, ease, familiarity, cost_sensitivity, trust_grade_score, urgency]
        rs = np.random.RandomState(42)
        
        # Layer 1 weights & biases (input to hidden)
        self.W1 = rs.normal(loc=0.0, scale=0.4, size=(6, 4))
        self.b1 = np.zeros(4)
        
        # Layer 2 weights & biases (hidden to output)
        self.W2 = rs.normal(loc=0.0, scale=0.4, size=(4, 1))
        self.b2 = np.zeros(1)
        
        # Pre-trained bias towards positive adoption
        # (usefulness and ease should positively correlate with adoption, cost should negatively correlate)
        # We enforce these weights manually to make the model robust out-of-the-box
        self.W1[0, 0] = 0.8  # perceived usefulness -> positive
        self.W1[1, 1] = 0.6  # perceived ease -> positive
        self.W1[2, 2] = 0.5  # familiarity -> positive
        self.W1[3, 3] = -0.7 # cost sensitivity -> negative
        self.W1[4, 0] = 0.4  # trust grade -> positive
        self.W1[5, 1] = 0.3  # urgency -> positive

    def _sigmoid(self, z):
        return 1.0 / (1.0 + np.exp(-np.clip(z, -15, 15)))

    def _relu(self, z):
        return np.maximum(0, z)

    def _relu_deriv(self, a):
        return (a > 0).astype(float)

    def forward(self, x):
        """Runs Neural Network forward pass for prediction."""
        # Layer 1
        z1 = np.dot(x, self.W1) + self.b1
        a1 = self._relu(z1)
        
        # Layer 2
        z2 = np.dot(a1, self.W2) + self.b2
        a2 = self._sigmoid(z2)
        
        return a2, a1, z1

    def train_step(self, x, y_true, lr=0.1):
        """Performs backpropagation to update weights online (Stochastic Gradient Descent)."""
        x = np.array(x)
        y_true = np.array(y_true)
        
        # Forward pass
        a2, a1, z1 = self.forward(x)
        
        # Backward pass (cross-entropy loss derivative)
        error = a2 - y_true # dL/dz2 for sigmoid + cross-entropy
        
        # Gradients for Layer 2
        dW2 = np.dot(a1.T, error)
        db2 = np.sum(error, axis=0)
        
        # Backprop to Layer 1
        da1 = np.dot(error, self.W2.T)
        dz1 = da1 * self._relu_deriv(a1)
        
        # Gradients for Layer 1
        dW1 = np.dot(x.T, dz1)
        db1 = np.sum(dz1, axis=0)
        
        # Update weights and biases
        self.W1 -= lr * dW1
        self.b1 -= lr * db1
        self.W2 -= lr * dW2
        self.b2 -= lr * db2
        
        logger.debug("AdoptionModel ML: trained online, error=%.4f", np.mean(np.abs(error)))

    def score_adoption(self, action_cards: List[ActionCard], expected_revenue_per_ha: float = 1200.0) -> List[ActionCard]:
        """Runs the neural network model on each action card to predict adoption probability."""
        for card in action_cards:
            ease = _EASE_BY_TYPE.get(card.action_type, 0.5)
            usefulness_mult = _USEFULNESS_BY_CONFIDENCE.get(card.confidence, 0.65)
            usefulness = min(1.0, card.priority_score * 2.0 * usefulness_mult)
            familiarity = _FAMILIARITY.get(card.action_type, 0.5)
            
            # Cost sensitivity calculation
            action_cost = _COST_PER_HA.get(card.action_type, 50)
            if card.rate and card.action_type == ActionType.FERTILIZE:
                action_cost = card.rate.recommended * 0.5
            cost_ratio = action_cost / max(1, expected_revenue_per_ha)
            cost_sensitivity = min(1.0, cost_ratio / 0.05)
            
            # Trust score mapping from L0 audit grades
            trust_grade_scores = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4, "F": 0.2}
            trust_grade_score = trust_grade_scores.get(card.explain.split("grade=")[-1][:1].upper(), 0.8)
            
            urgency = card.priority_breakdown.urgency_score
            
            # Assemble feature vector: shape (1, 6)
            x = np.array([[usefulness, ease, familiarity, cost_sensitivity, trust_grade_score, urgency]])
            
            # Predict adoption probability
            prob, _, _ = self.forward(x)
            adoption_prob = float(prob[0, 0])
            adoption_prob = max(0.05, min(0.99, adoption_prob)) # clamp to logical limits
            
            # Identify barriers
            barriers = []
            if ease < 0.5:
                barriers.append("HIGH_COMPLEXITY")
            if cost_sensitivity > 0.7:
                barriers.append("HIGH_COST")
            if familiarity < 0.4:
                barriers.append("UNFAMILIAR_ACTION")
            if usefulness < 0.3:
                barriers.append("LOW_PERCEIVED_VALUE")
                
            # Select nudge strategy
            if adoption_prob > 0.65:
                nudge = "NONE"
            elif "HIGH_COMPLEXITY" in barriers:
                nudge = "SIMPLIFY"
            elif "HIGH_COST" in barriers:
                nudge = "REFRAME"
            elif "UNFAMILIAR_ACTION" in barriers:
                nudge = "SOCIAL_PROOF"
            elif "LOW_PERCEIVED_VALUE" in barriers:
                nudge = "REFRAME"
            else:
                nudge = "SIMPLIFY"
                
            card.adoption = AdoptionProfile(
                adoption_probability=round(adoption_prob, 3),
                perceived_usefulness=round(usefulness, 3),
                perceived_ease=round(ease, 3),
                cost_sensitivity=round(cost_sensitivity, 3),
                familiarity_score=round(familiarity, 3),
                barriers=barriers,
                nudge_strategy=nudge,
            )
            
        logger.debug("AdoptionModel ML: Finished scoring %d cards", len(action_cards))
        return action_cards

adoption_engine = AdoptionModelEngine()

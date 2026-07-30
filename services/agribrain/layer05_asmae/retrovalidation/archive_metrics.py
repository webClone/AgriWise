"""
Archive Metrics.
Evaluates prediction errors and R^2 score for retrovalidation holdout scenes.
"""
import numpy as np
from typing import List, Dict, Any

class ArchiveMetrics:
    def __init__(self):
        pass

    def compute_rmse(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

    def compute_mae(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean(np.abs(y_true - y_pred)))

    def compute_r2(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        if ss_tot < 1e-8:
            return 0.0
        return float(1.0 - (ss_res / ss_tot))

    def evaluate_predictions(
        self,
        y_true: List[float],
        y_pred: List[float]
    ) -> Dict[str, float]:
        """
        Computes standard regression performance metrics (RMSE, MAE, R2).
        """
        if not y_true or not y_pred:
            return {"rmse": 0.0, "mae": 0.0, "r2": 0.0}
            
        true_arr = np.array(y_true, dtype=np.float32)
        pred_arr = np.array(y_pred, dtype=np.float32)
        
        return {
            "rmse": self.compute_rmse(true_arr, pred_arr),
            "mae": self.compute_mae(true_arr, pred_arr),
            "r2": self.compute_r2(true_arr, pred_arr)
        }

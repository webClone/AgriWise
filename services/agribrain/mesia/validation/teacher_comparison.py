"""Teacher Comparison Pipeline for Phase 1.

Ingests TDR probe or gravimetric truth data alongside CSI data to compute real
R2, RMSE, and bias for scientific validation.
"""

import math
from typing import List, Dict, Any

class TeacherComparison:
    """Compares MESIA inferred values against a certified ground truth teacher."""

    def __init__(self, teacher_id: str):
        self.teacher_id = teacher_id
        self.inferred_values = []
        self.truth_values = []

    def ingest_data_pair(self, inferred_vwc: float, true_vwc: float) -> None:
        """Ingests a paired data point from a measurement epoch."""
        self.inferred_values.append(inferred_vwc)
        self.truth_values.append(true_vwc)

    def calculate_rmse(self) -> float:
        """Calculates Root Mean Square Error (RMSE)."""
        if not self.inferred_values:
            return float("inf")
        sq_errors = [(inf - tr) ** 2 for inf, tr in zip(self.inferred_values, self.truth_values)]
        return math.sqrt(sum(sq_errors) / len(sq_errors))

    def calculate_r_squared(self) -> float:
        """Calculates R-squared (Coefficient of Determination)."""
        if len(self.inferred_values) < 2:
            return 0.0
        
        mean_truth = sum(self.truth_values) / len(self.truth_values)
        ss_tot = sum((tr - mean_truth) ** 2 for tr in self.truth_values)
        ss_res = sum((tr - inf) ** 2 for tr, inf in zip(self.truth_values, self.inferred_values))
        
        if ss_tot == 0:
            return 0.0
        return max(0.0, 1.0 - (ss_res / ss_tot))

    def generate_comparison_report(self) -> Dict[str, Any]:
        """Generates the comprehensive teacher comparison report."""
        if not self.inferred_values:
            return {"status": "FAILED_NO_DATA"}
            
        return {
            "teacher_id": self.teacher_id,
            "sample_count": len(self.inferred_values),
            "rmse": self.calculate_rmse(),
            "r_squared": self.calculate_r_squared(),
            "status": "COMPLETED"
        }

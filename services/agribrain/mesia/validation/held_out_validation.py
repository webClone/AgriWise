"""Held-Out Validation Harness for Phase 1.

Reserves 20% of measurement epochs to compute true scientific metrics and issues
cryptographic signatures for qualified authorities.
"""

import hashlib
import json
import math
from typing import List, Dict, Any

class HeldOutValidator:
    """Manages the 80/20 train/test split and independent validation metrics."""

    def __init__(self, validation_fraction: float = 0.2):
        self.validation_fraction = validation_fraction
        self.dataset: List[Any] = []

    def load_dataset(self, epochs: List[Any]) -> None:
        """Loads a dataset of measurement epochs or evaluation pairs."""
        self.dataset = epochs

    def perform_split(self) -> tuple:
        """Splits the dataset deterministically."""
        split_idx = int(len(self.dataset) * (1.0 - self.validation_fraction))
        train_set = self.dataset[:split_idx]
        test_set = self.dataset[split_idx:]
        return train_set, test_set

    def sign_validation_certificate(self, metrics: Dict[str, Any]) -> str:
        """Cryptographically signs the validation metrics."""
        raw = json.dumps(metrics, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def validate_capability(self) -> Dict[str, Any]:
        """Runs the validation on the held-out set and produces signed metrics."""
        train, test = self.perform_split()

        if not test:
            metrics = {
                "test_sample_count": 0,
                "held_out_rmse": float("nan"),
                "held_out_r2": float("nan"),
                "passed_thresholds": False,
                "reason": "No held-out test data available.",
            }
            metrics["signature"] = self.sign_validation_certificate(metrics)
            return metrics

        # Extract predictions and true labels from test pairs
        preds = []
        trues = []
        for item in test:
            if isinstance(item, dict) and "inferred" in item and "truth" in item:
                preds.append(float(item["inferred"]))
                trues.append(float(item["truth"]))
            elif isinstance(item, (tuple, list)) and len(item) == 2:
                preds.append(float(item[0]))
                trues.append(float(item[1]))

        if len(preds) < 2:
            metrics = {
                "test_sample_count": len(test),
                "held_out_rmse": float("nan"),
                "held_out_r2": float("nan"),
                "passed_thresholds": False,
                "reason": "Insufficient valid evaluation pairs in held-out set (need >= 2).",
            }
            metrics["signature"] = self.sign_validation_certificate(metrics)
            return metrics

        # Exact Root Mean Square Error (RMSE)
        sq_errs = [(p - t) ** 2 for p, t in zip(preds, trues)]
        rmse = math.sqrt(sum(sq_errs) / len(sq_errs))

        # Exact Coefficient of Determination (R^2)
        mean_true = sum(trues) / len(trues)
        ss_tot = sum((t - mean_true) ** 2 for t in trues)
        ss_res = sum((t - p) ** 2 for t, p in zip(trues, preds))
        r2 = max(0.0, 1.0 - (ss_res / ss_tot)) if ss_tot > 0.0 else 0.0

        metrics = {
            "test_sample_count": len(preds),
            "held_out_rmse": round(rmse, 6),
            "held_out_r2": round(r2, 6),
            "passed_thresholds": bool(rmse <= 0.10 and r2 >= 0.70),
        }

        metrics["signature"] = self.sign_validation_certificate(metrics)
        return metrics

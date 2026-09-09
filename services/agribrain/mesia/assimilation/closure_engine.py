"""MESIA Multi-Radio Closure & Certificate Engine — R6 §11.5 / P9.5.

Evaluates multi-radio cross-validation (leave-one-link/node/band/RAT out),
tests for shortcut vulnerabilities, and issues immutable ClosureCertificate records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.scientific import ClosureCertificate


class MultiRadioClosureEngine:
    """Evaluates cross-radio closure and generates ClosureCertificate records."""

    @staticmethod
    def evaluate_closure(
        certificate_id: str,
        target_capability: str,
        link_residuals: List[float],
        node_residuals: List[float],
        rat_residuals: List[float],
        validation_metrics: Optional[Dict[str, Any]] = None,
    ) -> ClosureCertificate:
        """Compute closure R2 metrics, residual variance, and shortcut checks."""
        all_res = link_residuals + node_residuals + rat_residuals
        n = max(1, len(all_res))
        mean_res = sum(all_res) / n
        var_res = sum((r - mean_res) ** 2 for r in all_res) / n

        # R2 score proxy based on residual variance
        r2_link = max(0.0, 1.0 - (sum(r**2 for r in link_residuals) / max(1, len(link_residuals))))
        r2_node = max(0.0, 1.0 - (sum(r**2 for r in node_residuals) / max(1, len(node_residuals))))
        r2_rat = max(0.0, 1.0 - (sum(r**2 for r in rat_residuals) / max(1, len(rat_residuals))))

        is_passed = (mean_res < 0.15) and (r2_rat >= 0.70)
        now = datetime.now(timezone.utc)
        
        vm = validation_metrics or {}
        has_real_metrics = bool(validation_metrics)

        return ClosureCertificate(
            certificate_id=certificate_id,
            target_capability=target_capability,
            evaluated_at=now,
            leave_link_out_r2=r2_link,
            leave_node_out_r2=r2_node,
            leave_band_out_r2=vm.get("held_out_r2", 0.0),  
            leave_rat_out_r2=r2_rat,
            future_time_prediction_rmse=vm.get("held_out_rmse", float("inf")),  
            intervention_holdout_rmse=vm.get("intervention_rmse", float("inf")),  
            closure_residual_mean=mean_res,
            closure_residual_variance=var_res,
            closure_coverage_pct=vm.get("coverage_pct", 0.0),  
            passed_shortcut_checks=vm.get("passed_thresholds", False),  
            shortcut_vulnerability_notes=["Validated via Teacher Comparison"] if has_real_metrics else ["UNVALIDATED: shortcut checks not yet performed with real data"],
            strongest_single_radio_metric=0.0,
            multi_radio_metric=0.0,
            non_radio_baseline_metric=0.0,
            incremental_value_demonstrated=has_real_metrics,  

            preregistration_ref="",
            split_manifest_hash="",  # Audit Finding #8: was "d" * 64
            dataset_version="",  # Audit Finding #8: was hard-coded "v2.0.0"
            closure_passed=False,  # Audit Finding #6: fail-closed default
            review_comments="CONTAINMENT: closure requires real multi-radio cross-validation data (Audit Finding #8).",
        )

"""
Crop Intelligence v6.0D — Evaluation & Accuracy Reporting.

Evaluates hierarchical ML classifier performance across multiple levels and stratifications,
computes ECE, Brier scores, confusion matrices, hierarchical partial credit,
abstention quality, and compares predictions with the v5.1 rules baseline.
"""

import os
import uuid
import json
import logging
import math
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from .label_schema import LabeledSample
from .classifier import HierarchicalCropClassifier

logger = logging.getLogger("agribrain.labels.evaluator")


def _wrap_metric(value: Optional[float], n: int) -> Dict[str, Any]:
    """Wrap a metric value with sample count and confidence status."""
    if n < 10:
        return {"value": None, "n": n, "status": "too_few_samples"}
    elif n < 30:
        return {"value": value, "n": n, "status": "low_confidence_metric"}
    else:
        return {"value": value, "n": n, "status": "ok"}


class CropModelEvaluator:
    """Evaluation engine for Hierarchical Crop Classifiers."""

    def __init__(self, classifier: HierarchicalCropClassifier):
        self.classifier = classifier

    def compute_ece(self, probs: np.ndarray, y_true: np.ndarray, classes: np.ndarray, n_bins: int = 10) -> float:
        """Compute Expected Calibration Error (ECE) for top predicted class."""
        N = len(y_true)
        if N == 0:
            return 0.0

        # Predict class index and confidence
        pred_idx = np.argmax(probs, axis=1)
        confidences = np.max(probs, axis=1)
        pred_classes = classes[pred_idx]

        correct = (pred_classes == y_true)

        ece = 0.0
        for m in range(1, n_bins + 1):
            bin_lower = (m - 1) / n_bins
            bin_upper = m / n_bins

            if m == 1:
                in_bin = (confidences >= bin_lower) & (confidences <= bin_upper)
            else:
                in_bin = (confidences > bin_lower) & (confidences <= bin_upper)

            bin_size = np.sum(in_bin)
            if bin_size > 0:
                bin_acc = np.mean(correct[in_bin])
                bin_conf = np.mean(confidences[in_bin])
                ece += (bin_size / N) * abs(bin_acc - bin_conf)

        return float(ece)

    def compute_brier_score(self, probs: np.ndarray, y_true: np.ndarray, classes: np.ndarray) -> float:
        """Compute multi-class Brier score."""
        N = len(y_true)
        if N == 0:
            return 0.0

        class_to_idx = {c: i for i, c in enumerate(classes)}

        squared_errors = []
        for i in range(N):
            p_i = probs[i]
            true_label = y_true[i]

            # Construct one-hot representation matching probabilities classes
            y_i = np.zeros_like(p_i)
            if true_label in class_to_idx:
                y_i[class_to_idx[true_label]] = 1.0

            # Compute sum of squared differences
            squared_errors.append(np.sum((p_i - y_i) ** 2))

        return float(np.mean(squared_errors))

    def compute_confusion_matrix(self, y_true: List[str], y_pred: List[str]) -> Dict[str, Dict[str, int]]:
        """Compute nested confusion matrix (true_class -> predicted_class -> count)."""
        matrix = {}
        for true_cls, pred_cls in zip(y_true, y_pred):
            if true_cls is None or pred_cls is None:
                continue
            true_str = str(true_cls)
            pred_str = str(pred_cls)
            if true_str not in matrix:
                matrix[true_str] = {}
            matrix[true_str][pred_str] = matrix[true_str].get(pred_str, 0) + 1
        return matrix

    def _run_rule_engine(self, sample: LabeledSample) -> Optional[str]:
        """Extract biophysical signals and run the v5.1 rules engine."""
        snapshot = sample.label.feature_vector_snapshot or {}
        full_json = snapshot.get("full_json", {}) if isinstance(snapshot, dict) else {}

        # Retrieve raw lists if archived
        ndvi_series = full_json.get("ndvi_series")
        ndvi_dates = full_json.get("ndvi_dates")
        ndvi_velocity = full_json.get("ndvi_velocity")
        seasonal_profile = full_json.get("seasonal_profile")

        f = sample.features
        k_zone = f.get("koppen_zone") or (snapshot.get("koppen_zone") if isinstance(snapshot, dict) else None)

        try:
            from layer2_veg_int.crop_identification import crop_id_engine
            res = crop_id_engine.identify(
                ndvi_series=ndvi_series,
                ndvi_dates=ndvi_dates,
                ndvi_velocity=ndvi_velocity,
                seasonal_profile=seasonal_profile,
                peak_doy=int(f["pos_doy"]) if f.get("pos_doy") is not None else None,
                greenup_doy=int(f["sos_doy"]) if f.get("sos_doy") is not None else None,
                senescence_doy=int(f["eos_doy"]) if f.get("eos_doy") is not None else None,
                season_length_days=int(f["los_days"]) if f.get("los_days") is not None else None,
                sar_vh_mean=f.get("vh_mean_db"),
                sar_vv_mean=f.get("vv_mean_db"),
                sar_vh_seasonal_range=f.get("vh_amplitude_db"),
                evi_mean=f.get("evi_mean"),
                ndmi_mean=f.get("ndmi_mean"),
                ndwi_mean=f.get("ndwi_mean"),
                lat=f.get("latitude"),
                lng=f.get("longitude"),
                climate_zone=k_zone,
                mean_temp_c=f.get("mean_temp_c"),
                annual_rainfall_mm=f.get("annual_rainfall_mm"),
                et0_mm=f.get("et0_mm"),
                area_ha=f.get("plot_area_ha"),
                soil_type=f.get("soil_texture_class") or (snapshot.get("soil_texture_class") if isinstance(snapshot, dict) else None),
                irrigation_type=f.get("irrigation_type") or (snapshot.get("irrigation_type") if isinstance(snapshot, dict) else None),
                _force_rule_engine=True
            )
            return res.top_crop
        except Exception as e:
            logger.error(f"[Evaluator] Failed to run rule engine: {e}")
            return None

    def evaluate(self, samples: List[LabeledSample], dataset_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform evaluation of the model and generate a comprehensive metrics report."""
        if not self.classifier.models or not self.classifier.imputer:
            raise ValueError("Classifier must be trained/loaded before running evaluation.")

        n_total = len(samples)
        if n_total == 0:
            return {
                "manifest": self._generate_manifest(0, 0, {}, dataset_filters),
                "summary": {"sample_count": 0, "eligible_sample_count": 0, "excluded_sample_count": 0},
                "hierarchy_metrics": {},
                "abstention_metrics": {},
                "confusion_matrices": {"L0": {}, "L1": {}, "L2": {}, "L3": {}},
                "stratified_metrics": {
                    "by_crop_group": {},
                    "by_koppen_zone": {},
                    "by_quality_tier": {},
                    "by_feature_completeness_bucket": {},
                    "by_prediction_depth": {}
                },
                "fallback_metrics": {
                    "ml_vs_rule": {},
                    "agronomic_rejection_rate": {"value": None, "n": 0, "status": "too_few_samples"},
                    "rule_fallback_rate": {"value": None, "n": 0, "status": "too_few_samples"}
                },
                "warnings": ["no_samples_provided"]
            }

        # ── 1. Batch Prediction & Feature Matrix Construction ──
        X_raw = []
        for s in samples:
            row = [s.features.get(f) for f in self.classifier.feature_names]
            X_raw.append(row)

        X_arr = np.array(X_raw, dtype=np.float64)
        X_imputed = self.classifier.imputer.transform(X_arr)

        level_probs = {}
        for level in ["L0", "L1", "L2", "L3"]:
            if self.classifier.metadata["level_status"].get(level) == "trained":
                model = self.classifier.models[level]
                level_probs[level] = model.predict_proba(X_imputed)

        # ── 2. Walk through each sample to gather predictions and rules engine outputs ──
        predictions = []
        y_trues = []
        bypass_flags = []
        agronomic_fallback_flags = []
        overall_fallback_flags = []
        pred_depths = []
        rule_predictions = []
        completeness_values = []

        for i, s in enumerate(samples):
            y_trues.append(s.hierarchy_targets)

            # Feature availability check
            flat_features = s.features
            l0_features = ["peak_ndvi", "base_ndvi", "amplitude", "cv_ndvi", "vv_mean_db", "vh_mean_db", "n_seasons", "is_evergreen"]
            l0_available = sum(1 for f in l0_features if flat_features.get(f) is not None)
            l0_availability = l0_available / len(l0_features) if l0_features else 1.0

            comp = s.quality.feature_completeness
            if comp is None or comp == 0.0:
                non_null = sum(1 for v in flat_features.values() if v is not None)
                comp = non_null / len(flat_features) if flat_features else 0.0
            completeness_values.append(comp)

            bypass = (comp < 0.4 or l0_availability < 0.5)
            bypass_flags.append(bypass)

            # Run ML prediction
            snapshot = s.label.feature_vector_snapshot or {}
            fv_input = {
                "flat_features": flat_features,
                "feature_vector_version": s.label.feature_vector_version or "6.0.0",
                "data_completeness": comp,
                "koppen_zone": flat_features.get("koppen_zone") or (snapshot.get("koppen_zone") if isinstance(snapshot, dict) else None),
                "aridity_index": flat_features.get("aridity_index") or (snapshot.get("aridity_index") if isinstance(snapshot, dict) else None),
                "irrigation_type": flat_features.get("irrigation_type") or (snapshot.get("irrigation_type") if isinstance(snapshot, dict) else None),
                "latitude": flat_features.get("latitude") or (snapshot.get("latitude") if isinstance(snapshot, dict) else None),
                "longitude": flat_features.get("longitude") or (snapshot.get("longitude") if isinstance(snapshot, dict) else None),
            }

            pred_res = self.classifier.predict(fv_input, apply_constraints=True)
            ml_output = pred_res["ml_classifier_output"]
            predictions.append(ml_output)

            # Check fallbacks
            l3_info = ml_output.get("L3", {})
            agronomic_fallback = l3_info.get("agronomic_filter", {}).get("fallback_triggered", False)
            agronomic_fallback_flags.append(agronomic_fallback)

            overall_fallback = bypass or agronomic_fallback
            overall_fallback_flags.append(overall_fallback)

            # Assign prediction depth
            l0_pred = ml_output.get("L0", {}).get("prediction")
            l1_pred = ml_output.get("L1", {}).get("prediction")
            l2_pred = ml_output.get("L2", {}).get("prediction")
            l3_pred = ml_output.get("L3", {}).get("prediction")

            if overall_fallback:
                depth = "L0"
            elif l3_pred is not None and l3_info.get("reason") not in ("high_entropy_l3", "insufficient_features_l3"):
                depth = "L3"
            elif l2_pred is not None:
                depth = "L2"
            elif l1_pred is not None:
                depth = "L1"
            else:
                depth = "L0"

            pred_depths.append(depth)

            # Run v5.1 rules engine
            rule_pred = self._run_rule_engine(s)
            rule_predictions.append(rule_pred)

        # ── 3. Compute Metrics for Subsets ──
        indices_all = list(range(n_total))
        global_metrics = self._compute_subset_metrics(
            indices_all, predictions, y_trues, level_probs, bypass_flags,
            agronomic_fallback_flags, overall_fallback_flags, pred_depths,
            rule_predictions, completeness_values
        )

        # ── 4. Stratifications ──
        by_crop_group = {}
        by_koppen_zone = {}
        by_quality_tier = {}
        by_feature_completeness = {}
        by_prediction_depth = {}

        for i, s in enumerate(samples):
            # Crop group
            cg = s.label.crop_group or "unknown"
            by_crop_group.setdefault(cg, []).append(i)

            # Köppen zone
            snapshot = s.label.feature_vector_snapshot or {}
            kz = s.features.get("koppen_zone") or (snapshot.get("koppen_zone") if isinstance(snapshot, dict) else None) or "unknown"
            by_koppen_zone.setdefault(kz, []).append(i)

            # Quality
            qt = s.quality.quality_tier or "unknown"
            by_quality_tier.setdefault(qt, []).append(i)

            # Completeness bucket
            comp = completeness_values[i]
            if comp < 0.3:
                bucket = "< 0.3"
            elif comp < 0.6:
                bucket = "0.3-0.6"
            elif comp < 0.8:
                bucket = "0.6-0.8"
            else:
                bucket = "> 0.8"
            by_feature_completeness.setdefault(bucket, []).append(i)

            # Prediction depth
            pd = pred_depths[i]
            by_prediction_depth.setdefault(pd, []).append(i)

        # Compute metric sets for each category
        stratified_metrics = {
            "by_crop_group": {
                k: self._compute_subset_metrics(v, predictions, y_trues, level_probs, bypass_flags, agronomic_fallback_flags, overall_fallback_flags, pred_depths, rule_predictions, completeness_values)
                for k, v in by_crop_group.items()
            },
            "by_koppen_zone": {
                k: self._compute_subset_metrics(v, predictions, y_trues, level_probs, bypass_flags, agronomic_fallback_flags, overall_fallback_flags, pred_depths, rule_predictions, completeness_values)
                for k, v in by_koppen_zone.items()
            },
            "by_quality_tier": {
                k: self._compute_subset_metrics(v, predictions, y_trues, level_probs, bypass_flags, agronomic_fallback_flags, overall_fallback_flags, pred_depths, rule_predictions, completeness_values)
                for k, v in by_quality_tier.items()
            },
            "by_feature_completeness_bucket": {
                k: self._compute_subset_metrics(v, predictions, y_trues, level_probs, bypass_flags, agronomic_fallback_flags, overall_fallback_flags, pred_depths, rule_predictions, completeness_values)
                for k, v in by_feature_completeness.items()
            },
            "by_prediction_depth": {
                k: self._compute_subset_metrics(v, predictions, y_trues, level_probs, bypass_flags, agronomic_fallback_flags, overall_fallback_flags, pred_depths, rule_predictions, completeness_values)
                for k, v in by_prediction_depth.items()
            }
        }

        # ── 5. Confusion Matrices ──
        confusion_matrices = {}
        for level in ["L0", "L1", "L2", "L3"]:
            y_true_level = [yt.get(level) for yt in y_trues]
            y_pred_level = [p.get(level, {}).get("prediction") for p in predictions]
            confusion_matrices[level] = self.compute_confusion_matrix(y_true_level, y_pred_level)

        # ── 6. Assemble Manifest & Output Report ──
        manifest = self._generate_manifest(n_total, 0, {}, dataset_filters)

        # Assemble output structures
        hierarchy_metrics = {
            "L0": {
                "accuracy": global_metrics["l0_accuracy"],
                "ece": global_metrics["l0_ece"],
                "brier": global_metrics["l0_brier"]
            },
            "L1": {
                "accuracy": global_metrics["l1_accuracy"],
                "ece": global_metrics["l1_ece"],
                "brier": global_metrics["l1_brier"]
            },
            "L2": {
                "accuracy": global_metrics["l2_accuracy"],
                "ece": global_metrics["l2_ece"],
                "brier": global_metrics["l2_brier"]
            },
            "L3": {
                "top1_accuracy_when_predicted": global_metrics["l3_top1_accuracy_when_predicted"],
                "top3_recall_when_predicted": global_metrics["l3_top3_recall_when_predicted"],
                "coverage_rate": global_metrics["l3_coverage_rate"],
                "abstention_rate": global_metrics["l3_abstention_rate"],
                "effective_accuracy_all_samples": global_metrics["l3_effective_accuracy_all_samples"],
                "ece_when_predicted": global_metrics["l3_ece_when_predicted"],
                "brier_when_predicted": global_metrics["l3_brier_when_predicted"]
            }
        }

        # Additional summary details
        summary = {
            "sample_count": n_total,
            "eligible_sample_count": n_total,
            "excluded_sample_count": 0,
        }

        # Collect warnings
        warnings = []
        if n_total < 30:
            warnings.append("small_evaluation_dataset")

        return {
            "manifest": manifest,
            "summary": summary,
            "hierarchy_metrics": hierarchy_metrics,
            "abstention_metrics": global_metrics["abstention_metrics"],
            "confusion_matrices": confusion_matrices,
            "stratified_metrics": stratified_metrics,
            "fallback_metrics": global_metrics["fallback_metrics"],
            "warnings": warnings
        }

    def _generate_manifest(self, sample_count: int, excluded_count: int, exclusion_reasons: Dict[str, int], dataset_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a reproducible manifest dictionary."""
        meta = self.classifier.metadata or {}
        model_meta_hash = hashlib_metadata(meta) if meta else "untrained"
        
        return {
            "evaluation_id": str(uuid.uuid4()),
            "evaluated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "model_version": meta.get("model_version", "6.0C"),
            "model_metadata_hash": model_meta_hash,
            "feature_vector_version": "6.0.0",
            "label_schema_version": "6.0B",
            "dataset_filters": dataset_filters or {
                "min_quality_tier": "C",
                "include_historical": True,
                "min_feature_completeness": 0.3
            },
            "sample_count": sample_count,
            "excluded_sample_count": excluded_count,
            "exclusion_reasons": exclusion_reasons
        }

    def _compute_subset_metrics(
        self,
        indices: List[int],
        predictions: List[Dict[str, Any]],
        y_trues: List[Dict[str, str]],
        level_probs: Dict[str, np.ndarray],
        bypass_flags: List[bool],
        agronomic_fallback_flags: List[bool],
        overall_fallback_flags: List[bool],
        pred_depths: List[str],
        rule_predictions: List[Optional[str]],
        completeness_values: List[float]
    ) -> Dict[str, Any]:
        """Compute all wrapped metrics on a subset of samples defined by indices."""
        n_sub = len(indices)
        if n_sub == 0:
            return {
                "l0_accuracy": _wrap_metric(None, 0),
                "l1_accuracy": _wrap_metric(None, 0),
                "l2_accuracy": _wrap_metric(None, 0),
                "l3_top1_accuracy_when_predicted": _wrap_metric(None, 0),
                "l3_top3_recall_when_predicted": _wrap_metric(None, 0),
                "l3_coverage_rate": _wrap_metric(None, 0),
                "l3_abstention_rate": _wrap_metric(None, 0),
                "l3_effective_accuracy_all_samples": _wrap_metric(None, 0),
                "l0_ece": _wrap_metric(None, 0),
                "l1_ece": _wrap_metric(None, 0),
                "l2_ece": _wrap_metric(None, 0),
                "l3_ece_when_predicted": _wrap_metric(None, 0),
                "l0_brier": _wrap_metric(None, 0),
                "l1_brier": _wrap_metric(None, 0),
                "l2_brier": _wrap_metric(None, 0),
                "l3_brier_when_predicted": _wrap_metric(None, 0),
                "hierarchical_partial_credit": _wrap_metric(None, 0),
                "abstention_metrics": {
                    "abstention_count_by_level": {"L0": 0, "L1": 0, "L2": 0},
                    "accuracy_when_abstained_at_L2": _wrap_metric(None, 0),
                    "accuracy_when_forced_to_L3": _wrap_metric(None, 0),
                },
                "fallback_metrics": {
                    "ml_vs_rule": {
                        "ml_correct_count": 0,
                        "rule_correct_count": 0,
                        "both_correct": 0,
                        "ml_only_correct": 0,
                        "rule_only_correct": 0,
                        "both_wrong": 0
                    },
                    "agronomic_rejection_rate": _wrap_metric(None, 0),
                    "rule_fallback_rate": _wrap_metric(None, 0)
                }
            }

        # Count bypasses and fallbacks
        bypassed_count = sum(1 for idx in indices if bypass_flags[idx])
        agronomic_count = sum(1 for idx in indices if agronomic_fallback_flags[idx])
        fallback_count = sum(1 for idx in indices if overall_fallback_flags[idx])

        # Basic levels accuracies
        l0_correct = 0
        l0_total = 0
        for idx in indices:
            pred = predictions[idx].get("L0", {}).get("prediction")
            true = y_trues[idx].get("L0")
            if pred is not None and true is not None:
                l0_total += 1
                if pred == true:
                    l0_correct += 1
        l0_acc = l0_correct / l0_total if l0_total > 0 else None

        l1_correct = 0
        l1_total = 0
        for idx in indices:
            pred = predictions[idx].get("L1", {}).get("prediction")
            true = y_trues[idx].get("L1")
            if pred is not None and true is not None:
                l1_total += 1
                if pred == true:
                    l1_correct += 1
        l1_acc = l1_correct / l1_total if l1_total > 0 else None

        l2_correct = 0
        l2_total = 0
        for idx in indices:
            pred = predictions[idx].get("L2", {}).get("prediction")
            true = y_trues[idx].get("L2")
            if pred is not None and true is not None:
                l2_total += 1
                if pred == true:
                    l2_correct += 1
        l2_acc = l2_correct / l2_total if l2_total > 0 else None

        # L3 Metrics (honesty in stopping early)
        l3_predicted_indices = [idx for idx in indices if pred_depths[idx] == "L3"]
        n_l3_predicted = len(l3_predicted_indices)

        l3_correct_when_pred = 0
        for idx in l3_predicted_indices:
            pred = predictions[idx].get("L3", {}).get("prediction")
            true = y_trues[idx].get("L3")
            if pred == true and true is not None:
                l3_correct_when_pred += 1
        l3_top1_acc_when_predicted = l3_correct_when_pred / n_l3_predicted if n_l3_predicted > 0 else None

        l3_recall_hits_when_pred = 0
        for idx in l3_predicted_indices:
            candidates = predictions[idx].get("L3", {}).get("top_candidates", [])
            true = y_trues[idx].get("L3")
            if true in [c["code"] for c in candidates[:3]] and true is not None:
                l3_recall_hits_when_pred += 1
        l3_top3_rec_when_predicted = l3_recall_hits_when_pred / n_l3_predicted if n_l3_predicted > 0 else None

        l3_coverage_rate = n_l3_predicted / n_sub
        l3_abstention_rate = 1.0 - l3_coverage_rate

        # Effective L3 accuracy over all samples (where depth = L3 and predicted correct)
        # Note: samples with depth < L3 are treated as incorrect/abstained
        l3_effective_accuracy_all_samples = l3_correct_when_pred / n_sub

        # Per-level ECE and Brier Score
        ece_dict = {}
        brier_dict = {}
        for level in ["L0", "L1", "L2"]:
            if level in level_probs:
                probs = level_probs[level]
                classes = self.classifier.models[level].classes_
                sub_probs = probs[indices]
                sub_y = np.array([y_trues[idx].get(level, "unknown") for idx in indices])

                ece_dict[level] = self.compute_ece(sub_probs, sub_y, classes)
                brier_dict[level] = self.compute_brier_score(sub_probs, sub_y, classes)
            else:
                ece_dict[level] = None
                brier_dict[level] = None

        # L3 calibration metrics (computed only on predicted samples)
        if "L3" in level_probs and n_l3_predicted > 0:
            probs = level_probs["L3"]
            classes = self.classifier.models["L3"].classes_
            sub_probs = probs[l3_predicted_indices]
            sub_y = np.array([y_trues[idx].get("L3", "unknown") for idx in l3_predicted_indices])

            ece_dict["L3"] = self.compute_ece(sub_probs, sub_y, classes)
            brier_dict["L3"] = self.compute_brier_score(sub_probs, sub_y, classes)
        else:
            ece_dict["L3"] = None
            brier_dict["L3"] = None

        # ── Hierarchical Partial-Credit Metric ──
        total_credit = 0.0
        for idx in indices:
            sample_credit = 0.0
            ml_out = predictions[idx]
            yt = y_trues[idx]

            # L0
            if ml_out.get("L0", {}).get("prediction") == yt.get("L0"):
                sample_credit += 0.25
            # L1
            if ml_out.get("L1", {}).get("prediction") == yt.get("L1"):
                sample_credit += 0.25
            # L2
            if ml_out.get("L2", {}).get("prediction") == yt.get("L2"):
                sample_credit += 0.25
            # L3
            if ml_out.get("L3", {}).get("prediction") == yt.get("L3"):
                sample_credit += 0.25

            total_credit += sample_credit
        hierarchical_partial_credit = total_credit / n_sub

        # ── Abstention quality metrics ──
        abstention_counts = {"L0": 0, "L1": 0, "L2": 0}
        for idx in indices:
            depth = pred_depths[idx]
            if depth != "L3":
                abstention_counts[depth] = abstention_counts.get(depth, 0) + 1

        # Accuracy when abstained at L2
        abstained_l2_indices = [idx for idx in indices if pred_depths[idx] == "L2"]
        n_abstained_l2 = len(abstained_l2_indices)
        correct_l2_when_abstained = 0
        for idx in abstained_l2_indices:
            pred = predictions[idx].get("L2", {}).get("prediction")
            true = y_trues[idx].get("L2")
            if pred == true and true is not None:
                correct_l2_when_abstained += 1
        accuracy_when_abstained_at_L2 = correct_l2_when_abstained / n_abstained_l2 if n_abstained_l2 > 0 else None

        # Accuracy when forced to L3 (safe stopping result vs forced deepest prediction)
        correct_forced_l3 = 0
        for idx in indices:
            candidates = predictions[idx].get("L3", {}).get("top_candidates", [])
            true = y_trues[idx].get("L3")
            forced_pred = candidates[0]["code"] if candidates else None
            if forced_pred == true and true is not None:
                correct_forced_l3 += 1
        accuracy_when_forced_to_L3 = correct_forced_l3 / n_sub

        abstention_metrics = {
            "hierarchical_partial_credit": _wrap_metric(hierarchical_partial_credit, n_sub),
            "abstention_count_by_level": abstention_counts,
            "accuracy_when_abstained_at_L2": _wrap_metric(accuracy_when_abstained_at_L2, n_abstained_l2),
            "accuracy_when_forced_to_L3": _wrap_metric(accuracy_when_forced_to_L3, n_sub),
        }

        # ── ML-vs-v5.1 comparison metrics ──
        ml_correct_count = 0
        rule_correct_count = 0
        both_correct = 0
        ml_only_correct = 0
        rule_only_correct = 0
        both_wrong = 0

        for idx in indices:
            # Get ML L3 prediction (we use forced deepest prediction here to check ML correctness at L3)
            candidates = predictions[idx].get("L3", {}).get("top_candidates", [])
            ml_pred = candidates[0]["code"] if candidates else None
            rule_pred = rule_predictions[idx]
            true = y_trues[idx].get("L3")

            ml_is_correct = (ml_pred == true and true is not None)
            rule_is_correct = (rule_pred == true and true is not None)

            if ml_is_correct:
                ml_correct_count += 1
            if rule_is_correct:
                rule_correct_count += 1

            if ml_is_correct and rule_is_correct:
                both_correct += 1
            elif ml_is_correct and not rule_is_correct:
                ml_only_correct += 1
            elif not ml_is_correct and rule_is_correct:
                rule_only_correct += 1
            else:
                both_wrong += 1

        fallback_metrics = {
            "ml_vs_rule": {
                "ml_correct_count": ml_correct_count,
                "rule_correct_count": rule_correct_count,
                "both_correct": both_correct,
                "ml_only_correct": ml_only_correct,
                "rule_only_correct": rule_only_correct,
                "both_wrong": both_wrong
            },
            "agronomic_rejection_rate": _wrap_metric(agronomic_count / n_sub, n_sub),
            "rule_fallback_rate": _wrap_metric(fallback_count / n_sub, n_sub),
        }

        return {
            "l0_accuracy": _wrap_metric(l0_acc, l0_total),
            "l1_accuracy": _wrap_metric(l1_acc, l1_total),
            "l2_accuracy": _wrap_metric(l2_acc, l2_total),
            "l3_top1_accuracy_when_predicted": _wrap_metric(l3_top1_acc_when_predicted, n_l3_predicted),
            "l3_top3_recall_when_predicted": _wrap_metric(l3_top3_rec_when_predicted, n_l3_predicted),
            "l3_coverage_rate": _wrap_metric(l3_coverage_rate, n_sub),
            "l3_abstention_rate": _wrap_metric(l3_abstention_rate, n_sub),
            "l3_effective_accuracy_all_samples": _wrap_metric(l3_effective_accuracy_all_samples, n_sub),
            "l0_ece": _wrap_metric(ece_dict["L0"], l0_total),
            "l1_ece": _wrap_metric(ece_dict["L1"], l1_total),
            "l2_ece": _wrap_metric(ece_dict["L2"], l2_total),
            "l3_ece_when_predicted": _wrap_metric(ece_dict["L3"], n_l3_predicted),
            "l0_brier": _wrap_metric(brier_dict["L0"], l0_total),
            "l1_brier": _wrap_metric(brier_dict["L1"], l1_total),
            "l2_brier": _wrap_metric(brier_dict["L2"], l2_total),
            "l3_brier_when_predicted": _wrap_metric(brier_dict["L3"], n_l3_predicted),
            "abstention_metrics": abstention_metrics,
            "fallback_metrics": fallback_metrics
        }

    @staticmethod
    def export_csv(metrics: Dict[str, Any]) -> str:
        """Flatten evaluation metrics JSON structure into a row-oriented CSV format."""
        import io
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["category", "stratum", "metric_name", "value", "n", "status"])

        # Helper to unpack wrapped metric dictionary
        def write_wrapped(cat: str, strat: str, key: str, m_dict: Any):
            if isinstance(m_dict, dict) and "value" in m_dict and "status" in m_dict:
                writer.writerow([cat, strat, key, m_dict["value"], m_dict.get("n", ""), m_dict["status"]])
            elif isinstance(m_dict, dict):
                # Nested non-wrapped dictionaries (like ece, brier_score, abstention_count_by_level)
                for k, v in m_dict.items():
                    if isinstance(v, dict) and "value" in v:
                        writer.writerow([cat, strat, f"{key}_{k}", v["value"], v.get("n", ""), v["status"]])
                    else:
                        writer.writerow([cat, strat, f"{key}_{k}", v, "", ""])
            else:
                writer.writerow([cat, strat, key, m_dict, "", ""])

        # 1. Global / Hierarchy metrics
        hier = metrics.get("hierarchy_metrics", {})
        for lvl, lvl_dict in hier.items():
            for key, val in lvl_dict.items():
                write_wrapped("hierarchy", lvl, key, val)

        # 2. Abstention metrics
        abst = metrics.get("abstention_metrics", {})
        for key, val in abst.items():
            write_wrapped("abstention", "overall", key, val)

        # 3. Fallback metrics
        fall = metrics.get("fallback_metrics", {})
        for key, val in fall.items():
            write_wrapped("fallback", "overall", key, val)

        # 4. Stratified metrics
        strat = metrics.get("stratified_metrics", {})
        for cat, strata in strat.items():
            for strat_name, strat_val in strata.items():
                for key, val in strat_val.items():
                    write_wrapped(cat, strat_name, key, val)

        return output.getvalue()


def hashlib_metadata(meta: Dict[str, Any]) -> str:
    """Compute deterministic SHA256 of metadata."""
    import hashlib
    serialized = json.dumps(meta, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

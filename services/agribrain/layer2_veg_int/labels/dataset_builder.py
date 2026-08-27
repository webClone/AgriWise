"""
Crop Intelligence v6.0B — Training Dataset Builder.

Builds ML-ready datasets from authority-validated crop labels.
Consumed by v6.0C hierarchical classifier.

Outputs:
  - List[LabeledSample] for in-memory training
  - CSV export for offline analysis
  - Summary statistics for dataset quality reporting

Historical records and ordinary farmer confirmations are not production
ground truth.  This builder fails closed unless every sample carries trusted
source authority, immutable evidence lineage, and leakage-control partitions.
"""

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .label_schema import (
    CropLabel,
    LabeledSample,
    LabelQualityScore,
    DatasetSummary,
    TRAINING_ELIGIBLE_LABEL_SOURCES,
    get_hierarchy_targets,
)
from .label_store import LabelStoreBase
from .label_quality import compute_label_quality
from services.agribrain.app.crop_training_snapshot_authority import (
    assess_crop_training_snapshot,
)

logger = logging.getLogger("agribrain.labels.dataset")

# Minimum quality tier thresholds
_TIER_THRESHOLD: Dict[str, float] = {
    "A": 0.8,
    "B": 0.6,
    "C": 0.4,
    "D": 0.0,
}


class TrainingDatasetBuilder:
    """Build ML-ready datasets from confirmed crop labels.

    Consumed by v6.0C hierarchical classifier.
    """

    def __init__(self, store: LabelStoreBase):
        self.store = store

    def build_dataset(
        self,
        min_quality_tier: str = "C",
        target_level: str = "L2",
        crop_groups: Optional[List[str]] = None,
        include_historical: bool = False,
        balance_classes: bool = False,
        max_samples_per_class: Optional[int] = None,
        require_feature_vector: bool = True,
        min_feature_completeness: float = 0.3,
        include_synthetic: bool = False,
    ) -> DatasetSummary:
        """Build a training dataset from stored labels.

        Args:
            min_quality_tier: Minimum quality tier (A/B/C/D)
            target_level: Which hierarchy level to train (L0/L1/L2/L3)
            crop_groups: Filter to specific crop groups (optional)
            include_historical: Inspect historical_record labels (default
                False). Historical records remain ineligible for production
                training even when inspected.
            balance_classes: Downsample to balance class distribution
            max_samples_per_class: Cap per class if balance_classes=True
            require_feature_vector: Exclude labels without feature vectors (default True)
            min_feature_completeness: Minimum completeness threshold (default 0.3)
            include_synthetic: Include synthetic_seeded labels (default False)

        Returns:
            DatasetSummary with samples, distributions, and warnings.
        """
        min_score = _TIER_THRESHOLD.get(min_quality_tier, 0.4)
        warnings = []
        if target_level not in {"L0", "L1", "L2", "L3"}:
            raise ValueError("target_level must be one of L0, L1, L2, L3")

        # Fetch the scoped label inventory and apply authority rules here so
        # exclusions are visible in the dataset receipt.  Store-side source
        # filtering would make unsafe labels disappear without an audit count.
        all_labels = self.store.get_all_labels(
            active_only=True,
            crop_groups=crop_groups,
            label_sources=None,
        )

        if not include_synthetic:
            all_labels = [l for l in all_labels if not getattr(l, "synthetic", False)]

        if not all_labels:
            return DatasetSummary(
                samples=[],
                class_distribution={},
                quality_distribution={"A": 0, "B": 0, "C": 0, "D": 0},
                feature_completeness_stats={"mean": 0, "std": 0, "min": 0, "max": 0},
                target_level=target_level,
                total_samples=0,
                warnings=["no_labels_found"],
                included_samples=0,
                excluded_samples=0,
                exclusion_reasons={
                    "historical_record_excluded": 0,
                    "untrusted_label_source": 0,
                    "authority_not_validated": 0,
                    "label_confidence_not_high": 0,
                    "missing_geometry": 0,
                    "missing_run_lineage": 0,
                    "missing_partition_metadata": 0,
                    "below_quality_threshold": 0,
                    "missing_feature_vector": 0,
                    "invalid_crop_model_input_receipt": 0,
                    "low_feature_completeness": 0,
                    "target_level_not_labeled": 0,
                },
            )

        # Score and filter
        samples: List[LabeledSample] = []
        quality_dist: Dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}
        completeness_values: List[float] = []

        included_samples = 0
        excluded_samples = 0
        exclusion_reasons = {
            "historical_record_excluded": 0,
            "untrusted_label_source": 0,
            "authority_not_validated": 0,
            "label_confidence_not_high": 0,
            "missing_geometry": 0,
            "missing_run_lineage": 0,
            "missing_partition_metadata": 0,
            "below_quality_threshold": 0,
            "missing_feature_vector": 0,
            "invalid_crop_model_input_receipt": 0,
            "low_feature_completeness": 0,
            "target_level_not_labeled": 0,
        }

        for label in all_labels:
            if target_level not in set(label.supported_hierarchy_levels):
                exclusion_reasons["target_level_not_labeled"] += 1
                excluded_samples += 1
                continue
            if label.label_source == "historical_record" and not include_historical:
                exclusion_reasons["historical_record_excluded"] += 1
                excluded_samples += 1
                continue

            if label.label_source not in TRAINING_ELIGIBLE_LABEL_SOURCES:
                exclusion_reasons["untrusted_label_source"] += 1
                excluded_samples += 1
                continue

            if not getattr(label, "authority_validated", False):
                exclusion_reasons["authority_not_validated"] += 1
                excluded_samples += 1
                continue

            if label.label_confidence != "HIGH":
                exclusion_reasons["label_confidence_not_high"] += 1
                excluded_samples += 1
                continue

            if not label.geometry_hash or label.geometry_hash == "NO_GEOMETRY":
                exclusion_reasons["missing_geometry"] += 1
                excluded_samples += 1
                continue

            if not label.layer1_run_id:
                exclusion_reasons["missing_run_lineage"] += 1
                excluded_samples += 1
                continue

            partition_values = (
                getattr(label, "tenant_id", None),
                getattr(label, "farm_id", None),
                getattr(label, "crop_cycle_id", None),
                getattr(label, "region_partition", None),
                getattr(label, "season_partition", None),
                getattr(label, "sensor_regime", None),
            )
            if any(not value for value in partition_values):
                exclusion_reasons["missing_partition_metadata"] += 1
                excluded_samples += 1
                continue

            quality = compute_label_quality(label)
            quality_dist[quality.quality_tier] = quality_dist.get(quality.quality_tier, 0) + 1

            if quality.overall_quality < min_score:
                exclusion_reasons["below_quality_threshold"] += 1
                excluded_samples += 1
                continue

            snapshot = label.feature_vector_snapshot
            if require_feature_vector and not snapshot:
                exclusion_reasons["missing_feature_vector"] += 1
                excluded_samples += 1
                continue

            training_input = assess_crop_training_snapshot(
                feature_vector_snapshot=snapshot,
                crop_model_input_receipt=getattr(
                    label, "crop_model_input_receipt", None
                ),
                tenant_id=getattr(label, "tenant_id", None),
                farm_id=getattr(label, "farm_id", None),
                plot_id=label.plot_id,
                crop_cycle_id=getattr(label, "crop_cycle_id", None),
                expected_receipt_hash=getattr(
                    label, "crop_model_input_receipt_hash", None
                ),
            )
            if not training_input.eligible:
                exclusion_reasons["invalid_crop_model_input_receipt"] += 1
                excluded_samples += 1
                continue

            # Extract features from snapshot, resolving nested "flat_features" if present
            features = {}
            if snapshot:
                if isinstance(snapshot, dict) and "flat_features" in snapshot:
                    features = snapshot["flat_features"]
                else:
                    features = snapshot

            completeness = quality.feature_completeness
            # Fallback if quality.feature_completeness is None/0 but we have features
            if (completeness is None or completeness == 0.0) and features:
                non_null = sum(1 for v in features.values() if v is not None)
                completeness = non_null / len(features) if features else 0.0

            if require_feature_vector and completeness < min_feature_completeness:
                exclusion_reasons["low_feature_completeness"] += 1
                excluded_samples += 1
                continue

            full_hierarchy = get_hierarchy_targets(
                label.crop_code, label.crop_group,
            )
            hierarchy = {
                level: value for level, value in full_hierarchy.items()
                if level in set(label.supported_hierarchy_levels)
            }

            sample = LabeledSample(
                label=label,
                features=features,
                quality=quality,
                hierarchy_targets=hierarchy,
            )
            samples.append(sample)
            included_samples += 1
            completeness_values.append(completeness)

        # Class distribution
        class_dist: Dict[str, int] = {}
        for s in samples:
            target = s.hierarchy_targets[target_level]
            class_dist[target] = class_dist.get(target, 0) + 1

        # Balance classes if requested
        if balance_classes and samples:
            samples = self._balance_classes(
                samples, target_level, max_samples_per_class
            )
            # Recompute after balancing
            class_dist = {}
            for s in samples:
                target = s.hierarchy_targets[target_level]
                class_dist[target] = class_dist.get(target, 0) + 1
            included_samples = len(samples)

        # Feature completeness stats
        if completeness_values:
            import statistics
            comp_stats = {
                "mean": round(statistics.mean(completeness_values), 3),
                "std": round(statistics.stdev(completeness_values), 3) if len(completeness_values) > 1 else 0.0,
                "min": round(min(completeness_values), 3),
                "max": round(max(completeness_values), 3),
            }
        else:
            comp_stats = {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}

        # Warnings
        if len(samples) < 20:
            warnings.append(f"small_dataset_{len(samples)}_samples")
        if class_dist:
            min_class = min(class_dist.values())
            max_class = max(class_dist.values())
            if max_class > 0 and min_class / max_class < 0.1:
                warnings.append("severe_class_imbalance")

        return DatasetSummary(
            samples=samples,
            class_distribution=class_dist,
            quality_distribution=quality_dist,
            feature_completeness_stats=comp_stats,
            target_level=target_level,
            total_samples=len(samples),
            warnings=warnings,
            included_samples=included_samples,
            excluded_samples=excluded_samples,
            exclusion_reasons=exclusion_reasons,
        )

    def _balance_classes(
        self,
        samples: List[LabeledSample],
        target_level: str,
        max_per_class: Optional[int] = None,
    ) -> List[LabeledSample]:
        """Downsample majority classes to balance distribution."""
        # Group by target class
        by_class: Dict[str, List[LabeledSample]] = {}
        for s in samples:
            target = s.hierarchy_targets[target_level]
            by_class.setdefault(target, []).append(s)

        # Determine target count
        min_count = min(len(v) for v in by_class.values()) if by_class else 0
        if max_per_class:
            target_count = min(min_count, max_per_class)
        else:
            target_count = min_count

        # Sort each class by quality (best first) and take top N
        balanced = []
        for class_name, class_samples in by_class.items():
            sorted_samples = sorted(
                class_samples,
                key=lambda s: s.quality.overall_quality,
                reverse=True,
            )
            balanced.extend(sorted_samples[:target_count])

        return balanced

    def export_csv(
        self,
        dataset: DatasetSummary,
        output_path: Optional[str] = None,
    ) -> str:
        """Export dataset to CSV.

        Columns: label_id, plot_id, crop_code, crop_group, L0, L1, L2, L3,
                 quality_tier, quality_score, + all flat feature keys.

        Returns CSV as string. If output_path given, also writes to file.
        """
        if not dataset.samples:
            return ""

        # Collect all feature keys across samples
        all_feature_keys = set()
        for s in dataset.samples:
            all_feature_keys.update(s.features.keys())
        feature_keys = sorted(all_feature_keys)

        # Build CSV
        output = io.StringIO()
        header = [
            "label_id", "plot_id", "crop_code", "crop_group",
            "L0", "L1", "L2", "L3",
            "quality_tier", "quality_score",
            "label_source", "label_confidence",
        ] + feature_keys

        writer = csv.writer(output)
        writer.writerow(header)

        for sample in dataset.samples:
            row = [
                sample.label.label_id,
                sample.label.plot_id,
                sample.label.crop_code,
                sample.label.crop_group,
                sample.hierarchy_targets.get("L0", ""),
                sample.hierarchy_targets.get("L1", ""),
                sample.hierarchy_targets.get("L2", ""),
                sample.hierarchy_targets.get("L3", ""),
                sample.quality.quality_tier,
                sample.quality.overall_quality,
                sample.label.label_source,
                sample.label.label_confidence,
            ]
            for key in feature_keys:
                val = sample.features.get(key)
                row.append("" if val is None else val)
            writer.writerow(row)

        csv_str = output.getvalue()

        if output_path:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                f.write(csv_str)
            logger.info(f"Exported {len(dataset.samples)} samples to {output_path}")

        return csv_str

    def get_dataset_report(self, dataset: DatasetSummary) -> Dict:
        """Generate human-readable dataset quality report."""
        if not dataset.samples:
            return {
                "total_samples": 0,
                "included_samples": dataset.included_samples,
                "excluded_samples": dataset.excluded_samples,
                "exclusion_reasons": dataset.exclusion_reasons,
                "recommendation": "No labeled data available. Collect crop confirmations first.",
            }

        # Geographic coverage
        lats = []
        lngs = []
        for s in dataset.samples:
            if s.features.get("latitude") is not None:
                lats.append(s.features["latitude"])
            if s.features.get("longitude") is not None:
                lngs.append(s.features["longitude"])

        geo_coverage = {}
        if lats and lngs:
            geo_coverage = {
                "lat_range": [round(min(lats), 3), round(max(lats), 3)],
                "lng_range": [round(min(lngs), 3), round(max(lngs), 3)],
                "n_locations": len(set(zip(
                    [round(l, 2) for l in lats],
                    [round(l, 2) for l in lngs],
                ))),
            }

        # Class balance
        if dataset.class_distribution:
            min_c = min(dataset.class_distribution.values())
            max_c = max(dataset.class_distribution.values())
            balance_ratio = round(min_c / max_c, 3) if max_c > 0 else 0.0
        else:
            balance_ratio = 0.0

        # Recommendations
        recommendations = []
        if dataset.total_samples < 50:
            recommendations.append("Collect more labeled samples for reliable training.")
        if balance_ratio < 0.2:
            recommendations.append("Class imbalance is severe. Consider data augmentation or class weighting.")
        if dataset.feature_completeness_stats.get("mean", 0) < 0.5:
            recommendations.append("Average feature completeness is low. Ensure L1 runs cover labeled plots.")
        if dataset.quality_distribution.get("D", 0) > dataset.total_samples * 0.3:
            recommendations.append("Many low-quality labels. Verify farmer confirmations and geometry stability.")

        return {
            "total_samples": dataset.total_samples,
            "included_samples": dataset.included_samples,
            "excluded_samples": dataset.excluded_samples,
            "exclusion_reasons": dataset.exclusion_reasons,
            "target_level": dataset.target_level,
            "n_classes": len(dataset.class_distribution),
            "class_distribution": dataset.class_distribution,
            "class_balance_ratio": balance_ratio,
            "quality_distribution": dataset.quality_distribution,
            "feature_completeness": dataset.feature_completeness_stats,
            "geographic_coverage": geo_coverage,
            "warnings": dataset.warnings,
            "recommendations": recommendations,
            "built_at": dataset.built_at,
        }

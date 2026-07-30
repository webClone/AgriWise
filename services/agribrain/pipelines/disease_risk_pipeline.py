"""
Disease Risk Pipeline
Full ML pipeline: ingest → features → train → infer → report
Example implementation for Disease Risk AI
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pipeline import BasePipeline, PipelineRun, PipelineStage, model_registry
from core.data_layer import DATASETS, DataContract


class DiseaseRiskPipeline(BasePipeline):
    """
    Full training pipeline for Disease Risk AI.
    Processes weather/crop data → trains classifier → deploys model.
    """
    
    def __init__(self):
        super().__init__("disease_risk")
        self.dataset = DATASETS.get("disease_risk")
    
    def ingest(self, run: PipelineRun, config: Dict) -> Dict:
        """
        Stage 1: Ingest data from versioned dataset.
        Loads all accumulated samples from user interactions.
        """
        records = []
        
        # Load from versioned dataset partitions
        if self.dataset:
            for partition in self.dataset.metadata.get("partitions", []):
                partition_file = self.dataset.path / f"partition_{partition}.jsonl"
                if partition_file.exists():
                    with open(partition_file) as f:
                        for line in f:
                            records.append(json.loads(line))
        
        # Save raw data artifact
        raw_data_path = run.run_dir / "raw_data.json"
        with open(raw_data_path, "w") as f:
            json.dump(records, f, indent=2)
        run.add_artifact("raw_data", str(raw_data_path))
        
        return {
            "records": records,
            "source": "versioned_dataset",
            "schema_version": self.dataset.metadata.get("schema_version") if self.dataset else None
        }
    
    def features(self, run: PipelineRun, data: Dict, config: Dict) -> Dict:
        """
        Stage 2: Feature engineering.
        Extract relevant features from raw weather/soil data.
        """
        records = data.get("records", [])
        
        # Define feature columns
        feature_columns = [
            "temp", "humidity", "leaf_wetness", "dew_point",
            "delta_t", "vpd", "rain", "wind_speed"
        ]
        
        # Extract features
        X = []  # Feature matrix
        y = []  # Labels (if available)
        
        for record in records:
            inputs = record.get("inputs", {}).get("inputs", {})
            realtime = inputs.get("realtime", {})
            
            # Extract feature vector
            features = {
                "temp": realtime.get("temp", 20),
                "humidity": realtime.get("humidity", 50),
                "leaf_wetness": realtime.get("leafWetness", 0),
                "dew_point": realtime.get("dewPoint", 10),
                "delta_t": realtime.get("deltaT", 5),
                "vpd": realtime.get("vpd", 1),
                "rain": realtime.get("rain", 0),
                "wind_speed": realtime.get("windSpeed", 10),
            }
            X.append(features)
            
            # Extract label if available
            label = record.get("label")
            if label:
                y.append(label.get("overall_risk", "unknown"))
            else:
                # Use heuristic output as pseudo-label
                output = record.get("inputs", {}).get("output", {})
                y.append(output.get("overall_risk", "unknown"))
        
        # Split train/validation (80/20)
        split_idx = int(len(X) * 0.8)
        
        features_data = {
            "columns": feature_columns,
            "train": {"X": X[:split_idx], "y": y[:split_idx]},
            "validation": {"X": X[split_idx:], "y": y[split_idx:]},
            "total_samples": len(X)
        }
        
        # Save features artifact
        features_path = run.run_dir / "features.json"
        with open(features_path, "w") as f:
            json.dump(features_data, f, indent=2)
        run.add_artifact("features", str(features_path))
        
        return features_data
    
    def train(self, run: PipelineRun, features: Dict, config: Dict) -> Dict:
        """
        Stage 3: Train disease risk model.
        Uses rule-based thresholds initially, upgrades to ML when data sufficient.
        """
        X_train = features.get("train", {}).get("X", [])
        y_train = features.get("train", {}).get("y", [])
        
        # Check if we have enough data for ML
        min_samples_for_ml = config.get("min_samples", 100)
        
        if len(X_train) >= min_samples_for_ml:
            # Train actual ML model (scikit-learn when available)
            model = self._train_ml_model(X_train, y_train, config)
            model_type = "ml_classifier"
        else:
            # Use rule-based model (heuristic thresholds)
            model = self._create_rule_based_model()
            model_type = "rule_based"
        
        # Calculate training metrics
        metrics = {
            "model_type": model_type,
            "train_samples": len(X_train),
            "min_samples_for_ml": min_samples_for_ml,
            "ready_for_ml": len(X_train) >= min_samples_for_ml
        }
        
        # Save model artifact
        model_path = self.models_dir / f"model_{run.run_id}.json"
        with open(model_path, "w") as f:
            json.dump({
                "type": model_type,
                "params": model,
                "trained_at": datetime.now().isoformat(),
                "samples": len(X_train)
            }, f, indent=2)
        run.add_artifact("model", str(model_path))
        
        # Register model
        version = model_registry.register(
            "disease_risk",
            str(model_path),
            metrics
        )
        
        return {
            "model": model,
            "model_type": model_type,
            "model_path": str(model_path),
            "version": version,
            "metrics": metrics
        }
    
    def _train_ml_model(self, X: List[Dict], y: List[str], config: Dict) -> Dict:
        """Train actual ML model using scikit-learn."""
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import LabelEncoder
            import numpy as np
            
            # Convert to numpy arrays
            feature_names = list(X[0].keys()) if X else []
            X_array = np.array([[sample.get(f, 0) for f in feature_names] for sample in X])
            
            # Encode labels
            le = LabelEncoder()
            y_encoded = le.fit_transform(y)
            
            # Train Random Forest
            clf = RandomForestClassifier(
                n_estimators=config.get("n_estimators", 50),
                max_depth=config.get("max_depth", 5),
                random_state=42
            )
            clf.fit(X_array, y_encoded)
            
            # Get feature importance
            importance = dict(zip(feature_names, clf.feature_importances_.tolist()))
            
            return {
                "algorithm": "random_forest",
                "feature_names": feature_names,
                "feature_importance": importance,
                "classes": le.classes_.tolist(),
                "n_estimators": clf.n_estimators,
                "max_depth": clf.max_depth
            }
            
        except ImportError:
            # Fall back to rule-based if sklearn not available
            return self._create_rule_based_model()
    
    def _create_rule_based_model(self) -> Dict:
        """Create rule-based model (heuristic thresholds)."""
        return {
            "algorithm": "rule_based",
            "rules": {
                "high_risk": {
                    "humidity_min": 90,
                    "temp_range": [10, 25],
                    "leaf_wetness_min": 50
                },
                "moderate_risk": {
                    "humidity_min": 70,
                    "temp_range": [15, 28],
                },
                "low_risk": {
                    "default": True
                }
            }
        }
    
    def infer(self, run: PipelineRun, model: Dict, inputs: Dict) -> Dict:
        """
        Stage 4: Run inference on validation set.
        """
        X_val = inputs.get("X", [])
        y_val = inputs.get("y", [])
        
        predictions = []
        correct = 0
        
        for i, sample in enumerate(X_val):
            pred = self._predict_single(model, sample)
            predictions.append(pred)
            
            if i < len(y_val) and pred == y_val[i]:
                correct += 1
        
        accuracy = correct / len(predictions) if predictions else 0
        
        return {
            "results": predictions,
            "accuracy": accuracy,
            "total": len(predictions)
        }
    
    def _predict_single(self, model: Dict, sample: Dict) -> str:
        """Make single prediction using model."""
        if model.get("algorithm") == "random_forest":
            # Would use trained model here
            pass
        
        # Default to rule-based
        rules = model.get("rules", {})
        
        humidity = sample.get("humidity", 50)
        temp = sample.get("temp", 20)
        leaf_wetness = sample.get("leaf_wetness", 0)
        
        high_risk_rules = rules.get("high_risk", {})
        if (humidity >= high_risk_rules.get("humidity_min", 90) and
            high_risk_rules.get("temp_range", [0, 100])[0] <= temp <= high_risk_rules.get("temp_range", [0, 100])[1]):
            return "high"
        
        mod_risk_rules = rules.get("moderate_risk", {})
        if humidity >= mod_risk_rules.get("humidity_min", 70):
            return "moderate"
        
        return "low"
    
    def report(self, run: PipelineRun, results: Dict) -> Dict:
        """
        Stage 5: Generate training report.
        """
        model_info = results.get("model", {})
        predictions = results.get("predictions", {})
        features = results.get("features", {})
        
        report = {
            "pipeline": self.pipeline_id,
            "run_id": run.run_id,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "model_type": model_info.get("model_type"),
                "total_samples": features.get("total_samples", 0),
                "training_samples": len(features.get("train", {}).get("X", [])),
                "validation_samples": len(features.get("validation", {}).get("X", [])),
                "validation_accuracy": predictions.get("accuracy", 0),
            },
            "model": {
                "version": model_info.get("version"),
                "path": model_info.get("model_path"),
            },
            "recommendations": self._generate_recommendations(model_info, predictions)
        }
        
        # Save report
        report_path = run.run_dir / "report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        run.add_artifact("report", str(report_path))
        
        # Also save human-readable markdown report
        md_report = self._generate_markdown_report(report)
        md_path = run.run_dir / "report.md"
        with open(md_path, "w") as f:
            f.write(md_report)
        run.add_artifact("report_md", str(md_path))
        
        return report
    
    def _generate_recommendations(self, model_info: Dict, predictions: Dict) -> List[str]:
        """Generate recommendations based on training results."""
        recommendations = []
        
        model_type = model_info.get("model_type")
        metrics = model_info.get("metrics", {})
        
        if model_type == "rule_based":
            samples = metrics.get("train_samples", 0)
            min_needed = metrics.get("min_samples_for_ml", 100)
            remaining = min_needed - samples
            recommendations.append(
                f"Need {remaining} more samples to enable ML training. "
                f"Current: {samples}/{min_needed}"
            )
        
        accuracy = predictions.get("accuracy", 0)
        if accuracy < 0.7:
            recommendations.append(
                "Model accuracy below 70%. Consider collecting more diverse training data."
            )
        
        return recommendations
    
    def _generate_markdown_report(self, report: Dict) -> str:
        """Generate human-readable markdown report."""
        summary = report.get("summary", {})
        
        md = f"""# Disease Risk Pipeline Report

**Run ID:** {report.get('run_id')}
**Generated:** {report.get('generated_at')}

## Summary

| Metric | Value |
|--------|-------|
| Model Type | {summary.get('model_type')} |
| Total Samples | {summary.get('total_samples')} |
| Training Samples | {summary.get('training_samples')} |
| Validation Samples | {summary.get('validation_samples')} |
| Validation Accuracy | {summary.get('validation_accuracy', 0):.1%} |

## Model

- **Version:** {report.get('model', {}).get('version')}
- **Path:** `{report.get('model', {}).get('path')}`

## Recommendations

"""
        for rec in report.get("recommendations", []):
            md += f"- {rec}\n"
        
        return md


# Factory function
def create_pipeline(ai_name: str) -> Optional[BasePipeline]:
    """Create pipeline for specified AI."""
    pipelines = {
        "disease_risk": DiseaseRiskPipeline,
    }
    
    pipeline_class = pipelines.get(ai_name)
    if pipeline_class:
        return pipeline_class()
    return None

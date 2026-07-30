"""
Crop Intelligence v6.0C — Hierarchical ML Classifier.

Trains, evaluates, and runs a hierarchical Random Forest classifier
on top of v6.0A CropFeatureVector data. Supports:
  - Level sample gates to prevent over-fitting on tiny datasets
  - GroupKFold split by plot_id to prevent farm-level validation leakage
  - Conditional probability calibration
  - Atomic model saving (pickle + JSON metadata)
  - Agronomic constraint filtering & fallback reporting
"""

import os
import pickle
import json
import tempfile
import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer

from .label_schema import LabeledSample
from ..features.crop_feature_vector import CropFeatureVector

logger = logging.getLogger("agribrain.labels.classifier")

# ── Level Gates ──────────────────────────────────────────────────────────────
MIN_CLASSES_PER_LEVEL = 2
MIN_SAMPLES_PER_CLASS = 5
MIN_TOTAL_SAMPLES = 30

# Version Constants
MODEL_VERSION = "6.0C"
FEATURE_VECTOR_VERSION = "6.0.0"
LABEL_SCHEMA_VERSION = "6.0B"


# ── Trivial Classifier Fallback ──────────────────────────────────────────────

class TrivialClassifier:
    """Fallback classifier when a level has exactly 1 class."""
    
    def __init__(self, class_name: str):
        self.classes_ = np.array([class_name])
        
    def fit(self, X, y):
        return self
        
    def predict(self, X):
        return np.array([self.classes_[0]] * len(X))
        
    def predict_proba(self, X):
        return np.array([[1.0]] * len(X))


# ── Atomic Writing Helper ───────────────────────────────────────────────────

def _atomic_write(data: Any, target_path: str, is_json: bool = False) -> None:
    """Write data to a temp file first, then atomically rename it."""
    dir_name = os.path.dirname(target_path)
    os.makedirs(dir_name, exist_ok=True)
    
    fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        if is_json:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        else:
            with os.fdopen(fd, "wb") as f:
                pickle.dump(data, f)
        os.replace(temp_path, target_path)
    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise e


import importlib

def _atomic_write_npz(arrays_dict: dict, target_path: str) -> None:
    dir_name = os.path.dirname(target_path)
    os.makedirs(dir_name, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=".npz")
    try:
        os.close(fd)
        np.savez(temp_path, **arrays_dict)
        os.replace(temp_path, target_path)
    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise e

def serialize_model(obj, prefix, arrays_dict):
    if obj is None:
        return None
        
    if isinstance(obj, np.ndarray):
        key = f"{prefix}_array"
        arrays_dict[key] = obj
        return {"__type__": "ndarray", "key": key}
        
    if type(obj).__name__ == "Tree":
        state = obj.__getstate__()
        if isinstance(state, dict):
            max_depth = state["max_depth"]
            node_count = state["node_count"]
            nodes = state["nodes"]
            values = state["values"]
        else:
            max_depth, node_count, nodes, values = state
            
        n_features = obj.n_features
        n_classes = obj.n_classes
        n_outputs = obj.n_outputs
        
        nodes_key = f"{prefix}_tree_nodes"
        values_key = f"{prefix}_tree_values"
        n_classes_key = f"{prefix}_tree_n_classes"
        arrays_dict[nodes_key] = nodes
        arrays_dict[values_key] = values
        arrays_dict[n_classes_key] = n_classes
        
        return {
            "__type__": "Tree",
            "max_depth": max_depth,
            "node_count": node_count,
            "n_features": n_features,
            "n_classes_key": n_classes_key,
            "n_outputs": n_outputs,
            "nodes_key": nodes_key,
            "values_key": values_key
        }
        
    if isinstance(obj, (int, float, str, bool)):
        return obj
        
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()

    if isinstance(obj, np.dtype):
        return {"__type__": "dtype", "name": str(obj)}
        
    if isinstance(obj, list):
        return [serialize_model(x, f"{prefix}_{i}", arrays_dict) for i, x in enumerate(obj)]
        
    if isinstance(obj, tuple):
        return {
            "__type__": "tuple",
            "items": [serialize_model(x, f"{prefix}_{i}", arrays_dict) for i, x in enumerate(obj)]
        }
        
    if isinstance(obj, dict):
        return {k: serialize_model(v, f"{prefix}_{k}", arrays_dict) for k, v in obj.items()}
        
    class_name = obj.__class__.__name__
    module_name = obj.__class__.__module__
    
    state = {}
    for k, v in obj.__dict__.items():
        if k.startswith("_") and k not in (
            "_estimator_type", "_classes", "_calibrated_classifiers", 
            "_fit_dtype", "_fill_dtype", "_n_samples", "_n_samples_bootstrap"
        ):
            continue
        state[k] = serialize_model(v, f"{prefix}_{class_name}_{k}", arrays_dict)
        
    return {
        "__type__": "object",
        "class": class_name,
        "module": module_name,
        "state": state
    }

def deserialize_model(data, arrays_dict):
    if data is None:
        return None
        
    if isinstance(data, (int, float, str, bool)):
        return data
        
    if isinstance(data, list):
        return [deserialize_model(x, arrays_dict) for x in data]
        
    if isinstance(data, dict):
        t = data.get("__type__")
        if t == "tuple":
            return tuple(deserialize_model(x, arrays_dict) for x in data["items"])
            
        if t == "dtype":
            return np.dtype(data["name"])
            
        if t == "ndarray":
            return arrays_dict[data["key"]]
            
        if t == "Tree":
            from sklearn.tree._tree import Tree
            max_depth = data["max_depth"]
            node_count = data["node_count"]
            n_features = data["n_features"]
            n_classes = arrays_dict[data["n_classes_key"]]
            n_outputs = data["n_outputs"]
            nodes = arrays_dict[data["nodes_key"]]
            values = arrays_dict[data["values_key"]]
            
            tree = Tree(n_features, n_classes, n_outputs)
            try:
                tree.__setstate__({
                    "max_depth": max_depth,
                    "node_count": node_count,
                    "nodes": nodes,
                    "values": values
                })
            except TypeError:
                tree.__setstate__((max_depth, node_count, nodes, values))
            return tree
            
        if t == "object":
            class_name = data["class"]
            module_name = data["module"]
            state = data["state"]
            
            try:
                mod = importlib.import_module(module_name)
                cls = getattr(mod, class_name)
            except Exception:
                if class_name == "TrivialClassifier":
                    cls = TrivialClassifier
                elif class_name == "SimpleImputer":
                    from sklearn.impute import SimpleImputer
                    cls = SimpleImputer
                elif class_name == "RandomForestClassifier":
                    from sklearn.ensemble import RandomForestClassifier
                    cls = RandomForestClassifier
                elif class_name == "DecisionTreeClassifier":
                    from sklearn.tree import DecisionTreeClassifier
                    cls = DecisionTreeClassifier
                elif class_name == "CalibratedClassifierCV":
                    from sklearn.calibration import CalibratedClassifierCV
                    cls = CalibratedClassifierCV
                elif class_name == "_CalibratedClassifier":
                    from sklearn.calibration import _CalibratedClassifier
                    cls = _CalibratedClassifier
                elif class_name == "_SigmoidCalibration":
                    from sklearn.calibration import _SigmoidCalibration
                    cls = _SigmoidCalibration
                else:
                    raise ValueError(f"Unknown class {class_name}")
            
            obj = cls.__new__(cls)
            restored_state = {k: deserialize_model(v, arrays_dict) for k, v in state.items()}
            obj.__dict__.update(restored_state)
            return obj
            
        return {k: deserialize_model(v, arrays_dict) for k, v in data.items()}
        
    return data



# ── Hierarchical Classifier ──────────────────────────────────────────────────

class ModelLoadStatus(dict):
    """Custom dictionary representation of model loading status.
    
    Evaluates to True if the model successfully loaded and is production eligible
    (or dev-approved), and False otherwise. Keeping backward compatibility.
    """
    def __init__(self, success: bool, data: Dict[str, Any]):
        super().__init__(data)
        self.success = success
        
    def __bool__(self) -> bool:
        return self.success


class HierarchicalCropClassifier:
    """Hierarchical Crop Classifier training and inference pipeline."""

    def __init__(self, model_dir: Optional[str] = None):
        if model_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            model_dir = os.path.join(base_dir, ".cache", "crop_models")
        self.model_dir = model_dir
        self.models: Optional[Dict[str, Any]] = None
        self.feature_names: List[str] = []
        self.imputer: Optional[SimpleImputer] = None
        self.metadata: Optional[Dict[str, Any]] = None
        self.production_eligible: bool = False

    def save(self) -> None:
        """Atomically serialize models and metadata to model_dir."""
        if not self.models or not self.feature_names or not self.imputer or not self.metadata:
            raise ValueError("Cannot save: classifier has not been trained yet.")
        
        os.makedirs(self.model_dir, exist_ok=True)
        
        # 1. Serialize models and imputer to dict & arrays
        arrays_dict = {}
        payload = {
            "models": self.models,
            "feature_names": self.feature_names,
            "imputer": self.imputer,
        }
        serialized_payload = serialize_model(payload, "model", arrays_dict)
        
        # 2. Save JSON manifest
        manifest_path = os.path.join(self.model_dir, "model_manifest.json")
        _atomic_write(serialized_payload, manifest_path, is_json=True)
        
        # 3. Save NPZ arrays
        arrays_path = os.path.join(self.model_dir, "model_arrays.npz")
        _atomic_write_npz(arrays_dict, arrays_path)

        # 4. Save JSON metadata
        meta_path = os.path.join(self.model_dir, "model_metadata.json")
        _atomic_write(self.metadata, meta_path, is_json=True)
        
        logger.info(f"[Classifier] Saved hierarchical models & metadata to {self.model_dir}")

    def load(self, allow_legacy_pickle: bool = False) -> Any:
        """Load models and metadata from model_dir."""
        manifest_path = os.path.join(self.model_dir, "model_manifest.json")
        arrays_path = os.path.join(self.model_dir, "model_arrays.npz")
        meta_path = os.path.join(self.model_dir, "model_metadata.json")
        legacy_path = os.path.join(self.model_dir, "hierarchical_models.pkl")
        
        env_allow_pickle = os.environ.get("AGRIBRAIN_ALLOW_LEGACY_PICKLE", "false").lower() == "true"
        allow_legacy = allow_legacy_pickle or env_allow_pickle

        # JSON+NPZ path
        if os.path.exists(manifest_path) and os.path.exists(arrays_path) and os.path.exists(meta_path):
            try:
                from common.safe_npz import safe_np_load
                with safe_np_load(arrays_path) as data:
                    arrays_dict = {k: data[k] for k in data.files}
                
                with open(manifest_path, "r", encoding="utf-8") as f:
                    serialized_payload = json.load(f)
                
                payload = deserialize_model(serialized_payload, arrays_dict)
                self.models = payload["models"]
                self.feature_names = payload["feature_names"]
                self.imputer = payload["imputer"]
                
                with open(meta_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                
                return self._post_load_eligibility()
            except Exception as e:
                logger.error(f"[Classifier] Failed to load JSON+NPZ model: {e}")
                return ModelLoadStatus(False, {
                    "model_loaded": False,
                    "blocked_reason": f"error: {str(e)}"
                })
        
        # Legacy pickle path
        elif os.path.exists(legacy_path) and os.path.exists(meta_path):
            if not allow_legacy:
                logger.error("[Classifier] Pickle models are forbidden in production.")
                return ModelLoadStatus(False, {
                    "model_loaded": False,
                    "blocked_reason": "legacy_pickle_rejected"
                })
            
            try:
                with open(legacy_path, "rb") as f:
                    payload = pickle.load(f)
                    self.models = payload["models"]
                    self.feature_names = payload["feature_names"]
                    self.imputer = payload["imputer"]
                
                with open(meta_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                    
                return self._post_load_eligibility()
            except Exception as e:
                logger.error(f"[Classifier] Failed to load legacy pickle model: {e}")
                return ModelLoadStatus(False, {
                    "model_loaded": False,
                    "blocked_reason": f"error: {str(e)}"
                })
        
        else:
            return ModelLoadStatus(False, {
                "model_loaded": False,
                "blocked_reason": "files_not_found"
            })

    def _post_load_eligibility(self) -> ModelLoadStatus:
        # A model file alone is not a scientific deployment contract. Version,
        # schema identity, held-out validation, and explicit eligibility are
        # mandatory and default-deny.
        metadata = self.metadata if isinstance(self.metadata, dict) else {}
        required_text = (
            "model_version",
            "feature_vector_version",
            "label_schema_version",
            "feature_order_hash",
        )
        missing = [key for key in required_text if not metadata.get(key)]
        validation_reports = metadata.get("validation_reports")
        if not isinstance(validation_reports, dict) or not validation_reports:
            missing.append("validation_reports")
        computed_schema_hash = hashlib.sha256(
            ",".join(sorted(self.feature_names)).encode("utf-8")
        ).hexdigest()
        if metadata.get("feature_order_hash") != computed_schema_hash:
            missing.append("feature_order_hash_mismatch")
        trained_levels = [
            level for level, status in (
                metadata.get("level_status") or {}
            ).items()
            if status == "trained"
        ]
        validated_levels = [
            level for level in trained_levels
            if isinstance(validation_reports, dict)
            and (validation_reports.get(level) or {}).get(
                "validation_status"
            ) == "evaluated"
            and int(
                (validation_reports.get(level) or {}).get(
                    "folds_used", 0
                ) or 0
            ) >= 2
        ]
        if not trained_levels or len(validated_levels) != len(trained_levels):
            missing.append("held_out_validation_incomplete")
        if missing:
            self.models = None
            self.imputer = None
            self.production_eligible = False
            return ModelLoadStatus(False, {
                "model_loaded": False,
                "blocked_reason": "invalid_model_deployment_contract",
                "missing_or_invalid": sorted(set(missing)),
            })

        production_eligible = metadata.get("production_eligible") is True
        training_dataset_type = str(
            metadata.get("training_dataset_type", "unknown")
        )
        is_synthetic_model = (training_dataset_type == "synthetic_seeded" or not production_eligible)
        
        allow_synthetic = os.environ.get("AGRIBRAIN_DEV_ALLOW_SYNTHETIC_MODEL", "false").lower() == "true"
        
        if is_synthetic_model and not allow_synthetic:
            logger.warning(
                "[Classifier] Refusing to load synthetic-only model in production/inference "
                "because production_eligible is False and AGRIBRAIN_DEV_ALLOW_SYNTHETIC_MODEL is not set."
            )
            self.models = None
            self.imputer = None
            self.production_eligible = False
            return ModelLoadStatus(False, {
                "model_loaded": False,
                "blocked_reason": "synthetic_model_not_production_eligible",
                "training_dataset_type": training_dataset_type
            })
            
        self.production_eligible = bool(
            production_eligible
            and training_dataset_type == "real_world"
            and "production_inference" in (
                metadata.get("allowed_for") or []
            )
        )
        logger.info(f"[Classifier] Loaded hierarchical models (trained at {self.metadata.get('trained_at')})")
        return ModelLoadStatus(True, {
            "model_loaded": True,
            "training_dataset_type": training_dataset_type,
            "production_eligible": self.production_eligible,
            "model_version": metadata.get("model_version"),
            "feature_schema_hash": computed_schema_hash,
            "validated_levels": validated_levels,
        })

    def train(
        self,
        samples: List[LabeledSample],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Train classifier with GroupKFold validation and level gating.
        
        Args:
            samples: Training samples with features and hierarchy targets.
            dry_run: If True, returns evaluation without saving to disk.
        """
        if not samples:
            return {
                "status": "not_trained",
                "reason": "no_training_samples"
            }

        # Align feature names deterministically
        flat_keys = sorted(list(CropFeatureVector().to_flat_dict().keys()))
        self.feature_names = flat_keys
        
        # Calculate feature order hash
        feature_order_hash = hashlib.sha256(",".join(flat_keys).encode("utf-8")).hexdigest()

        # Extract features (X) and metadata
        X_raw = []
        plot_ids = []
        
        # Map levels to list
        targets: Dict[str, List[str]] = {"L0": [], "L1": [], "L2": [], "L3": []}
        
        for s in samples:
            row = [s.features.get(f) for f in flat_keys]
            X_raw.append(row)
            plot_ids.append(s.label.plot_id)
            
            targets["L0"].append(s.hierarchy_targets.get("L0", "non_crop"))
            targets["L1"].append(s.hierarchy_targets.get("L1", "fallow"))
            targets["L2"].append(s.hierarchy_targets.get("L2", "non_crop"))
            targets["L3"].append(s.hierarchy_targets.get("L3", "unknown"))

        X_arr = np.array(X_raw, dtype=np.float64)
        groups = np.array(plot_ids)
        n_unique_groups = len(np.unique(groups))

        # Fit Imputer
        imputer = SimpleImputer(strategy="median")
        X_imputed = imputer.fit_transform(X_arr)

        trained_models = {}
        level_status = {}
        validation_reports = {}
        calibration_modes = {}
        class_distributions = {}

        # Train each level
        for level in ["L0", "L1", "L2", "L3"]:
            y_list = targets[level]
            y_arr = np.array(y_list)
            
            # 1. Compute class distribution
            unique_classes, counts = np.unique(y_arr, return_counts=True)
            dist = {str(k): int(v) for k, v in zip(unique_classes, counts)}
            class_distributions[level] = dist

            # 2. Level gating rules
            n_classes = len(unique_classes)
            min_samples = np.min(counts) if len(counts) > 0 else 0
            total_samples = len(y_arr)

            # L0 gate is slightly relaxed, other levels strictly require thresholds
            if level == "L0":
                # L0 requires at least 2 classes and basic count
                is_trainable = n_classes >= 2 and total_samples >= 10
            else:
                is_trainable = (
                    n_classes >= MIN_CLASSES_PER_LEVEL and
                    min_samples >= MIN_SAMPLES_PER_CLASS and
                    total_samples >= MIN_TOTAL_SAMPLES
                )

            if not is_trainable:
                level_status[level] = "not_enough_data"
                validation_reports[level] = {
                    "validation_status": "skipped_not_trainable",
                    "internal_validation_accuracy": 0.0,
                    "folds_used": 0,
                }
                calibration_modes[level] = "none"
                continue

            # 3. Validation: GroupKFold / StratifiedGroupKFold
            val_acc = 0.0
            val_status = "not_enough_groups"
            
            if n_unique_groups >= 2:
                n_splits = min(3, n_unique_groups)
                
                # Check StratifiedGroupKFold availability
                try:
                    from sklearn.model_selection import StratifiedGroupKFold
                    gkf = StratifiedGroupKFold(n_splits=n_splits)
                except ImportError:
                    from sklearn.model_selection import GroupKFold
                    gkf = GroupKFold(n_splits=n_splits)
                
                fold_scores = []
                try:
                    for train_idx, val_idx in gkf.split(X_imputed, y_arr, groups=groups):
                        X_tr, X_val = X_imputed[train_idx], X_imputed[val_idx]
                        y_tr, y_val = y_arr[train_idx], y_arr[val_idx]
                        
                        # Fold model calibration logic
                        tr_unique, tr_counts = np.unique(y_tr, return_counts=True)
                        tr_min_samples = np.min(tr_counts) if len(tr_counts) > 0 else 0
                        tr_unique_groups = len(np.unique(groups[train_idx]))
                        
                        if len(tr_unique) <= 1:
                            fold_model = TrivialClassifier(tr_unique[0])
                        elif tr_min_samples >= 5 and tr_unique_groups >= 3:
                            base_rf = RandomForestClassifier(n_estimators=50, random_state=42)
                            fold_model = CalibratedClassifierCV(estimator=base_rf, cv=min(3, tr_unique_groups))
                        else:
                            fold_model = RandomForestClassifier(n_estimators=50, random_state=42)
                            
                        fold_model.fit(X_tr, y_tr)
                        preds = fold_model.predict(X_val)
                        fold_scores.append(float(np.mean(preds == y_val)))
                        
                    val_acc = float(np.mean(fold_scores)) if fold_scores else 0.0
                    val_status = "evaluated"
                except Exception as e:
                    val_status = f"evaluation_failed: {str(e)[:80]}"
            
            validation_reports[level] = {
                "validation_status": val_status,
                "internal_validation_accuracy": round(val_acc, 4),
                "folds_used": min(3, n_unique_groups) if n_unique_groups >= 2 else 0,
            }

            # 4. Train final model on all data
            # Check calibration viability
            can_calibrate = (
                min_samples >= 5 and
                n_unique_groups >= 3
            )

            if n_classes == 1:
                model = TrivialClassifier(unique_classes[0])
                calibration_modes[level] = "trivial"
            elif can_calibrate:
                base_rf = RandomForestClassifier(n_estimators=50, random_state=42)
                model = CalibratedClassifierCV(estimator=base_rf, cv=3)
                calibration_modes[level] = "calibrated"
            else:
                model = RandomForestClassifier(n_estimators=50, random_state=42)
                calibration_modes[level] = "uncalibrated"

            model.fit(X_imputed, y_arr)
            trained_models[level] = model
            level_status[level] = "trained"

        # Assemble metadata
        has_synthetic = any(getattr(s.label, "synthetic", False) for s in samples)
        trained_levels = [
            level for level, status in level_status.items()
            if status == "trained"
        ]
        heldout_validated = bool(trained_levels) and all(
            (validation_reports.get(level) or {}).get(
                "validation_status"
            ) == "evaluated"
            and int(
                (validation_reports.get(level) or {}).get(
                    "folds_used", 0
                ) or 0
            ) >= 2
            for level in trained_levels
        )
        if has_synthetic:
            training_dataset_type = "synthetic_seeded"
            production_eligible = False
            allowed_for = ["pipeline_validation", "internal_demo"]
        else:
            training_dataset_type = "real_world"
            production_eligible = heldout_validated
            allowed_for = ["pipeline_validation", "internal_demo"]
            if production_eligible:
                allowed_for.insert(0, "production_inference")

        metadata = {
            "model_version": MODEL_VERSION,
            "trained_at": datetime.now(timezone.utc).isoformat() + "Z",
            "feature_vector_version": FEATURE_VECTOR_VERSION,
            "label_schema_version": LABEL_SCHEMA_VERSION,
            "sample_count": len(samples),
            "level_status": level_status,
            "class_distribution": class_distributions,
            "calibration_modes": calibration_modes,
            "validation_reports": validation_reports,
            "features_used": flat_keys,
            "feature_order_hash": feature_order_hash,
            "imputer_strategy": "median",
            "validation_method": "StratifiedGroupKFold_by_plot_id" if n_unique_groups >= 2 else "none",
            "heldout_validation_complete": heldout_validated,
            "training_dataset_type": training_dataset_type,
            "production_eligible": production_eligible,
            "allowed_for": allowed_for,
        }

        if not dry_run:
            self.models = trained_models
            self.imputer = imputer
            self.metadata = metadata
            self.save()

        return metadata

    def predict(
        self,
        feature_vector: Any,
        apply_constraints: bool = True,
    ) -> Dict[str, Any]:
        """Perform hierarchical prediction on a CropFeatureVector or snapshot dict.
        
        Args:
            feature_vector: Structured CropFeatureVector from v6.0A or flat dict.
            apply_constraints: Apply agronomic constraint filters to Level 3.
        """
        if not self.models or not self.imputer or not self.feature_names or not self.metadata:
            raise ValueError("Classifier has not been loaded or trained.")

        if isinstance(feature_vector, dict):
            if "flat_features" in feature_vector:
                flat = feature_vector["flat_features"]
            else:
                flat = feature_vector
            fv_version = feature_vector.get("feature_vector_version", FEATURE_VECTOR_VERSION)
            data_completeness = feature_vector.get("data_completeness", 1.0)
            koppen = feature_vector.get("koppen_zone") or flat.get("koppen_zone")
            aridity = feature_vector.get("aridity_index") or flat.get("aridity_index")
            irrigation = feature_vector.get("irrigation_type") or flat.get("irrigation_type")
            lat = feature_vector.get("latitude") or flat.get("latitude")
            lng = feature_vector.get("longitude") or flat.get("longitude")
        else:
            flat = feature_vector.to_flat_dict()
            fv_version = feature_vector.feature_vector_version
            data_completeness = feature_vector.data_completeness
            koppen = feature_vector.koppen_zone
            aridity = feature_vector.aridity_index
            irrigation = feature_vector.irrigation_type
            lat = feature_vector.latitude
            lng = feature_vector.longitude

        # ── Gate 1: Check Feature Vector Schema ──
        if fv_version != FEATURE_VECTOR_VERSION:
            raise ValueError(f"Feature version mismatch: model expects {FEATURE_VECTOR_VERSION}, got {fv_version}")

        # Ensure features are aligned
        row = []
        for f in self.feature_names:
            if f not in flat:
                raise ValueError(f"Required feature '{f}' missing from CropFeatureVector to_flat_dict().")
            row.append(flat[f])

        X_test = np.array([row], dtype=np.float64)
        X_imputed = self.imputer.transform(X_test)

        output: Dict[str, Any] = {}


        # ── Predict L0 ──
        if self.metadata["level_status"].get("L0") == "trained":
            model_l0 = self.models["L0"]
            prob = model_l0.predict_proba(X_imputed)[0]
            classes = model_l0.classes_
            
            # Resolve active_crop probability
            active_idx = np.where(classes == "active_crop")[0]
            active_prob = float(prob[active_idx[0]]) if len(active_idx) > 0 else 0.0
            pred = str(model_l0.predict(X_imputed)[0])
            output["L0"] = {"prediction": pred, "probability": round(active_prob, 4)}
        else:
            output["L0"] = {"prediction": None, "probability": 0.0, "reason": "not_trained"}

        # ── Predict L1 ──
        if self.metadata["level_status"].get("L1") == "trained":
            model_l1 = self.models["L1"]
            prob = model_l1.predict_proba(X_imputed)[0]
            classes = model_l1.classes_
            dist = {str(k): round(float(v), 4) for k, v in zip(classes, prob)}
            pred = str(model_l1.predict(X_imputed)[0])
            output["L1"] = {"prediction": pred, "probability": dist.get(pred, 0.0), "distribution": dist}
        else:
            output["L1"] = {"prediction": None, "probability": 0.0, "reason": "not_trained"}

        # ── Predict L2 ──
        if self.metadata["level_status"].get("L2") == "trained":
            model_l2 = self.models["L2"]
            prob = model_l2.predict_proba(X_imputed)[0]
            classes = model_l2.classes_
            dist = {str(k): round(float(v), 4) for k, v in zip(classes, prob)}
            pred = str(model_l2.predict(X_imputed)[0])
            output["L2"] = {"prediction": pred, "probability": dist.get(pred, 0.0), "distribution": dist}
        else:
            output["L2"] = {"prediction": None, "probability": 0.0, "reason": "not_trained"}

        # ── Predict L3 (with agronomic filtering) ──
        if self.metadata["level_status"].get("L3") == "trained":
            model_l3 = self.models["L3"]
            prob = model_l3.predict_proba(X_imputed)[0]
            classes = model_l3.classes_
            
            raw_candidates = [{"code": str(k), "raw_prob": float(v)} for k, v in zip(classes, prob)]
            
            # Apply agronomic constraint filtering
            filtered_candidates = []
            removed_candidates = []
            fallback_triggered = False
            
            for cand in raw_candidates:
                code = cand["code"]
                p = cand["raw_prob"]
                
                if apply_constraints and koppen:
                    # Score constraints
                    s_koppen = self._score_koppen(code, koppen)
                    s_aridity = self._score_aridity(code, mean_temp_c=None, irrigation_type=irrigation, annual_rainfall_mm=None, et0_mm=None)
                    s_region = self._check_region_compat(code, koppen)
                    
                    # Hard elimination: if Köppen <= 0.1 or aridity <= 0.2 or region incompatible
                    if s_koppen <= 0.1 or s_aridity <= 0.2 or not s_region:
                        removed_candidates.append(code)
                        # Eliminate
                        p = 0.0
                
                filtered_candidates.append({"code": code, "prob": p})
            
            # Re-normalize if sum > 0
            total_prob = sum(c["prob"] for c in filtered_candidates)
            
            if total_prob > 0.0:
                for c in filtered_candidates:
                    c["probability"] = round(c["prob"] / total_prob, 4)
                    del c["prob"]
            else:
                # All candidates zeroed out by agronomic constraints!
                # Trigger fallback
                fallback_triggered = True
                filtered_candidates = [{"code": c["code"], "probability": round(c["raw_prob"], 4)} for c in raw_candidates]

            # Sort candidates
            filtered_candidates.sort(key=lambda x: x["probability"], reverse=True)
            top_cand = filtered_candidates[0] if filtered_candidates else None
            
            # Shannon entropy over exact candidates (excluding 0 prob)
            active_probs = [c["probability"] for c in filtered_candidates if c["probability"] > 0]
            entropy = 0.0
            for ap in active_probs:
                entropy -= ap * math.log2(ap)
            max_entropy = math.log2(len(active_probs)) if len(active_probs) > 1 else 1.0
            norm_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

            # Margin check
            margin = filtered_candidates[0]["probability"] - filtered_candidates[1]["probability"] if len(filtered_candidates) > 1 else 1.0

            # Determine ambiguity reason
            ambiguity_reason = None
            if data_completeness < 0.4:
                ambiguity_reason = "insufficient_features_l3"
            elif norm_entropy > 0.7 or margin < 0.05:
                ambiguity_reason = "high_entropy_l3"

            # Populate Level 3 prediction details
            output["L3"] = {
                "prediction": top_cand["code"] if (top_cand and not fallback_triggered) else None,
                "probability": top_cand["probability"] if (top_cand and not fallback_triggered) else 0.0,
                "reason": "fallback_triggered" if fallback_triggered else (ambiguity_reason or "trained"),
                "top_candidates": filtered_candidates[:5],
                "agronomic_filter": {
                    "applied": apply_constraints,
                    "removed_candidates": removed_candidates,
                    "fallback_triggered": fallback_triggered,
                }
            }
        else:
            output["L3"] = {
                "prediction": None,
                "probability": 0.0,
                "reason": "insufficient_l3_training_data",
                "top_candidates": [],
                "agronomic_filter": {
                    "applied": apply_constraints,
                    "removed_candidates": [],
                    "fallback_triggered": False,
                }
            }

        return {
            "ml_classifier_output": output,
            "feature_vector_version": fv_version,
            "probability_calibration": self.metadata.get("calibration_modes", {}),
            "data_completeness": data_completeness,
        }

    # ── Agronomic Constraints Implementation ──────────────────────────────────

    def _score_koppen(self, crop_code: str, koppen_zone: Optional[str]) -> float:
        """Score crop affinity for the detected Köppen climate zone."""
        from layer2_veg_int.crop_science_data import KOPPEN_CROP_AFFINITY
        from crop_database import CROP_REGISTRY
        if koppen_zone is None:
            return 0.5

        affinity = KOPPEN_CROP_AFFINITY.get(crop_code)
        if affinity is not None:
            return affinity.get(koppen_zone, 0.2)

        # Fallback to architecture-level defaults
        crop = CROP_REGISTRY.get(crop_code)
        arch = crop.architecture if crop else "cereal"
        arch_defaults = {
            "cereal":       {"Csa": 0.9, "Csb": 0.8, "BSk": 0.7, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.7, "Cfb": 0.7, "Dfa": 0.6},
            "maize":        {"Csa": 0.7, "Csb": 0.6, "BSk": 0.4, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.9, "Cfb": 0.7, "Dfa": 0.8},
            "rice":         {"Csa": 0.4, "Csb": 0.2, "BSk": 0.1, "BSh": 0.2, "BWh": 0.3, "Cfa": 0.8, "Cfb": 0.3, "Dfa": 0.5, "Aw": 0.9, "Af": 1.0},
            "legume":       {"Csa": 0.9, "Csb": 0.7, "BSk": 0.7, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.5, "Cfb": 0.5, "Dfa": 0.4},
            "vegetable":    {"Csa": 0.7, "Csb": 0.8, "BSk": 0.4, "BSh": 0.4, "BWh": 0.3, "Cfa": 0.7, "Cfb": 0.8, "Dfa": 0.6},
            "perennial":    {"Csa": 0.9, "Csb": 0.7, "BSk": 0.5, "BSh": 0.4, "BWh": 0.3, "Cfa": 0.5, "Cfb": 0.4, "Dfa": 0.3},
            "cotton":       {"Csa": 0.7, "Csb": 0.4, "BSk": 0.4, "BSh": 0.7, "BWh": 0.5, "Cfa": 0.9, "Cfb": 0.2, "Dfa": 0.5},
            "tropical_tree":{"Csa": 0.05, "Csb": 0.02, "BSk": 0.01, "BSh": 0.15, "BWh": 0.10, "Cfa": 0.3, "Cfb": 0.02, "Dfa": 0.01, "Aw": 0.9, "Af": 1.0},
        }
        return arch_defaults.get(arch, {}).get(koppen_zone, 0.2)

    def _score_aridity(
        self, crop_code: str,
        mean_temp_c: Optional[float],
        irrigation_type: Optional[str],
        annual_rainfall_mm: Optional[float] = None,
        et0_mm: Optional[float] = None,
    ) -> float:
        """Score crop feasibility based on estimated aridity."""
        from layer2_veg_int.crop_science_data import ARIDITY_CROP_THRESHOLDS
        from crop_database import CROP_REGISTRY
        
        crop = CROP_REGISTRY.get(crop_code)
        if not crop:
            return 0.5

        is_irrigated = irrigation_type and irrigation_type.upper() in ("DRIP", "PIVOT", "SPRINKLER", "FLOOD")

        # 1. Check crop-specific thresholds
        thresholds = ARIDITY_CROP_THRESHOLDS.get(crop_code)
        if thresholds is None:
            wn = crop.water_needs
            if is_irrigated:
                return 0.7
            if wn == "low":
                return 0.8
            elif wn == "medium":
                return 0.6
            else:
                return 0.3

        min_idm, ideal_idm = thresholds

        if is_irrigated:
            if mean_temp_c is not None and crop.optimal_temp_min <= mean_temp_c <= crop.optimal_temp_max:
                return 0.9
            return 0.6

        # 2. Non-irrigated: calculate de Martonne index
        if annual_rainfall_mm is not None and et0_mm is not None:
            aridity_index = annual_rainfall_mm / max(1.0, et0_mm)
            estimated_idm = aridity_index * 40.0
        elif annual_rainfall_mm is not None and mean_temp_c is not None:
            estimated_idm = annual_rainfall_mm / max(1.0, mean_temp_c + 10.0)
        elif mean_temp_c is not None:
            estimated_idm = max(5.0, 40.0 - mean_temp_c)
        else:
            return 0.5

        if estimated_idm >= min_idm:
            closeness = min(1.0, (estimated_idm - min_idm) / max(1.0, ideal_idm - min_idm))
            return 0.5 + 0.5 * closeness
        else:
            return max(0.05, 0.5 * (estimated_idm / max(1.0, min_idm)))

    def _check_region_compat(self, crop_code: str, koppen_zone: Optional[str]) -> bool:
        """Check region compatibility maps."""
        from crop_database import CROP_REGISTRY
        if not koppen_zone:
            return True
        crop = CROP_REGISTRY.get(crop_code)
        if not crop:
            return True

        koppen_region_map = {
            "Csa": {"mediterranean", "mena"},
            "Csb": {"mediterranean", "temperate"},
            "BSk": {"semi_arid", "mena"},
            "BSh": {"semi_arid", "arid", "mena"},
            "BWh": {"arid", "mena"},
            "Cfa": {"temperate", "subtropical"},
            "Cfb": {"temperate"},
            "Dfa": {"temperate", "cold_continental"},
        }
        possible_regions = koppen_region_map.get(koppen_zone, set())
        if not possible_regions:
            return True

        crop_regions = {r.lower() for r in getattr(crop, "regions", [])}
        if not crop_regions:
            return True

        return bool(crop_regions.intersection(possible_regions))

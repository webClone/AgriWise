"""
Crop Intelligence v6.0B — Label Package.

Provides label schema, storage, quality scoring, and dataset builder for the
crop-cycle feedback system. Farmer/admin confirmations remain audit feedback;
only independently verified, lineage-complete labels can enter training.

MongoDB collection ``ConfirmedCropLabel`` is the audit-record source of truth.
Prisma defines the frontend/admin schema.
Python reads/writes the same collection via PyMongo and maps
documents into dataclasses.
"""

from .label_schema import (
    CropLabel,
    LabelQualityScore,
    LabeledSample,
    DatasetSummary,
    get_hierarchy_targets,
    validate_crop_code,
    validate_label_source,
    canonicalize_geometry_hash,
    ALLOWED_LABEL_SOURCES,
    TRAINING_ELIGIBLE_LABEL_SOURCES,
    LABEL_SCHEMA_VERSION,
    FEATURE_VECTOR_VERSION,
)
from .label_store import LabelStoreBase, InMemoryLabelStore, MongoLabelStore
from .label_quality import compute_label_quality
from .dataset_builder import TrainingDatasetBuilder
from .classifier import HierarchicalCropClassifier
from .evaluator import CropModelEvaluator

__all__ = [
    "CropLabel",
    "LabelQualityScore",
    "LabeledSample",
    "DatasetSummary",
    "get_hierarchy_targets",
    "validate_crop_code",
    "validate_label_source",
    "canonicalize_geometry_hash",
    "ALLOWED_LABEL_SOURCES",
    "TRAINING_ELIGIBLE_LABEL_SOURCES",
    "LABEL_SCHEMA_VERSION",
    "FEATURE_VECTOR_VERSION",
    "LabelStoreBase",
    "InMemoryLabelStore",
    "MongoLabelStore",
    "compute_label_quality",
    "TrainingDatasetBuilder",
    "HierarchicalCropClassifier",
    "CropModelEvaluator",
]

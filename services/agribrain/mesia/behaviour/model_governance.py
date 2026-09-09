"""MESIA Model Governance, Cards & Lifecycle Registry — R6 §9.8 / P7.9.

Maintains model cards, training data split manifests, authority records,
and versioned capability limitations for all ML and physical inference models.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ModelCard:
    """Standardized model card defining capabilities, bounds, and limitations."""

    model_id: str
    model_name: str
    version: str
    target_radio_family: str
    physical_primitive: str
    training_dataset_ref: str
    evaluation_split_hash: str
    intended_use: str
    prohibited_uses: List[str]
    calibrated_uncertainty_range: Dict[str, float]
    known_limitations: List[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def content_hash(self) -> str:
        d = {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "version": self.version,
            "target_radio_family": self.target_radio_family,
            "physical_primitive": self.physical_primitive,
            "training_dataset_ref": self.training_dataset_ref,
            "evaluation_split_hash": self.evaluation_split_hash,
            "intended_use": self.intended_use,
            "prohibited_uses": self.prohibited_uses,
            "calibrated_uncertainty_range": self.calibrated_uncertainty_range,
            "known_limitations": self.known_limitations,
            "created_at": self.created_at.isoformat(),
        }
        raw = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

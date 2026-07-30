from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

ALLOWED_SOURCE_TYPES = {
    "farmer_observation",
    "agronomist_observation",
    "field_scout",
    "soil_lab",
    "sensor_reading",
    "drone_image",
    "farmer_photo",
    "irrigation_log",
    "harvest_record",
    "insurance_inspection",
}

ALLOWED_TARGET_VARIABLES = {
    "vigor",
    "canopy_water",
    "salinity_stress",
    "biotic_confounder",
    "crop_stage",
    "yield_observed",
    "irrigation_event",
    "harvest_event",
}

ALLOWED_SPATIAL_SCOPES = {
    "point",
    "zone",
    "plot",
    "farm",
}

ALLOWED_TEMPORAL_SCOPES = {
    "instant",
    "daily",
    "weekly",
    "season",
}

ALLOWED_VALIDATOR_ROLES = {
    "farmer",
    "agronomist",
    "admin",
    "sensor",
    "lab",
    "drone",
    "system",
}

@dataclass
class ValidationEvent:
    event_id: str
    plot_id: str
    geometry_hash: str
    event_time: str
    source_type: str
    target_variable: str
    observed_value: Any
    spatial_scope: str
    temporal_scope: str
    confidence: float
    validator_role: str
    run_id: Optional[str] = None
    zone_id: Optional[str] = None
    observed_unit: Optional[str] = None
    trust_weight: float = 0.0
    evidence_hash: str = ""
    attachment_refs: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    created_at: str = ""
    event_hash: str = ""

    def __post_init__(self):
        # 0. Validate confidence range
        if self.confidence is None or not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")

        # 1. Plot and geometry hash validation
        if not self.plot_id or not self.plot_id.strip():
            raise ValueError("plot_id is required.")
        if not self.geometry_hash or not self.geometry_hash.strip():
            raise ValueError("geometry_hash is required.")

        # 2. Reject Layer 8 and visual-only ASMAE sources/roles
        if self.source_type in ["layer8", "layer8_action"] or self.validator_role == "layer8":
            raise ValueError("Layer 8 actions cannot create validation events.")
        if self.source_type == "visual_only_asmae" or "visual_only" in str(self.notes or ""):
            raise ValueError("Visual-only ASMAE cannot create validation events.")

        # 3. Validation of allowed source types, spatial scope, validator role, etc.
        if self.source_type not in ALLOWED_SOURCE_TYPES:
            raise ValueError(f"Unknown source type: {self.source_type}")
        if self.target_variable not in ALLOWED_TARGET_VARIABLES:
            raise ValueError(f"Unknown target variable: {self.target_variable}")
        if self.spatial_scope not in ALLOWED_SPATIAL_SCOPES:
            raise ValueError("spatial_scope is required.")
        if self.temporal_scope not in ALLOWED_TEMPORAL_SCOPES:
            raise ValueError("temporal_scope is required.")
        if self.validator_role not in ALLOWED_VALIDATOR_ROLES:
            raise ValueError(f"Unknown validator role: {self.validator_role}")

        # 4. Hash checks: evidence_hash is required for external evidence with attachments
        is_external = self.source_type in ["soil_lab", "sensor_reading", "drone_image", "farmer_photo", "harvest_record"]
        # If it's external evidence, we require evidence_hash.
        if is_external and not self.evidence_hash.strip():
            raise ValueError(f"evidence_hash is required for external evidence type {self.source_type}")

        # 5. Calculate dynamic trust weight
        self.trust_weight = self.calculate_trust_weight()

        # 6. Generate event_hash (excluding event_hash itself to avoid recursion)
        if not self.event_hash:
            self.event_hash = self.generate_event_hash()

        if not self.created_at:
            from datetime import datetime, timezone
            self.created_at = datetime.now(timezone.utc).isoformat()

    def calculate_trust_weight(self) -> float:
        # Base source trust weights
        if self.source_type in ["soil_lab", "agronomist_observation", "harvest_record"]:
            base_weight = 0.9
        elif self.source_type in ["farmer_observation", "drone_image", "farmer_photo", "irrigation_log", "insurance_inspection"]:
            # If farmer photo is single, we can lower it to 0.3
            if self.source_type == "farmer_photo" and len(self.attachment_refs) <= 1:
                base_weight = 0.3
            # If farmer observation is single vague note without attachments, base_weight = 0.3
            elif self.source_type == "farmer_observation" and not self.attachment_refs:
                base_weight = 0.3
            else:
                base_weight = 0.7
        elif self.source_type == "sensor_reading":
            # Calibrated sensor vs uncalibrated sensor: we can check validator_role or notes
            if "uncalibrated" in str(self.notes or "").lower():
                base_weight = 0.3
            else:
                base_weight = 0.9 # Calibrated sensor reading
        else:
            base_weight = 0.3

        # Role factor
        role_factor = 1.0
        if self.validator_role == "agronomist":
            role_factor = 1.0
        elif self.validator_role == "lab":
            role_factor = 1.0
        elif self.validator_role == "farmer":
            role_factor = 0.8
        elif self.validator_role == "sensor":
            role_factor = 0.9
        elif self.validator_role == "system":
            role_factor = 0.7

        # Scope factor
        scope_factor = 1.0
        if self.spatial_scope == "plot":
            scope_factor = 1.0
        elif self.spatial_scope == "zone":
            scope_factor = 0.95
        elif self.spatial_scope == "point":
            scope_factor = 0.9
        elif self.spatial_scope == "farm":
            scope_factor = 0.8

        # Recency factor
        recency_factor = 1.0

        # Evidence quality factor
        evidence_quality_factor = 1.0
        if self.evidence_hash:
            evidence_quality_factor = 1.0
        elif self.attachment_refs:
            evidence_quality_factor = 0.9
        else:
            evidence_quality_factor = 0.8

        return round(base_weight * role_factor * scope_factor * recency_factor * evidence_quality_factor * self.confidence, 4)

    def generate_event_hash(self) -> str:
        d = asdict(self)
        d.pop("event_hash", None)
        serialized = json.dumps(d, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

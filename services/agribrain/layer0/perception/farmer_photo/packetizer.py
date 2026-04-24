"""
Farmer Photo — Packetizer.

Converts calibrated evidence into PerceptionVariables and then into
ObservationPackets via the shared packet_adapter.

Scope enforcement: ALL packets are geometry_scope="point".
A single photo cannot represent an entire field.

Double-counting prevention:
  A single photo emits AT MOST ONE stress observation into Kalman.
  disease_symptom_prob is the primary stress evidence (carries symptom
  class, severity, and disease candidate as metadata).
  local_stress_proxy is NOT packetized separately — its severity value
  is carried inside the disease_symptom_prob details.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..common.contracts import (
    PerceptionVariable,
    PerceptionEngineOutput,
    PerceptionEngineFamily,
)
from ..common.packet_adapter import to_observation_packets

from .calibrator import CalibratedEvidence
from .schemas import OrganClass, SymptomClass


class FarmerPhotoPacketizer:
    """
    Converts calibrated evidence into ObservationPackets.

    Rules:
      - geometry_scope = "point" for ALL outputs
      - non-field images produce zero packets
      - organ-invalid combinations are not emitted
      - all outputs carry sigma
      - ONE stress observation per photo (no double-counting)
      - phenology gated by organ + confidence
    """

    def packetize(
        self,
        evidence: CalibratedEvidence,
        qa_score: float,
        reliability_weight: float,
        sigma_inflation: float,
        plot_id: str = "",
        timestamp: Optional[datetime] = None,
        image_content_hash: str = "",
        processing_steps: Optional[List[str]] = None,
        qa_flags: Optional[List[str]] = None,
        scene_class: str = "",
        model_versions: Optional[Dict[str, str]] = None,
    ) -> Tuple[Optional[PerceptionEngineOutput], List]:
        """
        Convert calibrated evidence into ObservationPackets.

        Returns (None, []) list if the image is not a valid field image.
        """
        if not evidence.is_field:
            return None, []

        variables: List[PerceptionVariable] = []

        # --- Unified Soil / Weak Plant Suppression (D2.2D) ---
        # Hard suppress agronomic evidence (canopy, phenology, symptom) if ANY of:
        # 1. Scene is non-agricultural or explicitly soil
        # 2. Organ classifier landed on SOIL
        # 3. Plant visibility is weak (confidence < 0.35)
        # Suppressed: local_canopy_cover, phenology_stage_est, disease_symptom_prob
        # May still emit: weak plant_identity_confidence (or nothing)
        is_hard_suppressed = (
            scene_class in ("soil_scene", "NON_FIELD", "UNUSABLE") or
            evidence.organ_class == OrganClass.SOIL or
            evidence.plant_identity_confidence < 0.35
        )

        # --- Local canopy cover (only if canopy-valid and not suppressed) ---
        if evidence.organ_class in (OrganClass.CANOPY, OrganClass.MIXED) and not is_hard_suppressed:
            variables.append(PerceptionVariable(
                name="local_canopy_cover",
                value=evidence.local_canopy_cover,
                sigma=evidence.canopy_cover_sigma,
                confidence=evidence.plant_identity_confidence,
                unit="fraction [0, 1]",
                details={"organ": evidence.organ_class},
            ))

        # --- Disease symptom probability ---
        if evidence.primary_symptom != SymptomClass.HEALTHY:
            variables.append(PerceptionVariable(
                name="disease_symptom_prob",
                value=evidence.disease_symptom_prob,
                sigma=evidence.disease_sigma,
                confidence=min(0.50, evidence.disease_candidate_confidence + 0.1),
                unit="probability [0, 1]",
                details={
                    "primary_symptom": evidence.primary_symptom,
                    "severity": evidence.local_symptom_score,
                    "disease_candidate": evidence.disease_candidate,
                },
            ))

        # --- Local stress proxy: NOT packetized separately ---
        # Severity is carried as metadata inside disease_symptom_prob.
        # Emitting both would double-count stress from the same evidence.

        # --- Phenology hint (gated by organ + plant confidence) ---
        phenology_valid_organs = {
            OrganClass.CANOPY, OrganClass.LEAF,
            OrganClass.FRUIT, OrganClass.MIXED,
        }
        if not is_hard_suppressed and evidence.organ_class in phenology_valid_organs:
            variables.append(PerceptionVariable(
                name="phenology_stage_est",
                value=evidence.phenology_stage_est,
                sigma=evidence.phenology_sigma,
                confidence=min(0.35, evidence.plant_identity_confidence * 0.6),
                unit="stage_float [0, 4]",
                details={"crop_class": evidence.crop_class},
            ))

        # --- Plant identity (auxiliary, not assimilated) ---
        variables.append(PerceptionVariable(
            name="plant_identity_confidence",
            value=evidence.plant_identity_confidence,
            sigma=0.20,
            confidence=evidence.crop_confidence,
            unit="confidence [0, 1]",
            details={
                "crop_class": evidence.crop_class,
                "organ_class": evidence.organ_class,
            },
        ))

        # --- Build engine output ---
        engine_output = PerceptionEngineOutput(
            engine_family=PerceptionEngineFamily.FARMER_PHOTO,
            plot_id=plot_id,
            timestamp=timestamp,
            geometry_scope="point",  # ENFORCED — never "plot"
            qa_score=qa_score,
            reliability_weight=reliability_weight,
            sigma_inflation=sigma_inflation,
            qa_flags=qa_flags or [],
            variables=variables,
            zone_outputs=[],  # No zone-level for farmer photo
            provenance_chain=processing_steps or [],
            model_versions=model_versions or {},
            image_content_hash=image_content_hash,
        )

        # --- Route through shared packet adapter ---
        packets = to_observation_packets(engine_output)
        return engine_output, packets

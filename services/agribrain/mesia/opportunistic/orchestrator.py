"""MESIA Opportunistic & Ambient Sensing Orchestrator — R6 §6.5 / P6.5.

Coordinates Signals of Opportunity (SoOP), passive bistatic reception, and
pure remote orbital reflectometry, outputting calibrated proposals for ASMAE assimilation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    AmbientOpportunityDescriptor,
    AmbientRadioFamily,
    BistaticForwardScatterObservation,
    GnssInterferometryObservation,
    PureRemoteObservation,
    SensingModality,
)
from .gnss_reflectometry import GnssReflectometrySolver
from .cellular_downlink import CellularDownlinkCorrelator
from .broadcast_uhf import BroadcastUhfEngine
from .spaceborne_gnssr import SpaceborneGnssrEngine
from .cml_backhaul import CommercialMicrowaveLinkEngine
from ..contracts.behaviour import BehaviourLikelihood
from ..assimilation.asmae_operator import ASMAEInnovationProposal, ASMAEObservationOperator


class OpportunisticSensingOrchestrator:
    """Orchestrates multi-source ambient RF sensing across all operational modalities."""

    def __init__(self, plot_id: str, modality: SensingModality = SensingModality.PURE_REMOTE_ORBITAL):
        self.plot_id = plot_id
        self.modality = modality
        self._catalog: Dict[str, AmbientOpportunityDescriptor] = {}

    def register_ambient_source(self, descriptor: AmbientOpportunityDescriptor) -> None:
        """Registers a known ambient source of opportunity."""
        self._catalog[descriptor.source_id] = descriptor

    def process_gnss_ir_observation(
        self,
        observation: GnssInterferometryObservation,
        prior_state_vwc: float = 0.20,
    ) -> ASMAEInnovationProposal:
        """Translates ground-based GNSS-IR multipath into an ASMAE innovation proposal."""
        now = datetime.now(timezone.utc)
        innovation = observation.estimated_vwc - prior_state_vwc

        return ASMAEInnovationProposal(
            proposal_id=f"innov-gnssir-{observation.observation_id}",
            target_state_variable="root_zone_water",
            microzone_id=f"{self.plot_id}_SECTOR_GNSS",
            depth_stratum="ROOT_ZONE_5_30CM",
            innovation_value=round(innovation, 4),
            observation_variance=round(observation.observation_variance, 6),
            confidence_support=0.85,
            authority_scope="evidence_proposal",
            native_lineage_hash=observation.raw_nmea_hash,
            likelihood_ref=observation.observation_id,
            created_at=now,
        )

    def process_cellular_forward_scatter(
        self,
        observation: BistaticForwardScatterObservation,
        prior_canopy_water: float = 0.50,
    ) -> ASMAEInnovationProposal:
        """Translates passive cellular forward-scatter into an ASMAE canopy water innovation."""
        now = datetime.now(timezone.utc)
        innovation = observation.estimated_canopy_water_index - prior_canopy_water

        return ASMAEInnovationProposal(
            proposal_id=f"innov-cell-{observation.observation_id}",
            target_state_variable="canopy_water",
            microzone_id=f"{self.plot_id}_SECTOR_CELLULAR",
            depth_stratum="CANOPY_TOP",
            innovation_value=round(innovation, 4),
            observation_variance=round(observation.observation_variance, 6),
            confidence_support=0.80,
            authority_scope="evidence_proposal",
            native_lineage_hash=observation.native_iq_hash,
            likelihood_ref=observation.observation_id,
            created_at=now,
        )

    def process_pure_remote_observation(
        self,
        observation: PureRemoteObservation,
        prior_state_vwc: float = 0.20,
    ) -> ASMAEInnovationProposal:
        """Translates 100% pure remote spaceborne reflectometry into an ASMAE innovation."""
        now = datetime.now(timezone.utc)
        target_var = "surface_wetness_event" if observation.mission == "CML_TELECOM" else "root_zone_water"
        depth_stratum = "SURFACE_0_5CM" if observation.mission == "CML_TELECOM" else "ROOT_ZONE_5_30CM"
        innovation = observation.estimated_root_zone_vwc - prior_state_vwc

        raw_repr = f"{observation.mission}_{observation.external_granule_id}_{observation.timestamp.isoformat()}"
        raw_hash = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()

        return ASMAEInnovationProposal(
            proposal_id=f"innov-remote-{observation.observation_id}",
            target_state_variable=target_var,
            microzone_id=f"{self.plot_id}_ORBITAL_SPECULAR",
            depth_stratum=depth_stratum,
            innovation_value=round(innovation, 4),
            observation_variance=round(max(0.01, 1.0 - observation.confidence) * 0.1, 6),
            confidence_support=round(observation.confidence, 3),
            authority_scope="evidence_proposal",
            native_lineage_hash=raw_hash,
            likelihood_ref=observation.observation_id,
            created_at=now,
        )

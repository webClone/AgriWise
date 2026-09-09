"""ASMAE Observation Dispatcher — Layer 0.5 Observation Boundary / WP07 / Finding #14.

Receives, validates, and routes observation events from Layer 0, MESIA, and external sensors
into ASMAE's ensemble Kalman filter assimilation pipeline.
Generates durable abstention receipts when observations lack qualification or authority.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from .contracts import ObservationEvent
from ..state.authority import AuthorityVector
from services.agribrain.scientific_contracts.observation import ASMAEObservationPayload

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ObservationAbstentionReceipt:
    """Durable audit record documenting why an observation was abstained from state assimilation."""

    observation_id: str
    source_family: str
    reason: str
    timestamp: datetime
    raw_payload_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "source_family": self.source_family,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "raw_payload_ref": self.raw_payload_ref,
        }


class ASMAEObservationDispatcher:
    """Central observation routing and admission engine for ASMAE."""

    def __init__(self) -> None:
        self._pending_admitted: List[ObservationEvent] = []
        self._abstention_log: List[ObservationAbstentionReceipt] = []

    def dispatch_event(self, event: ObservationEvent) -> Dict[str, Any]:
        """Dispatch a validated ObservationEvent into ASMAE's assimilation pipeline."""
        now = datetime.now(timezone.utc)

        # Gate on authority: only update state if explicitly authorized
        if not event.authority.state_update_allowed:
            receipt = ObservationAbstentionReceipt(
                observation_id=event.observation_id,
                source_family=event.source_family,
                reason="Authority vector prohibits state_update: qualification unverified or in containment mode",
                timestamp=now,
                raw_payload_ref=event.spatial_support_ref,
            )
            self._abstention_log.append(receipt)
            return {
                "status": "abstained_uncalibrated",
                "observation_id": event.observation_id,
                "reason": receipt.reason,
                "receipt": receipt.to_dict(),
            }

        self._pending_admitted.append(event)
        logger.info("Admitted observation %s for ASMAE assimilation", event.observation_id)
        return {
            "status": "admitted_for_assimilation",
            "observation_id": event.observation_id,
            "source_family": event.source_family,
            "queue_position": len(self._pending_admitted),
        }

    def dispatch_payload(self, payload: ASMAEObservationPayload) -> Dict[str, Any]:
        """Convert a strongly-typed ASMAEObservationPayload into an ObservationEvent and dispatch."""
        now = datetime.now(timezone.utc)
        is_calibrated = bool(payload.calibration_certificate_id and payload.calibration_certificate_id.strip())

        authority = AuthorityVector(
            visualization_allowed=True,
            state_update_allowed=is_calibrated,
            diagnosis_allowed=True,
        )

        event = ObservationEvent(
            observation_id=payload.observation_id,
            source_family=f"MESIA_{payload.target_state_variable.upper()}",
            sensor_id=f"mesia_{payload.microzone_id}",
            acquisition_time=payload.knowledge_cutoff,
            valid_time=now,
            spatial_support_ref=f"microzone:{payload.microzone_id}:{payload.depth_stratum}",
            quality_ref=f"var:{payload.observation_variance:.4f}",
            observation_operator_ref=payload.forward_operator_id,
            uncertainty_model_ref="gum_metrology_budget",
            authority=authority,
            provider="MESIA_OBSERVATORY",
            processing_level="CALIBRATED_PHYSICAL_INVERSION" if is_calibrated else "UNQUALIFIED_PROPOSAL",
        )
        return self.dispatch_event(event)

    def get_pending_observations(self) -> List[ObservationEvent]:
        """Return all admitted observations awaiting Kalman filter update."""
        return list(self._pending_admitted)

    def get_abstention_receipts(self) -> List[ObservationAbstentionReceipt]:
        """Return all durable abstention receipts recorded during this session."""
        return list(self._abstention_log)

    def clear(self) -> None:
        """Clear the pending admission queue and abstention logs."""
        self._pending_admitted.clear()
        self._abstention_log.clear()

"""MESIA Central Epoch Authority & Lifecycle Registry — R6 §6.4–§6.7.

Maintains active Geometry, Instrument, Network, Coexistence, Calibration,
and Software Model epochs across all observatory receiver nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.epochs import (
    GeometryEpoch,
    InstrumentEpoch,
    NetworkEpoch,
    CoexistenceEpoch,
    CalibrationState,
    SoftwareModelEpoch,
)


@dataclass
class ReceiverActiveEpochState:
    """The current active epoch set for a single receiver."""
    receiver_id: str
    active_geometry_epoch: Optional[GeometryEpoch] = None
    active_instrument_epoch: Optional[InstrumentEpoch] = None
    active_network_epoch: Optional[NetworkEpoch] = None
    active_coexistence_epoch: Optional[CoexistenceEpoch] = None
    active_calibration_state: Optional[CalibrationState] = None
    active_software_model_epoch: Optional[SoftwareModelEpoch] = None


class CentralEpochAuthority:
    """Central authority governing active epochs and lineage tracking."""

    def __init__(self) -> None:
        self._receiver_epochs: Dict[str, ReceiverActiveEpochState] = {}
        self._epoch_history: List[Any] = []

    def get_or_create_receiver_state(self, receiver_id: str) -> ReceiverActiveEpochState:
        if receiver_id not in self._receiver_epochs:
            self._receiver_epochs[receiver_id] = ReceiverActiveEpochState(receiver_id=receiver_id)
        return self._receiver_epochs[receiver_id]

    def update_geometry_epoch(self, receiver_id: str, new_epoch: GeometryEpoch) -> None:
        state = self.get_or_create_receiver_state(receiver_id)
        state.active_geometry_epoch = new_epoch
        self._epoch_history.append(new_epoch)

    def update_instrument_epoch(self, receiver_id: str, new_epoch: InstrumentEpoch) -> None:
        state = self.get_or_create_receiver_state(receiver_id)
        state.active_instrument_epoch = new_epoch
        self._epoch_history.append(new_epoch)

    def update_network_epoch(self, receiver_id: str, new_epoch: NetworkEpoch) -> None:
        state = self.get_or_create_receiver_state(receiver_id)
        state.active_network_epoch = new_epoch
        self._epoch_history.append(new_epoch)

    def update_coexistence_epoch(self, receiver_id: str, new_epoch: CoexistenceEpoch) -> None:
        state = self.get_or_create_receiver_state(receiver_id)
        state.active_coexistence_epoch = new_epoch
        self._epoch_history.append(new_epoch)

    def update_calibration_state(self, receiver_id: str, new_state: CalibrationState) -> None:
        state = self.get_or_create_receiver_state(receiver_id)
        state.active_calibration_state = new_state
        self._epoch_history.append(new_state)

    def update_software_model_epoch(self, receiver_id: str, new_epoch: SoftwareModelEpoch) -> None:
        state = self.get_or_create_receiver_state(receiver_id)
        state.active_software_model_epoch = new_epoch
        self._epoch_history.append(new_epoch)

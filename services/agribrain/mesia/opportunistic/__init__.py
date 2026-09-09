"""MESIA Opportunistic & Signals of Opportunity (SoOP) Sensing Subsystem — R6 §6.5.

Re-exports typed contracts and physical solvers for ambient radio wave sensing.
"""

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
from .orchestrator import OpportunisticSensingOrchestrator

__all__ = [
    "SensingModality",
    "AmbientRadioFamily",
    "AmbientOpportunityDescriptor",
    "GnssInterferometryObservation",
    "BistaticForwardScatterObservation",
    "PureRemoteObservation",
    "GnssReflectometrySolver",
    "CellularDownlinkCorrelator",
    "BroadcastUhfEngine",
    "SpaceborneGnssrEngine",
    "CommercialMicrowaveLinkEngine",
    "OpportunisticSensingOrchestrator",
]

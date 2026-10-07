"""
Layer 3.0 Water Intelligence Contracts Package
Canonical data contracts, factories, and transition DAG for soil-plant-atmosphere water state estimation.
"""

from layer3_water.contracts.authority import WaterPhysicsAuthority, HydrologyMode, SolverFidelity
from layer3_water.contracts.water_uncertainty import WaterUncertaintyBudget, WaterPhysicsConfidence
from layer3_water.contracts.atmospheric_state import (
    HumiditySourceType,
    RadiationSourceType,
    WindSourceType,
    TemperatureSourceType,
    AtmosphericInputQuality,
    CanopyTemperatureState,
)
from layer3_water.contracts.assimilation_state import (
    WaterSignalType,
    SoilObservationVector,
    Layer3ToLayer2Receipt,
    Layer3HydrologicalConstraintReceipt,
    Layer3ToLayer4BoundaryReceipt,
)
from layer3_water.contracts.irrigation_state import (
    IrrigationMethod,
    WaterDecisionAction,
    WaterDecisionUrgency,
    IrrigationEvent,
    IrrigationConstraints,
    IrrigationObjective,
    WaterDecision,
)
from layer3_water.contracts.water_state import (
    InfiltrationState,
    SoilEvaporationState,
    SoilWaterState,
    PotentialWaterFlux,
    ActualWaterFlux,
    WaterFluxState,
    RootZoneWaterState,
    WaterLimitationForecast,
    HydraulicStressMemoryState,
    AssimilationDiagnostic,
    IntervalFluxReceipt,
    AnalysisIncrementReceipt,
    WaterState,
)
from layer3_water.contracts.state_factory import WaterStateFactory
from layer3_water.contracts.transition_graph import (
    WaterProcessStage,
    ProcessStepDependency,
    Layer3WaterTransitionGraph,
)

__all__ = [
    "WaterPhysicsAuthority",
    "HydrologyMode",
    "SolverFidelity",
    "WaterUncertaintyBudget",
    "WaterPhysicsConfidence",
    "HumiditySourceType",
    "RadiationSourceType",
    "WindSourceType",
    "TemperatureSourceType",
    "AtmosphericInputQuality",
    "CanopyTemperatureState",
    "WaterSignalType",
    "SoilObservationVector",
    "Layer3ToLayer2Receipt",
    "Layer3HydrologicalConstraintReceipt",
    "Layer3ToLayer4BoundaryReceipt",
    "IrrigationMethod",
    "WaterDecisionAction",
    "WaterDecisionUrgency",
    "IrrigationEvent",
    "IrrigationConstraints",
    "IrrigationObjective",
    "WaterDecision",
    "InfiltrationState",
    "SoilEvaporationState",
    "SoilWaterState",
    "PotentialWaterFlux",
    "ActualWaterFlux",
    "WaterFluxState",
    "RootZoneWaterState",
    "WaterLimitationForecast",
    "HydraulicStressMemoryState",
    "AssimilationDiagnostic",
    "IntervalFluxReceipt",
    "AnalysisIncrementReceipt",
    "WaterState",
    "WaterStateFactory",
    "WaterProcessStage",
    "ProcessStepDependency",
    "Layer3WaterTransitionGraph",
]

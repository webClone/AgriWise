"""
Layer 3.0 Water Intelligence Process Transition Graph
Formally defines the directed acyclic dependency structure for Layer 3 simulation, assimilation, and optimization.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Set


class WaterProcessStage(str, Enum):
    """Stages of the Layer 3 water intelligence computation pipeline."""
    INPUT_INGESTION = "INPUT_INGESTION"                   # Ingest weather, management, soil properties, sensors, and L2 receipt
    SOLVER_SELECTION = "SOLVER_SELECTION"                 # Adaptive solver fidelity selection (Bucket vs Richards)
    ATMOSPHERIC_DEMAND = "ATMOSPHERIC_DEMAND"             # Penman-Monteith ET0 with atmospheric quality hierarchy
    CANOPY_DEMAND_PARTITIONING = "CANOPY_DEMAND_PARTITIONING" # Dual Kc (Kcb, Ke) from Layer 2 canopy structure
    ROOT_ZONE_AVAILABILITY = "ROOT_ZONE_AVAILABILITY"     # Zr, TAW, RAW, depletion Dr, and stress reduction Ks
    SOIL_WATER_BALANCE = "SOIL_WATER_BALANCE"             # Layered soil moisture update and mass conservation
    DATA_ASSIMILATION = "DATA_ASSIMILATION"               # Optimal Interpolation / EnKF observation update (X^+ = X^- + K(y - HX^-))
    ACTUAL_FLUX_PARTITIONING = "ACTUAL_FLUX_PARTITIONING" # Realized ETa, Tact, Esact, and Tdeficit
    HYDRAULIC_STRESS_MEMORY = "HYDRAULIC_STRESS_MEMORY"   # Historical stress accumulation and recovery rate tracking
    LIMITATION_FORECAST = "LIMITATION_FORECAST"           # Probabilistic trajectory across weather ensemble
    DECISION_OPTIMIZATION = "DECISION_OPTIMIZATION"       # MPC prescriptive irrigation optimization
    L2_FEEDBACK_SYNTHESIS = "L2_FEEDBACK_SYNTHESIS"       # Hydrological boundary constraints for L2/L4


@dataclass(frozen=True)
class ProcessStepDependency:
    """Directed execution edge between two process stages."""
    stage: WaterProcessStage
    required_inputs: Set[str]
    produced_outputs: Set[str]
    preceding_stages: List[WaterProcessStage]


class Layer3WaterTransitionGraph:
    """Formal DAG governing Layer 3 execution sequence and validation."""

    PIPELINE_DEPENDENCIES: Dict[WaterProcessStage, ProcessStepDependency] = {
        WaterProcessStage.INPUT_INGESTION: ProcessStepDependency(
            stage=WaterProcessStage.INPUT_INGESTION,
            required_inputs={"weather_data", "soil_profile_data", "l2_vegetation_state"},
            produced_outputs={"validated_weather", "validated_soil", "l2_receipt"},
            preceding_stages=[],
        ),
        WaterProcessStage.SOLVER_SELECTION: ProcessStepDependency(
            stage=WaterProcessStage.SOLVER_SELECTION,
            required_inputs={"validated_soil"},
            produced_outputs={"hydrology_mode", "solver_fidelity"},
            preceding_stages=[WaterProcessStage.INPUT_INGESTION],
        ),
        WaterProcessStage.ATMOSPHERIC_DEMAND: ProcessStepDependency(
            stage=WaterProcessStage.ATMOSPHERIC_DEMAND,
            required_inputs={"validated_weather"},
            produced_outputs={"et0_mm", "atmospheric_quality"},
            preceding_stages=[WaterProcessStage.INPUT_INGESTION],
        ),
        WaterProcessStage.CANOPY_DEMAND_PARTITIONING: ProcessStepDependency(
            stage=WaterProcessStage.CANOPY_DEMAND_PARTITIONING,
            required_inputs={"et0_mm", "l2_receipt"},
            produced_outputs={"kcb", "ke", "etp_mm", "tpot_mm", "espot_mm"},
            preceding_stages=[WaterProcessStage.ATMOSPHERIC_DEMAND],
        ),
        WaterProcessStage.ROOT_ZONE_AVAILABILITY: ProcessStepDependency(
            stage=WaterProcessStage.ROOT_ZONE_AVAILABILITY,
            required_inputs={"validated_soil", "l2_receipt", "etp_mm"},
            produced_outputs={"taw_mm", "raw_mm", "dr_mm", "ks"},
            preceding_stages=[WaterProcessStage.CANOPY_DEMAND_PARTITIONING],
        ),
        WaterProcessStage.SOIL_WATER_BALANCE: ProcessStepDependency(
            stage=WaterProcessStage.SOIL_WATER_BALANCE,
            required_inputs={"validated_soil", "validated_weather", "ks", "etp_mm"},
            produced_outputs={"theta_prior_profile", "deep_drainage_mm", "runoff_mm"},
            preceding_stages=[WaterProcessStage.ROOT_ZONE_AVAILABILITY],
        ),
        WaterProcessStage.DATA_ASSIMILATION: ProcessStepDependency(
            stage=WaterProcessStage.DATA_ASSIMILATION,
            required_inputs={"theta_prior_profile"},
            produced_outputs={"theta_posterior_profile", "assimilation_diagnostic"},
            preceding_stages=[WaterProcessStage.SOIL_WATER_BALANCE],
        ),
        WaterProcessStage.ACTUAL_FLUX_PARTITIONING: ProcessStepDependency(
            stage=WaterProcessStage.ACTUAL_FLUX_PARTITIONING,
            required_inputs={"ks", "tpot_mm", "espot_mm", "theta_posterior_profile"},
            produced_outputs={"eta_mm", "tact_mm", "esact_mm", "tdeficit_mm"},
            preceding_stages=[WaterProcessStage.DATA_ASSIMILATION],
        ),
        WaterProcessStage.HYDRAULIC_STRESS_MEMORY: ProcessStepDependency(
            stage=WaterProcessStage.HYDRAULIC_STRESS_MEMORY,
            required_inputs={"ks", "tdeficit_mm"},
            produced_outputs={"hydraulic_stress_memory"},
            preceding_stages=[WaterProcessStage.ACTUAL_FLUX_PARTITIONING],
        ),
        WaterProcessStage.LIMITATION_FORECAST: ProcessStepDependency(
            stage=WaterProcessStage.LIMITATION_FORECAST,
            required_inputs={"theta_posterior_profile", "taw_mm", "raw_mm", "weather_ensemble"},
            produced_outputs={"water_limitation_forecast"},
            preceding_stages=[WaterProcessStage.ACTUAL_FLUX_PARTITIONING],
        ),
        WaterProcessStage.DECISION_OPTIMIZATION: ProcessStepDependency(
            stage=WaterProcessStage.DECISION_OPTIMIZATION,
            required_inputs={"water_limitation_forecast", "irrigation_constraints", "irrigation_objective"},
            produced_outputs={"water_decision"},
            preceding_stages=[WaterProcessStage.LIMITATION_FORECAST],
        ),
        WaterProcessStage.L2_FEEDBACK_SYNTHESIS: ProcessStepDependency(
            stage=WaterProcessStage.L2_FEEDBACK_SYNTHESIS,
            required_inputs={"tact_mm", "tdeficit_mm", "ks", "theta_posterior_profile", "hydraulic_stress_memory"},
            produced_outputs={"hydrological_constraint_receipt"},
            preceding_stages=[WaterProcessStage.HYDRAULIC_STRESS_MEMORY],
        ),
    }

    @classmethod
    def get_execution_order(cls) -> List[WaterProcessStage]:
        """Return topologically sorted list of process stages."""
        return [
            WaterProcessStage.INPUT_INGESTION,
            WaterProcessStage.SOLVER_SELECTION,
            WaterProcessStage.ATMOSPHERIC_DEMAND,
            WaterProcessStage.CANOPY_DEMAND_PARTITIONING,
            WaterProcessStage.ROOT_ZONE_AVAILABILITY,
            WaterProcessStage.SOIL_WATER_BALANCE,
            WaterProcessStage.DATA_ASSIMILATION,
            WaterProcessStage.ACTUAL_FLUX_PARTITIONING,
            WaterProcessStage.HYDRAULIC_STRESS_MEMORY,
            WaterProcessStage.LIMITATION_FORECAST,
            WaterProcessStage.DECISION_OPTIMIZATION,
            WaterProcessStage.L2_FEEDBACK_SYNTHESIS,
        ]

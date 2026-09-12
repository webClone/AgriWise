"""R6.0 / Phase Task P06.1: Agronomical World Model Contracts.

Formal mathematical contracts for:
1. AgronomicalStateVector: Soil hydrology (5 strata), crop biology, nutrients, and latent state.
2. EnvironmentalDisturbance: Meteorological and boundary conditions.
3. ActionVector: Interventions with 4-phase lifecycle (PROPOSED, SCHEDULED, COMPLETED, EXPOSED).
4. Physical conservation invariants: Water and nutrient mass balance constraints.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from services.agribrain.scientific_contracts.authority import SpatialSupport
from services.agribrain.scientific_contracts.contracts_v2 import InterventionLifecycleState
from services.agribrain.scientific_contracts.exceptions import ContractViolation


AGRONOMICAL_STATE_SCHEMA_VERSION = "agronomical_state_v1"
DISTURBANCE_SCHEMA_VERSION = "environmental_disturbance_v1"
ACTION_VECTOR_SCHEMA_VERSION = "action_vector_v1"

# Standard depth intervals for 5-stratum hydrology: 0-10, 10-20, 20-40, 40-60, 60-100 cm
SOIL_STRATA_DEPTHS_CM: Tuple[Tuple[float, float], ...] = (
    (0.0, 10.0),
    (10.0, 20.0),
    (20.0, 40.0),
    (40.0, 60.0),
    (60.0, 100.0),
)


@dataclass(frozen=True)
class AgronomicalStateVector:
    """Formal Agronomical World Model State Vector s_t (P06.1).

    Tracks 5-stratum soil hydrology, soil temperature, crop phenology,
    dry biomass, mineral nutrients, and latent disease pressure.
    """

    plot_id: str
    timestamp: datetime

    # Soil Hydrology (5 discrete strata: 0-10, 10-20, 20-40, 40-60, 60-100 cm) in m3/m3
    soil_vwc_profile: Tuple[float, float, float, float, float]

    # Soil Temperature (5 discrete strata) in °C
    soil_temperature_c: Tuple[float, float, float, float, float]

    # Crop Biology
    crop_growth_stage_code: str  # BBCH or Zadoks scale code, e.g. "BBCH_65"
    cumulative_gdd_c: float  # [°C-days]
    fractional_canopy_cover: float  # [0.0, 1.0]
    leaf_area_index: float  # [m2/m2]
    root_depth_cm: float  # [cm]
    biomass_dry_matter_kg_ha: float  # [kg/ha]

    # Soil Nutrients
    mineral_n_topsoil_kg_ha: float  # [kg N/ha] (0-30 cm)
    mineral_n_subsoil_kg_ha: float  # [kg N/ha] (30-100 cm)

    # Latent Health / Pathogen Pressure
    foliar_pathogen_latent_spore_load: float  # [0.0, 1.0] normalized index

    # State Covariance Matrix (optional, for Kalman / ensemble representation)
    state_covariance: Optional[Tuple[Tuple[float, ...], ...]] = None

    schema_version: str = AGRONOMICAL_STATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.plot_id or not str(self.plot_id).strip():
            raise ContractViolation("AgronomicalStateVector requires non-blank plot_id")
        if not isinstance(self.timestamp, datetime):
            raise ContractViolation("AgronomicalStateVector requires datetime timestamp")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ContractViolation("AgronomicalStateVector timestamp must be timezone-aware UTC")

        # Check 5-stratum hydrology
        if len(self.soil_vwc_profile) != 5:
            raise ContractViolation(
                f"soil_vwc_profile must contain exactly 5 strata, got {len(self.soil_vwc_profile)}"
            )
        for i, vwc in enumerate(self.soil_vwc_profile):
            if not math.isfinite(vwc) or not (0.0 <= vwc <= 1.0):
                raise ContractViolation(
                    f"soil_vwc_profile stratum {i} ({SOIL_STRATA_DEPTHS_CM[i]}cm) "
                    f"must be in [0.0, 1.0] m3/m3, got {vwc}"
                )

        # Check 5-stratum temperature
        if len(self.soil_temperature_c) != 5:
            raise ContractViolation(
                f"soil_temperature_c must contain exactly 5 strata, got {len(self.soil_temperature_c)}"
            )
        for i, t in enumerate(self.soil_temperature_c):
            if not math.isfinite(t) or not (-50.0 <= t <= 80.0):
                raise ContractViolation(
                    f"soil_temperature_c stratum {i} must be in [-50.0, 80.0] °C, got {t}"
                )

        # Check canopy cover
        if not math.isfinite(self.fractional_canopy_cover) or not (0.0 <= self.fractional_canopy_cover <= 1.0):
            raise ContractViolation(
                f"fractional_canopy_cover must be in [0.0, 1.0], got {self.fractional_canopy_cover}"
            )

        # Check LAI, root depth, biomass
        if not math.isfinite(self.leaf_area_index) or self.leaf_area_index < 0.0:
            raise ContractViolation(f"leaf_area_index must be >= 0.0, got {self.leaf_area_index}")
        if not math.isfinite(self.root_depth_cm) or self.root_depth_cm < 0.0:
            raise ContractViolation(f"root_depth_cm must be >= 0.0, got {self.root_depth_cm}")
        if not math.isfinite(self.biomass_dry_matter_kg_ha) or self.biomass_dry_matter_kg_ha < 0.0:
            raise ContractViolation(
                f"biomass_dry_matter_kg_ha must be >= 0.0, got {self.biomass_dry_matter_kg_ha}"
            )

        # Check nutrients
        if not math.isfinite(self.mineral_n_topsoil_kg_ha) or self.mineral_n_topsoil_kg_ha < 0.0:
            raise ContractViolation(
                f"mineral_n_topsoil_kg_ha must be >= 0.0, got {self.mineral_n_topsoil_kg_ha}"
            )
        if not math.isfinite(self.mineral_n_subsoil_kg_ha) or self.mineral_n_subsoil_kg_ha < 0.0:
            raise ContractViolation(
                f"mineral_n_subsoil_kg_ha must be >= 0.0, got {self.mineral_n_subsoil_kg_ha}"
            )

        # Check pathogen pressure
        if not math.isfinite(self.foliar_pathogen_latent_spore_load) or not (
            0.0 <= self.foliar_pathogen_latent_spore_load <= 1.0
        ):
            raise ContractViolation(
                f"foliar_pathogen_latent_spore_load must be in [0.0, 1.0], got {self.foliar_pathogen_latent_spore_load}"
            )

    @property
    def total_soil_water_storage_mm(self) -> float:
        """Compute profile-integrated soil water storage in mm over 100 cm profile."""
        total_mm = 0.0
        for (z_top, z_bot), theta in zip(SOIL_STRATA_DEPTHS_CM, self.soil_vwc_profile):
            layer_thickness_mm = (z_bot - z_top) * 10.0  # cm to mm
            total_mm += theta * layer_thickness_mm
        return total_mm

    @property
    def total_mineral_n_kg_ha(self) -> float:
        """Total profile mineral nitrogen."""
        return self.mineral_n_topsoil_kg_ha + self.mineral_n_subsoil_kg_ha

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plot_id": self.plot_id,
            "timestamp": self.timestamp.isoformat(),
            "soil_vwc_profile": list(self.soil_vwc_profile),
            "soil_temperature_c": list(self.soil_temperature_c),
            "crop_growth_stage_code": self.crop_growth_stage_code,
            "cumulative_gdd_c": self.cumulative_gdd_c,
            "fractional_canopy_cover": self.fractional_canopy_cover,
            "leaf_area_index": self.leaf_area_index,
            "root_depth_cm": self.root_depth_cm,
            "biomass_dry_matter_kg_ha": self.biomass_dry_matter_kg_ha,
            "mineral_n_topsoil_kg_ha": self.mineral_n_topsoil_kg_ha,
            "mineral_n_subsoil_kg_ha": self.mineral_n_subsoil_kg_ha,
            "foliar_pathogen_latent_spore_load": self.foliar_pathogen_latent_spore_load,
            "total_soil_water_storage_mm": self.total_soil_water_storage_mm,
            "total_mineral_n_kg_ha": self.total_mineral_n_kg_ha,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class EnvironmentalDisturbance:
    """Boundary environmental and meteorological disturbance w_t (P06.1)."""

    timestamp: datetime
    precipitation_mm: float
    et0_mm: float
    solar_radiation_mj_m2: float
    temp_max_c: float
    temp_min_c: float
    wind_speed_m_s: float
    is_forecast: bool = False
    schema_version: str = DISTURBANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.timestamp, datetime):
            raise ContractViolation("EnvironmentalDisturbance requires datetime timestamp")
        if self.precipitation_mm < 0.0:
            raise ContractViolation(f"precipitation_mm must be >= 0.0, got {self.precipitation_mm}")
        if self.et0_mm < 0.0:
            raise ContractViolation(f"et0_mm must be >= 0.0, got {self.et0_mm}")
        if self.solar_radiation_mj_m2 < 0.0:
            raise ContractViolation(f"solar_radiation_mj_m2 must be >= 0.0, got {self.solar_radiation_mj_m2}")
        if self.temp_max_c < self.temp_min_c:
            raise ContractViolation(
                f"temp_max_c ({self.temp_max_c}) cannot be less than temp_min_c ({self.temp_min_c})"
            )
        if self.wind_speed_m_s < 0.0:
            raise ContractViolation(f"wind_speed_m_s must be >= 0.0, got {self.wind_speed_m_s}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "precipitation_mm": self.precipitation_mm,
            "et0_mm": self.et0_mm,
            "solar_radiation_mj_m2": self.solar_radiation_mj_m2,
            "temp_max_c": self.temp_max_c,
            "temp_min_c": self.temp_min_c,
            "wind_speed_m_s": self.wind_speed_m_s,
            "is_forecast": self.is_forecast,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class ActionVector:
    """Intervention action on the worldline with strict lifecycle tracking (P06.1)."""

    action_id: str
    action_type: str  # e.g., "IRRIGATION", "NITROGEN_FERTILIZATION", "FUNGICIDE_SPRAY"
    lifecycle_state: InterventionLifecycleState
    target_date: datetime
    rate: float
    units: str
    applied_efficiency: float = 1.0
    exposure_verified_at: Optional[datetime] = None
    spatial_extent: SpatialSupport = SpatialSupport.PLOT
    schema_version: str = ACTION_VECTOR_SCHEMA_VERSION
    actual_execution_timestamp: Optional[datetime] = None
    applied_rate: Optional[float] = None
    applied_units: Optional[str] = None
    as_applied_evidence_ids: Tuple[str, ...] = ()
    executor_device_id: Optional[str] = None
    spatial_footprint: Optional[Dict[str, Any]] = None
    exposure_confidence: float = 0.0
    application_status: str = "PLANNED"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.action_id or not str(self.action_id).strip():
            raise ContractViolation("ActionVector requires non-blank action_id")
        if not isinstance(self.lifecycle_state, InterventionLifecycleState):
            raise ContractViolation(f"lifecycle_state must be InterventionLifecycleState, got {type(self.lifecycle_state)}")
        if self.rate < 0.0:
            raise ContractViolation(f"rate must be >= 0.0, got {self.rate}")
        if not (0.0 <= self.applied_efficiency <= 1.0):
            raise ContractViolation(f"applied_efficiency must be in [0.0, 1.0], got {self.applied_efficiency}")

    def is_physically_realized(self) -> bool:
        """Returns True only if the action has progressed to completed execution or verified exposure."""
        return self.lifecycle_state in (InterventionLifecycleState.COMPLETED, InterventionLifecycleState.EXPOSED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "lifecycle_state": self.lifecycle_state.value,
            "target_date": self.target_date.isoformat(),
            "rate": self.rate,
            "units": self.units,
            "applied_efficiency": self.applied_efficiency,
            "exposure_verified_at": self.exposure_verified_at.isoformat() if self.exposure_verified_at else None,
            "spatial_extent": self.spatial_extent.value,
            "is_physically_realized": self.is_physically_realized(),
            "actual_execution_timestamp": self.actual_execution_timestamp.isoformat() if self.actual_execution_timestamp else None,
            "applied_rate": self.applied_rate,
            "applied_units": self.applied_units,
            "as_applied_evidence_ids": list(self.as_applied_evidence_ids),
            "executor_device_id": self.executor_device_id,
            "spatial_footprint": self.spatial_footprint,
            "exposure_confidence": self.exposure_confidence,
            "application_status": self.application_status,
            "schema_version": self.schema_version,
        }


def verify_water_balance_conservation(
    initial_storage_mm: float,
    final_storage_mm: float,
    precipitation_mm: float,
    irrigation_effective_mm: float,
    et_actual_mm: float,
    drainage_runoff_mm: float,
    tolerance_mm: float = 0.5,
) -> bool:
    """Verify physical water mass balance conservation:

    Delta Storage = Inflows (Precipitation + Irrigation) - Outflows (ET + Drainage/Runoff)
    """
    delta_storage = final_storage_mm - initial_storage_mm
    net_flux = (precipitation_mm + irrigation_effective_mm) - (et_actual_mm + drainage_runoff_mm)
    residual = abs(delta_storage - net_flux)

    if residual > tolerance_mm:
        raise ContractViolation(
            f"Physical water conservation violation: Delta Storage ({delta_storage:.2f}mm) != "
            f"Net Flux ({net_flux:.2f}mm), residual={residual:.2f}mm > tolerance={tolerance_mm:.2f}mm"
        )
    return True

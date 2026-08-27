"""
Layer 3.0 Water Uncertainty Budget Contract
Propagates four orthogonal sources of uncertainty across hydrological state estimation.
"""

from dataclasses import dataclass
import math
from layer3_water.contracts.authority import SolverFidelity


@dataclass(frozen=True)
class WaterUncertaintyBudget:
    """Four-component uncertainty budget for Layer 3 water state estimation.
    
    sigma_total = sqrt(sigma_sensor^2 + sigma_soil^2 + sigma_weather^2 + sigma_model^2)
    """
    sensor_sigma: float = 0.03       # Weather station, rain gauge, or flux tower sensor precision
    soil_sigma: float = 0.04         # Soil texture, retention parameter, and depth heterogeneity
    weather_sigma: float = 0.03      # Weather forecast ensemble divergence
    model_sigma: float = 0.03        # FAO-56 / process parameterization variance

    @property
    def total_sigma(self) -> float:
        """Quadrature sum representing standard error of estimation."""
        return round(
            math.sqrt(
                self.sensor_sigma**2
                + self.soil_sigma**2
                + self.weather_sigma**2
                + self.model_sigma**2
            ),
            4,
        )

    def to_dict(self) -> dict:
        return {
            "sensor_sigma": self.sensor_sigma,
            "soil_sigma": self.soil_sigma,
            "weather_sigma": self.weather_sigma,
            "model_sigma": self.model_sigma,
            "total_sigma": self.total_sigma,
        }


@dataclass(frozen=True)
class WaterPhysicsConfidence:
    """Multi-source confidence and numerical quality metric for hydrological state."""
    mass_balance_quality: float = 1.0          # Quality from mass closure error in [0.0, 1.0]
    solver_fidelity: SolverFidelity = SolverFidelity.EMPIRICAL_BUCKET
    soil_parameter_quality: float = 0.90       # Pedotransfer parameter confidence in [0.0, 1.0]
    weather_quality: float = 0.92              # Atmospheric provenance confidence in [0.0, 1.0]
    overall_water_confidence: float = 0.92     # Fused water state confidence in [0.0, 1.0]

    @classmethod
    def compute(
        cls,
        mass_balance_error_mm: float,
        solver_fidelity: SolverFidelity = SolverFidelity.EMPIRICAL_BUCKET,
        soil_quality: float = 0.90,
        weather_quality: float = 0.92,
    ) -> "WaterPhysicsConfidence":
        """Compute composite confidence incorporating mass closure degradation."""
        mb_qual = max(0.0, min(1.0, 1.0 - (mass_balance_error_mm / 0.50)))
        fidel_weight = 0.95 if solver_fidelity == SolverFidelity.HYDRAULIC_NUMERICAL else 0.88
        overall = round(mb_qual * 0.35 + fidel_weight * 0.25 + soil_quality * 0.20 + weather_quality * 0.20, 3)
        return cls(
            mass_balance_quality=round(mb_qual, 3),
            solver_fidelity=solver_fidelity,
            soil_parameter_quality=round(soil_quality, 3),
            weather_quality=round(weather_quality, 3),
            overall_water_confidence=overall,
        )

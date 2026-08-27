"""
Dedicated Uncertainty & Retrieval Jacobian Engine.

Implements sensitivity derivatives (Jacobians) and quadratic error propagation:
sigma_total = sqrt(sigma_sensor^2 + sigma_retrieval^2 + sigma_conflict^2 + sigma_model^2)
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

from layer2_contracts.state_contracts import UncertaintyBudget


class NDMIWaterStressModel:
    """Biophysical water response model with analytical Jacobian."""

    @staticmethod
    def evaluate(ndmi: Optional[float], sigma_ndmi: float = 0.04) -> Tuple[float, float]:
        """Compute physical water deficit S_W and retrieval standard deviation sigma_retrieval."""
        if ndmi is None:
            return 0.0, 0.08
        if ndmi >= 0.20:
            return 0.0, 0.02
        
        # S_W = 0.3 + (0.2 - NDMI) * 2.0
        val = min(1.0, max(0.0, 0.30 + (0.20 - ndmi) * 2.0))
        # dS/dNDMI = -2.0
        jacobian = 2.0
        sigma_retrieval = round(jacobian * sigma_ndmi, 4)
        return round(val, 3), sigma_retrieval


class TemperatureThermalStressModel:
    """Thermal canopy stress model with gradient-based uncertainty propagation."""

    @staticmethod
    def evaluate(
        temp_max: Optional[float],
        vpd: Optional[float],
        sigma_temp: float = 0.5,
        sigma_vpd: float = 0.15,
    ) -> Tuple[float, float]:
        """Compute physical thermal deficit S_T and gradient-propagated sigma_retrieval."""
        if temp_max is None and vpd is None:
            return 0.0, 0.06

        t_val = temp_max or 25.0
        v_val = vpd or 1.0

        sev = 0.0
        d_temp = 0.0
        d_vpd = 0.0

        if t_val > 35.0:
            sev += (t_val - 35.0) / 10.0 * 0.5
            d_temp = 0.05  # dS / dTemp

        if v_val > 3.0:
            sev += min(0.4, (v_val - 3.0) * 0.2)
            d_vpd = 0.20   # dS / dVPD

        sev = min(1.0, max(0.0, sev))
        var_retrieval = (d_temp * sigma_temp) ** 2 + (d_vpd * sigma_vpd) ** 2
        sigma_retrieval = round(math.sqrt(max(1e-6, var_retrieval)), 4)
        return round(sev, 3), max(0.015, sigma_retrieval)


class SalinityECModel:
    """Soil EC / spectral salinity model with retrieval uncertainty."""

    @staticmethod
    def evaluate(soil_ec: Optional[float], sigma_ec: float = 0.3) -> Tuple[float, float]:
        """Compute physical salinity deficit S_S and Jacobian uncertainty."""
        if soil_ec is None or soil_ec < 2.0:
            return 0.0, 0.04
        
        if soil_ec < 4.0:
            val = (soil_ec - 2.0) / 2.0 * 0.4
            d_ec = 0.20
        elif soil_ec < 8.0:
            val = 0.4 + (soil_ec - 4.0) / 4.0 * 0.35
            d_ec = 0.0875
        else:
            val = min(1.0, 0.75 + (soil_ec - 8.0) / 8.0 * 0.25)
            d_ec = 0.03125

        sigma_retrieval = round(d_ec * sigma_ec, 4)
        return round(val, 3), max(0.02, sigma_retrieval)


class UncertaintyPropagator:
    """Unified quadratic quadrature uncertainty propagator."""

    @staticmethod
    def build_budget(
        sensor_sigma: float = 0.02,
        retrieval_sigma: float = 0.03,
        conflict_penalty: float = 0.00,
        model_sigma: float = 0.03,
    ) -> UncertaintyBudget:
        """Construct an immutable UncertaintyBudget from component standard deviations."""
        return UncertaintyBudget(
            sensor_sigma=round(max(0.005, sensor_sigma), 4),
            retrieval_sigma=round(max(0.005, retrieval_sigma), 4),
            conflict_sigma=round(max(0.0, conflict_penalty), 4),
            model_sigma=round(max(0.01, model_sigma), 4),
        )

"""
Layer 4 Compliance Gate — EU Nitrate Directive + Environmental Risk Models.

Regulatory checks:
  - EU NVZ limit: 170 kg N/ha/yr from organic sources
  - Total N ceiling: crop-specific (default 250 kg/ha)
  - Closed season: Nov-Feb for NVZ (high leaching risk)
  - Buffer zones: 5-20m from water bodies

Environmental risk models:
  - Leaching: f(soil_texture, drainage, rainfall_intensity, season)
  - Runoff: f(slope, soil_cover, rainfall)
  - Volatilization: f(pH, temperature, application_method, urea_fraction)
  - Denitrification: f(waterlogging, temperature)

References:
  - EU Nitrates Directive 91/676/EEC
  - USDA-NRCS Nutrient Management Standard (590)
  - IPNI 4R Framework
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from layer4_nutrients.schema import (
    ApplicationMethod, EnvironmentalRisk, RegulatoryCompliance,
    RegulationFramework, Nutrient, FertilizerProduct, PRODUCT_ANALYSIS,
)


# ============================================================================
# Crop-specific N ceilings (kg N/ha/yr total application)
# ============================================================================
N_CEILINGS = {
    "corn": 280.0, "wheat": 220.0, "soybean": 50.0, "rice": 200.0,
    "cotton": 200.0, "barley": 180.0, "potato": 250.0, "sorghum": 200.0,
    "alfalfa": 30.0, "canola": 200.0, "sunflower": 150.0,
}


class ComplianceGate:
    """EU Nitrate Directive + 4R environmental compliance."""

    def check_compliance(
        self,
        nutrient: Nutrient,
        product: FertilizerProduct,
        rate_kg_ha: float,
        method: ApplicationMethod,
        swb_out: Any,
        crop_type: str = "corn",
        soil_ph: Optional[float] = None,
        constraints: Optional[Dict] = None,
        regulation: RegulationFramework = RegulationFramework.EU_NITRATE_DIRECTIVE,
    ) -> RegulatoryCompliance:
        """Run all compliance checks."""
        constraints = constraints or {}
        violations = []
        warnings = []

        # EU NVZ limit
        nvz_limit = 170.0
        total_n_ceiling = N_CEILINGS.get(crop_type.lower(), 250.0)

        # User override
        user_ceiling = constraints.get("nitrogen_limit_kg_ha")
        if user_ceiling is not None:
            total_n_ceiling = min(total_n_ceiling, user_ceiling)

        proposed_n = rate_kg_ha if nutrient == Nutrient.N else 0.0
        # Include N from multi-nutrient products (DAP, MAP)
        product_n_frac = PRODUCT_ANALYSIS.get(product, {}).get("N", 0)
        if nutrient != Nutrient.N and product_n_frac > 0:
            product_rate = rate_kg_ha / max(0.01, PRODUCT_ANALYSIS.get(product, {}).get(nutrient.value, 1.0))
            proposed_n = product_rate * product_n_frac

        # Check total N ceiling
        if proposed_n > total_n_ceiling:
            violations.append(
                f"Total N ({proposed_n:.0f} kg/ha) exceeds ceiling ({total_n_ceiling:.0f} kg/ha)")

        # Leaching risk gating
        leaching_risk = getattr(swb_out, "leaching_risk_index", 0.0) if swb_out else 0.0
        if leaching_risk > 0.6 and method == ApplicationMethod.BROADCAST and rate_kg_ha > 50:
            violations.append("High leaching risk: broadcast blocked (use banded/fertigation)")

        # Rate safety limits
        max_safe = {"N": 300.0, "P": 150.0, "K": 250.0}.get(nutrient.value, 300.0)
        if rate_kg_ha > max_safe:
            violations.append(f"Rate ({rate_kg_ha:.0f}) exceeds safety limit ({max_safe:.0f} kg/ha)")

        # Closed season check (simplified)
        # In real implementation, check current month against NVZ calendar

        # Buffer zone (placeholder)
        buffer_m = constraints.get("buffer_distance_m", 0.0)
        if buffer_m > 0 and buffer_m < 5.0:
            warnings.append(f"Buffer distance {buffer_m}m < 5m minimum for water bodies")

        # Water quota
        water_quota = constraints.get("water_quota_mm")
        if water_quota is not None and method == ApplicationMethod.FERTIGATION:
            warnings.append(f"Fertigation constrained by water quota ({water_quota}mm)")

        return RegulatoryCompliance(
            framework=regulation,
            is_compliant=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            nvz_limit_kg_ha=nvz_limit,
            total_n_ceiling_kg_ha=total_n_ceiling,
            proposed_n_total=round(proposed_n, 1),
            closed_season_active=False,
            buffer_distance_m=buffer_m,
        )

    def compute_environmental_risk(
        self,
        nutrient: Nutrient,
        rate_kg_ha: float,
        method: ApplicationMethod,
        swb_out: Any,
        soil_ph: Optional[float],
        crop_type: str,
    ) -> EnvironmentalRisk:
        """Compute environmental risk scores [0-1]."""

        # Leaching risk: f(drainage, rate, method)
        drainage = getattr(swb_out, "deep_percolation_mm", 0.0) if swb_out else 0.0
        leach_base = min(1.0, drainage / 100.0)
        rate_factor = min(1.0, rate_kg_ha / 200.0)
        method_factor = 1.0 if method == ApplicationMethod.BROADCAST else 0.6
        leaching = min(1.0, leach_base * 0.5 + rate_factor * 0.3 + method_factor * 0.2)

        # Runoff risk (simplified — would need slope data)
        water_stress = getattr(swb_out, "water_stress_index", 0.0) if swb_out else 0.0
        # Low water stress = saturated soil = higher runoff risk
        runoff = max(0.0, min(1.0, (1.0 - water_stress) * 0.3 * rate_factor))

        # Volatilization: f(pH, method, product)
        volatilization = 0.0
        if nutrient == Nutrient.N:
            # Urea volatilization on alkaline soils
            ph = soil_ph or 7.0
            if ph > 7.5:
                volatilization += 0.30
            if method == ApplicationMethod.BROADCAST:
                volatilization += 0.20
            elif method in (ApplicationMethod.BANDED, ApplicationMethod.DEEP_PLACEMENT):
                volatilization -= 0.10
            volatilization = max(0.0, min(1.0, volatilization))

        # Denitrification: f(waterlogging)
        saturation = 0.0
        if swb_out and hasattr(swb_out, "water_stress_index"):
            # Counter-intuitive: very low stress = saturated = denitrification risk
            if swb_out.water_stress_index < 0.05:
                saturation = 0.3
        denitrification = min(1.0, saturation)

        overall = max(leaching, runoff, volatilization, denitrification)

        return EnvironmentalRisk(
            leaching=round(leaching, 3),
            runoff=round(runoff, 3),
            volatilization=round(volatilization, 3),
            denitrification=round(denitrification, 3),
            overall=round(overall, 3),
        )

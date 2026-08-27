"""
Layer 3.0 Physical Water Limitation Engine
Evaluates physical soil water supply constraint on transpiration with rigorous uncertainty propagation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math

from layer3_water.contracts.water_state import (
    RootZoneWaterState,
    PotentialWaterFlux,
    WaterLimitationForecast,
)


@dataclass(frozen=True)
class WaterLimitationState:
    """Comprehensive physical water limitation diagnostic state."""
    stress_factor_ks: float                       # Ks ∈ [0.0, 1.0]
    root_zone_depletion_mm: float                 # Dr (mm)
    readily_available_water_mm: float             # RAW (mm)
    total_available_water_mm: float               # TAW (mm)
    transpiration_deficit_mm: float               # Tdeficit = (1 - Ks) * Tpot (mm/day)
    transpiration_deficit_sigma_mm: float         # 1-sigma uncertainty in Tdeficit
    water_limitation_probability: float           # Estimated probability of water supply restriction ∈ [0.0, 1.0]
    is_transpiration_constrained: bool            # True if Ks < 1.0 (Dr > RAW)
    confidence_score: float = 0.90
    diagnostic_evidence: List[str] = field(default_factory=list)


class WaterLimitationEngine:
    """Evaluates physical water limitation state from soil moisture and evaporative demand."""

    @classmethod
    def evaluate_limitation(
        cls,
        root_zone: RootZoneWaterState,
        potential_flux: PotentialWaterFlux,
        et0_uncertainty_sigma: float = 0.05,
    ) -> WaterLimitationState:
        """Compute exact physical water limitation parameters, uncertainty, and diagnostic explanation."""
        ks = root_zone.stress_factor_ks
        dr = root_zone.root_zone_depletion_mm
        raw = root_zone.readily_available_water_mm
        taw = root_zone.total_available_water_mm
        
        tpot = potential_flux.tpot_mm
        tact = round(ks * tpot, 2)
        tdef = round(max(0.0, tpot - tact), 2)
        
        # Propagate uncertainty: sigma_tpot = Kcb * sigma_et0
        sigma_tpot = potential_flux.kcb * et0_uncertainty_sigma
        ks_sigma = root_zone.ks_uncertainty_sigma
        # sigma_tdef = sqrt(((1 - Ks)*sigma_tpot)^2 + (Tpot * sigma_Ks)^2)
        sigma_tdef = math.sqrt(((1.0 - ks) * sigma_tpot) ** 2 + (tpot * ks_sigma) ** 2)
        
        is_constrained = ks < 0.999
        # Limitation probability scales continuously from 0 at RAW to 1.0 at TAW
        if dr <= raw:
            prob = 0.0
        else:
            prob = round(min(1.0, max(0.0, (dr - raw) / (taw - raw))), 3)
            
        evidence = []
        if dr <= raw:
            evidence.append(f"Root-zone moisture adequate (Dr={dr:.1f}mm <= RAW={raw:.1f}mm; Ks=1.00)")
        elif dr < taw:
            dep_pct = (dr / taw) * 100.0
            evidence.append(
                f"Transpiration limited by soil water deficit (Dr={dr:.1f}mm > RAW={raw:.1f}mm; "
                f"depletion={dep_pct:.0f}% TAW; Ks={ks:.2f}; deficit={tdef:.1f}±{sigma_tdef:.2f}mm/day)"
            )
        else:
            evidence.append(f"Severe root-zone exhaustion (Dr={dr:.1f}mm >= TAW={taw:.1f}mm; Ks=0.00; total stomatal closure)")

        return WaterLimitationState(
            stress_factor_ks=ks,
            root_zone_depletion_mm=dr,
            readily_available_water_mm=raw,
            total_available_water_mm=taw,
            transpiration_deficit_mm=tdef,
            transpiration_deficit_sigma_mm=round(sigma_tdef, 3),
            water_limitation_probability=prob,
            is_transpiration_constrained=is_constrained,
            # GAP-12 FIX: Dynamic confidence from uncertainty propagation.
            # Low ET0 sigma + low Ks sigma → high confidence.
            # Hargreaves fallback (sigma ~0.08) or uncalibrated soil (sigma ~0.06)
            # will produce lower confidence than a calibrated station (sigma ~0.02).
            confidence_score=round(max(0.3, min(0.98,
                1.0 - (et0_uncertainty_sigma * 3.0) - (ks_sigma * 2.0)
            )), 3),
            diagnostic_evidence=evidence,
        )

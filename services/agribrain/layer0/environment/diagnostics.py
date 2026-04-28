"""
Environmental Diagnostics.

Summarizes provider status, consensus disagreements, soil completeness,
forcing values used, and weak observation count.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.environment.schemas import ProcessForcing, WeakKalmanObservation
from layer0.environment.soilgrids.schemas import SoilGridsQAResult
from layer0.environment.fao.schemas import FAOQAResult
from layer0.environment.weather.schemas import WeatherConsensusDaily


def build_diagnostics(
    soilgrids_qa: Optional[SoilGridsQAResult] = None,
    fao_qa: Optional[FAOQAResult] = None,
    weather_qa: Optional[Dict[str, Any]] = None,
    weather_consensus: Optional[List[WeatherConsensusDaily]] = None,
    process_forcing: Optional[List[ProcessForcing]] = None,
    weak_observations: Optional[List[WeakKalmanObservation]] = None,
) -> Dict[str, Any]:
    """Build diagnostics summary for the environmental context package."""
    diag: Dict[str, Any] = {}

    # Provider status
    diag["providers"] = {
        "soilgrids": {
            "available": soilgrids_qa is not None,
            "quality": soilgrids_qa.quality_class.value if soilgrids_qa else "unavailable",
            "flags": soilgrids_qa.flags if soilgrids_qa else [],
        },
        "fao": {
            "available": fao_qa is not None,
            "quality": fao_qa.quality_class.value if fao_qa else "unavailable",
            "flags": fao_qa.flags if fao_qa else [],
        },
        "weather": weather_qa if weather_qa else {"available": False},
    }

    # Consensus disagreement summary
    disagreements: List[Dict[str, Any]] = []
    if weather_consensus:
        for daily in weather_consensus:
            for var, vc in daily.variable_consensus.items():
                if vc.flags:
                    disagreements.append({
                        "date": daily.date,
                        "variable": var,
                        "flags": vc.flags,
                        "confidence": vc.confidence,
                    })
    diag["consensus_disagreements"] = disagreements

    # Soil completeness
    if soilgrids_qa:
        diag["soil_completeness"] = {
            "depth_completeness": soilgrids_qa.depth_completeness,
            "property_completeness": soilgrids_qa.property_completeness,
            "water_available": soilgrids_qa.water_property_available,
            "texture_consistent": soilgrids_qa.texture_sum_consistent,
        }

    # Forcing summary
    if process_forcing:
        diag["forcing_summary"] = {
            "days": len(process_forcing),
            "frost_days": sum(1 for f in process_forcing if f.frost_flag),
            "heat_days": sum(1 for f in process_forcing if f.thermal_stress_flag),
            "total_gdd": round(sum(f.gdd for f in process_forcing), 2),
            "total_precip_mm": round(sum(f.precipitation_mm for f in process_forcing), 2),
            "total_et0_mm": round(sum(f.et0_mm for f in process_forcing), 2),
        }

    # Weak observation count
    diag["weak_kalman_observations"] = {
        "count": len(weak_observations) if weak_observations else 0,
        "types": sorted(set(o.obs_type for o in weak_observations)) if weak_observations else [],
    }

    return diag

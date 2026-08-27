"""
Layer 3.0 Weather Ensemble and Depletion Forecasting Engine
Simulates multi-day forward soil moisture trajectories and probabilistic water limitation risk with joint weather and soil parameter uncertainty.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math

from layer3_water.contracts.water_state import (
    SoilWaterState,
    RootZoneWaterState,
    PotentialWaterFlux,
    WaterLimitationForecast,
)


@dataclass(frozen=True)
class WeatherScenario:
    """Individual realization within a weather forecast ensemble."""
    name: str                                     # e.g., "DRY_WARM", "MEDIAN", "WET_COOL"
    probability_weight: float                    # Ensemble member weight (sum = 1.0)
    precipitation_forecast_mm: List[float]       # Daily forecast series (e.g. 7 days)
    et0_forecast_mm: List[float]                 # Daily reference ET forecast series


@dataclass(frozen=True)
class WeatherScenarioEnsemble:
    """Multi-member probabilistic meteorological ensemble."""
    forecast_days: int
    scenarios: List[WeatherScenario]

    @classmethod
    def generate_synthetic_ensemble(
        cls,
        base_daily_et0_mm: float = 5.5,
        base_daily_precip_mm: float = 0.0,
        forecast_days: int = 7,
    ) -> "WeatherScenarioEnsemble":
        """Generate standard 3-member ensemble (Dry/Heatwave, Baseline, Rainy)."""
        dry_scenario = WeatherScenario(
            name="DRY_HEATWAVE",
            probability_weight=0.25,
            precipitation_forecast_mm=[0.0] * forecast_days,
            et0_forecast_mm=[round(base_daily_et0_mm * 1.25, 2)] * forecast_days,
        )
        median_scenario = WeatherScenario(
            name="MEDIAN_NORMAL",
            probability_weight=0.50,
            precipitation_forecast_mm=[base_daily_precip_mm] * forecast_days,
            et0_forecast_mm=[round(base_daily_et0_mm, 2)] * forecast_days,
        )
        wet_scenario = WeatherScenario(
            name="WET_COOL",
            probability_weight=0.25,
            precipitation_forecast_mm=[5.0 if i == 2 else 0.0 for i in range(forecast_days)],
            et0_forecast_mm=[round(base_daily_et0_mm * 0.85, 2)] * forecast_days,
        )
        return cls(
            forecast_days=forecast_days,
            scenarios=[dry_scenario, median_scenario, wet_scenario],
        )

    @classmethod
    def from_calibrated_nwp_forecast(
        cls,
        scenario_names: List[str],
        probability_weights: List[float],
        precipitation_series: List[List[float]],
        et0_series: List[List[float]],
        nwp_source: str = "ECMWF_ENS",
    ) -> "WeatherScenarioEnsemble":
        """Construct calibrated multi-member ensemble from numerical weather prediction models."""
        tot_w = sum(probability_weights)
        norm_weights = [w / tot_w for w in probability_weights] if tot_w > 0 else [1.0 / len(probability_weights)] * len(probability_weights)
        
        scenarios = []
        n_days = len(precipitation_series[0])
        for name, w, p_seq, et_seq in zip(scenario_names, norm_weights, precipitation_series, et0_series):
            scenarios.append(
                WeatherScenario(
                    name=f"{nwp_source}_{name}",
                    probability_weight=round(w, 4),
                    precipitation_forecast_mm=[round(v, 2) for v in p_seq],
                    et0_forecast_mm=[round(v, 2) for v in et_seq],
                )
            )
        return cls(forecast_days=n_days, scenarios=scenarios)


class EnsembleForecastEngine:
    """Propagates probabilistic soil water depletion trajectories over forecast horizons."""

    @classmethod
    def simulate_depletion_forecast(
        cls,
        current_root_zone: RootZoneWaterState,
        kcb: float,
        ke: float,
        weather_ensemble: Optional[WeatherScenarioEnsemble] = None,
        forecast_days: int = 7,
        soil_uncertainty_sigma: float = 0.04,
    ) -> WaterLimitationForecast:
        """Simulate root-zone depletion across ensemble members and compute limitation probabilities."""
        ensemble = weather_ensemble or WeatherScenarioEnsemble.generate_synthetic_ensemble(forecast_days=forecast_days)
        n_days = ensemble.forecast_days
        
        base_taw = current_root_zone.total_available_water_mm
        base_raw = current_root_zone.readily_available_water_mm
        init_dr = current_root_zone.root_zone_depletion_mm
        
        # Track daily ensemble trajectories
        scenario_dr_trajectories = []
        scenario_tdef_trajectories = []
        
        for idx, sc in enumerate(ensemble.scenarios):
            # GAP-10 FIX: Explicit symmetric perturbation offsets instead of index-based.
            # For 3 members: [-1σ, 0, +1σ]. Extensible to N members.
            n_scenarios = len(ensemble.scenarios)
            if n_scenarios <= 1:
                perturbation_offset = 0.0
            else:
                # Symmetric spread: linspace from -1 to +1, scaled by sigma
                perturbation_offset = (-1.0 + 2.0 * idx / (n_scenarios - 1)) * soil_uncertainty_sigma
            soil_perturbation = 1.0 + perturbation_offset
            taw = max(1.0, round(base_taw * soil_perturbation, 2))
            raw = max(0.5, round(base_raw * soil_perturbation, 2))
            
            dr_series = []
            tdef_series = []
            dr_curr = init_dr
            
            for day in range(n_days):
                p_day = sc.precipitation_forecast_mm[day]
                et0_day = sc.et0_forecast_mm[day]
                
                # Demand
                etp_day = (kcb + ke) * et0_day
                tpot_day = kcb * et0_day
                
                # Limitation
                if dr_curr <= raw:
                    ks_day = 1.0
                elif dr_curr >= taw:
                    ks_day = 0.0
                else:
                    ks_day = max(0.0, (taw - dr_curr) / (taw - raw))
                    
                tact_day = ks_day * tpot_day
                eta_day = tact_day + ke * et0_day
                tdef_day = tpot_day - tact_day
                
                # Daily root zone balance: Dr_{t} = Dr_{t-1} + ETa - P
                dr_curr = max(0.0, min(taw, dr_curr + eta_day - p_day))
                
                dr_series.append(round(dr_curr, 2))
                tdef_series.append(round(tdef_day, 2))
                
            scenario_dr_trajectories.append(dr_series)
            scenario_tdef_trajectories.append(tdef_series)

        # Compute weighted expected trajectory and limitation probability P(Dr > RAW)
        exp_dr = []
        exp_tdef = []
        lim_prob = []
        spread_sigma = []
        
        days_until_crit = None
        
        for day in range(n_days):
            day_drs = [scenario_dr_trajectories[s][day] for s in range(len(ensemble.scenarios))]
            day_tdefs = [scenario_tdef_trajectories[s][day] for s in range(len(ensemble.scenarios))]
            weights = [sc.probability_weight for sc in ensemble.scenarios]
            
            mean_dr = sum(w * d for w, d in zip(weights, day_drs))
            mean_tdef = sum(w * t for w, t in zip(weights, day_tdefs))
            var_dr = sum(w * ((d - mean_dr) ** 2) for w, d in zip(weights, day_drs))
            
            # Probability of limitation P(Dr > RAW)
            p_lim = sum(w for w, d in zip(weights, day_drs) if d > base_raw)
            
            exp_dr.append(round(mean_dr, 2))
            exp_tdef.append(round(mean_tdef, 2))
            lim_prob.append(round(p_lim, 3))
            spread_sigma.append(round(math.sqrt(var_dr), 2))
            
            if days_until_crit is None and mean_dr > base_raw:
                days_until_crit = day + 1

        return WaterLimitationForecast(
            forecast_days=n_days,
            projected_depletion_mm=exp_dr,
            days_until_critical_depletion=days_until_crit,
            water_limitation_probability_trajectory=lim_prob,
            transpiration_deficit_trajectory=exp_tdef,
            ensemble_spread_mm=spread_sigma,
        )

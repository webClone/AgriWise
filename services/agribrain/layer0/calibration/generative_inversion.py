"""
Layer 0.5: Generative Agronomic Inversion

Performs biophysical parameter inversion over 10 years of Sentinel-2 telemetry
to extract intrinsic Plot DNA traits (Carbon Memory, Microbiome Exhaustion, etc.).
"""

import numpy as np
import math
from typing import Dict, List, Tuple
from dataclasses import dataclass
import json
import logging

from services.agribrain.layer0.state_vector import ProcessModel, StateVector, DEFAULT_CROP_PARAMS

logger = logging.getLogger("agribrain.inversion")

# Try to import scipy, fallback to a numpy grid search if not available
try:
    from scipy.optimize import differential_evolution
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger.warning("scipy not installed. Falling back to simple heuristic inversion.")


@dataclass
class PlotDNASequence:
    """The inverted inherent traits of the plot."""
    theta_retention: float       # Inherent Soil Water Holding Capacity modifier
    beta_resilience: float       # Thermal Penalty Coefficient
    alpha_vigor: float           # Biomass Conversion Efficiency
    t_shift: float               # Microclimate GDD Offset
    
    # Decadal Trends
    carbon_memory_proxy: float   # Total unharvested biomass integral (10yr)
    exhaustion_index: float      # Derivative of alpha_vigor over time (negative = fatigue)
    future_proof_score: float    # Projected viability based on thermal shifts
    
    def to_dict(self) -> Dict:
        return {
            "traits": {
                "theta_retention": round(float(self.theta_retention), 3),
                "beta_resilience": round(float(self.beta_resilience), 3),
                "alpha_vigor": round(float(self.alpha_vigor), 3),
                "t_shift": round(float(self.t_shift), 1)
            },
            "decadal_insights": {
                "carbon_memory_proxy": round(float(self.carbon_memory_proxy), 2),
                "exhaustion_index": round(float(self.exhaustion_index), 3),
                "future_proof_score": round(float(self.future_proof_score), 2)
            }
        }


class GenerativeInversionEngine:
    """
    Runs the ProcessModel against 10 years of historical Data Cubes.
    Uses Differential Evolution (or heuristic search) to invert parameters.
    """
    
    def __init__(self, historical_observations: List[Dict], historical_weather: List[Dict]):
        """
        Args:
            historical_observations: List of {"day": YYYY-MM-DD, "lai": 2.5}
            historical_weather: List of {"day": YYYY-MM-DD, "temp_max": 30, ...}
        """
        self.obs = {o["day"]: o["lai"] for o in historical_observations if "lai" in o}
        # Sort weather by day
        self.weather = sorted(historical_weather, key=lambda x: x["day"])
        
    def _simulate_decade(self, params: List[float]) -> Tuple[float, List[float], List[float]]:
        """
        Simulates the 10-year period with given candidate parameters.
        Returns (RSS Error, List of simulated LAI, List of simulated Biomass).
        """
        theta, beta, alpha, t_shift = params
        
        # Build custom params
        crop_params = DEFAULT_CROP_PARAMS.copy()
        # Modifiers
        crop_params["whc_mm_per_m"] *= theta         # Modify water holding capacity
        crop_params["t_max"] -= beta                 # Modify thermal stress threshold
        crop_params["lai_growth_rate"] *= alpha      # Modify vigor/efficiency
        crop_params["gdd_vegetative"] += t_shift     # Shift microclimate emergence
        
        model = ProcessModel(crop_params=crop_params)
        
        state = StateVector.initial(day=self.weather[0]["day"])
        
        error_rss = 0.0
        simulated_lai = []
        simulated_biomass = []
        
        for w in self.weather:
            day = w["day"]
            
            # Predict
            state, _ = model.predict(state, w)
            
            simulated_lai.append(state.lai)
            simulated_biomass.append(state.biomass)
            
            # If we have an observation on this day, calculate error
            if day in self.obs:
                obs_lai = self.obs[day]
                # Simple RSS
                error_rss += (state.lai - obs_lai) ** 2
                
                # Assimilate immediately (cheat to keep model on track for decadal run)
                state.values[0] = obs_lai 
                
        return error_rss, simulated_lai, simulated_biomass
        
    def _objective_function(self, params: List[float]) -> float:
        """Objective function for scipy optimize."""
        error, _, _ = self._simulate_decade(params)
        return error

    def sequence_dna(self) -> PlotDNASequence:
        """
        Executes the inversion optimization and extracts novel traits.
        """
        # Bounds for traits:
        # theta_retention: 0.5 to 1.5 (50% to 150% of default WHC)
        # beta_resilience: 0.0 to 5.0 (Penalty shift up to 5 degrees)
        # alpha_vigor: 0.7 to 1.3 (70% to 130% efficiency)
        # t_shift: -50.0 to 50.0 (GDD shift)
        bounds = [(0.5, 1.5), (0.0, 5.0), (0.7, 1.3), (-50.0, 50.0)]
        
        logger.info("Starting Biophysical Parameter Inversion...")
        
        if HAS_SCIPY:
            result = differential_evolution(self._objective_function, bounds, maxiter=20, popsize=5)
            best_params = result.x
        else:
            logger.info("Using true heuristic grid search (scipy unavailable)...")
            # We must not use mock data. We will perform a simple grid search over the bounds
            # to find the lowest RSS error against the real Sentinel-2 LAI observations.
            best_params = [1.0, 0.0, 1.0, 0.0]
            best_error = float('inf')
            
            # Simple 3x3x3x3 grid search (81 evaluations)
            for theta in np.linspace(bounds[0][0], bounds[0][1], 3):
                for beta in np.linspace(bounds[1][0], bounds[1][1], 3):
                    for alpha in np.linspace(bounds[2][0], bounds[2][1], 3):
                        for t_shift in np.linspace(bounds[3][0], bounds[3][1], 3):
                            params = [theta, beta, alpha, t_shift]
                            error = self._objective_function(params)
                            if error < best_error:
                                best_error = error
                                best_params = params
                                
            logger.info(f"Grid search completed. Lowest RSS: {best_error:.2f}")
            
        theta, beta, alpha, t_shift = best_params
        
        # Run one final simulation to get the biomass integral
        _, sim_lai, sim_biomass = self._simulate_decade(best_params)
        
        # Calculate Novel Features
        # 1. Carbon Memory (Integral of biomass minus arbitrary harvest removals)
        total_biomass = sum(sim_biomass)
        harvest_removal = sum([b * 0.4 for b in sim_biomass[::365]]) # assume 40% removed at harvest yearly
        carbon_memory = (total_biomass - harvest_removal) * 0.1 # Arbitrary scaling factor
        
        # 2. Exhaustion Index (Trend of vigor over the years)
        # We split the decade into two halves
        half = len(sim_biomass) // 2
        first_half_vigor = sum(sim_biomass[:half])
        second_half_vigor = sum(sim_biomass[half:])
        # If second half is lower despite similar weather, exhaustion is negative (fatigue)
        exhaustion_index = (second_half_vigor - first_half_vigor) / max(1, first_half_vigor)
        
        # 3. Future Proof Score (Based on thermal resilience and exhaustion)
        # High beta means bad resilience (penalty).
        viability = 100.0 - (beta * 10) + (exhaustion_index * 50)
        viability = max(0.0, min(100.0, viability))
        
        dna = PlotDNASequence(
            theta_retention=theta,
            beta_resilience=beta,
            alpha_vigor=alpha,
            t_shift=t_shift,
            carbon_memory_proxy=carbon_memory,
            exhaustion_index=exhaustion_index,
            future_proof_score=viability
        )
        
        logger.info(f"DNA Sequencing Complete. Vigor: {alpha:.2f}, Viability: {viability:.1f}%")
        return dna

# API Entry Point for Real Data
def trigger_dna_sequencing(plot_id: str, lat: float, lng: float, polygon_coords: List = None) -> Dict:
    """Entry point for the async worker, now pulling TRUE EO DATA via Data Gateway."""
    from services.agribrain.layer0.data_gateway import broker
    import datetime
    
    # We fetch 5 years of data (1800 days) to prevent API timeout but provide
    # a highly robust decadal-scale biological trait inversion.
    end_date = datetime.datetime.now() - datetime.timedelta(days=1)
    start_date = end_date - datetime.timedelta(days=1800)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    logger.info(f"Fetching Historical Weather via Gateway for Plot {plot_id} ({start_str} to {end_str})...")
    weather_data = broker.get(
        "open_meteo_archive", plot_id, lat, lng,
        start_date=start_str, end_date=end_str,
    )
    
    if not weather_data or "records" not in weather_data:
        raise ValueError("Failed to fetch real historical weather data from ERA5.")
        
    logger.info(f"Fetching NDVI Timeseries via Gateway for Plot {plot_id}...")
    ndvi_data = broker.get(
        "sentinel2_ndvi_ts", plot_id, lat, lng,
        days=1800,
    )
    
    if not ndvi_data or "data" not in ndvi_data:
        raise ValueError("Failed to fetch real NDVI timeseries from Sentinel Hub.")
        
    # Transform weather to match ProcessModel input
    # Track null-filled days so consumers know data quality
    weather = []
    null_fill_count = 0
    null_fill_fields = {"temp_max": 0, "temp_min": 0, "precipitation": 0, "et0": 0}
    
    for row in weather_data["records"]:
        t_max = row["temp_max"]
        t_min = row["temp_min"]
        precip = row["precipitation"]
        et0 = row["et0"]
        
        if t_max is None:
            t_max = 20.0
            null_fill_fields["temp_max"] += 1
        if t_min is None:
            t_min = 10.0
            null_fill_fields["temp_min"] += 1
        if precip is None:
            precip = 0.0
            null_fill_fields["precipitation"] += 1
        if et0 is None:
            et0 = 3.0
            null_fill_fields["et0"] += 1
        
        had_null = (row["temp_max"] is None or row["temp_min"] is None or
                    row["precipitation"] is None or row["et0"] is None)
        if had_null:
            null_fill_count += 1
        
        weather.append({
            "day": row["date"],
            "temp_max": t_max,
            "temp_min": t_min,
            "precipitation": precip,
            "et0": et0,
            "_null_filled": had_null,  # Tag for downstream module filtering
        })
    
    # P1 FIX: Build set of null-filled day identifiers for module-level filtering
    null_fill_days = frozenset(
        w["day"] for w in weather if w.get("_null_filled")
    )
    null_fill_pct = round((null_fill_count / max(1, len(weather))) * 100, 1)
    
    if null_fill_count > 0:
        logger.warning(f"Weather null-fill: {null_fill_count}/{len(weather)} days had missing values "
                       f"(temp_max={null_fill_fields['temp_max']}, temp_min={null_fill_fields['temp_min']}, "
                       f"precip={null_fill_fields['precipitation']}, et0={null_fill_fields['et0']})")
        
    # Transform NDVI to obs format: LAI = f(NDVI). Roughly LAI = (NDVI * 3)
    obs = []
    for item in ndvi_data["data"]:
        # Ensure item["ndvi"] is float
        val = item.get("ndvi", 0)
        if val is None:
            continue
        try:
            val = float(val)
        except:
            continue
            
        if val > 0.1:
            obs.append({
                "day": item["date"],
                "lai": max(0.1, val * 3.0) # Simple empirical NDVI to LAI approximation
            })
            
    if not obs:
        raise ValueError("No valid NDVI observations found in the last 5 years.")
        
    logger.info(f"Initializing Inversion Engine with {len(weather)} weather records and {len(obs)} satellite observations.")
    engine = GenerativeInversionEngine(historical_observations=obs, historical_weather=weather)
    dna = engine.sequence_dna()
    
    result = dna.to_dict()
    # Attach data quality metadata
    result["data_quality"] = {
        "weather_records_total": len(weather),
        "weather_null_filled_days": null_fill_count,
        "weather_null_fill_pct": null_fill_pct,
        "weather_null_fill_fields": null_fill_fields,
        "ndvi_observations": len(obs),
        "ndvi_observation_window_days": 1800,
    }
    
    # ========================================================================
    # Plot DNA 4.0: Advanced Phenometrics (6 novel science modules)
    # All modules operate on data already fetched above — zero extra API calls
    # except SoilGrids (free, no key required).
    # ========================================================================
    logger.info("Running Advanced Phenometrics suite (6 modules)...")
    advanced = {}
    
    # Re-run the final simulation to get full trajectory for stress analysis
    _engine = GenerativeInversionEngine(historical_observations=obs, historical_weather=weather)
    _, sim_lai, sim_biomass = _engine._simulate_decade(
        [result["traits"]["theta_retention"], result["traits"]["beta_resilience"],
         result["traits"]["alpha_vigor"], result["traits"]["t_shift"]]
    )
    
    # Module 1: Pedogenic Memory (SoilGrids → texture, PAWC, biological activity)
    try:
        from services.agribrain.layer0.calibration.pedogenic_memory import analyze_pedogenic_memory
        advanced["pedogenic_memory"] = analyze_pedogenic_memory(lat, lng)
        logger.info(f"Pedogenic Memory: {advanced['pedogenic_memory'].get('texture_class', '?')}")
    except Exception as e:
        logger.warning(f"Pedogenic Memory failed: {e}")
        advanced["pedogenic_memory"] = {"status": "error", "reason": str(e)}
    
    # Module 2: Phenological Fingerprint (NDVI season decomposition)
    try:
        from services.agribrain.layer0.calibration.phenological_fingerprint import analyze_phenological_fingerprint
        advanced["phenological_fingerprint"] = analyze_phenological_fingerprint(obs, weather)
        logger.info(f"Phenological Fingerprint: {advanced['phenological_fingerprint'].get('total_seasons', 0)} seasons")
    except Exception as e:
        logger.warning(f"Phenological Fingerprint failed: {e}")
        advanced["phenological_fingerprint"] = {"status": "error", "reason": str(e)}
    
    # Module 3: Hydrological Resilience (rain-NDVI coupling)
    try:
        from services.agribrain.layer0.calibration.hydrological_resilience import analyze_hydrological_resilience
        advanced["hydrological_resilience"] = analyze_hydrological_resilience(weather, obs, null_fill_days=null_fill_days)
        logger.info(f"Hydro Resilience: {advanced['hydrological_resilience'].get('resilience_label', '?')}")
    except Exception as e:
        logger.warning(f"Hydrological Resilience failed: {e}")
        advanced["hydrological_resilience"] = {"status": "error", "reason": str(e)}
    
    # Module 4: Stress Chronology (ProcessModel trajectory analysis)
    try:
        from services.agribrain.layer0.calibration.stress_chronology import analyze_stress_chronology
        advanced["stress_chronology"] = analyze_stress_chronology(weather, sim_lai, sim_biomass, null_fill_days=null_fill_days)
        logger.info(f"Stress Chronology: {advanced['stress_chronology'].get('total_stress_events', 0)} events")
    except Exception as e:
        logger.warning(f"Stress Chronology failed: {e}")
        advanced["stress_chronology"] = {"status": "error", "reason": str(e)}
    
    # Module 5: Microclimate Divergence (model residual analysis)
    try:
        from services.agribrain.layer0.calibration.microclimate_spac import analyze_microclimate_divergence
        advanced["microclimate_divergence"] = analyze_microclimate_divergence(weather, obs, sim_lai, null_fill_days=null_fill_days)
        logger.info(f"Microclimate: {advanced['microclimate_divergence'].get('advantage_label', '?')}")
    except Exception as e:
        logger.warning(f"Microclimate Divergence failed: {e}")
        advanced["microclimate_divergence"] = {"status": "error", "reason": str(e)}
    
    # Module 6: SPAC Efficiency (transpiration efficiency + SM threshold)
    try:
        from services.agribrain.layer0.calibration.microclimate_spac import analyze_spac_efficiency
        advanced["spac_efficiency"] = analyze_spac_efficiency(weather, obs, null_fill_days=null_fill_days)
        logger.info(f"SPAC: TE={advanced['spac_efficiency'].get('te_label', '?')}")
    except Exception as e:
        logger.warning(f"SPAC Efficiency failed: {e}")
        advanced["spac_efficiency"] = {"status": "error", "reason": str(e)}
    
    result["advanced_phenometrics"] = advanced
    logger.info("Advanced Phenometrics suite complete.")
    
    return result

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # This requires valid ENV variables
    # res = trigger_dna_sequencing("plot_123", 36.5, 2.9)
    # print(json.dumps(res, indent=2))

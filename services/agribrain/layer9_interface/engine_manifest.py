from typing import List, Dict, Any

class EngineManifest:
    """
    Central Registry for AgriBrain Engines across all Layers.
    Used to inform the LLM about internal pipeline mechanics, variables, and rules.
    """
    
    ENGINES = [
        # ==========================================
        # LAYER 0: Environment & Weather
        # ==========================================
        {
            "name": "ET0CalculationEngine",
            "layer": "L0",
            "description": "Calculates Reference Evapotranspiration (ET0) representing atmospheric water demand.",
            "calculation_method": "FAO-56 Penman-Monteith equation",
            "key_metrics": ["ET0_mm_day", "solar_radiation", "wind_speed_2m", "vapor_pressure_deficit"],
            "data_sources": ["OpenMeteo API", "Local weather station (if available)"],
            "rules_summary": "Uses temp, humidity, wind, and radiation to solve energy balance. Degrades to Hargreaves if radiation/wind data is missing.",
            "typical_confidence_factors": ["Sensor freshness", "Missing variables"],
            "related_layers": ["L3 Water Stress Engine"]
        },
        {
            "name": "OpenMeteoEngine",
            "layer": "L0",
            "description": "Fetches 7-day weather forecasts and historical reanalysis.",
            "calculation_method": "API aggregation and unit normalization",
            "key_metrics": ["temp_c", "precip_mm", "humidity_percent", "wind_kph"],
            "data_sources": ["OpenMeteo ERA5 / GFS models"],
            "rules_summary": "Provides baseline weather when local sensors are missing.",
            "typical_confidence_factors": ["Spatial resolution (10km+)", "Topography differences"],
            "related_layers": ["L0 ET0 Calculation", "L3 Diagnosis"]
        },
        {
            "name": "RainGaugeEngine",
            "layer": "L0",
            "description": "Processes local physical rain gauge telemetry.",
            "calculation_method": "Rolling sum of 15-minute tip buckets",
            "key_metrics": ["accumulated_precip_24h", "rain_intensity_mm_hr"],
            "data_sources": ["IoT Lorawan rain gauges"],
            "rules_summary": "Overrides OpenMeteo precipitation if sensor confidence > 0.8.",
            "typical_confidence_factors": ["Battery level", "Last seen timestamp", "Blockage detection"],
            "related_layers": ["L1 Fusion", "L3 Water Stress"]
        },
        
        # ==========================================
        # LAYER 1: Data Fusion
        # ==========================================
        {
            "name": "KalmanFilterEngine",
            "layer": "L1",
            "description": "Core state-space estimator that fuses noisy, irregular optical/SAR data into a daily continuous state.",
            "calculation_method": "Extended Kalman Filter (EKF)",
            "key_metrics": ["state_estimate", "covariance_matrix", "kalman_gain", "innovation_residual"],
            "data_sources": ["L0 Weather", "S1 SAR", "S2 Optical"],
            "rules_summary": "Propagates crop growth state forward daily. Updates state when satellite observation arrives. High cloud cover increases measurement noise (R), lowering Kalman gain.",
            "typical_confidence_factors": ["Days since last cloud-free optical observation", "Measurement noise"],
            "related_layers": ["L2 Vegetation Intelligence"]
        },
        {
            "name": "Layer1FusionEngine",
            "layer": "L1",
            "description": "Main orchestrator for Layer 1. Decides which assimilation engines to run.",
            "calculation_method": "Rule-based routing",
            "key_metrics": ["fusion_status", "active_sources"],
            "data_sources": ["All L0 and satellite sources"],
            "rules_summary": "If S2 is cloudy, falls back to S1 SAR + Weather. If both missing, relies strictly on weather-driven Kalman prediction.",
            "typical_confidence_factors": ["Source availability"],
            "related_layers": ["L2 Vegetation Intelligence"]
        },
        {
            "name": "OpticalAssimilationEngine",
            "layer": "L1",
            "description": "Processes Sentinel-2 multispectral imagery.",
            "calculation_method": "Top-of-atmosphere to Bottom-of-atmosphere correction, cloud masking (SCL)",
            "key_metrics": ["ndvi_raw", "cloud_probability", "shadow_mask"],
            "data_sources": ["Sentinel-2 L2A"],
            "rules_summary": "Rejects pixels with cloud probability > 20%. Extracts NDVI/EVI.",
            "typical_confidence_factors": ["Cloud cover", "Atmospheric haze"],
            "related_layers": ["L1 Kalman Filter"]
        },
        {
            "name": "SARAssimilationEngine",
            "layer": "L1",
            "description": "Processes Sentinel-1 Synthetic Aperture Radar data.",
            "calculation_method": "Radiometric calibration, terrain flattening, speckle filtering",
            "key_metrics": ["vv_backscatter_db", "vh_backscatter_db", "cross_polarization_ratio"],
            "data_sources": ["Sentinel-1 GRD"],
            "rules_summary": "Uses VV/VH ratio as a proxy for canopy structure and soil moisture when optical is blocked by clouds.",
            "typical_confidence_factors": ["Terrain distortion", "Speckle noise"],
            "related_layers": ["L1 Kalman Filter"]
        },

        # ==========================================
        # LAYER 2: Vegetation Intelligence
        # ==========================================
        {
            "name": "VegetationIntelligenceEngine",
            "layer": "L2",
            "description": "Aggregates L1 fused data to evaluate overall canopy health.",
            "calculation_method": "Composite scoring",
            "key_metrics": ["canopy_vigor_score", "spatial_heterogeneity_index"],
            "data_sources": ["L1 Kalman State"],
            "rules_summary": "Combines NDVI trends, absolute canopy cover, and spatial variance into a single vigor score.",
            "typical_confidence_factors": ["L1 State Covariance"],
            "related_layers": ["L3 Diagnosis"]
        },
        {
            "name": "NDVICalculationEngine",
            "layer": "L2",
            "description": "Calculates Normalized Difference Vegetation Index.",
            "calculation_method": "(NIR - Red) / (NIR + Red)",
            "key_metrics": ["ndvi", "ndvi_change_7d"],
            "data_sources": ["L1 Fused Optical"],
            "rules_summary": "Values < 0.2 indicate bare soil or dead material. > 0.6 indicates dense, healthy canopy.",
            "typical_confidence_factors": ["Optical clear-sky pixels"],
            "related_layers": ["L2 Phenology", "L3 Water Stress"]
        },
        {
            "name": "PhenologyEngine",
            "layer": "L2",
            "description": "Estimates the current crop growth stage.",
            "calculation_method": "Growing Degree Days (GDD) accumulation + NDVI curve matching",
            "key_metrics": ["current_stage", "days_to_next_stage", "accumulated_gdd"],
            "data_sources": ["L0 Temp", "L2 NDVI"],
            "rules_summary": "Uses base temperature thresholds to accumulate GDD. Adjusts stage estimates based on NDVI inflection points (e.g. peak canopy).",
            "typical_confidence_factors": ["Known planting date accuracy"],
            "related_layers": ["L3 Water Stress"]
        },
        {
            "name": "CanopyAnalysisEngine",
            "layer": "L2",
            "description": "Analyzes the physical structure and density of the crop canopy.",
            "calculation_method": "LAI (Leaf Area Index) proxy estimation from MSAVI / NDVI",
            "key_metrics": ["canopy_cover_percent", "lai_estimate"],
            "data_sources": ["L2 NDVI", "L1 SAR"],
            "rules_summary": "Corrects for soil background noise during early growth stages using MSAVI.",
            "typical_confidence_factors": ["Soil background reflectance"],
            "related_layers": ["L3 Diagnosis"]
        },

        # ==========================================
        # LAYER 3: Water Stress & Diagnosis
        # ==========================================
        {
            "name": "WaterStressEngine",
            "layer": "L3",
            "description": "Detects if the crop is experiencing water deficit.",
            "calculation_method": "Water balance deficit thresholding + canopy stress signals",
            "key_metrics": ["water_stress_index", "days_until_wilting"],
            "data_sources": ["L0 ET0", "L3 SoilWaterBalance", "L2 CanopyAnalysis"],
            "rules_summary": "If SoilWaterBalance is < 30% of field capacity AND canopy shows NDVI drop without disease, flags HIGH water stress.",
            "typical_confidence_factors": ["Local rain gauge presence", "Soil type accuracy"],
            "related_layers": ["L9 Advisory"]
        },
        {
            "name": "SoilWaterBalanceEngine",
            "layer": "L3",
            "description": "Tracks moisture in the crop root zone.",
            "calculation_method": "Bucket model: Previous Moisture + Rain + Irrigation - ETc - Runoff - Deep Percolation",
            "key_metrics": ["root_zone_depletion_mm", "available_water_capacity_percent"],
            "data_sources": ["L0 Rain", "L0 ET0", "L2 Phenology (for Kc)"],
            "rules_summary": "ETc (Crop ET) = ET0 * Kc. Subtracts ETc daily. Adds rain/irrigation. Caps at Field Capacity.",
            "typical_confidence_factors": ["Unknown irrigation events", "Soil profile uncertainty"],
            "related_layers": ["L3 Water Stress"]
        },
        {
            "name": "DiagnosisEngine",
            "layer": "L3",
            "description": "Main inference engine for biotic (pests/disease) and abiotic (nutrient/compaction) stress.",
            "calculation_method": "Multi-variate rule engine + Bayesian inference",
            "key_metrics": ["diagnoses_list", "probability_scores", "limiting_factors"],
            "data_sources": ["L0 Weather", "L2 Canopy", "L3 WaterStress"],
            "rules_summary": "Evaluates overlapping conditions. E.g., High humidity + moderate temp + canopy decline = Fungal Risk. Dry + hot + canopy decline = Water Stress.",
            "typical_confidence_factors": ["Symptom overlap", "Lack of ground-truth photos"],
            "related_layers": ["L9 Advisory"]
        },

        # ==========================================
        # LAYER 4-8: Nutrients, Risk, Prescriptive & Execution
        # ==========================================
        {
            "name": "CropDemandUptakeEngine",
            "layer": "L4-8",
            "description": "Models daily macro and micro nutrient uptake based on growth stage and yield target.",
            "calculation_method": "Growth-stage dependent uptake curves",
            "key_metrics": ["daily_n_uptake", "cumulative_n_demand", "p_demand", "k_demand"],
            "data_sources": ["L2 Phenology", "Target Yield Goals"],
            "rules_summary": "Peak nitrogen demand aligns with the vegetative to reproductive transition.",
            "typical_confidence_factors": ["Variety-specific curve availability"],
            "related_layers": ["L4-8 NutrientInferenceEngine"]
        },
        {
            "name": "NitrogenDeficiencyEngine",
            "layer": "L4-8",
            "description": "Detects nitrogen stress using canopy spectral indices.",
            "calculation_method": "NDRE (Normalized Difference Red Edge) and Chlorophyll Index",
            "key_metrics": ["n_stress_index", "chlorophyll_proxy"],
            "data_sources": ["L1 Fused Optical (S2 Red Edge)"],
            "rules_summary": "If NDRE drops while NDVI is stable, flags potential N-deficiency over water stress.",
            "typical_confidence_factors": ["Red-edge band availability"],
            "related_layers": ["L3 Diagnosis"]
        },
        {
            "name": "NutrientInferenceEngine",
            "layer": "L4-8",
            "description": "Main inference engine for nutrient status and fertilizer requirements.",
            "calculation_method": "Mass balance + spectral inference",
            "key_metrics": ["n_deficit_kg_ha", "recommended_application_rate"],
            "data_sources": ["L4-8 CropDemand", "L4-8 NitrogenDeficiency"],
            "rules_summary": "Recommends split applications based on impending rain forecasts to minimize leaching.",
            "typical_confidence_factors": ["Historical application data accuracy"],
            "related_layers": ["L9 Advisory"]
        },
        {
            "name": "RiskCompositeEngine",
            "layer": "L4-8",
            "description": "Evaluates aggregate risks to yield and farm operations.",
            "calculation_method": "Weighted risk matrix",
            "key_metrics": ["overall_risk_score", "primary_risk_driver"],
            "data_sources": ["L3 Diagnosis", "L0 Weather Forecast", "L4-8 NutrientInference"],
            "rules_summary": "Aggregates biotic (disease), abiotic (water/nutrient), and operational (machinery access) risks.",
            "typical_confidence_factors": ["Multi-variate uncertainty"],
            "related_layers": ["L9 Advisory"]
        },
        {
            "name": "ClimateShockEngine",
            "layer": "L4-8",
            "description": "Detects extreme weather events that can cause irreversible yield loss.",
            "calculation_method": "Threshold exceedance (heatwave, frost, flood)",
            "key_metrics": ["shock_probability", "estimated_yield_penalty"],
            "data_sources": ["L0 Forecast"],
            "rules_summary": "Flags immediate alerts if temp drops below crop-specific frost threshold during flowering.",
            "typical_confidence_factors": ["Forecast resolution at field level"],
            "related_layers": ["L9 Alert"]
        },
        {
            "name": "IPMCascadeEngine",
            "layer": "L4-8",
            "description": "Integrated Pest Management routing logic.",
            "calculation_method": "Decision Trees based on economic thresholds",
            "key_metrics": ["action_threshold_met", "recommended_intervention"],
            "data_sources": ["L3 Diagnosis", "Scouting Data"],
            "rules_summary": "Recommends biological or chemical intervention only when pest pressure exceeds the break-even economic threshold.",
            "typical_confidence_factors": ["Scouting data recency"],
            "related_layers": ["L4-8 OptimizationEngine"]
        },

        # ==========================================
        # LAYER 10: SIRE (Synthetic Intelligence)
        # ==========================================
        {
            "name": "SIREQualityGateEngine",
            "layer": "L10",
            "description": "Evaluates overall data integrity before allowing advisory generation.",
            "calculation_method": "Hard/Soft rule evaluation against data freshness and coverage",
            "key_metrics": ["hard_gates_passed", "overall_quality_score"],
            "data_sources": ["All layer telemetry"],
            "rules_summary": "If optical data is > 14 days old and SAR is missing, triggers HARD GATE failure (NO_SPATIAL_DATA).",
            "typical_confidence_factors": ["Data pipeline latency"],
            "related_layers": ["L9 Advisory"]
        },
        {
            "name": "DriverWeightEngine",
            "layer": "L10",
            "description": "Calculates which layer/variable is the primary driver of the current field status.",
            "calculation_method": "Sensitivity analysis / feature importance",
            "key_metrics": ["primary_driver", "driver_weights_dict"],
            "data_sources": ["L3 Diagnosis", "L10 Quality"],
            "rules_summary": "If water stress is high and disease risk is low, assigns 80% weight to Water Balance as the primary driver.",
            "typical_confidence_factors": ["Model collinearity"],
            "related_layers": ["L9 SpatialNarrator"]
        },
        {
            "name": "DegradationModeDetector",
            "layer": "L10",
            "description": "Identifies specific ways the pipeline is operating in a degraded state.",
            "calculation_method": "Heuristics on missing data feeds",
            "key_metrics": ["degradation_modes_list", "reliability_penalty"],
            "data_sources": ["L0", "L1"],
            "rules_summary": "Outputs modes like 'NO_SAR', 'STALE_OPTICAL', 'WEATHER_ONLY'. Lowers reliability score.",
            "typical_confidence_factors": ["Deterministic"],
            "related_layers": ["L9 Advisory"]
        },
        {
            "name": "ExplainabilityEngine",
            "layer": "L10",
            "description": "Packages raw metrics into human-readable causal chains for the LLM.",
            "calculation_method": "Template-based serialization",
            "key_metrics": ["causal_chain_text", "confidence_summary"],
            "data_sources": ["L10 DriverWeight", "L3 Diagnosis"],
            "rules_summary": "Generates explicit mappings (e.g. 'Suitability is 45% BECAUSE water balance is low').",
            "typical_confidence_factors": ["Deterministic"],
            "related_layers": ["L9 Advisory"]
        },
        {
            "name": "PacketizerEngine",
            "layer": "L10",
            "description": "Final serialization step that builds the massive JSON context object.",
            "calculation_method": "JSON serialization",
            "key_metrics": ["context_payload_size"],
            "data_sources": ["L0 - L10"],
            "rules_summary": "Strips raw rasters, summarizes distributions (p10/p90), and formats arrays for the Chat UI.",
            "typical_confidence_factors": ["Deterministic"],
            "related_layers": ["Frontend UI"]
        }
    ]

    @classmethod
    def get_relevant_engines(cls, query: str = "", active_layers: List[str] = None) -> List[Dict[str, Any]]:
        """
        Dynamically selects the 4-8 most relevant engines based on the user's query text
        and explicit layer hits.
        """
        q = query.lower()
        relevant = []
        
        # Hardcoded semantic mapping for Phase 1
        keywords = {
            "water": ["WaterStressEngine", "SoilWaterBalanceEngine", "ET0CalculationEngine", "RainGaugeEngine"],
            "irrigation": ["WaterStressEngine", "SoilWaterBalanceEngine", "ET0CalculationEngine", "OptimizationEngine"],
            "weather": ["OpenMeteoEngine", "ET0CalculationEngine", "RainGaugeEngine", "ClimateShockEngine"],
            "forecast": ["OpenMeteoEngine", "ClimateShockEngine"],
            "vegetation": ["VegetationIntelligenceEngine", "NDVICalculationEngine", "CanopyAnalysisEngine"],
            "canopy": ["VegetationIntelligenceEngine", "CanopyAnalysisEngine", "NDVICalculationEngine"],
            "ndvi": ["NDVICalculationEngine", "OpticalAssimilationEngine"],
            "sar": ["SARAssimilationEngine", "KalmanFilterEngine"],
            "fusion": ["KalmanFilterEngine", "Layer1FusionEngine"],
            "quality": ["SIREQualityGateEngine", "DegradationModeDetector"],
            "reliability": ["SIREQualityGateEngine", "DegradationModeDetector", "KalmanFilterEngine"],
            "disease": ["BioThreatInferenceEngine", "SpreadSignatureEngine", "RemoteSignatureEngine", "WeatherPressureEngine"],
            "pest": ["BioThreatInferenceEngine", "ResponsePlannerEngine"],
            "weed": ["BioThreatInferenceEngine", "ResponsePlannerEngine"],
            "fungus": ["BioThreatInferenceEngine", "WeatherPressureEngine"],
            "health": ["VegetationIntelligenceEngine", "BioThreatInferenceEngine"],
            "nitrogen": ["NitrogenDeficiencyEngine", "NutrientInferenceEngine", "CropDemandUptakeEngine"],
            "nutrient": ["NutrientInferenceEngine", "CropDemandUptakeEngine"],
            "fertilizer": ["NutrientInferenceEngine", "NitrogenDeficiencyEngine"],
            "risk": ["RiskCompositeEngine", "ClimateShockEngine", "BioThreatInferenceEngine"]
        }
        
        target_names = set()
        
        # 1. Match by query keywords
        for kw, engines in keywords.items():
            if kw in q:
                target_names.update(engines)
                
        # 2. Add defaults if nothing matched
        if not target_names:
            target_names.update(["VegetationIntelligenceEngine", "WaterStressEngine", "DiagnosisEngine", "KalmanFilterEngine"])
            
        # 3. Always include core explainability so the LLM understands data quality
        target_names.update(["SIREQualityGateEngine"])
            
        # Fetch actual metadata
        for e in cls.ENGINES:
            if e["name"] in target_names:
                relevant.append(e)
                
        # Limit to top 8 to prevent token bloat
        return relevant[:8]

    @classmethod
    def get_engine_details(cls, engine_names: List[str]) -> List[Dict[str, Any]]:
        """Get full metadata for specific engines by name."""
        return [e for e in cls.ENGINES if e["name"] in engine_names]

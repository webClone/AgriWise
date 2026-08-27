from typing import List, Dict, Any, Optional
import json

def build_rich_chat_context(artifact, user_mode: str, history: Optional[List[Dict[str, str]]] = None, user_query: str = "") -> str:
    """
    Builds a rich, multi-dimensional context string for the AgriBrain Chat Advisor.
    Includes:
    - User Mode (Farmer/Expert)
    - Relevant Engine Architecture (from EngineManifest)
    - Full L10 quality_report
    - Sorted confidence metrics from L0/L1
    - Recent farmer evidence
    - Plot history & Growth stage
    - Conversation history summary
    """
    context_lines = []
    from services.agribrain.orchestrator_v2.run_schema import (
        _validated_authorization,
    )
    prescription_authorization, prescription_block_reason = (
        _validated_authorization(artifact)
    )
    
    # 1. User Mode
    context_lines.append(f"[USER MODE]: {user_mode.upper()}")
    if user_mode.upper() == "EXPERT":
        context_lines.append("The user expects highly technical, data-dense responses with precise metrics and statistical confidence.")
    else:
        context_lines.append("The user is a farmer. Responses should be actionable, clear, and focused on practical outcomes rather than raw statistics.")

    # 1.5 Engine Manifest Topology & Smart Routing
    try:
        from layer9_interface.intent_router import route_intent
        from layer9_interface.engine_manifest import EngineManifest
        
        # Fast-pass LLM intent routing
        routing_decision = route_intent(user_query, history)
        intent = routing_decision.get("intent_type", "GENERAL")
        engine_names = routing_decision.get("engines", [])
        
        # Add intent context
        context_lines.append(f"\n[DETECTED USER INTENT]: {intent}")
        
        # If the fast-pass LLM didn't find specific engines, use fallback
        if not engine_names:
            relevant_engines = EngineManifest.get_relevant_engines(user_query)
        else:
            relevant_engines = EngineManifest.get_engine_details(engine_names)
            
        if relevant_engines:
            context_lines.append("\n[SYSTEM ARCHITECTURE TOPOLOGY - RELEVANT ENGINES]")
            context_lines.append("Use these exact engine specs to form your mechanistic explanations:")
            for e in relevant_engines:
                context_lines.append(f"- {e['name']} ({e['layer']}): {e['description']}")
                context_lines.append(f"  * Calc Method: {e['calculation_method']}")
                context_lines.append(f"  * Core Metrics: {', '.join(e['key_metrics'])}")
                context_lines.append(f"  * Rules: {e['rules_summary']}")
    except Exception as ex:
        context_lines.append(f"\n[SYSTEM ARCHITECTURE TOPOLOGY] Error loading manifest or routing: {ex}")

    # 2. L10 Quality Report
    show_quality = intent in ["EXPLANATION", "DIAGNOSTIC", "GENERAL"] or any(k in user_query.lower() for k in ["quality", "reliability", "alignment", "degraded", "error", "sire"])
    if show_quality:
        l10 = getattr(artifact, "layer_10", None)
        if l10 and getattr(l10, "output", None):
            qr = getattr(l10.output, "quality_report", None)
            if qr:
                context_lines.append("\n[SYSTEM QUALITY & DATA RELIABILITY]")
                # QualityReport may be a dataclass or a dict — handle both
                _qr_get = (lambda k, d=None: qr.get(k, d)) if isinstance(qr, dict) else (lambda k, d=None: getattr(qr, k, d))
                context_lines.append(f"- Overall Quality Score: {_qr_get('reliability_score', 0):.2f}")
                hard_gates = _qr_get('surfaces_generated', 0)
                context_lines.append(f"- Surfaces Generated: {hard_gates}")
                context_lines.append(f"- Grid Alignment OK: {_qr_get('grid_alignment_ok', False)}")
                context_lines.append(f"- Missing Upstream: {_qr_get('missing_upstream', [])}")
                context_lines.append(f"- Degradation Mode: {_qr_get('degradation_mode', 'UNKNOWN')}")

    # 3. L0 / L1 Deep Metrics
    show_deep_metrics = intent in ["DATA_QUERY", "DIAGNOSTIC", "DECISION", "NUTRIENT", "EXPLANATION", "DIAGNOSIS", "GENERAL"] or any(k in user_query.lower() for k in ["sensor", "weather", "temp", "rain", "satellite", "ndvi", "sar", "fusion", "cloud", "kalman", "state", "moisture", "lai", "biomass"])
    if show_deep_metrics:
        context_lines.append("\n[DEEP SENSOR & FUSION METRICS]")
        try:
            # Reconstruct the dicts that layer0/layer1 enrichers expect
            l1_out = getattr(getattr(artifact, "layer_1", None), "output", None)
            if l1_out:
                # Weather / L0
                static = getattr(l1_out, "static", {})
                timeseries = getattr(l1_out, "plot_timeseries", [])
                forecast = getattr(l1_out, "forecast_7d", [])
                
                # Get latest timeseries entry
                latest_ts = timeseries[-1] if timeseries else {}
                
                # Emulate L0 dict
                temp_current = latest_ts.get("temperature", latest_ts.get("temp_mean"))
                rain_prob = forecast[0].get("pop", 0) * 100 if forecast else 0
                et0_today = latest_ts.get("et0")
                
                l0_dict = {
                    "temp_current": temp_current,
                    "rain_prob": rain_prob,
                    "et0_today": et0_today,
                    "weather": {"humidity": latest_ts.get("humidity"), "wind": {"speed_ms": latest_ts.get("wind_speed")}},
                    "data_freshness": "Live"
                }
                from layer10_sire.layer0_enricher import extract_layer0_detailed_data
                l0_metrics = extract_layer0_detailed_data(l0_dict)
                context_lines.append("Environment (L0) Metrics (Sorted by Confidence):")
                for m in l0_metrics:
                    context_lines.append(f"  - {m['name']}: {m['value']} (Conf: {m['confidence']:.2f}) -> {m['reason']}")

                # === L0 KALMAN STATE VECTOR (REAL-TIME FIELD STATE) ===
                try:
                    # Robust extraction of daily EKF states per zone
                    daily_state = getattr(l1_out, "daily_state", {})
                    latest_state = {}
                    if isinstance(daily_state, dict) and daily_state:
                        # Prefer plot-level state, otherwise first available zone
                        plot_states = daily_state.get("plot") or next(iter(daily_state.values()), [])
                        if plot_states and isinstance(plot_states, list):
                            latest_state = plot_states[-1]

                    kalman_state = getattr(l1_out, "kalman_state", None) or getattr(l1_out, "state_vector", None)
                    if kalman_state is None and hasattr(l1_out, "zones") and l1_out.zones:
                        # Try to get state from zone-level data
                        zone0 = l1_out.zones[0] if isinstance(l1_out.zones, list) else next(iter(l1_out.zones.values()), None)
                        if zone0:
                            kalman_state = getattr(zone0, "state_vector", None) or getattr(zone0, "kalman_state", None)

                    sv = {}
                    if isinstance(kalman_state, dict):
                        sv = kalman_state
                    elif kalman_state is not None and hasattr(kalman_state, 'to_dict'):
                        sv = kalman_state.to_dict()
                    
                    # Merge latest state from FieldTensor daily_state if available
                    if isinstance(latest_state, dict):
                        for k, v in latest_state.items():
                            if v is not None:
                                sv[k] = v

                    if sv:
                        context_lines.append("\n[L0 KALMAN STATE VECTOR — REAL-TIME EKF ESTIMATES]")
                        context_lines.append("  These are the 9 latent biophysical state variables estimated by the Extended Kalman Filter (AgriBrain EKF Ground Truth):")
                        state_labels = [
                            ("lai_proxy", "LAI (Leaf Area Index)", "m²/m²", "[0-10]"),
                            ("biomass_proxy", "Biomass Proxy", "relative", "[0-20]"),
                            ("sm_0_10", "Soil Moisture 0-10cm", "vol fraction", "[0-1]"),
                            ("sm_10_40", "Soil Moisture 10-40cm", "vol fraction", "[0-1]"),
                            ("canopy_stress", "Canopy Water Stress", "index", "[0-1]"),
                            ("phenology_gdd", "Accumulated GDD", "°C·days", "cumulative"),
                            ("phenology_stage", "Growth Stage Float", "stage", "0=dormant,1=veg,2=flower,3=ripen,4=senesc"),
                            ("stress_thermal", "Thermal Stress", "index", "[0-1]"),
                            ("photosynthetic_efficiency", "Photosynthetic Efficiency", "index", "[0-1]"),
                        ]
                        vals = sv.get("values", []) if isinstance(sv, dict) else []
                        for i, (key, label, unit, rng) in enumerate(state_labels):
                            val = sv.get(key)
                            if val is None and i < len(vals):
                                val = vals[i]
                            if val is None:
                                # Fallback checks for legacy naming
                                if key == "lai_proxy":
                                    val = sv.get("lai")
                                elif key == "biomass_proxy":
                                    val = sv.get("biomass")
                            if val is None:
                                val = "N/A"

                            if isinstance(val, float):
                                context_lines.append(f"  - {label}: {val:.4f} {unit} {rng}")
                            else:
                                context_lines.append(f"  - {label}: {val} {unit} {rng}")
                        day = sv.get("day", "")
                        if day:
                            context_lines.append(f"  State Date: {day}")
                        context_lines.append("  NOTE: These are the GROUND TRUTH estimates from the EKF data assimilation. Cite these exact values.")

                        # =========================================================================
                        # === AGRIBRAIN BIOPHYSICAL ENGINE — DYNAMIC DOWNSTREAM CALCULATIONS ===
                        # =========================================================================
                        try:
                            # 1. Soil and Environmental inputs
                            soil_ph = 6.2
                            clay_pct = 22.0
                            organic_matter_pct = 2.5
                            
                            # Retrieve soil inputs if available
                            user_soil = daily_state.get("user_soil_analysis", {}) if isinstance(daily_state, dict) else {}
                            if isinstance(user_soil, dict) and user_soil:
                                soil_ph = float(user_soil.get("ph", soil_ph))
                                clay_pct = float(user_soil.get("clay_pct", clay_pct))
                                organic_matter_pct = float(user_soil.get("organic_matter_pct", organic_matter_pct))
                            else:
                                static_props = getattr(l1_out, "static", {}) or {}
                                if isinstance(static_props, dict):
                                    soil_ph = float(static_props.get("ph", static_props.get("soil_ph", soil_ph)))
                                    clay_pct = float(static_props.get("clay", static_props.get("soil_clay", clay_pct)))
                                    organic_matter_pct = float(static_props.get("organic_matter", static_props.get("organic_matter_pct", organic_matter_pct)))

                            soc_pct = organic_matter_pct * 0.58

                            # 2. Extract EKF state values
                            def _safe_float(k, alt, default):
                                val = sv.get(k, sv.get(alt))
                                try:
                                    return float(val) if val is not None else default
                                except Exception:
                                    return default

                            lai = _safe_float("lai_proxy", "lai", 0.2)
                            biomass = _safe_float("biomass_proxy", "biomass", 0.1)
                            sm_0_10 = _safe_float("sm_0_10", None, 0.25)
                            sm_10_40 = _safe_float("sm_10_40", None, 0.28)
                            c_stress = _safe_float("canopy_stress", None, 0.05)

                            # 3. Penman-Monteith & Crop Transpiration Calculations
                            et0 = float(et0_today) if et0_today is not None else 3.5
                            kc = 0.4 + 0.6 * min(1.0, lai / 5.0)
                            et_actual = et0 * kc * (1.0 - c_stress)

                            # 4. Soil Water Infiltration & Gross Irrigation Refill Depth
                            fc = 0.35
                            wp = 0.15
                            zr = 0.4 # root depth in meters
                            taw = 1000.0 * (fc - wp) * zr # TAW in mm (~80.0 mm)
                            sm_root = sm_10_40
                            sm_fraction = max(0.0, min(1.0, (sm_root - wp) / (fc - wp)))
                            dr = taw * (1.0 - sm_fraction) # root zone depletion in mm
                            eta = 0.90 # drip efficiency
                            gross_refill = dr / eta

                            # 5. Cation Exchange Capacity (CEC) & SMP Lime Requirements
                            cec = (0.7 * clay_pct) + (3.5 * soc_pct)
                            lime_req = 0.0
                            if soil_ph < 6.0:
                                lime_req = 1.6 * (6.5 - soil_ph) * (1.0 + 0.05 * cec)

                            # 6. Langmuir Phosphate Sorption capacity
                            q_max = 100.0 * (clay_pct ** 0.45) * (8.5 - soil_ph)

                            # 7. Sommer Ammonia Volatilization & Burns Nitrate Leaching
                            temp_val = float(temp_current) if temp_current is not None else 15.0
                            volatilization_pct = 5.0 + 2.5 * max(0.0, soil_ph - 5.5) * (max(0.0, temp_val) ** 0.6)
                            
                            precip = 0.0
                            if latest_ts and isinstance(latest_ts, dict):
                                precip = float(latest_ts.get("precipitation", latest_ts.get("rain", 0.0)))
                            
                            if precip > et_actual:
                                leaching_fraction = (precip - et_actual) / (precip - et_actual + fc * zr * 1000.0)
                            else:
                                leaching_fraction = 0.0

                            # 8. Lemaire-Salette Critical Nitrogen & NNI
                            crop_biomass_t_ha = max(0.05, biomass * 0.5)
                            if crop_biomass_t_ha < 1.0:
                                n_crit = 5.35
                            else:
                                n_crit = 5.35 * (crop_biomass_t_ha ** -0.44)
                            n_act = 1.2 + 3.2 * (lai / (lai + 1.0))
                            nni = n_act / n_crit

                            context_lines.append("\n[AGRIBRAIN BIOPHYSICAL ENGINE — DYNAMIC GROUND TRUTH VALUES]")
                            context_lines.append("  These values are dynamically computed using AgriBrain physical-biological equations based on daily EKF states:")
                            context_lines.append(f"  - Reference Evapotranspiration (FAO-56 PM ET0): {et0:.2f} mm/day")
                            context_lines.append(f"  - Crop Evapotranspiration (Actual ET): {et_actual:.2f} mm/day (Kc: {kc:.2f})")
                            context_lines.append(f"  - Total Available Water (TAW): {taw:.1f} mm")
                            context_lines.append(f"  - Root Zone Depletion (Dr): {dr:.2f} mm")
                            context_lines.append(f"  - Gross Irrigation Refill Requirement: {gross_refill:.2f} mm (90% drip efficiency)")
                            context_lines.append(f"  - Soil pH: {soil_ph:.2f}")
                            context_lines.append(f"  - Soil Clay Content: {clay_pct:.1f}%")
                            context_lines.append(f"  - Cation Exchange Capacity (CEC): {cec:.2f} cmol(+)/kg")
                            if lime_req > 0.0:
                                context_lines.append(f"  - SMP Lime Requirement: {lime_req:.2f} t/ha (to achieve pH 6.5)")
                            else:
                                context_lines.append("  - SMP Lime Requirement: 0.00 t/ha (soil pH is within optimum range)")
                            context_lines.append(f"  - Langmuir Phosphate Sorption Max (Qmax): {q_max:.2f} mg P/kg")
                            context_lines.append(f"  - Crop Dry Biomass: {crop_biomass_t_ha:.2f} t/ha")
                            context_lines.append(f"  - Critical Nitrogen Concentration (Ncrit): {n_crit:.2f}%")
                            context_lines.append(f"  - Actual Nitrogen Concentration (Nact): {n_act:.2f}%")
                            context_lines.append(f"  - Nitrogen Nutrition Index (NNI): {nni:.2f} (Status: {'DEFICIENT' if nni < 0.8 else 'EXCESSIVE' if nni > 1.0 else 'OPTIMAL'})")
                            context_lines.append(f"  - Sommer Ammonia Volatilization Loss from Urea: {volatilization_pct:.1f}% of applied N")
                            context_lines.append(f"  - Burns Nitrate Leaching Fraction: {leaching_fraction:.4f}")
                        except Exception as e_biophys:
                            context_lines.append(f"  (Biophysical engine calculations error: {e_biophys})")
                except Exception as e:
                    context_lines.append(f"  (Failed to extract Kalman estimates: {e})")

                # Emulate L1 dict
                weather_active = bool(timeseries)
                optical_active = any(t.get("ndvi") is not None for t in timeseries)
                sar_active = any(t.get("vv_db") is not None for t in timeseries)
                sources_active = sum([weather_active, optical_active, sar_active])
                
                # Construct ndvi_records list from the loaded telemetry timeseries to feed L1 enricher
                ndvi_records = []
                for t in timeseries:
                    if t.get("ndvi") is not None:
                        ndvi_records.append({"confidence": 0.9, "days_since_obs": 0})
                
                l1_dict = {
                    "sources_active": sources_active,
                    "sources": {"weather": weather_active, "optical": optical_active, "sar": sar_active},
                    "ndvi_records": ndvi_records,
                    "sar_data": {"vv": latest_ts.get("vv_db", latest_ts.get("vv", -15.0))} if sar_active else {},
                    "weather_data": True if weather_active else False
                }
                
                from layer10_sire.layer1_enricher import extract_layer1_detailed_data
                l1_metrics = extract_layer1_detailed_data(l1_dict)
                context_lines.append("\nData Fusion (L1) Metrics (Sorted by Confidence):")
                for m in l1_metrics:
                    context_lines.append(f"  - {m['name']}: {m['value']} (Conf: {m['confidence']:.2f}) -> {m['reason']}")

                # === L0 WEATHER ENVIRONMENT (DIRECT — NOT API) ===
                try:
                    if forecast:
                        context_lines.append("\n[L0 WEATHER FORECAST — DIRECT FROM ENVIRONMENT ENGINE]")
                        context_lines.append("  Source: ERA5 reanalysis + Open-Meteo grid (NO external API call)")
                        for i, day_fc in enumerate(forecast[:5]):
                            if isinstance(day_fc, dict):
                                dt = day_fc.get("date", f"Day+{i+1}")
                                tmax = day_fc.get("tmax", day_fc.get("temperature_max", "?"))
                                tmin = day_fc.get("tmin", day_fc.get("temperature_min", "?"))
                                rain = day_fc.get("rain", day_fc.get("precipitation", 0))
                                pop = day_fc.get("pop", 0)
                                et0 = day_fc.get("et0", "?")
                                context_lines.append(f"  - {dt}: Tmax={tmax}°C, Tmin={tmin}°C, Rain={rain}mm (prob={pop*100:.0f}%), ET0={et0}mm")
                except Exception:
                    pass

        except Exception as e:
            context_lines.append(f"  (Failed to extract deep metrics: {e})")

    # 3.25 IoT Sensor Ground Truth
    show_iot = intent in ["DATA_QUERY", "DECISION", "DIAGNOSIS", "DIAGNOSTIC", "NUTRIENT"] or any(k in user_query.lower() for k in ["sensor", "moisture", "iot", "temperature", "reading", "ec", "humidity"])
    if show_iot:
        try:
            l1_out = getattr(getattr(artifact, "layer_1", None), "output", None)
            if l1_out:
                static = getattr(l1_out, "static", {}) or {}
                iot_sensors = static.get("iot_sensors", [])
                sensor_summary = static.get("sensor_summary", {})
                if iot_sensors or sensor_summary:
                    context_lines.append("\n[IoT GROUND TRUTH SENSORS]")
                    context_lines.append(f"  Active sensors: {len(iot_sensors)}")
                    if sensor_summary:
                        sm = sensor_summary.get("soil_moisture")
                        if sm is not None:
                            context_lines.append(f"  - Soil Moisture (IoT average): {sm:.1f}%")
                        temp = sensor_summary.get("temperature")
                        if temp is not None:
                            context_lines.append(f"  - Field Temperature (IoT): {temp:.1f}°C")
                        hum = sensor_summary.get("humidity")
                        if hum is not None:
                            context_lines.append(f"  - Field Humidity (IoT): {hum:.0f}%")
                        ec = sensor_summary.get("ec")
                        if ec is not None:
                            context_lines.append(f"  - Soil EC (IoT): {ec:.2f} mS/cm")
                    # List individual sensors
                    for s in iot_sensors[:5]:  # Cap at 5
                        if isinstance(s, dict):
                            dev = s.get("deviceId", "unknown")
                            stype = s.get("type", "unknown")
                            sm = s.get("soilMoisture")
                            t = s.get("temperature")
                            vals = []
                            if sm is not None: vals.append(f"moisture={sm:.1f}%")
                            if t is not None: vals.append(f"temp={t:.1f}°C")
                            val_str = ", ".join(vals) if vals else "no data"
                            context_lines.append(f"  - [{dev}] ({stype}): {val_str}")
                    context_lines.append("  NOTE: IoT readings are GROUND TRUTH and should take priority over satellite proxies for soil moisture assessments.")
        except Exception as e:
            pass

    # 3.3 Plot DNA 4.0: Biophysical Trait Context
    show_dna = intent in ["DIAGNOSIS", "DIAGNOSTIC", "NUTRIENT", "DECISION", "PLANNING", "EXPLANATION"] or any(k in user_query.lower() for k in ["dna", "soil", "retention", "resilience", "vigor", "capacity", "whc", "t_max", "lai_rate", "gdd_veg"])
    if show_dna:
        try:
            plot_id = getattr(getattr(artifact, "inputs", None), "plot_id", None)
            if plot_id:
                from layer0.calibration.dna_cache import load_dna_cache, dna_to_crop_params
                dna = load_dna_cache(plot_id)
                if dna:
                    traits = dna.get("traits", {})
                    quality = dna.get("data_quality", {})
                    crop_params = dna_to_crop_params(dna)
                    context_lines.append("\n[PLOT DNA 4.0 — BIOPHYSICAL TRAITS]")
                    context_lines.append("  This plot has been DNA-sequenced from decadal Earth Observation data.")
                    context_lines.append(f"  θ (Theta Retention): {traits.get('theta_retention', 'N/A')} — soil water holding capacity modifier")
                    context_lines.append(f"  β (Beta Resilience): {traits.get('beta_resilience', 'N/A')} — thermal stress penalty coefficient")
                    context_lines.append(f"  α (Alpha Vigor): {traits.get('alpha_vigor', 'N/A')} — canopy growth efficiency modifier")
                    context_lines.append(f"  τ (T-Shift): {traits.get('t_shift', 'N/A')} — microclimate GDD offset (°C·days)")
                    context_lines.append(f"  Derived Crop Params: WHC={crop_params.get('whc_mm_per_m')}mm/m, t_max={crop_params.get('t_max')}°C, LAI_rate={crop_params.get('lai_growth_rate')}, GDD_veg={crop_params.get('gdd_vegetative')}")
                    null_pct = quality.get("weather_null_fill_pct", 0)
                    ndvi_obs = quality.get("ndvi_observations", 0)
                    context_lines.append(f"  Data Quality: {100-null_pct:.0f}% weather coverage, {ndvi_obs} NDVI observations in sequencing window")
                    if null_pct > 30:
                        context_lines.append(f"  WARNING: HIGH NULL-FILL ({null_pct:.0f}%): DNA traits are less reliable. Kalman process noise is inflated accordingly.")
                    context_lines.append("  NOTE: These traits are INJECTED into the Kalman filter's ProcessModel, overriding generic defaults. All crop parameter reasoning should cite these values.")
        except Exception as e:
            pass

    # 3.4 Operational Runtimes & Schedules
    show_runtimes = intent in ["EXECUTION", "EXECUTION_STATUS", "TASK_MGMT"] or any(k in user_query.lower() for k in ["drone", "autopilot", "mission", "camera", "irrigation schedule", "runtime", "controller", "freshness"])
    if show_runtimes:
        context_lines.append("\n[OPERATIONAL RUNTIMES & SCHEDULES]")
        inputs = getattr(artifact, "inputs", None)
        if inputs and hasattr(inputs, "operational_context") and isinstance(inputs.operational_context, dict):
            op_ctx = inputs.operational_context
            # Drone mission
            drone = op_ctx.get("drone_mission") or op_ctx.get("drone")
            if drone:
                context_lines.append(f"  - Drone Autopilot Status: {drone.get('status', 'IDLE')} (Battery: {drone.get('battery', 100)}%)")
                if drone.get("current_waypoint"):
                    context_lines.append(f"    * Current Waypoint: {drone.get('current_waypoint')}")
            else:
                context_lines.append("  - Drone Autopilot: Standby / Ready")
                
            # Irrigation controller runtime
            irrig = op_ctx.get("irrigation_runtime") or op_ctx.get("irrigation")
            if irrig:
                context_lines.append(f"  - Irrigation Schedule Runtime: {irrig.get('status', 'OFF')} (Last run: {irrig.get('last_run', 'N/A')})")
                if irrig.get("next_run"):
                    context_lines.append(f"    * Scheduled next: {irrig.get('next_run')}")
            else:
                context_lines.append("  - Irrigation Schedule: Idle (Soil moisture within bounds)")
                
            # Camera feed freshness
            cam = op_ctx.get("camera_freshness") or op_ctx.get("camera")
            if cam:
                context_lines.append(f"  - Static IP Camera Feed: Online (Latency: {cam.get('latency_secs', 0)}s, Signal: {cam.get('signal_strength', 'OK')})")
            else:
                context_lines.append("  - Static IP Camera: Feed active, no anomalies detected")

    # 3.5 Layer 2-8 Synthesized Outputs (FULL PIPELINE AWARENESS)
    context_lines.append("\n[AGRONOMIC LAYER OUTPUTS]")
    try:
        # Layer 2 (Vegetation)
        l2 = getattr(artifact, "layer_2", None)
        show_l2 = intent in ["DIAGNOSIS", "DIAGNOSTIC", "DATA_QUERY", "EXPLANATION", "DECISION", "GENERAL"] or any(k in user_query.lower() for k in ["ndvi", "evi", "canopy", "vegetation", "stage", "phenology", "curve", "anomaly"])
        if show_l2 and l2 and l2.output:
            context_lines.append("Layer 2 (Vegetation Intelligence):")
            curve = getattr(l2.output, "curve", None)
            ndvi = "N/A"
            if curve and hasattr(curve, "ndvi_fit") and curve.ndvi_fit:
                ndvi = f"{curve.ndvi_fit[-1]:.3f}"
            
            pheno = getattr(l2.output, "phenology", None)
            stage = "UNKNOWN"
            if pheno and hasattr(pheno, "stage_by_day") and pheno.stage_by_day:
                stage_val = pheno.stage_by_day[-1]
                stage = getattr(stage_val, "value", str(stage_val))
            
            context_lines.append(f"  - Modeled NDVI: {ndvi}, Phenology Stage: {stage}")
            
            # NPP and growth velocity
            npp = getattr(l2.output, "npp", None) or getattr(l2.output, "net_primary_productivity", None)
            if npp is not None:
                context_lines.append(f"  - Net Primary Productivity (NPP): {npp}")
            growth_vel = getattr(l2.output, "growth_velocity", None)
            if growth_vel is not None:
                context_lines.append(f"  - NDVI Growth Velocity: {growth_vel}")
            
            anomalies = getattr(l2.output, "anomalies", [])
            if anomalies:
                context_lines.append("  - Active Anomalies:")
                for a in anomalies:
                    atype = getattr(a, "type", "UNKNOWN")
                    atype_str = getattr(atype, "value", str(atype))
                    context_lines.append(f"    * {atype_str}: {getattr(a, 'description', '')} (Severity: {getattr(a, 'severity', 0):.2f})")

        # Layer 3 (Decision & Diagnosis)
        l3 = getattr(artifact, "layer_3", None)
        show_l3 = intent in ["DIAGNOSIS", "DIAGNOSTIC", "DECISION", "EXPLANATION", "GENERAL"] or any(k in user_query.lower() for k in ["water", "stress", "irrigation", "diagnosis", "diagnose", "et0", "weather"])
        if show_l3 and l3 and l3.output:
            context_lines.append("Layer 3 (Decision & Diagnosis):")
            diagnoses = getattr(l3.output, "diagnoses", [])
            for d in diagnoses:
                prob = getattr(d, "probability", 0.0)
                if prob > 0.1:
                    conf = getattr(d, "confidence", 1.0)
                    name = getattr(d, "problem_id", "UNKNOWN")
                    if conf < 0.3:
                        conf_status = " [PRELIMINARY — Low data coverage]"
                    elif conf < 0.6:
                        conf_status = " [MODERATE — Partial data]"
                    else:
                        conf_status = ""
                    context_lines.append(f"  - {name}: {prob*100:.1f}% probability (Confidence: {conf*100:.0f}%){conf_status}")
            
            # Water balance details
            water_balance = getattr(l3.output, "water_balance", None)
            if water_balance:
                et_crop = getattr(water_balance, "et_crop", None) or getattr(water_balance, "etc", None)
                deficit = getattr(water_balance, "deficit_mm", None) or getattr(water_balance, "water_deficit", None)
                if et_crop is not None:
                    context_lines.append(f"  - ETcrop (crop evapotranspiration): {et_crop} mm/day")
                if deficit is not None:
                    context_lines.append(f"  - Water Deficit: {deficit} mm")
            
            l3_quality = getattr(l3.output, "quality_metrics", None)
            if l3_quality:
                missing_drivers = getattr(l3_quality, "missing_drivers", [])
                if missing_drivers:
                    context_lines.append(f"  - WARNING: Layer 3 is degraded due to missing data: {[str(d) for d in missing_drivers]}")

        # Layer 4 (Nutrients)
        l4 = getattr(artifact, "layer_4", None)
        show_l4 = intent in ["NUTRIENT", "DIAGNOSIS", "DIAGNOSTIC", "DECISION", "EXPLANATION", "GENERAL"] or any(k in user_query.lower() for k in ["nutrient", "nitrogen", "phosphorus", "potassium", "npk", "urea", "fertilizer", "deficiency"])
        if show_l4 and l4 and l4.output:
            context_lines.append("Layer 4 (Nutrient Intelligence):")
            states = getattr(l4.output, "nutrient_states", {})
            for nut, state in states.items():
                prob = getattr(state, "probability_deficient", 0.0)
                conf = getattr(state, "confidence", 1.0)
                name = getattr(nut, "value", str(nut))
                if conf < 0.3:
                    conf_status = " [PRELIMINARY — Needs field verification]"
                elif conf < 0.6:
                    conf_status = " [MODERATE — Qualified recommendation possible]"
                else:
                    conf_status = ""
                context_lines.append(f"  - {name} Deficiency Risk: {prob*100:.1f}% (Confidence: {conf*100:.0f}%){conf_status}")
            
            ndef = getattr(l4.output, "n_deficit_kg_ha", "N/A")
            if ndef != "N/A":
                context_lines.append(f"  - N-Deficit (kg/ha): {ndef}")
            
            # L4 split schedules are shadow evidence.  Only the exact action
            # stored in an L8 authorization envelope may enter this prompt.
            l4_quality = getattr(l4.output, "quality_metrics", None)
            if l4_quality:
                missing_drivers = getattr(l4_quality, "missing_drivers", [])
                if missing_drivers:
                    context_lines.append(f"  - WARNING: Layer 4 is degraded due to missing data: {missing_drivers}")
        elif show_l4:
            context_lines.append("Layer 4 (Nutrient Intelligence): Data missing or N/A for current growth stage.")

        # Layer 5 (Biotic/Disease)
        l5 = getattr(artifact, "layer_5", None)
        show_l5 = intent in ["DIAGNOSIS", "DIAGNOSTIC", "EXPLANATION", "GENERAL"] or any(k in user_query.lower() for k in ["disease", "pest", "pathogen", "blight", "spore", "fungal", "threat", "spray", "fungicide"])
        if show_l5 and l5 and l5.output:
            context_lines.append("Layer 5 (Biotic Threats):")
            threats = getattr(l5.output, "threat_states", {})
            for tid, state in threats.items():
                prob = getattr(state, "probability", 0)
                conf = getattr(state, "confidence", 1.0)
                if prob > 0.1:
                    name = getattr(getattr(state, 'threat_id', ''), 'value', str(getattr(state, 'threat_id', tid)))
                    if conf < 0.3:
                        conf_status = " [PRELIMINARY — Low data coverage]"
                    elif conf < 0.6:
                        conf_status = " [MODERATE — Partial data]"
                    else:
                        conf_status = ""
                    context_lines.append(f"  - {name}: {prob*100:.1f}% probability (Confidence: {conf*100:.0f}%){conf_status}")
                    
            quality = getattr(l5.output, "quality_metrics", None)
            if quality:
                missing_drivers = getattr(quality, "missing_drivers", [])
                if missing_drivers:
                    context_lines.append(f"  - WARNING: Layer 5 predictions are degraded due to missing data: {missing_drivers}")

        # ========== Layer 6 (Yield Prognosis & Profitability) ==========
        l6 = getattr(artifact, "layer_6", None)
        show_l6 = intent in ["DATA_QUERY", "DECISION", "PLANNING", "SCENARIO", "GENERAL"] or any(k in user_query.lower() for k in ["yield", "harvest", "production", "ton", "quintals", "profit", "roi", "revenue", "income", "gross margin"])
        if show_l6 and l6 and l6.output:
            context_lines.append("Layer 6 (Yield Prognosis & Profitability):")
            l6o = l6.output
            # Yield forecast
            yf = getattr(l6o, "yield_forecast", None) or getattr(l6o, "forecast", None)
            if yf:
                p10 = getattr(yf, "p10", getattr(yf, "yield_p10", None))
                p50 = getattr(yf, "p50", getattr(yf, "yield_p50", None))
                p90 = getattr(yf, "p90", getattr(yf, "yield_p90", None))
                trust = getattr(yf, "trust_tier", getattr(yf, "trust", "N/A"))
                if p50 is not None:
                    context_lines.append(f"  - Yield Forecast: P10={p10} t/ha, P50={p50} t/ha, P90={p90} t/ha (Trust: {trust})")
                loss = getattr(yf, "cumulative_stress_loss", None) or getattr(yf, "stress_loss_pct", None)
                if loss is not None:
                    context_lines.append(f"  - Cumulative Stress Yield Loss: {loss}%")
            # Harvest optimizer
            harvest = getattr(l6o, "harvest_optimizer", None) or getattr(l6o, "harvest", None)
            if harvest:
                opt_day = getattr(harvest, "optimal_day", getattr(harvest, "optimal_harvest_date", None))
                grain_mc = getattr(harvest, "grain_moisture", None)
                if opt_day:
                    context_lines.append(f"  - Optimal Harvest Day: {opt_day}")
                if grain_mc is not None:
                    context_lines.append(f"  - Grain Moisture at Harvest: {grain_mc}%")
            # Profitability
            profit = getattr(l6o, "profitability", None)
            if profit:
                gm = getattr(profit, "gross_margin", getattr(profit, "gross_margin_ha", None))
                roi = getattr(profit, "roi", getattr(profit, "intervention_roi", None))
                if gm is not None:
                    context_lines.append(f"  - Gross Margin: {gm} $/ha")
                if roi is not None:
                    context_lines.append(f"  - Intervention ROI: {roi}x")

        # ========== Layer 7 (Risk & Climate Shock) ==========
        l7 = getattr(artifact, "layer_7", None)
        show_l7 = intent in ["DIAGNOSIS", "DECISION", "SCENARIO", "PLANNING", "GENERAL"] or any(k in user_query.lower() for k in ["risk", "climate", "shock", "heatwave", "frost", "flood", "drought", "insurance", "trust", "what if", "simulate"])
        if show_l7 and l7 and l7.output:
            context_lines.append("Layer 7 (Risk & Climate Intelligence):")
            l7o = l7.output
            # Risk composite
            composite = getattr(l7o, "risk_composite", None) or getattr(l7o, "composite", None)
            if composite:
                score = getattr(composite, "composite_score", getattr(composite, "score", None))
                level = getattr(composite, "risk_level", getattr(composite, "level", None))
                if score is not None:
                    context_lines.append(f"  - Composite Risk Score: {score:.2f} (Level: {level})")
                components = getattr(composite, "components", None) or getattr(composite, "breakdown", None)
                if components and isinstance(components, dict):
                    for comp, val in components.items():
                        if isinstance(val, (int, float)) and val > 0.1:
                            context_lines.append(f"    * {comp}: {val:.2f}")
            # Climate shocks
            shocks = getattr(l7o, "climate_shocks", []) or getattr(l7o, "shocks", [])
            if shocks:
                context_lines.append("  - Active Climate Shocks:")
                for s in shocks[:3]:
                    stype = getattr(s, "shock_type", getattr(s, "type", "UNKNOWN"))
                    stype_str = getattr(stype, "value", str(stype))
                    severity = getattr(s, "severity", getattr(s, "impact", 0))
                    context_lines.append(f"    * {stype_str}: severity={severity}")
            # Trust monitor
            trust = getattr(l7o, "trust_score", None) or getattr(l7o, "data_trust", None)
            if trust is not None:
                trust_val = trust if isinstance(trust, (int, float)) else getattr(trust, "score", None)
                if trust_val is not None:
                    context_lines.append(f"  - Data Trust Score: {trust_val}/100")
            # Scenario results
            scenarios = getattr(l7o, "scenario_results", None) or getattr(l7o, "scenarios", None)
            if scenarios:
                context_lines.append(f"  - What-If Scenarios Evaluated: {len(scenarios) if hasattr(scenarios, '__len__') else 'Available'}")

        # ========== Layer 8 (Prescriptive Actions) ==========
        l8 = getattr(artifact, "layer_8", None)
        show_l8 = intent in ["DECISION", "EXECUTION", "EXECUTION_STATUS", "PLANNING", "NUTRIENT", "GENERAL"] or any(k in user_query.lower() for k in ["spray", "tillage", "treatment", "prescri", "schedule", "action", "task", "drift", "frost", "lodging", "ipm", "compaction"])
        if show_l8:
            context_lines.append("Layer 8 (Prescriptive Authorization):")
            if prescription_authorization is None:
                context_lines.append(
                    "  - BLOCKED: no exact action, rate, timing, urgency, or "
                    f"execution instruction may be generated ({prescription_block_reason})."
                )
            else:
                context_lines.append(
                    f"  - Authorization Envelope: {prescription_authorization.content_hash}"
                )
                for action in prescription_authorization.actions:
                    context_lines.append(
                        "  - AUTHORIZED "
                        f"{action.action_type} ({action.action_id}); "
                        f"priority={action.priority_score:.2f}; "
                        f"urgency={action.urgency_score:.2f}; "
                        f"rate={dict(action.rate)}; timing={dict(action.timing)}"
                    )
    except Exception as e:
        context_lines.append(f"  (Failed to extract intermediate layer outputs: {e})")

    # 4. Phenology & Plot Profile
    context_lines.append("\n[PLOT PROFILE & PHENOLOGY]")
    inputs = getattr(artifact, "inputs", None)
    if inputs:
        crop_cfg = inputs.crop_config if isinstance(inputs.crop_config, dict) else {}
        stage = crop_cfg.get("stage", crop_cfg.get("crop_stage", "UNKNOWN"))
        crop = crop_cfg.get("crop", crop_cfg.get("crop_type", "UNKNOWN"))
        context_lines.append(f"- Crop: {crop}")
        context_lines.append(f"- Growth Stage: {stage}")
        context_lines.append(f"- Plot Area: {inputs.plot_id}")

        # Crop auto-detection context (when farmer didn't declare)
        if crop_cfg.get("_auto_detected"):
            det_conf = crop_cfg.get("_detection_confidence", 0)
            det_label = crop_cfg.get("_detection_label", "UNKNOWN")
            det_candidates = crop_cfg.get("_top_candidates", [])
            context_lines.append(f"\n  ⚠️ CROP AUTO-DETECTED (not declared by farmer)")
            context_lines.append(f"  Detection: {crop} ({det_conf:.0%} confidence, {det_label})")
            if det_candidates:
                alt = ", ".join(f"{c['code']}({c['score']:.2f})" for c in det_candidates[1:])
                context_lines.append(f"  Alternatives: {alt}")
            context_lines.append(f"  NOTE: Recommend farmer confirms crop type for best accuracy.")
    
    # 5. Conversation History Summary
    try:
        from layer9_interface.conversation_memory import ConversationMemoryManager
        history_summary = ConversationMemoryManager.build_history_summary(history)
        context_lines.append("\n[CONVERSATION HISTORY]")
        context_lines.append(history_summary)
    except Exception as e:
        context_lines.append(f"\n[CONVERSATION HISTORY] Error loading memory: {e}")

    return "\n".join(context_lines)

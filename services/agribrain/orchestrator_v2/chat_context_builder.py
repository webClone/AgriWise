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
    l10 = getattr(artifact, "layer_10", None)
    if l10 and getattr(l10, "output", None):
        qr = getattr(l10.output, "quality_report", {})
        if qr:
            context_lines.append("\n[SYSTEM QUALITY & DATA RELIABILITY]")
            context_lines.append(f"- Overall Quality Score: {qr.get('overall_quality_score', 0):.2f}")
            context_lines.append(f"- Hard Gates Passed: {qr.get('hard_gates_passed', 0)}/12")
            context_lines.append(f"- Spatial Anomaly Trustworthy: {qr.get('spatial_anomaly_trustworthy', False)}")
            context_lines.append(f"- Missing Core Drivers: {qr.get('missing_core_drivers', [])}")
            context_lines.append(f"- Degradation Modes: {qr.get('degradation_modes', [])}")

    # 3. L0 / L1 Deep Metrics
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

            # Emulate L1 dict
            weather_active = bool(timeseries)
            optical_active = any(t.get("ndvi") is not None for t in timeseries)
            sar_active = any(t.get("vv_db") is not None for t in timeseries)
            sources_active = sum([weather_active, optical_active, sar_active])
            
            # Create a mock ndvi_records from timeseries to feed L1 enricher
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

    except Exception as e:
        context_lines.append(f"  (Failed to extract deep metrics: {e})")

    # 3.25 IoT Sensor Ground Truth
    try:
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

    # 3.5 Layer 2-6 Synthesized Outputs
    context_lines.append("\n[AGRONOMIC LAYER OUTPUTS]")
    try:
        # Layer 2 (Vegetation)
        l2 = getattr(artifact, "layer_2", None)
        if l2 and l2.output:
            context_lines.append("Layer 2 (Vegetation Intelligence):")
            ndvi = getattr(l2.output, "ndvi", "N/A")
            pheno = getattr(l2.output, "phenology", None)
            stage = getattr(pheno, "stage", "UNKNOWN") if pheno else "UNKNOWN"
            context_lines.append(f"  - NDVI: {ndvi}, Phenology Stage: {stage}")

        # Layer 3 (Decision & Diagnosis)
        l3 = getattr(artifact, "layer_3", None)
        if l3 and l3.output:
            context_lines.append("Layer 3 (Decision & Diagnosis):")
            diagnoses = getattr(l3.output, "diagnoses", [])
            for d in diagnoses:
                prob = getattr(d, "probability", 0.0)
                if prob > 0.1:
                    conf = getattr(d, "confidence", 1.0)
                    name = getattr(d, "problem_id", "UNKNOWN")
                    # Nuanced confidence descriptor (not binary LOW/ok)
                    if conf < 0.3:
                        conf_status = " [PRELIMINARY — Low data coverage]"
                    elif conf < 0.6:
                        conf_status = " [MODERATE — Partial data]"
                    else:
                        conf_status = ""
                    context_lines.append(f"  - {name}: {prob*100:.1f}% probability (Confidence: {conf*100:.0f}%){conf_status}")
            
            l3_quality = getattr(l3.output, "quality_metrics", None)
            if l3_quality:
                missing_drivers = getattr(l3_quality, "missing_drivers", [])
                if missing_drivers:
                    context_lines.append(f"  - WARNING: Layer 3 is degraded due to missing data: {[str(d) for d in missing_drivers]}")

        # Layer 4 (Nutrients)
        l4 = getattr(artifact, "layer_4", None)
        if l4 and l4.output:
            context_lines.append("Layer 4 (Nutrient Intelligence):")
            states = getattr(l4.output, "nutrient_states", {})
            for nut, state in states.items():
                prob = getattr(state, "probability_deficient", 0.0)
                conf = getattr(state, "confidence", 1.0)
                name = getattr(nut, "value", str(nut))
                # Nuanced confidence descriptor — avoids LLM self-censorship
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
                
            l4_quality = getattr(l4.output, "quality_metrics", None)
            if l4_quality:
                missing_drivers = getattr(l4_quality, "missing_drivers", [])
                if missing_drivers:
                    context_lines.append(f"  - WARNING: Layer 4 is degraded due to missing data: {missing_drivers}")
        else:
            context_lines.append("Layer 4 (Nutrient Intelligence): Data missing or N/A for current growth stage.")

        # Layer 5 (Biotic/Disease)
        l5 = getattr(artifact, "layer_5", None)
        if l5 and l5.output:
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
    
    # 5. Conversation History Summary
    try:
        from layer9_interface.conversation_memory import ConversationMemoryManager
        history_summary = ConversationMemoryManager.build_history_summary(history)
        context_lines.append("\n[CONVERSATION HISTORY]")
        context_lines.append(history_summary)
    except Exception as e:
        context_lines.append(f"\n[CONVERSATION HISTORY] Error loading memory: {e}")

    return "\n".join(context_lines)

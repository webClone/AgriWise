import random
from services.agribrain.layer10_sire.schema import (
    Layer10Output,
    Layer10Input,
    ExplainabilityPack,
    DriverWeight,
    ModelEquation,
    ExplainabilityProvenance,
    ExplainabilityConfidence,
    ConfidencePenalty,
    SurfaceType
)

def build_key_evidence_drivers(l10_input: Layer10Input, output: Layer10Output) -> list[DriverWeight]:
    drivers = []
    
    # ── 1. NDVI Signal ──────────────────────────────────────────────────────
    # Priority: L10 surface pack (real rendered values) → field tensor daily state → fallback
    ndvi_latest = None
    ndvi_source = "estimated"

    # Best source: the actual NDVI_CLEAN surface that L10 rendered
    for surf in getattr(output, "surface_pack", []):
        st = getattr(surf, "semantic_type", None)
        st_val = st.value if hasattr(st, "value") else str(st)
        if st_val == "NDVI_CLEAN" and getattr(surf, "values", None):
            pixel_vals = []
            for row in surf.values:
                for v in row:
                    if v is not None and not (isinstance(v, float) and (v != v)):  # skip NaN
                        pixel_vals.append(v)
            if pixel_vals:
                ndvi_latest = sum(pixel_vals) / len(pixel_vals)
                ndvi_source = "surface"
            break

    # Fallback: field tensor plot_timeseries or daily_state
    if ndvi_latest is None:
        ft = getattr(l10_input, "field_tensor", None)
        # Try plot_timeseries first
        if ft and hasattr(ft, "plot_timeseries") and isinstance(ft.plot_timeseries, list) and len(ft.plot_timeseries) > 0:
            ts = ft.plot_timeseries
            ndvis = [float(r.get("ndvi")) for r in ts if r.get("ndvi") is not None]
            if ndvis:
                ndvi_latest = ndvis[-1]
                ndvi_source = "tensor"
        # Try daily_state
        elif ft and hasattr(ft, "daily_state") and isinstance(ft.daily_state, dict) and "ndvi" in ft.daily_state:
            ndvis = ft.daily_state["ndvi"]
            if ndvis and len(ndvis) > 0:
                ndvi_latest = float(ndvis[-1])
                ndvi_source = "tensor"
    
    # Last resort fallback
    if ndvi_latest is None:
        ndvi_latest = 0.0
        ndvi_source = "no_data"

    drivers.append(DriverWeight(
        name="NDVI Contribution",
        value=ndvi_latest,
        role="positive" if ndvi_latest > 0.3 else "uncertainty",
        description=f"Strongest driver of current canopy signal (source: {ndvi_source})." if ndvi_source == "surface"
                    else f"NDVI from {ndvi_source} — may not reflect latest satellite pass.",
        formatted_value=f"{ndvi_latest:.3f}"
    ))

    # ── 2. Recent Rainfall ──────────────────────────────────────────────────
    ft = getattr(l10_input, "field_tensor", None)
    precip = 0.0
    if ft and hasattr(ft, "plot_timeseries") and isinstance(ft.plot_timeseries, list) and len(ft.plot_timeseries) > 0:
        ts = ft.plot_timeseries
        precips = [float(r.get("rain", r.get("precipitation", 0.0)) or 0.0) for r in ts]
        if precips:
            precip = sum(precips[-3:])  # Last 3 days sum
    elif ft and hasattr(ft, "daily_state") and isinstance(ft.daily_state, dict) and "precipitation" in ft.daily_state:
        precips = ft.daily_state["precipitation"]
        if precips and len(precips) > 0:
            precip = sum(precips[-3:])  # Last 3 days sum
            
    if precip > 0:
        drivers.append(DriverWeight(
            name="Recent Rainfall",
            value=precip,
            role="positive" if precip < 30 else "negative",
            description="Supports emergence but may increase fungal risk." if precip > 10 else "Maintains adequate moisture.",
            formatted_value=f"{precip:.1f} mm"
        ))
        
    # ── 3. Cloud Cover / Optical Quality ────────────────────────────────────
    # Check multiple signals — the degradation_mode alone is unreliable because
    # it defaults to NORMAL in the schema and may not be updated by all code paths.
    qr = getattr(output, "quality_report", None)
    degrad = getattr(qr, "degradation_mode", None)
    degrad_str = str(degrad.value) if hasattr(degrad, "value") else str(degrad)
    warnings = getattr(qr, "warnings", [])
    missing_upstream = getattr(qr, "missing_upstream", [])
    reliability = getattr(qr, "reliability_score", 1.0)
    
    has_cloud_warning = any("cloud" in w.lower() or "optical" in w.lower() or "degrad" in w.lower() for w in warnings)
    has_optical_gap = any("L2" in m or "optical" in m.lower() or "sentinel-2" in m.lower() for m in missing_upstream)
    is_degraded = degrad_str not in ("NORMAL",) or reliability < 0.9 or has_cloud_warning or has_optical_gap
    
    if is_degraded:
        # Determine severity
        is_severe = degrad_str in ("DATA_GAP", "NO_SPATIAL") or reliability < 0.5
        drivers.append(DriverWeight(
            name="Cloud Cover Impact",
            value=1.0 - reliability,
            role="negative" if is_severe else "uncertainty",
            description=f"Optical data degraded (mode: {degrad_str}, reliability: {reliability:.0%}); relying on interpolation.",
            formatted_value="High" if is_severe else "Moderate"
        ))
    else:
        drivers.append(DriverWeight(
            name="Optical Clarity",
            value=1.0,
            role="positive",
            description="Clear sky observations confirm surface states.",
            formatted_value="Clear"
        ))

    # ── 4. SAR Backscatter ──────────────────────────────────────────────────
    if ft and hasattr(ft, "provenance_log") and ft.provenance_log:
        sources = ft.provenance_log[-1].get("sources", {})
        if "s1" in sources or "Sentinel-1" in sources:
            drivers.append(DriverWeight(
                name="SAR Backscatter",
                value=0.8,
                role="positive",
                description="Reliable moisture and structural proxy used.",
                formatted_value="Stable"
            ))

    return drivers[:5]

def build_premium_packs(l10_input: Layer10Input, output: Layer10Output) -> Layer10Output:
    """Builds the Explainability, Scenario, and History UI packs from live pipeline data."""
    try:
    
        # 1. Provide a baseline set of Explainability Packs
        exp_pack = {}
        run_id = output.run_id
        
        # Base Confidence from pipeline quality report
        qscore = output.quality_report.reliability_score
        qpens = [ConfidencePenalty("Pipeline degraded", 1.0 - qscore)] if qscore < 1.0 else []
        
        # Try grabbing live Sentinel-2 info
        l1 = l10_input.field_tensor
        l3 = l10_input.decision
        s2_sources = getattr(l1, "provenance", {}).get("sources", ["Sentinel-2"]) if l1 else ["Sentinel-2"]
        
        # Calculate precip from field tensor
        ft = getattr(l10_input, "field_tensor", None)
        precip = 0.0
        if ft and hasattr(ft, "plot_timeseries") and isinstance(ft.plot_timeseries, list) and len(ft.plot_timeseries) > 0:
            ts = ft.plot_timeseries
            precips = [float(r.get("rain", r.get("precipitation", 0.0)) or 0.0) for r in ts]
            if precips:
                precip = sum(precips[-3:])  # Last 3 days sum
        elif ft and hasattr(ft, "daily_state") and isinstance(ft.daily_state, dict) and "precipitation" in ft.daily_state:
            precips = ft.daily_state["precipitation"]
            if precips and len(precips) > 0:
                precip = sum(precips[-3:])  # Last 3 days sum

        has_farmer_logs = False
        if ft and hasattr(ft, "daily_state") and isinstance(ft.daily_state, dict):
            if any(k in ft.daily_state for k in ["irrigation", "irrigation_log", "fertilizer", "fertilizer_log"]):
                has_farmer_logs = True

        # Mapping between SurfaceType and the mode properties
        core_modes = [
            ("NDVI_CLEAN", "Canopy", "Photosynthetic vigor / canopy density", "Standard normalized difference vegetation index computation.", "(NIR - Red) / (NIR + Red)", "NIR, Red"),
            ("NDVI_DEVIATION", "Veg Attention", "Localized vigor deviation", "Calculates difference of pixels relative to spatial plot baseline.", "NDVI - Mean(NDVI)", "NDVI"),
            ("BASELINE_ANOMALY", "Veg Attention Anomaly", "Localized vigor deviation", "Calculates pixel deviation relative to long-term historical baseline.", "NDVI - Historical_Mean(NDVI)", "NDVI, History"),
            ("WATER_STRESS_PROB", "Water Status", "Possible irrigation deficit", "Computes current proxy moisture vs capacity.", "1 - (SM_current / SM_capacity) * exp(VPD)", "SAR_VH, Weather"),
            ("NUTRIENT_STRESS_PROB", "Nutrient Status", "Possible nutrient limitation", "Calculates chlorophyll-depletion probability from red-edge proxies.", "1 - (Chl_current / Chl_potential)", "RedEdge, NIR"),
            ("SALINITY_STRESS", "Soil Salinity", "Possible osmotic salinity stress", "Estimates soil salinity hazard probability based on EC and pH indicators.", "ƒ(EC_sensor, pH_sensor, Soil_prior)", "EC, pH"),
            ("COMPOSITE_RISK", "Composite Risk", "Dominant combined stress driver", "Calculates stage-weighted multi-source risk score.", "Kw * Water_Stress + Kn * Nutrient_Stress + Kd * Disease_Pressure + Ks * Salinity_Stress + Kdev * NDVI_Dev", "Water, Nutrient, Disease, Salinity, NDVI_Dev"),
            ("DATA_RELIABILITY", "Data Reliability", "Data quality / freshness / coverage", "Evaluates observation age, cloud cover, and spatial coverage.", "Freshness * (1 - Cloud_pct) * Spatial_coverage", "Sentinel-2, Sentinel-1, Metadata"),
            ("RESOLUTION_COVERAGE", "Resolution Coverage", "Spatial precision / provenance limit", "Calculates pixel-level resolution and source sensor scales.", "GSD_metrics(active_sensors)", "Telemetry_Metadata")
        ]

        for st_name, display_name, def_driver, eq_descr, eq_expr, eq_layers in core_modes:
            # Look up corresponding SurfaceArtifact in output.surface_pack
            surf = None
            for s in getattr(output, "surface_pack", []):
                st_val = s.semantic_type.value if hasattr(s.semantic_type, "value") else str(s.semantic_type)
                if st_val == st_name:
                    surf = s
                    break
            
            grounding_class = "PROXY_SPATIAL"
            observed_ratio = 0.0
            raster_basis = []
            mean_val = None
            p10_val = None
            p90_val = None
            
            if surf is not None:
                grounding_class = getattr(surf, "grounding_class", "PROXY_SPATIAL") or "PROXY_SPATIAL"
                observed_ratio = getattr(surf, "observed_ratio", 0.0)
                raster_basis = getattr(surf, "raster_basis", []) or []
                
                # Compute stats if values are available
                if getattr(surf, "values", None):
                    pixel_vals = []
                    for row in surf.values:
                        for v in row:
                            if v is not None and not (isinstance(v, float) and (v != v)):  # skip NaN
                                pixel_vals.append(v)
                    if pixel_vals:
                        pixel_vals.sort()
                        mean_val = sum(pixel_vals) / len(pixel_vals)
                        p10_val = pixel_vals[int(len(pixel_vals) * 0.1)]
                        p90_val = pixel_vals[int(len(pixel_vals) * 0.9)]

            # Determine dominant driver conservatively
            driver = def_driver
            if st_name == "WATER_STRESS_PROB":
                if observed_ratio >= 0.3 and precip < 1.0:
                    driver = "Possible irrigation deficit"
                elif precip >= 5.0:
                    driver = "Atmospheric drought pressure"
                else:
                    driver = "Moisture stress signal — irrigation history unavailable"
            elif st_name == "NUTRIENT_STRESS_PROB":
                has_red_edge = any(
                    b.lower() in {"ndre", "red_edge", "rededge", "b5", "b6", "b7", "b8a", "ci_red_edge"}
                    for b in raster_basis
                )
                if not has_red_edge:
                    driver = "Nutrient stress proxy — red-edge evidence unavailable"
                elif precip > 30.0:
                    driver = "Likely water-limited nutrient uptake"
                else:
                    driver = "Possible nutrient limitation"
            elif st_name == "COMPOSITE_RISK" and surf is not None and "dominant_driver" in getattr(surf, "provenance", {}):
                prov_driver = surf.provenance["dominant_driver"]
                if prov_driver == "water":
                    driver = "Dominant driver: Moisture deficit stress"
                elif prov_driver == "nutrient":
                    driver = "Dominant driver: Nutrient limitation stress"
                elif prov_driver == "disease":
                    driver = "Dominant driver: Disease pressure stress"
                elif prov_driver == "ndvi_dev":
                    driver = "Dominant driver: Localized vigor deviation"
                else:
                    driver = "Dominant combined stress driver"
            
            # Determine recommended action conservatively based on grounding class
            action = ""
            action_level = "monitor"
            
            if st_name == "NDVI_CLEAN":
                action_level = "monitor"
                if grounding_class == "RASTER_GROUNDED":
                    action = "Monitor growth stage in high-vigor zones; verify field condition on schedule."
                elif grounding_class == "PARTIAL_RASTER_GROUNDED":
                    action = "Monitor canopy condition; some pixels are gap-filled. Switch to Vegetation Attention to inspect localized anomalies."
                elif grounding_class == "MODEL_ASSISTED_RASTER":
                    action = "Use as advisory only; verify canopy density with field observation."
                elif grounding_class == "PROXY_SPATIAL":
                    action = "Treat as a plot-level risk cue, not a variable-rate prescription; verify in field."
                else:
                    action = "Treat as general plot-level advice; monitor on regular schedule."
                    
            elif st_name in ("NDVI_DEVIATION", "BASELINE_ANOMALY"):
                action_level = "scout"
                if grounding_class in ("RASTER_GROUNDED", "PARTIAL_RASTER_GROUNDED"):
                    action = "Scout highlighted low-vigor zones to inspect for localized stress."
                elif grounding_class == "MODEL_ASSISTED_RASTER":
                    action = "Use as advisory only; verify underperforming zones with field observation."
                elif grounding_class == "PROXY_SPATIAL":
                    action = "Scout underperforming zones indicated by model proxy; verify pixels with field walk."
                else:
                    action = "Treat as general plot-level risk cue; verify spatial variation when clearer imagery is available."
                    
            elif st_name == "WATER_STRESS_PROB":
                # V64 Water Stress Precipitation window rule
                if precip >= 5.0:
                    action = "Monitor rainfall infiltration; inspect drainage or runoff-prone areas if ponding or uneven wetting appears."
                    action_level = "monitor"
                elif 1.0 <= precip < 5.0:
                    action = "Verify soil moisture in red zones before adjusting irrigation; rainfall may be insufficient for root-zone recharge."
                    action_level = "verify"
                else:
                    action = "Inspect irrigation delivery in stressed zones and verify soil moisture before changing the schedule."
                    action_level = "scout"
                    
            elif st_name == "NUTRIENT_STRESS_PROB":
                has_red_edge = any(
                    b.lower() in {"ndre", "red_edge", "rededge", "b5", "b6", "b7", "b8a", "ci_red_edge"}
                    for b in raster_basis
                )
                if not has_red_edge:
                    driver = "Nutrient stress proxy — red-edge evidence unavailable"
                    action = "Observe leaf coloration in low-vigor zones; verify water stress and crop stage before considering nutrient intervention."
                    action_level = "verify"
                else:
                    action_level = "scout"
                    if grounding_class in ("RASTER_GROUNDED", "PARTIAL_RASTER_GROUNDED"):
                        action = "Scout leaves for discoloration, review fertigation records, and consider tissue/soil test."
                    else:
                        action = "Inspect leaves in low-vigor areas; use as advisory cue, not a variable-rate prescription."
                    
            elif st_name == "SALINITY_STRESS":
                action_level = "verify"
                action = "Verify soil electrical conductivity (EC) before planning leaching, drainage, or salinity interventions."
                    
            elif st_name == "COMPOSITE_RISK":
                action_level = "scout"
                if grounding_class in ("RASTER_GROUNDED", "PARTIAL_RASTER_GROUNDED"):
                    action = "Prioritize high-risk zones for field walk and verify multi-stress interaction."
                else:
                    action = "Treat as a plot-level risk cue, not a variable-rate prescription; prioritize high-risk zones for visual check."
                    
            elif st_name == "DATA_RELIABILITY":
                action_level = "monitor"
                action = "Monitor data freshness; wait for clearer imagery or verify with local photo/sensor upload."
                
            elif st_name == "RESOLUTION_COVERAGE":
                action_level = "monitor"
                action = "Use only at the shown decision scale (e.g., plot-level vs sub-meter zone)."

            # Build data-aware evidence list
            evidence = []
            evidence.append(f"Grounding class: {grounding_class}")
            evidence.append(f"Observed ratio: {observed_ratio:.0%}")
            
            if raster_basis:
                evidence.append(f"Raster basis: {', '.join(raster_basis)}")
            elif st_name == "NDVI_CLEAN":
                evidence.append("Sensor basis: Sentinel-2 optical telemetry")
                
            if mean_val is not None:
                evidence.append(f"Surface mean: {mean_val:.2f}")
            if p90_val is not None and st_name not in ("NDVI_DEVIATION", "BASELINE_ANOMALY"):
                evidence.append(f"Hotspot (P90) value: {p90_val:.2f}")
            if p10_val is not None and st_name in ("NDVI_DEVIATION", "BASELINE_ANOMALY"):
                evidence.append(f"Deviation (P10) limit: {p10_val:.3f}")
                
            if precip > 0:
                evidence.append(f"Recent precipitation: {precip:.1f} mm logged")
            else:
                evidence.append("No recent precipitation found in available logs")
                
            if has_farmer_logs:
                evidence.append("Farmer input logs checked")
            else:
                if st_name == "WATER_STRESS_PROB":
                    evidence.append("Irrigation log unavailable; moisture signal inferred from satellite proxy")
                else:
                    evidence.append("Farmer inputs log unavailable")
                    
            # Check warning conflicts
            warnings = getattr(output.quality_report, "warnings", [])
            has_conflict = any("conflict" in w.lower() for w in warnings)
            if has_conflict:
                evidence.append("Sensor conflicts detected in source telemetry")
            else:
                evidence.append("No sensor conflicts detected in active bands")

            # Score driver confidence based on grounding class and qscore
            driver_conf = qscore
            if grounding_class == "RASTER_GROUNDED":
                driver_conf *= 0.95
            elif grounding_class == "PARTIAL_RASTER_GROUNDED":
                driver_conf *= 0.85
            elif grounding_class == "MODEL_ASSISTED_RASTER":
                driver_conf *= 0.70
            else:
                driver_conf *= 0.55

            # V64: Safety Overrides based on weak grounding, low driver confidence, or low observed ratio
            weak_grounding = grounding_class in {"PROXY_SPATIAL", "UNIFORM", "MODEL_ASSISTED_RASTER"}
            low_driver_conf = driver_conf < 0.6
            low_observed = observed_ratio < 0.3

            if weak_grounding or low_driver_conf or low_observed:
                if action_level not in ("monitor", "verify"):
                    action_level = "verify"

            # Check and sanitize action string for forbidden prescriptive phrases
            forbidden_phrases = [
                "apply fertilizer", "apply nitrogen", "fertilize now",
                "irrigate immediately", "schedule irrigation now",
                "leach now", "spray", "treat immediately"
            ]
            action_lower = action.lower()
            if any(fp in action_lower for fp in forbidden_phrases):
                if st_name == "WATER_STRESS_PROB":
                    action = "Verify soil moisture in stressed zones and inspect irrigation equipment."
                elif st_name == "NUTRIENT_STRESS_PROB":
                    action = "Inspect leaf coloration in underperforming areas and verify soil conditions."
                elif st_name == "SALINITY_STRESS":
                    action = "Verify soil electrical conductivity (EC) before planning leaching, drainage, or salinity interventions."
                else:
                    action = "Verify field conditions in highlighted zones and monitor."
            
            # Formulate ModelEquation
            eqs = [ModelEquation(st_name.replace("_STRESS_PROB", "").replace("_STRESS", "").replace("_CLEAN", "").replace("_DEVIATION", ""), eq_expr, eq_descr)]
            
            # Create the pack
            exp_pack[st_name] = ExplainabilityPack(
                summary=f"Spatial analysis for {display_name.lower()} derived from {', '.join(raster_basis) if raster_basis else 'available satellites'}.",
                top_drivers=build_key_evidence_drivers(l10_input, output) if st_name == "NDVI_CLEAN" else [
                    DriverWeight(driver, 0.8, "positive" if action_level in ("monitor", "verify") else "negative")
                ],
                equations=eqs,
                charts={},
                provenance=ExplainabilityProvenance(
                    sources=s2_sources if not raster_basis else raster_basis,
                    timestamps=[output.timestamp],
                    model_version="v3.5 (Live-V63F)",
                    run_id=run_id,
                    degraded_reasons=[]
                ),
                confidence=ExplainabilityConfidence(
                    score=driver_conf,
                    penalties=qpens,
                    quality_scored_layers=eq_layers.split(", ")
                ),
                dominant_driver=driver,
                evidence=evidence,
                recommended_action=action,
                driver_confidence=round(driver_conf, 3),
                action_level=action_level
            )

        output.explainability_pack = exp_pack

        # 2. Build Realistic Agronomic Projections
        scenarios = []
        
        # Calculate baseline Value at Risk from L3 total severity
        base_var = 150 # Minimum operating risk
        total_sev = 0
        if l3 and hasattr(l3, "diagnoses"):
            total_sev = sum(getattr(d, "severity", 0) * getattr(d, "confidence", 0) for d in getattr(l3, "diagnoses", []))
            base_var = 150 + (total_sev * 45) # dynamic VaR

        # Get actual insights from current mode to tailor scenarios
        has_water_stress = any(d.problem_id == "WATER_STRESS" and d.severity > 0.3 for d in getattr(l3, "diagnoses", [])) if l3 else False
        has_nutrient_stress = any(d.problem_id == "NUTRIENT_DEFICIENCY" and d.severity > 0.3 for d in getattr(l3, "diagnoses", [])) if l3 else False

        # Scenario 1: Baseline (Always present)
        scenarios.append({
            "id": "scn_baseline",
            "title": "Baseline Trajectory",
            "description": "Projected outcome if current trends continue without intervention over the next 7 days.",
            "val_at_risk": round(base_var),
            "cost_of_action": 0,
            "yield_impact_pct": round(min(-2.5, -total_sev * 1.5), 1),
            "outcomes": [
                {"label": "Canopy Vigor", "value": "Declining" if total_sev > 2 else "Stable", "sentiment": "negative" if total_sev > 2 else "neutral"},
                {"label": "Stress Spread", "value": f"+{round(total_sev * 5)}%", "sentiment": "negative"},
            ]
        })

        # Scenario 2: Actionable intervention 1 (Water/Irrigation focused)
        scenarios.append({
            "id": "scn_irrigation",
            "title": "Targeted Moisture Protocol",
            "description": "Variable rate irrigation targeting high-stress zones based on SAR/optical moisture deficit.",
            "val_at_risk": round(base_var * 0.2), # reduced VaR
            "cost_of_action": round(12.5 * max(1, total_sev)),
            "yield_impact_pct": round(max(2.0, total_sev * 1.2), 1),
            "outcomes": [
                {"label": "Stress Recovery", "value": "Rapid (48h)", "sentiment": "positive"},
                {"label": "Water Efficiency", "value": "+18%", "sentiment": "positive"},
                {"label": "Canopy Vigor", "value": "Improving", "sentiment": "positive"},
            ]
        })

        # Scenario 3: Actionable intervention 2 (Nutrient focused)
        scenarios.append({
            "id": "scn_nutrient",
            "title": "Localized Top-Dress",
            "description": "Spot application of nitrogen to correct early-stage localized vigor degradation.",
            "val_at_risk": round(base_var * 0.4),
            "cost_of_action": round(25.0 * max(1, total_sev)),
            "yield_impact_pct": round(max(3.5, total_sev * 1.8), 1),
            "outcomes": [
                {"label": "Canopy Vigor", "value": "High Boost", "sentiment": "positive"},
                {"label": "Input Savings", "value": "12%", "sentiment": "positive"},
                {"label": "Runoff Risk", "value": "Minimal", "sentiment": "neutral"},
            ]
        })
        
        output.scenario_pack = scenarios

        # 3. Build History from Memory logs
        history_events = []
        try:
            from orchestrator_v2.chat_memory import load_memory
            mem = load_memory(l10_input.plot_id)
            if hasattr(mem, "history") and mem.history:
                for item in reversed(mem.history[-4:]):  # last 4
                    role = item.get("role", "system")
                    title = "AI Diagnosis Output" if role == "assistant" else "User Query Logging"
                    history_events.append({
                        "timestamp": output.timestamp,
                        "type": "USER_ACTION" if role == "user" else "AI_DIAGNOSTIC",
                        "title": title,
                        "description": item.get("content", "")[:60] + "..."
                    })
        except Exception:
            pass
            
        if not history_events:
            history_events = [{
                "timestamp": output.timestamp,
                "type": "SYSTEM",
                "title": "Data extraction initialized",
                "description": "Fresh telemetry pulled for pipeline execution."
            }]
            
        output.history_pack = history_events

    except Exception as e:
        import traceback
        print(f"[Premium Pack Builder] Execution failed, degrading gracefully: {e}")
        traceback.print_exc()
        output.explainability_pack = {}
        output.scenario_pack = []
        output.history_pack = []

    return output

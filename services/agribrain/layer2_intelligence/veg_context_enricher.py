"""
Vegetation Context Enricher — Converts VegIntOutput into canonical Layer 2 context features.

V91.2 Evidence Integrity Rules:
  1. NEVER overwrite canonical L1 keys (ndvi_mean, cwsi, ndmi_mean, etc.).
     Use veg_fit_* / veg_diag_* namespace for all enricher-produced features.
  2. Three-field evidence lineage:
     - source_evidence_ids: []        — always empty; enricher has no direct evidence
     - lineage_source_evidence_ids:   — real L1 observation IDs the curve was fitted from
     - derived_artifact_ids:          — model artifact references (e.g. "veg_curve_fit")
  3. Anomaly source_evidence_ids are preserved from the anomaly object's own
     lineage, but moved to lineage_source_evidence_ids to avoid attribution confusion.
"""

from typing import Any, Dict, List, Optional


def enrich_context_with_veg_output(context: Any, veg_out: Any, tensor: Any = None, inputs: Any = None) -> Any:
    """Enrich the copied Layer2InputContext with vegetation metrics.

    All features are written to veg_fit_* / veg_diag_* namespaced keys.
    Canonical L1 keys (ndvi_mean, cwsi, etc.) are never touched.
    """
    if context is None or veg_out is None:
        return context

    # Determine observed coverage
    obs_coverage = 0.0
    curve = getattr(veg_out, "curve", None)
    if curve is not None:
        q = getattr(curve, "quality", None)
        if q is not None:
            obs_coverage = getattr(q, "obs_coverage", 0.0)

    # Graded behavior for vegetation observed coverage
    is_degraded = obs_coverage == 0.0 or getattr(veg_out, "run_id", "").endswith("_degraded")

    diagnostic_only = False
    confidence_cap = 1.0
    cap_reason = None

    if is_degraded:
        diagnostic_only = True
        confidence_cap = 0.20
        cap_reason = "zero_observed_coverage"
    elif obs_coverage < 0.30:
        diagnostic_only = True
        confidence_cap = 0.30
        cap_reason = "low_observed_coverage"
    elif obs_coverage < 0.60:
        diagnostic_only = True
        confidence_cap = 0.50
        cap_reason = "medium_observed_coverage"
    else:
        diagnostic_only = False
        confidence_cap = 0.85

    # ── Extract lineage source IDs from VegIntOutput curve quality ──
    # These are the real S2/sensor observation IDs that the curve was fitted from.
    # They are AUDIT TRACEABILITY, not direct attribution evidence.
    lineage_ids: List[str] = []
    if curve is not None:
        q = getattr(curve, "quality", None)
        if q is not None:
            lineage_ids = list(getattr(q, "observation_ids", []) or [])

    # Helper to build derivation metadata and feature structure
    def _build_veg_feature(val, unit, is_diag=False,
                           lineage_source_evidence_ids=None):
        """Build a feature dict with V91.2 three-field evidence lineage.

        - source_evidence_ids:          ALWAYS [] (enricher has no direct evidence)
        - lineage_source_evidence_ids:  real observation IDs used to derive the fit
        - derived_artifact_ids:         ["veg_curve_fit"] (model artifact reference)
        """
        diag = is_diag or diagnostic_only
        lineage = lineage_source_evidence_ids or lineage_ids

        raw_conf = 0.80 if not diag else 0.50
        conf = min(raw_conf, confidence_cap)

        meta = {
            "source": "layer2_veg_int",
            "derived_feature": True,
            "diagnostic_only": diag,
            "source_evidence_ids": [],
            "lineage_source_evidence_ids": lineage,
            "derived_artifact_ids": ["veg_curve_fit"],
            "veg_obs_coverage": obs_coverage,
        }
        if cap_reason:
            meta["confidence_cap_reason"] = cap_reason

        return {
            "value": val,
            "unit": unit,
            "confidence": conf,
            "diagnostic_only": diag,
            "source_evidence_ids": [],
            "lineage_source_evidence_ids": lineage,
            "derived_artifact_ids": ["veg_curve_fit"],
            "derived_feature": True,
            "flags": ["veg_derived"],
            "derivation_metadata": meta,
        }

    # Extract latest values from fit curve
    ndvi_fit = getattr(curve, "ndvi_fit", [])
    d1 = getattr(curve, "ndvi_fit_d1", [])

    latest_ndvi = ndvi_fit[-1] if ndvi_fit else None
    latest_velocity = d1[-1] if d1 else None

    # Get metrics from health index
    health_index = getattr(veg_out, "health_index", None)
    latest_ndmi = None
    latest_cwsi = None
    latest_lai = None
    latest_fpar = None
    latest_fvc = None
    et_deficit = None
    wue = None

    if health_index is not None:
        latest_cwsi = getattr(health_index, "water_stress_index", None)
        latest_lai = getattr(health_index, "lai_estimate", None)
        latest_fpar = getattr(health_index, "fpar_current", None)
        latest_fvc = getattr(health_index, "vegetation_fraction", None)
        et_deficit = getattr(health_index, "et_deficit", None)
        wue = getattr(health_index, "wue", None)

    # ── 1. State-supporting features (veg_fit_* namespace) ──
    # NEVER write to ndvi_mean, cwsi, ndmi_mean, etc. — those are L1 canonical keys.
    if latest_ndvi is not None:
        context.vegetation_context["veg_fit_ndvi"] = _build_veg_feature(latest_ndvi, "index")
    if latest_ndmi is not None:
        context.water_context["veg_fit_ndmi"] = _build_veg_feature(latest_ndmi, "index")
    if latest_cwsi is not None:
        context.water_context["veg_fit_cwsi"] = _build_veg_feature(latest_cwsi, "index")
    if latest_lai is not None:
        context.vegetation_context["veg_fit_lai"] = _build_veg_feature(latest_lai, "m2/m2")
    if latest_fpar is not None:
        context.vegetation_context["veg_fit_fpar"] = _build_veg_feature(latest_fpar, "fraction")
    if latest_fvc is not None:
        context.vegetation_context["veg_fit_fvc"] = _build_veg_feature(latest_fvc, "fraction")
    if et_deficit is not None:
        context.water_context["veg_fit_et_deficit"] = _build_veg_feature(et_deficit, "mm")
    if latest_velocity is not None:
        context.vegetation_context["veg_fit_velocity"] = _build_veg_feature(latest_velocity, "index/day")

    # Phenology stage — phenology_stage is enricher's own key (not an L1 canonical key)
    pheno = getattr(veg_out, "phenology", None)
    if pheno is not None:
        stages = getattr(pheno, "stage_by_day", [])
        if stages:
            last_stage = stages[-1]
            stage_str = last_stage.value if hasattr(last_stage, "value") else str(last_stage)
            context.phenology_context["phenology_stage"] = _build_veg_feature(stage_str, "stage")

            if not context.crop_context:
                from layer1_fusion.schemas import CropCycleContext
                context.crop_context = CropCycleContext(
                    crop_type=getattr(inputs, "crop_config", {}).get("crop", "unknown") if inputs else "unknown",
                    current_stage=stage_str,
                    gdd_accumulated=0.0
                )
            else:
                context.crop_context.current_stage = stage_str

    # ── 2. Diagnostic features (veg_diag_* namespace) ──
    npp_series = getattr(curve, "npp_series", [])
    latest_npp = npp_series[-1] if npp_series else None
    if latest_npp is not None:
        context.vegetation_context["veg_diag_npp"] = _build_veg_feature(latest_npp, "gC/m2/day", is_diag=True)

    if wue is not None:
        context.vegetation_context["veg_diag_wue"] = _build_veg_feature(wue, "g/kg", is_diag=True)

    stability = getattr(veg_out, "stability", None)
    if stability is not None:
        mean_var = getattr(stability, "mean_spatial_var", None)
        if mean_var is not None:
            context.vegetation_context["veg_diag_spatial_het"] = _build_veg_feature(mean_var, "variance", is_diag=True)

    # ── 3. Anomalies as Diagnostic Priors ──
    # Anomaly source IDs from the anomaly object are treated as lineage
    # (the observations that triggered the anomaly detection), not direct evidence.
    anomalies = getattr(veg_out, "anomalies", []) or []
    for anomaly in anomalies:
        anomaly_type = getattr(anomaly, "type", "UNKNOWN").lower()
        severity = getattr(anomaly, "severity", 0.0)
        confidence = getattr(anomaly, "confidence", 0.5)

        # Extract anomaly's own source IDs as lineage (not attribution)
        anomaly_lineage = getattr(anomaly, "source_evidence_ids", [])
        if not anomaly_lineage and hasattr(anomaly, "source_ids"):
            anomaly_lineage = getattr(anomaly, "source_ids", [])
        anomaly_lineage = [] if is_degraded else list(anomaly_lineage)

        if "water" in anomaly_type or "dry" in anomaly_type or "deficit" in anomaly_type:
            key = "veg_water_anomaly"
            group = context.water_context
        elif "nutrient" in anomaly_type or "chloro" in anomaly_type:
            key = "veg_nutrient_anomaly"
            group = context.vegetation_context
        elif "thermal" in anomaly_type or "temp" in anomaly_type or "frost" in anomaly_type:
            key = "veg_thermal_anomaly"
            group = context.stress_evidence_context
        else:
            key = "veg_general_anomaly"
            group = context.vegetation_context

        group[key] = _build_veg_feature(
            val=severity,
            unit="score",
            is_diag=True,
            lineage_source_evidence_ids=anomaly_lineage,
        )
        group[key]["confidence"] = min(confidence, confidence_cap)

    return context

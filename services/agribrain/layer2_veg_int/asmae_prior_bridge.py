# -*- coding: utf-8 -*-
"""
ASMAE Prior Bridge — Layer 2 → ASMAE (BC.10.13 P5)

Translates VegIntOutput into ASMAE-compatible crop priors.

CONTRACT:
- If VegIntOutput is absent or incomplete → available=False.
- If available=True → crop-specific bounds/weights are populated from real
  phenology/stability data.
- No crop priors are fabricated. If crop type is unknown, bounds fall back to
  broad defaults but weight is reduced.
- Never assumes crop type from plot metadata alone. Only VegIntOutput or
  user-confirmed crop data are accepted as sources.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Crop group → biophysical bounds ───────────────────────────────────────────
# These are broad but evidence-based ranges per crop group.
# LAI: m²/m², Chlorophyll: relative units (0–1 normalised)
_CROP_GROUP_BOUNDS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "cereal":      {"lai": (0.5, 8.0), "chlorophyll": (0.3, 0.9)},
    "legume":      {"lai": (0.3, 6.0), "chlorophyll": (0.3, 0.85)},
    "orchard":     {"lai": (1.0, 7.0), "chlorophyll": (0.35, 0.90)},
    "vegetable":   {"lai": (0.3, 5.0), "chlorophyll": (0.25, 0.85)},
    "tuber":       {"lai": (0.5, 6.5), "chlorophyll": (0.3, 0.85)},
    "forage":      {"lai": (0.3, 7.5), "chlorophyll": (0.3, 0.85)},
    "industrial":  {"lai": (0.5, 8.0), "chlorophyll": (0.30, 0.90)},
    "fallow":      {"lai": (0.0, 1.5), "chlorophyll": (0.05, 0.40)},
    "unknown":     {"lai": (0.0, 10.0),"chlorophyll": (0.0, 1.0)},
}

# Coarse crop-name → group mapping.
_CROP_TO_GROUP: Dict[str, str] = {
    "wheat":    "cereal",   "barley": "cereal",   "corn": "cereal",
    "maize":    "cereal",   "rice":   "cereal",   "sorghum": "cereal",
    "soybean":  "legume",   "peas":   "legume",   "bean": "legume",
    "chickpea": "legume",   "lentil": "legume",
    "orange":   "orchard",  "lemon":  "orchard",  "apple": "orchard",
    "olive":    "orchard",  "almond": "orchard",  "grape": "orchard",
    "tomato":   "vegetable","pepper": "vegetable","potato": "tuber",
    "onion":    "vegetable","carrot": "vegetable",
    "sunflower":"industrial","cotton":"industrial","sugarcane":"industrial",
    "grass":    "forage",   "pasture":"forage",
}

# Broad fallback when crop group is unknown.
_BROAD_DEFAULT = {
    "lai":         (0.0, 10.0),
    "chlorophyll": (0.0,  1.0),
}
_BROAD_DEFAULT_WEIGHT = 0.20  # low weight when group is unknown


@dataclass
class ASMAECropPrior:
    """ASMAE-ready crop prior derived from Layer 2 VegIntOutput."""
    crop_type_used: Optional[str]
    crop_group_used: Optional[str]
    phenology_stage: Optional[str]
    phenology_used: bool
    lai_bounds: Tuple[float, float]
    chlorophyll_bounds: Tuple[float, float]
    spatial_stability_class: Optional[str]
    anomaly_severity_max: float          # 0–1; max anomaly severity found by Layer 2
    available: bool
    reason: str
    weight: float                        # How much to trust crop-prior-enhanced features (0–1)
    provenance: Dict[str, Any] = field(default_factory=dict)


def build_asmae_crop_prior(
    veg_int_output: Optional[Any],
    plot_metadata: Optional[Dict[str, Any]] = None,
) -> ASMAECropPrior:
    """
    Build an ASMAECropPrior from VegIntOutput.

    Parameters
    ----------
    veg_int_output:
        VegIntOutput (or None).  Only real VegIntOutput data is accepted.
        Fake or fabricated output must NOT be passed here.
    plot_metadata:
        Optional plot-level metadata (e.g. registered crop type from UI).
        Used ONLY to enrich the crop group; never used to fabricate priors.

    Returns
    -------
    ASMAECropPrior — always safe to consume.  Check available before using
    crop-specific bounds/weights.
    """
    # ── Guard: no VegIntOutput ────────────────────────────────────────────────
    if veg_int_output is None:
        logger.debug("ASMAECropPrior: VegIntOutput is None → available=False")
        return ASMAECropPrior(
            crop_type_used=None,
            crop_group_used=None,
            phenology_stage=None,
            phenology_used=False,
            lai_bounds=_BROAD_DEFAULT["lai"],
            chlorophyll_bounds=_BROAD_DEFAULT["chlorophyll"],
            spatial_stability_class=None,
            anomaly_severity_max=0.0,
            available=False,
            reason="layer2_prior_unavailable",
            weight=0.0,
            provenance={"source": "none"},
        )

    # ── Extract crop type ─────────────────────────────────────────────────────
    # Only from VegIntOutput provenance or plot_metadata (not invented).
    crop_type: Optional[str] = None
    prov = getattr(veg_int_output, "provenance", {}) or {}
    crop_type = prov.get("crop_type") or prov.get("identified_crop")

    # Accept from plot_metadata only if it was user-confirmed.
    if not crop_type and plot_metadata:
        if plot_metadata.get("crop_confirmed_by_user"):
            crop_type = plot_metadata.get("crop_type")

    crop_group: Optional[str] = None
    if crop_type:
        crop_group = _CROP_TO_GROUP.get(str(crop_type).lower().strip())

    if not crop_group:
        logger.debug("ASMAECropPrior: crop type '%s' maps to unknown group", crop_type)
        crop_group = "unknown"

    bounds = _CROP_GROUP_BOUNDS.get(crop_group, _CROP_GROUP_BOUNDS["unknown"])
    lai_bounds = bounds["lai"]
    chl_bounds = bounds["chlorophyll"]

    # Weight is reduced for unknown crop group.
    prior_weight = _BROAD_DEFAULT_WEIGHT if crop_group == "unknown" else 0.65

    # ── Extract phenology ─────────────────────────────────────────────────────
    phenology_stage: Optional[str] = None
    phenology_used = False
    try:
        pheno = getattr(veg_int_output, "phenology", None)
        if pheno:
            stage_by_day = getattr(pheno, "stage_by_day", []) or []
            if stage_by_day:
                phenology_stage = stage_by_day[-1]  # most recent stage
                phenology_used = True
    except Exception:
        pass

    # ── Extract spatial stability ─────────────────────────────────────────────
    stability_class: Optional[str] = None
    try:
        stab = getattr(veg_int_output, "stability", None)
        if stab:
            stability_class = getattr(stab, "stability_class", None)
    except Exception:
        pass

    # ── Extract anomaly severity ──────────────────────────────────────────────
    anomaly_severity_max = 0.0
    try:
        anomalies = getattr(veg_int_output, "anomalies", []) or []
        if anomalies:
            anomaly_severity_max = max(
                (getattr(a, "severity", 0.0) or 0.0) for a in anomalies
            )
    except Exception:
        pass

    # ── Guard: useless output ─────────────────────────────────────────────────
    # If we got a VegIntOutput but couldn't extract anything useful, mark
    # available=False rather than returning fabricated defaults.
    if not phenology_used and crop_group == "unknown" and stability_class is None:
        logger.debug("ASMAECropPrior: VegIntOutput present but empty → available=False")
        return ASMAECropPrior(
            crop_type_used=crop_type,
            crop_group_used=None,
            phenology_stage=None,
            phenology_used=False,
            lai_bounds=_BROAD_DEFAULT["lai"],
            chlorophyll_bounds=_BROAD_DEFAULT["chlorophyll"],
            spatial_stability_class=None,
            anomaly_severity_max=anomaly_severity_max,
            available=False,
            reason="layer2_prior_empty",
            weight=0.0,
            provenance={
                "source": "veg_int_output",
                "crop_type": crop_type,
                "crop_group": crop_group,
            },
        )

    logger.debug(
        "ASMAECropPrior: available=True crop_group=%s phenology=%s weight=%.2f",
        crop_group, phenology_stage, prior_weight,
    )
    return ASMAECropPrior(
        crop_type_used=crop_type,
        crop_group_used=crop_group,
        phenology_stage=phenology_stage,
        phenology_used=phenology_used,
        lai_bounds=lai_bounds,
        chlorophyll_bounds=chl_bounds,
        spatial_stability_class=stability_class,
        anomaly_severity_max=anomaly_severity_max,
        available=True,
        reason="ok",
        weight=prior_weight,
        provenance={
            "source": "veg_int_output",
            "crop_type": crop_type,
            "crop_group": crop_group,
            "phenology_stage": phenology_stage,
            "stability_class": stability_class,
        },
    )

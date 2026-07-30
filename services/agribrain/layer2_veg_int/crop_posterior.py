"""Canonical probabilistic crop identity for the two-pass ASMAE/L2 loop."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .crop_science_data import get_crop_group


CROP_POSTERIOR_CONTRACT_VERSION = "crop_identity_posterior_v1"
_AUTHORITY_RANK = {
    "UNKNOWN": 0,
    "MODEL_SPECIES_POSTERIOR": 1,
    "MODEL_GROUP_POSTERIOR": 2,
    "ARCHIVE_STABLE_GROUP": 3,
    "REGISTRY_DECLARED": 4,
    "AGRONOMIST_CONFIRMED": 5,
    "USER_CONFIRMED": 6,
}
_ALIASES = {
    "corn": "maize",
    "zea_mays": "maize",
    "citrus": "citrus_group",
}
_DECLARED_GROUPS = {
    "cereal", "legume", "vegetable", "forage", "orchard", "tuber",
    "industrial", "perennial", "annual", "mixed", "fallow",
}
_GROUP_PHYSICS = {
    "cereal": {
        "crop_coefficient": 1.05, "t_base": 5.0, "t_opt": 22.0,
        "t_max": 36.0, "lai_bounds": (0.2, 8.0),
        "chlorophyll_bounds": (12.0, 75.0),
    },
    "legume": {
        "crop_coefficient": 1.00, "t_base": 7.0, "t_opt": 24.0,
        "t_max": 38.0, "lai_bounds": (0.2, 6.5),
        "chlorophyll_bounds": (10.0, 70.0),
    },
    "vegetable": {
        "crop_coefficient": 1.00, "t_base": 8.0, "t_opt": 24.0,
        "t_max": 37.0, "lai_bounds": (0.1, 6.0),
        "chlorophyll_bounds": (8.0, 72.0),
    },
    "forage": {
        "crop_coefficient": 1.05, "t_base": 4.0, "t_opt": 21.0,
        "t_max": 36.0, "lai_bounds": (0.2, 8.0),
        "chlorophyll_bounds": (10.0, 75.0),
    },
    "orchard": {
        "crop_coefficient": 0.90, "t_base": 7.0, "t_opt": 24.0,
        "t_max": 39.0, "lai_bounds": (0.5, 7.5),
        "chlorophyll_bounds": (15.0, 80.0),
    },
    "annual": {
        "crop_coefficient": 1.00, "t_base": 8.0, "t_opt": 25.0,
        "t_max": 39.0, "lai_bounds": (0.1, 8.0),
        "chlorophyll_bounds": (8.0, 78.0),
    },
    "perennial": {
        "crop_coefficient": 0.90, "t_base": 7.0, "t_opt": 24.0,
        "t_max": 40.0, "lai_bounds": (0.4, 8.0),
        "chlorophyll_bounds": (12.0, 80.0),
    },
    "fallow": {
        "crop_coefficient": 0.25, "t_base": 5.0, "t_opt": 24.0,
        "t_max": 40.0, "lai_bounds": (0.0, 1.5),
        "chlorophyll_bounds": (0.0, 35.0),
    },
}


def _broad_group(group: Any) -> str:
    value = str(group or "unknown").lower()
    if value in _GROUP_PHYSICS:
        return value
    if "cereal" in value or value == "rice":
        return "cereal"
    if "legume" in value:
        return "legume"
    if "orchard" in value or "palm" in value:
        return "orchard"
    if "forage" in value:
        return "forage"
    if any(token in value for token in ("veg", "tuber", "herb", "spice")):
        return "vegetable"
    if any(token in value for token in ("perennial", "tree", "vine")):
        return "perennial"
    if value in {"non_crop", "bare_soil", "mixed_unknown", "fallow"}:
        return "fallow"
    if any(token in value for token in ("oilseed", "fiber", "sugar", "crop")):
        return "annual"
    return "unknown"


def _mixture_conditioning(
    group_posterior: Mapping[str, Any],
) -> Dict[str, Any]:
    broad_weights: Dict[str, float] = {}
    unknown = 0.0
    for group, raw_weight in group_posterior.items():
        weight = _finite(raw_weight)
        if weight is None or weight <= 0.0:
            continue
        broad = _broad_group(group)
        if broad == "unknown":
            unknown += weight
        else:
            broad_weights[broad] = broad_weights.get(broad, 0.0) + weight
    known_mass = sum(broad_weights.values())
    if known_mass <= 0.0:
        return {
            "known_mass": 0.0,
            "unknown_mass": min(1.0, unknown),
            "broad_group_weights": {},
            "parameters": {},
            "parameter_variance": {},
            "bounds": {},
        }
    normalized = {
        key: value / known_mass for key, value in broad_weights.items()
    }
    scalar_names = ("crop_coefficient", "t_base", "t_opt", "t_max")
    parameters = {
        name: sum(
            weight * float(_GROUP_PHYSICS[group][name])
            for group, weight in normalized.items()
        )
        for name in scalar_names
    }
    parameter_variance = {
        name: sum(
            weight
            * (float(_GROUP_PHYSICS[group][name]) - parameters[name]) ** 2
            for group, weight in normalized.items()
        )
        for name in scalar_names
    }
    supported_groups = [
        group for group, weight in normalized.items() if weight >= 0.05
    ] or list(normalized)
    bounds = {
        key: (
            min(float(_GROUP_PHYSICS[group][key][0]) for group in supported_groups),
            max(float(_GROUP_PHYSICS[group][key][1]) for group in supported_groups),
        )
        for key in ("lai_bounds", "chlorophyll_bounds")
    }
    return {
        "known_mass": round(known_mass, 8),
        "unknown_mass": round(max(unknown, 1.0 - known_mass), 8),
        "broad_group_weights": {
            key: round(value, 8) for key, value in sorted(normalized.items())
        },
        "parameters": {
            key: round(value, 8) for key, value in parameters.items()
        },
        "parameter_variance": {
            key: round(value, 8)
            for key, value in parameter_variance.items()
        },
        "bounds": {
            key: [round(value[0], 8), round(value[1], 8)]
            for key, value in bounds.items()
        },
    }


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _stable(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def normalize_declared_crop(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(raw, raw)


def crop_authority(crop_config: Mapping[str, Any]) -> str:
    candidates = ["UNKNOWN"]
    explicit = str(
        crop_config.get("crop_identity_authority")
        or crop_config.get("crop_authority")
        or ""
    ).upper()
    if explicit in _AUTHORITY_RANK:
        candidates.append(explicit)
    if (
        crop_config.get("crop_confirmed_by_user") is True
        or crop_config.get("user_confirmed") is True
    ):
        candidates.append("USER_CONFIRMED")
    if crop_config.get("confirmed_by_agronomist") is True:
        candidates.append("AGRONOMIST_CONFIRMED")
    crop = normalize_declared_crop(
        crop_config.get("crop") or crop_config.get("crop_type")
    )
    if crop not in {"", "unknown"}:
        candidates.append("REGISTRY_DECLARED")
    return max(candidates, key=lambda item: _AUTHORITY_RANK[item])


def _nested(context: Mapping[str, Any], *keys: str) -> Any:
    queue: List[Mapping[str, Any]] = [context]
    wanted = {key.lower() for key in keys}
    while queue:
        current = queue.pop(0)
        for key, value in current.items():
            if str(key).lower() in wanted:
                return value
            if isinstance(value, Mapping):
                queue.append(value)
    return None


def _admitted_records(records: Iterable[Any]) -> List[Dict[str, Any]]:
    from layer0.temporal_evidence import is_admitted_temporal_record

    admitted: Dict[str, Dict[str, Any]] = {}
    for raw in records or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        if not is_admitted_temporal_record(
            row,
            value_keys=(
                "ndvi", "ndvi_mean", "evi", "evi_mean", "ndmi",
                "ndmi_mean", "ndwi", "ndwi_mean", "vv", "vv_db",
                "vv_db_mean", "vh", "vh_db", "vh_db_mean",
            ),
        ):
            continue
        date_value = (
            row.get("date") or row.get("timestamp")
            or row.get("acquired_at") or row.get("datetime")
        )
        if not date_value:
            continue
        try:
            stamp = datetime.fromisoformat(
                str(date_value).replace("Z", "+00:00")
            )
        except ValueError:
            continue
        signals = {
            key: _finite(row.get(key))
            for key in (
                "ndvi", "ndvi_mean", "ndvi_clean", "evi", "evi_mean",
                "ndmi", "ndmi_mean", "ndwi", "ndwi_mean", "vv",
                "vv_db", "vv_db_mean", "vh", "vh_db", "vh_db_mean",
            )
        }
        if not any(value is not None for value in signals.values()):
            continue
        support_id = str(
            row.get("content_hash")
            or row.get("observation_id")
            or row.get("scene_id")
            or f"{stamp.isoformat()}:{row.get('source', 'unknown')}"
        )
        row["_parsed_date"] = stamp
        row["_signals"] = signals
        row["_support_id"] = support_id
        admitted.setdefault(support_id, row)
    return sorted(admitted.values(), key=lambda row: row["_parsed_date"])


def _series(
    rows: List[Dict[str, Any]], aliases: Tuple[str, ...]
) -> Tuple[List[float], List[str]]:
    values: List[float] = []
    dates: List[str] = []
    for row in rows:
        value = next(
            (
                _finite(row.get(alias))
                for alias in aliases
                if _finite(row.get(alias)) is not None
            ),
            None,
        )
        if value is None:
            continue
        values.append(value)
        dates.append(row["_parsed_date"].date().isoformat())
    return values, dates


def _mean(rows: List[Dict[str, Any]], aliases: Tuple[str, ...]) -> Optional[float]:
    values, _ = _series(rows, aliases)
    return sum(values) / len(values) if values else None


def _evidence_quality(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ndvi, dates = _series(
        rows, ("ndvi_clean", "ndvi", "ndvi_mean")
    )
    if dates:
        start = datetime.fromisoformat(dates[0])
        end = datetime.fromisoformat(dates[-1])
        span_days = max(0, (end - start).days)
    else:
        span_days = 0
    expected = max(1.0, span_days / 10.0 + 1.0)
    temporal_coverage = min(1.0, len(set(dates)) / expected)
    quality_values = []
    for row in rows:
        value = next(
            (
                parsed for key in (
                    "valid_fraction", "quality", "qa_score",
                    "reading_reliability",
                )
                if (parsed := _finite(row.get(key))) is not None
            ),
            None,
        )
        if value is not None:
            quality_values.append(value)
    mean_quality = (
        sum(max(0.0, min(1.0, value)) for value in quality_values)
        / len(quality_values)
        if quality_values else 0.5
    )
    families = {
        "optical" if any(
            _finite(row.get(key)) is not None
            for row in rows for key in (
                "ndvi", "ndvi_mean", "ndvi_clean", "evi", "evi_mean",
                "ndmi", "ndmi_mean", "ndwi", "ndwi_mean",
            )
        ) else "",
        "sar" if any(
            _finite(row.get(key)) is not None
            for row in rows for key in (
                "vv", "vv_db", "vv_db_mean", "vh", "vh_db", "vh_db_mean",
            )
        ) else "",
    } - {""}
    independence = min(1.0, len({row["_support_id"] for row in rows}) / 12.0)
    quality = (
        0.35 * min(1.0, len(ndvi) / 12.0)
        + 0.25 * temporal_coverage
        + 0.20 * mean_quality
        + 0.10 * independence
        + 0.10 * min(1.0, len(families) / 3.0)
    )
    return {
        "score": round(quality, 6),
        "admitted_record_count": len(rows),
        "admitted_ndvi_count": len(ndvi),
        "content_distinct_count": len({row["_support_id"] for row in rows}),
        "temporal_span_days": span_days,
        "temporal_coverage": round(temporal_coverage, 6),
        "mean_quality": round(mean_quality, 6),
        "independent_feature_families": sorted(families),
    }


def _declared_group(crop: str) -> str:
    if crop in _DECLARED_GROUPS:
        return crop
    try:
        group = str(get_crop_group(crop) or "unknown")
    except Exception:
        group = "unknown"
    return group


def _normalize_distribution(
    group_scores: Mapping[str, float], unknown: float
) -> Dict[str, float]:
    values = {
        str(key): max(0.0, float(value))
        for key, value in group_scores.items()
        if str(key) and str(key) != "unknown" and float(value) > 0.0
    }
    values["unknown"] = max(0.0, float(unknown))
    total = sum(values.values())
    if total <= 0.0:
        return {"unknown": 1.0}
    return {
        key: round(value / total, 8)
        for key, value in sorted(values.items())
    }


def infer_crop_posterior(
    *,
    plot_id: str,
    run_id: str,
    plot_timeseries: Iterable[Any],
    crop_config: Optional[Mapping[str, Any]] = None,
    operational_context: Optional[Mapping[str, Any]] = None,
    archive_context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the conservative pre-ASMAE crop-group inference pass."""
    crop_config = dict(crop_config or {})
    operational = dict(operational_context or {})
    rows = _admitted_records(plot_timeseries)
    quality = _evidence_quality(rows)
    declared = normalize_declared_crop(
        crop_config.get("crop") or crop_config.get("crop_type")
    )
    authority = crop_authority(crop_config)

    ndvi, ndvi_dates = _series(
        rows, ("ndvi_clean", "ndvi", "ndvi_mean")
    )
    vv = _mean(rows, ("vv", "vv_db", "vv_db_mean"))
    vh = _mean(rows, ("vh", "vh_db", "vh_db_mean"))
    temperatures: List[float] = []
    gdd_values: List[float] = []
    lat = _finite(_nested(operational, "lat", "latitude"))
    lng = _finite(_nested(operational, "lng", "lon", "longitude"))
    area = _finite(_nested(operational, "area_ha", "plot_area_ha"))
    soil = _nested(operational, "soil_type", "soil_texture_class")
    irrigation = _nested(operational, "irrigation_type", "irrigation_method")
    previous = _nested(
        archive_context or operational,
        "previous_crops", "crop_rotation", "crop_history",
    )

    species_ranking: List[Dict[str, Any]] = []
    group_scores: Dict[str, float] = {}
    engine_evidence: Dict[str, Any] = {}
    if len(ndvi) >= 6 or any(
        value is not None for value in (vv, vh, lat, area)
    ):
        from .crop_identification import identify_crop

        result = identify_crop(
            ndvi_series=ndvi or None,
            ndvi_dates=ndvi_dates or None,
            peak_ndvi=max(ndvi) if ndvi else None,
            trough_ndvi=min(ndvi) if ndvi else None,
            sar_vh_mean=vh,
            sar_vv_mean=vv,
            evi_mean=_mean(rows, ("evi", "evi_mean")),
            ndmi_mean=_mean(rows, ("ndmi", "ndmi_mean")),
            ndwi_mean=_mean(rows, ("ndwi", "ndwi_mean")),
            lat=lat,
            lng=lng,
            climate_zone=_nested(operational, "climate_zone", "koppen_zone"),
            elevation_m=_finite(_nested(operational, "elevation_m", "elevation")),
            mean_temp_c=(
                sum(temperatures) / len(temperatures)
                if temperatures else _finite(
                    _nested(operational, "mean_temp_c", "tmean")
                )
            ),
            gdd_accumulated=(
                sum(gdd_values) if gdd_values else _finite(
                    _nested(operational, "gdd_accumulated")
                )
            ),
            gdd_accumulation_days=quality["temporal_span_days"] or None,
            annual_rainfall_mm=_finite(
                _nested(operational, "annual_rainfall_mm", "rainfall_mm")
            ),
            et0_mm=_finite(_nested(operational, "et0_mm", "annual_et0_mm")),
            area_ha=area,
            soil_type=str(soil) if soil is not None else None,
            irrigation_type=str(irrigation) if irrigation is not None else None,
            previous_crops=previous if isinstance(previous, list) else None,
            dna_vigor=_finite(_nested(operational, "dna_vigor", "alpha_vigor")),
            dna_water_retention=_finite(
                _nested(operational, "dna_water_retention", "theta_retention")
            ),
            plot_id=plot_id,
            run_id=run_id,
        )
        engine_evidence = dict(result.evidence or {})
        for candidate in result.candidates:
            share = candidate.softmax_candidate_share
            if not isinstance(share, (int, float)):
                continue
            species_ranking.append({
                "code": candidate.code,
                "crop_group": candidate.crop_group,
                "ranking_share": round(float(share), 8),
                "score": round(float(candidate.score), 8),
            })
            group_scores[candidate.crop_group] = (
                group_scores.get(candidate.crop_group, 0.0) + float(share)
            )

    # A declaration is a prior with explicit authority. Confirmed declarations
    # are authoritative; a valid group such as "cereal" is never treated as
    # missing and "corn" has already normalized to maize.
    if declared not in {"", "unknown"}:
        group = _declared_group(declared)
        if authority in {"USER_CONFIRMED", "AGRONOMIST_CONFIRMED"}:
            group_scores = {group: 0.99}
            unknown = 0.01
        else:
            group_scores[group] = group_scores.get(group, 0.0) + 0.65
            unknown = max(0.08, 0.35 * (1.0 - quality["score"]))
    else:
        unknown = max(0.10, 1.0 - quality["score"])

    # Open-set rejection: weak, narrow, or non-discriminative evidence should
    # stop at unknown or crop group rather than force a species.
    sorted_groups = sorted(group_scores.values(), reverse=True)
    group_gap = (
        sorted_groups[0] - sorted_groups[1]
        if len(sorted_groups) > 1 else sorted_groups[0]
        if sorted_groups else 0.0
    )
    if quality["score"] < 0.35 or group_gap < 0.05:
        unknown = max(unknown, 0.55)
    group_posterior = _normalize_distribution(group_scores, unknown)
    best_group, best_probability = max(
        group_posterior.items(), key=lambda item: item[1]
    )
    deepest_level = (
        "UNKNOWN" if best_group == "unknown"
        else "CROP_GROUP"
    )

    scientific = {
        "contract_version": CROP_POSTERIOR_CONTRACT_VERSION,
        "plot_id": plot_id,
        "parent_run_id": run_id,
        "pass": "PRE_ASMAE",
        "authority": authority,
        "declared_crop_normalized": declared or None,
        "crop_group_posterior": group_posterior,
        "asmae_mixture_conditioning": _mixture_conditioning(
            group_posterior
        ),
        "unknown_probability": group_posterior.get("unknown", 0.0),
        "deepest_supported_level": deepest_level,
        "top_group": best_group,
        "top_group_probability": best_probability,
        "calibration_status": "uncalibrated_group_mixture",
        "species_ranking": species_ranking,
        "species_probability_published": False,
        "evidence_quality": quality,
        "engine_evidence": engine_evidence,
        "ml_status": "not_claimed_without_loaded_validated_artifact",
        "ml_production_eligible": False,
    }
    scientific["lineage_id"] = "CROP-LINEAGE-" + _stable({
        "plot_id": plot_id,
        "parent_run_id": run_id,
        "declared_crop": declared or None,
        "admitted_support": [
            row["_support_id"] for row in rows
        ],
    })[:24]
    scientific["content_hash"] = _stable(scientific)
    scientific["generated_at"] = datetime.now(timezone.utc).isoformat()
    return scientific


def condition_crop_context(
    crop_config: Optional[Mapping[str, Any]],
    crop_posterior: Mapping[str, Any],
) -> Dict[str, Any]:
    result = dict(crop_config or {})
    declared = normalize_declared_crop(
        result.get("crop") or result.get("crop_type")
    )
    if declared == "corn":
        declared = "maize"
    if declared:
        result["crop"] = declared
    mixture = dict(
        crop_posterior.get("asmae_mixture_conditioning")
        or _mixture_conditioning(
            crop_posterior.get("crop_group_posterior") or {}
        )
    )
    result.update({
        "crop_posterior": dict(crop_posterior),
        "crop_group_posterior": dict(
            crop_posterior.get("crop_group_posterior") or {}
        ),
        "unknown_probability": crop_posterior.get(
            "unknown_probability", 1.0
        ),
        "crop_identity_authority": crop_posterior.get(
            "authority", "UNKNOWN"
        ),
        "crop_posterior_hash": crop_posterior.get("content_hash"),
        "crop_lineage_id": crop_posterior.get("lineage_id"),
        "crop_mixture_conditioning": True,
        "crop_mixture_known_mass": mixture.get("known_mass", 0.0),
        "crop_mixture_group_weights": mixture.get(
            "broad_group_weights", {}
        ),
        "crop_mixture_parameter_variance": mixture.get(
            "parameter_variance", {}
        ),
        "crop_mixture_bounds": mixture.get("bounds", {}),
    })
    if float(mixture.get("known_mass", 0.0) or 0.0) >= 0.20:
        result.update(dict(mixture.get("parameters") or {}))
    return result


def refine_crop_posterior(
    pre_posterior: Mapping[str, Any],
    asmae_plot_state: Optional[Mapping[str, Any]],
    *,
    parent_run_id: str,
    material_change_threshold: float = 0.25,
) -> Dict[str, Any]:
    """Bounded pass-B refinement; ASMAE-derived evidence is not independent."""
    before = dict(pre_posterior.get("crop_group_posterior") or {})
    scores = {
        key: float(value) for key, value in before.items()
        if key != "unknown"
    }
    artifact = dict(asmae_plot_state or {})
    posterior = dict(artifact.get("posterior") or {})
    structure = (
        posterior.get("structure", {}).get("mean")
        if isinstance(posterior.get("structure"), dict) else None
    )
    phenology = (
        posterior.get("phenology_progress", {}).get("mean")
        if isinstance(posterior.get("phenology_progress"), dict) else None
    )
    vigor = (
        posterior.get("vigor", {}).get("mean")
        if isinstance(posterior.get("vigor"), dict) else None
    )
    # This feedback is dependent on evidence already used in pass A, so its
    # total likelihood influence is capped at 15%.
    if _finite(structure) is not None and float(structure) >= 0.65:
        for group in list(scores):
            if _broad_group(group) in {"orchard", "perennial"}:
                scores[group] *= 1.15
    if _finite(phenology) is not None and _finite(vigor) is not None:
        if float(vigor) < 0.2 and 0.2 < float(phenology) < 0.8:
            for group in list(scores):
                if _broad_group(group) == "fallow":
                    scores[group] *= 1.10
    unknown = float(before.get("unknown", 1.0))
    after = _normalize_distribution(scores, unknown)
    keys = set(before) | set(after)
    change = 0.5 * sum(
        abs(float(before.get(key, 0.0)) - float(after.get(key, 0.0)))
        for key in keys
    )
    scientific = {
        **{
            key: value for key, value in dict(pre_posterior).items()
            if key not in {"content_hash", "generated_at"}
        },
        "pass": "POST_ASMAE",
        "crop_group_posterior": after,
        "asmae_mixture_conditioning": _mixture_conditioning(after),
        "unknown_probability": after.get("unknown", 0.0),
        "parent_crop_posterior_hash": pre_posterior.get("content_hash"),
        "lineage_id": pre_posterior.get("lineage_id"),
        "asmae_plot_state_hash": artifact.get("content_hash"),
        "dependent_feedback_weight_cap": 0.15,
        "posterior_change_total_variation": round(change, 8),
        "material_change_threshold": material_change_threshold,
        "material_change": change >= material_change_threshold,
        "double_count_prevention": "asmae_feedback_treated_as_dependent",
    }
    scientific["content_hash"] = _stable(scientific)
    scientific["child_run_id"] = (
        "AGB2-CROP-" + _stable({
            "parent_run_id": parent_run_id,
            "crop_posterior_hash": scientific["content_hash"],
        })[:20]
        if scientific["material_change"]
        else None
    )
    scientific["generated_at"] = datetime.now(timezone.utc).isoformat()
    return scientific

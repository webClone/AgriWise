"""Canonical probabilistic crop identity for the two-pass ASMAE/L2 loop."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import platform
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .crop_science_data import get_crop_group


CROP_POSTERIOR_CONTRACT_VERSION = "crop_identity_posterior_v3"
_TEMPORAL_PRIOR_CONTRACT_VERSION = "crop_cycle_temporal_prior_v1"
_TEMPORAL_PRIOR_MAX_WEIGHT = 0.12
_TEMPORAL_PRIOR_SUPPORT_HALF_LIFE = 2.0
_TEMPORAL_PRIOR_AGE_HALF_LIFE_DAYS = 60.0
_AUTHORITY_RANK = {
    "UNKNOWN": 0,
    "MODEL_SPECIES_POSTERIOR": 1,
    "MODEL_GROUP_POSTERIOR": 2,
    "ARCHIVE_STABLE_GROUP": 3,
    "REGISTRY_DECLARED": 4,
    "OFFICIAL_PARCEL_LABEL": 5,
    "AGRONOMIST_CONFIRMED": 6,
    "USER_CONFIRMED": 7,
    "FARMER_CONFIRMED": 7,
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


def _scientific_content_hash(value: Mapping[str, Any]) -> str:
    """Hash the immutable scientific payload, excluding envelope fields."""
    return _stable({
        key: item
        for key, item in value.items()
        if key not in {"content_hash", "generated_at"}
    })


def normalize_declared_crop(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(raw, raw)


def _cycle_identity(
    crop_config: Mapping[str, Any],
    operational_context: Mapping[str, Any],
) -> Tuple[Optional[str], str]:
    """Resolve a real crop-cycle boundary; never invent a default season.

    Explicit database cycle/season identifiers are preferred.  A declared
    planting date is a conservative compatibility identity for deployments
    that have not transported the database id yet.  Plot id alone is never a
    cycle identity because it would carry a belief across rotations.
    """
    for source in (crop_config, operational_context):
        for key in (
            "crop_cycle_id", "crop_season_id", "cycle_id", "season_id",
        ):
            raw = source.get(key)
            value = str(raw or "").strip()
            if value and value.lower() not in {"unknown", "default", "default_season"}:
                return value, key

    planting = str(
        crop_config.get("planting_date")
        or operational_context.get("planting_date")
        or ""
    ).strip()
    crop = normalize_declared_crop(
        crop_config.get("crop") or crop_config.get("crop_type")
    )
    if planting and crop not in {"", "unknown"}:
        return f"planting:{planting[:10]}:{crop}", "planting_date_crop"
    return None, "unavailable"


def _parse_utc(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _apply_cycle_bounded_temporal_prior(
    current: Mapping[str, Any],
    previous: Any,
    *,
    plot_id: str,
    cycle_identity: Optional[str],
    current_declared_crop: Optional[str],
    current_authority: str,
    current_physical_acquisition_count: int,
    generated_at: datetime,
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """Blend a weak same-cycle memory without counting it as observation.

    This is a convex prior blend, not a likelihood update.  Its absolute
    influence is capped, decays with newly admitted independent support and
    age, and is reset unless both posteriors carry the exact same cycle id.
    """
    audit: Dict[str, Any] = {
        "contract_version": _TEMPORAL_PRIOR_CONTRACT_VERSION,
        "role": "prior_only_not_observation",
        "counted_as_evidence": False,
        "applied": False,
        "reason": "unavailable",
        "current_cycle_identity": cycle_identity,
        "current_declared_crop": current_declared_crop or None,
        "current_authority": current_authority,
        "weight": 0.0,
        "maximum_weight": _TEMPORAL_PRIOR_MAX_WEIGHT,
        "new_physical_acquisition_count": 0,
    }
    normalized_current = _normalize_distribution(
        {
            key: float(value)
            for key, value in current.items()
            if key != "unknown" and _finite(value) is not None
        },
        float(current.get("unknown", 0.0) or 0.0),
    )
    if not cycle_identity:
        audit["reason"] = "current_cycle_identity_missing"
        return normalized_current, audit
    if not isinstance(previous, Mapping) or not previous:
        audit["reason"] = "previous_posterior_missing"
        return normalized_current, audit
    if str(previous.get("plot_id") or "") != str(plot_id):
        audit["reason"] = "plot_identity_mismatch"
        return normalized_current, audit

    previous_cycle = str(previous.get("crop_cycle_identity") or "").strip()
    audit["previous_cycle_identity"] = previous_cycle or None
    if not previous_cycle:
        audit["reason"] = "previous_cycle_identity_missing"
        return normalized_current, audit
    if previous_cycle != cycle_identity:
        audit["reason"] = "crop_cycle_changed_reset"
        return normalized_current, audit

    current_declared = normalize_declared_crop(current_declared_crop)
    previous_declared = normalize_declared_crop(
        previous.get("declared_crop_normalized")
    )
    audit["previous_declared_crop"] = previous_declared or None
    if (
        current_declared != previous_declared
        and (current_declared not in {"", "unknown"}
             or previous_declared not in {"", "unknown"})
    ):
        audit["reason"] = "declared_identity_changed_reset"
        return normalized_current, audit
    if current_authority in {
        "USER_CONFIRMED",
        "FARMER_CONFIRMED",
        "AGRONOMIST_CONFIRMED",
        "OFFICIAL_PARCEL_LABEL",
    }:
        audit["reason"] = "confirmed_declaration_authoritative"
        return normalized_current, audit

    previous_hash = str(previous.get("content_hash") or "").strip()
    prior_distribution = previous.get("crop_group_posterior")
    if not previous_hash or not isinstance(prior_distribution, Mapping):
        audit["reason"] = "previous_prior_lineage_invalid"
        return normalized_current, audit
    recomputed_hash = _scientific_content_hash(previous)
    if not hmac.compare_digest(previous_hash, recomputed_hash):
        audit["reason"] = "previous_prior_content_hash_invalid"
        return normalized_current, audit
    previous_generated = _parse_utc(previous.get("generated_at"))
    if previous_generated is None or previous_generated > generated_at:
        audit["reason"] = "previous_prior_time_invalid"
        return normalized_current, audit

    prior = _normalize_distribution(
        {
            key: float(value)
            for key, value in prior_distribution.items()
            if key != "unknown" and _finite(value) is not None
        },
        float(prior_distribution.get("unknown", 0.0) or 0.0),
    )
    previous_quality = previous.get("evidence_quality")
    if (
        not isinstance(previous_quality, Mapping)
        or previous_quality.get("physical_acquisition_count") is None
    ):
        audit["reason"] = "previous_physical_acquisition_count_missing"
        return normalized_current, audit
    previous_physical_count = int(
        previous_quality.get("physical_acquisition_count", 0) or 0
    )
    current_physical_count = max(0, int(current_physical_acquisition_count))
    new_physical_count = max(
        0, current_physical_count - previous_physical_count
    )
    age_days = max(
        0.0, (generated_at - previous_generated).total_seconds() / 86400.0,
    )
    support_decay = math.pow(
        0.5, new_physical_count / _TEMPORAL_PRIOR_SUPPORT_HALF_LIFE,
    )
    age_decay = math.pow(
        0.5, age_days / _TEMPORAL_PRIOR_AGE_HALF_LIFE_DAYS,
    )
    weight = min(
        _TEMPORAL_PRIOR_MAX_WEIGHT,
        _TEMPORAL_PRIOR_MAX_WEIGHT * support_decay * age_decay,
    )
    if weight < 0.005:
        audit.update({
            "reason": "prior_decayed_below_threshold",
            "new_physical_acquisition_count": new_physical_count,
            "age_days": round(age_days, 6),
        })
        return normalized_current, audit

    keys = set(normalized_current) | set(prior)
    blended = {
        key: (1.0 - weight) * float(normalized_current.get(key, 0.0))
        + weight * float(prior.get(key, 0.0))
        for key in keys
    }
    result = _normalize_distribution(
        {key: value for key, value in blended.items() if key != "unknown"},
        blended.get("unknown", 0.0),
    )
    audit.update({
        "applied": True,
        "reason": "same_cycle_weak_prior",
        "weight": round(weight, 8),
        "previous_posterior_hash": previous_hash,
        "previous_physical_acquisition_count": previous_physical_count,
        "current_physical_acquisition_count": current_physical_count,
        "new_physical_acquisition_count": new_physical_count,
        "age_days": round(age_days, 6),
        "support_decay": round(support_decay, 8),
        "age_decay": round(age_decay, 8),
    })
    return result, audit


def crop_authority(crop_config: Mapping[str, Any]) -> str:
    candidates = ["UNKNOWN"]
    explicit = str(
        crop_config.get("crop_identity_authority")
        or crop_config.get("crop_authority")
        or crop_config.get("declared_crop_authority")
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
        if row.get("independence_identity_available") is False:
            # Provider reprocessing/content identities are not independent
            # acquisitions.  Sentinel-2 packets lacking the physical key must
            # not inflate temporal support.
            continue
        if not is_admitted_temporal_record(
            row,
            value_keys=(
                "ndvi", "ndvi_mean", "evi", "evi_mean", "ndmi",
                "ndmi_mean", "ndwi", "ndwi_mean", "ndre", "ndre_mean",
                "cired", "cired_mean", "lswi", "lswi_mean", "psri",
                "psri_mean", "vv", "vv_db", "vv_db_mean", "vh",
                "vh_db", "vh_db_mean",
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
                "ndmi", "ndmi_mean", "ndwi", "ndwi_mean", "ndre",
                "ndre_mean", "cired", "cired_mean", "lswi", "lswi_mean",
                "psri", "psri_mean", "vv", "vv_db", "vv_db_mean",
                "vh", "vh_db", "vh_db_mean",
            )
        }
        if not any(value is not None for value in signals.values()):
            continue
        support_id = str(
            row.get("physical_acquisition_key")
            or row.get("content_hash")
            or row.get("observation_id")
            or row.get("scene_id")
            or f"{stamp.isoformat()}:{row.get('source', 'unknown')}"
        )
        row["_parsed_date"] = stamp
        row["_signals"] = signals
        row["_support_id"] = support_id
        existing = admitted.get(support_id)
        if existing is None or (
            float(row.get("reading_reliability") or 0.0),
            float(row.get("valid_fraction") or 0.0),
            str(row.get("processing_timestamp") or ""),
        ) > (
            float(existing.get("reading_reliability") or 0.0),
            float(existing.get("valid_fraction") or 0.0),
            str(existing.get("processing_timestamp") or ""),
        ):
            admitted[support_id] = row
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
                "ndmi", "ndmi_mean", "ndwi", "ndwi_mean", "ndre",
                "ndre_mean", "cired", "cired_mean", "lswi", "lswi_mean",
                "psri", "psri_mean",
            )
        ) else "",
        "sar" if any(
            _finite(row.get(key)) is not None
            for row in rows for key in (
                "vv", "vv_db", "vv_db_mean", "vh", "vh_db", "vh_db_mean",
            )
        ) else "",
    } - {""}
    physical_count = len({row["_support_id"] for row in rows})
    content_count = len({
        str(row.get("content_hash")) for row in rows if row.get("content_hash")
    })
    processing_product_count = sum(
        max(1, int(row.get("processing_lineage_count") or 1)) for row in rows
    )
    independence = min(1.0, physical_count / 12.0)
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
        "content_distinct_count": content_count,
        "physical_acquisition_count": physical_count,
        "processing_product_count": processing_product_count,
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
    archive = dict(archive_context or {})
    # Generic Layer-1 history is intentionally not parsed into observational
    # features here.  Canonical crop evidence must be selected by the verified
    # CropEvidenceLedgerV2; history has a separately labelled prior role.
    rows: List[Dict[str, Any]] = []
    quality = _evidence_quality(rows)
    evidence_ledger = None
    evidence_ledger_payload = operational.get("crop_evidence_ledger") or {}
    if evidence_ledger_payload:
        from services.agribrain.scientific_contracts.crop_evidence import CropEvidenceLedgerV2
        evidence_ledger = CropEvidenceLedgerV2.from_dict(
            evidence_ledger_payload
        )
        if evidence_ledger.plot_namespace.plot_id != str(plot_id):
            raise ValueError("Crop evidence ledger plot namespace mismatch")
        for key, actual in (
            ("tenant_id", evidence_ledger.plot_namespace.tenant_id),
            ("farm_id", evidence_ledger.plot_namespace.farm_id),
        ):
            expected = str(operational.get(key) or "").strip()
            if expected and expected != actual:
                raise ValueError(
                    f"Crop evidence ledger {key} namespace mismatch"
                )
        expected_ledger_hash = str(
            operational.get("crop_evidence_ledger_hash") or ""
        )
        if (
            expected_ledger_hash
            and evidence_ledger.ledger_hash != expected_ledger_hash
        ):
            raise ValueError("Crop evidence ledger hash mismatch")
    declared = normalize_declared_crop(
        crop_config.get("crop") or crop_config.get("crop_type")
    )
    authority = crop_authority(crop_config)
    cycle_identity, cycle_identity_source = _cycle_identity(
        crop_config, operational
    )

    lat = _finite(_nested(operational, "lat", "latitude"))
    lng = _finite(_nested(operational, "lng", "lon", "longitude"))
    area = _finite(_nested(operational, "area_ha", "plot_area_ha"))
    soil = _nested(operational, "soil_type", "soil_texture_class")
    irrigation = _nested(operational, "irrigation_type", "irrigation_method")

    # Build the governed engineered-expert input even while the learned model
    # remains release-gated.  This closes the provenance path now without
    # promoting an unvalidated RF artifact into canonical crop truth.
    crop_model_input_receipt = None
    crop_model_input_error = None
    ledger_feature_vector = None
    crop_cycle_segmentation_receipt = None
    if evidence_ledger is not None:
        try:
            from .features.ledger_crop_features import (
                build_ledger_crop_feature_input,
                ledger_rows_for_observations,
            )

            (
                ledger_feature_vector,
                crop_model_input_receipt,
                crop_cycle_segmentation_receipt,
            ) = (
                build_ledger_crop_feature_input(
                    ledger=evidence_ledger,
                    crop_cycle_hypothesis_id=(cycle_identity or "unresolved-cycle"),
                    run_id=run_id,
                    latitude=lat,
                    longitude=lng,
                    koppen_zone=_nested(
                        operational, "climate_zone", "koppen_zone"
                    ),
                    aridity_index=_finite(_nested(
                        operational, "aridity_index"
                    )),
                    soil_texture_class=(
                        str(soil) if soil is not None else None
                    ),
                    irrigation_type=(
                        str(irrigation) if irrigation is not None else None
                    ),
                    plot_area_ha=area,
                )
            )
            rows = ledger_rows_for_observations(
                evidence_ledger,
                crop_cycle_segmentation_receipt.current_observation_ids,
            )
            quality = _evidence_quality(rows)
            scoped_readiness = (
                crop_cycle_segmentation_receipt.current_evidence_readiness
            )
            quality.update({
                "physical_acquisition_count": (
                    scoped_readiness.physical_acquisition_count
                ),
                "processing_product_count": len(rows),
                "admitted_record_count": len(rows),
                "admitted_ndvi_count": (
                    scoped_readiness.ndvi_observation_count
                ),
                "temporal_span_days": (
                    scoped_readiness.temporal_span_days or 0.0
                ),
                "independent_feature_families": list(
                    scoped_readiness.feature_families
                ),
                "phase_coverage": list(scoped_readiness.phase_coverage),
                "sensor_counts": dict(scoped_readiness.sensor_counts),
                "gdd_spans": {
                    basis: {
                        "min": minimum,
                        "max": maximum,
                        "span": span,
                        "count": count,
                    }
                    for basis, minimum, maximum, span, count
                    in scoped_readiness.gdd_spans
                },
                "domain_compatibility": {
                    "calibration": (
                        scoped_readiness.calibration_domain_compatibility
                    ),
                    "geographical": (
                        scoped_readiness.geographical_domain_compatibility
                    ),
                },
                "segment_readiness_status": (
                    scoped_readiness.readiness_status
                ),
                "segment_readiness_blockers": list(
                    scoped_readiness.blockers
                ),
            })
        except Exception as exc:
            crop_model_input_error = (
                f"crop_model_input_invalid:{type(exc).__name__}:{str(exc)[:160]}"
            )

    species_ranking: List[Dict[str, Any]] = []
    group_scores: Dict[str, float] = {}
    engine_evidence: Dict[str, Any] = {
        "observation_contract": "verified_crop_evidence_ledger_v2_only",
        "generic_plot_timeseries_consumed": False,
        "crop_evidence_ledger_hash": (
            evidence_ledger.ledger_hash if evidence_ledger else None
        ),
        "cycle_hypothesis_runs": [],
    }
    species_scores: Dict[str, Dict[str, Any]] = {}
    if evidence_ledger is not None and crop_cycle_segmentation_receipt is not None:
        from .crop_identification import identify_crop
        from .features.ledger_crop_features import ledger_rows_for_observations

        for hypothesis in crop_cycle_segmentation_receipt.current_cycle_hypotheses:
            hypothesis_rows = ledger_rows_for_observations(
                evidence_ledger, hypothesis.observation_ids,
            )
            ndvi, ndvi_dates = _series(
                hypothesis_rows, ("ndvi_clean", "ndvi", "ndvi_mean")
            )
            vv = _mean(hypothesis_rows, ("vv", "vv_db", "vv_db_mean"))
            vh = _mean(hypothesis_rows, ("vh", "vh_db", "vh_db_mean"))
            run_audit = {
                "hypothesis_id": hypothesis.hypothesis_id,
                "hypothesis_probability": hypothesis.probability,
                "observation_ids": list(hypothesis.observation_ids),
                "executed": False,
            }
            # Sparse inputs remain unresolved. Location, registry, weather,
            # soil and generic history are deliberately absent from this EO
            # expert call and remain separate priors.
            if len(ndvi) < 4 and vv is None and vh is None:
                run_audit["reason"] = "ledger_evidence_insufficient"
                engine_evidence["cycle_hypothesis_runs"].append(run_audit)
                continue
            result = identify_crop(
                ndvi_series=ndvi or None,
                ndvi_dates=ndvi_dates or None,
                peak_ndvi=max(ndvi) if ndvi else None,
                trough_ndvi=min(ndvi) if ndvi else None,
                sar_vh_mean=vh,
                sar_vv_mean=vv,
                evi_mean=_mean(hypothesis_rows, ("evi", "evi_mean")),
                ndmi_mean=_mean(hypothesis_rows, ("ndmi", "ndmi_mean")),
                ndwi_mean=_mean(hypothesis_rows, ("ndwi", "ndwi_mean")),
                plot_id=plot_id,
                run_id=run_id,
            )
            run_audit.update({
                "executed": True,
                "engine_version": (result.evidence or {}).get(
                    "engine_version"
                ),
            })
            engine_evidence["cycle_hypothesis_runs"].append(run_audit)
            if not engine_evidence.get("engine_version"):
                engine_evidence["engine_version"] = run_audit.get(
                    "engine_version"
                )
            for candidate in result.candidates:
                share = candidate.softmax_candidate_share
                if not isinstance(share, (int, float)):
                    continue
                weighted_share = float(share) * hypothesis.probability
                entry = species_scores.setdefault(candidate.code, {
                    "code": candidate.code,
                    "crop_group": candidate.crop_group,
                    "ranking_share": 0.0,
                    "score": 0.0,
                })
                entry["ranking_share"] += weighted_share
                entry["score"] += float(candidate.score) * hypothesis.probability
                group_scores[candidate.crop_group] = (
                    group_scores.get(candidate.crop_group, 0.0)
                    + weighted_share
                )
    species_ranking = sorted(
        (
            {
                **entry,
                "ranking_share": round(entry["ranking_share"], 8),
                "score": round(entry["score"], 8),
            }
            for entry in species_scores.values()
        ),
        key=lambda entry: (-entry["ranking_share"], entry["code"]),
    )

    # Preserve the declaration-free, memory-free ledger ranking before
    # registry authority and previous-cycle memory condition the ASMAE prior.
    # This is an uncalibrated EO diagnostic, not species confirmation.
    model_context_scores = dict(group_scores)
    model_context_unknown = max(0.10, 1.0 - quality["score"])
    model_context_sorted = sorted(
        model_context_scores.values(), reverse=True
    )
    model_context_gap = (
        model_context_sorted[0] - model_context_sorted[1]
        if len(model_context_sorted) > 1
        else model_context_sorted[0]
        if model_context_sorted else 0.0
    )
    if quality["score"] < 0.35 or model_context_gap < 0.05:
        model_context_unknown = max(model_context_unknown, 0.55)
    model_context_group_posterior = _normalize_distribution(
        model_context_scores, model_context_unknown
    )
    physical_support = int(quality["physical_acquisition_count"] or 0)
    if physical_support <= 0:
        model_context_status = "unavailable"
    elif physical_support < 4:
        model_context_status = "insufficient"
    elif physical_support < 6:
        model_context_status = "sparse_ranking_only"
    else:
        model_context_status = "observed_ranking_only"
    model_context_support = {
        "status": model_context_status,
        "admitted_physical_acquisition_count": physical_support,
        "admitted_ndvi_count": int(quality["admitted_ndvi_count"] or 0),
        "registry_declaration_included": False,
        "temporal_prior_included": False,
        "context_features_may_be_included": False,
        "generic_plot_timeseries_included": False,
        "crop_evidence_ledger_required": True,
        "crop_evidence_ledger_hash": (
            evidence_ledger.ledger_hash if evidence_ledger else None
        ),
        "cycle_segmentation_status": (
            crop_cycle_segmentation_receipt.status
            if crop_cycle_segmentation_receipt else "unavailable"
        ),
        "cycle_hypothesis_marginalized": bool(
            crop_cycle_segmentation_receipt
            and len(
                crop_cycle_segmentation_receipt.current_cycle_hypotheses
            ) > 1
        ),
        "species_confirmation_allowed": False,
        "role": "ledger_only_declaration_free_uncalibrated_group_ranking",
    }

    # A declaration is a prior with explicit authority. Confirmed declarations
    # are authoritative; a valid group such as "cereal" is never treated as
    # missing and "corn" has already normalized to maize.
    if declared not in {"", "unknown"}:
        group = _declared_group(declared)
        if authority in {
            "USER_CONFIRMED",
            "FARMER_CONFIRMED",
            "AGRONOMIST_CONFIRMED",
        }:
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
    generated_at = datetime.now(timezone.utc)
    group_posterior, temporal_prior = _apply_cycle_bounded_temporal_prior(
        group_posterior,
        archive.get("previous_crop_posterior"),
        plot_id=plot_id,
        cycle_identity=cycle_identity,
        current_declared_crop=declared or None,
        current_authority=authority,
        current_physical_acquisition_count=quality[
            "physical_acquisition_count"
        ],
        generated_at=generated_at,
    )
    best_group, best_probability = max(
        group_posterior.items(), key=lambda item: item[1]
    )
    deepest_level = (
        "UNKNOWN" if best_group == "unknown"
        else "CROP_GROUP"
    )
    from services.agribrain.scientific_contracts.crop_governance import CropModelReceiptV1
    crop_model_receipt = CropModelReceiptV1(
        model_family="ledger-bound-legacy-temporal-diagnostic",
        semantic_version=str(
            engine_evidence.get("engine_version") or "5.1-diagnostic"
        ),
        artifact_sha256="",
        feature_schema_version="crop-ledger-eo-ranking-v1",
        feature_schema_hash="",
        class_hierarchy_version="crop-taxonomy-v2",
        training_dataset_manifest_hash="",
        calibration_artifact_hash="",
        validation_report_hash="",
        region_domain_compatibility=(),
        production_eligible=False,
        inference_device="cpu",
        runtime_version="python-" + platform.python_version(),
        deterministic_preprocessing_version="crop-ledger-eo-preprocess-v1",
        eligibility_reasons=(
            "ledger_bound_heuristic_not_species_model",
            "production_temporal_model_artifact_unavailable",
            "calibration_and_external_validation_unavailable",
        ),
    )

    posterior_observation_ids = sorted({
        observation_id
        for hypothesis in (
            crop_cycle_segmentation_receipt.current_cycle_hypotheses
            if crop_cycle_segmentation_receipt else ()
        )
        for observation_id in hypothesis.observation_ids
    })
    posterior_observation_id_set = set(posterior_observation_ids)
    selected_hashes_for_posterior = {
        observation.observation_hash
        for observation in (evidence_ledger.observations if evidence_ledger else ())
        if observation.observation_id in posterior_observation_id_set
    }

    scientific = {
        "contract_version": CROP_POSTERIOR_CONTRACT_VERSION,
        "plot_id": plot_id,
        "parent_run_id": run_id,
        "pass": "PRE_ASMAE",
        "authority": authority,
        "crop_cycle_identity": cycle_identity,
        "crop_cycle_identity_source": cycle_identity_source,
        "declared_crop_normalized": declared or None,
        "model_context_group_posterior": model_context_group_posterior,
        "model_context_support": model_context_support,
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
        "species_evidence_status": "ranking_only_not_independently_confirmed",
        "species_science_provenance": (
            "mixed_curated_and_architecture_default_signatures"
        ),
        "observational_input_policy": {
            "authority": "verified_crop_evidence_ledger_v2_only",
            "generic_plot_timeseries_consumed": False,
            "generic_history_role": "prior_or_diagnostic_only",
            "posterior_observation_ids": posterior_observation_ids,
            "cycle_hypotheses_marginalized": bool(
                crop_cycle_segmentation_receipt
                and len(
                    crop_cycle_segmentation_receipt.current_cycle_hypotheses
                ) > 1
            ),
        },
        "evidence_quality": quality,
        "crop_evidence_ledger_hash": (
            evidence_ledger.ledger_hash if evidence_ledger else None
        ),
        "crop_evidence_ledger_status": (
            "verified" if evidence_ledger else "unavailable"
        ),
        "independent_evidence_ids": (
            [
                cluster.cluster_id
                for cluster in evidence_ledger.independence_clusters
                if cluster.independence_eligible and cluster.admitted
                and cluster.selected_observation_hash
                in selected_hashes_for_posterior
            ]
            if evidence_ledger else []
        ),
        "engine_evidence": engine_evidence,
        "temporal_prior": temporal_prior,
        "ml_status": "not_claimed_without_loaded_validated_artifact",
        "ml_production_eligible": crop_model_receipt.production_eligible,
        "crop_model_receipt": crop_model_receipt.to_dict(),
        "crop_model_receipt_hash": crop_model_receipt.content_hash,
        "crop_model_input_receipt": (
            crop_model_input_receipt.to_dict()
            if crop_model_input_receipt is not None else None
        ),
        "crop_model_input_receipt_hash": (
            crop_model_input_receipt.content_hash
            if crop_model_input_receipt is not None else None
        ),
        "crop_model_input_status": (
            "ledger_bound_diagnostic"
            if crop_model_input_receipt is not None else "unavailable"
        ),
        "crop_model_input_error": crop_model_input_error,
        "crop_cycle_segmentation_receipt": (
            crop_cycle_segmentation_receipt.to_dict()
            if crop_cycle_segmentation_receipt is not None else None
        ),
        "crop_cycle_segmentation_receipt_hash": (
            crop_cycle_segmentation_receipt.content_hash
            if crop_cycle_segmentation_receipt is not None else None
        ),
        "engineered_expert_execution_eligible": bool(
            crop_model_input_receipt is not None
            and crop_model_input_receipt.model_execution_eligible
        ),
        "engineered_expert_publication_eligible": False,
    }
    scientific["lineage_id"] = "CROP-LINEAGE-" + _stable({
        "plot_id": plot_id,
        "parent_run_id": run_id,
        "declared_crop": declared or None,
        "crop_cycle_identity": cycle_identity,
        "previous_posterior_hash": temporal_prior.get(
            "previous_posterior_hash"
        ),
        "crop_evidence_ledger_hash": (
            evidence_ledger.ledger_hash if evidence_ledger else None
        ),
        "crop_cycle_segmentation_receipt_hash": (
            crop_cycle_segmentation_receipt.content_hash
            if crop_cycle_segmentation_receipt else None
        ),
        "posterior_observation_ids": posterior_observation_ids,
    })[:24]
    scientific["content_hash"] = _scientific_content_hash(scientific)
    scientific["generated_at"] = generated_at.isoformat()
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
    refinement_fingerprint = _scientific_content_hash(scientific)
    scientific["child_run_id"] = (
        "AGB2-CROP-" + _stable({
            "parent_run_id": parent_run_id,
            "refinement_fingerprint": refinement_fingerprint,
        })[:20]
        if scientific["material_change"]
        else None
    )
    scientific["content_hash"] = _scientific_content_hash(scientific)
    scientific["generated_at"] = datetime.now(timezone.utc).isoformat()
    return scientific

"""Deterministic CropEvidenceLedgerV2 -> engineered expert input adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from services.agribrain.scientific_contracts.crop_evidence import (
    CropEvidenceLedgerV2,
)
from services.agribrain.scientific_contracts.crop_model_input import (
    CropModelInputReceiptV1,
    build_crop_model_input_receipt,
    normalize_verified_crop_evidence_ledger,
    observation_tokens_from_ledger,
)
from services.agribrain.scientific_contracts.crop_cycle_segmentation import (
    CropCycleSegmentationReceiptV1,
    build_crop_cycle_segmentation_receipt,
)

from .crop_feature_vector import (
    CROP_FEATURE_TRANSFORM_VERSION,
    NO_NORMALIZATION_ARTIFACT_HASH,
    CropFeatureVector,
    crop_feature_schema_receipt,
    crop_feature_transform_hash,
    extract_crop_features,
)


_STATISTIC_PRIORITY = {
    "mean": 0,
    "p50": 1,
    "median": 2,
    "value": 3,
    "max": 4,
    "min": 5,
}


def _token_row(token: Any) -> Dict[str, Any]:
    grouped: Dict[str, list[Tuple[int, str, float]]] = {}
    for name, statistic, value in token.feature_values:
        grouped.setdefault(name, []).append((
            _STATISTIC_PRIORITY.get(str(statistic).lower(), 99),
            str(statistic),
            float(value),
        ))
    row: Dict[str, Any] = {
        "date": token.sensing_time,
        "timestamp": token.sensing_time,
        "observation_id": token.observation_id,
        "observation_hash": token.observation_hash,
        "physical_acquisition_key": token.physical_acquisition_key,
        "source_family": token.source_family,
        "support_hash": token.support_hash,
        "orbit_direction": token.orbit_direction,
        "relative_orbit": token.relative_orbit,
        "incidence_angle": token.incidence_angle,
        "polarizations": list(token.polarizations),
        "backscatter_unit": "db" if token.source_family.lower().replace("-", "_") in {
            "sentinel1", "s1", "sar", "radar",
        } else None,
    }
    coordinates = dict(token.gdd_coordinates)
    row["gdd_coordinates"] = coordinates
    if token.primary_gdd_basis:
        primary_value = coordinates.get(token.primary_gdd_basis)
        if primary_value is not None:
            row["gdd_accumulated"] = float(primary_value)
            row["primary_gdd_basis"] = token.primary_gdd_basis
    for feature_name, candidates in grouped.items():
        _, statistic, value = min(candidates)
        row[feature_name] = value
        row[f"{feature_name}_{statistic}"] = value
        if statistic == "mean":
            row[f"{feature_name}_mean"] = value
    return row


def ledger_rows_for_observations(
    ledger: CropEvidenceLedgerV2 | Mapping[str, Any],
    observation_ids: Sequence[str],
) -> list[Dict[str, Any]]:
    """Return heuristic-compatible rows from selected ledger tokens only.

    Quality metadata is joined from the verified ledger evidence item.  The
    function rejects a selection that is not exactly representable by the
    admitted physical representatives, preventing a caller from smuggling a
    generic temporal row into the legacy diagnostic expert.
    """
    ledger = normalize_verified_crop_evidence_ledger(ledger)
    selected = {str(value) for value in observation_ids}
    tokens = tuple(
        token for token in observation_tokens_from_ledger(ledger)
        if token.observation_id in selected
    )
    if {token.observation_id for token in tokens} != selected:
        raise ValueError("Crop-cycle selection contains observations outside the ledger")
    items = {
        str(item.get("observation_id")): item
        for item in ledger.evidence_items()
        if item.get("model_use_eligible") is True
    }
    rows: list[Dict[str, Any]] = []
    for token in tokens:
        row = _token_row(token)
        evidence_item = items.get(token.observation_id) or {}
        quality = evidence_item.get("data_quality")
        quality = dict(quality) if isinstance(quality, Mapping) else {}
        parsed = datetime.fromisoformat(
            token.sensing_time.replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        row.update({
            "_parsed_date": parsed.astimezone(timezone.utc),
            "_support_id": token.physical_acquisition_key,
            "valid_fraction": quality.get("valid_fraction"),
            "reading_reliability": quality.get("reading_reliability"),
            "quality_class": token.quality_class,
            "ledger_bound": True,
        })
        rows.append(row)
    return sorted(rows, key=lambda row: (row["_parsed_date"], row["observation_hash"]))


def build_ledger_crop_feature_input(
    *,
    ledger: CropEvidenceLedgerV2 | Mapping[str, Any],
    crop_cycle_hypothesis_id: str,
    run_id: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    koppen_zone: Optional[str] = None,
    aridity_index: Optional[float] = None,
    soil_texture_class: Optional[str] = None,
    irrigation_type: Optional[str] = None,
    plot_area_ha: Optional[float] = None,
) -> Tuple[
    CropFeatureVector,
    CropModelInputReceiptV1,
    CropCycleSegmentationReceiptV1,
]:
    """Build a model-ready vector only from admitted ledger observations.

    The function never accepts a generic ``FieldTensor.plot_timeseries``.  A
    caller must first provide a verified evidence ledger, ensuring exact
    observation identity, support and processing-lineage closure.
    """
    ledger = normalize_verified_crop_evidence_ledger(ledger)
    segmentation = build_crop_cycle_segmentation_receipt(
        ledger,
        crop_cycle_hypothesis_id=crop_cycle_hypothesis_id,
    )
    current_ids = set(segmentation.current_observation_ids)
    tokens = tuple(
        token for token in observation_tokens_from_ledger(ledger)
        if token.observation_id in current_ids
    )
    rows = [_token_row(token) for token in tokens]
    source_families = sorted({token.source_family for token in tokens})
    feature_vector = extract_crop_features(
        rows,
        plot_id=ledger.plot_namespace.plot_id,
        run_id=run_id,
        latitude=latitude,
        longitude=longitude,
        koppen_zone=koppen_zone,
        aridity_index=aridity_index,
        soil_texture_class=soil_texture_class,
        irrigation_type=irrigation_type,
        plot_area_ha=plot_area_ha,
        data_sources=source_families,
        require_ledger_provenance=True,
    )
    schema = crop_feature_schema_receipt()
    transform_hash = crop_feature_transform_hash()

    evidence_items = [
        item for item in ledger.evidence_items()
        if item.get("model_use_eligible") is True
        and str(item.get("observation_id")) in current_ids
    ]
    domain_values = {
        str(item.get("calibration_domain_compatibility") or "unverified")
        for item in evidence_items
    } | {
        str(item.get("geographical_domain_compatibility") or "unverified")
        for item in evidence_items
    }
    domain_compatibility = (
        "incompatible" if "incompatible" in domain_values
        else "compatible" if domain_values == {"compatible"}
        else "unverified"
    )
    receipt = build_crop_model_input_receipt(
        ledger=ledger,
        crop_cycle_hypothesis_id=(
            f"{crop_cycle_hypothesis_id}:{segmentation.primary_hypothesis_id}"
        ),
        feature_schema=schema,
        feature_values=feature_vector.to_flat_dict(),
        feature_transform_hash=transform_hash,
        normalization_artifact_hash=NO_NORMALIZATION_ARTIFACT_HASH,
        domain_compatibility=domain_compatibility,
        # A feature tensor is not a calibration artifact.  This remains
        # unavailable until a separate disjoint calibration receipt exists.
        calibration_validity="unavailable",
        selected_observation_ids=segmentation.current_observation_ids,
    )
    feature_vector.extraction_warnings.extend([
        "ledger_bound_model_input",
        f"transform_version:{CROP_FEATURE_TRANSFORM_VERSION}",
    ])
    return feature_vector, receipt, segmentation


__all__ = [
    "build_ledger_crop_feature_input",
    "ledger_rows_for_observations",
]

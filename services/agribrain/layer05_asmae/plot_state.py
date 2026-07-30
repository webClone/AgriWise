"""Always-on plot-state artifact construction and authority resolution."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from .config import STATE_NAMES


PLOT_STATE_CONTRACT_VERSION = "asmae_plot_state_v1"
STATE_AVAILABILITY = {
    "CURRENT_SPATIAL_ASSIMILATED",
    "CURRENT_PLOT_TIMESERIES_CONDITIONED",
    "ARCHIVE_CONDITIONED",
    "CONTEXT_PRIOR_CONDITIONED",
    "LAST_KNOWN_GOOD_STALE",
    "UNAVAILABLE",
}
AUTHORITY_LEVELS = {
    "NONE",
    "DIAGNOSTIC",
    "SCOUTING",
    "MODEL_ASSISTED",
    "PRODUCTION",
    "RETROVALIDATED",
    "CERTIFIED",
}


def canonical_availability(value: Any, *, spatial: bool = False) -> str:
    if spatial:
        return "CURRENT_SPATIAL_ASSIMILATED"
    raw = str(value or "").upper()
    mapping = {
        "TIMESERIES_CONDITIONED": "CURRENT_PLOT_TIMESERIES_CONDITIONED",
        "CURRENT_PLOT_TIMESERIES_CONDITIONED": "CURRENT_PLOT_TIMESERIES_CONDITIONED",
        "ARCHIVE_CONDITIONED": "ARCHIVE_CONDITIONED",
        "PRIOR_ONLY": "CONTEXT_PRIOR_CONDITIONED",
        "CONTEXT_PRIOR_CONDITIONED": "CONTEXT_PRIOR_CONDITIONED",
        "LAST_KNOWN_GOOD_STALE": "LAST_KNOWN_GOOD_STALE",
    }
    return mapping.get(raw, "UNAVAILABLE")


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def aggregate_spatial_posterior(
    state_result: Mapping[str, Any],
    support_ledger: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    means = state_result.get("raster_maps", {}) or {}
    sigmas = state_result.get("uncertainty_maps", {}) or {}
    ledger_dict = support_ledger if isinstance(support_ledger, dict) else {}
    result: Dict[str, Dict[str, Any]] = {}
    for index, state in enumerate(STATE_NAMES):
        values = []
        uncertainty = []
        for node_id, vector in means.items():
            if isinstance(vector, (list, tuple)) and index < len(vector):
                value = _finite(vector[index])
                if value is not None:
                    values.append(value)
            sigma_vector = sigmas.get(node_id)
            if isinstance(sigma_vector, (list, tuple)) and index < len(sigma_vector):
                value = _finite(sigma_vector[index])
                if value is not None:
                    uncertainty.append(value)

        entry = ledger_dict.get(state) or {}
        accepted_cnt = int(entry.get("accepted_update_count", 0) or 0)
        has_spatial = int(entry.get("spatial_update_count", 0) or 0) > 0 or (accepted_cnt > 0 and len(values) > 0)
        has_temporal = int(entry.get("temporal_update_count", 0) or 0) > 0 or (accepted_cnt > 0 and not has_spatial)

        if has_spatial and values:
            status = "spatially_conditioned"
            rel = "direct" if accepted_cnt > 0 else "proxy"
        elif has_temporal:
            status = "temporally_conditioned"
            rel = "indirect"
        elif values and state in ("vigor", "lai", "canopy_water"):
            status = "model_propagated"
            rel = "proxy"
        else:
            status = "prior_constrained" if values else "unsupported"
            rel = "none"

        result[state] = {
            "mean": sum(values) / len(values) if values else None,
            "sigma": sum(uncertainty) / len(uncertainty) if uncertainty else None,
            "spatial_cell_count": len(values),
            "status": status,
            "observation_relationship": rel,
            "authority": status,
            "accepted_updates": accepted_cnt,
            "source_nodes": entry.get("source_nodes", []),
            "last_update": entry.get("last_update"),
        }
    return result


def build_plot_state_artifact(
    *,
    plot_id: str,
    run_id: str,
    as_of: Any,
    availability: str,
    authority: str,
    posterior: Mapping[str, Any],
    support_ledger: Any,
    production_usable: bool,
    current_spatial_assimilation: bool,
    geometry_hash: str,
    evidence_hash: str = "",
    stale_age_days: Optional[float] = None,
    reason: str = "",
) -> Dict[str, Any]:
    availability = canonical_availability(availability, spatial=current_spatial_assimilation)
    as_of_text = as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of or "")
    if not as_of_text.strip():
        raise ValueError("plot-state artifact requires as_of")
    authority = str(authority or "").upper()
    if authority not in AUTHORITY_LEVELS:
        raise ValueError("plot-state artifact requires explicit valid authority")
    from services.agribrain.scientific_contracts.ledger_adapter import index_state_support_ledger
    from services.agribrain.scientific_contracts.state_schema_ref import STATE_SUPPORT_LEDGER_SCHEMA_VERSION

    indexed_ledger = index_state_support_ledger(support_ledger) if support_ledger is not None else {}
    payload = {
        "contract_version": PLOT_STATE_CONTRACT_VERSION,
        "state_support_ledger_schema_version": STATE_SUPPORT_LEDGER_SCHEMA_VERSION,
        "plot_id": plot_id,
        "run_id": run_id,
        "as_of": as_of_text,
        "state_availability": availability,
        "authority_level": authority,
        "posterior": dict(posterior or {}),
        "state_support_ledger": indexed_ledger,
        "production_usable": bool(production_usable),
        "current_spatial_assimilation": bool(current_spatial_assimilation),
        "spatial_raster_available": bool(current_spatial_assimilation),
        "geometry_hash": geometry_hash,
        "evidence_hash": evidence_hash,
        "stale_age_days": stale_age_days,
        "reason": reason,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    scientific = {
        key: value for key, value in payload.items()
        if key not in {"run_id", "generated_at"}
    }
    payload["content_hash"] = hashlib.sha256(
        json.dumps(scientific, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return payload


def intersect_artifact_authority(
    artifact: Mapping[str, Any],
    *,
    production_allowed: bool,
    scientific_production_usable: bool,
) -> Dict[str, Any]:
    """Ensure state authority can never exceed current run authority."""
    result = dict(artifact or {})
    requested = str(result.get("authority_level") or "NONE").upper()
    if requested not in AUTHORITY_LEVELS:
        requested = "NONE"
    production_grade = requested in {
        "PRODUCTION", "RETROVALIDATED", "CERTIFIED"
    }
    if not (
        production_allowed
        and scientific_production_usable
        and production_grade
    ):
        if requested in {"PRODUCTION", "RETROVALIDATED", "CERTIFIED"}:
            requested = "MODEL_ASSISTED" if result.get("posterior") else "DIAGNOSTIC"
        result["production_usable"] = False
    result["authority_level"] = requested
    scientific = {
        key: value for key, value in result.items()
        if key not in {"run_id", "generated_at", "content_hash"}
    }
    result["content_hash"] = hashlib.sha256(
        json.dumps(scientific, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return result

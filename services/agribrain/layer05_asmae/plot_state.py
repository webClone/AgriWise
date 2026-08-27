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
    from services.agribrain.scientific_contracts.state_support import (
        resolve_state_evidence_class, StateEvidenceClass,
    )
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

        ev_class = resolve_state_evidence_class(entry)
        if ev_class == StateEvidenceClass.DIRECTLY_ASSIMILATED:
            status = "spatially_conditioned"
            rel = "direct"
        elif ev_class == StateEvidenceClass.PROXY_ASSIMILATED:
            status = "spatially_conditioned" if has_spatial else "temporally_conditioned"
            rel = "proxy"
        elif ev_class == StateEvidenceClass.INDIRECTLY_CONSTRAINED:
            status = "temporally_conditioned"
            rel = "indirect"
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
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    payload["content_hash"] = hashlib.sha256(encoded).hexdigest()
    return payload


def intersect_artifact_authority(
    artifact: Dict[str, Any],
    *,
    production_allowed: bool = True,
    scientific_production_usable: bool = True,
) -> Dict[str, Any]:
    """
    Intersect plot-state artifact authority level with runtime gates.
    Demotes authority level if production is disallowed or unusable.
    """
    res = dict(artifact or {})
    current_auth = str(res.get("authority_level", "NONE")).upper()
    has_posterior = bool(res.get("posterior"))
    prod_usable = bool(res.get("production_usable", True)) and scientific_production_usable and production_allowed

    if not has_posterior:
        res["authority_level"] = "NONE"
        res["production_usable"] = False
        return res

    if not prod_usable:
        res["production_usable"] = False
        if current_auth in ("PRODUCTION", "RETROVALIDATED", "CERTIFIED", "MODEL_ASSISTED", "SCOUTING"):
            res["authority_level"] = "DIAGNOSTIC"
        return res

    res["production_usable"] = True
    return res

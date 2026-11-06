"""Canonical B2B-08 post-freeze input identity for physical L3 checkpoints.

The fingerprint covers the exact daily scientific inputs, sealed irrigation
claims, and the prior Kalman state/covariance that produced the checkpoint.
Only durable, matching evidence may be recovered. No key or admission token
is emitted in the digest. Unsupported data fails closed.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any


class CheckpointInputConflict(RuntimeError):
    """A durable physical delivery state cannot be reused for new evidence."""


def _canonical(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CheckpointInputConflict("nonfinite_checkpoint_input")
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise CheckpointInputConflict("naive_checkpoint_timestamp")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Enum):
        return _canonical(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical(asdict(value))
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise CheckpointInputConflict("nonstring_checkpoint_input_key")
        return {k: _canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    raise CheckpointInputConflict("unsupported_checkpoint_input_type")


def checkpoint_input_digest(
    *, day: str, zone_id: str, weather: Any,
    observations: Any, events: Any, prior_state: Any,
    prior_covariance: Any,
    last_obs_day: Any, days_since_obs: Any,
    seen_event_ids: Any = None,
) -> str:
    """One versioned digest for both durable writes and cold recovery checks.

    Ignore ephemeral transport packet IDs while retaining signed receipt
    grants, event payload, timestamp and scope; changing either precipitation
    or adding a distinct delivery changes the digest. Observation order is
    preserved because sequential Kalman updates need not commute.
    """
    from services.agribrain.layer0.event_forcing_admission import (
        resolve_physical_event_plan,
    )

    if events:
        for raw in events:
            if not isinstance(raw, Mapping):
                raise CheckpointInputConflict("invalid_checkpoint_event_envelope")

    plan = resolve_physical_event_plan(
        events,
        day=day,
        zone_id=zone_id,
        seen_event_ids=set(seen_event_ids) if seen_event_ids is not None else None,
    )

    normalized_events = []
    for item in plan:
        if not item.is_admissible:
            continue
        raw = item.envelope
        payload = raw.get("payload")
        if isinstance(payload, Mapping):
            norm_payload = {k: v for k, v in payload.items() if k != "event_id"}
        else:
            norm_payload = payload
        evt_dict = {
            k: raw[k] for k in (
                "source", "timestamp", "plot_id",
                "geometry_hash", "geometry_version",
            ) if k in raw
        }
        evt_dict["payload"] = norm_payload
        normalized_events.append(evt_dict)
    body = {
        "contract": "akaloris/layer0/physical-checkpoint-input/v1",
        "day": day,
        "zone_id": zone_id,
        "weather": weather,
        "observations": observations or [],
        "events": normalized_events,
        "prior_state": {
            "day": getattr(prior_state, "day", None),
            "values": getattr(prior_state, "values", None),
            "variance": getattr(prior_state, "variance", None),
            "covariance": getattr(prior_covariance, "P", None),
            "last_obs_day": last_obs_day,
            "days_since_obs": days_since_obs,
        },
    }
    encoded = json.dumps(
        _canonical(body), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

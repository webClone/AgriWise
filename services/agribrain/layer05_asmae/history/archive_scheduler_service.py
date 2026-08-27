"""Scheduled, idempotent bridge from archive manifests to the plot worldline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from layer0.archive.scene_manifest import HistoricalSceneRecord

from .worldline_service import PlotWorldlineService, WORLDLINE_ROOT


ARCHIVE_MANIFEST_ROOT = (
    Path(__file__).resolve().parents[2] / "artifacts" / "archive_manifest"
)


def _read(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _records(plot_id: str, geometry_hash: str) -> List[HistoricalSceneRecord]:
    path = (
        ARCHIVE_MANIFEST_ROOT
        / str(plot_id)
        / str(geometry_hash)
        / "scene_manifest.jsonl"
    )
    result: List[HistoricalSceneRecord] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    allowed = set(HistoricalSceneRecord.__dataclass_fields__)
    for line in lines:
        try:
            raw = json.loads(line)
            if isinstance(raw, dict):
                result.append(HistoricalSceneRecord(**{
                    key: value for key, value in raw.items()
                    if key in allowed
                }))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return result


class ScheduledArchiveWorldlineService:
    """Run historical RTS/archive validation for due active plots."""

    def __init__(
        self,
        worldline: Optional[PlotWorldlineService] = None,
    ) -> None:
        self.worldline = worldline or PlotWorldlineService()

    def _due_plot_heads(self) -> List[Dict[str, Any]]:
        heads: List[Dict[str, Any]] = []
        if not Path(WORLDLINE_ROOT).exists():
            return heads
        for path in Path(WORLDLINE_ROOT).glob("*/*/*/head.json"):
            head = _read(path)
            tenant_id = str(head.get("tenant_id") or "").strip()
            namespace = str(head.get("namespace") or "").strip()
            if not tenant_id or not namespace:
                continue
            latest = head.get("latest_by_type") or {}
            current_id = latest.get("CURRENT_POSTERIOR_VALIDATED")
            if not current_id:
                continue
            current = self.worldline.load_event(
                str(head.get("plot_id", "")), str(current_id),
                tenant_id, namespace,
            )
            archive_id = latest.get("ARCHIVE_POSTERIOR_VALIDATED")
            archive = (
                self.worldline.load_event(
                    str(head.get("plot_id", "")), str(archive_id),
                    tenant_id, namespace,
                )
                if archive_id else {}
            )
            # A validated archive newer than the current candidate is already
            # reconciled. Rejected/acquisition-plan events remain retryable as
            # real provider manifests arrive.
            if archive and int(archive.get("sequence", 0) or 0) >= int(
                current.get("sequence", 0) or 0
            ):
                continue
            heads.append({
                "head": head,
                "current": current,
            })
        return sorted(
            heads,
            key=lambda item: int(
                (item.get("current") or {}).get("sequence", 0) or 0
            ),
        )

    def run_cycle(self, max_plots: int = 4) -> Dict[str, Any]:
        stats = {
            "status": "completed",
            "due": 0,
            "attempted": 0,
            "validated": 0,
            "rejected": 0,
            "acquisition_required": 0,
            "errors": [],
        }
        due = self._due_plot_heads()
        stats["due"] = len(due)
        for item in due[: max(0, int(max_plots))]:
            head = item["head"]
            current = item["current"]
            plot_id = str(head.get("plot_id", ""))
            geometry_hash = str(current.get("geometry_hash", "") or "")
            crop_payload = self.worldline.latest_payload(
                plot_id,
                "CROP_POSTERIOR",
                str(head.get("tenant_id") or "default_tenant"),
                str(head.get("namespace") or "default"),
            )
            crop_posterior = crop_payload.get("crop_posterior") or {}
            crop_context = {
                "crop": crop_posterior.get("declared_crop_normalized"),
                "crop_group_posterior": crop_posterior.get(
                    "crop_group_posterior", {}
                ),
                "crop_posterior_hash": crop_posterior.get("content_hash"),
            }
            context = {
                "historical_scene_records": _records(
                    plot_id, geometry_hash
                ),
                "crop_context": crop_context,
                "archive_trigger_event_id": current.get("event_id"),
                "tenant_id": str(head.get("tenant_id") or "default_tenant"),
                "worldline_namespace": str(
                    head.get("namespace") or "default"
                ),
            }
            stats["attempted"] += 1
            try:
                result = self.worldline.refresh_archive_from_context(
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    context=context,
                    tenant_id=context["tenant_id"],
                    namespace=context["worldline_namespace"],
                )
                status = str(result.get("status", ""))
                if status == "validated":
                    stats["validated"] += 1
                elif status in {
                    "acquisition_required",
                    "insufficient_archive_evidence",
                }:
                    stats["acquisition_required"] += 1
                else:
                    stats["rejected"] += 1
            except Exception as exc:
                stats["errors"].append({
                    "plot_id": plot_id,
                    "reason": str(exc),
                })
        return stats

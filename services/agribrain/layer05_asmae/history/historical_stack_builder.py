"""
Historical Stack Builder.
Organizes historical stacks of Sentinel scenes chronologically.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from layer0.archive.scene_manifest import HistoricalSceneRecord
from ..geometry.scene_stack_builder import build_scene_stack, SceneStack
from ..schema import ASMAEInput


class HistoricalStackBuilder:
    def __init__(self):
        pass

    def build_stack(
        self,
        plot_id: str,
        geometry_hash: str,
        records: List[HistoricalSceneRecord],
        polygon_geojson: Optional[Dict[str, Any]] = None,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
    ) -> SceneStack:
        """
        Builds a combined multi-sensor chronological scene stack
        from a list of HistoricalSceneRecord objects with dynamic dates
        and plot-native geometry.
        """
        # Filter records by sensor types
        s2_records = [r for r in records if r.source.lower() in ("sentinel2", "s2")]
        s1_records = [r for r in records if r.source.lower() in ("sentinel1", "s1")]

        # Determine dynamic start date
        if not records and (start_date is None or end_date is None):
            raise ValueError(
                "HistoricalStackBuilder requires explicit start/end dates when no scene records are provided; date fabrication for empty evidence is rejected"
            )

        resolved_start = start_date
        if resolved_start is None:
            if records:
                dates = [
                    str(getattr(r, "acquisition_time", "") or "")[:10]
                    for r in records
                    if str(getattr(r, "acquisition_time", "") or "")[:10]
                ]
                if dates:
                    try:
                        resolved_start = date.fromisoformat(min(dates))
                    except (ValueError, TypeError):
                        resolved_start = date(2015, 6, 23)
                else:
                    resolved_start = date(2015, 6, 23)
            else:
                resolved_start = date(2015, 6, 23)
        elif isinstance(resolved_start, str):
            resolved_start = date.fromisoformat(resolved_start[:10])
        elif isinstance(resolved_start, datetime):
            resolved_start = resolved_start.date()

        # Determine dynamic end date
        resolved_end = end_date
        if resolved_end is None:
            if records:
                dates = [
                    str(getattr(r, "acquisition_time", "") or "")[:10]
                    for r in records
                    if str(getattr(r, "acquisition_time", "") or "")[:10]
                ]
                if dates:
                    try:
                        resolved_end = date.fromisoformat(max(dates))
                    except (ValueError, TypeError):
                        resolved_end = datetime.now(timezone.utc).date()
                else:
                    resolved_end = datetime.now(timezone.utc).date()
            else:
                resolved_end = datetime.now(timezone.utc).date()
        elif isinstance(resolved_end, str):
            resolved_end = date.fromisoformat(resolved_end[:10])
        elif isinstance(resolved_end, datetime):
            resolved_end = resolved_end.date()

        # Validate polygon_geojson: must be a valid, non-empty GeoJSON Polygon or MultiPolygon (B59-04)
        if not polygon_geojson or not isinstance(polygon_geojson, dict):
            raise ValueError(
                f"HistoricalStackBuilder requires valid plot-native Polygon/MultiPolygon geometry, got {polygon_geojson}"
            )
        poly_type = str(polygon_geojson.get("type", "")).strip()
        if poly_type not in ("Polygon", "MultiPolygon"):
            raise ValueError(
                f"HistoricalStackBuilder requires GeoJSON type Polygon or MultiPolygon, got '{poly_type}'"
            )
        coords = polygon_geojson.get("coordinates")
        if not coords or not isinstance(coords, (list, tuple)) or len(coords) == 0:
            raise ValueError(
                f"HistoricalStackBuilder rejects empty geometry coordinates: {polygon_geojson}"
            )
        if poly_type == "Polygon":
            ring = coords[0]
            if not isinstance(ring, (list, tuple)) or len(ring) < 4:
                raise ValueError(
                    f"HistoricalStackBuilder Polygon must have at least 4 coordinates in outer ring, got {ring}"
                )
        elif poly_type == "MultiPolygon":
            poly0 = coords[0]
            if not isinstance(poly0, (list, tuple)) or len(poly0) == 0 or len(poly0[0]) < 4:
                raise ValueError(
                    f"HistoricalStackBuilder MultiPolygon must contain valid polygons with at least 4 coordinates, got {poly0}"
                )

        resolved_polygon = polygon_geojson

        # Construct ASMAEInput payload
        inp = ASMAEInput(
            plot_id=plot_id,
            run_id=f"hist_{plot_id}_{geometry_hash}",
            polygon_geojson=resolved_polygon,
            geometry_hash=geometry_hash,
            start_date=resolved_start,
            end_date=resolved_end,
            layer0_source_packages={
                "asmae_sentinel2_real": s2_records,
                "asmae_sentinel1_real": s1_records
            },
            mode="shadow",
            source_policy="historical"
        )

        # Delegate stack construction and quality assessment to the core builder
        return build_scene_stack(inp)

"""
Historical Stack Builder.
Organizes historical stacks of Sentinel scenes chronologically.
"""
from typing import List
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
        records: List[HistoricalSceneRecord]
    ) -> SceneStack:
        """
        Builds a combined multi-sensor chronological scene stack
        from a list of HistoricalSceneRecord objects.
        """
        # Filter records by sensor types
        s2_records = [r for r in records if r.source.lower() in ("sentinel2", "s2")]
        s1_records = [r for r in records if r.source.lower() in ("sentinel1", "s1")]

        from datetime import date
        # Construct ASMAEInput payload
        inp = ASMAEInput(
            plot_id=plot_id,
            run_id=f"hist_{plot_id}_{geometry_hash}",
            polygon_geojson={"type": "Polygon", "coordinates": []},
            geometry_hash=geometry_hash,
            start_date=date(2015, 1, 1), # Covers full archive
            end_date=date(2026, 6, 16),
            layer0_source_packages={
                "asmae_sentinel2_real": s2_records,
                "asmae_sentinel1_real": s1_records
            },
            mode="shadow",
            source_policy="historical"
        )

        # Delegate stack construction and quality assessment to the core builder
        return build_scene_stack(inp)

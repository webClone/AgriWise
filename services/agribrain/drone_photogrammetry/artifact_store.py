"""
Stage K — Artifact Output.

Saves the orthomosaic and associated metadata as artifact references.

V1: In-memory artifact refs with metadata JSON. No actual file I/O.
V2: COG GeoTIFF output, S3/GCS upload, tiled serving.

Design rule: artifact refs are the PRIMARY handoff to drone_rgb.
The inline _benchmark_pixels path is for testing only.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import datetime
import json
import logging

from .schemas import (
    DroneFrameSetInput,
    OrthomosaicOutput,
    PipelineProvenance,
    MosaicStatus,
)
from .mosaic import MosaicResult
from .seam_optimizer import SeamAnalysis
from .georef import GeorefResult
from .bundle_adjustment import BundleAdjustmentResult

logger = logging.getLogger(__name__)


class ArtifactStore:
    """Packages photogrammetry outputs into artifact references.
    
    V1: Generates synthetic artifact URIs and stores metadata in-memory.
    V2: Writes COG GeoTIFF, preview PNG, metadata JSON to storage.
    """
    
    def store(
        self,
        inp: DroneFrameSetInput,
        mosaic: MosaicResult,
        seam: SeamAnalysis,
        georef: GeorefResult,
        ba: BundleAdjustmentResult,
        provenance: PipelineProvenance,
        status: MosaicStatus,
        qa_score: float,
        sigma_inflation: float,
    ) -> OrthomosaicOutput:
        """Package all results into an OrthomosaicOutput.
        
        This is the final stage of the pipeline. The output is what
        drone_rgb Mapping Mode consumes.
        """
        # Generate artifact URIs
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        base = f"ortho://{inp.plot_id}/{inp.mission_id}/{ts}"
        
        output = OrthomosaicOutput(
            mission_id=inp.mission_id,
            plot_id=inp.plot_id,
            
            # Artifact refs (primary handoff)
            orthomosaic_ref=f"{base}/orthomosaic.tif",
            orthomosaic_preview_ref=f"{base}/preview.jpg",
            metadata_ref=f"{base}/metadata.json",
            quality_report_ref=f"{base}/quality_report.json",
            
            # Spatial
            crs=georef.crs,
            bbox=georef.bbox,
            ground_resolution_cm=georef.ground_resolution_cm,
            
            # Quality metrics
            coverage_completeness=georef.coverage_completeness,
            outside_polygon_waste=georef.outside_polygon_waste,
            georegistration_confidence=provenance.georef_confidence,
            seam_artifact_score=seam.seam_artifact_score,
            blur_score=provenance.mean_frame_blur,
            achieved_overlap=georef.achieved_overlap,
            holes_fraction=mosaic.holes_fraction,
            
            # Usability
            status=status,
            usable=(status != MosaicStatus.UNUSABLE),
            qa_score=qa_score,
            sigma_inflation=sigma_inflation,
            
            # Provenance (MANDATORY)
            provenance=provenance,
        )
        
        # Inline benchmark pixels (for testing pipeline only)
        if mosaic.pixels:
            output._benchmark_pixels = mosaic.pixels
        
        # Optional high-value refs
        output.contribution_map_ref = f"{base}/contribution_map.json"
        output.hole_map_ref = f"{base}/hole_map.json"
        output.uncertainty_map_ref = f"{base}/uncertainty_map.json"
        
        # V3: Propagate task usability
        if hasattr(georef, 'task_usability') and georef.task_usability:
            output._task_usability = georef.task_usability
        
        logger.info(
            f"[ArtifactStore] Stored orthomosaic: "
            f"ref={output.orthomosaic_ref}, "
            f"status={status.value}, "
            f"qa={qa_score:.2f}"
        )
        
        return output

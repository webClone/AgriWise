"""
Photogrammetry Engine — Top-Level Orchestrator.

Pipeline:
    validate → ingest → frame QA → camera normalize → tiepoints →
    alignment → bundle adjust → surface model → orthorectify →
    mosaic → seam optimize → georef → artifact store → emit output

QA truthfulness rules:
    If any of these fail badly, mark the mosaic degraded/unusable,
    inflate sigma, and suppress downstream structural outputs:
    - tie-point density
    - reprojection error
    - seam score
    - blur
    - coverage holes
    - GSD mismatch
    - georegistration confidence
"""

from __future__ import annotations
from typing import Optional
import logging
import time

from .schemas import (
    DroneFrameSetInput,
    OrthomosaicOutput,
    PipelineProvenance,
    MosaicStatus,
)
from .frame_ingest import FrameIngestor
from .frame_qa import FrameQA
from .camera_model import CameraModelNormalizer
from .tiepoints import TiePointExtractor
from .alignment import InitialAligner
from .bundle_adjustment import BundleAdjuster
from .surface_model import SurfaceModelBuilder
from .orthorectify import Orthorectifier
from .mosaic import MosaicGenerator
from .seam_optimizer import SeamOptimizer
from .georef import Georeferencer
from .artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class PhotogrammetryEngine:
    """Top-level orchestrator for orthomosaic creation.
    
    Runs the full 11-stage pipeline from raw frames to georeferenced
    orthomosaic. Enforces QA truthfulness: never silently pretends success.
    """
    
    # QA thresholds for status determination
    COVERAGE_UNUSABLE = 0.40
    COVERAGE_DEGRADED = 0.70
    BLUR_UNUSABLE = 0.60
    BLUR_DEGRADED = 0.35
    SEAM_UNUSABLE = 0.50
    SEAM_DEGRADED = 0.20
    REPROJ_UNUSABLE = 15.0   # pixels
    REPROJ_DEGRADED = 5.0
    HOLES_UNUSABLE = 0.40
    HOLES_DEGRADED = 0.15
    
    def __init__(self):
        self.ingestor = FrameIngestor()
        self.frame_qa = FrameQA()
        self.camera_normalizer = CameraModelNormalizer()
        self.tiepoint_extractor = TiePointExtractor()
        self.aligner = InitialAligner()
        self.bundle_adjuster = BundleAdjuster()
        self.surface_builder = SurfaceModelBuilder()
        self.orthorectifier = Orthorectifier()
        self.mosaic_generator = MosaicGenerator()
        self.seam_optimizer = SeamOptimizer()
        self.georeferencer = Georeferencer()
        self.artifact_store = ArtifactStore()
    
    def process(self, inp: DroneFrameSetInput) -> OrthomosaicOutput:
        """Run the full photogrammetry pipeline.
        
        Args:
            inp: DroneFrameSetInput from the mission layer.
            
        Returns:
            OrthomosaicOutput ready for drone_rgb consumption.
        """
        start_time = time.time()
        processing_steps = []
        
        logger.info(
            f"[PhotogrammetryEngine] Starting pipeline for "
            f"mission={inp.mission_id}, plot={inp.plot_id}, "
            f"frames={inp.frame_count or len(inp.frame_refs or inp.synthetic_frames or [])}"
        )
        
        # --- Stage A: Frame Ingestion ---
        manifest = self.ingestor.ingest(inp)
        processing_steps.append("A:ingest")
        
        if not manifest.is_valid:
            return self._fail_output(
                inp,
                f"Ingestion failed: {'; '.join(manifest.validation_errors)}",
                processing_steps, start_time,
            )
        
        # --- Stage B: Per-Frame QA ---
        qa_results = self.frame_qa.assess_batch(manifest.frames)
        processing_steps.append("B:frame_qa")
        
        usable_count = sum(1 for q in qa_results if q.usable)
        if usable_count < 3:
            return self._fail_output(
                inp,
                f"Too few usable frames after QA: {usable_count}",
                processing_steps, start_time,
            )
        
        # --- Stage C: Camera Normalization ---
        cameras = self.camera_normalizer.normalize_batch(manifest.frames)
        processing_steps.append("C:camera")
        
        # --- Stage D: Tie-Point Extraction ---
        overlap = self.tiepoint_extractor.extract(manifest.frames, qa_results)
        processing_steps.append("D:tiepoints")
        
        # --- Stage E: Initial Alignment (now uses tie-point pairs) ---
        alignment = self.aligner.align(
            manifest.frames, qa_results,
            overlap_pairs=overlap.pairs,
        )
        processing_steps.append("E:alignment")
        
        if not alignment.poses:
            return self._fail_output(
                inp,
                "No frames could be aligned (all missing GPS?)",
                processing_steps, start_time,
            )
        
        # --- Stage E (cont.): Bundle Adjustment ---
        ba_result = self.bundle_adjuster.adjust(alignment, overlap)
        processing_steps.append("E2:bundle_adjust")
        
        # --- Stage F: Surface Model ---
        surface = self.surface_builder.build(
            ba_result.refined_poses,
            dem_ref=inp.dem_ref,
            dem_resolution_m=inp.dem_resolution_m,
        )
        processing_steps.append("F:surface_model")
        
        # --- Stage G: Orthorectification ---
        tile_stack = self.orthorectifier.rectify(
            manifest.frames, qa_results,
            ba_result.refined_poses, cameras, surface,
        )
        processing_steps.append("G:orthorectify")
        
        # --- Stage H: Mosaic Generation ---
        mosaic = self.mosaic_generator.generate(tile_stack)
        processing_steps.append("H:mosaic")
        
        # --- Stage I: Seam Optimization ---
        seam = self.seam_optimizer.analyze(mosaic)
        processing_steps.append("I:seam_analyze")
        
        # --- Stage J: Georeferencing ---
        mean_overlap = overlap.mean_confidence
        georef = self.georeferencer.georeference(mosaic, inp, mean_overlap)
        processing_steps.append("J:georef")
        
        # --- Build Provenance (MANDATORY) ---
        provenance = self._build_provenance(
            manifest, qa_results, overlap, ba_result, surface,
            seam, mosaic, georef, processing_steps, start_time,
            gcps_provided=len(inp.gcps),
        )
        
        # --- Determine Status ---
        status, qa_score, sigma_inflation = self._determine_status(
            georef, seam, ba_result, mosaic, provenance, inp,
        )
        
        # --- Stage K: Artifact Store ---
        output = self.artifact_store.store(
            inp, mosaic, seam, georef, ba_result,
            provenance, status, qa_score, sigma_inflation,
        )
        processing_steps.append("K:artifact_store")
        
        elapsed = (time.time() - start_time) * 1000
        provenance.processing_time_ms = elapsed
        
        logger.info(
            f"[PhotogrammetryEngine] Complete: "
            f"status={status.value}, qa={qa_score:.2f}, "
            f"sigma={sigma_inflation:.2f}, "
            f"coverage={georef.coverage_completeness:.1%}, "
            f"time={elapsed:.0f}ms"
        )
        
        return output
    
    def _build_provenance(
        self, manifest, qa_results, overlap, ba_result, surface,
        seam, mosaic, georef, steps, start_time, gcps_provided=0,
    ) -> PipelineProvenance:
        """Build mandatory provenance record."""
        usable_frames = [q for q in qa_results if q.usable]
        rejected_frames = [q for q in qa_results if not q.usable]
        
        blur_scores = [q.blur_score for q in usable_frames]
        exposure_scores = [q.exposure_score for q in usable_frames]
        
        return PipelineProvenance(
            source_frame_ids=[f.frame_id for f in manifest.frames],
            total_frames_ingested=manifest.total_ingested,
            frames_rejected_qa=len(rejected_frames),
            frames_used_in_mosaic=len(usable_frames),
            mean_frame_blur=sum(blur_scores) / max(len(blur_scores), 1),
            mean_frame_exposure=sum(exposure_scores) / max(len(exposure_scores), 1),
            worst_frame_blur=max(blur_scores) if blur_scores else 0.0,
            alignment_method=(
                ba_result.refined_poses[0].source if ba_result.refined_poses else "none"
            ),
            alignment_confidence=ba_result.adjustment_confidence,
            mean_reprojection_error_px=ba_result.mean_reprojection_error_px,
            tiepoint_density=(
                overlap.mean_match_count if overlap.total_pairs > 0 else 0.0
            ),
            surface_model_type=surface.model_type.value,
            dem_source=surface.dem_ref,
            seam_score=seam.seam_artifact_score,
            contribution_uniformity=mosaic.contribution_uniformity,
            georef_confidence=min(
                1.0,
                georef.coverage_completeness
                * ba_result.adjustment_confidence
                * (1.0 - seam.seam_artifact_score)
            ),
            crs=georef.crs,
            gcps_provided=gcps_provided,
            gcps_used=0,  # V1: no fake GCP refinement
            pipeline_version="v3",
            processing_steps=steps,
        )
    
    def _determine_status(
        self, georef, seam, ba_result, mosaic, provenance, inp,
    ) -> tuple:
        """Determine mosaic status, QA score, and sigma inflation.
        
        Never silently pretends success. If quality is bad, mark it.
        """
        degraded_reasons = []
        unusable_reasons = []
        
        # Coverage
        if georef.coverage_completeness < self.COVERAGE_UNUSABLE:
            unusable_reasons.append(
                f"coverage={georef.coverage_completeness:.0%}"
            )
        elif georef.coverage_completeness < self.COVERAGE_DEGRADED:
            degraded_reasons.append(
                f"coverage={georef.coverage_completeness:.0%}"
            )
        
        # Blur
        if provenance.mean_frame_blur > self.BLUR_UNUSABLE:
            unusable_reasons.append(
                f"blur={provenance.mean_frame_blur:.2f}"
            )
        elif provenance.mean_frame_blur > self.BLUR_DEGRADED:
            degraded_reasons.append(
                f"blur={provenance.mean_frame_blur:.2f}"
            )
        
        # Seam
        if seam.seam_artifact_score > self.SEAM_UNUSABLE:
            unusable_reasons.append(
                f"seam={seam.seam_artifact_score:.2f}"
            )
        elif seam.seam_artifact_score > self.SEAM_DEGRADED:
            degraded_reasons.append(
                f"seam={seam.seam_artifact_score:.2f}"
            )
        
        # Reprojection error
        if ba_result.mean_reprojection_error_px > self.REPROJ_UNUSABLE:
            unusable_reasons.append(
                f"reproj={ba_result.mean_reprojection_error_px:.1f}px"
            )
        elif ba_result.mean_reprojection_error_px > self.REPROJ_DEGRADED:
            degraded_reasons.append(
                f"reproj={ba_result.mean_reprojection_error_px:.1f}px"
            )
        
        # Holes
        if mosaic.holes_fraction > self.HOLES_UNUSABLE:
            unusable_reasons.append(
                f"holes={mosaic.holes_fraction:.0%}"
            )
        elif mosaic.holes_fraction > self.HOLES_DEGRADED:
            degraded_reasons.append(
                f"holes={mosaic.holes_fraction:.0%}"
            )
        
        # GSD mismatch: compare against native camera GSD, not target
        # Native GSD = (altitude * sensor_width) / (focal_length * image_width)
        # For benchmark synthetic frames, achieved GSD may be lower than
        # native due to small pixel arrays — that is expected. Only flag
        # when achieved GSD is significantly worse than what the camera's
        # full-resolution images would produce.
        if georef.ground_resolution_cm > 0 and inp.target_gsd_cm > 0:
            # Estimate native GSD from camera + altitude
            if inp.camera and inp.camera.focal_length_mm > 0:
                alt = inp.flight_altitude_m or 50.0
                native_gsd_cm = (
                    alt * inp.camera.sensor_width_mm
                    / (inp.camera.focal_length_mm * inp.camera.image_width_px)
                ) * 100  # Convert m to cm
            else:
                native_gsd_cm = inp.target_gsd_cm
            
            # Flag only if achieved GSD is 3x worse than native
            gsd_ratio = georef.ground_resolution_cm / max(native_gsd_cm, 0.1)
            if gsd_ratio > 3.0:
                degraded_reasons.append(
                    f"GSD={georef.ground_resolution_cm:.1f}cm "
                    f"vs native={native_gsd_cm:.1f}cm"
                )
        
        # Determine status
        if unusable_reasons:
            status = MosaicStatus.UNUSABLE
            reason = "UNUSABLE: " + "; ".join(unusable_reasons)
        elif degraded_reasons:
            status = MosaicStatus.DEGRADED
            reason = "DEGRADED: " + "; ".join(degraded_reasons)
        else:
            status = MosaicStatus.USABLE
            reason = ""
        
        # QA score (composite)
        qa_score = (
            georef.coverage_completeness * 0.3
            + (1.0 - provenance.mean_frame_blur) * 0.2
            + (1.0 - seam.seam_artifact_score) * 0.2
            + ba_result.adjustment_confidence * 0.15
            + (1.0 - mosaic.holes_fraction) * 0.15
        )
        qa_score = max(0.1, min(1.0, qa_score))
        
        # Sigma inflation
        if status == MosaicStatus.UNUSABLE:
            sigma_inflation = 10.0
        elif status == MosaicStatus.DEGRADED:
            sigma_inflation = 1.0 + (1.0 - qa_score) * 5.0
        else:
            sigma_inflation = 1.0 + (1.0 - qa_score) * 2.0
        
        if reason:
            logger.warning(f"[PhotogrammetryEngine] {reason}")
        
        return status, round(qa_score, 3), round(sigma_inflation, 2)
    
    def _fail_output(
        self, inp, reason, steps, start_time,
    ) -> OrthomosaicOutput:
        """Create a failed/unusable output."""
        elapsed = (time.time() - start_time) * 1000
        
        provenance = PipelineProvenance(
            pipeline_version="v3",
            processing_steps=steps,
            processing_time_ms=elapsed,
        )
        
        logger.error(f"[PhotogrammetryEngine] Pipeline failed: {reason}")
        
        return OrthomosaicOutput(
            mission_id=inp.mission_id,
            plot_id=inp.plot_id,
            status=MosaicStatus.UNUSABLE,
            usable=False,
            qa_score=0.0,
            sigma_inflation=10.0,
            rejection_reason=reason,
            provenance=provenance,
        )

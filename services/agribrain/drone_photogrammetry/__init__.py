"""
Drone Photogrammetry — Orthomosaic Creation Subsystem.

Architectural position:
    Mission Orchestrator → **Photogrammetry** → Drone RGB Perception

This subsystem ingests raw drone frames from Mapping Mode missions,
reconstructs a georeferenced orthomosaic, and hands the stitched product
to drone_rgb Mapping Mode for agronomic interpretation.

Command/Revisit Mode frames bypass this subsystem entirely and route
directly to Farmer Photo.

Pipeline stages:
    A. Frame Ingestion        (frame_ingest.py)
    B. Per-Frame QA           (frame_qa.py)
    C. Camera Normalization   (camera_model.py)
    D. Tie-Point Extraction   (tiepoints.py)
    E. Alignment + Bundle Adj (alignment.py, bundle_adjustment.py)
    F. Surface Model          (surface_model.py)
    G. Orthorectification     (orthorectify.py)
    H. Mosaic Generation      (mosaic.py)
    I. Seam Optimization      (seam_optimizer.py)
    J. Georeferencing         (georef.py)
    K. Artifact Output        (artifact_store.py)

V1 status:
    Architecture-complete, testable, integration-ready.
    Reconstruction algorithms use deterministic heuristic placeholders.
    Real SfM libraries (OpenSfM, ODM) can drop into the pipeline later
    without contract changes.
"""

from .engine import PhotogrammetryEngine
from .schemas import DroneFrameSetInput, OrthomosaicOutput

__all__ = ["PhotogrammetryEngine", "DroneFrameSetInput", "OrthomosaicOutput"]

"""
Stage I — Seam Optimization.

Minimizes visible seam artifacts in the blended orthomosaic.

Critical because drone_rgb's row analysis is seam-sensitive:
if seam logic is bad, row continuity and weed maps get corrupted.

V1: Gradient-based seam detection + scoring. Reports seam quality but
    does not modify pixel data (read-only analysis).
V2: Graph-cut seam optimization, exposure-aware blending.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import logging

from .mosaic import MosaicResult

logger = logging.getLogger(__name__)


@dataclass
class SeamAnalysis:
    """Seam quality analysis of the mosaic."""
    seam_artifact_score: float = 0.0   # 0 = clean, 1 = severe
    
    # Per-region analysis
    num_seam_regions: int = 0
    worst_seam_gradient: float = 0.0
    mean_seam_gradient: float = 0.0
    
    # Row sensitivity
    row_discontinuity_risk: float = 0.0  # 0 = low risk, 1 = high risk
    
    # Lighting transitions
    lighting_transition_score: float = 0.0
    
    # Details
    seam_locations: List[Tuple[int, int]] = field(default_factory=list)
    # (y, x) grid coordinates of detected seam cells


class SeamOptimizer:
    """Analyzes and (V2) optimizes seam quality in the mosaic.
    
    V1: Read-only analysis. Detects seam artifacts by looking for
    strong gradients at tile boundaries (where contribution_map
    transitions from one dominant tile to another).
    
    V2: Graph-cut seam placement that avoids cutting through crop rows.
    """
    
    # Gradient threshold for seam detection
    SEAM_GRADIENT_THRESHOLD = 40  # Pixel value difference
    
    def analyze(self, mosaic: MosaicResult) -> SeamAnalysis:
        """Analyze the mosaic for seam artifacts.
        
        Looks for strong unnatural gradients at contribution boundaries.
        These indicate poor blending where tiles meet.
        """
        analysis = SeamAnalysis()
        
        if not mosaic.pixels or not mosaic.pixels.get("green"):
            return analysis
        
        green = mosaic.pixels["green"]
        h = mosaic.height_px
        w = mosaic.width_px
        contrib = mosaic.contribution_map
        
        if h < 3 or w < 3:
            return analysis
        
        # --- 1. Detect contribution boundaries ---
        # A seam exists where adjacent cells have different contribution counts
        # (indicating different tiles were dominant)
        seam_gradients = []
        seam_locs = []
        
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if mosaic.hole_map[y][x]:
                    continue
                
                # Check if this is a contribution boundary
                is_boundary = False
                if contrib[y][x] != contrib[y][x - 1] or contrib[y][x] != contrib[y - 1][x]:
                    is_boundary = True
                
                if is_boundary:
                    # Measure gradient strength at boundary
                    g_val = green[y][x]
                    grad_h = abs(g_val - green[y][x - 1])
                    grad_v = abs(g_val - green[y - 1][x])
                    max_grad = max(grad_h, grad_v)
                    
                    if max_grad > self.SEAM_GRADIENT_THRESHOLD:
                        seam_gradients.append(max_grad)
                        seam_locs.append((y, x))
        
        analysis.num_seam_regions = len(seam_locs)
        analysis.seam_locations = seam_locs[:100]  # Cap for memory
        
        if seam_gradients:
            analysis.worst_seam_gradient = max(seam_gradients)
            analysis.mean_seam_gradient = sum(seam_gradients) / len(seam_gradients)
            
            # Score: proportion of boundary cells with strong gradients
            total_boundary = sum(
                1 for y in range(1, h - 1) for x in range(1, w - 1)
                if not mosaic.hole_map[y][x]
                and (contrib[y][x] != contrib[y][x - 1]
                     or contrib[y][x] != contrib[y - 1][x])
            )
            if total_boundary > 0:
                analysis.seam_artifact_score = min(
                    1.0, len(seam_gradients) / total_boundary
                )
        
        # --- 2. Row discontinuity risk ---
        # Horizontal seams are especially dangerous for row analysis
        horizontal_seams = sum(
            1 for y, x in seam_locs if y > 0 and contrib[y][x] != contrib[y - 1][x]
        )
        if seam_locs:
            analysis.row_discontinuity_risk = min(
                1.0, horizontal_seams / max(len(seam_locs), 1) * 2
            )
        
        # --- 3. Lighting transition score ---
        # Check for systematic brightness shifts across contribution boundaries
        if len(seam_gradients) > 5:
            sorted_grads = sorted(seam_gradients, reverse=True)
            top_5_mean = sum(sorted_grads[:5]) / 5
            analysis.lighting_transition_score = min(
                1.0, top_5_mean / 100.0
            )
        
        logger.info(
            f"[SeamOptimizer] seam_score={analysis.seam_artifact_score:.2f}, "
            f"regions={analysis.num_seam_regions}, "
            f"row_risk={analysis.row_discontinuity_risk:.2f}, "
            f"lighting={analysis.lighting_transition_score:.2f}"
        )
        
        return analysis

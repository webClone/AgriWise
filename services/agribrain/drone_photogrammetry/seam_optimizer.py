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
    
    # V3: Edge and structure awareness
    edge_cut_count: int = 0          # Seams cutting across strong image edges
    structure_cut_risk: float = 0.0  # Risk of cutting structural features (0-1)
    low_confidence_seams: int = 0    # Seams in single-contributor areas


class SeamOptimizer:
    """Analyzes and (V2) optimizes seam quality in the mosaic.
    
    V1: Read-only analysis. Detects seam artifacts by looking for
    strong gradients at tile boundaries (where contribution_map
    transitions from one dominant tile to another).
    
    V2: Graph-cut seam placement that avoids cutting through crop rows.
    """
    
    # Gradient threshold for seam detection
    # V3: Set to 45 (up from 40) for real footage robustness.
    # Combined with sqrt-damped scoring to reduce sensitivity.
    SEAM_GRADIENT_THRESHOLD = 45
    
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
            f"lighting={analysis.lighting_transition_score:.2f}, "
            f"edge_cuts={analysis.edge_cut_count}, "
            f"struct_risk={analysis.structure_cut_risk:.2f}"
        )
        
        # --- V3: Edge-aware seam analysis ---
        self._analyze_edge_cuts(analysis, mosaic, green, contrib, h, w)
        
        return analysis
    
    def _analyze_edge_cuts(
        self,
        analysis: SeamAnalysis,
        mosaic: MosaicResult,
        green: List[List[int]],
        contrib: List[List[int]],
        h: int, w: int,
    ) -> None:
        """V3: Analyze seams for edge-awareness and structure risk."""
        if h < 3 or w < 3:
            return
        
        edge_cuts = 0
        lc_seams = 0
        high_gradient_total = 0
        seam_total = 0
        
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if mosaic.hole_map and mosaic.hole_map[y][x]:
                    continue
                
                c_here = contrib[y][x]
                is_seam = (
                    c_here != contrib[y][x-1]
                    or c_here != contrib[y-1][x]
                )
                if not is_seam:
                    continue
                
                seam_total += 1
                
                # Edge-cut: strong Sobel gradient at seam = structural cut
                gx = abs(green[y][x+1] - green[y][x-1]) if x+1 < w else 0
                gy = abs(green[y+1][x] - green[y-1][x]) if y+1 < h else 0
                gradient = gx + gy
                
                if gradient > 40:
                    edge_cuts += 1
                if gradient > 20:
                    high_gradient_total += 1
                
                # Low-confidence: single-contributor boundary
                if c_here <= 1:
                    lc_seams += 1
        
        analysis.edge_cut_count = edge_cuts
        analysis.low_confidence_seams = lc_seams
        analysis.structure_cut_risk = (
            min(1.0, high_gradient_total / max(seam_total, 1))
            if seam_total > 0 else 0.0
        )
        
        # Edge cuts inform structure_cut_risk but do NOT inflate the
        # main seam_artifact_score — that would double-penalize real
        # footage where natural texture gradients cross tile boundaries.

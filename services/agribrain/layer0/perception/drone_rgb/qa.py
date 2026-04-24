"""
Drone QA Evaluator.

Evaluates orthomosaic quality to ensure safe structural inference.
Applies reliability weighting and sigma inflation for downstream Kalman filters.
"""

from typing import Dict, Any, Tuple
from dataclasses import dataclass
import random

from .schemas import DroneRGBInput
from ....drone_mission.schemas import FlightMode

@dataclass
class DroneQAOutput:
    """Quality and reliability metrics for a drone structural map."""
    is_usable: bool = True
    rejection_reason: str = ""
    
    overall_score: float = 1.0       # 0.0 to 1.0
    sigma_inflation: float = 1.0     # Multiplier for observation uncertainty
    
    # Specific QA dimensions
    achieved_gsd_cm: float = 0.0
    coverage_completeness: float = 1.0 # Fraction of target polygon covered
    seam_artifact_rate: float = 0.0    # Proportion of map affected by bad stitching
    motion_blur_score: float = 0.0     # 0 = sharp, 1 = severely blurred
    shadow_severity: float = 0.0       # 0 = flat lighting, 1 = deep shadows


def evaluate_drone_qa(inp: DroneRGBInput) -> DroneQAOutput:
    """
    Evaluate structural orthomosaic quality.
    Enforces feasibility gating (is_usable).
    """
    qa = DroneQAOutput()
    
    if inp.flight_mode == FlightMode.COMMAND_REVISIT_MODE:
        # QA for command mode is deferred to FarmerPhotoEngine
        return qa
        
    meta = inp.orthomosaic_metadata or {}
    
    # 1. Evaluate Metadata
    qa.achieved_gsd_cm = meta.get("achieved_gsd_cm", 2.0)
    qa.coverage_completeness = meta.get("coverage_completeness", 1.0)
    
    # 2. Image-Aware Pixel Analysis
    if inp.synthetic_ortho_pixels and "green" in inp.synthetic_ortho_pixels:
        green = inp.synthetic_ortho_pixels["green"]
        h = len(green)
        w = len(green[0]) if h > 0 else 0
        
        if h > 2 and w > 2:
            # A. Coverage Holes (Blocks of Zeros)
            zero_count = sum(1 for y in range(h) for x in range(w) if green[y][x] == 0)
            qa.coverage_completeness = 1.0 - (zero_count / (h * w))
            
            # B. Blur Proxy (Laplacian Variance)
            # Calculate laplacian using a simplified 3x3 kernel on a sampled grid to save time
            laplacians = []
            for y in range(1, h - 1, 2):
                for x in range(1, w - 1, 2):
                    if green[y][x] > 0: # Skip holes
                        # L = top + bottom + left + right - 4*center
                        l = (green[y-1][x] + green[y+1][x] + green[y][x-1] + green[y][x+1] - 4 * green[y][x])
                        laplacians.append(l)
            
            if laplacians:
                mean_l = sum(laplacians) / len(laplacians)
                var_l = sum((x - mean_l)**2 for x in laplacians) / len(laplacians)
                # If variance is very low (< 50), it is highly blurred. If > 500, it is sharp.
                qa.motion_blur_score = max(0.0, min(1.0, 1.0 - (var_l / 500.0)))
            
            # C. Seam Artifacts (Linear Discontinuities)
            # Look for strong unnatural gradients along straight vertical/horizontal lines
            # Agricultural rows create gradients of ~60 per pixel. Seams create much higher gradients (>100).
            vertical_seam_score = 0
            for x in range(1, w - 1):
                col_grad = sum(abs(green[y][x] - green[y][x-1]) for y in range(h) if green[y][x] > 0 and green[y][x-1] > 0)
                if col_grad > h * 100: # Unnaturally high average gradient for a whole column
                    vertical_seam_score += 1
                    
            horizontal_seam_score = 0
            for y in range(1, h - 1):
                row_grad = sum(abs(green[y][x] - green[y-1][x]) for x in range(w) if green[y][x] > 0 and green[y-1][x] > 0)
                if row_grad > w * 100: 
                    horizontal_seam_score += 1
                    
            qa.seam_artifact_rate = min(1.0, (vertical_seam_score / w) + (horizontal_seam_score / h)) * 10.0 # scale up for sensitivity
    else:
        qa.seam_artifact_rate = 0.0
        qa.motion_blur_score = 0.0
        qa.shadow_severity = 0.0
        
    # 2. Score Calculation & Sigma Inflation
    # Compute score BEFORE gating so rejected cases still report an honest score.
    qa.overall_score = 1.0 - (qa.seam_artifact_rate * 1.5) - qa.motion_blur_score - (1.0 - qa.coverage_completeness)
    qa.overall_score = max(0.1, min(1.0, qa.overall_score))
    qa.sigma_inflation = 1.0 + (1.0 - qa.overall_score) * 4.0
        
    # 3. Hard Feasibility Gates
    if qa.coverage_completeness < 0.50:
        qa.is_usable = False
        qa.rejection_reason = f"Coverage too low ({qa.coverage_completeness:.0%})"
        return qa
        
    if qa.motion_blur_score > 0.4:
        qa.is_usable = False
        qa.rejection_reason = "Severe motion blur precludes structural mapping"
        return qa
        
    if qa.seam_artifact_rate > 0.3:
        qa.is_usable = False
        qa.rejection_reason = "Excessive stitching artifacts"
        return qa
    
    return qa

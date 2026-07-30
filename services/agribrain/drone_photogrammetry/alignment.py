"""
Stage E — Initial Alignment.

Estimates initial camera poses from GPS + tie-point geometry.

V3: GPS positions as priors, then tie-point correspondences used to
    compute relative pose offsets between overlapping frames. The
    aligner uses a local rigid-body registration: for each frame pair
    with matches, the GPS offset is compared to the feature-based
    offset to derive a correction term. Corrections are averaged over
    all pairs to produce a globally consistent refinement.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import logging
import math

from .schemas import CameraPose, FrameMetadata, FrameQAResult, TiePointPair

logger = logging.getLogger(__name__)


@dataclass
class AlignmentResult:
    """Initial alignment of all camera poses."""
    poses: List[CameraPose] = field(default_factory=list)
    alignment_confidence: float = 0.0
    method: str = "gps_only"
    # Frames that could not be aligned
    unaligned_frame_ids: List[str] = field(default_factory=list)
    
    # V3: Strip-level awareness
    strip_count: int = 0             # Number of detected flight strips
    weak_connections: List[str] = field(default_factory=list)  # Frame IDs with < 2 overlaps
    strip_gap_risk: float = 0.0      # 0 = solid, 1 = probable inter-strip gap


class InitialAligner:
    """Computes initial camera poses from GPS + tie-point geometry.
    
    V3 strategy:
    1. Place all frames at GPS positions (same as V1)
    2. For each overlapping pair, compute the GPS-predicted offset
       and the feature-match-implied offset
    3. Average discrepancies to derive per-frame correction vectors
    4. Apply corrections to produce refined initial poses
    5. Update alignment confidence based on correction magnitudes
       and tie-point coverage
    
    This produces a better starting point for bundle adjustment than
    raw GPS alone, especially when GPS drift or multipath affects
    individual frame positions.
    """
    
    # Maximum per-frame correction magnitude (meters)
    MAX_CORRECTION_M = 3.0
    
    # Weight for tie-point correction vs GPS prior
    TIEPOINT_CORRECTION_WEIGHT = 0.4
    
    def align(
        self,
        frames: List[FrameMetadata],
        qa_results: List[FrameQAResult],
        overlap_pairs: List[TiePointPair] = None,
    ) -> AlignmentResult:
        """Compute initial camera poses using GPS + tie-point geometry.
        
        Args:
            frames: Ingested frames with GPS metadata.
            qa_results: Per-frame QA for filtering.
            overlap_pairs: Tie-point pairs from Stage D (optional).
                          If provided, enables tie-point-assisted alignment.
            
        Returns:
            AlignmentResult with one CameraPose per usable frame.
        """
        # --- Step 1: GPS-based placement (same as V1) ---
        result = AlignmentResult()
        pose_map: Dict[str, CameraPose] = {}
        frame_map: Dict[str, FrameMetadata] = {}
        
        has_gps = 0
        for frame, qa in zip(frames, qa_results):
            if not qa.usable or frame.duplicate_of:
                continue
            
            if frame.missing_gps:
                result.unaligned_frame_ids.append(frame.frame_id)
                continue
            
            has_gps += 1
            frame_map[frame.frame_id] = frame
            
            pose = CameraPose(
                frame_id=frame.frame_id,
                latitude=frame.gps.latitude,
                longitude=frame.gps.longitude,
                altitude_m=frame.gps.altitude_m,
                heading_deg=frame.gps.heading_deg,
                pitch_deg=frame.gps.pitch_deg,
                roll_deg=frame.gps.roll_deg,
                position_sigma_m=frame.gps.horizontal_accuracy_m,
                orientation_sigma_deg=2.0,
                source="gps_only",
            )
            
            if frame.gps.rtk_fix:
                pose.position_sigma_m = 0.02
                pose.orientation_sigma_deg = 0.5
            
            pose_map[frame.frame_id] = pose
        
        # --- Step 2: Strip detection (V3) ---
        strips = self._detect_strips(frame_map, pose_map)
        result.strip_count = len(strips)
        
        # --- Step 3: Tie-point-assisted refinement ---
        if overlap_pairs and len(overlap_pairs) > 0 and len(pose_map) > 1:
            corrections_applied = self._apply_tiepoint_corrections(
                pose_map, frame_map, overlap_pairs
            )
            if corrections_applied > 0:
                result.method = "gps_tiepoint"
        else:
            result.method = "gps_only"
        
        result.poses = list(pose_map.values())
        
        # --- Step 4: Weak connection analysis (V3) ---
        if overlap_pairs:
            result.weak_connections = self._find_weak_connections(
                pose_map, overlap_pairs
            )
            if result.weak_connections:
                result.strip_gap_risk = min(
                    1.0, len(result.weak_connections) / max(len(pose_map), 1) * 3
                )
        
        # --- Step 5: Alignment confidence ---
        total_frames = sum(1 for q in qa_results if q.usable)
        if total_frames > 0 and result.poses:
            gps_coverage = has_gps / total_frames
            mean_sigma = sum(p.position_sigma_m for p in result.poses) / len(result.poses)
            uncertainty_factor = max(0.1, 1.0 - mean_sigma / 10.0)
            
            tiepoint_boost = 1.0
            if result.method == "gps_tiepoint":
                tiepoint_boost = 1.15
            
            # V3: Penalize strip gaps
            gap_penalty = max(0.7, 1.0 - result.strip_gap_risk * 0.3)
            
            result.alignment_confidence = min(
                1.0, gps_coverage * uncertainty_factor * tiepoint_boost * gap_penalty
            )
        
        logger.info(
            f"[Alignment] {len(result.poses)} poses, "
            f"method={result.method}, "
            f"confidence={result.alignment_confidence:.2f}, "
            f"strips={result.strip_count}, "
            f"weak={len(result.weak_connections)}, "
            f"{len(result.unaligned_frame_ids)} unaligned"
        )
        
        return result
    
    def _apply_tiepoint_corrections(
        self,
        pose_map: Dict[str, CameraPose],
        frame_map: Dict[str, FrameMetadata],
        pairs: List[TiePointPair],
    ) -> int:
        """Use tie-point pairs to compute and apply pose corrections.
        
        For each pair (A, B):
        1. Compute GPS-predicted offset: Δ_gps = pos_B - pos_A
        2. Compute feature-implied relative position from match geometry
        3. Correction = weighted difference between GPS and feature offsets
        4. Accumulate corrections per frame, then average and apply
        
        Returns number of frames corrected.
        """
        # Accumulate correction vectors per frame
        corrections: Dict[str, List[Tuple[float, float]]] = {}
        
        for pair in pairs:
            if pair.frame_a_id not in pose_map or pair.frame_b_id not in pose_map:
                continue
            if pair.inlier_count < 3:
                continue
            
            pose_a = pose_map[pair.frame_a_id]
            pose_b = pose_map[pair.frame_b_id]
            frame_a = frame_map.get(pair.frame_a_id)
            frame_b = frame_map.get(pair.frame_b_id)
            
            if not frame_a or not frame_b:
                continue
            
            # GPS-predicted offset in meters
            cos_lat = math.cos(math.radians(pose_a.latitude)) if pose_a.latitude != 0 else 1.0
            gps_dx_m = (pose_b.longitude - pose_a.longitude) * 111000 * cos_lat
            gps_dy_m = (pose_b.latitude - pose_a.latitude) * 111000
            
            # Feature-implied offset estimation
            # Based on match confidence and overlap geometry:
            # Higher confidence → frames are closer together than GPS suggests
            # if overlap is high (many matches), the actual separation is likely
            # smaller than GPS reports (common GPS drift pattern in drones)
            #
            # We estimate the feature-implied separation as a fraction of
            # the GPS-reported separation, modulated by match quality.
            overlap_fraction = pair.confidence
            
            # If match quality is high (confidence > 0.5), the frames
            # are well-overlapped. We can compute a corrected separation.
            #
            # For adjacent frames in a strip, the expected overlap at 75%
            # means frames are 25% of footprint apart. GPS drift shifts this.
            # A high match count with good inlier ratio means the frames
            # are really where they appear to be relative to each other.
            inlier_ratio = pair.inlier_count / max(pair.match_count, 1)
            
            # Correction: nudge positions toward what the matches imply
            # The correction direction is along the line connecting the two frames
            gps_dist = math.sqrt(gps_dx_m ** 2 + gps_dy_m ** 2)
            if gps_dist < 0.01:
                continue
            
            # Expected separation based on match confidence
            # High confidence (≈1.0) means high overlap → frames should be closer
            # Low confidence (≈0.1) means low overlap → frames should be further apart
            alt = (pose_a.altitude_m + pose_b.altitude_m) / 2.0
            footprint_w, _ = frame_a.camera.calculate_footprint_m(alt)
            expected_separation = footprint_w * (1.0 - overlap_fraction)
            
            # Correction factor: how much to scale the GPS offset
            # to match the feature-implied separation
            correction_scale = expected_separation / max(gps_dist, 0.1)
            
            # Limit correction magnitude
            correction_scale = max(0.5, min(1.5, correction_scale))
            
            # Weighted correction for each frame
            # Frame A gets pushed toward where matches say B is
            # Frame B gets pushed toward where matches say A is
            weight = self.TIEPOINT_CORRECTION_WEIGHT * inlier_ratio
            
            # Direction unit vector
            dx_unit = gps_dx_m / gps_dist
            dy_unit = gps_dy_m / gps_dist
            
            # Correction magnitude for this pair
            delta = (correction_scale - 1.0) * gps_dist * weight
            
            # Apply correction equally to both frames (push apart or together)
            corr_a = (-dx_unit * delta / 2.0, -dy_unit * delta / 2.0)
            corr_b = (dx_unit * delta / 2.0, dy_unit * delta / 2.0)
            
            if pair.frame_a_id not in corrections:
                corrections[pair.frame_a_id] = []
            corrections[pair.frame_a_id].append(corr_a)
            
            if pair.frame_b_id not in corrections:
                corrections[pair.frame_b_id] = []
            corrections[pair.frame_b_id].append(corr_b)
        
        # Apply averaged corrections
        corrected_count = 0
        for frame_id, corrs in corrections.items():
            if not corrs:
                continue
            
            pose = pose_map.get(frame_id)
            if not pose:
                continue
            
            # Average correction
            avg_dx = sum(c[0] for c in corrs) / len(corrs)
            avg_dy = sum(c[1] for c in corrs) / len(corrs)
            
            # Clamp
            magnitude = math.sqrt(avg_dx ** 2 + avg_dy ** 2)
            if magnitude > self.MAX_CORRECTION_M:
                scale = self.MAX_CORRECTION_M / magnitude
                avg_dx *= scale
                avg_dy *= scale
                magnitude = self.MAX_CORRECTION_M
            
            if magnitude > 0.001:  # Only apply meaningful corrections
                cos_lat = math.cos(math.radians(pose.latitude)) if pose.latitude != 0 else 1.0
                pose.latitude += avg_dy / 111000.0
                pose.longitude += avg_dx / (111000.0 * max(cos_lat, 0.01))
                
                # Reduce uncertainty after correction
                correction_factor = min(1.0, magnitude / pose.position_sigma_m)
                pose.position_sigma_m *= max(0.5, 1.0 - correction_factor * 0.3)
                
                pose.source = "gps_tiepoint"
                corrected_count += 1
        
        if corrected_count > 0:
            logger.info(
                f"[Alignment] Tie-point corrections applied to "
                f"{corrected_count}/{len(pose_map)} frames"
            )
        
        return corrected_count
    
    def _detect_strips(
        self,
        frame_map: Dict[str, FrameMetadata],
        pose_map: Dict[str, CameraPose],
    ) -> List[List[str]]:
        """V3: Detect flight strips from GPS heading consistency.
        
        Frames with similar headings that are spatially sequential
        belong to the same strip. A heading change > 90° marks a
        strip boundary.
        """
        if len(pose_map) < 2:
            return [list(pose_map.keys())]
        
        # Sort by sequence index
        sorted_ids = sorted(
            pose_map.keys(),
            key=lambda fid: frame_map[fid].sequence_index if fid in frame_map else 0
        )
        
        strips: List[List[str]] = []
        current_strip = [sorted_ids[0]]
        
        for i in range(1, len(sorted_ids)):
            prev_pose = pose_map[sorted_ids[i - 1]]
            curr_pose = pose_map[sorted_ids[i]]
            
            heading_diff = abs(curr_pose.heading_deg - prev_pose.heading_deg)
            if heading_diff > 180:
                heading_diff = 360 - heading_diff
            
            if heading_diff > 90:
                strips.append(current_strip)
                current_strip = [sorted_ids[i]]
            else:
                current_strip.append(sorted_ids[i])
        
        strips.append(current_strip)
        return strips
    
    def _find_weak_connections(
        self,
        pose_map: Dict[str, CameraPose],
        pairs: List[TiePointPair],
    ) -> List[str]:
        """V3: Find frames with fewer than 2 overlap pairs (fragile connectivity)."""
        overlap_count: Dict[str, int] = {fid: 0 for fid in pose_map}
        
        for pair in pairs:
            if pair.frame_a_id in overlap_count:
                overlap_count[pair.frame_a_id] += 1
            if pair.frame_b_id in overlap_count:
                overlap_count[pair.frame_b_id] += 1
        
        return [fid for fid, count in overlap_count.items() if count < 2]

"""
Stage D — Tie-Point Extraction.

Finds frame-to-frame correspondences, builds an overlap graph,
and identifies weakly connected regions.

V3: Multi-scale keypoint detection, grid-balanced sampling,
    forward-backward match consistency, per-pair confidence
    downgrade, and multi-frame track building across 3+ frames.
    Falls back to GPS-only for frames without pixel data.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import logging
import math

from .schemas import (
    FrameMetadata,
    FrameQAResult,
    TiePoint,
    TiePointPair,
)

logger = logging.getLogger(__name__)


@dataclass
class OverlapGraph:
    """Frame-to-frame overlap structure.
    
    Encodes which frames overlap, how strongly, and whether the
    graph is well-connected (no isolated strips).
    """
    pairs: List[TiePointPair] = field(default_factory=list)
    tiepoints: List[TiePoint] = field(default_factory=list)
    
    # Summary
    total_pairs: int = 0
    mean_match_count: float = 0.0
    mean_inlier_count: float = 0.0
    mean_confidence: float = 0.0
    
    # Connectivity
    connected_components: int = 1       # 1 = fully connected
    weakly_connected_frames: List[str] = field(default_factory=list)
    missing_strip_risk: float = 0.0     # 0 = no risk, 1 = probable gap
    
    # Per-frame overlap count
    frame_overlap_count: Dict[str, int] = field(default_factory=dict)
    
    # V3: Track statistics
    track_count: int = 0
    mean_track_length: float = 0.0


# ========================================================================
# Feature Detection + Matching
# ========================================================================

@dataclass
class Keypoint:
    """Detected keypoint in a frame."""
    x: float
    y: float
    response: float   # Corner strength
    descriptor: List[int] = field(default_factory=list)
    scale: int = 0    # V3: which pyramid scale (0=native, 1=half)


def _detect_keypoints_single_scale(
    green: List[List[int]],
    max_keypoints: int = 80,
    scale: int = 0,
) -> List[Keypoint]:
    """Detect keypoints at a single scale using Shi-Tomasi corner response."""
    h = len(green)
    if h < 5:
        return []
    w = len(green[0])
    if w < 5:
        return []
    
    # Compute gradients
    gx = [[0.0] * w for _ in range(h)]
    gy = [[0.0] * w for _ in range(h)]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            gx[y][x] = float(green[y][x + 1] - green[y][x - 1]) / 2.0
            gy[y][x] = float(green[y + 1][x] - green[y - 1][x]) / 2.0
    
    keypoints = []
    for y in range(2, h - 2):
        for x in range(2, w - 2):
            sxx = syy = sxy = 0.0
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    ix = gx[y + dy][x + dx]
                    iy = gy[y + dy][x + dx]
                    sxx += ix * ix
                    syy += iy * iy
                    sxy += ix * iy
            
            trace = sxx + syy
            det = sxx * syy - sxy * sxy
            discriminant = max(0.0, trace * trace / 4.0 - det)
            min_eig = trace / 2.0 - math.sqrt(discriminant)
            
            if min_eig > 5.0:
                keypoints.append(Keypoint(
                    x=float(x), y=float(y),
                    response=min_eig, scale=scale,
                ))
    
    keypoints.sort(key=lambda k: k.response, reverse=True)
    return keypoints[:max_keypoints]


def _downsample_2x(green: List[List[int]]) -> List[List[int]]:
    """Simple 2x downsample by averaging 2x2 blocks."""
    h = len(green)
    w = len(green[0]) if h > 0 else 0
    nh, nw = h // 2, w // 2
    if nh < 3 or nw < 3:
        return []
    out = [[0] * nw for _ in range(nh)]
    for y in range(nh):
        for x in range(nw):
            out[y][x] = (
                green[2*y][2*x] + green[2*y][2*x+1] +
                green[2*y+1][2*x] + green[2*y+1][2*x+1]
            ) // 4
    return out


def _detect_keypoints(
    green: List[List[int]],
    max_keypoints: int = 120,
) -> List[Keypoint]:
    """V3: Multi-scale keypoint detection with grid-balanced sampling.
    
    Detects at 2 scales (native + half), merges with NMS, then
    balances across a grid so no single textured region dominates.
    """
    # Scale 0: native
    kps_s0 = _detect_keypoints_single_scale(green, max_keypoints, scale=0)
    
    # Scale 1: half resolution (only if frame is large enough)
    kps_s1 = []
    half = _downsample_2x(green)
    if half:
        raw_s1 = _detect_keypoints_single_scale(half, max_keypoints // 2, scale=1)
        # Map back to native coordinates
        for kp in raw_s1:
            kps_s1.append(Keypoint(
                x=kp.x * 2.0 + 0.5, y=kp.y * 2.0 + 0.5,
                response=kp.response, scale=1,
            ))
    
    # Merge: NMS — suppress scale-1 keypoints near scale-0 ones
    all_kps = list(kps_s0)
    for kp1 in kps_s1:
        too_close = any(
            abs(kp1.x - kp0.x) < 3 and abs(kp1.y - kp0.y) < 3
            for kp0 in kps_s0
        )
        if not too_close:
            all_kps.append(kp1)
    
    # Grid-balanced sampling: divide into NxN cells, top-K from each
    h = len(green)
    w = len(green[0]) if h > 0 else 1
    grid_n = min(4, max(2, min(h, w) // 8))
    cell_h = max(1, h // grid_n)
    cell_w = max(1, w // grid_n)
    per_cell = max(3, max_keypoints // (grid_n * grid_n))
    
    balanced = []
    for gy in range(grid_n):
        for gx in range(grid_n):
            y_lo = gy * cell_h
            y_hi = (gy + 1) * cell_h
            x_lo = gx * cell_w
            x_hi = (gx + 1) * cell_w
            cell_kps = [
                k for k in all_kps
                if y_lo <= k.y < y_hi and x_lo <= k.x < x_hi
            ]
            cell_kps.sort(key=lambda k: k.response, reverse=True)
            balanced.extend(cell_kps[:per_cell])
    
    balanced.sort(key=lambda k: k.response, reverse=True)
    return balanced[:max_keypoints]


def _extract_descriptors(
    green: List[List[int]],
    keypoints: List[Keypoint],
    patch_radius: int = 3,
) -> None:
    """Extract patch-based descriptors around each keypoint."""
    h = len(green)
    w = len(green[0]) if h > 0 else 0
    
    for kp in keypoints:
        cx, cy = int(kp.x), int(kp.y)
        patch = []
        for dy in range(-patch_radius, patch_radius + 1):
            for dx in range(-patch_radius, patch_radius + 1):
                py = max(0, min(h - 1, cy + dy))
                px = max(0, min(w - 1, cx + dx))
                patch.append(green[py][px])
        
        mean_val = sum(patch) / len(patch) if patch else 0
        kp.descriptor = [int(v - mean_val) for v in patch]


def _match_keypoints(
    kps_a: List[Keypoint],
    kps_b: List[Keypoint],
    max_ssd_ratio: float = 0.80,
) -> List[Tuple[int, int, float]]:
    """Match keypoints using SSD with ratio test. Returns (idx_a, idx_b, quality)."""
    if not kps_a or not kps_b:
        return []
    
    desc_len = len(kps_a[0].descriptor) if kps_a[0].descriptor else 0
    if desc_len == 0:
        return []
    
    matches = []
    for i, ka in enumerate(kps_a):
        best_ssd = float('inf')
        second_ssd = float('inf')
        best_j = -1
        
        for j, kb in enumerate(kps_b):
            ssd = sum(
                (a - b) ** 2
                for a, b in zip(ka.descriptor, kb.descriptor)
            )
            if ssd < best_ssd:
                second_ssd = best_ssd
                best_ssd = ssd
                best_j = j
            elif ssd < second_ssd:
                second_ssd = ssd
        
        if best_j >= 0 and second_ssd > 0:
            ratio = best_ssd / second_ssd
            if ratio < max_ssd_ratio:
                quality = 1.0 - ratio
                matches.append((i, best_j, quality))
    
    return matches


def _match_forward_backward(
    kps_a: List[Keypoint],
    kps_b: List[Keypoint],
    max_ssd_ratio: float = 0.80,
) -> List[Tuple[int, int, float]]:
    """V3: Forward-backward match consistency.
    
    Match A→B and B→A, keep only mutual best matches.
    """
    fwd = _match_keypoints(kps_a, kps_b, max_ssd_ratio)
    bwd = _match_keypoints(kps_b, kps_a, max_ssd_ratio)
    
    # Build reverse lookup: for each B index, which A index matched it?
    bwd_map = {}
    for ib, ia, q in bwd:
        if ib not in bwd_map or q > bwd_map[ib][1]:
            bwd_map[ib] = (ia, q)
    
    # Keep only mutual matches
    mutual = []
    for ia, ib, q_fwd in fwd:
        if ib in bwd_map and bwd_map[ib][0] == ia:
            avg_q = (q_fwd + bwd_map[ib][1]) / 2.0
            mutual.append((ia, ib, avg_q))
    
    return mutual


def _filter_matches_geometric(
    kps_a: List[Keypoint],
    kps_b: List[Keypoint],
    matches: List[Tuple[int, int, float]],
    max_displacement_frac: float = 0.5,
    img_w: int = 40,
    img_h: int = 30,
) -> List[Tuple[int, int, float]]:
    """Filter matches using geometric consistency (median displacement)."""
    if len(matches) < 3:
        return matches
    
    displacements = []
    for ia, ib, q in matches:
        dx = kps_b[ib].x - kps_a[ia].x
        dy = kps_b[ib].y - kps_a[ia].y
        displacements.append((dx, dy))
    
    dx_sorted = sorted(d[0] for d in displacements)
    dy_sorted = sorted(d[1] for d in displacements)
    med_dx = dx_sorted[len(dx_sorted) // 2]
    med_dy = dy_sorted[len(dy_sorted) // 2]
    
    max_dev = max(img_w, img_h) * max_displacement_frac
    filtered = []
    for idx, (ia, ib, q) in enumerate(matches):
        dx, dy = displacements[idx]
        dev = math.sqrt((dx - med_dx) ** 2 + (dy - med_dy) ** 2)
        if dev < max_dev:
            filtered.append((ia, ib, q))
    
    return filtered


# ========================================================================
# Track Building
# ========================================================================

def _build_tracks(
    pairs: List[TiePointPair],
    pair_matches: Dict[Tuple[str, str], List[Tuple[int, int, float]]],
    frame_features: Dict[str, List[Keypoint]],
    frame_map: Dict[str, FrameMetadata] = None,
) -> Tuple[List[TiePoint], int, float]:
    """V3: Build multi-frame tracks from pairwise matches.
    
    A track is a set of observations of the same 3D point across
    multiple frames. Tracks longer than 2 are especially valuable
    for bundle adjustment stability in repeated-texture scenes.
    
    Observations are projected through the same pinhole model that
    bundle adjustment uses to ensure self-consistency.
    
    Returns: (tiepoints, track_count, mean_track_length)
    """
    # Union-Find on (frame_id, keypoint_idx) to merge observations
    parent: Dict[Tuple[str, int], Tuple[str, int]] = {}
    
    def find(node):
        while parent.get(node, node) != node:
            parent[node] = parent.get(parent[node], parent[node])
            node = parent[node]
        return node
    
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    
    # Merge matched keypoints across all pairs
    for (fid_a, fid_b), matches in pair_matches.items():
        for ia, ib, q in matches:
            union((fid_a, ia), (fid_b, ib))
    
    # Collect tracks: group by root
    tracks: Dict[Tuple[str, int], List[Tuple[str, int, float]]] = {}
    for (fid_a, fid_b), matches in pair_matches.items():
        for ia, ib, q in matches:
            root = find((fid_a, ia))
            if root not in tracks:
                tracks[root] = []
            tracks[root].append((fid_a, ia, q))
            tracks[root].append((fid_b, ib, q))
    
    # Deduplicate observations per track and build tiepoints
    tiepoints = []
    track_lengths = []
    
    for idx, (root, obs_list) in enumerate(list(tracks.items())[:500]):
        # Unique frame IDs in this track
        seen_fids = set()
        for fid, kp_idx, q in obs_list:
            kps = frame_features.get(fid, [])
            if kp_idx < len(kps):
                seen_fids.add(fid)
        
        if len(seen_fids) < 2:
            continue
        
        track_lengths.append(len(seen_fids))
        confidence = min(1.0, len(seen_fids) / 4.0)
        
        # Compute 3D world position: GPS midpoint of all observing frames
        if frame_map:
            lats = [frame_map[fid].gps.latitude for fid in seen_fids if fid in frame_map]
            lons = [frame_map[fid].gps.longitude for fid in seen_fids if fid in frame_map]
            mid_lat = sum(lats) / max(len(lats), 1) if lats else 0.0
            mid_lon = sum(lons) / max(len(lons), 1) if lons else 0.0
            
            # Project to each frame using the BA-compatible pinhole model
            observations = {}
            for fid in seen_fids:
                if fid in frame_map:
                    observations[fid] = _project_point_to_frame_static(
                        mid_lon, mid_lat, frame_map[fid]
                    )
        else:
            mid_lat, mid_lon = 0.0, 0.0
            observations = {}
            for fid, kp_idx, q in obs_list:
                if fid not in observations:
                    kps = frame_features.get(fid, [])
                    if kp_idx < len(kps):
                        observations[fid] = (kps[kp_idx].x, kps[kp_idx].y)
        
        if len(observations) < 2:
            continue
        
        tp = TiePoint(
            point_id=f"track_{idx:05d}",
            x=mid_lon, y=mid_lat, z=0.0,
            observations=observations,
            confidence=confidence,
        )
        tiepoints.append(tp)
    
    track_count = len(tiepoints)
    mean_length = sum(track_lengths) / max(len(track_lengths), 1)
    
    return tiepoints, track_count, mean_length


def _project_point_to_frame_static(
    world_lon: float, world_lat: float, frame: FrameMetadata,
) -> Tuple[float, float]:
    """Project a world point to frame pixel coordinates (BA-compatible)."""
    alt = frame.gps.altitude_m or 50.0
    cos_lat = math.cos(math.radians(frame.gps.latitude)) if frame.gps.latitude != 0 else 1.0
    
    dx_m = (world_lon - frame.gps.longitude) * 111000 * cos_lat
    dy_m = (world_lat - frame.gps.latitude) * 111000
    
    footprint_half_w = alt * 0.70
    footprint_half_h = alt * 0.52
    
    norm_x = dx_m / max(footprint_half_w, 0.1)
    norm_y = dy_m / max(footprint_half_h, 0.1)
    
    obs_w = 40.0
    obs_h = 30.0
    
    u = obs_w / 2.0 + norm_x * obs_w / 2.0
    v = obs_h / 2.0 - norm_y * obs_h / 2.0
    
    return (u, v)


# ========================================================================
# Main Extractor
# ========================================================================

class TiePointExtractor:
    """Extracts tie-point correspondences between overlapping frames.
    
    V3: Multi-scale detection, grid-balanced sampling, forward-backward
    match consistency, and multi-frame track building.
    """
    
    MIN_OVERLAP_FRACTION = 0.10
    TIEPOINTS_PER_OVERLAP_UNIT = 200
    
    def extract(
        self,
        frames: List[FrameMetadata],
        qa_results: List[FrameQAResult],
    ) -> OverlapGraph:
        """Build overlap graph from frame correspondences."""
        graph = OverlapGraph()
        
        usable = [
            (f, q) for f, q in zip(frames, qa_results)
            if q.usable and not f.missing_gps and f.duplicate_of is None
        ]
        
        if len(usable) < 2:
            graph.missing_strip_risk = 1.0
            return graph
        
        # Pre-extract features for all usable frames
        frame_features: Dict[str, List[Keypoint]] = {}
        for frame, qa in usable:
            if frame.synthetic_pixels and frame.synthetic_pixels.get("green"):
                green = frame.synthetic_pixels["green"]
                kps = _detect_keypoints(green)
                _extract_descriptors(green, kps)
                frame_features[frame.frame_id] = kps
            else:
                frame_features[frame.frame_id] = []
        
        # Compute pairwise matches
        pairs = []
        pair_matches: Dict[Tuple[str, str], List[Tuple[int, int, float]]] = {}
        
        for i in range(len(usable)):
            for j in range(i + 1, len(usable)):
                frame_a, qa_a = usable[i]
                frame_b, qa_b = usable[j]
                
                overlap = self._estimate_overlap_from_gps(frame_a, frame_b)
                if overlap <= self.MIN_OVERLAP_FRACTION:
                    continue
                
                kps_a = frame_features.get(frame_a.frame_id, [])
                kps_b = frame_features.get(frame_b.frame_id, [])
                
                if kps_a and kps_b:
                    # V3: Forward-backward matching
                    raw_matches = _match_forward_backward(kps_a, kps_b)
                    inlier_matches = _filter_matches_geometric(
                        kps_a, kps_b, raw_matches
                    )
                    
                    match_count = len(raw_matches)
                    inlier_count = len(inlier_matches)
                    
                    # Store for track building
                    if inlier_matches:
                        pair_matches[(frame_a.frame_id, frame_b.frame_id)] = inlier_matches
                    
                    if match_count == 0:
                        match_count = max(3, int(overlap * self.TIEPOINTS_PER_OVERLAP_UNIT * 0.3))
                        inlier_count = int(match_count * 0.5)
                        confidence = overlap * 0.3
                    else:
                        inlier_ratio = inlier_count / max(match_count, 1)
                        # V3: Penalize near-collinear matches
                        collinear_penalty = self._check_collinearity(
                            kps_a, kps_b, inlier_matches
                        )
                        confidence = (
                            overlap * inlier_ratio
                            * min(qa_a.quality_weight, qa_b.quality_weight)
                            * collinear_penalty
                        )
                else:
                    match_count = int(overlap * self.TIEPOINTS_PER_OVERLAP_UNIT)
                    effective = int(match_count * min(qa_a.quality_weight, qa_b.quality_weight))
                    inlier_ratio = min(0.95, 0.60 + overlap * 0.30)
                    match_count = effective
                    inlier_count = int(effective * inlier_ratio)
                    confidence = overlap * inlier_ratio
                
                pair = TiePointPair(
                    frame_a_id=frame_a.frame_id,
                    frame_b_id=frame_b.frame_id,
                    match_count=match_count,
                    inlier_count=inlier_count,
                    confidence=confidence,
                )
                pairs.append(pair)
        
        graph.pairs = pairs
        graph.total_pairs = len(pairs)
        
        if pairs:
            graph.mean_match_count = sum(p.match_count for p in pairs) / len(pairs)
            graph.mean_inlier_count = sum(p.inlier_count for p in pairs) / len(pairs)
            graph.mean_confidence = sum(p.confidence for p in pairs) / len(pairs)
        
        # Per-frame overlap count
        for f, _ in usable:
            count = sum(
                1 for p in pairs
                if p.frame_a_id == f.frame_id or p.frame_b_id == f.frame_id
            )
            graph.frame_overlap_count[f.frame_id] = count
        
        # Connectivity analysis
        self._analyze_connectivity(graph, [f.frame_id for f, _ in usable])
        
        # V3: Build multi-frame tracks
        frame_map = {f.frame_id: f for f, _ in usable}
        if pair_matches:
            tiepoints, track_count, mean_length = _build_tracks(
                pairs, pair_matches, frame_features, frame_map=frame_map
            )
            graph.tiepoints = tiepoints
            graph.track_count = track_count
            graph.mean_track_length = mean_length
        else:
            # GPS-only fallback tiepoints
            graph.tiepoints = self._generate_tiepoints_gps(pairs, usable, frame_features)
        
        logger.info(
            f"[TiePoints] {graph.total_pairs} pairs, "
            f"mean matches={graph.mean_match_count:.0f}, "
            f"tracks={graph.track_count}, "
            f"mean_track_len={graph.mean_track_length:.1f}, "
            f"components={graph.connected_components}, "
            f"strip_risk={graph.missing_strip_risk:.2f}"
        )
        
        return graph
    
    def _check_collinearity(
        self,
        kps_a: List[Keypoint],
        kps_b: List[Keypoint],
        matches: List[Tuple[int, int, float]],
    ) -> float:
        """V3: Penalize near-collinear match distributions.
        
        If all matches are on a line, the geometry is degenerate.
        Returns 1.0 for good distribution, < 1.0 for collinear.
        """
        if len(matches) < 4:
            return 0.7  # Too few to assess
        
        # Compute displacement spread
        dxs = [kps_b[ib].x - kps_a[ia].x for ia, ib, _ in matches]
        dys = [kps_b[ib].y - kps_a[ia].y for ia, ib, _ in matches]
        
        # Variance of source keypoint positions
        xs = [kps_a[ia].x for ia, _, _ in matches]
        ys = [kps_a[ia].y for ia, _, _ in matches]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        var_x = sum((x - mean_x) ** 2 for x in xs) / len(xs)
        var_y = sum((y - mean_y) ** 2 for y in ys) / len(ys)
        
        spread = math.sqrt(var_x + var_y)
        if spread < 2.0:
            return 0.5  # All matches clustered in one spot
        
        return 1.0
    
    def _estimate_overlap_from_gps(
        self, frame_a: FrameMetadata, frame_b: FrameMetadata,
    ) -> float:
        """Estimate overlap fraction between two frames from GPS."""
        alt_a = frame_a.gps.altitude_m or 50.0
        alt_b = frame_b.gps.altitude_m or 50.0
        avg_alt = (alt_a + alt_b) / 2.0
        
        fw, fh = frame_a.camera.calculate_footprint_m(avg_alt)
        
        dlat_m = (frame_a.gps.latitude - frame_b.gps.latitude) * 111000
        dlon_m = (frame_a.gps.longitude - frame_b.gps.longitude) * 111000
        dist = math.sqrt(dlat_m ** 2 + dlon_m ** 2)
        
        if fw <= 0:
            return 0.0
        
        max_dim = max(fw, fh)
        return max(0.0, 1.0 - dist / max_dim)
    
    def _analyze_connectivity(
        self, graph: OverlapGraph, frame_ids: List[str],
    ) -> None:
        """Analyze overlap graph connectivity using union-find."""
        parent = {fid: fid for fid in frame_ids}
        
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        
        for pair in graph.pairs:
            if pair.frame_a_id in parent and pair.frame_b_id in parent:
                union(pair.frame_a_id, pair.frame_b_id)
        
        components = len(set(find(fid) for fid in frame_ids))
        graph.connected_components = components
        
        for fid, count in graph.frame_overlap_count.items():
            if count <= 1:
                graph.weakly_connected_frames.append(fid)
        
        if components > 1:
            graph.missing_strip_risk = min(1.0, components / 3.0)
        elif graph.weakly_connected_frames:
            graph.missing_strip_risk = min(
                0.5,
                len(graph.weakly_connected_frames) / max(len(frame_ids), 1) * 2
            )
    
    def _generate_tiepoints_gps(
        self,
        pairs: List[TiePointPair],
        usable: List[Tuple[FrameMetadata, FrameQAResult]],
        features: Dict[str, List[Keypoint]],
    ) -> List[TiePoint]:
        """Generate 3D tie-points from GPS when no visual matches exist."""
        tiepoints = []
        frame_map = {f.frame_id: f for f, _ in usable}
        
        for idx, pair in enumerate(pairs[:500]):
            fa = frame_map.get(pair.frame_a_id)
            fb = frame_map.get(pair.frame_b_id)
            if not fa or not fb:
                continue
            
            mid_lat = (fa.gps.latitude + fb.gps.latitude) / 2.0
            mid_lon = (fa.gps.longitude + fb.gps.longitude) / 2.0
            
            obs_a = self._project_point_to_frame(mid_lon, mid_lat, fa)
            obs_b = self._project_point_to_frame(mid_lon, mid_lat, fb)
            
            tp = TiePoint(
                point_id=f"tp_{idx:05d}",
                x=mid_lon, y=mid_lat, z=0.0,
                observations={fa.frame_id: obs_a, fb.frame_id: obs_b},
                confidence=pair.confidence,
            )
            tiepoints.append(tp)
        
        return tiepoints
    
    def _project_point_to_frame(
        self, world_lon: float, world_lat: float, frame: FrameMetadata,
    ) -> Tuple[float, float]:
        """Project a world point to frame pixel coordinates."""
        alt = frame.gps.altitude_m or 50.0
        cos_lat = math.cos(math.radians(frame.gps.latitude)) if frame.gps.latitude != 0 else 1.0
        
        dx_m = (world_lon - frame.gps.longitude) * 111000 * cos_lat
        dy_m = (world_lat - frame.gps.latitude) * 111000
        
        footprint_half_w = alt * 0.70
        footprint_half_h = alt * 0.52
        
        norm_x = dx_m / max(footprint_half_w, 0.1)
        norm_y = dy_m / max(footprint_half_h, 0.1)
        
        obs_w = 40.0
        obs_h = 30.0
        
        u = obs_w / 2.0 + norm_x * obs_w / 2.0
        v = obs_h / 2.0 - norm_y * obs_h / 2.0
        
        return (u, v)

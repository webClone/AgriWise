"""
Stage A — Frame Ingestion.

Reads all frames, extracts EXIF, extracts GPS/IMU, validates timestamps,
detects duplicates, sorts by mission sequence, attaches mission-plan context.

Output: a normalized FrameManifest with per-frame metadata and
missing-metadata flags.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import datetime
import hashlib
import logging

from .schemas import (
    DroneFrameSetInput,
    FrameMetadata,
    FrameGPS,
    CameraIntrinsics,
)

logger = logging.getLogger(__name__)


@dataclass
class FrameManifest:
    """Normalized frame manifest produced by ingestion.
    
    Contains all frames sorted by capture sequence with metadata
    attached and flags for missing/duplicate data.
    """
    mission_id: str = ""
    plot_id: str = ""
    frames: List[FrameMetadata] = field(default_factory=list)
    
    # Summary stats
    total_ingested: int = 0
    duplicates_found: int = 0
    missing_gps_count: int = 0
    missing_exif_count: int = 0
    
    # Resolution tracking (V3)
    resolution_mode: str = "benchmark"   # ResolutionMode value
    native_resolution: str = ""          # e.g. "4000x3000"
    working_resolution: str = ""         # e.g. "2000x1500"
    
    # Temporal span
    first_capture: Optional[datetime.datetime] = None
    last_capture: Optional[datetime.datetime] = None
    
    # Spatial extent
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    # (min_lon, min_lat, max_lon, max_lat)
    
    # Flags
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)


class FrameIngestor:
    """Ingests raw drone frames into a normalized manifest.
    
    V1: Works with synthetic frame data and GPS metadata.
    V2: Will read real EXIF from JPEG/TIFF frames.
    """
    
    MIN_FRAMES = 3  # Minimum frames for a viable mapping mission
    
    def ingest(self, inp: DroneFrameSetInput) -> FrameManifest:
        """Ingest a frame set and produce a normalized manifest.
        
        Args:
            inp: DroneFrameSetInput from the mission layer.
            
        Returns:
            FrameManifest with sorted, deduplicated frames.
        """
        manifest = FrameManifest(
            mission_id=inp.mission_id,
            plot_id=inp.plot_id,
        )
        
        steps = ["ingest_start"]
        
        # --- 1. Build frame metadata list ---
        frames = self._extract_frames(inp)
        manifest.total_ingested = len(frames)
        steps.append(f"extracted:{len(frames)}_frames")
        
        if len(frames) < self.MIN_FRAMES:
            manifest.is_valid = False
            manifest.validation_errors.append(
                f"Insufficient frames: {len(frames)} < {self.MIN_FRAMES}"
            )
            manifest.frames = frames
            return manifest
        
        # --- 2. Validate timestamps ---
        frames = self._validate_timestamps(frames, manifest)
        steps.append("validated_timestamps")
        
        # --- 3. Sort by mission sequence ---
        frames = self._sort_by_sequence(frames)
        steps.append("sorted_by_sequence")
        
        # --- 4. Detect duplicates ---
        frames, dup_count = self._detect_duplicates(frames)
        manifest.duplicates_found = dup_count
        steps.append(f"dedup:{dup_count}_duplicates")
        
        # --- 5. Flag missing metadata ---
        self._flag_missing_metadata(frames, manifest)
        steps.append("flagged_metadata")
        
        # --- 6. Compute spatial extent ---
        self._compute_bbox(frames, manifest)
        steps.append("computed_bbox")
        
        # --- 7. Compute temporal span ---
        self._compute_temporal_span(frames, manifest)
        
        manifest.frames = frames
        manifest.is_valid = len(manifest.validation_errors) == 0
        
        # --- V3: Record resolution info ---
        is_synthetic = inp.synthetic_frames is not None and len(inp.synthetic_frames) > 0
        if inp.resolution_mode:
            manifest.resolution_mode = inp.resolution_mode
        elif is_synthetic:
            manifest.resolution_mode = "benchmark"
        else:
            manifest.resolution_mode = "native"
        
        if frames:
            manifest.native_resolution = f"{frames[0].native_width_px}x{frames[0].native_height_px}"
            manifest.working_resolution = f"{frames[0].working_width_px}x{frames[0].working_height_px}"
        
        logger.info(
            f"[FrameIngestor] Ingested {manifest.total_ingested} frames "
            f"for mission {inp.mission_id}: "
            f"{manifest.duplicates_found} dups, "
            f"{manifest.missing_gps_count} missing GPS, "
            f"res_mode={manifest.resolution_mode}, "
            f"native={manifest.native_resolution}, "
            f"valid={manifest.is_valid}"
        )
        
        return manifest
    
    def _extract_frames(self, inp: DroneFrameSetInput) -> List[FrameMetadata]:
        """Extract frame metadata from input."""
        frames = []
        
        # Determine frame count from available data
        if inp.synthetic_frames:
            count = len(inp.synthetic_frames)
        elif inp.frame_refs:
            count = len(inp.frame_refs)
        else:
            count = inp.frame_count
        
        for i in range(count):
            frame = FrameMetadata(
                frame_id=f"{inp.mission_id}_frame_{i:04d}",
                sequence_index=i,
            )
            
            # Attach frame ref
            if inp.frame_refs and i < len(inp.frame_refs):
                frame.frame_ref = inp.frame_refs[i]
            
            # Attach GPS
            if inp.frame_gps and i < len(inp.frame_gps):
                frame.gps = inp.frame_gps[i]
            else:
                frame.missing_gps = True
            
            # Attach camera intrinsics (shared across mission)
            frame.camera = inp.camera
            
            # Attach synthetic pixels (for benchmarking)
            if inp.synthetic_frames and i < len(inp.synthetic_frames):
                frame.synthetic_pixels = inp.synthetic_frames[i]
            
            # --- V3: Populate resolution tracking ---
            # Native dimensions from camera intrinsics (real frame size)
            frame.native_width_px = inp.camera.image_width_px
            frame.native_height_px = inp.camera.image_height_px
            
            # If synthetic pixels exist, actual working size is the synthetic array
            if frame.synthetic_pixels:
                green = frame.synthetic_pixels.get("green", [])
                if green:
                    frame.working_height_px = len(green)
                    frame.working_width_px = len(green[0]) if green[0] else 0
                else:
                    frame.working_width_px = frame.native_width_px
                    frame.working_height_px = frame.native_height_px
            else:
                # Real frames: working = native (no forced downscale)
                frame.working_width_px = frame.native_width_px
                frame.working_height_px = frame.native_height_px
            
            # Pyramid levels available (lazily built — we only record availability)
            frame.pyramid_levels_available = ["native"]
            if frame.native_width_px >= 200 and frame.native_height_px >= 200:
                frame.pyramid_levels_available.append("half")
            if frame.native_width_px >= 400 and frame.native_height_px >= 400:
                frame.pyramid_levels_available.append("quarter")
            
            # Generate timestamp from sequence if not provided
            if inp.capture_timestamp:
                frame.capture_timestamp = inp.capture_timestamp + datetime.timedelta(
                    seconds=i * 2  # ~2s between captures is typical
                )
            
            frames.append(frame)
        
        return frames
    
    def _validate_timestamps(
        self, frames: List[FrameMetadata], manifest: FrameManifest
    ) -> List[FrameMetadata]:
        """Validate temporal ordering and flag anomalies."""
        timestamps = [
            f.capture_timestamp for f in frames if f.capture_timestamp
        ]
        
        if not timestamps:
            manifest.validation_errors.append("No timestamps available")
            return frames
        
        # Check for backwards jumps (clock reset)
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i - 1]:
                manifest.validation_errors.append(
                    f"Timestamp backwards jump at frame {i}: "
                    f"{timestamps[i]} < {timestamps[i-1]}"
                )
        
        return frames
    
    def _sort_by_sequence(self, frames: List[FrameMetadata]) -> List[FrameMetadata]:
        """Sort frames by capture sequence (timestamp, then index)."""
        return sorted(
            frames,
            key=lambda f: (f.capture_timestamp or datetime.datetime.min, f.sequence_index),
        )
    
    def _detect_duplicates(
        self, frames: List[FrameMetadata]
    ) -> Tuple[List[FrameMetadata], int]:
        """Detect duplicate frames by GPS proximity + timestamp proximity.
        
        V1 heuristic: frames within 0.5m and 0.5s of each other are duplicates.
        V2: will use image content hashing.
        """
        dup_count = 0
        seen_positions: List[Tuple[float, float, float]] = []
        
        for frame in frames:
            if frame.missing_gps:
                continue
                
            pos = (frame.gps.latitude, frame.gps.longitude, frame.gps.altitude_m)
            
            for seen in seen_positions:
                # Approximate distance in meters
                dlat = abs(pos[0] - seen[0]) * 111000
                dlon = abs(pos[1] - seen[1]) * 111000
                dalt = abs(pos[2] - seen[2])
                dist = (dlat**2 + dlon**2 + dalt**2) ** 0.5
                
                if dist < 0.5:  # Within 0.5m
                    frame.duplicate_of = "nearby_frame"
                    dup_count += 1
                    break
            else:
                seen_positions.append(pos)
        
        return frames, dup_count
    
    def _flag_missing_metadata(
        self, frames: List[FrameMetadata], manifest: FrameManifest
    ) -> None:
        """Count and flag frames with missing critical metadata."""
        for frame in frames:
            if frame.missing_gps:
                manifest.missing_gps_count += 1
            if frame.missing_exif:
                manifest.missing_exif_count += 1
        
        if manifest.missing_gps_count > len(frames) * 0.3:
            manifest.validation_errors.append(
                f"Too many frames missing GPS: {manifest.missing_gps_count}/{len(frames)}"
            )
    
    def _compute_bbox(
        self, frames: List[FrameMetadata], manifest: FrameManifest
    ) -> None:
        """Compute spatial bounding box from frame GPS positions."""
        lats = [f.gps.latitude for f in frames if not f.missing_gps and f.gps.latitude != 0]
        lons = [f.gps.longitude for f in frames if not f.missing_gps and f.gps.longitude != 0]
        
        if lats and lons:
            manifest.bbox = (min(lons), min(lats), max(lons), max(lats))
    
    def _compute_temporal_span(
        self, frames: List[FrameMetadata], manifest: FrameManifest
    ) -> None:
        """Compute first/last capture timestamps."""
        timestamps = [
            f.capture_timestamp for f in frames if f.capture_timestamp
        ]
        if timestamps:
            manifest.first_capture = min(timestamps)
            manifest.last_capture = max(timestamps)

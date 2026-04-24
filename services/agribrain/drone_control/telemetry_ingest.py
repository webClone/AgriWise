"""
Drone Control — Telemetry Ingestor.

Consumes TelemetryPacket stream from the driver. Persists enough
history to reconstruct planned-vs-flown path, feed mission history,
and support refly planning.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import math

from .schemas import TelemetryPacket


@dataclass
class FlownPoint:
    """A single point on the flown path."""
    latitude: float
    longitude: float
    altitude_m: float
    heading_deg: float
    groundspeed_m_s: float
    battery_pct: float
    off_track_m: float
    waypoint_index: int
    capture_count: int
    sequence: int


@dataclass
class TelemetrySummary:
    """Aggregated summary of the telemetry stream."""
    execution_id: str = ""
    total_packets: int = 0
    
    # Battery
    battery_start_pct: float = 0.0
    battery_end_pct: float = 0.0
    battery_used_pct: float = 0.0
    min_battery_pct: float = 100.0
    
    # Path
    flown_distance_m: float = 0.0
    mean_off_track_m: float = 0.0
    max_off_track_m: float = 0.0
    mean_altitude_m: float = 0.0
    mean_groundspeed_m_s: float = 0.0
    
    # Progress
    max_waypoint_reached: int = 0
    total_waypoints: int = 0
    final_progress_pct: float = 0.0
    
    # Captures
    total_captures: int = 0
    expected_captures: int = 0
    capture_completeness_pct: float = 0.0
    
    # GPS quality
    min_gps_satellites: int = 99
    max_gps_hdop: float = 0.0
    gps_loss_count: int = 0
    
    # Link quality
    min_link_quality_pct: float = 100.0
    link_loss_count: int = 0


class TelemetryIngestor:
    """Ingests and persists telemetry packets.
    
    Builds a flown path and summary that can be used for:
    - Planned-vs-flown reconstruction
    - Mission history
    - Refly planning
    - Operator audit
    """
    
    def __init__(self, execution_id: str = ""):
        self._execution_id = execution_id
        self._packets: List[TelemetryPacket] = []
        self._flown_path: List[FlownPoint] = []
        self._battery_start: Optional[float] = None
    
    @property
    def packet_count(self) -> int:
        return len(self._packets)
    
    @property
    def flown_path(self) -> List[FlownPoint]:
        return list(self._flown_path)
    
    @property
    def packets(self) -> List[TelemetryPacket]:
        return list(self._packets)
    
    def ingest(self, packet: TelemetryPacket):
        """Ingest a single telemetry packet."""
        self._packets.append(packet)
        
        # Record battery start
        if self._battery_start is None:
            self._battery_start = packet.state.battery_pct
        
        # Record flown path point
        self._flown_path.append(FlownPoint(
            latitude=packet.state.latitude,
            longitude=packet.state.longitude,
            altitude_m=packet.state.altitude_m,
            heading_deg=packet.state.heading_deg,
            groundspeed_m_s=packet.state.groundspeed_m_s,
            battery_pct=packet.state.battery_pct,
            off_track_m=packet.off_track_m,
            waypoint_index=packet.current_waypoint_index,
            capture_count=packet.capture_count,
            sequence=packet.sequence,
        ))
    
    def summarize(self) -> TelemetrySummary:
        """Build an aggregated summary of all ingested telemetry."""
        if not self._packets:
            return TelemetrySummary(execution_id=self._execution_id)
        
        summary = TelemetrySummary(
            execution_id=self._execution_id,
            total_packets=len(self._packets),
        )
        
        # Battery
        summary.battery_start_pct = self._battery_start or 0.0
        summary.battery_end_pct = self._packets[-1].state.battery_pct
        summary.battery_used_pct = summary.battery_start_pct - summary.battery_end_pct
        summary.min_battery_pct = min(p.state.battery_pct for p in self._packets)
        
        # Path distance
        dist = 0.0
        for i in range(len(self._flown_path) - 1):
            p1, p2 = self._flown_path[i], self._flown_path[i + 1]
            dx = (p2.longitude - p1.longitude) * 85000.0
            dy = (p2.latitude - p1.latitude) * 111000.0
            dist += math.sqrt(dx * dx + dy * dy)
        summary.flown_distance_m = dist
        
        # Off-track
        off_tracks = [p.off_track_m for p in self._flown_path]
        summary.mean_off_track_m = sum(off_tracks) / len(off_tracks) if off_tracks else 0.0
        summary.max_off_track_m = max(off_tracks) if off_tracks else 0.0
        
        # Altitude & speed
        alts = [p.altitude_m for p in self._flown_path]
        speeds = [p.groundspeed_m_s for p in self._flown_path]
        summary.mean_altitude_m = sum(alts) / len(alts) if alts else 0.0
        summary.mean_groundspeed_m_s = sum(speeds) / len(speeds) if speeds else 0.0
        
        # Progress
        last = self._packets[-1]
        summary.max_waypoint_reached = last.current_waypoint_index
        summary.total_waypoints = last.total_waypoints
        summary.final_progress_pct = last.mission_progress_pct
        
        # Captures
        summary.total_captures = last.capture_count
        summary.expected_captures = last.expected_captures
        if last.expected_captures > 0:
            summary.capture_completeness_pct = (
                last.capture_count / last.expected_captures * 100.0
            )
        
        # GPS quality
        sats = [p.state.gps_satellites for p in self._packets]
        hdops = [p.state.gps_hdop for p in self._packets]
        summary.min_gps_satellites = min(sats) if sats else 0
        summary.max_gps_hdop = max(hdops) if hdops else 99.0
        summary.gps_loss_count = sum(1 for p in self._packets if not p.state.gps_fix)
        
        # Link quality
        links = [p.state.link_quality_pct for p in self._packets]
        summary.min_link_quality_pct = min(links) if links else 0.0
        summary.link_loss_count = sum(1 for p in self._packets if p.state.link_quality_pct < 1.0)
        
        return summary
    
    def get_flown_vs_planned_deviation(
        self,
        planned_waypoints: List[Tuple[float, float]],
    ) -> List[float]:
        """Compute per-waypoint deviation between flown and planned path.
        
        Args:
            planned_waypoints: List of (lat, lon) planned positions
            
        Returns:
            List of deviation distances in meters
        """
        deviations = []
        for point in self._flown_path:
            if point.waypoint_index < len(planned_waypoints):
                planned_lat, planned_lon = planned_waypoints[point.waypoint_index]
                dx = (point.longitude - planned_lon) * 85000.0
                dy = (point.latitude - planned_lat) * 111000.0
                deviations.append(math.sqrt(dx * dx + dy * dy))
        return deviations

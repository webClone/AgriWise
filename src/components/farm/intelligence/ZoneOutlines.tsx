"use client";

import { Polygon, Tooltip } from "react-leaflet";
import type { ZoneData } from "@/hooks/useLayer10";

interface ZoneOutlinesProps {
  zones: ZoneData[];
  gridHeight: number;
  gridWidth: number;
  bounds: { north: number; south: number; east: number; west: number };
  selectedZone: string | null;
  onZoneClick: (zoneId: string) => void;
}

// Zone type → visual style
const ZONE_STYLES: Record<string, { color: string; label: string }> = {
  LOW_VIGOR:      { color: "#ef4444", label: "Low Vigor" },
  WATER_STRESS:   { color: "#f59e0b", label: "Water Stress" },
  NUTRIENT_RISK:  { color: "#eab308", label: "Nutrient Risk" },
  DISEASE_RISK:   { color: "#f97316", label: "Disease Risk" },
  YIELD_GAP:      { color: "#dc2626", label: "Yield Gap" },
  HIGH_VIGOR:     { color: "#22c55e", label: "High Vigor" },
  IRRIGATE_ZONE:  { color: "#3b82f6", label: "Irrigate" },
  FERTILIZE_ZONE: { color: "#a855f7", label: "Fertilize" },
  SPRAY_ZONE:     { color: "#ec4899", label: "Spray" },
  BLOCKED_ZONE:   { color: "#64748b", label: "Blocked" },
  WAIT_ZONE:      { color: "#94a3b8", label: "Wait" },
  LOW_CONFIDENCE: { color: "#6b7280", label: "Low Confidence" },
  STALE_DATA:     { color: "#9ca3af", label: "Stale Data" },
  HIGH_CONFLICT:  { color: "#f43f5e", label: "Conflict" },
};

function cellIndicesToPolygon(
  cellIndices: [number, number][],
  gridH: number,
  gridW: number,
  bounds: { north: number; south: number; east: number; west: number }
): [number, number][] {
  // Convert cell indices to a bounding polygon (convex hull approximation)
  // Each cell is at (row, col) in the grid
  const latStep = (bounds.north - bounds.south) / gridH;
  const lngStep = (bounds.east - bounds.west) / gridW;

  if (cellIndices.length === 0) return [];

  // Find bounding box of cells
  let minR = Infinity, maxR = -Infinity, minC = Infinity, maxC = -Infinity;
  for (const [r, c] of cellIndices) {
    if (r < minR) minR = r;
    if (r > maxR) maxR = r;
    if (c < minC) minC = c;
    if (c > maxC) maxC = c;
  }

  // Convert to lat/lng polygon (clockwise)
  const south = bounds.north - (maxR + 1) * latStep;
  const north = bounds.north - minR * latStep;
  const west = bounds.west + minC * lngStep;
  const east = bounds.west + (maxC + 1) * lngStep;

  return [
    [north, west],
    [north, east],
    [south, east],
    [south, west],
    [north, west], // close
  ];
}

/** Severity → text label */
function severityLabel(s: number): string {
  if (s >= 0.8) return "Critical";
  if (s >= 0.6) return "High";
  if (s >= 0.4) return "Moderate";
  if (s >= 0.2) return "Low";
  return "Minimal";
}

export default function ZoneOutlines({
  zones,
  gridHeight,
  gridWidth,
  bounds,
  selectedZone,
  onZoneClick,
}: ZoneOutlinesProps) {
  return (
    <>
      {zones.map((zone) => {
        const positions = cellIndicesToPolygon(
          zone.cell_indices,
          gridHeight,
          gridWidth,
          bounds
        );
        if (positions.length === 0) return null;

        const style = ZONE_STYLES[zone.zone_type] || { color: "#94a3b8", label: zone.zone_type };
        const isSelected = selectedZone === zone.zone_id;

        return (
          <Polygon
            key={zone.zone_id}
            positions={positions}
            pathOptions={{
              color: style.color,
              weight: isSelected ? 3 : 2,
              fillColor: style.color,
              fillOpacity: isSelected ? 0.22 : 0.12,
              dashArray: isSelected ? undefined : "6, 4",
              className: "zone-contour",
            }}
            eventHandlers={{
              click: () => onZoneClick(zone.zone_id),
            }}
          >
            <Tooltip
              direction="top"
              offset={[0, -10]}
              opacity={0.95}
              className="zone-tooltip"
            >
              <div className="text-xs space-y-0.5">
                <div className="font-semibold" style={{ color: style.color }}>
                  {style.label}
                </div>
                <div className="text-slate-300">
                  Severity: {severityLabel(zone.severity)} ({(zone.severity * 100).toFixed(0)}%)
                </div>
                <div className="text-slate-400">
                  Confidence: {(zone.confidence * 100).toFixed(0)}%
                </div>
                {zone.top_drivers.length > 0 && (
                  <div className="text-slate-500 text-[10px]">
                    Drivers: {zone.top_drivers.slice(0, 2).join(", ")}
                  </div>
                )}
              </div>
            </Tooltip>
          </Polygon>
        );
      })}
    </>
  );
}

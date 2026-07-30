"use client";

/**
 * ZoneChip — Compact, anchored floating label at zone centroid
 *
 * Design principles:
 *   - Small and dense (not a floating box)
 *   - Anchored to zone via subtle glow dot/stem
 *   - Sits close to centroid
 *   - Fades in AFTER zone highlight (staged: 180-240ms delay)
 *   - Feels attached, not pasted on top
 */

import { useMemo } from "react";

interface ZoneChipProps {
  label: string;
  confidence: number;
  areaFraction: number;
  severity?: number;
  primaryDriver?: string | null;
  centroid: [number, number]; // [lng, lat]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  viewState: any;
}

function projectToScreen(
  lng: number, lat: number,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  viewState: any
): [number, number] | null {
  if (!viewState || viewState.longitude == null || viewState.latitude == null) return null;

  const zoom = viewState.zoom ?? 14;
  const centerLng = viewState.longitude;
  const centerLat = viewState.latitude;
  const width = viewState.width ?? 800;
  const height = viewState.height ?? 600;
  const scale = Math.pow(2, zoom) * 256;

  const centerX = ((centerLng + 180) / 360) * scale;
  const centerY = ((1 - Math.log(Math.tan((centerLat * Math.PI) / 180) + 1 / Math.cos((centerLat * Math.PI) / 180)) / Math.PI) / 2) * scale;
  const pointX = ((lng + 180) / 360) * scale;
  const pointY = ((1 - Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) / 2) * scale;

  const screenX = width / 2 + (pointX - centerX);
  const screenY = height / 2 + (pointY - centerY);

  if (screenX < -50 || screenX > width + 50 || screenY < -50 || screenY > height + 50) return null;
  return [screenX, screenY];
}

export default function ZoneChip({ label, confidence, areaFraction, severity, primaryDriver, centroid, viewState }: ZoneChipProps) {
  const screenPos = useMemo(
    () => projectToScreen(centroid[0], centroid[1], viewState),
    [centroid, viewState]
  );

  if (!screenPos) return null;

  const [x, y] = screenPos;
  const confPct = Math.round(confidence * 100);
  const sevPct = severity != null ? Math.round(severity * 100) : null;

  // Truncate long labels
  const shortLabel = label.length > 22 ? label.slice(0, 20) + "…" : label;
  const shortDriver = primaryDriver && primaryDriver.length > 18
    ? primaryDriver.slice(0, 16) + "…"
    : primaryDriver;

  return (
    <div
      className="zone-chip"
      style={{ left: `${x}px`, top: `${y}px` }}
    >
      {/* Anchor glow — small radial dot connecting chip to zone */}
      <div className="zone-chip-anchor" />

      {/* Chip body — compact, dark, dense */}
      <div className="zone-chip-body">
        <span className="zone-chip-label">{shortLabel}</span>
        <span className="zone-chip-meta">
          {confPct}%{sevPct != null ? ` · ${sevPct}% sev` : ""}
        </span>
        {shortDriver && (
          <span className="zone-chip-driver">{shortDriver}</span>
        )}
      </div>
    </div>
  );
}

"use client";

import { Droplets, History, FlaskConical, MapPin, Radio, Activity, X } from "lucide-react";
import { usePlotWorkspace } from "./PlotWorkspaceProvider";
import { useLayer10 } from "@/hooks/useLayer10";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";

export type P04InvestigationKind = "water" | "compare" | "simulate";

export default function WorkspaceContextActionsP04({
  onLaunch,
  onOpenSensor,
  workspaceEntities = [],
}: {
  onLaunch: (kind: P04InvestigationKind) => void;
  onOpenSensor?: (sensorId: string) => void;
  workspaceEntities?: WorkspaceFeatureEnvelope[];
}) {
  const { state, selectEntity } = usePlotWorkspace();
  const layer10 = useLayer10();
  const selection = state.selectedEntity;
  const plotMatches = !layer10.data || layer10.data.plot_id === state.plotScope.plotId;

  // 1. Zone selection context
  if (selection.kind === "ZONE" && plotMatches && selection.id) {
    const zoneId = selection.id;
    return (
      <section className="p04-map-context" aria-label="Zone investigation actions" data-testid="p04-map-context">
        <div className="p04-context-title">
          <MapPin size={16} aria-hidden="true" />
          <span>Investigate zone <strong>{zoneId}</strong></span>
        </div>
        <div className="p04-context-actions">
          <button type="button" onClick={() => onLaunch("water")}><Droplets size={15} /> Water stress</button>
          <button type="button" onClick={() => onLaunch("compare")}><History size={15} /> Compare time</button>
          <button type="button" onClick={() => onLaunch("simulate")}><FlaskConical size={15} /> Prepare what-if</button>
        </div>
      </section>
    );
  }

  // 2. Sensor selection context (P05)
  if (selection.kind === "SENSOR" && selection.id) {
    const sensorEntity =
      workspaceEntities.find(
        (e) => e.entity_id === selection.id || e.envelope_id === selection.id
      ) || ((selection.metadata as unknown) as WorkspaceFeatureEnvelope | undefined);

    const props = ((sensorEntity?.properties || {}) as Record<string, any>);
    const coords = sensorEntity?.geometry?.coordinates;
    const depth = sensorEntity?.spatial_support?.depth_cm;
    const isOnline = props.isOnline ?? true;
    const battery = props.battery;
    const latest = props.latestReading;
    const digest = sensorEntity?.provenance?.record_digest;
    const deviceId = props.deviceId || selection.id;
    const vendor = props.vendor || "Field Hardware";

    return (
      <section
        className="p04-map-context p05-sensor-context"
        aria-label="Sensor device context"
        data-testid="p05-sensor-context"
        style={{
          borderLeft: isOnline ? "4px solid #10b981" : "4px solid #94a3b8",
        }}
      >
        <div className="p04-context-title" style={{ justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Radio size={16} style={{ color: isOnline ? "#34d399" : "#94a3b8" }} aria-hidden="true" />
            <span>
              Sensor <strong>{deviceId}</strong>
              {depth != null && (
                <span style={{ marginInlineStart: 6, fontSize: "11px", opacity: 0.85, color: "#6ee7b7" }}>
                  ({depth} cm depth)
                </span>
              )}
            </span>
          </div>
          <span
            style={{
              fontSize: "10px",
              padding: "2px 8px",
              borderRadius: "999px",
              background: isOnline ? "rgba(16,185,129,0.2)" : "rgba(148,163,184,0.2)",
              color: isOnline ? "#34d399" : "#94a3b8",
              border: `1px solid ${isOnline ? "rgba(16,185,129,0.4)" : "rgba(148,163,184,0.3)"}`,
              fontWeight: 700,
              letterSpacing: "0.05em",
            }}
          >
            {isOnline ? "ONLINE" : "OFFLINE"}
          </span>
        </div>

        <div style={{ display: "flex", gap: "10px", fontSize: "11px", color: "#c5d7cb", marginBottom: "8px", flexWrap: "wrap" }}>
          {coords && (
            <span title="Authoritative registered WGS84 coordinates">
              📍 {coords[1].toFixed(6)}°N, {coords[0].toFixed(6)}°E
            </span>
          )}
          {latest?.soilMoisture != null && (
            <span>💧 VWC: {(latest.soilMoisture * (latest.soilMoisture <= 1 ? 100 : 1)).toFixed(1)}%</span>
          )}
          {latest?.temperature != null && (
            <span>🌡️ {latest.temperature.toFixed(1)}°C</span>
          )}
          {battery != null && (
            <span>🔋 {battery}%</span>
          )}
          <span style={{ color: "#94a3b8" }}>· {vendor}</span>
        </div>

        {digest && (
          <div style={{ fontSize: "10px", color: "#8ca895", marginBottom: "9px", fontFamily: "monospace" }}>
            Certified: {digest.slice(0, 16)}… (Registered Hardware)
          </div>
        )}

        <div className="p04-context-actions">
          <button
            type="button"
            onClick={() => onOpenSensor && onOpenSensor(String(deviceId))}
            style={{
              background: "#166534",
              borderColor: "#22c55e",
              color: "#f0fdf4",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Activity size={15} /> Open Instrument
          </button>
          <button
            type="button"
            onClick={() =>
              selectEntity({
                kind: null,
                id: null,
                sourceSnapshotId: null,
              })
            }
            style={{
              background: "rgba(255,255,255,0.06)",
              borderColor: "rgba(255,255,255,0.15)",
              color: "#94a3b8",
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            <X size={15} /> Clear selection
          </button>
        </div>
      </section>
    );
  }

  return null;
}

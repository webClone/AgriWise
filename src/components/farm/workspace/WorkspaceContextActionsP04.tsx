"use client";

import { Droplets, History, FlaskConical, MapPin, Radio, Activity, Camera, Plane, FileText, X } from "lucide-react";
import { usePlotWorkspace } from "./PlotWorkspaceProvider";
import { useLayer10 } from "@/hooks/useLayer10";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";
import type { WorkspaceQuickAction } from "./WorkspaceToolDock";

export type P04InvestigationKind = "water" | "compare" | "simulate";

export default function WorkspaceContextActionsP04({
  onLaunch,
  onOpenSensor,
  onOpenTool,
  workspaceEntities = [],
}: {
  onLaunch: (kind: P04InvestigationKind) => void;
  onOpenSensor?: (sensorId: string) => void;
  onOpenTool?: (tool: WorkspaceQuickAction) => void;
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
    const isFixture = props.is_benchmark_fixture === true || sensorEntity?.epistemic_class === "SIMULATED";
    const isOnline = isFixture ? false : (props.isOnline ?? true);
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
          borderLeft: isFixture ? "4px solid #eab308" : isOnline ? "4px solid #10b981" : "4px solid #94a3b8",
        }}
      >
        <div className="p04-context-title" style={{ justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Radio size={16} style={{ color: isFixture ? "#facc15" : isOnline ? "#34d399" : "#94a3b8" }} aria-hidden="true" />
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
              background: isFixture ? "rgba(234,179,8,0.15)" : isOnline ? "rgba(16,185,129,0.2)" : "rgba(148,163,184,0.2)",
              color: isFixture ? "#facc15" : isOnline ? "#34d399" : "#94a3b8",
              border: `1px solid ${isFixture ? "rgba(234,179,8,0.35)" : isOnline ? "rgba(16,185,129,0.4)" : "rgba(148,163,184,0.3)"}`,
              fontWeight: 700,
              letterSpacing: "0.05em",
            }}
          >
            {isFixture ? "DEMO FIXTURE" : isOnline ? "ONLINE" : "OFFLINE"}
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
            Envelope Integrity: {digest.slice(0, 16)}…
            {sensorEntity?.provenance?.verified_identity ? " (Verified Identity)" : ""}
          </div>
        )}

        <div className="p04-context-actions">
          <button
            type="button"
            onClick={() => onOpenSensor && onOpenSensor(String(sensorEntity?.entity_id || deviceId))}
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

  // 3. Camera selection context (P05.03)
  if (selection.kind === "CAMERA" && selection.id) {
    const cameraEntity =
      workspaceEntities.find(
        (e) => e.entity_id === selection.id || e.envelope_id === selection.id
      ) || ((selection.metadata as unknown) as WorkspaceFeatureEnvelope | undefined);

    const props = ((cameraEntity?.properties || {}) as Record<string, any>);
    const coords = cameraEntity?.geometry?.coordinates;
    const isFixture = props.is_benchmark_fixture === true || cameraEntity?.epistemic_class === "SIMULATED";
    const deviceId = props.deviceId || selection.id;
    const model = props.model || "AgroCam Vision Trap";
    const resolution = props.resolution || "4K UHD";
    const digest = cameraEntity?.provenance?.record_digest;

    return (
      <section
        className="p04-map-context p05-camera-context"
        aria-label="Camera device context"
        data-testid="p05-camera-context"
        style={{ borderLeft: "4px solid #a855f7" }}
      >
        <div className="p04-context-title" style={{ justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Camera size={16} style={{ color: "#c084fc" }} aria-hidden="true" />
            <span>
              Camera <strong>{deviceId}</strong>
            </span>
          </div>
          <span
            style={{
              fontSize: "10px",
              padding: "2px 8px",
              borderRadius: "999px",
              background: isFixture ? "rgba(234,179,8,0.15)" : "rgba(168,85,247,0.2)",
              color: isFixture ? "#facc15" : "#c084fc",
              border: `1px solid ${isFixture ? "rgba(234,179,8,0.35)" : "rgba(168,85,247,0.4)"}`,
              fontWeight: 700,
              letterSpacing: "0.05em",
            }}
          >
            {isFixture ? "DEMO FIXTURE" : "ACTIVE CAMERA"}
          </span>
        </div>

        <div style={{ display: "flex", gap: "10px", fontSize: "11px", color: "#c5d7cb", marginBottom: "8px", flexWrap: "wrap" }}>
          {coords && (
            <span title="Registered coordinates">
              📍 {coords[1].toFixed(6)}°N, {coords[0].toFixed(6)}°E
            </span>
          )}
          <span>📷 {model} ({resolution})</span>
        </div>

        {digest && (
          <div style={{ fontSize: "10px", color: "#8ca895", marginBottom: "9px", fontFamily: "monospace" }}>
            Envelope Integrity: {digest.slice(0, 16)}…
          </div>
        )}

        <div className="p04-context-actions">
          <button
            type="button"
            onClick={() => onOpenTool && onOpenTool("evidence")}
            style={{
              background: "#6b21a8",
              borderColor: "#a855f7",
              color: "#faf5ff",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Camera size={15} /> View Visual Stream
          </button>
          <button
            type="button"
            onClick={() => selectEntity({ kind: null, id: null, sourceSnapshotId: null })}
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

  // 4. Drone mission selection context (P05.03)
  if (selection.kind === "DRONE_MISSION" && selection.id) {
    const droneEntity =
      workspaceEntities.find(
        (e) => e.entity_id === selection.id || e.envelope_id === selection.id
      ) || ((selection.metadata as unknown) as WorkspaceFeatureEnvelope | undefined);

    const props = ((droneEntity?.properties || {}) as Record<string, any>);
    const coords = droneEntity?.geometry?.coordinates;
    const missionId = props.missionId || selection.id;
    const missionType = props.missionType || "MAPPING";
    const altitudeM = props.altitudeM || 45;
    const gsd = props.gsdCmPx || 2.0;
    const status = props.status || "PLANNED";
    const digest = droneEntity?.provenance?.record_digest;

    return (
      <section
        className="p04-map-context p05-drone-context"
        aria-label="Drone mission context"
        data-testid="p05-drone-context"
        style={{ borderLeft: "4px solid #f97316" }}
      >
        <div className="p04-context-title" style={{ justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Plane size={16} style={{ color: "#fb923c" }} aria-hidden="true" />
            <span>
              Drone Mission <strong>{missionId}</strong>
            </span>
          </div>
          <span
            style={{
              fontSize: "10px",
              padding: "2px 8px",
              borderRadius: "999px",
              background: "rgba(249,115,22,0.2)",
              color: "#fb923c",
              border: "1px solid rgba(249,115,22,0.4)",
              fontWeight: 700,
              letterSpacing: "0.05em",
            }}
          >
            {status}
          </span>
        </div>

        <div style={{ display: "flex", gap: "10px", fontSize: "11px", color: "#c5d7cb", marginBottom: "8px", flexWrap: "wrap" }}>
          {coords && (
            <span title="Takeoff/Corridor coordinates">
              📍 {coords[1].toFixed(6)}°N, {coords[0].toFixed(6)}°E
            </span>
          )}
          <span>🛫 {missionType} @ {altitudeM}m (GSD: {gsd} cm/px)</span>
        </div>

        {digest && (
          <div style={{ fontSize: "10px", color: "#8ca895", marginBottom: "9px", fontFamily: "monospace" }}>
            Envelope Integrity: {digest.slice(0, 16)}…
          </div>
        )}

        <div className="p04-context-actions">
          <button
            type="button"
            onClick={() => onOpenTool && onOpenTool("drone")}
            style={{
              background: "#c2410c",
              borderColor: "#ea580c",
              color: "#fff7ed",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Plane size={15} /> Open Mission Control
          </button>
          <button
            type="button"
            onClick={() => selectEntity({ kind: null, id: null, sourceSnapshotId: null })}
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

  // 5. Field observation selection context (P05.03)
  if ((selection.kind === "FIELD_OBSERVATION" || selection.kind === "FIELD_EVENT") && selection.id) {
    const obsEntity =
      workspaceEntities.find(
        (e) => e.entity_id === selection.id || e.envelope_id === selection.id
      ) || ((selection.metadata as unknown) as WorkspaceFeatureEnvelope | undefined);

    const props = ((obsEntity?.properties || {}) as Record<string, any>);
    const coords = obsEntity?.geometry?.coordinates;
    const category = props.category || "SCOUTING";
    const observer = props.observer || "Agronomist";
    const notes = props.notes || "Field scouting record";
    const digest = obsEntity?.provenance?.record_digest;

    return (
      <section
        className="p04-map-context p05-observation-context"
        aria-label="Field observation context"
        data-testid="p05-observation-context"
        style={{ borderLeft: "4px solid #f43f5e" }}
      >
        <div className="p04-context-title" style={{ justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <FileText size={16} style={{ color: "#fb7185" }} aria-hidden="true" />
            <span>
              Observation <strong>{category}</strong>
            </span>
          </div>
          <span
            style={{
              fontSize: "10px",
              padding: "2px 8px",
              borderRadius: "999px",
              background: "rgba(244,63,94,0.2)",
              color: "#fb7185",
              border: "1px solid rgba(244,63,94,0.4)",
              fontWeight: 700,
              letterSpacing: "0.05em",
            }}
          >
            GROUND SCOUT
          </span>
        </div>

        <div style={{ display: "flex", gap: "10px", fontSize: "11px", color: "#c5d7cb", marginBottom: "8px", flexWrap: "wrap" }}>
          {coords && (
            <span title="GPS surveyed coordinate">
              📍 {coords[1].toFixed(6)}°N, {coords[0].toFixed(6)}°E
            </span>
          )}
          <span>🔍 {notes}</span>
          <span style={{ color: "#94a3b8" }}>· {observer}</span>
        </div>

        {digest && (
          <div style={{ fontSize: "10px", color: "#8ca895", marginBottom: "9px", fontFamily: "monospace" }}>
            Envelope Integrity: {digest.slice(0, 16)}…
          </div>
        )}

        <div className="p04-context-actions">
          <button
            type="button"
            onClick={() => onOpenTool && onOpenTool("evidence")}
            style={{
              background: "#be123c",
              borderColor: "#e11d48",
              color: "#fff1f2",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <FileText size={15} /> Add / View Evidence
          </button>
          <button
            type="button"
            onClick={() => selectEntity({ kind: null, id: null, sourceSnapshotId: null })}
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

"use client";

import dynamic from "next/dynamic";
import { useCallback, useMemo } from "react";
import type { WorkspaceQuickAction } from "./WorkspaceToolDock";

const SensorNetworkWorkspace = dynamic(
  () => import("@/components/farm/intelligence/SensorNetworkWorkspace"),
  { ssr: false }
);
const DroneMissionPanel = dynamic(
  () => import("@/components/farm/drone/DroneMissionPanel"),
  { ssr: false }
);
const MesiaObservatoryWorkspace = dynamic(
  () => import("@/components/farm/intelligence/MesiaObservatoryWorkspace"),
  { ssr: false }
);
const IrrigationDashboard = dynamic(
  () => import("@/components/irrigation/IrrigationDashboard"),
  { ssr: false }
);
const AddEvidenceModal = dynamic(
  () => import("@/components/farm/intelligence/AddEvidenceModal"),
  { ssr: false }
);

interface WorkspaceSpecializedToolsProps {
  plotId: string;
  plot?: Record<string, unknown> | null;
  activeSpecializedTool: WorkspaceQuickAction | null;
  initialSensorId?: string | null;
  onClose: () => void;
  onEvidenceAdded?: () => void;
}

/**
 * P04 Specialized Tool Runtime Host:
 * Dynamically mounts Sensor, Drone, MESIA, Irrigation and Evidence
 * workspaces on-demand from the Workspace Tool Dock, preserving all
 * safety gates (read-only flight, disabled physical actuators).
 */
export default function WorkspaceSpecializedToolsP04({
  plotId,
  plot,
  activeSpecializedTool,
  initialSensorId,
  onClose,
  onEvidenceAdded,
}: WorkspaceSpecializedToolsProps) {
  const dronePolygon = useMemo(() => {
    if (!plot?.geoJson) return undefined;
    try {
      const parsed =
        typeof plot.geoJson === "string"
          ? JSON.parse(plot.geoJson as string)
          : plot.geoJson;
      if (parsed?.geometry?.coordinates) return parsed.geometry;
      if (parsed?.coordinates) return parsed;
    } catch {
      /* parse error — leave undefined */
    }
    return undefined;
  }, [plot?.geoJson]);

  const handleEvidenceSuccess = useCallback(() => {
    onClose();
    if (onEvidenceAdded) onEvidenceAdded();
  }, [onClose, onEvidenceAdded]);

  if (!activeSpecializedTool) return null;

  return (
    <>
      {activeSpecializedTool === "sensors" && (
        <SensorNetworkWorkspace
          plotId={plotId}
          initialSensorId={initialSensorId}
          onClose={onClose}
        />
      )}

      {activeSpecializedTool === "drone" && (
        <DroneMissionPanel
          plotId={plotId}
          polygonGeoJson={dronePolygon}
          onClose={onClose}
        />
      )}

      {activeSpecializedTool === "mesia" && (
        <MesiaObservatoryWorkspace plotId={plotId} onClose={onClose} />
      )}

      {activeSpecializedTool === "irrigation" && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 60,
            background: "rgba(2,6,23,0.95)",
            backdropFilter: "blur(20px)",
            overflowY: "auto",
          }}
        >
          <div
            style={{
              position: "sticky",
              top: 0,
              zIndex: 10,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "12px 24px",
              background: "rgba(2,6,23,0.9)",
              borderBottom: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <span style={{ fontSize: 14, fontWeight: 600, color: "#94A3B8" }}>
              Irrigation Simulation Workspace (Actuators Disabled)
            </span>
            <button
              onClick={onClose}
              style={{
                padding: "6px 16px",
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,0.1)",
                background: "rgba(255,255,255,0.04)",
                color: "#94A3B8",
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              ✕ Close
            </button>
          </div>
          <IrrigationDashboard />
        </div>
      )}

      {activeSpecializedTool === "evidence" && (
        <AddEvidenceModal
          plotId={plotId}
          onClose={onClose}
          onSuccess={handleEvidenceSuccess}
        />
      )}
    </>
  );
}

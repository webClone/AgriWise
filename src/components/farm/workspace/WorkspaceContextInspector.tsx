"use client";

import Link from "next/link";
import { useLayer10 } from "@/hooks/useLayer10";
import { useParcelAssessment } from "@/hooks/useParcelAssessment";
import { usePlotWorkspace } from "./PlotWorkspaceProvider";
import {
  ChevronLeft,
  ChevronRight,
  Focus,
  Layers3,
  MapPin,
  X,
  Radio,
  Activity,
  CheckCircle,
  AlertCircle,
} from "lucide-react";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";

export default function WorkspaceContextInspector({
  farmId,
  plotId,
  onCollapse,
  onOpenSensor,
  workspaceEntities = [],
}: {
  farmId: string;
  plotId: string;
  onCollapse: () => void;
  onOpenSensor?: (sensorId: string) => void;
  workspaceEntities?: WorkspaceFeatureEnvelope[];
}) {
  const layer10 = useLayer10();
  const parcel = useParcelAssessment();
  const { state, selectEntity } = usePlotWorkspace();

  const selectedEntity = state.selectedEntity;
  const selectedZoneId = layer10.selectedZone;
  const zone = layer10.data?.zones?.find((z) => z.zone_id === selectedZoneId) ?? null;

  // Selected sensor entity (P05)
  const sensorEntity =
    selectedEntity.kind === "SENSOR"
      ? workspaceEntities.find(
          (e) => e.entity_id === selectedEntity.id || e.envelope_id === selectedEntity.id
        ) || ((selectedEntity.metadata as unknown) as WorkspaceFeatureEnvelope | undefined)
      : null;

  const snapshotId =
    parcel.assessment?.identity?.snapshotId ?? layer10.data?.publication_id ?? null;
  const sourceValidForPlot = parcel.isApplicable && parcel.status === "ready";
  const analysisUrl = `/farm/${encodeURIComponent(farmId)}/plot/${encodeURIComponent(plotId)}/analysis`;

  const sensorProps = (sensorEntity?.properties || {}) as Record<string, any>;
  const sensorCoords = sensorEntity?.geometry?.coordinates;
  const sensorDepth = sensorEntity?.spatial_support?.depth_cm;
  const isOnline = sensorProps.isOnline ?? true;
  const latest = sensorProps.latestReading;

  return (
    <section className="pw-inspector" aria-label="Context Inspector">
      <header className="pw-inspector-header">
        <div>
          <span className="pw-eyebrow">PLOT INTELLIGENCE</span>
          <h2>Context Inspector</h2>
        </div>
        <button
          type="button"
          className="pw-icon-button"
          onClick={onCollapse}
          title="Collapse inspector"
          aria-label="Collapse Context Inspector"
        >
          <ChevronRight size={17} className="pw-ltr-icon" aria-hidden="true" />
          <ChevronLeft size={17} className="pw-rtl-icon" aria-hidden="true" />
        </button>
      </header>

      <div className="pw-inspector-content">
        {/* Selected Sensor Section (P05) */}
        {selectedEntity.kind === "SENSOR" && sensorEntity ? (
          <div className="pw-info-section" data-testid="p05-sensor-inspector">
            <div className="pw-section-title">
              <Radio size={15} className={isOnline ? "text-emerald-400" : "text-slate-400"} aria-hidden="true" />
              <span>Registered Sensor</span>
            </div>
            <strong className="pw-info-large">{sensorProps.deviceId || selectedEntity.id}</strong>
            <p style={{ margin: "4px 0 10px", fontSize: "12px", color: "#94a3b8" }}>
              {sensorProps.vendor || "Hardware"} · {sensorProps.model || "IoT Sensor"}
            </p>

            <dl className="pw-definition-list" style={{ marginBottom: "12px" }}>
              <div>
                <dt>Hardware Status</dt>
                <dd style={{ color: isOnline ? "#34d399" : "#94a3b8", fontWeight: 600 }}>
                  {isOnline ? "ONLINE (Active)" : "OFFLINE"}
                </dd>
              </div>
              {sensorDepth != null && (
                <div>
                  <dt>Placement Depth</dt>
                  <dd>{sensorDepth} cm</dd>
                </div>
              )}
              {sensorCoords ? (
                <div>
                  <dt>Coordinates</dt>
                  <dd title={`${sensorCoords[1]}, ${sensorCoords[0]}`}>
                    {sensorCoords[1].toFixed(5)}°N, {sensorCoords[0].toFixed(5)}°E
                  </dd>
                </div>
              ) : (
                <div>
                  <dt>Coordinates</dt>
                  <dd style={{ color: "#f59e0b" }}>Location not registered (List only)</dd>
                </div>
              )}
              {sensorProps.battery != null && (
                <div>
                  <dt>Battery</dt>
                  <dd>{sensorProps.battery}%</dd>
                </div>
              )}
              {sensorProps.rssi != null && (
                <div>
                  <dt>Signal Strength</dt>
                  <dd>{sensorProps.rssi} dBm</dd>
                </div>
              )}
              {latest?.soilMoisture != null && (
                <div>
                  <dt>Latest VWC</dt>
                  <dd style={{ color: "#38bdf8", fontWeight: 700 }}>
                    {(latest.soilMoisture * (latest.soilMoisture <= 1 ? 100 : 1)).toFixed(1)}%
                  </dd>
                </div>
              )}
              {latest?.temperature != null && (
                <div>
                  <dt>Temperature</dt>
                  <dd>{latest.temperature.toFixed(1)}°C</dd>
                </div>
              )}
            </dl>

            <div style={{ display: "flex", gap: "8px", flexDirection: "column" }}>
              <button
                type="button"
                className="pw-primary-link"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "6px",
                  cursor: "pointer",
                  width: "100%",
                  border: "none",
                  padding: "10px",
                  borderRadius: "8px",
                }}
                onClick={() =>
                  onOpenSensor && onOpenSensor(String(sensorProps.deviceId || selectedEntity.id))
                }
              >
                <Activity size={15} /> Open Sensor Instrument
              </button>
              <button
                type="button"
                className="pw-secondary-button"
                onClick={() =>
                  selectEntity({
                    kind: null,
                    id: null,
                    sourceSnapshotId: null,
                  })
                }
              >
                <X size={14} aria-hidden="true" /> Clear selection
              </button>
            </div>
          </div>
        ) : (
          /* Zone Selection Section */
          <div className="pw-info-section">
            <div className="pw-section-title">
              <MapPin size={15} aria-hidden="true" /> Selected location
            </div>
            {zone ? (
              <>
                <strong className="pw-info-large">{zone.zone_id}</strong>
                <p>
                  Zone geometry originates from the current Layer 10 view. Its
                  scientific interpretation depends on the publication shown below.
                </p>
                <button
                  type="button"
                  className="pw-secondary-button"
                  onClick={() => layer10.setSelectedZone(null)}
                >
                  <X size={14} aria-hidden="true" /> Clear zone selection
                </button>
              </>
            ) : (
              <div className="pw-empty-selection">
                <Focus size={25} aria-hidden="true" />
                <strong>No spatial entity selected</strong>
                <span>
                  Select a grounded zone or registered sensor pin on the map to inspect related context.
                </span>
              </div>
            )}
          </div>
        )}

        <div className="pw-info-section">
          <div className="pw-section-title">
            <Layers3 size={15} aria-hidden="true" /> Scientific view
          </div>
          <dl className="pw-definition-list">
            <div>
              <dt>Active lens</dt>
              <dd>{layer10.activeMode}</dd>
            </div>
            <div>
              <dt>Publication</dt>
              <dd title={snapshotId || undefined}>{snapshotId || "Unavailable"}</dd>
            </div>
            <div>
              <dt>Applicability</dt>
              <dd>
                {sourceValidForPlot
                  ? "Current plot/crop context"
                  : "Not confirmed for current context"}
              </dd>
            </div>
            <div>
              <dt>Zones available</dt>
              <dd>{layer10.data?.zones.length ?? 0}</dd>
            </div>
            <div>
              <dt>Sensors registered</dt>
              <dd>{workspaceEntities.length}</dd>
            </div>
          </dl>
          <p className="pw-trust-warning">
            A colored basemap is not evidence of a scientific raster. Inspect
            the map&apos;s authorized pixel legend and source receipt before interpretation.
          </p>
        </div>

        <div className="pw-info-section">
          <div className="pw-section-title">Related tools</div>
          <Link className="pw-primary-link" href={analysisUrl}>
            Open AgriBrain analysis
          </Link>
          <p>
            Full 13-state laboratory and cross-tool entity selection are scheduled
            for P03–P07; this inspector does not create unverified correlations.
          </p>
        </div>
      </div>
    </section>
  );
}

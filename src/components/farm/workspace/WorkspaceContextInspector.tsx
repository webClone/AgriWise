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
  Camera,
  Plane,
  FileText,
  CheckCircle,
  AlertCircle,
} from "lucide-react";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";
import type { WorkspaceQuickAction } from "./WorkspaceToolDock";

export default function WorkspaceContextInspector({
  farmId,
  plotId,
  onCollapse,
  onOpenSensor,
  onOpenTool,
  workspaceEntities = [],
}: {
  farmId: string;
  plotId: string;
  onCollapse: () => void;
  onOpenSensor?: (sensorId: string) => void;
  onOpenTool?: (tool: WorkspaceQuickAction) => void;
  workspaceEntities?: WorkspaceFeatureEnvelope[];
}) {
  const layer10 = useLayer10();
  const parcel = useParcelAssessment();
  const { state, selectEntity } = usePlotWorkspace();

  const selectedEntity = state.selectedEntity;
  const selectedZoneId = layer10.selectedZone;
  const zone = layer10.data?.zones?.find((z) => z.zone_id === selectedZoneId) ?? null;

  // Selected matched entity
  const matchedEntity =
    selectedEntity.kind && selectedEntity.id
      ? workspaceEntities.find(
          (e) => e.entity_id === selectedEntity.id || e.envelope_id === selectedEntity.id
        ) || ((selectedEntity.metadata as unknown) as WorkspaceFeatureEnvelope | undefined)
      : null;

  const snapshotId =
    parcel.assessment?.identity?.snapshotId ?? layer10.data?.publication_id ?? null;
  const sourceValidForPlot = parcel.isApplicable && parcel.status === "ready";
  const analysisUrl = `/farm/${encodeURIComponent(farmId)}/plot/${encodeURIComponent(plotId)}/analysis`;

  const entityProps = (matchedEntity?.properties || {}) as Record<string, any>;
  const entityCoords = matchedEntity?.geometry?.coordinates;
  const isFixture = entityProps.is_benchmark_fixture === true || matchedEntity?.epistemic_class === "SIMULATED";
  const isOnline = isFixture ? false : (entityProps.isOnline ?? true);
  const latest = entityProps.latestReading;

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
        {/* 1. Selected SENSOR Section */}
        {selectedEntity.kind === "SENSOR" && matchedEntity ? (
          <div className="pw-info-section" data-testid="p05-sensor-inspector">
            <div className="pw-section-title">
              <Radio size={15} className={isFixture ? "text-amber-400" : isOnline ? "text-emerald-400" : "text-slate-400"} aria-hidden="true" />
              <span>{isFixture ? "Simulated Benchmark Probe" : "Registered Sensor"}</span>
            </div>
            <strong className="pw-info-large">{entityProps.deviceId || selectedEntity.id}</strong>
            <p style={{ margin: "4px 0 10px", fontSize: "12px", color: "#94a3b8" }}>
              {entityProps.vendor || "Hardware"} · {entityProps.model || "IoT Sensor"}
            </p>

            <dl className="pw-definition-list" style={{ marginBottom: "12px" }}>
              <div>
                <dt>Hardware Status</dt>
                <dd style={{ color: isFixture ? "#facc15" : isOnline ? "#34d399" : "#94a3b8", fontWeight: 600 }}>
                  {isFixture ? "DEMO FIXTURE (No Telemetry Feed)" : isOnline ? "ONLINE (Active)" : "OFFLINE"}
                </dd>
              </div>
              <div>
                <dt>Epistemic Class</dt>
                <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#e2e8f0" }}>
                  {matchedEntity.epistemic_class}
                </dd>
              </div>
              {matchedEntity.provenance?.record_digest && (
                <div>
                  <dt>Envelope Integrity</dt>
                  <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#8ca895" }}>
                    {matchedEntity.provenance.record_digest.slice(0, 16)}…
                    {matchedEntity.provenance.verified_identity ? " (Verified)" : ""}
                  </dd>
                </div>
              )}
              {matchedEntity.spatial_support?.depth_cm != null && (
                <div>
                  <dt>Placement Depth</dt>
                  <dd>{matchedEntity.spatial_support.depth_cm} cm</dd>
                </div>
              )}
              {entityCoords ? (
                <div>
                  <dt>Coordinates</dt>
                  <dd title={`${entityCoords[1]}, ${entityCoords[0]}`}>
                    {entityCoords[1].toFixed(5)}°N, {entityCoords[0].toFixed(5)}°E
                  </dd>
                </div>
              ) : (
                <div>
                  <dt>Coordinates</dt>
                  <dd style={{ color: "#f59e0b" }}>Location not registered (List only)</dd>
                </div>
              )}
              {entityProps.battery != null && (
                <div>
                  <dt>Battery</dt>
                  <dd>{entityProps.battery}%</dd>
                </div>
              )}
              {entityProps.rssi != null && (
                <div>
                  <dt>Signal Strength</dt>
                  <dd>{entityProps.rssi} dBm</dd>
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
                  onOpenSensor && onOpenSensor(String(matchedEntity.entity_id || entityProps.deviceId || selectedEntity.id))
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
        ) : selectedEntity.kind === "CAMERA" && matchedEntity ? (
          /* 2. Selected CAMERA Section */
          <div className="pw-info-section" data-testid="p05-camera-inspector">
            <div className="pw-section-title">
              <Camera size={15} className="text-purple-400" aria-hidden="true" />
              <span>{isFixture ? "Simulated Camera Trap" : "Fixed Field Camera"}</span>
            </div>
            <strong className="pw-info-large">{entityProps.deviceId || selectedEntity.id}</strong>
            <p style={{ margin: "4px 0 10px", fontSize: "12px", color: "#94a3b8" }}>
              {entityProps.vendor || "AgroVision"} · {entityProps.model || "Vision Station"}
            </p>

            <dl className="pw-definition-list" style={{ marginBottom: "12px" }}>
              <div>
                <dt>Camera Status</dt>
                <dd style={{ color: "#c084fc", fontWeight: 600 }}>
                  {isFixture ? "DEMO FIXTURE (Standby)" : "ACTIVE STREAM"}
                </dd>
              </div>
              <div>
                <dt>Epistemic Class</dt>
                <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#e2e8f0" }}>
                  {matchedEntity.epistemic_class}
                </dd>
              </div>
              <div>
                <dt>Resolution</dt>
                <dd>{entityProps.resolution || "4K UHD (3840x2160)"}</dd>
              </div>
              <div>
                <dt>Field of View</dt>
                <dd>{entityProps.fieldOfView || "120° Wide Angle"}</dd>
              </div>
              {matchedEntity.provenance?.record_digest && (
                <div>
                  <dt>Envelope Integrity</dt>
                  <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#8ca895" }}>
                    {matchedEntity.provenance.record_digest.slice(0, 16)}…
                  </dd>
                </div>
              )}
              {entityCoords && (
                <div>
                  <dt>Coordinates</dt>
                  <dd>{entityCoords[1].toFixed(5)}°N, {entityCoords[0].toFixed(5)}°E</dd>
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
                  background: "#7c3aed",
                }}
                onClick={() => onOpenTool && onOpenTool("evidence")}
              >
                <Camera size={15} /> View Visual Stream
              </button>
              <button
                type="button"
                className="pw-secondary-button"
                onClick={() => selectEntity({ kind: null, id: null, sourceSnapshotId: null })}
              >
                <X size={14} aria-hidden="true" /> Clear selection
              </button>
            </div>
          </div>
        ) : selectedEntity.kind === "DRONE_MISSION" && matchedEntity ? (
          /* 3. Selected DRONE_MISSION Section */
          <div className="pw-info-section" data-testid="p05-drone-inspector">
            <div className="pw-section-title">
              <Plane size={15} className="text-orange-400" aria-hidden="true" />
              <span>Drone Mission Flight Plan</span>
            </div>
            <strong className="pw-info-large">{entityProps.name || selectedEntity.id}</strong>
            <p style={{ margin: "4px 0 10px", fontSize: "12px", color: "#94a3b8" }}>
              {entityProps.vendor || "DJI Enterprise"} · {entityProps.model || "Matrice 350 RTK"}
            </p>

            <dl className="pw-definition-list" style={{ marginBottom: "12px" }}>
              <div>
                <dt>Mission Status</dt>
                <dd style={{ color: "#fb923c", fontWeight: 600 }}>{entityProps.status || "PLANNED"}</dd>
              </div>
              <div>
                <dt>Flight Pattern</dt>
                <dd>{entityProps.pattern || "Boustrophedon (Lawnmower)"}</dd>
              </div>
              <div>
                <dt>Target Altitude</dt>
                <dd>{entityProps.altitudeM || 45} m AGL</dd>
              </div>
              <div>
                <dt>Ground Resolution</dt>
                <dd>{entityProps.gsdCmPx || 1.8} cm/pixel GSD</dd>
              </div>
              <div>
                <dt>Epistemic Class</dt>
                <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#e2e8f0" }}>
                  {matchedEntity.epistemic_class}
                </dd>
              </div>
              {matchedEntity.provenance?.record_digest && (
                <div>
                  <dt>Envelope Integrity</dt>
                  <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#8ca895" }}>
                    {matchedEntity.provenance.record_digest.slice(0, 16)}…
                  </dd>
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
                  background: "#ea580c",
                }}
                onClick={() => onOpenTool && onOpenTool("drone")}
              >
                <Plane size={15} /> Open Mission Control
              </button>
              <button
                type="button"
                className="pw-secondary-button"
                onClick={() => selectEntity({ kind: null, id: null, sourceSnapshotId: null })}
              >
                <X size={14} aria-hidden="true" /> Clear selection
              </button>
            </div>
          </div>
        ) : (selectedEntity.kind === "FIELD_OBSERVATION" || selectedEntity.kind === "FIELD_EVENT") && matchedEntity ? (
          /* 4. Selected FIELD_OBSERVATION Section */
          <div className="pw-info-section" data-testid="p05-observation-inspector">
            <div className="pw-section-title">
              <FileText size={15} className="text-rose-400" aria-hidden="true" />
              <span>Field Scouting Observation</span>
            </div>
            <strong className="pw-info-large">{entityProps.name || entityProps.category || "Scouting Record"}</strong>
            <p style={{ margin: "4px 0 10px", fontSize: "12px", color: "#94a3b8" }}>
              {entityProps.notes || "Field scouting log entry"}
            </p>

            <dl className="pw-definition-list" style={{ marginBottom: "12px" }}>
              <div>
                <dt>Severity</dt>
                <dd style={{ color: "#f43f5e", fontWeight: 600 }}>{entityProps.severity || "MEDIUM"}</dd>
              </div>
              <div>
                <dt>Observer</dt>
                <dd>{entityProps.observer || "Field Agronomist"}</dd>
              </div>
              <div>
                <dt>Epistemic Class</dt>
                <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#e2e8f0" }}>
                  {matchedEntity.epistemic_class}
                </dd>
              </div>
              {Array.isArray(entityProps.aiTags) && entityProps.aiTags.length > 0 && (
                <div>
                  <dt>AI Tags</dt>
                  <dd style={{ color: "#38bdf8" }}>{entityProps.aiTags.join(", ")}</dd>
                </div>
              )}
              {matchedEntity.provenance?.record_digest && (
                <div>
                  <dt>Envelope Integrity</dt>
                  <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#8ca895" }}>
                    {matchedEntity.provenance.record_digest.slice(0, 16)}…
                  </dd>
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
                  background: "#e11d48",
                }}
                onClick={() => onOpenTool && onOpenTool("evidence")}
              >
                <FileText size={15} /> Add / View Evidence
              </button>
              <button
                type="button"
                className="pw-secondary-button"
                onClick={() => selectEntity({ kind: null, id: null, sourceSnapshotId: null })}
              >
                <X size={14} aria-hidden="true" /> Clear selection
              </button>
            </div>
          </div>
        ) : (
          /* 5. Zone or Empty Selection Section */
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
                  Select a grounded zone, sensor pin, camera trap, or drone mission on the map to inspect related context.
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
              <dd>
                {snapshotId ? (
                  <span className="pw-digest" title={snapshotId}>
                    {snapshotId.slice(0, 12)}…
                  </span>
                ) : (
                  "Unavailable"
                )}
              </dd>
            </div>
            <div>
              <dt>Applicability</dt>
              <dd>
                {sourceValidForPlot ? (
                  <span className="pw-status-chip pw-chip-valid">
                    <CheckCircle size={12} aria-hidden="true" />
                    Verified for plot
                  </span>
                ) : (
                  <span className="pw-status-chip pw-chip-neutral">
                    <AlertCircle size={12} aria-hidden="true" />
                    Not confirmed for current context
                  </span>
                )}
              </dd>
            </div>
            <div>
              <dt>Zones available</dt>
              <dd>{layer10.data?.zones?.length ?? 0}</dd>
            </div>
            <div>
              <dt>Entities registered</dt>
              <dd>{workspaceEntities.length}</dd>
            </div>
          </dl>

          <p className="pw-footnote">
            A colored basemap is not evidence of a scientific raster. Inspect
            the map&apos;s authorized pixel legend and source receipt before interpretation.
          </p>

          <div className="pw-section-title" style={{ marginTop: "1rem" }}>
            <span>Related tools</span>
          </div>
          <div className="pw-quick-links">
            <Link href={analysisUrl} className="pw-secondary-button">
              Open Analysis Lab
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

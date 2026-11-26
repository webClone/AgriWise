"use client";

import { useState, useEffect } from "react";
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
  Edit3,
  Trash2,
  History,
  Scale,
  FlaskConical,
} from "lucide-react";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";
import {geometryBounds} from "@/lib/agribrain/workspace-geometry.mjs";
import {summarizeWorkspaceGeometry} from "./p07-spatial-summary.mjs";
import type { WorkspaceQuickAction } from "./WorkspaceToolDock";
import {
  ASMAE_13_STATE_ORDER,
  ASMAE_13_STATE_CATALOG,
  ASMAE_STATUS_META,
  resolveAsmaeStateAvailability,
  compareSensorWithCollocatedAsmae,
  type AsmaeStateKey,
  type AsmaeStateAvailabilityResult,
} from "@/lib/agribrain/asmae-13-states";
import type {
  SoilDepthProfile,
} from "@/lib/agribrain/physical-sensor-contract";
import type { ChannelStatus } from "@/lib/agribrain/physical-observation-store";
import HistoricalIntelligencePanel, { type HistoricalIntelligencePayload } from "./HistoricalIntelligencePanel";

export default function WorkspaceContextInspector({
  farmId,
  plotId,
  onCollapse,
  onOpenSensor,
  onOpenTool,
  workspaceEntities = [],
  onRevise,
  onRevoke,
  onHistory,
  activeAsmaeKey = "vigor",
  onSelectAsmaeState,
  activeAsmaeAvailability,
  sirePixelHover,
  historicalAsOfDate = null,
  historicalLoading = false,
  historicalError = null,
  historicalData = null,
  onSelectHistoricalDate,
  onReturnHistoricalToLive,
}: {
  farmId: string;
  plotId: string;
  onCollapse: () => void;
  onOpenSensor?: (sensorId: string) => void;
  onOpenTool?: (tool: WorkspaceQuickAction) => void;
  workspaceEntities?: WorkspaceFeatureEnvelope[];
  onRevise?: (entity: WorkspaceFeatureEnvelope) => void;
  onRevoke?: (entity: WorkspaceFeatureEnvelope) => void;
  onHistory?: (entity: WorkspaceFeatureEnvelope) => void;
  activeAsmaeKey?: AsmaeStateKey;
  onSelectAsmaeState?: (key: AsmaeStateKey) => void;
  activeAsmaeAvailability?: AsmaeStateAvailabilityResult;
  sirePixelHover?: { value: number | null; sigma?: number | null; row: number; col: number; coordinate: [number, number] } | null;
  historicalAsOfDate?: string | null;
  historicalLoading?: boolean;
  historicalError?: string | null;
  historicalData?: HistoricalIntelligencePayload | null;
  onSelectHistoricalDate?: (dateIso: string) => void;
  onReturnHistoricalToLive?: () => void;
}) {
  const [labViewMode, setLabViewMode] = useState<"farmer" | "expert">("farmer");
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
        ) || ((selectedEntity as any).metadata ? {
          entity_id: selectedEntity.id,
          envelope_id: selectedEntity.id,
          entity_kind: selectedEntity.kind,
          kind: selectedEntity.kind,
          epistemic_class: (selectedEntity as any).metadata?.epistemic_class || "OBSERVED_TELEMETRY",
          properties: (selectedEntity as any).metadata,
        } as any : null)
      : null;

  const snapshotId =
    parcel.assessment?.identity?.snapshotId ?? layer10.data?.publication_id ?? null;
  const sourceValidForPlot = parcel.isApplicable && parcel.status === "ready";
  const analysisUrl = `/farm/${encodeURIComponent(farmId)}/plot/${encodeURIComponent(plotId)}/analysis`;

  // Resolved ASMAE state context
  const rawPub = parcel.rawPublication;
  const posteriorRecord = rawPub?.asmae_posterior_numerical_record || null;
  const pubSurfaces = rawPub?.surfaces || layer10.data?.surfaces || [];
  const pubInventory = rawPub?.surface_inventory || null;

  const currentAsmaeAvail =
    activeAsmaeAvailability ||
    resolveAsmaeStateAvailability(activeAsmaeKey, pubSurfaces, posteriorRecord, pubInventory, {
      validationState: parcel.status === "invalid" ? "corrupt" : parcel.status === "stale" ? "stale" : "valid",
    });

  const activeDef = ASMAE_13_STATE_CATALOG[activeAsmaeKey] || ASMAE_13_STATE_CATALOG.vigor;
  const canonicalStatusKey =
    currentAsmaeAvail.status === "QUALIFIED_RASTER"
      ? "QUALIFIED_SPATIAL"
      : currentAsmaeAvail.status === "SCALAR_ONLY"
      ? "PLOT_ESTIMATE"
      : (currentAsmaeAvail.status as "QUALIFIED_SPATIAL" | "PLOT_ESTIMATE" | "UNAVAILABLE" | "BLOCKED");
  const activeStatusMeta = ASMAE_STATUS_META[canonicalStatusKey] || ASMAE_STATUS_META.UNAVAILABLE;

  const entityProps = (matchedEntity?.properties || {}) as Record<string, any>;
  const targetDeviceId = matchedEntity ? String(matchedEntity.entity_id || entityProps.deviceId || "") : "";

  // W2-R06: Fetch owner-scoped depth profile directly from authorized API as single authority
  const [fetchedProfile, setFetchedProfile] = useState<SoilDepthProfile | null>(null);
  const [fetchedChannels, setFetchedChannels] = useState<ChannelStatus[]>([]);
  const [profileLoading, setProfileLoading] = useState<boolean>(false);

  useEffect(() => {
    if (selectedEntity.kind !== "SENSOR" || !plotId || !targetDeviceId) {
      setFetchedProfile(null);
      setFetchedChannels([]);
      return;
    }

    const controller = new AbortController();
    setProfileLoading(true);

    fetch(
      `/api/plots/${encodeURIComponent(plotId)}/sensors/depth-profile?deviceId=${encodeURIComponent(targetDeviceId)}`,
      { signal: controller.signal }
    )
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.profile) {
          setFetchedProfile(data.profile);
          setFetchedChannels(data.channels || []);
        } else {
          setFetchedProfile(null);
          setFetchedChannels([]);
        }
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setFetchedProfile(null);
          setFetchedChannels([]);
        }
      })
      .finally(() => {
        setProfileLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [selectedEntity.kind, plotId, targetDeviceId]);

  const soilProfile = fetchedProfile;

  // Collocated in-situ moisture comparison strictly from authorized profile (W2-R06 & W2-R07)
  const rootZoneAvail = resolveAsmaeStateAvailability("root_zone_water", pubSurfaces, posteriorRecord, pubInventory);
  const measuredMoistureLayer = fetchedProfile?.layers?.find((l) => l.measured && l.vwcFraction !== null);
  const sensorMoistureValue = measuredMoistureLayer ? measuredMoistureLayer.vwcFraction : null;
  const sensorMoistureDepth = measuredMoistureLayer?.nominalCm ?? null;

  const sensorComparison =
    matchedEntity && selectedEntity.kind === "SENSOR" && sensorMoistureValue !== null
      ? compareSensorWithCollocatedAsmae(
          {
            soilMoisture: sensorMoistureValue,
            depthCm: sensorMoistureDepth,
          },
          rootZoneAvail
        )
      : null;
  const entityCoords = matchedEntity?.geometry?.type==="Point" ? matchedEntity.geometry.coordinates : null;
  const footprintBounds = matchedEntity?.geometry?.type !== "Point" ? geometryBounds(matchedEntity?.geometry) : null;
  const ownerDeclared=matchedEntity?.spatial_support?.location_source==="USER_DECLARED";
  const spatialSummary=summarizeWorkspaceGeometry(matchedEntity?.geometry ?? null);
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
          data-testid="p07-inspector-collapse-btn"
          onClick={onCollapse}
          title="Collapse inspector"
          aria-label="Collapse Context Inspector"
        >
          <ChevronRight size={17} className="pw-ltr-icon" aria-hidden="true" />
          <ChevronLeft size={17} className="pw-rtl-icon" aria-hidden="true" />
        </button>
      </header>

      <div className="pw-inspector-content">
        {matchedEntity && (
          <section className="pw-p07-entity-overview" aria-label="Selected entity overview"
            data-testid="p07-entity-overview">
            <div className="pw-p07-entity-overline">
              <span>{(matchedEntity.entity_kind || (matchedEntity as any).kind || "").replaceAll("_"," ")}</span>
              <span data-epistemic={matchedEntity.epistemic_class}>{(matchedEntity.epistemic_class || "OBSERVED_TELEMETRY").replaceAll("_"," ")}</span>
            </div>
            <h3>{String(entityProps.name || entityProps.deviceId || matchedEntity.entity_id)}</h3>
            <dl className="pw-p07-metrics">
              <div><dt>Mapped shape</dt><dd>{matchedEntity.geometry?.type || "Location not registered"}</dd></div>
              {spatialSummary?.areaM2 != null && <div><dt>Drawn area</dt><dd>{(spatialSummary.areaM2/10000).toFixed(2)} ha</dd></div>}
              {spatialSummary?.perimeterM != null && <div><dt>Perimeter</dt><dd>{Math.round(spatialSummary.perimeterM)} m</dd></div>}
              {spatialSummary?.lengthM != null && <div><dt>Route length</dt><dd>{Math.round(spatialSummary.lengthM)} m</dd></div>}
              {spatialSummary && <div><dt>Vertices</dt><dd>{spatialSummary.vertexCount}</dd></div>}
              {ownerDeclared && <div><dt>Revision</dt><dd>{String(entityProps.revision || 1)}</dd></div>}
              {matchedEntity.provenance?.record_digest && <div><dt>Envelope integrity</dt>
                <dd className="pw-p07-digest">{matchedEntity.provenance.record_digest.slice(0,12)}…</dd></div>}
            </dl>
            {ownerDeclared && <>
              <p className="pw-p07-entity-note">Owner-declared geometry. Dimensions are calculated from submitted vertices, not a verified survey or scientific publication.</p>
              <div className="pw-p07-entity-actions" aria-label="Geometry lifecycle actions">
                <button type="button" className="pw-p07-action-primary" data-testid="p06-revise-btn"
                  onClick={()=>onRevise?.(matchedEntity)}><Edit3 size={14}/> Adjust vertices</button>
                <button type="button" data-testid="p06-history-btn"
                  onClick={()=>onHistory?.(matchedEntity)}><History size={14}/> History</button>
                <button type="button" className="pw-p07-action-danger" data-testid="p06-revoke-btn"
                  onClick={()=>onRevoke?.(matchedEntity)}><Trash2 size={14}/> Revoke</button>
              </div>
            </>}
          </section>
        )}
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
              {ownerDeclared && <div role="note" style={{color:"#f59e0b",fontSize:"12px",fontWeight:600}}>
                Owner-declared geometry · Not independently verified or scientifically admitted
              </div>}
              {footprintBounds && (
                <div>
                  <dt>Mapped geometry</dt>
                  <dd>{matchedEntity.geometry?.type} · bounds [{footprintBounds.map(v=>v.toFixed(5)).join(", ")}]</dd>
                </div>
              )}
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

            {/* W2: Multi-Depth Soil Water Profile */}
            {soilProfile && (
              <div
                className="pw-soil-depth-profile-card"
                data-testid="p07-soil-depth-profile"
                style={{
                  background: "rgba(15, 23, 42, 0.75)",
                  border: "1px solid rgba(56, 189, 248, 0.25)",
                  borderRadius: "8px",
                  padding: "10px",
                  marginTop: "8px",
                  marginBottom: "10px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <Layers3 size={14} style={{ color: "#38bdf8" }} />
                    <span style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.05em", color: "#38bdf8", textTransform: "uppercase" }}>
                      Soil Water Profile
                    </span>
                    {entityProps.channelOffline && (
                      <span style={{ fontSize: "9px", background: "rgba(239, 68, 68, 0.2)", color: "#f87171", border: "1px solid rgba(239, 68, 68, 0.4)", borderRadius: "3px", padding: "1px 5px" }}>
                        Offline
                      </span>
                    )}
                    {entityProps.calibrationExpired && (
                      <span style={{ fontSize: "9px", background: "rgba(245, 158, 11, 0.2)", color: "#fbbf24", border: "1px solid rgba(245, 158, 11, 0.4)", borderRadius: "3px", padding: "1px 5px" }}>
                        Cal Expired
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: "9px", color: "#94a3b8", background: "rgba(255,255,255,0.06)", padding: "2px 6px", borderRadius: "4px" }}>
                    {soilProfile.measuredCount} measured depth{soilProfile.measuredCount === 1 ? "" : "s"}
                  </span>
                </div>

                <div style={{ fontSize: "9px", color: "#64748b", marginBottom: "8px" }}>
                  Historical evidence · Point sensors do not extrapolate across vertical profile
                </div>

                {/* Depth Bars */}
                <div style={{ display: "flex", flexDirection: "column", gap: "5px", marginBottom: "8px" }}>
                  {soilProfile.layers.map((layer) => (
                    <div key={layer.nominalCm} style={{ display: "grid", gridTemplateColumns: "42px 1fr 75px", alignItems: "center", gap: "8px", fontSize: "10px" }}>
                      <span style={{ color: "#94a3b8", fontFamily: "monospace" }}>{layer.nominalCm} cm</span>
                      <div style={{ height: "6px", background: "rgba(255,255,255,0.06)", borderRadius: "3px", overflow: "hidden" }}>
                        {layer.measured && layer.vwcFraction !== null ? (
                          <div
                            style={{
                              height: "100%",
                              width: `${Math.min(100, Math.max(0, (layer.vwcFraction / 0.6) * 100))}%`,
                              background: "linear-gradient(90deg, #38bdf8, #0284c7)",
                              borderRadius: "3px",
                            }}
                          />
                        ) : null}
                      </div>
                      <span style={{ textAlign: "right", color: layer.measured ? "#38bdf8" : "#64748b", fontWeight: layer.measured ? 700 : 400 }}>
                        {layer.label}
                      </span>
                    </div>
                  ))}
                </div>

                <div style={{ fontSize: "8.5px", color: "#64748b", fontStyle: "italic", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "4px" }}>
                  {soilProfile.supportDifferenceDisclaimer}
                </div>
              </div>
            )}

            {/* W1/W2 Collocated Sensor Telemetry vs. ASMAE Posterior State Comparison */}
            {sensorComparison && (
              <div
                className="pw-sensor-asmae-comparison"
                data-testid="p05-sensor-asmae-comparison"
                style={{
                  background: "rgba(15, 23, 42, 0.65)",
                  border: "1px solid rgba(56, 189, 248, 0.25)",
                  borderRadius: "8px",
                  padding: "10px",
                  marginTop: "8px",
                  marginBottom: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                  <Scale size={14} style={{ color: "#38bdf8" }} />
                  <span style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.05em", color: "#38bdf8", textTransform: "uppercase" }}>
                    Collocated Telemetry vs. ASMAE Context
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "8px" }}>
                  <div style={{ background: "rgba(255,255,255,0.03)", padding: "6px 8px", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div style={{ fontSize: "9px", fontWeight: 800, color: "#38bdf8", letterSpacing: "0.05em" }}>OBSERVED TELEMETRY</div>
                    <div style={{ fontSize: "13px", fontWeight: 750, color: "#f8fafc", margin: "2px 0" }}>
                      {sensorComparison.sensorValue !== null ? `${(sensorComparison.sensorValue * 100).toFixed(1)}% VWC` : "N/A"}
                    </div>
                    <div style={{ fontSize: "9px", color: "#94a3b8" }}>
                      In-situ probe ({sensorComparison.sensorDepthCm != null ? `${sensorComparison.sensorDepthCm}cm` : "depth uncalibrated"})
                    </div>
                  </div>
                  <div style={{ background: "rgba(255,255,255,0.03)", padding: "6px 8px", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div style={{ fontSize: "9px", fontWeight: 800, color: "#34d399", letterSpacing: "0.05em" }}>SCIENTIFIC ESTIMATE</div>
                    <div style={{ fontSize: "13px", fontWeight: 750, color: "#f8fafc", margin: "2px 0" }}>
                      {sensorComparison.asmaeMean !== null ? `${(sensorComparison.asmaeMean * 100).toFixed(1)}%${sensorComparison.asmaeSigma !== null ? ` ± ${(sensorComparison.asmaeSigma * 100).toFixed(1)}%` : ""}` : "N/A"}
                    </div>
                    <div style={{ fontSize: "9px", color: "#94a3b8" }}>ASMAE root_zone_water</div>
                  </div>
                </div>
                <div style={{
                  fontSize: "10px",
                  fontWeight: 700,
                  padding: "3px 6px",
                  borderRadius: "4px",
                  display: "inline-block",
                  background:
                    sensorComparison.comparisonStatus === "COMPARABLE"
                      ? "rgba(52, 211, 153, 0.15)"
                      : sensorComparison.comparisonStatus === "DIVERGENT"
                      ? "rgba(251, 146, 60, 0.15)"
                      : "rgba(148, 163, 184, 0.15)",
                  color:
                    sensorComparison.comparisonStatus === "COMPARABLE"
                      ? "#34d399"
                      : sensorComparison.comparisonStatus === "DIVERGENT"
                      ? "#fb923c"
                      : "#94a3b8",
                  border:
                    sensorComparison.comparisonStatus === "COMPARABLE"
                      ? "1px solid rgba(52, 211, 153, 0.3)"
                      : sensorComparison.comparisonStatus === "DIVERGENT"
                      ? "1px solid rgba(251, 146, 60, 0.3)"
                      : "1px solid rgba(148, 163, 184, 0.3)",
                  marginBottom: "6px",
                }}>
                  {sensorComparison.comparisonStatus === "COMPARABLE"
                    ? "✓ Consistent (Within 1σ Envelope)"
                    : sensorComparison.comparisonStatus === "DIVERGENT"
                    ? "⚠ Discrepancy (Outside 1σ)"
                    : "ℹ Not comparable (No posterior uncertainty σ)"}
                </div>
                <p style={{ fontSize: "10px", color: "#cbd5e1", lineHeight: 1.35, margin: "0 0 6px" }}>
                  {sensorComparison.narrative}
                </p>
                <div style={{ fontSize: "8.5px", color: "#64748b", fontStyle: "italic", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "4px" }}>
                  {sensorComparison.supportDifferenceDisclaimer}
                </div>
              </div>
            )}

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
              <span>{ownerDeclared ? "Owner-declared camera coverage" : isFixture ? "Simulated Camera Trap" : "Fixed Field Camera"}</span>
            </div>
            <strong className="pw-info-large">{entityProps.deviceId || selectedEntity.id}</strong>
            <p style={{ margin: "4px 0 10px", fontSize: "12px", color: "#94a3b8" }}>
              {entityProps.vendor || "AgroVision"} · {entityProps.model || "Vision Station"}
            </p>

            <dl className="pw-definition-list" style={{ marginBottom: "12px" }}>
              <div>
                <dt>Camera Status</dt>
                <dd style={{ color: "#c084fc", fontWeight: 600 }}>
                  {ownerDeclared ? "COVERAGE ONLY · LIVE STATUS UNKNOWN" : isFixture ? "DEMO FIXTURE (Standby)" : "ACTIVE STREAM"}
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
                <dd>{entityProps.resolution || (ownerDeclared ? "Not registered" : "4K UHD (3840x2160)")}</dd>
              </div>
              <div>
                <dt>Field of View</dt>
                <dd>{entityProps.fieldOfView || (ownerDeclared ? "Not calibrated" : "120° Wide Angle")}</dd>
              </div>
              {ownerDeclared && <div role="note" style={{color:"#f59e0b",fontSize:"12px",fontWeight:600}}>
                Owner-declared geometry · Not independently verified or scientifically admitted
              </div>}
              {footprintBounds && (
                <div>
                  <dt>Mapped geometry</dt>
                  <dd>{matchedEntity.geometry?.type} · bounds [{footprintBounds.map(v=>v.toFixed(5)).join(", ")}]</dd>
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
              {entityCoords && (
                <div>
                  <dt>Coordinates</dt>
                  <dd>{entityCoords[1].toFixed(5)}°N, {entityCoords[0].toFixed(5)}°E</dd>
                </div>
              )}
              {ownerDeclared && (
                <div>
                  <dt>Revision</dt>
                  <dd style={{ color: "#facc15", fontWeight: 600 }}>Revision {entityProps.revision || 1} · OWNER_DECLARED</dd>
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
                <Camera size={15} /> {ownerDeclared ? "Open evidence workspace" : "View Visual Stream"}
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
              {ownerDeclared && <div role="note" style={{color:"#f59e0b",fontSize:"12px",fontWeight:600}}>
                Owner-declared geometry · Not independently verified or scientifically admitted
              </div>}
              {footprintBounds && (
                <div>
                  <dt>Mapped geometry</dt>
                  <dd>{matchedEntity.geometry?.type} · bounds [{footprintBounds.map(v=>v.toFixed(5)).join(", ")}]</dd>
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
              {ownerDeclared && (
                <div>
                  <dt>Revision</dt>
                  <dd style={{ color: "#facc15", fontWeight: 600 }}>Revision {entityProps.revision || 1} · OWNER_DECLARED</dd>
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
              {ownerDeclared && <div role="note" style={{color:"#f59e0b",fontSize:"12px",fontWeight:600}}>
                Owner-declared geometry · Not independently verified or scientifically admitted
              </div>}
              {footprintBounds && (
                <div>
                  <dt>Mapped geometry</dt>
                  <dd>{matchedEntity.geometry?.type} · bounds [{footprintBounds.map(v=>v.toFixed(5)).join(", ")}]</dd>
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
              {ownerDeclared && (
                <div>
                  <dt>Revision</dt>
                  <dd style={{ color: "#facc15", fontWeight: 600 }}>Revision {entityProps.revision || 1} · OWNER_DECLARED</dd>
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
            {rawPub?.publication_authority && (
              <div>
                <dt>Authority</dt>
                <dd style={{ fontFamily: "monospace", fontSize: "11px", color: rawPub.publication_authority === "DIAGNOSTIC_ONLY" ? "#f59e0b" : "#34d399" }}>
                  {rawPub.publication_authority}
                </dd>
              </div>
            )}
            {(rawPub?.evidence_acquisition_date || rawPub?.evidence_cutoff_at) && (
              <div>
                <dt>Acquisition</dt>
                <dd style={{ fontSize: "11px", color: "#e2e8f0" }}>
                  {rawPub.evidence_acquisition_date || String(rawPub.evidence_cutoff_at).slice(0, 10)}
                </dd>
              </div>
            )}
            {rawPub?.calibration_status && (
              <div>
                <dt>Calibration</dt>
                <dd style={{ fontSize: "11px", color: "#94a3b8" }}>
                  {rawPub.calibration_status}
                </dd>
              </div>
            )}
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

          {/* W1 Complete ASMAE 13-State Latent Laboratory Card */}
          <div
            className="pw-asmae-lab-card"
            data-testid="p07-asmae-lab-inspector-card"
            style={{
              marginTop: "1.25rem",
              background: "rgba(16, 24, 39, 0.7)",
              border: "1px solid rgba(52, 211, 153, 0.25)",
              borderRadius: "10px",
              padding: "12px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <FlaskConical size={15} style={{ color: "#34d399" }} aria-hidden="true" />
                <span style={{ fontSize: "11px", fontWeight: 800, letterSpacing: "0.05em", color: "#34d399", textTransform: "uppercase" }}>
                  ASMAE Latent Laboratory
                </span>
              </div>
              {/* Farmer / Expert Toggle */}
              <div style={{ display: "flex", background: "rgba(0,0,0,0.5)", borderRadius: "6px", padding: "2px", border: "1px solid rgba(255,255,255,0.08)" }}>
                <button
                  type="button"
                  data-testid="p07-lab-mode-farmer"
                  onClick={() => setLabViewMode("farmer")}
                  style={{
                    fontSize: "9px",
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: "4px",
                    cursor: "pointer",
                    border: "none",
                    background: labViewMode === "farmer" ? "#34d399" : "transparent",
                    color: labViewMode === "farmer" ? "#0f172a" : "#94a3b8",
                  }}
                >
                  Farmer
                </button>
                <button
                  type="button"
                  data-testid="p07-lab-mode-expert"
                  onClick={() => setLabViewMode("expert")}
                  style={{
                    fontSize: "9px",
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: "4px",
                    cursor: "pointer",
                    border: "none",
                    background: labViewMode === "expert" ? "#34d399" : "transparent",
                    color: labViewMode === "expert" ? "#0f172a" : "#94a3b8",
                  }}
                >
                  Expert
                </button>
              </div>
            </div>

            {/* State selector dropdown */}
            <div style={{ marginBottom: "10px" }}>
              <label htmlFor="p07-asmae-state-select" className="sr-only">Select ASMAE state</label>
              <select
                id="p07-asmae-state-select"
                data-testid="p07-asmae-state-select"
                value={activeAsmaeKey}
                onChange={(e) => onSelectAsmaeState?.(e.target.value as AsmaeStateKey)}
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  borderRadius: "6px",
                  background: "rgba(0, 0, 0, 0.4)",
                  border: "1px solid rgba(52, 211, 153, 0.35)",
                  color: "#f8fafc",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {ASMAE_13_STATE_ORDER.map((sKey) => {
                  const sDef = ASMAE_13_STATE_CATALOG[sKey];
                  return (
                    <option key={sKey} value={sKey} style={{ background: "#0f172a", color: "#f8fafc" }}>
                      #{String(sDef.order).padStart(2, "0")} {sDef.name} ({sDef.shortName})
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Active State Header */}
            <div style={{ margin: "6px 0 10px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <strong style={{ fontSize: "13px", color: "#f8fafc" }}>
                  #{String(activeDef.order).padStart(2, "0")} {activeDef.name}
                </strong>
                <span
                  data-testid="p07-asmae-status-badge"
                  style={{
                    fontSize: "9px",
                    fontWeight: 800,
                    textTransform: "uppercase",
                    padding: "2px 6px",
                    borderRadius: "10px",
                    background: `${activeStatusMeta.color}22`,
                    color: activeStatusMeta.color,
                    border: `1px solid ${activeStatusMeta.color}44`,
                  }}
                >
                  {activeStatusMeta.badge}
                </span>
              </div>
              <p style={{ fontSize: "10.5px", color: "#94a3b8", margin: "2px 0 6px" }}>
                {activeDef.shortName} · Surface: {activeDef.surfaceType}
                {historicalData?.effective_resolution_by_state?.[activeDef.surfaceType] != null
                  ? ` · Eff. Resolution: ${historicalData.effective_resolution_by_state[activeDef.surfaceType]}m`
                  : historicalData?.suppressed_spatial_states?.[activeDef.key]
                    ? ` · Spatial: Withheld (${historicalData.suppressed_spatial_states[activeDef.key].spatial_support || "scalar_only"})`
                    : ""}
              </p>
            </div>

            {/* Content by View Mode */}
            {labViewMode === "farmer" ? (
              <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "8px", padding: "10px", marginBottom: "8px" }}>
                <div style={{ fontSize: "9.5px", color: "#a9c9b5", fontWeight: 700, marginBottom: "4px" }}>
                  FIELD PERSPECTIVE
                </div>
                <div style={{ fontSize: "11.5px", color: "#e2e8f0", fontWeight: 600, marginBottom: "6px" }}>
                  &ldquo;{activeDef.farmerQuestion}&rdquo;
                </div>
                <div style={{ fontSize: "10.5px", color: "#cbd5e1", lineHeight: 1.4 }}>
                  {currentAsmaeAvail.status === "QUALIFIED_SPATIAL" || currentAsmaeAvail.status === "QUALIFIED_RASTER" ? (
                    <span>
                      Qualified multi-spectral satellite raster is active across the field with an average value of{" "}
                      <strong style={{ color: "#34d399" }}>{currentAsmaeAvail.mean} {activeDef.unit}</strong>.
                      Inspect map pixels directly to observe local canopy variation.
                    </span>
                  ) : currentAsmaeAvail.status === "PLOT_ESTIMATE" || currentAsmaeAvail.status === "SCALAR_ONLY" ? (
                    <span>
                      Field-average estimate is <strong style={{ color: "#38bdf8" }}>{currentAsmaeAvail.mean} ± {currentAsmaeAvail.sigma} {activeDef.unit}</strong>.
                      Spatial map is withheld because individual tree-level variance is not certified for this cutoff date.
                    </span>
                  ) : (
                    <span>{currentAsmaeAvail.explanation}</span>
                  )}
                </div>
              </div>
            ) : (
              <dl className="pw-definition-list" style={{ marginBottom: "10px" }}>
                <div>
                  <dt>Posterior Mean (μ)</dt>
                  <dd style={{ color: "#34d399", fontWeight: 750 }}>
                    {currentAsmaeAvail.mean !== null ? `${currentAsmaeAvail.mean} ${activeDef.unit}` : "No Estimate"}
                  </dd>
                </div>
                <div>
                  <dt>Uncertainty (σ)</dt>
                  <dd style={{ color: "#38bdf8", fontWeight: 600 }}>
                    {currentAsmaeAvail.sigma !== null ? `± ${currentAsmaeAvail.sigma} ${activeDef.unit}` : "Undefined"}
                  </dd>
                </div>
                <div>
                  <dt>Physical Range</dt>
                  <dd>[{activeDef.range[0]}, {activeDef.range[1]}] {activeDef.unit}</dd>
                </div>
                <div>
                  <dt>Authority Tier</dt>
                  <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#e2e8f0" }}>
                    {activeDef.authorityCeiling}
                  </dd>
                </div>
                <div>
                  <dt>Identifiability</dt>
                  <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#facc15" }}>
                    {activeDef.identifiabilityClass}
                  </dd>
                </div>
                <div>
                  <dt>Support Class</dt>
                  <dd style={{ fontFamily: "monospace", fontSize: "11px", color: "#a855f7" }}>
                    {currentAsmaeAvail.supportClassification}
                  </dd>
                </div>
                {currentAsmaeAvail.observationEvidence.length > 0 && (
                  <div>
                    <dt>Admitted Sources</dt>
                    <dd style={{ fontSize: "10px", color: "#94a3b8" }}>
                      {currentAsmaeAvail.observationEvidence.join(" · ")}
                    </dd>
                  </div>
                )}
                {rawPub?.evidence_cutoff_at && (
                  <div>
                    <dt>Evidence Cutoff</dt>
                    <dd style={{ fontSize: "10px", color: "#e2e8f0", fontFamily: "monospace" }}>
                      {rawPub.evidence_cutoff_at}
                    </dd>
                  </div>
                )}
              </dl>
            )}

            {/* SIRE Pixel Inspection details if coordinate sampled */}
            {sirePixelHover && (
              <div
                className="pw-sire-pixel-card"
                data-testid="p07-sire-pixel-sample"
                style={{
                  background: "rgba(16, 185, 129, 0.1)",
                  border: "1px solid rgba(52, 211, 153, 0.3)",
                  borderRadius: "8px",
                  padding: "8px 10px",
                  marginTop: "8px",
                }}
              >
                <div style={{ fontSize: "10px", fontWeight: 750, color: "#34d399", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                  SIRE Sampled Pixel
                </div>
                <div style={{ fontSize: "12px", color: "#f1f5f9", margin: "2px 0" }}>
                  Value: <strong style={{ color: "#34d399" }}>{sirePixelHover.value ?? "N/A"}</strong> {activeDef.unit}
                  {sirePixelHover.sigma != null ? <span style={{ color: "#38bdf8", fontSize: "10.5px" }}> ± {sirePixelHover.sigma}</span> : null}
                </div>
                <div style={{ fontSize: "9.5px", color: "#94a3b8" }}>
                  Row {sirePixelHover.row}, Col {sirePixelHover.col} · [{sirePixelHover.coordinate[1].toFixed(5)}°N, {sirePixelHover.coordinate[0].toFixed(5)}°E]
                  {historicalData?.effective_resolution_by_state?.[activeDef.surfaceType] != null
                    ? ` · ${historicalData.effective_resolution_by_state[activeDef.surfaceType]}m adaptive grid`
                    : ""}
                </div>
              </div>
            )}

            <HistoricalIntelligencePanel
              activeAsOfDate={historicalAsOfDate}
              loading={historicalLoading}
              error={historicalError}
              data={historicalData}
              onSelectDate={(d) => onSelectHistoricalDate?.(d)}
              onReturnToLive={() => onReturnHistoricalToLive?.()}
            />
          </div>

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

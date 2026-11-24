"use client";

import { useState } from "react";
import { useParcelAssessment } from "@/hooks/useParcelAssessment";
import { useLayer10 } from "@/hooks/useLayer10";
import { usePlotTelemetry } from "@/hooks/usePlotTelemetry";
import { CheckCircle2, CircleAlert, Clock3, Radio, ChevronDown, History } from "lucide-react";

/**
 * P07: Reduce canvas obstruction without hiding epistemic distinctions.
 * Details remain available explicitly; no telemetry becomes scientific evidence.
 */
export default function WorkspaceScientificStatus() {
  const [expanded, setExpanded] = useState(false);
  const assessment = useParcelAssessment();
  const layer10 = useLayer10();
  const operational = usePlotTelemetry();
  const rawPub = assessment.rawPublication || layer10.data;
  const snapshotId = assessment.assessment?.identity?.snapshotId
    ?? layer10.data?.publication_id ?? null;
  const isReady = assessment.status === "ready" && assessment.isApplicable && Boolean(layer10.data);
  const isHistorical = Boolean(assessment.assessment) && !assessment.isApplicable;
  const waiting = assessment.status === "loading"
    || Boolean(assessment.error && /pending|timeout|waiting|queued/i.test(assessment.error));

  const pubAuth = rawPub?.publication_authority || rawPub?.publicationAuthority || "DIAGNOSTIC_ONLY";
  const isDiagnostic = pubAuth === "DIAGNOSTIC_ONLY";

  const label = isReady
    ? (isDiagnostic ? "Admitted diagnostic publication" : "Canonical publication loaded")
    : isHistorical ? "Historical / scope mismatch"
    : waiting ? "Publication pending"
    : assessment.status === "invalid" ? "Publication validation rejected"
    : "No authorized scientific surface";
  const Icon = isReady ? CheckCircle2 : waiting ? Clock3 : CircleAlert;
  const level = isReady ? "ready" : waiting ? "pending" : "unavailable";

  const acqDate = rawPub?.evidence_acquisition_date
    || (rawPub?.evidence_cutoff_at
        ? new Date(rawPub.evidence_cutoff_at).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
        : null);
  const publishedAt = rawPub?.published_at || rawPub?.publishedAt || null;
  const calibStatus = rawPub?.calibration_status || rawPub?.calibrationStatus || (isDiagnostic ? "uncalibrated_diagnostic" : "calibrated");
  const effRes = rawPub?.effective_resolution || rawPub?.effectiveResolution || "10m native satellite";
  const supportedLayers: string[] = rawPub?.supported_layers
    || rawPub?.supportedLayers
    || rawPub?.raster_availability?.supported_layers
    || [];
  const unsupportedLayers: Array<{ layer: string; reason: string }> = rawPub?.unsupported_layers
    || rawPub?.unsupportedLayers
    || rawPub?.raster_availability?.unsupported_layers
    || [];

  return <div className="pw-p07-status" data-testid="p07-scientific-status" data-level={level}>
    <button type="button" className="pw-p07-status-toggle"
      aria-label={`Scientific and operational status: ${label}. Show details`}
      aria-expanded={expanded} aria-controls="pw-p07-scientific-detail"
      onClick={() => setExpanded(previous => !previous)}>
      <Icon size={15} aria-hidden="true"/>
      <span className="pw-p07-status-label">{isReady ? (isDiagnostic ? "Diagnostic publication" : "Publication available") : "Operational canvas"} · {label}</span>
      <ChevronDown size={14} aria-hidden="true"/>
    </button>
    {expanded && <div className="pw-p07-status-detail" id="pw-p07-scientific-detail">
      <div className="pw-p07-status-row"><Icon size={16} aria-hidden="true"/>
        <div><strong>Publication Status</strong><span>{label} {snapshotId ? `(Snapshot: ${snapshotId})` : "· Snapshot not reported"}</span></div>
      </div>
      <div className="pw-p07-status-row"><Clock3 size={16} aria-hidden="true"/>
        <div><strong>Evidence Acquisition</strong><span>{acqDate || "Unavailable"}</span></div>
      </div>
      {publishedAt && (
        <div className="pw-p07-status-row"><Clock3 size={16} aria-hidden="true"/>
          <div><strong>Publication Timestamp</strong><span>{publishedAt}</span></div>
        </div>
      )}
      <div className="pw-p07-status-row">
        <div><strong>Scientific Authority</strong><span style={{ fontFamily: "monospace" }}>{pubAuth} {isDiagnostic ? "· Diagnostic only (Numerical authority withheld)" : "· Certified"}</span></div>
      </div>
      <div className="pw-p07-status-row">
        <div><strong>Raster Availability</strong><span>{supportedLayers.length > 0 ? `${supportedLayers.length} supported (${supportedLayers.join(", ")})` : "No supported raster"} · Thermal withheld (unobserved)</span></div>
      </div>
      <div className="pw-p07-status-row">
        <div><strong>Effective Resolution</strong><span>{effRes} · 1m field certification withheld</span></div>
      </div>
      <div className="pw-p07-status-row">
        <div><strong>Calibration Status</strong><span>{calibStatus}</span></div>
      </div>
      <div className="pw-p07-status-row"><Radio size={16} aria-hidden="true"/>
        <div><strong>Operational IoT · not scientific evidence</strong>
          <span>{operational.transportStatus} · {operational.stream.observations.length} unsealed observation(s)</span></div>
      </div>
      <p>A loaded publication does not prove that a scientific raster is rendered.
        Pixel-level interpretation requires separate map authorization and provenance.</p>

      {/* Explicit historical snapshot inspection (W2-R13 / Finding 1 & 5) */}
      <div style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
        {snapshotId === "L10-SNAP-MITIDJA-202609081200" ? (
          <div>
            <div style={{ fontSize: "10px", fontWeight: 700, color: "#34d399", marginBottom: "4px" }}>
              Active Historical Audit View (Read-Only)
            </div>
            <div style={{ fontSize: "9px", color: "#cbd5e1", marginBottom: "6px" }}>
              Snapshot L10-SNAP-MITIDJA-202609081200 · Validated empirical cutoff 2026-09-08 12:00:00Z
            </div>
            <button
              type="button"
              style={{
                background: "rgba(255, 255, 255, 0.08)",
                border: "1px solid rgba(255, 255, 255, 0.2)",
                borderRadius: "4px",
                color: "#f8fafc",
                fontSize: "10px",
                padding: "4px 8px",
                cursor: "pointer",
              }}
              onClick={() => {
                if (assessment.plotId && assessment.farmId) {
                  assessment.fetchAssessment(assessment.plotId, assessment.farmId);
                }
              }}
            >
              Return to Live Plot Head
            </button>
          </div>
        ) : (
          <div>
            <div style={{ fontSize: "10px", fontWeight: 700, color: "#38bdf8", marginBottom: "4px" }}>
              Historical Benchmark Snapshot
            </div>
            <button
              type="button"
              className="pw-historical-snapshot-btn"
              data-testid="inspect-historical-snapshot-btn"
              style={{
                background: "rgba(56, 189, 248, 0.12)",
                border: "1px solid rgba(56, 189, 248, 0.3)",
                borderRadius: "4px",
                color: "#38bdf8",
                fontSize: "10px",
                padding: "4px 8px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "4px",
              }}
              onClick={() => {
                if (assessment.plotId && assessment.farmId) {
                  assessment.fetchAssessment(assessment.plotId, assessment.farmId, {
                    snapshotId: "L10-SNAP-MITIDJA-202609081200",
                  });
                }
              }}
            >
              <History size={12} />
              Inspect Historical Benchmark (L10-SNAP-MITIDJA-202609081200)
            </button>
            <p style={{ fontSize: "9px", color: "#94a3b8", margin: "4px 0 0" }}>
              Loads immutable audited publication cutoff 2026-09-08 12:00 UTC (read-only audit view).
            </p>
          </div>
        )}
      </div>
    </div>}
  </div>;
}

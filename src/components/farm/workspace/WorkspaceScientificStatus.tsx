"use client";

import { useState } from "react";
import { useParcelAssessment } from "@/hooks/useParcelAssessment";
import { useLayer10 } from "@/hooks/useLayer10";
import { usePlotTelemetry } from "@/hooks/usePlotTelemetry";
import { CheckCircle2, CircleAlert, Clock3, Radio, ChevronDown } from "lucide-react";

/**
 * P07: Reduce canvas obstruction without hiding epistemic distinctions.
 * Details remain available explicitly; no telemetry becomes scientific evidence.
 */
export default function WorkspaceScientificStatus() {
  const [expanded, setExpanded] = useState(false);
  const assessment = useParcelAssessment();
  const layer10 = useLayer10();
  const operational = usePlotTelemetry();
  const snapshotId = assessment.assessment?.identity?.snapshotId
    ?? layer10.data?.publication_id ?? null;
  const isReady = assessment.status === "ready" && assessment.isApplicable && Boolean(layer10.data);
  const isHistorical = Boolean(assessment.assessment) && !assessment.isApplicable;
  const waiting = assessment.status === "loading"
    || Boolean(assessment.error && /pending|timeout|waiting|queued/i.test(assessment.error));
  const label = isReady ? "Canonical publication loaded"
    : isHistorical ? "Historical / scope mismatch"
    : waiting ? "Publication pending"
    : assessment.status === "invalid" ? "Publication validation rejected"
    : "No authorized scientific surface";
  const Icon = isReady ? CheckCircle2 : waiting ? Clock3 : CircleAlert;
  const level = isReady ? "ready" : waiting ? "pending" : "unavailable";

  return <div className="pw-p07-status" data-testid="p07-scientific-status" data-level={level}>
    <button type="button" className="pw-p07-status-toggle"
      aria-label={`Scientific and operational status: ${label}. Show details`}
      aria-expanded={expanded} aria-controls="pw-p07-scientific-detail"
      onClick={() => setExpanded(previous => !previous)}>
      <Icon size={15} aria-hidden="true"/>
      <span className="pw-p07-status-label">{isReady ? "Publication available" : "Operational canvas"} · {label}</span>
      <ChevronDown size={14} aria-hidden="true"/>
    </button>
    {expanded && <div className="pw-p07-status-detail" id="pw-p07-scientific-detail">
      <div className="pw-p07-status-row"><Icon size={16} aria-hidden="true"/>
        <div><strong>{label}</strong><span>{snapshotId ? `Snapshot: ${snapshotId}` : "Snapshot not reported"}</span></div>
      </div>
      <div className="pw-p07-status-row"><Radio size={16} aria-hidden="true"/>
        <div><strong>Operational IoT · not scientific evidence</strong>
          <span>{operational.transportStatus} · {operational.stream.observations.length} unsealed observation(s)</span></div>
      </div>
      <p>A loaded publication does not prove that a scientific raster is rendered.
        Pixel-level interpretation requires separate map authorization and provenance.</p>
    </div>}
  </div>;
}

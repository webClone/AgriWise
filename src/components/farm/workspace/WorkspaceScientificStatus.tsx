"use client";

import { useParcelAssessment } from "@/hooks/useParcelAssessment";
import { useLayer10 } from "@/hooks/useLayer10";
import { usePlotTelemetry } from "@/hooks/usePlotTelemetry";
import { CheckCircle2, CircleAlert, Clock3, Radio } from "lucide-react";

export default function WorkspaceScientificStatus() {
  const assessment = useParcelAssessment();
  const layer10 = useLayer10();
  const operational = usePlotTelemetry();
  const snapshotId = assessment.assessment?.identity?.snapshotId
    ?? layer10.data?.publication_id
    ?? null;

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

  return (
    <div className="pw-trust-strip" aria-label="Scientific publication and live telemetry status">
      <div className="pw-trust-item" data-level={level}>
        <Icon size={16} aria-hidden="true" />
        <div>
          <strong>{label}</strong>
          <span>{snapshotId ? `Snapshot: ${snapshotId}` : "Snapshot not reported"}</span>
        </div>
      </div>
      <div className="pw-trust-item" data-level="telemetry">
        <Radio size={16} aria-hidden="true" />
        <div>
          <strong>Operational IoT · not scientific evidence</strong>
          <span>
            {operational.transportStatus} · {operational.stream.observations.length} unsealed observation(s)
          </span>
        </div>
      </div>
      <p className="pw-trust-footnote">
        A loaded publication does not prove that a scientific raster is rendered.
        The map retains its separate pixel and provenance authorization.
      </p>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useLayer10 } from "@/hooks/useLayer10";
import { useParcelAssessment } from "@/hooks/useParcelAssessment";
import { ChevronLeft, ChevronRight, Focus, Layers3, MapPin, X } from "lucide-react";

export default function WorkspaceContextInspector({
  farmId, plotId, onCollapse,
}: {
  farmId: string;
  plotId: string;
  onCollapse: () => void;
}) {
  const layer10 = useLayer10();
  const parcel = useParcelAssessment();
  const selectedZoneId = layer10.selectedZone;
  const zone = layer10.data?.zones?.find(z => z.zone_id === selectedZoneId) ?? null;
  const snapshotId = parcel.assessment?.identity?.snapshotId
    ?? layer10.data?.publication_id ?? null;
  const sourceValidForPlot = parcel.isApplicable && parcel.status === "ready";
  const analysisUrl = `/farm/${encodeURIComponent(farmId)}/plot/${encodeURIComponent(plotId)}/analysis`;

  return (
    <section className="pw-inspector" aria-label="Context Inspector">
      <header className="pw-inspector-header">
        <div>
          <span className="pw-eyebrow">PLOT INTELLIGENCE</span>
          <h2>Context Inspector</h2>
        </div>
        <button type="button" className="pw-icon-button" onClick={onCollapse}
          title="Collapse inspector" aria-label="Collapse Context Inspector">
          <ChevronRight size={17} className="pw-ltr-icon" aria-hidden="true" />
          <ChevronLeft size={17} className="pw-rtl-icon" aria-hidden="true" />
        </button>
      </header>

      <div className="pw-inspector-content">
        <div className="pw-info-section">
          <div className="pw-section-title"><MapPin size={15} aria-hidden="true" /> Selected location</div>
          {zone ? (
            <>
              <strong className="pw-info-large">{zone.zone_id}</strong>
              <p>Zone geometry originates from the current Layer 10 view. Its
                scientific interpretation depends on the publication shown below.</p>
              <button type="button" className="pw-secondary-button"
                onClick={() => layer10.setSelectedZone(null)}>
                <X size={14} aria-hidden="true" /> Clear zone selection
              </button>
            </>
          ) : (
            <div className="pw-empty-selection">
              <Focus size={25} aria-hidden="true" />
              <strong>No spatial entity selected</strong>
              <span>Select a grounded zone on the map to inspect related scientific context.</span>
            </div>
          )}
        </div>
        <div className="pw-info-section">
          <div className="pw-section-title"><Layers3 size={15} aria-hidden="true" /> Scientific view</div>
          <dl className="pw-definition-list">
            <div><dt>Active lens</dt><dd>{layer10.activeMode}</dd></div>
            <div><dt>Publication</dt><dd title={snapshotId || undefined}>{snapshotId || "Unavailable"}</dd></div>
            <div><dt>Applicability</dt><dd>{sourceValidForPlot ? "Current plot/crop context" : "Not confirmed for current context"}</dd></div>
            <div><dt>Zones available</dt><dd>{layer10.data?.zones.length ?? 0}</dd></div>
          </dl>
          <p className="pw-trust-warning">
            A colored basemap is not evidence of a scientific raster. Inspect
            the map's authorized pixel legend and source receipt before interpretation.
          </p>
        </div>
        <div className="pw-info-section">
          <div className="pw-section-title">Related tools</div>
          <Link className="pw-primary-link" href={analysisUrl}>
            Open AgriBrain analysis
          </Link>
          <p>Full 13-state laboratory and cross-tool entity selection are scheduled
            for P03–P07; this inspector does not create unverified correlations.</p>
        </div>
      </div>
    </section>
  );
}

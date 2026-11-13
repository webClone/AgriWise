"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Clock3 } from "lucide-react";
import TimelineStrip from "@/components/farm/intelligence/TimelineStrip";

/**
 * P02 layout host for the existing evidence-aware timeline. The underlying
 * timeline remains the existing source-aware component until P13 introduces
 * global history/correlation selection.
 */
export default function WorkspaceTimelineContainer() {
  const [expanded, setExpanded] = useState(true);
  return (
    <section className="pw-timeline-slot" aria-label="Time and field evidence">
      <div className="pw-timeline-heading">
        <div>
          <Clock3 size={16} aria-hidden="true" />
          <strong>Time & evidence</strong>
          <span>Observed · operational · forecast — classified separately</span>
        </div>
        <button type="button" className="pw-timeline-toggle"
          aria-expanded={expanded} aria-controls="pw-timeline-inner"
          onClick={() => setExpanded(open => !open)}>
          {expanded ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronUp size={16} aria-hidden="true" />}
          {expanded ? "Collapse" : "Expand"}
        </button>
      </div>
      {expanded && (
        <div id="pw-timeline-inner" className="pw-timeline-inner">
          <TimelineStrip docked />
        </div>
      )}
    </section>
  );
}

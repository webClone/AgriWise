"use client";

import { useMemo } from "react";
import type { ZoneData } from "@/hooks/useLayer10";

interface ZoneNavBarProps {
  zones: ZoneData[];
  selectedZone: string | null;
  onSelectZone: (zoneId: string | null) => void;
  maxVisible?: number;
}

/** Rank-aware zone navigation bar — Field Overview | Zone A | Zone B | … | All Zones */
export default function ZoneNavBar({
  zones,
  selectedZone,
  onSelectZone,
  maxVisible = 5,
}: ZoneNavBarProps) {
  // Sort zones by severity × area_fraction (highest-priority first)
  const rankedZones = useMemo(() => {
    return [...zones]
      .sort((a, b) => {
        const scoreA = (a.severity || 0) * (a.area_fraction || 0);
        const scoreB = (b.severity || 0) * (b.area_fraction || 0);
        return scoreB - scoreA;
      })
      .slice(0, maxVisible);
  }, [zones, maxVisible]);

  if (zones.length === 0) return null;

  const isFieldOverview = selectedZone === null;

  return (
    <nav
      className="zone-nav-bar"
      id="zone-nav-bar"
      role="tablist"
      aria-label="Zone navigation"
    >
      {/* Field Overview — deselect all zones */}
      <button
        role="tab"
        aria-selected={isFieldOverview}
        onClick={() => onSelectZone(null)}
        className={`zone-nav-tab ${isFieldOverview ? "zone-nav-tab--active" : ""}`}
        id="zone-nav-overview"
      >
        <svg className="w-3 h-3 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M3 9h18M9 21V9" />
        </svg>
        <span>Field Overview</span>
      </button>

      {/* Divider */}
      <div className="zone-nav-divider" />

      {/* Individual ranked zones */}
      {rankedZones.map((zone, idx) => {
        const isActive = selectedZone === zone.zone_id;
        const severityPct = Math.round((zone.severity || 0) * 100);
        const label = zone.label || zone.zone_type?.replace(/_/g, " ") || `Zone ${idx + 1}`;

        return (
          <button
            key={zone.zone_id}
            role="tab"
            aria-selected={isActive}
            onClick={() => onSelectZone(isActive ? null : zone.zone_id)}
            className={`zone-nav-tab ${isActive ? "zone-nav-tab--active" : ""}`}
            id={`zone-nav-${zone.zone_id}`}
            title={`${label} — Severity ${severityPct}%, ${Math.round(zone.area_fraction * 100)}% of field`}
          >
            {/* Rank badge */}
            <span className="zone-nav-rank">{idx + 1}</span>
            <span className="zone-nav-label">{label}</span>
            {/* Severity micro-indicator */}
            <span
              className="zone-nav-severity"
              style={{
                backgroundColor:
                  severityPct > 70 ? "#ef4444" : severityPct > 40 ? "#eab308" : "#22c55e",
              }}
            />
          </button>
        );
      })}

      {/* Show "All Zones" only when there are more zones than maxVisible, or always as a convenience */}
      {zones.length > 1 && (
        <>
          <div className="zone-nav-divider" />
          <button
            role="tab"
            aria-selected={false}
            onClick={() => {
              // Toggle: if a zone is selected, deselect to show all; 
              // could be extended to a multi-select "all zones" highlight mode.
              onSelectZone(null);
            }}
            className="zone-nav-tab zone-nav-tab--all"
            id="zone-nav-all"
          >
            <svg className="w-3 h-3 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="3" />
              <circle cx="12" cy="12" r="7" />
              <circle cx="12" cy="12" r="10" />
            </svg>
            <span>All Zones</span>
            <span className="zone-nav-count">{zones.length}</span>
          </button>
        </>
      )}
    </nav>
  );
}

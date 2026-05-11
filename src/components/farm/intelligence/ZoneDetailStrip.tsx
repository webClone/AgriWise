"use client";

/**
 * ZoneDetailStrip — Horizontal zone detail bar above the timeline.
 * 
 * Replaces the old right-side ZoneSheet that hid everything else.
 * Shows zone name, severity, confidence, condition, drivers, and action
 * in a compact horizontal layout.
 */

import { useMemo } from "react";
import { Brain, X, MapPin, Shield, TrendingDown, Zap } from "lucide-react";
import type { ZoneData } from "@/hooks/useLayer10";
import {
  generateZoneCondition,
  humanizeZoneName,
  humanizeConfidence,
  humanizeAction,
  humanizeDriver,
} from "./fieldInsightAdapter";

interface ZoneDetailStripProps {
  zone: ZoneData | null;
  allZones: ZoneData[];
  onClose: () => void;
  onAskAgriBrain?: (query?: string) => void;
}

export default function ZoneDetailStrip({
  zone,
  allZones,
  onClose,
  onAskAgriBrain,
}: ZoneDetailStripProps) {
  const rankedZones = useMemo(() => {
    return [...allZones]
      .sort((a, b) => (b.severity ?? 0) * (b.area_fraction ?? 0) - (a.severity ?? 0) * (a.area_fraction ?? 0))
      .slice(0, 6);
  }, [allZones]);

  if (!zone) return null;

  const conditionSentence = generateZoneCondition(zone);
  const zoneName = humanizeZoneName(zone, rankedZones.findIndex(z => z.zone_id === zone.zone_id));
  const confidenceLabel = humanizeConfidence(zone.confidence);
  const severityPct = Math.round((zone.severity ?? 0) * 100);
  const severityWord = severityPct > 70 ? "Critical" : severityPct > 40 ? "Moderate" : "Low";
  const severityColor = severityPct > 70 ? "#f87171" : severityPct > 40 ? "#fbbf24" : "#4ade80";
  const areaPct = Math.round((zone.area_fraction ?? 0) * 100);

  const actionText = zone.linked_actions?.length
    ? humanizeAction(zone.linked_actions[0])
    : "No immediate intervention required.";

  const drivers = (zone.top_drivers || []).slice(0, 3);

  return (
    <div
      style={{
        position: "absolute",
        bottom: "170px",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 25,
        width: "100%",
        maxWidth: "860px",
        padding: "0 12px",
        boxSizing: "border-box",
        pointerEvents: "auto",
      }}
    >
      <div
        style={{
          background: "rgba(15, 23, 42, 0.45)",
          backdropFilter: "blur(32px)",
          WebkitBackdropFilter: "blur(32px)",
          border: "1px solid rgba(255, 255, 255, 0.12)",
          borderRadius: "14px",
          overflow: "hidden",
          boxShadow: "0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)",
        }}
        id="zone-detail-strip"
      >
        {/* Top row: Zone name + severity + close */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            padding: "10px 16px 8px",
            borderBottom: "1px solid rgba(71, 85, 105, 0.12)",
          }}
        >
          {/* Severity indicator */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "3px 10px",
              borderRadius: "20px",
              background: `${severityColor}12`,
              border: `1px solid ${severityColor}30`,
            }}
          >
            <div
              style={{
                width: "6px", height: "6px", borderRadius: "50%",
                background: severityColor,
                boxShadow: `0 0 6px ${severityColor}60`,
              }}
            />
            <span style={{ fontSize: "0.68rem", fontWeight: 700, color: severityColor, letterSpacing: "0.06em", textTransform: "uppercase" }}>
              {severityWord}
            </span>
          </div>

          {/* Zone name */}
          <span style={{ fontSize: "0.88rem", fontWeight: 700, color: "#f1f5f9", letterSpacing: "0.01em" }}>
            {zoneName}
          </span>

          {/* Confidence badge */}
          <span style={{
            fontSize: "0.62rem", fontWeight: 600, color: "#94a3b8",
            padding: "2px 8px", borderRadius: "10px",
            background: "rgba(71, 85, 105, 0.2)", border: "1px solid rgba(71, 85, 105, 0.15)",
            textTransform: "uppercase", letterSpacing: "0.08em",
          }}>
            {confidenceLabel}
          </span>

          {/* Spacer */}
          <div style={{ flex: 1 }} />

          {/* Ask AgriBrain */}
          {onAskAgriBrain && (
            <button
              onClick={() => onAskAgriBrain(`I need advice regarding the ${zoneName}. ${conditionSentence}`)}
              style={{
                display: "flex", alignItems: "center", gap: "6px",
                padding: "5px 14px", borderRadius: "8px",
                background: "rgba(99, 102, 241, 0.12)", border: "1px solid rgba(99, 102, 241, 0.25)",
                color: "#a5b4fc", fontSize: "0.72rem", fontWeight: 600,
                cursor: "pointer", transition: "all 0.15s",
              }}
              onMouseOver={e => e.currentTarget.style.background = "rgba(99, 102, 241, 0.22)"}
              onMouseOut={e => e.currentTarget.style.background = "rgba(99, 102, 241, 0.12)"}
              id="zone-strip-ask-agribrain"
            >
              <Brain size={13} />
              Ask AgriBrain
            </button>
          )}

          {/* Close */}
          <button
            onClick={onClose}
            style={{
              width: "26px", height: "26px", borderRadius: "8px",
              background: "rgba(71, 85, 105, 0.15)", border: "none",
              color: "#94a3b8", cursor: "pointer", fontSize: "0.75rem",
              display: "flex", alignItems: "center", justifyContent: "center",
              transition: "all 0.15s",
            }}
            onMouseOver={e => e.currentTarget.style.background = "rgba(71, 85, 105, 0.3)"}
            onMouseOut={e => e.currentTarget.style.background = "rgba(71, 85, 105, 0.15)"}
            aria-label="Close zone detail"
          >
            <X size={14} />
          </button>
        </div>

        {/* Bottom row: Condition + Stats + Drivers + Action */}
        <div
          style={{
            display: "flex",
            alignItems: "stretch",
            gap: "1px",
            padding: "0",
          }}
        >
          {/* Condition sentence */}
          <div style={{
            flex: "1 1 auto",
            padding: "10px 16px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            minWidth: 0,
          }}>
            <p style={{
              fontSize: "0.78rem", color: "#cbd5e1",
              lineHeight: 1.45, margin: 0,
              overflow: "hidden",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical" as const,
            }}>
              {conditionSentence}
            </p>
          </div>

          {/* Stat cards */}
          <div style={{
            display: "flex", gap: "2px",
            padding: "8px 4px",
            flexShrink: 0,
          }}>
            {/* Area */}
            <div style={{
              padding: "6px 12px", borderRadius: "8px",
              background: "rgba(0,0,0,0.25)", border: "1px solid rgba(71,85,105,0.1)",
              display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
              minWidth: "52px",
            }}>
              <MapPin size={11} color="#94a3b8" />
              <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#f1f5f9" }}>{areaPct}%</span>
              <span style={{ fontSize: "0.55rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>Area</span>
            </div>

            {/* Severity */}
            <div style={{
              padding: "6px 12px", borderRadius: "8px",
              background: "rgba(0,0,0,0.25)", border: "1px solid rgba(71,85,105,0.1)",
              display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
              minWidth: "52px",
            }}>
              <TrendingDown size={11} color={severityColor} />
              <span style={{ fontSize: "0.82rem", fontWeight: 700, color: severityColor }}>{severityPct}</span>
              <span style={{ fontSize: "0.55rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>Severity</span>
            </div>

            {/* Confidence */}
            <div style={{
              padding: "6px 12px", borderRadius: "8px",
              background: "rgba(0,0,0,0.25)", border: "1px solid rgba(71,85,105,0.1)",
              display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
              minWidth: "52px",
            }}>
              <Shield size={11} color="#60a5fa" />
              <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#f1f5f9" }}>{Math.round((zone.confidence ?? 0) * 100)}%</span>
              <span style={{ fontSize: "0.55rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>Conf</span>
            </div>
          </div>

          {/* Drivers + Action */}
          <div style={{
            padding: "8px 16px 8px 12px",
            display: "flex", flexDirection: "column",
            justifyContent: "center", gap: "4px",
            borderLeft: "1px solid rgba(71,85,105,0.1)",
            minWidth: "200px", maxWidth: "260px",
            flexShrink: 0,
          }}>
            {/* Drivers */}
            {drivers.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                {drivers.map((d, i) => (
                  <span key={i} style={{
                    fontSize: "0.62rem", fontWeight: 600, color: "#94a3b8",
                    padding: "1px 6px", borderRadius: "4px",
                    background: "rgba(71,85,105,0.15)", border: "1px solid rgba(71,85,105,0.1)",
                  }}>
                    {humanizeDriver(d)}
                  </span>
                ))}
              </div>
            )}

            {/* Action */}
            <div style={{
              display: "flex", alignItems: "center", gap: "5px",
              fontSize: "0.72rem", color: "#a5b4fc", fontWeight: 500,
              lineHeight: 1.3,
            }}>
              <Zap size={10} color="#a5b4fc" style={{ flexShrink: 0 }} />
              <span style={{
                overflow: "hidden",
                display: "-webkit-box",
                WebkitLineClamp: 1,
                WebkitBoxOrient: "vertical" as const,
              }}>
                {actionText}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

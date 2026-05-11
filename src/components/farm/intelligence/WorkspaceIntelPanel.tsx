"use client";

import { useMemo } from "react";
import type { Layer10Result, ExplainabilityPack, HistogramData, DeltaHistogramData, ZoneData } from "@/hooks/useLayer10";

interface Props {
  data: Layer10Result | null;
  activeMode: string;
  activeSurfaceType: string;
  activePack: ExplainabilityPack | undefined;
}

/* ── Micro SVG: Confidence Arc ─────────────────────────────────── */
function ConfidenceArc({ score, size = 72 }: { score: number; size?: number }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - score * circ;
  const color = score >= 0.8 ? "#4ade80" : score >= 0.5 ? "#fbbf24" : "#f87171";
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="transparent" stroke="rgba(71,85,105,0.2)" strokeWidth="5" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="transparent" stroke={color} strokeWidth="5"
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 0.8s ease" }} />
    </svg>
  );
}

/* ── Mini Histogram SVG ────────────────────────────────────────── */
function MiniHistogram({ histogram, colors }: { histogram: HistogramData; colors: [string, string, string] }) {
  const max = Math.max(...histogram.bin_counts, 1);
  const n = histogram.bin_counts.length;
  const barW = 100 / n;

  function lerp(t: number): string {
    const hex = (r: number, g: number, b: number) => `rgb(${r},${g},${b})`;
    const parse = (h: string) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
    const [lo, mid, hi] = colors.map(parse);
    if (t <= 0.5) { const f = t * 2; return hex(lo[0] + f * (mid[0] - lo[0]), lo[1] + f * (mid[1] - lo[1]), lo[2] + f * (mid[2] - lo[2])); }
    const f = (t - 0.5) * 2; return hex(mid[0] + f * (hi[0] - mid[0]), mid[1] + f * (hi[1] - mid[1]), mid[2] + f * (hi[2] - mid[2]));
  }

  return (
    <svg viewBox="0 0 100 40" style={{ width: "100%", height: "56px", display: "block" }}>
      {histogram.bin_counts.map((c, i) => (
        <rect key={i} x={i * barW} y={40 - (c / max) * 38} width={barW - 0.3} height={(c / max) * 38}
          fill={lerp(i / n)} rx="0.5" opacity="0.85" />
      ))}
    </svg>
  );
}

/* ── Section wrapper ───────────────────────────────────────────── */
function Section({ title, badge, children }: { title: string; badge?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ padding: "16px 20px", borderBottom: "1px solid rgba(99,102,241,0.08)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <span style={{ fontSize: "0.6rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.12em", color: "#64748b" }}>{title}</span>
        {badge}
      </div>
      {children}
    </div>
  );
}

/* ── Stat Chip ─────────────────────────────────────────────────── */
function Chip({ label, value, color = "#e2e8f0" }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(71,85,105,0.12)", borderRadius: "8px", padding: "6px 8px", textAlign: "center" }}>
      <div style={{ fontSize: "0.82rem", fontWeight: 700, fontFamily: "'Inter', monospace", color, lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: "0.55rem", color: "#475569", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", marginTop: "2px" }}>{label}</div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   MAIN PANEL
   ═══════════════════════════════════════════════════════════════════ */
export default function WorkspaceIntelPanel({ data, activeMode, activeSurfaceType, activePack }: Props) {
  const quality = data?.quality;
  const reliability = quality?.reliability_score ?? 0;
  const histogram = data?.histograms?.field?.find(h => h.surface_type === activeSurfaceType) || null;
  const delta = data?.histograms?.delta?.find(d => d.surface_type === activeSurfaceType) || null;
  const zones = data?.zones || [];
  const drivers = activePack?.top_drivers || [];

  // Derive colors from mode
  const colorMap: Record<string, [string, string, string]> = {
    canopy: ["#FF0000", "#FFFF00", "#00CC00"], vegetation: ["#FF0000", "#FFFF00", "#00CC00"],
    water_stress: ["#1a5276", "#f39c12", "#e74c3c"], nutrient_risk: ["#27ae60", "#f1c40f", "#c0392b"],
    composite_risk: ["#2ecc71", "#e67e22", "#e74c3c"], uncertainty: ["#2c3e50", "#8e44ad", "#e74c3c"],
    veg_attention: ["#8B4513", "#F5F5DC", "#228B22"],
  };
  const colors = colorMap[activeMode] || colorMap.canopy;

  // Assimilation sources
  const provSources = activePack?.provenance?.sources || [];
  const assimSources = data?.assimilation?.sources || provSources;

  if (!data) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: "12px", color: "#475569" }}>
        <div style={{ width: "24px", height: "24px", border: "2px solid rgba(99,102,241,0.3)", borderTop: "2px solid #6366f1", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
        <span style={{ fontSize: "0.75rem" }}>Awaiting intelligence stream…</span>
      </div>
    );
  }

  return (
    <div className="custom-scrollbar" style={{ flex: 1, overflowY: "auto", background: "linear-gradient(180deg, rgba(11,16,21,1) 0%, rgba(15,20,35,1) 100%)" }}>

      {/* ══ 1. INTELLIGENCE PULSE ═══════════════════════════════════ */}
      <Section title="Intelligence Pulse" badge={
        <span style={{ fontSize: "0.55rem", padding: "2px 8px", borderRadius: "6px", fontWeight: 700,
          background: reliability >= 0.8 ? "rgba(34,197,94,0.12)" : reliability >= 0.5 ? "rgba(251,191,36,0.12)" : "rgba(248,113,113,0.12)",
          color: reliability >= 0.8 ? "#4ade80" : reliability >= 0.5 ? "#fbbf24" : "#f87171",
          border: `1px solid ${reliability >= 0.8 ? "rgba(34,197,94,0.25)" : reliability >= 0.5 ? "rgba(251,191,36,0.25)" : "rgba(248,113,113,0.25)"}`,
          textTransform: "uppercase", letterSpacing: "0.08em",
        }}>{quality?.degradation_mode || "NORMAL"}</span>
      }>
        <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "12px" }}>
          <div style={{ position: "relative", flexShrink: 0 }}>
            <ConfidenceArc score={reliability} />
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
              <span style={{ fontSize: "1.1rem", fontWeight: 800, color: "#f1f5f9", fontFamily: "monospace" }}>{(reliability * 100).toFixed(0)}</span>
              <span style={{ fontSize: "0.5rem", color: "#64748b", fontWeight: 600 }}>TRUST %</span>
            </div>
          </div>
          <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
            <Chip label="Surfaces" value={String(quality?.surfaces_generated || 0)} />
            <Chip label="Zones" value={String(quality?.zones_generated || 0)} />
            <Chip label="Grid" value={quality?.grid_alignment_ok ? "✓ Synced" : "⚠ Drift"} color={quality?.grid_alignment_ok ? "#4ade80" : "#fbbf24"} />
            <Chip label="Detail" value={quality?.detail_conservation_ok ? "✓ Conserved" : "⚠ Smoothed"} color={quality?.detail_conservation_ok ? "#4ade80" : "#fbbf24"} />
          </div>
        </div>
        {(quality?.warnings?.length ?? 0) > 0 && (
          <div style={{ background: "rgba(251,191,36,0.06)", border: "1px solid rgba(251,191,36,0.15)", borderRadius: "8px", padding: "8px 10px" }}>
            {quality!.warnings.map((w, i) => (
              <div key={i} style={{ fontSize: "0.68rem", color: "#fbbf24", lineHeight: 1.5 }}>⚠ {w}</div>
            ))}
          </div>
        )}
      </Section>

      {/* ══ 2. EVIDENCE WATERFALL ═══════════════════════════════════ */}
      <Section title="Evidence Waterfall" badge={
        <span style={{ fontSize: "0.55rem", color: "#475569" }}>{drivers.length} FACTORS</span>
      }>
        {activePack?.summary && (
          <p style={{ fontSize: "0.72rem", color: "#94a3b8", lineHeight: 1.6, marginBottom: "12px", fontStyle: "italic" }}>
            {activePack.summary}
          </p>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {drivers.map((d: any, i: number) => {
            const isPos = d.role === "positive";
            const isNeg = d.role === "negative";
            const barColor = isPos ? "#4ade80" : isNeg ? "#f87171" : "#fbbf24";
            const barWidth = Math.min(Math.abs(d.value) * 100, 100);
            return (
              <div key={i} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(71,85,105,0.1)", borderRadius: "10px", padding: "10px 12px",
                animation: `fadeInUp 300ms ease ${i * 80}ms both` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "#e2e8f0" }}>{d.name}</span>
                  <span style={{ fontSize: "0.78rem", fontWeight: 800, fontFamily: "monospace", color: barColor }}>{d.formatted_value || d.value?.toFixed(2)}</span>
                </div>
                {/* Impact bar */}
                <div style={{ height: "4px", borderRadius: "2px", background: "rgba(71,85,105,0.15)", overflow: "hidden", marginBottom: "6px" }}>
                  <div style={{ height: "100%", width: `${barWidth}%`, borderRadius: "2px", background: `linear-gradient(90deg, ${barColor}40, ${barColor})`,
                    transition: "width 0.6s ease" }} />
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ fontSize: "0.55rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", padding: "1px 6px", borderRadius: "4px",
                    background: isPos ? "rgba(74,222,128,0.1)" : isNeg ? "rgba(248,113,113,0.1)" : "rgba(251,191,36,0.1)",
                    color: barColor }}>{d.role}</span>
                  {d.description && <span style={{ fontSize: "0.6rem", color: "#475569", lineHeight: 1.3 }}>{d.description}</span>}
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ══ 3. LIVE DISTRIBUTION ════════════════════════════════════ */}
      {histogram && (
        <Section title="Field Distribution" badge={
          delta ? (
            <span style={{ fontSize: "0.55rem", fontWeight: 800, padding: "2px 8px", borderRadius: "6px",
              background: delta.shift_direction === "IMPROVING" ? "rgba(74,222,128,0.1)" : delta.shift_direction === "DEGRADING" ? "rgba(248,113,113,0.1)" : "rgba(71,85,105,0.1)",
              color: delta.shift_direction === "IMPROVING" ? "#4ade80" : delta.shift_direction === "DEGRADING" ? "#f87171" : "#94a3b8",
              border: `1px solid ${delta.shift_direction === "IMPROVING" ? "rgba(74,222,128,0.2)" : delta.shift_direction === "DEGRADING" ? "rgba(248,113,113,0.2)" : "rgba(71,85,105,0.15)"}`,
            }}>{delta.shift_direction === "IMPROVING" ? "↑" : delta.shift_direction === "DEGRADING" ? "↓" : "→"} {delta.shift_direction}</span>
          ) : null
        }>
          <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: "8px", padding: "8px 6px 4px", marginBottom: "8px" }}>
            <MiniHistogram histogram={histogram} colors={colors} />
            <div style={{ display: "flex", justifyContent: "space-between", padding: "0 2px", marginTop: "2px" }}>
              <span style={{ fontSize: "0.5rem", color: "#475569", fontFamily: "monospace" }}>{histogram.bin_edges[0]?.toFixed(2)}</span>
              <span style={{ fontSize: "0.5rem", color: "#475569", fontFamily: "monospace" }}>{histogram.bin_edges[histogram.bin_edges.length - 1]?.toFixed(2)}</span>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "4px" }}>
            <Chip label="Mean" value={histogram.mean.toFixed(3)} color={colors[1]} />
            <Chip label="Std" value={histogram.std.toFixed(3)} />
            <Chip label="P10" value={histogram.p10?.toFixed(3) || "–"} />
            <Chip label="P90" value={histogram.p90?.toFixed(3) || "–"} />
          </div>
          {delta && (
            <div style={{ marginTop: "8px", background: "rgba(255,255,255,0.02)", borderRadius: "8px", padding: "8px 10px", border: "1px solid rgba(71,85,105,0.1)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6rem" }}>
                <span style={{ color: "#64748b" }}>Temporal Δ</span>
                <span style={{ color: "#94a3b8", fontFamily: "monospace" }}>{delta.date_from} → {delta.date_to}</span>
              </div>
              <div style={{ fontSize: "0.78rem", fontWeight: 700, fontFamily: "monospace", marginTop: "4px",
                color: delta.mean_change > 0 ? "#4ade80" : delta.mean_change < 0 ? "#f87171" : "#94a3b8" }}>
                Mean Δ: {delta.mean_change > 0 ? "+" : ""}{delta.mean_change.toFixed(4)}
              </div>
            </div>
          )}
        </Section>
      )}

      {/* ══ 4. ZONE INTELLIGENCE ════════════════════════════════════ */}
      {zones.length > 0 && (
        <Section title="Zone Intelligence" badge={
          <span style={{ fontSize: "0.55rem", color: "#475569" }}>{zones.length} ZONES</span>
        }>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {zones.slice(0, 6).map((z, i) => (
              <div key={z.zone_id} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(71,85,105,0.1)", borderRadius: "10px", padding: "10px 12px",
                animation: `fadeInUp 250ms ease ${i * 60}ms both` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <div style={{ width: "6px", height: "6px", borderRadius: "50%",
                      background: z.severity > 0.7 ? "#f87171" : z.severity > 0.4 ? "#fbbf24" : "#4ade80" }} />
                    <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "#e2e8f0" }}>{z.zone_type.replace(/_/g, " ")}</span>
                  </div>
                  <span style={{ fontSize: "0.55rem", color: "#64748b", fontFamily: "monospace" }}>{(z.area_fraction).toFixed(0)}% area</span>
                </div>
                {/* Severity + Confidence bars */}
                <div style={{ display: "flex", gap: "8px", marginBottom: "6px" }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "0.5rem", color: "#475569", marginBottom: "2px" }}>Severity</div>
                    <div style={{ height: "3px", borderRadius: "2px", background: "rgba(71,85,105,0.15)" }}>
                      <div style={{ height: "100%", width: `${z.severity * 100}%`, borderRadius: "2px",
                        background: z.severity > 0.7 ? "#f87171" : z.severity > 0.4 ? "#fbbf24" : "#4ade80" }} />
                    </div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "0.5rem", color: "#475569", marginBottom: "2px" }}>Confidence</div>
                    <div style={{ height: "3px", borderRadius: "2px", background: "rgba(71,85,105,0.15)" }}>
                      <div style={{ height: "100%", width: `${z.confidence * 100}%`, borderRadius: "2px", background: "#a5b4fc" }} />
                    </div>
                  </div>
                </div>
                {/* Driver tags */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "3px" }}>
                  {z.top_drivers.slice(0, 3).map((d, di) => (
                    <span key={di} style={{ fontSize: "0.5rem", padding: "1px 6px", borderRadius: "4px",
                      background: "rgba(99,102,241,0.08)", color: "#a5b4fc", fontWeight: 600 }}>{d}</span>
                  ))}
                  {z.linked_actions.length > 0 && z.linked_actions.map((a, ai) => (
                    <span key={ai} style={{ fontSize: "0.5rem", padding: "1px 6px", borderRadius: "4px",
                      background: "rgba(34,197,94,0.08)", color: "#4ade80", fontWeight: 600 }}>⚡ {a}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ══ 5. DATA ASSIMILATION ════════════════════════════════════ */}
      <Section title="Data Assimilation" badge={
        <span style={{ fontSize: "0.55rem", color: "#475569" }}>{assimSources.length} SOURCES</span>
      }>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginBottom: "10px" }}>
          {(assimSources.length > 0 ? assimSources : ["Sentinel-2", "Sentinel-1-SAR", "OpenMeteo", "SoilGrids"]).map((src: string, i: number) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "0.65rem", color: "#cbd5e1",
              background: "rgba(0,0,0,0.3)", padding: "4px 10px", borderRadius: "6px", border: "1px solid rgba(71,85,105,0.12)" }}>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>
              {src}
            </div>
          ))}
        </div>
        {/* Coverage bar */}
        <div style={{ marginBottom: "4px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.55rem", color: "#475569", marginBottom: "3px" }}>
            <span>Freshness</span>
            <span style={{ fontFamily: "monospace", color: "#94a3b8" }}>{((quality?.reliability_score ?? 0) * 100).toFixed(0)}%</span>
          </div>
          <div style={{ height: "4px", borderRadius: "2px", background: "rgba(71,85,105,0.15)" }}>
            <div style={{ height: "100%", borderRadius: "2px", width: `${(quality?.reliability_score ?? 0) * 100}%`,
              background: "linear-gradient(90deg, #6366f1, #4ade80)", transition: "width 0.5s ease" }} />
          </div>
        </div>
      </Section>

      {/* ══ 6. MODEL PROVENANCE ═════════════════════════════════════ */}
      {activePack?.provenance && (
        <Section title="Model Provenance" badge={
          <span style={{ fontSize: "0.5rem", padding: "2px 8px", borderRadius: "6px", fontWeight: 700,
            background: "rgba(99,102,241,0.12)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.2)" }}>
            LIVE • {activePack.provenance.model_version}
          </span>
        }>
          {/* Equation */}
          {activePack.equations?.[0] && (
            <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: "8px", padding: "10px 12px", marginBottom: "10px", border: "1px solid rgba(71,85,105,0.08)" }}>
              <div style={{ fontSize: "0.55rem", color: "#475569", marginBottom: "4px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>Core Formulation</div>
              <div style={{ fontFamily: "'Fira Code', 'JetBrains Mono', monospace", fontSize: "0.72rem", color: "#e2e8f0", display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ color: "#6366f1" }}>ƒ(x)</span>
                <span style={{ color: "#475569" }}>=</span>
                <span>{activePack.equations[0].expression}</span>
              </div>
              <div style={{ fontSize: "0.58rem", color: "#64748b", marginTop: "4px", fontStyle: "italic" }}>{activePack.equations[0].plain_language}</div>
            </div>
          )}
          {/* Run metadata */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px" }}>
            <Chip label="Run ID" value={activePack.provenance.run_id?.slice(0, 12) || "—"} />
            <Chip label="Timestamp" value={activePack.provenance.timestamps?.[0]?.slice(11, 19) || "—"} />
          </div>
          {/* Confidence breakdown */}
          {activePack.confidence && (
            <div style={{ marginTop: "8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.6rem", marginBottom: "4px" }}>
                <span style={{ color: "#475569" }}>Model Confidence</span>
                <span style={{ fontFamily: "monospace", fontWeight: 700,
                  color: activePack.confidence.score >= 0.8 ? "#4ade80" : activePack.confidence.score >= 0.5 ? "#fbbf24" : "#f87171" }}>
                  {(activePack.confidence.score * 100).toFixed(0)}%
                </span>
              </div>
              {activePack.confidence.penalties?.map((p: any, i: number) => (
                <div key={i} style={{ fontSize: "0.58rem", color: "#f87171", display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
                  <span>↓ {p.reason}</span>
                  <span style={{ fontFamily: "monospace" }}>-{(p.impact * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          )}
        </Section>
      )}

      {/* ══ 7. HISTORY ══════════════════════════════════════════════ */}
      {(data.history_pack?.length ?? 0) > 0 && (
        <Section title="Field History">
          <div style={{ borderLeft: "1px solid rgba(71,85,105,0.15)", paddingLeft: "12px", display: "flex", flexDirection: "column", gap: "10px" }}>
            {data.history_pack!.slice(0, 4).map((h, i) => (
              <div key={i} style={{ position: "relative" }}>
                <div style={{ position: "absolute", left: "-16px", top: "4px", width: "8px", height: "8px", borderRadius: "50%",
                  background: h.type === "USER_ACTION" ? "#6366f1" : h.type === "SYSTEM" ? "#64748b" : "#4ade80",
                  border: "2px solid #0B1015" }} />
                <div style={{ fontSize: "0.55rem", color: "#475569", fontFamily: "monospace" }}>{h.timestamp?.slice(0, 16)}</div>
                <div style={{ fontSize: "0.68rem", fontWeight: 600, color: "#e2e8f0", marginTop: "2px" }}>{h.title}</div>
                <div style={{ fontSize: "0.6rem", color: "#94a3b8", lineHeight: 1.4 }}>{h.description}</div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Bottom spacer */}
      <div style={{ height: "20px" }} />
    </div>
  );
}

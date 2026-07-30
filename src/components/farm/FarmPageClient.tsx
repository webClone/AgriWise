"use client";

import Link from "next/link";
import ParticleField, { RingChart, AnimatedNumber } from "./FarmVisuals";

interface FarmCardData {
  id: string;
  name: string;
  wilaya: string;
  totalArea: number;
  plots: { id: string; name: string; area: number; cropCycles?: { cropCode: string; status: string }[] }[];
}

export function FarmHeroClient({ farmCount }: { farmCount: number }) {
  return (
    <div style={{ position: "relative", padding: "56px 24px 32px", maxWidth: "1100px", margin: "0 auto", overflow: "hidden" }}>
      <ParticleField color="#4ade8040" count={25} />
      <div style={{ position: "relative", zIndex: 1, display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: "16px", flexWrap: "wrap" }} className="fm-anim">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
            <div className="fm-logo-pulse" style={{ width: "44px", height: "44px", borderRadius: "14px", background: "linear-gradient(135deg, rgba(34,197,94,0.15), rgba(16,185,129,0.08))", border: "1px solid rgba(34,197,94,0.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.2rem", position: "relative" }}>
              🌱
              <div className="fm-logo-ring" />
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: "10px", fontWeight: 800, color: "#4ade80", textTransform: "uppercase", letterSpacing: "0.14em" }}>AgriWise</span>
              <span style={{ fontSize: "9px", color: "#475569", letterSpacing: "0.06em" }}>Satellite Farm Intelligence</span>
            </div>
          </div>
          <h1 style={{ fontSize: "clamp(2.2rem, 5vw, 3.2rem)", fontWeight: 200, margin: 0, lineHeight: 1.1, color: "#f8fafc" }}>
            My <span className="fm-gradient-text" style={{ fontWeight: 800 }}>Farms</span>
          </h1>
          <p style={{ fontSize: "14px", color: "#475569", marginTop: "10px", maxWidth: "460px", lineHeight: 1.65 }}>
            Monitor {farmCount} farm{farmCount !== 1 ? "s" : ""} with satellite-powered crop intelligence, precision analytics, and yield forecasting.
          </p>
        </div>
      </div>
    </div>
  );
}

export function FarmStatsClient({ farms, totalPlots, totalArea, totalCrops }: {
  farms: number; totalPlots: number; totalArea: number; totalCrops: number;
}) {
  const usagePct = totalArea > 0 ? Math.min(100, Math.round((totalArea / (totalArea * 1.2)) * 100)) : 0;
  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px 32px" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
        {[
          { icon: "🏡", value: farms, label: "Farms", color: "#4ade80", sub: "registered" },
          { icon: "📐", value: totalPlots, label: "Plots", color: "#60a5fa", sub: "geo-mapped" },
          { icon: "📏", value: totalArea, label: "Hectares", color: "#c084fc", sub: "total area", decimal: true },
          { icon: "🌾", value: totalCrops, label: "Active Crops", color: "#fbbf24", sub: "this season" },
        ].map((s, i) => (
          <div key={i} className="fm-anim fm-stat-card" style={{
            padding: "20px", borderRadius: "14px",
            background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.1)",
            position: "relative", overflow: "hidden",
            animationDelay: `${0.15 + i * 0.08}s`,
          }}>
            <div style={{ position: "absolute", top: 0, left: "15%", right: "15%", height: "1px", background: `linear-gradient(90deg, transparent, ${s.color}25, transparent)` }} />
            <div className="fm-stat-glow" style={{ position: "absolute", top: "-30px", right: "-20px", width: "80px", height: "80px", borderRadius: "50%", background: `${s.color}06`, filter: "blur(20px)", pointerEvents: "none" }} />
            <div style={{ display: "flex", alignItems: "center", gap: "14px", position: "relative" }}>
              <div style={{ fontSize: "1.5rem", width: "46px", height: "46px", borderRadius: "12px", background: `${s.color}08`, border: `1px solid ${s.color}12`, display: "flex", alignItems: "center", justifyContent: "center" }}>{s.icon}</div>
              <div>
                <AnimatedNumber value={s.value} color={s.color} suffix={s.decimal ? "" : ""} />
                <div style={{ fontSize: "11px", color: "#64748b", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginTop: "3px" }}>{s.label}</div>
                <div style={{ fontSize: "9px", color: "#334155", marginTop: "1px" }}>{s.sub}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function FarmCardClient({ farm, idx }: { farm: FarmCardData; idx: number }) {
  const activeCrops = farm.plots.flatMap(p => p.cropCycles || []).filter(c => c.status === "ACTIVE" || c.status === "GROWING");
  const cropNames = [...new Set(activeCrops.map(c => c.cropCode))].slice(0, 3);
  const areaUsed = farm.plots.reduce((a, p) => a + p.area, 0);
  const usagePct = farm.totalArea > 0 ? Math.min(100, Math.round((areaUsed / farm.totalArea) * 100)) : 0;

  return (
    <Link href={`/farm/${farm.id}`} style={{ textDecoration: "none", color: "inherit" }}>
      <div className="fm-anim fm-farm-card" style={{
        borderRadius: "18px", background: "rgba(15,23,42,0.4)",
        border: "1px solid rgba(71,85,105,0.1)", cursor: "pointer",
        position: "relative", overflow: "hidden",
        animationDelay: `${0.2 + idx * 0.07}s`,
      }}>
        {/* Animated gradient top bar */}
        <div className="fm-card-gradient" style={{ height: "3px" }} />

        <div style={{ padding: "20px 22px 16px" }}>
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
              <div className="fm-farm-icon" style={{
                width: "52px", height: "52px", borderRadius: "16px",
                background: "linear-gradient(135deg, rgba(34,197,94,0.1), rgba(59,130,246,0.05))",
                border: "1px solid rgba(34,197,94,0.1)",
                display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.5rem",
              }}>🌾</div>
              <div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#f1f5f9", margin: 0 }}>{farm.name}</h3>
                <div style={{ display: "flex", alignItems: "center", gap: "4px", marginTop: "3px" }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                  <span style={{ fontSize: "12px", color: "#64748b" }}>{farm.wilaya}</span>
                  <span style={{ fontSize: "10px", color: "#334155" }}>·</span>
                  <span style={{ fontSize: "12px", color: "#4ade80", fontWeight: 700 }}>{farm.totalArea} ha</span>
                </div>
              </div>
            </div>
            <RingChart value={usagePct} size={50} stroke={3} color={usagePct > 80 ? "#4ade80" : "#60a5fa"} />
          </div>

          {/* Badges */}
          <div style={{ display: "flex", gap: "6px", marginBottom: "14px", flexWrap: "wrap" }}>
            <span className="fm-badge" style={{ background: "rgba(59,130,246,0.08)", color: "#60a5fa", borderColor: "rgba(59,130,246,0.12)" }}>
              📐 {farm.plots.length} {farm.plots.length === 1 ? "plot" : "plots"}
            </span>
            {activeCrops.length > 0 && (
              <span className="fm-badge" style={{ background: "rgba(251,191,36,0.06)", color: "#fbbf24", borderColor: "rgba(251,191,36,0.1)" }}>
                🌿 {activeCrops.length} active crop{activeCrops.length !== 1 ? "s" : ""}
              </span>
            )}
            <span className="fm-badge" style={{ background: "rgba(192,132,252,0.06)", color: "#c084fc", borderColor: "rgba(192,132,252,0.1)" }}>
              📏 {areaUsed.toFixed(1)} ha mapped
            </span>
          </div>

          {/* Utilization bar */}
          <div style={{ marginBottom: "14px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "5px" }}>
              <span style={{ fontSize: "9px", color: "#475569", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>Land Utilization</span>
              <span style={{ fontSize: "10px", color: "#94a3b8", fontFamily: "monospace", fontWeight: 600 }}>{areaUsed.toFixed(1)}/{farm.totalArea} ha</span>
            </div>
            <div style={{ height: "5px", borderRadius: "5px", background: "rgba(71,85,105,0.12)", overflow: "hidden" }}>
              <div className="fm-usage-bar" style={{ height: "100%", borderRadius: "5px", width: `${usagePct}%`, background: usagePct > 80 ? "linear-gradient(90deg, #22c55e, #4ade80)" : "linear-gradient(90deg, #3b82f6, #60a5fa)", boxShadow: `0 0 8px ${usagePct > 80 ? "rgba(34,197,94,0.25)" : "rgba(59,130,246,0.25)"}` }} />
            </div>
          </div>

          {/* Plot + Crop chips */}
          <div style={{ display: "flex", gap: "5px", flexWrap: "wrap", alignItems: "center" }}>
            {farm.plots.slice(0, 3).map(plot => (
              <span key={plot.id} className="fm-chip">{plot.name} · {plot.area}ha</span>
            ))}
            {farm.plots.length > 3 && <span style={{ fontSize: "10px", color: "#334155" }}>+{farm.plots.length - 3}</span>}
            {cropNames.length > 0 && (
              <>
                <div style={{ width: "1px", height: "14px", background: "rgba(71,85,105,0.12)", margin: "0 3px" }} />
                {cropNames.map((cn, ci) => (
                  <span key={ci} className="fm-chip" style={{ background: "rgba(34,197,94,0.05)", borderColor: "rgba(34,197,94,0.08)", color: "#4ade80" }}>🌿 {cn}</span>
                ))}
              </>
            )}
          </div>
        </div>

        {/* Hover arrow */}
        <div className="fm-card-arrow">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M9 18l6-6-6-6"/></svg>
        </div>
      </div>
    </Link>
  );
}

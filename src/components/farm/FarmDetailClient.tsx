"use client";

import Link from "next/link";
import ParticleField, { RingChart, AnimatedNumber } from "./FarmVisuals";

interface FarmDetailClientProps {
  farm: { id: string; name: string; wilaya: string; commune?: string | null; totalArea: number; latitude?: number | null; longitude?: number | null; irrigationType?: string | null; soilType?: string | null; waterSource?: string | null };
  plotCount: number;
  activeCrops: number;
  equipmentCount: number;
  mappedArea: number;
}

export function FarmDetailHero({ farm, plotCount, activeCrops, equipmentCount, mappedArea }: FarmDetailClientProps) {
  const usagePct = farm.totalArea > 0 ? Math.min(100, Math.round((mappedArea / farm.totalArea) * 100)) : 0;
  const healthScore = Math.min(100, Math.round(60 + activeCrops * 5 + plotCount * 3));

  return (
    <>
      {/* ── Header with particles ─────────────────────────── */}
      <div style={{ position: "relative", padding: "44px 24px 24px", maxWidth: "1100px", margin: "0 auto", overflow: "hidden" }} suppressHydrationWarning={true}>
        <ParticleField color="#4ade8030" count={20} />
        <div style={{ position: "relative", zIndex: 1 }} className="fd-anim" suppressHydrationWarning={true}>
          <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "16px" }} suppressHydrationWarning={true}>
            <Link href="/farm" className="fd-back-btn" style={{
              width: "44px", height: "44px", borderRadius: "14px",
              background: "rgba(15,23,42,0.6)", border: "1px solid rgba(71,85,105,0.12)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#94a3b8", textDecoration: "none", flexShrink: 0,
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            </Link>
            <div suppressHydrationWarning={true}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }} suppressHydrationWarning={true}>
                <span style={{ fontSize: "10px", fontWeight: 800, color: "#4ade80", textTransform: "uppercase", letterSpacing: "0.12em" }}>Farm Overview</span>
                <div className="fd-live-dot" suppressHydrationWarning={true} />
              </div>
              <h1 style={{ fontSize: "clamp(1.8rem, 4vw, 2.6rem)", fontWeight: 800, margin: 0, lineHeight: 1.1, color: "#f8fafc" }}>{farm.name}</h1>
            </div>
          </div>
          {/* Location + badges */}
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center", marginLeft: "60px" }} suppressHydrationWarning={true}>
            <div style={{ display: "flex", alignItems: "center", gap: "4px", padding: "4px 12px", borderRadius: "8px", background: "rgba(71,85,105,0.08)", border: "1px solid rgba(71,85,105,0.06)" }} suppressHydrationWarning={true}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              <span style={{ fontSize: "11px", color: "#64748b" }}>{farm.commune ? `${farm.commune}, ${farm.wilaya}` : farm.wilaya}</span>
            </div>
            <span style={{ padding: "4px 12px", borderRadius: "8px", fontSize: "11px", fontWeight: 700, background: "rgba(34,197,94,0.08)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.1)" }}>{farm.totalArea} ha</span>
            {farm.latitude && farm.longitude && (
              <span style={{ fontSize: "10px", color: "#334155", fontFamily: "monospace", padding: "4px 10px", borderRadius: "6px", background: "rgba(71,85,105,0.06)" }}>
                {farm.latitude.toFixed(4)}° {farm.longitude.toFixed(4)}°
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Dashboard Strip ────────────────────────────────── */}
      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px 24px" }} suppressHydrationWarning={true}>
        <div className="fd-anim" style={{ animationDelay: "0.1s", display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: "12px", alignItems: "stretch" }} suppressHydrationWarning={true}>
          {/* Key stats */}
          {[
            { icon: "📐", v: plotCount, l: "Plots", c: "#60a5fa", sub: "geo-mapped" },
            { icon: "🌿", v: activeCrops, l: "Active Crops", c: "#fbbf24", sub: "this season" },
            { icon: "🚜", v: equipmentCount, l: "Equipment", c: "#c084fc", sub: "registered" },
          ].map((s, i) => (
            <div key={i} className="fd-stat" style={{
              padding: "18px", borderRadius: "14px",
              background: "rgba(15,23,42,0.45)", border: "1px solid rgba(71,85,105,0.1)",
              position: "relative", overflow: "hidden",
            }} suppressHydrationWarning={true}>
              <div style={{ position: "absolute", top: 0, left: "20%", right: "20%", height: "1px", background: `linear-gradient(90deg, transparent, ${s.c}20, transparent)` }} suppressHydrationWarning={true} />
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }} suppressHydrationWarning={true}>
                <div style={{ fontSize: "1.3rem", width: "42px", height: "42px", borderRadius: "10px", background: `${s.c}08`, border: `1px solid ${s.c}12`, display: "flex", alignItems: "center", justifyContent: "center" }} suppressHydrationWarning={true}>{s.icon}</div>
                <div suppressHydrationWarning={true}>
                  <AnimatedNumber value={s.v} color={s.c} />
                  <div style={{ fontSize: "10px", color: "#64748b", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginTop: "3px" }} suppressHydrationWarning={true}>{s.l}</div>
                  <div style={{ fontSize: "8px", color: "#334155", marginTop: "1px" }} suppressHydrationWarning={true}>{s.sub}</div>
                </div>
              </div>
            </div>
          ))}

          {/* Ring chart panel */}
          <div style={{ padding: "16px 20px", borderRadius: "14px", background: "rgba(15,23,42,0.45)", border: "1px solid rgba(71,85,105,0.1)", display: "flex", alignItems: "center", gap: "16px" }} suppressHydrationWarning={true}>
            <RingChart value={usagePct} size={62} stroke={4} color={usagePct > 80 ? "#4ade80" : "#60a5fa"} label="used" />
            <div suppressHydrationWarning={true}>
              <div style={{ fontSize: "12px", fontWeight: 700, color: "#f1f5f9" }} suppressHydrationWarning={true}>{mappedArea.toFixed(1)} ha</div>
              <div style={{ fontSize: "9px", color: "#64748b", marginTop: "2px" }} suppressHydrationWarning={true}>of {farm.totalArea} ha mapped</div>
              <div style={{ marginTop: "6px", height: "3px", width: "60px", borderRadius: "3px", background: "rgba(71,85,105,0.12)", overflow: "hidden" }} suppressHydrationWarning={true}>
                <div className="fd-bar" style={{ height: "100%", borderRadius: "3px", width: `${usagePct}%`, background: usagePct > 80 ? "#4ade80" : "#60a5fa" }} suppressHydrationWarning={true} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Farm Properties ────────────────────────────────── */}
      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px 24px" }} suppressHydrationWarning={true}>
        <div className="fd-anim" style={{ animationDelay: "0.2s" }} suppressHydrationWarning={true}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }} suppressHydrationWarning={true}>
            <div style={{ width: "3px", height: "14px", borderRadius: "2px", background: "linear-gradient(180deg, #22d3ee, #818cf8)" }} suppressHydrationWarning={true} />
            <span style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.1em" }} suppressHydrationWarning={true}>Farm Properties</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "10px" }} suppressHydrationWarning={true}>
            {[
              { icon: "💧", label: "Irrigation System", value: farm.irrigationType || "Not configured", color: "#22d3ee", configured: !!farm.irrigationType },
              { icon: "🪨", label: "Soil Type", value: farm.soilType || "Not analyzed", color: "#a78bfa", configured: !!farm.soilType },
              { icon: "💦", label: "Water Source", value: farm.waterSource || "Not specified", color: "#60a5fa", configured: !!farm.waterSource },
              { icon: "📍", label: "Region", value: farm.commune ? `${farm.commune}, ${farm.wilaya}` : farm.wilaya, color: "#4ade80", configured: true },
            ].map((p, i) => (
              <div key={i} className="fd-info" style={{
                padding: "18px", borderRadius: "14px",
                background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.08)",
                display: "flex", alignItems: "center", gap: "14px", position: "relative", overflow: "hidden",
              }} suppressHydrationWarning={true}>
                <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "1px", background: `linear-gradient(90deg, ${p.color}10, transparent)` }} suppressHydrationWarning={true} />
                <div style={{ width: "46px", height: "46px", borderRadius: "12px", background: `${p.color}06`, border: `1px solid ${p.color}10`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.4rem", flexShrink: 0 }} suppressHydrationWarning={true}>{p.icon}</div>
                <div style={{ minWidth: 0 }} suppressHydrationWarning={true}>
                  <div style={{ fontSize: "14px", fontWeight: 600, color: "#f1f5f9", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} suppressHydrationWarning={true}>{p.value}</div>
                  <div style={{ fontSize: "10px", color: "#64748b", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginTop: "1px" }} suppressHydrationWarning={true}>{p.label}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: "4px", marginTop: "3px" }} suppressHydrationWarning={true}>
                    <div style={{ width: "5px", height: "5px", borderRadius: "50%", background: p.configured ? "#22c55e" : "#475569" }} suppressHydrationWarning={true} />
                    <span style={{ fontSize: "9px", color: p.configured ? "#4ade80" : "#475569" }} suppressHydrationWarning={true}>{p.configured ? "Configured" : "Needs setup"}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

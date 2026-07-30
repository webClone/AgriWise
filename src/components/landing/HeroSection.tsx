"use client";
import Link from "next/link";
import Image from "next/image";
import { Particles, Reveal, TypeWriter, OrbitRing } from "./LandingPrimitives";
import { ThemeLogo } from "./ThemeLogo";

export default function HeroSection() {
  return (
    <section style={{ position: "relative", paddingTop: "140px", paddingBottom: "80px", overflow: "hidden" }}>
      <Particles n={50} />
      <div style={{ position: "absolute", top: "-20%", left: "-15%", width: "55%", height: "70%", background: "radial-gradient(ellipse, rgba(34,197,94,0.07) 0%, transparent 60%)", pointerEvents: "none" }} />
      <div style={{ position: "absolute", bottom: "-15%", right: "-10%", width: "50%", height: "55%", background: "radial-gradient(ellipse, rgba(99,102,241,0.05) 0%, transparent 60%)", pointerEvents: "none" }} />
      <div style={{ position: "absolute", top: "10%", right: "5%", opacity: 0.12, pointerEvents: "none" }}><OrbitRing size={280} /></div>

      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px", position: "relative", zIndex: 1, textAlign: "center" }}>
        <Reveal>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: "28px" }}>
            <ThemeLogo height={140} />
          </div>
        </Reveal>
        <Reveal delay={0.05}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", padding: "6px 16px", borderRadius: "24px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.15)", color: "#4ade80", marginBottom: "24px" }}>
            <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#22c55e", boxShadow: "0 0 8px #22c55e80", animation: "pulse 2s ease-in-out infinite" }} />
            Satellites · Drones · Sensors · Photos — One Platform
          </div>
        </Reveal>

        <Reveal delay={0.1}>
          <h1 style={{ fontSize: "clamp(2.8rem, 6.5vw, 5rem)", fontWeight: 200, margin: "0 auto 10px", maxWidth: "1050px", lineHeight: 1.05, letterSpacing: "-0.02em" }}>
            Total Field Perception{" "}
            <span className="hp-grad-text" style={{ fontWeight: 800, display: "block" }}>
              <TypeWriter texts={["From Space to Soil", "Satellite Intelligence", "Drone Scouting", "IoT Sensor Fusion", "Photo Ground Truth"]} />
            </span>
          </h1>
        </Reveal>

        <Reveal delay={0.2}>
          <p style={{ fontSize: "clamp(16px, 2vw, 20px)", color: "#64748b", maxWidth: "700px", margin: "16px auto 40px", lineHeight: 1.7 }}>
            AgriWise fuses satellite imagery, drone scans, IoT sensor telemetry, and farmer photo evidence into a unified 10-layer AI engine. See what no single source can reveal alone.
          </p>
        </Reveal>

        <Reveal delay={0.3}>
          <div style={{ display: "flex", gap: "14px", justifyContent: "center", flexWrap: "wrap", marginBottom: "16px" }}>
            <Link href="/farm" className="hp-cta" style={{ padding: "16px 36px", borderRadius: "14px", background: "linear-gradient(135deg, #22c55e, #16a34a)", color: "#fff", fontSize: "17px", fontWeight: 700, textDecoration: "none", position: "relative", overflow: "hidden", boxShadow: "0 4px 30px rgba(34,197,94,0.3), inset 0 1px 0 rgba(255,255,255,0.15)" }}>
              <div className="hp-shimmer" />Open Dashboard →
            </Link>
            <Link href="#perception" style={{ padding: "16px 36px", borderRadius: "14px", background: "rgba(71,85,105,0.08)", border: "1px solid rgba(71,85,105,0.12)", color: "#94a3b8", fontSize: "17px", fontWeight: 600, textDecoration: "none" }} className="hp-cta-ghost">
              See The Stack
            </Link>
          </div>
          <p style={{ fontSize: "12px", color: "#334155" }}>Free · No credit card · Satellites + Drones + Sensors + Photos</p>
        </Reveal>

        {/* ── Perception sources strip ────────────────────────── */}
        <Reveal delay={0.4}>
          <div style={{ display: "flex", justifyContent: "center", gap: "20px", marginTop: "32px", marginBottom: "20px", flexWrap: "wrap" }}>
            {[
              { icon: "🛰️", label: "Sentinel Satellites", sub: "10m / 5-day", color: "#4ade80" },
              { icon: "🚁", label: "Drone Imagery", sub: "2cm / on-demand", color: "#22d3ee" },
              { icon: "📡", label: "IoT Sensors", sub: "Real-time telemetry", color: "#818cf8" },
              { icon: "📸", label: "Photo Evidence", sub: "Ground truth", color: "#fbbf24" },
            ].map((s, i) => (
              <div key={i} className="hp-src-badge" style={{
                display: "flex", alignItems: "center", gap: "10px",
                padding: "10px 18px", borderRadius: "12px",
                background: "rgba(10,15,30,0.85)", border: `1px solid ${s.color}15`,
                backdropFilter: "blur(10px)",
              }}>
                <div style={{ fontSize: "1.2rem" }}>{s.icon}</div>
                <div style={{ textAlign: "left" }}>
                  <div style={{ fontSize: "12px", fontWeight: 700, color: s.color }}>{s.label}</div>
                  <div style={{ fontSize: "9px", color: "#475569" }}>{s.sub}</div>
                </div>
              </div>
            ))}
          </div>
        </Reveal>

        {/* Dashboard screenshot */}
        <Reveal delay={0.55}>
          <div style={{ marginTop: "30px", position: "relative" }}>
            <div className="hp-float" style={{ position: "absolute", top: "8%", left: "-3%", zIndex: 3, padding: "10px 16px", borderRadius: "12px", background: "rgba(10,15,30,0.92)", border: "1px solid rgba(34,197,94,0.12)", backdropFilter: "blur(12px)", animationDelay: "0s" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "rgba(34,197,94,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>🛰️</div>
                <div><div style={{ fontSize: "11px", fontWeight: 700, color: "#4ade80" }}>Sentinel-2 L2A</div><div style={{ fontSize: "8px", color: "#475569" }}>Last scan: 2h ago</div></div>
              </div>
            </div>
            <div className="hp-float" style={{ position: "absolute", top: "20%", right: "-2%", zIndex: 3, padding: "10px 16px", borderRadius: "12px", background: "rgba(10,15,30,0.92)", border: "1px solid rgba(129,140,248,0.12)", backdropFilter: "blur(12px)", animationDelay: "1.5s" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "rgba(129,140,248,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>📡</div>
                <div><div style={{ fontSize: "11px", fontWeight: 700, color: "#818cf8" }}>3 Sensors Online</div><div style={{ fontSize: "8px", color: "#475569" }}>Soil + Weather + Flow</div></div>
              </div>
            </div>
            <div className="hp-float" style={{ position: "absolute", bottom: "18%", left: "4%", zIndex: 3, padding: "10px 16px", borderRadius: "12px", background: "rgba(10,15,30,0.92)", border: "1px solid rgba(251,191,36,0.12)", backdropFilter: "blur(12px)", animationDelay: "3s" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "rgba(251,191,36,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>📸</div>
                <div><div style={{ fontSize: "11px", fontWeight: 700, color: "#fbbf24" }}>12 Photos Tagged</div><div style={{ fontSize: "8px", color: "#475569" }}>GPS-linked evidence</div></div>
              </div>
            </div>
            <div className="hp-float" style={{ position: "absolute", bottom: "12%", right: "3%", zIndex: 3, padding: "10px 16px", borderRadius: "12px", background: "rgba(10,15,30,0.92)", border: "1px solid rgba(34,211,238,0.12)", backdropFilter: "blur(12px)", animationDelay: "4.5s" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "rgba(34,211,238,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>🚁</div>
                <div><div style={{ fontSize: "11px", fontWeight: 700, color: "#22d3ee" }}>Drone Ready</div><div style={{ fontSize: "8px", color: "#475569" }}>Flight plan queued</div></div>
              </div>
            </div>
            <div style={{ borderRadius: "20px", overflow: "hidden", border: "1px solid rgba(71,85,105,0.1)", boxShadow: "0 24px 100px rgba(0,0,0,0.6), 0 0 150px rgba(34,197,94,0.04)" }}>
              <Image src="/landing/hero.jpg" alt="AgriWise Dashboard" width={1200} height={675} style={{ width: "100%", height: "auto", display: "block" }} priority />
              <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, transparent 60%, #050a14 100%)", pointerEvents: "none", borderRadius: "20px" }} />
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

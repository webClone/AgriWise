"use client";

import Link from "next/link";
import HomeNav from "@/components/marketing/HomeNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { Particles, Reveal, OrbitRing } from "@/components/landing/LandingPrimitives";
import AgriBrainVisuals from "@/components/landing/AgriBrainVisuals";
import AgriBrainLayers from "@/components/landing/AgriBrainLayers";
import AgriBrainSurfaces from "@/components/landing/AgriBrainSurfaces";
import AgriBrainTutorial from "@/components/landing/AgriBrainTutorial";
import { ThemeProvider, useTheme } from "@/components/landing/ThemeProvider";
import "@/components/landing/agribrain-theme.css";
import "@/components/marketing/marketing.css";

/* ═══ AgriBrain Deep Technical Page ═════════════════════════════
   Phase 3.5 Bridge Pass:
   - Placed inside LTR marketing boundary
   - Uses HomeNav & MarketingFooter
   - Consistent terminology: 11 Governed Layers (Layer 0–10),
     evidence objects & scientific authority ladder
   - Unsupported claim ("runs in under 30 seconds") removed
   - Deep scientific content & interactive layers preserved
   ═══════════════════════════════════════════════════════════════ */

function AgriBrainContent() {
  const { theme } = useTheme();
  return (
    <div data-theme={theme} style={{ minHeight: "100vh", background: "#050a14", color: "#e2e8f0", fontFamily: "'Inter', system-ui, sans-serif", overflowX: "hidden" }}>
      <HomeNav />

      {/* Hero */}
      <section style={{ position: "relative", paddingTop: "140px", paddingBottom: "80px", overflow: "hidden", textAlign: "center" }}>
        <Particles n={30} color="rgba(129,140,248,0.25)" />
        <div style={{ position: "absolute", top: "8%", right: "8%", opacity: 0.1 }}><OrbitRing size={240} color="#818cf8" /></div>
        <div style={{ maxWidth: "900px", margin: "0 auto", padding: "0 24px", position: "relative", zIndex: 1 }}>
          <Reveal>
            <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", padding: "6px 16px", borderRadius: "24px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(129,140,248,0.08)", border: "1px solid rgba(129,140,248,0.15)", color: "#818cf8", marginBottom: "24px" }}>
              <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#818cf8", boxShadow: "0 0 8px #818cf880" }} />
              Technical Architecture Documentation
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <h1 style={{ fontSize: "clamp(2.5rem, 5.5vw, 4rem)", fontWeight: 200, margin: "0 0 16px", lineHeight: 1.1 }}>
              How <span style={{ fontWeight: 800, background: "linear-gradient(135deg, #818cf8, #c084fc, #e879f9)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>AgriBrain</span> Works
            </h1>
          </Reveal>
          <Reveal delay={0.2}>
            <p style={{ fontSize: "clamp(16px, 2vw, 19px)", color: "#64748b", maxWidth: "680px", margin: "0 auto 32px", lineHeight: 1.7 }}>
              An 11-layer governed intelligence engine. From raw Earth observation and IoT telemetry through physical assimilation, ASMAE reconstruction, and competing agronomic hypotheses — to calibrated decision support with full authority provenance.
            </p>
          </Reveal>
          <Reveal delay={0.3}>
            <div style={{ display: "flex", gap: "16px", justifyContent: "center", flexWrap: "wrap" }}>
              {[
                { l: "11 Governed Layers (L0–L10)", c: "#818cf8" },
                { l: "ASMAE Sub-Grid Reconstruction", c: "#22d3ee" },
                { l: "6-Level Authority Ladder", c: "#fbbf24" },
                { l: "FAO-56 Water Balance Physics", c: "#4ade80" },
                { l: "Plot Worldline Memory", c: "#e879f9" },
              ].map((b, i) => (
                <span key={i} style={{ padding: "6px 14px", borderRadius: "8px", fontSize: "11px", fontWeight: 700, background: `${b.c}08`, border: `1px solid ${b.c}12`, color: b.c }}>{b.l}</span>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* Data flow visual */}
      <section style={{ padding: "0 0 80px" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ padding: "36px", borderRadius: "24px", background: "rgba(15,23,42,0.5)", border: "1px solid rgba(71,85,105,0.08)", overflowX: "auto" }}>
              <div style={{ fontSize: "13px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "24px", textAlign: "center" }}>End-to-End Governed Pipeline</div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", justifyContent: "center", flexWrap: "wrap" }}>
                {[
                  { n: "🛰️ Satellite", c: "#4ade80" }, { n: "📡 Sensors", c: "#818cf8" }, { n: "🚁 Drone", c: "#22d3ee" }, { n: "📸 Photos", c: "#fbbf24" },
                ].map((s, i) => (
                  <span key={i} style={{ padding: "10px 18px", borderRadius: "12px", background: `${s.c}08`, border: `1px solid ${s.c}15`, fontSize: "14px", fontWeight: 700, color: s.c }}>{s.n}</span>
                ))}
                <span style={{ color: "#334155", fontWeight: 800, fontSize: "20px" }}>→</span>
                {["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10"].map((l, i) => (
                  <span key={l} style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                    <span style={{ padding: "6px 10px", borderRadius: "8px", background: "rgba(71,85,105,0.12)", border: "1px solid rgba(71,85,105,0.08)", fontSize: "13px", fontWeight: 800, color: "#94a3b8", fontFamily: "monospace" }}>{l}</span>
                    {i < 10 && <span style={{ color: "#334155", fontSize: "14px" }}>→</span>}
                  </span>
                ))}
                <span style={{ color: "#334155", fontWeight: 800, fontSize: "20px" }}>→</span>
                <span style={{ padding: "10px 18px", borderRadius: "12px", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.15)", fontSize: "15px", fontWeight: 800, color: "#4ade80" }}>🎯 Prescriptions</span>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <AgriBrainVisuals />
      <AgriBrainLayers />
      <AgriBrainSurfaces />
      <AgriBrainTutorial />

      {/* Bottom CTA */}
      <section style={{ padding: "60px 0 100px" }}>
        <div style={{ maxWidth: "800px", margin: "0 auto", padding: "0 24px", textAlign: "center" }}>
          <Reveal>
            <div style={{ padding: "56px 40px", borderRadius: "24px", background: "linear-gradient(135deg, rgba(129,140,248,0.06), rgba(34,197,94,0.04))", border: "1px solid rgba(129,140,248,0.1)", position: "relative", overflow: "hidden" }}>
              <Particles color="rgba(129,140,248,0.12)" n={20} />
              <div style={{ position: "relative", zIndex: 1 }}>
                <h2 style={{ fontSize: "clamp(1.6rem, 3.5vw, 2.4rem)", fontWeight: 200, margin: "0 0 14px" }}>
                  Explore AgriBrain <span style={{ fontWeight: 800, color: "#f8fafc" }}>In Action</span>
                </h2>
                <p style={{ fontSize: "16px", color: "#64748b", maxWidth: "480px", margin: "0 auto 28px", lineHeight: 1.6 }}>
                  Register or select a field plot to observe real-time telemetry, evidence graphs, and layer-by-layer field state reconstructions.
                </p>
                <Link href="/farm/new" style={{ display: "inline-flex", padding: "16px 40px", borderRadius: "14px", background: "linear-gradient(135deg, #22c55e, #16a34a)", color: "#fff", fontSize: "17px", fontWeight: 800, textDecoration: "none", boxShadow: "0 4px 30px rgba(34,197,94,0.3)" }}>Analyze My Field →</Link>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}

export default function AgriBrainPage() {
  return (
    <ThemeProvider>
      <AgriBrainContent />
    </ThemeProvider>
  );
}

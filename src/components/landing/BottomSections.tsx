"use client";
import Link from "next/link";
import { Reveal, Counter, Particles } from "./LandingPrimitives";

const WORKFLOW = [
  { step: "01", title: "Map & Connect", desc: "Draw plot boundaries. Connect IoT sensors. Link drone accounts. Start snapping geo-tagged photos.", icon: "✏️", color: "#4ade80" },
  { step: "02", title: "Multi-Source Capture", desc: "Satellites scan every 5 days. Drones fly on-demand. Sensors stream 24/7. Photos upload from the field.", icon: "🛰️", color: "#22d3ee" },
  { step: "03", title: "AI Fusion Engine", desc: "AgriBrain fuses all 4 perception sources through 10 layers: calibration → anomaly → zones → prescriptions.", icon: "🧠", color: "#818cf8" },
  { step: "04", title: "Precision Action", desc: "Zone-level prescriptions validated by sensor data and photo evidence. Know exactly where, when, and how much.", icon: "🎯", color: "#fbbf24" },
];

const TESTIMONIALS = [
  { name: "Karim B.", role: "Wheat Farmer · Djelfa", quote: "I caught a water stress zone 4 days before my crops showed symptoms. Saved an entire 3-hectare section.", avatar: "👨‍🌾" },
  { name: "Amina T.", role: "Agronomist · Blida", quote: "The zone intelligence maps let me prescribe variable-rate fertilization. My clients saw 15% yield improvement.", avatar: "👩‍🔬" },
  { name: "Youcef M.", role: "Farm Manager · Tiaret", quote: "Having 10-meter resolution maps refreshed every 5 days transformed how I manage 200 hectares.", avatar: "👨‍💼" },
];

export default function BottomSections() {
  return (
    <>
      {/* ═══ HOW IT WORKS ═════════════════════════════════════ */}
      <section id="how" style={{ padding: "110px 0", borderTop: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "64px" }}>
              <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.15)", color: "#fbbf24", marginBottom: "18px" }}>Simple Workflow</div>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3.2rem)", fontWeight: 200, margin: "0 0 14px" }}>
                Four Steps to <span style={{ fontWeight: 800, color: "#f8fafc" }}>Precision Farming</span>
              </h2>
            </div>
          </Reveal>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "14px", position: "relative" }}>
            {/* Connector line */}
            <div style={{ position: "absolute", top: "60px", left: "12.5%", right: "12.5%", height: "2px", background: "linear-gradient(90deg, #4ade80, #22d3ee, #818cf8, #fbbf24)", opacity: 0.15, zIndex: 0 }} />
            {WORKFLOW.map((w, i) => (
              <Reveal key={i} delay={0.05 + i * 0.1}>
                <div className="hp-fcard" style={{ padding: "30px 24px", borderRadius: "16px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.08)", textAlign: "center", position: "relative", zIndex: 1 }}>
                  <div style={{ width: "56px", height: "56px", borderRadius: "16px", background: `${w.color}08`, border: `1px solid ${w.color}12`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.6rem", margin: "0 auto 14px" }}>{w.icon}</div>
                  <div style={{ fontSize: "10px", fontWeight: 800, color: w.color, letterSpacing: "0.15em", marginBottom: "8px" }}>STEP {w.step}</div>
                  <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#f1f5f9", margin: "0 0 8px" }}>{w.title}</h3>
                  <p style={{ fontSize: "13px", color: "#64748b", lineHeight: 1.6, margin: 0 }}>{w.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ TESTIMONIALS ═════════════════════════════════════ */}
      <section style={{ padding: "110px 0", borderTop: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "56px" }}>
              <div style={{ display: "inline-flex", padding: "5px 14px", borderRadius: "20px", fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.15)", color: "#4ade80", marginBottom: "18px" }}>Trusted by Farmers</div>
              <h2 style={{ fontSize: "clamp(2rem, 4.5vw, 3.2rem)", fontWeight: 200, margin: 0 }}>
                Real Results, <span style={{ fontWeight: 800, color: "#f8fafc" }}>Real Fields</span>
              </h2>
            </div>
          </Reveal>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
            {TESTIMONIALS.map((t, i) => (
              <Reveal key={i} delay={0.05 + i * 0.08}>
                <div className="hp-fcard" style={{ padding: "28px", borderRadius: "16px", background: "rgba(15,23,42,0.4)", border: "1px solid rgba(71,85,105,0.08)", height: "100%" }}>
                  <div style={{ fontSize: "24px", color: "#22c55e", marginBottom: "14px" }}>★★★★★</div>
                  <p style={{ fontSize: "14px", color: "#94a3b8", lineHeight: 1.7, margin: "0 0 20px", fontStyle: "italic" }}>&ldquo;{t.quote}&rdquo;</p>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px", borderTop: "1px solid rgba(71,85,105,0.08)", paddingTop: "16px" }}>
                    <div style={{ width: "40px", height: "40px", borderRadius: "12px", background: "rgba(34,197,94,0.08)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.3rem" }}>{t.avatar}</div>
                    <div>
                      <div style={{ fontSize: "13px", fontWeight: 700, color: "#f1f5f9" }}>{t.name}</div>
                      <div style={{ fontSize: "11px", color: "#475569" }}>{t.role}</div>
                    </div>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ COMPARISON TABLE ═════════════════════════════════ */}
      <section style={{ padding: "110px 0", borderTop: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "900px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", marginBottom: "48px" }}>
              <h2 style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)", fontWeight: 200, margin: "0 0 12px" }}>
                Traditional vs <span style={{ fontWeight: 800, color: "#4ade80" }}>AgriWise</span>
              </h2>
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <div style={{ borderRadius: "16px", overflow: "hidden", border: "1px solid rgba(71,85,105,0.1)" }}>
              {[
                ["Monitoring", "Weekly manual scouting", "Daily satellite + drone + sensor fusion"],
                ["Resolution", "Field-level guesswork", "10m satellite + 2cm drone detail"],
                ["Water Stress", "Visible symptoms (too late)", "5-day early detection (SAR + sensors)"],
                ["Drone Scouting", "No integration", "Autonomous flights with zone targeting"],
                ["Sensors", "Standalone data loggers", "Real-time telemetry fused with satellite"],
                ["Ground Truth", "Manual field notes", "GPS-tagged photos with AI analysis"],
                ["Zone Management", "Uniform treatment", "Variable-rate prescriptions per zone"],
                ["Decision Making", "Experience-based intuition", "Multi-source confidence scoring"],
                ["Cost", "Expensive consultants", "Free satellite + affordable sensors"],
              ].map(([label, old, aw], i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "180px 1fr 1fr", borderBottom: i < 5 ? "1px solid rgba(71,85,105,0.06)" : "none" }}>
                  <div style={{ padding: "16px 20px", fontSize: "13px", fontWeight: 700, color: "#94a3b8", background: "rgba(15,23,42,0.5)" }}>{label}</div>
                  <div style={{ padding: "16px 20px", fontSize: "13px", color: "#64748b", background: "rgba(15,23,42,0.3)", borderLeft: "1px solid rgba(71,85,105,0.06)" }}>{old}</div>
                  <div style={{ padding: "16px 20px", fontSize: "13px", color: "#4ade80", fontWeight: 600, background: "rgba(34,197,94,0.03)", borderLeft: "1px solid rgba(71,85,105,0.06)" }}>✓ {aw}</div>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══ METRICS ══════════════════════════════════════════ */}
      <section style={{ padding: "80px 0", borderTop: "1px solid rgba(71,85,105,0.08)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px", textAlign: "center" }}>
            {[
              { v: 15, s: "%", l: "Average Yield Increase", c: "#4ade80" },
              { v: 40, s: "%", l: "Water Savings", c: "#22d3ee" },
              { v: 5, s: "x", l: "Faster Decision Making", c: "#818cf8" },
              { v: 3, s: "x", l: "ROI vs Manual Scouting", c: "#fbbf24" },
            ].map((m, i) => (
              <Reveal key={i} delay={i * 0.08}>
                <div style={{ padding: "32px", borderRadius: "16px", background: "rgba(15,23,42,0.35)", border: "1px solid rgba(71,85,105,0.06)" }}>
                  <div style={{ fontSize: "clamp(2rem, 4vw, 3rem)", fontWeight: 800, color: m.c, lineHeight: 1 }}><Counter end={m.v} suffix={m.s} /></div>
                  <div style={{ fontSize: "12px", color: "#64748b", fontWeight: 600, marginTop: "8px" }}>{m.l}</div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FINAL CTA ════════════════════════════════════════ */}
      <section style={{ padding: "100px 0 120px" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <Reveal>
            <div style={{ textAlign: "center", padding: "72px 48px", borderRadius: "28px", background: "linear-gradient(135deg, rgba(34,197,94,0.06), rgba(59,130,246,0.04), rgba(129,140,248,0.03))", border: "1px solid rgba(34,197,94,0.1)", position: "relative", overflow: "hidden" }}>
              <Particles color="rgba(74,222,128,0.15)" n={25} />
              <div style={{ position: "relative", zIndex: 1 }}>
                <h2 style={{ fontSize: "clamp(2rem, 5vw, 3.2rem)", fontWeight: 200, margin: "0 0 14px" }}>
                  Start Seeing Your Fields in <span className="hp-grad-text" style={{ fontWeight: 800 }}>A New Light</span>
                </h2>
                <p style={{ fontSize: "17px", color: "#64748b", maxWidth: "520px", margin: "0 auto 36px", lineHeight: 1.65 }}>
                  Join farmers across Algeria using satellite intelligence to grow more with less. Free forever — no credit card required.
                </p>
                <Link href="/farm" className="hp-cta" style={{ display: "inline-flex", padding: "18px 48px", borderRadius: "16px", background: "linear-gradient(135deg, #22c55e, #16a34a)", color: "#fff", fontSize: "18px", fontWeight: 800, textDecoration: "none", position: "relative", overflow: "hidden", boxShadow: "0 4px 32px rgba(34,197,94,0.35), inset 0 1px 0 rgba(255,255,255,0.15)" }}>
                  <div className="hp-shimmer" />
                  Launch AgriWise →
                </Link>
                <div style={{ display: "flex", gap: "24px", justifyContent: "center", marginTop: "20px" }}>
                  {["Free forever", "No credit card", "10m resolution"].map((t, i) => (
                    <span key={i} style={{ fontSize: "11px", color: "#475569", display: "flex", alignItems: "center", gap: "4px" }}>
                      <div style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#22c55e" }} />{t}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══ FOOTER ═══════════════════════════════════════════ */}
      <footer style={{ borderTop: "1px solid rgba(71,85,105,0.08)", padding: "48px 0 32px" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: "40px", marginBottom: "40px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                <div style={{ width: "28px", height: "28px", borderRadius: "8px", background: "linear-gradient(135deg, rgba(34,197,94,0.15), rgba(16,185,129,0.08))", border: "1px solid rgba(34,197,94,0.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.8rem" }}>🌱</div>
                <span style={{ fontSize: "15px", fontWeight: 800, color: "#f8fafc" }}>Agri<span style={{ color: "#4ade80" }}>Wise</span></span>
              </div>
              <p style={{ fontSize: "13px", color: "#475569", lineHeight: 1.6, maxWidth: "280px" }}>Satellite-powered precision agriculture. Transforming how Algeria grows food.</p>
            </div>
            <div>
              <h4 style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "14px" }}>Product</h4>
              {["Dashboard", "Farm Manager", "Zone Intelligence", "Drone Control", "Sensor Hub", "Photo Gallery"].map(t => (
                <div key={t} style={{ fontSize: "13px", color: "#475569", marginBottom: "8px", cursor: "pointer" }}>{t}</div>
              ))}
            </div>
            <div>
              <h4 style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "14px" }}>Technology</h4>
              {["Sentinel-2 Optical", "Sentinel-1 SAR", "Drone Multispectral", "IoT LoRa/Cellular", "Photo AI Detection", "Kalman Filtering"].map(t => (
                <div key={t} style={{ fontSize: "13px", color: "#475569", marginBottom: "8px" }}>{t}</div>
              ))}
            </div>
            <div>
              <h4 style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "14px" }}>Company</h4>
              {["About", "Contact", "Privacy", "Terms"].map(t => (
                <div key={t} style={{ fontSize: "13px", color: "#475569", marginBottom: "8px" }}>{t}</div>
              ))}
            </div>
          </div>
          <div style={{ borderTop: "1px solid rgba(71,85,105,0.06)", paddingTop: "20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "11px", color: "#334155" }}>🇩🇿 Built with ❤️ in Algeria · © {new Date().getFullYear()} AgriWise</span>
            <span style={{ fontSize: "11px", color: "#334155" }}>Powered by Sentinel · Copernicus Programme</span>
          </div>
        </div>
      </footer>
    </>
  );
}

"use client";

import Link from "next/link";
import Image from "next/image";
import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";

/* ═══ FarmerAgronomistStory ═══════════════════════════════════
   Two connected stories:
   - Farmer: What changed? → Why? → What should I inspect? → What are my options? → What happened after?
   - Agronomist: Portfolio of farms, anomaly detection, competing hypotheses, evidence collection, recommendations, tasks.
   
   "AgriWise augments farmers and agronomists rather than replacing them."
   ═══════════════════════════════════════════════════════════════ */

export default function FarmerAgronomistStory() {
  return (
    <section
      className="marketing-section"
      id="farmer-agronomist"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <div className="marketing-container">
        {/* ── Header ────────────────────────────────────────── */}
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "64px" }}>
            <div
              className="marketing-section-badge"
              style={{
                background: "var(--field-green-dim)",
                border: "1px solid rgba(74, 222, 128, 0.15)",
                color: "var(--field-green)",
              }}
            >
              Field & Advisory Intelligence
            </div>
            <h2 className="marketing-section-title">
              Augmenting human expertise,{" "}
              <strong>never replacing it</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
              AgriWise gives farmers clear field questions and actionable options, while giving agronomists portfolio-wide anomaly detection and hypothesis testing tools.
            </p>
          </div>
        </Reveal>

        {/* ── Side-by-side: Farmer vs Agronomist ───────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "32px" }}>
          {/* Farmer Card */}
          <Reveal>
            <div
              className="marketing-card"
              style={{
                padding: "32px",
                borderColor: "rgba(74, 222, 128, 0.2)",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
                  <span style={{ fontSize: "1.8rem" }} aria-hidden="true">🌾</span>
                  <div>
                    <h3 style={{ fontSize: "20px", fontWeight: 700, color: "var(--field-green)", margin: 0 }}>
                      The Farmer Experience
                    </h3>
                    <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                      Field-level decision support under real-world constraints
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "12px", margin: "24px 0" }}>
                  {[
                    { step: "1. What changed?", detail: "Clear alert when canopy biomass or soil moisture deviates." },
                    { step: "2. Why?", detail: "AgriBrain isolates weather, irrigation deficit, or pest pressure." },
                    { step: "3. What should I inspect?", detail: "Pinpointed GPS coordinates for field scouting." },
                    { step: "4. What are my options?", detail: "Constrained recommendations with cost & trade-off estimates." },
                    { step: "5. What happened after?", detail: "Post-intervention tracking to confirm crop recovery." },
                  ].map((item, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "12px 14px",
                        borderRadius: "var(--radius-sm)",
                        background: "rgba(74, 222, 128, 0.05)",
                        border: "1px solid rgba(74, 222, 128, 0.1)",
                      }}
                    >
                      <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--field-green)" }}>
                        {item.step}
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
                        {item.detail}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <Link href="/farm/new" className="marketing-cta-primary" style={{ padding: "10px 20px", fontSize: "13px" }}>
                Analyze My Field →
              </Link>
            </div>
          </Reveal>

          {/* Agronomist Card */}
          <Reveal delay={0.1}>
            <div
              className="marketing-card"
              style={{
                padding: "32px",
                borderColor: "rgba(34, 211, 238, 0.2)",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
                  <span style={{ fontSize: "1.8rem" }} aria-hidden="true">🔬</span>
                  <div>
                    <h3 style={{ fontSize: "20px", fontWeight: 700, color: "var(--evidence-observed)", margin: 0 }}>
                      The Agronomist Workspace
                    </h3>
                    <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                      Portfolio management & hypothesis evaluation
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "12px", margin: "24px 0" }}>
                  {[
                    { title: "Portfolio Monitoring", detail: "Track 50+ farms simultaneously with automated anomaly ranking." },
                    { title: "Competing Hypotheses", detail: "Evaluate N-deficiency vs root-rot before issuing advice." },
                    { title: "Targeted Evidence Request", detail: "Request specific photos or soil samples from farmers." },
                    { title: "Prescriptive Protocol", detail: "Issue governed agronomic prescriptions with digital signature." },
                    { title: "Longitudinal Analytics", detail: "Compare treatment effectiveness across seasons and soil types." },
                  ].map((item, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "12px 14px",
                        borderRadius: "var(--radius-sm)",
                        background: "rgba(34, 211, 238, 0.05)",
                        border: "1px solid rgba(34, 211, 238, 0.1)",
                      }}
                    >
                      <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--evidence-observed)" }}>
                        {item.title}
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
                        {item.detail}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <Link href="/farm" className="marketing-cta-secondary" style={{ padding: "10px 20px", fontSize: "13px" }}>
                Open Agronomist Workspace →
              </Link>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

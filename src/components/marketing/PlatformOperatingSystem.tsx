import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";
import Image from "next/image";

/* ═══ PlatformOperatingSystem ══════════════════════════════════
   Shows the connected AgriWise workspace instead of isolated
   feature cards. One unified product view with labeled
   capability areas.
   
   Server component — no client-side interactivity needed.
   ═══════════════════════════════════════════════════════════════ */

const PLATFORM_CAPABILITIES = [
  {
    label: "Field Registry",
    description: "Plot boundaries, soil profiles, crop rotations and ownership.",
    icon: "📍",
    color: "var(--field-green)",
  },
  {
    label: "Crop Cycles",
    description: "Sowing to harvest — phenological tracking with GDD and satellite signatures.",
    icon: "🌱",
    color: "var(--evidence-observed)",
  },
  {
    label: "Evidence Ingestion",
    description: "Satellite, weather, sensor, drone, photo, lab — governed and provenance-tracked.",
    icon: "📡",
    color: "var(--evidence-inferred)",
  },
  {
    label: "Tasks & Interventions",
    description: "Scouting, spraying, irrigation, harvest — scheduled, assigned, tracked.",
    icon: "📋",
    color: "var(--uncertainty-amber)",
  },
  {
    label: "Intervention History",
    description: "What was done, when, where, why — the operational memory of every field.",
    icon: "📜",
    color: "var(--accent-enterprise)",
  },
  {
    label: "Economics & Yield",
    description: "Input costs, yield intervals, profitability analysis, ROI tracking.",
    icon: "📈",
    color: "var(--accent-bank)",
  },
  {
    label: "Reports & Communication",
    description: "Automated field reports, season summaries, stakeholder communications.",
    icon: "📄",
    color: "var(--accent-cooperative)",
  },
  {
    label: "Collaboration & Teams",
    description: "Multi-user workspaces, role-based access, agronomist-farmer interaction.",
    icon: "👥",
    color: "var(--accent-research)",
  },
] as const;

export default function PlatformOperatingSystem() {
  return (
    <section
      className="marketing-section"
      id="platform"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <div className="marketing-container">
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "56px" }}>
            <div className="marketing-section-badge" style={{
              background: "var(--field-green-dim)",
              border: "1px solid rgba(74, 222, 128, 0.15)",
              color: "var(--field-green)",
            }}>
              Operating Platform
            </div>
            <h2 className="marketing-section-title">
              One connected workspace,{" "}
              <strong>not a catalogue of features</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
              AgriWise is not a collection of isolated tools.
              Field registry, evidence, operations, economics and collaboration
              work as a single connected system.
            </p>
          </div>
        </Reveal>

        {/* Dashboard screenshot */}
        <Reveal delay={0.1}>
          <div style={{
            borderRadius: "var(--radius-xl)",
            overflow: "hidden",
            border: "1px solid var(--border-default)",
            boxShadow: "var(--shadow-elevated)",
            marginBottom: "48px",
            position: "relative",
          }}>
            <Image
              src="/landing/hero.jpg"
              alt="AgriWise connected workspace — field monitoring, evidence layers, and operational tools"
              width={1200}
              height={675}
              style={{ width: "100%", height: "auto", display: "block" }}
            />
            <div style={{
              position: "absolute",
              inset: 0,
              background: "linear-gradient(180deg, transparent 50%, var(--surface-base) 100%)",
              pointerEvents: "none",
            }} />
          </div>
        </Reveal>

        {/* Capability grid */}
        <StaggerContainer
          stagger={0.05}
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "12px",
          }}
        >
          {PLATFORM_CAPABILITIES.map((cap) => (
            <StaggerItem key={cap.label}>
              <div className="marketing-card" style={{ padding: "20px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <span style={{ fontSize: "1.2rem" }} aria-hidden="true">{cap.icon}</span>
                  <span style={{
                    fontSize: "14px",
                    fontWeight: 700,
                    color: cap.color,
                  }}>
                    {cap.label}
                  </span>
                </div>
                <p style={{
                  fontSize: "12px",
                  color: "var(--text-muted)",
                  lineHeight: 1.5,
                  margin: 0,
                }}>
                  {cap.description}
                </p>
              </div>
            </StaggerItem>
          ))}
        </StaggerContainer>
      </div>
    </section>
  );
}

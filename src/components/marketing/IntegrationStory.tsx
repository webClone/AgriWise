"use client";

import { useState } from "react";
import Link from "next/link";
import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";
import InstitutionalContactDialog from "./InstitutionalContactDialog";

/* ═══ IntegrationStory ═════════════════════════════════════════
   API & Integration Ecosystem.
   AgriWise as infrastructure: sensors, labs, irrigation controllers, ERP, claims, credit, government data, APIs.
   ═══════════════════════════════════════════════════════════════ */

export default function IntegrationStory() {
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <section
      className="marketing-section"
      id="integrations"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <div className="marketing-container">
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "56px" }}>
            <div
              className="marketing-section-badge"
              style={{
                background: "rgba(148, 163, 184, 0.1)",
                border: "1px solid rgba(148, 163, 184, 0.2)",
                color: "var(--text-secondary)",
              }}
            >
              Infrastructure & API Ecosystem
            </div>
            <h2 className="marketing-section-title">
              Connected to your existing{" "}
              <strong>systems & infrastructure</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
              AgriWise is built as open, interoperable infrastructure. Connect IoT sensors, laboratory LIMS, ERPs, irrigation telemetry, and custom analytical pipelines via REST & GraphQL APIs.
            </p>
          </div>
        </Reveal>

        {/* Integration Nodes Grid */}
        <StaggerContainer stagger={0.05} className="marketing-grid-4" style={{ marginBottom: "40px" }}>
          {[
            { label: "IoT & Soil Probes", detail: "MQTT / HTTP telemetry streams", icon: "📡" },
            { label: "Laboratory LIMS", detail: "Soil & tissue test ingestion", icon: "🧪" },
            { label: "Irrigation Systems", detail: "Flow meter & pivot valve state", icon: "💧" },
            { label: "Corporate ERPs", detail: "SAP, Odoo, Dynamics integration", icon: "💼" },
            { label: "Claims & Underwriting", detail: "Risk API & spatial audit packages", icon: "🛡️" },
            { label: "Government Portals", detail: "Regional GIS & crop inventory feeds", icon: "🏛️" },
            { label: "Drone / UAV Imagery", detail: "Ortho-mosaic & RGB photogrammetry", icon: "🛸" },
            { label: "Webhooks & Events", detail: "Real-time automated workflow triggers", icon: "🔔" },
          ].map((item, i) => (
            <StaggerItem key={i}>
              <div className="marketing-card" style={{ padding: "20px", textAlign: "center" }}>
                <div style={{ fontSize: "1.5rem", marginBottom: "8px" }} aria-hidden="true">{item.icon}</div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-primary)" }}>{item.label}</div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>{item.detail}</div>
              </div>
            </StaggerItem>
          ))}
        </StaggerContainer>

        {/* API CTA Banner */}
        <Reveal>
          <div
            style={{
              padding: "28px 36px",
              borderRadius: "var(--radius-xl)",
              background: "var(--surface-elevated)",
              border: "1px solid var(--border-default)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "16px",
            }}
          >
            <div>
              <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)" }}>
                Building custom agricultural software or analytical models?
              </div>
              <div style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "2px" }}>
                Access AgriBrain evidence graphs, state reconstructions, and risk signals programmatically.
              </div>
            </div>
            <div style={{ display: "flex", gap: "12px" }}>
              <button onClick={() => setDialogOpen(true)} className="marketing-cta-primary" style={{ padding: "10px 20px", fontSize: "13px" }}>
                Build with AgriWise API →
              </button>
              <Link href="/agribrain" className="marketing-cta-ghost" style={{ fontSize: "13px" }}>
                View Architecture
              </Link>
            </div>
          </div>
        </Reveal>

        <InstitutionalContactDialog
          isOpen={dialogOpen}
          onClose={() => setDialogOpen(false)}
          intent="api"
          customTitle="Discuss Developer & Enterprise API Integration"
        />
      </div>
    </section>
  );
}

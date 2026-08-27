"use client";

import { useState } from "react";
import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";
import InstitutionalContactDialog from "./InstitutionalContactDialog";

/* ═══ EnterpriseStory ═════════════════════════════════════════
   Commercial Farm / Farm Enterprise intelligence.
   Multi-field, team allocation, equipment integration, SLAs.
   ═══════════════════════════════════════════════════════════════ */

export default function EnterpriseStory() {
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <section
      className="marketing-section"
      id="enterprise"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <div className="marketing-container">
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "56px" }}>
            <div
              className="marketing-section-badge"
              style={{
                background: "rgba(129, 140, 248, 0.1)",
                border: "1px solid rgba(129, 140, 248, 0.2)",
                color: "var(--accent-enterprise)",
              }}
            >
              Farm Enterprise Infrastructure
            </div>
            <h2 className="marketing-section-title">
              Operational control for{" "}
              <strong>large-scale agricultural enterprises</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
              Coordinate hundreds of fields, multi-disciplinary teams, irrigation networks, equipment fleets, and yield expectations from a single enterprise workspace.
            </p>
          </div>
        </Reveal>

        {/* Enterprise feature grid */}
        <StaggerContainer stagger={0.06} className="marketing-grid-3" style={{ marginBottom: "40px" }}>
          {[
            {
              title: "Multi-Field Operations",
              desc: "Unified view across regional farm clusters, crop rotations, and operational zones.",
              icon: "🏢",
            },
            {
              title: "Team & Role Governance",
              desc: "Granular access controls for farm managers, field operators, agronomists, and executives.",
              icon: "👥",
            },
            {
              title: "IoT & Drone Integration",
              desc: "Direct telemetry ingestion from soil sensors, weather stations, pivots, and UAV flights.",
              icon: "🛸",
            },
            {
              title: "Yield & P50 Economics",
              desc: "Continuous yield distribution modeling with input cost tracking and margin projections.",
              icon: "📈",
            },
            {
              title: "Custom Data API & Export",
              desc: "Programmatic access via REST/GraphQL for integration into corporate ERPs and data lakes.",
              icon: "⚙️",
            },
            {
              title: "Enterprise SLA & Support",
              desc: "Dedicated agronomist account manager, guaranteed satellite latency, and 99.9% uptime SLA.",
              icon: "🛡️",
            },
          ].map((item, i) => (
            <StaggerItem key={i}>
              <div className="marketing-card" style={{ height: "100%", padding: "24px" }}>
                <div style={{ fontSize: "1.6rem", marginBottom: "10px" }} aria-hidden="true">
                  {item.icon}
                </div>
                <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 6px" }}>
                  {item.title}
                </h3>
                <p style={{ fontSize: "13px", color: "var(--text-muted)", lineHeight: 1.5, margin: 0 }}>
                  {item.desc}
                </p>
              </div>
            </StaggerItem>
          ))}
        </StaggerContainer>

        {/* Banner with CTA */}
        <Reveal>
          <div
            style={{
              padding: "32px 40px",
              borderRadius: "var(--radius-xl)",
              background: "linear-gradient(135deg, rgba(129, 140, 248, 0.08), rgba(99, 102, 241, 0.04))",
              border: "1px solid rgba(129, 140, 248, 0.2)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "20px",
            }}
          >
            <div>
              <span className="marketing-illustrative-label" style={{ marginBottom: "8px" }}>
                Illustrative product view
              </span>
              <h3 style={{ fontSize: "20px", fontWeight: 700, color: "var(--text-primary)", margin: "4px 0 0" }}>
                Ready to scale AgriWise across your commercial operations?
              </h3>
            </div>
            <button
              onClick={() => setDialogOpen(true)}
              className="marketing-cta-primary"
              style={{ padding: "12px 28px", fontSize: "14px" }}
            >
              Explore Farm Enterprise →
            </button>
          </div>
        </Reveal>

        <InstitutionalContactDialog
          isOpen={dialogOpen}
          onClose={() => setDialogOpen(false)}
          intent="enterprise"
          customTitle="Discuss Farm Enterprise Intelligence"
        />
      </div>
    </section>
  );
}

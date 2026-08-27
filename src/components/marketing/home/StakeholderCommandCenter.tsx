"use client";

import React, { useState } from "react";
import { AUDIENCES, AUDIENCE_IDS, type AudienceId, type ContactIntent } from "../data/audiences";
import InstitutionalContactDialog from "../InstitutionalContactDialog";
import { User, Stethoscope, Building2, Users, Landmark, ShieldCheck, Globe, Package, TestTube, ArrowRight } from "lucide-react";

/* ═══ AgriWise R2 — StakeholderCommandCenter ═══════════════════
   Unified Stakeholder Command Center.
   A single vertical rail projecting 9 distinct operational views
   over the persistent WebGL SpatialStage.
   ═══════════════════════════════════════════════════════════════ */

const ROLE_ICONS: Record<string, any> = {
  farmer: User,
  agronomist: Stethoscope,
  enterprise: Building2,
  cooperative: Users,
  bank: Landmark,
  insurance: ShieldCheck,
  government: Globe,
  agribusiness: Package,
  research: TestTube,
};

const COMMAND_AUDIENCES = AUDIENCE_IDS.filter((id) => id !== "api");

export default function StakeholderCommandCenter() {
  const [selectedRole, setSelectedRole] = useState<AudienceId>("farmer");
  const [dialogOpen, setDialogOpen] = useState(false);

  const audience = AUDIENCES[selectedRole];
  const Icon = ROLE_ICONS[selectedRole] || User;

  const handleRoleSelect = (roleId: AudienceId) => {
    setSelectedRole(roleId);
  };

  return (
    <section
      id="command-center"
      data-r2-chapter="command-center"
      data-r2-narrative="true"
      style={{
        position: "relative",
        paddingTop: "100px",
        paddingBottom: "100px",
        borderTop: "1px solid var(--border-subtle)",
      }}
    >
      <div className="marketing-container">
        <div style={{ textAlign: "center", marginBottom: "56px" }}>
          <div
            className="marketing-section-badge"
            style={{
              background: "rgba(129, 140, 248, 0.08)",
              border: "1px solid rgba(129, 140, 248, 0.2)",
              color: "var(--accent-enterprise)",
            }}
          >
            Stakeholder Command Center
          </div>
          <h2 className="marketing-section-title">
            One spatial engine,{" "}
            <strong>nine operational projections</strong>
          </h2>
          <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
            Select any role from the vertical rail below to transform the underlying spatial stage and operational intelligence model.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "32px", alignItems: "flex-start" }}>
          {/* Vertical Rail Selector */}
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {COMMAND_AUDIENCES.map((roleId) => {
              const aud = AUDIENCES[roleId];
              const RoleIcon = ROLE_ICONS[roleId] || User;
              const isSelected = selectedRole === roleId;
              return (
                <button
                  key={roleId}
                  onClick={() => handleRoleSelect(roleId)}
                  className="marketing-card"
                  aria-pressed={isSelected}
                  style={{
                    padding: "12px 16px",
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                    textAlign: "left",
                    cursor: "pointer",
                    borderRadius: "var(--radius-md)",
                    borderColor: isSelected ? aud.color : "var(--border-subtle)",
                    background: isSelected ? `${aud.color}15` : "var(--surface-elevated)",
                    color: isSelected ? aud.color : "var(--text-secondary)",
                    fontWeight: isSelected ? 700 : 500,
                  }}
                >
                  <RoleIcon size={18} color={isSelected ? aud.color : "var(--text-muted)"} />
                  <span style={{ fontSize: "14px", flex: 1 }}>{aud.label}</span>
                </button>
              );
            })}
          </div>

          {/* Role Projection Detail Box */}
          <div
            className="marketing-card"
            style={{
              padding: "40px",
              borderRadius: "var(--radius-xl)",
              background: "var(--surface-modal)",
              border: `1px solid ${audience.color}30`,
              boxShadow: "var(--shadow-elevated)",
              position: "relative",
            }}
          >
            <span className="marketing-illustrative-label" style={{ position: "absolute", top: "20px", right: "20px" }}>
              ILLUSTRATIVE PRODUCT VIEW
            </span>

            <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "20px" }}>
              <div
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "12px",
                  background: `${audience.color}15`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon size={24} color={audience.color} />
              </div>
              <div>
                <h3 style={{ fontSize: "24px", fontWeight: 700, color: audience.color, margin: 0 }}>
                  {audience.label} Projection
                </h3>
                <div style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "2px" }}>
                  {audience.tagline}
                </div>
              </div>
            </div>

            <p style={{ fontSize: "15px", color: "var(--text-body)", lineHeight: 1.7, marginBottom: "28px" }}>
              {audience.description}
            </p>

            <div
              style={{
                padding: "16px 20px",
                borderRadius: "var(--radius-md)",
                background: "var(--surface-code)",
                border: "1px solid var(--border-subtle)",
                marginBottom: "28px",
              }}
            >
              <div style={{ fontSize: "10px", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
                Central Operational Question
              </div>
              <div style={{ fontSize: "14px", fontWeight: 600, color: audience.color, fontStyle: "italic" }}>
                "{audience.centralQuestion}"
              </div>
            </div>

            <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
              {audience.primaryAction.type === "route" ? (
                <a href={audience.primaryAction.href} className="marketing-cta-primary" style={{ padding: "12px 28px", fontSize: "14px" }}>
                  {audience.primaryAction.label} <ArrowRight size={16} />
                </a>
              ) : (
                <button onClick={() => setDialogOpen(true)} className="marketing-cta-primary" style={{ padding: "12px 28px", fontSize: "14px" }}>
                  {audience.primaryAction.label} <ArrowRight size={16} />
                </button>
              )}
            </div>
          </div>
        </div>

        <InstitutionalContactDialog
          isOpen={dialogOpen}
          onClose={() => setDialogOpen(false)}
          intent={selectedRole as ContactIntent}
        />
      </div>
    </section>
  );
}

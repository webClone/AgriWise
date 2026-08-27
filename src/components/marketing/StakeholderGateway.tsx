"use client";
import { useState, useCallback } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";
import { AUDIENCES, AUDIENCE_IDS, type AudienceId } from "./data/audiences";

/* ═══ StakeholderGateway ═══════════════════════════════════════
   "What are you trying to understand?"
   
   Interactive persona selector with 9 stakeholder cards.
   Choosing one transforms the product preview and value proposition.
   Uses framer-motion layout transitions for smooth morphing.
   
   Combined with the scale story: Field → Farm → Portfolio → Nation.
   ═══════════════════════════════════════════════════════════════ */

/** Scale levels for the narrative */
const SCALES = [
  { label: "Field", icon: "🌾", description: "One plot, one farmer, one season — understanding what is happening and what to do.", color: "var(--field-green)" },
  { label: "Farm", icon: "🏡", description: "Multiple fields, crop rotations, irrigation, tasks, equipment, economics — operational intelligence.", color: "var(--evidence-observed)" },
  { label: "Portfolio", icon: "📊", description: "Hundreds of farms, institutional monitoring, risk assessment, credit, insurance — aggregate intelligence.", color: "var(--accent-enterprise)" },
  { label: "Nation", icon: "🏛️", description: "Regional and national crop inventory, water governance, food security, drought monitoring — sovereign intelligence.", color: "var(--accent-government)" },
] as const;

/** Show the top 9 audience roles (exclude 'api' from the gateway grid) */
const GATEWAY_AUDIENCES = AUDIENCE_IDS.filter(id => id !== "api");

export default function StakeholderGateway() {
  const [selectedRole, setSelectedRole] = useState<AudienceId | null>(null);
  const prefersReduced = useReducedMotion();

  const handleSelect = useCallback((role: AudienceId) => {
    setSelectedRole((prev) => (prev === role ? null : role));
  }, []);

  const selectedAudience = selectedRole ? AUDIENCES[selectedRole] : null;

  return (
    <section
      className="marketing-section"
      id="solutions"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <div className="marketing-container">
        {/* ── Scale story ──────────────────────────────────── */}
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "64px" }}>
            <div className="marketing-section-badge" style={{
              background: "var(--evidence-observed-dim)",
              border: "1px solid rgba(34, 211, 238, 0.15)",
              color: "var(--evidence-observed)",
            }}>
              One intelligence core, every scale
            </div>
            <h2 className="marketing-section-title">
              From one field to the{" "}
              <strong>entire food system</strong>
            </h2>
          </div>
        </Reveal>

        {/* Scale levels */}
        <StaggerContainer
          stagger={0.08}
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "12px",
            marginBottom: "80px",
          }}
        >
          {SCALES.map((scale) => (
            <StaggerItem key={scale.label}>
              <div
                className="marketing-card"
                style={{ textAlign: "center", padding: "28px 20px" }}
              >
                <div style={{ fontSize: "2rem", marginBottom: "12px" }} aria-hidden="true">
                  {scale.icon}
                </div>
                <div style={{
                  fontSize: "16px",
                  fontWeight: 700,
                  color: scale.color,
                  marginBottom: "8px",
                }}>
                  {scale.label}
                </div>
                <p style={{
                  fontSize: "13px",
                  color: "var(--text-muted)",
                  lineHeight: 1.55,
                  margin: 0,
                }}>
                  {scale.description}
                </p>
              </div>
            </StaggerItem>
          ))}
        </StaggerContainer>

        {/* ── Stakeholder gateway ──────────────────────────── */}
        <Reveal>
          <div style={{ textAlign: "center", marginBottom: "48px" }}>
            <h2 className="marketing-section-title" style={{ fontSize: "clamp(1.6rem, 3.5vw, 2.6rem)" }}>
              What are you trying to <strong>understand?</strong>
            </h2>
            <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
              AgriWise serves different intelligence to each role.
              Select yours to see what matters to you.
            </p>
          </div>
        </Reveal>

        {/* Audience grid */}
        <StaggerContainer
          stagger={0.04}
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: "12px",
            marginBottom: "32px",
          }}
        >
          {GATEWAY_AUDIENCES.map((roleId) => {
            const aud = AUDIENCES[roleId];
            const isSelected = selectedRole === roleId;
            return (
              <StaggerItem key={roleId}>
                <button
                  className={`marketing-card marketing-card--interactive ${isSelected ? "marketing-card--active" : ""}`}
                  onClick={() => handleSelect(roleId)}
                  aria-pressed={isSelected}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    cursor: "pointer",
                    borderColor: isSelected ? aud.color : undefined,
                    boxShadow: isSelected ? `0 0 20px ${aud.color}15` : undefined,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "1.4rem" }} aria-hidden="true">{aud.icon}</span>
                    <span style={{
                      fontSize: "15px",
                      fontWeight: 700,
                      color: isSelected ? aud.color : "var(--text-primary)",
                    }}>
                      {aud.label}
                    </span>
                  </div>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-muted)",
                    lineHeight: 1.5,
                    margin: 0,
                  }}>
                    {aud.tagline}
                  </p>
                </button>
              </StaggerItem>
            );
          })}
        </StaggerContainer>

        {/* Selected role detail panel */}
        <AnimatePresence mode="wait">
          {selectedAudience && (
            <motion.div
              key={selectedRole}
              initial={prefersReduced ? { opacity: 1 } : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={prefersReduced ? { opacity: 1 } : { opacity: 0, y: -8 }}
              transition={{ duration: prefersReduced ? 0 : 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="marketing-card"
              style={{
                padding: "32px",
                borderColor: `${selectedAudience.color}25`,
              }}
            >
              <div style={{ display: "flex", gap: "24px", flexWrap: "wrap" }}>
                {/* Left: description */}
                <div style={{ flex: "1 1 300px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
                    <span style={{ fontSize: "1.6rem" }} aria-hidden="true">{selectedAudience.icon}</span>
                    <h3 style={{
                      fontSize: "20px",
                      fontWeight: 700,
                      color: selectedAudience.color,
                      margin: 0,
                    }}>
                      {selectedAudience.label}
                    </h3>
                  </div>

                  <p style={{
                    fontSize: "14px",
                    color: "var(--text-muted)",
                    lineHeight: 1.7,
                    margin: "0 0 12px",
                  }}>
                    {selectedAudience.description}
                  </p>

                  <div style={{
                    padding: "12px 16px",
                    borderRadius: "var(--radius-sm)",
                    background: `${selectedAudience.color}06`,
                    border: `1px solid ${selectedAudience.color}12`,
                    marginBottom: "20px",
                  }}>
                    <div style={{ fontSize: "10px", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
                      Central Question
                    </div>
                    <div style={{ fontSize: "13px", color: selectedAudience.color, fontWeight: 600, fontStyle: "italic" }}>
                      "{selectedAudience.centralQuestion}"
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                    {selectedAudience.primaryAction.type === "route" ? (
                      <a href={selectedAudience.primaryAction.href} className="marketing-cta-primary" style={{ fontSize: "14px", padding: "10px 24px" }}>
                        {selectedAudience.primaryAction.label}
                      </a>
                    ) : (
                      <button
                        className="marketing-cta-primary"
                        style={{ fontSize: "14px", padding: "10px 24px" }}
                        onClick={() => {
                          /* Will connect to InstitutionalContactDialog in Phase 2 */
                          const section = document.getElementById("cta-constellation");
                          section?.scrollIntoView({ behavior: "smooth" });
                        }}
                      >
                        {selectedAudience.primaryAction.label}
                      </button>
                    )}
                    {selectedAudience.secondaryAction && (
                      selectedAudience.secondaryAction.type === "route" ? (
                        <a href={selectedAudience.secondaryAction.href} className="marketing-cta-ghost" style={{ fontSize: "13px" }}>
                          {selectedAudience.secondaryAction.label}
                        </a>
                      ) : (
                        <button
                          className="marketing-cta-ghost"
                          style={{ fontSize: "13px" }}
                          onClick={() => {
                            const section = document.getElementById("cta-constellation");
                            section?.scrollIntoView({ behavior: "smooth" });
                          }}
                        >
                          {selectedAudience.secondaryAction.label}
                        </button>
                      )
                    )}
                  </div>
                </div>

                {/* Right: evidence types */}
                <div style={{ flex: "0 0 220px" }}>
                  <div style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    color: "var(--text-dim)",
                    textTransform: "uppercase",
                    letterSpacing: "0.1em",
                    marginBottom: "12px",
                  }}>
                    Evidence Sources
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    {selectedAudience.evidence.slice(0, 6).map((eid) => (
                      <div
                        key={eid}
                        style={{
                          padding: "6px 10px",
                          borderRadius: "var(--radius-sm)",
                          background: "var(--surface-code)",
                          border: "1px solid var(--border-subtle)",
                          fontSize: "11px",
                          color: "var(--text-secondary)",
                          fontWeight: 500,
                        }}
                      >
                        {eid.replace(/-/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}

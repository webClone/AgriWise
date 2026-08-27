"use client";
import { useState, useRef } from "react";
import Link from "next/link";
import { motion, useInView, useReducedMotion, AnimatePresence } from "framer-motion";
import { Reveal, StaggerContainer, StaggerItem } from "./motion/Reveal";
import { AGRIBRAIN_VERBS } from "./data/capabilities";
import { EVIDENCE_SOURCES } from "./data/evidence";

/* ═══ AgriBrainStory ═══════════════════════════════════════════
   The central technological reveal.
   
   "Raw agricultural data is not intelligence."
   
   Then evidence enters one by one → AgriBrain forms a governed
   evidence state → the six verbs process it → intelligence emerges.
   
   Does NOT show layer numbers or confidence percentages.
   ═══════════════════════════════════════════════════════════════ */

/** Subset of evidence sources for the flow animation */
const FLOW_EVIDENCE = EVIDENCE_SOURCES.slice(0, 6);

export default function AgriBrainStory() {
  const [activeVerb, setActiveVerb] = useState(0);
  const sectionRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(sectionRef, { once: true, amount: 0.2 });
  const prefersReduced = useReducedMotion();

  return (
    <section
      className="marketing-section"
      id="agribrain"
      ref={sectionRef}
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <div className="marketing-container" style={{ textAlign: "center" }}>
        {/* ── Opening statement ────────────────────────────── */}
        <Reveal>
          <p style={{
            fontSize: "clamp(1.1rem, 2.5vw, 1.4rem)",
            color: "var(--text-muted)",
            fontWeight: 400,
            letterSpacing: "0.01em",
            marginBottom: "8px",
          }}>
            Raw agricultural data is not intelligence.
          </p>
        </Reveal>

        <Reveal delay={0.1}>
          <h2 className="marketing-section-title" style={{ maxWidth: "850px", margin: "0 auto 16px" }}>
            AgriBrain transforms evidence into{" "}
            <strong className="marketing-gradient-text">understanding</strong>
          </h2>
        </Reveal>

        <Reveal delay={0.15}>
          <p className="marketing-section-subtitle" style={{ margin: "0 auto 56px", textAlign: "center" }}>
            Satellite acquisition. Weather record. Soil measurement. Farmer irrigation event.
            Sensor reading. Photograph. AgriBrain governs each source, reconstructs the field,
            notices contradictions, proposes explanations, evaluates actions, and records outcomes.
          </p>
        </Reveal>

        {/* ── Evidence flow animation ─────────────────────── */}
        <Reveal delay={0.2}>
          <div style={{
            padding: "32px",
            borderRadius: "var(--radius-xl)",
            background: "var(--surface-elevated)",
            border: "1px solid var(--border-subtle)",
            marginBottom: "48px",
            overflow: "hidden",
          }}>
            {/* Evidence sources entering */}
            <div style={{ marginBottom: "24px" }}>
              <div style={{
                fontSize: "10px",
                fontWeight: 700,
                color: "var(--text-dim)",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                marginBottom: "16px",
              }}>
                Evidence Enters
              </div>
              <div style={{
                display: "flex",
                justifyContent: "center",
                gap: "12px",
                flexWrap: "wrap",
              }}>
                {FLOW_EVIDENCE.map((source, i) => (
                  <motion.div
                    key={source.id}
                    initial={prefersReduced ? { opacity: 1 } : { opacity: 0, scale: 0.8 }}
                    animate={isInView ? { opacity: 1, scale: 1 } : {}}
                    transition={{
                      delay: prefersReduced ? 0 : 0.3 + i * 0.12,
                      duration: prefersReduced ? 0 : 0.5,
                      ease: [0.16, 1, 0.3, 1],
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "8px 14px",
                      borderRadius: "var(--radius-sm)",
                      background: `${source.color}08`,
                      border: `1px solid ${source.color}18`,
                    }}
                  >
                    <span style={{ fontSize: "0.9rem" }} aria-hidden="true">{source.icon}</span>
                    <span style={{ fontSize: "12px", fontWeight: 600, color: source.color }}>
                      {source.label}
                    </span>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Arrow / flow indicator */}
            <motion.div
              initial={prefersReduced ? { opacity: 1 } : { opacity: 0, scaleY: 0 }}
              animate={isInView ? { opacity: 1, scaleY: 1 } : {}}
              transition={{ delay: prefersReduced ? 0 : 1.0, duration: prefersReduced ? 0 : 0.4 }}
              style={{
                width: "2px",
                height: "40px",
                background: "linear-gradient(180deg, var(--evidence-observed), var(--agribrain-violet))",
                margin: "0 auto 24px",
                borderRadius: "1px",
              }}
            />

            {/* AgriBrain processing */}
            <motion.div
              initial={prefersReduced ? { opacity: 1 } : { opacity: 0, y: 12 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: prefersReduced ? 0 : 1.2, duration: prefersReduced ? 0 : 0.6 }}
              style={{
                padding: "20px 24px",
                borderRadius: "var(--radius-lg)",
                background: "linear-gradient(135deg, rgba(167, 139, 250, 0.06), rgba(129, 140, 248, 0.04))",
                border: "1px solid rgba(167, 139, 250, 0.12)",
                marginBottom: "24px",
              }}
            >
              <div style={{
                fontSize: "13px",
                fontWeight: 700,
                color: "var(--agribrain-violet)",
                marginBottom: "4px",
              }}>
                🧠 AgriBrain
              </div>
              <div style={{
                fontSize: "12px",
                color: "var(--text-muted)",
              }}>
                Source governance · State estimation · Agronomic reasoning · Uncertainty quantification · Outcome learning
              </div>
            </motion.div>

            {/* Arrow out */}
            <motion.div
              initial={prefersReduced ? { opacity: 1 } : { opacity: 0, scaleY: 0 }}
              animate={isInView ? { opacity: 1, scaleY: 1 } : {}}
              transition={{ delay: prefersReduced ? 0 : 1.6, duration: prefersReduced ? 0 : 0.4 }}
              style={{
                width: "2px",
                height: "40px",
                background: "linear-gradient(180deg, var(--agribrain-violet), var(--field-green))",
                margin: "0 auto 24px",
                borderRadius: "1px",
              }}
            />

            {/* Output: Intelligence */}
            <motion.div
              initial={prefersReduced ? { opacity: 1 } : { opacity: 0, y: 12 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: prefersReduced ? 0 : 1.8, duration: prefersReduced ? 0 : 0.6 }}
              style={{
                display: "flex",
                justifyContent: "center",
                gap: "12px",
                flexWrap: "wrap",
              }}
            >
              {["Map", "Alert", "Task", "Report", "Institutional Signal"].map((output, i) => (
                <div
                  key={output}
                  style={{
                    padding: "8px 16px",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--field-green-dim)",
                    border: "1px solid rgba(74, 222, 128, 0.12)",
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "var(--field-green)",
                  }}
                >
                  {output}
                </div>
              ))}
            </motion.div>
          </div>
        </Reveal>

        {/* ── The six verbs ────────────────────────────────── */}
        <Reveal delay={0.1}>
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "5px 14px",
            borderRadius: "24px",
            fontSize: "11px",
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            background: "var(--agribrain-violet-dim)",
            border: "1px solid rgba(167, 139, 250, 0.15)",
            color: "var(--agribrain-violet)",
            marginBottom: "18px",
          }}>
            Six Governed Verbs
          </div>
        </Reveal>

        <Reveal delay={0.15}>
          <h3 style={{
            fontSize: "clamp(1.4rem, 3vw, 2rem)",
            fontWeight: 200,
            margin: "0 0 12px",
            color: "var(--text-primary)",
          }}>
            Evidence → State → Understanding → Decision → Outcome → <strong>Learning</strong>
          </h3>
          <p style={{
            fontSize: "15px",
            color: "var(--text-muted)",
            maxWidth: "600px",
            margin: "0 auto 40px",
            lineHeight: 1.65,
          }}>
            This is the intelligence cycle. Not a pipeline that runs once, but a
            system that learns from every season, every field, every outcome.
          </p>
        </Reveal>

        {/* Verb tabs / cards */}
        <StaggerContainer className="marketing-grid-3" stagger={0.08} style={{ textAlign: "left" }}>
          {AGRIBRAIN_VERBS.map((verb, i) => (
            <StaggerItem key={verb.id}>
              <button
                className={`marketing-card marketing-card--interactive ${activeVerb === i ? "marketing-card--active" : ""}`}
                onClick={() => setActiveVerb(i)}
                aria-pressed={activeVerb === i}
                style={{
                  width: "100%",
                  textAlign: "left",
                  cursor: "pointer",
                  borderColor: activeVerb === i ? verb.color : undefined,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
                  <span style={{ fontSize: "1.2rem" }} aria-hidden="true">{verb.icon}</span>
                  <span style={{
                    fontSize: "15px",
                    fontWeight: 700,
                    color: verb.color,
                  }}>
                    {verb.label}
                  </span>
                </div>
                <p style={{
                  fontSize: "13px",
                  color: "var(--text-muted)",
                  lineHeight: 1.55,
                  margin: "0 0 10px",
                }}>
                  {verb.description}
                </p>
                <div style={{
                  fontSize: "11px",
                  color: "var(--text-dim)",
                  padding: "6px 10px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--surface-code)",
                  border: "1px solid var(--border-subtle)",
                  fontFamily: "var(--font-mono)",
                }}>
                  {verb.transformation}
                </div>
              </button>
            </StaggerItem>
          ))}
        </StaggerContainer>

        {/* CTA to /agribrain */}
        <Reveal delay={0.2}>
          <div style={{ marginTop: "48px" }}>
            <Link href="/agribrain" className="marketing-cta-secondary">
              Explore the full AgriBrain architecture →
            </Link>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

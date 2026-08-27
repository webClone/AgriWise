import React from "react";
import { SCALE_STORY_LAYOUT } from "../../experience/SpatialStage/ScaleStoryLayout";

/* ═══ AgriWise R2 Pass 6 — ScaleChapter ═════════════════════════
   Cinematic Editorial Scale Narrative with Timeline-Synchronized Rail Layout.
   Directly bound to SCALE_STORY_LAYOUT for 1:1 DOM and WebGL alignment.
   ═══════════════════════════════════════════════════════════════ */

export default function ScaleChapter() {
  return (
    <section
      id="scale"
      data-r2-chapter="scale"
      className="r2-scale-sequence"
      data-r2-narrative="true"
      style={{
        minHeight: `${SCALE_STORY_LAYOUT.totalHeightVh}vh`,
        position: "relative",
        paddingTop: "100px",
        paddingBottom: "260px",
      }}
    >
      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        {/* Sequence Intro Header */}
        <div style={{ maxWidth: "620px", marginBottom: "120px" }}>
          <div
            className="marketing-section-badge"
            style={{
              background: "rgba(74, 222, 128, 0.08)",
              border: "1px solid rgba(74, 222, 128, 0.25)",
              color: "var(--field-green)",
              marginBottom: "16px",
            }}
          >
            One Intelligence Core · Five Scales
          </div>

          <h2
            style={{
              fontSize: "clamp(2rem, 3.8vw, 3.2rem)",
              fontWeight: 200,
              lineHeight: 1.15,
              color: "var(--text-primary)",
              margin: "0 0 16px",
            }}
          >
            The spatial system moves from{" "}
            <strong className="marketing-gradient-text" style={{ fontWeight: 800 }}>
              field to sovereign nation
            </strong>
          </h2>
        </div>

        {/* 5 Alternating High-Impact Editorial Shots */}
        <div style={{ display: "flex", flexDirection: "column", gap: "75vh" }}>
          {SCALE_STORY_LAYOUT.stages.map((shot, idx) => {
            const isRight = shot.side === "right";
            const isClimax = shot.isClimax || idx === SCALE_STORY_LAYOUT.stages.length - 1;

            return (
              <div
                id={`shot-${shot.id}`}
                key={shot.id}
                data-r2-stage={shot.id}
                style={{
                  display: "flex",
                  justifyContent: isRight ? "flex-end" : "flex-start",
                  width: "100%",
                }}
              >
                <div
                  style={{
                    maxWidth: "580px",
                    borderLeft: "3px solid #4ade80",
                    paddingLeft: "24px",
                    background: "none",
                    boxShadow: "none",
                  }}
                >
                  {/* Eyebrow & Microtype */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      marginBottom: "12px",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "13px",
                        fontWeight: 800,
                        color: "#4ade80",
                        letterSpacing: "0.1em",
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {shot.num} · {shot.label}
                    </span>
                    <span
                      style={{
                        fontSize: "11px",
                        color: "#64748b",
                        letterSpacing: "0.06em",
                        marginLeft: "auto",
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {shot.micro}
                    </span>
                  </div>

                  {/* Massive Editorial Headline */}
                  <h3
                    style={{
                      fontSize: "clamp(2.2rem, 4vw, 3.4rem)",
                      fontWeight: 700,
                      color: "#f8fafc",
                      margin: "0 0 16px",
                      lineHeight: 1.12,
                      letterSpacing: "-0.02em",
                    }}
                  >
                    {shot.title}
                  </h3>

                  {/* Spatial Climax Mnemonic directly in space (No UI Card Box) */}
                  {isClimax && (
                    <div style={{ marginTop: "40px", paddingTop: "24px", borderTop: "1px solid rgba(74, 222, 128, 0.2)" }}>
                      <div
                        style={{
                          fontSize: "clamp(1.4rem, 2.4vw, 1.9rem)",
                          fontWeight: 800,
                          color: "#ffffff",
                          lineHeight: 1.25,
                          marginBottom: "12px",
                        }}
                      >
                        One intelligence system.
                        <br />
                        Every agricultural scale.
                      </div>
                      <div
                        style={{
                          fontSize: "15px",
                          color: "#22d3ee",
                          fontWeight: 600,
                          letterSpacing: "0.02em",
                        }}
                      >
                        Scale is only useful if the evidence is trustworthy →
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

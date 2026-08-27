"use client";

import React, { useState } from "react";
import { getAsmaeRun } from "@/components/experience/scientific-run/selectors";
import { Microscope, CheckCircle2 } from "lucide-react";

/* ═══ AgriWise R2 Pass 3B — SpatialAsmaeChapter ═════════════════
   10-Step ASMAE Sub-Grid Reconstruction Microscope.
   Operates cleanly with local step selection in DOM HTML mode.
   ═══════════════════════════════════════════════════════════════ */

export default function SpatialAsmaeChapter() {
  const asmae = getAsmaeRun();
  const [activeStepIndex, setActiveStepIndex] = useState(0);

  const steps = asmae.closureSteps;
  const currentStep = steps[activeStepIndex] || steps[0];

  const handleStepSelect = (index: number) => {
    setActiveStepIndex(index);
  };

  return (
    <section
      id="asmae-microscope"
      data-r2-chapter="asmae-microscope"
      data-r2-narrative="true"
      style={{
        position: "relative",
        paddingTop: "120px",
        paddingBottom: "120px",
      }}
    >
      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        <div style={{ maxWidth: "640px", marginBottom: "48px" }}>
          <div
            className="marketing-section-badge"
            style={{
              background: "rgba(74, 222, 128, 0.08)",
              border: "1px solid rgba(74, 222, 128, 0.2)",
              color: "var(--field-green)",
              marginBottom: "16px",
            }}
          >
            <Microscope size={12} /> ASMAE Sub-Grid Inverse Reconstruction
          </div>

          <h2 className="marketing-section-title" style={{ fontSize: "clamp(2rem, 3.5vw, 3rem)", margin: "0 0 16px" }}>
            Sub-grid resolution without{" "}
            <strong className="marketing-gradient-text">unbacked extrapolation</strong>
          </h2>

          <p className="marketing-section-subtitle" style={{ margin: 0, textAlign: "left" }}>
            ASMAE enforces parent-cell radiometric conservation, evaluating Bayesian model disagreement before assigning effective resolution.
          </p>
        </div>

        {/* Closure Step Timeline Controls */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "24px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {steps.map((step, idx) => (
              <button
                key={step.stepIndex}
                onClick={() => handleStepSelect(idx)}
                style={{
                  textAlign: "left",
                  padding: "12px 16px",
                  borderRadius: "8px",
                  background: idx === activeStepIndex ? "rgba(74, 222, 128, 0.12)" : "rgba(15, 23, 42, 0.6)",
                  border: idx === activeStepIndex ? "1px solid #4ade80" : "1px solid var(--border-subtle)",
                  color: idx === activeStepIndex ? "#f8fafc" : "var(--text-muted)",
                  cursor: "pointer",
                  fontSize: "13px",
                  fontWeight: 600,
                  transition: "all 0.2s ease",
                }}
              >
                <div style={{ fontSize: "10px", color: idx === activeStepIndex ? "#4ade80" : "var(--text-dim)", textTransform: "uppercase" }}>
                  Step 0{step.stepIndex}
                </div>
                {step.stepName}
              </button>
            ))}
          </div>

          {/* Active Step Details Panel */}
          <div
            className="r2-narrative-step"
            style={{ padding: "32px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                <CheckCircle2 size={18} color="#4ade80" />
                <span style={{ fontSize: "11px", fontWeight: 700, color: "#4ade80", textTransform: "uppercase" }}>
                  {currentStep.authorityAssigned}
                </span>
              </div>
              <h3 style={{ fontSize: "20px", fontWeight: 700, color: "#f8fafc", margin: "0 0 12px" }}>
                {currentStep.stepName}
              </h3>
              <p style={{ fontSize: "14px", color: "var(--text-muted)", lineHeight: 1.6, margin: "0 0 24px" }}>
                {currentStep.description}
              </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <div style={{ padding: "12px", borderRadius: "8px", background: "var(--surface-code)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: "10px", color: "var(--text-dim)", textTransform: "uppercase" }}>Native Support</div>
                <div style={{ fontSize: "13px", fontWeight: 700, color: "#f8fafc", marginTop: "2px" }}>
                  {currentStep.nativeSupportLabel}
                </div>
              </div>
              <div style={{ padding: "12px", borderRadius: "8px", background: "var(--surface-code)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: "10px", color: "var(--text-dim)", textTransform: "uppercase" }}>Radiometric Residual</div>
                <div style={{ fontSize: "13px", fontWeight: 700, color: "#4ade80", marginTop: "2px" }}>
                  {currentStep.radiometricResidualNormalized} (Conserved Energy Residual)
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

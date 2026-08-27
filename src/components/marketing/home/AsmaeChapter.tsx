"use client";

import React, { useState } from "react";
import { getAsmaeRun } from "@/components/experience/scientific-run/selectors";
import { Microscope, CheckCircle2 } from "lucide-react";

/* ═══ AgriWise R2 — AsmaeChapter ═══════════════════════════════
   10-Step ASMAE Map Microscope.
   ═══════════════════════════════════════════════════════════════ */

export default function AsmaeChapter() {
  const asmae = getAsmaeRun();
  const [activeStepIndex, setActiveStepIndex] = useState(0);

  const steps = asmae.closureSteps;
  const currentStep = steps[activeStepIndex] || steps[0];

  const handleStepClick = (index: number) => {
    setActiveStepIndex(index);
  };

  return (
    <section
      id="asmae-microscope"
      style={{
        position: "relative",
        paddingTop: "100px",
        paddingBottom: "100px",
        borderTop: "1px solid var(--border-subtle)",
      }}
    >
      <div className="marketing-container">
        <div style={{ textAlign: "center", marginBottom: "48px" }}>
          <div
            className="marketing-section-badge"
            style={{
              background: "rgba(34, 211, 238, 0.08)",
              border: "1px solid rgba(34, 211, 238, 0.2)",
              color: "var(--evidence-observed)",
            }}
          >
            <Microscope size={12} /> ASMAE Sub-Grid Engine
          </div>
          <h2 className="marketing-section-title">
            Sub-grid field reconstruction{" "}
            <strong className="marketing-gradient-text">with radiometric closure</strong>
          </h2>
          <p className="marketing-section-subtitle" style={{ margin: "12px auto 0", textAlign: "center" }}>
            ASMAE does not perform artificial AI super-resolution. It solves physically constrained inverse models over sub-grid microzones while conserving parent-cell energy.
          </p>
        </div>

        {/* 6 Step Interactive Laboratory Rail */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: "32px", alignItems: "center" }}>
          {/* Step Buttons */}
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {steps.map((step, idx) => {
              const isActive = activeStepIndex === idx;
              return (
                <button
                  key={step.stepIndex}
                  onClick={() => handleStepClick(idx)}
                  className="marketing-card"
                  style={{
                    padding: "16px 20px",
                    display: "flex",
                    alignItems: "center",
                    gap: "14px",
                    textAlign: "left",
                    cursor: "pointer",
                    borderColor: isActive ? "var(--evidence-observed)" : "var(--border-subtle)",
                    background: isActive ? "rgba(34, 211, 238, 0.08)" : "var(--surface-elevated)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <div
                    style={{
                      width: "24px",
                      height: "24px",
                      borderRadius: "50%",
                      background: isActive ? "var(--evidence-observed)" : "var(--surface-code)",
                      color: isActive ? "#050a14" : "var(--text-secondary)",
                      fontSize: "12px",
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {idx + 1}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-primary)" }}>
                      {step.stepName}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                      {step.nativeSupportLabel}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Detailed Inspector Card */}
          <div
            className="marketing-card"
            style={{
              padding: "36px",
              borderRadius: "var(--radius-xl)",
              background: "var(--surface-modal)",
              border: "1px solid rgba(34, 211, 238, 0.25)",
              boxShadow: "var(--shadow-elevated)",
            }}
          >
            <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--evidence-observed)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Step {currentStep.stepIndex} of {steps.length} · Scientific Laboratory Inspector
            </div>

            <h3 style={{ fontSize: "22px", fontWeight: 700, color: "var(--text-primary)", margin: "8px 0 14px" }}>
              {currentStep.stepName}
            </h3>

            <p style={{ fontSize: "14px", color: "var(--text-muted)", lineHeight: 1.7, marginBottom: "24px" }}>
              {currentStep.description}
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div style={{ padding: "12px", borderRadius: "8px", background: "var(--surface-code)", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: "10px", color: "var(--text-dim)", textTransform: "uppercase" }}>Effective Resolution</div>
                  <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--evidence-observed)", marginTop: "2px" }}>
                    {currentStep.effectiveResolutionLabel}
                  </div>
                </div>

                <div style={{ padding: "12px", borderRadius: "8px", background: "var(--surface-code)", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: "10px", color: "var(--text-dim)", textTransform: "uppercase" }}>Radiometric Residual</div>
                  <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--field-green)", marginTop: "2px" }}>
                    {currentStep.radiometricResidualNormalized} (Conserved Energy Residual)
                  </div>
                </div>
              </div>

              <div style={{ padding: "12px", borderRadius: "8px", background: "var(--surface-code)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: "10px", color: "var(--text-dim)", textTransform: "uppercase" }}>Authority Assigned</div>
                <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-primary)", marginTop: "2px", display: "flex", alignItems: "center", gap: "6px" }}>
                  <CheckCircle2 size={14} color="var(--field-green)" /> {currentStep.authorityAssigned}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

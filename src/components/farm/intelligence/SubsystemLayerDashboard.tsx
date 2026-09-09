"use client";

/**
 * SubsystemLayerDashboard.tsx
 *
 * Dedicated, highly-interactive parametric dashboard for every canonical subsystem
 * (L0 through L10).
 *
 * Features:
 *   - 11 dedicated subsystem workspaces.
 *   - Parametric tuning controls: soil lab tests, crop calibration, sensor injection, irrigation tuning.
 *   - Deep telemetry inspector & raw data stream viewers.
 *   - Evidence lineage & epistemic audits (explaining why a layer is OK vs DEGRADED).
 *   - Real-time What-If simulation engine showcasing how parameterization elevates health to 100%.
 */

import React, { useState, useMemo } from "react";
import { SUBSYSTEM_METADATA } from "@/hooks/usePlotIntelligence";
import type { SubsystemParamsState } from "@/hooks/useSubsystemParameters";

interface SubsystemLayerDashboardProps {
  isOpen: boolean;
  onClose: () => void;
  activeLayerId: string;
  onSelectLayer: (layerId: string) => void;
  subsystemParams: {
    params: SubsystemParamsState;
    updateLayer: <K extends keyof SubsystemParamsState>(layerId: K, patch: Partial<SubsystemParamsState[K]>) => void;
    resetLayer: (layerId: keyof SubsystemParamsState) => void;
    resetAll: () => void;
    isLayerOverridden: (layerId: string) => boolean;
    getSimulatedLayerStatus: (layerId: string, originalStatus: string) => {
      status: "OK" | "DEGRADED" | "FAILED" | "UNAVAILABLE" | "SKIPPED";
      confidence: number;
      sourceTag: string;
      isOverridden: boolean;
      flags: string[];
    };
    simulation: {
      healthPercent: number;
      reliabilityPercent: number;
      okCount: number;
      degradedCount: number;
      total: number;
      isFullyHealthy: boolean;
    };
  };
  piData: any;
  l10Data: any;
}

const LAYER_IDS = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10"];

export default function SubsystemLayerDashboard({
  isOpen,
  onClose,
  activeLayerId,
  onSelectLayer,
  subsystemParams,
  piData,
  l10Data,
}: SubsystemLayerDashboardProps) {
  const [activeTab, setActiveTab] = useState<"params" | "telemetry" | "lineage" | "simulation">("params");
  const [appliedNotice, setAppliedNotice] = useState<string | null>(null);

  const {
    params,
    updateLayer,
    resetLayer,
    resetAll,
    getSimulatedLayerStatus,
    simulation,
  } = subsystemParams;

  const currentMeta = SUBSYSTEM_METADATA[activeLayerId] || {
    name: "Subsystem Workspace",
    nameAr: "نظام فرعي",
    icon: "⚙️",
    tag: "SYS",
    farmerGroup: "conditions" as const,
  };

  const baseStatus = (activeLayerId === "L4" || activeLayerId === "L6") ? "DEGRADED" : "OK";
  const currentSim = getSimulatedLayerStatus(activeLayerId, baseStatus);

  const handleApply = () => {
    setAppliedNotice("Parameters active! Real-time pipeline recalculated.");
    setTimeout(() => setAppliedNotice(null), 3000);
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 99999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(3, 7, 18, 0.82)",
        backdropFilter: "blur(18px)",
        padding: "16px",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "1040px",
          height: "88vh",
          maxHeight: "820px",
          background: "linear-gradient(180deg, #0c1222 0%, #080c19 100%)",
          border: "1px solid rgba(71, 85, 105, 0.3)",
          borderRadius: "20px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.75), 0 0 40px rgba(99, 102, 241, 0.1)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          color: "#f1f5f9",
        }}
      >
        {/* Top Header */}
        <div
          style={{
            padding: "14px 20px",
            borderBottom: "1px solid rgba(71, 85, 105, 0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "rgba(15, 23, 42, 0.6)",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span style={{ fontSize: "1.75rem" }}>{currentMeta.icon}</span>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0, color: "#fff" }}>
                  {currentMeta.name}
                </h2>
                <span
                  style={{
                    fontSize: "9px",
                    fontWeight: 800,
                    letterSpacing: "0.08em",
                    padding: "2px 6px",
                    borderRadius: "4px",
                    background: "rgba(99, 102, 241, 0.15)",
                    color: "#a5b4fc",
                    border: "1px solid rgba(99, 102, 241, 0.3)",
                  }}
                >
                  {currentMeta.tag}
                </span>
                <span
                  style={{
                    fontSize: "9px",
                    fontWeight: 700,
                    padding: "2px 6px",
                    borderRadius: "4px",
                    background: currentSim.status === "OK" ? "rgba(34, 197, 94, 0.12)" : "rgba(245, 158, 11, 0.12)",
                    color: currentSim.status === "OK" ? "#4ade80" : "#fbbf24",
                    border: `1px solid ${currentSim.status === "OK" ? "rgba(34, 197, 94, 0.25)" : "rgba(245, 158, 11, 0.25)"}`,
                  }}
                >
                  {currentSim.status === "OK" ? "● OPERATIONAL" : "▲ DEGRADED"} ({Math.round(currentSim.confidence * 100)}% Conf)
                </span>
              </div>
              <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: "2px 0 0 0" }}>
                Source: <span style={{ color: currentSim.isOverridden ? "#38bdf8" : "#cbd5e1", fontWeight: 600 }}>{currentSim.sourceTag}</span>
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {/* Global Simulated Health Pill */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background: "rgba(0,0,0,0.3)",
                padding: "4px 10px",
                borderRadius: "8px",
                border: "1px solid rgba(71, 85, 105, 0.25)",
              }}
            >
              <span style={{ fontSize: "11px", color: "#94a3b8" }}>Pipeline Health:</span>
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 800,
                  color: simulation.healthPercent >= 90 ? "#4ade80" : "#fbbf24",
                  fontFamily: "monospace",
                }}
              >
                {simulation.healthPercent}% ({simulation.okCount}/11 OK)
              </span>
            </div>

            {/* Close Button */}
            <button
              onClick={onClose}
              style={{
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.1)",
                color: "#94a3b8",
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "14px",
                fontWeight: 700,
                transition: "all 0.2s",
              }}
              onMouseOver={(e) => (e.currentTarget.style.color = "#fff")}
              onMouseOut={(e) => (e.currentTarget.style.color = "#94a3b8")}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Subsystem Carousel / Switcher */}
        <div
          style={{
            display: "flex",
            gap: "4px",
            padding: "8px 16px",
            background: "rgba(0,0,0,0.35)",
            borderBottom: "1px solid rgba(71, 85, 105, 0.15)",
            overflowX: "auto",
            flexShrink: 0,
          }}
        >
          {LAYER_IDS.map((lid) => {
            const meta = SUBSYSTEM_METADATA[lid];
            const sim = getSimulatedLayerStatus(lid, (lid === "L4" || lid === "L6") ? "DEGRADED" : "OK");
            const isSelected = lid === activeLayerId;
            return (
              <button
                key={lid}
                onClick={() => onSelectLayer(lid)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "5px 10px",
                  borderRadius: "8px",
                  border: isSelected ? "1px solid #6366f1" : "1px solid rgba(71, 85, 105, 0.15)",
                  background: isSelected ? "rgba(99, 102, 241, 0.18)" : "rgba(255, 255, 255, 0.02)",
                  color: isSelected ? "#fff" : "#94a3b8",
                  cursor: "pointer",
                  fontSize: "11px",
                  fontWeight: isSelected ? 700 : 500,
                  whiteSpace: "nowrap",
                  transition: "all 0.15s",
                }}
              >
                <span>{meta.icon}</span>
                <span>{meta.name}</span>
                <span
                  style={{
                    width: "6px",
                    height: "6px",
                    borderRadius: "50%",
                    background: sim.status === "OK" ? "#4ade80" : "#fbbf24",
                  }}
                />
              </button>
            );
          })}
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid rgba(71, 85, 105, 0.15)",
            background: "rgba(8, 12, 25, 0.5)",
            padding: "0 20px",
            flexShrink: 0,
          }}
        >
          {[
            { id: "params", label: "🎛️ Parametric Tuning & Overrides", badge: currentSim.isOverridden ? "Active" : null },
            { id: "telemetry", label: "📡 Live Telemetry & Streams" },
            { id: "lineage", label: "🧬 Lineage & Epistemic Audit" },
            { id: "simulation", label: "🧪 What-If Simulation Engine", badge: `${simulation.healthPercent}%` },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as any)}
              style={{
                padding: "10px 16px",
                background: "transparent",
                border: "none",
                borderBottom: activeTab === t.id ? "2px solid #6366f1" : "2px solid transparent",
                color: activeTab === t.id ? "#fff" : "#94a3b8",
                fontWeight: activeTab === t.id ? 700 : 500,
                fontSize: "12px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                transition: "all 0.2s",
              }}
            >
              <span>{t.label}</span>
              {t.badge && (
                <span
                  style={{
                    fontSize: "9px",
                    padding: "1px 5px",
                    borderRadius: "4px",
                    background: "rgba(99, 102, 241, 0.2)",
                    color: "#a5b4fc",
                    fontWeight: 700,
                  }}
                >
                  {t.badge}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Content Body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "20px",
            background: "rgba(8, 12, 25, 0.2)",
          }}
        >
          {appliedNotice && (
            <div
              style={{
                padding: "8px 14px",
                borderRadius: "8px",
                background: "rgba(16, 185, 129, 0.15)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                color: "#34d399",
                fontSize: "12px",
                fontWeight: 600,
                marginBottom: "16px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span>✅</span>
              <span>{appliedNotice}</span>
            </div>
          )}

          {/* TAB 1: PARAMETRIC TUNING */}
          {activeTab === "params" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              {/* Degradation Warning Banner if degraded */}
              {!currentSim.isOverridden && (activeLayerId === "L4" || activeLayerId === "L6") && (
                <div
                  style={{
                    background: "rgba(245, 158, 11, 0.08)",
                    border: "1px solid rgba(245, 158, 11, 0.25)",
                    borderRadius: "12px",
                    padding: "14px 16px",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "12px",
                  }}
                >
                  <span style={{ fontSize: "1.2rem" }}>⚠️</span>
                  <div style={{ fontSize: "12px", color: "#fcd34d" }}>
                    <strong>Why is this subsystem currently degraded (82% System Health)?</strong>
                    <p style={{ margin: "4px 0 0 0", color: "#fbbf24", lineHeight: 1.5 }}>
                      {activeLayerId === "L4"
                        ? "The system lacks a plot-specific laboratory soil analysis or IoT soil probe, forcing an automatic fallback to an Assumed Baseline (Regional Profile) with only 4% confidence. Input your soil test values below to upgrade this subsystem to 95% confidence (OK status)."
                        : "Yield Potential is uncalibrated because crop variety parameters and planting timeline are missing, and satellite coverage is currently single-point only. Calibrate your crop variety below to upgrade to 90% confidence (OK status)."}
                    </p>
                  </div>
                </div>
              )}

              {/* SPECIFIC PARAMETER PANELS */}

              {/* L4: SOIL PROFILE */}
              {activeLayerId === "L4" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      background: "rgba(0,0,0,0.25)",
                      padding: "12px 16px",
                      borderRadius: "12px",
                      border: "1px solid rgba(71,85,105,0.2)",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: "13px", fontWeight: 700, color: "#fff" }}>Data Source Mode</div>
                      <div style={{ fontSize: "11px", color: "#94a3b8" }}>
                        Choose whether to use regional pedological model estimates or verified soil lab test data
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "6px" }}>
                      <button
                        onClick={() => updateLayer("L4", { sourceMode: "regional_fallback" })}
                        style={{
                          padding: "6px 12px",
                          borderRadius: "8px",
                          border: params.L4.sourceMode === "regional_fallback" ? "1px solid #f59e0b" : "1px solid rgba(71,85,105,0.3)",
                          background: params.L4.sourceMode === "regional_fallback" ? "rgba(245,158,11,0.15)" : "transparent",
                          color: params.L4.sourceMode === "regional_fallback" ? "#fbbf24" : "#94a3b8",
                          fontSize: "11px",
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        Regional Baseline (Generic)
                      </button>
                      <button
                        onClick={() => updateLayer("L4", { sourceMode: "lab_test" })}
                        style={{
                          padding: "6px 12px",
                          borderRadius: "8px",
                          border: params.L4.sourceMode === "lab_test" ? "1px solid #10b981" : "1px solid rgba(71,85,105,0.3)",
                          background: params.L4.sourceMode === "lab_test" ? "rgba(16,185,129,0.15)" : "transparent",
                          color: params.L4.sourceMode === "lab_test" ? "#34d399" : "#94a3b8",
                          fontSize: "11px",
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        🧪 Verified Field Lab Test (Ground Truth)
                      </button>
                    </div>
                  </div>

                  {/* Soil Texture & pH Controls */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                    <div
                      style={{
                        background: "rgba(0,0,0,0.2)",
                        padding: "16px",
                        borderRadius: "12px",
                        border: "1px solid rgba(71,85,105,0.15)",
                      }}
                    >
                      <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Soil Texture Class</label>
                      <select
                        value={params.L4.textureClass}
                        onChange={(e) => updateLayer("L4", { textureClass: e.target.value as any })}
                        style={{
                          width: "100%",
                          marginTop: "6px",
                          padding: "8px 12px",
                          borderRadius: "8px",
                          background: "#0f172a",
                          border: "1px solid rgba(71,85,105,0.3)",
                          color: "#fff",
                          fontSize: "12px",
                        }}
                      >
                        <option value="loam">Loam (Standard Balanced)</option>
                        <option value="sandy_loam">Sandy Loam (Fast Draining)</option>
                        <option value="clay_loam">Clay Loam (High Retention)</option>
                        <option value="clay">Clay (Heavy)</option>
                        <option value="sand">Sand (Rapid Infiltration)</option>
                        <option value="silty_loam">Silt Loam (Fertile Alluvial)</option>
                      </select>

                      <div style={{ marginTop: "16px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                          <span>Clay Percentage:</span>
                          <span style={{ fontWeight: 700, color: "#fff" }}>{params.L4.clay_pct}%</span>
                        </div>
                        <input
                          type="range"
                          min={5}
                          max={60}
                          value={params.L4.clay_pct}
                          onChange={(e) => updateLayer("L4", { clay_pct: Number(e.target.value) })}
                          style={{ width: "100%", accentColor: "#6366f1" }}
                        />
                      </div>

                      <div style={{ marginTop: "12px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                          <span>Sand Percentage:</span>
                          <span style={{ fontWeight: 700, color: "#fff" }}>{params.L4.sand_pct}%</span>
                        </div>
                        <input
                          type="range"
                          min={10}
                          max={85}
                          value={params.L4.sand_pct}
                          onChange={(e) => updateLayer("L4", { sand_pct: Number(e.target.value) })}
                          style={{ width: "100%", accentColor: "#6366f1" }}
                        />
                      </div>
                    </div>

                    <div
                      style={{
                        background: "rgba(0,0,0,0.2)",
                        padding: "16px",
                        borderRadius: "12px",
                        border: "1px solid rgba(71,85,105,0.15)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
                        <span style={{ fontWeight: 700 }}>Soil pH (H₂O):</span>
                        <span style={{ fontWeight: 800, color: params.L4.ph < 6.0 ? "#fbbf24" : params.L4.ph > 7.8 ? "#60a5fa" : "#4ade80" }}>
                          {params.L4.ph.toFixed(1)} ({params.L4.ph < 6.0 ? "Acidic" : params.L4.ph > 7.8 ? "Alkaline" : "Neutral / Ideal"})
                        </span>
                      </div>
                      <input
                        type="range"
                        min={4.5}
                        max={9.0}
                        step={0.1}
                        value={params.L4.ph}
                        onChange={(e) => updateLayer("L4", { ph: Number(e.target.value) })}
                        style={{ width: "100%", marginTop: "6px", accentColor: "#10b981" }}
                      />

                      <div style={{ marginTop: "14px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                          <span>Total Nitrogen (g/kg):</span>
                          <span style={{ fontWeight: 700, color: "#fff" }}>{params.L4.totalNitrogen_g_kg.toFixed(2)}</span>
                        </div>
                        <input
                          type="range"
                          min={0.5}
                          max={4.0}
                          step={0.05}
                          value={params.L4.totalNitrogen_g_kg}
                          onChange={(e) => updateLayer("L4", { totalNitrogen_g_kg: Number(e.target.value) })}
                          style={{ width: "100%", accentColor: "#6366f1" }}
                        />
                      </div>

                      <div style={{ marginTop: "12px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                          <span>Organic Carbon (g/kg):</span>
                          <span style={{ fontWeight: 700, color: "#fff" }}>{params.L4.organicCarbon_g_kg.toFixed(1)}</span>
                        </div>
                        <input
                          type="range"
                          min={5.0}
                          max={50.0}
                          step={0.5}
                          value={params.L4.organicCarbon_g_kg}
                          onChange={(e) => updateLayer("L4", { organicCarbon_g_kg: Number(e.target.value) })}
                          style={{ width: "100%", accentColor: "#6366f1" }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* L6: YIELD CALIBRATION */}
              {activeLayerId === "L6" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      background: "rgba(0,0,0,0.25)",
                      padding: "12px 16px",
                      borderRadius: "12px",
                      border: "1px solid rgba(71,85,105,0.2)",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: "13px", fontWeight: 700, color: "#fff" }}>Yield Model Calibration</div>
                      <div style={{ fontSize: "11px", color: "#94a3b8" }}>
                        Select the crop variety and target yield baseline to eliminate uncalibrated warnings
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "6px" }}>
                      <button
                        onClick={() => updateLayer("L6", { sourceMode: "uncalibrated" })}
                        style={{
                          padding: "6px 12px",
                          borderRadius: "8px",
                          border: params.L6.sourceMode === "uncalibrated" ? "1px solid #f59e0b" : "1px solid rgba(71,85,105,0.3)",
                          background: params.L6.sourceMode === "uncalibrated" ? "rgba(245,158,11,0.15)" : "transparent",
                          color: params.L6.sourceMode === "uncalibrated" ? "#fbbf24" : "#94a3b8",
                          fontSize: "11px",
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        Uncalibrated Satellite Estimate
                      </button>
                      <button
                        onClick={() => updateLayer("L6", { sourceMode: "calibrated" })}
                        style={{
                          padding: "6px 12px",
                          borderRadius: "8px",
                          border: params.L6.sourceMode === "calibrated" ? "1px solid #10b981" : "1px solid rgba(71,85,105,0.3)",
                          background: params.L6.sourceMode === "calibrated" ? "rgba(16,185,129,0.15)" : "transparent",
                          color: params.L6.sourceMode === "calibrated" ? "#34d399" : "#94a3b8",
                          fontSize: "11px",
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        🎯 Calibrated Crop Model (Ground Truth)
                      </button>
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                    <div
                      style={{
                        background: "rgba(0,0,0,0.2)",
                        padding: "16px",
                        borderRadius: "12px",
                        border: "1px solid rgba(71,85,105,0.15)",
                      }}
                    >
                      <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Crop Variety</label>
                      <select
                        value={params.L6.cropType}
                        onChange={(e) => updateLayer("L6", { cropType: e.target.value as any })}
                        style={{
                          width: "100%",
                          marginTop: "6px",
                          padding: "8px 12px",
                          borderRadius: "8px",
                          background: "#0f172a",
                          border: "1px solid rgba(71,85,105,0.3)",
                          color: "#fff",
                          fontSize: "12px",
                        }}
                      >
                        <option value="olive">Olive (Zitoun - Olea europaea)</option>
                        <option value="citrus">Citrus (Oranges & Clementines)</option>
                        <option value="wheat">Wheat (Durum / Soft)</option>
                        <option value="tomato">Tomato (Open Field / Protected)</option>
                        <option value="barley">Barley</option>
                        <option value="potato">Potato</option>
                        <option value="maize">Maize (Corn)</option>
                        <option value="date_palm">Date Palm</option>
                      </select>

                      <div style={{ marginTop: "16px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                          <span>Target Benchmark Yield:</span>
                          <span style={{ fontWeight: 700, color: "#4ade80" }}>{params.L6.targetYield_t_ha} t/ha</span>
                        </div>
                        <input
                          type="range"
                          min={1.0}
                          max={15.0}
                          step={0.2}
                          value={params.L6.targetYield_t_ha}
                          onChange={(e) => updateLayer("L6", { targetYield_t_ha: Number(e.target.value) })}
                          style={{ width: "100%", accentColor: "#10b981" }}
                        />
                      </div>
                    </div>

                    <div
                      style={{
                        background: "rgba(0,0,0,0.2)",
                        padding: "16px",
                        borderRadius: "12px",
                        border: "1px solid rgba(71,85,105,0.15)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
                        <span style={{ fontWeight: 700 }}>Crop Growth Coefficient (Kc):</span>
                        <span style={{ fontWeight: 800, color: "#60a5fa" }}>{params.L6.cropCoefficientKc.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min={0.4}
                        max={1.35}
                        step={0.05}
                        value={params.L6.cropCoefficientKc}
                        onChange={(e) => updateLayer("L6", { cropCoefficientKc: Number(e.target.value) })}
                        style={{ width: "100%", marginTop: "6px", accentColor: "#60a5fa" }}
                      />

                      <div style={{ marginTop: "16px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                          <span>Historical Farm Baseline:</span>
                          <span style={{ fontWeight: 700, color: "#fff" }}>{params.L6.historicalBenchmark_t_ha} t/ha</span>
                        </div>
                        <input
                          type="range"
                          min={1.0}
                          max={12.0}
                          step={0.2}
                          value={params.L6.historicalBenchmark_t_ha}
                          onChange={(e) => updateLayer("L6", { historicalBenchmark_t_ha: Number(e.target.value) })}
                          style={{ width: "100%", accentColor: "#6366f1" }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* L2: CANOPY & ASMAE */}
              {activeLayerId === "L2" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Crop Phenological Growth Stage</label>
                    <select
                      value={params.L2.cropStageOverride}
                      onChange={(e) => updateLayer("L2", { cropStageOverride: e.target.value as any })}
                      style={{ width: "100%", marginTop: "6px", padding: "8px 12px", borderRadius: "8px", background: "#0f172a", border: "1px solid rgba(71,85,105,0.3)", color: "#fff", fontSize: "12px" }}
                    >
                      <option value="auto">Auto (Require Canonical Phenology Receipt)</option>
                      <option value="emergence">Emergence / Early Sprouting</option>
                      <option value="vegetative">Vegetative Canopy Expansion</option>
                      <option value="flowering">Flowering & Bloom</option>
                      <option value="yield_formation">Yield Formation / Fruit Set</option>
                      <option value="ripening">Ripening & Maturation</option>
                      <option value="harvest">Harvest Ready / Senescence</option>
                    </select>

                    <div style={{ marginTop: "16px" }}>
                      <label style={{ fontSize: "11px", color: "#94a3b8" }}>Confirmed Planting / Pruning Date</label>
                      <input
                        type="date"
                        value={params.L2.confirmedPlantingDate}
                        onChange={(e) => updateLayer("L2", { confirmedPlantingDate: e.target.value })}
                        style={{ width: "100%", marginTop: "4px", padding: "6px 10px", borderRadius: "8px", background: "#0f172a", border: "1px solid rgba(71,85,105,0.3)", color: "#fff", fontSize: "12px" }}
                      />
                    </div>
                  </div>

                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
                      <span style={{ fontWeight: 700 }}>Canopy NDVI Sensitivity:</span>
                      <span style={{ fontWeight: 800, color: "#4ade80" }}>{params.L2.ndviSensitivity.toFixed(2)}x</span>
                    </div>
                    <input
                      type="range"
                      min={0.5}
                      max={1.5}
                      step={0.05}
                      value={params.L2.ndviSensitivity}
                      onChange={(e) => updateLayer("L2", { ndviSensitivity: Number(e.target.value) })}
                      style={{ width: "100%", marginTop: "8px", accentColor: "#4ade80" }}
                    />

                    <div style={{ marginTop: "16px" }}>
                      <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Cloud Filtering Policy</label>
                      <select
                        value={params.L2.cloudFilterStrictness}
                        onChange={(e) => updateLayer("L2", { cloudFilterStrictness: e.target.value as any })}
                        style={{ width: "100%", marginTop: "6px", padding: "8px 12px", borderRadius: "8px", background: "#0f172a", border: "1px solid rgba(71,85,105,0.3)", color: "#fff", fontSize: "12px" }}
                      >
                        <option value="strict">Strict Cloud Mask (&lt;5% Cloud Probability)</option>
                        <option value="standard">Standard Sentinel SCL Mask</option>
                        <option value="relaxed">Relaxed (Include Thin Cirrus Pixels)</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}

              {/* L3: SOIL WATER & IRRIGATION */}
              {activeLayerId === "L3" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Irrigation Infrastructure</label>
                    <select
                      value={params.L3.irrigationMethod}
                      onChange={(e) => updateLayer("L3", { irrigationMethod: e.target.value as any })}
                      style={{ width: "100%", marginTop: "6px", padding: "8px 12px", borderRadius: "8px", background: "#0f172a", border: "1px solid rgba(71,85,105,0.3)", color: "#fff", fontSize: "12px" }}
                    >
                      <option value="drip">Drip Micro-irrigation (Goutte-à-goutte)</option>
                      <option value="pivot">Center Pivot / Lateral Move</option>
                      <option value="sprinkler">Solid Set Sprinklers</option>
                      <option value="furrow">Surface Furrow / Basin Flood</option>
                    </select>

                    <div style={{ marginTop: "16px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                        <span>Distribution Efficiency:</span>
                        <span style={{ fontWeight: 700, color: "#38bdf8" }}>{params.L3.irrigationEfficiency_pct}%</span>
                      </div>
                      <input
                        type="range"
                        min={50}
                        max={95}
                        value={params.L3.irrigationEfficiency_pct}
                        onChange={(e) => updateLayer("L3", { irrigationEfficiency_pct: Number(e.target.value) })}
                        style={{ width: "100%", accentColor: "#38bdf8" }}
                      />
                    </div>
                  </div>

                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
                      <span style={{ fontWeight: 700 }}>Effective Root Zone Depth:</span>
                      <span style={{ fontWeight: 800, color: "#38bdf8" }}>{params.L3.rootDepth_cm} cm</span>
                    </div>
                    <input
                      type="range"
                      min={20}
                      max={150}
                      step={5}
                      value={params.L3.rootDepth_cm}
                      onChange={(e) => updateLayer("L3", { rootDepth_cm: Number(e.target.value) })}
                      style={{ width: "100%", marginTop: "8px", accentColor: "#38bdf8" }}
                    />

                    <div style={{ marginTop: "16px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                        <span>Refill Trigger (MAD % of TAW):</span>
                        <span style={{ fontWeight: 700, color: "#f59e0b" }}>{params.L3.depletionTrigger_pct}%</span>
                      </div>
                      <input
                        type="range"
                        min={30}
                        max={70}
                        value={params.L3.depletionTrigger_pct}
                        onChange={(e) => updateLayer("L3", { depletionTrigger_pct: Number(e.target.value) })}
                        style={{ width: "100%", accentColor: "#f59e0b" }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* L1: SENSOR FUSION */}
              {activeLayerId === "L1" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Virtual IoT Soil Probe Feed</span>
                      <button
                        onClick={() => updateLayer("L1", { simulatedSensorActive: !params.L1.simulatedSensorActive })}
                        style={{
                          padding: "4px 10px",
                          borderRadius: "6px",
                          border: params.L1.simulatedSensorActive ? "1px solid #10b981" : "1px solid rgba(71,85,105,0.3)",
                          background: params.L1.simulatedSensorActive ? "rgba(16,185,129,0.2)" : "transparent",
                          color: params.L1.simulatedSensorActive ? "#34d399" : "#94a3b8",
                          fontSize: "11px",
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        {params.L1.simulatedSensorActive ? "● Sensor Active" : "○ Disconnected"}
                      </button>
                    </div>

                    <div style={{ marginTop: "16px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                        <span>Probe Moisture (VWC %):</span>
                        <span style={{ fontWeight: 700, color: "#60a5fa" }}>{params.L1.soilMoistureVwc_pct}%</span>
                      </div>
                      <input
                        type="range"
                        min={10}
                        max={50}
                        step={0.5}
                        disabled={!params.L1.simulatedSensorActive}
                        value={params.L1.soilMoistureVwc_pct}
                        onChange={(e) => updateLayer("L1", { soilMoistureVwc_pct: Number(e.target.value) })}
                        style={{ width: "100%", accentColor: "#60a5fa" }}
                      />
                    </div>
                  </div>

                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
                      <span style={{ fontWeight: 700 }}>Ground Sensor vs Satellite Fusion Weight:</span>
                      <span style={{ fontWeight: 800, color: "#a5b4fc" }}>{params.L1.sensorFusionWeight_pct}%</span>
                    </div>
                    <input
                      type="range"
                      min={10}
                      max={90}
                      value={params.L1.sensorFusionWeight_pct}
                      onChange={(e) => updateLayer("L1", { sensorFusionWeight_pct: Number(e.target.value) })}
                      style={{ width: "100%", marginTop: "8px", accentColor: "#6366f1" }}
                    />
                    <p style={{ fontSize: "11px", color: "#94a3b8", marginTop: "12px", lineHeight: 1.4 }}>
                      Higher sensor weighting prioritizes local capacitive moisture and micro-station readings over Sentinel-2 / ERA5 optical passes.
                    </p>
                  </div>
                </div>
              )}

              {/* L0: MICROCLIMATE */}
              {activeLayerId === "L0" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
                      <span style={{ fontWeight: 700 }}>Elevation Adjustment:</span>
                      <span style={{ fontWeight: 800, color: "#fff" }}>{params.L0.elevationOffset_m > 0 ? `+${params.L0.elevationOffset_m}` : params.L0.elevationOffset_m} m</span>
                    </div>
                    <input
                      type="range"
                      min={-150}
                      max={300}
                      step={10}
                      value={params.L0.elevationOffset_m}
                      onChange={(e) => updateLayer("L0", { elevationOffset_m: Number(e.target.value) })}
                      style={{ width: "100%", marginTop: "8px", accentColor: "#6366f1" }}
                    />
                    <p style={{ fontSize: "11px", color: "#94a3b8", marginTop: "8px" }}>
                      Applies adiabatic lapse rate (-0.65°C per 100m) to correct gridded weather predictions for ridge/valley terrain.
                    </p>
                  </div>

                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
                      <span style={{ fontWeight: 700 }}>Heatwave Thermal Stress Threshold:</span>
                      <span style={{ fontWeight: 800, color: "#f87171" }}>{params.L0.heatThreshold_c}°C</span>
                    </div>
                    <input
                      type="range"
                      min={30}
                      max={45}
                      step={0.5}
                      value={params.L0.heatThreshold_c}
                      onChange={(e) => updateLayer("L0", { heatThreshold_c: Number(e.target.value) })}
                      style={{ width: "100%", marginTop: "8px", accentColor: "#f87171" }}
                    />
                  </div>
                </div>
              )}

              {/* L5: PATHOLOGY */}
              {activeLayerId === "L5" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Crop Pathogen Susceptibility</label>
                    <select
                      value={params.L5.pathogenSusceptibility}
                      onChange={(e) => updateLayer("L5", { pathogenSusceptibility: e.target.value as any })}
                      style={{ width: "100%", marginTop: "6px", padding: "8px 12px", borderRadius: "8px", background: "#0f172a", border: "1px solid rgba(71,85,105,0.3)", color: "#fff", fontSize: "12px" }}
                    >
                      <option value="resistant">Resistant Cultivar (Low Risk Multiplier)</option>
                      <option value="moderate">Moderate / Standard Commercial</option>
                      <option value="high">High Susceptibility (Tight Alert Window)</option>
                      <option value="severe">Severe / Outbreak History on Plot</option>
                    </select>
                  </div>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
                      <span style={{ fontWeight: 700 }}>Spore Germination Wetness Window:</span>
                      <span style={{ fontWeight: 800, color: "#f59e0b" }}>{params.L5.sporeGerminationHours} hours</span>
                    </div>
                    <input
                      type="range"
                      min={3}
                      max={18}
                      value={params.L5.sporeGerminationHours}
                      onChange={(e) => updateLayer("L5", { sporeGerminationHours: Number(e.target.value) })}
                      style={{ width: "100%", marginTop: "8px", accentColor: "#f59e0b" }}
                    />
                  </div>
                </div>
              )}

              {/* L7: CALENDAR */}
              {activeLayerId === "L7" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Field Operational Readiness</label>
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "10px" }}>
                      <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "#fff", cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={params.L7.laborAvailable}
                          onChange={(e) => updateLayer("L7", { laborAvailable: e.target.checked })}
                          style={{ width: "16px", height: "16px", accentColor: "#10b981" }}
                        />
                        Labor Teams Available On-Site
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "#fff", cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={params.L7.machineryReady}
                          onChange={(e) => updateLayer("L7", { machineryReady: e.target.checked })}
                          style={{ width: "16px", height: "16px", accentColor: "#10b981" }}
                        />
                        Tractors & Spray Machinery Fueled / Operational
                      </label>
                    </div>
                  </div>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Task Scheduling Priority</label>
                    <select
                      value={params.L7.prioritySorting}
                      onChange={(e) => updateLayer("L7", { prioritySorting: e.target.value as any })}
                      style={{ width: "100%", marginTop: "6px", padding: "8px 12px", borderRadius: "8px", background: "#0f172a", border: "1px solid rgba(71,85,105,0.3)", color: "#fff", fontSize: "12px" }}
                    >
                      <option value="urgency">Urgency / Pathogen Risk Window</option>
                      <option value="economic_impact">Economic Impact & Yield Protection</option>
                      <option value="water_saving">Water Conservation & Drought Defense</option>
                    </select>
                  </div>
                </div>
              )}

              {/* L8: PRESCRIPTIONS */}
              {activeLayerId === "L8" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
                      <span style={{ fontWeight: 700 }}>Variable Rate Safety Margin:</span>
                      <span style={{ fontWeight: 800, color: "#34d399" }}>{params.L8.safetyMargin_pct}%</span>
                    </div>
                    <input
                      type="range"
                      min={80}
                      max={120}
                      value={params.L8.safetyMargin_pct}
                      onChange={(e) => updateLayer("L8", { safetyMargin_pct: Number(e.target.value) })}
                      style={{ width: "100%", marginTop: "8px", accentColor: "#10b981" }}
                    />
                  </div>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#cbd5e1" }}>
                      <span style={{ fontWeight: 700 }}>Nitrogen Application Ceiling:</span>
                      <span style={{ fontWeight: 800, color: "#60a5fa" }}>{params.L8.nitrogenCap_kg_ha} kg N/ha</span>
                    </div>
                    <input
                      type="range"
                      min={40}
                      max={220}
                      step={5}
                      value={params.L8.nitrogenCap_kg_ha}
                      onChange={(e) => updateLayer("L8", { nitrogenCap_kg_ha: Number(e.target.value) })}
                      style={{ width: "100%", marginTop: "8px", accentColor: "#60a5fa" }}
                    />
                  </div>
                </div>
              )}

              {/* L9: ADVISORY */}
              {activeLayerId === "L9" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Agronomic Advisory Strategy</label>
                    <select
                      value={params.L9.advisoryStrategy}
                      onChange={(e) => updateLayer("L9", { advisoryStrategy: e.target.value as any })}
                      style={{ width: "100%", marginTop: "6px", padding: "8px 12px", borderRadius: "8px", background: "#0f172a", border: "1px solid rgba(71,85,105,0.3)", color: "#fff", fontSize: "12px" }}
                    >
                      <option value="conservative">Conservative (Water & Input Savings)</option>
                      <option value="balanced">Balanced (Optimal ROI & Sustainability)</option>
                      <option value="yield_maximizing">Maximum Yield (Intensive Agronomic Regimen)</option>
                    </select>
                  </div>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Economic Fertilizer Sensitivity</label>
                    <select
                      value={params.L9.economicSensitivity}
                      onChange={(e) => updateLayer("L9", { economicSensitivity: e.target.value as any })}
                      style={{ width: "100%", marginTop: "6px", padding: "8px 12px", borderRadius: "8px", background: "#0f172a", border: "1px solid rgba(71,85,105,0.3)", color: "#fff", fontSize: "12px" }}
                    >
                      <option value="low">Low (Prioritize maximum vegetative growth)</option>
                      <option value="medium">Medium (Standard cost-efficiency balance)</option>
                      <option value="high">High (Strict marginal returns filter)</option>
                    </select>
                  </div>
                </div>
              )}

              {/* L10: MESIA SYNTHESIS */}
              {activeLayerId === "L10" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Safety Strictness Filter</label>
                    <select
                      value={params.L10.safetyStrictness}
                      onChange={(e) => updateLayer("L10", { safetyStrictness: e.target.value as any })}
                      style={{ width: "100%", marginTop: "6px", padding: "8px 12px", borderRadius: "8px", background: "#0f172a", border: "1px solid rgba(71,85,105,0.3)", color: "#fff", fontSize: "12px" }}
                    >
                      <option value="strict">Strict (Block any un-validated spatial zone)</option>
                      <option value="balanced">Balanced (MESIA World Model Consensus)</option>
                      <option value="permissive">Permissive (Advisory Guidance Active)</option>
                    </select>
                  </div>
                  <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.15)" }}>
                    <label style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1" }}>Conflict Resolution Protocol</label>
                    <select
                      value={params.L10.conflictResolution}
                      onChange={(e) => updateLayer("L10", { conflictResolution: e.target.value as any })}
                      style={{ width: "100%", marginTop: "6px", padding: "8px 12px", borderRadius: "8px", background: "#0f172a", border: "1px solid rgba(71,85,105,0.3)", color: "#fff", fontSize: "12px" }}
                    >
                      <option value="safety_first">Safety First (Preserve Plant Tissue & Water)</option>
                      <option value="yield_first">Yield First (Maximize Biomass Accumulation)</option>
                      <option value="consensus">Consensus (Bayesian Multi-Layer Weighting)</option>
                    </select>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: LIVE TELEMETRY */}
          {activeTab === "telemetry" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
                <div style={{ background: "rgba(0,0,0,0.3)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(71,85,105,0.2)" }}>
                  <div style={{ fontSize: "10px", color: "#94a3b8", textTransform: "uppercase" }}>Telemetry Reliability</div>
                  <div style={{ fontSize: "18px", fontWeight: 800, color: currentSim.confidence >= 0.8 ? "#4ade80" : "#fbbf24", marginTop: "4px" }}>
                    {(currentSim.confidence * 100).toFixed(0)}%
                  </div>
                  <div style={{ fontSize: "10px", color: "#64748b", marginTop: "2px" }}>
                    {currentSim.status === "OK" ? "Within operational confidence window" : "Below 50% verification threshold"}
                  </div>
                </div>

                <div style={{ background: "rgba(0,0,0,0.3)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(71,85,105,0.2)" }}>
                  <div style={{ fontSize: "10px", color: "#94a3b8", textTransform: "uppercase" }}>Data Feed Source</div>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#fff", marginTop: "6px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {currentSim.sourceTag}
                  </div>
                  <div style={{ fontSize: "10px", color: "#64748b", marginTop: "2px" }}>
                    {currentSim.isOverridden ? "Farmer Verified Parameter" : "Automated Remote Sensing"}
                  </div>
                </div>

                <div style={{ background: "rgba(0,0,0,0.3)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(71,85,105,0.2)" }}>
                  <div style={{ fontSize: "10px", color: "#94a3b8", textTransform: "uppercase" }}>Subsystem Status</div>
                  <div style={{ fontSize: "16px", fontWeight: 800, color: currentSim.status === "OK" ? "#4ade80" : "#fbbf24", marginTop: "4px" }}>
                    {currentSim.status}
                  </div>
                  <div style={{ fontSize: "10px", color: "#64748b", marginTop: "2px" }}>
                    {currentSim.flags.length > 0 ? currentSim.flags.join(", ") : "All verification checks passed"}
                  </div>
                </div>
              </div>

              {/* Raw JSON Stream Inspection */}
              <div style={{ background: "rgba(0,0,0,0.4)", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.2)", padding: "14px" }}>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "#cbd5e1", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" }}>
                  Active Parameter Snapshot & Telemetry Context
                </div>
                <pre
                  style={{
                    background: "#080c19",
                    padding: "12px",
                    borderRadius: "8px",
                    fontSize: "11px",
                    fontFamily: "monospace",
                    color: "#38bdf8",
                    maxHeight: "240px",
                    overflowY: "auto",
                    margin: 0,
                    border: "1px solid rgba(71,85,105,0.2)",
                  }}
                >
                  {JSON.stringify(
                    {
                      subsystem_id: activeLayerId,
                      name: currentMeta.name,
                      status: currentSim.status,
                      confidence: currentSim.confidence,
                      active_parameters: params[activeLayerId as keyof SubsystemParamsState],
                      degradation_flags: currentSim.flags,
                    },
                    null,
                    2
                  )}
                </pre>
              </div>
            </div>
          )}

          {/* TAB 3: LINEAGE & AUDIT */}
          {activeTab === "lineage" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ background: "rgba(0,0,0,0.25)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(71,85,105,0.2)" }}>
                <h4 style={{ fontSize: "13px", fontWeight: 700, margin: "0 0 8px 0", color: "#fff" }}>
                  Epistemic Lineage & Evidence Provenance
                </h4>
                <p style={{ fontSize: "12px", color: "#94a3b8", lineHeight: 1.5 }}>
                  AgriWise enforces strict separation between <strong>Empirical Ground Truth</strong>, <strong>Physical Remote Sensing</strong>, and <strong>Regional Generic Fallbacks</strong>.
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px", background: "rgba(255,255,255,0.02)", borderRadius: "8px" }}>
                    <span style={{ fontSize: "16px" }}>🛰️</span>
                    <div>
                      <div style={{ fontSize: "12px", fontWeight: 600, color: "#fff" }}>Earth Observation (Sentinel-2 / Sentinel-1)</div>
                      <div style={{ fontSize: "10px", color: "#64748b" }}>Multi-spectral 10m bands assimilated for canopy chlorophyll and surface backscatter.</div>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px", background: "rgba(255,255,255,0.02)", borderRadius: "8px" }}>
                    <span style={{ fontSize: "16px" }}>🌤️</span>
                    <div>
                      <div style={{ fontSize: "12px", fontWeight: 600, color: "#fff" }}>Numerical Weather Prediction (NWP)</div>
                      <div style={{ fontSize: "10px", color: "#64748b" }}>High-resolution regional atmospheric models driving evapotranspiration and spray windows.</div>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px", background: "rgba(255,255,255,0.02)", borderRadius: "8px" }}>
                    <span style={{ fontSize: "16px" }}>🧪</span>
                    <div>
                      <div style={{ fontSize: "12px", fontWeight: 600, color: "#fff" }}>Soil & Nutrient Calibration</div>
                      <div style={{ fontSize: "10px", color: currentSim.isOverridden ? "#34d399" : "#fbbf24" }}>
                        {activeLayerId === "L4" && currentSim.isOverridden
                          ? "Verified Field Lab Test — 100% authoritative ground truth active."
                          : "Regional Pedological Survey baseline — requires physical lab test for full precision."}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: WHAT-IF SIMULATION */}
          {activeTab === "simulation" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              <div
                style={{
                  background: "linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(16, 185, 129, 0.1) 100%)",
                  borderRadius: "16px",
                  padding: "20px",
                  border: "1px solid rgba(99, 102, 241, 0.25)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "#fff" }}>
                    Pipeline Health What-If Simulator
                  </h3>
                  <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: "4px 0 0 0", maxWidth: "480px", lineHeight: 1.5 }}>
                    See how your ground-truth parameter overrides (lab soil tests, crop variety calibration, and irrigation constraints) elevate pipeline reliability.
                  </p>
                </div>

                <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: "10px", color: "#94a3b8", textTransform: "uppercase" }}>System Health</div>
                    <div style={{ fontSize: "2rem", fontWeight: 900, color: simulation.healthPercent === 100 ? "#4ade80" : "#fbbf24", fontFamily: "monospace" }}>
                      {simulation.healthPercent}%
                    </div>
                    <div style={{ fontSize: "10px", color: "#cbd5e1" }}>
                      {simulation.okCount}/11 Systems OK
                    </div>
                  </div>

                  <div style={{ width: "1px", height: "40px", background: "rgba(255,255,255,0.1)" }} />

                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: "10px", color: "#94a3b8", textTransform: "uppercase" }}>Scientific Reliability</div>
                    <div style={{ fontSize: "2rem", fontWeight: 900, color: "#60a5fa", fontFamily: "monospace" }}>
                      {simulation.reliabilityPercent}%
                    </div>
                    <div style={{ fontSize: "10px", color: "#cbd5e1" }}>
                      Evidence Grade
                    </div>
                  </div>
                </div>
              </div>

              {/* Subsystem Readiness Matrix */}
              <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: "12px", padding: "16px", border: "1px solid rgba(71,85,105,0.2)" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "#cbd5e1", marginBottom: "12px" }}>
                  Subsystem Verification Matrix
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
                  {LAYER_IDS.map((lid) => {
                    const meta = SUBSYSTEM_METADATA[lid];
                    const sim = getSimulatedLayerStatus(lid, (lid === "L4" || lid === "L6") ? "DEGRADED" : "OK");
                    return (
                      <div
                        key={lid}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "8px 12px",
                          borderRadius: "8px",
                          background: "rgba(255,255,255,0.02)",
                          border: "1px solid rgba(71,85,105,0.12)",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span>{meta.icon}</span>
                          <span style={{ fontSize: "11px", fontWeight: 600, color: "#fff" }}>{meta.name}</span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span
                            style={{
                              fontSize: "9px",
                              padding: "1px 6px",
                              borderRadius: "4px",
                              background: sim.status === "OK" ? "rgba(34,197,94,0.15)" : "rgba(245,158,11,0.15)",
                              color: sim.status === "OK" ? "#4ade80" : "#fbbf24",
                              fontWeight: 700,
                            }}
                          >
                            {sim.status} ({(sim.confidence * 100).toFixed(0)}%)
                          </span>
                          {sim.isOverridden && (
                            <span style={{ fontSize: "8px", padding: "1px 4px", borderRadius: "3px", background: "rgba(56,189,248,0.2)", color: "#38bdf8", fontWeight: 700 }}>
                              OVERRIDE
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div
          style={{
            padding: "14px 20px",
            borderTop: "1px solid rgba(71, 85, 105, 0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "rgba(15, 23, 42, 0.7)",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <button
              onClick={() => resetLayer(activeLayerId as keyof SubsystemParamsState)}
              style={{
                padding: "6px 12px",
                borderRadius: "8px",
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.1)",
                color: "#94a3b8",
                fontSize: "11px",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.2s",
              }}
            >
              Reset {currentMeta.name} to Baseline
            </button>
            <button
              onClick={resetAll}
              style={{
                padding: "6px 12px",
                borderRadius: "8px",
                background: "rgba(239, 68, 68, 0.08)",
                border: "1px solid rgba(239, 68, 68, 0.2)",
                color: "#f87171",
                fontSize: "11px",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.2s",
              }}
            >
              Reset Entire Pipeline
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <button
              onClick={onClose}
              style={{
                padding: "8px 16px",
                borderRadius: "8px",
                background: "transparent",
                border: "1px solid rgba(71,85,105,0.3)",
                color: "#cbd5e1",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Close
            </button>
            <button
              onClick={handleApply}
              style={{
                padding: "8px 20px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)",
                border: "1px solid rgba(99, 102, 241, 0.4)",
                color: "#fff",
                fontSize: "12px",
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 4px 12px rgba(99, 102, 241, 0.3)",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <span>Apply Parameters</span>
              <span>→</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

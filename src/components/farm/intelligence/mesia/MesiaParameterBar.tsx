"useClient";
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MesiaParameters } from "./types";

interface MesiaParameterBarProps {
  parameters: MesiaParameters;
  onChange: (updated: Partial<MesiaParameters>) => void;
  onReset: () => void;
}

const SOIL_TEXTURES = ["Clay Loam", "Sandy Loam", "Silty Clay", "Sand", "Clay"] as const;

export default function MesiaParameterBar({
  parameters,
  onChange,
  onReset,
}: MesiaParameterBarProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const toggleBand = (band: string) => {
    const current = parameters.activeBands;
    if (current.includes(band)) {
      if (current.length > 1) {
        onChange({ activeBands: current.filter((b) => b !== band) });
      }
    } else {
      onChange({ activeBands: [...current, band] });
    }
  };

  return (
    <div
      style={{
        background: "rgba(11, 18, 33, 0.95)",
        borderBottom: "1px solid rgba(56, 189, 248, 0.25)",
        backdropFilter: "blur(12px)",
        padding: "10px 24px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        zIndex: 20,
      }}
    >
      {/* Primary Quick Controls Row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        {/* Left Side: Physical Inversion Model & Soil Texture */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              🌱 Soil Matrix:
            </span>
            <select
              value={parameters.soilTexture}
              onChange={(e) => onChange({ soilTexture: e.target.value as any })}
              style={{
                background: "rgba(15, 23, 42, 0.9)",
                border: "1px solid rgba(56, 189, 248, 0.4)",
                borderRadius: "6px",
                padding: "4px 8px",
                color: "#38bdf8",
                fontSize: "11px",
                fontWeight: 600,
                outline: "none",
                cursor: "pointer",
              }}
            >
              {SOIL_TEXTURES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div style={{ width: "1px", height: "18px", background: "rgba(51, 65, 85, 0.6)" }} />

          {/* Dielectric Formulation */}
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8" }}>ε_r Model:</span>
            {(
              [
                { id: "dobson", label: "Dobson '85" },
                { id: "topp", label: "Topp '80" },
                { id: "mironov", label: "Mironov '13" },
              ] as const
            ).map((m) => {
              const isSelected = parameters.dielectricModel === m.id;
              return (
                <button
                  key={m.id}
                  onClick={() => onChange({ dielectricModel: m.id })}
                  style={{
                    padding: "3px 8px",
                    borderRadius: "4px",
                    fontSize: "10px",
                    fontWeight: isSelected ? 700 : 500,
                    border: isSelected ? "1px solid #38bdf8" : "1px solid rgba(51, 65, 85, 0.4)",
                    background: isSelected ? "rgba(56, 189, 248, 0.2)" : "rgba(15, 23, 42, 0.6)",
                    color: isSelected ? "#38bdf8" : "#94a3b8",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {m.label}
                </button>
              );
            })}
          </div>

          <div style={{ width: "1px", height: "18px", background: "rgba(51, 65, 85, 0.6)" }} />

          {/* Active Radiometric Modalities */}
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8" }}>Bands:</span>
            {[
              { id: "GNSS", label: "GNSS-R L1", col: "#4ade80" },
              { id: "CELL", label: "Cellular 4G/5G", col: "#a78bfa" },
              { id: "UHF", label: "UHF 546M", col: "#f59e0b" },
              { id: "SAR", label: "SAR C-Band", col: "#38bdf8" },
              { id: "WIFI", label: "Wi-Fi CSI", col: "#ec4899" },
            ].map((b) => {
              const active = parameters.activeBands.includes(b.id);
              return (
                <button
                  key={b.id}
                  onClick={() => toggleBand(b.id)}
                  style={{
                    padding: "3px 7px",
                    borderRadius: "4px",
                    fontSize: "10px",
                    fontWeight: active ? 700 : 500,
                    border: active ? `1px solid ${b.col}` : "1px solid rgba(51, 65, 85, 0.4)",
                    background: active ? `rgba(${b.col === "#4ade80" ? "74, 222, 128" : "56, 189, 248"}, 0.15)` : "rgba(15, 23, 42, 0.5)",
                    color: active ? b.col : "#64748b",
                    cursor: "pointer",
                  }}
                >
                  {active ? "✓ " : ""}{b.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Side: View Mode, Provenance Filter & Drawer Toggle */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          {/* Provenance Filter */}
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 600 }}>Provenance:</span>
            <button
              onClick={() =>
                onChange({
                  provenanceFilter: parameters.provenanceFilter === "all" ? "measured_only" : "all",
                })
              }
              style={{
                padding: "3px 8px",
                borderRadius: "4px",
                fontSize: "10px",
                fontWeight: 700,
                border:
                  parameters.provenanceFilter === "measured_only"
                    ? "1px solid #4ade80"
                    : "1px solid rgba(51, 65, 85, 0.5)",
                background:
                  parameters.provenanceFilter === "measured_only"
                    ? "rgba(34, 197, 94, 0.2)"
                    : "rgba(15, 23, 42, 0.6)",
                color: parameters.provenanceFilter === "measured_only" ? "#4ade80" : "#94a3b8",
                cursor: "pointer",
              }}
              title="Toggle to hide model approximations and show only physically measured in-situ telemetry"
            >
              {parameters.provenanceFilter === "measured_only" ? "● Strict Measured Only" : "○ Full Physical Model"}
            </button>
          </div>

          <div style={{ width: "1px", height: "18px", background: "rgba(51, 65, 85, 0.6)" }} />

          {/* View Density */}
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 600 }}>Density:</span>
            {(["compact", "engineering"] as const).map((d) => {
              const active = parameters.viewDensity === d;
              return (
                <button
                  key={d}
                  onClick={() => onChange({ viewDensity: d })}
                  style={{
                    padding: "3px 8px",
                    borderRadius: "4px",
                    fontSize: "10px",
                    fontWeight: active ? 700 : 500,
                    border: active ? "1px solid #38bdf8" : "1px solid rgba(51, 65, 85, 0.4)",
                    background: active ? "rgba(56, 189, 248, 0.2)" : "transparent",
                    color: active ? "#38bdf8" : "#94a3b8",
                    cursor: "pointer",
                    textTransform: "capitalize",
                  }}
                >
                  {d}
                </button>
              );
            })}
          </div>

          <div style={{ width: "1px", height: "18px", background: "rgba(51, 65, 85, 0.6)" }} />

          {/* Advanced Physics Drawer Toggle Button */}
          <button
            onClick={() => setIsDrawerOpen(!isDrawerOpen)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 10px",
              borderRadius: "6px",
              fontSize: "11px",
              fontWeight: 700,
              background: isDrawerOpen ? "rgba(56, 189, 248, 0.25)" : "rgba(30, 41, 59, 0.8)",
              border: isDrawerOpen ? "1px solid #38bdf8" : "1px solid rgba(51, 65, 85, 0.6)",
              color: isDrawerOpen ? "#38bdf8" : "#f8fafc",
              cursor: "pointer",
            }}
          >
            <span>⚙️ Physical Parameters</span>
            <span style={{ fontSize: "10px" }}>{isDrawerOpen ? "▲" : "▼"}</span>
          </button>
        </div>
      </div>

      {/* Expandable Parameter Tuning Drawer */}
      <AnimatePresence>
        {isDrawerOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            style={{
              overflow: "hidden",
              borderTop: "1px solid rgba(51, 65, 85, 0.5)",
              paddingTop: "12px",
            }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: "16px",
                background: "rgba(15, 23, 42, 0.75)",
                padding: "14px 16px",
                borderRadius: "8px",
                border: "1px solid rgba(51, 65, 85, 0.4)",
              }}
            >
              {/* Parameter 1: Bulk Density */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                  <span style={{ fontSize: "11px", color: "#cbd5e1", fontWeight: 600 }}>
                    Dry Bulk Density (ρ_b):
                  </span>
                  <span style={{ fontSize: "11px", color: "#38bdf8", fontWeight: 700 }}>
                    {parameters.bulkDensity.toFixed(2)} g/cm³
                  </span>
                </div>
                <input
                  type="range"
                  min="1.00"
                  max="1.75"
                  step="0.05"
                  value={parameters.bulkDensity}
                  onChange={(e) => onChange({ bulkDensity: parseFloat(e.target.value) })}
                  style={{ width: "100%", accentColor: "#38bdf8", cursor: "pointer" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px", color: "#64748b" }}>
                  <span>1.00 (Porous)</span>
                  <span>1.75 (Compacted)</span>
                </div>
              </div>

              {/* Parameter 2: Antenna Mast Height */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                  <span style={{ fontSize: "11px", color: "#cbd5e1", fontWeight: 600 }}>
                    Antenna Phase Center (h_ant):
                  </span>
                  <span style={{ fontSize: "11px", color: "#4ade80", fontWeight: 700 }}>
                    {parameters.antennaHeightM.toFixed(2)} m
                  </span>
                </div>
                <input
                  type="range"
                  min="1.0"
                  max="4.5"
                  step="0.05"
                  value={parameters.antennaHeightM}
                  onChange={(e) => onChange({ antennaHeightM: parseFloat(e.target.value) })}
                  style={{ width: "100%", accentColor: "#4ade80", cursor: "pointer" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px", color: "#64748b" }}>
                  <span>1.0m (Low Mast)</span>
                  <span>4.5m (Tower)</span>
                </div>
              </div>

              {/* Parameter 3: Elevation Cutoff Mask */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                  <span style={{ fontSize: "11px", color: "#cbd5e1", fontWeight: 600 }}>
                    Elevation Cutoff Mask (θ_min):
                  </span>
                  <span style={{ fontSize: "11px", color: "#f59e0b", fontWeight: 700 }}>
                    {parameters.elevationMaskDeg}°
                  </span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="25"
                  step="1"
                  value={parameters.elevationMaskDeg}
                  onChange={(e) => onChange({ elevationMaskDeg: parseInt(e.target.value) })}
                  style={{ width: "100%", accentColor: "#f59e0b", cursor: "pointer" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px", color: "#64748b" }}>
                  <span>5° (Max Multi-path)</span>
                  <span>25° (Top Horizon)</span>
                </div>
              </div>

              {/* Parameter 4: Expert Persona Filter */}
              <div>
                <span style={{ fontSize: "11px", color: "#cbd5e1", fontWeight: 600, display: "block", marginBottom: "6px" }}>
                  Expert Persona Scope:
                </span>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
                  {[
                    { id: "all", label: "Full Observatory" },
                    { id: "agronomist", label: "🌱 Agronomist" },
                    { id: "rf_engineer", label: "⚡ RF Physicist" },
                    { id: "auditor", label: "⚖️ P-08 Auditor" },
                  ].map((p) => {
                    const active = parameters.expertPersona === p.id;
                    return (
                      <button
                        key={p.id}
                        onClick={() => onChange({ expertPersona: p.id as any })}
                        style={{
                          padding: "5px 8px",
                          borderRadius: "4px",
                          fontSize: "10px",
                          fontWeight: active ? 700 : 500,
                          border: active ? "1px solid #38bdf8" : "1px solid rgba(51, 65, 85, 0.4)",
                          background: active ? "rgba(56, 189, 248, 0.2)" : "rgba(30, 41, 59, 0.5)",
                          color: active ? "#38bdf8" : "#94a3b8",
                          cursor: "pointer",
                          textAlign: "left",
                        }}
                      >
                        {p.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Reset & Summary Footer */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "8px" }}>
              <span style={{ fontSize: "10px", color: "#64748b" }}>
                * Changing physical parameters immediately re-indexes Fresnel reflection coefficients, skin depth, and multipath interference periods across all tabs.
              </span>
              <button
                onClick={onReset}
                style={{
                  background: "transparent",
                  border: "1px solid rgba(239, 68, 68, 0.4)",
                  borderRadius: "4px",
                  padding: "3px 8px",
                  color: "#f87171",
                  fontSize: "10px",
                  cursor: "pointer",
                }}
              >
                Reset to Defaults
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

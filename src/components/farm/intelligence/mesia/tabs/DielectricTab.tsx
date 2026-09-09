"use client";
import React, { useState, useMemo } from "react";
import { MesiaData, MesiaParameters } from "../types";

interface DielectricTabProps {
  data: MesiaData;
  parameters: MesiaParameters;
}

export default function DielectricTab({ data, parameters }: DielectricTabProps) {
  const [selectedDepthCm, setSelectedDepthCm] = useState<number>(6.0);
  const [latticeMode, setLatticeMode] = useState<"macro" | "hd1m">("hd1m");
  const [hoveredZone, setHoveredZone] = useState<any>(null);

  const profile = data.dielectric_profile;
  const temporal = data.temporal_dynamics;
  const lattice1m = profile?.spatial_lattice_1m;

  // Determine current active horizon based on depth
  const currentHorizon = useMemo(() => {
    if (selectedDepthCm <= 1.0) {
      return { id: 1, name: "Horizon 1: Surface Crust (0-1 cm)", vwc: profile?.horizon_0_1cm_vwc_pct ?? 18.5, col: "#38bdf8" };
    }
    if (selectedDepthCm <= 3.0) {
      return { id: 2, name: "Horizon 2: Boundary Layer (1-3 cm)", vwc: profile?.horizon_1_3cm_vwc_pct ?? 20.2, col: "#4ade80" };
    }
    if (selectedDepthCm <= 9.0) {
      return { id: 3, name: "Horizon 3: Active Root Core (3-9 cm)", vwc: profile?.horizon_3_9cm_vwc_pct ?? 22.8, col: "#a78bfa" };
    }
    return { id: 4, name: "Horizon 4: Deep Subsoil (9-27 cm)", vwc: profile?.horizon_9_27cm_vwc_pct ?? 26.4, col: "#f59e0b" };
  }, [selectedDepthCm, profile]);

  // Compute dielectric permittivity based on selected model and parameters
  const dielectricComputed = useMemo(() => {
    const theta = currentHorizon.vwc / 100.0;
    const rho_b = parameters.bulkDensity;

    let eps_real = 12.5;
    let modelCitation = "Dobson et al. (1985)";

    if (parameters.dielectricModel === "topp") {
      // Topp Universal Polynomial Model (1980)
      eps_real = 3.03 + 9.3 * theta + 146.0 * (theta ** 2) - 76.7 * (theta ** 3);
      modelCitation = "Topp et al. (1980) Empirical Polynomial";
    } else if (parameters.dielectricModel === "mironov") {
      // Mironov Refractive Dielectric Model (2013)
      const nd = 1.634; // dry soil refractive index
      const nw = 8.92; // free water refractive index
      const theta_t = 0.08; // bound water transition
      if (theta <= theta_t) {
        eps_real = (nd + (nw - 1.0) * theta) ** 2;
      } else {
        eps_real = (nd + (nw - 1.0) * theta_t + (nw - 1.0) * (theta - theta_t)) ** 2;
      }
      modelCitation = "Mironov Generalized Refractive Model (2013)";
    } else {
      // Dobson Semi-Empirical Mixing Model (1985)
      const alpha = 0.65;
      const eps_s = 4.7; // solid soil mineral permittivity
      eps_real = (1.0 + (rho_b / 2.65) * (eps_s ** alpha - 1.0) + (theta ** 1.02) * (80.0 ** alpha - 1.0)) ** (1.0 / alpha);
      modelCitation = "Dobson 4-Component Semi-Empirical (1985)";
    }

    const eps_imag = eps_real * 0.14; // Typical loss tangent
    const cond_s_m = (eps_imag * 1575.42e6) / 1.7975e10;

    return {
      eps_real: Math.max(2.5, Math.min(65.0, eps_real)),
      eps_imag: Math.max(0.1, eps_imag),
      cond_s_m: Math.max(0.001, cond_s_m),
      modelCitation,
    };
  }, [currentHorizon, parameters.dielectricModel, parameters.bulkDensity]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* 1. 2.5D Volumetric Soil Horizon Strata Cutaway */}
      <div
        style={{
          background: "rgba(15, 23, 42, 0.85)",
          border: "1px solid rgba(56, 189, 248, 0.35)",
          borderRadius: "14px",
          padding: "18px 20px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
          <div>
            <div style={{ fontSize: "14px", fontWeight: 700, color: "#38bdf8" }}>
              🌱 2.5D Soil Horizon Strata & Dielectric Inversion
            </div>
            <div style={{ fontSize: "11px", color: "#94a3b8" }}>
              Model: <strong style={{ color: "#f8fafc" }}>{dielectricComputed.modelCitation}</strong> | Soil: {parameters.soilTexture} (ρ_b = {parameters.bulkDensity.toFixed(2)} g/cm³)
            </div>
          </div>

          {/* Quick Horizon Buttons */}
          <div style={{ display: "flex", gap: "6px" }}>
            {[
              { depth: 0.5, label: "H1: 0-1cm", col: "#38bdf8" },
              { depth: 2.0, label: "H2: 1-3cm", col: "#4ade80" },
              { depth: 6.0, label: "H3: 3-9cm", col: "#a78bfa" },
              { depth: 18.0, label: "H4: 9-27cm", col: "#f59e0b" },
            ].map((h) => {
              const isSel = Math.abs(selectedDepthCm - h.depth) < 1.5;
              return (
                <button
                  key={h.depth}
                  onClick={() => setSelectedDepthCm(h.depth)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "6px",
                    border: isSel ? `1px solid ${h.col}` : "1px solid rgba(51, 65, 85, 0.5)",
                    background: isSel ? "rgba(30, 41, 59, 0.8)" : "rgba(15, 23, 42, 0.5)",
                    color: isSel ? h.col : "#94a3b8",
                    fontSize: "10px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {h.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Isometric SVG Diagram & Dielectric Metrics Box */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "20px", alignItems: "center" }}>
          {/* Isometric Cutaway Graphic */}
          <div style={{ background: "rgba(10, 15, 30, 0.95)", borderRadius: "10px", padding: "14px", border: "1px solid rgba(51, 65, 85, 0.5)" }}>
            <svg width="100%" height="200" viewBox="0 0 540 200">
              {/* Horizon 4 */}
              <g
                onClick={() => setSelectedDepthCm(18)}
                style={{ cursor: "pointer", opacity: currentHorizon.id === 4 ? 1 : 0.6 }}
              >
                <polygon points="120,155 420,155 470,130 170,130" fill="rgba(245, 158, 11, 0.35)" stroke="#f59e0b" strokeWidth={currentHorizon.id === 4 ? "2" : "1"} />
                <polygon points="120,155 120,175 420,175 420,155" fill="rgba(180, 83, 9, 0.4)" stroke="#f59e0b" strokeWidth="1" />
                <polygon points="420,175 470,150 470,130 420,155" fill="rgba(146, 64, 14, 0.5)" stroke="#f59e0b" strokeWidth="1" />
                <text x="270" y="168" fill="#f8fafc" fontSize="10" fontWeight="700" textAnchor="middle">
                  Horizon 4: Deep Subsoil (9 – 27 cm) • {profile?.horizon_9_27cm_vwc_pct ?? 26.4}% VWC
                </text>
              </g>

              {/* Horizon 3 */}
              <g
                onClick={() => setSelectedDepthCm(6)}
                style={{ cursor: "pointer", opacity: currentHorizon.id === 3 ? 1 : 0.6 }}
              >
                <polygon points="120,115 420,115 470,90 170,90" fill="rgba(167, 139, 250, 0.35)" stroke="#a78bfa" strokeWidth={currentHorizon.id === 3 ? "2" : "1"} />
                <polygon points="120,115 120,130 420,130 420,115" fill="rgba(124, 58, 237, 0.4)" stroke="#a78bfa" strokeWidth="1" />
                <polygon points="420,130 470,105 470,90 420,115" fill="rgba(109, 40, 217, 0.5)" stroke="#a78bfa" strokeWidth="1" />
                <text x="270" y="125" fill="#f8fafc" fontSize="10" fontWeight="700" textAnchor="middle">
                  Horizon 3: Active Root Core (3 – 9 cm) • {profile?.horizon_3_9cm_vwc_pct ?? 22.8}% VWC
                </text>
              </g>

              {/* Horizon 2 */}
              <g
                onClick={() => setSelectedDepthCm(2)}
                style={{ cursor: "pointer", opacity: currentHorizon.id === 2 ? 1 : 0.6 }}
              >
                <polygon points="120,75 420,75 470,50 170,50" fill="rgba(74, 222, 128, 0.35)" stroke="#4ade80" strokeWidth={currentHorizon.id === 2 ? "2" : "1"} />
                <polygon points="120,75 120,90 420,90 420,75" fill="rgba(22, 163, 74, 0.4)" stroke="#4ade80" strokeWidth="1" />
                <polygon points="420,90 470,65 470,50 420,75" fill="rgba(21, 128, 61, 0.5)" stroke="#4ade80" strokeWidth="1" />
                <text x="270" y="85" fill="#f8fafc" fontSize="10" fontWeight="700" textAnchor="middle">
                  Horizon 2: Boundary Layer (1 – 3 cm) • {profile?.horizon_1_3cm_vwc_pct ?? 20.2}% VWC
                </text>
              </g>

              {/* Horizon 1 */}
              <g
                onClick={() => setSelectedDepthCm(0.5)}
                style={{ cursor: "pointer", opacity: currentHorizon.id === 1 ? 1 : 0.6 }}
              >
                <polygon points="120,35 420,35 470,10 170,10" fill="rgba(56, 189, 248, 0.35)" stroke="#38bdf8" strokeWidth={currentHorizon.id === 1 ? "2" : "1"} />
                <polygon points="120,35 120,50 420,50 420,35" fill="rgba(2, 132, 199, 0.4)" stroke="#38bdf8" strokeWidth="1" />
                <polygon points="420,50 470,25 470,10 420,35" fill="rgba(3, 105, 161, 0.5)" stroke="#38bdf8" strokeWidth="1" />
                <text x="270" y="45" fill="#f8fafc" fontSize="10" fontWeight="700" textAnchor="middle">
                  Horizon 1: Surface Crust (0 – 1 cm) • {profile?.horizon_0_1cm_vwc_pct ?? 18.5}% VWC
                </text>
              </g>
            </svg>
          </div>

          {/* Real-Time Dielectric Metrics Card */}
          <div style={{ background: "rgba(18, 26, 43, 0.85)", border: `1px solid ${currentHorizon.col}`, borderRadius: "10px", padding: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "11px", fontWeight: 700, color: currentHorizon.col }}>
                ACTIVE LAYER ANALYSIS
              </span>
              <span style={{ fontSize: "10px", color: "#94a3b8" }}>Depth: {selectedDepthCm.toFixed(1)} cm</span>
            </div>

            <div style={{ fontSize: "13px", fontWeight: 700, color: "#f8fafc" }}>
              {currentHorizon.name}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginTop: "4px" }}>
              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "8px", borderRadius: "6px" }}>
                <div style={{ fontSize: "10px", color: "#94a3b8" }}>Volumetric Water (θ):</div>
                <div style={{ fontSize: "16px", fontWeight: 700, color: currentHorizon.col }}>
                  {currentHorizon.vwc.toFixed(1)}%
                </div>
              </div>

              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "8px", borderRadius: "6px" }}>
                <div style={{ fontSize: "10px", color: "#94a3b8" }}>Real Permittivity (ε'):</div>
                <div style={{ fontSize: "16px", fontWeight: 700, color: "#38bdf8" }}>
                  {dielectricComputed.eps_real.toFixed(2)}
                </div>
              </div>

              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "8px", borderRadius: "6px" }}>
                <div style={{ fontSize: "10px", color: "#94a3b8" }}>Loss Factor (ε''):</div>
                <div style={{ fontSize: "14px", fontWeight: 600, color: "#f59e0b" }}>
                  {dielectricComputed.eps_imag.toFixed(2)}
                </div>
              </div>

              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "8px", borderRadius: "6px" }}>
                <div style={{ fontSize: "10px", color: "#94a3b8" }}>Conductivity (σ):</div>
                <div style={{ fontSize: "14px", fontWeight: 600, color: "#cbd5e1" }}>
                  {(dielectricComputed.cond_s_m * 1000).toFixed(1)} mS/m
                </div>
              </div>
            </div>

            <div style={{ fontSize: "10px", color: "#94a3b8", borderTop: "1px solid rgba(51, 65, 85, 0.4)", paddingTop: "8px" }}>
              Calculated via <strong>{parameters.dielectricModel.toUpperCase()}</strong> model. Free water boundary temperature: 20°C.
            </div>
          </div>
        </div>
      </div>

      {/* 2. Microzone Tomography & 1m Spatial Lattice */}
      <div
        style={{
          background: "rgba(15, 23, 42, 0.85)",
          border: "1px solid rgba(51, 65, 85, 0.6)",
          borderRadius: "14px",
          padding: "18px 20px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
          <div>
            <div style={{ fontSize: "14px", fontWeight: 700, color: "#f8fafc" }}>
              🗺️ Spatial Dielectric Permittivity Lattice
            </div>
            <div style={{ fontSize: "10px", color: "#94a3b8" }}>
              Continuous spatial root-zone moisture field inverted from cellular & satellite forward models
            </div>
          </div>

          {/* Mode Switcher */}
          <div style={{ display: "flex", gap: "6px" }}>
            <button
              onClick={() => setLatticeMode("hd1m")}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                border: latticeMode === "hd1m" ? "1px solid #38bdf8" : "1px solid rgba(51, 65, 85, 0.5)",
                background: latticeMode === "hd1m" ? "rgba(56, 189, 248, 0.2)" : "rgba(15, 23, 42, 0.6)",
                color: latticeMode === "hd1m" ? "#38bdf8" : "#94a3b8",
                fontSize: "11px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              1m High-Definition Lattice
            </button>
            <button
              onClick={() => setLatticeMode("macro")}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                border: latticeMode === "macro" ? "1px solid #4ade80" : "1px solid rgba(51, 65, 85, 0.5)",
                background: latticeMode === "macro" ? "rgba(34, 197, 94, 0.2)" : "rgba(15, 23, 42, 0.6)",
                color: latticeMode === "macro" ? "#4ade80" : "#94a3b8",
                fontSize: "11px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Macro Microzones (36 Cells)
            </button>
          </div>
        </div>

        {latticeMode === "hd1m" && lattice1m ? (
          <div>
            {/* 1m Lattice Summary Bar */}
            <div style={{ display: "flex", justifyContent: "space-between", background: "rgba(30, 41, 59, 0.4)", padding: "8px 12px", borderRadius: "8px", marginBottom: "12px", fontSize: "11px", color: "#cbd5e1" }}>
              <span>Dimensions: <strong>{lattice1m.dimensions.cols} × {lattice1m.dimensions.rows} pixels (1m res)</strong></span>
              <span>Min VWC: <strong>{lattice1m.stats.min_root_vwc_pct.toFixed(1)}%</strong></span>
              <span>Mean VWC: <strong style={{ color: "#38bdf8" }}>{lattice1m.stats.mean_root_vwc_pct.toFixed(1)}%</strong></span>
              <span>Max VWC: <strong>{lattice1m.stats.max_root_vwc_pct.toFixed(1)}%</strong></span>
              <span style={{ color: "#4ade80", fontWeight: 700 }}>✓ ASMAE Model-Assisted Lattice</span>
            </div>

            {/* Heatmap visualization grid */}
            <div style={{ display: "grid", gridTemplateColumns: `repeat(${lattice1m.dimensions.cols}, 1fr)`, gap: "2px", maxHeight: "240px", overflow: "auto", background: "rgba(10, 15, 30, 0.9)", padding: "8px", borderRadius: "8px" }}>
              {lattice1m.root_zone_vwc_grid.map((row, rIdx) =>
                row.map((val, cIdx) => {
                  const min = lattice1m.stats.min_root_vwc_pct;
                  const max = lattice1m.stats.max_root_vwc_pct;
                  const norm = max > min ? (val - min) / (max - min) : 0.5;
                  const r = Math.round(30 + norm * 30);
                  const g = Math.round(80 + norm * 110);
                  const b = Math.round(150 + norm * 105);

                  return (
                    <div
                      key={`${rIdx}-${cIdx}`}
                      title={`Pixel (${cIdx}, ${rIdx}): ${val.toFixed(2)}% VWC`}
                      style={{
                        height: "14px",
                        borderRadius: "2px",
                        background: `rgb(${r}, ${g}, ${b})`,
                      }}
                    />
                  );
                })
              )}
            </div>
          </div>
        ) : (
          /* Macro 36-zone Grid */
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "8px" }}>
            {profile?.spatial_microzones?.map((zone) => {
              const isHovered = hoveredZone?.microzone_id === zone.microzone_id;
              return (
                <div
                  key={zone.microzone_id}
                  onMouseEnter={() => setHoveredZone(zone)}
                  onMouseLeave={() => setHoveredZone(null)}
                  style={{
                    background: isHovered ? "rgba(56, 189, 248, 0.25)" : "rgba(30, 41, 59, 0.5)",
                    border: isHovered ? "1px solid #38bdf8" : "1px solid rgba(51, 65, 85, 0.4)",
                    borderRadius: "8px",
                    padding: "10px",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div style={{ fontSize: "10px", color: "#94a3b8", display: "flex", justifyContent: "space-between" }}>
                    <span>{zone.microzone_id}</span>
                    <span style={{ color: "#38bdf8" }}>({zone.grid_x},{zone.grid_y})</span>
                  </div>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#f8fafc", margin: "4px 0" }}>
                    {zone.soil_vwc_pct.toFixed(1)}% VWC
                  </div>
                  <div style={{ fontSize: "10px", color: "#cbd5e1" }}>
                    ε_r = {zone.dielectric_eps_r.toFixed(1)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 3. Hydrological Diurnal Drying & Flux Summary */}
      {temporal && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "16px" }}>
          <div style={{ background: "rgba(18, 26, 43, 0.75)", border: "1px solid rgba(51, 65, 85, 0.5)", borderRadius: "10px", padding: "14px" }}>
            <span style={{ fontSize: "11px", color: "#94a3b8" }}>Diurnal Phase:</span>
            <div style={{ fontSize: "14px", fontWeight: 700, color: "#38bdf8", marginTop: "2px" }}>
              {temporal.diurnal_phase}
            </div>
            <div style={{ fontSize: "10px", color: "#64748b", marginTop: "4px" }}>
              Local Solar Time: {temporal.local_solar_time} (Zenith {temporal.solar_zenith_deg.toFixed(1)}°)
            </div>
          </div>

          <div style={{ background: "rgba(18, 26, 43, 0.75)", border: "1px solid rgba(51, 65, 85, 0.5)", borderRadius: "10px", padding: "14px" }}>
            <span style={{ fontSize: "11px", color: "#94a3b8" }}>Soil Drying Rate:</span>
            <div style={{ fontSize: "14px", fontWeight: 700, color: "#4ade80", marginTop: "2px" }}>
              {temporal.drying_rate_pct_per_day.toFixed(2)}% VWC / day
            </div>
            <div style={{ fontSize: "10px", color: "#64748b", marginTop: "4px" }}>
              Concordant with Penman-Monteith potential evapotranspiration ETc
            </div>
          </div>

          <div style={{ background: "rgba(18, 26, 43, 0.75)", border: "1px solid rgba(51, 65, 85, 0.5)", borderRadius: "10px", padding: "14px" }}>
            <span style={{ fontSize: "11px", color: "#94a3b8" }}>Equivalent Water Flux:</span>
            <div style={{ fontSize: "14px", fontWeight: 700, color: "#f59e0b", marginTop: "2px" }}>
              {temporal.equivalent_water_flux_mm_day.toFixed(2)} mm / day
            </div>
            <div style={{ fontSize: "10px", color: "#64748b", marginTop: "4px" }}>
              Hydrological Regime: {temporal.hydrological_regime}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

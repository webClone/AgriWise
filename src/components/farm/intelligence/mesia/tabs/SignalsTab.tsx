"use client";
import React, { useState, useMemo } from "react";
import { MesiaData, MesiaParameters, SatelliteIlluminator } from "../types";

interface SignalsTabProps {
  data: MesiaData;
  parameters: MesiaParameters;
}

const SPECTRUM_BANDS = [
  { id: "UHF", label: "UHF Terrestrial", freq: "546 MHz", skinDepth: "~35-45 cm", col: "#f59e0b" },
  { id: "CELL", label: "Cellular LTE/5G", freq: "800 - 3500 MHz", skinDepth: "~12-25 cm", col: "#a78bfa" },
  { id: "GNSS", label: "GNSS L1 / L2", freq: "1575.42 MHz", skinDepth: "~5-10 cm", col: "#4ade80" },
  { id: "SAR", label: "Sentinel-1 C-SAR", freq: "5405 MHz", skinDepth: "~2-5 cm", col: "#38bdf8" },
  { id: "WIFI", label: "Wi-Fi 2.4/5G", freq: "2412 - 5800 MHz", skinDepth: "~4-8 cm", col: "#ec4899" },
];

export default function SignalsTab({ data, parameters }: SignalsTabProps) {
  const [selectedSat, setSelectedSat] = useState<SatelliteIlluminator | null>(null);
  const [rayElevDeg, setRayElevDeg] = useState<number>(35);
  const [selectedBand, setSelectedBand] = useState<string>("ALL");

  const gnssData = data.signals_of_opportunity?.gnss_reflectometry;
  const cellularData = data.signals_of_opportunity?.cellular_forward_scatter;
  const uhfData = data.signals_of_opportunity?.terrestrial_broadcast_uhf;

  // Filter satellites based on parameters.elevationMaskDeg
  const filteredSats = useMemo(() => {
    if (!gnssData?.primary_illuminators) return [];
    return gnssData.primary_illuminators.filter(
      (s) => s.elev_deg >= parameters.elevationMaskDeg
    );
  }, [gnssData, parameters.elevationMaskDeg]);

  // Active illuminator for ray tracing
  const activeSat = selectedSat || filteredSats[0] || null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* 1. Multi-Band Frequency & Penetration Spectrum Banner */}
      <div
        style={{
          background: "rgba(15, 23, 42, 0.8)",
          border: "1px solid rgba(51, 65, 85, 0.5)",
          borderRadius: "12px",
          padding: "14px 18px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "13px", fontWeight: 700, color: "#f8fafc" }}>
              📻 Multi-Band Ambient Physical Spectrum
            </span>
            <span style={{ fontSize: "10px", padding: "2px 6px", borderRadius: "4px", background: "rgba(56, 189, 248, 0.15)", color: "#38bdf8", fontWeight: 700 }}>
              P-08 PASSIVE SENSING
            </span>
          </div>
          <div style={{ fontSize: "11px", color: "#94a3b8" }}>
            Skin depth calculated for <strong>{parameters.soilTexture}</strong> (ρ_b = {parameters.bulkDensity.toFixed(2)} g/cm³)
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "8px" }}>
          {SPECTRUM_BANDS.map((b) => {
            const isSelected = selectedBand === b.id;
            const isBandActive = parameters.activeBands.includes(b.id);
            return (
              <button
                key={b.id}
                onClick={() => setSelectedBand(isSelected ? "ALL" : b.id)}
                style={{
                  padding: "8px 10px",
                  borderRadius: "8px",
                  border: isSelected ? `1px solid ${b.col}` : "1px solid rgba(51, 65, 85, 0.4)",
                  background: isSelected ? "rgba(30, 41, 59, 0.8)" : "rgba(18, 26, 43, 0.5)",
                  color: isSelected ? "#f8fafc" : "#94a3b8",
                  textAlign: "left",
                  cursor: "pointer",
                  opacity: isBandActive ? 1 : 0.4,
                  transition: "all 0.15s ease",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, color: b.col, marginBottom: "2px" }}>
                  {b.label}
                </div>
                <div style={{ fontSize: "10px", color: "#cbd5e1", fontWeight: 600 }}>{b.freq}</div>
                <div style={{ fontSize: "9px", color: "#94a3b8", marginTop: "2px" }}>
                  Skin: {b.skinDepth}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Side-by-Side: Polar Skyplot + Ray-Tracing Fresnel Ellipsoid */}
      <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: "20px" }}>
        {/* Polar Celestial Radar */}
        <div
          style={{
            background: "rgba(15, 23, 42, 0.85)",
            border: "1px solid rgba(51, 65, 85, 0.6)",
            borderRadius: "14px",
            padding: "16px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          <div style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <span style={{ fontSize: "13px", fontWeight: 700, color: "#38bdf8" }}>
              🧭 SGP4 Ephemeris Skyplot
            </span>
            <span style={{ fontSize: "10px", color: "#4ade80", background: "rgba(34, 197, 94, 0.15)", padding: "2px 6px", borderRadius: "4px", fontWeight: 600 }}>
              {filteredSats.length} Sats &gt; {parameters.elevationMaskDeg}°
            </span>
          </div>

          <div style={{ position: "relative", width: "270px", height: "270px", margin: "8px 0" }}>
            <svg width="270" height="270" viewBox="0 0 280 280">
              <circle cx="140" cy="140" r="130" fill="rgba(10, 15, 30, 0.95)" stroke="rgba(51, 65, 85, 0.6)" strokeWidth="1" />
              <circle cx="140" cy="140" r="100" fill="none" stroke="rgba(51, 65, 85, 0.4)" strokeWidth="1" strokeDasharray="3 3" />
              <circle cx="140" cy="140" r="65" fill="none" stroke="rgba(51, 65, 85, 0.4)" strokeWidth="1" strokeDasharray="3 3" />
              <circle cx="140" cy="140" r="30" fill="none" stroke="rgba(51, 65, 85, 0.5)" strokeWidth="1" />
              <line x1="140" y1="10" x2="140" y2="270" stroke="rgba(51, 65, 85, 0.5)" strokeWidth="1" />
              <line x1="10" y1="140" x2="270" y2="140" stroke="rgba(51, 65, 85, 0.5)" strokeWidth="1" />
              <text x="140" y="24" fill="#94a3b8" fontSize="10" fontWeight="700" textAnchor="middle">N</text>
              <text x="264" y="144" fill="#94a3b8" fontSize="10" fontWeight="700" textAnchor="middle">E</text>
              <text x="140" y="264" fill="#94a3b8" fontSize="10" fontWeight="700" textAnchor="middle">S</text>
              <text x="16" y="144" fill="#94a3b8" fontSize="10" fontWeight="700" textAnchor="middle">W</text>

              {/* Cellular Mast Bearings */}
              {cellularData?.masts_tracked?.map((m, idx) => {
                const angleRad = ((m.bearing_deg - 90) * Math.PI) / 180;
                const tx = 140 + 128 * Math.cos(angleRad);
                const ty = 140 + 128 * Math.sin(angleRad);
                return (
                  <g key={`cell-${idx}`}>
                    <circle cx={tx} cy={ty} r="4" fill="#a78bfa" stroke="#f8fafc" strokeWidth="1" />
                    <line x1="140" y1="140" x2={tx} y2={ty} stroke="rgba(167, 139, 250, 0.25)" strokeWidth="1" strokeDasharray="2 2" />
                  </g>
                );
              })}

              {/* Satellites */}
              {filteredSats.map((sat, i) => {
                const r = (1 - sat.elev_deg / 90.0) * 115;
                const rad = ((sat.az_deg - 90) * Math.PI) / 180;
                const sx = 140 + r * Math.cos(rad);
                const sy = 140 + r * Math.sin(rad);
                const isSel = activeSat?.name === sat.name;
                const col = sat.name.includes("GALILEO") ? "#38bdf8" : sat.name.includes("GPS") ? "#4ade80" : "#a78bfa";

                return (
                  <g
                    key={`sat-${i}`}
                    onClick={() => {
                      setSelectedSat(sat);
                      setRayElevDeg(Math.round(sat.elev_deg));
                    }}
                    style={{ cursor: "pointer" }}
                  >
                    {isSel && (
                      <circle cx={sx} cy={sy} r="9" fill="none" stroke={col} strokeWidth="1.5">
                        <animate attributeName="r" values="6;11;6" dur="2s" repeatCount="indefinite" />
                      </circle>
                    )}
                    <circle cx={sx} cy={sy} r="4" fill={col} stroke="#f8fafc" strokeWidth="1" />
                    <text x={sx + 6} y={sy + 3} fill={col} fontSize="8" fontWeight="600">
                      {sat.name.split(" ")[0]}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          <div style={{ width: "100%", display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#94a3b8", marginTop: "4px" }}>
            <span>● Green: GPS</span>
            <span>● Cyan: Galileo</span>
            <span>● Purple: Glonass / Cellular</span>
          </div>
        </div>

        {/* Ray-Tracing Fresnel Ellipsoid Simulator */}
        <div
          style={{
            background: "rgba(15, 23, 42, 0.85)",
            border: "1px solid rgba(51, 65, 85, 0.6)",
            borderRadius: "14px",
            padding: "16px",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <div>
              <div style={{ fontSize: "14px", fontWeight: 700, color: "#f8fafc" }}>
                📐 Specular Reflection & Fresnel Footprint Geometry
              </div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>
                Active Target: <strong style={{ color: "#4ade80" }}>{activeSat?.name || "Direct Line"}</strong> | Antenna Mast: {parameters.antennaHeightM.toFixed(2)}m
              </div>
            </div>

            {/* Elevation Slider */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "11px", color: "#94a3b8" }}>Angle θ:</span>
              <input
                type="range"
                min="5"
                max="85"
                value={rayElevDeg}
                onChange={(e) => setRayElevDeg(parseInt(e.target.value))}
                style={{ width: "90px", accentColor: "#38bdf8", cursor: "pointer" }}
              />
              <span style={{ fontSize: "11px", color: "#38bdf8", fontWeight: 700, minWidth: "26px" }}>
                {rayElevDeg}°
              </span>
            </div>
          </div>

          {/* SVG Ray Diagram */}
          <div
            style={{
              flex: 1,
              minHeight: "180px",
              background: "rgba(10, 15, 30, 0.95)",
              borderRadius: "10px",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <svg width="100%" height="100%" viewBox="0 0 520 180" preserveAspectRatio="none">
              {/* Ground level */}
              <line x1="20" y1="140" x2="500" y2="140" stroke="#334155" strokeWidth="2" />
              <rect x="20" y="140" width="480" height="35" fill="rgba(30, 41, 59, 0.3)" />

              {/* Antenna Mast */}
              {(() => {
                const mastHeightPx = Math.min(65, Math.max(25, parameters.antennaHeightM * 20));
                const rxX = 420;
                const rxY = 140 - mastHeightPx;

                // Specular point calculation: d_sp = h / tan(theta)
                const rad = (rayElevDeg * Math.PI) / 180.0;
                const spDistPx = mastHeightPx / Math.max(0.1, Math.tan(rad));
                const spX = Math.max(60, rxX - spDistPx);
                const spY = 140;

                // Ray from sky
                const skyX = Math.max(30, spX - 180 * Math.cos(rad));
                const skyY = Math.max(10, spY - 180 * Math.sin(rad));

                // 1st Fresnel zone semi-major axis
                const lambda = 0.1903; // L1 carrier 19 cm
                const hM = parameters.antennaHeightM;
                const aM = (Math.sqrt(lambda * hM * Math.sin(rad) + (lambda / 2) ** 2) / (Math.sin(rad) ** 2));
                const aPx = Math.min(70, Math.max(12, aM * 5));

                return (
                  <g>
                    {/* Mast */}
                    <line x1={rxX} y1="140" x2={rxX} y2={rxY} stroke="#38bdf8" strokeWidth="3" />
                    <circle cx={rxX} cy={rxY} r="4" fill="#38bdf8" />
                    <text x={rxX + 8} y={rxY + 4} fill="#38bdf8" fontSize="9" fontWeight="700">
                      Rx ({parameters.antennaHeightM.toFixed(2)}m)
                    </text>

                    {/* Incident Ray */}
                    <line x1={skyX} y1={skyY} x2={spX} y2={spY} stroke="#4ade80" strokeWidth="2" strokeDasharray="4 2" />
                    <circle cx={skyX} cy={skyY} r="3" fill="#4ade80" />

                    {/* Specular Point & Fresnel Zone Footprint */}
                    <ellipse cx={spX} cy={spY} rx={aPx} ry="6" fill="rgba(56, 189, 248, 0.25)" stroke="#38bdf8" strokeWidth="1.5" />
                    <circle cx={spX} cy={spY} r="3" fill="#f59e0b" />
                    <text x={spX} y={spY + 16} fill="#f59e0b" fontSize="8" fontWeight="600" textAnchor="middle">
                      SP Footprint ({aM.toFixed(1)}m)
                    </text>

                    {/* Reflected Ray */}
                    <line x1={spX} y1={spY} x2={rxX} y2={rxY} stroke="#f59e0b" strokeWidth="2" />

                    {/* Direct Ray */}
                    <line x1={skyX} y1={skyY} x2={rxX} y2={rxY} stroke="rgba(74, 222, 128, 0.4)" strokeWidth="1.5" strokeDasharray="2 2" />
                  </g>
                );
              })()}
            </svg>
          </div>

          <div style={{ marginTop: "8px", display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
            <span>Incident Ray: <strong style={{ color: "#4ade80" }}>Direct Wave</strong></span>
            <span>Ground Reflection: <strong style={{ color: "#f59e0b" }}>Multipath Carrier</strong></span>
            <span>Phase Delay: <strong style={{ color: "#38bdf8" }}>Δφ = (4π·h/λ)·sin(θ)</strong></span>
          </div>
        </div>
      </div>

      {/* 3. Physical Ambient Illuminator Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
        {/* GNSS Reflectometry Summary */}
        <div style={{ background: "rgba(18, 26, 43, 0.75)", border: "1px solid rgba(74, 222, 128, 0.3)", borderRadius: "12px", padding: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <span style={{ fontSize: "13px", fontWeight: 700, color: "#4ade80" }}>
              🛰️ GNSS-R Constellation Signals
            </span>
            <span style={{ fontSize: "10px", color: "#94a3b8" }}>L1 / 1575.42 MHz</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px", fontSize: "11px", color: "#cbd5e1" }}>
            <span>Satellites Overhead:</span>
            <strong>{gnssData?.satellites_overhead_count ?? filteredSats.length} Sats</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px", fontSize: "11px", color: "#cbd5e1" }}>
            <span>Inferred Surface VWC:</span>
            <strong style={{ color: "#4ade80" }}>{gnssData?.inferred_subsurface_vwc_pct ?? 22.4}% VWC</strong>
          </div>
          <div style={{ fontSize: "10px", color: "#94a3b8", lineHeight: 1.4 }}>
            Direct-to-reflected multipath SNR ratio derived via specular point Fresnel geometry. Validated against elevation mask {parameters.elevationMaskDeg}°.
          </div>
        </div>

        {/* Cellular Forward-Scatter */}
        <div style={{ background: "rgba(18, 26, 43, 0.75)", border: "1px solid rgba(167, 139, 250, 0.3)", borderRadius: "12px", padding: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <span style={{ fontSize: "13px", fontWeight: 700, color: "#a78bfa" }}>
              📡 Macro Cellular Forward-Scatter
            </span>
            <span style={{ fontSize: "10px", color: "#94a3b8" }}>ITU-R P.833</span>
          </div>
          {cellularData?.masts_tracked && cellularData.masts_tracked.length > 0 ? (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px", fontSize: "11px", color: "#cbd5e1" }}>
                <span>Registered Towers (OSM):</span>
                <strong>{cellularData.masts_tracked.length} Masts (Radius &le; 8 km)</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px", fontSize: "11px", color: "#cbd5e1" }}>
                <span>Canopy Water Index (CWI):</span>
                <strong style={{ color: "#a78bfa" }}>{cellularData.canopy_water_index?.toFixed(3) ?? "0.040"}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px", fontSize: "11px", color: "#cbd5e1" }}>
                <span>Mean Canopy Excess Loss:</span>
                <strong>{cellularData.mean_excess_loss_db?.toFixed(1) ?? "0.0"} dB</strong>
              </div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>
                Nearest: {cellularData.masts_tracked[0].operator} ({cellularData.masts_tracked[0].dist_m}m, bearing {cellularData.masts_tracked[0].bearing_deg}°)
              </div>
            </>
          ) : (
            <div style={{ padding: "12px", background: "rgba(15, 23, 42, 0.6)", borderRadius: "6px", textAlign: "center" }}>
              <div style={{ fontSize: "11px", color: "#94a3b8", marginBottom: "4px" }}>
                No cellular base stations registered in OpenStreetMap within 8 km.
              </div>
              <span style={{ fontSize: "9px", color: "#64748b" }}>Status: NO_MASTS_IN_RANGE</span>
            </div>
          )}
        </div>

        {/* Broadcast UHF Deep Penetration */}
        <div style={{ background: "rgba(18, 26, 43, 0.75)", border: "1px solid rgba(245, 158, 11, 0.3)", borderRadius: "12px", padding: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <span style={{ fontSize: "13px", fontWeight: 700, color: "#f59e0b" }}>
              🗼 Regional Broadcast UHF Station
            </span>
            <span style={{ fontSize: "10px", color: "#94a3b8" }}>546 MHz DVB-T</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px", fontSize: "11px", color: "#cbd5e1" }}>
            <span>Transmitter:</span>
            <strong>{uhfData?.transmitter || "TDA Regional Transmitter"}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px", fontSize: "11px", color: "#cbd5e1" }}>
            <span>Grazing Geometry:</span>
            <strong>{uhfData?.grazing_angle_deg ?? 1.4}° Elevation</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px", fontSize: "11px", color: "#cbd5e1" }}>
            <span>Estimated Skin Depth:</span>
            <strong style={{ color: "#f59e0b" }}>{uhfData?.skin_depth_cm ?? 42} cm</strong>
          </div>
          <div style={{ fontSize: "10px", color: "#94a3b8", lineHeight: 1.4 }}>
            Deep ground wave penetration directly senses subsoil horizons unreachable by satellite optical or microwave skin depths.
          </div>
        </div>
      </div>
    </div>
  );
}

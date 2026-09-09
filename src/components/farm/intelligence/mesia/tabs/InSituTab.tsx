"use client";
import React, { useState, useRef } from "react";
import { MesiaData, MesiaParameters } from "../types";

interface InSituTabProps {
  data: MesiaData;
  parameters: MesiaParameters;
  onRefresh: () => void;
}

export default function InSituTab({ data, parameters, onRefresh }: InSituTabProps) {
  const [selectedPol, setSelectedPol] = useState<"VV" | "VH" | "RHCP" | "LHCP">("VV");
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const sigmfInputRef = useRef<HTMLInputElement>(null);

  const inSituGnss = data.radio_wave_channels?.in_situ_ground_receiver;
  const inSituWifi = data.radio_wave_channels?.in_situ_wifi_receiver;
  const oranData = data.signals_of_opportunity?.cellular_forward_scatter?.oran_e2_telemetry;
  const fleetData = data.fleet_health;

  // Real-time Fresnel reflection calculation from parcel soil permittivity
  const eps_r = data.dielectric_profile?.mean_dielectric_permittivity_eps_r ?? 14.5;
  const thetaRad = (45.0 * Math.PI) / 180.0;
  const sinTheta = Math.sin(thetaRad);
  const cosTheta = Math.cos(thetaRad);
  const u = Math.sqrt(Math.max(0.1, eps_r - sinTheta ** 2));

  const r_vv = Math.abs((eps_r * cosTheta - u) / (eps_r * cosTheta + u));
  const r_hh = Math.abs((cosTheta - u) / (cosTheta + u));
  const r_lhcp = Math.abs((r_vv - r_hh) / 2.0);
  const r_rhcp = Math.abs((r_vv + r_hh) / 2.0);

  // File Upload Handlers
  const handleNmeaUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("plot_id", data.plot_id);

    try {
      const resp = await fetch(`/api/agribrain/mesia/upload-nmea`, {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        throw new Error(`Upload failed with status ${resp.status}`);
      }
      setUploadSuccess(`Successfully ingested NMEA log: ${file.name}`);
      onRefresh();
    } catch (err: any) {
      setUploadError(err?.message || "Failed to upload NMEA file");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Upload Status Toast */}
      {uploadSuccess && (
        <div style={{ background: "rgba(34, 197, 94, 0.2)", border: "1px solid #4ade80", borderRadius: "8px", padding: "10px 14px", color: "#4ade80", fontSize: "12px", display: "flex", justifyContent: "space-between" }}>
          <span>✓ {uploadSuccess}</span>
          <button onClick={() => setUploadSuccess(null)} style={{ background: "none", border: "none", color: "#4ade80", cursor: "pointer" }}>✕</button>
        </div>
      )}
      {uploadError && (
        <div style={{ background: "rgba(239, 68, 68, 0.2)", border: "1px solid #f87171", borderRadius: "8px", padding: "10px 14px", color: "#f87171", fontSize: "12px", display: "flex", justifyContent: "space-between" }}>
          <span>⚠️ {uploadError}</span>
          <button onClick={() => setUploadError(null)} style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* Hidden File Inputs */}
      <input type="file" ref={fileInputRef} onChange={handleNmeaUpload} accept=".nmea,.log,.txt" style={{ display: "none" }} />
      <input type="file" ref={sigmfInputRef} accept=".sigmf-data,.sigmf-meta,.bin" style={{ display: "none" }} />

      {/* 1. Hardware Status Cards Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "16px" }}>
        {/* In-Situ GNSS-R Ground Receiver */}
        <div
          style={{
            background: "rgba(18, 26, 43, 0.85)",
            border: inSituGnss?.physical_waves_measured
              ? "1px solid rgba(74, 222, 128, 0.5)"
              : "1px solid rgba(51, 65, 85, 0.6)",
            borderRadius: "14px",
            padding: "18px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: "14px", fontWeight: 700, color: "#f8fafc", display: "flex", alignItems: "center", gap: "8px" }}>
                📡 GNSS-R In-Situ Ground Receiver
              </div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>u-blox ZED-F9P Multipath Interferometry</div>
            </div>
            {inSituGnss?.physical_waves_measured ? (
              <span style={{ fontSize: "9px", padding: "3px 7px", borderRadius: "4px", background: "rgba(34, 197, 94, 0.2)", color: "#4ade80", border: "1px solid #4ade80", fontWeight: 700 }}>
                ● PHYSICAL TELEMETRY ACTIVE
              </span>
            ) : (
              <span style={{ fontSize: "9px", padding: "3px 7px", borderRadius: "4px", background: "rgba(100, 116, 139, 0.2)", color: "#94a3b8", border: "1px solid rgba(100, 116, 139, 0.4)", fontWeight: 700 }}>
                ○ AWAITING FIELD STREAM
              </span>
            )}
          </div>

          {inSituGnss?.physical_waves_measured ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "11px", color: "#cbd5e1" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Log File Source:</span>
                <strong style={{ color: "#38bdf8" }}>{inSituGnss.log_source}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Sentences Ingested:</span>
                <strong>{inSituGnss.native_nmea_sentences_count?.toLocaleString()} NMEA Sentences</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Inferred Ground Soil VWC:</span>
                <strong style={{ color: "#4ade80", fontSize: "13px" }}>{inSituGnss.ground_measured_vwc_pct}% VWC</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Antenna Height h:</span>
                <strong>{inSituGnss.antenna_height_m?.toFixed(2)} m</strong>
              </div>
              <div style={{ fontSize: "9px", color: "#64748b", wordBreak: "break-all", background: "rgba(10, 15, 30, 0.6)", padding: "6px", borderRadius: "4px" }}>
                SHA256: {inSituGnss.sha256}
              </div>
            </div>
          ) : (
            <div style={{ padding: "14px", background: "rgba(15, 23, 42, 0.6)", borderRadius: "8px", textAlign: "center", display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ fontSize: "12px", color: "#cbd5e1", fontWeight: 600 }}>
                No active NMEA GNSS-R receiver log connected
              </div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>
                Upload raw NMEA captures ($GPGSV, $GLGSV sentences) recorded with low-elevation multipath reflections to activate physical measurement.
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                style={{
                  background: "rgba(56, 189, 248, 0.15)",
                  border: "1px solid #38bdf8",
                  borderRadius: "6px",
                  padding: "8px 14px",
                  color: "#38bdf8",
                  fontSize: "11px",
                  fontWeight: 700,
                  cursor: "pointer",
                  marginTop: "4px",
                }}
              >
                {uploading ? "Ingesting..." : "📂 Ingest NMEA Log Stream"}
              </button>
            </div>
          )}
        </div>

        {/* In-Situ Wi-Fi CSI Capture */}
        <div
          style={{
            background: "rgba(18, 26, 43, 0.85)",
            border: inSituWifi?.physical_waves_measured
              ? "1px solid rgba(236, 72, 153, 0.5)"
              : "1px solid rgba(51, 65, 85, 0.6)",
            borderRadius: "14px",
            padding: "18px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: "14px", fontWeight: 700, color: "#f8fafc" }}>
                📶 In-Situ Wi-Fi CSI Transceiver
              </div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>ESP32-S3 64-Subcarrier OFDM Matrix</div>
            </div>
            {inSituWifi?.physical_waves_measured ? (
              <span style={{ fontSize: "9px", padding: "3px 7px", borderRadius: "4px", background: "rgba(236, 72, 153, 0.2)", color: "#f472b6", border: "1px solid #f472b6", fontWeight: 700 }}>
                ● PHYSICAL CSI ACTIVE
              </span>
            ) : (
              <span style={{ fontSize: "9px", padding: "3px 7px", borderRadius: "4px", background: "rgba(100, 116, 139, 0.2)", color: "#94a3b8", border: "1px solid rgba(100, 116, 139, 0.4)", fontWeight: 700 }}>
                ○ NO CSI CAPTURE
              </span>
            )}
          </div>

          {inSituWifi?.physical_waves_measured ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "11px", color: "#cbd5e1" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Subcarriers Monitored:</span>
                <strong>{inSituWifi.num_subcarriers ?? 64} Subcarriers (OFDM)</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Center Frequency:</span>
                <strong>{((inSituWifi.center_frequency_hz ?? 2412e6) / 1e6).toFixed(1)} MHz</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Amplitude Variance:</span>
                <strong style={{ color: "#f472b6" }}>{inSituWifi.amplitude_variance?.toFixed(4)}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Canopy Water Index:</span>
                <strong style={{ color: "#38bdf8" }}>{inSituWifi.canopy_water_index?.toFixed(3)}</strong>
              </div>
            </div>
          ) : (
            <div style={{ padding: "14px", background: "rgba(15, 23, 42, 0.6)", borderRadius: "8px", textAlign: "center", display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ fontSize: "12px", color: "#cbd5e1", fontWeight: 600 }}>
                No active SigMF CSI dataset registered
              </div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>
                Upload binary SigMF CSI captures (.sigmf-data + .sigmf-meta) recorded across parcel crop rows to activate subcarrier foliar attenuation analysis.
              </div>
              <button
                onClick={() => sigmfInputRef.current?.click()}
                style={{
                  background: "rgba(236, 72, 153, 0.15)",
                  border: "1px solid #ec4899",
                  borderRadius: "6px",
                  padding: "8px 14px",
                  color: "#f472b6",
                  fontSize: "11px",
                  fontWeight: 700,
                  cursor: "pointer",
                  marginTop: "4px",
                }}
              >
                📂 Ingest SigMF CSI Dataset
              </button>
            </div>
          )}
        </div>

        {/* O-RAN E2 KPM Telemetry */}
        <div
          style={{
            background: "rgba(18, 26, 43, 0.85)",
            border: oranData?.is_consent_valid
              ? "1px solid rgba(167, 139, 250, 0.5)"
              : "1px solid rgba(51, 65, 85, 0.6)",
            borderRadius: "14px",
            padding: "18px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: "14px", fontWeight: 700, color: "#f8fafc" }}>
                📱 O-RAN Near-RT RIC (E2 Interface)
              </div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>Cellular Operator Key Performance Metrics</div>
            </div>
            {oranData?.is_consent_valid ? (
              <span style={{ fontSize: "9px", padding: "3px 7px", borderRadius: "4px", background: "rgba(167, 139, 250, 0.2)", color: "#a78bfa", border: "1px solid #a78bfa", fontWeight: 700 }}>
                ✓ CONSENT VALIDATED
              </span>
            ) : (
              <span style={{ fontSize: "9px", padding: "3px 7px", borderRadius: "4px", background: "rgba(100, 116, 139, 0.2)", color: "#94a3b8", border: "1px solid rgba(100, 116, 139, 0.4)", fontWeight: 700 }}>
                DISCONNECTED
              </span>
            )}
          </div>

          {oranData?.is_consent_valid ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "11px", color: "#cbd5e1" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Operator:</span>
                <strong>{oranData.operator_name} (Cell {oranData.cell_id})</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>PRB Utilization:</span>
                <strong style={{ color: "#a78bfa" }}>{oranData.prb_utilization_pct.toFixed(1)}%</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Mean Tx Power:</span>
                <strong>{oranData.mean_tx_power_dbm.toFixed(1)} dBm</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Active Beam Index:</span>
                <strong>Beam #{oranData.active_beam_index}</strong>
              </div>
            </div>
          ) : (
            <div style={{ padding: "14px", background: "rgba(15, 23, 42, 0.6)", borderRadius: "8px", textAlign: "center", display: "flex", flexDirection: "column", gap: "6px" }}>
              <div style={{ fontSize: "12px", color: "#cbd5e1", fontWeight: 600 }}>
                O-RAN E2 KPM stream disconnected
              </div>
              <div style={{ fontSize: "10px", color: "#94a3b8", lineHeight: 1.4 }}>
                Requires an active cryptographic consent agreement and E2 KPM subscription with the local mobile network operator to monitor base station beam steering.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 2. Electromagnetic Polarization & Reflection Lab */}
      <div
        style={{
          background: "rgba(15, 23, 42, 0.85)",
          border: "1px solid rgba(51, 65, 85, 0.6)",
          borderRadius: "14px",
          padding: "18px 20px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
          <div>
            <div style={{ fontSize: "14px", fontWeight: 700, color: "#38bdf8" }}>
              ⚡ Electromagnetic Polarization & Fresnel Boundary Reflection
            </div>
            <div style={{ fontSize: "10px", color: "#94a3b8" }}>
              Calculated for mean parcel soil permittivity ε_r = {eps_r.toFixed(2)} at 45° incidence angle
            </div>
          </div>

          <div style={{ display: "flex", gap: "6px" }}>
            {[
              { id: "VV", label: "Linear VV", col: "#38bdf8", val: r_vv },
              { id: "VH", label: "Linear HH", col: "#a78bfa", val: r_hh },
              { id: "RHCP", label: "Circular RHCP", col: "#4ade80", val: r_rhcp },
              { id: "LHCP", label: "Circular LHCP", col: "#f59e0b", val: r_lhcp },
            ].map((p) => {
              const isSel = selectedPol === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => setSelectedPol(p.id as any)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "6px",
                    border: isSel ? `1px solid ${p.col}` : "1px solid rgba(51, 65, 85, 0.5)",
                    background: isSel ? "rgba(30, 41, 59, 0.8)" : "rgba(18, 26, 43, 0.5)",
                    color: isSel ? p.col : "#94a3b8",
                    fontSize: "11px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {p.label} (R = {p.val.toFixed(3)})
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "10px" }}>
          <div style={{ background: "rgba(18, 26, 43, 0.6)", padding: "10px", borderRadius: "8px", border: "1px solid rgba(56, 189, 248, 0.3)" }}>
            <span style={{ fontSize: "10px", color: "#94a3b8" }}>Co-Pol VV Reflection (R_vv):</span>
            <div style={{ fontSize: "18px", fontWeight: 700, color: "#38bdf8", marginTop: "2px" }}>
              {r_vv.toFixed(4)}
            </div>
            <span style={{ fontSize: "9px", color: "#64748b" }}>Brewster Angle Minima ~68°</span>
          </div>

          <div style={{ background: "rgba(18, 26, 43, 0.6)", padding: "10px", borderRadius: "8px", border: "1px solid rgba(167, 139, 250, 0.3)" }}>
            <span style={{ fontSize: "10px", color: "#94a3b8" }}>Cross-Pol HH Reflection (R_hh):</span>
            <div style={{ fontSize: "18px", fontWeight: 700, color: "#a78bfa", marginTop: "2px" }}>
              {r_hh.toFixed(4)}
            </div>
            <span style={{ fontSize: "9px", color: "#64748b" }}>Monotonic Increase with Angle</span>
          </div>

          <div style={{ background: "rgba(18, 26, 43, 0.6)", padding: "10px", borderRadius: "8px", border: "1px solid rgba(74, 222, 128, 0.3)" }}>
            <span style={{ fontSize: "10px", color: "#94a3b8" }}>Circular RHCP Direct (Γ_R):</span>
            <div style={{ fontSize: "18px", fontWeight: 700, color: "#4ade80", marginTop: "2px" }}>
              {r_rhcp.toFixed(4)}
            </div>
            <span style={{ fontSize: "9px", color: "#64748b" }}>Transmitted Satellite Direct</span>
          </div>

          <div style={{ background: "rgba(18, 26, 43, 0.6)", padding: "10px", borderRadius: "8px", border: "1px solid rgba(245, 158, 11, 0.3)" }}>
            <span style={{ fontSize: "10px", color: "#94a3b8" }}>Circular LHCP Reflected (Γ_L):</span>
            <div style={{ fontSize: "18px", fontWeight: 700, color: "#f59e0b", marginTop: "2px" }}>
              {r_lhcp.toFixed(4)}
            </div>
            <span style={{ fontSize: "9px", color: "#64748b" }}>Soil Moisture Carrier Mode</span>
          </div>
        </div>
      </div>

      {/* 3. Physical Fleet Sentinel Nodes Health */}
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
              🛡️ Physical Fleet Sentinels & Calibration Drift
            </div>
            <div style={{ fontSize: "10px", color: "#94a3b8" }}>
              Hardware operational integrity, battery reserve, and continuous cable loopback drift monitoring
            </div>
          </div>
          <span style={{ fontSize: "10px", color: "#38bdf8", background: "rgba(56, 189, 248, 0.15)", padding: "3px 8px", borderRadius: "4px", fontWeight: 600 }}>
            {fleetData?.telemetry_stream_type || "HARDWARE_REGISTRY"}
          </span>
        </div>

        {fleetData?.nodes && fleetData.nodes.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11px", color: "#cbd5e1" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(51, 65, 85, 0.6)", color: "#94a3b8", textAlign: "left" }}>
                  <th style={{ padding: "8px 6px" }}>Node Identifier</th>
                  <th style={{ padding: "8px 6px" }}>Role</th>
                  <th style={{ padding: "8px 6px" }}>Battery</th>
                  <th style={{ padding: "8px 6px" }}>Temp (°C)</th>
                  <th style={{ padding: "8px 6px" }}>Drift Sentinel</th>
                  <th style={{ padding: "8px 6px" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {fleetData.nodes.map((node) => (
                  <tr key={node.node_id} style={{ borderBottom: "1px solid rgba(51, 65, 85, 0.3)" }}>
                    <td style={{ padding: "8px 6px", fontWeight: 700, color: "#f8fafc" }}>{node.node_id}</td>
                    <td style={{ padding: "8px 6px", color: "#94a3b8" }}>{node.role}</td>
                    <td style={{ padding: "8px 6px", color: node.battery_pct > 30 ? "#4ade80" : "#f87171" }}>
                      {node.battery_pct.toFixed(0)}%
                    </td>
                    <td style={{ padding: "8px 6px" }}>{node.temperature_celsius.toFixed(1)}°C</td>
                    <td style={{ padding: "8px 6px", color: node.sentinel_drift_db < 1.0 ? "#4ade80" : "#f59e0b" }}>
                      {node.sentinel_drift_db.toFixed(2)} dB
                    </td>
                    <td style={{ padding: "8px 6px" }}>
                      {node.is_healthy ? (
                        <span style={{ color: "#4ade80", fontWeight: 700 }}>● Healthy</span>
                      ) : (
                        <span style={{ color: "#f87171", fontWeight: 700 }}>⚠️ Maintenance</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: "16px", background: "rgba(15, 23, 42, 0.6)", borderRadius: "8px", textAlign: "center", color: "#94a3b8", fontSize: "11px" }}>
            No physical sensor nodes currently enrolled for this parcel.
          </div>
        )}
      </div>
    </div>
  );
}

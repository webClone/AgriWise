"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MesiaData, MesiaParameters } from "./mesia/types";
import MesiaParameterBar from "./mesia/MesiaParameterBar";
import SignalsTab from "./mesia/tabs/SignalsTab";
import DielectricTab from "./mesia/tabs/DielectricTab";
import InSituTab from "./mesia/tabs/InSituTab";
import AsmaeSupervisorTab from "./mesia/tabs/AsmaeSupervisorTab";
import WaveStudioTab from "./mesia/tabs/WaveStudioTab";

interface MesiaObservatoryWorkspaceProps {
  plotId: string;
  onClose: () => void;
}

const DEFAULT_PARAMETERS: MesiaParameters = {
  soilTexture: "Clay Loam",
  bulkDensity: 1.35,
  dielectricModel: "dobson",
  antennaHeightM: 1.85,
  elevationMaskDeg: 10,
  activeBands: ["GNSS", "CELL", "UHF", "SAR", "WIFI"],
  provenanceFilter: "all",
  viewDensity: "engineering",
  expertPersona: "all",
};

export default function MesiaObservatoryWorkspace({
  plotId,
  onClose,
}: MesiaObservatoryWorkspaceProps) {
  const [data, setData] = useState<MesiaData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"signals" | "dielectric" | "insitu" | "asmae" | "studio">("signals");
  const [parameters, setParameters] = useState<MesiaParameters>(DEFAULT_PARAMETERS);
  const [isGovernanceOpen, setIsGovernanceOpen] = useState<boolean>(false);

  // Fetch MESIA telemetry from backend API
  const fetchMesiaTelemetry = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/api/agribrain/mesia?plotId=${encodeURIComponent(plotId)}`);
      if (!resp.ok) {
        throw new Error(`MESIA service status: ${resp.status}`);
      }
      const json = await resp.json();
      if (json.data) {
        setData(json.data);
      } else {
        throw new Error("Invalid MESIA telemetry payload");
      }
    } catch (err: any) {
      setError(err?.message || "Failed to contact MESIA physical observatory");
    } finally {
      setLoading(false);
    }
  }, [plotId]);

  useEffect(() => {
    fetchMesiaTelemetry();
  }, [fetchMesiaTelemetry]);

  // Update parameters handler
  const handleParameterChange = (updates: Partial<MesiaParameters>) => {
    setParameters((prev) => ({ ...prev, ...updates }));
  };

  const handleResetParameters = () => {
    setParameters(DEFAULT_PARAMETERS);
  };

  const tabs = [
    { id: "signals", label: "Ambient Signals & Optics", icon: "🧭", badge: `${data?.signals_of_opportunity?.gnss_reflectometry?.satellites_overhead_count ?? 8} Sats` },
    { id: "dielectric", label: "Soil Strata & 1m Lattice", icon: "🌱", badge: "2.5D Profile" },
    { id: "insitu", label: "In-Situ Sentinels & Hardware", icon: "📡", badge: data?.radio_wave_channels?.in_situ_ground_receiver?.physical_waves_measured ? "LIVE" : "READY" },
    { id: "asmae", label: "ASMAE Biophysical Supervisor", icon: "🛡️", badge: "P-08 Locked" },
    { id: "studio", label: "Multi-Wave Physics Studio", icon: "🔬", badge: "Interactive" },
  ] as const;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        background: "#0a0f1d",
        color: "#f8fafc",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        fontFamily: "var(--font-sans, system-ui, -apple-system, sans-serif)",
      }}
    >
      {/* ── Top Header Bar ────────────────────────────────────────────── */}
      <header
        style={{
          background: "rgba(10, 15, 29, 0.95)",
          borderBottom: "1px solid rgba(51, 65, 85, 0.5)",
          backdropFilter: "blur(16px)",
          padding: "12px 24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          zIndex: 30,
        }}
      >
        {/* Left Side: Title & Geodetic Positioning */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "18px" }}>📡</span>
              <h1 style={{ fontSize: "16px", fontWeight: 800, color: "#f8fafc", letterSpacing: "-0.02em", margin: 0 }}>
                MESIA PHYSICAL OBSERVATORY
              </h1>
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: "4px",
                  background: "rgba(56, 189, 248, 0.15)",
                  color: "#38bdf8",
                  border: "1px solid rgba(56, 189, 248, 0.3)",
                  letterSpacing: "0.5px",
                }}
              >
                PASSIVE ELECTROMAGNETIC SENSING
              </span>
            </div>
            <div style={{ fontSize: "11px", color: "#94a3b8", display: "flex", alignItems: "center", gap: "8px", marginTop: "2px" }}>
              <span>Plot: <strong style={{ color: "#e2e8f0" }}>{plotId.slice(0, 10)}...</strong></span>
              {data?.geodetic_centroid && (
                <>
                  <span>•</span>
                  <span>
                    Lat: {data.geodetic_centroid.lat.toFixed(5)}° | Lng: {data.geodetic_centroid.lng.toFixed(5)}° | Alt: {data.geodetic_centroid.alt_m.toFixed(1)}m
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Right Side: Status Badges & Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {/* Principle P-08 Safety Badge */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: "rgba(245, 158, 11, 0.12)",
              border: "1px solid rgba(245, 158, 11, 0.4)",
              padding: "4px 10px",
              borderRadius: "6px",
              cursor: "pointer",
            }}
            onClick={() => setIsGovernanceOpen(true)}
            title="Click to view Principle P-08 Actuation Governance Certificate"
          >
            <span style={{ fontSize: "12px" }}>🔒</span>
            <div>
              <div style={{ fontSize: "10px", fontWeight: 700, color: "#fbbf24" }}>
                P-08 FAIL-CLOSED LOCK
              </div>
              <div style={{ fontSize: "9px", color: "#f59e0b" }}>
                Actuation Authority: DISABLED
              </div>
            </div>
          </div>

          {/* Refresh Button */}
          <button
            onClick={fetchMesiaTelemetry}
            disabled={loading}
            style={{
              background: "rgba(30, 41, 59, 0.8)",
              border: "1px solid rgba(51, 65, 85, 0.6)",
              borderRadius: "6px",
              padding: "6px 12px",
              fontSize: "11px",
              fontWeight: 600,
              color: "#94a3b8",
              cursor: "pointer",
            }}
            title="Reload live physical radio wave measurements"
          >
            {loading ? "Refreshing..." : "↻ Refresh"}
          </button>

          {/* Close Window */}
          <button
            onClick={onClose}
            style={{
              background: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.4)",
              borderRadius: "6px",
              padding: "6px 12px",
              fontSize: "12px",
              fontWeight: 700,
              color: "#f87171",
              cursor: "pointer",
            }}
          >
            ✕ Close
          </button>
        </div>
      </header>

      {/* ── Global Interactive Physics Parameter Bar ───────────────────── */}
      <MesiaParameterBar
        parameters={parameters}
        onChange={handleParameterChange}
        onReset={handleResetParameters}
      />

      {/* ── Tab Navigation Bar ─────────────────────────────────────────── */}
      <nav
        style={{
          background: "rgba(15, 23, 42, 0.9)",
          borderBottom: "1px solid rgba(51, 65, 85, 0.4)",
          padding: "0 24px",
          display: "flex",
          gap: "8px",
          overflowX: "auto",
          zIndex: 10,
        }}
      >
        {tabs.map((tab) => {
          const isSelected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "12px 16px",
                border: "none",
                background: "transparent",
                color: isSelected ? "#38bdf8" : "#94a3b8",
                borderBottom: isSelected ? "2px solid #38bdf8" : "2px solid transparent",
                fontSize: "12px",
                fontWeight: isSelected ? 700 : 500,
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.badge && (
                <span
                  style={{
                    fontSize: "9px",
                    padding: "2px 6px",
                    borderRadius: "4px",
                    background: isSelected ? "rgba(56, 189, 248, 0.2)" : "rgba(51, 65, 85, 0.4)",
                    color: isSelected ? "#38bdf8" : "#94a3b8",
                    fontWeight: 700,
                  }}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* ── Main Tab Content Viewport ──────────────────────────────────── */}
      <main
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px",
        }}
      >
        {loading && !data && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "350px", gap: "12px" }}>
            <div style={{ width: "36px", height: "36px", borderRadius: "50%", border: "3px solid rgba(56, 189, 248, 0.2)", borderTopColor: "#38bdf8", animation: "spin 1s linear infinite" }} />
            <span style={{ fontSize: "13px", color: "#94a3b8", fontWeight: 600 }}>
              Synthesizing Multi-Band Radio Wave Telemetry & Ephemeris...
            </span>
            <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {error && (
          <div style={{ background: "rgba(239, 68, 68, 0.15)", border: "1px solid #f87171", borderRadius: "10px", padding: "16px 20px", color: "#f87171", fontSize: "12px" }}>
            <div style={{ fontWeight: 700, marginBottom: "4px" }}>⚠️ MESIA Telemetry Error</div>
            <div>{error}</div>
            <button onClick={fetchMesiaTelemetry} style={{ marginTop: "8px", background: "rgba(239, 68, 68, 0.25)", border: "1px solid #f87171", borderRadius: "4px", padding: "4px 10px", color: "#f8fafc", fontSize: "11px", cursor: "pointer" }}>
              Retry Connection
            </button>
          </div>
        )}

        {data && (
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18 }}
            >
              {activeTab === "signals" && (
                <SignalsTab data={data} parameters={parameters} />
              )}
              {activeTab === "dielectric" && (
                <DielectricTab data={data} parameters={parameters} />
              )}
              {activeTab === "insitu" && (
                <InSituTab data={data} parameters={parameters} onRefresh={fetchMesiaTelemetry} />
              )}
              {activeTab === "asmae" && (
                <AsmaeSupervisorTab data={data} parameters={parameters} />
              )}
              {activeTab === "studio" && (
                <WaveStudioTab data={data} parameters={parameters} onApplyParameters={handleParameterChange} />
              )}
            </motion.div>
          </AnimatePresence>
        )}
      </main>

      {/* ── Governance Audit Modal (Principle P-08 Lock) ───────────────── */}
      <AnimatePresence>
        {isGovernanceOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0, 0, 0, 0.75)",
              backdropFilter: "blur(8px)",
              zIndex: 100,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "20px",
            }}
            onClick={() => setIsGovernanceOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{
                background: "rgba(15, 23, 42, 0.98)",
                border: "1px solid rgba(245, 158, 11, 0.5)",
                borderRadius: "14px",
                padding: "24px",
                maxWidth: "600px",
                width: "100%",
                boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "20px" }}>🔒</span>
                  <div style={{ fontSize: "16px", fontWeight: 800, color: "#fbbf24" }}>
                    MESIA Principle P-08 Governance Certificate
                  </div>
                </div>
                <button
                  onClick={() => setIsGovernanceOpen(false)}
                  style={{ background: "none", border: "none", color: "#94a3b8", fontSize: "18px", cursor: "pointer" }}
                >
                  ✕
                </button>
              </div>

              <div style={{ fontSize: "12px", color: "#cbd5e1", lineHeight: 1.6, display: "flex", flexDirection: "column", gap: "10px" }}>
                <p>
                  <strong>Fail-Closed Safety Guarantee:</strong> MESIA operates as a strictly passive physical observatory. It never executes irrigation valves, fertigation injectors, or mechanical actuators directly.
                </p>
                <div style={{ background: "rgba(10, 15, 30, 0.7)", padding: "10px 12px", borderRadius: "8px", border: "1px solid rgba(51, 65, 85, 0.5)", fontSize: "11px" }}>
                  <div>• Decision Eligibility: <strong style={{ color: "#f87171" }}>LOCKED (false)</strong></div>
                  <div>• Authority Scope: <strong style={{ color: "#38bdf8" }}>RESEARCH_ONLY</strong></div>
                  <div>• Target Layer: <strong style={{ color: "#4ade80" }}>Layer 0 Proposal Emittance to ASMAE</strong></div>
                  <div>• Cryptographic Hash: <code style={{ color: "#94a3b8" }}>SHA256:4a8e2b9c1d0f...</code></div>
                </div>
                <p>
                  All radio wave innovations are routed through ASMAE biophysical invariants ($L_0$ to $L_{10}$). In the event of sensor drift, antenna mechanical displacement, or extreme sirocco wind gusts, measurement variance $R$ is dynamically inflated up to 100× to protect the world model.
                </p>
              </div>

              <button
                onClick={() => setIsGovernanceOpen(false)}
                style={{
                  marginTop: "18px",
                  width: "100%",
                  padding: "10px",
                  borderRadius: "8px",
                  background: "rgba(245, 158, 11, 0.2)",
                  border: "1px solid #f59e0b",
                  color: "#fbbf24",
                  fontSize: "12px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Acknowledge Governance Certificate
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

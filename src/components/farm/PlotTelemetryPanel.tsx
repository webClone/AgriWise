"use client";

import { useEffect, useState } from "react";
import { FAOIntelligenceProfile, getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";

interface PlotTelemetryPanelProps {
  lat: number;
  lng: number;
  initialData?: FAOIntelligenceProfile['realTime'];
}

export default function PlotTelemetryPanel({ lat, lng, initialData }: PlotTelemetryPanelProps) {
  const [data, setData] = useState<FAOIntelligenceProfile['realTime'] | undefined>(initialData);
  const [loading, setLoading] = useState(!initialData);

  useEffect(() => {
    if (initialData) return;

    async function fetchData() {
      try {
        setLoading(true);
        // We fetch the full profile to get the calculated physics, 
        // effectively reusing the logic in fao-data-service.
        // In the future, we can create a dedicated lightweight endpoint.
        const profile = await getFAOLandIntelligence(lat, lng, "generic");
        setData(profile.realTime);
      } catch (err) {
        console.error("Failed to fetch telemetry", err);
      } finally {
        setLoading(false);
      }
    }

    if (lat && lng) {
      fetchData();
    }
  }, [lat, lng, initialData]);

  if (loading) {
    return (
      <div className="card fade-in h-full" style={{ padding: "1.5rem", background: "#1e293b", border: "1px solid #334155", borderRadius: "12px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
           <div className="h-6 w-32 bg-slate-700/50 rounded animate-pulse"></div>
           <div className="h-6 w-16 bg-slate-700/50 rounded animate-pulse"></div>
        </div>
        <div className="grid grid-cols-2 gap-4">
           <div className="h-24 bg-slate-700/50 rounded animate-pulse"></div>
           <div className="h-24 bg-slate-700/50 rounded animate-pulse"></div>
           <div className="h-24 bg-slate-700/50 rounded animate-pulse"></div>
           <div className="h-24 bg-slate-700/50 rounded animate-pulse"></div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="card fade-in h-full" style={{ 
      padding: "1.5rem", 
      background: "#1e293b", 
      border: "1px solid #334155", 
      borderLeft: "4px solid #ef4444", 
      borderRadius: "12px",
      display: "flex",
      flexDirection: "column"
    }}>
      
      {/* Live Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <div style={{ position: "relative", width: "12px", height: "12px" }}>
                  <div className="animate-pulse" style={{ position: "absolute", width: "100%", height: "100%", borderRadius: "50%", background: "#ef4444", opacity: 0.7 }}></div>
                  <div style={{ position: "absolute", top: "25%", left: "25%", width: "50%", height: "50%", borderRadius: "50%", background: "#ef4444" }}></div>
              </div>
              <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: "700", color: "#f8fafc", letterSpacing: "0.5px" }}>Real-Time Telemetry</h3>
          </div>
          <div style={{ fontSize: "0.7rem", color: "#94a3b8", background: "#0f172a", padding: "4px 8px", borderRadius: "20px", border: "1px solid #334155" }}>
              ⚡ Physics Engine
          </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", flex: 1 }}>
          
          {/* Agronomic Physics (Priority) */}
          <div>
              <span style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase", fontWeight: "700", letterSpacing: "1px", display: "block", marginBottom: "0.5rem" }}>Physics</span>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: "0.9rem" }}>
                  <div style={{ background: (data.deltaT >= 2 && data.deltaT <= 8) ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)", padding: "0.75rem", borderRadius: "8px", border: "1px solid", borderColor: (data.deltaT >= 2 && data.deltaT <= 8) ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)" }}>
                      <span style={{ display: "block", fontSize: "0.7rem", color: "#94a3b8", marginBottom: "0.1rem" }}>Delta-T</span>
                      <b style={{ color: (data.deltaT >= 2 && data.deltaT <= 8) ? "#34d399" : "#f87171", fontSize: "1.1rem" }}>{data.deltaT.toFixed(1)}</b>
                  </div>
                  <div style={{ background: "rgba(255,255,255,0.03)", padding: "0.75rem", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.05)" }}>
                      <span style={{ display: "block", fontSize: "0.7rem", color: "#94a3b8", marginBottom: "0.1rem" }}>VPD</span>
                      <b style={{ color: "#f1f5f9", fontSize: "1.1rem" }}>{data.vpd} <span style={{fontSize:"0.7rem", color:"#64748b"}}>kPa</span></b>
                  </div>
              </div>
          </div>

          {/* Atmosphere */}
          <div>
              <span style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase", fontWeight: "700", letterSpacing: "1px", display: "block", marginBottom: "0.5rem" }}>Atmosphere</span>
              <div style={{ display: "flex", alignItems: "baseline", gap: "1rem" }}>
                  <span style={{ fontSize: "2.2rem", fontWeight: "700", color: "#f8fafc", lineHeight: 1 }}>{data.temp}°C</span>
                  <div style={{ display: "flex", flexDirection: "column" }}>
                      <span style={{ fontSize: "0.9rem", color: "#60a5fa", fontWeight: "600" }}>{data.rain}mm Rain</span>
                      <span style={{ fontSize: "0.7rem", color: "#64748b" }}>Current Hour</span>
                  </div>
              </div>
          </div>

          {/* Soil & Water */}
          <div style={{ marginTop: "auto" }}>
               <div style={{ background: "rgba(255,255,255,0.03)", padding: "0.75rem", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                      <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Soil Tension</span>
                      <span style={{ fontSize: "0.75rem", color: "#f1f5f9" }}>{(data.soilTension / 1000).toFixed(1)} MPa</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Leaf Wetness</span>
                      <span style={{ fontSize: "0.75rem", color: data.leafWetness > 0 ? "#f87171" : "#34d399" }}>{data.leafWetness}%</span>
                  </div>
               </div>
          </div>

      </div>
    </div>
  );
}

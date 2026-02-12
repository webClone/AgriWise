"use client";

import { useEffect, useState } from "react";

interface SoilMoistureData {
  layers: {
    depth: string;
    moisture: number;
    temperature: number;
  }[];
  timestamp: string;
}

interface SoilProperties {
  ph: number;
  organic_carbon: number;
  nitrogen: number;
  clay: number;
  sand: number;
  silt: number;
  cec?: number;
  texture_class?: string;
}

interface PlotSoilPanelProps {
  lat: number;
  lng: number;
}

function getMoistureColor(value: number): string {
  if (value < 15) return "#ef4444"; // Dry - Red
  if (value < 25) return "#f59e0b"; // Low - Orange
  if (value < 40) return "#10b981"; // Optimal - Green
  return "#3b82f6"; // High - Blue
}

function getMoistureLabel(value: number): string {
  if (value < 15) return "جافة";
  if (value < 25) return "منخفضة";
  if (value < 40) return "مثالية";
  return "عالية";
}

export default function PlotSoilPanel({ lat, lng }: PlotSoilPanelProps) {
  const [moisture, setMoisture] = useState<SoilMoistureData | null>(null);
  const [properties, setProperties] = useState<SoilProperties | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"moisture" | "properties">("moisture");

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);

        // Fetch soil moisture
        // Fetch soil moisture via Proxy
        const moistureRes = await fetch(`/api/proxy?path=/eo/soil-layers&lat=${lat}&lng=${lng}`);
        const moistureData = await moistureRes.json();
        
        if (!moistureData.error && moistureData.layers) {
          setMoisture(moistureData);
        }

        // Fetch soil properties
        // Fetch soil properties via Proxy
        const soilRes = await fetch(`/api/proxy?path=/eo/soil-properties&lat=${lat}&lng=${lng}`);
        const propsData = await soilRes.json();
        
        if (!propsData.error) {
          setProperties(propsData);
        }

      } catch (err) {
        console.error("Soil data fetch error:", err);
      } finally {
        setLoading(false);
      }
    }

    if (lat && lng) {
      fetchData();
    }
  }, [lat, lng]);

  if (loading) {
    return (
      <div className="card" style={{ background: "#1a1f2e", border: "1px solid #334155", padding: "1.5rem" }}>
        <div className="animate-pulse">
          <div className="h-6 bg-slate-700/50 rounded w-1/3 mb-4"></div>
          <div className="space-y-2">
            <div className="h-12 bg-slate-700/50 rounded"></div>
            <div className="h-12 bg-slate-700/50 rounded"></div>
            <div className="h-12 bg-slate-700/50 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card fade-in" style={{ 
      background: "linear-gradient(135deg, #1a1f2e 0%, #0f172a 100%)", 
      border: "1px solid #334155", 
      padding: "1.5rem",
      color: "white"
    }}>
      {/* Header with Tabs */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
        <h3 style={{ margin: 0, fontWeight: 600, display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span>🌱</span> بيانات التربة
        </h3>
        <div style={{ display: "flex", gap: "0.25rem" }}>
          <button
            onClick={() => setActiveTab("moisture")}
            style={{
              padding: "0.375rem 0.75rem",
              fontSize: "0.75rem",
              fontWeight: 600,
              borderRadius: "0.375rem",
              border: "none",
              cursor: "pointer",
              background: activeTab === "moisture" ? "#3b82f6" : "transparent",
              color: activeTab === "moisture" ? "white" : "#94a3b8"
            }}
          >
            💧 الرطوبة
          </button>
          <button
            onClick={() => setActiveTab("properties")}
            style={{
              padding: "0.375rem 0.75rem",
              fontSize: "0.75rem",
              fontWeight: 600,
              borderRadius: "0.375rem",
              border: "none",
              cursor: "pointer",
              background: activeTab === "properties" ? "#10b981" : "transparent",
              color: activeTab === "properties" ? "white" : "#94a3b8"
            }}
          >
            🧪 الخصائص
          </button>
        </div>
      </div>

      {/* Moisture Tab */}
      {activeTab === "moisture" && (
        <div>
          {moisture?.layers ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {moisture.layers.map((layer, i) => (
                <div key={i} style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  gap: "1rem",
                  padding: "0.75rem",
                  background: "rgba(255,255,255,0.03)",
                  borderRadius: "0.5rem",
                  border: "1px solid rgba(255,255,255,0.08)"
                }}>
                  <div style={{ minWidth: "80px", fontSize: "0.75rem", color: "#94a3b8" }}>
                    {layer.depth}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ 
                      height: "8px", 
                      background: "#1e293b", 
                      borderRadius: "99px",
                      overflow: "hidden"
                    }}>
                      <div style={{ 
                        height: "100%", 
                        width: `${Math.min(100, layer.moisture * 2)}%`,
                        background: getMoistureColor(layer.moisture),
                        borderRadius: "99px",
                        transition: "width 0.5s ease"
                      }}></div>
                    </div>
                  </div>
                  <div style={{ 
                    minWidth: "60px", 
                    textAlign: "left",
                    fontSize: "0.875rem",
                    fontWeight: 600,
                    color: getMoistureColor(layer.moisture)
                  }}>
                    {layer.moisture.toFixed(1)}%
                  </div>
                  <div style={{ 
                    fontSize: "0.65rem", 
                    padding: "0.25rem 0.5rem",
                    background: getMoistureColor(layer.moisture) + "20",
                    color: getMoistureColor(layer.moisture),
                    borderRadius: "99px",
                    minWidth: "50px",
                    textAlign: "center"
                  }}>
                    {getMoistureLabel(layer.moisture)}
                  </div>
                  {layer.temperature && (
                    <div style={{ fontSize: "0.75rem", color: "#f59e0b" }}>
                      🌡️ {layer.temperature.toFixed(1)}°C
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "2rem", color: "#64748b" }}>
              لا تتوفر بيانات الرطوبة
            </div>
          )}
        </div>
      )}

      {/* Properties Tab */}
      {activeTab === "properties" && (
        <div>
          {properties ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "1rem" }}>
              {/* pH */}
              <div style={{ 
                padding: "1rem",
                background: "rgba(255,255,255,0.03)",
                borderRadius: "0.5rem",
                border: "1px solid rgba(255,255,255,0.08)"
              }}>
                <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  درجة الحموضة pH
                </div>
                <div style={{ 
                  fontSize: "1.5rem", 
                  fontWeight: 700, 
                  color: properties.ph < 5.5 ? "#ef4444" : properties.ph > 8 ? "#f59e0b" : "#10b981"
                }}>
                  {properties.ph?.toFixed(1) || "N/A"}
                </div>
              </div>

              {/* Organic Carbon */}
              <div style={{ 
                padding: "1rem",
                background: "rgba(255,255,255,0.03)",
                borderRadius: "0.5rem",
                border: "1px solid rgba(255,255,255,0.08)"
              }}>
                <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  الكربون العضوي
                </div>
                <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#8b5cf6" }}>
                  {properties.organic_carbon?.toFixed(1) || "N/A"}
                  <span style={{ fontSize: "0.75rem", color: "#64748b" }}> g/kg</span>
                </div>
              </div>

              {/* Nitrogen */}
              <div style={{ 
                padding: "1rem",
                background: "rgba(255,255,255,0.03)",
                borderRadius: "0.5rem",
                border: "1px solid rgba(255,255,255,0.08)"
              }}>
                <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  النيتروجين
                </div>
                <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#10b981" }}>
                  {properties.nitrogen?.toFixed(0) || "N/A"}
                  <span style={{ fontSize: "0.75rem", color: "#64748b" }}> mg/kg</span>
                </div>
              </div>

              {/* Texture */}
              <div style={{ 
                padding: "1rem",
                background: "rgba(255,255,255,0.03)",
                borderRadius: "0.5rem",
                border: "1px solid rgba(255,255,255,0.08)"
              }}>
                <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
                  قوام التربة
                </div>
                <div style={{ display: "flex", gap: "0.5rem", fontSize: "0.7rem" }}>
                  <span style={{ padding: "0.25rem 0.5rem", background: "#d97706", borderRadius: "0.25rem" }}>
                    رمل {properties.sand?.toFixed(0)}%
                  </span>
                  <span style={{ padding: "0.25rem 0.5rem", background: "#7c3aed", borderRadius: "0.25rem" }}>
                    طين {properties.clay?.toFixed(0)}%
                  </span>
                  <span style={{ padding: "0.25rem 0.5rem", background: "#059669", borderRadius: "0.25rem" }}>
                    طمي {properties.silt?.toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "2rem", color: "#64748b" }}>
              لا تتوفر بيانات خصائص التربة
            </div>
          )}
        </div>
      )}
    </div>
  );
}

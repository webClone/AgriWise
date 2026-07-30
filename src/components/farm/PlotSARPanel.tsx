"use client";

import { useEffect, useState } from "react";

interface SARData {
  // Soil moisture proxy
  moisture?: {
    vv_db: number | null;
    vh_db: number | null;
    vv_vh_ratio: number | null;
    moisture_estimate: string;
    date: string;
  };
  // Biomass
  biomass?: {
    vh_db: number | null;
    biomass_level: string;
    biomass_desc: string;
    date: string;
  };
  // Flood detection
  flood?: {
    is_flooded: boolean;
    flood_confidence: number;
    status: string;
    vv_db: number | null;
    date: string;
  };
  // Crop emergence
  emergence?: {
    is_emerging: boolean;
    emergence_confidence: number;
    vh_slope: number;
    vh_change_db: number;
    status: string;
  };
}

interface PlotSARPanelProps {
  lat: number;
  lng: number;
}

function getBiomassColor(level: string): string {
  switch (level) {
    case "high": return "#10b981";
    case "medium": return "#f59e0b";
    case "low": return "#ef4444";
    case "bare": return "#64748b";
    default: return "#64748b";
  }
}

export default function PlotSARPanel({ lat, lng }: PlotSARPanelProps) {
  const [data, setData] = useState<SARData>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchAll() {
      try {
        setLoading(true);
        setError(null);

        // Fetch SAR Analysis via Proxy
        const sarRes = await fetch(`/api/proxy?path=/eo/sar-analysis&lat=${lat}&lng=${lng}`);
        const sarData = await sarRes.json();
        
        if (sarData && !sarData.error) {
           const { moisture, biomass, flood, emergence } = sarData;
           
           setData({
             moisture: moisture.error ? null : moisture,
             biomass: biomass.error ? null : biomass,
             flood: flood.error ? null : flood,
             emergence: emergence.error ? null : emergence
           });
        }
      } catch (err) {
        console.error("Failed to fetch SAR data", err);
        setError("Could not load SAR analysis.");
      } finally {
        setLoading(false);
      }
    }

    if (lat && lng) {
      fetchAll();
    }
  }, [lat, lng]);

  if (loading) {
    return (
      <div className="card" style={{ background: "#1a1f2e", border: "1px solid #334155", padding: "1.5rem" }}>
        <div className="animate-pulse">
          <div className="h-6 bg-slate-700/50 rounded w-1/3 mb-4"></div>
          <div className="grid grid-cols-2 gap-4">
            <div className="h-20 bg-slate-700/50 rounded"></div>
            <div className="h-20 bg-slate-700/50 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  const hasSARData = data.moisture || data.biomass || data.flood || data.emergence;

  return (
    <div className="card fade-in" style={{ 
      height: "100%",
      display: "flex",
      flexDirection: "column"
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
        <h3 style={{ margin: 0, fontWeight: 600, display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span>📡</span> رادار Sentinel-1 (SAR)
        </h3>
        <div style={{ 
          fontSize: "0.65rem", 
          padding: "0.25rem 0.5rem", 
          background: "#3b82f620", 
          color: "#3b82f6", 
          borderRadius: "99px" 
        }}>
          يعمل عبر الغيوم ☁️
        </div>
      </div>

      {!hasSARData && !error && (
        <div style={{ textAlign: "center", padding: "2rem", color: "#64748b" }}>
          لا تتوفر بيانات SAR - تحقق من إعدادات Sentinel Hub
        </div>
      )}

      {error && (
        <div style={{ textAlign: "center", padding: "2rem", color: "#ef4444" }}>
          {error}
        </div>
      )}

      {hasSARData && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "1rem" }}>
          
          {/* Biomass Card */}
          <div style={{ 
            padding: "1rem",
            background: "rgba(255,255,255,0.03)",
            borderRadius: "0.5rem",
            border: "1px solid rgba(255,255,255,0.08)"
          }}>
            <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              🌱 الكتلة الحيوية
            </div>
            {data.biomass ? (
              <>
                <div style={{ 
                  fontSize: "1.25rem", 
                  fontWeight: 700, 
                  color: getBiomassColor(data.biomass.biomass_level),
                  marginTop: "0.25rem"
                }}>
                  {data.biomass.biomass_desc}
                </div>
                <div style={{ fontSize: "0.7rem", color: "#64748b", marginTop: "0.25rem" }}>
                  VH: {data.biomass.vh_db} dB
                </div>
              </>
            ) : (
              <div style={{ fontSize: "1rem", color: "#64748b" }}>غير متاح</div>
            )}
          </div>

          {/* Flood Status Card */}
          <div style={{ 
            padding: "1rem",
            background: "rgba(255,255,255,0.03)",
            borderRadius: "0.5rem",
            border: "1px solid rgba(255,255,255,0.08)"
          }}>
            <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              💧 حالة الفيضان
            </div>
            {data.flood ? (
              <>
                <div style={{ 
                  fontSize: "1.25rem", 
                  fontWeight: 700, 
                  color: data.flood.is_flooded ? "#3b82f6" : "#10b981",
                  marginTop: "0.25rem"
                }}>
                  {data.flood.status}
                </div>
                {data.flood.is_flooded && (
                  <div style={{ fontSize: "0.7rem", color: "#64748b", marginTop: "0.25rem" }}>
                    ثقة: {data.flood.flood_confidence}%
                  </div>
                )}
              </>
            ) : (
              <div style={{ fontSize: "1rem", color: "#64748b" }}>غير متاح</div>
            )}
          </div>

          {/* Moisture Proxy Card */}
          <div style={{ 
            padding: "1rem",
            background: "rgba(255,255,255,0.03)",
            borderRadius: "0.5rem",
            border: "1px solid rgba(255,255,255,0.08)"
          }}>
            <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              🌊 رطوبة التربة
            </div>
            {data.moisture ? (
              <>
                <div style={{ 
                  fontSize: "1.25rem", 
                  fontWeight: 700, 
                  color: data.moisture.moisture_estimate === "wet" ? "#3b82f6" : 
                         data.moisture.moisture_estimate === "moist" ? "#10b981" : "#f59e0b",
                  marginTop: "0.25rem"
                }}>
                  {data.moisture.moisture_estimate === "wet" ? "رطبة" :
                   data.moisture.moisture_estimate === "moist" ? "رطبة قليلاً" : "جافة"}
                </div>
                <div style={{ fontSize: "0.7rem", color: "#64748b", marginTop: "0.25rem" }}>
                  VV/VH: {data.moisture.vv_vh_ratio}
                </div>
              </>
            ) : (
              <div style={{ fontSize: "1rem", color: "#64748b" }}>غير متاح</div>
            )}
          </div>

          {/* Crop Emergence Card */}
          <div style={{ 
            padding: "1rem",
            background: "rgba(255,255,255,0.03)",
            borderRadius: "0.5rem",
            border: "1px solid rgba(255,255,255,0.08)"
          }}>
            <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              🌿 الإنبات المبكر
            </div>
            {data.emergence ? (
              <>
                <div style={{ 
                  fontSize: "1.25rem", 
                  fontWeight: 700, 
                  color: data.emergence.is_emerging ? "#10b981" : "#64748b",
                  marginTop: "0.25rem"
                }}>
                  {data.emergence.status}
                </div>
                {data.emergence.is_emerging && (
                  <div style={{ fontSize: "0.7rem", color: "#64748b", marginTop: "0.25rem" }}>
                    ثقة: {data.emergence.emergence_confidence}%
                  </div>
                )}
                <div style={{ fontSize: "0.65rem", color: "#64748b", marginTop: "0.25rem" }}>
                  تغير VH: {data.emergence.vh_change_db > 0 ? "+" : ""}{data.emergence.vh_change_db} dB
                </div>
              </>
            ) : (
              <div style={{ fontSize: "1rem", color: "#64748b" }}>غير متاح</div>
            )}
          </div>

        </div>
      )}

      {/* Footer info */}
      <div style={{ 
        marginTop: "1rem", 
        paddingTop: "0.75rem", 
        borderTop: "1px solid rgba(255,255,255,0.08)",
        fontSize: "0.65rem",
        color: "#64748b",
        display: "flex",
        justifyContent: "space-between"
      }}>
        <span>🛰️ Sentinel-1 GRD (رادار)</span>
        <span>يعمل ليلاً وعبر الغيوم</span>
      </div>
    </div>
  );
}

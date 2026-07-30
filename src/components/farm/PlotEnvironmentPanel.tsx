"use client";

import { useEffect, useState } from "react";

interface AirQualityData {
  pm2_5: number;
  pm10: number;
  ozone: number;
  no2: number;
  so2: number;
  aqi_eu?: number;
  aqi_us?: number;
}

interface FireRiskData {
  fire_count: number;
  risk_level: string;
  search_radius_km: number;
}

interface ElevationData {
  elevation: number;
  source: string;
}

interface PlotEnvironmentPanelProps {
  lat: number;
  lng: number;
}

function getAQIColor(aqi: number): string {
  if (aqi <= 50) return "#10b981"; // Good - Green
  if (aqi <= 100) return "#f59e0b"; // Moderate - Yellow
  if (aqi <= 150) return "#f97316"; // Unhealthy for sensitive - Orange
  if (aqi <= 200) return "#ef4444"; // Unhealthy - Red
  if (aqi <= 300) return "#7c3aed"; // Very unhealthy - Purple
  return "#831843"; // Hazardous - Maroon
}

function getAQILabel(aqi: number): string {
  if (aqi <= 50) return "جيد";
  if (aqi <= 100) return "مقبول";
  if (aqi <= 150) return "متوسط";
  if (aqi <= 200) return "سيء";
  if (aqi <= 300) return "سيء جداً";
  return "خطير";
}

function getFireRiskColor(level: string): string {
  switch (level.toLowerCase()) {
    case "low": return "#10b981";
    case "moderate": return "#f59e0b";
    case "high": return "#f97316";
    case "extreme": return "#ef4444";
    default: return "#64748b";
  }
}

function getFireRiskLabel(level: string): string {
  switch (level.toLowerCase()) {
    case "low": return "منخفض";
    case "moderate": return "متوسط";
    case "high": return "عالي";
    case "extreme": return "شديد";
    default: return level;
  }
}

export default function PlotEnvironmentPanel({ lat, lng }: PlotEnvironmentPanelProps) {
  const [airQuality, setAirQuality] = useState<AirQualityData | null>(null);
  const [fireRisk, setFireRisk] = useState<FireRiskData | null>(null);
  const [elevation, setElevation] = useState<ElevationData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);

        // Fetch environment data via Proxy
        const envRes = await fetch(`/api/proxy?path=/eo/environment-analysis&lat=${lat}&lng=${lng}`);
        const envData = await envRes.json();
        
        if (envData && !envData.error) {
            setAirQuality(envData.air_quality?.error ? null : envData.air_quality);
            setFireRisk(envData.fire_risk?.error ? null : envData.fire_risk);
            setElevation(envData.elevation?.error ? null : envData.elevation);
        }
      } catch (err) {
        console.error("Failed to fetch environment data", err);
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
      <div className="card" style={{ background: "#1e293b", border: "1px solid #334155", padding: "1.5rem" }}>
        <div className="animate-pulse">
          <div className="h-6 bg-slate-700/50 rounded w-1/3 mb-4"></div>
          <div className="grid grid-cols-3 gap-4">
            <div className="h-24 bg-slate-700/50 rounded"></div>
            <div className="h-24 bg-slate-700/50 rounded"></div>
            <div className="h-24 bg-slate-700/50 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  const aqi = airQuality?.aqi_us || airQuality?.aqi_eu || 0;

  return (
    <div className="card fade-in" style={{ 
      background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)", 
      border: "1px solid #334155", 
      padding: "1.5rem",
      color: "white"
    }}>
      <h3 style={{ margin: "0 0 1rem 0", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <span>🌍</span> البيئة المحيطة
      </h3>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
        {/* Air Quality */}
        <div style={{ 
          padding: "1rem",
          background: "rgba(255,255,255,0.03)",
          borderRadius: "0.75rem",
          border: "1px solid rgba(255,255,255,0.08)",
          textAlign: "center"
        }}>
          <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
            جودة الهواء
          </div>
          {airQuality ? (
            <>
              <div style={{ 
                fontSize: "2.5rem", 
                fontWeight: 700, 
                color: getAQIColor(aqi),
                lineHeight: 1
              }}>
                {Math.round(aqi)}
              </div>
              <div style={{ 
                fontSize: "0.75rem", 
                color: getAQIColor(aqi),
                marginTop: "0.25rem",
                fontWeight: 600
              }}>
                {getAQILabel(aqi)}
              </div>
              <div style={{ 
                display: "grid", 
                gridTemplateColumns: "1fr 1fr", 
                gap: "0.25rem", 
                marginTop: "0.75rem",
                fontSize: "0.65rem",
                color: "#94a3b8"
              }}>
                <span>PM2.5: {airQuality.pm2_5?.toFixed(0)}</span>
                <span>PM10: {airQuality.pm10?.toFixed(0)}</span>
                <span>O₃: {airQuality.ozone?.toFixed(0)}</span>
                <span>NO₂: {airQuality.no2?.toFixed(0)}</span>
              </div>
            </>
          ) : (
            <div style={{ color: "#64748b", fontSize: "0.875rem" }}>غير متوفر</div>
          )}
        </div>

        {/* Fire Risk */}
        <div style={{ 
          padding: "1rem",
          background: "rgba(255,255,255,0.03)",
          borderRadius: "0.75rem",
          border: "1px solid rgba(255,255,255,0.08)",
          textAlign: "center"
        }}>
          <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
            خطر الحرائق
          </div>
          {fireRisk ? (
            <>
              <div style={{ fontSize: "2.5rem", marginBottom: "0.25rem" }}>
                {fireRisk.risk_level === "low" ? "✅" : 
                 fireRisk.risk_level === "moderate" ? "⚠️" : 
                 fireRisk.risk_level === "high" ? "🔥" : "🔥"}
              </div>
              <div style={{ 
                fontSize: "0.875rem", 
                color: getFireRiskColor(fireRisk.risk_level),
                fontWeight: 600
              }}>
                {getFireRiskLabel(fireRisk.risk_level)}
              </div>
              <div style={{ 
                fontSize: "0.65rem", 
                color: "#64748b",
                marginTop: "0.5rem"
              }}>
                {fireRisk.fire_count} حريق في {fireRisk.search_radius_km} كم
              </div>
            </>
          ) : (
            <div style={{ color: "#64748b", fontSize: "0.875rem" }}>غير متوفر</div>
          )}
        </div>

        {/* Elevation */}
        <div style={{ 
          padding: "1rem",
          background: "rgba(255,255,255,0.03)",
          borderRadius: "0.75rem",
          border: "1px solid rgba(255,255,255,0.08)",
          textAlign: "center"
        }}>
          <div style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
            الارتفاع
          </div>
          {elevation ? (
            <>
              <div style={{ fontSize: "2rem", marginBottom: "0.25rem" }}>
                🏔️
              </div>
              <div style={{ 
                fontSize: "1.5rem", 
                fontWeight: 700,
                color: "#60a5fa"
              }}>
                {elevation.elevation} م
              </div>
              <div style={{ 
                fontSize: "0.65rem", 
                color: "#64748b",
                marginTop: "0.25rem"
              }}>
                فوق مستوى البحر
              </div>
            </>
          ) : (
            <div style={{ color: "#64748b", fontSize: "0.875rem" }}>غير متوفر</div>
          )}
        </div>
      </div>
    </div>
  );
}

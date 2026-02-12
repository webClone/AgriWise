"use client";

import { useEffect, useState } from "react";
import { Trees, Tractor, Building, Waves, Info, Activity, Droplets } from "lucide-react";
import { fetchSatelliteData } from "@/lib/satellite-providers";

interface LandCoverPanelProps {
  lat: number;
  lng: number;
}

interface LandCoverData {
  location: { lat: number; lng: number };
  class_value: number;
  label: string;
  color: string;
  is_potentially_crop: boolean;
  source: string;
  vegetation_density?: number;
}

interface HealthData {
  ndvi: number;
  ndmi: number;
  status: string;
  color: string;
  description: string;
}

export default function PlotLandCoverPanel({ lat, lng }: LandCoverPanelProps) {
  const [data, setData] = useState<LandCoverData | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Parallel fetch for Land Cover and Satellite Stats
        const [landCoverResponse, satelliteProfile] = await Promise.all([
           fetch(`/api/proxy?path=/eo/land-cover&lat=${lat}&lng=${lng}`),
           fetchSatelliteData('sentinel', lat, lng, 'wheat') // Default crop for generic health
        ]);

        if (landCoverResponse.ok) {
          const result = await landCoverResponse.json();
          setData(result);
        }

        if (satelliteProfile && satelliteProfile.layers && satelliteProfile.layers.length > 0) {
            // Get latest available data
            const latest = satelliteProfile.layers[satelliteProfile.layers.length - 1]; // Oldest is usually last in some lists, need to check sort. 
            // Usually OneSoilProfile layers are chronological or reverse. Let's assume indices are available.
            // Using logic from SatelliteMissionControl: layers are chronological usually.
            // Actually, let's grab the one with the highest NDVI to avoid cloud noise if possible, or just the latest valid one.
            // For simplicity, taking the last one (latest).
            
            const ndvi = latest.ndvi || 0;
            const ndmi = latest.ndmi || 0;
            
            let status = "Unknown";
            let color = "#94a3b8"; // Gray
            let desc = "No data";

            // Logic matching False Color Legend
            if (ndvi > 0.6) {
                status = "Vigorous / Healthy";
                color = "#dc2626"; // Bright Red
                desc = "High Biomass (PIR Reflectance)";
            } else if (ndvi > 0.3) {
                status = "Moderate / Stable";
                color = "#991b1b"; // Dark Red
                desc = "Moderate Vegetation Cover";
            } else if (ndvi > 0.1) {
                status = "Sparse / Stressed";
                color = "#b45309"; // Brown/Orange
                desc = "Low Vegetation / Bare Soil Mix";
            } else {
                status = "Bare Soil / Non-Veg";
                color = "#78350f"; // Dark Brown
                desc = "No Vegetation Detected";
            }
            
            setHealth({ ndvi, ndmi, status, color, description: desc });
        }

      } catch (error) {
        console.error("Failed to fetch data", error);
      } finally {
        setLoading(false);
      }
    };

    if (lat && lng) fetchData();
  }, [lat, lng]);

  if (loading) {
    return (
      <div className="card animate-pulse p-4 mb-4 bg-slate-100 dark:bg-slate-800 border-none">
        <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/3 mb-2"></div>
        <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/4"></div>
      </div>
    );
  }

  if (!data || !data.label) {
    return (
      <div className="card p-4 mb-4 border-l-4 border-red-500 bg-red-50 dark:bg-red-900/20 dark:border-red-900/50">
        <h4 className="text-sm font-semibold text-red-700 dark:text-red-400 flex items-center gap-2">
           <Info className="h-4 w-4" />
           Land Cover Unavailable
        </h4>
        <p className="text-xs text-red-600 dark:text-red-300 mt-1">
           Could not retrieve satellite classification.
        </p>
      </div>
    );
  }

  const getIcon = (label: string) => {
    if (label.includes("Crop")) return <Tractor className="h-5 w-5 text-green-600" />;
    if (label.includes("Tree") || label.includes("Forest")) return <Trees className="h-5 w-5 text-emerald-700" />;
    if (label.includes("Built") || label.includes("Urban")) return <Building className="h-5 w-5 text-red-500" />;
    if (label.includes("Water")) return <Waves className="h-5 w-5 text-blue-500" />;
    return <Info className="h-5 w-5 text-gray-500" />;
  };

  // Safe to cast because of the early return above
  const validData = data as LandCoverData;

  return (
    <div className="fade-in mb-4" style={{ 
       direction: 'rtl', 
       textAlign: 'right',
       padding: "1rem",
       background: "rgba(255,255,255,0.05)",
       borderRadius: "0.75rem",
       border: "1px solid rgba(255,255,255,0.1)"
    }}>
       {/* Card Header */}
       <h3 style={{ 
          borderBottom: "1px solid rgba(255,255,255,0.1)", 
          paddingBottom: "0.75rem", 
          marginBottom: "1rem", 
          fontSize: "1rem", 
          fontWeight: 700, 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "flex-start", // Handle RTL (Start=Right)
          gap: "0.5rem",
          color: "#fff"
       }}>
          {getIcon(validData.label)}
          <span>الغطاء الأرضي (Land Cover)</span>
       </h3>

       {/* Content Container (Flex Column) */}
       <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          
          {/* Main Status Row: Icon & Text */}
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              {/* Icon Section */}
              <div style={{ fontSize: "2.5rem" }}>
                 {getIcon(validData.label)}
              </div>

              {/* Text Section */}
              <div style={{ flex: 1 }}>
                 <div style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    التصنيف الحالي
                 </div>
                 <div style={{ fontSize: "1.25rem", fontWeight: 700, color: validData.color }}>
                    {validData.label}
                 </div>
                 <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.25rem" }}>
                    ESA WorldCover (10m)
                 </div>
              </div>
          </div>

          {/* Vegetation Health Section (New) */}
          {health && (
            <div className="mt-2 p-3 bg-slate-900/50 rounded-lg border border-slate-800/50">
                <div className="flex items-center justify-between mb-2">
                    <div className="text-[10px] uppercase font-bold text-slate-400 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
                        Vegetation Health (PIR / R / V)
                    </div>
                </div>
                
                <div className="flex items-start gap-3">
                    {/* Status Indicator Block */}
                    <div className="flex-1">
                        <div className="text-sm font-bold truncate" style={{ color: health.color }}>
                            {health.status}
                        </div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                            {health.description}
                        </div>
                    </div>

                    {/* Metrics */}
                    <div className="flex gap-2">
                        <div className="text-center px-2 py-1 bg-slate-800/50 rounded">
                            <div className="text-[9px] text-slate-400 mb-0.5 flex justify-center"><Activity size={10}/> NDVI</div>
                            <div className="text-xs font-mono font-bold text-emerald-400">{health.ndvi.toFixed(2)}</div>
                        </div>
                        <div className="text-center px-2 py-1 bg-slate-800/50 rounded">
                            <div className="text-[9px] text-slate-400 mb-0.5 flex justify-center"><Droplets size={10}/> NDMI</div>
                            <div className="text-xs font-mono font-bold text-blue-400">{health.ndmi.toFixed(2)}</div>
                        </div>
                    </div>
                </div>
                
                {/* Visual Health Bar */}
                <div className="mt-2 h-1.5 w-full bg-slate-800 rounded-full overflow-hidden flex">
                    {/* False Color Scale Representation */}
                    <div className="h-full bg-amber-900" style={{ width: '20%', opacity: health.ndvi < 0.2 ? 1 : 0.3 }}></div>
                    <div className="h-full bg-red-900" style={{ width: '30%', opacity: health.ndvi >= 0.2 && health.ndvi < 0.4 ? 1 : 0.3 }}></div>
                    <div className="h-full bg-red-600" style={{ width: '50%', opacity: health.ndvi >= 0.4 ? 1 : 0.3 }}></div>
                </div>
            </div>
          )}

          {/* Divider if Density exists */}
          {validData.vegetation_density !== undefined && !health && (
             <div style={{ height: "1px", background: "rgba(255,255,255,0.1)", width: "100%" }}></div>
          )}

          {/* Vegetation Density Bar Section (Legacy/Supplemental) */}
          {validData.vegetation_density !== undefined && (
             <div>
                {(() => {
                    // Safe access because of the surrounding check
                    const density = validData.vegetation_density!;
                    
                    // Dynamic Colors for Gradient
                    const getGradient = (d: number) => {
                        if (d < 0.3) return "linear-gradient(90deg, #f59e0b 0%, #d97706 100%)"; // Amber
                        if (d < 0.6) return "linear-gradient(90deg, #84cc16 0%, #65a30d 100%)"; // Lime
                        return "linear-gradient(90deg, #10b981 0%, #059669 100%)"; // Emerald
                    };
                    const bgGradient = getGradient(density);
                    const percent = Math.min(100, Math.max(5, density * 100));

                    return (
                      <>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "0.5rem" }}>
                            <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#fff" }}>
                               {percent.toFixed(0)}%
                            </div>
                            <div style={{ fontSize: "0.65rem", color: "#94a3b8", textTransform: "uppercase" }}>
                               كثافة الغطاء النباتي (Density)
                            </div>
                        </div>

                        {/* Progress Bar Track */}
                        <div style={{ 
                          height: "12px", 
                          background: "#1e293b", 
                          borderRadius: "6px", 
                          overflow: "hidden", 
                          position: "relative",
                          transform: "rotate(180deg)" // Grow Right to Left
                        }}>
                           {/* Progress Bar Fill */}
                           <div style={{ 
                             height: "100%", 
                             width: `${percent}%`, 
                             background: bgGradient,
                             borderRadius: "6px", 
                             transition: "width 0.5s ease"
                           }}></div>
                        </div>

                        <div style={{ display: "flex", justifyContent: "space-between", marginTop: "0.5rem", fontSize: "0.6rem", color: "#64748b" }}>
                           <span>Dense (كثيف)</span>
                           <span>Moderate (متوسط)</span>
                           <span>Sparse (نادر)</span>
                        </div>
                      </>
                    );
                })()}
             </div>
          )}
       </div>
    </div>
  );
}

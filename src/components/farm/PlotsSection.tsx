"use client";

import { useState } from "react";
import Link from "next/link";
import AddPlotForm from "./AddPlotForm";


interface Plot {
  id: string;
  name: string;
  nameAr?: string;
  area: number;
  soilType?: string;
  irrigation?: string;
}

interface CropCycle {
  id: string;
  cropCode: string;
  cropNameAr?: string;
  variety?: string;
  status: string;
  plotId: string;
}

interface PlotsSectionProps {
  farmId: string;
  plots: Plot[];
  cropCycles: CropCycle[];
  farmCoordinates?: { lat: number; lng: number };
}

const SOIL_LABELS: Record<string, string> = {
  CLAY: "طينية", SANDY: "رملية", LOAM: "طميية",
  SILT: "غرينية", PEAT: "خثية", CHALKY: "كلسية",
};

const IRRIGATION_LABELS: Record<string, string> = {
  DRIP: "تقطير", SPRINKLER: "رش", PIVOT: "محوري",
  FLOOD: "غمر", RAINFED: "بعلي",
};

const IRRIGATION_ICONS: Record<string, string> = {
  DRIP: "💧", SPRINKLER: "🔄", PIVOT: "⭕",
  FLOOD: "🌊", RAINFED: "🌧️", "": "🌧️",
};

const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  GROWING: { bg: "rgba(34, 197, 94, 0.12)", color: "#4ade80", label: "نمو" },
  FLOWERING: { bg: "rgba(236, 72, 153, 0.12)", color: "#f472b6", label: "إزهار" },
  PLANTED: { bg: "rgba(59, 130, 246, 0.12)", color: "#93c5fd", label: "مزروع" },
  FRUITING: { bg: "rgba(251, 146, 60, 0.12)", color: "#fb923c", label: "إثمار" },
  READY_TO_HARVEST: { bg: "rgba(234, 179, 8, 0.12)", color: "#facc15", label: "جاهز للحصاد" },
  HARVESTED: { bg: "rgba(148, 163, 184, 0.12)", color: "#94a3b8", label: "محصود" },
  PLANNED: { bg: "rgba(99, 102, 241, 0.12)", color: "#a5b4fc", label: "مخطط" },
  FAILED: { bg: "rgba(239, 68, 68, 0.12)", color: "#f87171", label: "فشل" },
};

export default function PlotsSection({ farmId, plots, cropCycles, farmCoordinates }: PlotsSectionProps) {
  const [showAddForm, setShowAddForm] = useState(false);

  return (
    <>
      <div className="card fade-in" style={{ marginBottom: "1.5rem", padding: "20px" }}>
        {/* Header */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          marginBottom: plots.length > 0 ? "16px" : "0",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "1.25rem" }}>🌱</span>
            <h3 style={{ margin: 0, fontWeight: 700, fontSize: "1rem" }}>
              قطع الأرض
            </h3>
            {plots.length > 0 && (
              <span style={{
                fontSize: "0.7rem", fontWeight: 700,
                background: "rgba(34, 197, 94, 0.12)", color: "#4ade80",
                padding: "2px 10px", borderRadius: "9999px",
                border: "1px solid rgba(34, 197, 94, 0.2)",
              }}>
                {plots.length}
              </span>
            )}
          </div>
          <button
            onClick={() => setShowAddForm(true)}
            style={{
              padding: "6px 14px", borderRadius: "8px",
              fontSize: "0.8rem", fontWeight: 600, cursor: "pointer",
              background: "rgba(34, 197, 94, 0.1)",
              border: "1px solid rgba(34, 197, 94, 0.2)",
              color: "#4ade80",
              transition: "all 0.2s ease",
            }}
            onMouseOver={e => e.currentTarget.style.background = "rgba(34, 197, 94, 0.18)"}
            onMouseOut={e => e.currentTarget.style.background = "rgba(34, 197, 94, 0.1)"}
          >
            + إضافة قطعة
          </button>
        </div>
        
        {plots.length === 0 ? (
          /* Empty State */
          <div style={{
            textAlign: "center", padding: "3rem 2rem",
            border: "2px dashed rgba(71, 85, 105, 0.2)",
            borderRadius: "16px",
            background: "linear-gradient(135deg, rgba(15, 23, 42, 0.3), rgba(15, 23, 42, 0.1))",
          }}>
            <div style={{
              width: "64px", height: "64px", borderRadius: "16px",
              background: "rgba(34, 197, 94, 0.08)",
              display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 1rem", fontSize: "1.75rem",
            }}>
              🗺️
            </div>
            <p style={{ fontWeight: 600, fontSize: "0.95rem", color: "#e8ecf4", margin: "0 0 0.5rem 0" }}>
              لا توجد قطع مسجلة لهذه المزرعة
            </p>
            <p style={{ fontSize: "0.8rem", color: "#64748b", margin: "0 0 1.25rem 0" }}>
              ابدأ بتحديد قطع أرضك ورسم حدودها على الخريطة
            </p>
            <button
              onClick={() => setShowAddForm(true)}
              style={{
                padding: "10px 24px", borderRadius: "10px",
                fontWeight: 700, fontSize: "0.85rem", cursor: "pointer",
                background: "linear-gradient(135deg, #22c55e, #16a34a)",
                border: "none", color: "#fff",
                boxShadow: "0 4px 16px rgba(34, 197, 94, 0.3)",
                transition: "all 0.2s ease",
              }}
            >
              🌱 إضافة أول قطعة
            </button>
          </div>
        ) : (
          /* Plot Cards */
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {plots.map((plot) => {
              const plotCrops = cropCycles.filter(c => c.plotId === plot.id);
              return (
                <Link 
                  href={`/farm/${farmId}/plot/${plot.id}`}
                  key={plot.id} 
                  style={{ textDecoration: "none", color: "inherit", display: "block" }}
                >
                  <div
                    style={{ 
                      padding: "14px 16px",
                      background: "rgba(15, 23, 42, 0.4)",
                      borderRadius: "12px",
                      border: "1px solid rgba(71, 85, 105, 0.15)",
                      transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
                      cursor: "pointer",
                    }}
                    onMouseOver={e => {
                      e.currentTarget.style.background = "rgba(15, 23, 42, 0.6)";
                      e.currentTarget.style.borderColor = "rgba(34, 197, 94, 0.2)";
                      e.currentTarget.style.transform = "translateX(-2px)";
                    }}
                    onMouseOut={e => {
                      e.currentTarget.style.background = "rgba(15, 23, 42, 0.4)";
                      e.currentTarget.style.borderColor = "rgba(71, 85, 105, 0.15)";
                      e.currentTarget.style.transform = "translateX(0)";
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                          <h4 style={{ margin: 0, fontWeight: 600, fontSize: "0.95rem", color: "#e8ecf4" }}>
                            {plot.name}
                          </h4>
                          <span style={{
                            fontSize: "0.7rem", color: "#64748b",
                            background: "rgba(51, 65, 85, 0.4)",
                            padding: "2px 8px", borderRadius: "4px",
                          }}>
                            {plot.area} هكتار
                          </span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "0.75rem", color: "#64748b" }}>
                          {plot.soilType && (
                            <span>{SOIL_LABELS[plot.soilType] || plot.soilType}</span>
                          )}
                          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            {IRRIGATION_ICONS[plot.irrigation || ""] || "🌧️"}
                            {IRRIGATION_LABELS[plot.irrigation || ""] || "بعلي"}
                          </span>
                        </div>
                      </div>

                      {/* Arrow */}
                      <div style={{ color: "#475569", fontSize: "0.9rem", marginTop: "4px" }}>←</div>
                    </div>

                    {/* Active crops */}
                    {plotCrops.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "10px" }}>
                        {plotCrops.map((crop) => {
                          const style = STATUS_STYLES[crop.status] || STATUS_STYLES.PLANNED;
                          return (
                            <span 
                              key={crop.id} 
                              style={{ 
                                fontSize: "0.7rem", fontWeight: 600,
                                padding: "3px 10px", borderRadius: "9999px",
                                background: style.bg, color: style.color,
                                border: `1px solid ${style.color}20`,
                              }}
                            >
                              {crop.cropNameAr || crop.cropCode}
                              {crop.variety ? ` — ${crop.variety}` : ""}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {showAddForm && (
        <AddPlotForm 
          farmId={farmId} 
          farmCoordinates={farmCoordinates}
          onClose={() => setShowAddForm(false)} 
        />
      )}
    </>
  );
}

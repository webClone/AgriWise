"use client";

import { useState } from "react";
import Link from "next/link";
import AddPlotForm from "./AddPlotForm";
import { useLanguage } from "@/lib/i18n/LanguageContext";
import { ChevronRight, ChevronLeft, Plus, Sprout, Layers } from "lucide-react";

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

const SOIL_LABELS: Record<string, { ar: string; en: string; fr: string }> = {
  CLAY: { ar: "طينية", en: "Clay", fr: "Argileux" },
  SANDY: { ar: "رملية", en: "Sandy", fr: "Sableux" },
  LOAM: { ar: "طميية", en: "Loam", fr: "Limoneux" },
  SILT: { ar: "غرينية", en: "Silt", fr: "Silt" },
  PEAT: { ar: "خثية", en: "Peat", fr: "Tourbeux" },
  CHALKY: { ar: "كلسية", en: "Chalky", fr: "Calcaire" },
};

const IRRIGATION_LABELS: Record<string, { ar: string; en: string; fr: string }> = {
  DRIP: { ar: "تقطير", en: "Drip", fr: "Goutte-à-goutte" },
  SPRINKLER: { ar: "رش", en: "Sprinkler", fr: "Aspersion" },
  PIVOT: { ar: "محوري", en: "Center Pivot", fr: "Pivot" },
  FLOOD: { ar: "غمر", en: "Surface / Flood", fr: "Gravitaire" },
  RAINFED: { ar: "بعلي", en: "Rainfed", fr: "Pluvial" },
};

const IRRIGATION_ICONS: Record<string, string> = {
  DRIP: "💧", SPRINKLER: "🔄", PIVOT: "⭕",
  FLOOD: "🌊", RAINFED: "🌧️", "": "🌧️",
};

const STATUS_STYLES: Record<string, { bg: string; color: string; labelAr: string; labelEn: string; labelFr: string }> = {
  GROWING: { bg: "rgba(34, 197, 94, 0.12)", color: "#4ade80", labelAr: "نمو", labelEn: "Vegetative", labelFr: "Végétation" },
  FLOWERING: { bg: "rgba(236, 72, 153, 0.12)", color: "#f472b6", labelAr: "إزهار", labelEn: "Flowering", labelFr: "Floraison" },
  PLANTED: { bg: "rgba(59, 130, 246, 0.12)", color: "#93c5fd", labelAr: "مزروع", labelEn: "Planted", labelFr: "Semé" },
  FRUITING: { bg: "rgba(251, 146, 60, 0.12)", color: "#fb923c", labelAr: "إثمار", labelEn: "Fruiting", labelFr: "Fructification" },
  READY_TO_HARVEST: { bg: "rgba(234, 179, 8, 0.12)", color: "#facc15", labelAr: "جاهز للحصاد", labelEn: "Ready to Harvest", labelFr: "Prêt à récolter" },
  HARVESTED: { bg: "rgba(148, 163, 184, 0.12)", color: "#94a3b8", labelAr: "محصود", labelEn: "Harvested", labelFr: "Récolté" },
  PLANNED: { bg: "rgba(99, 102, 241, 0.12)", color: "#a5b4fc", labelAr: "مخطط", labelEn: "Planned", labelFr: "Planifié" },
  FAILED: { bg: "rgba(239, 68, 68, 0.12)", color: "#f87171", labelAr: "فشل", labelEn: "Failed", labelFr: "Échoué" },
};

export default function PlotsSection({ farmId, plots, cropCycles, farmCoordinates }: PlotsSectionProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const { locale, isRtl } = useLanguage();

  const title = locale === "ar" ? "قطع الأرض" : locale === "fr" ? "Parcelles cadastrales" : "Farm Plots";
  const addPlotLabel = locale === "ar" ? "+ إضافة قطعة" : locale === "fr" ? "+ Ajouter une parcelle" : "+ Add Plot";
  const areaUnit = locale === "ar" ? "هكتار" : "ha";
  const emptyTitle = locale === "ar" ? "لا توجد قطع مسجلة لهذه المزرعة" : locale === "fr" ? "Aucune parcelle enregistrée" : "No plots mapped for this farm yet";
  const emptySub = locale === "ar" ? "ابدأ بتحديد قطع أرضك ورسم حدودها على الخريطة" : locale === "fr" ? "Délimitez vos parcelles et tracez leurs polygones sur la carte satellite" : "Start by registering your parcels and drawing polygon boundaries on satellite imagery";
  const emptyBtn = locale === "ar" ? "إضافة أول قطعة" : locale === "fr" ? "Ajouter la première parcelle" : "Add First Plot";

  return (
    <>
      <div 
        style={{
          marginBottom: "1.5rem",
          padding: "24px",
          background: "rgba(15, 23, 42, 0.5)",
          backdropFilter: "blur(16px)",
          borderRadius: "18px",
          border: "1px solid rgba(71, 85, 105, 0.15)",
          boxShadow: "0 10px 40px rgba(0,0,0,0.25)",
        }} 
        suppressHydrationWarning={true}
      >
        {/* Header */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          marginBottom: plots.length > 0 ? "20px" : "0",
        }} suppressHydrationWarning={true}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }} suppressHydrationWarning={true}>
            <div style={{
              width: "32px", height: "32px", borderRadius: "8px",
              background: "rgba(34, 197, 94, 0.1)",
              border: "1px solid rgba(34, 197, 94, 0.2)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#4ade80",
            }}>
              <Layers size={16} />
            </div>
            <h3 style={{ margin: 0, fontWeight: 700, fontSize: "1.1rem", color: "#f8fafc" }}>
              {title}
            </h3>
            {plots.length > 0 && (
              <span style={{
                fontSize: "0.75rem", fontWeight: 700,
                background: "rgba(34, 197, 94, 0.12)", color: "#4ade80",
                padding: "2px 10px", borderRadius: "9999px",
                border: "1px solid rgba(34, 197, 94, 0.25)",
              }}>
                {plots.length}
              </span>
            )}
          </div>
          <button
            onClick={() => setShowAddForm(true)}
            style={{
              padding: "8px 16px", borderRadius: "10px",
              fontSize: "0.82rem", fontWeight: 600, cursor: "pointer",
              background: "rgba(34, 197, 94, 0.12)",
              border: "1px solid rgba(34, 197, 94, 0.3)",
              color: "#4ade80",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
            }}
            onMouseOver={e => {
              e.currentTarget.style.background = "rgba(34, 197, 94, 0.22)";
              e.currentTarget.style.transform = "translateY(-1px)";
            }}
            onMouseOut={e => {
              e.currentTarget.style.background = "rgba(34, 197, 94, 0.12)";
              e.currentTarget.style.transform = "translateY(0)";
            }}
          >
            <Plus size={14} />
            <span>{addPlotLabel}</span>
          </button>
        </div>
        
        {plots.length === 0 ? (
          /* Empty State */
          <div style={{
            textAlign: "center", padding: "3.5rem 2rem",
            border: "1px dashed rgba(71, 85, 105, 0.25)",
            borderRadius: "16px",
            background: "linear-gradient(135deg, rgba(15, 23, 42, 0.4), rgba(15, 23, 42, 0.15))",
          }}>
            <div style={{
              width: "64px", height: "64px", borderRadius: "18px",
              background: "rgba(34, 197, 94, 0.1)",
              border: "1px solid rgba(34, 197, 94, 0.2)",
              display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 1.25rem", fontSize: "1.75rem",
            }}>
              🗺️
            </div>
            <p style={{ fontWeight: 700, fontSize: "1.05rem", color: "#f1f5f9", margin: "0 0 0.5rem 0" }}>
              {emptyTitle}
            </p>
            <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: "0 0 1.5rem 0", maxWidth: "420px", marginLeft: "auto", marginRight: "auto", lineHeight: 1.5 }}>
              {emptySub}
            </p>
            <button
              onClick={() => setShowAddForm(true)}
              style={{
                padding: "10px 24px", borderRadius: "12px",
                fontWeight: 700, fontSize: "0.88rem", cursor: "pointer",
                background: "linear-gradient(135deg, #22c55e, #16a34a)",
                border: "none", color: "#fff",
                boxShadow: "0 4px 20px rgba(34, 197, 94, 0.35)",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                transition: "all 0.2s ease",
              }}
            >
              <Sprout size={16} />
              <span>{emptyBtn}</span>
            </button>
          </div>
        ) : (
          /* Plot Cards */
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "14px" }} suppressHydrationWarning={true}>
            {plots.map((plot) => {
              const plotCrops = cropCycles.filter(c => c.plotId === plot.id);
              const soilLabel = plot.soilType ? (SOIL_LABELS[plot.soilType]?.[locale] || plot.soilType) : null;
              const irrigationLabel = plot.irrigation ? (IRRIGATION_LABELS[plot.irrigation]?.[locale] || plot.irrigation) : null;

              return (
                <Link 
                  href={`/farm/${farmId}/plot/${plot.id}`}
                  key={plot.id} 
                  style={{ textDecoration: "none", color: "inherit", display: "block" }}
                >
                  <div
                    style={{ 
                      padding: "16px 18px",
                      background: "rgba(15, 23, 42, 0.6)",
                      borderRadius: "14px",
                      border: "1px solid rgba(71, 85, 105, 0.18)",
                      transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
                      cursor: "pointer",
                      position: "relative",
                      overflow: "hidden",
                    }}
                    onMouseOver={e => {
                      e.currentTarget.style.background = "rgba(15, 23, 42, 0.85)";
                      e.currentTarget.style.borderColor = "rgba(34, 197, 94, 0.35)";
                      e.currentTarget.style.transform = "translateY(-3px)";
                      e.currentTarget.style.boxShadow = "0 12px 30px rgba(0,0,0,0.3), 0 0 20px rgba(34,197,94,0.06)";
                    }}
                    onMouseOut={e => {
                      e.currentTarget.style.background = "rgba(15, 23, 42, 0.6)";
                      e.currentTarget.style.borderColor = "rgba(71, 85, 105, 0.18)";
                      e.currentTarget.style.transform = "translateY(0)";
                      e.currentTarget.style.boxShadow = "none";
                    }}
                    suppressHydrationWarning={true}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }} suppressHydrationWarning={true}>
                      <div style={{ flex: 1 }} suppressHydrationWarning={true}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }} suppressHydrationWarning={true}>
                          <h4 style={{ margin: 0, fontWeight: 700, fontSize: "1rem", color: "#f8fafc" }}>
                            {locale === "ar" && plot.nameAr ? plot.nameAr : plot.name}
                          </h4>
                          <span style={{
                            fontSize: "0.72rem", color: "#4ade80",
                            background: "rgba(34, 197, 94, 0.1)",
                            border: "1px solid rgba(34, 197, 94, 0.2)",
                            padding: "2px 8px", borderRadius: "6px", fontWeight: 700,
                          }}>
                            {plot.area} {areaUnit}
                          </span>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "0.78rem", color: "#94a3b8", flexWrap: "wrap" }} suppressHydrationWarning={true}>
                          {soilLabel && (
                            <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                              🪨 {soilLabel}
                            </span>
                          )}
                          <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                            {IRRIGATION_ICONS[plot.irrigation || ""] || "🌧️"}
                            {irrigationLabel || (locale === "ar" ? "بعلي" : "Rainfed")}
                          </span>
                        </div>
                      </div>

                      {/* Directional arrow */}
                      <div style={{ color: "#4ade80", opacity: 0.8, marginTop: "2px" }} suppressHydrationWarning={true}>
                        {isRtl ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
                      </div>
                    </div>

                    {/* Active crops */}
                    {plotCrops.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "12px", borderTop: "1px solid rgba(71,85,105,0.12)", paddingTop: "10px" }} suppressHydrationWarning={true}>
                        {plotCrops.map((crop) => {
                          const style = STATUS_STYLES[crop.status] || STATUS_STYLES.PLANNED;
                          const cropName = locale === "ar" && crop.cropNameAr ? crop.cropNameAr : crop.cropCode;
                          const statusLabel = locale === "ar" ? style.labelAr : locale === "fr" ? style.labelFr : style.labelEn;

                          return (
                            <div 
                              key={crop.id} 
                              style={{ 
                                fontSize: "0.72rem", fontWeight: 600,
                                padding: "3px 10px", borderRadius: "9999px",
                                background: style.bg, color: style.color,
                                border: `1px solid ${style.color}25`,
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "6px",
                              }}
                            >
                              <span>{cropName}</span>
                              {crop.variety && <span style={{ opacity: 0.7 }}>({crop.variety})</span>}
                              <span style={{ fontSize: "0.65rem", padding: "1px 6px", borderRadius: "4px", background: "rgba(0,0,0,0.25)" }}>{statusLabel}</span>
                            </div>
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

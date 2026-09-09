"use client";

import { useState, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";

const MapDrawer = dynamic(() => import("@/components/farm/MapDrawer"), { 
  ssr: false,
  loading: () => (
    <div style={{
      height: "100%", width: "100%",
      background: "linear-gradient(135deg, #0c1224 0%, #131b36 100%)",
      borderRadius: "16px",
      display: "flex", alignItems: "center", justifyContent: "center",
      color: "#64748b", fontSize: "0.875rem",
    }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem", animation: "pulse 2s infinite" }}>🗺️</div>
        Loading satellite map...
      </div>
    </div>
  )
});

interface AddPlotFormProps {
  farmId: string;
  farmCoordinates?: { lat: number; lng: number };
  onClose: () => void;
  onSuccess?: () => void;
  initialData?: any;
}

const SOIL_TYPES = [
  { value: "", labelEn: "Unspecified", labelAr: "غير محدد", icon: "🪨", descEn: "Not specified", descAr: "غير محدد" },
  { value: "CLAY", labelEn: "Clay", labelAr: "طينية", icon: "🟤", descEn: "Heavy, retains water", descAr: "ثقيلة، تحتفظ بالماء" },
  { value: "SANDY", labelEn: "Sandy", labelAr: "رملية", icon: "🟡", descEn: "Light, fast draining", descAr: "خفيفة، سريعة الصرف" },
  { value: "LOAM", labelEn: "Loam", labelAr: "طميية", icon: "🟠", descEn: "Balanced, ideal", descAr: "متوازنة، مثالية" },
  { value: "SILT", labelEn: "Silt", labelAr: "غرينية", icon: "🔵", descEn: "Fine, fertile", descAr: "ناعمة، خصبة" },
  { value: "PEAT", labelEn: "Peat", labelAr: "خثية", icon: "⬛", descEn: "Organic, acidic", descAr: "عضوية، حمضية" },
  { value: "CHALKY", labelEn: "Chalky", labelAr: "كلسية", icon: "⬜", descEn: "Alkaline, stony", descAr: "قلوية، صخرية" },
];

const IRRIGATION_TYPES = [
  { value: "", labelEn: "Rainfed", labelAr: "بعلي (مطري)", icon: "🌧️" },
  { value: "DRIP", labelEn: "Drip", labelAr: "تقطير", icon: "💧" },
  { value: "SPRINKLER", labelEn: "Sprinkler", labelAr: "رش", icon: "🔄" },
  { value: "PIVOT", labelEn: "Center Pivot", labelAr: "محوري", icon: "⭕" },
  { value: "FLOOD", labelEn: "Surface / Flood", labelAr: "غمر", icon: "🌊" },
];

const I18N = {
  en: {
    addTitle: "Add New Plot",
    editTitle: "Edit Plot",
    step1Sub: "Define plot boundaries on the satellite map",
    step2Sub: "Complete plot agronomic details",
    loadingMap: "Loading map...",
    mapUnavailable: "Map unavailable",
    noCoords: "Farm coordinates not available. Please set farm location first.",
    hectares: "hectares",
    points: "vertices",
    fromDrawing: "✓ From map boundary",
    nextBtn: "Next →",
    backBtn: "← Back to Map",
    cancelBtn: "Cancel",
    saveBtn: "Save Plot",
    savingBtn: "Saving...",
    plotName: "Plot Name *",
    plotNamePlaceholder: "e.g., North Olive Grove",
    plotArea: "Area (ha) *",
    soilType: "Soil Type",
    irrigationType: "Irrigation System",
    hintMap: "🪄 Use Magic Wand, ⚡ Auto-Detect, or ✏️ draw manually to delineate field boundary.",
    submitError: "An error occurred while saving the plot.",
    genericError: "An error occurred. Please try again.",
  },
  ar: {
    addTitle: "إضافة قطعة جديدة",
    editTitle: "تعديل القطعة",
    step1Sub: "حدد حدود القطعة على الخريطة الفضائية",
    step2Sub: "أكمل بيانات القطعة الزراعية",
    loadingMap: "جاري تحميل الخريطة...",
    mapUnavailable: "لا يمكن عرض الخريطة",
    noCoords: "إحداثيات المزرعة غير متوفرة. يرجى تحديث موقع المزرعة أولاً.",
    hectares: "هكتار",
    points: "نقطة",
    fromDrawing: "✓ من الرسم",
    nextBtn: "التالي ←",
    backBtn: "→ العودة للخريطة",
    cancelBtn: "إلغاء",
    saveBtn: "حفظ القطعة",
    savingBtn: "جاري الحفظ...",
    plotName: "اسم القطعة *",
    plotNamePlaceholder: "مثال: القطعة الشمالية",
    plotArea: "المساحة (هكتار) *",
    soilType: "نوع التربة",
    irrigationType: "نظام الري",
    hintMap: "🪄 استخدم المحدد الذكي، ⚡ الكشف التلقائي، أو ✏️ ارسم يدوياً لتحديد الحقل.",
    submitError: "حدث خطأ أثناء إنشاء القطعة",
    genericError: "حدث خطأ. حاول مرة أخرى.",
  },
};

export default function AddPlotForm({ farmId, farmCoordinates, onClose, onSuccess, initialData }: AddPlotFormProps) {
  const router = useRouter();
  const [lang, setLang] = useState<"en" | "ar">("en");
  const [mounted, setMounted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [geoJson, setGeoJson] = useState<any>(initialData?.geoJson || null);
  const [step, setStep] = useState<1 | 2>(1); // 1 = map, 2 = details
  const [formData, setFormData] = useState({
    name: initialData?.name || "",
    area: initialData?.area?.toString() || "",
    soilType: initialData?.soilType || "",
    irrigation: initialData?.irrigation || "",
  });

  const t = I18N[lang];

  useEffect(() => {
    setMounted(true);
    // Lock body scroll when modal is open
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const payload = { ...formData, farmId, geoJson };
      const url = initialData ? `/api/plots/${initialData.id}` : "/api/plots";
      const method = initialData ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.success) {
        router.refresh();
        onSuccess?.();
        onClose();
      } else {
        setError(data.error || t.submitError);
      }
    } catch {
      setError(t.genericError);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleDrawCreated = useCallback((geometry: any, area: number) => {
    setGeoJson(geometry);
    if (area > 0) {
      const areaStr = area.toFixed(2);
      setFormData(prev => (prev.area === areaStr ? prev : { ...prev, area: areaStr }));
    }
  }, []);

  // Compute polygon stats from geoJson
  const polygonStats = geoJson?.geometry?.coordinates?.[0]
    ? {
        points: geoJson.geometry.coordinates[0].length - 1,
        area: parseFloat(formData.area) || 0,
      }
    : null;

  if (!mounted) return null;

  return createPortal(
    <div
      style={{
        position: "fixed", inset: 0,
        background: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 99999, padding: "1rem",
        animation: "fadeIn 0.2s ease-out",
        direction: lang === "ar" ? "rtl" : "ltr",
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        style={{
          position: "relative",
          width: "100%", maxWidth: "980px", maxHeight: "94vh",
          background: "linear-gradient(180deg, #0a1628 0%, #0c1224 100%)",
          border: "1px solid rgba(71, 85, 105, 0.25)",
          borderRadius: "20px",
          boxShadow: "0 24px 80px rgba(0, 0, 0, 0.7), 0 8px 32px rgba(0, 0, 0, 0.4)",
          overflow: "hidden",
          display: "flex", flexDirection: "column",
          animation: "slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        {/* ─── Header Bar ─────────────────────────────────────────── */}
        <div style={{
          padding: "16px 22px",
          borderBottom: "1px solid rgba(71, 85, 105, 0.2)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: "rgba(15, 23, 42, 0.6)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div style={{
              width: "38px", height: "38px", borderRadius: "10px",
              background: "linear-gradient(135deg, rgba(34, 197, 94, 0.25), rgba(16, 185, 129, 0.15))",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "1.2rem",
            }}>
              🌱
            </div>
            <div>
              <h3 style={{ margin: 0, fontWeight: 700, fontSize: "1.05rem", color: "#f1f5f9" }}>
                {initialData ? t.editTitle : t.addTitle}
              </h3>
              <p style={{ margin: 0, fontSize: "0.75rem", color: "#94a3b8" }}>
                {step === 1 ? t.step1Sub : t.step2Sub}
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            {/* Language Switcher */}
            <button
              type="button"
              onClick={() => setLang(l => (l === "en" ? "ar" : "en"))}
              style={{
                background: "rgba(51, 65, 85, 0.4)",
                border: "1px solid rgba(71, 85, 105, 0.35)",
                borderRadius: "8px",
                padding: "5px 10px",
                color: "#38bdf8",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.2s ease",
                display: "flex",
                alignItems: "center",
                gap: "5px",
              }}
              title="Toggle Language"
              onMouseOver={e => e.currentTarget.style.borderColor = "rgba(56, 189, 248, 0.5)"}
              onMouseOut={e => e.currentTarget.style.borderColor = "rgba(71, 85, 105, 0.35)"}
            >
              <span>🌐</span>
              <span>{lang === "en" ? "عربي" : "English"}</span>
            </button>

            {/* Step Indicator */}
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <div style={{
                width: "26px", height: "26px", borderRadius: "50%", fontSize: "0.75rem", fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: step === 1 ? "rgba(34, 197, 94, 0.2)" : "rgba(34, 197, 94, 0.15)",
                color: step === 1 ? "#4ade80" : "#22c55e",
                border: step === 1 ? "1.5px solid rgba(34, 197, 94, 0.5)" : "1.5px solid rgba(34, 197, 94, 0.2)",
              }}>
                {geoJson ? "✓" : "1"}
              </div>
              <div style={{ width: "20px", height: "1px", background: "rgba(71, 85, 105, 0.3)" }} />
              <div style={{
                width: "26px", height: "26px", borderRadius: "50%", fontSize: "0.75rem", fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: step === 2 ? "rgba(34, 197, 94, 0.2)" : "rgba(51, 65, 85, 0.3)",
                color: step === 2 ? "#4ade80" : "#64748b",
                border: step === 2 ? "1.5px solid rgba(34, 197, 94, 0.5)" : "1.5px solid rgba(51, 65, 85, 0.3)",
              }}>
                2
              </div>
            </div>

            <button
              onClick={onClose}
              style={{
                background: "rgba(51, 65, 85, 0.3)", border: "1px solid rgba(71, 85, 105, 0.2)",
                borderRadius: "8px", width: "32px", height: "32px",
                display: "flex", alignItems: "center", justifyContent: "center",
                cursor: "pointer", color: "#94a3b8", fontSize: "1rem",
                transition: "all 0.2s ease",
              }}
              onMouseOver={e => { e.currentTarget.style.background = "rgba(239, 68, 68, 0.15)"; e.currentTarget.style.color = "#f87171"; }}
              onMouseOut={e => { e.currentTarget.style.background = "rgba(51, 65, 85, 0.3)"; e.currentTarget.style.color = "#94a3b8"; }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* ─── Content ─────────────────────────────────────────────── */}
        <div style={{ flex: 1, overflow: "auto" }}>

          {/* STEP 1: Map Drawing & Auto-Detection */}
          {step === 1 && (
            <div style={{ display: "flex", flexDirection: "column", width: "100%" }}>
              {/* Map Container */}
              <div style={{ height: "460px", position: "relative", overflow: "hidden", width: "100%" }}>
                {farmCoordinates ? (
                  <MapDrawer 
                    center={[farmCoordinates.lat, farmCoordinates.lng]} 
                    onDrawCreated={handleDrawCreated}
                    initialGeoJson={geoJson}
                    lang={lang}
                  />
                ) : (
                  <div style={{
                    height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
                    background: "linear-gradient(135deg, #0c1224, #131b36)",
                    color: "#64748b", textAlign: "center", padding: "2rem",
                  }}>
                    <div>
                      <div style={{ fontSize: "2.5rem", marginBottom: "1rem", opacity: 0.5 }}>📍</div>
                      <p style={{ fontSize: "0.9rem", fontWeight: 500, color: "#94a3b8" }}>{t.mapUnavailable}</p>
                      <p style={{ fontSize: "0.8rem", marginTop: "0.5rem" }}>{t.noCoords}</p>
                    </div>
                  </div>
                )}

                {/* Polygon Stats Overlay */}
                {polygonStats && (
                  <div style={{
                    position: "absolute", bottom: "16px",
                    [lang === "ar" ? "right" : "left"]: "16px",
                    zIndex: 1000,
                    background: "rgba(8, 12, 25, 0.94)", backdropFilter: "blur(14px)",
                    border: "1px solid rgba(34, 197, 94, 0.3)", borderRadius: "12px",
                    padding: "10px 16px", display: "flex", alignItems: "center", gap: "16px",
                    boxShadow: "0 8px 30px rgba(0,0,0,0.5)",
                  }}>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "1.05rem", fontWeight: 700, color: "#4ade80" }}>
                        {polygonStats.area.toFixed(2)}
                      </div>
                      <div style={{ fontSize: "0.65rem", color: "#94a3b8", marginTop: "2px" }}>{t.hectares}</div>
                    </div>
                    <div style={{ width: "1px", height: "28px", background: "rgba(71, 85, 105, 0.3)" }} />
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "1.05rem", fontWeight: 700, color: "#94a3b8" }}>
                        {polygonStats.points}
                      </div>
                      <div style={{ fontSize: "0.65rem", color: "#64748b", marginTop: "2px" }}>{t.points}</div>
                    </div>
                  </div>
                )}
              </div>

              {/* Map Instructions + Next */}
              <div style={{
                padding: "14px 22px",
                borderTop: "1px solid rgba(71, 85, 105, 0.18)",
                display: "flex", alignItems: "center", justifyContent: "space-between",
                background: "rgba(15, 23, 42, 0.6)",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "0.85rem" }}>💡</span>
                  <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                    {t.hintMap}
                  </span>
                </div>
                <button
                  onClick={() => setStep(2)}
                  style={{
                    padding: "9px 22px", borderRadius: "10px", fontWeight: 600, fontSize: "0.85rem",
                    cursor: "pointer", transition: "all 0.2s ease",
                    border: "none",
                    background: geoJson
                      ? "linear-gradient(135deg, #22c55e, #16a34a)"
                      : "rgba(51, 65, 85, 0.4)",
                    color: geoJson ? "#fff" : "#94a3b8",
                    boxShadow: geoJson ? "0 4px 16px rgba(34, 197, 94, 0.3)" : "none",
                  }}
                >
                  {t.nextBtn}
                </button>
              </div>
            </div>
          )}

          {/* STEP 2: Plot Agronomic Details */}
          {step === 2 && (
            <div style={{ padding: "26px" }}>
              {error && (
                <div style={{
                  padding: "12px 16px", borderRadius: "10px", marginBottom: "20px",
                  background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.25)",
                  color: "#f87171", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "8px",
                }}>
                  <span>⚠️</span> {error}
                </div>
              )}

              <form onSubmit={handleSubmit} id="plot-form">
                {/* Plot Name + Area Row */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "18px", marginBottom: "24px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "#94a3b8", marginBottom: "8px" }}>
                      {t.plotName}
                    </label>
                    <input
                      type="text" name="name" required
                      placeholder={t.plotNamePlaceholder}
                      value={formData.name}
                      onChange={handleChange}
                      style={{
                        width: "100%", padding: "12px 14px", borderRadius: "10px",
                        background: "rgba(15, 23, 42, 0.6)",
                        border: "1px solid rgba(71, 85, 105, 0.25)",
                        color: "#e8ecf4", fontSize: "0.9rem",
                        outline: "none", transition: "border-color 0.2s ease",
                      }}
                      onFocus={e => e.target.style.borderColor = "rgba(34, 197, 94, 0.4)"}
                      onBlur={e => e.target.style.borderColor = "rgba(71, 85, 105, 0.25)"}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "#94a3b8", marginBottom: "8px" }}>
                      {t.plotArea}
                    </label>
                    <div style={{ position: "relative" }}>
                      <input
                        type="number" name="area" required step="0.01" min="0.01"
                        placeholder="0.00"
                        value={formData.area}
                        onChange={handleChange}
                        style={{
                          width: "100%", padding: "12px 14px", borderRadius: "10px",
                          background: geoJson ? "rgba(34, 197, 94, 0.06)" : "rgba(15, 23, 42, 0.6)",
                          border: geoJson ? "1px solid rgba(34, 197, 94, 0.3)" : "1px solid rgba(71, 85, 105, 0.25)",
                          color: "#e8ecf4", fontSize: "0.9rem",
                          outline: "none", transition: "border-color 0.2s ease",
                        }}
                        onFocus={e => e.target.style.borderColor = "rgba(34, 197, 94, 0.4)"}
                        onBlur={e => e.target.style.borderColor = geoJson ? "rgba(34, 197, 94, 0.3)" : "rgba(71, 85, 105, 0.25)"}
                      />
                      {geoJson && (
                        <span style={{
                          position: "absolute",
                          [lang === "ar" ? "left" : "right"]: "14px",
                          top: "50%", transform: "translateY(-50%)",
                          fontSize: "0.72rem", color: "#4ade80", fontWeight: 600,
                        }}>
                          {t.fromDrawing}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Soil Type */}
                <div style={{ marginBottom: "24px" }}>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "#94a3b8", marginBottom: "10px" }}>
                    {t.soilType}
                  </label>
                  <div style={{
                    display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(126px, 1fr))",
                    gap: "10px",
                  }}>
                    {SOIL_TYPES.map(soil => (
                      <button
                        key={soil.value}
                        type="button"
                        onClick={() => setFormData(prev => ({ ...prev, soilType: soil.value }))}
                        style={{
                          padding: "10px 8px", borderRadius: "10px", cursor: "pointer",
                          background: formData.soilType === soil.value
                            ? "rgba(34, 197, 94, 0.12)"
                            : "rgba(15, 23, 42, 0.5)",
                          border: formData.soilType === soil.value
                            ? "1.5px solid rgba(34, 197, 94, 0.4)"
                            : "1px solid rgba(71, 85, 105, 0.2)",
                          textAlign: "center", transition: "all 0.2s ease",
                          display: "flex", flexDirection: "column", alignItems: "center", gap: "4px",
                        }}
                        onMouseOver={e => {
                          if (formData.soilType !== soil.value) e.currentTarget.style.borderColor = "rgba(71, 85, 105, 0.4)";
                        }}
                        onMouseOut={e => {
                          if (formData.soilType !== soil.value) e.currentTarget.style.borderColor = "rgba(71, 85, 105, 0.2)";
                        }}
                      >
                        <span style={{ fontSize: "1.1rem" }}>{soil.icon}</span>
                        <span style={{
                          fontSize: "0.82rem", fontWeight: 600,
                          color: formData.soilType === soil.value ? "#4ade80" : "#e8ecf4",
                        }}>
                          {lang === "ar" ? soil.labelAr : soil.labelEn}
                        </span>
                        <span style={{ fontSize: "0.65rem", color: "#64748b", lineHeight: 1.2 }}>
                          {lang === "ar" ? soil.descAr : soil.descEn}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Irrigation Type */}
                <div style={{ marginBottom: "28px" }}>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "#94a3b8", marginBottom: "10px" }}>
                    {t.irrigationType}
                  </label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                    {IRRIGATION_TYPES.map(irr => (
                      <button
                        key={irr.value}
                        type="button"
                        onClick={() => setFormData(prev => ({ ...prev, irrigation: irr.value }))}
                        style={{
                          padding: "10px 16px", borderRadius: "10px", cursor: "pointer",
                          background: formData.irrigation === irr.value
                            ? "rgba(59, 130, 246, 0.12)"
                            : "rgba(15, 23, 42, 0.5)",
                          border: formData.irrigation === irr.value
                            ? "1.5px solid rgba(59, 130, 246, 0.4)"
                            : "1px solid rgba(71, 85, 105, 0.2)",
                          display: "flex", alignItems: "center", gap: "8px",
                          transition: "all 0.2s ease",
                        }}
                        onMouseOver={e => {
                          if (formData.irrigation !== irr.value) e.currentTarget.style.borderColor = "rgba(71, 85, 105, 0.4)";
                        }}
                        onMouseOut={e => {
                          if (formData.irrigation !== irr.value) e.currentTarget.style.borderColor = "rgba(71, 85, 105, 0.2)";
                        }}
                      >
                        <span style={{ fontSize: "1rem" }}>{irr.icon}</span>
                        <span style={{
                          fontSize: "0.85rem", fontWeight: 600,
                          color: formData.irrigation === irr.value ? "#93c5fd" : "#e8ecf4",
                        }}>
                          {lang === "ar" ? irr.labelAr : irr.labelEn}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Actions Bar */}
                <div style={{
                  display: "flex", gap: "10px", alignItems: "center",
                  paddingTop: "16px", borderTop: "1px solid rgba(71, 85, 105, 0.18)",
                }}>
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    style={{
                      padding: "10px 18px", borderRadius: "10px", fontWeight: 600, fontSize: "0.85rem",
                      cursor: "pointer", transition: "all 0.2s ease",
                      background: "rgba(51, 65, 85, 0.3)", border: "1px solid rgba(71, 85, 105, 0.2)",
                      color: "#94a3b8",
                    }}
                  >
                    {t.backBtn}
                  </button>

                  <div style={{ flex: 1 }} />

                  <button
                    type="button"
                    onClick={onClose}
                    style={{
                      padding: "10px 18px", borderRadius: "10px", fontWeight: 600, fontSize: "0.85rem",
                      cursor: "pointer", transition: "all 0.2s ease",
                      background: "transparent", border: "1px solid rgba(71, 85, 105, 0.2)",
                      color: "#94a3b8",
                    }}
                  >
                    {t.cancelBtn}
                  </button>

                  <button
                    type="submit"
                    disabled={loading || !formData.name || !formData.area}
                    style={{
                      padding: "10px 28px", borderRadius: "10px", fontWeight: 700, fontSize: "0.9rem",
                      cursor: loading ? "wait" : "pointer",
                      transition: "all 0.25s ease",
                      border: "none",
                      background: (loading || !formData.name || !formData.area)
                        ? "rgba(51, 65, 85, 0.4)"
                        : "linear-gradient(135deg, #22c55e, #16a34a)",
                      color: (loading || !formData.name || !formData.area) ? "#64748b" : "#fff",
                      boxShadow: (loading || !formData.name || !formData.area) ? "none" : "0 4px 20px rgba(34, 197, 94, 0.35)",
                    }}
                  >
                    {loading ? (
                      <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span style={{ animation: "spin 1s linear infinite", display: "inline-block" }}>⏳</span>
                        {t.savingBtn}
                      </span>
                    ) : (
                      `💾 ${t.saveBtn}`
                    )}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

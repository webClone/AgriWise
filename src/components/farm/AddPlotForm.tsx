"use client";

import { useState, useCallback } from "react";
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
        جاري تحميل الخريطة...
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
  { value: "", label: "غير محدد", icon: "🪨" },
  { value: "CLAY", label: "طينية", icon: "🟤", desc: "ثقيلة، تحتفظ بالماء" },
  { value: "SANDY", label: "رملية", icon: "🟡", desc: "خفيفة، سريعة الصرف" },
  { value: "LOAM", label: "طميية", icon: "🟠", desc: "متوازنة، مثالية" },
  { value: "SILT", label: "غرينية", icon: "🔵", desc: "ناعمة، خصبة" },
  { value: "PEAT", label: "خثية", icon: "⬛", desc: "عضوية، حمضية" },
  { value: "CHALKY", label: "كلسية", icon: "⬜", desc: "قلوية، صخرية" },
];

const IRRIGATION_TYPES = [
  { value: "", label: "بعلي (مطري)", icon: "🌧️" },
  { value: "DRIP", label: "تقطير", icon: "💧" },
  { value: "SPRINKLER", label: "رش", icon: "🔄" },
  { value: "PIVOT", label: "محوري", icon: "⭕" },
  { value: "FLOOD", label: "غمر", icon: "🌊" },
];

export default function AddPlotForm({ farmId, farmCoordinates, onClose, onSuccess, initialData }: AddPlotFormProps) {
  const router = useRouter();
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
        setError(data.error || "حدث خطأ أثناء إنشاء القطعة");
      }
    } catch {
      setError("حدث خطأ. حاول مرة أخرى.");
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
      setFormData(prev => ({ ...prev, area: area.toFixed(2) }));
    }
  }, []);

  // Compute polygon stats from geoJson
  const polygonStats = geoJson?.geometry?.coordinates?.[0]
    ? {
        points: geoJson.geometry.coordinates[0].length - 1,
        area: parseFloat(formData.area) || 0,
      }
    : null;

  return (
    <div
      style={{
        position: "fixed", inset: 0,
        background: "rgba(0, 0, 0, 0.7)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 1000, padding: "1rem",
        animation: "fadeIn 0.2s ease-out",
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        style={{
          width: "100%", maxWidth: "960px", maxHeight: "92vh",
          background: "linear-gradient(180deg, #0a1628 0%, #0c1224 100%)",
          border: "1px solid rgba(71, 85, 105, 0.2)",
          borderRadius: "20px",
          boxShadow: "0 24px 80px rgba(0, 0, 0, 0.6), 0 8px 32px rgba(0, 0, 0, 0.4)",
          overflow: "hidden",
          display: "flex", flexDirection: "column",
          animation: "slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        {/* ─── Header Bar ─────────────────────────────────────────── */}
        <div style={{
          padding: "16px 20px",
          borderBottom: "1px solid rgba(71, 85, 105, 0.15)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: "rgba(15, 23, 42, 0.5)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div style={{
              width: "36px", height: "36px", borderRadius: "10px",
              background: "linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(16, 185, 129, 0.1))",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "1.1rem",
            }}>
              🌱
            </div>
            <div>
              <h3 style={{ margin: 0, fontWeight: 600, fontSize: "1rem", color: "#e8ecf4" }}>
                {initialData ? "تعديل القطعة" : "إضافة قطعة جديدة"}
              </h3>
              <p style={{ margin: 0, fontSize: "0.75rem", color: "#64748b" }}>
                {step === 1 ? "حدد حدود القطعة على الخريطة" : "أكمل بيانات القطعة"}
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {/* Step Indicator */}
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <div style={{
                width: "24px", height: "24px", borderRadius: "50%", fontSize: "0.7rem", fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: step === 1 ? "rgba(34, 197, 94, 0.2)" : "rgba(34, 197, 94, 0.15)",
                color: step === 1 ? "#4ade80" : "#22c55e",
                border: step === 1 ? "1.5px solid rgba(34, 197, 94, 0.4)" : "1.5px solid rgba(34, 197, 94, 0.2)",
              }}>
                {geoJson ? "✓" : "1"}
              </div>
              <div style={{ width: "20px", height: "1px", background: "rgba(71, 85, 105, 0.3)" }} />
              <div style={{
                width: "24px", height: "24px", borderRadius: "50%", fontSize: "0.7rem", fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: step === 2 ? "rgba(34, 197, 94, 0.2)" : "rgba(51, 65, 85, 0.3)",
                color: step === 2 ? "#4ade80" : "#64748b",
                border: step === 2 ? "1.5px solid rgba(34, 197, 94, 0.4)" : "1.5px solid rgba(51, 65, 85, 0.3)",
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

          {/* STEP 1: Map Drawing */}
          {step === 1 && (
            <div style={{ display: "flex", flexDirection: "column" }}>
              {/* Map Container */}
              <div style={{ height: "450px", position: "relative" }}>
                {farmCoordinates ? (
                  <MapDrawer 
                    center={[farmCoordinates.lat, farmCoordinates.lng]} 
                    onDrawCreated={handleDrawCreated}
                  />
                ) : (
                  <div style={{
                    height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
                    background: "linear-gradient(135deg, #0c1224, #131b36)",
                    color: "#64748b", textAlign: "center", padding: "2rem",
                  }}>
                    <div>
                      <div style={{ fontSize: "2.5rem", marginBottom: "1rem", opacity: 0.5 }}>📍</div>
                      <p style={{ fontSize: "0.9rem", fontWeight: 500, color: "#94a3b8" }}>لا يمكن عرض الخريطة</p>
                      <p style={{ fontSize: "0.8rem", marginTop: "0.5rem" }}>إحداثيات المزرعة غير متوفرة. يرجى تحديث موقع المزرعة أولاً.</p>
                    </div>
                  </div>
                )}

                {/* Polygon Stats Overlay */}
                {polygonStats && (
                  <div style={{
                    position: "absolute", bottom: "12px", right: "12px", zIndex: 1000,
                    background: "rgba(8, 12, 25, 0.92)", backdropFilter: "blur(12px)",
                    border: "1px solid rgba(34, 197, 94, 0.2)", borderRadius: "10px",
                    padding: "10px 14px", display: "flex", alignItems: "center", gap: "16px",
                  }}>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "1rem", fontWeight: 700, color: "#4ade80" }}>
                        {polygonStats.area.toFixed(2)}
                      </div>
                      <div style={{ fontSize: "0.65rem", color: "#64748b", marginTop: "2px" }}>هكتار</div>
                    </div>
                    <div style={{ width: "1px", height: "28px", background: "rgba(71, 85, 105, 0.3)" }} />
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: "1rem", fontWeight: 700, color: "#94a3b8" }}>
                        {polygonStats.points}
                      </div>
                      <div style={{ fontSize: "0.65rem", color: "#64748b", marginTop: "2px" }}>نقطة</div>
                    </div>
                  </div>
                )}
              </div>

              {/* Map Instructions + Next */}
              <div style={{
                padding: "14px 20px",
                borderTop: "1px solid rgba(71, 85, 105, 0.15)",
                display: "flex", alignItems: "center", justifyContent: "space-between",
                background: "rgba(15, 23, 42, 0.5)",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "0.8rem" }}>✏️</span>
                  <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                    ارسم المضلع باستخدام أداة الرسم في الزاوية العلوية — سيتم حساب المساحة تلقائياً
                  </span>
                </div>
                <button
                  onClick={() => setStep(2)}
                  style={{
                    padding: "8px 20px", borderRadius: "10px", fontWeight: 600, fontSize: "0.85rem",
                    cursor: "pointer", transition: "all 0.2s ease",
                    border: "none",
                    background: geoJson
                      ? "linear-gradient(135deg, #22c55e, #16a34a)"
                      : "rgba(51, 65, 85, 0.4)",
                    color: geoJson ? "#fff" : "#94a3b8",
                    boxShadow: geoJson ? "0 4px 16px rgba(34, 197, 94, 0.3)" : "none",
                  }}
                >
                  التالي ←
                </button>
              </div>
            </div>
          )}

          {/* STEP 2: Plot Details */}
          {step === 2 && (
            <div style={{ padding: "24px" }}>
              {error && (
                <div style={{
                  padding: "12px 16px", borderRadius: "10px", marginBottom: "20px",
                  background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.2)",
                  color: "#f87171", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "8px",
                }}>
                  <span>⚠️</span> {error}
                </div>
              )}

              <form onSubmit={handleSubmit} id="plot-form">
                {/* Plot Name + Area Row */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "24px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "#94a3b8", marginBottom: "8px" }}>
                      اسم القطعة *
                    </label>
                    <input
                      type="text" name="name" required
                      placeholder="مثال: القطعة الشمالية"
                      value={formData.name}
                      onChange={handleChange}
                      style={{
                        width: "100%", padding: "12px 14px", borderRadius: "10px",
                        background: "rgba(15, 23, 42, 0.6)",
                        border: "1px solid rgba(71, 85, 105, 0.25)",
                        color: "#e8ecf4", fontSize: "0.9rem",
                        outline: "none", transition: "border-color 0.2s ease",
                        direction: "rtl",
                      }}
                      onFocus={e => e.target.style.borderColor = "rgba(34, 197, 94, 0.4)"}
                      onBlur={e => e.target.style.borderColor = "rgba(71, 85, 105, 0.25)"}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "#94a3b8", marginBottom: "8px" }}>
                      المساحة (هكتار) *
                    </label>
                    <div style={{ position: "relative" }}>
                      <input
                        type="number" name="area" required step="0.01" min="0.01"
                        placeholder="0.00"
                        value={formData.area}
                        onChange={handleChange}
                        style={{
                          width: "100%", padding: "12px 14px", borderRadius: "10px",
                          background: geoJson ? "rgba(34, 197, 94, 0.05)" : "rgba(15, 23, 42, 0.6)",
                          border: geoJson ? "1px solid rgba(34, 197, 94, 0.2)" : "1px solid rgba(71, 85, 105, 0.25)",
                          color: "#e8ecf4", fontSize: "0.9rem",
                          outline: "none", transition: "border-color 0.2s ease",
                          direction: "ltr",
                        }}
                        onFocus={e => e.target.style.borderColor = "rgba(34, 197, 94, 0.4)"}
                        onBlur={e => e.target.style.borderColor = geoJson ? "rgba(34, 197, 94, 0.2)" : "rgba(71, 85, 105, 0.25)"}
                      />
                      {geoJson && (
                        <span style={{
                          position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)",
                          fontSize: "0.7rem", color: "#4ade80", fontWeight: 600,
                        }}>
                          ✓ من الرسم
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Soil Type */}
                <div style={{ marginBottom: "24px" }}>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "#94a3b8", marginBottom: "10px" }}>
                    نوع التربة
                  </label>
                  <div style={{
                    display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
                    gap: "8px",
                  }}>
                    {SOIL_TYPES.map(soil => (
                      <button
                        key={soil.value}
                        type="button"
                        onClick={() => setFormData(prev => ({ ...prev, soilType: soil.value }))}
                        style={{
                          padding: "10px 8px", borderRadius: "10px", cursor: "pointer",
                          background: formData.soilType === soil.value
                            ? "rgba(34, 197, 94, 0.1)"
                            : "rgba(15, 23, 42, 0.5)",
                          border: formData.soilType === soil.value
                            ? "1.5px solid rgba(34, 197, 94, 0.35)"
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
                          fontSize: "0.8rem", fontWeight: 600,
                          color: formData.soilType === soil.value ? "#4ade80" : "#e8ecf4",
                        }}>
                          {soil.label}
                        </span>
                        {soil.desc && (
                          <span style={{ fontSize: "0.65rem", color: "#64748b", lineHeight: 1.2 }}>
                            {soil.desc}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Irrigation Type */}
                <div style={{ marginBottom: "28px" }}>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "#94a3b8", marginBottom: "10px" }}>
                    نظام الري
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
                            ? "rgba(59, 130, 246, 0.1)"
                            : "rgba(15, 23, 42, 0.5)",
                          border: formData.irrigation === irr.value
                            ? "1.5px solid rgba(59, 130, 246, 0.35)"
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
                          {irr.label}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Actions Bar */}
                <div style={{
                  display: "flex", gap: "10px", alignItems: "center",
                  paddingTop: "16px", borderTop: "1px solid rgba(71, 85, 105, 0.15)",
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
                    → رجوع للخريطة
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
                    إلغاء
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
                        جاري الحفظ...
                      </span>
                    ) : (
                      "💾 حفظ القطعة"
                    )}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

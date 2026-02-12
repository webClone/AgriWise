"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";

// Dynamically import MapDrawer (Client side only)
const MapDrawer = dynamic(() => import("@/components/farm/MapDrawer"), { 
  ssr: false,
  loading: () => (
    <div className="h-[300px] w-full bg-gray-100 rounded-lg animate-pulse flex items-center justify-center text-gray-400">
      Loading Map...
    </div>
  )
});

interface AddPlotFormProps {
  farmId: string;
  farmCoordinates?: { lat: number; lng: number };
  onClose: () => void;
  onSuccess?: () => void;
  initialData?: any; // Start optional for edit
}

export default function AddPlotForm({ farmId, farmCoordinates, onClose, onSuccess, initialData }: AddPlotFormProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [geoJson, setGeoJson] = useState<any>(initialData?.geoJson || null);
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
    const payload = {
        ...formData,
        farmId,
        geoJson, 
    };

      const url = initialData ? `/api/plots/${initialData.id}` : "/api/plots";
      const method = initialData ? "PUT" : "POST";

      const res = await fetch(url, {
        method: method,
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
    } catch (err) {
      console.error(err);
      setError("حدث خطأ. حاول مرة أخرى.");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleDrawCreated = (geometry: any, area: number) => {
    setGeoJson(geometry);
    // Auto-fill area if it wasn't manually entered or if user wants to update it
    // For now, let's just update it if it's empty or override it
    if (area > 0) {
        setFormData(prev => ({ ...prev, area: area.toString() }));
    }
  };

  return (
    <div style={{
      position: "fixed",
      inset: 0,
      background: "rgba(0, 0, 0, 0.5)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1000,
      padding: "1rem"
    }}>
      <div className="card" style={{ 
        width: "100%", 
        maxWidth: "800px", // Wider modal for map
        maxHeight: "90vh",
        overflow: "auto",
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: "1.5rem"
      }}>
        {/* Left Column: Form */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h3 style={{ margin: 0, fontWeight: 600 }}>
                {initialData ? "✏️ تعديل القطعة" : "🌱 إضافة قطعة جديدة"}
            </h3>
            <button 
              onClick={onClose}
              style={{ 
                background: "none", 
                border: "none", 
                fontSize: "1.5rem", 
                cursor: "pointer",
                color: "var(--foreground-muted)"
              }}
            >
              ✕
            </button>
          </div>

          {error && (
            <div style={{ 
              padding: "0.75rem", 
              background: "rgba(239, 68, 68, 0.1)", 
              color: "#dc2626",
              borderRadius: "8px",
              marginBottom: "1rem",
              fontSize: "0.875rem"
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} id="plot-form">
            <div className="input-group" style={{ marginBottom: "1rem" }}>
              <label className="input-label">اسم القطعة *</label>
              <input
                type="text"
                name="name"
                required
                className="input"
                placeholder="مثال: القطعة الشمالية"
                value={formData.name}
                onChange={handleChange}
              />
            </div>

            <div className="input-group" style={{ marginBottom: "1rem" }}>
              <label className="input-label">المساحة (هكتار) *</label>
              <input
                type="number"
                name="area"
                required
                step="0.01"
                min="0.01"
                className="input"
                placeholder="0.00"
                value={formData.area}
                onChange={handleChange}
              />
              {geoJson && <p style={{fontSize: "0.75rem", color: "green", marginTop: "0.25rem"}}>تم تحديد المساحة من الرسم ✓</p>}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
              <div className="input-group">
                <label className="input-label">نوع التربة</label>
                <select
                  name="soilType"
                  className="input select"
                  value={formData.soilType}
                  onChange={handleChange}
                >
                  <option value="">غير محدد</option>
                  <option value="CLAY">طينية</option>
                  <option value="SANDY">رملية</option>
                  <option value="LOAM">طميية</option>
                  <option value="SILT">غرينية</option>
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">نظام الري</label>
                <select
                  name="irrigation"
                  className="input select"
                  value={formData.irrigation}
                  onChange={handleChange}
                >
                  <option value="">بعلي</option>
                  <option value="DRIP">تقطير</option>
                  <option value="SPRINKLER">رش</option>
                  <option value="FLOOD">غمر</option>
                </select>
              </div>
            </div>

            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button
                type="button"
                onClick={onClose}
                className="btn btn-secondary"
                style={{ flex: 1 }}
              >
                إلغاء
              </button>
              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary"
                style={{ flex: 1 }}
              >
                {loading ? "جاري الحفظ..." : "💾 حفظ"}
              </button>
            </div>
          </form>
        </div>

        {/* Right Column: Map */}
        <div style={{ display: "flex", flexDirection: "column" }}>
            <h4 style={{ margin: "0 0 1rem 0", fontSize: "0.9rem", color: "var(--foreground-muted)" }}>
                📍 ارسم حدود القطعة على الخريطة
            </h4>
            {farmCoordinates ? (
                <MapDrawer 
                    center={[farmCoordinates.lat, farmCoordinates.lng]} 
                    onDrawCreated={handleDrawCreated}
                />
            ) : (
                <div style={{ 
                    height: "300px", 
                    background: "#f3f4f6", 
                    borderRadius: "0.5rem", 
                    display: "flex", 
                    alignItems: "center", 
                    justifyContent: "center",
                    color: "#9ca3af",
                    textAlign: "center",
                    padding: "1rem"
                }}>
                    لا يمكن عرض الخريطة لأن إحداثيات المزرعة غير متوفرة
                </div>
            )}
            <p style={{ fontSize: "0.75rem", color: "var(--foreground-muted)", marginTop: "0.5rem" }}>
                استخدم أدوات الرسم (المضلع) في الزاوية لتحديد شكل القطعة. سيتم حساب المساحة تلقائياً.
            </p>
        </div>
      </div>
    </div>
  );
}


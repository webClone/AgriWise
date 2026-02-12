"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import wilayasData from "@/data/algeria/wilayas.json";

interface EditFarmModalProps {
  farm: {
    id: string;
    name: string;
    totalArea: number;
    wilaya: string;
    commune?: string | null;
    soilType?: string | null;
    waterSource?: string | null;
    irrigationType?: string | null;
  };
  onClose: () => void;
  onSuccess?: () => void;
}

export default function EditFarmModal({ farm, onClose, onSuccess }: EditFarmModalProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [formData, setFormData] = useState({
    name: farm.name,
    totalArea: farm.totalArea.toString(),
    wilaya: farm.wilaya,
    commune: farm.commune || "",
    soilType: farm.soilType || "",
    waterSource: farm.waterSource || "",
    irrigationType: farm.irrigationType || "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`/api/farms/${farm.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      const data = await res.json();

      if (data.success) {
        router.refresh();
        onSuccess?.();
        onClose();
      } else {
        setError(data.error || "حدث خطأ أثناء تحديث المزرعة");
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
        maxWidth: "500px", 
        maxHeight: "90vh",
        overflowY: "auto",
        position: "relative"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, fontWeight: 600 }}>📝 تعديل المزرعة</h3>
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

        <form onSubmit={handleSubmit}>
          <div className="input-group" style={{ marginBottom: "1rem" }}>
            <label className="input-label">اسم المزرعة *</label>
            <input
              type="text"
              name="name"
              required
              className="input"
              value={formData.name}
              onChange={handleChange}
            />
          </div>

          <div className="input-group" style={{ marginBottom: "1rem" }}>
            <label className="input-label">المساحة الكلية (هكتار) *</label>
            <input
              type="number"
              name="totalArea"
              required
              step="0.01"
              min="0.01"
              className="input"
              value={formData.totalArea}
              onChange={handleChange}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
            <div className="input-group">
              <label className="input-label">الولاية *</label>
              <select
                name="wilaya"
                required
                className="input select"
                value={formData.wilaya}
                onChange={handleChange}
              >
                 <option value="">اختر الولاية</option>
                {wilayasData.wilayas.map((w) => (
                    <option key={w.code} value={w.nameAr}>{w.code} - {w.nameAr}</option>
                ))}
              </select>
            </div>
            <div className="input-group">
              <label className="input-label">البلدية</label>
              <input
                type="text"
                name="commune"
                className="input"
                value={formData.commune}
                onChange={handleChange}
                placeholder="اختياري"
              />
            </div>
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
                  <option value="PEAT">ثرفية (Peat)</option>
                  <option value="CHALKY">طباشيرية</option>
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">مصدر المياه</label>
                <select
                  name="waterSource"
                  className="input select"
                  value={formData.waterSource}
                  onChange={handleChange}
                >
                   <option value="">غير محدد</option>
                   <option value="WELL">بئر</option>
                   <option value="DAM">سد</option>
                   <option value="RIVER">نهر</option>
                   <option value="DESALINATION">تحلية</option>
                   <option value="RAINFED">مياه أمطار</option>
                </select>
              </div>
          </div>

          <div className="input-group" style={{ marginBottom: "1.5rem" }}>
            <label className="input-label">نظام الري</label>
            <select
                name="irrigationType"
                className="input select"
                value={formData.irrigationType}
                onChange={handleChange}
            >
                <option value="">غير محدد</option>
                <option value="DRIP">تقطير</option>
                <option value="SPRINKLER">رش</option>
                <option value="FLOOD">غمر</option>
                <option value="PIVOT">محوري</option>
                <option value="RAINFED">بعلي (مطري)</option>
            </select>
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
              {loading ? "جاري الحفظ..." : "💾 حفظ التغييرات"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

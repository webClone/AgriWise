"use client";

import { useActionState, useEffect } from "react";
import { createPortal } from "react-dom";
import { addEquipment, updateEquipment } from "@/actions/equipment";

const EQUIPMENT_TYPES = [
  { value: "TRACTOR", label: "جرار" },
  { value: "HARVESTER", label: "حصادة" },
  { value: "PUMP", label: "مضخة" },
  { value: "IRRIGATION_SYSTEM", label: "نظام ري" },
  { value: "PLOW", label: "محراث" },
  { value: "SPRAYER", label: "مرشة مبيدات" },
  { value: "TRUCK", label: "شاحنة" },
  { value: "STORAGE", label: "مخزن" },
  { value: "OTHER", label: "أخرى" },
];

const CONDITIONS = [
  { value: "new", label: "جديد" },
  { value: "good", label: "جيد" },
  { value: "fair", label: "متوسط" },
  { value: "poor", label: "سيء" },
  { value: "broken", label: "معطل" },
];

interface AddEquipmentFormProps {
  farmId: string;
  initialData?: any;
  onClose: () => void;
}

export default function AddEquipmentForm({ farmId, initialData, onClose }: AddEquipmentFormProps) {
  const initialState = { success: false, message: "" };
  
  // Use bound actions for add/update
  const action = initialData 
    ? updateEquipment.bind(null, initialData.id, farmId)
    : addEquipment.bind(null, farmId);

  const [state, formAction, isPending] = useActionState(action, initialState);

  // Close modal on success
  useEffect(() => {
    if (state.success) {
      onClose();
    }
  }, [state.success, onClose]);

  // Use portal to break out of any parent transforms (animations/cards)
  if (typeof document === 'undefined') return null;

  return createPortal(
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: "rgba(0, 0, 0, 0.75)",
      display: "flex", // Revert to flex for standard centering with portal
      alignItems: "center",
      justifyContent: "center",
      zIndex: 99999,
      padding: "1rem",
      backdropFilter: "blur(4px)"
    }}>
      <div className="card" style={{ 
        width: "100%", 
        maxWidth: "450px", 
        maxHeight: "90vh", 
        overflowY: "auto",
        position: "relative",
        boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
        border: "1px solid var(--background-tertiary)"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
          <h3 style={{ margin: 0, fontWeight: "bold", fontSize: "1.125rem" }}>
            {initialData ? "تعديل المعدات" : "إضافة معدات جديدة"}
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
            &times;
          </button>
        </div>

        <form action={formAction} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {state.message && !state.success && (
            <div style={{ 
              padding: "0.75rem", 
              background: "rgba(220, 38, 38, 0.1)", 
              color: "#ef4444", 
              borderRadius: "8px", 
              fontSize: "0.875rem" 
            }}>
              {state.message}
            </div>
          )}

          <div className="input-group">
            <label className="input-label">الاسم</label>
            <input 
              name="name"
              defaultValue={initialData?.name}
              required 
              className="input"
              placeholder="مثال: جرار ماسي فيرغسون"
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="input-group">
              <label className="input-label">النوع</label>
              <select 
                name="type" 
                defaultValue={initialData?.type}
                className="input select"
              >
                {EQUIPMENT_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">العدد</label>
              <input 
                type="number" 
                name="quantity" 
                defaultValue={initialData?.quantity || 1}
                min="1"
                className="input"
              />
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">الحالة</label>
            <select 
              name="condition" 
              defaultValue={initialData?.condition || "good"}
              className="input select"
            >
              {CONDITIONS.map(c => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
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
              disabled={isPending}
              className="btn btn-primary"
              style={{ flex: 1 }}
            >
              {isPending ? "جاري الحفظ..." : "حفظ"}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}

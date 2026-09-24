"use client";

import { useState } from "react";
import { deleteEquipment } from "@/actions/equipment";
import AddEquipmentForm from "./AddEquipmentForm";
import { useLanguage } from "@/lib/i18n/LanguageContext";
import { Wrench, Plus, Trash2, Pencil } from "lucide-react";

type Equipment = {
  id: string;
  name: string;
  type: string;
  condition: string | null;
  quantity: number;
};

const EQUIPMENT_TYPE_LABELS: Record<string, { ar: string; en: string; fr: string; icon: string }> = {
  TRACTOR: { ar: "جرار", en: "Tractor", fr: "Tracteur", icon: "🚜" },
  HARVESTER: { ar: "حصادة", en: "Harvester", fr: "Moissonneuse", icon: "🌾" },
  PUMP: { ar: "مضخة", en: "Water Pump", fr: "Pompe", icon: "💧" },
  IRRIGATION_SYSTEM: { ar: "نظام ري", en: "Irrigation System", fr: "Système d'irrigation", icon: "🚿" },
  PLOW: { ar: "محراث", en: "Plow", fr: "Charrue", icon: "⚒️" },
  SPRAYER: { ar: "مرشة", en: "Sprayer", fr: "Pulvérisateur", icon: "🧴" },
  TRUCK: { ar: "شاحنة", en: "Truck", fr: "Camion", icon: "🚚" },
  STORAGE: { ar: "مخزن", en: "Storage / Silo", fr: "Stockage / Silo", icon: "🏭" },
  OTHER: { ar: "أخرى", en: "Other", fr: "Autre", icon: "📦" },
};

const CONDITION_LABELS: Record<string, { ar: string; en: string; fr: string; color: string; bg: string }> = {
  new: { ar: "جديد", en: "New", fr: "Neuf", color: "#4ade80", bg: "rgba(34, 197, 94, 0.12)" },
  good: { ar: "جيد", en: "Good", fr: "Bon état", color: "#60a5fa", bg: "rgba(59, 130, 246, 0.12)" },
  fair: { ar: "متوسط", en: "Fair", fr: "Passable", color: "#facc15", bg: "rgba(234, 179, 8, 0.12)" },
  poor: { ar: "سيء", en: "Poor", fr: "Mauvais", color: "#fb923c", bg: "rgba(251, 146, 60, 0.12)" },
  broken: { ar: "معطل", en: "Broken", fr: "En panne", color: "#f87171", bg: "rgba(239, 68, 68, 0.12)" },
};

export default function EquipmentList({ 
  equipment, 
  farmId 
}: { 
  equipment: Equipment[]; 
  farmId: string 
}) {
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<Equipment | null>(null);
  const { locale, isRtl } = useLanguage();

  const title = locale === "ar" ? "المعدات والآلات" : locale === "fr" ? "Matériel & Machinisme" : "Equipment & Machinery";
  const addBtn = locale === "ar" ? "+ إضافة معدات" : locale === "fr" ? "+ Ajouter du matériel" : "+ Add Equipment";
  const emptyTitle = locale === "ar" ? "لا توجد معدات مسجلة لهذه المزرعة" : locale === "fr" ? "Aucun matériel enregistré" : "No machinery registered for this farm";
  const emptyBtn = locale === "ar" ? "إضافة أول معدات" : locale === "fr" ? "Ajouter le premier équipement" : "Register First Equipment";
  const confirmDelete = locale === "ar" ? "هل أنت متأكد من حذف هذه المعدات؟" : locale === "fr" ? "Voulez-vous vraiment supprimer cet équipement ?" : "Are you sure you want to remove this equipment?";

  const colName = locale === "ar" ? "الاسم" : locale === "fr" ? "Nom" : "Name";
  const colType = locale === "ar" ? "النوع" : locale === "fr" ? "Type" : "Type";
  const colQty = locale === "ar" ? "العدد" : locale === "fr" ? "Qté" : "Qty";
  const colStatus = locale === "ar" ? "الحالة" : locale === "fr" ? "État" : "Condition";
  const colActions = locale === "ar" ? "إجراءات" : locale === "fr" ? "Actions" : "Actions";

  const handleDelete = async (id: string) => {
    if (confirm(confirmDelete)) {
      await deleteEquipment(id, farmId);
    }
  };

  return (
    <div 
      style={{
        padding: "24px",
        background: "rgba(15, 23, 42, 0.5)",
        backdropFilter: "blur(16px)",
        borderRadius: "18px",
        border: "1px solid rgba(71, 85, 105, 0.15)",
        boxShadow: "0 10px 40px rgba(0,0,0,0.25)",
      }} 
      suppressHydrationWarning={true}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }} suppressHydrationWarning={true}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{
            width: "32px", height: "32px", borderRadius: "8px",
            background: "rgba(168, 85, 247, 0.1)",
            border: "1px solid rgba(168, 85, 247, 0.2)",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "#c084fc",
          }}>
            <Wrench size={16} />
          </div>
          <h3 style={{ margin: 0, fontWeight: 700, fontSize: "1.1rem", color: "#f8fafc" }}>{title}</h3>
          {equipment.length > 0 && (
            <span style={{
              fontSize: "0.75rem", fontWeight: 700,
              background: "rgba(168, 85, 247, 0.12)", color: "#c084fc",
              padding: "2px 10px", borderRadius: "9999px",
              border: "1px solid rgba(168, 85, 247, 0.25)",
            }}>
              {equipment.length}
            </span>
          )}
        </div>

        <button 
          onClick={() => setIsAddModalOpen(true)}
          style={{
            padding: "8px 16px", borderRadius: "10px",
            fontSize: "0.82rem", fontWeight: 600, cursor: "pointer",
            background: "rgba(168, 85, 247, 0.12)",
            border: "1px solid rgba(168, 85, 247, 0.3)",
            color: "#c084fc",
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            transition: "all 0.2s ease",
          }}
          onMouseOver={e => {
            e.currentTarget.style.background = "rgba(168, 85, 247, 0.22)";
            e.currentTarget.style.transform = "translateY(-1px)";
          }}
          onMouseOut={e => {
            e.currentTarget.style.background = "rgba(168, 85, 247, 0.12)";
            e.currentTarget.style.transform = "translateY(0)";
          }}
        >
          <Plus size={14} />
          <span>{addBtn}</span>
        </button>
      </div>

      {equipment.length === 0 ? (
        <div style={{ 
          textAlign: "center", 
          padding: "3.5rem 2rem", 
          background: "linear-gradient(135deg, rgba(15, 23, 42, 0.4), rgba(15, 23, 42, 0.15))", 
          borderRadius: "16px", 
          border: "1px dashed rgba(71, 85, 105, 0.25)",
        }} suppressHydrationWarning={true}>
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }} suppressHydrationWarning={true}>🚜</div>
          <p style={{ fontWeight: 700, fontSize: "1rem", color: "#f1f5f9", margin: "0 0 1.25rem 0" }}>{emptyTitle}</p>
          <button 
            onClick={() => setIsAddModalOpen(true)}
            style={{
              padding: "10px 22px", borderRadius: "10px",
              fontWeight: 700, fontSize: "0.85rem", cursor: "pointer",
              background: "linear-gradient(135deg, #a855f7, #7e22ce)",
              border: "none", color: "#fff",
              boxShadow: "0 4px 20px rgba(168, 85, 247, 0.3)",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <Plus size={14} />
            <span>{emptyBtn}</span>
          </button>
        </div>
      ) : (
        <div style={{ overflowX: "auto" }} suppressHydrationWarning={true}>
          <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: "0 8px", textAlign: isRtl ? "right" : "left" }}>
            <thead>
              <tr style={{ color: "#94a3b8", fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                <th style={{ padding: "8px 16px" }}>{colName}</th>
                <th style={{ padding: "8px 16px" }}>{colType}</th>
                <th style={{ padding: "8px 16px", textAlign: "center" }}>{colQty}</th>
                <th style={{ padding: "8px 16px" }}>{colStatus}</th>
                <th style={{ padding: "8px 16px", textAlign: isRtl ? "left" : "right" }}>{colActions}</th>
              </tr>
            </thead>
            <tbody>
              {equipment.map((item) => {
                const typeInfo = EQUIPMENT_TYPE_LABELS[item.type] || EQUIPMENT_TYPE_LABELS.OTHER;
                const typeLabel = typeInfo[locale] || typeInfo.en;
                const condInfo = CONDITION_LABELS[item.condition || "good"] || CONDITION_LABELS.good;
                const condLabel = condInfo[locale] || condInfo.en;

                return (
                  <tr 
                    key={item.id} 
                    style={{ 
                      background: "rgba(15, 23, 42, 0.6)", 
                      borderRadius: "10px",
                      transition: "background 0.2s ease",
                    }}
                    onMouseOver={e => e.currentTarget.style.background = "rgba(15, 23, 42, 0.85)"}
                    onMouseOut={e => e.currentTarget.style.background = "rgba(15, 23, 42, 0.6)"}
                  >
                    <td style={{ padding: "14px 16px", fontWeight: 600, color: "#f8fafc", borderRadius: isRtl ? "0 10px 10px 0" : "10px 0 0 10px" }}>
                      {item.name}
                    </td>
                    <td style={{ padding: "14px 16px", color: "#94a3b8", fontSize: "0.85rem" }}>
                      <span style={{ marginRight: "6px" }}>{typeInfo.icon}</span>
                      <span>{typeLabel}</span>
                    </td>
                    <td style={{ padding: "14px 16px", textAlign: "center", fontWeight: 700, color: "#4ade80", fontSize: "0.95rem" }}>
                      {item.quantity}
                    </td>
                    <td style={{ padding: "14px 16px" }}>
                      <span style={{
                        padding: "3px 10px",
                        borderRadius: "99px",
                        fontSize: "0.72rem",
                        fontWeight: 600,
                        background: condInfo.bg,
                        color: condInfo.color,
                        border: `1px solid ${condInfo.color}25`,
                        display: "inline-block",
                      }}>
                        {condLabel}
                      </span>
                    </td>
                    <td style={{ padding: "14px 16px", textAlign: isRtl ? "left" : "right", borderRadius: isRtl ? "10px 0 0 10px" : "0 10px 10px 0" }}>
                      <div style={{ display: "inline-flex", gap: "6px" }} suppressHydrationWarning={true}>
                        <button 
                          onClick={() => setEditingItem(item)}
                          title="Edit"
                          style={{
                            color: "#4ade80",
                            background: "rgba(34, 197, 94, 0.1)",
                            border: "1px solid rgba(34, 197, 94, 0.2)",
                            width: "32px", height: "32px", borderRadius: "8px",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            cursor: "pointer",
                            transition: "all 0.15s ease",
                          }}
                          onMouseOver={e => e.currentTarget.style.background = "rgba(34, 197, 94, 0.25)"}
                          onMouseOut={e => e.currentTarget.style.background = "rgba(34, 197, 94, 0.1)"}
                        >
                          <Pencil size={13} />
                        </button>
                        <button 
                          onClick={() => handleDelete(item.id)}
                          title="Delete"
                          style={{
                            color: "#f87171",
                            background: "rgba(239, 68, 68, 0.1)",
                            border: "1px solid rgba(239, 68, 68, 0.2)",
                            width: "32px", height: "32px", borderRadius: "8px",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            cursor: "pointer",
                            transition: "all 0.15s ease",
                          }}
                          onMouseOver={e => e.currentTarget.style.background = "rgba(239, 68, 68, 0.25)"}
                          onMouseOut={e => e.currentTarget.style.background = "rgba(239, 68, 68, 0.1)"}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {(isAddModalOpen || editingItem) && (
        <AddEquipmentForm 
          farmId={farmId}
          initialData={editingItem}
          onClose={() => {
            setIsAddModalOpen(false);
            setEditingItem(null);
          }}
        />
      )}
    </div>
  );
}

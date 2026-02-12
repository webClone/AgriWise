"use client";

import { useState } from "react";
import { deleteEquipment } from "@/actions/equipment";
import AddEquipmentForm from "./AddEquipmentForm";

type Equipment = {
  id: string;
  name: string;
  type: string;
  condition: string | null;
  quantity: number;
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

  const handleDelete = async (id: string) => {
    if (confirm("هل أنت متأكد من حذف هذه المعدات؟")) {
      await deleteEquipment(id, farmId);
    }
  };

  return (
    <div className="card mt-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xl font-bold">المعدات والآلات</h3>
        <button 
          onClick={() => setIsAddModalOpen(true)}
          className="btn btn-primary"
          style={{ fontSize: "0.875rem", padding: "0.5rem 1rem" }}
        >
          + إضافة معدات
        </button>
      </div>

      {equipment.length === 0 ? (
        <div style={{ 
          textAlign: "center", 
          padding: "3rem", 
          background: "var(--background-secondary)", 
          borderRadius: "12px", 
          border: "1px dashed var(--background-tertiary)",
          color: "var(--foreground-muted)"
        }}>
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>🚜</div>
          <p style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>لا توجد معدات مسجلة لهذه المزرعة</p>
          <button 
            onClick={() => setIsAddModalOpen(true)}
            className="btn btn-outline"
            style={{ fontSize: "0.9rem" }}
          >
            إضافة أول معدات
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-right" style={{ borderCollapse: "separate", borderSpacing: "0 0.5rem" }}>
            <thead>
              <tr style={{ color: "var(--foreground-muted)", fontSize: "0.875rem" }}>
                <th className="pb-2 px-4">الاسم</th>
                <th className="pb-2 px-4">النوع</th>
                <th className="pb-2 px-4">العدد</th>
                <th className="pb-2 px-4">الحالة</th>
                <th className="pb-2 px-4 text-left">إجراءات</th>
              </tr>
            </thead>
            <tbody>
              {equipment.map((item) => (
                <tr key={item.id} style={{ background: "var(--background-secondary)", borderRadius: "8px" }}>
                  <td className="py-3 px-4 font-medium" style={{ borderRadius: "0 8px 8px 0" }}>{item.name}</td>
                  <td className="py-3 px-4 text-gray-400">
                    {item.type === 'TRACTOR' ? '🚜 جرار' : 
                     item.type === 'HARVESTER' ? '🌾 حصادة' :
                     item.type === 'PUMP' ? '💧 مضخة' : 
                     item.type === 'IRRIGATION_SYSTEM' ? '🚿 نظام ري' :
                     item.type === 'PLOW' ? '⚒️ محراث' : 
                     item.type === 'SPRAYER' ? '🧴 مرشة' : 
                     item.type === 'TRUCK' ? '🚚 شاحنة' : 
                     item.type === 'STORAGE' ? '🏭 مخزن' : '📦 أخرى'}
                  </td>
                  <td className="py-3 px-4 text-center font-bold" style={{ color: "var(--color-primary-500)" }}>{item.quantity}</td>
                  <td className="py-3 px-4">
                    <span style={{
                      padding: "0.25rem 0.75rem",
                      borderRadius: "99px",
                      fontSize: "0.75rem",
                      background: 
                        item.condition === 'new' ? 'rgba(34, 197, 94, 0.1)' :
                        item.condition === 'good' ? 'rgba(59, 130, 246, 0.1)' :
                        item.condition === 'fair' ? 'rgba(234, 179, 8, 0.1)' :
                        'rgba(239, 68, 68, 0.1)',
                      color:
                        item.condition === 'new' ? '#22c55e' :
                        item.condition === 'good' ? '#3b82f6' :
                        item.condition === 'fair' ? '#eab308' :
                        '#ef4444',
                      display: "inline-block"
                    }}>
                      {item.condition === 'new' ? '✨ جديد' : 
                       item.condition === 'good' ? '👍 جيد' : 
                       item.condition === 'fair' ? '😐 متوسط' : 
                       item.condition === 'poor' ? '👎 سيء' : 
                       item.condition === 'broken' ? '🛠️ معطل' : '-'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-left" style={{ borderRadius: "8px 0 0 8px" }}>
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                      <button 
                        onClick={() => setEditingItem(item)}
                        className="btn-icon"
                        title="تعديل"
                        style={{ color: "var(--color-primary-500)", background: "rgba(34, 197, 94, 0.1)", width: "32px", height: "32px", padding: 0, display: "flex", alignItems: "center", justifyContent: "center" }}
                      >
                        ✏️
                      </button>
                      <button 
                        onClick={() => handleDelete(item.id)}
                        className="btn-icon"
                        title="حذف"
                        style={{ color: "#ef4444", background: "rgba(239, 68, 68, 0.1)", width: "32px", height: "32px", padding: 0, display: "flex", alignItems: "center", justifyContent: "center" }}
                      >
                        🗑️
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
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

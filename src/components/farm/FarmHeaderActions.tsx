"use client";

import { useState } from "react";
import { Pencil } from "lucide-react";
import EditFarmModal from "./EditFarmModal";
import { useLanguage } from "@/lib/i18n/LanguageContext";

interface FarmHeaderActionsProps {
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
}

export default function FarmHeaderActions({ farm }: FarmHeaderActionsProps) {
  const [showEditModal, setShowEditModal] = useState(false);
  const { locale } = useLanguage();

  const editLabel = locale === "ar" ? "تعديل المزرعة" : locale === "fr" ? "Modifier l'exploitation" : "Edit Farm";

  return (
    <>
      <button 
        type="button"
        onClick={() => setShowEditModal(true)}
        className="hover-lift transition-smooth"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "8px",
          padding: "8px 16px",
          borderRadius: "10px",
          background: "rgba(15, 23, 42, 0.75)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(71, 85, 105, 0.25)",
          color: "#f1f5f9",
          fontSize: "12px",
          fontWeight: 600,
          cursor: "pointer",
          boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
        }}
        onMouseOver={e => {
          e.currentTarget.style.borderColor = "rgba(34, 197, 94, 0.4)";
          e.currentTarget.style.background = "rgba(15, 23, 42, 0.9)";
        }}
        onMouseOut={e => {
          e.currentTarget.style.borderColor = "rgba(71, 85, 105, 0.25)";
          e.currentTarget.style.background = "rgba(15, 23, 42, 0.75)";
        }}
      >
        <Pencil size={13} style={{ color: "#4ade80" }} />
        <span>{editLabel}</span>
      </button>

      {showEditModal && (
        <EditFarmModal 
          farm={farm} 
          onClose={() => setShowEditModal(false)} 
        />
      )}
    </>
  );
}

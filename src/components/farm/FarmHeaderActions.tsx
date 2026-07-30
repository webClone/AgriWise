"use client";

import { useState } from "react";
import EditFarmModal from "./EditFarmModal";

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

  return (
    <>
      <button 
        className="btn btn-primary" 
        style={{ padding: "0.5rem 1rem", fontSize: "0.875rem" }}
        onClick={() => setShowEditModal(true)}
      >
        ✏️ تعديل
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

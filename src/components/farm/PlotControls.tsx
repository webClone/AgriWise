"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AddPlotForm from "@/components/farm/AddPlotForm";

interface PlotControlsProps {
  plot: any;
  farmId: string;
}

export default function PlotControls({ plot, farmId }: PlotControlsProps) {
  const router = useRouter();
  const [showEdit, setShowEdit] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    if (!window.confirm("Are you sure you want to delete this plot? This action cannot be undone.")) {
      return;
    }

    setIsDeleting(true);
    try {
      const res = await fetch(`/api/plots/${plot.id}`, {
        method: "DELETE",
      });

      if (res.ok) {
        router.push(`/farm/${farmId}`);
        router.refresh();
      } else {
        alert("An error occurred while deleting");
      }
    } catch (err) {
      console.error(err);
      alert("An error occurred while deleting");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button
          onClick={() => setShowEdit(true)}
          className="btn btn-secondary"
          style={{ padding: "0.5rem 1rem", fontSize: "0.875rem" }}
        >
          ✏️ Edit
        </button>
        <button
          onClick={handleDelete}
          disabled={isDeleting}
          className="btn"
          style={{ 
            padding: "0.5rem 1rem", 
            fontSize: "0.875rem", 
            background: "#fee2e2", 
            color: "#dc2626",
            border: "1px solid #fecaca" 
          }}
        >
          {isDeleting ? "Deleting..." : "🗑️ Delete"}
        </button>
      </div>

      {showEdit && (
        <AddPlotForm
          farmId={farmId}
          onClose={() => setShowEdit(false)}
          onSuccess={() => {
            setShowEdit(false);
            router.refresh();
          }}
          initialData={plot}
          // Assuming coordinates are not strictly needed for edit if we passed geoJson
          // But if we want to redraw, we need center. 
          // Ideally we pass farm coordinates. For now, let's leave undefined or pass null if map is optional
        />
      )}
    </>
  );
}

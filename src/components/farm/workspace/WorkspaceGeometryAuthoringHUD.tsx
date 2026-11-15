"use client";

import { useState } from "react";
import { PenTool, Undo2, Trash2, X, Check, Plane, FileText, AlertCircle, ShieldAlert } from "lucide-react";
import {
  createGeometryRegistration,
  formatDraftGeometry,
  type GeometryDraft,
  type RegisterGeometryPayload,
} from "@/lib/agribrain/geometry-authoring";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";

interface AuthoringHUDProps {
  plotId: string;
  drawingKind: "DRONE_MISSION" | "FIELD_OBSERVATION" | null;
  draftCoordinates: [number, number][];
  onAddVertex: (coord: [number, number]) => void;
  onUndoVertex: () => void;
  onClearVertices: () => void;
  onCancel: () => void;
  onComplete: (entity: WorkspaceFeatureEnvelope) => void;
}

export default function WorkspaceGeometryAuthoringHUD({
  plotId,
  drawingKind,
  draftCoordinates,
  onUndoVertex,
  onClearVertices,
  onCancel,
  onComplete,
}: AuthoringHUDProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [scoutTitle, setScoutTitle] = useState("");
  const [scoutSeverity, setScoutSeverity] = useState("warning");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!drawingKind) return null;

  const isLine = drawingKind === "DRONE_MISSION";
  const minPoints = isLine ? 2 : 3;
  const canFinish = draftCoordinates.length >= minPoints;

  const handleFinishClick = () => {
    if (!canFinish) return;
    setLabel(isLine ? `Flight Corridor Plan ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : `Scouting Boundary ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
    setScoutTitle(isLine ? "" : "Field Scouting Observation Record");
    setErrorMessage(null);
    setModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!label.trim()) {
      setErrorMessage("Please enter a name or label for this geometry.");
      return;
    }

    const draft: GeometryDraft = {
      entityKind: drawingKind,
      type: isLine ? "LineString" : "Polygon",
      coordinates: draftCoordinates,
    };
    const geometry = formatDraftGeometry(draft);
    if (!geometry) {
      setErrorMessage(`Insufficient coordinates for a valid ${draft.type}.`);
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const payload: RegisterGeometryPayload = {
        entity_kind: drawingKind,
        source_kind: isLine ? "OWNER_PLAN" : "CROP_OBSERVATION",
        label: label.trim(),
        notes: notes.trim() || null,
        geometry,
        ...(isLine
          ? { source_id: null }
          : {
              new_observation: {
                title: scoutTitle.trim() || label.trim(),
                severity: scoutSeverity,
                type: "pest",
                description: notes.trim() || null,
              },
            }),
      };

      const res = await createGeometryRegistration(plotId, payload);
      setIsSubmitting(false);
      setModalOpen(false);
      if (res.entity) {
        onComplete(res.entity);
      }
    } catch (err: any) {
      setIsSubmitting(false);
      setErrorMessage(err.message || "Failed to persist geometry registration.");
    }
  };

  return (
    <>
      {/* Top Floating Authoring HUD */}
      <div
        className="pw-authoring-hud"
        data-testid="p06-authoring-hud"
        style={{
          position: "absolute",
          top: "16px",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 40,
          background: "rgba(15, 23, 42, 0.92)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(234, 179, 8, 0.5)",
          borderRadius: "12px",
          padding: "10px 16px",
          boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.6)",
          display: "flex",
          alignItems: "center",
          gap: "14px",
          color: "#f8fafc",
          fontSize: "13px",
          pointerEvents: "auto",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {isLine ? (
            <Plane size={16} className="text-orange-400" />
          ) : (
            <FileText size={16} className="text-rose-400" />
          )}
          <span style={{ fontWeight: 600, color: isLine ? "#fb923c" : "#f43f5e" }}>
            {isLine ? "Drawing Drone Corridor (LineString)" : "Mapping Scouting Area (Polygon)"}
          </span>
        </div>

        <div style={{ height: "18px", width: "1px", background: "rgba(255,255,255,0.2)" }} />

        <div style={{ color: "#94a3b8", fontSize: "12px" }}>
          <strong style={{ color: "#f8fafc" }}>{draftCoordinates.length}</strong> points placed
          {canFinish ? (
            <span style={{ color: "#4ade80", marginLeft: "6px" }}>(Ready to save)</span>
          ) : (
            <span style={{ color: "#facc15", marginLeft: "6px" }}>
              (Need {minPoints - draftCoordinates.length} more)
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <button
            type="button"
            onClick={onUndoVertex}
            disabled={draftCoordinates.length === 0}
            title="Undo last point"
            style={{
              background: "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.15)",
              color: draftCoordinates.length === 0 ? "#64748b" : "#e2e8f0",
              borderRadius: "6px",
              padding: "6px 10px",
              cursor: draftCoordinates.length === 0 ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: "5px",
              fontSize: "12px",
            }}
          >
            <Undo2 size={13} /> Undo
          </button>

          <button
            type="button"
            onClick={onClearVertices}
            disabled={draftCoordinates.length === 0}
            title="Clear all points"
            style={{
              background: "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.15)",
              color: draftCoordinates.length === 0 ? "#64748b" : "#e2e8f0",
              borderRadius: "6px",
              padding: "6px 10px",
              cursor: draftCoordinates.length === 0 ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: "5px",
              fontSize: "12px",
            }}
          >
            <Trash2 size={13} /> Clear
          </button>

          <button
            type="button"
            onClick={handleFinishClick}
            disabled={!canFinish}
            data-testid="p06-finish-drawing-btn"
            style={{
              background: canFinish ? "#16a34a" : "rgba(22, 163, 74, 0.3)",
              border: "1px solid rgba(74, 222, 128, 0.4)",
              color: canFinish ? "#ffffff" : "#86efac",
              fontWeight: 600,
              borderRadius: "6px",
              padding: "6px 12px",
              cursor: canFinish ? "pointer" : "not-allowed",
              display: "flex",
              alignItems: "center",
              gap: "5px",
              fontSize: "12px",
            }}
          >
            <Check size={14} /> Finish & Save
          </button>

          <button
            type="button"
            onClick={onCancel}
            title="Cancel drawing"
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              padding: "6px",
              borderRadius: "6px",
            }}
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Save Registration Dialog Modal */}
      {modalOpen && (
        <div
          className="pw-modal-backdrop"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.7)",
            backdropFilter: "blur(4px)",
            zIndex: 60,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            className="pw-modal-content"
            data-testid="p06-authoring-modal"
            style={{
              background: "#0f172a",
              border: "1px solid rgba(234, 179, 8, 0.4)",
              borderRadius: "14px",
              maxWidth: "480px",
              width: "100%",
              padding: "24px",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.8)",
              color: "#f8fafc",
            }}
          >
            <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <PenTool size={18} className="text-amber-400" />
                <h3 style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>
                  Save Owner-Declared {isLine ? "Flight Corridor" : "Scouting Polygon"}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer" }}
              >
                <X size={18} />
              </button>
            </header>

            <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#cbd5e1", marginBottom: "5px", fontWeight: 600 }}>
                  Feature Name / Label *
                </label>
                <input
                  type="text"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="e.g. North Orchard Survey Flight Plan"
                  required
                  style={{
                    width: "100%",
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.15)",
                    borderRadius: "8px",
                    padding: "9px 12px",
                    color: "#f8fafc",
                    fontSize: "13px",
                    outline: "none",
                  }}
                />
              </div>

              {!isLine && (
                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "#cbd5e1", marginBottom: "5px", fontWeight: 600 }}>
                    Linked Scouting Observation Record *
                  </label>
                  <input
                    type="text"
                    value={scoutTitle}
                    onChange={(e) => setScoutTitle(e.target.value)}
                    placeholder="e.g. Surveyed Aphid Scouting Record"
                    required
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      borderRadius: "8px",
                      padding: "9px 12px",
                      color: "#f8fafc",
                      fontSize: "13px",
                      outline: "none",
                    }}
                  />
                  <div style={{ display: "flex", gap: "10px", marginTop: "8px" }}>
                    <select
                      value={scoutSeverity}
                      onChange={(e) => setScoutSeverity(e.target.value)}
                      style={{
                        background: "rgba(255,255,255,0.06)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        borderRadius: "6px",
                        padding: "6px 10px",
                        color: "#f8fafc",
                        fontSize: "12px",
                      }}
                    >
                      <option value="info">Severity: Info</option>
                      <option value="warning">Severity: Warning</option>
                      <option value="critical">Severity: Critical</option>
                    </select>
                  </div>
                </div>
              )}

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#cbd5e1", marginBottom: "5px", fontWeight: 600 }}>
                  Field Notes (Optional)
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  placeholder="Additional context or agronomic observations..."
                  style={{
                    width: "100%",
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.15)",
                    borderRadius: "8px",
                    padding: "8px 12px",
                    color: "#f8fafc",
                    fontSize: "13px",
                    outline: "none",
                    resize: "none",
                  }}
                />
              </div>

              {/* Epistemic Boundary Notice */}
              <div
                style={{
                  background: "rgba(234, 179, 8, 0.12)",
                  border: "1px solid rgba(234, 179, 8, 0.3)",
                  borderRadius: "8px",
                  padding: "10px 12px",
                  display: "flex",
                  gap: "10px",
                  alignItems: "flex-start",
                  fontSize: "11px",
                  color: "#fef08a",
                }}
              >
                <ShieldAlert size={16} className="text-amber-400 shrink-0" style={{ marginTop: "2px" }} />
                <div>
                  <strong>Owner-Declared Provisional Record</strong>
                  <p style={{ margin: "2px 0 0", color: "#fde047" }}>
                    This spatial feature will be persisted as <code>{isLine ? "PLANNED" : "ESTIMATED"}</code> with revision 1 and an append-only audit trail. It does not certify hardware measurements or scientific publication authority.
                  </p>
                </div>
              </div>

              {errorMessage && (
                <div style={{ color: "#f87171", fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                  <AlertCircle size={14} /> {errorMessage}
                </div>
              )}

              <footer style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  style={{
                    background: "rgba(255,255,255,0.08)",
                    border: "1px solid rgba(255,255,255,0.15)",
                    color: "#cbd5e1",
                    borderRadius: "8px",
                    padding: "9px 16px",
                    cursor: "pointer",
                    fontSize: "13px",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  data-testid="p06-save-geometry-btn"
                  style={{
                    background: "#059669",
                    border: "1px solid rgba(52, 211, 153, 0.5)",
                    color: "#ffffff",
                    fontWeight: 600,
                    borderRadius: "8px",
                    padding: "9px 20px",
                    cursor: isSubmitting ? "not-allowed" : "pointer",
                    fontSize: "13px",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  {isSubmitting ? "Persisting..." : "Save to Field"}
                </button>
              </footer>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

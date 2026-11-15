"use client";

import { useEffect, useState } from "react";
import { Edit3, Trash2, History, AlertTriangle, X, Check, ShieldAlert, MapPin } from "lucide-react";
import {
  reviseGeometryRegistration,
  revokeGeometryRegistration,
  getGeometryRevisions,
  type GeometryRevisionRecord,
} from "@/lib/agribrain/geometry-authoring";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";

interface LifecycleModalProps {
  plotId: string;
  entity: WorkspaceFeatureEnvelope;
  mode: "revise" | "revoke" | "history" | null;
  onClose: () => void;
  onRevised: (updatedEntity: WorkspaceFeatureEnvelope) => void;
  onRevoked: (revokedId: string) => void;
  onEditOnMap?: (entity: WorkspaceFeatureEnvelope) => void;
}

export default function WorkspaceGeometryLifecycleModal({
  plotId,
  entity,
  mode,
  onClose,
  onRevised,
  onRevoked,
  onEditOnMap,
}: LifecycleModalProps) {
  const props = (entity.properties || {}) as Record<string, any>;
  const regId = (entity.provenance as any)?.registration_id || entity.entity_id;
  const currentRevision = Number(props.revision) || 1;

  const [label, setLabel] = useState(String(props.name || entity.entity_id));
  const [notes, setNotes] = useState(String(props.notes || ""));
  const initialCoordinatesJson = entity.geometry?.coordinates
    ? JSON.stringify(entity.geometry.coordinates)
    : "";
  const [coordinatesText, setCoordinatesText] = useState(initialCoordinatesJson);
  const [revokeReason, setRevokeReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // History state
  const [revisions, setRevisions] = useState<GeometryRevisionRecord[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    if (mode === "history" && regId) {
      setLoadingHistory(true);
      setErrorMessage(null);
      getGeometryRevisions(plotId, regId)
        .then((res) => {
          setRevisions(res.revisions || []);
          setLoadingHistory(false);
        })
        .catch((err) => {
          setErrorMessage(err.message || "Failed to load revision history");
          setLoadingHistory(false);
        });
    }
  }, [mode, plotId, regId]);

  if (!mode) return null;

  const handleReviseSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    let revisedGeometry: any = undefined;
    if (coordinatesText.trim() && coordinatesText.trim() !== initialCoordinatesJson.trim()) {
      try {
        const parsed = JSON.parse(coordinatesText.trim());
        if (!Array.isArray(parsed)) {
          throw new Error("Coordinates must be a JSON array");
        }
        const geomType = entity.geometry?.type || (entity.entity_kind === "DRONE_MISSION" ? "LineString" : "Polygon");
        if (geomType === "Polygon") {
          const ring = Array.isArray(parsed[0]) && typeof parsed[0][0] === "number" ? parsed : parsed[0];
          if (!Array.isArray(ring) || ring.length < 3) {
            throw new Error("Polygon requires at least 3 vertices");
          }
          const first = ring[0];
          const last = ring[ring.length - 1];
          const closedRing = [...ring];
          if (first[0] !== last[0] || first[1] !== last[1]) {
            closedRing.push([first[0], first[1]]);
          }
          revisedGeometry = {
            type: "Polygon",
            coordinates: [closedRing],
          };
        } else {
          if (parsed.length < 2) {
            throw new Error("LineString requires at least 2 vertices");
          }
          revisedGeometry = {
            type: "LineString",
            coordinates: parsed,
          };
        }
      } catch (parseErr: any) {
        setIsSubmitting(false);
        setErrorMessage(`Invalid coordinates format: ${parseErr.message}`);
        return;
      }
    }

    try {
      const res = await reviseGeometryRegistration(plotId, regId, {
        expected_revision: currentRevision,
        label: label.trim(),
        notes: notes.trim() || null,
        geometry: revisedGeometry,
      });
      setIsSubmitting(false);
      onClose();
      if (res.entity) onRevised(res.entity);
    } catch (err: any) {
      setIsSubmitting(false);
      setErrorMessage(err.message || "Revision failed");
    }
  };

  const handleRevokeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await revokeGeometryRegistration(plotId, regId, currentRevision, revokeReason.trim() || undefined);
      setIsSubmitting(false);
      onClose();
      onRevoked(regId);
    } catch (err: any) {
      setIsSubmitting(false);
      setErrorMessage(err.message || "Revocation failed");
    }
  };

  return (
    <div
      className="pw-modal-backdrop"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.75)",
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
        data-testid="p06-lifecycle-modal"
        style={{
          background: "#0f172a",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          borderRadius: "14px",
          maxWidth: "520px",
          width: "100%",
          padding: "24px",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.8)",
          color: "#f8fafc",
        }}
      >
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {mode === "revise" && <Edit3 size={18} className="text-amber-400" />}
            {mode === "revoke" && <Trash2 size={18} className="text-rose-400" />}
            {mode === "history" && <History size={18} className="text-cyan-400" />}
            <h3 style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>
              {mode === "revise" && `Revise Geometry (Rev ${currentRevision} → ${currentRevision + 1})`}
              {mode === "revoke" && "Revoke Owner-Declared Geometry"}
              {mode === "history" && "Append-Only Revision History"}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer" }}
          >
            <X size={18} />
          </button>
        </header>

        {/* 1. REVISE MODE */}
        {mode === "revise" && (
          <form onSubmit={handleReviseSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", color: "#cbd5e1", marginBottom: "5px", fontWeight: 600 }}>
                Feature Name / Label *
              </label>
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
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

            <div>
              <label style={{ display: "block", fontSize: "12px", color: "#cbd5e1", marginBottom: "5px", fontWeight: 600 }}>
                Revision Notes
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                placeholder="Reason or field context for this revision..."
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

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <label style={{ fontSize: "12px", color: "#cbd5e1", fontWeight: 600 }}>
                  Geometry Vertices ({entity.geometry?.type || "Unknown"})
                </label>
                {onEditOnMap && (
                  <button
                    type="button"
                    data-testid="p06-edit-on-map-btn"
                    onClick={() => {
                      onClose();
                      onEditOnMap(entity);
                    }}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                      background: "rgba(56, 189, 248, 0.15)",
                      border: "1px solid rgba(56, 189, 248, 0.35)",
                      color: "#38bdf8",
                      borderRadius: "6px",
                      padding: "4px 10px",
                      fontSize: "11px",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    <MapPin size={13} /> Adjust Vertices on Field Map
                  </button>
                )}
              </div>
              <textarea
                value={coordinatesText}
                onChange={(e) => setCoordinatesText(e.target.value)}
                rows={3}
                placeholder="Coordinates JSON array [ [lon, lat], ... ]"
                style={{
                  width: "100%",
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.15)",
                  borderRadius: "8px",
                  padding: "8px 12px",
                  color: "#f8fafc",
                  fontSize: "11px",
                  fontFamily: "monospace",
                  outline: "none",
                  resize: "vertical",
                }}
              />
            </div>

            <div
              style={{
                background: "rgba(56, 189, 248, 0.1)",
                border: "1px solid rgba(56, 189, 248, 0.25)",
                borderRadius: "8px",
                padding: "10px 12px",
                fontSize: "12px",
                color: "#7dd3fc",
              }}
            >
              <strong>Optimistic Concurrency Protection</strong>
              <p style={{ margin: "2px 0 0", color: "#bae6fd", fontSize: "11px" }}>
                Asserting revision <code>{currentRevision}</code>. The previous geometry will be permanently recorded in the immutable revision log before advancing to revision <code>{currentRevision + 1}</code>.
              </p>
            </div>

            {errorMessage && (
              <div style={{ color: "#f87171", fontSize: "12px" }}>{errorMessage}</div>
            )}

            <footer style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  background: "rgba(255,255,255,0.08)",
                  border: "1px solid rgba(255,255,255,0.15)",
                  color: "#cbd5e1",
                  borderRadius: "8px",
                  padding: "9px 16px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                data-testid="p06-submit-revision-btn"
                style={{
                  background: "#d97706",
                  border: "1px solid #f59e0b",
                  color: "#ffffff",
                  fontWeight: 600,
                  borderRadius: "8px",
                  padding: "9px 20px",
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                }}
              >
                {isSubmitting ? "Applying Revision..." : "Save Revision"}
              </button>
            </footer>
          </form>
        )}

        {/* 2. REVOKE MODE */}
        {mode === "revoke" && (
          <form onSubmit={handleRevokeSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div
              style={{
                background: "rgba(244, 63, 94, 0.12)",
                border: "1px solid rgba(244, 63, 94, 0.3)",
                borderRadius: "8px",
                padding: "12px",
                display: "flex",
                gap: "10px",
                alignItems: "flex-start",
                color: "#fecdd3",
              }}
            >
              <AlertTriangle size={20} className="text-rose-400 shrink-0" style={{ marginTop: "2px" }} />
              <div>
                <strong style={{ color: "#ffe4e6" }}>Soft-Revoke Geometry Registration</strong>
                <p style={{ margin: "4px 0 0", fontSize: "12px", color: "#fda4af" }}>
                  This action archives the feature and immediately omits it from the active map scene and entity directory. The complete geometry revision history remains auditable.
                </p>
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", color: "#cbd5e1", marginBottom: "5px", fontWeight: 600 }}>
                Revocation Reason (Optional)
              </label>
              <input
                type="text"
                value={revokeReason}
                onChange={(e) => setRevokeReason(e.target.value)}
                placeholder="e.g. Flight plan completed / scout area resolved"
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

            {errorMessage && (
              <div style={{ color: "#f87171", fontSize: "12px" }}>{errorMessage}</div>
            )}

            <footer style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  background: "rgba(255,255,255,0.08)",
                  border: "1px solid rgba(255,255,255,0.15)",
                  color: "#cbd5e1",
                  borderRadius: "8px",
                  padding: "9px 16px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                data-testid="p06-submit-revoke-btn"
                style={{
                  background: "#e11d48",
                  border: "1px solid #f43f5e",
                  color: "#ffffff",
                  fontWeight: 600,
                  borderRadius: "8px",
                  padding: "9px 20px",
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                }}
              >
                {isSubmitting ? "Revoking..." : "Confirm Revocation"}
              </button>
            </footer>
          </form>
        )}

        {/* 3. HISTORY MODE */}
        {mode === "history" && (
          <div>
            {loadingHistory ? (
              <p style={{ color: "#94a3b8", fontSize: "13px" }}>Loading immutable revision ledger...</p>
            ) : errorMessage ? (
              <p style={{ color: "#f87171", fontSize: "13px" }}>{errorMessage}</p>
            ) : revisions.length === 0 ? (
              <p style={{ color: "#94a3b8", fontSize: "13px" }}>No past revisions found.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "360px", overflowY: "auto" }}>
                {revisions.map((rev) => (
                  <div
                    key={rev.id}
                    style={{
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      borderRadius: "8px",
                      padding: "10px 14px",
                      fontSize: "12px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontWeight: 700, color: rev.operation === "REVOKE" ? "#f43f5e" : "#38bdf8" }}>
                        Revision {rev.revision} · {rev.operation}
                      </span>
                      <time style={{ color: "#94a3b8", fontSize: "11px" }}>
                        {new Date(rev.createdAt).toLocaleString()}
                      </time>
                    </div>
                    <div style={{ marginTop: "4px", color: "#e2e8f0" }}>{rev.name}</div>
                    {rev.notes && <p style={{ margin: "4px 0 0", color: "#94a3b8", fontSize: "11px" }}>{rev.notes}</p>}
                    <div style={{ marginTop: "6px", fontFamily: "monospace", fontSize: "10px", color: "#8ca895" }}>
                      SHA-256: {rev.geometryDigest.slice(0, 20)}…
                    </div>
                  </div>
                ))}
              </div>
            )}
            <footer style={{ display: "flex", justifyContent: "flex-end", marginTop: "16px" }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  background: "rgba(255,255,255,0.08)",
                  border: "1px solid rgba(255,255,255,0.15)",
                  color: "#cbd5e1",
                  borderRadius: "8px",
                  padding: "8px 18px",
                  cursor: "pointer",
                }}
              >
                Close
              </button>
            </footer>
          </div>
        )}
      </div>
    </div>
  );
}


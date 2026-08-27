"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { AUDIENCES, type AudienceId, type ContactIntent } from "./data/audiences";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  intent: ContactIntent;
  customTitle?: string;
}

export default function InstitutionalContactDialog({
  isOpen,
  onClose,
  intent,
  customTitle,
}: Props) {
  const audience = AUDIENCES[intent] || AUDIENCES.enterprise;
  const prefersReduced = useReducedMotion();
  const dialogRef = useRef<HTMLDivElement>(null);
  const firstInputRef = useRef<HTMLInputElement>(null);

  const [formData, setFormData] = useState({
    name: "",
    email: "",
    organization: "",
    orgType: "",
    fieldCount: "",
    country: "Algeria",
    message: "",
  });

  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  // Auto focus first input when opened
  useEffect(() => {
    if (isOpen) {
      setStatus("idle");
      setErrorMessage("");
      setTimeout(() => firstInputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Trap ESC key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.email || !formData.organization) {
      setErrorMessage("Please complete all required fields.");
      setStatus("error");
      return;
    }

    setStatus("submitting");
    setErrorMessage("");

    try {
      const res = await fetch("/api/marketing/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          intent,
          ...formData,
        }),
      });

      if (!res.ok) {
        throw new Error("Server error, please try again.");
      }

      setStatus("success");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to submit request.");
      setStatus("error");
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="dialog-title"
        >
          {/* Backdrop */}
          <motion.div
            initial={prefersReduced ? { opacity: 1 } : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={prefersReduced ? { opacity: 0 } : { opacity: 0 }}
            onClick={onClose}
            style={{
              position: "absolute",
              inset: 0,
              background: "rgba(3, 7, 18, 0.82)",
              backdropFilter: "blur(8px)",
            }}
          />

          {/* Modal Container */}
          <motion.div
            ref={dialogRef}
            initial={prefersReduced ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={prefersReduced ? { opacity: 0, scale: 1 } : { opacity: 0, scale: 0.95, y: 12 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            style={{
              position: "relative",
              width: "100%",
              maxWidth: "540px",
              maxHeight: "90vh",
              overflowY: "auto",
              background: "var(--surface-modal)",
              borderRadius: "var(--radius-xl)",
              border: `1px solid ${audience.color}30`,
              boxShadow: "0 24px 80px rgba(0,0,0,0.6)",
              padding: "32px",
              color: "var(--text-primary)",
            }}
          >
            {/* Close Button */}
            <button
              onClick={onClose}
              aria-label="Close dialog"
              style={{
                position: "absolute",
                top: "20px",
                right: "20px",
                background: "rgba(71,85,105,0.1)",
                border: "1px solid var(--border-subtle)",
                color: "var(--text-muted)",
                width: "32px",
                height: "32px",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
              }}
            >
              ✕
            </button>

            {/* Header */}
            <div style={{ marginBottom: "24px" }}>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "4px 12px",
                  borderRadius: "20px",
                  fontSize: "11px",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  background: `${audience.color}15`,
                  color: audience.color,
                  marginBottom: "12px",
                }}
              >
                <span aria-hidden="true">{audience.icon}</span> {audience.label} Evaluation
              </div>
              <h2
                id="dialog-title"
                style={{
                  fontSize: "22px",
                  fontWeight: 700,
                  margin: "0 0 6px",
                  color: "var(--text-primary)",
                }}
              >
                {customTitle || `Discuss AgriWise for ${audience.label}s`}
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
                Connect with our technical & agricultural intelligence team to evaluate deployment or API integration.
              </p>
            </div>

            {status === "success" ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "32px 16px",
                  background: "rgba(34, 197, 94, 0.06)",
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid rgba(34, 197, 94, 0.2)",
                }}
              >
                <div style={{ fontSize: "2.5rem", marginBottom: "12px" }}>✅</div>
                <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--field-green)", margin: "0 0 8px" }}>
                  Request Received
                </h3>
                <p style={{ fontSize: "14px", color: "var(--text-body)", margin: "0 0 20px" }}>
                  Thank you for reaching out. An AgriWise technical specialist will review your request and contact you within 24 hours.
                </p>
                <button onClick={onClose} className="marketing-cta-primary" style={{ padding: "10px 24px", fontSize: "14px" }}>
                  Close
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {status === "error" && (
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: "var(--radius-sm)",
                      background: "rgba(248, 113, 113, 0.1)",
                      border: "1px solid rgba(248, 113, 113, 0.2)",
                      color: "var(--risk-red)",
                      fontSize: "13px",
                    }}
                  >
                    {errorMessage}
                  </div>
                )}

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}>
                      Full Name *
                    </label>
                    <input
                      ref={firstInputRef}
                      type="text"
                      required
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="e.g. Dr. Ahmed Benali"
                      style={{
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--surface-elevated-solid)",
                        border: "1px solid var(--border-default)",
                        color: "var(--text-primary)",
                        fontSize: "13px",
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}>
                      Work Email *
                    </label>
                    <input
                      type="email"
                      required
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      placeholder="name@organization.com"
                      style={{
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--surface-elevated-solid)",
                        border: "1px solid var(--border-default)",
                        color: "var(--text-primary)",
                        fontSize: "13px",
                      }}
                    />
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}>
                      Organization Name *
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.organization}
                      onChange={(e) => setFormData({ ...formData, organization: e.target.value })}
                      placeholder="e.g. National Agribank / AgroEnterprise"
                      style={{
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--surface-elevated-solid)",
                        border: "1px solid var(--border-default)",
                        color: "var(--text-primary)",
                        fontSize: "13px",
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}>
                      Country
                    </label>
                    <input
                      type="text"
                      value={formData.country}
                      onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                      placeholder="Algeria"
                      style={{
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--surface-elevated-solid)",
                        border: "1px solid var(--border-default)",
                        color: "var(--text-primary)",
                        fontSize: "13px",
                      }}
                    />
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}>
                      Organization Type
                    </label>
                    <select
                      value={formData.orgType}
                      onChange={(e) => setFormData({ ...formData, orgType: e.target.value })}
                      style={{
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--surface-elevated-solid)",
                        border: "1px solid var(--border-default)",
                        color: "var(--text-primary)",
                        fontSize: "13px",
                      }}
                    >
                      <option value="">Select Type...</option>
                      <option value="Commercial Farm">Commercial Farm</option>
                      <option value="Government Ministry / Agency">Government Ministry / Agency</option>
                      <option value="Bank / Financial Institution">Bank / Financial Institution</option>
                      <option value="Insurance Provider">Insurance Provider</option>
                      <option value="Agricultural Cooperative">Agricultural Cooperative</option>
                      <option value="Agribusiness / Supply Chain">Agribusiness / Supply Chain</option>
                      <option value="Research Institution">Research Institution</option>
                      <option value="Technology Partner / Developer">Technology Partner / Developer</option>
                    </select>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}>
                      Scope / Scale
                    </label>
                    <input
                      type="text"
                      value={formData.fieldCount}
                      onChange={(e) => setFormData({ ...formData, fieldCount: e.target.value })}
                      placeholder="e.g. 5,000 ha / 120 credit lines"
                      style={{
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--surface-elevated-solid)",
                        border: "1px solid var(--border-default)",
                        color: "var(--text-primary)",
                        fontSize: "13px",
                      }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px" }}>
                    Evaluation Goals / Message
                  </label>
                  <textarea
                    rows={3}
                    value={formData.message}
                    onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                    placeholder="Describe your operational or evaluation needs..."
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      borderRadius: "var(--radius-sm)",
                      background: "var(--surface-elevated-solid)",
                      border: "1px solid var(--border-default)",
                      color: "var(--text-primary)",
                      fontSize: "13px",
                      resize: "vertical",
                    }}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "8px" }}>
                  <button
                    type="button"
                    onClick={onClose}
                    className="marketing-cta-ghost"
                    style={{ fontSize: "13px" }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={status === "submitting"}
                    className="marketing-cta-primary"
                    style={{ padding: "10px 24px", fontSize: "14px" }}
                  >
                    {status === "submitting" ? "Submitting..." : "Submit Evaluation Request →"}
                  </button>
                </div>
              </form>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  AlertTriangle,
  Tractor,
  Building2,
  Users,
  GraduationCap,
  Landmark,
  Eye,
  EyeOff,
} from "lucide-react";
import { useLanguage } from "@/lib/i18n/LanguageContext";
import LanguageSwitcher from "@/components/common/LanguageSwitcher";
import wilayasData from "@/data/algeria/wilayas.json";

export default function RegisterPage() {
  const { t, isRtl, dir, locale } = useLanguage();
  const router = useRouter();

  // Form fields
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [wilayaCode, setWilayaCode] = useState("");
  const [role, setRole] = useState("SMALL_FARMER");
  const [farmName, setFarmName] = useState("");
  const [farmArea, setFarmArea] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const roles = [
    { id: "SMALL_FARMER", label: t.auth.roles.smallFarmer, icon: Tractor },
    { id: "MEDIUM_FARMER", label: t.auth.roles.mediumFarmer, icon: Tractor },
    { id: "LARGE_FARMER", label: t.auth.roles.largeFarmer, icon: Building2 },
    { id: "AGRONOMIST", label: t.auth.roles.agronomist, icon: GraduationCap },
    { id: "COOPERATIVE_MANAGER", label: t.auth.roles.cooperative, icon: Users },
    { id: "NATIONAL_GOV", label: t.auth.roles.sovereign, icon: Landmark },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanedPhone = phone.replace(/[\s-]/g, "");
    if (!cleanedPhone.match(/^0[567]\d{8}$/)) {
      setError(t.auth.errors.invalidPhone);
      return;
    }

    if (!name.trim()) {
      setError(t.auth.errors.required);
      return;
    }

    if (!wilayaCode) {
      setError(t.auth.errors.required);
      return;
    }

    if (password && password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    const selectedWilaya = wilayasData.wilayas.find((w) => w.code === wilayaCode);
    const wilayaName =
      locale === "ar"
        ? selectedWilaya?.nameAr
        : locale === "fr"
        ? selectedWilaya?.nameFr
        : selectedWilaya?.nameEn;

    setLoading(true);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          phone: cleanedPhone,
          email: email.trim() || undefined,
          password: password || undefined,
          wilaya: wilayaName || selectedWilaya?.nameAr || "Algeria",
          wilayaCode,
          role,
          farmName: farmName.trim() || undefined,
          farmArea: farmArea ? Number(farmArea) : undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || t.auth.errors.general);
      }

      router.push("/farm");
      router.refresh();
    } catch (err: any) {
      setError(err.message || t.auth.errors.general);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#05070B",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        position: "relative",
        overflow: "hidden",
        direction: dir,
        color: "#F8FAFC",
        padding: "24px 16px",
      }}
    >
      {/* Ambient Top Mesh Glow */}
      <div
        style={{
          position: "absolute",
          top: "-15%",
          left: "50%",
          transform: "translateX(-50%)",
          width: "900px",
          height: "550px",
          background: "radial-gradient(ellipse, rgba(34, 197, 94, 0.12) 0%, rgba(5, 7, 11, 0) 70%)",
          pointerEvents: "none",
          zIndex: 0,
        }}
      />

      {/* Top Header Bar */}
      <header
        style={{
          maxWidth: "1140px",
          width: "100%",
          margin: "0 auto",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          position: "relative",
          zIndex: 10,
        }}
      >
        <Link
          href="/"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            textDecoration: "none",
            color: "#FFFFFF",
          }}
        >
          <span
            style={{
              fontSize: "18px",
              fontWeight: 800,
              letterSpacing: "-0.025em",
              fontFamily: "var(--font-heading)",
            }}
          >
            AGRIWISE
          </span>
          <span
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              backgroundColor: "#22c55e",
              boxShadow: "0 0 10px #22c55e",
            }}
          />
        </Link>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <LanguageSwitcher variant="capsule" />
          <Link
            href="/login"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "12px",
              fontWeight: 600,
              color: "#94A3B8",
              textDecoration: "none",
              padding: "6px 12px",
              borderRadius: "8px",
              background: "rgba(255, 255, 255, 0.03)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            {isRtl ? <ArrowRight size={14} /> : <ArrowLeft size={14} />}
            <span>{t.auth.signIn}</span>
          </Link>
        </div>
      </header>

      {/* Main Glassmorphic Registration Card */}
      <main
        style={{
          maxWidth: "580px",
          width: "100%",
          margin: "32px auto",
          position: "relative",
          zIndex: 10,
        }}
      >
        <div
          className="dribbble-glass-card"
          style={{
            background: "rgba(10, 16, 26, 0.88)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            border: "1px solid rgba(34, 197, 94, 0.25)",
            borderRadius: "24px",
            padding: "36px 32px",
            boxShadow: "0 24px 60px rgba(0, 0, 0, 0.6), 0 0 30px rgba(34, 197, 94, 0.12)",
          }}
        >
          {/* Header Title */}
          <div style={{ textAlign: "center", marginBottom: "26px" }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "3px 10px",
                borderRadius: "9999px",
                background: "rgba(34, 197, 94, 0.1)",
                border: "1px solid rgba(34, 197, 94, 0.25)",
                color: "#22c55e",
                fontSize: "11px",
                fontFamily: "var(--font-mono)",
                fontWeight: 700,
                marginBottom: "12px",
              }}
            >
              <Sparkles size={12} />
              <span>ALGERIA BIOPHYSICAL REGISTRY</span>
            </div>

            <h1
              style={{
                fontSize: "22px",
                fontWeight: 800,
                color: "#FFFFFF",
                letterSpacing: "-0.02em",
                margin: "0 0 8px",
              }}
            >
              {t.auth.registerTitle}
            </h1>
            <p style={{ fontSize: "13px", color: "#94A3B8", margin: 0, lineHeight: 1.5 }}>
              {t.auth.registerSubtitle}
            </p>
          </div>

          {/* Feedback Error */}
          {error && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "10px 14px",
                borderRadius: "10px",
                background: "rgba(239, 68, 68, 0.12)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                color: "#F87171",
                fontSize: "12px",
                marginBottom: "20px",
              }}
            >
              <AlertTriangle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* 1. Name & Phone */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "14px",
                marginBottom: "16px",
              }}
            >
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#CBD5E1", marginBottom: "6px" }}>
                  {t.auth.labels.name} *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t.auth.labels.namePlaceholder}
                  required
                  style={{
                    width: "100%",
                    background: "rgba(6, 12, 9, 0.65)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "12px",
                    padding: "12px 14px",
                    color: "#FFFFFF",
                    fontSize: "13px",
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#CBD5E1", marginBottom: "6px" }}>
                  {t.auth.labels.phone} *
                </label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="05XX XX XX XX"
                  required
                  dir="ltr"
                  style={{
                    width: "100%",
                    background: "rgba(6, 12, 9, 0.65)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "12px",
                    padding: "12px 14px",
                    color: "#FFFFFF",
                    fontSize: "13px",
                    fontFamily: "var(--font-mono)",
                    outline: "none",
                  }}
                />
              </div>
            </div>

            {/* 2. Wilaya & Password */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "14px",
                marginBottom: "16px",
              }}
            >
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#CBD5E1", marginBottom: "6px" }}>
                  {t.auth.labels.wilaya} *
                </label>
                <select
                  value={wilayaCode}
                  onChange={(e) => setWilayaCode(e.target.value)}
                  required
                  style={{
                    width: "100%",
                    background: "rgba(6, 12, 9, 0.95)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "12px",
                    padding: "12px 14px",
                    color: "#FFFFFF",
                    fontSize: "13px",
                    outline: "none",
                    cursor: "pointer",
                  }}
                >
                  <option value="">{t.auth.labels.selectWilaya}</option>
                  {wilayasData.wilayas.map((w) => {
                    const wilayaDisplayName =
                      locale === "ar"
                        ? `${w.code} - ${w.nameAr}`
                        : locale === "fr"
                        ? `${w.code} - ${w.nameFr}`
                        : `${w.code} - ${w.nameEn}`;
                    return (
                      <option key={w.code} value={w.code} style={{ background: "#05070B", color: "#FFFFFF" }}>
                        {wilayaDisplayName}
                      </option>
                    );
                  })}
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#CBD5E1", marginBottom: "6px" }}>
                  {t.auth.labels.password} *
                </label>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    background: "rgba(6, 12, 9, 0.65)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "12px",
                    padding: "0 12px",
                  }}
                >
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min. 6 chars"
                    required
                    style={{
                      width: "100%",
                      background: "transparent",
                      border: "none",
                      padding: "12px 0",
                      color: "#FFFFFF",
                      fontSize: "13px",
                      outline: "none",
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#64748B",
                      cursor: "pointer",
                    }}
                  >
                    {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>
            </div>

            {/* 3. Role Selector */}
            <div style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#CBD5E1", marginBottom: "8px" }}>
                {t.auth.labels.role}
              </label>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, 1fr)",
                  gap: "8px",
                }}
              >
                {roles.map((r) => {
                  const isSelected = role === r.id;
                  const Icon = r.icon;
                  return (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => setRole(r.id)}
                      className="transition-smooth"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        padding: "8px 10px",
                        borderRadius: "10px",
                        border: isSelected ? "1px solid #22c55e" : "1px solid rgba(255, 255, 255, 0.08)",
                        background: isSelected ? "rgba(34, 197, 94, 0.14)" : "rgba(255, 255, 255, 0.03)",
                        color: isSelected ? "#FFFFFF" : "#94A3B8",
                        cursor: "pointer",
                        fontSize: "11px",
                        fontWeight: 600,
                        textAlign: isRtl ? "right" : "left",
                      }}
                    >
                      <Icon size={14} style={{ color: isSelected ? "#22c55e" : "#64748B", flexShrink: 0 }} />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 4. Optional Initial Farm */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1.2fr 0.8fr",
                gap: "14px",
                marginBottom: "24px",
              }}
            >
              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94A3B8", marginBottom: "6px" }}>
                  {t.auth.labels.farmName}
                </label>
                <input
                  type="text"
                  value={farmName}
                  onChange={(e) => setFarmName(e.target.value)}
                  placeholder={t.auth.labels.farmNamePlaceholder}
                  style={{
                    width: "100%",
                    background: "rgba(6, 12, 9, 0.65)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "12px",
                    padding: "12px 14px",
                    color: "#FFFFFF",
                    fontSize: "13px",
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94A3B8", marginBottom: "6px" }}>
                  {t.auth.labels.farmArea}
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={farmArea}
                  onChange={(e) => setFarmArea(e.target.value)}
                  placeholder={t.auth.labels.farmAreaPlaceholder}
                  style={{
                    width: "100%",
                    background: "rgba(6, 12, 9, 0.65)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "12px",
                    padding: "12px 14px",
                    color: "#FFFFFF",
                    fontSize: "13px",
                    outline: "none",
                  }}
                />
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="hover-lift transition-smooth"
              style={{
                width: "100%",
                padding: "14px",
                borderRadius: "12px",
                background: "#22c55e",
                border: "none",
                color: "#05070B",
                fontSize: "14px",
                fontWeight: 700,
                cursor: loading ? "not-allowed" : "pointer",
                boxShadow: "0 4px 20px rgba(34, 197, 94, 0.35)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
              }}
            >
              <span>{loading ? "Initializing Farm Twin..." : t.auth.signUp}</span>
              <ShieldCheck size={16} />
            </button>
          </form>

          {/* Bottom Switcher */}
          <div
            style={{
              marginTop: "24px",
              paddingTop: "16px",
              borderTop: "1px solid rgba(255, 255, 255, 0.08)",
              textAlign: "center",
              fontSize: "13px",
              color: "#94A3B8",
            }}
          >
            <span>{t.auth.switch.haveAccount} </span>
            <Link
              href="/login"
              style={{
                color: "#22c55e",
                fontWeight: 700,
                textDecoration: "none",
              }}
            >
              {t.auth.switch.loginNow}
            </Link>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer
        style={{
          maxWidth: "1140px",
          width: "100%",
          margin: "0 auto",
          textAlign: "center",
          fontSize: "12px",
          color: "#64748B",
          position: "relative",
          zIndex: 10,
        }}
      >
        <span>AgriWise Agricultural Intelligence · Algeria Sovereign Deployment</span>
      </footer>
    </div>
  );
}

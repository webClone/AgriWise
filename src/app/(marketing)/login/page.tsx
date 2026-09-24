"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Smartphone,
  KeyRound,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Eye,
  EyeOff,
  Tractor,
  GraduationCap,
  Landmark,
  ArrowLeft,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useLanguage } from "@/lib/i18n/LanguageContext";
import LanguageSwitcher from "@/components/common/LanguageSwitcher";

function LoginForm() {
  const { t, isRtl, dir } = useLanguage();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectPath = searchParams.get("redirect") || "/farm";

  const [activeTab, setActiveTab] = useState<"otp" | "password" | "demo">("otp");

  // Phone OTP state
  const [phone, setPhone] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpStep, setOtpStep] = useState<"phone" | "verify">("phone");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);

  // Password state
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // General state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Countdown timer for OTP
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown((c) => c - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  // Handle Send OTP
  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    const cleaned = phone.replace(/[\s-]/g, "");
    if (!cleaned.match(/^0[567]\d{8}$/)) {
      setError(t.auth.errors.invalidPhone);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/otp/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: cleaned }),
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || t.auth.errors.general);
      }

      setOtpStep("verify");
      setCountdown(60);
      if (data.code) {
        setDevCode(data.code);
      }
      setSuccessMsg(data.message || "Code sent successfully");
    } catch (err: any) {
      setError(err.message || t.auth.errors.general);
    } finally {
      setLoading(false);
    }
  };

  // Handle Verify OTP
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanedPhone = phone.replace(/[\s-]/g, "");
    const cleanedCode = otpCode.trim();

    if (cleanedCode.length < 6) {
      setError(t.auth.errors.invalidOtp);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/otp/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: cleanedPhone,
          code: cleanedCode,
        }),
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || t.auth.errors.invalidOtp);
      }

      router.push(redirectPath);
      router.refresh();
    } catch (err: any) {
      setError(err.message || t.auth.errors.invalidOtp);
    } finally {
      setLoading(false);
    }
  };

  // Handle Password Login
  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!identifier || !password) {
      setError(t.auth.errors.required);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password }),
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || t.auth.errors.invalidCredentials);
      }

      router.push(redirectPath);
      router.refresh();
    } catch (err: any) {
      setError(err.message || t.auth.errors.invalidCredentials);
    } finally {
      setLoading(false);
    }
  };

  // Handle 1-Click Demo Login
  const handleDemoLogin = async (persona: "farmer" | "agronomist" | "sovereign") => {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/demo-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona }),
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || "Demo login failed");
      }

      router.push(data.redirect || redirectPath);
      router.refresh();
    } catch (err: any) {
      setError(err.message || "Failed to initialize demo persona");
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
      {/* Background Ambient Glows */}
      <div
        style={{
          position: "absolute",
          top: "-15%",
          left: "50%",
          transform: "translateX(-50%)",
          width: "800px",
          height: "500px",
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
            href="/"
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
            <span>{isRtl ? "العودة للرئيسية" : "Back to Home"}</span>
          </Link>
        </div>
      </header>

      {/* Main Glassmorphic Auth Card */}
      <main
        style={{
          maxWidth: "480px",
          width: "100%",
          margin: "40px auto",
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
          {/* Badge & Title */}
          <div style={{ textAlign: "center", marginBottom: "28px" }}>
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
              <span>MESIA R2 COGNITIVE ENGINE</span>
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
              {t.auth.loginTitle}
            </h1>
            <p style={{ fontSize: "13px", color: "#94A3B8", margin: 0, lineHeight: 1.5 }}>
              {t.auth.loginSubtitle}
            </p>
          </div>

          {/* Tab Selector Buttons */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "6px",
              background: "rgba(255, 255, 255, 0.03)",
              padding: "4px",
              borderRadius: "12px",
              border: "1px solid rgba(255, 255, 255, 0.06)",
              marginBottom: "24px",
            }}
          >
            <button
              onClick={() => {
                setActiveTab("otp");
                setError(null);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                padding: "8px 10px",
                borderRadius: "9px",
                border: "none",
                cursor: "pointer",
                fontSize: "12px",
                fontWeight: 700,
                background: activeTab === "otp" ? "#22c55e" : "transparent",
                color: activeTab === "otp" ? "#05070B" : "#94A3B8",
                transition: "all 0.2s ease",
              }}
            >
              <Smartphone size={13} />
              <span>{t.auth.tabs.otp}</span>
            </button>

            <button
              onClick={() => {
                setActiveTab("password");
                setError(null);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                padding: "8px 10px",
                borderRadius: "9px",
                border: "none",
                cursor: "pointer",
                fontSize: "12px",
                fontWeight: 700,
                background: activeTab === "password" ? "#22c55e" : "transparent",
                color: activeTab === "password" ? "#05070B" : "#94A3B8",
                transition: "all 0.2s ease",
              }}
            >
              <KeyRound size={13} />
              <span>{t.auth.tabs.password}</span>
            </button>

            <button
              onClick={() => {
                setActiveTab("demo");
                setError(null);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                padding: "8px 10px",
                borderRadius: "9px",
                border: "none",
                cursor: "pointer",
                fontSize: "12px",
                fontWeight: 700,
                background: activeTab === "demo" ? "#22c55e" : "transparent",
                color: activeTab === "demo" ? "#05070B" : "#94A3B8",
                transition: "all 0.2s ease",
              }}
            >
              <Sparkles size={13} />
              <span>{t.auth.tabs.demo}</span>
            </button>
          </div>

          {/* Feedback Messages */}
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

          {successMsg && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "10px 14px",
                borderRadius: "10px",
                background: "rgba(34, 197, 94, 0.12)",
                border: "1px solid rgba(34, 197, 94, 0.3)",
                color: "#22c55e",
                fontSize: "12px",
                marginBottom: "20px",
              }}
            >
              <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
              <span>{successMsg}</span>
            </div>
          )}

          {/* TAB 1: PHONE OTP VERIFICATION */}
          {activeTab === "otp" && (
            <div>
              {otpStep === "phone" ? (
                <form onSubmit={handleSendOtp}>
                  <div style={{ marginBottom: "20px" }}>
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: 600,
                        color: "#CBD5E1",
                        marginBottom: "8px",
                      }}
                    >
                      {t.auth.labels.phone}
                    </label>

                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        background: "rgba(6, 12, 9, 0.65)",
                        border: "1px solid rgba(255, 255, 255, 0.12)",
                        borderRadius: "12px",
                        padding: "0 14px",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "13px",
                          fontFamily: "var(--font-mono)",
                          color: "#22c55e",
                          fontWeight: 700,
                          marginRight: isRtl ? 0 : "8px",
                          marginLeft: isRtl ? "8px" : 0,
                          userSelect: "none",
                        }}
                      >
                        +213
                      </span>
                      <input
                        type="tel"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder={t.auth.labels.phonePlaceholder}
                        required
                        dir="ltr"
                        style={{
                          width: "100%",
                          background: "transparent",
                          border: "none",
                          padding: "14px 0",
                          color: "#FFFFFF",
                          fontSize: "14px",
                          fontFamily: "var(--font-mono)",
                          outline: "none",
                        }}
                      />
                    </div>
                  </div>

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
                    <span>{loading ? t.auth.otp.sendingCode : t.auth.otp.sendCode}</span>
                    <ArrowRight size={16} className="rtl-mirror" />
                  </button>
                </form>
              ) : (
                <form onSubmit={handleVerifyOtp}>
                  <div style={{ marginBottom: "20px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <label style={{ fontSize: "12px", fontWeight: 600, color: "#CBD5E1" }}>
                        {t.auth.otp.enterCode}
                      </label>
                      <button
                        type="button"
                        onClick={() => setOtpStep("phone")}
                        style={{
                          background: "none",
                          border: "none",
                          color: "#22c55e",
                          fontSize: "11px",
                          cursor: "pointer",
                          textDecoration: "underline",
                        }}
                      >
                        {t.auth.otp.changePhone}
                      </button>
                    </div>

                    <input
                      type="text"
                      maxLength={6}
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                      placeholder="• • • • • •"
                      autoFocus
                      required
                      dir="ltr"
                      style={{
                        width: "100%",
                        background: "rgba(6, 12, 9, 0.65)",
                        border: "1px solid rgba(34, 197, 94, 0.4)",
                        borderRadius: "12px",
                        padding: "14px",
                        textAlign: "center",
                        color: "#FFFFFF",
                        fontSize: "24px",
                        fontFamily: "var(--font-mono)",
                        letterSpacing: "8px",
                        outline: "none",
                      }}
                    />

                    {/* Dev Quick-Fill Helper */}
                    {devCode && (
                      <div style={{ marginTop: "10px" }}>
                        <button
                          type="button"
                          onClick={() => setOtpCode(devCode)}
                          style={{
                            width: "100%",
                            padding: "6px 12px",
                            borderRadius: "8px",
                            background: "rgba(34, 197, 94, 0.1)",
                            border: "1px dashed rgba(34, 197, 94, 0.4)",
                            color: "#22c55e",
                            fontSize: "11px",
                            fontFamily: "var(--font-mono)",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: "6px",
                          }}
                        >
                          <Sparkles size={12} />
                          <span>
                            {t.auth.otp.devFill}: <strong>{devCode}</strong>
                          </span>
                        </button>
                      </div>
                    )}
                  </div>

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
                      marginBottom: "14px",
                    }}
                  >
                    <span>{loading ? t.auth.otp.verifying : t.auth.otp.verifyAndLogin}</span>
                    <ShieldCheck size={16} />
                  </button>

                  <div style={{ textAlign: "center" }}>
                    {countdown > 0 ? (
                      <span style={{ fontSize: "12px", color: "#64748B" }}>
                        {t.auth.otp.resendIn} {countdown}s
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={handleSendOtp}
                        style={{
                          background: "none",
                          border: "none",
                          color: "#22c55e",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        {t.auth.otp.resendCode}
                      </button>
                    )}
                  </div>
                </form>
              )}
            </div>
          )}

          {/* TAB 2: PASSWORD LOGIN */}
          {activeTab === "password" && (
            <form onSubmit={handlePasswordLogin}>
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#CBD5E1", marginBottom: "8px" }}>
                  {t.auth.labels.identifier}
                </label>
                <input
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder={t.auth.labels.identifierPlaceholder}
                  required
                  style={{
                    width: "100%",
                    background: "rgba(6, 12, 9, 0.65)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "12px",
                    padding: "14px",
                    color: "#FFFFFF",
                    fontSize: "14px",
                    outline: "none",
                  }}
                />
              </div>

              <div style={{ marginBottom: "22px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#CBD5E1", marginBottom: "8px" }}>
                  {t.auth.labels.password}
                </label>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    background: "rgba(6, 12, 9, 0.65)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "12px",
                    padding: "0 14px",
                  }}
                >
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t.auth.labels.passwordPlaceholder}
                    required
                    style={{
                      width: "100%",
                      background: "transparent",
                      border: "none",
                      padding: "14px 0",
                      color: "#FFFFFF",
                      fontSize: "14px",
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
                      padding: "4px",
                    }}
                    aria-label="Toggle password visibility"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

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
                <span>{loading ? "Authenticating..." : t.auth.signIn}</span>
                <ArrowRight size={16} className="rtl-mirror" />
              </button>
            </form>
          )}

          {/* TAB 3: 1-CLICK DEMO PERSONAS */}
          {activeTab === "demo" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={{ fontSize: "12px", color: "#94A3B8", marginBottom: "4px", lineHeight: 1.5 }}>
                {t.auth.demo.desc}
              </div>

              {/* Persona 1: Smallholder Farmer */}
              <button
                onClick={() => handleDemoLogin("farmer")}
                disabled={loading}
                className="hover-lift transition-smooth"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "12px 14px",
                  borderRadius: "12px",
                  background: "rgba(34, 197, 94, 0.08)",
                  border: "1px solid rgba(34, 197, 94, 0.25)",
                  cursor: "pointer",
                  textAlign: isRtl ? "right" : "left",
                  color: "#FFFFFF",
                }}
              >
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "10px",
                    background: "rgba(34, 197, 94, 0.2)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#22c55e",
                    flexShrink: 0,
                  }}
                >
                  <Tractor size={18} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "13px", fontWeight: 700 }}>
                    {t.auth.demo.farmerTitle}
                  </div>
                  <div style={{ fontSize: "11px", color: "#94A3B8", marginTop: "2px" }}>
                    {t.auth.demo.farmerDesc}
                  </div>
                </div>
              </button>

              {/* Persona 2: Regional Agronomist */}
              <button
                onClick={() => handleDemoLogin("agronomist")}
                disabled={loading}
                className="hover-lift transition-smooth"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "12px 14px",
                  borderRadius: "12px",
                  background: "rgba(59, 130, 246, 0.08)",
                  border: "1px solid rgba(59, 130, 246, 0.25)",
                  cursor: "pointer",
                  textAlign: isRtl ? "right" : "left",
                  color: "#FFFFFF",
                }}
              >
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "10px",
                    background: "rgba(59, 130, 246, 0.2)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#60A5FA",
                    flexShrink: 0,
                  }}
                >
                  <GraduationCap size={18} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "13px", fontWeight: 700 }}>
                    {t.auth.demo.agronomistTitle}
                  </div>
                  <div style={{ fontSize: "11px", color: "#94A3B8", marginTop: "2px" }}>
                    {t.auth.demo.agronomistDesc}
                  </div>
                </div>
              </button>

              {/* Persona 3: Sovereign Food Security */}
              <button
                onClick={() => handleDemoLogin("sovereign")}
                disabled={loading}
                className="hover-lift transition-smooth"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "12px 14px",
                  borderRadius: "12px",
                  background: "rgba(168, 85, 247, 0.08)",
                  border: "1px solid rgba(168, 85, 247, 0.25)",
                  cursor: "pointer",
                  textAlign: isRtl ? "right" : "left",
                  color: "#FFFFFF",
                }}
              >
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "10px",
                    background: "rgba(168, 85, 247, 0.2)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#C084FC",
                    flexShrink: 0,
                  }}
                >
                  <Landmark size={18} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "13px", fontWeight: 700 }}>
                    {t.auth.demo.sovereignTitle}
                  </div>
                  <div style={{ fontSize: "11px", color: "#94A3B8", marginTop: "2px" }}>
                    {t.auth.demo.sovereignDesc}
                  </div>
                </div>
              </button>
            </div>
          )}

          {/* Bottom Switcher: Register Link */}
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
            <span>{t.auth.switch.noAccount} </span>
            <Link
              href="/register"
              style={{
                color: "#22c55e",
                fontWeight: 700,
                textDecoration: "none",
              }}
            >
              {t.auth.switch.registerNow}
            </Link>
          </div>
        </div>
      </main>

      {/* Footer Notice */}
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

export default function LoginPage() {
  return (
    <React.Suspense
      fallback={
        <div
          style={{
            minHeight: "100vh",
            backgroundColor: "#060D17",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#94A3B8",
          }}
        >
          Loading...
        </div>
      }
    >
      <LoginForm />
    </React.Suspense>
  );
}


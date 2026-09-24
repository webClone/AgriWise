"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  User as UserIcon,
  LogOut,
  Tractor,
  ShieldCheck,
  ChevronDown,
  Sparkles,
  Layers,
} from "lucide-react";
import { useLanguage } from "@/lib/i18n/LanguageContext";

interface UserProfile {
  id: string;
  name: string;
  nameAr?: string | null;
  phone: string;
  email?: string | null;
  role: string;
  wilaya?: string;
  wilayaCode?: string;
}

interface UserMenuProps {
  variant?: "nav" | "compact";
}

export default function UserMenu({ variant = "nav" }: UserMenuProps) {
  const { t, isRtl, locale } = useLanguage();
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Check auth session
  useEffect(() => {
    let isMounted = true;
    async function checkAuth() {
      try {
        const res = await fetch("/api/auth/me", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated && data.user && isMounted) {
            setUser(data.user);
          }
        }
      } catch (err) {
        console.warn("Session check error:", err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    checkAuth();
    return () => {
      isMounted = false;
    };
  }, []);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [menuOpen]);

  const handleLogout = async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      setUser(null);
      setMenuOpen(false);
      router.push("/login");
      router.refresh();
    } catch (err) {
      console.error("Logout error:", err);
    }
  };

  if (loading) {
    return (
      <div
        style={{
          width: "32px",
          height: "32px",
          borderRadius: "50%",
          background: "rgba(255, 255, 255, 0.05)",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          animation: "pulse 1.5s infinite ease-in-out",
        }}
      />
    );
  }

  // If unauthenticated: render Sign In & Register links
  if (!user) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <Link
          href="/login"
          className="hover-lift transition-smooth"
          style={{
            fontSize: "13px",
            fontWeight: 600,
            color: "#CBD5E1",
            textDecoration: "none",
            padding: "7px 14px",
            borderRadius: "9999px",
            background: "rgba(255, 255, 255, 0.04)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            fontFamily: "var(--font-heading)",
          }}
        >
          {t.auth.signIn}
        </Link>

        <Link
          href="/register"
          className="hover-lift transition-smooth"
          style={{
            fontSize: "13px",
            fontWeight: 700,
            color: "#05070B",
            textDecoration: "none",
            padding: "7px 16px",
            borderRadius: "9999px",
            background: "#22c55e",
            boxShadow: "0 2px 14px rgba(34, 197, 94, 0.35)",
            fontFamily: "var(--font-heading)",
          }}
        >
          {t.auth.signUp}
        </Link>
      </div>
    );
  }

  // Get display name (Arabic if locale is ar and nameAr available)
  const displayName = (locale === "ar" && user.nameAr) ? user.nameAr : (user.name || "AgriWise User");
  const initials = displayName
    .split(" ")
    .map((n) => n[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  // Role translation lookup
  const roleLabel =
    user.role === "AGRONOMIST"
      ? t.auth.roles.agronomist
      : user.role === "NATIONAL_GOV" || user.role === "LOCAL_GOV"
      ? t.auth.roles.sovereign
      : user.role === "COOPERATIVE_MANAGER"
      ? t.auth.roles.cooperative
      : user.role === "LARGE_FARMER"
      ? t.auth.roles.largeFarmer
      : user.role === "MEDIUM_FARMER"
      ? t.auth.roles.mediumFarmer
      : t.auth.roles.smallFarmer;

  return (
    <div ref={menuRef} style={{ position: "relative" }}>
      {/* Profile Capsule Trigger */}
      <button
        onClick={() => setMenuOpen(!menuOpen)}
        className="hover-lift transition-smooth"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "8px",
          background: "rgba(10, 16, 26, 0.75)",
          border: "1px solid rgba(34, 197, 94, 0.3)",
          padding: "4px 10px 4px 4px",
          borderRadius: "9999px",
          cursor: "pointer",
          color: "#FFFFFF",
          boxShadow: menuOpen ? "0 0 16px rgba(34, 197, 94, 0.25)" : "none",
        }}
        aria-expanded={menuOpen}
        aria-haspopup="true"
      >
        {/* Avatar Circle */}
        <div
          style={{
            width: "28px",
            height: "28px",
            borderRadius: "50%",
            background: "linear-gradient(135deg, #10B981 0%, #047857 100%)",
            color: "#FFFFFF",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "11px",
            fontWeight: 800,
            fontFamily: "var(--font-mono)",
            border: "1px solid rgba(255, 255, 255, 0.2)",
          }}
        >
          {initials || <UserIcon size={14} />}
        </div>

        {/* User Name & Status Dot */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", textAlign: isRtl ? "right" : "left" }}>
          <span
            style={{
              fontSize: "12px",
              fontWeight: 600,
              color: "#F8FAFC",
              maxWidth: "110px",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {displayName}
          </span>
          <span
            style={{
              width: "5px",
              height: "5px",
              borderRadius: "50%",
              backgroundColor: "#22c55e",
              boxShadow: "0 0 8px #22c55e",
            }}
          />
        </div>

        <ChevronDown
          size={14}
          style={{
            color: "#94A3B8",
            transform: menuOpen ? "rotate(180deg)" : "none",
            transition: "transform 0.2s ease",
          }}
        />
      </button>

      {/* Glassmorphic Dropdown Menu */}
      {menuOpen && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: isRtl ? "auto" : 0,
            left: isRtl ? 0 : "auto",
            width: "260px",
            background: "rgba(6, 12, 9, 0.95)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            border: "1px solid rgba(34, 197, 94, 0.25)",
            borderRadius: "16px",
            boxShadow: "0 20px 50px rgba(0, 0, 0, 0.7), 0 0 20px rgba(34, 197, 94, 0.12)",
            padding: "16px",
            zIndex: 1100,
            direction: isRtl ? "rtl" : "ltr",
          }}
          className="anim-scale-up"
        >
          {/* Header Card: User Info */}
          <div
            style={{
              paddingBottom: "12px",
              marginBottom: "12px",
              borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <div style={{ fontSize: "14px", fontWeight: 700, color: "#FFFFFF", marginBottom: "2px" }}>
              {displayName}
            </div>
            <div style={{ fontSize: "11px", color: "#94A3B8", fontFamily: "var(--font-mono)" }}>
              {user.phone}
            </div>
            {user.wilaya && (
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                  marginTop: "6px",
                  fontSize: "10px",
                  fontWeight: 600,
                  color: "#22c55e",
                  background: "rgba(34, 197, 94, 0.1)",
                  padding: "2px 8px",
                  borderRadius: "6px",
                  border: "1px solid rgba(34, 197, 94, 0.2)",
                }}
              >
                <Sparkles size={10} />
                <span>{user.wilaya}</span> · <span>{roleLabel}</span>
              </div>
            )}
          </div>

          {/* Menu Items */}
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <Link
              href="/farm"
              onClick={() => setMenuOpen(false)}
              className="hover-lift transition-smooth"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "9px 12px",
                borderRadius: "10px",
                textDecoration: "none",
                fontSize: "13px",
                fontWeight: 600,
                color: "#F8FAFC",
                background: "rgba(255, 255, 255, 0.03)",
              }}
            >
              <Tractor size={16} style={{ color: "#22c55e" }} />
              <span>{t.auth.userMenu.myFarms}</span>
            </Link>

            <Link
              href="/farm/new"
              onClick={() => setMenuOpen(false)}
              className="hover-lift transition-smooth"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "9px 12px",
                borderRadius: "10px",
                textDecoration: "none",
                fontSize: "13px",
                fontWeight: 600,
                color: "#F8FAFC",
                background: "rgba(255, 255, 255, 0.03)",
              }}
            >
              <Layers size={16} style={{ color: "#00E676" }} />
              <span>+ {t.nav.analyzeField}</span>
            </Link>
          </div>

          {/* Logout Divider */}
          <div
            style={{
              marginTop: "12px",
              paddingTop: "10px",
              borderTop: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <button
              onClick={handleLogout}
              className="hover-lift transition-smooth"
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "9px 12px",
                borderRadius: "10px",
                background: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.2)",
                color: "#F87171",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <LogOut size={16} />
              <span>{t.auth.userMenu.logout}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
